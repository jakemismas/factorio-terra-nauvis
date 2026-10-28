#!/usr/bin/env python3
"""Game-backed self-tests of the S8 tools, run through tools/fh.py only.

Each test uses instance ea-s8 and its own content-hashed ea-s8-* modset, writes a new run directory under
--out-root, and checks the fh.py RESULT line says isolated=yes before trusting any output.

  python mod/tools/game_selftest.py --out-root previews/earth-build/s8/gst-1 [--only t1,grid,sheet,oracle,dump,nav]
  python mod/tools/game_selftest.py --out-root <copy of a finished run> --replay

--replay re-derives every test's verdict from the game outputs a finished run left under --out-root,
launching nothing: each game command (fh.py preview, sample, scenario, run and dump-data, oracle.py
probe and dump_render's scenario runs) returns the RESULT line rebuilt from that run's own run.json,
and every check after it runs the committed code over the stored outputs again. The gate replays a
scratch copy of the suite's run (rule 2: it trusts no verdict file, game-selftest.json included); a
replay refuses a folder inside the runner's evidence tree (previews/earth-build), whose analysis files
and game-selftest.json it would rewrite.

A relative --out-root is the workspace's, from any working directory: it is joined onto FACTORIO_WS
before the live-profile refusal, so the path checked is the path written. A game run that may have
left its instance (tnguard.run_breach) stops every further game run at once (exit 3).

Tests:
  t1      fh.py sample of ep_s8_x, ep_s8_y and ep_s8_disc (mods/ep-s8-probe) on a synthetic 160 x 128
          reference at scales 3 and 6: every grid point must sit on the tile the plan predicted, and
          the T1 metric of the disc against its own analytic reference must be exactly 1.0
  grid    ep-s8-dump grid mode: the synthetic disc at scale 3, and all of Europe at scale 6 in one run
  sheet   a real preview of mods/ep-s8-disc-world scored by the T1 preview mode, and contact sheets
  oracle  oracle.py check through one fh.py sample run and one ep-s8-dump points probe
  dump    ep-s8-dump on a vanilla 256 x 256 area at seed 1000, rendered, and compared tile for tile
          with a vanilla preview of the same area
  nav     nav.py channel and walkability checks on that dump
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import earthgeo as eg  # noqa: E402
import t1_metrics as t1  # noqa: E402
import tnguard  # noqa: E402

if __name__ == "__main__":
    # contact_sheet, oracle and dump_render `import game_selftest` for INSTANCE and NAMES; without
    # this alias they would get a second, empty copy of this module.
    sys.modules["game_selftest"] = sys.modules[__name__]

WS = eg.WS
# Hard rule 1: build instances and modsets are named ea-*; planning's ep-s8 sets stay untouched.
# Each modset name carries the sha256 prefix of the mod folders it holds, so a changed test mod
# always gets a new modset (fh.py refuses --add over a copy holding files the source dropped).
INSTANCE = "ea-s8"
MODS = HERE / "mods"
SAMPLER = WS / "tools" / "probe-mods" / "fh-sampler"
NAMES = {}
RESULTS = []


def folder_hash(*dirs):
    h = __import__("hashlib").sha256()
    for d in dirs:
        d = Path(d)
        for p in sorted(q for q in d.rglob("*") if q.is_file()):
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:8]


def setup_modsets(replay=False):
    """Create every modset the game self-tests use, once, under content-hashed ea- names (a replay
    only names them: it launches nothing and needs no modset)."""
    sets = {"probe": [SAMPLER, MODS / "ep-s8-probe"],
            "probe_dump": [MODS / "ep-s8-probe", MODS / "ep-s8-dump"],
            # no settings-defining mod here: the disc preview must run without fh.py's stored-settings WARN
            "disc": [MODS / "ep-s8-probe", MODS / "ep-s8-disc-world"],
            "dump": [MODS / "ep-s8-dump"]}
    for key, dirs in sets.items():
        name = f"ea-s8-{key.replace('_', '-')}-{folder_hash(*dirs)}"
        if not replay:
            code, so, res = run([eg.FH, "modset", name, "--add"] + dirs, f"modset {name}")
            if not res.startswith("RESULT ok"):
                sys.exit(f"RESULT fail could not create modset {name}: {res}")
        NAMES[key] = name
    return NAMES


# fh.py subcommands that launch the game; each needs the runner's guard bracket (design constraint 1)
FH_GAME_COMMANDS = {"preview", "sample", "scenario", "run", "dump-data"}
# Set by --replay: game commands are answered from the stored run's run.json instead of launched.
REPLAY = {"on": False}


def replayed_result(out_dir, label):
    """(exit code, stdout, RESULT line) of a stored game run, rebuilt from its run.json the way
    fh.py's finish() prints them; a run directory without run.json replays as a failure."""
    rj = Path(out_dir) / "run.json"
    if not rj.exists():
        res = f"RESULT fail replay: no run.json in {out_dir}"
        print(f"[{label}] {res}")
        return 1, "", res
    meta = json.loads(rj.read_text(encoding="utf-8"))
    errors = meta.get("error_lines") or []
    ok = meta.get("exit") == 0 and meta.get("isolated") is not False and not errors
    iso = {True: "yes", False: "NO", None: "unknown"}[meta.get("isolated")]
    res = (f"RESULT {'ok' if ok else 'fail'} replayed exit={meta.get('exit')} isolated={iso} errors={len(errors)} "
           f"out={out_dir}")
    so = "".join(f"  WARN: {w}\n" for w in meta.get("warnings") or []) + res + "\n"
    print(f"[{label}] {res}")
    return (0 if ok else 1), so, res


def _out_arg(args):
    a = [str(x) for x in args]
    return a[a.index("--out") + 1] if "--out" in a and a.index("--out") + 1 < len(a) else None


def run(args, label):
    """Run a Python tool from the workspace; return (exit code, stdout, RESULT line). A game launch
    through fh.py runs only inside tools/earth_test.py's guard bracket (tnguard); under --replay it
    is answered from its stored run directory instead, and nothing is launched."""
    game = bool(args) and ((str(args[0]) == str(eg.FH) and len(args) > 1 and str(args[1]) in FH_GAME_COMMANDS) or
                           (Path(str(args[0])).name == "oracle.py" and len(args) > 1 and str(args[1]) == "probe"))
    if game and REPLAY["on"]:
        out = _out_arg(args)
        return replayed_result(out, label) if out else (1, "", "RESULT fail replay: the command names no --out")
    if args and str(args[0]) == str(eg.FH) and len(args) > 1 and str(args[1]) in FH_GAME_COMMANDS:
        tnguard.require_bracket(f"game_selftest.py ({label})")
    cp = subprocess.run([sys.executable] + [str(a) for a in args], cwd=WS, capture_output=True, text=True)
    lines = [l for l in cp.stdout.splitlines() if l.startswith("RESULT ")]
    res = lines[-1] if lines else "RESULT none"
    print(f"[{label}] {res}")
    if cp.returncode != 0 and not lines:
        print(cp.stdout[-2000:], cp.stderr[-2000:])
    if game:
        # a run that may have left its instance stops every further game run at once (design
        # constraint 1): a later one would only repeat its writes; the runner's guard check follows
        why = tnguard.run_breach(_out_arg(args), res)
        if why:
            print(f"RESULT fail game_selftest.py stops every further game run: [{label}] {why}", flush=True)
            sys.exit(3)
    return cp.returncode, cp.stdout, res


def record(name, ok, detail):
    RESULTS.append({"test": name, "ok": bool(ok), "detail": detail})
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: {detail}")


def isolated(result_lines):
    return all("isolated=yes" in l for l in result_lines)


# ------------------------------------------------------------------------------------------------

SYN_W, SYN_H, SYN_R = 160, 128, 200


def synthetic_disc_reference(scale, origin="floor"):
    """Land where 200 - |p| >= 0 at the integer corner of each pixel-centre tile."""
    wr, hr = int((SYN_W + 0.5) // 2), int((SYN_H + 0.5) // 2)
    tx = eg.pixel_centre_tiles(np.arange(SYN_W), wr, scale, origin).astype(float)
    ty = eg.pixel_centre_tiles(np.arange(SYN_H), hr, scale, origin).astype(float)
    land = (SYN_R - np.sqrt(tx[None, :] ** 2 + ty[:, None] ** 2)) >= 0
    return land, wr, hr


def test_t1(out_root):
    out = {}
    ms = NAMES["probe"]
    for scale in ("3", "6"):
        land, wr, hr = synthetic_disc_reference(scale)
        ref_png = out_root / f"t1-synth-s{scale}-land.png"
        ref_png.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(land).save(ref_png)
        mref = eg.MapRef(land=land, wr=wr, hr=hr)
        blocks = t1.plan_blocks(mref, scale)
        runs, lines = [], []
        for i, b in enumerate(blocks):
            rd = out_root / f"t1-s{scale}-b{i:02d}"
            code, so, res = run([eg.FH, "sample", "--instance", INSTANCE, "--modset", ms,
                                 "--names", "ep_s8_x,ep_s8_y,ep_s8_disc", "--seed", "1000",
                                 "--size", b["size"], "--step", b["step"],
                                 "--center", f"{b['center'][0]},{b['center'][1]}", "--out", rd], f"sample s{scale} b{i}")
            lines.append(res)
            runs.append(rd)
        record(f"t1_s{scale}_isolated", isolated(lines), "; ".join(lines))
        # Grid positions: the sampled x and y must equal the tile the mapping predicts per pixel.
        bad = covered = 0
        for rd in runs:
            d = t1.read_sample_json(rd)
            rows, cols, vx, _ = t1.map_sample(mref, d, "ep_s8_x", scale, "floor")
            _, _, vy, _ = t1.map_sample(mref, d, "ep_s8_y", scale, "floor")
            want_x = eg.pixel_centre_tiles(cols, wr, scale)[None, :]
            want_y = eg.pixel_centre_tiles(rows, hr, scale)[:, None]
            bad += int((vx != want_x).sum() + (vy != want_y).sum())
            covered += vx.size
        record(f"t1_s{scale}_grid_positions", bad == 0 and covered == SYN_W * SYN_H,
               f"{covered} pixels covered, {bad} sampled x or y values off the predicted tile")
        # Metric: the disc against its analytic reference is exact. Against a reference drawn with
        # EarthMaps' half-pixel placement it is not, and every error sits on the coast.
        em_land, _, _ = synthetic_disc_reference(scale, "earthmaps")
        em_png = out_root / f"t1-synth-s{scale}-land-earthmaps.png"
        Image.fromarray(em_land).save(em_png)
        for refname, png, want_exact in (("own_reference", ref_png, True), ("earthmaps_reference", em_png, False)):
            js = out_root / f"t1-s{scale}-{refname}.json"
            code, so, res = run([HERE / "t1_metrics.py", "sample", "--ref-land", png, "--wr", wr, "--hr", hr,
                                 "--scale", scale, "--name", "ep_s8_disc",
                                 "--runs"] + runs + ["--out-json", js, "--overlay", js.with_suffix(".png")],
                                f"t1 s{scale} {refname}")
            r = json.loads(js.read_text(encoding="utf-8"))
            cd = r["coast_deviation_px"]
            ok = (r["pixel_agreement"] == 1.0) if want_exact else (r["pixel_agreement"] < 1.0 and cd["max"] <= 0.75)
            record(f"t1_s{scale}_{refname}", ok, f"agreement {r['pixel_agreement']} misclassified "
                   f"{cd['misclassified']} coast max {cd['max']}")
        out[scale] = runs
    return out


def test_grid(out_root):
    """ep-s8-dump grid mode: (a) the synthetic disc at scale 3 scores exactly 1.0 like the sample
    mode; (b) all of Europe at scale 6 in one run, every one of its 4,089,600 grid bits equal to the
    analytic disc at the planned tiles."""
    import dump_render
    land, wr, hr = synthetic_disc_reference("3")
    ref_png = out_root / "grid-synth-s3-land.png"
    Image.fromarray(land).save(ref_png)
    mref = eg.MapRef(land=land, wr=wr, hr=hr)
    g = t1.plan_grid(mref, "3")
    rd = out_root / "grid-synth-s3"
    code, res, f, so = dump_render.run_dump(INSTANCE, NAMES["probe_dump"], rd, grid=f"{g['x0']},{g['y0']},{g['step']},"
                                            f"{g['nx']},{g['ny']}", grid_name="ep_s8_disc", types="",
                                            decoratives=False, label="grid-synth")
    print(f"[grid synth] {res}")
    record("grid_synth_isolated", "isolated=yes" in res and f is not None, res)
    js = out_root / "grid-synth-s3.json"
    code, so, res = run([HERE / "t1_metrics.py", "grid", "--ref-land", ref_png, "--wr", wr, "--hr", hr, "--scale", "3",
                         "--runs", rd, "--out-json", js], "t1 grid synth")
    r = json.loads(js.read_text(encoding="utf-8"))
    record("grid_synth_t1", r["pixel_agreement"] == 1.0 and r["covered_px"] == SYN_W * SYN_H,
           f"agreement {r['pixel_agreement']} covered {r['covered_px']}")
    eu = eg.MapRef("europe")
    g = t1.plan_grid(eu, "6")
    rd = out_root / "grid-europe-s6"
    code, res, f, so = dump_render.run_dump(INSTANCE, NAMES["probe_dump"], rd, grid=f"{g['x0']},{g['y0']},{g['step']},"
                                            f"{g['nx']},{g['ny']}", grid_name="ep_s8_disc", types="",
                                            decoratives=False, label="grid-europe-s6")
    print(f"[grid europe] {res}")
    record("grid_europe_isolated", "isolated=yes" in res and f is not None, res)
    if f is None:
        return
    gg, arr, _ = t1.read_grid(f)
    tx = g["x0"] + np.arange(g["nx"]) * g["step"]
    ty = g["y0"] + np.arange(g["ny"]) * g["step"]
    want = (SYN_R - np.sqrt(tx[None, :].astype(float) ** 2 + ty[:, None].astype(float) ** 2)) >= 0
    record("grid_europe_bits", arr.shape == want.shape and bool(((arr == 1) == want).all()) and gg["nonfinite"] == 0,
           f"{arr.size} grid bits, {int(((arr == 1) != want).sum())} differ from the analytic disc, "
           f"{int((arr == 1).sum())} land")
    js = out_root / "grid-europe-s6-t1.json"
    code, so, res = run([HERE / "t1_metrics.py", "grid", "--map", "europe", "--scale", "6", "--runs", rd,
                         "--out-json", js, "--overlay", js.with_suffix(".png")], "t1 grid europe")
    r = json.loads(js.read_text(encoding="utf-8"))
    record("grid_europe_t1_covers_map", r["covered_px"] == eu.W * eu.H, f"covered {r['covered_px']} of {eu.W * eu.H}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--only", default="t1,grid,sheet,oracle,dump,nav")
    ap.add_argument("--replay", action="store_true",
                    help="re-derive every verdict from the finished run under --out-root; launch nothing")
    a = ap.parse_args()
    # A relative --out-root is the workspace's (the usage above). It is resolved there before the
    # live-profile refusal, so the path checked is the path written: checked against the working
    # directory and then joined onto the workspace, ..\..\AppData\Roaming\Factorio from the repo
    # passed the check and was written in the live profile.
    tnguard.refuse_live_outputs(a, "game_selftest.py", base=WS)
    out_root = Path(a.out_root)
    if a.replay:
        # a replay launches nothing (every game command answers from its run.json), so it needs no
        # bracket; it rewrites the analysis files and game-selftest.json beside the stored runs, so
        # it runs on a scratch copy only, never on the runner's stored evidence itself (the gate
        # copies the suite's run to a temporary folder first)
        evidence = tnguard.out_root(WS)
        try:
            in_evidence = out_root.resolve().is_relative_to(evidence.resolve())
        except OSError:
            in_evidence = True
        if in_evidence:
            print(f"RESULT fail game_selftest.py refuses --replay on {out_root}: it lies in the runner's evidence "
                  f"tree {evidence}, and a replay rewrites the stored analysis files and game-selftest.json; replay "
                  f"a copy outside it", flush=True)
            sys.exit(1)
        if not out_root.is_dir() or not any(out_root.iterdir()):
            sys.exit(f"RESULT fail --replay needs a finished run under --out-root {out_root}")
        REPLAY["on"] = True
        import dump_render
        dump_render.REPLAY["on"] = True
    else:
        tnguard.require_bracket("game_selftest.py")
        if out_root.exists() and any(out_root.iterdir()):
            sys.exit(f"RESULT fail --out-root {out_root} already holds files; use a new directory")
        out_root.mkdir(parents=True, exist_ok=True)
    only = set(a.only.split(","))
    setup_modsets(replay=a.replay)
    t1_runs = None
    if only & {"t1", "oracle", "sheet"}:
        t1_runs = test_t1(out_root)
    if "grid" in only:
        test_grid(out_root)
    if "sheet" in only:
        import contact_sheet
        contact_sheet.game_selftest(out_root, t1_runs, record, run)
    if "oracle" in only:
        import oracle
        oracle.game_selftest(out_root, t1_runs, record, run)
    dump_dir = None
    if "dump" in only or "nav" in only:
        import dump_render
        dump_dir = dump_render.game_selftest(out_root, record, run)
    if "nav" in only and dump_dir is not None:
        import nav
        nav.game_selftest(out_root, dump_dir, record, run)
    (out_root / "game-selftest.json").write_text(json.dumps(RESULTS, indent=1), encoding="utf-8")
    bad = [r for r in RESULTS if not r["ok"]]
    print(f"RESULT {'ok' if not bad else 'fail'} game_selftest tests={len(RESULTS)} failed={len(bad)} "
          f"{'replayed=yes ' if a.replay else ''}out={out_root}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
