#!/usr/bin/env python3
"""Freeze Alien Biomes' palm autoplace as Earth-owned data (milestone climate-tiles; project rule 9).

  python tools/build_palms.py --dump <dump-data run dir>   write the generated palm table
  python tools/build_palms.py --check                       the committed table against its digest

The Earth copies of Alien Biomes' palm autoplace (tn_palm_*_v1, design constraint 3's palm switch)
are registered bodies, so their generation fields must never follow a newer Alien Biomes in place
(design constraint 2). This tool reads, from one dump-data run of a modset holding Alien
Biomes (fh.py's run.json names the modset), each palm config.lua's tiles.palm.copies names: its
probability, richness and every local expression, and every noise function those texts call; it
records the modset's Alien Biomes version and zip sha256, the dump's sha256 and the digest of the
recorded data, and writes them as name-free data (config.lua's tiles.palm.table). trees.lua builds
the copies from that table alone, the called functions carried as local functions, and
data-final-fixes.lua compares the live palm autoplace with it: on any difference Earth presets name
the neutral body instead (log line), and the gate's dump facts fail, so an Alien Biomes update is a
deliberate change that ships the copies' next version from a new table. Never edit the output by
hand; rerun this tool.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MOD = REPO / "terra-nauvis"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402

EMITTER = 1
AB = "alien-biomes"
# The names a palm text may read besides its own locals and the functions it carries: the climate
# properties Earth presets redirect, and elevation, which the copies replace with the palm constant.
READS = ("elevation", "moisture", "temperature", "aux")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_:]*")
WIDTH = 118


class PalmError(RuntimeError):
    pass


def norm(v):
    """Numbers as tnconfig reads them back from Lua (an integral float is an int)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and v.is_integer() and abs(v) < 2 ** 53:
        return int(v)
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def digest(data):
    """sha256 of the recorded palms and functions (canonical JSON), the table's own digest."""
    core = {"trees": norm(data["trees"]), "functions": norm(data["functions"])}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def idents(text):
    if not isinstance(text, str):
        return set()
    return set(IDENT.findall(QUOTED.sub(" ", text)))


def palm_table(dump, trees):
    """{"trees": {tree: {probability_expression, richness_expression, local_expressions}}, "functions":
    {name: {parameters, expression[, local_expressions]}}} from a data-raw dump; PalmError when a palm
    or a field is missing, or a text reads a named expression the copies cannot carry."""
    nf = dump.get("noise-function") or {}
    ne = dump.get("noise-expression") or {}
    out = {"trees": {}, "functions": {}}
    pending = []
    for tree in trees:
        ap = ((dump.get("tree") or {}).get(tree) or {}).get("autoplace")
        if not ap:
            raise PalmError(f"the dump has no autoplace for {tree}")
        rec = {}
        for field in ("probability_expression", "richness_expression"):
            if ap.get(field) is None:
                raise PalmError(f"{tree} has no {field}")
            rec[field] = ap[field]
        rec["local_expressions"] = dict(ap.get("local_expressions") or {})
        out["trees"][tree] = rec
        texts = [rec["probability_expression"], rec["richness_expression"]] + list(rec["local_expressions"].values())
        pending.append((tree, set(rec["local_expressions"]), texts))
    seen = set()
    while pending:
        where, local, texts = pending.pop()
        for text in texts:
            if isinstance(text, str) and ('"' in text or "\\" in text or "\n" in text):
                raise PalmError(f"{where}: a text holds a double quote, backslash or newline: {text[:80]!r}")
            for n in idents(text):
                if n in local or n in READS:
                    continue
                if n in nf:
                    if n not in seen:
                        seen.add(n)
                        f = nf[n]
                        rec = {"parameters": list(f.get("parameters") or []), "expression": f.get("expression")}
                        if f.get("local_expressions"):
                            rec["local_expressions"] = dict(f["local_expressions"])
                        if f.get("local_functions"):
                            raise PalmError(f"function {n} has local functions, which this emitter does not carry")
                        out["functions"][n] = rec
                        pending.append((n, set(rec["parameters"]) | set(rec.get("local_expressions") or {}),
                                        [rec["expression"]] + list((rec.get("local_expressions") or {}).values())))
                elif n in ne:
                    raise PalmError(f"{where} reads the named expression {n}, which the copies cannot freeze")
    return out


def run_modset(run_dir):
    rj = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    if rj.get("isolated") is not True or rj.get("error_lines"):
        raise PalmError(f"{run_dir}: run.json is not an isolated run without error lines")
    return rj.get("modset")


def ab_zip(ws, modset):
    """(version, sha256) of the modset's Alien Biomes zip."""
    d = Path(ws) / "test-instance" / "modsets" / modset
    zips = sorted(d.glob(f"{AB}_*.zip"))
    if len(zips) != 1:
        raise PalmError(f"modset {modset} holds {len(zips)} {AB} zips, want 1")
    version = zips[0].stem[len(AB) + 1:]
    return version, hashlib.sha256(zips[0].read_bytes()).hexdigest()


def lua_str(s, indent):
    """A Lua string literal starting a line at `indent`, split with .. so no line runs past WIDTH."""
    room = max(40, WIDTH - indent - 6)
    parts = [s[i:i + room] for i in range(0, len(s), room)] or [""]
    return (" ..\n" + " " * indent).join(f'"{p}"' for p in parts)


def lua_value(v, indent):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise PalmError(f"number {v} has no Lua literal")
        return repr(v)
    if isinstance(v, str):
        return lua_str(v, indent)
    if isinstance(v, list):
        return "{" + ", ".join(lua_value(x, indent + 2) for x in v) + "}"
    if isinstance(v, dict):
        pad = " " * (indent + 2)
        rows = []
        for k in sorted(v):
            row = f'{pad}["{k}"] = {lua_value(v[k], indent + 2)},'
            if isinstance(v[k], str) and max(len(line) for line in row.splitlines()) > WIDTH:
                row = f'{pad}["{k}"] =\n{pad}  {lua_str(v[k], indent + 4)},'
            rows.append(row)
        return "{\n" + "\n".join(rows) + "\n" + " " * indent + "}"
    raise PalmError(f"value {v!r} has no Lua literal")


def emit(data, meta):
    head = [
        f"-- Generated by tools/build_palms.py (emitter {EMITTER}) from a dump-data run of modset {meta['modset']}",
        f"-- (data-raw-dump.json sha256 {meta['dump_sha256']}),",
        f"-- {AB} {meta['version']} (zip sha256 {meta['zip_sha256']}).",
        "-- Name-free data: trees.lua builds the Earth palm copies from it and data-final-fixes.lua compares",
        "-- the live palm autoplace with it (config.lua tiles.palm).",
        "-- Never edit by hand: rerun the tool (plan hard rule 9).",
    ]
    body = {"source": {"mod": AB, "version": meta["version"], "zip_sha256": meta["zip_sha256"],
                       "dump_sha256": meta["dump_sha256"], "digest": digest(data), "emitter": EMITTER},
            "trees": data["trees"], "functions": data["functions"]}
    text = "\n".join(head) + "\nreturn " + lua_value(body, 0) + "\n"
    long = [i + 1 for i, line in enumerate(text.splitlines()) if len(line) > 120]
    if long:
        raise PalmError(f"emitted lines {long[:5]} run past 120 characters")
    return text


def table_path(cfg):
    mod_path = cfg["tiles"]["palm"]["table"]
    return MOD / (mod_path.replace(".", "/") + ".lua")


def trees_of(cfg):
    return list(dict.fromkeys(c["tree"] for c in cfg["tiles"]["palm"]["copies"]))


def check(cfg=None):
    """Findings for the committed table: it loads as pure data, its digest matches its own data, it
    records the trees config.lua copies and every field the copies read."""
    cfg = cfg or tnconfig.load()
    p = table_path(cfg)
    if not p.exists():
        return [f"{p.relative_to(REPO).as_posix()} is missing: run python tools/build_palms.py --dump <run>"]
    out = []
    t = tnconfig.load(p)
    src = t.get("source") or {}
    if src.get("mod") != AB or not src.get("version") or not re.fullmatch(r"[0-9a-f]{64}", str(src.get("zip_sha256"))):
        out.append(f"{p.name}: source {src} does not record {AB}'s version and zip sha256")
    if src.get("digest") != digest(t):
        out.append(f"{p.name}: its digest {src.get('digest')} differs from its data's {digest(t)}: rerun the tool, "
                   f"never edit it by hand")
    for tree in trees_of(cfg):
        rec = (t.get("trees") or {}).get(tree) or {}
        for field in ("probability_expression", "richness_expression", "local_expressions"):
            if field not in rec:
                out.append(f"{p.name}: {tree} has no {field}")
    # the mod reads the table through literal requires (the registration scan reads literal module
    # names), which must name the file config.lua names
    lit = f'require("{cfg["tiles"]["palm"]["table"]}")'
    for rel in ("prototypes/expressions/trees.lua", "data-final-fixes.lua"):
        if lit not in (MOD / rel).read_text(encoding="utf-8"):
            out.append(f"terra-nauvis/{rel} does not read the palm table with {lit}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", help="a dump-data run directory of a modset holding Alien Biomes")
    ap.add_argument("--ws", default=r"%FACTORIO_WS%", help="the Factorio workspace")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cfg = tnconfig.load()
    if a.check:
        f = check(cfg)
        print(f"PALMS {'ok' if not f else 'fail'} {f[:3]}")
        return 0 if not f else 1
    if not a.dump:
        ap.error("--dump or --check")
    run = Path(a.dump)
    raw = (run / "data-raw-dump.json").read_bytes()
    data = palm_table(json.loads(raw.decode("utf-8")), trees_of(cfg))
    modset = run_modset(run)
    version, zsha = ab_zip(a.ws, modset)
    meta = {"modset": modset, "version": version, "zip_sha256": zsha, "dump_sha256": hashlib.sha256(raw).hexdigest()}
    text = emit(data, meta)
    out = table_path(cfg)
    out.write_text(text, encoding="utf-8", newline="\n")
    back = tnconfig.load(out)
    if digest(back) != digest(data):
        raise PalmError(f"{out}: the written table reads back with another digest")
    print(f"PALMS ok wrote {out.relative_to(REPO).as_posix()} ({AB} {version}, {len(data['trees'])} palms, "
          f"functions {sorted(data['functions'])}, digest {digest(data)[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
