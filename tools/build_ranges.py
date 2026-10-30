#!/usr/bin/env python3
"""The ranges table's writer and its crest geometry (milestone ridges; ARCHITECTURE.md, milestone contract 8).

  python tools/build_ranges.py emit     write terra-nauvis/prototypes/tables/ranges.lua
  python tools/build_ranges.py check    emit in memory and compare with the committed table
  python tools/build_ranges.py list     ranges, openings and pass-free stretches per map

Rows (APPROVALS 5 and 06:45), from data-src/approvals/approvals-data.json (which
ranges and passes are adopted, each pass's arc along its crest, the pass-free stretches and the
unnamed-gap rule), the design notes (the crest polylines it measured) and
data-src/ridges/vertex-heights.json (each crest vertex's height):
  crest   every range approvals-data.json lists (16), as R7b's crest polyline in degrees
  heights one per crest vertex, in metres: a ridge runs wider where its mountain is taller
  pass    every adopted pass (54 of 56: Khyber and Bolan stand on no listed range and are dropped),
          at the crest point approvals-data.json's arc_km names: the point serving it, which
          build_approvals.py placed (the nearest crest point, the crest's end for Derbent, the crest
          point nearest the middle of the route for Babinov)
  gap     the unnamed pass-width gaps of the rule "a pass-free stretch of L km gets ceil(L / 400) - 1"
          (approvals-data.json rules.unnamed_gap_rule and unnamed_gaps_per_stretch), computed here and
          never placed by hand: gap k of a stretch lies in the window that keeps every piece of the
          stretch at most 400 km, at its lowest-curvature crest point, the middle of the longest
          straight piece of crest inside the window (curvature on a polyline sits at its vertices)
  edge    per map, a range cut by the map's edge with no adopted pass on that map (APPROVALS 5 and
          the notes of approvals-data.json: Europe's Caucasus and Atlas): an opening where the crest
          meets the edge, so the ridge stops short of the edge and its two sides still meet
Each range also lists, per map that holds any of its vertices, the crest segments the map's ridge
reads: those whose box comes within MARGIN_PX of the map's extent, the furthest a ridge reaches at
scale 1. Distances along a crest are ground km, great circle per segment and linear inside one, as
build_approvals.py measures them, so the arcs and stretches here equal approvals-data.json's.

An approval edit is an edit of approvals-data.json and a rerun of `emit`; the static gate row re-emits
the table and fails on any difference, so the table never drifts from its sources.
`prototypes/expressions/ridges.lua` turns the rows into each map's crest distance and openings.

No numpy at import: `earth_test.py static` imports this module, and CI runs it without numpy.
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
TABLE = MOD / "prototypes" / "tables" / "ranges.lua"
APPROVALS = REPO / "data-src" / "approvals" / "approvals-data.json"
R7B = REPO / "docs" / "plan" / "research" / "R7b-geography.json"
HEIGHTS = REPO / "data-src" / "ridges" / "vertex-heights.json"
TOOL_VERSION = 2

EARTH_R_KM = 6371.0088          # build_approvals.py's sphere, so arcs equal approvals-data.json's
DEG_KM = math.pi * EARTH_R_KM / 180.0
ARC_TOLERANCE_KM = 0.2          # approvals-data.json rounds arcs and stretches to 0.1 km
# A ridge reaches its widest half-width plus its swell and its wander from the crest (config.lua
# ridges), that many reference pixels at scale 1: a segment whose box comes within this of a map's
# extent can put cliffs on it.
MARGIN_PX = 200.0
MAX_COLUMNS = 120               # tools/lint/luacheckrc.lua max_line_length
KINDS = ("pass", "gap", "edge")
TIP_KM = 0.5                    # an opening this close to a crest's end vertex sits at that end


class RangeError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ geometry

def gc_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


def seg_lengths(pts):
    return [gc_km(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]


def arcs_of(pts):
    acc = [0.0]
    for s in seg_lengths(pts):
        acc.append(acc[-1] + s)
    return acc


def point_at_arc(pts, arc):
    """(lat, lon, segment index from 1) at arc km from the first vertex, linear inside a segment as
    build_approvals.py's point_at_arc counts; an arc at a vertex belongs to the segment it starts,
    the crest's end to the last segment."""
    acc = 0.0
    lens = seg_lengths(pts)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        seg = lens[i]
        if seg > 0 and (acc + seg > arc or i == len(lens) - 1):
            t = min(max((arc - acc) / seg, 0.0), 1.0)
            return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), i + 1
        acc += seg
    raise RangeError("a crest with no length")


def edge_uv(m, lat, lon, ppd):
    """A map's continuous raster coordinates (pixel col spans [col, col + 1); earthgeo's convention)."""
    return (lon - float(m["lon_left_edge"])) * ppd, (float(m["lat_top_edge"]) - lat) * ppd


def inside(m, lat, lon, ppd, margin=0.0):
    u, v = edge_uv(m, lat, lon, ppd)
    return -margin <= u < int(m["width_px"]) + margin and -margin <= v < int(m["height_px"]) + margin


def seg_near(m, a, b, ppd, margin):
    """The segment's box comes within margin px of the map's extent."""
    ua, va = edge_uv(m, a[0], a[1], ppd)
    ub, vb = edge_uv(m, b[0], b[1], ppd)
    W, H = int(m["width_px"]), int(m["height_px"])
    return max(ua, ub) >= -margin and min(ua, ub) < W + margin and max(va, vb) >= -margin and \
        min(va, vb) < H + margin


def edge_crossings(m, pts, ppd):
    """[(lat, lon, segment index from 1)] where the crest crosses the map's extent boundary."""
    W, H = int(m["width_px"]), int(m["height_px"])
    out = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        ia, ib = inside(m, a[0], a[1], ppd), inside(m, b[0], b[1], ppd)
        if ia == ib:
            continue
        ua, va = edge_uv(m, a[0], a[1], ppd)
        ub, vb = edge_uv(m, b[0], b[1], ppd)
        # the parameter where the segment leaves (or enters) the box [0, W] x [0, H]
        ts = []
        for p0, p1, lim in ((ua, ub, 0.0), (ua, ub, float(W)), (va, vb, 0.0), (va, vb, float(H))):
            if p1 != p0:
                t = (lim - p0) / (p1 - p0)
                if 0.0 <= t <= 1.0:
                    u, v = ua + t * (ub - ua), va + t * (vb - va)
                    if -1e-9 <= u <= W + 1e-9 and -1e-9 <= v <= H + 1e-9:
                        ts.append(t)
        if not ts:
            raise RangeError(f"segment {i + 1} changes sides of {m['key']}'s extent without crossing it")
        t = min(ts) if ia else max(ts)
        out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), i + 1))
    return out


def turn_free_pieces(acc, lo, hi):
    """The straight pieces of crest inside [lo, hi] km: (start, end) per segment it meets."""
    out = []
    for i in range(len(acc) - 1):
        a, b = max(acc[i], lo), min(acc[i + 1], hi)
        if b > a:
            out.append((a, b))
    return out


def lowest_curvature(acc, lo, hi):
    """The window's lowest-curvature crest point: the middle of its longest straight piece (the earliest
    on a tie), so the gap sits as far from a bend as the window allows."""
    pieces = turn_free_pieces(acc, lo, hi)
    if not pieces:
        return (lo + hi) / 2
    a, b = max(pieces, key=lambda p: (round(p[1] - p[0], 9), -p[0]))
    return (a + b) / 2


def place_gaps(acc, a, b, n, every):
    """n gap arcs inside the stretch [a, b] so no piece exceeds `every` km: gap k at the lowest-curvature
    point of the window [max(previous, b - every * (n - k + 1)), previous + every]."""
    out, prev = [], a
    for k in range(n, 0, -1):
        lo, hi = max(prev, b - every * k), min(prev + every, b)
        if lo > hi + 1e-9:
            raise RangeError(f"no window for a gap in the stretch {a:.1f} to {b:.1f} km")
        g = lowest_curvature(acc, lo, hi)
        out.append(g)
        prev = g
    return out


# ------------------------------------------------------------------------------------------------ derive

def heights_of(rid, g, doc):
    """A range's vertex heights in metres (data-src/ridges/vertex-heights.json): one per crest vertex,
    none above R7b's highest point for the range."""
    hs = (doc.get("ranges") or {}).get(rid)
    want = len(g["crest_polyline"])
    if not isinstance(hs, list) or len(hs) != want:
        raise RangeError(f"{rid}: vertex-heights.json holds {len(hs) if isinstance(hs, list) else 'no'} heights "
                         f"for {want} crest vertices")
    top = float(g["highest_elevation_m"])
    if max(hs) > top + 1:
        raise RangeError(f"{rid}: a vertex height of {max(hs)} m tops R7b's highest point, {top} m")
    return [float(h) for h in hs]


def derive(cfg, appr, r7b):
    """The table's ranges from the approval data, R7b and the vertex heights, in approvals-data.json's
    order, with the per-map facts list() reports."""
    ppd = float(cfg["coordinates"]["px_per_degree"])
    every = float(appr["rules"]["unnamed_gap_every_km"])
    heights = json.loads(HEIGHTS.read_text(encoding="utf-8"))
    maps = [cfg["maps"][k] for k in cfg["map_order"]]
    geo = {r["id"]: r for r in r7b["ranges"]}
    passes = {}
    for p in appr["passes"]:
        passes.setdefault(p["range"], []).append(p)
    out = []
    for ar in appr["ranges"]:
        rid = ar["id"]
        g = geo.get(rid)
        if g is None:
            raise RangeError(f"approvals-data.json range {rid} is not in R7b-geography.json")
        pts = [(float(v["lat"]), float(v["lon"])) for v in g["crest_polyline"]]
        if len(pts) != int(ar["vertices"]):
            raise RangeError(f"{rid}: R7b holds {len(pts)} crest vertices, approvals-data.json {ar['vertices']}")
        acc = arcs_of(pts)
        length = acc[-1]
        if abs(length - float(ar["crest_km"])) > 0.5:
            raise RangeError(f"{rid}: crest {length:.1f} km, approvals-data.json {ar['crest_km']}")
        on_maps = [m["key"] for m in maps if any(inside(m, la, lo, ppd) for la, lo in pts)]
        for m in maps:
            n_in = sum(1 for la, lo in pts if inside(m, la, lo, ppd))
            if n_in != int(ar["vertices_inside"][m["key"]]):
                raise RangeError(f"{rid}: {n_in} vertices inside {m['key']}, approvals-data.json "
                                 f"{ar['vertices_inside'][m['key']]}")
        adopted = sorted((p for p in passes.get(rid, []) if p["adopted"]), key=lambda p: float(p["arc_km"]))
        openings = []
        for p in adopted:
            la, lo, seg = point_at_arc(pts, float(p["arc_km"]))
            openings.append({"kind": "pass", "id": p["id"], "arc_km": float(p["arc_km"]), "lat": la, "lon": lo,
                             "seg": seg, "cited_maps": [k for k in cfg["map_order"] if p["maps"].get(k)]})
        stops = [0.0] + [o["arc_km"] for o in openings] + [length]
        stretches = [b - a for a, b in zip(stops, stops[1:])]
        want = [float(s) for s in ar["pass_free_stretches_km"]]
        if len(want) != len(stretches) or any(abs(x - y) > ARC_TOLERANCE_KM for x, y in zip(stretches, want)):
            raise RangeError(f"{rid}: pass-free stretches {[round(s, 1) for s in stretches]}, approvals-data.json {want}")
        counts = [max(0, math.ceil(s / every - 1e-9) - 1) for s in stretches]
        if counts != [int(c) for c in ar["unnamed_gaps_per_stretch"]]:
            raise RangeError(f"{rid}: the rule gives {counts} unnamed gaps per stretch, approvals-data.json "
                             f"{ar['unnamed_gaps_per_stretch']}")
        k = 0
        for a, b, n in zip(stops, stops[1:], counts):
            for arc in place_gaps(acc, a, b, n, every):
                k += 1
                la, lo, seg = point_at_arc(pts, arc)
                openings.append({"kind": "gap", "id": f"{rid}_gap_{k}", "arc_km": arc, "lat": la, "lon": lo,
                                 "seg": seg})
        if k != int(ar["unnamed_gaps"]):
            raise RangeError(f"{rid}: {k} unnamed gaps, approvals-data.json {ar['unnamed_gaps']}")
        openings.sort(key=lambda o: (o["arc_km"], o["kind"]))
        segments = {}
        for m in maps:
            if m["key"] not in on_maps:
                continue
            segments[m["key"]] = [i + 1 for i, (a, b) in enumerate(zip(pts, pts[1:]))
                                  if seg_near(m, a, b, ppd, MARGIN_PX)]
        for o in openings:
            o["maps"] = [k for k in on_maps if inside(cfg["maps"][k], o["lat"], o["lon"], ppd, MARGIN_PX)]
        # a range cut by a map's edge with no adopted pass cited on that map stops short of the edge
        for m in maps:
            if m["key"] not in on_maps or all(inside(m, la, lo, ppd) for la, lo in pts):
                continue
            if any(m["key"] in o.get("cited_maps", []) for o in openings if o["kind"] == "pass"):
                continue
            for j, (la, lo, seg) in enumerate(edge_crossings(m, pts, ppd), 1):
                arc = acc[seg - 1] + gc_km(pts[seg - 1][0], pts[seg - 1][1], la, lo)
                openings.append({"kind": "edge", "id": f"{rid}_edge_{m['key']}_{j}", "arc_km": arc, "lat": la,
                                 "lon": lo, "seg": seg, "maps": [m["key"]]})
        openings.sort(key=lambda o: (o["arc_km"], KINDS.index(o["kind"]), o["id"]))
        for o in openings:
            o.pop("cited_maps", None)
            # an opening at a crest's end vertex (Cadibona, Semmering, the Iron Gates, Derbent, Postojna,
            # Wakhjir) also clears the ridge's end cap past that vertex: tip -1 at the first vertex, 1
            # at the last
            if o["kind"] != "edge" and o["arc_km"] <= TIP_KM:
                o["tip"] = -1
            elif o["kind"] != "edge" and o["arc_km"] >= length - TIP_KM:
                o["tip"] = 1
            elif o["kind"] != "edge":
                # an opening at an interior crest vertex (R7b drew most crests through their passes) sits
                # on the vertex and opens across the bisector of the two segments meeting there, so the
                # inner flank of the bend is cut as wide as the outer one
                for i in range(1, len(acc) - 1):
                    if abs(o["arc_km"] - acc[i]) <= TIP_KM:
                        o["vertex"] = i + 1
                        o["lat"], o["lon"] = pts[i]
                        o["seg"] = i + 1
                        break
        out.append({"id": rid, "name": g["name"], "crest_km": length, "crest": [list(p) for p in pts],
                    "heights": heights_of(rid, g, heights), "segments": segments, "openings": openings})
    return out


def map_stretches(cfg, rng, map_key):
    """The pass-free stretches (km) of a range's crest on one map: the crest inside the map's extent,
    cut at every opening the map holds, at the range's ends and where the crest leaves the map."""
    ppd = float(cfg["coordinates"]["px_per_degree"])
    m = cfg["maps"][map_key]
    pts = [tuple(p) for p in rng["crest"]]
    acc = arcs_of(pts)
    # the inside intervals of the crest, in arc km
    marks = [0.0] + [acc[c[2] - 1] + gc_km(pts[c[2] - 1][0], pts[c[2] - 1][1], c[0], c[1])
                     for c in edge_crossings(m, pts, ppd)] + [acc[-1]]
    inner = []
    for a, b in zip(marks, marks[1:]):
        la, lo, _ = point_at_arc(pts, (a + b) / 2)
        if inside(m, la, lo, ppd):
            inner.append((a, b))
    cuts = sorted(o["arc_km"] for o in rng["openings"] if map_key in o["maps"])
    out = []
    for a, b in inner:
        stops = [a] + [c for c in cuts if a < c < b] + [b]
        out += [y - x for x, y in zip(stops, stops[1:])]
    return out


# ------------------------------------------------------------------------------------------------ emit

def lua_num(v):
    if isinstance(v, bool):
        raise RangeError("a boolean where a number belongs")
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) < 2 ** 53):
        return str(int(v))
    return repr(round(float(v), 7))


def lua_str(s):
    if not isinstance(s, str) or any(ord(ch) > 126 or ch in "\"\\\n" for ch in s):
        raise RangeError(f"{s!r}: table strings are printable ASCII without quotes or backslashes")
    return '"' + s + '"'


def ascii_name(s):
    """R7b's display names, folded to the table's printable ASCII (the locale never reads them)."""
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if ord(ch) < 127)


def wrap_items(items, indent, width=MAX_COLUMNS):
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


def emit_range(cfg, r):
    ind, inner = "    ", "      "
    out = [ind + "{"]
    out += wrap_items([f"id = {lua_str(r['id'])}", f"name = {lua_str(ascii_name(r['name']))}",
                       f"crest_km = {lua_num(round(r['crest_km'], 1))}"], inner)
    out.append(inner + "crest = {")
    out += wrap_items(["{" + lua_num(a) + ", " + lua_num(b) + "}" for a, b in r["crest"]], inner + "  ")
    out.append(inner + "},")
    out.append(inner + "heights = {")
    out += wrap_items([lua_num(h) for h in r["heights"]], inner + "  ")
    out.append(inner + "},")
    out.append(inner + "segments = {")
    for k in cfg["map_order"]:
        if k in r["segments"]:
            out += wrap_items([f"{k} = {{" + ", ".join(str(i) for i in r["segments"][k]) + "}"], inner + "  ")
    out.append(inner + "},")
    out.append(inner + "openings = {")
    for o in r["openings"]:
        fields = [f"kind = {lua_str(o['kind'])}", f"id = {lua_str(o['id'])}", f"seg = {o['seg']}",
                  f"arc_km = {lua_num(round(o['arc_km'], 1))}", f"lat = {lua_num(o['lat'])}",
                  f"lon = {lua_num(o['lon'])}"] + ([f"tip = {o['tip']}"] if o.get("tip") else []) +             ([f"vertex = {o['vertex']}"] if o.get("vertex") else []) +             ["maps = {" + ", ".join(lua_str(m) for m in o["maps"]) + "}"]
        lines = wrap_items(fields, inner + "   ", MAX_COLUMNS - 1)
        lines[0] = inner + "  {" + lines[0].strip()
        lines[-1] = lines[-1][:-1] + "},"
        out += lines
    out.append(inner + "},")
    out.append(ind + "},")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise RangeError(f"range {r['id']}: a line of {len(line)} columns")
    return out


HEADER = """\
-- Ridge ranges (ARCHITECTURE.md, slice contract 8; APPROVALS 5; DECISIONS 05:55 and 06:45; slice ridges).
-- Written by tools/build_ranges.py (writer {tool}) from
--   data-src/approvals/approvals-data.json sha256 {appr}
--   docs/plan/research/R7b-geography.json sha256 {r7b}
--   data-src/ridges/vertex-heights.json sha256 {heights}
-- Never edit by hand: an approval edit is an edit of approvals-data.json, then
-- `python tools/build_ranges.py emit`; the static gate row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through
-- tools/tnconfig.py's loader. prototypes/expressions/ridges.lua turns each map's ranges into the map's
-- crest distance and openings. Fields: id; name (R7b's, ASCII); crest_km (ground km along the crest);
-- crest (R7b's crest polyline, lat and lon per vertex); heights (metres, one per crest vertex: the
-- ridge's width follows them); segments (per map that holds any vertex, the crest segments its ridge
-- reads, from 1); openings: kind (pass: an adopted pass at the crest point that
-- serves it; gap: an unnamed pass-width gap at the lowest-curvature crest point, at least one every
-- {every} km of crest; edge: where a range cut by the map's edge with no pass on that map meets the
-- edge), id, lat and lon (on the crest), seg (the crest segment it lies on), arc_km (from the first
-- vertex), tip (-1 or 1 at the crest's first or last vertex: the opening also clears the end cap),
-- vertex (an interior crest vertex the opening sits on: it opens across the bend's bisector) and maps
-- (the maps that open it). Degrees throughout.
"""


def emit_text(cfg, ranges, appr, appr_sha, r7b_sha):
    every = float(appr["rules"]["unnamed_gap_every_km"])
    out = HEADER.format(tool=TOOL_VERSION, appr=appr_sha, r7b=r7b_sha, heights=sha256(HEIGHTS),
                        every=lua_num(every)).splitlines()
    out += ["return {", "  ranges = {"]
    for r in ranges:
        out += emit_range(cfg, r)
    out += ["  },", "}"]
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise RangeError(f"a header line of {len(line)} columns")
    return "\n".join(out) + "\n"


def sha256(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sources(appr_path=APPROVALS, r7b_path=R7B):
    return (json.loads(Path(appr_path).read_text(encoding="utf-8")),
            json.loads(Path(r7b_path).read_text(encoding="utf-8")))


def build(cfg=None, appr_path=APPROVALS, r7b_path=R7B):
    cfg = cfg or tnconfig.load()
    appr, r7b = sources(appr_path, r7b_path)
    ranges = derive(cfg, appr, r7b)
    return ranges, emit_text(cfg, ranges, appr, sha256(appr_path), sha256(r7b_path))


# ------------------------------------------------------------------------------------------------ load

def load_table(path=TABLE):
    """The table's ranges as Python data (tnconfig's pure-data loader), validated."""
    data = tnconfig.load(path)
    ranges = data.get("ranges")
    if not isinstance(ranges, list) or not ranges:
        raise RangeError(f"{path}: no ranges list")
    for r in ranges:
        problems = range_problems(r)
        if problems:
            raise RangeError(f"{path}: range {r.get('id')!r}: {problems[0]}")
    return ranges


def range_problems(r):
    out = []
    if not isinstance(r, dict):
        return ["a range is not a keyed table"]
    crest = r.get("crest")
    if not isinstance(crest, list) or len(crest) < 2 or not all(isinstance(p, list) and len(p) == 2 for p in crest):
        out.append("crest needs at least 2 {lat, lon} vertices")
        return out
    hs = r.get("heights")
    if not isinstance(hs, list) or len(hs) != len(crest) or not all(isinstance(h, (int, float)) for h in hs):
        out.append("heights needs one number per crest vertex")
    segs = r.get("segments")
    if not isinstance(segs, dict) and segs != []:
        out.append("segments is not keyed by map")
    else:
        for k, v in (segs or {}).items():
            if not isinstance(v, list) or not all(isinstance(i, int) and 1 <= i < len(crest) for i in v):
                out.append(f"segments.{k} names a segment the crest lacks")
    for o in r.get("openings") or []:
        if not isinstance(o, dict) or o.get("kind") not in KINDS:
            out.append(f"an opening of kind {o.get('kind') if isinstance(o, dict) else o!r}")
            continue
        if not (isinstance(o.get("seg"), int) and 1 <= o["seg"] < len(crest)):
            out.append(f"opening {o.get('id')}: seg {o.get('seg')!r} is not a crest segment")
        if not all(isinstance(o.get(k), (int, float)) for k in ("lat", "lon", "arc_km")):
            out.append(f"opening {o.get('id')}: lat, lon and arc_km are numbers")
        if not isinstance(o.get("maps"), list):
            out.append(f"opening {o.get('id')}: maps is a list")
        if o.get("tip") not in (None, -1, 1):
            out.append(f"opening {o.get('id')}: tip is -1 or 1")
        if o.get("vertex") is not None and not (isinstance(o["vertex"], int) and 1 < o["vertex"] < len(crest)):
            out.append(f"opening {o.get('id')}: vertex is an interior crest vertex")
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
        return [f"{Path(path).name} differs from a fresh emission at line {i + 1}: rerun python tools/build_ranges.py "
                f"emit (committed {a[i] if i < len(a) else '<end>'!r}, emitted {b[i] if i < len(b) else '<end>'!r})"]
    return []


def table_findings(cfg=None, path=TABLE, appr_path=APPROVALS):
    """T16 (FG): the committed table re-emits byte for byte from its sources, and its rows are the
    approval data's: every range approvals-data.json lists, exactly its adopted passes (so Khyber and
    Bolan, which it drops, are absent), exactly the rule's count of unnamed gaps per pass-free stretch,
    and no pass-free stretch over the rule's km on the whole crest or on any map."""
    cfg = cfg or tnconfig.load()
    out = check_table(path, cfg)
    try:
        ranges = load_table(path)
    except (RangeError, tnconfig.ConfigError) as e:
        return out + [str(e)]
    appr = json.loads(Path(appr_path).read_text(encoding="utf-8"))
    every = float(appr["rules"]["unnamed_gap_every_km"])
    have = {r["id"]: r for r in ranges}
    want_ids = [r["id"] for r in appr["ranges"]]
    if [r["id"] for r in ranges] != want_ids:
        out.append(f"ranges {[r['id'] for r in ranges]}, approvals-data.json lists {want_ids}")
    adopted = {p["id"] for p in appr["passes"] if p["adopted"]}
    dropped = {p["id"] for p in appr["passes"] if not p["adopted"]}
    got = {o["id"] for r in ranges for o in r.get("openings") or [] if o["kind"] == "pass"}
    if got != adopted:
        out.append(f"passes differ from the adopted ones: missing {sorted(adopted - got)}, extra {sorted(got - adopted)}")
    if got & dropped:
        out.append(f"dropped passes in the table: {sorted(got & dropped)}")
    for ar in appr["ranges"]:
        r = have.get(ar["id"])
        if r is None:
            continue
        gaps = [o for o in r.get("openings") or [] if o["kind"] == "gap"]
        if len(gaps) != int(ar["unnamed_gaps"]):
            out.append(f"{ar['id']}: {len(gaps)} unnamed gaps, the rule gives {ar['unnamed_gaps']}")
        cuts = sorted(o["arc_km"] for o in r.get("openings") or [] if o["kind"] in ("pass", "gap"))
        stops = [0.0] + cuts + [float(r["crest_km"])]
        longest = max(b - a for a, b in zip(stops, stops[1:]))
        if longest > every + ARC_TOLERANCE_KM:
            out.append(f"{ar['id']}: a pass-free stretch of {longest:.1f} km, over {every:g}")
        for mk in (r.get("segments") or {}):
            st = map_stretches(cfg, r, mk)
            if st and max(st) > every + ARC_TOLERANCE_KM:
                out.append(f"{ar['id']} on {mk}: a pass-free stretch of {max(st):.1f} km, over {every:g}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit")
    sub.add_parser("check")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            ranges, text = build()
            TABLE.parent.mkdir(parents=True, exist_ok=True)
            TABLE.write_text(text, encoding="utf-8", newline="\n")
            print(f"RESULT ok emitted {len(ranges)} ranges to {TABLE.relative_to(REPO).as_posix()} sha256 {sha256(TABLE)}")
            return 0
        if a.cmd == "check":
            f = table_findings()
            print(f"RESULT {'ok' if not f else 'fail'} table check{': ' + f[0] if f else ''}")
            return 0 if not f else 1
        cfg = tnconfig.load()
        ranges = load_table()
        for r in ranges:
            kinds = {k: sum(1 for o in r["openings"] if o["kind"] == k) for k in KINDS}
            print(f"{r['id']}: {r['crest_km']} km, {len(r['crest']) - 1} segments, openings {kinds}")
            for mk, segs in r["segments"].items():
                st = map_stretches(cfg, r, mk)
                n = sum(1 for o in r["openings"] if mk in o["maps"])
                print(f"   {mk}: {len(segs)} segments, {n} openings, longest pass-free "
                      f"{max(st) if st else 0:.1f} km")
        print(f"RESULT ok {len(ranges)} ranges")
        return 0
    except (RangeError, tnconfig.ConfigError, OSError, KeyError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
