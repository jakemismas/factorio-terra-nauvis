#!/usr/bin/env python3
"""V1 contact sheet: reference crop, generated land mask, preview and a red difference overlay.

Panels, left to right, all of one reference-pixel window:
  1 reference   land grey, water dark blue, thin water (excluded from T1) light blue
  2 generated   the land decision (t1_metrics --candidate-out PNG, an array, or derived from the preview)
  3 preview     the fh.py preview cropped to the window's tiles (1 tile per pixel, resized to the panel)
  4 difference  t1_metrics overlay: red = generated land on reference water, orange = generated water
                on reference land, light blue = excluded thin water, black = not covered
It also runs `fh.py compare` on panels 1 and 2 drawn in one palette (its --sbs image and RESULT line
go into the sheet JSON) and the T1 metric for the window.

Commands (from the Factorio workspace):
  python mod/tools/contact_sheet.py --map europe --window 900,650,300,200 --candidate cand.png --preview pv/1000.png --preview-offset X,Y --scale 3 --out sheet.png
  python mod/tools/contact_sheet.py selftest
"""
import argparse
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


def build(mref, window, cand_land, cand_cov, preview=None, preview_offset=(0, 0), scale=None, origin="floor",
          panel_px=480, out=None, fh_compare=True):
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
    if preview is not None:
        pv = np.asarray(Image.open(preview).convert("RGB"))
        S_h, S_w = pv.shape[:2]
        cx, cy = (preview_offset[0] // 32) * 32, (preview_offset[1] // 32) * 32
        sf, of = eg.as_fraction(scale), eg.origin_fraction(origin)
        tx0, tx1 = math.floor((c0 - mref.wr - of) * sf), math.ceil((c0 + w - mref.wr - of) * sf)
        ty0, ty1 = math.floor((r0 - mref.hr - of) * sf), math.ceil((r0 + h - mref.hr - of) * sf)
        px0, py0 = tx0 - (cx - S_w // 2), ty0 - (cy - S_h // 2)
        crop = np.zeros((ty1 - ty0, tx1 - tx0, 3), np.uint8)
        sx0, sy0 = max(px0, 0), max(py0, 0)
        sx1, sy1 = min(px0 + crop.shape[1], S_w), min(py0 + crop.shape[0], S_h)
        if sx1 > sx0 and sy1 > sy0:
            crop[sy0 - py0:sy1 - py0, sx0 - px0:sx1 - px0] = pv[sy0:sy1, sx0:sx1]
        p_pv = np.asarray(Image.fromarray(crop).resize((pw, ph), Image.NEAREST if crop.shape[1] <= pw else Image.BOX))
        panels.append(p_pv)
        titles.append(f"preview tiles {tx0}..{tx1 - 1}, {ty0}..{ty1 - 1}")
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
            "islands_window": res["islands"]["buckets"], "preview": str(preview) if preview else None}
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
