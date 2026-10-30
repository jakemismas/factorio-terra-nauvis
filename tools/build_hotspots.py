#!/usr/bin/env python3
"""The hotspot table's writer (milestone resources-enemies; ARCHITECTURE.md milestone contract 9).

  python tools/build_hotspots.py emit     write terra-nauvis/prototypes/tables/hotspots.lua
  python tools/build_hotspots.py check    emit in memory and compare with the committed table
  python tools/build_hotspots.py list     the rows per map and resource

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
"""
import argparse
import hashlib
import json
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

TOOL_VERSION = 1
OFFSHORE = "offshore-oil"
STRENGTHS = (2, 3)
MAX_COLUMNS = build_regions.MAX_COLUMNS
FIELD_ORDER = ("id", "resource", "strength", "mult", "radius_px", "cap_px")
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


def row_problems(r, map_keys):
    out = []
    if not isinstance(r, dict):
        return ["a row is not a keyed table"]
    rid = r.get("id")
    if not isinstance(rid, str) or not rid or build_regions.slug(rid) != rid:
        out.append(f"id {rid!r} is not lower-case letters, digits and single underscores")
    if not isinstance(r.get("resource"), str) or not r["resource"]:
        out.append("resource is not a name")
    if r.get("strength") not in STRENGTHS:
        out.append(f"strength {r.get('strength')!r} is not one of {STRENGTHS}")
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit")
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
        if a.cmd == "check":
            f = table_findings()
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
