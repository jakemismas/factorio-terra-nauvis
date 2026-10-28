#!/usr/bin/env python3
"""Safety rails every repo tool shares for design constraint 1 (project rules 1 and 2).

  live_output_problem(path, base)  why a tool must not write to `path` (any spelling but a plain,
                              fully qualified drive-letter path; the live profile by path or by file
                              identity; any folder named mods; a file with a second hard link, or a
                              folder holding one or a link into the profile), or None. A relative
                              path is judged where the tool will write it: joined to `base`, the
                              directory the tool resolves it against (the working directory when
                              omitted)
  absolute_output(path, base)  that absolute path
  refuse_live_outputs(ns, tool, base)  exit with a RESULT fail line when an output dest of an
                              argparse namespace (OUTPUT_ARGS) fails live_output_problem; otherwise
                              rewrite each one to its absolute path, so the tool writes, and hands
                              its subprocesses, exactly the path that was checked
  run_breach(out, result)     why a finished game run shows it may have left its instance, or None
  bracket_problem()           why this process is not inside an earth_test.py guard bracket, or None
  require_bracket(tool)       exit with a RESULT fail line unless bracket_problem() is None

The bracket: `tools/earth_test.py` takes the workspace lock and the chained G9 start snapshot,
then writes a fresh token into the lock record and hands it to its children as TN_BRACKET. A tool
that launches the game through fh.py (game_selftest.py, dump_render.py run, oracle.py probe, the
gate's kill probe) calls require_bracket first, so it refuses unless the canonical workspace lock
is held, with that token, by a live ancestor process whose guard entry is still open. A direct
run therefore stops before fh.py is ever called.

It reads only paths and process tables; it launches nothing and needs no game.
"""
import json
import os
import re
import stat
import sys
from pathlib import Path

DEFAULT_WS = r"%FACTORIO_WS%"
ENV = "TN_BRACKET"


def ws_root():
    # absolute, so a relative FACTORIO_WS cannot mean one folder here and another in a subprocess
    # that runs with the workspace as its working directory
    return Path(os.path.abspath(os.environ.get("FACTORIO_WS") or DEFAULT_WS))


def out_root(ws=None):
    return Path(ws or ws_root()) / "previews" / "earth-build"


def lock_path(ws=None):
    return out_root(ws) / "earth-test.lock"


def guard_root(ws=None):
    return out_root(ws) / "guard"


def _known_roaming():
    """The roaming application-data folder from the shell's known-folder API (not from an
    environment variable a caller could change), or None off Windows or on failure."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

        u = uuid.UUID("{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}")   # FOLDERID_RoamingAppData
        g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        out = ctypes.c_wchar_p()
        shell32, ole32 = ctypes.windll.shell32, ctypes.windll.ole32
        if shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value)
        finally:
            ole32.CoTaskMemFree(out)
    except (OSError, AttributeError, ValueError):
        return None


def live_profile_roots():
    """The live profile's possible homes: %APPDATA%\\Factorio, the known roaming folder's Factorio
    and the per-user default."""
    roots = []
    app = os.environ.get("APPDATA")
    if app:
        roots.append(Path(app) / "Factorio")
    known = _known_roaming()
    if known:
        roots.append(known / "Factorio")
    roots.append(Path.home() / "AppData" / "Roaming" / "Factorio")
    out = []
    for r in roots:
        try:
            r = r.resolve()
        except OSError:
            pass
        if r not in out:
            out.append(r)
    return out


def _inside(p, root):
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


PLAIN_DRIVE_RE = re.compile(r"^[A-Za-z]:$")
DRIVE_RELATIVE_RE = re.compile(r"^[A-Za-z]:(?!\\)")


def spelling_problem(path, base=None):
    """Why a path spelling is refused before any comparison, or None. Repo tools write only to
    plain drive-letter paths, fully qualified or relative to the tool's base folder. Refused, because
    the live profile's plain spelling would not match them:
      - an extended-length (\\\\?\\), device (\\\\.\\) or UNC spelling (an admin share such as
        \\\\localhost\\C$ reaches a local drive under another name);
      - anything starting with a single backslash: an NT-namespace spelling (\\??\\, \\GLOBAL??\\,
        \\Device\\), which Win32 hands straight to the object manager, so that resolve() returns a
        drive-relative 'C:Users\\...' and every comparison and link check would miss the target
        (\\??\\UNC\\localhost\\C$ reopens the admin share the same way), or a root-relative path;
      - a drive-relative spelling ('C:foo'), and any '?' or '*' or NUL character;
      - and anything that resolves to a path that is not fully qualified on a plain drive letter
        (a mapped network drive, a drive-relative result)."""
    s = os.fspath(path).replace("/", "\\")
    if "\0" in s:
        return f"{path!r} holds a NUL character"
    if s.startswith("\\\\"):
        return (f"{path} is an extended-length, device or UNC spelling: repo tools write only to plain "
                f"drive-letter paths")
    if s.startswith("\\"):
        return (f"{path} starts with a single backslash: an NT-namespace spelling (\\??\\, \\GLOBAL??\\, \\Device\\) "
                f"or a root-relative path; repo tools write only to plain drive-letter paths")
    if "?" in s or "*" in s:
        return f"{path} holds a '?' or '*' (a wildcard or a namespace spelling): no file name holds either"
    if DRIVE_RELATIVE_RE.match(s):
        return f"{path} is drive-relative (no backslash after the drive letter): name the folder in full"
    r = _resolved(absolute_output(s, base))
    if str(r).startswith("\\\\") or not PLAIN_DRIVE_RE.match(r.drive or "") or r.root != "\\":
        return (f"{path} resolves to {r}, which is not a fully qualified path on a plain drive letter (a network, "
                f"device or drive-relative path)")
    return None


def absolute_output(path, base=None):
    """The absolute path a tool writes for `path`: a relative one joined to `base` (the folder the
    tool resolves it against; the working directory when omitted), '..' folded as Win32 folds it."""
    p = Path(os.fspath(path))
    if p.is_absolute():
        return Path(os.path.abspath(p))
    return Path(os.path.abspath(Path(base) / p if base is not None else p))


def _nearest_existing(p):
    q = Path(p)
    while not q.exists():
        if q.parent == q:
            return None
        q = q.parent
    return q


def _segment(seg):
    """A path segment as Windows opens it: trailing dots and spaces dropped, a stream suffix cut."""
    return seg.split(":")[0].rstrip(". ").lower()


def _resolved(p):
    try:
        return Path(p).resolve()
    except (OSError, ValueError):
        return Path(p).absolute()


def _profile_problem(path, r, roots):
    """Why the resolved path `r` lies in the live profile, by path or by the file identity of its
    nearest existing ancestor (so a junction, a subst drive or a short name cannot hide it)."""
    for root in roots:
        if _inside(r, root) or str(r).lower().startswith(str(root).lower()):
            return f"{path} is inside the live profile {root} (hard rule 2: nothing writes there)"
    anc = _nearest_existing(r)
    if anc is not None:
        for a in [anc] + list(anc.parents):
            for root in roots:
                try:
                    if root.exists() and os.path.samefile(a, root):
                        return f"{path} is inside the live profile {root} through {a} (hard rule 2: nothing writes there)"
                except OSError:
                    continue
    return None


def _links(p):
    """The hard-link count of a regular file (1 for anything else or anything unreadable)."""
    try:
        st = os.stat(p)
    except (OSError, ValueError):
        return 1
    return st.st_nlink if stat.S_ISREG(st.st_mode) else 1


def _is_link(p):
    try:
        return os.path.islink(p) or bool(getattr(os.path, "isjunction", lambda _: False)(p))
    except OSError:
        return False


def link_problem(path, r, roots):
    """Why writing at the existing path `r` would reach another file: a regular file with a second
    hard link (a write through it changes every name's file, and one may sit in the live profile;
    the nearest-ancestor comparison sees only this name), or a folder that directly holds such a
    file or a symbolic link or junction into the live profile (a tool that rewrites a file there
    writes through it). Folders are read one level deep: the tools write their files directly into
    the folders they are given."""
    if not r.exists():
        return None
    n = _links(r)
    if n > 1:
        return (f"{path} is a file with {n} hard links: a write through it changes the other names' file too, "
                f"which may sit in the live profile")
    if r.is_dir():
        try:
            children = list(os.scandir(r))
        except OSError:
            children = []
        for e in children:
            if _is_link(e.path):
                why = _profile_problem(f"{path} holds {e.name}, a link that", _resolved(e.path), roots)
                if why:
                    return why
            elif e.is_file(follow_symlinks=False) and _links(e.path) > 1:
                return (f"{path} holds {e.name}, a file with {_links(e.path)} hard links: rewriting it would change "
                        f"the other names' file too, which may sit in the live profile")
    return None


def live_output_problem(path, base=None):
    """A message when a tool must not write to `path`, else None: any spelling but a plain,
    fully qualified or relative, drive-letter path (spelling_problem); anything inside the live
    profile, compared by resolved path and by file identity of its nearest existing ancestor (so a
    junction, a subst drive or a short name cannot hide it); a file with a second hard link, or a
    folder holding one or a link into the live profile (link_problem); and any folder with a path
    segment named mods (a game mods folder; test mods live in tools/mods/ and are read, never
    written). A relative path is judged at absolute_output(path, base), where the tool writes it."""
    why = spelling_problem(path, base)
    if why:
        return why
    p = Path(os.fspath(path))
    full = absolute_output(p, base)
    r = _resolved(full)
    roots = live_profile_roots()
    why = _profile_problem(path, r, roots) or link_problem(path, r, roots)
    if why:
        return why
    if any(_segment(seg) == "mods" for seg in list(r.parts) + list(full.parts) + list(p.parts)):
        return f"{path} has a path segment named mods: nothing in the repo installs into a mods folder"
    return None


# Every argparse dest of every tool under tools/ is declared in exactly one of these three sets; the
# T16 output_args row fails on an undeclared dest, and on a tool that declares an output dest but
# never calls refuse_live_outputs (design constraint 1: no tool writes the live profile).
# Dests naming a file or folder a tool writes:
OUTPUT_ARGS = {"out", "out_dir", "out_root", "out_json", "png", "png_out", "json_out", "overlay", "sbs",
               "candidate_out", "dest", "github_env"}
# Dests naming a file or folder a tool only reads:
READ_ARGS = {"mod_dir", "frozen", "ref_land", "ref_thin", "candidate", "preview", "water_colours_from",
             "map_gen_settings", "dump", "src", "oracle_dir", "sample", "probe", "expressions", "runs"}
# Dests holding values, never paths:
VALUE_ARGS = {"release", "check_tag", "map", "wr", "hr", "window", "cand_origin", "preview_offset", "scale",
              "origin", "panel_px", "instance", "modset", "seed", "areas", "points", "names", "types",
              "no_decoratives", "scene", "lattice", "gen_tick", "tick", "label", "grid", "grid_name",
              "grid_threshold", "grid_op", "area", "tiles_only", "no_legend", "through", "cold", "slice", "only",
              "reason", "maps", "no_simulation", "a", "b", "to_border", "width", "kmax", "wmax", "block", "live",
              "place", "lonlat", "expr", "context", "cap", "conn", "name", "threshold", "land_when", "shift",
              "replay"}


def refuse_live_outputs(ns, tool, base=None):
    """Exit with a RESULT fail line when any output argument of an argparse namespace points into
    the live profile or a mods folder (design constraint 1: nothing writes the live profile).
    `base` is the folder the tool resolves a relative output against (the working directory when
    omitted). Every output argument that passes is rewritten in `ns` to its absolute path, so the
    path the tool writes, and the one it hands a subprocess running in another folder, is the
    path that was checked."""
    for k, v in sorted(vars(ns).items()):
        if k in OUTPUT_ARGS and v:
            many = isinstance(v, (list, tuple))
            done = []
            for one in (v if many else [v]):
                why = live_output_problem(one, base)
                if why:
                    print(f"RESULT fail {tool} refuses --{k.replace('_', '-')}: {why}", flush=True)
                    sys.exit(1)
                done.append(str(absolute_output(one, base)))
            setattr(ns, k, done if many else done[0])


def run_breach(out_dir=None, result=""):
    """Why a finished game run shows it may have left its instance, or None (design constraint 1):
    its RESULT line reads fail-NOT-ISOLATED, isolated=NO or isolated=unknown, or a run.json under
    its --out (the run's own, or a scenario's create or bench step) records isolated as anything
    but true (fh.py: the game named a write-data path other than its instance's, or none), or a
    scenario step that is not isolated. A launch fh.py refused writes no run.json and is no breach.
    Every caller stops all further game runs on a breach: a run that used another write-data,
    likely the live profile, would only repeat its writes."""
    res = result or ""
    for word in ("fail-NOT-ISOLATED", "isolated=NO", "isolated=unknown"):
        if word in res:
            return f"its RESULT line reads {word}: {res.strip()[:240]}"
    if out_dir is None:
        return None
    d = Path(out_dir)
    for rj in (d / "run.json", d / "create" / "run.json", d / "bench" / "run.json"):
        if not rj.is_file():
            continue
        try:
            meta = json.loads(rj.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return f"{rj} is unreadable ({e}), so the run's isolation is unproven"
        if not isinstance(meta, dict) or meta.get("isolated") is not True:
            seen = meta.get("write_data_seen") if isinstance(meta, dict) else None
            return (f"{rj} records isolated={meta.get('isolated') if isinstance(meta, dict) else None} "
                    f"(write data seen: {seen})")
        for sub in ("create", "bench"):
            if isinstance(meta.get(sub), dict) and meta[sub].get("isolated") is False:
                return f"{rj} records its {sub} step as not isolated (write data seen: {meta[sub].get('write_data_seen')})"
    return None


def _ancestors(pid=None):
    """The parent chain of this process (pids), from its parent upwards."""
    import perf
    parent = {p: pp for p, pp, _ in perf.processes()}
    out, q = [], parent.get(pid or os.getpid())
    while q and q not in out and len(out) < 32:
        out.append(q)
        q = parent.get(q)
    return out


def bracket_problem():
    raw = os.environ.get(ENV)
    if not raw:
        return (f"no {ENV}: this tool launches the game only inside tools/earth_test.py's guard bracket "
                f"(workspace lock plus the chained G9 guard); run it through 'earth_test.py suite <slice>'")
    try:
        b = json.loads(raw)
        lock, chain, start, token, pid = Path(b["lock"]), Path(b["chain"]), b["start"], b["token"], int(b["pid"])
    except (ValueError, KeyError, TypeError):
        return f"{ENV} is malformed"
    try:
        if lock.resolve() != lock_path().resolve():
            return f"{ENV} names {lock}, not the workspace lock {lock_path()}"
        if guard_root().resolve() not in chain.resolve().parents:
            return f"{ENV} names the chain {chain}, outside the workspace guard {guard_root()}"
    except OSError as e:
        return f"{ENV} paths do not resolve: {e}"
    try:
        rec = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"the workspace lock {lock} is unreadable"
    if rec.get("token") != token or rec.get("pid") != pid:
        return "the workspace lock is not held by this bracket (token or owner differs)"
    import perf
    if not perf.process_alive(pid, rec.get("start_time")):
        return f"the bracket's owner pid {pid} is gone"
    if pid != os.getpid() and pid not in _ancestors():
        return f"the bracket's owner pid {pid} is not an ancestor of this process"
    try:
        entries = json.loads(chain.read_text(encoding="utf-8"))["entries"]
    except (OSError, ValueError, KeyError):
        return f"the guard chain {chain} is unreadable"
    last = entries[-1] if entries else {}
    if last.get("start") != start or last.get("token") != token or last.get("ended"):
        return "the guard chain's last entry is not this bracket's open entry"
    return None


def require_bracket(tool):
    why = bracket_problem()
    if why:
        print(f"RESULT fail {tool} refuses to launch the game: {why}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    print("RESULT " + ("ok inside a guard bracket" if bracket_problem() is None else f"fail {bracket_problem()}"))
