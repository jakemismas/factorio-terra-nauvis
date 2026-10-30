#!/usr/bin/env python3
"""Waterway sets (ARCHITECTURE.md, "Build-time data flow" step 3; milestone waterways).

  python tools/build_waterways.py import [--map m]       data-src/waterways/<map>.json from S4's features and
                                                          the approvals (planning commit, through git show)
  python tools/build_waterways.py emit [--map m]          the generated Lua for scales 1 to 6, the map's river-safe
                                                          starts and the manifest data-src/waterways/manifest-<map>.json
  python tools/build_waterways.py check [--map m]         two emissions byte-identical to the committed files (T16)
  python tools/build_waterways.py rivers                  T16 (JI-03): each map's rivers equal APPROVALS 7's adopted
                                                          rows in approvals-data.json, in order, with their class
  python tools/build_waterways.py mask --map m --scale s --out p.png   the T1 corridor mask of one map and scale
  python tools/build_waterways.py offline [--map m] [--scale s]         geometric T5 pre-checks of the emitted sets

Method (S4, with the chosen widths and fords, design notes 12:35). Every feature's path is S4's least-cost
route through EarthMaps' drawn water, from the inland end to open sea at least 6 px from land, land
gaps bridged (data-src/waterways/<map>.json, cells of the map's own raster). Per scale s it is
resampled at one tile, box-smoothed (three passes) with the smallest of S4's windows for which the
Douglas-Peucker simplification at the scale's tolerance obeys R4's bend rule (no 17-tile stretch
turning more than 90 degrees), and where the largest window still fails, a 30 x 30 turning basin is
drawn at the sharpest vertex of each failing stretch; a basin T5's criterion names (REQUIRED_BASINS)
is drawn at the sharpest stretch where the bend rule places none. Vertices land on a 1/16-tile grid
in the map's geo tiles: X = s (u - 0.5 - wr) + floor(s / 2) for S4's pixel coordinate u (pixel
centres at col + 0.5), the coordinate chain's frame, so the tile holding a pixel centre reads the
carve where the coast fit reads that centre (U2).

A river's course is natural at three steps. Here
its out-and-back hooks are cut (deloop), it is smoothed by at least smoothing.min_window_px reference px,
which also loses most of the raster's octilinear stairs and of the segments, and each segment takes a
half-width from the river's profile, narrow at the source and wide at the coast (river_widths). In the
mod, waterways.lua warps the coordinates every set reads by one shared noise field and modulates the
width by one low-frequency noise, so the banks wander and stop being parallel for a few noise
evaluations per tile, not per segment. A turning basin is a short wide capsule on the river, not a square.

Each scale's file holds four name-free sets, which prototypes/expressions/waterways.lua binds to the
map's geo tiles through the locals X and Y (the rivers' warped tiles), XP and YP (the passages' lighter
warp, so a strait or canal keeps the places the oracle tests) and W (the width modulation):
  ww      rivers, straits and basins: per (half-width, depth, frame) class max(depth, slope (d - hw)),
          d the distance in tiles to the class's nearest segment, hw times W on a river, held at the
          river floor; min() over the classes (the elevation the carve allows; the entry takes min() with it)
  canals  the canals, the same form (min(), canals on)
  dams    slope (hw_dam - d) over the dam polylines (max(), canals off)
  fords   the ford rectangles: score where the tile is inside one and its elevation is below 0, else
          -inf (the water-shallow hook's on branch); they read the rivers' warped tiles, so each stays on
          its river
Segment distances come from one local function, seg, with its projection coefficients folded per
segment; ford rectangles from another, box. Coefficients print as float32 %.9g, every line stays
within 120 columns (build_geo.py's backslash-z wrapping), and the same inputs give byte-identical
files. A ford's banks are land in the reference and the coast fit; it sits on a straight reach whose
banks clear the coast detail (land at every seed) where its interval has one, else on the least
bending such reach with its rectangle widened by the bend, else where its banks come nearest to
clearing the detail (marked bank_margin_px).

The river-safe starts live in the manifest only: the per-map starts_<map>_v1.lua files
were never read by the mod and went stale when Old World's city table moved Prague and added
Frankfurt, Aachen and Moscow, so the emitter no longer writes them (design notes 2026-10-30,
a development branch).

The manifest records per scale every feature's window, segment count, half-width, depth, shipped
polyline and bend result, every ford (centre, tangent, half-widths, interval) and every skipped ford
interval with its reason, the basins, the T1 corridor mask's pixel count and share, the thin-water
pixels left as land, and the river-safe start of every city: the corridors within its
start disc, the move to the nearest tile with clear tiles of land, and the bank half-planes the start
lake and starting ore read, in world tiles relative to the moved spawn.
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402

EMITTER_VERSION = 3
MAX_COLUMNS = 120
DATA = REPO / "data-src" / "waterways"
APPROVALS = REPO / "data-src" / "approvals" / "approvals-data.json"
EARTHMAPS = REPO / "data-src" / "earthmaps"
GENERATED = REPO / "terra-nauvis" / "prototypes" / "generated"
CONFIG = REPO / "terra-nauvis" / "prototypes" / "config.lua"
# S4's results at the planning commit every ported input names (TST-23: spikes/ never reaches main)
PLANNING_COMMIT = "45c86d706c2124f48112c195813d5a0f696931e0"
S4_FEATURES = "spikes/S4-rivers/results/{map}-features.json"
MIN_ARGS = 64               # arguments per min() call in a balanced tree
# Straits in the oracle's id spelling (tools/oracle.py STRAITS plus Messina and Kerch, which S4 drew)
STRAIT_IDS = {"Strait of Gibraltar": "gibraltar", "Bosporus": "bosporus", "Dardanelles": "dardanelles",
              "Strait of Dover": "dover", "Oresund": "oresund", "Great Belt": "great_belt",
              "Little Belt": "little_belt", "Strait of Messina": "messina", "Kerch Strait": "kerch"}
CANAL_IDS = {"Kiel Canal": "kiel", "Corinth Canal": "corinth", "Suez Canal": "suez", "Panama Canal": "panama"}
DAM_CANAL = {"Isthmus of Corinth": "corinth", "Isthmus of Suez": "suez", "Isthmus of Panama": "panama"}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(Path(p).read_bytes())


def slug(name):
    out, dash = [], False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash:
            out.append("_")
            dash = True
    return "".join(out).strip("_")


def load_cfg():
    return tnconfig.load(CONFIG)


def ww_cfg(cfg):
    w = cfg.get("waterways")
    if not isinstance(w, dict):
        raise SystemExit("config.lua has no waterways group")
    return w


def map_keys(cfg, only=None):
    keys = tnconfig.map_keys(cfg)
    if only:
        if only not in keys:
            raise SystemExit(f"unknown map {only!r}; config.lua maps are {keys}")
        return [only]
    return keys


def write_text(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _is_points(v):
    return (isinstance(v, list) and len(v) > 0 and
            all(isinstance(q, list) and len(q) == 2 and
                all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in q) for q in v))


def _dump(v, indent):
    """JSON with one-space indents, except that point lists ([[x, y], ...]) wrap at about 110 columns, so
    a path of a thousand cells is a few dozen lines instead of four thousand."""
    pad = " " * indent
    if _is_points(v):
        lines, cur = [], ""
        for it in (json.dumps(q) for q in v):
            piece = it if not cur else cur + ", " + it
            if len(pad) + 1 + len(piece) > 110 and cur:
                lines.append(cur + ",")
                cur = it
            else:
                cur = piece
        lines.append(cur)
        return "[\n" + "\n".join(pad + " " + ln for ln in lines) + "\n" + pad + "]"
    if isinstance(v, dict):
        if not v:
            return "{}"
        parts = [f"{pad} {json.dumps(k, ensure_ascii=False)}: {_dump(x, indent + 1)}" for k, x in v.items()]
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(not isinstance(x, (dict, list)) for x in v):
            return json.dumps(v, ensure_ascii=False)
        parts = [f"{pad} {_dump(x, indent + 1)}" for x in v]
        return "[\n" + ",\n".join(parts) + "\n" + pad + "]"
    return json.dumps(v, ensure_ascii=False)


def write_json(p, obj):
    text = _dump(obj, 0) + "\n"
    if json.loads(text) != json.loads(json.dumps(obj)):
        raise ValueError(f"{p}: the compact JSON writer changed the data")
    write_text(p, text)


# ------------------------------------------------------------------------------------------------ import

def git_show(path, commit=PLANNING_COMMIT):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{path}"], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"git show {commit[:12]}:{path} failed: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


# Straits keep their drawn passage through their narrowest point (R7b; the oracle's strait rows,
# decision 19). Each is re-routed at import with S4's own least-cost method (s4geo.dijkstra: drawn water
# and thin water cost 1 per px, land 60, diagonal steps sqrt 2 and three times dearer across a
# corner-only contact) from S4's first cell, through the R7b narrowest point snapped to drawn water,
# to S4's last cell. S4 routed the Dardanelles from the Aegean into the Gulf of Saros and through a
# drawn gap at the Bolayir isthmus to the Sea of Marmara, north of the Gallipoli peninsula, and ended
# it back in the Gulf: it takes these waypoints instead (general-knowledge positions, UNVERIFIED as
# such, as S4's own waypoints were): its Aegean entrance, the narrows, Gelibolu and open Marmara water.
R7B = REPO / "docs" / "plan" / "research" / "R7b-geography.json"
STRAIT_WAYPOINTS = {"dardanelles": [(26.05, 39.95), "narrows", (26.67, 40.41), (27.35, 40.62)]}
PATH_COSTS = {"water": 1.0, "land": 60.0, "corner": 3.0}
SNAP_PX = 8
ISTHMUS_ON_ROUTE_PX = 2


def lonlat_cell(meta, lon, lat):
    g = meta["georeference"]
    return (int(math.floor((g["lat_top_edge"] - lat) * g["px_per_degree"])),
            int(math.floor((lon - g["lon_left_edge"]) * g["px_per_degree"])))


def least_cost_path(water, a, b, pad=40):
    """S4's least-cost route (s4geo.dijkstra) between cells a and b (row, col) in a window around them:
    water cells cost 1, land 60, diagonal steps sqrt 2, tripled across a corner-only contact."""
    import heapq
    np = _np()
    H, W = water.shape
    r0, r1 = max(min(a[0], b[0]) - pad, 0), min(max(a[0], b[0]) + pad + 1, H)
    c0, c1 = max(min(a[1], b[1]) - pad, 0), min(max(a[1], b[1]) + pad + 1, W)
    wat = water[r0:r1, c0:c1]
    cost = np.where(wat, PATH_COSTS["water"], PATH_COSTS["land"])
    h, w_ = cost.shape
    start, goal = (a[0] - r0, a[1] - c0), (b[0] - r0, b[1] - c0)
    dist = np.full((h, w_), np.inf)
    prev = np.full((h, w_), -1, np.int64)
    dist[start] = 0.0
    pq = [(0.0, start[0], start[1])]
    steps = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
             (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
    while pq:
        d, r, c = heapq.heappop(pq)
        if d > dist[r, c]:
            continue
        if (r, c) == goal:
            break
        for dr, dc, sl in steps:
            rr, cc = r + dr, c + dc
            if rr < 0 or cc < 0 or rr >= h or cc >= w_:
                continue
            step = cost[rr, cc] * sl
            if dr and dc and not wat[r + dr, c] and not wat[r, c + dc]:
                step *= PATH_COSTS["corner"]
            nd = d + step
            if nd < dist[rr, cc]:
                dist[rr, cc] = nd
                prev[rr, cc] = r * w_ + c
                heapq.heappush(pq, (nd, rr, cc))
    if not np.isfinite(dist[goal]):
        raise SystemExit(f"no route between cells {a} and {b}")
    path = [goal]
    while prev[path[-1]] >= 0:
        k = int(prev[path[-1]])
        path.append((k // w_, k % w_))
    return [(r + r0, c + c0) for r, c in path[::-1]]


def snap_water(water, cell, max_px=SNAP_PX):
    """The nearest drawn-water cell to `cell` within max_px (S4 snapped its waypoints so)."""
    np = _np()
    r, c = cell
    best = None
    for dr in range(-max_px, max_px + 1):
        for dc in range(-max_px, max_px + 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < water.shape[0] and 0 <= cc < water.shape[1] and water[rr, cc]:
                d2 = dr * dr + dc * dc
                if best is None or d2 < best[0]:
                    best = (d2, (rr, cc))
    if best is None:
        raise SystemExit(f"no drawn water within {max_px} px of {cell}")
    return best[1]


def strait_route(map_key, sid, cells, meta, water, narrows):
    """A strait's cells re-routed through its narrowest point (see STRAIT_WAYPOINTS)."""
    if narrows is None:
        return cells, None
    n_cell = snap_water(water, lonlat_cell(meta, narrows[0], narrows[1]))
    if sid in STRAIT_WAYPOINTS:
        pts = [n_cell if w == "narrows" else snap_water(water, lonlat_cell(meta, w[0], w[1]))
               for w in STRAIT_WAYPOINTS[sid]]
    else:
        pts = [(cells[0][1], cells[0][0]), n_cell, (cells[-1][1], cells[-1][0])]
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        leg = least_cost_path(water, a, b)
        out += leg if not out else leg[1:]
    return [[c, r] for r, c in out], {"narrows_cell": [n_cell[1], n_cell[0]],
                                     "waypoints": [[c, r] for r, c in pts]}


def line_cells(a, b):
    """The 8-connected cells of the straight line from cell a to cell b (row, col), both included."""
    (r0, c0), (r1, c1) = a, b
    n = max(abs(r1 - r0), abs(c1 - c0))
    if n == 0:
        return [a]
    return [(int(round(r0 + (r1 - r0) * k / n)), int(round(c0 + (c1 - c0) * k / n))) for k in range(n + 1)]


def snap_land(meta, land, lon, lat, max_px=SNAP_PX):
    """(row, col) of the nearest reference land pixel, by centre, to a point within max_px: the pixel
    tools/oracle.py's snap gives an isthmus place (its row is tested there), the same tie order
    (numpy's first minimum over rows then columns)."""
    np = _np()
    g = meta["georeference"]
    u, v = (lon - g["lon_left_edge"]) * g["px_per_degree"], (g["lat_top_edge"] - lat) * g["px_per_degree"]
    c0, r0 = int(math.floor(u)), int(math.floor(v))
    R = int(math.ceil(max_px)) + 1
    rs = np.arange(max(r0 - R, 0), min(r0 + R + 1, land.shape[0]))
    cs = np.arange(max(c0 - R, 0), min(c0 + R + 1, land.shape[1]))
    sub = land[np.ix_(rs, cs)]
    d = np.hypot((cs[None, :] + 0.5) - u, (rs[:, None] + 0.5) - v)
    d = np.where(sub, d, np.inf)
    k = np.unravel_index(np.argmin(d), d.shape)
    if not np.isfinite(d[k]) or d[k] > max_px:
        return lonlat_cell(meta, lon, lat)
    return int(rs[k[0]]), int(cs[k[1]])


def canal_route(cells, meta, water, route, isthmus=None, land=None):
    """A canal's cells along its real route (R7b's OpenStreetMap centreline, the oracle's canal rows):
    S4's sea end, a least-cost leg to the route's first vertex, straight cells vertex to vertex, a
    least-cost leg from its last vertex to S4's other sea end. An R7b isthmus point within
    ISTHMUS_ON_ROUTE_PX of the route (Corinth's and Suez's lie on the canal line), at the land pixel the
    oracle snaps it to, becomes a route vertex, so the canal passes through the tested pixel."""
    if not route:
        return cells, None
    verts = [lonlat_cell(meta, lon, lat) for lat, lon in route]
    if isthmus is not None:
        q = snap_land(meta, land, isthmus[0], isthmus[1])
        best = None
        for i, (a, b) in enumerate(zip(verts[:-1], verts[1:])):
            ux, uy = b[0] - a[0], b[1] - a[1]
            L2 = ux * ux + uy * uy
            tt = 0.0 if L2 == 0 else min(max(((q[0] - a[0]) * ux + (q[1] - a[1]) * uy) / L2, 0.0), 1.0)
            d = math.hypot(q[0] - a[0] - tt * ux, q[1] - a[1] - tt * uy)
            if best is None or d < best[0]:
                best = (d, i)
        if best is not None and best[0] <= ISTHMUS_ON_ROUTE_PX and q not in verts:
            verts.insert(best[1] + 1, q)
    start, end = (cells[0][1], cells[0][0]), (cells[-1][1], cells[-1][0])
    out = least_cost_path(water, start, verts[0])
    for a, b in zip(verts[:-1], verts[1:]):
        out += line_cells(a, b)[1:]
    out += least_cost_path(water, verts[-1], end)[1:]
    dedup = [out[0]]
    for c in out[1:]:
        if c != dedup[-1]:
            dedup.append(c)
    return [[c, r] for r, c in dedup], {"route_cells": [[c, r] for r, c in verts]}


def import_map(map_key):
    """data-src/waterways/<map>.json: APPROVALS 7's adopted rivers in priority order with their class
    and S4's cell path, S4's straits, the canals APPROVALS 6 puts on the map and their dams."""
    src_path = S4_FEATURES.format(map=map_key)
    raw = git_show(src_path)
    feats = json.loads(raw)["features"]
    by_name = {f["name"]: f for f in feats}
    appr_bytes = APPROVALS.read_bytes()
    A = json.loads(appr_bytes)
    rows = A["rivers"][map_key]
    rivers = []
    for r in rows:
        if not r["adopted"]:
            continue
        f = by_name.get(r["name"])
        if f is None or f["kind"] != "river":
            raise SystemExit(f"{map_key}: adopted river {r['name']!r} has no S4 feature in {src_path}")
        rivers.append({"rank": r["rank"], "id": slug(r["name"]), "name": r["name"], "class": r["class"],
                       "block": r["block"], "length_px": r["length_px"], "map_km": r["map_km"],
                       "ends_in": r["ends_in"], "real_width_km": f["real_width_km"],
                       "cells": [[int(c), int(rr)] for c, rr in f["polyline_cells"]]})
    straits = []
    meta = json.loads((EARTHMAPS / f"{map_key}.json").read_text(encoding="utf-8"))
    import earthgeo as eg
    mref = eg.MapRef(map_key)
    water = ~mref.land | mref.thin
    r7b = {s["id"]: s for s in json.loads(R7B.read_text(encoding="utf-8"))["straits"]}
    for f in feats:
        if f["kind"] == "strait":
            sid = STRAIT_IDS[f["name"]]
            np_ = r7b.get(sid, {}).get("narrowest_point")
            cells, route = strait_route(map_key, sid, [[int(c), int(rr)] for c, rr in f["polyline_cells"]], meta,
                                        water, (np_["lon"], np_["lat"]) if np_ else None)
            rec = {"id": sid, "name": f["name"], "width_class": f["width_class"],
                   "real_width_km": f["real_width_km"], "cells": cells}
            if route:
                rec["route"] = dict(route, rule="re-routed at import through the R7b narrowest point "
                                                "(docs/plan/research/R7b-geography.json) with S4's least-cost "
                                                "method; see STRAIT_WAYPOINTS")
            straits.append(rec)
    on_map = {c["id"]: bool(c["maps"].get(map_key)) for c in A["canals"]}
    R = json.loads(R7B.read_text(encoding="utf-8"))
    routes = {c["id"]: c.get("route_polyline") for c in R["canals"]}
    isthmi = {i["id"]: (i["narrowest_point"]["lon"], i["narrowest_point"]["lat"]) for i in R.get("isthmuses", [])}
    canals, dams = [], []
    for f in feats:
        if f["kind"] == "canal":
            cid = CANAL_IDS[f["name"]]
            if on_map.get(cid):
                cells, route = canal_route([[int(c), int(rr)] for c, rr in f["polyline_cells"]], meta, water,
                                           routes.get(cid), isthmi.get(cid), mref.land)
                rec = {"id": cid, "name": f["name"], "real_width_km": f["real_width_km"], "cells": cells}
                if route:
                    rec["route"] = dict(route, rule="S4's sea ends joined to R7b's route vertices "
                                                    "(docs/plan/research/R7b-geography.json canals route_polyline)")
                canals.append(rec)
        elif f["kind"] == "dam":
            cid = DAM_CANAL[f["name"]]
            if on_map.get(cid):
                dams.append({"id": cid, "name": f["name"], "canal": cid,
                             "polyline_px": [[float(x), float(y)] for x, y in f["polyline_eps0.5"]]})
    missing = sorted(c for c, on in on_map.items() if on and c not in {x["id"] for x in canals})
    if missing:
        raise SystemExit(f"{map_key}: APPROVALS 6 puts {missing} on the map but S4 drew no such canal")
    rec = {
        "format": "tn-waterways/1",
        "map": map_key,
        "built_by": "tools/build_waterways.py import",
        "sources": {
            "features": {"path": src_path, "commit": PLANNING_COMMIT, "sha256": sha256_bytes(raw)},
            "approvals": {"path": "data-src/approvals/approvals-data.json", "sha256": sha256_bytes(appr_bytes)},
        },
        "frame": "cells are [col, row] of the map's reference raster (data-src/earthmaps/<map>-land.png), each "
                 "feature's path from its inland end to its sea end (S4 section 1); a dam's polyline_px is S4's "
                 "0.5 px simplification in pixel coordinates, pixel centres at col + 0.5",
        "rule": "rivers: APPROVALS 7's adopted rows in priority order (rivers[] of approvals-data.json), each with "
                "its class; straits: S4's D17 set; canals and dams: APPROVALS 6's rows on this map",
        "rivers": rivers,
        "straits": straits,
        "canals": canals,
        "dams": dams,
    }
    # a recorded cut (the plan's waterway cut order, each with its the design notes entry) is data the
    # import keeps: it never re-adds a river a cut removed from a scale
    old = DATA / f"{map_key}.json"
    if old.exists():
        prev = json.loads(old.read_text(encoding="utf-8"))
        if prev.get("cuts"):
            rec["cuts_rule"] = prev.get("cuts_rule")
            rec["cuts"] = prev["cuts"]
    write_json(DATA / f"{map_key}.json", rec)
    return {"map": map_key, "rivers": len(rivers), "straits": len(straits), "canals": len(canals), "dams": len(dams)}


def write_provenance(cfg):
    """data-src/waterways/PROVENANCE.md: every file's sha256 (the T16 data-src row re-hashes them)."""
    files = sorted(p for p in DATA.iterdir() if p.is_file() and p.name != "PROVENANCE.md")
    lines = [
        "# Waterways: provenance",
        "",
        "The inputs and the emission manifests of `tools/build_waterways.py` (ARCHITECTURE.md, \"Build-time data",
        "flow\", step 3; slice `waterways`). The T16 data-src row re-hashes every file of this folder against the",
        "table below, and the gate's `ww_emit` row re-emits the generated sets from the inputs twice and",
        "compares each byte for byte with the committed Lua.",
        "",
        "## Source",
        "",
        "Each `<map>.json` is written by `python tools/build_waterways.py import` from S4's path extraction",
        f"(`spikes/S4-rivers/results/<map>-features.json` at planning commit `{PLANNING_COMMIT}` on",
        "`origin/planning/sprint-1`, read with `git show`; TST-23) and from `data-src/approvals/approvals-data.json`:",
        "APPROVALS 7's adopted rivers in priority order with their class, S4's nine straits, and the canals and",
        "dams APPROVALS 6 puts on the map. S4's own commands, run from the Factorio workspace with numpy and",
        "Pillow on the S8 reference rasters (S4 README): `python mod/spikes/S4-rivers/s4.py vectorise`.",
        "Each `manifest-<map>.json` is written by `python tools/build_waterways.py emit` beside the generated",
        "files it describes. A cut under the plan's waterway cut order is an edit to `<map>.json` (a river",
        "removed from the bottom of its list, or a tolerance raised) regenerated in the same commit, with a",
        "DECISIONS.md entry citing the timed run (plan section 6.3).",
        "",
        "| File | sha256 | Role |",
        "|---|---|---|",
    ]
    for p in files:
        role = "emission manifest" if p.name.startswith("manifest-") else "tool input"
        lines.append(f"| `{p.name}` | `{sha256_file(p)}` | {role} |")
    write_text(DATA / "PROVENANCE.md", "\n".join(lines) + "\n")


# ------------------------------------------------------------------------------------------------ geometry

def _np():
    import numpy as np
    return np


def resample(P, step):
    np = _np()
    P = np.asarray(P, float)
    seg = np.diff(P, axis=0)
    L = np.sqrt((seg ** 2).sum(1))
    s = np.concatenate([[0.0], np.cumsum(L)])
    n = max(int(s[-1] / step), 1)
    t = np.linspace(0.0, s[-1], n + 1)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], 1)


def box_smooth(Q, w, passes):
    np = _np()
    if w <= 1:
        return Q.copy()
    k = np.ones(w) / w
    out = Q.copy()
    pad = w // 2
    for _ in range(passes):
        ext = np.concatenate([np.repeat(out[:1], pad, 0), out, np.repeat(out[-1:], pad, 0)])
        out = np.stack([np.convolve(ext[:, 0], k, "valid"), np.convolve(ext[:, 1], k, "valid")], 1)
        out[0], out[-1] = Q[0], Q[-1]
    return out


def dp_simplify(pts, eps):
    """Douglas-Peucker on an (n, 2) array; keeps both end points (S4's s4geo.dp_simplify)."""
    np = _np()
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts.copy()
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    xs, ys = pts[:, 0].tolist(), pts[:, 1].tolist()
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = xs[i], ys[i]
        sx, sy = xs[j] - ax, ys[j] - ay
        L2 = sx * sx + sy * sy
        if j - i < 48:
            # small spans in plain floats: the same distances as the vector path, without numpy's
            # per-call overhead (the first maximum wins in both)
            best, k = -1.0, -1
            for m in range(i + 1, j):
                qx, qy = xs[m] - ax, ys[m] - ay
                if L2 == 0:
                    d = math.sqrt(qx * qx + qy * qy)
                else:
                    tt = min(max((qx * sx + qy * sy) / L2, 0.0), 1.0)
                    ex, ey = qx - tt * sx, qy - tt * sy
                    d = math.sqrt(ex * ex + ey * ey)
                if d > best:
                    best, k = d, m - i - 1
            dk = best
        else:
            seg = np.array([sx, sy])
            q = pts[i + 1:j] - pts[i]
            if L2 == 0:
                d = np.sqrt((q ** 2).sum(1))
            else:
                tt = np.clip((q @ seg) / L2, 0, 1)
                d = np.sqrt(((q - np.outer(tt, seg)) ** 2).sum(1))
            k = int(np.argmax(d))
            dk = float(d[k])
        if dk > eps:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return pts[keep]


def snap(P, grid):
    np = _np()
    return np.round(np.asarray(P, float) * grid) / grid


def dedupe(P):
    np = _np()
    P = np.asarray(P, float)
    keep = [0]
    for i in range(1, len(P)):
        if abs(P[i, 0] - P[keep[-1], 0]) > 1e-12 or abs(P[i, 1] - P[keep[-1], 1]) > 1e-12:
            keep.append(i)
    return P[keep]


def turn_windows(P, window, limit_deg):
    """R4's bend rule on a polyline in tiles: the stretches of at most `window` tiles of centreline whose
    headings turn by more than limit_deg in total (S4's turn_violations, kept as stretches). Returns
    (violations, worst turn in degrees, [(first inner vertex, last inner vertex, sharpest vertex)])."""
    np = _np()
    P = np.asarray(P, float)
    if len(P) < 3:
        return 0, 0.0, []
    seg = np.diff(P, axis=0)
    L = np.sqrt((seg ** 2).sum(1))
    ang = np.arctan2(seg[:, 1], seg[:, 0])
    turn = np.abs((np.diff(ang) + np.pi) % (2 * np.pi) - np.pi)     # at inner vertex i + 1
    pos = np.cumsum(L)[:-1]                                           # arc position of inner vertex i + 1
    viol, worst, runs = 0, 0.0, []
    j, acc = 0, 0.0
    for i in range(len(turn)):
        acc += turn[i]
        while pos[i] - pos[j] > window:
            acc -= turn[j]
            j += 1
        d = math.degrees(acc)
        worst = max(worst, d)
        if d > limit_deg + 1e-6:
            viol += 1
            sharp = j + int(np.argmax(turn[j:i + 1]))
            runs.append((j + 1, i + 1, sharp + 1))
    return viol, round(worst, 1), runs


def seg_dist(P, Q):
    """Distance from each point of P (n, 2) to the polyline Q (m, 2), and the arc position of the foot."""
    np = _np()
    P = np.asarray(P, float)
    Q = np.asarray(Q, float)
    best = np.full(len(P), np.inf)
    foot = np.zeros(len(P))
    acc = 0.0
    for a, b in zip(Q[:-1], Q[1:]):
        u = b - a
        L2 = float(u @ u)
        if L2 == 0:
            continue
        t = np.clip(((P - a) @ u) / L2, 0, 1)
        d = np.hypot(P[:, 0] - a[0] - t * u[0], P[:, 1] - a[1] - t * u[1])
        better = d < best
        best = np.where(better, d, best)
        foot = np.where(better, acc + t * math.sqrt(L2), foot)
        acc += math.sqrt(L2)
    return best, foot


def polyline_length(P):
    np = _np()
    P = np.asarray(P, float)
    if len(P) < 2:
        return 0.0
    return float(np.sqrt((np.diff(P, axis=0) ** 2).sum(1)).sum())


def point_at(P, a):
    """(point, unit tangent, segment index) at arc length a along the polyline P."""
    np = _np()
    acc = 0.0
    for i in range(len(P) - 1):
        u = P[i + 1] - P[i]
        L = float(np.hypot(u[0], u[1]))
        if L == 0:
            continue
        if acc + L >= a or i == len(P) - 2:
            t = min(max((a - acc) / L, 0.0), 1.0)
            return P[i] + t * u, u / L, i
        acc += L
    return P[-1], np.array([1.0, 0.0]), len(P) - 2


# ------------------------------------------------------------------------------------------------ widths

def half_width(w, kind, s, width_class=None, real_km=0.0, river_class=None):
    """Half-width in tiles: rivers max(floor / 2 + margin, k s / 2) by class,
    straits max(F / 2 + margin, s / 2, w s / (2 km_per_px)), canals max(floor / 2 + margin, s / 2)."""
    floor = w["floor_tiles"] / 2 + w["margin_tiles"]
    if kind == "river":
        return max(floor, w["river_k"][river_class] * s / 2)
    if kind == "strait":
        F = w["two_way_tiles"] if width_class == "two_way" else w["floor_tiles"]
        return max(F / 2 + w["margin_tiles"], 0.5 * s, 0.5 * real_km * s / w["km_per_px"])
    if kind == "canal":
        return max(floor, 0.5 * s)
    if kind == "dam":
        return max(w["dam"]["floor_tiles"], w["dam"]["per_scale"] * s)
    raise ValueError(kind)


def warp_reach(w, s, passage=False):
    """The farthest the shared warp moves a river (or a passage) from its polyline, in tiles: the octaves'
    amplitudes at the scale times the peak of basis noise (config.lua natural.noise_peak)."""
    N = w["natural"]
    return N["noise_peak"] * sum((o["amplitude"][0] + o["amplitude"][1] * s) * (o["passage"] if passage else 1)
                                 for o in N["warp"])


def river_widths(w, f, s, geo):
    """A half-width per shipped segment of a river: the class half-width times the profile, source at the
    inland end to mouth where the course meets the coast fit, and tip at the very source, which tapers over
    taper_tiles, each on a step_tiles grid so segments share classes. The floor holds everywhere but the
    taper, which the warp and W then leave a natural end instead of a round cap. Returns (widths, the
    half-width at arc length a)."""
    np = _np()
    Pf = w["natural"]["profile"]
    P = np.asarray(f["P"], float)
    L = np.sqrt((np.diff(P, axis=0) ** 2).sum(1))
    cum = np.concatenate([[0.0], np.cumsum(L)])
    land = geo.fit_land_at_geo(P[:, 0], P[:, 1], s)
    idx = np.nonzero(land)[0]
    coast = float(cum[idx[-1]]) if len(idx) else float(cum[-1])
    coast = max(coast, 1.0)
    floor = w["natural"]["width"]["floor_half_tiles"]
    step = Pf["step_tiles"]
    taper = Pf["taper_tiles"][0] + Pf["taper_tiles"][1] * s

    def at(a):
        t = min(a / coast, 1.0)
        hw = max(floor, f["hw"] * (Pf["source"] + (Pf["mouth"] - Pf["source"]) * t))
        if a < taper:
            hw *= Pf["tip"] + (1 - Pf["tip"]) * a / taper
        return max(round(hw / step) * step, step)

    return [at(float(c + l / 2)) for c, l in zip(cum[:-1], L)], at


def class_width(w, river_class, s):
    """A river's design width in tiles, max(floor, k s) (APPROVALS 7's table; T5's width check)."""
    return max(w["floor_tiles"], w["river_k"][river_class] * s)


# ------------------------------------------------------------------------------------------------ per scale

class MapGeo:
    def __init__(self, cfg, map_key):
        m = cfg["maps"][map_key]
        self.key = map_key
        self.W, self.H, self.wr, self.hr = m["width_px"], m["height_px"], m["wr"], m["hr"]
        self._land = self._thin = None
        # the lattice detail's largest move of the coast in reference px (coast.lua: amplitude times
        # the clamp of its octave sum)
        self.detail_px = float(cfg["coast"]["detail_amplitude_px"]) * float(cfg["coast"]["detail_clamp"])

    def offset(self, s):
        """Geo tile = s * u + offset for S4's pixel coordinate u: offset = floor(s / 2) - s (r + 0.5)."""
        c = s // 2
        return c - s * (self.wr + 0.5), c - s * (self.hr + 0.5)

    _RASTERS = {}
    _FITS = {}
    _LOW = {}

    def _fit(self):
        """(fit land, checkpoint record) and the fit's smallest value over each pixel's 3 x 3
        neighbourhood: the shipped coast fit at every reference pixel centre (data-src/fits/<map>/fit.json's
        geo checkpoint, evaluated by build_geo.pixel_values), thresholded at 0, and that minimum. The fit is
        piecewise bilinear between pixel centres (S1-fit's tents), so the minimum bounds it anywhere in the
        pixel, and the lattice detail moves the coast by at most its amplitude (S9): where the minimum
        exceeds the amplitude, the pixel is land in the game at every seed."""
        if self.key not in MapGeo._FITS:
            import build_geo as bg
            np = _np()
            spec = bg.fit_spec(self.key)
            ck = bg.FITS / self.key / spec["bodies"]["geo"]["checkpoint"]
            meta, idx, coef = bg.load_model(ck)
            v = bg.pixel_values(meta, idx, coef)
            MapGeo._FITS[self.key] = (v > 0, {"path": ck.relative_to(REPO).as_posix(),
                                              "sha256": sha256_bytes(ck.read_bytes())})
            low = v.copy()
            H, W = v.shape
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ys, yd = (slice(max(dy, 0), H + min(dy, 0)), slice(max(-dy, 0), H + min(-dy, 0)))
                    xs, xd = (slice(max(dx, 0), W + min(dx, 0)), slice(max(-dx, 0), W + min(-dx, 0)))
                    np.minimum(low[yd, xd], v[ys, xs], out=low[yd, xd])
            MapGeo._LOW[self.key] = low
            del v
        return MapGeo._FITS[self.key], MapGeo._LOW[self.key]

    def fit_land(self):
        """The shipped coast fit's land at every reference pixel centre and its checkpoint's path and sha256."""
        return self._fit()[0]

    def bank_check(self, X, Y, s):
        """A ford's bank samples at geo tiles (X, Y): (each lies on land in the reference raster and in the
        shipped coast fit, the smallest 3 x 3 fit minimum over their pixels in reference px, -inf when
        not). The fit keeps wide thin water, a lake or a delta, as water, and its error elsewhere can
        leave water where the reference has land; a bank whose minimum exceeds the coast detail's
        amplitude (detail_px) is land at every seed, one below it may be water at some."""
        np = _np()
        land, _ = self.load()
        (fit, _), low = self._fit()
        X = np.asarray(X, float)
        Y = np.asarray(Y, float)
        c = np.floor((X - s // 2) / s + self.wr + 0.5).astype(np.int64)
        r = np.floor((Y - s // 2) / s + self.hr + 0.5).astype(np.int64)
        if not ((c >= 0) & (c < self.W) & (r >= 0) & (r < self.H)).all():
            return False, float("-inf")
        if not (land[r, c] & fit[r, c]).all():
            return False, float("-inf")
        return True, float(low[r, c].min())

    def load(self):
        if self._land is None:
            if self.key not in MapGeo._RASTERS:
                import earthgeo as eg
                mref = eg.MapRef(self.key)
                MapGeo._RASTERS[self.key] = (mref.land, mref.thin)
            self._land, self._thin = MapGeo._RASTERS[self.key]
        return self._land, self._thin

    def fit_land_at_geo(self, X, Y, s, strict=False):
        """Whether the coast fit's target is land at geo tiles (X, Y): the reference raster's pixel of each
        tile, thin water counted as land (the fit fills it, S1-fit), or, when strict, land in both the
        reference and the shipped coast fit (bank_check scores a ford's banks)."""
        np = _np()
        land, thin = self.load()
        X = np.asarray(X, float)
        Y = np.asarray(Y, float)
        c = np.floor((X - s // 2) / s + self.wr + 0.5).astype(np.int64)
        r = np.floor((Y - s // 2) / s + self.hr + 0.5).astype(np.int64)
        inside = (c >= 0) & (c < self.W) & (r >= 0) & (r < self.H)
        out = np.zeros(X.shape, bool)
        cc, rr = np.clip(c, 0, self.W - 1), np.clip(r, 0, self.H - 1)
        if strict:
            (fit, _), _ = self._fit()
            out[inside] = land[rr[inside], cc[inside]] & fit[rr[inside], cc[inside]]
        else:
            out[inside] = land[rr[inside], cc[inside]] | thin[rr[inside], cc[inside]]
        return out


def scale_cut(w, data, s):
    """(Douglas-Peucker tolerance in tiles, rivers carved) at scale s: config.lua's tolerance and every
    adopted river, unless the map's data-src file records a cut for the scale under the plan's waterway
    cut order (section 6.3: tolerance up, then rivers out from the bottom of the list, never one of
    Europe's 22), each with its the design notes entry."""
    cut = (data.get("cuts") or {}).get(str(s)) or {}
    tol = cut.get("tolerance_tiles", w["tolerance_tiles"][s - 1])
    n = cut.get("rivers", len(data["rivers"]))
    return float(tol), int(n)


def keep_cells(feature, kind):
    """The cells a drawn passage's simplified course keeps as vertices, so its carve holds the places
    the oracle tests there whatever the tolerance: a strait's R7b waypoints and narrowest point, a
    canal's R7b route vertices (its isthmus point among them)."""
    r = feature.get("route") or {}
    if kind == "canal":
        return [tuple(c) for c in r.get("route_cells") or []]
    if kind == "strait":
        out = [tuple(c) for c in r.get("waypoints") or []]
        return out + ([tuple(r["narrows_cell"])] if r.get("narrows_cell") else [])
    return []


def dp_tolerances(pts, eps):
    """Douglas-Peucker with a tolerance per point: a span splits at the point that most exceeds its
    own tolerance, while any does; keeps both end points."""
    np = _np()
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts.copy()
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = pts[j] - pts[i]
        L2 = float(seg @ seg)
        q = pts[i + 1:j] - pts[i]
        if L2 == 0:
            d = np.sqrt((q ** 2).sum(1))
        else:
            tt = np.clip((q @ seg) / L2, 0, 1)
            d = np.sqrt(((q - np.outer(tt, seg)) ** 2).sum(1))
        x = d - eps[i + 1:j]
        k = int(np.argmax(x))
        if x[k] > 0:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return pts[keep]


def kept_simplify(Q, cells, keep, tol, tight, step):
    """Douglas-Peucker of a passage at `tol`, its kept cells held within `tight` tiles: the course
    `cells` (px cells, in order; Q is their centres in tiles) is resampled piece by piece between the
    kept cells it passes, so each kept cell's centre is a sample point, which then carries the tighter
    tolerance (the oracle tests those places: they stay inside the carve with a margin)."""
    np = _np()
    pos = [tuple(int(v) for v in c) for c in cells]
    want = set(keep)
    cuts = sorted({0, len(pos) - 1} | {i for i, c in enumerate(pos) if c in want})
    parts, tight_at = [], []
    for a, b in zip(cuts[:-1], cuts[1:]):
        R = resample(Q[a:b + 1], step)
        if parts:
            R = R[1:]
        parts.append(R)
        if pos[b] in want:
            tight_at.append(sum(len(p) for p in parts) - 1)
    if pos[0] in want:
        tight_at.append(0)
    R = np.concatenate(parts) if parts else np.asarray(Q, float)
    eps = np.full(len(R), float(tol))
    eps[tight_at] = min(float(tol), float(tight))
    return dp_tolerances(R, eps)


def canal_course(cells, route):
    """A canal's drawn course in px cells: S4's sea-end legs as cells and, between them, straight lines
    through R7b's route vertices. The rasterised route lines are a staircase of pixel steps, which
    Douglas-Peucker keeps wherever the passage tolerance is under a pixel (scales 3 to 6), at a cost of
    about 30 Tile per kept segment; the route vertices are the canal's real course."""
    np = _np()
    pos = [tuple(c) for c in cells]
    verts = []
    for v in route:
        if not verts or verts[-1] != tuple(v):
            verts.append(tuple(v))
    if verts[0] not in pos or verts[-1] not in pos:
        raise SystemExit("canal course: a route end vertex is not on the canal's cells (re-run import)")
    i0 = pos.index(verts[0])
    i1 = len(pos) - 1 - pos[::-1].index(verts[-1])
    if i1 < i0:
        raise SystemExit("canal course: the route's last vertex precedes its first on the canal's cells")
    return np.asarray(pos[:i0] + verts + pos[i1 + 1:], float)


def deloop(cells, D):
    """A river's cells with its out-and-back hooks cut: a cell within gap_px (Chebyshev) of a cell at least
    arc_px and at most reach_px later on the path jumps to the last such cell. S4's least-cost route takes
    such a hook where the drawn water branches (the Rhine's delta, 54 px out and back): no smoothing
    window loses it, and it is what the bend rule put two turning basins on."""
    np = _np()
    C = np.asarray(cells, float)
    gap, arc, reach = int(D["gap_px"]), int(D["arc_px"]), int(D["reach_px"])
    keep, i, n = [], 0, len(C)
    while i < n:
        keep.append(i)
        j0, j1 = i + arc, min(n, i + reach)
        if j0 < j1:
            hit = np.nonzero(np.abs(C[j0:j1] - C[i]).max(1) <= gap)[0]
            if len(hit):
                i = j0 + int(hit[-1])
                continue
        i += 1
    return C[keep]


def shaped(w, feature, kind, s, geo, tol=None, hw=None):
    """(window, polyline in geo tiles, bend record) of one feature at scale s (hw: a passage's
    half-width, which holds its kept R7b points within hw less one tile of the course)."""
    np = _np()
    ox, oy = geo.offset(s)
    grid = w["vertex_grid"]
    if tol is None:
        tol = w["tolerance_tiles"][s - 1]
    if kind == "dam":
        P = np.asarray(feature["polyline_px"], float) * s + [ox, oy]
        P = dedupe(snap(P, grid))
        return None, P, {"violations": 0, "worst_deg": 0.0, "runs": [], "smoothed_fails": []}
    route = (feature.get("route") or {}).get("route_cells") if kind == "canal" else None
    raw = canal_course(feature["cells"], route) if route else np.asarray(feature["cells"], float)
    if kind == "river":
        raw = deloop(raw, w["natural"]["deloop"])
    cells = raw + 0.5
    bw, lim = w["bend"]["window_tiles"], w["bend"]["limit_degrees"]
    fine = w["smoothing"]["fine_tolerance_tiles"]
    if kind in w["smoothing"]["drawn_kinds"]:
        # a strait or canal is a sea passage EarthMaps draws as thin water, which the coast fit fills as
        # land: only its carve restores it, so it keeps its drawn course (no smoothing), simplified at
        # the scale's tolerance between the R7b points it keeps, and takes a turning basin wherever its
        # shipped polyline fails the bend rule
        tight = max(1.0, (hw if hw is not None else tol + 1.0) - 1.0)
        Pk = kept_simplify(cells * s, raw, keep_cells(feature, kind), tol, tight, w["smoothing"]["step_tiles"])
        P = dedupe(snap(Pk + [ox, oy], grid))
        v, worst, runs = turn_windows(P, bw, lim)
        return 1, P, {"violations": v, "worst_deg": worst, "runs": runs, "smoothed_fails": []}
    Q = resample(cells * s, w["smoothing"]["step_tiles"])
    # S4's smoothing (s4width.smooth_for_scale): the smallest window whose smoothed centreline, at the
    # fine tolerance, obeys the bend rule; the largest window where none does
    chosen = None
    least = w["smoothing"]["min_window_px"] * s
    windows = [x for x in w["smoothing"]["windows"] if x >= least] or w["smoothing"]["windows"][-1:]
    for win in windows:
        Sm = box_smooth(Q, int(win), w["smoothing"]["passes"])
        Pf = dp_simplify(Sm, fine)
        v, _, runs_f = turn_windows(Pf, bw, lim)
        chosen = (int(win), Sm, Pf, runs_f)
        if v == 0:
            break
    win, Sm, Pf, runs_f = chosen
    P = dedupe(snap(dp_simplify(Sm, tol) + [ox, oy], grid))
    v, worst, runs = turn_windows(P, bw, lim)
    # where the smoothed centreline itself still fails, its sharpest vertex of each failing stretch
    # (S4: the Rhine and the Garonne at scale 6)
    smoothed_fails = [stretch_centre(Pf, a, b, ox, oy) for a, b, _ in runs_f]
    return win, P, {"violations": v, "worst_deg": worst, "runs": runs, "smoothed_fails": smoothed_fails}


def stretch_centre(P, a, b, ox=0.0, oy=0.0):
    """The centre of the bounding box of a failing stretch's turning vertices a to b: they lie within the
    bend window of path of each other, so a basin square larger than the window centred there holds
    every one of them."""
    lo, hi = a, b
    xs = [float(P[i][0]) for i in range(lo, hi + 1)]
    ys = [float(P[i][1]) for i in range(lo, hi + 1)]
    return (round(((min(xs) + max(xs)) / 2 + ox) * 16) / 16, round(((min(ys) + max(ys)) / 2 + oy) * 16) / 16)


def basins_for(P, runs, half, smoothed_fails=()):
    """Turning basins (R4 W10): one centred on each stretch where the smoothed centreline still fails the
    bend rule, then one on each failing stretch of the shipped polyline that no basin covers yet."""
    out = []
    for c in smoothed_fails:
        if not any(max(abs(c[0] - b[0]), abs(c[1] - b[1])) <= half / 2 for b in out):
            out.append(c)
    for a, b, _ in runs:
        if basin_cover(P, [(a, b, None)], out, half):
            continue
        out.append(stretch_centre(P, a, b))
    return out


# The turning basins T5's bend criterion names (design section 10, milestone 0: "basins exist for the
# Dardanelles at every scale and for the Rhine, the Garonne and the Little Belt at scale 6 (S4)"), by
# feature id and the scales they are required at. Where the bend rule places none on a map that carries
# the feature, one 30 x 30 basin sits at the shipped polyline's sharpest stretch, in the feature's own
# set.
REQUIRED_BASINS = {"dardanelles": (1, 2, 3, 4, 5, 6), "little_belt": (6,), "rhine": (6,), "garonne": (6,)}


def sharpest_centre(P, window):
    """The centre of the stretch of at most `window` tiles of path whose headings turn the most in total
    (turn_windows' measure; the middle vertex of a polyline without a turn)."""
    np = _np()
    P = np.asarray(P, float)
    if len(P) < 3:
        m = P[len(P) // 2] if len(P) % 2 else (P[len(P) // 2 - 1] + P[len(P) // 2]) / 2
        return round(float(m[0]) * 16) / 16, round(float(m[1]) * 16) / 16
    seg = np.diff(P, axis=0)
    L = np.sqrt((seg ** 2).sum(1))
    ang = np.arctan2(seg[:, 1], seg[:, 0])
    turn = np.abs((np.diff(ang) + np.pi) % (2 * np.pi) - np.pi)
    pos = np.cumsum(L)[:-1]
    best, j, acc = (-1.0, 0, 0), 0, 0.0
    for i in range(len(turn)):
        acc += turn[i]
        while pos[i] - pos[j] > window:
            acc -= turn[j]
            j += 1
        if acc > best[0] + 1e-9:
            best = (acc, j, i)
    return stretch_centre(P, best[1] + 1, best[2] + 1)


def course_tangent(P, c):
    """The unit direction of a polyline around its vertex nearest the point c."""
    np = _np()
    P = np.asarray(P, float)
    i = int(np.argmin(((P - np.asarray(c, float)) ** 2).sum(1)))
    d = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
    n = float(np.hypot(d[0], d[1]))
    return (float(d[0] / n), float(d[1] / n)) if n > 0 else (1.0, 0.0)


def basin_cover(P, runs, basins, half):
    """Every failing stretch's vertices lie inside some basin square (T5's bend rule with basins)."""
    for a, b, _ in runs:
        for i in range(a, b + 1):
            x, y = float(P[i][0]), float(P[i][1])
            if not any(max(abs(x - bx), abs(y - by)) <= half for bx, by in basins):
                return False
    return True


# a ford interval in which every position has a bank that is water in the reference or the coast fit:
# it runs through a lake, a reservoir or an estuary, which no ford can span (the suite accepts such an
# interval, and only such an interval, and records it)
NATURAL_WATER = "a bank is water in the reference or the coast fit (lake, sea or coast)"
CLASH = "another corridor within the banks"


def place_fords(w, geo, s, P, hw, others, fid="", hw_at=None):
    """Fords of one river at scale s: one per every_px * s tiles of the shipped path.
    Every whole-tile position of an interval, from its middle outward, is a candidate whose banks are
    land in the reference and the coast fit (geo.bank_check) with no other corridor within them. A
    straight reach (the path within one tile of the tangent line over the ford and two tiles each way)
    keeps the plain rectangle; a bending one widens it by the reach's deviation, so it still spans the
    carve over its whole length (T5 measures the length along the river). The ford takes, in order:
    the first straight candidate whose banks clear the coast detail (land at every seed); the least
    bending such candidate; else the candidate whose banks come nearest to clearing it (straight
    first), marked `bank_margin_px` (its banks may be water at some seeds). An interval without a
    candidate is skipped with the reasons its positions failed on; natural water is the one reason
    the suite accepts. Returns (fords, skipped intervals)."""
    np = _np()
    F = w["ford"]
    D = F["every_px"] * s
    hl = F["length_tiles"] / 2
    # a ford reads the river's warped tiles, so it spans the river's carve at its widest there; its banks
    # are safe when the warp's whole reach still leaves them on land
    wide = 1 + w["natural"]["width"]["amplitude"]
    reach = warp_reach(w, s)
    L = polyline_length(P)
    n = int(L // D)
    cum = np.concatenate([[0.0], np.cumsum(np.sqrt((np.diff(P, axis=0) ** 2).sum(1)))])

    def ford(k, a, C, T, half_width, dev=None, margin=None):
        rec = {"interval": k, "arc_tiles": round(float(a), 3),
               "centre": [round(float(C[0]), 4), round(float(C[1]), 4)],
               "tangent": [round(float(T[0]), 6), round(float(T[1]), 6)],
               "half_length": hl, "half_width": round(half_width, 4)}
        if dev is not None:
            rec["bend_tiles"] = round(float(dev), 3)
        if margin is not None:
            rec["bank_margin_px"] = round(float(margin), 3)
        return rec

    fords, skipped = [], []
    for k in range(n):
        lo, hi = k * D + hl + 2, (k + 1) * D - hl - 2
        # off the interval's middle by a hash of the river and interval, so the fords stop reading as a
        # dashed line along the river
        spread = hashlib.sha256(f"{fid}:{k}".encode("ascii")).digest()[0] / 255 - 0.5
        a0 = (k + 0.5 + 2 * F["jitter"] * spread) * D
        steps = [0]
        for d in range(1, int(D / 2) + 1):
            steps += [d, -d]
        found, bent, marginal, whys, tried = None, None, None, set(), 0
        for d in steps:
            a = a0 + d
            if a < lo or a > hi:
                continue
            tried += 1
            C, T, _ = point_at(P, a)
            N = np.array([-T[1], T[0]])
            across = (hw_at(a) if hw_at else hw) * wide + F["margin_tiles"]
            # the reach's deviation from the tangent line over the ford's length plus two tiles each way
            # (its vertices there and the stretch's two ends)
            lo_a, hi_a = a - hl - 2, a + hl + 2
            near = [point_at(P, lo_a)[0], point_at(P, hi_a)[0]] +                 [P[i] for i in range(len(P)) if lo_a < cum[i] < hi_a]
            dev = max(abs(float((q - C) @ N)) for q in near)
            straight = dev <= 1.0
            if not straight and bent is not None and bent[0] <= dev:
                continue        # a safe position that bends less already holds this interval's ford
            acr = across if straight else across + dev
            bank = acr + F["bank_tiles"]
            pts = []
            for t in (-hl, 0.0, hl):
                for sign in (-1, 1):
                    for off in np.linspace(acr, bank, 3):
                        pts.append(C + t * T + sign * off * N)
            pts = np.array(pts)
            land, score = geo.bank_check(pts[:, 0], pts[:, 1], s)
            if not land:
                whys.add(NATURAL_WATER)
                continue
            clash = False
            for O, ohw, lo_xy, hi_xy in others:
                if ((C < lo_xy - bank - ohw - 1).any()) or ((C > hi_xy + bank + ohw + 1).any()):
                    continue
                od, _ = seg_dist(pts, O)
                if (od < ohw + 1).any():
                    clash = True
                    break
            if clash:
                whys.add(CLASH)
                continue
            far = np.array([C + sign * (bank + reach) * N for sign in (-1, 1)] +
                           [C + sign * (hl + reach) * T for sign in (-1, 1)])
            safe = score > geo.detail_px and geo.bank_check(far[:, 0], far[:, 1], s)[0]
            if safe and straight:
                found = ford(k, a, C, T, acr)
                break
            if safe:
                bent = (dev, ford(k, a, C, T, acr, dev))
                continue
            rank = (0 if straight else 1, -score, dev)
            if marginal is None or rank < marginal[0]:
                marginal = (rank, ford(k, a, C, T, acr, None if straight else dev, score))
        if found is None:
            found = bent[1] if bent is not None else (marginal[1] if marginal is not None else None)
        if found:
            fords.append(found)
        else:
            reasons = sorted(whys) or ["no position in the interval"]
            skipped.append({"interval": k, "reason": reasons[0] if len(reasons) == 1 else "; ".join(reasons),
                            "reasons": reasons, "positions": tried})
    return fords, skipped


def build_scale(cfg, data, geo, s):
    """Every set of one map at scale s, as data (the emitter renders it)."""
    w = ww_cfg(cfg)
    np = _np()
    tol, keep = scale_cut(w, data, s)
    feats = []
    for r in data["rivers"][:keep]:
        hw = half_width(w, "river", s, river_class=r["class"])
        win, P, bend = shaped(w, r, "river", s, geo, tol)
        feats.append({"kind": "river", "id": r["id"], "name": r["name"], "class": r["class"], "hw": hw,
                      "depth": w["depth"]["river"], "window": win, "P": P, "bend": bend})
    for t in data["straits"]:
        hw = half_width(w, "strait", s, width_class=t["width_class"], real_km=t["real_width_km"])
        win, P, bend = shaped(w, t, "strait", s, geo, tol, hw)
        feats.append({"kind": "strait", "id": t["id"], "name": t["name"], "width_class": t["width_class"], "hw": hw,
                      "depth": w["depth"]["strait"], "window": win, "P": P, "bend": bend})
    for c in data["canals"]:
        hw = half_width(w, "canal", s, real_km=c["real_width_km"])
        win, P, bend = shaped(w, c, "canal", s, geo, tol, hw)
        feats.append({"kind": "canal", "id": c["id"], "name": c["name"], "hw": hw, "depth": w["depth"]["canal"],
                      "window": win, "P": P, "bend": bend})
    for d in data["dams"]:
        hw = half_width(w, "dam", s)
        _, P, bend = shaped(w, d, "dam", s, geo)
        feats.append({"kind": "dam", "id": d["id"], "name": d["name"], "canal": d["canal"], "hw": hw,
                      "window": None, "P": P, "bend": bend})
    half = w["basin_tiles"] / 2
    basins = []
    hw_at = {}
    for f in feats:
        if f["kind"] == "river":
            f["widths"], hw_at[f["id"]] = river_widths(w, f, s, geo)
            f["reach"] = max(f["widths"]) * (1 + w["natural"]["width"]["amplitude"]) + warp_reach(w, s)
        else:
            f["reach"] = f["hw"] + warp_reach(w, s, True)
    for f in feats:
        f["basins"] = []
        if f["kind"] == "dam":
            continue
        if f["bend"]["runs"] or f["bend"].get("smoothed_fails"):
            f["basins"] = basins_for(f["P"], f["bend"]["runs"], half, f["bend"].get("smoothed_fails", ()))
            f["bend"]["covered"] = basin_cover(f["P"], f["bend"]["runs"], f["basins"], half)
        if not f["basins"] and s in REQUIRED_BASINS.get(f["id"], ()):
            f["basins"] = [sharpest_centre(f["P"], w["bend"]["window_tiles"])]
            f["bend"]["required"] = True
        for b in f["basins"]:
            basins.append({"feature": f["id"], "kind": f["kind"], "centre": [round(b[0], 4), round(b[1], 4)],
                           "tangent": [round(v, 6) for v in course_tangent(f["P"], b)], "depth": f["depth"]})
    carved = [(f["P"], f["hw"]) for f in feats if f["kind"] != "dam"]
    for i, f in enumerate(feats):
        if f["kind"] != "river":
            f["fords"], f["fords_skipped"] = [], []
            continue
        others = [(o["P"], o["hw"], o["P"].min(0), o["P"].max(0)) for j, o in enumerate(feats)
                  if j != i and o["kind"] != "dam"]
        f["fords"], f["fords_skipped"] = place_fords(w, geo, s, f["P"], f["hw"], others, f["id"], hw_at[f["id"]])
    return {"scale": s, "features": feats, "basins": basins, "half_basin": half, "carved": carved,
            "tolerance_tiles": tol, "rivers_carved": keep, "rivers_listed": len(data["rivers"])}


# ------------------------------------------------------------------------------------------------ emitter

def f32(v):
    np = _np()
    return f"{float(np.float32(v)):.9g}"


def g9(v):
    return f"{float(v):.9g}"


def min_tree(items, k=MIN_ARGS):
    items = list(items)
    if not items:
        raise ValueError("min_tree of nothing")
    while len(items) > 1:
        items = [items[i] if len(items[i:i + k]) == 1 else "min(" + ", ".join(items[i:i + k]) + ")"
                 for i in range(0, len(items), k)]
    return items[0]


FRAMES = {"river": ("X", "Y"), "passage": ("XP", "YP")}


def seg_call(a, b, frame):
    """One segment's seg() in a frame's coordinates, or None for a zero-length segment."""
    (x0, y0), (x1, y1) = a, b
    ux, uy = x1 - x0, y1 - y0
    L2 = ux * ux + uy * uy
    if L2 < 1e-12:
        return None
    X, Y = FRAMES[frame]
    return f"seg({X}, {Y}, {g9(x0)}, {g9(y0)}, {g9(ux)}, {g9(uy)}, {f32(ux / L2)}, {f32(uy / L2)})"


def seg_calls(P, frame):
    calls = [seg_call(a, b, frame) for a, b in zip(P[:-1], P[1:])]
    return [c for c in calls if c]


def class_terms(groups, slope, floor=0.0):
    """One term per (half-width, depth, frame) class: max(depth, slope * (sqrt(min of squared distances) -
    hw)), a river's hw modulated by W and held at the floor (a class under the floor is a source's taper)."""
    terms = []
    for (hw, depth, frame), calls in sorted(groups.items()):
        width = g9(hw)
        if frame == "river":
            width = f"{g9(hw)} * W" if hw < floor else f"max({g9(floor)}, {g9(hw)} * W)"
        terms.append(f"max({g9(depth)}, {g9(slope)} * (sqrt({min_tree(calls)}) - {width}))")
    return terms


def render_sets(cfg, built):
    """The four expressions of one map and scale, and their statistics."""
    w = ww_cfg(cfg)
    slope = w["slope"]
    feats = built["features"]
    half = built["half_basin"]
    ww_groups, canal_groups, dam_calls = {}, {}, []
    counts = {"river": 0, "strait": 0, "canal": 0, "dam": 0}
    Bs = w["natural"]["basin"]
    floor = w["natural"]["width"]["floor_half_tiles"]
    for f in feats:
        frame = "river" if f["kind"] == "river" else "passage"
        calls = seg_calls(f["P"], frame)
        f["segments"] = len(calls)
        counts[f["kind"]] += len(calls)
        if f["kind"] == "dam":
            dam_calls.extend(calls)
            continue
        if f["kind"] == "river":
            for a, b, hw in zip(f["P"][:-1], f["P"][1:], f["widths"]):
                call = seg_call(a, b, frame)
                if call:
                    ww_groups.setdefault((round(hw, 4), f["depth"], frame), []).append(call)
            continue
        key = (round(f["hw"], 4), f["depth"], frame)
        (canal_groups if f["kind"] == "canal" else ww_groups).setdefault(key, []).extend(calls)
    # a turning basin is a short wide capsule along its course, in its feature's frame; a canal's turning
    # basins belong to the canal set, carved only with canals on: in the waterway set they would open the
    # isthmus the canal crosses with canals off
    for b in built["basins"]:
        (cx, cy), (tx, ty) = b["centre"], b["tangent"]
        reach = Bs["half_length_tiles"]
        frame = "river" if b["kind"] == "river" else "passage"
        call = seg_call((cx - tx * reach, cy - ty * reach), (cx + tx * reach, cy + ty * reach), frame)
        key = (float(Bs["radius_tiles"]), b["depth"], frame)
        (canal_groups if b["kind"] == "canal" else ww_groups).setdefault(key, []).append(call)
    ww_terms = class_terms(ww_groups, slope, floor)
    canal_terms = class_terms(canal_groups, slope, floor)
    ww = min_tree(ww_terms) if ww_terms else "inf"
    canals = min_tree(canal_terms) if canal_terms else "inf"
    if dam_calls:
        hwd = half_width(w, "dam", built["scale"])
        dams = f"{g9(slope)} * ({g9(hwd)} - sqrt({min_tree(dam_calls)}))"
    else:
        dams = "-inf"
    boxes = []
    for f in feats:
        for fd in f.get("fords", []):
            (cx, cy), (tx, ty) = fd["centre"], fd["tangent"]
            boxes.append(f"box(X, Y, {g9(cx)}, {g9(cy)}, {f32(tx)}, {f32(ty)}, {g9(fd['half_length'])}, "
                         f"{g9(fd['half_width'])})")
    if boxes:
        fords = f"if(max({min_tree(boxes)}, elevation) < 0, {g9(w['ford']['score'])}, -inf)"
    else:
        fords = "-inf"
    stats = {"segments": counts, "fords": len(boxes), "basins": len(built["basins"]),
             "classes": {"ww": len(ww_groups), "canals": len(canal_groups)}}
    return {"ww": ww, "canals": canals, "dams": dams, "fords": fords}, stats


def lua_string_lines(text, first_prefix, last_suffix, indent="  "):
    from build_geo import lua_string_lines as split_lines
    return split_lines(text, first_prefix, last_suffix, indent)


SEG_FN = ('{parameters = {"px", "py", "ax", "ay", "ux", "uy", "a", "b"}, expression = "ex * ex + ey * ey",\n'
          '  local_expressions = {dx = "px - ax", dy = "py - ay", t = "clamp(dx * a + dy * b, 0, 1)",\n'
          '                       ex = "dx - t * ux", ey = "dy - t * uy"}}')
BOX_FN = ('{parameters = {"px", "py", "cx", "cy", "tx", "ty", "hl", "hw"},\n'
          '  expression = "max(abs(dx * tx + dy * ty) - hl, abs(dy * tx - dx * ty) - hw)",\n'
          '  local_expressions = {dx = "px - cx", dy = "py - cy"}}')


def render_lua(cfg, map_key, s, exprs, stats, data_rel, data_sha):
    m = cfg["maps"][map_key]
    seg = stats["segments"]
    header = [f"Generated by tools/build_waterways.py (emitter {EMITTER_VERSION}) from {data_rel}",
              f"(sha256 {data_sha}) and config.lua's waterways group.",
              f"{m['display']} at scale {s}: {seg['river']} river, {seg['strait']} strait, {seg['canal']} canal and "
              f"{seg['dam']} dam segments,",
              f"{stats['fords']} fords, {stats['basins']} turning basins.",
              "Name-free data: waterways.lua binds the locals X, Y, XP, YP and W to the map's warped geo tiles.",
              "Never edit by hand: rerun the tool (plan hard rule 9)."]
    out = [f"-- {line}" for line in header]
    out.append("local F = {}")
    out += ("F.seg = " + SEG_FN).split("\n")
    out += ("F.box = " + BOX_FN).split("\n")
    out.append("local S = {functions = F}")
    for key in ("ww", "canals", "dams", "fords"):
        out += lua_string_lines(exprs[key], f"S.{key} = ", "")
    out.append(f"S.stats = {{rivers = {seg['river']}, straits = {seg['strait']}, canals = {seg['canal']}, "
               f"dams = {seg['dam']}, fords = {stats['fords']}, basins = {stats['basins']}}}")
    out.append("return S")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise ValueError(f"line of {len(line)} columns: {line[:60]!r}")
    return "\n".join(out) + "\n"


def file_name(map_key, s, version):
    return f"waterways_{map_key}_s{s}_v{version}.lua"


def load_data(map_key):
    p = DATA / f"{map_key}.json"
    if not p.exists():
        raise SystemExit(f"{p.relative_to(REPO).as_posix()} is missing: run `python tools/build_waterways.py import`")
    return json.loads(p.read_text(encoding="utf-8")), p


def poly_list(P):
    return [[round(float(x), 4), round(float(y), 4)] for x, y in P]


def feature_record(f, s, w):
    rec = {"kind": f["kind"], "id": f["id"], "name": f["name"], "hw_tiles": round(f["hw"], 4),
           "reach_tiles": round(f["reach"], 3), "segments": f["segments"], "window_tiles": f["window"],
           "polyline_geo": poly_list(f["P"]),
           "length_tiles": round(polyline_length(f["P"]), 3)}
    if f["kind"] != "dam":
        rec["depth"] = f["depth"]
        rec["bend"] = {"violations": f["bend"]["violations"], "worst_deg": f["bend"]["worst_deg"],
                       "basins": [[round(b[0], 4), round(b[1], 4)] for b in f.get("basins", [])],
                       "covered": f["bend"].get("covered", True)}
        if f["bend"].get("required"):
            rec["bend"]["required_basin"] = True
    if f["kind"] == "river":
        rec["class"] = f["class"]
        rec["width_tiles"] = class_width(w, f["class"], s)
        rec["half_widths"] = [round(float(min(f["widths"])), 4), round(float(max(f["widths"])), 4)]
        rec["fords"] = f["fords"]
        rec["fords_skipped"] = f["fords_skipped"]
        rec["fords_expected"] = int(polyline_length(f["P"]) // (w["ford"]["every_px"] * s))
    if f["kind"] == "strait":
        rec["width_class"] = f["width_class"]
    if f["kind"] == "dam":
        rec["canal"] = f["canal"]
    return rec


def emit_map(cfg, map_key, out_dir=GENERATED, manifest=True, scales=None):
    """Write the map's six generated files (and its manifest) and return the manifest record. The
    river-safe starts stay in the manifest's per-scale records only: no Lua file is emitted for them
."""
    w = ww_cfg(cfg)
    data, dp = load_data(map_key)
    data_sha = sha256_file(dp)
    data_rel = dp.relative_to(REPO).as_posix()
    geo = MapGeo(cfg, map_key)
    version = w["version"]
    rec = {"format": "tn-waterways-manifest/1", "tool": "tools/build_waterways.py", "emitter_version": EMITTER_VERSION,
           "map": map_key, "input": {"file": data_rel, "sha256": data_sha}, "coast_fit": geo.fit_land()[1],
           "config": {k: w[k] for k in sorted(w) if k != "sets"}, "scales": {}}
    starts = {}
    for s in scales or cfg["scales"]["values"]:
        built = build_scale(cfg, data, geo, s)
        exprs, stats = render_sets(cfg, built)
        text = render_lua(cfg, map_key, s, exprs, stats, data_rel, data_sha)
        name = file_name(map_key, s, version)
        write_text(Path(out_dir) / name, text)
        mask = corridor_mask(cfg, geo, built) if manifest else None
        srec = {"file": f"terra-nauvis/prototypes/generated/{name}", "sha256": sha256_bytes(text.encode("utf-8")),
                "bytes": len(text.encode("utf-8")), "stats": stats,
                "cut": {"tolerance_tiles": built["tolerance_tiles"], "rivers_carved": built["rivers_carved"],
                        "rivers_listed": built["rivers_listed"]},
                "features": [feature_record(f, s, w) for f in built["features"]],
                "basins": built["basins"]}
        if mask is not None:
            land, thin = geo.load()
            srec["t1_mask"] = {"pixels": int(mask.sum()), "share": round(float(mask.sum()) / mask.size, 6),
                               "thin_water_px": int(thin.sum()),
                               "thin_water_left_as_land_px": int((thin & ~mask).sum()),
                               "reference_land_carved_px": int((land & ~thin & mask).sum())}
        starts[s] = start_records(cfg, geo, built, map_key)
        if mask is not None:
            srec["starts"] = starts[s]
        rec["scales"][str(s)] = srec
    if manifest:
        write_json(DATA / f"manifest-{map_key}.json", rec)
    return rec


def check(cfg, maps):
    """T16: two emissions byte-identical to each other and to the committed files."""
    w = ww_cfg(cfg)
    fails = []
    with tempfile.TemporaryDirectory(prefix="tn-ww-") as td:
        for map_key in maps:
            runs = []
            for n in range(2):
                d = Path(td) / f"run{n}"
                emit_map(cfg, map_key, d, manifest=False)
                runs.append(d)
            for name in [file_name(map_key, s, w["version"]) for s in cfg["scales"]["values"]]:
                a, b = (runs[0] / name).read_bytes(), (runs[1] / name).read_bytes()
                committed = GENERATED / name
                if a != b:
                    fails.append(f"{name}: two emissions differ")
                if not committed.exists():
                    fails.append(f"{name}: no committed file")
                elif committed.read_bytes() != a:
                    fails.append(f"{name}: the committed file differs from a fresh emission (rerun build_waterways.py "
                                 f"emit)")
    return fails


# ------------------------------------------------------------------------------------------------ T1 masks

def corridor_mask(cfg, geo, built):
    """T1's corridor mask (U13): every reference pixel whose centre's tile lies inside a carve (within
    hw plus half a tile of a river, strait, canal or dam centreline, or inside a turning basin), so the
    carves never count against the coast's agreement; T5 judges them."""
    np = _np()
    s = built["scale"]
    ox, oy = geo.offset(s)
    mask = np.zeros((geo.H, geo.W), bool)
    for f in built["features"]:
        # the centreline in pixel-centre coordinates of the raster: u = (X - offset) / s - 0.5
        P = (np.asarray(f["P"], float) - [ox, oy]) / s - 0.5
        r = (f.get("reach", f["hw"]) + 0.5) / s
        band_into(mask, P, r)
    w = ww_cfg(cfg)
    for b in built["basins"]:
        cx, cy = (b["centre"][0] - ox) / s - 0.5, (b["centre"][1] - oy) / s - 0.5
        h = (built["half_basin"] + warp_reach(w, s) + 0.5) / s
        c0, c1 = max(int(math.ceil(cx - h)), 0), min(int(math.floor(cx + h)), geo.W - 1)
        r0, r1 = max(int(math.ceil(cy - h)), 0), min(int(math.floor(cy + h)), geo.H - 1)
        if c1 >= c0 and r1 >= r0:
            mask[r0:r1 + 1, c0:c1 + 1] = True
    return mask


def band_into(mask, P, r):
    """Set every pixel whose centre (col, row) lies within r of the polyline P (pixel units)."""
    np = _np()
    H, W = mask.shape
    for (x0, y0), (x1, y1) in zip(P[:-1], P[1:]):
        c0 = max(int(math.floor(min(x0, x1) - r)), 0)
        c1 = min(int(math.ceil(max(x0, x1) + r)), W - 1)
        r0 = max(int(math.floor(min(y0, y1) - r)), 0)
        r1 = min(int(math.ceil(max(y0, y1) + r)), H - 1)
        if c1 < c0 or r1 < r0:
            continue
        X, Y = np.meshgrid(np.arange(c0, c1 + 1, dtype=float), np.arange(r0, r1 + 1, dtype=float))
        ux, uy = x1 - x0, y1 - y0
        L2 = ux * ux + uy * uy
        t = np.clip(((X - x0) * ux + (Y - y0) * uy) / L2, 0, 1) if L2 > 0 else 0.0
        dx, dy = X - x0 - t * ux, Y - y0 - t * uy
        mask[r0:r1 + 1, c0:c1 + 1] |= (dx * dx + dy * dy) <= r * r


def mask_from_manifest(cfg, map_key, s):
    """T1's corridor mask of one map and scale from the committed manifest (the shipped polylines,
    half-widths and basins), the same pixels corridor_mask gives at emission, without re-smoothing.
    None when the map has no manifest."""
    np = _np()
    mp = DATA / f"manifest-{map_key}.json"
    if not mp.exists():
        return None
    M = json.loads(mp.read_text(encoding="utf-8"))
    rec = (M.get("scales") or {}).get(str(s))
    if rec is None:
        return None
    geo = MapGeo(cfg, map_key)
    feats = [{"P": np.asarray(f["polyline_geo"], float), "hw": f["hw_tiles"], "reach": f["reach_tiles"]}
             for f in rec["features"]]
    half = ww_cfg(cfg)["basin_tiles"] / 2
    built = {"scale": int(s), "features": feats, "basins": rec.get("basins", []), "half_basin": half}
    return corridor_mask(cfg, geo, built)


def mask_for(cfg, map_key, s):
    """(mask, built) of one map and scale, from the committed inputs (the T1 rows call this)."""
    data, _ = load_data(map_key)
    geo = MapGeo(cfg, map_key)
    built = build_scale(cfg, data, geo, s)
    render_sets(cfg, built)
    return corridor_mask(cfg, geo, built), built


# ------------------------------------------------------------------------------------------------ starts

def city_pixels(map_key):
    """{setting value: (name, col, row)} of the map's EarthMaps cities its spawn-city dropdown keeps."""
    J = json.loads((EARTHMAPS / f"{map_key}.json").read_text(encoding="utf-8"))
    A = json.loads(APPROVALS.read_text(encoding="utf-8"))
    kept = set(A["cities"][map_key]["kept"])
    out = {}
    for c in J["cities"]["list"]:
        if c["full_name"] not in kept:
            continue
        v = "-".join(x for x in "".join(ch if ch.isalnum() else " " for ch in c["name"].lower()).split())
        out[v] = (c["name"], int(c["pixel"][0]), int(c["pixel"][1]))
    return out


def start_records(cfg, geo, built, map_key):
    """River-safe starts (decision 18; TST-06): per city, the corridors within its start disc, and when one
    crosses the clear disc around the spawn, the nearest tile with clear_tiles of reference land and no
    corridor, and the bank half-planes for the start lake and starting ore. Half-planes are
    {nx, ny, c} with the spawn's side nx x + ny y + c >= 0, in world tiles of the moved spawn."""
    np = _np()
    w = ww_cfg(cfg)
    S = w["start"]
    s = built["scale"]
    clear, radius = S["clear_tiles"], S["radius_tiles"]
    carved = [(f["id"], f["kind"], f["P"], f["hw"]) for f in built["features"] if f["kind"] != "dam"]
    out = {}
    for value, (name, col, row) in sorted(city_pixels(map_key).items()):
        sx, sy = s * (col - geo.wr) + s // 2, s * (row - geo.hr) + s // 2
        near = []
        for fid, kind, P, hw in carved:
            d, _ = seg_dist(np.array([[sx, sy]], float), P)
            if d[0] - hw < radius:
                near.append((fid, kind, P, hw, float(d[0] - hw)))
        rec = {"name": name, "spawn_geo": [sx, sy], "corridors": [[n[0], round(n[4], 2)] for n in near]}
        crossing = [n for n in near if n[4] < clear]
        tx, ty = sx, sy
        if crossing:
            moved = nearest_clear(geo, s, sx, sy, [(n[2], n[3]) for n in near], clear)
            if moved is None:
                rec["move"] = None
                rec["move_failed"] = f"no tile within {int(radius)} tiles has {clear} clear tiles"
            else:
                tx, ty = moved
                rec["move"] = [tx - sx, ty - sy]
        else:
            rec["move"] = [0, 0]
        banks = []
        for fid, kind, P, hw, _ in near:
            d, foot = seg_dist(np.array([[tx, ty]], float), P)
            Q, T, _ = point_at(P, float(foot[0]))
            n = np.array([-T[1], T[0]])
            if float(n @ (np.array([tx, ty], float) - Q)) < 0:
                n = -n
            # world = geo - spawn: the half-plane n . (world + spawn - Q) >= 0
            c = float(n @ (np.array([tx, ty], float) - Q))
            banks.append({"corridor": fid, "nx": round(float(n[0]), 6), "ny": round(float(n[1]), 6),
                          "c": round(c, 3), "distance_tiles": round(float(d[0]), 2)})
        rec["banks"] = banks
        out[value] = rec
    return out


def nearest_clear(geo, s, sx, sy, corridors, clear, reach=150):
    """The nearest integer geo tile to (sx, sy), by distance then by angle, on reference land (thin water
    counted as land) with no corridor band within `clear` tiles. Sea and lakes near the spawn are the
    start land guarantee's (spawn-cities: land within its radius of the spawn, which moves with it), so
    only the carves, which cut through the guarantee, keep a spawn off a tile."""
    np = _np()
    offs = []
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            r2 = dx * dx + dy * dy
            if r2 <= reach * reach:
                offs.append((r2, math.atan2(dy, dx), dx, dy))
    offs.sort()
    for _, _, dx, dy in offs:
        tx, ty = sx + dx, sy + dy
        if not geo.fit_land_at_geo(np.array([tx], float), np.array([ty], float), s).all():
            continue
        ok = True
        for P, hw in corridors:
            d, _ = seg_dist(np.array([[tx, ty]], float), P)
            if d[0] - hw < clear:
                ok = False
                break
        if ok:
            return tx, ty
    return None


# ------------------------------------------------------------------------------------------------ JI-03

def river_findings(cfg):
    """T16 (JI-03): each map's rivers in data-src/waterways/<map>.json equal APPROVALS 7's adopted rows of
    approvals-data.json, in order and with their class (a river leaves only from the bottom, each
    through a the design notes entry: then the kept list is a prefix of the adopted rows), and Europe keeps
    all 22."""
    A = json.loads(APPROVALS.read_text(encoding="utf-8"))
    out = []
    for key in tnconfig.map_keys(cfg):
        p = DATA / f"{key}.json"
        if not p.exists():
            out.append(f"data-src/waterways/{key}.json is missing")
            continue
        D = json.loads(p.read_text(encoding="utf-8"))
        want = [(r["name"], r["class"]) for r in A["rivers"][key] if r["adopted"]]
        have = [(r["name"], r["class"]) for r in D["rivers"]]
        if have != want[:len(have)]:
            out.append(f"{key}: the rivers {have} are not APPROVALS 7's adopted rows {want} in order with their class")
        if len(have) < len(want):
            cut = [n for n, _ in want[len(have):]]
            out.append(f"{key}: rivers {cut} are cut from the bottom; each needs its DECISIONS.md entry (checked by "
                       f"review)")
        europe = [r["name"] for r in A["rivers"][key] if r["adopted"] and r["block"] == "europe"]
        lost = [n for n in europe if n not in {r["name"] for r in D["rivers"]}]
        if lost:
            out.append(f"{key}: Europe's rivers {lost} are missing (never one of Europe's 22)")
    return out


# ------------------------------------------------------------------------------------------------ offline T5

def tile_window(polys, pad):
    np = _np()
    allp = np.concatenate([np.asarray(P, float) for P in polys])
    x0, y0 = np.floor(allp.min(0) - pad).astype(int)
    x1, y1 = np.ceil(allp.max(0) + pad).astype(int)
    return int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1)


def raster_water(geo, s, x0, y0, w_, h_, features, basins, half, canals_on=True, dams=True):
    """Water at tile resolution in a window, offline: the coast fit's target water (reference water,
    thin water filled) minus dams, plus every carve band, the open canals and the basins; a stand-in
    for the generated tiles (T5 in the game is the judge)."""
    np = _np()
    X, Y = np.meshgrid(np.arange(x0, x0 + w_, dtype=float), np.arange(y0, y0 + h_, dtype=float))
    water = ~geo.fit_land_at_geo(X, Y, s)
    if dams:
        for f in features:
            if f["kind"] == "dam" and not canals_on:
                water &= ~band_tiles(X, Y, f["P"], f["hw"])
    for f in features:
        if f["kind"] in ("river", "strait") or (f["kind"] == "canal" and canals_on):
            water |= band_tiles(X, Y, f["P"], f["hw"])
    for b in basins:
        water |= np.hypot(X - b["centre"][0], Y - b["centre"][1]) < half
    return water


def band_tiles(X, Y, P, hw):
    np = _np()
    out = np.zeros(X.shape, bool)
    for (x0, y0), (x1, y1) in zip(P[:-1], P[1:]):
        ux, uy = x1 - x0, y1 - y0
        L2 = ux * ux + uy * uy
        if L2 == 0:
            continue
        t = np.clip(((X - x0) * ux + (Y - y0) * uy) / L2, 0, 1)
        dx, dy = X - x0 - t * ux, Y - y0 - t * uy
        out |= (dx * dx + dy * dy) < hw * hw
    return out


def offline(cfg, maps, scales):
    """Offline T5 pre-checks of the emitted sets (a 7 or 11-tile square from end to end of every river,
    strait and open canal; fords present; bend rule covered by basins), on a raster stand-in."""
    from earthmaps_decode import fits_square
    import nav
    np = _np()
    w = ww_cfg(cfg)
    report = {}
    for map_key in maps:
        data, _ = load_data(map_key)
        geo = MapGeo(cfg, map_key)
        for s in scales:
            built = build_scale(cfg, data, geo, s)
            render_sets(cfg, built)
            rows = []
            for f in built["features"]:
                if f["kind"] == "dam":
                    continue
                k = w["two_way_tiles"] if f.get("width_class") == "two_way" else w["floor_tiles"]
                x0, y0, ww_, hh = tile_window([f["P"]], f["hw"] + 40)
                if ww_ * hh > 60_000_000:
                    rows.append({"id": f["id"], "skipped": f"window {ww_} x {hh} too large offline"})
                    continue
                water = raster_water(geo, s, x0, y0, ww_, hh, built["features"], built["basins"],
                                     built["half_basin"])
                a = (int(round(f["P"][0][1])) - y0, int(round(f["P"][0][0])) - x0)
                b = (int(round(f["P"][-1][1])) - y0, int(round(f["P"][-1][0])) - x0)
                ok = nav.connected_disc(water, a, b, k)
                rows.append({"id": f["id"], "kind": f["kind"], "square": k, "connected": bool(ok),
                             "fords": len(f.get("fords", [])),
                             "fords_expected": int(polyline_length(f["P"]) // (w["ford"]["every_px"] * s))
                             if f["kind"] == "river" else 0,
                             "bend_ok": f["bend"]["violations"] == 0 or f["bend"].get("covered", False)})
            report[f"{map_key}@{s}"] = rows
            bad = [r for r in rows if not r.get("connected", True) or not r.get("bend_ok", True)]
            print(f"{map_key} scale {s}: {len(rows)} features, {len(bad)} failing offline "
                  f"{[r['id'] for r in bad]}", flush=True)
    return report


# ------------------------------------------------------------------------------------------------ cuts

def propose_cuts(cfg, maps, base, target, coef):
    """The plan's waterway cut order (section 6.3) per map and scale against a Tile target: the
    tolerance first, in whole tiles from config.lua's up to one reference pixel (s tiles, the level
    ARCHITECTURE.md's cut order names for Alien Biomes worlds), then rivers out from the bottom of the
    list down to Europe's 22, with Tile estimated as base + seg * segments + ford * fords + basin *
    basins (coefficients fitted to measured 64 px --verbose previews). Proposes; writes nothing."""
    w = ww_cfg(cfg)
    out = {}
    for map_key in maps:
        data, _ = load_data(map_key)
        geo = MapGeo(cfg, map_key)
        floor = sum(1 for r in data["rivers"] if r["block"] == "europe")
        out[map_key] = {}
        for s in cfg["scales"]["values"]:
            b = base[map_key][str(s)]
            lim = target[map_key]
            t0 = w["tolerance_tiles"][s - 1]
            tols = [t0] + [float(x) for x in range(int(t0) + 1, s + 1)]
            chosen, tried = None, []
            ladder = [(t_, len(data["rivers"])) for t_ in tols] +                      [(tols[-1], n) for n in range(len(data["rivers"]) - 1, floor - 1, -1)]
            for t_, n in ladder:
                d2 = dict(data, cuts={str(s): {"tolerance_tiles": t_, "rivers": n}})
                built = build_scale(cfg, d2, geo, s)
                _, st = render_sets(cfg, built)
                seg = st["segments"]["river"] + st["segments"]["strait"] + st["segments"]["canal"]
                est = b + coef["seg"] * seg + coef["ford"] * st["fords"] + coef["basin"] * st["basins"]
                tried.append({"tolerance_tiles": t_, "rivers": n, "segments": seg, "fords": st["fords"],
                              "estimate": round(est)})
                if est <= lim:
                    chosen = tried[-1]
                    break
            out[map_key][str(s)] = {"limit": lim, "base": b, "chosen": chosen, "tried": tried}
            print(map_key, s, "chosen", chosen, flush=True)
    return out


# ------------------------------------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("import", "emit", "check"):
        p = sub.add_parser(name)
        p.add_argument("--map")
    sub.add_parser("rivers")
    p = sub.add_parser("mask")
    p.add_argument("--map", required=True)
    p.add_argument("--scale", type=int, required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("offline")
    p.add_argument("--map")
    p.add_argument("--scale", type=int)
    p.add_argument("--out")
    p = sub.add_parser("cuts")
    p.add_argument("--map")
    p.add_argument("--model", required=True, help="JSON {base: {map: {scale: tile}}, target: {map: tile}, "
                                                    "coef: {seg, ford, basin}}")
    p.add_argument("--out")
    a = ap.parse_args(argv)
    cfg = load_cfg()
    if a.cmd == "import":
        for key in map_keys(cfg, a.map):
            print(json.dumps(import_map(key)))
        write_provenance(cfg)
        print("RESULT ok import")
        return 0
    if a.cmd == "emit":
        for key in map_keys(cfg, a.map):
            rec = emit_map(cfg, key)
            print(json.dumps({"map": key, "scales": {s: r["stats"] for s, r in rec["scales"].items()}}))
        write_provenance(cfg)
        print("RESULT ok emit")
        return 0
    if a.cmd == "check":
        fails = check(cfg, map_keys(cfg, a.map))
        for f in fails:
            print("FAIL", f)
        print(f"RESULT {'ok' if not fails else 'FAIL'} check fails={len(fails)}")
        return 0 if not fails else 1
    if a.cmd == "rivers":
        fails = river_findings(cfg)
        for f in fails:
            print("FAIL", f)
        print(f"RESULT {'ok' if not fails else 'FAIL'} rivers fails={len(fails)}")
        return 0 if not fails else 1
    if a.cmd == "mask":
        from PIL import Image
        mask, _ = mask_for(cfg, a.map, a.scale)
        Image.fromarray((mask * 255).astype("uint8")).save(a.out)
        print(f"RESULT ok mask pixels={int(mask.sum())} share={float(mask.sum()) / mask.size:.6f}")
        return 0
    if a.cmd == "cuts":
        M = json.loads(Path(a.model).read_text(encoding="utf-8"))
        rep = propose_cuts(cfg, map_keys(cfg, a.map), M["base"], M["target"], M["coef"])
        if a.out:
            write_json(Path(a.out), rep)
        print("RESULT ok cuts")
        return 0
    if a.cmd == "offline":
        rep = offline(cfg, map_keys(cfg, a.map), [a.scale] if a.scale else cfg["scales"]["values"])
        if a.out:
            write_json(Path(a.out), rep)
        bad = sum(1 for rows in rep.values() for r in rows if not r.get("connected", True) or not r.get("bend_ok", True))
        print(f"RESULT {'ok' if not bad else 'FAIL'} offline failing={bad}")
        return 0 if not bad else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
