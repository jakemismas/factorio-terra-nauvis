#!/usr/bin/env python3
"""The Terra Nauvis gate runner (the design notes section 5; test notes.md section 1).

  python tools/earth_test.py gate --through <milestone> [--cold]   every milestone's testCommand, under 10 min
  python tools/earth_test.py suite <milestone> [--only <check>]     the milestone suite: raw runs and a manifest
  python tools/earth_test.py install-check                      every milestone's installCheck
  python tools/earth_test.py baseline                           rewrite the measured values in tests/
  python tools/earth_test.py static                             T16 static rows: no game, no workspace
  python tools/earth_test.py freeze                             register new Earth bodies (europe-coast on)

Rules this file implements (design section 5):
  1. Lock, budget. Every command that launches the game holds the workspace lock (a lock whose
     owner process is gone is free), runs every game launch through fh.py and requires G1 of each
     run: fh.py isolation is the only live-profile protection,
     and a run that may have left its instance stops the command. It reads the game build from its
     first real run (G8) and, for the gate, stops itself at 9 minutes. Every fh.py launch runs in a
     kill-on-close job object, so a killed runner leaves no game process behind.
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
import math
import os
import random
import re
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
import tnfrozen  # noqa: E402
import tnguard  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
PLAN = REPO / "SPRINT-1-PLAN.md"
TESTS = REPO / "tests"
BUDGETS = TESTS / "budgets.json"
BASELINES = TESTS / "baselines"
SUITES = BASELINES / "suites"
DEFAULT_WS = r"%FACTORIO_WS%"
# re-baselined from 2.1.23 build 87750 after Steam's 2026-10-29 update
GAME_VERSION, GAME_BUILD = "2.1.24", "87808"
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
COMMANDS = ("gate", "suite", "install-check", "baseline", "freeze")


class GateError(RuntimeError):
    pass


class BudgetExceeded(GateError):
    pass


class FatalRun(BaseException):
    """A game run that may have left its instance (run.json isolated not true, a NOT-ISOLATED
    RESULT) or ran on another build (G8): every further game run of the command stops at once.
    It derives from BaseException, so no row's or group loop's `except GateError` or `except
    Exception` swallows it; only with_lock catches it, after which the job is terminated before
    the lock is released (design constraint 1). It is raised through Ctx.fatal, which at the moment
    of the breach stops every later launch of the command (Ctx.stop) and terminates the job, so the
    runs other workers have in flight end too (run_lanes)."""


# ------------------------------------------------------------------------------------------------ milestones

# The runner's milestone registry (design note 2): per milestone its part, its fast-gate rows (FG),
# its suite checks (SS), which suite checks are deterministic or timed (rule 3's live sample), the
# oracle properties it ships, and the dumps whose Earth bodies the frozen row and freeze read
# (M1 here; climate-tiles adds M2). Each later milestone appends its entry. It stays one literal that no
# other module-level statement names: the static rows and the release build read it with
# tnfrozen.runner_registry, which fails closed otherwise, and a tests/frozen.json record's dump label
# must be one of these labels.
REGISTRY = [
    {"id": "toolchain", "part": 1, "order": 0,
     "fg": ["static", "plan_main", "section6", "data_src", "offline_selftests", "runner_controls",
            "dumps", "frozen", "t13_dump_facts", "isolation_b", "ab_withheld", "t13_zero_cost",
            "t13_preset_preview", "t13_scenario", "t15a_rows", "isolation_a"],
     "ss": ["gst", "t15b_m0", "walker_m0", "perf15", "rt_m0", "save_m0"],
     "deterministic_ss": ["gst"],
     "timed_ss": ["t15b_m0"],
     "oracle_properties": [],
     "dumps": ["m1"]},
    # Europe's coast at scales 1 to 6, its Map type entry, per-save values and the first timed
    # baselines (design section 8, milestone 0). The toolchain rows above run on the real Europe preset
    # from here: the placeholder is retired, and ab_withheld speaks for every preset withheld beside
    # Alien Biomes (Europe, until climate-tiles' palm switch).
    {"id": "europe-coast", "part": 2, "order": 0,
     "fg": ["ec_dump_facts", "geo_emit", "t1_t2_grids", "t3_oracle", "t11_pair", "t12_twice", "t13_routes",
            "maptype_route", "t16_guard", "water_inert"],
     "ss": ["t1_previews", "v1_sheets", "t1_corner", "t3_detail", "t11_values", "t18_drift", "maptype_cost",
            "t15b_m1", "walker_m1", "preview_time", "rt_m1", "save_m1", "hitch", "save_excess"],
     "deterministic_ss": ["t18_drift", "t1_corner"],
     "timed_ss": ["t15b_m1"],
     "oracle_properties": ["land", "water"],
     "dumps": ["m1"]},
    # City spawns by the shift, the spawn lake and land guarantee, inland lakes, the start message,
    # the RSO warning and the Nauvis-only guard (design section 8, milestone 1). Its suite re-times Europe
    # (the programs changed) through europe-coast's timed checks, which place through the shift.
    {"id": "spawn-cities", "part": 2, "order": 1,
     "fg": ["sc_dump_facts", "t14_walker", "t15b_geo", "t7_random", "t13_maptype_city"],
     "ss": ["t7_coastal", "t7_sweep", "t7_seeds", "t3_lakes", "t4_start_area", "t11_city", "t13_rso", "t18_player",
            "t14_planet", "t18_force_spawn", "v2_cities", "t15b_m1", "walker_m1", "rt_m1", "save_m1"],
     "deterministic_ss": ["t7_seeds", "t14_planet", "t18_force_spawn"],
     "timed_ss": ["t15b_m1"],
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
    leaves a truncated file (the cache index, suite manifests, baselines, frozen.json)."""
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


def landed_slices(refs=None):
    """The registry's milestones landed on the reference refs (main and origin/main): a milestone lands with
    its suite manifest (tests/baselines/suites/<id>.json), so a ref holding that file has landed it.
    A milestone counts as landed when any resolving ref holds it, so a stale ref never adds a milestone to
    the pending group (fewer pending milestones allow less growth). Fails closed when no ref resolves."""
    refs = list(refs) if refs is not None else tn_static.reference_refs()
    out, resolved = set(), 0
    for ref in refs:
        sha = tn_static.git_ref_commit(ref, REPO)
        if sha is None:
            continue
        resolved += 1
        for s in REGISTRY:
            cp = subprocess.run(["git", "cat-file", "-e", f"{sha}:tests/baselines/suites/{s['id']}.json"],
                                cwd=str(REPO), capture_output=True)
            if cp.returncode == 0:
                out.add(s["id"])
    if not resolved:
        raise GateError(f"none of the reference refs {refs} resolves: the landed slices are unknown (fail closed)")
    return out


def pending_slices(through, landed=None):
    """The milestones a gate through `through` measures over the landed state: every registry milestone up to
    `through` that no reference ref has landed, and `through` itself. The Group mode lands
    several milestones as one commit and gates them with the last one's testCommand, so that gate meets
    the group's allocations together."""
    landed = landed_slices() if landed is None else set(landed)
    return [s["id"] for s in registry_upto(through) if s["id"] not in landed or s["id"] == through]


def gate_evidence_slices(through, landed=None):
    """The registry entries whose suite evidence a gate through `through` re-derives and whose checks
    its live sample is drawn from (design section 5, step 12; rules 2 and 3): every pending milestone. The
    Group mode lands several milestones as one commit and runs only the last one's testCommand,
    so that gate is the one gate each milestone of the group meets on the tree that lands; it holds an
    earlier milestone of the group to that milestone's own manifest. A landed milestone's evidence is its
    landing's record, which a later milestone's edits stale by design, so no later gate re-derives it
."""
    return [slice_entry(s) for s in pending_slices(through, landed)]


def live_pools(entries):
    """Rule 3's two pools over the gated milestones: each deterministic and each timed suite check any of
    them names, once, in registry order."""
    det, timed = [], []
    for e in entries:
        det += [n for n in e["deterministic_ss"] if n not in det]
        timed += [n for n in e["timed_ss"] if n not in timed]
    return det, timed


def alloc_cells(sec6, slice_id):
    """A milestone's 6.3 cells: those in force (a fixture's own milestone among them), else the plan's row."""
    got = (sec6.get("allocations") or {}).get(slice_id) or (sec6.get("all_allocations") or {}).get(slice_id)
    if got is None:
        raise GateError(f"section 6.3 gives {slice_id!r} no allocation")
    return got


def batch_alloc_for(sec6, pending, prog, modset, map_key, variant=None):
    """One program's 6.3 allocation for a row over the pending milestones: a cap in any of them governs,
    then a first (the group records the first value, and only the limits apply), then a headroom
    rule (the latest one's); otherwise the adds sum and a none counts 0."""
    rules = [alloc_for(alloc_cells(sec6, s)[prog], modset, map_key, variant) for s in pending]
    for kind in ("cap", "first", "headroom"):
        hit = [r for r in rules if r["kind"] == kind]
        if hit:
            return hit[-1]
    return {"kind": "add", "value": sum(r["value"] for r in rules if r["kind"] == "add")}


P1_RELATIVE = 1.10      # 6.2 P1: at most (main's recorded ratio + the milestone's time allocation) x 1.10


def landed_p1_ratio(through, map_key, refs=None):
    """The M1t/M0t ratio at 16 LP a reference ref recorded for the map's block, the smaller over its
    scales and over the refs (the stricter base): read from the suite manifest of the latest milestone
    before `through` in registry order that the ref holds with a t15b_m1 record. None when no ref
    recorded one."""
    refs = list(refs) if refs is not None else tn_static.reference_refs()
    ids = [s["id"] for s in registry_upto(through)][:-1]
    best = None
    for ref in refs:
        sha = tn_static.git_ref_commit(ref, REPO)
        if sha is None:
            continue
        for sid in reversed(ids):
            text = git_show(f"{sha}:tests/baselines/suites/{sid}.json")
            summ = ((json.loads(text).get("checks") or {}).get("t15b_m1") or {}).get("summary") if text else None
            if not summ:
                continue
            got = [v.get(f"{0xFFFF:#x}") for k, v in summ.items() if k.startswith("scale_") and isinstance(v, dict)]
            got = [r for r in got if isinstance(r, (int, float))]
            if got:
                best = min(got) if best is None else min(best, min(got))
                break
    return best


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
    "P1": "derive_t15b_europe: M1t/M0t at 16 LP on the map's TQ1b block at scales 6 and 1 (suite check t15b_m1, "
          "its live sample)",
    "P4": "derive_rt_pair: ticks over 20 ms in each M1 window (suite check rt_m1)",
    "P5": "derive_rt_pair: the median p99 interval of M1 over M0's (suite check rt_m1)",
    "P6": "derive_rt_pair: the longest M1 interval (suite check rt_m1)",
    "P7": "derive_walker_pair: Earth scriptUpdate per tick over M0's in benchmark mode (suite check walker_m1)",
    "P19": "derive_save_pair: the forced block's save increment, M1 over M0 (suite check save_m1)",
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

    def release(self):
        if self.held:
            write_atomic(self.path, json.dumps({"pid": 0, "released": time.strftime("%Y-%m-%d %H:%M:%S")}))
            self.held = False


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
        self.locked = False
        if self.ws:
            self.fh_py = self.ws / "tools" / "fh.py"
            self.root = tnguard.absolute_output(os.environ["TN_OUT_ROOT"]) \
                if self.killprobe and os.environ.get("TN_OUT_ROOT") else self.ws / "previews" / "earth-build"
            self.out = self.root / cmd / f"{self.stamp}-{self.slice}"
            n = 1
            while self.out.exists():
                n += 1
                self.out = self.root / cmd / f"{self.stamp}-{self.slice}-{n}"
            root_r, out_r = self.root.resolve(), self.out.resolve()
            if out_r.parent != (root_r / cmd) or not out_r.is_relative_to(root_r):
                raise GateError(f"output directory {self.out} resolves outside {self.root}/{cmd}")
            self.out.mkdir(parents=True)
            import perf
            self.perf = perf
            self.job = perf.Job()
        self.build = None
        self.instance = {"gate": "ea-gate", "suite": "ea-suite", "baseline": "ea-base",
                         "install-check": "ea-ic", "freeze": "ea-freeze"}.get(cmd, "ea-gate")
        self.log_lines = []
        self.shared = {}
        # design constraint 1: set by the first FatalRun in any thread; from then on nothing launches
        self.stop = threading.Event()
        self.stop_reason = ""
        self.launch_lock = threading.Lock()

    # -- output
    def say(self, line):
        print(line, flush=True)
        self.log_lines.append(line)

    # -- design constraint 1
    def fatal(self, why):
        """At the moment a breach is seen, in whatever thread sees it: stop every later launch of
        this command and terminate the job now, which ends the game runs other workers have in flight;
        returns the FatalRun to raise. The launch lock makes the two one step against popen_text: a
        launch either joined the job before the terminate (and dies with it) or sees the stop and
        never starts. with_lock terminates the job again before it frees the lock."""
        with self.launch_lock:
            if not self.stop.is_set():
                self.stop_reason = why
                self.stop.set()
            job = getattr(self, "job", None)
            if job is not None:
                try:
                    job.terminate()
                except Exception:
                    pass
        return FatalRun(why)

    def halt_if_stopped(self, what):
        """FatalRun instead of `what` once a breach has stopped this command."""
        if self.stop.is_set():
            raise FatalRun(f"{what} not launched: an earlier run of this command stopped every further game run "
                           f"({self.stop_reason[:240]})")

    def check_budget(self, what):
        if self.deadline and time.time() > self.deadline:
            raise BudgetExceeded(f"the {GATE_BUDGET_S // 60}-minute budget ran out before {what}")

    def env(self):
        e = dict(os.environ)
        e["FACTORIO_WS"] = str(self.ws)
        e.setdefault("PYTHONIOENCODING", "utf-8")
        return e

    def popen_text(self, cmd, timeout, watcher=None, monitor=False):
        # every process of the command starts here, so this is where a stopped command stops launching
        with self.launch_lock:
            self.halt_if_stopped(" ".join(Path(str(c)).name for c in cmd[:3])[:160])
            p = self.job.popen([str(c) for c in cmd], cwd=str(self.ws), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=self.env())
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
        """fh.py subcommands that launch no game (modset, settings, compare). They run outside the
        job."""
        cp = subprocess.run([sys.executable, str(self.fh_py)] + [str(a) for a in args], cwd=str(self.ws),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            env=self.env())
        text = (cp.stdout or "") + (cp.stderr or "")
        lines = [l for l in text.splitlines() if l.startswith("RESULT ")]
        return lines[-1] if lines else "RESULT none " + text[-300:]

    def fh(self, args, out, timeout=600, watcher=None, monitor=False):
        """A game run through fh.py into a new --out, only while the command holds the workspace lock
        (the kill probe: under its parent's); checks the build pin (G8) on its stdout. A run that may
        have left its instance (tnguard.run_breach) or ran on another build raises FatalRun: no later
        game run of this command starts (design constraint 1)."""
        if not self.locked and not self.killprobe:
            raise GateError(f"fh.py {args[0]} outside the workspace lock: every game launch of a runner command holds "
                            f"it (hard rule 4)")
        self.halt_if_stopped(f"fh.py {args[0]} into {out}")
        self.check_budget(f"fh.py {args[0]}")
        out = Path(out)
        full = list(args[:1]) + ["--out", out] + list(args[1:]) if "--out" not in args else list(args)
        if "--timeout" not in full and args[0] in ("preview", "scenario", "dump-data", "run", "sample"):
            full = full[:1] + ["--timeout", str(timeout)] + full[1:]
        code, text, mon = self.popen_text([sys.executable, self.fh_py] + full, timeout + 300, watcher, monitor)
        r = Run(full, code, text, out)
        r.mon = mon
        why = tnguard.run_breach(out, r.result)
        if why:
            raise self.fatal(f"fh.py {args[0]} into {out}: {why}")
        if self.stop.is_set():
            # another worker's breach terminated the job while this run was in flight: it means nothing
            raise FatalRun(f"fh.py {args[0]} into {out} was ended by an earlier run that stopped every further game "
                           f"run ({self.stop_reason[:240]})")
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
                raise self.fatal(f"G8: the game is {got[0]} build {got[1]}, not {GAME_VERSION} build {GAME_BUILD}: "
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
        """What a modset holds, for row keys: every file's sha256 and every folder's hash, with
        mod-list.json taken as its mods and their enabled flags. fh.py modset and the game write
        that file in different layouts (149 and 153 bytes for one list, measured), so its bytes
        would key a row on which program touched the modset last in this command."""
        d = self.ctx.ws / "test-instance" / "modsets" / modset
        items = []
        for p in sorted(d.iterdir()):
            if p.name in ("mod-settings.dat",) or p.name.startswith("mod-settings.dat."):
                continue
            if p.is_file() and p.name == "mod-list.json":
                try:
                    listed = json.loads(p.read_text(encoding="utf-8")).get("mods") or []
                    items.append((p.name, key_of(sorted([str(m.get("name")), bool(m.get("enabled"))]
                                                        for m in listed if isinstance(m, dict)))))
                    continue
                except (OSError, ValueError, AttributeError):
                    pass
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


KILLPROBE_INSTANCE = "ea-killprobe"


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


NOISE_TYPES = tnfrozen.NOISE_TYPES
FREEZE_CMD = "python tools/earth_test.py freeze"


def earth_bodies(dump, cfg):
    """Every Earth noise body of a dump as {name: (type, prototype)} (tnfrozen.earth_bodies, which the
    static rows and the release build share)."""
    return tnfrozen.earth_bodies(dump, cfg)


def frozen_exempt(cfg):
    """The names never registered (U3's one exemption plus the placeholder): the placeholder's names
    and the Map type fallbacks that mirror a startup setting. A frozen fallback is registered like
    every Earth body, so no later version moves the worlds that read it."""
    return tnfrozen.exempt_names(cfg)


def frozen_check(fz_work, fz_main, dumps, cfg, registry=None):
    """The frozen-body checker (design constraint 2): tests/frozen.json keeps the
    tnfrozen contract, every record well formed against the runner's milestone registry (a dump label
    that no registry entry assigns, or that the record's milestone could not have produced, fails and is
    never skipped, since the label picks the dump the body is read from); it is append-only against
    the reference, whole records compared (type, sha256, dump, milestone and date), so a relabel moves a
    registered record as a new hash does; every registered body is present in the dump its record
    names with the same generation-field hash; no placeholder name or Map type fallback is
    registered; and every Earth body of every dump the gate reads (M1, and M2 once a milestone adds it)
    is registered, the placeholder's names and the fallbacks excepted, so a body can neither ship
    unregistered nor change in place unseen. `dumps` maps a dump label ("m1", "m2") to its data-raw
    dump. No registered body goes unread: a record whose dump label this command did not produce
    fails like an unknown label, a later milestone's dump included (the gate through an earlier milestone
    cannot vouch for that body; run it through the newest milestone, which produces every label). Only
    `dumps=None` reads no dump, for the controls that test the append-only comparison alone."""
    registry = REGISTRY if registry is None else registry
    fails = []
    if dumps is not None and not isinstance(dumps, dict):
        dumps = {"m1": dumps}
    fails += tnfrozen.file_problems(fz_work, registry)
    bodies = (fz_work or {}).get("bodies") if isinstance((fz_work or {}).get("bodies"), dict) else {}
    for name, rec in ((fz_main or {}).get("bodies") or {}).items():
        if name not in bodies:
            fails.append(f"{name} is registered on the reference but missing from tests/frozen.json (append-only)")
            continue
        changed = tnfrozen.record_changes(bodies[name], rec)
        if changed:
            fails.append(f"{name}: tests/frozen.json changed the registered record's {changed} (append-only: a "
                         f"record never changes in place; ship a change under the next _v<n>)")
    ph = set(tnconfig.placeholder_names(cfg)) if cfg else set()
    fb = set(tnconfig.exempt_fallback_names(cfg)) if cfg else set()
    for name, rec in bodies.items():
        if name in ph:
            fails.append(f"placeholder name {name} is registered")
        if name in fb:
            fails.append(f"Map type fallback {name} is registered (a fallback that mirrors a startup setting never is; "
                         f"U3)")
        if dumps is None or tnfrozen.record_problems(name, rec, registry):
            continue
        label = rec["dump"]
        if label not in dumps:
            fails.append(f"registered body {name}: its record's dump label {label!r} names a dump this command did not "
                         f"produce ({sorted(dumps)}), so its hash and presence would go unchecked (fail closed: run "
                         f"the gate through a slice that produces {label!r})")
            continue
        body = (dumps[label].get(rec["type"]) or {}).get(name)
        if body is None:
            fails.append(f"registered body {name} is missing from the {label} dump (old names stay defined)")
        elif body_hash(body) != rec["sha256"]:
            fails.append(f"registered body {name} changed in place (ship it under the next _v<n>)")
    exempt = ph | fb
    for label, dump in sorted((dumps or {}).items()):
        for name in sorted(earth_bodies(dump, cfg)):
            if name not in exempt and name not in bodies:
                fails.append(f"Earth body {name} of the {label} dump is not registered in tests/frozen.json "
                             f"(sacred constraint 2): register it with {FREEZE_CMD}")
    return fails


def freeze_registry(fz, dumps, cfg, slice_id, today, registry=None):
    """What `freeze` writes, or GateError: every existing record must keep the tnfrozen contract (a
    dump label no registry entry assigns, or a typo of one, refuses the run instead of being
    skipped) and match the dump it names in type and hash (present, never changed in place); no
    placeholder name or setting-mirroring fallback may be registered; then every Earth body of the
    dumps that is not yet registered is appended with a full record for `slice_id`. Returns (the new
    registry, the names added); it never changes an existing record."""
    registry = REGISTRY if registry is None else registry
    probs = tnfrozen.file_problems(fz, registry)
    if probs:
        raise GateError(f"tests/frozen.json breaks the record contract: {probs[:2]}; freeze registers nothing")
    skip = frozen_exempt(cfg)
    bad = sorted(set(fz["bodies"]) & skip)
    if bad:
        raise GateError(f"tests/frozen.json registers {bad}, which are never registered (the placeholder's names, the "
                        f"fallbacks that mirror a startup setting; U3); freeze registers nothing")
    for name, rec in sorted(fz["bodies"].items()):
        if rec["dump"] not in dumps:
            raise GateError(f"{name} is registered from the {rec['dump']} dump, which this freeze did not produce; "
                            f"freeze registers nothing")
        body = (dumps[rec["dump"]].get(rec["type"]) or {}).get(name)
        if body is None:
            raise GateError(f"registered body {name} is missing from the {rec['dump']} dump (old names stay defined); "
                            f"freeze registers nothing")
        h = body_hash(body)
        if h != rec["sha256"]:
            raise GateError(f"{name} changed in place: registered {rec['sha256'][:12]}, now {h[:12]}; ship it under "
                            f"the next _v<n>")
    out = json.loads(json.dumps(fz))
    added = []
    for label, dump in dumps.items():
        for name, (t, proto) in sorted(earth_bodies(dump, cfg).items()):
            if name in skip or name in out["bodies"]:
                continue
            out["bodies"][name] = tnfrozen.record(t, body_hash(proto), label, slice_id, today)
            added.append(name)
    probs = tnfrozen.file_problems(out, registry)
    if probs:
        raise GateError(f"freeze would write a registry that breaks the record contract: {probs[:2]}")
    return out, added


GEN_FIELDS = tnfrozen.HASH_FIELDS


def body_hash(proto):
    """sha256 of a noise body's generation fields only (never intended_property, localised_name, order):
    tnfrozen.body_hash, which the offline body check (T16, the release build) shares."""
    return tnfrozen.body_hash(proto)


def offline_parity(dumps, cfg, source=MOD):
    """The offline data stage (tools/tnlua.py) held to the game: every dump's Earth bodies and the
    offline ones are the same names with the same generation fields. CI's bodies row and the release
    build judge registered bodies by the offline reading alone, so a disagreement fails here instead
    of letting them misjudge a body. Returns (failures, {label: bodies compared})."""
    try:
        off = tnfrozen.offline_bodies(source, cfg)
    except Exception as e:  # tnlua.LuaError and anything else: fail closed
        return [f"the offline data stage did not run: {type(e).__name__}: {e} (fail closed)"], {}
    fails, seen = [], {}
    for label, dump in sorted((dumps or {}).items()):
        game = earth_bodies(dump, cfg)
        seen[label] = len(game)
        for name in sorted(set(game) ^ set(off)):
            where = "the offline data stage" if name in off else f"the {label} dump"
            fails.append(f"offline parity: {name} is defined by {where} only (tools/tnlua.py and the game disagree)")
        for name in sorted(set(game) & set(off)):
            gt, gp = game[name]
            ot, op = off[name]
            want = {k: gp.get(k) for k in GEN_FIELDS if k in gp}
            got = {k: op.get(k) for k in GEN_FIELDS if k in op}
            if gt != ot or want != got:
                diff = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k)) or ["type"]
                fails.append(f"offline parity: {name} differs between the {label} dump and the offline data stage "
                             f"in {diff} (tools/tnlua.py and the game disagree)")
    return fails, seen


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


FX_DATE = "2026-10-28"
# A two-milestone fixture registry: fx-b adds a dump, so a label can be assigned yet not one fx-a produced.
FX_REGISTRY = [{"id": "fx-a", "dumps": ["m1"]}, {"id": "fx-b", "dumps": ["m1", "m2"]}]
_DROP = object()


def fx_registry(bodies):
    """A tests/frozen.json fixture holding `bodies` under the tnfrozen contract."""
    return {"format": tnfrozen.FORMAT, "hash_fields": list(tnfrozen.HASH_FIELDS), "bodies": bodies}


def fx_record(proto, dump="m1", slice_id=None):
    """A well-formed record of `proto` for the live registry's current milestone (or `slice_id`)."""
    return tnfrozen.record(proto.get("type", "noise-expression"), body_hash(proto), dump,
                           slice_id or REGISTRY[-1]["id"], FX_DATE)


def fx_edited(fz, name, **fields):
    """A copy of the fixture registry `fz` with `name`'s record fields set (or dropped, with _DROP)."""
    out = json.loads(json.dumps(fz))
    for k, v in fields.items():
        if v is _DROP:
            out["bodies"][name].pop(k, None)
        else:
            out["bodies"][name][k] = v
    return out


def unassigned_label(registry=None):
    """A dump label of the registry's own form (m<n>) that no entry assigns: what a hand relabel to a
    later milestone's dump reads as before that milestone lands."""
    labels = tnfrozen.assigned_labels(REGISTRY if registry is None else registry)
    return next(f"m{i}" for i in range(1, 1000) if f"m{i}" not in labels)


def _refuses(fn, needle):
    """Whether fn raises the GateError whose message holds `needle` (another refusal is no proof)."""
    try:
        fn()
    except GateError as e:
        return needle in str(e)
    return False


def frozen_controls(cfg):
    """The frozen checker and freeze on fixture dumps and registries: a changed hash, a missing name
    and an unregistered Earth body fail (naming the freeze command); a GUI-only change, the
    placeholder's names and a Map type fallback left unregistered pass. Every record field is held
    to the contract and never skips the check: a record relabeled to a dump no registry entry
    assigns (with its body unchanged, changed in place or dropped), a typo of a label, a missing
    label, a label its milestone could not have produced, an unknown milestone, an undefined field, a bad
    date or hash and a file without the hash's field list each fail; a landed record relabeled to
    another assigned dump, retyped, re-sliced or re-dated fails the append-only comparison; a
    well-formed record whose dump this command did not produce (a later milestone's) fails too, so no
    registered body goes unread; freeze refuses each broken registry and a body changed in place
    under a relabel, and appends full records."""
    prefix = cfg["identity"]["noise_prefix"]
    name = f"{prefix}fixture_v1"
    body = {"type": "noise-expression", "name": name, "expression": "x + 1"}
    reg = fx_registry({name: fx_record(body)})
    d_ok = {"noise-expression": {name: body}}
    d_changed = {"noise-expression": {name: dict(body, expression="x + 2")}}
    d_missing = {"noise-expression": {}}
    d_gui = {"noise-expression": {name: dict(body, intended_property="elevation", order="z", localised_name=["x"])}}
    d_new = {"noise-expression": {name: body,
                                  f"{prefix}fixture_elevation_europe_v1": dict(body, name="x", expression="x")},
             "noise-function": {f"{prefix}fixture_fn_v1": {"type": "noise-function", "expression": "a",
                                                          "parameters": ["a"]}}}
    ph = tnconfig.placeholder_names(cfg)
    d_ph = {"noise-expression": dict({n: dict(body, name=n) for n in ph}, **{name: body})}
    # the fallbacks live in each geography version: these fixtures replace the newest version's
    fb_cfg = tn_static.cfg_version(cfg, fallbacks=[{"name": f"{prefix}fixture_fallback", "map_qualified": False}])
    d_fb = {"noise-expression": {name: body, f"{prefix}fixture_fallback": dict(body, name="f")}}
    # a frozen fallback (a constant a landed entry reads) is registered like every body
    fz_name = f"{prefix}fixture_frozen_v1"
    fz_cfg = tn_static.cfg_version(cfg, fallbacks=[{"name": fz_name, "map_qualified": False, "frozen": True}])
    fz_body = {"type": "noise-expression", "name": fz_name, "expression": "0"}
    d_fz = {"noise-expression": {name: body, fz_name: fz_body}}
    reg_fz = fx_registry(dict(reg["bodies"], **{fz_name: fx_record(fz_body)}))
    d_fz_moved = {"noise-expression": {name: body, fz_name: dict(fz_body, expression="32")}}
    new_fails = frozen_check(reg, reg, {"m1": d_new}, cfg)
    out = {"changed hash fails": bool(frozen_check(reg, reg, {"m1": d_changed}, cfg)),
           "missing name fails": bool(frozen_check(reg, reg, {"m1": d_missing}, cfg)),
           "GUI-only change passes": not frozen_check(reg, reg, {"m1": d_gui}, cfg),
           "an unregistered Earth expression and function fail and name the freeze command": (
               len(new_fails) == 2 and all(FREEZE_CMD in f for f in new_fails)),
           "an unregistered body of the M2 dump fails too": bool(frozen_check(reg, reg, {"m1": d_gui, "m2": d_new},
                                                                             cfg)),
           "the placeholder's names stay unregistered": (not frozen_check(reg, reg, {"m1": d_ph}, cfg)) if ph else True,
           "a Map type fallback stays unregistered": not frozen_check(reg, reg, {"m1": d_fb}, fb_cfg),
           "a frozen Map type fallback left unregistered fails": bool(frozen_check(reg, reg, {"m1": d_fz}, fz_cfg)),
           "a registered frozen Map type fallback passes": not frozen_check(reg_fz, reg_fz, {"m1": d_fz}, fz_cfg),
           "a frozen Map type fallback moved in place fails": bool(frozen_check(reg_fz, reg_fz, {"m1": d_fz_moved},
                                                                                fz_cfg))}
    # every record field, the dump label first: each broken record fails although no reference holds
    # it (the reference is the record itself), so the failure is the contract's, never a skip
    other = unassigned_label()
    relabel = fx_edited(reg, name, dump=other)
    broken = {
        f"a record relabeled to {other}, a dump no registry entry assigns, fails with its body unchanged":
            (relabel, d_ok, f"dump {other!r} is no label"),
        f"a record relabeled to {other} fails with its body changed in place": (relabel, d_changed,
                                                                              f"dump {other!r} is no label"),
        f"a record relabeled to {other} fails with its body dropped from the dump": (relabel, d_missing,
                                                                                   f"dump {other!r} is no label"),
        "a typo of a dump label (M1) fails": (fx_edited(reg, name, dump="M1"), d_ok, "dump 'M1' is no label"),
        "a record without a dump label fails (it never defaults to m1)": (fx_edited(reg, name, dump=_DROP), d_ok,
                                                                          "lacks ['dump']"),
        "a record naming a slice the registry lacks fails": (fx_edited(reg, name, slice="no-such-slice"), d_ok,
                                                             "slice 'no-such-slice' is no slice"),
        "a record holding a field the contract does not define fails": (fx_edited(reg, name, note="x"), d_ok,
                                                                        "holds ['note']"),
        "a record with a malformed date fails": (fx_edited(reg, name, registered="28/10/2026"), d_ok,
                                                 "registered '28/10/2026' is not"),
        "a record with a malformed sha256 fails": (fx_edited(reg, name, sha256="Z" * 64), d_ok, "sha256 is not"),
        "a record of an unknown type fails": (fx_edited(reg, name, type="noise-thing"), d_ok,
                                              "type 'noise-thing' is not"),
        "a registry without the hash's field list fails": ({k: v for k, v in reg.items() if k != "hash_fields"},
                                                            d_ok, "hash_fields None")}
    for label, (fz, dump, needle) in broken.items():
        out[label] = any(needle in f for f in frozen_check(fz, fz, {"m1": dump}, cfg))
    a_rec = fx_registry({name: tnfrozen.record("noise-expression", body_hash(body), "m1", "fx-a", FX_DATE)})
    out["a record whose dump its slice could not have produced fails"] = any(
        "freeze produces through fx-a" in f for f in frozen_check(
            fx_edited(a_rec, name, dump="m2"), fx_edited(a_rec, name, dump="m2"), {"m1": d_ok, "m2": d_ok}, cfg,
            registry=FX_REGISTRY))
    landed = {
        "a landed record relabeled to another assigned dump": fx_edited(a_rec, name, dump="m2", slice="fx-b"),
        "a landed record re-sliced": fx_edited(a_rec, name, slice="fx-b"),
        "a landed record re-dated": fx_edited(a_rec, name, registered="2026-10-29"),
        "a landed record retyped": fx_edited(a_rec, name, type="noise-function")}
    for label, fz in landed.items():
        out[f"{label} fails the append-only comparison"] = any(
            "changed the registered record" in f for f in frozen_check(fz, a_rec, {"m1": d_ok, "m2": d_ok}, cfg,
                                                                        registry=FX_REGISTRY))
    later = fx_edited(a_rec, name, dump="m2", slice="fx-b")
    out["a later slice's dump this command did not produce fails (no registered body goes unread)"] = any(
        "did not produce" in f for f in frozen_check(later, later, {"m1": d_ok}, cfg, registry=FX_REGISTRY))
    out["the same record passes once the command produces its dump"] = not frozen_check(
        later, later, {"m1": d_ok, "m2": d_ok}, cfg, registry=FX_REGISTRY)
    # freeze: the same contract before it writes, and full records when it does
    sid = REGISTRY[-1]["id"]
    try:
        new_fz, added = freeze_registry(reg, {"m1": d_new}, cfg, sid, FX_DATE)
        ok = (sorted(added) == sorted([f"{prefix}fixture_elevation_europe_v1", f"{prefix}fixture_fn_v1"]) and
              new_fz["bodies"][name] == reg["bodies"][name] and not tnfrozen.file_problems(new_fz, REGISTRY) and
              all(new_fz["bodies"][n]["slice"] == sid and new_fz["bodies"][n]["dump"] == "m1" for n in added))
    except GateError:
        ok = False
    out["freeze appends a full record for each new body and keeps every existing record"] = ok
    for label, (fz, dump, needle) in {
            f"freeze refuses a record relabeled to {other}": (relabel, d_ok, "is no label"),
            f"freeze refuses a record relabeled to {other} whose body changed in place": (relabel, d_changed,
                                                                                         "is no label"),
            "freeze refuses a typo of a dump label": (fx_edited(reg, name, dump="M1"), d_ok, "is no label"),
            "freeze refuses a record without a dump label": (fx_edited(reg, name, dump=_DROP), d_ok, "lacks ['dump']"),
            "freeze refuses a registered body changed in place": (reg, d_changed, "changed in place"),
            "freeze refuses a registered body missing from its dump": (reg, d_missing, "is missing from the m1 dump")
    }.items():
        out[label] = _refuses(lambda fz=fz, dump=dump: freeze_registry(fz, {"m1": dump}, cfg, sid, FX_DATE), needle)
    return out


def reference_registry():
    """The append-only reference of design constraint 2: the union of tests/frozen.json at every
    reference ref that resolves (main and origin/main; tn_static.reference_files), so a stale local
    main cannot hide a body origin/main registers. Returns (registry, {ref: commit}, failures): an
    unreadable reference fails closed, never an empty registry."""
    try:
        texts = tn_static.reference_files("tests/frozen.json", REPO)
        regs = {ref: json.loads(text) for ref, (_, text) in texts.items()}
    except (tn_static.ReferenceUnreadable, ValueError) as e:
        return {"bodies": {}}, {}, [f"the append-only reference is unreadable: {e} (fail closed)"]
    union, probs = tn_static.frozen_union(regs)
    return {"bodies": union["bodies"]}, {ref: sha for ref, (sha, _) in texts.items()}, probs


def row_frozen(ctx, mods, sec6, row, cache):
    cfg = mods.cfg
    work = json.loads((TESTS / "frozen.json").read_text(encoding="utf-8"))
    main, ref_shas, ref_fails = reference_registry()
    row.fails += ref_fails
    dumps = gate_dumps(ctx, ctx.slice)
    row.fails += frozen_check(work, main, dumps, cfg)
    seen = sorted({n for d in dumps.values() for n in earth_bodies(d, cfg)})
    # the offline data stage, which CI's bodies row and the release build judge bodies by, held to the
    # game's dumps; then the registry held to the offline bodies, as those two hold it
    par, par_seen = offline_parity(dumps, cfg)
    row.fails += par
    if not par:
        row.fails += tnfrozen.body_problems(tnfrozen.offline_bodies(MOD, cfg), work, cfg)
    # every earlier milestone of the group landed its registry in its suite manifest's snapshot
    try:
        snaps, unsnapped = tnfrozen.suite_snapshots(REGISTRY, before=ctx.slice, suites=SUITES)
    except tnfrozen.RegistryUnreadable as e:
        snaps, unsnapped = {}, {}
        row.fails.append(f"the earlier slices' suite manifests are unreadable: {e}")
    row.fails += tnfrozen.snapshot_problems(work, snaps)
    row.fails += tnfrozen.unsnapshotted_problems(work, unsnapped, main)
    ctl = frozen_controls(cfg)
    ctl.update(snapshot_controls())
    ctl.update(offline_controls(ctx, dumps, work, cfg))
    try:
        ctl["the static reading of the runner's registry (CI, the release build) equals the live REGISTRY"] = (
            tnfrozen.runner_registry(HERE / "earth_test.py") == REGISTRY)
    except tnfrozen.RegistryUnreadable:
        ctl["the static reading of the runner's registry (CI, the release build) equals the live REGISTRY"] = False
    reg = sorted((work.get("bodies") or {}))
    if reg and "m1" in dumps:
        victim = reg[0]
        t_ = (work["bodies"][victim].get("type") or "noise-expression")
        changed = json.loads(json.dumps({t_: dumps["m1"].get(t_) or {}}))
        if victim in changed[t_]:
            changed[t_][victim]["expression"] = str(changed[t_][victim].get("expression")) + " + 0"
            fx = dict(dumps["m1"], **changed)
            ctl["a fixture changing registered " + victim + " in the real dump fails (registered, not yet released)"] = any(
                "changed in place" in f for f in frozen_check(work, work, {"m1": fx}, cfg))
            # the review's case: the same change, or the body dropped, with the record's dump label
            # edited by hand to a dump no milestone assigns yet, or mistyped
            dropped = json.loads(json.dumps({t_: dumps["m1"].get(t_) or {}}))
            del dropped[t_][victim]
            fx_drop = dict(dumps["m1"], **dropped)
            ctl[f"the real dump without registered {victim} fails (old names stay defined)"] = any(
                "is missing from the m1 dump" in f for f in frozen_check(work, work, {"m1": fx_drop}, cfg))
            own = str(work["bodies"][victim].get("dump"))
            for lb in (unassigned_label(), own.upper() if own.upper() != own else own + "x"):
                edited = fx_edited(work, victim, dump=lb)
                ctl[f"the real dump with {victim} changed and its dump label edited to {lb!r} fails"] = any(
                    f"dump {lb!r} is no label" in f for f in frozen_check(edited, edited, {"m1": fx}, cfg))
                ctl[f"the real dump without {victim} and its dump label edited to {lb!r} fails"] = any(
                    f"dump {lb!r} is no label" in f for f in frozen_check(edited, edited, {"m1": fx_drop}, cfg))
                ctl[f"landed {victim} relabeled to {lb!r} fails the append-only comparison"] = any(
                    "changed the registered record" in f for f in frozen_check(edited, work, dumps, cfg))
    # the reference read fails closed: a ref that does not resolve, or one without the file, raises
    for label, (path, refs) in {
            "a reference ref that does not resolve fails closed": ("tests/frozen.json",
                                                                   ["refs/heads/tn-gate-no-such-ref"]),
            "a resolving reference ref without the registry fails closed": ("tests/tn-gate-no-such-file.json",
                                                                            ["HEAD"])}.items():
        try:
            tn_static.reference_files(path, REPO, refs)
            ctl[label] = False
        except tn_static.ReferenceUnreadable:
            ctl[label] = True
    if reg:
        landed = {"format": "tn-frozen/1", "bodies": json.loads(json.dumps(work["bodies"]))}
        stale = {"format": "tn-frozen/1", "bodies": {n: r for n, r in landed["bodies"].items() if n != reg[0]}}
        moved = json.loads(json.dumps(work))
        moved["bodies"][reg[0]]["sha256"] = "0" * 64
        union, _ = tn_static.frozen_union({"main": stale, "origin/main": landed})
        ctl["a hash changed in place fails against origin/main when a stale local main lacks the body"] = any(
            "changed the registered record" in f for f in frozen_check(moved, {"bodies": union["bodies"]}, None, cfg))
    for k, ok in ctl.items():
        if not ok:
            row.fails.append(f"frozen checker positive control did not behave: {k}")
    refs_seen = ", ".join(f"{r} {s[:8]}" for r, s in sorted(ref_shas.items())) or "no reference"
    snaps_seen = ", ".join(f"{k.split(chr(39))[0]} ({len((v or {}).get('bodies') or {})} records)"
                           for k, v in sorted(snaps.items())) or "none before this slice"
    row.detail = (f"{len(work.get('bodies', {}))} registered bodies, each record holding the tnfrozen contract (dump "
                  f"labels the registry assigns: {tnfrozen.assigned_labels(REGISTRY)}), whole records append-only "
                  f"against {refs_seen} and the earlier slices' snapshots ({snaps_seen}); every one read from the "
                  f"dump its record names (none unread) and built offline by tools/tnlua.py at its hash, the offline "
                  f"bodies equal to the game's ({par_seen} compared); Earth bodies of the {sorted(dumps)} "
                  f"dumps {seen}, every one registered or exempt (placeholder, fallbacks); {sum(ctl.values())} of "
                  f"{len(ctl)} controls behaved")


def snapshot_controls():
    """The snapshot rule on a two-milestone fixture registry: an earlier milestone's snapshot keeps only the
    records registered through it (a later milestone's own redo stays open), passes the registry it was
    taken from and a later milestone's changed record, and fails its record re-hashed, dropped, or
    re-registered by the later milestone (a new milestone and date), a snapshot edited by hand, and a record
    of a milestone without a snapshot that no reference holds."""
    out = {}
    a = {"type": "noise-expression", "name": "tn_fx_a_v1", "expression": "1"}
    b = {"type": "noise-expression", "name": "tn_fx_b_v1", "expression": "2"}
    fz = fx_registry({a["name"]: fx_record(a, slice_id="fx-a"), b["name"]: fx_record(b, slice_id="fx-b")})
    snap = tnfrozen.snapshot(fz, FX_REGISTRY, "fx-a")
    out["snapshot: an earlier slice's snapshot holds its records and leaves a later slice's out"] = (
        sorted(snap["bodies"]) == [a["name"]])
    out["snapshot: the registry it was taken from passes"] = not tnfrozen.snapshot_problems(fz, {"fx-a": snap})
    later = fx_edited(fz, b["name"], sha256="5" * 64)
    out["snapshot: a later slice redoing its own record passes the earlier slice's snapshot"] = (
        not tnfrozen.snapshot_problems(later, {"fx-a": snap}))
    dropped = json.loads(json.dumps(fz))
    del dropped["bodies"][a["name"]]
    redone = fx_edited(fz, a["name"], slice="fx-b", registered="2026-10-29")
    edited = json.loads(json.dumps(snap))
    edited["bodies"][a["name"]]["sha256"] = "6" * 64
    for label, (wfz, snaps, needle) in {
            "an earlier slice's record re-hashed in place fails": (fx_edited(fz, a["name"], sha256="7" * 64),
                                                                  {"fx-a": snap}, "changed the record"),
            "an earlier slice's record dropped fails": (dropped, {"fx-a": snap}, "missing from tests/frozen.json"),
            "an earlier slice's record re-registered by a later slice fails": (redone, {"fx-a": snap},
                                                                               "changed the record"),
            "a snapshot edited by hand fails closed": (fz, {"fx-a": edited}, "does not cover its bodies")}.items():
        out[f"snapshot: {label}"] = any(needle in f for f in tnfrozen.snapshot_problems(wfz, snaps))
    out["snapshot: a record of a slice without a snapshot that no reference holds fails closed"] = any(
        "fail closed" in f for f in tnfrozen.unsnapshotted_problems(fz, {"fx-a": "no suite manifest"}, {"bodies": {}}))
    out["snapshot: a record of a slice without a snapshot that a reference holds passes"] = not (
        tnfrozen.unsnapshotted_problems(fz, {"fx-a": "no suite manifest"}, {"bodies": dict(fz["bodies"])}))
    return out


def offline_controls(ctx, dumps, work, cfg):
    """The offline body check sees a body changed through its code: a copy of the mod whose spawn lake
    reads half its distance (the review's probe) differs from the game's dump and fails its registered
    record, while the unchanged mod passes both."""
    out = {}
    if "m1" not in dumps:
        return {"offline: the controls need the M1 dump": False}
    fx = ctx.out / "offline-fixture" / MOD.name
    if fx.exists():
        return {"offline: the fixture folder is new": False}
    shutil.copytree(MOD, fx)
    p = fx / "prototypes" / "expressions" / "spawn.lua"
    text = p.read_text(encoding="utf-8")
    probe = text.replace('lake_d = "sqrt(', 'lake_d = "0.5 * sqrt(', 1)
    if probe == text:
        return {"offline: the probe edit applies to spawn.lua": False}
    p.write_text(probe, encoding="utf-8", newline="\n")
    lakes = sorted(n for n in tnfrozen.offline_bodies(fx, cfg)
                   if n.startswith(f"{cfg['identity']['noise_prefix']}spawn_lake"))
    par, _ = offline_parity({"m1": dumps["m1"]}, cfg, source=fx)
    out["offline: the spawn lake changed in its code differs from the game's dump"] = bool(lakes) and all(
        any(n in f for f in par) for n in lakes)
    registered = [n for n in lakes if n in (work.get("bodies") or {})]
    probs = tnfrozen.body_problems(tnfrozen.offline_bodies(fx, cfg), work, cfg)
    out["offline: the spawn lake changed in its code fails its registered record"] = bool(registered) and all(
        any(n in f and "changed in place" in f for f in probs) for n in registered)
    out["offline: the unchanged mod passes its registered records"] = not tnfrozen.body_problems(
        tnfrozen.offline_bodies(MOD, cfg), work, cfg)
    return out


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


def evidence_rows(ctx_like, entries, checks, suites=SUITES, say=None):
    """Step 12's re-derivation over the gated milestones (gate_evidence_slices): one row per milestone, holding
    every suite check the milestone names to its own manifest under rule 2 (suite_evidence). Returns the
    rows and {milestone id: {check: (meas, fails, detail)}} of what re-derived."""
    rows, results = [], {}
    for entry in entries:
        row = Row(f"suite_evidence:{entry['id']}")
        t = time.time()
        man_path = Path(suites) / f"{entry['id']}.json"
        manifest = None
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else None
        except ValueError as e:
            row.fails.append(f"{rel_repo(man_path)} is unreadable ({e}): run python tools/earth_test.py suite "
                             f"{entry['id']}")
        if manifest is not None and not isinstance(manifest, dict):
            row.fails.append(f"{rel_repo(man_path)} holds no manifest object: run python tools/earth_test.py suite "
                             f"{entry['id']}")
            manifest = None
        known = [n for n in entry["ss"] if n in checks]
        row.fails += [f"the runner defines no suite check {n} that {entry['id']} names" for n in entry["ss"]
                      if n not in checks]
        fails, res = suite_evidence(ctx_like, entry["id"], manifest, {n: checks[n].key_fn() for n in known},
                                    {n: checks[n].derive_fn for n in known})
        row.fails += fails
        results[entry["id"]] = res
        row.detail = "; ".join(f"{n}: {r[2]}" for n, r in res.items())[:1500]
        if say:
            say(f"ROW {'ok  ' if not row.fails else 'FAIL'} {row.name}: {row.detail} [{time.time() - t:.1f}s]")
            for f in row.fails[:10]:
                say(f"     - {f}")
        rows.append(row)
    return rows, results


def stored_evidence(pick, entries, results):
    """The re-derived measurements of `pick` a live sample is compared with: those of the latest gated
    milestone whose evidence holds it (a check two milestones of a group both record is compared with the
    newer record). None when no gated milestone's evidence re-derived it."""
    for e in reversed(entries):
        got = (results.get(e["id"]) or {}).get(pick)
        if got is not None:
            return got[0]
    return None


def live_compare(kind, pick, live, stored):
    """Rule 3's comparison of a live sample with the suite evidence: a deterministic row's live
    measurements equal its evidence's, re-derived from the stored raw outputs, exactly; a timed row
    meets section 6 in its own derivation and is never compared for equality."""
    if kind != "deterministic":
        return []
    if stored is None:
        return [f"no re-derived suite evidence of {pick} to compare the live run with (rule 3)"]
    a, b = (json.loads(json.dumps(x, sort_keys=True, default=str)) for x in (live, stored))
    if a == b:
        return []
    keys = sorted(str(k) for k in set(a) | set(b) if a.get(k) != b.get(k)) \
        if isinstance(a, dict) and isinstance(b, dict) else []
    return [f"the live run of {pick} measured differently from its suite evidence"
            f"{' in ' + ', '.join(keys[:8]) if keys else ''} (rule 3: deterministic rows compare exactly)"]


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
    out["every 6.2 row in force through europe-coast has an enforcing check"] = (not unenforced_limits(ec),
                                                                                  unenforced_limits(ec))
    # a row that first comes into force in a later milestone, before its consumer lands
    ct = parse_section6(main, "climate-tiles")
    out["a row in force with no enforcing check fails closed (climate-tiles' P2 before its consumer lands)"] = (
        "P2" in unenforced_limits(ct), unenforced_limits(ct)[:3])
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
    # europe-coast's own allocation (+400 Entity for tn_land_coarse and the start mask, Cliff 0, Tile cap)
    ec = parse_section6(main, "europe-coast")
    eu = {"row": "map", "map": "europe", "modset": "M1", "scale": 6, "toggles": "on"}
    out["T15a: a Europe row's Entity growth over europe-coast's +400 fails"] = bool(check_t15a(
        [van, dict(eu, programs=prog(82000, ent + 401, VANILLA["cliff"]))], ec, [], "europe-coast"))
    out["T15a: a Europe row's Cliff growth over europe-coast's 0 fails"] = bool(check_t15a(
        [van, dict(eu, programs=prog(82000, ent, VANILLA["cliff"] + 1))], ec, [], "europe-coast"))
    out["T15a: a Europe row over P10's Tile cap fails"] = bool(check_t15a(
        [van, dict(eu, programs=prog(116001, ent, VANILLA["cliff"]))], ec, [], "europe-coast"))
    out["T15a: a Europe row within europe-coast's allocation passes"] = not check_t15a(
        [van, dict(eu, programs=prog(82000, ent + 400, VANILLA["cliff"]))], ec, [], "europe-coast")
    # a group (the build lands several milestones as one commit and gates them with the last one): its
    # gate meets every pending milestone's allocation together, a cap or first in any governing and adds
    # summing; one milestone gated alone meets its own
    sc = parse_section6(main, "spawn-cities")
    batch = ["europe-coast", "spawn-cities"]
    grown = dict(eu, programs=prog(83000, ent + 600, VANILLA["cliff"]))
    out["T15a: a batch whose earlier slice caps Tile passes Tile growth past the later slice's +700"] = not check_t15a(
        [van, grown], sc, [], "spawn-cities", batch)
    out["T15a: the same Tile growth gated on spawn-cities alone fails (+700)"] = bool(check_t15a(
        [van, grown], sc, [], "spawn-cities", ["spawn-cities"]))
    out["T15a: a batch's Entity adds sum (+400 and +200 pass +600)"] = not check_t15a(
        [van, grown], sc, [], "spawn-cities", batch)
    out["T15a: a batch's Entity adds sum (+601 fails)"] = bool(check_t15a(
        [van, dict(eu, programs=prog(83000, ent + 601, VANILLA["cliff"]))], sc, [], "spawn-cities", batch))
    out["pending: an unlanded earlier slice joins the batch, a landed one does not, the gated slice always does"] = (
        pending_slices("spawn-cities", {"toolchain"}) == batch and
        pending_slices("spawn-cities", {"toolchain", "europe-coast"}) == ["spawn-cities"] and
        pending_slices("spawn-cities", {"toolchain", "europe-coast", "spawn-cities"}) == ["spawn-cities"])
    first = batch_alloc_for(sc, batch, "time", "M1", "europe")
    alone = batch_alloc_for(sc, ["spawn-cities"], "time", "M1", "europe")
    out["P1: a batch over europe-coast's first ratio records it (first); spawn-cities alone adds 0.03"] = (
        first["kind"] == "first" and alone == {"kind": "add", "value": 0.03})
    p1 = p1_limits(sc, "spawn-cities", "europe", batch).get("P1", {}).get("limit")
    out["P1: the batch's bound is the absolute 1.5"] = p1 == {"max": 1.5}
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


def fatal_run_controls():
    """Design constraint 1: a game run that may have left its instance, or one on another build,
    stops the whole command (no game, no live profile; scratch run directories and a stub
    command). A run.json with isolated false or unknown, a scenario step not isolated, and a
    NOT-ISOLATED or isolated=NO RESULT line are breaches; an isolated run and a launch fh.py refused
    (no run.json) are not. FatalRun is no Exception: fg_rows passes it through and runs no later
    row; Ctx.check_build raises it on another build; with_lock catches it and terminates the job
    while it still holds the lock, which it then releases."""
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
        killed = []
        stub = types.SimpleNamespace(build=None, perf=perf, say=lambda line: None, stop=threading.Event(),
                                     stop_reason="", launch_lock=threading.Lock(),
                                     job=types.SimpleNamespace(terminate=lambda: killed.append(True)))
        stub.fatal = types.MethodType(Ctx.fatal, stub)
        try:
            Ctx.check_build(stub, b)
            raised = False
        except FatalRun:
            raised = True
        out["fatal: G8, a run on another build, stops the command and terminates the job at once"] = (
            raised and stub.stop.is_set() and killed == [True], f"stopped {stub.stop.is_set()}, terminate calls {killed}")

        class LockCtx:
            def __init__(self, root):
                self.root, self.ws, self.out = root, root, root / "out"
                self.out.mkdir(parents=True)
                self.cmd, self.slice, self.stamp = "gate", "toolchain", time.strftime("%Y%m%d-%H%M%S")
                self.log_lines, self.shared, self.locked, self.calls = [], {}, False, []
                lock_file = root / "earth-test.lock"
                self.job = types.SimpleNamespace(terminate=lambda: self.calls.append(
                    "terminate, lock free" if Lock.is_free(lock_file) else "terminate, lock held"))

            def say(self, line):
                self.log_lines.append(line)
        lc = LockCtx(td / "lock")

        def body():
            raise FatalRun("fixture breach")
        code = with_lock(lc, body)
        out["fatal: with_lock catches FatalRun, terminates the job while it holds the lock, then frees the lock"] = (
            code == 1 and any(l.startswith("FATAL ") for l in lc.log_lines) and lc.calls == ["terminate, lock held"]
            and Lock.is_free(lc.root / "earth-test.lock") and not lc.locked, lc.calls)
        out.update(lane_stop_controls(td / "lanes"))
    return out


LANE_STUB = """import json, os, sys, time
from pathlib import Path
a = sys.argv[1:]
out = Path(a[a.index("--out") + 1])
with open(os.environ["TN_LANE_LOG"], "a", encoding="utf-8") as f:
    f.write("%.6f %s\\n" % (time.time(), out.name))
out.mkdir(parents=True, exist_ok=True)
bad = out.name == os.environ.get("TN_LANE_BREACH")
(out / "run.json").write_text(json.dumps({"exit": 0, "isolated": not bad, "error_lines": []}), encoding="utf-8")
# the breach reports late enough that every lane's first run has started and logged its launch
time.sleep(0.5 if bad else float(os.environ["TN_LANE_SLEEP"]))
print("RESULT ok exit=0 isolated=" + ("NO" if bad else "yes") + " errors=0", flush=True)
"""


def lane_stop_controls(td):
    """Design constraint 1 across workers, with the real run_lanes, Ctx.fh, Ctx.popen_text and a real
    kill-on-close job, launching a stub in place of fh.py (no game): four workers of five jobs. With
    worker 0's first run a breach (its run.json records isolated false) and every other run sleeping
    20 s, FatalRun reaches the caller within seconds, the job is terminated, at most one run per worker
    was launched (the breach and the runs already in flight beside it), no run started after the
    terminate, and Ctx.fh launches nothing once the command is stopped. Positive control: the same
    workers without the breach launch all twenty runs."""
    import perf
    out = {}

    class LaneCtx:
        fh, fatal, halt_if_stopped, popen_text, check_build, check_budget = (
            Ctx.fh, Ctx.fatal, Ctx.halt_if_stopped, Ctx.popen_text, Ctx.check_build, Ctx.check_budget)

        def __init__(self, root, breach, sleep):
            self.root, self.ws = root, root
            self.locked, self.killprobe, self.deadline, self.build, self.perf = True, False, None, None, perf
            self.stop, self.stop_reason, self.launch_lock = threading.Event(), "", threading.Lock()
            self.fh_py = root / "fh_stub.py"
            self.fh_py.write_text(LANE_STUB, encoding="utf-8")
            self.log = root / "launches.txt"
            self.extra = {"TN_LANE_LOG": str(self.log), "TN_LANE_BREACH": breach or "", "TN_LANE_SLEEP": str(sleep)}
            self.real_job, self.terminated = perf.Job(), []
            parent = self

            class JobProxy:
                def popen(self, cmd, **kw):
                    return parent.real_job.popen(cmd, **kw)

                def terminate(self):
                    parent.terminated.append(time.time())
                    parent.real_job.terminate()
            self.job = JobProxy()

        def say(self, line):
            pass

        def env(self):
            e = dict(os.environ)
            e.update(self.extra)
            return e

        def launches(self):
            got = []
            text = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
            for line in text.splitlines():
                parts = line.split()
                if len(parts) == 2:
                    try:
                        got.append((float(parts[0]), parts[1]))
                    except ValueError:
                        pass
            return got

    def lanes_for(root):
        return [[(None, ["version", "--instance", f"lane-{i}", "--modset", f"lane-{i}"], root / "runs" / f"l{i}-j{j}", 60)
                 for j in range(5)] for i in range(4)]

    for label, breach, sleep in (("breach", "l0-j0", 20.0), ("clean", None, 0.2)):
        root = Path(td) / label
        root.mkdir(parents=True)
        lc = LaneCtx(root, breach, sleep)
        t0 = time.time()
        raised = False
        try:
            run_lanes(lc, lanes_for(root))
        except FatalRun:
            raised = True
        took = time.time() - t0
        got = lc.launches()
        if breach:
            per_lane = {}
            for _, name in got:
                per_lane[name.split("-")[0]] = per_lane.get(name.split("-")[0], 0) + 1
            first_kill = min(lc.terminated) if lc.terminated else None
            late = [n for ts, n in got if first_kill is None or ts > first_kill]
            out["fatal: a breach in one lane reaches the caller and terminates the job at once"] = (
                raised and bool(lc.terminated) and took < 15, f"raised {raised}, {len(lc.terminated)} terminate calls, "
                                                               f"{took:.1f} s")
            out["fatal: after a breach in one lane no lane launches another run"] = (
                ("l0-j0" in [n for _, n in got]) and all(v == 1 for v in per_lane.values()) and not late,
                f"launched {sorted(n for _, n in got)}; after the terminate: {late}")
            before = len(got)
            try:
                lc.fh(["version", "--instance", "lane-x", "--modset", "lane-x"], root / "runs" / "after", timeout=60)
                refused = False
            except FatalRun:
                refused = True
            out["fatal: Ctx.fh launches nothing once the command is stopped"] = (
                refused and len(lc.launches()) == before, f"refused {refused}")
        else:
            out["fatal: positive control, the same lanes without a breach launch all twenty runs"] = (
                not raised and len(got) == 20 and not lc.terminated, f"{len(got)} launches, raised {raised}")
        lc.real_job.close()
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


def slice_id_controls():
    """A crafted milestone id never reaches the file system: gate and suite refuse it before any path is
    built (Ctx validates it first), so nothing appears in a scratch workspace."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="tn-sliceid-") as td:
        ws = Path(td) / "ws"
        (ws / "tools").mkdir(parents=True)
        (ws / "tools" / "fh.py").write_text("raise SystemExit('the slice-id control never runs fh.py')\n",
                                            encoding="utf-8")
        env = dict(os.environ)
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


def gate_evidence_controls():
    """Step 12 over a group: the gate re-derives the suite evidence of
    every milestone it lands and draws its live sample over their checks; an earlier milestone of the group
    whose manifest is missing, unreadable, stale or failing fails the gate under its own refresh
    command; a deterministic live sample must equal its re-derived evidence, a timed one meets
    section 6 instead."""
    out = {}

    def ids(through, landed):
        return [e["id"] for e in gate_evidence_slices(through, landed)]
    ec, sc = slice_entry("europe-coast"), slice_entry("spawn-cities")
    batch = ids("spawn-cities", {"toolchain"})
    out["gate evidence: a batch's gate re-derives every pending slice's suite evidence"] = (
        batch == ["europe-coast", "spawn-cities"], str(batch))
    alone = (ids("spawn-cities", {"toolchain", "europe-coast"}), ids("europe-coast", {"toolchain"}),
             ids("spawn-cities", {"toolchain", "europe-coast", "spawn-cities"}))
    out["gate evidence: a landed slice's evidence is never re-derived; the gated slice's always is"] = (
        alone == (["spawn-cities"], ["europe-coast"], ["spawn-cities"]), str(alone))
    det, timed = live_pools(gate_evidence_slices("spawn-cities", {"toolchain"}))
    want_det = list(dict.fromkeys(ec["deterministic_ss"] + sc["deterministic_ss"]))
    want_timed = list(dict.fromkeys(ec["timed_ss"] + sc["timed_ss"]))
    out["live sample: a batch's pools hold every pending slice's checks, each once"] = (
        det == want_det and timed == want_timed and all(n in det for n in ec["deterministic_ss"]), f"{det} {timed}")
    det1, timed1 = live_pools(gate_evidence_slices("spawn-cities", {"toolchain", "europe-coast"}))
    out["live sample: a slice gated alone draws from its own pools"] = (
        det1 == sc["deterministic_ss"] and timed1 == sc["timed_ss"], f"{det1} {timed1}")
    with tempfile.TemporaryDirectory(prefix="tn-gate-evidence-") as td:
        td = Path(td)

        class FakeCtx:
            ws = td
        suites = td / "suites"
        suites.mkdir()

        def run_dir(name, code):
            d = td / "runs" / name
            d.mkdir(parents=True)
            (d / "run.json").write_text(json.dumps({"exit": code, "isolated": True, "error_lines": []}),
                                        encoding="utf-8")
            return f"runs/{name}"
        good_a, good_b, bad_a = run_dir("a-good", 0), run_dir("b-good", 0), run_dir("a-bad", 1)

        def derive(dirs):
            return {"runs": len(dirs)}, sum((g1(d) for d in dirs), []), "fixture"
        checks = {"a": SuiteCheck("a", lambda: "ka", None, derive), "b": SuiteCheck("b", lambda: "kb", None, derive)}
        early = {"id": "fx-early", "ss": ["a"], "deterministic_ss": ["a"], "timed_ss": []}
        late = {"id": "fx-late", "ss": ["b"], "deterministic_ss": ["b"], "timed_ss": []}

        def manifest(slice_id, name, key, rd):
            (suites / f"{slice_id}.json").write_text(json.dumps(
                {"format": "tn-suite/1", "slice": slice_id, "checks": {name: {"key": key, "run_dirs": [rd]}}}),
                encoding="utf-8")

        def verdict():
            rows, _ = evidence_rows(FakeCtx, [early, late], checks, suites)
            return {r.name: r.fails for r in rows}
        manifest("fx-late", "b", "kb", good_b)
        v = verdict()
        e_f = v.get("suite_evidence:fx-early") or []
        out["gate evidence: an earlier batch slice without a manifest fails under its own suite command"] = (
            bool(e_f) and "suite fx-early --only a" in e_f[0] and not v.get("suite_evidence:fx-late"), str(v)[:200])
        (suites / "fx-early.json").write_text("{not json", encoding="utf-8")
        v = verdict()
        out["gate evidence: an earlier batch slice's unreadable manifest fails, not crashes"] = (
            any("unreadable" in x for x in v.get("suite_evidence:fx-early") or []), str(v)[:200])
        manifest("fx-early", "a", "old", good_a)
        v = verdict()
        e_f = v.get("suite_evidence:fx-early") or []
        out["gate evidence: an earlier batch slice's stale key fails under its own suite command"] = (
            bool(e_f) and "stale" in e_f[0] and "suite fx-early --only a" in e_f[0], str(v)[:200])
        manifest("fx-early", "a", "ka", bad_a)
        v = verdict()
        out["gate evidence: an earlier batch slice's failing raw outputs fail"] = (
            any("exit=1" in x for x in v.get("suite_evidence:fx-early") or []), str(v)[:200])
        manifest("fx-early", "a", "ka", good_a)
        v = verdict()
        out["gate evidence: every gated slice's current evidence passes"] = (
            set(v) == {"suite_evidence:fx-early", "suite_evidence:fx-late"} and not any(v.values()), str(v)[:200])
        rows, _ = evidence_rows(FakeCtx, [dict(early, ss=["a", "zz"]), late], checks, suites)
        out["gate evidence: a check a slice names that the runner lacks fails"] = (
            any("no suite check zz" in x for x in rows[0].fails), str(rows[0].fails)[:200])
    corner = {"scale_3": {"with_offset": 0.991846, "without_offset": 0.990839}}
    out["live sample: a deterministic run equal to its re-derived evidence passes"] = (
        not live_compare("deterministic", "t1_corner", corner, json.loads(json.dumps(corner))), "")
    moved = {"scale_3": {"with_offset": 0.991846, "without_offset": 0.99}}
    out["live sample: a deterministic run differing from its evidence fails"] = (
        bool(live_compare("deterministic", "t1_corner", moved, corner)), "")
    out["live sample: a deterministic run without re-derived evidence fails"] = (
        bool(live_compare("deterministic", "t1_corner", corner, None)), "")
    out["live sample: a timed run meets section 6, never equality"] = (
        not live_compare("timed", "t15b_m1", {"0xffff": {"ratio": 1.01}}, {"0xffff": {"ratio": 1.03}}), "")
    res = {"fx-early": {"t": ({"v": 1}, [], ""), "a": ({"v": 3}, [], "")}, "fx-late": {"t": ({"v": 2}, [], "")}}
    two = [dict(early, timed_ss=["t"]), dict(late, timed_ss=["t"])]
    out["live sample: a check two batch slices record compares with the later one's evidence"] = (
        stored_evidence("t", two, res) == {"v": 2} and stored_evidence("a", two, res) == {"v": 3} and
        stored_evidence("b", two, res) is None, "")
    return out


def review_fix_controls():
    """Controls for europe-coast's review fixes: the far-field switch finder, the entity compare, the
    water-slider walk, the withheld presets and the read-back."""
    out = {}
    fl = -100
    win = [(x, 0) for x in range(-2, 3)]
    clean = {(-2, 0): {"f": fl}, (-1, 0): {"f": fl}, (0, 0): {"f": -1}, (1, 0): {"f": float("inf")},
             (2, 0): {"f": float("inf")}}
    sw = edge_switch(win, clean, "f", fl)
    out["the far-field switch finder finds a clean switch"] = (bool(sw) and min(q[0] for q in sw[0]) == 0, str(sw)[:80])
    out["a window without a switch reads as none"] = (
        edge_switch(win, {q: {"f": float("inf")} for q in win}, "f", fl) is None, "")
    out["an unrecognized value reads as no switch"] = (
        edge_switch(win, {**clean, (1, 0): {"f": "unrecognized"}}, "f", fl) is None, "")
    a = [("tree", 1.5, 2.5, ""), ("iron-ore", 3.5, 3.5, "500")]
    out["equal entity lists differ by 0"] = (entity_difference(a, list(a)) == 0, "")
    out["a moved entity counts twice"] = (entity_difference(a, [("tree", 1.5, 3.5, ""), a[1]]) == 2, "")
    out["a changed resource amount counts"] = (entity_difference(a, [a[0], ("iron-ore", 3.5, 3.5, "600")]) == 2, "")
    dump = {"planet": {"nauvis": {"map_gen_settings": {"autoplace_controls": {}, "autoplace_settings": {
        "tile": {"settings": {"t1": {}, "t2": {}}}, "entity": {"settings": {}}, "decorative": {"settings": {}}}}}},
        "tile": {"t1": {"autoplace": {"probability_expression": "wl_x * 2"}},
                 "t2": {"autoplace": {"probability_expression": "var('control:water:frequency') + 1"}}},
        "noise-expression": {"wl_x": {"expression": "10 * log2(control:water:size)"}}, "noise-function": {}}
    readers = water_readers(dump)
    _, r_all = walk_water(dump, {}, readers)
    _, r_baked = walk_water(dump, {"wl_x": 0}, readers)
    out["the water walk finds a body that reads control:water:*"] = ("wl_x" in r_all, str(r_all))
    out["the water walk finds an autoplace that reads the control itself"] = ("tile:t2:probability" in r_all,
                                                                               str(r_all))
    out["a reader baked as a number reads nothing"] = ("wl_x" not in r_baked, str(r_baked))
    cfg = {"presets": {"europe": {"name": "p-europe", "map": "europe", "withheld_with": ["alien-biomes"]},
                       "other": {"name": "p-other", "map": "europe"}}}
    out["a preset is withheld beside a listed mod"] = (withheld_beside(cfg, ["alien-biomes"]) == {"p-europe": "europe"},
                                                       "")
    out["no preset is withheld without a listed mod"] = (withheld_beside(cfg, ["rso-mod"]) == {}, "")
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
    for group in (fatal_run_controls, oracle_controls, gst_replay_controls, review_fix_controls, t7_ore_controls,
                  gate_evidence_controls):
        try:
            results.update(group())
        except Exception as e:
            results[f"{group.__name__} ran"] = (False, f"{type(e).__name__}: {e}")
    if ctx.killprobe:
        results["slice id controls skipped inside the kill probe"] = (True, "")
    else:
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


def probe_games(perf, root_pid):
    """{pid: start time} of every live game process whose ancestry reaches root_pid (a process keeps
    its parent's pid after the parent exits, so an orphan whose parent chain is intact still counts)."""
    procs = perf.processes()
    parent = {pid: ppid for pid, ppid, _ in procs}
    out = {}
    for pid, _, name in procs:
        if name.lower() != perf.GAME_IMAGE:
            continue
        q, hops = parent.get(pid), 0
        while q and hops < 12:
            if q == root_pid:
                st = perf.process_start_time(pid)
                if st is not None:
                    out[pid] = st
                break
            q, hops = parent.get(q), hops + 1
    return out


def kill_control(ctx):
    """Start a fixture gate that launches a long game run through fh.py, hard-kill it the moment its
    game process appears, then require that no game process of the probe remains and that the
    fixture lock is free (dead owner; TST-12). The probe's games are the ones descended from it,
    recorded with their start times before the kill and checked by pid and start time after it, so
    a game another run runs on the shared machine is neither the probe's nor a failure: the
    control leaves it alone and counts it in its detail."""
    if ctx.killprobe:
        return True, "skipped inside the kill probe"
    perf = ctx.perf
    td = ctx.out / "kill-probe"
    td.mkdir(parents=True)
    lock = td / "fixture.lock"
    env = ctx.env()
    env.update({"TN_KILLPROBE": "1", "TN_LOCK_FILE": str(lock), "TN_OUT_ROOT": str(td / "root")})
    with ctx.launch_lock:
        ctx.halt_if_stopped("the kill control's probe gate")
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
    own = probe_games(perf, p.pid)
    own.setdefault(game, perf.process_start_time(game))
    perf.terminate_pid(p.pid)
    p.wait(30)

    def own_left():
        alive = {pid for pid, st in own.items() if st is not None and perf.process_alive(pid, st)}
        return sorted(alive | set(probe_games(perf, p.pid)))
    t1 = time.time()
    while time.time() - t1 < 20 and own_left():
        time.sleep(0.25)
    left = own_left()
    others = sorted(set(perf.game_pids()) - set(left))
    free = Lock.is_free(lock)
    ok = not left and free and lock_before.get("pid") == p.pid
    return ok, (f"probe pid {p.pid} held the fixture lock, its game pid {game} was running; after a hard kill "
                f"{len(left)} of its game processes remain and the lock is {'free' if free else 'HELD'}" +
                (f" ({len(others)} game processes of other sessions left alone)" if others else ""))


def killprobe_gate(ctx):
    """Inside the kill control's child: its parent gate holds the workspace lock, so the long game
    run sits under it; take the fixture lock and start the run."""
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
    presets = d1["map-gen-presets"]["default"]
    scale = int(cfg["settings"]["scale"]["default_value"])
    pname, p = None, None
    for key in cfg["preset_order"]:
        pc = cfg["presets"][key]
        pname, p = pc["name"], presets.get(pc["name"])
        if not p:
            row.fails.append(f"preset {pname} is missing from the dump")
            continue
        want_pen = expected_pen(cfg, pc["map"], scale)
        got_pen = (p.get("basic_settings") or {}).get("property_expression_names")
        if got_pen != want_pen:
            row.fails.append(f"preset {pname} property_expression_names {got_pen}, want {want_pen} (config.lua)")
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
    # only the newest version of each map's elevation entry carries the Map type fields (D2 amended)
    entries = {g["entry"] for g in tnconfig.geography(cfg).values()}
    for n in earth_noise:
        b = d1["noise-expression"].get(n)
        if b and b.get("intended_property") and n not in entries:
            row.fails.append(f"{n} carries intended_property, but only the newest elevation entry of a map may")
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


AB_MODS = ["alien-biomes"]          # the row runs beside Alien Biomes whichever presets it withholds


def withheld_beside(cfg, mods_loaded):
    """{preset name: map key} of the Terra Nauvis presets presets.lua withholds while the mods in
    `mods_loaded` are loaded (config.lua's presets.<key>.withheld_with)."""
    out = {}
    for key, mlist in tnconfig.withheld_presets(cfg).items():
        if any(m in mods_loaded for m in mlist):
            out[cfg["presets"][key]["name"]] = cfg["presets"][key]["map"]
    return out


def row_ab_withheld(ctx, mods, sec6, row, cache):
    """Design constraint 3 beside Alien Biomes: AB 0.8.0's palms (tree-palm-a, tree-palm-b) read
    elevation in the Entity program, and a Terra Nauvis preset redirects elevation to its map's fine
    field, so presets.lua withholds every preset whose withheld_with lists a loaded mod (Europe,
    until climate-tiles ships the palm switch; design note 9). On M1 plus the live AB copy
    (fh.py modset --from-live): G1 to G3 on dump-data; no withheld preset in the dump; isolation (b)
    on every Terra Nauvis preset the dump does hold (none while every preset is withheld); each
    map's Map type entry and its fallbacks still defined there, and a Map-type-only world created
    there logs the withheld notice once (it names no preset the new-game screen lacks) and never the
    plain one. Positive control: the same dump walked with each withheld preset's own redirects
    (config.lua's table at the default scale) must reach the fine field from an Entity root (the
    palm path), so withholding is what keeps the constraint and the row would see a preset that
    slipped through. Withholding reaches new worlds only, so the save route is warned: a preset
    world made on M1 and loaded beside AB logs the withheld-preset warning exactly once, and loaded
    on M1, or on M1 with an unrelated mod added (a configuration change without a withholding mod),
    it logs none; an Earth world made beside AB from the preset's full map-gen-settings file (a
    server's route) logs it once at creation; the Map-type-only world beside AB never logs it."""
    cfg = mods.cfg
    live_set = list(AB_MODS)
    for mlist in tnconfig.withheld_presets(cfg).values():
        live_set += [m for m in mlist if m not in live_set]
    live = list(dict.fromkeys(live_set + [d for m in live_set for d in LIVE_DEPS.get(m, [])]))
    withheld = withheld_beside(cfg, live)
    m1ab = mods.with_live("m1ab", live)
    pname, mk, g = first_preset(cfg)
    key, newest = common_key(ctx, "ab_withheld", {"m1ab": mods.manifest(m1ab), "live": live, "withheld": withheld})

    def live_run():
        r = mods.prepare(m1ab, "m1ab")
        inst = ctx.instance
        save = ctx.out / "ab-create-maptype" / "mt.zip"
        rc = ctx.fh(create_args(inst, m1ab, save, mgs=maptype_mgs(ctx, cfg)), save.parent)
        # the save route: a preset world made without Alien Biomes, loaded beside it, on M1 itself
        # and on M1 with an unrelated mod added (a configuration change without a withholding mod)
        m1 = mods.m1()
        mods.prepare(m1, "m1")
        pw = ctx.out / "ab-create-preset" / "pw.zip"
        outs = [r.out, rc.out, ctx.fh(create_args(inst, m1, pw, preset=pname), pw.parent).out]
        mp = probe_modset(ctx, mods, "m1g1")
        dump_settings(ctx, mp, inst, label="ab")()
        for label, ms in (("beside-ab", m1ab), ("m1", m1), ("m1-probe", mp)):
            outs.append(ctx.fh(scenario_args(inst, ms, 3, save=pw), ctx.out / f"ab-load-preset-{label}").out)
        # an Earth world made beside Alien Biomes from the preset's full map-gen-settings file
        se = ctx.out / "ab-create-mgs" / "e.zip"
        outs.append(ctx.fh(create_args(inst, m1ab, se, mgs=preset_mgs(ctx, cfg)), se.parent).out)
        return outs

    def derive(dirs):
        d, dc = dirs[0], dirs[1]
        fails = g1(d) + g3(d) + g2(d, [cfg["identity"]["id"]] + live) + g1(dc) + g3(dc)
        for x in dirs[2:]:
            fails += g1(x) + g3(x)
        dump = json.loads((Path(d) / "data-raw-dump.json").read_text(encoding="utf-8"))
        held = ((dump.get("map-gen-presets") or {}).get("default") or {})
        fw = set(firewall_names(cfg))
        scale = int(cfg["settings"]["scale"]["default_value"])
        present = sorted(n for n in withheld if n in held)
        if present:
            fails.append(f"with {live} loaded the dump still holds the presets {present}, which config.lua withholds "
                         f"there: AB's palms read their elevation entry, the fine field (sacred constraint 3)")
        # isolation (b) beside AB on every Terra Nauvis preset that is defined there
        walked = {}
        for pn in earth_presets(cfg):
            if pn in withheld or pn not in held:
                if pn not in withheld:
                    fails.append(f"preset {pn} is missing beside {live}, though config.lua does not withhold it")
                continue
            rep = walk_roots(dump, preset_pen(dump, pn), fw)
            walked[pn] = sum(rep[gr]["hits"] for gr in ("entity", "decorative", "cliff"))
            if walked[pn]:
                ex = rep["entity"]["example"] or rep["decorative"]["example"] or rep["cliff"]["example"] or []
                fails.append(f"beside {live}, {pn}'s Entity, decorative or Cliff roots reach the fine field in "
                             f"{walked[pn]} paths, e.g. {' > '.join(ex[-5:])} (sacred constraint 3)")
        # the Map type entries (every version) and their fallbacks stay defined beside AB
        ne = dump.get("noise-expression") or {}
        for key_, gg in tnconfig.geography(cfg).items():
            if (ne.get(gg["entry"]) or {}).get("intended_property") != cfg["keys"]["elevation"]:
                fails.append(f"beside {live} the Map type entry {gg['entry']} is missing or lacks intended_property")
            for n in [n for n in gg["entry_versions"] if n not in ne]:
                fails.append(f"beside {live} the entry version {n} is not defined")
            for f in tnconfig.fallbacks(cfg).get(key_, []):
                if f["name"] not in ne:
                    fails.append(f"beside {live} the Map type fallback {f['name']} is not defined")
        # positive control: each withheld preset's own redirects reach the fine field through the palms
        hits, ex = 0, []
        for pn, map_key in sorted(withheld.items()):
            rep = walk_roots(dump, expected_pen(cfg, map_key, scale), fw)
            h = rep["entity"]["hits"] + rep["decorative"]["hits"] + rep["cliff"]["hits"]
            hits += h
            ex = ex or rep["entity"]["example"] or rep["decorative"]["example"] or []
            if not h:
                fails.append(f"positive control: {pn}'s redirects reach no firewall name in the AB dump: the row could "
                             f"not tell a withheld preset from a harmless one (has Alien Biomes changed? then "
                             f"withholding may be lifted with a DECISIONS entry)")
        # the Map-type-only world beside AB: the withheld notice, once, and never the plain one
        preset_name = ("map-gen-preset-name", pname)
        n_wh = count_lines(log_text(dc), render_message(cfg, "notice_withheld", preset_name))
        n_plain = count_lines(log_text(dc), render_message(cfg, "notice", preset_name))
        want_wh = 1 if pname in withheld else 0
        if n_wh != want_wh or n_plain != 1 - want_wh:
            fails.append(f"the Map-type-only world beside {live} logs the withheld notice {n_wh} times and the plain one "
                         f"{n_plain} times (want {want_wh} and {1 - want_wh})")
        # the save route: the withheld-preset warning, once where an Earth world meets a withholding mod
        wmods = [m for m in tnconfig.withheld_presets(cfg).get(cfg["preset_order"][0], []) if m in live]
        want_w = 1 if pname in withheld and wmods else 0
        any_warn = message_prefix(cfg, "withheld_beside")
        warn = render_message(cfg, "withheld_beside", preset_name, ", ".join(wmods)) if wmods else any_warn
        cases = ("preset world made on M1", "loaded beside AB", "loaded on M1", "loaded on M1 with an unrelated mod",
                 "Earth world made beside AB from the preset's full file")
        want = [0, want_w, 0, 0, want_w]
        got_any = [count_lines(log_text(x), any_warn) for x in dirs[2:7]]
        got = [count_lines(log_text(x), warn) for x in dirs[2:7]]
        if got_any != want or got != want:
            fails.append(f"the withheld-preset warning appears {dict(zip(cases, got))} times exactly and "
                         f"{dict(zip(cases, got_any))} in any form; want {dict(zip(cases, want))} ({warn!r})")
        n_mt_warn = count_lines(log_text(dc), any_warn)
        if n_mt_warn:
            fails.append(f"the Map-type-only world beside {live} logs the withheld-preset warning {n_mt_warn} times "
                         f"(want 0: it names no preset)")
        meas = {"withheld": sorted(withheld), "withheld_present": present, "walked": walked, "control_paths": hits,
                "control_example": ex[-4:], "notice_withheld": n_wh, "notice_plain": n_plain,
                "warning": dict(zip(cases, got))}
        return meas, fails, (f"with {', '.join(live)} (live copies): presets {sorted(withheld)} withheld, none in the "
                             f"dump; presets defined there {sorted(walked) or 'none'}, 0 firewall paths; Map type "
                             f"entries and fallbacks defined; control: the withheld redirects reach the fine field in "
                             f"{hits} paths, e.g. {' > '.join(ex[-4:])}; the Map-type-only world logs the withheld "
                             f"notice {n_wh} time(s); the preset save loaded beside AB logs the withheld-preset "
                             f"warning {got[1]} time(s), on M1 {got[2]} and {got[3]}, the Earth world made beside AB "
                             f"{got[4]}")

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


def row_t13_preset_preview(ctx, mods, sec6, row, cache):
    """The first Terra Nauvis preset's 256 px preview at seed 1000 differs from M0's (G5) and equals
    the committed baseline hash (rule 5)."""
    m0, m1 = ctx.shared["m0"], ctx.shared["m1"]
    pname, mk, _ = first_preset(mods.cfg)
    key, newest = common_key(ctx, "t13_preset_preview", {"m1": mods.manifest(m1), "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        return [preview(ctx, m0, "pv-m0-256", 256).out, preview(ctx, m1, "pv-preset-256", 256, preset=pname).out]

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        a, b = derive_preview(dirs[0]), derive_preview(dirs[1])
        fails += g2(dirs[1], [mods.cfg["identity"]["id"]])
        if not b["images"] or a["images"] == b["images"]:
            fails.append(f"the {pname} preview equals M0's: Earth was not active (G5)")
        want = ((baseline_record().get("previews_256") or {}).get(mk) or {}).get(str(SEED))
        if (b["images"] or {}).get(f"{SEED}.png") != want:
            fails.append(f"the preset preview at seed {SEED} differs from tests/baselines/build-{GAME_BUILD}.json: "
                         f"run 'earth_test.py baseline' and commit it (rule 5)")
        return {"m0": a["images"], "preset": b["images"]}, fails, \
            f"{pname} preview {list((b['images'] or {}).values())[:1]} differs from M0's at seed {SEED} (G5)"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_t13_scenario(ctx, mods, sec6, row, cache):
    """A 60-tick scenario on the first Terra Nauvis preset (G1 to G3), on M1's probe twin, whose dump
    probe proves the preset applied (G5): elevation at a point 100 tiles beyond the map's west edge
    (placed through the runner world's spawn offset: world = geo - offset, spawn-cities) reads the
    elevation entry's value, below 0, and its real tile is water."""
    import dump_render
    cfg = mods.cfg
    pname, mk, g = first_preset(cfg)
    m1p = mods.with_mods("m1p", [HERE / "mods" / "ep-s8-dump"])
    ph_name = g["entry"]
    s0 = int(cfg["settings"]["scale"]["default_value"])
    sea_x = -cfg["maps"][mk]["wr"] * s0 - 100 - runner_offset(cfg, mk, s0)[0]
    points = f"0,0;{sea_x},0"
    key, newest = common_key(ctx, "t13_scenario", {"m1p": mods.manifest(m1p), "points": points})

    def live():
        mods.prepare(m1p, "m1p")
        fh = dump_render.load_fh()
        dump_render.set_startup(fh, ctx.instance, m1p, {
            "label": "t13", "areas": f"{sea_x - 16},-16,32,32", "late-areas": "", "points": points,
            "names": f"elevation,{ph_name}",
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
        hv, hp = hvals.get("elevation"), hvals.get(ph_name)
        if hv is None or hv != hp or hv <= 0:
            fails.append(f"at the spawn (0, 0) elevation {hv} and {ph_name} {hp}: want the entry's land value")
        if "water" not in str(sea.get("tile", "")):
            fails.append(f"the real tile at ({sea_x}, 0) is {sea.get('tile')}, not water")
        return {"sea": {"elevation": ev, "tile": sea.get("tile")}, "home_elevation": hvals.get("elevation")}, \
            fails, f"60-tick scenario passes G1 to G3; at ({sea_x}, 0) elevation {ev} = {ph_name}, tile {sea.get('tile')} (G5)"

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 4: T15a rows and isolation (a)

COMPARATOR = {"M1": "vanilla", "M2": "bab"}     # the row each modset's Earth rows are compared with (U7)
ZERO_COST_ROWS = ("vanilla", "default", "bab")


BUDGET_SCALES = (1, 2, 3, 4, 5, 6)


def budgets_rows(cfg, meas_map, meas_m0, meas_def):
    """tests/budgets.json rows, each keyed by row kind, map, modset, scale, toggles (and variant):
    vanilla (M0), the default preset with Earth loaded (zero cost), and the first preset's map at
    scales 1 to 6 with toggles on and off. No toggle exists before spawn-cities, so a scale's on and
    off rows hold one measurement; the milestone that adds a toggle measures its off row."""
    pname, mk, _ = first_preset(cfg)
    common = {"seed": SEED, "size": 64}
    rows = [
        dict(common, row="vanilla", map=None, modset="M0", preset=None, scale=None, toggles="n/a", programs=meas_m0),
        dict(common, row="default", map=None, modset="M1", preset=None, scale=None, toggles="n/a", programs=meas_def),
    ]
    for s in sorted(meas_map):
        for tog in ("on", "off"):
            rows.append(dict(common, row="map", map=mk, modset="M1", preset=pname, scale=s, toggles=tog,
                             programs=meas_map[s]))
    return rows


def _row_id(r):
    return (r.get("row"), r.get("map"), r.get("modset"), r.get("scale"), r.get("toggles"), r.get("variant"))


def check_t15a(rows, sec6, main_rows, through, pending=None):
    """T15a against section 6 (parsed from main's plan): every 6.2 complexity limit in force, bound
    by its measure's program, modset and maps (P10 and P12 on M1 rows, P11 and P13 on M2 rows, P14 on
    every Earth row; P12 and P13 per map by the row's map); no Earth row equal to its comparator
    (G5); and growth over main's same row (or, for a row main lacks, its comparator's) within the
    6.3 allocation of the pending milestones (`pending`, default the gating milestone alone; a group's gate
    passes every unlanded milestone up to it: batch_alloc_for) for the row's modset and map ("cap": only
    the limits bound it; "none" and a cell that names nothing give 0)."""
    fails = []
    pending = [through] if pending is None else list(pending)
    missing = [s for s in pending if s not in (sec6.get("allocations") or {}) and
               s not in (sec6.get("all_allocations") or {})]
    if missing or through not in sec6["allocations"]:
        return [f"section 6.3 gives {missing or [through]} no allocation"]
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
            a = batch_alloc_for(sec6, pending, prog, r.get("modset"), r.get("map"), r.get("variant"))
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


def reference_budget_rows():
    """The landed tests/budgets.json rows check_t15a measures growth over, from every reference ref
    that resolves (main and origin/main): where they disagree on a row, each program takes the
    smaller landed complexity, so a stale ref never allows more growth. (rows, failures): an
    unreadable reference fails closed instead of reading as no landed rows."""
    try:
        texts = tn_static.reference_files("tests/budgets.json", REPO)
        per_ref = [json.loads(text).get("rows", []) for _, text in texts.values()]
    except (tn_static.ReferenceUnreadable, ValueError, AttributeError) as e:
        return [], [f"the landed tests/budgets.json is unreadable: {e} (fail closed)"]
    merged = {}
    for rows in per_ref:
        for r in rows:
            k = _row_id(r)
            if k not in merged:
                merged[k] = json.loads(json.dumps(r))
                continue
            progs = merged[k].setdefault("programs", {})
            for p, rec in (r.get("programs") or {}).items():
                if p not in progs or rec.get("complexity", 0) < progs[p].get("complexity", 0):
                    progs[p] = dict(rec)
    return list(merged.values()), []


def row_t15a_rows(ctx, mods, sec6, row, cache):
    """T15a: complexity from 64 px --verbose previews: M0, the default preset with Earth loaded, and
    the first preset's map at scales 1 to 6 (each scale through the preset's full MGS file at that
    scale, the preset route's equal), against P10 to P14 and the milestone's 6.3 allocation, and equal
    to tests/budgets.json."""
    m0, m1 = ctx.shared["m0"], ctx.shared["m1"]
    cfg = mods.cfg
    key, newest = common_key(ctx, "t15a_rows", {"m1": mods.manifest(m1), "dump": ctx.shared.get("dump_m1_sha"),
                                                  "scales": BUDGET_SCALES})

    def live():
        out = [preview(ctx, m0, "cx-m0", 64, verbose=True).out, preview(ctx, m1, "cx-default", 64, verbose=True).out]
        for s in BUDGET_SCALES:
            out.append(preview(ctx, m1, f"cx-map-s{s}", 64, verbose=True, mgs=preset_mgs(ctx, cfg, s)).out)
        return out

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        c0, cd = ctx_complexity(dirs[0]), ctx_complexity(dirs[1])
        cmap = {s: ctx_complexity(d) for s, d in zip(BUDGET_SCALES, dirs[2:])}
        cp = cmap[max(BUDGET_SCALES)]
        rows = budgets_rows(mods.cfg, cmap, c0, cd)
        pend = pending_slices(ctx.slice)
        if isinstance(sec6, Exception):
            fails.append(f"section 6 unreadable: {sec6}")
        else:
            main_rows, ref_fails = reference_budget_rows()
            fails += ref_fails
            fails += check_t15a(rows, sec6, main_rows, ctx.slice, pend)
        work = json.loads(BUDGETS.read_text(encoding="utf-8")).get("rows", [])
        if work != rows:
            fails.append("tests/budgets.json differs from the gate's measurement: run 'python tools/earth_test.py "
                         "baseline' and commit it (rule 5)")
        enforced = sorted(k for k, v in (sec6["limits"] if isinstance(sec6, dict) else {}).items() if v.get("complexity"))
        per = ", ".join(f"{s}: {cmap[s].get('tile', {}).get('complexity')}/{cmap[s].get('entity', {}).get('complexity')}/"
                        f"{cmap[s].get('cliff', {}).get('complexity')}" for s in BUDGET_SCALES)
        return {"rows": rows}, fails, (f"map rows Tile/Entity/Cliff by scale {per}, within {'/'.join(enforced)} and "
                                       f"the 6.3 allocation of the pending slices {pend} over the landed rows or the "
                                       f"comparator, not vanilla; equal to tests/budgets.json")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


ISOLATION_SCALES = (1, 6)


def row_isolation_a(ctx, mods, sec6, row, cache):
    """Isolation check (a), design constraint 3, S9's method: on every Terra Nauvis preset the
    Entity and Cliff programs are identical between the real build and its constant-coast twin
    while Tile differs (the twin's positive control). Positive control for Entity: on the leak
    fixture preset Entity must differ, since vanilla starting ore reads the twin's constant there."""
    cfg = mods.cfg
    m1 = ctx.shared["m1"]
    # each preset at its startup scale (6) through --preset, and at scale 1 through the preset's full
    # MGS file at that scale (the preset route's equal, T13): the plan's scales 1 and 6 on M1
    variants = []
    for pn in earth_presets(cfg):
        variants.append((pn, None))
        if pn == first_preset(cfg)[0]:
            variants.append((pn, ISOLATION_SCALES[0]))
    presets = [f"{pn} scale {s or cfg['settings']['scale']['default_value']}" for pn, s in variants]
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
        for i, (pn, s) in enumerate(variants):
            if s is None:
                dirs += [preview(ctx, m1, f"iso-real-{i}", 64, preset=pn, verbose=True).out,
                         preview(ctx, m1c, f"iso-twin-{i}", 64, preset=pn, verbose=True).out]
            else:
                mgs = preset_mgs(ctx, cfg, s)
                dirs += [preview(ctx, m1, f"iso-real-{i}", 64, mgs=mgs, verbose=True).out,
                         preview(ctx, m1c, f"iso-twin-{i}", 64, mgs=mgs, verbose=True).out]
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


# ================================================================================================ europe-coast

# Milestone europe-coast (part 2): Europe's coast at scales 1 to 6, its Map type entry, per-save values
# and the first timed baselines. Every Earth name comes from config.lua through tnconfig.
T1_BAR = 0.991                      # 6.1 T1-a: masked agreement per map (preview mode or dumped tiles)
ISLAND_MIN_PX = 65                  # 6.1 T1-e: every reference land component of 65 px or more present
UNCERTAIN_BAND = (-0.0100, 0.0)     # S8: tile outcome and threshold disagree only in this band
T11_AB = (3, 5)                     # T11: a scale 3 world created under A, loaded under B (scale 5)
# S2's 41-chunk probe set (spikes/S2-params ep-s2-params control.lua): 3 x 3 chunks around (40, 0),
# (0, 40) and (-28, -28) and the strip x 4..16 at y 0, generated first, as tile areas; then S2's
# whole-table map_gen_settings round trip (read surface.map_gen_settings and assign it back, what any
# mod merging autoplace entries does) and only after it the late chunk (60, 0), ep-s8-dump's late area.
T11_AREAS = "1248,-32,96,96;-32,1248,96,96;-928,-928,96,96;128,0,416,32"
T11_LATE = "1920,0,32,32"
T11_CHUNKS = 41
T11_LATE_CHUNKS = 1
T12_AREA = "-48,-48,96,96"          # T12 and the route parity: 3 x 3 chunks around the spawn
FAR_PROBES = (1, 100, 10000, 100000)  # D15: tiles beyond each map edge that must read deep water
EDGE_WINDOW = 2                     # T3: tiles each side of an edge the probe reads to find the far-field switch
DEEP_BELOW = -2.5                   # vanilla deepwater beats water below elevation -2.5 (water_base)
PAR_MAX = 4                         # project rule 1: at most four game processes at once for correctness
PREVIEW_MAX = 4096                  # the largest preview tile the T1 previews use
T1_SCALES_FG = (1, 6)
DETAIL_SCALES = (1, 2, 3, 4, 5, 6)
DETAIL_PROBES = 64                  # T3 detail control: off-centre tiles probed per scale from 2


def coast_view(cfg):
    """A 256 px preview offset that holds the first map's coast at its startup scale: the Baltic
    shore north of the map's geo origin (reference pixels 1200, 852 to 1200, 800 at scale 6), placed
    through the runner world's spawn offset (spawn-cities: world = geo - offset), so the Map type
    route's water mask and the route parity compare water as well as land."""
    _, mk, g = first_preset(cfg)
    s = int(cfg["settings"]["scale"]["default_value"])
    ox, oy = runner_offset(cfg, mk, s)
    return (-(ox // 32) * 32, -(((COAST_VIEW_PX * s) + oy) // 32) * 32)


COAST_VIEW_PX = 53                  # reference pixels north of the spawn to the Baltic shore (Europe)


def first_preset(cfg):
    """(preset name, map key, geography) of the first Terra Nauvis preset (Europe): the map's newest
    geography version, the one its preset names (tnconfig.geography)."""
    key = cfg["preset_order"][0]
    p = cfg["presets"][key]
    geo = tnconfig.geography(cfg).get(p["map"])
    if not geo:
        raise GateError(f"config.lua gives the preset {p['name']} no geography for {p['map']}")
    return p["name"], p["map"], geo


def expected_pen(cfg, map_key, scale, city=None):
    """The property_expression_names a map's preset must bake at a startup scale (and, for a version
    with a spawn record, a spawn-city setting value, default the setting's default): its newest
    geography version's, from config.lua's own tables (tnconfig.baked_names mirrors presets.lua,
    vanilla's water-slider readers at their default-slider values included, D15; from spawn-cities
    also the distance redirect, the map's city number and the spawn lake and bias keys, with the
    version's city offset names pointing at the city fold)."""
    return tnconfig.baked_names(cfg, map_key, tnconfig.geography(cfg)[map_key], scale, city)


def runner_offset(cfg, map_key, scale, seed=SEED, city=None):
    """The spawn offset (tiles) of the runner's preset world of a map at `scale` and `seed`, made at
    the default settings (or with spawn-city `city`): world = geo - offset (spawn-cities; S7). With a
    city offset baked as numbers (europe-coast's 0) it is those numbers."""
    import oracle
    return oracle.pen_offset(cfg, map_key, expected_pen(cfg, map_key, scale, city), seed)


# spawn-cities' composition terms a coast-only world neutralises through property_expression_names,
# which a body reads before the prototype of the same name: a lake or guarantee term set to this
# number (or its negative) changes no tile, so the world's tiles are the version's coast alone.
NEUTRAL = 1000000000


def coast_only_pen(cfg, map_key, pen):
    """`pen` with the map's spawn shift undone (the version's city offset names 0, the geo origin at
    world (0, 0)) and the spawn lake, the version's inland lakes and the start land guarantee
    neutral: T1, T2 and T3 score the coast fit in europe-coast's frame. Outside its footprint no lake
    or guarantee term changes a tile's class, so neutralising them equals masking their footprints
    (U13); measured equal to the version 1 world's water (design notes, spawn-cities: the coast-only
    worlds). spawn-cities' own rows check the lakes. A version without a spawn record is returned
    as it is."""
    g = tnconfig.geography(cfg)[map_key]
    if not g.get("spawn"):
        return dict(pen)
    out = dict(pen)
    out.update({g["cx"]: 0, g["cy"]: 0, g["spawn_lake"]: NEUTRAL, g["inland_lakes"]: NEUTRAL,
                g["start_land"]: -NEUTRAL})
    return out


NO_CLIFFS = {"name": "cliff", "richness": 0}


def write_mgs(ctx, label, pen):
    """A --map-gen-settings file holding only property_expression_names; its keys come from the dumped
    preset (U10: never combined with --preset)."""
    d = ctx.out / "mgs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{label}.json"
    p.write_text(json.dumps({"property_expression_names": pen}, indent=1, sort_keys=True), encoding="utf-8")
    return p


def preset_mgs(ctx, cfg, scale=None, cliffs=True, coast_only=False):
    """The first preset as the M1 dump holds it, as a full MGS file, at its startup scale or at
    `scale` (the preset made at that startup scale bakes exactly that; T13 proves the two routes
    equal). cliffs=False adds cliff richness 0 for the T1 previews: a preview draws cliffs over the
    tiles, water included, and cliffs never change a tile. coast_only=True writes coast_only_pen's
    test-only world (T1, T2 and T3 in europe-coast's frame)."""
    pname, mk, _ = first_preset(cfg)
    pen = dict(preset_pen(ctx.shared["dump_m1"], pname))
    if not pen:
        raise GateError(f"the M1 dump holds no preset {pname}")
    if scale is not None:
        pen[cfg["keys"]["scale"]] = int(scale)
    label = f"preset-s{pen[cfg['keys']['scale']]}"
    if coast_only:
        pen = coast_only_pen(cfg, mk, pen)
        label += "-coast"
    if cliffs:
        return write_mgs(ctx, label, pen)
    d = ctx.out / "mgs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{label}-nocliffs.json"
    f.write_text(json.dumps({"property_expression_names": pen, "cliff_settings": NO_CLIFFS}, indent=1, sort_keys=True),
                 encoding="utf-8")
    return f


def maptype_mgs(ctx, cfg):
    """S13's mgs-maptype-europe.json with the shipped name: only elevation, set to the entry."""
    _, _, g = first_preset(cfg)
    return write_mgs(ctx, "maptype-elevation-only", {cfg["keys"]["elevation"]: g["entry"]})


def blocking_water_colours(dump):
    """Map colours of the player-blocking water tiles a map can place: tiles with the water_tile and
    player layers and an autoplace (base: water and deepwater). out-of-map and water-wube share
    coal's black map colour and are never placed, so a dump's full water list would read coal as
    water."""
    out = []
    for t in (dump.get("tile") or {}).values():
        layers = (t.get("collision_mask") or {}).get("layers") or {}
        mc = t.get("map_color")
        if "water_tile" in layers and "player" in layers and t.get("autoplace") and mc is not None:
            out.append((mc.get("r", 0), mc.get("g", 0), mc.get("b", 0)) if isinstance(mc, dict) else tuple(mc[:3]))
    if not out:
        raise GateError("the dump holds no placeable player-blocking water tile")
    return out


def lane_instance(ctx, i):
    return f"{ctx.instance}-p{i + 1}"


def run_lanes(ctx, lanes):
    """Each worker runs its jobs [(prepare or None, fh args, out, timeout)] in order on its own instance
    and modset, at most PAR_MAX workers at once (project rule 1; one instance and one modset per
    concurrent run). A job's prepare() runs in its worker right before it (it writes that worker's
    modset settings). Returns {str(out): Run}.

    Design constraint 1 holds across workers: the first FatalRun in any worker stops the whole command
    at once. Ctx.fatal sets ctx.stop and terminates the job, which ends every run other workers have
    in flight; each worker checks ctx.stop before each job and Ctx.fh launches nothing once it is set;
    workers not started yet are cancelled; and the FatalRun reaches the caller, ahead of any other worker
    error, as soon as every worker has stopped (the lane_stop runner control)."""
    from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
    used = {}
    for i, jobs in enumerate(lanes):
        for _, args, _, _ in jobs:
            for flag in ("--instance", "--modset"):
                v = args[args.index(flag) + 1]
                if used.setdefault((flag, v), i) != i:
                    raise GateError(f"two lanes share {flag} {v}: concurrent runs need their own")
    results = {}

    def lane(jobs):
        for prep, args, out, timeout in jobs:
            ctx.halt_if_stopped(f"fh.py {args[0]} into {out}")
            if prep:
                prep()
            results[str(out)] = ctx.fh(args, out, timeout=timeout)

    ex = ThreadPoolExecutor(max_workers=PAR_MAX)
    futs = []
    try:
        futs = [ex.submit(lane, jobs) for jobs in lanes]
        wait(futs, return_when=FIRST_EXCEPTION)
    finally:
        # workers not started never start; running ones meet ctx.stop (or a terminated job) and end
        ex.shutdown(wait=True, cancel_futures=True)
    errors = [f.exception() for f in futs if not f.cancelled() and f.exception() is not None]
    fatal = next((e for e in errors if isinstance(e, FatalRun)), None)
    if fatal is not None:
        raise fatal
    if errors:
        raise errors[0]
    return results


def split_lanes(jobs, n=PAR_MAX):
    lanes = [[] for _ in range(min(n, len(jobs)))]
    for i, j in enumerate(jobs):
        lanes[i % len(lanes)].append(j)
    return lanes


DUMP_DEFAULTS = {"label": "dump", "areas": "", "late-areas": "", "points": "", "names": "", "decoratives": False,
                 "scene": "", "scene-lattice": 4, "gen-tick": 1, "tick": 2, "types": "", "grid": "",
                 "grid-name": "elevation",
                 "grid-threshold": "0", "grid-op": "ge", "measure": ""}


def dump_settings(ctx, modset, inst, **vals):
    """A prepare() that writes every ep-s8-dump startup setting of `modset` (stored values persist in a
    modset otherwise; dump_render.set_startup)."""
    import dump_render

    def prep():
        v = dict(DUMP_DEFAULTS)
        v.update({k.replace("_", "-"): x for k, x in vals.items()})
        dump_render.set_startup(dump_render.load_fh(), inst, modset, v)
    return prep


def probe_modset(ctx, mods, tag, scale=None):
    """M1 plus ep-s8-dump (its own modset per tag), prepared (G7), with the startup scale written when
    given."""
    ms = mods.with_mods(tag, [HERE / "mods" / "ep-s8-dump"])
    mods.prepare(ms, tag)
    if scale is not None:
        set_scale(ctx, mods, ms, scale)
    return ms


def set_scale(ctx, mods, modset, scale):
    name = mods.cfg["settings"]["scale"]["name"]
    res = ctx.fh_plain(["settings", modset, "--set", f"startup.{name}={int(scale)}"])
    if not res.startswith("RESULT ok"):
        raise GateError(f"fh.py settings {modset}: {res}")


def scenario_args(inst, modset, ticks, seed=SEED, mgs=None, save=None):
    a = ["scenario", "--instance", inst, "--modset", modset, "--ticks", str(ticks)]
    if save is not None:
        return a + ["--save", save]
    a += ["--seed", str(seed)]
    if mgs is not None:
        a += ["--map-gen-settings", mgs]
    return a


def create_args(inst, modset, save, seed=SEED, preset=None, mgs=None):
    a = ["run", "--instance", inst, "--modset", modset, "--", "--create", save, "--map-gen-seed", str(seed)]
    if preset:
        a += ["--preset", preset]
    if mgs:
        a += ["--map-gen-settings", mgs]
    return a


def read_dump(run_dir, label):
    import dump_render
    f = Path(run_dir) / "script-output" / "ep-s8-dump" / f"{label}.json"
    if not f.exists():
        raise GateError(f"{run_dir}: the probe wrote no {f.name}")
    return dump_render.load_json(f)


ROUTE_TYPES = "tree,simple-entity,resource,cliff,unit-spawner,turret,unit,fish"


def dump_seed_fails(run_dir, label, want_seed):
    """An exit-0 guard on one probe dump (test notes T2): the surface's map_gen_settings.seed,
    which ep-s8-dump writes, equals the seed the run asked for, so a run that ignored its seed
    cannot pass a seed check by comparing a map with itself."""
    try:
        got = read_dump(run_dir, label).get("seed")
    except GateError as e:
        return [str(e)]
    if got != want_seed:
        return [f"{run_dir}: the dump reads seed {got}, the run asked for {want_seed} (exit-0 guard)"]
    return []


def spawn_map_fails(run_dir, label, name):
    """An exit-0 guard on one probe dump (G5): `name` (tn_map) read through the surface at the spawn
    is a number above 0, so the run's world is an Earth preset world and not a silent vanilla one."""
    try:
        v = (point_values(read_dump(run_dir, label)).get((0, 0)) or {}).get(name)
    except GateError as e:
        return [str(e)]
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not v > 0:
        return [f"{run_dir}: {name} reads {v!r} at (0, 0), not above 0: the world is not an Earth preset world "
                f"(exit-0 guard)"]
    return []


def m0_probe(ctx, mods, tag):
    """M0 plus ep-s8-dump in a modset of its own per tag, prepared (G7): a vanilla comparator."""
    ms = mods.with_mods(tag, [HERE / "mods" / "ep-s8-dump"], earth=False)
    mods.prepare(ms, tag)
    return ms


def area_entities(dump):
    """Every dumped entity of every area as sorted (name, x, y, extra) tuples: extra is a resource's
    amount or a cliff's orientation as text, else empty, so a richness or orientation change counts."""
    out = []
    for a in dump.get("areas") or []:
        names = [e["name"] for e in a.get("entity_names") or []]
        out += [(names[e[0]], e[1], e[2], str(e[3]) if len(e) > 3 else "") for e in a.get("entities") or []]
        out += [(names[c[0]], c[1], c[2], str(c[3]) if len(c) > 3 else "") for c in a.get("cliffs") or []]
    return sorted(out)


def entity_difference(a, b):
    """How many entities of two dumps' sorted entity lists have no match in the other (a multiset
    symmetric difference)."""
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    return sum(((ca - cb) + (cb - ca)).values())


def read_back(cfg, vals, map_key, scale):
    """The per-save values a probe read through the surface at one point, against what the map's
    preset bakes at `scale` (expected_pen): [(key, got, want)] for every key that differs. The keys
    are tn_map, tn_scale, tn_geo, the map's city offset and, for a version with a spawn record, its
    city number. Where the preset bakes the offset names as the city fold's names (spawn-cities),
    the probe reads the folded tiles, so the want is the oracle's offset of that world at SEED
    (runner_offset)."""
    want = dict(expected_pen(cfg, map_key, scale))
    g, K = tnconfig.geography(cfg)[map_key], cfg["keys"]
    keys = [K["map"], K["scale"], K["geo"], g["cx"], g["cy"]] + ([g["city"]] if g.get("spawn") else [])
    if any(isinstance(want[k], str) for k in (g["cx"], g["cy"])):
        for k, o in zip((g["cx"], g["cy"]), runner_offset(cfg, map_key, scale)):
            want[k] = o
    return [(k, vals.get(k), want[k]) for k in keys if vals.get(k) != want[k]]


def area_tiles(dump):
    """Every dumped area's tile names as one flat list (row-major per area, areas in order)."""
    import dump_render
    out = []
    for a in dump.get("areas") or []:
        pal, idx = dump_render.decode_tiles(a)
        out += [pal[i] for i in idx.ravel().tolist()]
    return out


def point_values(dump):
    """{(x, y): {"tile": name, name: value, ...}} from a points dump."""
    names = dump.get("names") or []
    out = {}
    for p in dump.get("points") or []:
        rec = {"tile": p.get("tile")}
        vals = p.get("values") or []
        if isinstance(vals, dict):
            vals = []
        for n, v in zip(names, vals):
            rec[n] = v
        out[(p["x"], p["y"])] = rec
    return out


def log_text(run_dir):
    """The game logs of a run directory and its create and bench steps (not stdout, which repeats
    each log line)."""
    parts = []
    for sub in ("", "create", "bench"):
        f = Path(run_dir) / sub / "factorio-current.log"
        if f.exists():
            parts.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def locale_messages(cfg):
    """{key: text} of the mod's message section and the names messages interpolate, from the locale
    file (the in-game load proves the file; this renders what a log line must read)."""
    secs, _ = tn_static.parse_cfg((MOD / "locale" / "en" / "terra-nauvis.cfg").read_text(encoding="utf-8"))
    return secs


def render_message(cfg, key, *args):
    """The text log() writes for {section.key, args...}: __n__ replaced by each argument, a nested
    localised name ([section, key]) resolved from the locale file."""
    secs = locale_messages(cfg)
    msgs = cfg["messages"]
    text = secs[msgs["section"]][msgs["keys"][key]]
    for i, a in enumerate(args, 1):
        if isinstance(a, (list, tuple)):
            sec, k = a
            a = secs[sec][k]
        text = text.replace(f"__{i}__", str(a))
    return text


def message_prefix(cfg, key):
    """The fixed text before a message's first parameter: it finds the message whatever its values."""
    secs = locale_messages(cfg)
    msgs = cfg["messages"]
    return secs[msgs["section"]][msgs["keys"][key]].split("__1__")[0].rstrip()


def count_lines(text, needle):
    return sum(1 for line in text.splitlines() if needle in line)


def grid_spec(mref, scale, cfg=None):
    import t1_metrics as t1
    g = t1.plan_grid(mref, str(scale))
    return f"{g['x0']},{g['y0']},{g['step']},{g['nx']},{g['ny']}"


def grid_land(mref, run_dir, scale):
    """(land, covered) full-size arrays of a grid run (thresholded elevation at pixel centres)."""
    import numpy as np
    import t1_metrics as t1
    g, arr, _ = t1.read_grid(run_dir)
    rows, cols, block = t1.map_grid(mref, g, arr, str(scale), "floor")
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    L[np.ix_(rows, cols)] = block == 1
    C[np.ix_(rows, cols)] = block != 2
    return L, C


def preview_plan(mref, scale, max_size=PREVIEW_MAX):
    """(size, [offsets]) of square previews (sizes and offsets multiples of 64 and 32) that cover the
    map's extent at a scale, overlapping by 64 tiles. The extent is W s x H s tiles from the
    pixel-centre geometry (city offset 0 in this milestone)."""
    W, H = mref.W * int(scale), mref.H * int(scale)
    x0, y0 = -mref.wr * int(scale), -mref.hr * int(scale)
    size = min(max_size, -(-(max(W, H) + 64) // 64) * 64)

    def centres(a0, n):
        c = ((a0 + size // 2) // 32) * 32
        out = [c]
        while out[-1] + size // 2 < a0 + n:
            out.append(out[-1] + size - 64)
        return out
    return size, [(cx, cy) for cy in centres(y0, H) for cx in centres(x0, W)]


def preview_args(inst, modset, size, seed=SEED, mgs=None, offset=None, preset=None, verbose=False):
    a = ["preview", "--instance", inst, "--modset", modset, "--seed", str(seed), "--size", str(size)]
    if offset is not None:
        a.append(f"--offset={offset[0]},{offset[1]}")
    if mgs is not None:
        a += ["--map-gen-settings", mgs]
    extra = (["--verbose"] if verbose else []) + (["--preset", preset] if preset else [])
    return a + (["--"] + extra if extra else [])


def cliff_colours(dump):
    """The cliffs' map colours: a preview draws cliffs over the tiles, water included (the real game
    keeps no cliff on water), so a cliff pixel hides its tile from preview mode."""
    out = []
    for p in (dump.get("cliff") or {}).values():
        mc = p.get("map_color") if isinstance(p, dict) else None
        if mc is not None:
            out.append((mc.get("r", 0), mc.get("g", 0), mc.get("b", 0)) if isinstance(mc, dict) else tuple(mc[:3]))
    return out


def previews_land(mref, runs, scale, colours, hidden=()):
    """(land, covered, hidden) from preview runs [(run dir, (offset x, offset y))]: each preview pixel
    is a tile, water where its colour is a player-blocking water tile's (t1_metrics' preview mode).
    A pixel drawn in a `hidden` colour (cliffs) shows no tile: it is left uncovered and counted."""
    import numpy as np
    from PIL import Image
    import t1_metrics as t1
    ws = t1.water_colour_set(colours)
    hs = t1.water_colour_set(hidden) if hidden else set()
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    Hd = np.zeros((mref.H, mref.W), bool)
    for d, off in runs:
        imgs = sorted(Path(d).glob(f"{SEED}.png")) or sorted(Path(d).glob("*.png"))
        if len(imgs) != 1:
            raise GateError(f"{d}: {len(imgs)} preview images (G4)")
        lp = t1.preview_land(imgs[0], ws)
        Lp, Cp = t1.map_preview(mref, lp, off, str(scale), "floor")
        if hs:
            hp = ~t1.preview_land(imgs[0], hs)
            Hp, _ = t1.map_preview(mref, hp, off, str(scale), "floor")
            Hd[Cp] = Hp[Cp]
        L[Cp] = Lp[Cp]
        C |= Cp
    C &= ~Hd
    return L, C, Hd


def t1_eval(mref, L, C):
    """T1 on one land decision (thin water masked; the D15 lake footprints and D16 corridors are empty
    until spawn-cities and waterways): agreement, IoU, coast deviation, islands per size bucket
    (4- and 8-connected), and the thin water that became land, as pixels and reaches."""
    import numpy as np
    import t1_metrics as t1
    res, _ = t1.crop_and_evaluate(mref, L.copy(), C, t1.DEFAULT_CAP, 4)
    res8, _ = t1.crop_and_evaluate(mref, L.copy(), C, t1.DEFAULT_CAP, 8)
    thin = L & C & mref.thin
    R = t1.flat_runs(thin, 8)
    area = np.bincount(R["comp"], weights=R["e"] - R["s"] + 1, minlength=R["n"]) if R["n"] else np.zeros(0)
    cd = res["coast_deviation_px"]
    b4, b8 = res["islands"]["buckets"], res8["islands"]["buckets"]
    return {"agreement": res["pixel_agreement"], "iou": res["land_iou"], "p99_px": cd["p99"], "max_px": cd["max"],
            "mean_px": cd["mean"], "misclassified": cd["misclassified"], "covered_px": res["covered_px"],
            "evaluated_px": res["evaluated_px"],
            "masked_px": {"thin_water": res["excluded_thin_px"], "lake_footprints_d15": 0, "corridors_d16": 0},
            "islands_conn4": {k: [v["present"], v["islands"]] for k, v in b4.items()},
            "islands_conn8": {k: [v["present"], v["islands"]] for k, v in b8.items()},
            "islands_65_missing": [b4["65+"]["missing"], b8["65+"]["missing"]],
            "thin_water_became_land": {"pixels": int(thin.sum()), "reaches": int(R["n"]),
                                       "reaches_20_px_plus": int((area >= 20).sum())}}


def t1_fails(label, rec, bar=T1_BAR):
    out = []
    if rec["agreement"] is None or rec["agreement"] < bar:
        out.append(f"{label}: masked agreement {rec['agreement']} under {bar} (T1-a)")
    if any(rec["islands_65_missing"]):
        out.append(f"{label}: land components of {ISLAND_MIN_PX} px or more missing (4- and 8-connected) "
                   f"{rec['islands_65_missing']} (T1-e)")
    return out


# -- step 2: Europe's dump facts (T13, T16; the Map type entry and its fallbacks)

def entry_reads(dump, pen, start):
    """The names a body reaches in the program (NoiseGraph through the preset's redirects) and the
    property_expression_names keys among them."""
    graph = NoiseGraph(dump, pen)
    seen, _ = graph.walk([(start, ())], lambda n: False)
    return seen


def row_ec_dump_facts(ctx, mods, sec6, row, cache):
    """T13 and T16 on the dumps (D2 amended; S13): the Map type entry carries intended_property
    "elevation", a [noise-expression] localised_name whose locale text is "<title>: <map>" and an
    order after vanilla's unordered entries and before Island's; no other Earth expression carries
    intended_property; the preset's elevation names the entry; every per-save name the entry reads
    has a prototype fallback equal to what the preset bakes, at default settings and at T11's
    settings B, and so does every older version's entry, against what its own version's preset
    would bake (tnconfig.baked_names; older entries stay defined for the worlds that name them); no
    map-dependent value reaches the entry through tn_map or a shared key; the fallbacks, and only
    they, are exempt from tests/frozen.json; and the geography reads no vanilla named body (each
    would need an Earth copy equal to 2.1.23's)."""
    cfg = mods.cfg
    d1 = ctx.shared.get("dump_m1")
    if d1 is None:
        row.fails.append("no M1 dump")
        return
    pname, mk, g = first_preset(cfg)
    ne = d1.get("noise-expression") or {}
    entry = ne.get(g["entry"])
    K = cfg["keys"]
    fails, parts = row.fails, []
    if not entry:
        fails.append(f"the dump lacks the Map type entry {g['entry']}")
        return
    if entry.get("intended_property") != K["elevation"]:
        fails.append(f"{g['entry']} intended_property {entry.get('intended_property')!r}, want {K['elevation']!r}")
    ln = entry.get("localised_name")
    want_ln = [f"noise-expression.{g['entry']}"]
    if ln != want_ln:
        fails.append(f"{g['entry']} localised_name {ln!r}, want {want_ln!r}")
    secs = locale_messages(cfg)
    want_text = f"{cfg['identity']['title']}: {cfg['maps'][mk]['display']}"
    got_text = (secs.get("noise-expression") or {}).get(g["entry"])
    if got_text != want_text:
        fails.append(f"locale [noise-expression] {g['entry']} reads {got_text!r}, want {want_text!r}")
    order = entry.get("order") or ""
    vanilla_entries = {n: (b.get("order") or "") for n, b in ne.items()
                       if b.get("intended_property") == K["elevation"] and not n.startswith(cfg["identity"]["noise_prefix"])}
    unordered = [n for n, o in vanilla_entries.items() if not o]
    ordered_after = sorted(o for o in vanilla_entries.values() if o)
    if not order or (ordered_after and not order < ordered_after[0]):
        fails.append(f"{g['entry']} order {order!r} does not sort after vanilla's unordered entries {unordered} and "
                     f"before {ordered_after[:1]} (S13: after Lakes, before Island)")
    carriers = sorted(n for n, b in ne.items() if n.startswith(cfg["identity"]["noise_prefix"]) and
                      b.get("intended_property"))
    newest = sorted(gg["entry"] for gg in tnconfig.geography(cfg).values())
    if carriers != newest:
        fails.append(f"Terra Nauvis expressions carrying intended_property {carriers}, want only {newest}")
    pen = preset_pen(d1, pname)
    if pen.get(K["elevation"]) != g["entry"]:
        fails.append(f"preset {pname} names {pen.get(K['elevation'])!r} for elevation, not the entry {g['entry']}")
    for k in (K["map"], K["scale"], K["geo"]):
        if not isinstance(pen.get(k), (int, float)) or isinstance(pen.get(k), bool):
            fails.append(f"preset {pname} bakes {k} as {pen.get(k)!r}, not a number (T13)")
    # the per-save names the entry reads: walked through the prototype names alone (a Map type pick
    # sets only elevation), then each must be a fallback valued as the preset bakes it
    reads = entry_reads(d1, {}, g["entry"])
    keys = set(cfg["preset_keys"])
    read_keys = sorted(n for n in reads if n in keys)
    fb = {e["name"]: e for e in g["fallbacks"]}
    if sorted(fb) != read_keys:
        fails.append(f"the entry reads the per-save names {read_keys}; config.lua's fallbacks for its version are "
                     f"{sorted(fb)}")
    shared_bad = [n for n in read_keys if n in (K["map"], K["geo"], K["land_coarse"]) or
                  (n in fb and fb[n]["map_qualified"] and tn_static.map_suffixes(n, cfg["map_order"]) != [mk])]
    if shared_bad:
        fails.append(f"map-dependent values reach the entry through tn_map or a shared key: {shared_bad}")
    fmt = cfg["number_format"]
    # every older version of the entry reads exactly its own version's fallbacks
    older = tnconfig.geography_versions(cfg)[mk][:-1]
    for v in older:
        if v["entry"] in ne:
            got = sorted(n for n in entry_reads(d1, {}, v["entry"]) if n in keys)
            want = sorted(e["name"] for e in v["fallbacks"])
            if got != want:
                fails.append(f"the older entry {v['entry']} reads the per-save names {got}; its version's fallbacks "
                             f"are {want}")

    def baked_text(value):
        return fmt % value if isinstance(value, (int, float)) and not isinstance(value, bool) else value

    def fallback_values(dump, label, want_scale):
        bad = []
        p = preset_pen(dump, pname)
        for n in read_keys:
            body = (dump.get("noise-expression") or {}).get(n)
            if body is None:
                bad.append(f"{label}: no prototype fallback {n}")
                continue
            baked = p.get(n)
            if baked is None or body.get("expression") != baked_text(baked):
                bad.append(f"{label}: fallback {n} = {body.get('expression')!r}, the preset bakes {baked!r}")
            if body.get("local_expressions"):
                bad.append(f"{label}: fallback {n} carries local expressions")
        if p.get(K["scale"]) != want_scale:
            bad.append(f"{label}: the preset bakes scale {p.get(K['scale'])}, want {want_scale}")
        # an older version's fallbacks, valued as that version's own preset bakes them
        for v in older:
            vb = tnconfig.baked_names(cfg, mk, v, want_scale)
            for e in v["fallbacks"]:
                body = (dump.get("noise-expression") or {}).get(e["name"])
                if body is None or body.get("expression") != baked_text(vb[e["name"]]):
                    bad.append(f"{label}: the older version's fallback {e['name']} = "
                               f"{(body or {}).get('expression')!r}, its version bakes {vb[e['name']]!r}")
        return bad
    fails += fallback_values(d1, "default settings", int(cfg["settings"]["scale"]["default_value"]))
    # T11's settings B: a dump of M1 with the startup scale B
    mb = mods.make(f"ea-m1b{T11_AB[1]}-{mods.zip_sha[:8]}", [mods.build_zip()])
    mods.prepare(mb, f"m1b{T11_AB[1]}")
    set_scale(ctx, mods, mb, T11_AB[1])
    key, newest = common_key(ctx, "ec_dump_b", {"mb": mods.manifest(mb), "b": T11_AB[1]})
    hit = cache.get(key) if cache is not None else None
    rb = None
    if hit:
        d = abs_ws(ctx, hit["run_dirs"][0])
        if not g1(d) and run_time(d) >= newest and (d / "data-raw-dump.json").exists():
            rb = d
    if rb is None:
        r = ctx.fh(["dump-data", "--instance", ctx.instance, "--modset", mb], ctx.out / f"dump-settings-b{T11_AB[1]}")
        if not r.ok:
            fails.append(f"dump-data at settings B: {r.result}")
        fails += g1(r.out) + g3(r.out)
        rb = r.out
        tmp = Row("ec_dump_b")
        tmp.run_dirs, tmp.meas = [rb], {}
        if cache is not None and not g1(rb):
            cache.put(key, tmp, newest)
    db = json.loads((Path(rb) / "data-raw-dump.json").read_text(encoding="utf-8"))
    fails += fallback_values(db, f"settings B (scale {T11_AB[1]})", T11_AB[1])
    exempt = frozen_exempt(cfg)
    if exempt != set(tnconfig.placeholder_names(cfg)) | set(tnconfig.exempt_fallback_names(cfg)):
        fails.append(f"names exempt from tests/frozen.json {sorted(exempt)} are not exactly the fallbacks that mirror a "
                     f"startup setting")
    # the binding contract: every other name the entry reads through a prototype is registered, so no
    # later version can move a Map-type-only world made from it (ARCHITECTURE.md, "Map type entries")
    fz_bodies = (json.loads((TESTS / "frozen.json").read_text(encoding="utf-8")).get("bodies") or {})
    # pinned means registered under a record the frozen row reads: a record that breaks the contract
    # (a dump label no milestone assigns, say) pins nothing
    pinned = {n for n, r in fz_bodies.items() if not tnfrozen.record_problems(n, r, REGISTRY)}
    unpinned = sorted(n for n in read_keys if n not in exempt and n not in pinned)
    if unpinned:
        fails.append(f"the entry reads {unpinned} through prototypes that tests/frozen.json does not register under a "
                     f"well-formed record: a later version could move every Map-type-only world made from it")
    # the setting-mirroring fallbacks a Map-type-only world follows: the scale and, for a version with
    # a spawn record, its map's city number (the spawn-city setting); nothing else follows a setting
    follows = {K["scale"]} | ({g["city"]} if g.get("spawn") else set())
    drifting = sorted(n for n in read_keys if n in exempt and n not in follows)
    if drifting:
        fails.append(f"the entry reads the setting-mirroring fallbacks {drifting}: only the scale and its version's "
                     f"city number follow a setting")
    # every version of the entry stays defined; only the newest carries the Map type fields
    missing_versions = [n for n in g["entry_versions"] if n not in ne]
    if missing_versions:
        fails.append(f"entry versions {missing_versions} are not defined: older versions stay defined for the worlds "
                     f"that name them")
    # every named body the geography reads is an Earth body, a fallback or a preset key: no vanilla body
    earth = set(earth_bodies(d1, cfg))
    vanilla_reached = set()
    for start in (g["entry"], g["land_coarse"], g["start_mask"]):
        for n in entry_reads(d1, pen, start):
            if (n in ne or n in (d1.get("noise-function") or {})) and n not in earth and n not in keys:
                vanilla_reached.add(n)
    if vanilla_reached:
        fails.append(f"the geography reads vanilla bodies {sorted(vanilla_reached)}: copy each under an Earth name "
                     f"equal to 2.1.23's body (versioning rule 3)")
    row.run_dirs = [rb]
    parts.append(f"{g['entry']}: intended_property {entry.get('intended_property')}, order {order!r} (after "
                 f"{unordered}, before {ordered_after[:1]}), locale {got_text!r}; reads {read_keys}, each a fallback "
                 f"equal to the preset at scales {cfg['settings']['scale']['default_value']} and {T11_AB[1]}, all but "
                 f"the setting mirrors {sorted(n for n in read_keys if n in exempt)} registered; versions {g['entry_versions']} defined, each older one reading its own "
                 f"version's fallbacks ({len(older)} older); no vanilla body read")
    row.detail = "; ".join(parts)


def row_geo_emit(ctx, mods, sec6, row, cache):
    """T16: tools/build_geo.py emits byte-identical geo and coarse files twice from the committed
    checkpoints (numpy is imported here only, so `earth_test.py static` stays numpy-free for CI)."""
    import build_geo
    done = []
    for mk in (mods.cfg.get("geography") or {}):
        f = build_geo.check(mk)
        row.fails += [f"{mk}: {x}" for x in f]
        done.append(mk)
    row.detail = f"build_geo.py check: two emissions per map {done} byte-identical to the committed generated files"


# -- step 5: T1 and T2 (grids and preview)

def row_t1_t2_grids(ctx, mods, sec6, row, cache):
    """T1 (FG): the thresholded-elevation grid at every pixel centre at scales 1 and 6 and the scale 1
    preview each meet 0.991 with thin water masked, every land component of 65 px or more present;
    every pixel where scale 1's grid bits and preview tiles disagree lies in S8's uncertain band.
    T2 (FG): the grids at seeds 1002 and 1004 equal seed 1000's outside the T1 masks, at both
    scales. T2's exit-0 guards (test notes): every grid run reads back the seed it asked for
    (map_gen_settings.seed) and tn_map above 0 at the spawn through the surface, and as the positive
    control M0's grid, compared the same way, differs across the same three seeds (TST-21; G6), so a
    seed that stopped reaching the runs would fail instead of reading as invariance."""
    import earthgeo as eg
    cfg = mods.cfg
    K = cfg["keys"]
    _, mk, _ = first_preset(cfg)
    mref = eg.MapRef(mk)
    lanes_ms = [probe_modset(ctx, mods, f"m1g{i + 1}") for i in range(PAR_MAX)]
    vms = mods.make(f"ea-m1v1-{mods.zip_sha[:8]}", [mods.build_zip()])
    mods.prepare(vms, "m1v1")
    m0g = m0_probe(ctx, mods, "m0g1")
    mgs = {s: preset_mgs(ctx, cfg, s, coast_only=True) for s in T1_SCALES_FG}
    pv_mgs = preset_mgs(ctx, cfg, 1, cliffs=False, coast_only=True)
    size, offs = preview_plan(mref, 1)
    key, newest = common_key(ctx, "t1_t2_grids", {"ms": [mods.manifest(m) for m in lanes_ms + [vms, m0g]],
                                                    "dump": ctx.shared.get("dump_m1_sha"), "seeds": SEEDS,
                                                    "scales": T1_SCALES_FG, "preview": [size, offs]})
    jobs = []
    for seed in SEEDS:
        for s in T1_SCALES_FG:
            jobs.append((seed, s))
    n_jobs = len(jobs)

    def live():
        lanes = [[] for _ in range(PAR_MAX)]
        dirs = []
        for i, (seed, s) in enumerate(jobs):
            ln = i % PAR_MAX
            ms, inst = lanes_ms[ln], lane_instance(ctx, ln)
            out = ctx.out / f"t1-grid-s{s}-{seed}"
            lanes[ln].append((dump_settings(ctx, ms, inst, label="grid", grid=grid_spec(mref, s), points="0,0",
                                            names=K["map"]),
                              scenario_args(inst, ms, 4, seed, mgs[s]), out, 900))
            dirs.append(out)
        # the preview runs on an instance and a modset of its own: a fifth worker, started when one ends
        pv = ctx.out / "t1-preview-s1"
        lanes.append([(None, preview_args(lane_instance(ctx, PAR_MAX), vms, size, SEED, pv_mgs, offs[0]), pv, 600)])
        # T2's positive control: M0's scale 1 grid at the same three seeds, a sixth worker of its own
        m0_inst = lane_instance(ctx, PAR_MAX + 1)
        m0_dirs = [ctx.out / f"t2-m0-grid-{seed}" for seed in SEEDS]
        lanes.append([(dump_settings(ctx, m0g, m0_inst, label="grid", grid=grid_spec(mref, 1)),
                       scenario_args(m0_inst, m0g, 4, seed), out, 900) for seed, out in zip(SEEDS, m0_dirs)])
        run_lanes(ctx, [l for l in lanes if l])
        dirs.append(pv)
        dirs += m0_dirs
        # disagreements between scale 1's grid bits and its preview tiles get their elevation probed
        bad = grid_preview_disagreements(ctx, mods, mref, dirs[0], pv, offs[0])
        if bad:
            pts = ";".join(f"{x},{y}" for x, y in bad[:400])
            ms, inst = lanes_ms[0], lane_instance(ctx, 0)
            dump_settings(ctx, ms, inst, label="band", points=pts, names="elevation")()
            r = ctx.fh(scenario_args(inst, ms, 4, SEED, mgs[1]), ctx.out / "t1-band-probe")
            dirs.append(r.out)
        return dirs

    def derive(dirs):
        fails, meas = [], {}
        for d in dirs:
            fails += g1(d) + g3(d)
        grids = {}
        for i, (seed, s) in enumerate(jobs):
            grids[(seed, s)] = grid_land(mref, dirs[i], s)
            # T2's exit-0 guards: the run used its own seed, and the world is an Earth preset world
            fails += dump_seed_fails(dirs[i], "grid", seed) + spawn_map_fails(dirs[i], "grid", K["map"])
        pv = dirs[n_jobs]
        m0_dirs = dirs[n_jobs + 1:n_jobs + 1 + len(SEEDS)]
        band = dirs[n_jobs + 1 + len(SEEDS)] if len(dirs) > n_jobs + 1 + len(SEEDS) else None
        colours = blocking_water_colours(ctx.shared["dump_m1"])
        Lp, Cp, Hp = previews_land(mref, [(pv, offs[0])], 1, colours, cliff_colours(ctx.shared["dump_m1"]))
        meas["preview_cliff_pixels"] = int(Hp.sum())
        if Hp.any():
            fails.append(f"{int(Hp.sum())} cliff pixels in the cliff-free preview: the cliff setting did not apply")
        for s in T1_SCALES_FG:
            rec = t1_eval(mref, *grids[(SEED, s)])
            meas[f"grid_s{s}"] = rec
            fails += t1_fails(f"grid scale {s}", rec)
        rec = t1_eval(mref, Lp, Cp)
        meas["preview_s1"] = rec
        fails += t1_fails("preview scale 1", rec)
        # T2: every seed's grid bits equal seed 1000's outside the masks
        def seed_diff(L0, C0, L, C):
            return int(((L != L0) & C & C0 & ~mref.thin).sum())
        for s in T1_SCALES_FG:
            L0, C0 = grids[(SEED, s)]
            for seed in SEEDS[1:]:
                diff = seed_diff(L0, C0, *grids[(seed, s)])
                meas[f"t2_s{s}_{seed}"] = diff
                if diff:
                    fails.append(f"T2: scale {s} seed {seed}: {diff} grid bits differ from seed {SEED} outside the masks")
        # T2's positive control: the same comparison on M0's grids sees the seed (TST-21; G6)
        m0 = {}
        for seed, d in zip(SEEDS, m0_dirs):
            fails += dump_seed_fails(d, "grid", seed)
            m0[seed] = grid_land(mref, d, 1)
        for seed in SEEDS[1:]:
            diff = seed_diff(*m0[SEED], *m0[seed])
            meas[f"t2_m0_{seed}"] = diff
            if not diff:
                fails.append(f"T2 positive control: M0's grid at seed {seed} equals seed {SEED}'s outside the masks, so "
                             f"the comparison cannot see a seed change (TST-21)")
        # grid against preview at scale 1: each disagreement must lie in the uncertain band
        L1, C1 = grids[(SEED, 1)]
        dis = (L1 != Lp) & C1 & Cp
        meas["grid_vs_preview_s1"] = int(dis.sum())
        if dis.any():
            if band is None:
                fails.append(f"{int(dis.sum())} pixels disagree between grid bits and preview tiles and no probe ran")
            else:
                fails += dump_seed_fails(band, "band", SEED)
                vals = point_values(read_dump(band, "band"))
                out_band = [p for p, v in vals.items() if not (UNCERTAIN_BAND[0] <= (v.get("elevation") or 0)
                                                              < UNCERTAIN_BAND[1])]
                if out_band or int(dis.sum()) > len(vals):
                    fails.append(f"{int(dis.sum())} pixels disagree between grid bits and preview tiles; "
                                 f"{len(out_band)} probed outside S8's band {UNCERTAIN_BAND}, e.g. {out_band[:3]}")
        g6, p1 = meas["grid_s6"], meas["preview_s1"]
        return meas, fails, (f"grid T1 {meas['grid_s1']['agreement']} (scale 1) and {g6['agreement']} (scale 6), "
                             f"cliff-free preview ({meas['preview_cliff_pixels']} cliff pixels), "
                             f"preview {p1['agreement']} (scale 1), coast p99 {p1['p99_px']} max {p1['max_px']} px, "
                             f"65+ islands present {p1['islands_conn4']['65+']}; thin water become land "
                             f"{p1['thin_water_became_land']}; grid against preview {meas['grid_vs_preview_s1']} "
                             f"pixels apart; T2 0 differing bits at seeds {list(SEEDS[1:])}, each run on its own seed "
                             f"with {K['map']} above 0; control: M0's grid differs at seeds {list(SEEDS[1:])} in "
                             f"{[meas.get(f't2_m0_{s_}') for s_ in SEEDS[1:]]} bits")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def grid_preview_disagreements(ctx, mods, mref, grid_dir, pv_dir, off):
    """Tiles (scale 1) where the grid's thresholded elevation and the preview's tile disagree."""
    import numpy as np
    L1, C1 = grid_land(mref, grid_dir, 1)
    Lp, Cp, _ = previews_land(mref, [(pv_dir, off)], 1, blocking_water_colours(ctx.shared["dump_m1"]),
                              cliff_colours(ctx.shared["dump_m1"]))
    rr, cc = np.nonzero((L1 != Lp) & C1 & Cp)
    return [(int(c) - mref.wr, int(r) - mref.hr) for r, c in zip(rr.tolist(), cc.tolist())]


# -- step 6: T3 (oracle places, the far field, the extents)

def far_points(mref, scale):
    """On the row and the column through the spawn: probe tiles 1, 100, 10,000 and 100,000 tiles
    beyond each map edge, in FAR_PROBES order, four per distance (left, right, top, bottom); the
    window of tiles EDGE_WINDOW each side of each edge, in which the runner finds where the far-field
    box switches (the measured extent); and the extent floor(W s) x floor(H s) the switch must give."""
    s = int(scale)
    left, right = -s * mref.wr, s * (mref.W - mref.wr) - 1
    top, bottom = -s * mref.hr, s * (mref.H - mref.hr) - 1
    far = []
    for d in FAR_PROBES:
        far += [(left - d, 0), (right + d, 0), (0, top - d), (0, bottom + d)]
    ks = range(-EDGE_WINDOW, EDGE_WINDOW + 1)
    window = {"left": [(left + k, 0) for k in ks], "right": [(right + k, 0) for k in ks],
              "top": [(0, top + k) for k in ks], "bottom": [(0, bottom + k) for k in ks]}
    return far, window, (mref.W * s, mref.H * s)


def edge_switch(window, vals, far_name, floor):
    """(the outermost tile of the window's run inside the map, or None) for one edge: the window
    runs from inside to outside or the reverse; the tiles whose far body reads the floor are outside.
    None when the window does not hold exactly one switch from inside to outside."""
    inside = [p for p in window if (vals.get(p) or {}).get(far_name) not in (None, floor) and
              not isinstance((vals.get(p) or {}).get(far_name), str)]
    outside = [p for p in window if (vals.get(p) or {}).get(far_name) == floor]
    if not inside or not outside or len(inside) + len(outside) != len(window):
        return None
    return inside, outside


def row_t3_oracle(ctx, mods, sec6, row, cache):
    """T3 (FG; scale 6): every oracle place's land or water expectation holds at expression level and
    in its real tile (strait and canal rows stay null until waterways); probes 1, 100, 10,000 and
    100,000 tiles beyond each map edge read deep water (D15), at scale 6 and at every scale from the
    edge ring's (config.lua coast.edge_min_scale), and from 100 tiles out at every scale; at scales 1
    to 6 the far-field box switches exactly at the extent, measured from a window of tiles across
    each edge on the spawn's row and column, which must give floor(W s) x floor(H s) tiles; from the
    ring's scale the extent's outermost tile reads the edge water and below it the map's own value.
    Exit-0 guards (test notes T3): every probe reads tn_map above 0 through the surface, and the
    real tiles at the water places differ from M0's tiles at the same positions."""
    import earthgeo as eg
    import oracle
    cfg = mods.cfg
    _, mk, g = first_preset(cfg)
    K = cfg["keys"]
    mref = eg.MapRef(mk)
    O = oracle.load_oracle(mk, TESTS / "oracle")
    E = json.loads((TESTS / "oracle" / "expressions.json").read_text(encoding="utf-8"))
    lanes_ms = [probe_modset(ctx, mods, f"m1g{i + 1}") for i in range(PAR_MAX)]
    m0p = mods.with_mods("m0p", [HERE / "mods" / "ep-s8-dump"], earth=False)
    mods.prepare(m0p, "m0p")
    names = f"elevation,{g['entry']},{g['far']},{K['map']}"
    places = [tuple(oracle.place_tile(mref, p, "6")) for p in O["places"]]
    # the positions where the probe expects water: the oracle's water places (none until waterways
    # adds straits) and the scale 6 far probes, which must read deep water; M0 is probed there too
    far6 = far_points(mref, 6)[0]
    m0_points = list(dict.fromkeys(places + far6))
    plan = {}
    for s in DETAIL_SCALES:
        far, window, _ = far_points(mref, s)
        pts = far + [p for side in window.values() for p in side]
        if s == 6:
            pts = places + pts
        plan[s] = list(dict.fromkeys(pts))
    key, newest = common_key(ctx, "t3_oracle", {"ms": [mods.manifest(m) for m in lanes_ms], "m0p": mods.manifest(m0p),
                                                  "plan": plan, "m0_points": m0_points,
                                                  "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        lanes = [[] for _ in range(PAR_MAX)]
        dirs = []
        for i, s in enumerate(DETAIL_SCALES):
            ln = i % PAR_MAX
            ms, inst = lanes_ms[ln], lane_instance(ctx, ln)
            out = ctx.out / f"t3-s{s}"
            lanes[ln].append((dump_settings(ctx, ms, inst, label="t3", points=";".join(f"{x},{y}" for x, y in plan[s]),
                                            names=names),
                              scenario_args(inst, ms, 4, SEED, preset_mgs(ctx, cfg, s, coast_only=True)), out,
                              900))
            dirs.append(out)
        # M0 at the same oracle positions: the exit-0 guard's vanilla tiles
        ln = PAR_MAX - 1
        inst = lane_instance(ctx, ln)
        out = ctx.out / "t3-m0"
        lanes[ln].append((dump_settings(ctx, m0p, inst, label="t3", points=";".join(f"{x},{y}" for x, y in m0_points),
                                        names="elevation"),
                          scenario_args(inst, m0p, 4, SEED), out, 900))
        dirs.append(out)
        run_lanes(ctx, [l for l in lanes if l])
        return dirs

    def derive(dirs):
        fails, meas = [], {}
        for d in dirs:
            fails += g1(d) + g3(d)
        floor = cfg["coast"]["far_floor"]
        edge_water = cfg["coast"]["edge_water"]
        ring_from = int(cfg["coast"]["edge_min_scale"])
        ring_at_1, deep_at_1 = {}, {}
        for d in dirs:
            fails += dump_seed_fails(d, "t3", SEED)
        for i, s in enumerate(DETAIL_SCALES):
            vals = point_values(read_dump(dirs[i], "t3"))
            far, window, want = far_points(mref, s)
            # tn_map through the surface at every probe (test notes T3's exit-0 guard)
            bad_map = [p for p, v in vals.items() if not isinstance(v.get(K["map"]), (int, float)) or
                       isinstance(v.get(K["map"]), bool) or not v[K["map"]] > 0]
            if bad_map or not vals:
                fails.append(f"scale {s}: {K['map']} reads {(vals.get(bad_map[0]) or {}).get(K['map']) if bad_map else None}"
                             f" at {bad_map[:1] or 'no probe'}, not above 0: the preset is not what the probe reads "
                             f"(T3 exit-0 guard)")
            # the measured extent: where the far-field box switches on the spawn's row and column
            span = {}
            for side, pts in window.items():
                sw = edge_switch(pts, vals, g["far"], floor)
                if sw is None:
                    fails.append(f"scale {s} {side} edge: no single switch of {g['far']} to {floor} across "
                                 f"{pts[0]}..{pts[-1]}: {[(vals.get(p) or {}).get(g['far']) for p in pts]}")
                    continue
                inside, outside = sw
                axis = 0 if side in ("left", "right") else 1
                last = min(p[axis] for p in inside) if side in ("left", "top") else max(p[axis] for p in inside)
                span[side] = last
                # every outside tile lies beyond every inside tile: one clean switch
                beyond = all(p[axis] < last for p in outside) if side in ("left", "top") else \
                    all(p[axis] > last for p in outside)
                if not beyond:
                    fails.append(f"scale {s} {side} edge: tiles inside and outside the extent interleave")
                ring = (vals.get((last, 0) if axis == 0 else (0, last)) or {}).get(g["far"])
                if s >= ring_from and ring != edge_water:
                    fails.append(f"scale {s} {side} edge: the outermost tile {last} reads {ring} in {g['far']}, not "
                                 f"the edge water {edge_water}")
                if s < ring_from and ring == edge_water:
                    fails.append(f"scale {s} {side} edge: the outermost tile reads the edge water, which below scale "
                                 f"{ring_from} would sit on a pixel-centre tile")
            if len(span) == 4:
                got = (span["right"] - span["left"] + 1, span["bottom"] - span["top"] + 1)
                meas[f"extent_s{s}"] = list(got)
                if got != want:
                    fails.append(f"scale {s}: measured extent {got} differs from floor(W s) x floor(H s) {want}")
            for p, v in vals.items():
                if v.get("elevation") != v.get(g["entry"]):
                    fails.append(f"scale {s} {p}: elevation {v.get('elevation')} is not the entry's "
                                 f"{v.get(g['entry'])}: the preset did not apply (G5)")
                    break
            # the far probes: deep water from 1 tile out where the ring exists, from 100 tiles out
            # everywhere; below the ring's scale plain water 1 tile out is reported
            ring_at_1[s], deep_at_1[s] = 0, 0
            for i_, p in enumerate(far):
                v = vals.get(p, {})
                d_ = FAR_PROBES[i_ // 4]
                tile = str(v.get("tile"))
                if v.get("elevation") is None or v["elevation"] != floor or v["elevation"] >= DEEP_BELOW:
                    fails.append(f"scale {s} far probe {p}: elevation {v.get('elevation')}, want the far floor {floor} "
                                 f"(D15)")
                elif "deepwater" in tile:
                    deep_at_1[s] += d_ == 1
                elif d_ == 1 and s < ring_from and tile == "water":
                    ring_at_1[s] += 1
                else:
                    fails.append(f"scale {s} far probe {p}, {d_} tiles out: tile {tile} (D15: deep water)")
            if s != 6:
                continue
            ok = bad = 0
            m0 = point_values(read_dump(dirs[len(DETAIL_SCALES)], "t3"))
            water_places = differ = 0
            for pl in O["places"]:
                t = tuple(oracle.place_tile(mref, pl, "6"))
                v = vals.get(t, {})
                for prop in ("land", "water"):
                    want_v = pl["expect"].get(prop)
                    spec = E.get(prop) or {}
                    if want_v is None or not spec.get("expr"):
                        continue
                    got = oracle.decode(spec, v.get(spec["expr"]) if v.get(spec["expr"]) is not None else float("nan"))
                    tile_water = "water" in str(v.get("tile"))
                    tile_ok = (not tile_water) if prop == "land" else tile_water
                    if got != want_v or tile_ok != bool(want_v):
                        bad += 1
                        fails.append(f"{pl['name']} {prop}: expression {v.get(spec['expr'])} -> {got}, tile "
                                     f"{v.get('tile')}, want {want_v}")
                    else:
                        ok += 1
                if pl["expect"].get("water") is True:
                    water_places += 1
                    differ += str(v.get("tile")) != str((m0.get(t) or {}).get("tile"))
            for q in far6:
                water_places += 1
                differ += str((vals.get(q) or {}).get("tile")) != str((m0.get(q) or {}).get("tile"))
            meas["oracle"] = {"pass": ok, "fail": bad}
            meas["water_places_differing_from_m0"] = [differ, water_places]
            if ok == 0:
                fails.append("no oracle place carries a land or water expectation with a mapped expression")
            if not water_places or not differ:
                fails.append(f"the real tiles at the {water_places} water places (the oracle's and the far probes) equal "
                             f"M0's at the same positions: the probe may not read Earth tiles (T3 exit-0 guard)")
        meas["deep_water_1_tile_out"] = {str(s): deep_at_1[s] for s in DETAIL_SCALES}
        meas["plain_water_1_tile_out"] = {str(s): ring_at_1[s] for s in DETAIL_SCALES}
        return meas, fails, (f"oracle {meas.get('oracle')} at scale 6 (expression and real tile), water places "
                             f"differing from M0 {meas.get('water_places_differing_from_m0')}; far probes "
                             f"{list(FAR_PROBES)} tiles beyond each edge deep water at scales {ring_from} to 6 (1 tile "
                             f"out: {[deep_at_1[s] for s in DETAIL_SCALES]} of 4 deep at scales 1 to 6; plain water "
                             f"{[ring_at_1[s] for s in DETAIL_SCALES]} below scale {ring_from}, where the outermost "
                             f"tile holds a pixel centre); measured extents "
                             f"{[meas.get(f'extent_s{s}') for s in DETAIL_SCALES]}; {K['map']} above 0 at every probe")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 9: T11 one A then B pair

T11_TYPES = "resource,tree,cliff,unit-spawner"  # test notes T11: resources, trees, cliffs and spawners


def t11_names(cfg, map_key):
    """The names a T11 probe reads at (0, 0) through the surface: every number the preset bakes (tn_map,
    tn_scale, tn_geo, the city offset and, with a spawn record, the city number) and elevation."""
    g, K = tnconfig.geography(cfg)[map_key], cfg["keys"]
    city = [g["city"]] if g.get("spawn") else []
    return ",".join([K["scale"], K["map"], K["geo"], g["cx"], g["cy"]] + city + ["elevation"])


def t11_compare(cfg, map_key, a, b, ab, aa, bb):
    """One T11 pair from its three probe dumps (A loaded under B, A under A, B under B): tiles and
    entities against fresh A (0 differ), tiles against fresh B (more than 0, G6) and entities against
    fresh B (reported), the values read back as A's, and tn_map above 0 in each world. Returns
    (measurements, failures)."""
    K = cfg["keys"]
    fails = []
    seeds = [x.get("seed") for x in (ab, aa, bb)]
    if any(s_ != SEED for s_ in seeds):
        fails.append(f"the three worlds read seeds {seeds}, created at {SEED} (exit-0 guard)")
    # S2's round trip: in every world the late chunk was generated after a whole-table
    # map_gen_settings assignment, and the baked names survived it unchanged
    for label, x in (("A loaded under B", ab), ("A under A", aa), ("B under B", bb)):
        fails += t11_roundtrip_fails(cfg, map_key, label, x)
    tab, taa, tbb = (area_tiles(x) for x in (ab, aa, bb))
    if len(tab) != T11_CHUNKS * 1024 or len(taa) != len(tab) or len(tbb) != len(tab):
        fails.append(f"probe set sizes {len(tab)}, {len(taa)}, {len(tbb)}, want {T11_CHUNKS * 1024}")
    d_aa = sum(1 for x, y in zip(tab, taa) if x != y)
    d_bb = sum(1 for x, y in zip(tab, tbb) if x != y)
    late = T11_LATE_CHUNKS * 1024
    d_late = sum(1 for x, y in zip(tab[-late:], taa[-late:]) if x != y) if len(tab) >= late else None
    if d_aa:
        fails.append(f"A loaded under B differs from A in {d_aa} of {len(tab)} tiles (want 0)")
    if d_late:
        fails.append(f"the late chunk generated after the round trip differs from fresh A in {d_late} tiles (want 0)")
    if not d_bb:
        fails.append("A loaded under B equals a fresh B world: the scale did not shape the map (G6)")
    eab, eaa, ebb = (area_entities(x) for x in (ab, aa, bb))
    e_aa, e_bb = entity_difference(eab, eaa), entity_difference(eab, ebb)
    if not eab or not eaa:
        fails.append(f"the probe set holds {len(eab)} and {len(eaa)} entities: the entity compare tests nothing")
    if e_aa:
        fails.append(f"A loaded under B differs from A in {e_aa} entities of {len(eab)} (want 0)")
    # entities against fresh B are reported: inland the entity layer follows vanilla's climate, which no
    # scale moves, so a pair may show none (the suite requires some pair to show them)
    pts = [point_values(x).get((0, 0), {}) for x in (ab, aa, bb)]
    back, back_b = read_back(cfg, pts[0], map_key, a), read_back(cfg, pts[2], map_key, b)
    if back:
        fails.append(f"values read back under B are not A's: {back}")
    if back_b:
        fails.append(f"the fresh B world reads {back_b} (want its own values)")
    maps = [v.get(K["map"]) for v in pts]
    if not all(isinstance(m, (int, float)) and not isinstance(m, bool) and m > 0 for m in maps):
        fails.append(f"{K['map']} reads {maps} in the three worlds, not above 0 in each (T11 exit-0 guard)")
    meas = {"tiles": len(tab), "differing_vs_fresh_a": d_aa, "differing_vs_fresh_b": d_bb, "entities": len(eab),
            "entities_differing_vs_fresh_a": e_aa, "entities_differing_vs_fresh_b": e_bb,
            "late_tiles_differing_vs_fresh_a": d_late,
            "roundtrip_names": len(((ab.get("roundtrip") or {}).get("pen_after")) or {}),
            "read_back": {k: pts[0].get(k) for k in t11_names(cfg, map_key).split(",") if k != "elevation"},
            "tn_map": maps}
    return meas, fails


def t11_roundtrip_fails(cfg, map_key, label, dump):
    """S2's whole-table round trip in one probe dump (ep-s8-dump's late areas): the probe assigned
    surface.map_gen_settings to itself before generating its late area, recorded
    property_expression_names before and after, and the two are equal and hold every key the preset
    bakes (tn_geo among them, so the world is an Earth preset world), with the late area dumped."""
    rt = dump.get("roundtrip")
    if not isinstance(rt, dict) or not isinstance(rt.get("pen_before"), dict) or \
            not isinstance(rt.get("pen_after"), dict):
        return [f"{label}: the probe recorded no map_gen_settings round trip before its late area"]
    fails = []
    before, after = rt["pen_before"], rt["pen_after"]
    if before != after:
        diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        fails.append(f"{label}: property_expression_names changed across the round trip at {diff}")
    want = [k for k in expected_pen(cfg, map_key, 1) if k not in after]
    if want:
        fails.append(f"{label}: after the round trip the surface lacks the baked keys {want}")
    if dump.get("late_area_count") != T11_LATE_CHUNKS:
        fails.append(f"{label}: the probe dumped {dump.get('late_area_count')!r} late areas, want {T11_LATE_CHUNKS}")
    return fails


def row_t11_pair(ctx, mods, sec6, row, cache):
    """T11 (FG): a scale 3 world created under settings A and loaded under B (scale 5)
    generates S2's 41-chunk probe set, requested in one fixed order, its 41st chunk (60, 0) only
    after S2's whole-table map_gen_settings round trip (property_expression_names equal before and
    after it, every baked key kept), with 0 differing tiles and 0
    differing entities (resources with their amounts, trees, cliffs with their orientations,
    spawners) against the same world loaded under A (a fresh A world), more than 0 differing tiles
    against a fresh B world (G6) and the entities against it reported; every per-save value the
    preset bakes (tn_map, tn_scale, tn_geo, the city offset) reads back as A's through the surface,
    and tn_map is above 0 in all three worlds (test notes T11's exit-0 guard); the drift line
    appears once for the drifted scale and never on an undrifted load (A under A, whose own startup
    settings changed too: the probe's)."""
    cfg = mods.cfg
    pname, mk, _ = first_preset(cfg)
    a, b = T11_AB
    msa = probe_modset(ctx, mods, f"m1t11a{a}", scale=a)
    msb = probe_modset(ctx, mods, f"m1t11b{b}", scale=b)
    names = t11_names(cfg, mk)
    key, newest = common_key(ctx, "t11_pair", {"a": mods.manifest(msa), "b": mods.manifest(msb), "ab": T11_AB,
                                                 "areas": T11_AREAS, "late": T11_LATE, "types": T11_TYPES,
                                                 "names": names})

    def live():
        inst = ctx.instance
        sa, sb = ctx.out / "t11-create-a" / "a.zip", ctx.out / "t11-create-b" / "b.zip"
        r1 = ctx.fh(create_args(inst, msa, sa, preset=pname), sa.parent)
        r2 = ctx.fh(create_args(inst, msb, sb, preset=pname), sb.parent)
        outs = [r1.out, r2.out]
        for label, ms, save in (("a-under-b", msb, sa), ("a-under-a", msa, sa), ("b-under-b", msb, sb)):
            dump_settings(ctx, ms, inst, label="t11", areas=T11_AREAS, late_areas=T11_LATE, points="0,0", names=names,
                          types=T11_TYPES)()
            outs.append(ctx.fh(scenario_args(inst, ms, 4, save=save), ctx.out / f"t11-{label}").out)
        return outs

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        ab, aa, bb = (read_dump(d, "t11") for d in dirs[2:5])
        meas, f = t11_compare(cfg, mk, a, b, ab, aa, bb)
        fails += f
        line = render_message(cfg, "drift_scale", a, b)
        n_ab = count_lines(log_text(dirs[2]), line)
        any_drift = message_prefix(cfg, "drift_scale")
        n_aa_any = count_lines(log_text(dirs[3]), any_drift)
        n_bb_any = count_lines(log_text(dirs[4]), any_drift)
        if n_ab != 1:
            fails.append(f"the drift line appears {n_ab} times on A loaded under B (want once): {line!r}")
        if n_aa_any or n_bb_any:
            fails.append(f"a drift line appears on an undrifted load (A under A {n_aa_any}, B under B {n_bb_any})")
        meas["drift_lines"] = [n_ab, n_aa_any, n_bb_any]
        return meas, fails, (f"scale {a} world loaded under scale {b}: {meas['differing_vs_fresh_a']} of {meas['tiles']} "
                             f"tiles and {meas['entities_differing_vs_fresh_a']} of {meas['entities']} entities differ "
                             f"from fresh A, {meas['differing_vs_fresh_b']} tiles and "
                             f"{meas['entities_differing_vs_fresh_b']} entities from fresh B (S2: 0 and 22,341 of "
                             f"41,984 tiles); read back {meas['read_back']}, {cfg['keys']['map']} {meas['tn_map']}; "
                             f"drift line once, none on undrifted loads")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 10: T12 created twice

def row_t12_twice(ctx, mods, sec6, row, cache):
    """T12 (FG): Europe at scale 6, seed 1000, created twice: identical benchmark checksums and 0
    differing tiles in 3 x 3 chunks around the spawn and 3 x 3 chunks on the Baltic shore north of
    it (coast_view), so water is compared as well as land. Exit-0 guards: both runs read back seed
    1000 and tn_map above 0 at the spawn through the surface (Earth was active), and as the positive
    control M0's world at the same seed and areas differs from Earth's in its tiles and its checksum
    (G6), so the compare can see two different worlds (at the inland spawn alone both are vanilla
    land: measured 0 differing tiles there)."""
    cfg = mods.cfg
    K = cfg["keys"]
    ms = [probe_modset(ctx, mods, f"m1g{i + 1}") for i in range(2)]
    m0p = m0_probe(ctx, mods, "m0g3")
    mgs = preset_mgs(ctx, cfg, 6)
    cx_, cy_ = coast_view(cfg)
    areas = f"{T12_AREA};{cx_ - 48},{cy_ - 48},96,96"
    key, newest = common_key(ctx, "t12_twice", {"ms": [mods.manifest(m) for m in ms + [m0p]], "area": areas,
                                                  "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        lanes = []
        dirs = []
        for i in range(2):
            inst = lane_instance(ctx, i)
            out = ctx.out / f"t12-{i + 1}"
            lanes.append([(dump_settings(ctx, ms[i], inst, label="t12", areas=areas, points="0,0", names=K["map"]),
                           scenario_args(inst, ms[i], 4, SEED, mgs), out, 900)])
            dirs.append(out)
        inst = lane_instance(ctx, 2)
        out = ctx.out / "t12-m0"
        lanes.append([(dump_settings(ctx, m0p, inst, label="t12", areas=areas), scenario_args(inst, m0p, 4, SEED),
                       out, 900)])
        dirs.append(out)
        run_lanes(ctx, lanes)
        return dirs

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d) + dump_seed_fails(d, "t12", SEED)
        for d in dirs[:2]:
            fails += spawn_map_fails(d, "t12", K["map"])
        cs = [(load_run_json(d) or {}).get("bench_checksums") for d in dirs]
        if not cs[0] or cs[0] != cs[1]:
            fails.append(f"benchmark checksums differ: {cs[:2]}")
        t = [area_tiles(read_dump(d, "t12")) for d in dirs]
        diff = sum(1 for x, y in zip(t[0], t[1]) if x != y)
        if diff or len(t[0]) != len(t[1]) or not t[0]:
            fails.append(f"{diff} of {len(t[0])} tiles differ between two creations")
        # positive control: the vanilla world at the same seed and area is a different world
        d_m0 = sum(1 for x, y in zip(t[0], t[2]) if x != y)
        if not d_m0 or len(t[2]) != len(t[0]) or cs[2] == cs[0]:
            fails.append(f"positive control: M0's world differs from Earth's in {d_m0} of {len(t[0])} tiles with "
                         f"checksums {cs[2]} and {cs[0]}: the compare cannot see two different worlds (G6)")
        return {"checksums": cs[:2], "tiles": len(t[0]), "differing": diff, "m0_differing": d_m0,
                "m0_checksums": cs[2]}, fails, \
            (f"created twice: checksums {cs[0]} equal, {diff} of {len(t[0])} tiles (spawn and Baltic shore) differ; "
             f"both on seed {SEED} with {K['map']} above 0; control: M0 differs in {d_m0} tiles and its checksum")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 3: T13 route parity and the Map type route; T18 notice

def row_t13_routes(ctx, mods, sec6, row, cache):
    """T13 (FG; 256 px; seed 1000): --preset and a full --map-gen-settings file (never both) give the
    same preview and, created with --create and loaded, the same tiles and checksums. Exit-0 guards
    (test notes T13): G2 on every preview and creation, the route preview differs from M0's at the
    same seed, size and offset, and both loaded worlds read tn_map above 0 at the spawn, so two
    worlds that both fell back to vanilla cannot pass as equal."""
    cfg = mods.cfg
    K = cfg["keys"]
    pname, _, _ = first_preset(cfg)
    ms = probe_modset(ctx, mods, "m1g1")
    m0 = ctx.shared["m0"]
    mgs = preset_mgs(ctx, cfg)
    key, newest = common_key(ctx, "t13_routes", {"ms": mods.manifest(ms), "m0": mods.manifest(m0),
                                                   "dump": ctx.shared.get("dump_m1_sha"), "area": T12_AREA})

    def live():
        inst = ctx.instance
        off = coast_view(cfg)
        a = ctx.fh(preview_args(inst, ms, 256, preset=pname, offset=off), ctx.out / "route-preview-preset").out
        b = ctx.fh(preview_args(inst, ms, 256, mgs=mgs, offset=off), ctx.out / "route-preview-mgs").out
        sp, sm = ctx.out / "route-create-preset" / "p.zip", ctx.out / "route-create-mgs" / "m.zip"
        c = ctx.fh(create_args(inst, ms, sp, preset=pname), sp.parent).out
        d = ctx.fh(create_args(inst, ms, sm, mgs=mgs), sm.parent).out
        outs = [a, b, c, d]
        for label, save in (("preset", sp), ("mgs", sm)):
            dump_settings(ctx, ms, inst, label="route", areas=T12_AREA, types=ROUTE_TYPES, points="0,0",
                          names=K["map"])()
            outs.append(ctx.fh(scenario_args(inst, ms, 4, save=save), ctx.out / f"route-load-{label}").out)
        outs.append(ctx.fh(preview_args(inst, m0, 256, offset=off), ctx.out / "route-preview-m0").out)
        return outs

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        # G2 on every preview and creation (a load from a save prints no checksum lines)
        for d in dirs[:4]:
            fails += g2(d, [cfg["identity"]["id"], "base"])
        fails += g2(dirs[6], ["base"])
        for d in dirs[4:6]:
            fails += spawn_map_fails(d, "route", K["map"])
        pa, pb = derive_preview(dirs[0]), derive_preview(dirs[1])
        pz = derive_preview(dirs[6])
        if not pa["images"] or pa["images"] != pb["images"]:
            fails.append(f"the preset and MGS previews differ: {pa['images']} vs {pb['images']}")
        if not pz["images"] or list(pz["images"].values()) == list(pa["images"].values()):
            fails.append("the route preview equals M0's at the same seed, size and offset: Earth was not active (G5)")
        da, db = (read_dump(d, "route") for d in dirs[4:6])
        ta, tb = area_tiles(da), area_tiles(db)
        diff = sum(1 for x, y in zip(ta, tb) if x != y)
        ea, eb = area_entities(da), area_entities(db)
        ca, cb = ((load_run_json(d) or {}).get("bench_checksums") for d in dirs[4:6])
        if diff or not ta or len(ta) != len(tb):
            fails.append(f"the two created worlds' tiles differ: {diff} of {len(ta)}")
        if ea != eb or not ea:
            fails.append(f"the two created worlds' entities differ: {len(ea)} against {len(eb)}")
        # the benchmark checksums differ between the routes while tiles, entities, generated chunks and
        # the surface's map gen settings agree: recorded, not compared
        return {"preview": pa["images"], "m0_preview": pz["images"], "tiles_differing": diff, "entities": len(ea),
                "checksums": [ca, cb]}, fails, \
            (f"--preset and a full --map-gen-settings file: one preview {list(pa['images'].values())[:1]}, unlike M0's; "
             f"created worlds equal ({diff} of {len(ta)} tiles and {len(ea)} entities differ by 0; benchmark checksums "
             f"{ca} and {cb} recorded), both with {K['map']} above 0; G2 on every preview and creation")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_maptype_route(ctx, mods, sec6, row, cache):
    """T13 (FG; the Map type route; scale 6; 256 px; seed 1000; S13): an MGS file that sets only
    elevation to Europe's entry previews and creates with exit 0, no error signature and no "is not
    defined; ignoring" line; its preview differs from M0's (G5) and its player-blocking water mask
    equals the preset world's. T18 (FG): that world's on_init logs the notice line exactly once,
    naming the preset and what it adds; a preset world and a default world never log it."""
    cfg = mods.cfg
    pname, _, g = first_preset(cfg)
    ms = mods.make(f"ea-m1v1-{mods.zip_sha[:8]}", [mods.build_zip()])
    mods.prepare(ms, "m1v1")
    m0 = ctx.shared["m0"]
    mt = maptype_mgs(ctx, cfg)
    key, newest = common_key(ctx, "maptype_route", {"ms": mods.manifest(ms), "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        inst = ctx.instance
        off = coast_view(cfg)
        outs = [ctx.fh(preview_args(inst, ms, 256, mgs=mt, offset=off), ctx.out / "mt-preview").out,
                ctx.fh(preview_args(inst, ms, 256, preset=pname, offset=off), ctx.out / "mt-preview-preset").out,
                ctx.fh(preview_args(inst, m0, 256, offset=off), ctx.out / "mt-preview-m0").out]
        for label, extra in (("maptype", {"mgs": mt}), ("preset", {"preset": pname}), ("default", {})):
            save = ctx.out / f"mt-create-{label}" / f"{label}.zip"
            outs.append(ctx.fh(create_args(inst, ms, save, **extra), save.parent).out)
        return outs

    def derive(dirs):
        import numpy as np
        import t1_metrics as t1
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        a, p, z = (derive_preview(d) for d in dirs[:3])
        if not a["images"] or a["images"] == z["images"]:
            fails.append("the Map type preview equals M0's: the entry was not applied (G5)")
        ws = t1.water_colour_set(blocking_water_colours(ctx.shared["dump_m1"]))
        wa = ~t1.preview_land(Path(dirs[0]) / f"{SEED}.png", ws)
        wp = ~t1.preview_land(Path(dirs[1]) / f"{SEED}.png", ws)
        diff = int((wa != wp).sum())
        if not wa.any() or wa.all():
            fails.append(f"the Map type preview holds {int(wa.sum())} water pixels: the view shows no coast to compare")
        if diff:
            fails.append(f"the Map type world's player-blocking water mask differs from the preset world's in {diff} "
                         f"pixels")
        notice = render_message(cfg, "notice", ("map-gen-preset-name", pname))
        counts = [count_lines(log_text(d), notice) for d in dirs[3:6]]
        if counts[0] != 1:
            fails.append(f"the elevation-only world logs the notice {counts[0]} times (want once): {notice!r}")
        if counts[1] or counts[2]:
            fails.append(f"the notice appears on a preset world ({counts[1]}) or a default world ({counts[2]})")
        meas = {"preview": a["images"], "water_mask_diff": diff, "water_px": int(np.sum(wa)), "notice": counts}
        return meas, fails, (f"elevation-only MGS: preview {list(a['images'].values())[:1]} differs from M0's, water mask "
                             f"equal to the preset world's ({int(np.sum(wa))} water pixels); notice logged {counts} times "
                             f"(Map type, preset, default)")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- step 11: the missing-name guard

def stage_drop(ctx, cfg, names, tag):
    """A staged copy of tools/mods/ea-drop-name dropping `names` (the runner names them at run time,
    so a rename stays a config edit): the test build with one Earth name dropped."""
    src = HERE / "mods" / "ea-drop-name"
    dst = ctx.out / "stage" / f"ea-drop-name-{tag}"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    lua = ", ".join(json.dumps(n) for n in names)
    (dst / "drop-names.lua").write_text(f"return {{names = {{{lua}}}}}\n", encoding="utf-8", newline="\n")
    info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
    info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
    (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    return dst


def row_t16_guard(ctx, mods, sec6, row, cache):
    """T16 (FG; review note 2 and 3): the missing-name guard fires on a test build with one Earth
    name dropped (the start mask, which a preset world names) and stays silent otherwise: the same
    preset save loaded beside the fixture dropping nothing (on_configuration_changed runs: a mod was
    added), and a Map-type-only save loaded with the name dropped."""
    cfg = mods.cfg
    pname, _, g = first_preset(cfg)
    dropped = g["start_mask"]
    key_name = cfg["keys"]["start_mask"]
    m1 = ctx.shared["m1"]
    drop = stage_drop(ctx, cfg, [dropped], "one")
    none = stage_drop(ctx, cfg, [], "none")
    md = mods.with_mods("m1drop", [drop])
    mn = mods.with_mods("m1dropnone", [none])
    mt = maptype_mgs(ctx, cfg)
    key, newest = common_key(ctx, "t16_guard", {"md": mods.manifest(md), "mn": mods.manifest(mn),
                                                  "m1": mods.manifest(m1), "dropped": dropped})

    def live():
        inst = ctx.instance
        sp, sm = ctx.out / "guard-create-preset" / "p.zip", ctx.out / "guard-create-maptype" / "m.zip"
        outs = [ctx.fh(create_args(inst, m1, sp, preset=pname), sp.parent).out,
                ctx.fh(create_args(inst, m1, sm, mgs=mt), sm.parent).out]
        for label, ms, save in (("dropped", md, sp), ("silent", mn, sp), ("maptype-dropped", md, sm)):
            outs.append(ctx.fh(scenario_args(inst, ms, 3, save=save), ctx.out / f"guard-load-{label}").out)
        return outs

    def derive(dirs):
        fails = []
        # the dropped name's own load is the positive control: the game logs the missing redirect
        # there (G3's signature, expected), and the guard must name the key and the dropped value
        for i, d in enumerate(dirs):
            fails += g1(d) + ([] if i == 2 else g3(d))
        line = render_message(cfg, "missing_name", key_name, dropped)
        prefix = message_prefix(cfg, "missing_name")
        n = [count_lines(log_text(d), line) for d in dirs[2:5]]
        any_n = [count_lines(log_text(d), prefix) for d in dirs[2:5]]
        if n[0] != 1:
            fails.append(f"the guard logged {n[0]} lines for the dropped {dropped} (want once): {line!r}")
        if any_n[1] or any_n[2]:
            fails.append(f"the guard spoke on the intact build ({any_n[1]}) or on the Map-type-only world ({any_n[2]})")
        return {"guard_lines": n, "any_guard_lines": any_n}, fails, \
            (f"dropping {dropped}: the guard names {key_name} once; silent beside a fixture dropping nothing and on "
             f"the Map-type-only world with the name dropped")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


# -- the water slider (D15: inert on Earth presets; config.lua's water_slider)

WATER_PREVIEW = 1024                # px: the reviewer's window at the spawn, cliffs drawn
WATER_VARIANTS = (("none", {"size": 0}), ("size-6", {"size": 6}), ("frequency-6", {"frequency": 6}),
                  ("frequency-1-6", {"frequency": 1 / 6}))
WATER_CONTROL = "control:water:"


def water_readers(dump):
    """Every named noise body and autoplace key of a dump whose own text reads control:water:*
    (vanilla 2.1.23: water_level, segmentation_multiplier and nauvis_segmentation_multiplier)."""
    ne, nf = dump.get("noise-expression") or {}, dump.get("noise-function") or {}
    out = set()
    for name in set(ne) | set(nf):
        texts, _ = _body_texts(ne, nf, name)
        if any(isinstance(tx, str) and WATER_CONTROL in tx for tx in texts or []):
            out.add(name)
    for k, (texts, _) in autoplace_index(dump).items():
        if any(isinstance(tx, str) and WATER_CONTROL in tx for tx in texts):
            out.add(k)
    return out


def generation_roots(dump):
    """[(root label, [property keys])] of everything Nauvis generates: every tile its autoplace settings
    list, every entity and decorative it places, and the two cliff properties."""
    planet = dump["planet"]["nauvis"]["map_gen_settings"]
    tiles = sorted(((((planet.get("autoplace_settings") or {}).get("tile") or {}).get("settings")) or {}))
    roots = [(f"tile/{n}", [f"tile:{n}:probability"]) for n in tiles]
    for group, items in placed_autoplace(dump).items():
        for t, name in items:
            roots.append((f"{t}/{name}", [f"{group}:{name}:probability", f"{group}:{name}:richness"]))
    roots += [(f"cliff:{prop}", [prop]) for prop in ("cliff_elevation", "cliffiness")]
    return roots


def walk_water(dump, pen, readers):
    """The paths from every generation root to a body that reads control:water:* on a map made with
    `pen` (NoiseGraph): a name the map redirects is judged by its target, so a key baked as a number
    reads nothing. Returns (paths, the reader names reached)."""
    graph = NoiseGraph(dump, pen)
    starts = [(ref, (label,)) for label, refs in generation_roots(dump) for ref in refs]
    _, hits = graph.walk(starts, lambda n: (n in readers or n.startswith(WATER_CONTROL)) and n not in graph.eff,
                         lambda v: v in readers)
    return hits, sorted({h[-1] for h in hits})


def write_mgs_full(ctx, label, body):
    d = ctx.out / "mgs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{label}.json"
    p.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return p


def row_water_inert(ctx, mods, sec6, row, cache):
    """D15 (smoke step 2; APPROVALS: the water slider has no effect under Earth presets): statically,
    no tile, entity, decorative or cliff root of any Terra Nauvis preset reaches a body that reads
    control:water:*, and every reader the M1 dump holds is one config.lua's water_slider bakes;
    positive control: the same walk with those keys left out reaches each baked reader (every one is
    live, and nothing else is). In the game, at seed 1000 and 1024 px around the spawn with cliffs
    drawn: the preset's full MGS file at water size 0 (none) and 6 and frequency 6 and 1/6 previews
    byte-identical to the default slider; the same file without the baked keys previews identical
    at the default slider (the bake changes nothing there) and differs at size 0 (the slider bites
    without it); M0's preview changes at size 0 (G6) and differs from Earth's (G5)."""
    cfg = mods.cfg
    d1 = ctx.shared.get("dump_m1")
    if d1 is None:
        row.fails.append("no M1 dump")
        return
    pname, _, _ = first_preset(cfg)
    baked = [w["key"] for w in tnconfig.water_slider(cfg)]
    pen = dict(preset_pen(d1, pname))
    if not pen:
        row.fails.append(f"the M1 dump holds no preset {pname}")
        return
    unbaked = {k: v for k, v in pen.items() if k not in baked}
    ms = [mods.make(f"ea-m1v{i + 1}-{mods.zip_sha[:8]}", [mods.build_zip()]) for i in range(PAR_MAX - 1)]
    for i, m in enumerate(ms):
        mods.prepare(m, f"m1v{i + 1}")
    m0 = ctx.shared["m0"]
    jobs = [("earth-default", ms[0], {"property_expression_names": pen})]
    jobs += [(f"earth-{lb}", ms[0], {"property_expression_names": pen, "autoplace_controls": {"water": c}})
             for lb, c in WATER_VARIANTS]
    jobs += [("unbaked-default", ms[0], {"property_expression_names": unbaked}),
             ("unbaked-none", ms[0], {"property_expression_names": unbaked,
                                      "autoplace_controls": {"water": dict(WATER_VARIANTS[0][1])}}),
             ("m0-default", m0, None), ("m0-none", m0, {"autoplace_controls": {"water": dict(WATER_VARIANTS[0][1])}})]
    key, newest = common_key(ctx, "water_inert", {"ms": [mods.manifest(m) for m in ms], "m0": mods.manifest(m0),
                                                    "dump": ctx.shared.get("dump_m1_sha"), "jobs": [
                                                        (lb, body) for lb, _, body in jobs], "size": WATER_PREVIEW})

    def live():
        lanes = [[] for _ in range(PAR_MAX)]
        dirs = []
        for i, (lb, m, body) in enumerate(jobs):
            # each worker keeps one modset of its own; M0 runs in the last worker
            ln = PAR_MAX - 1 if m == m0 else i % (PAR_MAX - 1)
            mm = ms[ln] if m != m0 else m0
            mgs = write_mgs_full(ctx, f"water-{lb}", body) if body is not None else None
            out = ctx.out / f"water-{lb}"
            lanes[ln].append((None, preview_args(lane_instance(ctx, ln), mm, WATER_PREVIEW, SEED, mgs), out, 900))
            dirs.append(out)
        run_lanes(ctx, [l for l in lanes if l])
        return dirs

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d) + images_rehash(d)
        def image(d):
            try:
                return (derive_preview(d)["images"] or {}).get(f"{SEED}.png")
            except GateError as e:
                fails.append(str(e))
                return None
        h = {lb: image(d) for (lb, _, _), d in zip(jobs, dirs)}
        if any(v is None for v in h.values()):
            fails.append(f"a water-slider preview wrote no {SEED}.png: {[k for k, v in h.items() if v is None]}")
        moved = [lb for lb, _ in WATER_VARIANTS if h.get(f"earth-{lb}") != h.get("earth-default")]
        if moved:
            fails.append(f"the water slider moves the {pname} preview at {moved} (D15: byte-identical at every water "
                         f"slider setting)")
        if h.get("unbaked-default") != h.get("earth-default"):
            fails.append("the baked water keys change the preset's preview at the default slider")
        if h.get("unbaked-none") == h.get("unbaked-default"):
            fails.append("positive control: without the baked keys the preset ignores water size 0 too; the row could "
                         "not see a slider that bites")
        if h.get("m0-none") == h.get("m0-default"):
            fails.append("positive control: M0's preview ignores water size 0 (G6)")
        if h.get("m0-default") == h.get("earth-default"):
            fails.append("the preset's preview equals M0's (G5)")
        # statically: no root of any Terra Nauvis preset reaches a water-slider reader
        readers = water_readers(d1)
        stat = {}
        for pn in earth_presets(cfg):
            p_ = preset_pen(d1, pn)
            paths, reached = walk_water(d1, p_, readers)
            stat[pn] = len(paths)
            if paths:
                fails.append(f"{pn}: {len(paths)} paths reach a water-slider reader, e.g. {' > '.join(paths[0][-5:])} "
                             f"(bake it in config.lua's water_slider)")
        stray = sorted(r for r in readers if r not in baked)
        _, reached_unbaked = walk_water(d1, unbaked, readers)
        if reached_unbaked != sorted(baked):
            fails.append(f"positive control: without the baked keys the walk reaches the readers {reached_unbaked}, "
                         f"want exactly the baked {sorted(baked)}")
        meas = {"hashes": h, "moved": moved, "static_paths": stat, "readers": sorted(readers), "stray_readers": stray,
                "reached_unbaked": reached_unbaked}
        return meas, fails, (f"{pname} at seed {SEED}, {WATER_PREVIEW} px, cliffs drawn: water "
                             f"{[lb for lb, _ in WATER_VARIANTS]} byte-identical to the default slider; without the "
                             f"baked {baked} identical at the default and moved at size 0; M0 moved at size 0; "
                             f"statically 0 paths to the dump's readers {sorted(readers)} (unbaked: {reached_unbaked})")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


ROW_FUNCS = {
    "static": row_static, "plan_main": row_plan_main, "section6": row_section6,
    "frozen": row_frozen, "data_src": row_data_src, "offline_selftests": row_offline_selftests,
    "runner_controls": row_runner_controls, "dumps": row_dumps, "t13_dump_facts": row_t13_dump_facts,
    "isolation_b": row_isolation_b, "ab_withheld": row_ab_withheld, "t13_zero_cost": row_t13_zero_cost,
    "t13_preset_preview": row_t13_preset_preview,
    "t13_scenario": row_t13_scenario, "t15a_rows": row_t15a_rows, "isolation_a": row_isolation_a,
    # europe-coast
    "ec_dump_facts": row_ec_dump_facts, "geo_emit": row_geo_emit, "t1_t2_grids": row_t1_t2_grids,
    "t3_oracle": row_t3_oracle, "t11_pair": row_t11_pair, "t12_twice": row_t12_twice, "t13_routes": row_t13_routes,
    "maptype_route": row_maptype_route, "t16_guard": row_t16_guard, "water_inert": row_water_inert,
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
# A timed pair on the 16 LP proxy and the same pair at 8 LP after it, the diagnostic design section 6.2
# records for every timed pair that runs on the proxy and never gates (the walker, the Map type route).
PROXY_MASKS = (0xFFFF, 0xFF)
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
    file beside the run: our game pids, foreign game pids, the most game processes seen, the wholly
    suspended game processes seen (parked: they ran nothing, so they are neither foreign nor
    counted), the affinity reads, the CPU load before the run, the tasklist rows right after it and
    the game's peak working set in MB (T15-h; read before the caller closes the monitor's process
    handles)."""
    peak = mon.peak_mb() if mon is not None and hasattr(mon, "peak_mb") else None
    rec = {"mask": mask, "load_pre": load_pre, "tasklist_after": list(after or []),
           "root": getattr(mon, "root", None), "ours": sorted(getattr(mon, "ours", {}) or {}),
           "foreign": sorted(getattr(mon, "foreign", set()) or set()), "max_games": getattr(mon, "max_games", None),
           "parked": sorted(getattr(mon, "parked", set()) or set()),
           "polls": getattr(mon, "polls", None), "masks": [list(m) for m in (getattr(mon, "masks", []) or [])],
           "peak_mb": peak}
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


def derive_t15b(dirs, limits, reps, pair="m0_self", label="M0t/M0t", census_m0=None):
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
    want = census_m0 if census_m0 is not None else (baseline_record().get("t15b_block") or {}).get("census_m0") or {}
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


def support_steps(vb, t0=WALK["T0"]):
    """BasicTilesSupportCompute per walker step in ms, in time order from the first request (tick
    t0): each non-zero tick is one column's support build, the first the column into empty land."""
    col = vb.get(PERF15_KEEP) or []
    return [v / 1e6 for tk, v in zip(vb.get("tick") or [], col) if tk >= t0 and v]


def step_summary(steps):
    """The first column's support build, the median of the later ones and the longest (ms)."""
    later = sorted(steps[1:])
    return {"first_ms": round(steps[0], 3) if steps else None,
            "later_ms": round(later[len(later) // 2], 3) if later else None,
            "max_ms": round(max(steps), 3) if steps else None}


def derive_walker(d, mask=0xFFFF):
    """The benchmark-mode walker from its raw outputs: G1, the persisted monitor record (no foreign
    game process, none right after), and with a mask the affinity verdict recomputed from the
    watcher's records (never the run-time affinity.json); then the --benchmark-verbose columns, the
    first and later columns' support build, and the peak working set the monitor record holds (None
    in a record written before it kept one)."""
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
            "columns": {c: {k: round(v, 5) for k, v in st["columns"][c].items()} for c in ["wholeUpdate", "scriptUpdate"] + mg},
            "support_steps": step_summary(support_steps(vb)), "peak_mb": (mon or {}).get("peak_mb")}
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
        cmd = [sys.executable, str(HERE / "game_selftest.py"), "--out-root", str(copy), "--replay"]
        cmd += ["--only", only] if only else []
        cp = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=900)
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
    try:
        rel = os.path.relpath(d, tnguard.ws_root())
    except ValueError:
        rel = str(d)
    refused = []
    for args in (["--out-root", str(d)], ["--out-root", rel]):
        cp = subprocess.run([sys.executable, str(HERE / "game_selftest.py")] + args + ["--replay", "--only", "t1"],
                            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=120)
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
        code, text, _ = ctx.popen_text([sys.executable, HERE / "game_selftest.py", "--out-root", out], 1800)
        (ctx.out / "gst.txt").write_text(text, encoding="utf-8")
        # the child stops itself on a breach; the runner then stops every further game run too
        for rd in [out] + sorted({p.parent for p in out.rglob("run.json")}) if out.is_dir() else [out]:
            why = tnguard.run_breach(rd)
            if why:
                raise ctx.fatal(f"game_selftest.py run {rd}: {why}")
        if "stops every further game run" in text:
            raise ctx.fatal("game_selftest.py stopped every further game run: " +
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
    if any(s["id"] == "europe-coast" for s in registry_upto(ctx.slice)) and ctx.slice != "toolchain":
        ec_suite_checks(ctx, mods, sec6, checks, d, limits, ctl, timing, sig)
    if any(s["id"] == "spawn-cities" for s in registry_upto(ctx.slice)):
        sc_suite_checks(ctx, mods, sec6, checks, d, limits, ctl, timing, sig)
    return checks


# -- europe-coast's suite checks

# Phase 4 placed its timed rows relative to London at scale 6 (BENCHMARKS.md:114-123; London's pixel
# centre at world (0, 0)): tile offsets from London's pixel-centre tile. This milestone holds each fixed in
# geo coordinates and places it through the save's spawn offset (fit review; tq1-gen-block exists for
# it): the near block (TQ1b's, Switzerland), the exploring band (eastern Poland and Belarus) and the
# walker. London's pixel comes from the oracle (EarthMaps' city file).
P4_ANCHOR = "city:London"
P4_SCALE = 6
P4_BLOCK_CENTRE = (2048 + 256, 1024 + 256)   # chunks 64..79 x 32..47
P4_WARM = (-2048, -1536)                     # the warm-up chunk (-64, -48)
P4_BAND = (188 * 32, -14 * 32)               # rtexplore cx0 188, cy -14 (chunks)
P4_WALK = (2048, -2048)                      # walk x0, y0 (tiles)
BLOCK_LAND = (0.50, 0.95)                    # test notes 5.4: a coast block of 50 to 95 percent land
START_AREA_CHUNKS = 7                        # --create generates chunks -7..6 around the spawn (measured)
T15B_SCALES = (6, 1)
T15B_MASKS = {6: ("MASK16", "MASK8", "MASK24"), 1: ("MASK16", "MASK8")}
RT_REPS = 3
# TQ1b's chord between two timed tent sizes (8 and 24 LP only) and the whole composite (TQ3, Phase 4):
# the build records its error against them (design experiment 1).
CHORD = {"terms": (4096, 16384), "lp8": (0.993, 1.641), "lp24": (1.018, 1.488)}
COMPOSITE = {"tq3_16lp": 1.045, "phase4_8lp": 1.26, "phase4_24lp": 1.03}
PAIR_LIMITS["m1_m0"] = {0xFFFF: ["P1"], MASK24: ["P3"]}
# T15-f (test notes 5.5; design section 6.2: recorded, never gated): preview time by Phase 4's method
# (BENCHMARKS.md section 3) at 1024 px, and at 256 px, the plan's second size, centred on the T15b
# block, seed 1000, --threads 8, 7 valid repetitions per config interleaved in one group, read from
# the "Map preview generation time" line, which excludes startup and noise compilation.
PREVIEW_TIME = {"sizes": (1024, 256), "reps": 7, "threads": 8}
PT_DIR_RE = re.compile(r"r(\d{3})-(m1|m0)-(\d+)")
PT_LINE_RE = re.compile(r"Map preview generation time: ([\d.]+) seconds")


def phase4_tile(cfg, mref, scale, dx, dy):
    """The world tile at `scale` of the geo point that sat (dx, dy) tiles from London's pixel-centre
    tile in Phase 4 at scale 6, through the runner world's spawn offset at that scale (europe-coast:
    the city offset baked as 0; spawn-cities: the default spawn city at SEED, so the timed blocks keep
    their geo position through the shift)."""
    import oracle
    O = oracle.load_oracle(mref.key, TESTS / "oracle")
    lon = next(p for p in O["places"] if p["id"] == P4_ANCHOR)
    lx, ly = (int(v) for v in oracle.place_tile(mref, lon, str(P4_SCALE)))
    u = (lx + dx + 0.5) / P4_SCALE + mref.wr
    v = (ly + dy + 0.5) / P4_SCALE + mref.hr
    ox, oy = runner_offset(cfg, mref.key, scale)
    return int(math.floor(scale * (u - mref.wr))) - ox, int(math.floor(scale * (v - mref.hr))) - oy


def london_start_pen(ctx, cfg, mref, pname, g):
    """The dumped preset's property_expression_names at Phase 4's London start (scale 6): the city
    offset names hold London's pixel-centre GEO tile, the value the chain adds to x and y (gx = x +
    cx), so London sits at world (0, 0). phase4_tile gives a world tile of the runner's world, so its
    spawn offset is added back. On a version with a spawn record the city number is London's too, so
    the spawn lake and the starting-ore bias are London's, and the fold for that number must give
    the same tile (a cross-check of the two routes); a version that bakes numbers takes the tile."""
    lx, ly = phase4_tile(cfg, mref, 6, 0, 0)
    ox, oy = runner_offset(cfg, mref.key, 6)
    geo = (lx + ox, ly + oy)
    pen = dict(preset_pen(ctx.shared["dump_m1"], pname))
    if not pen:
        raise GateError(f"the M1 dump holds no property_expression_names for the preset {pname}")
    pen[g["cx"]], pen[g["cy"]] = geo
    if g.get("spawn"):
        values = sc_values(cfg, g)
        hits = [v for v in values[1:] if runner_offset(cfg, mref.key, 6, city=v) == geo]
        if len(hits) != 1:
            raise GateError(f"Phase 4's London geo tile {geo} at scale 6 is the city fold's tile of {hits or 'no city'} "
                            f"(want exactly one city)")
        pen[g["city"]] = values.index(hits[0])
    return pen


def europe_block(cfg, mref, scale):
    """(tq1-gen-block spec "bx:by:wx:wy", block corner chunk, reference land fraction of its tiles).
    The block's north-west corner is Phase 4's, fixed in geo coordinates: at scale 1 a block centred
    there would reach into the start area the game generates at creation (chunks -7..6 around the
    spawn), and a timed repetition counts only when the block was never generated before it."""
    import numpy as np
    cx, cy = phase4_tile(cfg, mref, P4_SCALE, P4_BLOCK_CENTRE[0] - 256, P4_BLOCK_CENTRE[1] - 256)
    bx, by = cx // 32, cy // 32
    # world tiles are geo tiles minus the runner world's spawn offset at each scale (spawn-cities)
    sox, soy = runner_offset(cfg, mref.key, scale)
    if scale != P4_SCALE:
        # the same geo extent at another scale: the chunk-aligned block holding the scale 6 block's
        # pixels, clear of the start area, closest to centred on them
        o6x, o6y = runner_offset(cfg, mref.key, P4_SCALE)
        gx0, gy0 = bx * 32 + o6x, by * 32 + o6y
        c0, c1 = gx0 // P4_SCALE + mref.wr, (gx0 + 511) // P4_SCALE + mref.wr
        r0, r1 = gy0 // P4_SCALE + mref.hr, (gy0 + 511) // P4_SCALE + mref.hr
        tx0, tx1 = (c0 - mref.wr) * scale - sox, (c1 - mref.wr + 1) * scale - 1 - sox
        ty0, ty1 = (r0 - mref.hr) * scale - soy, (r1 - mref.hr + 1) * scale - 1 - soy
        sa = START_AREA_CHUNKS * 32
        best = None
        for qx in range((tx1 - 511) // 32 - 1, tx0 // 32 + 2):
            for qy in range((ty1 - 511) // 32 - 1, ty0 // 32 + 2):
                X, Y = qx * 32, qy * 32
                if not (X <= tx0 and X + 511 >= tx1 and Y <= ty0 and Y + 511 >= ty1):
                    continue
                if not (X + 511 < -sa or X >= sa or Y + 511 < -sa or Y >= sa):
                    continue
                d2 = (X + 256 - (tx0 + tx1) / 2) ** 2 + (Y + 256 - (ty0 + ty1) / 2) ** 2
                if best is None or (d2, qx, qy) < best:
                    best = (d2, qx, qy)
        if best is None:
            raise GateError(f"no 16 x 16 chunk block at scale {scale} holds the T15b block's geo extent clear of the "
                            f"start area")
        bx, by = best[1], best[2]
    wx, wy = (v // 32 for v in phase4_tile(cfg, mref, scale, *P4_WARM))
    tx = np.arange(bx * 32, bx * 32 + 512)
    ty = np.arange(by * 32, by * 32 + 512)
    cols = np.floor_divide(tx + sox, scale) + mref.wr
    rows = np.floor_divide(ty + soy, scale) + mref.hr
    inside = (cols >= 0) & (cols < mref.W)
    rin = (rows >= 0) & (rows < mref.H)
    land = mref.land[np.ix_(rows[rin], cols[inside])]
    frac = float(land.sum()) / (512 * 512)
    return f"{bx}:{by}:{wx}:{wy}", (bx, by), round(frac, 4)


def europe_positions(cfg, mref):
    """Every timed position of the milestone, from Phase 4's through London (scale 6 unless named)."""
    spec6, corner6, land6 = europe_block(cfg, mref, 6)
    spec1, corner1, land1 = europe_block(cfg, mref, 1)
    bx, by = phase4_tile(cfg, mref, 6, *P4_BAND)
    wx, wy = phase4_tile(cfg, mref, 6, *P4_WALK)
    explore = dict(EXPLORE, cx0=bx // 32, cy=by // 32)
    walk = dict(WALK, x0=wx, y0=wy)
    return {"block": {6: spec6, 1: spec1}, "block_land": {6: land6, 1: land1}, "save_block": corner6,
            "explore": explore, "walk": walk}


def earth_driver_modsets(ctx, mods):
    """M1t (M1 plus TQ1's timer) and M1d (M1 plus TQ2's driver), named by the Earth zip."""
    return (mods.with_mods("m1t", [HERE / "mods" / "tq1-gen"]),
            mods.with_mods("m1d", [HERE / "mods" / "tq2-driver"]))


def make_save_mgs(ctx, mods, modset, setting, spec, label, mgs=None):
    """make_save with the world made from a full MGS file (the preset route's equal, T13), so the
    Earth configs' saves carry the preset's keys; mgs None makes a default world (M0)."""
    mods.prepare(modset, label)
    res = ctx.fh_plain(["settings", modset, "--set", f"runtime-global.{setting}={spec}"])
    if not res.startswith("RESULT ok"):
        raise GateError(f"fh.py settings {modset}: {res}")
    r = ctx.fh(scenario_args(ctx.instance, modset, 1, SEED, mgs), ctx.out / f"save-{label}")
    if g1(r.out):
        raise GateError(f"save creation for {label} failed: {g1(r.out)[:2]}")
    return r.out / "scenario.zip"


def pair_batch(ctx, configs, reps, masks, label, deadline):
    """One quiet-window group of configs a and b [(modset, save)], interleaved rounds rotated by one per
    mask (test notes 5.2): t15b_batch's protocol for an Earth pair."""
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
            ms, save = configs[cfg]
            rec = timed_rep(ctx, ms, save, out_root / f"r{idx:03d}-{cfg}-{mask:x}", mask, deadline, log,
                            expect_census=census.get(cfg))
            if rec["valid"]:
                c = rec.get("census") or {}
                census.setdefault(cfg, {k: c.get(k) for k in CENSUS_KEYS})
                valid[(cfg, mask)].append(rec["force_ms"])
            if idx > 6 * reps * len(order):
                raise GateError("too many discarded repetitions")
        rnd += 1
    return out_root


def p1_limits(sec6, slice_id, map_key="europe", pending=None):
    """The 6.2 limits a timed pair meets for `slice_id`: P1's relative rule reads main's recorded ratio
    plus the time allocation of the pending milestones (pending_slices: a group's gate meets its milestones'
    allocations together); a 'first' allocation records the first ratio and only the absolute bar
    applies (6.3). An added allocation reads the landed ratio from the reference refs' suite
    manifests (landed_p1_ratio) and bounds the pair at min(the absolute bar, (that ratio plus the
    allocation) x 1.10), failing closed when no ref recorded one."""
    lim = dict(sec6["limits"])
    if "P1" in lim:
        pend = pending_slices(slice_id) if pending is None else list(pending)
        alloc = batch_alloc_for(sec6, pend, "time", "M1", map_key)
        rec = dict(lim["P1"])
        if alloc["kind"] in ("first", "cap"):
            rec["limit"] = {"max": rec["limit"]["max"]}
        elif alloc["kind"] == "add":
            base = landed_p1_ratio(slice_id, map_key)
            if base is None:
                raise GateError(f"P1's relative rule for {pend} needs the landed M1t/M0t ratio, which no reference "
                                f"ref's suite manifest records (fail closed)")
            rel = round((base + alloc["value"]) * P1_RELATIVE, 4)
            rec["limit"] = {"max": min(rec["limit"]["max"], rel)}
        else:
            raise GateError(f"P1 has no rule for a {alloc['kind']} time allocation of {pend}")
        lim["P1"] = rec
    return lim


def derive_t15b_europe(dirs, limits, reps, mask_names, census_want=None):
    """The Earth pairs, one group per scale: derive_t15b on each (P1 at 16 LP, P3 at 24 LP, 8 LP a
    diagnostic), the M0 config's census against tests/baselines' census for that block, and the
    chord's and the composite's errors recorded."""
    fails, meas = [], {}
    for scale, d in dirs.items():
        want = (census_want or {}).get(str(scale))
        if not want:
            fails.append(f"scale {scale}: tests/baselines holds no M0 census of this block: run 'earth_test.py baseline'")
        m, f, _ = derive_t15b([d], limits, reps, pair="m1_m0", label=f"M1t/M0t scale {scale}", census_m0=want or {})
        fails += [f"scale {scale}: {x}" for x in f]
        meas[f"scale_{scale}"] = m
    s6 = meas.get("scale_6", {})
    for lp, mask in (("lp8", 0xFF), ("lp24", MASK24)):
        r = (s6.get(f"{mask:#x}") or {}).get("ratio")
        (t0, t1_), (y0, y1) = CHORD["terms"], CHORD[lp]
        chord = y0 + (8192 - t0) / (t1_ - t0) * (y1 - y0)
        meas[f"chord_{lp}"] = {"chord_at_8192": round(chord, 4), "measured": r,
                              "error": round(r - chord, 4) if r is not None else None}
    meas["composite"] = dict(COMPOSITE, measured_16lp=(s6.get(f"{0xFFFF:#x}") or {}).get("ratio"))
    return meas, fails, "; ".join(f"scale {s}: " + ", ".join(f"{k} {v.get('ratio')}" for k, v in m.items()
                                                            if isinstance(v, dict) and "ratio" in v)
                                  for s, m in ((k[6:], v) for k, v in meas.items() if k.startswith("scale_")))


def live_t15b_m1(ctx, mods, sec6):
    """The gate's live timed sample of europe-coast (rule 3): one gate-sized group of M1t against M0t
    on the map's block at scale 6 at 16 LP (P1), with rule 5's extra group when the ratio sits within
    0.03 of the bar and the group fits the budget, else fail closed. Returns (dirs, meas, fails,
    detail)."""
    import earthgeo as eg
    cfg = mods.cfg
    _, mk, _ = first_preset(cfg)
    pos = europe_positions(cfg, eg.MapRef(mk))
    m1t, _ = earth_driver_modsets(ctx, mods)
    m0t, _, _ = driver_modsets(ctx, mods)
    lim = p1_limits(sec6, ctx.slice) if isinstance(sec6, dict) else {}
    census = ((baseline_record().get("t15b_europe") or {}).get("census_m0") or {}).get("6") or {}
    sa = make_save_mgs(ctx, mods, m1t, "tq1-gen-block", pos["block"][6], "live-m1t", preset_mgs(ctx, cfg, 6))
    sb = make_save_mgs(ctx, mods, m0t, "tq1-gen-block", pos["block"][6], "live-m0t")
    cfgs = {"a": (m1t, sa), "b": (m0t, sb)}
    t0 = time.time()
    dirs = [pair_batch(ctx, cfgs, T15B["reps_gate"], [ctx.perf.MASK16], "live-t15b-m1", ctx.deadline)]
    took = time.time() - t0
    meas, f, detail = derive_t15b(dirs, lim, T15B["reps_gate"], pair="m1_m0", label="M1t/M0t", census_m0=census)
    rec = meas.get(f"{ctx.perf.MASK16:#x}") or {}
    if rec.get("undecided"):
        fits, need = extra_batch_fits(took, 2 * T15B["reps_gate"], 2 * T15B["reps_extra"], time.time(), ctx.deadline)
        if fits:
            dirs.append(pair_batch(ctx, cfgs, T15B["reps_extra"], [ctx.perf.MASK16], "live-t15b-m1-x", ctx.deadline))
            meas, f, detail = derive_t15b(dirs, lim, T15B["reps_gate"], pair="m1_m0", label="M1t/M0t",
                                          census_m0=census)
        else:
            f = [f"P1: M1t/M0t at 16 LP is {rec['ratio']}, within {BORDERLINE} of its bound {rec['borderline']:g}, and "
                 f"rule 5's batch needs about {need:.0f} s, more than the gate has left: fail closed"]
    return dirs, meas, f, detail


def run_peak_mb(d):
    """The peak working set (MB) the monitor record beside a run holds, or None."""
    f = Path(d).parent / f"{Path(d).name}-monitor.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("peak_mb") if f.exists() else None
    except ValueError:
        return None


def derive_rt_pair(dirs, limits):
    """P4 to P6 from interleaved real-time runs of M1 and M0 (one group): each M1 run at most P4's ticks
    over 20 ms and P6's longest interval; the median M1 p99 over the median M0 p99 at most P5. The
    peak working set while exploring at 24 LP (T15-h) is recorded per run from the monitor record
    beside it, with the median M1 minus the median M0; a run without one fails (incomplete evidence)."""
    import perf
    fails, meas = [], {"m1": [], "m0": []}
    peaks = {"m1": [], "m0": []}
    for cfg, ds in dirs.items():
        for d in ds:
            m, f, _ = derive_rt([d])
            fails += [f"{cfg} {Path(d).name}: {x}" for x in f]
            meas[cfg].append(m)
            pk = run_peak_mb(d)
            if pk is None:
                fails.append(f"{cfg} {Path(d).name}: no peak working set beside the run ({Path(d).name}-monitor.json)")
            peaks[cfg].append(pk)
    if not meas["m1"] or not meas["m0"]:
        return meas, fails + ["no real-time runs"], ""
    if all(p is not None for v in peaks.values() for p in v):
        p1, p0 = perf.median(peaks["m1"]), perf.median(peaks["m0"])
        meas["peak_mb"] = {"m1": peaks["m1"], "m0": peaks["m0"], "m1_median": p1, "m0_median": p0,
                           "m1_minus_m0": round(p1 - p0, 1)}
    p4 = (limits.get("P4") or {}).get("limit", {}).get("max")
    p5 = (limits.get("P5") or {}).get("limit", {}).get("max")
    p6 = (limits.get("P6") or {}).get("limit", {}).get("M1_ms")
    over = [m.get("over_20ms") for m in meas["m1"]]
    longest = [m.get("max") for m in meas["m1"]]
    ratio = perf.median([m["p99"] for m in meas["m1"]]) / perf.median([m["p99"] for m in meas["m0"]])
    meas["p5_ratio"] = round(ratio, 4)
    if p4 is None or p5 is None or p6 is None:
        fails.append(f"P4 to P6 limits unreadable: {p4}, {p5}, {p6}")
    else:
        if any(o is None or o > p4 for o in over):
            fails.append(f"P4: M1 ticks over 20 ms {over}, at most {p4:g} per window")
        if ratio > p5:
            fails.append(f"P5: p99 interval M1/M0 {ratio:.4f}, at most {p5:g}")
        if any(x is None or x > p6 for x in longest):
            fails.append(f"P6: M1 longest interval {longest} ms, at most {p6:g}")
    pk = meas.get("peak_mb") or {}
    return meas, fails, (f"real time at 60 UPS: M1 ticks over 20 ms {over} (P4), p99 ratio {ratio:.4f} (P5), "
                         f"longest {longest} ms (P6); M0 {[m.get('over_20ms') for m in meas['m0']]} over 20 ms; peak "
                         f"working set {pk.get('m1_median')} against {pk.get('m0_median')} MB (recorded)")


def walker_pair_rows(a, b):
    """The recorded benchmark-mode rows of one M1 and M0 walker pair (design section 6.2): Earth
    scriptUpdate per tick over M0's, wholeUpdate mean and p99 against M0's, the mapGenerator sum,
    BasicTilesSupportCompute per column and for the first column, and the peak working set while
    exploring, M1 minus M0 (T15-h)."""
    w1, w0 = a["columns"]["wholeUpdate"], b["columns"]["wholeUpdate"]
    p1, p0 = a.get("peak_mb"), b.get("peak_mb")
    su = a["columns"]["scriptUpdate"]["mean"] - b["columns"]["scriptUpdate"]["mean"]
    return {"scriptUpdate_delta_ms": round(su, 5),
            "wholeUpdate": {"mean_ratio": round(w1["mean"] / w0["mean"], 4), "p99_m1": w1["p99"], "p99_m0": w0["p99"]},
            "basic_tiles_support": {k: v.get(PERF15_KEEP) for k, v in (("m1", a["columns"]), ("m0", b["columns"]))},
            "basic_tiles_support_steps": {"m1": a.get("support_steps"), "m0": b.get("support_steps")},
            "mapGenerator_sum_ms": {k: round(sum(v["sum_ms"] for c, v in m["columns"].items()
                                                if c.startswith("mapGenerator") and c != "mapGenerator"), 3)
                                    for k, m in (("m1", a), ("m0", b))},
            "peak_mb": {"m1": p1, "m0": p0,
                        "m1_minus_m0": round(p1 - p0, 1) if p1 is not None and p0 is not None else None}}


def derive_walker_pair(dirs, limits, masks=PROXY_MASKS):
    """P7: Earth scriptUpdate while exploring in benchmark mode, M1 minus M0, per tick, on the 16 LP
    pair (dirs[0] M1, dirs[1] M0), with its recorded rows (walker_pair_rows); then each further
    mask's pair in order (the 8 LP diagnostic: dirs[2] and dirs[3]) with the same rows, recorded and
    never gated. Every run is re-derived at its own mask (G1, the monitor record, the affinity
    verdict from the watcher's records), and every pair must carry both peak working sets."""
    if len(dirs) != 2 * len(masks):
        return {}, [f"{len(dirs)} walker runs, want {2 * len(masks)}: M1 and M0 at each of "
                    f"{[f'{m:#x}' for m in masks]}"], ""
    fails, rows, raw = [], {}, {}
    for i, mask in enumerate(masks):
        a, fa, _ = derive_walker(dirs[2 * i], mask)
        b, fb, _ = derive_walker(dirs[2 * i + 1], mask)
        fails += [f"M1 at {mask:#x}: {x}" for x in fa] + [f"M0 at {mask:#x}: {x}" for x in fb]
        if fa or fb:
            continue
        rows[mask], raw[mask] = walker_pair_rows(a, b), (a, b)
        if rows[mask]["peak_mb"]["m1_minus_m0"] is None:
            fails.append(f"mask {mask:#x}: a monitor record holds no peak working set (M1 "
                         f"{rows[mask]['peak_mb']['m1']}, M0 {rows[mask]['peak_mb']['m0']} MB)")
    if fails:
        return {}, fails, ""
    a, b = raw[masks[0]]
    d = a["columns"]["scriptUpdate"]["mean"] - b["columns"]["scriptUpdate"]["mean"]
    lim = (limits.get("P7") or {}).get("limit", {}).get("delta_ms")
    if lim is None:
        fails.append("P7's limit is unreadable")
    elif d > lim:
        fails.append(f"P7: Earth scriptUpdate {d:+.4f} ms per tick over M0's, at most +{lim:g}")
    meas = dict(rows[masks[0]], mask=f"{masks[0]:#x}")
    meas["diagnostic"] = {f"{m:#x}": rows[m] for m in masks[1:]}
    diag = "; ".join(f"{m:#x} diagnostic: scriptUpdate {rows[m]['scriptUpdate_delta_ms']:+.4f} ms, wholeUpdate mean "
                     f"{rows[m]['wholeUpdate']['mean_ratio']}x, peak {rows[m]['peak_mb']['m1_minus_m0']:+} MB"
                     for m in masks[1:])
    return meas, fails, (f"benchmark mode at {masks[0]:#x}: scriptUpdate {d:+.4f} ms per tick over M0 (P7), "
                         f"wholeUpdate mean {meas['wholeUpdate']['mean_ratio']}x M0's, first column's support build "
                         f"{meas['basic_tiles_support_steps']['m1']['first_ms']} ms, peak working set "
                         f"{meas['peak_mb']['m1']} against {meas['peak_mb']['m0']} MB (recorded)"
                         + (f"; {diag}" if diag else ""))


def derive_save_pair(dirs, limits):
    """P19: the block's increment between the two server saves, M1 against M0; the whole save's
    ratio recorded."""
    a, fa, _ = derive_save([dirs[0]])
    b, fb, _ = derive_save([dirs[1]])
    fails = [f"M1: {x}" for x in fa] + [f"M0: {x}" for x in fb]
    if fails or not b.get("increment"):
        return {"m1": a, "m0": b}, fails or ["M0's save increment is 0"], ""
    r = a["increment"] / b["increment"]
    whole = a["post"] / b["post"] if b.get("post") else None
    lim = (limits.get("P19") or {}).get("limit", {}).get("max")
    if lim is None:
        fails.append("P19's limit is unreadable")
    elif r > lim:
        fails.append(f"P19: the block's save increment {r:.4f}x M0's, at most {lim:g}")
    return {"m1": a, "m0": b, "increment_ratio": round(r, 4), "whole_save_ratio": round(whole, 4) if whole else None}, \
        fails, f"server save: block increment {r:.4f}x M0's (P19), whole save {whole and round(whole, 4)}x (recorded)"


def preview_time_from_raw(run):
    """One preview-time repetition re-derived from its run directory and the monitor record beside it
    (rule 2): G1 and G3, exactly one image that re-hashes (G4), exactly one "Map preview generation
    time" line, no other game process during the run or right after it, and a quiet machine before
    it (TQ1's quiet window)."""
    import perf
    run = Path(run)
    reasons = list(g1(run)) + g3(run) + images_rehash(run)
    images = (load_run_json(run) or {}).get("images") or {}
    if len(images) != 1:
        reasons.append(f"{len(images)} images, want 1 (G4)")
    found = PT_LINE_RE.findall(perf.read(run / "stdout.txt"))
    if len(found) != 1:
        reasons.append(f"{len(found)} 'Map preview generation time' lines, want 1")
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
    return {"valid": not reasons, "reasons": reasons, "seconds": float(found[0]) if len(found) == 1 else None,
            "image": next(iter(images.values())) if len(images) == 1 else None}


def derive_preview_time(dirs, sizes=PREVIEW_TIME["sizes"], reps=PREVIEW_TIME["reps"]):
    """T15-f from the group's raw outputs alone (rule 2): every repetition directory
    (r<NNN>-<config>-<size>, numbered without a gap, so none can be dropped) re-derived by
    preview_time_from_raw, the runner's reps.jsonl only cross-checked against that; per size, the
    configured valid repetitions per config, one image per config across its valid repetitions and
    M1's unlike M0's (G5: the preset applied), and the ratio of the medians, recorded, never gated."""
    import perf
    if len(dirs) != 1:
        return {}, [f"{len(dirs)} preview-time batches, want 1"], ""
    root = Path(dirs[0])
    fails = []
    runs = sorted((d for d in root.iterdir() if d.is_dir() and PT_DIR_RE.fullmatch(d.name)),
                  key=lambda d: int(PT_DIR_RE.fullmatch(d.name).group(1))) if root.is_dir() else []
    idx = [int(PT_DIR_RE.fullmatch(d.name).group(1)) for d in runs]
    if not runs or idx != list(range(1, len(idx) + 1)):
        fails.append(f"{root.name}: repetition directories {idx[:3]}...{idx[-3:]} are not numbered 1..{len(idx)} "
                     f"without a gap (a dropped repetition)")
    logged = {}
    rj = root / "reps.jsonl"
    for line in (rj.read_text(encoding="utf-8").splitlines() if rj.exists() else []):
        if line.strip():
            r = json.loads(line)
            logged[Path(r.get("out", "")).name] = r
    if set(logged) != {d.name for d in runs}:
        fails.append(f"{root.name}: reps.jsonl lists {len(logged)} repetitions, the batch holds {len(runs)} repetition "
                     f"directories")
    secs, images = {}, {}
    for run in runs:
        m = PT_DIR_RE.fullmatch(run.name)
        key = (m.group(2), int(m.group(3)))
        raw = preview_time_from_raw(run)
        stored = logged.get(run.name)
        if stored is not None and bool(stored.get("valid")) != raw["valid"]:
            fails.append(f"{run.name}: reps.jsonl records valid={bool(stored.get('valid'))}, its raw outputs say "
                         f"valid={raw['valid']} {raw['reasons'][:2]}")
        if raw["valid"]:
            secs.setdefault(key, []).append(raw["seconds"])
            images.setdefault(key, set()).add(raw["image"])
    meas = {}
    for size in sizes:
        a, b = secs.get(("m1", size), []), secs.get(("m0", size), [])
        ia, ib = images.get(("m1", size), set()), images.get(("m0", size), set())
        if len(a) < reps or len(b) < reps:
            fails.append(f"{size} px: {len(a)} and {len(b)} valid repetitions, want {reps} each")
            continue
        if len(ia) != 1 or len(ib) != 1:
            fails.append(f"{size} px: the valid repetitions drew {len(ia)} M1 and {len(ib)} M0 images, want one each")
        elif ia == ib:
            fails.append(f"{size} px: M1's preview equals M0's (G5: the preset did not apply)")
        ma, mb = perf.median(a), perf.median(b)
        if not mb or mb <= 0:
            fails.append(f"{size} px: M0's median preview time is {mb} s")
            continue
        meas[f"px_{size}"] = {"m1_median_s": ma, "m0_median_s": mb, "ratio": round(ma / mb, 3),
                              "m1_spread_s": perf.spread(a), "m0_spread_s": perf.spread(b), "reps": [len(a), len(b)]}
    return meas, fails, "; ".join(
        f"{k[3:]} px: M1 {v['m1_median_s']} s against M0 {v['m0_median_s']} s, {v['ratio']}x (recorded, not gated; "
        f"Phase 4's composite: 5.09x at 1024 px, 6.27x at 256 px)" for k, v in meas.items())


def save_zip_parts(path):
    """{entry: bytes} of the save's map data files (level-init.dat and level.dat and their parts)."""
    import zipfile
    out = {}
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            base = i.filename.rsplit("/", 1)[-1]
            if base.startswith(("level-init.dat", "level.dat")):
                out[base] = out.get(base, 0) + i.compress_size
    return out


def ensure_dumps(ctx, mods):
    """The M0 and M1 dumps (row dumps), when a command reaches the suite checks without the FG rows
    (suite --only)."""
    if ctx.shared.get("dump_m1") is None:
        r = Row("dumps")
        row_dumps(ctx, mods, None, r, None)
        if r.fails:
            raise GateError(f"the dumps the suite checks read failed: {r.fails[:2]}")


T18_MOVED_PX = 32                         # T18: the test build's move of the city-offset fallback, tiles
V1_DIR = SUITES / "europe-coast" / "v1"   # the committed contact sheets (design section 5), outside the keyed tests digest
SMOKE_PREVIEW = 1024                      # px: smoke step 2's CLI preview of the preset at seed 1000


def rel_repo(p):
    try:
        return Path(p).resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(p)


def commit_v1(ctx, out):
    """Copy a V1 run's contact sheets into the repo (V1_DIR), each with its JSON whose paths are made
    workspace-relative, after clearing the sheets an earlier run left there: design section 5 keeps
    the contact sheets in the repo, so a checkout without the workspace's previews still holds them.
    tests/baselines/suites/ is outside every suite key, so the copy re-keys nothing."""
    V1_DIR.mkdir(parents=True, exist_ok=True)
    for old in list(V1_DIR.glob("*.png")) + list(V1_DIR.glob("*.json")):
        old.unlink()
    for png in sorted(Path(out).glob("*.png")):
        shutil.copyfile(png, V1_DIR / png.name)
        meta = png.with_suffix(".json")
        if meta.is_file():
            rec = json.loads(meta.read_text(encoding="utf-8"))
            for k in ("preview", "sheet"):
                if isinstance(rec.get(k), list):
                    rec[k] = [rel_ws(ctx, x) for x in rec[k]]
                elif rec.get(k):
                    rec[k] = rel_ws(ctx, rec[k])
            (V1_DIR / meta.name).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")


def ec_suite_checks(ctx, mods, sec6, checks, d, limits, ctl, timing, sig):
    """europe-coast's suite checks, added to suite_checks' table."""
    import earthgeo as eg
    ensure_dumps(ctx, mods)
    cfg = mods.cfg
    pname, mk, g = first_preset(cfg)
    esig_cache = {}

    def esig(modset, label):
        """The compiled programs' --verbose signature with the Earth preset applied (rule 2)."""
        if label not in esig_cache:
            esig_cache[label] = program_signature(ctx, mods, modset, f"e-{label}", preset=pname)
        return esig_cache[label]
    mref = eg.MapRef(mk)
    lim = p1_limits(sec6, ctx.slice) if isinstance(sec6, dict) else {}
    dump_sha = ctx.shared.get("dump_m1_sha")

    def base_key(name, extra=None):
        return key_of({"check": name, "mod": d["mod"], "tools": d["tools"], "test_mods": d["test_mods"],
                       "data_src": d["data_src"], "tests": d["tests"], "fh": d["fh"], "build": GAME_BUILD,
                       "extra": extra or {}})

    # T1 (SS; scales 1, 3, 6; design experiment 2): from preview tiles, never thresholded expressions
    t1_scales = (1, 3, 6)
    plans = {s: preview_plan(mref, s) for s in t1_scales}

    def t1_run(deadline):
        ms = [mods.make(f"ea-m1v{i + 1}-{mods.zip_sha[:8]}", [mods.build_zip()]) for i in range(PAR_MAX)]
        for i, m in enumerate(ms):
            mods.prepare(m, f"m1v{i + 1}")
        jobs = []
        for s in t1_scales:
            size, offs = plans[s]
            mgs = preset_mgs(ctx, cfg, s, cliffs=False, coast_only=True)
            for j, off in enumerate(offs):
                jobs.append((None, None, ctx.out / f"t1pv-s{s}-{j:02d}", (size, mgs, off)))
        lanes = [[] for _ in range(PAR_MAX)]
        for i, (_, _, out, (size, mgs, off)) in enumerate(jobs):
            ln = i % PAR_MAX
            lanes[ln].append((None, preview_args(lane_instance(ctx, ln), ms[ln], size, SEED, mgs, off), out, 900))
        run_lanes(ctx, lanes)
        return [j[2] for j in jobs]

    def t1_derive(dirs):
        fails, meas = [], {}
        for x in dirs:
            fails += g1(x) + g3(x) + images_rehash(x)
        colours = blocking_water_colours(ctx.shared["dump_m1"])
        k = 0
        for s in t1_scales:
            size, offs = plans[s]
            runs = [(dirs[k + j], off) for j, off in enumerate(offs)]
            k += len(offs)
            L, C, Hd = previews_land(mref, runs, s, colours, cliff_colours(ctx.shared["dump_m1"]))
            rec = t1_eval(mref, L, C)
            rec["hidden_by_cliffs_px"] = int(Hd.sum())
            if rec["covered_px"] != mref.W * mref.H or rec["hidden_by_cliffs_px"]:
                fails.append(f"scale {s}: the cliff-free previews cover {rec['covered_px']} of {mref.W * mref.H} "
                             f"pixels, {rec['hidden_by_cliffs_px']} hidden by cliffs")
            meas[f"scale_{s}"] = rec
            fails += t1_fails(f"scale {s}", rec)
        return meas, fails, "; ".join(
            f"scale {s}: {m['agreement']} (p99 {m['p99_px']}, max {m['max_px']} px, 65+ {m['islands_conn4']['65+']}, "
            f"thin water become land {m['thin_water_became_land']['pixels']} px in "
            f"{m['thin_water_became_land']['reaches_20_px_plus']} reaches of 20 px or more)"
            for s, m in ((k_[6:], v) for k_, v in meas.items()))

    checks["t1_previews"] = SuiteCheck("t1_previews", lambda: base_key("t1_previews", {"plans": plans, "dump": dump_sha}),
                                       t1_run, t1_derive)

    # V1 (SS renders; TST-14): contact sheets from the T1 previews, listed in the manifest
    def v1_run(deadline):
        ent = (ctx.shared.get("suite_runs") or {}).get("t1_previews")
        if not ent:
            man = SUITES / "europe-coast.json"
            rec = ((json.loads(man.read_text(encoding="utf-8")) if man.exists() else {}).get("checks") or {}).get(
                "t1_previews") or {}
            if rec.get("key") == checks["t1_previews"].key_fn() and rec.get("run_dirs"):
                ent = [abs_ws(ctx, x) for x in rec["run_dirs"]]
        ent = ent or t1_run(deadline)
        out = ctx.out / "v1"
        out.mkdir(parents=True, exist_ok=True)
        import contact_sheet
        colours = blocking_water_colours(ctx.shared["dump_m1"])
        k = 0
        windows = {"whole": (0, 0, mref.W, mref.H), "channel": (380, 820, 260, 180), "denmark": (900, 560, 240, 180),
                   "aegean": (1500, 1360, 260, 200)}
        for s in t1_scales:
            _, offs = plans[s]
            runs = [(ent[k + j], off) for j, off in enumerate(offs)]
            k += len(offs)
            L, C, _ = previews_land(mref, runs, s, colours, cliff_colours(ctx.shared["dump_m1"]))
            # the preview panel tiles every T1 preview of the scale together, so a window wider than
            # one preview (the whole map at scales 3 and 6) shows all of its terrain, as the
            # reference panel does (the whole map at scale 1 sits in one preview)
            tiles = [(Path(rd) / f"{SEED}.png", off) for rd, off in runs]
            for name, win in windows.items():
                contact_sheet.build(mref, win, L, C, scale=str(s), origin="floor", panel_px=480,
                                    out=out / f"europe-s{s}-{name}.png", fh_compare=False, previews=tiles)
        (out / "run.json").write_text(json.dumps({"exit": 0, "isolated": True, "error_lines": [],
                                                  "images": {p.name: sha256_file(p) for p in sorted(out.glob("*.png"))}},
                                                 indent=1), encoding="utf-8")
        commit_v1(ctx, out)
        # smoke step 2's CLI preview: the preset itself (--preset, the new-game screen's route) at seed
        # 1000 with the default sliders and cliffs drawn, as the screen shows it
        m1 = mods.m1()
        mods.prepare(m1, "m1")
        smoke = ctx.fh(preview_args(ctx.instance, m1, SMOKE_PREVIEW, SEED, preset=pname), ctx.out / "v1-smoke-preview")
        return [out, smoke.out]

    def v1_derive(dirs):
        rj = load_run_json(dirs[0]) or {}
        fails = images_rehash(dirs[0])
        sheets = sorted((rj.get("images") or {}))
        if len(sheets) < 3:
            fails.append(f"{len(sheets)} contact sheets, want Europe at scales 1, 3 and 6")
        # the committed copies (design section 5: the repo keeps the contact sheets) equal the run's
        committed = sorted(q.name for q in V1_DIR.glob("*.png")) if V1_DIR.is_dir() else []
        if committed != sheets:
            fails.append(f"{rel_repo(V1_DIR)} holds {committed}, the run made {sheets}: run python tools/earth_test.py "
                         f"suite europe-coast --only v1_sheets")
        for name in sheets:
            q = V1_DIR / name
            if q.is_file() and sha256_file(q) != (rj.get("images") or {}).get(name):
                fails.append(f"the committed sheet {rel_repo(q)} differs from the run's")
        smoke = {}
        if len(dirs) < 2:
            fails.append("no smoke-step preview in the run: smoke step 2 compares the new-game screen with it")
        else:
            fails += g1(dirs[1]) + g3(dirs[1])
            try:
                img = derive_preview(dirs[1])["images"]
                smoke = {"path": rel_ws(ctx, Path(dirs[1]) / f"{SEED}.png"), "sha256": img.get(f"{SEED}.png"),
                         "preset": pname, "seed": SEED, "size": SMOKE_PREVIEW}
            except GateError as e:
                fails.append(str(e))
        meas = {"sheets": sheets, "committed": [rel_repo(V1_DIR / n) for n in committed], "smoke_preview": smoke}
        return meas, fails, (f"{len(sheets)} contact sheets for the verification pass's reviewer (V1), committed in "
                             f"{rel_repo(V1_DIR)}; smoke step 2's preview {smoke.get('path')}")

    checks["v1_sheets"] = SuiteCheck("v1_sheets", lambda: base_key("v1_sheets", {"plans": plans, "dump": dump_sha}),
                                     v1_run, v1_derive)

    # T1, T3 (SS; graft 7): the integer-corner offset's positive control. A test build
    # without it (config.lua's one constant set so floor(s / divisor) is 0 at every scale) scores lower on
    # the same pixel-centre grids at scales 3 and 6
    corner_scales = (3, 6)

    def stage_nocorner():
        dst = ctx.out / "stage" / "nocorner" / cfg["identity"]["id"]
        shutil.copytree(MOD, dst, dirs_exist_ok=True)
        p = dst / "prototypes" / "config.lua"
        text = p.read_text(encoding="utf-8")
        want = f"corner_offset_divisor = {cfg['coordinates']['corner_offset_divisor']},"
        if want not in text:
            raise GateError("config.lua's corner_offset_divisor line was not found for the no-offset test build")
        p.write_text(text.replace(want, "corner_offset_divisor = 1000000,"), encoding="utf-8", newline="\n")
        return dst

    def corner_run(deadline):
        nocorner = stage_nocorner()
        real = [probe_modset(ctx, mods, f"m1g{i + 1}") for i in range(2)]
        nc = []
        for i in range(2):
            ms = mods.make(f"ea-nocorner{i + 1}-{mods.build_zip() and mods.zip_sha[:8]}-{folder_hash(nocorner)}-"
                           f"{folder_hash(HERE / 'mods' / 'ep-s8-dump')}",
                           [nocorner, HERE / "mods" / "ep-s8-dump"])
            mods.prepare(ms, f"nocorner{i + 1}")
            nc.append(ms)
        lanes, dirs = [], []
        for i, s in enumerate(corner_scales):
            mgs = preset_mgs(ctx, cfg, s, coast_only=True)
            for j, (label, ms) in enumerate((("real", real[i]), ("nocorner", nc[i]))):
                ln = 2 * i + j
                inst = lane_instance(ctx, ln)
                out = ctx.out / f"corner-{label}-s{s}"
                lanes.append([(dump_settings(ctx, ms, inst, label="grid", grid=grid_spec(mref, s)),
                               scenario_args(inst, ms, 4, SEED, mgs), out, 900)])
                dirs.append(out)
        run_lanes(ctx, lanes)
        return dirs

    def corner_derive(dirs):
        fails, meas = [], {}
        for x in dirs:
            fails += g1(x) + g3(x) + dump_seed_fails(x, "grid", SEED)
        for i, s in enumerate(corner_scales):
            a = t1_eval(mref, *grid_land(mref, dirs[2 * i], s))
            b = t1_eval(mref, *grid_land(mref, dirs[2 * i + 1], s))
            meas[f"scale_{s}"] = {"with_offset": a["agreement"], "without_offset": b["agreement"]}
            if not (b["agreement"] < a["agreement"]):
                fails.append(f"scale {s}: the build without the corner offset scores {b['agreement']}, not lower than "
                             f"{a['agreement']}: the control cannot see the offset")
        return meas, fails, "; ".join(f"scale {k[6:]}: {v['with_offset']} with the offset, {v['without_offset']} "
                                      f"without" for k, v in meas.items())

    checks["t1_corner"] = SuiteCheck("t1_corner", lambda: base_key("t1_corner", {"dump": dump_sha}), corner_run,
                                     corner_derive)

    # T3 (SS; scales 1 to 6): lattice detail is 0 at every pixel-centre tile: the grid with the detail
    # on equals the grid with the detail body set to 0 (a constant twin of that one body). Exit-0
    # guards: every run reads back seed 1000 and tn_map above 0 at the spawn, and the detail-on grid
    # meets T1's bar (the preset applied, G5); positive control (G6): at scales 2 to 6, off-centre
    # tiles beside coast pixels read a non-zero detail and a different elevation with the detail on
    # than off, so the equality at the centres is the lattice's zero, not a detail that never acted.
    def detail_points(s):
        """Off-centre tiles at scale s: the tile one step right of and below the pixel-centre tile
        of DETAIL_PROBES coast pixels (a land pixel with a water 4-neighbour), spread over the map.
        Both of its lattice coordinates lie between pixel centres, so every octave reads basis noise
        off its lattice; at scale 1 every tile holds a pixel centre, so there are none."""
        import numpy as np
        if s < 2:
            return []
        L = mref.land
        coast = L & ~(np.roll(L, 1, 0) & np.roll(L, -1, 0) & np.roll(L, 1, 1) & np.roll(L, -1, 1))
        coast[[0, -1], :] = False
        coast[:, [0, -1]] = False
        rr, cc = np.nonzero(coast)
        pick = np.linspace(0, len(rr) - 1, DETAIL_PROBES).astype(int) if len(rr) else np.array([], int)
        tx = eg.pixel_centre_tiles(cc[pick], mref.wr, s, "floor") + 1
        ty = eg.pixel_centre_tiles(rr[pick], mref.hr, s, "floor") + 1
        return [(int(x), int(y)) for x, y in zip(tx.tolist(), ty.tolist())]

    detail_names = f"elevation,{g['detail']},{cfg['keys']['map']}"

    def detail_run(deadline):
        off = stage_constant(ctx, cfg, [g["detail"]], "0", "detail-off")
        real = [probe_modset(ctx, mods, f"m1g{i + 1}") for i in range(2)]
        offs = []
        for i in range(2):
            ms = mods.with_mods(f"m1do{i + 1}", [off, HERE / "mods" / "ep-s8-dump"])
            mods.prepare(ms, f"m1do{i + 1}")
            offs.append(ms)
        lanes = [[] for _ in range(4)]
        dirs = []
        for i, s in enumerate(DETAIL_SCALES):
            mgs = preset_mgs(ctx, cfg, s, coast_only=True)
            for j, (label, pool) in enumerate((("on", real), ("off", offs))):
                ln = 2 * (i % 2) + j
                ms, inst = pool[i % 2], lane_instance(ctx, ln)
                out = ctx.out / f"detail-{label}-s{s}"
                pts = ";".join(f"{x},{y}" for x, y in [(0, 0)] + detail_points(s))
                lanes[ln].append((dump_settings(ctx, ms, inst, label="grid", grid=grid_spec(mref, s), points=pts,
                                                names=detail_names),
                                  scenario_args(inst, ms, 4, SEED, mgs), out, 900))
                dirs.append(out)
        run_lanes(ctx, lanes)
        return dirs

    def detail_derive(dirs):
        import t1_metrics as t1
        fails, meas = [], {}
        K = cfg["keys"]
        for x in dirs:
            fails += g1(x) + g3(x) + dump_seed_fails(x, "grid", SEED) + spawn_map_fails(x, "grid", K["map"])
        control = {}
        for i, s in enumerate(DETAIL_SCALES):
            _, a, _ = t1.read_grid(dirs[2 * i])
            _, b, _ = t1.read_grid(dirs[2 * i + 1])
            n = int((a != b).sum()) if a.shape == b.shape else -1
            meas[f"scale_{s}"] = n
            if n:
                fails.append(f"scale {s}: {n} pixel-centre grid bits differ between the detail on and off")
            # G5: the detail-on grid is Earth's coast at this scale
            rec = t1_eval(mref, *grid_land(mref, dirs[2 * i], s))
            meas[f"t1_on_s{s}"] = rec["agreement"]
            if rec["agreement"] is None or rec["agreement"] < T1_BAR:
                fails.append(f"scale {s}: the detail-on grid scores T1 {rec['agreement']} under {T1_BAR}: the preset did "
                             f"not apply (G5)")
            # G6: between pixel centres the detail acts
            pts = detail_points(s)
            if not pts:
                continue
            von, voff = (point_values(read_dump(dirs[2 * i + j], "grid")) for j in (0, 1))
            nz = sum(1 for q in pts if (von.get(q) or {}).get(g["detail"]) not in (None, 0))
            de = sum(1 for q in pts if (von.get(q) or {}).get("elevation") != (voff.get(q) or {}).get("elevation"))
            zero_off = all((voff.get(q) or {}).get(g["detail"]) == 0 for q in pts)
            control[s] = [nz, de, len(pts)]
            if not nz or not de or not zero_off:
                fails.append(f"scale {s} positive control: of {len(pts)} off-centre tiles {nz} read a non-zero detail and "
                             f"{de} a different elevation with the detail on than off (the off build's detail reads 0 "
                             f"everywhere: {zero_off}): the equality at pixel centres could not see the detail (G6)")
        meas["control_off_centre"] = {str(k): v for k, v in control.items()}
        return meas, fails, (f"grid bits differing with the detail on and off at scales 1 to 6: "
                             f"{[meas[f'scale_{s}'] for s in DETAIL_SCALES]}; detail-on T1 "
                             f"{[meas[f't1_on_s{s}'] for s in DETAIL_SCALES]}; every run on seed {SEED} with "
                             f"{K['map']} above 0; control, off-centre tiles [non-zero detail, elevation moved, probed] "
                             f"at scales 2 to 6: {[control.get(s) for s in DETAIL_SCALES[1:]]}")

    checks["t3_detail"] = SuiteCheck("t3_detail", lambda: base_key("t3_detail", {"dump": dump_sha,
                                                                                 "probes": DETAIL_PROBES}),
                                     detail_run, detail_derive)

    # T11 (SS; every value): each scale A created and loaded under the next scale B; map and geography
    # id have one value each in this milestone, and the city offset no setting moves yet
    pairs = [(a, a % 6 + 1) for a in DETAIL_SCALES]

    def t11_run(deadline):
        msx = {s: probe_modset(ctx, mods, f"m1s{s}", scale=s) for s in DETAIL_SCALES}
        saves = {}
        lanes = [[] for _ in range(PAR_MAX)]
        for i, s in enumerate(DETAIL_SCALES):
            ln = i % PAR_MAX
            save = ctx.out / f"t11v-create-{s}" / f"s{s}.zip"
            saves[s] = save
            lanes[ln].append((None, create_args(lane_instance(ctx, ln), msx[s], save, preset=pname), save.parent, 900))
        # workers own modsets: re-key so each worker's modsets are its own
        by_lane = {}
        for i, s in enumerate(DETAIL_SCALES):
            by_lane.setdefault(i % PAR_MAX, []).append(s)
        run_lanes(ctx, [l for l in lanes if l])
        loads = [[] for _ in range(PAR_MAX)]
        dirs = [saves[s].parent for s in DETAIL_SCALES]
        for i, s in enumerate(DETAIL_SCALES):
            ln = i % PAR_MAX
            inst = lane_instance(ctx, ln)
            for label, save in ((f"{s - 1 if s > 1 else 6}-under-{s}", saves[s - 1 if s > 1 else 6]),
                                (f"{s}-under-{s}", saves[s])):
                out = ctx.out / f"t11v-{label}"
                loads[ln].append((dump_settings(ctx, msx[s], inst, label="t11", areas=T11_AREAS, late_areas=T11_LATE,
                                                points="0,0", names=t11_names(cfg, mk), types=T11_TYPES),
                                  scenario_args(inst, msx[s], 4, save=save), out, 900))
        run_lanes(ctx, [l for l in loads if l])
        for a, b in pairs:
            dirs += [ctx.out / f"t11v-{a}-under-{b}", ctx.out / f"t11v-{a}-under-{a}", ctx.out / f"t11v-{b}-under-{b}"]
        return dirs

    def t11_derive(dirs):
        fails, meas = [], {}
        for x in dirs:
            fails += g1(x) + g3(x)
        k = len(DETAIL_SCALES)
        any_drift = message_prefix(cfg, "drift_scale")
        for i, (a, b) in enumerate(pairs):
            d_ab, d_aa, d_bb = dirs[k + 3 * i:k + 3 * i + 3]
            ab, aa, bb = (read_dump(x, "t11") for x in (d_ab, d_aa, d_bb))
            rec, f = t11_compare(cfg, mk, a, b, ab, aa, bb)
            drift = count_lines(log_text(d_ab), render_message(cfg, "drift_scale", a, b))
            # the undrifted loads (each world under its own scale) never log a drift line
            undrifted = [count_lines(log_text(x), any_drift) for x in (d_aa, d_bb)]
            rec.update({"drift_lines": drift, "undrifted_drift_lines": undrifted})
            meas[f"{a}_under_{b}"] = rec
            fails += [f"scale {a} loaded under {b}: {x}" for x in f]
            if drift != 1:
                fails.append(f"scale {a} loaded under {b}: the drift line appears {drift} times (want once)")
            if any(undrifted):
                fails.append(f"scale {a} loaded under {b}: a drift line appears on an undrifted load ({a} under {a} "
                             f"{undrifted[0]}, {b} under {b} {undrifted[1]})")
        summary = {p: [m["differing_vs_fresh_a"], m["entities_differing_vs_fresh_a"], m["differing_vs_fresh_b"],
                       m["entities_differing_vs_fresh_b"], m["drift_lines"], m["undrifted_drift_lines"]]
                   for p, m in meas.items()}
        # the entity compare's positive control on real data: some pair's entities differ from fresh B
        if not any(m["entities_differing_vs_fresh_b"] for m in meas.values()):
            fails.append("no scale pair shows an entity differing from its fresh B world: the entity compare could "
                         "not see a scale change (G6)")
        return meas, fails, (f"every scale value A loaded under B, [tiles and entities against fresh A, against fresh "
                             f"B, drift lines, undrifted drift lines]: {summary}; values read back as A's, "
                             f"{cfg['keys']['map']} above 0 in every world")

    checks["t11_values"] = SuiteCheck("t11_values", lambda: base_key("t11_values", {"pairs": pairs, "types": T11_TYPES,
                                                                                   "areas": T11_AREAS,
                                                                                   "late": T11_LATE}),
                                      t11_run, t11_derive)

    # T18 (SS): an elevation-only world created at scale 6 and loaded at scale 3 logs one drift line
    # saying the world follows the changed setting; loaded at 6 it logs none. Two test builds of the
    # same version stand for later ones (a mod's changed content raises on_configuration_changed,
    # measured in design notes 2026-10-28 05:30). Under the "older" build Europe's entry has lost its Map
    # type fields and its [noise-expression] name, as the entry's next version takes them over: the
    # world loaded there at scale 3 is still a Map-type-only world (storage identifies it) and its one
    # drift line names the map by its preset. Under the "moved" build the city offset constant moved,
    # which the frozen registry forbids a real build: loaded at scale 6 the world logs one drift line
    # saying it follows this version of the mod (the tripwire). The world is made from the newest
    # version whose city offset is baked as numbers (europe-coast's version 1 once spawn-cities' version
    # 2, whose offset names name the city fold, takes the preset): an older entry still counts, and its
    # frozen offset constants are what the moved build moves
    gt = next(v for v in reversed(tnconfig.geography_versions(cfg)[mk])
              if all(isinstance(x, int) for x in v["city_offset"]))

    def stage_moved():
        dst = ctx.out / "stage" / "offset-moved" / cfg["identity"]["id"]
        shutil.copytree(MOD, dst, dirs_exist_ok=True)
        q = dst / "prototypes" / "config.lua"
        text = q.read_text(encoding="utf-8")
        want = "city_offset = {" + ", ".join(str(v) for v in gt["city_offset"]) + "},"
        if text.count(want) != 1:
            raise GateError("config.lua's city_offset line was not found for the moved-offset test build")
        moved = [gt["city_offset"][0] + T18_MOVED_PX, gt["city_offset"][1]]
        q.write_text(text.replace(want, "city_offset = {" + ", ".join(str(v) for v in moved) + "},"), encoding="utf-8",
                     newline="\n")
        return dst, moved

    def stage_older():
        """The test build standing for the entry's next version: Europe's entry without its Map type
        fields (intended_property, localised_name, order) and without its [noise-expression] name."""
        dst = ctx.out / "stage" / "entry-older" / cfg["identity"]["id"]
        shutil.copytree(MOD, dst, dirs_exist_ok=True)
        q = dst / "prototypes" / "expressions" / "coast.lua"
        text = q.read_text(encoding="utf-8")
        for field in ("entry.intended_property = ", "entry.localised_name = ", "entry.order = "):
            lines = [ln for ln in text.split("\n") if ln.strip().startswith(field)]
            if len(lines) != 1:
                raise GateError(f"coast.lua's {field.strip()} line was not found once for the older-entry test build")
            text = text.replace(lines[0] + "\n", "")
        q.write_text(text, encoding="utf-8", newline="\n")
        loc = dst / "locale" / "en" / "terra-nauvis.cfg"
        lt = loc.read_text(encoding="utf-8")
        kept = [ln for ln in lt.split("\n") if not ln.startswith(g["entry"] + "=")]
        if len(kept) != len(lt.split("\n")) - 1:
            raise GateError("the locale's [noise-expression] line of the entry was not found for the older-entry build")
        loc.write_text("\n".join(kept), encoding="utf-8", newline="\n")
        return dst

    def t18_run(deadline):
        m6 = probe_modset(ctx, mods, "m1s6", scale=6)
        m3 = probe_modset(ctx, mods, "m1s3", scale=3)
        moved_dir, _ = stage_moved()
        older_dir = stage_older()
        probe = HERE / "mods" / "ep-s8-dump"
        mm = mods.make(f"ea-moved-{mods.build_zip() and mods.zip_sha[:8]}-{folder_hash(moved_dir)}-"
                       f"{folder_hash(probe)}", [moved_dir, probe])
        mods.prepare(mm, "moved")
        set_scale(ctx, mods, mm, 6)
        mo = mods.make(f"ea-older-{mods.zip_sha[:8]}-{folder_hash(older_dir)}-{folder_hash(probe)}", [older_dir, probe])
        mods.prepare(mo, "older")
        set_scale(ctx, mods, mo, 3)
        # the probe's startup settings equal in the world's modset and the test builds', so only the
        # mod's content (and, under the older build, the scale) differs from the creation
        for ms in (m6, m3, mm, mo):
            dump_settings(ctx, ms, ctx.instance, label="t18")()
        save = ctx.out / "t18-create" / "mt.zip"
        mt = write_mgs(ctx, "maptype-elevation-only-t18", {cfg["keys"]["elevation"]: gt["entry"]})
        outs = [ctx.fh(create_args(ctx.instance, m6, save, mgs=mt), save.parent).out]
        for label, ms in (("at-3", m3), ("at-6", m6), ("moved-at-6", mm), ("older-at-3", mo)):
            outs.append(ctx.fh(scenario_args(ctx.instance, ms, 3, save=save), ctx.out / f"t18-load-{label}").out)
        return outs

    def t18_derive(dirs):
        fails = []
        for x in dirs:
            fails += g1(x) + g3(x)
        # every message names the map by its preset, which no version changes (ARCHITECTURE.md, "Guards")
        label = ("map-gen-preset-name", pname)
        line = render_message(cfg, "drift_follows", label, ("mod-setting-name", cfg["settings"]["scale"]["name"]),
                              "3", "6")
        fmt = cfg["number_format"]
        moved = [gt["city_offset"][0] + T18_MOVED_PX, gt["city_offset"][1]]
        upd = render_message(cfg, "drift_update", label, gt["cx"], fmt % moved[0], fmt % gt["city_offset"][0])
        prefixes = (message_prefix(cfg, "drift_follows"), message_prefix(cfg, "drift_update"))

        def drift_lines(text):
            # the two messages share their opening words: each line counts once
            return sum(1 for ln in text.splitlines() if any(pf in ln for pf in prefixes))
        n3 = count_lines(log_text(dirs[1]), line)
        n6 = drift_lines(log_text(dirs[2]))
        n_upd = count_lines(log_text(dirs[3]), upd)
        n_moved_any = drift_lines(log_text(dirs[3]))
        n_older = count_lines(log_text(dirs[4]), line)
        n_older_any = drift_lines(log_text(dirs[4]))
        if n3 != 1 or n6:
            fails.append(f"the elevation-only world logs {n3} drift lines at scale 3 (want 1: {line!r}) and {n6} at 6")
        if n_upd != 1 or n_moved_any != 1:
            fails.append(f"under a build whose city offset constant moved, the elevation-only world logs the update "
                         f"line {n_upd} times and {n_moved_any} drift lines in all (want 1 and 1: {upd!r})")
        if n_older != 1 or n_older_any != 1:
            fails.append(f"under a build whose entry lost its Map type fields and [noise-expression] name, the "
                         f"elevation-only world loaded at scale 3 logs the drift line {n_older} times and "
                         f"{n_older_any} drift lines in all (want 1 and 1: an older entry still counts, and the line "
                         f"names the preset: {line!r})")
        return ({"at_3": n3, "at_6": n6, "moved_at_6": n_upd, "moved_at_6_any": n_moved_any, "older_at_3": n_older,
                 "older_at_3_any": n_older_any}, fails,
                f"elevation-only world made at 6: loaded at 3, {n3} drift line; at 6, {n6}; under a build whose city "
                f"offset constant moved, {n_upd} update line; under a build whose entry lost its Map type fields, at "
                f"3, {n_older} drift line naming the preset")

    checks["t18_drift"] = SuiteCheck("t18_drift", lambda: base_key("t18_drift", {"moved_px": T18_MOVED_PX,
                                                                                 "entry": gt["entry"]}), t18_run,
                                     t18_derive)

    # The Map type route, measured and reported (Contradictions item 15; T15): its Tile, Entity and Cliff
    # complexity and its forced-generation ratio against M0 at 16 LP, scale 6, with the same pair at 8 LP
    # in the group as the diagnostic (design section 6.2)
    pos = europe_positions(cfg, mref)
    m1t, m1d = earth_driver_modsets(ctx, mods)
    m0t, m0d, _ = driver_modsets(ctx, mods)

    def mt_run(deadline):
        mt = maptype_mgs(ctx, cfg)
        cx = ctx.fh(preview_args(ctx.instance, ctx.shared["m1"], 64, mgs=mt, verbose=True), ctx.out / "mt-cx").out
        sa = make_save_mgs(ctx, mods, m1t, "tq1-gen-block", pos["block"][6], "mt-a", mt)
        sb = make_save_mgs(ctx, mods, m0t, "tq1-gen-block", pos["block"][6], "mt-b")
        return [cx, pair_batch(ctx, {"a": (m1t, sa), "b": (m0t, sb)}, T15B["reps_suite"], list(PROXY_MASKS),
                               "t15b-maptype", deadline)]

    def mt_derive(dirs):
        fails = g1(dirs[0])
        cx = ctx_complexity(dirs[0])
        census = ((baseline_record().get("t15b_europe") or {}).get("census_m0") or {}).get("6") or {}
        m, f, _ = derive_t15b([dirs[1]], {}, T15B["reps_suite"], pair="m1_m0", label="Map type/M0t", census_m0=census)
        fails += f
        missing = [f"{x:#x}" for x in PROXY_MASKS if f"{x:#x}" not in m]
        if missing:
            fails.append(f"the Map type pair has no ratio at {missing}: the batch times it at "
                         f"{[f'{x:#x}' for x in PROXY_MASKS]}")
        r16, r8 = ((m.get(f"{x:#x}") or {}).get("ratio") for x in PROXY_MASKS)
        return {"complexity": cx, "forced": m}, fails, \
            (f"reported, not gated: the Map type route compiles Tile {cx.get('tile', {}).get('complexity')}, Entity "
             f"{cx.get('entity', {}).get('complexity')}, Cliff {cx.get('cliff', {}).get('complexity')}; forced "
             f"generation {r16}x M0 at 16 LP, {r8}x at 8 LP (diagnostic)")

    checks["maptype_cost"] = SuiteCheck("maptype_cost", lambda: base_key(
        "maptype_cost", {"sig": esig(m1t, "m1t"), "timing": timing, "control": ctl, "pos": pos, "records": TIMED_RECORDS,
                         "masks": list(PROXY_MASKS)}),
        mt_run, mt_derive)

    # T15 (SS and FG first baselines; design experiment 1, base part; P1, P3): Europe in the TQ1b
    # harness at scales 6 and 1 against M0, one group per scale
    def t15b_run(deadline):
        out = []
        for s in T15B_SCALES:
            mgs = preset_mgs(ctx, cfg, s)
            sa = make_save_mgs(ctx, mods, m1t, "tq1-gen-block", pos["block"][s], f"m1t-s{s}", mgs)
            sb = make_save_mgs(ctx, mods, m0t, "tq1-gen-block", pos["block"][s], f"m0t-s{s}")
            masks = [getattr(ctx.perf, m) if m != "MASK24" else MASK24 for m in T15B_MASKS[s]]
            out.append(pair_batch(ctx, {"a": (m1t, sa), "b": (m0t, sb)}, T15B["reps_suite"], masks, f"t15b-m1-s{s}",
                                  deadline))
        return out

    def t15b_derive(dirs):
        census = (baseline_record().get("t15b_europe") or {}).get("census_m0")
        meas, fails, detail = derive_t15b_europe(dict(zip(T15B_SCALES, dirs)), lim, T15B["reps_suite"],
                                                 T15B_MASKS, census)
        for s in T15B_SCALES:
            frac = pos["block_land"][s]
            meas[f"block_land_s{s}"] = frac
            if not (BLOCK_LAND[0] <= frac <= BLOCK_LAND[1]):
                fails.append(f"scale {s}: the block {pos['block'][s]} holds {frac:.1%} reference land, not 50 to 95 %")
        return meas, fails, detail

    checks["t15b_m1"] = SuiteCheck("t15b_m1", lambda: key_of({
        "check": "t15b_m1", "sig": [esig(m1t, "m1t"), sig(m0t, "m0t")], "control": ctl, "timing": timing,
        "config": T15B, "pos": pos, "masks": T15B_MASKS, "build": GAME_BUILD, "borderline": BORDERLINE,
        "records": TIMED_RECORDS, "earth": [d["mod"], dump_sha]}), t15b_run, t15b_derive)

    # P7 and the recorded benchmark-mode rows: the walker on Europe and on M0
    walk_spec = "walk:nauvis:{x0}:{y0}:{dx}:{dy}:{R}:{P}:{N}:{D}:{T0}".format(**pos["walk"])

    def walker_run_pair(deadline, label="walk", earth_ms=None, mgs=None, masks=(PROXY_MASKS[0],)):
        """M1 then M0 on the walker at each mask in turn: [M1, M0] per mask, the 16 LP pair under its
        own names and each further mask's pair suffixed with the mask (walk-m1-ff, walk-m0-ff)."""
        ms = earth_ms or m1d
        mgs = mgs or preset_mgs(ctx, cfg, 6)
        out = []
        for mask in masks:
            sfx = "" if mask == PROXY_MASKS[0] else f"-{mask:x}"
            for lab, mset, m in ((f"{label}-m1{sfx}", ms, mgs), (f"{label}-m0{sfx}", m0d, None)):
                save = make_save_mgs(ctx, mods, mset, "tq2-mode", walk_spec, lab, m)
                ticks = pos["walk"]["T0"] + pos["walk"]["N"] * pos["walk"]["P"] + pos["walk"]["D"] + 2
                _, load_pre = ctx.perf.wait_quiet(deadline)
                watcher = ctx.perf.Watcher(ctx.out / f"{lab}-affinity.jsonl", mask, ctx.job)
                r = ctx.fh(["scenario", "--instance", "ea-time", "--modset", mset, "--save", save, "--ticks",
                            str(ticks), "--", "--benchmark-verbose", "all", "--threads", str(T15B["threads"])],
                           ctx.out / lab, timeout=900, watcher=watcher, monitor=True)
                after = ctx.perf.tasklist_game()
                recs, _, _ = watcher.finish()
                persist_monitor(r.out.parent / f"{r.out.name}-monitor.json", r.mon, mask, load_pre, after)
                if r.mon:
                    r.mon.close()
                out.append(r.out)
        return out

    checks["walker_m1"] = SuiteCheck("walker_m1", lambda: key_of({
        "check": "walker_m1", "sig": [esig(m1d, "m1d"), sig(m0d, "m0d")], "control": ctl, "timing": timing,
        "walk": walk_spec, "masks": list(PROXY_MASKS), "build": GAME_BUILD, "records": TIMED_RECORDS,
        "earth": [d["mod"], dump_sha]}),
        lambda deadline: walker_run_pair(deadline, masks=PROXY_MASKS), lambda dirs: derive_walker_pair(dirs, lim))

    # T15-f (test notes 5.5; design section 6.2, recorded): preview time of the Europe preset at scale 6
    # against M0, centred on the T15b block (Phase 4's --offset 2304,1280 there), interleaved in one group
    pt_offset = (pos["save_block"][0] * 32 + 256, pos["save_block"][1] * 32 + 256)

    def pt_run(deadline):
        root = ctx.out / "preview-time"
        root.mkdir(parents=True, exist_ok=True)
        cfgs = {"m1": (ctx.shared["m1"], preset_mgs(ctx, cfg, P4_SCALE)), "m0": (ctx.shared["m0"], None)}
        reps = PREVIEW_TIME["reps"]
        order = [(c, s) for s in PREVIEW_TIME["sizes"] for c in ("m1", "m0")]
        valid = {k: 0 for k in order}
        idx, rnd = 0, 0
        while any(v < reps for v in valid.values()):
            for c, size in order[rnd % len(order):] + order[:rnd % len(order)]:
                if valid[(c, size)] >= reps:
                    continue
                idx += 1
                ms, mgs = cfgs[c]
                run = root / f"r{idx:03d}-{c}-{size}"
                _, load_pre = ctx.perf.wait_quiet(deadline)
                r = ctx.fh(preview_args(ctx.instance, ms, size, SEED, mgs, pt_offset) +
                           ["--", "--threads", str(PREVIEW_TIME["threads"])], run, monitor=True)
                persist_monitor(root / f"{run.name}-monitor.json", r.mon, None, load_pre, ctx.perf.tasklist_game())
                if r.mon:
                    r.mon.close()
                raw = preview_time_from_raw(run)
                with open(root / "reps.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"out": str(run), "valid": raw["valid"], "seconds": raw["seconds"],
                                        "reasons": raw["reasons"]}, default=str) + "\n")
                if raw["valid"]:
                    valid[(c, size)] += 1
                if idx > 6 * reps * len(order):
                    raise GateError("too many discarded preview-time repetitions")
            rnd += 1
        return [root]

    checks["preview_time"] = SuiteCheck("preview_time", lambda: base_key(
        "preview_time", {"timing": timing, "config": PREVIEW_TIME, "offset": pt_offset, "dump": dump_sha}),
        pt_run, derive_preview_time)

    # P4 to P6: TQ2's exploring frontier across its band, fixed in geo coordinates, in real time on a
    # loopback server at 60 UPS, M1 against M0 interleaved in one group
    rt_spec = "rtexplore:nauvis:{cx0}:{cy}:{R}:{K}:{P}:{D}:{T0}".format(**pos["explore"])

    def rt_runs(deadline, label="rt", earth_ms=None, mgs=None):
        ms = earth_ms or m1d
        mgs = mgs or preset_mgs(ctx, cfg, 6)
        out = {"m1": [], "m0": []}
        for i in range(RT_REPS):
            for cfg_, mset, m in (("m1", ms, mgs), ("m0", m0d, None)):
                lab = f"{label}-{cfg_}-{i + 1}"
                save = make_save_mgs(ctx, mods, mset, "tq2-mode", rt_spec, f"save-{lab}", m)
                out[cfg_].append(server_run_save(ctx, mset, save, lab, SERVER["rt_timeout"], ["tq2-rt"]))
        return [x for k in ("m1", "m0") for x in out[k]]

    def rt_derive(dirs):
        return derive_rt_pair({"m1": dirs[:RT_REPS], "m0": dirs[RT_REPS:]}, lim)

    checks["rt_m1"] = SuiteCheck("rt_m1", lambda: key_of({
        "check": "rt_m1", "sig": [esig(m1d, "m1d"), sig(m0d, "m0d")], "control": ctl, "timing": timing,
        "spec": rt_spec, "reps": RT_REPS, "server": [SERVER, sha256_file(HERE / "perf-server-settings.json")],
        "build": GAME_BUILD, "earth": [d["mod"], dump_sha]}), rt_runs, rt_derive)

    # P19: the save increment of the forced block, M1 against M0 (Phase 4's server-save job)
    save_spec = "save:nauvis:{}:{}:1".format(*pos["save_block"])

    def save_runs(deadline, label="save", earth_ms=None, mgs=None, m0=True):
        ms = earth_ms or m1d
        mgs = mgs or preset_mgs(ctx, cfg, 6)
        cfgs = [("m1", ms, mgs)] + ([("m0", m0d, None)] if m0 else [])
        out = []
        for cfg_, mset, m in cfgs:
            save = make_save_mgs(ctx, mods, mset, "tq2-mode", save_spec, f"save-{label}-{cfg_}", m)
            out.append(server_run_save(ctx, mset, save, f"{label}-{cfg_}", SERVER["save_timeout"],
                                       ["tq2-pre", "tq2-post"]))
        return out

    checks["save_m1"] = SuiteCheck("save_m1", lambda: key_of({
        "check": "save_m1", "sig": [esig(m1d, "m1d"), sig(m0d, "m0d")], "control": ctl, "timing": timing,
        "spec": save_spec, "server": [SERVER, sha256_file(HERE / "perf-server-settings.json")], "build": GAME_BUILD,
        "earth": [d["mod"], dump_sha]}), save_runs, lambda dirs: derive_save_pair(dirs, lim))

    # The first-column hitch (measured): benchmark-mode BasicTilesSupportCompute for the
    # first and a later column, and the longest real-time interval, for the real build, its
    # constant-coast twin (the coast's share) and the tried reduction, a cheaper coast fit
    def hitch_run(deadline):
        twin = stage_twin(ctx, cfg)
        mtw = mods.with_mods("m1dtwin", [HERE / "mods" / "tq2-driver", twin])
        cheap = stage_cheap_fit(ctx, cfg)
        mch = mods.make(f"ea-m1dcheap-{mods.build_zip() and mods.zip_sha[:8]}-{folder_hash(cheap)}-"
                        f"{folder_hash(HERE / 'mods' / 'tq2-driver')}",
                        [cheap, HERE / "mods" / "tq2-driver"])
        out = []
        for label, ms in (("real", m1d), ("twin", mtw), ("cheap", mch)):
            mods.prepare(ms, f"hitch-{label}")
            out += walker_run_pair(deadline, f"hitch-walk-{label}", ms)[:1]
            out += rt_runs_one(ctx, mods, ms, rt_spec, preset_mgs(ctx, cfg, 6), f"hitch-rt-{label}")
        return out

    def hitch_derive(dirs):
        fails, meas = [], {}
        for i, label in enumerate(("real", "twin", "cheap")):
            w, f, _ = derive_walker(dirs[2 * i])
            r, f2, _ = derive_rt([dirs[2 * i + 1]])
            fails += [f"{label}: {x}" for x in f + f2]
            # the walker's steps in time order from its first request: the first column into empty land,
            # then the median of the later ones (derive_walker's support_steps)
            s = w.get("support_steps") or step_summary([])
            meas[label] = {"basic_tiles_support_first_ms": s["first_ms"], "basic_tiles_support_later_ms": s["later_ms"],
                           "basic_tiles_support_max_ms": s["max_ms"],
                           "rt_longest_ms": r.get("max"), "rt_over_20ms": r.get("over_20ms")}
        rl, tw = meas.get("real", {}), meas.get("twin", {})
        if rl.get("basic_tiles_support_first_ms") and tw.get("basic_tiles_support_first_ms"):
            meas["coast_share_first_ms"] = round(rl["basic_tiles_support_first_ms"] - tw["basic_tiles_support_first_ms"], 3)
        return meas, fails, f"measured (DECISIONS europe-coast, the hitch entry): {meas}"

    checks["hitch"] = SuiteCheck("hitch", lambda: key_of({
        "check": "hitch", "sig": [esig(m1d, "m1d")], "control": ctl, "timing": timing, "walk": walk_spec,
        "rt": rt_spec, "build": GAME_BUILD, "earth": [d["mod"], d["data_src"], dump_sha]}), hitch_run, hitch_derive)

    # The start-area save excess (measured): whole saves and their map files for M0, the
    # shipped spawn, Phase 4's London start (a test-only full MGS setting the offset names, never with
    # --preset) and the constant-coast twin there, which puts no sea near London
    def excess_run(deadline):
        lmgs = write_mgs(ctx, "london-start", london_start_pen(ctx, cfg, mref, pname, g))
        twin = stage_twin(ctx, cfg)
        mtw = mods.with_mods("m1dtwin", [HERE / "mods" / "tq2-driver", twin])
        mods.prepare(mtw, "excess-twin")
        out = save_runs(deadline, "excess-spawn", m1d, preset_mgs(ctx, cfg, 6), m0=True)
        out += save_runs(deadline, "excess-london", m1d, lmgs, m0=False)
        out += save_runs(deadline, "excess-london-twin", mtw, lmgs, m0=False)
        # the tried reductions: the same tree in fewer characters, and a fit with half the terms
        for kind in ("nospace", "cheap"):
            src = stage_cheap_fit(ctx, cfg, kind)
            ms = mods.make(f"ea-m1d{kind}-{mods.build_zip() and mods.zip_sha[:8]}-{folder_hash(src)}-"
                           f"{folder_hash(HERE / 'mods' / 'tq2-driver')}",
                           [src, HERE / "mods" / "tq2-driver"])
            mods.prepare(ms, f"excess-{kind}")
            out += save_runs(deadline, f"excess-spawn-{kind}", ms, preset_mgs(ctx, cfg, 6), m0=False)
        return out

    def excess_derive(dirs):
        fails, meas = [], {}
        for label, x in zip(("spawn_m1", "m0", "london_m1", "london_twin", "spawn_nospace", "spawn_cheap"), dirs):
            sv, f = derive_server(x, ["tq2-pre", "tq2-post"])
            fails += [f"{label}: {y}" for y in f]
            pre = Path(x) / "tq2-pre.zip"
            meas[label] = {"pre_bytes": (sv.get("saves", {}).get("tq2-pre") or {}).get("bytes"),
                           "map_files": save_zip_parts(pre) if pre.exists() else None}
        m0 = (meas.get("m0") or {}).get("pre_bytes")
        for k in ("spawn_m1", "london_m1", "london_twin", "spawn_nospace", "spawn_cheap"):
            if k in meas and m0 and meas[k].get("pre_bytes"):
                meas[k]["ratio_to_m0"] = round(meas[k]["pre_bytes"] / m0, 4)
        return meas, fails, f"measured (DECISIONS europe-coast, the save-excess entry): {meas}"

    checks["save_excess"] = SuiteCheck("save_excess", lambda: key_of({
        "check": "save_excess", "sig": [esig(m1d, "m1d"), sig(m0d, "m0d")], "control": ctl, "spec": save_spec,
        "server": [SERVER, sha256_file(HERE / "perf-server-settings.json")], "build": GAME_BUILD,
        "earth": [d["mod"], dump_sha]}), excess_run, excess_derive)
    return checks


def stage_constant(ctx, cfg, names, value, tag):
    """A staged copy of tools/mods/ea-coast-twin turning `names` into the constant `value` (the
    constant-coast twin's mechanism, here for one body: the detail-off build)."""
    src = HERE / "mods" / "ea-coast-twin"
    dst = ctx.out / "stage" / f"ea-coast-twin-{tag}"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    lua_list = ", ".join(json.dumps(n) for n in names)
    (dst / "twin-names.lua").write_text(f"return {{names = {{{lua_list}}}, value = {json.dumps(value)}}}\n",
                                        encoding="utf-8", newline="\n")
    info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
    info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
    (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    return dst


def stage_cheap_fit(ctx, cfg, kind="cheap"):
    """A test build of the mod with another coast body, for the measured experiments (never shipped):
    "cheap", the 4,096-term checkpoint of the same fit (data-src/fits/<map>/model-4096.npz), which
    cuts the Tile program but misses T1's bar offline (curve.json: 0.98667); "nospace", the shipped
    tents with every space dropped from the expression text (the same tree in fewer characters).
    Emitted by build_geo.py into a staged copy of the mod only."""
    import build_geo
    _, mk, _ = first_preset(cfg)
    dst = ctx.out / "stage" / kind / cfg["identity"]["id"]
    shutil.copytree(MOD, dst, dirs_exist_ok=True)
    spec = build_geo.fit_spec(mk)
    model = "model-4096.npz" if kind == "cheap" else spec["bodies"]["geo"]["checkpoint"]
    meta, idx, coef = build_geo.load_model(build_geo.FITS / mk / model)
    locs, expr, stats = build_geo.tent_body(meta, idx, coef)
    if kind == "nospace":
        locs = {k: v.replace(" ", "") for k, v in locs.items()}
        expr = expr.replace(" ", "")
        lines = ["local L = {}"]
        for k, v in locs.items():
            lines += nospace_lines(v, f'L["{k}"] = ', "")
        lines += nospace_lines(expr, "return {locals = L, expression = ", "}")
        text = "\n".join(lines) + "\n"
    else:
        text = build_geo.render_lua(locs, expr, stats, [f"Test-only: {model}, for the measured experiments."])
    (dst / "prototypes" / "generated" / spec["bodies"]["geo"]["file"]).write_text(text, encoding="utf-8", newline="\n")
    return dst


def nospace_lines(text, first, last, width=118):
    """A long Lua string literal without spaces, broken anywhere with the \\z escape (test builds only)."""
    out, cur, pos = [], first + '"', 0
    while True:
        rest = text[pos:]
        if len(cur) + len(rest) + 1 + len(last) <= width:
            out.append(cur + rest + '"' + last)
            return out
        room = width - len(cur) - 2
        out.append(cur + rest[:room] + "\\z")
        pos += room
        cur = "  "


def server_run_save(ctx, modset, save, label, timeout, saves):
    """server_run on an existing save (make_save_mgs made it, with the job baked in). The monitor's
    record goes beside the run (its peak working set is T15-h's while exploring at 24 LP)."""
    wd = ctx.ws / "test-instance" / "instances" / "ea-srv" / "write-data"
    (wd / "saves").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    _, load_pre = ctx.perf.wait_quiet(ctx.deadline or time.time() + 3600)
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
    persist_monitor(r.out.parent / f"{r.out.name}-monitor.json", r.mon, None, load_pre, ctx.perf.tasklist_game())
    if r.mon:
        r.mon.close()
    return r.out


def rt_runs_one(ctx, mods, modset, spec, mgs, label):
    save = make_save_mgs(ctx, mods, modset, "tq2-mode", spec, f"save-{label}", mgs)
    return [server_run_save(ctx, modset, save, label, SERVER["rt_timeout"], ["tq2-rt"])]


# ------------------------------------------------------------------------------------------------ spawn-cities

# Design section 8, milestone 1: spawns at the chosen city by the shift (S7 option ii), the spawn lake and
# start land guarantee, sparse inland lakes, the start message, the RSO warning and the Nauvis-only
# guard. world = geo - (cx, cy): tools/oracle.py models the float32 fold (T7 (c)) and converts places;
# europe-coast's T1, T2 and T3 rows score the coast in a coast-only world (coast_only_pen) and its
# timed positions place through runner_offset (the T15b block keeps its geo position).
SC_SCALES = (1, 3, 6)
SC_SEEDS_C = (1000, 1002, 1004, 4000000001, 4294967295)     # T7 (c): S7's five seeds
# T7 (b)'s coastal and low-lying sample at scale 1, run before the sweep (FEAS-06): the plan's five
# and ARCHITECTURE.md's Amsterdam
SC_COASTAL = ("london", "lisbon", "oslo", "helsinki", "monaco", "amsterdam")
SC_ORES = ("iron-ore", "copper-ore", "coal", "stone")
SC_ENEMY_TYPES = ("unit-spawner", "turret", "unit")
SC_START_R = 150            # T7 (b): starting ore and enemies within 150 tiles of the spawn
SC_DRY_R = 12               # T7 (b): no player-blocking water within 12 tiles (PD: room for the crash site)
SC_LAKE_MIN = 1000          # T7 (b): the start lake's own footprint holds at least 1,000 water tiles
SC_LAKE_CENTRE = (40, 110)  # T7 (b): the footprint is centred 40 to 110 tiles from the spawn
SC_ORE_SHARE = 0.5          # T7 (b): at least half of vanilla's resource tiles at the same seed (PD)
# T7 (b)'s ore bar as a rate: every ore within 150 tiles of every start,
# and at most this share of the seed-1000 sweep's ore checks under half of vanilla's tiles, none of
# them at a start whose disc holds no sea by tn_land_coarse
SC_ORE_RATE = 0.015
# The start disc's sea, read from the coarse checkpoint offline, is held to the game's tn_land_coarse
# at the spawn and at 8 points on the disc's rim in every T7 scenario, within this many reference px
SC_COARSE_TOL = 0.01
SC_COARSE_PROBES = ((0, 0), (150, 0), (106, 106), (0, 150), (-106, 106), (-150, 0), (-106, -106), (0, -150),
                    (106, -106))
SC_AREA = 224               # the dumped square around the spawn, +-224 tiles (S7's enemy ring)
SC_LAKE_GRID = 160          # the spawn lake's footprint, the lake expression at every tile within +-160
SC_HOTSPOT_MARGIN_KM = "city_margin_km"   # approvals-data.json rules key: r + j + this, map km (APPROVALS 12)
SC_DENSITY_TOL = 0.30       # T3: inland-lake density within 30 percent of its design value (PD)
SC_DENSITY_BLOCK = 2048     # T3: sampled blocks of 2,048 geo tiles (four spot-noise regions of 1,024)
SC_DENSITY_STEP = 4         # T3: the inland-lake expression sampled every 4 tiles in a block
SC_DENSITY_MIN_ELIGIBLE = 0.5   # T3: a sampled inland block has at least half its points where lakes may lie
SC_SQUARE = 512             # T3: the real-tile square's side in tiles, at scales 1 and 6
SC_SQUARE_LATTICE = 64      # T3: scale 1's candidate squares start every 64 geo tiles from the extent's corner
SC_FORCE_PICKS = ("oslo", "athens", "madrid")   # T18 (c): three other cities
SC_T11 = ("london", "oslo")  # T11: a world created with city A, loaded with city B
# T11: the probe blocks at the start area's edge, 3 x 3 chunks just outside the 196 start chunks
SC_T11_AREAS = "224,-48,96,96;-320,-48,96,96;-48,224,96,96;-48,-320,96,96"
T14_ISLAND = "island"  # T14's negative control: a vanilla preset that sets elevation (base map-gen-presets.lua)
SC_START_AREAS = (1 / 6, 6)  # T4: the starting-area slider's smallest and largest settings
# T4: the square sampled around the spawn (x0 = y0 = -2048, every 16 tiles, 256 x 256 points): enemy bases
# are sparse spots, so a ray can miss the disc's edge; the radius is the nearest positive point
SC_T4_GRID = (-2048, 16, 256)
SC_T4_TOL = 23              # T4: Earth's and M0's radii agree within 23 tiles (one diagonal grid step)


def sc_map(cfg):
    """(map key, geography) of the first preset's map, which must carry a city fold."""
    _, mk, g = first_preset(cfg)
    if "city" not in g:
        raise GateError(f"config.lua gives {mk} no city fold (spawn-cities)")
    return mk, g


def sc_values(cfg, g):
    return cfg["settings"][g["city_setting"]]["allowed_values"]


def sc_mgs(ctx, cfg, mk, scale, city, label, extra=None):
    """A full MGS file of the map's preset as the startup settings scale and city would bake it
    (expected_pen; T13 holds the preset route and this route equal)."""
    pen = expected_pen(cfg, mk, scale, city)
    pen.update(extra or {})
    return write_mgs(ctx, f"sc-{label}", pen)


def sc_city_modset(ctx, mods, tag, city=None, scale=None, extra=()):
    """M1 plus the dump probe (and `extra` mods), prepared, with the spawn-city and scale settings
    written explicitly (G7)."""
    cfg = mods.cfg
    _, g = sc_map(cfg)
    ms = mods.with_mods(tag, [HERE / "mods" / "ep-s8-dump"] + list(extra))
    mods.prepare(ms, tag)
    sets = []
    if city is not None:
        sets.append(f"startup.{cfg['settings'][g['city_setting']]['name']}={city}")
    if scale is not None:
        sets.append(f"startup.{cfg['settings']['scale']['name']}={int(scale)}")
    if sets:
        res = ctx.fh_plain(["settings", ms, "--set"] + sets)
        if not res.startswith("RESULT ok"):
            raise GateError(f"fh.py settings {ms}: {res}")
    return ms


def sc_m0_probe(ctx, mods):
    """M0 plus the dump probe: vanilla's start at the same seed, the comparator of T7 (b)'s ore."""
    ms = mods.with_mods("m0p", [HERE / "mods" / "ep-s8-dump"], earth=False)
    mods.prepare(ms, "m0p")
    return ms


def sc_t7_settings(ctx, ms, inst, cfg, g):
    """The dump probe's settings for one T7 (b) scenario: the square around the spawn (tiles, ore,
    enemies, cliffs), S7's measure() at the spawn, the city index, map, scale and coarse land field at
    (0, 0) and the coarse field at SC_COARSE_PROBES (the start disc's sea, read offline, is held to
    them), and the spawn lake's expression at every tile within SC_LAKE_GRID (1 where it is below 0:
    its own footprint)."""
    R = SC_LAKE_GRID
    K = cfg["keys"]
    return dump_settings(ctx, ms, inst, label="t7", areas=f"{-SC_AREA},{-SC_AREA},{2 * SC_AREA},{2 * SC_AREA}",
                         types="resource,unit-spawner,turret,unit,cliff", decoratives=False, measure="0,0",
                         points=";".join(f"{x},{y}" for x, y in SC_COARSE_PROBES),
                         names=f"{g['city_index']},{K['map']},{K['scale']},{K['land_coarse']}",
                         grid=f"{-R},{-R},1,{2 * R},{2 * R}", grid_name=g["spawn_lake"],
                         grid_threshold="0", grid_op="lt")


def sc_m0_settings(ctx, ms, inst):
    """M0's comparator scenario: S7's measure() at the spawn only."""
    return dump_settings(ctx, ms, inst, label="t7", areas="", types="resource", decoratives=False, measure="0,0")


def sc_grid_bits(dump):
    """The dump's grid as {(x, y): bit} for bit 1 (value op threshold)."""
    import numpy as np
    g = dump.get("grid") or {}
    if not g.get("recognised", True) or not g.get("rows"):
        return None, g
    arr = np.empty((int(g["ny"]), int(g["nx"])), np.uint8)
    for j, row in enumerate(g["rows"]):
        v, n = zip(*(tok.split("*") for tok in row.split(" ")))
        arr[j] = np.repeat(np.array(v, np.uint8), np.array(n, np.int64))
    return arr, g


def sc_m0_ore(run_dir):
    """Vanilla's resource tiles within SC_START_R of the spawn, per ore, from M0's measure()."""
    m = (read_dump(run_dir, "t7").get("measure") or [{}])[0]
    return {o: int(((m.get("resources") or {}).get(o) or {}).get("n150") or 0) for o in SC_ORES}


_COARSE_FIELD = {}


def sc_coarse_field(mk):
    """The map's coarse land field (the body the preset key tn_land_coarse names) as its tent levels
    [(spacing in reference px, coefficient grid)], from the coarse checkpoint its generated file is
    emitted from (build_geo's check holds the file to it). A level's tents are the bilinear
    interpolation of its grid on its own lattice (zero beyond the grid), so the field is exact
    everywhere, beyond the raster's edge too."""
    if mk not in _COARSE_FIELD:
        import numpy as np
        import build_geo
        import build_spawn
        meta, idx, coef = build_geo.load_model(build_spawn.coarse_checkpoint(mk))
        levels, k0 = [], 0
        for k, a in enumerate(idx):
            G = np.zeros(meta["shapes"][k], np.float64)
            G.ravel()[a] += coef[k0:k0 + len(a)]
            k0 += len(a)
            if len(a):
                levels.append((float(meta["step"] * 2 ** k), G))
        _COARSE_FIELD[mk] = levels
    return _COARSE_FIELD[mk]


def sc_coarse_at(cfg, mk, index, scale, xs, ys):
    """tn_land_coarse at world tiles (xs, ys) of a world spawned at city `index` (1 to n) at `scale`,
    offline: the coordinate chain reads the fit at U = col + x / s, V = row + y / s (coast.lua, with the
    city offset s * (col - wr) + floor(s / 2) of oracle.spawn_offset)."""
    import numpy as np
    import oracle
    _, px = oracle.city_fold(cfg, mk)
    col, row = px[int(index) - 1]
    s = float(int(scale))
    U = col + np.asarray(xs, np.float64) / s
    V = row + np.asarray(ys, np.float64) / s
    out = np.zeros(np.shape(U), np.float64)
    for sp, G in sc_coarse_field(mk):
        u, v = U / sp, V / sp
        i0, j0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
        fu, fv = u - i0, v - j0
        H, W = G.shape
        for di, wu in ((0, 1 - fu), (1, fu)):
            for dj, wv in ((0, 1 - fv), (1, fv)):
                i, j = i0 + di, j0 + dj
                ok = (i >= 0) & (i < W) & (j >= 0) & (j < H)
                out[ok] += G[j[ok], i[ok]] * wu[ok] * wv[ok]
    return out


_DISC_MIN = {}


def sc_start_disc_min(cfg, mk, index, scale):
    """The least tn_land_coarse over the start disc (every tile within SC_START_R of the spawn) of the
    world spawned at city `index` at `scale`: below 0, the coarse field reads sea in the disc."""
    key = (mk, int(index), int(scale))
    if key not in _DISC_MIN:
        import numpy as np
        r = SC_START_R
        ys, xs = np.mgrid[-r:r + 1, -r:r + 1]
        inside = xs * xs + ys * ys <= r * r
        _DISC_MIN[key] = float(sc_coarse_at(cfg, mk, index, scale, xs[inside], ys[inside]).min())
    return _DISC_MIN[key]


def sc_ore_verdict(records, vanilla, rate=None):
    """T7 (b)'s ore bar over T7 records {label: record of sc_t7_eval}:
    (summary, failures). Each record holds four ore checks. Absolute: every ore has tiles within
    SC_START_R of the spawn reachable on foot (none within 150, or none reachable, fails), each record
    carries its start disc's sea, and no check under half of vanilla's tiles at the same seed sits at
    a start whose disc holds no sea by tn_land_coarse. With `rate` (the sweep's), more than `rate` of
    the checks under half fails. The summary names every check under half."""
    fails, under, total = [], [], 0
    for label, rec in records.items():
        disc = rec.get("start_disc") or {}
        reach, within = rec.get("ore_reachable") or {}, rec.get("ore_150") or {}
        if not isinstance(disc.get("sea"), bool) or set(reach) != set(SC_ORES) or set(within) != set(SC_ORES):
            fails.append(f"{label}: no start disc sea or ore record (fail closed)")
            continue
        for o in SC_ORES:
            total += 1
            if not within[o]:
                fails.append(f"{label}: no {o} within {SC_START_R} tiles of the spawn")
            elif not reach[o]:
                fails.append(f"{label}: {o} {within[o]} tiles within {SC_START_R}, none reachable on foot from the "
                             f"spawn")
            want = SC_ORE_SHARE * vanilla.get(o, 0)
            if reach[o] < want or not reach[o]:
                under.append({"check": f"{label} {o}", "reachable": int(reach[o]), "within_150": int(within[o]),
                              "vanilla": int(vanilla.get(o, 0)), "sea": disc["sea"],
                              "coarse_min": disc.get("coarse_min")})
                if not disc["sea"]:
                    fails.append(f"{label}: {o} {reach[o]} tiles reachable on foot within {SC_START_R}, under half of "
                                 f"vanilla's {vanilla.get(o)}, at a start whose disc holds no sea by tn_land_coarse "
                                 f"(least {disc.get('coarse_min')})")
    allowed = int(math.floor(rate * total + 1e-9)) if rate is not None else None
    if rate is not None and len(under) > allowed:
        fails.append(f"{len(under)} of {total} ore checks under half of vanilla's tiles, more than {rate * 100:g} "
                     f"percent ({allowed}): {', '.join(u['check'] for u in under)}")
    summary = {"checks": total, "under_half": under, "allowed": allowed,
               "rate": round(len(under) / total, 5) if total else None}
    return summary, fails


def sc_ore_text(summary):
    """The suite report's line for T7 (b)'s ore bar: every check under half named."""
    under = summary.get("under_half") or []
    names = "; ".join(f"{u['check']} {u['reachable']} of vanilla's {u['vanilla']} "
                      f"({'sea' if u['sea'] else 'NO SEA'} in the start disc)" for u in under)
    lim = f", at most {summary['allowed']} allowed" if summary.get("allowed") is not None else ""
    return f"ore under half {len(under)} of {summary.get('checks')} checks{lim}" + (f": {names}" if names else "")


def t7_ore_controls():
    """Controls for T7 (b)'s ore bar: the sweep's verdict fails one check under half at a start whose
    disc holds no sea, fails checks under half over SC_ORE_RATE at starts by the sea, fails an ore
    missing within 150 tiles, fails a record without its disc's sea, and passes the allowed count by
    the sea (so the bar is neither always nor never failing)."""
    vanilla = {"iron-ore": 600, "copper-ore": 400, "coal": 240, "stone": 250}
    ok = {o: v for o, v in vanilla.items()}

    def recs(n, sea=True):
        return {f"c{i} scale 1": {"ore_150": dict(ok), "ore_reachable": dict(ok),
                                  "start_disc": {"sea": sea, "coarse_min": -3.0 if sea else 4.0}} for i in range(n)}

    out = {}
    base = recs(123)
    s, f = sc_ore_verdict(base, vanilla, SC_ORE_RATE)
    out["T7 ore: a clean sweep passes"] = (not f and s["checks"] == 492 and s["allowed"] == 7, str(f[:1]))
    inland = recs(123)
    inland["c0 scale 1"]["start_disc"] = {"sea": False, "coarse_min": 4.0}
    inland["c0 scale 1"]["ore_reachable"]["iron-ore"] = 100
    s, f = sc_ore_verdict(inland, vanilla, SC_ORE_RATE)
    out["T7 ore: one check under half at a start whose disc holds no sea fails"] = (
        len(f) == 1 and "no sea" in f[0] and len(s["under_half"]) == 1, str(f[:1]))
    at7 = recs(123)
    for i in range(7):
        at7[f"c{i} scale 1"]["ore_reachable"]["copper-ore"] = 150
    s, f = sc_ore_verdict(at7, vanilla, SC_ORE_RATE)
    out["T7 ore: 7 of 492 checks under half by the sea pass"] = (not f and len(s["under_half"]) == 7, str(f[:1]))
    over = recs(123)
    for i in range(8):
        over[f"c{i} scale 1"]["ore_reachable"]["copper-ore"] = 150
    s, f = sc_ore_verdict(over, vanilla, SC_ORE_RATE)
    out["T7 ore: 8 of 492 checks under half by the sea (over 1.5 percent) fail"] = (
        len(f) == 1 and "more than 1.5 percent" in f[0] and all(f"c{i} scale 1 copper-ore" in f[0] for i in range(8)),
        str(f[:1]))
    missing = recs(123)
    missing["c3 scale 1"]["ore_150"]["stone"] = 0
    missing["c3 scale 1"]["ore_reachable"]["stone"] = 0
    s, f = sc_ore_verdict(missing, vanilla, SC_ORE_RATE)
    out["T7 ore: an ore missing within 150 tiles fails"] = (any("no stone within" in x for x in f), str(f[:1]))
    blocked = recs(1)
    blocked["c0 scale 1"]["ore_reachable"]["coal"] = 0
    s, f = sc_ore_verdict(blocked, vanilla)
    out["T7 ore: an ore none of whose tiles is reachable on foot fails"] = (
        any("none reachable" in x for x in f), str(f[:1]))
    bare = recs(2)
    del bare["c1 scale 1"]["start_disc"]
    s, f = sc_ore_verdict(bare, vanilla, SC_ORE_RATE)
    out["T7 ore: a record without its start disc's sea fails closed"] = (any("fail closed" in x for x in f), str(f[:1]))
    return out


def sc_t7_eval(cfg, mk, g, run_dir, m0_ore, seed, number, scale, label):
    """T7 (b) and (c) and T18 (a) on one T7 scenario. Returns (record, failures). The starting ore is
    recorded here (its tiles within 150, those reachable on foot, the start disc's sea by
    tn_land_coarse) and judged over the records by sc_ore_verdict, T7 (b)'s rate bar."""
    import numpy as np
    import dump_render as dr
    import nav
    import oracle
    d = read_dump(run_dir, "t7")
    fails, rec = [], {}
    m = (d.get("measure") or [{}])[0]
    area = (d.get("areas") or [None])[0]
    if not area or not m:
        return rec, [f"{label}: the probe wrote no area or measure"]
    a = area["area"]
    names, idx = dr.decode_tiles(area)
    layers = dr.tile_layers(area)
    blocking = np.array([("water_tile" in layers.get(n, set()) and "player" in layers.get(n, set())) for n in names])
    W = blocking[idx]
    ys, xs = np.mgrid[0:W.shape[0], 0:W.shape[1]]
    tx, ty = xs + a["x0"], ys + a["y0"]
    dist = np.hypot(tx + 0.5, ty + 0.5)
    spawn = (-a["y0"], -a["x0"])
    rec["spawn_tile"] = names[idx[spawn]]
    if W[spawn]:
        fails.append(f"{label}: the spawn tile is {rec['spawn_tile']}, player-blocking water")
    wet = int((W & (dist <= SC_DRY_R)).sum())
    rec["water_within_12"] = wet
    rec["nearest_water"] = round(float(dist[W].min()), 1) if W.any() else None
    if wet:
        fails.append(f"{label}: {wet} player-blocking water tiles within {SC_DRY_R} tiles of the spawn")
    # the start lake: its own footprint (the lake expression below 0), the water tiles inside it
    bits, gmeta = sc_grid_bits(d)
    if bits is None:
        fails.append(f"{label}: the spawn lake expression was not recognised on the grid")
    else:
        fy, fx = np.nonzero(bits == 1)
        fx, fy = fx * int(gmeta["step"]) + int(gmeta["x0"]), fy * int(gmeta["step"]) + int(gmeta["y0"])
        inside = (fx >= a["x0"]) & (fx < a["x0"] + a["w"]) & (fy >= a["y0"]) & (fy < a["y0"] + a["h"])
        wet_fp = int(W[fy[inside] - a["y0"], fx[inside] - a["x0"]].sum())
        cen = (float(fx.mean()) + 0.5, float(fy.mean()) + 0.5) if fx.size else (0.0, 0.0)
        cdist = round(math.hypot(*cen), 1)
        rec["lake"] = {"footprint_tiles": int(fx.size), "water_tiles": wet_fp, "centre_distance": cdist}
        if wet_fp < SC_LAKE_MIN:
            fails.append(f"{label}: the start lake's footprint holds {wet_fp} water tiles (want {SC_LAKE_MIN} or more)")
        if not (SC_LAKE_CENTRE[0] <= cdist <= SC_LAKE_CENTRE[1]):
            fails.append(f"{label}: the start lake is centred {cdist} tiles from the spawn (want {SC_LAKE_CENTRE})")
    # starting ore: at least half of vanilla's tiles per ore within 150, and that many reachable on foot
    free = nav.walk_free(area, 1)
    lab, _ = nav.labels(free)
    comp = lab[spawn]
    ent_names = [e["name"] for e in area.get("entity_names") or []]
    ore_reach = {o: 0 for o in SC_ORES}
    ore_all = {o: 0 for o in SC_ORES}
    for e in area.get("entities") or []:
        n = ent_names[e[0]]
        if n not in ore_reach or math.hypot(e[1], e[2]) > SC_START_R:
            continue
        ore_all[n] += 1
        r_, c_ = int(math.floor(e[2])) - a["y0"], int(math.floor(e[1])) - a["x0"]
        if 0 <= r_ < lab.shape[0] and 0 <= c_ < lab.shape[1] and comp >= 0 and lab[r_, c_] == comp:
            ore_reach[n] += 1
    rec["ore_150"] = ore_all
    rec["ore_reachable"] = ore_reach
    # the lake reached on foot: a walkable tile next to a footprint water tile in the spawn's component
    if bits is not None and comp >= 0:
        fp = np.zeros(W.shape, bool)
        fp[fy[inside] - a["y0"], fx[inside] - a["x0"]] = True
        fpw = fp & W
        near = np.zeros_like(fpw)
        near[1:, :] |= fpw[:-1, :]
        near[:-1, :] |= fpw[1:, :]
        near[:, 1:] |= fpw[:, :-1]
        near[:, :-1] |= fpw[:, 1:]
        shore = near & free & (lab == comp)
        rec["lake_shore_reachable"] = int(shore.sum())
        if not shore.any():
            fails.append(f"{label}: no walkable tile beside the start lake is reachable on foot from the spawn")
    # enemies within 150: none
    by = (m.get("enemies") or {}).get("by_type") or {}
    rec["enemies_150"] = {t: int(by.get(t) or 0) for t in SC_ENEMY_TYPES}
    if any(rec["enemies_150"].values()):
        fails.append(f"{label}: enemies within {SC_START_R} tiles {rec['enemies_150']}")
    # (c): the index read back at (0, 0) is the model's (or the setting's), and a city of the table
    pv = point_values(d).get((0, 0), {})
    got = pv.get(g["city_index"])
    want_idx = oracle.resolved_city(cfg, mk, seed, number)
    n_cities = len(sc_values(cfg, g)) - 1
    rec["city_index"] = got
    if got != want_idx:
        fails.append(f"{label}: city index {got} read back at (0, 0); the model gives {want_idx}")
    if not (isinstance(got, (int, float)) and 1 <= got <= n_cities and float(got).is_integer()):
        fails.append(f"{label}: city index {got} is no city of the table (1 to {n_cities})")
    if not isinstance(pv.get(cfg["keys"]["map"]), (int, float)) or pv.get(cfg["keys"]["map"]) <= 0:
        fails.append(f"{label}: {cfg['keys']['map']} reads {pv.get(cfg['keys']['map'])} at (0, 0): Earth not active (G5)")
    # T7 (b)'s rate bar: the start disc's sea by tn_land_coarse (the model's city), read offline over
    # every tile of the disc and held to the game's field at the spawn and on the disc's rim
    lc = cfg["keys"]["land_coarse"]
    allv = point_values(d)
    probe = [allv.get(p, {}).get(lc) for p in SC_COARSE_PROBES]
    off = [float(v) for v in sc_coarse_at(cfg, mk, want_idx, scale, [p[0] for p in SC_COARSE_PROBES],
                                          [p[1] for p in SC_COARSE_PROBES])]
    bad = [(p, v, round(o, 4)) for p, v, o in zip(SC_COARSE_PROBES, probe, off)
           if not isinstance(v, (int, float)) or isinstance(v, bool) or abs(float(v) - o) > SC_COARSE_TOL]
    dmin = sc_start_disc_min(cfg, mk, want_idx, scale)
    errs = [abs(float(v) - o) for v, o in zip(probe, off) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    rec["start_disc"] = {"coarse_min": round(dmin, 3), "sea": dmin < 0,
                         "probe_max_error": round(max(errs), 6) if errs else None}
    if bad:
        rec["start_disc"].pop("sea")
        fails.append(f"{label}: the game's {lc} differs from the offline coarse field by more than {SC_COARSE_TOL} "
                     f"at {bad[:3]} (point, game, offline), so the start disc's sea is unknown")
    # T18 (a): the start message, logged once, and freeplay's intro carrying it
    if isinstance(got, (int, float)) and 1 <= got <= n_cities:
        city = oracle.city_table()[mk]["cities"][sc_values(cfg, g)[int(got)]]
        mp = cfg["maps"][mk]
        line = render_message(cfg, "start", city["name"], mp["width_px"] * int(scale), mp["height_px"] * int(scale))
        n_log = count_lines(log_text(run_dir), line)
        rec["start_message"] = [line, n_log]
        if n_log != 1:
            fails.append(f"{label}: the start message {line!r} is logged {n_log} times (want once)")
        intro = ((d.get("intro") or {}).get("message"))
        want_key = f"{cfg['messages']['section']}.{cfg['messages']['keys']['start']}"
        last = intro[-1] if isinstance(intro, list) and intro else None
        ok = (isinstance(last, list) and last[:2] == [want_key, city["name"]] and
              [int(v) for v in last[2:4]] == [mp["width_px"] * int(scale), mp["height_px"] * int(scale)])
        rec["intro"] = bool(ok)
        if not ok:
            fails.append(f"{label}: freeplay's intro does not end with the start message: {str(intro)[:200]}")
    return rec, fails


def sc_scenarios(ctx, jobs):
    """Run T7 scenarios [(prepare, args, out)] in up to PAR_MAX workers; each job names its
    own worker's instance and modset."""
    lanes = {}
    for prep, args, out, lane in jobs:
        lanes.setdefault(lane, []).append((prep, args, out, 900))
    run_lanes(ctx, list(lanes.values()))
    return [j[2] for j in jobs]


def sc_lane_modsets(ctx, mods, tag, n=PAR_MAX):
    """n probe modsets (M1 plus the dump probe) for parallel T7 workers."""
    return [sc_city_modset(ctx, mods, f"{tag}{i + 1}") for i in range(n)]


# -- FG rows

def row_sc_dump_facts(ctx, mods, sec6, row, cache):
    """T16 (FG) and the city fold's static facts on the M1 dump: every body this milestone
    changes that europe-coast registered (the elevation composition, the start mask, the coordinate
    chain the city offset enters) is a new versioned name, registered, that the Europe preset names,
    while the older versions stay defined, registered, unnamed by any preset and without the Map
    type fields, and version 1's offset fallbacks still hold their registered 0; the preset bakes
    the distance redirect, the default city number, the city fold's names and the spawn lake and
    bias keys; the city table is bound to its sources (every city's pixel the reference JSON's, its
    offset the oracle's tile at scales 1, 3 and 6; the setting's values random plus the approvals'
    kept cities, in order, none removed); the generated spawn bearings re-emit byte for byte; and
    the float32 model reproduces S7's five game picks."""
    import oracle
    cfg = mods.cfg
    d1 = ctx.shared.get("dump_m1")
    if d1 is None:
        row.fails.append("no M1 dump")
        return
    pname, mk, g = first_preset(cfg)
    if not g.get("spawn"):
        row.fails.append(f"config.lua gives {mk}'s newest geography version no spawn record")
        return
    fz = json.loads((TESTS / "frozen.json").read_text(encoding="utf-8")).get("bodies") or {}
    ne = d1.get("noise-expression") or {}
    pen = preset_pen(d1, pname)
    K = cfg["keys"]
    versions = tnconfig.geography_versions(cfg)[mk]
    masks = [m["name"] for m in tnconfig.start_masks(cfg)]
    pairs = (("elevation", g["entry"], [v["entry"] for v in versions[:-1]]),
             ("start mask", g["start_mask"], [m for m in masks if m != g["start_mask"]]),
             ("chain", g["gx"], [v["gx"] for v in versions[:-1]]))
    named = {v for p in (d1.get("map-gen-presets") or {}).get("default", {}).values() if isinstance(p, dict)
             for v in ((p.get("basic_settings") or {}).get("property_expression_names") or {}).values()}
    for what, newest, older in pairs:
        if newest not in fz:
            row.fails.append(f"the {what} the preset names, {newest}, is not registered in tests/frozen.json")
        for o in older:
            if o not in ne:
                row.fails.append(f"the older {what} {o} is no longer defined (old saves name it)")
            if o not in fz:
                row.fails.append(f"the older {what} {o} is not registered")
            if o in named:
                row.fails.append(f"a preset still names the older {what} {o}")
            if (ne.get(o) or {}).get("intended_property"):
                row.fails.append(f"the older {what} {o} still carries intended_property")
    if pen.get(K["elevation"]) != g["entry"] or pen.get(K["start_mask"]) != g["start_mask"]:
        row.fails.append(f"the preset names {pen.get(K['elevation'])} and {pen.get(K['start_mask'])}, not the newest "
                         f"{g['entry']} and {g['start_mask']}")
    # every older version's own city offset names keep the frozen constants they were registered with
    fmt = cfg["number_format"]
    for v in versions[:-1]:
        for name, value in zip((v["cx"], v["cy"]), v["city_offset"]):
            want_text = fmt % value if isinstance(value, int) else value
            got_text = (ne.get(name) or {}).get("expression")
            if got_text != want_text:
                row.fails.append(f"the older version's offset fallback {name} reads {got_text!r}, registered as "
                                 f"{want_text!r}: a later version re-pointed it")
    want = expected_pen(cfg, mk, int(cfg["settings"]["scale"]["default_value"]))
    for k in (K["distance"], g["city"], g["cx"], g["cy"], K["spawn_lake"], K["spawn_bias"]):
        if pen.get(k) != want.get(k):
            row.fails.append(f"the preset bakes {k} = {pen.get(k)!r}, want {want.get(k)!r}")
    for n in (g["city_index"], g["inland_lakes"], *g["city_offset"], g["spawn_lake"], g["spawn_bias"],
              g["start_land"], g["distance"]):
        if n not in ne:
            row.fails.append(f"the dump lacks {n}")
    # the generated spawn bearings re-emit byte for byte from the raster and the city table (T16)
    import build_spawn
    row.fails += [f"spawn bearings: {x}" for x in build_spawn.check(mk)]
    checks = oracle.spawn_selftest(cfg)
    bad = [c for c in checks if not c[1]]
    row.fails += [f"spawn model and city table: {c[0]} ({c[2]})" for c in bad[:8]]
    row.detail = (f"{g['entry']}, {g['gx']} and {g['start_mask']} named and registered, "
                  f"{[o for _, _, olds in pairs for o in olds]} defined, registered and unnamed, the older offset "
                  f"fallbacks unmoved; the preset bakes distance, the city number, the fold and the spawn lake and "
                  f"bias keys; the spawn bearings re-emit; {len(checks) - len(bad)} of {len(checks)} model and "
                  f"city-table checks")


def t14_walk(d1, d0, cfg):
    """T14's static part on a dump pair: (references, planet differences). An Earth noise name may be
    referenced only by the Earth presets, the Earth bodies themselves (the Map type entries and their
    fallbacks among them) and, from the hook milestones on, gated Nauvis entries; no planet prototype may
    differ from M0's."""
    earth = set(earth_bodies(d1, cfg))
    presets = set(earth_presets(cfg))
    refs = []

    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for k, v in o.items():
                yield str(k)
                yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
    for t, protos in d1.items():
        if not isinstance(protos, dict):
            continue
        for n, p in protos.items():
            if t in NOISE_TYPES and n in earth:
                continue
            if t == "map-gen-presets":
                for pn, pv in (p.items() if isinstance(p, dict) else []):
                    if pn in presets:
                        continue
                    hit = {tok for s in strings(pv) for tok in expr_refs(s) if tok in earth}
                    if hit:
                        refs.append(f"preset {pn} references {sorted(hit)[:3]}")
                continue
            hit = {tok for s in strings(p) for tok in expr_refs(s) if tok in earth}
            if hit:
                refs.append(f"{t} {n} references {sorted(hit)[:3]}")
    planets = []
    p0, p1 = d0.get("planet") or {}, d1.get("planet") or {}
    for n in sorted(set(p0) | set(p1)):
        if p0.get(n) != p1.get(n):
            planets.append(n)
    return refs, planets


def row_t14_walker(ctx, mods, sec6, row, cache):
    """T14 (FG static; D33): in the M1 dump every Earth expression is referenced only from the Earth
    presets, the Map type entries and their fallbacks and other Earth expressions (gated Nauvis
    entries join with the hook milestones), and no planet prototype differs from M0's. Positive controls:
    a vanilla expression and a planet that name an Earth body, and a changed planet, are found."""
    cfg = mods.cfg
    d0, d1 = ctx.shared.get("dump_m0"), ctx.shared.get("dump_m1")
    if d0 is None or d1 is None:
        row.fails.append("no M0 and M1 dumps")
        return
    refs, planets = t14_walk(d1, d0, cfg)
    row.fails += [f"T14: {r}" for r in refs[:10]]
    row.fails += [f"T14: planet {p} differs from M0's" for p in planets]
    _, _, g = first_preset(cfg)
    fx = json.loads(json.dumps(d1))
    fx.setdefault("noise-expression", {})["ea_t14_fixture"] = {"type": "noise-expression", "name": "ea_t14_fixture",
                                                               "expression": f"1 + {g['entry']}"}
    nauvis = (fx.get("planet") or {}).get("nauvis")
    if nauvis is not None:
        fx["planet"]["nauvis"] = dict(nauvis, map_seed_offset=12345)
    r2, p2 = t14_walk(fx, d0, cfg)
    ctl = {"a vanilla-named expression reading an Earth body is found": any("ea_t14_fixture" in r for r in r2),
           "a changed planet is found": nauvis is None or "nauvis" in p2}
    for k, ok in ctl.items():
        if not ok:
            row.fails.append(f"T14 positive control did not behave: {k}")
    n_earth = len(earth_bodies(d1, cfg))
    row.detail = (f"{n_earth} Earth bodies referenced only by Earth presets and Earth bodies; "
                  f"{len(d1.get('planet') or {})} planet prototypes equal M0's; {sum(ctl.values())} of {len(ctl)} "
                  f"controls behaved")


def row_t15b_geo(ctx, mods, sec6, row, cache):
    """T15 (FG; the T15b block keeps its geo position through the shift): under the runner world's
    spawn offset the scale 6 block's geo corner lies within one chunk of Phase 4's (London-relative,
    fixed in geo tiles) and the scale 1 block holds that block's pixels, clear of the start area; a
    positive control places the same block for another spawn city and finds other world chunks but the
    same geo corner."""
    import earthgeo as eg
    import oracle
    cfg = mods.cfg
    mk, g = sc_map(cfg)
    mref = eg.MapRef(mk)
    O = oracle.load_oracle(mk, TESTS / "oracle")
    lon = next(p for p in O["places"] if p["id"] == P4_ANCHOR)
    lx, ly = (int(v) for v in oracle.place_tile(mref, lon, str(P4_SCALE)))
    anchor = (lx + P4_BLOCK_CENTRE[0] - 256, ly + P4_BLOCK_CENTRE[1] - 256)   # geo tiles at scale 6
    pos = europe_positions(cfg, mref)
    off6 = runner_offset(cfg, mk, P4_SCALE)
    bx, by = pos["save_block"]
    geo = (bx * 32 + off6[0], by * 32 + off6[1])
    dx, dy = geo[0] - anchor[0], geo[1] - anchor[1]
    if not (-32 < dx <= 0 and -32 < dy <= 0):
        row.fails.append(f"the scale 6 block's geo corner {geo} is {dx, dy} tiles from Phase 4's {anchor} (want within "
                         f"one chunk, snapped down)")
    for s, land in pos["block_land"].items():
        if not (BLOCK_LAND[0] <= land <= BLOCK_LAND[1]):
            row.fails.append(f"scale {s}: the block holds {land} reference land (want {BLOCK_LAND})")
    # positive control: another spawn city moves the world chunks, never the geo corner
    other = "london" if sc_values(cfg, g)[oracle.resolved_city(cfg, mk, SEED, 0)] != "london" else "oslo"
    o2 = runner_offset(cfg, mk, P4_SCALE, city=other)
    w2 = ((anchor[0] - o2[0]) // 32, (anchor[1] - o2[1]) // 32)
    geo2 = (w2[0] * 32 + o2[0], w2[1] * 32 + o2[1])
    moved = w2 != (bx, by) and abs(geo2[0] - geo[0]) < 32 and abs(geo2[1] - geo[1]) < 32
    if not moved:
        row.fails.append(f"positive control: at {other} the block's chunks {w2} and geo corner {geo2} (against {bx, by} "
                         f"and {geo}) do not show a shift that keeps the geo position")
    row.detail = (f"scale 6 block chunks {bx, by} (geo corner {geo}, Phase 4's {anchor}, offset {off6}); land "
                  f"{pos['block_land']}; at {other} the chunks move to {w2}, the geo corner stays")


def row_t7_random(ctx, mods, sec6, row, cache):
    """T7 (b), (c) and T18 (a) (FG; Europe random spawn; seed 1000; scale 6; M1): the spawn tile land, no
    player-blocking water within 12 tiles, the start lake's own footprint holding 1,000 water tiles or
    more centred 40 to 110 tiles out, iron, copper, coal and stone each within 150 tiles and reachable
    on foot, with at least half of vanilla's tiles at the same seed unless the start disc holds sea by
    tn_land_coarse (then the check is named and the sweep's rate bar counts it), the lake's shore
    reachable, 0 spawners, worms and units within 150; the index read back at (0, 0) equal to the
    float32 model; the start
    message logged once and ending freeplay's intro; and a default world in the same modset gets no
    Earth message (G6)."""
    cfg = mods.cfg
    mk, g = sc_map(cfg)
    ms = sc_lane_modsets(ctx, mods, "m1sc", 2)
    m0p = sc_m0_probe(ctx, mods)
    mgs = sc_mgs(ctx, cfg, mk, 6, "random", "t7-random-s6")
    key, newest = common_key(ctx, "t7_random", {"ms": [mods.manifest(m) for m in ms + [m0p]],
                                                  "dump": ctx.shared.get("dump_m1_sha"), "mgs": mgs.read_text()})

    def live():
        jobs = [(sc_t7_settings(ctx, ms[0], lane_instance(ctx, 0), cfg, g),
                 scenario_args(lane_instance(ctx, 0), ms[0], 3, SEED, mgs), ctx.out / "t7-random-s6", 0),
                (sc_m0_settings(ctx, m0p, lane_instance(ctx, 1)),
                 scenario_args(lane_instance(ctx, 1), m0p, 3, SEED), ctx.out / "t7-m0", 1),
                (sc_t7_settings(ctx, ms[1], lane_instance(ctx, 2), cfg, g),
                 scenario_args(lane_instance(ctx, 2), ms[1], 3, SEED), ctx.out / "t7-default-world", 2)]
        return sc_scenarios(ctx, jobs)

    def derive(dirs):
        fails = []
        for d in dirs:
            fails += g1(d) + g3(d)
        m0 = sc_m0_ore(dirs[1])
        rec, f = sc_t7_eval(cfg, mk, g, dirs[0], m0, SEED, 0, 6, "random seed 1000 scale 6")
        fails += f
        ore, f = sc_ore_verdict({"random seed 1000 scale 6": rec}, m0)
        rec["ore_bar"] = ore
        fails += f
        prefix = message_prefix(cfg, "start")
        n_default = count_lines(log_text(dirs[2]), prefix)
        dd = read_dump(dirs[2], "t7")
        intro_default = (dd.get("intro") or {}).get("message")
        if n_default:
            fails.append(f"the default world logs the start message {n_default} times (want none)")
        if intro_default:
            fails.append(f"the default world's freeplay intro was set: {str(intro_default)[:120]}")
        rec["m0_ore"] = m0
        rec["default_world_messages"] = n_default
        return rec, fails, (f"random at seed 1000, scale 6: city {rec.get('city_index')} (the model's), spawn "
                            f"{rec.get('spawn_tile')}, water within 12 tiles {rec.get('water_within_12')}, lake "
                            f"{rec.get('lake')}, ore {rec.get('ore_reachable')} reachable against vanilla's {m0} "
                            f"({sc_ore_text(ore)}; start disc {rec.get('start_disc')}), enemies "
                            f"{rec.get('enemies_150')}; start message once, intro set {rec.get('intro')}; none on a "
                            f"default world")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


def row_t13_maptype_city(ctx, mods, sec6, row, cache):
    """T13 (FG; the Map type route; Europe; scale 6; seed 1000): an elevation-only world reads back the
    same city index at (0, 0) as the preset world under the same startup settings, for random and for
    one named city (London), and its player-blocking water mask around the spawn, the start lake and
    land guarantee included, equals the preset world's (256 px previews at the spawn)."""
    cfg = mods.cfg
    pname, mk, g = first_preset(cfg)
    mt = maptype_mgs(ctx, cfg)
    msets = {"random": sc_city_modset(ctx, mods, "m1scmr"), "london": sc_city_modset(ctx, mods, "m1scml", city="london")}
    key, newest = common_key(ctx, "t13_maptype_city", {"ms": {k: mods.manifest(v) for k, v in msets.items()},
                                                         "dump": ctx.shared.get("dump_m1_sha")})

    def live():
        lanes, dirs = [], []
        for i, (city, ms) in enumerate(msets.items()):
            inst = lane_instance(ctx, i)
            pts = dump_settings(ctx, ms, inst, label="t13c", points="0,0", names=g["city_index"])
            save = ctx.out / f"t13c-{city}-create-preset" / "p.zip"
            # the maptype world in one scenario; the preset world created with --preset (fh.py's `--`
            # extras reach the benchmark step only) and loaded with the probe, as T11 does
            jobs = [(pts, scenario_args(inst, ms, 3, SEED, mt), ctx.out / f"t13c-{city}-maptype", 900),
                    (None, create_args(inst, ms, save, preset=pname), save.parent, 900),
                    (pts, scenario_args(inst, ms, 3, save=save), ctx.out / f"t13c-{city}-preset", 900),
                    (None, preview_args(inst, ms, 256, mgs=mt), ctx.out / f"t13c-{city}-maptype-preview", 600),
                    (None, preview_args(inst, ms, 256, preset=pname), ctx.out / f"t13c-{city}-preset-preview", 600)]
            dirs += [j[2] for j in jobs]
            lanes.append(jobs)
        run_lanes(ctx, lanes)
        return dirs

    def derive(dirs):
        import t1_metrics as t1
        fails, meas = [], {}
        for d in dirs:
            fails += g1(d) + g3(d)
        ws = t1.water_colour_set(blocking_water_colours(ctx.shared["dump_m1"]))
        for i, city in enumerate(("random", "london")):
            mt_s, _, pr_s, mt_p, pr_p = dirs[5 * i: 5 * i + 5]
            a = point_values(read_dump(mt_s, "t13c")).get((0, 0), {}).get(g["city_index"])
            b = point_values(read_dump(pr_s, "t13c")).get((0, 0), {}).get(g["city_index"])
            wa = ~t1.preview_land(Path(mt_p) / f"{SEED}.png", ws)
            wb = ~t1.preview_land(Path(pr_p) / f"{SEED}.png", ws)
            diff = int((wa != wb).sum())
            meas[city] = {"index_maptype": a, "index_preset": b, "water_px": int(wb.sum()), "water_diff": diff}
            if a is None or a != b:
                fails.append(f"{city}: the elevation-only world reads city {a} at (0, 0), the preset world {b}")
            if diff:
                fails.append(f"{city}: the elevation-only world's water mask at the spawn differs in {diff} pixels")
            if not wb.any():
                fails.append(f"{city}: no water in the spawn preview: the start lake is missing")
        if meas.get("random", {}).get("index_preset") == meas.get("london", {}).get("index_preset"):
            fails.append("random and London resolve to one city: the setting did not reach the worlds (G6)")
        return meas, fails, (f"elevation-only and preset worlds agree: random city {meas.get('random', {}).get('index_preset')}, "
                             f"London {meas.get('london', {}).get('index_preset')}; spawn water masks equal "
                             f"({meas.get('random', {}).get('water_px')} and {meas.get('london', {}).get('water_px')} "
                             f"water pixels)")

    cached_or_live(ctx, row, cache, key, newest, live, derive)


ROW_FUNCS.update({
    "sc_dump_facts": row_sc_dump_facts, "t14_walker": row_t14_walker, "t15b_geo": row_t15b_geo,
    "t7_random": row_t7_random, "t13_maptype_city": row_t13_maptype_city,
})


# -- suite checks

def sc_hotspot_margins(cfg, mk):
    """T7 (a) against the approvals table: each kept city's map distance (reference pixels times
    km_per_px) to every adopted hotspot centre of the map, against r + j + the city margin. Returns
    ({city: closest margin in km}, failures)."""
    import oracle
    appr = json.loads((REPO / "data-src" / "approvals" / "approvals-data.json").read_text(encoding="utf-8"))
    rules = appr["rules"]
    _, g = sc_map(cfg)
    values, px = oracle.city_fold(cfg, mk)
    out, fails = {}, []
    for v, (c, r) in zip(values[1:], px):
        best = None
        for h in appr["hotspots"]:
            if not (h.get("adopted") or {}).get(mk):
                continue
            hp = ((h.get("surface") or {}).get(mk) or {}).get("pixel")
            if not hp:
                continue
            km = math.hypot(c - hp[0], r - hp[1]) * rules["km_per_px"]
            need = h["radius_km"] + h["jitter_km"] + rules[SC_HOTSPOT_MARGIN_KM]
            slack = km - need
            if best is None or slack < best[0]:
                best = (round(slack, 1), h["id"])
            if km <= need:
                fails.append(f"{v}: {round(km, 1)} map km from {h['id']}, inside its margin {need} km")
        out[v] = best
    return out, fails


def sc_suite_checks(ctx, mods, sec6, checks, d, limits, ctl, timing, sig):
    cfg = mods.cfg
    mk, g = sc_map(cfg)
    values = sc_values(cfg, g)

    def key(name, extra=None):
        k, _ = common_key(ctx, f"ss-{name}", extra)
        return k

    def m0_ore_run(deadline, label="sc-m0"):
        m0p = sc_m0_probe(ctx, mods)
        inst = lane_instance(ctx, PAR_MAX - 1)
        sc_m0_settings(ctx, m0p, inst)()
        return ctx.fh(scenario_args(inst, m0p, 3, SEED), ctx.out / label).out

    def t7_jobs(cities_scales, tag, seed=SEED):
        lanes = sc_lane_modsets(ctx, mods, tag, PAR_MAX - 1)
        jobs = []
        for i, (city, s) in enumerate(cities_scales):
            ln = i % len(lanes)
            inst = lane_instance(ctx, ln)
            mgs = sc_mgs(ctx, cfg, mk, s, city, f"{tag}-{city}-s{s}-{seed}")
            jobs.append((sc_t7_settings(ctx, lanes[ln], inst, cfg, g), scenario_args(inst, lanes[ln], 3, seed, mgs),
                         ctx.out / f"{tag}-{city}-s{s}-{seed}", ln))
        return jobs

    def t7_derive(cities_scales, tag, dirs, seed=SEED, rate=None):
        """Every scenario's T7 record, then T7 (b)'s ore bar over them (sc_ore_verdict; the rate only
        over the sweep, whose seed-1000 checks the decision counts)."""
        fails, meas = [], {}
        m0 = sc_m0_ore(dirs[-1])
        for d_ in dirs:
            fails += g1(d_) + g3(d_)
        recs = {}
        for (city, s), d_ in zip(cities_scales, dirs[:-1]):
            number = values.index(city)
            rec, f = sc_t7_eval(cfg, mk, g, d_, m0, seed, number, s, f"{city} scale {s}")
            meas[f"{city}-s{s}"] = rec
            recs[f"{city} scale {s}"] = rec
            fails += f
        meas["m0_ore"] = m0
        ore, f = sc_ore_verdict(recs, m0, rate)
        meas["ore_bar"] = ore
        fails += f
        return meas, fails

    # T7 (b) on the coastal and low-lying sample at scale 1 (FEAS-06), before the full sweep; its checks
    # recur in the sweep, which judges the rate
    coastal = [(c, 1) for c in SC_COASTAL]

    def coastal_run(deadline):
        dirs = sc_scenarios(ctx, t7_jobs(coastal, "t7c"))
        return dirs + [m0_ore_run(deadline, "t7c-m0")]

    checks["t7_coastal"] = SuiteCheck("t7_coastal", lambda: key("t7_coastal", {"cities": coastal}), coastal_run,
                                      lambda dirs: (lambda m, f: (m, f, f"{len(coastal)} coastal and low-lying cities "
                                                                       f"at scale 1: {len(f)} failures; "
                                                                       f"{sc_ore_text(m['ore_bar'])}"))(
                                          *t7_derive(coastal, "t7c", dirs)))

    # T7 (a) and (b): every city plus random at scales 1, 3 and 6
    sweep = [(c, s) for s in SC_SCALES for c in values]

    def sweep_run(deadline):
        dirs = sc_scenarios(ctx, t7_jobs(sweep, "t7s"))
        return dirs + [m0_ore_run(deadline, "t7s-m0")]

    def sweep_derive(dirs):
        meas, fails = t7_derive(sweep, "t7s", dirs, rate=SC_ORE_RATE)
        margins, f = sc_hotspot_margins(cfg, mk)
        fails += f
        meas["hotspot_slack_km"] = margins
        worst = min((v for v in margins.values() if v), default=None)
        # the bar's own controls (a no-sea failure and a rate over 1.5 percent must fail) behave
        ctl = t7_ore_controls()
        meas["ore_bar"]["controls"] = {k: ok for k, (ok, _) in ctl.items()}
        fails += [f"T7 ore bar control did not behave: {k} {d_}" for k, (ok, d_) in ctl.items() if not ok]
        return meas, fails, (f"{len(values) - 1} cities plus random at scales {list(SC_SCALES)}: {len(fails)} failures; "
                             f"{sc_ore_text(meas['ore_bar'])}; closest hotspot slack {worst} map km")

    checks["t7_sweep"] = SuiteCheck("t7_sweep", lambda: key("t7_sweep", {"sweep": sweep}), sweep_run, sweep_derive)

    # T7 (c): the read-back index equals the model at S7's five seeds, repeats on one seed, and is a
    # city of the table (no removed city exists in it)
    def seeds_run(deadline):
        lanes = sc_lane_modsets(ctx, mods, "t7r", PAR_MAX)
        jobs = []
        for i, seed in enumerate(SC_SEEDS_C + (SC_SEEDS_C[0],)):
            ln = i % PAR_MAX
            inst = lane_instance(ctx, ln)
            mgs = sc_mgs(ctx, cfg, mk, 6, "random", f"t7r-{seed}")
            jobs.append((dump_settings(ctx, lanes[ln], inst, label="t7r", points="0,0", names=g["city_index"]),
                         scenario_args(inst, lanes[ln], 3, seed, mgs), ctx.out / f"t7r-{seed}-{i}", ln))
        return sc_scenarios(ctx, jobs)

    def seeds_derive(dirs):
        import oracle
        fails, meas = [], {}
        seeds = SC_SEEDS_C + (SC_SEEDS_C[0],)
        n = len(values) - 1
        for seed, d_ in zip(seeds, dirs):
            fails += g1(d_) + g3(d_)
            got = point_values(read_dump(d_, "t7r")).get((0, 0), {}).get(g["city_index"])
            want = oracle.random_city_index(cfg, seed, n)
            meas.setdefault(str(seed), []).append(got)
            if got != want:
                fails.append(f"seed {seed}: index {got} read back, the float32 model gives {want}")
            if not (isinstance(got, (int, float)) and 1 <= got <= n):
                fails.append(f"seed {seed}: index {got} names no city of the table")
        if len(set(meas[str(SC_SEEDS_C[0])])) != 1:
            fails.append(f"seed {SC_SEEDS_C[0]} twice gave {meas[str(SC_SEEDS_C[0])]}")
        if len({tuple(v) for v in meas.values()}) < 3:
            fails.append("random gives fewer than three cities over five seeds (G6)")
        return meas, fails, f"random at {list(SC_SEEDS_C)}: {meas} (each the float32 model's; repeats)"

    checks["t7_seeds"] = SuiteCheck("t7_seeds", lambda: key("t7_seeds", {"seeds": SC_SEEDS_C}), seeds_run, seeds_derive)

    # T3: inland-lake density, lakes only where the lake expression puts them, the far field
    I = cfg["spawn"]["inland_lakes"]
    design = I["per_region"] * math.pi * (I["radius"] * (1 - I["level"])) ** 2 / (I["region"] * I["region"])

    def eligible_mask(mref):
        """Reference land at least coast_px reference pixels (rounded up) from any water pixel: where the
        coast gate lets an inland lake lie (it reads the fit, which this approximates)."""
        import numpy as np
        r = int(math.ceil(I["coast_px"]))
        land = mref.land.astype(bool)
        out = land.copy()
        pad = np.pad(land, r, constant_values=False)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                out &= pad[r + dy:r + dy + land.shape[0], r + dx:r + dx + land.shape[1]]
        return out

    def lake_blocks(scale):
        """Sampled inland blocks at a scale, (gx0, gy0, width, height) in geo tiles: at scale 6 blocks of
        SC_DENSITY_BLOCK tiles aligned to the spot regions (whole regions, so each holds its exact lake
        count) inside the extent with at least SC_DENSITY_MIN_ELIGIBLE eligible points, the first eight;
        at scale 1 no aligned block fits Europe's 2,400 x 1,704 tiles, so the one block is the whole
        extent."""
        import numpy as np
        import earthgeo as eg
        mref = eg.MapRef(mk)
        s = int(scale)
        if s == 1:
            return [(-mref.wr, -mref.hr, mref.W, mref.H)]
        elig = eligible_mask(mref)
        B = SC_DENSITY_BLOCK
        out = []
        for gy0 in range(-mref.hr * s // B * B, (mref.H - mref.hr) * s, B):
            for gx0 in range(-mref.wr * s // B * B, (mref.W - mref.wr) * s, B):
                xs = np.arange(gx0, gx0 + B, 64)
                ys = np.arange(gy0, gy0 + B, 64)
                cols, rows = xs // s + mref.wr, ys // s + mref.hr
                if cols.min() < 0 or rows.min() < 0 or cols.max() >= mref.W or rows.max() >= mref.H:
                    continue
                if float(elig[np.ix_(rows, cols)].mean()) >= SC_DENSITY_MIN_ELIGIBLE:
                    out.append((gx0, gy0, B, B))
        return out[:8]

    def square_origin(s, grid_dump=None):
        """The real-tile square's geo origin at a scale. At scale 6, the first sampled block's corner. At
        scale 1, whose one block is the whole extent: of the SC_SQUARE-tile squares on a 64-tile lattice
        from the extent's corner, inside the extent and wholly outside the start disc's lake exclusion
        (start_radii start radii of the spawn, which holds the spawn lake and the start land guarantee
        that the coast-only world neutralises), the one holding the most inland-lake points of the scale
        1 block's grid (`grid_dump`), ties to the north and then the west; None when none qualifies.
        Returns (gx0, gy0, lake points or None)."""
        import numpy as np
        import earthgeo as eg
        if int(s) != 1:
            gx0, gy0, _, _ = lake_blocks(s)[0]
            return gx0, gy0, None
        mref = eg.MapRef(mk)
        bx, by, bw, bh = lake_blocks(1)[0]
        bits, _ = sc_grid_bits(grid_dump)
        if bits is None:
            return None
        lake = bits == 1
        gxs = bx + np.arange(lake.shape[1]) * SC_DENSITY_STEP
        gys = by + np.arange(lake.shape[0]) * SC_DENSITY_STEP
        ox, oy = runner_offset(cfg, mk, 1)
        excl = I["start_radii"] * 150
        S, step = SC_SQUARE, SC_SQUARE_LATTICE
        best = None
        for sy in range(by, by + bh - S + 1, step):
            rows = (gys >= sy) & (gys < sy + S)
            for sx in range(bx, bx + bw - S + 1, step):
                qx, qy = min(max(ox, sx), sx + S - 1), min(max(oy, sy), sy + S - 1)
                if math.hypot(qx - ox, qy - oy) <= excl:
                    continue
                n = int(lake[np.ix_(rows, (gxs >= sx) & (gxs < sx + S))].sum())
                if best is None or n > best[2]:
                    best = (sx, sy, n)
        return best

    def square_jobs(s, gx0, gy0, lanes, i):
        """The real-tile square at a scale: its tiles and the inland-lake expression at every tile in the
        city world, so every inland water tile is shown to lie in a lake footprint; beside it the same
        geo square of the coast-only world (europe-coast's coast, which T1 scores), the comparator for
        water the lakes did not add."""
        off = runner_offset(cfg, mk, s)
        city = cfg["settings"][g["city_setting"]]["default_value"]
        mgs = sc_mgs(ctx, cfg, mk, s, city, f"t3l-s{s}")
        x0, y0 = gx0 - off[0], gy0 - off[1]
        S = SC_SQUARE
        ln = i % PAR_MAX
        inst = lane_instance(ctx, ln)
        jobs = [(dump_settings(ctx, lanes[ln], inst, label="t3l", areas=f"{x0},{y0},{S},{S}", types="",
                               decoratives=False, grid=f"{x0},{y0},1,{S},{S}", grid_name=g["inland_lakes"],
                               grid_threshold="0", grid_op="lt"),
                 scenario_args(inst, lanes[ln], 3, SEED, mgs), ctx.out / f"t3l-tiles-s{s}", ln)]
        ln = (i + 1) % PAR_MAX
        inst = lane_instance(ctx, ln)
        cmgs = write_mgs(ctx, f"sc-t3l-s{s}-coast", coast_only_pen(cfg, mk, expected_pen(cfg, mk, s, city)))
        jobs.append((dump_settings(ctx, lanes[ln], inst, label="t3l", areas=f"{gx0},{gy0},{S},{S}", types="",
                                   decoratives=False),
                     scenario_args(inst, lanes[ln], 3, SEED, cmgs), ctx.out / f"t3l-coast-s{s}", ln))
        return jobs, i + 2

    def lakes_run(deadline):
        lanes = sc_lane_modsets(ctx, mods, "t3l", PAR_MAX)
        jobs, i = [], 0
        for s in (1, 6):
            off = runner_offset(cfg, mk, s)
            mgs = sc_mgs(ctx, cfg, mk, s, cfg["settings"][g["city_setting"]]["default_value"], f"t3l-s{s}")
            for gx0, gy0, bw, bh in lake_blocks(s):
                ln = i % PAR_MAX
                inst = lane_instance(ctx, ln)
                nx, ny = bw // SC_DENSITY_STEP, bh // SC_DENSITY_STEP
                jobs.append((dump_settings(ctx, lanes[ln], inst, label="t3l", areas="",
                                           grid=f"{gx0 - off[0]},{gy0 - off[1]},{SC_DENSITY_STEP},{nx},{ny}",
                                           grid_name=g["inland_lakes"], grid_threshold="0", grid_op="lt"),
                             scenario_args(inst, lanes[ln], 3, SEED, mgs), ctx.out / f"t3l-s{s}-{gx0}-{gy0}", ln))
                i += 1
            # the far field with the lakes on: probes beyond each edge, in world tiles
            import earthgeo as eg
            far, _, _ = far_points(eg.MapRef(mk), s)
            ln = i % PAR_MAX
            inst = lane_instance(ctx, ln)
            pts = ";".join(f"{x - off[0]},{y - off[1]}" for x, y in far)
            jobs.append((dump_settings(ctx, lanes[ln], inst, label="t3l", points=pts, names="elevation"),
                         scenario_args(inst, lanes[ln], 3, SEED, mgs), ctx.out / f"t3l-far-s{s}", ln))
            i += 1
        # real tiles at scale 6 run beside the grids; scale 1's square is placed from its grid
        gx0, gy0, _ = square_origin(6)
        more, i = square_jobs(6, gx0, gy0, lanes, i)
        dirs = sc_scenarios(ctx, jobs + more)
        sq = square_origin(1, read_dump(dirs[0], "t3l"))
        if sq is None:
            raise GateError("T3: no scale 1 real-tile square qualifies (the scale 1 grid was not recognised, or every "
                            "square meets the start disc)")
        more, i = square_jobs(1, sq[0], sq[1], lanes, i)
        return dirs + sc_scenarios(ctx, more)

    def lakes_derive(dirs):
        import numpy as np
        import earthgeo as eg
        mref = eg.MapRef(mk)
        elig = eligible_mask(mref)
        fails, meas = [], {"design_fraction": round(design, 5), "blocks": {}}
        for d_ in dirs:
            fails += g1(d_) + g3(d_)
        k = 0
        for s in (1, 6):
            blocks = lake_blocks(s)
            off = runner_offset(cfg, mk, s)
            if not blocks:
                fails.append(f"scale {s}: no inland block qualifies")
            for gx0, gy0, bw, bh in blocks:
                bits, gm = sc_grid_bits(read_dump(dirs[k], "t3l"))
                k += 1
                if bits is None:
                    fails.append(f"scale {s} block {gx0, gy0}: the inland-lake expression was not recognised")
                    continue
                # each grid point's pixel: eligible when the coast gate lets a lake lie there and it lies
                # outside the spawn's exclusion disc (start_radii start radii at the default slider)
                gxs = np.arange(bits.shape[1]) * SC_DENSITY_STEP + gx0
                gys = np.arange(bits.shape[0]) * SC_DENSITY_STEP + gy0
                cols = np.clip(gxs // s + mref.wr, 0, mref.W - 1)
                rows = np.clip(gys // s + mref.hr, 0, mref.H - 1)
                E = elig[np.ix_(rows, cols)]
                wx, wy = np.meshgrid(gxs - off[0], gys - off[1])
                E &= np.hypot(wx, wy) > I["start_radii"] * 150
                lakes = (bits == 1)
                dens = float((lakes & E).sum()) / max(1, int(E.sum()))
                stray = int((lakes & ~E).sum())
                meas["blocks"][f"s{s}:{gx0},{gy0}"] = {"eligible": round(float(E.mean()), 3),
                                                       "density": round(dens, 5), "lake_points_outside": stray}
                if abs(dens - design) > SC_DENSITY_TOL * design:
                    fails.append(f"scale {s} block {gx0, gy0}: inland-lake density {round(dens, 5)} against the design "
                                 f"{round(design, 5)} (within {int(SC_DENSITY_TOL * 100)} percent)")
            vals = point_values(read_dump(dirs[k], "t3l"))
            k += 1
            floor_ = cfg["coast"]["far_floor"]
            bad = [(p, v.get("elevation")) for p, v in vals.items() if v.get("elevation") != floor_]
            if bad:
                fails.append(f"scale {s}: far probes off the far floor with the lakes on: {bad[:3]}")
            meas[f"far_s{s}"] = len(vals)
        # lakes only where the lake expression puts them: every player-blocking water tile of the square
        # that the coast-only world (the same geo square without the lakes) does not hold lies in an
        # inland-lake footprint or on a tile next to one (the game settles a tile at a footprint's
        # inner corner with its neighbours); the coast fit's own error (T1: p99 1.58 px) is not the
        # lakes', so the comparator is that world, not the reference raster. A tile on the coast-only
        # world's shoreline (water and land in its 3 x 3 neighbourhood) may change class with the
        # shift either way: there the coast's elevation is near 0 and the base game's land-tile
        # scores, which follow world position, settle it; the square's outermost ring, whose
        # neighbourhood the square cuts, counts as shoreline
        import dump_render as dr

        def water_of(area):
            names, idx = dr.decode_tiles(area)
            layers = dr.tile_layers(area)
            blocking = np.array([("water_tile" in layers.get(n, set()) and "player" in layers.get(n, set()))
                                 for n in names])
            return blocking[idx]

        def square_check(s, dsq, csq, want):
            """One scale's real-tile square: (record, failures)."""
            label = f"scale {s} real-tile square"
            area = (dsq.get("areas") or [None])[0]
            bits, gm = sc_grid_bits(dsq)
            carea = (csq.get("areas") or [None])[0]
            if area is None or bits is None or carea is None:
                return {}, [f"{label}: wrote no tiles or no lake grid, or the coast-only square no tiles"]
            off = runner_offset(cfg, mk, s)
            rec, f = {"geo_origin": [want[0], want[1]]}, []
            if want[2] is not None:
                rec["grid_lake_points"] = want[2]
            got = (area["area"]["x0"] + off[0], area["area"]["y0"] + off[1])
            got_c = (carea["area"]["x0"], carea["area"]["y0"])
            if got != tuple(want[:2]) or got_c != tuple(want[:2]):
                f.append(f"{label}: the squares sit at geo {got} and {got_c}, not at the chosen {tuple(want[:2])}")
            W, Wc = water_of(area), water_of(carea)
            fp = bits == 1
            if W.shape != Wc.shape or W.shape != fp.shape:
                return rec, f + [f"{label}: tiles {W.shape}, coast-only tiles {Wc.shape} and lake grid {fp.shape} "
                                 f"differ in shape"]
            pad = np.pad(fp, 1, constant_values=False)
            near = fp.copy()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    near |= pad[1 + dy:1 + dy + fp.shape[0], 1 + dx:1 + dx + fp.shape[1]]
            pc = np.pad(Wc, 1, mode="edge")
            wet, dry = np.zeros_like(Wc), np.zeros_like(Wc)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = pc[1 + dy:1 + dy + Wc.shape[0], 1 + dx:1 + dx + Wc.shape[1]]
                    wet |= q
                    dry |= ~q
            shore = wet & dry
            shore[0, :] = shore[-1, :] = shore[:, 0] = shore[:, -1] = True
            added = W & ~Wc
            lost = Wc & ~W
            unexplained = added & ~near & ~shore
            rec.update({"water": int(W.sum()), "coast_only_water": int(Wc.sum()),
                        "in_lake_footprints": int((W & fp).sum()), "added": int(added.sum()),
                        "added_beside_a_footprint": int((added & near & ~fp).sum()),
                        "shoreline_flips": int(((added & ~near) | lost).sum()),
                        "unexplained": int(unexplained.sum()),
                        "coast_water_lost_off_shore": int((lost & ~shore).sum())})
            if unexplained.any():
                f.append(f"{label}: {int(unexplained.sum())} inland water tiles the coast-only world does not hold lie "
                         f"in no lake footprint nor beside one nor on its shoreline (lakes only where the lake "
                         f"expression puts them)")
            if (lost & ~shore).any():
                f.append(f"{label}: {int((lost & ~shore).sum())} water tiles of the coast-only world off its shoreline "
                         f"are land with the lakes on")
            if not (W & fp & ~Wc).any():
                f.append(f"{label}: holds no lake water: the check saw no lake (G6)")
            return rec, f

        # the squares: scale 6's beside the grids, then scale 1's, placed from the scale 1 grid (dirs[0])
        meas["tiles_square"] = {}
        sq1 = square_origin(1, read_dump(dirs[0], "t3l"))
        for s, want in ((6, square_origin(6)), (1, sq1)):
            if want is None:
                fails.append(f"scale {s}: no real-tile square qualifies")
                k += 2
                continue
            rec, f = square_check(s, read_dump(dirs[k], "t3l"), read_dump(dirs[k + 1], "t3l"), want)
            k += 2
            meas["tiles_square"][f"scale_{s}"] = rec
            fails += f
        if k != len(dirs):
            fails.append(f"T3 read {k} of its {len(dirs)} run directories")
        sqs = meas["tiles_square"]
        return meas, fails, (f"inland lakes: design fraction {round(design, 5)}; {len(meas['blocks'])} sampled blocks "
                             f"within {int(SC_DENSITY_TOL * 100)} percent; real tiles at scale 1 {sqs.get('scale_1')} "
                             f"and at scale 6 {sqs.get('scale_6')}; far probes deep at scales 1 and 6")

    checks["t3_lakes"] = SuiteCheck("t3_lakes", lambda: key("t3_lakes", {"design": design}), lakes_run, lakes_derive)

    # T4: the starting-area slider at its smallest and largest scales the start radius (tier_from_start
    # leaves 0) and the enemy-free disc (enemy_base_probability leaves 0) the vanilla way, Earth against
    # M0 under the same slider; M0 itself must change with the slider (G6)
    def t4_run(deadline):
        m1p = sc_city_modset(ctx, mods, "t4e")
        m0p = sc_m0_probe(ctx, mods)
        jobs, i = [], 0
        lo, step, n = SC_T4_GRID
        for sa in SC_START_AREAS:
            for name in ("enemy_base_probability", "tier_from_start"):
                for who, ms in (("earth", m1p), ("m0", m0p)):
                    pen = expected_pen(cfg, mk, 6) if who == "earth" else {}
                    f = ctx.out / "mgs" / f"t4-{who}-{name}-{sa:.3f}.json"
                    f.parent.mkdir(parents=True, exist_ok=True)
                    body = {"starting_area": sa}
                    if pen:
                        body["property_expression_names"] = pen
                    f.write_text(json.dumps(body), encoding="utf-8")
                    ln = 0 if who == "earth" else 1
                    inst = lane_instance(ctx, ln)
                    jobs.append((dump_settings(ctx, ms, inst, label="t4", areas="", grid=f"{lo},{lo},{step},{n},{n}",
                                               grid_name=name, grid_threshold="0", grid_op="gt"),
                                 scenario_args(inst, ms, 3, SEED, f), ctx.out / f"t4-{who}-{name}-{i}", ln))
                    i += 1
        return sc_scenarios(ctx, jobs)

    def t4_derive(dirs):
        import numpy as np
        fails, meas = [], {}
        lo, step, n = SC_T4_GRID
        k = 0
        for sa in SC_START_AREAS:
            for name in ("enemy_base_probability", "tier_from_start"):
                r = {}
                for who in ("earth", "m0"):
                    d_ = dirs[k]
                    k += 1
                    fails += g1(d_) + g3(d_)
                    bits, gm = sc_grid_bits(read_dump(d_, "t4"))
                    if bits is None:
                        fails.append(f"{who} {name} at starting area {sa:.3f}: not recognised")
                        continue
                    ys, xs = np.nonzero(bits == 1)
                    r[who] = (round(float(np.hypot(xs * step + lo, ys * step + lo).min()), 1) if xs.size else None)
                meas[f"{name}@{sa:.3f}"] = r
                if r.get("earth") is None or r.get("m0") is None or abs(r["earth"] - r["m0"]) > SC_T4_TOL:
                    fails.append(f"{name} at starting area {sa:.3f}: Earth's disc ends at {r.get('earth')}, M0's at "
                                 f"{r.get('m0')} (want within {SC_T4_TOL} tiles)")
        for name in ("enemy_base_probability", "tier_from_start"):
            a, b = (meas.get(f"{name}@{sa:.3f}", {}).get("m0") for sa in SC_START_AREAS)
            if a is None or a == b:
                fails.append(f"positive control: M0's {name} disc does not change with the slider ({a}, {b})")
        return meas, fails, f"starting area {[round(x, 3) for x in SC_START_AREAS]}: {meas}"

    checks["t4_start_area"] = SuiteCheck("t4_start_area", lambda: key("t4_start_area", {"sa": SC_START_AREAS,
                                                                                         "grid": SC_T4_GRID}),
                                         t4_run, t4_derive)

    # T11: a world created with city A and loaded with city B generates the probe blocks at
    # the start area's edge as fresh A does (tiles and entities in a fixed request order) and differently
    # from fresh B; the city reads back as A's and the city drift line appears once, never undrifted
    def t11_run(deadline):
        a, b = SC_T11
        pname, _, _ = first_preset(cfg)
        msa, msb = sc_city_modset(ctx, mods, "t11ca", city=a), sc_city_modset(ctx, mods, "t11cb", city=b)
        inst = ctx.instance
        sa, sb = ctx.out / "t11c-create-a" / "a.zip", ctx.out / "t11c-create-b" / "b.zip"
        outs = [ctx.fh(create_args(inst, msa, sa, preset=pname), sa.parent).out,
                ctx.fh(create_args(inst, msb, sb, preset=pname), sb.parent).out]
        for label, ms, save in (("a-under-b", msb, sa), ("a-under-a", msa, sa), ("b-under-b", msb, sb)):
            dump_settings(ctx, ms, inst, label="t11c", areas=SC_T11_AREAS, types=ROUTE_TYPES, points="0,0",
                          names=g["city_index"])()
            outs.append(ctx.fh(scenario_args(inst, ms, 4, save=save), ctx.out / f"t11c-{label}").out)
        return outs

    def t11_derive(dirs):
        fails = []
        a, b = SC_T11
        for d_ in dirs:
            fails += g1(d_) + g3(d_)
        ab, aa, bb = (read_dump(x, "t11c") for x in dirs[2:5])
        tab, taa, tbb = (area_tiles(x) for x in (ab, aa, bb))
        eab, eaa, ebb = (area_entities(x) for x in (ab, aa, bb))
        d_aa = sum(1 for x, y in zip(tab, taa) if x != y)
        d_bb = sum(1 for x, y in zip(tab, tbb) if x != y)
        if d_aa or len(tab) != len(taa) or not tab:
            fails.append(f"A loaded under B differs from fresh A in {d_aa} of {len(tab)} tiles (want 0)")
        if eab != eaa:
            fails.append(f"A loaded under B differs from fresh A in entities ({len(eab)} against {len(eaa)})")
        if not d_bb:
            fails.append("A loaded under B equals fresh B: the city did not shape the probe blocks (G6)")
        ia = point_values(ab).get((0, 0), {}).get(g["city_index"])
        if ia != values.index(a):
            fails.append(f"the city reads back as {ia} under B, not A's {values.index(a)}")
        line = render_message(cfg, "drift_city", ("string-mod-setting", f"{cfg['settings'][g['city_setting']]['name']}-{a}"),
                              ("string-mod-setting", f"{cfg['settings'][g['city_setting']]['name']}-{b}"))
        n_ab = count_lines(log_text(dirs[2]), line)
        any_ = message_prefix(cfg, "drift_city")
        n_aa, n_bb = count_lines(log_text(dirs[3]), any_), count_lines(log_text(dirs[4]), any_)
        if n_ab != 1:
            fails.append(f"the city drift line appears {n_ab} times on A under B (want once): {line!r}")
        if n_aa or n_bb:
            fails.append(f"a city drift line on an undrifted load (A under A {n_aa}, B under B {n_bb})")
        meas = {"tiles": len(tab), "differing_vs_fresh_a": d_aa, "differing_vs_fresh_b": d_bb, "entities": len(eab),
                "city_read_back": ia, "drift_lines": [n_ab, n_aa, n_bb]}
        return meas, fails, (f"{a} world loaded under {b}: {d_aa} of {len(tab)} tiles and the entities equal fresh A, "
                             f"{d_bb} tiles differ from fresh B; city {ia}; drift line once")

    checks["t11_city"] = SuiteCheck("t11_city", lambda: key("t11_city", {"ab": SC_T11, "areas": SC_T11_AREAS}),
                                    t11_run, t11_derive)

    # T13 (M5 and M4): an Earth world on M5 (the live pack with RSO) creates with exit 0 and no error
    # line and logs the RSO warning exactly once; M4 (without RSO) and a non-Earth M5 world log none
    def live_pack():
        rows = json.loads((REPO / "docs" / "plan" / "research" / "R5-modlist.json").read_text(encoding="utf-8"))
        return [r["name"] for r in rows if r.get("enabled")]

    def rso_run(deadline):
        names = live_pack()
        m5 = mods.with_live("m5", names)
        m4 = mods.with_live("m4", [n for n in names if n != "rso-mod"])
        for ms, lbl in ((m5, "m5"), (m4, "m4")):
            mods.prepare(ms, lbl)
        mgs = sc_mgs(ctx, cfg, mk, 6, cfg["settings"][g["city_setting"]]["default_value"], "rso-s6")
        inst = ctx.instance
        return [ctx.fh(scenario_args(inst, m5, 3, SEED, mgs), ctx.out / "rso-m5-earth", timeout=1500).out,
                ctx.fh(scenario_args(inst, m4, 3, SEED, mgs), ctx.out / "rso-m4-earth", timeout=1500).out,
                ctx.fh(scenario_args(inst, m5, 3, SEED), ctx.out / "rso-m5-default", timeout=1500).out]

    def rso_derive(dirs):
        fails = []
        for d_ in dirs:
            fails += g1(d_)
        prefix = message_prefix(cfg, "rso")
        n = [count_lines(log_text(d_), prefix) for d_ in dirs]
        if n[0] != 1:
            fails.append(f"the Earth world on M5 logs the RSO warning {n[0]} times (want once)")
        if n[1] or n[2]:
            fails.append(f"the RSO warning appears on M4 ({n[1]}) or on a non-Earth M5 world ({n[2]})")
        return {"rso_lines": n}, fails, f"RSO warning lines: M5 Earth {n[0]}, M4 Earth {n[1]}, M5 default {n[2]}"

    checks["t13_rso"] = SuiteCheck("t13_rso", lambda: key("t13_rso", {"pack": live_pack()}), rso_run, rso_derive)

    # T18: the per-player path needs a player; whether a headless run can script one is
    # recorded here (2.1.23 lists create_test_player only on LuaSimulation): when it cannot, the
    # design notes entry stands and smoke steps 4 and 1 carry the RSO warning and the Map type notice
    def player_run(deadline):
        ms = mods.with_mods("t18p", [HERE / "mods" / "ea-player-probe"])
        mods.prepare(ms, "t18p")
        return [ctx.fh(scenario_args(ctx.instance, ms, 3, SEED), ctx.out / "t18-player").out]

    def player_derive(dirs):
        fails = g1(dirs[0])
        f = Path(dirs[0]) / "script-output" / "ea-player-probe" / "player.json"
        rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if not f.exists():
            fails.append("the player probe wrote nothing")
        elif rec.get("create_test_player_available"):
            fails.append("a headless run can script a player: replace the smoke route with the scripted-player test "
                         "(ruling 25)")
        return rec, fails, (f"no scripted player headless ({rec.get('error')}); the per-player sends stay with smoke "
                            f"steps 4 and 1 (DECISIONS, spawn-cities)")

    checks["t18_player"] = SuiteCheck("t18_player", lambda: key("t18_player"), player_run, player_derive)

    # T14 (SS synthetic planet, S11's method): planet surfaces in an Earth world read no Earth key with the
    # guard and read them with it disabled (a staged build whose guard returns at once)
    def stage_planet():
        src = HERE / "mods" / "ea-planet-probe"
        dst = ctx.out / "stage" / "ea-planet-probe"
        shutil.copytree(src, dst, dirs_exist_ok=True)
        info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
        info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
        (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
        return dst

    def stage_unguarded():
        dst = ctx.out / "stage" / "unguarded" / cfg["identity"]["id"]
        shutil.copytree(MOD, dst, dirs_exist_ok=True)
        f = dst / "scripts" / "guards.lua"
        text = f.read_text(encoding="utf-8")
        head = "function M.surface_guard(surface)\n"
        if text.count(head) != 1:
            raise GateError("scripts/guards.lua has no single surface_guard to disable for T14's control")
        f.write_text(text.replace(head, head + "  do return 0 end\n"), encoding="utf-8", newline="\n")
        return dst

    def planet_run(deadline):
        probe = stage_planet()
        real = mods.with_mods("t14p", [probe])
        mods.prepare(real, "t14p")
        mods.build_zip()
        unguarded = stage_unguarded()
        ung = mods.make(f"ea-t14u-{mods.zip_sha[:8]}-{folder_hash(unguarded, probe)}", [unguarded, probe])
        mods.prepare(ung, "t14u")
        mgs = sc_mgs(ctx, cfg, mk, 6, cfg["settings"][g["city_setting"]]["default_value"], "t14-s6")
        outs = [ctx.fh(scenario_args(ctx.instance, real, 4, SEED, mgs), ctx.out / "t14-guard").out,
                ctx.fh(scenario_args(ctx.instance, ung, 4, SEED, mgs), ctx.out / "t14-unguarded").out]
        # the negative control: a vanilla preset that sets a preset key (Island's elevation), on a new
        # map with the guard and as a save made without Terra Nauvis that then gains it (the on_init and
        # on_configuration_changed sweeps over a surface that already inherited the key)
        island = write_mgs(ctx, "t14-island", t14_island_pen())
        plain = mods.with_mods("t14i", [HERE / "mods" / "ea-planet-probe"], earth=False)
        mods.prepare(plain, "t14i")
        save = ctx.out / "t14-island-create" / "island.zip"
        outs.append(ctx.fh(scenario_args(ctx.instance, real, 4, SEED, island), ctx.out / "t14-island-new").out)
        ctx.fh(create_args(ctx.instance, plain, save, mgs=island), save.parent)
        outs.append(ctx.fh(scenario_args(ctx.instance, real, 4, save=save), ctx.out / "t14-island-added").out)
        return outs

    def t14_island_pen():
        pen = dict(preset_pen(ctx.shared.get("dump_m1"), T14_ISLAND))
        if not str(pen.get("elevation") or ""):
            raise GateError(f"the M1 dump's {T14_ISLAND} preset sets no elevation: T14's negative control has no "
                            f"vanilla preset key to keep")
        return pen

    def planet_derive(dirs):
        fails, meas = [], {}
        keys = set(cfg["preset_keys"])
        if len(dirs) != 4:
            return meas, [f"{len(dirs)} T14 runs, want 4 (guard, unguarded, island new and island added)"], "incomplete"
        want_elev = str(t14_island_pen()["elevation"])
        for label, d_, want in (("guard", dirs[0], False), ("unguarded", dirs[1], True),
                                ("island_new", dirs[2], "island"), ("island_added", dirs[3], "island")):
            fails += g1(d_) + g3(d_)
            f = Path(d_) / "script-output" / "ea-planet-probe" / "planets.json"
            if not f.exists():
                fails.append(f"{label}: the planet probe wrote nothing")
                continue
            rep = json.loads(f.read_text(encoding="utf-8"))
            surfs = rep.get("surfaces") or {}
            meas[label] = {n: sorted(set(s.get("inherited") or []) & keys) for n, s in surfs.items()}
            if len(surfs) != 2:
                fails.append(f"{label}: {len(surfs)} probe surfaces, want 2")
            if want == "island":
                # a non-Earth save: every preset key the vanilla preset set stays on both surfaces
                if "elevation" not in (rep.get("default_keys") or []):
                    fails.append(f"{label}: the save's defaults hold no elevation key, so the control tests nothing")
                for n, s in surfs.items():
                    if s.get("elevation_key") != want_elev or "elevation" not in (s.get("inherited") or []):
                        fails.append(f"{label}: {n} reads elevation {s.get('elevation_key')!r}, not the vanilla "
                                     f"preset's {want_elev!r}: the guard touched a non-Earth save")
                meas[label + "_elevation"] = {n: s.get("elevation_key") for n, s in surfs.items()}
                continue
            for n, got in meas[label].items():
                if want and set(got) != keys & set(rep.get("default_keys") or []):
                    fails.append(f"{label}: {n} inherits {got}, not every Earth key (the positive control)")
                if not want and got:
                    fails.append(f"guard: {n} still reads Earth keys {got}")
        return meas, fails, (f"with the guard the probe planets read no Earth key; without it they read "
                             f"{len(next(iter((meas.get('unguarded') or {}).values()), []))} (positive control); "
                             f"a vanilla {T14_ISLAND} preset save, new and with the mod added, keeps {want_elev} on both "
                             f"(negative control)")

    checks["t14_planet"] = SuiteCheck("t14_planet", lambda: key("t14_planet"), planet_run, planet_derive)

    # T18 (c), D31: a second force's spawn at three other cities from shipped data only lands on land, as
    # the oracle expects at each city
    def stage_force(picks):
        import oracle
        src = HERE / "mods" / "ea-force-spawn"
        dst = ctx.out / "stage" / "ea-force-spawn"
        shutil.copytree(src, dst, dirs_exist_ok=True)
        rows = oracle.city_table()[mk]["cities"]
        m = cfg["maps"][mk]

        def lua(v):
            if isinstance(v, dict):
                return "{" + ", ".join(f"[{json.dumps(k)}] = {lua(x)}" for k, x in v.items()) + "}"
            if isinstance(v, (list, tuple)):
                return "{" + ", ".join(lua(x) for x in v) + "}"
            return json.dumps(v)
        spec = {"cities": {k: rows[k] for k in picks},
                "map": {k: m[k] for k in ("lon_left_edge", "lat_top_edge", "wr", "hr")},
                "px_per_degree": cfg["coordinates"]["px_per_degree"],
                "corner_divisor": cfg["coordinates"]["corner_offset_divisor"],
                "offset_names": [g["cx"], g["cy"]], "scale_name": cfg["keys"]["scale"], "picks": list(picks)}
        (dst / "force-spawn-spec.lua").write_text("return " + lua(spec) + "\n", encoding="utf-8", newline="\n")
        info = json.loads((dst / "info.json").read_text(encoding="utf-8"))
        info["dependencies"] = info["dependencies"] + [cfg["identity"]["id"]]
        (dst / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
        return dst

    def force_run(deadline):
        ms = mods.with_mods("t18f", [stage_force(SC_FORCE_PICKS)])
        mods.prepare(ms, "t18f")
        mgs = sc_mgs(ctx, cfg, mk, 6, cfg["settings"][g["city_setting"]]["default_value"], "t18f-s6")
        return [ctx.fh(scenario_args(ctx.instance, ms, 3, SEED, mgs), ctx.out / "t18-force").out]

    def force_derive(dirs):
        import earthgeo as eg
        import oracle
        fails = g1(dirs[0]) + g3(dirs[0])
        f = Path(dirs[0]) / "script-output" / "ea-force-spawn" / "spawns.json"
        if not f.exists():
            return {}, fails + ["the force-spawn probe wrote nothing"], "no output"
        rep = json.loads(f.read_text(encoding="utf-8"))
        mref = eg.MapRef(mk)
        O = oracle.load_oracle(mk, TESTS / "oracle")
        places = {p["name"]: p for p in O["places"] if p["kind"] == "city"}
        off = tuple(int(v) for v in rep.get("offset") or ())
        want_off = runner_offset(cfg, mk, 6)
        if off != want_off:
            fails.append(f"the folded offset read at (0, 0) is {off}, the model's {want_off}")
        meas = {"offset": off, "spawns": []}
        for sp in rep.get("spawns") or []:
            p = places.get(sp["name"])
            want_land = (p or {}).get("expect", {}).get("land")
            tile_land = "water" not in str(sp.get("tile"))
            geo = tuple(oracle.place_tile(mref, p, 6)) if p else None
            want_world = oracle.world_tile(geo, off) if geo else None
            meas["spawns"].append({"city": sp["city"], "tile": sp.get("tile"), "world": sp.get("world"),
                                   "oracle_world": want_world})
            if want_land is None:
                fails.append(f"{sp['city']}: the oracle has no land expectation")
            elif tile_land != bool(want_land):
                fails.append(f"{sp['city']}: tile {sp.get('tile')} at the second force's spawn, the oracle expects "
                             f"land={want_land}")
            if want_world is not None and tuple(sp.get("world") or ()) != want_world:
                fails.append(f"{sp['city']}: spawn tile {sp.get('world')} from shipped data, the oracle's {want_world}")
        if len(meas["spawns"]) != len(SC_FORCE_PICKS):
            fails.append(f"{len(meas['spawns'])} spawns placed, want {len(SC_FORCE_PICKS)}")
        return meas, fails, f"a second force at {list(SC_FORCE_PICKS)}: {[s['tile'] for s in meas['spawns']]}"

    checks["t18_force_spawn"] = SuiteCheck("t18_force_spawn", lambda: key("t18_force_spawn", {"picks": SC_FORCE_PICKS}),
                                           force_run, force_derive)

    # V2 (SS renders; test notes V1 to V5, JI-19): city crops at scales 1, 3 and 6 for the
    # verification pass's reviewer, rubric "city on land with its lake and ores in view": per city the
    # reference land around its pixel (land, thin water, water) beside a preview of the world that
    # spawns there (the spawn at the panel's centre, cliffs off), one contact sheet per scale,
    # committed under V2_DIR as the V1 sheets are under V1_DIR
    cities = values[1:]

    def v2_run(deadline):
        lanes = sc_lane_modsets(ctx, mods, "v2c", PAR_MAX)
        jobs, i = [], 0
        for s in SC_SCALES:
            for city in cities:
                ln = i % PAR_MAX
                pen = expected_pen(cfg, mk, s, city)
                f = ctx.out / "mgs" / f"v2-{city}-s{s}.json"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps({"property_expression_names": pen, "cliff_settings": NO_CLIFFS}, indent=1,
                                        sort_keys=True), encoding="utf-8")
                jobs.append((None, preview_args(lane_instance(ctx, ln), lanes[ln], V2_PX, SEED, f),
                             ctx.out / f"v2-{city}-s{s}", ln))
                i += 1
        dirs = sc_scenarios(ctx, jobs)
        out = ctx.out / "v2"
        out.mkdir(parents=True, exist_ok=True)
        k = 0
        for s in SC_SCALES:
            v2_sheet(cfg, mk, s, [(c, dirs[k + j]) for j, c in enumerate(cities)], out / f"europe-cities-s{s}.png")
            k += len(cities)
        (out / "run.json").write_text(json.dumps({"exit": 0, "isolated": True, "error_lines": [],
                                                  "images": {p.name: sha256_file(p) for p in sorted(out.glob("*.png"))}},
                                                 indent=1), encoding="utf-8")
        commit_sheets(ctx, out, V2_DIR)
        return dirs + [out]

    def v2_derive(dirs):
        fails = []
        for d_ in dirs[:-1]:
            fails += g1(d_) + g3(d_)
        hashes = []
        for d_ in dirs[:-1]:
            try:
                hashes.append(derive_preview(d_)["images"].get(f"{SEED}.png"))
            except GateError as e:
                fails.append(str(e))
        if len(dirs) - 1 != len(cities) * len(SC_SCALES):
            fails.append(f"{len(dirs) - 1} city previews, want {len(cities)} cities at scales {list(SC_SCALES)}")
        # G6: the shift moved the spawn, so two previews may share an image only where the game has
        # nothing to tell them apart: the same reference land in the crop (thin water is land, as
        # the fit fills it) and the same spawn-lake bearing. Inland cities at scales 3 and 6 show
        # land and their lake alone, and the base game's tiles follow world position, not the city.
        sig = v2_signatures(cfg, mk, cities)
        seen = {}
        for (c, s), h in zip([(c, s) for s in SC_SCALES for c in cities], hashes):
            if h is None:
                continue
            other = seen.setdefault(h, (c, s))
            if other != (c, s) and sig[other] != sig[(c, s)]:
                fails.append(f"the previews of {other[0]} at scale {other[1]} and {c} at scale {s} are byte-identical "
                             f"while their reference crops or lake bearings differ: the city did not move the spawn (G6)")
        if len(set(hashes)) < 2:
            fails.append("every city preview is byte-identical: the city did not move the spawn (G6)")
        rj = load_run_json(dirs[-1]) or {}
        fails += images_rehash(dirs[-1])
        sheets = sorted(rj.get("images") or {})
        committed = sorted(q.name for q in V2_DIR.glob("*.png")) if V2_DIR.is_dir() else []
        if committed != sheets or len(sheets) != len(SC_SCALES):
            fails.append(f"{rel_repo(V2_DIR)} holds {committed}, the run made {sheets} (want one per scale)")
        for name in sheets:
            q = V2_DIR / name
            if q.is_file() and sha256_file(q) != (rj.get("images") or {}).get(name):
                fails.append(f"the committed sheet {rel_repo(q)} differs from the run's")
        return ({"sheets": sheets, "committed": [rel_repo(V2_DIR / n) for n in committed], "previews": len(hashes)},
                fails, f"{len(sheets)} city-crop sheets (V2) of {len(cities)} cities at scales {list(SC_SCALES)}, "
                       f"committed in {rel_repo(V2_DIR)}")

    checks["v2_cities"] = SuiteCheck("v2_cities", lambda: key("v2_cities", {"px": V2_PX, "scales": SC_SCALES}),
                                     v2_run, v2_derive)


V2_DIR = SUITES / "spawn-cities" / "v2"     # the committed city-crop sheets (outside the keyed tests digest)
V2_PX = 256                                 # px: each city's preview and reference crop, the spawn at the centre


def commit_sheets(ctx, out, dest):
    """Copy a render run's sheets into the repo (`dest`), after clearing the sheets an earlier run left
    there; tests/baselines/suites/ is outside every suite key, so the copy re-keys nothing."""
    dest.mkdir(parents=True, exist_ok=True)
    for old in list(dest.glob("*.png")) + list(dest.glob("*.json")):
        old.unlink()
    for png in sorted(Path(out).glob("*.png")):
        shutil.copyfile(png, dest / png.name)


def v2_signatures(cfg, mk, cities):
    """Per (city, scale) of the V2 sheets, what the game can show of the city in its crop: the
    reference land (thin water as land) under the crop, as v2_sheet reads it, and the spawn lake's
    generated bearing at that scale."""
    import hashlib as hl
    import numpy as np
    import earthgeo as eg
    import oracle
    mref = eg.MapRef(mk)
    g = tnconfig.geography(cfg)[mk]
    values = cfg["settings"][g["city_setting"]]["allowed_values"]
    bearings = tnconfig.load(REPO / "terra-nauvis" / g["bearings"])["bearings"]
    land = mref.land.astype(bool) | mref.thin.astype(bool)
    half = V2_PX // 2
    xs = np.arange(-half, half)
    out = {}
    for s in SC_SCALES:
        for city in cities:
            cx, cy = oracle.spawn_offset(cfg, mk, s, SEED, values.index(city))
            cols_ = np.clip(np.floor_divide(xs + cx, s) + mref.wr, 0, mref.W - 1)
            rows_ = np.clip(np.floor_divide(xs + cy, s) + mref.hr, 0, mref.H - 1)
            crop = np.ascontiguousarray(land[np.ix_(rows_, cols_)])
            out[(city, s)] = (hl.sha256(crop.tobytes()).hexdigest(), bearings[city][s - 1])
    return out


def v2_sheet(cfg, mk, scale, runs, out_png, cols=5, panel=192):
    """One V2 contact sheet: per city (runs: [(setting value, preview run dir)]) the reference land
    around its pixel at `scale` (tan land, light blue thin water, blue water; world tile (x, y) reads
    pixel (floor((x + cx) / s) + wr, floor((y + cy) / s) + hr) under the city's offset) beside the
    preview centred on the spawn, both scaled to `panel` px, a red cross at the spawn, and the city's
    name above. Saved as a palette PNG to keep the committed copy small."""
    import numpy as np
    from PIL import Image, ImageDraw
    import earthgeo as eg
    import oracle
    import tnconfig as tc
    mref = eg.MapRef(mk)
    rows_tbl = tc.load(oracle.CITIES)[mk]["cities"]
    s = int(scale)
    label_h = 18
    n = len(runs)
    nrows = -(-n // cols)
    sheet = Image.new("RGB", (cols * (2 * panel + 8), nrows * (panel + label_h + 6)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    half = V2_PX // 2
    xs = np.arange(-half, half)
    for i, (city, run) in enumerate(runs):
        number = cfg["settings"][tnconfig.geography(cfg)[mk]["city_setting"]]["allowed_values"].index(city)
        cx, cy = oracle.spawn_offset(cfg, mk, s, SEED, number)
        cols_ = np.clip(np.floor_divide(xs + cx, s) + mref.wr, 0, mref.W - 1)
        rows_ = np.clip(np.floor_divide(xs + cy, s) + mref.hr, 0, mref.H - 1)
        land = mref.land.astype(bool)[np.ix_(rows_, cols_)]
        thin = mref.thin.astype(bool)[np.ix_(rows_, cols_)]
        ref = np.zeros((V2_PX, V2_PX, 3), np.uint8)
        ref[:] = (40, 70, 140)
        ref[thin] = (110, 160, 210)
        ref[land] = (176, 150, 100)
        ref_img = Image.fromarray(ref).resize((panel, panel), Image.NEAREST)
        pv = Image.open(Path(run) / f"{SEED}.png").convert("RGB").resize((panel, panel), Image.NEAREST)
        x0 = (i % cols) * (2 * panel + 8)
        y0 = (i // cols) * (panel + label_h + 6) + label_h
        sheet.paste(ref_img, (x0, y0))
        sheet.paste(pv, (x0 + panel + 4, y0))
        c = panel // 2
        for px in (x0 + c, x0 + panel + 4 + c):
            draw.line([(px - 5, y0 + c), (px + 5, y0 + c)], fill=(230, 30, 30))
            draw.line([(px, y0 + c - 5), (px, y0 + c + 5)], fill=(230, 30, 30))
        name = rows_tbl.get(city, {}).get("name", city)
        draw.text((x0 + 2, y0 - label_h + 3), f"{name}  (scale {s}, offset {cx}, {cy})", fill=(235, 235, 235))
    sheet.convert("P", palette=Image.ADAPTIVE, colors=256).save(out_png, optimize=True)


# ------------------------------------------------------------------------------------------------ commands

def with_lock(ctx, fn):
    """Lock, the command, lock release; the job dies with us. Every game launch of the command and of
    its child tools runs while the command holds the workspace lock."""
    lock = Lock(ctx.root / "earth-test.lock")
    code = 1
    try:
        lock.acquire(ctx.cmd)
        ctx.locked = True
        code = fn()
    except FatalRun as e:
        # the job is terminated below, before the lock is released and before anything else can launch
        ctx.say(f"FATAL {e}; every further game run of this command is stopped and the job is terminated; report "
                f"it first on the sprint parent issue (sacred constraint 1)")
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
        ctx.locked = False
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
        gated = gate_evidence_slices(a.through)
        ctx.say(f"gate through {a.through} ({mode}): {len(rows_wanted)} FG rows of {[s['id'] for s in entries]}; "
                f"suite evidence and live sample of {[s['id'] for s in gated]}")
        try:
            state["rows"] += fg_rows(ctx, mods, sec6, rows_wanted, use_cache=not a.cold)
            # design section 5, step 12: the suite verdicts of every milestone this gate lands re-derived (the
            # pending milestones: a group's earlier milestones with <milestone-id>), never a landed milestone's
            state["rows"] += suite_gate(ctx, mods, sec6, gated)
        except BudgetExceeded as e:
            done = {r.name for r in state["rows"]}
            state["not_run"] = [r for r in rows_wanted if r not in done]
            ctx.say(f"BUDGET {e}; rows not run: {state['not_run']} and the suite evidence")
            return 1
        return 0 if all(not r.fails for r in state["rows"]) else 1

    code = with_lock(ctx, body)
    failed = [r.name for r in state["rows"] if r.fails]
    secs = round(time.time() - ctx.t0, 1)
    verdict = "ok" if code == 0 and not failed and not state["not_run"] else "fail"
    print(f"GATE {verdict} through={a.through} mode={mode} rows={len(state['rows'])} failed={failed} "
          f"not_run={state['not_run']} seconds={secs} out={ctx.out}",
          flush=True)
    return 0 if verdict == "ok" else 1


def suite_gate(ctx, mods, sec6, entries):
    """Step 12: the suite evidence of every gated milestone re-derived (gate_evidence_slices: the pending
    milestones, so a group's gate holds each of its milestones to its own manifest), then the rotating live
    sample (rule 3) drawn over all their checks: one deterministic check, compared exactly with its
    re-derived evidence, and one timed row against section 6, with rule 5's extra group for a
    borderline timed ratio when it fits the gate's budget."""
    checks = suite_checks(ctx, mods, sec6)
    rows, results = evidence_rows(ctx, entries, checks, say=ctx.say)
    det, timed = live_pools(entries)
    rng = random.Random(time.time_ns())
    for kind, pool in (("deterministic", det), ("timed", timed)):
        if not pool:
            continue
        pick = rng.choice(pool)
        owners = [e["id"] for e in entries if pick in e["deterministic_ss"] + e["timed_ss"]]
        lrow = Row(f"live_sample:{pick}")
        t = time.time()
        try:
            if pick == "t15b_m1":
                dirs, meas, f, detail = live_t15b_m1(ctx, mods, sec6)
            elif pick == "t15b_m0":
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
            lrow.fails += list(f) + live_compare(kind, pick, meas, stored_evidence(pick, entries, results))
            lrow.detail = f"{kind} live sample {pick} of {', '.join(owners)}: {detail}"
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
        # the milestone's registry lands in its manifest (tnfrozen.snapshot): later milestones of a group are
        # held to it before anything reaches main
        manifest = snapshot_manifest(a.slice, json.loads((TESTS / "frozen.json").read_text(encoding="utf-8")),
                                     manifest)
        for n in names:
            t = time.time()
            key = checks[n].key_fn()
            dirs = checks[n].run_fn(time.time() + 3600)
            ctx.shared.setdefault("suite_runs", {})[n] = dirs
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

    code = with_lock(ctx, body)
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
        pname = earth_presets(cfg)[0]
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

    code = with_lock(ctx, body)
    print(f"INSTALL-CHECK {'ok' if code == 0 else 'fail'} zip={info.get('zip')} sha256={info.get('sha')} "
          f"modset={info.get('modset')} earth_preview={list((info.get('earth') or {}).values())[:1]} "
          f"vanilla_preview={list((info.get('vanilla') or {}).values())[:1]} out={ctx.out}", flush=True)
    return code


def cmd_baseline(a):
    """Rewrite the measured values in tests/budgets.json and tests/baselines/ from fresh runs, each of
    which must pass G1 to G3 (and G2 for an Earth run), render exactly one image per seed (G4) and
    carry the three --verbose complexity lines where it records them; the first preset's preview
    must differ from M0's at every canonical seed (G5) and every block census must be complete. Any
    failed run refuses both files, which stay as they were."""
    entry = current_slice()
    ctx = Ctx("baseline", entry["id"])

    def body():
        mods = Mods(ctx)
        cfg = mods.cfg
        m0, m1 = mods.m0(), mods.m1()
        mods.prepare(m0, "m0")
        r1 = mods.prepare(m1, "m1")
        ctx.shared["dump_m1"] = json.loads((r1.out / "data-raw-dump.json").read_text(encoding="utf-8"))
        pname, mk, _ = first_preset(cfg)
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
        cmap = {s: checked(preview(ctx, m1, f"cx-map-s{s}", 64, verbose=True, mgs=preset_mgs(ctx, cfg, s)), True,
                           True)["complexity"] for s in BUDGET_SCALES}
        if {k: v.get("complexity") for k, v in c0.items()} != VANILLA:
            fails.append(f"M0 complexity {c0} is not vanilla's {VANILLA} (G8: re-baseline the build pin first)")
        if cd != c0:
            fails.append("the default preset with Earth loaded compiles differently from M0 (T13 zero cost)")
        vanilla, earth = {}, {}
        for seed in SEEDS:
            g = checked(preview(ctx, m0, f"m0-256-{seed}", 256, seed=seed), False)
            vanilla[str(seed)] = g["images"].get(f"{seed}.png")
            g = checked(preview(ctx, m1, f"preset-256-{seed}", 256, preset=pname, seed=seed), True)
            earth[str(seed)] = g["images"].get(f"{seed}.png")
            if not vanilla[str(seed)] or not earth[str(seed)]:
                fails.append(f"seed {seed}: a preview wrote no {seed}.png")
            elif vanilla[str(seed)] == earth[str(seed)]:
                fails.append(f"seed {seed}: the {pname} preview equals M0's (G5)")
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
        # M0's census of the map's own T15b blocks (fixed in geo coordinates, scales 6 and 1)
        import earthgeo as eg
        pos = europe_positions(cfg, eg.MapRef(mk))
        eu_census = {}
        for s, spec in sorted(pos["block"].items()):
            sv = make_save(ctx, mods, m0t, "tq1-gen-block", spec, f"census-{mk}-s{s}")
            rr = ctx.fh(["scenario", "--instance", ctx.instance, "--modset", m0t, "--save", sv, "--ticks", "10", "--",
                         "--threads", str(T15B["threads"])], ctx.out / f"census-{mk}-s{s}")
            fails.extend(g1(rr.out) + g3(rr.out))
            c = ctx.perf.parse_forced(rr.out).get("census") or {}
            if c.get("block_generated_before") != 0 or c.get("block_generated_after") != 256:
                fails.append(f"census run {mk} scale {s}: block generated {c.get('block_generated_before')} -> "
                             f"{c.get('block_generated_after')} chunks, want 0 -> 256")
            eu_census[str(s)] = {k: c.get(k) for k in keep}
        if fails:
            for f in fails[:20]:
                ctx.say(f"FAIL {f}")
            raise GateError(f"baseline refused: {len(fails)} run checks failed; tests/budgets.json and "
                            f"tests/baselines/build-{GAME_BUILD}.json are unchanged")
        rows = budgets_rows(cfg, cmap, c0, cd)
        write_atomic(BUDGETS, json.dumps({
            "format": "tn-budgets/1",
            "note": "Measured values only (ruling 3): complexity rows from 64 px --verbose previews at seed 1000. "
                    "Written by 'earth_test.py baseline'; the gate requires equality and reads thresholds from the "
                    "plan's section 6.",
            "game_build": f"{GAME_VERSION} build {GAME_BUILD}", "rows": rows}, indent=1) + "\n")
        write_atomic(BASELINES / f"build-{GAME_BUILD}.json", json.dumps({
            "format": "tn-baselines/1", "game_build": f"{GAME_VERSION} build {GAME_BUILD}",
            "note": "Vanilla and comparator hashes keyed by game build (G8), each Terra Nauvis map's preset "
                    "preview hashes, the T15b block's census on M0, and M0's census of each map's own T15b "
                    "blocks (fixed in geo coordinates through the spawn offset). Written by 'earth_test.py "
                    "baseline'.",
            "previews_256": {"M0": vanilla, mk: earth},
            "t15b_block": {"chunks": T15B["block"], "census_m0": {k: census.get(k) for k in keep}},
            "t15b_europe": {"map": mk, "blocks": {str(s): v for s, v in pos["block"].items()},
                            "block_land": {str(s): v for s, v in pos["block_land"].items()}, "census_m0": eu_census},
        }, indent=1) + "\n")
        ctx.say(f"wrote {BUDGETS} ({len(rows)} rows) and {BASELINES / ('build-' + GAME_BUILD + '.json')}")
        return 0

    code = with_lock(ctx, body)
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
        # every existing record checked against the contract and its own dump before anything is
        # appended; the placeholder's names and the setting-mirroring fallbacks are never registered
        new_fz, new = freeze_registry(fz, dumps, cfg, entry["id"], time.strftime("%Y-%m-%d"))
        # no record an earlier milestone's snapshot holds may move (a hand-dropped record re-registered by
        # this milestone would come back with a new milestone and date)
        snaps, _ = tnfrozen.suite_snapshots(REGISTRY, before=entry["id"], suites=SUITES)
        bad = tnfrozen.snapshot_problems(new_fz, snaps)
        if bad:
            raise GateError(f"freeze would break an earlier slice's frozen snapshot: {bad[:2]}; freeze registers "
                            f"nothing")
        added.extend(new)
        write_atomic(TESTS / "frozen.json", json.dumps(new_fz, indent=1) + "\n")
        write_snapshot(entry["id"], new_fz)
        return 0

    code = with_lock(ctx, body)
    print(f"FREEZE {'ok' if code == 0 else 'fail'} added={len(added)} {added[:10]} out={ctx.out}", flush=True)
    return code


def snapshot_manifest(slice_id, fz, manifest=None):
    """The milestone's suite manifest with its frozen snapshot (tnfrozen.snapshot: the records registered
    through it) set from `fz`. The registry's newest milestone may still redo its own records before it
    lands, so its snapshot is replaced; an earlier milestone's snapshot only grows: a record it holds that
    `fz` changed or dropped raises GateError, so re-running an earlier milestone's suite cannot launder a
    rewritten record into its snapshot."""
    man_path = SUITES / f"{slice_id}.json"
    if manifest is None:
        manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else \
            {"format": "tn-suite/1", "slice": slice_id, "checks": {}}
    old = manifest.get("frozen")
    if old is not None and slice_id != REGISTRY[-1]["id"]:
        bad = tnfrozen.snapshot_problems(fz, {f"{slice_id}'s suite manifest": old})
        if bad:
            raise GateError(f"tests/frozen.json moved a record {slice_id}'s snapshot holds: {bad[:2]} (fail closed)")
    manifest["frozen"] = tnfrozen.snapshot(fz, REGISTRY, slice_id)
    return manifest


def write_snapshot(slice_id, fz):
    """Write the milestone's frozen snapshot into its suite manifest (snapshot_manifest)."""
    write_atomic(SUITES / f"{slice_id}.json", json.dumps(snapshot_manifest(slice_id, fz), indent=1, default=str) + "\n")


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
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except GateError as e:
        print(f"RESULT fail {e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
