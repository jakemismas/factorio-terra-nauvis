#!/usr/bin/env python3
"""The tests/frozen.json contract (design constraint 2; ARCHITECTURE.md data flow step 6).

Every reader and writer of the registry holds it to this module: the gate's frozen row and `freeze`
(earth_test.py), the T16 frozen and append-only rows (tn_static.py) and `build_zip.py --release`.

  {"format": "tn-frozen/1", "note": <text>, "hash_fields": HASH_FIELDS, "bodies": {<name>: <record>}}

A record holds exactly RECORD_KEYS: `type` (a noise type), `sha256` (64 lower-case hex over the
body's HASH_FIELDS), `dump` (the label of the dump freeze read the body from), `milestone` (the milestone
of the runner's registry that registered it) and `registered` (the date freeze wrote it), and
optionally OPTIONAL_RECORD_KEYS: `mask` (resources-enemies), one of MASK_NAMES, for a wrapper of an
optional mod's live autoplace whose hash leaves out the live text it wraps (earth_test.body_hash). The dump
label decides which dump the gate's frozen row reads the body from, so a label that no entry of the
runner's milestone registry (earth_test.py REGISTRY) assigns would switch that row off for the body;
such a label, a missing one and one its milestone could not have produced fail in every reader instead
of being skipped. A record never changes once a reference holds it: the append-only checks compare
whole records, so a relabel, a retype or a new date moves a registered record as a new hash does.

The static rows and the release build import no runner, so they read REGISTRY from its one
module-level literal; the gate's frozen row checks that reading against the live registry.

A registered body is built by code from data, so its name and its data alone cannot show it
unchanged. `offline_bodies` runs the mod's settings and data stages under tools/tnlua.py (no game),
and `body_problems` holds every body built there to the record that registers it, hashed as the
dumped bodies are (`body_hash`): the T16 bodies row (CI), `build_zip.py --release` and a zip copied
out of the checkout apply it, and the gate's frozen row holds the offline reading to the game's
dump (parity).

A registry is landed before it reaches main once an earlier milestone of a group recorded it, or once
its zip left the checkout. Each milestone's suite manifest (tests/baselines/suites/<milestone>.json)
carries a `frozen` snapshot of the records registered through that milestone (`snapshot`, written by
`suite` and `freeze`), and a zip copied out of the checkout carries its bodies and one in its build
record; `snapshot_problems` fails any record such a snapshot holds that the registry changed or
dropped.

Until the first release, tests/unreleased-moves.json lists what a landed state held and the tree may
leave behind (its issue, 2026-10-30 10:26: nothing has shipped and no saves exist): per
record the exact sha256 values the registry moved away from, and the tn_geo ids it retired.
`active_moves` reads it, a release tag voids it (the T16 append-only row then fails until it is empty),
and every other record stays held. tools/refreeze.py writes it together with the registry.
"""
import ast
import copy
import datetime
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "tools" / "earth_test.py"
FORMAT = "tn-frozen/1"
NOISE_TYPES = ("noise-expression", "noise-function")
# The generation fields a body's sha256 covers (never intended_property, localised_name or order).
HASH_FIELDS = ("type", "name", "expression", "local_expressions", "local_functions", "parameters")
RECORD_KEYS = ("type", "sha256", "dump", "slice", "registered")
OPTIONAL_RECORD_KEYS = ("mask",)
MASK_NAMES = ("live",)
FILE_KEYS = ("format", "note", "hash_fields", "bodies")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LABEL_RE = re.compile(r"[a-z0-9]+")
_ABSENT = object()
_READ = {}


class RegistryUnreadable(ValueError):
    pass


def registry_problems(registry):
    """The milestone registry's shape as this contract reads it: a non-empty list of entries, each with a
    milestone id of its own and a list of dump labels."""
    if not isinstance(registry, list) or not registry:
        return ["REGISTRY is not a non-empty list of slice entries"]
    out, ids = [], set()
    for i, s in enumerate(registry):
        sid = s.get("id") if isinstance(s, dict) else None
        if not isinstance(sid, str) or not sid:
            out.append(f"REGISTRY[{i}] has no slice id")
            continue
        if sid in ids:
            out.append(f"REGISTRY lists the slice {sid} twice")
        ids.add(sid)
        dumps = s.get("dumps")
        if not isinstance(dumps, list) or not all(isinstance(lb, str) and LABEL_RE.fullmatch(lb) for lb in dumps):
            out.append(f"REGISTRY {sid} dumps {dumps!r} is not a list of dump labels")
    return out


def runner_registry(path=RUNNER):
    """REGISTRY as tools/earth_test.py writes it: its one module-level literal assignment. No other
    module-level statement may name REGISTRY, since an append there would escape this reading.
    Raises RegistryUnreadable (fail closed). Each reading is kept by path, size and mtime, since one
    static run asks for it about a dozen times and a parse of the runner takes half a second."""
    path = Path(path)
    try:
        st = path.stat()
        key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    except OSError as e:
        raise RegistryUnreadable(f"{path.name} is unreadable ({e})") from e
    if key not in _READ:
        _READ[key] = _read_registry(path)
    return copy.deepcopy(_READ[key])


def _names_registry_at_import(node):
    """Whether a module-level statement names REGISTRY in code that runs when the module loads: a
    class body, a decorator or a default value does, a function or lambda body does not (it runs
    later, against the registry the module built)."""
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Name) and n.id == "REGISTRY":
            return True
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(getattr(n, "decorator_list", []))
            stack.extend(n.args.defaults + [d for d in n.args.kw_defaults if d is not None])
            continue
        stack.extend(ast.iter_child_nodes(n))
    return False


def _read_registry(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as e:
        raise RegistryUnreadable(f"{path.name} does not parse ({type(e).__name__}: {e})") from e
    assigns, others = [], []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "REGISTRY":
            assigns.append(node)
        elif _names_registry_at_import(node):
            others.append(node.lineno)
    if len(assigns) != 1 or others:
        raise RegistryUnreadable(f"{path.name} must assign REGISTRY once at module level and name it in no other "
                                 f"module-level statement (assignments: {len(assigns)}; other statements at lines "
                                 f"{others})")
    try:
        registry = ast.literal_eval(assigns[0].value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e:
        raise RegistryUnreadable(f"{path.name}: REGISTRY is not a literal ({e})") from e
    probs = registry_problems(registry)
    if probs:
        raise RegistryUnreadable(f"{path.name}: " + "; ".join(probs[:3]))
    return registry


def labels_through(registry):
    """{milestone id: the dump labels freeze produces when that milestone registers}: the labels of every
    registry entry up to and including it, in registry order."""
    out, seen = {}, []
    for s in registry:
        for lb in s.get("dumps") or []:
            if lb not in seen:
                seen.append(lb)
        out[s["id"]] = list(seen)
    return out


def assigned_labels(registry):
    """Every dump label some entry of the registry assigns."""
    return sorted({lb for s in registry for lb in (s.get("dumps") or [])})


def record(type_, sha256, dump, slice_id, registered, mask=None):
    """A record as freeze writes it: RECORD_KEYS, in that order, and the mask when it has one."""
    out = {"type": type_, "sha256": sha256, "dump": dump, "slice": slice_id, "registered": registered}
    if mask is not None:
        out["mask"] = mask
    return out


def _is_date(v):
    if not isinstance(v, str) or not DATE_RE.fullmatch(v):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def record_problems(name, rec, registry):
    """Every way one record breaks the contract against the runner's milestone registry ([] when it
    holds): exactly RECORD_KEYS, and a mask of MASK_NAMES where one is given; a noise type; 64 lower-case hex; a milestone of the registry; a dump
    label that some registry entry assigns and that freeze produces through that milestone; a date."""
    where = f"tests/frozen.json {name}"
    if not isinstance(rec, dict):
        return [f"{where}: the record is a {type(rec).__name__}, not a table"]
    out = []
    missing = [k for k in RECORD_KEYS if k not in rec]
    extra = sorted(str(k) for k in rec if k not in RECORD_KEYS and k not in OPTIONAL_RECORD_KEYS)
    if missing:
        out.append(f"{where}: the record lacks {missing} (a {FORMAT} record holds {list(RECORD_KEYS)})")
    if extra:
        out.append(f"{where}: the record holds {extra}, which a {FORMAT} record does not define")
    if "mask" in rec and rec["mask"] not in MASK_NAMES:
        out.append(f"{where}: mask {rec['mask']!r} is not one of {list(MASK_NAMES)}")
    if "type" in rec and rec["type"] not in NOISE_TYPES:
        out.append(f"{where}: type {rec['type']!r} is not one of {list(NOISE_TYPES)}")
    if "sha256" in rec and not (isinstance(rec["sha256"], str) and SHA256_RE.fullmatch(rec["sha256"])):
        out.append(f"{where}: sha256 is not 64 lower-case hex")
    through = labels_through(registry)
    labels = assigned_labels(registry)
    sl, lb = rec.get("slice"), rec.get("dump")
    if "slice" in rec and not (isinstance(sl, str) and sl in through):
        out.append(f"{where}: slice {sl!r} is no slice of the runner's registry {list(through)}")
    if "dump" in rec:
        if not (isinstance(lb, str) and lb in labels):
            out.append(f"{where}: dump {lb!r} is no label the runner's registry assigns to a slice ({labels}), so "
                       f"the gate's frozen row would never read the body (fail closed)")
        elif isinstance(sl, str) and sl in through and lb not in through[sl]:
            out.append(f"{where}: dump {lb!r} is not among the dumps {through[sl]} that freeze produces through "
                       f"{sl}, the slice the record names")
    if "registered" in rec and not _is_date(rec["registered"]):
        out.append(f"{where}: registered {rec['registered']!r} is not a YYYY-MM-DD date")
    return out


def file_problems(fz, registry):
    """The registry file's shape and every record's ([] when it holds): a JSON object of FILE_KEYS
    (`note` optional), the format, the hash's field list and a bodies table of valid records."""
    if not isinstance(fz, dict):
        return [f"tests/frozen.json is a {type(fz).__name__}, not a JSON object"]
    out = []
    extra = sorted(str(k) for k in fz if k not in FILE_KEYS)
    if extra:
        out.append(f"tests/frozen.json holds {extra}, which {FORMAT} does not define")
    if fz.get("format") != FORMAT:
        out.append(f"tests/frozen.json format {fz.get('format')!r}, want {FORMAT!r}")
    if fz.get("hash_fields") != list(HASH_FIELDS):
        out.append(f"tests/frozen.json hash_fields {fz.get('hash_fields')!r}: every registered sha256 covers "
                   f"{list(HASH_FIELDS)}")
    if "note" in fz and not isinstance(fz["note"], str):
        out.append("tests/frozen.json note is not text")
    bodies = fz.get("bodies")
    if not isinstance(bodies, dict):
        return out + ["tests/frozen.json has no bodies table"]
    for name in sorted(bodies):
        out += record_problems(name, bodies[name], registry)
    return out


MOVES = REPO / "tests" / "unreleased-moves.json"
MOVES_FORMAT = "tn-unreleased-moves/1"
MOVES_KEYS = ("format", "ruling", "geographies", "records")


def moves_problems(moves):
    """The waiver file's shape ([] when it holds): MOVES_KEYS, the decision that allows it, tn_geo ids,
    and per record name a list of sha256 values."""
    if not isinstance(moves, dict):
        return [f"tests/unreleased-moves.json is a {type(moves).__name__}, not a JSON object"]
    out = []
    if sorted(moves) != sorted(MOVES_KEYS):
        out.append(f"tests/unreleased-moves.json holds {sorted(moves)}, want {sorted(MOVES_KEYS)}")
    if moves.get("format") != MOVES_FORMAT:
        out.append(f"tests/unreleased-moves.json format {moves.get('format')!r}, want {MOVES_FORMAT!r}")
    if not (isinstance(moves.get("ruling"), str) and moves.get("ruling")):
        out.append("tests/unreleased-moves.json names no ruling")
    geos = moves.get("geographies")
    if not (isinstance(geos, list) and all(isinstance(g, int) and not isinstance(g, bool) for g in geos)):
        out.append("tests/unreleased-moves.json geographies is not a list of tn_geo ids")
    recs = moves.get("records")
    if not isinstance(recs, dict):
        return out + ["tests/unreleased-moves.json records is not a table"]
    for name, hashes in sorted(recs.items()):
        if not (isinstance(hashes, list) and hashes and all(isinstance(h, str) and SHA256_RE.fullmatch(h) for h in hashes)):
            out.append(f"tests/unreleased-moves.json {name}: not a list of sha256 values")
    return out


def read_moves(path=MOVES):
    """The waiver file's table, or None when the file is absent. Raises RegistryUnreadable when it
    does not parse or breaks its shape (fail closed)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        moves = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RegistryUnreadable(f"tests/unreleased-moves.json does not parse ({e}) (fail closed)") from e
    probs = moves_problems(moves)
    if probs:
        raise RegistryUnreadable(f"{probs[0]} (fail closed)")
    return moves


def active_moves(tags, path=MOVES):
    """The waiver while no release exists; None once any release tag does (`tags`, the checkout's
    v<x.y.z> tags), so nothing a release holds can ever be excused."""
    return None if tags else read_moves(path)


def moved(moves, name, sha256):
    """Whether the waiver excuses the registered record `name` at this exact hash."""
    return bool(moves) and sha256 in ((moves.get("records") or {}).get(name) or [])


# The collapse (0.3.0: one geography version per map; on the maintainer's
# word that no world exists on any version before 0.3.0). Unlike the unreleased waiver, no release tag voids it: it
# names exactly what the collapse took out of landed states, so the append-only checks excuse that and hold every other
# record, row, version and file as before.
#   versions     the geo_id of every geography version config.lua's geography no longer lists
#   geographies  the tn_geo ids whose release_registry rows left with them
#   frames       the tn_geo ids whose rows stay as a map's frame (config.lua frames), which may only lose names this
#                file drops and files it lists
#   records      {name: [sha256]}: every record the registry dropped, at the hash a landed state registered it
#   files        the mod-relative generated files the tree dropped
COLLAPSE = REPO / "tests" / "collapsed.json"
COLLAPSE_FORMAT = "tn-collapsed/1"
COLLAPSE_KEYS = ("format", "ruling", "versions", "geographies", "frames", "records", "files")


def collapse_problems(c):
    """The collapse record's shape ([] when it holds)."""
    if not isinstance(c, dict):
        return [f"tests/collapsed.json is a {type(c).__name__}, not a JSON object"]
    out = []
    if sorted(c) != sorted(COLLAPSE_KEYS):
        out.append(f"tests/collapsed.json holds {sorted(c)}, want {sorted(COLLAPSE_KEYS)}")
    if c.get("format") != COLLAPSE_FORMAT:
        out.append(f"tests/collapsed.json format {c.get('format')!r}, want {COLLAPSE_FORMAT!r}")
    if not (isinstance(c.get("ruling"), str) and c.get("ruling")):
        out.append("tests/collapsed.json names no ruling")
    for k in ("versions", "geographies", "frames"):
        v = c.get(k)
        if not (isinstance(v, list) and all(isinstance(g, int) and not isinstance(g, bool) for g in v)):
            out.append(f"tests/collapsed.json {k} is not a list of tn_geo ids")
    if set(c.get("geographies") or []) & set(c.get("frames") or []):
        out.append("tests/collapsed.json retires and keeps a frame of the same tn_geo id")
    files = c.get("files")
    if not (isinstance(files, list) and all(isinstance(f, str) and f for f in files)):
        out.append("tests/collapsed.json files is not a list of mod-relative paths")
    recs = c.get("records")
    if not isinstance(recs, dict):
        return out + ["tests/collapsed.json records is not a table"]
    for name, hashes in sorted(recs.items()):
        if not (isinstance(hashes, list) and hashes and all(isinstance(h, str) and SHA256_RE.fullmatch(h) for h in hashes)):
            out.append(f"tests/collapsed.json {name}: not a list of sha256 values")
    return out


def read_collapse(path=COLLAPSE):
    """The collapse record, or None when the file is absent. Raises RegistryUnreadable when it does not
    parse or breaks its shape (fail closed)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RegistryUnreadable(f"tests/collapsed.json does not parse ({e}) (fail closed)") from e
    probs = collapse_problems(c)
    if probs:
        raise RegistryUnreadable(f"{probs[0]} (fail closed)")
    return c


def with_collapse(moves, collapse):
    """The waiver the append-only checks read: `moves` (the unreleased waiver, or None) with the collapse's records
    and retired tn_geo ids added; None when both are empty."""
    if not collapse:
        return moves
    recs = {n: list(h) for n, h in ((moves or {}).get("records") or {}).items()}
    for n, hashes in (collapse.get("records") or {}).items():
        recs[n] = sorted(set(recs.get(n, [])) | set(hashes))
    geos = sorted(set((moves or {}).get("geographies") or []) | set(collapse.get("geographies") or []))
    return {"format": MOVES_FORMAT, "ruling": (moves or {}).get("ruling") or collapse.get("ruling"),
            "geographies": geos, "records": recs}


def record_changes(mine, ref):
    """The fields in which a record differs from a reference record, over every field of either (a
    field one of them lacks counts as changed); [] when they are equal."""
    if not isinstance(mine, dict) or not isinstance(ref, dict):
        return [] if mine == ref else ["the record"]
    return sorted(str(k) for k in set(mine) | set(ref) if mine.get(k, _ABSENT) != ref.get(k, _ABSENT))


# ------------------------------------------------------------------------------------------------ bodies

SNAPSHOT_FORMAT = "tn-frozen-snapshot/1"
SUITES = REPO / "tests" / "baselines" / "suites"


def key_of(obj):
    """sha256 of an object's canonical JSON (sorted keys, no spaces): every registry hash."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def body_hash(proto, mask=None):
    """sha256 of a noise body's generation fields only (never intended_property, localised_name, order),
    with a frozen record's mask applied (MASK_NAMES): "live" leaves out the local tables a wrapper
    rebuilds from live settings."""
    if mask is None:
        return key_of({k: proto.get(k) for k in HASH_FIELDS if k in proto})
    if mask == "live":
        rec = {k: proto.get(k) for k in HASH_FIELDS if k in proto and k not in ("local_expressions", "local_functions")}
        return key_of(dict(rec, mask="live"))
    raise ValueError(f"unknown frozen mask {mask!r} (known: {list(MASK_NAMES)})")


def earth_bodies(dump, cfg):
    """Every Earth noise body of a dump (or of the offline data stage, which has its form) as {name:
    (type, prototype)}: a noise-expression or noise-function whose name carries config.lua's noise
    prefix or is a noise name config.lua defines (the schema requires the prefix of every such name,
    so the two agree)."""
    import tnconfig
    prefix = ((cfg or {}).get("identity") or {}).get("noise_prefix") or "\0"
    known = set(tnconfig.noise_names(cfg)) if cfg and cfg.get("identity") else set()
    out = {}
    for t in NOISE_TYPES:
        for name, proto in ((dump or {}).get(t) or {}).items():
            if name.startswith(prefix) or name in known:
                out[name] = (t, proto)
    return out


def exempt_names(cfg):
    """The names never registered (U3's one exemption plus the placeholder): the placeholder's names
    and the Map type fallbacks that mirror a startup setting."""
    import tnconfig
    if not cfg:
        return set()
    return set(tnconfig.placeholder_names(cfg)) | set(tnconfig.exempt_fallback_names(cfg))


def offline_dump(source):
    """The data stage of the mod at `source` (a mod folder, a mod zip's path or its bytes) at default
    settings, in the dump's form {type: {name: prototype}}. Raises tnlua.LuaError (fail closed)."""
    import tnlua
    return tnlua.data_stage(tnlua.reader_for(source))


def offline_bodies(source, cfg):
    """{name: (type, prototype)} of every Earth body the mod at `source` defines, offline."""
    return earth_bodies(offline_dump(source), cfg)


# The dumps the offline data stage reproduces: M1, base only (tools/tnlua.py runs no other mod). A
# record registered from the Alien Biomes (M2) or Oil Rig (M3) dump names a body that exists only beside
# that mod; the gate's frozen row holds those to the game's own dumps.
OFFLINE_DUMPS = ("m1",)
# M2 reproduces offline too: its bodies read only mods["alien-biomes"], so a second stage with that flag
# builds them. Without it a config value read only under `if AB` could move a released body with every
# automated check green. M3 needs the Oil Rig's prototypes and stays with the gate.
OFFLINE_AB_DUMPS = ("m2",)
OFFLINE_AB_MODS = {"alien-biomes": "0.8.0"}


def offline_ab_problems(source, fz, cfg):
    """body_problems for the M2 records against the bodies the data stage builds with Alien Biomes' flag.
    Raises tnlua.LuaError (fail closed)."""
    import tnlua
    dump = tnlua.data_stage(tnlua.reader_for(source), mods={**tnlua.DEFAULT_MODS, **OFFLINE_AB_MODS})
    return body_problems(earth_bodies(dump, cfg), fz, cfg, "the offline Alien Biomes data stage", OFFLINE_AB_DUMPS)


def live_ab_bodies(cfg):
    """The bodies only the game can compute: data-final-fixes.lua builds them from Alien Biomes' installed palms, so no
    offline stage holds their text. The gate compares them with Alien Biomes loaded (the M2 dump); every offline reading
    reports them skipped, never passed (`skipped_note`), whatever dump label their released records carry."""
    copies = (((cfg or {}).get("tiles") or {}).get("palm") or {}).get("copies") or []
    return {c["body"] for c in copies}


def skipped_note(cfg):
    n = len(live_ab_bodies(cfg))
    return f"{n} palm bodies skipped: they need Alien Biomes loaded, and only the gate's frozen row compares them" if n else ""


def body_problems(bodies, fz, cfg, where="the offline data stage", dumps=OFFLINE_DUMPS):
    """Every registered record of `dumps` held to the body `bodies` builds under its name ([] when all
    hold): present with the record's type and the record's hash (a body changed in place through its
    code or its data fails like a re-hash), and every Earth body built there registered, the exempt
    names excepted (design constraint 2). The live_ab_bodies are left out: see skipped_note."""
    out = []
    registered = (fz or {}).get("bodies") if isinstance((fz or {}).get("bodies"), dict) else {}
    skipped = live_ab_bodies(cfg)
    for name, rec in sorted(registered.items()):
        if not isinstance(rec, dict) or (dumps is not None and rec.get("dump") not in dumps) or name in skipped:
            continue
        got = bodies.get(name)
        if got is None:
            out.append(f"registered body {name} is not defined by {where} (old names stay defined)")
            continue
        t, proto = got
        if t != rec.get("type"):
            out.append(f"registered body {name} is a {t} in {where}, registered as a {rec.get('type')}")
        h = body_hash(proto, rec.get("mask"))
        if h != rec.get("sha256"):
            out.append(f"registered body {name} changed in place: registered {str(rec.get('sha256'))[:12]}, {where} "
                       f"builds {h[:12]} (a registered body never changes; ship it under the next _v<n>)")
    exempt = exempt_names(cfg)
    for name in sorted(set(bodies) - set(registered) - exempt):
        out.append(f"Earth body {name} of {where} is not registered in tests/frozen.json: run python "
                   f"tools/earth_test.py freeze (sacred constraint 2)")
    return out


def body_digests(bodies):
    """{name: {type, sha256}} of offline or dumped bodies ({name: (type, prototype)}): what a build
    record keeps."""
    return {n: {"type": t, "sha256": body_hash(p)} for n, (t, p) in sorted(bodies.items())}


def body_changes(old, new, exempt=()):
    """The bodies of a landed build that a new one changed or dropped, the exempt names excepted, as
    [(name, "changed" or "dropped")]; both are {name: {type, sha256}} (body_digests)."""
    out = []
    for name in sorted(set(old) - set(exempt)):
        if name not in new:
            out.append((name, "dropped"))
        elif {k: (new[name] or {}).get(k) for k in ("type", "sha256")} != \
                {k: (old[name] or {}).get(k) for k in ("type", "sha256")}:
            out.append((name, "changed"))
    return out


def snapshot(fz, registry, slice_id):
    """The records registered through `slice_id` (its own and every earlier milestone's, in registry
    order) as a snapshot: what that milestone's suite manifest keeps. Records of later milestones are left
    out, so a group's later milestone may still redo its own registration before it lands."""
    ids = [s["id"] for s in registry]
    if slice_id not in ids:
        raise RegistryUnreadable(f"snapshot: {slice_id!r} is no slice of the runner's registry {ids}")
    through = set(ids[: ids.index(slice_id) + 1])
    bodies = {n: copy.deepcopy(r) for n, r in sorted(((fz or {}).get("bodies") or {}).items())
              if isinstance(r, dict) and r.get("slice") in through}
    return {"format": SNAPSHOT_FORMAT, "through": slice_id, "bodies": bodies, "sha256": key_of(bodies)}


def snapshot_problems(fz, snapshots, moves=None):
    """Every record a snapshot holds ({label: snapshot}) that the registry `fz` changed or dropped,
    the waiver's records at their exact hash excepted (`moves`, active_moves), and every snapshot that
    is not well formed (its sha256 must cover its bodies, so a record edited in a snapshot without its
    hash fails instead of reading as the reference)."""
    out = []
    bodies = (fz or {}).get("bodies") if isinstance((fz or {}).get("bodies"), dict) else {}
    for label, snap in sorted(snapshots.items()):
        if not isinstance(snap, dict) or snap.get("format") != SNAPSHOT_FORMAT or \
                not isinstance(snap.get("bodies"), dict):
            out.append(f"{label}: the frozen snapshot is not {SNAPSHOT_FORMAT} with a bodies table (fail closed)")
            continue
        if snap.get("sha256") != key_of(snap["bodies"]):
            out.append(f"{label}: the frozen snapshot's sha256 does not cover its bodies (edited by hand; fail closed)")
            continue
        for name, rec in sorted(snap["bodies"].items()):
            if moved(moves, name, rec.get("sha256")):
                continue
            if name not in bodies:
                out.append(f"{name} is registered in {label}'s snapshot but missing from tests/frozen.json (a "
                           f"registered record never leaves the registry)")
                continue
            changed = record_changes(bodies[name], rec)
            if changed:
                out.append(f"{name}: tests/frozen.json changed the record {label}'s snapshot holds, in {changed} (a "
                           f"registered record never changes in place, landed on main or not; ship a change under "
                           f"the next _v<n>)")
    return out


def suite_snapshots(registry, before=None, suites=SUITES):
    """({milestone id: snapshot} from the suite manifests of the registry's milestones before `before` (every
    milestone when None), {milestone id: why it has none}). A manifest that does not parse raises
    RegistryUnreadable (fail closed)."""
    ids = [s["id"] for s in registry]
    if before is not None:
        if before not in ids:
            raise RegistryUnreadable(f"{before!r} is no slice of the runner's registry {ids}")
        ids = ids[: ids.index(before)]
    snaps, none = {}, {}
    for sid in ids:
        p = Path(suites) / f"{sid}.json"
        if not p.exists():
            none[sid] = "no suite manifest"
            continue
        try:
            man = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise RegistryUnreadable(f"{p.name} does not parse ({e}) (fail closed)") from e
        snap = man.get("frozen") if isinstance(man, dict) else None
        if snap is None:
            none[sid] = "no frozen snapshot in its suite manifest"
        else:
            snaps[f"{sid}'s suite manifest"] = snap
    return snaps, none


def unsnapshotted_problems(fz, none, reference):
    """A milestone whose suite manifest keeps no snapshot may own no record that no landed reference
    holds: such a record would have nothing to keep it fixed until its group lands (fail closed)."""
    out = []
    ref = (reference or {}).get("bodies") or {}
    for name, rec in sorted(((fz or {}).get("bodies") or {}).items()):
        sid = rec.get("slice") if isinstance(rec, dict) else None
        if sid in none and name not in ref:
            out.append(f"{name} is registered by {sid}, which has {none[sid]}, and no landed reference holds it: run "
                       f"python tools/earth_test.py suite {sid} (or freeze) so its registry is snapshotted (fail "
                       f"closed)")
    return out
