#!/usr/bin/env python3
"""Space Age compatibility of Terra Nauvis: the sa-compat test (2026-10-28), reusable as gate rows.

The requirement (2026-10-28): Terra Nauvis works with Space Age, and its Earth maps affect no other planet in any
way and cause no error. Every check compares a modset with terra-nauvis against its twin without it,
both with the four expansion mods (fh.py modset --expansion) and tools/mods/ea-sa-probe:

  1 load     --dump-data and --create succeed (RESULT ok, isolated=yes, errors=0), no warning or error
             line names terra-nauvis, no warning is new against the twin, and every prototype but
             terra-nauvis' own equals the twin's in the dump.
  2 planets  every planet's surface, created through LuaPlanet.create_surface at tick 3 and
             force-generated in fixed chunk blocks by the probe, equals the twin's per chunk in tiles,
             entities and decoratives, in sampled properties and in its compiled noise programs, on the
             default preset and on every Terra Nauvis preset; each planet's preview is reported too
             (a preview runs no control stage, so the surface guard cannot act there).
  3 Nauvis   every Terra Nauvis preset generates its map under Space Age (Nauvis differs from the
             twin's) with the spawn on land; a default world with terra-nauvis loaded equals the twin's.
  4 names    no terra-nauvis noise expression, noise function, setting, autoplace control, preset or
             locale key collides with a name the expansion or the base game defines.

Controls: the twin runs twice and must agree with itself (determinism), and a staged terra-nauvis
whose D33 surface guard returns at once must leave Earth keys on the planets (positive control).

Usage, from the repo root:
  python tools/sa_compat.py stage --zip ZIP --root OUT     the modsets and the unguarded copy (no launch)
  python tools/sa_compat.py matrix --root OUT              every game launch, one at a time (resumable)
  python tools/sa_compat.py report --root OUT              the four verdicts; writes OUT/report.json

matrix launches only through %FACTORIO_WS%/tools/fh.py, and only while the workspace lock
(previews/earth-build/earth-test.lock) is free and no factorio.exe runs; it never takes the lock, so a
gate that starts meanwhile waits for one launch at most. Beside a live build, run matrix and report
under the E-core wrapper.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MOD = REPO / "terra-nauvis"
PROBE = HERE / "mods" / "ea-sa-probe"
WS = Path(os.environ.get("FACTORIO_WS", r"%FACTORIO_WS%"))
GAME = Path(os.environ.get("FACTORIO_GAME", r"%FACTORIO_GAME%"))
FH = WS / "tools" / "fh.py"
LOCK = WS / "previews" / "earth-build" / "earth-test.lock"
EXPANSION = ["space-age", "quality", "elevated-rails", "recycler"]
INSTANCE = "ea-sa"
# tools/earth_test.py (compat-completeness) sets RUNNER inside a command that holds the workspace lock: every fh.py
# call then goes through the command's own runs, one game at a time, and the quiet wait stands down.
RUNNER = None
TICKS = 10
TRAVEL_TICKS = 70
PREVIEW_SIZE = 512
TIMEOUT = 300

PROG_RE = re.compile(r"(\w+) noise program processed (\d+) expressions \((\d+) unique\) and has (\d+) operations "
                     r"and (\d+) registers; estimated complexity: (\d+)")
MARK_RE = re.compile(r"ea-sa-probe: (?:creating the surface of planet|generating surface|platform moved to) (\S+)")
STAMP_RE = re.compile(r"^\s*\d+\.\d+\s+")
WARN_RE = re.compile(r"\b(Warning|Error|error|warning)\b")

sys.path.insert(0, str(HERE))


def load_cfg():
    import tnconfig
    return tnconfig.load()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")


def fh(args):
    if RUNNER is not None:
        return RUNNER(args)
    cmd = [sys.executable, str(FH)] + [str(a) for a in args]
    cp = subprocess.run(cmd, cwd=str(WS), capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (cp.stdout or "") + (cp.stderr or "")
    results = [line for line in text.splitlines() if line.startswith("RESULT")]
    return (results[-1] if results else "RESULT fail (no RESULT line) " + text.strip()[-300:]), text


# ---------------------------------------------------------------- stage

def stage_unguarded(dst):
    """A copy of terra-nauvis/ whose D33 surface guard returns at once (earth_test.py's T14 control)."""
    shutil.copytree(MOD, dst)
    f = dst / "scripts" / "guards.lua"
    text = f.read_text(encoding="utf-8")
    head = "function M.surface_guard(surface)\n"
    if text.count(head) != 1:
        sys.exit("RESULT fail scripts/guards.lua has no single surface_guard to disable")
    f.write_text(text.replace(head, head + "  do return 0 end\n"), encoding="utf-8", newline="\n")


def prime_and_set(root, name, vals):
    """fh.py writes settings only into a modset that has run once (its mod-settings.dat): one dump-data run
    first, then the values. Nothing to write, nothing launched."""
    if not vals:
        return
    if RUNNER is None:
        wait_quiet(print)
    d = Path(root) / "stage" / "prime" / name
    res, _ = fh(["dump-data", "--instance", INSTANCE, "--modset", name, "--timeout", TIMEOUT, "--out", d])
    if not res.startswith("RESULT ok"):
        sys.exit(f"RESULT fail priming {name}: {res}")
    res, _ = fh(["settings", name, "--set"] + list(vals))
    if not res.startswith("RESULT ok"):
        sys.exit(f"RESULT fail settings {name}: {res}")


def cmd_stage(a):
    root = Path(a.root).resolve()
    if (root / "plan.json").exists():
        sys.exit(f"RESULT fail {root} already holds a plan.json; use a new --root")
    root.mkdir(parents=True, exist_ok=True)
    zpath = Path(a.zip).resolve()
    sha = sha256(zpath)
    ung = root / "stage" / "unguarded" / "terra-nauvis"
    stage_unguarded(ung)
    exp = ",".join(EXPANSION)
    short = sha[:8]
    pre = a.prefix
    live = [n for n in (a.live or "").split(",") if n]
    tail = ""
    if live or a.blocks != "standard":
        tail = "-" + hashlib.sha256(json.dumps([live, a.blocks]).encode()).hexdigest()[:6]
    sets = {
        "tn": (f"{pre}-1-{short}{tail}", [zpath, PROBE], exp),
        "twin": (f"{pre}-2-twin{tail}", [PROBE], exp),
        "ung": (f"{pre}-3-{short}u{tail}", [ung, PROBE], exp),
        "tn_base": (f"{pre}-4-{short}b{tail}", [zpath, PROBE], "none"),
    }
    results = {}
    for key, (name, mods, ex) in sets.items():
        extra = ["--from-live", ",".join(live)] if live else []
        res, _ = fh(["modset", name, "--add"] + mods + ["--expansion", ex] + extra)
        results[key] = res
        print(res)
        if not res.startswith("RESULT ok"):
            sys.exit(f"RESULT fail modset {name}: {res}")
    # a variant's settings written explicitly (G7): a wide block set on all, the --set values on the modsets
    # holding terra-nauvis (the twin defines no such setting); the standard run writes nothing, as before
    for key, (name, _, _) in sets.items():
        vals = ([f"runtime-global.ea-sa-probe-blocks={a.blocks}"] if a.blocks != "standard" else []) + \
            (list(a.set or []) if key != "twin" else [])
        prime_and_set(root, name, vals)
    cfg = load_cfg()
    plan = {"zip": str(zpath), "zip_sha256": sha, "probe": str(PROBE), "unguarded": str(ung), "seed": a.seed,
            "instance": INSTANCE, "expansion": EXPANSION, "modsets": {k: v[0] for k, v in sets.items()},
            "presets": [cfg["presets"][k]["name"] for k in cfg["preset_order"]], "stage_results": results,
            "live": live, "settings": list(a.set or []), "blocks": a.blocks}
    write_json(root / "plan.json", plan)
    print(f"RESULT ok staged {len(sets)} modsets zip_sha256={sha} root={root}")
    return 0


def cmd_stage_travel(a):
    """The travel pair (the probe's travel mode through the marker mod): planet surfaces from the
    engine's own creation when a platform enters orbit, with terra-nauvis and without."""
    root = Path(a.root).resolve()
    plan = read_json(root / "plan.json")
    if not plan:
        sys.exit(f"RESULT fail {root} has no plan.json; run stage first")
    marker = HERE / "mods" / "ea-sa-travel"
    short = plan["zip_sha256"][:8]
    exp = ",".join(EXPANSION)
    pre = plan["modsets"]["tn"].split("-1-")[0]
    tail = "l" if a.landing else ""
    live = plan.get("live") or []
    sets = {"tn_travel": (f"{pre}-5-{short}t{tail}", [Path(plan["zip"]), PROBE, marker]),
            "twin_travel": (f"{pre}-6-twin-t{tail}", [PROBE, marker])}
    for key, (name, mods) in sets.items():
        extra = ["--from-live", ",".join(live)] if live else []
        res, _ = fh(["modset", name, "--add"] + mods + ["--expansion", exp] + extra)
        print(res)
        if not res.startswith("RESULT ok"):
            sys.exit(f"RESULT fail modset {name}: {res}")
        vals = ([f"runtime-global.ea-sa-probe-blocks={plan['blocks']}"] if plan.get("blocks", "standard") != "standard"
                else []) + (["runtime-global.ea-sa-probe-landing=true"] if a.landing else [])
        vals += list(plan.get("settings") or []) if key == "tn_travel" else []
        prime_and_set(root, name, vals)
        plan["modsets"][key] = name
    plan["landing"] = bool(a.landing)
    write_json(root / "plan.json", plan)
    print(f"RESULT ok staged the travel pair root={root}")
    return 0


# ---------------------------------------------------------------- matrix

def lock_state():
    d = read_json(LOCK) if LOCK.exists() else None
    if not d or not d.get("pid"):
        return True, d
    import perf
    return (not perf.process_alive(d["pid"], d.get("start_time"))), d


def games_running():
    cp = subprocess.run(["tasklist", "/FI", "IMAGENAME eq factorio.exe", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, errors="replace")
    return [line for line in cp.stdout.splitlines() if line.lower().startswith('"factorio.exe"')]


def wait_quiet(log, poll=5, settle=3):
    """Wait until the lock is free and no factorio.exe runs, twice `settle` seconds apart, so another
    caller that saw the same gap and took the lock or launched meanwhile wins it."""
    if RUNNER is not None:
        return 0
    t0, last = time.time(), 0.0
    while True:
        free, d = lock_state()
        games = games_running()
        if free and not games:
            time.sleep(settle)
            free, d = lock_state()
            if free and not games_running():
                return round(time.time() - t0)
            continue
        if time.time() - last > 300:
            held = "free" if free else f"held by pid {d.get('pid')} ({d.get('cmd')}, since {d.get('since')})"
            log(f"waiting: lock {held}; {len(games)} factorio.exe running")
            last = time.time()
        time.sleep(poll)


def planets_of(dump):
    return sorted((dump or {}).get("planet", {}))


def maptype_mgs(root):
    """One --map-gen-settings file per map with a Map type entry: what the Terrain tab's Map type pick
    stores, elevation alone (S13), so the elevation-only route is checked on every planet too."""
    cfg = load_cfg()
    d = root / "mgs"
    d.mkdir(exist_ok=True)
    out = {}
    import tnconfig
    geo = tnconfig.geography(cfg)
    for key in cfg["map_order"]:
        g = geo.get(key)  # the map's newest geography version, whose entry is its Map type entry
        if not g:
            continue
        f = d / f"maptype-{key}.json"
        if not f.exists():
            write_json(f, {"property_expression_names": {cfg["keys"]["elevation"]: g["entry"]}})
        out[key] = f
    return out


VANILLA_ELEVATIONS = ["elevation_island", "elevation_lakes"]


def control_mgs(root, dump):
    """Build controls without terra-nauvis: an elevation-only MGS naming a vanilla body, which changes
    Nauvis alone (every other planet sets elevation itself), the vanilla analog of a Map type pick. A
    planet that differs here differs from any change to Nauvis, whichever mod or setting makes it."""
    d = root / "mgs"
    d.mkdir(exist_ok=True)
    known = set((dump or {}).get("noise-expression", {}))
    out = {}
    for name in VANILLA_ELEVATIONS:
        if name not in known:
            continue
        f = d / f"vanilla-{name}.json"
        if not f.exists():
            write_json(f, {"property_expression_names": {"elevation": name}})
        out[f"vanilla-{name}"] = f
    return out


def matrix_steps(plan, root, planets, maptypes=None, controls=None, quick=False):
    m, seed, runs = plan["modsets"], plan["seed"], root / "runs"
    inst = INSTANCE if RUNNER is not None else plan["instance"]
    steps = []

    def scenario(label, ms, save=None, mgs=None, ticks=TICKS):
        a = ["scenario", "--instance", inst, "--modset", ms, "--ticks", ticks, "--timeout", TIMEOUT]
        a += ["--save", save] if save else ["--seed", seed]
        a += ["--map-gen-settings", mgs] if mgs else []
        steps.append((label, a + ["--out", runs / label, "--", "--verbose"]))

    def create(label, ms, preset):
        d = runs / label
        steps.append((label, ["run", "--instance", inst, "--modset", ms, "--timeout", TIMEOUT, "--out", d, "--",
                              "--create", d / "p.zip", "--map-gen-seed", seed, "--preset", preset]))
        return d / "p.zip"

    def preview(label, ms, planet, preset=None):
        a = ["preview", "--instance", inst, "--modset", ms, "--seed", seed, "--seed-max", seed + 4, "--size",
             PREVIEW_SIZE, "--planet", planet, "--timeout", TIMEOUT, "--out", runs / label, "--", "--verbose"]
        steps.append((label, a + (["--preset", preset] if preset else [])))

    # Ordered by what decides the verdicts, since every step needs its own quiet gap: the real
    # generation runs first, then the previews that can leak (a preset on each planet), then the rest.
    scenario("scn-tn-default", m["tn"])
    scenario("scn-twin-default", m["twin"])
    for preset in plan["presets"]:
        save = create(f"create-tn-{preset}", m["tn"], preset)
        scenario(f"scn-tn-{preset}", m["tn"], save=save)
        # the same Earth world again: a planet that differs from itself is the engine's, not a leak
        scenario(f"scn-tn-{preset}-r2", m["tn"], save=save)
        if not quick:
            scenario(f"scn-ung-{preset}", m["ung"], save=create(f"create-ung-{preset}", m["ung"], preset))
    scenario("scn-twin-default-r2", m["twin"])
    for key, mgs in (maptypes or {}).items():
        scenario(f"scn-tn-maptype-{key}", m["tn"], mgs=mgs)
    if m.get("tn_travel") and m.get("twin_travel"):
        for preset in plan["presets"]:
            scenario(f"scn-tn-travel-{preset}", m["tn_travel"],
                     save=create(f"create-tn-travel-{preset}", m["tn_travel"], preset), ticks=TRAVEL_TICKS)
        scenario("scn-twin-travel", m["twin_travel"], ticks=TRAVEL_TICKS)
    for key, mgs in (controls or {}).items():
        scenario(f"scn-twin-{key}", m["twin"], mgs=mgs)
    if quick:
        return steps
    # Space Age enabled on an existing Earth save: created base-only, loaded with the expansion, so
    # on_configuration_changed runs with the expansion added before any planet surface exists
    for preset in plan["presets"]:
        scenario(f"scn-tn-addsa-{preset}", m["tn"], save=create(f"create-base-{preset}", m["tn_base"], preset))
    for planet in planets:
        preview(f"pv-twin-default-{planet}", m["twin"], planet)
        for preset in plan["presets"]:
            preview(f"pv-tn-{preset}-{planet}", m["tn"], planet, preset)
    for planet in planets:
        preview(f"pv-tn-default-{planet}", m["tn"], planet)
    for preset in plan["presets"]:
        preview(f"pv-base-{preset}-nauvis", m["tn_base"], "nauvis", preset)
    preview("pv-base-default-nauvis", m["tn_base"], "nauvis")
    return steps


def cmd_matrix(a):
    root = Path(a.root).resolve()
    plan = read_json(root / "plan.json")
    if not plan:
        sys.exit(f"RESULT fail {root} has no plan.json; run stage first")
    (root / "runs").mkdir(exist_ok=True)
    rec_path = root / "matrix.json"
    done = read_json(rec_path) or {}

    def log(msg):
        line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
        print(line, flush=True)
        with open(root / "matrix.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def step(label, args):
        if label in done:
            return done[label]["result"]
        waited = wait_quiet(log)
        t0 = time.time()
        res, text = fh(args)
        done[label] = {"result": res, "waited_s": waited, "wall_s": round(time.time() - t0, 1),
                       "args": [str(x) for x in args]}
        write_json(rec_path, done)
        log(f"{label}: {res} (waited {waited} s, {done[label]['wall_s']} s)")
        return res

    runs = root / "runs"
    m = plan["modsets"]
    inst = INSTANCE if RUNNER is not None else plan["instance"]
    step("dump-tn", ["dump-data", "--instance", inst, "--modset", m["tn"], "--timeout", TIMEOUT, "--out", runs / "dump-tn"])
    step("dump-twin", ["dump-data", "--instance", inst, "--modset", m["twin"], "--timeout", TIMEOUT,
                       "--out", runs / "dump-twin"])
    if not (root / "settings-tn.txt").exists():
        _, text = fh(["settings", m["tn"], "--show"])
        (root / "settings-tn.txt").write_text(text, encoding="utf-8")
    twin_dump = read_json(runs / "dump-twin" / "data-raw-dump.json")
    planets = planets_of(twin_dump)
    if not planets:
        sys.exit("RESULT fail the twin dump lists no planet")
    log(f"planets: {', '.join(planets)}")
    if a.quick:
        plan["quick"] = True
        write_json(root / "plan.json", plan)
    steps = matrix_steps(plan, root, planets, maptype_mgs(root), control_mgs(root, twin_dump), quick=bool(a.quick))
    del twin_dump
    for label, args in steps:
        step(label, args)
    bad = [k for k, v in done.items() if not v["result"].startswith("RESULT ok")]
    print(f"RESULT {'ok' if not bad else 'fail'} steps={len(done)} failed={','.join(bad) or 'none'} root={root}")
    return 0 if not bad else 1


# ---------------------------------------------------------------- report helpers

def run_ok(d):
    """G1 for one run directory: exit 0, isolated, no error line (scenario runs check both steps)."""
    rj = read_json(Path(d) / "run.json")
    if rj is None:
        return None, "not run"
    parts = [rj] + [rj[k] for k in ("create", "bench") if isinstance(rj.get(k), dict)]
    # scenario --save records its copy of the save as a create step that launched nothing
    parts = [p for p in parts if (p.get("cmd") or [""])[0] != "copied existing save"]
    for p in parts:
        if p.get("exit") != 0 or p.get("isolated") is not True or p.get("error_lines"):
            return False, f"exit={p.get('exit')} isolated={p.get('isolated')} errors={p.get('error_lines')[:3]}"
    return True, "ok"


def run_texts(d):
    """stdout and the copied game log of a run and of its create and bench steps: --benchmark-sanitize
    leaves the bench step's stdout with the final timings only, so its log lines are in the log file."""
    d = Path(d)
    out = []
    for sub in (d, d / "create", d / "bench"):
        for name in ("stdout.txt", "factorio-current.log"):
            f = sub / name
            if f.exists():
                out.append(f.read_text(encoding="utf-8", errors="replace"))
    return out


def warning_lines(d, names):
    """Warning and error lines of a run, without timestamps and with modset and run paths replaced, so
    lines of a run and its twin compare."""
    out = set()
    for text in run_texts(d):
        for line in text.splitlines():
            if not WARN_RE.search(line) or "Program arguments" in line:
                continue
            s = STAMP_RE.sub("", line).strip()
            for n in names:
                s = s.replace(n, "<modset>")
            s = re.sub(r"[A-Za-z]:[\\/][^\"' ]*", "<path>", s)
            out.add(s)
    return out


def mentions(d, needles):
    hits = []
    for text in run_texts(d):
        for line in text.splitlines():
            if any(n in line for n in needles) and "Program arguments" not in line:
                hits.append(STAMP_RE.sub("", line).strip())
    return hits


def programs(d, step="bench"):
    """Compiled noise program lines per probe segment: 'load' before any probe marker, then the surface
    whose creation or generation the probe last logged."""
    d = Path(d)
    base = d / step if (d / step).is_dir() else d
    f = base / "factorio-current.log"
    if not f.exists() or not f.stat().st_size:
        f = base / "stdout.txt"
    if not f.exists():
        return None
    out, seg, pending = {}, "load", []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        mk = MARK_RE.search(line)
        if mk:
            # travel mode logs its marker after the move, and the engine compiles the planet's programs
            # inside the move: those lines belong to the planet the marker names
            owner = mk.group(1) if "platform moved to" in line else seg
            out.setdefault(owner, []).extend(pending)
            pending, seg = [], mk.group(1)
            continue
        p = PROG_RE.search(line)
        if p:
            pending.append(p.group(0))
    out.setdefault(seg, []).extend(pending)
    return {k: v for k, v in out.items() if v}


def surface_programs(progs, surface):
    """A surface's compiled program lines; Nauvis's program compiles when the save loads, before any
    probe marker."""
    if progs is None:
        return None
    return (progs.get("load", []) if surface == "nauvis" else []) + progs.get(surface, [])


def last_by_kind(lines):
    """The last compile of each program (Tile, Entity, Cliff): the one generation used, should a settings
    write recompile a surface's programs."""
    out = {}
    for line in lines or []:
        out[PROG_RE.search(line).group(1)] = line
    return out


def as_dict(v):
    return v if isinstance(v, dict) else {}


def _resources_equal(runs, label, surface, block):
    """Resource totals (count and amount) of one block in an Earth world equal the twin's."""
    run = "scn-" + label.split(" vs ", 1)[0]
    a = probe_out(runs / run)["surfaces"].get(surface) or {}
    b = probe_out(runs / "scn-twin-default")["surfaces"].get(surface) or {}
    ta = as_dict(as_dict(as_dict(a.get("blocks")).get(block)).get("totals"))
    tb = as_dict(as_dict(as_dict(b.get("blocks")).get(block)).get("totals"))
    ra, rb = as_dict(ta.get("resource_amount")), as_dict(tb.get("resource_amount"))
    ea, eb = as_dict(ta.get("entities")), as_dict(tb.get("entities"))
    return ra == rb and all(ea.get(k) == eb.get(k) for k in set(ra) | set(rb))


def probe_out(d, prefix="surface-"):
    base = Path(d) / "script-output" / "ea-sa-probe"
    out = {"surfaces": {}, "summary": read_json(base / "summary.json"), "platform": read_json(base / "platform.json"),
           "travel": read_json(base / "travel.json")}
    if base.exists():
        for f in sorted(base.glob(f"{prefix}*.json")):
            r = read_json(f)
            out["surfaces"][r["surface"]] = r
    return out


def compare_surface(x, y):
    """Per block and chunk: tiles, entities and decoratives; then totals, sampled properties, the seed
    and property_expression_names after every guard."""
    res = {"equal": True, "blocks": {}, "props_equal": None, "pen_equal": None, "seed_equal": None}
    for block in sorted(set(as_dict(x.get("blocks"))) | set(as_dict(y.get("blocks")))):
        bx, by = as_dict(as_dict(x.get("blocks")).get(block)), as_dict(as_dict(y.get("blocks")).get(block))
        cx, cy = as_dict(bx.get("chunks")), as_dict(by.get("chunks"))
        diff = {"tiles": [], "entities": [], "decoratives": [], "missing": []}
        for k in sorted(set(cx) | set(cy)):
            p, q = cx.get(k), cy.get(k)
            if p is None or q is None:
                diff["missing"].append(k)
                continue
            if p["t"] != q["t"]:
                diff["tiles"].append(k)
            if p["e"] != q["e"] or p["en"] != q["en"]:
                diff["entities"].append(k)
            if p["d"] != q["d"] or p["dn"] != q["dn"]:
                diff["decoratives"].append(k)
        tx, ty = as_dict(bx.get("totals")), as_dict(by.get("totals"))
        totals_equal = all(as_dict(tx.get(t)) == as_dict(ty.get(t))
                           for t in ("tiles", "entities", "decoratives", "resource_amount"))
        chunks = len(set(cx) & set(cy))
        ok = not any(diff.values()) and totals_equal and bx.get("missing") == by.get("missing") and chunks > 0
        res["blocks"][block] = {"chunks": chunks, "missing_a": bx.get("missing"), "missing_b": by.get("missing"),
                                "totals_equal": totals_equal, "entities": sum(as_dict(tx.get("entities")).values()),
                                "decoratives": sum(as_dict(tx.get("decoratives")).values()),
                                "diff": {k: v[:12] for k, v in diff.items() if v},
                                "diff_counts": {k: len(v) for k, v in diff.items() if v}, "equal": ok}
        res["equal"] = res["equal"] and ok
    res["props_equal"] = as_dict(x.get("props")) == as_dict(y.get("props"))
    res["pen_equal"] = as_dict(x.get("pen")) == as_dict(y.get("pen"))
    res["seed_equal"] = x.get("seed") == y.get("seed")
    if not res["props_equal"]:
        res["props"] = {"a": x.get("props"), "b": y.get("props")}
    if not res["pen_equal"]:
        pa, pb = as_dict(x.get("pen")), as_dict(y.get("pen"))
        res["pen_diff"] = {k: [pa.get(k), pb.get(k)] for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)}
    res["generation_equal"] = res["equal"] and res["props_equal"] and res["seed_equal"]
    return res


def compare_runs(a, b, surfaces, prefix="surface-"):
    pa, pb = probe_out(a, prefix), probe_out(b, prefix)
    out, progs_a, progs_b = {}, programs(a), programs(b)
    for s in surfaces:
        x, y = pa["surfaces"].get(s), pb["surfaces"].get(s)
        if x is None or y is None:
            out[s] = {"generation_equal": None, "note": f"no digest ({'a' if x is None else 'b'})"}
            continue
        r = compare_surface(x, y)
        la, lb = surface_programs(progs_a, s), surface_programs(progs_b, s)
        ka, kb = last_by_kind(la), last_by_kind(lb)
        # None: neither log holds this surface's compile (Nauvis compiles in the create step, which
        # fh.py runs without --verbose); its previews compare the programs instead
        r["programs_equal"] = None if not ka and not kb else ka == kb
        r["program_lists_equal"] = la == lb
        r["programs"] = ka if r["programs_equal"] and r["program_lists_equal"] else {"a": la, "b": lb}
        out[s] = r
    return out


def preview_info(d):
    rj = read_json(Path(d) / "run.json")
    if rj is None:
        return None
    return {"images": rj.get("images") or {}, "ok": run_ok(d)[0], "programs": (programs(d, ".") or {}).get("load")}


# ---------------------------------------------------------------- names

def locale_keys(files):
    keys = {}
    for f in files:
        section = None
        for raw in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = raw.strip()
            if not line or line[0] in ";#":
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if "=" in line:
                keys.setdefault((section, line.split("=", 1)[0].strip()), []).append(f)
    return keys


def names_check(cfg, dump_tn, dump_twin, msd_tn, msd_twin):
    ident = cfg["identity"]
    prefix, sprefix, mid = ident["noise_prefix"], ident["setting_prefix"], ident["id"]
    added = {t: sorted(set(v) - set(dump_twin.get(t, {}))) for t, v in dump_tn.items()}
    added = {t: v for t, v in added.items() if v}
    removed = {t: sorted(set(v) - set(dump_tn.get(t, {}))) for t, v in dump_twin.items()}
    removed = {t: v for t, v in removed.items() if v}
    collisions = []
    for t in ("noise-expression", "noise-function", "autoplace-control"):
        for n in dump_tn.get(t, {}):
            if n.startswith(prefix) and n in dump_twin.get(t, {}):
                collisions.append(f"{t} {n}: defined without terra-nauvis too")
        for n in dump_twin.get(t, {}):
            if n.startswith(prefix):
                collisions.append(f"{t} {n}: the twin (base and expansion) defines a name in terra-nauvis' prefix")
    presets_tn = set(as_dict(dump_tn.get("map-gen-presets", {}).get("default")))
    presets_twin = set(as_dict(dump_twin.get("map-gen-presets", {}).get("default")))
    preset_names = [cfg["presets"][k]["name"] for k in cfg["preset_order"]]
    for n in preset_names:
        if n in presets_twin:
            collisions.append(f"map-gen-preset {n}: defined without terra-nauvis too")
    set_tn = {n for t in (msd_tn or {}).values() if isinstance(t, dict) for n in t}
    set_twin = {n for t in (msd_twin or {}).values() if isinstance(t, dict) for n in t}
    for n in sorted(set_tn & set_twin):
        if n.startswith(sprefix):
            collisions.append(f"setting {n}: defined without terra-nauvis too")
    mine = sorted(set_tn - set_twin)
    stray_settings = [n for n in mine if not n.startswith(sprefix)]
    twin_any = {}
    for t, v in dump_twin.items():
        for n in v:
            twin_any.setdefault(n, []).append(t)
    cross = {n: twin_any[n] for t, v in added.items() for n in v if n in twin_any}
    tn_loc = locale_keys(sorted((MOD / "locale").rglob("*.cfg")))
    game_loc = {}
    for mod in ["core", "base"] + EXPANSION:
        langs = {f.relative_to(MOD / "locale").parts[0] for f in (MOD / "locale").rglob("*.cfg")}
        files = [f for lang in sorted(langs) for f in sorted((GAME / "data" / mod / "locale" / lang).glob("*.cfg"))]
        for k, fs in locale_keys(files).items():
            game_loc.setdefault(k, set()).add(mod)
    loc_coll = {f"[{s}] {k}": sorted(game_loc[(s, k)]) for (s, k) in tn_loc if (s, k) in game_loc}
    for key, mods in loc_coll.items():
        collisions.append(f"locale {key}: also defined by {', '.join(mods)}")
    stray_noise = [n for t in ("noise-expression", "noise-function") for n in added.get(t, []) if not n.startswith(prefix)]
    other_added = {t: v for t, v in added.items() if t not in ("noise-expression", "noise-function")}
    return {"collisions": collisions, "added": {t: len(v) for t, v in added.items()},
            "added_other_types": other_added, "removed_vs_twin": removed, "stray_noise_names": stray_noise,
            "settings_added": mine, "stray_settings": stray_settings, "presets_added": sorted(presets_tn - presets_twin),
            "cross_namespace_info": cross, "locale_keys_checked": len(tn_loc), "game_locale_keys": len(game_loc)}


def dump_diff(cfg, dump_tn, dump_twin):
    """Every prototype in both dumps but terra-nauvis' own must be equal; map-gen-presets compares its
    entries without terra-nauvis' presets."""
    prefix = cfg["identity"]["noise_prefix"]
    preset_names = {cfg["presets"][k]["name"] for k in cfg["preset_order"]}
    differ, compared = [], 0
    for t in sorted(set(dump_tn) & set(dump_twin)):
        a, b = dump_tn[t], dump_twin[t]
        for n in sorted(set(a) & set(b)):
            x, y = a[n], b[n]
            if t == "map-gen-presets":
                x = {k: v for k, v in as_dict(x).items() if k not in preset_names}
                y = {k: v for k, v in as_dict(y).items()}
            compared += 1
            if json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True):
                keys = sorted(k for k in set(as_dict(x)) | set(as_dict(y)) if as_dict(x).get(k) != as_dict(y).get(k))
                differ.append(f"{t}/{n}: {keys[:8]}")
    only_tn = [f"{t}/{n}" for t in dump_tn for n in dump_tn[t] if n not in dump_twin.get(t, {})]
    earth = [s for s in only_tn if s.split("/", 1)[1].startswith(prefix)]
    return {"compared": compared, "differ": differ, "only_tn": len(only_tn), "only_tn_earth": len(earth),
            "only_tn_not_earth": [s for s in only_tn if s not in earth],
            "only_twin": [f"{t}/{n}" for t in dump_twin for n in dump_twin[t] if n not in dump_tn.get(t, {})]}


# ---------------------------------------------------------------- report

def cmd_report(a):
    root = Path(a.root).resolve()
    plan = read_json(root / "plan.json")
    runs = root / "runs"
    cfg = load_cfg()
    ident = cfg["identity"]
    m = plan["modsets"]
    needles = [ident["id"], ident["title"], ident["noise_prefix"]]
    rep = {"plan": plan, "checks": {}}
    dump_tn = read_json(runs / "dump-tn" / "data-raw-dump.json")
    dump_twin = read_json(runs / "dump-twin" / "data-raw-dump.json")
    planets = planets_of(dump_twin)
    others = [p for p in planets if p != "nauvis"]
    presets = plan["presets"]
    maptypes = [k for k in cfg["map_order"] if cfg["geography"].get(k)]
    addsa = [p for p in presets if read_json(runs / f"scn-tn-addsa-{p}" / "run.json")]

    # 1 load
    tn_runs = ["dump-tn", "scn-tn-default"] + [f"create-tn-{p}" for p in presets] + [f"scn-tn-{p}" for p in presets]
    tn_runs += [f"scn-tn-maptype-{k}" for k in maptypes] + [f"scn-tn-addsa-{p}" for p in addsa]
    twin_runs = ["dump-twin", "scn-twin-default", "scn-twin-default-r2"]
    g1 = {r: run_ok(runs / r)[1] for r in tn_runs + twin_runs}
    tn_warn = set().union(*[warning_lines(runs / r, list(m.values())) for r in tn_runs])
    twin_warn = set().union(*[warning_lines(runs / r, list(m.values())) for r in twin_runs])
    naming = sorted(w for w in tn_warn if any(n in w for n in needles))
    new_warn = sorted(tn_warn - twin_warn)
    locale_bad = [h for r in tn_runs for h in mentions(runs / r, ["Unknown key", "Failed to load locale"])]
    one = {"runs": g1, "warnings_naming_terra_nauvis": naming, "warnings_new_vs_twin": new_warn,
           "locale_errors": locale_bad[:10],
           "terra_nauvis_log_lines": sorted(set(h for r in tn_runs for h in mentions(runs / r, ["Terra Nauvis",
                                                                                              "terra-nauvis:"])))[:20]}
    if dump_tn and dump_twin:
        one["dump_diff"] = dump_diff(cfg, dump_tn, dump_twin)
        pen = as_dict(as_dict(dump_tn.get("map-gen-presets", {}).get("default")).get(presets[0], {})
                      .get("basic_settings")).get("property_expression_names")
        one["preset_pen"] = pen
        # every key any preset bakes must be one the D33 guard strips (config.lua preset_keys); the list also
        # holds keys that only other presets or Alien Biomes worlds bake, so it is a superset, never equal
        unlisted = {}
        for name in presets:
            pp = as_dict(as_dict(as_dict(dump_tn.get("map-gen-presets", {}).get("default")).get(name, {})
                                 .get("basic_settings")).get("property_expression_names"))
            miss = sorted(set(pp) - set(cfg["preset_keys"]))
            if miss or not pp:
                unlisted[name] = miss or ["(the preset bakes no key)"]
        one["preset_keys_unlisted"] = unlisted
        one["preset_keys_match_config"] = bool(pen) and not unlisted
    msd_tn = read_json(runs / "dump-tn" / "mod-settings-dump.json")
    msd_twin = read_json(runs / "dump-twin" / "mod-settings-dump.json")
    one["settings_defined"] = sorted(n for t in as_dict(msd_tn).values() if isinstance(t, dict) for n in t
                                     if n.startswith(ident["setting_prefix"]))
    one["settings_stored"] = (root / "settings-tn.txt").read_text(encoding="utf-8")[-1500:] \
        if (root / "settings-tn.txt").exists() else None
    dd = one.get("dump_diff") or {}
    one["pass"] = (all(v == "ok" for v in g1.values()) and not naming and not locale_bad and bool(dd)
                   and not dd.get("differ") and not dd.get("only_twin") and not dd.get("only_tn_not_earth")
                   and one.get("preset_keys_match_config") is True and len(one["settings_defined"]) > 0)
    rep["checks"]["1_load"] = one

    # 2 planets (and the controls)
    two = {"planets": planets, "comparisons": {}}
    pairs = {"tn-default vs twin": ("scn-tn-default", "scn-twin-default"),
             "twin-r2 vs twin (determinism)": ("scn-twin-default-r2", "scn-twin-default")}
    for p in presets:
        pairs[f"tn-{p} vs twin"] = (f"scn-tn-{p}", "scn-twin-default")
        pairs[f"unguarded-{p} vs twin (positive control)"] = (f"scn-ung-{p}", "scn-twin-default")
        if read_json(runs / f"scn-tn-{p}-r2" / "run.json"):
            pairs[f"tn-{p}-r2 vs tn-{p} (Earth determinism)"] = (f"scn-tn-{p}-r2", f"scn-tn-{p}")
    for k in maptypes:
        pairs[f"tn-maptype-{k} vs twin"] = (f"scn-tn-maptype-{k}", "scn-twin-default")
    for p in addsa:
        pairs[f"tn-addsa-{p} vs twin"] = (f"scn-tn-addsa-{p}", "scn-twin-default")
    controls =[f"vanilla-{n}" for n in VANILLA_ELEVATIONS if read_json(runs / f"scn-twin-vanilla-{n}" / "run.json")]
    for k in controls:
        pairs[f"{k} vs twin (engine control)"] = (f"scn-twin-{k}", "scn-twin-default")
    for label, (x, y) in pairs.items():
        two["comparisons"][label] = compare_runs(runs / x, runs / y, planets)
    # Which planets differ only in entity placement while their settings, programs, tiles, decoratives and
    # sampled properties match: the residue a change to Nauvis alone leaves, measured without terra-nauvis
    # by the Build controls.
    residue = {}
    for label, c in two["comparisons"].items():
        for s in others:
            r = c.get(s) or {}
            if r.get("generation_equal") is False:
                kinds = sorted({k for b in (r.get("blocks") or {}).values() for k in (b.get("diff_counts") or {})})
                residue.setdefault(s, {})[label] = {
                    "kinds": kinds, "settings_equal": r.get("pen_equal"), "programs_equal": r.get("programs_equal"),
                    "props_equal": r.get("props_equal"),
                    "chunks": {b: v.get("diff") for b, v in (r.get("blocks") or {}).items() if v.get("diff")}}
    two["differences"] = residue
    two["engine_controls"] = controls
    # A leak: a guarded Earth world's planet differs in settings, compiled programs, sampled properties,
    # tiles, decoratives or resources. An entity-only difference (no resource total moved) is engine
    # residue when an engine control without terra-nauvis differs in the same chunk of the same planet.
    earth_labels = [f"tn-{p} vs twin" for p in presets] + [f"tn-maptype-{k} vs twin" for k in maptypes]
    earth_labels += [f"tn-addsa-{p} vs twin" for p in addsa]
    leaks, explained = [], []
    for s, d in residue.items():
        control_chunks = {(b, ch) for lab, v in d.items() if lab.endswith("(engine control)")
                          for b, kinds in v["chunks"].items() for ch in kinds.get("entities", [])}
        for lab in earth_labels:
            v = d.get(lab)
            if not v:
                continue
            c = two["comparisons"][lab][s]
            res_equal = all(as_dict(as_dict(c.get("blocks")).get(b)).get("totals_equal") or
                            _resources_equal(runs, lab, s, b) for b in as_dict(c.get("blocks")))
            chunks = {(b, ch) for b, kinds in v["chunks"].items() for ch in kinds.get("entities", [])}
            entity_only = v["kinds"] == ["entities"] and v["settings_equal"] and v["programs_equal"] is not False \
                and v["props_equal"] and res_equal
            if entity_only and chunks and chunks <= control_chunks:
                explained.append(f"{s} {lab}: entities in {sorted(chunks)}, also moved by {', '.join(controls)}")
            else:
                leaks.append(f"{s} {lab}: {v}")
    two["leaks"], two["engine_residue"] = leaks, explained
    det = two["comparisons"]["twin-r2 vs twin (determinism)"]
    two["determinism_holds"] = all((det.get(s) or {}).get("generation_equal") for s in planets)
    # an Earth world against itself: a planet differing here is nondeterminism, which fails as surely as a leak
    # but names its cause
    two["earth_determinism"] = {
        p: {s: (two["comparisons"][f"tn-{p}-r2 vs tn-{p} (Earth determinism)"].get(s) or {}).get("generation_equal")
            for s in planets}
        for p in presets if f"tn-{p}-r2 vs tn-{p} (Earth determinism)" in two["comparisons"]}
    two["determinism_holds"] = two["determinism_holds"] and all(
        v is not False for per in two["earth_determinism"].values() for v in per.values())

    def planets_equal(label):
        c = two["comparisons"][label]
        return all((c.get(s) or {}).get("generation_equal") is True and (c.get(s) or {}).get("programs_equal") is True
                   for s in others)

    def planets_clean(label):
        """Equal but for engine residue: settings, programs and properties equal on every planet."""
        c = two["comparisons"][label]
        return all((c.get(s) or {}).get("pen_equal") is True and (c.get(s) or {}).get("programs_equal") is True
                   and (c.get(s) or {}).get("props_equal") is True for s in others)

    two["equal_default"] = planets_equal("tn-default vs twin")
    two["equal_presets"] = {p: planets_equal(f"tn-{p} vs twin") for p in presets}
    two["equal_presets"].update({f"maptype-{k}": planets_equal(f"tn-maptype-{k} vs twin") for k in maptypes})
    two["clean_presets"] = {p: planets_clean(f"tn-{p} vs twin") for p in presets}
    two["clean_presets"].update({f"maptype-{k}": planets_clean(f"tn-maptype-{k} vs twin") for k in maptypes})
    two["clean_presets"].update({f"addsa-{p}": planets_clean(f"tn-addsa-{p} vs twin") for p in addsa})
    pos = {}
    for p in presets:
        c = two["comparisons"][f"unguarded-{p} vs twin (positive control)"]
        pos[p] = {s: {"pen_differs": (c.get(s) or {}).get("pen_equal") is False,
                      "props_differ": (c.get(s) or {}).get("props_equal") is False,
                      "programs_differ": (c.get(s) or {}).get("programs_equal") is False,
                      "tiles_entities_decoratives_differ": (c.get(s) or {}).get("equal") is False} for s in others}
    two["positive_control"] = pos
    guard = {}
    for p in presets:
        po = probe_out(runs / f"scn-tn-{p}")
        default = as_dict((po["summary"] or {}).get("default_pen"))
        for s in others:
            r = po["surfaces"].get(s) or {}
            before, after = as_dict(r.get("pen_before_guard")), as_dict(r.get("pen"))
            guard[f"{p}/{s}"] = {
                "inherited_before_guard": sorted(k for k in before if k in default and before[k] == default[k]),
                "earth_keys_after_guard": sorted(k for k in after if k in default and after[k] == default[k]),
                "created_tick": r.get("created_tick")}
        plat = dict(po["platform"] or {})
        plat["earth_keys_after_guard"] = sorted(k for k, v in as_dict(plat.get("pen")).items()
                                                if k in default and v == default[k])
        plat["inherited_before_guard"] = sorted(k for k, v in as_dict(plat.get("pen_before_guard")).items()
                                                if k in default and v == default[k])
        guard[f"{p}/platform"] = plat
    two["guard"] = guard
    pv = {}
    for planet in planets:
        tw = preview_info(runs / f"pv-twin-default-{planet}")
        row = {"twin": tw and sorted(tw["images"].values())}
        for label in ["default"] + presets:
            info = preview_info(runs / f"pv-tn-{label}-{planet}")
            if info is None or tw is None:
                row[label] = "not run"
                continue
            row[label] = {"ok": info["ok"], "images_equal_twin": info["images"] == tw["images"],
                          "programs_equal_twin": info["programs"] == tw["programs"]}
            if not row[label]["programs_equal_twin"]:
                row[label]["programs"] = {"tn": (info["programs"] or [])[:3], "twin": (tw["programs"] or [])[:3]}
        pv[planet] = row
    two["previews"] = pv
    travel = {}
    tw_t = runs / "scn-twin-travel"
    for p in presets:
        tn_t = runs / f"scn-tn-travel-{p}"
        if not (read_json(tn_t / "run.json") and read_json(tw_t / "run.json")):
            continue
        c = compare_runs(tn_t, tw_t, others, prefix="travel-surface-")
        po, pt = probe_out(tn_t, "travel-surface-"), probe_out(tw_t, "travel-surface-")
        default = as_dict((po["summary"] or {}).get("default_pen"))
        info = {"tn": po["travel"], "twin": pt["travel"], "comparisons": c, "guard": {}}
        for s in others:
            r = po["surfaces"].get(s) or {}
            before, after = as_dict(r.get("pen_before_guard")), as_dict(r.get("pen"))
            info["guard"][s] = {"earth_keys_before_guard": sorted(k for k in before if k.startswith(ident["noise_prefix"])
                                                                  or k in ("distance", "starting_resources_lake_mask")),
                                "earth_keys_after_guard": sorted(k for k in after if k.startswith(ident["noise_prefix"])
                                                                 or k in ("distance", "starting_resources_lake_mask"))}
        info["surfaces_created_by_engine"] = sorted(po["surfaces"])
        info["equal"] = bool(po["surfaces"]) and all(
            (c.get(s) or {}).get("generation_equal") is True for s in po["surfaces"] if s in others) and \
            sorted(po["surfaces"]) == sorted(pt["surfaces"])
        info["ok"] = run_ok(tn_t)[1], run_ok(tw_t)[1]
        travel[p] = info
    two["travel"] = travel or "not run"
    platforms_ok = all((guard.get(f"{p}/platform") or {}).get("ok") is True for p in presets)
    two["pass"] = (bool(others) and two["determinism_holds"] and two["equal_default"]
                   and all(two["clean_presets"].values()) and not two["leaks"] and bool(controls)
                   and all(not g.get("earth_keys_after_guard") for g in guard.values()) and platforms_ok)
    rep["checks"]["2_planets"] = two

    # 3 Nauvis
    three = {}
    c0 = two["comparisons"]["tn-default vs twin"].get("nauvis") or {}
    three["default_world_equals_twin"] = c0.get("generation_equal") is True and c0.get("programs_equal") is not False
    three["presets"] = {}
    for p in presets:
        c = two["comparisons"][f"tn-{p} vs twin"].get("nauvis") or {}
        po = probe_out(runs / f"scn-tn-{p}")
        spawn = (po["surfaces"].get("nauvis") or {}).get("spawn")
        pv_sa = preview_info(runs / f"pv-tn-{p}-nauvis")
        pv_base = preview_info(runs / f"pv-base-{p}-nauvis")
        pv_twin = preview_info(runs / "pv-twin-default-nauvis")
        three["presets"][p] = {
            "nauvis_differs_from_twin": c.get("equal") is False,
            "spawn": spawn,
            "spawn_on_land": bool(spawn) and spawn.get("blocking_within_12") == 0,
            "preview_differs_from_twin": None if plan.get("quick") else
            (bool(pv_sa and pv_twin) and pv_sa["images"] != pv_twin["images"]),
            "preview_equals_base_only": bool(pv_sa and pv_base) and pv_sa["images"] == pv_base["images"],
            "programs_equal_base_only": bool(pv_sa and pv_base) and pv_sa["programs"] == pv_base["programs"],
            "start_lines": [h for h in mentions(runs / f"create-tn-{p}", ["Spawn city", "spawn city"])][:3]}
    for k in maptypes:
        c = two["comparisons"][f"tn-maptype-{k} vs twin"].get("nauvis") or {}
        spawn = (probe_out(runs / f"scn-tn-maptype-{k}")["surfaces"].get("nauvis") or {}).get("spawn")
        three["presets"][f"maptype-{k}"] = {
            "nauvis_differs_from_twin": c.get("equal") is False, "spawn": spawn,
            "spawn_on_land": bool(spawn) and spawn.get("blocking_within_12") == 0,
            "preview_differs_from_twin": None,
            "notice_lines": mentions(runs / f"scn-tn-maptype-{k}" / "create", ["map type alone"])[:3]}
    for p in addsa:
        c = two["comparisons"][f"tn-addsa-{p} vs twin"].get("nauvis") or {}
        spawn = (probe_out(runs / f"scn-tn-addsa-{p}")["surfaces"].get("nauvis") or {}).get("spawn")
        three["presets"][f"addsa-{p}"] = {
            "nauvis_differs_from_twin": c.get("equal") is False, "spawn": spawn,
            "spawn_on_land": bool(spawn) and spawn.get("blocking_within_12") == 0, "preview_differs_from_twin": None,
            "configuration_changed_lines": mentions(runs / f"scn-tn-addsa-{p}", ["guard removed", "Terra Nauvis:"])[:6]}
    pvd = preview_info(runs / "pv-tn-default-nauvis")
    pvt = preview_info(runs / "pv-twin-default-nauvis")
    three["default_preview_equals_twin"] = None if plan.get("quick") else (bool(pvd and pvt) and
                                                                          pvd["images"] == pvt["images"])
    three["pass"] = (three["default_world_equals_twin"] and three["default_preview_equals_twin"] is not False
                     and all(v["nauvis_differs_from_twin"] and v["spawn_on_land"]
                             and v["preview_differs_from_twin"] is not False for v in three["presets"].values()))
    rep["checks"]["3_nauvis"] = three

    # 4 names
    if dump_tn and dump_twin:
        four = names_check(cfg, dump_tn, dump_twin, msd_tn, msd_twin)
        four["pass"] = (not four["collisions"] and not four["stray_noise_names"] and not four["stray_settings"]
                        and not four["removed_vs_twin"])
    else:
        four = {"pass": None, "note": "a dump is missing"}
    rep["checks"]["4_names"] = four

    write_json(root / "report.json", rep)
    for k, v in rep["checks"].items():
        print(f"{k}: {'PASS' if v.get('pass') else ('NOT RUN' if v.get('pass') is None else 'FAIL')}")
    print(f"RESULT {'ok' if all(v.get('pass') for v in rep['checks'].values()) else 'fail'} "
          f"report={root / 'report.json'}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--zip", required=True)
    s.add_argument("--root", required=True)
    s.add_argument("--seed", type=int, default=1000)
    s.add_argument("--prefix", default="ea-sa", help="modset name prefix (one per variant)")
    s.add_argument("--live", default="", help="comma list of live mods every modset copies (fh.py --from-live)")
    s.add_argument("--set", action="append", help="a startup setting for the modsets holding terra-nauvis")
    s.add_argument("--blocks", default="standard", choices=["standard", "wide"], help="the probe's block set")
    s.set_defaults(fn=cmd_stage)
    st = sub.add_parser("stage-travel")
    st.add_argument("--root", required=True)
    st.add_argument("--landing", action="store_true", help="send a cargo pod down to every planet the platform reaches")
    st.set_defaults(fn=cmd_stage_travel)
    mx = sub.add_parser("matrix")
    mx.add_argument("--root", required=True)
    mx.add_argument("--quick", action="store_true",
                    help="the real-generation runs only: no previews, no unguarded copy, no expansion-added save")
    mx.set_defaults(fn=cmd_matrix)
    r = sub.add_parser("report")
    r.add_argument("--root", required=True)
    r.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
