#!/usr/bin/env python3
"""The region layer's table writer and its geometry (milestone region-layer; ARCHITECTURE.md, "Region layer").

  python tools/build_regions.py emit     write terra-nauvis/prototypes/tables/regions.lua
  python tools/build_regions.py check    emit in memory and compare with the committed table
  python tools/build_regions.py list     the rows per map and layer

Rows (S10 design (d)): exact discs, polygons and buffered paths in degrees, written
from data-src/approvals/approvals-data.json (what each map adopts, hotspot centres, radii and jitter;
APPROVALS 2, 4, 8 and 10) and the design notes (outlines, extents and the
protected features beside the destroyed zone), by the rules of S10's tuned table
(spikes/S10-regions/tables.py in an earlier prototype):
  destroyed   the outline in data-src/approvals/destroyed-zone.json on
              every map whose extent holds it: a polygon whose vertices each move per seed by up to their
              own jitter, at the file's warp share (above 1: stronger than the shared warp), plus the
              file's keep rows (warp 0), buffered paths that hold Britain, Denmark and the Carpathian
              crest outside at every seed
  forest      every adopted forest: R7b's outline as a polygon, else a disc of its equivalent radius;
              share 0.25 for discs, 0.4 for thin outlines, 1 for the rest; boost 1
  marsh       every adopted marsh by APPROVALS 8's extent: a box, a buffered coast line or a disc of
              its equivalent radius; warp share 0 (deltas and coasts stay put; roughness only)
  hotspot     every adopted hotspot as a disc of its radius r at its adopted centre, jittered per
              seed by up to j = r / 2 in the data stage (S6's linear fold, a phase per row), warp 0,
              biter multiplier 4 (APPROVALS 1b)
An approval edit is an edit of approvals-data.json and a rerun of `emit`; the gate's static row
re-emits the table and fails on any difference, so the table never drifts from its sources.

Geometry: every row is evaluated in the region frame, the frame map's reference pixels (config.lua
`regions.frame`) with pixel centres at integer (u, v), the coordinate chain's frame (ARCHITECTURE.md,
"The coordinate chain"). Every map's raster sits on that 45 px per degree grid (Europe is an exact
crop of Atlantic's raster; Old World's edges are whole pixels away), so a map's own (u, v) moves into
the frame by a whole-pixel offset and a row is the same region on every map and at every scale.
`prototypes/expressions/regions.lua` evaluates the same formulas in the game.

No numpy at import: `earth_test.py static` imports this module, and CI runs it without numpy.
"""
import argparse
import json
import math
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
TABLE = MOD / tnconfig.REGION_TABLE
APPROVALS = REPO / "data-src" / "approvals" / "approvals-data.json"
ZONE = REPO / "data-src" / "approvals" / "destroyed-zone.json"
R7B = REPO / "docs" / "plan" / "research" / "R7b-geography.json"
TOOL_VERSION = 1

# S10's tuned table (spikes/S10-regions/tables.py, an earlier prototype; S10-regions.md 3)
SHARE_FOREST_DISC = 0.25
SHARE_THIN_POLYGON = 0.4    # S10 tuned the Carpathian and Dinaric outlines to 0.4
SHARE_POLYGON = 1.0
SHARE_EXCLUDE = 0.0
SHARE_MARSH = 0.0
SHARE_HOTSPOT = 0.0
# A polygon is thin when its area over its perimeter, about half its mean width for a strip, is below
# this: Carpathian 18.9 and Dinaric 17.2 px (S10's two thin outlines), Hyrcanian 10.6; the next is
# Upper Guinean at 33.3.
THIN_AREA_PER_PERIMETER_PX = 25.0
FOREST_BOOST = 1            # a row's relative great-forest strength (S10 open question 4: default 1)
ENEMY_MULT = 4              # APPROVALS 1b: enemy-base probability times 4 inside a hotspot's disc
MAX_SHARE = 3               # the destroyed zone's warp runs past the shared warp; every other row's is at most 1
LAYERS = ("destroyed", "forest", "marsh", "hotspot")
SHAPES = ("disc", "polygon", "path")
MAX_COLUMNS = 120           # tools/lint/luacheckrc.lua max_line_length


class RegionError(ValueError):
    pass


def cfg_regions(cfg):
    r = cfg.get("regions")
    if not isinstance(r, dict):
        raise RegionError("config.lua has no regions group")
    return r


# ------------------------------------------------------------------------------------------------ frame

def frame(cfg):
    """(lon_left_edge, lat_top_edge, px_per_degree) of the region frame: the frame map's raster."""
    key = cfg_regions(cfg)["frame"]
    m = cfg["maps"][key]
    return float(m["lon_left_edge"]), float(m["lat_top_edge"]), float(cfg["coordinates"]["px_per_degree"])


def to_px(lat, lon, fr):
    """Region-frame (u, v) of a point: pixel centres at integer u, v (the chain's frame)."""
    lon0, lat0, ppd = fr
    return (lon - lon0) * ppd - 0.5, (lat0 - lat) * ppd - 0.5


def to_latlon(u, v, fr):
    lon0, lat0, ppd = fr
    return lat0 - (v + 0.5) / ppd, lon0 + (u + 0.5) / ppd


def map_offset(cfg, map_key):
    """(du, dv): a map's own chain (u, v) plus this is the region frame's. Whole pixels, or RegionError
    when the map's raster is off the frame's grid by more than regions.frame_tolerance_px."""
    lon0, lat0, ppd = frame(cfg)
    m = cfg["maps"][map_key]
    tol = float(cfg_regions(cfg)["frame_tolerance_px"])
    du = (float(m["lon_left_edge"]) - lon0) * ppd
    dv = (lat0 - float(m["lat_top_edge"])) * ppd
    out = []
    for name, d in (("u", du), ("v", dv)):
        r = math.floor(d + 0.5)
        if abs(d - r) > tol:
            raise RegionError(f"{map_key}'s raster is {d:.4f} px from the region frame in {name}: not a whole pixel")
        out.append(int(r))
    return tuple(out)


def map_extent_px(cfg, map_key):
    """(u0, v0, u1, v1): the map's raster in the region frame, pixel centres inclusive."""
    du, dv = map_offset(cfg, map_key)
    m = cfg["maps"][map_key]
    return du, dv, du + int(m["width_px"]) - 1, dv + int(m["height_px"]) - 1


def in_map(cfg, map_key, u, v):
    u0, v0, u1, v1 = map_extent_px(cfg, map_key)
    return u0 - 0.5 <= u <= u1 + 0.5 and v0 - 0.5 <= v <= v1 + 0.5


# ------------------------------------------------------------------------------------------------ shapes

def km_per_px(cfg):
    return float(cfg_regions(cfg)["km_per_px"])


def shape_px(row, cfg):
    """A row's nominal shape in the region frame (no warp, no roughness, no jitter):
    {"kind": "disc", "cu", "cv", "r"} | {"kind": "polygon", "pts"} | {"kind": "path", "pts", "r"}."""
    fr, kpp = frame(cfg), km_per_px(cfg)
    if row["shape"] == "disc":
        cu, cv = to_px(row["lat"], row["lon"], fr)
        return {"kind": "disc", "cu": cu, "cv": cv, "r": row["radius_km"] / kpp}
    pts = [to_px(lat, lon, fr) for lat, lon in row["latlon"]]
    if row["shape"] == "path":
        return {"kind": "path", "pts": pts, "r": row["radius_km"] / kpp}
    return {"kind": "polygon", "pts": pts}


def _seg_d2(u, v, pts, closed):
    best = math.inf
    n = len(pts)
    for i in range(n if closed else n - 1):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        du, dv = u - ax, v - ay
        t = min(1.0, max(0.0, (du * ex + dv * ey) / (ex * ex + ey * ey)))
        qx, qy = du - t * ex, dv - t * ey
        best = min(best, qx * qx + qy * qy)
    return best


def _inside(u, v, pts):
    """The crossing-number test regions.lua emits: edges with ey != 0 that straddle the point's row
    and cross it to the right."""
    n, odd = len(pts), False
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        if ay == by:
            continue
        if ((v < ay) != (v < by)) and u < ax + (v - ay) * ((bx - ax) / (by - ay)):
            odd = not odd
    return odd


def sd_px(shape, u, v):
    """Signed distance in reference pixels, positive inside, of a nominal shape at (u, v)."""
    k = shape["kind"]
    if k == "disc":
        return shape["r"] - math.hypot(u - shape["cu"], v - shape["cv"])
    if k == "path":
        return shape["r"] - math.sqrt(_seg_d2(u, v, shape["pts"], False))
    d = math.sqrt(_seg_d2(u, v, shape["pts"], True))
    return d if _inside(u, v, shape["pts"]) else -d


def sd_grid(shape, U, V):
    """sd_px on numpy arrays (imported here, never at module load)."""
    import numpy as np
    U, V = np.asarray(U, float), np.asarray(V, float)
    k = shape["kind"]
    if k == "disc":
        return shape["r"] - np.hypot(U - shape["cu"], V - shape["cv"])
    pts = shape["pts"]
    n = len(pts)
    closed = k == "polygon"
    best = np.full(U.shape, np.inf)
    odd = np.zeros(U.shape, bool)
    for i in range(n if closed else n - 1):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        du, dv = U - ax, V - ay
        t = np.clip((du * ex + dv * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        qx, qy = du - t * ex, dv - t * ey
        best = np.minimum(best, qx * qx + qy * qy)
        if closed and ay != by:
            odd ^= ((V < ay) != (V < by)) & (U < ax + (V - ay) * ((bx - ax) / (by - ay)))
    if k == "path":
        return shape["r"] - np.sqrt(best)
    d = np.sqrt(best)
    return np.where(odd, d, -d)


def zone_sd(rows, cfg, u, v, grid=False):
    """The destroyed zone's nominal signed distance: min(max(include sds), -exclude sd, ...)."""
    if grid:
        import numpy as np
    inc = [shape_px(r, cfg) for r in rows if r["layer"] == "destroyed" and r.get("mode") != "exclude"]
    exc = [shape_px(r, cfg) for r in rows if r["layer"] == "destroyed" and r.get("mode") == "exclude"]
    f = sd_grid if grid else sd_px
    if not inc:
        return -math.inf
    parts = [f(s, u, v) for s in inc]
    out = parts[0]
    for p in parts[1:]:
        out = np.maximum(out, p) if grid else max(out, p)
    for s in exc:
        out = np.minimum(out, -f(s, u, v)) if grid else min(out, -f(s, u, v))
    return out


def polygon_area_perimeter(pts):
    a = per = 0.0
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
        per += math.hypot(x2 - x1, y2 - y1)
    return abs(a) / 2, per


def max_drift_px(row, cfg):
    """The most a row's edge can move from its nominal shape at any seed, in reference pixels: its
    share of the warp clamp, the roughness clamp and, for a hotspot or a seeded polygon, its jitter
    radius (a polygon's largest vertex jitter)."""
    R = cfg_regions(cfg)
    out = float(row["warp"]) * float(R["warp"]["clamp_px"]) + float(R["rough"]["clamp_px"])
    if row["layer"] == "hotspot":
        out += row["jitter_km"] / km_per_px(cfg)
    if row.get("vertex_jitter_km"):
        out += max(row["vertex_jitter_km"]) / km_per_px(cfg)
    return out


def rows_on(rows, map_key):
    return [r for r in rows if map_key in r["maps"]]


# ------------------------------------------------------------------------------------------------ derive

def slug(text):
    out, prev = [], "_"
    for ch in text.lower():
        c = ch if ("a" <= ch <= "z" or "0" <= ch <= "9") else "_"
        if c == "_" and prev == "_":
            continue
        out.append(c)
        prev = c
    return "".join(out).strip("_")


def phase_of(row_id):
    """A row's jitter phase in [0, 1): a fraction of the CRC-32 of its id, so adding or removing a
    row never moves another (D13 data-edit locality)."""
    return round(zlib.crc32(row_id.encode("ascii")) / 2 ** 32, 9)


def adopted_maps(cfg, adopted):
    return [k for k in cfg["map_order"] if (adopted or {}).get(k)]


def derive_rows(cfg, appr, r7b, zone):
    """The table's rows from the approval data, R7b and the zone's outline, in table order."""
    fr = frame(cfg)
    kpp = km_per_px(cfg)
    if abs(float(appr["rules"]["km_per_px"]) - kpp) > 1e-9:
        raise RegionError(f"config.lua regions.km_per_px {kpp} differs from approvals-data.json rules.km_per_px "
                          f"{appr['rules']['km_per_px']}")
    rows = []
    # The destroyed zone on every map whose extent holds its every vertex.
    verts = zone["vertices"]
    poly = [[float(p["lat"]), float(p["lon"])] for p in verts]
    pts = [to_px(lat, lon, fr) for lat, lon in poly]
    maps_d = [k for k in cfg["map_order"] if all(in_map(cfg, k, u, v) for u, v in pts)]
    rows.append({"id": "destroyed_europe", "layer": "destroyed", "mode": "include", "shape": "polygon",
                 "warp": float(zone["warp_share"]), "maps": maps_d, "latlon": poly,
                 "vertex_jitter_km": [float(p["jitter_km"]) for p in verts],
                 "vertex_phase": [phase_of("destroyed_europe_" + p["id"]) for p in verts],
                 "source": "destroyed-zone.json vertices (Jake's ruling of 2026-10-30 10:05)"})
    # Keep rows: what stays outside the zone at every seed.
    for k in zone["keep"]:
        rows.append({"id": k["id"], "layer": "destroyed", "mode": "exclude", "shape": "path", "warp": SHARE_EXCLUDE,
                     "maps": maps_d, "radius_km": float(k["radius_km"]),
                     "latlon": [[float(a), float(b)] for a, b in k["latlon"]],
                     "source": f"destroyed-zone.json keep {k['id']}"})
    # Forests (APPROVALS 4).
    r7f = {f["id"]: f for f in r7b["forests"]}
    for f in appr["forests"]:
        maps = adopted_maps(cfg, f.get("adopted"))
        if maps:
            rows.append(forest_row(cfg, f, r7f[f["id"]], maps))
    # Marshes (APPROVALS 8).
    r7m = {m["id"]: m for m in r7b["marshes"]}
    for m in appr["marshes"]:
        maps = adopted_maps(cfg, m.get("adopted"))
        if not maps:
            continue
        rows.append(marsh_row(cfg, m, r7m[m["id"]], maps))
    # Hotspots (APPROVALS 2), at the adopted centre (decision 16 moved one inland).
    for h in appr["hotspots"]:
        maps = adopted_maps(cfg, h.get("adopted"))
        if not maps:
            continue
        rid = slug(h["id"])
        rows.append({"id": rid, "layer": "hotspot", "shape": "disc", "warp": SHARE_HOTSPOT, "maps": maps,
                     "lat": float(h["lat"]), "lon": float(h["lon"]), "radius_km": float(h["radius_km"]),
                     "jitter_km": float(h["jitter_km"]), "mult": ENEMY_MULT, "resource": h["resource"],
                     "phase": phase_of(rid),
                     "source": f"approvals-data.json hotspots {h['id']} (APPROVALS 2; R7a)"})
    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise RegionError(f"duplicate row ids {dup}")
    return rows


def forest_row(cfg, f, g, maps):
    """One forest row: R7b's outline as a polygon, else a disc of the equivalent radius."""
    fr = frame(cfg)
    outline = (g.get("extent") or {}).get("polygon_latlon")
    rid = slug(f["id"])
    if outline:
        latlon = [[float(a), float(b)] for a, b in outline]
        area, per = polygon_area_perimeter([to_px(a, b, fr) for a, b in latlon])
        share = SHARE_THIN_POLYGON if area / per < THIN_AREA_PER_PERIMETER_PX else SHARE_POLYGON
        return {"id": rid, "layer": "forest", "shape": "polygon", "warp": share, "maps": maps, "boost": FOREST_BOOST,
                "latlon": latlon,
                "source": f"R7b-geography.json forests {f['id']} outline, {len(latlon)} vertices (APPROVALS 4)"}
    return {"id": rid, "layer": "forest", "shape": "disc", "warp": SHARE_FOREST_DISC, "maps": maps,
            "boost": FOREST_BOOST, "lat": float(f["lat"]), "lon": float(f["lon"]),
            "radius_km": float(f["equivalent_radius_km"]),
            "source": f"approvals-data.json forests {f['id']}, a disc of its equivalent radius (APPROVALS 4)"}


def marsh_row(cfg, m, g, maps):
    """One marsh row from APPROVALS 8's extent column: a box, a buffered coast line, else a disc."""
    ext = g.get("extent") or {}
    c = g["centroid"]
    rid = slug(m["id"])
    kpp = km_per_px(cfg)
    fr = frame(cfg)
    if "west_east_km" in ext and "north_south_km" in ext:
        # a box centred on the article coordinate, its sides converted at km_per_px (APPROVALS 2's
        # rule: a size in tiles does not depend on latitude)
        cu, cv = to_px(float(c["lat"]), float(c["lon"]), fr)
        hu, hv = ext["west_east_km"] / kpp / 2, ext["north_south_km"] / kpp / 2
        corners = [(cu - hu, cv - hv), (cu + hu, cv - hv), (cu + hu, cv + hv), (cu - hu, cv + hv)]
        latlon = [[round(a, 6), round(b, 6)] for a, b in (to_latlon(u, v, fr) for u, v in corners)]
        return {"id": rid, "layer": "marsh", "shape": "polygon", "warp": SHARE_MARSH, "maps": maps, "latlon": latlon,
                "source": f"R7b-geography.json marshes {m['id']} box {ext['west_east_km']} x {ext['north_south_km']} km "
                          f"(APPROVALS 8)"}
    if ext.get("coast_polyline"):
        latlon = [[float(a), float(b)] for a, b in ext["coast_polyline"]]
        pts = [to_px(a, b, fr) for a, b in latlon]
        length_km = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                        for i in range(len(pts) - 1)) * kpp
        # the band's half-width from its stated area along this line: area = length x 2 r
        half = round(float(ext["area_km2"]) / (2 * length_km), 3)
        return {"id": rid, "layer": "marsh", "shape": "path", "warp": SHARE_MARSH, "maps": maps, "radius_km": half,
                "latlon": latlon,
                "source": f"R7b-geography.json marshes {m['id']} coast_polyline, a band of {ext['area_km2']} km2 "
                          f"(APPROVALS 8)"}
    r = ext.get("equivalent_radius_km")
    if r is None:
        raise RegionError(f"marsh {m['id']} has no box, coast line or equivalent radius in R7b")
    return {"id": rid, "layer": "marsh", "shape": "disc", "warp": SHARE_MARSH, "maps": maps, "lat": float(c["lat"]),
            "lon": float(c["lon"]), "radius_km": float(r),
            "source": f"R7b-geography.json marshes {m['id']}, a disc of its equivalent radius (APPROVALS 8)"}


def spessart_row(cfg, appr, r7b):
    """S10's locality row: the alternate forest Spessart, adopted on Europe (only in a test copy)."""
    f = next(x for x in appr["forests"] if x["id"] == "spessart")
    g = next(x for x in r7b["forests"] if x["id"] == "spessart")
    return forest_row(cfg, f, g, [cfg["map_order"][0]])


# ------------------------------------------------------------------------------------------------ emit

def lua_num(v):
    if isinstance(v, bool):
        raise RegionError("a boolean where a number belongs")
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) < 2 ** 53):
        return str(int(v))
    return repr(float(v))


def lua_str(s):
    if not isinstance(s, str) or any(ord(ch) > 126 or ch in "\"\\\n" for ch in s):
        raise RegionError(f"{s!r}: table strings are printable ASCII without quotes or backslashes")
    return '"' + s + '"'


def wrap_items(items, indent, width=MAX_COLUMNS):
    """Lines of comma-terminated items, each line within width columns."""
    lines, cur = [], indent
    for it in items:
        piece = it + ","
        if cur.strip() and len(cur) + 1 + len(piece) > width:
            lines.append(cur.rstrip())
            cur = indent
        cur = cur + (" " if cur.strip() else "") + piece
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


FIELD_ORDER = ("id", "layer", "mode", "shape", "warp", "boost", "mult", "resource", "lat", "lon", "radius_km",
               "jitter_km", "phase")


def emit_row(r):
    ind = "    "
    inner = ind + "  "
    out = [ind + "{"]
    scalars = []
    for k in FIELD_ORDER:
        if k in r:
            v = r[k]
            scalars.append(f"{k} = {lua_str(v) if isinstance(v, str) else lua_num(v)}")
    out += wrap_items(scalars, inner)
    out += wrap_items(["maps = {" + ", ".join(lua_str(m) for m in r["maps"]) + "}"], inner)
    if "latlon" in r:
        out.append(inner + "latlon = {")
        out += wrap_items(["{" + lua_num(a) + ", " + lua_num(b) + "}" for a, b in r["latlon"]], inner + "  ")
        out.append(inner + "},")
    for k in ("vertex_jitter_km", "vertex_phase"):
        if k in r:
            out.append(inner + k + " = {")
            out += wrap_items([lua_num(v) for v in r[k]], inner + "  ")
            out.append(inner + "},")
    out.append(inner + "source = " + lua_str(r["source"]) + ",")
    out.append(ind + "},")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise RegionError(f"row {r['id']}: a line of {len(line)} columns")
    return out


HEADER = """\
-- Region layer rows (ARCHITECTURE.md, "Region layer"; S10 design (d), DECISIONS 07:45; slice region-layer).
-- Written by tools/build_regions.py (writer {tool}) from
--   data-src/approvals/approvals-data.json sha256 {appr}
--   docs/plan/research/R7b-geography.json sha256 {r7b}
--   data-src/approvals/destroyed-zone.json sha256 {zone}
-- Never edit by hand: an approval edit is an edit of approvals-data.json, then
-- `python tools/build_regions.py emit`; the static gate row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through
-- tools/tnconfig.py's loader. prototypes/expressions/regions.lua turns every row into its named
-- signed distance, weight and depth, and each layer's rows into the layer's aggregates.
-- Fields: id (the names' row part); layer (destroyed, forest, marsh, hotspot); mode (destroyed:
-- include, or exclude to keep a protected feature out of the zone); shape (disc: lat, lon,
-- radius_km; polygon: latlon vertices; path: latlon and radius_km, buffered); warp (the row's share
-- of the shared domain warp); maps (the maps that adopt it); boost (forest strength); mult, resource,
-- jitter_km and phase (hotspot: biter multiplier, resource, jitter radius and the phase of its fold);
-- vertex_jitter_km and vertex_phase (a seeded polygon: each vertex's jitter radius and fold phase).
-- Degrees throughout; sizes in km at regions.km_per_px (config.lua).
"""


def emit_text(rows, appr_sha, r7b_sha, zone_sha):
    out = HEADER.format(tool=TOOL_VERSION, appr=appr_sha, r7b=r7b_sha, zone=zone_sha).splitlines()
    out += ["return {", "  rows = {"]
    for r in rows:
        out += emit_row(r)
    out += ["  },", "}"]
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise RegionError(f"a header line of {len(line)} columns")
    return "\n".join(out) + "\n"


def sha256(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(cfg=None, appr_path=APPROVALS, r7b_path=R7B, zone_path=ZONE):
    cfg = cfg or tnconfig.load()
    appr = json.loads(Path(appr_path).read_text(encoding="utf-8"))
    r7b = json.loads(Path(r7b_path).read_text(encoding="utf-8"))
    zone = json.loads(Path(zone_path).read_text(encoding="utf-8"))
    rows = derive_rows(cfg, appr, r7b, zone)
    return rows, emit_text(rows, sha256(appr_path), sha256(r7b_path), sha256(zone_path))


# ------------------------------------------------------------------------------------------------ load

def load_table(path=TABLE):
    """The table's rows as Python data (tnconfig's pure-data loader), validated."""
    data = tnconfig.load(path)
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RegionError(f"{path}: no rows list")
    for r in rows:
        problems = row_problems(r)
        if problems:
            raise RegionError(f"{path}: row {r.get('id')!r}: {problems[0]}")
    return rows


def row_problems(r):
    out = []
    if not isinstance(r, dict):
        return ["a row is not a keyed table"]
    rid = r.get("id")
    if not isinstance(rid, str) or not rid or slug(rid) != rid:
        out.append(f"id {rid!r} is not lower-case letters, digits and single underscores")
    if r.get("layer") not in LAYERS:
        out.append(f"layer {r.get('layer')!r}")
    if r.get("shape") not in SHAPES:
        out.append(f"shape {r.get('shape')!r}")
    if not isinstance(r.get("warp"), (int, float)) or not 0 <= r["warp"] <= MAX_SHARE:
        out.append(f"warp {r.get('warp')!r} is not a share in [0, {MAX_SHARE}]")
    if not isinstance(r.get("maps"), list) or not r["maps"]:
        out.append("maps is not a list of map keys")
    if r.get("shape") in ("disc", "path") and not (isinstance(r.get("radius_km"), (int, float)) and r["radius_km"] > 0):
        out.append("a disc or path needs radius_km > 0")
    if r.get("shape") == "disc" and not all(isinstance(r.get(k), (int, float)) for k in ("lat", "lon")):
        out.append("a disc needs lat and lon")
    if r.get("shape") in ("polygon", "path"):
        ll = r.get("latlon")
        need = 3 if r["shape"] == "polygon" else 2
        if not isinstance(ll, list) or len(ll) < need or not all(isinstance(p, list) and len(p) == 2 for p in ll):
            out.append(f"a {r['shape']} needs latlon with at least {need} vertices")
    if r.get("layer") == "destroyed" and r.get("mode") not in ("include", "exclude"):
        out.append("a destroyed row needs mode include or exclude")
    if "vertex_jitter_km" in r or "vertex_phase" in r:
        n = len(r.get("latlon") or [])
        if r.get("shape") != "polygon" or len(r.get("vertex_jitter_km") or []) != n or \
                len(r.get("vertex_phase") or []) != n:
            out.append("a seeded polygon needs one vertex_jitter_km and one vertex_phase per vertex")
    if r.get("layer") == "hotspot":
        if r.get("shape") != "disc":
            out.append("a hotspot row is a disc")
        for k in ("jitter_km", "mult", "phase"):
            if not isinstance(r.get(k), (int, float)):
                out.append(f"a hotspot row needs {k}")
        if isinstance(r.get("phase"), (int, float)) and not 0 <= r["phase"] < 1:
            out.append("phase is not in [0, 1)")
    if r.get("layer") == "forest" and not isinstance(r.get("boost"), (int, float)):
        out.append("a forest row needs boost")
    return out


def check_table(path=TABLE, cfg=None):
    """Findings of the committed table against a fresh emission (empty when byte-identical)."""
    _, text = build(cfg)
    try:
        have = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    if have != text:
        a, b = have.splitlines(), text.splitlines()
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        return [f"{Path(path).name} differs from a fresh emission at line {i + 1}: rerun python tools/build_regions.py "
                f"emit (committed {a[i] if i < len(a) else '<end>'!r}, emitted {b[i] if i < len(b) else '<end>'!r})"]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit")
    sub.add_parser("check")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            rows, text = build()
            TABLE.parent.mkdir(parents=True, exist_ok=True)
            TABLE.write_text(text, encoding="utf-8", newline="\n")
            print(f"RESULT ok emitted {len(rows)} rows to {TABLE.relative_to(REPO).as_posix()} sha256 {sha256(TABLE)}")
            return 0
        if a.cmd == "check":
            f = check_table()
            print(f"RESULT {'ok' if not f else 'fail'} table check{': ' + f[0] if f else ''}")
            return 0 if not f else 1
        cfg = tnconfig.load()
        rows = load_table()
        for mk in cfg["map_order"]:
            on = rows_on(rows, mk)
            by = {ly: [r["id"] for r in on if r["layer"] == ly] for ly in LAYERS}
            print(f"{mk}: " + "; ".join(f"{ly} {len(v)}" for ly, v in by.items()))
        print(f"RESULT ok {len(rows)} rows")
        return 0
    except (RegionError, tnconfig.ConfigError, OSError, KeyError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
