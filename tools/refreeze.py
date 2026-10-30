#!/usr/bin/env python3
"""Re-register changed Earth bodies from fresh dumps, before the first release.

  python tools/refreeze.py --m1 <dump dir> [--m2 <dump dir>] [--m3 <dump dir>] [--write]

Reads each dump's data-raw-dump.json (fh.py dump-data; M1 base and the mod, M2 beside Alien Biomes, M3
beside the Oil Rig) and brings tests/frozen.json to them:

  a record whose dump is given and whose body hashes otherwise is re-registered in place,
  a record whose dump is given and whose body is gone is dropped,
  an Earth body no record holds is added under the runner's newest milestone (never a name the registry
  exempts: the placeholder's and the fallbacks that mirror a startup setting).

Each hash a record leaves behind, against this tree's registry, main, origin/main or a suite snapshot,
goes into tests/unreleased-moves.json, the waiver the T16 append-only row, the release build and a
landing read (tools/tnfrozen.py), so the move is named in the diff and every other record stays held.
A record of a dump not given is left alone and counted: a change that
reaches an Alien Biomes or Oil Rig body needs that dump too. It refuses once a release tag exists: a
release's records never move. Without --write it only reports.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import earth_test  # noqa: E402
import tn_static  # noqa: E402
import tnconfig  # noqa: E402
import tnfrozen  # noqa: E402

REPO = HERE.parent
FROZEN = REPO / "tests" / "frozen.json"
MOVES = REPO / "tests" / "unreleased-moves.json"


def read_dump(p):
    p = Path(p)
    f = p / "data-raw-dump.json" if p.is_dir() else p
    return json.loads(f.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8", newline="\n")


def landed_records():
    """Every record a reference ref or a suite snapshot holds, as [(name, record)]."""
    refs, _ = tn_static.append_only_reference(REPO)
    out = [(n, r) for d in refs.values() for n, r in ((d["frozen"] or {}).get("bodies") or {}).items()]
    snaps, _ = tnfrozen.suite_snapshots(earth_test.REGISTRY)
    return out + [(n, r) for s in snaps.values() for n, r in ((s or {}).get("bodies") or {}).items()]


def refreeze(fz, moves, dumps, cfg, today, newest, landed=()):
    """(the new registry, the new waiver, {changed, dropped, added, unchecked}) of `dumps`, {label: dump}.
    A landed record (`landed`) the new registry no longer equals goes into the waiver too, so a record
    an earlier commit of the branch moved is named as well."""
    fz, moves = json.loads(json.dumps(fz)), json.loads(json.dumps(moves))
    skip = earth_test.frozen_exempt(cfg)
    live = earth_test.live_masked_names(cfg)
    report = {"changed": [], "dropped": [], "added": [], "unchecked": []}

    def leave(name, rec):
        known = moves["records"].setdefault(name, [])
        if rec["sha256"] not in known:
            known.append(rec["sha256"])

    for name, rec in list(fz["bodies"].items()):
        dump = dumps.get(rec["dump"])
        if dump is None:
            report["unchecked"].append(name)
            continue
        body = (dump.get(rec["type"]) or {}).get(name)
        if body is None:
            leave(name, rec)
            del fz["bodies"][name]
            report["dropped"].append(name)
            continue
        h = tnfrozen.body_hash(body, rec.get("mask"))
        if h != rec["sha256"]:
            leave(name, rec)
            fz["bodies"][name] = dict(rec, sha256=h, registered=today)
            report["changed"].append(name)
    for label, dump in dumps.items():
        for name, (t, proto) in sorted(tnfrozen.earth_bodies(dump, cfg).items()):
            if name in skip or name in fz["bodies"]:
                continue
            mask = "live" if name in live else None
            fz["bodies"][name] = tnfrozen.record(t, tnfrozen.body_hash(proto, mask), label, newest, today, mask=mask)
            report["added"].append(name)
    for name, rec in landed:
        if fz["bodies"].get(name, {}).get("sha256") != rec["sha256"]:
            leave(name, rec)
    moves["records"] = {n: moves["records"][n] for n in sorted(moves["records"])}
    return fz, moves, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for label in ("m1", "m2", "m3"):
        ap.add_argument(f"--{label}", help="an fh.py dump-data folder (or its data-raw-dump.json)")
    ap.add_argument("--write", action="store_true", help="write tests/frozen.json and tests/unreleased-moves.json")
    a = ap.parse_args(argv)
    if not a.m1:
        print("RESULT fail refreeze needs --m1: nearly every record is an M1 body")
        return 1
    tags = tn_static.release_tag_refs(REPO)
    if tags:
        print(f"RESULT fail {tags[0]} exists: a release's records never move, so ship a change under the next _v<n>")
        return 1
    cfg = tnconfig.load()
    schema = tnconfig.schema_problems(cfg)
    if schema:
        print(f"RESULT fail config.lua schema: {schema[:2]}")
        return 1
    dumps = {label: read_dump(getattr(a, label)) for label in ("m1", "m2", "m3") if getattr(a, label)}
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    moves = tnfrozen.read_moves(MOVES)
    if moves is None:
        print("RESULT fail tests/unreleased-moves.json is missing")
        return 1
    new_fz, new_moves, rep = refreeze(fz, moves, dumps, cfg, time.strftime("%Y-%m-%d"), earth_test.REGISTRY[-1]["id"],
                                      landed_records())
    probs = tnfrozen.file_problems(new_fz, earth_test.REGISTRY) + tnfrozen.moves_problems(new_moves)
    if probs:
        print(f"RESULT fail the new registry breaks the record contract: {probs[:3]}")
        return 1
    for k in ("changed", "dropped", "added"):
        print(f"{k} {len(rep[k])}: {', '.join(rep[k][:12])}{' ...' if len(rep[k]) > 12 else ''}")
    print(f"unchecked {len(rep['unchecked'])} (their dump was not given): {', '.join(rep['unchecked'])}")
    if a.write:
        write_json(FROZEN, new_fz)
        write_json(MOVES, new_moves)
    print(f"RESULT ok refreeze changed={len(rep['changed'])} dropped={len(rep['dropped'])} added={len(rep['added'])} "
          f"records={len(new_fz['bodies'])} waived={len(new_moves['records'])} written={'yes' if a.write else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
