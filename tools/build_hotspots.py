#!/usr/bin/env python3
"""The hotspot table's writer (milestone resources-enemies; ARCHITECTURE.md milestone contract 9).

  python tools/build_hotspots.py emit     write terra-nauvis/prototypes/tables/hotspots.lua
  python tools/build_hotspots.py emit2    write terra-nauvis/prototypes/tables/hotspots_v2.lua
  python tools/build_hotspots.py emit3    write terra-nauvis/prototypes/tables/hotspots_v3.lua
  python tools/build_hotspots.py check    emit both in memory and compare with the committed tables
  python tools/build_hotspots.py list     the rows per map and resource, on each table

One row per adopted hotspot of data-src/approvals/approvals-data.json (APPROVALS 2 and 3: strength 2
or 3 with the centre inside the map's extent, offshore fields included), keyed by the id of the region
layer's hotspot row that holds its disc (prototypes/tables/regions.lua; the same slug of the
approval id), with what the resource bodies need beside that disc:
  resource, strength   the hotspot's resource and R7a's strength (the target's multiplier)
  mult                 the biter multiplier inside the disc (APPROVALS 1b; the region row's)
  radius_px, cap_px    the disc radius r and r + the city margin (APPROVALS 2: a floor at small
                       scales stops there, short of the city-removal distance), in reference pixels at
                       the approval data's km per pixel
  share                per map, the disc's land share at the adopted centre (water share for an
                       offshore field) from the reference land mask, computed offline by the approval
                       builder (decision 16; FEAS-12): each target scales by it
  offshore             an offshore field (APPROVALS 3): its disc is stamped to deepwater
and each map's whole-pixel offset into the region frame (build_regions.map_offset), which moves the
region layer's jittered centres onto the map's own chain for the offshore stamps.

The table is cross-checked against the region table: every hotspot row there has a row here with
the same resource, maps and radius, and nothing more. An approval edit is an edit of
approvals-data.json and a rerun of `emit` here and in build_regions.py; the static gate row re-emits
the table and fails on any difference. No numpy: `earth_test.py static` imports this module.

The second table, hotspots_v2.lua, is the rows of data-src/hotspots/hotspots-v2.json: new worlds read the first
table's rows it keeps and these, through the bodies of prototypes/expressions/hotspots_v2.lua. A row here holds its
region fields too, since a released region table never changes, and the file lists the first table's rows it retires
and each row's rivals, which this writer works out: a row gives way to each smaller row of another ore whose disc
can touch its own on a shared map, and always to an offshore field, whose body is the first table's. The land
shares are computed offline from data-src/earthmaps/<map>-land.png and stored in the json. A row whose reach (radius,
jitter, the city margin) holds a spawn city of one of its maps fails: no field stands at a start. A row's least_tiles,
where the json gives one, is the least its ore footprint reaches in tiles at any scale: at scale 1 the floor of 48
tiles is no wider than a regular ore patch. The enemy layer keeps to the footprint without it.

The third table, hotspots_v3.lua, is the rows of data-src/hotspots/hotspots-v3.json: rows that move off the sea or the
lake onto land (new ids, so every released region body stays), the ids they retire from the first two tables, per row
the factor `rich` raises a small disc's ore per tile by (at most 3), and the rivals of the whole set. A row may carry
its own jitter_km, so a coastal disc stays on land over its jitter.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_regions  # noqa: E402
import tnconfig  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
TABLE = MOD / "prototypes" / "tables" / "hotspots.lua"
APPROVALS = REPO / "data-src" / "approvals" / "approvals-data.json"
TABLE2 = MOD / "prototypes" / "tables" / "hotspots_v2.lua"
ROWS2 = REPO / "data-src" / "hotspots" / "hotspots-v2.json"
TABLE3 = MOD / "prototypes" / "tables" / "hotspots_v3.lua"
ROWS3 = REPO / "data-src" / "hotspots" / "hotspots-v3.json"
RICH_MAX = 3   # the most a row's ore per tile may be raised over the table's rule

TOOL_VERSION = 1
OFFSHORE = "offshore-oil"
STRENGTHS = (2, 3)
STRENGTHS2 = (2, 3, 4, 5)
MAX_COLUMNS = build_regions.MAX_COLUMNS
FIELD_ORDER = ("id", "resource", "strength", "mult", "radius_px", "cap_px")
FIELD_ORDER2 = ("id", "layer", "shape", "warp", "mult", "resource", "lat", "lon", "radius_km", "jitter_km", "phase",
                "strength", "radius_px", "cap_px")
PX_PER_DEGREE = 45
RIVAL_JITTER = 0.5   # config.lua regions.jitter.hotspot_share: the share of a row's jitter its disc can move
DIGITS = 6


class HotspotError(ValueError):
    pass


def km_per_px(appr):
    return float(appr["rules"]["km_per_px"])


def derive(cfg, appr):
    """The table's rows (approval order) and the maps' frame offsets."""
    kpp = km_per_px(appr)
    if abs(build_regions.km_per_px(cfg) - kpp) > 1e-9:
        raise HotspotError(f"config.lua regions.km_per_px differs from approvals-data.json rules.km_per_px {kpp}")
    margin = float(appr["rules"]["city_margin_km"])
    rows = []
    for h in appr["hotspots"]:
        maps = build_regions.adopted_maps(cfg, h.get("adopted"))
        if not maps:
            continue
        if int(h["strength"]) not in STRENGTHS:
            raise HotspotError(f"{h['id']} is adopted at strength {h['strength']}; APPROVALS 2 adopts 2 and 3 only")
        offshore = h["resource"] == OFFSHORE
        share = {}
        for mk in maps:
            s = (h.get("surface") or {}).get(mk) or {}
            key = "water_share_in_disc" if offshore else "land_share_in_disc"
            if not isinstance(s.get(key), (int, float)):
                raise HotspotError(f"{h['id']} has no {key} on {mk} in approvals-data.json")
            share[mk] = round(float(s[key]), DIGITS)
        rows.append({"id": build_regions.slug(h["id"]), "resource": h["resource"], "strength": int(h["strength"]),
                     "mult": build_regions.ENEMY_MULT,
                     "radius_px": round(float(h["radius_km"]) / kpp, DIGITS),
                     "cap_px": round((float(h["radius_km"]) + margin) / kpp, DIGITS),
                     "maps": maps, "share": share, "offshore": offshore,
                     "source": f"approvals-data.json hotspots {h['id']} (APPROVALS {3 if offshore else 2}; R7a)"})
    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise HotspotError(f"duplicate hotspot ids {dup}")
    offsets = {mk: list(build_regions.map_offset(cfg, mk)) for mk in cfg["map_order"]}
    return rows, offsets


def lua_num(v):
    return build_regions.lua_num(v)


def lua_str(s):
    return build_regions.lua_str(s)


def emit_row(r, map_order):
    ind = "    "
    inner = ind + "  "
    out = [ind + "{"]
    scalars = []
    for k in FIELD_ORDER:
        v = r[k]
        scalars.append(f"{k} = {lua_str(v) if isinstance(v, str) else lua_num(v)}")
    scalars.append(f"offshore = {'true' if r['offshore'] else 'false'}")
    out += build_regions.wrap_items(scalars, inner)
    out += build_regions.wrap_items(["maps = {" + ", ".join(lua_str(m) for m in r["maps"]) + "}"], inner)
    out += build_regions.wrap_items(["share = {" + ", ".join(f"{m} = {lua_num(r['share'][m])}" for m in map_order
                                                             if m in r["share"]) + "}"], inner)
    out.append(inner + "source = " + lua_str(r["source"]) + ",")
    out.append(ind + "},")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise HotspotError(f"row {r['id']}: a line of {len(line)} columns")
    return out


HEADER = """\
-- Hotspot rows (ARCHITECTURE.md slice contract 9; APPROVALS 2 and 3; S6; slice resources-enemies).
-- Written by tools/build_hotspots.py (writer {tool}) from
--   data-src/approvals/approvals-data.json sha256 {appr}
-- Never edit by hand: an approval edit is an edit of approvals-data.json, then
-- `python tools/build_hotspots.py emit` (and build_regions.py emit for the discs); the static gate row
-- re-emits this file and fails on a difference.
--
-- Pure data, like config.lua. Each row's disc is the region layer's hotspot row of the same id
-- (prototypes/tables/regions.lua), jittered per seed there; prototypes/expressions/resources.lua and
-- enemies.lua read that disc through the region layer's interface names and build each resource's
-- hotspot spots, the offshore field stamps and the enemy layer from these rows.
-- Fields: id (the region row's id); resource; strength (R7a, the target's multiplier); mult (biters
-- inside the disc); radius_px and cap_px (the disc radius and the radius plus the city margin, in
-- reference pixels: a footprint's floor stops at cap); offshore (a field stamped to deepwater); maps
-- (the maps that adopt it); share (per map, the disc's land share, water share for a field, from the
-- reference land mask). frame_offset: each map's whole-pixel offset into the region frame.
"""


def emit_text(rows, offsets, appr_sha, map_order):
    out = HEADER.format(tool=TOOL_VERSION, appr=appr_sha).splitlines()
    out += ["return {", "  rows = {"]
    for r in rows:
        out += emit_row(r, map_order)
    out += ["  },", "  frame_offset = {"]
    for mk in map_order:
        du, dv = offsets[mk]
        out.append(f"    {mk} = {{{lua_num(du)}, {lua_num(dv)}}},")
    out += ["  },", "}"]
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise HotspotError(f"a line of {len(line)} columns")
    return "\n".join(out) + "\n"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(cfg=None, appr_path=APPROVALS):
    cfg = cfg or tnconfig.load()
    appr = json.loads(Path(appr_path).read_text(encoding="utf-8"))
    rows, offsets = derive(cfg, appr)
    return rows, offsets, emit_text(rows, offsets, sha256(appr_path), cfg["map_order"])


def row_problems(r, map_keys, strengths=STRENGTHS):
    out = []
    if not isinstance(r, dict):
        return ["a row is not a keyed table"]
    rid = r.get("id")
    if not isinstance(rid, str) or not rid or build_regions.slug(rid) != rid:
        out.append(f"id {rid!r} is not lower-case letters, digits and single underscores")
    if not isinstance(r.get("resource"), str) or not r["resource"]:
        out.append("resource is not a name")
    if r.get("strength") not in strengths:
        out.append(f"strength {r.get('strength')!r} is not one of {strengths}")
    for k in ("mult", "radius_px", "cap_px"):
        if not isinstance(r.get(k), (int, float)) or isinstance(r.get(k), bool) or r[k] <= 0:
            out.append(f"{k} is not a positive number")
    if isinstance(r.get("radius_px"), (int, float)) and isinstance(r.get("cap_px"), (int, float)) and \
            r["cap_px"] < r["radius_px"]:
        out.append("cap_px is below radius_px")
    if not isinstance(r.get("offshore"), bool) or r["offshore"] != (r.get("resource") == OFFSHORE):
        out.append("offshore is not true exactly for the offshore-oil rows")
    maps = r.get("maps")
    if not isinstance(maps, list) or not maps or set(maps) - set(map_keys):
        out.append("maps is not a list of map keys")
    share = r.get("share")
    if not isinstance(share, dict) or set(share) != set(maps or []) or \
            not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in share.values()):
        out.append("share is not a share in [0, 1] for exactly the row's maps")
    return out


def load_table(path=TABLE, cfg=None):
    """(rows, frame offsets) of the committed table (tnconfig's pure-data loader), validated."""
    cfg = cfg or tnconfig.load()
    data = tnconfig.load(path)
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HotspotError(f"{path}: no rows list")
    for r in rows:
        problems = row_problems(r, cfg["map_order"])
        if problems:
            raise HotspotError(f"{path}: row {r.get('id')!r}: {problems[0]}")
    offsets = data.get("frame_offset")
    if not isinstance(offsets, dict) or set(offsets) != set(cfg["map_order"]):
        raise HotspotError(f"{path}: frame_offset must hold every map key")
    return rows, offsets


def region_findings(rows, region_rows, cfg):
    """The table against the region table's hotspot rows: the same ids, resources, maps and radii."""
    kpp = build_regions.km_per_px(cfg)
    have = {r["id"]: r for r in region_rows if r.get("layer") == "hotspot"}
    out = []
    for r in rows:
        g = have.pop(r["id"], None)
        if g is None:
            out.append(f"hotspot {r['id']} has no hotspot row in the region table")
            continue
        if g.get("resource") != r["resource"]:
            out.append(f"hotspot {r['id']}: resource {r['resource']}, the region row's {g.get('resource')}")
        if list(g.get("maps") or []) != list(r["maps"]):
            out.append(f"hotspot {r['id']}: maps {r['maps']}, the region row's {g.get('maps')}")
        if abs(float(g.get("radius_km", 0)) / kpp - r["radius_px"]) > 10 ** -DIGITS:
            out.append(f"hotspot {r['id']}: radius {r['radius_px']} px, the region row's {g.get('radius_km')} km")
        if g.get("mult") != r["mult"]:
            out.append(f"hotspot {r['id']}: mult {r['mult']}, the region row's {g.get('mult')}")
    for rid in sorted(have):
        out.append(f"the region table's hotspot row {rid} has no row in the hotspot table")
    return out


def table_findings(cfg=None, path=TABLE):
    """Findings of the committed table: a fresh emission and the region table's hotspot rows."""
    cfg = cfg or tnconfig.load()
    f = check_table(path, cfg)
    try:
        rows, _ = load_table(path, cfg)
        f += region_findings(rows, build_regions.load_table(), cfg)
    except (HotspotError, build_regions.RegionError, tnconfig.ConfigError) as e:
        f.append(str(e))
    return f


def check_table(path=TABLE, cfg=None):
    """Findings of the committed table against a fresh emission (empty when byte-identical)."""
    _, _, text = build(cfg)
    try:
        have = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    if have != text:
        a, b = have.splitlines(), text.splitlines()
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        return [f"{Path(path).name} differs from a fresh emission at line {i + 1}: rerun python tools/build_hotspots.py "
                f"emit (committed {a[i] if i < len(a) else '<end>'!r}, emitted {b[i] if i < len(b) else '<end>'!r})"]
    return []


def derive2(cfg, appr, data, first):
    """The second table's rows, the ids it retires from the first (rows `first`) and every kept row's rivals."""
    kpp = km_per_px(appr)
    margin = float(appr["rules"]["city_margin_km"])
    share_j = float(appr["rules"]["jitter_fraction"])
    rows = []
    for h in data["rows"]:
        rid = build_regions.slug(h["id"])
        maps = [m for m in cfg["map_order"] if m in h["maps"]]
        rkm = float(h["radius_km"])
        if h["resource"] == OFFSHORE:
            raise HotspotError(f"{rid}: an offshore field stays on the first table's stamps")
        share = {m: round(float(h["land_share"][m]), DIGITS) for m in maps}
        row = {"id": rid, "layer": "hotspot", "shape": "disc", "warp": 0, "mult": build_regions.ENEMY_MULT,
               "resource": h["resource"], "lat": float(h["lat"]), "lon": float(h["lon"]), "radius_km": rkm,
               "jitter_km": rkm * share_j, "phase": build_regions.phase_of(rid), "strength": int(h["strength"]),
               "radius_px": round(rkm / kpp, DIGITS), "cap_px": round((rkm + margin) / kpp, DIGITS),
               "offshore": False, "maps": maps, "share": share,
               "source": f"hotspots-v2.json {h['id']} (deposits-research.md)"}
        if "least_tiles" in h:
            row["least_tiles"] = int(h["least_tiles"])
        rows.append(row)
    retired = [build_regions.slug(i) for i in data.get("retired", [])]
    have = {r["id"] for r in first}
    for rid in retired:
        if rid not in have:
            raise HotspotError(f"hotspots-v2.json retires {rid}, which the first table does not hold")
    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1 or i in have})
    if dup:
        raise HotspotError(f"hotspots-v2.json ids {dup} repeat: a row of its own needs a name of its own")
    reranked = {}
    for hid, s in data.get("reranked", {}).items():
        rid = build_regions.slug(hid)
        if rid not in have or rid in retired or s not in STRENGTHS2:
            raise HotspotError(f"hotspots-v2.json reranks {rid}, not a kept row of the first table at a strength it allows")
        reranked[rid] = s
    return rows, retired, reranked


def load_rows2(path=TABLE, path2=TABLE2, cfg=None):
    """(rows a new world reads, frame offsets, the second table's rows): the first table's kept rows at their strength
    on the second table, then the second table's."""
    cfg = cfg or tnconfig.load()
    first, offsets = load_table(path, cfg)
    data = tnconfig.load(path2)
    rows = [dict(r, strength=data["strength"].get(r["id"], r["strength"])) for r in first if r["id"] not in data["retired"]]
    return rows + list(data["rows"]), offsets, list(data["rows"])


def rivals_of(rows, kpp):
    """{row id: the rows it gives way to}, over rows carrying lat, lon, cap_px, jitter_km, maps and offshore."""
    out = {}
    most = lambda r: max(r["cap_px"], r.get("least_tiles", 0))
    outer = lambda r: most(r) + r["jitter_km"] * RIVAL_JITTER / kpp
    for a in rows:
        if a["offshore"]:
            continue
        for b in rows:
            if a is b or a["resource"] == b["resource"] or not set(a["maps"]) & set(b["maps"]):
                continue
            du, dv = (a["lon"] - b["lon"]) * PX_PER_DEGREE, (a["lat"] - b["lat"]) * PX_PER_DEGREE
            if du * du + dv * dv > (outer(a) + outer(b)) ** 2:
                continue
            if b["offshore"] or most(b) < most(a) or (most(b) == most(a) and b["id"] < a["id"]):
                out.setdefault(a["id"], []).append(b["id"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def city_findings(rows, cfg, appr):
    """Each row whose reach holds a spawn city of one of its maps (APPROVALS' city rule, on map distance)."""
    kpp = km_per_px(appr)
    margin = float(appr["rules"]["city_margin_km"])
    out = []
    for mk, table in city_tables().items():
        for r in rows:
            if mk not in r["maps"]:
                continue
            reach = max(r["radius_km"] + margin, r.get("least_tiles", 0) * kpp) + r["jitter_km"] * RIVAL_JITTER
            for key, c in table.items():
                d = math.hypot(c["lon"] - r["lon"], c["lat"] - r["lat"]) * PX_PER_DEGREE * kpp
                if d <= reach:
                    out.append(f"hotspot {r['id']} holds {c['name']} on {mk}: {d:.0f} km, its reach {reach:.0f} km")
    return out


def city_tables():
    """{map key: {city key: {name, lon, lat}}} of the spawn city files."""
    out = {}
    for name in ("cities.lua", "cities_atlantic.lua", "cities_olde_world.lua"):
        data = tnconfig.load(MOD / "prototypes" / "tables" / name)
        for mk, t in data.items():
            out[mk] = t["cities"]
    return out


def build2(cfg=None, appr_path=APPROVALS, rows_path=ROWS2):
    cfg = cfg or tnconfig.load()
    appr = json.loads(Path(appr_path).read_text(encoding="utf-8"))
    data = json.loads(Path(rows_path).read_text(encoding="utf-8"))
    first, _ = derive(cfg, appr)
    regions = {r["id"]: r for r in build_regions.load_table() if r.get("layer") == "hotspot"}
    rows, retired, reranked = derive2(cfg, appr, data, first)
    kept = [dict(r, lat=regions[r["id"]]["lat"], lon=regions[r["id"]]["lon"], jitter_km=regions[r["id"]]["jitter_km"])
            for r in first if r["id"] not in retired]
    rivals = rivals_of(kept + rows, km_per_px(appr))
    text = emit_text2(rows, retired, reranked, rivals, sha256(rows_path), cfg["map_order"])
    return rows, retired, rivals, text


def emit_row2(r, map_order):
    ind = "    "
    inner = ind + "  "
    out = [ind + "{"]
    scalars = []
    for k in FIELD_ORDER2:
        v = r[k]
        scalars.append(f"{k} = {lua_str(v) if isinstance(v, str) else lua_num(v)}")
    if "least_tiles" in r:
        scalars.append(f"least_tiles = {lua_num(r['least_tiles'])}")
    scalars.append("offshore = false")
    out += build_regions.wrap_items(scalars, inner)
    out += build_regions.wrap_items(["maps = {" + ", ".join(lua_str(m) for m in r["maps"]) + "}"], inner)
    out += build_regions.wrap_items(["share = {" + ", ".join(f"{m} = {lua_num(r['share'][m])}" for m in map_order
                                                             if m in r["share"]) + "}"], inner)
    out.append(inner + "source = " + lua_str(r["source"]) + ",")
    out.append(ind + "},")
    return out


HEADER2 = """\
-- The second hotspot table (config.lua hotspots_v2; ARCHITECTURE.md, release versioning rule 14).
-- Written by tools/build_hotspots.py (writer {tool}) from
--   data-src/hotspots/hotspots-v2.json sha256 {src}
-- Never edit by hand: an edit is an edit of that file, then `python tools/build_hotspots.py emit2`; the static gate
-- row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua. rows: the rows new worlds read beside the first table's they keep, each with the
-- region fields of prototypes/tables/regions.lua (a released table) and the first table's hotspot fields, where
-- strength runs to 5. retired: the first table's rows new worlds do not read. strength: the first table's rows new
-- worlds read at another strength. rivals: per row, the rows of another ore whose footprints it keeps out of.
-- least_tiles, on a row that has one: the least its ore footprint reaches in tiles at any scale.
"""


def emit_text2(rows, retired, reranked, rivals, src_sha, map_order):
    out = HEADER2.format(tool=TOOL_VERSION, src=src_sha).splitlines()
    out += ["return {", "  rows = {"]
    for r in rows:
        out += emit_row2(r, map_order)
    out += ["  },"]
    out += build_regions.wrap_items(["retired = {" + ", ".join(lua_str(i) for i in retired) + "}"], "  ")
    out += ["  strength = {"]
    for k, v in sorted(reranked.items()):
        out.append(f"    {k} = {v},")
    out += ["  },", "  rivals = {"]
    for k, v in rivals.items():
        out += build_regions.wrap_items([f"{k} = {{" + ", ".join(lua_str(i) for i in v) + "}"], "    ")
    out += ["  },", "}"]
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise HotspotError(f"a line of {len(line)} columns: {line[:60]}")
    return "\n".join(out) + "\n"


def table2_findings(cfg=None, path=TABLE2):
    """Findings of the second table: a fresh emission, its rows' shapes and the spawn cities."""
    cfg = cfg or tnconfig.load()
    try:
        rows, retired, rivals, text = build2(cfg)
    except (HotspotError, tnconfig.ConfigError, OSError, KeyError, ValueError) as e:
        return [f"hotspots-v2.json: {e}"]
    try:
        have = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    out = []
    if have != text:
        out.append(f"{Path(path).name} differs from a fresh emission: rerun python tools/build_hotspots.py emit2")
    for r in rows:
        problems = row_problems(r, cfg["map_order"], STRENGTHS2)
        if problems:
            out.append(f"row {r['id']}: {problems[0]}")
    appr = json.loads(APPROVALS.read_text(encoding="utf-8"))
    return out + city_findings(rows, cfg, appr)


def derive3(cfg, appr, data, first, rows2, retired2):
    """The third table's rows, the ids it retires and the per-tile factors, over the first two tables' kept rows."""
    kpp = km_per_px(appr)
    margin = float(appr["rules"]["city_margin_km"])
    share_j = float(appr["rules"]["jitter_fraction"])
    live = {r["id"] for r in first if r["id"] not in retired2} | {r["id"] for r in rows2}
    rows = []
    for h in data["rows"]:
        rid = build_regions.slug(h["id"])
        maps = [m for m in cfg["map_order"] if m in h["maps"]]
        rkm = float(h["radius_km"])
        share = {m: round(float(h["land_share"][m]), DIGITS) for m in maps}
        jit = float(h["jitter_km"]) if "jitter_km" in h else rkm * share_j
        row = {"id": rid, "layer": "hotspot", "shape": "disc", "warp": 0, "mult": build_regions.ENEMY_MULT,
               "resource": h["resource"], "lat": float(h["lat"]), "lon": float(h["lon"]), "radius_km": rkm,
               "jitter_km": jit, "phase": build_regions.phase_of(rid), "strength": int(h["strength"]),
               "radius_px": round(rkm / kpp, DIGITS), "cap_px": round((rkm + margin) / kpp, DIGITS),
               "offshore": False, "maps": maps, "share": share,
               "source": f"hotspots-v3.json {h['id']} (a moved row)"}
        if "least_tiles" in h:
            row["least_tiles"] = int(h["least_tiles"])
        rows.append(row)
    retired = [build_regions.slug(i) for i in data.get("retired", [])]
    for rid in retired:
        if rid not in live:
            raise HotspotError(f"hotspots-v3.json retires {rid}, which the first two tables do not hold")
    ids = [r["id"] for r in rows]
    taken = live | {r["id"] for r in first}
    dup = sorted({i for i in ids if ids.count(i) > 1 or i in taken})
    if dup:
        raise HotspotError(f"hotspots-v3.json ids {dup} repeat: a row of its own needs a name of its own")
    rich = {}
    final = (live - set(retired)) | set(ids)
    for hid, pairs in data.get("rich", {}).items():
        rid = build_regions.slug(hid)
        ok = rid in final and isinstance(pairs, list) and pairs
        for pair in pairs if ok else []:
            m, upto = pair
            ok = ok and isinstance(m, (int, float)) and not isinstance(m, bool) and 1 < m <= RICH_MAX and                 isinstance(upto, int) and upto >= 0
        if not ok:
            raise HotspotError(f"hotspots-v3.json rich {rid}: not a live row at pairs of [a factor over 1 and up to "
                               f"{RICH_MAX}, the largest scale it applies at (0 for every scale)]")
        total = 1.0
        for m, _ in pairs:
            total *= m
        if total > RICH_MAX * RICH_MAX:
            raise HotspotError(f"hotspots-v3.json rich {rid}: the factors multiply past {RICH_MAX * RICH_MAX}")
        rich[rid] = [(float(m), upto) for m, upto in pairs]
    return rows, retired, rich


def build3(cfg=None, appr_path=APPROVALS, rows_path=ROWS3, rows2_path=ROWS2):
    cfg = cfg or tnconfig.load()
    appr = json.loads(Path(appr_path).read_text(encoding="utf-8"))
    data2 = json.loads(Path(rows2_path).read_text(encoding="utf-8"))
    data3 = json.loads(Path(rows_path).read_text(encoding="utf-8"))
    first, _ = derive(cfg, appr)
    regions = {r["id"]: r for r in build_regions.load_table() if r.get("layer") == "hotspot"}
    rows2, retired2, _ = derive2(cfg, appr, data2, first)
    rows3, retired3, rich = derive3(cfg, appr, data3, first, rows2, retired2)
    kept = [dict(r, lat=regions[r["id"]]["lat"], lon=regions[r["id"]]["lon"], jitter_km=regions[r["id"]]["jitter_km"])
            for r in first if r["id"] not in retired2 and r["id"] not in retired3]
    kept += [r for r in rows2 if r["id"] not in retired3]
    rivals = rivals_of(kept + rows3, km_per_px(appr))
    text = emit_text3(rows3, retired3, rich, rivals, sha256(rows_path), cfg["map_order"])
    return rows3, retired3, rivals, text


HEADER3 = """\
-- The third hotspot table (config.lua hotspots_v3; ARCHITECTURE.md, release versioning rule 14).
-- Written by tools/build_hotspots.py (writer {tool}) from
--   data-src/hotspots/hotspots-v3.json sha256 {src}
-- Never edit by hand: an edit is an edit of that file, then `python tools/build_hotspots.py emit3`; the static gate
-- row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua. rows: rows of the first two tables moved onto land, each with the region fields of
-- prototypes/tables/regions.lua and the hotspot fields of the second table. retired: the ids of the first two tables
-- this table's readers do not read. rich: per row, the factor its ore per tile is raised by over the rule's, so a
-- small disc holds its design total in the room it has. rivals: per row of the whole set, the rows of another ore
-- whose footprints it keeps out of.
"""


def emit_text3(rows, retired, rich, rivals, src_sha, map_order):
    out = HEADER3.format(tool=TOOL_VERSION, src=src_sha).splitlines()
    out += ["return {", "  rows = {"]
    for r in rows:
        out += emit_row2(r, map_order)
    out += ["  },"]
    out += ["  retired = {"]
    out += build_regions.wrap_items([lua_str(i) for i in retired], "    ")
    out += ["  },", "  rich = {"]
    for k, pairs in sorted(rich.items()):
        out.append(f"    {k} = {{" + ", ".join(f"{{{lua_num(m)}, {upto}}}" for m, upto in pairs) + "},")
    out += ["  },", "  rivals = {"]
    for k, v in rivals.items():
        out += build_regions.wrap_items([f"{k} = {{" + ", ".join(lua_str(i) for i in v) + "}"], "    ")
    out += ["  },", "}"]
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise HotspotError(f"a line of {len(line)} columns: {line[:60]}")
    return "\n".join(out) + "\n"


def table3_findings(cfg=None, path=TABLE3):
    """Findings of the third table: a fresh emission, its rows' shapes and the spawn cities."""
    cfg = cfg or tnconfig.load()
    try:
        rows, retired, rivals, text = build3(cfg)
    except (HotspotError, tnconfig.ConfigError, OSError, KeyError, ValueError) as e:
        return [f"hotspots-v3.json: {e}"]
    try:
        have = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    out = []
    if have != text:
        out.append(f"{Path(path).name} differs from a fresh emission: rerun python tools/build_hotspots.py emit3")
    for r in rows:
        problems = row_problems(r, cfg["map_order"], STRENGTHS2)
        if problems:
            out.append(f"row {r['id']}: {problems[0]}")
    appr = json.loads(APPROVALS.read_text(encoding="utf-8"))
    return out + city_findings(rows, cfg, appr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit")
    sub.add_parser("emit2")
    sub.add_parser("emit3")
    sub.add_parser("check")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            rows, _, text = build()
            TABLE.parent.mkdir(parents=True, exist_ok=True)
            TABLE.write_text(text, encoding="utf-8", newline="\n")
            print(f"RESULT ok emitted {len(rows)} rows to {TABLE.relative_to(REPO).as_posix()} sha256 {sha256(TABLE)}")
            return 0
        if a.cmd == "emit2":
            rows, retired, rivals, text = build2()
            TABLE2.write_text(text, encoding="utf-8", newline="\n")
            print(f"RESULT ok emitted {len(rows)} rows, {len(retired)} retired, {len(rivals)} with rivals, to "
                  f"{TABLE2.relative_to(REPO).as_posix()} sha256 {sha256(TABLE2)}")
            return 0
        if a.cmd == "emit3":
            rows, retired, rivals, text = build3()
            TABLE3.write_text(text, encoding="utf-8", newline="\n")
            print(f"RESULT ok emitted {len(rows)} rows, {len(retired)} retired, {len(rivals)} with rivals, to "
                  f"{TABLE3.relative_to(REPO).as_posix()} sha256 {sha256(TABLE3)}")
            return 0
        if a.cmd == "check":
            f = table_findings() + table2_findings() + table3_findings()
            print(f"RESULT {'ok' if not f else 'fail'} table check{': ' + f[0] if f else ''}")
            return 0 if not f else 1
        cfg = tnconfig.load()
        rows, _ = load_table(cfg=cfg)
        for mk in cfg["map_order"]:
            on = [r for r in rows if mk in r["maps"]]
            by = {}
            for r in on:
                by[r["resource"]] = by.get(r["resource"], 0) + 1
            print(f"{mk}: {len(on)} hotspots; " + ", ".join(f"{k} {v}" for k, v in by.items()))
        print(f"RESULT ok {len(rows)} rows")
        return 0
    except (HotspotError, build_regions.RegionError, tnconfig.ConfigError, OSError, KeyError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
