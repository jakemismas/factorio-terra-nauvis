#!/usr/bin/env python3
"""The Terra Nauvis gate runner (the design notes section 5; test notes.md section 1).

  python tools/earth_test.py gate --through <milestone> [--cold]   every milestone's testCommand, under 10 min
  python tools/earth_test.py suite <milestone> [--only <check>]     the milestone suite: raw runs and a manifest
  python tools/earth_test.py install-check                      every milestone's installCheck
  python tools/earth_test.py baseline                           rewrite the measured values in tests/
  python tools/earth_test.py static                             T16 static rows: no game, no workspace
  python tools/earth_test.py freeze                             register new Earth bodies (europe-coast on)
  python tools/earth_test.py guard-rebaseline --reason <text>   A manual re-baseline of the G9 chain:
                                                                interactive terminal only, never unattended

Rules this file implements (design section 5):
  1. Guard, lock, budget. Every command that launches the game sits in a chained live-profile guard
     bracket (fh.py guard snapshot first, fh.py guard check last; within a part each start
     snapshot must equal the previous command's end snapshot, the part's first command
     re-baselines, and a build instance's game log newer than the chain's last clean end fails
     the start), holds the workspace lock (a lock whose owner process is gone is free), reads
     the game build from its first real run (G8) and, for the gate, stops itself at 9 minutes.
     A dirty guard stops every game run until the maintainer clears it by hand (GUARD_STOP).
     Every fh.py launch runs in a kill-on-close job object, so a killed runner leaves no game
     process behind.
  2. No trusted verdict files. Every check's key is a sha256 recomputed over its inputs; cached
     raw outputs are re-validated (G1 on every run.json, a run newer than its inputs, images
     re-hashed) and the verdict re-derived with the committed checker. A stale FG row re-runs live;
     stale suite evidence fails at once and names the exact `suite <milestone> --only <check>` command.
  3. A rotating live sample: one suite check and one timed row are re-executed by every gate.
  4. Equality only where deterministic; timed ratios against the plan's section 6 only.

It runs the game only through %FACTORIO_WS%\\tools\\fh.py, finds the harness through FACTORIO_WS
(default %FACTORIO_WS%) and refuses a game-launching command without
it. It never writes a tracked file while gating; `baseline` and `suite` write tests/ as the plan's
builder order requires (final code change, then baseline, then suite last).
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_zip  # noqa: E402
import tn_static  # noqa: E402
import tnconfig  # noqa: E402
import tnguard  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
PLAN = REPO / "SPRINT-1-PLAN.md"
TESTS = REPO / "tests"
BUDGETS = TESTS / "budgets.json"
BASELINES = TESTS / "baselines"
SUITES = BASELINES / "suites"
DEFAULT_WS = r"%FACTORIO_WS%"
GAME_VERSION, GAME_BUILD = "2.1.23", "87750"
GATE_BUDGET_S = 9 * 60
SEED = 1000
SEEDS = (1000, 1002, 1004)
S8_COUNTS = {"t1_metrics": 62, "oracle": 760, "dump_render": 10, "contact_sheet": 4, "nav": 10}
GST_TESTS = 31
VANILLA = {"tile": 10068, "entity": 8549, "cliff": 287}
TWIN_CONSTANT = "8"                       # S9's constant coast
T15B = {"block": "64:32:-64:-48", "reps_gate": 5, "reps_suite": 7, "reps_extra": 7, "threads": 8, "ticks": 10}
# Rule 5: a timed ratio within this of a limit gets one more group of reps_extra reps per config,
# decided on the pooled reps (test notes 5.4); in the gate only if the group fits the budget.
BORDERLINE = 0.03
WALK = {"x0": 2048, "y0": -2048, "dx": 64, "dy": 0, "R": 3, "P": 60, "N": 60, "D": 240, "T0": 60}
EXPLORE = {"cx0": 188, "cy": -14, "R": 5, "K": 60, "P": 32, "D": 240, "T0": 60}
SAVE_BLOCK = (64, 32)
SERVER = {"port": 34497, "rt_timeout": 75, "save_timeout": 40}
PERF15_KEEP = "mapGeneratorBasicTilesSupportCompute"
# The commands that build a Ctx: each is a fixed path segment of the output root.
COMMANDS = ("gate", "suite", "install-check", "baseline", "freeze", "guard-rebaseline")


class GateError(RuntimeError):
    pass


class BudgetExceeded(GateError):
    pass


class FatalRun(BaseException):
    """A game run that may have left its instance (run.json isolated not true, a NOT-ISOLATED
    RESULT) or ran on another build (G8): every further game run of the command stops at once.
    It derives from BaseException, so no row's or group loop's `except GateError` or `except
    Exception` swallows it; only with_bracket catches it, after which the job is terminated and
    the guard check runs (design constraint 1, project rule 2)."""


# ------------------------------------------------------------------------------------------------ milestones

# The runner's milestone registry (design note 2): per milestone its part, its fast-gate rows (FG),
# its suite checks (SS), which suite checks are deterministic or timed (rule 3's live sample), the
# oracle properties it ships, and the dumps whose Earth bodies the frozen row and freeze read
# (M1 here; climate-tiles adds M2). Each later milestone appends its entry.
REGISTRY = [
    {"id": "toolchain", "part": 1, "order": 0,
     "fg": ["static", "fh_flags", "plan_main", "section6", "data_src", "offline_selftests", "runner_controls",
            "dumps", "frozen", "t13_dump_facts", "isolation_b", "ab_placeholder", "t13_zero_cost",
            "t13_placeholder", "t13_scenario", "t15a_rows", "isolation_a"],
     "ss": ["gst", "t15b_m0", "walker_m0", "perf15", "rt_m0", "save_m0"],
     "deterministic_ss": ["gst"],
     "timed_ss": ["t15b_m0"],
     "oracle_properties": [],
     "dumps": ["m1"]},
]


def registry_upto(slice_id):
    ids = [s["id"] for s in REGISTRY]
    if slice_id not in ids:
        raise GateError(f"unknown slice {slice_id!r}; the runner's registry holds {ids}")
    return REGISTRY[: ids.index(slice_id) + 1]


def current_slice():
    return REGISTRY[-1]


def slice_entry(slice_id):
    for s in REGISTRY:
        if s["id"] == slice_id:
            return s
    raise GateError(f"unknown slice {slice_id!r}; the runner's registry holds {[s['id'] for s in REGISTRY]}")


def checked_slice(slice_id):
    """A milestone id the runner may join into a path: it must fullmatch SLICE_ID and name a registry
    entry. Every command validates its milestone id with this before it builds any path (Ctx joins
    the id into its output directory), so a crafted id never reaches the file system."""
    if not isinstance(slice_id, str) or not re.fullmatch(SLICE_ID, slice_id):
        raise GateError(f"{slice_id!r} is not a slice id (lower-case words joined by single hyphens)")
    registry_upto(slice_id)
    return slice_id


# ------------------------------------------------------------------------------------------------ hashing

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tree_digest(paths, root=REPO, exclude=()):
    """sha256 over (relative path, bytes) of every file under the given paths; also the newest mtime."""
    h = hashlib.sha256()
    newest = 0.0
    files = []
    for base in paths:
        base = Path(base)
        if base.is_file():
            files.append(base)
        elif base.is_dir():
            files += [p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for p in sorted(set(files)):
        r = p.resolve().relative_to(Path(root).resolve()).as_posix() if str(p).startswith(str(root)) else p.as_posix()
        if any(r.startswith(e) for e in exclude):
            continue
        h.update(r.encode() + b"\0" + p.read_bytes() + b"\0")
        newest = max(newest, p.stat().st_mtime)
    return h.hexdigest(), newest


def key_of(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def write_atomic(path, text):
    """Write a state or tracked file through a temp file and os.replace, so a kill mid-write never
    leaves a truncated file (chain.json, the cache index, suite manifests, baselines, frozen.json)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------ plan

def git_show(ref_path):
    cp = subprocess.run(["git", "show", ref_path], cwd=str(REPO), capture_output=True)
    if cp.returncode != 0:
        return None
    return cp.stdout.decode("utf-8")


def plan_matches_main(work_text, main_text):
    """Rule 3 of section 6: the working tree's plan must equal main's byte for byte (LF)."""
    if main_text is None:
        return ["git show main:SPRINT-1-PLAN.md failed: no local main branch"]
    if work_text.replace("\r\n", "\n") != main_text.replace("\r\n", "\n"):
        return ["the working tree's SPRINT-1-PLAN.md differs from main's copy (no slice moves its own bar)"]
    return []


def plan_slice_order(text):
    """Milestone ids in build order, from the plan's section 20 part JSON blocks."""
    ids = []
    for block in re.findall(r"```json\n(.*?)```", text, re.S):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        for s in sorted(d.get("slices", []), key=lambda s: s.get("order", 0)):
            if s.get("id") and s["id"] not in ids:
                ids.append(s["id"])
    return ids


def _table(text, heading):
    i = text.find(heading)
    if i < 0:
        raise GateError(f"the plan has no section {heading!r}")
    rows = []
    for line in text[i:].split("\n")[1:]:
        if line.startswith("#"):
            break
        if line.startswith("|") and not re.match(r"^\|\s*-", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


NUM = r"[+-]?\d[\d,]*(?:\.\d+)?"
SLICE_ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"


def _num(s):
    return float(s.replace(",", ""))


def _split_top(text, sep=";"):
    """Split on sep outside parentheses (a note may hold the separator)."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return out


def _strip_note(seg):
    """('body', 'note') for 'body (note)', else (seg, None)."""
    m = re.fullmatch(r"(.*?)\s*\(([^()]*)\)", seg.strip(), re.S)
    return (m.group(1).strip(), m.group(2).strip()) if m else (seg.strip(), None)


def _same_rule(m, earlier, cell):
    p1 = (earlier or {}).get("P1", {}).get("limit", {})
    if p1.get("tbd"):
        return {"tbd": True}   # it reads P1's rule, which is TBD-P4 itself: fails where it is in force
    if "relative_factor" not in p1:
        raise GateError(f"limit cell {cell!r} names the same relative rule, but P1 holds none")
    return {"max": _num(m.group(1)), "relative_factor": p1["relative_factor"], "relative_rule": "P1"}


def parse_limit(cell, earlier=None):
    """The value a 6.2 Limit cell holds, as a dict; {"tbd": True} for a TBD-P4 cell (it fails only a
    gate that enforces it). Any other text the gate cannot read raises GateError (fail closed).
    `earlier` holds the rows parsed so far, for "the same relative rule"."""
    c = cell.strip()
    if "TBD-P4" in c:
        return {"tbd": True}
    out = {}
    segs = _split_top(c)
    if len(segs) == 3 and all(re.fullmatch(NUM, s) for s in segs):
        return {"per_map_values": [_num(s) for s in segs]}
    patterns = (
        (rf"({NUM}) to ({NUM})", lambda m: {"min": _num(m.group(1)), "max": _num(m.group(2))}),
        (rf"({NUM})", lambda m: {"max": _num(m.group(1))}),
        (rf"({NUM}) ms", lambda m: {"max_ms": _num(m.group(1))}),
        (rf"({NUM}), and at most \(main's recorded ratio \+ the slice's time allocation\) x ({NUM})",
         lambda m: {"max": _num(m.group(1)), "relative_factor": _num(m.group(2))}),
        (rf"({NUM}), and the same relative rule", lambda m: _same_rule(m, earlier, cell)),
        (rf"at most ({NUM}) per .+", lambda m: {"max": _num(m.group(1))}),
        (rf"({NUM}) ms on (M\d)", lambda m: {f"{m.group(2)}_ms": _num(m.group(1))}),
        (rf"\+({NUM}) ms per tick", lambda m: {"delta_ms": _num(m.group(1))}),
        (rf"({NUM}), failing only when .+", lambda m: {"max": _num(m.group(1)), "overlap_rule": True}),
        (r"(P\d+) to (P\d+)", lambda m: {"same_as": [m.group(1), m.group(2)]}),
        (rf"`([A-Za-z]+)`(?: (p99|mean))? ({NUM})",
         lambda m: {"columns": {m.group(1): {"stat": m.group(2), "max": _num(m.group(3))}}}),
    )
    for seg in segs:
        body, _note = _strip_note(seg)
        for pat, fn in patterns:
            m = re.fullmatch(pat, body)
            if not m:
                continue
            for k, v in fn(m).items():
                if k == "columns":
                    out.setdefault("columns", {}).update(v)
                elif k in out:
                    raise GateError(f"limit cell {cell!r} sets {k} twice")
                else:
                    out[k] = v
            break
        else:
            raise GateError(f"unparseable limit cell {cell!r}")
    return out


def _measure_scope(measure, mapnames):
    """What a 6.2 Measure cell says about T15a: {program, modset, maps} for a complexity row."""
    m = re.match(r"^(Tile|Entity|Cliff) complexity per world(?:, (M\d))?(?:[:,]|$)", measure)
    if not m:
        return None
    maps = None
    if ":" in measure:
        maps = []
        for d in [x.strip() for x in measure.split(":", 1)[1].split(",")]:
            if d not in mapnames:
                raise GateError(f"measure {measure!r} names {d!r}, which is not a config.lua map")
            maps.append(mapnames[d])
    return {"program": m.group(1).lower(), "modset": m.group(2), "maps": maps}


def _alloc_value(text, modset, maps, variant, cell):
    v = text.strip()
    rule = {"modset": modset, "maps": list(maps), "variant": variant}
    if v in ("cap", "first", "none"):
        return dict(rule, kind=v)
    m = re.fullmatch(rf"\+?({NUM})", v)
    if m:
        return dict(rule, kind="add", value=_num(m.group(1)))
    m = re.fullmatch(rf"\+({NUM}) more", v)
    if m:
        return dict(rule, kind="add_more", value=_num(m.group(1)))
    m = re.fullmatch(r"(P\d+) minus the map's coast, base and the later reserves here", v)
    if m:
        return dict(rule, kind="headroom", limit=m.group(1))
    raise GateError(f"unparseable allocation cell {cell!r} (at {v!r})")


def parse_alloc(cell, mapnames):
    """A 6.3 cell as rules: each {modset (None: M1, and M2 takes the same numbers), maps, variant,
    kind (add, add_more, cap, first, none, headroom), value or limit}. mapnames: {display: key}.
    {"tbd": True} for a TBD-P4 cell; GateError for text the gate cannot read."""
    c = cell.strip()
    if "TBD-P4" in c:
        return {"cell": cell, "tbd": True, "rules": []}
    keys = list(mapnames.values())
    names_re = "|".join(re.escape(d) for d in mapnames)
    rules = []
    for seg in _split_top(c):
        if not seg:
            raise GateError(f"unparseable allocation cell {cell!r} (empty segment)")
        body, note = _strip_note(seg)
        modset, variant = None, None
        if note:
            m = re.fullmatch(r"(M\d)(?:, (key on|key off))?", note)
            if m:
                modset, variant = m.group(1), m.group(2)
        m = re.match(r"^(M\d|P[12])(?: (key on|key off))? (.+)$", body)
        if m:
            modset = {"P1": "M1", "P2": "M2"}.get(m.group(1), m.group(1))
            variant = m.group(2) or variant
            body = m.group(3)
        body = re.sub(r"^[a-z][a-z ]*:\s*", "", body)
        per = re.fullmatch(rf"(?:[a-z][a-z ]* )?((?:{names_re}) \+{NUM}(?:, (?:{names_re}) \+{NUM})*)", body)
        if per:
            for d, v in re.findall(rf"({names_re}) \+({NUM})", per.group(1)):
                rules.append({"modset": modset, "maps": [mapnames[d]], "variant": variant, "kind": "add",
                              "value": _num(v)})
            continue
        if re.search(rf" on (the new maps|{names_re})(,|$)", body):
            parsed = []
            for it in [x.strip() for x in body.split(",")]:
                m = re.fullmatch(rf"(.+?) on (the new maps|{names_re})", it)
                if not m:
                    raise GateError(f"unparseable allocation cell {cell!r} (at {it!r})")
                parsed.append((m.group(1), m.group(2)))
            named = {mapnames[sc] for _, sc in parsed if sc in mapnames}
            for val, sc in parsed:
                # "the new maps": every map the cell does not name; with none named, all but the first
                maps = [mapnames[sc]] if sc in mapnames else ([k for k in keys if k not in named] if named
                                                              else keys[1:])
                rules.append(_alloc_value(val, modset, maps, variant, cell))
            continue
        rules.append(_alloc_value(body, modset, keys, variant, cell))
    return {"cell": cell, "rules": rules}


def alloc_for(alloc, modset, map_key, variant=None):
    """The allocation a 6.3 cell gives one row: {"kind": "add", "value": v} or a cap, first, none
    or headroom rule. Rules for the row's modset win; with none, the unscoped rules apply (M2 rows
    take M1's numbers); adds at that level sum; a cell naming nothing for the row gives 0."""
    if alloc.get("tbd"):
        raise GateError(f"TBD-P4 in an enforced allocation: {alloc['cell']!r}")

    def sel(ms):
        return [r for r in alloc["rules"] if r["modset"] == ms and map_key in r["maps"]
                and r["variant"] in (None, variant)]
    level = sel(modset) or sel(None)
    if not level:
        return {"kind": "add", "value": 0.0}
    special = [r for r in level if r["kind"] in ("cap", "first", "none", "headroom")]
    if special:
        if len(level) != 1:
            raise GateError(f"allocation cell {alloc['cell']!r} is ambiguous for {modset} {map_key}")
        return dict(special[0])
    total = 0.0
    for r in level:
        if r["kind"] == "add":
            total += r["value"]
        else:  # add_more: the M1 value of the map plus this
            base = alloc_for(alloc, "M1", map_key, None)
            if base["kind"] != "add":
                raise GateError(f"allocation cell {alloc['cell']!r}: 'more' over a {base['kind']} M1 value")
            total += base["value"] + r["value"]
    return {"kind": "add", "value": total}


def headroom_limit(sec6, slice_id, prog, modset, map_key, limit_id):
    """'P10 minus the map's coast, base and the later reserves here': the limit minus every later
    milestone's add allocation for the row's program, modset and map (the map's coast and base are in
    the row itself)."""
    lim = (sec6["all_limits"].get(limit_id) or {}).get("limit") or {}
    if "max" not in lim:
        raise GateError(f"{slice_id}'s {prog} allocation names {limit_id}, which holds no single limit")
    order = sec6["order"]
    reserve = 0.0
    for later in order[order.index(slice_id) + 1:]:
        a = alloc_for(sec6["all_allocations"][later][prog], modset, map_key)
        if a["kind"] == "add":
            reserve += a["value"]
    return lim["max"] - reserve


def parse_section6(text, through, mapnames=None):
    """Every 6.2 and 6.3 cell of the plan (fail closed on text the gate cannot read), then the rows
    in force through `through`: the 6.2 rows whose From names a milestone at or before it and the 6.3
    rows of those milestones. A 6.2 From cell that names no milestone (P3: "milestone and release suites") is
    in force from the first section 20 milestone, so every suite that records its measure enforces
    it; no bar is parsed and enforced by none. A TBD-P4 cell fails only when it is in force. The
    'every other milestone' row applies to each section 20 milestone without a row of its own."""
    if mapnames is None:
        mapnames = tnconfig.map_by_display(tnconfig.load())
    order = plan_slice_order(text)
    if through not in order:
        raise GateError(f"slice {through!r} is not in the plan's section 20")
    upto = set(order[: order.index(through) + 1])
    all_limits, unassigned = {}, []
    for row in _table(text, "### 6.2 Performance limits"):
        if len(row) < 5 or not re.fullmatch(r"P\d+", row[0]):
            continue
        ids = re.findall(rf"`({SLICE_ID})`", row[3])
        for i in ids:
            if i not in order:
                raise GateError(f"6.2 row {row[0]} names {i!r}, which is not a section 20 slice")
        if not ids and not row[3].strip():
            raise GateError(f"6.2 row {row[0]} has an empty From cell")
        rec = {"measure": row[1], "from": ids[0] if ids else order[0], "from_cell": row[3], "from_ids": ids,
               "cell": row[2], "limit": parse_limit(row[2], all_limits),
               "complexity": _measure_scope(row[1], mapnames)}
        cx = rec["complexity"]
        if "per_map_values" in rec["limit"]:
            vals = rec["limit"].pop("per_map_values")
            if not cx or not cx["maps"] or len(cx["maps"]) != len(vals):
                raise GateError(f"6.2 row {row[0]}: {len(vals)} per-map values for maps {cx and cx['maps']}")
            rec["limit"]["per_map"] = dict(zip(cx["maps"], vals))
        all_limits[row[0]] = rec
        if not ids:
            unassigned.append(row[0])
    limits = {}
    for pid, rec in all_limits.items():
        if rec["from"] in upto:
            if rec["limit"].get("tbd"):
                raise GateError(f"TBD-P4 in an enforced limit: {pid} {rec['cell']!r}")
            limits[pid] = rec
    all_allocs, other = {}, None
    for row in _table(text, "### 6.3 Allocations"):
        if len(row) < 6 or row[0] == "Slice":
            continue
        cells = {"tile": row[1], "entity": row[2], "cliff": row[3], "time": row[4]}
        m = re.fullmatch(rf"`({SLICE_ID})`", row[0])
        if m:
            if m.group(1) not in order:
                raise GateError(f"6.3 row {row[0]} is not a section 20 slice")
            if m.group(1) in all_allocs:
                raise GateError(f"6.3 has two rows for {m.group(1)}")
            all_allocs[m.group(1)] = {k: parse_alloc(v, mapnames) for k, v in cells.items()}
        elif row[0] == "every other slice":
            other = {k: parse_alloc(v, mapnames) for k, v in cells.items()}
        else:
            raise GateError(f"6.3 row {row[0]!r} names no slice")
    for sid in order:
        if sid not in all_allocs:
            if other is None:
                raise GateError(f"section 6.3 has no row for {sid!r} and no 'every other slice' row")
            all_allocs[sid] = other
    allocs = {}
    for sid in order:
        if sid in upto:
            for prog, a in all_allocs[sid].items():
                if a.get("tbd"):
                    raise GateError(f"TBD-P4 in an enforced allocation: {sid} {prog} {a['cell']!r}")
            allocs[sid] = all_allocs[sid]
    return {"limits": limits, "allocations": allocs, "all_limits": all_limits, "all_allocations": all_allocs,
            "order": order, "from_first_slice": unassigned}


# Which check of this runner enforces each 6.2 row once it is in force. The section6 row fails when
# a row in force through --through has no consumer here, so no bar is ever parsed and enforced by
# none (fail closed); each milestone that brings a row into force adds its consumer with the check.
LIMIT_CONSUMERS = {
    "P3": "derive_t15b: every 24 LP (mask 0xFFFFFF) forced-generation ratio of an Earth modset against its "
          "comparator (pairs m1_m0, m2_bab), in every suite that records one",
    "P10": "check_t15a (Tile, M1 rows)", "P11": "check_t15a (Tile, M2 rows)", "P12": "check_t15a (Entity, M1 rows)",
    "P13": "check_t15a (Entity, M2 rows)", "P14": "check_t15a (Cliff, every Earth row)",
    "P18": "derive_t15b: M0t against M0t at 16 LP (pair m0_self)",
}


def unenforced_limits(sec6):
    """The 6.2 rows in force that no check of this runner consumes (LIMIT_CONSUMERS)."""
    return [pid for pid in sorted(sec6["limits"], key=lambda k: int(k[1:])) if pid not in LIMIT_CONSUMERS]


# ------------------------------------------------------------------------------------------------ workspace

def find_ws(required=True):
    # absolute: every path built on it is handed to fh.py, which runs with the workspace as cwd
    ws = Path(os.path.abspath(os.environ.get("FACTORIO_WS") or DEFAULT_WS))
    fh = ws / "tools" / "fh.py"
    if not fh.is_file():
        if required:
            raise GateError(f"no harness at {fh}: set FACTORIO_WS to the Factorio workspace "
                            f"(this command launches the game and runs it only through fh.py)")
        return None
    return ws


class Lock:
    """The workspace-wide lock: one game-launching command at a time; a dead owner frees it."""

    def __init__(self, path):
        self.path = Path(path)
        self.held = False

    @staticmethod
    def read(path):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def is_free(path):
        import perf
        d = Lock.read(path)
        if not d or not d.get("pid"):
            return True
        return not perf.process_alive(d["pid"], d.get("start_time"))

    def acquire(self, cmd, wait_s=120):
        import perf
        self.path.parent.mkdir(parents=True, exist_ok=True)
        me = os.getpid()
        rec = {"pid": me, "start_time": perf.process_start_time(me), "cmd": cmd,
               "since": time.strftime("%Y-%m-%d %H:%M:%S")}
        t0 = time.time()
        while True:
            if self.is_free(self.path):
                tmp = self.path.with_suffix(f".{me}.tmp")
                tmp.write_text(json.dumps(rec), encoding="utf-8")
                os.replace(tmp, self.path)
                time.sleep(0.2)
                d = self.read(self.path) or {}
                if d.get("pid") == me:
                    self.held = True
                    return
            if time.time() - t0 > wait_s:
                d = self.read(self.path) or {}
                raise GateError(f"the workspace lock is held by pid {d.get('pid')} ({d.get('cmd')}, since "
                                f"{d.get('since')}); two game-launching commands never overlap")
            time.sleep(2)

    def set_token(self, token, chain, start):
        """Publish the bracket token (after the G9 start snapshot): children inherit it as
        TN_BRACKET and the repo's game-launching tools refuse without it (tnguard)."""
        rec = self.read(self.path) or {}
        if not self.held or rec.get("pid") != os.getpid():
            raise GateError("the workspace lock changed hands before the guard bracket opened")
        rec.update(token=token, chain=str(chain), start=start)
        write_atomic(self.path, json.dumps(rec))
        return {"lock": str(self.path), "chain": str(chain), "start": start, "token": token, "pid": os.getpid()}

    def release(self):
        if self.held:
            write_atomic(self.path, json.dumps({"pid": 0, "released": time.strftime("%Y-%m-%d %H:%M:%S")}))
            self.held = False


# What every G9 halt tells its reader. It names no command: a dirty guard stops all game runs and is
# reported first on the parent issue; clearing it is the maintainer's, at his own terminal.
GUARD_STOP = ("stop all game runs and report this first on the sprint parent issue (hard rule 2); only Jake "
              "clears the guard, by hand at his own interactive terminal, after reviewing the change")


class Guard:
    """The chained live-profile guard (G9; project rule 2), keyed by the part of the command's milestone.

    The chain's last entry is authoritative. A command chains to its clean end snapshot; a last entry
    whose end check failed halts every later command of the part (GUARD_STOP) until the maintainer clears it by
    hand; an entry that never finished (a killed command) is checked against its own start snapshot.
    Only a part's first command re-baselines on its own, and it refuses while the previous part's
    chain ends dirty or unfinished or the append-only journal records commands of this part that the
    chain lacks (a lost or replaced chain.json). Every start also fails closed when a build instance
    (test-instance/instances/ea-*) wrote a game log after the chain's last clean end, which means a
    game ran outside any chained bracket (design constraint 1); after an entry that never finished,
    only the instances its ledger names may have (its own runs). chain.json is written atomically."""

    def __init__(self, ctx, part, recover=False):
        self.ctx, self.part = ctx, part
        self.root = ctx.root / "guard"
        self.dir = self.root / f"part-{part}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.chain_file = self.dir / "chain.json"
        self.journal_file = self.root / "journal.jsonl"
        self.start_file = None
        self.token = None
        try:
            self.chain = self.read_chain(self.chain_file, part)
        except GateError:
            if not recover:
                raise
            moved = self.chain_file.with_name(f"chain.json.unreadable-{ctx.stamp}")
            os.replace(self.chain_file, moved)
            self._journal("chain-set-aside", moved=moved.name)
            self.chain = {"part": part, "entries": [], "set_aside": moved.name}

    @staticmethod
    def read_chain(path, part):
        if not Path(path).exists():
            return {"part": part, "entries": []}
        try:
            c = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(c, dict) or not isinstance(c.get("entries"), list):
                raise ValueError("no entries list")
            return c
        except (OSError, ValueError) as e:
            raise GateError(f"G9: {path} is unreadable ({e}); {GUARD_STOP}")

    def _save(self):
        write_atomic(self.chain_file, json.dumps(self.chain, indent=1))

    @staticmethod
    def entry_epoch(chain_dir, entry, key, snap_key):
        """When an entry started or ended (epoch seconds): its recorded time, else its snapshot
        file's modification time (entries written before the time was recorded)."""
        if entry.get(key):
            return float(entry[key])
        f = Path(chain_dir) / str(entry.get(snap_key) or "")
        return f.stat().st_mtime if entry.get(snap_key) and f.exists() else None

    @staticmethod
    def chain_last_clean_end(chain_dir, entries):
        """The end time of a chain's newest entry that ended clean (epoch seconds), or None."""
        for e in reversed(entries):
            if e.get("end"):
                return Guard.entry_epoch(chain_dir, e, "ended_epoch", "end")
        return None

    def _epoch(self, entry, key, snap_key):
        return Guard.entry_epoch(self.dir, entry, key, snap_key)

    def stray_logs(self, since, allowed=()):
        """Build instances (ea-*) whose game log is newer than `since`: a game ran there after the
        chain's last clean end, outside any chained bracket, unless the instance is in `allowed`
        (the ledger of an entry that never finished)."""
        inst = Path(self.ctx.ws) / "test-instance" / "instances"
        out = []
        if since is None or not inst.is_dir():
            return out
        for d in sorted(inst.glob("ea-*")):
            f = d / "write-data" / "factorio-current.log"
            if d.name in allowed or not f.exists():
                continue
            m = f.stat().st_mtime
            if m > since + 0.5:
                out.append(f"{d.name} ({time.strftime('%H:%M:%S', time.localtime(m))})")
        return out

    def note_launch(self, instance):
        """The open entry's ledger: every build instance this bracket launches the game on (the
        runner's own fh.py runs and its child tools'), saved before the launch."""
        if not self.start_file or not instance:
            return
        for e in self.chain["entries"]:
            if e["start"] == self.start_file:
                if instance not in e.setdefault("instances", []):
                    e["instances"].append(instance)
                    self._save()
                return

    def rebaselines(self):
        """The journal's explicit re-baselines and set-aside chains of this part, for the record."""
        return [e for e in self.journal_events() if e.get("event") in ("rebaseline", "chain-set-aside")]

    def _journal(self, event, **kw):
        rec = {"part": self.part, "event": event, "cmd": self.ctx.cmd, "slice": self.ctx.slice,
               "stamp": self.ctx.stamp, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        rec.update(kw)
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.journal_file, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def journal_events(self, part=None):
        part = self.part if part is None else part
        if not self.journal_file.exists():
            return []
        out = []
        for line in self.journal_file.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("part") == part:
                out.append(r)
        return out

    def previous_part_problem(self):
        if self.part <= 1:
            return None
        prev = self.root / f"part-{self.part - 1}" / "chain.json"
        if not prev.exists():
            return None
        try:
            c = self.read_chain(prev, self.part - 1)
        except GateError as e:
            return str(e)
        if not c["entries"]:
            return None
        last = c["entries"][-1]
        if last.get("end"):
            return None
        if last.get("ended"):
            return f"part {self.part - 1}'s chain ends dirty: {last['cmd']} ended with {last.get('check')}"
        return f"part {self.part - 1}'s chain ends with {last['cmd']} ({last['start']}), which never finished"

    def check(self, snap):
        return self.ctx.fh_plain(["guard", "check", self.dir / snap])

    def _new_file(self, suffix):
        name = f"{self.ctx.stamp}-{self.ctx.cmd}-{suffix}.json"
        n = 1
        while (self.dir / name).exists():
            n += 1
            name = f"{self.ctx.stamp}-{self.ctx.cmd}-{n}-{suffix}.json"
        return name

    def start(self):
        entries = self.chain["entries"]
        if entries:
            last = entries[-1]
            if last.get("end"):
                base, how = last["end"], f"chained to {last['cmd']} {last['end']}"
                since, allowed, ref = self._epoch(last, "ended_epoch", "end"), (), f"{last['cmd']} {last['end']}"
            elif last.get("ended"):
                raise GateError(f"G9: the last command of part {self.part}, {last['cmd']} ({last['start']}), ended "
                                f"with a dirty guard ({last.get('check')}); {GUARD_STOP}")
            else:
                base = last["start"]
                how = f"chained to the start snapshot of {last['cmd']} {last['start']}, which never finished"
                # its own runs wrote logs after its start: only the instances its ledger names may have
                since, allowed = self._epoch(last, "started_epoch", "start"), tuple(last.get("instances") or [])
                ref = f"the start of {last['cmd']} {last['start']}, which never finished (ledger {list(allowed)})"
            stray = self.stray_logs(since, allowed)
            if stray:
                raise GateError(f"G9: build instances ran the game after {ref}, outside any chained guard bracket "
                                f"(sacred constraint 1): {stray}; {GUARD_STOP}")
            res = self.check(base)
            if not res.startswith("RESULT ok"):
                raise GateError(f"G9: the live profile changed since {base} ({res}); {GUARD_STOP}")
            if not last.get("ended"):
                last["abandoned"] = (f"never finished; its start snapshot checked clean by {self.ctx.cmd} "
                                     f"{self.ctx.stamp}")
        else:
            if any(e.get("event") in ("start", "finish") for e in self.journal_events()):
                raise GateError(f"G9: {self.chain_file} holds no entries, but {self.journal_file} records commands of "
                                f"part {self.part}: the chain was lost or replaced; {GUARD_STOP}")
            prob = self.previous_part_problem()
            if prob:
                raise GateError(f"G9: {prob}; the first command of part {self.part} does not re-baseline over it; "
                                f"{GUARD_STOP}")
            prev = self.root / f"part-{self.part - 1}" / "chain.json"
            if self.part > 1 and prev.exists():
                stray = self.stray_logs(Guard.chain_last_clean_end(prev.parent,
                                                                   self.read_chain(prev, self.part - 1)["entries"]))
                if stray:
                    raise GateError(f"G9: build instances ran the game after part {self.part - 1}'s last clean end, "
                                    f"outside any chained guard bracket (sacred constraint 1): {stray}; the first "
                                    f"command of part {self.part} does not re-baseline over them; {GUARD_STOP}")
            how = "first command of the part: re-baselined"
        self.start_file = self._new_file("start")
        res = self.ctx.fh_plain(["guard", "snapshot", self.dir / self.start_file])
        if not res.startswith("RESULT ok"):
            raise GateError(f"G9 snapshot failed: {res}")
        self.token = secrets.token_hex(16)
        entries.append({"cmd": self.ctx.cmd, "slice": self.ctx.slice, "start": self.start_file, "end": None,
                        "how": how, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "started_epoch": time.time(),
                        "token": self.token, "instances": []})
        self._save()
        self._journal("start", start=self.start_file, how=how)
        return f"{res.split(' file=')[0]} ({how})"

    def finish(self):
        res = self.check(self.start_file)
        ok = res.startswith("RESULT ok")
        end_file = self._new_file("end")
        snap = self.ctx.fh_plain(["guard", "snapshot", self.dir / end_file])
        snap_ok = snap.startswith("RESULT ok")
        clean = ok and snap_ok
        for e in self.chain["entries"]:
            if e["start"] == self.start_file:
                e["end"] = end_file if clean else None
                e["check"] = res if snap_ok else f"{res}; end snapshot failed: {snap}"
                e["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
                e["ended_epoch"] = time.time()
                e["dirty"] = not clean
        self._save()
        self._journal("finish", start=self.start_file, end=end_file if clean else None, check=res, dirty=not clean)
        return clean, res, snap

    def rebaseline(self, reason, reviewed=None):
        """A manual re-baseline, by hand: a fresh snapshot becomes the chain's clean last entry, with the
        reason, the change he reviewed and what it replaced logged in the chain and the journal.
        Launches no game. cmd_guard_rebaseline is its only caller outside the runner's controls,
        and it refuses without an interactive terminal and the typed-back change list."""
        snap_file = self._new_file("rebaseline")
        res = self.ctx.fh_plain(["guard", "snapshot", self.dir / snap_file])
        if not res.startswith("RESULT ok"):
            raise GateError(f"G9 snapshot failed: {res}")
        last = self.chain["entries"][-1] if self.chain["entries"] else None
        replaced = {k: last.get(k) for k in ("cmd", "start", "end", "check", "ended")} if last else None
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.chain["entries"].append({"cmd": "guard-rebaseline", "slice": self.ctx.slice, "start": snap_file,
                                      "end": snap_file, "how": f"re-baseline by hand: {reason}", "reason": reason,
                                      "reviewed": reviewed, "replaces": replaced,
                                      "check": "RESULT ok re-baseline by hand, no check", "started": now,
                                      "ended": now, "started_epoch": time.time(), "ended_epoch": time.time()})
        self._save()
        self._journal("rebaseline", start=snap_file, reason=reason, reviewed=reviewed, replaces=replaced)
        return res


class Run:
    def __init__(self, args, code, text, out):
        self.args, self.code, self.text, self.out = args, code, text, out
        lines = [l for l in (text or "").splitlines() if l.startswith("RESULT ")]
        self.result = lines[-1] if lines else "RESULT none"

    @property
    def ok(self):
        return self.result.startswith("RESULT ok") and " isolated=yes " in self.result and " errors=0 " in self.result


class Ctx:
    """One command's working state: workspace, job object, output root, build pin, deadline."""

    def __init__(self, cmd, slice_id, budget=None, need_ws=True):
        if cmd not in COMMANDS:
            raise GateError(f"unknown command {cmd!r}")
        self.cmd, self.slice = cmd, checked_slice(slice_id)
        self.t0 = time.time()
        self.deadline = self.t0 + budget if budget else None
        self.ws = find_ws(need_ws)
        self.stamp = time.strftime("%Y%m%d-%H%M%S")
        self.killprobe = os.environ.get("TN_KILLPROBE") == "1"
        self.bracket = None
        self.guard = None
        if self.killprobe:
            # the kill probe launches the game inside its parent gate's guard bracket only
            why = tnguard.bracket_problem()
            if why:
                raise GateError(f"TN_KILLPROBE refused: {why}")
        if self.ws:
            self.fh_py = self.ws / "tools" / "fh.py"
            self.root = tnguard.absolute_output(os.environ["TN_OUT_ROOT"]) \
                if self.killprobe and os.environ.get("TN_OUT_ROOT") else self.ws / "previews" / "earth-build"
            why = tnguard.live_output_problem(self.root)
            if why:
                raise GateError(f"output root refused: {why}")
            # the guard journal is the one file under the root appended in place (every other state
            # file is replaced whole, and runs write into new folders): no second hard link
            why = tnguard.live_output_problem(self.root / "guard" / "journal.jsonl")
            if why:
                raise GateError(f"guard journal refused: {why}")
            self.out = self.root / cmd / f"{self.stamp}-{self.slice}"
            n = 1
            while self.out.exists():
                n += 1
                self.out = self.root / cmd / f"{self.stamp}-{self.slice}-{n}"
            root_r, out_r = self.root.resolve(), self.out.resolve()
            if out_r.parent != (root_r / cmd) or not out_r.is_relative_to(root_r):
                raise GateError(f"output directory {self.out} resolves outside {self.root}/{cmd}")
            why = tnguard.live_output_problem(self.out)
            if why:
                raise GateError(f"output directory refused: {why}")
            self.out.mkdir(parents=True)
            import perf
            self.perf = perf
            self.job = perf.Job()
        self.build = None
        self.instance = {"gate": "ea-gate", "suite": "ea-suite", "baseline": "ea-base",
                         "install-check": "ea-ic", "freeze": "ea-freeze"}.get(cmd, "ea-gate")
        self.log_lines = []
        self.shared = {}

    # -- output
    def say(self, line):
        print(line, flush=True)
        self.log_lines.append(line)

    def check_budget(self, what):
        if self.deadline and time.time() > self.deadline:
            raise BudgetExceeded(f"the {GATE_BUDGET_S // 60}-minute budget ran out before {what}")

    def env(self):
        e = dict(os.environ)
        e["FACTORIO_WS"] = str(self.ws)
        e.setdefault("PYTHONIOENCODING", "utf-8")
        if self.bracket:
            e[tnguard.ENV] = json.dumps(self.bracket)
        return e

    def popen_text(self, cmd, timeout, watcher=None, monitor=False):
        p = self.job.popen([str(c) for c in cmd], cwd=str(self.ws), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace", env=self.env())
        if watcher:
            watcher.go(p.pid)
        mon = None
        if monitor:
            mon = self.perf.Monitor(p.pid)
            mon.start()
        try:
            text, _ = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            text, _ = p.communicate()
            text = (text or "") + "\nRESULT fail the runner's own timeout killed this process\n"
        finally:
            if mon:
                mon.halt.set()
                mon.join()
        return p.returncode, text or "", mon

    def fh_plain(self, args, timeout=300):
        """fh.py subcommands that launch no game (guard, modset, settings, compare). They run outside
        the job, so the guard check still works after the job has been terminated."""
        cp = subprocess.run([sys.executable, str(self.fh_py)] + [str(a) for a in args], cwd=str(self.ws),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            env=self.env())
        text = (cp.stdout or "") + (cp.stderr or "")
        lines = [l for l in text.splitlines() if l.startswith("RESULT ")]
        return lines[-1] if lines else "RESULT none " + text[-300:]

    def fh(self, args, out, timeout=600, watcher=None, monitor=False):
        """A game run through fh.py into a new --out, only inside the guard bracket (the kill probe:
        inside its parent's); checks the build pin (G8) on its stdout. A run that may have left its
        instance (tnguard.run_breach) or ran on another build raises FatalRun: no later game run of
        this command starts (design constraint 1)."""
        if self.bracket is None and not self.killprobe:
            raise GateError(f"fh.py {args[0]} outside the guard bracket: every game launch sits inside the lock and "
                            f"a chained G9 snapshot and check (hard rule 2)")
        self.check_budget(f"fh.py {args[0]}")
        if self.guard is not None and "--instance" in args:
            self.guard.note_launch(str(args[list(args).index("--instance") + 1]))
        out = Path(out)
        full = list(args[:1]) + ["--out", out] + list(args[1:]) if "--out" not in args else list(args)
        if "--timeout" not in full and args[0] in ("preview", "scenario", "dump-data", "run", "sample"):
            full = full[:1] + ["--timeout", str(timeout)] + full[1:]
        code, text, mon = self.popen_text([sys.executable, self.fh_py] + full, timeout + 300, watcher, monitor)
        r = Run(full, code, text, out)
        r.mon = mon
        why = tnguard.run_breach(out, r.result)
        if why:
            raise FatalRun(f"fh.py {args[0]} into {out}: {why}")
        self.check_build(out)
        return r

    def check_build(self, out):
        for so in [out / "stdout.txt", out / "create" / "stdout.txt", out / "bench" / "stdout.txt"]:
            if not so.exists():
                continue
            m = self.perf.VERSION_RE.search(so.read_text(encoding="utf-8", errors="replace")[:4000])
            if not m:
                continue
            got = (m.group(1), m.group(2))
            if self.build is None:
                self.build = got
                self.say(f"G8 build {got[0]} build {got[1]} from {so}")
            if got != (GAME_VERSION, GAME_BUILD):
                # every vanilla hash, measured value and timing reference is the pinned build's: no
                # further run of this command means anything (G8), so all of them stop
                raise FatalRun(f"G8: the game is {got[0]} build {got[1]}, not {GAME_VERSION} build {GAME_BUILD}: "
                               f"re-baseline (vanilla hashes, measured values and timing references)")


# ------------------------------------------------------------------------------------------------ run checks

def load_run_json(run_dir):
    p = Path(run_dir) / "run.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def g1(run_dir, server=False, saves=None, since=None):
    """G1 on one run directory (or the server clause). Returns a list of failures."""
    rj = load_run_json(run_dir)
    if rj is None:
        return [f"{run_dir}: no run.json"]
    out = []
    if rj.get("isolated") is not True:
        out.append(f"{run_dir}: isolated={rj.get('isolated')}")
    if rj.get("error_lines"):
        out.append(f"{run_dir}: errors={len(rj['error_lines'])}: {rj['error_lines'][0][:160]}")
    if server:
        if rj.get("exit") != "timeout":
            out.append(f"{run_dir}: server run exit={rj.get('exit')} (want timeout)")
        for name, mtime in (saves or {}).items():
            if mtime is None or (since and mtime < since):
                out.append(f"{run_dir}: server save {name} missing or stale")
    elif rj.get("exit") != 0:
        out.append(f"{run_dir}: exit={rj.get('exit')}")
    for sub in ("create", "bench"):
        if isinstance(rj.get(sub), dict) and rj[sub].get("isolated") is False:
            out.append(f"{run_dir}/{sub}: not isolated")
    return out


def stdout_of(run_dir):
    parts = []
    for so in [Path(run_dir) / "stdout.txt", Path(run_dir) / "create" / "stdout.txt",
               Path(run_dir) / "bench" / "stdout.txt"]:
        if so.exists():
            parts.append(so.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def g2(run_dir, mods):
    so = stdout_of(run_dir)
    return [f"{run_dir}: no 'Checksum of {m}' (G2)" for m in mods if f"Checksum of {m}:" not in so]


def g3(run_dir, earth_names=()):
    out = []
    so = stdout_of(run_dir)
    for line in so.splitlines():
        if "is not defined; ignoring" in line:
            out.append(f"{run_dir}: {line.strip()[:200]} (G3)")
        elif "Mod package read error" in line:
            out.append(f"{run_dir}: {line.strip()[:200]} (zip row)")
    return out


def images_rehash(run_dir):
    rj = load_run_json(run_dir) or {}
    out = []
    for name, digest in (rj.get("images") or {}).items():
        p = Path(run_dir) / name
        if not p.exists() or sha256_file(p) != digest:
            out.append(f"{run_dir}/{name} does not re-hash to its recorded sha256")
    return out


def run_time(run_dir):
    p = Path(run_dir) / "run.json"
    return p.stat().st_mtime if p.exists() else 0.0


# ------------------------------------------------------------------------------------------------ modsets

class Mods:
    """Modsets for one command: ea- names carrying the Earth zip's sha256 prefix."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.cfg = tnconfig.load()
        self.zip = None
        self.zip_sha = None
        self.dumps = {}

    def build_zip(self):
        if self.zip is None:
            zpath, digest, rec = build_zip.build(self.ctx.out / "zip")
            self.zip, self.zip_sha = zpath, digest
            self.ctx.say(f"zip {zpath.name} sha256 {digest}")
        return self.zip

    def make(self, name, adds=(), from_live=()):
        """fh.py modset: adds are folders or zips in the repo or the workspace; from_live names mods
        fh.py copies read-only from the live mods folder (project rule 2: the build reads it only so)."""
        res = self.ctx.fh_plain(["modset", name] + (["--add"] + [str(a) for a in adds] if adds else []) +
                                (["--from-live", ",".join(from_live)] if from_live else []))
        if not res.startswith("RESULT ok"):
            raise GateError(f"fh.py modset {name}: {res}")
        return name

    def m0(self):
        return self.make("ea-m0")

    def m1(self, suffix=""):
        z = self.build_zip()
        return self.make(f"ea-m1-{self.zip_sha[:8]}{suffix}", [z])

    def with_mods(self, tag, dirs, earth=True):
        h = folder_hash(*dirs)
        if earth:
            z = self.build_zip()
            return self.make(f"ea-{tag}-{self.zip_sha[:8]}-{h}", [z] + list(dirs))
        return self.make(f"ea-{tag}-{h}", list(dirs))

    def with_live(self, tag, names):
        """M1 plus mods fh.py copies read-only from the live mods folder (`--from-live`), in a modset
        named by the Earth zip's sha256 prefix; its manifest (every zip's sha256) keys the rows
        that use it, so a changed live copy re-runs them."""
        z = self.build_zip()
        return self.make(f"ea-{tag}-{self.zip_sha[:8]}", [z], from_live=names)

    def prepare(self, modset, label):
        """G7: a first dump-data run on the modset (its mod-settings-dump.json lists what exists),
        then every Earth setting written explicitly. Returns the dump run."""
        if modset in self.dumps:
            return self.dumps[modset]
        r = self.ctx.fh(["dump-data", "--instance", self.ctx.instance, "--modset", modset],
                        self.ctx.out / f"dump-{label}")
        fails = g1(r.out) + g3(r.out)
        if fails:
            raise GateError(f"dump-data on {modset}: {fails[:3]} ({r.result})")
        sd = json.loads((r.out / "mod-settings-dump.json").read_text(encoding="utf-8")) \
            if (r.out / "mod-settings-dump.json").exists() else {}
        defined = {n for group in sd.values() if isinstance(group, dict) for n in group}
        if any(m["name"] == self.cfg["identity"]["id"] for m in self.modlist(modset)):
            sets = []
            for key in self.cfg["setting_order"]:
                s = self.cfg["settings"][key]
                if s["name"] not in defined:
                    raise GateError(f"G7: setting {s['name']} is not in {modset}'s mod-settings-dump.json")
                sets.append(f"{s['setting_type']}.{s['name']}={s['default_value']}")
            res = self.ctx.fh_plain(["settings", modset, "--set"] + sets)
            if not res.startswith("RESULT ok"):
                raise GateError(f"fh.py settings {modset}: {res}")
        self.dumps[modset] = r
        return r

    def modlist(self, modset):
        f = self.ctx.ws / "test-instance" / "modsets" / modset / "mod-list.json"
        return json.loads(f.read_text(encoding="utf-8"))["mods"] if f.exists() else []

    def manifest(self, modset):
        d = self.ctx.ws / "test-instance" / "modsets" / modset
        items = []
        for p in sorted(d.iterdir()):
            if p.name in ("mod-settings.dat",) or p.name.startswith("mod-settings.dat."):
                continue
            if p.is_file():
                items.append((p.name, sha256_file(p)))
            elif p.is_dir():
                items.append((p.name, folder_hash(p)))
        return items


def folder_hash(*dirs):
    h = hashlib.sha256()
    for d in dirs:
        d = Path(d)
        if d.is_file():
            h.update(d.name.encode() + b"\0" + d.read_bytes())
            continue
        for p in sorted(q for q in d.rglob("*") if q.is_file()):
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:8]


def stage_twin(ctx, cfg):
    """A staged copy of tools/mods/ea-coast-twin naming the firewall bodies config.lua marks: the
    test mod gets every Earth name from the runner at run time (D36 stays a config edit)."""
    src = HERE / "mods" / "ea-coast-twin"
    dst = ctx.out / "stage" / "ea-coast-twin"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    names = firewall_names(cfg)
    lua_list = ", ".join(json.dumps(n) for n in names)
    (dst / "twin-names.lua").write_text(f"return {{names = {{{lua_list}}}, value = {json.dumps(TWIN_CONSTANT)}}}\n",
                                        encoding="utf-8", newline="\n")
    info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
    info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
    (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    return dst


def firewall_names(cfg):
    """The fine field (design constraint 3): each map's elevation entry and every term only it
    reads, from config.lua's firewall group and the placeholder's firewall keys (in toolchain the
    placeholder elevation). A wrong shape or an empty set raises: an isolation check against no
    name would pass while testing nothing."""
    try:
        names = tnconfig.firewall_names(cfg)
    except tnconfig.ConfigError as e:
        raise GateError(str(e))
    if not names:
        raise GateError("config.lua names no firewall body (firewall, placeholder.firewall): the isolation checks "
                        "would test nothing")
    return names


START_MASK_KEY = "starting_resources_lake_mask"   # vanilla's starting-ore mask (R6 Q3)
LEAK_FIXTURE = "ea-leak-fixture"                  # the test mod, and its start-mask control preset
LEAK_FIXTURE_PROPS = "ea-leak-fixture-props"      # its property-key control preset (isolation b)
LEAK_BODIES = {"entity": "ea_leak_fixture_entity", "decorative": "ea_leak_fixture_decorative"}
LEAK_CONSTANTS = {"ea_leak_fixture_number": 6, "ea_leak_fixture_flag": True}


def earth_presets(cfg):
    return [cfg["presets"][k]["name"] for k in cfg["preset_order"]]


def placeholder_presets(cfg):
    """The names of the presets config.lua marks placeholder (toolchain's; europe-coast removes them)."""
    return [cfg["presets"][k]["name"] for k in cfg["preset_order"] if (cfg["presets"][k] or {}).get("placeholder")]


def preset_pen(dump, name):
    p = ((dump or {}).get("map-gen-presets") or {}).get("default", {}).get(name) or {}
    return (p.get("basic_settings") or {}).get("property_expression_names") or {}


def lua_value(v):
    """A property_expression_names value as a Lua literal: a name or numeric string, a number or a
    boolean (the values' types, string|boolean|double, in the local prototype docs)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and v == v and abs(v) != float("inf"):
        return repr(v)
    if isinstance(v, str) and v.isascii() and v.isprintable():
        return json.dumps(v)
    raise GateError(f"the leak fixture cannot stage the redirect value {v!r}: not a name, a number or a boolean")


def lua_names(pen):
    return "{" + ", ".join(f"[{lua_value(k)}] = {lua_value(v)}" for k, v in sorted(pen.items())) + "}"


def leak_fixture(ctx, mods):
    """The isolation checks' positive controls, staged once per command: tools/mods/ea-leak-fixture
    with two test-only presets, and the modset M1 plus that fixture.

    LEAK_FIXTURE carries every key of the first Terra Nauvis preset but the start mask (numbers
    stay numbers), so vanilla starting ore reads the fine field: isolation (a) must see Entity
    change against the twin there and (b) must walk to the fine field through the start mask.
    LEAK_FIXTURE_PROPS carries every key of that preset, the start mask included, plus two
    property-keyed redirects, one entity and one decorative autoplace key of a prototype Nauvis
    places, each to a fixture body that reads a firewall name (ARCHITECTURE, Preset redirects:
    `entity:<ore>:probability` and the like): (b) must follow both keys to the fine field, which a
    walk of the prototypes' own text never reaches. It also carries LEAK_CONSTANTS, a number and a
    boolean that no expression reads, so the fixture's data stage proves it stages number-valued
    redirects as they are (the dump must hold them unchanged). Returns {"dir", "modset", "start",
    "props", "keys"} (the two staged redirect tables and the property keys of the second)."""
    if "leak_fixture" in ctx.shared:
        return ctx.shared["leak_fixture"]
    cfg = mods.cfg
    d1 = ctx.shared.get("dump_m1")
    if d1 is None:
        raise GateError("the leak fixture needs the M1 dump (row dumps)")
    full = preset_pen(d1, earth_presets(cfg)[0])
    start = {k: v for k, v in full.items() if k != START_MASK_KEY}
    fw = sorted(firewall_names(cfg))
    if not any(isinstance(v, str) and v in fw for v in start.values()):
        raise GateError(f"the leak fixture would redirect {start}, which names no firewall body")
    placed = placed_autoplace(d1)
    ore = next((n for t, n in sorted(placed["entity"]) if t == "resource"), None)
    dec = next((n for _, n in sorted(placed["decorative"])), None)
    if not ore or not dec:
        raise GateError(f"the M1 dump places no resource ({ore}) or no decorative ({dec}): the property-key control "
                        f"has no root to redirect")
    keys = {"entity": f"entity:{ore}:probability", "decorative": f"decorative:{dec}:richness"}
    props = dict(full)
    props.update({keys[g]: LEAK_BODIES[g] for g in keys})
    # a number and a boolean as values, as the presets bake tn_map, tn_scale and tn_on from europe-coast
    # on: the fixture's data stage must stage them as they are (no expression reads these keys)
    props.update(LEAK_CONSTANTS)
    exprs = [{"name": LEAK_BODIES[g], "expression": f"clamp({fw[0]}, 0, 1)"} for g in sorted(LEAK_BODIES)]
    src = HERE / "mods" / LEAK_FIXTURE
    dst = ctx.out / "stage" / LEAK_FIXTURE
    shutil.copytree(src, dst, dirs_exist_ok=True)
    presets_lua = ", ".join(f"{{name = {lua_value(n)}, order = {lua_value(o)}, names = {lua_names(p)}}}"
                            for n, o, p in ((LEAK_FIXTURE, "z-ea-leak", start), (LEAK_FIXTURE_PROPS, "z-ea-leak-props",
                                                                                  props)))
    exprs_lua = ", ".join(f"{{name = {lua_value(e['name'])}, expression = {lua_value(e['expression'])}}}" for e in exprs)
    (dst / "fixture-names.lua").write_text(f"return {{presets = {{{presets_lua}}}, expressions = {{{exprs_lua}}}}}\n",
                                           encoding="utf-8", newline="\n")
    info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
    info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
    (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    m1f = mods.with_mods("m1f", [dst])
    ctx.shared["leak_fixture"] = {"dir": dst, "modset": m1f, "start": start, "props": props, "keys": keys}
    return ctx.shared["leak_fixture"]


def placeholder_preset(cfg):
    ph = cfg.get("placeholder") or {}
    return cfg["presets"][ph["preset"]]["name"] if ph else None


# ------------------------------------------------------------------------------------------------ dump walk

TOKEN_RE = re.compile(r"var\(\s*'([^']+)'\s*\)|var\(\s*\"([^\"]+)\"\s*\)|'[^']*'|\"[^\"]*\"|([A-Za-z_][A-Za-z0-9_]*)")


def expr_refs(expr):
    if not isinstance(expr, str):
        return []
    out = []
    for m in TOKEN_RE.finditer(expr):
        n = m.group(1) or m.group(2) or m.group(3)
        if n:
            out.append(n)
    return out


def redirect_constant(v):
    """True when a property_expression_names value is a number (a double, a boolean or a numeric
    string; the local prototype docs type the values string|boolean|double): the property is then
    that constant and reads no expression. ARCHITECTURE's Preset redirects bake tn_map, tn_scale,
    tn_city, tn_geo and tn_on as numbers."""
    if isinstance(v, (bool, int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def autoplace_index(dump):
    """{property key: (texts, local names)} of every tile, entity and decorative autoplace in the
    dump. `entity:<name>:probability` and `:richness` (and the decorative and tile keys) are
    readable variables and redirectable keys whose default is the prototype's own autoplace
    expression, its local expressions in scope (doc-html/auxiliary/noise-expressions.html)."""
    idx = {}
    for t, protos in dump.items():
        if not isinstance(protos, dict):
            continue
        kind = "tile" if t == "tile" else "decorative" if t == "optimized-decorative" else "entity"
        for name, p in protos.items():
            ap = p.get("autoplace") if isinstance(p, dict) else None
            if not isinstance(ap, dict):
                continue
            locs = ap.get("local_expressions") or {}
            for prop in ("probability", "richness"):
                idx[f"{kind}:{name}:{prop}"] = ([ap.get(f"{prop}_expression")] + list(locs.values()), set(locs))
    return idx


def _body_texts(ne, nf, name):
    """(texts, local names) of a named noise expression or function, or (None, set())."""
    body = ne.get(name) or nf.get(name)
    if not isinstance(body, dict):
        return None, set()
    texts = [body.get("expression")] + list((body.get("local_expressions") or {}).values())
    texts += [f.get("expression") for f in (body.get("local_functions") or {}).values() if isinstance(f, dict)]
    # names local to this body (locals, local functions, parameters) never resolve globally
    scope = (set(body.get("local_expressions") or {}) | set(body.get("local_functions") or {}) |
             set(body.get("parameters") or []))
    return texts, scope


class NoiseGraph:
    """Name resolution in the programs of a map made with one preset, as the local docs give it:
    locals and parameters first, then the map's property_expression_names (the preset's, under the
    planet's own, which win: noise rule 3), then prototype names. A redirect to a number is
    that constant and reads nothing; a redirect to an undefined name is ignored by the game (a log
    line, G3), which then reads the default; an autoplace property key that is not redirected reads
    the prototype's own autoplace expression."""

    def __init__(self, dump, pen):
        self.ne = dump.get("noise-expression", {}) or {}
        self.nf = dump.get("noise-function", {}) or {}
        self.idx = autoplace_index(dump)
        self.eff = dict(pen or {})
        planet = ((dump.get("planet") or {}).get("nauvis") or {}).get("map_gen_settings") or {}
        self.eff.update(planet.get("property_expression_names") or {})

    def walk(self, starts, hit_name, hit_target=None):
        """Depth first from `starts` ([(name, path)]): (every name reached with its path, the paths
        that end on a name for which hit_name is true or a redirect target for which hit_target is)."""
        seen, hits, stack = {}, [], list(starts)
        while stack:
            name, path = stack.pop()
            if name in seen:
                continue
            seen[name] = path
            if hit_name(name):
                hits.append(path + (name,))
                continue
            node, texts, scope = name, None, set()
            if name in self.eff:
                v = self.eff[name]
                if redirect_constant(v):
                    continue
                if isinstance(v, str) and (v in self.ne or v in self.nf):
                    path = path + (f"{name}->(preset) {v}",)
                    if hit_target and hit_target(v):
                        hits.append(path + (v,))
                        continue
                    if v in seen:
                        continue
                    seen[v] = path
                    node = v
                    texts, scope = _body_texts(self.ne, self.nf, v)
                else:
                    path = path + (f"{name}->(preset) {v!r}, which is undefined: the game reads the default",)
            if texts is None:
                texts, scope = self.idx[name] if name in self.idx else _body_texts(self.ne, self.nf, name)
            for tx in texts or []:
                for ref in expr_refs(tx):
                    if ref not in scope:
                        stack.append((ref, path + (node,)))
        return seen, hits

    def reads_property(self, target, key):
        """The path by which the redirect target of `key` reads `key` itself, directly or through
        any name it reads (A-3: the game fails with 'Parameter arg_register expects Number, None
        given.'), or None."""
        texts, scope = _body_texts(self.ne, self.nf, target)
        starts = [(ref, (f"{key}->(preset) {target}", target)) for tx in (texts or []) for ref in expr_refs(tx)
                  if ref not in scope]
        _, hits = self.walk(starts, lambda n: n == key)
        return list(hits[0]) if hits else None


def placed_autoplace(dump):
    """{"entity": [(type, name)], "decorative": [(type, name)]}: the prototypes Nauvis places (its
    autoplace settings list them, or their autoplace names a control the planet lists)."""
    planet = dump["planet"]["nauvis"]["map_gen_settings"]
    controls = set(planet.get("autoplace_controls", {}))
    ent_settings = set(((planet.get("autoplace_settings") or {}).get("entity") or {}).get("settings", {}) or {})
    dec_settings = set(((planet.get("autoplace_settings") or {}).get("decorative") or {}).get("settings", {}) or {})
    out = {"entity": [], "decorative": []}
    for t, protos in dump.items():
        if t == "tile" or not isinstance(protos, dict):
            continue
        for name, p in protos.items():
            ap = p.get("autoplace") if isinstance(p, dict) else None
            if not isinstance(ap, dict):
                continue
            group = "decorative" if t == "optimized-decorative" else "entity"
            if name in (dec_settings if group == "decorative" else ent_settings) or ap.get("control") in controls:
                out[group].append((t, name))
    return out


def walk_roots(dump, pen, firewall):
    """Isolation check (b): from every Entity, decorative and Cliff root on Nauvis, follow named
    expressions, noise functions, var() names and the map's property_expression_names (NoiseGraph);
    report each root group that reaches a firewall name, with its paths. A placed prototype's
    program reads its property keys, `entity:<name>:probability` and `:richness` (decoratives
    `decorative:...`), so a key the preset redirects is walked through its target and the
    prototype's own text only when it is not redirected (ARCHITECTURE, Preset redirects: the ore
    and offshore-oil keys from milestone 9 on)."""
    roots = {"entity": [], "decorative": [], "cliff": []}
    for group, items in placed_autoplace(dump).items():
        for t, name in items:
            roots[group].append((f"{t}/{name}", [f"{group}:{name}:probability", f"{group}:{name}:richness"]))
    for prop in ("cliff_elevation", "cliffiness"):
        roots["cliff"].append((f"cliff:{prop}", [prop]))
    fw = set(firewall)
    graph = NoiseGraph(dump, pen)
    report = {}
    for group, items in roots.items():
        starts = [(ref, (rname,)) for rname, refs in items for ref in refs]
        seen, hits = graph.walk(starts, lambda n: n in fw, lambda n: n in fw)
        report[group] = {"roots": len(items), "names_reached": len(seen), "hits": len(hits),
                         "example": list(hits[0]) if hits else None, "paths": [list(h) for h in hits[:24]],
                         "reached": sorted(seen)}
    return report


# ------------------------------------------------------------------------------------------------ rows

class Row:
    def __init__(self, name):
        self.name = name
        self.fails = []
        self.detail = ""
        self.run_dirs = []
        self.meas = {}
        self.cached = False


def fg_rows(ctx, mods, sec6, rows_wanted, use_cache):
    """Run each FG row (live, or re-validated from the cache when its key matches). Every live row
    that passes writes its cache entry, so a suite leaves every gate key warm."""
    results = []
    cache = Cache(ctx)
    cache.read = use_cache
    for name in rows_wanted:
        row = Row(name)
        t = time.time()
        try:
            fn = ROW_FUNCS[name]
            fn(ctx, mods, sec6, row, cache)
        except BudgetExceeded:
            raise
        except GateError as e:
            row.fails.append(str(e))
        except Exception as e:
            row.fails.append(f"row crashed: {type(e).__name__}: {e}")
            ctx.say(traceback.format_exc()[-1500:])
        ok = not row.fails
        ctx.say(f"ROW {'ok  ' if ok else 'FAIL'} {name}{' (cache hit, re-validated)' if row.cached else ''}: "
                f"{row.detail} [{time.time() - t:.1f}s]")
        for f in row.fails[:10]:
            ctx.say(f"     - {f}")
        results.append(row)
    return results


class Cache:
    """Content-hash cache of FG rows: run directories and measurements, never a verdict."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.file = ctx.root / "cache" / "index.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.idx = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}
        except ValueError:
            # a cache index is never trusted evidence: an unreadable one only costs live re-runs
            moved = self.file.with_name(f"index.json.unreadable-{ctx.stamp}")
            os.replace(self.file, moved)
            ctx.say(f"     the FG cache index was unreadable; set aside as {moved.name}, every row runs live")
            self.idx = {}
        self.read = True

    def get(self, key):
        return self.idx.get(key) if self.read else None

    def put(self, key, row, newest):
        self.idx[key] = {"row": row.name, "run_dirs": [rel_ws(self.ctx, d) for d in row.run_dirs],
                         "meas": row.meas, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "inputs_mtime": newest}
        write_atomic(self.file, json.dumps(self.idx, indent=1))


def rel_ws(ctx, p):
    try:
        return Path(p).resolve().relative_to(ctx.ws.resolve()).as_posix()
    except ValueError:
        return str(p)


def abs_ws(ctx, p):
    q = Path(p)
    return q if q.is_absolute() else ctx.ws / q


def cached_or_live(ctx, row, cache, key, newest, live, derive, server_dirs=()):
    """Rule 2 for an FG row: a key hit re-validates the raw outputs and re-derives; else run live."""
    if cache is not None:
        hit = cache.get(key)
        if hit:
            dirs = [abs_ws(ctx, d) for d in hit["run_dirs"]]
            problems = []
            for d in dirs:
                if d in server_dirs:
                    continue
                problems += g1(d) + images_rehash(d)
                if run_time(d) < newest:
                    problems.append(f"{d} predates the newest input change")
            if not problems:
                meas, fails, detail = derive(dirs)
                meas = json.loads(json.dumps(meas, default=str))
                if meas == hit["meas"]:
                    row.cached, row.run_dirs, row.meas, row.fails, row.detail = True, dirs, meas, fails, detail
                    return
                ctx.say(f"     cache entry for {row.name} re-derived differently; running it live")
            else:
                ctx.say(f"     cache entry for {row.name} failed re-validation ({problems[0]}); running it live")
    dirs = live()
    meas, fails, detail = derive(dirs)
    meas = json.loads(json.dumps(meas, default=str))
    row.run_dirs, row.meas, row.fails, row.detail = dirs, meas, fails, detail
    if cache is not None and not fails:
        cache.put(key, row, newest)


def input_digests(ctx):
    """Digests of the input categories keys are built from (computed once per command)."""
    if "digests" in ctx.shared:
        return ctx.shared["digests"]
    d = {}
    d["mod"], m1 = tree_digest([MOD])
    d["control"], m2 = tree_digest([MOD / "control.lua", MOD / "scripts"])
    d["tools"], m3 = tree_digest([p for p in HERE.glob("*.py")] + [HERE / "lint", HERE / "affinity_watch.ps1"])
    d["test_mods"], m4 = tree_digest([HERE / "mods"])
    d["data_src"], m5 = tree_digest([REPO / "data-src"])
    d["tests"], m6 = tree_digest([TESTS], exclude=("tests/baselines/suites/",))
    d["fh"] = sha256_file(ctx.fh_py)
    d["sampler"] = folder_hash(ctx.ws / "tools" / "probe-mods" / "fh-sampler")
    d["newest"] = max(m1, m2, m3, m4, m5, m6)
    ctx.shared["digests"] = d
    return d


def common_key(ctx, name, extra=None):
    d = input_digests(ctx)
    return key_of({"row": name, "build": [GAME_VERSION, GAME_BUILD], "mod": d["mod"], "tools": d["tools"],
                   "test_mods": d["test_mods"], "data_src": d["data_src"], "tests": d["tests"], "fh": d["fh"],
                   "extra": extra or {}}), d["newest"]


# -- step 1: static and plan rows

def row_static(ctx, mods, sec6, row, cache):
    """T16 static rows, run as `earth_test.py static` with FACTORIO_WS unset: proves CI's command."""
    env = {k: v for k, v in os.environ.items() if k != "FACTORIO_WS"}
    if not env.get("TN_LUACHECK"):
        manifest = tn_static.lint_manifest()
        exe = tn_static.find_luacheck(manifest)
        if exe:
            env["TN_LUACHECK"] = str(exe)
    cp = subprocess.run([sys.executable, str(HERE / "earth_test.py"), "static"], cwd=str(REPO), capture_output=True,
                        text=True, encoding="utf-8", errors="replace", env=env)
    out = cp.stdout + cp.stderr
    (ctx.out / "static.txt").write_text(out, encoding="utf-8")
    last = [l for l in out.splitlines() if l.startswith("STATIC ")]
    row.detail = (last[-1] if last else "no STATIC line") + " (FACTORIO_WS unset)"
    if cp.returncode != 0 or not last or not last[-1].startswith("STATIC ok"):
        row.fails += [l.strip() for l in out.splitlines() if l.startswith(("ROW FAIL", "     - "))][:12] or [out[-400:]]


def read_fh_sets(fh_py):
    import ast
    tree = ast.parse(Path(fh_py).read_text(encoding="utf-8"))
    sets = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("GUI_FLAGS", "FORBIDDEN_EXTRA", "HEADLESS_ACTIONS"):
                sets[node.targets[0].id] = sorted(ast.literal_eval(node.value))
    return sets


def tool_constant(path, name):
    """A module-level literal of a tool, read with ast (the tool is never imported here)."""
    import ast
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and \
                node.targets[0].id == name:
            return ast.literal_eval(node.value)
    raise GateError(f"{Path(path).name} defines no literal {name}")


KILLPROBE_INSTANCE = "ea-killprobe"


def row_fh_flags(ctx, mods, sec6, row, cache):
    """The launch scan's vendored flag sets equal fh.py's (read with ast, never imported)."""
    vend = json.loads((HERE / "lint" / "fh-flags.json").read_text(encoding="utf-8"))
    live = read_fh_sets(ctx.fh_py)
    for k in ("GUI_FLAGS", "FORBIDDEN_EXTRA"):
        if sorted(vend[k]) != live.get(k):
            row.fails.append(f"tools/lint/fh-flags.json {k} differs from fh.py's: {sorted(set(vend[k]) ^ set(live.get(k, [])))}")
    sha = sha256_file(ctx.fh_py)
    note = "" if sha == vend.get("fh_py_sha256") else f"; fh.py changed since vendoring ({sha[:12]}), sets still equal"
    row.detail = f"{len(vend['GUI_FLAGS'])} GUI flags, {len(vend['FORBIDDEN_EXTRA'])} isolation flags equal fh.py's{note}"


def row_plan_main(ctx, mods, sec6, row, cache):
    work = PLAN.read_text(encoding="utf-8")
    main = git_show("main:SPRINT-1-PLAN.md")
    row.fails += plan_matches_main(work, main)
    row.detail = "SPRINT-1-PLAN.md equals main's copy" if not row.fails else "plan differs from main"


def row_section6(ctx, mods, sec6, row, cache):
    if isinstance(sec6, Exception):
        row.fails.append(str(sec6))
        row.detail = "section 6 unreadable"
        return
    lim = sec6["limits"]
    row.fails += [f"6.2 row {pid} is in force through {ctx.slice} but no check of this runner enforces it "
                  f"(LIMIT_CONSUMERS): a bar parsed and enforced by none fails closed" for pid in unenforced_limits(sec6)]
    row.detail = (f"from main's copy, every cell parsed: limits {sorted(lim, key=lambda k: int(k[1:]))} in force "
                  f"through {ctx.slice}, each with its enforcing check ({len(sec6['all_limits'])} rows; "
                  f"{sec6['from_first_slice']} name no slice in From and are in force from {sec6['order'][0]}); "
                  f"allocations of {sorted(sec6['allocations'])} ({len(sec6['all_allocations'])} slices read)")


NOISE_TYPES = ("noise-expression", "noise-function")
FREEZE_CMD = "python tools/earth_test.py freeze"


def earth_bodies(dump, cfg):
    """Every Earth noise body of a dump as {name: (type, prototype)}: a noise-expression or
    noise-function whose name carries config.lua's noise prefix or is a noise name config.lua
    defines (the schema requires the prefix of every such name, so the two agree)."""
    prefix = ((cfg or {}).get("identity") or {}).get("noise_prefix") or "\0"
    known = set(tnconfig.noise_names(cfg)) if cfg and cfg.get("identity") else set()
    out = {}
    for t in NOISE_TYPES:
        for name, proto in ((dump or {}).get(t) or {}).items():
            if name.startswith(prefix) or name in known:
                out[name] = (t, proto)
    return out


def frozen_exempt(cfg):
    """The names never registered (U3's one exemption plus the placeholder): the placeholder's names
    and the Map type fallbacks."""
    if not cfg:
        return set()
    return set(tnconfig.placeholder_names(cfg)) | set(tnconfig.fallback_names(cfg))


def frozen_check(fz_work, fz_main, dumps, cfg):
    """The frozen-body checker (design constraint 2): tests/frozen.json is append-only
    against main; every registered body is present in the dump it was registered from with the
    same generation-field hash; no placeholder name or Map type fallback is registered; and every
    Earth body of every dump the gate reads (M1, and M2 once a milestone adds it) is registered, the
    placeholder's names and the fallbacks excepted, so a body can neither ship unregistered nor
    change in place unseen. `dumps` maps a dump label ("m1", "m2") to its data-raw dump."""
    fails = []
    if dumps is not None and not isinstance(dumps, dict):
        dumps = {"m1": dumps}
    bodies = (fz_work or {}).get("bodies", {})
    for name, rec in ((fz_main or {}).get("bodies") or {}).items():
        if name not in bodies:
            fails.append(f"{name} is registered on main but missing from tests/frozen.json (append-only)")
        elif bodies[name].get("sha256") != rec.get("sha256"):
            fails.append(f"{name}: tests/frozen.json changed a registered hash (append-only)")
    ph = set(tnconfig.placeholder_names(cfg)) if cfg else set()
    fb = set(tnconfig.fallback_names(cfg)) if cfg else set()
    for name, rec in bodies.items():
        if name in ph:
            fails.append(f"placeholder name {name} is registered")
        if name in fb:
            fails.append(f"Map type fallback {name} is registered (fallbacks mirror startup settings and never are; U3)")
        if dumps:
            label = rec.get("dump", "m1")
            if label not in dumps:
                continue
            body = (dumps[label].get(rec.get("type", "noise-expression")) or {}).get(name)
            if body is None:
                fails.append(f"registered body {name} is missing from the {label} dump (old names stay defined)")
            elif body_hash(body) != rec.get("sha256"):
                fails.append(f"registered body {name} changed in place (ship it under the next _v<n>)")
    exempt = ph | fb
    for label, dump in sorted((dumps or {}).items()):
        for name in sorted(earth_bodies(dump, cfg)):
            if name not in exempt and name not in bodies:
                fails.append(f"Earth body {name} of the {label} dump is not registered in tests/frozen.json "
                             f"(sacred constraint 2): register it with {FREEZE_CMD}")
    return fails


GEN_FIELDS = ("type", "name", "expression", "local_expressions", "local_functions", "parameters")


def body_hash(proto):
    """sha256 of a noise body's generation fields only (never intended_property, localised_name, order)."""
    return key_of({k: proto.get(k) for k in GEN_FIELDS if k in proto})


def gate_dumps(ctx, through):
    """The dumps the frozen row and freeze read, by label, from the registry's `dumps` of every
    milestone up to `through` (toolchain: M1; climate-tiles adds M2). A label the dumps row did not
    produce fails closed."""
    labels = []
    for s in registry_upto(through):
        for label in s.get("dumps", []):
            if label not in labels:
                labels.append(label)
    out = {}
    for label in labels:
        d = ctx.shared.get(f"dump_{label}")
        if d is None:
            raise GateError(f"the registry names the {label} dump, which this command did not produce")
        out[label] = d
    if not out:
        raise GateError("the registry names no dump for the frozen-body check")
    return out


def frozen_controls(cfg):
    """The frozen checker on fixture dumps: a changed hash, a missing name and an unregistered Earth
    body fail (naming the freeze command); a GUI-only change, the placeholder's names and a Map type
    fallback left unregistered pass."""
    prefix = cfg["identity"]["noise_prefix"]
    body = {"type": "noise-expression", "name": f"{prefix}fixture_v1", "expression": "x + 1"}
    reg = {"bodies": {f"{prefix}fixture_v1": {"type": "noise-expression", "sha256": body_hash(body)}}}
    d_changed = {"noise-expression": {f"{prefix}fixture_v1": dict(body, expression="x + 2")}}
    d_missing = {"noise-expression": {}}
    d_gui = {"noise-expression": {f"{prefix}fixture_v1": dict(body, intended_property="elevation", order="z",
                                                               localised_name=["x"])}}
    d_new = {"noise-expression": {f"{prefix}fixture_v1": body,
                                  f"{prefix}fixture_elevation_europe_v1": dict(body, name="x", expression="x")},
             "noise-function": {f"{prefix}fixture_fn_v1": {"type": "noise-function", "expression": "a",
                                                          "parameters": ["a"]}}}
    ph = tnconfig.placeholder_names(cfg)
    d_ph = {"noise-expression": dict({n: dict(body, name=n) for n in ph}, **{f"{prefix}fixture_v1": body})}
    fb_cfg = dict(cfg, fallbacks={cfg["map_order"][0]: [{"name": f"{prefix}fixture_fallback", "map_qualified": False}]})
    d_fb = {"noise-expression": {f"{prefix}fixture_v1": body, f"{prefix}fixture_fallback": dict(body, name="f")}}
    new_fails = frozen_check(reg, reg, {"m1": d_new}, cfg)
    return {"changed hash fails": bool(frozen_check(reg, reg, {"m1": d_changed}, cfg)),
            "missing name fails": bool(frozen_check(reg, reg, {"m1": d_missing}, cfg)),
            "GUI-only change passes": not frozen_check(reg, reg, {"m1": d_gui}, cfg),
            "an unregistered Earth expression and function fail and name the freeze command": (
                len(new_fails) == 2 and all(FREEZE_CMD in f for f in new_fails)),
            "an unregistered body of the M2 dump fails too": bool(frozen_check(reg, reg, {"m1": d_gui, "m2": d_new},
                                                                              cfg)),
            "the placeholder's names stay unregistered": (not frozen_check(reg, reg, {"m1": d_ph}, cfg)) if ph else True,
            "a Map type fallback stays unregistered": not frozen_check(reg, reg, {"m1": d_fb}, fb_cfg)}


def row_frozen(ctx, mods, sec6, row, cache):
    cfg = mods.cfg
    work = json.loads((TESTS / "frozen.json").read_text(encoding="utf-8"))
    main_text = git_show("main:tests/frozen.json")
    main = json.loads(main_text) if main_text else {"bodies": {}}
    dumps = gate_dumps(ctx, ctx.slice)
    row.fails += frozen_check(work, main, dumps, cfg)
    seen = sorted({n for d in dumps.values() for n in earth_bodies(d, cfg)})
    ctl = frozen_controls(cfg)
    for k, ok in ctl.items():
        if not ok:
            row.fails.append(f"frozen checker positive control did not behave: {k}")
    row.detail = (f"{len(work.get('bodies', {}))} registered bodies, append-only against main; Earth bodies of the "
                  f"{sorted(dumps)} dumps {seen}, every one registered or exempt (placeholder, fallbacks); "
                  f"{sum(ctl.values())} of {len(ctl)} controls behaved")


# -- data-src (decoder regeneration) and the offline self-tests

def row_data_src(ctx, mods, sec6, row, cache):
    src = ctx.ws / "downloads" / "earthmaps" / "src"
    em = REPO / "data-src" / "earthmaps"
    srcd, _ = tree_digest([src / "data"], root=src)
    key, newest = common_key(ctx, "data_src", {"earthmaps_src": srcd})

    def live():
        out = ctx.out / "data-src"
        out.mkdir(parents=True)
        cmd = [sys.executable, "-I", HERE / "earthmaps_decode.py", src, "--png-out", out / "png", "--json-out",
               out / "json", "--no-simulation"]
        code, text, _ = ctx.popen_text(cmd, 600)
        (out / "decode.txt").write_text(text, encoding="utf-8")
        rec = {"exit": code, "isolated": True, "error_lines": [] if code == 0 else [text[-300:]], "images": {}}
        for p in sorted((out / "png").glob("*.png")):
            rec["images"][f"png/{p.name}"] = sha256_file(p)
        (out / "run.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        return [out]

    def derive(dirs):
        out = dirs[0]
        fails = []
        meas = {}
        cfg = mods.cfg
        for key_ in cfg["map_order"]:
            J = json.loads((em / f"{key_}.json").read_text(encoding="utf-8"))
            R = json.loads((out / "json" / f"{key_}.json").read_text(encoding="utf-8"))
            for kind, rec in J["png"].items():
                regen = out / "png" / rec["file"]
                committed = em / rec["file"]
                if not regen.exists():
                    fails.append(f"decoder wrote no {rec['file']}")
                    continue
                a, b = regen.read_bytes(), committed.read_bytes()
                if a != b:
                    fails.append(f"{rec['file']}: regenerated bytes differ from data-src (TST-01)")
                if sha256_bytes(a) != rec["sha256"]:
                    fails.append(f"{rec['file']}: regenerated sha256 differs from {key_}.json png.{kind}")
                meas[rec["file"]] = sha256_bytes(a)
            for k in ("width_px", "height_px"):
                if R[k] != J[k]:
                    fails.append(f"{key_}: {k} {R[k]} differs from the reference {J[k]}")
            rc = {c["code"]: c["pixels"] for c in R["class_legend"]["classes"]}
            jc = {c["code"]: c["pixels"] for c in J["class_legend"]["classes"]}
            if rc != jc:
                fails.append(f"{key_}: class counts differ from the reference JSON")
            meas[f"{key_}_classes"] = jc
        return meas, fails, f"{len([k for k in meas if k.endswith('.png')])} rasters regenerated byte for byte " \
                            f"with python -I tools/earthmaps_decode.py; sizes and class counts equal the reference"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_offline_selftests(ctx, mods, sec6, row, cache):
    # the oracle's staged activation: a property may hold expectations once the milestone that
    # owns it is live, which is every registry milestone up to the gate's --through
    live_slices = [s["id"] for s in registry_upto(ctx.slice)]
    key, newest = common_key(ctx, "offline_selftests", {"live": live_slices})

    def live():
        out = ctx.out / "offline-selftests"
        out.mkdir(parents=True)
        rec = {"exit": 0, "isolated": True, "error_lines": [], "tools": {}}
        for tool in list(S8_COUNTS) + ["oracle-validate", "perf"]:
            args = [HERE / "oracle.py", "validate", "--live", ",".join(live_slices)] if tool == "oracle-validate" else \
                [HERE / f"{tool}.py"] + ([] if tool == "perf" else ["selftest"])
            code, text, _ = ctx.popen_text([sys.executable] + args, 600)
            (out / f"{tool}.txt").write_text(text, encoding="utf-8")
            rec["tools"][tool] = code
        (out / "run.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        return [out]

    def derive(dirs):
        out = dirs[0]
        fails, meas = [], {}
        for tool in list(S8_COUNTS) + ["oracle-validate", "perf"]:
            text = (out / f"{tool}.txt").read_text(encoding="utf-8")
            res = [l for l in text.splitlines() if l.startswith("RESULT ")]
            m = re.search(r"checks=(\d+) failed=(\d+)", res[-1]) if res else None
            if not res or not res[-1].startswith("RESULT ok") or not m or m.group(2) != "0":
                fails.append(f"{tool} selftest: {res[-1] if res else 'no RESULT line'}")
                continue
            meas[tool] = int(m.group(1))
            if tool in S8_COUNTS and int(m.group(1)) != S8_COUNTS[tool]:
                fails.append(f"{tool} ran {m.group(1)} checks, S8 ran {S8_COUNTS[tool]}")
        # the registry's oracle_properties are the properties the oracle's layers map gives each milestone
        layers = json.loads((TESTS / "oracle" / "europe.json").read_text(encoding="utf-8")).get("layers") or {}
        for s in registry_upto(ctx.slice):
            owned = sorted(k for k, v in layers.items() if v == s["id"])
            if sorted(s.get("oracle_properties", [])) != owned:
                fails.append(f"REGISTRY {s['id']} oracle_properties {sorted(s.get('oracle_properties', []))}, the oracle's "
                             f"layers map gives it {owned}")
        return meas, fails, "S8 offline self-tests " + " + ".join(str(meas.get(t)) for t in S8_COUNTS) + \
               f" checks; oracle data {meas.get('oracle-validate')} checks; perf {meas.get('perf')}"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- runner positive controls

def suite_evidence(ctx_like, slice_id, manifest, expected_keys, derive_fns):
    """Rule 2 for suite evidence: a key mismatch fails at once with the exact refresh command; a
    match re-validates the raw outputs and re-derives the verdict (a manifest's own verdict, if any,
    is ignored)."""
    fails, results = [], {}
    checks = (manifest or {}).get("checks", {})
    for name, want_key in expected_keys.items():
        ent = checks.get(name)
        cmd = f"python tools/earth_test.py suite {slice_id} --only {name}"
        if not ent:
            fails.append(f"suite evidence for {name} is missing: run {cmd}")
            continue
        if ent.get("key") != want_key:
            fails.append(f"suite evidence for {name} is stale (key {str(ent.get('key'))[:12]} != {want_key[:12]}): "
                         f"run {cmd}")
            continue
        dirs = [abs_ws(ctx_like, d) for d in ent.get("run_dirs", [])]
        try:
            meas, f, detail = derive_fns[name](dirs)
        except Exception as e:
            meas, f, detail = {}, [f"re-derivation crashed: {type(e).__name__}: {e}"], ""
        results[name] = (meas, f, detail)
        fails += [f"{name}: {x}" for x in f]
    return fails, results


def section6_controls(main):
    """Section 6 read from main's plan: every section 20 milestone parses (each later milestone's bar is read
    by this runner, never by code the milestone writes itself), TBD-P4 fails only where it is in force,
    and the per-map and per-modset cells read as the plan states them."""
    out = {}
    order = plan_slice_order(main)
    bad = []
    for sid in order:
        try:
            parse_section6(main, sid)
        except GateError as e:
            bad.append(f"{sid}: {e}")
    out["section 6 parses for every section 20 slice"] = (not bad and len(order) > 1, bad[:2])
    p10 = re.search(r"^\| P10 \| [^|]+\| ([^|]+) \|", main, re.M)
    tbd = main.replace(p10.group(0), p10.group(0).replace(p10.group(1), "TBD-P4 ")) if p10 else main
    try:
        parse_section6(tbd, "toolchain")
        out["TBD-P4 in an enforced row fails"] = (False, "parsed")
    except GateError:
        out["TBD-P4 in an enforced row fails"] = (True, "")
    p1 = re.search(r"^\| P1 \| [^|]+\| ([^|]+) \|", main, re.M)
    later = main.replace(p1.group(0), p1.group(0).replace(p1.group(1), "TBD-P4 ")) if p1 else main
    try:
        parse_section6(later, "toolchain")
        out["TBD-P4 in a row not yet enforced does not fail toolchain"] = (True, "")
    except GateError as e:
        out["TBD-P4 in a row not yet enforced does not fail toolchain"] = (False, str(e))
    try:
        parse_section6(later, "europe-coast")
        out["TBD-P4 in P1 fails europe-coast, which enforces it"] = (False, "parsed")
    except GateError:
        out["TBD-P4 in P1 fails europe-coast, which enforces it"] = (True, "")
    junk = main.replace("| `ridges` | 0 |", "| `ridges` | about 0 |", 1)
    try:
        parse_section6(junk, "toolchain")
        out["an unreadable later 6.3 cell fails closed"] = (False, "parsed")
    except GateError:
        out["an unreadable later 6.3 cell fails closed"] = (True, "")
    tc = parse_section6(main, "toolchain")
    p3 = tc["limits"].get("P3") or {}
    out["P3 (its From names no slice) is in force from the first section 20 slice, at 1.5"] = (
        p3.get("from") == plan_slice_order(main)[0] and p3.get("limit", {}).get("max") == 1.5, p3.get("from"))
    out["every 6.2 row in force through toolchain has an enforcing check"] = (not unenforced_limits(tc),
                                                                               unenforced_limits(tc))
    ec = parse_section6(main, "europe-coast")
    out["a row in force with no enforcing check fails closed (europe-coast's P1 before its consumer lands)"] = (
        "P1" in unenforced_limits(ec), unenforced_limits(ec)[:3])
    noslice = re.sub(r"^(\| P18 \| [^|]+\| [^|]+ \| )`toolchain`", r"\1suites", main, count=1, flags=re.M)
    try:
        ns = parse_section6(noslice, "toolchain")
        out["a From cell naming no slice reads as in force from the first slice"] = (
            "P18" in ns["limits"] and "P18" in ns["from_first_slice"], ns["from_first_slice"])
    except GateError as e:
        out["a From cell naming no slice reads as in force from the first slice"] = (False, str(e))
    try:
        r = parse_section6(main, "release")
        A = r["all_allocations"]

        def v(sid, prog, ms, mk, var=None):
            a = alloc_for(A[sid][prog], ms, mk, var)
            if a["kind"] == "headroom":
                return ("headroom", headroom_limit(r, sid, prog, ms, mk, a["limit"]))
            return (a["kind"], a.get("value"))
        want = {("climate-tiles", "tile", "M1", "europe"): ("add", 1500.0),
                ("climate-tiles", "tile", "M1", "atlantic"): ("add", 2300.0),
                ("climate-tiles", "tile", "M2", "europe"): ("cap", None),
                ("trees-forests", "entity", "M2", "atlantic"): ("add", 9400.0),
                ("olde-world-atlantic", "tile", "M1", "europe"): ("add", 0.0),
                ("olde-world-atlantic", "tile", "M1", "olde_world"): ("cap", None),
                ("olde-world-atlantic", "time", "M1", "atlantic"): ("first", None),
                ("waterways", "tile", "M1", "europe"): ("headroom", 114300.0),
                ("resources-enemies", "tile", "M1", "olde_world"): ("add", 500.0),
                ("destroyed-europe", "tile", "M1", "europe"): ("add", 0.0),
                ("coast-band-fix", "entity", "M1", "europe"): ("add", 0.0),
                ("toolchain", "entity", "M1", "europe"): ("add", 0.0),
                ("toolchain", "time", "M1", "europe"): ("none", None)}
        got = {k: v(*k) for k in want}
        got[("destroyed-europe", "tile", "M2 key on", "europe")] = v("destroyed-europe", "tile", "M2", "europe", "key on")
        want[("destroyed-europe", "tile", "M2 key on", "europe")] = ("add", 2700.0)
        diff = [f"{k}: {got[k]} != {w}" for k, w in want.items() if got[k] != w]
        out["6.3 cells read per map and modset as the plan states them"] = (not diff, diff[:3])
        per = r["all_limits"]["P12"]["limit"].get("per_map")
        out["P12 binds its three values to Europe, Atlantic and Old World"] = (
            per == {"europe": 15000.0, "atlantic": 20000.0, "olde_world": 19000.0}, per)
    except GateError as e:
        out["6.3 cells read per map and modset as the plan states them"] = (False, str(e))
    return out


def t15a_controls(main):
    """T15a's checker on fixture rows that must fail or pass, with section 6 read through
    climate-tiles (P10 to P14 all in force) and a fixture allocation."""
    out = {}
    r = parse_section6(main, "climate-tiles")
    fake = dict(r, allocations=dict(r["allocations"], fixture={
        "tile": {"cell": "cap", "rules": [{"modset": None, "maps": ["europe", "atlantic", "olde_world"],
                                           "variant": None, "kind": "cap"}]},
        "entity": {"cell": "+400", "rules": [{"modset": None, "maps": ["europe", "atlantic", "olde_world"],
                                              "variant": None, "kind": "add", "value": 400.0}]},
        "cliff": {"cell": "0", "rules": []}, "time": {"cell": "first", "rules": []}}))

    def prog(t, e, c):
        return {"tile": {"complexity": t}, "entity": {"complexity": e}, "cliff": {"complexity": c}}
    van = {"row": "vanilla", "map": None, "modset": "M0", "programs": prog(VANILLA["tile"], VANILLA["entity"],
                                                                         VANILLA["cliff"])}
    bab = {"row": "bab", "map": None, "modset": "M2", "programs": prog(20000, 14800, 287)}

    def row_(mk, ms, t, e, c=287):
        return {"row": "map", "map": mk, "modset": ms, "scale": 6, "toggles": "on", "programs": prog(t, e, c)}

    def chk(rows, sec=fake, through="fixture"):
        return check_t15a(rows, sec, [], through)
    ent = VANILLA["entity"]
    out["T15a: an M1 Tile row over P10 fails"] = bool(chk([van, row_("europe", "M1", 116001, ent)]))
    out["T15a: an M2 Tile row between P10 and P11 passes (P10 binds M1 only)"] = not chk(
        [van, bab, row_("europe", "M2", 150000, 14900)])
    out["T15a: an M2 Tile row over P11 fails"] = bool(chk([van, bab, row_("europe", "M2", 180001, 14900)]))
    out["T15a: an M1 Entity row over P12 fails even within the allocation"] = bool(chk(
        [van, row_("europe", "M1", 90000, 15150)], dict(fake, allocations=dict(fake["allocations"], fixture=dict(
            fake["allocations"]["fixture"], entity={"cell": "cap", "rules": [
                {"modset": None, "maps": ["europe"], "variant": None, "kind": "cap"}]})))))
    capall = dict(fake, allocations=dict(fake["allocations"], fixture=dict(fake["allocations"]["fixture"], entity={
        "cell": "cap", "rules": [{"modset": None, "maps": ["europe", "atlantic", "olde_world"], "variant": None,
                                  "kind": "cap"}]})))
    out["T15a: P12 is per map (Atlantic 19,500 passes, Old World 19,500 fails)"] = (
        not chk([van, row_("atlantic", "M1", 90000, 19500)], capall) and
        bool(chk([van, row_("olde_world", "M1", 90000, 19500)], capall)))
    out["T15a: an M2 Entity row over P13 fails"] = bool(chk([van, bab, row_("europe", "M2", 150000, 28001)], capall))
    out["T15a: Entity growth over the slice's allocation fails"] = bool(chk([van, row_("europe", "M1", 90000, ent + 401)]))
    out["T15a: growth within the allocation passes"] = not chk([van, row_("europe", "M1", 90000, ent + 400)])
    out["T15a: a row equal to its comparator fails (G5)"] = bool(chk(
        [van, row_("europe", "M1", VANILLA["tile"], VANILLA["entity"], VANILLA["cliff"])]))
    out["T15a: an M2 row without its BAB comparator fails (U7)"] = bool(chk([van, row_("europe", "M2", 150000, 14900)]))
    tc = parse_section6(main, "toolchain")
    ph = {"row": "placeholder", "map": "europe", "modset": "M1", "scale": 6, "toggles": "n/a"}
    out["T15a: the placeholder row's Entity growth over toolchain's 0 fails"] = bool(check_t15a(
        [van, dict(ph, programs=prog(10093, ent + 1, VANILLA["cliff"]))], tc, [], "toolchain"))
    out["T15a: the placeholder row's Cliff growth over toolchain's 0 fails"] = bool(check_t15a(
        [van, dict(ph, programs=prog(10093, ent, VANILLA["cliff"] + 1))], tc, [], "toolchain"))
    out["T15a: the placeholder row within toolchain's allocation passes"] = not check_t15a(
        [van, dict(ph, programs=prog(10093, ent, VANILLA["cliff"]))], tc, [], "toolchain")
    return {k: (v, "") for k, v in out.items()}


def _fake_rep_files(run, ms, census, mask, pid=4242, b_census=None):
    """The raw files of one synthetic repetition: run.json passing G1, the timer's force time and
    census, the watcher's set and exit records, the persisted monitor reads and the game log line
    the affinity verdict times the set against."""
    (run / "script-output" / "tq1").mkdir(parents=True)
    (run / "bench").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"exit": 0, "isolated": True, "error_lines": []}), encoding="utf-8")
    (run / "script-output" / "tq1" / "gen.txt").write_text(f"force Duration: {ms}ms\n", encoding="utf-8")
    (run / "script-output" / "tq1" / "gen.json").write_text(json.dumps(census), encoding="utf-8")
    (run / "bench" / "factorio-current.log").write_text("   0.375 Loading map x.zip: 1 bytes.\n", encoding="utf-8")
    t0 = 1793144783559
    hexmask = f"{mask:#X}".replace("0X", "0x")
    (run.parent / f"{run.name}-affinity.jsonl").write_text(
        json.dumps({"event": "set", "pid": pid, "mask": mask, "readback": mask, "threads_outside": 0, "threads": 5,
                    "threads_read": 5, "set_after_start_ms": 20.4, "unix_ms": t0}) + "\n" +
        json.dumps({"event": "exit", "pid": pid, "polls": 8, "process_mask_mismatch_polls": 0, "thread_bad_polls": 0,
                    "last_process_mask": mask, "thread_or_all": hexmask, "max_threads": 76}) + "\n", encoding="utf-8")
    (run.parent / f"{run.name}-monitor.json").write_text(json.dumps(
        {"mask": mask, "load_pre": 5.0, "tasklist_after": [], "root": 1, "ours": [pid], "foreign": [], "max_games": 1,
         "polls": 9, "masks": [[t0 + 100 * k, pid, mask] for k in range(1, 4)]}), encoding="utf-8")


def _fake_reps(root, a_ms, b_ms, census, mask, b_census=None):
    """A synthetic T15b group whose every repetition is valid from its raw files (rep_from_raw), with
    the runner's reps.jsonl beside it; b_census gives config b its own census (an Earth pair)."""
    root.mkdir(parents=True)
    lines = []
    for i, (cfg, ms) in enumerate([("a", v) for v in a_ms] + [("b", v) for v in b_ms], 1):
        run = root / f"r{i:03d}-{cfg}-{mask:x}"
        c = b_census if (cfg == "b" and b_census is not None) else census
        _fake_rep_files(run, ms, c, mask)
        lines.append(json.dumps({"out": str(run), "valid": True, "force_ms": ms, "mask": mask, "census": c}))
    (root / "reps.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def t15b_controls(main):
    """Rule 5 on synthetic repetitions (no game): a borderline ratio on one group is undecided and
    fails, the pooled group decides it, a pooled ratio outside P18 fails, a clear ratio passes on
    one group, and the gate's budget test refuses an extra group that does not fit."""
    import perf
    out = {}
    lim = parse_section6(main, "toolchain")["limits"]
    census = dict((baseline_record().get("t15b_block") or {}).get("census_m0") or {"water_tiles": 1, "trees": 1,
                                                                                     "enemies": 1},
                  block_generated_before=0, block_generated_after=256)
    k16 = f"{perf.MASK16:#x}"
    with tempfile.TemporaryDirectory(prefix="tn-rule5-") as td:
        td = Path(td)
        near = _fake_reps(td / "near", [640.0] * 5, [621.4] * 5, census, perf.MASK16)
        meas, f, _ = derive_t15b([near], lim, 5)
        out["rule 5: a ratio within 0.03 of a P18 bound on one batch is undecided and fails"] = (
            bool(f) and bool((meas.get(k16) or {}).get("undecided")), f[:1])
        extra = _fake_reps(td / "near-x", [640.0] * 7, [621.4] * 7, census, perf.MASK16)
        meas, f, _ = derive_t15b([near, extra], lim, 5)
        out["rule 5: the pooled batch decides a borderline ratio inside P18"] = (
            not f and (meas.get(k16) or {}).get("reps") == [12, 12], f[:1])
        over = _fake_reps(td / "over-x", [640.0] * 7, [600.0] * 7, census, perf.MASK16)
        meas, f, _ = derive_t15b([near, over], lim, 5)
        out["rule 5: a pooled ratio outside P18 fails"] = (bool(f), (meas.get(k16) or {}).get("ratio"))
        short = _fake_reps(td / "short-x", [640.0] * 3, [621.4] * 3, census, perf.MASK16)
        meas, f, _ = derive_t15b([near, short], lim, 5)
        out["rule 5: an extra batch short of 7 reps per config fails"] = (bool(f), f[:1])
        mid = _fake_reps(td / "mid", [640.0] * 5, [638.0] * 5, census, perf.MASK16)
        meas, f, _ = derive_t15b([mid], lim, 5)
        out["rule 5: a ratio clear of both bounds passes on one batch"] = (
            not f and not (meas.get(k16) or {}).get("undecided"), f[:1])
        low = _fake_reps(td / "low", [600.0] * 5, [622.0] * 5, census, perf.MASK16)
        meas, f, _ = derive_t15b([low], lim, 5)
        out["rule 5: a ratio near P18's lower bound is borderline too"] = (
            (meas.get(k16) or {}).get("borderline") == 0.95, (meas.get(k16) or {}).get("ratio"))
        # rule 2: validity comes from the raw outputs, never from the runner's reps.jsonl
        clean = _fake_reps(td / "raw-clean", [640.0] * 5, [638.0] * 5, census, perf.MASK16)
        meas, f, _ = derive_t15b([clean], lim, 5)
        out["rule 2: a batch valid in its raw outputs passes"] = (not f, f[:1])
        tampered = _fake_reps(td / "raw-mask", [640.0] * 5, [638.0] * 5, census, perf.MASK16)
        wf = tampered / "r002-a-ffff-affinity.jsonl"
        wf.write_text(wf.read_text(encoding="utf-8").replace('"readback": 65535', '"readback": 255', 1), encoding="utf-8")
        meas, f, _ = derive_t15b([tampered], lim, 5)
        out["rule 2: a rep logged valid whose mask read back wrong fails"] = (
            any("r002-a-ffff" in x and "valid=False" in x for x in f), f[:1])
        cen = _fake_reps(td / "raw-census", [640.0] * 5, [638.0] * 5, census, perf.MASK16)
        gj = cen / "r003-a-ffff" / "script-output" / "tq1" / "gen.json"
        gj.write_text(json.dumps(dict(census, water_tiles=(census.get("water_tiles") or 0) + 1)), encoding="utf-8")
        meas, f, _ = derive_t15b([cen], lim, 5)
        out["rule 2: a rep logged valid whose raw census differs fails"] = (
            any("r003-a-ffff" in x for x in f), f[:1])
        mon = _fake_reps(td / "raw-monitor", [640.0] * 5, [638.0] * 5, census, perf.MASK16)
        os.replace(mon / "r004-a-ffff-monitor.json", td / "moved-monitor.json")
        meas, f, _ = derive_t15b([mon], lim, 5)
        out["rule 2: a rep without its persisted monitor record fails"] = (any("r004-a-ffff" in x for x in f), f[:1])
        gap = _fake_reps(td / "raw-gap", [640.0] * 6, [638.0] * 5, census, perf.MASK16)
        os.replace(gap / "r006-a-ffff", td / "moved-rep")
        meas, f, _ = derive_t15b([gap], lim, 5)
        out["rule 2: a dropped repetition directory fails"] = (any("without a gap" in x for x in f), f[:1])
        # P3 (in force from the first milestone): an Earth pair's 24 LP ratio meets 1.5 wherever recorded
        earth = dict(census, water_tiles=(census.get("water_tiles") or 0) + 999)
        over3 = _fake_reps(td / "p3-over", [700.0] * 7, [400.0] * 7, earth, MASK24, b_census=census)
        meas, f, _ = derive_t15b([over3], lim, 7, pair="m1_m0", label="M1t/M0t")
        out["P3: an Earth pair's 24 LP ratio over 1.5 fails"] = (any(x.startswith("P3:") for x in f), f[:1])
        ok3 = _fake_reps(td / "p3-ok", [500.0] * 7, [400.0] * 7, earth, MASK24, b_census=census)
        meas, f, _ = derive_t15b([ok3], lim, 7, pair="m1_m0", label="M1t/M0t")
        out["P3: an Earth pair's 24 LP ratio within 1.5 passes"] = (not f, f[:1])
    now = time.time()
    out["rule 5: the gate fails closed when the extra batch does not fit its budget"] = (
        not extra_batch_fits(60.0, 10, 14, now, now + 30)[0] and extra_batch_fits(60.0, 10, 14, now, now + 600)[0], "")
    return out


def guard_controls():
    """The chained G9 guard on scratch chains with a stub fh.py (no game, no live profile)."""
    out = {}

    class Stub:
        def __init__(self, root, cmd, dirty=False):
            self.root, self.cmd, self.slice, self.stamp = Path(root), cmd, "toolchain", time.strftime("%Y%m%d-%H%M%S")
            self.ws = Path(root)
            self.dirty, self.calls = dirty, []

        def fh_plain(self, args, timeout=300):
            self.calls.append([str(a) for a in args])
            if args[0] == "guard" and args[1] == "snapshot":
                Path(args[2]).write_text("{}", encoding="utf-8")
                return f"RESULT ok snapshot files=1 file={args[2]}"
            return "RESULT changed added=0 removed=0 changed=1" if self.dirty else "RESULT ok added=0 removed=0 changed=0"

    def halts(fn):
        try:
            fn()
            return False
        except GateError:
            return True

    def halt_text(fn):
        try:
            fn()
            return ""
        except GateError as e:
            return str(e)

    def game_log(root, inst, ahead=5.0):
        f = Path(root) / "test-instance" / "instances" / inst / "write-data" / "factorio-current.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("log\n", encoding="utf-8")
        t = time.time() + ahead
        os.utime(f, (t, t))
    with tempfile.TemporaryDirectory(prefix="tn-guard-") as td:
        td = Path(td)
        g = Guard(Stub(td / "a", "baseline", dirty=True), 1)
        g.start()
        g.finish()
        msg = halt_text(lambda: Guard(Stub(td / "a", "gate"), 1).start())
        out["G9: a dirty end check halts the next command of the part"] = (bool(msg), "")
        out["G9: the halt says to stop and report on the parent issue, and names no re-baseline command"] = (
            "parent issue" in msg and "guard-rebaseline" not in msg and "earth_test.py" not in msg, msg[-120:])
        # design constraint 1: a game run outside the chained bracket shows in the build instances' logs
        g = Guard(Stub(td / "g", "gate"), 1)
        g.start()
        g.finish()
        game_log(td / "g", "ea-dev")
        out["G9: a build instance's game log written after the chain's last clean end halts the next command"] = (
            halts(lambda: Guard(Stub(td / "g", "gate"), 1).start()), "")
        g = Guard(Stub(td / "h", "gate"), 1)
        g.start()
        g.finish()
        game_log(td / "h", "ea-dev", ahead=-3600.0)
        out["G9: a build instance's log older than the last clean end passes"] = (
            not halts(lambda: Guard(Stub(td / "h", "gate"), 1).start()), "")
        game_log(td / "h", "other-caller")
        out["G9: an instance outside the build's ea- names is not the build's run and passes"] = (
            not halts(lambda: Guard(Stub(td / "h", "gate"), 1).start()), "")
        g = Guard(Stub(td / "i", "suite"), 1)
        g.start()
        g.note_launch("ea-suite")                  # killed after launching on ea-suite: never finishes
        game_log(td / "i", "ea-suite")
        out["G9: after an entry that never finished, its own ledger's instance may hold a newer log"] = (
            not halts(lambda: Guard(Stub(td / "i", "gate"), 1).start()), "")
        g = Guard(Stub(td / "j", "suite"), 1)
        g.start()
        g.note_launch("ea-suite")
        game_log(td / "j", "ea-dev")
        out["G9: after an entry that never finished, an instance outside its ledger halts"] = (
            halts(lambda: Guard(Stub(td / "j", "gate"), 1).start()), "")
        g = Guard(Stub(td / "k", "gate"), 1)
        g.start()
        g.finish()
        game_log(td / "k", "ea-gate")
        out["G9: a part's first command halts on a game log written after the previous part's last clean end"] = (
            halts(lambda: Guard(Stub(td / "k", "gate"), 2).start()), "")
        g = Guard(Stub(td / "b", "suite"), 1)
        g.start()                                   # killed: never finishes
        s2 = Stub(td / "b", "gate")
        Guard(s2, 1).start()
        checks = [c for c in s2.calls if c[1] == "check"]
        out["G9: an unfinished entry is checked against its own start snapshot"] = (
            bool(checks) and checks[0][2].endswith(g.start_file), checks[:1])
        g = Guard(Stub(td / "c", "suite"), 1)
        g.start()
        out["G9: a changed profile after an unfinished entry halts"] = (
            halts(lambda: Guard(Stub(td / "c", "gate", dirty=True), 1).start()), "")
        g = Guard(Stub(td / "d", "gate"), 1)
        g.start()
        g.finish()
        chain = td / "d" / "guard" / "part-1" / "chain.json"
        os.replace(chain, chain.with_name("chain.json.moved"))
        out["G9: a lost chain.json that the journal records halts (no silent re-baseline)"] = (
            halts(lambda: Guard(Stub(td / "d", "gate"), 1).start()), "")
        chain.write_text('{"part": 1, "entr', encoding="utf-8")
        out["G9: a truncated chain.json halts"] = (halts(lambda: Guard(Stub(td / "d", "gate"), 1)), "")
        rb = Guard(Stub(td / "d", "guard-rebaseline"), 1, recover=True)
        rb.rebaseline("control: the chain was set aside")
        ok = not halts(lambda: Guard(Stub(td / "d", "gate"), 1).start())
        out["G9: only the explicit, logged re-baseline clears it"] = (
            ok and any(e.get("event") == "rebaseline" for e in rb.journal_events()), "")
        g = Guard(Stub(td / "e", "gate", dirty=True), 1)
        g.start()
        g.finish()
        out["G9: a part's first command refuses while the previous part's chain ends dirty"] = (
            halts(lambda: Guard(Stub(td / "e", "gate"), 2).start()), "")
        g = Guard(Stub(td / "f", "gate"), 1)
        g.start()
        g.finish()
        out["G9: a part's first command re-baselines after a clean previous part"] = (
            not halts(lambda: Guard(Stub(td / "f", "gate"), 2).start()), "")
    return out


def fatal_run_controls():
    """Design constraint 1: a game run that may have left its instance, or one on another build,
    stops the whole command (no game, no live profile; scratch run directories and a stub
    command). A run.json with isolated false or unknown, a scenario step not isolated, and a
    NOT-ISOLATED or isolated=NO RESULT line are breaches; an isolated run and a launch fh.py refused
    (no run.json) are not. FatalRun is no Exception: fg_rows passes it through and runs no later
    row; Ctx.check_build raises it on another build; with_bracket catches it, terminates the job,
    and only then runs the guard check."""
    import types
    import perf
    out = {}
    with tempfile.TemporaryDirectory(prefix="tn-fatal-") as td:
        td = Path(td)

        def rd(name, meta=None, sub=None):
            d = td / "runs" / name
            w = d if sub is None else d / sub
            w.mkdir(parents=True)
            if meta is not None:
                (w / "run.json").write_text(json.dumps(meta), encoding="utf-8")
            return d
        good = {"exit": 0, "isolated": True, "error_lines": [], "write_data_seen": "x"}
        cases = {
            "fatal: run.json isolated false is a breach": (rd("a", dict(good, isolated=False)), "RESULT fail x", True),
            "fatal: run.json isolated unknown is a breach": (rd("b", dict(good, isolated=None)), "RESULT ok x", True),
            "fatal: a scenario's bench step not isolated is a breach": (
                rd("c", dict(good, bench={"isolated": False})), "RESULT ok x", True),
            "fatal: a failed create step's own run.json not isolated is a breach": (
                rd("d", dict(good, isolated=None), sub="create"), "RESULT fail map creation failed", True),
            "fatal: a fail-NOT-ISOLATED RESULT line alone is a breach": (td / "runs" / "none",
                                                                       "RESULT fail-NOT-ISOLATED exit=0 isolated=NO", True),
            "fatal: an isolated run is no breach": (rd("e", good), "RESULT ok exit=0 isolated=yes errors=0", False),
            "fatal: a launch fh.py refused (no run.json) is no breach": (
                td / "runs" / "refused", "RESULT fail --out already holds files", False),
        }
        for label, (d, res, want) in cases.items():
            why = tnguard.run_breach(d, res)
            out[label] = (bool(why) == want, why or "")
        out["fatal: FatalRun is no Exception, so no `except Exception` swallows it"] = (
            not issubclass(FatalRun, Exception) and not issubclass(FatalRun, GateError), "")

        class RowCtx:
            root, stamp = td / "rows", time.strftime("%Y%m%d-%H%M%S")

            def say(self, line):
                pass
        ran = []

        def boom(ctx, mods, sec6, row, cache):
            raise FatalRun("fixture breach")

        def after(ctx, mods, sec6, row, cache):
            ran.append(True)
        ROW_FUNCS["_fatal_fixture"], ROW_FUNCS["_after_fixture"] = boom, after
        try:
            try:
                fg_rows(RowCtx(), None, None, ["_fatal_fixture", "_after_fixture"], use_cache=False)
                passed = False
            except FatalRun:
                passed = True
        finally:
            ROW_FUNCS.pop("_fatal_fixture", None)
            ROW_FUNCS.pop("_after_fixture", None)
        out["fatal: fg_rows passes FatalRun through and runs no later row"] = (passed and not ran, "")
        b = rd("other-build", {})
        (b / "stdout.txt").write_text("   0.000 Factorio 2.1.99 (build 99999, win64, steam)\n", encoding="utf-8")
        stub = types.SimpleNamespace(build=None, perf=perf, say=lambda line: None)
        try:
            Ctx.check_build(stub, b)
            raised = False
        except FatalRun:
            raised = True
        out["fatal: G8, a run on another build, stops the command"] = (raised, "")

        class BracketCtx:
            def __init__(self, root):
                self.root, self.ws, self.out = root, root, root / "out"
                self.out.mkdir(parents=True)
                self.cmd, self.slice, self.stamp = "gate", "toolchain", time.strftime("%Y%m%d-%H%M%S")
                self.log_lines, self.shared, self.bracket, self.guard, self.calls = [], {}, None, None, []
                self.job = types.SimpleNamespace(terminate=lambda: self.calls.append("terminate"))

            def say(self, line):
                self.log_lines.append(line)

            def fh_plain(self, args, timeout=300):
                self.calls.append(f"{args[0]} {args[1]}")
                if args[0] == "guard" and args[1] == "snapshot":
                    Path(args[2]).write_text("{}", encoding="utf-8")
                    return f"RESULT ok snapshot files=1 file={args[2]}"
                return "RESULT ok added=0 removed=0 changed=0"
        bc = BracketCtx(td / "bracket")

        def body():
            raise FatalRun("fixture breach")
        code = with_bracket(bc, body)
        checks = [i for i, c in enumerate(bc.calls) if c == "guard check"]
        out["fatal: with_bracket catches FatalRun, terminates the job, then runs the guard check"] = (
            code == 1 and any(l.startswith("FATAL ") for l in bc.log_lines) and "terminate" in bc.calls and
            bool(checks) and bc.calls.index("terminate") < checks[-1], bc.calls)
    return out


def oracle_controls():
    """Staged oracle activation on a scratch copy of tests/oracle (no game): an expectation set before
    its owner ships fails, the same once the owner is live passes, and the brief lock holds always."""
    import oracle
    out = {}
    with tempfile.TemporaryDirectory(prefix="tn-oracle-") as td:
        td = Path(td) / "oracle"
        shutil.copytree(TESTS / "oracle", td)
        eu = json.loads((td / "europe.json").read_text(encoding="utf-8"))
        forest = next(p for p in eu["places"] if p["kind"] == "forest")
        forest["expect"]["forest"] = True
        brief = next(p for p in eu["places"] if p.get("origin") == "brief")

        def run(live, places):
            (td / "europe.json").write_text(json.dumps(dict(eu, places=places), indent=1, ensure_ascii=False),
                                            encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                return oracle.validate(live, td)
        upto = [s for s in plan_slice_order(git_show("main:SPRINT-1-PLAN.md") or PLAN.read_text(encoding="utf-8"))]
        before = upto[: upto.index("trees-forests")]
        out["oracle: a forest expectation before trees-forests ships fails"] = (run(before, eu["places"]) != 0, "")
        out["oracle: the same expectation once trees-forests is live passes"] = (
            run(before + ["trees-forests"], eu["places"]) == 0, "")
        forest["expect"]["forest"] = None
        old = brief["expect"]["climate_band"]
        brief["expect"]["climate_band"] = "temperate" if old != "temperate" else "cold"
        out["oracle: a changed brief climate band fails even with every slice live"] = (run(upto, eu["places"]) != 0, "")
        brief["expect"]["climate_band"] = old
    return out


def bracket_controls(ctx):
    """Design constraint 1: every repo tool that launches the game refuses outside the guard bracket.
    Each is started with TN_BRACKET removed (and once with a forged one) and must print its refusal
    before fh.py runs; no game process may appear. Any slip would still sit inside this command's
    own lock and G9 bracket."""
    out = {}
    env = {k: v for k, v in ctx.env().items() if k != tnguard.ENV}
    probe = ctx.out / "bracket-probe"
    runs = {
        "bracket: game_selftest.py refuses outside the bracket": [HERE / "game_selftest.py", "--out-root", probe / "gst"],
        "bracket: dump_render.py run refuses outside the bracket": [
            HERE / "dump_render.py", "run", "--instance", "ea-bracket", "--modset", "ea-m0", "--out", probe / "dump"],
        "bracket: oracle.py probe refuses outside the bracket": [
            HERE / "oracle.py", "probe", "--map", "europe", "--scale", "6", "--names", "elevation", "--instance",
            "ea-bracket", "--modset", "ea-m0", "--out", probe / "probe"],
    }
    forged = dict(env, **{tnguard.ENV: json.dumps(dict(ctx.bracket or {}, token="0" * 32))})
    cases = [(k, v, env) for k, v in runs.items()] + [
        ("bracket: a forged token is refused", runs["bracket: game_selftest.py refuses outside the bracket"], forged),
        ("bracket: the kill probe refuses outside its parent's bracket",
         [HERE / "earth_test.py", "gate", "--through", ctx.slice], dict(env, TN_KILLPROBE="1",
                                                                         TN_LOCK_FILE=str(probe / "x.lock"),
                                                                         TN_OUT_ROOT=str(probe / "root")))]
    for label, args, e in cases:
        before = set(ctx.perf.game_pids())
        cp = subprocess.run([sys.executable] + [str(a) for a in args], cwd=str(ctx.ws), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=e, timeout=120)
        text = cp.stdout + cp.stderr
        new_games = set(ctx.perf.game_pids()) - before
        refused = cp.returncode != 0 and ("refuses to launch the game" in text or "TN_KILLPROBE refused" in text)
        out[label] = (refused and not new_games and not (probe / "gst").exists() and not (probe / "dump").exists(),
                      text.strip().splitlines()[-1:] if text.strip() else [])
    return out


def rebaseline_controls(ctx):
    """The guard's re-baseline is left to the maintainer: started the way an unattended job or a script
    starts it (stdin and stdout are pipes), guard-rebaseline must refuse at once, before it takes
    the lock or writes the chain or the journal; the terminal test itself accepts only a console."""
    out = {}
    part = slice_entry(ctx.slice)["part"]
    files = [ctx.root / "guard" / f"part-{part}" / "chain.json", ctx.root / "guard" / "journal.jsonl"]

    def state():
        return [(p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in files]
    before, t0 = state(), time.time()
    cp = subprocess.run([sys.executable, str(HERE / "earth_test.py"), "guard-rebaseline", "--reason", "control"],
                        cwd=str(REPO), stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=90, env=ctx.env())
    text = (cp.stdout or "") + (cp.stderr or "")
    out["guard-rebaseline refuses an unattended start at once and changes nothing"] = (
        cp.returncode != 0 and "interactive terminal" in text and time.time() - t0 < 60 and state() == before,
        text.strip().splitlines()[-1:] if text.strip() else [])

    class Term:
        def __init__(self, tty):
            self.tty = tty

        def isatty(self):
            return self.tty
    out["the operator test accepts a console and refuses pipes"] = (
        operator_problem(Term(True), Term(True)) is None and operator_problem(Term(False), Term(True)) is not None and
        operator_problem(Term(True), Term(False)) is not None, "")
    out["GUARD_STOP names no command"] = ("earth_test.py" not in GUARD_STOP and "guard-rebaseline" not in GUARD_STOP, "")
    return out


def slice_id_controls():
    """A crafted milestone id never reaches the file system: gate and suite refuse it before any path is
    built (Ctx validates it first; guard-rebaseline's --milestone goes through the same check behind its
    terminal test), so nothing appears in a scratch workspace."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="tn-sliceid-") as td:
        ws = Path(td) / "ws"
        (ws / "tools").mkdir(parents=True)
        (ws / "tools" / "fh.py").write_text("raise SystemExit('the slice-id control never runs fh.py')\n",
                                            encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != tnguard.ENV}
        env["FACTORIO_WS"] = str(ws)
        crafted_id = "x/../../../outside/mods/evil"
        cases = {"gate --through with ..": ["gate", "--through", crafted_id],
                 "suite with ..": ["suite", crafted_id],
                 "suite with an absolute path": ["suite", str(Path(td) / "abs")],
                 "suite with upper case": ["suite", "Toolchain"],
                 "gate --through an unknown id": ["gate", "--through", "no-such-slice"]}
        for label, args in cases.items():
            cp = subprocess.run([sys.executable, str(HERE / "earth_test.py")] + args, cwd=str(REPO), env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=90)
            made = sorted(p.relative_to(td).as_posix() for p in Path(td).rglob("*")
                          if p.relative_to(td).as_posix() not in ("ws", "ws/tools", "ws/tools/fh.py"))
            out[f"slice id: {label} is refused before any path is built"] = (
                cp.returncode != 0 and "RESULT fail" in (cp.stdout or "") and not made, made[:3])
    return out


def row_runner_controls(ctx, mods, sec6, row, cache):
    results = {}
    with tempfile.TemporaryDirectory(prefix="tn-runner-controls-") as td:
        td = Path(td)

        class FakeCtx:
            ws = td

        bad_run = td / "runs" / "fixture-check"
        bad_run.mkdir(parents=True)
        (bad_run / "run.json").write_text(json.dumps({"exit": 1, "isolated": True, "error_lines": ["Error: fixture"]}),
                                          encoding="utf-8")
        derive = {"fixture": lambda dirs: ({}, sum((g1(d) for d in dirs), []), "")}
        man = {"checks": {"fixture": {"key": "k1", "run_dirs": ["runs/fixture-check"], "verdict": "pass"}}}
        f, _ = suite_evidence(FakeCtx, ctx.slice, man, {"fixture": "k1"}, derive)
        results["manifest calling a failing check passed fails"] = (bool(f), "")
        f, _ = suite_evidence(FakeCtx, ctx.slice, man, {"fixture": "k2"}, derive)
        want = f"python tools/earth_test.py suite {ctx.slice} --only fixture"
        results["stale key prints the exact suite --only command"] = (bool(f) and want in f[0], f[:1])
    main = git_show("main:SPRINT-1-PLAN.md") or PLAN.read_text(encoding="utf-8")
    results["working-tree plan differing from main fails"] = (bool(plan_matches_main(main + "\n<!-- edit -->\n", main)),
                                                              "")
    for group in (section6_controls, t15a_controls, t15b_controls):
        try:
            results.update(group(main))
        except Exception as e:
            results[f"{group.__name__} ran"] = (False, f"{type(e).__name__}: {e}")
    for group in (guard_controls, fatal_run_controls, oracle_controls, gst_replay_controls):
        try:
            results.update(group())
        except Exception as e:
            results[f"{group.__name__} ran"] = (False, f"{type(e).__name__}: {e}")
    if ctx.killprobe:
        results["bracket controls skipped inside the kill probe"] = (True, "")
    else:
        for group in (bracket_controls, rebaseline_controls):
            try:
                results.update(group(ctx))
            except Exception as e:
                results[f"{group.__name__} ran"] = (False, f"{type(e).__name__}: {e}")
        try:
            results.update(slice_id_controls())
        except Exception as e:
            results["slice_id_controls ran"] = (False, f"{type(e).__name__}: {e}")
    ok, kdetail = kill_control(ctx)
    results["killed gate leaves no game process and a free lock"] = (ok, kdetail)
    for k, (ok, detail) in results.items():
        if not ok:
            row.fails.append(f"positive control did not behave: {k} {detail if detail else ''}".rstrip())
    row.detail = f"{sum(1 for ok, _ in results.values() if ok)} of {len(results)} runner controls behaved; kill: {kdetail}"


def kill_control(ctx):
    """Start a fixture gate that launches a long game run through fh.py, hard-kill it the moment its
    game process appears, then require no game process and a free (dead-owner) lock."""
    if ctx.killprobe:
        return True, "skipped inside the kill probe"
    perf = ctx.perf
    if perf.game_pids():
        return False, "a game process is already running"
    td = ctx.out / "kill-probe"
    td.mkdir(parents=True)
    lock = td / "fixture.lock"
    env = ctx.env()
    env.update({"TN_KILLPROBE": "1", "TN_LOCK_FILE": str(lock), "TN_OUT_ROOT": str(td / "root")})
    if ctx.guard is not None:
        ctx.guard.note_launch(KILLPROBE_INSTANCE)
    p = ctx.job.popen([sys.executable, str(HERE / "earth_test.py"), "gate", "--through", ctx.slice], cwd=str(REPO),
                      stdout=open(td / "probe.txt", "w", encoding="utf-8"), stderr=subprocess.STDOUT, env=env)
    t0 = time.time()
    game = None
    while time.time() - t0 < 120:
        if p.poll() is not None:
            break
        procs = perf.processes()
        parent = {pid: ppid for pid, ppid, _ in procs}
        for pid, _, name in procs:
            if name.lower() == perf.GAME_IMAGE:
                q, hops = parent.get(pid), 0
                while q and hops < 12:
                    if q == p.pid:
                        game = pid
                        break
                    q, hops = parent.get(q), hops + 1
        if game:
            break
        time.sleep(0.05)
    if not game:
        p.kill()
        return False, f"the probe gate never started a game process (exit {p.poll()})"
    lock_before = Lock.read(lock) or {}
    perf.terminate_pid(p.pid)
    p.wait(30)
    t1 = time.time()
    while time.time() - t1 < 20 and perf.game_pids():
        time.sleep(0.25)
    left = perf.game_pids()
    free = Lock.is_free(lock)
    ok = not left and free and lock_before.get("pid") == p.pid
    return ok, (f"probe pid {p.pid} held the fixture lock, its game pid {game} was running; after a hard kill "
                f"{len(left)} game processes remain and the lock is {'free' if free else 'HELD'}")


def killprobe_gate(ctx):
    """Inside the kill control's child: its parent gate holds the workspace lock and an open guard
    entry (Ctx verified TN_BRACKET), so the long game run sits inside that bracket; take the
    fixture lock and start the run."""
    why = tnguard.live_output_problem(os.environ["TN_LOCK_FILE"])
    if why:
        raise GateError(f"TN_LOCK_FILE refused: {why}")
    lock = Lock(tnguard.absolute_output(os.environ["TN_LOCK_FILE"]))
    lock.acquire("killprobe gate", wait_s=5)
    mods = Mods(ctx)
    m0 = mods.m0()
    ctx.fh(["preview", "--instance", KILLPROBE_INSTANCE, "--modset", m0, "--seed", str(SEED), "--size", "4096", "--",
            "--threads", "1"], ctx.out / "long-preview", timeout=300)
    return 1


# -- step 2: dumps and dump facts

def row_dumps(ctx, mods, sec6, row, cache):
    cfg = mods.cfg
    m0 = mods.m0()
    m1 = mods.m1()
    r0 = mods.prepare(m0, "m0")
    r1 = mods.prepare(m1, "m1")
    row.run_dirs = [r0.out, r1.out]
    row.fails += g2(r1.out, [cfg["identity"]["id"], "base"]) + g2(r0.out, ["base"])
    log = (r1.out / "factorio-current.log").read_text(encoding="utf-8", errors="replace") + stdout_of(r1.out)
    if "Mod package read error" in log:
        row.fails.append("the load log holds 'Mod package read error' (zip row)")
    sd = json.loads((r1.out / "mod-settings-dump.json").read_text(encoding="utf-8"))
    got = {n: s for group in sd.values() if isinstance(group, dict) for n, s in group.items()}
    rules = json.loads((TESTS / "design-rules.json").read_text(encoding="utf-8"))["settings"]
    for key, want in rules.items():
        s = cfg["settings"][key]
        g = got.get(s["name"], {})
        for field in ("default_value", "setting_type", "allowed_values", "type"):
            if field in want and g.get(field) != want[field]:
                row.fails.append(f"dumped setting {s['name']} {field} {g.get(field)!r}, APPROVALS 1a {want[field]!r}")
    for n in got:
        if n.startswith(cfg["identity"]["setting_prefix"]) and n not in {s["name"] for s in cfg["settings"].values()}:
            row.fails.append(f"dumped setting {n} is not defined in config.lua")
    ctx.shared["dump_m0"] = json.loads((r0.out / "data-raw-dump.json").read_text(encoding="utf-8"))
    ctx.shared["dump_m1"] = json.loads((r1.out / "data-raw-dump.json").read_text(encoding="utf-8"))
    ctx.shared["dump_m1_sha"] = sha256_file(r1.out / "data-raw-dump.json")
    ctx.shared["m0"], ctx.shared["m1"] = m0, m1
    row.detail = (f"M0 {m0} and M1 {m1} dump-data pass G1 to G3; settings dump equals APPROVALS 1a for "
                  f"{sorted(rules)}; settings written explicitly (G7)")


def row_t13_dump_facts(ctx, mods, sec6, row, cache):
    cfg = mods.cfg
    d0, d1 = ctx.shared.get("dump_m0"), ctx.shared.get("dump_m1")
    if d0 is None or d1 is None:
        row.fails.append("no M0 and M1 dumps (row dumps failed)")
        return
    schema = tnconfig.schema_problems(cfg)
    if schema:
        row.fails += [f"config.lua schema: {x}" for x in schema]
        return
    names = tnconfig.defined_names(cfg)
    earth_noise = names["noise"]
    pname = placeholder_preset(cfg)
    presets = d1["map-gen-presets"]["default"]
    p = presets.get(pname)
    ph = cfg["placeholder"]
    if not p:
        row.fails.append(f"preset {pname} is missing from the dump")
    else:
        want_pen = {k: ph["names"][k] for k in ph["keys"]}
        got_pen = (p.get("basic_settings") or {}).get("property_expression_names")
        if got_pen != want_pen:
            row.fails.append(f"preset {pname} property_expression_names {got_pen}, want {want_pen}")
        order = p.get("order", "")
        if not ("a" < order < "b"):
            row.fails.append(f"preset order {order!r} does not sort right after Default and before Rich resources")
    # every Terra Nauvis preset's redirects: a value is a number (nothing to define or read) or a
    # defined noise expression that never reads the property it replaces, directly, through var()
    # (a property-keyed name such as entity:<ore>:probability) or through any name it reads (A-3)
    for pn in earth_presets(cfg):
        pen = preset_pen(d1, pn)
        graph = NoiseGraph(d1, pen)
        for k, target in sorted(pen.items()):
            if redirect_constant(target):
                continue
            if not isinstance(target, str):
                row.fails.append(f"{pn}: preset key {k} holds {target!r}: a redirect value is a noise expression name "
                                 f"or a number")
                continue
            if d1["noise-expression"].get(target) is None:
                row.fails.append(f"{pn}: preset key {k} names {target}, which the dump lacks")
                continue
            loop = graph.reads_property(target, k)
            if loop:
                row.fails.append(f"{pn}: redirect target {target} reads the property {k} it replaces (A-3): "
                                 f"{' > '.join(loop[-6:])}")
    added, changed = [], []
    for t, protos in d1.items():
        if not isinstance(protos, dict):
            continue
        base = d0.get(t, {}) if isinstance(d0.get(t), dict) else {}
        for n, v in protos.items():
            if n not in base:
                added.append((t, n))
            elif v != base[n] and not (t == "map-gen-presets" and n == "default"):
                changed.append((t, n))
    if changed:
        row.fails.append(f"Earth changed vanilla prototypes {changed[:5]} (A-1: default worlds stay vanilla)")
    for t, n in added:
        if t == "noise-expression" or t == "noise-function":
            if n not in earth_noise:
                row.fails.append(f"{t} {n} is not a name config.lua defines")
        else:
            row.fails.append(f"Earth added a {t} prototype {n} (only noise bodies and presets in this slice; D1)")
    base_presets = set(d0["map-gen-presets"]["default"])
    extra = set(presets) - base_presets
    if extra - names["preset"]:
        row.fails.append(f"presets {sorted(extra - names['preset'])} are not config's")
    for n in earth_noise:
        b = d1["noise-expression"].get(n)
        if b and b.get("intended_property"):
            row.fails.append(f"{n} carries intended_property (Map type entries arrive with europe-coast)")
    exprs = {n: (d1["noise-expression"].get(n) or {}).get("expression") for n in earth_noise}
    toggles = [t["preset_key"] for t in tnconfig.toggles(cfg)]
    row.fails += tn_static.toggle_multiply_findings(exprs, toggles)
    row.detail = (f"preset {pname} order {p.get('order') if p else None} redirects {sorted((p or {}).get('basic_settings', {}).get('property_expression_names', {}))}; "
                  f"{len(added)} added prototypes, all Earth names; no vanilla prototype changed")


def row_isolation_b(ctx, mods, sec6, row, cache):
    """Isolation check (b), design constraint 3: the static walk of the M1 dump from every Entity,
    decorative and Cliff root reaches no firewall name on any Terra Nauvis preset, and it follows
    the preset's redirects (it reaches the start mask the preset names). Positive controls, on the
    test-only presets of that modset's dump: on LEAK_FIXTURE (the fine field without the start
    mask) the walk must report vanilla's starting-ore mask reaching the fine field; on
    LEAK_FIXTURE_PROPS (the start mask redirected, plus an entity and a decorative autoplace key
    redirected to bodies that read the fine field) it must report both keys reaching it, which a
    walk of the prototypes' own autoplace text would miss."""
    cfg = mods.cfg
    d1 = ctx.shared.get("dump_m1")
    if d1 is None:
        row.fails.append("no M1 dump")
        return
    fw = set(firewall_names(cfg))
    report, parts = {}, []
    for pname in earth_presets(cfg):
        pen = preset_pen(d1, pname)
        if not pen:
            row.fails.append(f"preset {pname} is missing from the dump or redirects nothing")
            continue
        rep = walk_roots(d1, pen, fw)
        report[pname] = rep
        for g in ("entity", "decorative", "cliff"):
            if rep[g]["hits"]:
                row.fails.append(f"{pname}: {g} roots reach the firewall in {rep[g]['hits']} paths, e.g. "
                                 f"{' > '.join(rep[g]['example'][-5:])} (sacred constraint 3)")
        mask = pen.get(START_MASK_KEY)
        if not mask:
            row.fails.append(f"{pname} does not redirect {START_MASK_KEY}: vanilla starting ore would read its "
                             f"elevation (sacred constraint 3)")
        elif mask not in rep["entity"]["reached"]:
            row.fails.append(f"the walk never reached {pname}'s start mask {mask}: it did not follow the redirect")
        parts.append(f"{pname}: Entity {rep['entity']['roots']} roots, decorative {rep['decorative']['roots']}, "
                     f"Cliff {rep['cliff']['roots']}: 0 firewall paths" if not any(rep[g]["hits"] for g in rep)
                     else f"{pname}: firewall reached")
    fx = leak_fixture(ctx, mods)
    rf = mods.prepare(fx["modset"], "m1f")
    df = json.loads((rf.out / "data-raw-dump.json").read_text(encoding="utf-8"))
    got = preset_pen(df, LEAK_FIXTURE)
    if got != fx["start"]:
        row.fails.append(f"the leak fixture preset redirects {got}, staged {fx['start']}")
    rf_rep = walk_roots(df, got, fw)
    report[LEAK_FIXTURE] = rf_rep
    mask_paths = [p for p in rf_rep["entity"]["paths"] if any(START_MASK_KEY in str(x) for x in p)]
    ex = mask_paths[0] if mask_paths else []
    if not mask_paths:
        row.fails.append("positive control: on the leak fixture preset the walk did not report the fine field "
                         f"reaching the Entity program through {START_MASK_KEY}: the check could not fail")
    got_p = preset_pen(df, LEAK_FIXTURE_PROPS)
    if got_p != fx["props"]:
        row.fails.append(f"the property-key fixture preset redirects {got_p}, staged {fx['props']}")
    rp = walk_roots(df, got_p, fw)
    report[LEAK_FIXTURE_PROPS] = rp
    prop_parts = []
    for g, k in sorted(fx["keys"].items()):
        via = [p for p in rp[g]["paths"] if any(str(x).startswith(f"{k}->(preset) ") for x in p)]
        if not via:
            row.fails.append(f"positive control: on {LEAK_FIXTURE_PROPS} the walk did not follow the redirected {g} "
                             f"key {k} to the fine field: a property-keyed redirect would pass unseen")
        else:
            prop_parts.append(" > ".join(via[0][-3:]))
    if any(START_MASK_KEY in str(x) for p in rp["entity"]["paths"] for x in p):
        row.fails.append(f"{LEAK_FIXTURE_PROPS} redirects the start mask, yet the walk reached the fine field through "
                         f"{START_MASK_KEY}")
    (ctx.out / "isolation-b.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    ctx.shared["isolation_b"] = report
    row.run_dirs = [rf.out]
    row.detail = ("; ".join(parts) + f"; control {LEAK_FIXTURE}: {rf_rep['entity']['hits']} Entity paths, e.g. "
                  f"{' > '.join(ex[-4:])}; control {LEAK_FIXTURE_PROPS}: {'; '.join(prop_parts)}")


# The hard dependencies of the live mods a row copies in (Alien Biomes needs its graphics library).
LIVE_DEPS = {"alien-biomes": ["alien-biomes-graphics"]}


AB_GAP = ("from europe-coast until climate-tiles the real Terra Nauvis presets are defined beside Alien Biomes and "
          "AB's palms read their elevation entry, the fine field, in the Entity program: that leak is outside the "
          "gate until climate-tiles ships the palm switch and the M2 isolation checks (ARCHITECTURE S-3; plan "
          "reconciliation 9)")


def row_ab_placeholder(ctx, mods, sec6, row, cache):
    """Design constraint 3 on the placeholder preset beside Alien Biomes: AB 0.8.0's palms
    (tree-palm-a, tree-palm-b) read elevation in the Entity program, and the placeholder preset
    redirects elevation to the fine field, so presets.lua withholds every preset config.lua marks
    placeholder whenever a mod of placeholder.withheld_with is loaded. On M1 plus the live AB copy
    (fh.py modset --from-live): G1 to G3 on dump-data, and no placeholder preset in the dump (the
    row speaks only for presets marked placeholder: the real presets are meant to exist beside AB).
    Positive control: the same dump walked with the placeholder's own redirects must reach the fine
    field from an Entity root (the palm path), so withholding the preset is what keeps the
    constraint, and the check would see a preset that slipped through.

    The row retires with the placeholder: from europe-coast, which removes it, config.lua marks no
    placeholder preset and the row passes with that noted, and the AB palm leak on the real presets
    stays outside the gate until climate-tiles (AB_GAP)."""
    cfg = mods.cfg
    ph = cfg.get("placeholder") or {}
    marked = placeholder_presets(cfg)
    if not ph and not marked:
        row.detail = f"retired: config.lua marks no placeholder preset (europe-coast removed it); {AB_GAP}"
        return
    if not ph or not marked or placeholder_preset(cfg) not in marked:
        row.fails.append(f"config.lua's placeholder group and the presets it marks placeholder ({marked}) disagree: "
                         f"the row cannot tell which preset to withhold beside Alien Biomes")
        return
    wanted = list(ph.get("withheld_with") or [])
    if not wanted:
        row.detail = "config.lua withholds the placeholder preset beside no mod"
        row.fails.append("placeholder.withheld_with is empty: nothing withholds the placeholder preset beside "
                         "Alien Biomes, whose palms read elevation (sacred constraint 3)")
        return
    live = list(dict.fromkeys(wanted + [d for m in wanted for d in LIVE_DEPS.get(m, [])]))
    m1ab = mods.with_live("m1ab", live)
    key, newest = common_key(ctx, "ab_placeholder", {"m1ab": mods.manifest(m1ab), "live": live, "marked": marked})

    def live_run():
        r = mods.prepare(m1ab, "m1ab")
        return [r.out]

    def derive(dirs):
        d = dirs[0]
        fails = g1(d) + g3(d) + g2(d, [cfg["identity"]["id"]] + live)
        dump = json.loads((Path(d) / "data-raw-dump.json").read_text(encoding="utf-8"))
        present = [p for p in marked if p in ((dump.get("map-gen-presets") or {}).get("default") or {})]
        if present:
            fails.append(f"with {wanted} loaded the dump still holds the placeholder presets {present}: presets.lua "
                         f"must withhold every preset marked placeholder while a mod of placeholder.withheld_with is "
                         f"loaded, since AB's palms read the placeholder's elevation, the fine field (sacred "
                         f"constraint 3); the real presets are not withheld")
        pen = {k: ph["names"][k] for k in ph["keys"]}
        rep = walk_roots(dump, pen, set(firewall_names(cfg)))
        hits = rep["entity"]["hits"] + rep["decorative"]["hits"] + rep["cliff"]["hits"]
        ex = rep["entity"]["example"] or rep["decorative"]["example"] or []
        if not hits:
            fails.append("positive control: with the placeholder's redirects the AB dump reaches no firewall name; "
                         "the check could not tell a withheld preset from a harmless one (has AB changed?)")
        meas = {"placeholder_presets_with_ab": present, "control_paths": hits, "control_example": ex[-4:]}
        return meas, fails, (f"with {', '.join(live)} (live copies) no placeholder preset ({', '.join(marked)}) is "
                             f"defined; control: the placeholder's redirects would reach the fine field in {hits} "
                             f"paths, e.g. {' > '.join(ex[-4:])}; the row retires with the placeholder in europe-coast")

    cached_or_live(ctx, row, cache, key, newest, live_run, derive)


# -- step 3: zero cost, placeholder preview, scenario

def preview(ctx, modset, label, size, preset=None, seed=SEED, verbose=False, mgs=None):
    args = ["preview", "--instance", ctx.instance, "--modset", modset, "--seed", str(seed), "--size", str(size)]
    if mgs:
        args += ["--map-gen-settings", mgs]
    extra = []
    if verbose:
        extra.append("--verbose")
    if preset:
        extra += ["--preset", preset]
    if extra:
        args += ["--"] + extra
    return ctx.fh(args, ctx.out / label)


def derive_preview(d, seeds=1):
    """A preview run's images and complexity; G4: exactly one image per seed rendered."""
    rj = load_run_json(d) or {}
    images = rj.get("images") or {}
    if len(images) != seeds:
        raise GateError(f"{d}: {len(images)} images for {seeds} seed(s) (G4)")
    return {"images": images, "complexity": ctx_complexity(d)}


def ctx_complexity(d):
    import perf
    return perf.parse_complexity((Path(d) / "stdout.txt").read_text(encoding="utf-8", errors="replace")) \
        if (Path(d) / "stdout.txt").exists() else {}


def baseline_record():
    f = BASELINES / f"build-{GAME_BUILD}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def row_t13_zero_cost(ctx, mods, sec6, row, cache):
    m0, m1 = ctx.shared["m0"], ctx.shared["m1"]
    key, newest = common_key(ctx, "t13_zero_cost", {"m1": mods.manifest(m1), "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        return [preview(ctx, m0, "zc-m0-256", 256).out, preview(ctx, m1, "zc-m1-256", 256).out,
                preview(ctx, m0, "zc-m0-64v", 64, verbose=True).out, preview(ctx, m1, "zc-m1-64v", 64, verbose=True).out]

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        a, b, c, e = (derive_preview(d) for d in dirs)
        fails += g2(dirs[1], [mods.cfg["identity"]["id"]])
        if a["images"] != b["images"]:
            fails.append(f"a default-preset world with Earth differs from M0: {a['images']} vs {b['images']}")
        if c["complexity"] != e["complexity"]:
            fails.append(f"default-preset complexity differs from M0: {e['complexity']} vs {c['complexity']}")
        got = {k: v["complexity"] for k, v in c["complexity"].items()}
        if got != VANILLA:
            fails.append(f"M0 complexity {got} is not vanilla's {VANILLA} (re-baseline?)")
        want = ((baseline_record().get("previews_256") or {}).get("M0") or {}).get(str(SEED))
        if (a["images"] or {}).get(f"{SEED}.png") != want:
            fails.append(f"M0's preview at seed {SEED} differs from tests/baselines/build-{GAME_BUILD}.json: "
                         f"re-baseline (rule 5)")
        meas = {"m0_256": a["images"], "m1_default_256": b["images"], "m0_64": c["complexity"],
                "m1_default_64": e["complexity"]}
        return meas, fails, (f"M1 default preview at seed {SEED} hash-identical to M0 ({list((a['images'] or {}).values())[:1]}); "
                             f"complexity identical {got}")

    cached_or_live(ctx, row, cache, key, newest, live, derive)
    ctx.shared["m0_256"] = (row.meas or {}).get("m0_256")


def row_t13_placeholder(ctx, mods, sec6, row, cache):
    m0, m1 = ctx.shared["m0"], ctx.shared["m1"]
    pname = placeholder_preset(mods.cfg)
    key, newest = common_key(ctx, "t13_placeholder", {"m1": mods.manifest(m1), "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        return [preview(ctx, m0, "ph-m0-256", 256).out, preview(ctx, m1, "ph-preset-256", 256, preset=pname).out]

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        a, b = derive_preview(dirs[0]), derive_preview(dirs[1])
        fails += g2(dirs[1], [mods.cfg["identity"]["id"]])
        if not b["images"] or a["images"] == b["images"]:
            fails.append("the Terra Nauvis: Europe preview equals M0's: Earth was not active (G5)")
        want = ((baseline_record().get("previews_256") or {}).get("placeholder") or {}).get(str(SEED))
        if (b["images"] or {}).get(f"{SEED}.png") != want:
            fails.append(f"the preset preview at seed {SEED} differs from tests/baselines/build-{GAME_BUILD}.json: "
                         f"run 'earth_test.py baseline' and commit it (rule 5)")
        return {"m0": a["images"], "preset": b["images"]}, fails, \
            f"preset preview {list((b['images'] or {}).values())[:1]} differs from M0's at seed {SEED} (G5)"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_t13_scenario(ctx, mods, sec6, row, cache):
    """A 60-tick scenario on the placeholder preset (G1 to G3), on M1's probe twin, whose dump probe
    proves the preset applied (G5): elevation at a point beyond the coast reads the placeholder's
    value, below 0, and its real tile is water."""
    import dump_render
    cfg = mods.cfg
    pname = placeholder_preset(cfg)
    m1p = mods.with_mods("m1p", [HERE / "mods" / "ep-s8-dump"])
    ph_name = cfg["placeholder"]["names"]["elevation"]
    sea_x = -cfg["placeholder"]["spawn_px"][0] * cfg["placeholder"]["scale"] - 100
    points = f"0,0;{sea_x},0"
    key, newest = common_key(ctx, "t13_scenario", {"m1p": mods.manifest(m1p), "points": points})

    def live():
        mods.prepare(m1p, "m1p")
        fh = dump_render.load_fh()
        dump_render.set_startup(fh, ctx.instance, m1p, {
            "label": "t13", "areas": f"{sea_x - 16},-16,32,32", "points": points, "names": f"elevation,{ph_name}",
            "decoratives": False, "scene": "", "scene-lattice": 4, "gen-tick": 1, "tick": 2, "types": "",
            "grid": "", "grid-name": "elevation", "grid-threshold": "0", "grid-op": "ge"})
        save = ctx.out / "t13-create" / "t13.zip"
        r1 = ctx.fh(["run", "--instance", ctx.instance, "--modset", m1p, "--", "--create", save,
                     "--map-gen-seed", str(SEED), "--preset", pname], ctx.out / "t13-create")
        r2 = ctx.fh(["scenario", "--instance", ctx.instance, "--modset", m1p, "--save", save, "--ticks", "60"],
                    ctx.out / "t13-scenario")
        return [r1.out, r2.out]

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        # a save loaded by --benchmark prints no mod checksums; the create run carries G2
        fails += g2(dirs[0], [cfg["identity"]["id"], "ep-s8-dump"])
        f = dirs[1] / "script-output" / "ep-s8-dump" / "t13.json"
        if not f.exists():
            return {}, fails + ["the probe wrote no dump: no proof the preset applied (G5)"], ""
        d = dump_render.load_json(f)
        names = d.get("names", [])
        pts = {(p["x"], p["y"]): p for p in d.get("points", [])}
        sea = pts.get((sea_x, 0), {})
        home = pts.get((0, 0), {})
        vals = dict(zip(names, sea.get("values") or []))
        hvals = dict(zip(names, home.get("values") or []))
        ev, pv = vals.get("elevation"), vals.get(ph_name)
        if ev is None or pv is None or ev != pv or ev >= 0:
            fails.append(f"at ({sea_x}, 0) elevation {ev} and {ph_name} {pv}: the preset did not apply (G5)")
        if "water" not in str(sea.get("tile", "")):
            fails.append(f"the real tile at ({sea_x}, 0) is {sea.get('tile')}, not water")
        return {"sea": {"elevation": ev, "tile": sea.get("tile")}, "home_elevation": hvals.get("elevation")}, \
            fails, f"60-tick scenario passes G1 to G3; at ({sea_x}, 0) elevation {ev} = {ph_name}, tile {sea.get('tile')} (G5)"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 4: T15a rows and isolation (a)

COMPARATOR = {"M1": "vanilla", "M2": "bab"}     # the row each modset's Earth rows are compared with (U7)
ZERO_COST_ROWS = ("vanilla", "default", "bab")


def budgets_rows(cfg, meas_ph, meas_m0, meas_def):
    """tests/budgets.json rows: each keyed by row kind, map, modset, scale, toggles (and variant)."""
    ph = cfg["placeholder"]
    common = {"seed": SEED, "size": 64}
    return [
        dict(common, row="vanilla", map=None, modset="M0", preset=None, scale=None, toggles="n/a", programs=meas_m0),
        dict(common, row="default", map=None, modset="M1", preset=None, scale=None, toggles="n/a", programs=meas_def),
        dict(common, row="placeholder", map=ph["map"], modset="M1", preset=placeholder_preset(cfg), scale=ph["scale"],
             toggles="n/a", programs=meas_ph),
    ]


def _row_id(r):
    return (r.get("row"), r.get("map"), r.get("modset"), r.get("scale"), r.get("toggles"), r.get("variant"))


def check_t15a(rows, sec6, main_rows, through):
    """T15a against section 6 (parsed from main's plan): every 6.2 complexity limit in force, bound
    by its measure's program, modset and maps (P10 and P12 on M1 rows, P11 and P13 on M2 rows, P14 on
    every Earth row; P12 and P13 per map by the row's map); no Earth row equal to its comparator
    (G5); and growth over main's same row (or, for a row main lacks, its comparator's) within the
    gating milestone's 6.3 allocation for the row's modset and map ("cap": only the limits bound it;
    "none" and a cell that names nothing give 0)."""
    fails = []
    alloc = sec6["allocations"].get(through)
    if alloc is None:
        return [f"section 6.3 gives {through!r} no allocation"]
    comps = {r.get("row"): r for r in rows if r.get("row") in COMPARATOR.values()}
    for r in rows:
        if r.get("row") in ZERO_COST_ROWS:
            continue
        name = f"{r.get('row')} ({r.get('modset')}, {r.get('map')})"
        cx = {k: v["complexity"] for k, v in (r.get("programs") or {}).items()}
        if set(cx) != {"tile", "entity", "cliff"}:
            fails.append(f"{name}: programs {sorted(cx)}, want Tile, Entity and Cliff (--verbose)")
            continue
        for pid, rec in sec6["limits"].items():
            sc = rec.get("complexity")
            if not sc or (sc["modset"] and sc["modset"] != r.get("modset")):
                continue
            lim = rec["limit"]
            cap = lim.get("max") if "max" in lim else (lim.get("per_map") or {}).get(r.get("map"))
            if cap is None:
                fails.append(f"{name}: {pid} holds no value for map {r.get('map')!r}")
            elif cx[sc["program"]] > cap:
                fails.append(f"{name} {sc['program'].title()} {cx[sc['program']]} over {pid} {cap:g}")
        comp = comps.get(COMPARATOR.get(r.get("modset")))
        if comp is None:
            fails.append(f"{name}: no {COMPARATOR.get(r.get('modset'), 'comparator')} row to compare with (U7)")
            continue
        comp_cx = {k: v["complexity"] for k, v in comp["programs"].items()}
        if cx == comp_cx:
            fails.append(f"{name} equals its comparator's {comp_cx}: the preset was not applied (G5)")
        base = next((m for m in main_rows if _row_id(m) == _row_id(r)), None)
        base_cx = {k: v["complexity"] for k, v in (base or comp)["programs"].items()}
        for prog in ("tile", "entity", "cliff"):
            a = alloc_for(alloc[prog], r.get("modset"), r.get("map"), r.get("variant"))
            if a["kind"] in ("cap", "first"):
                continue
            if a["kind"] == "headroom":
                top = headroom_limit(sec6, through, prog, r.get("modset"), r.get("map"), a["limit"])
                if cx[prog] > top:
                    fails.append(f"{name} {prog} {cx[prog]} over {a['limit']} minus the later reserves ({top:g})")
                continue
            allowed = a["value"] if a["kind"] == "add" else 0.0
            grew = cx[prog] - base_cx.get(prog, 0)
            if grew > allowed:
                fails.append(f"{name} {prog} grew {grew} over {'main' if base else 'its comparator'}, above "
                             f"{through}'s allocation {allowed:g}")
    return fails


def row_t15a_rows(ctx, mods, sec6, row, cache):
    m0, m1 = ctx.shared["m0"], ctx.shared["m1"]
    pname = placeholder_preset(mods.cfg)
    key, newest = common_key(ctx, "t15a_rows", {"m1": mods.manifest(m1), "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        return [preview(ctx, m0, "cx-m0", 64, verbose=True).out, preview(ctx, m1, "cx-default", 64, verbose=True).out,
                preview(ctx, m1, "cx-placeholder", 64, preset=pname, verbose=True).out]

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        c0, cd, cp = (ctx_complexity(d) for d in dirs)
        rows = budgets_rows(mods.cfg, cp, c0, cd)
        if isinstance(sec6, Exception):
            fails.append(f"section 6 unreadable: {sec6}")
        else:
            main_text = git_show("main:tests/budgets.json")
            main_rows = json.loads(main_text).get("rows", []) if main_text else []
            fails += check_t15a(rows, sec6, main_rows, ctx.slice)
        work = json.loads(BUDGETS.read_text(encoding="utf-8")).get("rows", [])
        if work != rows:
            fails.append("tests/budgets.json differs from the gate's measurement: run 'python tools/earth_test.py "
                         "baseline' and commit it (rule 5)")
        enforced = sorted(k for k, v in (sec6["limits"] if isinstance(sec6, dict) else {}).items() if v.get("complexity"))
        return {"rows": rows}, fails, (f"placeholder Tile {cp.get('tile', {}).get('complexity')} Entity "
                                       f"{cp.get('entity', {}).get('complexity')} Cliff {cp.get('cliff', {}).get('complexity')} "
                                       f"within {'/'.join(enforced)} and {ctx.slice}'s 6.3 allocation over its comparator, "
                                       f"not vanilla; equal to tests/budgets.json")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_isolation_a(ctx, mods, sec6, row, cache):
    """Isolation check (a), design constraint 3, S9's method: on every Terra Nauvis preset the
    Entity and Cliff programs are identical between the real build and its constant-coast twin
    while Tile differs (the twin's positive control). Positive control for Entity: on the leak
    fixture preset Entity must differ, since vanilla starting ore reads the twin's constant there."""
    cfg = mods.cfg
    m1 = ctx.shared["m1"]
    presets = earth_presets(cfg)
    twin_src = stage_twin(ctx, cfg)
    fx = leak_fixture(ctx, mods)
    fix_src, m1f = fx["dir"], fx["modset"]
    m1c = mods.with_mods("m1c", [twin_src, fix_src])
    key, newest = common_key(ctx, "isolation_a", {"m1c": mods.manifest(m1c), "m1f": mods.manifest(m1f),
                                                  "dump": ctx.shared.get("dump_m1_sha"), "presets": presets})

    def live():
        mods.prepare(m1c, "m1c")
        mods.prepare(m1f, "m1f")
        dirs = []
        for i, pn in enumerate(presets):
            dirs += [preview(ctx, m1, f"iso-real-{i}", 64, preset=pn, verbose=True).out,
                     preview(ctx, m1c, f"iso-twin-{i}", 64, preset=pn, verbose=True).out]
        dirs += [preview(ctx, m1f, "iso-fixture-real", 64, preset=LEAK_FIXTURE, verbose=True).out,
                 preview(ctx, m1c, "iso-fixture-twin", 64, preset=LEAK_FIXTURE, verbose=True).out]
        return dirs

    def logged(d, needle):
        return needle in stdout_of(d) or needle in (Path(d) / "factorio-current.log").read_text(
            encoding="utf-8", errors="replace")

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        if len(dirs) != 2 * len(presets) + 2:
            return {}, fails + [f"{len(dirs)} run directories, want {2 * len(presets) + 2}"], ""
        meas, parts = {}, []
        for i, pn in enumerate(presets):
            real, twin = ctx_complexity(dirs[2 * i]), ctx_complexity(dirs[2 * i + 1])
            if not logged(dirs[2 * i + 1], "ea-coast-twin: "):
                fails.append(f"{pn}: the twin's log line is missing: the constant coast did not apply")
            if not real or real.get("tile") == twin.get("tile"):
                fails.append(f"{pn}: the twin's Tile program equals the real build's: the positive control failed "
                             f"(TST-08)")
            for prog in ("entity", "cliff"):
                if real.get(prog) != twin.get(prog):
                    fails.append(f"{pn}: {prog.title()} differs between the real build {real.get(prog)} and its "
                                 f"constant-coast twin {twin.get(prog)}: the fine field reaches it (sacred "
                                 f"constraint 3)")
            meas[pn] = {"real": real, "twin": twin}
            parts.append(f"{pn}: Tile {real.get('tile', {}).get('complexity')} vs twin "
                         f"{twin.get('tile', {}).get('complexity')}, Entity {real.get('entity', {}).get('complexity')} "
                         f"and Cliff {real.get('cliff', {}).get('complexity')} equal the twin's")
        fr, ft = ctx_complexity(dirs[-2]), ctx_complexity(dirs[-1])
        if not logged(dirs[-2], f"{LEAK_FIXTURE}: preset") or not logged(dirs[-1], f"{LEAK_FIXTURE}: preset"):
            fails.append("the leak fixture's log line is missing: its preset was not added")
        if not fr or fr.get("entity") == ft.get("entity"):
            fails.append("positive control: on the leak fixture preset Entity is identical between the real build "
                         "and the twin, so the check could not see a fine field in Entity")
        if not fr or fr.get("tile") == ft.get("tile"):
            fails.append("positive control: on the leak fixture preset the twin's Tile equals the real build's")
        meas[LEAK_FIXTURE] = {"real": fr, "twin": ft}
        parts.append(f"control {LEAK_FIXTURE}: Entity {fr.get('entity', {}).get('complexity')} vs twin "
                     f"{ft.get('entity', {}).get('complexity')} (must differ)")
        return meas, fails, "; ".join(parts)

    cached_or_live(ctx, row, cache, key, newest, live, derive)


ROW_FUNCS = {
    "static": row_static, "fh_flags": row_fh_flags, "plan_main": row_plan_main, "section6": row_section6,
    "frozen": row_frozen, "data_src": row_data_src, "offline_selftests": row_offline_selftests,
    "runner_controls": row_runner_controls, "dumps": row_dumps, "t13_dump_facts": row_t13_dump_facts,
    "isolation_b": row_isolation_b, "ab_placeholder": row_ab_placeholder, "t13_zero_cost": row_t13_zero_cost,
    "t13_placeholder": row_t13_placeholder,
    "t13_scenario": row_t13_scenario, "t15a_rows": row_t15a_rows, "isolation_a": row_isolation_a,
}


# ------------------------------------------------------------------------------------------------ suite checks

class SuiteCheck:
    def __init__(self, name, key_fn, run_fn, derive_fn):
        self.name, self.key_fn, self.run_fn, self.derive_fn = name, key_fn, run_fn, derive_fn


def program_signature(ctx, mods, modset, label, preset=None):
    """The compiled programs' --verbose signature of a modset (64 px preview), the key of its timed rows."""
    r = preview(ctx, modset, f"sig-{label}", 64, preset=preset, verbose=True)
    if g1(r.out):
        raise GateError(f"signature preview of {modset} failed: {g1(r.out)[:2]}")
    return ctx_complexity(r.out)


def driver_modsets(ctx, mods):
    m0t = mods.with_mods("m0t", [HERE / "mods" / "tq1-gen"], earth=False)
    m0d = mods.with_mods("m0d", [HERE / "mods" / "tq2-driver"], earth=False)
    heavy = mods.with_mods("heavy", [HERE / "mods" / "tq2-driver", HERE / "mods" / "ea-heavy-probe"], earth=False)
    return m0t, m0d, heavy


def make_save(ctx, mods, modset, setting, spec, label):
    """One untimed save per config (fh.py scenario --seed 1000 --ticks 1); the job is baked in."""
    mods.prepare(modset, label)
    res = ctx.fh_plain(["settings", modset, "--set", f"runtime-global.{setting}={spec}"])
    if not res.startswith("RESULT ok"):
        raise GateError(f"fh.py settings {modset}: {res}")
    r = ctx.fh(["scenario", "--instance", ctx.instance, "--modset", modset, "--seed", str(SEED), "--ticks", "1"],
               ctx.out / f"save-{label}")
    if g1(r.out):
        raise GateError(f"save creation for {label} failed: {g1(r.out)[:2]}")
    return r.out / "scenario.zip"


def timed_rep(ctx, modset, save, out, mask, deadline, log, expect_census=None):
    """One quiet-window repetition of the T15b timer, with the affinity watcher when mask is set; a rep
    counts only if its block census equals the config's (test notes 5.2 item 5)."""
    perf = ctx.perf
    watcher = None
    if mask:
        watcher = perf.Watcher(out.parent / f"{out.name}-affinity.jsonl", mask, ctx.job)
        if not watcher.ready:
            raise GateError("the affinity watcher did not start")
    # the gate waits at most 2 minutes for a quiet machine, a suite up to its own deadline
    wait_until = min(deadline, time.time() + 120) if ctx.cmd == "gate" else deadline
    rows_pre, load_pre = perf.wait_quiet(wait_until, log)
    r = ctx.fh(["scenario", "--instance", "ea-time", "--modset", modset, "--save", save, "--ticks", str(T15B["ticks"]),
                "--", "--threads", str(T15B["threads"])], out, watcher=watcher, monitor=True)
    rec = {"out": str(out), "load_pre": load_pre, "result": r.result, "mask": mask, "reasons": []}
    rec.update(perf.parse_forced(out))
    rec["foreign"] = sorted(r.mon.foreign) if r.mon else []
    after = perf.tasklist_game()
    # the monitor's own observations, persisted beside the run, so the gate re-derives the rep's
    # validity from them instead of trusting this record's verdict (rule 2)
    persist_monitor(out.parent / f"{out.name}-monitor.json", r.mon, mask, load_pre, after)
    if not r.ok:
        rec["reasons"].append("fh.py result not ok: " + r.result)
    if rec["foreign"] or (r.mon and r.mon.max_games > 1):
        rec["reasons"].append(f"another game process during the run {rec['foreign']}")
    if after:
        rec["reasons"].append("a game process right after the run")
    c = rec.get("census") or {}
    if c.get("block_generated_before") != 0 or c.get("block_generated_after") != 256:
        rec["reasons"].append(f"block not generated exactly once: {c.get('block_generated_before')} -> "
                              f"{c.get('block_generated_after')}")
    if rec.get("force_ms") is None:
        rec["reasons"].append("no force duration")
    cs = {k: c.get(k) for k in ("water_tiles", "trees", "enemies")}
    if expect_census is not None and cs != expect_census:
        rec["reasons"].append(f"census {cs} differs from the config's {expect_census}")
    if watcher:
        recs, err, code = watcher.finish()
        log_text = (out / "bench" / "factorio-current.log").read_text(encoding="utf-8", errors="replace") \
            if (out / "bench" / "factorio-current.log").exists() else ""
        av = perf.affinity_verdict(recs, r.mon, log_text, mask)
        rec["affinity"] = av
        rec["reasons"] += ["affinity: " + x for x in av["reasons"]]
    if r.mon:
        r.mon.close()
    rec["valid"] = not rec["reasons"]
    (out.parent / f"{out.name}-rep.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    log(rec)
    return rec


def t15b_batch(ctx, mods, reps, masks, label, deadline):
    """M0t against M0t in one group (P18): two saves of the same config, interleaved rounds rotated by
    one, per mask; a rep counts only when valid and its census equals the config's."""
    m0t, _, _ = driver_modsets(ctx, mods)
    save_a = make_save(ctx, mods, m0t, "tq1-gen-block", T15B["block"], f"{label}-a")
    save_b = make_save(ctx, mods, m0t, "tq1-gen-block", T15B["block"], f"{label}-b")
    out_root = ctx.out / label
    out_root.mkdir(parents=True, exist_ok=True)
    logf = out_root / "reps.jsonl"

    def log(rec):
        with open(logf, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    valid = {(cfg, m): [] for cfg in ("a", "b") for m in masks}
    census = {}
    idx, rnd = 0, 0
    order = [(cfg, m) for m in masks for cfg in ("a", "b")]
    while any(len(v) < reps for v in valid.values()):
        rot = order[rnd % len(order):] + order[: rnd % len(order)]
        for cfg, mask in rot:
            if len(valid[(cfg, mask)]) >= reps:
                continue
            idx += 1
            save = save_a if cfg == "a" else save_b
            rec = timed_rep(ctx, m0t, save, out_root / f"r{idx:03d}-{cfg}-{mask:x}", mask, deadline, log,
                            expect_census=census.get(cfg))
            if rec["valid"]:
                c = rec.get("census") or {}
                census.setdefault(cfg, {k: c.get(k) for k in ("water_tiles", "trees", "enemies")})
                valid[(cfg, mask)].append(rec["force_ms"])
            if idx > 6 * reps * len(order):
                raise GateError("too many discarded repetitions")
        rnd += 1
    return out_root


def ratio_verdict(ratio, limit, band=BORDERLINE):
    """(inside the limit, the bound the ratio sits within `band` of, or None): rule 5's test of a
    timed ratio against a 6.2 limit (min and max, or max alone)."""
    lo, hi = limit.get("min"), limit.get("max")
    ok = (lo is None or ratio >= lo) and (hi is None or ratio <= hi)
    near = [b for b in (lo, hi) if b is not None and abs(ratio - b) <= band + 1e-9]
    return ok, (near[0] if near else None)


def extra_batch_fits(batch_seconds, batch_reps, extra_reps, now, deadline, margin=1.25):
    """(fits, seconds needed): whether one more group of extra_reps repetitions fits before the
    deadline, from the first group's wall time per repetition (its saves included) and a margin."""
    need = batch_seconds / max(1, batch_reps) * extra_reps * margin + 15.0
    return now + need <= deadline, need


MASK24 = 0xFFFFFF                 # all 24 logical processors (P3)
CENSUS_KEYS = ("water_tiles", "trees", "enemies")
# The 6.2 rows a timed pair's ratio (config a over config b) is held to, per affinity mask. P18 is
# M0t against M0t at 16 LP; P3 is every Earth modset's forced generation against its comparator at
# 24 LP (M1t/M0t, M2t/BABt) wherever a suite records one. P1 and P2 join the Earth pairs at 16 LP
# with the milestones that bring them into force. A mask with no row here is a recorded diagnostic.
PAIR_LIMITS = {"m0_self": {0xFFFF: ["P18"]},
               "m1_m0": {MASK24: ["P3"]},
               "m2_bab": {MASK24: ["P3"]}}
# The pair's configs whose block census must equal tests/baselines' vanilla census (M0 configs).
PAIR_VANILLA = {"m0_self": ("a", "b"), "m1_m0": ("b",), "m2_bab": ()}
# The record format of the timed rows' evidence: 2 adds the persisted monitor reads the gate
# re-derives each repetition's validity from (rule 2), so evidence of format 1 is stale.
TIMED_RECORDS = 2
REP_DIR_RE = re.compile(r"r(\d{3})-([ab])-([0-9a-f]+)")


def persist_monitor(path, mon, mask, load_pre, after):
    """The monitor's observations of one timed run (TQ1's quiet-window and affinity evidence) as a
    file beside the run: our game pids, foreign game pids, the most game processes seen, the
    affinity reads, the CPU load before the run and the tasklist rows right after it."""
    rec = {"mask": mask, "load_pre": load_pre, "tasklist_after": list(after or []),
           "root": getattr(mon, "root", None), "ours": sorted(getattr(mon, "ours", {}) or {}),
           "foreign": sorted(getattr(mon, "foreign", set()) or set()), "max_games": getattr(mon, "max_games", None),
           "polls": getattr(mon, "polls", None), "masks": [list(m) for m in (getattr(mon, "masks", []) or [])]}
    Path(path).write_text(json.dumps(rec, default=str), encoding="utf-8")
    return rec


def monitor_view(rec):
    """A persisted monitor record in the shape perf.affinity_verdict reads (ours, masks)."""
    import types
    return types.SimpleNamespace(ours={int(p): None for p in rec.get("ours") or []},
                                 masks=[tuple(m) for m in rec.get("masks") or []])


def affinity_from_raw(watcher_file, monitor_file, log_file, mask):
    """TQ1b's affinity verdict recomputed from raw outputs: the watcher's own records, the persisted
    monitor reads and the game log. Returns the reasons it fails (empty: the mask held)."""
    import perf
    if not Path(watcher_file).exists():
        return [f"no affinity watcher records ({Path(watcher_file).name})"]
    if not Path(monitor_file).exists():
        return [f"no persisted monitor record ({Path(monitor_file).name})"]
    try:
        recs = [json.loads(l) for l in Path(watcher_file).read_text(encoding="utf-8").splitlines() if l.strip()]
        mon = json.loads(Path(monitor_file).read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"unreadable watcher or monitor record: {e}"]
    av = perf.affinity_verdict(recs, monitor_view(mon), perf.read(log_file), mask)
    return list(av["reasons"])


def rep_from_raw(run, mask, census_want=None):
    """One T15b repetition's validity, force time and census, re-derived from its run directory and
    the files beside it (never from the runner's reps.jsonl or rep.json verdicts): G1 on run.json,
    the timer's force time and block census from script-output (perf.parse_forced), the persisted
    monitor record (no foreign game process during the run, at most one game process, none right
    after it, a quiet machine before it) and, with a mask, the affinity verdict recomputed from the
    watcher's records."""
    import perf
    run = Path(run)
    reasons = list(g1(run))
    f = perf.parse_forced(run)
    c = f.get("census") or {}
    if c.get("block_generated_before") != 0 or c.get("block_generated_after") != 256:
        reasons.append(f"block not generated exactly once: {c.get('block_generated_before')} -> "
                       f"{c.get('block_generated_after')}")
    if f.get("force_ms") is None:
        reasons.append("no force duration")
    cs = {k: c.get(k) for k in CENSUS_KEYS}
    if census_want is not None and cs != census_want:
        reasons.append(f"census {cs} differs from {census_want}")
    mon_file = run.parent / f"{run.name}-monitor.json"
    try:
        mon = json.loads(mon_file.read_text(encoding="utf-8")) if mon_file.exists() else None
    except ValueError:
        mon = None
    if mon is None:
        reasons.append(f"no persisted monitor record ({mon_file.name})")
    else:
        if mon.get("foreign") or (mon.get("max_games") or 0) > 1:
            reasons.append(f"another game process during the run {mon.get('foreign')}")
        if mon.get("tasklist_after"):
            reasons.append("a game process right after the run")
        if mon.get("load_pre") is None or float(mon["load_pre"]) >= perf.LOAD_LIMIT:
            reasons.append(f"CPU load before the run {mon.get('load_pre')} is not under {perf.LOAD_LIMIT}%")
        if mon.get("mask") != mask:
            reasons.append(f"monitor record mask {mon.get('mask')} differs from the run's {mask}")
    if mask:
        reasons += ["affinity: " + x for x in affinity_from_raw(run.parent / f"{run.name}-affinity.jsonl", mon_file,
                                                               run / "bench" / "factorio-current.log", mask)]
    return {"valid": not reasons, "reasons": reasons, "force_ms": f.get("force_ms"), "census": cs}


def pair_limit_failures(pair, mask, ratio, limits, pooled, label):
    """Rule 5 for one timed pair at one mask against the 6.2 rows PAIR_LIMITS binds there: a ratio
    outside a limit fails; one within BORDERLINE of a bound is undecided on one group (fails until
    the pooled reps decide it). Returns (failures, the bound it sits near or None, undecided)."""
    fails, near_any, undecided = [], None, False
    for pid in PAIR_LIMITS.get(pair, {}).get(mask, []):
        if pid not in limits:
            continue
        lim = limits[pid]["limit"]
        ok, near = ratio_verdict(ratio, lim)
        if near is not None:
            near_any = near
        if near is not None and not pooled:
            undecided = True
            fails.append(f"{pid}: {label} at mask {mask:#x} is {ratio:.4f}, within {BORDERLINE} of its bound {near:g}: "
                         f"rule 5 decides it on one more batch of {T15B['reps_extra']} reps per config, pooled")
        elif not ok:
            fails.append(f"{pid}: {label} at mask {mask:#x} is {ratio:.4f}{' on the pooled reps' if pooled else ''}, "
                         f"outside {lim.get('min')} to {lim.get('max')}")
    return fails, near_any, undecided


def derive_t15b(dirs, limits, reps, pair="m0_self", label="M0t/M0t"):
    """T15b from one group or a group plus rule 5's extra group, pooled, re-derived from the raw
    outputs alone (rule 2): every repetition directory of each group (r<NNN>-<config>-<mask>,
    numbered without a gap, so none can be dropped) has its validity, force time and census
    recomputed by rep_from_raw; the runner's reps.jsonl is only cross-checked against that, and a
    disagreement fails. Each config's valid reps share one census, the vanilla configs' equal
    tests/baselines', and each mask's ratio of medians meets the rows PAIR_LIMITS binds (P18 for
    M0t against M0t at 16 LP; P3 for an Earth pair at 24 LP). A ratio within BORDERLINE of a bound
    is decided only on the pooled reps of one more group; on one group it is undecided and fails."""
    import perf
    fails, meas = [], {}
    if not dirs or len(dirs) > 2:
        return {}, [f"{len(dirs)} batches: rule 5 allows one batch plus one more"], ""
    want = (baseline_record().get("t15b_block") or {}).get("census_m0") or {}
    want = {k: want.get(k) for k in CENSUS_KEYS} if want else None
    by, census, batch_masks = {}, {}, []
    for bi, out_root in enumerate(dirs):
        out_root = Path(out_root)
        runs = sorted((d for d in out_root.iterdir() if d.is_dir() and REP_DIR_RE.fullmatch(d.name)),
                      key=lambda d: int(REP_DIR_RE.fullmatch(d.name).group(1)))
        idx = [int(REP_DIR_RE.fullmatch(d.name).group(1)) for d in runs]
        if idx != list(range(1, len(idx) + 1)):
            fails.append(f"{out_root.name}: repetition directories {idx[:3]}...{idx[-3:]} are not numbered 1..{len(idx)} "
                         f"without a gap (a dropped repetition)")
        logged = {}
        rj = out_root / "reps.jsonl"
        for line in (rj.read_text(encoding="utf-8").splitlines() if rj.exists() else []):
            if line.strip():
                r = json.loads(line)
                if r.get("kind") != "deferred":
                    logged[Path(r.get("out", "")).name] = r
        if set(logged) != {d.name for d in runs}:
            fails.append(f"{out_root.name}: reps.jsonl lists {len(logged)} repetitions, the batch holds {len(runs)} "
                         f"repetition directories")
        masks = set()
        for run in runs:
            m = REP_DIR_RE.fullmatch(run.name)
            cfg_, mask = m.group(2), int(m.group(3), 16)
            masks.add(mask)
            raw = rep_from_raw(run, mask, census.get(cfg_))
            if raw["valid"]:
                census.setdefault(cfg_, raw["census"])
                by.setdefault((cfg_, mask), []).append(raw["force_ms"])
            stored = logged.get(run.name)
            if stored is not None and bool(stored.get("valid")) != raw["valid"]:
                fails.append(f"{run.name}: reps.jsonl records valid={bool(stored.get('valid'))}, its raw outputs say "
                             f"valid={raw['valid']} {raw['reasons'][:2]}")
            if stored is not None and raw["valid"] and stored.get("force_ms") != raw["force_ms"]:
                fails.append(f"{run.name}: force time re-parses to {raw['force_ms']}, recorded {stored.get('force_ms')}")
        batch_masks.append(masks)
    for cfg_ in PAIR_VANILLA.get(pair, ()):
        if want and cfg_ in census and census[cfg_] != want:
            fails.append(f"config {cfg_}: block census {census[cfg_]} differs from tests/baselines' {want}")
    for mask in sorted({m for _, m in by}):
        a, b = by.get(("a", mask), []), by.get(("b", mask), [])
        pooled = len(dirs) > 1 and mask in batch_masks[1]
        need = reps + (T15B["reps_extra"] if pooled else 0)
        if len(a) < need or len(b) < need:
            fails.append(f"mask {mask:#x}: {len(a)} and {len(b)} valid reps, want {need} each")
            continue
        ratio = perf.median(a) / perf.median(b)
        rec = {"a_median_ms": perf.median(a), "b_median_ms": perf.median(b), "ratio": round(ratio, 4),
               "a_spread": perf.spread(a), "b_spread": perf.spread(b), "reps": [len(a), len(b)],
               "batches": 2 if pooled else 1}
        f, near, undecided = pair_limit_failures(pair, mask, ratio, limits, pooled, label)
        if PAIR_LIMITS.get(pair, {}).get(mask):
            rec["borderline"] = near
        if undecided:
            rec["undecided"] = True
        fails += f
        meas[f"{mask:#x}"] = rec
    for mask in PAIR_LIMITS.get(pair, {}):
        if pair == "m0_self" and f"{mask:#x}" not in meas:
            fails.append(f"no pair at mask {mask:#x} ({', '.join(PAIR_LIMITS[pair][mask])})")
    return meas, fails, "; ".join(
        f"mask {k}: {label} {v['ratio']} (medians {v['a_median_ms']:.1f} and {v['b_median_ms']:.1f} ms, {v['reps']} "
        f"reps re-derived from raw outputs{', pooled over 2 batches (rule 5)' if v['batches'] > 1 else ''})"
        for k, v in meas.items())


def walker_run(ctx, mods, modset, label, deadline, mask=None):
    spec = "walk:nauvis:{x0}:{y0}:{dx}:{dy}:{R}:{P}:{N}:{D}:{T0}".format(**WALK)
    save = make_save(ctx, mods, modset, "tq2-mode", spec, f"walk-{label}")
    ticks = WALK["T0"] + WALK["N"] * WALK["P"] + WALK["D"] + 2
    perf = ctx.perf
    perf.wait_quiet(deadline)
    watcher = perf.Watcher(ctx.out / f"walk-{label}-affinity.jsonl", mask, ctx.job) if mask else None
    r = ctx.fh(["scenario", "--instance", "ea-time", "--modset", modset, "--save", save, "--ticks", str(ticks), "--",
                "--benchmark-verbose", "all", "--threads", str(T15B["threads"])], ctx.out / f"walk-{label}",
               timeout=900, watcher=watcher, monitor=True)
    after = perf.tasklist_game()
    if watcher:
        recs, _, _ = watcher.finish()
        log_text = perf.read(r.out / "bench" / "factorio-current.log")
        # a diagnostic copy of the run-time verdict; the gate recomputes it from the raw records
        (r.out / "affinity.json").write_text(json.dumps(
            perf.affinity_verdict(recs, r.mon, log_text, mask), indent=1, default=str), encoding="utf-8")
    persist_monitor(r.out.parent / f"{r.out.name}-monitor.json", r.mon, mask, None, after)
    if r.mon:
        r.mon.close()
    return r.out


def derive_walker(d, mask=0xFFFF):
    """The benchmark-mode walker from its raw outputs: G1, the persisted monitor record (no foreign
    game process, none right after), and with a mask the affinity verdict recomputed from the
    watcher's records (never the run-time affinity.json); then the --benchmark-verbose columns."""
    import perf
    d = Path(d)
    fails = g1(d)
    mon_file = d.parent / f"{d.name}-monitor.json"
    try:
        mon = json.loads(mon_file.read_text(encoding="utf-8")) if mon_file.exists() else None
    except ValueError:
        mon = None
    if mon is None:
        fails.append(f"walker: no persisted monitor record ({mon_file.name})")
    else:
        if mon.get("foreign") or (mon.get("max_games") or 0) > 1:
            fails.append(f"walker: another game process during the run {mon.get('foreign')}")
        if mon.get("tasklist_after"):
            fails.append("walker: a game process right after the run")
        if mon.get("mask") != mask:
            fails.append(f"walker: monitor record mask {mon.get('mask')} differs from the check's {mask}")
    if mask:
        fails += [f"walker affinity {mask:#x}: {x}" for x in affinity_from_raw(
            d.parent / f"{d.name}-affinity.jsonl", mon_file, d / "bench" / "factorio-current.log", mask)]
    w = json.loads(perf.read(Path(d) / "script-output" / "tq2" / "walk.json") or "{}")
    if not w:
        return {}, fails + ["no walk.json"], ""
    if w.get("generated") != w.get("requested"):
        fails.append(f"walker: {w.get('generated')} of {w.get('requested')} requested chunks generated")
    vb = perf.parse_verbose(perf.read(Path(d) / "bench" / "stdout.txt"))
    if not vb:
        return {}, fails + ["no --benchmark-verbose rows"], ""
    st = perf.window_stats(vb, w["window_start_tick"], w["window_end_tick"], columns_per=WALK["N"])
    need = ["wholeUpdate", "scriptUpdate", "mapGenerator", PERF15_KEEP]
    missing = [c for c in need if c not in st["columns"]]
    if missing:
        fails.append(f"columns missing from --benchmark-verbose all: {missing}")
    mg = sorted(c for c in st["columns"] if c.startswith("mapGenerator"))
    meas = {"requested": w["requested"], "window": [st["first"], st["last"]], "ticks": st["ticks"],
            "columns": {c: {k: round(v, 5) for k, v in st["columns"][c].items()} for c in ["wholeUpdate", "scriptUpdate"] + mg}}
    return meas, fails, (f"walker parsed {st['ticks']} ticks, {len(mg)} mapGenerator columns: wholeUpdate mean "
                         f"{st['columns']['wholeUpdate']['mean']:.3f} ms, scriptUpdate mean "
                         f"{st['columns']['scriptUpdate']['mean']:.4f} ms, BasicTilesSupportCompute "
                         f"{st['columns'].get(PERF15_KEEP, {}).get('per_step_ms', 0):.2f} ms per step")


def derive_perf15(dirs):
    if len(dirs) != 2:
        return {}, [f"perf15 holds {len(dirs)} walker runs, want 2 (M0 and the heavy probe)"], ""
    a_meas, fa, _ = derive_walker(dirs[0])
    b_meas, fb, _ = derive_walker(dirs[1])
    fails = fa + fb
    if fails:
        return {}, fails, ""
    deltas = {}
    for c, rec in b_meas["columns"].items():
        if c.startswith("mapGenerator") and c != "mapGenerator" and c in a_meas["columns"]:
            deltas[c] = round(rec["sum_ms"] - a_meas["columns"][c]["sum_ms"], 3)
    moved = max(deltas, key=deltas.get) if deltas else None
    sig = {"M0": dirs[2] if len(dirs) > 2 else None}
    return {"deltas_ms": deltas, "moved": moved}, [], (
        f"record-only: the heavy probe moved {moved} by {deltas.get(moved)} ms over the window "
        f"(Phase 4 found the composite's cost in BasicTilesSupportCompute, BENCHMARKS.md:247-272)")


def server_run(ctx, mods, modset, spec, label, timeout, saves):
    save = make_save(ctx, mods, modset, "tq2-mode", spec, label)
    wd = ctx.ws / "test-instance" / "instances" / "ea-srv" / "write-data"
    (wd / "saves").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ctx.perf.wait_quiet(ctx.deadline or time.time() + 3600)
    r = ctx.fh(["run", "--instance", "ea-srv", "--modset", modset, "--", "--start-server", save, "--server-settings",
                HERE / "perf-server-settings.json", "--port", str(SERVER["port"]), "--bind", "127.0.0.1"],
               ctx.out / label, timeout=timeout, monitor=True)
    got = {}
    for name in saves:
        f = wd / "saves" / f"{name}.zip"
        if f.exists() and f.stat().st_mtime >= t0:
            dst = r.out / f"{name}.zip"
            shutil.copy2(f, dst)
            got[name] = {"bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
    (r.out / "server-saves.json").write_text(json.dumps({"since": t0, "saves": got}, indent=1), encoding="utf-8")
    if r.mon:
        r.mon.close()
    return r.out


def derive_server(d, saves):
    """The server clause from the run's raw outputs: G1 with exit=timeout, and each expected save
    copied into the run directory, written by this server (its mtime, kept by the copy, at or after
    the server's start) and re-hashing to its record. The sizes later rows use are the files' own."""
    sv = json.loads((Path(d) / "server-saves.json").read_text(encoding="utf-8"))
    since = sv.get("since")
    present = {n: (Path(d) / f"{n}.zip").stat().st_mtime if (Path(d) / f"{n}.zip").exists() else None for n in saves}
    fails = [] if isinstance(since, (int, float)) else ["server-saves.json records no server start time"]
    fails += g1(d, server=True, saves=present, since=since if isinstance(since, (int, float)) else None)
    rj = Path(d) / "run.json"
    if isinstance(since, (int, float)) and rj.exists() and since > rj.stat().st_mtime:
        fails.append("server-saves.json records a start after the run ended")
    for n in saves:
        f = Path(d) / f"{n}.zip"
        if n not in sv["saves"] or not f.exists():
            fails.append(f"server save {n} missing (server clause)")
            continue
        if sha256_file(f) != sv["saves"][n]["sha256"]:
            fails.append(f"server save {n} does not re-hash")
        sv["saves"][n]["bytes"] = f.stat().st_size
    return sv, fails


def derive_rt(dirs):
    import perf
    d = dirs[0]
    sv, fails = derive_server(d, ["tq2-rt"])
    ticks, iv = perf.parse_rt(d)
    lo, hi = EXPLORE["T0"], EXPLORE["T0"] + EXPLORE["K"] * EXPLORE["P"] + EXPLORE["D"] - 1
    if len(iv) != hi - lo + 1 or (ticks and (ticks[0], ticks[-1]) != (lo, hi)):
        fails.append(f"{len(iv)} interval lines over ticks {ticks[:1]}..{ticks[-1:]}, want {lo}..{hi}")
    x = json.loads(perf.read(Path(d) / "script-output" / "tq2" / "explore.json") or "{}")
    if not x or x.get("pending_at_window_end") != 0 or x.get("band_generated") != x.get("band_chunks"):
        fails.append("the exploring window did not generate every requested chunk")
    st = perf.interval_stats(iv) or {}
    meas = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()}
    return meas, fails, (f"real time at 60 UPS on M0 (record-only until europe-coast): {meas.get('over_20ms')} ticks "
                         f"over 20 ms (P4), p99 {meas.get('p99')} ms (P5), longest {meas.get('max')} ms (P6)")


def derive_save(dirs):
    d = dirs[0]
    sv, fails = derive_server(d, ["tq2-pre", "tq2-post"])
    import perf
    blk = json.loads(perf.read(Path(d) / "script-output" / "tq2" / "save-block.json") or "{}")
    if blk.get("block_generated_after") != 256:
        fails.append("the forced block was not generated in the save job")
    s = sv.get("saves", {})
    inc = s.get("tq2-post", {}).get("bytes", 0) - s.get("tq2-pre", {}).get("bytes", 0)
    return {"pre": s.get("tq2-pre", {}).get("bytes"), "post": s.get("tq2-post", {}).get("bytes"), "increment": inc}, \
        fails, f"server saves at ticks 60 and 120 on M0: the forced block's save increment is {inc} bytes (P19 record)"


def gst_replay(d, only=None, tamper=None):
    """Replay a stored game self-test run on a scratch copy (game_selftest.py --replay): (the
    re-derived verdicts or None, the replay's RESULT line). `only` limits the tests; `tamper(copy)`
    edits the copy first (the positive control)."""
    with tempfile.TemporaryDirectory(prefix="tn-gst-replay-") as td:
        copy = Path(td) / "gst"
        shutil.copytree(d, copy)
        if (copy / "game-selftest.json").exists():
            os.replace(copy / "game-selftest.json", Path(td) / "stored-verdicts.json")
        if tamper:
            tamper(copy)
        env = {k: v for k, v in os.environ.items() if k != tnguard.ENV}
        cmd = [sys.executable, str(HERE / "game_selftest.py"), "--out-root", str(copy), "--replay"]
        cmd += ["--only", only] if only else []
        cp = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=900, env=env)
        lines = [l for l in (cp.stdout or "").splitlines() if l.startswith("RESULT ")]
        tail = lines[-1] if lines else (cp.stdout or cp.stderr or "")[-300:]
        rf = copy / "game-selftest.json"
        return (json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else None), tail


def gst_replay_controls():
    """The replay re-derives instead of trusting: on the suite's stored game self-test run (t1 tests
    only, a scratch copy), the untouched copy replays clean, and a copy whose sampled values were
    edited (nothing an image hash covers) fails its grid test although the stored verdict file
    says every test passed."""
    out = {}
    man = SUITES / "toolchain.json"
    ent = (json.loads(man.read_text(encoding="utf-8")).get("checks") or {}).get("gst") if man.exists() else None
    d = None
    if ent and ent.get("run_dirs"):
        q = Path(ent["run_dirs"][0])
        d = q if q.is_absolute() else Path(os.environ.get("FACTORIO_WS") or DEFAULT_WS) / q
    sample = Path("t1-s3-b00") / "script-output" / "fh-sampler" / "sample.json"
    if not d or not (d / sample).exists():
        return {"gst replay: a stored game self-test run exists to replay": (
            False, "none found: run python tools/earth_test.py suite toolchain --only gst")}

    def tamper(copy):
        f = copy / sample
        s = json.loads(f.read_text(encoding="utf-8"))
        key = sorted(s)[:4] if isinstance(s, dict) else type(s).__name__

        def bump(o):
            if isinstance(o, dict):
                if "ep_s8_x" in o and isinstance(o["ep_s8_x"], list):
                    o["ep_s8_x"] = [v + 1 if isinstance(v, (int, float)) else v for v in o["ep_s8_x"]]
                    return True
                return any(bump(v) for v in o.values())
            if isinstance(o, list):
                return any(bump(v) for v in o)
            return False
        if not bump(s):
            raise GateError(f"the sample file shape changed ({key}); the control cannot edit it")
        f.write_text(json.dumps(s), encoding="utf-8")
    # a replay rewrites analysis files and game-selftest.json beside the runs it replays: on the stored
    # evidence itself it must refuse before writing anything, whatever folder it is started from
    sf = d / "game-selftest.json"
    before = sha256_file(sf) if sf.exists() else None
    env = {k: v for k, v in os.environ.items() if k != tnguard.ENV}
    try:
        rel = os.path.relpath(d, tnguard.ws_root())
    except ValueError:
        rel = str(d)
    refused = []
    for args in (["--out-root", str(d)], ["--out-root", rel]):
        cp = subprocess.run([sys.executable, str(HERE / "game_selftest.py")] + args + ["--replay", "--only", "t1"],
                            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=120, env=env)
        refused.append(cp.returncode != 0 and "refuses --replay" in (cp.stdout or "") + (cp.stderr or ""))
    out["gst replay: a replay on the stored evidence itself (absolute or workspace-relative) is refused"] = (
        all(refused) and (sha256_file(sf) if sf.exists() else None) == before, refused)
    res, tail = gst_replay(d, only="t1")
    out["gst replay: the stored t1 runs replay clean"] = (
        bool(res) and all(r["ok"] for r in res), tail)
    try:
        res, tail = gst_replay(d, only="t1", tamper=tamper)
        bad = [r["test"] for r in (res or []) if not r["ok"]]
        out["gst replay: an edited sample fails its test although the stored verdicts say ok"] = (
            "t1_s3_grid_positions" in bad, bad[:3] or tail)
    except GateError as e:
        out["gst replay: an edited sample fails its test although the stored verdicts say ok"] = (False, str(e))
    return out


def derive_gst(dirs):
    """The game self-test re-derived from its raw outputs (rule 2): G1 and the image hashes of every
    stored run directory, then a scratch copy of the run replayed by game_selftest.py --replay, which
    answers every game command from that run's own run.json and re-runs every committed check over
    the stored outputs, launching nothing. The run's game-selftest.json is never the verdict: it is
    only cross-checked against the replay, and a disagreement fails."""
    d = Path(dirs[0])
    fails = []
    sf = d / "game-selftest.json"
    stored = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else None
    if stored is None:
        fails.append("no game-selftest.json in the stored run")
    images = {}
    for rj in sorted(d.rglob("run.json")):
        fails += g1(rj.parent)
        fails += images_rehash(rj.parent)
        for k, v in (load_run_json(rj.parent).get("images") or {}).items():
            images[f"{rj.parent.name}/{k}"] = v
    res, tail = gst_replay(d)
    if res is None:
        return {"images": images}, fails + [f"the replay wrote no verdicts ({tail})"], ""
    bad = [r["test"] for r in res if not r["ok"]]
    if len(res) != GST_TESTS:
        fails.append(f"the replayed game self-test ran {len(res)} tests, S8 ran {GST_TESTS}")
    if bad:
        fails.append(f"replayed game self-test failures: {bad[:6]}")
    if stored is not None:
        s = {r["test"]: bool(r["ok"]) for r in stored}
        g = {r["test"]: bool(r["ok"]) for r in res}
        if s != g:
            diff = sorted(k for k in set(s) | set(g) if s.get(k) != g.get(k))
            fails.append(f"the stored game-selftest.json disagrees with the replay on {diff[:6]}")
    return {"tests": len(res), "failed": len(bad), "images": images, "replayed": True}, fails, \
        (f"game self-test {len(res) - len(bad)} of {len(res)}, re-derived by replaying the stored runs (nothing "
         f"launched); {len(images)} preview images re-hashed")


# the S8 tools the game self-test runs, and the modules they import
GST_TOOLS = ("game_selftest.py", "earthgeo.py", "t1_metrics.py", "contact_sheet.py", "oracle.py", "dump_render.py",
             "nav.py", "tnconfig.py", "tnguard.py", "perf.py")


def suite_checks(ctx, mods, sec6):
    """Each suite check: (key builder, runner, deriver). Timed rows key on the programs' --verbose
    signatures plus the control-stage sources (rule 2); the rest on their inputs."""
    d = input_digests(ctx)
    limits = sec6["limits"] if isinstance(sec6, dict) else {}
    m0t, m0d, heavy = driver_modsets(ctx, mods)
    # The M0 rows load no Earth mod: they key on the vanilla programs' signatures, the driver mods
    # (their control stage), the timing machinery, fh.py and the build, never on Earth's sources or
    # the runner's registry, so a later milestone's routine edits leave this evidence warm (rule 2).
    ctl = {"tq1-gen": folder_hash(HERE / "mods" / "tq1-gen"), "tq2-driver": folder_hash(HERE / "mods" / "tq2-driver")}
    timing = {"perf": sha256_file(HERE / "perf.py"), "watcher": sha256_file(HERE / "affinity_watch.ps1"), "fh": d["fh"]}

    def sig(modset, label):
        k = f"sig-{modset}"
        if k not in ctx.shared:
            ctx.shared[k] = program_signature(ctx, mods, modset, label)
        return ctx.shared[k]

    checks = {}

    def gst_key():
        # what the game self-test exercises: S8's tools and their imports, the S8 probe mods, the
        # rasters, S8's oracle fixture and expressions, config.lua (earthgeo reads it), fh.py, the
        # sampler and the build
        tools, _ = tree_digest([HERE / t for t in GST_TOOLS])
        s8mods, _ = tree_digest([HERE / "mods" / m for m in ("ep-s8-probe", "ep-s8-dump", "ep-s8-disc-world")])
        rasters, _ = tree_digest([REPO / "data-src" / "earthmaps"])
        oracle, _ = tree_digest([TESTS / "oracle" / "s8", TESTS / "oracle" / "expressions.json"])
        return key_of({"check": "gst", "tools": tools, "test_mods": s8mods, "data_src": rasters, "oracle": oracle,
                       "config": sha256_file(MOD / "prototypes" / "config.lua"), "fh": d["fh"],
                       "sampler": d["sampler"], "build": GAME_BUILD})

    def gst_run(deadline):
        out = ctx.out / "gst"
        if ctx.guard is not None:
            ctx.guard.note_launch(tool_constant(HERE / "game_selftest.py", "INSTANCE"))
        code, text, _ = ctx.popen_text([sys.executable, HERE / "game_selftest.py", "--out-root", out], 1800)
        (ctx.out / "gst.txt").write_text(text, encoding="utf-8")
        # the child stops itself on a breach; the runner then stops every further game run too
        for rd in [out] + sorted({p.parent for p in out.rglob("run.json")}) if out.is_dir() else [out]:
            why = tnguard.run_breach(rd)
            if why:
                raise FatalRun(f"game_selftest.py run {rd}: {why}")
        if "stops every further game run" in text:
            raise FatalRun("game_selftest.py stopped every further game run: " +
                           next((l for l in text.splitlines() if "stops every further game run" in l), "")[:300])
        return [out]

    checks["gst"] = SuiteCheck("gst", gst_key, gst_run, derive_gst)

    def t15b_key():
        return key_of({"check": "t15b_m0", "sig": sig(m0t, "m0t"), "control": ctl, "timing": timing, "config": T15B,
                       "build": GAME_BUILD, "masks": [ctx.perf.MASK16, ctx.perf.MASK8], "borderline": BORDERLINE,
                       "records": TIMED_RECORDS})

    def t15b_run(deadline, reps=T15B["reps_suite"], masks=None):
        """Rule 5 in the suite: a 16 LP ratio within BORDERLINE of a P18 bound gets one more group of
        reps_extra reps per config at 16 LP, and the evidence holds both groups (decided pooled)."""
        masks = masks or [ctx.perf.MASK16, ctx.perf.MASK8]
        first = t15b_batch(ctx, mods, reps, masks, "t15b-m0", deadline)
        meas, _, _ = derive_t15b([first], limits, reps)
        rec = meas.get(f"{ctx.perf.MASK16:#x}") or {}
        if not rec.get("undecided"):
            return [first]
        ctx.say(f"     rule 5: M0t/M0t {rec['ratio']} is within {BORDERLINE} of {rec['borderline']:g}; one more batch "
                f"of {T15B['reps_extra']} reps per config, decided on the pooled reps")
        return [first, t15b_batch(ctx, mods, T15B["reps_extra"], [ctx.perf.MASK16], "t15b-m0-x", deadline)]

    checks["t15b_m0"] = SuiteCheck("t15b_m0", t15b_key, t15b_run,
                                   lambda dirs: derive_t15b(dirs, limits, T15B["reps_suite"]))

    def walker_key():
        return key_of({"check": "walker_m0", "sig": sig(m0d, "m0d"), "control": ctl, "timing": timing, "config": WALK,
                       "build": GAME_BUILD, "records": TIMED_RECORDS})

    checks["walker_m0"] = SuiteCheck("walker_m0", walker_key,
                                     lambda deadline: [walker_run(ctx, mods, m0d, "m0", deadline, ctx.perf.MASK16)],
                                     lambda dirs: derive_walker(dirs[0]))

    def perf15_key():
        return key_of({"check": "perf15", "sig": [sig(m0d, "m0d"), sig(heavy, "heavy")], "control": ctl,
                       "timing": timing, "heavy": folder_hash(HERE / "mods" / "ea-heavy-probe"), "config": WALK,
                       "build": GAME_BUILD, "records": TIMED_RECORDS})

    checks["perf15"] = SuiteCheck("perf15", perf15_key,
                                  lambda deadline: [walker_run(ctx, mods, m0d, "perf15-m0", deadline, ctx.perf.MASK16),
                                                    walker_run(ctx, mods, heavy, "perf15-heavy", deadline,
                                                               ctx.perf.MASK16)],
                                  derive_perf15)

    def rt_key():
        return key_of({"check": "rt_m0", "sig": sig(m0d, "m0d"), "control": ctl, "timing": timing, "config": EXPLORE,
                       "server": [SERVER, sha256_file(HERE / "perf-server-settings.json")], "build": GAME_BUILD})

    rt_spec = "rtexplore:nauvis:{cx0}:{cy}:{R}:{K}:{P}:{D}:{T0}".format(**EXPLORE)
    checks["rt_m0"] = SuiteCheck("rt_m0", rt_key,
                                 lambda deadline: [server_run(ctx, mods, m0d, rt_spec, "rt-m0", SERVER["rt_timeout"],
                                                              ["tq2-rt"])],
                                 derive_rt)

    def save_key():
        return key_of({"check": "save_m0", "sig": sig(m0d, "m0d"), "control": ctl, "timing": timing, "block": SAVE_BLOCK,
                       "server": [SERVER, sha256_file(HERE / "perf-server-settings.json")], "build": GAME_BUILD})

    save_spec = f"save:nauvis:{SAVE_BLOCK[0]}:{SAVE_BLOCK[1]}:1"
    checks["save_m0"] = SuiteCheck("save_m0", save_key,
                                   lambda deadline: [server_run(ctx, mods, m0d, save_spec, "save-m0",
                                                                SERVER["save_timeout"], ["tq2-pre", "tq2-post"])],
                                   derive_save)
    return checks


# ------------------------------------------------------------------------------------------------ commands

def with_bracket(ctx, fn):
    """Lock, guard snapshot, the bracket token, the command, guard check, lock release; the job dies
    with us. Every game launch of the command and of its child tools sits inside this bracket."""
    lock = Lock(ctx.root / "earth-test.lock")
    guard = None
    code = 1
    try:
        lock.acquire(ctx.cmd)
        guard = Guard(ctx, slice_entry(ctx.slice)["part"])
        ctx.say(f"G9 {guard.start()}")
        ctx.guard = guard
        # the record of every manual re-baseline in this part: the run logs each one
        for e in guard.rebaselines():
            ctx.say(f"G9 NOTE part {guard.part} {e.get('event')} at {e.get('at')}: {e.get('reason') or e.get('moved')} "
                    f"(replaced {(e.get('replaces') or {}).get('cmd')} {(e.get('replaces') or {}).get('start')}); "
                    f"log it on the sprint parent issue")
        ctx.shared["rebaselines"] = len(guard.rebaselines())
        ctx.bracket = lock.set_token(guard.token, guard.chain_file, guard.start_file)
        code = fn()
    except FatalRun as e:
        # the job is terminated and the guard checked below, before anything else can launch
        ctx.say(f"FATAL {e}; every further game run of this command is stopped, the job is terminated and the "
                f"guard check runs now; {GUARD_STOP}")
        code = 1
    except BudgetExceeded as e:
        ctx.say(f"BUDGET {e}")
        code = 1
    except GateError as e:
        ctx.say(f"HALT {e}")
        code = 1
    except Exception as e:  # a crash fails closed, with the trace kept in the console
        ctx.say(f"CRASH {type(e).__name__}: {e}")
        ctx.say(traceback.format_exc()[-3000:])
        code = 1
    finally:
        try:
            ctx.job.terminate()
        except Exception:
            pass
        ctx.bracket = None
        ctx.guard = None
        if guard is not None and guard.start_file:
            ok, res, _ = guard.finish()
            ctx.say(f"G9 check {res}")
            if not ok:
                code = 1
        lock.release()
        (ctx.out / "console.txt").write_text("\n".join(ctx.log_lines) + "\n", encoding="utf-8")
    return code


def load_sec6(slice_id):
    main = git_show("main:SPRINT-1-PLAN.md")
    try:
        if main is None:
            raise GateError("git show main:SPRINT-1-PLAN.md failed")
        return parse_section6(main, slice_id)
    except GateError as e:
        return e


def cmd_gate(a):
    ctx = Ctx("gate", a.through, budget=GATE_BUDGET_S)
    if ctx.killprobe:
        return killprobe_gate(ctx)
    entries = registry_upto(a.through)
    rows_wanted = []
    for s in entries:
        for r in s["fg"]:
            if r not in rows_wanted:
                rows_wanted.append(r)
    mode = "cold" if a.cold else "warm"
    state = {"rows": [], "not_run": []}

    def body():
        sec6 = load_sec6(a.through)
        mods = Mods(ctx)
        ctx.say(f"gate through {a.through} ({mode}): {len(rows_wanted)} FG rows of {[s['id'] for s in entries]}")
        try:
            state["rows"] += fg_rows(ctx, mods, sec6, rows_wanted, use_cache=not a.cold)
            # design section 5: <milestone-id>'s suite verdicts re-derived, never an earlier milestone's
            state["rows"] += suite_gate(ctx, mods, sec6, slice_entry(a.through), a.through)
        except BudgetExceeded as e:
            done = {r.name for r in state["rows"]}
            state["not_run"] = [r for r in rows_wanted if r not in done]
            ctx.say(f"BUDGET {e}; rows not run: {state['not_run']} and the suite evidence")
            return 1
        return 0 if all(not r.fails for r in state["rows"]) else 1

    code = with_bracket(ctx, body)
    failed = [r.name for r in state["rows"] if r.fails]
    secs = round(time.time() - ctx.t0, 1)
    verdict = "ok" if code == 0 and not failed and not state["not_run"] else "fail"
    print(f"GATE {verdict} through={a.through} mode={mode} rows={len(state['rows'])} failed={failed} "
          f"not_run={state['not_run']} rebaselines={ctx.shared.get('rebaselines', 0)} seconds={secs} out={ctx.out}",
          flush=True)
    return 0 if verdict == "ok" else 1


def suite_gate(ctx, mods, sec6, entry, through):
    """Step 12: the --through milestone's suite evidence re-derived, then the rotating live sample (rule
    3), with rule 5's extra group for a borderline timed ratio when it fits the gate's budget."""
    rows = []
    row = Row(f"suite_evidence:{entry['id']}")
    t = time.time()
    man_path = SUITES / f"{entry['id']}.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else None
    checks = suite_checks(ctx, mods, sec6)
    expected = {n: checks[n].key_fn() for n in entry["ss"]}
    fails, results = suite_evidence(ctx, entry["id"], manifest, expected, {n: checks[n].derive_fn for n in entry["ss"]})
    row.fails += fails
    row.detail = "; ".join(f"{n}: {r[2]}" for n, r in results.items())[:1500]
    ctx.say(f"ROW {'ok  ' if not row.fails else 'FAIL'} {row.name}: {row.detail} [{time.time() - t:.1f}s]")
    for f in row.fails[:10]:
        ctx.say(f"     - {f}")
    rows.append(row)
    if entry["id"] != through:
        return rows
    rng = random.Random(time.time_ns())
    for kind, pool in (("deterministic", entry["deterministic_ss"]), ("timed", entry["timed_ss"])):
        if not pool:
            continue
        pick = rng.choice(pool)
        lrow = Row(f"live_sample:{pick}")
        t = time.time()
        try:
            if pick == "t15b_m0":
                limits = sec6["limits"] if isinstance(sec6, dict) else {}
                t0 = time.time()
                dirs = [t15b_batch(ctx, mods, T15B["reps_gate"], [ctx.perf.MASK16], "t15b-m0", ctx.deadline)]
                took = time.time() - t0
                meas, f, detail = derive_t15b(dirs, limits, T15B["reps_gate"])
                rec = meas.get(f"{ctx.perf.MASK16:#x}") or {}
                if rec.get("undecided"):
                    fits, need = extra_batch_fits(took, 2 * T15B["reps_gate"], 2 * T15B["reps_extra"], time.time(),
                                                  ctx.deadline)
                    if fits:
                        ctx.say(f"     rule 5: M0t/M0t {rec['ratio']} is within {BORDERLINE} of {rec['borderline']:g}; "
                                f"one more batch of {T15B['reps_extra']} reps per config (about {need:.0f} s)")
                        dirs.append(t15b_batch(ctx, mods, T15B["reps_extra"], [ctx.perf.MASK16], "t15b-m0-x",
                                               ctx.deadline))
                        meas, f, detail = derive_t15b(dirs, limits, T15B["reps_gate"])
                    else:
                        f = [f"P18: M0t/M0t at 16 LP is {rec['ratio']}, within {BORDERLINE} of its bound "
                             f"{rec['borderline']:g}, and rule 5's batch of {T15B['reps_extra']} reps per config needs "
                             f"about {need:.0f} s, more than the {max(0.0, ctx.deadline - time.time()):.0f} s the gate "
                             f"has left: fail closed on this borderline ratio (TEST-STRATEGY 5.4)"]
            else:
                dirs = checks[pick].run_fn(ctx.deadline)
                meas, f, detail = checks[pick].derive_fn(dirs)
                stored = results.get(pick, ({}, [], ""))[0]
                if pick == "gst" and stored and meas.get("images") != stored.get("images"):
                    f.append("the live game self-test's preview hashes differ from the suite evidence")
            lrow.fails += f
            lrow.detail = f"{kind} live sample {pick}: {detail}"
        except BudgetExceeded:
            raise
        except Exception as e:
            lrow.fails.append(f"live sample crashed: {type(e).__name__}: {e}")
        ctx.say(f"ROW {'ok  ' if not lrow.fails else 'FAIL'} {lrow.name}: {lrow.detail} [{time.time() - t:.1f}s]")
        for f in lrow.fails[:10]:
            ctx.say(f"     - {f}")
        rows.append(lrow)
    return rows


def cmd_suite(a):
    ctx = Ctx("suite", a.slice)
    entry = slice_entry(a.slice)

    def body():
        sec6 = load_sec6(a.slice)
        mods = Mods(ctx)
        ok = True
        if not a.only:
            rows = fg_rows(ctx, mods, sec6, [r for s in registry_upto(a.slice) for r in s["fg"]], use_cache=False)
            ok = all(not r.fails for r in rows)
        checks = suite_checks(ctx, mods, sec6)
        names = [a.only] if a.only else entry["ss"]
        for n in names:
            if n not in checks:
                raise GateError(f"unknown suite check {n!r}; {sorted(checks)}")
        man_path = SUITES / f"{a.slice}.json"
        manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else \
            {"format": "tn-suite/1", "slice": a.slice, "checks": {}}
        for n in names:
            t = time.time()
            key = checks[n].key_fn()
            dirs = checks[n].run_fn(time.time() + 3600)
            meas, fails, detail = checks[n].derive_fn(dirs)
            manifest["checks"][n] = {"key": key, "run_dirs": [rel_ws(ctx, d) for d in dirs],
                                     "recorded": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": meas}
            ctx.say(f"SUITE {'ok  ' if not fails else 'FAIL'} {n}: {detail} [{time.time() - t:.1f}s]")
            for f in fails[:10]:
                ctx.say(f"     - {f}")
            ok = ok and not fails
            manifest["game_build"] = f"{GAME_VERSION} build {GAME_BUILD}"
            manifest["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            write_atomic(man_path, json.dumps(manifest, indent=1, default=str) + "\n")
        return 0 if ok else 1

    code = with_bracket(ctx, body)
    print(f"SUITE {'ok' if code == 0 else 'fail'} slice={a.slice} only={a.only or '-'} "
          f"seconds={round(time.time() - ctx.t0, 1)} manifest={SUITES / (a.slice + '.json')} out={ctx.out}", flush=True)
    return code


def cmd_install_check(a):
    entry = current_slice()
    ctx = Ctx("install-check", entry["id"])
    info = {}

    def body():
        cp = subprocess.run([sys.executable, str(HERE / "build_zip.py")], cwd=str(REPO), capture_output=True, text=True)
        res = [l for l in cp.stdout.splitlines() if l.startswith("RESULT ")]
        if cp.returncode != 0 or not res or not res[-1].startswith("RESULT ok"):
            raise GateError(f"tools/build_zip.py: {res[-1] if res else cp.stdout[-300:]}")
        zpath = Path(re.search(r"zip=(.+?) sha256=", res[-1]).group(1))
        digest = sha256_file(zpath)
        cfg = tnconfig.load()
        ms = f"ea-ic-{digest[:8]}-{ctx.stamp}"
        r = ctx.fh_plain(["modset", ms, "--add", zpath])
        if not r.startswith("RESULT ok"):
            raise GateError(f"fh.py modset {ms}: {r}")
        ctx.fh_plain(["modset", "ea-m0"])
        mods = Mods(ctx)
        d = mods.prepare(ms, "load")
        fails = g1(d.out) + g3(d.out) + g2(d.out, [cfg["identity"]["id"], "base"])
        log = (d.out / "factorio-current.log").read_text(encoding="utf-8", errors="replace") + stdout_of(d.out)
        if "Mod package read error" in log:
            fails.append("the load log holds 'Mod package read error'")
        pname = placeholder_preset(cfg)
        pv = preview(ctx, ms, "earth-preview", 256, preset=pname)
        v = preview(ctx, "ea-m0", "vanilla-preview", 256)
        fails += g1(pv.out) + g3(pv.out) + g1(v.out)
        a_img, b_img = (load_run_json(pv.out) or {}).get("images"), (load_run_json(v.out) or {}).get("images")
        if not a_img or a_img == b_img:
            fails.append("the Earth preview hash equals vanilla's")
        info.update(zip=str(zpath), sha=digest, modset=ms, earth=a_img, vanilla=b_img)
        for f in fails:
            ctx.say(f"FAIL {f}")
        return 0 if not fails else 1

    code = with_bracket(ctx, body)
    print(f"INSTALL-CHECK {'ok' if code == 0 else 'fail'} zip={info.get('zip')} sha256={info.get('sha')} "
          f"modset={info.get('modset')} earth_preview={list((info.get('earth') or {}).values())[:1]} "
          f"vanilla_preview={list((info.get('vanilla') or {}).values())[:1]} out={ctx.out}", flush=True)
    return code


def cmd_baseline(a):
    """Rewrite the measured values in tests/budgets.json and tests/baselines/ from fresh runs, each of
    which must pass G1 to G3 (and G2 for an Earth run), render exactly one image per seed (G4) and
    carry the three --verbose complexity lines where it records them; the placeholder preview must
    differ from M0's at every canonical seed (G5) and the block census must be complete. Any failed
    run refuses both files, which stay as they were."""
    entry = current_slice()
    ctx = Ctx("baseline", entry["id"])

    def body():
        mods = Mods(ctx)
        cfg = mods.cfg
        m0, m1 = mods.m0(), mods.m1()
        mods.prepare(m0, "m0")
        mods.prepare(m1, "m1")
        pname = placeholder_preset(cfg)
        fails = []

        def checked(r, earth, verbose=False):
            fails.extend(g1(r.out) + g3(r.out))
            if earth:
                fails.extend(g2(r.out, [cfg["identity"]["id"]]))
            try:
                got = derive_preview(r.out)
            except GateError as e:
                fails.append(str(e))
                return {"images": {}, "complexity": {}}
            if verbose and set(got["complexity"]) != {"tile", "entity", "cliff"}:
                fails.append(f"{r.out}: no Tile, Entity and Cliff complexity lines (--verbose)")
            return got

        c0 = checked(preview(ctx, m0, "cx-m0", 64, verbose=True), False, True)["complexity"]
        cd = checked(preview(ctx, m1, "cx-default", 64, verbose=True), True, True)["complexity"]
        cp = checked(preview(ctx, m1, "cx-placeholder", 64, preset=pname, verbose=True), True, True)["complexity"]
        if {k: v.get("complexity") for k, v in c0.items()} != VANILLA:
            fails.append(f"M0 complexity {c0} is not vanilla's {VANILLA} (G8: re-baseline the build pin first)")
        if cd != c0:
            fails.append("the default preset with Earth loaded compiles differently from M0 (T13 zero cost)")
        vanilla, earth = {}, {}
        for seed in SEEDS:
            g = checked(preview(ctx, m0, f"m0-256-{seed}", 256, seed=seed), False)
            vanilla[str(seed)] = g["images"].get(f"{seed}.png")
            g = checked(preview(ctx, m1, f"ph-256-{seed}", 256, preset=pname, seed=seed), True)
            earth[str(seed)] = g["images"].get(f"{seed}.png")
            if not vanilla[str(seed)] or not earth[str(seed)]:
                fails.append(f"seed {seed}: a preview wrote no {seed}.png")
            elif vanilla[str(seed)] == earth[str(seed)]:
                fails.append(f"seed {seed}: the placeholder preview equals M0's (G5)")
        m0t, _, _ = driver_modsets(ctx, mods)
        save = make_save(ctx, mods, m0t, "tq1-gen-block", T15B["block"], "census")
        r = ctx.fh(["scenario", "--instance", ctx.instance, "--modset", m0t, "--save", save, "--ticks", "10", "--",
                    "--threads", str(T15B["threads"])], ctx.out / "census")
        fails.extend(g1(r.out) + g3(r.out))
        census = ctx.perf.parse_forced(r.out).get("census") or {}
        if census.get("block_generated_before") != 0 or census.get("block_generated_after") != 256:
            fails.append(f"census run: block generated {census.get('block_generated_before')} -> "
                         f"{census.get('block_generated_after')} chunks, want 0 -> 256")
        keep = ("water_tiles", "trees", "enemies", "resources", "rocks", "cliffs")
        if any(census.get(k) is None for k in keep):
            fails.append(f"census run: missing counts {[k for k in keep if census.get(k) is None]}")
        if fails:
            for f in fails[:20]:
                ctx.say(f"FAIL {f}")
            raise GateError(f"baseline refused: {len(fails)} run checks failed; tests/budgets.json and "
                            f"tests/baselines/build-{GAME_BUILD}.json are unchanged")
        rows = budgets_rows(cfg, cp, c0, cd)
        write_atomic(BUDGETS, json.dumps({
            "format": "tn-budgets/1",
            "note": "Measured values only (ruling 3): complexity rows from 64 px --verbose previews at seed 1000. "
                    "Written by 'earth_test.py baseline'; the gate requires equality and reads thresholds from the "
                    "plan's section 6.",
            "game_build": f"{GAME_VERSION} build {GAME_BUILD}", "rows": rows}, indent=1) + "\n")
        write_atomic(BASELINES / f"build-{GAME_BUILD}.json", json.dumps({
            "format": "tn-baselines/1", "game_build": f"{GAME_VERSION} build {GAME_BUILD}",
            "note": "Vanilla and comparator hashes keyed by game build (G8), the placeholder preset's preview "
                    "hashes and the T15b block's census on M0. Written by 'earth_test.py baseline'.",
            "previews_256": {"M0": vanilla, "placeholder": earth},
            "t15b_block": {"chunks": T15B["block"], "census_m0": {k: census.get(k) for k in keep}},
        }, indent=1) + "\n")
        ctx.say(f"wrote {BUDGETS} ({len(rows)} rows) and {BASELINES / ('build-' + GAME_BUILD + '.json')}")
        return 0

    code = with_bracket(ctx, body)
    print(f"BASELINE {'ok' if code == 0 else 'fail'} seconds={round(time.time() - ctx.t0, 1)} out={ctx.out}", flush=True)
    return code


def cmd_freeze(a):
    entry = current_slice()
    ctx = Ctx("freeze", entry["id"])
    added = []

    def body():
        mods = Mods(ctx)
        cfg = mods.cfg
        schema = tnconfig.schema_problems(cfg)
        if schema:
            raise GateError(f"config.lua schema: {schema[:2]}; freeze registers nothing")
        # every dump the gate's frozen row reads (the registry's `dumps`): M1 is the one this runner
        # produces; a milestone that adds M2 adds its dump here and in the dumps row
        labels = [lb for s in registry_upto(entry["id"]) for lb in s.get("dumps", [])]
        dumps = {}
        for label in dict.fromkeys(labels):
            if label != "m1":
                raise GateError(f"freeze cannot produce the {label} dump yet; the slice that adds it extends freeze")
            r = mods.prepare(mods.m1(), "m1")
            dumps[label] = json.loads((r.out / "data-raw-dump.json").read_text(encoding="utf-8"))
        fz = json.loads((TESTS / "frozen.json").read_text(encoding="utf-8"))
        # placeholder names and the Map type fallbacks are never registered (U3's one exemption)
        skip = frozen_exempt(cfg)
        for label, dump in dumps.items():
            for name, (t, proto) in sorted(earth_bodies(dump, cfg).items()):
                if name in skip:
                    continue
                h = body_hash(proto)
                if name in fz["bodies"]:
                    if fz["bodies"][name]["sha256"] != h and fz["bodies"][name].get("dump", "m1") == label:
                        raise GateError(f"{name} changed in place: registered {fz['bodies'][name]['sha256'][:12]}, "
                                        f"now {h[:12]}; ship it under the next _v<n>")
                    continue
                fz["bodies"][name] = {"type": t, "sha256": h, "dump": label, "slice": entry["id"],
                                      "registered": time.strftime("%Y-%m-%d")}
                added.append(name)
        write_atomic(TESTS / "frozen.json", json.dumps(fz, indent=1) + "\n")
        return 0

    code = with_bracket(ctx, body)
    print(f"FREEZE {'ok' if code == 0 else 'fail'} added={len(added)} {added[:10]} out={ctx.out}", flush=True)
    return code


def operator_problem(stdin=None, stdout=None):
    """Why this process is not a person at an interactive terminal, or None. The guard's re-baseline
    is left to the maintainer (project rule 2: a dirty guard stops all game runs and is reported first on
    the parent issue; the plan defines no other re-baseline than a part's first command): it needs
    stdin and stdout on a console, so an unattended job's or a script's pipes are refused."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        if stdin is None or stdout is None or not stdin.isatty() or not stdout.isatty():
            return ("refuses: clearing the guard is Jake's, by hand at an interactive terminal (a console window; in "
                    "Git Bash prefix winpty); an unattended run stops and reports on the sprint parent issue")
    except (AttributeError, ValueError, OSError):
        return "refuses: no interactive terminal"
    return None


CHANGED_RE = re.compile(r"^CHANGED (.*) \[[^\]]*\] -> \[[^\]]*\]$")


def guard_check_lines(ctx, snap):
    """fh.py guard check of one snapshot, with its ADDED, REMOVED and CHANGED lines: (RESULT line,
    lines, changed paths). Launches no game."""
    cp = subprocess.run([sys.executable, str(ctx.fh_py), "guard", "check", str(snap)], cwd=str(ctx.ws),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=ctx.env())
    lines = (cp.stdout or "").splitlines()
    paths = []
    for l in lines:
        if l.startswith(("ADDED", "REMOVED")):
            paths.append(l.split(None, 1)[1].strip() if len(l.split(None, 1)) > 1 else "")
        else:
            m = CHANGED_RE.match(l)
            if m:
                paths.append(m.group(1).strip())
    res = next((l for l in reversed(lines) if l.startswith("RESULT ")), "RESULT none")
    return res, [l for l in lines if not l.startswith("RESULT ")], paths


def cmd_guard_rebaseline(a):
    """A manual re-baseline of the chained guard (G9), by hand only: after he has reviewed a dirty,
    unfinished or set-aside chain, a fresh snapshot becomes the chain's clean last entry, with his
    reason and the change he typed back logged in the chain and the journal (every later command
    prints it). It refuses without an interactive terminal, before it takes the lock or touches
    anything; then it shows fh.py guard check against the chain's last snapshot and the stray game
    logs, and goes on only when the operator types back every changed path. Launches no game."""
    why = operator_problem()
    if why:
        print(f"RESULT fail guard-rebaseline {why}", flush=True)
        return 1
    if not (a.reason or "").strip():
        print("RESULT fail guard-rebaseline needs --reason (what changed in the live profile and why it is safe)")
        return 1
    slice_id = checked_slice(a.slice or current_slice()["id"])
    ctx = Ctx("guard-rebaseline", slice_id)
    lock = Lock(ctx.root / "earth-test.lock")
    try:
        lock.acquire(ctx.cmd)
        guard = Guard(ctx, slice_entry(slice_id)["part"], recover=True)
        entries = guard.chain["entries"]
        last = entries[-1] if entries else None
        base = (last.get("end") or last.get("start")) if last else None
        print(f"G9 part {guard.part}: last entry {last and last.get('cmd')} {last and last.get('start')} "
              f"({'clean' if last and last.get('end') else 'dirty' if last and last.get('ended') else 'unfinished' if last else 'none'})")
        res, lines, paths = (guard_check_lines(ctx, guard.dir / base) if base else ("RESULT none (no snapshot)", [], []))
        for l in lines:
            print(f"  {l}")
        print(f"  {res}")
        stray = guard.stray_logs(Guard.chain_last_clean_end(guard.dir, entries))
        if stray:
            print(f"  game logs written after the chain's last clean end: {stray}")
        print("Type back every changed path listed above, one per line, then an empty line "
              "(type none when no path is listed):", flush=True)
        typed = []
        while True:
            line = input().strip()
            if not line:
                break
            typed.append(line)
        want = sorted(paths)
        ok = (typed == ["none"] and not want) or (sorted(typed) == want and want)
        if not ok:
            print(f"RESULT fail guard-rebaseline: the typed list {sorted(typed)} is not the changed list {want}; "
                  f"nothing re-baselined", flush=True)
            return 1
        res2 = guard.rebaseline(a.reason.strip(), reviewed={"base": base, "check": res, "changed": want,
                                                           "stray_logs": stray})
    except GateError as e:
        print(f"RESULT fail {e}", flush=True)
        return 1
    finally:
        lock.release()
    print(f"RESULT ok G9 re-baselined part {slice_entry(slice_id)['part']} by hand ({res2.split(' file=')[0]}); "
          f"reason: {a.reason.strip()}; chain {guard.chain_file}; log it on the sprint parent issue", flush=True)
    return 0


def cmd_static(a):
    if not (REPO / "terra-nauvis").exists():
        print("STATIC fail no terra-nauvis/ folder")
        return 1
    results = tn_static.run_rows()
    failed = [r["row"] for r in results if not r["ok"]]
    print(f"STATIC {'ok' if not failed else 'fail'} rows={len(results)} failed={failed}", flush=True)
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="every slice's testCommand")
    g.add_argument("--through", required=True)
    g.add_argument("--cold", action="store_true", help="ignore the FG cache: every FG key stale (timing the cold gate)")
    g.set_defaults(fn=cmd_gate)
    s = sub.add_parser("suite", help="the slice suite")
    s.add_argument("slice")
    s.add_argument("--only")
    s.set_defaults(fn=cmd_suite)
    sub.add_parser("install-check").set_defaults(fn=cmd_install_check)
    sub.add_parser("baseline").set_defaults(fn=cmd_baseline)
    sub.add_parser("static").set_defaults(fn=cmd_static)
    sub.add_parser("freeze").set_defaults(fn=cmd_freeze)
    r = sub.add_parser("guard-rebaseline", help="Jake's hand re-baseline of the chained live-profile guard (an "
                       "interactive terminal only; an unattended run stops and reports on the parent issue)")
    r.add_argument("--reason", required=True)
    r.add_argument("--slice", help="the slice whose part's chain to re-baseline (default: the newest slice)")
    r.set_defaults(fn=cmd_guard_rebaseline)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except GateError as e:
        print(f"RESULT fail {e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
