#!/usr/bin/env python3
"""T16 static rows (test notes.md T16; design section 5, `earth_test.py static`).

Every row here reads only the checked-out tree: no game, no fh.py, no FACTORIO_WS and no git refs,
so ci.yml runs the same rows on GitHub's runner that the gate runs as its step 1. Each row returns
a list of failure messages (empty means pass) and a short detail line.

Rows: lint, info_json, locale, dashes, registration, names, design_rules, launch_scan, output_args,
workflow_scan, attribution_scan, data_src, frozen_static, zip, plus fixture positive controls
for the scans (each rule must fail its own fixture; fixtures are written at run time into a
temporary directory outside the scanned trees and never committed).
"""
import ast as pyast
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_zip  # noqa: E402
import tnconfig  # noqa: E402
import tnguard  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
LINT = HERE / "lint"
# Dot directories (.git, the gitignored scratch folder) are skipped by walk_files; these are the rest.
# The mod scans never use walk_files: they read build_zip's own file list (mod_files), so every
# file the zip ships is scanned and a skipped folder cannot hide one.
SKIP_DIRS = {"dist", "spikes", "__pycache__", "node_modules"}
# Needles of the launch scan, assembled so this file holds no literal the scan would flag in itself.
GAME_IMAGE = "factorio" + ".exe"
APPDATA_WORD = "app" + "data"

EN_EM_DASHES = {"\u2012": "figure dash", "\u2013": "en dash", "\u2014": "em dash", "\u2015": "horizontal bar",
                "\u2e3a": "two-em dash", "\u2e3b": "three-em dash"}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")
SPACE_AGE_FLAGS = {"quality_required", "rail_bridges_required", "spoiling_required", "freezing_required",
                   "segmented_units_required", "expansion_shaders_required", "expansion_required",
                   "space_travel_required"}
DEP_RE = re.compile(r"^\s*(?P<prefix>\(\?\)|[!?~+])?\s*(?P<name>[A-Za-z0-9_\-]+(?: [A-Za-z0-9_\-]+)*)\s*"
                    r"(?:(?P<op><=|>=|<|>|=)\s*(?P<ver>\S+))?\s*$")
ALLOWED_EVENTS = {"on_surface_created", "on_player_created", "on_runtime_mod_setting_changed"}
BANDFIX_EVENTS = {"on_chunk_generated", "on_chunk_deleted", "on_surface_cleared", "on_surface_deleted"}
BANDFIX_FILE = "scripts/bandfix.lua"
SCRIPT_LIFECYCLE = {"on_init", "on_load", "on_configuration_changed"}
DATA_LUA = ("prototypes/config.lua", "prototypes/tables/", "prototypes/generated/")


# ------------------------------------------------------------------------------------------------ helpers

def rel(p, root=REPO):
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk_files(root, suffixes=None, skip=SKIP_DIRS):
    root = Path(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip and not d.startswith("."))
        for f in sorted(filenames):
            p = Path(dirpath) / f
            if suffixes is None or p.suffix.lower() in suffixes:
                out.append(p)
    return out


def mod_files(mod=MOD):
    """Every file of the mod folder by build_zip's own classification: what the zip ships and what
    the build refuses (the zip row reports a refusal; the scans still read the file)."""
    ships, refused = build_zip.classify_files(Path(mod))
    return [Path(mod) / r for r in ships + refused]


def mod_lua(mod=MOD):
    return [p for p in mod_files(mod) if p.suffix.lower() == ".lua"]


def walk_all(root):
    """Every file under root except inside .git and __pycache__ folders: the launch and attribution
    scans read dot folders and the folders walk_files skips (dist, spikes, node_modules) too."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in (".git", "__pycache__"))
        out += [Path(dirpath) / f for f in sorted(filenames)]
    return out


def read_text_or_none(p):
    """A file's text, or None for a binary file (a NUL byte, or not UTF-8)."""
    b = Path(p).read_bytes()
    if b"\0" in b:
        return None
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


def lua_strings(tree, astnodes):
    """Every string literal of a luaparser tree as (value, line)."""
    out = []
    for node in tnconfig_walk(tree):
        if isinstance(node, astnodes.String):
            s = node.s.decode("utf-8", "replace") if isinstance(node.s, (bytes, bytearray)) else node.s
            out.append((s, getattr(node, "line", None)))
    return out


def tnconfig_walk(node):
    """Depth-first walk over luaparser nodes."""
    from luaparser import astnodes
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for k, v in vars(n).items():
            if k.startswith("_") or k in ("comments", "first_token", "last_token", "parent"):
                continue
            if isinstance(v, astnodes.Node):
                stack.append(v)
            elif isinstance(v, list):
                stack.extend(x for x in v if isinstance(x, astnodes.Node))


def parse_lua_file(p):
    return tnconfig.parse_lua(Path(p).read_text(encoding="utf-8"), rel(p))


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def lint_manifest(lint_dir=LINT):
    return load_json(Path(lint_dir) / "manifest.json")


# ------------------------------------------------------------------------------------------------ lint

def find_luacheck(manifest):
    """The linter binary: TN_LUACHECK, then PATH, then the manifest's per-user install paths."""
    cands = []
    env = os.environ.get("TN_LUACHECK")
    if env:
        cands.append(Path(env))
    for name in ("luacheck.exe", "luacheck"):
        w = shutil.which(name)
        if w:
            cands.append(Path(w))
    for p in manifest["linter"].get("user_install_paths", []):
        cands.append(Path(os.path.expanduser(p)))
    for c in cands:
        if c.is_file():
            return c
    return None


LUACHECK_TOTAL_RE = re.compile(r"Total: (\d+) warnings? / (\d+) errors? in (\d+) files?")
LUACHECK_FILE_RE = re.compile(r"^Checking (\S+)\s+(OK|\d+ warnings?|\d+ errors?.*|Syntax error.*)$", re.M)


def run_luacheck(root, files, manifest, lint_dir=LINT):
    """(failures, detail, checked_count) for luacheck over the given files (paths relative to root)."""
    fails = []
    exe = find_luacheck(manifest)
    want = manifest["linter"]
    if exe is None:
        return [f"{want['name']} {want['version']} not found (set TN_LUACHECK, or install it per tools/lint/manifest.json)"], "", 0
    got_sha = sha256_file(exe)
    if got_sha != want["sha256"]:
        return [f"{exe} has sha256 {got_sha}, manifest records {want['sha256']}"], "", 0
    if not files:
        return ["no Lua files to lint: an empty list fails (T16 exit-0 guard)"], "", 0
    cfg_path = Path(lint_dir) / "luacheckrc.lua"
    cmd = [str(exe), "--config", str(cfg_path), "--no-color", "--codes"] + [f.as_posix() for f in files]
    cp = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = cp.stdout + cp.stderr
    m = LUACHECK_TOTAL_RE.search(out)
    if not m:
        return [f"luacheck printed no total line (exit {cp.returncode}): {out[-400:]}"], "", 0
    warnings, errors, checked = (int(x) for x in m.groups())
    seen = {x.group(1) for x in LUACHECK_FILE_RE.finditer(out)}
    expect = {f.as_posix() for f in files}
    allow = load_json(Path(lint_dir) / "allowlist.json").get("luacheck", [])
    flagged = [l.strip() for l in out.splitlines() if re.search(r":\d+:\d+: \([EW]\d+\)", l)]
    not_allowed = [l for l in flagged if not any(a in l for a in allow)]
    if checked != len(files):
        fails.append(f"luacheck checked {checked} files, the zip holds {len(files)} Lua files")
    if seen != expect:
        fails.append(f"luacheck reported files {sorted(seen ^ expect)[:6]} differently from the zip's list")
    if errors:
        fails.append(f"luacheck errors: {errors}")
    if not_allowed:
        fails.append("luacheck warnings not in tools/lint/allowlist.json: " + "; ".join(not_allowed[:8]))
    if cp.returncode not in (0, 1) or (cp.returncode == 1 and not flagged):
        fails.append(f"luacheck exit {cp.returncode}")
    return fails, f"{want['name']} {want['version']}: {warnings} warnings / {errors} errors in {checked} files", checked


def row_lint(repo=REPO, lint_dir=LINT):
    manifest = lint_manifest(lint_dir)
    fails = []
    try:
        import importlib.metadata as md
        lp = md.version("luaparser")
    except Exception:
        lp = None
    if lp != manifest["luaparser"]["version"]:
        fails.append(f"luaparser {lp} installed, tools/lint/manifest.json records {manifest['luaparser']['version']}")
    mod = Path(repo) / "terra-nauvis"
    _, listing = build_zip.zip_bytes(mod, top=mod.name)
    # the zip's own entries, not a second walk of the folder, so the count check can fail
    zip_lua = [Path("terra-nauvis") / e["name"].split("/", 1)[1] for e in listing if e["name"].endswith(".lua")]
    if sorted(zip_lua) != sorted(p.relative_to(repo) for p in mod_lua(mod)):
        fails.append("the mod scans' Lua list differs from the zip's entries")
    lf, detail, checked = run_luacheck(repo, zip_lua, manifest, lint_dir)
    fails += lf
    parsed, bad = 0, []
    floor = sorted({Path(repo) / z for z in zip_lua} | set(walk_files(repo, {".lua"})))
    for p in floor:
        try:
            parse_lua_file(p)
            parsed += 1
        except tnconfig.ConfigError as e:
            bad.append(str(e)[:200])
    fails += [f"luaparser: {b}" for b in bad]
    if parsed == 0:
        fails.append("luaparser parsed no Lua file")
    return fails, f"{detail}; luaparser {lp} parsed {parsed} repo Lua files"


# ------------------------------------------------------------------------------------------------ info.json

def version_parts(v):
    parts = v.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return [int(p) for p in parts]


def check_info(info, cfg):
    fails = []
    ident = cfg["identity"]
    for key, want in (("name", ident["id"]), ("version", ident["version"]), ("title", ident["title"]),
                      ("author", ident["author"]), ("factorio_version", ident["factorio_version"])):
        if info.get(key) != want:
            fails.append(f"info.json {key} is {info.get(key)!r}, config.lua says {want!r}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(info.get("version", ""))):
        fails.append("info.json version is not x.y.z")
    if info.get("factorio_version") != "2.1":
        fails.append("factorio_version must be \"2.1\"")
    if len(str(info.get("title", ""))) > 100:
        fails.append(f"title is {len(info['title'])} characters (at most 100)")
    for flag in sorted(SPACE_AGE_FLAGS & set(info)):
        fails.append(f"Space Age feature flag {flag} in info.json")
    deps = info.get("dependencies")
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        fails.append("dependencies must be a list of strings")
        deps = []
    base_ok = False
    for d in deps:
        m = DEP_RE.match(d)
        if not m:
            fails.append(f"dependency {d!r} does not parse")
            continue
        name, op, ver, prefix = m.group("name"), m.group("op"), m.group("ver"), m.group("prefix")
        if name == "space-age" and prefix != "!":
            fails.append(f"dependency {d!r} needs Space Age")
        if ver is not None:
            parts = version_parts(ver)
            if parts is None or len(parts) < 2 or len(parts) > 3:
                fails.append(f"dependency {d!r}: version needs two or three numbers")
            if prefix == "?":
                fails.append(f"optional dependency {d!r} carries a version (mod-management rule 6)")
        elif op is not None:
            fails.append(f"dependency {d!r} has an operator but no version")
        if name == "base" and prefix is None and op == ">=" and ver == ident["base_version"]:
            base_ok = True
    if not base_ok:
        fails.append(f"dependencies lack \"base >= {ident['base_version']}\"")
    return fails


def row_info(mod=MOD):
    cfg = tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    info = load_json(Path(mod) / "info.json")
    fails = check_info(info, cfg)
    return fails, f"{info.get('name')} {info.get('version')} factorio {info.get('factorio_version')}, " \
                  f"{len(info.get('dependencies', []))} dependencies"


# ------------------------------------------------------------------------------------------------ locale

def parse_cfg(text, where="locale"):
    """{section: {key: value}} and the list of format errors of a Factorio locale .cfg file."""
    sections, errors, cur = {"": {}}, [], ""
    for i, line in enumerate(text.split("\n"), 1):
        s = line.rstrip("\r")
        if not s.strip() or s.lstrip().startswith(("#", ";")):
            continue
        m = re.fullmatch(r"\[([^\]]+)\]\s*", s)
        if m:
            cur = m.group(1)
            if cur in sections and cur != "":
                errors.append(f"{where}:{i}: section [{cur}] repeated")
            sections.setdefault(cur, {})
            continue
        if "=" not in s:
            errors.append(f"{where}:{i}: line has no '=' (fails the load, S11)")
            continue
        k, v = s.split("=", 1)
        if k in sections[cur]:
            errors.append(f"{where}:{i}: key {cur}.{k} defined twice")
        sections[cur][k] = v
    return sections, errors


def expected_locale(cfg, control_keys=()):
    ident = cfg["identity"]
    exp = {"mod-name": {ident["id"]}, "mod-description": {ident["id"]}, "mod-setting-name": set(),
           "mod-setting-description": set(), "string-mod-setting": set(), "map-gen-preset-name": set(),
           "map-gen-preset-description": set()}
    for s in cfg.get("settings", {}).values():
        exp["mod-setting-name"].add(s["name"])
        exp["mod-setting-description"].add(s["name"])
        if s.get("type") == "string-setting":
            for v in s.get("allowed_values") or []:
                exp["string-mod-setting"].add(f"{s['name']}-{v}")
    for p in cfg.get("presets", {}).values():
        exp["map-gen-preset-name"].add(p["name"])
        exp["map-gen-preset-description"].add(p["name"])
    for sec, key in control_keys:
        exp.setdefault(sec, set()).add(key)
    return exp


def control_locale_keys(mod=MOD):
    """Locale keys control code references: {"section.key", ...} tables in control.lua and scripts/."""
    from luaparser import astnodes
    keys = []
    files = [p for p in mod_lua(mod) if rel(p, mod) == "control.lua" or rel(p, mod).startswith("scripts/")]
    for p in files:
        for node in tnconfig_walk(parse_lua_file(p)):
            if isinstance(node, astnodes.Table) and node.fields and node.fields[0].key is None:
                v = node.fields[0].value
                if isinstance(v, astnodes.String):
                    s = v.s.decode() if isinstance(v.s, bytes) else v.s
                    m = re.fullmatch(r"([a-z0-9_-]+)\.([A-Za-z0-9_.-]+)", s)
                    if m:
                        keys.append((m.group(1), m.group(2)))
    return keys


def row_locale(mod=MOD):
    cfg = tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    files = sorted((Path(mod) / "locale" / "en").glob("*.cfg"))
    fails = []
    if not files:
        return ["no locale/en/*.cfg file"], ""
    merged = {}
    for f in files:
        secs, errs = parse_cfg(f.read_text(encoding="utf-8"), rel(f))
        fails += errs
        for sec, kv in secs.items():
            for k, v in kv.items():
                if k in merged.setdefault(sec, {}):
                    fails.append(f"key {sec}.{k} defined in two files")
                merged[sec][k] = v
    exp = expected_locale(cfg, control_locale_keys(mod))
    for sec, keys in exp.items():
        have = set(merged.get(sec, {}))
        for k in sorted(keys - have):
            fails.append(f"locale lacks [{sec}] {k}")
    for sec, kv in merged.items():
        for k, v in kv.items():
            if not v.strip():
                fails.append(f"locale [{sec}] {k} is empty")
    n = sum(len(v) for v in merged.values())
    return fails, f"{len(files)} file(s), {n} keys, {sum(len(v) for v in exp.values())} required"


# ------------------------------------------------------------------------------------------------ dashes

def text_files(root):
    """The shipped text files of a mod folder (build_zip's list, binaries left out)."""
    return [p for p in mod_files(root) if p.suffix.lower() not in {".png", ".zip", ".dat", ".npz", ".npy"}]


def dash_findings(root):
    out = []
    for p in text_files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(f"{rel(p)}: not UTF-8 text")
            continue
        for i, line in enumerate(text.split("\n"), 1):
            for ch, name in EN_EM_DASHES.items():
                if ch in line:
                    out.append(f"{rel(p)}:{i}: {name}")
            if EMOJI_RE.search(line):
                out.append(f"{rel(p)}:{i}: emoji or pictograph")
    return out


def row_dashes(mod=MOD):
    f = dash_findings(mod)
    return f, f"{len(text_files(mod))} shipped text files"


# ------------------------------------------------------------------------------------------------ registration

def _dotted(node, astnodes):
    """'a.b.c' for a Name/Index chain with dot notation, else None."""
    parts = []
    while isinstance(node, astnodes.Index):
        if node.notation != astnodes.IndexNotation.DOT or not isinstance(node.idx, astnodes.Name):
            return None
        parts.append(node.idx.id)
        node = node.value
    if isinstance(node, astnodes.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _children(n, astnodes):
    for k, v in vars(n).items():
        if k.startswith("_") or k in ("comments", "first_token", "last_token", "parent"):
            continue
        if isinstance(v, astnodes.Node):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, astnodes.Node):
                    yield x


# Reads of the global script that register nothing; every other use of `script` must be a direct
# call script.on_event(defines.events.<allowed>, ...) or a lifecycle registration.
SCRIPT_READS = {"mod_name", "active_mods", "feature_flags", "level"}
# Indirect access to globals or to code: any of these could reach script or register a handler.
INDIRECT_NAMES = {"_G", "_ENV", "rawget", "rawset", "getfenv", "setfenv", "load", "loadstring", "loadfile", "dofile"}
# Core lualib modules a mod may require that register no event (the core event_handler library does).
REQUIRE_OK = {"util", "__core__/lualib/util", "__core__.lualib.util"}
PER_TICK_EVENTS = {"on_tick"}


def registration_findings(mod=MOD):
    """Event registrations against ARCHITECTURE.md's event table, as an allowlist. The global
    `script` may appear only as the base of a direct call script.on_event(defines.events.<name>, ...)
    with a literal event from the table, a lifecycle call (on_init, on_load,
    on_configuration_changed) in control.lua or scripts/, or a read of script.mod_name,
    active_mods, feature_flags or level; any other reference (an alias, an argument, a stored
    method, bracket indexing, a method call) is flagged. So are _G, _ENV, rawget, rawset, getfenv,
    setfenv, load, loadstring, loadfile and dofile; a require that is not a string literal naming a
    file of the mod or an allowed core module (the core event_handler library registers events); a
    reference to defines.events.on_tick or on_nth_tick anywhere and to a per-chunk event outside
    scripts/bandfix.lua, whatever the call; a computed index into defines.events; and an alias of
    defines or defines.events."""
    from luaparser import astnodes
    DOT = astnodes.IndexNotation.DOT
    out = []
    for p in mod_lua(mod):
        r = rel(p, mod)
        control_side = r == "control.lua" or r.startswith("scripts/")
        tree = parse_lua_file(p)
        nodes = list(tnconfig_walk(tree))
        parent = {}
        for n in nodes:
            for c in _children(n, astnodes):
                parent[id(c)] = n
        targets = set()
        for n in nodes:
            if isinstance(n, (astnodes.Assign, astnodes.LocalAssign)):
                targets.update(id(t) for t in n.targets)

        def line(n):
            return getattr(n, "line", None) or getattr(parent.get(id(n)), "line", "?")

        def is_script(n):
            return isinstance(n, astnodes.Name) and n.id == "script"
        allowed = set()
        for n in nodes:
            if isinstance(n, astnodes.Call) and isinstance(n.func, astnodes.Index) and n.func.notation == DOT \
                    and is_script(n.func.value) and isinstance(n.func.idx, astnodes.Name):
                what = n.func.idx.id
                if what in SCRIPT_LIFECYCLE:
                    allowed.add(id(n.func.value))
                    if not control_side:
                        out.append(f"{r}:{line(n)}: script.{what} outside control.lua and scripts/")
                elif what == "on_event":
                    allowed.add(id(n.func.value))
                    if not control_side:
                        out.append(f"{r}:{line(n)}: script.on_event outside control.lua and scripts/")
                    if not n.args:
                        out.append(f"{r}:{line(n)}: script.on_event without an event")
                        continue
                    ev = n.args[0]
                    evs = [f.value for f in ev.fields] if isinstance(ev, astnodes.Table) else [ev]
                    for e in evs:
                        d = _dotted(e, astnodes)
                        if not d or not d.startswith("defines.events.") or d.count(".") != 2:
                            out.append(f"{r}:{line(n)}: computed or non-literal event id (only defines.events.<name> "
                                       f"literals)")
                            continue
                        name = d.rsplit(".", 1)[1]
                        if name in BANDFIX_EVENTS:
                            if r != BANDFIX_FILE:
                                out.append(f"{r}:{line(n)}: per-chunk event {name} outside {BANDFIX_FILE}")
                        elif name not in ALLOWED_EVENTS:
                            out.append(f"{r}:{line(n)}: event {name} is not in ARCHITECTURE.md's event table")
                else:
                    out.append(f"{r}:{line(n)}: script.{what} is not an allowed registration")
                    allowed.add(id(n.func.value))
            elif isinstance(n, astnodes.Index) and n.notation == DOT and is_script(n.value) \
                    and isinstance(n.idx, astnodes.Name) and n.idx.id in SCRIPT_READS and id(n) not in targets:
                allowed.add(id(n.value))
        for n in nodes:
            if is_script(n) and id(n) not in allowed:
                out.append(f"{r}:{line(n)}: references the global script outside a direct allowed call (an alias, "
                           f"argument, stored method or method call can register any handler)")
            if isinstance(n, astnodes.Name) and n.id in INDIRECT_NAMES:
                out.append(f"{r}:{line(n)}: {n.id} (indirect access to globals or code)")
            if isinstance(n, astnodes.Name) and n.id == "require":
                call = parent.get(id(n))
                arg = call.args[0] if isinstance(call, astnodes.Call) and call.func is n and len(call.args) == 1 else None
                mod_name = (arg.s.decode() if isinstance(arg.s, bytes) else arg.s) \
                    if isinstance(arg, astnodes.String) else None
                if mod_name is None:
                    out.append(f"{r}:{line(n)}: require without one literal module name")
                elif mod_name not in REQUIRE_OK and not (Path(mod) / (mod_name.replace(".", "/") + ".lua")).is_file():
                    out.append(f"{r}:{line(n)}: require({mod_name!r}) is neither a file of the mod nor an allowed core "
                               f"module (the core event_handler library registers events)")
            if isinstance(n, astnodes.Name) and n.id == "defines":
                par = parent.get(id(n))
                if not (isinstance(par, astnodes.Index) and par.value is n and par.notation == DOT):
                    out.append(f"{r}:{line(n)}: defines used other than as defines.<member> (an alias)")
            if isinstance(n, astnodes.Index) and isinstance(n.value, astnodes.Name) and n.value.id == "defines" \
                    and n.notation == DOT and isinstance(n.idx, astnodes.Name) and n.idx.id == "events":
                par = parent.get(id(n))
                if not (isinstance(par, astnodes.Index) and par.value is n):
                    out.append(f"{r}:{line(n)}: defines.events used other than as defines.events.<name> (an alias)")
                elif par.notation != DOT or not isinstance(par.idx, astnodes.Name):
                    out.append(f"{r}:{line(n)}: computed index into defines.events")
                else:
                    ev = par.idx.id
                    if ev in PER_TICK_EVENTS:
                        out.append(f"{r}:{line(n)}: references defines.events.{ev} (no per-tick handler)")
                    elif ev in BANDFIX_EVENTS and r != BANDFIX_FILE:
                        out.append(f"{r}:{line(n)}: references the per-chunk event {ev} outside {BANDFIX_FILE}")
            if isinstance(n, (astnodes.Index, astnodes.Name)):
                d = _dotted(n, astnodes)
                if d and (d.endswith(".on_nth_tick") or d == "on_nth_tick"):
                    out.append(f"{r}:{line(n)}: references {d} (no per-tick handler)")
            if isinstance(n, astnodes.String):
                s = n.s.decode() if isinstance(n.s, bytes) else n.s
                if s in ("on_tick", "on_nth_tick"):
                    out.append(f"{r}:{line(n)}: string {s!r} (computed per-tick handler)")
                elif s in BANDFIX_EVENTS and r != BANDFIX_FILE:
                    out.append(f"{r}:{line(n)}: string {s!r} (computed per-chunk handler outside {BANDFIX_FILE})")
            if isinstance(n, astnodes.Invoke) and is_script(n.source):
                out.append(f"{r}:{line(n)}: script:{getattr(n.func, 'id', '?')} method call")
    return sorted(set(out))


def row_registration(mod=MOD):
    f = registration_findings(mod)
    return f, f"{len(mod_lua(mod))} Lua files scanned against the event allowlist"


# ------------------------------------------------------------------------------------------------ names

def lua_identifier_names(tree, astnodes):
    """Every identifier a Lua file uses where a game name can stand, as (id, line, form): the field
    of a dot index (`data.raw["noise-expression"].tn_x`, `function M.tn_x()`), the Name key of a
    table constructor field (`{tn_x = 1}`), a method call's name (`obj:tn_x()`) and a method
    definition's name (`function M:tn_x()`). A rename must stay a config edit, so these count as
    spellings exactly like string literals (design constraint 5)."""
    out = []
    for node in tnconfig_walk(tree):
        line = getattr(node, "line", None)
        if isinstance(node, astnodes.Index) and node.notation == astnodes.IndexNotation.DOT and \
                isinstance(node.idx, astnodes.Name):
            out.append((node.idx.id, line, "dot index"))
        elif isinstance(node, astnodes.Field) and not node.between_brackets and isinstance(node.key, astnodes.Name):
            out.append((node.key.id, line, "table key"))
        elif isinstance(node, astnodes.Invoke) and isinstance(node.func, astnodes.Name):
            out.append((node.func.id, line, "method call"))
        elif isinstance(node, astnodes.Method) and isinstance(node.name, astnodes.Name):
            out.append((node.name.id, line, "method name"))
    return out


def test_mod_files(mod=MOD):
    """The test-only mods beside the mod folder (tools/mods/ of the same tree): every Lua file and
    info.json. They get every Earth name from the runner at run time (ARCHITECTURE.md module map)."""
    test_mods_dir = Path(mod).parent / "tools" / "mods"
    if not test_mods_dir.is_dir():
        return []
    return [p for p in walk_files(test_mods_dir) if p.suffix.lower() == ".lua" or p.name == "info.json"]


def name_findings(mod=MOD):
    """No Lua file but config.lua spells an Earth name, as a string or as an identifier (a dot-index
    field, a table key, a method name), in the mod and in the test-only mods of tools/mods/ (whose
    info.json files are read too); the locale keys match config's names."""
    cfg = tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    ident = cfg["identity"]
    schema = tnconfig.schema_problems(cfg)
    if schema:
        return [f"config.lua schema: {x}" for x in schema]
    names = tnconfig.defined_names(cfg)
    every = set().union(*names.values())
    prefix_re = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(ident["noise_prefix"]))
    from luaparser import astnodes
    out = []

    def judge(where, s, kind):
        if ident["id"] in s:
            out.append(f"{where}: {kind} spells the mod ID {ident['id']!r}")
        elif prefix_re.search(s):
            out.append(f"{where}: {kind} spells a noise name ({ident['noise_prefix']}...): {s!r}")
        elif s in every:
            out.append(f"{where}: {kind} spells the config name {s!r}")

    lua_files = [(p, rel(p, mod)) for p in mod_lua(mod) if rel(p, mod) != "prototypes/config.lua"]
    lua_files += [(p, rel(p, Path(mod).parent)) for p in test_mod_files(mod) if p.suffix.lower() == ".lua"]
    for p, r in lua_files:
        tree = parse_lua_file(p)
        for s, line in lua_strings(tree, astnodes):
            judge(f"{r}:{line}", s, "string")
        for s, line, form in lua_identifier_names(tree, astnodes):
            judge(f"{r}:{line}", s, f"identifier ({form})")
    for p in test_mod_files(mod):
        if p.name != "info.json":
            continue
        r = rel(p, Path(mod).parent)

        def strings(o):
            if isinstance(o, str):
                yield o
            elif isinstance(o, dict):
                for k, v in o.items():
                    yield str(k)
                    yield from strings(v)
            elif isinstance(o, list):
                for v in o:
                    yield from strings(v)
        for s in strings(load_json(p)):
            judge(r, s, "string")
    # The locale's keys are exactly config's names (no stray key a rename would leave behind).
    exp = expected_locale(cfg, control_locale_keys(mod))
    for f in sorted((Path(mod) / "locale" / "en").glob("*.cfg")):
        secs, _ = parse_cfg(f.read_text(encoding="utf-8"), rel(f))
        for sec, kv in secs.items():
            for k in kv:
                if k not in exp.get(sec, set()):
                    out.append(f"{rel(f)}: [{sec}] {k} is not a name config.lua defines")
    return out


def row_names(mod=MOD):
    f = name_findings(mod)
    return f, (f"Lua strings and identifiers outside config.lua ({len(mod_lua(mod)) - 1} mod files, "
               f"{len(test_mod_files(mod))} test-mod files of tools/mods/), info.json (lint row) and locale keys "
               f"against config.lua")


# ------------------------------------------------------------------------------------------------ design rules

NUM_IN_STRING_RE = re.compile(r"(?<![A-Za-z_])(\d+(?:\.\d+)?)")


def design_findings(mod=MOD, rules_path=REPO / "tests" / "design-rules.json"):
    from luaparser import astnodes
    cfg = tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    rules = load_json(rules_path)
    out = []
    # Setting defaults equal APPROVALS 1a, for the settings that exist (each milestone adds its rows).
    have = cfg.get("settings", {})
    rows = rules.get("settings", {})
    for key in sorted(set(have) | set(rows)):
        if key not in rows:
            out.append(f"setting {key} has no row in tests/design-rules.json")
            continue
        if key not in have:
            out.append(f"tests/design-rules.json row {key} names a setting config.lua does not define")
            continue
        for field in ("type", "setting_type", "default_value", "allowed_values"):
            if field in rows[key] and have[key].get(field) != rows[key][field]:
                out.append(f"setting {key}: {field} is {have[key].get(field)!r}, APPROVALS 1a says {rows[key][field]!r}")
    # D2: no setting selects the map.
    map_ids = set()
    for m in cfg.get("maps", {}).values():
        map_ids |= {m["key"], m["setting_key"], m["display"]}
    for key, s in have.items():
        vals = set(s.get("allowed_values") or [])
        if len(vals & map_ids) >= 2 or s["name"].endswith("-map"):
            out.append(f"setting {key} selects the map (D2)")
    allowed_nums = set(rules.get("numeric_literals_allowed", [0, 1, 2]))
    for p in mod_lua(mod):
        r = rel(p, mod)
        tree = parse_lua_file(p)
        for s, line in lua_strings(tree, astnodes):
            low = s.lower()
            if "silo" in low or "teleport" in low:
                out.append(f"{r}:{line}: silo or teleporter name {s!r} (D1)")
        if any(r == d or r.startswith(d) for d in DATA_LUA if d.endswith("/")) or r in DATA_LUA:
            continue
        for node in tnconfig_walk(tree):
            if isinstance(node, astnodes.Number) and node.n not in allowed_nums:
                out.append(f"{r}:{getattr(node, 'line', '?')}: numeric literal {node.n} outside the data tables")
            if isinstance(node, astnodes.String):
                s = node.s.decode() if isinstance(node.s, bytes) else node.s
                for m in NUM_IN_STRING_RE.finditer(s):
                    v = float(m.group(1))
                    if v not in allowed_nums:
                        out.append(f"{r}:{getattr(node, 'line', '?')}: number {m.group(1)} inside a string outside "
                                   f"the data tables")
    for t in tnconfig.toggles(cfg):
        if t.get("mechanism") not in ("name switch", "hook gate"):
            out.append(f"toggle {t.get('setting')}: mechanism {t.get('mechanism')!r} is neither a name switch nor "
                       f"a hook gate (U5)")
    return out


def toggle_multiply_findings(expressions, toggle_keys):
    """U5 on dumped bodies: no toggle key used as a multiplicand. expressions: {name: text}."""
    out = []
    for key in toggle_keys:
        pat = re.compile(r"\*\s*\(?\s*" + re.escape(key) + r"\b|\b" + re.escape(key) + r"\s*\)?\s*\*")
        for name, text in expressions.items():
            if isinstance(text, str) and pat.search(text):
                out.append(f"{name} multiplies by the toggle {key} (U5)")
    return out


def row_design(mod=MOD):
    f = design_findings(mod)
    return f, "APPROVALS 1a defaults for existing settings, D1, D2, literals outside data tables, U5"


# ------------------------------------------------------------------------------------------------ launch scan

def fh_flags(lint_dir=LINT):
    d = load_json(Path(lint_dir) / "fh-flags.json")
    return set(d["GUI_FLAGS"]), set(d["FORBIDDEN_EXTRA"])


LAUNCH_FUNCS = {"run", "Popen", "call", "check_call", "check_output", "system", "startfile", "execv", "execvp",
                "spawnv", "spawnl", "create_subprocess_exec", "create_subprocess_shell"}
COPY_FUNCS = {"copy", "copy2", "copyfile", "copytree", "move", "replace", "rename"}
MODS_RE = re.compile(r"(^|[\\/])mods([\\/]|$)", re.I)
COPY_CMDS = {"copy-item", "copy", "xcopy", "robocopy", "cp", "move-item", "mv", "move"}


def _docstring_ids(tree):
    ids = set()
    for node in pyast.walk(tree):
        if isinstance(node, (pyast.Module, pyast.FunctionDef, pyast.AsyncFunctionDef, pyast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], pyast.Expr) and isinstance(body[0].value, pyast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _consts(node):
    return [n.value for n in pyast.walk(node) if isinstance(n, pyast.Constant) and isinstance(n.value, str)]


def _call_name(call):
    f = call.func
    if isinstance(f, pyast.Attribute):
        return f.attr
    if isinstance(f, pyast.Name):
        return f.id
    return ""


def _is_fh_marker(el):
    if isinstance(el, pyast.Constant) and isinstance(el.value, str) and el.value.replace("\\", "/").endswith("fh.py"):
        return True
    if isinstance(el, pyast.Name) and el.id.upper() in ("FH", "FH_PY"):
        return True
    if isinstance(el, pyast.Attribute) and el.attr.upper() in ("FH", "FH_PY"):
        return True
    return False


# assembled from fragments, like APPDATA_WORD, so this file holds no literal its own scan flags
LIVE_WORDS = (APPDATA_WORD, "roam" + "ing\\factorio", "roam" + "ing/factorio", "system-" + "write-data")
OUT_FLAGS = {"--out-dir", "--out", "--out-root", "--png-out", "--json-out", "--mod-directory"}
WRITE_FUNCS = {"write_bytes", "write_text", "copyfile", "copyfileobj", "symlink", "symlink_to", "hardlink_to",
               "link", "link_to", "unpack_archive", "make_archive", "extractall", "build"}
FACTORIO_MODS_RE = re.compile(r"(^|[\\/])factorio[\\/]+mods([\\/]|$)", re.I)


def live_word(text):
    low = text.lower()
    return next((w for w in LIVE_WORDS if w in low), None)


def _assignments(tree):
    """{name: [value nodes]} of every simple assignment in the file (any scope)."""
    env = {}
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Assign):
            for t in node.targets:
                if isinstance(t, pyast.Name):
                    env.setdefault(t.id, []).append(node.value)
        elif isinstance(node, (pyast.AnnAssign, pyast.AugAssign)) and isinstance(node.target, pyast.Name) and node.value:
            env.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, pyast.NamedExpr):
            env.setdefault(node.target.id, []).append(node.value)
    return env


PATH_CALLS = {"str", "Path", "PurePath", "PureWindowsPath", "WindowsPath", "PosixPath", "fspath", "abspath",
              "normpath", "realpath", "expanduser", "expandvars", "resolve", "absolute", "joinpath", "join"}


def _folds(node, env, depth=0, seen=None):
    """Best-effort string values of an expression (at most 16): string constants; + and / joins;
    f-strings; str(), Path(), os.path.join() and similar wrappers and methods; os.environ[...] and
    getenv(...) as %NAME%; and names through every assignment in the file. Unknown parts read '?'."""
    seen = seen or set()
    if depth > 12:
        return ["?"]
    if isinstance(node, pyast.Constant):
        return [node.value] if isinstance(node.value, str) else ["?"]
    if isinstance(node, pyast.JoinedStr):
        outs = [""]
        for v in node.values:
            parts = _folds(v.value if isinstance(v, pyast.FormattedValue) else v, env, depth + 1, seen)
            outs = [a + b for a in outs for b in parts][:16]
        return outs
    if isinstance(node, pyast.BinOp) and isinstance(node.op, (pyast.Add, pyast.Div)):
        sep = "/" if isinstance(node.op, pyast.Div) else ""
        return [a + sep + b for a in _folds(node.left, env, depth + 1, seen)
                for b in _folds(node.right, env, depth + 1, seen)][:16]
    if isinstance(node, pyast.Name):
        if node.id in seen or node.id not in env:
            return ["?"]
        out = []
        for v in env[node.id]:
            out += _folds(v, env, depth + 1, seen | {node.id})
        return out[:16] or ["?"]
    if isinstance(node, pyast.Subscript):
        base = node.value
        if isinstance(base, pyast.Attribute) and base.attr == "environ":
            key = _folds(node.slice, env, depth + 1, seen)
            return [f"%{k}%" for k in key][:16]
        return ["?"]
    if isinstance(node, pyast.Call):
        nm = _call_name(node)
        if nm in ("getenv", "get") and node.args and isinstance(node.func, pyast.Attribute) and (
                nm == "getenv" or (isinstance(node.func.value, pyast.Attribute) and node.func.value.attr == "environ")):
            return [f"%{k}%" for k in _folds(node.args[0], env, depth + 1, seen)][:16]
        if nm in PATH_CALLS:
            parts = []
            if isinstance(node.func, pyast.Attribute) and nm not in ("join",):
                parts.append(_folds(node.func.value, env, depth + 1, seen))
            parts += [_folds(a, env, depth + 1, seen) for a in node.args]
            outs = [""]
            for ps in parts:
                outs = [a + ("/" if a else "") + b for a in outs for b in ps][:16]
            return outs
    return ["?"]


def _last_component(s):
    return re.split(r"[\\/]", s.strip().strip("\"'"))[-1].lower()


def py_launch_findings(path, text, gui, forbidden, allow_exe, allow_live=False):
    out = []
    try:
        tree = pyast.parse(text)
    except SyntaxError as e:
        return [f"{path}: Python syntax error {e}"]
    docs = _docstring_ids(tree)
    env = _assignments(tree)
    # Graphical and portal long flags have no use but launching the game, so they fail anywhere in
    # code. The isolation flags (--config, --mod-directory, -c, ...) and the short graphical flags
    # (-s, -m) are ordinary options of other programs (git -c, python -m, luacheck --config), so
    # they fail only as argv tokens bound for fh.py.
    gui_long = {f for f in gui if f.startswith("--")}
    bound_only = (gui | forbidden) - gui_long
    fh_bound = set()
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Call):
            nm = _call_name(node).lower()
            if "fh" in nm.split("_") or nm.startswith("fh") or nm.endswith("_fh"):
                for a in node.args:
                    for sub in pyast.walk(a):
                        if isinstance(sub, (pyast.List, pyast.Tuple)):
                            fh_bound.add(id(sub))
    for node in pyast.walk(tree):
        if isinstance(node, (pyast.List, pyast.Tuple)):
            els = node.elts
            consts = [e.value for e in els if isinstance(e, pyast.Constant) and isinstance(e.value, str)]
            bound = id(node) in fh_bound or any(_is_fh_marker(e) for e in els) or \
                "--instance" in consts or "--modset" in consts
            for c in consts:
                tok = c.split("=", 1)[0]
                if bound and tok in bound_only:
                    out.append(f"{path}:{node.lineno}: argv token {c!r} bound for fh.py is a flag fh.py refuses")
            low = [c.lower() for c in consts]
            if any("mapshot" in c for c in low) and "render" in low:
                out.append(f"{path}:{node.lineno}: mapshot render in an argument list")
            for i, e in enumerate(els[:-1]):
                if isinstance(e, pyast.Constant) and isinstance(e.value, str) and e.value in OUT_FLAGS:
                    for v in _folds(els[i + 1], env):
                        if MODS_RE.search(v) or live_word(v):
                            out.append(f"{path}:{node.lineno}: {e.value} points into a mods folder or the live profile")
                            break
        if isinstance(node, pyast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            v = node.value
            lv = v.lower()
            if v.split("=", 1)[0] in gui_long:
                out.append(f"{path}:{node.lineno}: {v!r} is a graphical or portal flag fh.py refuses")
            if GAME_IMAGE in lv and not allow_exe:
                out.append(f"{path}:{node.lineno}: names the game image outside the process-inspection module")
            if live_word(v) and not allow_live:
                out.append(f"{path}:{node.lineno}: live-profile path ({live_word(v)})")
            if FACTORIO_MODS_RE.search(v):
                out.append(f"{path}:{node.lineno}: a Factorio mods folder path")
        if isinstance(node, pyast.Call):
            nm = _call_name(node)
            if nm in LAUNCH_FUNCS and node.args:
                first = node.args[0]
                prog = first.elts[0] if isinstance(first, (pyast.List, pyast.Tuple)) and first.elts else first
                for c in _folds(prog, env):
                    lc = _last_component(c.split(" ")[0] if isinstance(first, pyast.Constant) else c)
                    if GAME_IMAGE in c.lower() or lc in ("factorio", GAME_IMAGE):
                        out.append(f"{path}:{node.lineno}: launches the game directly (only fh.py launches the game)")
                        break
            dests = []
            if nm in COPY_FUNCS and len(node.args) >= 2:
                dests.append(node.args[1])
            if nm in WRITE_FUNCS:
                if isinstance(node.func, pyast.Attribute):
                    dests.append(node.func.value)
                dests += list(node.args[:1]) + [k.value for k in node.keywords if k.arg in ("out_dir", "dst", "dest")]
            if nm == "open" and node.args:
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"),
                                                                     None)
                if isinstance(mode, pyast.Constant) and isinstance(mode.value, str) and set(mode.value) & set("wax+"):
                    dests.append(node.args[0])
            for d in dests:
                if any(MODS_RE.search(c) or c.lower() == "mods" or FACTORIO_MODS_RE.search(c) for c in _folds(d, env)):
                    out.append(f"{path}:{node.lineno}: copies or writes into a mods folder")
                    break
    return sorted(set(out))


def _tokens(line):
    return [t for t in re.split(r"[\s\"'`,;()|]+", line) if t]


# Whole-line comments by file type; a line in any other file is scanned whatever it starts with.
LINE_COMMENTS = {".lua": ("--",), ".bat": ("rem ", "REM ", "@rem ", "::"), ".cmd": ("rem ", "REM ", "@rem ", "::"),
                 ".js": ("//",), ".mjs": ("//",), ".cjs": ("//",), ".ts": ("//",)}
HASH_COMMENT_SUFFIXES = {".sh", ".bash", ".zsh", ".ps1", ".psm1", ".yml", ".yaml", ".toml", ".ini", ".txt", ".cfg", ""}


def line_launch_findings(path, text, gui, forbidden, allow_exe, allow_live=False):
    out = []
    long_flags = {f for f in gui | forbidden if f.startswith("--")}
    short_flags = {f for f in gui | forbidden if not f.startswith("--")}
    suffix = Path(path).suffix.lower()
    comments = LINE_COMMENTS.get(suffix, ("#",) if suffix in HASH_COMMENT_SUFFIXES else ())
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        if not line or (comments and line.startswith(comments)):
            continue
        toks = _tokens(line)
        low = line.lower()
        bound = "fh.py" in low or "factorio" in low
        for t in toks:
            tt = t.split("=", 1)[0]
            if tt in long_flags or (bound and tt in short_flags):
                out.append(f"{path}:{i}: token {t!r} is a flag fh.py refuses")
        if "mapshot" in low and "render" in [t.lower() for t in toks]:
            out.append(f"{path}:{i}: mapshot render")
        if live_word(line) and not allow_live:
            out.append(f"{path}:{i}: live-profile path ({live_word(line)})")
        if FACTORIO_MODS_RE.search(line):
            out.append(f"{path}:{i}: a Factorio mods folder path")
        if GAME_IMAGE in low:
            launching = re.search(r"(start-process|invoke-expression|invoke-item|^&|\s&\s|cmd(\.exe)?\s+/c|^\.\\|"
                                  r"^start\s)", low)
            if not allow_exe or launching:
                out.append(f"{path}:{i}: names or launches the game image")
        for k, t in enumerate(toks[:-1]):
            if t in OUT_FLAGS and (MODS_RE.search(toks[k + 1]) or live_word(toks[k + 1])):
                out.append(f"{path}:{i}: {t} points into a mods folder or the live profile")
        segs = re.split(r"[|;]|&&", line)
        for seg in segs:
            st = _tokens(seg)
            if st and st[0].lower() in COPY_CMDS and any(MODS_RE.search(t) for t in st[1:]):
                out.append(f"{path}:{i}: copies into a mods folder")
            if st and _last_component(st[0].lstrip("&").strip()) in ("factorio", GAME_IMAGE):
                out.append(f"{path}:{i}: runs the game binary directly")
    return sorted(set(out))


# Files the launch scan reads as data rather than code: the vendored flag sets it matches against.
LAUNCH_DATA = {"tools/lint/fh-flags.json"}
EXEC_SUFFIXES = {".exe", ".com", ".scr", ".msi", ".dll"}
ROOT_SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh", ".ps1", ".psm1", ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".bat",
                        ".cmd", ".vbs"}


def launch_findings(roots, lint_dir=LINT, base=REPO, files=()):
    """The launch scan over every file of the given trees (dot and build folders included, .git and
    __pycache__ aside) plus extra files: Python through its AST, every other text file line by line,
    and a binary executable (which no scan can read) is a finding of its own."""
    gui, forbidden = fh_flags(lint_dir)
    allow_exe = {"tools/perf.py", "tools/affinity_watch.ps1"}
    allow_live = {"tools/tnguard.py"}
    out, n = [], 0
    paths = [p for root in roots for p in walk_all(root)] + [Path(f) for f in files]
    for p in paths:
        r = rel(p, base)
        if r in LAUNCH_DATA:
            continue
        if p.suffix.lower() in EXEC_SUFFIXES:
            out.append(f"{r}: a binary executable in a scanned tree (the scan cannot read it)")
            continue
        text = read_text_or_none(p)
        if text is None:
            continue
        n += 1
        is_py = p.suffix.lower() in (".py", ".pyw") or text.startswith("#!") and "python" in text.split("\n", 1)[0]
        fn = py_launch_findings if is_py else line_launch_findings
        out += fn(r, text, gui, forbidden, r in allow_exe, r in allow_live)
    return out, n


def root_scripts(repo=REPO):
    """Script files at the repo root: by suffix, or by a #! line."""
    out = []
    for p in sorted(Path(repo).iterdir()):
        if not p.is_file():
            continue
        head = (read_text_or_none(p) or "")[:2]
        if p.suffix.lower() in ROOT_SCRIPT_SUFFIXES or head == "#!":
            out.append(p)
    return out


def argparse_dests(tree):
    """(dest, line) of every add_argument call of a Python file: its dest= keyword, else its first
    long option (dashes to underscores), else its first short option, else its positional name;
    (None, line) when the option names are not literal strings (the row fails closed on it)."""
    out = []
    for node in pyast.walk(tree):
        if not (isinstance(node, pyast.Call) and isinstance(node.func, pyast.Attribute) and
                node.func.attr == "add_argument"):
            continue
        dest = next((kw.value.value for kw in node.keywords if kw.arg == "dest" and
                     isinstance(kw.value, pyast.Constant) and isinstance(kw.value.value, str)), None)
        if dest is None and any(kw.arg == "dest" for kw in node.keywords):
            out.append((None, node.lineno))
            continue
        if dest is None:
            if any(not (isinstance(a, pyast.Constant) and isinstance(a.value, str)) for a in node.args) or not node.args:
                out.append((None, node.lineno))
                continue
            opts = [a.value for a in node.args]
            longs = [o for o in opts if o.startswith("--")]
            shorts = [o for o in opts if o.startswith("-") and not o.startswith("--")]
            dest = longs[0][2:] if longs else (shorts[0][1:] if shorts else opts[0])
        out.append((dest.replace("-", "_"), node.lineno))
    return out


def _calls_refuse(tree):
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Call):
            f = node.func
            if (isinstance(f, pyast.Attribute) and f.attr == "refuse_live_outputs") or \
                    (isinstance(f, pyast.Name) and f.id == "refuse_live_outputs"):
                return True
    return False


def output_args_findings(tools_dir=HERE, base=REPO):
    """Design constraint 1 for every tool's options: each argparse dest of each Python file under
    tools/ is declared in exactly one of tnguard's OUTPUT_ARGS (written), READ_ARGS (read only) and
    VALUE_ARGS (never a path), so a new option that writes cannot slip past the live-profile
    refusal unnoticed; and every file with an output dest calls tnguard.refuse_live_outputs."""
    out = []
    sets = {"output": tnguard.OUTPUT_ARGS, "read": tnguard.READ_ARGS, "value": tnguard.VALUE_ARGS}
    for a, b in (("output", "read"), ("output", "value"), ("read", "value")):
        both = sets[a] & sets[b]
        if both:
            out.append(f"tnguard declares {sorted(both)} as both {a} and {b} options")
    n = 0
    for p in walk_files(tools_dir, {".py"}):
        try:
            tree = pyast.parse(Path(p).read_text(encoding="utf-8"))
        except SyntaxError as e:
            out.append(f"{rel(p, base)}: does not parse ({e})")
            continue
        has_output = False
        for dest, line in argparse_dests(tree):
            n += 1
            if dest is None:
                out.append(f"{rel(p, base)}:{line}: add_argument with option names the scan cannot read")
                continue
            kinds = [k for k, s in sets.items() if dest in s]
            if not kinds:
                out.append(f"{rel(p, base)}:{line}: option dest {dest!r} is declared in none of tnguard's OUTPUT_ARGS, "
                           f"READ_ARGS or VALUE_ARGS (a written path must be in OUTPUT_ARGS)")
            has_output = has_output or "output" in kinds
        if has_output and not _calls_refuse(tree):
            out.append(f"{rel(p, base)}: declares an output option but never calls tnguard.refuse_live_outputs")
    return out, n


def row_output_args(repo=REPO):
    f, n = output_args_findings(Path(repo) / "tools", repo)
    return f, (f"{n} argparse options under tools/ each declared written, read or value in tnguard; every tool "
               f"with a written option refuses the live profile")


def row_launch(repo=REPO):
    roots = [Path(repo) / d for d in ("tools", "tests", ".github")]
    extra = root_scripts(repo)
    f, n = launch_findings([r for r in roots if r.exists()], LINT, repo, extra)
    return f, f"{n} text files in tools/, tests/ and .github/ and {len(extra)} root scripts"


class YamlError(ValueError):
    pass


def _strip_comment(s):
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(s):
    s = s.strip()
    if s == "" or s == "~" or s == "null":
        return None
    if (s[0] == s[-1] == '"' or s[0] == s[-1] == "'") and len(s) >= 2:
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") or s.startswith("&") or s.startswith("*") or s.startswith("!"):
        raise YamlError(f"unsupported YAML construct {s!r}")
    return s


def parse_yaml(text):
    """The YAML subset the workflows use: mappings, lists of mappings or scalars, block scalars."""
    lines = []
    for raw in text.split("\n"):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YamlError("tab indentation")
        lines.append(raw.rstrip("\r"))
    pos = [0]

    def nxt():
        while pos[0] < len(lines):
            s = _strip_comment(lines[pos[0]])
            if s.strip():
                return pos[0], len(s) - len(s.lstrip()), s.strip()
            pos[0] += 1
        return None

    def block_scalar(indent):
        out = []
        while pos[0] < len(lines):
            raw = lines[pos[0]]
            if raw.strip() and len(raw) - len(raw.lstrip()) <= indent:
                break
            out.append(raw)
            pos[0] += 1
        body = [l for l in out]
        ind = min((len(l) - len(l.lstrip()) for l in body if l.strip()), default=0)
        return "\n".join(l[ind:] for l in body).strip("\n") + "\n"

    def parse_node(indent):
        t = nxt()
        if t is None:
            return None
        _, ind, s = t
        if ind < indent:
            return None
        if s.startswith("- ") or s == "-":
            return parse_list(ind)
        return parse_map(ind)

    def parse_value(rest, ind):
        if rest in ("|", "|-", ">", ">-"):
            return block_scalar(ind)
        if rest == "":
            t = nxt()
            if t is None or t[1] <= ind:
                return None
            return parse_node(t[1])
        return _scalar(rest)

    def parse_map(indent, first=None):
        out = {}
        while True:
            if first is not None:
                s, first = first, None
            else:
                t = nxt()
                if t is None:
                    break
                _, ind, s = t
                if ind != indent or s.startswith("- "):
                    if ind > indent:
                        raise YamlError(f"line {pos[0] + 1}: unexpected indentation")
                    break
                pos[0] += 1
            m = re.match(r"^((?:\"[^\"]*\"|'[^']*'|[^:\s][^:]*?)):(?:\s+(.*))?$", s)
            if not m:
                raise YamlError(f"line {pos[0]}: cannot read {s!r}")
            key = _scalar(m.group(1))
            if key in out:
                raise YamlError(f"duplicate key {key!r}")
            out[key] = parse_value((m.group(2) or "").strip(), indent)
        return out

    def parse_list(indent):
        out = []
        while True:
            t = nxt()
            if t is None:
                break
            _, ind, s = t
            if ind != indent or not (s.startswith("- ") or s == "-"):
                if ind > indent:
                    raise YamlError(f"line {pos[0] + 1}: unexpected indentation")
                break
            pos[0] += 1
            rest = s[1:].strip()
            if rest == "":
                out.append(parse_node(indent + 1))
            elif re.match(r"^((?:\"[^\"]*\"|'[^']*'|[^:\s\"'][^:]*?)):(\s+.*)?$", rest) and not rest.startswith(("\"", "'")):
                out.append(parse_map(ind + 2, first=rest))
            else:
                out.append(_scalar(rest))
        return out

    node = parse_node(0)
    if nxt() is not None:
        raise YamlError(f"line {pos[0] + 1}: trailing content")
    return node if node is not None else {}


# ------------------------------------------------------------------------------------------------ workflow scan

SHA_RE = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
# The workflows are a closed world: these keys only, one job, and exactly the expected steps in
# order, each run block exactly its commands. Anything else can stop a check from failing the run
# (continue-on-error, if, a trigger filter, an extra step writing $GITHUB_ENV, a shell, a working
# directory or an environment that runs another program, a checkout of another repository).
WORKFLOW_KEYS = {"name", "on", "permissions", "jobs"}
JOB_KEYS = {"runs-on", "steps"}
STEP_KEYS = {"name", "uses", "with", "run", "env"}
PIP_LINE = "python -m pip install --disable-pip-version-check -r tools/lint/requirements.txt"
LINT_LINE = 'python tools/lint/fetch_linter.py --dest "$env:RUNNER_TEMP\\luacheck" --github-env "$env:GITHUB_ENV"'
TAG_ENV = "${{ github.ref_name }}"
TOKEN_ENV = "${{ secrets.GITHUB_TOKEN }}"
PUBLISH_FILES = ('$files = @(Get-ChildItem -Path dist -File | Where-Object { $_.Name -like "*.zip" -or $_.Name -like '
                 '"*.zip.sha256" } | ForEach-Object { $_.FullName })')
PUBLISH_COUNT = 'if ($files.Count -ne 2) { throw "expected the zip and its .sha256 in dist, found $($files.Count) files" }'


def _expected_steps(kind, manifest):
    """The one step sequence each workflow may hold."""
    common = [
        {"label": "the checkout", "uses": "actions/checkout@"},
        {"label": "the Python setup", "uses": "actions/setup-python@",
         "with": {"python-version": manifest["luaparser"]["python"]}},
        {"label": "the luaparser and linter install", "run": [PIP_LINE, LINT_LINE]},
    ]
    if kind == "ci":
        return common + [
            {"label": "the static checks", "run": ["python tools/earth_test.py static"]},
            {"label": "the zip build", "run": ["python tools/build_zip.py"]},
            {"label": "the artifact upload", "uses": "actions/upload-artifact@", "with": "upload"},
        ]
    return common + [
        {"label": "the tag check", "run": ['python tools/build_zip.py --check-tag "$env:TAG"'], "env": {"TAG": TAG_ENV}},
        {"label": "the release build", "run": ["python tools/build_zip.py --release"]},
        {"label": "the publish step", "run": "publish", "env": {"TAG": TAG_ENV, "GH_TOKEN": TOKEN_ENV}},
    ]


def _run_lines(step):
    r = step.get("run")
    return [l.strip() for l in r.split("\n") if l.strip()] if isinstance(r, str) else None


def publish_problems(name, lines):
    """The publish block: the file list of exactly the zip and its .sha256, the count check, and one
    gh release create whose arguments attach exactly that list (only --title, --notes and
    --verify-tag besides: no --draft, --prerelease, --target or other repository)."""
    import shlex
    if lines is None or len(lines) != 3:
        return [f"{name}: the publish step must be exactly three lines (the file list, its count check, gh release "
                f"create), found {lines}"]
    fails = []
    if lines[0] != PUBLISH_FILES:
        fails.append(f"{name}: the publish step's file list must be exactly the zip and its .sha256 from dist "
                     f"({PUBLISH_FILES})")
    if lines[1] != PUBLISH_COUNT:
        fails.append(f"{name}: the publish step must throw unless it found exactly those two files ({PUBLISH_COUNT})")
    try:
        tok = shlex.split(lines[2])
    except ValueError as e:
        return fails + [f"{name}: the gh release create line does not parse ({e})"]
    if tok[:4] != ["gh", "release", "create", "$env:TAG"]:
        fails.append(f'{name}: the publish command must be gh release create "$env:TAG" (found {tok[:4]})')
    files, flags, i = [], {}, 4
    while i < len(tok):
        t = tok[i]
        if t in ("--title", "--notes") and i + 1 < len(tok):
            flags[t] = tok[i + 1]
            i += 2
        elif t == "--verify-tag":
            flags[t] = True
            i += 1
        elif t.startswith("-"):
            fails.append(f"{name}: gh release create passes {t}; only --title, --notes and --verify-tag are allowed")
            i += 1
        else:
            files.append(t)
            i += 1
    if files != ["@files"]:
        fails.append(f"{name}: gh release create must attach exactly @files (the zip and its .sha256), not {files}")
    if flags.get("--title") != "$env:TAG" or not flags.get("--notes") or "--verify-tag" not in flags:
        fails.append(f'{name}: gh release create needs --title "$env:TAG", --notes and --verify-tag')
    return fails


def structure_problems(name, kind, wf, manifest):
    """The closed-world shape of a workflow: its keys, one job with its keys, and exactly the
    expected steps, each with only its own keys, `with`, `env` and exact run lines."""
    fails = []
    extra = sorted(set(wf) - WORKFLOW_KEYS)
    if extra:
        fails.append(f"{name}: workflow keys {extra} are not allowed (only {sorted(WORKFLOW_KEYS)})")
    jobs = wf.get("jobs") or {}
    if len(jobs) != 1:
        fails.append(f"{name}: must hold exactly one job, found {sorted(jobs)}")
    want = _expected_steps(kind, manifest)
    for jn, job in jobs.items():
        job = job or {}
        bad = sorted(set(job) - JOB_KEYS)
        if bad:
            fails.append(f"{name}: job {jn} sets {bad}; a job holds only runs-on and steps (continue-on-error, if, "
                         f"env, defaults and the like can keep a failed check from failing the run)")
        steps = job.get("steps") or []
        if len(steps) != len(want) or not all(isinstance(s, dict) for s in steps):
            fails.append(f"{name}: job {jn} must hold exactly {len(want)} steps ({', '.join(w['label'] for w in want)}), "
                         f"found {len(steps)}")
        for i, (s, w) in enumerate(zip(steps, want)):
            if not isinstance(s, dict):
                continue
            where = f"{name}: step {i + 1} ({w['label']})"
            bad = sorted(set(s) - STEP_KEYS)
            if bad:
                fails.append(f"{where} sets {bad}; a step holds only {sorted(STEP_KEYS)} (no continue-on-error, if, "
                             f"shell, working-directory)")
            if "uses" in w:
                if not str(s.get("uses", "")).startswith(w["uses"]) or "run" in s:
                    fails.append(f"{where} must be the action {w['uses']}<sha> and nothing else")
            elif "uses" in s:
                fails.append(f"{where} must run its commands, not the action {s.get('uses')}")
            spec_with = w.get("with")
            got_with = s.get("with")
            if spec_with == "upload":
                if not isinstance(got_with, dict) or set(got_with) != {"name", "path", "if-no-files-found"} or \
                        got_with.get("path") != "dist/*.zip" or got_with.get("if-no-files-found") != "error":
                    fails.append(f"{where} must upload dist/*.zip with if-no-files-found: error and nothing else "
                                 f"(found {got_with})")
            elif got_with != spec_with:
                fails.append(f"{where} must carry with {spec_with}, found {got_with}")
            if (s.get("env") or None) != w.get("env"):
                fails.append(f"{where} must carry env {w.get('env')}, found {s.get('env')}")
            lines = _run_lines(s)
            if w.get("run") == "publish":
                fails += publish_problems(name, lines)
            elif "run" in w and lines != w["run"]:
                fails.append(f"{where} must run exactly {w['run']}, found {lines}")
    return fails


def _steps(wf):
    out = []
    for job in (wf.get("jobs") or {}).values():
        out += [s for s in (job or {}).get("steps") or [] if isinstance(s, dict)]
    return out


def _runs(steps):
    out = []
    for s in steps:
        r = s.get("run")
        if isinstance(r, str):
            out += [l.strip() for l in r.split("\n") if l.strip()]
    return out


def _common_workflow(name, wf, text, manifest):
    fails = []
    jobs = wf.get("jobs") or {}
    if not jobs:
        fails.append(f"{name}: no jobs")
    for jn, job in jobs.items():
        if (job or {}).get("runs-on") != "windows-latest":
            fails.append(f"{name}: job {jn} does not run on windows-latest")
        if "permissions" in (job or {}):
            fails.append(f"{name}: job {jn} sets its own permissions")
    steps = _steps(wf)
    for s in steps:
        u = s.get("uses")
        if u is not None and not SHA_RE.match(str(u)):
            fails.append(f"{name}: action {u!r} is not pinned to a full commit SHA")
    py = [s for s in steps if str(s.get("uses", "")).startswith("actions/setup-python@")]
    want_py = manifest["luaparser"]["python"]
    if len(py) != 1 or str((py[0].get("with") or {}).get("python-version")) != want_py:
        fails.append(f"{name}: needs one actions/setup-python step with python-version {want_py!r}")
    runs = _runs(steps)
    if "python -m pip install --disable-pip-version-check -r tools/lint/requirements.txt" not in runs:
        fails.append(f"{name}: does not install luaparser from tools/lint/requirements.txt")
    if not any(r.startswith("python tools/lint/fetch_linter.py ") for r in runs):
        fails.append(f"{name}: does not install the linter with tools/lint/fetch_linter.py (sha256-checked)")
    low = text.lower()
    for bad in ("fh.py", "factorio_ws", GAME_IMAGE, "--start" + "-server", "steam", APPDATA_WORD):
        if bad in low:
            fails.append(f"{name}: mentions {bad!r} (the workflows never run the game or read the workspace)")
    secrets = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text))
    if secrets - {"GITHUB_TOKEN"}:
        fails.append(f"{name}: reads secrets {sorted(secrets - {'GITHUB_TOKEN'})} (only the workflow's own GITHUB_TOKEN)")
    allowed_runs = {"python -m pip install --disable-pip-version-check -r tools/lint/requirements.txt"}
    for r in runs:
        if r.startswith("python ") and r not in allowed_runs and not r.startswith(
                ("python tools/lint/fetch_linter.py ", "python tools/earth_test.py static", "python tools/build_zip.py")):
            fails.append(f"{name}: unexpected python step {r!r}")
    return fails, steps, runs, secrets


def check_ci(text, manifest):
    try:
        wf = parse_yaml(text)
    except YamlError as e:
        return [f"ci.yml: {e}"]
    fails, steps, runs, secrets = _common_workflow("ci.yml", wf, text, manifest)
    fails += structure_problems("ci.yml", "ci", wf, manifest)
    on = wf.get("on")
    if not isinstance(on, dict) or set(on) != {"push", "pull_request"}:
        fails.append("ci.yml: must trigger on push and pull_request only")
    elif on.get("push") is not None or on.get("pull_request") is not None:
        fails.append(f"ci.yml: push and pull_request must carry no filter (branches, paths, tags, types), so CI runs "
                     f"on every push and pull request (found {on})")
    if wf.get("permissions") != {"contents": "read"}:
        fails.append("ci.yml: permissions must be exactly contents: read")
    if secrets:
        fails.append("ci.yml: reads a secret; CI needs none")
    for want in ("python tools/earth_test.py static", "python tools/build_zip.py"):
        if want not in runs:
            fails.append(f"ci.yml: lacks the check step {want!r}")
    up = [s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
    if len(up) != 1 or not str((up[0].get("with") or {}).get("path", "")).startswith("dist/") or \
            not str((up[0].get("with") or {}).get("path", "")).endswith(".zip"):
        fails.append("ci.yml: must upload the zip from dist/ as an artifact")
    if any(r.startswith("python tools/build_zip.py --release") for r in runs):
        fails.append("ci.yml: builds a release zip")
    if any(r.startswith("gh ") for r in runs):
        fails.append("ci.yml: calls gh")
    return fails


def check_release(text, manifest):
    try:
        wf = parse_yaml(text)
    except YamlError as e:
        return [f"release.yml: {e}"]
    fails, steps, runs, secrets = _common_workflow("release.yml", wf, text, manifest)
    fails += structure_problems("release.yml", "release", wf, manifest)
    on = wf.get("on")
    if not (isinstance(on, dict) and set(on) == {"push"} and isinstance(on["push"], dict)
            and set(on["push"]) == {"tags"} and on["push"]["tags"] == ["v*"]):
        fails.append("release.yml: must trigger only on a pushed tag v*")
    if wf.get("permissions") != {"contents": "write"}:
        fails.append("release.yml: permissions must be exactly contents: write")
    order = []
    for s in steps:
        r = s.get("run") or ""
        env = s.get("env") or {}
        if 'python tools/build_zip.py --check-tag "$env:TAG"' in r:
            if env.get("TAG") != "${{ github.ref_name }}":
                fails.append("release.yml: the tag check must read TAG from github.ref_name")
            order.append("tag")
        if r.strip() == "python tools/build_zip.py --release":
            order.append("build")
        if "gh release create" in r:
            if env.get("GH_TOKEN") != "${{ secrets.GITHUB_TOKEN }}":
                fails.append("release.yml: gh must use the workflow's own GITHUB_TOKEN")
            if "*.zip" not in r or "*.zip.sha256" not in r:
                fails.append("release.yml: the release must attach the zip and its .sha256")
            order.append("publish")
    if order != ["tag", "build", "publish"]:
        fails.append(f"release.yml: steps must be the tag check, build_zip.py --release, then gh release create "
                     f"(found {order})")
    return fails


def workflow_findings(gh_dir=REPO / ".github" / "workflows", lint_dir=LINT):
    manifest = lint_manifest(lint_dir)
    out = []
    for name, fn in (("ci.yml", check_ci), ("release.yml", check_release)):
        p = Path(gh_dir) / name
        if not p.exists():
            out.append(f"{name} is missing")
            continue
        out += fn(p.read_text(encoding="utf-8"), manifest)
    req = (Path(lint_dir) / "requirements.txt").read_text(encoding="utf-8")
    if f"luaparser=={manifest['luaparser']['version']}" not in req.split():
        out.append("tools/lint/requirements.txt does not pin luaparser to the manifest's version")
    return out


def row_workflow(repo=REPO):
    f = workflow_findings(Path(repo) / ".github" / "workflows", LINT)
    return f, "ci.yml and release.yml against DECISIONS 12:35"


# ------------------------------------------------------------------------------------------------ attribution scan

def attribution_patterns():
    """Assembled from fragments at run time: no committed file holds a literal pattern (U14)."""
    j = "".join
    words = [j(["cl", "aude"]), j(["anthr", "opic"]), j(["open", "ai"]), j(["chat", "gpt"]), j(["co", "pilot"]),
             j(["gem", "ini"]), j(["g", "pt-", "4"]), j(["l", "lm-gen", "erated"])]
    phrases = [j(["co", "-auth", "ored", "-by"]), j(["gene", "rated ", "with "]), j(["gene", "rated ", "by ", "ai"]),
               j(["ai", "-gene", "rated"]), j(["writ", "ten ", "by ", "ai"]), j(["no", "reply", "@", "anthr", "opic"])]
    # A word inside a path (a tool's dot folder, a URL) is not attribution; a word in prose is.
    rx = [re.compile(r"(?<![a-z0-9./\\])" + re.escape(w) + r"(?![a-z0-9])", re.I) for w in words]
    rx += [re.compile(re.escape(p), re.I) for p in phrases]
    return rx


def attribution_findings(roots, base=REPO):
    rx = attribution_patterns()
    out, n = [], 0
    for root in roots:
        for p in walk_all(root):
            if p.suffix.lower() in {".png", ".zip", ".dat", ".npz", ".npy", ".exe"}:
                continue
            text = read_text_or_none(p)
            if text is None:
                continue
            n += 1
            for i, line in enumerate(text.split("\n"), 1):
                for r in rx:
                    if r.search(line):
                        out.append(f"{rel(p, base)}:{i}: AI attribution pattern")
                        break
    return out, n


def row_attribution(repo=REPO):
    roots = [Path(repo) / d for d in ("terra-nauvis", "tools", "tests", "data-src", ".github")]
    f, n = attribution_findings([r for r in roots if r.exists()], repo)
    return f, f"{n} text files in terra-nauvis/, tools/, tests/, data-src/ and .github/"


# ------------------------------------------------------------------------------------------------ data-src

def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"{p} is not a PNG")
    return struct.unpack(">II", head[16:24])


def provenance_hashes(md_path):
    """{file: sha256} from the provenance table rows '| `file` | `sha256` | ...'."""
    out = {}
    for line in Path(md_path).read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def data_src_findings(repo=REPO):
    repo = Path(repo)
    out = []
    cfg = tnconfig.load(repo / "terra-nauvis" / "prototypes" / "config.lua")
    em = repo / "data-src" / "earthmaps"
    prov = provenance_hashes(em / "PROVENANCE.md")
    files = sorted(p.name for p in em.iterdir() if p.is_file() and p.name != "PROVENANCE.md")
    for name in files:
        if name not in prov:
            out.append(f"data-src/earthmaps/{name} is not in PROVENANCE.md")
        elif sha256_file(em / name) != prov[name]:
            out.append(f"data-src/earthmaps/{name} sha256 differs from PROVENANCE.md")
    for name in prov:
        if name not in files:
            out.append(f"PROVENANCE.md lists data-src/earthmaps/{name}, which is missing")
    for key in cfg["map_order"]:
        jp = em / f"{key}.json"
        if not jp.exists():
            out.append(f"data-src/earthmaps/{key}.json is missing")
            continue
        J = load_json(jp)
        for kind, rec in J["png"].items():
            pp = em / rec["file"]
            if not pp.exists():
                out.append(f"{rec['file']} is missing")
                continue
            if sha256_file(pp) != rec["sha256"]:
                out.append(f"{rec['file']} sha256 differs from {key}.json png.{kind}")
            if png_size(pp) != (J["width_px"], J["height_px"]):
                out.append(f"{rec['file']} is {png_size(pp)}, {key}.json says {J['width_px']} x {J['height_px']}")
        m = cfg["maps"][key]
        g = J["georeference"]
        radii = J["earthmaps_radii"]
        pairs = (("width_px", J["width_px"]), ("height_px", J["height_px"]),
                 ("wr", radii["decompressed_width_radius"]), ("hr", radii["decompressed_height_radius"]),
                 ("lon_left_edge", g["lon_left_edge"]), ("lat_top_edge", g["lat_top_edge"]))
        for field, want in pairs:
            if m.get(field) != want:
                out.append(f"config.lua maps.{key}.{field} is {m.get(field)!r}, {key}.json says {want!r}")
        if cfg["coordinates"]["px_per_degree"] != g["px_per_degree"]:
            out.append(f"config.lua px_per_degree differs from {key}.json")
    ap = repo / "data-src" / "approvals"
    aprov = provenance_hashes(ap / "PROVENANCE.md")
    for name in sorted(p.name for p in ap.iterdir() if p.is_file() and p.name != "PROVENANCE.md"):
        if aprov.get(name) != sha256_file(ap / name):
            out.append(f"data-src/approvals/{name} sha256 differs from its PROVENANCE.md")
    return out


def row_data_src(repo=REPO):
    f = data_src_findings(repo)
    return f, "provenance sha256, reference JSON png hashes and sizes, config.lua against the reference JSON"


# ------------------------------------------------------------------------------------------------ frozen, budgets

THRESHOLD_KEY_RE = re.compile(r"(limit|cap|threshold|allocation|allowance|ceiling|bar)$", re.I)


def config_frozen_findings(cfg, fz):
    """config.lua against tests/frozen.json (design constraint 2), statically: every Earth noise body
    config.lua defines, released or a firewall body, is registered, the placeholder's names and the
    Map type fallbacks excepted and never registered; every entry is well formed. The gate's frozen
    row checks the dumped bodies and their hashes; this row needs no game, so CI runs it too."""
    out = []
    ph = set(tnconfig.placeholder_names(cfg))
    fb = set(tnconfig.fallback_names(cfg))
    bodies = fz.get("bodies") or {}
    for name, rec in bodies.items():
        if name in ph:
            out.append(f"placeholder name {name} is registered in tests/frozen.json")
        if name in fb:
            out.append(f"Map type fallback {name} is registered in tests/frozen.json (U3: fallbacks never are)")
        if not re.fullmatch(r"[0-9a-f]{64}", str(rec.get("sha256", ""))):
            out.append(f"tests/frozen.json {name}: sha256 is not 64 hex")
        if rec.get("type") not in ("noise-expression", "noise-function"):
            out.append(f"tests/frozen.json {name}: type {rec.get('type')!r}")
    for name in tnconfig.unregistered_names(cfg, bodies):
        out.append(f"config.lua defines the Earth body {name}, which tests/frozen.json does not register: run python "
                   f"tools/earth_test.py freeze (sacred constraint 2)")
    return out


def frozen_static_findings(repo=REPO):
    repo = Path(repo)
    out = []
    cfg = tnconfig.load(repo / "terra-nauvis" / "prototypes" / "config.lua")
    fz = load_json(repo / "tests" / "frozen.json")
    if fz.get("format") != "tn-frozen/1" or not isinstance(fz.get("bodies"), dict):
        out.append("tests/frozen.json is not tn-frozen/1 with a bodies table")
        return out
    out += config_frozen_findings(cfg, fz)
    bud = load_json(repo / "tests" / "budgets.json")

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if THRESHOLD_KEY_RE.search(str(k)):
                    out.append(f"tests/budgets.json holds a threshold-like key {path}{k} (measured values only)")
                walk(v, f"{path}{k}.")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}{i}.")
    walk(bud, "")
    return out


def row_frozen(repo=REPO):
    f = frozen_static_findings(repo)
    fz = load_json(Path(repo) / "tests" / "frozen.json")
    return f, f"{len(fz.get('bodies', {}))} registered bodies; budgets.json holds measured values only"


# ------------------------------------------------------------------------------------------------ zip

def zip_findings(repo=REPO):
    import zipfile
    with tempfile.TemporaryDirectory(prefix="tn-zip-") as td:
        return _zip_findings(repo, Path(td), zipfile)


def _zip_findings(repo, tmp, zipfile):
    out = []
    a = build_zip.build(tmp / "a", mod_dir=Path(repo) / "terra-nauvis")
    b = build_zip.build(tmp / "b", mod_dir=Path(repo) / "terra-nauvis")
    if a[1] != b[1]:
        out.append(f"two consecutive builds differ: {a[1]} and {b[1]}")
    cfg = tnconfig.load(Path(repo) / "terra-nauvis" / "prototypes" / "config.lua")
    want_name = f"{cfg['identity']['id']}_{cfg['identity']['version']}.zip"
    if a[0].name != want_name:
        out.append(f"zip is named {a[0].name}, want {want_name}")
    with zipfile.ZipFile(a[0]) as zf:
        names = zf.namelist()
        bad = zf.testzip()
    tops = {n.split("/", 1)[0] for n in names}
    top = cfg["identity"]["id"]
    if tops != {top}:
        out.append(f"zip top folders {sorted(tops)}, want one: {top}")
    for need in ("LICENSE", "SOURCE-OFFER.txt", "info.json"):
        if f"{top}/{need}" not in names:
            out.append(f"zip lacks {top}/{need}")
    if bad:
        out.append(f"zip entry {bad} fails its CRC")
    lic = (Path(repo) / "terra-nauvis" / "LICENSE").read_text(encoding="utf-8")
    if "GNU GENERAL PUBLIC LICENSE" not in lic or "Version 3, 29 June 2007" not in lic:
        out.append("terra-nauvis/LICENSE is not the GPLv3 text")
    gi = (Path(repo) / ".gitignore").read_text(encoding="utf-8").split()
    if "dist/" not in gi:
        out.append(".gitignore does not ignore dist/")
    return out, a


def row_zip(repo=REPO):
    f, a = zip_findings(repo)
    return f, f"{a[0].name} sha256 {a[1][:16]} twice, {len(a[2]['entries'])} files"


# ------------------------------------------------------------------------------------------------ fixture controls

def _write(root, relpath, text):
    p = Path(root) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def fixture_controls():
    """Positive controls: every scan rule must fail a fixture that breaks it. Fixtures live in a fresh
    temporary directory outside the scanned trees and are never committed."""
    results = []
    gui, forbidden = fh_flags()
    exe = "factorio" + ".exe"
    app = "%" + "APP" + "DATA" + "%"
    gflag = sorted(f for f in gui if f.startswith("--"))[0]
    with tempfile.TemporaryDirectory(prefix="tn-fixtures-") as td:
        td = Path(td)
        cases = {
            "launch: the game image launched directly":
                ("tools/a.py", f"import subprocess\nsubprocess.run([r'C:\\game\\bin\\x64\\{exe}', '--create', 'x.zip'])\n"),
            "launch: a flag fh.py refuses":
                ("tools/b.py", f"FH = 'tools/fh.py'\ncmd = [FH, 'run', '--', '{gflag}', 'save.zip']\n"),
            "launch: mapshot render":
                ("tools/c.ps1", "& python tools/fh.py run -- mapshot render\n"),
            "launch: a live-profile path":
                ("tools/d.py", f"import os\nLIVE = r'{app}\\Factorio'\n"),
            "launch: copy into a mods folder":
                ("tools/e.ps1", "Copy-Item dist\\x.zip \"$HOME\\Fact" + "orio\\mods\\\"\n"),
            "launch: short flag bound for fh.py":
                ("tools/f.py", "FH = 'tools/fh.py'\nargs = [FH, 'run', '--', '-c', 'other.ini']\n"),
        }
        for label, (path, text) in cases.items():
            d = td / label.split(":")[0] / str(abs(hash(label)) % 10 ** 8)
            _write(d, path, text)
            f, _ = launch_findings([d], LINT, d)
            results.append((label, bool(f), f[:2]))
        clean = td / "clean-launch"
        _write(clean, "tools/ok.py", "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pip', 'list'])\n"
                                     "subprocess.run(['git', '-c', 'core.quotepath=off', 'status'])\n")
        f, _ = launch_findings([clean], LINT, clean)
        results.append(("launch: python -m and git -c stay clean", not f, f[:2]))
        # attribution
        word = "".join(["Cl", "aude"])
        d = td / "attr"
        _write(d, "tests/note.txt", f"Written with help from {word}.\n")
        f, _ = attribution_findings([d], d)
        results.append(("attribution: a pattern in a file", bool(f), f[:1]))
        trailer = "-".join(["Co", "Authored", "By"]) + ": x <y@z>"
        d2 = td / "attr2"
        _write(d2, "tools/x.py", f"# {trailer}\n")
        f, _ = attribution_findings([d2], d2)
        results.append(("attribution: a co-author trailer", bool(f), f[:1]))
        # workflow mutations
        manifest = lint_manifest()
        wf_dir = REPO / ".github" / "workflows"
        ci = (wf_dir / "ci.yml").read_text(encoding="utf-8")
        rel_wf = (wf_dir / "release.yml").read_text(encoding="utf-8")
        sha = re.search(r"actions/checkout@([0-9a-f]{40})", ci).group(1)
        muts = [
            ("workflow: ci without pull_request", "ci", ci.replace("  pull_request:\n", "")),
            ("workflow: ci without push", "ci", ci.replace("  push:\n", "")),
            ("workflow: ci with write permission", "ci", ci.replace("contents: read", "contents: write")),
            ("workflow: unpinned action", "ci", ci.replace(f"actions/checkout@{sha}", "actions/checkout@v7")),
            ("workflow: ci not on windows-latest", "ci", ci.replace("windows-latest", "ubuntu-latest")),
            ("workflow: other python", "ci", ci.replace('"3.13.3"', '"3.12"')),
            ("workflow: ci without the static step", "ci", ci.replace("run: python tools/earth_test.py static",
                                                                       "run: python tools/earth_test.py --help")),
            ("workflow: ci without the artifact", "ci", re.sub(r"      - name: Upload the zip\n(        .*\n)+", "", ci)),
            ("workflow: ci reads a secret", "ci", ci.replace("run: python tools/build_zip.py\n",
                                                             "run: python tools/build_zip.py\n        env:\n"
                                                             "          X: ${{ secrets.DEPLOY_KEY }}\n")),
            ("workflow: ci calls fh.py", "ci", ci.replace("run: python tools/build_zip.py\n",
                                                          "run: python tools/build_zip.py\n      - run: python "
                                                          "../tools/fh.py preview\n")),
            ("workflow: ci reads FACTORIO_WS", "ci", ci.replace("run: python tools/earth_test.py static",
                                                                "run: python tools/earth_test.py static\n        env:\n"
                                                                "          FACTORIO_WS: C:/ws")),
            ("workflow: ci without the linter", "ci", re.sub(r"\n\s*python tools/lint/fetch_linter.py [^\n]*", "", ci)),
            ("workflow: release on a branch", "rel", rel_wf.replace('    tags:\n      - "v*"', '    branches:\n      - main')),
            ("workflow: release with read permission", "rel", rel_wf.replace("contents: write", "contents: read")),
            ("workflow: release without the tag check", "rel",
             re.sub(r"      - name: Check the tag against info.json\n(        .*\n)+", "", rel_wf)),
            ("workflow: release without --release", "rel", rel_wf.replace("run: python tools/build_zip.py --release",
                                                                          "run: python tools/build_zip.py")),
            ("workflow: release with another token", "rel", rel_wf.replace("${{ secrets.GITHUB_TOKEN }}",
                                                                           "${{ secrets.RELEASE_PAT }}")),
            ("workflow: release without the .sha256", "rel", rel_wf.replace('-or $_.Name -like "*.zip.sha256"', "")),
        ]
        pip = "          python -m pip install --disable-pip-version-check -r tools/lint/requirements.txt\n"
        lint = re.search(r"\n\s*python tools/lint/fetch_linter.py [^\n]*", ci).group(0)

        def add_step(text, run):
            return text.replace("      - name: Check out\n", f"      - run: {run}\n      - name: Check out\n", 1)

        def job_perm(text):
            return re.sub(r"(\n    runs-on: windows-latest\n)", "\n    permissions:\n      contents: write\\1", text, 1)
        server = "--start" + "-server"
        for kind, text in (("ci", ci), ("rel", rel_wf)):
            name = "ci" if kind == "ci" else "release"
            muts += [
                (f"workflow: {name} without the luaparser install", kind, text.replace(pip, "")),
                (f"workflow: {name} without the linter install", kind, text.replace(lint, "")),
                (f"workflow: {name} launches the game image", kind, add_step(text, f"C:/g/bin/x64/{exe} --version")),
                (f"workflow: {name} starts a server", kind, add_step(text, f"python x.py {server} s.zip")),
                (f"workflow: {name} mentions steam", kind, add_step(text, "echo " + "ste" + "am")),
                (f"workflow: {name} reads the live profile", kind, add_step(text, f"dir $env:{'APP' + 'DATA'}")),
                (f"workflow: {name} calls fh.py", kind, add_step(text, "python ../tools/fh.py preview")),
                (f"workflow: {name} reads FACTORIO_WS", kind, add_step(text, "echo $env:FACTORIO_WS")),
                (f"workflow: {name} overrides permissions in a job", kind, job_perm(text)),
            ]
        muts += [
            ("workflow: ci without the build_zip step", "ci", re.sub(r"      - name: Build the zip\n(        .*\n)+", "", ci)),
            ("workflow: ci builds a release zip", "ci", add_step(ci, "python tools/build_zip.py --release")),
            ("workflow: ci calls gh", "ci", add_step(ci, "gh release list")),
            ("workflow: ci with an extra trigger", "ci", ci.replace("  pull_request:\n", "  pull_request:\n  workflow_dispatch:\n")),
            ("workflow: release not on windows-latest", "rel", rel_wf.replace("windows-latest", "ubuntu-latest")),
            ("workflow: release on another python", "rel", rel_wf.replace('"3.13.3"', '"3.12"')),
            ("workflow: release with an unpinned action", "rel", rel_wf.replace(f"actions/checkout@{sha}", "actions/checkout@v7")),
            ("workflow: release with an extra trigger", "rel", rel_wf.replace("on:\n  push:\n", "on:\n  workflow_dispatch:\n  push:\n")),
        ]
        # every way a step or the job can stop failing, or be routed elsewhere, past its own run line
        static_run = "        run: python tools/earth_test.py static\n"
        build_run = "        run: python tools/build_zip.py\n"
        tag_run = '        run: python tools/build_zip.py --check-tag "$env:TAG"\n'
        release_run = "        run: python tools/build_zip.py --release\n"
        publish_run = "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"   # the publish step's last line before run

        def after(text, line, extra):
            return text.replace(line, line + extra, 1)
        for kind, text, line, what in (("ci", ci, static_run, "the static step"), ("ci", ci, build_run, "the build step"),
                                       ("rel", rel_wf, tag_run, "the tag check"),
                                       ("rel", rel_wf, release_run, "the release build"),
                                       ("rel", rel_wf, publish_run, "the publish step")):
            line = line if line in text else ""
            muts += [
                (f"workflow: continue-on-error on {what}", kind,
                 after(text, line, "        continue-on-error: true\n") if line else text),
                (f"workflow: if: false on {what}", kind, after(text, line, "        if: false\n") if line else text),
                (f"workflow: a shell override on {what}", kind, after(text, line, "        shell: bash\n") if line else text),
                (f"workflow: a working-directory on {what}", kind,
                 after(text, line, "        working-directory: spikes\n") if line else text),
            ]
            if kind == "ci" or what == "the release build":
                muts.append((f"workflow: an environment on {what}", kind,
                             after(text, line, "        env:\n          PYTHONPATH: x\n") if line else text))
        for kind, text in (("ci", ci), ("rel", rel_wf)):
            name = "ci" if kind == "ci" else "release"
            job = "    runs-on: windows-latest\n"
            muts += [
                (f"workflow: {name} job with continue-on-error", kind, after(text, job, "    continue-on-error: true\n")),
                (f"workflow: {name} job with an if", kind, after(text, job, "    if: false\n")),
                (f"workflow: {name} job with run defaults", kind, after(text, job, "    defaults:\n      run:\n        shell: bash\n")),
                (f"workflow: {name} job with an environment", kind, after(text, job, "    env:\n      PYTHONPATH: x\n")),
                (f"workflow: {name} with a workflow-level environment", kind,
                 text.replace("\njobs:\n", "\nenv:\n  PYTHONPATH: x\n\njobs:\n", 1)),
                (f"workflow: {name} with a second job", kind,
                 text + "  extra:\n    runs-on: windows-latest\n    steps:\n      - run: echo x\n"),
                (f"workflow: {name} with a step writing GITHUB_ENV", kind,
                 add_step(text, 'echo "PYTHONPATH=x" >> $env:GITHUB_ENV')),
                (f"workflow: {name} install block with an extra line", kind,
                 text.replace(lint, lint + '\n          echo "PYTHONPATH=x" >> $env:GITHUB_ENV', 1)),
                (f"workflow: {name} checks out another repository", kind,
                 text.replace(f"actions/checkout@{sha} # v7.0.1\n",
                              f"actions/checkout@{sha} # v7.0.1\n        with:\n          repository: someone/else\n", 1)),
            ]
        muts += [
            ("workflow: the static step neutralised in its own run block", "ci",
             ci.replace("run: python tools/earth_test.py static", "run: python tools/earth_test.py static; exit 0")),
            ("workflow: the static step followed by exit 0", "ci",
             ci.replace(static_run, "        run: |\n          python tools/earth_test.py static\n          exit 0\n")),
            ("workflow: the tag check neutralised in its own run block", "rel",
             rel_wf.replace('run: python tools/build_zip.py --check-tag "$env:TAG"',
                            'run: python tools/build_zip.py --check-tag "$env:TAG"; exit 0')),
            ("workflow: the release build neutralised in its own run block", "rel",
             rel_wf.replace("run: python tools/build_zip.py --release", "run: python tools/build_zip.py --release; exit 0")),
            ("workflow: the release attaches only the .sha256 (its file list)", "rel",
             rel_wf.replace('$_.Name -like "*.zip" -or ', "")),
            ("workflow: gh attaches only the .sha256 (its arguments)", "rel",
             rel_wf.replace('"$env:TAG" @files', '"$env:TAG" "dist/x.zip.sha256"')),
            ("workflow: gh attaches an extra file", "rel", rel_wf.replace('"$env:TAG" @files', '"$env:TAG" @files README.md')),
            ("workflow: the publish count check removed", "rel",
             re.sub(r"\n\s*if \(\$files\.Count -ne 2\)[^\n]*", "", rel_wf)),
            ("workflow: ci on push to main only", "ci", ci.replace("  push:\n", "  push:\n    branches: [main]\n", 1)),
            ("workflow: ci on pull requests touching some paths only", "ci",
             ci.replace("  pull_request:\n", '  pull_request:\n    paths:\n      - "tools/**"\n', 1)),
            ("workflow: the artifact upload ignores a missing zip", "ci",
             ci.replace("if-no-files-found: error", "if-no-files-found: ignore")),
            ("workflow: the artifact upload of another path", "ci", ci.replace("path: dist/*.zip", "path: README.md")),
            ("workflow: the release is a draft", "rel", rel_wf.replace("--verify-tag", "--verify-tag --draft")),
            ("workflow: the release is a prerelease", "rel", rel_wf.replace("--verify-tag", "--prerelease --verify-tag")),
            ("workflow: the release names another repository", "rel",
             rel_wf.replace("--verify-tag", "--verify-tag --repo someone/else")),
        ]
        lint_dir = td / "lint-fixture"
        shutil.copytree(LINT, lint_dir)
        (lint_dir / "requirements.txt").write_text("luaparser\n", encoding="utf-8")
        f = workflow_findings(REPO / ".github" / "workflows", lint_dir)
        results.append(("workflow: requirements.txt without the luaparser pin", bool(f), f[:1]))
        for label, kind, text in muts:
            fn = check_ci if kind == "ci" else check_release
            orig = ci if kind == "ci" else rel_wf
            f = fn(text, manifest) if text != orig else []
            results.append((label, bool(f) and text != orig, f[:1] if text != orig else ["mutation did not apply"]))
        results.append(("workflow: the committed ci.yml and release.yml pass the scan",
                        not check_ci(ci, manifest) and not check_release(rel_wf, manifest),
                        (check_ci(ci, manifest) + check_release(rel_wf, manifest))[:1]))
        # the tag check itself: only "v" plus info.json's version passes
        _, version, _ = build_zip.mod_identity()
        major, minor, patch = version.split(".")
        for tag, want in (("v" + version, True), (f"v{major}.{minor}.{int(patch) + 1}", False), (version, False),
                          ("v" + version + "-rc1", False), ("V" + version, False), (" v" + version, False)):
            try:
                build_zip.check_tag(tag)
                passed = True
            except build_zip.BuildError:
                passed = False
            results.append((f"check_tag: {tag!r} {'passes' if want else 'fails'}", passed == want, ""))
        # registration, names, dashes, info.json, locale
        lua_cases = {
            "registration: on_tick": ("control.lua", "script.on_event(defines.events.on_tick, function() end)\n"),
            "registration: on_nth_tick": ("control.lua", "script.on_nth_tick(60, function() end)\n"),
            "registration: per-chunk outside bandfix": ("scripts/guards.lua",
                                                        "script.on_event(defines.events.on_chunk_generated, "
                                                        "function() end)\n"),
            "registration: computed event id": ("control.lua", "local ev = defines.events\nlocal k = 'on_' .. 'tick'\n"
                                                               "script.on_event(ev[k], function() end)\n"),
        }
        base_mod = td / "mod-base"
        shutil.copytree(MOD, base_mod / "terra-nauvis")
        for label, (path, text) in lua_cases.items():
            m = td / ("mod-" + str(abs(hash(label)) % 10 ** 8)) / "terra-nauvis"
            shutil.copytree(MOD, m)
            _write(m, path, text)
            f = registration_findings(m)
            results.append((label, bool(f), f[:1]))
        m = td / "mod-names" / "terra-nauvis"
        shutil.copytree(MOD, m)
        cfg = tnconfig.load(MOD / "prototypes" / "config.lua")
        _write(m, "prototypes/extra.lua", f"local n = \"{cfg['identity']['noise_prefix']}x_v1\"\nreturn n\n")
        f = name_findings(m)
        results.append(("names: a noise name outside config.lua", bool(f), f[:1]))
        results += name_form_fixtures(td, cfg)
        results += output_args_fixtures(td)
        m = td / "mod-coord" / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, "prototypes/expressions/extra.lua", "local e = \"x - 7200\"\nreturn e\n")
        f = design_findings(m)
        results.append(("design: a tile literal outside the data tables", bool(f), f[:1]))
        m = td / "mod-dash" / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, "locale/en/extra.cfg", "[x]\ny=a \u2013 b\n")
        f = dash_findings(m)
        results.append(("dashes: an en dash in shipped text", bool(f), f[:1]))
        info = load_json(MOD / "info.json")
        for label, mutate in (("info.json: title over 100", lambda i: i.update(title="T" * 101)),
                              ("info.json: one-number version", lambda i: i["dependencies"].append("? x >= 1")),
                              ("info.json: Space Age flag", lambda i: i.update(quality_required=True)),
                              ("info.json: factorio 2.0", lambda i: i.update(factorio_version="2.0"))):
            i2 = json.loads(json.dumps(info))
            mutate(i2)
            f = check_info(i2, cfg)
            results.append((label, bool(f), f[:1]))
        secs, errs = parse_cfg("[a]\nb=c\nno equals here\nb=d\n")
        results.append(("locale: a line without '=' and a duplicate key", len(errs) >= 2, errs[:2]))
        exp = expected_locale(cfg)
        missing = [k for k in exp["string-mod-setting"] if k.endswith("-6")]
        results.append(("locale: every dropdown value needs its label", bool(missing), missing[:1]))
        f = toggle_multiply_findings({"x": "a * tn_canals"}, ["tn_canals"])
        results.append(("design: toggle multiply (U5, dump check)", bool(f), f[:1]))
        results += registration_form_fixtures(td)
        results += launch_form_fixtures(td, gui)
        results += schema_fixtures(td, cfg)
    return results


def name_form_fixtures(td, cfg):
    """Each way a Lua file can spell an Earth name past a string literal must fail the name scan:
    a dot-index field, a table key, a method call, a method definition, a dotted function name;
    the same in a test-only mod of tools/mods/, and the mod ID in such a mod's info.json."""
    prefix = cfg["identity"]["noise_prefix"]
    placeholder = sorted((cfg.get("placeholder") or {}).get("names", {}).values())
    known = placeholder[0] if placeholder else prefix + "land_coarse"
    forms = {
        "names: a dot-index field spells a noise name": (
            "prototypes/extra.lua", f'local e = data.raw["noise-expression"].{known}\nreturn e\n'),
        "names: a table key spells a noise name": ("prototypes/extra.lua", f"local t = {{{prefix}land_coarse = 1}}\nreturn t\n"),
        "names: a method call spells a noise name": ("prototypes/extra.lua", f"local o = {{}}\no:{prefix}x()\n"),
        "names: a method definition spells a noise name": (
            "prototypes/extra.lua", f"local M = {{}}\nfunction M:{prefix}x() end\nreturn M\n"),
        "names: a dotted function name spells a noise name": (
            "prototypes/extra.lua", f"local M = {{}}\nfunction M.{prefix}x() end\nreturn M\n"),
    }
    out = []
    for label, (path, text) in forms.items():
        m = td / ("names-" + str(abs(hash(label)) % 10 ** 8)) / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, path, text)
        f = name_findings(m)
        out.append((label, bool(f), f[:1]))
    for label, path, text in (
            ("names: a test-only mod's Lua spells a noise name", "tools/mods/ea-x/data.lua",
             f'local e = data.raw["noise-expression"].{known}\nreturn e\n'),
            ("names: a test-only mod's Lua string spells a noise name", "tools/mods/ea-x/data.lua",
             f'local n = "{known}"\nreturn n\n'),
            ("names: a test-only mod's info.json names the mod ID", "tools/mods/ea-x/info.json",
             json.dumps({"name": "ea-x", "dependencies": [cfg["identity"]["id"]]}))):
        root = td / ("tmods-" + str(abs(hash(label)) % 10 ** 8))
        shutil.copytree(MOD, root / "terra-nauvis")
        _write(root, path, text)
        f = name_findings(root / "terra-nauvis")
        out.append((label, bool(f), f[:1]))
    clean = td / "names-clean" / "terra-nauvis"
    shutil.copytree(MOD, clean)
    _write(clean, "prototypes/extra.lua", "local t = {elevation = 1}\nlocal e = t.elevation\nreturn e\n")
    f = name_findings(clean)
    out.append(("names: identifiers that spell no Earth name stay clean", not f, f[:1]))
    return out


def output_args_fixtures(td):
    """The output_args row: an undeclared option dest fails, a written option without the refusal
    call fails, and a declared, refused one passes."""
    out = []
    cases = {
        "output_args: an option declared nowhere fails": (
            "import argparse\nap = argparse.ArgumentParser()\nap.add_argument('--install-into')\n", True),
        "output_args: a written option without refuse_live_outputs fails": (
            "import argparse\nap = argparse.ArgumentParser()\nap.add_argument('--out')\na = ap.parse_args()\n", True),
        "output_args: a computed option name fails closed": (
            "import argparse\nap = argparse.ArgumentParser()\nflag = '--o' + 'ut'\nap.add_argument(flag)\n", True),
        "output_args: a declared, refused written option passes": (
            "import argparse\nimport tnguard\nap = argparse.ArgumentParser()\nap.add_argument('--out')\n"
            "ap.add_argument('--seed')\na = ap.parse_args()\ntnguard.refuse_live_outputs(a, 'x')\n", False),
    }
    for label, (text, must_fail) in cases.items():
        d = td / ("oargs-" + str(abs(hash(label)) % 10 ** 8))
        _write(d, "tools/x.py", text)
        f, _ = output_args_findings(d / "tools", d)
        out.append((label, bool(f) == must_fail, f[:1]))
    out += relative_output_fixtures(td)
    return out


def relative_output_fixtures(td):
    """A relative output is judged where the tool writes it: joined to the folder the tool resolves
    it against (its base), not to whatever folder it was started from. A scratch workspace holds a
    scratch profile; the relative path lands in that profile from the workspace but not from the
    folder the tool runs in. tnguard must refuse it with that base and rewrite every passing output
    to the absolute path it checked; and game_selftest.py --replay, started from another folder
    with that relative --out-root (it joins a relative --out-root onto FACTORIO_WS), must refuse it
    and write nothing (the round-3 review's escape). Every write would land in the scratch folder."""
    import argparse
    import contextlib
    import io
    out = []
    bs = "\\"
    fact = "Fact" + "orio"
    app = "APP" + "DATA"
    ws = td / "rel-ws"
    (ws / "repo").mkdir(parents=True)
    profile = ws / "prof" / fact
    (profile / "evidence").mkdir(parents=True)
    (profile / "evidence" / "keep.txt").write_text("x", encoding="utf-8")
    rel = "prof" + bs + fact + bs + "evidence"
    orig_roots = tnguard.live_profile_roots
    tnguard.live_profile_roots = lambda: [profile.resolve()] + orig_roots()
    try:
        out.append(("output_args: a relative output is judged against the tool's base, not its working folder",
                    tnguard.live_output_problem(rel, ws) is not None and
                    tnguard.live_output_problem(rel, ws / "repo") is None, ""))
        ns = argparse.Namespace(out_root=rel, seed="1")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                tnguard.refuse_live_outputs(ns, "fixture", base=ws)
            refused = False
        except SystemExit:
            refused = True
        ok_ns = argparse.Namespace(out_root="fine", seed="1")
        tnguard.refuse_live_outputs(ok_ns, "fixture", base=ws)
        out.append(("output_args: refuse_live_outputs refuses with the base and rewrites a passing output to its "
                    "absolute path", refused and ok_ns.out_root == str(ws / "fine") and ok_ns.seed == "1",
                    ok_ns.out_root))
    finally:
        tnguard.live_profile_roots = orig_roots
    import importlib.util
    label = "output_args: game_selftest.py --replay judges a relative --out-root where it writes it"
    if not (importlib.util.find_spec("numpy") and importlib.util.find_spec("PIL")):
        out.append((label, True, "skipped: numpy and PIL are absent (CI installs only the lint requirements); the "
                                 "gate's static row runs it"))
        return out
    env = {k: v for k, v in os.environ.items() if k != tnguard.ENV}
    env["FACTORIO_WS"] = str(ws)
    env[app] = str(profile.parent)
    before = sorted(p.name for p in (profile / "evidence").iterdir())
    cp = subprocess.run([sys.executable, str(HERE / "game_selftest.py"), "--out-root", rel, "--replay"],
                        cwd=str(ws / "repo"), env=env, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=180)
    after = sorted(p.name for p in (profile / "evidence").iterdir())
    text = (cp.stdout or "") + (cp.stderr or "")
    out.append((label, cp.returncode != 0 and "refuses --out-root" in text and before == after,
                (text.strip().splitlines() or [""])[-1][:200]))
    return out


def registration_form_fixtures(td):
    """Each way a handler can be registered past a literal script.on_event must fail the scan."""
    ev = "defines.events"
    forms = {
        "registration: the core event_handler library": ("control.lua", 'local h = require("event_handler")\n'
                                                         f'h.add_lib({{events = {{[{ev}.on_player_created] = '
                                                         'function() end}})\n'),
        "registration: an alias of script": ("control.lua", f"local s = script\ns.on_event({ev}.on_player_created, "
                                                            "function() end)\n"),
        "registration: _G.script": ("control.lua", f"_G.script.on_event({ev}.on_player_created, function() end)\n"),
        "registration: a stored script.on_event": ("control.lua", f"local reg = script.on_event\nreg({ev}."
                                                                  "on_player_created, function() end)\n"),
        "registration: script passed as an argument": ("control.lua", "local function f(x) return x end\nf(script)\n"),
        "registration: rawget of a global": ("control.lua", 'local s = rawget(_ENV, "script")\nreturn s\n'),
        "registration: a computed index into defines.events": ("control.lua", f"local n = 'on_' .. 'tick'\nscript."
                                                                              f"on_event({ev}[n], function() end)\n"),
        "registration: an alias of defines": ("control.lua", "local d = defines\nreturn d\n"),
        "registration: a per-chunk event as a table key outside bandfix": (
            "scripts/guards.lua", f"local t = {{[{ev}.on_chunk_generated] = function() end}}\nreturn t\n"),
        "registration: a per-chunk event name as a string": ("scripts/guards.lua",
                                                              "local n = 'on_chunk_generated'\nreturn n\n"),
        "registration: script:method call": ("control.lua", "script:on_event(1, function() end)\n"),
        "registration: a handler file under a dist folder": ("scripts/dist/tick.lua", f"script.on_event({ev}.on_tick, "
                                                                                      "function() end)\n"),
    }
    out = []
    for label, (path, text) in forms.items():
        m = td / ("reg-" + str(abs(hash(label)) % 10 ** 8)) / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, path, text)
        f = registration_findings(m)
        out.append((label, bool(f), f[:1]))
    m = td / "reg-clean" / "terra-nauvis"
    shutil.copytree(MOD, m)
    _write(m, "scripts/ok.lua", f"script.on_init(function() end)\nscript.on_event({ev}.on_player_created, "
                                f"function() end)\nlocal n = script.mod_name\nreturn n\n")
    f = registration_findings(m)
    out.append(("registration: the allowed forms stay clean", not f, f[:2]))
    m = td / "names-dist" / "terra-nauvis"
    shutil.copytree(MOD, m)
    cfg = tnconfig.load(MOD / "prototypes" / "config.lua")
    _write(m, "scripts/dist/names.lua", f"local n = \"{cfg['identity']['noise_prefix']}secret_v1\"\nreturn n\n")
    f = name_findings(m)
    try:
        build_zip.mod_files(m)
        refused = False
    except build_zip.BuildError:
        refused = True
    out.append(("scan list: a Lua file under a dist folder is scanned and refused by the zip", bool(f) and refused,
                f[:1]))
    return out


def launch_form_fixtures(td, gui):
    """Each live-profile, mods-folder and launch form must fail the launch scan."""
    exe = "factorio" + ".exe"
    app = "APP" + "DATA"
    fact = "Fact" + "orio"
    forms = {
        "launch: a shell script copying into the live mods folder": (
            "tools/install.sh", f'cp dist/terra-nauvis_0.1.0.zip "${app}/{fact}/mods/"\n'),
        "launch: the braced live-profile variable in a script": ("tools/a.ps1", f"Get-ChildItem ${{{app}}}\n"),
        "launch: the PowerShell live-profile variable in a script": ("tools/b.ps1", f"Get-ChildItem $env:{app}\n"),
        "launch: the roaming profile path without the profile variable": ("tools/c.py", f"P = '~/Roaming/{fact}/saves'\n"),
        "launch: a JavaScript copy into a mods folder": (
            "tools/x.js", f"require('fs').copyFileSync('dist/x.zip', process.env.{app} + '/{fact}/mods/x.zip')\n"),
        "launch: build_zip.py --out-dir into the live mods folder": (
            "tools/inst.py", "import os, subprocess, sys\nsubprocess.run([sys.executable, 'tools/build_zip.py', "
                             f"'--out-dir', os.path.expandvars('${app}/{fact}/mods')])\n"),
        "launch: --out-dir into a mods folder in a script": ("tools/d.ps1", "python tools/build_zip.py --out-dir "
                                                                            "C:/somewhere/mods\n"),
        "launch: a game launch under a dist folder": (
            "tools/dist/run.py", f"import subprocess\nsubprocess.run([r'C:/g/bin/x64/{exe}', '--create', 'x'])\n"),
        "launch: a game launch under a dot folder": (
            "tools/.hidden/run.py", f"import subprocess\nsubprocess.run([r'C:/g/bin/x64/{exe}', '--create', 'x'])\n"),
        "launch: the game through a path variable": (
            "tools/v.py", "import subprocess\nfrom pathlib import Path\nexe = Path('C:/g') / 'bin' / 'x64' / "
                          "('fact' + 'orio')\nsubprocess.run([str(exe), '--version'])\n"),
        "launch: a write into a mods folder": (
            "tools/w.py", "from pathlib import Path\nd = Path('C:/x') / 'mods'\n(d / 'x.zip').write_bytes(b'')\n"),
        "launch: the game binary run from a shell script": ("tools/g.sh", f'"$GAME/bin/x64/{fact.lower()}" --version\n'),
        "launch: the write-data placeholder of the live profile": (
            "tools/cfg.py", "W = 'write-data=__PATH__" + "system-" + "write-data__'\n"),
    }
    out = []
    for label, (path, text) in forms.items():
        d = td / ("launch-" + str(abs(hash(label)) % 10 ** 8))
        _write(d, path, text)
        f, _ = launch_findings([d / "tools"], LINT, d)
        out.append((label, bool(f), f[:1]))
    d = td / "launch-exe"
    (d / "tools").mkdir(parents=True)
    (d / "tools" / "helper.exe").write_bytes(b"MZ\0\0")
    f, _ = launch_findings([d / "tools"], LINT, d)
    out.append(("launch: a binary executable in a scanned tree", bool(f), f[:1]))
    d = td / "launch-root"
    _write(d, "setup.sh", f'cp dist/x.zip "$HOME/{fact}/mods/"\n')
    f, _ = launch_findings([], LINT, d, root_scripts(d))
    out.append(("launch: a root script copying into a mods folder", bool(f), f[:1]))
    live = Path(os.environ.get(app) or Path.home() / ("App" + "Data") / "Roaming") / fact
    bs = "\\"
    # Every spelling build_zip.build() is handed targets a scratch profile, added to the guard's
    # roots for the duration: were a spelling to slip past the guard, the zip would land in the
    # scratch folder, never in the real live profile. The real profile is only ever checked.
    fake = td / "profile-root" / fact
    (fake / "saves").mkdir(parents=True)
    (fake / "player-data.json").write_text("{}", encoding="utf-8")
    drive, rest = str(fake)[:1], str(fake)[2:]
    linked = td / "linked-out" / "player-data.json"
    linked.parent.mkdir(parents=True)
    os.link(fake / "player-data.json", linked)
    spellings = {
        "a mods folder": td / "out" / "mods",
        "the live profile": fake / "x",
        "the extended-length spelling": bs * 2 + "?" + bs + str(fake) + bs + "saves",
        "the forward-slash extended-length spelling": "//?/" + str(fake).replace(bs, "/") + "/config",
        "the localhost admin share": bs * 2 + "localhost" + bs + drive + "$" + rest + bs + "saves",
        "the loopback-address admin share": bs * 2 + "127.0.0.1" + bs + drive.lower() + "$" + rest + bs + "script-output",
        "the extended UNC admin share": bs * 2 + "?" + bs + "UNC" + bs + "localhost" + bs + drive + "$" + rest,
        "the device spelling": bs * 2 + "." + bs + str(fake) + bs + "saves",
        "a mods folder with a trailing dot": td / "out" / "mods." / "x",
        "the NT-namespace spelling of a profile file": bs + "??" + bs + str(fake) + bs + "player-data.json",
        "the NT-namespace spelling of a profile folder": bs + "??" + bs + str(fake) + bs + "saves",
        "the NT-namespace admin share": bs + "??" + bs + "UNC" + bs + "localhost" + bs + drive + "$" + rest + bs + "saves",
        "the NT-namespace spelling with a lower-case drive": bs + "??" + bs + str(fake).lower() + bs + "saves",
        "the forward-slash NT-namespace spelling": "/??/" + str(fake).replace(bs, "/") + "/saves",
        "the global NT namespace": bs + "GLOBAL??" + bs + str(fake) + bs + "saves",
        "a device-object path": bs + "Device" + bs + "HarddiskVolume1" + rest + bs + "saves",
        "a root-relative path": bs + rest.lstrip(bs) + bs + "saves",
        "a drive-relative path": drive + ":" + "x",
        "a wildcard": str(td / "out") + bs + "*",
        "a hard link to a profile file": linked,
        "a folder holding a hard link to a profile file": linked.parent,
    }
    try:
        import _winapi
        jx = td / "junction"
        _winapi.CreateJunction(str(fake), str(jx))
        jdir = td / "holds-junction"
        jdir.mkdir()
        _winapi.CreateJunction(str(fake), str(jdir / "inner"))
        spellings.update({"a plain path through a junction into the profile": jx / "x",
                          "the NT-namespace spelling through a junction": bs + "??" + bs + str(jx) + bs + "x",
                          "a folder holding a junction into the profile": jdir})
    except (ImportError, OSError, AttributeError):
        out.append(("tnguard junction spellings (no junction support here)", True, "skipped"))
    orig_roots = tnguard.live_profile_roots
    tnguard.live_profile_roots = lambda: [fake.resolve()] + orig_roots()
    try:
        refused = {}
        for label, target in spellings.items():
            try:
                build_zip.build(target)
                refused[label] = False
            except build_zip.BuildError:
                refused[label] = True
        escaped = sorted(p.relative_to(fake).as_posix() for p in fake.rglob("*") if p.suffix in (".zip", ".sha256")
                         or p.name.endswith(".build.json"))
        out.append(("build_zip.py refuses an --out-dir in a mods folder or the (scratch) live profile, in every spelling",
                    all(refused.values()) and not escaped and tnguard.live_output_problem(td / "out" / "dist") is None,
                    [k for k, v in refused.items() if not v] + escaped))
        for label, target in spellings.items():
            out.append((f"tnguard refuses {label} as an output", tnguard.live_output_problem(target) is not None, ""))
    finally:
        tnguard.live_profile_roots = orig_roots
    out.append(("tnguard refuses the real live profile, plainly and in the NT namespace (checked, never written)",
                tnguard.live_output_problem(live / "x") is not None and
                tnguard.live_output_problem(bs + "??" + bs + str(live) + bs + "x") is not None, ""))
    import argparse
    import contextlib
    import io
    for dest in ("candidate_out", "dest", "github_env", "out_json"):
        ns = argparse.Namespace(**{dest: str(live / "saves" / "x.png")})
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                tnguard.refuse_live_outputs(ns, "fixture")
            ok = False
        except SystemExit:
            ok = True
        out.append((f"refuse_live_outputs refuses --{dest.replace('_', '-')} into the live profile", ok, ""))
    for p in (linked, td / "junction", td / "holds-junction" / "inner"):
        try:
            if p.is_dir() and not p.is_symlink():
                os.rmdir(p)
            elif p.exists():
                os.unlink(p)
        except OSError:
            pass
    return out


def schema_fixtures(td, cfg):
    """config.lua's group shapes: a wrong shape raises instead of reading as empty, fallbacks are
    exempt from the release registry check and never registered, and defined_names includes them."""
    out = []
    bad_fw = dict(cfg, firewall=["tn_x_v1"])
    try:
        tnconfig.firewall_names(bad_fw)
        out.append(("schema: a list-shaped firewall group raises", False, "read as names"))
    except tnconfig.ConfigError:
        out.append(("schema: a list-shaped firewall group raises", True, ""))
    bad_fb = dict(cfg, fallbacks=["tn_scale"])
    out.append(("schema: a flat fallbacks list fails the names row", bool(tnconfig.schema_problems(bad_fb)), ""))
    out.append(("schema: an unknown map key under fallbacks fails", bool(tnconfig.schema_problems(dict(
        cfg, fallbacks={"mars": [{"name": "tn_scale", "map_qualified": False}]}))), ""))
    fb = dict(cfg, fallbacks={"europe": [{"name": "tn_scale", "map_qualified": False}]},
              release_registry=[{"release": "0.1.0", "geography": "g1", "names": ["tn_scale", "tn_geo_v1"], "files": []}],
              placeholder=None, presets={"europe": dict(cfg["presets"]["europe"], placeholder=None)})
    fz = td / "frozen-fixture.json"
    fz.write_text(json.dumps({"format": "tn-frozen/1", "bodies": {"tn_geo_v1": {"type": "noise-expression",
                                                                               "sha256": "0" * 64}}}), encoding="utf-8")
    out.append(("schema: a fallback in the release registry is exempt from frozen.json", not build_zip.release_problems(
        fb, fz), build_zip.release_problems(fb, fz)[:1]))
    fz.write_text(json.dumps({"format": "tn-frozen/1", "bodies": {"tn_geo_v1": {"type": "noise-expression",
                                                                               "sha256": "0" * 64},
                                                                 "tn_scale": {"type": "noise-expression",
                                                                              "sha256": "0" * 64}}}), encoding="utf-8")
    out.append(("schema: a registered fallback fails the release build", bool(build_zip.release_problems(fb, fz)), ""))
    out.append(("schema: defined_names includes the fallbacks", "tn_scale" in tnconfig.defined_names(fb)["noise"], ""))
    bad_tg = dict(cfg, toggles={"canals": {"setting": "scale", "preset_key": "tn_canals", "mechanism": "name switch"}},
                  toggle_order=[])
    out.append(("schema: toggles without their toggle_order entry fail", bool(tnconfig.schema_problems(bad_tg)), ""))
    # the three stores of Earth body names (config.lua's firewall and release registry, frozen.json)
    fw_only = dict(fb, firewall={"europe": ["tn_elevation_europe_v1", "tn_geo_europe_v1"]}, release_registry=[])
    out.append(("schema: a firewall body in no release_registry row fails the names row",
                bool(tnconfig.schema_problems(fw_only)), ""))
    fz.write_text(json.dumps({"format": "tn-frozen/1", "bodies": {}}), encoding="utf-8")
    probs = build_zip.release_problems(fw_only, fz)
    out.append(("release: an unregistered firewall body fails the release build",
                any("tn_elevation_europe_v1" in p and "not registered" in p for p in probs), probs[:1]))
    fw_reg = dict(fb, firewall={"europe": ["tn_geo_v1"]})
    fz.write_text(json.dumps({"format": "tn-frozen/1", "bodies": {}}), encoding="utf-8")
    out.append(("release: a released body never frozen fails the release build",
                any("tn_geo_v1" in p for p in build_zip.release_problems(fw_reg, fz)), ""))
    out.append(("static: a config body missing from frozen.json fails the frozen row",
                any("tn_geo_v1" in x for x in config_frozen_findings(fw_reg, {"bodies": {}})), ""))
    out.append(("static: a registered config body passes the frozen row",
                not config_frozen_findings(fw_reg, {"bodies": {"tn_geo_v1": {"type": "noise-expression",
                                                                             "sha256": "0" * 64}}}), ""))
    out.append(("schema: a noise name without the noise prefix fails",
                bool(tnconfig.schema_problems(dict(fb, release_registry=[{"release": "0.1.0", "geography": "g1",
                                                                         "names": ["elevation_x"], "files": []}]))),
                ""))
    out.append(("schema: the placeholder's names need no registration",
                not tnconfig.unregistered_names(cfg, {}) if cfg.get("placeholder") else True, ""))
    return out


def row_fixtures():
    res = fixture_controls()
    bad = [f"{label} did not behave ({detail})" for label, ok, detail in res if not ok]
    return bad, f"{len(res)} positive controls, {len(res) - len(bad)} behaved"


# ------------------------------------------------------------------------------------------------ all rows

ROWS = [
    ("lint", row_lint), ("info_json", row_info), ("locale", row_locale), ("dashes", row_dashes),
    ("registration", row_registration), ("names", row_names), ("design_rules", row_design),
    ("launch_scan", row_launch), ("output_args", row_output_args), ("workflow_scan", row_workflow),
    ("attribution_scan", row_attribution), ("data_src", row_data_src), ("frozen_static", row_frozen), ("zip", row_zip),
    ("fixtures", row_fixtures),
]


def run_rows(only=None, printer=print):
    results = []
    for name, fn in ROWS:
        if only and name not in only:
            continue
        try:
            fails, detail = fn()
        except Exception as e:  # a crashed row fails closed
            fails, detail = [f"row crashed: {type(e).__name__}: {e}"], ""
        results.append({"row": name, "ok": not fails, "failures": fails, "detail": detail})
        printer(f"ROW {'ok  ' if not fails else 'FAIL'} {name}: {detail}")
        for f in fails[:12]:
            printer(f"     - {f}")
    return results
