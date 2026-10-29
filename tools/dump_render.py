#!/usr/bin/env python3
"""V4: dump real tiles and entities from a scenario run (mods/ep-s8-dump) and draw them to PNG.

Commands (from the Factorio workspace):
  python mod/tools/dump_render.py run --instance ep-s8 --modset ep-s8-dump --seed 1000 --areas -128,-128,256,256 --out previews/earth-build/s8/dump-1
  python mod/tools/dump_render.py render previews/earth-build/s8/dump-1/script-output/ep-s8-dump/dump.json --png out.png [--area 0] [--tiles-only]
  python mod/tools/dump_render.py compare-preview <dump.json> <preview.png> --preview-offset 0,0 [--out-json cmp.json]
  python mod/tools/dump_render.py selftest

`run` needs the modset to hold the dump mod (fh.py modset <name> --add mod/tools/mods/ep-s8-dump).
It writes the ep-s8-dump-* startup settings into that modset's mod-settings.dat with fh.py's own
encoder (tools/fh.py is imported, never edited), then runs `fh.py scenario`. Points (`--points
x,y;x,y` with `--names`) are evaluated with calculate_tile_properties and read back as real tiles;
`--scene cliffs` adds one cliff of every orientation with the game's collision rasters, and `--scene wall`
a cliff wall across x -40..40 near y 1026 with one 8-tile gap (dump area -40,1004,80,44); nav.py uses both.

Render: 1 px per tile, the tile's map_color, then entities on top (trees green, rocks light grey,
ores their map_color, cliffs dark brown over their collision box, enemies red, fish cyan), with a
legend panel on the right listing every tile and entity class with its count.
"""
import argparse
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import earthgeo as eg  # noqa: E402

WS = eg.WS
MOD_DIR = HERE / "mods" / "ep-s8-dump"
SETTING_PREFIX = "ep-s8-dump-"
ENTITY_COLOURS = {  # class -> (colour, legend label)
    "tree": ((30, 150, 40), "trees"),
    "simple-entity": ((190, 190, 190), "rocks (simple-entity)"),
    "cliff": ((60, 35, 15), "cliffs (collision box)"),
    "unit-spawner": ((255, 25, 25), "spawners"),
    "turret": ((255, 90, 200), "worms (turret)"),
    "unit": ((255, 140, 140), "units"),
    "fish": ((0, 230, 255), "fish"),
}


def load_fh():
    spec = importlib.util.spec_from_file_location("fh_harness", eg.FH)
    fh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fh)
    return fh


def load_json(path):
    """Read a dump (or any game JSON), turning the bare inf/nan tokens the game writes into JSON."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r'(?<![\w"])-inf\b', "-1e309", text)
    text = re.sub(r'(?<![\w"-])inf\b', "1e309", text)
    text = re.sub(r'(?<![\w"])-?nan\b', "NaN", text)
    return json.loads(text)


def as_list(x):
    return [] if x in (None, {}) else x


# ------------------------------------------------------------------------------------------------
# Run

def set_startup(fh, instance, modset, values):
    """Write ep-s8-dump-* startup values with fh.py's encoder (the same path fh.py sample uses)."""
    ms = fh.MODSETS / modset
    f = fh.ensure_settings_file(instance, ms)
    doc = fh.read_mod_settings(f)
    startup = fh._dict_get(doc["tree"], "startup")
    for name, v in values.items():
        key = SETTING_PREFIX + name
        node = [1, 0, bool(v)] if isinstance(v, bool) else ([6, 0, int(v)] if isinstance(v, int) else [3, 0, str(v)])
        entry = fh._dict_get(startup, key)
        if entry is None:
            startup[2].append((key, [5, 0, [("value", node)]]))
        else:
            entry[2] = [(k, node if k == "value" else c) for k, c in entry[2]]
    f.write_bytes(fh.encode_mod_settings(doc))
    return f


DEFAULT_TYPES = "tree,simple-entity,resource,cliff,unit-spawner,turret,unit,fish"
# Set only by game_selftest.py --replay, in its own process: run_dump answers from stored runs.
REPLAY = {"on": False}


def run_dump(instance, modset, out, seed=1000, areas="", points="", names="", types=None, decoratives=True,
             scene="", lattice=4, gen_tick=1, dump_tick=2, label="dump", map_gen_settings=None, timeout=900,
             grid="", grid_name="elevation", grid_threshold="0", grid_op="ge"):
    """Configure and run one scenario; returns (exit code, RESULT line, path of the dump JSON or None).
    Every ep-s8-dump setting is written on every call: stored values persist in the modset otherwise.
    A run that may have left its instance stops every further game run (design constraint 1;
    tnguard.run_breach). Under game_selftest.py --replay it launches nothing and answers from the
    stored run directory."""
    if REPLAY["on"]:
        import game_selftest as gs
        code, so, res = gs.replayed_result(out, f"replay {label}")
        f = Path(out) / "script-output" / "ep-s8-dump" / f"{label}.json"
        return code, res, (f if f.exists() else None), so
    import tnguard
    # fh.py runs with the workspace as its working directory: hand it an absolute path, resolved
    # against this process's working directory, never a relative one it would re-anchor
    out = tnguard.absolute_output(out)
    if map_gen_settings:
        map_gen_settings = tnguard.absolute_output(map_gen_settings)
    fh = load_fh()
    ml = fh.MODSETS / modset / "mod-list.json"
    if not ml.exists() or not any(m["name"] == "ep-s8-dump" and m["enabled"]
                                  for m in json.loads(ml.read_text(encoding="utf-8"))["mods"]):
        raise SystemExit(f"RESULT fail modset {modset} lacks ep-s8-dump: python tools/fh.py modset {modset} --add {MOD_DIR}")
    vals = {"label": label, "areas": areas, "late-areas": "", "points": points, "names": names,
            "decoratives": bool(decoratives),
            "scene": scene, "scene-lattice": int(lattice), "gen-tick": int(gen_tick), "tick": int(dump_tick),
            "types": DEFAULT_TYPES if types is None else types, "grid": grid, "grid-name": grid_name or "elevation",
            "grid-threshold": str(grid_threshold), "grid-op": grid_op}
    set_startup(fh, instance, modset, vals)
    cmd = [sys.executable, str(eg.FH), "scenario", "--instance", instance, "--modset", modset, "--seed", str(seed),
           "--ticks", str(int(dump_tick) + 2), "--out", str(out), "--timeout", str(timeout)]
    if map_gen_settings:
        cmd += ["--map-gen-settings", str(map_gen_settings)]
    cp = subprocess.run(cmd, cwd=WS, capture_output=True, text=True)
    lines = [l for l in cp.stdout.splitlines() if l.startswith("RESULT ")]
    res = lines[-1] if lines else "RESULT none " + cp.stdout[-500:]
    why = tnguard.run_breach(out, res)
    if why:
        # design constraint 1: a run that may have left its instance stops every further game run
        raise SystemExit(f"RESULT fail dump_render.py stops every further game run: {why}")
    f = Path(out) / "script-output" / "ep-s8-dump" / f"{label}.json"
    return cp.returncode, res, (f if f.exists() else None), cp.stdout


def cmd_run(a):
    code, res, f, so = run_dump(a.instance, a.modset, a.out, a.seed, a.areas or "", a.points or "", a.names or "",
                                a.types, not a.no_decoratives, a.scene or "", a.lattice, a.gen_tick, a.tick,
                                a.label, a.map_gen_settings, grid=a.grid or "", grid_name=a.grid_name,
                                grid_threshold=a.grid_threshold, grid_op=a.grid_op)
    print(so.strip())
    ok = code == 0 and f is not None and "isolated=yes" in res
    print(f"RESULT {'ok' if ok else 'fail'} dump={f} scenario=({res})")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------
# Decode and draw

def decode_tiles(area):
    """(palette names, int32 index array H x W) from a dumped area."""
    a = area["area"]
    h, w = a["h"], a["w"]
    idx = np.empty((h, w), np.int32)
    for r, row in enumerate(area["tiles"]["rows"]):
        c = 0
        for tok in row.split(" "):
            i, n = tok.split("*")
            n = int(n)
            idx[r, c:c + n] = int(i)
            c += n
        if c != w:
            raise ValueError(f"row {r}: decoded {c} tiles, want {w}")
    return list(area["tiles"]["palette"]), idx


def colour255(c):
    if c is None:
        return (255, 0, 255)
    c = [float(v) for v in c[:3]]
    if all(v <= 1.0 for v in c):
        return tuple(int(math.floor(v * 255)) for v in c)
    return tuple(int(round(v)) for v in c)


def tile_layers(area):
    return {t["name"]: set(as_list(t.get("layers"))) for t in as_list(area["tiles"].get("info"))}


def box_corners(lt, rb, orientation, sign=1.0, pivot=None):
    """Corners of a (possibly oriented) box. Orientation is in turns (1/8 = 45 degrees), rotating
    clockwise on screen (y down) for sign +1, about the box centre unless a pivot is given."""
    cx, cy = (lt[0] + rb[0]) / 2, (lt[1] + rb[1]) / 2
    hx, hy = (rb[0] - lt[0]) / 2, (rb[1] - lt[1]) / 2
    px, py = (cx, cy) if pivot is None else pivot
    th = sign * 2 * math.pi * orientation
    ct, st = math.cos(th), math.sin(th)
    out = []
    for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
        x, y = cx + dx - px, cy + dy - py
        out.append((px + x * ct - y * st, py + x * st + y * ct))
    return out


def points_in_polygon(poly, xs, ys):
    """Convex polygon (clockwise or not) contains points (vectorised)."""
    inside_pos = np.ones(xs.shape, bool)
    inside_neg = np.ones(xs.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (x2 - x1) * (ys - y1) - (y2 - y1) * (xs - x1)
        inside_pos &= cross >= -1e-9
        inside_neg &= cross <= 1e-9
    return inside_pos | inside_neg


def cliff_boxes(area):
    """[(name, x, y, orientation string, corners)] using each cliff's dumped bounding box."""
    names = [e["name"] for e in as_list(area.get("entity_names"))]
    out = []
    for c in as_list(area.get("cliffs")):
        ni, x, y, orient, ltx, lty, rbx, rby, bo = c
        out.append((names[ni], x, y, orient, box_corners((ltx, lty), (rbx, rby), bo)))
    return out


def raster_cliffs(area, x0, y0, w, h, n=1):
    """Bool raster (h * n, w * n): cell centres inside any cliff collision box."""
    out = np.zeros((h * n, w * n), bool)
    for _, _, _, _, poly in cliff_boxes(area):
        xs_ = [p[0] for p in poly]
        ys_ = [p[1] for p in poly]
        c0 = max(int(math.floor((min(xs_) - x0) * n)) - 1, 0)
        c1 = min(int(math.ceil((max(xs_) - x0) * n)) + 1, w * n)
        r0 = max(int(math.floor((min(ys_) - y0) * n)) - 1, 0)
        r1 = min(int(math.ceil((max(ys_) - y0) * n)) + 1, h * n)
        if c1 <= c0 or r1 <= r0:
            continue
        gx = x0 + (np.arange(c0, c1) + 0.5) / n
        gy = y0 + (np.arange(r0, r1) + 0.5) / n
        X, Y = np.meshgrid(gx, gy)
        out[r0:r1, c0:c1] |= points_in_polygon(poly, X, Y)
    return out


def render(dump, area_i=0, tiles_only=False, legend=True):
    area = dump["areas"][area_i]
    a = area["area"]
    x0, y0, w, h = a["x0"], a["y0"], a["w"], a["h"]
    names, idx = decode_tiles(area)
    info = {t["name"]: t for t in as_list(area["tiles"].get("info"))}
    pal = np.array([colour255(info.get(n, {}).get("map_color")) for n in names], np.uint8)
    img = pal[idx]
    counts = {"tiles": {n: int((idx == i).sum()) for i, n in enumerate(names)}, "entities": {}}
    if not tiles_only:
        einfo = as_list(area.get("entity_names"))
        for e in as_list(area.get("entities")):
            ni, ex, ey = e[0], e[1], e[2]
            typ = einfo[ni]["type"]
            col = ENTITY_COLOURS.get(typ, ((255, 255, 0), typ))[0]
            if typ == "resource":
                col = colour255(einfo[ni].get("map_color"))
            c, r = int(math.floor(ex - x0)), int(math.floor(ey - y0))
            if 0 <= r < h and 0 <= c < w:
                img[r, c] = col
            key = einfo[ni]["name"] if typ == "resource" else typ
            counts["entities"][key] = counts["entities"].get(key, 0) + 1
        cl = raster_cliffs(area, x0, y0, w, h)
        img[cl] = ENTITY_COLOURS["cliff"][0]
        if area.get("cliffs"):
            counts["entities"]["cliff"] = len(area["cliffs"])
    im = Image.fromarray(img)
    if not legend:
        return im, counts
    items = [(tuple(int(v) for v in pal[i]), f"{n} ({counts['tiles'][n]})") for i, n in enumerate(names)]
    if not tiles_only:
        einfo = as_list(area.get("entity_names"))
        for key, cnt in sorted(counts["entities"].items()):
            res = next((e for e in einfo if e["name"] == key and e["type"] == "resource"), None)
            if res is not None:
                items.append((colour255(res.get("map_color")), f"{key} ({cnt})"))
            else:
                col, label = ENTITY_COLOURS.get(key, ((255, 255, 0), key))
                items.append((col, f"{label} ({cnt})"))
    line = 14
    title = [f"{dump.get('label', '')} seed {dump.get('seed')} tick {dump.get('tick')}",
             f"area x {x0}..{x0 + w - 1}, y {y0}..{y0 + h - 1}, 1 px per tile"]
    lw = 300
    H = max(h, (len(items) + len(title) + 1) * line + 8)
    canvas = Image.new("RGB", (w + lw, H), (24, 24, 24))
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    y = 4
    for t in title:
        d.text((w + 8, y), t, fill=(235, 235, 235))
        y += line
    y += 4
    for col, label in items:
        d.rectangle([w + 8, y + 2, w + 18, y + 11], fill=col, outline=(255, 255, 255))
        d.text((w + 24, y), label[:44], fill=(235, 235, 235))
        y += line
    return canvas, counts


def cmd_render(a):
    dump = load_json(a.dump)
    canvas, counts = render(dump, a.area, a.tiles_only, not a.no_legend)
    Path(a.png).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(a.png)
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(counts, indent=1), encoding="utf-8")
    print(f"RESULT ok render png={a.png} tiles={sum(counts['tiles'].values())} "
          f"entities={sum(counts['entities'].values())}")
    return 0


def compare_preview(dump, preview_png, offset=(0, 0), area_i=0):
    """Tile-for-tile agreement between dumped tiles and a preview of the same area.

    Preview pixel (px, py) is tile (cx - S/2 + px, cy - S/2 + py) with cx snapped down to a multiple
    of 32 (factorio-test-harness). Only preview pixels showing some tile's exact map_color are
    compared (entities draw over tiles)."""
    area = dump["areas"][area_i]
    a = area["area"]
    names, idx = decode_tiles(area)
    info = {t["name"]: t for t in as_list(area["tiles"].get("info"))}
    pal = np.array([colour255(info.get(n, {}).get("map_color")) for n in names], np.int32)
    pv = np.asarray(Image.open(preview_png).convert("RGB")).astype(np.int32)
    S_h, S_w = pv.shape[:2]
    cx, cy = (offset[0] // 32) * 32, (offset[1] // 32) * 32
    px0, py0 = a["x0"] - (cx - S_w // 2), a["y0"] - (cy - S_h // 2)
    sub = pv[py0:py0 + a["h"], px0:px0 + a["w"]]
    if sub.shape[:2] != (a["h"], a["w"]):
        raise SystemExit("RESULT fail the preview does not cover the dumped area")
    key = (sub[..., 0] << 16) | (sub[..., 1] << 8) | sub[..., 2]
    pk = (pal[:, 0] << 16) | (pal[:, 1] << 8) | pal[:, 2]
    tile_coloured = np.isin(key, pk)
    want = pk[idx]
    same = tile_coloured & (key == want)
    n_tc = int(tile_coloured.sum())
    water = {n for n, L in tile_layers(area).items() if "water_tile" in L}
    wmask = np.isin(idx, [i for i, n in enumerate(names) if n in water])
    wk = pk[[i for i, n in enumerate(names) if n in water]] if water else np.zeros(0, np.int32)
    pv_water = np.isin(key, wk)
    return {
        "area": a, "preview": str(preview_png), "preview_offset": list(offset),
        "tile_coloured_px": n_tc, "tile_coloured_agree_px": int(same.sum()),
        "tile_agreement": round(int(same.sum()) / n_tc, 6) if n_tc else None,
        "all_px": int(key.size), "tile_coloured_fraction": round(n_tc / key.size, 6),
        "water_tiles_dumped": int(wmask.sum()), "water_px_preview": int(pv_water.sum()),
        "water_agree_px": int((wmask & pv_water).sum()),
        "water_iou": round(int((wmask & pv_water).sum()) / max(int((wmask | pv_water).sum()), 1), 6),
    }


def cmd_compare_preview(a):
    dump = load_json(a.dump)
    off = tuple(int(v) for v in a.preview_offset.split(","))
    r = compare_preview(dump, a.preview, off, a.area)
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(r, indent=1), encoding="utf-8")
    print(f"RESULT ok compare tile_agreement={r['tile_agreement']} tile_coloured_px={r['tile_coloured_px']} "
          f"water_iou={r['water_iou']}")
    return 0


# ------------------------------------------------------------------------------------------------
# Self-tests

def synthetic_dump():
    """A hand-made 8 x 6 area: grass with a water pool, two trees, an ore and a cliff."""
    rows = ["0*8", "0*2 1*3 0*3", "0*2 1*3 0*3", "0*8", "2*8", "2*8"]
    return {"format": "ep-s8-dump/1", "label": "synthetic", "seed": 0, "tick": 2, "areas": [{
        "area": {"x0": -4, "y0": -3, "w": 8, "h": 6},
        "tiles": {"palette": ["grass-1", "water", "sand-1"], "rows": rows,
                  "info": [{"name": "grass-1", "map_color": [55, 53, 11, 1], "layers": ["ground_tile"]},
                           {"name": "water", "map_color": [51, 83, 95, 1], "layers": ["water_tile", "player"]},
                           {"name": "sand-1", "map_color": [138, 103, 58, 1], "layers": ["ground_tile"]}]},
        "entity_names": [{"name": "tree-01", "type": "tree"}, {"name": "iron-ore", "type": "resource",
                                                                "map_color": [0.415, 0.525, 0.580, 1]},
                         {"name": "cliff", "type": "cliff"}],
        "entities": [[0, -3.5, -2.5], [0, 2.2, -0.1], [1, 0.5, 2.5, 600]],
        "cliffs": [[2, 0.0, 1.5, "west-to-east", -2.0, 0.0, 2.0, 3.0, 0]],
        "decoratives": {}}], "points": []}


def selftest():
    checks = []

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    d = synthetic_dump()
    names, idx = decode_tiles(d["areas"][0])
    ck("decode_shape", idx.shape == (6, 8))
    ck("decode_water", int((idx == 1).sum()) == 6 and bool((idx[1:3, 2:5] == 1).all()))
    canvas, counts = render(d, 0, tiles_only=False, legend=False)
    img = np.asarray(canvas)
    ck("render_size", img.shape[:2] == (6, 8), str(img.shape))
    ck("render_tree", tuple(img[0, 0]) == ENTITY_COLOURS["tree"][0], str(tuple(img[0, 0])))   # (-3.5, -2.5) -> col 0, row 0
    ck("render_tree2", tuple(img[2, 6]) == ENTITY_COLOURS["tree"][0], str(tuple(img[2, 6])))  # (2.2, -0.1) -> col 6, row 2
    # The cliff box x -2..2, y 0..3 covers tile centres x -1.5..1.5 (cols 2..5) and y 0.5..2.5 (rows 3..5).
    cl = raster_cliffs(d["areas"][0], -4, -3, 8, 6)
    ck("cliff_raster", int(cl.sum()) == 12 and bool(cl[3:6, 2:6].all()), str(int(cl.sum())))
    ck("render_water", tuple(img[1, 2]) == (51, 83, 95))
    ck("counts", counts["tiles"] == {"grass-1": 26, "water": 6, "sand-1": 16}, str(counts["tiles"]))
    # Oriented box: a 2 x 2 square turned 1/8 is a diamond reaching sqrt(2) from its centre.
    poly = box_corners((-1, -1), (1, 1), 0.125)
    ck("diamond", max(abs(p[0]) for p in poly) > 1.41 and max(abs(p[0]) for p in poly) < 1.42)
    # Canvas with legend.
    canvas, _ = render(d, 0)
    ck("legend_canvas", canvas.size[0] == 8 + 300)
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name} {detail}")
    print(f"RESULT {'ok' if not bad else 'fail'} dump_render selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def game_selftest(out_root, record, run):
    """Vanilla 256 x 256 at seed 1000: dump, render, and compare tile for tile with a preview."""
    import game_selftest as gs
    fh_cmd = [eg.FH]
    out = out_root / "dump-vanilla-256"
    code, res, f, so = run_dump(gs.INSTANCE, gs.NAMES["dump"], out, seed=1000, areas="-128,-128,256,256;-40,1004,80,44",
                                label="vanilla-256", scene="cliffs,wall")
    print(f"[dump vanilla 256] {res}")
    record("dump_isolated_and_written", code == 0 and f is not None and "isolated=yes" in res, res)
    if f is None:
        return None
    dump = load_json(f)
    canvas, counts = render(dump, 0)
    canvas.save(out_root / "dump-vanilla-256.png")
    tiles_im, _ = render(dump, 0, tiles_only=True, legend=False)
    tiles_im.save(out_root / "dump-vanilla-256-tiles.png")
    (out_root / "dump-vanilla-256-counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    ar = dump["areas"][0]
    record("dump_area_complete", ar["chunks_not_generated"] == 0 and sum(counts["tiles"].values()) == 256 * 256,
           f"chunks_not_generated={ar['chunks_not_generated']} tiles={sum(counts['tiles'].values())} "
           f"entities={counts['entities']}")
    pv = out_root / "preview-vanilla-256"
    code, so, res = run(fh_cmd + ["preview", "--instance", gs.INSTANCE, "--modset", gs.NAMES["dump"], "--seed", "1000",
                                  "--size", "256", "--out", pv], "preview vanilla 256")
    record("preview_isolated", "isolated=yes" in res, res)
    cmp = compare_preview(dump, pv / "1000.png", (0, 0))
    (out_root / "dump-vs-preview.json").write_text(json.dumps(cmp, indent=1), encoding="utf-8")
    # Harness reference: tile-only disagreement about 0.4 % at seed 1000 (cli-and-previews.md).
    record("dump_matches_preview_tiles", cmp["tile_agreement"] is not None and cmp["tile_agreement"] >= 0.99
           and cmp["water_iou"] >= 0.99, json.dumps({k: cmp[k] for k in ("tile_agreement", "tile_coloured_px",
                                                                          "water_iou", "water_tiles_dumped")}))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--instance", required=True)
    p.add_argument("--modset", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--areas", help="x0,y0,w,h;x0,y0,w,h in tiles")
    p.add_argument("--points", help="x,y;x,y in tiles")
    p.add_argument("--names", help="comma list of expressions to evaluate at the points")
    p.add_argument("--types", help="comma list of entity types (default: trees, rocks, ores, cliffs, enemies, fish)")
    p.add_argument("--no-decoratives", action="store_true")
    p.add_argument("--scene", default="", help="comma list: cliffs (every orientation with game rasters), wall (T6 known answer)")
    p.add_argument("--lattice", type=int, default=4)
    p.add_argument("--gen-tick", type=int, default=1)
    p.add_argument("--tick", type=int, default=2)
    p.add_argument("--label", default="dump")
    p.add_argument("--map-gen-settings")
    p.add_argument("--grid", help="x0,y0,step,nx,ny: thresholded --grid-name on a grid (t1_metrics plan-grid prints it)")
    p.add_argument("--grid-name", default="elevation")
    p.add_argument("--grid-threshold", default="0")
    p.add_argument("--grid-op", choices=("ge", "gt", "le", "lt"), default="ge")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("render")
    p.add_argument("dump")
    p.add_argument("--png", required=True)
    p.add_argument("--area", type=int, default=0)
    p.add_argument("--tiles-only", action="store_true")
    p.add_argument("--no-legend", action="store_true")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("compare-preview")
    p.add_argument("dump")
    p.add_argument("preview")
    p.add_argument("--preview-offset", default="0,0")
    p.add_argument("--area", type=int, default=0)
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_compare_preview)
    p = sub.add_parser("selftest")
    p.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
