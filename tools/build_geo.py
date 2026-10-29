#!/usr/bin/env python3
"""Coast fit emitter (ARCHITECTURE.md, "Build-time data flow" step 2; milestone europe-coast).

  python tools/build_geo.py emit --map europe          write the generated Lua and the manifest
  python tools/build_geo.py check --map europe         re-emit twice into a scratch folder and compare
                                                       byte for byte with the committed files (T16)
  python tools/build_geo.py refit-islands --map europe the recorded local refit: model-8192 plus
                                                       level-0 tents over every reference land
                                                       component of 65 px or more it misses (T1-e)
  python tools/build_geo.py offline --map europe       offline T1 of the committed checkpoints

S1-fit's one-sided multilevel tent model (data-src/fits/<map>/, copied from the planning commit, see
PROVENANCE.md there) becomes two scale-independent bodies: the shipped coast fit
prototypes/generated/geo_<map>_v<n>.lua and the coarse land field
prototypes/generated/land_coarse_<map>_v<n>.lua (the 256-term checkpoint of the same fit).

A tent at level k (spacing h = 2^k reference pixels) and node (i, j) contributes
c * T(u / h - i) * T(v / h - j) with T(t) = max(0, 1 - |t|), in the fit frame where pixel centres sit
at integer u, v. Factors are shared local expressions per column and row, terms are grouped by row
factor, and every sum is a balanced parenthesis tree (S1-fit; S9). Coefficients print as float32
%.9g.

The generated files are name-free data: the factors read the locals U and V, which
prototypes/expressions/coast.lua binds to the map's coordinate chain from config.lua, so no
generated file spells an Earth name (T16 name scan). Every line stays within 120 columns: long
strings continue with Lua 5.2's \\z escape, as vanilla's noise-programs.lua does (luacheck 1.2.0
and luaparser 4.2.0 both read it), never with a '..' chain. Emission is reproducible: the same
checkpoint gives byte-identical Lua.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

EMITTER_VERSION = 1
MAX_COLUMNS = 120
FITS = REPO / "data-src" / "fits"
GENERATED = REPO / "terra-nauvis" / "prototypes" / "generated"
ISLAND_MIN_PX = 65          # T1-e: every reference land component of 65 px or more
REFIT_TARGET_PX = 1.0       # the one-sided fit's margin: a patched pixel centre reads +1 px


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fit_spec(map_key):
    """The map's fit manifest input (data-src/fits/<map>/fit.json): which checkpoint each body uses."""
    spec = json.loads((FITS / map_key / "fit.json").read_text(encoding="utf-8"))
    for body in ("geo", "land_coarse"):
        if body not in spec.get("bodies", {}):
            raise SystemExit(f"RESULT fail {map_key}/fit.json lacks the {body} body")
    return spec


# ------------------------------------------------------------------------------------------------ model

def load_model(path):
    """(meta, per-level sorted flat node indices, coefficients) of an S1-fit tents checkpoint."""
    import numpy as np
    z = np.load(path)
    meta = json.loads(str(z["meta"]))
    if meta.get("family") != "mr" or meta.get("step") != 1:
        raise SystemExit(f"RESULT fail {path}: not a step-1 multilevel tent model")
    idx = [z[f"idx{k}"].astype(np.int64) for k in range(meta["K"] + 1)]
    coef = z["coef"].astype(np.float64)
    if sum(len(a) for a in idx) != len(coef):
        raise SystemExit(f"RESULT fail {path}: {len(coef)} coefficients for {sum(len(a) for a in idx)} nodes")
    return meta, idx, coef


def save_model(path, meta, idx, coef):
    import numpy as np
    arrays = {f"idx{k}": np.asarray(a, np.int64) for k, a in enumerate(idx)}
    np.savez(path, meta=np.array(json.dumps(meta)), coef=np.asarray(coef, np.float64), **arrays)


def terms(meta, idx, coef):
    """(level k, node column i, node row j, coefficient) per active tent, level by level."""
    off = 0
    for k, a in enumerate(idx):
        nw = meta["shapes"][k][1]
        for flat, c in zip(a.tolist(), coef[off:off + len(a)].tolist()):
            j, i = divmod(int(flat), nw)
            yield k, i, j, c
        off += len(a)


def _prolong(c):
    import numpy as np
    a, b = c.shape
    t = np.empty((2 * a - 1, b), np.float32)
    t[0::2] = c
    t[1::2] = 0.5 * (c[:-1] + c[1:])
    f = np.empty((2 * a - 1, 2 * b - 1), np.float32)
    f[:, 0::2] = t
    f[:, 1::2] = 0.5 * (t[:, :-1] + t[:, 1:])
    return f


def pixel_values(meta, idx, coef):
    """The model at every reference pixel centre (H x W float32): the level grids summed by 2x
    prolongations (S1-fit's bases.MR), exact for tents at the nodes of the finest grid."""
    import numpy as np
    K = meta["K"]
    offs = [0]
    for a in idx:
        offs.append(offs[-1] + len(a))
    G = np.zeros(meta["shapes"][K], np.float32)
    G.ravel()[idx[K]] += coef[offs[K]:offs[K + 1]].astype(np.float32)
    for k in range(K - 1, -1, -1):
        G = _prolong(G)
        if len(idx[k]):
            G.ravel()[idx[k]] += coef[offs[k]:offs[k + 1]].astype(np.float32)
    return np.ascontiguousarray(G[:meta["H"], :meta["W"]])


# ------------------------------------------------------------------------------------------------ emission

def g9(v):
    return f"{float(v):.9g}"


def bsum(items):
    items = list(items)
    if not items:
        return "0"
    while len(items) > 1:
        nxt = [f"({items[i]} + {items[i + 1]})" for i in range(0, len(items) - 1, 2)]
        if len(items) % 2:
            nxt.append(items[-1])
        items = nxt
    return items[0]


def tent_body(meta, idx, coef):
    """(locals, expression, stats): name-free factors on U and V, row sums, the sum of rows."""
    import numpy as np
    locs, groups, n = {}, defaultdict(list), 0
    for k, i, j, c in terms(meta, idx, coef):
        if c == 0:
            continue
        n += 1
        h = 1 << k
        un, vn = f"u{k}_{i}", f"v{k}_{j}"
        if un not in locs:
            locs[un] = f"max(0, 1 - abs(U - {i}))" if h == 1 else f"max(0, 1 - abs(U * {g9(1.0 / h)} - {i}))"
        if vn not in locs:
            locs[vn] = f"max(0, 1 - abs(V - {j}))" if h == 1 else f"max(0, 1 - abs(V * {g9(1.0 / h)} - {j}))"
        groups[(k, j)].append(f"{float(np.float32(c)):.9g} * {un}")
    rows = []
    for (k, j), items in sorted(groups.items()):
        rn = f"r{k}_{j}"
        locs[rn] = bsum(items)
        rows.append(f"v{k}_{j} * {rn}")
    factors = sum(1 for name in locs if name[0] in "uv")
    return locs, bsum(rows), {"terms": n, "factors": factors, "row_groups": len(groups)}


def lua_string_lines(text, first_prefix, last_suffix, indent="  "):
    """A Lua double-quoted literal of `text` (no quote or backslash in it) as physical lines of at
    most MAX_COLUMNS: `first_prefix` + '"' starts the first line, '"' + `last_suffix` ends the last,
    and each break is a backslash-z escape, which skips the newline and the next line's indent. A
    break falls only after a space, so the skipped whitespace is never part of the text."""
    if '"' in text or "\\" in text:
        raise ValueError("the emitter writes expression text without quotes or backslashes")
    lines, cur, pos = [], first_prefix + '"', 0
    while True:
        room = MAX_COLUMNS - len(cur) - 2          # the line ends in '\z'
        rest = text[pos:]
        if len(cur) + len(rest) + 1 + len(last_suffix) <= MAX_COLUMNS:
            lines.append(cur + rest + '"' + last_suffix)
            return lines
        cut = rest.rfind(" ", 0, max(room, 1))
        while cut >= 0 and cut + 1 < len(rest) and rest[cut + 1] == " ":
            cut = rest.rfind(" ", 0, cut)
        if cut < 0:
            raise ValueError(f"no break point within {MAX_COLUMNS} columns in {rest[:60]!r}")
        lines.append(cur + rest[:cut + 1] + "\\z")
        pos += cut + 1
        cur = indent


def render_lua(locs, expr, stats, header):
    out = [f"-- {line}" for line in header]
    out.append("local L = {}")
    for name, body in locs.items():
        out += lua_string_lines(body, f'L["{name}"] = ', "")
    out += lua_string_lines(expr, "return {locals = L, expression = ",
                            f", terms = {stats['terms']}, factors = {stats['factors']}, "
                            f"row_groups = {stats['row_groups']}}}")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise ValueError(f"line of {len(line)} columns: {line[:60]!r}")
    return "\n".join(out) + "\n"


def emit_body(map_key, body, spec):
    """(file name, Lua text, record) of one body of the map's fit."""
    b = spec["bodies"][body]
    model = FITS / map_key / b["checkpoint"]
    meta, idx, coef = load_model(model)
    locs, expr, stats = tent_body(meta, idx, coef)
    digest = sha256_file(model)
    rel = model.relative_to(REPO).as_posix()
    header = [f"Generated by tools/build_geo.py (emitter {EMITTER_VERSION}) from {rel}",
              f"(sha256 {digest}).",
              f"{b['note']}: {stats['terms']} tents, {stats['factors']} factors, {stats['row_groups']} row groups.",
              "Name-free data: coast.lua binds the locals U and V to the map's coordinate chain.",
              "Never edit by hand: rerun the tool (plan hard rule 9)."]
    text = render_lua(locs, expr, stats, header)
    return b["file"], text, dict(stats, checkpoint=rel, checkpoint_sha256=digest)


def emit(map_key, out_dir=GENERATED, manifest=True):
    spec = fit_spec(map_key)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = {"format": "tn-geo-manifest/1", "tool": "tools/build_geo.py", "emitter_version": EMITTER_VERSION,
           "map": map_key, "bodies": {}}
    for body in ("geo", "land_coarse"):
        name, text, r = emit_body(map_key, body, spec)
        p = out_dir / name
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        r["file"] = f"terra-nauvis/prototypes/generated/{name}"
        r["sha256"] = sha256_file(p)
        r["bytes"] = p.stat().st_size
        rec["bodies"][body] = r
    if manifest:
        mp = FITS / map_key / "manifest.json"
        mp.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rec


def check(map_key):
    """T16: emission twice from the committed checkpoints, each byte-identical to the committed file."""
    spec = fit_spec(map_key)
    fails = []
    with tempfile.TemporaryDirectory(prefix="tn-geo-") as td:
        runs = []
        for n in range(2):
            d = Path(td) / f"run{n}"
            emit(map_key, d, manifest=False)
            runs.append(d)
        for body in ("geo", "land_coarse"):
            name = spec["bodies"][body]["file"]
            committed = GENERATED / name
            a, b = (runs[0] / name).read_bytes(), (runs[1] / name).read_bytes()
            if a != b:
                fails.append(f"{name}: two emissions differ")
            if not committed.exists():
                fails.append(f"{name}: no committed file")
            elif committed.read_bytes() != a:
                fails.append(f"{name}: the committed file differs from a fresh emission (rerun build_geo.py emit)")
    return fails


# ------------------------------------------------------------------------------------------------ islands

def island_report(values, ref, thin, conn):
    """Reference land components of ISLAND_MIN_PX or more and whether each is present (at least half
    its pixels land), on scored pixels (thin water is never land in the reference)."""
    import numpy as np
    import t1_metrics as t1
    cand = (values > 0) & ~thin
    R = t1.flat_runs(ref, conn)
    nc = R["n"]
    length = R["e"] - R["s"] + 1
    area = np.bincount(R["comp"], weights=length, minlength=nc).astype(np.int64)
    candc = np.bincount(R["comp"], weights=t1.per_run_counts(cand, R["fs"], R["fe"]), minlength=nc)
    big = np.nonzero(area >= ISLAND_MIN_PX)[0]
    missing = [int(c) for c in big if 2 * candc[c] < area[c]]
    return R, area, big, missing


def refit_islands(map_key, src_name, dst_name):
    """The local refit (FEAS-16): level-0 tents over every pixel of each missing component of
    ISLAND_MIN_PX or more (4- and 8-connected) whose value is below REFIT_TARGET_PX, each raising
    that pixel centre to the target and leaving every other pixel centre unchanged."""
    import numpy as np
    import earthgeo as eg
    mref = eg.MapRef(map_key)
    ref, thin = mref.land, mref.thin
    src = FITS / map_key / src_name
    meta, idx, coef = load_model(src)
    vals = pixel_values(meta, idx, coef)
    patch = {}
    report = {}
    for conn in (4, 8):
        R, area, big, missing = island_report(vals, ref, thin, conn)
        report[f"conn{conn}"] = {"components_65_plus": int(len(big)), "missing_before": len(missing)}
        for c in missing:
            for r, s, e in zip(R["rows"][R["comp"] == c].tolist(), R["s"][R["comp"] == c].tolist(),
                               R["e"][R["comp"] == c].tolist()):
                for col in range(s, e + 1):
                    if vals[r, col] < REFIT_TARGET_PX:
                        patch[(r, col)] = REFIT_TARGET_PX - float(vals[r, col])
    nw = meta["shapes"][0][1]
    lvl0 = {int(f): n for n, f in enumerate(idx[0].tolist())}
    add_flat, add_coef = [], []
    coef = coef.copy()
    for (r, col), delta in sorted(patch.items()):
        flat = r * nw + col
        if flat in lvl0:
            coef[lvl0[flat]] += delta
        else:
            add_flat.append(flat)
            add_coef.append(delta)
    merged = np.concatenate([idx[0], np.asarray(add_flat, np.int64)])
    order = np.argsort(merged, kind="stable")
    c0 = np.concatenate([coef[:len(idx[0])], np.asarray(add_coef, np.float64)])[order]
    idx = [merged[order]] + idx[1:]
    coef = np.concatenate([c0, coef[len(merged) - len(add_flat):]])
    meta = dict(meta, terms=int(sum(len(a) for a in idx)),
                refit={"from": src_name, "kind": "level-0 tents over missing land components of "
                       f"{ISLAND_MIN_PX} px or more (T1-e)", "target_px": REFIT_TARGET_PX,
                       "pixels_patched": len(patch), "terms_added": len(add_flat)})
    after = pixel_values(meta, idx, coef)
    for conn in (4, 8):
        _, _, _, missing = island_report(after, ref, thin, conn)
        report[f"conn{conn}"]["missing_after"] = len(missing)
    changed = np.argwhere(after != vals)
    report["pixel_centres_changed"] = int(len(changed))
    report["pixel_centres_patched"] = len(patch)
    dst = FITS / map_key / dst_name
    save_model(dst, meta, idx, coef)
    report["checkpoint"] = dst.relative_to(REPO).as_posix()
    report["sha256"] = sha256_file(dst)
    report["terms"] = meta["terms"]
    return report


def offline(map_key):
    """Offline T1 of each body's checkpoint at reference pixel centres (t1_metrics' evaluate)."""
    import numpy as np
    import earthgeo as eg
    import t1_metrics as t1
    spec = fit_spec(map_key)
    mref = eg.MapRef(map_key)
    out = {}
    for body, b in spec["bodies"].items():
        meta, idx, coef = load_model(FITS / map_key / b["checkpoint"])
        cand = pixel_values(meta, idx, coef) > 0
        cov = np.ones_like(cand)
        res, _ = t1.crop_and_evaluate(mref, cand, cov, t1.DEFAULT_CAP, 4)
        cd = res["coast_deviation_px"]
        out[body] = {"checkpoint": b["checkpoint"], "agreement": res["pixel_agreement"], "p99_px": cd["p99"],
                     "max_px": cd["max"], "islands_65_plus": res["islands"]["buckets"]["65+"]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("emit", "check", "offline"):
        p = sub.add_parser(name)
        p.add_argument("--map", required=True)
    p = sub.add_parser("refit-islands")
    p.add_argument("--map", required=True)
    p.add_argument("--src", default="model-8192.npz")
    p.add_argument("--dst", default="model-8192-t1e.npz")
    a = ap.parse_args(argv)
    if a.cmd == "emit":
        rec = emit(a.map)
        print(json.dumps(rec, indent=1))
        print(f"RESULT ok emitted {[b['file'] for b in rec['bodies'].values()]}")
        return 0
    if a.cmd == "check":
        fails = check(a.map)
        for f in fails:
            print(f"FAIL {f}")
        print(f"RESULT {'ok' if not fails else 'fail'} checks=2 failed={len(fails)} "
              f"two emissions byte-identical to the committed generated files")
        return 0 if not fails else 1
    if a.cmd == "refit-islands":
        rep = refit_islands(a.map, a.src, a.dst)
        print(json.dumps(rep, indent=1))
        print(f"RESULT ok refit {rep['checkpoint']} terms={rep['terms']}")
        return 0
    rep = offline(a.map)
    print(json.dumps(rep, indent=1))
    print("RESULT ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
