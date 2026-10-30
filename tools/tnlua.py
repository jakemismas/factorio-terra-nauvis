#!/usr/bin/env python3
"""The mod's settings and data stages run offline: a Lua 5.2 interpreter over luaparser's tree.

The registered noise bodies are built by code (prototypes/expressions/*.lua and presets.lua's
fallback loop) from data (config.lua, prototypes/tables/, prototypes/generated/), so a check that
reads names or data alone cannot see a body changed in place through its code. This module runs
the mod's own settings.lua and data.lua (then data-updates.lua and data-final-fixes.lua) the way
the game's stages do, with stubs for what the game provides: `data` (data.raw holding vanilla's
`map-gen-presets.default` only, and `data:extend`, which files prototypes by type and name),
`settings.startup` (every startup setting at the default value the settings stage gave it, or at a
value the caller passes), `mods` (`base` only, or the caller's) and the standard library subset
below. It returns every prototype the stage defined, as Python data in the JSON form of the
game's --dump-data, so tools/tnfrozen.py hashes them with the same function as the dumped bodies.
The gate's frozen row holds this reading to the game's own dump on every run (parity).

It needs no game, no Lua binary and no network: luaparser 4.2.0, already the T16 syntax floor,
parses the files, so CI and release.yml run it. It fails closed: a construct or a library call
outside the subset, a require it cannot resolve inside the mod, a value whose text depends on an
address (tostring of a table or function), a tie between distinct values in table.sort (Lua's
sort is not stable) and every Lua runtime error raise LuaError, never a partial result.

The subset: every statement of Lua 5.2 but goto and labels; every expression but the 5.3 integer
and bitwise operators; numbers are doubles (tostring and `..` use "%.14g", as Lua 5.2 does);
globals assert, error, ipairs, next, pairs, select, tonumber, tostring, type, unpack, log and
require; string.format (d i u c x X o e E f F g G s %, no %q), find, gmatch, gsub, len, lower,
match, rep, sub and upper (Lua patterns without %b and position captures);
table.concat, insert, remove, sort and unpack; math.abs, acos, asin, ceil, cos, deg, exp, floor, fmod,
huge, log, max, min, pi, pow, rad, sin, sqrt and tan.
"""
import math
import re
import zipfile
from functools import cmp_to_key
from pathlib import Path, PurePosixPath

import tnconfig

SETTINGS_FILES = ("settings.lua", "settings-updates.lua", "settings-final-fixes.lua")
DATA_FILES = ("data.lua", "data-updates.lua", "data-final-fixes.lua")
DEFAULT_MODS = {"base": "2.1.24"}
_PARSED = {}


class LuaError(RuntimeError):
    """Lua's error(), a runtime fault, or a construct outside the subset: the stage did not run."""


class Table:
    __slots__ = ("h",)

    def __init__(self, h=None):
        self.h = {} if h is None else h

    def get(self, k):
        return self.h.get(_key(k))

    def set(self, k, v):
        k = _key(k)
        if v is None:
            self.h.pop(k, None)
        else:
            self.h[k] = v

    def length(self):
        n = 0
        while (n + 1) in self.h:
            n += 1
        return n


class _Bool:
    """A boolean table key (Python's True and 1 would collide in a dict)."""
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __eq__(self, o):
        return isinstance(o, _Bool) and o.v == self.v

    def __hash__(self):
        return hash(("lua-bool", self.v))


def _key(k):
    if k is None:
        raise LuaError("table index is nil")
    if isinstance(k, bool):
        return _Bool(k)
    if isinstance(k, float):
        if k != k:
            raise LuaError("table index is NaN")
        if k.is_integer():
            return int(k)
    return k


def _unkey(k):
    if isinstance(k, _Bool):
        return k.v
    if isinstance(k, int):
        return float(k)
    return k


class Function:
    __slots__ = ("params", "vararg", "body", "scope", "name")

    def __init__(self, params, vararg, body, scope, name):
        self.params, self.vararg, self.body, self.scope, self.name = params, vararg, body, scope, name


class Builtin:
    __slots__ = ("fn", "name")

    def __init__(self, fn, name):
        self.fn, self.name = fn, name


class _Return(Exception):
    def __init__(self, values):
        self.values = values


class _Break(Exception):
    pass


class Scope:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def find(self, name):
        s = self
        while s is not None:
            if name in s.vars:
                return s
            s = s.parent
        return None


def lua_type(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, Table):
        return "table"
    if isinstance(v, (Function, Builtin)):
        return "function"
    raise LuaError(f"a value of Python type {type(v).__name__} reached Lua")


def fmt_number(n):
    """Lua 5.2's number to text: "%.14g"."""
    if n != n:
        raise LuaError("tostring of NaN prints a platform-dependent text (fail closed)")
    return "%.14g" % n


def tostring(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return fmt_number(v)
    if isinstance(v, str):
        return v
    raise LuaError(f"tostring of a {lua_type(v)} prints its address, which differs every run (fail closed)")


_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_HEX_RE = re.compile(r"([+-]?)0[xX]([0-9a-fA-F]+)")


def str2number(s):
    """Lua 5.2's string to number (decimal or hexadecimal integer, surrounding blanks allowed), or None."""
    t = s.strip(" \f\n\r\t\v")
    if _NUM_RE.fullmatch(t):
        return float(t)
    m = _HEX_RE.fullmatch(t)
    if m:
        return float(int(m.group(2), 16)) * (-1.0 if m.group(1) == "-" else 1.0)
    return None


def _arith_operand(v, op):
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        n = str2number(v)
        if n is not None:
            return n
    raise LuaError(f"attempt to perform arithmetic ({op}) on a {lua_type(v)} value")


def _div(a, b):
    if b == 0.0:
        if a != a or a == 0.0:
            return math.nan
        neg = (a < 0) != (math.copysign(1.0, b) < 0)
        return -math.inf if neg else math.inf
    return a / b


def _mod(a, b):
    if b == 0.0:
        return math.nan
    return a - math.floor(a / b) * b if math.isfinite(a / b) else math.nan


def _pow(a, b):
    try:
        return math.pow(a, b)
    except (OverflowError, ValueError):
        return math.nan if a < 0 else math.inf


def _concat_operand(v):
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        return fmt_number(v)
    raise LuaError(f"attempt to concatenate a {lua_type(v)} value")


def raw_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, float) and isinstance(b, float):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    return a is b


def less_than(a, b):
    if isinstance(a, float) and isinstance(b, float) and not isinstance(a, bool) and not isinstance(b, bool):
        return a < b
    if isinstance(a, str) and isinstance(b, str):
        return a.encode("utf-8") < b.encode("utf-8")
    raise LuaError(f"attempt to compare a {lua_type(a)} with a {lua_type(b)}")


def less_equal(a, b):
    if isinstance(a, float) and isinstance(b, float) and not isinstance(a, bool) and not isinstance(b, bool):
        return a <= b
    if isinstance(a, str) and isinstance(b, str):
        return a.encode("utf-8") <= b.encode("utf-8")
    raise LuaError(f"attempt to compare a {lua_type(a)} with a {lua_type(b)}")


def truthy(v):
    return v is not None and v is not False


def to_lua(v):
    """Python data (dicts, lists, numbers, strings, booleans) as Lua values."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        t = Table()
        for k, x in v.items():
            t.set(to_lua(k), to_lua(x))
        return t
    if isinstance(v, (list, tuple)):
        t = Table()
        for i, x in enumerate(v, 1):
            t.set(float(i), to_lua(x))
        return t
    if isinstance(v, (Table, Function, Builtin)):
        return v
    raise LuaError(f"cannot pass a Python {type(v).__name__} to Lua")


def to_py(v, _seen=None):
    """A Lua value as the game's JSON dump writes it: a table whose keys are exactly 1 to n is a list,
    any other table an object with text keys; integral numbers are ints."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, float):
        if v != v or v in (math.inf, -math.inf):
            raise LuaError("a prototype holds a non-finite number, which JSON cannot carry (fail closed)")
        return int(v) if v.is_integer() and abs(v) < 2 ** 53 else v
    if isinstance(v, Table):
        _seen = set() if _seen is None else _seen
        if id(v) in _seen:
            raise LuaError("a prototype table refers to itself")
        _seen = _seen | {id(v)}
        n = v.length()
        if n and n == len(v.h):
            return [to_py(v.h[i], _seen) for i in range(1, n + 1)]
        out = {}
        for k, x in v.h.items():
            k = _unkey(k)
            ks = fmt_number(k) if isinstance(k, float) else k if isinstance(k, str) else None
            if ks is None:
                raise LuaError(f"a prototype table has a {lua_type(k)} key")
            out[ks] = to_py(x, _seen)
        return out
    raise LuaError(f"a prototype holds a {lua_type(v)}")


# ------------------------------------------------------------------------------------------------ library

def _arg(args, i):
    return args[i] if i < len(args) else None


def _check_table(v, fn, i=1):
    if not isinstance(v, Table):
        raise LuaError(f"bad argument #{i} to '{fn}' (table expected, got {lua_type(v)})")
    return v


def _check_number(v, fn, i=1):
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        n = str2number(v)
        if n is not None:
            return n
    raise LuaError(f"bad argument #{i} to '{fn}' (number expected, got {lua_type(v)})")


def _check_string(v, fn, i=1):
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        return fmt_number(v)
    raise LuaError(f"bad argument #{i} to '{fn}' (string expected, got {lua_type(v)})")


_FMT_RE = re.compile(r"%([-+ #0]*)(\d*)(?:\.(\d*))?([a-zA-Z%])")


def string_format(args):
    fmt = _check_string(_arg(args, 0), "format")
    out, pos, argi = [], 0, 1
    for m in _FMT_RE.finditer(fmt):
        out.append(fmt[pos:m.start()])
        pos = m.end()
        flags, width, prec, conv = m.group(1), m.group(2), m.group(3), m.group(4)
        if conv == "%":
            if flags or width or prec is not None:
                raise LuaError("invalid conversion to 'format'")
            out.append("%")
            continue
        spec = "%" + flags + width + ("." + prec if prec is not None else "")
        v = _arg(args, argi)
        argi += 1
        if argi - 1 >= len(args):
            raise LuaError(f"bad argument #{argi} to 'format' (no value)")
        if conv in "diouxXc":
            n = _check_number(v, "format", argi)
            if not math.isfinite(n):
                raise LuaError(f"bad argument #{argi} to 'format' (number has no integer representation)")
            i = int(n)
            if not (-1 < n - i < 1):
                raise LuaError(f"bad argument #{argi} to 'format' (not a number in proper range)")
            if conv == "c":
                out.append(chr(i & 0xFF))
            elif conv == "o" and "#" in flags:
                raise LuaError("string.format %#o differs between C and Python (fail closed)")
            else:
                out.append((spec + ("d" if conv in "iu" else conv)) % i)
        elif conv in "eEfFgG":
            n = _check_number(v, "format", argi)
            if not math.isfinite(n):
                raise LuaError("string.format of a non-finite number prints a platform-dependent text (fail closed)")
            out.append((spec + conv) % n)
        elif conv == "s":
            out.append((spec + "s") % tostring(v))
        else:
            raise LuaError(f"string.format conversion %{conv} is outside the offline subset (fail closed)")
    out.append(fmt[pos:])
    rest = _FMT_RE.sub("", fmt)
    if "%" in rest:
        raise LuaError("invalid conversion in the format string of 'format'")
    return ["".join(out)]


def _string_sub(args):
    s = _check_string(_arg(args, 0), "sub")
    b = s.encode("utf-8")
    n = len(b)
    i = int(_check_number(_arg(args, 1) if len(args) > 1 else 1.0, "sub", 2))
    j = int(_check_number(_arg(args, 2), "sub", 3)) if _arg(args, 2) is not None else -1
    if i < 0:
        i = max(n + i + 1, 1)
    elif i == 0:
        i = 1
    if j < 0:
        j = n + j + 1
    elif j > n:
        j = n
    return [b[i - 1:j].decode("utf-8", "strict") if i <= j else ""]


_LUA_CLASS = {
    "a": lambda c: c.isascii() and c.isalpha(), "d": lambda c: "0" <= c <= "9",
    "l": lambda c: "a" <= c <= "z", "u": lambda c: "A" <= c <= "Z",
    "s": lambda c: c in " \t\n\v\f\r", "w": lambda c: c.isascii() and c.isalnum(),
    "x": lambda c: c in "0123456789abcdefABCDEF", "c": lambda c: ord(c) < 32 or ord(c) == 127,
    "p": lambda c: 32 < ord(c) < 127 and not c.isalnum(),
}


def _class_pred(k):
    f = _LUA_CLASS.get(k.lower())
    if f is None:
        return lambda c, k=k: c == k
    return f if k.islower() else (lambda c, f=f: not f(c))


def _set_pred(pat, i):
    """The Lua set starting after '[' at pat[i]: (predicate over one character, index after ']')."""
    neg = i < len(pat) and pat[i] == "^"
    if neg:
        i += 1
    preds, first = [], True
    while True:
        if i >= len(pat):
            raise LuaError("malformed pattern (missing ']')")
        ch = pat[i]
        if ch == "]" and not first:
            i += 1
            break
        first = False
        if ch == "%":
            if i + 1 >= len(pat):
                raise LuaError("malformed pattern (ends with '%')")
            preds.append(_class_pred(pat[i + 1]))
            i += 2
        elif i + 2 < len(pat) and pat[i + 1] == "-" and pat[i + 2] != "]":
            lo, hi = ch, pat[i + 2]
            preds.append(lambda c, lo=lo, hi=hi: lo <= c <= hi)
            i += 3
        else:
            preds.append(lambda c, ch=ch: c == ch)
            i += 1
    if neg:
        return (lambda c: not any(f(c) for f in preds)), i
    return (lambda c: any(f(c) for f in preds)), i


def _rx_class(pred):
    chars = [chr(b) for b in range(256) if pred(chr(b))]
    if not chars:
        return "(?!)"
    return "[" + "".join("\\" + c if c in "-]\\^[" else c for c in chars) + "]"


_PAT_CACHE = {}


def lua_pattern(pat):
    """A Lua 5.2 pattern as a compiled Python regex (single-byte characters; %b and position captures
    fail closed)."""
    if pat in _PAT_CACHE:
        return _PAT_CACHE[pat]
    out, i, n = [], 0, len(pat)
    if pat.startswith("^"):
        out.append(r"\A")
        i = 1
    while i < n:
        ch = pat[i]
        if ch == "(":
            if i + 1 < n and pat[i + 1] == ")":
                raise LuaError("position captures are outside the offline subset (fail closed)")
            out.append("(")
            i += 1
            continue
        if ch == ")":
            out.append(")")
            i += 1
            continue
        if ch == "$" and i == n - 1:
            out.append(r"\Z")
            i += 1
            continue
        if ch == "%":
            if i + 1 >= n:
                raise LuaError("malformed pattern (ends with '%')")
            k = pat[i + 1]
            if k == "b":
                raise LuaError("%b is outside the offline subset (fail closed)")
            if k == "f":
                if i + 2 >= n or pat[i + 2] != "[":
                    raise LuaError("missing '[' after '%f' in pattern")
                pred, j = _set_pred(pat, i + 3)
                cls = _rx_class(pred)
                if pred("\0"):
                    out.append(f"(?<={_rx_class(lambda c: not pred(c))})(?:(?={cls})|\\Z)")
                else:
                    out.append(f"(?<!{cls})(?={cls})")
                i = j
                continue
            if k.isdigit():
                out.append("\\" + k)
                i += 2
                continue
            single = _rx_class(_class_pred(k))
            i += 2
        elif ch == "[":
            pred, i = _set_pred(pat, i + 1)
            single = _rx_class(pred)
        elif ch == ".":
            single = r"[\s\S]"
            i += 1
        else:
            single = re.escape(ch)
            i += 1
        q = pat[i] if i < n else ""
        if q in ("*", "+", "?"):
            out.append(single + q)
            i += 1
        elif q == "-":
            out.append(single + "*?")
            i += 1
        else:
            out.append(single)
    rx = re.compile("".join(out))
    _PAT_CACHE[pat] = rx
    return rx


def _captures(m):
    return list(m.groups()) if m.re.groups else [m.group(0)]


def _init_pos(s, v, fn):
    i = int(_check_number(v, fn, 3)) if v is not None else 1
    if i < 0:
        i = max(len(s) + i + 1, 1)
    elif i == 0:
        i = 1
    return i - 1


def _string_find(args):
    s = _check_string(_arg(args, 0), "find")
    pat = _check_string(_arg(args, 1), "find", 2)
    i = _init_pos(s, _arg(args, 2), "find")
    if i > len(s):
        return [None]
    if truthy(_arg(args, 3)):
        k = s.find(pat, i)
        return [None] if k < 0 else [float(k + 1), float(k + len(pat))]
    m = lua_pattern(pat).search(s, i)
    if not m:
        return [None]
    return [float(m.start() + 1), float(m.end())] + (list(m.groups()) if m.re.groups else [])


def _string_match(args):
    s = _check_string(_arg(args, 0), "match")
    pat = _check_string(_arg(args, 1), "match", 2)
    i = _init_pos(s, _arg(args, 2), "match")
    if i > len(s):
        return [None]
    m = lua_pattern(pat).search(s, i)
    return _captures(m) if m else [None]


def _string_gmatch(args):
    s = _check_string(_arg(args, 0), "gmatch")
    pat = _check_string(_arg(args, 1), "gmatch", 2)
    it = lua_pattern(pat).finditer(s)

    def step(a):
        m = next(it, None)
        return _captures(m) if m else [None]
    return [Builtin(step, "gmatch iterator")]


def _gsub_text(repl, m, caps):
    out, j = [], 0
    while j < len(repl):
        c = repl[j]
        if c != "%":
            out.append(c)
            j += 1
            continue
        if j + 1 >= len(repl):
            raise LuaError("invalid use of '%' in replacement string")
        d = repl[j + 1]
        if d == "%":
            out.append("%")
        elif d == "0":
            out.append(m.group(0))
        elif d.isdigit():
            k = int(d)
            if k > len(caps):
                raise LuaError(f"invalid capture index %{k}")
            out.append(_check_string(caps[k - 1], "gsub"))
        else:
            raise LuaError("invalid use of '%' in replacement string")
        j += 2
    return "".join(out)


def _string_gsub(args, interp):
    s = _check_string(_arg(args, 0), "gsub")
    pat = _check_string(_arg(args, 1), "gsub", 2)
    repl = _arg(args, 2)
    limit = _arg(args, 3)
    limit = int(_check_number(limit, "gsub", 4)) if limit is not None else -1
    if isinstance(repl, float):
        repl = fmt_number(repl)
    count = 0

    def sub(m):
        nonlocal count
        if 0 <= limit <= count:
            return m.group(0)
        count += 1
        caps = _captures(m)
        if isinstance(repl, str):
            return _gsub_text(repl, m, caps)
        if isinstance(repl, Table):
            v = repl.get(caps[0])
        elif isinstance(repl, (Function, Builtin)):
            v = (interp.call(repl, caps) or [None])[0]
        else:
            raise LuaError(f"bad argument #3 to 'gsub' (string/function/table expected, got {lua_type(repl)})")
        if v is None or v is False:
            return m.group(0)
        if isinstance(v, (str, float)):
            return _check_string(v, "gsub")
        raise LuaError(f"invalid replacement value (a {lua_type(v)})")
    out = lua_pattern(pat).sub(sub, s)
    return [out, float(count)]


def _sort_lt(comp, interp):
    if comp is None:
        return less_than
    return lambda a, b: truthy((interp.call(comp, [a, b]) or [None])[0])


def table_sort(args, interp):
    t = _check_table(_arg(args, 0), "sort")
    comp = _arg(args, 1)
    if comp is not None and not isinstance(comp, (Function, Builtin)):
        raise LuaError("bad argument #2 to 'sort' (function expected)")
    n = t.length()
    vals = [t.h[i] for i in range(1, n + 1)]
    lt = _sort_lt(comp, interp)
    vals.sort(key=cmp_to_key(lambda a, b: -1 if lt(a, b) else (1 if lt(b, a) else 0)))
    for a, b in zip(vals, vals[1:]):
        if not lt(a, b) and not lt(b, a) and not raw_equal(a, b):
            raise LuaError("table.sort met two distinct values that compare equal: Lua's sort is not stable, so the "
                           "game's order is unknown (fail closed)")
    for i, v in enumerate(vals, 1):
        t.h[i] = v
    return []


def _table_insert(args):
    t = _check_table(_arg(args, 0), "insert")
    n = t.length()
    if len(args) == 2:
        t.set(float(n + 1), args[1])
    elif len(args) == 3:
        pos = int(_check_number(args[1], "insert", 2))
        if pos < 1 or pos > n + 1:
            raise LuaError("bad argument #2 to 'insert' (position out of bounds)")
        for i in range(n, pos - 1, -1):
            t.h[i + 1] = t.h[i]
        t.set(float(pos), args[2])
    else:
        raise LuaError("wrong number of arguments to 'insert'")
    return []


def _table_remove(args):
    t = _check_table(_arg(args, 0), "remove")
    n = t.length()
    pos = int(_check_number(args[1], "remove", 2)) if len(args) > 1 else n
    if n == 0 and len(args) < 2:
        return [None]
    if pos < 1 or pos > n + 1:
        raise LuaError("bad argument #2 to 'remove' (position out of bounds)")
    v = t.h.get(pos)
    for i in range(pos, n):
        t.h[i] = t.h[i + 1]
    t.h.pop(n, None)
    return [v]


def _unpack(args):
    t = _check_table(_arg(args, 0), "unpack")
    i = int(_check_number(_arg(args, 1), "unpack", 2)) if _arg(args, 1) is not None else 1
    j = int(_check_number(_arg(args, 2), "unpack", 3)) if _arg(args, 2) is not None else t.length()
    return [t.h.get(k) for k in range(i, j + 1)]


def _table_concat(args):
    t = _check_table(_arg(args, 0), "concat")
    sep = _check_string(_arg(args, 1), "concat", 2) if _arg(args, 1) is not None else ""
    i = int(_check_number(_arg(args, 2), "concat", 3)) if _arg(args, 2) is not None else 1
    j = int(_check_number(_arg(args, 3), "concat", 4)) if _arg(args, 3) is not None else t.length()
    parts = []
    for k in range(i, j + 1):
        v = t.h.get(k)
        if not isinstance(v, (str, float)) or isinstance(v, bool):
            raise LuaError(f"invalid value (at index {k}) in table for 'concat'")
        parts.append(_concat_operand(v))
    return [sep.join(parts)]


def _math1(fn, name):
    def f(args):
        x = _check_number(_arg(args, 0), name)
        try:
            return [float(fn(x))]
        except (OverflowError, ValueError):
            return [math.nan]
    return f


def _floor(args):
    x = _check_number(_arg(args, 0), "floor")
    return [float(math.floor(x)) if math.isfinite(x) else x]


def _ceil(args):
    x = _check_number(_arg(args, 0), "ceil")
    return [float(math.ceil(x)) if math.isfinite(x) else x]


def _minmax(args, name, better):
    if not args:
        raise LuaError(f"bad argument #1 to '{name}' (number expected, got no value)")
    best = _check_number(args[0], name)
    for i, a in enumerate(args[1:], 2):
        x = _check_number(a, name, i)
        if better(x, best):
            best = x
    return [best]


def _tonumber(args):
    v, base = _arg(args, 0), _arg(args, 1)
    if base is None:
        if isinstance(v, float):
            return [v]
        if isinstance(v, str):
            return [str2number(v)]
        return [None]
    b = int(_check_number(base, "tonumber", 2))
    s = _check_string(v, "tonumber").strip().lower()
    neg = s.startswith("-")
    s = s[1:] if neg else s
    try:
        n = float(int(s, b)) if s and re.fullmatch(r"[0-9a-z]+", s) else None
    except ValueError:
        n = None
    return [(-n if neg else n) if n is not None else None]


def _select(args):
    n = _arg(args, 0)
    if n == "#":
        return [float(len(args) - 1)]
    i = int(_check_number(n, "select"))
    if i < 0:
        i = len(args) + i
        if i < 1:
            raise LuaError("bad argument #1 to 'select' (index out of range)")
    elif i == 0:
        raise LuaError("bad argument #1 to 'select' (index out of range)")
    return list(args[i:])


def _error(args):
    msg = _arg(args, 0)
    raise LuaError(f"error(): {tostring(msg) if isinstance(msg, (str, float, bool)) or msg is None else lua_type(msg)}")


def _assert(args):
    if not truthy(_arg(args, 0)):
        msg = _arg(args, 1)
        raise LuaError(f"assertion failed: {tostring(msg) if isinstance(msg, (str, float)) else ''}")
    return list(args)


def _next(args):
    t = _check_table(_arg(args, 0), "next")
    k = _arg(args, 1)
    keys = list(t.h)
    if k is None:
        i = 0
    else:
        kk = _key(k)
        try:
            i = keys.index(kk) + 1
        except ValueError:
            raise LuaError("invalid key to 'next'")
    if i >= len(keys):
        return [None]
    return [_unkey(keys[i]), t.h[keys[i]]]


def _pairs(args):
    t = _check_table(_arg(args, 0), "pairs")
    keys = list(t.h)
    state = {"i": 0}

    def step(_a):
        while state["i"] < len(keys):
            k = keys[state["i"]]
            state["i"] += 1
            if k in t.h:
                return [_unkey(k), t.h[k]]
        return [None]
    return [Builtin(step, "pairs iterator"), t, None]


def _ipairs(args):
    t = _check_table(_arg(args, 0), "ipairs")

    def step(a):
        i = int(a[1]) + 1
        v = t.h.get(i)
        return [None] if v is None else [float(i), v]
    return [Builtin(step, "ipairs iterator"), t, 0.0]


def _type(args):
    if not args:
        raise LuaError("bad argument #1 to 'type' (value expected)")
    return [lua_type(args[0])]


def _lib(interp):
    def B(fn, name):
        return Builtin(fn, name)
    string = Table()
    for name, fn in {
            "format": string_format, "sub": _string_sub, "find": _string_find, "match": _string_match,
            "gmatch": _string_gmatch, "gsub": lambda a: _string_gsub(a, interp),
            "len": lambda a: [float(len(_check_string(_arg(a, 0), "len").encode("utf-8")))],
            "lower": lambda a: [_check_string(_arg(a, 0), "lower").lower()],
            "upper": lambda a: [_check_string(_arg(a, 0), "upper").upper()],
            "rep": lambda a: [_check_string(_arg(a, 0), "rep") * max(0, int(_check_number(_arg(a, 1), "rep", 2)))]}.items():
        string.set(name, B(fn, "string." + name))
    table = Table()
    for name, fn in {"concat": _table_concat, "insert": _table_insert, "remove": _table_remove,
                     "sort": lambda a: table_sort(a, interp), "unpack": _unpack}.items():
        table.set(name, B(fn, "table." + name))
    m = Table()
    for name, fn in {"abs": abs, "cos": math.cos, "sin": math.sin, "tan": math.tan, "sqrt": math.sqrt,
                     "exp": math.exp, "rad": math.radians, "deg": math.degrees, "asin": math.asin,
                     "acos": math.acos}.items():
        m.set(name, B(_math1(fn, name), "math." + name))
    m.set("floor", B(_floor, "math.floor"))
    m.set("ceil", B(_ceil, "math.ceil"))
    m.set("log", B(lambda a: [math.log(_check_number(_arg(a, 0), "log")) if _arg(a, 1) is None else
                              math.log(_check_number(_arg(a, 0), "log")) / math.log(_check_number(_arg(a, 1), "log", 2))],
                   "math.log"))
    m.set("fmod", B(lambda a: [math.fmod(_check_number(_arg(a, 0), "fmod"), _check_number(_arg(a, 1), "fmod", 2))],
                    "math.fmod"))
    m.set("pow", B(lambda a: [_pow(_check_number(_arg(a, 0), "pow"), _check_number(_arg(a, 1), "pow", 2))], "math.pow"))
    m.set("max", B(lambda a: _minmax(a, "max", lambda x, b: x > b), "math.max"))
    m.set("min", B(lambda a: _minmax(a, "min", lambda x, b: x < b), "math.min"))
    m.set("pi", math.pi)
    m.set("huge", math.inf)
    g = {
        "assert": B(_assert, "assert"), "error": B(_error, "error"), "ipairs": B(_ipairs, "ipairs"),
        "next": B(_next, "next"), "pairs": B(_pairs, "pairs"), "select": B(_select, "select"),
        "tonumber": B(_tonumber, "tonumber"), "tostring": B(lambda a: [tostring(_arg(a, 0))], "tostring"),
        "type": B(_type, "type"), "unpack": B(_unpack, "unpack"), "log": B(lambda a: [], "log"),
        "string": string, "table": table, "math": m,
    }
    return g, string


# ------------------------------------------------------------------------------------------------ interpreter

class Interpreter:
    """One Lua state: the globals of one stage and its module cache."""

    def __init__(self, reader, globals_=None):
        self.reader = reader
        self.astnodes = tnconfig._ast()[1]
        self.globals = Scope()
        lib, self.string_lib = _lib(self)
        self.globals.vars.update(lib)
        self.globals.vars["require"] = Builtin(self._require, "require")
        for k, v in (globals_ or {}).items():
            self.globals.vars[k] = v
        self.loaded = {}
        self.where = "?"
        n = self.astnodes
        self._expr = {
            n.Nil: lambda e, s: None, n.TrueExpr: lambda e, s: True, n.FalseExpr: lambda e, s: False,
            n.Number: lambda e, s: float(e.n), n.String: self._string, n.Name: self._name, n.Index: self._index,
            n.Table: self._table, n.AnonymousFunction: self._anon, n.Concat: self._concat,
            n.AndLoOp: self._and, n.OrLoOp: self._or, n.ULNotOp: lambda e, s: not truthy(self.ev(e.operand, s)),
            n.UMinusOp: lambda e, s: -_arith_operand(self.ev(e.operand, s), "unm"),
            n.ULengthOP: self._len, n.EqToOp: lambda e, s: raw_equal(self.ev(e.left, s), self.ev(e.right, s)),
            n.NotEqToOp: lambda e, s: not raw_equal(self.ev(e.left, s), self.ev(e.right, s)),
            n.LessThanOp: lambda e, s: less_than(self.ev(e.left, s), self.ev(e.right, s)),
            n.GreaterThanOp: lambda e, s: less_than(self.ev(e.right, s), self.ev(e.left, s)),
            n.LessOrEqThanOp: lambda e, s: less_equal(self.ev(e.left, s), self.ev(e.right, s)),
            n.GreaterOrEqThanOp: lambda e, s: less_equal(self.ev(e.right, s), self.ev(e.left, s)),
            n.AddOp: self._arith(lambda a, b: a + b, "add"), n.SubOp: self._arith(lambda a, b: a - b, "sub"),
            n.MultOp: self._arith(lambda a, b: a * b, "mul"), n.FloatDivOp: self._arith(_div, "div"),
            n.ModOp: self._arith(_mod, "mod"), n.ExpoOp: self._arith(_pow, "pow"),
        }
        self._stat = {
            n.LocalAssign: self._local_assign, n.Assign: self._assign, n.Call: self._call_stat,
            n.Invoke: self._call_stat, n.LocalFunction: self._local_function, n.Function: self._function,
            n.Method: self._method, n.Return: self._return, n.If: self._if, n.While: self._while,
            n.Repeat: self._repeat, n.Fornum: self._fornum, n.Forin: self._forin, n.Do: self._do,
            n.Break: self._break, n.SemiColon: lambda st, s: None,
        }

    # -- errors

    def fail(self, node, why):
        raise LuaError(f"{self.where}:{getattr(node, 'line', None) or '?'}: {why}")

    # -- chunks and require

    def run_file(self, rel):
        text = self.reader.read(rel)
        if text is None:
            raise LuaError(f"{rel} is missing")
        return self.run_chunk(text, rel)

    def run_chunk(self, text, where):
        tree = parse(text, where)
        prev, self.where = self.where, where
        try:
            self.block(tree.body, Scope(self.globals), varargs=[])
            return []
        except _Return as r:
            return r.values
        except _Break:
            raise LuaError(f"{where}: break outside a loop")
        except RecursionError as e:
            raise LuaError(f"{where}: stack overflow") from e
        finally:
            self.where = prev

    def _require(self, args):
        name = _arg(args, 0)
        if not isinstance(name, str):
            raise LuaError(f"bad argument #1 to 'require' (string expected, got {lua_type(name)})")
        rel = self.reader.module_path(name)
        if rel is None:
            raise LuaError(f"require({name!r}): the offline stage resolves only this mod's own files from its root "
                           f"(fail closed)")
        if rel not in self.loaded:
            self.loaded[rel] = None
            vals = self.run_file(rel)
            v = vals[0] if vals else None
            self.loaded[rel] = True if v is None else v
        elif self.loaded[rel] is None:
            raise LuaError(f"require({name!r}): a require loop")
        return [self.loaded[rel]]

    # -- blocks and statements

    def block(self, block, scope, varargs=None):
        if varargs is not None:
            scope.vars["..."] = varargs
        stat = self._stat
        for st in block.body:
            fn = stat.get(type(st))
            if fn is None:
                if isinstance(st, self.astnodes.Comment):
                    continue
                self.fail(st, f"the statement {type(st).__name__} is outside the offline subset (fail closed)")
            fn(st, scope)

    def _local_assign(self, st, scope):
        for t in st.targets:
            if getattr(t, "attribute", None) is not None:
                self.fail(st, "local attributes (<const>, <close>) are Lua 5.4")
        vals = self.explist(st.values or [], scope)
        for i, t in enumerate(st.targets):
            scope.vars[t.id] = vals[i] if i < len(vals) else None

    def _assign(self, st, scope):
        n = self.astnodes
        refs = []
        for t in st.targets:
            if isinstance(t, n.Name):
                refs.append(("name", t.id, None))
            elif isinstance(t, n.Index):
                obj = self.ev(t.value, scope)
                key = t.idx.id if t.notation == n.IndexNotation.DOT else self.ev(t.idx, scope)
                refs.append(("index", obj, key))
            else:
                self.fail(st, f"cannot assign to a {type(t).__name__}")
        vals = self.explist(st.values, scope)
        for i, (kind, a, b) in enumerate(refs):
            v = vals[i] if i < len(vals) else None
            if kind == "name":
                self.set_name(a, v, scope)
            else:
                if not isinstance(a, Table):
                    self.fail(st, f"attempt to index a {lua_type(a)} value")
                a.set(b, v)

    def set_name(self, name, v, scope):
        s = scope.find(name)
        (s or self.globals).vars[name] = v

    def _call_stat(self, st, scope):
        self.call_expr(st, scope)

    def make_function(self, args, body, scope, name):
        n = self.astnodes
        params, vararg = [], False
        for a in args:
            if isinstance(a, n.Name):
                params.append(a.id)
            elif isinstance(a, (n.Varargs, n.Dots)):
                vararg = True
            else:
                self.fail(a, f"unsupported parameter {type(a).__name__}")
        return Function(params, vararg, body, scope, name)

    def _local_function(self, st, scope):
        scope.vars[st.name.id] = None
        scope.vars[st.name.id] = self.make_function(st.args, st.body, scope, st.name.id)

    def _function(self, st, scope):
        n = self.astnodes
        f = self.make_function(st.args, st.body, scope, getattr(st.name, "id", "function"))
        if isinstance(st.name, n.Name):
            self.set_name(st.name.id, f, scope)
        elif isinstance(st.name, n.Index):
            obj = self.ev(st.name.value, scope)
            if not isinstance(obj, Table):
                self.fail(st, f"attempt to index a {lua_type(obj)} value")
            key = st.name.idx.id if st.name.notation == n.IndexNotation.DOT else self.ev(st.name.idx, scope)
            obj.set(key, f)
        else:
            self.fail(st, "unsupported function name")

    def _method(self, st, scope):
        n = self.astnodes
        obj = self.ev(st.source, scope)
        if not isinstance(obj, Table):
            self.fail(st, f"attempt to index a {lua_type(obj)} value")
        f = self.make_function([n.Name("self")] + list(st.args), st.body, scope, st.name.id)
        obj.set(st.name.id, f)

    def _return(self, st, scope):
        vals = st.values
        if vals is None:
            raise _Return([])
        if not isinstance(vals, list):
            vals = [vals]
        raise _Return(self.explist(vals, scope))

    def _if(self, st, scope):
        n = self.astnodes
        node = st
        while True:
            if truthy(self.ev(node.test, scope)):
                self.block(node.body, Scope(scope))
                return
            orelse = node.orelse
            if orelse is None:
                return
            if isinstance(orelse, n.ElseIf):
                node = orelse
                continue
            if isinstance(orelse, n.Block):
                self.block(orelse, Scope(scope))
                return
            if isinstance(orelse, list):
                self.block(n.Block(orelse), Scope(scope))
                return
            self.fail(st, f"unsupported else branch {type(orelse).__name__}")

    def _while(self, st, scope):
        guard = 0
        while truthy(self.ev(st.test, scope)):
            guard += 1
            if guard > 10 ** 8:
                self.fail(st, "a while loop ran 10^8 times")
            try:
                self.block(st.body, Scope(scope))
            except _Break:
                break

    def _repeat(self, st, scope):
        guard = 0
        while True:
            guard += 1
            if guard > 10 ** 8:
                self.fail(st, "a repeat loop ran 10^8 times")
            inner = Scope(scope)
            try:
                self.block(st.body, inner)
            except _Break:
                break
            if truthy(self.ev(st.test, inner)):
                break

    def _fornum(self, st, scope):
        start = _arith_operand(self.ev(st.start, scope), "for initial value")
        stop = _arith_operand(self.ev(st.stop, scope), "for limit")
        step = float(st.step) if isinstance(st.step, (int, float)) else _arith_operand(self.ev(st.step, scope),
                                                                                       "for step")
        if step == 0:
            self.fail(st, "'for' step is zero")
        i = start
        while (step > 0 and i <= stop) or (step < 0 and i >= stop):
            inner = Scope(scope)
            inner.vars[st.target.id] = i
            try:
                self.block(st.body, inner)
            except _Break:
                break
            i += step

    def _forin(self, st, scope):
        vals = self.explist(st.iter, scope)
        f, s, var = (vals + [None, None, None])[:3]
        names = [t.id for t in st.targets]
        while True:
            r = self.call(f, [s, var])
            first = r[0] if r else None
            if first is None:
                break
            var = first
            inner = Scope(scope)
            for i, nm in enumerate(names):
                inner.vars[nm] = r[i] if i < len(r) else None
            try:
                self.block(st.body, inner)
            except _Break:
                break

    def _do(self, st, scope):
        self.block(st.body, Scope(scope))

    def _break(self, st, scope):
        raise _Break()

    # -- expressions

    def ev(self, e, scope):
        fn = self._expr.get(type(e))
        if fn is not None:
            return fn(e, scope)
        n = self.astnodes
        if isinstance(e, (n.Call, n.Invoke)):
            r = self.call_expr(e, scope)
            return r[0] if r else None
        if isinstance(e, (n.Varargs, n.Dots)):
            va = self._varargs(e, scope)
            return va[0] if va else None
        self.fail(e, f"the expression {type(e).__name__} is outside the offline subset (fail closed)")

    def explist(self, exprs, scope):
        """Values of an expression list, the last call or ... expanded (a wrapped one truncated)."""
        n = self.astnodes
        out = []
        for i, e in enumerate(exprs):
            last = i == len(exprs) - 1
            if last and not getattr(e, "wrapped", False) and isinstance(e, (n.Call, n.Invoke)):
                out += self.call_expr(e, scope)
            elif last and not getattr(e, "wrapped", False) and isinstance(e, (n.Varargs, n.Dots)):
                out += self._varargs(e, scope)
            else:
                out.append(self.ev(e, scope))
        return out

    def _varargs(self, e, scope):
        s = scope.find("...")
        if s is None or s.vars["..."] is None:
            self.fail(e, "cannot use '...' outside a vararg function")
        return list(s.vars["..."])

    def _string(self, e, scope):
        s = e.s
        if isinstance(s, (bytes, bytearray)):
            try:
                return s.decode("utf-8")
            except UnicodeDecodeError:
                self.fail(e, "a string literal that is not UTF-8")
        return s

    def _name(self, e, scope):
        s = scope.find(e.id)
        if s is None:
            return self.globals.vars.get(e.id)
        return s.vars[e.id]

    def index(self, obj, key, node):
        if isinstance(obj, Table):
            return obj.get(key)
        if isinstance(obj, str):
            return self.string_lib.get(key)
        self.fail(node, f"attempt to index a {lua_type(obj)} value (field {key!r})")

    def _index(self, e, scope):
        obj = self.ev(e.value, scope)
        key = e.idx.id if e.notation == self.astnodes.IndexNotation.DOT else self.ev(e.idx, scope)
        return self.index(obj, key, e)

    def _table(self, e, scope):
        n = self.astnodes
        t = Table()
        pos = 1
        fields = e.fields
        for i, f in enumerate(fields):
            if f.key is None:
                last = i == len(fields) - 1
                if last and not getattr(f.value, "wrapped", False) and isinstance(f.value, (n.Call, n.Invoke,
                                                                                            n.Varargs, n.Dots)):
                    for v in self.explist([f.value], scope):
                        t.set(float(pos), v)
                        pos += 1
                else:
                    t.set(float(pos), self.ev(f.value, scope))
                    pos += 1
                continue
            if not f.between_brackets and isinstance(f.key, n.Name):
                key = f.key.id
            else:
                key = self.ev(f.key, scope)
            t.set(key, self.ev(f.value, scope))
        return t

    def _anon(self, e, scope):
        return self.make_function(e.args, e.body, scope, "anonymous")

    def _concat(self, e, scope):
        return _concat_operand(self.ev(e.left, scope)) + _concat_operand(self.ev(e.right, scope))

    def _and(self, e, scope):
        a = self.ev(e.left, scope)
        return self.ev(e.right, scope) if truthy(a) else a

    def _or(self, e, scope):
        a = self.ev(e.left, scope)
        return a if truthy(a) else self.ev(e.right, scope)

    def _len(self, e, scope):
        v = self.ev(e.operand, scope)
        if isinstance(v, str):
            return float(len(v.encode("utf-8")))
        if isinstance(v, Table):
            return float(v.length())
        self.fail(e, f"attempt to get length of a {lua_type(v)} value")

    def _arith(self, op, name):
        def f(e, scope):
            return op(_arith_operand(self.ev(e.left, scope), name), _arith_operand(self.ev(e.right, scope), name))
        return f

    # -- calls

    def call_expr(self, e, scope):
        n = self.astnodes
        if isinstance(e, n.Invoke):
            obj = self.ev(e.source, scope)
            fn = self.index(obj, e.func.id, e)
            args = [obj] + self.explist(e.args, scope)
        else:
            fn = self.ev(e.func, scope)
            args = self.explist(e.args, scope)
        if not isinstance(fn, (Function, Builtin)):
            what = getattr(e.func, "id", None) or type(e.func).__name__
            self.fail(e, f"attempt to call a {lua_type(fn)} value ({what})")
        return self.call(fn, args)

    def call(self, fn, args):
        if isinstance(fn, Builtin):
            r = fn.fn(list(args))
            return list(r) if r else []
        if not isinstance(fn, Function):
            raise LuaError(f"{self.where}: attempt to call a {lua_type(fn)} value")
        scope = Scope(fn.scope)
        for i, p in enumerate(fn.params):
            scope.vars[p] = args[i] if i < len(args) else None
        # a function without ... hides its enclosing function's (None: '...' is a compile error there)
        scope.vars["..."] = list(args[len(fn.params):]) if fn.vararg else None
        try:
            self.block(fn.body, scope)
        except _Return as r:
            return r.values
        return []


def parse(text, where):
    """luaparser's tree of `text`, kept per text (one static run reads the same files many times)."""
    import hashlib
    k = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if k not in _PARSED:
        try:
            _PARSED[k] = tnconfig.parse_lua(text, where)
        except tnconfig.ConfigError as e:
            raise LuaError(str(e)) from e
    return _PARSED[k]


# ------------------------------------------------------------------------------------------------ readers

class DirReader:
    """The mod's files from a folder (the checkout's terra-nauvis/ or a copy)."""

    def __init__(self, root):
        self.root = Path(root)

    def read(self, rel):
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def exists(self, rel):
        return (self.root / rel).is_file()

    def module_path(self, name):
        return _module_path(name, self.exists)

    def label(self):
        return str(self.root)


class ZipReader:
    """The mod's files from a mod zip (one top folder, any name)."""

    def __init__(self, path_or_bytes):
        import io
        src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
        self.name = "<bytes>" if isinstance(path_or_bytes, (bytes, bytearray)) else str(path_or_bytes)
        with zipfile.ZipFile(src) as zf:
            names = [i.filename for i in zf.infolist() if not i.is_dir()]
            tops = {n.split("/", 1)[0] for n in names}
            if len(tops) != 1 or any("/" not in n for n in names):
                raise LuaError(f"{self.name}: a mod zip holds one top folder, found {sorted(tops)[:3]}")
            top = tops.pop() + "/"
            self.files = {n[len(top):]: zf.read(n) for n in names}

    def read(self, rel):
        b = self.files.get(rel)
        return b.decode("utf-8") if b is not None else None

    def exists(self, rel):
        return rel in self.files

    def module_path(self, name):
        return _module_path(name, self.exists)

    def label(self):
        return self.name


def _module_path(name, exists):
    """A require name as a file at the mod root ("a.b" and "a/b" both read a/b.lua), or None."""
    if not isinstance(name, str) or not name or name.startswith("__") or ".." in name.replace(".", "/").split("/"):
        return None
    stem = name[:-4] if name.endswith(".lua") else name
    rel = stem.replace(".", "/") if "/" not in stem else stem
    rel = str(PurePosixPath(rel)) + ".lua"
    if rel.startswith("/") or not exists(rel):
        return None
    return rel


# ------------------------------------------------------------------------------------------------ stages

def _data_global(raw):
    data = Table()
    data.set("raw", raw)

    def extend(args):
        self_, protos = _arg(args, 0), _arg(args, 1)
        if self_ is not data:
            raise LuaError("data.extend must be called as data:extend(...)")
        _check_table(protos, "extend", 2)
        for i in range(1, protos.length() + 1):
            p = protos.h[i]
            if not isinstance(p, Table):
                raise LuaError(f"data:extend: entry {i} is a {lua_type(p)}, not a prototype")
            t, nm = p.get("type"), p.get("name")
            if not isinstance(t, str) or not isinstance(nm, str):
                raise LuaError(f"data:extend: entry {i} lacks a text type and name")
            bucket = raw.get(t)
            if bucket is None:
                bucket = Table()
                raw.set(t, bucket)
            bucket.set(nm, p)
        return []
    data.set("extend", Builtin(extend, "data.extend"))
    return data


def settings_stage(reader, mods=None):
    """{setting name: prototype} as settings.lua and its siblings define them."""
    raw = Table()
    interp = Interpreter(reader, {"data": _data_global(raw), "mods": to_lua(dict(mods or DEFAULT_MODS))})
    for f in SETTINGS_FILES:
        if reader.exists(f):
            interp.run_file(f)
    out = {}
    for t in ("bool-setting", "int-setting", "double-setting", "string-setting", "color-setting"):
        b = raw.get(t)
        if isinstance(b, Table):
            for k, p in b.h.items():
                out[_unkey(k)] = to_py(p)
    return out


VANILLA_RAW = tnconfig.REPO / "tests" / "vanilla-raw.json"


def vanilla_raw(path=VANILLA_RAW):
    """The base game's prototypes the mod's data stage reads (tests/vanilla-raw.json, a reduced
    base-only --dump-data), {type: {name: prototype}}, or {} when the file is absent."""
    import json
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("raw") or {}


def data_stage(reader, values=None, mods=None, base=None):
    """Every prototype the mod's data stage defines, {type: {name: prototype}}, as the dump writes
    them. Startup settings read their default values unless `values` names one. data.raw starts with
    `base` (default: vanilla_raw()), the base game's prototypes the mod's hooks and wrappers read,
    beside vanilla's default map-gen-presets entry."""
    sets = settings_stage(reader, mods)
    startup = Table()
    for name, p in sets.items():
        if p.get("setting_type") != "startup":
            continue
        v = (values or {}).get(name, p.get("default_value"))
        startup.set(name, to_lua({"value": v}))
    settings = Table()
    settings.set("startup", startup)
    raw = Table()
    for t, protos in sorted((vanilla_raw() if base is None else base).items()):
        if t != "map-gen-presets":
            raw.set(t, to_lua(protos))
    presets = Table()
    presets.set("default", to_lua({"type": "map-gen-presets", "name": "default"}))
    raw.set("map-gen-presets", presets)
    interp = Interpreter(reader, {"data": _data_global(raw), "settings": settings,
                                  "mods": to_lua(dict(mods or DEFAULT_MODS))})
    for f in DATA_FILES:
        if reader.exists(f):
            interp.run_file(f)
    out = {}
    for t, b in raw.h.items():
        if isinstance(b, Table):
            out[_unkey(t)] = {_unkey(k): to_py(p) for k, p in b.h.items()}
    return out


def reader_for(source):
    """A reader for a mod folder, a mod zip's path, or a mod zip's bytes."""
    if isinstance(source, (bytes, bytearray)):
        return ZipReader(source)
    p = Path(source)
    if p.is_dir():
        return DirReader(p)
    if p.is_file() and p.suffix.lower() == ".zip":
        return ZipReader(p)
    raise LuaError(f"{source} is neither a mod folder nor a mod zip")
