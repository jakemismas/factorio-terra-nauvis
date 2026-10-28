#!/usr/bin/env python3
"""T1: fidelity of a generated land decision against the EarthMaps reference land mask (D7).

Inputs are a land decision for reference pixels, in one of three forms:
  array    a PNG or .npy of land (True / >= 192) and water (False / <= 63) per reference pixel,
           optionally a crop placed with --cand-origin; PNG grey 64..191 or npy -1 = not covered
  sample   fh.py sample runs of a land expression taken at reference pixel centres (plan them with
           the plan subcommand); land = value >= threshold by default (vanilla water is elevation < 0)
  preview  an fh.py preview PNG (1 tile per pixel); water = pixels with a water tile's exact map_color
The reference thin-water mask (rivers and channels under 3 px wide) is excluded from every count.

Outputs one JSON (pixel agreement, land IoU, coast deviation, islands by size bucket, the D7 bars)
and a palette PNG: grey = land agrees, dark blue = water agrees, red = generated land on reference
water, orange = generated water on reference land, light blue = excluded thin water, black = not
covered.

Coast deviation of a misclassified pixel is the distance from its centre to the nearest reference
land/water boundary edge, in reference pixels (exact up to --cap, default 64; larger ones are
counted as capped). A pixel touching the coast along an edge scores 0.5, along a corner only 0.71.
An island is a 4-connected reference land component (--conn 8 for 8); present = at least half its
pixels are generated land; separate = present and its generated land is not connected to another
reference land component. Islands not wholly inside the covered area are not scored.

Commands (run from the Factorio workspace):
  python mod/tools/t1_metrics.py array --map europe --candidate cand.png --out-json t1.json --overlay t1.png
  python mod/tools/t1_metrics.py plan --map europe --scale 6 --name <expression> --instance ep-x --modset ep-x-m --seed 1000 --out-root previews/earth-build/x/t1
  python mod/tools/t1_metrics.py sample --map europe --scale 6 --name <expression> --runs previews/earth-build/x/t1/b00 ... --out-json t1.json --overlay t1.png
  python mod/tools/t1_metrics.py preview --map europe --scale 1 --preview pv/1000.png --preview-offset 0,0 --out-json t1.json
  python mod/tools/t1_metrics.py selftest
"""
import argparse
import hashlib
import json
import math
import re
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import earthgeo as eg  # noqa: E402
from earthmaps_decode import label_runs, row_runs  # noqa: E402  (R1's run-length components)

TOOL_VERSION = 1
BUCKETS = ((1, 1, "1"), (2, 4, "2-4"), (5, 16, "5-16"), (17, 64, "17-64"), (65, None, "65+"))
D7_AGREEMENT = 0.99
D7_COAST_PX = 0.5
DEFAULT_CAP = 64
SAMPLER_MAX = 1024  # fh-sampler-size maximum_value (tools/probe-mods/fh-sampler/settings.lua)
SAMPLER_MIN = 8
# Overlay palette indices.
OV_WATER, OV_LAND, OV_FALSE_LAND, OV_FALSE_WATER, OV_THIN, OV_UNCOVERED = range(6)
OV_COLOURS = [(25, 50, 95), (200, 200, 190), (255, 0, 0), (255, 150, 0), (120, 205, 240), (0, 0, 0)]
OV_LEGEND = {"grey": "land, agrees", "dark blue": "water, agrees", "red": "generated land on reference water",
             "orange": "generated water on reference land", "light blue": "reference thin water (excluded)",
             "black": "not covered"}
# Base-game water tiles and map_color (%FACTORIO_GAME%/data/base/prototypes/tile/tiles.lua lines
# 997, 1046, 1094, 1142, 1229, 1317). Previews draw a tile's exact map_color (factorio-test-harness).
BASE_WATER_COLOURS = {
    "deepwater": (38, 64, 73), "deepwater-green": (0.0941, 0.149, 0.066), "water": (51, 83, 95),
    "water-green": (31, 48, 18), "water-shallow": (82, 98, 92), "water-mud": (65, 89, 90),
}


# ------------------------------------------------------------------------------------------------
# Distances

def vertical_distance(target, capv=255, invert=False):
    """uint8: rows from each pixel to the nearest target pixel in the same column, saturating at capv.
    invert=True uses ~target as the target set without allocating it."""
    H, W = target.shape
    out = np.empty((H, W), np.uint8)
    cur = np.full(W, capv, np.uint16)
    for r in range(H):
        t = ~target[r] if invert else target[r]
        cur = np.where(t, 0, np.minimum(cur + 1, capv))
        out[r] = cur
    cur = np.full(W, capv, np.uint16)
    for r in range(H - 1, -1, -1):
        t = ~target[r] if invert else target[r]
        cur = np.where(t, 0, np.minimum(cur + 1, capv))
        np.minimum(out[r], cur.astype(np.uint8), out=out[r])
    return out


def coast_distance(vd, rq, cq, cap=DEFAULT_CAP):
    """Distance from the centres of pixels (rq, cq) to the nearest target pixel square.

    vd is vertical_distance(target). For a target pixel dr rows and dc columns away the distance from
    a pixel centre to its square is sqrt(a(dr)^2 + a(dc)^2) with a(d) = max(|d| - 0.5, 0); because the
    query pixel is not a target, that equals the distance to the nearest boundary edge. Exact up to
    cap; larger distances come back as inf.
    """
    H, W = vd.shape

    def a2(v):
        f = np.maximum(v.astype(np.float64) - 0.5, 0.0)
        return f * f

    best2 = a2(vd[rq, cq])
    K = int(math.ceil(cap)) + 1
    idx = np.arange(rq.size)
    for k in range(1, K + 1):
        ak2 = (k - 0.5) ** 2
        act = idx[best2 > ak2]
        if act.size == 0:
            break
        for sgn in (1, -1):
            cc = cq[act] + sgn * k
            ok = (cc >= 0) & (cc < W)
            sel = act[ok]
            if sel.size:
                best2[sel] = np.minimum(best2[sel], a2(vd[rq[sel], cc[ok]]) + ak2)
    d = np.sqrt(best2)
    d[d > cap] = np.inf
    return d


def coast_stats(d, cap):
    if d.size == 0:
        return {"misclassified": 0, "max": 0.0, "p99": 0.0, "mean": 0.0, "capped": 0, "cap": cap,
                "within_half_px": 0, "histogram": {}}
    capped = ~np.isfinite(d)
    dd = np.where(capped, cap + 1.0, d)
    edges = [(0.5, "0.5 (edge)"), (0.7072, "0.71 (corner)"), (1.5, "<=1.5"), (2.5, "<=2.5"), (4.5, "<=4.5"),
             (8.5, "<=8.5"), (16.5, "<=16.5"), (float(cap), f"<={cap}")]
    hist, lo = {}, -1.0
    for hi, name in edges:
        hist[name] = int(((dd > lo) & (dd <= hi + 1e-9)).sum())
        lo = hi + 1e-9
    hist[f">{cap}"] = int(capped.sum())
    return {
        "misclassified": int(d.size),
        "max": float(dd.max()) if not capped.any() else f">{cap}",
        "p99": round(float(np.percentile(dd, 99)), 4),
        "mean": round(float(dd.mean()), 4),
        "capped": int(capped.sum()), "cap": cap,
        "capped_note": f"capped pixels count as {cap + 1} in p99 and mean" if capped.any() else None,
        "within_half_px": int((dd <= 0.5 + 1e-9).sum()),
        "histogram": hist,
    }


# ------------------------------------------------------------------------------------------------
# Run-length helpers (rows from R1's row_runs; flat half-open intervals [fs, fe))

def row_runs_lowmem(mask, chunk=512):
    """Same output as R1's row_runs (rows, starts, ends of horizontal runs), in row chunks."""
    H, W = mask.shape
    R, S, E = [], [], []
    for r0 in range(0, H, chunk):
        sub = mask[r0:r0 + chunk]
        m = np.zeros((sub.shape[0], W + 2), np.int8)
        m[:, 1:-1] = sub
        d = np.diff(m, axis=1)
        rs, cs = np.nonzero(d == 1)
        _, ce = np.nonzero(d == -1)
        R.append(rs.astype(np.int64) + r0)
        S.append(cs.astype(np.int64))
        E.append(ce.astype(np.int64) - 1)
    if not R:
        z = np.zeros(0, np.int64)
        return z, z, z
    return np.concatenate(R), np.concatenate(S), np.concatenate(E)


def flat_runs(mask, conn):
    H, W = mask.shape
    rows, s, e = row_runs_lowmem(mask)
    comp, n = label_runs(rows, s, e, H, conn)
    return {"rows": rows, "s": s, "e": e, "comp": comp, "n": n, "fs": rows * W + s, "fe": rows * W + e + 1}


def per_run_counts(mask, fs, fe):
    """Number of True pixels of mask inside each flat run."""
    if fs.size == 0:
        return np.zeros(0, np.int64)
    flat = np.ascontiguousarray(mask).ravel().view(np.uint8)
    idx = np.empty(fs.size * 2, np.int64)
    idx[0::2], idx[1::2] = fs, fe
    if idx[-1] >= flat.size:      # reduceat's last segment runs to the end anyway
        idx = idx[:-1]
    return np.add.reduceat(flat, idx, dtype=np.int64)[0::2]


def run_overlaps(fs_a, fe_a, fs_b, fe_b):
    """Index pairs (i, j) of overlapping runs; each set sorted and disjoint."""
    lo = np.searchsorted(fe_b, fs_a, side="right")
    hi = np.searchsorted(fs_b, fe_a, side="left")
    cnt = np.maximum(hi - lo, 0)
    tot = int(cnt.sum())
    if tot == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    ia = np.repeat(np.arange(fs_a.size), cnt)
    offs = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    return ia, np.repeat(lo, cnt) + offs


# ------------------------------------------------------------------------------------------------
# The metric

def evaluate(ref, thin, cand, cov, interior=(False, False, False, False), cap=DEFAULT_CAP, conn=4,
             offset=(0, 0), mref=None, max_list=50):
    """ref, thin, cand, cov: bool arrays of one crop. interior = (top, bottom, left, right): True where
    that crop edge lies inside the full image, so components touching it are not whole islands.
    offset = (col, row) of the crop in the full image. Returns (result, overlay palette indices)."""
    H, W = ref.shape
    # Memory: one scratch mask (tmp) is reused for every count; misclassified pixels are kept as
    # index arrays only. Peak on Atlantic (102 M px) is the inputs plus about four masks.
    np.logical_and(cand, cov, out=cand)           # in place: nothing outside the covered area is land
    E = cov & ~thin
    tmp = np.empty_like(ref)
    n_eval = int(E.sum())

    def count(fn, *args):
        fn(*args, out=tmp)
        np.logical_and(tmp, E, out=tmp)
        return int(tmp.sum())

    np.logical_not(ref, out=tmp)
    np.logical_and(tmp, cand, out=tmp)
    np.logical_and(tmp, E, out=tmp)
    fl_r, fl_c = np.nonzero(tmp)
    np.logical_not(cand, out=tmp)
    np.logical_and(tmp, ref, out=tmp)
    np.logical_and(tmp, E, out=tmp)
    fw_r, fw_c = np.nonzero(tmp)
    n_fl, n_fw = int(fl_r.size), int(fw_r.size)
    inter = count(np.logical_and, cand, ref)
    union = count(np.logical_or, cand, ref)
    np.logical_and(cov, thin, out=tmp)
    n_thin = int(tmp.sum())
    res = {
        "covered_px": int(cov.sum()),
        "excluded_thin_px": n_thin,
        "evaluated_px": n_eval,
        "pixel_agreement": round((n_eval - n_fl - n_fw) / n_eval, 6) if n_eval else None,
        "land_iou": round(inter / union, 6) if union else None,
        "false_land_px": n_fl, "false_water_px": n_fw,
        "reference_land_px": count(np.logical_and, ref, ref), "generated_land_px": count(np.logical_and, cand, cand),
    }
    del tmp
    # Coast deviation.
    parts = []
    for rq, cq, invert in ((fl_r, fl_c, False), (fw_r, fw_c, True)):
        if rq.size:
            vd = vertical_distance(ref, invert=invert)
            parts.append(coast_distance(vd, rq, cq, cap))
            del vd
    d = np.concatenate(parts) if parts else np.zeros(0)
    res["coast_deviation_px"] = coast_stats(d, cap)
    del d, parts

    # Islands.
    R = flat_runs(ref, conn)
    nc = R["n"]
    length = R["e"] - R["s"] + 1
    area = np.bincount(R["comp"], weights=length, minlength=nc).astype(np.int64)
    x0 = np.full(nc, 1 << 40, np.int64)
    x1 = np.full(nc, -1, np.int64)
    y0 = np.full(nc, 1 << 40, np.int64)
    y1 = np.full(nc, -1, np.int64)
    if nc:
        np.minimum.at(x0, R["comp"], R["s"])
        np.maximum.at(x1, R["comp"], R["e"])
        np.minimum.at(y0, R["comp"], R["rows"])
        np.maximum.at(y1, R["comp"], R["rows"])
    top, bottom, left, right = interior
    whole = ~((top & (y0 == 0)) | (bottom & (y1 == H - 1)) | (left & (x0 == 0)) | (right & (x1 == W - 1)))
    covc = np.bincount(R["comp"], weights=per_run_counts(cov, R["fs"], R["fe"]), minlength=nc)
    candc = np.bincount(R["comp"], weights=per_run_counts(cand, R["fs"], R["fe"]), minlength=nc)
    scored = whole & (covc == area)
    present = scored & (2 * candc >= area)
    gen = np.where(E, cand, ref)      # thin water and uncovered pixels take the reference value
    del E
    G = flat_runs(gen, conn)
    merged = np.zeros(nc, bool)
    if nc and G["n"]:
        ia, ib = run_overlaps(R["fs"], R["fe"], G["fs"], G["fe"])
        ng = np.int64(G["n"])
        key = np.unique(R["comp"][ia].astype(np.int64) * ng + G["comp"][ib].astype(np.int64))
        ri, gi = key // ng, key % ng
        nref = np.bincount(gi, minlength=int(ng))
        merged[ri[nref[gi] >= 2]] = True
    del gen, G
    buckets = {}
    for lo, hi, name in BUCKETS:
        inb = scored & (area >= lo) & (area <= (hi if hi is not None else area.max(initial=0)))
        p = present & inb
        buckets[name] = {"islands": int(inb.sum()), "present": int(p.sum()),
                         "separate": int((p & ~merged).sum()), "merged": int((p & merged).sum()),
                         "missing": int((inb & ~present).sum())}
    fail = np.nonzero(scored & (~present | merged))[0]
    fail = fail[np.argsort(-area[fail], kind="stable")][:max_list]
    failing = []
    for i in fail.tolist():
        c0, r0 = int(x0[i]) + offset[0], int(y0[i]) + offset[1]
        c1, r1 = int(x1[i]) + offset[0], int(y1[i]) + offset[1]
        rec = {"area_px": int(area[i]), "generated_land_px": int(candc[i]),
               "status": "missing" if not present[i] else "merged", "bbox_px": [c0, r0, c1, r1]}
        if mref is not None and mref.meta:
            lon, lat = mref.uv_to_lonlat((c0 + c1 + 1) / 2, (r0 + r1 + 1) / 2)
            rec["centre_lonlat"] = [round(lon, 4), round(lat, 4)]
        failing.append(rec)
    res["islands"] = {"connectivity": conn, "reference_components": int(nc),
                      "scored": int(scored.sum()), "not_scored": int(nc - scored.sum()),
                      "buckets": buckets, "failing": failing,
                      "failing_note": f"largest {max_list} missing or merged islands, bbox in full-image pixels [c0, r0, c1, r1]"}
    agree_ok = res["pixel_agreement"] is not None and res["pixel_agreement"] >= D7_AGREEMENT
    cd = res["coast_deviation_px"]
    coast_ok = cd["misclassified"] == 0 or (cd["capped"] == 0 and cd["max"] <= D7_COAST_PX + 1e-9)
    res["d7"] = {"agreement_bar": D7_AGREEMENT, "agreement_pass": bool(agree_ok),
                 "coast_bar_px": D7_COAST_PX, "coast_pass": bool(coast_ok)}

    ov = np.where(ref, np.uint8(OV_LAND), np.uint8(OV_WATER))
    ov[np.logical_not(cov)] = OV_UNCOVERED
    ov[np.logical_and(cov, thin)] = OV_THIN
    ov[fl_r, fl_c] = OV_FALSE_LAND
    ov[fw_r, fw_c] = OV_FALSE_WATER
    return res, ov


def palette_image(idx, colours):
    """uint8 index array to a palette PNG image (putpalette turns the L image into P)."""
    im = Image.fromarray(np.ascontiguousarray(idx, dtype=np.uint8))
    pal = []
    for c in colours:
        pal.extend(c)
    im.putpalette(pal + [0] * (768 - len(pal)))
    return im


def save_overlay(ov, path):
    im = palette_image(ov, OV_COLOURS)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)


def crop_and_evaluate(mref, cand_full, cov_full, cap, conn, max_list=50, margin=None):
    """Crop to the covered bounding box plus a margin (exact distances up to cap), then evaluate."""
    rows = np.nonzero(cov_full.any(axis=1))[0]
    cols = np.nonzero(cov_full.any(axis=0))[0]
    if rows.size == 0:
        raise SystemExit("RESULT fail nothing covered: no candidate pixel maps onto the reference")
    H, W = cov_full.shape
    m = int(math.ceil(cap)) + 2 if margin is None else margin
    r0, r1 = max(int(rows[0]) - m, 0), min(int(rows[-1]) + 1 + m, H)
    c0, c1 = max(int(cols[0]) - m, 0), min(int(cols[-1]) + 1 + m, W)
    interior = (r0 > 0, r1 < H, c0 > 0, c1 < W)
    sl = (slice(r0, r1), slice(c0, c1))
    res, ov = evaluate(mref.land[sl], mref.thin[sl], cand_full[sl], cov_full[sl], interior, cap, conn,
                       offset=(c0, r0), mref=mref, max_list=max_list)
    br0, br1, bc0, bc1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    res["window_px"] = [bc0, br0, bc1 - bc0, br1 - br0]
    res["window_note"] = "[col, row, width, height] of the covered bounding box in reference pixels"
    ov = ov[br0 - r0:br1 - r0, bc0 - c0:bc1 - c0]
    return res, ov


# ------------------------------------------------------------------------------------------------
# Inputs

def load_candidate(path):
    """(land, covered) from a PNG or .npy; see the module docstring for the encoding."""
    path = Path(path)
    if path.suffix.lower() == ".npy":
        a = np.load(path)
        if a.dtype == bool:
            return a, np.ones_like(a, bool)
        return a > 0, a >= 0
    im = Image.open(path)
    if im.mode == "1":
        a = np.asarray(im).astype(bool)
        return a, np.ones_like(a, bool)
    g = np.asarray(im.convert("L"))
    return g >= 192, (g >= 192) | (g <= 63)


def save_candidate(land, cov, path):
    g = np.where(cov, np.where(land, 255, 0), 128).astype(np.uint8)
    Image.fromarray(g).save(path, optimize=True)


def place(mref, land, cov, origin_cr):
    """Full-size (land, covered) arrays with a crop placed at origin (col, row)."""
    c0, r0 = origin_cr
    h, w = land.shape
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    rs0, cs0 = max(r0, 0), max(c0, 0)
    rs1, cs1 = min(r0 + h, mref.H), min(c0 + w, mref.W)
    if rs1 <= rs0 or cs1 <= cs0:
        raise SystemExit("RESULT fail the candidate lies outside the reference")
    L[rs0:rs1, cs0:cs1] = land[rs0 - r0:rs1 - r0, cs0 - c0:cs1 - c0]
    C[rs0:rs1, cs0:cs1] = cov[rs0 - r0:rs1 - r0, cs0 - c0:cs1 - c0]
    return L, C


def read_sample_json(path):
    """fh.py sample output (a run directory or the sample.json itself), with fh.py's inf/nan fix."""
    p = Path(path)
    f = p / "script-output" / "fh-sampler" / "sample.json" if p.is_dir() else p
    text = f.read_text(encoding="utf-8")
    text = re.sub(r'(?<![\w"])-inf\b', "-1e309", text)
    text = re.sub(r'(?<![\w"-])inf\b', "1e309", text)
    text = re.sub(r'(?<![\w"])-?nan\b', "NaN", text)
    d = json.loads(text)
    d["_file"] = str(f)
    return d


def sample_grid_tiles(d):
    """First grid tile (x, y), step, size, and the fractional offset of the evaluated positions."""
    size, step = int(d["size"]), int(d["step"])
    x0f = Fraction(d["cx"]) - Fraction(size, 2) * step
    y0f = Fraction(d["cy"]) - Fraction(size, 2) * step
    X0, Y0 = math.floor(x0f), math.floor(y0f)
    return X0, Y0, step, size, (float(x0f - X0), float(y0f - Y0))


def map_sample(mref, d, name, scale, origin):
    """Per covered reference pixel: the sampled value. Returns (rows, cols, values block)."""
    vals = d["values"].get(name) if isinstance(d["values"], dict) else None
    if not vals:
        raise SystemExit(f"RESULT fail {d['_file']}: no values for {name!r} (unknown expression name?)")
    X0, Y0, step, size, frac = sample_grid_tiles(d)
    V = np.asarray(vals, dtype=np.float64)
    if V.size != size * size:
        raise SystemExit(f"RESULT fail {d['_file']}: {V.size} values for a {size}x{size} grid")
    V = V.reshape(size, size)

    def axis(n, radius, start):
        t = eg.pixel_centre_tiles(np.arange(n), radius, scale, origin)
        j = t - start
        ok = (j >= 0) & (j % step == 0) & (j // step < size)
        return np.nonzero(ok)[0], (j[ok] // step)

    cols, jc = axis(mref.W, mref.wr, X0)
    rows, jr = axis(mref.H, mref.hr, Y0)
    return rows, cols, V[np.ix_(jr, jc)], frac


def land_from_values(v, threshold, op):
    fin = np.isfinite(v)
    with np.errstate(invalid="ignore"):
        land = {"ge": v >= threshold, "gt": v > threshold, "le": v <= threshold, "lt": v < threshold}[op]
    return land & fin, fin


def water_colour_set(names_colours):
    out = set()
    for c in names_colours:
        c = tuple(float(x) for x in c[:3])
        if all(x <= 1.0 for x in c):
            out.add(tuple(int(math.floor(x * 255)) for x in c))
            out.add(tuple(int(round(x * 255)) for x in c))
        else:
            out.add(tuple(int(round(x)) for x in c))
    return out


def water_colours_from_dump(path):
    """Water tiles (collision layer water_tile) and their map_color from fh.py dump-data output."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cols = []
    for name, t in raw.get("tile", {}).items():
        layers = (t.get("collision_mask") or {}).get("layers") or {}
        if "water_tile" in layers and t.get("map_color") is not None:
            mc = t["map_color"]
            cols.append((mc.get("r", 0), mc.get("g", 0), mc.get("b", 0)) if isinstance(mc, dict) else tuple(mc[:3]))
    return cols


def preview_land(png, colours):
    rgb = np.asarray(Image.open(png).convert("RGB"))
    key = (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]
    wk = np.array([(r << 16) | (g << 8) | b for r, g, b in colours], np.int32)
    return ~np.isin(key, wk)


def map_preview(mref, land_px, offset, scale, origin):
    """Preview pixel (px, py) is tile (cx - S/2 + px, cy - S/2 + py), cx snapped down to a multiple of
    32 (factorio-test-harness, cli-and-previews.md). Returns full-size (land, covered)."""
    S_h, S_w = land_px.shape
    cx, cy = (offset[0] // 32) * 32, (offset[1] // 32) * 32
    tx = eg.pixel_centre_tiles(np.arange(mref.W), mref.wr, scale, origin) - (cx - S_w // 2)
    ty = eg.pixel_centre_tiles(np.arange(mref.H), mref.hr, scale, origin) - (cy - S_h // 2)
    okc, okr = (tx >= 0) & (tx < S_w), (ty >= 0) & (ty < S_h)
    cols, rows = np.nonzero(okc)[0], np.nonzero(okr)[0]
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    if cols.size and rows.size:
        L[np.ix_(rows, cols)] = land_px[np.ix_(ty[okr], tx[okc])]
        C[np.ix_(rows, cols)] = True
    return L, C


def read_grid(path):
    """ep-s8-dump grid (a dump JSON or a dump_render run directory): (grid meta, uint8 array ny x nx
    with 1 = value op threshold, 0 = not, 2 = not finite, file)."""
    import dump_render
    p = Path(path)
    if p.is_dir():
        files = sorted((p / "script-output" / "ep-s8-dump").glob("*.json"))
        if len(files) != 1:
            raise SystemExit(f"RESULT fail {p}: want exactly one ep-s8-dump JSON, found {len(files)}")
        p = files[0]
    g = dump_render.load_json(p).get("grid")
    if not g:
        raise SystemExit(f"RESULT fail {p}: no grid in this dump")
    if not g.get("recognised", True):
        raise SystemExit(f"RESULT fail {p}: calculate_tile_properties did not recognise {g.get('name')!r}")
    arr = np.empty((int(g["ny"]), int(g["nx"])), np.uint8)
    for j, row in enumerate(g["rows"]):
        v, n = zip(*(tok.split("*") for tok in row.split(" ")))
        arr[j] = np.repeat(np.array(v, np.uint8), np.array(n, np.int64))
    return g, arr, str(p)


def map_grid(mref, g, arr, scale, origin):
    """Reference pixels whose centre tile is a grid point: (rows, cols, block of arr)."""
    def axis(n, radius, start, step, count):
        t = eg.pixel_centre_tiles(np.arange(n), radius, scale, origin)
        j = t - int(start)
        ok = (j >= 0) & (j % int(step) == 0) & (j // int(step) < int(count))
        return np.nonzero(ok)[0], j[ok] // int(step)
    cols, jc = axis(mref.W, mref.wr, g["x0"], g["step"], g["nx"])
    rows, jr = axis(mref.H, mref.hr, g["y0"], g["step"], g["ny"])
    return rows, cols, arr[np.ix_(jr, jc)]


def plan_grid(mref, scale, origin="floor", window=None):
    """One ep-s8-dump grid covering the window: step = scale with one point per pixel for integer
    scales, else step 1 over the tiles the pixel centres fall in."""
    s = eg.as_fraction(scale)
    c0, r0, w, h = window or (0, 0, mref.W, mref.H)
    tx = eg.pixel_centre_tiles(np.arange(c0, c0 + w), mref.wr, s, origin)
    ty = eg.pixel_centre_tiles(np.arange(r0, r0 + h), mref.hr, s, origin)
    if s.denominator == 1:
        return {"x0": int(tx[0]), "y0": int(ty[0]), "step": s.numerator, "nx": w, "ny": h}
    return {"x0": int(tx.min()), "y0": int(ty.min()), "step": 1,
            "nx": int(tx.max() - tx.min() + 1), "ny": int(ty.max() - ty.min() + 1)}


# ------------------------------------------------------------------------------------------------
# Planning fh.py sample runs

def plan_blocks(mref, scale, origin="floor", window=None, max_size=SAMPLER_MAX):
    """Sample grids whose points are the tiles holding reference pixel centres.

    Integer scale: step = scale and one grid point per pixel. Other scales: step 1 over the tiles
    the window's pixel centres fall in (several pixels share a tile when scale < 1)."""
    s = eg.as_fraction(scale)
    c0, r0, w, h = window or (0, 0, mref.W, mref.H)
    blocks = []
    if s.denominator == 1:
        step = s.numerator
        for br in range(r0, r0 + h, max_size):
            for bc in range(c0, c0 + w, max_size):
                nw, nh = min(max_size, c0 + w - bc), min(max_size, r0 + h - br)
                size = max(nw, nh, SAMPLER_MIN)
                size += size % 2
                X0 = int(eg.pixel_centre_tiles([bc], mref.wr, s, origin)[0])
                Y0 = int(eg.pixel_centre_tiles([br], mref.hr, s, origin)[0])
                blocks.append({"px_window": [bc, br, nw, nh], "size": size, "step": step,
                               "center": [X0 + (size // 2) * step, Y0 + (size // 2) * step]})
    else:
        tx = eg.pixel_centre_tiles(np.arange(c0, c0 + w), mref.wr, s, origin)
        ty = eg.pixel_centre_tiles(np.arange(r0, r0 + h), mref.hr, s, origin)
        for Y0 in range(int(ty.min()), int(ty.max()) + 1, max_size):
            for X0 in range(int(tx.min()), int(tx.max()) + 1, max_size):
                nx = min(max_size, int(tx.max()) + 1 - X0)
                ny = min(max_size, int(ty.max()) + 1 - Y0)
                size = max(nx, ny, SAMPLER_MIN)
                size += size % 2
                pc = np.nonzero((tx >= X0) & (tx < X0 + size))[0]
                pr = np.nonzero((ty >= Y0) & (ty < Y0 + size))[0]
                blocks.append({"px_window": [c0 + int(pc[0]), r0 + int(pr[0]), int(pc.size), int(pr.size)],
                               "size": size, "step": 1, "center": [X0 + size // 2, Y0 + size // 2]})
    return blocks


# ------------------------------------------------------------------------------------------------
# Commands

def finish(a, mref, res, ov, inputs):
    mref._land = mref._thin = None   # free the full-size rasters before the overlay is encoded
    res = dict({"tool": "t1_metrics", "tool_version": TOOL_VERSION, "map": mref.key, "inputs": inputs}, **res)
    if a.overlay:
        save_overlay(ov, a.overlay)
        res["overlay"] = {"file": str(a.overlay), "legend": OV_LEGEND}
    res["peak_memory_mb"] = eg.peak_memory_mb()
    text = json.dumps(res, indent=1)
    if a.out_json:
        Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out_json).write_text(text, encoding="utf-8")
    cd = res["coast_deviation_px"]
    isl = res["islands"]["buckets"]
    print(f"RESULT ok agreement={res['pixel_agreement']} iou={res['land_iou']} "
          f"coast_max={cd['max']} coast_p99={cd['p99']} coast_mean={cd['mean']} misclassified={cd['misclassified']} "
          f"islands_present={sum(b['present'] for b in isl.values())}/{sum(b['islands'] for b in isl.values())} "
          f"islands_separate={sum(b['separate'] for b in isl.values())} "
          f"d7_agreement={'pass' if res['d7']['agreement_pass'] else 'fail'} "
          f"d7_coast={'pass' if res['d7']['coast_pass'] else 'fail'} covered={res['covered_px']} "
          f"json={a.out_json or '-'}")
    return 0


def make_ref(a):
    if a.map:
        return eg.MapRef(a.map)
    if not a.ref_land:
        raise SystemExit("RESULT fail give --map or --ref-land (with optional --ref-thin, --wr, --hr)")
    return eg.MapRef(land=a.ref_land, thin=a.ref_thin, wr=a.wr, hr=a.hr)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cmd_array(a):
    mref = make_ref(a)
    land, cov = load_candidate(a.candidate)
    origin_cr = tuple(int(v) for v in a.cand_origin.split(",")) if a.cand_origin else (0, 0)
    L, C = place(mref, land, cov, origin_cr)
    res, ov = crop_and_evaluate(mref, L, C, a.cap, a.conn)
    del L, C, land, cov
    inputs = {"mode": "array", "candidate": str(a.candidate), "candidate_sha256": sha(a.candidate),
              "candidate_origin_px": list(origin_cr)}
    return finish(a, mref, res, ov, inputs)


def cmd_sample(a):
    mref = make_ref(a)
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    runs, nonfinite = [], 0
    for r in a.runs:
        d = read_sample_json(r)
        rows, cols, block, frac = map_sample(mref, d, a.name, a.scale, a.origin)
        land, fin = land_from_values(block, a.threshold, a.land_when)
        nonfinite += int((~fin).sum())
        if rows.size and cols.size:
            L[np.ix_(rows, cols)] = land
            C[np.ix_(rows, cols)] = fin
        runs.append({"file": d["_file"], "size": d["size"], "step": d["step"], "center": [d["cx"], d["cy"]],
                     "position_fraction": list(frac), "covered_px": int(fin.sum())})
        del d
    if a.candidate_out:
        rows = np.nonzero(C.any(axis=1))[0]
        cols = np.nonzero(C.any(axis=0))[0]
        if rows.size:
            sl = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
            save_candidate(L[sl], C[sl], a.candidate_out)
            Path(str(a.candidate_out) + ".json").write_text(json.dumps(
                {"origin_px": [int(cols[0]), int(rows[0])], "map": mref.key, "scale": str(a.scale),
                 "name": a.name}), encoding="utf-8")
    res, ov = crop_and_evaluate(mref, L, C, a.cap, a.conn)
    del L, C
    inputs = {"mode": "sample", "name": a.name, "scale": str(a.scale), "origin": a.origin,
              "land_when": f"value {a.land_when} {a.threshold}", "nonfinite_px": nonfinite, "runs": runs,
              "candidate_out": str(a.candidate_out) if a.candidate_out else None}
    return finish(a, mref, res, ov, inputs)


def cmd_preview(a):
    mref = make_ref(a)
    cols = [c for c in BASE_WATER_COLOURS.values()]
    if a.water_colours_from:
        cols = water_colours_from_dump(a.water_colours_from)
    land_px = preview_land(a.preview, water_colour_set(cols))
    off = tuple(int(v) for v in a.preview_offset.split(","))
    L, C = map_preview(mref, land_px, off, a.scale, a.origin)
    res, ov = crop_and_evaluate(mref, L, C, a.cap, a.conn)
    del L, C, land_px
    inputs = {"mode": "preview", "preview": str(a.preview), "preview_sha256": sha(a.preview),
              "preview_offset": list(off), "scale": str(a.scale), "origin": a.origin,
              "water_colours": sorted(water_colour_set(cols))}
    return finish(a, mref, res, ov, inputs)


def cmd_grid(a):
    mref = make_ref(a)
    L = np.zeros((mref.H, mref.W), bool)
    C = np.zeros((mref.H, mref.W), bool)
    runs = []
    for r in a.runs:
        g, arr, f = read_grid(r)
        rows, cols, block = map_grid(mref, g, arr, a.scale, a.origin)
        if rows.size and cols.size:
            L[np.ix_(rows, cols)] = block == 1
            C[np.ix_(rows, cols)] = block != 2
        runs.append({"file": f, "name": g["name"], "rule": f"value {g['op']} {g['threshold']}",
                     "grid": [g["x0"], g["y0"], g["step"], g["nx"], g["ny"]], "nonfinite": g["nonfinite"],
                     "covered_px": int((block != 2).sum())})
        del arr
    if a.candidate_out:
        rr = np.nonzero(C.any(axis=1))[0]
        cc = np.nonzero(C.any(axis=0))[0]
        if rr.size:
            sl = (slice(rr[0], rr[-1] + 1), slice(cc[0], cc[-1] + 1))
            save_candidate(L[sl], C[sl], a.candidate_out)
            Path(str(a.candidate_out) + ".json").write_text(json.dumps(
                {"origin_px": [int(cc[0]), int(rr[0])], "map": mref.key, "scale": str(a.scale)}), encoding="utf-8")
    res, ov = crop_and_evaluate(mref, L, C, a.cap, a.conn)
    del L, C
    inputs = {"mode": "grid", "scale": str(a.scale), "origin": a.origin, "runs": runs,
              "candidate_out": str(a.candidate_out) if a.candidate_out else None}
    return finish(a, mref, res, ov, inputs)


def cmd_plan_grid(a):
    mref = make_ref(a)
    win = tuple(int(v) for v in a.window.split(",")) if a.window else None
    g = plan_grid(mref, a.scale, a.origin, win)
    spec = f"{g['x0']},{g['y0']},{g['step']},{g['nx']},{g['ny']}"
    out = a.out or "<out>"
    print(f"python mod/tools/dump_render.py run --instance {a.instance} --modset {a.modset} "
          f"--seed {a.seed} --grid {spec} --grid-name {a.name} --grid-threshold {a.threshold} "
          f"--grid-op {a.land_when} --no-decoratives --types \"\" --label t1grid --out {out}")
    print(f"python mod/tools/t1_metrics.py grid --map {mref.key} --scale {a.scale} --origin {a.origin} "
          f"--runs {out}")
    print(f"RESULT ok plan-grid points={g['nx'] * g['ny']} grid={spec}")
    return 0


def cmd_sanity(a):
    """The reference against itself shifted by (dx, dy) pixels: a known-answer run on real data."""
    mref = make_ref(a)
    dx, dy = (int(v) for v in a.shift.split(","))
    ref = mref.land
    cand = np.zeros_like(ref)
    H, W = ref.shape
    cand[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = \
        ref[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
    cov = np.zeros_like(ref)
    cov[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = True
    del ref
    res, ov = crop_and_evaluate(mref, cand, cov, a.cap, a.conn)
    del cand, cov
    return finish(a, mref, res, ov, {"mode": "sanity", "shift_px": [dx, dy]})


def cmd_plan(a):
    mref = make_ref(a)
    win = tuple(int(v) for v in a.window.split(",")) if a.window else None
    blocks = plan_blocks(mref, a.scale, a.origin, win)
    cmds = []
    for i, b in enumerate(blocks):
        out = f"{a.out_root}/b{i:02d}" if a.out_root else f"<out>/b{i:02d}"
        b["out"] = out
        b["command"] = (f"python tools/fh.py sample --instance {a.instance} --modset {a.modset} --names {a.name} "
                        f"--seed {a.seed} --size {b['size']} --step {b['step']} "
                        f"--center {b['center'][0]},{b['center'][1]} --out {out}")
        cmds.append(b["command"])
    plan = {"map": mref.key, "scale": str(a.scale), "origin": a.origin, "name": a.name, "blocks": blocks,
            "sample_command": f"python mod/tools/t1_metrics.py sample --map {mref.key} "
                              f"--scale {a.scale} --origin {a.origin} --name {a.name} --runs "
                              + " ".join(b["out"] for b in blocks)}
    if a.out_json:
        Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out_json).write_text(json.dumps(plan, indent=1), encoding="utf-8")
    for c in cmds:
        print(c)
    print(plan["sample_command"])
    print(f"RESULT ok blocks={len(blocks)} scale={a.scale} json={a.out_json or '-'}")
    return 0


# ------------------------------------------------------------------------------------------------
# Self-test on synthetic cases (no game run)

def _brute_distance(ref, r, c):
    tr, tc = np.nonzero(ref != ref[r, c])
    ad = lambda d: np.maximum(np.abs(d) - 0.5, 0.0)  # noqa: E731
    return float(np.sqrt(ad(tr - r) ** 2 + ad(tc - c) ** 2).min())


def _bfs_labels(mask, conn):
    H, W = mask.shape
    lab = np.full((H, W), -1, int)
    n = 0
    nb = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if conn == 8 else [])
    for r in range(H):
        for c in range(W):
            if mask[r, c] and lab[r, c] < 0:
                stack = [(r, c)]
                lab[r, c] = n
                while stack:
                    y, x = stack.pop()
                    for dy, dx in nb:
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and lab[yy, xx] < 0:
                            lab[yy, xx] = n
                            stack.append((yy, xx))
                n += 1
    return lab, n


def synthetic_case():
    """40 x 48 reference with a mainland, a river and six islands, and a candidate with known errors."""
    H, W = 40, 48
    ref = np.zeros((H, W), bool)
    ref[5:35, 5:25] = True          # mainland, 600 px
    ref[5:21, 15] = False           # 16 px river into the mainland (thin water)
    thin = np.zeros((H, W), bool)
    thin[5:21, 15] = True
    ref[10, 35] = True              # A: 1 px
    ref[15:17, 35:37] = True        # B: 4 px
    ref[22:25, 33:37] = True        # C: 12 px
    ref[28:33, 40:46] = True        # D: 30 px
    ref[3, 40] = True               # F: 1 px
    ref[3, 42] = True               # G: 1 px
    cand = ref.copy()
    cand[4, 10] = True              # edge-adjacent false land: 0.5
    cand[30, 10] = False            # interior false water: 4.5 (row 35 is water)
    cand[4, 4] = True               # corner-only false land: sqrt(0.5) = 0.7071
    cand[10, 35] = False            # A removed: missing, 0.5
    cand[3, 41] = True              # bridge F-G: both merged, 0.5
    cand[15, 35] = cand[15, 36] = False   # B keeps 2 of 4: present (at least half), 0.5 each
    for r, c in [(23, 34), (23, 35), (22, 33), (22, 34), (22, 35), (22, 36), (24, 33)]:
        cand[r, c] = False          # C keeps 5 of 12: missing; two interior pixels at 1.5
    cand[12, 15] = True             # river pixel: excluded
    cand[38, 2] = True              # stray false land: sqrt(3.5^2 + 2.5^2) = 4.3012
    return ref, thin, cand


def selftest(verbose=True):
    checks = []

    def check(name, got, want, tol=1e-4):
        ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
        checks.append((name, ok, got, want))

    # 1. Synthetic case with hand-computed answers.
    ref, thin, cand = synthetic_case()
    cov = np.ones_like(ref)
    res, ov = evaluate(ref, thin, cand, cov)
    check("evaluated_px", res["evaluated_px"], 40 * 48 - 16)
    check("false_land_px", res["false_land_px"], 4)
    check("false_water_px", res["false_water_px"], 11)
    check("pixel_agreement", res["pixel_agreement"], round((1904 - 15) / 1904, 6))
    inter = int((ref & ~thin).sum()) - 11
    union = int((ref & ~thin).sum()) + 4
    check("land_iou", res["land_iou"], round(inter / union, 6))
    cd = res["coast_deviation_px"]
    check("coast_max", cd["max"], 4.5)
    check("coast_mean", cd["mean"], round((10 * 0.5 + math.sqrt(0.5) + 2 * 1.5 + math.hypot(3.5, 2.5) + 4.5) / 15, 4))
    check("coast_within_half", cd["within_half_px"], 10)
    check("coast_corner_bucket", cd["histogram"]["0.71 (corner)"], 1)
    b = res["islands"]["buckets"]
    check("bucket1", b["1"], {"islands": 3, "present": 2, "separate": 0, "merged": 2, "missing": 1})
    check("bucket2-4", b["2-4"], {"islands": 1, "present": 1, "separate": 1, "merged": 0, "missing": 0})
    check("bucket5-16", b["5-16"], {"islands": 1, "present": 0, "separate": 0, "merged": 0, "missing": 1})
    check("bucket17-64", b["17-64"], {"islands": 1, "present": 1, "separate": 1, "merged": 0, "missing": 0})
    check("bucket65+", b["65+"], {"islands": 1, "present": 1, "separate": 1, "merged": 0, "missing": 0})
    check("d7_agreement_pass", res["d7"]["agreement_pass"], True)
    check("d7_coast_pass", res["d7"]["coast_pass"], False)
    check("overlay_red", int((ov == OV_FALSE_LAND).sum()), 4)
    check("overlay_thin", int((ov == OV_THIN).sum()), 16)
    # Identity: perfect agreement, nothing misclassified.
    res_id, _ = evaluate(ref, thin, ref.copy(), cov)
    check("identity_agreement", res_id["pixel_agreement"], 1.0)
    check("identity_coast_pass", res_id["d7"]["coast_pass"], True)

    # 2. Distances against brute force on random images.
    rng = np.random.default_rng(7)
    worst = 0.0
    for trial in range(6):
        rr = rng.random((37, 41)) < (0.2 + 0.12 * trial)
        rq, cq = np.nonzero(rng.random(rr.shape) < 0.3)
        for target_is_land in (True, False):
            sel = rr[rq, cq] != target_is_land
            q_r, q_c = rq[sel], cq[sel]
            if q_r.size == 0:
                continue
            d = coast_distance(vertical_distance(rr if target_is_land else ~rr), q_r, q_c, cap=64)
            for k in range(q_r.size):
                if not (rr.all() or (~rr).all()):
                    bd = _brute_distance(rr, q_r[k], q_c[k])
                    worst = max(worst, abs(bd - d[k]))
    check("distance_vs_bruteforce_max_error", worst, 0.0, tol=1e-9)
    # Cap: a lone false pixel far from any target is reported as capped.
    far = np.zeros((10, 300), bool)
    far[:, 0] = True
    dfar = coast_distance(vertical_distance(far), np.array([5]), np.array([250]), cap=64)
    check("distance_capped", bool(np.isinf(dfar[0])), True)

    # 3. Islands against a brute-force flood fill on random images (4 and 8 connectivity).
    mismatch = 0
    for trial in range(8):
        rr = rng.random((30, 33)) < 0.35
        cc = rr ^ (rng.random(rr.shape) < 0.12)
        for conn in (4, 8):
            res_r, _ = evaluate(rr, np.zeros_like(rr), cc, np.ones_like(rr), conn=conn, max_list=10 ** 6)
            lab_r, n_r = _bfs_labels(rr, conn)
            lab_g, n_g = _bfs_labels(cc, conn)
            area = np.bincount(lab_r[lab_r >= 0], minlength=n_r)
            got = np.bincount(lab_r[(lab_r >= 0) & cc], minlength=n_r)
            pres = 2 * got >= area
            refs_per_gen = {}
            for i in range(n_r):
                for g in set(lab_g[(lab_r == i) & (lab_g >= 0)].tolist()):
                    refs_per_gen.setdefault(g, set()).add(i)
            merged = np.zeros(n_r, bool)
            for g, s in refs_per_gen.items():
                if len(s) >= 2:
                    merged[list(s)] = True
            for lo, hi, name in BUCKETS:
                inb = (area >= lo) & (area <= (hi if hi else 10 ** 9))
                want = {"islands": int(inb.sum()), "present": int((pres & inb).sum()),
                        "separate": int((pres & inb & ~merged).sum()), "merged": int((pres & inb & merged).sum()),
                        "missing": int((inb & ~pres).sum())}
                if res_r["islands"]["buckets"][name] != want:
                    mismatch += 1
    check("islands_vs_bruteforce_mismatches", mismatch, 0)

    # 4. Sample mode: a synthetic fh-sampler grid at several scales reproduces the candidate.
    mref = eg.MapRef(land=ref, thin=thin)
    for scale in ("1", "3", "6", "0.5", "0.25"):
        for origin in ("floor", "earthmaps"):
            s = eg.as_fraction(scale)
            tcol = eg.pixel_centre_tiles(np.arange(mref.W), mref.wr, s, origin)
            trow = eg.pixel_centre_tiles(np.arange(mref.H), mref.hr, s, origin)
            # The truth per tile: land if any pixel whose centre falls in that tile is candidate land
            # (for scale >= 1 each tile holds at most one pixel centre).
            L = np.zeros((mref.H, mref.W), bool)
            C = np.zeros((mref.H, mref.W), bool)
            want_land = np.zeros_like(cand)
            for blk in plan_blocks(mref, scale, origin):
                size, step = blk["size"], blk["step"]
                X0 = blk["center"][0] - (size // 2) * step
                Y0 = blk["center"][1] - (size // 2) * step
                vals = np.full((size, size), -1.0)
                for r in range(mref.H):
                    jr = trow[r] - Y0
                    if jr < 0 or jr % step or jr // step >= size:
                        continue
                    for c in range(mref.W):
                        jc = tcol[c] - X0
                        if jc < 0 or jc % step or jc // step >= size:
                            continue
                        if cand[r, c]:
                            vals[jr // step, jc // step] = 1.0
                d = {"size": size, "step": step, "cx": blk["center"][0], "cy": blk["center"][1],
                     "values": {"t": vals.ravel().tolist()}, "_file": "synthetic"}
                rows, cols, block, _ = map_sample(mref, d, "t", scale, origin)
                land, fin = land_from_values(block, 0.0, "ge")
                L[np.ix_(rows, cols)] = land
                C[np.ix_(rows, cols)] = fin
            for r in range(mref.H):
                for c in range(mref.W):
                    same = (tcol == tcol[c])[None, :] & (trow == trow[r])[:, None]
                    want_land[r, c] = bool((cand & same).any())
            check(f"sample_s{scale}_{origin}_coverage", int(C.sum()), mref.H * mref.W)
            check(f"sample_s{scale}_{origin}_values", bool((L == want_land).all()), True)
            if s >= 1:
                check(f"sample_s{scale}_{origin}_equals_candidate", bool((L == cand).all()), True)
    # Plan arithmetic for a real map: grid point j of each block is the tile of pixel (c0 + j).
    eu = eg.MapRef("europe")
    for scale in ("1", "3", "6"):
        for blk in plan_blocks(eu, scale):
            c0, r0, _, _ = blk["px_window"]
            size, step = blk["size"], blk["step"]
            xs = blk["center"][0] + (np.arange(size) - size // 2) * step
            want = eg.pixel_centre_tiles(np.arange(c0, c0 + size), eu.wr, scale)
            if not np.array_equal(xs, want):
                check(f"plan_europe_s{scale}", False, True)
                break
        else:
            check(f"plan_europe_s{scale}", True, True)

    # 4b. Grid mode: an ep-s8-dump style grid planned by plan_grid maps back onto every pixel.
    for scale in ("1", "3", "6", "0.5"):
        g = plan_grid(mref, scale)
        tcol = eg.pixel_centre_tiles(np.arange(mref.W), mref.wr, scale)
        trow = eg.pixel_centre_tiles(np.arange(mref.H), mref.hr, scale)
        arr = np.zeros((g["ny"], g["nx"]), np.uint8)
        for r in range(mref.H):
            for c in range(mref.W):
                jx, jy = (tcol[c] - g["x0"]) // g["step"], (trow[r] - g["y0"]) // g["step"]
                arr[jy, jx] = max(arr[jy, jx], int(cand[r, c]))
        rows, cols, block = map_grid(mref, g, arr, scale, "floor")
        want = np.zeros_like(cand)
        for r in range(mref.H):
            for c in range(mref.W):
                same = (tcol == tcol[c])[None, :] & (trow == trow[r])[:, None]
                want[r, c] = bool((cand & same).any())
        got = np.zeros_like(cand)
        got[np.ix_(rows, cols)] = block == 1
        check(f"grid_s{scale}_coverage", int(rows.size * cols.size), mref.H * mref.W)
        check(f"grid_s{scale}_values", bool((got == want).all()), True)

    # 5. Preview mode: an image painted from the candidate at scale 2 maps back exactly.
    s = 2
    S = 128
    img = np.zeros((S, S, 3), np.uint8)
    img[...] = (55, 53, 11)
    cx = cy = 0
    for r in range(mref.H):
        for c in range(mref.W):
            if cand[r, c]:
                continue
            for ty in range((r - mref.hr) * s, (r - mref.hr) * s + s):      # pixel r covers these tiles
                for tx in range((c - mref.wr) * s, (c - mref.wr) * s + s):
                    py, px = ty - (cy - S // 2), tx - (cx - S // 2)
                    if 0 <= py < S and 0 <= px < S:
                        img[py, px] = (51, 83, 95)
    tmp = Path(tempfile.mkdtemp(prefix="s8-selftest-"))   # outside the repo
    pth = tmp / "t1-selftest-preview.png"
    Image.fromarray(img).save(pth)
    land_px = preview_land(pth, water_colour_set(BASE_WATER_COLOURS.values()))
    Lp, Cp = map_preview(mref, land_px, (cx, cy), s, "floor")
    check("preview_coverage", int(Cp.sum()), mref.H * mref.W)
    check("preview_equals_candidate", bool((Lp == cand).all()), True)

    bad = [c for c in checks if not c[1]]
    if verbose:
        for name, ok, got, want in checks:
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}" + ("" if ok else f" want {want!r}"))
    print(f"RESULT {'ok' if not bad else 'fail'} selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--map", choices=eg.MAPS)
        p.add_argument("--ref-land", help="custom reference land PNG (instead of --map)")
        p.add_argument("--ref-thin", help="custom thin-water PNG")
        p.add_argument("--wr", type=int)
        p.add_argument("--hr", type=int)
        p.add_argument("--cap", type=float, default=DEFAULT_CAP, help="coast distance cap in pixels")
        p.add_argument("--conn", type=int, choices=(4, 8), default=4)
        p.add_argument("--out-json")
        p.add_argument("--overlay", help="difference overlay PNG (palette)")

    p = sub.add_parser("array", help="land decision as a PNG or .npy at reference pixels")
    common(p)
    p.add_argument("--candidate", required=True)
    p.add_argument("--cand-origin", help="col,row of the candidate's top-left pixel in the reference")
    p.set_defaults(fn=cmd_array)

    p = sub.add_parser("sample", help="fh.py sample runs of a land expression at pixel centres")
    common(p)
    p.add_argument("--runs", nargs="+", required=True, help="fh.py sample run dirs or sample.json files")
    p.add_argument("--name", required=True, help="sampled expression name")
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--land-when", choices=("ge", "gt", "le", "lt"), default="ge")
    p.add_argument("--candidate-out", help="write the assembled land decision PNG (grey 128 = not covered)")
    p.set_defaults(fn=cmd_sample)

    p = sub.add_parser("preview", help="fh.py preview PNG classified by water tile colours")
    common(p)
    p.add_argument("--preview", required=True)
    p.add_argument("--preview-offset", default="0,0", help="the fh.py preview --offset, in tiles")
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--water-colours-from", help="fh.py dump-data data-raw-dump.json (water_tile tiles)")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("plan", help="fh.py sample commands that put grid points on pixel centres")
    p.add_argument("--map", choices=eg.MAPS)
    p.add_argument("--ref-land")
    p.add_argument("--ref-thin")
    p.add_argument("--wr", type=int)
    p.add_argument("--hr", type=int)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--window", help="col,row,width,height in reference pixels (default: whole map)")
    p.add_argument("--name", default="<land-expression>")
    p.add_argument("--instance", default="<instance>")
    p.add_argument("--modset", default="<modset>")
    p.add_argument("--seed", default="1000")
    p.add_argument("--out-root")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("grid", help="ep-s8-dump grid runs (one run per map and scale, no 1024 cap)")
    common(p)
    p.add_argument("--runs", nargs="+", required=True, help="dump_render run dirs or dump JSON files with a grid")
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--candidate-out")
    p.set_defaults(fn=cmd_grid)

    p = sub.add_parser("plan-grid", help="the dump_render run command for a whole-map grid at pixel centres")
    p.add_argument("--map", choices=eg.MAPS)
    p.add_argument("--ref-land")
    p.add_argument("--ref-thin")
    p.add_argument("--wr", type=int)
    p.add_argument("--hr", type=int)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--window")
    p.add_argument("--name", default="<land-expression>")
    p.add_argument("--threshold", default="0")
    p.add_argument("--land-when", choices=("ge", "gt", "le", "lt"), default="ge")
    p.add_argument("--instance", default="<instance>")
    p.add_argument("--modset", default="<modset>")
    p.add_argument("--seed", default="1000")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_plan_grid)

    p = sub.add_parser("sanity", help="the reference against a shifted copy of itself (real data)")
    common(p)
    p.add_argument("--shift", default="0,0", help="dx,dy in pixels")
    p.set_defaults(fn=cmd_sanity)

    p = sub.add_parser("selftest", help="synthetic cases with known answers")
    p.set_defaults(fn=lambda a: selftest())

    a = ap.parse_args()
    import tnguard
    tnguard.refuse_live_outputs(a, "t1_metrics.py")
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
