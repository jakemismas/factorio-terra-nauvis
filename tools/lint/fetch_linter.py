#!/usr/bin/env python3
"""Download the linter that tools/lint/manifest.json records and check its sha256 (ci.yml, release.yml).

  python tools/lint/fetch_linter.py --dest <new directory> [--github-env <GITHUB_ENV file>]

The binary lands in its own directory (downloads are untrusted data, project rule 8) and is accepted
only when its sha256 equals the manifest's. With --github-env, TN_LUACHECK is appended there so the
later steps' `earth_test.py static` finds it. It reads no secret and touches nothing else. Both
output options pass tools/tnguard.py's refusal (the live profile, any folder named mods and any
spelling but a plain drive-letter path), like every other tool's.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import tnguard  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dest", required=True)
    ap.add_argument("--github-env")
    a = ap.parse_args(argv)
    tnguard.refuse_live_outputs(a, "fetch_linter.py")
    m = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))["linter"]
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / Path(m["source"]).name
    with urllib.request.urlopen(m["source"], timeout=120) as r:
        data = r.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != m["sha256"]:
        print(f"RESULT fail {m['source']} has sha256 {digest}, manifest records {m['sha256']}")
        return 1
    target.write_bytes(data)
    if a.github_env:
        with open(a.github_env, "a", encoding="utf-8") as f:
            f.write(f"TN_LUACHECK={target}\n")
    print(f"RESULT ok {m['name']} {m['version']} sha256={digest} path={target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
