#!/usr/bin/env python3
"""T5 navigability and T6 ridge-wall flood fills over tiles and cliffs dumped by mods/ep-s8-dump.

T5 water: water = tiles whose collision mask has the water_tile layer (Cargo Ships waterways need
it; R4). A channel of width k exists between A and B when a k x k all-water square can travel from a
placement covering A to one covering B in 4-connected steps. Reports connectivity at --width and the
largest passable width.

T6 walk: the character is blocked where its box (half-size 0.2 tiles) touches a cliff's collision box
(each cliff's dumped bounding_box, oriented when the game says so) or where its centre stands on a tile
with the player collision layer (deep water, water, out-of-map). The free space is a lattice of
--lattice cells per tile. Reports whether A and B connect, the widest square (in tiles) that can
travel between them (rail width check), and the same with --block rectangles closed (to show that
two sides of a range connect only through the named passes).

Commands (from the Factorio workspace):
  python mod/tools/nav.py water <dump.json> --a x,y --b x,y [--width 7] [--area 0]
  python mod/tools/nav.py water <dump.json> --a x,y --to-border [--width 7]
  python mod/tools/nav.py walk <dump.json> --a x,y --b x,y [--width 2] [--block x0,y0,x1,y1 ...] [--png walk.png]
  python mod/tools/nav.py cliff-check <dump.json>     (cliff geometry against the game's own rasters)
  python mod/tools/nav.py selftest
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import dump_render as dr  # noqa: E402
from earthmaps_decode import fits_square, label_runs  # noqa: E402
from t1_metrics import row_runs_lowmem  # noqa: E402

CHAR_HALF = 0.2  # base character collision_box {{-0.2, -0.2}, {0.2, 0.2}}; matched the game's rasters (cliff-check)


# ------------------------------------------------------------------------------------------------
# Labels and passable widths

def labels(mask, conn=4):
    """Dense int32 label image (-1 = background) from run-length components."""
    H, W = mask.shape
    rows, s, e = row_runs_lowmem(mask)
    comp, n = label_runs(rows, s, e, H, conn)
    lab = np.full(H * W, -1, np.int32)
    if rows.size:
        length = e - s + 1
        start = rows * W + s
        pos = np.repeat(start - np.cumsum(length) + length, length) + np.arange(int(length.sum()))
        lab[pos] = np.repeat(comp.astype(np.int32), length)
    return lab.reshape(H, W), n


def placements_covering(lab, r, c, k):
    """Labels of k x k placements (top-left indexed) whose square covers cell (r, c)."""
    sub = lab[max(r - k + 1, 0):r + 1, max(c - k + 1, 0):c + 1]
    return set(sub[sub >= 0].tolist())


def connected_at(mask, a, b, k, to_border=False):
    """True when a k x k square of mask can move from covering cell a to covering cell b (or to any
    placement touching the mask border when to_border)."""
    f = fits_square(mask, k)
    if f.size == 0:
        return False
    lab, _ = labels(f)
    la = placements_covering(lab, a[0], a[1], k)
    if not la:
        return False
    if to_border:
        edge = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
        edge.discard(-1)
        return bool(la & edge)
    return bool(la & placements_covering(lab, b[0], b[1], k))


def disc_offsets(r):
    """The cells of a disc of radius r about the origin (r = 3 holds 29 cells)."""
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dy * dy + dx * dx <= r * r]


def erode_disc(mask, r):
    """Cells whose whole disc of radius r lies in mask (cells within r of the edge drop out)."""
    H, W = mask.shape
    out = np.zeros((H, W), bool)
    if r <= 0:
        return mask.astype(bool).copy()
    if H <= 2 * r or W <= 2 * r:
        return out
    core = np.ones((H - 2 * r, W - 2 * r), bool)
    for dy, dx in disc_offsets(r):
        core &= mask[r + dy:H - r + dy, r + dx:W - r + dx]
    out[r:H - r, r:W - r] = core
    return out


def disc_cover(lab, cell, r):
    """Labels of the eroded cells whose disc of radius r covers `cell`."""
    rr, cc = cell
    out = set()
    for dy, dx in disc_offsets(r):
        y, x = rr + dy, cc + dx
        if 0 <= y < lab.shape[0] and 0 <= x < lab.shape[1] and lab[y, x] >= 0:
            out.add(int(lab[y, x]))
    return out


def connected_disc(mask, a, b, width, to_border=False):
    """S4's channel test (T5 for waterways): a disc of diameter `width` (radius (width - 1) // 2) can
    travel from a placement covering cell a to one covering cell b (or to the mask border when
    to_border), so the channel is `width` tiles wide at any heading. S4 eroded the water by a disc of
    radius 3 and flood-filled from the inland end; the disc steps between valid centres 8-connected,
    because a band holding exactly `width` tiles per row erodes to a core one cell wide that shifts
    diagonally where the band does (Old World's Yenisei at scale 1). An axis-aligned k x k square
    (connected_at) needs a channel k times the square root of 2 wide on a diagonal."""
    r = max((int(width) - 1) // 2, 0)
    e = erode_disc(mask, r)
    if not e.any():
        return False
    lab, _ = labels(e, conn=8)
    la = disc_cover(lab, a, r)
    if not la:
        return False
    if to_border:
        H, W = lab.shape
        edge = (set(lab[r, :].tolist()) | set(lab[H - 1 - r, :].tolist()) | set(lab[:, r].tolist()) |
                set(lab[:, W - 1 - r].tolist()))
        edge.discard(-1)
        return bool(la & edge)
    return bool(la & disc_cover(lab, b, r))


def max_passable(mask, a, b, kmax, to_border=False):
    """Largest k <= kmax with connected_at true (connectivity is monotone in k); 0 if none."""
    if not connected_at(mask, a, b, 1, to_border):
        return 0
    lo, hi = 1, kmax
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if connected_at(mask, a, b, mid, to_border):
            lo = mid
        else:
            hi = mid - 1
    return lo


# ------------------------------------------------------------------------------------------------
# Geometry

def sat_blocked(poly, X, Y, half):
    """Axis-aligned squares of half-size `half` centred on (X, Y) intersect the convex polygon."""
    P = np.asarray(poly, float)
    hit = (X - half <= P[:, 0].max()) & (X + half >= P[:, 0].min()) & \
          (Y - half <= P[:, 1].max()) & (Y + half >= P[:, 1].min())
    n = len(P)
    for i in range(n):
        ex, ey = P[(i + 1) % n] - P[i]
        nx, ny = -ey, ex
        L = math.hypot(nx, ny)
        if L == 0:
            continue
        nx, ny = nx / L, ny / L
        proj = P[:, 0] * nx + P[:, 1] * ny
        q = X * nx + Y * ny
        r = half * (abs(nx) + abs(ny))
        hit &= (q - r <= proj.max() + 1e-9) & (q + r >= proj.min() - 1e-9)
    return hit


def cliff_raster(area, x0, y0, w, h, n, half=0.0, sign=1.0):
    """Lattice (h*n, w*n): cells whose centre-square (half-size `half`) touches a cliff box."""
    out = np.zeros((h * n, w * n), bool)
    names = [e["name"] for e in dr.as_list(area.get("entity_names"))]
    for c in dr.as_list(area.get("cliffs")):
        _, cx, cy, _, ltx, lty, rbx, rby, bo = c
        poly = dr.box_corners((ltx, lty), (rbx, rby), bo, sign=sign)
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        c0 = max(int(math.floor((min(xs) - half - x0) * n)) - 1, 0)
        c1 = min(int(math.ceil((max(xs) + half - x0) * n)) + 1, w * n)
        r0 = max(int(math.floor((min(ys) - half - y0) * n)) - 1, 0)
        r1 = min(int(math.ceil((max(ys) + half - y0) * n)) + 1, h * n)
        if c1 <= c0 or r1 <= r0:
            continue
        X, Y = np.meshgrid(x0 + (np.arange(c0, c1) + 0.5) / n, y0 + (np.arange(r0, r1) + 0.5) / n)
        out[r0:r1, c0:c1] |= sat_blocked(poly, X, Y, half)
    del names
    return out


def tile_mask(area, layer):
    names, idx = dr.decode_tiles(area)
    L = dr.tile_layers(area)
    hit = [i for i, nm in enumerate(names) if layer in L.get(nm, set())]
    return np.isin(idx, hit)


def parse_xy(text):
    x, y = (float(v) for v in text.split(","))
    return x, y


# ------------------------------------------------------------------------------------------------
# Commands

def water_report(area, a_xy, b_xy, width, kmax, to_border):
    a = area["area"]
    water = tile_mask(area, "water_tile")
    ca = (int(math.floor(a_xy[1] - a["y0"])), int(math.floor(a_xy[0] - a["x0"])))
    cb = None if b_xy is None else (int(math.floor(b_xy[1] - a["y0"])), int(math.floor(b_xy[0] - a["x0"])))
    for name, cell in (("a", ca), ("b", cb)):
        if cell is not None and not (0 <= cell[0] < water.shape[0] and 0 <= cell[1] < water.shape[1]):
            raise SystemExit(f"RESULT fail point {name} lies outside the dumped area")
    rep = {"check": "T5 water channel", "area": a, "a": list(a_xy), "b": list(b_xy) if b_xy else None,
           "to_border": to_border, "a_is_water": bool(water[ca]), "b_is_water": bool(water[cb]) if cb else None,
           "water_tiles": int(water.sum())}
    rep["connected_width_1"] = connected_at(water, ca, cb, 1, to_border)
    if width:
        rep["width"] = width
        rep["connected_at_width"] = connected_at(water, ca, cb, int(width), to_border)
    rep["max_passable_width_tiles"] = max_passable(water, ca, cb, kmax, to_border)
    rep["max_searched"] = kmax
    return rep


def cmd_water(a):
    dump = dr.load_json(a.dump)
    rep = water_report(dump["areas"][a.area], parse_xy(a.a), parse_xy(a.b) if a.b else None, a.width, a.kmax,
                       a.to_border)
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    ok = rep["connected_at_width"] if a.width else rep["connected_width_1"]
    print(f"RESULT {'ok' if ok else 'fail'} water connected_width_1={rep['connected_width_1']} "
          f"connected_at_width={rep.get('connected_at_width')} max_width={rep['max_passable_width_tiles']}")
    return 0 if ok else 1


def walk_free(area, n, blocks=()):
    a = area["area"]
    x0, y0, w, h = a["x0"], a["y0"], a["w"], a["h"]
    blocked = cliff_raster(area, x0, y0, w, h, n, half=CHAR_HALF)
    tiles_block = tile_mask(area, "player")
    blocked |= np.repeat(np.repeat(tiles_block, n, axis=0), n, axis=1)
    for bx0, by0, bx1, by1 in blocks:
        c0, c1 = int(math.floor((bx0 - x0) * n)), int(math.ceil((bx1 - x0) * n))
        r0, r1 = int(math.floor((by0 - y0) * n)), int(math.ceil((by1 - y0) * n))
        blocked[max(r0, 0):max(r1, 0), max(c0, 0):max(c1, 0)] = True
    return ~blocked


def walk_report(area, a_xy, b_xy, n, width, wmax, blocks=()):
    a = area["area"]
    free = walk_free(area, n, blocks)
    cell = lambda p: (int(math.floor((p[1] - a["y0"]) * n)), int(math.floor((p[0] - a["x0"]) * n)))  # noqa: E731
    ca, cb = cell(a_xy), cell(b_xy)
    lab, ncomp = labels(free)
    rep = {"check": "T6 walkability", "area": a, "lattice_per_tile": n, "character_half_size": CHAR_HALF,
           "a": list(a_xy), "b": list(b_xy), "blocks": [list(b) for b in blocks],
           "cliffs": len(dr.as_list(area.get("cliffs"))), "free_components": int(ncomp),
           "a_free": bool(free[ca]), "b_free": bool(free[cb]),
           "connected": bool(free[ca] and free[cb] and lab[ca] == lab[cb])}
    kmax = int(round(wmax * n))
    k = max_passable(free, ca, cb, kmax)
    rep["max_passable_width_tiles"] = round(k / n, 4)
    rep["max_passable_note"] = ("widest square (side in tiles, lattice resolution) that travels from A to B "
                                "through the free space; the character body is already subtracted around cliffs")
    if width:
        rep["width"] = width
        rep["connected_at_width"] = connected_at(free, ca, cb, int(round(width * n)))
    return rep, free, lab


def cmd_walk(a):
    dump = dr.load_json(a.dump)
    area = dump["areas"][a.area]
    blocks = [tuple(float(v) for v in b.split(",")) for b in (a.block or [])]
    rep, free, lab = walk_report(area, parse_xy(a.a), parse_xy(a.b), a.lattice, a.width, a.wmax, blocks)
    if a.png:
        img = np.where(free[..., None], np.array([200, 200, 190], np.uint8), np.array([60, 35, 15], np.uint8))
        Image.fromarray(img.astype(np.uint8)).save(a.png)
        rep["png"] = a.png
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(f"RESULT ok walk connected={rep['connected']} max_width={rep['max_passable_width_tiles']} "
          f"connected_at_width={rep.get('connected_at_width')} cliffs={rep['cliffs']} components={rep['free_components']}")
    return 0


def cliff_check(dump):
    """Compare the cliff model with the game's own rasters from the dump's cliff scene:
    point-in-box against find_entities_filtered{position}, box grown by the character against
    can_place_entity{name = "character"}. Tries both rotation senses for oriented boxes."""
    rows = []
    tot = {+1.0: [0, 0, 0, 0, 0], -1.0: [0, 0, 0, 0, 0]}
    for s in dump.get("scene") or []:
        L = s["lattice"]
        n, nx, ny, lx0, ly0 = L["n"], L["nx"], L["ny"], L["x0"], L["y0"]
        occ = np.array([[ch == "1" for ch in r] for r in s["cliff_at_point"]])
        chr_ = np.array([[ch == "1" for ch in r] for r in s["character_blocked"]])
        ltx, lty, rbx, rby, bo = s["bounding_box"]
        area = {"entity_names": [{"name": "cliff", "type": "cliff"}],
                "cliffs": [[0, s["x"], s["y"], s["orientation"], ltx, lty, rbx, rby, bo]]}
        rec = {"orientation": s["orientation"], "box_orientation": bo}
        for sign in (+1.0, -1.0):
            mo = cliff_raster(area, lx0, ly0, nx // n, ny // n, n, half=0.0, sign=sign)
            mc = cliff_raster(area, lx0, ly0, nx // n, ny // n, n, half=CHAR_HALF, sign=sign)
            # Lattice points lying on a box edge (the 45-degree boxes pass through them) are ties that
            # the game and the model may break differently; count mismatches away from any edge.
            poly = dr.box_corners((ltx, lty), (rbx, rby), bo, sign=sign)
            rr, cc = np.nonzero(mo != occ)
            off_edge = int((edge_distance(poly, lx0 + (cc + 0.5) / n, ly0 + (rr + 0.5) / n) > 0.01).sum())
            rec[f"sign{int(sign):+d}"] = {"point_mismatch": int((mo != occ).sum()), "point_mismatch_off_edge": off_edge,
                                          "character_mismatch": int((mc != chr_).sum()), "cells": int(occ.size)}
            t = tot[sign]
            t[0] += int((mo != occ).sum())
            t[1] += int((mc != chr_).sum())
            t[2] += int(occ.size)
            t[3] += int(occ.sum())
            t[4] += off_edge
        rows.append(rec)
    best = min(tot, key=lambda k: tot[k][4] + tot[k][1])
    return {"cliffs": len(rows), "per_orientation": rows,
            "totals": {f"sign{int(k):+d}": {"point_mismatch": v[0], "point_mismatch_off_edge": v[4],
                                            "character_mismatch": v[1], "cells": v[2], "cliff_cells": v[3]}
                       for k, v in tot.items()},
            "best_sign": best,
            "note": "point = find_entities_filtered{position, type = cliff}; character = not can_place_entity"
                    "{name = character}; sign +1 = clockwise on screen (y down) about the box centre"}


def edge_distance(poly, xs, ys):
    """Distance from points to the polygon boundary."""
    d = np.full(np.shape(xs), np.inf)
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        vx, vy = bx - ax, by - ay
        t = np.clip(((xs - ax) * vx + (ys - ay) * vy) / max(vx * vx + vy * vy, 1e-12), 0, 1)
        d = np.minimum(d, np.hypot(xs - (ax + t * vx), ys - (ay + t * vy)))
    return d


def cmd_cliff_check(a):
    rep = cliff_check(dr.load_json(a.dump))
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    t = rep["totals"][f"sign{int(rep['best_sign']):+d}"]
    ok = t["point_mismatch_off_edge"] == 0 and t["character_mismatch"] == 0
    print(f"RESULT {'ok' if ok else 'fail'} cliff-check cliffs={rep['cliffs']} best_sign={rep['best_sign']:+.0f} "
          f"character_mismatch={t['character_mismatch']} point_mismatch={t['point_mismatch']} "
          f"point_mismatch_off_edge={t['point_mismatch_off_edge']} of {t['cells']} cells")
    return 0


# ------------------------------------------------------------------------------------------------
# Self-tests

# ------------------------------------------------------------------------------------------------
# Waterways (milestone waterways): the corridor raster from ea-ww-probe's chunk dumps, fords and widths

def chunk_raster(dump):
    """(names, layers, idx, x0, y0) from an ea-ww-probe tiles dump: the tiles of every dumped chunk
    placed in their bounding box (tile index -1 where no chunk was dumped), so T5 rebuilds S4's
    corridor raster from the chunks along a waterway alone."""
    pal = dump["palette"]
    names = [p["name"] for p in pal]
    layers = {p["name"]: set(p.get("layers") or []) for p in pal}
    cs = [(c[0], c[1]) for c in dump["chunks"]]
    if not cs:
        raise SystemExit("RESULT fail the dump holds no chunk")
    cx0, cy0 = min(c[0] for c in cs), min(c[1] for c in cs)
    cx1, cy1 = max(c[0] for c in cs), max(c[1] for c in cs)
    idx = np.full(((cy1 - cy0 + 1) * 32, (cx1 - cx0 + 1) * 32), -1, np.int32)
    for cx, cy, rows, *_ in dump["chunks"]:
        r0, c0 = (cy - cy0) * 32, (cx - cx0) * 32
        for j, row in enumerate(rows):
            x = c0
            for part in row.split():
                i, n = (int(v) for v in part.split("*"))
                idx[r0 + j, x:x + n] = i
                x += n
    return names, layers, idx, cx0 * 32, cy0 * 32


def layer_mask(names, layers, idx, layer):
    hit = [i for i, nm in enumerate(names) if layer in layers.get(nm, set())]
    return np.isin(idx, hit)


def name_mask(names, idx, wanted):
    hit = [i for i, nm in enumerate(names) if nm in wanted]
    return np.isin(idx, hit)


def to_cell(x0, y0, p):
    return int(math.floor(p[1] - y0)), int(math.floor(p[0] - x0))


def ford_report(names, layers, idx, x0, y0, centre, tangent, half_length, half_width, bank=6, square=7,
                shallow=("water-shallow",), ends=None, path=None):
    """T5 at one ford: a character walks from one bank to the other through the
    dumped tiles (tiles with the player layer block it, as in the game); counted as water, the ford's
    shallow tiles block the same walk (the positive control: the reach is a barrier but for the ford);
    the shallow run along the centreline through the ford (its length: `path`, the river's own
    centreline sampled every tile through the ford, or the tangent line's points when not given) and
    the shallow-or-land run across it (it spans the river); and a square of side `square` travels
    through the ford along the river on tiles with water_tile (ships pass; fords count), between `ends`,
    two points on the river's centreline beyond the ford (the tangent line's points when not given: on
    a bend they leave the carve)."""
    cx, cy = centre
    tx, ty = tangent
    nx, ny = -ty, tx
    blocked = layer_mask(names, layers, idx, "player") | (idx < 0)
    shal = name_mask(names, idx, set(shallow))
    water = layer_mask(names, layers, idx, "water_tile")
    reach = half_width + bank
    a = (cx + nx * reach, cy + ny * reach)
    b = (cx - nx * reach, cy - ny * reach)
    ca, cb = to_cell(x0, y0, a), to_cell(x0, y0, b)
    H, W = idx.shape
    inside = all(0 <= c[0] < H and 0 <= c[1] < W for c in (ca, cb))
    rep = {"centre": [cx, cy], "banks": [list(a), list(b)], "banks_inside": inside}
    if not inside:
        rep["crosses"] = rep["control_crosses"] = False
        return rep
    free = ~blocked
    lab, _ = labels(free)
    rep["bank_tiles_free"] = [bool(free[ca]), bool(free[cb])]
    rep["crosses"] = bool(free[ca] and free[cb] and lab[ca] == lab[cb])
    free2 = free & ~shal
    lab2, _ = labels(free2)
    rep["control_crosses"] = bool(free2[ca] and free2[cb] and lab2[ca] == lab2[cb])
    # the shallow run along the centreline and the crossing line's tiles
    run = 0
    line = path if path is not None else \
        [(cx + tx * k, cy + ty * k) for k in range(-int(half_length) - 6, int(half_length) + 7)]
    for p in line:
        r, c = to_cell(x0, y0, p)
        if 0 <= r < H and 0 <= c < W and shal[r, c]:
            run += 1
    rep["length_tiles"] = run
    rep["length_along"] = "centreline" if path is not None else "tangent"
    across_blocking = 0
    for k in range(-int(reach), int(reach) + 1):
        r, c = to_cell(x0, y0, (cx + nx * k, cy + ny * k))
        if 0 <= r < H and 0 <= c < W and blocked[r, c]:
            across_blocking += 1
    rep["blocking_tiles_across"] = across_blocking
    rep["spans"] = across_blocking == 0
    if ends is not None:
        up, down = to_cell(x0, y0, ends[0]), to_cell(x0, y0, ends[1])
    else:
        up = to_cell(x0, y0, (cx - tx * (half_length + 12), cy - ty * (half_length + 12)))
        down = to_cell(x0, y0, (cx + tx * (half_length + 12), cy + ty * (half_length + 12)))
    ok = all(0 <= c[0] < H and 0 <= c[1] < W for c in (up, down))
    rep["channel_square"] = square
    rep["channel_through_ford"] = bool(ok and connected_disc(water, up, down, square))
    return rep


def section_width_min(names, layers, idx, x0, y0, point, normal, reach, spread=40, step=5):
    """The narrowest section_width through the point over normals turned up to `spread` degrees either
    way: near a polyline vertex the carve's own direction differs from the segment's, and a section
    across it obliquely reads wide (a 7.5-tile band read 30 degrees off measures 9)."""
    best = None
    for d in range(-spread, spread + 1, step):
        a = math.radians(d)
        n = (normal[0] * math.cos(a) - normal[1] * math.sin(a), normal[0] * math.sin(a) + normal[1] * math.cos(a))
        w = section_width(names, layers, idx, x0, y0, point, n, reach)
        best = w if best is None else min(best, w)
    return best


def banks_land(names, layers, idx, x0, y0, point, normal, out):
    """Both tiles `out` tiles from the point along the normal are inside the raster and lack water_tile
    (land on both banks there, so a cross-section measures the carve, not a lake it runs through)."""
    water = layer_mask(names, layers, idx, "water_tile")
    H, W = idx.shape
    for sign in (1, -1):
        r, c = to_cell(x0, y0, (point[0] + sign * normal[0] * out, point[1] + sign * normal[1] * out))
        if not (0 <= r < H and 0 <= c < W) or idx[r, c] < 0 or water[r, c]:
            return False
    return True


def section_width(names, layers, idx, x0, y0, point, normal, reach):
    """The water across a river at a point: the run of tiles with water_tile along the normal through
    the point, counted outward from it both ways until the first tile without (T5's width check)."""
    water = layer_mask(names, layers, idx, "water_tile")
    H, W = idx.shape
    r, c = to_cell(x0, y0, point)
    if not (0 <= r < H and 0 <= c < W) or not water[r, c]:
        return 0
    n = 1
    for sign in (1, -1):
        for k in range(1, int(reach) + 1):
            # step half a tile at a time so a diagonal normal visits every tile it crosses once
            seen = set()
            for h in (k - 0.5, k):
                rr, cc = to_cell(x0, y0, (point[0] + sign * normal[0] * h, point[1] + sign * normal[1] * h))
                seen.add((rr, cc))
            if not all(0 <= rr < H and 0 <= cc < W and water[rr, cc] for rr, cc in seen):
                break
            n += 1
    return n


def selftest():
    checks = []

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # T5: a 3-wide channel from a lake to the area border, pinched to 2 wide in one place.
    def mk_area(water, cliffs=()):
        h, w = water.shape
        rows = []
        for r in range(h):
            parts, cur, cnt = [], None, 0
            for c in range(w):
                v = 1 if water[r, c] else 0
                if v == cur:
                    cnt += 1
                else:
                    if cur is not None:
                        parts.append(f"{cur}*{cnt}")
                    cur, cnt = v, 1
            parts.append(f"{cur}*{cnt}")
            rows.append(" ".join(parts))
        return {"area": {"x0": 0, "y0": 0, "w": w, "h": h},
                "tiles": {"palette": ["grass-1", "water"], "rows": rows,
                          "info": [{"name": "grass-1", "layers": ["ground_tile"]},
                                   {"name": "water", "layers": ["player", "water_tile"]}]},
                "entity_names": [{"name": "cliff", "type": "cliff"}], "cliffs": list(cliffs)}
    wm = np.zeros((40, 60), bool)
    wm[5:15, 5:20] = True              # lake
    wm[9:12, 20:60] = True             # channel, 3 wide, to the east border
    wm[9, 35] = False                  # pinch: 2 wide at x 35
    ar = mk_area(wm)
    r = water_report(ar, (10.5, 10.5), (58.5, 10.5), 3, 12, False)
    ck("t5_connected_w1", r["connected_width_1"])
    ck("t5_not_at_w3", r["connected_at_width"] is False)
    ck("t5_max_width_2", r["max_passable_width_tiles"] == 2, str(r["max_passable_width_tiles"]))
    r2 = water_report(ar, (10.5, 10.5), None, 2, 12, True)
    ck("t5_to_border_w2", r2["connected_at_width"] is True)
    wm2 = wm.copy()
    wm2[9:12, 40] = False              # cut the channel
    r3 = water_report(mk_area(wm2), (10.5, 10.5), (58.5, 10.5), 1, 12, False)
    ck("t5_cut", r3["connected_width_1"] is False)

    # T6: a wall of axis-aligned cliff boxes across a 60 x 40 land area at y 19..22 with a 6-tile gap.
    land = np.zeros((40, 60), bool)
    cl = []
    for x in range(0, 60, 4):
        if 26 <= x < 32:
            continue
        cl.append([0, x + 2, 20.5, "west-to-east", x, 19.0, x + 4, 22.0, 0])
    ar6 = mk_area(land, cl)
    rep, free, lab = walk_report(ar6, (30, 5), (30, 35), 4, 2, 20)
    # Gap from x 28 to 32 is 4 tiles clear of boxes (x 26 and x 30 cliffs removed); the character body
    # makes the walkable gap 4 - 2 * 0.2 = 3.6 tiles, which the lattice reads as 3.5 (14 cells).
    ck("t6_connected", rep["connected"])
    ck("t6_gap_width", abs(rep["max_passable_width_tiles"] - 3.5) <= 0.25, str(rep["max_passable_width_tiles"]))
    rep_b, _, _ = walk_report(ar6, (30, 5), (30, 35), 4, None, 20, blocks=[(26, 18, 34, 24)])
    ck("t6_blocked_gap_disconnects", rep_b["connected"] is False)
    # Water tiles block the character too.
    land2 = np.zeros((40, 60), bool)
    land2[18:22, :] = True
    rep_w, _, _ = walk_report(mk_area(land2), (30, 5), (30, 35), 2, None, 10)
    ck("t6_water_blocks", rep_w["connected"] is False)
    # SAT: a unit square centred at 0 touches a diamond of radius 1 at (1.0, 0) but not at (1.25, 0).
    dia = [(0, -1), (1, 0), (0, 1), (-1, 0)]
    hit = sat_blocked(dia, np.array([1.0, 1.25]), np.array([0.0, 0.0]), 0.2)
    ck("sat_diamond", bool(hit[0]) and not bool(hit[1]))
    # T5 for waterways (S4's disc): a diagonal carve of half-width 3.75 (the floor) passes a 7-tile
    # disc end to end, which no 7 x 7 square can; pinched to half-width 2 it does not
    Yg, Xg = np.mgrid[0:80, 0:80].astype(float)
    dist = np.abs(Xg - Yg) / math.sqrt(2)
    diag = dist < 3.75
    ends = ((10, 10), (69, 69))
    ck("t5_disc_diagonal_floor", connected_disc(diag, *ends, 7) and not connected_at(diag, *ends, 7))
    pinch = diag & ~((dist >= 2.0) & (np.abs(Xg + Yg - 80) < 4))
    ck("t5_disc_pinched", not connected_disc(pinch, *ends, 7) and connected_disc(pinch, *ends, 3))
    # a vertical band exactly 7 tiles wide that shifts one column every 6 rows erodes to a core one
    # cell wide that steps diagonally: the disc still travels (8-connected centres)
    step = np.zeros((60, 40), bool)
    for r in range(60):
        c = 10 + r // 6
        step[r, c:c + 7] = True
    ck("t5_disc_band_shift", connected_disc(step, (3, 13), (56, 22), 7))
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name} {detail}")
    print(f"RESULT {'ok' if not bad else 'fail'} nav selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def game_selftest(out_root, dump_file, record, run):
    dump = dr.load_json(dump_file)
    cc = cliff_check(dump)
    (out_root / "nav-cliff-check.json").write_text(json.dumps(cc, indent=1), encoding="utf-8")
    t = cc["totals"][f"sign{int(cc['best_sign']):+d}"]
    record("t6_cliff_geometry_vs_game", cc["cliffs"] == 20 and t["point_mismatch_off_edge"] == 0 and
           t["character_mismatch"] == 0,
           f"20 orientations, rotation sense {cc['best_sign']:+.0f}: character mismatches {t['character_mismatch']} "
           f"of {t['cells']} cells; point mismatches {t['point_mismatch']}, all on box edges "
           f"({t['point_mismatch_off_edge']} off edge); both senses: {cc['totals']}")
    # Known-answer wall (scene "wall", dumped as area 1): sides connect only through the 8-tile gap.
    if len(dump["areas"]) > 1:
        wall = dump["areas"][1]
        gx = sorted(c[1] for c in wall["cliffs"])
        rep, free, lab = walk_report(wall, (0, 1010), (0, 1040), 4, 2, 16)
        img = np.where(free[..., None], np.array([200, 200, 190], np.uint8), np.array([60, 35, 15], np.uint8))
        Image.fromarray(img.astype(np.uint8)).save(out_root / "nav-wall-walk.png")
        (out_root / "nav-wall-walk.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        # Gap between the boxes of the cliffs at x -6 and 6 is 8 tiles; minus the character body 7.6,
        # read on a quarter-tile lattice as 7.5.
        record("t6_wall_gap", rep["connected"] and abs(rep["max_passable_width_tiles"] - 7.5) <= 0.25 and
               rep["cliffs"] == 18, f"cliffs {rep['cliffs']} at x {gx[:3]}..{gx[-3:]}, connected {rep['connected']}, "
                                    f"max width {rep['max_passable_width_tiles']} tiles")
        rep_b, _, _ = walk_report(wall, (0, 1010), (0, 1040), 4, None, 16, blocks=[(-4, 1020, 4, 1032)])
        record("t6_wall_only_through_gap", rep_b["connected"] is False, f"gap closed: connected {rep_b['connected']}")
    # T5 on the vanilla start-area lake: two points in it connect; the lake does not reach the border.
    ar = dump["areas"][0]
    water = tile_mask(ar, "water_tile")
    lab, n = labels(water)
    big = np.bincount(lab[lab >= 0]).argmax()
    rr, cc_ = np.nonzero(lab == big)
    a = (ar["area"]["x0"] + int(cc_.min()) + 0.5, ar["area"]["y0"] + int(rr[cc_ == cc_.min()][0]) + 0.5)
    b = (ar["area"]["x0"] + int(cc_.max()) + 0.5, ar["area"]["y0"] + int(rr[cc_ == cc_.max()][0]) + 0.5)
    rep = water_report(ar, a, b, None, 40, False)
    rep_border = water_report(ar, a, None, None, 40, True)
    (out_root / "nav-lake.json").write_text(json.dumps({"lake": rep, "to_border": rep_border}, indent=1), encoding="utf-8")
    record("t5_vanilla_lake", rep["connected_width_1"] and rep["max_passable_width_tiles"] >= 1 and
           not rep_border["connected_width_1"], f"lake {int((lab == big).sum())} tiles, ends connected "
           f"{rep['connected_width_1']}, max width {rep['max_passable_width_tiles']}, reaches border "
           f"{rep_border['connected_width_1']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("water")
    p.add_argument("dump")
    p.add_argument("--a", required=True)
    p.add_argument("--b")
    p.add_argument("--to-border", action="store_true")
    p.add_argument("--width", type=int)
    p.add_argument("--kmax", type=int, default=64)
    p.add_argument("--area", type=int, default=0)
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_water)
    p = sub.add_parser("walk")
    p.add_argument("dump")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--lattice", type=int, default=4)
    p.add_argument("--width", type=float, help="square side in tiles that must pass (rail check)")
    p.add_argument("--wmax", type=float, default=32.0)
    p.add_argument("--block", action="append", help="x0,y0,x1,y1 rectangle to close (repeatable)")
    p.add_argument("--area", type=int, default=0)
    p.add_argument("--png")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_walk)
    p = sub.add_parser("cliff-check")
    p.add_argument("dump")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_cliff_check)
    p = sub.add_parser("selftest")
    p.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args()
    if a.cmd == "water" and not a.b and not a.to_border:
        ap.error("water needs --b or --to-border")
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
