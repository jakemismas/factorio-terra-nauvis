#!/usr/bin/env python3
"""Write tests/vanilla-raw.json, the base game's prototypes the offline data stage reads, from the installed game.

  python tools/make_vanilla_raw.py                    dump through %FACTORIO_WS%/tools/fh.py, then reduce
  python tools/make_vanilla_raw.py --dump FILE        reduce a data-raw-dump.json made another way
  python tools/make_vanilla_raw.py --out FILE         write FILE instead of tests/vanilla-raw.json

tools/tnlua.py seeds data.raw with this file, so the bodies, release_zip and fixtures rows and
build_zip.py --release build the bodies the game builds. The dump runs the base game alone: no other mod,
every expansion mod disabled (fh.py modset --expansion none), in an instance and a modset of its own, and
a RESULT line without isolated=yes, or a log naming a mod other than core and base, fails. A dump given
with --dump must come from such a run too (Factorio 2.1, `--dump-data`, base only). The reduction keeps
planet, autoplace-control, noise-expression and noise-function whole, and keeps name, type, autoplace,
collision_mask, order and subgroup of every resource, tile, tree, optimized-decorative and simple-entity
(tnlua.VANILLA_WHOLE, VANILLA_REDUCED, VANILLA_FIELDS). The output is sorted JSON, so the same game gives
the same bytes. Regenerate after a game update; the bodies row then shows whether a body moved.

Prints one RESULT line; exit 0 only when the file was written.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import tnlua  # noqa: E402

OUT = tnlua.VANILLA_RAW
NOTE = ("The base game's prototypes the mod's data stage reads (data-final-fixes.lua's hooks and wrappers), from a "
        "base-only --dump-data of the installed game: planet, autoplace-control, noise-expression and noise-function "
        "whole, and resource, tile, tree, optimized-decorative and simple-entity reduced to name, type, autoplace, "
        "collision_mask, order and subgroup. tools/tnlua.py seeds data.raw with it, so the offline data stage builds "
        "the bodies the game builds (the bodies row, build_zip.py --release). Regenerate from a new base-only dump "
        "after a game update.")
INSTANCE = "tn-vanilla-raw"
TIMEOUT = 600
CHECKSUM_RE = re.compile(r"Checksum of (\S+):")
VERSION_RE = re.compile(r"Loading mod base (\d+)\.(\d+)\.\d+")


class MakeError(Exception):
    pass


def reduce_dump(dump):
    """{"format", "note", "raw"} from a whole data-raw-dump.json, by the tnlua.VANILLA_* rule."""
    raw = {}
    for t in tnlua.VANILLA_WHOLE + tnlua.VANILLA_REDUCED:
        protos = dump.get(t)
        if not isinstance(protos, dict) or not protos:
            raise MakeError(f"the dump holds no {t} prototypes: it is not a Factorio 2.1 --dump-data")
        if t in tnlua.VANILLA_WHOLE:
            raw[t] = protos
        else:
            raw[t] = {n: {k: p[k] for k in tnlua.VANILLA_FIELDS if k in p} for n, p in protos.items()}
    planets = sorted(raw["planet"])
    if planets != ["nauvis"]:
        raise MakeError(f"the dump defines the planets {planets}: an expansion or another mod was loaded "
                        f"(base alone defines nauvis only)")
    return {"format": tnlua.VANILLA_RAW_FORMAT, "note": NOTE, "raw": raw}


def dump_text(data):
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def fh_path():
    ws = Path(os.path.abspath(os.environ.get("FACTORIO_WS") or REPO.parent))
    fh = ws / "tools" / "fh.py"
    if not fh.is_file():
        raise MakeError(f"no harness at {fh}: set FACTORIO_WS to the folder whose tools/fh.py runs the game, "
                        f"or pass --dump with a base-only data-raw-dump.json")
    return ws, fh


def fh(ws, script, args):
    cp = subprocess.run([sys.executable, str(script)] + [str(a) for a in args], cwd=str(ws), capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    lines = [ln for ln in (cp.stdout or "").splitlines() if ln.startswith("RESULT")]
    return lines[-1] if lines else "RESULT fail (no RESULT line) " + ((cp.stdout or "") + (cp.stderr or "")).strip()[-300:]


def run_dump(instance, modset, work):
    """The data-raw-dump.json of a base-only --dump-data run through fh.py, as a dict."""
    ws, script = fh_path()
    res = fh(ws, script, ["modset", modset, "--expansion", "none"])
    print("fh:", res)
    if not res.startswith("RESULT ok") or " enabled=base " not in res + " ":
        raise MakeError(f"the modset {modset} is not base alone: {res}")
    out = Path(work) / "dump"
    res = fh(ws, script, ["dump-data", "--instance", instance, "--modset", modset, "--timeout", TIMEOUT, "--out", out])
    print("fh:", res)
    if not res.startswith("RESULT ok") or " isolated=yes " not in res or " errors=0 " not in res:
        raise MakeError(f"the dump run failed or was not isolated: {res}")
    stdout = (out / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    mods = sorted(set(CHECKSUM_RE.findall(stdout)))
    if mods != ["base"]:
        raise MakeError(f"the dump run loaded {mods}, not base alone")
    m = VERSION_RE.search(stdout)
    if not m or (m.group(1), m.group(2)) != ("2", "1"):
        raise MakeError(f"the dump run is not Factorio 2.1 ({m.group(0) if m else 'no base version line'})")
    return json.loads((out / "data-raw-dump.json").read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", help="a base-only data-raw-dump.json to reduce; no game is launched")
    ap.add_argument("--out", default=str(OUT), help="the file to write (default tests/vanilla-raw.json)")
    ap.add_argument("--instance", default=INSTANCE, help="fh.py instance for the dump run")
    ap.add_argument("--modset", default=INSTANCE, help="fh.py modset for the dump run, base alone")
    ap.add_argument("--work", help="a new folder for the dump run's evidence (default: a temporary one)")
    a = ap.parse_args(argv)
    try:
        if a.dump:
            dump = json.loads(Path(a.dump).read_text(encoding="utf-8"))
        elif a.work:
            work = Path(a.work).resolve()
            if work.exists() and any(work.iterdir()):
                raise MakeError(f"{work} already holds files; give a new --work")
            dump = run_dump(a.instance, a.modset, work)
        else:
            with tempfile.TemporaryDirectory(prefix="tn-vanilla-raw-") as td:
                dump = run_dump(a.instance, a.modset, td)
        text = dump_text(reduce_dump(dump))
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(text.encode("utf-8"))
        problem = tnlua.vanilla_raw_problem(out)
        if problem:
            raise MakeError(f"the written file does not read back: {problem}")
    except (MakeError, OSError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1
    counts = ",".join(f"{t}={len(json.loads(text)['raw'][t])}" for t in tnlua.VANILLA_WHOLE + tnlua.VANILLA_REDUCED)
    print(f"RESULT ok out={out} bytes={len(text.encode('utf-8'))} {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
