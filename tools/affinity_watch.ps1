# Affinity watcher, ported from the planning spike TQ1b (spikes/TQ1b-timing/tools/affinity_watch.ps1 at
# an earlier prototype) for tools/perf.py: it restricts one game process to a set of logical
# processors, from outside. -Mask takes the set: 0xFFFF (65535), the eight P-cores with both
# hyperthreads, is the 16 LP weaker-machine proxy every timed limit runs on; 0xFF
# (255) is the 8 LP diagnostic recorded beside it.
#
# Protocol: prints READY once its native helper is compiled, then reads one line from stdin: the
# PID of the tools/fh.py process that is about to launch the game. It finds the game process whose
# ancestor chain contains that PID, sets ProcessorAffinity to -Mask, reads it back, and then polls
# every -PollMs until the game exits. Each poll reads the process mask and every thread's own
# affinity mask (NtQueryInformationThread, ThreadBasicInformation). Records are JSON lines in
# -OutFile: one "set" record, one "exit" record (or "timeout" / "fh-gone").
#
# fh.py is not modified, and this script never starts a process: it only watches and pins the one
# fh.py started.
param(
    [Parameter(Mandatory = $true)][string]$OutFile,
    [long]$Mask = 65535,
    [int]$PollMs = 100,
    [double]$FindTimeoutS = 300,
    [string]$Exe = 'factorio.exe'
)
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class Tq1bNative {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct PROCESSENTRY32W {
        public uint dwSize; public uint cntUsage; public uint th32ProcessID; public IntPtr th32DefaultHeapID;
        public uint th32ModuleID; public uint cntThreads; public uint th32ParentProcessID; public int pcPriClassBase;
        public uint dwFlags; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExeFile;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct THREADENTRY32 {
        public uint dwSize; public uint cntUsage; public uint th32ThreadID; public uint th32OwnerProcessID;
        public int tpBasePri; public int tpDeltaPri; public uint dwFlags;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct THREAD_BASIC_INFORMATION {
        public int ExitStatus; public IntPtr TebBaseAddress; public IntPtr UniqueProcess; public IntPtr UniqueThread;
        public UIntPtr AffinityMask; public int Priority; public int BasePriority;
    }
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32FirstW(IntPtr h, ref PROCESSENTRY32W e);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32NextW(IntPtr h, ref PROCESSENTRY32W e);
    [DllImport("kernel32.dll")] static extern bool Thread32First(IntPtr h, ref THREADENTRY32 e);
    [DllImport("kernel32.dll")] static extern bool Thread32Next(IntPtr h, ref THREADENTRY32 e);
    [DllImport("kernel32.dll")] static extern IntPtr OpenThread(uint access, bool inherit, uint tid);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("ntdll.dll")] static extern int NtQueryInformationThread(IntPtr h, int cls, ref THREAD_BASIC_INFORMATION info, int len, IntPtr retLen);

    static bool Bad(IntPtr h) { return h == IntPtr.Zero || h == new IntPtr(-1); }

    // PID of an <exe> process whose ancestor chain (up to 12 levels) contains root; 0 if none.
    public static int FindDescendant(int root, string exe) {
        IntPtr s = CreateToolhelp32Snapshot(2, 0);
        if (Bad(s)) return 0;
        var parent = new Dictionary<uint, uint>();
        var hits = new List<uint>();
        try {
            var e = new PROCESSENTRY32W();
            e.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32W));
            bool ok = Process32FirstW(s, ref e);
            while (ok) {
                parent[e.th32ProcessID] = e.th32ParentProcessID;
                if (string.Equals(e.szExeFile, exe, StringComparison.OrdinalIgnoreCase)) hits.Add(e.th32ProcessID);
                ok = Process32NextW(s, ref e);
            }
        } finally { CloseHandle(s); }
        foreach (uint pid in hits) {
            uint p;
            if (!parent.TryGetValue(pid, out p)) continue;
            for (int i = 0; i < 12 && p != 0; i++) {
                if (p == (uint)root) return (int)pid;
                uint q;
                if (!parent.TryGetValue(p, out q)) break;
                p = q;
            }
        }
        return 0;
    }

    // [threads, threads read, threads with bits outside mask, OR of thread masks, AND of thread masks]
    public static ulong[] ThreadMasks(int pid, ulong mask) {
        ulong n = 0, read = 0, outside = 0, orv = 0, andv = ulong.MaxValue;
        IntPtr s = CreateToolhelp32Snapshot(4, 0);
        if (Bad(s)) return new ulong[] { 0, 0, 0, 0, 0 };
        try {
            var e = new THREADENTRY32();
            e.dwSize = (uint)Marshal.SizeOf(typeof(THREADENTRY32));
            bool ok = Thread32First(s, ref e);
            while (ok) {
                if (e.th32OwnerProcessID == (uint)pid) {
                    n++;
                    foreach (uint access in new uint[] { 0x0800, 0x0040 }) {
                        IntPtr h = OpenThread(access, false, e.th32ThreadID);
                        if (h == IntPtr.Zero) continue;
                        var tbi = new THREAD_BASIC_INFORMATION();
                        int st = NtQueryInformationThread(h, 0, ref tbi, Marshal.SizeOf(typeof(THREAD_BASIC_INFORMATION)), IntPtr.Zero);
                        CloseHandle(h);
                        if (st == 0) {
                            ulong m = tbi.AffinityMask.ToUInt64();
                            read++; orv |= m; andv &= m;
                            if ((m & ~mask) != 0) outside++;
                            break;
                        }
                    }
                }
                ok = Thread32Next(s, ref e);
            }
        } finally { CloseHandle(s); }
        if (read == 0) andv = 0;
        return new ulong[] { n, read, outside, orv, andv };
    }
}
'@

function Emit($obj) {
    $obj['unix_ms'] = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
    [System.IO.File]::AppendAllText($OutFile, ($obj | ConvertTo-Json -Compress -Depth 5) + "`n")
}

[Console]::Out.WriteLine('READY')
[Console]::Out.Flush()
$fhPid = [int]([Console]::In.ReadLine())
$umask = [UInt64]$Mask
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$gamePid = 0
$loops = 0
while ($true) {
    $gamePid = [Tq1bNative]::FindDescendant($fhPid, $Exe)
    if ($gamePid -ne 0) { break }
    $loops++
    if ($sw.Elapsed.TotalSeconds -gt $FindTimeoutS) { Emit @{ event = 'timeout'; fh_pid = $fhPid }; exit 2 }
    if (($loops % 200) -eq 0) {
        try { $null = [System.Diagnostics.Process]::GetProcessById($fhPid) } catch { Emit @{ event = 'fh-gone'; fh_pid = $fhPid }; exit 3 }
    }
    [System.Threading.Thread]::Sleep(1)
}
$found_ms = $sw.Elapsed.TotalMilliseconds
$p = [System.Diagnostics.Process]::GetProcessById($gamePid)
$before = [long]$p.ProcessorAffinity
$p.ProcessorAffinity = [IntPtr]$Mask
$tSet = [DateTime]::Now
$p.Refresh()
$readback = [long]$p.ProcessorAffinity
$start = $p.StartTime
$tm = [Tq1bNative]::ThreadMasks($gamePid, $umask)
Emit @{
    event = 'set'; pid = $gamePid; fh_pid = $fhPid; mask = $Mask; before = $before; readback = $readback
    set_after_start_ms = [math]::Round(($tSet - $start).TotalMilliseconds, 1); found_after_pid_ms = [math]::Round($found_ms, 1)
    threads = $tm[0]; threads_read = $tm[1]; threads_outside = $tm[2]
    thread_or = ('0x{0:X}' -f $tm[3]); thread_and = ('0x{0:X}' -f $tm[4])
}
$polls = 0; $procBad = 0; $threadPollsBad = 0; $threadPollsUnread = 0; $maxThreads = 0; $minRead = [UInt64]::MaxValue
$orAll = [UInt64]0
$lastProc = $readback
while ($true) {
    [System.Threading.Thread]::Sleep($PollMs)
    try {
        $p.Refresh()
        if ($p.HasExited) { break }
        $a = [long]$p.ProcessorAffinity
    } catch { break }
    $tm = [Tq1bNative]::ThreadMasks($gamePid, $umask)
    if ($tm[0] -eq 0) { break }
    $polls++
    $lastProc = $a
    if ($a -ne $Mask) { $procBad++ }
    # A thread read outside the mask fails the run. A thread that could not be read at all is
    # counted apart: it exits between the snapshot and OpenThread (seen near game shutdown).
    if ($tm[2] -ne 0) { $threadPollsBad++ }
    if ($tm[1] -lt $tm[0]) { $threadPollsUnread++ }
    if ($tm[0] -gt $maxThreads) { $maxThreads = $tm[0] }
    if ($tm[1] -lt $minRead) { $minRead = $tm[1] }
    $orAll = $orAll -bor $tm[3]
}
Emit @{
    event = 'exit'; pid = $gamePid; polls = $polls; process_mask_mismatch_polls = $procBad
    thread_bad_polls = $threadPollsBad; thread_unreadable_polls = $threadPollsUnread
    max_threads = $maxThreads; last_process_mask = $lastProc
    min_threads_read = $(if ($polls) { $minRead } else { 0 }); thread_or_all = ('0x{0:X}' -f $orAll)
    exit_after_start_ms = [math]::Round(([DateTime]::Now - $start).TotalMilliseconds, 1)
}
