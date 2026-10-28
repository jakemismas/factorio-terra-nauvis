#!/usr/bin/env python3
"""Package terra-nauvis/ into a byte-reproducible mod zip (T16 zip row; ARCHITECTURE.md data flow 7).

  python tools/build_zip.py                    the zip under dist/ (installCheck and ci.yml)
  python tools/build_zip.py --release          the release zip plus its .sha256 (release.yml)
  python tools/build_zip.py --check-tag v0.1.0 fail unless the tag is "v" plus info.json's version

The zip holds one top folder, terra-nauvis/, with every file of the mod folder in sorted order,
fixed timestamps, fixed attributes and no compression, so two builds give one sha256 on this
machine and on GitHub's windows-latest runner alike (the repo checks out LF everywhere). Stored
entries keep the bytes independent of the zlib build, and the build record names the interpreter
and zlib versions anyway.

It reads only the checked-out tree: no git refs, no fh.py, no FACTORIO_WS, no game.

--release refuses while config.lua marks any placeholder name (the placeholder is never released)
and when any Earth noise body config.lua defines, released or a firewall body, is missing from
tests/frozen.json (the Map type fallbacks excepted; design constraint 2). It finds the bodies
statically, through the luaparser loader, because release.yml runs without the game; the gate's
frozen row checks the dumped bodies themselves. Every build refuses an output folder inside the
live profile, with a path segment named mods, in any spelling but a plain drive-letter path (the
NT namespace included), or holding a second hard link of a file or a link into the live profile
(nothing in the repo installs into a mods folder; tools/tnguard.py).
"""
import argparse
import hashlib
import json
import platform
import re
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402
import tnguard  # noqa: E402

REPO = HERE.parent
MOD = REPO / "terra-nauvis"
FROZEN = REPO / "tests" / "frozen.json"
DIST = REPO / "dist"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
FILE_ATTR = (0o100644 << 16)
DIR_ATTR = (0o040755 << 16) | 0x10
# Only these files may ship; anything else (scratch, editor backups, caches) fails the build.
ALLOWED_SUFFIXES = {".lua", ".json", ".cfg", ".txt", ".png", ".md"}
ALLOWED_PLAIN = {"LICENSE"}
# Folder names that hold build output or scratch anywhere else; none of them belongs in the mod, and
# every T16 mod scan reads this module's file list, so nothing ships unscanned.
REFUSED_DIRS = {"dist", "spikes", "node_modules", "__pycache__"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class BuildError(RuntimeError):
    pass


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(Path(p).read_bytes())


def mod_identity(mod_dir=MOD, config_path=None):
    """(id, version) from config.lua, checked against info.json."""
    cfg = tnconfig.load(config_path or (mod_dir / "prototypes" / "config.lua"))
    info = json.loads((mod_dir / "info.json").read_text(encoding="utf-8"))
    ident = cfg["identity"]
    if info.get("name") != ident["id"]:
        raise BuildError(f"info.json name {info.get('name')!r} differs from config.lua id {ident['id']!r}")
    if info.get("version") != ident["version"]:
        raise BuildError(f"info.json version {info.get('version')!r} differs from config.lua {ident['version']!r}")
    if not VERSION_RE.match(ident["version"]):
        raise BuildError(f"version {ident['version']!r} is not x.y.z")
    return ident["id"], ident["version"], cfg


def classify_files(mod_dir=MOD):
    """(the files that ship, the files the build refuses), sorted POSIX paths relative to the mod
    folder. The T16 mod scans read both lists, so no file in the folder escapes them."""
    out, bad = [], []
    for p in sorted(mod_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(mod_dir).as_posix()
        parts = rel.split("/")
        if any(x.startswith(".") for x in parts) or any(x.lower() in REFUSED_DIRS for x in parts[:-1]):
            bad.append(rel)
        elif p.suffix.lower() not in ALLOWED_SUFFIXES and p.name not in ALLOWED_PLAIN:
            bad.append(rel)
        else:
            out.append(rel)
    return sorted(out), sorted(bad)


def mod_files(mod_dir=MOD):
    """Every file of the mod folder, as sorted POSIX paths relative to it; refuses unexpected files."""
    out, bad = classify_files(mod_dir)
    if bad:
        raise BuildError("files that may not ship in the mod folder: " + ", ".join(bad[:10]))
    if "info.json" not in out:
        raise BuildError("terra-nauvis/info.json is missing")
    return sorted(out)


def zip_bytes(mod_dir=MOD, top=None):
    """The zip as bytes plus its entry list. top is the zip's single top folder."""
    files = mod_files(mod_dir)
    top = top or mod_dir.name
    dirs = set()
    for rel in files:
        parts = rel.split("/")[:-1]
        for i in range(len(parts)):
            dirs.add("/".join(parts[: i + 1]))
    entries = [(f"{top}/", None)] + [(f"{top}/{d}/", None) for d in sorted(dirs)]
    entries += [(f"{top}/{rel}", (mod_dir / rel).read_bytes()) for rel in files]
    entries.sort(key=lambda e: e[0])
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in entries:
            zi = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            zi.create_system = 3
            zi.compress_type = zipfile.ZIP_STORED
            if data is None:
                zi.external_attr = DIR_ATTR
                zf.writestr(zi, b"")
            else:
                zi.external_attr = FILE_ATTR
                zf.writestr(zi, data)
    listing = [{"name": n, "bytes": len(d), "sha256": sha256_bytes(d)} for n, d in entries if d is not None]
    return buf.getvalue(), listing


def placeholder_names(cfg):
    ph = cfg.get("placeholder") or {}
    names = sorted((ph.get("names") or {}).values())
    presets = sorted(p["name"] for p in (cfg.get("presets") or {}).values() if p.get("placeholder"))
    return names, presets


def release_problems(cfg, frozen_path=FROZEN):
    """Why a release build must refuse, as a list of messages (empty means it may proceed): any
    placeholder name, any config.lua schema problem, and any Earth noise body config.lua defines
    (released bodies and firewall bodies alike) that tests/frozen.json does not register, the Map
    type fallbacks excepted (U3's one exemption: they mirror startup settings and are never
    registered; design constraint 2: --release refuses any other unregistered body)."""
    problems = []
    names, presets = placeholder_names(cfg)
    if names or presets:
        problems.append("config.lua marks placeholder names " + ", ".join(names + presets) +
                        "; the placeholder is never released (europe-coast retires it)")
    problems += [f"config.lua schema: {x}" for x in tnconfig.schema_problems(cfg)]
    try:
        frozen = json.loads(Path(frozen_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return problems + [f"tests/frozen.json is unreadable: {e}"]
    registered = frozen.get("bodies") or {}
    exempt = set(tnconfig.fallback_names(cfg))
    releases = {n: r.get("release") for r in tnconfig.release_registry(cfg) for n in (r.get("names") or [])}
    for name in tnconfig.unregistered_names(cfg, registered):
        where = f"of release {releases[name]}" if name in releases else "(a firewall body in no release row)"
        problems.append(f"Earth body {name} {where} is not registered in tests/frozen.json: run python "
                        f"tools/earth_test.py freeze")
    for name in sorted(exempt & set(registered)):
        problems.append(f"Map type fallback {name} is registered in tests/frozen.json (fallbacks never are)")
    return problems


def check_tag(tag, mod_dir=MOD):
    _, version, _ = mod_identity(mod_dir)
    want = "v" + version
    if tag != want:
        raise BuildError(f"tag {tag!r} does not equal 'v' plus info.json's version ({want!r})")
    return want


def build(out_dir=DIST, release=False, mod_dir=MOD, frozen_path=FROZEN):
    why = tnguard.live_output_problem(out_dir)
    if why:
        raise BuildError(f"refusing --out-dir: {why}")
    mod_id, version, cfg = mod_identity(mod_dir)
    if release:
        problems = release_problems(cfg, frozen_path)
        if problems:
            raise BuildError("release refused: " + "; ".join(problems))
    data, listing = zip_bytes(mod_dir, top=mod_id)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{mod_id}_{version}.zip"
    zpath = out_dir / name
    zpath.write_bytes(data)
    digest = sha256_bytes(data)
    record = {"zip": name, "sha256": digest, "bytes": len(data), "entries": listing,
              "python": platform.python_version(), "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
              "compression": "stored", "release": release}
    (out_dir / f"{mod_id}_{version}.build.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8",
                                                           newline="\n")
    if release:
        (out_dir / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8", newline="\n")
    return zpath, digest, record


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--release", action="store_true", help="the release zip and its .sha256")
    ap.add_argument("--check-tag", metavar="TAG", help="fail unless TAG is 'v' plus info.json's version")
    ap.add_argument("--out-dir", default=str(DIST))
    ap.add_argument("--mod-dir", default=str(MOD), help=argparse.SUPPRESS)
    ap.add_argument("--frozen", default=str(FROZEN), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    tnguard.refuse_live_outputs(a, "build_zip.py")
    try:
        if a.check_tag is not None:
            want = check_tag(a.check_tag, Path(a.mod_dir))
            print(f"RESULT ok tag={a.check_tag} matches info.json version ({want})")
            return 0
        zpath, digest, rec = build(a.out_dir, a.release, Path(a.mod_dir), Path(a.frozen))
    except (BuildError, tnconfig.ConfigError, OSError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1
    print(f"RESULT ok zip={zpath} sha256={digest} files={len(rec['entries'])} bytes={rec['bytes']} "
          f"release={'yes' if a.release else 'no'} python={rec['python']} zlib={rec['zlib_runtime']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
