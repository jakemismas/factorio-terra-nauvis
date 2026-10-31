#!/usr/bin/env python3
"""The islets the reference raster lost, from a vector coastline: data-src/bandfix/islets-<map>.json.

EarthMaps' raster holds 45 pixels per degree, about 2.5 km, so an island smaller than a pixel can be missing from it.
RESOLVE Ecoregions 2017 (CC BY 4.0, data-src/bandfix/PROVENANCE.md) draws the world's land as polygons far finer than
that. This tool rasterises them at K subpixels per reference pixel, registers them to the reference block by block,
and lists every polygon component that lies in open sea with a clear pixel between it and all reference land. An islet
takes the pixels it covers by a quarter, or the one it covers most, so the K+ tables hold it as land in open sea
(build_geo.py bandfix_classes) and the handler draws a small island. Nothing else reads these files: the reference
rasters and the coast fit stay as they are.

  python tools/build_islets.py --map olde_world --shp <folder>/Ecoregions2017.shp

The shapefile is not in this repository (149 MB): see the PROVENANCE file for its address and sha256.
"""
import argparse
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

import build_geo as bg
import earthgeo as eg

Image.MAX_IMAGE_PIXELS = None
K = 4                   # subpixels per reference pixel
BLOCK_PX = 225          # registration blocks, 5 degrees
REACH_SUB = 16          # the largest shift tried, in subpixels
STRIP_SUB = 4096        # rows rasterised at once
MIN_SUB = 3             # a smaller component is a rasterising artefact, not an island
MAX_SPAN_SUB = 64       # a larger component is a land mass the raster already holds
COVER_SUB = K * K // 4  # the subpixels that make a pixel an islet's own


def rings(path):
    """Each polygon ring of the shapefile as an array of (lon, lat)."""
    data = Path(path).read_bytes()
    pos, n = 100, len(data)
    while pos < n:
        _, words = struct.unpack(">ii", data[pos:pos + 8])
        st = pos + 8
        if struct.unpack("<i", data[st:st + 4])[0] == 5:
            nparts, npts = struct.unpack("<ii", data[st + 36:st + 44])
            parts = np.frombuffer(data, "<i4", nparts, st + 44)
            pts = np.frombuffer(data, "<f8", npts * 2, st + 44 + 4 * nparts).reshape(-1, 2)
            for k in range(nparts):
                yield pts[int(parts[k]):int(parts[k + 1]) if k + 1 < nparts else npts]
        pos = st + words * 2


def rasterise(path, mref):
    """bool (H K, W K): land at K subpixels per reference pixel; a shapefile's holes run counter-clockwise."""
    W, H = mref.W * K, mref.H * K
    items = []
    for p in rings(path):
        q = np.empty_like(p)
        q[:, 0] = (p[:, 0] - mref.lon_left) * mref.ppd * K
        q[:, 1] = (mref.lat_top - p[:, 1]) * mref.ppd * K
        if q[:, 0].max() < 0 or q[:, 0].min() > W or q[:, 1].max() < 0 or q[:, 1].min() > H or len(q) < 3:
            continue
        x, y = p[:, 0], p[:, 1]
        hole = float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1])) > 0
        items.append((q, hole, q[:, 1].min(), q[:, 1].max()))
    strips = []
    for y0 in range(0, H, STRIP_SUB):
        y1 = min(H, y0 + STRIP_SUB)
        im = Image.new("1", (W, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        for hole in (False, True):
            for q, h, ymin, ymax in items:
                if h == hole and ymax >= y0 and ymin <= y1:
                    pts = q.copy()
                    pts[:, 1] -= y0
                    dr.polygon([tuple(a) for a in pts.tolist()], fill=0 if hole else 1)
        strips.append(np.array(im, bool))
    return np.concatenate(strips, axis=0)


def registration(A, L):
    """Per block of the reference, the subpixel shift (dy, dx) of the polygons, where the block holds a coast; the
    nearest such block's shift elsewhere."""
    H, W = L.shape
    nby, nbx = H // BLOCK_PX + 1, W // BLOCK_PX + 1
    dy, dx, good = np.zeros((nby, nbx)), np.zeros((nby, nbx)), np.zeros((nby, nbx), bool)
    B = BLOCK_PX * K
    window = np.r_[0:REACH_SUB + 1, B - REACH_SUB:B]
    for j in range(nby):
        for i in range(nbx):
            e = A[j * B:(j + 1) * B, i * B:(i + 1) * B]
            r = L[j * BLOCK_PX:(j + 1) * BLOCK_PX, i * BLOCK_PX:(i + 1) * BLOCK_PX]
            if e.shape != (B, B) or r.shape != (BLOCK_PX, BLOCK_PX) or not 0.02 < r.mean() < 0.98:
                continue
            r2 = np.repeat(np.repeat(r, K, 0), K, 1).astype(np.float32)
            cc = np.fft.irfft2(np.fft.rfft2(e.astype(np.float32) - e.mean()) * np.conj(np.fft.rfft2(r2 - r2.mean())),
                               s=e.shape)
            sub = cc[np.ix_(window, window)]
            a, b = np.unravel_index(np.argmax(sub), sub.shape)
            sy, sx = int(window[a]), int(window[b])
            dy[j, i], dx[j, i] = (sy if sy <= REACH_SUB else sy - B), (sx if sx <= REACH_SUB else sx - B)
            good[j, i] = True
    near = ndi.distance_transform_edt(~good, return_distances=False, return_indices=True)
    return ndi.median_filter(dy[tuple(near)], 3), ndi.median_filter(dx[tuple(near)], 3), int(good.sum())


def islets(path, map_key):
    mref = eg.MapRef(map_key)
    cls = bg.ref_classes(mref)
    H, W = cls.shape
    A = rasterise(path, mref)
    L = cls == 1
    dy, dx, blocks = registration(A, L)
    rgb = np.asarray(Image.open(mref.land_path.with_name(f"{map_key}-classes.png")).convert("RGB"))
    open_sea = (cls == 0) & (rgb[..., 0] == 20) & (rgb[..., 1] == 40) & (rgb[..., 2] == 110)
    near_land = ndi.binary_dilation(L, structure=np.ones((3, 3), bool))
    lab, _ = ndi.label(A, structure=np.ones((3, 3), bool))
    out = []
    for k, sl in enumerate(ndi.find_objects(lab)):
        if sl[0].stop - sl[0].start > MAX_SPAN_SUB or sl[1].stop - sl[1].start > MAX_SPAN_SUB:
            continue
        yy, xx = np.nonzero(lab[sl] == k + 1)
        if len(yy) < MIN_SUB:
            continue
        yy, xx = yy + sl[0].start, xx + sl[1].start
        bj = min(int(yy.mean() / (BLOCK_PX * K)), dy.shape[0] - 1)
        bi = min(int(xx.mean() / (BLOCK_PX * K)), dy.shape[1] - 1)
        py, px = ((yy - dy[bj, bi]) / K).astype(int), ((xx - dx[bj, bi]) / K).astype(int)
        if py.min() < 0 or px.min() < 0 or py.max() >= H or px.max() >= W:
            continue
        if near_land[py, px].any() or not open_sea[py, px].all():
            continue
        u, n = np.unique(py * W + px, return_counts=True)
        keep = u[n >= COVER_SUB] if (n >= COVER_SUB).any() else u[np.argmax(n)][None]
        out.append(sorted(int(v) for v in keep))
    out.sort()
    pixels = [[v % W, v // W] for one in out for v in one]
    return {"format": "tn-islets/1", "tool": "tools/build_islets.py", "map": map_key,
            "source": "RESOLVE Ecoregions 2017, CC BY 4.0", "subpixels": K, "blocks_registered": blocks,
            "islets": len(out), "pixels": pixels}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", required=True)
    ap.add_argument("--shp", required=True)
    a = ap.parse_args()
    rec = islets(a.shp, a.map)
    p = bg.BANDFIX_DATA / f"islets-{a.map}.json"
    bg._write_json(p, rec)
    print(f"RESULT ok {a.map}: {rec['islets']} islets, {len(rec['pixels'])} pixels, {p}")


if __name__ == "__main__":
    main()
