#!/usr/bin/env python3
"""V1 contact sheet: reference crop, generated land mask, preview and a red difference overlay; and the
poster mode (V5, D30; milestone extras): one map's whole extent stitched from fh.py previews, with a title, a
legend and scale bars.

Panels, left to right, all of one reference-pixel window:
  1 reference   land grey, water dark blue, thin water (excluded from T1) light blue
  2 generated   the land decision (t1_metrics --candidate-out PNG, an array, or derived from the preview)
  3 preview     the fh.py preview cropped to the window's tiles (1 tile per pixel, resized to the panel);
                given several previews (`previews`), each tile is drawn from the preview that holds
                it, so a window wider than one preview shows all of its terrain
  4 difference  t1_metrics overlay: red = generated land on reference water, orange = generated water
                on reference land, light blue = excluded thin water, black = not covered
It also runs `fh.py compare` on panels 1 and 2 drawn in one palette (its --sbs image and RESULT line
go into the sheet JSON) and the T1 metric for the window.

Poster mode: every reference pixel of the map takes the preview tile holding its centre (t1_metrics'
map_preview geometry, so the poster's land is exactly what T1's preview mode scores), the whole extent is
box-filtered to the poster width, and a title band and a legend band with the map colours of the dump's
tiles and resources and two scale bars (kilometres north to south, tiles at the world's scale) frame it.
Posters come from previews or dumped tiles only, never from a graphical client (D30).

Commands (from the Factorio workspace):
  python mod/tools/contact_sheet.py --map europe --window 900,650,300,200 --candidate cand.png --preview pv/1000.png --preview-offset X,Y --scale 3 --out sheet.png
  python mod/tools/contact_sheet.py poster --map europe --scale 1 --seed 1000 --title "Terra Nauvis: Europe" --run pv1/1000.png@32,384 --dump data-raw-dump.json --out docs/posters/europe.png
  python mod/tools/contact_sheet.py selftest
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import earthgeo as eg  # noqa: E402
import t1_metrics as t1  # noqa: E402

MASK_COLOURS = [(25, 50, 95), (200, 200, 190), (120, 205, 240), (0, 0, 0)]  # water, land, thin, uncovered


def mask_panel(land, cov=None, thin=None):
    idx = np.where(land, 1, 0).astype(np.uint8)
    if thin is not None:
        idx[thin & ~land] = 2
    if cov is not None:
        idx[~cov] = 3
    pal = np.array(MASK_COLOURS, np.uint8)
    return pal[idx]


def fit(img, w, h, max_pool_bad=None):
    """Resize an RGB array to (w, h): nearest when enlarging; when shrinking, nearest plus any
    difference colour kept visible (max-pooled) for the overlay panel."""
    H, W = img.shape[:2]
    if (W, H) == (w, h):
        return img
    im = Image.fromarray(img)
    if w >= W:
        return np.asarray(im.resize((w, h), Image.NEAREST))
    out = np.asarray(im.resize((w, h), Image.NEAREST)).copy()
    if max_pool_bad is not None:
        ys = (np.arange(H) * h // H)
        xs = (np.arange(W) * w // W)
        for col in max_pool_bad:
            m = (img == np.array(col, np.uint8)).all(axis=2)
            r, c = np.nonzero(m)
            out[ys[r], xs[c]] = col
    return out


def labelled(panels, titles, header):
    ph = max(p.shape[0] for p in panels)
    pw = sum(p.shape[1] for p in panels) + 8 * (len(panels) - 1)
    top = 34
    canvas = Image.new("RGB", (pw, ph + top), (24, 24, 24))
    d = ImageDraw.Draw(canvas)
    d.text((4, 2), header[:160], fill=(235, 235, 235))
    x = 0
    for p, t in zip(panels, titles):
        canvas.paste(Image.fromarray(p), (x, top))
        d.text((x + 4, 18), t, fill=(235, 235, 235))
        x += p.shape[1] + 8
    return canvas


def preview_crop(previews, tx0, tx1, ty0, ty1):
    """The tiles tx0..tx1 - 1, ty0..ty1 - 1 from fh.py previews, each (path, offset): a preview of
    size S at offset (x, y) covers the tiles from (x - S / 2, y - S / 2), its offset snapped down to
    a multiple of 32 as the game snaps it. Each tile is drawn from a preview that holds it (where
    previews overlap the later one is drawn; their pixels agree, one generator), a tile no preview
    holds stays black, and a preview that holds none of the window is never decoded. Returns (the
    crop, the previews drawn from)."""
    crop = np.zeros((ty1 - ty0, tx1 - tx0, 3), np.uint8)
    used = []
    for path, offset in previews:
        with Image.open(path) as im:
            S_w, S_h = im.size
            cx, cy = (offset[0] // 32) * 32, (offset[1] // 32) * 32
            px0, py0 = tx0 - (cx - S_w // 2), ty0 - (cy - S_h // 2)
            sx0, sy0 = max(px0, 0), max(py0, 0)
            sx1, sy1 = min(px0 + crop.shape[1], S_w), min(py0 + crop.shape[0], S_h)
            if sx1 <= sx0 or sy1 <= sy0:
                continue
            pv = np.asarray(im.convert("RGB"))
        crop[sy0 - py0:sy1 - py0, sx0 - px0:sx1 - px0] = pv[sy0:sy1, sx0:sx1]
        used.append(path)
    return crop, used


def build(mref, window, cand_land, cand_cov, preview=None, preview_offset=(0, 0), scale=None, origin="floor",
          panel_px=480, out=None, fh_compare=True, previews=None):
    """The sheet of one window. `preview` with `preview_offset` names one fh.py preview; `previews`,
    a list of (path, offset), names several, which the preview panel tiles together (the T1 runs
    at scales above 1 cover the map in several previews)."""
    c0, r0, w, h = window
    sl = (slice(r0, r0 + h), slice(c0, c0 + w))
    ref, thin = mref.land[sl].copy(), mref.thin[sl].copy()
    land, cov = cand_land[sl].copy(), cand_cov[sl].copy()
    res, ov = t1.evaluate(ref, thin, land.copy(), cov.copy(), interior=(r0 > 0, r0 + h < mref.H, c0 > 0, c0 + w < mref.W),
                          offset=(c0, r0), mref=mref, max_list=20)
    ov_rgb = np.array(t1.OV_COLOURS, np.uint8)[ov]
    zoom = max(1, panel_px // max(w, h)) if max(w, h) <= panel_px else None
    pw, ph = (w * zoom, h * zoom) if zoom else (panel_px, max(1, round(h * panel_px / w)))
    p_ref = fit(mask_panel(ref, None, thin), pw, ph)
    p_gen = fit(mask_panel(land, cov), pw, ph)
    p_ov = fit(ov_rgb, pw, ph, max_pool_bad=[t1.OV_COLOURS[t1.OV_FALSE_LAND], t1.OV_COLOURS[t1.OV_FALSE_WATER]])
    panels, titles = [p_ref, p_gen], ["reference", "generated land"]
    tiles = list(previews) if previews else ([(preview, preview_offset)] if preview is not None else [])
    pv_rec = None
    if tiles:
        sf, of = eg.as_fraction(scale), eg.origin_fraction(origin)
        tx0, tx1 = math.floor((c0 - mref.wr - of) * sf), math.ceil((c0 + w - mref.wr - of) * sf)
        ty0, ty1 = math.floor((r0 - mref.hr - of) * sf), math.ceil((r0 + h - mref.hr - of) * sf)
        crop, used = preview_crop(tiles, tx0, tx1, ty0, ty1)
        pv_rec = [str(q) for q in used] if len(used) > 1 else (str(used[0]) if used else None)
        p_pv = np.asarray(Image.fromarray(crop).resize((pw, ph), Image.NEAREST if crop.shape[1] <= pw else Image.BOX))
        panels.append(p_pv)
        titles.append(f"preview tiles {tx0}..{tx1 - 1}, {ty0}..{ty1 - 1}" +
                      (f" from {len(used)} previews" if len(used) > 1 else ""))
    panels.append(p_ov)
    titles.append("difference (red false land, orange false water)")
    cd = res["coast_deviation_px"]
    header = (f"{mref.key or 'custom'} window col {c0} row {r0} {w}x{h} px"
              + (f", scale {scale}" if scale else "")
              + f" | agreement {res['pixel_agreement']} IoU {res['land_iou']} coast max {cd['max']} "
                f"false land {res['false_land_px']} false water {res['false_water_px']}")
    sheet = labelled(panels, titles, header)
    info = {"window_px": list(window), "t1_window": {k: res[k] for k in ("pixel_agreement", "land_iou", "false_land_px",
                                                                        "false_water_px", "coast_deviation_px", "d7")},
            "islands_window": res["islands"]["buckets"],
            "preview": pv_rec}
    if out:
        # absolute: fh.py compare below runs in the workspace and must write --sbs and --mask
        # beside the sheet, not re-anchor a relative path there
        out = Path(os.path.abspath(out))
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        info["sheet"] = str(out)
        if fh_compare:
            a_png, b_png = out.with_name(out.stem + "-ref.png"), out.with_name(out.stem + "-gen.png")
            Image.fromarray(mask_panel(ref)).save(a_png)
            Image.fromarray(mask_panel(land & cov)).save(b_png)
            sbs, mask = out.with_name(out.stem + "-sbs.png"), out.with_name(out.stem + "-diffmask.png")
            cp = subprocess.run([sys.executable, str(eg.FH), "compare", str(a_png), str(b_png), "--sbs", str(sbs),
                                 "--mask", str(mask)], cwd=eg.WS, capture_output=True, text=True)
            line = next((l for l in cp.stdout.splitlines() if l.startswith("RESULT")), cp.stdout.strip())
            info["fh_compare"] = {"result": line, "sbs": str(sbs), "mask": str(mask) if mask.exists() else None,
                                  "note": "panels 1 and 2 drawn as land/water only (thin water shown as water)"}
        out.with_suffix(".json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return sheet, info


def cmd_build(a):
    mref = t1.make_ref(a)
    window = tuple(int(v) for v in a.window.split(",")) if a.window else (0, 0, mref.W, mref.H)
    if a.candidate:
        land, cov = t1.load_candidate(a.candidate)
        origin_cr = (0, 0)
        side = Path(str(a.candidate) + ".json")
        if a.cand_origin:
            origin_cr = tuple(int(v) for v in a.cand_origin.split(","))
        elif side.exists():
            origin_cr = tuple(json.loads(side.read_text(encoding="utf-8"))["origin_px"])
        L, C = t1.place(mref, land, cov, origin_cr)
    elif a.preview:
        cols = list(t1.BASE_WATER_COLOURS.values())
        if a.water_colours_from:
            cols = t1.water_colours_from_dump(a.water_colours_from)
        land_px = t1.preview_land(a.preview, t1.water_colour_set(cols))
        L, C = t1.map_preview(mref, land_px, tuple(int(v) for v in a.preview_offset.split(",")), a.scale, a.origin)
    else:
        raise SystemExit("RESULT fail give --candidate or --preview")
    off = tuple(int(v) for v in a.preview_offset.split(","))
    sheet, info = build(mref, window, L, C, a.preview, off, a.scale, a.origin, a.panel_px, a.out)
    t = info["t1_window"]
    print(f"RESULT ok sheet={a.out} agreement={t['pixel_agreement']} coast_max={t['coast_deviation_px']['max']} "
          f"fh_compare=({info.get('fh_compare', {}).get('result', '-')})")
    return 0


# Poster mode (V5, D30). KM_PER_DEGREE is a degree of latitude on a sphere of the mean Earth radius, so one
# reference pixel spans KM_PER_DEGREE / px_per_degree km north to south (APPROVALS 1c: 2,471 m per tile at scale 1).
POSTER_WIDTH = 2400
KM_PER_DEGREE = 2 * math.pi * 6371.0 / 360
POSTER_BG = (24, 24, 24)
POSTER_FG = (235, 235, 235)
UNCOVERED = (0, 0, 0)
KM_STEPS = (50, 100, 200, 250, 500, 1000, 2000, 2500, 5000)
TILE_STEPS = (100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000)
# The legend: (label, prototype type, names whose first one the dump holds); a row is left out when the dump
# holds none of its names.
POSTER_LEGEND = (
    ("deep water", "tile", ("deepwater",)), ("water", "tile", ("water",)),
    ("shallow water and fords", "tile", ("water-shallow",)), ("marsh mud", "tile", ("water-mud",)),
    ("grassland", "tile", ("grass-1",)), ("dirt and dry land", "tile", ("dirt-4", "dirt-1")),
    ("sand and desert", "tile", ("sand-1",)),
    ("iron ore", "resource", ("iron-ore",)), ("copper ore", "resource", ("copper-ore",)),
    ("coal", "resource", ("coal",)), ("stone", "resource", ("stone",)),
    ("uranium ore", "resource", ("uranium-ore",)), ("crude oil", "resource", ("crude-oil",)),
    ("cliff ridges", "cliff", ("cliff",)),
)


def map_rgb(mc):
    """A dump's map_color as 0 to 255 RGB, as t1_metrics' water colour set reads it (floor of x * 255)."""
    c = (mc.get("r", 0), mc.get("g", 0), mc.get("b", 0)) if isinstance(mc, dict) else tuple(mc[:3])
    c = tuple(float(x) for x in c)
    if all(x <= 1.0 for x in c):
        return tuple(int(math.floor(x * 255)) for x in c)
    return tuple(int(round(x)) for x in c)


# Entities the map draws in the chart's own colours (utility constants), not a prototype's map colour: trees
# (blended over the ground, so the swatch is the full colour) and enemy bases.
POSTER_CHART_LEGEND = (("trees, over the ground", ("default_color_by_type", "tree")),
                       ("enemy bases", ("default_enemy_color",)))


def poster_legend(dump):
    """[(label, rgb)] of POSTER_LEGEND's rows whose prototype the dump holds with a map colour, then the chart
    colours of trees and enemy bases from the dump's utility constants."""
    out = []
    for label, kind, names in POSTER_LEGEND:
        for n in names:
            mc = ((dump.get(kind) or {}).get(n) or {}).get("map_color")
            if mc is not None:
                out.append((label, map_rgb(mc)))
                break
    chart = (((dump.get("utility-constants") or {}).get("default") or {}).get("chart") or {})
    for label, path in POSTER_CHART_LEGEND:
        v = chart
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, (list, dict)):
            out.append((label, map_rgb(v)))
    return out


def stitch(mref, runs, scale="1", origin="floor"):
    """(rgb H x W x 3, covered H x W) at one pixel per reference pixel: each pixel takes the preview tile that
    holds its centre, from the preview that covers it (t1_metrics.map_preview's geometry; the city offset is
    0, so a world tile is a geo tile), black where no preview does. runs: [(png, (offset x, offset y))]."""
    canvas = np.zeros((mref.H, mref.W, 3), np.uint8)
    cov = np.zeros((mref.H, mref.W), bool)
    for png, off in runs:
        rgb = np.asarray(Image.open(png).convert("RGB"))
        S_h, S_w = rgb.shape[:2]
        cx, cy = (int(off[0]) // 32) * 32, (int(off[1]) // 32) * 32
        tx = eg.pixel_centre_tiles(np.arange(mref.W), mref.wr, scale, origin) - (cx - S_w // 2)
        ty = eg.pixel_centre_tiles(np.arange(mref.H), mref.hr, scale, origin) - (cy - S_h // 2)
        okc, okr = (tx >= 0) & (tx < S_w), (ty >= 0) & (ty < S_h)
        cols, rows = np.nonzero(okc)[0], np.nonzero(okr)[0]
        if cols.size and rows.size:
            canvas[np.ix_(rows, cols)] = rgb[np.ix_(ty[okr], tx[okc])]
            cov[np.ix_(rows, cols)] = True
    return canvas, cov


def nice_step(per_px, max_px, steps):
    """The largest step of `steps` (in units of per_px per pixel) that draws at most max_px pixels."""
    best = steps[0]
    for s in steps:
        if s / per_px <= max_px:
            best = s
    return best


def poster(mref, runs, title, subtitle, legend, scale="1", width=POSTER_WIDTH, out=None):
    """The poster image and its record. The map is the stitched extent box-filtered to `width` pixels (never
    enlarged); the legend band names each colour and draws a north-south kilometre bar and a tile bar at the
    world's scale (the map is plate carree: east-west distances shrink by the cosine of the latitude)."""
    from PIL import ImageFont
    canvas, cov = stitch(mref, runs, scale)
    w = min(int(width), mref.W)
    h = max(1, round(mref.H * w / mref.W))
    img = Image.fromarray(canvas)
    if (w, h) != (mref.W, mref.H):
        img = img.resize((w, h), Image.BOX)
    f_title = ImageFont.load_default(size=26)
    f_text = ImageFont.load_default(size=18)
    top, row_h, sw = 64, 30, 22
    per_row = max(1, (w - 16) // 300)
    rows_n = -(-len(legend) // per_row) if legend else 0
    band = 16 + rows_n * row_h + 3 * row_h
    sheet = Image.new("RGB", (w, top + h + band), POSTER_BG)
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), title, fill=POSTER_FG, font=f_title)
    d.text((10, 38), subtitle, fill=POSTER_FG, font=f_text)
    sheet.paste(img, (0, top))
    y0 = top + h + 12
    for i, (label, rgb) in enumerate(legend):
        x = 10 + (i % per_row) * 300
        y = y0 + (i // per_row) * row_h
        d.rectangle([x, y, x + sw, y + sw], fill=tuple(rgb), outline=POSTER_FG)
        d.text((x + sw + 8, y + 1), label, fill=POSTER_FG, font=f_text)
    ref_px_per_poster_px = mref.W / w
    km_per_px = KM_PER_DEGREE / float(mref.ppd) * ref_px_per_poster_px
    tiles_per_px = float(eg.as_fraction(scale)) * ref_px_per_poster_px
    yb = y0 + rows_n * row_h + 8
    km = nice_step(km_per_px, w / 5, KM_STEPS)
    tiles = nice_step(tiles_per_px, w / 5, TILE_STEPS)
    bars = []
    for i, (n, per, label) in enumerate(((km, km_per_px, f"{km:,} km north to south"),
                                          (tiles, tiles_per_px, f"{tiles:,} tiles at scale {scale}"))):
        L = int(round(n / per))
        y = yb + i * row_h
        d.rectangle([10, y + 6, 10 + L, y + 14], fill=POSTER_FG)
        d.text((20 + L, y), label, fill=POSTER_FG, font=f_text)
        bars.append({"label": label, "px": L})
    d.text((10, yb + 2 * row_h), "Plate carree: east to west a degree shrinks with the cosine of the latitude, so "
           "the bars hold north to south. Black: outside every preview.", fill=POSTER_FG, font=f_text)
    info = {"map": mref.key, "scale": str(scale), "reference_px": [mref.W, mref.H], "map_px": [w, h],
            "size": list(sheet.size), "covered_px": int(cov.sum()), "uncovered_px": int((~cov).sum()),
            "legend": [[label, list(rgb)] for label, rgb in legend], "bars": bars,
            "runs": [{"image": str(p), "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(), "offset": list(o)}
                     for p, o in runs]}
    if out:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out, optimize=False)
        info["poster"] = str(out)
        info["poster_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    return sheet, info


def poster_selftest():
    """Offline: a synthetic map and two overlapping synthetic previews stitch to the pixels map_preview gives
    T1, the poster has its title, map and legend bands, and two builds give identical bytes."""
    checks = []
    W, H = 96, 40
    mref = eg.MapRef(land=np.ones((H, W), bool), thin=np.zeros((H, W), bool))
    tmp = Path(tempfile.mkdtemp(prefix="poster-selftest-"))   # outside the repo
    runs = []
    for i, off in enumerate(((-32, 0), (32, 0))):
        a = np.zeros((64, 64, 3), np.uint8)
        a[..., 0] = np.arange(64)[None, :] + 100 * i
        a[..., 1] = np.arange(64)[:, None]
        p = tmp / f"pv{i}.png"
        Image.fromarray(a).save(p)
        runs.append((p, off))
    rgb, cov = stitch(mref, runs, "1")
    ok_geo = True
    for p, off in runs:
        land = np.ones((64, 64), bool)
        _, C = t1.map_preview(mref, land, off, "1", "floor")
        ok_geo &= bool((cov | ~C).all())
    checks.append(("stitch_covers_map_preview", ok_geo and bool(cov.all()), f"covered {int(cov.sum())} of {W * H}"))
    checks.append(("stitch_right_preview_wins", int(rgb[0, W - 1, 0]) >= 100, str(tuple(rgb[0, W - 1]))))
    sheet, info = poster(mref, runs, "selftest", "two previews", [("water", (25, 50, 95)), ("land", (200, 200, 190))],
                         width=96, out=tmp / "a.png")
    sheet2, info2 = poster(mref, runs, "selftest", "two previews", [("water", (25, 50, 95)), ("land", (200, 200, 190))],
                           width=96, out=tmp / "b.png")
    checks.append(("poster_bytes_repeat", info["poster_sha256"] == info2["poster_sha256"], info["poster_sha256"][:12]))
    checks.append(("poster_bands", sheet.size[1] > H + 64 and info["map_px"] == [W, H], str(sheet.size)))
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name} {detail}")
    print(f"RESULT {'ok' if not bad else 'fail'} poster selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def parse_run(s):
    """'<png>@<x>,<y>' as (path, (x, y))."""
    png, _, off = s.rpartition("@")
    x, y = (int(v) for v in off.split(","))
    return Path(png), (x, y)


def poster_main(argv):
    ap = argparse.ArgumentParser(description="poster mode: one map stitched from previews (V5, D30)")
    ap.add_argument("--map", choices=eg.MAPS, required=True)
    ap.add_argument("--scale", default="1")
    ap.add_argument("--seed", default="1000")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--run", action="append", required=True, help="<preview png>@<offset x>,<offset y>")
    ap.add_argument("--dump", required=True, help="data-raw-dump.json of the build (legend colours)")
    ap.add_argument("--width", type=int, default=POSTER_WIDTH)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    mref = eg.MapRef(a.map)
    dump = json.loads(Path(a.dump).read_text(encoding="utf-8"))
    sub = a.subtitle or f"seed {a.seed}, scale {a.scale}, stitched from {len(a.run)} preview(s)"
    _, info = poster(mref, [parse_run(r) for r in a.run], a.title, sub, poster_legend(dump), a.scale, a.width,
                     out=a.out)
    Path(a.out).with_suffix(".json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"RESULT ok poster={a.out} size={info['size']} covered={info['covered_px']} "
          f"uncovered={info['uncovered_px']} sha256={info['poster_sha256'][:16]}")
    return 0


def selftest():
    checks = []

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    ref, thin, cand = t1.synthetic_case()
    mref = eg.MapRef(land=ref, thin=thin)
    tmp = Path(tempfile.mkdtemp(prefix="s8-selftest-"))   # outside the repo
    sheet, info = build(mref, (0, 0, mref.W, mref.H), cand, np.ones_like(cand), panel_px=480,
                        out=tmp / "sheet-selftest.png", fh_compare=True)
    arr = np.asarray(sheet)
    zoom = 480 // 48
    ck("sheet_size", sheet.size == (3 * 48 * zoom + 16, 40 * zoom + 34), str(sheet.size))
    # Overlay panel starts after two panels plus gaps; false land at (row 4, col 10) must be red.
    x = 2 * (48 * zoom + 8) + 10 * zoom + zoom // 2
    y = 34 + 4 * zoom + zoom // 2
    ck("overlay_red_at_false_land", tuple(arr[y, x]) == (255, 0, 0), str(tuple(arr[y, x])))
    ck("t1_window_matches_metric", info["t1_window"]["false_land_px"] == 4 and info["t1_window"]["false_water_px"] == 11)
    fc = info.get("fh_compare", {}).get("result", "")
    # fh.py compare counts every differing pixel, the excluded river pixel included (15 + 1).
    ck("fh_compare_ran", fc.startswith("RESULT different changed_px=16"), fc)
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name} {detail}")
    print(f"RESULT {'ok' if not bad else 'fail'} contact_sheet selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def game_selftest(out_root, t1_runs, record, run):
    """Disc world (mods/ep-s8-disc-world: Nauvis elevation = ep_s8_disc): a real preview at scale 3
    scored by the T1 preview mode against the analytic reference, and a contact sheet of reference,
    sampled land, preview and difference."""
    import game_selftest as gs
    land, wr, hr = gs.synthetic_disc_reference("3")
    ref_png = out_root / "t1-synth-s3-land.png"
    if not ref_png.exists():
        Image.fromarray(land).save(ref_png)
    pv = out_root / "sheet-preview-disc"
    code, so, res = run([eg.FH, "preview", "--instance", gs.INSTANCE, "--modset", gs.NAMES["disc"], "--seed", "1000",
                         "--size", "512", "--out", pv], "preview disc world")
    record("sheet_preview_isolated", "isolated=yes" in res and "WARN" not in so, res)
    js = out_root / "t1-preview-disc-s3.json"
    code, so, res = run([HERE / "t1_metrics.py", "preview", "--ref-land", ref_png, "--wr", wr, "--hr", hr,
                         "--scale", "3", "--preview", pv / "1000.png", "--preview-offset", "0,0",
                         "--out-json", js, "--overlay", js.with_suffix(".png")], "t1 preview disc")
    r = json.loads(js.read_text(encoding="utf-8"))
    cd = r["coast_deviation_px"]
    record("t1_preview_disc", r["pixel_agreement"] >= 0.99 and r["d7"]["coast_pass"],
           f"real preview tiles vs the analytic disc: agreement {r['pixel_agreement']}, misclassified "
           f"{cd['misclassified']}, coast max {cd['max']}")
    cand = out_root / "t1-s3-candidate.png"
    code, so, res = run([HERE / "t1_metrics.py", "sample", "--ref-land", ref_png, "--wr", wr, "--hr", hr, "--scale", "3",
                         "--name", "ep_s8_disc", "--runs"] + list(t1_runs["3"]) +
                        ["--candidate-out", cand, "--out-json", out_root / "t1-s3-candidate.json"], "t1 candidate")
    sheet = out_root / "sheet-disc-s3-sampled.png"
    code, so, res = run([HERE / "contact_sheet.py", "--ref-land", ref_png, "--wr", wr, "--hr", hr, "--window",
                         "0,0,160,128", "--candidate", cand, "--preview", pv / "1000.png", "--preview-offset", "0,0",
                         "--scale", "3", "--out", sheet], "contact sheet sampled")
    info = json.loads(sheet.with_suffix(".json").read_text(encoding="utf-8"))
    record("sheet_sampled", sheet.exists() and info["fh_compare"]["result"].startswith("RESULT identical"),
           f"{sheet.name}: window agreement {info['t1_window']['pixel_agreement']}, fh.py compare "
           f"{info['fh_compare']['result']}")
    sheet2 = out_root / "sheet-disc-s3-preview.png"
    code, so, res = run([HERE / "contact_sheet.py", "--ref-land", ref_png, "--wr", wr, "--hr", hr, "--window",
                         "0,0,160,128", "--preview", pv / "1000.png", "--preview-offset", "0,0",
                         "--scale", "3", "--out", sheet2], "contact sheet preview")
    info2 = json.loads(sheet2.with_suffix(".json").read_text(encoding="utf-8"))
    t = info2["t1_window"]
    n_bad = t["false_land_px"] + t["false_water_px"]
    record("sheet_preview_land", sheet2.exists() and f"changed_px={n_bad} " in info2["fh_compare"]["result"]
           and n_bad == cd["misclassified"],
           f"{sheet2.name}: {n_bad} differing pixels in red or orange; fh.py compare {info2['fh_compare']['result']}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    if len(sys.argv) > 1 and sys.argv[1] == "poster-selftest":
        sys.exit(poster_selftest())
    if len(sys.argv) > 1 and sys.argv[1] == "poster":
        sys.exit(poster_main(sys.argv[2:]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", choices=eg.MAPS)
    ap.add_argument("--ref-land")
    ap.add_argument("--ref-thin")
    ap.add_argument("--wr", type=int)
    ap.add_argument("--hr", type=int)
    ap.add_argument("--window", help="col,row,width,height in reference pixels (default: whole map)")
    ap.add_argument("--candidate", help="land decision PNG or .npy (t1_metrics --candidate-out writes one)")
    ap.add_argument("--cand-origin", help="col,row of the candidate in the reference (default: its sidecar JSON)")
    ap.add_argument("--preview", help="fh.py preview PNG")
    ap.add_argument("--preview-offset", default="0,0")
    ap.add_argument("--scale", default="1")
    ap.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    ap.add_argument("--water-colours-from")
    ap.add_argument("--panel-px", type=int, default=480)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit(cmd_build(a))


if __name__ == "__main__":
    main()
