"""Decode EarthMaps' world data into reference rasters and statistics.

Usage (run from the Factorio workspace, always with python -I because the input is untrusted):

    python -I mod/tools/earthmaps_decode.py downloads/earthmaps/src \
        --png-out previews/earth-build/reference --json-out mod/data-src/earthmaps

The input is a checkout of https://github.com/HySpeed/EarthMaps. Its data files are Lua, but they are
parsed here as text with strict patterns and never executed. Only numpy and Pillow are needed.

Outputs per map (europe, atlantic, olde_world):
  <png-out>/<map>-classes.png    palette PNG, pixel value = class index (CLASS_CODES order)
  <png-out>/<map>-land.png       1-bit PNG, 1 = land, 0 = water (no out-of-map pixels occur)
  <png-out>/<map>-thinwater.png  1-bit PNG, 1 = water in features under 3 px wide (rivers and
                                 narrow channels); derived, because rivers are not a class
  <json-out>/<map>.json          geometry, georeference, class legend and counts, coast, connectivity,
                                 islands, thin water, straits and isthmuses, cities, sampler simulation
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image

DECODER_VERSION = "1"

# worldgen.lua:17-30 (EarthMaps 2.1.2): data letter -> tile name. Index = palette index in classes.png.
CLASS_CODES = "_oOwWgmGdDsS"
TILE_NAMES = {
    "_": "out-of-map", "o": "deepwater", "O": "deepwater-green", "w": "water", "W": "water-green",
    "g": "grass-1", "m": "grass-3", "G": "grass-2", "d": "dirt-3", "D": "dirt-6",
    "s": "sand-1", "S": "sand-3",
}
WATER_CODES = set("oOwW")
LAND_CODES = set("gmGdDsS")
# Readable palette for the class PNG (the in-game map colours of the grass tiles are nearly identical).
PALETTE = {
    "_": (0, 0, 0), "o": (20, 40, 110), "O": (10, 60, 60), "w": (60, 120, 200), "W": (40, 110, 90),
    "g": (120, 170, 60), "m": (150, 190, 90), "G": (40, 110, 40), "d": (170, 130, 80),
    "D": (110, 80, 50), "s": (235, 215, 150), "S": (200, 170, 100),
}
# map_color from %FACTORIO_GAME%/data/base/prototypes/tile/tiles.lua (2.1.23), line of the map_color entry.
GAME_MAP_COLOR = {
    "_": ([0, 0, 0], 952), "o": ([38, 64, 73], 997), "O": ([0.0941, 0.149, 0.066], 1046),
    "w": ([51, 83, 95], 1094), "W": ([31, 48, 18], 1142), "g": ([55, 53, 11], 1349),
    "G": ([66, 57, 15], 1381), "m": ([65, 52, 28], 1414), "d": ([133, 92, 53], 1571),
    "D": ([80, 55, 31], 1665), "s": ([138, 103, 58], 1730), "S": ([115, 83, 47], 1798),
}
WATER_IDX = np.array([c in WATER_CODES for c in CLASS_CODES])
LAND_IDX = np.array([c in LAND_CODES for c in CLASS_CODES])

MAPS = {  # map key -> (world data file, cities file, EarthMaps world name)
    "europe": ("world_europe.lua", "cities_europe.lua", "Earth - Europe"),
    "atlantic": ("world_atlantic.lua", "cities_atlantic.lua", "Earth - Atlantic"),
    "olde_world": ("world_olde_world.lua", "cities_olde_world.lua", "Earth - Olde World"),
}
SCALES = [0.25, 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]  # settings.lua:29 allowed_values
DETAIL_LEVEL = 2  # config.lua:21
PPD = 45.0  # pixels per degree, fitted below
KM_PER_DEG_LAT = 111.195  # mean Earth radius 6371.0 km

# Geographic extents (deg) used as control points for the georeference fit of the Atlantic raster.
# (name, lat_south, lat_north, lon_west, lon_east, edges used). Values are the commonly published
# extreme points of each land mass; Cape Agulhas, Cap-Vert, Cape Chelyuskin, Cape York and so on.
CONTROL = [
    ("Afro-Eurasia", -34.833, 77.72, -17.53, None, "SNW"),
    ("South America", -53.90, 12.46, -81.33, -34.79, "WE"),
    ("Australia", -39.14, -10.69, 113.16, 153.64, "NSWE"),
    ("Greenland", 59.80, 83.66, -73.07, -11.40, "NWE"),
    ("Madagascar", -25.61, -11.95, 43.19, 50.48, "NSWE"),
    ("Iceland", 63.39, 66.54, -24.53, -13.50, "NSWE"),
    ("Sri Lanka", 5.919, 9.835, 79.69, 81.88, "NSE"),
    ("Tasmania", -43.64, -40.64, 144.60, 148.35, "NSWE"),
    ("Ireland", 51.44, 55.383, -10.48, -5.43, "NSWE"),
    ("Newfoundland", 46.62, 51.63, -59.42, -52.62, "NSWE"),
    ("Taiwan", 21.90, 25.30, 120.03, 122.00, "NSWE"),
    ("Hainan", 18.16, 20.16, 108.61, 111.05, "NSWE"),
    ("Hokkaido", 41.40, 45.52, 139.80, 145.82, "NSE"),
    ("Java", -8.78, -5.88, 105.21, 114.60, "NSWE"),
    ("NZ South Island", -46.67, -40.50, 166.43, 174.32, "NSWE"),
    ("NZ North Island", -41.61, -34.39, 172.64, 178.55, "NSE"),
    ("Vancouver Island", 48.31, 50.78, -128.43, -123.29, "NSWE"),
    ("Cuba", 19.83, 23.20, -84.95, -74.13, "SWE"),
]

# Named straits (must stay open, D17) and isthmuses (must stay closed unless canals, D17/D18).
# (name, kind, window lon0, lon1, lat0, lat1, seed A (lon, lat), seed B (lon, lat), seeds are water
# for straits and land for isthmuses; isthmuses also carry water seeds on both seas).
FEATURES = [
    ("Strait of Gibraltar", "strait", -6.6, -4.6, 35.3, 36.6, (-6.3, 35.95), (-4.9, 36.1), None),
    ("Bosporus", "strait", 28.75, 29.45, 40.85, 41.45, (28.95, 40.95), (29.25, 41.35), None),
    ("Dardanelles", "strait", 25.95, 27.0, 39.85, 40.6, (26.05, 39.95), (26.9, 40.5), None),
    ("Strait of Dover", "strait", 0.6, 2.4, 50.4, 51.6, (1.0, 50.6), (2.1, 51.45), None),
    ("Oresund", "strait", 12.3, 13.1, 55.3, 56.3, (12.6, 56.2), (12.8, 55.4), None),
    ("Great Belt", "strait", 10.6, 11.4, 55.0, 56.0, (11.0, 55.9), (11.0, 55.1), None),
    ("Little Belt", "strait", 9.5, 10.2, 55.0, 55.8, (9.95, 55.7), (9.95, 55.1), None),
    ("Strait of Messina", "strait", 15.3, 15.9, 37.9, 38.5, (15.55, 38.4), (15.5, 38.0), None),
    ("Kerch Strait", "strait", 36.2, 37.0, 44.9, 45.6, (36.7, 45.5), (36.5, 45.0), None),
    ("Isthmus of Corinth", "isthmus", 22.7, 23.3, 37.7, 38.2, (22.95, 37.8), (23.1, 38.1),
     ((22.85, 38.05), (23.15, 37.85))),
    ("Isthmus of Suez", "isthmus", 31.6, 33.2, 29.6, 31.7, (31.9, 30.4), (33.0, 30.4),
     ((32.3, 31.5), (32.55, 29.8))),
    ("Isthmus of Panama", "isthmus", -80.6, -78.8, 8.4, 9.8, (-80.4, 9.0), (-79.0, 9.0),
     ((-79.9, 9.6), (-79.5, 8.6))),
    ("Jutland base (Kiel Canal)", "isthmus", 8.6, 10.6, 53.7, 54.7, (9.6, 54.6), (9.6, 53.85),
     ((8.75, 54.0), (10.35, 54.45))),
]

# Wetlands where a marsh treatment would apply (D14): (name, lon0, lon1, lat0, lat1).
WETLANDS = [
    ("Pripyat Marshes (Polesia)", 25.0, 29.0, 51.5, 52.5),
    ("Danube Delta", 28.7, 29.8, 44.8, 45.5),
    ("Camargue (Rhone delta)", 4.3, 4.9, 43.35, 43.7),
    ("Po Delta", 12.0, 12.6, 44.8, 45.1),
    ("Wadden Sea coast", 4.8, 8.8, 53.0, 53.7),
    ("Sudd", 29.5, 32.0, 6.5, 9.5),
    ("Okavango Delta", 22.0, 23.7, -20.0, -18.5),
    ("Mesopotamian Marshes", 46.5, 47.8, 30.5, 31.5),
    ("Vasyugan Swamp", 75.0, 82.0, 56.0, 58.0),
    ("Sundarbans", 88.5, 89.8, 21.5, 22.5),
    ("Pantanal", -58.0, -55.5, -20.0, -16.0),
    ("Everglades", -81.2, -80.4, 25.2, 26.5),
]

# River reaches for the sampler simulation: (name, upstream (lon, lat), downstream (lon, lat)).
RIVERS = [
    ("Rhine (Mainz to Cologne)", (8.27, 50.0), (6.96, 50.94)),
    ("Danube (Vienna to Budapest)", (16.37, 48.21), (19.05, 47.50)),
    ("Elbe (Magdeburg to Hamburg)", (11.64, 52.13), (9.99, 53.54)),
    ("Vistula (Warsaw to Torun)", (21.03, 52.24), (18.60, 53.01)),
    ("Loire (Orleans to Tours)", (1.90, 47.90), (0.69, 47.40)),
    ("Dnieper (Kyiv to Cherkasy)", (30.55, 50.45), (32.06, 49.44)),
]


# ------------------------------------------------------------------------------------------------
# Strict parsing of untrusted Lua data files

MAX_FILE_BYTES = 64 * 1024 * 1024
ROW_RE = re.compile(r"(?:[A-Za-z][0-9]+)+")
TOKEN_RE = re.compile(r"([A-Za-z])([0-9]+)")
STRING_RE = re.compile(r'"([^"\\\n]*)"')


def read_text(path):
    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        raise ValueError(f"{path}: {size} bytes is over the {MAX_FILE_BYTES} limit")
    with open(path, "rb") as f:
        raw = f.read()
    return raw, raw.decode("ascii")


def parse_world(path):
    """Return (array HxW uint8 of class indices, sha256, row count) from a world_*.lua file."""
    raw, text = read_text(path)
    rows = STRING_RE.findall(text)
    skeleton = STRING_RE.sub("", text)
    if not re.fullmatch(r"\s*return\s*\{[\s,]*\}\s*", skeleton):
        raise ValueError(f"{path}: unexpected structure outside the row strings")
    table = bytearray(256)
    for i in range(256):
        table[i] = 255
    for i, c in enumerate(CLASS_CODES):
        table[ord(c)] = i
    table = bytes(table)
    out, width = [], None
    for n, row in enumerate(rows):
        if not ROW_RE.fullmatch(row):
            raise ValueError(f"{path}: row {n + 1} is not letter-count pairs")
        parts = []
        for m in TOKEN_RE.finditer(row):
            letter, count = m.group(1), int(m.group(2))
            if letter not in CLASS_CODES:
                raise ValueError(f"{path}: row {n + 1} has unknown code {letter!r}")
            if count <= 0 or count > 100000:
                raise ValueError(f"{path}: row {n + 1} has run length {count}")
            parts.append(letter.encode("ascii") * count)
        b = b"".join(parts).translate(table)
        if width is None:
            width = len(b)
        elif len(b) != width:
            raise ValueError(f"{path}: row {n + 1} decodes to {len(b)} px, row 1 to {width}")
        out.append(b)
    arr = np.frombuffer(b"".join(out), dtype=np.uint8).reshape(len(out), width)
    return arr, hashlib.sha256(raw).hexdigest()


CITY_RE = re.compile(
    r'\["([^"\\\n]+)"\]\s*=\s*\{\s*gui_grid\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*,\s*y\s*=\s*(-?\d+)\s*\}\s*,'
    r'\s*position\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*,\s*y\s*=\s*(-?\d+)\s*\}\s*\}')


def parse_cities(path):
    raw, text = read_text(path)
    body = "\n".join(line.split("--", 1)[0] for line in text.splitlines())
    entries = [(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), m.start())
               for m in CITY_RE.finditer(body)]
    if len(entries) != body.count('["'):
        raise ValueError(f"{path}: {body.count(chr(91) + chr(34))} keys but {len(entries)} parsed entries")
    names = [e[0] for e in entries]
    dupes = sorted({n for n in names if names.count(n) > 1})
    lines = {}
    for e in entries:
        lines[e[0]] = body.count("\n", 0, e[5]) + 1
    cities = []
    for full, gx, gy, x, y, _ in entries:
        cities.append({"full_name": full, "name": full.split(", ")[-1], "gui_grid": [gx, gy],
                       "position": [x, y], "file_line": lines[full]})
    return cities, dupes, hashlib.sha256(raw).hexdigest()


def read_git_commit(src):
    try:
        head = open(os.path.join(src, ".git", "HEAD"), encoding="ascii").read().strip()
        if re.fullmatch(r"[0-9a-f]{40}", head):
            return head
        m = re.fullmatch(r"ref: (refs/[A-Za-z0-9._/-]+)", head)
        if not m:
            return None
        ref = m.group(1)
        p = os.path.join(src, ".git", *ref.split("/"))
        if os.path.exists(p):
            sha = open(p, encoding="ascii").read().strip()
        else:
            sha = None
            for line in open(os.path.join(src, ".git", "packed-refs"), encoding="ascii"):
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    sha = parts[0]
        return sha if sha and re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except (OSError, UnicodeDecodeError):
        return None


# ------------------------------------------------------------------------------------------------
# Connected components on run-length rows (no scipy)

def row_runs(mask):
    H, W = mask.shape
    m = np.zeros((H, W + 2), np.int8)
    m[:, 1:-1] = mask
    d = np.diff(m, axis=1)
    rs, cs = np.nonzero(d == 1)
    _, ce = np.nonzero(d == -1)
    return rs.astype(np.int64), cs.astype(np.int64), (ce - 1).astype(np.int64)


def label_runs(rows, starts, ends, H, conn):
    n = len(rows)
    first = np.searchsorted(rows, np.arange(H + 1))
    us, vs = [], []
    ext = 0 if conn == 4 else 1
    for r in range(1, H):
        a0, a1, b0, b1 = first[r - 1], first[r], first[r], first[r + 1]
        if a0 == a1 or b0 == b1:
            continue
        ps, pe = starts[a0:a1], ends[a0:a1]
        lo = np.searchsorted(pe, starts[b0:b1] - ext, "left")
        hi = np.searchsorted(ps, ends[b0:b1] + ext, "right") - 1
        cnt = hi - lo + 1
        ok = cnt > 0
        if not ok.any():
            continue
        ci, cnt, lo = np.nonzero(ok)[0], cnt[ok], lo[ok]
        rep_i = np.repeat(ci, cnt)
        offs = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        us.append(rep_i + b0)
        vs.append(np.repeat(lo, cnt) + offs + a0)
    parent = np.arange(n, dtype=np.int64)
    if us:
        u, v = np.concatenate(us), np.concatenate(vs)
        while True:
            pu, pv = parent[u], parent[v]
            lo_, hi_ = np.minimum(pu, pv), np.maximum(pu, pv)
            k = lo_ != hi_
            if not k.any():
                break
            np.minimum.at(parent, hi_[k], lo_[k])
            while True:
                pp = parent[parent]
                if np.array_equal(pp, parent):
                    break
                parent = pp
    roots, comp = np.unique(parent, return_inverse=True)
    return comp, len(roots)


def components(mask, conn=4):
    H, W = mask.shape
    rows, s, e = row_runs(mask)
    comp, nc = label_runs(rows, s, e, H, conn)
    length = e - s + 1
    area = np.bincount(comp, weights=length, minlength=nc).astype(np.int64)
    x0 = np.full(nc, 1 << 40, np.int64)
    x1 = np.full(nc, -1, np.int64)
    y0 = np.full(nc, 1 << 40, np.int64)
    y1 = np.full(nc, -1, np.int64)
    np.minimum.at(x0, comp, s)
    np.maximum.at(x1, comp, e)
    np.minimum.at(y0, comp, rows)
    np.maximum.at(y1, comp, rows)
    border = (x0 == 0) | (y0 == 0) | (x1 == W - 1) | (y1 == H - 1)
    return {"n": nc, "area": area, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "border": border,
            "comp": comp, "rows": rows, "s": s, "e": e}


def label_image(C, shape):
    """Dense label image (int32, -1 = background) from a components() result."""
    H, W = shape
    lab = np.full((H, W), -1, np.int32)
    for r, s, e, c in zip(C["rows"].tolist(), C["s"].tolist(), C["e"].tolist(), C["comp"].tolist()):
        lab[r, s:e + 1] = c
    return lab


# ------------------------------------------------------------------------------------------------
# Morphology with square structuring elements

def fits_square(m, k):
    """fits[r, c] is True when the k x k square with top-left (r, c) lies inside m."""
    H, W = m.shape
    if H < k or W < k:
        return np.zeros((max(H - k + 1, 0), max(W - k + 1, 0)), bool)
    h = m[:, :W - k + 1].copy()
    for i in range(1, k):
        h &= m[:, i:W - k + 1 + i]
    f = h[:H - k + 1, :].copy()
    for i in range(1, k):
        f &= h[i:H - k + 1 + i, :]
    return f


def covered_by_square(m, k):
    """True where some k x k square lying inside m covers the pixel (morphological opening)."""
    H, W = m.shape
    f = fits_square(m, k)
    out = np.zeros((H, W), bool)
    if f.size == 0:
        return out
    hh = np.zeros((f.shape[0], W), bool)
    for j in range(k):
        hh[:, j:j + f.shape[1]] |= f
    for i in range(k):
        out[i:i + f.shape[0], :] |= hh
    return out


def adj4(m):
    o = np.zeros_like(m)
    o[1:, :] |= m[:-1, :]
    o[:-1, :] |= m[1:, :]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    return o


def checkerboards(a_mask):
    """2x2 blocks where a_mask pixels touch only diagonally (both other pixels are not a_mask)."""
    m, n = a_mask, ~a_mask
    d1 = m[:-1, :-1] & m[1:, 1:] & n[:-1, 1:] & n[1:, :-1]
    d2 = m[:-1, 1:] & m[1:, :-1] & n[:-1, :-1] & n[1:, 1:]
    return d1, d2


def max_passable_square(mask, seed_a, seed_b, kmax=60):
    """Largest k such that a k x k square of mask can travel (4-connected steps) from a placement
    covering seed_a to one covering seed_b. 0 when even single pixels do not connect."""
    best = 0
    for k in range(1, kmax + 1):
        f = fits_square(mask, k)
        if f.size == 0:
            break
        C = components(f, 4)
        lab = label_image(C, f.shape)

        def labels_at(seed):
            r, c = seed
            sub = lab[max(r - k + 1, 0):r + 1, max(c - k + 1, 0):c + 1]
            return set(sub[sub >= 0].tolist())
        if labels_at(seed_a) & labels_at(seed_b):
            best = k
        else:
            break
    return best


def connected(mask, seed_a, seed_b, conn):
    C = components(mask, conn)
    lab = label_image(C, mask.shape)
    la, lb = lab[seed_a], lab[seed_b]
    return bool(la >= 0 and la == lb)


# ------------------------------------------------------------------------------------------------
# Georeference

class Geo:
    """Plate carree georeference of a raster cropped from the Atlantic raster."""

    def __init__(self, lon_left_atl, lat_top_atl, dx, dy, W, H, ppd=PPD):
        self.ppd, self.W, self.H = ppd, W, H
        self.lon_left = lon_left_atl + dx / ppd
        self.lat_top = lat_top_atl - dy / ppd
        self.lon_right = self.lon_left + W / ppd
        self.lat_bottom = self.lat_top - H / ppd

    def px(self, lon, lat):
        return int(math.floor((self.lat_top - lat) * self.ppd)), int(math.floor((lon - self.lon_left) * self.ppd))

    def lonlat(self, row, col):
        return self.lon_left + (col + 0.5) / self.ppd, self.lat_top - (row + 0.5) / self.ppd

    def window(self, lon0, lon1, lat0, lat1):
        r0, c0 = self.px(lon0, lat1)
        r1, c1 = self.px(lon1, lat0)
        if r1 < 0 or c1 < 0 or r0 >= self.H or c0 >= self.W:
            return None
        if r0 < 0 or c0 < 0 or r1 >= self.H or c1 >= self.W:
            return "partial"
        return r0, r1 + 1, c0, c1 + 1


def fit_georeference(atl, C_land):
    """Least-squares fit of col = a*lon + b and row = c*lat + d (plate carree) on control points."""
    H, W = atl.shape
    nominal = Geo(-180 + 511 / PPD, 90 - 127 / PPD, 0, 0, W, H)  # only used to pick components
    big = np.nonzero(C_land["area"] >= 500)[0]
    obs, picked = [], []
    for name, s, n, w, e, edges in CONTROL:
        r0, c0 = nominal.px(w if w is not None else -180, n)
        r1, c1 = nominal.px(e if e is not None else 180, s)
        best, best_iou = None, 0.0
        for i in big:
            ix0, ix1 = max(c0, C_land["x0"][i]), min(c1, C_land["x1"][i])
            iy0, iy1 = max(r0, C_land["y0"][i]), min(r1, C_land["y1"][i])
            if ix1 < ix0 or iy1 < iy0:
                continue
            inter = (ix1 - ix0 + 1) * (iy1 - iy0 + 1)
            ua = (c1 - c0 + 1) * (r1 - r0 + 1) + (C_land["x1"][i] - C_land["x0"][i] + 1) * (
                C_land["y1"][i] - C_land["y0"][i] + 1) - inter
            iou = inter / ua
            if iou > best_iou:
                best, best_iou = i, iou
        if best is None or best_iou < 0.3:
            picked.append({"name": name, "matched": False})
            continue
        i = best
        picked.append({"name": name, "matched": True, "iou": round(float(best_iou), 3),
                       "area_px": int(C_land["area"][i]),
                       "bbox_px": [int(C_land["x0"][i]), int(C_land["y0"][i]), int(C_land["x1"][i]), int(C_land["y1"][i])]})
        for edge in edges:
            geo = {"N": n, "S": s, "W": w, "E": e}[edge]
            pxv = {"W": C_land["x0"][i], "E": C_land["x1"][i], "N": C_land["y0"][i], "S": C_land["y1"][i]}[edge] + 0.5
            obs.append((name, edge, geo, float(pxv)))

    def robust(g, p):
        keep = np.ones(len(g), bool)
        for _ in range(10):
            a_, b_ = np.polyfit(g[keep], p[keep], 1)
            r = p - (a_ * g + b_)
            mad = 1.4826 * np.median(np.abs(r[keep] - np.median(r[keep])))
            nk = np.abs(r) <= max(3 * mad, 3.0)
            if (nk == keep).all():
                break
            keep = nk
        return a_, b_, r, keep
    gx = np.array([o[2] for o in obs if o[1] in "WE"])
    px_ = np.array([o[3] for o in obs if o[1] in "WE"])
    gy = np.array([o[2] for o in obs if o[1] in "NS"])
    py_ = np.array([o[3] for o in obs if o[1] in "NS"])
    ax, bx, rx, kx = robust(gx, px_)
    ay, by, ry, ky = robust(gy, py_)
    # alternatives on latitude, for the record
    def merc(lat):
        return np.degrees(np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)))
    def miller(lat):
        return np.degrees(1.25 * np.log(np.tan(np.pi / 4 + 0.4 * np.radians(lat))))
    alt = {}
    for nm, fn in (("mercator", merc), ("miller", miller)):
        g2 = fn(gy)
        a2, b2 = np.polyfit(g2, py_, 1)
        alt[nm] = round(float(np.sqrt(((py_ - (a2 * g2 + b2)) ** 2).mean())), 1)
    alt["equirectangular"] = round(float(np.sqrt((ry ** 2).mean())), 1)
    lon_left = -180 + 511 / PPD
    lat_top = 90 - 127 / PPD
    srx = px_[kx] - (gx[kx] - lon_left) * PPD
    sry = py_[ky] - (lat_top - gy[ky]) * PPD
    dropped = [f"{o[0]} {o[1]}" for o, k in zip([o for o in obs if o[1] in "WE"], kx) if not k]
    dropped += [f"{o[0]} {o[1]}" for o, k in zip([o for o in obs if o[1] in "NS"], ky) if not k]
    return {
        "method": "least squares on extreme pixels of matched land components (4-connected), "
                  "outliers dropped above max(3*MAD, 3 px); x and y fitted independently",
        "fitted": {
            "px_per_degree_lon": round(float(ax), 4), "px_per_degree_lat": round(float(-ay), 4),
            "lon_at_left_edge": round(float(-bx / ax), 4), "lat_at_top_edge": round(float(-by / ay), 4),
            "rms_x_px": round(float(np.sqrt((rx[kx] ** 2).mean())), 2),
            "rms_y_px": round(float(np.sqrt((ry[ky] ** 2).mean())), 2),
            "n_x": int(kx.sum()), "n_x_total": len(kx), "n_y": int(ky.sum()), "n_y_total": len(ky),
            "dropped": dropped,
        },
        "rms_y_px_all_points_by_projection": alt,
        "snapped": {
            "model": "integer crop (511 columns, 127 rows) of a 16200 x 8100 px, 45 px/deg global plate carree grid",
            "lon_at_left_edge": round(lon_left, 6), "lat_at_top_edge": round(lat_top, 6),
            "rms_x_px": round(float(np.sqrt((srx ** 2).mean())), 2),
            "rms_y_px": round(float(np.sqrt((sry ** 2).mean())), 2),
            "mean_x_px": round(float(srx.mean()), 2), "mean_y_px": round(float(sry.mean()), 2),
        },
        "controls": picked,
        "observations": [{"feature": o[0], "edge": o[1], "geo_deg": o[2], "px": o[3]} for o in obs],
    }, lon_left, lat_top


def find_offset(big, small):
    """Locate small inside big by exact row-snippet matches; returns (dy, dx) or None."""
    hits = []
    for rb in np.linspace(small.shape[0] * 0.1, small.shape[0] * 0.9, 6).astype(int):
        row = small[rb]
        best, bi = -1, 0
        for i in range(0, small.shape[1] - 400, 200):
            t = int(np.count_nonzero(np.diff(row[i:i + 400])))
            if t > best:
                best, bi = t, i
        if best < 20:
            continue
        snip = row[bi:bi + 400].tobytes()
        for ra in range(big.shape[0]):
            j = big[ra].tobytes().find(snip)
            if j >= 0:
                hits.append((ra - rb, j - bi))
                break
    if hits and all(h == hits[0] for h in hits):
        return hits[0], len(hits)
    return None, len(hits)


# ------------------------------------------------------------------------------------------------
# Port of EarthMaps' generateTileName (worldgen.lua:239-311) for small windows

def em_sample(data, s, xs, ys, rng):
    """Class index per tile for integer tile coordinates xs, ys at scale s. 0 = out-of-map."""
    H, W = data.shape
    hr, wr = int(math.floor((H + 0.5) / 2)), int(math.floor((W + 0.5) / 2))
    X, Y = xs / s, ys / s
    top, left = np.floor(Y).astype(np.int64), np.floor(X).astype(np.int64)
    bottom, right = top + 1, left + 1

    def code(cx, cy):
        out = np.zeros(cx.shape, np.int16)  # '_' outside the data (worldgen.lua:222)
        inside = (cy >= -hr) & (cy <= hr) & (cx >= -wr) & (cx <= wr)
        row = cy + hr
        row = np.where(row >= H, row - 1, row)  # compressed_data[y+hr+1] or compressed_data[y+hr]
        col = cx + wr
        empty = inside & (col >= W)  # string.sub past the end gives ""
        ok = inside & ~empty
        out[ok] = data[row[ok], col[ok]]
        out[empty] = -1
        return out
    lt, rt, lb, rb = code(left, top), code(right, top), code(left, bottom), code(right, bottom)
    result = lt.copy()
    alleq = (lt == rt) & (lt == lb) & (lt == rb)
    anyempty = (lt == -1) | (rt == -1) | (lb == -1) | (rb == -1)
    todo = ~alleq & ~anyempty
    result[~alleq & anyempty] = 0
    ms = max(s / DETAIL_LEVEL, 20)
    sd = math.sqrt(DETAIL_LEVEL)
    Xt, Yt = X[todo], Y[todo]
    ty, by = (top[todo] - Yt) ** 2, (bottom[todo] - Yt) ** 2
    lx, rx = (left[todo] - Xt) ** 2, (right[todo] - Xt) ** 2
    n = int(todo.sum())
    w = [(1 - np.sqrt(ty + lx) / sd) ** 2 + rng.random(n) / ms,
         (1 - np.sqrt(ty + rx) / sd) ** 2 + rng.random(n) / ms,
         (1 - np.sqrt(by + lx) / sd) ** 2 + rng.random(n) / ms,
         (1 - np.sqrt(by + rx) / sd) ** 2 + rng.random(n) / ms]
    c = [lt[todo], rt[todo], lb[todo], rb[todo]]
    sums = [sum(w[j] * (c[j] == c[i]) for j in range(4)) for i in range(4)]
    best_c, best_s = c[0].copy(), sums[0].copy()
    for i in (1, 2, 3):
        better = sums[i] > best_s
        best_c[better], best_s[better] = c[i][better], sums[i][better]
    result[todo] = best_c
    return result


def simulate_river(data, geo, name, up, down, scales, rng_seed=1):
    """Run the EarthMaps sampler over a river reach at each scale and test water continuity."""
    H, W = data.shape
    water = WATER_IDX[data]
    ra, ca = geo.px(*up)
    rb_, cb = geo.px(*down)

    def snap(r, c):
        best = None
        for rad in range(0, 8):
            sub = water[max(r - rad, 0):r + rad + 1, max(c - rad, 0):c + rad + 1]
            ys, xs = np.nonzero(sub)
            if len(ys):
                d = (ys + max(r - rad, 0) - r) ** 2 + (xs + max(c - rad, 0) - c) ** 2
                i = int(np.argmin(d))
                best = (int(ys[i] + max(r - rad, 0)), int(xs[i] + max(c - rad, 0)))
                break
        return best
    A, B = snap(ra, ca), snap(rb_, cb)
    if A is None or B is None:
        return {"river": name, "error": "no water pixel within 7 px of an end point"}
    m = 25
    r0, r1 = max(min(A[0], B[0]) - m, 0), min(max(A[0], B[0]) + m + 1, H)
    c0, c1 = max(min(A[1], B[1]) - m, 0), min(max(A[1], B[1]) + m + 1, W)
    win_w = water[r0:r1, c0:c1]
    a_w, b_w = (A[0] - r0, A[1] - c0), (B[0] - r0, B[1] - c0)
    res = {"river": name, "end_points_px": [list(A), list(B)],
           "pixels": {"connected_4": connected(win_w, a_w, b_w, 4), "connected_8": connected(win_w, a_w, b_w, 8)}}
    hr, wr = int(math.floor((H + 0.5) / 2)), int(math.floor((W + 0.5) / 2))
    rng = np.random.default_rng(rng_seed)
    out = []
    for s in scales:
        x0, x1 = int(math.floor((c0 - wr) * s)), int(math.ceil((c1 - 1 - wr) * s))
        y0, y1 = int(math.floor((r0 - hr) * s)), int(math.ceil((r1 - 1 - hr) * s))
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        cls = em_sample(data, s, xs.astype(np.float64), ys.astype(np.float64), rng)
        wt = np.isin(cls, [CLASS_CODES.index(ch) for ch in "oOwW"])

        def tile_of(p):
            return int(round((p[0] - hr) * s)) - y0, int(round((p[1] - wr) * s)) - x0

        ta, tb = tile_of(A), tile_of(B)

        def snap_t(t):
            for rad in range(0, int(3 * max(s, 1)) + 3):
                sub = wt[max(t[0] - rad, 0):t[0] + rad + 1, max(t[1] - rad, 0):t[1] + rad + 1]
                ys2, xs2 = np.nonzero(sub)
                if len(ys2):
                    return int(ys2[0] + max(t[0] - rad, 0)), int(xs2[0] + max(t[1] - rad, 0))
            return None
        ta, tb = snap_t(ta), snap_t(tb)
        if ta is None or tb is None:
            out.append({"scale": s, "connected_4": False, "note": "end point lost"})
            continue
        c4 = connected(wt, ta, tb, 4)
        k = max_passable_square(wt, ta, tb, kmax=int(2 * max(s, 1)) + 4) if c4 else 0
        Cw = components(wt, 4)
        out.append({"scale": s, "connected_4": c4, "max_square_tiles": k,
                    "water_components_4_in_window": int(Cw["n"])})
    res["by_scale"] = out
    return res


# ------------------------------------------------------------------------------------------------
# Per-map analysis

def size_histogram(area):
    edges = [1, 2, 3, 5, 9, 17, 33, 65, 129, 257, 513, 1025, 4097, 16385, 65537, 1 << 62]
    out = {}
    for lo, hi in zip(edges[:-1], edges[1:]):
        out[f"{lo}-{hi - 1}" if hi < (1 << 62) else f">={lo}"] = int(((area >= lo) & (area < hi)).sum())
    return out


def analyse(key, arr, geo, info, cities, city_dupes, sim_rivers):
    H, W = arr.shape
    hr, wr = int(math.floor((H + 0.5) / 2)), int(math.floor((W + 0.5) / 2))
    land = LAND_IDX[arr]
    water = WATER_IDX[arr]
    counts = np.bincount(arr.ravel(), minlength=len(CLASS_CODES))
    total = H * W
    J = {"map": key, "earthmaps_world": MAPS[key][2]}
    J.update(info)
    J["width_px"], J["height_px"] = W, H
    J["earthmaps_radii"] = {"decompressed_width_radius": wr, "decompressed_height_radius": hr,
                            "source": "worldgen.lua:444,448 floor((n + 0.5) / 2)"}
    km_px = KM_PER_DEG_LAT / geo.ppd
    J["georeference"] = {
        "projection": "plate carree (equirectangular): column linear in longitude, row linear in latitude",
        "px_per_degree": geo.ppd,
        "lon_left_edge": round(geo.lon_left, 4), "lon_right_edge": round(geo.lon_right, 4),
        "lat_top_edge": round(geo.lat_top, 4), "lat_bottom_edge": round(geo.lat_bottom, 4),
        "pixel_centre_formula": "lon = lon_left_edge + (col + 0.5) / 45; lat = lat_top_edge - (row + 0.5) / 45 (0-based col, row)",
        "km_per_px_north_south": round(km_px, 4),
        "km_per_px_east_west_at": {f"{lat}N": round(km_px * math.cos(math.radians(lat)), 4) for lat in (0, 30, 45, 50, 55, 60, 70)},
        "earthmaps_tile_origin": {
            "lon": round(geo.lon_left + (wr + 0.5) / geo.ppd, 4), "lat": round(geo.lat_top - (hr + 0.5) / geo.ppd, 4),
            "note": "tile (0, 0) samples pixel (col wr, row hr); tile (x, y) at scale s samples pixel (x/s + wr, y/s + hr), worldgen.lua:221-224,244",
        },
        "status": "derived: least-squares fit on the Atlantic raster (see atlantic.json georeference_fit) plus exact crop offsets; datum assumed WGS84",
    }
    J["world_size_tiles_by_scale"] = [
        {"scale": s, "width": int(math.floor(W * s)), "height": int(math.floor(H * s)),
         "tiles": int(math.floor(W * s)) * int(math.floor(H * s)),
         "land_tiles_approx": int(round(int(land.sum()) * s * s)),
         "km_per_tile_north_south": round(km_px / s, 4)}
        for s in SCALES]
    legend = []
    for i, c in enumerate(CLASS_CODES):
        legend.append({"index": i, "code": c, "tile": TILE_NAMES[c], "is_land": c in LAND_CODES,
                       "is_water": c in WATER_CODES, "pixels": int(counts[i]),
                       "fraction": round(float(counts[i]) / total, 6), "png_rgb": PALETTE[c],
                       "game_map_color": GAME_MAP_COLOR[c][0],
                       "game_map_color_source": f"data/base/prototypes/tile/tiles.lua:{GAME_MAP_COLOR[c][1]}"})
    J["class_legend"] = {"source": "worldgen.lua:17-30", "classes": legend,
                         "codes_present": [c for i, c in enumerate(CLASS_CODES) if counts[i]]}
    J["land_px"], J["water_px"] = int(land.sum()), int(water.sum())
    J["land_fraction"] = round(float(land.sum()) / total, 6)
    J["out_of_map_px"] = int(counts[0])
    J["land_mask_rule"] = ("land = g m G d D s S (grass-1, grass-3, grass-2, dirt-3, dirt-6, sand-1, sand-3); "
                           "water = o O w W. Rivers, lakes, marsh and the 1 px coastline stroke are all water "
                           "classes in the data, so they count as water. No shallow-water class exists.")
    near_land = water & adj4(land)
    coast = land & adj4(water)
    J["coast_px"] = int(coast.sum())
    J["coast_definition"] = "land pixels 4-adjacent to a water pixel inside the raster (the raster border is not water)"
    J["water_px_adjacent_to_land_by_class"] = {CLASS_CODES[i]: int(c) for i, c in enumerate(np.bincount(arr[near_land], minlength=12)) if c}
    J["coast_px_touching_o"] = int((coast & adj4(arr == CLASS_CODES.index("o"))).sum())
    d1, d2 = checkerboards(water)
    J["diagonal_only_links"] = {"count": int(d1.sum() + d2.sum()),
                                "definition": "2x2 blocks with water on one diagonal and land on the other: water joins only in 8-connectivity, and land likewise"}
    # connectivity
    conn = {}
    comps = {}
    for nm, m in (("land", land), ("water", water)):
        for c in (4, 8):
            C = components(m, c)
            comps[(nm, c)] = C
            area = C["area"]
            interior = ~C["border"]
            conn[f"{nm}_{c}"] = {"components": int(C["n"]), "not_touching_border": int(interior.sum()),
                                 "largest_px": [int(v) for v in np.sort(area)[::-1][:5]],
                                 "size_histogram": size_histogram(area)}
    J["connectivity"] = conn
    CL = comps[("land", 4)]
    order = np.argsort(CL["area"], kind="stable")
    J["smallest_islands_px_4conn"] = [int(v) for v in CL["area"][order[:20]]]
    J["smallest_islands_px_8conn"] = [int(v) for v in np.sort(comps[("land", 8)]["area"])[:20]]
    big = []
    for i in order[::-1][:12]:
        lw, lt_ = geo.lonlat(CL["y0"][i], CL["x0"][i])
        le, lb_ = geo.lonlat(CL["y1"][i], CL["x1"][i])
        big.append({"area_px": int(CL["area"][i]), "bbox_px": [int(CL["x0"][i]), int(CL["y0"][i]), int(CL["x1"][i]), int(CL["y1"][i])],
                    "bbox_lonlat": [round(lw, 2), round(lb_, 2), round(le, 2), round(lt_, 2)],
                    "touches_border": bool(CL["border"][i])})
    J["largest_land_components_4conn"] = big
    CWi = comps[("water", 4)]
    lakes = ~CWi["border"]
    J["lakes_4conn"] = {"count": int(lakes.sum()), "size_histogram": size_histogram(CWi["area"][lakes]),
                        "definition": "water components (4-connected) that do not touch the raster border"}
    # thin water
    cov2 = covered_by_square(water, 2)
    cov3 = covered_by_square(water, 3)
    thin = water & ~cov3
    w1 = water & ~cov2
    w2 = cov2 & ~cov3
    CT = components(thin, 8)
    keep = CT["area"] >= 20
    river_mask = np.zeros_like(thin)
    for r, s, e, c in zip(CT["rows"].tolist(), CT["s"].tolist(), CT["e"].tolist(), CT["comp"].tolist()):
        if keep[c]:
            river_mask[r, s:e + 1] = True
    td1, td2 = checkerboards(water)
    diag_in_thin = int((td1 & thin[:-1, :-1] & thin[1:, 1:]).sum() + (td2 & thin[:-1, 1:] & thin[1:, :-1]).sum())
    tcounts = np.bincount(arr[thin], minlength=12)
    J["thin_water"] = {
        "definition": "water pixels not covered by any all-water 3x3 square (morphological opening); width 1 = not covered by any all-water 2x2 square",
        "px": int(thin.sum()), "width_1_px": int(w1.sum()), "width_2_px": int(w2.sum()),
        "by_class": {CLASS_CODES[i]: int(c) for i, c in enumerate(tcounts) if c},
        "components_8conn": int(CT["n"]), "components_8conn_ge_20px": int(keep.sum()),
        "px_in_components_ge_20px": int(river_mask.sum()),
        "diagonal_only_links_inside_thin_water": diag_in_thin,
        "png": f"{key}-thinwater.png (all thin water, not only components >= 20 px)",
    }
    # named straits and isthmuses
    feats = []
    for name, kind, lo0, lo1, la0, la1, sa, sb, wseeds in FEATURES:
        win = geo.window(lo0, lo1, la0, la1)
        if win is None or win == "partial":
            feats.append({"name": name, "kind": kind, "in_map": win is not None, "measured": False})
            continue
        r0, r1, c0, c1 = win
        wl, ww = land[r0:r1, c0:c1], water[r0:r1, c0:c1]

        def seed(lonlat, mask):
            r, c = geo.px(*lonlat)
            r, c = r - r0, c - c0
            for rad in range(0, 6):
                sub = mask[max(r - rad, 0):r + rad + 1, max(c - rad, 0):c + rad + 1]
                ys, xs = np.nonzero(sub)
                if len(ys):
                    d = (ys + max(r - rad, 0) - r) ** 2 + (xs + max(c - rad, 0) - c) ** 2
                    i = int(np.argmin(d))
                    return int(ys[i] + max(r - rad, 0)), int(xs[i] + max(c - rad, 0))
            return None
        lat_mid = (la0 + la1) / 2
        rec = {"name": name, "kind": kind, "in_map": True, "measured": True,
               "window_px": [int(c0), int(r0), int(c1 - 1), int(r1 - 1)], "window_lonlat": [lo0, la0, lo1, la1],
               "km_per_px_ns": round(km_px, 3), "km_per_px_ew": round(km_px * math.cos(math.radians(lat_mid)), 3)}
        if kind == "strait":
            A, B = seed(sa, ww), seed(sb, ww)
            if A is None or B is None:
                rec["error"] = "seed not on water"
            else:
                rec["water_connected_4"] = connected(ww, A, B, 4)
                rec["water_connected_8"] = connected(ww, A, B, 8)
                rec["max_passable_water_square_px"] = max_passable_square(ww, A, B)
        else:
            A, B = seed(sa, wl), seed(sb, wl)
            if A is None or B is None:
                rec["error"] = "seed not on land"
            else:
                rec["land_connected_4"] = connected(wl, A, B, 4)
                rec["land_connected_8"] = connected(wl, A, B, 8)
                rec["max_passable_land_square_px"] = max_passable_square(wl, A, B)
            WA, WB = seed(wseeds[0], ww), seed(wseeds[1], ww)
            if WA is None or WB is None:
                rec["water_error"] = "sea seed not on water"
            else:
                rec["seas_connected_by_water_4"] = connected(ww, WA, WB, 4)
                rec["seas_connected_by_water_8"] = connected(ww, WA, WB, 8)
                if rec["seas_connected_by_water_4"]:
                    rec["max_passable_water_square_px"] = max_passable_square(ww, WA, WB)
        feats.append(rec)
    J["straits_and_isthmuses"] = {
        "method": "inside the window only: seeds snapped to the nearest pixel of the right kind within 5 px; "
                  "max_passable_*_square_px = largest k such that a k x k all-water (or all-land) square can move "
                  "in 4-connected steps from a placement covering seed A to one covering seed B (0 = not connected)",
        "features": feats}
    # wetlands
    wl_out = []
    for name, lo0, lo1, la0, la1 in WETLANDS:
        win = geo.window(lo0, lo1, la0, la1)
        if win is None or win == "partial":
            continue
        r0, r1, c0, c1 = win
        sub = arr[r0:r1, c0:c1]
        cc = np.bincount(sub.ravel(), minlength=12)
        wl_out.append({"name": name, "window_lonlat": [lo0, la0, lo1, la1], "px": int(sub.size),
                       "class_fraction": {CLASS_CODES[i]: round(float(c) / sub.size, 4) for i, c in enumerate(cc) if c}})
    J["wetland_windows"] = wl_out
    # climate by latitude band (land only)
    bands = []
    lat_rows = geo.lat_top - (np.arange(H) + 0.5) / geo.ppd
    for b_hi in range(90, -90, -5):
        rows = np.nonzero((lat_rows <= b_hi) & (lat_rows > b_hi - 5))[0]
        if len(rows) == 0:
            continue
        sub = arr[rows[0]:rows[-1] + 1]
        lm = LAND_IDX[sub]
        nl = int(lm.sum())
        if nl == 0:
            continue
        cc = np.bincount(sub[lm], minlength=12)
        bands.append({"lat_band": f"{b_hi - 5} to {b_hi}", "land_px": nl,
                      "class_fraction_of_land": {CLASS_CODES[i]: round(float(c) / nl, 4) for i, c in enumerate(cc) if c}})
    J["land_classes_by_latitude"] = bands
    # cities
    city_out = []
    lab_dist_cache = None
    for c in cities:
        x, y = c["position"]
        col, row = DETAIL_LEVEL * x + wr, DETAIL_LEVEL * y + hr
        rec = {"full_name": c["full_name"], "name": c["name"], "cities_file_line": c["file_line"],
               "position": c["position"], "pixel": [col, row]}
        if 0 <= row < H and 0 <= col < W:
            lon, lat = geo.lonlat(row, col)
            rec["lonlat"] = [round(lon, 3), round(lat, 3)]
            k = int(arr[row, col])
            rec["class"] = CLASS_CODES[k]
            rec["on_land"] = bool(LAND_IDX[k])
            rr = 40
            sub_l = land[max(row - rr, 0):row + rr + 1, max(col - rr, 0):col + rr + 1]
            sub_w = water[max(row - rr, 0):row + rr + 1, max(col - rr, 0):col + rr + 1]
            ys, xs = np.nonzero(sub_w if rec["on_land"] else sub_l)
            if len(ys):
                d = np.sqrt((ys + max(row - rr, 0) - row) ** 2 + (xs + max(col - rr, 0) - col) ** 2)
                rec["nearest_water_px" if rec["on_land"] else "nearest_land_px"] = round(float(d.min()), 2)
            rec["land_fraction_within_10px"] = round(float(LAND_IDX[arr[max(row - 10, 0):row + 11, max(col - 10, 0):col + 11]].mean()), 3)
        else:
            rec["outside_raster"] = True
        tiles = {}
        for s in (1, 2, 4, 6, 10):
            px_, py_ = x * DETAIL_LEVEL * s, y * DETAIL_LEVEL * s
            cx, cy = math.floor(px_ / 32), math.floor(py_ / 32)
            tx, ty = cx * 32 + 16, cy * 32 + 16
            pc, pr = int(round(tx / s)) + wr, int(round(ty / s)) + hr
            onl = bool(LAND_IDX[arr[pr, pc]]) if (0 <= pr < H and 0 <= pc < W) else None
            tiles[str(s)] = {"tile": [tx, ty], "chunk": [cx, cy], "nearest_pixel_on_land": onl}
        rec["spawn_tile_by_scale"] = tiles
        city_out.append(rec)
    chunk_clash = {}
    for s in SCALES:
        seen, clashes = {}, []
        for c in cities:
            x, y = c["position"]
            key_ = (math.floor(x * DETAIL_LEVEL * s / 32), math.floor(y * DETAIL_LEVEL * s / 32))
            if key_ in seen:
                clashes.append([seen[key_], c["name"]])
            else:
                seen[key_] = c["name"]
        chunk_clash[str(s)] = clashes
    J["cities"] = {
        "count": len(cities), "duplicate_keys": city_dupes,
        "position_rule": "tile = chunk centre of (position * 2 * scale), worldgen.lua:38-40; pixel = (2x + wr, 2y + hr)",
        "on_water": [c["name"] for c in city_out if c.get("on_land") is False],
        "same_chunk_clashes_by_scale": chunk_clash,
        "clash_effect": "initCityChunks raises 'Chunk position already exists in chunk map' (worldgen.lua:80-81) when two cities share a chunk",
        "list": city_out}
    if sim_rivers:
        J["river_sampler_simulation"] = {
            "method": "numpy port of generateTileName (worldgen.lua:239-311), including the 4-corner weighted vote and "
                      "random()/max_scale jitter (numpy RNG, seed 1, instead of Factorio's math.random); water = o O w W; "
                      "connected_4 = the two river end points are joined by 4-connected water tiles inside the window",
            "rivers": [simulate_river(arr, geo, *r, scales=[0.25, 0.5, 1, 2, 3, 4, 6]) for r in sim_rivers]}
    return J, land, thin


def save_png(arr, path):
    img = Image.fromarray(np.ascontiguousarray(arr), "P")
    flat = []
    for c in CLASS_CODES:
        flat += list(PALETTE[c])
    img.putpalette(flat + [0] * (768 - len(flat)))
    img.save(path, optimize=False, compress_level=6)


def save_mask(mask, path):
    Image.fromarray(np.ascontiguousarray(mask)).convert("1").save(path, compress_level=6)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="EarthMaps checkout (folder holding info.json and data/)")
    ap.add_argument("--png-out", required=True)
    ap.add_argument("--json-out", required=True)
    ap.add_argument("--maps", default="europe,atlantic,olde_world")
    ap.add_argument("--no-simulation", action="store_true", help="skip the river sampler simulation")
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    info = json.loads(read_text(os.path.join(src, "info.json"))[1])
    meta = {"source": {"repo": "https://github.com/HySpeed/EarthMaps", "commit": read_git_commit(src),
                       "info_json": {k: info.get(k) for k in ("name", "version", "factorio_version", "dependencies")}},
            "decoder": {"script": "tools/earthmaps_decode.py", "version": DECODER_VERSION}}
    os.makedirs(a.png_out, exist_ok=True)
    os.makedirs(a.json_out, exist_ok=True)
    keys = [k.strip() for k in a.maps.split(",") if k.strip()]
    for k in keys:
        if k not in MAPS:
            sys.exit(f"unknown map {k!r}; choose from {sorted(MAPS)}")
    print("decoding atlantic (reference frame for all maps)", flush=True)
    atl, atl_sha = parse_world(os.path.join(src, "data", MAPS["atlantic"][0]))
    C_atl = components(LAND_IDX[atl], 4)
    fit, lon_left_atl, lat_top_atl = fit_georeference(atl, C_atl)
    print(f"georeference: {fit['fitted']}", flush=True)
    for k in keys:
        wfile, cfile, _ = MAPS[k]
        if k == "atlantic":
            arr, sha = atl, atl_sha
            offset, nhits = (0, 0), 6
        else:
            arr, sha = parse_world(os.path.join(src, "data", wfile))
            offset, nhits = find_offset(atl, arr)
            if offset is None:
                sys.exit(f"{k}: could not locate the raster inside atlantic")
        dy, dx = offset
        H, W = arr.shape
        sub = atl[dy:dy + H, dx:dx + W]
        diff = sub != arr
        crop = {"atlantic_offset_rows": int(dy), "atlantic_offset_cols": int(dx), "matched_snippets": nhits,
                "identical_px": int((~diff).sum()), "total_px": int(diff.size)}
        if diff.any():
            ys, xs = np.nonzero(diff)
            pairs = {}
            for x_, y_ in zip(sub[diff].tolist(), arr[diff].tolist()):
                pairs[f"{CLASS_CODES[x_]}->{CLASS_CODES[y_]}"] = pairs.get(f"{CLASS_CODES[x_]}->{CLASS_CODES[y_]}", 0) + 1
            crop["differences"] = {
                "bbox_px": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "atlantic_land_to_water": int((LAND_IDX[sub] & WATER_IDX[arr]).sum()),
                "atlantic_water_to_land": int((WATER_IDX[sub] & LAND_IDX[arr]).sum()),
                "class_changes": dict(sorted(pairs.items(), key=lambda kv: -kv[1]))}
        geo = Geo(lon_left_atl, lat_top_atl, dx, dy, W, H)
        if "differences" in crop:
            b = crop["differences"]["bbox_px"]
            lw, lt_ = geo.lonlat(b[1], b[0])
            le, lb_ = geo.lonlat(b[3], b[2])
            crop["differences"]["bbox_lonlat"] = [round(lw, 2), round(lb_, 2), round(le, 2), round(lt_, 2)]
        cities, dupes, csha = parse_cities(os.path.join(src, "data", cfile))
        info_k = dict(meta)
        info_k["source"] = dict(meta["source"], world_file=f"data/{wfile}", world_file_sha256=sha,
                                cities_file=f"data/{cfile}", cities_file_sha256=csha)
        info_k["crop_of_atlantic"] = crop
        print(f"analysing {k} {W}x{H}", flush=True)
        J, land, thin = analyse(k, arr, geo, info_k, cities, dupes, RIVERS if not a.no_simulation else None)
        if k == "atlantic":
            J["georeference_fit"] = fit
        pngs = {"classes": f"{k}-classes.png", "land": f"{k}-land.png", "thinwater": f"{k}-thinwater.png"}
        save_png(arr, os.path.join(a.png_out, pngs["classes"]))
        save_mask(land, os.path.join(a.png_out, pngs["land"]))
        save_mask(thin, os.path.join(a.png_out, pngs["thinwater"]))
        J["png"] = {n: {"file": f, "sha256": sha256_file(os.path.join(a.png_out, f))} for n, f in pngs.items()}
        with open(os.path.join(a.json_out, f"{k}.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(J, f, indent=1)
        print(f"wrote {k}: classes, land, thinwater PNGs and {k}.json", flush=True)


if __name__ == "__main__":
    main()
