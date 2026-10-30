#!/usr/bin/env python3
"""T15 timing machinery and the one process-inspection module (test notes.md 5.2 to 5.6).

Ported from the planning spikes TQ1, TQ1b and TQ2 (spikes/TQ1-timing, TQ1b-timing, TQ2-benchmark at
an earlier prototype): their quiet-window protocol, process monitor, affinity watcher
driver and parsers, rewritten around tools/earth_test.py's job object and run records.

This is the only Python module in the repo that names the game's process image (the T16 launch scan
allows it here and in tools/affinity_watch.ps1): it lists, watches and pins game processes that
fh.py started. It never launches the game; every game run goes through the workspace's fh.py.

  - Job: a Windows job object with kill-on-close. Every fh.py launch is assigned to it while still
    suspended, so a hard-killed runner takes its whole process tree, the game included, with it.
  - quiet window: no game process alive and total CPU load under 25 percent over 2 s before each
    repetition (deferred and retried every 20 s until a deadline), the process table polled every
    0.25 s during the run, and no game process right after it.
  - affinity: tools/affinity_watch.ps1 pins the game to a mask (0xFFFF, the 16 LP proxy; 0xFF, the
    8 LP diagnostic) before "Loading map" and proves it held on the process and every thread.
  - parsers: the timer's force time, the block census, --benchmark-verbose columns, real-time tick
    intervals and server-save sizes.
"""
import ctypes
import json
import math
import os
import re
import statistics
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME_IMAGE = "factorio.exe"
WATCHER = HERE / "affinity_watch.ps1"
MASK16, MASK8 = 0xFFFF, 0xFF
LOAD_LIMIT, LOAD_WINDOW = 25.0, 2.0
RETRY_S = 20.0

# --------------------------------------------------------------------------------------- Win32

K32 = ctypes.WinDLL("kernel32", use_last_error=True)
NTDLL = ctypes.WinDLL("ntdll")
TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA, PROCESS_TERMINATE = 0x0100, 0x0001
INVALID_HANDLE = ctypes.c_void_p(-1).value
STILL_ACTIVE = 259
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
CREATE_SUSPENDED = 0x00000004


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                  "OtherOperationCount", "ReadTransferCount",
                                                  "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


K32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
K32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
K32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
K32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
K32.CloseHandle.argtypes = [wintypes.HANDLE]
K32.OpenProcess.restype = wintypes.HANDLE
K32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
K32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
K32.GetSystemTimes.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
K32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
K32.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                       ctypes.POINTER(ctypes.c_size_t)]
K32.CreateJobObjectW.restype = wintypes.HANDLE
K32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
K32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
K32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
K32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
K32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
NTDLL.NtResumeProcess.argtypes = [wintypes.HANDLE]
NTDLL.NtSuspendProcess.argtypes = [wintypes.HANDLE]
NTDLL.NtQuerySystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.ULONG,
                                           ctypes.POINTER(wintypes.ULONG)]
NTDLL.NtQuerySystemInformation.restype = ctypes.c_long
PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
PSAPI.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]


def _ft(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def processes():
    """[(pid, parent pid, image name)] of every process."""
    snap = K32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    out = []
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    ok = K32.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        out.append((pe.th32ProcessID, pe.th32ParentProcessID, pe.szExeFile))
        ok = K32.Process32NextW(snap, ctypes.byref(pe))
    K32.CloseHandle(snap)
    return out


def game_pids():
    return sorted(pid for pid, _, name in processes() if name.lower() == GAME_IMAGE)


# SystemProcessInformation on x64: each entry is a SYSTEM_PROCESS_INFORMATION (0x100 bytes: the
# thread count at 0x04, the pid at 0x50) followed by its SYSTEM_THREAD_INFORMATION records (0x50
# bytes each: ThreadState at 0x44, WaitReason at 0x48). A thread stopped by NtSuspendProcess or
# SuspendThread waits with reason Suspended.
SYSTEM_PROCESS_INFORMATION = 5
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
THREAD_STATE_WAITING, WAIT_REASON_SUSPENDED = 5, 5


def suspended_pids():
    """The pids of processes whose every thread is suspended: a fully suspended process executes
    nothing, so it cannot perturb a timed run (a build-ahead draft the run's governor parks while
    the workspace lock is held stays in the process table). An empty set when the query fails, so
    every process then counts as running (fail closed for the quiet window)."""
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        return set()
    size = 1 << 20
    for _ in range(8):
        buf = ctypes.create_string_buffer(size)
        need = wintypes.ULONG()
        st = NTDLL.NtQuerySystemInformation(SYSTEM_PROCESS_INFORMATION, buf, size, ctypes.byref(need))
        if (st & 0xFFFFFFFF) == STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, need.value + (1 << 16))
            continue
        if st != 0:
            return set()
        break
    else:
        return set()
    raw, out, off = buf.raw, set(), 0
    while True:
        nxt, nthreads = int.from_bytes(raw[off:off + 4], "little"), int.from_bytes(raw[off + 4:off + 8], "little")
        pid = int.from_bytes(raw[off + 0x50:off + 0x58], "little")
        states = []
        for i in range(nthreads):
            base = off + 0x100 + i * 0x50
            states.append((int.from_bytes(raw[base + 0x44:base + 0x48], "little"),
                           int.from_bytes(raw[base + 0x48:base + 0x4C], "little")))
        if pid and states and all(s == (THREAD_STATE_WAITING, WAIT_REASON_SUSPENDED) for s in states):
            out.add(pid)
        if not nxt:
            return out
        off += nxt


def tasklist_game():
    """The protocol's literal check: tasklist filtered on the game's image name, without the game
    processes that are wholly suspended (suspended_pids: they execute nothing). The quiet window and
    the check right after a timed run read it."""
    cp = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_IMAGE}", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True)
    rows = [l for l in cp.stdout.splitlines() if l.lower().startswith(f'"{GAME_IMAGE}"')]
    parked = suspended_pids()

    def pid_of(row):
        cells = row.split('","')
        return int(cells[1]) if len(cells) > 1 and cells[1].isdigit() else None
    return [r for r in rows if pid_of(r) not in parked]


def process_start_time(pid):
    """Creation time of a live process (100 ns units), or None when it is gone."""
    h = K32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return None
    try:
        code = wintypes.DWORD()
        if not K32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != STILL_ACTIVE:
            return None
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not K32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return None
        return _ft(c)
    finally:
        K32.CloseHandle(h)


def process_alive(pid, start_time=None):
    st = process_start_time(pid)
    if st is None:
        return False
    return start_time is None or st == start_time


def terminate_pid(pid):
    h = K32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
    if not h:
        return False
    try:
        return bool(K32.TerminateProcess(h, 1))
    finally:
        K32.CloseHandle(h)


def system_times():
    idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not K32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        raise OSError(ctypes.get_last_error(), "GetSystemTimes failed")
    return _ft(idle), _ft(kern), _ft(user)


def cpu_load(seconds=LOAD_WINDOW):
    """Total CPU load in percent of all logical processors over `seconds` (GetSystemTimes)."""
    a = system_times()
    time.sleep(seconds)
    b = system_times()
    idle = b[0] - a[0]
    total = (b[1] - a[1]) + (b[2] - a[2])
    return round(100.0 * (total - idle) / total, 1) if total else 0.0


# --------------------------------------------------------------------------------------- job object

class Job:
    """A kill-on-close job object: when the last handle closes (this process exits or is killed),
    Windows terminates every process in the job, the game processes fh.py started included."""

    def __init__(self):
        self.h = K32.CreateJobObjectW(None, None)
        if not self.h:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not K32.SetInformationJobObject(self.h, JobObjectExtendedLimitInformation, ctypes.byref(info),
                                           ctypes.sizeof(info)):
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        self.procs = []

    def popen(self, cmd, **kw):
        """Start a process suspended, put it in the job, then let it run, so not even its first
        child can escape the job."""
        flags = kw.pop("creationflags", 0) | CREATE_SUSPENDED
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        if not K32.AssignProcessToJobObject(self.h, int(p._handle)):
            err = ctypes.get_last_error()
            p.kill()
            raise OSError(err, "AssignProcessToJobObject failed")
        NTDLL.NtResumeProcess(int(p._handle))
        self.procs.append(p)
        return p

    def terminate(self):
        if self.h:
            K32.TerminateJobObject(self.h, 1)

    def close(self):
        if self.h:
            K32.CloseHandle(self.h)
            self.h = None


# --------------------------------------------------------------------------------------- monitor

class Monitor(threading.Thread):
    """Polls the process table every 0.25 s while a run is in flight (TQ1's monitor): a game
    process outside the run's tree is foreign; handles to our own game processes stay open so their
    affinity, CPU time and peak memory can be read until and after exit. A game process that is
    wholly suspended at a poll (suspended_pids) runs nothing then: it is recorded in `parked`, and it
    becomes foreign at the first poll that finds it running."""

    def __init__(self, root_pid, interval=0.25):
        super().__init__(daemon=True)
        self.root, self.interval = root_pid, interval
        self.halt = threading.Event()
        self.ours, self.foreign, self.max_games, self.polls = {}, set(), 0, 0
        self.parked = set()
        self.masks = []

    def run(self):
        while not self.halt.is_set():
            self.poll()
            self.halt.wait(self.interval)
        self.poll()

    def poll(self):
        try:
            procs = processes()
        except OSError:
            return
        parent = {pid: ppid for pid, ppid, _ in procs}
        parked = suspended_pids()
        every = [pid for pid, _, name in procs if name.lower() == GAME_IMAGE]
        games = [pid for pid in every if pid not in parked]
        self.parked.update(pid for pid in every if pid in parked)
        self.polls += 1
        self.max_games = max(self.max_games, len(games))
        for pid in games:
            if pid in self.ours or pid in self.foreign:
                continue
            p, mine = parent.get(pid), False
            for _ in range(12):
                if p is None or p == 0:
                    break
                if p == self.root:
                    mine = True
                    break
                p = parent.get(p)
            if mine:
                self.ours[pid] = K32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            else:
                self.foreign.add(pid)
        for pid, h in list(self.ours.items()):
            if not h:
                continue
            pm, sm = ctypes.c_size_t(), ctypes.c_size_t()
            if K32.GetProcessAffinityMask(h, ctypes.byref(pm), ctypes.byref(sm)):
                self.masks.append((int(time.time() * 1000), pid, pm.value))

    def peak_mb(self):
        out = []
        for pid, h in self.ours.items():
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            if h and PSAPI.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                out.append(round(pmc.PeakWorkingSetSize / 2 ** 20, 1))
        return max(out) if out else None

    def close(self):
        for h in self.ours.values():
            if h:
                K32.CloseHandle(h)


class Watcher:
    """tools/affinity_watch.ps1 as a separate process (TQ1b): READY, then the fh.py PID on stdin."""

    def __init__(self, out_file, mask, job=None):
        self.file = Path(out_file)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(WATCHER),
               "-OutFile", str(self.file), "-Mask", str(mask)]
        kw = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.p = job.popen(cmd, **kw) if job else subprocess.Popen(cmd, **kw)
        got = []
        t = threading.Thread(target=lambda: got.append(self.p.stdout.readline()), daemon=True)
        t.start()
        t.join(90)
        self.ready = bool(got) and got[0].strip() == "READY"

    def go(self, pid):
        self.p.stdin.write(f"{pid}\n")
        self.p.stdin.flush()

    def finish(self, timeout=120):
        try:
            _, err = self.p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.p.kill()
            _, err = self.p.communicate()
        text = self.file.read_text(encoding="utf-8") if self.file.exists() else ""
        recs = [json.loads(l) for l in text.splitlines() if l.strip()]
        return recs, (err or "")[-1500:], self.p.returncode


LOADING_RE = re.compile(r"^\s*([\d.]+) Loading map ", re.M)


def affinity_verdict(recs, mon, log_text, mask):
    """TQ1b's rule: the mask took before the save loaded and held on the process and every thread
    until exit, and the monitor's own reads after the set agree."""
    v = {"mask": mask, "reasons": []}
    sets = [r for r in recs if r.get("event") == "set"]
    exits = [r for r in recs if r.get("event") == "exit"]
    if len(sets) != 1 or len(exits) != 1:
        v["reasons"].append(f"watcher records: {len(sets)} set, {len(exits)} exit ({[r.get('event') for r in recs]})")
        return v
    s, e = sets[0], exits[0]
    m = LOADING_RE.search(log_text)
    v["loading_map_ms"] = round(1000 * float(m.group(1)), 1) if m else None
    v["set_after_start_ms"] = s["set_after_start_ms"]
    v["readback"] = s["readback"]
    if s["readback"] != mask:
        v["reasons"].append(f"readback {s['readback']} != mask {mask}")
    if s["threads_outside"] or s["threads_read"] < 1:
        v["reasons"].append(f"threads at set: {s['threads_read']}/{s['threads']} read, {s['threads_outside']} outside")
    if v["loading_map_ms"] is None or s["set_after_start_ms"] >= v["loading_map_ms"]:
        v["reasons"].append(f"mask set {s['set_after_start_ms']} ms after start, map load at {v['loading_map_ms']} ms")
    or_all = int(e["thread_or_all"], 16)
    if (e["polls"] < 1 or e["process_mask_mismatch_polls"] or e["thread_bad_polls"] or
            (e["last_process_mask"] != mask and e["last_process_mask"] != 0) or or_all & ~mask or not or_all):
        v["reasons"].append(f"did not hold: polls {e['polls']}, process mismatches {e['process_mask_mismatch_polls']}, "
                            f"thread polls outside {e['thread_bad_polls']}, thread OR {e['thread_or_all']}, "
                            f"last {e['last_process_mask']}")
    if sorted(mon.ours) != [s["pid"]]:
        v["reasons"].append(f"watcher pid {s['pid']} is not the monitor's game pid {sorted(mon.ours)}")
    after = [pm for t, pid, pm in mon.masks if t > s["unix_ms"] and pm != 0]
    v["monitor_reads_after_set"] = len(after)
    if not after or any(pm != mask for pm in after):
        v["reasons"].append(f"monitor read {sorted(set(after))} after the set ({len(after)} reads)")
    v["polls"], v["max_threads"] = e["polls"], e["max_threads"]
    return v


# --------------------------------------------------------------------------------------- quiet window

class QuietTimeout(RuntimeError):
    pass


def wait_quiet(deadline, log=None):
    """Return (tasklist rows, load) once no game process runs and CPU load is under the limit;
    retry every 20 s; raise QuietTimeout at the deadline (a self-recovering halt)."""
    while True:
        rows = tasklist_game()
        load = None if rows else cpu_load()
        if not rows and load is not None and load < LOAD_LIMIT:
            return rows, load
        if log:
            log({"kind": "deferred", "tasklist_rows": rows, "load_pre": load,
                 "reason": "game running" if rows else f"cpu load {load}% >= {LOAD_LIMIT}%"})
        if time.time() + RETRY_S > deadline:
            raise QuietTimeout("no quiet window before the deadline: " +
                               ("a game process is running" if rows else f"CPU load {load}%"))
        time.sleep(RETRY_S)


# --------------------------------------------------------------------------------------- parsers

def read(p):
    p = Path(p)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


DUR_RE = re.compile(r"(warm|request|force) Duration: ([\d.]+)ms")
CX_RE = re.compile(r"(Cliff|Entity|Tile) noise program processed (\d+) expressions \((\d+) unique\) "
                   r"and has (\d+) operations and (\d+) registers; estimated complexity: (\d+)\.")
RT_RE = re.compile(r"^(\d+) Duration: ([\d.]+)ms", re.M)
VERSION_RE = re.compile(r"Factorio (\d+\.\d+\.\d+) \(build (\d+), ([^)]*)\)")


def parse_complexity(stdout):
    """{program: {expressions, unique, operations, registers, complexity}} from --verbose lines."""
    out = {}
    for g in CX_RE.findall(stdout):
        out[g[0].lower()] = {"expressions": int(g[1]), "unique": int(g[2]), "operations": int(g[3]),
                             "registers": int(g[4]), "complexity": int(g[5])}
    return out


def parse_forced(run_dir, tag="tq1"):
    """The timer's force time (ms) and its block census from a scenario run directory."""
    so = Path(run_dir) / "script-output" / tag
    durs = dict((k, float(v)) for k, v in DUR_RE.findall(read(so / "gen.txt") + read(so / "warm.txt")))
    gen = read(so / "gen.json")
    return {"force_ms": durs.get("force"), "request_ms": durs.get("request"), "warm_ms": durs.get("warm"),
            "census": json.loads(gen) if gen else None}


def parse_verbose(text, extra=()):
    """--benchmark-verbose all: a header 'tick,timestamp,...' then one 't<i>,...' row per tick (ns).
    Keeps wholeUpdate, scriptUpdate and every mapGenerator* column, plus the named `extra` columns
    present in the header (PERF-09 reads pathFinder); `columns` lists the kept ones."""
    lines = text.splitlines()
    try:
        h = next(i for i, l in enumerate(lines) if l.startswith("tick,timestamp,"))
    except StopIteration:
        return None
    cols = lines[h].rstrip(",").split(",")
    idx = {c: i for i, c in enumerate(cols)}
    want = [c for c in cols if c in ("wholeUpdate", "scriptUpdate") or c.startswith("mapGenerator") or c in extra]
    out = {c: [] for c in want}
    out["tick"] = []
    for l in lines[h + 1:]:
        if not l.startswith("t") or "," not in l:
            continue
        f = l.rstrip(",").split(",")
        if len(f) < len(cols):
            continue
        out["tick"].append(int(f[0][1:]))
        for c in want:
            out[c].append(int(f[idx[c]]))
    out["columns"] = want
    return out


def pct(vals, q):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def window_stats(vb, lo, hi, columns_per=None):
    """Per-tick means, p99 and max in ms over ticks lo..hi for wholeUpdate, scriptUpdate and every
    mapGenerator* column; with columns_per, also each column's sum per that many requests."""
    sel = [i for i, t in enumerate(vb["tick"]) if lo <= t <= hi]
    if not sel:
        return None
    r = {"ticks": len(sel), "first": vb["tick"][sel[0]], "last": vb["tick"][sel[-1]], "columns": {}}
    for c in vb["columns"]:
        v = [vb[c][i] / 1e6 for i in sel]
        rec = {"mean": statistics.fmean(v), "p99": pct(v, 0.99), "max": max(v), "sum_ms": sum(v)}
        if columns_per:
            rec["per_step_ms"] = sum(v) / columns_per
        r["columns"][c] = rec
    gen = [c for c in vb["columns"] if c.startswith("mapGenerator") and c != "mapGenerator"]
    r["mapGenerator_sub_sum_ms"] = sum(r["columns"][c]["sum_ms"] for c in gen)
    return r


def interval_stats(iv):
    """Real-time tick intervals in ms (TQ2's rt.txt): P4 ticks over 20 ms, P5 p99, P6 longest."""
    if not iv:
        return None
    return {"ticks": len(iv), "mean": statistics.fmean(iv), "p50": pct(iv, 0.5), "p95": pct(iv, 0.95),
            "p99": pct(iv, 0.99), "max": max(iv), "over_20ms": sum(1 for x in iv if x > 20.0),
            "over_33ms": sum(1 for x in iv if x > 1000.0 / 30), "window_s": sum(iv) / 1000.0,
            "ups": len(iv) / (sum(iv) / 1000.0)}


def parse_rt(run_dir):
    text = read(Path(run_dir) / "script-output" / "tq2" / "rt.txt")
    pairs = [(int(t), float(ms)) for t, ms in RT_RE.findall(text)]
    return [t for t, _ in pairs], [ms for _, ms in pairs]


def median(v):
    return statistics.median(v) if v else None


def spread(v):
    return [min(v), max(v)] if v else None


def selftest():
    """Offline checks of the parsers and the job object (no game)."""
    checks = []
    so = ("   0.001 2026-10-27; Factorio 2.1.23 (build 87750, win64, steam)\n"
          "   0.5 Verbose CompiledMapGenSettings.cpp:429:   Tile noise program processed 1296 expressions (593 unique) "
          "and has 479 operations and 53 registers; estimated complexity: 10068.\n")
    cx = parse_complexity(so)
    checks.append(("complexity", cx.get("tile", {}).get("complexity") == 10068))
    checks.append(("version", VERSION_RE.search(so).groups()[:2] == ("2.1.23", "87750")))
    vb = parse_verbose("tick,timestamp,wholeUpdate,mapGenerator,mapGeneratorBasicTilesSupportCompute,scriptUpdate,\n"
                       "t0,1,2000000,1000000,500000,1000,\nt1,2,4000000,3000000,2500000,2000,\n")
    st = window_stats(vb, 0, 1)
    checks.append(("verbose", st["columns"]["mapGeneratorBasicTilesSupportCompute"]["sum_ms"] == 3.0))
    pf_text = "tick,timestamp,wholeUpdate,pathFinder,scriptUpdate,\nt0,1,2000000,700,1000,\nt1,2,4000000,300,2000,\n"
    pf = parse_verbose(pf_text, extra=("pathFinder",))
    checks.append(("verbose_extra", pf["pathFinder"] == [700, 300] and "pathFinder" not in parse_verbose(pf_text)))
    iv = interval_stats([16.6, 16.7, 25.0, 300.0])
    checks.append(("intervals", iv["over_20ms"] == 2 and iv["max"] == 300.0))
    j = Job()
    p = j.popen([sys.executable, "-c", "import time; time.sleep(30)"])
    # a wholly suspended process is parked, and running again once resumed (the census of the quiet
    # window and the monitor); this process itself is never parked
    h = K32.OpenProcess(0x0800, False, p.pid)
    was = p.pid in suspended_pids()
    NTDLL.NtSuspendProcess(h)
    parked = p.pid in suspended_pids()
    NTDLL.NtResumeProcess(h)
    after = p.pid in suspended_pids()
    K32.CloseHandle(h)
    checks.append(("suspended_census", not was and parked and not after and os.getpid() not in suspended_pids()))
    j.terminate()
    p.wait(10)
    checks.append(("job_terminates_children", p.returncode is not None))
    j.close()
    bad = [n for n, ok in checks if not ok]
    print(f"RESULT {'ok' if not bad else 'fail'} perf selftest checks={len(checks)} failed={len(bad)} {bad}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(selftest())
