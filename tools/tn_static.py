#!/usr/bin/env python3
"""T16 static rows (test notes.md T16; design section 5, `earth_test.py static`).

Every row here reads only the checked-out tree: no game, no fh.py and no FACTORIO_WS, so ci.yml
runs the same rows on GitHub's runner that the gate runs as its step 1. One row reads git refs: the
append-only row compares the tree with main and origin/main (ci.yml and latest.yml check out with
full history, so the runner holds origin/main) and fails closed when it cannot read them. Each row
returns a list of failure messages (empty means pass) and a short detail line.

Rows: lint, info_json, locale, dashes, registration, storage, names, design_rules, workflow_scan,
data_src, frozen_static, append_only, fallbacks, zip, plus fixture positive
controls for the scans (each rule must fail its own fixture; fixtures are written at run time into
a temporary directory outside the scanned trees and never committed). No row scans tools/ or
tests/ for game launches,
live-profile paths or copies into a mods folder (the workflow scan still keeps all three workflows
off the game and the workspace): fh.py isolation (G1) is the only live-profile protection (decision
of 2026-10-27 23:47), and copying the built zip into the live mods folder is allowed (16:19).
"""
import copy
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
import tnfrozen  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
LINT = HERE / "lint"
# Dot directories (.git, the gitignored scratch folder) are skipped by walk_files; these are the rest.
# The mod scans never use walk_files: they read build_zip's own file list (mod_files), so every
# file the zip ships is scanned and a skipped folder cannot hide one.
SKIP_DIRS = {"dist", "spikes", "__pycache__", "node_modules"}
# Needles of the workflow scan, in fragments as they were when the retired launch scan read this file.
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
# Data files, exempt from the literal rule: config, the approval tables and every generated file, the
# control stage's band-fix tables among them (coast-band-fix: terra-nauvis/scripts/generated/).
DATA_LUA = ("prototypes/config.lua", "prototypes/tables/", "prototypes/generated/", "scripts/generated/")


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


_PARSED = {}


def parse_lua_file(p):
    """luaparser's tree of a Lua file, kept per text as tnlua.parse keeps it: the fixture controls read
    the mod's files again in every copy they edit, and no reader changes a tree (design notes 2026-10-29
    11:05). A file that does not parse raises each time it is read."""
    text = Path(p).read_text(encoding="utf-8")
    k = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if k not in _PARSED:
        _PARSED[k] = tnconfig.parse_lua(text, rel(p))
    return _PARSED[k]


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def lint_manifest(lint_dir=LINT):
    return load_json(Path(lint_dir) / "manifest.json")


# ------------------------------------------------------------------------------------------------ lint

def find_luacheck(manifest):
    """The linter binary: TN_LUACHECK, then PATH, then a local copy at downloads/<name>-<version>/ in FACTORIO_WS or
    in any folder that holds the checkout (fetch_linter.py --dest writes one). run_luacheck refuses a binary whose
    sha256 is not the manifest's, so a copy found this way still has to be the recorded release."""
    cands = []
    env = os.environ.get("TN_LUACHECK")
    if env:
        cands.append(Path(env))
    for name in ("luacheck.exe", "luacheck"):
        w = shutil.which(name)
        if w:
            cands.append(Path(w))
    want = manifest["linter"]
    rel = Path("downloads") / f"{want['name']}-{want['version']}" / Path(want["source"]).name
    roots = ([Path(os.environ["FACTORIO_WS"])] if os.environ.get("FACTORIO_WS") else []) + list(REPO.parents)
    cands += [r / rel for r in roots]
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
    # the Map type entries: the newest elevation entry of each map carries localised_name
    # {"noise-expression.<entry>"} (D2 amended), so the [noise-expression] section names it
    for g in tnconfig.geography(cfg).values():
        exp.setdefault("noise-expression", set()).add(g["entry"])
    # a scale extension's entry takes those fields at the scales past its version's list
    for x in (cfg.get("scale_extensions") or {}).values():
        exp.setdefault("noise-expression", set()).add(x["entry"])
    frozen = (cfg.get("tiles") or {}).get("frozen")
    if frozen:
        exp["tile-name"] = {frozen["tile"]}
    # control code's messages, whose keys it builds from config.lua's messages group
    msgs = cfg.get("messages") or {}
    for key in (msgs.get("keys") or {}).values():
        exp.setdefault(msgs["section"], set()).add(key)
    for sec, key in control_keys:
        exp.setdefault(sec, set()).add(key)
    return exp


def thousands(n):
    return f"{int(n):,}"


def scale_label_findings(cfg, merged):
    """Each scale value's label (APPROVALS 1c) carries every map's world size at that scale,
    W s x H s tiles from config.lua's map sizes, written with thousands separators."""
    out = []
    s = (cfg.get("settings") or {}).get("scale")
    if not s:
        return out
    labels = merged.get("string-mod-setting", {})
    for v in s.get("allowed_values") or []:
        text = labels.get(f"{s['name']}-{v}")
        if text is None:
            continue
        for key in cfg["map_order"]:
            m = cfg["maps"][key]
            want = f"{m['display']} {thousands(m['width_px'] * int(v))} x {thousands(m['height_px'] * int(v))}"
            if want not in text:
                out.append(f"locale [string-mod-setting] {s['name']}-{v} lacks the world size {want!r} (APPROVALS 1c)")
    return out


SIZE_FIGURE_RE = re.compile(r"(?<!\d)(?<!\d,)(\d{1,3}(?:,\d{3})+|\d+) x (\d{1,3}(?:,\d{3})+|\d+)(?!\d)(?!,\d)")
R8_DOC = REPO / "docs" / "plan" / "research" / "R8-perf-footprint.md"
APPROVALS_DATA = REPO / "data-src" / "approvals" / "approvals-data.json"


def size_texts(cfg, merged):
    """The texts that carry the size context (milestone extras; D3): each scale label, the scale tooltip and each
    preset description, as (where, text or None, sizes it must carry, sizes it may carry), sizes as "W x H"
    strings with thousands separators: a scale label its value's world size of every map, the tooltip none, a
    preset description its map's size at size_context.preset_scales; any of them may carry any world size of
    the maps it names."""
    sc = cfg.get("size_context") or {}
    scale = (cfg.get("settings") or {}).get("scale") or {}
    values = [int(v) for v in scale.get("allowed_values") or []]

    def size(mk, v):
        m = cfg["maps"][mk]
        return f"{thousands(m['width_px'] * v)} x {thousands(m['height_px'] * v)}"
    every = {size(mk, v) for mk in cfg["map_order"] for v in values}
    out = []
    labels = merged.get("string-mod-setting", {})
    for v in values:
        need = {size(mk, v) for mk in cfg["map_order"]}
        out.append((f"[string-mod-setting] {scale['name']}-{v}", labels.get(f"{scale['name']}-{v}"), need, need))
    if scale:
        out.append((f"[mod-setting-description] {scale['name']}",
                    merged.get("mod-setting-description", {}).get(scale["name"]), set(), every))
    for key in cfg.get("preset_order") or []:
        p = cfg["presets"][key]
        need = {size(p["map"], int(v)) for v in sc.get("preset_scales") or []}
        allowed = {size(p["map"], v) for v in values}
        out.append((f"[map-gen-preset-description] {p['name']}", merged.get("map-gen-preset-description", {}).get(
            p["name"]), need, allowed))
    return out


def size_context_findings(cfg, merged, r8_text=None, approvals=None):
    """D3 and JI-12 (T16 locale; milestone extras): every scale label, the scale tooltip and every preset
    description carry their world sizes and both factory footprints of config.lua's size_context, every "W x H"
    figure in them is one of those, and each says size_context.reported_phrase before its first footprint (they
    are reported community examples, never measurements). The table itself is checked against its sources: each
    footprint is its R8 section 1 row's figure, and the maps' sizes at every offered scale are
    approvals-data.json's world_size_tiles (APPROVALS 1c)."""
    sc = cfg.get("size_context")
    if not sc:
        return ["config.lua has no size_context table: the labels' size and footprint figures have no data table "
                "(slice extras; D3)"]
    out = []
    phrase = sc.get("reported_phrase") or ""
    fps = [f"{thousands(f['width'])} x {thousands(f['height'])}" for f in sc.get("footprints") or []]
    if len(fps) < 1 or not phrase:
        out.append("config.lua size_context needs reported_phrase and at least one footprint")
    r8_text = r8_text if r8_text is not None else (R8_DOC.read_text(encoding="utf-8") if R8_DOC.exists() else "")
    for f, fig in zip(sc.get("footprints") or [], fps):
        row = next((l for l in r8_text.splitlines() if l.startswith(f"| {f.get('r8_row')} |")), None)
        if row is None:
            out.append(f"size_context footprint {f.get('key')}: R8 holds no row {f.get('r8_row')!r}")
        elif f"{fig} tiles" not in row:
            out.append(f"size_context footprint {f.get('key')} is {fig}, which R8's row {f.get('r8_row')!r} does not "
                       f"give")
        if f.get("source") and row is not None and f["source"] not in row:
            out.append(f"size_context footprint {f.get('key')}: its source {f['source']} is not R8's row's")
    if approvals is None and APPROVALS_DATA.exists():
        approvals = load_json(APPROVALS_DATA)
    ws = (approvals or {}).get("world_size_tiles") or {}
    for mk in cfg["map_order"]:
        m = cfg["maps"][mk]
        for v in (cfg.get("settings") or {}).get("scale", {}).get("allowed_values") or []:
            want = (ws.get(mk) or {}).get(str(v))
            # the approved table stops at scale 6; a scale past it has only the maps' sizes, which size_texts checks
            if want is None and int(v) not in cfg["scales"]["released"]:
                continue
            if want != [m["width_px"] * int(v), m["height_px"] * int(v)]:
                out.append(f"{mk} at scale {v}: config.lua's size {m['width_px'] * int(v)} x {m['height_px'] * int(v)} "
                           f"differs from approvals-data.json world_size_tiles {want} (APPROVALS 1c)")
    for where, text, need, allowed in size_texts(cfg, merged):
        if text is None:
            out.append(f"locale {where} is missing")
            continue
        found = {f"{a} x {b}" for a, b in SIZE_FIGURE_RE.findall(text)}
        for fig in sorted((need | set(fps)) - found):
            out.append(f"locale {where} lacks the figure {fig!r} (D3: world size and both footprints)")
        for fig in sorted(found - allowed - set(fps)):
            out.append(f"locale {where} carries {fig!r}, which is neither one of its world sizes nor a footprint of "
                       f"config.lua's size_context")
        at = [text.find(fig) for fig in fps if fig in text]
        if at and (text.find(phrase) < 0 or text.find(phrase) > min(at)):
            out.append(f"locale {where} does not call its footprints {phrase!r} before giving them (JI-12)")
    return out


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


def control_noise_label_findings(mod=MOD):
    """Control code never builds a [noise-expression] locale key: only the newest version of a map's
    elevation entry keeps its [noise-expression] name, so a message labelled through one would read
    as an unknown key on a world made from an older version. Messages name a map by its preset's
    name (or a per-map message key), which no version changes (ARCHITECTURE.md, "Guards")."""
    from luaparser import astnodes
    out = []
    for p in mod_lua(mod):
        r = rel(p, mod)
        if not (r == "control.lua" or r.startswith("scripts/")):
            continue
        for s, line in lua_strings(parse_lua_file(p), astnodes):
            if s.startswith("noise-expression."):
                out.append(f"{r}:{line}: control code builds the locale key {s!r}...: label a world by its map's "
                           f"preset name, which no version changes")
    return out


def row_locale(mod=MOD):
    cfg = tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    files = sorted((Path(mod) / "locale" / "en").glob("*.cfg"))
    fails = control_noise_label_findings(mod)
    if not files:
        return fails + ["no locale/en/*.cfg file"], ""
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
    fails += scale_label_findings(cfg, merged)
    # extras on: the size context (D3, JI-12), whose table arrives with that milestone
    if cfg.get("size_context") or cfg.get("markers"):
        fails += size_context_findings(cfg, merged)
    # waterways on: the Map type notice names fords among what the preset adds (plan T16; ARCHITECTURE.md,
    # "Map type entries")
    msgs = cfg.get("messages") or {}
    if cfg.get("waterways") and msgs:
        notice = (merged.get(msgs.get("section"), {}) or {}).get((msgs.get("keys") or {}).get("notice"), "")
        if "ford" not in notice.lower():
            fails.append(f"the Map type notice [{msgs.get('section')}] {(msgs.get('keys') or {}).get('notice')} does "
                         f"not name fords among the preset's additions")
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


# The stored-records contract (ARCHITECTURE.md, "Guards"): the per-player warning store has one owner.
GUARDS_FILE = "scripts/guards.lua"


# ------------------------------------------------------------------------------------------------ D33

# D33's strip rule (ARCHITECTURE.md, "D33 surface guard"; milestone ridges): from ridges config.lua's
# preset_keys lists vanilla properties (cliff_elevation, cliffiness, the ore probabilities, beside
# group 0's water slider readers) whose vanilla values Space Age's planets also set themselves, so the
# guard that strips keys from surfaces other than Nauvis may strip one only through guards.lua's
# M.earth_valued (the save's default value names an Earth body, or the key is an Earth per-save key).
D33_PREDICATE = "earth_valued"


def lua_function_body(text, name):
    """The text of `function <name>(...)` up to its closing `end` at column 0, or None."""
    m = re.search(rf"^function {re.escape(name)}\(", text, flags=re.M)
    if not m:
        return None
    end = re.search(r"^end\b", text[m.end():], flags=re.M)
    return text[m.start(): m.end() + (end.end() if end else len(text) - m.end())]


def d33_findings(text):
    """The D33 rule on guards.lua's text: M.earth_valued is defined, reads config.lua's noise prefix and
    tests both the key and the value; and the surface guard, once a milestone adds it, strips a listed key
    only through it."""
    out = []
    pred = lua_function_body(text, f"M.{D33_PREDICATE}")
    if pred is None:
        out.append(f"{GUARDS_FILE} defines no M.{D33_PREDICATE}(key, value), D33's strip rule")
    elif "noise_prefix" not in pred or not re.search(r"\(\s*key\s*\)", pred) or not re.search(r"\(\s*value\s*\)", pred):
        out.append(f"M.{D33_PREDICATE} must test the key and the value against config.lua's noise prefix")
    guard = lua_function_body(text, "M.surface_guard")
    if guard is not None and "preset_keys" in guard and f"{D33_PREDICATE}(" not in guard:
        out.append(f"M.surface_guard strips config.lua's preset_keys without M.{D33_PREDICATE}: on a world that is no "
                   f"Earth map it would blank a planet's own vanilla key (Lakes and Island: cliffiness, "
                   f"cliff_elevation on Space Age's planets; ARCHITECTURE.md, D33)")
    return out


def row_d33(mod=MOD):
    text = read_text_or_none(mod / GUARDS_FILE)
    if text is None:
        return [f"{GUARDS_FILE} is missing"], ""
    f = d33_findings(text)
    has_guard = lua_function_body(text, "M.surface_guard") is not None
    return f, (f"guards.lua's M.{D33_PREDICATE} holds D33's strip rule" +
               ("; M.surface_guard strips through it" if has_guard else "; no surface guard in this tree yet"))


D33_UNRESTRICTED = """function M.surface_guard(surface)
  local default = game.default_map_gen_settings.property_expression_names or {}
  local pen = surface.map_gen_settings.property_expression_names or {}
  for _, key in ipairs(cfg.preset_keys) do
    local v, d = pen[key], default[key]
    if v ~= nil and v ~= "" and d ~= nil and tostring(v) == tostring(d) then
      pen[key] = ""
    end
  end
end
"""


def d33_fixtures():
    """The d33 row's positive controls: a surface guard that compares values alone fails, the same guard
    through M.earth_valued passes, and a guards.lua without the predicate fails."""
    out = []
    real = read_text_or_none(MOD / GUARDS_FILE) or ""
    pred = lua_function_body(real, f"M.{D33_PREDICATE}") or ""
    out.append(("d33: the real guards.lua passes", not d33_findings(real), d33_findings(real)[:1]))
    # the fixture guards stand in for the real one (group 0's spawn-cities ships M.surface_guard, and
    # lua_function_body reads the first definition), or join a guards.lua that has none
    guard = lua_function_body(real, "M.surface_guard")

    def with_guard(text):
        return real.replace(guard, text.rstrip("\n")) if guard else real + "\n" + text
    bad = with_guard(D33_UNRESTRICTED)
    out.append(("d33: a surface guard that compares values alone fails", bool(d33_findings(bad)), ""))
    good = with_guard(D33_UNRESTRICTED.replace(
        "tostring(v) == tostring(d) then", "tostring(v) == tostring(d) and M.earth_valued(key, d) then"))
    out.append(("d33: the guard through M.earth_valued passes", not d33_findings(good), d33_findings(good)[:1]))
    out.append(("d33: a guards.lua without the predicate fails", bool(d33_findings(real.replace(pred, ""))) if pred
                else False, ""))
    return out


# ------------------------------------------------------------------------------------------------ redefinitions

# A file's chunk defines each function once. Lua lets a later `function M.x`, `M.x = function` or
# `local function x` win without a word, so a stale copy a restack carries in silently replaces the
# definition every earlier caller and the text rows read (the second M.kind of ridges' restack
# dropped the base's storage branch; lua_function_body and luacheck both see only one of the two).

def lua_redefinitions(text, where):
    """Every function name one Lua chunk defines twice at its top level: a global or dotted
    `function a.b()`, a method `function a:b()`, an assignment of a function to a dotted name, or a
    `local function x`, each as '<where>:<line>: <name> redefined (first at line <n>)'. A chunk with
    fewer than two `function` keywords defines at most one, so it is never parsed (the generated
    tables hold none)."""
    if text.count("function") < 2:
        return []
    from luaparser import astnodes
    out, seen = [], {}
    for st in tnconfig.parse_lua(text, where).body.body:
        names = []
        if isinstance(st, astnodes.LocalFunction):
            names = ["local " + st.name.id]
        elif isinstance(st, astnodes.Method):
            src = _dotted(st.source, astnodes)
            names = [f"{src}:{st.name.id}"] if src else []
        elif isinstance(st, astnodes.Function):
            names = [_dotted(st.name, astnodes)]
        elif isinstance(st, astnodes.Assign):
            names = [_dotted(t, astnodes) for t, v in zip(st.targets, st.values)
                     if isinstance(v, astnodes.AnonymousFunction)]
        for n in names:
            if not n:
                continue
            line = getattr(st, "line", None) or "?"
            if n in seen:
                out.append(f"{where}:{line}: {n} redefined (first at line {seen[n]}); the later copy wins for every "
                           f"caller")
            else:
                seen[n] = line
    return out


def redefinition_findings(mod=MOD):
    """lua_redefinitions over every Lua file the mod ships."""
    out = []
    for p in mod_lua(mod):
        out += lua_redefinitions(Path(p).read_text(encoding="utf-8"), rel(p, mod))
    return out


def row_redefinitions(mod=MOD):
    f = redefinition_findings(mod)
    return f, f"{len(mod_lua(mod))} Lua files: each top-level function defined once"


def redefinition_fixtures():
    """The redefinition scan on guards.lua's text: the shipped file passes and the walk reads it; a
    second function M.kind (as ridges' restack carried in), a second local function and a function
    assigned over a defined M.kind each fail."""
    guards = read_text_or_none(MOD / GUARDS_FILE) or ""
    walked = any(rel(p, MOD) == GUARDS_FILE for p in mod_lua(MOD))
    real = lua_redefinitions(guards, GUARDS_FILE) if guards else ["guards.lua is missing"]
    out = [("redefinitions: the shipped guards.lua passes and the walk reads it", walked and not real, real[:1])]
    cases = {
        "redefinitions: a second function M.kind fails": "function M.kind(surface)\n  return nil\nend\n",
        "redefinitions: a second local function fails": "local function pen_of(surface)\n  return {}\nend\n",
        "redefinitions: a function assigned over a defined M.kind fails": "M.kind = function()\n  return nil\nend\n",
    }
    for label, extra in cases.items():
        f = lua_redefinitions(guards.replace("\nreturn M", "\n" + extra + "\nreturn M"), GUARDS_FILE)
        out.append((label, bool(f), f[:1]))
    return out


STORED_FIELDS = {"warnings", "sent"}
WARNING_WRITER = "record_warning"


STORED_TABLES = {"storage", "storage.earth", "storage.map_type"}


def storage_contract_findings(mod=MOD, cfg=None):
    """The stored-records contract, statically: storage.earth.warnings and storage.earth.sent (and
    storage.map_type.sent) belong to scripts/guards.lua, so no other file of the mod indexes a field
    named warnings or sent, by dot or by a string key, or replaces storage, storage.earth or
    storage.map_type wholesale (which would drop the stored warnings and counts; other files add or
    change fields of their own); every warning is stored through record_warning, and each call
    names its key as a string literal that is a key of config.lua's messages.keys, so a stored key
    always has its text (a renamed or unknown key fails here)."""
    from luaparser import astnodes
    DOT = astnodes.IndexNotation.DOT
    cfg = cfg if cfg is not None else tnconfig.load(Path(mod) / "prototypes" / "config.lua")
    keys = set(((cfg.get("messages") or {}).get("keys") or {}) or {})
    out = []

    def table_name(t):
        d = _dotted(t, astnodes)
        if d is None and isinstance(t, astnodes.Index) and isinstance(t.idx, astnodes.String):
            base = _dotted(t.value, astnodes)
            k = t.idx.s.decode() if isinstance(t.idx.s, bytes) else t.idx.s
            d = f"{base}.{k}" if base else None
        return d
    for p in mod_lua(mod):
        r = rel(p, mod)
        tree = parse_lua_file(p)
        for n in tnconfig_walk(tree):
            if isinstance(n, astnodes.Assign) and r != GUARDS_FILE:
                for t in n.targets:
                    if table_name(t) in STORED_TABLES:
                        out.append(f"{r}:{getattr(n, 'line', '?')}: replaces {table_name(t)} wholesale, which "
                                   f"{GUARDS_FILE} builds (add or change fields of your own instead)")
            if isinstance(n, astnodes.Index) and r != GUARDS_FILE:
                k = n.idx.id if n.notation == DOT and isinstance(n.idx, astnodes.Name) else (
                    (n.idx.s.decode() if isinstance(n.idx.s, bytes) else n.idx.s)
                    if isinstance(n.idx, astnodes.String) else None)
                if k in STORED_FIELDS:
                    out.append(f"{r}:{getattr(n, 'line', '?')}: indexes {k!r}, a stored field only {GUARDS_FILE} "
                               f"touches (store a warning with guards.{WARNING_WRITER})")
            if isinstance(n, (astnodes.Call, astnodes.Invoke)):
                f = n.func
                name = f.id if isinstance(f, astnodes.Name) else (
                    f.idx.id if isinstance(f, astnodes.Index) and f.notation == DOT and
                    isinstance(f.idx, astnodes.Name) else None)
                if name != WARNING_WRITER:
                    continue
                arg = n.args[0] if n.args else None
                k = (arg.s.decode() if isinstance(arg.s, bytes) else arg.s) if isinstance(arg, astnodes.String) else None
                if k is None:
                    out.append(f"{r}:{getattr(n, 'line', '?')}: {WARNING_WRITER} without a literal message key")
                elif k not in keys:
                    out.append(f"{r}:{getattr(n, 'line', '?')}: {WARNING_WRITER}({k!r}) names no key of config.lua "
                               f"messages.keys")
    return sorted(set(out))


def row_storage(mod=MOD):
    f = storage_contract_findings(mod)
    return f, (f"{len(mod_lua(mod))} Lua files: the stored warning fields only in {GUARDS_FILE}, every "
               f"{WARNING_WRITER} key a messages key")


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

NUM_IN_STRING_RE = re.compile(r"(?<![A-Za-z_\d])(\d+(?:\.\d+)?)")


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


# ------------------------------------------------------------------------------------------------ workflow yaml

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
# The workflows are a closed world: these keys only (latest.yml adds its one concurrency block), one
# job, and exactly the expected steps in order, each run block exactly its commands. Anything else
# can stop a check from failing the run (continue-on-error, if, a trigger filter, an extra step
# writing $GITHUB_ENV, a shell, a working directory or an environment that runs another program, a
# checkout of another repository).
WORKFLOW_KEYS = {"name", "on", "permissions", "jobs"}
LATEST_KEYS = WORKFLOW_KEYS | {"concurrency"}
JOB_KEYS = {"runs-on", "steps"}
STEP_KEYS = {"name", "uses", "with", "run", "env"}
PIP_LINE = "python -m pip install --disable-pip-version-check -r tools/lint/requirements.txt"
LINT_LINE = 'python tools/lint/fetch_linter.py --dest "$env:RUNNER_TEMP\\luacheck" --github-env "$env:GITHUB_ENV"'
TAG_ENV = "${{ github.ref_name }}"
TOKEN_ENV = "${{ secrets.GITHUB_TOKEN }}"
PUBLISH_FILES = ('$files = @(Get-ChildItem -Path dist -File | Where-Object { $_.Name -like "*.zip" -or $_.Name -like '
                 '"*.zip.sha256" } | ForEach-Object { $_.FullName })')
PUBLISH_COUNT = 'if ($files.Count -ne 2) { throw "expected the zip and its .sha256 in dist, found $($files.Count) files" }'
# latest.yml: one concurrency group that never cancels a running publish, and the
# publish block line for line. GitHub runs a run block in pwsh after $ErrorActionPreference = 'stop'
# and ends it with exit $LASTEXITCODE. A native command's non-zero exit throws nothing there (the
# first line pins $PSNativeCommandUseErrorActionPreference to $false), so the failed view of a
# missing release only skips the delete, and each gh call that must succeed is checked on its line.
LATEST_CONCURRENCY = {"group": "latest-release", "cancel-in-progress": "false"}
LATEST_NOTES = ("Rolling dev build of main at $env:GITHUB_SHA, replaced on every push to main. Install: place the "
                "zip in the Factorio mods folder.")
LATEST_PUBLISH = (
    "$PSNativeCommandUseErrorActionPreference = $false",
    '$files = @(Get-ChildItem -Path dist -File | Where-Object { $_.Name -like "*.zip" } | ForEach-Object '
    '{ $_.FullName })',
    'if ($files.Count -ne 1) { throw "expected exactly one zip in dist, found $($files.Count) files" }',
    "gh release view latest --json tagName",
    'if ($LASTEXITCODE -eq 0) { gh release delete latest --cleanup-tag --yes; if ($LASTEXITCODE -ne 0) { throw "gh '
    'release delete failed with exit code $LASTEXITCODE" } }',
    'gh release create latest @files --target "$env:GITHUB_SHA" --prerelease --title latest --notes '
    f'"{LATEST_NOTES}"',
    'if ($LASTEXITCODE -ne 0) { throw "gh release create failed with exit code $LASTEXITCODE" }',
    '$tag = gh api "repos/$env:GITHUB_REPOSITORY/commits/tags/latest" --jq ".sha"',
    'if ($tag -ne $env:GITHUB_SHA) { throw "the latest tag points at $tag, not $env:GITHUB_SHA" }',
)
LATEST_CREATE = 5   # the index of the gh release create line in LATEST_PUBLISH


def _expected_steps(kind, manifest):
    """The one step sequence each workflow may hold. All three
    checkouts keep full history (fetch-depth 0): CI's and latest's so the static append-only row
    reads origin/main and the release tags on the runner, the release's so its tag check can refuse a
    tag whose commit is not on origin/main and its build can compare with the earlier release tags."""
    checkout = {"label": "the full-history checkout", "uses": "actions/checkout@", "with": {"fetch-depth": "0"}}
    common = [
        checkout,
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
    if kind == "latest":
        return common + [
            {"label": "the static checks", "run": ["python tools/earth_test.py static"]},
            {"label": "the zip build", "run": ["python tools/build_zip.py"]},
            {"label": "the publish step", "run": "latest-publish", "env": {"GH_TOKEN": TOKEN_ENV}},
        ]
    return common + [
        {"label": "the tag check", "run": ['python tools/build_zip.py --check-tag "$env:TAG"'], "env": {"TAG": TAG_ENV}},
        {"label": "the static checks", "run": ["python tools/earth_test.py static"]},
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


def latest_publish_problems(name, lines):
    """latest.yml's publish block: exactly the LATEST_PUBLISH lines, and its gh release create parsed
    for a clear message: the tag latest, exactly @files, and only --target "$env:GITHUB_SHA",
    --prerelease, --title latest and --notes (no --draft, --latest, --repo or other flag)."""
    import shlex
    if lines is None or len(lines) != len(LATEST_PUBLISH):
        return [f"{name}: the publish step must be exactly the {len(LATEST_PUBLISH)} lines of DECISIONS 22:34 (the "
                f"native-command pin, the zip list, its count check, the release view, the conditional delete, the "
                f"create, its check, the tag lookup and its check), found {lines}"]
    fails = [f"{name}: publish line {i + 1} must be exactly {want!r}, found {got!r}"
             for i, (got, want) in enumerate(zip(lines, LATEST_PUBLISH)) if got != want]
    try:
        tok = shlex.split(lines[LATEST_CREATE])
    except ValueError as e:
        return fails + [f"{name}: the gh release create line does not parse ({e})"]
    if tok[:4] != ["gh", "release", "create", "latest"]:
        fails.append(f"{name}: the publish command must be gh release create latest (found {tok[:4]})")
    files, flags, i = [], {}, 4
    while i < len(tok):
        t = tok[i]
        if t in ("--target", "--title", "--notes") and i + 1 < len(tok):
            flags[t] = tok[i + 1]
            i += 2
        elif t == "--prerelease":
            flags[t] = True
            i += 1
        elif t.startswith("-"):
            fails.append(f"{name}: gh release create passes {t}; only --target, --prerelease, --title and --notes "
                         f"are allowed")
            i += 1
        else:
            files.append(t)
            i += 1
    if files != ["@files"]:
        fails.append(f"{name}: gh release create must attach exactly @files (the dev zip), not {files}")
    if flags.get("--target") != "$env:GITHUB_SHA" or "--prerelease" not in flags or flags.get("--title") != "latest" \
            or not flags.get("--notes"):
        fails.append(f'{name}: gh release create needs --target "$env:GITHUB_SHA", --prerelease, --title latest and '
                     f'--notes')
    return fails


def structure_problems(name, kind, wf, manifest):
    """The closed-world shape of a workflow: its keys, one job with its keys, and exactly the
    expected steps, each with only its own keys, `with`, `env` and exact run lines."""
    fails = []
    keys = LATEST_KEYS if kind == "latest" else WORKFLOW_KEYS
    extra = sorted(set(wf) - keys)
    if extra:
        fails.append(f"{name}: workflow keys {extra} are not allowed (only {sorted(keys)})")
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
            elif w.get("run") == "latest-publish":
                fails += latest_publish_problems(name, lines)
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
        if r.strip() == "python tools/earth_test.py static":
            order.append("static")
        if r.strip() == "python tools/build_zip.py --release":
            order.append("build")
        if "gh release create" in r:
            if env.get("GH_TOKEN") != "${{ secrets.GITHUB_TOKEN }}":
                fails.append("release.yml: gh must use the workflow's own GITHUB_TOKEN")
            if "*.zip" not in r or "*.zip.sha256" not in r:
                fails.append("release.yml: the release must attach the zip and its .sha256")
            order.append("publish")
    if order != ["tag", "static", "build", "publish"]:
        fails.append(f"release.yml: steps must be the tag check, the static rows, build_zip.py --release, then gh "
                     f"release create (found {order})")
    return fails


def check_latest(text, manifest):
    """latest.yml: every push to main runs the static rows, builds the dev zip and
    replaces the rolling latest pre-release with it, as strictly shaped as release.yml."""
    try:
        wf = parse_yaml(text)
    except YamlError as e:
        return [f"latest.yml: {e}"]
    fails, steps, runs, secrets = _common_workflow("latest.yml", wf, text, manifest)
    fails += structure_problems("latest.yml", "latest", wf, manifest)
    on = wf.get("on")
    if not (isinstance(on, dict) and set(on) == {"push"} and isinstance(on["push"], dict)
            and set(on["push"]) == {"branches"} and on["push"]["branches"] == ["main"]):
        fails.append(f"latest.yml: must trigger only on a push to branches [main] (found {on})")
    if wf.get("permissions") != {"contents": "write"}:
        fails.append("latest.yml: permissions must be exactly contents: write")
    if wf.get("concurrency") != LATEST_CONCURRENCY:
        fails.append(f"latest.yml: concurrency must be exactly group: latest-release, cancel-in-progress: false, so "
                     f"only the newest push publishes and no running publish is cut short (found "
                     f"{wf.get('concurrency')})")
    if any(r.startswith("python tools/build_zip.py --release") for r in runs):
        fails.append("latest.yml: builds the release zip; latest carries the dev zip CI uploads")
    order = []
    for s in steps:
        r = s.get("run") or ""
        env = s.get("env") or {}
        if r.strip() == "python tools/earth_test.py static":
            order.append("static")
        if r.strip() == "python tools/build_zip.py":
            order.append("build")
        if "gh release create" in r:
            if env.get("GH_TOKEN") != TOKEN_ENV:
                fails.append("latest.yml: gh must use the workflow's own GITHUB_TOKEN")
            order.append("publish")
    if order != ["static", "build", "publish"]:
        fails.append(f"latest.yml: steps must be the static checks, build_zip.py, then the publish step, so a broken "
                     f"main is never published (found {order})")
    return fails


def workflow_findings(gh_dir=REPO / ".github" / "workflows", lint_dir=LINT):
    manifest = lint_manifest(lint_dir)
    out = []
    for name, fn in (("ci.yml", check_ci), ("release.yml", check_release), ("latest.yml", check_latest)):
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
    return f, "ci.yml and release.yml against DECISIONS 12:35, latest.yml against DECISIONS 22:34"


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
    # the coast fits (europe-coast on): every file of each map's fit folder re-hashes to its
    # PROVENANCE.md row, and every row names a file that exists
    fits = repo / "data-src" / "fits"
    for d in sorted(p for p in fits.iterdir() if p.is_dir()) if fits.is_dir() else []:
        if not (d / "PROVENANCE.md").exists():
            out.append(f"data-src/fits/{d.name} has no PROVENANCE.md")
            continue
        fprov = provenance_hashes(d / "PROVENANCE.md")
        names = sorted(p.name for p in d.iterdir() if p.is_file() and p.name != "PROVENANCE.md")
        for name in names:
            if name not in fprov:
                out.append(f"data-src/fits/{d.name}/{name} is not in its PROVENANCE.md")
            elif sha256_file(d / name) != fprov[name]:
                out.append(f"data-src/fits/{d.name}/{name} sha256 differs from its PROVENANCE.md")
        for name in fprov:
            if name not in names:
                out.append(f"data-src/fits/{d.name}/PROVENANCE.md lists {name}, which is missing")
    for key in (cfg.get("geography") or {}):
        if not (fits / key / "PROVENANCE.md").exists():
            out.append(f"config.lua gives {key} a geography, but data-src/fits/{key}/ holds no provenance")
    # the waterways (milestone waterways): every file re-hashes to its PROVENANCE.md row, and each map's
    # rivers are APPROVALS 7's adopted rows with their class (JI-03)
    ww = repo / "data-src" / "waterways"
    if ww.is_dir():
        wprov = provenance_hashes(ww / "PROVENANCE.md") if (ww / "PROVENANCE.md").exists() else {}
        if not wprov:
            out.append("data-src/waterways has no PROVENANCE.md table")
        names = sorted(p.name for p in ww.iterdir() if p.is_file() and p.name != "PROVENANCE.md")
        for name in names:
            if name not in wprov:
                out.append(f"data-src/waterways/{name} is not in its PROVENANCE.md")
            elif sha256_file(ww / name) != wprov[name]:
                out.append(f"data-src/waterways/{name} sha256 differs from its PROVENANCE.md")
        for name in wprov:
            if name not in names:
                out.append(f"data-src/waterways/PROVENANCE.md lists {name}, which is missing")
        out += waterway_river_findings(repo, cfg)
        out += waterway_basin_findings(repo, cfg)
    elif cfg.get("waterways"):
        out.append("config.lua has a waterways group, but data-src/waterways/ is missing")
    # the palm digest (climate-tiles): config.lua's record of tools/build_palms.py's digest is well formed
    if ((cfg.get("tiles") or {}).get("palm") or {}).get("digest"):
        import build_palms
        out += [f"palm digest: {x}" for x in build_palms.check(cfg)]
    out += bandfix_data_findings(repo, cfg)
    return out


def bandfix_data_findings(repo, cfg):
    """The band-fix tables (milestone coast-band-fix): data-src/bandfix/ re-hashes to its PROVENANCE.md; each
    map config.lua's bandfix.tables lists has a manifest whose recorded inputs are the committed fit
    checkpoint, rasters, waterway manifest and bandfix group, and whose generated files are committed with
    the recorded sha256; every map bandfix.maps lists has tables, Atlantic never does, and each tables
    map's newest geography version (the one its preset names) is one its tables serve."""
    import hashlib
    out = []
    B = cfg.get("bandfix")
    bd = repo / "data-src" / "bandfix"
    if not B:
        return out
    if not bd.is_dir():
        return ["config.lua has a bandfix group, but data-src/bandfix/ is missing"]
    bprov = provenance_hashes(bd / "PROVENANCE.md") if (bd / "PROVENANCE.md").exists() else {}
    if not bprov:
        out.append("data-src/bandfix has no PROVENANCE.md table")
    names = sorted(p.name for p in bd.iterdir() if p.is_file() and p.name != "PROVENANCE.md")
    for name in names:
        if name not in bprov:
            out.append(f"data-src/bandfix/{name} is not in its PROVENANCE.md")
        elif sha256_file(bd / name) != bprov[name]:
            out.append(f"data-src/bandfix/{name} sha256 differs from its PROVENANCE.md")
    for name in bprov:
        if name not in names:
            out.append(f"data-src/bandfix/PROVENANCE.md lists {name}, which is missing")
    tables = B.get("tables") or {}
    for mk in B.get("maps") or []:
        if mk not in tables:
            out.append(f"config.lua bandfix.maps lists {mk}, which has no K+ tables (bandfix.tables)")
    checked = B.get("checks") or {}
    for mk in sorted(set(B.get("maps") or []) | set(tables)):
        if mk not in checked:
            out.append(f"config.lua lists {mk} for the band fix, which runs no flip check (bandfix.checks; Atlantic "
                       f"was never priced, S12)")
    digest = tnconfig.bandfix_digest(B)
    for mk, spec in tables.items():
        mp = bd / f"manifest-{mk}.json"
        if not mp.exists():
            out.append(f"config.lua bandfix.tables lists {mk}, but data-src/bandfix/manifest-{mk}.json is missing")
            continue
        M = load_json(mp)
        g = tnconfig.geography(cfg).get(mk) or {}
        if g.get("geo_id") not in (spec.get("geographies") or []):
            out.append(f"{mk}'s geography {g.get('geo_id')} is not one its band-fix tables serve "
                       f"({spec.get('geographies')}): re-emit the tables and list it")
        for row in (B.get("generations") or {}).get(mk) or []:
            lost = [i for i in row.get("geographies") or [] if i not in (spec.get("geographies") or [])]
            if lost:
                out.append(f"bandfix.generations.{mk} serves {lost}, which bandfix.tables.{mk} does not list")
            if not int(B["version"]) < int(row.get("version", 0)):
                out.append(f"bandfix.generations.{mk} holds version {row.get('version')}: a generation is above "
                           f"bandfix.version {B['version']}")
        inp = M.get("inputs") or {}
        ck = repo / (inp.get("checkpoint") or "-")
        fit = load_json(repo / "data-src" / "fits" / mk / "fit.json")
        want_ck = f"data-src/fits/{mk}/{fit['bodies']['geo']['checkpoint']}"
        if inp.get("checkpoint") != want_ck or not ck.exists() or sha256_file(ck) != inp.get("checkpoint_sha256"):
            out.append(f"manifest-{mk}.json was built from {inp.get('checkpoint')}, not the shipped fit {want_ck}")
        em = repo / "data-src" / "earthmaps"
        for kind, field in (("land", "land_sha256"), ("thinwater", "thinwater_sha256")):
            if sha256_file(em / f"{mk}-{kind}.png") != inp.get(field):
                out.append(f"manifest-{mk}.json was built from another {mk}-{kind}.png")
        if inp.get("bandfix_config_sha256") != digest:
            out.append(f"manifest-{mk}.json was built under another config.lua bandfix group: re-emit the tables")
        ww = repo / "data-src" / "waterways" / f"manifest-{mk}.json"
        files = [M.get("shared") or {}] + list((M.get("scales") or {}).values())
        for rec in files:
            f = repo / (rec.get("file") or "-")
            if not f.exists():
                out.append(f"manifest-{mk}.json names {rec.get('file')}, which is missing")
            elif sha256_file(f) != rec.get("sha256"):
                out.append(f"{rec.get('file')} sha256 differs from manifest-{mk}.json (rerun build_geo.py emit "
                           f"--bandfix)")
        for s, rec in (M.get("scales") or {}).items():
            if ww.exists() and rec.get("waterway_manifest_sha256") != sha256_file(ww):
                out.append(f"manifest-{mk}.json scale {s} was built from another waterway manifest")
        have = sorted(int(s) for s in (M.get("scales") or {}))
        if have != sorted(int(s) for s in cfg["scales"]["exact_coast"]):
            out.append(f"manifest-{mk}.json holds scales {have}, not every scale Exact coastlines serves")
    return out


def waterway_river_findings(repo, cfg):
    """T16 (JI-03): each map's rivers in data-src/waterways/<map>.json are the adopted rows of APPROVALS 7
    in approvals-data.json, in order and with their major or minor class; a cut (the plan's waterway cut
    order, section 6.3) only carves fewer rivers from the top of that list at a scale, never fewer than
    the map's rows of Europe's block (Europe keeps all 22), and only raises the tolerance."""
    repo = Path(repo)
    out = []
    A = load_json(repo / "data-src" / "approvals" / "approvals-data.json")
    w = cfg.get("waterways") or {}
    tol = w.get("tolerance_tiles") or []
    for key in cfg.get("map_order", []):
        p = repo / "data-src" / "waterways" / f"{key}.json"
        if not p.exists():
            out.append(f"data-src/waterways/{key}.json is missing")
            continue
        D = load_json(p)
        want = [(r["name"], r["class"]) for r in A["rivers"][key] if r["adopted"]]
        have = [(r.get("name"), r.get("class")) for r in D.get("rivers", [])]
        if have != want:
            out.append(f"data-src/waterways/{key}.json rivers {[n for n, _ in have]} are not APPROVALS 7's adopted rows "
                       f"{[n for n, _ in want]} in order with their class")
        floor = sum(1 for r in A["rivers"][key] if r["adopted"] and r.get("block") == "europe")
        for s, c in sorted((D.get("cuts") or {}).items()):
            n = c.get("rivers", len(have))
            if not isinstance(n, int) or n < floor or n > len(have):
                out.append(f"data-src/waterways/{key}.json cuts scale {s} to {n} rivers: a cut keeps between "
                           f"Europe's {floor} and all {len(have)}")
            t_ = c.get("tolerance_tiles")
            offered = [int(x) for x in cfg["scales"]["values"]]
            base = tol[offered.index(int(s))] if str(s).isdigit() and int(s) in offered else None
            if t_ is not None and base is not None and t_ < base:
                out.append(f"data-src/waterways/{key}.json lowers scale {s}'s tolerance to {t_} below config.lua's {base}")
    return out


def lua_set_strings(text):
    """The S.<set> = "..." strings of a generated waterway file, with Lua's \\z continuations applied."""
    out = {}
    for m in re.finditer(r'^S\.(\w+) = "', text, re.M):
        i, buf = m.end(), []
        while text[i] != '"':
            if text[i] == "\\" and text[i + 1] == "z":
                i += 2
                while text[i] in " \t\r\n":
                    i += 1
                continue
            buf.append(text[i])
            i += 1
        out[m.group(1)] = "".join(buf)
    return out


def waterway_basin_findings(repo, cfg):
    """A canal's turning basins lie in its map's canal set, carved only with canals on, and every other
    basin in the waterway set: a canal basin in the waterway set would open the isthmus with canals
    off (each manifest's basins against its generated file)."""
    repo = Path(repo)
    out = []
    for key in cfg.get("map_order", []):
        p = repo / "data-src" / "waterways" / f"manifest-{key}.json"
        if not p.exists():
            continue
        for s, rec in sorted((load_json(p).get("scales") or {}).items()):
            f = repo / str(rec.get("file", ""))
            if not f.is_file():
                out.append(f"manifest-{key}.json scale {s} names {rec.get('file')}, which is missing")
                continue
            sets = lua_set_strings(f.read_text(encoding="utf-8"))
            reach = cfg["waterways"]["natural"]["basin"]["half_length_tiles"]
            for b in rec.get("basins") or []:
                # a basin is a capsule along its course, in its feature's frame
                (cx, cy), (tx, ty) = b["centre"], b["tangent"]
                x, y = ("X", "Y") if b.get("kind") == "river" else ("XP", "YP")
                term = f"seg({x}, {y}, {float(cx - tx * reach):.9g}, {float(cy - ty * reach):.9g}, "
                home, other = ("canals", "ww") if b.get("kind") == "canal" else ("ww", "canals")
                if term not in sets.get(home, "") or term in sets.get(other, ""):
                    out.append(f"{key} scale {s}: the {b.get('kind')} basin of {b.get('feature')} at {b['centre']} is not "
                               f"in the {home} set alone")
    return out


def row_data_src(repo=REPO):
    f = data_src_findings(repo)
    return f, "provenance sha256, reference JSON png hashes and sizes, config.lua against the reference JSON"


# ------------------------------------------------------------------------------------------------ frozen, budgets

THRESHOLD_KEY_RE = re.compile(r"(limit|cap|threshold|allocation|allowance|ceiling|bar)$", re.I)


def config_frozen_findings(cfg, fz, registry=None):
    """config.lua against tests/frozen.json (design constraint 2), statically: the file and every
    record keep the tnfrozen contract against the runner's milestone registry (each field present and
    well formed, the dump label one that a registry entry assigns and the record's milestone could have
    produced, so no record can switch the gate's frozen row off for its body); every Earth noise
    body config.lua defines, released or a firewall body, is registered, the placeholder's names and
    the Map type fallbacks that mirror a startup setting excepted and never registered (a frozen
    fallback is registered like every body). The region layer's row names count (tnconfig composes
    them from config.lua's stems and the table's ids), so a table row added without a freeze fails
    here. The gate's frozen row checks the dumped bodies and their hashes; this row needs no game, so
    CI runs it too. `registry` defaults to the runner's,
    read statically (fail closed)."""
    if registry is None:
        try:
            registry = tnfrozen.runner_registry()
        except tnfrozen.RegistryUnreadable as e:
            return [f"the runner's slice registry is unreadable: {e} (fail closed)"]
    out = list(tnfrozen.file_problems(fz, registry))
    ph = set(tnconfig.placeholder_names(cfg))
    fb = set(tnconfig.exempt_fallback_names(cfg))
    bodies = fz.get("bodies") if isinstance(fz, dict) and isinstance(fz.get("bodies"), dict) else {}
    # the live mask (tnfrozen's optional mask) belongs to the Oil Rig's offshore-oil wrappers only
    # (resources-enemies), and they always carry it
    offshore = ((cfg.get("resources") or {}).get("offshore")) or {}
    live = {n for n in (offshore.get("p"), offshore.get("r")) if n}
    for name in bodies:
        rec = bodies[name] if isinstance(bodies[name], dict) else {}
        if (rec.get("mask") == "live") != (name in live):
            out.append(f"tests/frozen.json {name}: mask {rec.get('mask')!r}; only the Oil Rig's wrappers {sorted(live)} "
                       f"carry the live mask, and they always do")
        if name in ph:
            out.append(f"placeholder name {name} is registered in tests/frozen.json")
        if name in fb:
            out.append(f"Map type fallback {name} mirrors a startup setting and is registered in tests/frozen.json "
                       f"(U3: such fallbacks never are)")
    for name in tnconfig.unregistered_names(cfg, bodies):
        out.append(f"config.lua defines the Earth body {name}, which tests/frozen.json does not register: run python "
                   f"tools/earth_test.py freeze (sacred constraint 2)")
    return out


def frozen_static_findings(repo=REPO):
    repo = Path(repo)
    out = []
    cfg = tnconfig.load(repo / "terra-nauvis" / "prototypes" / "config.lua")
    fz = load_json(repo / "tests" / "frozen.json")
    try:
        registry = tnfrozen.runner_registry(repo / "tools" / "earth_test.py")
    except tnfrozen.RegistryUnreadable as e:
        out.append(f"the runner's slice registry is unreadable: {e} (fail closed)")
    else:
        out += config_frozen_findings(cfg, fz, registry)
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


def map_suffixes(name, maps):
    """The map keys a noise name carries as its suffix, before an optional version suffix
    (tn_<name>_<map> or tn_<name>_<map>_v<n>)."""
    return [m for m in maps if re.search(r"_" + re.escape(m) + r"(?:_v\d+)?$", name)]


def fallback_findings(cfg):
    """The Map type fallbacks statically, for every geography version of every map (older versions'
    entries stay defined, so their fallbacks do too): each is a key that version's preset bakes
    (tnconfig.baked_names, the mirror of presets.lua) and a preset key, a map-qualified one carries
    its map's key as its suffix (before an optional version suffix) and a shared one carries none
    (one fallback holds one value, so a value that differs by map needs a map-qualified name), none
    is a firewall body, a frozen one is a released body (so tests/frozen.json registers it and no
    later version moves it) and one that mirrors a setting is not (U3's one exemption), and every
    version lists its own. The gate's dump facts check each fallback's value against what its
    version's preset bakes, at default settings and at T11's settings B."""
    out = []
    keys = set(cfg.get("preset_keys") or [])
    fw = set(tnconfig.firewall_names(cfg))
    maps = tnconfig.map_keys(cfg)
    released = set(tnconfig.release_names(cfg))
    for key, versions in tnconfig.geography_versions(cfg).items():
        for i, v in enumerate(versions, 1):
            where = f"{key} version {i} ({v['entry']})"
            if not v["fallbacks"]:
                out.append(f"config.lua gives {where} no Map type fallbacks (its entry reads the scale at least)")
            baked = tnconfig.baked_names(cfg, key, v, 1)
            for e in v["fallbacks"]:
                n = e["name"]
                if n not in keys:
                    out.append(f"fallback {n} of {where} is not a preset key (preset_keys): no preset bakes it")
                if n not in baked:
                    out.append(f"fallback {n} of {where} is no key that version's preset bakes, so nothing values it")
                suffixed = map_suffixes(n, maps)
                if e["map_qualified"] and suffixed != [key]:
                    out.append(f"fallback {n} is marked map-qualified but does not end in _{key} (or _{key}_v<n>)")
                if not e["map_qualified"] and suffixed:
                    out.append(f"fallback {n} is shared but ends in a map key {suffixed}: one fallback holds one value")
                if n in fw:
                    out.append(f"fallback {n} is a firewall body")
                if e.get("frozen") and n not in released:
                    out.append(f"frozen fallback {n} is in no release_registry row: it would never be registered")
                if not e.get("frozen") and n in released:
                    out.append(f"fallback {n} mirrors a startup setting but is a released body (U3)")
    # a map's frame (config.lua frames, 0.3.0): its city offset names, which no preset bakes, frozen and released
    for key, fr in tnconfig.frames(cfg).items():
        for e in fr["fallbacks"]:
            n = e["name"]
            if n not in keys:
                out.append(f"frame fallback {n} of {key} is not a preset key (preset_keys)")
            if map_suffixes(n, maps) != [key]:
                out.append(f"frame fallback {n} does not end in _{key} (or _{key}_v<n>)")
            if n in fw:
                out.append(f"frame fallback {n} is a firewall body")
            if n not in released:
                out.append(f"frame fallback {n} is in no release_registry row: it would never be registered")
    return out


def row_fallbacks(repo=REPO):
    cfg = tnconfig.load(Path(repo) / "terra-nauvis" / "prototypes" / "config.lua")
    f = fallback_findings(cfg)
    n = len(tnconfig.fallback_names(cfg))
    nv = sum(len(v) for v in tnconfig.geography_versions(cfg).values())
    return f, (f"{n} Map type fallbacks ({len(tnconfig.frozen_fallback_names(cfg))} frozen) over {nv} geography "
               f"version(s): each a key its version's preset bakes, map-qualified by suffix, none a firewall body, "
               f"frozen ones released")


def row_frozen(repo=REPO):
    f = frozen_static_findings(repo)
    fz = load_json(Path(repo) / "tests" / "frozen.json")
    return f, (f"{len(fz.get('bodies', {}))} registered bodies, every record held to the tnfrozen contract against "
               f"the runner's slice registry; budgets.json holds measured values only")


# ------------------------------------------------------------------------------------------------ append-only
#
# What saves and released zips hold never moves: registered bodies (design constraint 2), the tn_map
# and tn_geo ids a preset bakes, and the message keys stored warnings name. The reference is every
# landed state the checkout can see, main and origin/main (and origin/<base> on a pull request's
# runner, which ci.yml checks out with full history) and every v<x.y.z> release tag, read from git,
# and the check fails closed: no ref that resolves, or a ref that resolves without a readable file,
# fails the row instead of comparing against an empty registry. A group's earlier milestones land their
# registries before main does, in their suite manifests' frozen snapshots (tnfrozen.snapshot), which
# the row holds the registry to as well.
REFERENCE_REFS = ("main", "origin/main")
GIT_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
RELEASE_TAG_RE = re.compile(r"v\d+\.\d+\.\d+")


class ReferenceUnreadable(RuntimeError):
    pass


def release_tag_refs(repo=REPO):
    """Every release tag the checkout holds (v<x.y.z>) as refs/tags/<tag>, sorted. A push to main is
    compared with main itself, so only the releases keep a registered record fixed against a commit
    that reaches main without a pull request. Raises ReferenceUnreadable when git cannot list tags."""
    cp = subprocess.run(["git", "tag", "--list", "v*"], cwd=str(repo), capture_output=True, text=True)
    if cp.returncode != 0:
        raise ReferenceUnreadable(f"git tag --list failed ({(cp.stderr or '').strip()[:200]}) (fail closed)")
    return [f"refs/tags/{t}" for t in sorted(cp.stdout.split()) if RELEASE_TAG_RE.fullmatch(t)]


def reference_refs():
    # A tag's commit can sit behind main when the release runs, and main may rightly hold more by then. --check-tag
    # holds the tag to main's history; here a tag run compares with the earlier releases alone.
    refs = [] if os.environ.get("GITHUB_REF_TYPE") == "tag" else list(REFERENCE_REFS)
    base = os.environ.get("GITHUB_BASE_REF") or ""
    if base and GIT_REF_RE.fullmatch(base) and ".." not in base and f"origin/{base}" not in refs:
        refs.append(f"origin/{base}")
    return refs + [t for t in release_tag_refs() if t not in refs]


def git_ref_commit(ref, repo=REPO):
    """The commit a ref names, or None when it does not resolve."""
    cp = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=str(repo),
                        capture_output=True, text=True)
    sha = (cp.stdout or "").strip()
    return sha if cp.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def reference_files(path, repo=REPO, refs=None):
    """{ref: (commit, text)} of the repo-relative POSIX `path` at every reference ref that resolves.
    Fails closed: raises ReferenceUnreadable when no reference ref resolves, or when a ref that
    resolves holds no readable `path`."""
    refs = list(refs) if refs is not None else reference_refs()
    out, absent = {}, []
    for ref in refs:
        sha = git_ref_commit(ref, repo)
        if sha is None:
            absent.append(ref)
            continue
        cp = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=str(repo), capture_output=True)
        if cp.returncode != 0:
            why = (cp.stderr or b"").decode("utf-8", "replace").strip()[:200]
            raise ReferenceUnreadable(f"git show {ref}:{path} failed ({why}); the append-only check cannot read its "
                                      f"reference (fail closed)")
        try:
            out[ref] = (sha, cp.stdout.decode("utf-8"))
        except UnicodeDecodeError as e:
            raise ReferenceUnreadable(f"{ref}:{path} is not UTF-8 ({e}) (fail closed)") from e
    if not out:
        raise ReferenceUnreadable(f"none of the reference refs {refs} resolves; fetch origin or check out with full "
                                  f"history (fail closed)")
    return out


def frozen_union(registries, moves=None):
    """The union of the reference refs' frozen.json registries, {"bodies": {...}}, and the problems
    (a registry that is not tn-frozen/1, or two refs registering one name with different records:
    whole records compare, so a dump label, type, milestone or date the refs disagree on fails like a
    hash; two hashes the waiver both excuses, `moves`, are a stale local main, not a disagreement)."""
    union, probs, where = {}, [], {}
    for ref, fz in sorted(registries.items()):
        if not isinstance(fz, dict) or fz.get("format") != tnfrozen.FORMAT or not isinstance(fz.get("bodies"), dict):
            probs.append(f"{ref}:tests/frozen.json is not tn-frozen/1 with a bodies table (fail closed)")
            continue
        for name, rec in fz["bodies"].items():
            if not isinstance(rec, dict):
                probs.append(f"{ref}:tests/frozen.json {name} is not a record (fail closed)")
                rec = {}
            if name in union:
                diff = tnfrozen.record_changes(rec, union[name])
                if diff and not (tnfrozen.moved(moves, name, rec.get("sha256")) and
                                 tnfrozen.moved(moves, name, union[name].get("sha256"))):
                    probs.append(f"{name}: {where[name]} and {ref} register different records ({diff})")
                continue
            union[name] = rec
            where[name] = ref
    return {"bodies": union, "where": where}, probs


def _as_dict(v):
    return v if isinstance(v, dict) else {}


def append_only_findings(work_fz, work_cfg, refs, moves=None):
    """What the working tree dropped or changed of the persisted entries its references hold. `refs`
    maps a ref to {"frozen": <its tests/frozen.json>, "cfg": <its config table>}. Append-only:
    every registered body's whole record (type, sha256, the dump label the gate reads it from, milestone
    and date) and the field list the hashes cover, every tn_map id (maps.<key>.id), every tn_geo id
    with its map (release_registry), and every stored message key with its locale key and section.
    `moves` (tnfrozen.active_moves) excuses a record at its exact hash and a retired tn_geo id."""
    out = []
    union, probs = frozen_union({ref: d.get("frozen") for ref, d in refs.items()}, moves)
    out += probs
    bodies = _as_dict(_as_dict(work_fz).get("bodies"))
    for name, rec in sorted(union["bodies"].items()):
        ref = union["where"][name]
        mine = bodies.get(name)
        if tnfrozen.moved(moves, name, rec.get("sha256")):
            continue
        if name not in bodies:
            out.append(f"{name} is registered on {ref} but missing from tests/frozen.json (append-only)")
            continue
        diff = tnfrozen.record_changes(mine, rec)
        if diff:
            out.append(f"{name}: tests/frozen.json changed the record {ref} registers, in {diff} (append-only: a "
                       f"record never changes in place; ship a change under the next _v<n>)")
    for ref, d in sorted(refs.items()):
        rfz = _as_dict(d.get("frozen"))
        if "hash_fields" in rfz and rfz.get("hash_fields") != _as_dict(work_fz).get("hash_fields"):
            out.append(f"tests/frozen.json hash_fields is {rfz.get('hash_fields')!r} on {ref} and "
                       f"{_as_dict(work_fz).get('hash_fields')!r} here: the registered hashes cover the landed fields")
    wcfg = work_cfg or {}
    wmaps = _as_dict(wcfg.get("maps"))
    try:
        wgeo = tnconfig.geo_maps(wcfg)
    except tnconfig.ConfigError as e:
        out.append(f"config.lua release_registry does not resolve tn_geo ids here: {e}")
        wgeo = {}
    wmsg = _as_dict(wcfg.get("messages"))
    wkeys = _as_dict(wmsg.get("keys"))
    retired = set(_as_dict(moves).get("geographies") or [])
    for ref, d in sorted(refs.items()):
        rc = _as_dict(d.get("cfg"))
        for key, m in sorted(_as_dict(rc.get("maps")).items()):
            rid = m.get("id") if isinstance(m, dict) else None
            if rid is None:
                continue
            got = wmaps.get(key).get("id") if isinstance(wmaps.get(key), dict) else None
            if got != rid:
                out.append(f"config.lua maps.{key}.id is {rid!r} on {ref} and {got!r} here: a tn_map id saves hold "
                           f"never changes")
        for r in rc.get("release_registry") or []:
            if not isinstance(r, dict) or "geography" not in r:
                continue
            if r["geography"] in retired and r["geography"] not in wgeo:
                continue
            if wgeo.get(r["geography"]) != r.get("map"):
                out.append(f"config.lua release_registry: tn_geo id {r['geography']!r} names map {r.get('map')!r} on "
                           f"{ref} and {wgeo.get(r['geography'])!r} here: a tn_geo id saves hold never moves")
        rmsg = _as_dict(rc.get("messages"))
        rkeys = _as_dict(rmsg.get("keys"))
        if rkeys and rmsg.get("section") != wmsg.get("section"):
            out.append(f"config.lua messages.section is {rmsg.get('section')!r} on {ref} and {wmsg.get('section')!r} "
                       f"here: stored warnings name their text through it")
        for k, v in sorted(rkeys.items()):
            if wkeys.get(k) != v:
                out.append(f"config.lua messages.keys.{k} is {v!r} on {ref} and {wkeys.get(k)!r} here: a key stored "
                           f"warnings can hold is never removed or renamed")
    return sorted(set(out))


def append_only_reference(repo=REPO, refs=None):
    """The reference refs' frozen.json and config.lua as append_only_findings reads them, and the
    commits read. Raises ReferenceUnreadable (fail closed)."""
    fzs = reference_files("tests/frozen.json", repo, refs)
    cfgs = reference_files("terra-nauvis/prototypes/config.lua", repo, refs)
    out = {}
    for ref, (sha, text) in fzs.items():
        if ref not in cfgs or cfgs[ref][0] != sha:
            raise ReferenceUnreadable(f"{ref} moved while the check read it (fail closed)")
        try:
            out[ref] = {"frozen": json.loads(text), "cfg": tnconfig.loads(cfgs[ref][1], f"{ref}:config.lua")}
        except (ValueError, tnconfig.ConfigError) as e:
            raise ReferenceUnreadable(f"{ref}: a reference file does not parse ({e}) (fail closed)") from e
    return out, {ref: sha for ref, (sha, _) in fzs.items()}


# The data a registered body is built from (design constraint 2; ARCHITECTURE.md, "Release
# versioning policy"). The gate's frozen row hashes the dumped bodies and needs the game; these
# static rules hold the same line for a change that lands through CI alone (a regenerated file, an
# edited constant or city row). Once a reference holds a release_registry row, every value it holds
# at one of these config.lua paths keeps its value here: a table may gain keys, a "versions" list may
# gain entries at its end, and any other value must be equal. The landed rows themselves, every file
# a landed row or geography version names, every map table of prototypes/tables/ and the allowed
# values of every setting a geography version names (RELEASE_SETTING_REFS) are fixed too.
# The expression code (prototypes/expressions/) is code, not data: its bodies change only through
# the dump, which the gate's frozen row reads.
RELEASE_CONFIG_PATHS = (("coordinates",), ("number_format",), ("coast",), ("spawn",), ("keys",),
                        ("start_mask", "versions"), ("geography", "*", "versions"), ("maps", "*"))
RELEASE_CONFIG_SKIP = ("display",)  # maps.<key>.display: the map's locale name, which no body reads
RELEASE_TABLES_DIR = "terra-nauvis/prototypes/tables/"
# A setting's allowed values that a registered body is built from, reached through a geography
# version's spawn record (spawn.city_setting): the city fold's random pick is "% n + 1" over the
# list's cities and its if-chains follow the list's order, presets bake a city as its position in
# the list, and control code reads that number back through the same list. So the list is fixed
# exactly: no reorder and no append (an append changes n, so every random-city save moves).
RELEASE_SETTING_REFS = (("spawn", "city_setting"),)


def release_settings(cfg):
    """{settings key: [where it is named]} for every setting a geography version names through a
    RELEASE_SETTING_REFS field."""
    out = {}
    for gk, g in sorted(_as_dict(cfg.get("geography")).items()):
        for i, v in enumerate(_as_dict(g).get("versions") or []):
            for rec, field in RELEASE_SETTING_REFS:
                key = _as_dict(_as_dict(v).get(rec)).get(field)
                if key is not None:
                    out.setdefault(key, []).append(f"geography.{gk}.versions[{i + 1}].{rec}.{field}")
    return out


def _norm_bytes(b):
    return b.replace(b"\r\n", b"\n")


def _release_value_findings(ref_v, work_v, where, ref, collapse=None):
    if isinstance(ref_v, dict):
        if not isinstance(work_v, dict):
            return [f"{where} is a table on {ref} and {work_v!r} here (a value a registered body is built from)"]
        out = []
        for k in sorted(ref_v, key=str):
            if k in RELEASE_CONFIG_SKIP and where.startswith("config.lua maps."):
                continue
            if k not in work_v:
                out.append(f"{where}.{k} is on {ref} and gone here (a value a registered body is built from)")
                continue
            out += _release_value_findings(ref_v[k], work_v[k], f"{where}.{k}", ref, collapse)
        return out
    # 0.3.0's collapse (tests/collapsed.json) took the versions it lists out of geography.<map>.versions: the rest of
    # the landed list still leads the list here, unchanged
    if collapse and isinstance(ref_v, list) and where.startswith("config.lua geography.") and \
            where.endswith(".versions"):
        gone = set(collapse.get("versions") or [])
        ref_v = [v for v in ref_v if not (isinstance(v, dict) and v.get("geo_id") in gone)]
    # A list of versions, or of the tn_geo ids a term applies to (coast.warp.geographies and the edge band's fold list),
    # only grows: a new entry reaches only the new version, which is how the next geography version keeps its map's coast
    # warp.
    if isinstance(ref_v, list) and where.endswith((".versions", ".geographies", ".fold_geographies")):
        if not isinstance(work_v, list) or len(work_v) < len(ref_v):
            return [f"{where} lost entries {ref} holds (versions are append-only)"]
        return [f"{where}[{i + 1}] changed in place against {ref} (a landed version never changes; add the next "
                f"version)" for i, (a, b) in enumerate(zip(ref_v, work_v)) if a != b]
    if ref_v != work_v:
        return [f"{where} is {json.dumps(ref_v)[:80]} on {ref} and {json.dumps(work_v)[:80]} here: a registered body "
                f"is built from it, so it never changes in place (ship the change under the next _v<n>)"]
    return []


def _release_paths(cfg, path):
    """[(where, value)] at a RELEASE_CONFIG_PATHS path of a config table ("*" walks every key)."""
    nodes = [("config.lua", cfg)]
    for part in path:
        nxt = []
        for where, v in nodes:
            if not isinstance(v, dict):
                continue
            for k in (sorted(v, key=str) if part == "*" else [part]):
                if k in v:
                    nxt.append((f"{where}{' ' if where == 'config.lua' else '.'}{k}", v[k]))
        nodes = nxt
    return nodes


def bandfix_table_files(cfg):
    """The mod-relative Exact coastlines tables of every generation a config lists. Control code reads them on
    every chunk of a save, so a released one moves tiles as surely as a noise body."""
    B = _as_dict(cfg.get("bandfix"))
    scales = _as_dict(cfg.get("scales")).get("exact_coast")
    if not isinstance(B.get("version"), int) or not isinstance(scales, list):
        return set()
    out = set()
    for key in _as_dict(B.get("tables")):
        rows = [{"version": B["version"]}] + [r for r in (_as_dict(B.get("generations")).get(key) or [])
                                              if isinstance(r, dict)]
        for r in rows:
            out.add(f"scripts/generated/bandfix_{key}_v{r.get('shared', r.get('version'))}.lua")
            out.update(f"scripts/generated/bandfix_{key}_s{s}_v{r.get('version')}.lua" for s in scales)
    return out


# A released file withdrawn from the tree because its licence bars distributing it. The row that named it stays landed in
# every other respect, and the bodies it built keep their records: the gate compares them with the source mod loaded.
WITHDRAWN_FILES = ("prototypes/generated/palms_ab_v1.lua",)


def without_withdrawn(row):
    """A release_registry row as the append-only check reads it: no withdrawn file, and no empty files list."""
    files = [f for f in (row.get("files") or []) if f not in WITHDRAWN_FILES]
    out = {k: v for k, v in row.items() if k != "files"}
    return dict(out, files=files) if files else out


def release_input_files(cfg):
    """The mod-relative files a config's landed rows bind: every release_registry row's files, every
    geography version's fits and spawn bearings, and every generation's band-fix tables."""
    files = bandfix_table_files(cfg)
    for r in cfg.get("release_registry") or []:
        if isinstance(r, dict):
            files.update(f for f in (r.get("files") or []) if isinstance(f, str))
    for g in _as_dict(cfg.get("geography")).values():
        for v in (_as_dict(g).get("versions") or []):
            v = _as_dict(v)
            files.update(f for f in _as_dict(v.get("fits")).values() if isinstance(f, str))
            b = _as_dict(v.get("spawn")).get("bearings")
            if isinstance(b, str):
                files.add(b)
    return sorted(files)


def _collapsed_row(r, wrows, collapse):
    """Whether 0.3.0's collapse (tests/collapsed.json) excuses landed release row `r` here: a retired tn_geo id's row
    is gone, a frame's row lost only names the collapse dropped and files it lists or another row here names, and a
    row of no geography left whole when every name it released was dropped and each of its files is so placed, or
    kept with the rest of its names (the same release and fields, no name added) when each name it lost was dropped."""
    if not collapse:
        return False
    # a file a lost row named leaves with it (the collapse lists it) or stays named by a row here
    recs = set(collapse.get("records") or {})
    files = set(collapse.get("files") or []) | {f for w in wrows for f in (w.get("files") or [])}
    geo = r.get("geography")
    if geo is None:
        if (set(r.get("names") or []) <= recs and set(r.get("files") or []) <= files and
                without_withdrawn(r) not in [without_withdrawn(w) for w in wrows]):
            return True
        other = {k: v for k, v in r.items() if k not in ("names", "files")}
        rn, rf = list(r.get("names") or []), set(r.get("files") or [])
        for w in wrows:
            if w.get("geography") is not None or w.get("map") is not None:
                continue
            if {k: v for k, v in w.items() if k not in ("names", "files")} != other:
                continue
            wn, wf = list(w.get("names") or []), set(w.get("files") or [])
            kept_in_order = [n for n in rn if n in set(wn)] == wn
            if wn and kept_in_order and set(rn) - set(wn) <= recs and rf - wf <= files and wf <= rf:
                return True
        return False
    mine = [w for w in wrows if w.get("geography") == geo and w.get("map") == r.get("map")]
    if geo in (collapse.get("geographies") or []):
        return not mine
    if geo in (collapse.get("frames") or []) and len(mine) == 1:
        w = mine[0]
        lost_n = set(r.get("names") or []) - set(w.get("names") or [])
        lost_f = set(r.get("files") or []) - set(w.get("files") or [])
        same = {k: v for k, v in r.items() if k not in ("names", "files")} == \
            {k: v for k, v in w.items() if k not in ("names", "files")}
        return (same and lost_n <= recs and lost_f <= files and set(w.get("names") or []) <= set(r.get("names") or [])
                and set(w.get("files") or []) <= set(r.get("files") or []))
    return False


def release_input_findings(work, refs, collapse=None):
    """What the working tree changed in place of the data a reference's landed bodies are built from.
    `work` and each `refs[ref]` are {"cfg": <config table>, "files": {<mod-relative path>: <sha256, or
    None when absent>}, "tables": {<repo-relative path>: <table, or None>}}. A reference without a
    release_registry row freezes nothing (nothing has landed). `collapse` (tests/collapsed.json, 0.3.0's one
    geography version per map) excuses exactly what it lists: the versions it drops from geography.<map>.versions,
    the release rows it retires or trims to a frame (_collapsed_row) and the generated files it drops."""
    out = []
    wcfg = _as_dict(work.get("cfg"))
    for ref, d in sorted(refs.items()):
        rc = _as_dict(d.get("cfg"))
        rows = [r for r in (rc.get("release_registry") or []) if isinstance(r, dict)]
        if not rows:
            continue
        for path in RELEASE_CONFIG_PATHS:
            got = dict(_release_paths(wcfg, path))
            for where, v in _release_paths(rc, path):
                if where not in got:
                    out.append(f"{where} is on {ref} and gone here (a value a registered body is built from)")
                    continue
                out += _release_value_findings(v, got[where], where, ref, collapse)
        rsets, wsets = _as_dict(rc.get("settings")), _as_dict(wcfg.get("settings"))
        for key, named in sorted(release_settings(rc).items(), key=lambda kv: str(kv[0])):
            where = f"config.lua settings.{key}.allowed_values"
            want = _as_dict(rsets.get(key)).get("allowed_values")
            have = _as_dict(wsets.get(key)).get("allowed_values")
            if not isinstance(want, list):
                out.append(f"{where}: {ref}'s {named[0]} names it but {ref} holds no such list (fail closed)")
            elif have != want:
                state = "gone" if not isinstance(have, list) else (
                    "reordered" if sorted(have) == sorted(want) else "changed")
                out.append(f"{where} is {state} here against {ref} ({len(want)} values there, "
                           f"{len(have) if isinstance(have, list) else 0} here): {named[0]} builds registered bodies "
                           f"and baked per-save numbers from its order and length, so it never changes, not even by "
                           f"an append (ship a new setting under the next geography version)")
        wrows = [r for r in (wcfg.get("release_registry") or []) if isinstance(r, dict)]
        for r in rows:
            if _collapsed_row(r, wrows, collapse):
                continue
            if r.get("geography") is None and r.get("map") is None:
                # a row of no geography (a layer's or a milestone's shared bodies, from region-layer and
                # climate-tiles several): no id names it, so the landed row must stand here unchanged
                if without_withdrawn(r) not in [without_withdrawn(w) for w in wrows]:
                    out.append(f"config.lua release_registry row of no geography naming "
                               f"{sorted(map(str, r.get('names') or []))[:2]} is landed on {ref} and changed or "
                               f"missing here (a landed row never changes)")
                continue
            mine = [w for w in wrows if w.get("geography") == r.get("geography") and w.get("map") == r.get("map")]
            if mine != [r]:
                state = "changed" if mine else "missing"
                out.append(f"config.lua release_registry row of map {r.get('map')!r} geography {r.get('geography')!r} "
                           f"is landed on {ref} and {state} here (a landed row never changes)")
        for f in release_input_files(rc):
            if f in WITHDRAWN_FILES:
                continue
            want = _as_dict(d.get("files")).get(f)
            have = _as_dict(work.get("files")).get(f)
            if have is None and collapse and f in (collapse.get("files") or []):
                continue
            if want is None:
                out.append(f"terra-nauvis/{f}: {ref}'s landed rows name it but {ref} holds no such file (fail closed)")
            elif have != want:
                state = "differs from" if have else "is missing against"
                out.append(f"terra-nauvis/{f} {state} {ref} (sha256 {str(have)[:12]} here, {want[:12]} there): a "
                           f"landed row's bodies read it, so it never changes in place (emit the next version's file)")
        for tp, rt in sorted(_as_dict(d.get("tables")).items()):
            wt = _as_dict(work.get("tables")).get(tp)
            if not isinstance(rt, dict):
                out.append(f"{tp} on {ref} does not parse as a keyed table (fail closed)")
                continue
            for k in sorted(rt, key=str):
                if not isinstance(wt, dict) or k not in wt:
                    out.append(f"{tp} table {k!r} is on {ref} and gone here (a released table version)")
                elif wt[k] != rt[k]:
                    out.append(f"{tp} table {k!r} changed in place against {ref}: a released table version is never "
                               f"edited (ship the change as the next version)")
    return sorted(set(out))


def _git_ls(sha, prefix, repo=REPO):
    cp = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha, "--", prefix], cwd=str(repo),
                        capture_output=True, text=True)
    if cp.returncode != 0:
        raise ReferenceUnreadable(f"git ls-tree {sha[:8]} {prefix} failed ({(cp.stderr or '').strip()[:200]}) "
                                  f"(fail closed)")
    return [x for x in cp.stdout.splitlines() if x.endswith(".lua")]


def _git_blob(sha, path, repo=REPO):
    cp = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=str(repo), capture_output=True)
    return cp.stdout if cp.returncode == 0 else None


def release_input_reference(refs_cfg, shas, repo=REPO):
    """The work tree's and each reference's release inputs, as release_input_findings reads them (the
    work side's "cfg" is the caller's to add)."""
    repo = Path(repo)
    refs, wanted, tables = {}, set(), set()
    for ref, cfg in refs_cfg.items():
        sha = shas[ref]
        files, tabs = {}, {}
        if [r for r in (cfg.get("release_registry") or []) if isinstance(r, dict)]:
            for f in release_input_files(cfg):
                blob = _git_blob(sha, f"terra-nauvis/{f}", repo)
                files[f] = hashlib.sha256(_norm_bytes(blob)).hexdigest() if blob is not None else None
            for tp in _git_ls(sha, RELEASE_TABLES_DIR, repo):
                blob = _git_blob(sha, tp, repo)
                try:
                    tabs[tp] = tnconfig.loads(blob.decode("utf-8"), f"{ref}:{tp}") if blob is not None else None
                except (UnicodeDecodeError, tnconfig.ConfigError):
                    tabs[tp] = None
            wanted.update(files)
            tables.update(tabs)
        refs[ref] = {"cfg": cfg, "files": files, "tables": tabs}
    wfiles = {}
    for f in sorted(wanted):
        p = repo / "terra-nauvis" / f
        wfiles[f] = hashlib.sha256(_norm_bytes(p.read_bytes())).hexdigest() if p.is_file() else None
    wtabs = {}
    for tp in sorted(tables):
        p = repo / tp
        try:
            wtabs[tp] = tnconfig.load(p) if p.is_file() else None
        except tnconfig.ConfigError:
            wtabs[tp] = None
    return {"files": wfiles, "tables": wtabs}, refs


def work_release_inputs(cfg, repo=REPO):
    """The working tree's own release inputs in release_input_findings' shape (the fixtures' base)."""
    repo = Path(repo)
    files = {}
    for f in release_input_files(cfg):
        p = repo / "terra-nauvis" / f
        files[f] = hashlib.sha256(_norm_bytes(p.read_bytes())).hexdigest() if p.is_file() else None
    tables = {}
    tdir = repo / RELEASE_TABLES_DIR
    for p in sorted(tdir.glob("*.lua")) if tdir.is_dir() else []:
        tables[RELEASE_TABLES_DIR + p.name] = tnconfig.load(p)
    return {"cfg": cfg, "files": files, "tables": tables}


def moves_findings(repo, tags):
    """(findings, the waiver or None): tests/unreleased-moves.json (tools/tnfrozen.py) applies while no
    release exists, and a release that exists voids it, so a non-empty file then fails the row."""
    path = Path(repo) / "tests" / "unreleased-moves.json"
    try:
        moves = tnfrozen.read_moves(path)
    except tnfrozen.RegistryUnreadable as e:
        return [str(e)], None
    if tags and moves and (moves.get("records") or moves.get("geographies")):
        return [f"tests/unreleased-moves.json still holds entries, but {tags[0]} exists: a release voids the "
                f"waiver, so empty the file"], None
    return [], None if tags else moves


def collapse_findings(repo, work_fz, work_cfg):
    """(findings, the collapse or None): tests/collapsed.json (tools/tnfrozen.py), 0.3.0's one geography version per
    map, which no release voids. It must hold what it names gone: no record it lists in tests/frozen.json, no version
    it lists in config.lua's geography, no retired tn_geo id in the release registry, each frame id a frame of
    config.lua, and no file it lists in the tree. A collapse with a finding excuses nothing (fail closed)."""
    repo = Path(repo)
    try:
        c = tnfrozen.read_collapse(repo / "tests" / "collapsed.json")
    except tnfrozen.RegistryUnreadable as e:
        return [str(e)], None
    if not c:
        return [], None
    out = []
    bodies = _as_dict(_as_dict(work_fz).get("bodies"))
    out += [f"tests/collapsed.json drops {n}, which tests/frozen.json still registers" for n in sorted(c["records"])
            if n in bodies]
    try:
        ids = {v["geo_id"] for vs in tnconfig.geography_versions(work_cfg).values() for v in vs}
        geo = tnconfig.geo_maps(work_cfg)
        fr = {f["geo_id"] for f in tnconfig.frames(work_cfg).values()}
    except tnconfig.ConfigError as e:
        return out + [f"tests/collapsed.json cannot be held to config.lua: {e}"], None
    out += [f"tests/collapsed.json drops geography version {g}, which config.lua still lists" for g in c["versions"]
            if g in ids]
    out += [f"tests/collapsed.json retires tn_geo id {g}, which the release registry still names" for g in
            c["geographies"] if g in geo]
    out += [f"tests/collapsed.json keeps tn_geo id {g} as a frame, which config.lua frames lacks" for g in c["frames"]
            if g not in fr]
    out += [f"tests/collapsed.json drops terra-nauvis/{f}, which is still in the tree" for f in c["files"]
            if (repo / "terra-nauvis" / f).exists()]
    return out, (c if not out else None)


def row_append_only(repo=REPO):
    repo = Path(repo)
    try:
        refs, shas = append_only_reference(repo)
        tags = release_tag_refs(repo)
    except ReferenceUnreadable as e:
        return [str(e)], "the reference is unreadable"
    work_fz = load_json(repo / "tests" / "frozen.json")
    work_cfg = tnconfig.load(repo / "terra-nauvis" / "prototypes" / "config.lua")
    mv_f, moves = moves_findings(repo, tags)
    co_f, collapse = collapse_findings(repo, work_fz, work_cfg)
    moves = tnfrozen.with_collapse(moves, collapse)
    f = mv_f + co_f + append_only_findings(work_fz, work_cfg, refs, moves)
    # The inputs of a landed body are fixed from its first release: before
    # one, the bodies row holds what they build to the registry, and the waiver holds the registry.
    try:
        work_in, ref_in = release_input_reference({r: d["cfg"] for r, d in refs.items() if r in tags}, shas, repo)
    except ReferenceUnreadable as e:
        return f + [str(e)], "the release inputs' reference is unreadable"
    work_in["cfg"] = work_cfg
    f = sorted(set(f + release_input_findings(work_in, ref_in, collapse)))
    snap_f, snap_seen = snapshot_findings(repo, work_fz, refs, moves)
    f = sorted(set(f + snap_f))
    landed = sorted(ref for ref, d in ref_in.items() if d["cfg"].get("release_registry"))
    seen = ", ".join(f"{ref} {sha[:8]}" for ref, sha in sorted(shas.items()))
    waived = len((moves or {}).get("records") or {})
    return f, (f"registered records (whole: type, sha256, dump, slice, date), tn_map and tn_geo ids and stored "
               f"message keys append-only against {seen}, and the records against the frozen snapshots of the "
               f"slices before the registry's newest ({snap_seen}), {waived} waived by name and hash (no release "
               f"yet, or 0.3.0's collapse: {len((collapse or {}).get('records') or {})} records, versions "
               f"{(collapse or {}).get('versions')}, rows retired {(collapse or {}).get('geographies')} or kept as "
               f"frames {(collapse or {}).get('frames')}); the landed bodies' inputs (config values, spawn-city setting lists, rows, generated files, "
               f"tables) fixed against {', '.join(landed) or 'no release yet'}")


def snapshot_findings(repo, work_fz, refs, moves=None):
    """The registry against the frozen snapshots of every milestone before the runner registry's newest
    (a group's earlier milestones, which land their registries in their suite manifests before main
    holds them), and a record of such a milestone without a snapshot that no reference holds (fail
    closed). Returns (findings, what was read)."""
    repo = Path(repo)
    try:
        registry = tnfrozen.runner_registry(repo / "tools" / "earth_test.py")
        snaps, none = tnfrozen.suite_snapshots(registry, before=registry[-1]["id"],
                                               suites=repo / "tests" / "baselines" / "suites")
    except tnfrozen.RegistryUnreadable as e:
        return [f"the slices' frozen snapshots are unreadable: {e}"], "unreadable"
    union, _ = frozen_union({ref: d.get("frozen") for ref, d in refs.items()}, moves)
    f = tnfrozen.snapshot_problems(work_fz, snaps, moves) + tnfrozen.unsnapshotted_problems(work_fz, none, union)
    seen = ", ".join(f"{k.split(chr(39))[0]} {len((v or {}).get('bodies') or {})} records"
                     for k, v in sorted(snaps.items())) or "none"
    return f, seen


# ------------------------------------------------------------------------------------------------ bodies
#
# The registered bodies themselves, without the game: tools/tnlua.py runs the mod's settings and
# data stages offline, and every Earth body they build is held to its tests/frozen.json record
# (tnfrozen.body_problems), so a body changed in place through its code (prototypes/expressions/,
# presets.lua) fails CI as a re-hash would. The gate's frozen row holds this reading equal to the
# game's dump on every gate run.

def bodies_findings(mod, fz, cfg):
    """(findings, bodies or None): the offline bodies of the mod folder `mod` against `fz`."""
    try:
        bodies = tnfrozen.offline_bodies(mod, cfg)
        beside_ab = tnfrozen.offline_ab_problems(mod, fz, cfg)
    except Exception as e:  # tnlua.LuaError and anything else: fail closed
        return [f"the offline data stage did not run: {type(e).__name__}: {e} (fail closed)"], None
    return tnfrozen.body_problems(bodies, fz, cfg) + beside_ab, bodies


def vanilla_raw_missing():
    """[the one line] when tests/vanilla-raw.json cannot seed the offline data stage, else []. The rows that
    build bodies offline fail on it first: an empty data.raw would fail them later on a vanilla name."""
    import tnlua
    problem = tnlua.vanilla_raw_problem()
    return [problem] if problem else []


def row_bodies(repo=REPO):
    missing = vanilla_raw_missing()
    if missing:
        return missing, "the offline data stage needs the base game's prototypes"
    repo = Path(repo)
    cfg = tnconfig.load(repo / "terra-nauvis" / "prototypes" / "config.lua")
    fz = load_json(repo / "tests" / "frozen.json")
    f, bodies = bodies_findings(repo / "terra-nauvis", fz, cfg)
    n = len((fz.get("bodies") or {}))
    return f, (f"{len(bodies or {})} Earth bodies built offline by tools/tnlua.py (settings and data stages at default "
               f"settings), every one of the {n} registered at its record's hash and every other one exempt; "
               f"{tnfrozen.skipped_note(cfg)}")


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


def release_zip_findings(repo=REPO):
    """T16 (FG; zip; milestone extras): `build_zip.py --release` twice gives one byte-identical zip, its
    .sha256 file names that zip and its sha256 exactly, and the release refuses an Earth body missing from
    tests/frozen.json (a released body and a firewall body each dropped from a copy of the registry) and a
    registered Map type fallback that mirrors a startup setting, while every such fallback (U3's one
    exemption) is let through: the real registry holds none of them and the release builds. A frozen
    fallback is registered like every Earth body (tnconfig.frozen_fallback_names). Returns (findings,
    detail)."""
    out = []
    repo = Path(repo)
    mod = repo / "terra-nauvis"
    frozen = repo / "tests" / "frozen.json"
    cfg = tnconfig.load(mod / "prototypes" / "config.lua")
    with tempfile.TemporaryDirectory(prefix="tn-release-") as td:
        td = Path(td)
        builds = []
        for tag in ("a", "b"):
            try:
                builds.append(build_zip.build(td / tag, release=True, mod_dir=mod, frozen_path=frozen))
            except build_zip.BuildError as e:
                return [f"build_zip.py --release refused the tree: {e}"], "the release build was refused"
        (za, da, _), (zb, db, _) = builds
        if da != db or za.read_bytes() != zb.read_bytes():
            out.append(f"two release builds differ: {da} and {db}")
        side = za.with_name(za.name + ".sha256")
        want = f"{build_zip.sha256_bytes(za.read_bytes())}  {za.name}\n"
        if not side.exists():
            out.append(f"the release wrote no {side.name}")
        elif side.read_text(encoding="utf-8") != want:
            out.append(f"{side.name} reads {side.read_text(encoding='utf-8')!r}, want {want!r}")
        fz = load_json(frozen)
        bodies = fz.get("bodies") or {}
        exempt = set(tnconfig.exempt_fallback_names(cfg))
        if exempt & set(bodies):
            out.append(f"tests/frozen.json registers Map type fallbacks that mirror a startup setting "
                       f"{sorted(exempt & set(bodies))[:4]}")
        released = [n for n in tnconfig.release_names(cfg) if n in bodies]
        firewall = [n for n in tnconfig.firewall_names(cfg) if n in bodies]
        controls = []
        if released:
            controls.append(("a released body", released[0], None))
        if firewall:
            controls.append(("a firewall body", firewall[-1], None))
        if exempt:
            fb = sorted(exempt)[0]
            controls.append(("a registered Map type fallback", fb, {"type": "noise-expression", "sha256": "0" * 64}))
        for label, name, add in controls:
            fz2 = json.loads(json.dumps(fz))
            if add is None:
                fz2["bodies"].pop(name, None)
            else:
                fz2["bodies"][name] = add
            f2 = td / f"frozen-{len(label)}-{abs(hash(name)) % 10 ** 6}.json"
            f2.write_text(json.dumps(fz2), encoding="utf-8")
            try:
                build_zip.build(td / "refused", release=True, mod_dir=mod, frozen_path=f2)
                out.append(f"positive control: the release built with {label} ({name}) "
                           f"{'dropped from' if add is None else 'added to'} the registry")
            except build_zip.BuildError as e:
                if name not in str(e):
                    out.append(f"positive control: the release refused {label} ({name}) without naming it: {e}")
        if not exempt:
            out.append("config.lua lists no Map type fallback: the exemption has nothing to let through")
    return out, (f"{za.name} sha256 {da[:16]} twice, .sha256 matches; refuses {', '.join(c[0] for c in controls)}; "
                 f"{len(exempt)} unregistered fallbacks let through")


def row_release_zip(repo=REPO):
    missing = vanilla_raw_missing()
    if missing:
        return missing, "the release build needs the base game's prototypes"
    return release_zip_findings(repo)


# The graphical and portal flags fh.py refuses (its GUI_FLAGS, long forms; fh.py lives outside this repo), written in
# fragments so this file is not a hit of its own scan. A test run never passes one, and posters never come from
# the render command of the map-export mod, which reads the live mod list and opens a graphical client (D30; V5).
GRAPHICAL_FLAGS = tuple("--" + f for f in (
    "load" + "-game", "load" + "-scenario", "mp" + "-connect", "host", "host" + "-interactive",
    "benchmark" + "-graphics", "benchmark" + "-frame", "heavy", "until" + "-tick", "sync" + "-mods",
    "dump" + "-icon-sprites", "full" + "screen", "window" + "-size", "map2" + "scenario", "scenario2" + "map",
    "apply" + "-update", "dap", "generate-map-preview" + "-random"))
EXPORT_MOD_WORD = "map" + "shot"
TOOLS_SCAN_SUFFIXES = {".py", ".lua", ".ps1", ".json", ".md", ".txt", ".js", ".cfg", ".bat", ".sh"}


def tools_scan_findings(tools=HERE):
    """V5, T16 (milestone extras; D30): no file under tools/ names the map-export mod (its render command is the one
    route a poster must never take) or passes a graphical or portal flag, as a whole token."""
    out = []
    pats = [(f, re.compile(r"(?<![\w-])" + re.escape(f) + r"(?![\w-])")) for f in GRAPHICAL_FLAGS]
    files = [p for p in walk_files(tools) if p.suffix.lower() in TOOLS_SCAN_SUFFIXES]
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.split("\n"), 1):
            if EXPORT_MOD_WORD in line.lower():
                out.append(f"{rel(p)}:{i}: names {EXPORT_MOD_WORD} (posters come from previews or dumped tiles; D30)")
            for f, pat in pats:
                if pat.search(line):
                    out.append(f"{rel(p)}:{i}: the graphical or portal flag {f}")
    return out, len(files)


def row_tools_scan(tools=HERE):
    f, n = tools_scan_findings(tools)
    return f, f"{n} files under tools/: no {EXPORT_MOD_WORD} and none of {len(GRAPHICAL_FLAGS)} graphical or portal flags"


# ------------------------------------------------------------------------------------------------ fixture controls

def _write(root, relpath, text):
    p = Path(root) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def vanilla_raw_controls(td):
    """The base prototypes file fails closed, and tools/make_vanilla_raw.py reduces a dump by the rule tnlua reads."""
    import make_vanilla_raw
    import tnlua
    out = []
    absent = Path(td) / "absent" / "vanilla-raw.json"
    try:
        tnlua.vanilla_raw(absent)
        out.append(("vanilla-raw: an absent file raises", False, "read as a base"))
    except tnlua.VanillaRawMissing as e:
        out.append(("vanilla-raw: an absent file raises and names its maker",
                    "is missing: run python tools/make_vanilla_raw.py" in str(e), str(e)))
    empty = _write(td, "empty/vanilla-raw.json", json.dumps({"format": tnlua.VANILLA_RAW_FORMAT, "raw": {}}))
    out.append(("vanilla-raw: a file holding no prototypes fails", bool(tnlua.vanilla_raw_problem(empty)), ""))
    stranger = _write(td, "format/vanilla-raw.json", json.dumps({"format": "x/1", "raw": {"tile": {"a": {}}}}))
    out.append(("vanilla-raw: a file of another format fails", bool(tnlua.vanilla_raw_problem(stranger)), ""))
    dump = {t: {"a": {"name": "a", "type": t, "extra": 1}} for t in tnlua.VANILLA_WHOLE + tnlua.VANILLA_REDUCED}
    dump["planet"] = {"nauvis": {"name": "nauvis", "type": "planet", "extra": 1}}
    dump["item"] = {"a": {"name": "a", "type": "item"}}
    red = make_vanilla_raw.reduce_dump(dump)["raw"]
    out.append(("vanilla-raw: the reduction keeps whole types whole, trims the others and drops the rest",
                red["noise-expression"]["a"].get("extra") == 1 and "extra" not in red["tile"]["a"] and "item" not in red,
                ""))
    sa = dict(dump, planet=dict(dump["planet"], vulcanus={"name": "vulcanus", "type": "planet"}))
    try:
        make_vanilla_raw.reduce_dump(sa)
        out.append(("vanilla-raw: a dump with an expansion planet is refused", False, "reduced"))
    except make_vanilla_raw.MakeError:
        out.append(("vanilla-raw: a dump with an expansion planet is refused", True, ""))
    return out


def fixture_controls():
    """Positive controls: every scan rule must fail a fixture that breaks it. Fixtures live in a fresh
    temporary directory outside the scanned trees and are never committed."""
    results = []
    exe = "factorio" + ".exe"
    with tempfile.TemporaryDirectory(prefix="tn-fixtures-") as td:
        td = Path(td)
        results += vanilla_raw_controls(td / "vanilla")
        # workflow mutations
        manifest = lint_manifest()
        wf_dir = REPO / ".github" / "workflows"
        ci = (wf_dir / "ci.yml").read_text(encoding="utf-8")
        rel_wf = (wf_dir / "release.yml").read_text(encoding="utf-8")
        latest_wf = (wf_dir / "latest.yml").read_text(encoding="utf-8")
        names = {"ci": "ci", "rel": "release", "latest": "latest"}
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
        for kind, text in (("ci", ci), ("rel", rel_wf), ("latest", latest_wf)):
            name = names[kind]
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
            ("workflow: ci checks out without full history", "ci",
             ci.replace("        with:\n          fetch-depth: 0\n", "")),
            ("workflow: ci checks out a shallow history", "ci", ci.replace("fetch-depth: 0", "fetch-depth: 1")),
            ("workflow: release checks out without full history (the landed-tag check needs origin/main)", "rel",
             rel_wf.replace("        with:\n          fetch-depth: 0\n", "", 1)),
            ("workflow: release checks out a shallow history", "rel", rel_wf.replace("fetch-depth: 0", "fetch-depth: 1")),
            ("workflow: latest checks out without full history (the append-only row needs origin/main)", "latest",
             latest_wf.replace("        with:\n          fetch-depth: 0\n", "", 1)),
            ("workflow: latest checks out a shallow history", "latest", latest_wf.replace("fetch-depth: 0", "fetch-depth: 1")),
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
                                       ("rel", rel_wf, static_run, "the release static step"),
                                       ("rel", rel_wf, release_run, "the release build"),
                                       ("rel", rel_wf, publish_run, "the publish step"),
                                       ("latest", latest_wf, static_run, "the latest static step"),
                                       ("latest", latest_wf, build_run, "the latest zip build"),
                                       ("latest", latest_wf, publish_run, "the latest publish step")):
            line = line if line in text else ""
            muts += [
                (f"workflow: continue-on-error on {what}", kind,
                 after(text, line, "        continue-on-error: true\n") if line else text),
                (f"workflow: if: false on {what}", kind, after(text, line, "        if: false\n") if line else text),
                (f"workflow: a shell override on {what}", kind, after(text, line, "        shell: bash\n") if line else text),
                (f"workflow: a working-directory on {what}", kind,
                 after(text, line, "        working-directory: spikes\n") if line else text),
            ]
            if kind == "ci" or what in ("the release build", "the latest static step", "the latest zip build"):
                muts.append((f"workflow: an environment on {what}", kind,
                             after(text, line, "        env:\n          PYTHONPATH: x\n") if line else text))
        for kind, text in (("ci", ci), ("rel", rel_wf), ("latest", latest_wf)):
            name = names[kind]
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
        # latest.yml: its trigger, permissions, concurrency, step order and publish block
        lw = latest_wf
        conc = "concurrency:\n  group: latest-release\n  cancel-in-progress: false\n"
        static_step = r"      - name: Static checks\n(        .*\n)+"
        publish_name = "      - name: Publish the latest pre-release\n"
        delete_check = '; if ($LASTEXITCODE -ne 0) { throw "gh release delete failed with exit code $LASTEXITCODE" }'
        muts += [
            ("workflow: latest on a tag", "latest", lw.replace("    branches:\n      - main\n", '    tags:\n      - "v*"\n')),
            ("workflow: latest on pull_request", "latest", lw.replace("on:\n  push:\n", "on:\n  pull_request:\n  push:\n")),
            ("workflow: latest with an extra trigger", "latest",
             lw.replace("on:\n  push:\n", "on:\n  workflow_dispatch:\n  push:\n")),
            ("workflow: latest on every push", "latest", lw.replace("  push:\n    branches:\n      - main\n", "  push:\n")),
            ("workflow: latest on another branch", "latest", lw.replace("      - main\n", "      - release\n")),
            ("workflow: latest on an extra branch", "latest", lw.replace("      - main\n", "      - main\n      - dev\n")),
            ("workflow: latest on pushes touching some paths only", "latest",
             lw.replace("      - main\n", '      - main\n    paths:\n      - "terra-nauvis/**"\n')),
            ("workflow: latest with read permission", "latest", lw.replace("contents: write", "contents: read")),
            ("workflow: latest with an extra permission", "latest",
             lw.replace("  contents: write\n", "  contents: write\n  actions: write\n")),
            ("workflow: latest with write-all permissions", "latest",
             lw.replace("permissions:\n  contents: write\n", "permissions: write-all\n")),
            ("workflow: latest with another token", "latest",
             lw.replace("${{ secrets.GITHUB_TOKEN }}", "${{ secrets.RELEASE_PAT }}")),
            ("workflow: latest with an unpinned action", "latest", lw.replace(f"actions/checkout@{sha}", "actions/checkout@v7")),
            ("workflow: latest not on windows-latest", "latest", lw.replace("windows-latest", "ubuntu-latest")),
            ("workflow: latest on another python", "latest", lw.replace('"3.13.3"', '"3.12"')),
            ("workflow: latest without the concurrency block", "latest", lw.replace(conc, "")),
            ("workflow: latest cancels a running publish", "latest",
             lw.replace("cancel-in-progress: false", "cancel-in-progress: true")),
            ("workflow: latest in a per-commit concurrency group", "latest",
             lw.replace("group: latest-release", "group: ${{ github.sha }}")),
            ("workflow: latest with the concurrency block on its job", "latest",
             lw.replace(conc + "\n", "").replace("    runs-on: windows-latest\n", "    runs-on: windows-latest\n    "
                                                 "concurrency:\n      group: latest-release\n      cancel-in-progress: "
                                                 "false\n", 1)),
            ("workflow: latest publishes under an if", "latest",
             lw.replace(publish_name, publish_name + "        if: github.ref == 'refs/heads/main'\n")),
            ("workflow: latest without the static step", "latest", re.sub(static_step, "", lw)),
            ("workflow: latest with the static step neutralised in its own run block", "latest",
             lw.replace("run: python tools/earth_test.py static", "run: python tools/earth_test.py static; exit 0")),
            ("workflow: latest with the static step followed by exit 0", "latest",
             lw.replace(static_run, "        run: |\n          python tools/earth_test.py static\n          exit 0\n")),
            ("workflow: latest publishes before the static checks", "latest",
             re.sub(static_step, "", lw) + "      - name: Static checks\n        run: python tools/earth_test.py static\n"),
            ("workflow: latest without the zip build", "latest", re.sub(r"      - name: Build the zip\n(        .*\n)+", "", lw)),
            ("workflow: latest builds the release zip", "latest",
             lw.replace(build_run, "        run: python tools/build_zip.py --release\n")),
            ("workflow: latest with the zip build neutralised in its own run block", "latest",
             lw.replace(build_run, "        run: python tools/build_zip.py; exit 0\n")),
            ("workflow: latest with an extra step", "latest",
             lw.replace(publish_name, "      - name: Build the zip again\n        run: python tools/build_zip.py\n" +
                        publish_name)),
            ("workflow: latest without --prerelease", "latest", lw.replace(" --prerelease", "")),
            ("workflow: latest publishes a draft", "latest", lw.replace(" --prerelease", " --prerelease --draft")),
            ("workflow: latest marked the repository's Latest release", "latest",
             lw.replace(" --prerelease", " --prerelease --latest")),
            ("workflow: latest names another repository", "latest",
             lw.replace(" --prerelease", " --prerelease --repo someone/else")),
            ("workflow: latest without --target", "latest", lw.replace(' --target "$env:GITHUB_SHA"', "")),
            ("workflow: latest at the branch head, not the pushed commit", "latest",
             lw.replace('--target "$env:GITHUB_SHA"', "--target main")),
            ("workflow: latest under another tag", "latest", lw.replace("gh release create latest", "gh release create nightly")),
            ("workflow: latest under another title", "latest", lw.replace("--title latest", '--title "$env:GITHUB_SHA"')),
            ("workflow: latest notes run a subexpression", "latest", lw.replace('--notes "Rolling', '--notes "$(exit 0)Rolling')),
            ("workflow: latest attaches an extra file", "latest", lw.replace("latest @files", "latest @files README.md")),
            ("workflow: latest attaches every file in dist", "latest",
             lw.replace(' | Where-Object { $_.Name -like "*.zip" }', "")),
            ("workflow: latest without the zip count check", "latest",
             re.sub(r"\n\s*if \(\$files\.Count -ne 1\)[^\n]*", "", lw)),
            ("workflow: latest without the native-command pin", "latest",
             lw.replace("          $PSNativeCommandUseErrorActionPreference = $false\n", "")),
            ("workflow: latest deletes without looking first", "latest",
             lw.replace("gh release view latest --json tagName\n", "gh release delete latest --cleanup-tag --yes\n")),
            ("workflow: latest delete leaves the old tag", "latest", lw.replace(" --cleanup-tag", "")),
            ("workflow: latest ignores a failed delete", "latest", lw.replace(delete_check, "")),
            ("workflow: latest ignores a failed create", "latest",
             re.sub(r"\n\s*if \(\$LASTEXITCODE -ne 0\) \{ throw \"gh release create[^\n]*", "", lw)),
            ("workflow: latest without the tag check", "latest", re.sub(r"\n\s*\$tag = gh api [^\n]*\n\s*if \(\$tag [^\n]*", "", lw)),
            ("workflow: latest checks the tag of another repository", "latest",
             lw.replace("repos/$env:GITHUB_REPOSITORY/", "repos/someone/else/")),
            ("workflow: latest tag check compares nothing", "latest", lw.replace("if ($tag -ne $env:GITHUB_SHA)", "if ($false)")),
            ("workflow: latest publish followed by exit 0", "latest", lw.rstrip("\n") + "\n          exit 0\n"),
        ]
        lint_dir = td / "lint-fixture"
        shutil.copytree(LINT, lint_dir)
        (lint_dir / "requirements.txt").write_text("luaparser\n", encoding="utf-8")
        f = workflow_findings(REPO / ".github" / "workflows", lint_dir)
        results.append(("workflow: requirements.txt without the luaparser pin", bool(f), f[:1]))
        checks = {"ci": (check_ci, ci), "rel": (check_release, rel_wf), "latest": (check_latest, latest_wf)}
        for label, kind, text in muts:
            fn, orig = checks[kind]
            f = fn(text, manifest) if text != orig else []
            results.append((label, bool(f) and text != orig, f[:1] if text != orig else ["mutation did not apply"]))
        committed = check_ci(ci, manifest) + check_release(rel_wf, manifest) + check_latest(latest_wf, manifest)
        results.append(("workflow: the committed ci.yml, release.yml and latest.yml pass the scan", not committed,
                        committed[:1]))
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
        results += europe_coast_fixtures(td, cfg)
        results += registration_form_fixtures(td)
        results += schema_fixtures(td, cfg)
        results += storage_contract_fixtures(td)
        results += append_only_fixtures(cfg, load_json(REPO / "tests" / "frozen.json"))
        results += release_input_fixtures(cfg)
        results += bandfix_digest_fixtures(cfg)
        results += thin_version_fixtures(cfg)
        fz = load_json(REPO / "tests" / "frozen.json")
        results += bodies_fixtures(td, cfg, fz)
        results += landing_fixtures(td, cfg, fz)
        results += landed_tag_fixtures(td)
        results += snapshot_file_fixtures(td)
        results += region_fixtures(td, cfg)
        results += ranges_fixtures(td)
        results += hotspots_fixtures(td)
        results += d33_fixtures()
        results += redefinition_fixtures()
        results += extras_fixtures(td, cfg)
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


def europe_coast_fixtures(td, cfg):
    """The rows europe-coast added: the Map type entry's [noise-expression] name and the scale
    labels' world sizes (locale), the fits provenance (data-src) and the fallbacks' shape."""
    out = []
    loc = MOD / "locale" / "en" / "terra-nauvis.cfg"
    entry = next(iter(tnconfig.geography(cfg).values()), {}).get("entry")
    if entry:
        m = td / "loc-maptype" / "terra-nauvis"
        shutil.copytree(MOD, m)
        text = loc.read_text(encoding="utf-8")
        (m / "locale" / "en" / "terra-nauvis.cfg").write_text(
            "\n".join(l for l in text.split("\n") if not l.startswith(entry + "=")), encoding="utf-8")
        f, _ = row_locale(m)
        out.append(("locale: a Map type entry without its [noise-expression] name fails",
                    any(entry in x for x in f), f[:1]))
    s = cfg["settings"]["scale"]
    m = td / "loc-sizes" / "terra-nauvis"
    shutil.copytree(MOD, m)
    text = loc.read_text(encoding="utf-8")
    v = s["allowed_values"][-1]
    key = f"{s['name']}-{v}="
    m0 = cfg["maps"][cfg["map_order"][0]]
    right = thousands(m0["width_px"] * int(v))
    bad = "\n".join((l.replace(right, right + "1") if l.startswith(key) else l) for l in text.split("\n"))
    (m / "locale" / "en" / "terra-nauvis.cfg").write_text(bad, encoding="utf-8")
    f, _ = row_locale(m)
    out.append(("locale: a scale label with a wrong world size fails", any("world size" in x for x in f), f[:1]))
    if cfg.get("waterways"):
        m = td / "loc-notice" / "terra-nauvis"
        shutil.copytree(MOD, m)
        msgs = cfg["messages"]
        nkey = msgs["keys"]["notice"] + "="
        bad = "\n".join((l.replace("ford", "crossing") if l.startswith(nkey) else l) for l in text.split("\n"))
        (m / "locale" / "en" / "terra-nauvis.cfg").write_text(bad, encoding="utf-8")
        f, _ = row_locale(m)
        out.append(("locale: a Map type notice that does not name fords fails", any("ford" in x for x in f), f[:1]))
    r = td / "fits-repo"
    shutil.copytree(REPO / "data-src", r / "data-src")
    shutil.copytree(MOD, r / "terra-nauvis")
    fits = r / "data-src" / "fits"
    victim = next((p for d in sorted(fits.iterdir()) if d.is_dir() for p in sorted(d.glob("*.npz"))), None)
    if victim is not None:
        victim.write_bytes(victim.read_bytes() + b"\0")
        f = data_src_findings(r)
        out.append(("data-src: a fit checkpoint differing from its provenance fails",
                    any(victim.name in x for x in f), f[:1]))
    else:
        out.append(("data-src: a fit checkpoint differing from its provenance fails", False, "no fit checkpoint"))
    wwd = r / "data-src" / "waterways"
    if cfg.get("waterways") and wwd.is_dir():
        k0 = cfg["map_order"][0]
        src = wwd / f"{k0}.json"
        D = load_json(src)
        D2 = dict(D, rivers=list(reversed(D["rivers"])))
        src.write_text(json.dumps(D2), encoding="utf-8")
        f = data_src_findings(r)
        out.append(("data-src: a waterway input differing from its provenance fails",
                    any(src.name in x and "PROVENANCE" in x for x in f), f[:1]))
        out.append(("data-src: rivers out of APPROVALS 7's order fail", any("not APPROVALS 7" in x for x in f), f[:1]))
        D3 = dict(D, cuts={"6": {"rivers": 1, "tolerance_tiles": 0}})
        src.write_text(json.dumps(D3), encoding="utf-8")
        f = data_src_findings(r)
        out.append(("data-src: a cut below Europe's rivers fails", any("a cut keeps between" in x for x in f), f[:1]))
        out.append(("data-src: a cut lowering the tolerance fails", any("lowers scale" in x for x in f), f[:1]))
        man = wwd / f"manifest-{k0}.json"
        M = load_json(man)
        flip = next(((s, i) for s, rec in sorted(M["scales"].items()) for i, b in enumerate(rec.get("basins") or [])
                     if b.get("kind") == "canal"), None)
        if flip:
            M["scales"][flip[0]]["basins"][flip[1]]["kind"] = "river"
            man.write_text(json.dumps(M), encoding="utf-8")
            f = waterway_basin_findings(r, cfg)
            out.append(("data-src: a canal basin outside its canal set fails", any("basin" in x for x in f), f[:1]))
        else:
            out.append(("data-src: a canal basin outside its canal set fails", False, "no canal basin to move"))
    else:
        out.append(("data-src: waterway inputs present with config.lua's waterways group", not cfg.get("waterways"),
                    "no data-src/waterways"))
    geo = tnconfig.geography(cfg)
    if geo:
        key0 = next(iter(geo))
        fb = geo[key0]["fallbacks"]
        shared = cfg_version(cfg, key0, fallbacks=[{"name": cfg["keys"]["scale"] + "_" + key0, "map_qualified": False}])
        out.append(("fallbacks: a shared fallback carrying a map suffix fails", bool(fallback_findings(shared)), ""))
        qual = cfg_version(cfg, key0, fallbacks=[{"name": cfg["keys"]["scale"], "map_qualified": True}])
        out.append(("fallbacks: a map-qualified fallback without its map suffix fails", bool(fallback_findings(qual)),
                    ""))
        stray = cfg_version(cfg, key0, fallbacks=[{"name": cfg["identity"]["noise_prefix"] + "stray",
                                                   "map_qualified": False}])
        out.append(("fallbacks: a fallback no preset bakes fails", bool(fallback_findings(stray)), ""))
        out.append(("fallbacks: config.lua's fallbacks pass", not fallback_findings(cfg), fallback_findings(cfg)[:1]))
        frozen = [e for e in fb if e.get("frozen")]
        if frozen:
            thawed = cfg_version(cfg, key0, fallbacks=[dict(e, frozen=False) if e is frozen[0] else e for e in fb])
            out.append(("fallbacks: a released fallback that mirrors a setting fails",
                        bool(fallback_findings(thawed)) and bool(tnconfig.schema_problems(thawed)), ""))
            unreg = dict(cfg, release_registry=[dict(r, names=[n for n in r["names"] if n != frozen[0]["name"]])
                                                for r in cfg["release_registry"]])
            out.append(("fallbacks: a frozen fallback in no release row fails",
                        bool(fallback_findings(unreg)) and bool(tnconfig.schema_problems(unreg)), ""))
        else:
            out.append(("fallbacks: config.lua holds a frozen fallback to test", False, "none frozen"))
    # control code labels a world by its preset's name, never a [noise-expression] key
    m = td / "ctl-noise-label" / "terra-nauvis"
    shutil.copytree(MOD, m)
    (m / "scripts" / "label_fixture.lua").write_text(
        'local M = {}\nfunction M.label(e)\n  return {"noise-expression." .. e}\nend\nreturn M\n', encoding="utf-8")
    f, _ = row_locale(m)
    out.append(("locale: control code building a [noise-expression] key fails",
                any("label_fixture.lua" in x for x in f), f[:1]))
    out.append(("locale: the shipped control code builds no [noise-expression] key",
                not control_noise_label_findings(MOD), control_noise_label_findings(MOD)[:1]))
    out += version_fixtures(cfg)
    return out


def cfg_version(cfg, map_key=None, index=-1, **fields):
    """A deep copy of `cfg` with one geography version's fields set (by default the newest version of
    the first map): a fixture config for the schema and fallback checks."""
    out = copy.deepcopy(cfg)
    geo = out["geography"]
    geo[map_key or next(iter(geo))]["versions"][index].update(copy.deepcopy(fields))
    return out


def next_version(cfg, map_key=None):
    """config.lua with the next geography version of a map added the way a later milestone adds one
    (ARCHITECTURE.md, "Map type entries": the documented v2): every name of its own (each name's
    version suffix moved on), the next unused tn_geo id with its own release row, the same generated
    files bound to its own chain, its offset names in preset_keys, its fine field in the firewall, a
    start mask version of its own, and the fallbacks its entry reads (the shared scale and its own
    frozen offsets). Returns (config, map key, the new version)."""
    out = copy.deepcopy(cfg)
    key = map_key or next(iter(out["geography"]))
    vs = out["geography"][key]["versions"]
    last = vs[-1]
    n = int(re.search(r"_v(\d+)$", last["entry"]).group(1)) + 1

    def bump(name):
        return re.sub(r"_v\d+$", "", name) + f"_v{n}"
    new = {r: bump(last[r]) for r in tnconfig.GEOGRAPHY_NAMES}
    ids = [v["geo_id"] for g in out["geography"].values() for v in g["versions"]]
    ids += [r["geography"] for r in out["release_registry"] if "geography" in r]
    gid = max(ids) + 1
    mask = dict(next(m for m in out["start_mask"]["versions"] if m["name"] == last["start_mask"]),
                name=bump(last["start_mask"]))
    out["start_mask"]["versions"].append(mask)
    own = {last["cx"]: new["cx"], last["cy"]: new["cy"]}
    v = dict(last, **new, geo_id=gid, start_mask=mask["name"],
             fallbacks=[dict(e, name=own.get(e["name"], e["name"])) for e in last["fallbacks"]])
    # a spawn record's names that read the version's chain are the version's own too (its inland
    # lakes); the other spawn bodies read no chain and serve both versions
    sp = tnconfig.spawn_of(last)
    spawn_new = {r: bump(sp[r]) for r in tnconfig.SPAWN_OWN} if sp else {}
    if sp:
        v["spawn"] = dict(sp, **spawn_new)
    # waterway sets read the version's chain too, so a version that composes them takes sets of its own,
    # and the map's sets are then the newest version's
    ww = tnconfig.waterways_of(last)
    ww_new = {k: [bump(n) for n in names] for k, names in ww.items()} if ww else {}
    if ww:
        v["waterways"] = ww_new
        out["waterways"]["sets"][key] = ww_new
    # its mouth and warp bodies read the chain as well (tnconfig.waterway_names)
    extra_new = set()
    for field in ("mouths", "warp"):
        if last.get(field):
            v[field] = [bump(n) for n in last[field]]
            extra_new |= set(v[field])
    # a shore body (climate-tiles) reads the version's fit, detail and box, so it is the version's own too
    shore_new = {bump(last["shore"])} if last.get("shore") else set()
    if shore_new:
        v["shore"] = next(iter(shore_new))
    vs.append(v)
    out["release_registry"].append({"release": out["release_registry"][-1]["release"], "map": key, "geography": gid,
                                    "names": sorted(set(new.values()) | {mask["name"]} | set(spawn_new.values()) |
                                                    {n for names in ww_new.values() for n in names} | shore_new |
                                                    extra_new),
                                    "files": []})
    out["preset_keys"] = list(out["preset_keys"]) + [new["cx"], new["cy"]]
    out["firewall"][key] = list(out["firewall"][key]) + [n for n in tnconfig.fine_names(v)
                                                         if n not in out["firewall"][key]]
    return out, key, v


def version_fixtures(cfg):
    """config.lua holds every version of a map's geography, fallbacks and start mask: the documented
    next version (names of its own, the next tn_geo id, the same generated files) passes every
    schema and fallback check and becomes the preset's version while the older one stays listed;
    a next version that re-points an older version's names, shares its tn_geo id, bakes a key
    preset_keys lacks, leaves its fine field outside the firewall, names a start mask or a file
    config.lua lacks, or lists a shared fallback with other flags fails; and the retired one-version
    shapes (a top-level fallbacks group or start_mask_versions, a geography holding entry_versions,
    an empty versions list, a start mask without its formula) fail instead of being read by no one."""
    out = []
    if not tnconfig.geography(cfg) or not tnconfig.start_masks(cfg):
        return [("versions: the fixtures need a geography and a start mask", False, "")]
    v2cfg, key, v2 = next_version(cfg)
    probs = tnconfig.schema_problems(v2cfg) + fallback_findings(v2cfg)
    newest = tnconfig.geography(v2cfg)[key]
    out.append(("versions: the documented next version passes the schema and fallback checks",
                not probs and newest["entry"] == v2["entry"] and newest["entry_versions"][-1] == v2["entry"] and
                len(newest["entry_versions"]) == len(tnconfig.geography(cfg)[key]["entry_versions"]) + 1, probs[:1]))
    out.append(("versions: the next version's start mask and fallbacks join the older ones",
                [m["name"] for m in tnconfig.start_masks(v2cfg)][-1] == v2["start_mask"] and
                {v2["cx"], v2["cy"]} <= set(tnconfig.frozen_fallback_names(v2cfg)) and
                set(tnconfig.frozen_fallback_names(cfg)) <= set(tnconfig.frozen_fallback_names(v2cfg)), ""))
    older = tnconfig.geography_versions(cfg)[key][-1]
    sk = cfg["keys"]["scale"]
    cases = {
        "a next version re-pointing the older version's city offset names": (
            cfg_version(v2cfg, key, cx=older["cx"], cy=older["cy"],
                        fallbacks=[e for e in older["fallbacks"]]), "in more than one role or version"),
        "a next version sharing the older version's tn_geo id": (
            cfg_version(v2cfg, key, geo_id=older["geo_id"]), "geo_id of more than one version"),
        "a next version baking an offset name preset_keys lacks": (
            dict(v2cfg, preset_keys=[k for k in v2cfg["preset_keys"] if k != v2["cx"]]), "preset_keys lacks"),
        "a next version whose entry is outside the firewall": (
            dict(v2cfg, firewall={key: [n for n in v2cfg["firewall"][key] if n != v2["entry"]]}),
            "firewall." + key + " lacks"),
        "a next version naming no start mask version": (
            cfg_version(v2cfg, key, start_mask=cfg["identity"]["noise_prefix"] + "start_mask_v99"),
            "is no start_mask version"),
        "a next version binding a file no release row lists": (
            cfg_version(v2cfg, key, fits=dict(v2["fits"], geo="prototypes/generated/geo_nowhere_v9.lua")),
            "no release_registry row lists"),
        "a next version listing the shared scale fallback as frozen": (
            cfg_version(v2cfg, key, fallbacks=[dict(e, frozen=True) if e["name"] == sk else e
                                               for e in v2["fallbacks"]]), "with different flags"),
        "a top-level fallbacks group (retired into each geography version)": (
            dict(cfg, fallbacks={key: [{"name": sk, "map_qualified": False}]}), "retired"),
        "a top-level start_mask_versions group (retired into start_mask.versions)": (
            dict(cfg, start_mask_versions=[]), "retired"),
        "a geography holding entry_versions beside its versions": (
            dict(cfg, geography={key: dict(cfg["geography"][key], entry_versions=[older["entry"]])}),
            "must hold exactly"),
        "a geography with no version": (
            dict(cfg, geography={key: dict(cfg["geography"][key], versions=[])}), "at least one version"),
        "a start mask version without its formula": (
            dict(cfg, start_mask={"versions": [{k: x for k, x in m.items() if k != "formula"}
                                               for m in cfg["start_mask"]["versions"]]}), "formula"),
        "a start mask named twice": (
            dict(cfg, start_mask={"versions": cfg["start_mask"]["versions"] * 2}), "twice"),
    }
    for label, (c, needle) in cases.items():
        got = tnconfig.schema_problems(c)
        hit = [x for x in got if needle in x]
        out.append((f"versions: {label} fails the schema check", bool(hit), (hit or got or ["no problem"])[:1]))
    extra = cfg_version(v2cfg, key, fallbacks=v2["fallbacks"] + [
        {"name": cfg["identity"]["noise_prefix"] + "unbaked_" + key, "map_qualified": True}])
    got = fallback_findings(extra)
    out.append(("versions: a next version's fallback that its preset does not bake fails the fallback row",
                any("is no key that version's preset bakes" in x for x in got), got[:1]))
    return out + spawn_record_fixtures(cfg)


def spawn_record_fixtures(cfg):
    """A geography version's spawn record (spawn-cities), class-swept: the shipped record passes, and
    each way to break it fails the schema check with its own message: a missing field, an inland
    lakes body another version names (it reads the version's own chain), the inland lakes or the
    start land guarantee outside the firewall, the spawn lake (the start mask reads it in the Entity
    program) inside it, city offset numbers beside a city fold, a city number that is a frozen
    fallback or no fallback at all, a bearings file no release row lists, a city setting whose first
    value is not random, and a key the version's preset bakes that preset_keys lacks."""
    out = []
    geo = tnconfig.geography_versions(cfg)
    key = next((k for k, vs in geo.items() if tnconfig.spawn_of(vs[-1])), None)
    if key is None:
        return [("spawn: the fixtures need a geography version with a spawn record", False, "")]
    vs = geo[key]
    v = vs[-1]
    sp = v["spawn"]
    i = len(vs) - 1
    out.append(("spawn: the shipped spawn record passes the schema check", not tnconfig.schema_problems(cfg),
                tnconfig.schema_problems(cfg)[:1]))

    def with_spawn(**fields):
        return cfg_version(cfg, key, i, spawn=dict(sp, **fields))

    def fw_without(name):
        return dict(cfg, firewall=dict(cfg["firewall"], **{key: [n for n in cfg["firewall"][key] if n != name]}))
    older_spawned, _, _ = next_version(cfg, key)
    older_spawned["geography"][key]["versions"][-1]["spawn"] = dict(sp)
    older_spawned["geography"][key]["versions"][-1]["city_offset"] = list(v["city_offset"])
    frozen_city = copy.deepcopy(cfg)
    for vv in frozen_city["geography"][key]["versions"]:
        vv["fallbacks"] = [dict(e, frozen=True) if e["name"] == sp["city"] else e for e in vv["fallbacks"]]
    # the city number dropped from every version's fallbacks (one prototype serves every version that
    # lists it, so a later version with the same fold would keep it a fallback)
    no_city_fallback = copy.deepcopy(cfg)
    for vv in no_city_fallback["geography"][key]["versions"]:
        vv["fallbacks"] = [e for e in vv["fallbacks"] if e["name"] != sp["city"]]
    setting = cfg["settings"][sp["city_setting"]]
    unrandom = dict(cfg, settings=dict(cfg["settings"], **{sp["city_setting"]: dict(
        setting, allowed_values=list(setting["allowed_values"][1:]) + setting["allowed_values"][:1])}))
    cases = {
        "a spawn record without its bearings file": (
            cfg_version(cfg, key, i, spawn={k: x for k, x in sp.items() if k != "bearings"}), "must hold exactly"),
        "a next version naming the older version's inland lakes": (older_spawned, "in more than one role or version"),
        "inland lakes outside the firewall": (fw_without(sp["inland_lakes"]), "firewall." + key + " lacks"),
        "the start land guarantee outside the firewall": (fw_without(sp["start_land"]), "firewall." + key + " lacks"),
        "the spawn lake inside the firewall": (
            dict(cfg, firewall=dict(cfg["firewall"], **{key: list(cfg["firewall"][key]) + [sp["spawn_lake"]]})),
            "must stay firewall-clean"),
        "city offset numbers beside a city fold": (cfg_version(cfg, key, i, city_offset=[0, 0]), "must name the city fold"),
        "a city number that is a frozen fallback": (frozen_city, "mirrors a startup setting"),
        "a city number that is no fallback": (no_city_fallback, "mirrors a startup setting"),
        "a bearings file no release row lists": (
            with_spawn(bearings="prototypes/generated/spawn_nowhere_v9.lua"), "no release_registry row lists"),
        "a city setting whose first value is not random": (unrandom, "must start with spawn.random_value"),
        "a baked spawn key preset_keys lacks": (
            dict(cfg, preset_keys=[k for k in cfg["preset_keys"] if k != cfg["keys"]["spawn_lake"]]), "preset_keys lacks"),
    }
    for label, (c, needle) in cases.items():
        got = tnconfig.schema_problems(c)
        hit = [x for x in got if needle in x]
        out.append((f"spawn: {label} fails the schema check", bool(hit), (hit or got or ["no problem"])[:1]))
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


def fixture_frozen(bodies):
    """A tests/frozen.json fixture holding `bodies` under the tnfrozen contract."""
    return {"format": tnfrozen.FORMAT, "hash_fields": list(tnfrozen.HASH_FIELDS), "bodies": bodies}


def fixture_record(registry, sha256="0" * 64, type_="noise-expression"):
    """A record that keeps the tnfrozen contract against `registry`, for its newest milestone."""
    sid = registry[-1]["id"]
    return tnfrozen.record(type_, sha256, tnfrozen.labels_through(registry)[sid][0], sid, "2026-10-28")


def frozen_record_fixtures(td, cfg, registry, rec):
    """Every field of a tests/frozen.json record fails the static frozen row when it breaks the
    tnfrozen contract, the dump label first (relabeled to a dump no registry entry assigns, a typo,
    missing, or one the record's milestone could not have produced), then an unknown milestone, an undefined
    field, a bad date, hash or type, a record that is not a table and a file without the hash's
    field list; the release build fails the dump-label cases too; and the static reading of the
    runner's registry fails closed on a runner that does not assign it once, as a literal that no
    other module-level statement names. `cfg` registers one body, tn_geo_v1, under `rec`."""
    out = []
    name = "tn_geo_v1"
    unassigned = next(f"m{i}" for i in range(1, 1000) if f"m{i}" not in tnfrozen.assigned_labels(registry))

    def with_rec(**fields):
        r = dict(rec)
        for k, v in fields.items():
            if v is None:
                r.pop(k, None)
            else:
                r[k] = v
        return fixture_frozen({name: r})
    two = [{"id": "fx-a", "dumps": ["m1"]}, {"id": "fx-b", "dumps": ["m1", "m2"]}]
    relabeled = f"a record relabeled to {unassigned}, a dump no registry entry assigns"
    label_cases = {relabeled: with_rec(dump=unassigned), "a typo of a dump label (M1)": with_rec(dump="M1"),
                   "a record without a dump label": with_rec(dump=None)}
    cases = dict({k: (v, registry) for k, v in label_cases.items()}, **{
        "a record whose dump its slice could not have produced": (fixture_frozen({name: tnfrozen.record(
            "noise-expression", "0" * 64, "m2", "fx-a", "2026-10-28")}), two),
        "a record naming a slice the registry lacks": (with_rec(slice="no-such-slice"), registry),
        "a record holding a field the contract does not define": (with_rec(note="x"), registry),
        "a record with a malformed date": (with_rec(registered="2026-13-01"), registry),
        "a record with a malformed sha256": (with_rec(sha256="0" * 63), registry),
        "a record of an unknown type": (with_rec(type="noise"), registry),
        "a record that is not a table": (fixture_frozen({name: "m1"}), registry),
        "a registry without the hash's field list": (
            {k: v for k, v in fixture_frozen({name: rec}).items() if k != "hash_fields"}, registry)})
    for label, (fz, reg) in cases.items():
        f = config_frozen_findings(cfg, fz, reg)
        out.append((f"static: {label} fails the frozen row", bool(f), f[:1]))
    p = td / "frozen-record-fixture.json"
    for label, fz in label_cases.items():
        p.write_text(json.dumps(fz), encoding="utf-8")
        probs = build_zip.release_problems(cfg, p)
        out.append((f"release: {label} fails the release build",
                    any(f"tests/frozen.json {name}:" in x and "dump" in x for x in probs), probs[:1]))
    one = '{"id": "a", "dumps": ["m1"]}'
    runners = {
        "a runner without REGISTRY": "X = 1\n",
        "a runner whose REGISTRY is not a literal": "BASE = []\nREGISTRY = BASE + []\n",
        "a runner extending REGISTRY at module level": f"REGISTRY = [{one}]\nREGISTRY.append({one})\n",
        "a runner extending REGISTRY in a class body": f"REGISTRY = [{one}]\nclass X:\n    REGISTRY.append({one})\n",
        "a runner assigning REGISTRY twice": f"REGISTRY = [{one}]\nREGISTRY = [{one}]\n",
        "a runner whose REGISTRY lists a dump label that is not text": 'REGISTRY = [{"id": "a", "dumps": [1]}]\n',
        "a runner reading REGISTRY only in function bodies": f"REGISTRY = [{one}]\ndef f():\n    return REGISTRY\n"}
    for label, text in runners.items():
        rp = td / ("runner-" + str(abs(hash(label)) % 10 ** 8)) / "earth_test.py"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(text, encoding="utf-8")
        reads = label.startswith("a runner reading")
        try:
            got = tnfrozen.runner_registry(rp)
            out.append((f"registry: {label} {'reads' if reads else 'fails closed'}", reads and got == [json.loads(one)],
                        "read" if reads else "read without an error"))
        except tnfrozen.RegistryUnreadable as e:
            out.append((f"registry: {label} {'reads' if reads else 'fails closed'}", not reads, str(e)[:80]))
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
    out.append(("schema: an unknown map key under geography fails", bool(tnconfig.schema_problems(dict(
        cfg, geography=dict(cfg.get("geography") or {}, mars={"map_type_order": "z", "versions": []})))), ""))
    registry = tnfrozen.runner_registry()
    rec = fixture_record(registry)
    fz = td / "frozen-fixture.json"
    # the Map type fallbacks, on the shipped config: the scale mirrors a setting, so it is exempt from
    # tests/frozen.json and never registered, while a frozen fallback is registered like every body
    sk = cfg["keys"]["scale"]
    # each fixture record is the registered one, or carries the body's real hash, which the release
    # build's offline body and snapshot checks hold it to (tnfrozen.body_problems, snapshot_problems)
    real = tnfrozen.body_digests(tnfrozen.offline_bodies(MOD, cfg))
    landed = (load_json(REPO / "tests" / "frozen.json").get("bodies") or {})
    every = {n: landed.get(n) or dict(rec, **(real.get(n) or {})) for n in tnconfig.unregistered_names(cfg, {})}
    fz.write_text(json.dumps(fixture_frozen(every)), encoding="utf-8")
    probs = build_zip.release_problems(cfg, fz)
    out.append(("schema: a fallback that mirrors a setting is exempt from frozen.json",
                not probs and sk not in every and sk in tnconfig.exempt_fallback_names(cfg), probs[:1]))
    rows = [dict(r) for r in cfg["release_registry"]]
    in_release = dict(cfg, release_registry=[dict(rows[0], names=list(rows[0]["names"]) + [sk])] + rows[1:])
    out.append(("schema: a fallback that mirrors a setting in a release row fails the names row (U3)",
                any(sk in x and "U3" in x for x in tnconfig.schema_problems(in_release)), ""))
    # the scale's fallback marked frozen in every version of every map that lists it (one prototype
    # serves them all, so a version that kept it unfrozen would fail on the differing flags instead)
    frozen_fb = copy.deepcopy(cfg)
    for g in frozen_fb["geography"].values():
        for v in g["versions"]:
            v["fallbacks"] = [dict(e, frozen=True) if e["name"] == sk else e for e in v["fallbacks"]]
    out.append(("schema: a frozen fallback in no release row fails the names row",
                any(sk in x and "frozen fallback" in x for x in tnconfig.schema_problems(frozen_fb)), ""))
    out.append(("release: a frozen fallback left unregistered fails the release build",
                any(sk in x for x in build_zip.release_problems(dict(frozen_fb, release_registry=in_release[
                    "release_registry"]), fz)), ""))
    fz.write_text(json.dumps(fixture_frozen(dict(every, **{sk: rec}))), encoding="utf-8")
    probs = build_zip.release_problems(cfg, fz)
    out.append(("schema: a registered fallback fails the release build",
                any(sk in p and "is registered" in p for p in probs), probs[:1]))
    out.append(("schema: defined_names includes the fallbacks", sk in tnconfig.defined_names(cfg)["noise"], ""))
    # a synthetic config of one released body, for the release build and the frozen rows
    fb = dict(cfg, release_registry=[{"release": "0.1.0", "map": "europe", "geography": 1, "names": ["tn_geo_v1"],
                                      "files": []}],
              placeholder=None, presets={"europe": dict(cfg["presets"]["europe"], placeholder=None)},
              preset_order=["europe"], firewall={}, geography={}, start_mask=None, regions=None)
    bad_tg = dict(cfg, toggles={"canals": {"setting": "scale", "preset_key": "tn_canals", "mechanism": "name switch"}},
                  toggle_order=[])
    out.append(("schema: toggles without their toggle_order entry fail", bool(tnconfig.schema_problems(bad_tg)), ""))
    # the three stores of Earth body names (config.lua's firewall and release registry, frozen.json)
    fw_only = dict(fb, firewall={"europe": ["tn_elevation_europe_v1", "tn_geo_europe_v1"]}, release_registry=[])
    out.append(("schema: a firewall body in no release_registry row fails the names row",
                bool(tnconfig.schema_problems(fw_only)), ""))
    fz.write_text(json.dumps(fixture_frozen({})), encoding="utf-8")
    probs = build_zip.release_problems(fw_only, fz)
    out.append(("release: an unregistered firewall body fails the release build",
                any("tn_elevation_europe_v1" in p and "not registered" in p for p in probs), probs[:1]))
    fw_reg = dict(fb, firewall={"europe": ["tn_geo_v1"]})
    fz.write_text(json.dumps(fixture_frozen({})), encoding="utf-8")
    out.append(("release: a released body never frozen fails the release build",
                any("tn_geo_v1" in p for p in build_zip.release_problems(fw_reg, fz)), ""))
    out.append(("static: a config body missing from frozen.json fails the frozen row",
                any("tn_geo_v1" in x for x in config_frozen_findings(fw_reg, fixture_frozen({}), registry)), ""))
    out.append(("static: a registered config body passes the frozen row",
                not config_frozen_findings(fw_reg, fixture_frozen({"tn_geo_v1": rec}), registry),
                config_frozen_findings(fw_reg, fixture_frozen({"tn_geo_v1": rec}), registry)[:1]))
    out += frozen_record_fixtures(td, fw_reg, registry, rec)
    out.append(("schema: a noise name without the noise prefix fails",
                any("noise prefix" in x for x in tnconfig.schema_problems(dict(fb, release_registry=[
                    {"release": "0.1.0", "map": "europe", "geography": 1, "names": ["elevation_x"], "files": []}]))),
                ""))
    out += id_space_fixtures(cfg)
    if cfg.get("geography"):
        stray = cfg_version(cfg, far=cfg["identity"]["noise_prefix"] + "far_unlisted_v1")
        out.append(("schema: a geography name in no release row fails the names row",
                    any("far_unlisted_v1" in x for x in tnconfig.schema_problems(stray)), ""))
        gk = next(iter(cfg["geography"]))
        no_off = copy.deepcopy(cfg)
        no_off["geography"][gk]["versions"][-1].pop("city_offset")
        out.append(("schema: a geography version without its city offset fails",
                    bool(tnconfig.schema_problems(no_off)), ""))
    out.append(("schema: the placeholder's names need no registration",
                not tnconfig.unregistered_names(cfg, {}) if cfg.get("placeholder") else True, ""))
    # each preset's withheld_with (the mods that withhold it) and the water_slider group (D15)
    pk = next(iter(cfg.get("presets") or {}), None)
    if pk:
        for label, wv in (("a string", "alien-biomes"), ("a list holding a number", ["alien-biomes", 3])):
            bad_wh = dict(cfg, presets=dict(cfg["presets"], **{pk: dict(cfg["presets"][pk], withheld_with=wv)}))
            out.append((f"schema: withheld_with as {label} fails", bool(tnconfig.schema_problems(bad_wh)), ""))
        out.append(("schema: the shipped withheld_with lists pass",
                    not any("withheld_with" in x for x in tnconfig.schema_problems(cfg)), ""))
    ws = list(cfg.get("water_slider") or [])
    if ws:
        for label, bad_ws in (("a key outside preset_keys", ws + [{"key": "elevation_lakes", "value": 0}]),
                              ("a non-number value", [dict(ws[0], value="0")] + ws[1:]),
                              ("a key listed twice", ws + [dict(ws[0])]),
                              ("an entry with a stray field", [dict(ws[0], note="x")] + ws[1:])):
            out.append((f"schema: water_slider with {label} fails",
                        bool(tnconfig.schema_problems(dict(cfg, water_slider=bad_ws))), ""))
        out.append(("schema: the shipped water_slider passes",
                    not any("water_slider" in x for x in tnconfig.schema_problems(cfg)), ""))
    return out


def id_space_fixtures(cfg):
    """The id spaces (tnconfig.id_space_problems): a tn_map id or a tn_geo id shared by two maps, a
    geo_id with no release row or registered under another map, a geography id in two rows, a row
    with a geography but no map, a shared Map type order and a non-integer id each fail; the shipped
    config passes."""
    out = [("ids: the shipped config.lua passes the id-space check", not tnconfig.id_space_problems(cfg),
            tnconfig.id_space_problems(cfg)[:1])]
    maps = list(cfg.get("map_order") or [])
    geo = dict(cfg.get("geography") or {})
    rows = [dict(r) for r in cfg.get("release_registry") or []]
    if len(maps) < 2 or not geo or not rows:
        return out + [("ids: the fixtures need two maps, a geography and a release row", False, "")]
    first = next(iter(geo))
    other = next(m for m in maps if m != first)
    g0 = tnconfig.geography(cfg)[first]
    mk = dict(cfg["maps"])
    rows.sort(key=lambda r: r.get("map") != first)

    def other_map(geo_id=None, order="z"):
        """The first map's geography copied under another map, with its own Map type order and, when
        given, its versions' tn_geo id."""
        g = copy.deepcopy(cfg["geography"][first])
        for v in g["versions"]:
            v["geo_id"] = v["geo_id"] if geo_id is None else geo_id
        return dict(geo, **{other: dict(g, map_type_order=order)})
    cases = {
        "a tn_map id shared by two maps": (
            dict(cfg, maps=dict(mk, **{other: dict(mk[other], id=mk[first]["id"])})), "names more than one map"),
        "a tn_map id that is not a positive integer": (
            dict(cfg, maps=dict(mk, **{first: dict(mk[first], id=0)})), "must be a positive integer"),
        "a tn_geo id shared by two maps": (
            dict(cfg, geography=other_map(), release_registry=rows + [dict(rows[0], map=other, release="0.1.1")]),
            "geo_id of more than one version or map"),
        "a geo_id with no release row": (
            cfg_version(cfg, first, geo_id=g0["geo_id"] + 7), "has no release_registry row"),
        "a geo_id registered under another map": (
            dict(cfg, release_registry=[dict(rows[0], map=other)] + rows[1:]), "an id names one map"),
        "a geography id in two release rows": (
            dict(cfg, release_registry=rows + [dict(rows[0], release="0.1.1")]), "appears in more than one row"),
        "a release row with a geography and no map": (
            dict(cfg, release_registry=[{k: v for k, v in rows[0].items() if k != "map"}] + rows[1:]),
            "names its map and its geography id together"),
        "a non-integer geography id": (
            dict(cfg, release_registry=[dict(rows[0], geography="g1")] + rows[1:]), "must be a positive integer"),
        "a Map type order shared by two maps": (
            dict(cfg, geography=other_map(g0["geo_id"] + 1, geo[first]["map_type_order"]),
                 release_registry=rows + [dict(rows[0], map=other, geography=g0["geo_id"] + 1)]),
            "Map type order"),
    }
    for label, (c, needle) in cases.items():
        probs = tnconfig.schema_problems(c)
        hit = [p for p in probs if needle in p]
        out.append((f"ids: {label} fails the schema check", bool(hit), (hit or probs or ["no problem"])[:1]))
    return out


def storage_contract_fixtures(td):
    """The stored-records scan: another file indexing the warning store (by dot or by a string key),
    a record_warning call with an unknown key and one with a computed key each fail."""
    out = []
    cases = {
        "storage: another file appends to storage.earth.warnings": (
            "scripts/start.lua", "local e = storage.earth\ne.warnings[#e.warnings + 1] = {\"x\"}\n"),
        "storage: another file writes a sent count by string key": (
            "scripts/start.lua", "storage.earth[\"sent\"] = {}\n"),
        "storage: record_warning with a key messages.keys lacks": (
            "scripts/start.lua", "local g = require(\"scripts.guards\")\ng.record_warning(\"no_such_message\", {})\n"),
        "storage: record_warning with a computed key": (
            "scripts/start.lua", "local g = require(\"scripts.guards\")\nlocal k = \"withheld\" .. \"_beside\"\n"
                                 "g.record_warning(k, {})\n"),
        "storage: another file replaces storage.earth wholesale": (
            "scripts/start.lua", "storage.earth = {schema = 1}\n"),
        "storage: another file replaces storage.map_type by string key": (
            "scripts/start.lua", "storage[\"map_type\"] = nil\n"),
    }
    for label, (path, text) in cases.items():
        m = td / ("mod-st-" + str(abs(hash(label)) % 10 ** 8)) / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, path, text)
        f = storage_contract_findings(m)
        out.append((label, bool(f), f[:1]))
    return out


def append_only_fixtures(cfg, fz):
    """The append-only check on fixture references: a dropped or re-hashed registered body, a record
    relabeled (to another dump or a mistyped label), re-sliced, re-dated, retyped or given a field, a
    changed hash field list, a moved tn_map id, a tn_geo id moved to another map, a removed or
    renamed stored message key and two references disagreeing on a hash or a dump label each fail;
    the tree against itself and an added body pass; and a ref that does not resolve, or a resolving
    ref without the file, fails closed."""
    out = []
    import copy
    ref = {"frozen": copy.deepcopy(fz), "cfg": copy.deepcopy(cfg)}
    out.append(("append-only: the tree against itself passes", not append_only_findings(fz, cfg, {"main": ref}),
                append_only_findings(fz, cfg, {"main": ref})[:1]))
    bodies = sorted((fz.get("bodies") or {}))
    maps = list(cfg.get("map_order") or [])
    msg = sorted(((cfg.get("messages") or {}).get("keys") or {}))
    if not bodies or len(maps) < 2 or not msg or not cfg.get("release_registry"):
        return out + [("append-only: the fixtures need a registered body, two maps, a message and a release row",
                       False, "")]
    v = bodies[0]
    added = copy.deepcopy(fz)
    added["bodies"]["tn_fixture_added_v1"] = {"type": "noise-expression", "sha256": "1" * 64}
    out.append(("append-only: an added body passes", not append_only_findings(added, cfg, {"main": ref}), ""))
    dropped = copy.deepcopy(fz)
    del dropped["bodies"][v]
    rehashed = copy.deepcopy(fz)
    rehashed["bodies"][v]["sha256"] = "2" * 64
    moved_id = copy.deepcopy(cfg)
    moved_id["maps"][maps[0]]["id"] = 99
    moved_geo = copy.deepcopy(cfg)
    moved_geo["release_registry"][0]["map"] = maps[1]
    no_msg = copy.deepcopy(cfg)
    del no_msg["messages"]["keys"][msg[0]]
    renamed = copy.deepcopy(cfg)
    renamed["messages"]["keys"][msg[0]] = "renamed-" + renamed["messages"]["keys"][msg[0]]
    other = copy.deepcopy(ref)
    other["frozen"]["bodies"][v]["sha256"] = "3" * 64
    # every field of a landed record is fixed, the dump label the gate reads a body from first: a hand
    # relabel (to a later milestone's dump or a mistyped one) moves a record as a new hash does
    own = str(fz["bodies"][v].get("dump"))
    later = next(f"m{i}" for i in range(1, 1000) if f"m{i}" != own)

    def edited(**fields):
        e = copy.deepcopy(fz)
        e["bodies"][v].update(fields)
        return e
    other_label = copy.deepcopy(ref)
    other_label["frozen"]["bodies"][v]["dump"] = later
    fields_moved = copy.deepcopy(fz)
    fields_moved["hash_fields"] = [f for f in (fz.get("hash_fields") or []) if f != "parameters"]
    for label, (wfz, wcfg, refs) in {
            "a dropped registered body": (dropped, cfg, {"main": ref}),
            "a registered body re-hashed in place": (rehashed, cfg, {"main": ref}),
            "a re-hashed body that only origin/main registers (a stale local main)": (
                rehashed, cfg, {"main": {"frozen": dropped, "cfg": cfg}, "origin/main": ref}),
            f"a registered record relabeled to {later}": (edited(dump=later), cfg, {"main": ref}),
            "a registered record's dump label mistyped": (edited(dump=own.upper() if own.upper() != own else own + "x"),
                                                          cfg, {"main": ref}),
            "a registered record re-sliced": (edited(slice=str(fz["bodies"][v].get("slice")) + "-x"), cfg,
                                              {"main": ref}),
            "a registered record re-dated": (edited(registered="2000-01-01"), cfg, {"main": ref}),
            "a registered record retyped": (edited(type="noise-function" if fz["bodies"][v].get("type") !=
                                                   "noise-function" else "noise-expression"), cfg, {"main": ref}),
            "a registered record given a field": (edited(note="x"), cfg, {"main": ref}),
            "a changed hash field list": (fields_moved, cfg, {"main": ref}),
            "a moved tn_map id": (fz, moved_id, {"main": ref}),
            "a tn_geo id moved to another map": (fz, moved_geo, {"main": ref}),
            "a removed stored message key": (fz, no_msg, {"main": ref}),
            "a renamed stored message key": (fz, renamed, {"main": ref}),
            "two references disagreeing on a hash": (fz, cfg, {"main": ref, "origin/main": other}),
            "two references disagreeing on a dump label": (fz, cfg, {"main": ref, "origin/main": other_label})}.items():
        f = append_only_findings(wfz, wcfg, refs)
        out.append((f"append-only: {label} fails", bool(f), f[:1]))
    out += unreleased_moves_fixtures(cfg, fz, ref, v, dropped, rehashed)
    for label, (path, refs) in {
            "a ref that does not resolve": ("tests/frozen.json", ["refs/heads/tn-fixture-no-such-ref"]),
            "a resolving ref without the file": ("tests/tn-fixture-no-such-file.json", ["HEAD"])}.items():
        try:
            reference_files(path, REPO, refs)
            out.append((f"append-only: {label} fails closed", False, "read without an error"))
        except ReferenceUnreadable as e:
            out.append((f"append-only: {label} fails closed", True, str(e)[:80]))
    return out


def unreleased_moves_fixtures(cfg, fz, ref, name, dropped, rehashed):
    """The unreleased waiver: a record moved or dropped passes only at the exact hash the waiver lists
    (append-only and snapshots alike), a retired tn_geo id only when listed; a release tag voids the
    waiver and fails the row while it holds entries, a broken file fails closed, and tools/refreeze.py
    records each hash a record leaves."""
    import copy
    import refreeze
    out = []
    rec = fz["bodies"][name]
    moves = {"format": tnfrozen.MOVES_FORMAT, "ruling": "fixture", "geographies": [], "records": {name: [rec["sha256"]]}}
    wrong = dict(moves, records={name: ["4" * 64]})
    main = {"main": ref}
    for label, wfz in (("a re-hashed body", rehashed), ("a dropped body", dropped)):
        f = append_only_findings(wfz, cfg, main, moves)
        out.append((f"unreleased: {label} the waiver lists at its landed hash passes", not f, f[:1]))
        out.append((f"unreleased: {label} the waiver lists at another hash fails",
                    bool(append_only_findings(wfz, cfg, main, wrong)), ""))
    snap = {"format": tnfrozen.SNAPSHOT_FORMAT, "bodies": {name: rec}, "sha256": tnfrozen.key_of({name: rec})}
    out.append(("unreleased: a snapshot's record the waiver lists passes",
                not tnfrozen.snapshot_problems(rehashed, {"fx": snap}, moves), ""))
    out.append(("unreleased: a snapshot's record the waiver does not list fails",
                bool(tnfrozen.snapshot_problems(rehashed, {"fx": snap}, wrong)), ""))
    row = next(r for r in cfg["release_registry"] if "geography" in r)
    gone = copy.deepcopy(cfg)
    gone["release_registry"] = [r for r in cfg["release_registry"] if r != row]
    out.append(("unreleased: a tn_geo id that left the registry fails", bool(append_only_findings(fz, gone, main)), ""))
    f = append_only_findings(fz, gone, main, dict(moves, geographies=[row["geography"]]))
    out.append(("unreleased: a tn_geo id the waiver retires passes", not f, f[:1]))
    with tempfile.TemporaryDirectory(prefix="tn-moves-") as td:
        p = Path(td) / "tests" / "unreleased-moves.json"
        p.parent.mkdir()
        p.write_text(json.dumps(moves), encoding="utf-8")
        f, got = moves_findings(td, [])
        out.append(("unreleased: the waiver applies while no release exists", not f and got == moves, f[:1]))
        f, got = moves_findings(td, ["refs/tags/v0.1.0"])
        out.append(("unreleased: a release tag voids a waiver that holds entries", bool(f) and got is None, ""))
        out.append(("unreleased: active_moves reads nothing once a release exists",
                    tnfrozen.active_moves(["refs/tags/v0.1.0"], p) is None, ""))
        p.write_text("{", encoding="utf-8")
        f, got = moves_findings(td, [])
        out.append(("unreleased: a waiver that does not parse fails closed", bool(f) and got is None, ""))
        p.write_text(json.dumps(dict(moves, ruling="")), encoding="utf-8")
        f, got = moves_findings(td, [])
        out.append(("unreleased: a waiver naming no ruling fails closed", bool(f) and got is None, ""))
    pre = cfg["identity"]["noise_prefix"]
    gone_n, kept_n, new_n = f"{pre}fx_gone_v1", f"{pre}fx_kept_v1", f"{pre}fx_new_v1"
    bodies = {gone_n: tnfrozen.record("noise-expression", "5" * 64, "m1", "extras", "2026-10-30"),
              kept_n: tnfrozen.record("noise-expression", "6" * 64, "m1", "extras", "2026-10-30"),
              f"{pre}fx_m2_v1": tnfrozen.record("noise-expression", "7" * 64, "m2", "extras", "2026-10-30")}
    dump = {"noise-expression": {kept_n: {"type": "noise-expression", "name": kept_n, "expression": "1"},
                                 new_n: {"type": "noise-expression", "name": new_n, "expression": "2"}}}
    empty = dict(moves, records={})
    nf, nm, rep = refreeze.refreeze({"bodies": bodies}, empty, {"m1": dump}, cfg, "2026-10-30", "extras",
                                    [(kept_n, bodies[kept_n])])
    out.append(("unreleased: refreeze moves, drops and adds, and names each hash left behind",
                rep["changed"] == [kept_n] and rep["dropped"] == [gone_n] and rep["added"] == [new_n] and
                rep["unchecked"] == [f"{pre}fx_m2_v1"] and nm["records"] == {gone_n: ["5" * 64], kept_n: ["6" * 64]} and
                nf["bodies"][kept_n]["slice"] == "extras" and gone_n not in nf["bodies"], str(rep)[:120]))
    with tempfile.TemporaryDirectory(prefix="tn-seal-") as td:
        fx_registry = [{"id": "fx-a", "dumps": ["m1"]}, {"id": "fx-b", "dumps": ["m1"]}]
        kept = tnfrozen.record("noise-expression", "6" * 64, "m1", "fx-a", "2026-10-30")
        stale = {gone_n: tnfrozen.record("noise-expression", "5" * 64, "m1", "fx-a", "2026-10-30")}
        snap = {"format": tnfrozen.SNAPSHOT_FORMAT, "bodies": stale, "sha256": tnfrozen.key_of(stale)}
        (Path(td) / "fx-a.json").write_text(json.dumps({"slice": "fx-a", "frozen": snap}), encoding="utf-8")
        (Path(td) / "fx-b.json").write_text(json.dumps({"slice": "fx-b"}), encoding="utf-8")
        sealed_fz = {"bodies": {kept_n: kept}}
        out.append(("seal: the stale snapshot fails with no waiver",
                    bool(tnfrozen.snapshot_problems(sealed_fz, {"fx": snap})), ""))
        ns, mans = refreeze.seal(dict(moves, geographies=[1]), sealed_fz, fx_registry, td)
        found = tnfrozen.snapshot_problems(sealed_fz, {str(p): m["frozen"] for p, m in mans.items()})
        out.append(("seal: the waiver empties, the snapshot follows the registry and a manifest without one stays",
                    ns["records"] == {} and ns["geographies"] == [] and not found and
                    [Path(p).name for p in mans] == ["fx-a.json"], found[:1]))
        moves_ok, _ = moves_findings_on(td, ns)
        out.append(("seal: a sealed waiver passes with a release tag", moves_ok, ""))
    # 0.3.0's collapse (tests/collapsed.json): no release voids it, it excuses a dropped record at its landed hash
    # only, and it fails closed while the tree still holds what it names gone or when it breaks its shape
    col = {"format": tnfrozen.COLLAPSE_FORMAT, "ruling": "fixture", "versions": [], "geographies": [], "frames": [],
           "records": {name: [rec["sha256"]]}, "files": []}
    f = append_only_findings(dropped, cfg, main, tnfrozen.with_collapse(None, col))
    out.append(("collapse: a dropped record the collapse lists at its landed hash passes", not f, f[:1]))
    out.append(("collapse: a dropped record the collapse lists at another hash fails",
                bool(append_only_findings(dropped, cfg, main, tnfrozen.with_collapse(
                    None, dict(col, records={name: ["4" * 64]})))), ""))
    with tempfile.TemporaryDirectory(prefix="tn-collapse-") as td:
        p = Path(td) / "tests" / "collapsed.json"
        p.parent.mkdir()
        p.write_text(json.dumps(col), encoding="utf-8")
        f, got = collapse_findings(td, dropped, cfg)
        out.append(("collapse: a collapse whose records left the registry applies", not f and got == col, f[:1]))
        f, got = collapse_findings(td, fz, cfg)
        out.append(("collapse: a record the registry still holds fails closed", bool(f) and got is None, ""))
        p.write_text(json.dumps(dict(col, format="x")), encoding="utf-8")
        f, got = collapse_findings(td, dropped, cfg)
        out.append(("collapse: a collapse of another format fails closed", bool(f) and got is None, ""))
    return out


def moves_findings_on(td, moves):
    """(no finding, the findings) of `moves` as a checkout's waiver with a release tag present."""
    p = Path(td) / "tests" / "unreleased-moves.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(moves), encoding="utf-8")
    f, _ = moves_findings(td, ["refs/tags/v0.1.0"])
    return not f, f


def thin_version_fixtures(cfg):
    """A thin geography version (config.lua `over`): it may name an older version's chain, fit and sets
    and takes only its entry and basin as its own; the same names without `over`, or an `over` that names
    no older entry, fail."""
    out = []
    key = sorted(_as_dict(cfg.get("geography")))[0]

    def with_version(**fields):
        c = copy.deepcopy(cfg)
        vs = c["geography"][key]["versions"]
        v = dict(copy.deepcopy(vs[-1]), entry="tn_fixture_entry_v99", geo_id=9999, **fields)
        vs.append(v)
        return c

    def refused(c):
        try:
            tnconfig.geography_versions(c)
        except tnconfig.ConfigError as e:
            return str(e)
        return ""
    older = cfg["geography"][key]["versions"][-1]["entry"]
    basin = {"name": "tn_fixture_basin_v1", "u": 1, "v": 1, "radius_px": 1}
    f = refused(with_version(over=older, basin=basin))
    out.append(("thin version: names an older version's chain and sets", not f, f[:120]))
    out.append(("thin version: the same names without over fail", bool(refused(with_version(basin=basin))), ""))
    out.append(("thin version: over naming no older entry fails",
                bool(refused(with_version(over="tn_fixture_none_v1", basin=basin))), ""))
    out.append(("thin version: over without a basin fails", bool(refused(with_version(over=older))), ""))
    return out


def bandfix_digest_fixtures(cfg):
    """A tn_geo id appended to a map's band-fix tables keeps the digest they were built under; a moved first
    id or any other edit of the group changes it."""
    B = cfg["bandfix"]
    key = sorted(B["tables"])[0]
    base = tnconfig.bandfix_digest(B)
    appended, moved, other = copy.deepcopy(B), copy.deepcopy(B), copy.deepcopy(B)
    appended["tables"][key]["geographies"].append(9999)
    moved["tables"][key]["geographies"][0] = 9999
    other["version"] = B["version"] + 1
    row = copy.deepcopy(B)
    row["generations"] = {key: [{"version": B["version"] + 1, "geographies": [9999]}]}
    return [("band fix: a tn_geo id appended keeps the tables' digest", tnconfig.bandfix_digest(appended) == base, ""),
            ("band fix: a generation row keeps the tables' digest", tnconfig.bandfix_digest(row) == base, ""),
            ("band fix: a generation's tn_geo reads its version, any other the group's",
             tnconfig.bandfix_generation(row, key, 9999)[0] == B["version"] + 1 and
             tnconfig.bandfix_generation(row, key, B["tables"][key]["geographies"][0])[0] == B["version"], ""),
            ("band fix: every generation's tables are release inputs",
             f"scripts/generated/bandfix_{key}_s1_v{B['version'] + 1}.lua" in release_input_files(dict(cfg, bandfix=row)) and
             f"scripts/generated/bandfix_{key}_s1_v{B['version']}.lua" in release_input_files(cfg), ""),
            ("band fix: the first tn_geo id moved changes it", tnconfig.bandfix_digest(moved) != base, ""),
            ("band fix: the next rule's first id passes", not tnconfig.bandfix_next_problems(cfg), ""),
            ("band fix: a next rule that reaches a released tn_geo fails",
             bool(tnconfig.bandfix_next_problems(dict(cfg, bandfix_next=dict(cfg["bandfix_next"], from_geo=18)))), ""),
            ("band fix: another edit of the group changes it", tnconfig.bandfix_digest(other) != base, "")]


def release_input_fixtures(cfg):
    """The landed bodies' inputs on fixture references built from the working tree: a regenerated
    file, a changed coast, spawn or coordinates constant, a re-pointed key, a city row edited, a city
    added, a geography version edited in place, a landed release row edited or dropped and a map's
    geometry moved each fail; the tree against itself, a version appended, a new constant or map
    table added and a map's display name changed pass; a reference without a release row freezes
    nothing; and a reference whose landed row names a file it lacks fails closed."""
    out = []
    base = work_release_inputs(cfg)
    ref = copy.deepcopy(base)
    files = sorted(base["files"])
    tables = sorted(base["tables"])
    maps = list(cfg.get("map_order") or [])
    geo = sorted(_as_dict(cfg.get("geography")))
    if not files or not tables or not geo or not cfg.get("release_registry") or not maps:
        return [("release inputs: the fixtures need a landed row, a generated file, a table and a geography", False,
                 "")]
    tk = sorted(base["tables"][tables[0]], key=str)[0]

    def work(edit):
        w = copy.deepcopy(base)
        edit(w)
        return w

    def set_path(w, path, value):
        d = w["cfg"]
        for part in path[:-1]:
            d = d[part]
        d[path[-1]] = value

    def first_city(w):
        cities = _as_dict(w["tables"][tables[0]][tk]).get("cities")
        return cities, sorted(_as_dict(cities), key=str)[0] if _as_dict(cities) else None

    def edit_city(w):
        cities, c = first_city(w)
        cities[c]["lon"] = float(cities[c]["lon"]) + 0.5

    def add_city(w):
        cities, _ = first_city(w)
        cities["tn-fixture-city"] = {"name": "Fixture", "country": "Nowhere", "lon": 0.0, "lat": 0.0}

    def edit_version(w):
        w["cfg"]["geography"][geo[0]]["versions"][0]["city_offset"] = [1, 1]

    def add_version(w):
        vs = w["cfg"]["geography"][geo[0]]["versions"]
        vs.append(dict(copy.deepcopy(vs[-1]), entry="tn_fixture_entry_v99"))

    def edit_row(w):
        w["cfg"]["release_registry"][0]["files"] = list(w["cfg"]["release_registry"][0]["files"])[:-1]

    def drop_row(w):
        del w["cfg"]["release_registry"][0]

    def regen(w):
        w["files"][files[0]] = "0" * 64

    def drop_file(w):
        w["files"][files[0]] = None

    def first_number(section):
        return next(k for k, v in sorted(_as_dict(cfg.get(section)).items()) if isinstance(v, (int, float))
                    and not isinstance(v, bool))
    coast_k, coord_k = first_number("coast"), first_number("coordinates")
    warp_ids = list(cfg["coast"]["warp"]["geographies"])
    fold_ids = list(cfg["coast"]["edge_band"]["fold_geographies"])
    m0 = maps[0]
    geom_k = next(k for k, v in sorted(_as_dict(cfg["maps"][m0]).items()) if isinstance(v, (int, float))
                  and not isinstance(v, bool) and k != "id")
    lake = _as_dict(_as_dict(cfg.get("spawn")).get("lake"))
    key0 = sorted(_as_dict(cfg.get("keys")))[0]
    city_sets = sorted(release_settings(cfg))
    if not city_sets:
        return out + [("release inputs: the fixtures need a geography version with a spawn-city setting", False, "")]
    cs = city_sets[0]

    def city_values(w, edit):
        vals = list(w["cfg"]["settings"][cs]["allowed_values"])
        w["cfg"]["settings"][cs] = dict(w["cfg"]["settings"][cs], allowed_values=edit(vals))

    failing = {
        "a regenerated file": regen,
        "a landed file removed": drop_file,
        f"coast.{coast_k} changed": lambda w: set_path(w, ("coast", coast_k), cfg["coast"][coast_k] + 1),
        f"coordinates.{coord_k} changed": lambda w: set_path(w, ("coordinates", coord_k),
                                                             cfg["coordinates"][coord_k] + 1),
        "spawn.lake.distance changed": lambda w: set_path(w, ("spawn", "lake", "distance"),
                                                          lake.get("distance", 0) + 1),
        "number_format changed": lambda w: set_path(w, ("number_format",), "%.6g"),
        f"keys.{key0} re-pointed": lambda w: set_path(w, ("keys", key0), "tn_fixture_key"),
        f"maps.{m0}.{geom_k} moved": lambda w: set_path(w, ("maps", m0, geom_k), cfg["maps"][m0][geom_k] + 1),
        "a coast constant removed": lambda w: w["cfg"]["coast"].pop(coast_k),
        "a tn_geo id dropped from coast.warp.geographies": lambda w: set_path(w, ("coast", "warp", "geographies"),
                                                                              warp_ids[:-1]),
        "coast.warp.geographies reordered": lambda w: set_path(w, ("coast", "warp", "geographies"), warp_ids[::-1]),
        "a city row edited": edit_city,
        "a city added to a released table": add_city,
        "a released map table removed": lambda w: w["tables"][tables[0]].pop(tk),
        "a geography version edited in place": edit_version,
        "a landed release row edited": edit_row,
        "a landed release row dropped": drop_row,
        f"settings.{cs} cities swapped": lambda w: city_values(w, lambda v: v[:1] + [v[2], v[1]] + v[3:]),
        f"settings.{cs} a city appended": lambda w: city_values(w, lambda v: v + ["tn-fixture-city"]),
        f"settings.{cs} a city inserted": lambda w: city_values(w, lambda v: v[:2] + ["tn-fixture-city"] + v[2:]),
        f"settings.{cs} sorted": lambda w: city_values(w, lambda v: v[:1] + sorted(v[1:], reverse=True)),
        f"settings.{cs} a city removed": lambda w: city_values(w, lambda v: v[:-1]),
        f"settings.{cs} removed": lambda w: w["cfg"]["settings"].pop(cs),
    }
    passing = {
        "the tree against itself": lambda w: None,
        f"settings.{cs} order key changed": lambda w: set_path(w, ("settings", cs, "order"), "z-fixture"),
        "a new setting added": lambda w: set_path(w, ("settings", "tn_fixture_setting"),
                                                  {"name": "x", "allowed_values": ["a"]}),
        "a geography version appended": add_version,
        "a tn_geo id appended to coast.warp.geographies": lambda w: set_path(w, ("coast", "warp", "geographies"),
                                                                             warp_ids + [9999]),
        "a tn_geo id appended to coast.edge_band.fold_geographies": lambda w: set_path(
            w, ("coast", "edge_band", "fold_geographies"), fold_ids + [9999]),
        "a new coast constant": lambda w: set_path(w, ("coast", "tn_fixture_new"), 1),
        "a new map table": lambda w: w["tables"][tables[0]].__setitem__("tn_fixture_map", {"version": 1}),
        f"maps.{m0}.display renamed": lambda w: set_path(w, ("maps", m0, "display"), "Fixture"),
    }
    # 0.3.0's collapse (tests/collapsed.json): the tree's band-fix group still counts the tables the collapse dropped
    col = tnfrozen.read_collapse() or None
    for label, edit in failing.items():
        f = release_input_findings(work(edit), {"main": ref}, col)
        out.append((f"release inputs: {label} fails", bool(f), f[:1]))
    for label, edit in passing.items():
        f = release_input_findings(work(edit), {"main": ref}, col)
        out.append((f"release inputs: {label} passes", not f, f[:1]))
    unlanded = copy.deepcopy(ref)
    unlanded["cfg"] = dict(copy.deepcopy(cfg), release_registry=[])
    f = release_input_findings(work(regen), {"main": unlanded})
    out.append(("release inputs: a reference without a release row freezes nothing", not f, f[:1]))
    hollow = copy.deepcopy(ref)
    hollow["files"][files[0]] = None
    f = release_input_findings(base, {"main": hollow})
    out.append(("release inputs: a landed row naming a file its reference lacks fails closed", bool(f), f[:1]))
    out += collapse_input_fixtures(cfg, base, ref, geo, files, col)
    return out


def collapse_input_fixtures(cfg, base, ref, geo, files, col=None):
    """0.3.0's collapse (tests/collapsed.json, `col`) on the release inputs: a geography version, a retired release
    row, a frame row's lost name and a generated file pass only when the collapse lists them, and fail when it does
    not (the tree's own collapse, without that entry)."""
    out = []
    v0 = cfg["geography"][geo[0]]["versions"][0]
    row = next(r for r in cfg["release_registry"] if r.get("geography") is not None and r.get("names"))
    lost = sorted(row["names"])[0]
    c0 = {"versions": [], "geographies": [], "frames": [], "records": {}, "files": list((col or {}).get("files") or [])}
    c = dict(c0, versions=[v0["geo_id"]])

    def work(edit):
        w = copy.deepcopy(base)
        edit(w)
        return w

    def drop_version(w):
        w["cfg"]["geography"][geo[0]]["versions"] = w["cfg"]["geography"][geo[0]]["versions"][1:]

    def drop_row(w):
        w["cfg"]["release_registry"] = [r for r in w["cfg"]["release_registry"] if r is not row and r != row]

    def trim_row(w):
        for r in w["cfg"]["release_registry"]:
            if r == row:
                r["names"] = [n for n in r["names"] if n != lost]

    def drop_file(w):
        w["files"][files[0]] = None

    none_row = next((r for r in cfg["release_registry"] if r.get("geography") is None and len(r.get("names") or []) > 1),
                    None)
    none_lost = sorted(none_row["names"])[0] if none_row else None

    def trim_none_row(w):
        for r in w["cfg"]["release_registry"]:
            if r == none_row:
                r["names"] = [n for n in r["names"] if n != none_lost]

    cases = (
        ("a geography version dropped", drop_version, c, dict(c, versions=[9999])),
        ("a release row retired", drop_row, dict(c, versions=[], geographies=[row["geography"]]),
         dict(c, versions=[], geographies=[9999])),
        ("a frame row that lost a dropped name", trim_row,
         dict(c, versions=[], frames=[row["geography"]], records={lost: ["0" * 64]}),
         dict(c, versions=[], frames=[row["geography"]], records={})),
        ("a generated file dropped", drop_file, dict(c, versions=[], files=c0["files"] + [files[0]]), c0),
        ("a row of no geography that lost a dropped name", trim_none_row,
         dict(c, versions=[], records={none_lost: ["0" * 64]}), dict(c, versions=[], records={})),
    )
    out.append(("collapse: the tree against itself passes under its own collapse",
                not release_input_findings(base, {"main": ref}, c0), release_input_findings(base, {"main": ref}, c0)[:1]))
    for label, edit, listed, unlisted in cases:
        w = work(edit)
        f = release_input_findings(w, {"main": ref}, listed)
        out.append((f"collapse: {label} the collapse lists passes", not f, f[:1]))
        out.append((f"collapse: {label} the collapse does not list fails",
                    bool(release_input_findings(w, {"main": ref}, unlisted)), ""))
    return out


def _mod_copy(td, label):
    m = Path(td) / f"mod-{label}" / "terra-nauvis"
    shutil.copytree(MOD, m)
    return m


def _edit(m, rel, old, new, where="replace"):
    """Edit one file of a mod copy; returns False when the edit does not apply (the control fails)."""
    p = Path(m) / rel
    text = p.read_text(encoding="utf-8")
    if where == "append":
        out = text + new
    elif where == "prepend":
        out = new + text
    else:
        out = text.replace(old, new, 1)
    if out == text:
        return False
    p.write_text(out, encoding="utf-8", newline="\n")
    return True


def bodies_fixtures(td, cfg, fz):
    """The bodies row on mod copies: the unchanged mod passes; the review's two probes (the spawn
    lake's distance halved in spawn.lua, the geo tile chain moved in coast.lua), a frozen fallback's
    body moved in presets.lua, a registered body no longer defined and an unregistered Earth body
    added each fail; a Lua error, a require outside the mod and a text built from an address fail
    closed."""
    out = []
    pre = cfg["identity"]["noise_prefix"]
    reg = sorted((fz.get("bodies") or {}))
    lakes = [n for n in reg if n.startswith(pre + "spawn_lake")]
    gxs = [n for n in reg if n.startswith(pre + "gx_")]
    frozen_fb = sorted(set(tnconfig.frozen_fallback_names(cfg)) & set(reg))
    m = _mod_copy(td, "bodies-ok")
    f, b = bodies_findings(m, fz, cfg)
    out.append(("bodies: the unchanged mod passes", not f and bool(b), f[:1]))
    cases = {
        "the spawn lake's distance halved in spawn.lua (the review's probe) fails": (
            ("prototypes/expressions/spawn.lua", 'lake_d = "sqrt(', 'lake_d = "0.5 * sqrt(', "replace"),
            lakes, "changed in place"),
        "the geo tile chain moved in coast.lua (the review's probe) fails": (
            ("prototypes/expressions/coast.lua", 'def(g.gx, "x + " .. g.cx)', 'def(g.gx, "x + 7 + " .. g.cx)',
             "replace"), gxs, "changed in place"),
        "a frozen fallback's body moved in presets.lua fails": (
            ("prototypes/presets.lua", 'type(value) == "number" and num(value) or value',
             '"1 + " .. tostring(value)', "replace"), frozen_fb, "changed in place"),
        "a registered body the data stage no longer defines fails": (
            ("prototypes/presets.lua", "data:extend(fallbacks)", "", "replace"), frozen_fb, "is not defined"),
        "an unregistered Earth body fails": (
            ("data.lua", None, f'\ndata:extend({{{{type = "noise-expression", name = "{pre}fixture_unregistered_v1", '
                               f'expression = "1"}}}})\n', "append"), [f"{pre}fixture_unregistered_v1"],
            "is not registered"),
        "a Lua error in the data stage fails closed": (
            ("data.lua", None, '\nerror("fixture")\n', "append"), [], "did not run"),
        "a require of a module outside the mod fails closed": (
            ("data.lua", None, 'require("util")\n', "prepend"), [], "did not run"),
        "a text built from a table's address fails closed": (
            ("data.lua", None, "\nlocal fixture = tostring({})\n", "append"), [], "did not run"),
    }
    for i, (label, ((rel, old, new, where), names, needle)) in enumerate(cases.items()):
        m = _mod_copy(td, f"bodies-{i}")
        if not _edit(m, rel, old, new, where):
            out.append((f"bodies: {label}", False, ["the edit did not apply"]))
            continue
        f, _ = bodies_findings(m, fz, cfg)
        hit = [x for x in f if needle in x]
        ok = bool(hit) and all(any(n in x for x in hit) for n in names)
        if label.startswith(("the spawn", "the geo", "a frozen", "a registered")):
            ok = ok and bool(names)
        out.append((f"bodies: {label}", ok, f[:1]))
    return out


def landing_fixtures(td, cfg, fz):
    """A zip that leaves the checkout lands (build_zip.build with landing): the first lands with its
    bodies and its registry's snapshot in its build record, and the same tree lands again beside it;
    a zip already in the folder whose body this build changed (the spawn lake probe) or dropped (an
    extra body), one that cannot be read offline, and a build record whose snapshot holds a record
    the registry moved each refuse the landing; a folder inside the checkout is no landing."""
    out = []
    folder = Path(td) / "landing-ok"
    try:
        _, _, rec = build_zip.build(folder, landing=True)
        snap = rec.get("frozen") or {}
        offline = {n for n, r in (fz.get("bodies") or {}).items() if r.get("dump") in tnfrozen.OFFLINE_DUMPS}
        ok = (set(rec.get("bodies") or {}) >= offline and
              snap.get("sha256") == tnfrozen.key_of(snap.get("bodies")) and snap.get("bodies") == fz.get("bodies"))
        out.append(("landing: a first zip lands with its bodies and its registry's snapshot in its build record", ok, ""))
        build_zip.build(folder, landing=True)
        out.append(("landing: the same tree lands again beside its own zip", True, ""))
    except build_zip.BuildError as e:
        out.append(("landing: a first zip lands and the same tree lands again", False, str(e)[:120]))
    pre = cfg["identity"]["noise_prefix"]

    def refuses(label, prepare, needle):
        d = Path(td) / f"landing-{abs(hash(label)) % 10 ** 8}"
        d.mkdir(parents=True)
        try:
            prepare(d)
        except Exception as e:
            out.append((f"landing: {label}", False, f"fixture: {type(e).__name__}: {e}"))
            return
        try:
            build_zip.build(d, landing=True)
            out.append((f"landing: {label}", False, "landed"))
        except build_zip.BuildError as e:
            out.append((f"landing: {label}", needle in str(e), str(e)[:160]))

    def old_zip(d, rel, old, new, where):
        m = _mod_copy(d, "old")
        if not _edit(m, rel, old, new, where):
            raise RuntimeError("the edit did not apply")
        build_zip.build(d, mod_dir=m)
    refuses("a zip in the folder whose spawn lake this build changed refuses",
            lambda d: old_zip(d, "prototypes/expressions/spawn.lua", 'lake_d = "sqrt(', 'lake_d = "0.5 * sqrt(', "replace"),
            "which this build changed")
    refuses("a zip in the folder with a body this build dropped refuses",
            lambda d: old_zip(d, "data.lua", None, f'\ndata:extend({{{{type = "noise-expression", name = '
                                                    f'"{pre}fixture_landed_v1", expression = "1"}}}})\n', "append"),
            "which this build dropped")
    refuses("a zip in the folder that cannot be read offline refuses (fail closed)",
            lambda d: (d / f"{cfg['identity']['id']}_0.0.1.zip").write_bytes(b"not a zip"), "cannot be read offline")

    def moved_snapshot(d):
        build_zip.build(d)
        rec_path = d / f"{cfg['identity']['id']}_{cfg['identity']['version']}.build.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        moved = json.loads(json.dumps(fz))
        name = sorted(moved["bodies"])[0]
        moved["bodies"][name]["sha256"] = "8" * 64
        rec["frozen"] = tnfrozen.snapshot(moved, tnfrozen.runner_registry(), tnfrozen.runner_registry()[-1]["id"])
        rec_path.write_text(json.dumps(rec), encoding="utf-8")
    refuses("a build record in the folder whose snapshot holds a record the registry moved refuses", moved_snapshot,
            "changed the record")
    out.append(("landing: a folder inside the checkout is no landing, one outside it is",
                not build_zip.leaves_checkout(REPO / "dist") and build_zip.leaves_checkout(Path(td)), ""))
    return out


def _git_fx(repo, *args):
    ident = ["-c", "user.name=Jake Mismas", "-c", "user.email=jake@jakemismas.com"]
    cp = subprocess.run(["git", *ident, *args], cwd=str(repo), capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(cp.stderr or cp.stdout).strip()[:200]}")
    return cp.stdout.strip()


def landed_tag_fixtures(td):
    """The tag check's landed half (build_zip.check_landed) on a throwaway repository: a tag on
    origin/main's head passes, and so does an annotated tag on an ancestor of it; a tag on a branch
    commit that main does not hold, a tag that is not the checked-out commit, a tag that does not
    resolve and a checkout without origin/main each refuse."""
    out = []
    g = Path(td) / "git-landed"
    g.mkdir()

    def landed(tag):
        try:
            build_zip.check_landed(tag, g)
            return True, ""
        except build_zip.BuildError as e:
            return False, str(e)
    try:
        _git_fx(g, "init", "-q", "-b", "main")
        (g / "a.txt").write_text("a\n", encoding="utf-8")
        _git_fx(g, "add", "a.txt")
        _git_fx(g, "commit", "-q", "-m", "Add the fixture's first file")
        a = _git_fx(g, "rev-parse", "HEAD")
        (g / "a2.txt").write_text("a2\n", encoding="utf-8")
        _git_fx(g, "add", "a2.txt")
        _git_fx(g, "commit", "-q", "-m", "Add the fixture's second file")
        _git_fx(g, "update-ref", "refs/remotes/origin/main", "HEAD")
        _git_fx(g, "tag", "v0.1.0")
        ok, why = landed("v0.1.0")
        out.append(("landed tag: a tag on origin/main's head passes", ok, why[:120]))
        _git_fx(g, "tag", "-a", "-m", "fixture", "v0.0.9", a)
        _git_fx(g, "checkout", "-q", "--detach", "v0.0.9")
        ok, why = landed("v0.0.9")
        out.append(("landed tag: an annotated tag on an ancestor of origin/main passes", ok, why[:120]))
        _git_fx(g, "checkout", "-q", "-b", "side", "v0.1.0")
        (g / "b.txt").write_text("b\n", encoding="utf-8")
        _git_fx(g, "add", "b.txt")
        _git_fx(g, "commit", "-q", "-m", "Add a branch commit main does not hold")
        _git_fx(g, "tag", "v0.1.1")
        ok, why = landed("v0.1.1")
        out.append(("landed tag: a tag on a branch commit that origin/main does not hold refuses",
                    not ok and "is not on origin/main" in why, why[:120]))
        ok, why = landed("v0.1.0")
        out.append(("landed tag: a tag that is not the checked-out commit refuses",
                    not ok and "is not tag" in why, why[:120]))
        ok, why = landed("v9.9.9")
        out.append(("landed tag: a tag that does not resolve refuses", not ok and "does not resolve" in why, why[:120]))
        _git_fx(g, "checkout", "-q", "--detach", "v0.1.0")
        _git_fx(g, "update-ref", "-d", "refs/remotes/origin/main")
        ok, why = landed("v0.1.0")
        out.append(("landed tag: a checkout without origin/main refuses (fail closed)",
                    not ok and "fail closed" in why, why[:120]))
    except (RuntimeError, OSError) as e:
        out.append(("landed tag: the throwaway repository was built", False, str(e)[:160]))
    return out


def snapshot_file_fixtures(td):
    """The snapshots as the rows read them from suite manifests: an earlier milestone's snapshot passes
    the registry it was taken from and fails a record of it re-hashed; a manifest that does not parse
    fails closed; an earlier milestone without a snapshot that registered a record no reference holds
    fails closed."""
    out = []
    reg = [{"id": "fx-a", "dumps": ["m1"]}, {"id": "fx-b", "dumps": ["m1"]}]
    rec = {"type": "noise-expression", "sha256": "1" * 64, "dump": "m1", "slice": "fx-a", "registered": "2026-10-29"}
    fz = {"format": tnfrozen.FORMAT, "hash_fields": list(tnfrozen.HASH_FIELDS),
          "bodies": {"tn_fx_a_v1": dict(rec), "tn_fx_b_v1": dict(rec, slice="fx-b", sha256="2" * 64)}}
    d = Path(td) / "suites-fixture"
    d.mkdir()
    (d / "fx-a.json").write_text(json.dumps({"format": "tn-suite/1", "slice": "fx-a", "checks": {},
                                             "frozen": tnfrozen.snapshot(fz, reg, "fx-a")}), encoding="utf-8")
    snaps, none = tnfrozen.suite_snapshots(reg, before="fx-b", suites=d)
    out.append(("snapshots: an earlier slice's snapshot passes the registry it was taken from",
                bool(snaps) and not none and not tnfrozen.snapshot_problems(fz, snaps), ""))
    moved = json.loads(json.dumps(fz))
    moved["bodies"]["tn_fx_a_v1"]["sha256"] = "3" * 64
    out.append(("snapshots: an earlier slice's record re-hashed fails its snapshot",
                any("changed the record" in x for x in tnfrozen.snapshot_problems(moved, snaps)), ""))
    (d / "fx-a.json").write_text("{not json", encoding="utf-8")
    try:
        tnfrozen.suite_snapshots(reg, before="fx-b", suites=d)
        out.append(("snapshots: a suite manifest that does not parse fails closed", False, "read"))
    except tnfrozen.RegistryUnreadable:
        out.append(("snapshots: a suite manifest that does not parse fails closed", True, ""))
    (d / "fx-a.json").write_text(json.dumps({"format": "tn-suite/1", "slice": "fx-a", "checks": {}}), encoding="utf-8")
    snaps, none = tnfrozen.suite_snapshots(reg, before="fx-b", suites=d)
    out.append(("snapshots: an earlier slice without a snapshot whose record no reference holds fails closed",
                not snaps and any("fail closed" in x for x in tnfrozen.unsnapshotted_problems(fz, none, {"bodies": {}})),
                ""))
    return out


def row_fixtures():
    missing = vanilla_raw_missing()
    if missing:
        return missing, "the release fixtures need the base game's prototypes"
    res = fixture_controls()
    bad = [f"{label} did not behave ({detail})" for label, ok, detail in res if not ok]
    return bad, f"{len(res)} positive controls, {len(res) - len(bad)} behaved"


# ------------------------------------------------------------------------------------------------ regions

# The region layer (milestone region-layer; T16, D13, A-7): one file builds every region formula. What a
# consumer may read of config.lua's regions group is the interface (ARCHITECTURE.md, "Region layer"):
# an aggregate's name, the version suffix, or a row name stem (sd, w, depth, and a hotspot's centre hu,
# hv and plain distance pd) to name one row's output.
REGION_FILE = "prototypes/expressions/regions.lua"
REGION_TABLE_MODULE = tnconfig.REGION_TABLE[:-len(".lua")].replace("/", ".")
REGION_INTERFACE = {"highland_fray", "highland_fray_tile", "highland_massif", "highland_cold",
                    "destroyed_sd", "destroyed_w", "destroyed_depth", "forest_w", "forest_sum", "tree_mult",
                    "marsh_w", "hotspot_w", "enemy_mult", "suffix"}
REGION_ROW_INTERFACE = {"sd", "w", "depth", "hu", "hv", "pd"}


def region_formula_findings(mod=MOD):
    """No region formula outside prototypes/expressions/regions.lua: no other mod Lua file requires the
    region table, and every read of config.lua's regions group outside it is a full dotted path to an
    interface name (regions.names.<aggregate>, regions.names.suffix, regions.names.row.<sd|w|depth|hu|hv|pd>).
    The warp, roughness, ramp, jitter, frame and query-point names stay the layer's own, and an alias
    of the group (or of its names table) or a bracket index would hide what is read, so both fail."""
    from luaparser import astnodes
    DOT = astnodes.IndexNotation.DOT
    out = []
    for p in mod_lua(mod):
        r = rel(p, mod)
        if r in (REGION_FILE, "prototypes/config.lua"):
            continue
        tree = parse_lua_file(p)
        nodes = list(tnconfig_walk(tree))
        parent = {}
        for n in nodes:
            for c in _children(n, astnodes):
                parent[id(c)] = n
        for n in nodes:
            line = getattr(n, "line", None) or getattr(parent.get(id(n)), "line", "?")
            if isinstance(n, astnodes.Call) and isinstance(n.func, astnodes.Name) and n.func.id == "require" and n.args:
                a = n.args[0]
                s = (a.s.decode() if isinstance(a.s, bytes) else a.s) if isinstance(a, astnodes.String) else ""
                if s.replace("/", ".") == REGION_TABLE_MODULE:
                    out.append(f"{r}:{line}: requires the region table outside {REGION_FILE}")
            if not isinstance(n, astnodes.Index):
                continue
            if n.notation != DOT and isinstance(n.idx, astnodes.String):
                s = n.idx.s.decode() if isinstance(n.idx.s, bytes) else n.idx.s
                if s == "regions":
                    out.append(f"{r}:{line}: a bracket index of regions (read the interface by its dotted path)")
                continue
            if not (n.notation == DOT and isinstance(n.idx, astnodes.Name) and n.idx.id == "regions"):
                continue
            chain, cur = [], n
            while True:
                par = parent.get(id(cur))
                if isinstance(par, astnodes.Index) and par.value is cur and par.notation == DOT and \
                        isinstance(par.idx, astnodes.Name):
                    chain.append(par.idx.id)
                    cur = par
                else:
                    break
            ok = (len(chain) >= 2 and chain[0] == "names" and chain[1] in REGION_INTERFACE) or \
                (len(chain) >= 3 and chain[:2] == ["names", "row"] and chain[2] in REGION_ROW_INTERFACE)
            if not ok:
                out.append(f"{r}:{line}: reads regions.{'.'.join(chain) or '(the whole group)'} outside {REGION_FILE}: "
                           f"only the interface names (a region formula lives in one file; T16, A-7)")
    return out


def row_regions(repo=REPO):
    import build_regions
    repo = Path(repo)
    f = build_regions.check_table()
    try:
        rows = build_regions.load_table()
    except build_regions.RegionError as e:
        rows, f = [], f + [str(e)]
    f += region_formula_findings(repo / "terra-nauvis")
    return f, (f"prototypes/tables/regions.lua re-emits byte for byte from its sources ({len(rows)} rows); no region "
               f"formula outside {REGION_FILE}")


def region_fixtures(td, cfg):
    """The regions row's positive controls: a consumer requiring the table, reading the warp, aliasing
    the group or bracket-indexing it fails; reading an interface name stays clean; a hand edit of the
    table fails the re-emission; a malformed row fails the table loader."""
    import build_regions
    out = []
    head = 'local cfg = require("prototypes.config")\n'
    forms = {
        "regions: a consumer requiring the region table fails": 'local t = require("prototypes.tables.regions")\n'
                                                                "return t\n",
        "regions: a consumer reading the shared warp fails": head + "local a = cfg.regions.warp.amplitude_px\nreturn a\n",
        "regions: a consumer reading the query point fails": head + "local q = cfg.regions.names.u\nreturn q\n",
        "regions: an alias of the regions group fails": head + "local R = cfg.regions\nreturn R\n",
        "regions: a bracket index of the regions group fails": head + 'local R = cfg["regions"]\nreturn R\n',
    }
    for label, text in forms.items():
        m = td / ("rg-" + str(abs(hash(label)) % 10 ** 8)) / "terra-nauvis"
        shutil.copytree(MOD, m)
        _write(m, "prototypes/expressions/consumer.lua", text)
        f = region_formula_findings(m)
        out.append((label, bool(f), f[:1]))
    m = td / "rg-clean" / "terra-nauvis"
    shutil.copytree(MOD, m)
    _write(m, "prototypes/expressions/consumer.lua", head + "local n = cfg.regions.names.tree_mult .. cfg.regions.names."
                                                           "row.w .. cfg.regions.names.suffix\nreturn n\n")
    f = region_formula_findings(m)
    out.append(("regions: a consumer reading interface names stays clean", not f, f[:1]))
    edited = td / "regions-edited.lua"
    edited.write_text(build_regions.TABLE.read_text(encoding="utf-8").replace("warp = 0.25", "warp = 0.3", 1),
                      encoding="utf-8")
    f = build_regions.check_table(edited)
    out.append(("regions: a hand edit of the region table fails its re-emission", bool(f), f[:1]))
    out.append(("regions: a row without a shape fails the table loader",
                bool(build_regions.row_problems({"id": "x", "layer": "forest", "warp": 1, "maps": ["europe"]})), ""))
    out += region_name_fixtures(td, cfg)
    return out


# ------------------------------------------------------------------------------------------------ ranges

def row_ranges(repo=REPO):
    """T16 (FG; milestone ridges): prototypes/tables/ranges.lua re-emits byte for byte from
    approvals-data.json and R7b, and its rows are the approval data's: the 16 ranges, exactly the
    adopted passes (Khyber and Bolan, which approvals-data.json drops, absent), the unnamed gaps the
    400 km rule gives per pass-free stretch, computed by tools/build_ranges.py and never placed by
    hand, and no pass-free stretch over 400 km on the whole crest or on any map."""
    import build_ranges
    f = build_ranges.table_findings()
    try:
        ranges = build_ranges.load_table()
    except (build_ranges.RangeError, tnconfig.ConfigError) as e:
        ranges, f = [], f + [str(e)]
    kinds = {k: sum(1 for r in ranges for o in r.get("openings") or [] if o.get("kind") == k)
             for k in build_ranges.KINDS}
    # the second table (0.3.0): re-emits from data-src/ridges/ranges-v2.json, no id of the first, the same 400 km rule
    f2 = build_ranges.table2_findings()
    try:
        n2 = len(build_ranges.load_table2())
    except (build_ranges.RangeError, tnconfig.ConfigError) as e:
        n2, f2 = 0, f2 + [str(e)]
    return f + f2, (f"prototypes/tables/ranges.lua re-emits byte for byte from its sources ({len(ranges)} ranges; "
                    f"openings {kinds}); the passes are approvals-data.json's adopted ones and the unnamed gaps its "
                    f"rule's; ranges_v2.lua re-emits from ranges-v2.json ({n2} ranges)")


def ranges_fixtures(td):
    """The ranges row's positive controls: a hand edit of the table fails its re-emission; a hand-placed
    gap, a dropped pass and a stretch over the rule's km fail the table checks; the real table passes."""
    import build_ranges
    out = []
    text = build_ranges.TABLE.read_text(encoding="utf-8")
    edited = td / "ranges-edited.lua"
    edited.write_text(text.replace("crest_km = 1016.3", "crest_km = 1016.4", 1), encoding="utf-8")
    f = build_ranges.check_table(edited)
    out.append(("ranges: a hand edit of the ranges table fails its re-emission", bool(f), f[:1]))
    cfg = tnconfig.load()
    appr, r7b = build_ranges.sources()
    ranges = build_ranges.derive(cfg, appr, r7b)

    def findings_of(rs):
        p = td / ("ranges-" + str(abs(hash(json.dumps(rs, sort_keys=True))) % 10 ** 8) + ".lua")
        p.write_text(build_ranges.emit_text(cfg, rs, appr, "fixture", "fixture"), encoding="utf-8")
        return [x for x in build_ranges.table_findings(cfg, p) if "fresh emission" not in x]
    import copy
    extra = copy.deepcopy(ranges)
    o = dict(extra[0]["openings"][0], kind="gap", id="hand_placed_gap")
    extra[0]["openings"].append(o)
    out.append(("ranges: a hand-placed unnamed gap fails the rule's count", bool(findings_of(extra)), ""))
    dropped = copy.deepcopy(ranges)
    dropped[0]["openings"] = [x for x in dropped[0]["openings"] if x["kind"] != "pass"][:0] + \
        [x for x in dropped[0]["openings"] if x["kind"] == "pass"][1:]
    out.append(("ranges: a missing adopted pass fails", bool(findings_of(dropped)), ""))
    long_ = copy.deepcopy(ranges)
    andes = next(r for r in long_ if r["id"] == "andes")
    andes["openings"] = [x for x in andes["openings"] if x["kind"] != "gap"]
    out.append(("ranges: a pass-free stretch over the rule's km fails", bool(findings_of(long_)), ""))
    out.append(("ranges: the real table passes its checks", not findings_of(ranges), findings_of(ranges)[:1]))
    return out


# ------------------------------------------------------------------------------------------------ hotspots

def row_hotspots(repo=REPO):
    """T16 (FG; milestone resources-enemies): prototypes/tables/hotspots.lua re-emits byte for byte from
    approvals-data.json, and its rows are the region table's hotspot rows (ids, resources, maps, radii
    and biter multipliers), so the bodies read the same discs the region layer draws."""
    import build_hotspots
    f = build_hotspots.table_findings() + build_hotspots.table2_findings()
    try:
        rows, _ = build_hotspots.load_table()
    except (build_hotspots.HotspotError, tnconfig.ConfigError) as e:
        rows, f = [], f + [str(e)]
    return f, (f"prototypes/tables/hotspots.lua and hotspots_v2.lua re-emit byte for byte from their sources ({len(rows)} rows, "
               f"{sum(1 for r in rows if r['offshore'])} offshore fields) and matches the region table's hotspot rows")


def hotspots_fixtures(td):
    """The hotspots row's positive controls: a hand edit fails the re-emission; a row the region table
    lacks, or with another radius, fails the cross-check; the real table passes."""
    import build_hotspots
    import build_regions
    out = []
    text = build_hotspots.TABLE.read_text(encoding="utf-8")
    edited = td / "hotspots-edited.lua"
    edited.write_text(text.replace("strength = 3", "strength = 2", 1), encoding="utf-8")
    f = build_hotspots.check_table(edited)
    out.append(("hotspots: a hand edit of the hotspot table fails its re-emission", bool(f), f[:1]))
    cfg = tnconfig.load()
    rows, _ = build_hotspots.load_table()
    reg = build_regions.load_table()
    extra = [dict(rows[0], id="hand_added_hotspot")] + rows
    out.append(("hotspots: a row the region table lacks fails", bool(build_hotspots.region_findings(extra, reg, cfg)),
                ""))
    wider = [dict(rows[0], radius_px=rows[0]["radius_px"] + 1)] + rows[1:]
    out.append(("hotspots: a radius unlike the region row's fails", bool(build_hotspots.region_findings(wider, reg, cfg)),
                ""))
    f = build_hotspots.region_findings(rows, reg, cfg)
    out.append(("hotspots: the real table matches the region table", not f, f[:1]))
    edited2 = td / "hotspots-v2-edited.lua"
    edited2.write_text(build_hotspots.TABLE2.read_text(encoding="utf-8") + "-- hand edit" + chr(10), encoding="utf-8")
    f = build_hotspots.table2_findings(cfg, edited2)
    out.append(("hotspots: a hand edit of the second table fails its re-emission", bool(f), f[:1]))
    f = build_hotspots.table2_findings(cfg)
    out.append(("hotspots: the real second table has no finding", not f, f[:1]))
    near = [dict(rows[0], lat=50.1, lon=8.7, radius_km=40, jitter_km=20, maps=["olde_world"])]
    f = build_hotspots.city_findings(near, cfg, json.loads(build_hotspots.APPROVALS.read_text(encoding="utf-8")))
    out.append(("hotspots: a row on Frankfurt fails the spawn city check", bool(f), f[:1]))
    return out


def region_name_fixtures(td, cfg):
    """The region layer's composed names are config.lua's names (design constraints 2 and 5): a row
    added to the table in a staged copy makes config.lua define the row's names and its new warped
    query point, and while tests/frozen.json lacks them the static frozen row fails and
    `build_zip.py --release` refuses; a frozen.json missing one row body fails both; a regions group
    whose table no release row lists fails the schema; the committed tree passes the release check."""
    import build_regions
    out = []
    names = tnconfig.region_names(cfg)
    if not names["rows"]:
        return [("regions: the composed-name controls need a regions group", False, "config.lua has none")]
    frozen_path = REPO / "tests" / "frozen.json"
    extra = {"id": "fixture_extra_row", "layer": "hotspot", "shape": "disc", "warp": 0.63, "mult": 4,
             "resource": "fixture", "lat": 50.0, "lon": 9.0, "radius_km": 30, "jitter_km": 15, "phase": 0.5,
             "maps": [cfg["map_order"][0]], "source": "a tn_static fixture row"}
    want = {tnconfig.region_row_name(cfg, k, extra["id"]) for k in tnconfig.REGION_ROW_KINDS +
            tnconfig.REGION_CENTRE_KINDS} | set(tnconfig.region_query_names(cfg, extra["warp"]))
    sd = tnconfig.region_row_name(cfg, "sd", extra["id"])
    root = td / "rg-names"
    shutil.copytree(MOD, root / "terra-nauvis")
    (root / "tests").mkdir(parents=True)
    for f in ("frozen.json", "budgets.json"):
        shutil.copy2(REPO / "tests" / f, root / "tests" / f)
    # the static frozen row reads the runner's milestone registry from the tree it checks
    (root / "tools").mkdir(parents=True)
    shutil.copy2(REPO / "tools" / "earth_test.py", root / "tools" / "earth_test.py")
    text = build_regions.emit_text(build_regions.load_table() + [extra], "a fixture", "a fixture", "a fixture")
    _write(root / "terra-nauvis", tnconfig.REGION_TABLE, text)
    staged = tnconfig.load(root / "terra-nauvis" / "prototypes" / "config.lua")
    got = tnconfig.defined_names(staged)["noise"]
    out.append(("regions: a staged table row's names and its warped query point are names config.lua defines",
                want <= got and sd not in tnconfig.defined_names(cfg)["noise"], sorted(want - got)[:2]))
    f = frozen_static_findings(root)
    out.append(("regions: a staged table row frozen.json lacks fails the static frozen row",
                all(any(n in x for x in f) for n in want), f[:1]))
    probs = build_zip.release_problems(staged, frozen_path)
    out.append(("regions: build_zip --release names a staged row's unregistered bodies with their release",
                all(any(n in p and "of release" in p for p in probs) for n in want), probs[:1]))
    try:
        build_zip.build(td / "rg-names-dist", release=True, mod_dir=root / "terra-nauvis", frozen_path=frozen_path)
        refused = []
    except build_zip.BuildError as e:
        refused = [str(e)]
    out.append(("regions: build_zip --release --mod-dir refuses a staged table row frozen.json lacks",
                bool(refused) and sd in refused[0], refused[:1] or ["built"]))
    fz = load_json(frozen_path)
    hot = next((d for d in names["rows"].values() if "hu" in d), next(iter(names["rows"].values())))
    victim = hot.get("hu") or hot["sd"]
    minus = td / "frozen-minus-one-row-body.json"
    minus.write_text(json.dumps(dict(fz, bodies={k: v for k, v in (fz.get("bodies") or {}).items() if k != victim})),
                     encoding="utf-8")
    probs = build_zip.release_problems(cfg, minus)
    out.append(("regions: a frozen.json missing one region row body refuses the release build",
                any(victim in p for p in probs), probs[:1]))
    f = config_frozen_findings(cfg, load_json(minus))
    out.append(("regions: a frozen.json missing one region row body fails the static frozen row",
                any(victim in x for x in f), f[:1]))
    unlisted = dict(cfg, release_registry=[r for r in tnconfig.release_registry(cfg)
                                           if tnconfig.REGION_TABLE not in (r.get("files") or [])])
    out.append(("regions: a regions group whose table no release row lists fails the schema",
                any(tnconfig.REGION_TABLE in x for x in tnconfig.schema_problems(unlisted)), ""))
    probs = build_zip.release_problems(cfg, frozen_path)
    out.append(("regions: the committed config, region table and frozen.json pass the release check", not probs,
                probs[:1]))
    return out


# ------------------------------------------------------------------------------------------------ all rows

def extras_fixtures(td, cfg):
    """The rows extras added: the size context of the locale (a label without a footprint, a wrong figure, a
    footprint not called reported, a table figure R8 does not give, a map size off APPROVALS 1c) and the tools
    scan (a graphical flag, the map-export mod's name); the committed locale and tools/ stay clean."""
    out = []
    if not cfg.get("size_context"):
        return [("extras: config.lua has a size_context table", False, ["no size_context"])]
    secs, _ = parse_cfg((MOD / "locale" / "en" / "terra-nauvis.cfg").read_text(encoding="utf-8"))
    merged = {k: dict(v) for k, v in secs.items()}
    out.append(("size context: the committed locale passes", not size_context_findings(cfg, merged),
                size_context_findings(cfg, merged)[:1]))
    s = cfg["settings"]["scale"]
    sc = cfg["size_context"]
    fp0 = sc["footprints"][0]
    fig0 = f"{thousands(fp0['width'])} x {thousands(fp0['height'])}"
    key6 = f"{s['name']}-{s['allowed_values'][-1]}"
    pkey = cfg["presets"][cfg["preset_order"][0]]["name"]

    def mutated(sec, key, fn):
        m = {k: dict(v) for k, v in merged.items()}
        m[sec][key] = fn(m[sec][key])
        return size_context_findings(cfg, m)
    for label, sec, key, fn in (
            ("size context: a scale label without a footprint fails", "string-mod-setting", key6,
             lambda v: v.replace(fig0, "")),
            ("size context: a preset description with a wrong world size fails", "map-gen-preset-description", pkey,
             lambda v: v.replace(" x ", " x 1", 1)),
            ("size context: footprints not called reported fail", "map-gen-preset-description", pkey,
             lambda v: v.replace(sc["reported_phrase"], "examples")),
            ("size context: a scale tooltip without the footprints fails", "mod-setting-description", s["name"],
             lambda v: v.split(sc["reported_phrase"])[0])):
        f = mutated(sec, key, fn)
        out.append((label, bool(f), f[:1]))
    bad_cfg = json.loads(json.dumps(cfg))
    bad_cfg["size_context"]["footprints"][0]["width"] = fp0["width"] + 1
    f = size_context_findings(bad_cfg, merged)
    out.append(("size context: a footprint R8 does not give fails", any("R8" in x for x in f), f[:1]))
    bad_cfg = json.loads(json.dumps(cfg))
    bad_cfg["maps"][cfg["map_order"][0]]["width_px"] += 1
    f = size_context_findings(bad_cfg, merged)
    out.append(("size context: a map size off APPROVALS 1c fails", any("world_size_tiles" in x for x in f), f[:1]))
    f, _ = tools_scan_findings(HERE)
    out.append(("tools scan: the committed tools/ is clean", not f, f[:1]))
    for label, text in (("tools scan: a graphical flag in a tool fails", f"args = ['{GRAPHICAL_FLAGS[0]}', 'x']\n"),
                        ("tools scan: the map-export mod's name in a tool fails", f"# render with {EXPORT_MOD_WORD}\n")):
        d = td / ("tscan-" + str(abs(hash(label)) % 10 ** 8))
        _write(d, "x.py", text)
        f, _ = tools_scan_findings(d)
        out.append((label, bool(f), f[:1]))
    return out


ROWS = [
    ("lint", row_lint), ("info_json", row_info), ("locale", row_locale), ("dashes", row_dashes),
    ("registration", row_registration), ("storage", row_storage), ("names", row_names),
    ("design_rules", row_design), ("workflow_scan", row_workflow),
    ("data_src", row_data_src), ("frozen_static", row_frozen), ("bodies", row_bodies), ("append_only", row_append_only),
    ("fallbacks", row_fallbacks), ("zip", row_zip), ("regions", row_regions), ("ranges", row_ranges), ("hotspots", row_hotspots),
    ("release_zip", row_release_zip), ("tools_scan", row_tools_scan),
    ("d33_guard", row_d33), ("redefinitions", row_redefinitions), ("fixtures", row_fixtures),
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
