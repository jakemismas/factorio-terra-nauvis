#!/usr/bin/env python3
"""Package terra-nauvis/ into a byte-reproducible mod zip (T16 zip row; ARCHITECTURE.md data flow 7).

  python tools/build_zip.py                    the zip under dist/ (installCheck, ci.yml and latest.yml)
  python tools/build_zip.py --release          the release zip plus its .sha256 (release.yml)
  python tools/build_zip.py --check-tag v0.1.0 fail unless the tag is "v" plus info.json's version,
                                               names the checked-out commit and sits on origin/main
  python tools/build_zip.py --out-dir <folder> the zip in another folder (outside the checkout, a
                                               landing: see below)

The zip holds one top folder, terra-nauvis/, with every file of the mod folder in sorted order,
fixed timestamps, fixed attributes and no compression, so two builds give one sha256 on this
machine and on GitHub's windows-latest runner alike (the repo checks out LF everywhere). Stored
entries keep the bytes independent of the zlib build, and the build record names the interpreter
and zlib versions anyway. It needs no fh.py, no FACTORIO_WS and no game.

--release refuses while config.lua marks any placeholder name (the placeholder is never released)
and when any Earth noise body config.lua defines, released or a firewall body, is missing from
tests/frozen.json (the Map type fallbacks excepted; design constraint 2). The region layer's every
body counts: its row names come from config.lua's stems and suffix and the region table's row ids,
composed by tools/tnconfig.py as regions.lua composes them. It finds the bodies statically, through
the luaparser loader, because release.yml runs without the game; the gate's frozen row checks the
dumped bodies themselves. --out-dir takes any folder, the live mods folder
included: copying the built zip there is allowed, and the build
record lands beside the zip (and the .sha256 with --release).
"""
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

--release refuses while config.lua marks any placeholder name (the placeholder is never released),
when a tests/frozen.json record breaks the tnfrozen contract (tools/tnfrozen.py: every field well
formed, the dump label one the runner's milestone registry assigns, read from tools/earth_test.py's
source), when any Earth noise body config.lua defines, released or a firewall body, is missing
from tests/frozen.json (the Map type fallbacks excepted; design constraint 2), and when a body
moved: it builds every Earth body from the mod's own code offline (the settings and data stages
under tools/tnlua.py, at default settings; the gate's frozen row holds that reading equal to the
game's dump) and refuses any registered body whose hash differs from its record, any registered
name the code no longer defines and any Earth body it does not register; it refuses a registry
that changed or dropped a record of a milestone's frozen snapshot (tests/baselines/suites/<milestone>.json,
a group's registries before they land) and, against every earlier v<x.y.z> release tag, anything
the T16 append-only rule fixes. release.yml checks out full history and runs --check-tag first,
which refuses a tag that is not the checked-out commit or whose commit is not on origin/main, so a
release ships only a commit main's history holds, never a branch commit that skipped CI.

--out-dir takes any folder, the live mods folder included: copying the built zip there is allowed
, and the build record lands beside the zip (and the .sha256 with
--release). A zip that leaves the checkout lands: once it is in a mods folder, a save can be made
from its bodies, so its registry counts as landed from then (design constraint 2). Such a build
applies the release's body and snapshot checks, reads the zips of this mod already in the folder
(and the build records beside them, which this tool wrote) and refuses when any body one of them
defines is changed or dropped here, or any record a build record's snapshot holds moved, and writes
the zip's bodies and its registry's snapshot into its own build record. It reads nothing else in
the folder.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tnconfig  # noqa: E402
import tnfrozen  # noqa: E402

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
SHA1_RE = re.compile(r"[0-9a-f]{40}")
MAIN_REF = "origin/main"


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


def active_moves(repo=REPO):
    """The waiver of a tree with no release yet (tnfrozen.active_moves), or None. Fails closed."""
    import tn_static
    try:
        return tnfrozen.active_moves(tn_static.release_tag_refs(repo), Path(repo) / "tests" / "unreleased-moves.json")
    except tn_static.ReferenceUnreadable as e:
        raise tnfrozen.RegistryUnreadable(str(e)) from e


def offline_body_problems(mod_dir, cfg, frozen, registry, suites=tnfrozen.SUITES, where="the offline data stage"):
    """(problems, bodies): every Earth body the mod at `mod_dir` builds offline (tnlua), held to its
    tests/frozen.json record (tnfrozen.body_problems), and the registry held to every milestone's frozen
    snapshot, the waiver's records excepted. The offline stage failing, or a manifest that does not
    parse, fails closed."""
    try:
        bodies = tnfrozen.offline_bodies(mod_dir, cfg)
        beside_ab = tnfrozen.offline_ab_problems(mod_dir, frozen, cfg)
    except Exception as e:  # tnlua.LuaError and anything else the stage raises
        return [f"the offline data stage did not run: {type(e).__name__}: {e} (fail closed)"], None
    problems = tnfrozen.body_problems(bodies, frozen, cfg, where) + beside_ab
    try:
        snaps, _ = tnfrozen.suite_snapshots(registry, suites=suites)
        moves = active_moves()
    except tnfrozen.RegistryUnreadable as e:
        return problems + [f"the slices' frozen snapshots are unreadable: {e}"], bodies
    return problems + tnfrozen.snapshot_problems(frozen, snaps, moves), bodies


def released_problems(frozen, cfg, repo=REPO):
    """What the registry and config.lua changed of every earlier release (the v<x.y.z> tags the
    checkout holds), by the T16 append-only rule; [] when no release exists yet. Fails closed."""
    import tn_static
    try:
        tags = tn_static.release_tag_refs(repo)
        if not tags:
            return []
        refs, _ = tn_static.append_only_reference(repo, tags)
    except tn_static.ReferenceUnreadable as e:
        return [f"the earlier releases are unreadable: {e} (fail closed)"]
    return [f"against the earlier releases: {x}" for x in tn_static.append_only_findings(frozen, cfg, refs)]


def release_problems(cfg, frozen_path=FROZEN, registry=None, mod_dir=MOD, suites=tnfrozen.SUITES, repo=REPO):
    """Why a release build must refuse, as a list of messages (empty means it may proceed): any
    placeholder name, any config.lua schema problem, a tests/frozen.json that breaks the tnfrozen
    record contract against the runner's milestone registry (read statically from tools/earth_test.py,
    failing closed; a record whose dump label no registry entry assigns is never checked by the
    gate), any Earth noise body config.lua defines (released bodies, the region table's composed row
    names among them, and firewall bodies alike) that tests/frozen.json does not register, the Map
    type fallbacks that mirror startup settings excepted (U3's one exemption: they are never
    registered, while a frozen fallback is registered like every body; design constraint 2: --release
    refuses any other unregistered body), any body the mod's code builds (offline, tnlua) that differs
    from its record or is unregistered, any registered name it no longer builds, any record a milestone's
    frozen snapshot holds that the registry moved, and anything an earlier release tag fixes that
    moved. `cfg` loaded from a mod folder's config.lua reads that folder's region table
    (tnconfig.Config.source)."""
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
    try:
        registry = tnfrozen.runner_registry() if registry is None else registry
    except tnfrozen.RegistryUnreadable as e:
        return problems + [f"the runner's slice registry is unreadable: {e} (fail closed)"]
    problems += tnfrozen.file_problems(frozen, registry)
    registered = frozen.get("bodies") if isinstance(frozen, dict) and isinstance(frozen.get("bodies"), dict) else {}
    try:
        exempt = set(tnconfig.exempt_fallback_names(cfg))
        releases = tnconfig.release_of(cfg)
    except tnconfig.ConfigError as e:
        return problems + [f"config.lua schema: {e}"]
    for name in tnconfig.unregistered_names(cfg, registered):
        where = f"of release {releases[name]}" if name in releases else "(a firewall body in no release row)"
        problems.append(f"Earth body {name} {where} is not registered in tests/frozen.json: run python "
                        f"tools/earth_test.py freeze")
    for name in sorted(exempt & set(registered)):
        problems.append(f"Map type fallback {name} mirrors a startup setting and is registered in "
                        f"tests/frozen.json (such fallbacks never are; U3)")
    found, _ = offline_body_problems(mod_dir, cfg, frozen, registry, suites)
    problems += found
    problems += released_problems(frozen, cfg, repo)
    return problems


def check_tag(tag, mod_dir=MOD):
    _, version, _ = mod_identity(mod_dir)
    want = "v" + version
    if tag != want:
        raise BuildError(f"tag {tag!r} does not equal 'v' plus info.json's version ({want!r})")
    return want


def _git(args, repo):
    try:
        cp = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    except OSError as e:
        raise BuildError(f"git is not runnable ({e}) (fail closed)") from e
    return cp.returncode, (cp.stdout or "").strip(), (cp.stderr or "").strip()


def check_landed(tag, repo=REPO, main_ref=MAIN_REF):
    """The tag check's second half (release.yml checks out full history): the tag names the
    checked-out commit, and that commit is on `main_ref` (its head or an ancestor), so a release ships
    only what main's history holds, past CI's append-only reference, never a branch commit pushed with
    a tag. Returns (the tag's commit, main's head); raises BuildError, failing closed when git, the tag
    or `main_ref` does not resolve."""
    if not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise BuildError(f"tag {tag!r} is not v<x.y.z>")
    rc, tag_sha, _ = _git(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"], repo)
    if rc != 0 or not SHA1_RE.fullmatch(tag_sha):
        raise BuildError(f"tag {tag} does not resolve to a commit in {repo} (fail closed)")
    rc, head, _ = _git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], repo)
    if rc != 0 or head != tag_sha:
        raise BuildError(f"the checked-out commit {head[:12] or '(none)'} is not tag {tag}'s {tag_sha[:12]}")
    rc, main_sha, _ = _git(["rev-parse", "--verify", "--quiet", f"{main_ref}^{{commit}}"], repo)
    if rc != 0 or not SHA1_RE.fullmatch(main_sha):
        raise BuildError(f"{main_ref} does not resolve: the tag check needs the full history (fetch-depth 0) "
                         f"(fail closed)")
    rc, _, err = _git(["merge-base", "--is-ancestor", tag_sha, main_sha], repo)
    if rc == 1:
        raise BuildError(f"tag {tag} names {tag_sha[:12]}, which is not on {main_ref} (head {main_sha[:12]}): a "
                         f"release ships only a commit main's history holds")
    if rc != 0:
        raise BuildError(f"git merge-base --is-ancestor failed ({err[:200]}) (fail closed)")
    return tag_sha, main_sha


def leaves_checkout(out_dir, repo=REPO):
    """Whether `out_dir` lies outside the checkout (a mods folder, or any other place a zip can be
    loaded from): such a build is a landing."""
    o = os.path.normcase(str(Path(out_dir).resolve()))
    r = os.path.normcase(str(Path(repo).resolve()))
    return not (o == r or o.startswith(r.rstrip("\\/") + os.sep))


def landed_zips(out_dir, mod_id):
    """The zips of this mod already in `out_dir` (<id>_<x.y.z>.zip), sorted."""
    pat = re.compile(re.escape(mod_id) + r"_\d+\.\d+\.\d+\.zip")
    d = Path(out_dir)
    return sorted(p for p in d.glob(f"{mod_id}_*.zip") if p.is_file() and pat.fullmatch(p.name)) if d.is_dir() else []


def landing_problems(out_dir, mod_dir, cfg, frozen, registry, suites=tnfrozen.SUITES):
    """Why a zip may not land in `out_dir` (leaves_checkout): the release's offline body and snapshot
    checks, then every zip of this mod already there (a save may have been made from it): each body it
    defines, read offline from the zip itself, must be built here unchanged, and each record its build
    record's snapshot holds must stand in tests/frozen.json. Returns (problems, this build's bodies)."""
    problems, bodies = offline_body_problems(mod_dir, cfg, frozen, registry, suites, "the zip's data stage")
    if bodies is None:
        return problems, None
    new = tnfrozen.body_digests(bodies)
    moves = active_moves()
    import tnlua
    for z in landed_zips(out_dir, cfg["identity"]["id"]):
        where = f"{z.name} in {out_dir}"
        try:
            reader = tnlua.ZipReader(z)
            text = reader.read("prototypes/config.lua")
            if text is None:
                raise BuildError("it holds no prototypes/config.lua")
            old_cfg = tnconfig.loads(text, f"{z.name}:config.lua")
            old = tnfrozen.body_digests(tnfrozen.earth_bodies(tnlua.data_stage(reader), old_cfg))
        except Exception as e:
            problems.append(f"{where} cannot be read offline ({type(e).__name__}: {e}): a save may use its bodies, so "
                            f"no zip lands beside it (fail closed); move it out by hand once no save needs it")
            continue
        exempt = tnfrozen.exempt_names(cfg) | tnfrozen.exempt_names(old_cfg)
        for name, why in tnfrozen.body_changes(old, new, exempt):
            if tnfrozen.moved(moves, name, (old[name] or {}).get("sha256")):
                continue
            problems.append(f"{where} defines {name}, which this build {why}: a body that reached a mods folder is "
                            f"landed and never changes in place (ship a change under the next _v<n>)")
        rec_path = Path(out_dir) / f"{z.stem}.build.json"
        if rec_path.is_file():
            try:
                rec = json.loads(rec_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                problems.append(f"{rec_path.name} in {out_dir} does not parse ({e}) (fail closed)")
                continue
            snap = rec.get("frozen") if isinstance(rec, dict) else None
            if snap is not None:
                problems += tnfrozen.snapshot_problems(frozen, {f"{rec_path.name} in {out_dir}": snap}, moves)
    return problems, bodies


def build(out_dir=DIST, release=False, mod_dir=MOD, frozen_path=FROZEN, landing=False, suites=tnfrozen.SUITES):
    """Build the zip into `out_dir`. `release` applies release_problems; `landing` (the CLI sets it
    for an out-dir outside the checkout) applies landing_problems. Either refuses with BuildError,
    and either writes the bodies and the registry's snapshot into the build record."""
    mod_id, version, cfg = mod_identity(mod_dir)
    bodies = frozen = registry = None
    if release or landing:
        try:
            frozen = json.loads(Path(frozen_path).read_text(encoding="utf-8"))
            registry = tnfrozen.runner_registry()
        except (OSError, ValueError) as e:
            raise BuildError(f"tests/frozen.json is unreadable: {e}") from e
        except tnfrozen.RegistryUnreadable as e:
            raise BuildError(f"the runner's slice registry is unreadable: {e} (fail closed)") from e
    if release:
        problems = release_problems(cfg, frozen_path, registry, mod_dir, suites)
        if problems:
            raise BuildError("release refused: " + "; ".join(problems))
    if landing:
        problems, bodies = landing_problems(out_dir, mod_dir, cfg, frozen, registry, suites)
        if problems:
            raise BuildError(f"landing in {out_dir} refused: " + "; ".join(problems))
    if (release or landing) and bodies is None:
        bodies = tnfrozen.offline_bodies(mod_dir, cfg)
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
    if bodies is not None:
        record["landing"] = bool(landing)
        record["bodies"] = tnfrozen.body_digests(bodies)
        record["frozen"] = tnfrozen.snapshot(frozen, registry, registry[-1]["id"])
    (out_dir / f"{mod_id}_{version}.build.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8",
                                                           newline="\n")
    if release:
        (out_dir / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8", newline="\n")
    return zpath, digest, record


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--release", action="store_true", help="the release zip and its .sha256")
    ap.add_argument("--check-tag", metavar="TAG", help="fail unless TAG is 'v' plus info.json's version, names the "
                                                       "checked-out commit and is on origin/main")
    ap.add_argument("--out-dir", default=str(DIST), help="the zip's folder; one outside the checkout is a landing")
    ap.add_argument("--mod-dir", default=str(MOD), help=argparse.SUPPRESS)
    ap.add_argument("--frozen", default=str(FROZEN), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        if a.check_tag is not None:
            want = check_tag(a.check_tag, Path(a.mod_dir))
            tag_sha, main_sha = check_landed(a.check_tag)
            print(f"RESULT ok tag={a.check_tag} matches info.json version ({want}) and names the checked-out commit "
                  f"{tag_sha[:12]}, on {MAIN_REF} (head {main_sha[:12]})")
            return 0
        zpath, digest, rec = build(a.out_dir, a.release, Path(a.mod_dir), Path(a.frozen),
                                   landing=leaves_checkout(a.out_dir))
    except (BuildError, tnconfig.ConfigError, tnfrozen.RegistryUnreadable, OSError, ValueError) as e:
        print(f"RESULT fail {e}")
        return 1
    print(f"RESULT ok zip={zpath} sha256={digest} files={len(rec['entries'])} bytes={rec['bytes']} "
          f"release={'yes' if a.release else 'no'} python={rec['python']} zlib={rec['zlib_runtime']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
