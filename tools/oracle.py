#!/usr/bin/env python3
"""T3 geography oracle: named places per map, converted to tiles at any scale, checked in game runs.

Data: oracle/<map>.json (built by `build` from R1's reference JSON and R7b's geography JSON) and
oracle/expressions.json (which named noise expression answers each property; null until a milestone
builds it). Every place carries its published latitude and longitude, the reference pixel where its
expectation holds in the EarthMaps raster (snapped to the nearest pixel of the right kind), and an
`expect` table: land, water, river, climate_band, tile_family_ab, tile_family_vanilla, region,
destroyed_zone, forest, hotspot. null means unknown; later milestones fill them.

Commands (from the Factorio workspace):
  python mod/tools/oracle.py build
  python mod/tools/oracle.py convert --map europe --scale 6 [--place Bosporus] [--lonlat 29.05,41.08]
  python mod/tools/oracle.py plan --map europe --scale 6 --names <expression> --instance ep-x --modset ep-x-m --out-root previews/earth-build/x/t3
  python mod/tools/oracle.py check --map europe --scale 6 --sample <fh.py sample run dirs> [--expr land=<expression>] [--context canals=false] --out-json t3.json
  python mod/tools/oracle.py check ... --probe <ep-s8-dump points.json>   (calculate_tile_properties and real tiles at the exact place tiles)
  python mod/tools/oracle.py selftest
"""
import argparse
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import earthgeo as eg  # noqa: E402

# Ported from spikes/S8-tooling (an earlier prototype): the oracle data lives in
# tests/oracle/, S8's own place set as a byte-copied fixture in tests/oracle/s8/ (its self-test
# reproduces S8's 760 checks there), and the research JSON in the repo's docs/.
ORACLE_DIR = eg.REPO / "tests" / "oracle"
S8_DIR = ORACLE_DIR / "s8"
R7B = eg.REPO / "docs" / "plan" / "research" / "R7b-geography.json"
APPROVALS = eg.REPO / "data-src" / "approvals" / "approvals-data.json"
PROPERTIES = ("land", "water", "river", "climate_band", "tile_family_ab", "tile_family_vanilla", "region",
              "destroyed_zone", "forest", "hotspot", "marsh")
SNAP_MAX_PX = 8.0
SCALES = (0.25, 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20)  # EarthMaps settings.lua:29 (R1)
# D9 names these countries cold, and North Africa hot: hints for the climate milestones, not expectations.
COLD_COUNTRIES = {"Norway", "Sweden", "Finland", "Russia"}
HOT_COUNTRIES = {"Morocco", "Algeria", "Tunisia", "Libya", "Egypt", "North Africa"}
# R7b ids for the D17 list (straits open; isthmuses closed unless canals are on).
STRAITS = ("gibraltar", "bosporus", "dardanelles", "dover", "oresund", "great_belt", "little_belt")
ISTHMUSES = ("corinth", "suez", "panama")
# Isthmus points that lie on a canal line (R7b canals route_polyline): water there when canals are on.
ON_CANAL = {"corinth": True, "suez": True, "panama": None}


def blank_expect():
    return {p: None for p in PROPERTIES}


# ------------------------------------------------------------------------------------------------
# Build

def snap(mref, lon, lat, want_land, max_px=SNAP_MAX_PX):
    """Nearest pixel (by centre) of the wanted class to a lon/lat point, within max_px."""
    u, v = mref.lonlat_to_uv(lon, lat)
    c0, r0 = int(math.floor(u)), int(math.floor(v))
    R = int(math.ceil(max_px)) + 1
    rs = np.arange(max(r0 - R, 0), min(r0 + R + 1, mref.H))
    cs = np.arange(max(c0 - R, 0), min(c0 + R + 1, mref.W))
    if rs.size == 0 or cs.size == 0:
        return None
    sub = mref.land[np.ix_(rs, cs)] == want_land
    d = np.hypot((cs[None, :] + 0.5) - u, (rs[:, None] + 0.5) - v)
    d = np.where(sub, d, np.inf)
    k = np.unravel_index(np.argmin(d), d.shape)
    if not np.isfinite(d[k]) or d[k] > max_px:
        return None
    return int(cs[k[1]]), int(rs[k[0]]), float(d[k])


def in_extent(mref, lon, lat):
    u, v = mref.lonlat_to_uv(lon, lat)
    return 0 <= u < mref.W and 0 <= v < mref.H


def build_map(key, geo):
    mref = eg.MapRef(key)
    J = mref.meta
    places = []
    for c in J["cities"]["list"]:
        lon, lat = c["lonlat"]
        country = c["full_name"].split(", ")[1] if c["full_name"].count(", ") >= 2 else None
        rec = {"id": f"city:{c['name']}", "name": c["name"], "kind": "city", "full_name": c["full_name"],
               "lon": lon, "lat": lat,
               "source": f"EarthMaps {J['source'].get('cities_file', 'cities file')} line {c['cities_file_line']}, "
                         f"position {c['position']} via R1 georeference (pixel centre)"}
        sn = snap(mref, lon, lat, True)
        rec["ref_pixel"] = [sn[0], sn[1]] if sn else None
        rec["snap_px"] = round(sn[2], 3) if sn else None
        if sn and (sn[0], sn[1]) != tuple(c["pixel"]):
            rec["snap_note"] = f"EarthMaps city pixel {c['pixel']} is water; snapped to the nearest land pixel"
        ex = blank_expect()
        ex["land"], ex["water"] = True, False
        ex["hotspot"] = False          # D25: no spawn city inside a hotspot (D4 removes such cities)
        rec["expect"] = ex
        hints = {}
        if country in COLD_COUNTRIES:
            hints["climate"] = f"cold (D9 names {country})"
        if country in HOT_COUNTRIES:
            hints["climate"] = f"hot (D9: North Africa is hot and desert by default)"
        rec["hints"] = hints
        places.append(rec)
    for group, ids in (("straits", STRAITS), ("isthmuses", ISTHMUSES)):
        for s in geo[group]:
            if s["id"] not in ids:
                continue
            npnt = s["narrowest_point"]
            lon, lat = float(npnt["lon"]), float(npnt["lat"])
            if not in_extent(mref, lon, lat):
                continue
            strait = group == "straits"
            rec = {"id": f"{'strait' if strait else 'isthmus'}:{s['id']}", "name": s["name"],
                   "kind": "strait" if strait else "isthmus", "lon": lon, "lat": lat,
                   "source": f"R7b-geography.json {group} {s['id']} narrowest_point ({npnt.get('basis', '')}); "
                             f"{s.get('citation_url', '')}", "min_width_m": s.get("min_width_m")}
            sn = snap(mref, lon, lat, not strait)
            rec["ref_pixel"] = [sn[0], sn[1]] if sn else None
            rec["snap_px"] = round(sn[2], 3) if sn else None
            ex = blank_expect()
            if strait:
                ex["water"], ex["land"] = True, False
            else:
                ex["land"], ex["water"] = True, False
            rec["expect"] = ex
            rec["hints"] = {}
            if not strait:
                on = ON_CANAL.get(s["id"])
                rec["expect_when"] = [{"when": {"canals": True},
                                       "expect": {"water": True, "land": False} if on else {"land": None, "water": None},
                                       "note": "the point lies on the canal line (R7b canals)" if on else
                                               "representative point, not on the canal line: unknown with canals on"}]
            places.append(rec)
    for p in places:
        if p["ref_pixel"] is not None:
            c, r = p["ref_pixel"]
            lon, lat = mref.pixel_lonlat(c, r)
            p["ref_pixel_lonlat"] = [round(lon, 5), round(lat, 5)]
            p["tiles_by_scale"] = {str(s): list(place_tile(mref, p, s)) for s in (1, 2, 3, 4, 5, 6)}
    return {
        "format": "earth-oracle/1", "map": key, "built_by": "mod/tools/oracle.py build",
        "sources": {"reference_json": f"mod/data-src/earthmaps/{key}.json",
                    "reference_land_png_sha256": J["png"]["land"]["sha256"],
                    "geography_json": "mod/docs/plan/research/R7b-geography.json"},
        "georeference": {k: J["georeference"][k] for k in ("px_per_degree", "lon_left_edge", "lat_top_edge")},
        "width_px": mref.W, "height_px": mref.H, "earthmaps_radii": J["earthmaps_radii"],
        "conventions": {
            "pixel": "u = (lon - lon_left_edge) * 45, v = (lat_top_edge - lat) * 45; pixel col spans [col, col + 1)",
            "tile": "floor convention: x = (u - wr) * scale; a place's tile is the tile holding its ref_pixel centre, "
                    "evaluated by the game at that tile's integer corner (earthgeo.py)",
            "tiles_by_scale": "precomputed [x, y] of that tile for scales 1 to 6 (floor convention)",
            "expect": "null = unknown; expect_when lists overrides that apply under a settings context",
            "snap": f"ref_pixel is the nearest pixel of the expected kind within {SNAP_MAX_PX} px of the published "
                    f"point (land for cities and isthmuses, water for straits); null when none",
        },
        "properties": list(PROPERTIES),
        "places": places,
    }


def cmd_build(a):
    """S8's builder, kept to show how the fixture in tests/oracle/s8/ was made; it writes only to
    --out-dir, never over the fixture or the extended oracle (see `extend`)."""
    geo = json.loads(R7B.read_text(encoding="utf-8"))
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in (a.maps.split(",") if a.maps else eg.MAPS):
        O = build_map(key, geo)
        path = out_dir / f"{key}.json"
        path.write_text(json.dumps(O, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        unsnapped = [p["name"] for p in O["places"] if p["ref_pixel"] is None]
        snapped = [(p["name"], p["snap_px"]) for p in O["places"] if p["snap_px"] and p["snap_px"] > 0.71]
        print(f"{key}: {len(O['places'])} places ({sum(p['kind'] == 'city' for p in O['places'])} cities), "
              f"unsnapped={unsnapped}, moved over 0.71 px={snapped}")
    exp = out_dir / "expressions.json"
    if not exp.exists():
        exp.write_text(json.dumps(DEFAULT_EXPRESSIONS, indent=1), encoding="utf-8", newline="\n")
    print(f"RESULT ok oracle built maps={a.maps or ','.join(eg.MAPS)} dir={out_dir}")
    return 0


DEFAULT_EXPRESSIONS = {
    "_note": ("How each oracle property is read from a run. expr = named noise expression sampled through "
              "fh.py sample or the ep-s8-dump points probe; null = not built yet, so the property is skipped. "
              "rule: ge/gt/le/lt against threshold gives a boolean; bands maps value ranges to names; values "
              "maps rounded values to names; source 'tile' reads the real tile name from a probe."),
    "land": {"expr": None, "rule": "ge", "threshold": 0},
    "water": {"expr": None, "rule": "lt", "threshold": 0},
    "river": {"expr": None, "rule": "gt", "threshold": 0},
    "climate_band": {"expr": None, "bands": None},
    "tile_family_ab": {"source": "tile", "families": None},
    "tile_family_vanilla": {"source": "tile", "families": None},
    "region": {"expr": None, "values": None},
    "destroyed_zone": {"expr": None, "rule": "gt", "threshold": 0},
    "forest": {"expr": None, "rule": "gt", "threshold": 0},
    "hotspot": {"expr": None, "rule": "gt", "threshold": 0},
    "marsh": {"expr": None, "rule": "gt", "threshold": 0},
}


# ------------------------------------------------------------------------------------------------
# Convert

def load_oracle(key, oracle_dir=None):
    return json.loads((Path(oracle_dir or ORACLE_DIR) / f"{key}.json").read_text(encoding="utf-8"))


def place_tile(mref, p, scale, origin="floor"):
    """Tile of a place: the tile holding its ref_pixel centre (or its raw point when unsnapped)."""
    if p.get("ref_pixel") is not None:
        c, r = p["ref_pixel"]
        tx = int(eg.pixel_centre_tiles([c], mref.wr, scale, origin)[0])
        ty = int(eg.pixel_centre_tiles([r], mref.hr, scale, origin)[0])
        return tx, ty
    return mref.lonlat_to_tile(p["lon"], p["lat"], scale, origin)[1]


def cmd_convert(a):
    mref = eg.MapRef(a.map)
    rows = []
    if a.lonlat:
        lon, lat = (float(v) for v in a.lonlat.split(","))
        (x, y), t = mref.lonlat_to_tile(lon, lat, a.scale, a.origin)
        u, v = mref.lonlat_to_uv(lon, lat)
        rows.append({"name": f"({lon}, {lat})", "lon": lon, "lat": lat, "pixel": [int(math.floor(u)), int(math.floor(v))],
                     "tile_point": [round(x, 3), round(y, 3)], "tile": list(t)})
    else:
        O = load_oracle(a.map)
        for p in O["places"]:
            if a.place and a.place.lower() not in p["name"].lower():
                continue
            (x, y), t_raw = mref.lonlat_to_tile(p["lon"], p["lat"], a.scale, a.origin)
            rows.append({"name": p["name"], "kind": p["kind"], "lon": p["lon"], "lat": p["lat"],
                         "ref_pixel": p["ref_pixel"], "tile": list(place_tile(mref, p, a.scale, a.origin)),
                         "tile_of_raw_point": list(t_raw), "chunk": [v // 32 for v in place_tile(mref, p, a.scale, a.origin)]})
    W, H = mref.world_size_tiles(a.scale)
    for r in rows:
        print(f"{r['name'][:28]:28s} lon {r['lon']:9.4f} lat {r['lat']:8.4f}  tile {r['tile'][0]:8d},{r['tile'][1]:8d}"
              + (f"  ref_pixel {r['ref_pixel']}" if r.get("ref_pixel") else ""))
    if a.out_json:
        Path(a.out_json).write_text(json.dumps({"map": a.map, "scale": str(a.scale), "origin": a.origin,
                                                "world_size_tiles": [W, H], "places": rows}, indent=1), encoding="utf-8")
    print(f"RESULT ok convert map={a.map} scale={a.scale} places={len(rows)} world={W}x{H}")
    return 0


# ------------------------------------------------------------------------------------------------
# Check

def load_expressions(path, overrides):
    E = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else dict(DEFAULT_EXPRESSIONS)
    for o in overrides or []:
        prop, _, name = o.partition("=")
        if prop not in PROPERTIES:
            raise SystemExit(f"RESULT fail --expr {o!r}: unknown property {prop!r}")
        E[prop] = dict(E.get(prop) or {}, expr=name)
    return E


def parse_context(text):
    ctx = {}
    for item in (text.split(",") if text else []):
        k, _, v = item.partition("=")
        ctx[k.strip()] = {"true": True, "on": True, "false": False, "off": False}.get(v.strip().lower(), v.strip())
    return ctx


def effective_expect(p, ctx):
    ex = dict(p["expect"])
    for w in p.get("expect_when", []):
        if all(ctx.get(k) == v for k, v in w["when"].items()):
            ex.update(w["expect"])
    return ex


def decode(spec, value):
    if value is None or not np.isfinite(value):
        return None
    if spec.get("rule"):
        t = float(spec.get("threshold", 0))
        return {"ge": value >= t, "gt": value > t, "le": value <= t, "lt": value < t}[spec["rule"]]
    if spec.get("bands"):
        for lo, hi, name in spec["bands"]:
            if (lo is None or value >= lo) and (hi is None or value < hi):
                return name
        return None
    if spec.get("values"):
        return spec["values"].get(str(int(round(value))))
    return value


class SampleIndex:
    """Values at tiles from fh.py sample runs (a grid per run)."""

    def __init__(self, runs):
        import t1_metrics as t1
        self.grids = []
        for r in runs:
            d = t1.read_sample_json(r)
            X0, Y0, step, size, frac = t1.sample_grid_tiles(d)
            vals = {n: np.asarray(v, dtype=float).reshape(size, size) for n, v in d["values"].items() if v} \
                if isinstance(d["values"], dict) else {}
            self.grids.append({"file": d["_file"], "X0": X0, "Y0": Y0, "step": step, "size": size, "vals": vals})

    def value(self, name, tx, ty):
        """(value, exact) at tile (tx, ty): exact when the tile is a grid point, else the nearest grid
        point within half a step; (None, None) when no grid covers it or the name was not sampled."""
        best = None
        for g in self.grids:
            if name not in g["vals"]:
                continue
            jx, jy = (tx - g["X0"]) / g["step"], (ty - g["Y0"]) / g["step"]
            ix, iy = int(round(jx)), int(round(jy))
            if 0 <= ix < g["size"] and 0 <= iy < g["size"]:
                exact = (jx == ix and jy == iy)
                v = float(g["vals"][name][iy, ix])
                if exact:
                    return v, True
                if best is None:
                    best = (v, False)
        return best if best else (None, None)


class ProbeIndex:
    """Values and real tiles at exact positions from an ep-s8-dump points file."""

    def __init__(self, paths):
        self.points = {}
        for path in paths:
            import dump_render
            d = dump_render.load_json(path)
            names = d.get("names", [])
            for pt in d.get("points", []):
                key = (int(math.floor(pt["x"])), int(math.floor(pt["y"])))
                rec = {"tile": pt.get("tile"), "values": dict(zip(names, pt.get("values", [])))}
                self.points[key] = rec

    def value(self, name, tx, ty):
        rec = self.points.get((tx, ty))
        if rec is None or not isinstance(rec["values"].get(name), (int, float)):
            return None, None
        return float(rec["values"][name]), True

    def tile(self, tx, ty):
        rec = self.points.get((tx, ty))
        return rec["tile"] if rec else None


def tile_family(spec, tile_name):
    fams = spec.get("families")
    if not tile_name or not fams:
        return None
    for fam, prefixes in fams.items():
        if any(tile_name.startswith(pfx) for pfx in prefixes):
            return fam
    return "other"


def check(mref, O, scale, origin, E, ctx, sample=None, probe=None):
    out = []
    counts = {"pass": 0, "fail": 0, "skip": 0, "not_covered": 0}
    for p in O["places"]:
        tx, ty = place_tile(mref, p, scale, origin)
        ex = effective_expect(p, ctx)
        rec = {"id": p["id"], "name": p["name"], "kind": p["kind"], "tile": [tx, ty], "checks": {}}
        for prop in PROPERTIES:
            want = ex.get(prop)
            spec = E.get(prop) or {}
            if want is None:
                continue
            if spec.get("source") == "tile":
                tname = probe.tile(tx, ty) if probe else None
                got = tile_family(spec, tname)
                status = "skip" if got is None else ("pass" if got == want else "fail")
                rec["checks"][prop] = {"want": want, "got": got, "tile": tname, "status": status,
                                       "why": None if got is not None else "needs a probe run and a families table"}
                counts[status] += 1
                continue
            if not spec.get("expr"):
                rec["checks"][prop] = {"want": want, "status": "skip", "why": "no expression mapped yet"}
                counts["skip"] += 1
                continue
            value, exact, src = None, None, None
            for name_src, idx in (("probe", probe), ("sample", sample)):
                if idx is not None:
                    value, exact = idx.value(spec["expr"], tx, ty)
                    if value is not None:
                        src = name_src
                        break
            if value is None:
                rec["checks"][prop] = {"want": want, "status": "not_covered", "expr": spec["expr"],
                                       "why": "no run covered this tile with this expression"}
                counts["not_covered"] += 1
                continue
            got = decode(spec, value)
            status = "pass" if got == want else "fail"
            rec["checks"][prop] = {"want": want, "got": got, "value": value, "expr": spec["expr"],
                                   "exact_tile": exact, "source": src, "status": status}
            counts[status] += 1
        if probe is not None and probe.tile(tx, ty) is not None:
            rec["real_tile"] = probe.tile(tx, ty)
        out.append(rec)
    return out, counts


def cmd_check(a):
    mref = eg.MapRef(a.map)
    O = load_oracle(a.map, a.oracle_dir)
    E = load_expressions(a.expressions, a.expr)
    ctx = parse_context(a.context)
    sample = SampleIndex(a.sample) if a.sample else None
    probe = ProbeIndex(a.probe) if a.probe else None
    if sample is None and probe is None:
        raise SystemExit("RESULT fail give --sample run dirs and/or --probe points files")
    out, counts = check(mref, O, a.scale, a.origin, E, ctx, sample, probe)
    rep = {"tool": "oracle check", "map": a.map, "scale": str(a.scale), "origin": a.origin, "context": ctx,
           "expressions": {k: v for k, v in E.items() if not k.startswith("_")}, "counts": counts, "places": out}
    if a.out_json:
        Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out_json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    fails = [f"{r['name']}.{k}" for r in out for k, c in r["checks"].items() if c["status"] == "fail"]
    print(f"RESULT {'ok' if not fails else 'fail'} oracle map={a.map} scale={a.scale} pass={counts['pass']} "
          f"fail={counts['fail']} skip={counts['skip']} not_covered={counts['not_covered']} "
          f"json={a.out_json or '-'}" + (f" first_fails={','.join(fails[:5])}" if fails else ""))
    return 0 if not fails else 1


def probe_points(mref, O, scale, origin="floor"):
    pts = []
    for p in O["places"]:
        tx, ty = place_tile(mref, p, scale, origin)
        pts.append(f"{tx},{ty}")
    return ";".join(sorted(set(pts), key=pts.index))


def cmd_probe(a):
    """One scenario run: calculate_tile_properties and the real tile at every place tile."""
    import dump_render
    mref = eg.MapRef(a.map)
    O = load_oracle(a.map, a.oracle_dir)
    code, res, f, so = dump_render.run_dump(a.instance, a.modset, a.out, a.seed, areas="",
                                            points=probe_points(mref, O, a.scale, a.origin), names=a.names,
                                            types="", decoratives=False, label=f"oracle-{a.map}-s{a.scale}",
                                            map_gen_settings=a.map_gen_settings)
    ok = code == 0 and f is not None and "isolated=yes" in res
    print(f"RESULT {'ok' if ok else 'fail'} oracle probe map={a.map} scale={a.scale} points={len(O['places'])} "
          f"file={f} scenario=({res})")
    return 0 if ok else 1


def cmd_plan(a):
    """fh.py sample commands: T1-aligned blocks (grid points on pixel-centre tiles) that hold places."""
    import t1_metrics as t1
    mref = eg.MapRef(a.map)
    O = load_oracle(a.map)
    px = [p["ref_pixel"] for p in O["places"] if p["ref_pixel"]]
    blocks = []
    for b in t1.plan_blocks(mref, a.scale, a.origin):
        c0, r0, w, h = b["px_window"]
        if any(c0 <= c < c0 + w and r0 <= r < r0 + h for c, r in px):
            blocks.append(b)
    for i, b in enumerate(blocks):
        out = f"{a.out_root}/b{i:02d}" if a.out_root else f"<out>/b{i:02d}"
        print(f"python tools/fh.py sample --instance {a.instance} --modset {a.modset} --names {a.names} --seed {a.seed} "
              f"--size {b['size']} --step {b['step']} --center {b['center'][0]},{b['center'][1]} --out {out}")
    print(f"RESULT ok oracle plan map={a.map} scale={a.scale} blocks={len(blocks)}")
    return 0


# ------------------------------------------------------------------------------------------------
# Toolchain extension (design section 7, milestone toolchain, T3 oracle data)
#
# tests/oracle/<map>.json = S8's places (the fixture rows, verbatim, except that strait and
# isthmus rows carry null land and water expectations tagged for waterways) plus rows
# that toolchain adds, each with its source: R7b's passes, forests, canal route vertices, marshes
# and the Destroyed Europe polygon with inside and outside probes; R7a's hotspots at their adopted
# centres (approvals-data.json); R1's six river reaches; and the brief's climate rows
#, tagged "brief" so the climate builder never writes its own answers. Every other
# expectation of an added row stays null until its layer ships.

BRIEF = "notes/EARTH-MOD-PLANNER-PROMPT.md:164-166 (D9)"
BRIEF_QUOTE = ("North Africa is hot and desert by default; Russia, Norway, Sweden and Finland are cold; "
               "the coldest biomes are far north")
# Brief-sourced climate places (decision 14; T3 Places): band names the climate milestone maps to Earth
# temperature: cold = cold or colder, coldest = the coldest band, hot_desert = hot and desert.
BRIEF_PLACES = [
    ("oslo", "Oslo, Norway", 10.7522, 59.9139, "cold", "published city coordinate"),
    ("stockholm", "Stockholm, Sweden", 18.0686, 59.3293, "cold", "published city coordinate"),
    ("helsinki", "Helsinki, Finland", 24.9384, 60.1699, "cold", "published city coordinate"),
    ("moscow", "Moscow, Russia", 37.6173, 55.7558, "cold", "published city coordinate"),
    ("varanger", "Varanger Peninsula, Norway (70.4 N)", 29.0, 70.4, "coldest",
     "interior point north of 70 N where EarthMaps paints class d (ice and tundra) on every map"),
    ("taymyr", "Taymyr Peninsula, Russia (75 N)", 100.0, 75.0, "coldest",
     "interior point north of 70 N, class d, on the maps that reach it"),
    ("gafsa", "Gafsa, Tunisia (North Africa)", 8.78, 34.42, "hot_desert",
     "North African point inside Europe's extent, EarthMaps class S (sand-3)"),
    ("sahara-algeria", "Sahara interior, Algeria", 2.0, 27.0, "hot_desert", "Sahara interior point, class s"),
    ("sahara-libya", "Sahara interior, Libya", 15.0, 26.0, "hot_desert", "Sahara interior point, class s"),
    ("western-desert", "Western Desert, Egypt", 28.0, 25.0, "hot_desert", "Sahara interior point, class s"),
    ("nejd", "Najd, Arabian interior", 44.0, 24.5, "hot_desert", "Arabian interior point, class s"),
    ("rub-al-khali", "Rub' al Khali, Arabian interior", 50.0, 20.5, "hot_desert", "Arabian interior point, class s"),
]
# Which milestone ships each property (staged activation): the gate checks a property only
# from its milestone on. Strait and canal land/water rows ship with waterways.
LAYERS = {"land": "europe-coast", "water": "europe-coast", "river": "waterways", "climate_band": "climate-tiles",
          "tile_family_ab": "climate-tiles", "tile_family_vanilla": "climate-tiles", "region": "region-layer",
          "destroyed_zone": "destroyed-europe", "forest": "trees-forests", "hotspot": "resources-enemies",
          "marsh": "climate-tiles"}
WATERWAY_KINDS = ("strait", "isthmus", "canal")


def polygon_edge_distance(lon, lat, poly):
    """Smallest planar distance in degrees from a point to the polygon's edges."""
    best = float("inf")
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        tt = 0.0 if L == 0 else max(0.0, min(1.0, ((lon - x1) * dx + (lat - y1) * dy) / L))
        best = min(best, math.hypot(lon - (x1 + tt * dx), lat - (y1 + tt * dy)))
    return best


def point_in_polygon(lon, lat, poly):
    """Ray casting in lon/lat, as R7b computed its membership."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xi = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < xi:
                inside = not inside
    return inside


def _row(mref, rid, name, kind, lon, lat, source, snap_land=None, **extra):
    rec = {"id": rid, "name": name, "kind": kind, "lon": float(lon), "lat": float(lat), "source": source}
    if snap_land is None:
        c, r = mref.lonlat_to_pixel(lon, lat)
        rec["ref_pixel"] = [c, r] if 0 <= c < mref.W and 0 <= r < mref.H else None
        rec["snap_px"] = 0.0 if rec["ref_pixel"] else None
    else:
        sn = snap(mref, lon, lat, snap_land)
        rec["ref_pixel"] = [sn[0], sn[1]] if sn else None
        rec["snap_px"] = round(sn[2], 3) if sn else None
    rec["expect"] = blank_expect()
    rec["hints"] = {}
    rec.update(extra)
    if rec["ref_pixel"] is not None:
        c, r = rec["ref_pixel"]
        plon, plat = mref.pixel_lonlat(c, r)
        rec["ref_pixel_lonlat"] = [round(plon, 5), round(plat, 5)]
        rec["on_reference_land"] = bool(mref.land[r, c])
        rec["tiles_by_scale"] = {str(s): list(place_tile(mref, rec, s)) for s in (1, 2, 3, 4, 5, 6)}
    return rec


def extend_map(key, geo, appr, s8_rows):
    mref = eg.MapRef(key)
    J = mref.meta
    places = []
    for p in s8_rows:
        p = json.loads(json.dumps(p))
        if p["kind"] in ("strait", "isthmus"):
            p["expect"]["land"] = p["expect"]["water"] = None
            p["pending"] = {"land": "waterways", "water": "waterways"}
            p["ruling"] = "19: strait and canal rows carry null expectations until waterways ships them"
            for w in p.get("expect_when", []):
                w["expect"] = {"land": None, "water": None}
        p["origin"] = "s8"
        places.append(p)
    r7b = "docs/plan/research/R7b-geography.json"
    for s in geo["passes"]:
        if in_extent(mref, s["lon"], s["lat"]):
            places.append(_row(mref, f"pass:{s['id']}", s["name"], "pass", s["lon"], s["lat"],
                               f"{r7b} passes {s['id']} ({s.get('coord_basis', '')}); {s.get('citation_url', '')}",
                               origin="r7b", range=s.get("range_id"), layer="ridges"))
    adopted_forest = {f["id"]: f.get("adopted", {}).get(key) for f in appr["forests"]}
    for f in geo["forests"]:
        c = f["centroid"]
        if in_extent(mref, c["lon"], c["lat"]):
            places.append(_row(mref, f"forest:{f['id']}", f["name"], "forest", c["lon"], c["lat"],
                               f"{r7b} forests {f['id']} centroid ({c.get('basis', '')}); {f.get('citation_url', '')}",
                               origin="r7b", tier=f.get("tier"),
                               radius_km=(f.get("extent") or {}).get("equivalent_radius_km"),
                               adopted=adopted_forest.get(f["id"]), layer="trees-forests"))
    canal_maps = {c["id"]: c.get("maps", {}).get(key) for c in appr["canals"]}
    for cn in geo["canals"]:
        for k, (lat, lon) in enumerate(cn.get("route_polyline") or []):
            if in_extent(mref, lon, lat) and canal_maps.get(cn["id"]) is not False:
                places.append(_row(mref, f"canal:{cn['id']}:{k}", f"{cn['name']} route vertex {k}", "canal", lon, lat,
                                   f"{r7b} canals {cn['id']} route_polyline[{k}] ({cn.get('route_basis', '')[:60]})",
                                   origin="r7b", canal=cn["id"], vertex=k,
                                   pending={"land": "waterways", "water": "waterways"},
                                   ruling="19: strait and canal rows carry null expectations until waterways ships them"))
    adopted_marsh = {m["id"]: m.get("adopted", {}).get(key) for m in appr["marshes"]}
    for m in geo["marshes"]:
        c = m["centroid"]
        if in_extent(mref, c["lon"], c["lat"]):
            places.append(_row(mref, f"marsh:{m['id']}", m["name"], "marsh", c["lon"], c["lat"],
                               f"{r7b} marshes {m['id']} centroid ({c.get('basis', '')}); {m.get('citation_url', '')}",
                               origin="r7b", tier=m.get("tier"), adopted=adopted_marsh.get(m["id"]), layer="climate-tiles"))
    de = geo["destroyed_europe"]
    poly = [[v["lon"], v["lat"]] for v in de["polygon"]]
    for side, group in (("inside", de["cities_inside"]), ("outside", de["cities_outside_checked"])):
        for c in group:
            if in_extent(mref, c["lon"], c["lat"]):
                slug = re.sub(r"[^a-z0-9]+", "-", c["name"].lower()).strip("-")
                # A probe within one reference pixel of the boundary is a band edge (T3 PD): either
                # side passes there (Terespol and Przemysl anchor the eastern edge itself).
                edge = polygon_edge_distance(c["lon"], c["lat"], poly) <= 1.0 / mref.ppd
                places.append(_row(mref, f"destroyed-{side}:{slug}", c["name"], "destroyed_probe", c["lon"], c["lat"],
                                   f"{r7b} destroyed_europe cities_{side if side == 'inside' else 'outside_checked'} "
                                   f"{c['name']}; {c.get('citation_url', '')}",
                                   origin="r7b", polygon_side=side, band_edge=edge, layer="destroyed-europe"))
    for h in appr["hotspots"]:
        if in_extent(mref, h["lon"], h["lat"]):
            places.append(_row(mref, f"hotspot:{h['id']}", h["id"], "hotspot", h["lon"], h["lat"],
                               f"docs/plan/research/R7a-hotspots.json {h['id']}, adopted centre from "
                               f"data-src/approvals/approvals-data.json (ruling 16)",
                               origin="r7a", resource=h["resource"], cited_lon=h.get("cited_lon"),
                               cited_lat=h.get("cited_lat"), radius_km=h.get("radius_km"), strength=h.get("strength"),
                               adopted=(h.get("adopted") or {}).get(key) if isinstance(h.get("adopted"), dict)
                               else h.get("adopted"), layer="resources-enemies"))
    eu = eg.MapRef("europe")
    for river in eu.meta["river_sampler_simulation"]["rivers"]:
        slug = re.sub(r"[^a-z0-9]+", "-", river["river"].lower()).strip("-")
        # R1 records each end as [row, col] (Mainz at row 987, col 868 reads 50.0 N, 8.28 E).
        for end, (r, c) in zip(("a", "b"), river["end_points_px"]):
            lon, lat = eu.pixel_lonlat(c, r)
            if in_extent(mref, lon, lat):
                places.append(_row(mref, f"river:{slug}:{end}", f"{river['river']} end {end}", "river_reach", lon, lat,
                                   f"R1 (docs/plan/research/R1-earthmaps.md, 'The reaches tested'); data-src/earthmaps/"
                                   f"europe.json river_sampler_simulation end_points_px [row, col] {[r, c]}",
                                   origin="r1", reach=river["river"],
                                   pending={"river": "waterways"}, layer="waterways"))
    for slug, name, lon, lat, band, basis in BRIEF_PLACES:
        if in_extent(mref, lon, lat):
            rec = _row(mref, f"climate:{slug}", name, "climate", lon, lat,
                       f"brief {BRIEF}: \"{BRIEF_QUOTE}\"; point: {basis}", snap_land=True,
                       origin="brief", tags=["brief"], layer="climate-tiles",
                       locked="brief: written by toolchain from the brief (ruling 14); the climate slice "
                              "never edits it")
            rec["expect"]["climate_band"] = band
            places.append(rec)
    O = {
        "format": "earth-oracle/2", "map": key, "built_by": "mod/tools/oracle.py extend",
        "sources": {"s8_fixture": f"tests/oracle/s8/{key}.json (byte copy of spikes/S8-tooling/oracle/{key}.json)",
                    "reference_json": f"data-src/earthmaps/{key}.json",
                    "reference_land_png_sha256": J["png"]["land"]["sha256"],
                    "geography_json": r7b, "approvals": "data-src/approvals/approvals-data.json",
                    "hotspots": "docs/plan/research/R7a-hotspots.json via approvals-data.json",
                    "rivers": "docs/plan/research/R1-earthmaps.md and data-src/earthmaps/europe.json",
                    "brief": BRIEF},
        "georeference": {k: J["georeference"][k] for k in ("px_per_degree", "lon_left_edge", "lat_top_edge")},
        "width_px": mref.W, "height_px": mref.H, "earthmaps_radii": J["earthmaps_radii"],
        "conventions": dict(load_oracle(key, S8_DIR)["conventions"],
                            origin="s8 rows come from the fixture; r7b, r7a, r1 and brief rows are added by "
                                   "toolchain; ref_pixel of an added row is the pixel holding its point (brief rows: "
                                   "the nearest land pixel)"),
        "layers": LAYERS,
        "destroyed_europe_polygon": {"vertices_lonlat": poly, "source": f"{r7b} destroyed_europe.polygon",
                                     "status": de.get("status")},
        "properties": list(PROPERTIES),
        "places": places,
    }
    return O


def cmd_extend(a):
    geo = json.loads(R7B.read_text(encoding="utf-8"))
    appr = json.loads(APPROVALS.read_text(encoding="utf-8"))
    for key in eg.MAPS:
        s8 = load_oracle(key, S8_DIR)["places"]
        O = extend_map(key, geo, appr, s8)
        (ORACLE_DIR / f"{key}.json").write_text(json.dumps(O, indent=1, ensure_ascii=False) + "\n",
                                                encoding="utf-8", newline="\n")
        kinds = {}
        for p in O["places"]:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        print(f"{key}: {len(O['places'])} places {kinds}")
    exp = ORACLE_DIR / "expressions.json"
    exp.write_text(json.dumps(DEFAULT_EXPRESSIONS, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"RESULT ok oracle extended maps={','.join(eg.MAPS)} dir={ORACLE_DIR}")
    return 0


def owner(O, p, prop):
    """The milestone that ships a row's property: the row's pending tag, else the oracle's layers map."""
    return (p.get("pending") or {}).get(prop) or (O.get("layers") or LAYERS).get(prop)


def validate(live=(), oracle_dir=None):
    """The oracle rows: sources, the fixture rows intact, the reference holding wherever a land
    expectation exists, the polygon sides, and staged activation: an expectation may be
    set only once the milestone that owns its property (the row's pending tag, else the layers map) is
    live, which is every milestone in `live` (the runner passes the milestones up to the gate's --through).
    The brief rows are locked whatever is live: their climate band is the brief's."""
    checks = []
    live = set(live)

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    geo = json.loads(R7B.read_text(encoding="utf-8"))
    brief_band = {f"climate:{slug}": band for slug, _, _, _, band, _ in BRIEF_PLACES}
    counts = {}
    s8_dir = Path(oracle_dir) / "s8" if oracle_dir else S8_DIR
    for key in eg.MAPS:
        O = load_oracle(key, oracle_dir)
        F = load_oracle(key, s8_dir)
        mref = eg.MapRef(key)
        ck(f"{key}_layers", O.get("layers") == LAYERS, str(O.get("layers")))
        ids = [p["id"] for p in O["places"]]
        ck(f"{key}_ids_unique", len(ids) == len(set(ids)), f"{len(ids)} ids")
        ck(f"{key}_properties", O.get("properties") == list(PROPERTIES))
        fix = {p["id"]: p for p in F["places"]}
        got = {p["id"]: p for p in O["places"] if p.get("origin") == "s8"}
        ck(f"{key}_s8_rows_present", set(fix) == set(got), f"{len(got)} of {len(fix)}")
        same = 0
        for pid, fp in fix.items():
            op = dict(got.get(pid) or {})
            for k in ("origin", "pending", "ruling"):
                op.pop(k, None)
            fp2 = json.loads(json.dumps(fp))
            if fp2["kind"] in ("strait", "isthmus"):
                fp2["expect"]["land"] = fp2["expect"]["water"] = None
                for w in fp2.get("expect_when", []):
                    w["expect"] = {"land": None, "water": None}
            # once waterways is live its strait and isthmus rows may carry the fixture's own values
            filled_ok = fp["kind"] in ("strait", "isthmus") and owner(O, got.get(pid) or fp, "land") in live and                 op == json.loads(json.dumps(fp))
            same += int(op == fp2 or filled_ok)
        ck(f"{key}_s8_rows_unchanged", same == len(fix), f"{same} of {len(fix)} equal the fixture")
        k = {}
        for p in O["places"]:
            k[p["kind"]] = k.get(p["kind"], 0) + 1
            if not str(p.get("source", "")).strip():
                ck(f"{key}_{p['id']}_source", False, "no source")
            ex = p["expect"]
            if p["kind"] in WATERWAY_KINDS and owner(O, p, "land") not in live:
                ck(f"{key}_{p['id']}_waterways_null", ex["land"] is None and ex["water"] is None and
                   (p.get("pending") or {}).get("land") == "waterways", str(ex))
            if p.get("origin") == "brief":
                ck(f"{key}_{p['id']}_brief", "brief" in p.get("tags", []) and BRIEF in p["source"] and
                   str(p.get("locked", "")).startswith("brief") and
                   ex["climate_band"] == brief_band.get(p["id"]), str(ex))
            if p.get("origin") in ("brief", "r7b", "r7a", "r1"):
                early = [kk for kk, v in ex.items() if v is not None and owner(O, p, kk) not in live
                         and not (kk == "climate_band" and p.get("origin") == "brief")]
                ck(f"{key}_{p['id']}_staged", not early,
                   f"set before its owner ships: {[(kk, owner(O, p, kk)) for kk in early]}")
            if ex.get("land") is not None and p["kind"] not in WATERWAY_KINDS:
                if p["ref_pixel"] is None:
                    ck(f"{key}_{p['id']}_snapped", False, "a land expectation without a pixel")
                else:
                    c, r = p["ref_pixel"]
                    ck(f"{key}_{p['id']}_reference_holds", bool(mref.land[r, c]) == ex["land"])
            if p["kind"] == "destroyed_probe":
                poly = O["destroyed_europe_polygon"]["vertices_lonlat"]
                ok = point_in_polygon(p["lon"], p["lat"], poly) == (p["polygon_side"] == "inside")
                ck(f"{key}_{p['id']}_polygon_side", ok or p.get("band_edge"),
                   f"edge distance {polygon_edge_distance(p['lon'], p['lat'], poly):.4f} deg")
        counts[key] = k
        ck(f"{key}_brief_rows", sum(1 for p in O["places"] if p.get("origin") == "brief") >= 5,
           f"{sum(1 for p in O['places'] if p.get('origin') == 'brief')} brief rows")
    eu = load_oracle("europe", oracle_dir)
    kinds = {p["kind"] for p in eu["places"]}
    for need in ("pass", "forest", "canal", "marsh", "destroyed_probe", "hotspot", "river_reach", "climate"):
        ck(f"europe_has_{need}", need in kinds)
    sides = {p.get("polygon_side") for p in eu["places"] if p["kind"] == "destroyed_probe"}
    ck("europe_destroyed_probes_both_sides", sides == {"inside", "outside"}, str(sides))
    n_pass = sum(1 for p in eu["places"] if p["kind"] == "pass")
    ck("europe_all_r7b_passes", n_pass == sum(1 for s in geo["passes"] if in_extent(eg.MapRef("europe"), s["lon"], s["lat"])),
       f"{n_pass} passes")
    reaches = {p.get("reach") for p in eu["places"] if p["kind"] == "river_reach"}
    ck("europe_six_river_reaches", len(reaches) == 6, f"{len(reaches)} reaches")
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in bad[:20]:
        print(f"  FAIL {name}: {detail}")
    print(f"  places by kind: {json.dumps(counts)}")
    print(f"RESULT {'ok' if not bad else 'fail'} oracle validate checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


# ------------------------------------------------------------------------------------------------
# Self-tests

def selftest(oracle_dir=None):
    """S8's 760 offline checks, on S8's own place set (the fixture copy in tests/oracle/s8/)."""
    oracle_dir = Path(oracle_dir or S8_DIR)
    checks = []

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    def load_oracle(key, _unused=None):  # the fixture, never the extended oracle
        return json.loads((oracle_dir / f"{key}.json").read_text(encoding="utf-8"))

    for key in eg.MAPS:
        O = load_oracle(key)
        mref = eg.MapRef(key)
        n_city = sum(p["kind"] == "city" for p in O["places"])
        ck(f"{key}_cities", n_city == mref.meta["cities"]["count"], f"{n_city} cities")
        for p in O["places"]:
            if p["ref_pixel"] is None:
                ck(f"{key}_{p['name']}_snapped", False, "no pixel of the expected kind within reach")
                continue
            c, r = p["ref_pixel"]
            want_land = p["expect"]["land"]
            ck(f"{key}_{p['name']}_reference_holds", bool(mref.land[r, c]) == want_land,
               f"pixel {c},{r} land={bool(mref.land[r, c])}")
            # Round trip: pixel centre -> lon/lat -> pixel.
            lon, lat = mref.pixel_lonlat(c, r)
            ck(f"{key}_{p['name']}_roundtrip", mref.lonlat_to_pixel(lon, lat) == (c, r))
            # Tile of the place is the tile holding the pixel centre, and maps back to the pixel.
            for s in (1, 3, 6):
                tx, ty = place_tile(mref, p, s)
                ck(f"{key}_{p['name']}_s{s}_tile_to_pixel", mref.tile_to_pixel(tx, ty, s) == (c, r),
                   f"tile {tx},{ty}")
    # The D17 names are present where the map holds them.
    eu = load_oracle("europe")
    names = {p["id"] for p in eu["places"]}
    for sid in STRAITS + ("corinth",):
        ck(f"europe_has_{sid}", any(i.endswith(":" + sid) for i in names))
    at = load_oracle("atlantic")
    ck("atlantic_has_suez_panama", all(any(p["id"] == f"isthmus:{i}" for p in at["places"]) for i in ("suez", "panama")))
    ow = load_oracle("olde_world")
    ck("olde_world_has_no_panama", not any(p["id"] == "isthmus:panama" for p in ow["places"]))
    # EarthMaps' own spawn tile for Tirana at scale 2 (R1 spawn_tile_by_scale) is the chunk centre of
    # (pixel - radius) * scale: within one chunk plus a pixel of our tile.
    mref = eg.MapRef("europe")
    tirana = next(c for c in mref.meta["cities"]["list"] if c["name"] == "Tirana")
    p = next(p for p in eu["places"] if p["name"] == "Tirana")
    for s in ("1", "2", "6"):
        em = tirana["spawn_tile_by_scale"][s]["tile"]
        ours = place_tile(mref, p, int(s))
        ck(f"tirana_s{s}_near_earthmaps_spawn", max(abs(em[0] - ours[0]), abs(em[1] - ours[1])) <= 16 + int(s),
           f"ours {ours} EarthMaps {em}")
    # Context: an isthmus on a canal line flips to water when canals are on.
    cor = next(p for p in eu["places"] if p["id"] == "isthmus:corinth")
    ck("corinth_canals_off_land", effective_expect(cor, {})["land"] is True)
    ck("corinth_canals_on_water", effective_expect(cor, {"canals": True})["water"] is True)
    # Checker on a synthetic grid: land expression true everywhere except Bosporus' tile.
    s = 3
    bos = next(p for p in eu["places"] if p["id"] == "strait:bosporus")
    btx, bty = place_tile(mref, bos, s)

    class FakeIdx:
        def value(self, name, tx, ty):
            return (-1.0 if (tx, ty) == (btx, bty) else 1.0), True

        def tile(self, tx, ty):
            return None
    E = load_expressions(oracle_dir / "expressions.json", ["land=fake", "water=fake"])
    out, counts = check(mref, eu, s, "floor", E, {}, sample=FakeIdx())
    fails = {(r["name"], k) for r in out for k, c in r["checks"].items() if c["status"] == "fail"}
    want_fails = {(p["name"], k) for p in eu["places"] if p["kind"] == "strait" and p["id"] != "strait:bosporus"
                  for k in ("land", "water")}
    ck("checker_synthetic_fails", fails == want_fails, f"{len(fails)} fails, want {len(want_fails)}")
    ck("checker_skips_unmapped", counts["skip"] == sum(1 for p in eu["places"] if p["expect"]["hotspot"] is not None),
       f"skip={counts['skip']}")
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        if not ok:
            print(f"  FAIL {name}: {detail}")
    print(f"  {len(checks) - len(bad)} of {len(checks)} checks ok")
    print(f"RESULT {'ok' if not bad else 'fail'} oracle selftest checks={len(checks)} failed={len(bad)}")
    return 0 if not bad else 1


def game_selftest(out_root, t1_runs, record, run):
    """Europe at scale 1 with the probe expressions (ep_s8_x, ep_s8_y, ep_s8_disc):
    (a) one fh.py sample run over the T1 block holding the most places: sampled x, y at every covered
        place equal the converter tile, and the checker fails for land and water against ep_s8_disc
        equal the analytic prediction;
    (b) one ep-s8-dump points run over every place: the same two checks at all places, through
        calculate_tile_properties at the exact tiles, plus the real tile name."""
    import game_selftest as gs
    import t1_metrics as t1
    mref = eg.MapRef("europe")
    O = load_oracle("europe", S8_DIR)
    s = "1"
    px = [p["ref_pixel"] for p in O["places"] if p["ref_pixel"]]
    blocks = t1.plan_blocks(mref, s)
    counts = [sum(1 for c, r in px if b["px_window"][0] <= c < b["px_window"][0] + b["px_window"][2]
                  and b["px_window"][1] <= r < b["px_window"][1] + b["px_window"][3]) for b in blocks]
    b = blocks[int(np.argmax(counts))]
    rd = out_root / "oracle-sample-europe-s1"
    code, so, res = run([eg.FH, "sample", "--instance", gs.INSTANCE, "--modset", gs.NAMES["probe"],
                         "--names", "ep_s8_x,ep_s8_y,ep_s8_disc", "--seed", "1000", "--size", b["size"],
                         "--step", b["step"], "--center", f"{b['center'][0]},{b['center'][1]}", "--out", rd],
                        "oracle sample")
    record("oracle_sample_isolated", "isolated=yes" in res, res)

    def analytic_fails(covered):
        want = set()
        for p in O["places"]:
            tx, ty = place_tile(mref, p, s)
            if (tx, ty) not in covered:
                continue
            inside = 200 - math.hypot(tx, ty) >= 0
            for k in ("land", "water"):
                if p["expect"][k] is not None and (inside if k == "land" else not inside) != p["expect"][k]:
                    want.add((p["name"], k))
        return want

    def checker(args, js, label):
        code, so, res = run([HERE / "oracle.py", "check", "--map", "europe", "--scale", s, "--oracle-dir", S8_DIR] + args +
                            ["--expr", "land=ep_s8_disc", "--expr", "water=ep_s8_disc", "--out-json", js], label)
        rep = json.loads(js.read_text(encoding="utf-8"))
        got = {(r["name"], k) for r in rep["places"] for k, c in r["checks"].items() if c["status"] == "fail"}
        return rep, got

    idx = SampleIndex([rd])
    covered, off = set(), 0
    for p in O["places"]:
        tx, ty = place_tile(mref, p, s)
        vx, ex = idx.value("ep_s8_x", tx, ty)
        vy, ey = idx.value("ep_s8_y", tx, ty)
        if ex and ey:
            covered.add((tx, ty))
            off += int(vx != tx or vy != ty)
    record("oracle_sample_place_tiles", off == 0 and len(covered) >= 10,
           f"{len(covered)} of {len(O['places'])} places in the sampled block, {off} with x,y off the converter tile")
    rep, got = checker(["--sample", rd], out_root / "oracle-check-sample.json", "oracle check sample")
    want = analytic_fails(covered)
    record("oracle_check_sample", got == want and rep["counts"]["pass"] > 0 and rep["counts"]["not_covered"] > 0,
           f"{rep['counts']}; fails equal the analytic disc: {got == want} ({len(got)} fails)")

    pd = out_root / "oracle-probe-europe-s1"
    code, so, res = run([HERE / "oracle.py", "probe", "--map", "europe", "--scale", s, "--oracle-dir", S8_DIR, "--names",
                         "ep_s8_x,ep_s8_y,ep_s8_disc", "--instance", gs.INSTANCE, "--modset", gs.NAMES["probe_dump"],
                         "--out", pd], "oracle probe")
    record("oracle_probe_isolated", "isolated=yes" in res, res)
    files = list((pd / "script-output" / "ep-s8-dump").glob("*.json"))
    if not files:
        record("oracle_probe_written", False, "no probe file")
        return None
    pidx = ProbeIndex(files)
    off = 0
    for p in O["places"]:
        tx, ty = place_tile(mref, p, s)
        off += int(pidx.value("ep_s8_x", tx, ty)[0] != tx or pidx.value("ep_s8_y", tx, ty)[0] != ty)
    tiles = sorted({str(pidx.tile(*place_tile(mref, p, s))) for p in O["places"]})
    record("oracle_probe_place_tiles", off == 0, f"{len(O['places'])} places, {off} off; real tiles seen {tiles[:6]}")
    rep, got = checker(["--probe"] + files, out_root / "oracle-check-probe.json", "oracle check probe")
    allp = {place_tile(mref, p, s) for p in O["places"]}
    want = analytic_fails(allp)
    record("oracle_check_probe", got == want and rep["counts"]["not_covered"] == 0,
           f"{rep['counts']}; fails equal the analytic disc: {got == want} ({len(got)} fails)")
    return [rd]


# ------------------------------------------------------------------------------------------------
# The spawn shift (milestone spawn-cities; S7 option ii): the chosen city's pixel centre sits at world
# (0, 0), so every place converts as world = geo - (cx, cy), with (cx, cy) the tile holding that
# centre, scale (col - wr) + floor(scale / corner_offset_divisor) (ARCHITECTURE.md, "The coordinate
# chain"). The fold's random pick runs in float32 in the noise program; random_city_index is the
# tool's model of it (T7 (c)), never control code's: control reads the index back at (0, 0).

CITIES = eg.REPO / "terra-nauvis" / "prototypes" / "tables" / "cities.lua"
# S7's game runs of the same hash on its 30-city dummy list (spikes/S7-spawn, design notes 04:00): seed ->
# city picked by the noise program. 4294967295 reads as 4294967296 in float32, so its city (8) is not
# the integer hash's (1). The model must reproduce every row.
S7_RANDOM = {"n": 30, "picks": {1000: 11, 1002: 25, 1004: 9, 4000000001: 3, 4294967295: 8},
             "integer_4294967295": 1}
_CITY_TABLES = {}


def city_table(path=CITIES):
    """The city table as Python data, parsed once per file content and handed out as a copy: the
    runner folds the cities for every spawn it places (city_fold), and parsing the table for each
    one was most of the gate's re-derivation of the T7 sweep."""
    import tnconfig
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    key = (str(p.resolve()), hashlib.sha256(text.encode("utf-8")).hexdigest())
    if key not in _CITY_TABLES:
        _CITY_TABLES[key] = tnconfig.loads(text, str(p), p.name)
    return copy.deepcopy(_CITY_TABLES[key])


def city_fold(cfg, map_key):
    """(setting values, [(col, row)]) of a map's city fold: the spawn-city setting's values in fold
    order ("random" first, so city k is values[k]) and each city's reference pixel, converted from the
    city table's degrees with the pixel-centre formula exactly as spawn.lua converts them."""
    import tnconfig
    g = tnconfig.geography(cfg)[map_key]
    if not g.get("spawn"):
        raise ValueError(f"config.lua gives {map_key}'s newest geography version no spawn record")
    values = cfg["settings"][g["city_setting"]]["allowed_values"]
    rows = city_table()[map_key]["cities"]
    m = cfg["maps"][map_key]
    ppd = cfg["coordinates"]["px_per_degree"]
    px = []
    for v in values[1:]:
        c = rows[v]
        px.append((math.floor((c["lon"] - m["lon_left_edge"]) * ppd), math.floor((m["lat_top_edge"] - c["lat"]) * ppd)))
    return values, px


def random_city_index(cfg, seed, n):
    """The fold's random pick, 1 to n, as the noise program computes it in float32:
    (map_seed_small * a + floor(map_seed / d) * b) % n + 1, map_seed_small the integer seed's low 16
    bits and map_seed itself a float32 (config.lua spawn.hash; S7)."""
    H = cfg["spawn"]["hash"]
    f = np.float32
    ms = f(int(seed))
    small = f(int(seed) & 0xFFFF)
    high = np.floor(ms / f(H["high_div"]))
    h = small * f(H["small_mult"]) + high * f(H["high_mult"])
    r = h - np.floor(h / f(n)) * f(n)
    return int(r) + 1


def resolved_city(cfg, map_key, seed, number):
    """The city index (1 to n) a world resolves: its baked city number, or for 0 (random) the model."""
    _, px = city_fold(cfg, map_key)
    number = int(number or 0)
    return number if number > 0 else random_city_index(cfg, seed, len(px))


def spawn_offset(cfg, map_key, scale, seed, number):
    """(cx, cy) in tiles for a world at `scale` and `seed` with the baked city number `number`."""
    _, px = city_fold(cfg, map_key)
    col, row = px[resolved_city(cfg, map_key, seed, number) - 1]
    m = cfg["maps"][map_key]
    s = int(scale)
    corner = s // int(cfg["coordinates"]["corner_offset_divisor"])
    return s * (col - m["wr"]) + corner, s * (row - m["hr"]) + corner


def pen_offset(cfg, map_key, pen, seed):
    """The spawn offset of a world made with property_expression_names `pen` at `seed`: numbers baked for
    the city offset names of the map's newest geography version stand as they are (europe-coast's 0,
    or a test-only tile); names (the city fold) resolve through the baked city number."""
    import tnconfig
    g = tnconfig.geography(cfg)[map_key]
    a, b = pen.get(g["cx"]), pen.get(g["cy"])
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a, b)):
        return int(a), int(b)
    return spawn_offset(cfg, map_key, int(pen[cfg["keys"]["scale"]]), seed, pen.get(g.get("city"), 0))


def world_tile(tile, offset):
    """A geo tile (the S8 tools' tile space) as a world tile under the spawn shift."""
    return int(tile[0]) - int(offset[0]), int(tile[1]) - int(offset[1])


def spawn_selftest(cfg=None, oracle_dir=None):
    """Offline checks of the spawn model, outside S8's 760 (selftest's count stays S8's): the float32
    model reproduces S7's five game picks and differs from the integer hash where S7 found it does;
    every map with a city fold converts each city to the reference JSON's pixel, its offset at scales
    1, 3 and 6 is the oracle's pixel-centre tile, and the setting lists no city the approvals removed.
    Returns [(name, ok, detail)]."""
    import tnconfig
    cfg = cfg or tnconfig.load()
    out = []
    for seed, want in S7_RANDOM["picks"].items():
        got = random_city_index(cfg, seed, S7_RANDOM["n"])
        out.append((f"model seed {seed} picks S7's city {want}", got == want, f"got {got}"))
    H = cfg["spawn"]["hash"]
    integer = (65535 * H["small_mult"] + (4294967295 // H["high_div"]) * H["high_mult"]) % S7_RANDOM["n"] + 1
    out.append(("the integer hash differs at 4294967295 (why control reads the index back)",
                integer == S7_RANDOM["integer_4294967295"] and integer != S7_RANDOM["picks"][4294967295],
                f"integer {integer}"))
    appr = json.loads(APPROVALS.read_text(encoding="utf-8"))
    newest = tnconfig.geography(cfg)
    for key in cfg["map_order"]:
        g = newest.get(key) or {}
        if not g.get("spawn"):
            continue
        mref = eg.MapRef(key)
        values, px = city_fold(cfg, key)
        ref = {c["name"]: c for c in mref.meta["cities"]["list"]}
        rows = city_table()[key]["cities"]
        O = load_oracle(key, oracle_dir)
        places = {p["name"]: p for p in O["places"] if p["kind"] == "city"}
        removed = {r["name"] for r in appr["cities"][key]["removed"]}
        kept = appr["cities"][key]["kept"]
        names = [rows[v]["name"] for v in values[1:]]
        out.append((f"{key}: the setting lists the approvals' kept cities in order",
                    [ref[n]["full_name"] for n in names if n in ref] == kept and len(names) == len(kept),
                    f"{len(names)} cities"))
        out.append((f"{key}: no removed city is a value", not (set(names) & removed), f"removed {sorted(removed)}"))
        for v, n, (col, row) in zip(values[1:], names, px):
            r = ref.get(n)
            out.append((f"{key} {v}: pixel equals the reference JSON's", r is not None and [col, row] == r["pixel"],
                        f"{(col, row)} against {r and r['pixel']}"))
            p = places.get(n)
            for s in (1, 3, 6):
                k = values.index(v)
                got = spawn_offset(cfg, key, s, 1000, k)
                want = tuple(place_tile(mref, p, s)) if p else None
                out.append((f"{key} {v} scale {s}: offset equals the oracle's tile", got == want, f"{got} against {want}"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build", help="S8's builder of its place set, into --out-dir only")
    p.add_argument("--maps")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("extend", help="write tests/oracle/<map>.json: S8's places plus the toolchain rows")
    p.set_defaults(fn=cmd_extend)
    p = sub.add_parser("validate", help="validate tests/oracle/<map>.json against its sources and the fixture")
    p.add_argument("--live", default="", help="comma list of the slices whose oracle properties are live")
    p.set_defaults(fn=lambda a: validate([x for x in a.live.split(",") if x]))
    p = sub.add_parser("convert")
    p.add_argument("--map", required=True, choices=eg.MAPS)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--place")
    p.add_argument("--lonlat")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_convert)
    p = sub.add_parser("plan")
    p.add_argument("--map", required=True, choices=eg.MAPS)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--names", default="<expressions>")
    p.add_argument("--instance", default="<instance>")
    p.add_argument("--modset", default="<modset>")
    p.add_argument("--seed", default="1000")
    p.add_argument("--out-root")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("probe", help="run ep-s8-dump points at every place tile (needs ep-s8-dump in the modset)")
    p.add_argument("--map", required=True, choices=eg.MAPS)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--names", required=True, help="comma list of expressions to evaluate")
    p.add_argument("--instance", required=True)
    p.add_argument("--modset", required=True)
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--map-gen-settings")
    p.add_argument("--out", required=True)
    p.add_argument("--oracle-dir", default=str(ORACLE_DIR))
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("check")
    p.add_argument("--map", required=True, choices=eg.MAPS)
    p.add_argument("--scale", required=True)
    p.add_argument("--origin", choices=sorted(eg.ORIGINS), default="floor")
    p.add_argument("--sample", nargs="*", help="fh.py sample run dirs")
    p.add_argument("--probe", nargs="*", help="ep-s8-dump points JSON files")
    p.add_argument("--expressions", default=str(ORACLE_DIR / "expressions.json"))
    p.add_argument("--oracle-dir", default=str(ORACLE_DIR))
    p.add_argument("--expr", action="append", help="override: property=expression_name")
    p.add_argument("--context", help="settings context, e.g. canals=true,alien_biomes=false")
    p.add_argument("--out-json")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("selftest")
    p.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
