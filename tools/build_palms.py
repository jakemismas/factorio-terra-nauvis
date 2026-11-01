#!/usr/bin/env python3
"""The digest of Alien Biomes' palm autoplace (milestone climate-tiles; config.lua tiles.palm.digest).

  python tools/build_palms.py --dump <dump-data run dir>   print the digest of a dump's palms
  python tools/build_palms.py --check [--dump <run>]       config.lua's digest is well formed, a dump's palms match it

The Earth copies of Alien Biomes' palm autoplace (tn_palm_*_v1, design constraint 3's palm switch) are built at
data-final-fixes from the installed palms and hold no Alien Biomes text in this repository. Those names are
registered, so their generation fields must never follow a newer Alien Biomes in place (design constraint 2, decision
21). This tool reads each palm config.lua's tiles.palm.copies names from one dump-data run, with the noise functions
its texts call, and reduces them to a digest, which config.lua records. data-final-fixes.lua computes the same digest
from the live prototypes: on a difference, or a missing palm, the copies are the neutral body and Earth presets name
it (log line), and the gate's dump facts fail, so an Alien Biomes update is a deliberate change. The digest is two
32-bit FNV-1a hashes, so the mod's data stage can compute it, of the canonical text below. Numbers print at 9
significant digits, as a dump's numbers round-trip through text.
"""
import argparse
import functools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402

AB = "alien-biomes"
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_:]*")


class PalmError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def spec():
    """config.lua tiles.palm.digest, which data-final-fixes.lua reads too: the constants and `reads`, the names a palm text
    may read besides its own locals and the functions it calls."""
    return tnconfig.load()["tiles"]["palm"]["digest"]


def text_of(v):
    return v if isinstance(v, str) else spec()["number"] % v


def canonical(data):
    """The text the digest reads: data-final-fixes.lua's palm_text writes the same lines."""
    lines = []
    for tree in sorted(data["trees"]):
        rec = data["trees"][tree]
        lines += [f"tree {tree}", "p " + text_of(rec["probability_expression"]),
                  "r " + text_of(rec["richness_expression"])]
        lines += [f"l {k} {text_of(v)}" for k, v in sorted(rec["local_expressions"].items())]
    for name in sorted(data["functions"]):
        f = data["functions"][name]
        lines += [f"f {name} " + ",".join(f["parameters"]), "e " + text_of(f["expression"])]
        lines += [f"l {k} {text_of(v)}" for k, v in sorted((f.get("local_expressions") or {}).items())]
    return "\n".join(lines)


def fnv(text, base, d):
    h = base
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * d["prime_low"] + (h << d["prime_shift"])) % d["word"]
    return h


def digest(data):
    d = spec()
    text = canonical(data)
    return "".join(d["hex"] % fnv(text, b, d) for b in d["bases"])


def idents(text):
    if not isinstance(text, str):
        return set()
    return set(IDENT.findall(QUOTED.sub(" ", text)))


def palm_table(dump, trees):
    """{"trees": {tree: {probability_expression, richness_expression, local_expressions}}, "functions":
    {name: {parameters, expression[, local_expressions]}}} from a data-raw dump, in memory only; PalmError when a palm
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
            for n in idents(text):
                if n in local or n in spec()["reads"]:
                    continue
                if n in nf:
                    if n not in seen:
                        seen.add(n)
                        f = nf[n]
                        rec = {"parameters": list(f.get("parameters") or []), "expression": f.get("expression")}
                        if f.get("local_expressions"):
                            rec["local_expressions"] = dict(f["local_expressions"])
                        if f.get("local_functions"):
                            raise PalmError(f"function {n} has local functions, which the copies do not carry")
                        out["functions"][n] = rec
                        pending.append((n, set(rec["parameters"]) | set(rec.get("local_expressions") or {}),
                                        [rec["expression"]] + list((rec.get("local_expressions") or {}).values())))
                elif n in ne:
                    raise PalmError(f"{where} reads the named expression {n}, which the copies cannot carry")
    return out


def trees_of(cfg):
    return list(dict.fromkeys(c["tree"] for c in cfg["tiles"]["palm"]["copies"]))


def check(cfg=None):
    """Findings for config.lua's record: an Alien Biomes version and a digest of the tool's form."""
    cfg = cfg or tnconfig.load()
    d = cfg["tiles"]["palm"].get("digest") or {}
    out = []
    if not d.get("version") or not re.fullmatch(r"[0-9a-f]{16}", str(d.get("value"))):
        out.append(f"config.lua tiles.palm.digest {d} does not record {AB}'s version and a digest from this tool")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", help="a dump-data run directory of a modset holding Alien Biomes")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cfg = tnconfig.load()
    if not a.dump and not a.check:
        ap.error("--dump or --check")
    f = check(cfg)
    if a.dump:
        raw = (Path(a.dump) / "data-raw-dump.json").read_text(encoding="utf-8")
        got = digest(palm_table(json.loads(raw), trees_of(cfg)))
        print(f"PALMS digest {got}")
        if a.check and got != cfg["tiles"]["palm"]["digest"]["value"]:
            f.append(f"the dump's palms read {got}, config.lua records {cfg['tiles']['palm']['digest']['value']}")
    if a.check:
        print(f"PALMS {'ok' if not f else 'fail'} {f[:3]}")
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
