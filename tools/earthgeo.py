"""Shared geometry for the S8 tools: reference rasters, georeference and the tile mapping.

Every S8 tool takes its conventions from this module, so a change of convention is one edit here.

Reference pixels
    Pixel (col, row) is 0-based, row 0 at the top (north). In continuous pixel coordinates (u, v)
    pixel col spans [col, col + 1), so its centre is u = col + 0.5.

Georeference (R1, data-src/earthmaps/<map>.json "georeference")
    u = (lon - lon_left_edge) * 45 and v = (lat_top_edge - lat) * 45 (plate carree, 45 px/degree).

Tile mapping at scale s (tiles per reference pixel on each axis)
    tile-space x = (u - wr - origin) * s and y = (v - hr - origin) * s, with wr, hr the EarthMaps radii
    floor((W + 0.5) / 2) and floor((H + 0.5) / 2) from the reference JSON.
    origin 0 ("floor", the default): tile t samples pixel floor(t / s + wr), the mapping R1's README
        states. Pixel c covers tiles [(c - wr) s, (c - wr + 1) s).
    origin 0.5 ("earthmaps"): EarthMaps' own placement. Its sampler (worldgen.lua:244-284) gives each
        tile the nearest data sample, so pixel c is centred on tile (c - wr) s, half a pixel up and
        left of the floor convention. Use it only to score EarthMaps itself.
    The tile that stands for a pixel is the tile containing the pixel centre, floor(x(col + 0.5)).
    The game evaluates a tile's noise at the tile's integer corner, so at odd scales that sample
    point is not the pixel centre (scale 1: the pixel's top-left corner; scale 3: a third of the
    way in). Even scales put the corner exactly on the pixel centre.
"""
import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image

# The Atlantic reference rasters are 102 M px, above Pillow's decompression-bomb warning limit.
Image.MAX_IMAGE_PIXELS = 400_000_000

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import tnconfig  # noqa: E402

# Ported from the planning spike S8 (spikes/S8-tooling in an earlier prototype): every path
# root the spike derived from its own location now comes from the repo or from FACTORIO_WS. The
# rasters and reference JSON live in data-src/earthmaps/, the harness in the workspace.
# Absolute, so a relative FACTORIO_WS names one folder here and in the tools run in the workspace.
WS = Path(os.path.abspath(os.environ.get("FACTORIO_WS") or r"%FACTORIO_WS%"))
REF_PNG_DIR = REPO / "data-src" / "earthmaps"
REF_JSON_DIR = REPO / "data-src" / "earthmaps"
FH = WS / "tools" / "fh.py"

# The conventions are config.lua's (ARCHITECTURE.md, "The coordinate chain"; U2): one home.
_CFG = tnconfig.load()
MAPS = tuple(_CFG["map_order"])
PX_PER_DEGREE = _CFG["coordinates"]["px_per_degree"]
DEFAULT_ORIGIN = _CFG["coordinates"]["origin"]
CORNER_OFFSET_DIVISOR = _CFG["coordinates"]["corner_offset_divisor"]
ORIGINS = {"floor": Fraction(0), "earthmaps": Fraction(1, 2)}


def corner_offset_tiles(scale):
    """The tent mapping's integer-corner offset at an integer scale: floor(scale / divisor) tiles,
    which makes the tile holding a pixel centre read the fit exactly at that centre (U2)."""
    return int(scale) // CORNER_OFFSET_DIVISOR


def as_fraction(s):
    """Exact scale: '6', 0.25, '1.5' or '3/2' become Fractions, so floor() never rounds wrongly."""
    if isinstance(s, Fraction):
        return s
    if isinstance(s, float):
        return Fraction(s).limit_denominator(1 << 20)
    return Fraction(str(s)).limit_denominator(1 << 20)


def origin_fraction(origin):
    if isinstance(origin, str):
        if origin not in ORIGINS:
            raise ValueError(f"origin must be one of {sorted(ORIGINS)}")
        return ORIGINS[origin]
    return as_fraction(origin)


def load_mask(path):
    """A PNG (any mode) or .npy as a bool array; PNG pixels >= 128 after conversion to L are True."""
    path = Path(path)
    if path.suffix.lower() == ".npy":
        return np.load(path).astype(bool)
    im = Image.open(path)
    if im.mode == "1":
        return np.asarray(im).astype(bool)
    return np.asarray(im.convert("L")) >= 128


class MapRef:
    """One reference map: size, radii, georeference and (lazily) the land and thin-water masks."""

    def __init__(self, key=None, land=None, thin=None, wr=None, hr=None, meta=None):
        self.key = key
        if key is not None:
            if key not in MAPS:
                raise ValueError(f"unknown map {key!r}; use one of {MAPS}")
            meta = json.loads((REF_JSON_DIR / f"{key}.json").read_text(encoding="utf-8"))
            land = land or REF_PNG_DIR / f"{key}-land.png"
            thin = thin or REF_PNG_DIR / f"{key}-thinwater.png"
        self.meta = meta or {}
        self._land = self._thin = None
        self.land_path = self.thin_path = None
        if isinstance(land, np.ndarray):
            self._land = land.astype(bool)
        elif land is not None:
            self.land_path = Path(land)
        if isinstance(thin, np.ndarray):
            self._thin = thin.astype(bool)
        elif thin is not None:
            self.thin_path = Path(thin)
        if self.meta:
            self.W, self.H = int(self.meta["width_px"]), int(self.meta["height_px"])
            radii = self.meta["earthmaps_radii"]
            self.wr = int(radii["decompressed_width_radius"])
            self.hr = int(radii["decompressed_height_radius"])
            g = self.meta["georeference"]
            self.ppd = float(g["px_per_degree"])
            self.lon_left, self.lat_top = float(g["lon_left_edge"]), float(g["lat_top_edge"])
        else:
            self.H, self.W = self.land.shape
            self.wr = int(math.floor((self.W + 0.5) / 2)) if wr is None else int(wr)
            self.hr = int(math.floor((self.H + 0.5) / 2)) if hr is None else int(hr)
            self.ppd, self.lon_left, self.lat_top = 45.0, 0.0, 0.0

    @property
    def land(self):
        if self._land is None:
            self._land = load_mask(self.land_path)
        return self._land

    @property
    def thin(self):
        if self._thin is None:
            self._thin = load_mask(self.thin_path) if self.thin_path else np.zeros_like(self.land)
        return self._thin

    # -- georeference
    def lonlat_to_uv(self, lon, lat):
        return (lon - self.lon_left) * self.ppd, (self.lat_top - lat) * self.ppd

    def uv_to_lonlat(self, u, v):
        return self.lon_left + u / self.ppd, self.lat_top - v / self.ppd

    def pixel_lonlat(self, col, row):
        """Longitude and latitude of a pixel centre."""
        return self.uv_to_lonlat(col + 0.5, row + 0.5)

    def lonlat_to_pixel(self, lon, lat):
        u, v = self.lonlat_to_uv(lon, lat)
        return int(math.floor(u)), int(math.floor(v))

    # -- tiles
    def uv_to_tile(self, u, v, scale, origin="floor"):
        """Continuous tile-space position of a continuous pixel position."""
        s, o = float(as_fraction(scale)), float(origin_fraction(origin))
        return (u - self.wr - o) * s, (v - self.hr - o) * s

    def lonlat_to_tile(self, lon, lat, scale, origin="floor"):
        """(x, y) continuous and the tile index (floor) holding that point."""
        x, y = self.uv_to_tile(*self.lonlat_to_uv(lon, lat), scale, origin)
        return (x, y), (int(math.floor(x)), int(math.floor(y)))

    def pixel_centre_tile_cols(self, cols, scale, origin="floor"):
        return pixel_centre_tiles(cols, self.wr, scale, origin)

    def pixel_centre_tile_rows(self, rows, scale, origin="floor"):
        return pixel_centre_tiles(rows, self.hr, scale, origin)

    def tile_to_pixel(self, tx, ty, scale, origin="floor"):
        """Pixel whose area holds the centre of tile (tx, ty)."""
        s, o = as_fraction(scale), origin_fraction(origin)
        u = (Fraction(tx) + Fraction(1, 2)) / s + self.wr + o
        v = (Fraction(ty) + Fraction(1, 2)) / s + self.hr + o
        return int(math.floor(u)), int(math.floor(v))

    def world_size_tiles(self, scale):
        s = as_fraction(scale)
        return int(math.floor(self.W * s)), int(math.floor(self.H * s))


def pixel_centre_tiles(idx, radius, scale, origin="floor"):
    """Tile index holding the centre of each pixel index (exact integer arithmetic).

    x = (i + 1/2 - radius - origin) * s with s = p / q and origin = k / 2, so
    tile = floor(((2 i + 1 - 2 radius - 2 origin) * p) / (2 q)).
    """
    s, o = as_fraction(scale), origin_fraction(origin)
    p, q = s.numerator, s.denominator
    two_o = o * 2
    if two_o.denominator != 1:
        raise ValueError("origin must be a multiple of 1/2")
    i = np.asarray(idx, dtype=np.int64)
    num = (2 * i + 1 - 2 * int(radius) - int(two_o)) * p
    return np.floor_divide(num, 2 * q)


def peak_memory_mb():
    """Peak working set of this process in MB (Windows), or None elsewhere."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return None
        return round(pmc.PeakWorkingSetSize / 2 ** 20, 1)
    except Exception:
        return None
