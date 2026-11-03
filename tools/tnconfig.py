#!/usr/bin/env python3
"""Read terra-nauvis/prototypes/config.lua into Python without a Lua interpreter.

config.lua is the single source of every name and constant the mod defines (ARCHITECTURE.md,
"Module map"). The settings, data and control stages `require` it; the Python tools read the same
file here, through luaparser 4.2.0 (the T16 syntax floor), so no second copy of a name exists.

Only a pure-data subset of Lua is accepted, and anything else fails closed:
  local NAME = <expr>            (one target, one value)
  return <expr>                  (the chunk's last statement)
  <expr> := nil | true | false | number | string | table constructor | NAME | expr.field |
            expr[expr] | expr .. expr | expr + - * / % ^ expr | -expr | (expr)
Function calls, globals, assignments to fields and every other statement raise ConfigError, which
is what "pure data" means for this file.

Lua tables become dicts when they have any keyed field, lists when every field is positional.
Numbers keep Lua's value (an integral float such as 6.0 is returned as the int 6). A loaded table
remembers its file (Config.source), so the accessors read the region table beside the config.lua
they were given, in a staged mod copy as in the repo.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "terra-nauvis" / "prototypes" / "config.lua"


class ConfigError(ValueError):
    pass


class Config(dict):
    """A loaded pure-data table: a dict that also remembers the file it came from (None for a dict
    built in code, whose region table is then the repo's)."""
    source = None


def _ast():
    try:
        from luaparser import ast as lua_ast
        from luaparser import astnodes
    except ImportError as e:  # pragma: no cover - the manifest pins luaparser for CI
        raise ConfigError("luaparser is not installed; pip install -r tools/lint/requirements.txt") from e
    return lua_ast, astnodes


def _num(v):
    if isinstance(v, float) and v.is_integer() and abs(v) < 2 ** 53:
        return int(v)
    return v


class _Evaluator:
    def __init__(self, astnodes, where):
        self.n = astnodes
        self.where = where
        self.env = {}

    def fail(self, node, why):
        line = getattr(node, "line", None)
        raise ConfigError(f"{self.where}:{line or '?'}: {why} ({type(node).__name__}); config.lua is pure data")

    def eval(self, node):
        n = self.n
        if isinstance(node, n.Nil):
            return None
        if isinstance(node, n.TrueExpr):
            return True
        if isinstance(node, n.FalseExpr):
            return False
        if isinstance(node, n.Number):
            return _num(node.n)
        if isinstance(node, n.String):
            s = node.s
            return s.decode("utf-8") if isinstance(s, (bytes, bytearray)) else s
        if isinstance(node, n.Name):
            if node.id not in self.env:
                self.fail(node, f"unknown name {node.id!r} (only locals defined earlier in the file)")
            return self.env[node.id]
        if isinstance(node, n.Index):
            base = self.eval(node.value)
            if node.notation == n.IndexNotation.DOT:
                key = node.idx.id
            else:
                key = self.eval(node.idx)
            if isinstance(base, dict) and key in base:
                return base[key]
            if isinstance(base, list) and isinstance(key, int) and 1 <= key <= len(base):
                return base[key - 1]
            self.fail(node, f"no field {key!r}")
        if isinstance(node, n.Table):
            return self.table(node)
        if isinstance(node, n.Concat):
            a, b = self.eval(node.left), self.eval(node.right)
            if not all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in (a, b)):
                self.fail(node, "'..' needs strings or numbers")
            return self.lua_str(a) + self.lua_str(b)
        ops = {"AddOp": lambda a, b: a + b, "SubOp": lambda a, b: a - b, "MultOp": lambda a, b: a * b,
               "FloatDivOp": lambda a, b: a / b, "ModOp": lambda a, b: a % b, "ExpoOp": lambda a, b: a ** b}
        kind = type(node).__name__
        if kind in ops:
            a, b = self.eval(node.left), self.eval(node.right)
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a, b)):
                self.fail(node, "arithmetic needs numbers")
            if kind == "FloatDivOp":
                return _num(float(a) / float(b))
            return _num(ops[kind](a, b))
        if kind == "UMinusOp":
            v = self.eval(node.operand)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                self.fail(node, "unary minus needs a number")
            return _num(-v)
        self.fail(node, "unsupported expression")

    @staticmethod
    def lua_str(v):
        if isinstance(v, str):
            return v
        if isinstance(v, int):
            return str(v)
        return format(v, ".14g")

    def table(self, node):
        n = self.n
        keyed, positional = {}, []
        for f in node.fields:
            value = self.eval(f.value)
            if f.key is None:
                positional.append(value)
                continue
            if not f.between_brackets and isinstance(f.key, n.Name):
                key = f.key.id
            else:
                key = self.eval(f.key)
            if key in keyed:
                self.fail(f, f"duplicate key {key!r}")
            keyed[key] = value
        if keyed and positional:
            for i, v in enumerate(positional, 1):
                if i in keyed:
                    self.fail(node, f"positional field {i} clashes with a keyed field")
                keyed[i] = v
            return keyed
        return positional if not keyed else keyed

    def chunk(self, tree):
        n = self.n
        body = tree.body.body
        if not body or not isinstance(body[-1], n.Return):
            raise ConfigError(f"{self.where}: the chunk must end with 'return <table>'")
        for st in body[:-1]:
            if not isinstance(st, n.LocalAssign) or len(st.targets) != 1 or len(st.values) != 1:
                self.fail(st, "only 'local NAME = <expr>' statements may precede the return")
            name = st.targets[0].id
            if name in self.env:
                self.fail(st, f"local {name!r} defined twice")
            self.env[name] = self.eval(st.values[0])
        ret = body[-1]
        if len(ret.values) != 1:
            self.fail(ret, "return exactly one value")
        return self.eval(ret.values[0])


def parse_lua(text, where="<lua>"):
    """luaparser AST of a Lua chunk; ConfigError on a syntax error."""
    lua_ast, _ = _ast()
    try:
        return lua_ast.parse(text)
    except Exception as e:  # luaparser raises SyntaxException and friends
        raise ConfigError(f"{where}: Lua syntax error: {e}") from e


def _eval_text(text, path):
    tree = parse_lua(text, str(path))
    _, astnodes = _ast()
    data = _Evaluator(astnodes, path.name).chunk(tree)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the returned value is not a keyed table")
    out = Config(data)
    out.source = path.resolve()
    return out


def load(path=CONFIG):
    """The config table of a pure-data Lua file as Python data (a Config that remembers `path`)."""
    path = Path(path)
    return _eval_text(path.read_text(encoding="utf-8"), path)


def loads(text, where="<lua>", name=None):
    """The config table of pure-data Lua text (for example config.lua as a git ref holds it)."""
    tree = parse_lua(text, where)
    _, astnodes = _ast()
    data = _Evaluator(astnodes, name or where).chunk(tree)
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: the returned value is not a keyed table")
    return data


# The spawn-city table files (pure data, one keyed table each): cities.lua holds Europe's
# (spawn-cities) and each later map has a file of its own (cities_<map>.lua), so a landed file, and the
# spawn bearings generated from it, never change when a map is added. prototypes/city_tables.lua
# merges the same files in the game.
TABLES_DIR = REPO / "terra-nauvis" / "prototypes" / "tables"


def city_table_files(tables_dir=TABLES_DIR):
    """{map key: path of the table file that holds the map's newest version} over prototypes/tables/cities*.lua, as
    prototypes/city_tables.lua merges them (0.3.1: a map's next version is a file of its own); two files holding one
    map at the same version raise ConfigError."""
    out, ver = {}, {}
    for p in sorted(Path(tables_dir).glob("cities*.lua")):
        for key, tbl in load(p).items():
            v = tbl.get("version")
            if key in out and ver[key] == v:
                raise ConfigError(f"the spawn-city tables {out[key].name} and {p.name} both hold the map {key} at "
                                  f"version {v}")
            if key not in out or v > ver[key]:
                out[key], ver[key] = p, v
    return out


def city_tables(tables_dir=TABLES_DIR):
    """Every map's spawn-city table, {map key: {version, cities}}, merged from prototypes/tables/
    (city_table_files)."""
    return {key: load(p)[key] for key, p in city_table_files(tables_dir).items()}


# ------------------------------------------------------------------------------------------------ schema
#
# The shapes of config.lua's groups (ARCHITECTURE.md, the config.lua table). Every Python reader
# goes through these accessors, which raise ConfigError on a wrong shape instead of returning an
# empty set: a group that a check reads and silently finds empty would let that check pass while
# testing nothing. An empty Lua table loads as [] and counts as an empty table of either shape.


def _keyed(cfg, group):
    v = cfg.get(group, {})
    if v == []:
        return {}
    if not isinstance(v, dict):
        raise ConfigError(f"config.lua {group} must be a keyed table, not {type(v).__name__}")
    return v


def _listed(cfg, group, where=None):
    v = cfg.get(group, []) if where is None else where
    if v == {}:
        return []
    if not isinstance(v, list):
        raise ConfigError(f"config.lua {group} must be a list, not {type(v).__name__}")
    return v


def _names(v, where):
    if v == {}:
        v = []
    if not isinstance(v, list) or not all(isinstance(n, str) and n for n in v):
        raise ConfigError(f"config.lua {where} must be a list of names")
    return v


def map_keys(cfg):
    keys = _names(cfg.get("map_order", []), "map_order")
    if set(keys) != set(_keyed(cfg, "maps")):
        raise ConfigError("config.lua map_order must list exactly the keys of maps")
    return keys


def map_by_display(cfg):
    """{display name: map key}, e.g. {"Old World": "olde_world"} (the plan's tables name maps so)."""
    return {cfg["maps"][k]["display"]: k for k in map_keys(cfg)}


def firewall_names(cfg):
    """The fine field (design constraint 3): `firewall` is keyed by map key, each a list of the map's
    elevation entry and every term only it reads (from europe-coast on); the placeholder's
    `firewall` lists which of its name keys belong to the field (toolchain: elevation)."""
    out = set()
    maps = set(_keyed(cfg, "maps"))
    for key, names in _keyed(cfg, "firewall").items():
        if key not in maps:
            raise ConfigError(f"config.lua firewall.{key} is not a map key")
        out.update(_names(names, f"firewall.{key}"))
    ph = cfg.get("placeholder") or {}
    if ph:
        pnames = ph.get("names") or {}
        for k in _names(ph.get("firewall", []), "placeholder.firewall"):
            if k not in pnames:
                raise ConfigError(f"config.lua placeholder.firewall names {k!r}, which placeholder.names lacks")
            out.add(pnames[k])
    return sorted(out)


FALLBACK_FIELDS = {"name", "map_qualified", "frozen"}


def _fallback_entries(entries, where):
    """One geography version's Map type fallbacks, each {name = <noise name>, map_qualified = <bool>,
    frozen = <bool, optional>}, every name once."""
    entries = _listed(None, where, entries)
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("name"), str) or not e["name"] or \
                not isinstance(e.get("map_qualified"), bool) or set(e) - FALLBACK_FIELDS or \
                not isinstance(e.get("frozen", False), bool):
            raise ConfigError(f"config.lua {where} entries must be {{name = <noise name>, "
                              f"map_qualified = <bool>, frozen = <bool, optional>}}")
    names = [e["name"] for e in entries]
    if len(set(names)) != len(names):
        raise ConfigError(f"config.lua {where} lists a fallback name twice")
    return entries


def fallbacks(cfg):
    """The Map type fallbacks of every geography version, per map: {map key: [entry, ...]}, each
    name once, in version order (a version's `fallbacks` lists the per-save names its elevation
    entry reads, which a Map type pick leaves to prototype-level fallbacks valued as that version's
    preset bakes them), then the map's frame's (config.lua frames: its city offset names, frozen). A
    fallback without `frozen` (or false) mirrors a startup setting and is U3's
    one exemption, never registered; a frozen one is a constant body, registered like every Earth
    body, so no later version moves it. One prototype serves every map and version that lists a
    name, so each listing of it must carry the same flags (map_qualified, frozen)."""
    out, flags = {}, {}
    fr = frames(cfg)
    for key, versions in geography_versions(cfg).items():
        lst, seen = [], set()
        for v in versions + ([fr[key]] if key in fr else []):
            for e in v["fallbacks"]:
                f = (e["map_qualified"], bool(e.get("frozen")))
                if flags.setdefault(e["name"], f) != f:
                    raise ConfigError(f"config.lua lists the Map type fallback {e['name']} with different flags "
                                      f"(map_qualified, frozen) in two versions or maps: one prototype serves them all")
                if e["name"] not in seen:
                    seen.add(e["name"])
                    lst.append(e)
        out[key] = lst
    return out


def fallback_names(cfg):
    """Every Map type fallback's name, frozen or not."""
    return sorted({e["name"] for entries in fallbacks(cfg).values() for e in entries})


def exempt_fallback_names(cfg):
    """The fallbacks that mirror a startup setting (not frozen): U3's one exemption from
    tests/frozen.json."""
    return sorted({e["name"] for entries in fallbacks(cfg).values() for e in entries if not e.get("frozen")})


def frozen_fallback_names(cfg):
    """The frozen fallbacks: constants no setting moves, registered like every Earth body, so a world
    that reads one never moves with the mod (ARCHITECTURE.md, "Map type entries")."""
    return sorted({e["name"] for entries in fallbacks(cfg).values() for e in entries if e.get("frozen")})


# The noise names of one geography version, by role: its elevation entry, the bodies only it reads,
# its coarse land field, its coordinate chain and its city offset names.
GEOGRAPHY_NAMES = ("entry", "geo", "land_coarse", "detail", "far", "gx", "gy", "u", "v", "cx", "cy")
VERSION_FIELDS = set(GEOGRAPHY_NAMES) | {"geo_id", "city_offset", "start_mask", "fits", "fallbacks"}
# A version's optional fields: `spawn` (spawn-cities), the spawn at the chosen city, `waterways`
# (waterways), the map's waterway sets the version composes, bound to its chain, and `shore`
# (climate-tiles), the shore body its entry composes in place of the transfer: it reads the version's
# fit, detail and box, so it is the version's own and in its fine field; and `fields`
# (resources-enemies), the map-qualified per-save key of the map's offshore field stamp, which its entry
# composes last (a Map type fallback mirroring the hotspots setting; the stamp body reads the layer
# chain, so it is no version's own).
# (edge-and-lakes) `edge`, true when the version's far-field box carries the soft map edge
# (coast.edge_band), and `lakes`, the per-save inland lakes switch its entry reads its inland lakes
# through (a toggle's preset key; only with a spawn record).
OPTIONAL_VERSION_FIELDS = {"spawn", "waterways", "waterway_files", "mouths", "warp", "shore", "fields", "edge", "lakes", "over",
                           "basin", "scales"}
# A waterways record: per kind, the set names by scale. The sets read the version's chain, so they are
# its own: a later version that composes the waterways names sets of its own, and config.lua's
# waterways.sets[map] is the record of the map's newest version that has one.
WATERWAY_KINDS = ("ww", "canals", "dams", "fords")
# The fit bodies a version binds to generated files (tools/build_geo.py's bodies).
FIT_ROLES = ("geo", "land_coarse")
GENERATED_DIR = "prototypes/generated/"
# The fine field of a version (design constraint 3): its entry and every term only it reads.
FINE_ROLES = ("entry", "geo", "detail", "far")
# A version's spawn record (spawn-cities): the map's spawn-city setting (a settings key), the
# per-save city number (a Map type fallback that mirrors the setting), the resolved index control
# reads back at (0, 0), the spawn lake and starting-ore bias the start mask reads through the
# preset keys, the version's inland lakes, the start land guarantee, the distance body the preset
# redirects `distance` to, and the generated spawn bearings file. All of them, or no record.
SPAWN_FIELDS = ("city_setting", "city", "city_index", "spawn_lake", "spawn_bias", "inland_lakes", "start_land",
                "distance", "bearings")
SPAWN_NAMES = ("city", "city_index", "spawn_lake", "spawn_bias", "inland_lakes", "start_land", "distance")
# lake_floor (optional, true only): the version's inland lakes hold the floor off every spot (config.lua
# spawn.inland_lakes.floor), so the shore noise leaves no water specks; a version without it keeps its body.
SPAWN_OPTIONAL = ("lake_floor",)
# The spawn names that read the version's own chain: each version that has them takes its own (never
# shared with or re-pointed from another version); the other spawn bodies read no chain and may
# serve several versions, as a start mask version does.
SPAWN_OWN = ("inland_lakes",)
# The spawn names in the fine field (ARCHITECTURE.md, the firewall rule): the inland lakes and the
# start land guarantee, which only the entry reads.
SPAWN_FINE = ("inland_lakes", "start_land")


def spawn_of(version):
    """A geography version's spawn record, or None (europe-coast's version 1 has none)."""
    return version.get("spawn") or None


def waterways_of(version):
    """A geography version's waterways record ({kind: [set name by scale]}), or None."""
    return version.get("waterways") or None


def waterway_names(version):
    """Every waterway set name a version composes (they read its chain, so they are its own and in its
    fine field), in kind and scale order, and its mouth bodies; [] without a waterways record."""
    ww = waterways_of(version)
    return ([n for k in WATERWAY_KINDS for n in ww[k]] + list(version.get("mouths") or [])
            + list(version.get("warp") or [])) if ww else []


def version_scales(cfg, version):
    """The scales a geography version's own bodies serve, in the order of its waterway name lists: its `scales`, or
    the released list a landed version was built on, whose row never changes (config.lua scales)."""
    return [int(s) for s in version.get("scales") or cfg["scales"]["released"]]


def scale_extension(cfg, map_key, version):
    """The record of a released version's scales past its list (config.lua scale_extensions), or None."""
    x = (cfg.get("scale_extensions") or {}).get(map_key)
    return x if x and x["geo_id"] == version["geo_id"] else None


def extension_names(cfg, map_key, version):
    """The names a version's scale extension adds: its entry and sets."""
    x = scale_extension(cfg, map_key, version)
    return [x["entry"]] + waterway_names(x) if x else []


def scale_record(cfg, map_key, version, scale):
    """(record, position) of the record that serves a scale: the version, or its extension past a released
    version's list (presets.lua baked mirrors it). A scale neither serves reads the version's last position, as
    its frozen entry does."""
    s, own = int(scale), version_scales(cfg, version)
    x = scale_extension(cfg, map_key, version)
    if s in own:
        return version, own.index(s)
    if x and s in version_scales(cfg, x):
        return x, version_scales(cfg, x).index(s)
    return version, len(own) - 1


def shore_names(version):
    """A version's shore body (climate-tiles) as a one-name list, or []."""
    return [version["shore"]] if version.get("shore") else []


def fine_names(version):
    """A version's fine field: its entry, the bodies only it reads and, with a spawn record, the
    inland lakes and the start land guarantee; its waterway sets and its shore body."""
    sp = spawn_of(version)
    return ([version[n] for n in FINE_ROLES] + ([sp[n] for n in SPAWN_FINE] if sp else []) + waterway_names(version) +
            shore_names(version) + ([version["basin"]["name"]] if version.get("basin") else []))


def own_names(version):
    """The noise names a version takes as its own, which no other version may name: its
    GEOGRAPHY_NAMES and, with a spawn record, the spawn names that read its chain; its waterway sets
    and its shore body."""
    if version.get("over"):
        return [version["entry"], version["basin"]["name"]]
    sp = spawn_of(version)
    return ([version[n] for n in GEOGRAPHY_NAMES] + ([sp[n] for n in SPAWN_OWN] if sp else []) + waterway_names(version) +
            shore_names(version))


def _spawn_record(sp, where, cfg):
    if not isinstance(sp, dict) or set(sp) - set(SPAWN_OPTIONAL) != set(SPAWN_FIELDS):
        raise ConfigError(f"config.lua {where}.spawn must hold exactly {sorted(SPAWN_FIELDS)}, and optionally "
                          f"{sorted(SPAWN_OPTIONAL)}")
    if "lake_floor" in sp and sp["lake_floor"] is not True:
        raise ConfigError(f"config.lua {where}.spawn.lake_floor must be true or absent")
    for n in SPAWN_NAMES:
        if not isinstance(sp[n], str) or not sp[n]:
            raise ConfigError(f"config.lua {where}.spawn.{n} must be a noise name")
    b = sp["bearings"]
    if not (isinstance(b, str) and b.startswith(GENERATED_DIR) and b.endswith(".lua")):
        raise ConfigError(f"config.lua {where}.spawn.bearings must be a generated file ({GENERATED_DIR}<name>.lua)")
    settings = _keyed(cfg, "settings")
    s = settings.get(sp["city_setting"])
    random_value = ((cfg.get("spawn") or {}).get("random_value"))
    if not isinstance(s, dict) or s.get("type") != "string-setting":
        raise ConfigError(f"config.lua {where}.spawn.city_setting {sp['city_setting']!r} is not a string setting's key")
    vals = s.get("allowed_values") or []
    if not vals or vals[0] != random_value or len(set(vals)) != len(vals):
        raise ConfigError(f"config.lua {where}.spawn.city_setting {sp['city_setting']!r}: its allowed values must start "
                          f"with spawn.random_value {random_value!r} (the per-save number 0) and list each city once")
    return sp


def _waterways_record(ww, where, cfg, key, scales=None):
    """A waterways record holds one name per scale of its own version's list (config.lua `scales`)."""
    offered = [int(s) for s in ((cfg.get("scales") or {}).get("values")) or []]
    if scales is None or not scales or any(int(s) not in offered for s in scales):
        raise ConfigError(f"config.lua {where} needs its own `scales`, a list of offered scales {offered}")
    n = len(scales)
    if not isinstance(ww, dict) or set(ww) != set(WATERWAY_KINDS) or not all(
            isinstance(ww[k], list) and len(ww[k]) == n and all(isinstance(x, str) and x for x in ww[k])
            for k in WATERWAY_KINDS):
        raise ConfigError(f"config.lua {where}.waterways must map exactly {list(WATERWAY_KINDS)} to one set name per "
                          f"scale ({n})")
    return ww


def spawn_next_of(cfg, version):
    """The next spawn folds of a geography version (config.lua spawn_next, 0.3.1), or None: served, the number of
    cities the released folds serve, the next city offset names, spawn lake and bias, and their bearings file."""
    vs = ((cfg.get("spawn_next") or {}).get("versions")) or {}
    return vs.get(version.get("geo_id")) or vs.get(str(version.get("geo_id"))) or None


def city_number(cfg, version, value=None):
    """The per-save city number a version's preset bakes for a spawn-city setting value (default:
    the setting's default): the value's position in the setting's allowed values, random 0."""
    s = cfg["settings"][spawn_of(version)["city_setting"]]
    return s["allowed_values"].index(s["default_value"] if value is None else value)


def _offset_value(v):
    """A city offset the preset bakes: an integer (tiles) or the name of an expression that folds it."""
    return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, str) and bool(v))


def geography_versions(cfg):
    """`geography` is keyed by map key (europe-coast on), each {map_type_order, versions}: the order
    of the map's Map type entry, and every version of the map's elevation entry, oldest first and
    the newest last. A version is {geo_id, entry, geo, land_coarse, detail, far, gx, gy, u, v, cx,
    cy, city_offset, start_mask, fits = {geo, land_coarse}, fallbacks = {...}}: its geography
    release id (tn_geo, in the one id space across maps; id_space_problems), the noise names of its
    entry, the bodies only that entry reads, its coarse field, its chain and its city offset names,
    the offset its preset bakes there (integers, or names of expressions that fold it), the start
    mask its preset names, the generated file each fit body binds and the Map type fallbacks its
    entry reads, plus an optional spawn record (spawn-cities; SPAWN_FIELDS). No two versions of a map
    share a noise name of their own (own_names): a later version takes names of its own and never
    re-points an older one's (decision 21; ARCHITECTURE.md, "Map type entries", binding).
    {map key: [version, ...]}."""
    out = {}
    maps = set(_keyed(cfg, "maps"))
    for key, g in _keyed(cfg, "geography").items():
        if key not in maps:
            raise ConfigError(f"config.lua geography.{key} is not a map key")
        if not isinstance(g, dict) or set(g) != {"map_type_order", "versions"}:
            raise ConfigError(f"config.lua geography.{key} must hold exactly ['map_type_order', 'versions']")
        if not isinstance(g["map_type_order"], str) or not g["map_type_order"]:
            raise ConfigError(f"config.lua geography.{key}.map_type_order must be an order string")
        versions = _listed(None, f"geography.{key}.versions", g["versions"])
        if not versions:
            raise ConfigError(f"config.lua geography.{key}.versions must list at least one version")
        names = []
        for i, v in enumerate(versions, 1):
            where = f"geography.{key}.versions[{i}]"
            if not isinstance(v, dict) or set(v) - OPTIONAL_VERSION_FIELDS != VERSION_FIELDS:
                raise ConfigError(f"config.lua {where} must hold exactly {sorted(VERSION_FIELDS)}, and optionally "
                                  f"{sorted(OPTIONAL_VERSION_FIELDS)}")
            if "spawn" in v:
                _spawn_record(v["spawn"], where, cfg)
            if "waterways" in v:
                _waterways_record(v["waterways"], where, cfg, key, version_scales(cfg, v))
            if "waterway_files" in v and not (_positive_int(v["waterway_files"]) and "waterways" in v):
                raise ConfigError(f"config.lua {where}.waterway_files must be a version of the map's generated waterway "
                                  f"files, on a version with a waterways record")
            if "shore" in v and (not isinstance(v["shore"], str) or not v["shore"]):
                raise ConfigError(f"config.lua {where}.shore must be a noise name (the version's shore body)")
            if "fields" in v and (not isinstance(v["fields"], str) or not v["fields"]):
                raise ConfigError(f"config.lua {where}.fields must be a noise name (the map's offshore stamp key)")
            if "edge" in v and (v["edge"] is not True or not isinstance(((cfg.get("coast") or {}).get("edge_band")),
                                                                       dict)):
                raise ConfigError(f"config.lua {where}.edge must be true, with coast.edge_band defined")
            if "over" in v and (v["over"] not in [o["entry"] for o in versions[: i - 1]] or
                                not isinstance(v.get("basin"), dict) or not v["basin"].get("name")):
                raise ConfigError(f"config.lua {where}.over must name an older version's entry, with a basin record")
            if "lakes" in v:
                keys = {t.get("preset_key") for t in (cfg.get("toggles") or {}).values() if isinstance(t, dict)}
                if not isinstance(v["lakes"], str) or v["lakes"] not in keys or "spawn" not in v:
                    raise ConfigError(f"config.lua {where}.lakes must be a toggle's preset key, on a version with a "
                                      f"spawn record (the inland lakes switch)")
            for n in GEOGRAPHY_NAMES + ("start_mask",):
                if not isinstance(v[n], str) or not v[n]:
                    raise ConfigError(f"config.lua {where}.{n} must be a noise name")
            if not _positive_int(v["geo_id"]):
                raise ConfigError(f"config.lua {where}.geo_id must be a positive integer (a tn_geo id), found "
                                  f"{v['geo_id']!r}")
            off = v["city_offset"]
            if not (isinstance(off, list) and len(off) == 2 and all(_offset_value(x) for x in off)):
                raise ConfigError(f"config.lua {where}.city_offset must be two values, each an integer or a noise "
                                  f"name")
            if "spawn" in v and not all(isinstance(x, str) for x in off):
                raise ConfigError(f"config.lua {where}.city_offset must name the city fold's two bodies: a version "
                                  f"with a spawn record moves with its city")
            fits = v["fits"]
            if not isinstance(fits, dict) or set(fits) != set(FIT_ROLES) or not all(
                    isinstance(f, str) and f.startswith(GENERATED_DIR) and f.endswith(".lua") for f in fits.values()):
                raise ConfigError(f"config.lua {where}.fits must map exactly {list(FIT_ROLES)} to generated files "
                                  f"({GENERATED_DIR}<name>.lua)")
            _fallback_entries(v["fallbacks"], f"{where}.fallbacks")
            names += own_names(v)
        dup = _duplicates(names)
        if dup:
            raise ConfigError(f"config.lua geography.{key} names {dup} in more than one role or version: each version "
                              f"takes names of its own and never re-points an older one's (ruling 21)")
        out[key] = versions
    return out


FRAME_NAMES = ("gx", "gy", "u", "v", "cx", "cy")
FRAME_FIELDS = set(FRAME_NAMES) | {"geo_id", "city_offset", "fallbacks"}


def frames(cfg):
    """`frames` (0.3.0: one geography version per map) is keyed by map key, each {geo_id, gx, gy, u, v, cx, cy,
    city_offset, fallbacks}: the coordinate chain of the map's layer_chain_geo release, kept when that version was
    dropped because every map-wide layer reads it by name. geo_id is the map's layer_chain_geo and no version's,
    the names are noise names no version takes, and the fallbacks are exactly cx then cy, map-qualified and frozen
    (no preset bakes them; presets.lua values them as city_offset). {map key: frame}; {} without the group."""
    out = {}
    maps = set(_keyed(cfg, "maps"))
    lc = cfg.get("layer_chain_geo") or {}
    raw = cfg.get("frames")
    if raw in (None, [], {}):
        return out
    if not isinstance(raw, dict):
        raise ConfigError("config.lua frames must be keyed by map key")
    taken = {n for vs in geography_versions(cfg).values() for v in vs for n in own_names(v)}
    ids = {v["geo_id"] for vs in geography_versions(cfg).values() for v in vs}
    for key, f in raw.items():
        where = f"frames.{key}"
        if key not in maps:
            raise ConfigError(f"config.lua {where} is not a map key")
        if not isinstance(f, dict) or set(f) != FRAME_FIELDS:
            raise ConfigError(f"config.lua {where} must hold exactly {sorted(FRAME_FIELDS)}")
        for n in FRAME_NAMES:
            if not isinstance(f[n], str) or not f[n]:
                raise ConfigError(f"config.lua {where}.{n} must be a noise name")
        if f["geo_id"] != lc.get(key) or f["geo_id"] in ids:
            raise ConfigError(f"config.lua {where}.geo_id {f['geo_id']!r} must be the map's layer_chain_geo "
                              f"({lc.get(key)!r}) and no geography version's")
        off = f["city_offset"]
        if not (isinstance(off, list) and len(off) == 2 and all(isinstance(x, str) and x for x in off)):
            raise ConfigError(f"config.lua {where}.city_offset must name the city fold's two bodies")
        fb = _fallback_entries(f["fallbacks"], f"{where}.fallbacks")
        if [e["name"] for e in fb] != [f["cx"], f["cy"]] or not all(e["map_qualified"] and e.get("frozen") for e in fb):
            raise ConfigError(f"config.lua {where}.fallbacks must be exactly cx then cy, map-qualified and frozen")
        clash = sorted(set(f[n] for n in FRAME_NAMES) & taken)
        if clash:
            raise ConfigError(f"config.lua {where} names {clash}, which a geography version takes as its own")
        out[key] = f
    return out


def geography(cfg):
    """{map key: the map's newest geography version}, with the map's `map_type_order` and its
    `entry_versions` (every version's entry, oldest first, the newest last) added, and the fields of
    its spawn record, when it has one, copied to the top level (city_setting, city, city_index, ...;
    `spawn` stays too): the version the map's preset names, whose entry alone carries the Map type
    fields. Control code identifies a Map-type-only world by any entry version. Readers that need
    every version use geography_versions."""
    raw = _keyed(cfg, "geography")
    return {key: dict(versions[-1], **(spawn_of(versions[-1]) or {}), map_type_order=raw[key]["map_type_order"],
                      entry_versions=[v["entry"] for v in versions])
            for key, versions in geography_versions(cfg).items()}


# ------------------------------------------------------------------------------------------------ regions
#
# The region layer (milestone region-layer). prototypes/expressions/regions.lua defines the layer's
# fixed names from config.lua's regions.names, and for every row of the region table beside
# config.lua the names that config.lua's row stem, the row's id and config.lua's version suffix
# make, plus one warped query point per distinct warp share. The accessors below compose the same
# names by the same rule, and the release_registry row that lists the table under `files` releases
# them, so every reader of config's names (the gate's dump facts, the T16 name and frozen rows,
# build_zip.py --release) sees each one: a row name derives from config.lua through its stem and
# suffix (design constraint 5), and a row edit stays a data edit of the table (D13).

REGION_MAX_SHARE = 3                               # the destroyed zone's warp runs past the shared warp
REGION_TABLE = "prototypes/tables/regions.lua"     # relative to the mod folder, as `files` spells it
HOTSPOT_TABLE2 = "prototypes/tables/hotspots_v2.lua"     # its rows take region names too, less the weight
REGION_TABLE2 = "prototypes/tables/regions_v2.lua"       # its rows take region names too (0.3.0)
HOTSPOT_TABLE3 = "prototypes/tables/hotspots_v3.lua"     # its rows take region names too, less the weight (0.3.1)
REGION_ROW_KINDS = ("sd", "w", "depth")            # every row's signed distance, weight and depth
REGION_CENTRE_KINDS = ("hu", "hv", "pd")           # a hotspot disc's jittered centre and plain distance
REGION_AGGREGATES = ("destroyed_sd", "destroyed_w", "destroyed_depth", "forest_w", "forest_sum", "tree_mult",
                     "marsh_w", "hotspot_w", "enemy_mult")
REGION_OWN = ("ox", "oy", "ax", "ay", "wk", "wx", "wy", "rough")   # the noise anchor, the warp, the roughness
_ROW_ID = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
_TABLES = {}


def region_table_path(cfg):
    """The region table beside the config.lua `cfg` was loaded from (the repo's for a dict built in
    code): <mod>/prototypes/tables/regions.lua."""
    src = getattr(cfg, "source", None)
    mod = Path(src).parents[1] if src else CONFIG.parents[1]
    return mod / REGION_TABLE


def region_table_rows(cfg):
    """The region table's rows (the table beside cfg's config.lua), read with the pure-data loader;
    each row is a keyed table with an id (lower-case letters and digits joined by single underscores,
    unique), a layer, a shape and a warp share in [0, REGION_MAX_SHARE]. The parse is cached by the file's
    sha256."""
    p = region_table_path(cfg)
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise ConfigError(f"{p}: the region table is unreadable ({e})") from e
    key = hashlib.sha256(raw).hexdigest()
    if key not in _TABLES:
        rows = _eval_text(raw.decode("utf-8"), p).get("rows")
        if not isinstance(rows, list) or not rows:
            raise ConfigError(f"{p}: the region table holds no rows list")
        seen = set()
        for r in rows:
            rid = r.get("id") if isinstance(r, dict) else None
            if not isinstance(rid, str) or not _ROW_ID.fullmatch(rid) or rid in seen:
                raise ConfigError(f"{p}: row id {rid!r} is not a unique id of lower-case letters and digits joined by "
                                  f"single underscores")
            seen.add(rid)
            w = r.get("warp")
            if not isinstance(r.get("layer"), str) or not isinstance(r.get("shape"), str) or \
                    isinstance(w, bool) or not isinstance(w, (int, float)) or not 0 <= w <= REGION_MAX_SHARE:
                raise ConfigError(f"{p}: row {rid} needs a layer, a shape and a warp share in [0, {REGION_MAX_SHARE}]")
        _TABLES[key] = rows
    return _TABLES[key]


def _region_group(cfg):
    R = cfg.get("regions")
    n = R.get("names") if isinstance(R, dict) else None
    stems = n.get("row") if isinstance(n, dict) else None
    keys = ("suffix", "share", "u", "v") + REGION_AGGREGATES + REGION_OWN
    if not isinstance(stems, dict) or not all(isinstance(n.get(k), str) and n[k] for k in keys) or \
            not all(isinstance(stems.get(k), str) and stems[k] for k in REGION_ROW_KINDS + REGION_CENTRE_KINDS):
        raise ConfigError(f"config.lua regions.names must name {list(keys)} and the row stems "
                          f"{list(REGION_ROW_KINDS + REGION_CENTRE_KINDS)}")
    h = R.get("share_hundredths")
    if isinstance(h, bool) or not isinstance(h, int) or h <= 0:
        raise ConfigError("config.lua regions.share_hundredths must be a positive integer")
    return R, n


def region_row_name(cfg, kind, row_id):
    """A row's name of one kind (sd, w, depth; hu, hv for a hotspot): config.lua's stem, the row id,
    config.lua's version suffix, as regions.lua spells it (row.<kind> .. id .. suffix)."""
    _, n = _region_group(cfg)
    if kind not in REGION_ROW_KINDS + REGION_CENTRE_KINDS:
        raise ConfigError(f"no region row name kind {kind!r}")
    return n["row"][kind] + row_id + n["suffix"]


def region_query_names(cfg, share):
    """The (u, v) names of the query point for a warp share, as regions.lua's query() spells them:
    h = floor(share * share_hundredths + 1/2); the unwarped point at h = 0, else u, v .. share .. h ..
    suffix."""
    R, n = _region_group(cfg)
    h = _share_h(R, share)
    if h == 0:
        return n["u"] + n["suffix"], n["v"] + n["suffix"]
    return n["u"] + n["share"] + str(h) + n["suffix"], n["v"] + n["share"] + str(h) + n["suffix"]


def _share_h(R, share):
    return int(math.floor(share * R["share_hundredths"] + 0.5))


def region_names(cfg, rows=None):
    """Every noise name regions.lua defines, composed as it composes them from config.lua's
    regions.names and the table's rows (`rows`, else the table beside cfg's config.lua):
    {"aggregates": {key: name}, "internal": [names], "rows": {id: {kind: name}}}. Internal names are
    the layer's own (the query point and its warped shares, the noise anchor, the warp and the
    roughness); consumers read the aggregates and the row names. Empty parts without a regions group."""
    if not cfg.get("regions"):
        return {"aggregates": {}, "internal": [], "rows": {}}
    R, n = _region_group(cfg)
    rows = region_table_rows(cfg) if rows is None else rows
    internal = list(region_query_names(cfg, 0)) + [n[k] for k in REGION_OWN]
    shares = {_share_h(R, r["warp"]): r["warp"] for r in rows}
    for h in sorted(set(shares) - {0}):
        internal += list(region_query_names(cfg, shares[h]))
    per = {}
    for r in rows:
        kinds = REGION_ROW_KINDS + (REGION_CENTRE_KINDS if r["layer"] == "hotspot" and r["shape"] == "disc" else ())
        per[r["id"]] = {k: region_row_name(cfg, k, r["id"]) for k in kinds}
    return {"aggregates": {k: n[k] for k in REGION_AGGREGATES}, "internal": internal, "rows": per}


def hotspot2_row_names(cfg, table_file="hotspots_v2.lua"):
    """Every row name regions.lua composes for a later hotspot table's rows: a hotspot row's, less the weight."""
    table = _eval_text((region_table_path(cfg).parent / table_file).read_text(encoding="utf-8"),
                       region_table_path(cfg).parent / table_file)
    kinds = tuple(k for k in REGION_ROW_KINDS if k != "w") + REGION_CENTRE_KINDS
    return sorted(region_row_name(cfg, k, r["id"]) for r in table["rows"] for k in kinds)


def region2_row_names(cfg):
    """Every row name regions.lua composes for the second region table's rows: a row's sd, weight and depth."""
    path = region_table_path(cfg).parent / "regions_v2.lua"
    table = _eval_text(path.read_text(encoding="utf-8"), path)
    return sorted(region_row_name(cfg, k, r["id"]) for r in table["rows"] for k in REGION_ROW_KINDS)


def region_noise_names(cfg, rows=None):
    """region_names as one sorted list."""
    names = region_names(cfg, rows)
    out = set(names["aggregates"].values()) | set(names["internal"])
    for d in names["rows"].values():
        out |= set(d.values())
    return sorted(out)


def start_masks(cfg):
    """`start_mask` is {versions = {...}}: every version of the start mask, oldest first, each
    {name = <noise name>, formula = <positive integer>, <parameter> = <number>, ...} (spawn.lua
    builds formula n from the version's numbers). A geography version names the one its preset
    bakes; older versions stay defined, unchanged. [version, ...]; [] when config.lua
    has no start mask."""
    sm = cfg.get("start_mask")
    if sm is None or sm in ([], {}):
        return []
    if not isinstance(sm, dict) or set(sm) != {"versions"}:
        raise ConfigError("config.lua start_mask must hold exactly ['versions']")
    out = _listed(None, "start_mask.versions", sm["versions"])
    for i, m in enumerate(out, 1):
        if not isinstance(m, dict) or not isinstance(m.get("name"), str) or not m["name"] or \
                not _positive_int(m.get("formula")) or not all(
                    isinstance(x, (int, float)) and not isinstance(x, bool)
                    for k, x in m.items() if k not in ("name", "formula")):
            raise ConfigError(f"config.lua start_mask.versions[{i}] must be {{name = <noise name>, formula = "
                              f"<positive integer>, <parameter> = <number>, ...}}")
    dup = _duplicates([m["name"] for m in out])
    if dup:
        raise ConfigError(f"config.lua start_mask.versions names {dup} twice")
    return out


def baked_names(cfg, map_key, version, scale, city=None, ab=False):
    """The property_expression_names a geography version's preset bakes at a startup scale (and,
    for a version with a spawn record, a spawn-city setting value, default the setting's default),
    as presets.lua builds them from the same rows: the version's entry, start mask and coarse field,
    the map's tn_map id, the scale, the version's tn_geo id, its city offset under its own names,
    and vanilla's water-slider readers at their default-slider values (D15); with a spawn record
    also the distance redirect, the map's city number and the spawn lake and bias keys; from
    climate-tiles the climate redirects, the marsh keys and the palm keys (with or without Alien
    Biomes), and with ab=True (Alien Biomes loaded, the M2 dump) the AB climate variant, the vanilla
    tile keys and the exclusion key, else the fallback climate and the marsh grass key; from
    trees-forests the tree keys; from ridges the cliff properties, the map's ridge keys and the Earth
    ores' wrapper keys; from destroyed-europe, with
    ab=True, the Alien Biomes temperature's next version."""
    K, m = cfg["keys"], cfg["maps"][map_key]
    rec, pos = scale_record(cfg, map_key, version, scale)
    pen = {K["elevation"]: rec["entry"], K["start_mask"]: version["start_mask"],
           K["land_coarse"]: version["land_coarse"], K["map"]: m["id"], K["scale"]: int(scale),
           K["geo"]: version["geo_id"], version["cx"]: version["city_offset"][0],
           version["cy"]: version["city_offset"][1]}
    pen.update({w["key"]: w["value"] for w in water_slider(cfg)})
    sp = spawn_of(version)
    if sp:
        pen.update({K["distance"]: sp["distance"], sp["city"]: city_number(cfg, version, city),
                    K["spawn_lake"]: sp["spawn_lake"], K["spawn_bias"]: sp["spawn_bias"]})
    # waterways: the hook gate on and the ford key at the map's ford set for the scale
    ww = waterways_of(rec)
    if ww:
        pen.update({K["on"]: cfg["hooks"]["gate_on"], K["fords"]: ww["fords"][pos]})
    # each toggle of the map at its setting's default: its on or off body
    for tg in toggles(cfg):
        if map_key in (tg.get("maps") or []):
            on = cfg["settings"][tg["setting"]]["default_value"]
            pen[tg["preset_key"]] = tg["on"] if on else tg["off"]
    # the climate and tile keys (climate-tiles; presets.lua climate_names), the same on every version
    cl, tl = cfg.get("climate"), cfg.get("tiles")
    if cl and tl:
        variant = cl["points"]["ab" if ab else "fallback"]
        for prop in ("temperature", "moisture", "aux"):
            pen[prop] = variant[prop]
        for k in ("water_mud", "water_shallow"):
            pen[tl["marsh"][k]["key"]] = tl["marsh"][k]["body"]
        # 0.3.0: the spread's frequency sliders at the biome size (presets.lua climate_names)
        size = cl.get("size")
        if size:
            for k in size["keys"]:
                pen[k] = 1 / size["factor"]
        # the palm keys with AB loaded or not
        for c in tl["palm"]["copies"]:
            pen[c["key"]] = c["body"]
        if ab:
            for tile in tl["vanilla"]["tiles"]:
                pen[tl["vanilla"]["keys"][tile]] = tl["vanilla"]["body"]
            pen[tl["exclude"]["key"]] = tl["exclude"]["body"]
            mix = tl["vanilla"]["mix"]
            if map_key in mix["maps"]:
                pen[mix["key"]] = mix["amount"]
        else:
            pen[tl["marsh"]["grass"]["key"]] = tl["marsh"]["grass"]["body"]
            pen[tl["frozen"]["key"]] = tl["frozen"].get("body2") or tl["frozen"]["body"]
    # the tree keys (trees-forests; presets.lua tree_names), after the climate keys: the multiplier key at
    # the region layer's multiplier, and with ab=True every restored tree's, rock's and decorative's key
    # at its body and each palm's probability key at its second version
    tr = cfg.get("trees")
    if tr:
        rs = tr["restore"]
        pen[tr["boost"]["key"]] = cfg["regions"]["names"]["tree_mult"]
        if ab:
            for n in rs["trees"].values():
                pen[n["p"]] = n["body"]
                pen[n["r"]] = rs["richness"]
            for n in rs["rocks"].values():
                pen[n["key"]] = n["body"]
            for key in rs["decoratives"].values():
                pen[key] = rs["deco_body"]
            for pm in tr["palm"]:
                pen[pm["key"]] = pm.get("next3") or pm.get("next2") or pm["next"]
            nb = (cfg.get("blue") or {}).get("no_blue")
            if nb:
                pen[nb["key"]] = cfg["neutral"]["one"]
            p2 = (cfg.get("blue") or {}).get("plants2")
            if p2:
                pen[p2["key"]] = cfg["neutral"]["one"]
    # the ridges (ridges; presets.lua ridge_values): the two cliff properties at the ridge bodies and the
    # map's crest, openings and band keys; and every Earth ore's probability key at its clearance wrapper,
    # which data-final-fixes.lua adds to every preset (M1 holds all six resources)
    rd = cfg.get("ridges")
    if rd:
        n, rp = rd["names"], rd["preset"]
        if map_key in rp["crest"] and map_key in rp["openings"] and map_key in n["band"]:
            pen.update({K["cliff_elevation"]: rp["cliff_elevation"], K["cliffiness"]: n["cliffiness"],
                        K["crest"]: rp["crest"][map_key], K["openings"]: rp["openings"][map_key],
                        K["band"]: rp.get("band", n["band"])[map_key],
                        K["high"]: rp["high"][map_key],
                        K["passes"]: rp["passes"][map_key],
                        K["high_tile"]: rp["high_tile"][map_key]})
            for name, r in cfg["trees"]["restore"]["rocks"].items():
                if r.get("high"):
                    pen[r["key"] if ab else f"entity:{name}:probability"] = r["high"]
            if ab:
                pen[K["rock_lift"]] = n["rock_lift_ab"]
            else:
                pen[K["ground"]] = n["ground"]
        pen.update({o["key"]: o["name"] for o in rd["ores"]})
    # resources-enemies: the ore keys at the next probability wrappers and the richness keys at theirs,
    # the enemy property at its wrapper (data-final-fixes.lua adds them to every preset; the Oil Rig's
    # keys exist only beside it), and a version with an offshore stamp bakes its stamp key, the map's
    # stamp body with hotspots on and the neutral zero off (presets.lua)
    rs = cfg.get("resources")
    if rs:
        for o in rs["ores"]:
            # 0.3.0: a cut probability wrapper (p3) and the richness wrapper's next version (r2) where defined
            pen[o["probability"]] = o.get("p3") or o["p"]
            pen[o["richness"]] = o.get("r2") or o["r"]
        pen[K["enemy"]] = cfg["enemies"]["wrapper"]
        # a development branch: the hotspot amount and each live patch expression at its Earth body (the Oil Rig's
        # exists only beside it)
        amount = cfg["settings"]["hotspot_amount"]["default_value"]
        pen[K["hotspot_amount"]] = int(amount) / cfg["hotspots"]["amount_percent"]
        # 0.3.0: the regional scarcity level at the setting's default (resources.scarcity)
        sc = rs.get("scarcity")
        if sc:
            pen[sc["key"]] = sc["levels"][cfg["settings"][sc["setting"]]["default_value"]]
        for b in rs["natural"]["bodies"]:
            if rs["offshore"]["resource"] not in b["live"]:
                # 0.3.0: vanilla's function with the footprint gap (resources.natural.fn2)
                pen[b["live"]] = b.get("name2") or b["name"]
    if version.get("fields"):
        tg = cfg["toggles"]["hotspots"]
        on = cfg["settings"][tg["setting"]]["default_value"]
        pen[version["fields"]] = cfg["fields"]["names"][map_key] if on else cfg["neutral"]["zero"]
    # destroyed-europe (presets.lua destroyed_values, last): with Alien Biomes temperature names the Alien
    # Biomes temperature's next version whatever the toggle (its folded switch keeps climate-tiles' first
    # version when off); the random pool replaces the city number only with the zone on, never at the
    # setting's default (off)
    de = cfg.get("destroyed")
    if ab and de and de.get("names"):
        pen["temperature"] = de["names"]["temperature"]
    # the cold north (presets.lua grain_values): its plain temperature, which reads the zone's by name
    if ab and cl and cl["points"].get("north"):
        pen["temperature"] = cl["points"]["north"]
    # coast-band-fix (presets.lua bandfix_names, last): the band-fix key where the setting is on at its
    # default, acts on the map and serves the scale
    bf = cfg.get("bandfix")
    if (bf and cfg["settings"][bf["setting"]]["default_value"] and map_key in (bf.get("maps") or [])
            and int(scale) in [int(s) for s in cfg["scales"]["exact_coast"]]):
        pen[bf["key"]] = bf["on"]
    # the next geo body (presets.lua geo_next_values, after baked, config.lua coast.next): past above_scale it
    # replaces the version's own
    gn = ((cfg.get("coast") or {}).get("next") or {}).get("versions") or {}
    gn = gn.get(version["geo_id"]) or gn.get(str(version["geo_id"]))
    if gn and int(scale) > gn["above_scale"]:
        pen[version["geo"]] = gn["body"]
    # the next spawn folds (presets.lua spawn_next_values, after baked): a city number past the released folds'
    # cities names the next folds over the version's city offset, its map's frame, the spawn lake and the bias
    nx, sp = spawn_next_of(cfg, version), spawn_of(version)
    if nx and sp and isinstance(pen.get(sp["city"]), int) and pen[sp["city"]] > nx["served"]:
        pen[version["cx"]], pen[version["cy"]] = nx["city_offset"][0], nx["city_offset"][1]
        fr = frames(cfg).get(map_key)
        if fr:
            pen[fr["cx"]], pen[fr["cy"]] = nx["city_offset"][0], nx["city_offset"][1]
        pen[K["spawn_lake"]] = pen[sp["spawn_lake"]] = nx["spawn_lake"]
        pen[K["spawn_bias"]] = nx["spawn_bias"]
    # the second hotspot table: presets.lua baked names it over the first table's
    pen.update((cfg.get("hotspots_v2") or {}).get("points") or {})
    # the second region table: presets.lua baked names its forest and marsh aggregates over the first table's
    pen.update((cfg.get("regions_v2") or {}).get("points") or {})
    if rs and cfg.get("hotspots_v2"):
        pen[K["enemy"]] = cfg["hotspots_v2"]["nests"]["wrapper"]
    # the scattered bases (data-final-fixes.lua enemy_wrapper): 0.3.0's presets name them over the nests
    if rs and (cfg["enemies"].get("scatter") or {}).get("wrapper"):
        pen[K["enemy"]] = cfg["enemies"]["scatter"]["wrapper"]
    # trees off a hotspot's ore (data-final-fixes.lua): new presets switch the hook gate on
    if rs and rs.get("ore_trees"):
        pen[rs["ore_trees"]["key"]] = cfg["neutral"]["one"]
        if rs["ore_trees"].get("open_v2"):
            pen[rs["ore_trees"]["open"]] = rs["ore_trees"]["open_v2"]
            pen[rs["ore_trees"]["plants"]["open"]] = rs["ore_trees"]["plants"]["open_v2"]
    # 0.3.1: the third hotspot table's bodies, wrappers, nests and tree shares over the second table's
    h3 = cfg.get("hotspots_v3")
    if rs and h3:
        pen.update(h3["points"])
        for o in rs["ores"]:
            if o.get("p4"):
                pen[o["probability"]] = o["p4"]
                pen[o["richness"]] = o["r3"]
        pen[K["enemy"]] = h3["scatter"]
        if rs.get("ore_trees") and rs["ore_trees"].get("open_v3"):
            pen[rs["ore_trees"]["open"]] = rs["ore_trees"]["open_v3"]
            pen[rs["ore_trees"]["plants"]["open"]] = rs["ore_trees"]["plants"]["open_v3"]
    return pen


RELEASE_FIELDS = {"release", "map", "geography", "names", "files"}


def _positive_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def release_registry(cfg):
    """`release_registry` is a list of {release = <version>, map = <map key>, geography = <tn_geo
    id>, names = {<noise names>}, files = {<generated files>}} (europe-coast writes the first row).
    A row of a geography release carries `map` and `geography` together: the geography id is a
    positive integer and the map a map key, so every tn_geo a save can hold resolves to one map."""
    out = []
    maps = set(_keyed(cfg, "maps"))
    for r in _listed(cfg, "release_registry"):
        if not isinstance(r, dict) or not isinstance(r.get("release"), str) or set(r) - RELEASE_FIELDS:
            raise ConfigError("config.lua release_registry rows must be {release, map, geography, names, files}")
        if ("map" in r) != ("geography" in r):
            raise ConfigError(f"config.lua release_registry {r['release']}: a geography release names its map and "
                              f"its geography id together")
        if "geography" in r and (not _positive_int(r["geography"]) or r["map"] not in maps):
            raise ConfigError(f"config.lua release_registry {r['release']}: geography must be a positive integer "
                              f"(a tn_geo id) and map a map key (found {r.get('geography')!r}, {r.get('map')!r})")
        _names(r.get("names", []), f"release_registry {r['release']} names")
        _names(r.get("files", []), f"release_registry {r['release']} files")
        out.append(r)
    return out


def release_of(cfg):
    """{noise name: release} of every released name: a row's `names`, and every name of the region
    layer for a row whose `files` lists the region table (REGION_TABLE)."""
    out = {}
    for r in release_registry(cfg):
        names = list(r.get("names") or [])
        if REGION_TABLE in (r.get("files") or []):
            names += region_noise_names(cfg)
        if HOTSPOT_TABLE2 in (r.get("files") or []):
            names += hotspot2_row_names(cfg)
        if HOTSPOT_TABLE3 in (r.get("files") or []):
            names += hotspot2_row_names(cfg, "hotspots_v3.lua")
        if REGION_TABLE2 in (r.get("files") or []):
            names += region2_row_names(cfg)
        for n in names:
            out[n] = r["release"]
    return out


def geo_maps(cfg):
    """{tn_geo id: map key} over every geography release in release_registry: how control code and
    the tools resolve a save's tn_geo (ARCHITECTURE.md, "Release versioning policy", rule 4)."""
    out = {}
    for r in release_registry(cfg):
        if "geography" in r:
            out.setdefault(r["geography"], r["map"])
    return out


def _duplicates(values):
    seen, dup = set(), []
    for v in values:
        if v in seen and v not in dup:
            dup.append(v)
        seen.add(v)
    return dup


def id_space_problems(cfg):
    """The id spaces config.lua defines, each closed: every id is well formed and names one thing
    only. tn_map ids (maps.<key>.id) are positive integers unique across maps; tn_geo ids are one
    space across every map: each geography version's geo_id is a positive integer unique across
    every version of every map, each release_registry geography id appears in one row only, and each
    version's geo_id has its row, naming that version's map, so no id can collide or resolve to two.
    Map keys, setting keys, display names, preset names and orders, Map type orders, message locale
    keys and the detail octaves' seed1 values are unique too. Returns messages (schema_problems
    reports them)."""
    out = []
    try:
        maps = _keyed(cfg, "maps")
        for k, m in maps.items():
            if not isinstance(m, dict):
                out.append(f"config.lua maps.{k} must be a keyed table")
                continue
            if m.get("key") != k:
                out.append(f"config.lua maps.{k}.key must be {k!r} (found {m.get('key')!r})")
            if not _positive_int(m.get("id")):
                out.append(f"config.lua maps.{k}.id must be a positive integer (the tn_map value), found {m.get('id')!r}")
        good = {k: m for k, m in maps.items() if isinstance(m, dict)}
        for field, what in (("id", "tn_map id"), ("setting_key", "setting key"), ("display", "display name")):
            for v in _duplicates([m.get(field) for m in good.values() if m.get(field) is not None]):
                out.append(f"config.lua maps: {what} {v!r} names more than one map")
        rows = release_registry(cfg)
        versions = [(k, i, v) for k, vs in geography_versions(cfg).items() for i, v in enumerate(vs, 1)]
        for v in _duplicates([v["geo_id"] for _, _, v in versions]):
            out.append(f"config.lua geography: tn_geo id {v!r} is the geo_id of more than one version or map (one id "
                       f"space across every map and version)")
        geo = _keyed(cfg, "geography")
        for v in _duplicates([g.get("map_type_order") for g in geo.values() if isinstance(g, dict)]):
            out.append(f"config.lua geography: Map type order {v!r} is used by more than one map")
        ids = [r["geography"] for r in rows if "geography" in r]
        for v in _duplicates(ids):
            out.append(f"config.lua release_registry: tn_geo id {v} appears in more than one row (a geography "
                       f"release is registered once, under one map)")
        for k, i, v in versions:
            own = [r for r in rows if r.get("geography") == v["geo_id"]]
            if not own:
                out.append(f"config.lua geography.{k}.versions[{i}].geo_id {v['geo_id']!r} has no release_registry "
                           f"row (each geography release is registered with its map)")
            elif any(r["map"] != k for r in own):
                out.append(f"config.lua geography.{k}.versions[{i}].geo_id {v['geo_id']!r} is registered under map "
                           f"{[r['map'] for r in own]} in release_registry, not {k!r} (an id names one map)")
        # a map's frame (0.3.0) keeps its dropped version's tn_geo id and release row
        for k, f in frames(cfg).items():
            own = [r for r in rows if r.get("geography") == f["geo_id"]]
            if not own:
                out.append(f"config.lua frames.{k}.geo_id {f['geo_id']!r} has no release_registry row (each geography "
                           f"release is registered with its map)")
            elif any(r["map"] != k for r in own):
                out.append(f"config.lua frames.{k}.geo_id {f['geo_id']!r} is registered under map "
                           f"{[r['map'] for r in own]} in release_registry, not {k!r} (an id names one map)")
        presets = _keyed(cfg, "presets")
        for field in ("name", "order"):
            for v in _duplicates([p.get(field) for p in presets.values() if isinstance(p, dict)]):
                out.append(f"config.lua presets: {field} {v!r} is used by more than one preset")
        for k, p in presets.items():
            if isinstance(p, dict) and "map" in p and p["map"] not in maps:
                out.append(f"config.lua presets.{k}.map {p['map']!r} is not a map key")
        msg = (cfg.get("messages") or {}).get("keys") or {}
        if msg == []:
            msg = {}
        if not isinstance(msg, dict) or not all(isinstance(v, str) and v for v in msg.values()):
            out.append("config.lua messages.keys must map each message key to a locale key")
        else:
            for v in _duplicates(list(msg.values())):
                out.append(f"config.lua messages.keys: locale key {v!r} serves more than one message")
        octaves = ((cfg.get("coast") or {}).get("detail_octaves")) or []
        for v in _duplicates([o.get("seed1") for o in octaves if isinstance(o, dict)]):
            out.append(f"config.lua coast.detail_octaves: seed1 {v!r} is used by more than one octave (A-11)")
    except ConfigError as e:
        out.append(str(e))
    return out


def release_names(cfg):
    return sorted(release_of(cfg))


# requires (destroyed-europe): a mod without which a preset bakes the toggle off whatever its setting says
TOGGLE_FIELDS = {"setting", "preset_key", "default", "mechanism", "on", "off", "maps", "requires",
                 "map_type_follows"}


def toggles(cfg):
    """`toggles` is keyed by toggle key, `toggle_order` lists those keys, as settings and presets are;
    each toggle is {setting = <settings key>, preset_key = <property_expression_names key>,
    default, mechanism = "name switch" | "hook gate", on = <name>, off = <name>, maps = {...},
    map_type_follows = <true where the Map type fallback mirrors the setting>}.
    Returns the toggles in order, each with its key under "key"."""
    t = _keyed(cfg, "toggles")
    order = _names(cfg.get("toggle_order", []), "toggle_order")
    if set(order) != set(t) or len(order) != len(set(order)):
        raise ConfigError("config.lua toggle_order must list exactly the keys of toggles, once each")
    out = []
    settings = _keyed(cfg, "settings")
    for k in order:
        e = t[k]
        if not isinstance(e, dict) or set(e) - TOGGLE_FIELDS or not {"setting", "preset_key", "mechanism"} <= set(e):
            raise ConfigError(f"config.lua toggles.{k} must hold setting, preset_key and mechanism "
                              f"(and only {sorted(TOGGLE_FIELDS)})")
        if e["setting"] not in settings:
            raise ConfigError(f"config.lua toggles.{k}.setting {e['setting']!r} is not a settings key")
        out.append(dict(e, key=k))
    return out


def withheld_presets(cfg):
    """{preset key: [mod names]}: each preset's withheld_with, the mods whose presence withholds it
    (presets.lua defines no such preset while one is loaded; europe-coast withholds Europe beside
    Alien Biomes until climate-tiles' palm switch). A preset without the field is never withheld."""
    out = {}
    for key, p in _keyed(cfg, "presets").items():
        if not isinstance(p, dict):
            raise ConfigError(f"config.lua presets.{key} must be a keyed table")
        out[key] = list(_names(p.get("withheld_with", []), f"presets.{key}.withheld_with"))
    return out


def water_slider(cfg):
    """`water_slider` lists {key = <vanilla noise name>, value = <number>}: vanilla's readers of the
    water slider that every Earth preset bakes at their default-slider value (D15). Each key is a
    preset key (preset_keys), so the missing-name guard and the D33 guard know it."""
    out = []
    keys = set(cfg.get("preset_keys") or [])
    for e in _listed(cfg, "water_slider"):
        if not isinstance(e, dict) or set(e) != {"key", "value"} or not isinstance(e.get("key"), str) or \
                not e["key"] or isinstance(e.get("value"), bool) or not isinstance(e.get("value"), (int, float)):
            raise ConfigError("config.lua water_slider entries must be {key = <noise name>, value = <number>}")
        if e["key"] not in keys:
            raise ConfigError(f"config.lua water_slider key {e['key']!r} is not in preset_keys")
        out.append(e)
    if len({e["key"] for e in out}) != len(out):
        raise ConfigError("config.lua water_slider lists a key twice")
    return out


# Groups that europe-coast's review moved into a per-version home (every version per map). A copy
# left at the top level would be read by no one, so its versions would silently drop out.
RETIRED_GROUPS = {"fallbacks": "geography.<map>.versions[n].fallbacks", "start_mask_versions": "start_mask.versions"}


def bandfix_next_problems(cfg):
    """The band fix's next rule writes other tiles, so it must reach no map's first geography of `bandfix.tables`,
    the one its tables were built for and released with: a save of it would change under the rule."""
    nx = cfg.get("bandfix_next")
    tables = (cfg.get("bandfix") or {}).get("tables") or {}
    firsts = [t["geographies"][0] for t in tables.values() if t.get("geographies")]
    if nx and firsts and nx["from_geo"] <= max(firsts):
        return [f"config.lua bandfix_next.from_geo {nx['from_geo']} reaches tn_geo {max(firsts)}, a released geography"]
    return []


def schema_problems(cfg):
    """Every shape problem of config.lua's groups, as messages (the T16 names row reports them)."""
    out = [f"config.lua {g} is retired: it lives in {home} (every version per map), and a top-level copy is read by "
           f"no one" for g, home in RETIRED_GROUPS.items() if g in cfg]
    for fn in (map_keys, firewall_names, fallbacks, release_registry, toggles, geography_versions, frames, start_masks,
               withheld_presets, water_slider):
        try:
            fn(cfg)
        except ConfigError as e:
            out.append(str(e))
    for group, order in (("settings", "setting_order"), ("presets", "preset_order")):
        try:
            keys = _names(cfg.get(order, []), order)
            if set(keys) != set(_keyed(cfg, group)):
                out.append(f"config.lua {order} must list exactly the keys of {group}")
        except ConfigError as e:
            out.append(str(e))
    try:
        _names(cfg.get("preset_keys", []), "preset_keys")
    except ConfigError as e:
        out.append(str(e))
    out += id_space_problems(cfg)
    out += bandfix_next_problems(cfg)
    # The region layer's names are released through the row that lists its table: a regions group
    # whose table no release row lists would leave every row name unreleased and unregistered.
    try:
        listed = [r["release"] for r in release_registry(cfg) if REGION_TABLE in (r.get("files") or [])]
        if cfg.get("regions"):
            region_noise_names(cfg)
            if not listed:
                out.append(f"config.lua regions: no release_registry row lists {REGION_TABLE} under files, so no "
                           f"release carries the region layer's row names")
        elif listed:
            out.append(f"config.lua release_registry {listed} lists {REGION_TABLE}, but config.lua has no regions "
                       f"group")
    except ConfigError as e:
        out.append(str(e))
    ph = cfg.get("placeholder") or {}
    if ph:
        names = ph.get("names") or {}
        try:
            if not isinstance(names, dict) or set(_names(ph.get("keys", []), "placeholder.keys")) != set(names):
                out.append("config.lua placeholder.keys must list exactly the keys of placeholder.names")
            if "withheld_with" not in ph:
                out.append("config.lua placeholder.withheld_with must list the mods that withhold the placeholder "
                           "preset (presets.lua reads it)")
            else:
                _names(ph["withheld_with"], "placeholder.withheld_with")
        except ConfigError as e:
            out.append(str(e))
    # The three stores of Earth body names agree (design constraint 2): every firewall body but the
    # placeholder's is a released body (so it is registered in tests/frozen.json and checked by
    # build_zip.py --release), and every noise name config.lua defines carries the noise prefix, so
    # the gate's dump check of prefixed bodies sees every one of them.
    try:
        ph_names = set(placeholder_names(cfg))
        stray = sorted(set(firewall_names(cfg)) - ph_names - set(release_names(cfg)))
        if stray:
            out.append(f"config.lua firewall names {stray} are in no release_registry row: every fine-field body "
                       f"is a registered, released body")
        released = set(release_names(cfg)) | set(fallback_names(cfg))
        rel = set(release_names(cfg))
        fw = _keyed(cfg, "firewall")
        masks = {m["name"] for m in start_masks(cfg)}
        files = {f for r in release_registry(cfg) for f in (r.get("files") or [])}
        pkeys = set(cfg.get("preset_keys") or [])
        for key, versions in geography_versions(cfg).items():
            for i, v in enumerate(versions, 1):
                where = f"geography.{key}.versions[{i}]"
                sp = spawn_of(v)
                missing = sorted(v[n] for n in GEOGRAPHY_NAMES if v[n] not in released)
                missing += [v["entry"]] if v["entry"] not in rel else []
                missing += [v["start_mask"]] if v["start_mask"] not in rel else []
                # a spawn record's bodies and the fold its offset names are released bodies; the city
                # number is a fallback that mirrors the setting (checked with the fallbacks)
                missing += [n for n in waterway_names(v) if n not in rel]
                if waterways_of(v):
                    shared = [cfg["keys"]["on"], cfg["keys"]["fords"]] + list((cfg.get("neutral") or {}).values())
                    missing += [n for n in shared if n not in rel]
                if sp:
                    missing += [sp[n] for n in SPAWN_NAMES if n != "city" and sp[n] not in rel]
                    missing += [x for x in v["city_offset"] if isinstance(x, str) and x not in rel]
                    if sp["city"] not in exempt_fallback_names(cfg):
                        out.append(f"config.lua {where}.spawn.city {sp['city']!r} is no Map type fallback that "
                                   f"mirrors a startup setting (the spawn-city setting's number)")
                if missing:
                    out.append(f"config.lua {where} names {sorted(set(missing))}, which no release_registry row or "
                               f"fallback lists (every entry and start mask version is a released body)")
                # the fine field: the entry and every term only it reads, in every version
                unwalled = sorted(n for n in fine_names(v) if n not in (fw.get(key) or []))
                if unwalled:
                    out.append(f"config.lua {where} names {unwalled}, which firewall.{key} lacks (the fine field of "
                               f"every version; sacred constraint 3)")
                if sp:
                    walled = sorted(sp[n] for n in SPAWN_NAMES if n not in SPAWN_FINE and sp[n] in set(firewall_names(cfg)))
                    walled += sorted(x for x in v["city_offset"] if x in set(firewall_names(cfg)))
                    if walled:
                        out.append(f"config.lua {where} puts {walled} in the firewall: the start mask and distance read "
                                   f"them in the Entity program, so they must stay firewall-clean")
                if v["start_mask"] not in masks:
                    out.append(f"config.lua {where}.start_mask {v['start_mask']!r} is no start_mask version")
                stray = sorted(f for f in v["fits"].values() if f not in files)
                if stray:
                    out.append(f"config.lua {where}.fits binds {stray}, which no release_registry row lists")
                if sp and sp["bearings"] not in files:
                    out.append(f"config.lua {where}.spawn.bearings {sp['bearings']!r} is a file no release_registry row "
                               f"lists")
                # every key the version's preset bakes is a preset key: the missing-name guard and the
                # Nauvis-only surface guard know only those (D33; Space Age)
                try:
                    unkeyed = sorted(str(k) for k in baked_names(cfg, key, v, 1) if k not in pkeys)
                except (KeyError, TypeError) as e:
                    unkeyed = [f"(no preset table: {type(e).__name__} {e})"]
                if unkeyed:
                    out.append(f"config.lua {where}: its preset bakes {unkeyed}, which preset_keys lacks (the "
                               f"guards strip and check only preset_keys)")
        # each map's frame: every name a released body, its geo_id a release row of its map
        for key, f in frames(cfg).items():
            missing = sorted(f[n] for n in FRAME_NAMES if f[n] not in rel)
            missing += [x for x in f["city_offset"] if x not in rel]
            if missing:
                out.append(f"config.lua frames.{key} names {missing}, which no release_registry row lists")
            walled = sorted(f[n] for n in FRAME_NAMES if f[n] in set(firewall_names(cfg)))
            if walled:
                out.append(f"config.lua frames.{key} puts {walled} in the firewall: the map-wide layers read the "
                           f"frame in every program")
        # each map's waterways.sets is the record of its newest version that composes the waterways
        all_sets = ((cfg.get("waterways") or {}).get("sets")) or {}
        for key, versions in geography_versions(cfg).items():
            composing = [v["waterways"] for v in versions if "waterways" in v]
            if (composing[-1] if composing else None) != all_sets.get(key):
                out.append(f"config.lua waterways.sets.{key} must be the waterways record of {key}'s newest version "
                           f"that has one (the sets its preset names)")
        for key in sorted(set(all_sets) - set(geography_versions(cfg))):
            out.append(f"config.lua waterways.sets.{key} names sets for a map without a geography")
        for m in start_masks(cfg):
            if m["name"] not in rel:
                out.append(f"config.lua start mask {m['name']} is in no release_registry row (every version is a "
                           f"released body)")
        # a frozen fallback is a released, registered constant; one that mirrors a setting never is
        for n in frozen_fallback_names(cfg):
            if n not in rel:
                out.append(f"config.lua frozen fallback {n} is in no release_registry row: a frozen fallback is a "
                           f"registered constant")
        for n in exempt_fallback_names(cfg):
            if n in rel:
                out.append(f"config.lua fallback {n} mirrors a startup setting but a release_registry row lists it "
                           f"(U3: such fallbacks are never registered; mark it frozen if no setting moves it)")
        prefix = (cfg.get("identity") or {}).get("noise_prefix") or ""
        unprefixed = sorted(n for n in noise_names(cfg) if not prefix or not n.startswith(prefix))
        if unprefixed:
            out.append(f"config.lua noise names {unprefixed} lack the noise prefix {prefix!r}")
    except ConfigError as e:
        out.append(str(e))
    return out


def bandfix_digest(group):
    """sha256 of config.lua's bandfix group as its tables were built under it. Each map's geographies list
    counts as its first id: a later geography version that keeps the map's coast appends its id and serves
    the same tables, so no re-emission follows and the digests the manifests hold stay right. The generations
    only say which tables a tn_geo reads, so a new one leaves every map's digest right as well."""
    tables = {k: dict(v, geographies=list(v.get("geographies") or [])[:1]) for k, v in (group.get("tables") or {}).items()}
    built = {k: v for k, v in group.items() if k != "generations"}
    return hashlib.sha256(json.dumps(dict(built, tables=tables), sort_keys=True).encode()).hexdigest()


def bandfix_generation(group, map_key, geo_id=None):
    """(version, shared version) of a map's Exact coastlines tables: the ones a tn_geo reads, or the map's newest
    with no id. Its row of bandfix.generations, else bandfix.version; `shared` is the version of the K+ table
    when a later generation keeps an older one because the coast did not move."""
    rows = (group.get("generations") or {}).get(map_key) or []
    if geo_id is None:
        rows = rows[-1:]
    for r in rows:
        if geo_id is None or geo_id in (r.get("geographies") or []):
            return int(r["version"]), int(r.get("shared", r["version"]))
    return int(group["version"]), int(group["version"])


def placeholder_names(cfg):
    """The placeholder's noise names (never registered or released; europe-coast retires them)."""
    ph = cfg.get("placeholder") or {}
    names = ph.get("names") or {}
    if not isinstance(names, dict):
        raise ConfigError("config.lua placeholder.names must be a keyed table")
    return sorted(names.values())


def noise_names(cfg):
    """Every noise name config.lua defines: released bodies (the region layer's every name among
    them, its row names composed from config.lua's stems and suffix and the table's ids), Map type
    fallbacks, firewall bodies, the start mask versions, every geography version's spawn bodies
    and the placeholder's names."""
    spawn = {sp[n] for vs in geography_versions(cfg).values() for v in vs for sp in [spawn_of(v)] if sp
             for n in SPAWN_NAMES}
    return sorted(set(release_names(cfg)) | set(fallback_names(cfg)) | set(firewall_names(cfg)) |
                  {m["name"] for m in start_masks(cfg)} | spawn | set(placeholder_names(cfg)))


def unregistered_names(cfg, registered):
    """The noise names config.lua defines that tests/frozen.json must hold but does not: every one
    (the region layer's row names included) but the placeholder's names and the Map type fallbacks
    that mirror a startup setting (U3's one exemption; a frozen fallback is registered).
    `registered` is frozen.json's bodies table (or any collection of names)."""
    exempt = set(placeholder_names(cfg)) | set(exempt_fallback_names(cfg))
    return sorted(n for n in noise_names(cfg) if n not in exempt and n not in registered)


def defined_names(cfg):
    """Every name config.lua defines for the game: mod ID, settings and their dropdown labels'
    locale keys, presets and noise names (released bodies with the region layer's composed names,
    Map type fallbacks, firewall bodies and the placeholder's names). Used by the T16 name scan, the
    locale check and the dump facts."""
    ident = cfg["identity"]
    out = {"mod": {ident["id"]}, "setting": set(), "string_setting_value": set(), "preset": set(),
           "noise": set(), "placeholder_noise": set(), "fallback_noise": set()}
    for s in _keyed(cfg, "settings").values():
        out["setting"].add(s["name"])
        for v in s.get("allowed_values") or []:
            out["string_setting_value"].add(f"{s['name']}-{v}")
    for p in _keyed(cfg, "presets").values():
        out["preset"].add(p["name"])
    out["noise"].update(noise_names(cfg))
    out["fallback_noise"].update(fallback_names(cfg))
    out["placeholder_noise"].update(placeholder_names(cfg))
    return out


def main(argv):
    import json
    path = Path(argv[1]) if len(argv) > 1 else CONFIG
    print(json.dumps(load(path), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
