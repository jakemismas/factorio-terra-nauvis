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
Numbers keep Lua's value (an integral float such as 6.0 is returned as the int 6).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "terra-nauvis" / "prototypes" / "config.lua"


class ConfigError(ValueError):
    pass


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


def load(path=CONFIG):
    """The config table of a pure-data Lua file as Python data."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    tree = parse_lua(text, str(path))
    _, astnodes = _ast()
    data = _Evaluator(astnodes, path.name).chunk(tree)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the returned value is not a keyed table")
    return data


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


def fallbacks(cfg):
    """The Map type fallbacks (U3's one exemption): `fallbacks` is keyed by map key, each a list of
    {name = <noise name>, map_qualified = <bool>} for the names that map's elevation entry reads
    and a Map type pick leaves to prototype-level fallbacks. {map key: [entry, ...]}."""
    out = {}
    maps = set(_keyed(cfg, "maps"))
    for key, entries in _keyed(cfg, "fallbacks").items():
        if key not in maps:
            raise ConfigError(f"config.lua fallbacks.{key} is not a map key")
        entries = _listed(cfg, f"fallbacks.{key}", entries)
        for e in entries:
            if not isinstance(e, dict) or not isinstance(e.get("name"), str) or \
                    not isinstance(e.get("map_qualified"), bool) or set(e) - {"name", "map_qualified"}:
                raise ConfigError(f"config.lua fallbacks.{key} entries must be {{name = <noise name>, "
                                  f"map_qualified = <bool>}}")
        out[key] = entries
    return out


def fallback_names(cfg):
    return sorted({e["name"] for entries in fallbacks(cfg).values() for e in entries})


def release_registry(cfg):
    """`release_registry` is a list of {release = <version>, geography = <id>, names = {<noise
    names>}, files = {<generated files>}} (europe-coast writes the first row)."""
    out = []
    for r in _listed(cfg, "release_registry"):
        if not isinstance(r, dict) or not isinstance(r.get("release"), str) or set(r) - {"release", "geography",
                                                                                          "names", "files"}:
            raise ConfigError("config.lua release_registry rows must be {release, geography, names, files}")
        _names(r.get("names", []), f"release_registry {r['release']} names")
        _names(r.get("files", []), f"release_registry {r['release']} files")
        out.append(r)
    return out


def release_names(cfg):
    return sorted({n for r in release_registry(cfg) for n in (r.get("names") or [])})


TOGGLE_FIELDS = {"setting", "preset_key", "default", "mechanism", "on", "off", "maps"}


def toggles(cfg):
    """`toggles` is keyed by toggle key, `toggle_order` lists those keys, as settings and presets are;
    each toggle is {setting = <settings key>, preset_key = <property_expression_names key>,
    default, mechanism = "name switch" | "hook gate", on = <name>, off = <name>, maps = {...}}.
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


def schema_problems(cfg):
    """Every shape problem of config.lua's groups, as messages (the T16 names row reports them)."""
    out = []
    for fn in (map_keys, firewall_names, fallbacks, release_registry, toggles):
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
        prefix = (cfg.get("identity") or {}).get("noise_prefix") or ""
        unprefixed = sorted(n for n in noise_names(cfg) if not prefix or not n.startswith(prefix))
        if unprefixed:
            out.append(f"config.lua noise names {unprefixed} lack the noise prefix {prefix!r}")
    except ConfigError as e:
        out.append(str(e))
    return out


def placeholder_names(cfg):
    """The placeholder's noise names (never registered or released; europe-coast retires them)."""
    ph = cfg.get("placeholder") or {}
    names = ph.get("names") or {}
    if not isinstance(names, dict):
        raise ConfigError("config.lua placeholder.names must be a keyed table")
    return sorted(names.values())


def noise_names(cfg):
    """Every noise name config.lua defines: released bodies, Map type fallbacks, firewall bodies and
    the placeholder's names."""
    return sorted(set(release_names(cfg)) | set(fallback_names(cfg)) | set(firewall_names(cfg)) |
                  set(placeholder_names(cfg)))


def unregistered_names(cfg, registered):
    """The noise names config.lua defines that tests/frozen.json must hold but does not: every one
    but the placeholder's names and the Map type fallbacks (U3's one exemption). `registered` is
    frozen.json's bodies table (or any collection of names)."""
    exempt = set(placeholder_names(cfg)) | set(fallback_names(cfg))
    return sorted(n for n in noise_names(cfg) if n not in exempt and n not in registered)


def defined_names(cfg):
    """Every name config.lua defines for the game: mod ID, settings and their dropdown labels'
    locale keys, presets and noise names (released bodies, Map type fallbacks, firewall bodies and
    the placeholder's names). Used by the T16 name scan, the locale check and the dump facts."""
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
