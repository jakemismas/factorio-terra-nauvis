#!/usr/bin/env python3
"""Coast fit emitter (ARCHITECTURE.md, "Build-time data flow" step 2; milestone europe-coast).

  python tools/build_geo.py emit --map europe          write the generated Lua and the manifest
  python tools/build_geo.py check --map europe         re-emit twice into a scratch folder and compare
                                                       byte for byte with the committed files (T16)
  python tools/build_geo.py refit-islands --map europe the recorded local refit: model-8192 plus
                                                       level-0 tents over every reference land
                                                       component of 65 px or more it misses (T1-e)
  python tools/build_geo.py offline --map europe       offline T1 of the committed checkpoints
  python tools/build_geo.py fit --map atlantic         the native-resolution fit itself, resumable: every
                                                       growth step's checkpoint and the fit state go to
                                                       a work folder outside the repo (--work), and a
                                                       rerun resumes after its newest completed step
  python tools/build_geo.py curve --map atlantic       offline T1 (t1_metrics) of the fit's checkpoints
                                                       into the work folder's curve.json
  python tools/build_geo.py adopt --map atlantic       copy the smallest checkpoint at or above T1's
                                                       bar, the 256-term one and the curve into
                                                       data-src/fits/<map>/ and write fit.json

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
import math
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


# ------------------------------------------------------------------------------------------------ fit
#
# The fit itself, ported from S1-fit (spikes/S1-fit/fit.py, bases.py and common.py at planning commit
# 45c86d706c21) for the maps the spikes never fitted at native resolution (milestone olde-world-atlantic,
# design review experiments 4 and 5). The arithmetic is S1-fit's, operation for operation, so the port
# reproduces Europe's recorded curve (data-src/fits/europe/curve.json); what changed is memory and
# resumability only: masks stay boolean or int8 (products with 0, 1 and -1 are exact in float32),
# the candidate scores of a level are taken in chunks (the same top terms), the adjoint reuses the
# forward grid in place, and every growth step leaves its checkpoint, the fit state and the model
# field in the work folder, so a halt resumes the fit instead of restarting it (design section 9).

FIT_FORMAT = "tn-fit-state/1"
CURVE_FORMAT = "tn-fit-curve/1"
FIT_PARAMS = {"family": "mr", "mode": "onesided", "step": 1, "D": 4.0, "K": 10, "lam": 1e-4, "margin": 1.0,
              "growth": 1.25, "newton": 4, "maxit": 150, "nmin": 64, "tol": 2e-3}
FIT_BAR = 0.991             # T1-a (design section 6.1): the smallest checkpoint at or above it ships
COARSE_TERMS = 256          # the coarse land field is the fit's 256-term checkpoint
TOP_CHUNK = 1 << 22         # candidate scoring chunk (float64 scores of 4 M nodes at a time)
# S1-fit's Tile complexity model (spikes/S1-fit/README.md, --cost): per term, per shared factor, per
# row group, at zero terms. An estimate only; the gate's T15a rows measure the real programs.
TILE_COST = (5.02, 0.2, 18.45, 8777.0)


def default_work(map_key):
    import earthgeo as eg
    return eg.WS / "previews" / "earth-build" / "fits" / map_key


def fit_schedule(nmin, nmax, growth):
    """S1-fit's term counts: every power of two from nmin, plus nmin * growth^i rounded."""
    checkpoints, n = [], nmin
    while n <= nmax:
        checkpoints.append(n)
        n *= 2
    steps = set(checkpoints)
    x = float(nmin)
    while x < nmax:
        steps.add(int(round(x)))
        x *= growth
    return sorted(s for s in steps if nmin <= s <= nmax), checkpoints


def _column_gaps(mask, strip=1024):
    """uint16: rows to the nearest True pixel in the same column (0 on True, 65535 if none)."""
    import numpy as np
    H, W = mask.shape
    out = np.empty((H, W), np.uint16)
    rows = np.arange(H, dtype=np.int32)[:, None]
    for c0 in range(0, W, strip):
        sub = mask[:, c0:c0 + strip]
        above = np.where(sub, rows, -(1 << 20)).astype(np.int32)
        np.maximum.accumulate(above, axis=0, out=above)
        below = np.where(sub, rows, 1 << 21).astype(np.int32)
        below = np.minimum.accumulate(below[::-1], axis=0)[::-1]
        g = np.minimum(rows - above, below - rows)
        out[:, c0:c0 + strip] = np.minimum(g, 65535).astype(np.uint16)
    return out


def _capped_dist_rows(gap, rows, cols, cap):
    """Distance to the class of `gap` at rows x cols, exact up to `cap`, else at least cap."""
    import numpy as np
    W = gap.shape[1]
    R = int(np.ceil(cap)) + 1
    best = np.full((len(rows), len(cols)), np.inf, np.float32)
    sub = gap[rows]
    for dc in range(-R, R + 1):
        c2 = cols + dc
        ok = (c2 >= 0) & (c2 < W)
        if not ok.any():
            continue
        g = sub[:, c2[ok]]
        v = g.astype(np.float32) - 0.5
        np.maximum(v, 0, out=v)
        v[g == 65535] = 1e9
        h = max(abs(dc) - 0.5, 0.0)
        cur = best[:, ok]
        np.minimum(cur, v * v + h * h, out=cur)
        best[:, ok] = cur
    return np.sqrt(best)


def saturated_sdf(land, D, chunk=256):
    """The fit target: signed distance (land positive) at pixel centres, D * tanh(sdf / D), float32."""
    import numpy as np
    H, W = land.shape
    gW = _column_gaps(~land)
    gL = _column_gaps(land)
    cols = np.arange(W)
    out = np.empty((H, W), np.float32)
    cap = 4.0 * D
    for k in range(0, H, chunk):
        rows = np.arange(k, min(H, k + chunk))
        dw = _capped_dist_rows(gW, rows, cols, cap)
        dl = _capped_dist_rows(gL, rows, cols, cap)
        lm = land[k:k + len(rows)]
        sdf = np.where(lm, np.minimum(dw, cap), -np.minimum(dl, cap))
        out[k:k + len(rows)] = D * np.tanh(sdf / D)
    return out


def _restrict(f):
    t = f[:, 0::2].copy()
    h = 0.5 * f[:, 1::2]
    t[:, :-1] += h
    t[:, 1:] += h
    c = t[0::2].copy()
    h = 0.5 * t[1::2]
    c[:-1] += h
    c[1:] += h
    return c


class TentBasis:
    """S1-fit's multilevel tents (bases.MR) on the reference grid itself, with the active set."""

    def __init__(self, H, W, K):
        import numpy as np
        self.H, self.W, self.K = H, W, K
        hK = 1 << K
        self.Ew = -(-(W - 1) // hK) * hK
        self.Eh = -(-(H - 1) // hK) * hK
        self.shape = [((self.Eh >> k) + 1, (self.Ew >> k) + 1) for k in range(K + 1)]
        self.s1 = np.array([float(((1 - np.abs(np.arange(-(h - 1), h)) / h) ** 2).sum())
                            for h in (1 << k for k in range(K + 1))])
        self.idx = [np.zeros(0, np.int64) for _ in range(K + 1)]

    def n(self):
        return sum(len(a) for a in self.idx)

    def offsets(self):
        o = [0]
        for a in self.idx:
            o.append(o[-1] + len(a))
        return o

    def add(self, level, flat, c):
        """Merge new nodes into their levels; the coefficients re-laid out, new ones 0."""
        import numpy as np
        offs = self.offsets()
        parts = []
        for k, a in enumerate(self.idx):
            ck = c[offs[k]:offs[k + 1]]
            add_k = flat[level == k]
            if len(add_k):
                merged = np.concatenate([a, add_k])
                order = np.argsort(merged, kind="stable")
                parts.append(np.concatenate([ck, np.zeros(len(add_k))])[order])
                self.idx[k] = merged[order]
            else:
                parts.append(ck)
        return np.concatenate(parts) if parts else np.zeros(0)

    def grid(self, c):
        """The model at every node of the finest grid, padding included (S1-fit's _grid0)."""
        import numpy as np
        offs = self.offsets()
        K = self.K
        G = np.zeros(self.shape[K], np.float32)
        G.ravel()[self.idx[K]] += c[offs[K]:offs[K + 1]].astype(np.float32)
        for k in range(K - 1, -1, -1):
            G = _prolong(G)
            if len(self.idx[k]):
                G.ravel()[self.idx[k]] += c[offs[k]:offs[k + 1]].astype(np.float32)
        return G

    def forward(self, c):
        import numpy as np
        return np.ascontiguousarray(self.grid(c)[:self.H, :self.W])

    def _chain(self, G):
        yield 0, G
        for k in range(1, self.K + 1):
            G = _restrict(G)
            yield k, G

    def _padded(self, R):
        import numpy as np
        G = np.zeros(self.shape[0], np.float32)
        G[:self.H, :self.W] = R
        return G

    def _adjoint_grid(self, G):
        import numpy as np
        return np.concatenate([g.ravel()[self.idx[k]].astype(np.float64) for k, g in self._chain(G)])

    def adjoint(self, R):
        """A^T R restricted to the active terms."""
        return self._adjoint_grid(self._padded(R))

    def aop_image(self, c, wmask):
        """A^T (wmask * A c): the forward grid weighted in place and its padding cleared, which is
        exactly S1-fit's adjoint of w * forward(c)."""
        G = self.grid(c)
        G[:self.H, :self.W] *= wmask
        G[self.H:, :] = 0
        G[:, self.W:] = 0
        return self._adjoint_grid(G)

    def precond(self):
        import numpy as np
        return np.concatenate([np.full(len(a), self.s1[k] ** 2) for k, a in enumerate(self.idx)])

    def _level_top(self, g, k, m):
        """Flat indices and scores of the m best inactive nodes of one level, chunk by chunk."""
        import numpy as np
        flat = g.ravel()
        act = self.idx[k]
        ci, cs = [], []
        for a in range(0, flat.size, TOP_CHUNK):
            b = min(flat.size, a + TOP_CHUNK)
            s = np.abs(flat[a:b]) / self.s1[k]
            lo, hi = np.searchsorted(act, [a, b])
            s[act[lo:hi] - a] = -1.0
            mm = min(m, s.size)
            top = np.argpartition(s, s.size - mm)[s.size - mm:]
            top = top[s[top] > 0]
            ci.append(top.astype(np.int64) + a)
            cs.append(s[top])
        ci, cs = np.concatenate(ci), np.concatenate(cs)
        if len(cs) > m:
            keep = np.argpartition(cs, len(cs) - m)[len(cs) - m:]
            ci, cs = ci[keep], cs[keep]
        return ci, cs

    def top_candidates(self, R, n):
        """The n inactive terms with the largest normalized |A^T R| (S1-fit's greedy group)."""
        import numpy as np
        lv, fl, sc = [], [], []
        for k, g in self._chain(self._padded(R)):
            top, s = self._level_top(g, k, n)
            lv.append(np.full(len(top), k))
            fl.append(top)
            sc.append(s)
        lv, fl, sc = np.concatenate(lv), np.concatenate(fl), np.concatenate(sc)
        if len(sc) > n:
            keep = np.argpartition(sc, len(sc) - n)[len(sc) - n:]
            lv, fl = lv[keep], fl[keep]
        return lv, fl

    def describe(self):
        import numpy as np
        d = {"levels": {}}
        for k, a in enumerate(self.idx):
            if len(a):
                nw = self.shape[k][1]
                d["levels"][str(1 << k)] = {"terms": int(len(a)), "cols": int(len(np.unique(a % nw))),
                                            "rows": int(len(np.unique(a // nw)))}
        d["factors"] = int(sum(v["cols"] + v["rows"] for v in d["levels"].values()))
        d["row_groups"] = int(sum(v["rows"] for v in d["levels"].values()))
        return d


def _pcg(B, c0, wmask, target, lam, tol, maxit):
    import numpy as np
    P = B.precond()
    M = P * (1.0 + lam)
    lamv = lam * P

    def aop(c):
        return B.aop_image(c, wmask) + lamv * c

    b = B.adjoint(wmask * target)
    bn = np.linalg.norm(b)
    x = c0.copy()
    if bn == 0:
        return x, 0
    r = b - aop(x)
    z = r / M
    p = z.copy()
    rz = r @ z
    it = 0
    for it in range(1, maxit + 1):
        Ap = aop(p)
        pAp = p @ Ap
        if pAp <= 0:
            break
        alpha = rz / pAp
        x += alpha * p
        r -= alpha * Ap
        if np.linalg.norm(r) < tol * bn:
            break
        z = r / M
        rz2 = r @ z
        p = z + (rz2 / rz) * p
        rz = rz2
    return x, it


def _hinge_obj(f, c, y, valid, m, lamv):
    import numpy as np
    v = np.maximum(0.0, m - y * f)
    return float((valid * v * v).sum(dtype=np.float64) + (lamv * c * c).sum())


def _newton(B, c, y, valid, m, lam, steps, tol, maxit, log, wgt=None):
    """wgt: the per-pixel weights of a region-weighted fit (0 on thin water), or None, where every
    valid pixel weighs 1 and the arithmetic is S1-fit's unchanged."""
    import numpy as np
    lamv = lam * B.precond()
    wv = valid if wgt is None else wgt
    f = B.forward(c)
    J = _hinge_obj(f, c, y, wv, m, lamv)
    iters = 0
    for s in range(steps):
        a = ((y * f) < m) & valid
        cn, it = _pcg(B, c, a if wgt is None else a * wgt, (y * m).astype(np.float32), lam, tol, maxit)
        iters += it
        fn = B.forward(cn)
        Jn = _hinge_obj(fn, cn, y, wv, m, lamv)
        if Jn > J:
            # f is linear in c, so a damped step is the same blend of both evaluations
            best = (Jn, fn, cn)
            for step in (0.5, 0.25, 0.125):
                ft = f + step * (fn - f)
                ct = c + step * (cn - c)
                Jt = _hinge_obj(ft, ct, y, wv, m, lamv)
                if Jt < best[0]:
                    best = (Jt, ft, ct)
                if Jt < J:
                    break
            Jn, fn, cn = best
            if Jn > J:
                break
        rel = (J - Jn) / max(J, 1e-12)
        c, f = cn, fn
        log(f"   newton {s + 1}: J {J:.1f} -> {Jn:.1f} (cg {it}, active px {int(a.sum())})")
        J = Jn
        if rel < 1e-3:
            break
    return c, f, J, iters


def _save_ckpt(path, map_key, B, c, H, W):
    import numpy as np
    meta = {"map": map_key, "family": FIT_PARAMS["family"], "mode": FIT_PARAMS["mode"], "step": 1,
            "K": B.K, "Hs": H, "Ws": W, "H": H, "W": W, "terms": int(B.n()), "D": FIT_PARAMS["D"],
            "Ew": B.Ew, "Eh": B.Eh, "shapes": [list(s) for s in B.shape], "tool": "tools/build_geo.py fit"}
    arrs = {f"idx{k}": a for k, a in enumerate(B.idx)}
    tmp = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(tmp, meta=json.dumps(meta), coef=np.asarray(c, np.float64), **arrs)
    tmp.replace(path)


def _write_json(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def tile_estimate(desc):
    a, b, g, z = TILE_COST
    terms = sum(v["terms"] for v in desc["levels"].values())
    return round(a * terms + b * desc["factors"] + g * desc["row_groups"] + z)


def region_box_px(mref, box):
    """(r0, r1, c0, c1): the reference pixels whose centres lie in a box of (lon0, lon1, lat0, lat1)
    degrees in the map's own frame (its georeference), clipped to the raster."""
    import math
    lon0, lon1, lat0, lat1 = (float(x) for x in box[:4])
    u0, v0 = mref.lonlat_to_uv(min(lon0, lon1), max(lat0, lat1))
    u1, v1 = mref.lonlat_to_uv(max(lon0, lon1), min(lat0, lat1))
    c0, c1 = max(0, math.ceil(u0 - 0.5)), min(mref.W, math.floor(u1 - 0.5) + 1)
    r0, r1 = max(0, math.ceil(v0 - 0.5)), min(mref.H, math.floor(v1 - 0.5) + 1)
    return r0, r1, c0, c1


def region_weights(mref, valid, regions):
    """The per-pixel weights of a region-weighted fit: 1 on every valid pixel, times the largest
    multiplier of the region boxes holding the pixel centre, and 0 on thin water."""
    import numpy as np
    mult = np.ones(valid.shape, np.float32)
    for r in regions:
        r0, r1, c0, c1 = region_box_px(mref, r)
        np.maximum(mult[r0:r1, c0:c1], np.float32(r[4]), out=mult[r0:r1, c0:c1])
    mult *= valid
    return mult


def parse_region(text):
    """'lon0,lon1,lat0,lat1,weight' (degrees in the map's frame; weight above 0)."""
    parts = [float(x) for x in text.split(",")]
    if len(parts) != 5 or parts[4] <= 0:
        raise argparse.ArgumentTypeError("a region is lon0,lon1,lat0,lat1,weight with weight above 0")
    return parts


def fit(map_key, work, nmax, stop_agreement, extra_steps, max_steps=None, through=8192, regions=None,
        start_from=None):
    """S1-fit's greedy fit at native resolution, resumable (see the section comment above).

    regions: optional boxes [lon0, lon1, lat0, lat1, weight] that multiply the fit's per-pixel
    weight (the hinge objective, the refits and the greedy scores), so the terms concentrate on
    those coasts. Off by default, which keeps S1-fit's arithmetic and the recorded fits unchanged;
    when on, the boxes join the fit's params, so a resume with other boxes is refused.

    start_from: optional checkpoint of the same reference (an earlier fit's growth step) whose terms
    and coefficients the growth continues from, instead of the least-squares start at nmin terms;
    its name, sha256 and terms join the params."""
    import time
    import numpy as np
    import earthgeo as eg
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    logf = open(work / "fit.log", "a", encoding="utf-8")

    def log(msg):
        line = f"[{map_key}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    P = dict(FIT_PARAMS)
    if regions:
        P["region_weights"] = [[float(x) for x in r] for r in regions]
    if start_from:
        start_from = Path(start_from)
        P["start_from"] = {"checkpoint": start_from.name, "sha256": sha256_file(start_from),
                           "terms": int(len(load_model(start_from)[2]))}
    t0 = time.time()
    mref = eg.MapRef(map_key)
    H, W = mref.H, mref.W
    inputs = {name: sha256_file(p) for name, p in (("land", mref.land_path), ("thin", mref.thin_path))}
    counts, pow2 = fit_schedule(P["nmin"], nmax, P["growth"])
    state_path = work / "fit-state.json"
    header = {"format": FIT_FORMAT, "tool": "tools/build_geo.py fit", "map": map_key, "params": P,
              "reference": [H, W], "inputs_sha256": inputs,
              "ported_from": "spikes/S1-fit fit.py, bases.py, common.py at planning commit 45c86d706c21"}
    state = None
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for key in ("format", "map", "params", "reference", "inputs_sha256"):
            if state.get(key) != header[key]:
                raise SystemExit(f"RESULT fail {state_path}: {key} differs from this run's; use a new --work")
    else:
        state = dict(header, points=[])
    land = mref.land
    thin = mref.thin
    filled = land | thin
    valid = ~thin
    n_valid = int(valid.sum())
    wgt = region_weights(mref, valid, regions) if regions else None
    wv = valid if wgt is None else wgt
    y = np.where(filled, np.int8(1), np.int8(-1))
    t = saturated_sdf(filled, P["D"])
    del filled, land, thin
    mref._land = mref._thin = None
    marg = (np.abs(t) * P["margin"]).astype(np.float32)
    log(f"reference {W}x{H}, valid px {n_valid}, target ready ({time.time() - t0:.1f} s, "
        f"peak {eg.peak_memory_mb()} MB)")
    B = TentBasis(H, W, P["K"])
    c = np.zeros(0)
    f = None
    done = 0
    if state["points"]:
        last = state["points"][-1]
        done = last["terms_target"]
        meta, idx, coef = load_model(work / last["checkpoint"])
        if [list(s) for s in meta["shapes"]] != [list(s) for s in B.shape]:
            raise SystemExit("RESULT fail the checkpoint's grid shapes differ from this reference's")
        B.idx = [np.asarray(a, np.int64) for a in idx]
        c = coef
        fpath = work / "resume-f.npy"
        rec = json.loads((work / "resume-f.json").read_text(encoding="utf-8")) if (work / "resume-f.json").exists() else {}
        if fpath.exists() and rec.get("terms_target") == done:
            f = np.load(fpath)
            log(f"resumed after {done} terms from {last['checkpoint']} with the stored model field")
        else:
            f = B.forward(c)
            log(f"resumed after {done} terms from {last['checkpoint']}; the model field recomputed")
        del t
        t = None
    elif start_from:
        meta, idx, coef = load_model(start_from)
        if [list(s) for s in meta["shapes"]] != [list(s) for s in B.shape]:
            raise SystemExit("RESULT fail the start checkpoint's grid shapes differ from this reference's")
        B.idx = [np.asarray(a, np.int64) for a in idx]
        c = coef
        done = int(len(coef))
        f = B.forward(c)
        log(f"starting after {done} terms from {start_from.name}")
        del t
        t = None
    first = done == 0
    reached = next((p["terms_target"] for p in state["points"] if p["sample_agreement"] >= stop_agreement), None)
    ran = 0
    for N in counts:
        if N <= done:
            continue
        if reached is not None and counts.index(N) > counts.index(reached) + extra_steps and N > through:
            log(f"stop rule met: agreement {stop_agreement} at {reached} terms plus {extra_steps} steps, "
                f"and through {through} terms")
            break
        if max_steps is not None and ran >= max_steps:
            log(f"stopping after {ran} steps this run (--max-steps)")
            break
        ts = time.time()
        if first:
            R = wv * t
        else:
            act_px = ((y * f) < marg) & valid
            R = (act_px if wgt is None else act_px * wgt) * (y * marg - f)
            del act_px
        lv, fl = B.top_candidates(R, N - B.n())
        del R
        c = B.add(lv, fl, c)
        cg_ls = 0
        if first:
            c, cg_ls = _pcg(B, c, wv, t, P["lam"], P["tol"], P["maxit"])
        f = None
        c, f, J, cg_h = _newton(B, c, y, valid, marg, P["lam"], P["newton"], P["tol"], P["maxit"], log, wgt)
        if first:
            t = None
            first = False
        tf = time.time() - ts
        agree = int((((f > 0) == (y > 0)) & valid).sum()) / n_valid
        name = f"model-{N}.npz"
        _save_ckpt(work / name, map_key, B, c, H, W)
        np.save(work / "resume-f.tmp.npy", f)
        (work / "resume-f.tmp.npy").replace(work / "resume-f.npy")
        _write_json(work / "resume-f.json", {"terms_target": N})
        desc = B.describe()
        pt = {"terms_target": N, "terms": int(B.n()), "checkpoint": name, "power_of_two": N in pow2,
              "sample_agreement": agree, "cg_ls": cg_ls, "cg_hinge": cg_h, "hinge_J": J,
              "fit_seconds": round(tf, 1), "peak_memory_mb": eg.peak_memory_mb(), "describe": desc,
              "tile_estimate": tile_estimate(desc)}
        state["points"].append(pt)
        _write_json(state_path, state)
        log(f"{B.n():>8} agreement {agree * 100:.4f}% (fit {tf:.0f} s, cg {cg_ls}+{cg_h}, "
            f"peak {pt['peak_memory_mb']} MB, Tile estimate {pt['tile_estimate']})")
        ran += 1
        if reached is None and agree >= stop_agreement:
            reached = N
    log(f"run done in {time.time() - t0:.0f} s; {len(state['points'])} steps recorded")
    logf.close()
    return state


def curve(map_key, work, min_sample, only=None):
    """Offline T1 (t1_metrics' definitions, as `offline`) of the fit's checkpoints: every power of
    two and every step whose sample agreement is at least min_sample, into <work>/curve.json."""
    import numpy as np
    import earthgeo as eg
    import t1_metrics as t1
    work = Path(work)
    state = json.loads((work / "fit-state.json").read_text(encoding="utf-8"))
    cpath = work / "curve.json"
    cur = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    done = {p["checkpoint"]: p for p in cur.get("points", [])}
    mref = eg.MapRef(map_key)
    out = []
    for p in state["points"]:
        want = (p["power_of_two"] or p["sample_agreement"] >= min_sample) if only is None \
            else p["terms_target"] in only
        rec = dict(p)
        ck = work / p["checkpoint"]
        digest = sha256_file(ck)
        prev = done.get(p["checkpoint"])
        if prev and prev.get("checkpoint_sha256") == digest and "t1" in prev:
            rec["t1"] = prev["t1"]
        elif want:
            meta, idx, coef = load_model(ck)
            cand = pixel_values(meta, idx, coef) > 0
            cov = np.ones_like(cand)
            res, _ = t1.crop_and_evaluate(mref, cand, cov, t1.DEFAULT_CAP, 4)
            del cand, cov
            cd = res["coast_deviation_px"]
            rec["t1"] = {"agreement": res["pixel_agreement"], "land_iou": res["land_iou"],
                         "coast_p99_px": cd["p99"], "coast_max_px": cd["max"], "connectivity": 4,
                         "islands": res["islands"]["buckets"], "evaluated_px": res["evaluated_px"],
                         "peak_memory_mb": eg.peak_memory_mb()}
            print(f"[{map_key}] {p['terms']:>8} T1 agreement {res['pixel_agreement']} p99 {cd['p99']} "
                  f"max {cd['max']}", flush=True)
        rec["checkpoint_sha256"] = digest
        out.append(rec)
    doc = {"format": CURVE_FORMAT, "map": map_key, "params": state["params"], "reference": state["reference"],
           "inputs_sha256": state["inputs_sha256"], "bar": FIT_BAR,
           "note": "agreement, p99 and max from t1_metrics over every reference pixel centre, thin water "
                   "excluded; sample_agreement is the fit's own count over the same pixels; tile_estimate "
                   "is S1-fit's complexity model (TILE_COST), never a measurement",
           "points": out}
    _write_json(cpath, doc)
    return doc


def adopt(map_key, work, version=1, budget=None):
    """Copy the shipped checkpoints (the smallest at or above FIT_BAR, and the 256-term one) and the
    curve into data-src/fits/<map>/ and write its fit.json; the emitter reads only that folder.

    budget: for a region-weighted fit grown from the folder's shipped fit (fit --region and
    --start-from), ship the largest evaluated step within this many terms instead of the bar rule's
    (every step is above the bar once the start is), and record the budget in fit.json. The coarse
    land field stays the folder's own (fit.json's land_coarse body and its checkpoint, byte for
    byte), and curve.json becomes the whole lineage: the folder's curve through the start
    checkpoint, each point marked stage "base", then the region steps, marked stage "region"."""
    import shutil
    work = Path(work)
    doc = json.loads((work / "curve.json").read_text(encoding="utf-8"))
    pts = [p for p in doc["points"] if "t1" in p]
    dst = FITS / map_key
    dst.mkdir(parents=True, exist_ok=True)
    import tnconfig
    label = tnconfig.load()["maps"][map_key]["display"]
    if budget is not None:
        params = doc["params"]
        start = params.get("start_from")
        if not params.get("region_weights") or not start:
            raise SystemExit(f"RESULT fail --budget adopts a region-weighted fit grown with --start-from; {work} is not")
        if not 0 < budget <= 8192:
            raise SystemExit("RESULT fail the budget is at most 8,192 terms (the Europe map's budget)")
        old = fit_spec(map_key)["bodies"]
        if sha256_file(dst / start["checkpoint"]) != start["sha256"]:
            raise SystemExit(f"RESULT fail the fit started from {start['checkpoint']} {start['sha256'][:12]}, which "
                             f"is not {dst / start['checkpoint']}")
        base = json.loads((dst / "curve.json").read_text(encoding="utf-8"))
        bpts = [dict(p, stage="base") for p in base["points"] if p["terms"] <= start["terms"]]
        if not any(p["checkpoint"] == old["land_coarse"]["checkpoint"] and "t1" in p for p in bpts):
            raise SystemExit(f"RESULT fail the folder's curve does not record {old['land_coarse']['checkpoint']}")
        within = [p for p in pts if p["terms"] <= budget]
        if not within:
            raise SystemExit(f"RESULT fail no evaluated step of {work} lies within {budget} terms")
        ship = max(within, key=lambda p: p["terms"])
        shutil.copyfile(work / ship["checkpoint"], dst / ship["checkpoint"])
        doc = dict(doc, base_params=base["params"], base_inputs_sha256=base["inputs_sha256"],
                   points=bpts + [dict(p, stage="region") for p in doc["points"]])
        doc["note"] = (doc["note"] + "; stage base: the folder's earlier fit through the start checkpoint "
                       "(base_params), stage region: the region-weighted growth from it (params)")
        coarse = next(p for p in bpts if p["checkpoint"] == old["land_coarse"]["checkpoint"])
        geo = {"checkpoint": ship["checkpoint"], "file": f"geo_{map_key}_v{version}.lua",
               "note": f"{label}'s coast fit, region weighted", "budget_terms": int(budget)}
        coarse_body = old["land_coarse"]
    else:
        ship = next((p for p in sorted(pts, key=lambda p: p["terms"]) if p["t1"]["agreement"] >= FIT_BAR), None)
        if ship is None:
            raise SystemExit(f"RESULT fail no evaluated checkpoint of {map_key} reaches {FIT_BAR}")
        coarse = next((p for p in pts if p["terms_target"] == COARSE_TERMS), None)
        if coarse is None:
            raise SystemExit(f"RESULT fail the {COARSE_TERMS}-term checkpoint of {map_key} is not evaluated")
        for p in (ship, coarse):
            shutil.copyfile(work / p["checkpoint"], dst / p["checkpoint"])
        geo = {"checkpoint": ship["checkpoint"], "file": f"geo_{map_key}_v{version}.lua",
               "note": f"{label}'s coast fit, the smallest checkpoint at or above {FIT_BAR}"}
        coarse_body = {"checkpoint": coarse["checkpoint"], "file": f"land_coarse_{map_key}_v{version}.lua",
                       "note": f"{label}'s coarse land field, the {COARSE_TERMS}-tent checkpoint of the same fit"}
    _write_json(dst / "curve.json", doc)
    spec = {"format": "tn-fit/1", "map": map_key,
            "note": f"Which checkpoint each generated body of {label} is emitted from (tools/build_geo.py). "
                    "See PROVENANCE.md.",
            # each note heads its generated file, so it stays short (the file's 120-column rule)
            "bodies": {"geo": geo, "land_coarse": coarse_body}}
    _write_json(dst / "fit.json", spec)
    return {"geo": ship, "land_coarse": coarse}


# ------------------------------------------------------------------------------------------------ band fix
#
# Exact coastlines (milestone coast-band-fix; the design notes section 13; S12's method on the shipped bases;
# the S13-bandfix spike's rule). Per map that config.lua's bandfix.tables lists and per offered scale, the
# K+ table terra-nauvis/scripts/bandfix.lua reads (scripts/generated/bandfix_<map>_s<k>_v<n>.lua) and
# the pricing in data-src/bandfix/manifest-<map>.json.
#
# The rule, in the coordinate chain's frame (U2): tile offset i of pixel c at scale s samples the fit at
# u = c + (i - floor(s / 2)) / s, inside pixel c's square. Its band is the set of neighbour squares of
# the other class (thin water and the area outside the raster count as water) closer than half a pixel
# to that point (S12's closed rule: exactly half a pixel is outside the band). A K pixel is a scored
# pixel (not thin water) outside every waterway, canal, dam and basin footprint (grown by
# bandfix.mask_margin_tiles) holding a tile outside its band that the coast fit may misclassify: the
# game adds the lattice detail (|detail| <= coast.detail_amplitude_px * coast.detail_clamp, 0 at pixel
# centres) to the fit, which no offline model reproduces (S1-cloud), so a tile is possibly wrong unless
# the fit alone is right by more than that bound plus bandfix.float_margin_px. A map with a coast warp
# has no detail: it reads the fit up to warp_reach_px away, so a tile is possibly wrong while the other
# class lies within that many pixels (on top of bandfix.correction_tiles). K+ is K and its 8
# neighbours, whose classes the band needs. A K pixel whose band region holds no 2 x 2 block of tiles
# (an islet or a channel narrower than a pixel) is a fill pixel, written whole.
#
# The model is piecewise bilinear on the level-0 grid (a level-k tent is bilinear on every level-0 cell),
# so the fit at a sample point is the bilinear interpolation of the uncropped level-0 grid; left of
# column 0 and above row 0 only node 0 of each level reaches, and those strips are summed level by level.
# The pricing (S12's Table 1 measures) counts the tiles the band rule writes when the fit alone decides
# (detail 0), on the map's own chunk grid with the city offset 0; S12 left out the waterway masks and the
# fills, which the shipped-rule columns include.

BANDFIX_EMITTER = 1
BANDFIX_FORMAT = "tn-bandfix-manifest/1"
BANDFIX_GENERATED = REPO / "terra-nauvis" / "scripts" / "generated"
BANDFIX_DATA = REPO / "data-src" / "bandfix"
BANDFIX_PRICE_SCALES = (1, 3, 6)        # the scales the plan's T1 (offline, first) re-prices
TQ1B_MS_PER_WRITTEN_CHUNK = 0.34        # S12's only timing input (TQ1b, 24 LP), for the estimate column only
F32_SENSITIVE = 0.005                   # |fit| under this may change class in float32 (S12: drift <= 3.0e-3)
ROW_BAND = 128                          # pixel rows per vectorized band
BASIS_NOISE_MAX = 1.77                  # basis_noise's measured extreme (factorio-worldgen-noise)


def bandfix_cfg(cfg=None):
    import tnconfig
    cfg = cfg or tnconfig.load()
    B = cfg.get("bandfix")
    if not B:
        raise SystemExit("RESULT fail config.lua has no bandfix group")
    return cfg, B


def bandfix_digest(B):
    import tnconfig
    return tnconfig.bandfix_digest(B)


def bandfix_file(map_key, s, version):
    return f"bandfix_{map_key}_s{int(s)}_v{int(version)}.lua"


def ref_classes(mref):
    """int8 per reference pixel: 0 water, 1 land, 2 thin water (unscored; water for the band)."""
    import numpy as np
    cls = np.zeros((mref.H, mref.W), np.int8)
    cls[mref.land] = 1
    cls[mref.thin] = 2
    return cls


def sea_channels(map_key, mref, cls, steps):
    """bool per pixel: the thin water of the ocean class within `steps` 8-connected pixels of open water along thin
    water: straits, sounds and inlets narrower than three pixels, which the coast fit fills as land. A river drawn in
    the same class stops being one here; the rest of it stays thin water."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(mref.land_path.with_name(f"{map_key}-classes.png")).convert("RGB"))
    ocean = (rgb[..., 0] == 20) & (rgb[..., 1] == 40) & (rgb[..., 2] == 110)
    allowed = (cls == 2) & ocean
    return ndi.binary_dilation(cls == 0, structure=np.ones((3, 3), bool), iterations=int(steps),
                               mask=allowed | (cls == 0)) & allowed


def bandfix_classes(map_key, mref, B):
    """ref_classes as the K+ tables read it: thin water that belongs to the sea counts as water, so the handler
    opens it."""
    cls = ref_classes(mref)
    cls[sea_channels(map_key, mref, cls, B["channel_px"])] = 0
    return cls


def other_masks(cls, neighbours):
    """uint8 per pixel: bit b set where neighbour b (config order) is of the other class; thin water and
    the area outside the raster count as water."""
    import numpy as np
    H, W = cls.shape
    landish = np.zeros((H + 2, W + 2), bool)
    landish[1:-1, 1:-1] = cls == 1
    me = landish[1:-1, 1:-1]
    out = np.zeros((H, W), np.uint8)
    for b, (dc, dr) in enumerate(neighbours):
        nb = landish[1 + dr:1 + dr + H, 1 + dc:1 + dc + W]
        out |= ((nb != me).astype(np.uint8) << b)
    return out


def reach_lut(s, neighbours):
    """(s, s) uint8: bit b set where neighbour b's square lies closer than half a pixel to the sample point
    of tile offset (i, j) inside its pixel; exact integers in units of 1 / (2 s) px (S12's band_lut; the
    handler builds the same table)."""
    import numpy as np
    half = s // 2

    def g(d, k):
        d2 = 2 * (k - half)
        if d == 0:
            return 0
        if d == 1:
            return s - d2
        return d2 + s
    lut = np.zeros((s, s), np.uint8)
    for j in range(s):
        for i in range(s):
            m = 0
            for b, (dc, dr) in enumerate(neighbours):
                gx, gy = g(dc, i), g(dr, j)
                if gx * gx + gy * gy < s * s:
                    m |= 1 << b
            lut[j, i] = m
    return lut


def thin_lut(s, reach):
    """bool[256]: True where the band region of a pixel with that other-class mask holds no 2 x 2 block of
    tiles, so the band rule alone could draw a strip one tile wide there (a fill pixel)."""
    import numpy as np
    out = np.zeros(256, bool)
    for m in range(256):
        R = (reach & m) == 0
        if s < 2:
            out[m] = True
            continue
        block = R[:-1, :-1] & R[:-1, 1:] & R[1:, :-1] & R[1:, 1:]
        out[m] = not bool(block.any())
    return out


def level0_grid(meta, idx, coef):
    """The model at every level-0 node, uncropped ((Eh + 1) x (Ew + 1) float32), by 2x prolongations."""
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
    return G


def edge_lines(meta, idx, coef):
    """Per level: the coefficients of node column 0 and node row 0 (float64), all a point left of
    column 0 or above row 0 reads."""
    import numpy as np
    out = []
    off = 0
    for k, a in enumerate(idx):
        nh, nw = meta["shapes"][k]
        c = coef[off:off + len(a)]
        off += len(a)
        col0, row0 = np.zeros(nh), np.zeros(nw)
        j, i = np.divmod(a, nw)
        col0[j[i == 0]] = c[i == 0]
        row0[i[j == 0]] = c[j == 0]
        out.append((col0, row0))
    return out


def _interp1(arr, x):
    import numpy as np
    x = np.asarray(x, float)
    i0 = np.floor(x).astype(np.int64)
    t = x - i0
    n = len(arr)
    a = np.where((i0 >= 0) & (i0 < n), arr[np.clip(i0, 0, n - 1)], 0.0)
    b = np.where((i0 + 1 >= 0) & (i0 + 1 < n), arr[np.clip(i0 + 1, 0, n - 1)], 0.0)
    return (1 - t) * a + t * b


def edge_values(lines, u, v):
    """The model exactly at points with u < 0 or v < 0 (each level's node 0 alone reaches there)."""
    import numpy as np
    u, v = np.asarray(u, float), np.asarray(v, float)
    out = np.zeros(np.broadcast(u, v).shape)
    for k, (col0, row0) in enumerate(lines):
        h = float(1 << k)
        wu = np.where(u < 0, 1 + u / h, 0.0)
        wv = np.where(v < 0, 1 + v / h, 0.0)
        left = (u < 0) & (v >= 0)
        top = (v < 0) & (u >= 0)
        corner = (u < 0) & (v < 0)
        out = out + np.where(left, wu * _interp1(col0, v / h), 0.0)
        out = out + np.where(top, wv * _interp1(row0, u / h), 0.0)
        out = out + np.where(corner, wu * wv * col0[0], 0.0)
    return out


def fit_band(Gp, lines, s, i, j, r0, n, W):
    """The fit (float64, n x W) at tile offset (i, j) of pixel rows r0 .. r0 + n - 1, every column. Gp is
    the level-0 grid padded by one zero row and column at the top and left."""
    import numpy as np
    half = s // 2
    du, dv = (i - half) / s, (j - half) / s
    ca = 0 if du >= 0 else -1
    ra = 0 if dv >= 0 else -1
    wu = du if du >= 0 else 1 + du
    wv = dv if dv >= 0 else 1 + dv
    rs, cs = r0 + ra + 1, ca + 1
    g00 = Gp[rs:rs + n, cs:cs + W].astype(np.float64)
    g01 = Gp[rs:rs + n, cs + 1:cs + 1 + W].astype(np.float64)
    g10 = Gp[rs + 1:rs + 1 + n, cs:cs + W].astype(np.float64)
    g11 = Gp[rs + 1:rs + 1 + n, cs + 1:cs + 1 + W].astype(np.float64)
    f = (1 - wv) * ((1 - wu) * g00 + wu * g01) + wv * ((1 - wu) * g10 + wu * g11)
    if du < 0:
        rows = np.arange(r0, r0 + n, dtype=float) + dv
        f[:, 0] = edge_values(lines, np.full(n, du), rows)
    if dv < 0 and r0 == 0:
        cols = np.arange(W, dtype=float) + du
        f[0, :] = edge_values(lines, cols, np.full(W, dv))
    return f


def waterway_footprint(cfg, mref, map_key, s, margin_tiles):
    """bool per pixel: within (half-width + margin) tiles of any waterway, canal or dam centreline, or of a
    turning basin, at scale s, pixel by pixel conservatively (a pixel's sample points lie within half a
    diagonal of its centre), from the committed waterway manifest (both canal states)."""
    import math
    import numpy as np
    import build_waterways as bw
    mp = bw.DATA / f"manifest-{map_key}.json"
    mask = np.zeros((mref.H, mref.W), bool)
    if not mp.exists():
        return mask, None
    M = json.loads(mp.read_text(encoding="utf-8"))
    rec = (M.get("scales") or {}).get(str(int(s)))
    if rec is None:
        return mask, sha256_file(mp)
    geo = bw.MapGeo(cfg, map_key)
    ox, oy = geo.offset(s)
    reach = math.sqrt(2) / 2
    for f in rec["features"]:
        P = (np.asarray(f["polyline_geo"], float) - [ox, oy]) / s - 0.5
        bw.band_into(mask, P, (f["reach_tiles"] + margin_tiles) / s + reach)
    half = bw.ww_cfg(cfg)["basin_tiles"] / 2 + bw.warp_reach(bw.ww_cfg(cfg), s)
    for b in rec.get("basins") or []:
        cx, cy = (b["centre"][0] - ox) / s - 0.5, (b["centre"][1] - oy) / s - 0.5
        h = (half + margin_tiles) / s + reach
        c0, c1 = max(int(math.floor(cx - h)), 0), min(int(math.ceil(cx + h)), mref.W - 1)
        r0, r1 = max(int(math.floor(cy - h)), 0), min(int(math.ceil(cy + h)), mref.H - 1)
        if c1 >= c0 and r1 >= r0:
            mask[r0:r1 + 1, c0:c1 + 1] = True
    # the river ponds the entry fills with land (build_waterways.py river_ponds): the handler must not dig
    # them back out of the reference
    for p in rec.get("ponds") or []:
        cx, cy = (p["centre"][0] - ox) / s - 0.5, (p["centre"][1] - oy) / s - 0.5
        h = (p["radius"] + margin_tiles) / s + reach
        c0, c1 = max(int(math.floor(cx - h)), 0), min(int(math.ceil(cx + h)), mref.W - 1)
        r0, r1 = max(int(math.floor(cy - h)), 0), min(int(math.ceil(cy + h)), mref.H - 1)
        if c1 >= c0 and r1 >= r0:
            mask[r0:r1 + 1, c0:c1 + 1] = True
    return mask, sha256_file(mp)


def chunk_axis(n_px, radius, s, offset, chunk):
    """(per pixel index, the chunk index of its tile at `offset`, from 0; the chunk count) on one axis of
    the map's own chunk grid at scale s (city offset 0: geo tiles are world tiles)."""
    import numpy as np
    first = (-radius * s) // chunk
    last = ((n_px - radius) * s - 1) // chunk
    t = s * (np.arange(n_px, dtype=np.int64) - radius) + offset
    return t // chunk - first, int(last - first + 1)


def dilate_tiles(A, k):
    """bool array grown by k tiles in Chebyshev distance (separable: rows, then columns; each axis doubles
    its reach over a padded copy, so a pass costs log k)."""
    import numpy as np
    if k <= 0:
        return A.copy()
    P = np.pad(A, k)
    H, W = P.shape
    for axis in (1, 0):
        reach = 0
        while reach < k:
            d = min(2 * reach + 1, k - reach)
            out = P.copy()
            if axis == 1:
                out[:, d:] |= P[:, :W - d]
                out[:, :W - d] |= P[:, d:]
            else:
                out[d:, :] |= P[:H - d, :]
                out[:H - d, :] |= P[d:, :]
            P = out
            reach += d
    return P[k:-k, k:-k]


def warp_reach_px(cfg, map_key):
    """The farthest a map's coast warp can move a sample point along one axis, in reference px (0 for a map
    with no warped geography): the sum of the larger axis's amplitudes at basis noise's extreme."""
    W = (cfg.get("coast") or {}).get("warp") or {}
    ids = {v["geo_id"] for v in cfg["geography"][map_key]["versions"]}
    if not ids & set(W.get("geographies") or []):
        return 0.0
    return BASIS_NOISE_MAX * max(sum(abs(float(o["amplitude_px"])) for o in W[axis]) for axis in ("u", "v"))


def bandfix_pass1(cfg, B, mref, cls, om, Gp, lines, s, mask, scored, L, margin, warp_px=0.0):
    """One scale, first pass, on the tile grid of a band of pixel rows at a time: the possibly-wrong pixels
    (K without the masks: a scored pixel holding a tile outside its band whose class the fit and the
    lattice detail may get wrong, or that the game's water correction may turn, a tile of the other
    possible class lying within bandfix.correction_tiles) and S12's pricing counts on the map's own chunk
    grid (the band rule's writes with the fit alone deciding, every scored pixel)."""
    import numpy as np
    H, W = cls.shape
    reach = reach_lut(s, [tuple(x) for x in B["neighbours"]])
    chunk = int(B["chunk_tiles"])
    corr = int(B["correction_tiles"]) + math.ceil(warp_px * s)
    halo = -(-corr // s)
    K = np.zeros((H, W), bool)
    rowc = [chunk_axis(H, mref.hr, s, j, chunk) for j in range(s)]
    colc = [chunk_axis(W, mref.wr, s, i, chunk) for i in range(s)]
    ncx, ncy = colc[0][1], rowc[0][1]
    nchunks = ncx * ncy
    s12 = np.zeros(nchunks, np.int64)
    w2l = np.zeros(nchunks, np.int64)
    sens = 0
    rows_per = max(4, min(ROW_BAND, (1 << 22) // (s * s * W)))
    for r0 in range(0, H, rows_per):
        n = min(rows_per, H - r0)
        ra, rb = max(0, r0 - halo), min(H, r0 + n + halo)
        m_ = rb - ra
        F = np.empty((m_ * s, W * s), np.float32)
        OUT = np.empty((m_ * s, W * s), bool)
        own = slice(r0 - ra, r0 - ra + n)
        sl = slice(r0, r0 + n)
        sc, Lb = scored[sl], L[sl]
        for j in range(s):
            crow = rowc[j][0][sl][:, None] * ncx
            for i in range(s):
                f = fit_band(Gp, lines, s, i, j, ra, m_, W)
                F[j::s, i::s] = f
                out = (om[ra:rb] & reach[j, i]) == 0
                OUT[j::s, i::s] = out
                fo, oo = f[own], out[own]
                wr_ = sc & oo & ((fo > 0) != Lb)
                flat = crow + colc[i][0][None, :]
                s12 += np.bincount(flat[wr_], minlength=nchunks)
                w2l += np.bincount(flat[wr_ & Lb], minlength=nchunks)
                sens += int((sc & oo & (np.abs(fo) < F32_SENSITIVE)).sum())
        may_water = dilate_tiles(F <= margin, corr)
        may_land = dilate_tiles(F >= -margin, corr)
        Lt = np.repeat(np.repeat(L[ra:rb], s, axis=0), s, axis=1)
        St = np.repeat(np.repeat(scored[ra:rb], s, axis=0), s, axis=1)
        Kt = St & OUT & np.where(Lt, may_water, may_land)
        Kp = Kt.reshape(m_, s, W, s).any(axis=(1, 3))
        K[sl] = Kp[own]
    return {"K": K, "reach": reach, "rowc": rowc, "colc": colc, "ncx": ncx, "nchunks": nchunks, "s12": s12,
            "w2l": w2l, "f32_sensitive_tiles": sens}


def bandfix_pass2(B, cls, om, Gp, lines, s, Keff, fill, L, P):
    """One scale, second pass: the shipped rule's writes with the fit alone deciding (detail 0): the
    scale's writable K pixels, outside the band or whole for a fill pixel; and the chunks it reads."""
    import numpy as np
    H, W = cls.shape
    reach, rowc, colc, ncx, nchunks = P["reach"], P["rowc"], P["colc"], P["ncx"], P["nchunks"]
    shipped = np.zeros(nchunks, np.int64)
    dirty = np.zeros(nchunks, bool)
    for r0 in range(0, H, ROW_BAND):
        n = min(ROW_BAND, H - r0)
        sl = slice(r0, r0 + n)
        Kb, Fb, Lb, omb = Keff[sl], fill[sl], L[sl], om[sl]
        if not Kb.any():
            continue
        for j in range(s):
            crow = rowc[j][0][sl][:, None] * ncx
            for i in range(s):
                flat = crow + colc[i][0][None, :]
                dirty[np.unique(flat[Kb])] = True
                f = fit_band(Gp, lines, s, i, j, r0, n, W)
                out = (omb & reach[j, i]) == 0
                wr_ = Kb & (out | Fb) & ((f > 0) != Lb)
                shipped += np.bincount(flat[wr_], minlength=nchunks)
    return shipped, dirty


def chunk_stats(counts, nchunks, w2l=None):
    import numpy as np
    t = counts[counts > 0]
    rec = {"chunks": int(nchunks), "touched": int(len(t)), "share": round(len(t) / nchunks, 6) if nchunks else 0.0,
           "tiles_written": int(counts.sum()),
           "tiles_per_touched_chunk": {"mean": round(float(t.mean()), 2) if len(t) else 0.0,
                                       "p95": int(np.percentile(t, 95, method="higher")) if len(t) else 0,
                                       "max": int(t.max()) if len(t) else 0},
           "est_ms_per_generated_chunk": round(len(t) / nchunks * TQ1B_MS_PER_WRITTEN_CHUNK, 4) if nchunks else 0.0}
    if w2l is not None:
        rec["water_to_land_tiles"] = int(w2l.sum())
        rec["land_to_water_tiles"] = int(counts.sum() - w2l.sum())
        rec["touched_with_water_to_land"] = int(((counts > 0) & (w2l > 0)).sum())
    return rec


def varint(v, alphabet, base):
    out = []
    v = int(v)
    while v >= base:
        out.append(alphabet[base + v % base])
        v //= base
    out.append(alphabet[v])
    return "".join(out)


def dilate8(K):
    import numpy as np
    H, W = K.shape
    out = K.copy()
    pad = np.zeros((H + 2, W + 2), bool)
    pad[1:-1, 1:-1] = K
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            out |= pad[1 + dr:1 + dr + H, 1 + dc:1 + dc + W]
    return out


def shared_symbols(cls, K, Kp, B):
    """uint8 per pixel: the shared table's symbol index (0-based in bandfix.symbol_order): none outside
    K+, then water, land, a K pixel of either class, thin water."""
    import numpy as np
    at = {role: n for n, role in enumerate(B["symbol_order"])}
    sym = np.full(cls.shape, at["none"], np.uint8)
    land, water = cls == 1, cls == 0
    sym[Kp & water] = at["water"]
    sym[Kp & land] = at["land"]
    sym[Kp & (cls == 2)] = at["thin"]
    sym[K & water] = at["water_k"]
    sym[K & land] = at["land_k"]
    return sym


def encode_runs(values, keep, nsym, B):
    """{row: payload} of every row holding a `keep` pixel: its first column, then one varint per run of
    equal values over the row's span, (length - 1) * nsym + value."""
    import numpy as np
    alpha, base = B["alphabet"], int(B["varint_base"])
    out = {}
    for r in np.nonzero(keep.any(axis=1))[0].tolist():
        nz = np.nonzero(keep[r])[0]
        c0, c1 = int(nz[0]), int(nz[-1])
        seg = values[r, c0:c1 + 1].astype(np.int16)
        cut = np.nonzero(np.diff(seg))[0] + 1
        starts = np.concatenate([[0], cut])
        ends = np.concatenate([cut, [len(seg)]])
        parts = [varint(c0, alpha, base)]
        for a, b in zip(starts.tolist(), ends.tolist()):
            parts.append(varint((b - a - 1) * nsym + int(seg[a]), alpha, base))
        out[int(r)] = "".join(parts)
    return out


def decode_runs(payload, nsym, B):
    """(first column, values) of one payload: encode_runs' inverse, for the round trip."""
    alpha, base = B["alphabet"], int(B["varint_base"])
    dec = {ch: n for n, ch in enumerate(alpha)}
    vals, v, mul = [], 0, 1
    for ch in payload:
        d = dec[ch]
        if d >= base:
            v += (d - base) * mul
            mul *= base
        else:
            vals.append(v + d * mul)
            v, mul = 0, 1
    out = []
    for x in vals[1:]:
        out += [x % nsym] * (x // nsym + 1)
    return vals[0], out


def round_trip(rows, values, keep, nsym, B, what):
    """Every payload decodes to the values over its span, and no row holding a `keep` pixel lacks one."""
    import numpy as np
    for r, payload in rows.items():
        c0, vals = decode_runs(payload, nsym, B)
        if vals != values[r, c0:c0 + len(vals)].tolist() or keep[r, :c0].any() or keep[r, c0 + len(vals):].any():
            raise SystemExit(f"RESULT fail {what}: row {r} does not round-trip")
    missing = sorted(set(np.nonzero(keep.any(axis=1))[0].tolist()) - set(rows))
    if missing:
        raise SystemExit(f"RESULT fail {what}: rows {missing[:5]} hold pixels but no payload")


def lua_long_lines(text, first, last, width=MAX_COLUMNS):
    """A Lua string literal of `text` (no quote, backslash or space in it) broken anywhere with \\z."""
    out, cur, pos = [], first + '"', 0
    while True:
        rest = text[pos:]
        if len(cur) + len(rest) + 1 + len(last) <= width:
            out.append(cur + rest + '"' + last)
            return out
        room = width - len(cur) - 2
        out.append(cur + rest[:room] + "\\z")
        pos += room
        cur = "  "


def render_rows(header, rows, meta):
    out = [f"-- {line}" for line in header]
    out.append("local R = {}")
    for r in sorted(rows):
        out += lua_long_lines(rows[r], f"R[{r}] = ", "")
    fields = ", ".join(f"{k} = {v}" for k, v in meta.items())
    out.append(f"return {{rows = R, {fields}}}")
    for line in out:
        if len(line) > MAX_COLUMNS:
            raise ValueError(f"line of {len(line)} columns: {line[:60]!r}")
    return "\n".join(out) + "\n"


def bandfix_shared_file(map_key, version):
    return f"bandfix_{map_key}_v{int(version)}.lua"


def _write_lf(p, text):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def emit_bandfix(map_key, out_dir=BANDFIX_GENERATED, manifest=True, scales=None, log=print):
    """The map's shared K+ table and its per-scale mask tables, byte-reproducible, and the manifest with
    S12's pricing measures and the shipped rule's, per scale."""
    import numpy as np
    import earthgeo as eg
    import time
    cfg, B = bandfix_cfg()
    if map_key not in (B.get("tables") or {}):
        raise SystemExit(f"RESULT fail config.lua bandfix.tables lists no K+ tables for {map_key}")
    scales = [int(s) for s in (scales or cfg["scales"]["values"])]
    spec = fit_spec(map_key)
    ck = FITS / map_key / spec["bodies"]["geo"]["checkpoint"]
    meta, idx, coef = load_model(ck)
    mref = eg.MapRef(map_key)
    cls = bandfix_classes(map_key, mref, B)
    nb = [tuple(x) for x in B["neighbours"]]
    om = other_masks(cls, nb)
    Gp = np.pad(level0_grid(meta, idx, coef), ((1, 0), (1, 0)))
    lines = edge_lines(meta, idx, coef)
    C = cfg["coast"]
    warp_px = warp_reach_px(cfg, map_key)
    margin = float(B["float_margin_px"])
    if not warp_px:
        margin += float(C["detail_amplitude_px"]) * float(C["detail_clamp"])
    scored, L = cls != 2, cls == 1
    rel_ck = ck.relative_to(REPO).as_posix()
    label = cfg["maps"][map_key]["display"]
    inputs = {"checkpoint": rel_ck, "checkpoint_sha256": sha256_file(ck),
              "land_sha256": sha256_file(mref.land_path), "thinwater_sha256": sha256_file(mref.thin_path),
              "bandfix_config_sha256": bandfix_digest(B),
              "coast_detail": [C["detail_amplitude_px"], C["detail_clamp"]], "margin_px": round(margin, 6)}
    if warp_px:
        inputs["warp_reach_px"] = round(warp_px, 6)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    P1, masks, t = {}, {}, {}
    K = np.zeros(cls.shape, bool)
    for s in scales:
        t0 = time.time()
        masks[s], ww_sha = waterway_footprint(cfg, mref, map_key, s, float(B["mask_margin_tiles"]))
        masks[s] &= scored
        P1[s] = bandfix_pass1(cfg, B, mref, cls, om, Gp, lines, s, masks[s], scored, L, margin, warp_px)
        P1[s]["ww_sha"] = ww_sha
        K |= P1[s]["K"]
        t[s] = time.time() - t0
    K |= scored & (om != 0)
    Kp = dilate8(K)
    order = B["symbol_order"]
    nsym = len(order)
    sym = shared_symbols(cls, K, Kp, B)
    rows = encode_runs(sym, Kp, nsym, B)
    round_trip(rows, sym, Kp, nsym, B, f"{map_key} shared table")
    kpix, kplus = int(K.sum()), int(Kp.sum())
    shared_name = bandfix_shared_file(map_key, B["version"])
    header = [f"Generated by tools/build_geo.py (band fix emitter {BANDFIX_EMITTER}) from {rel_ck}",
              f"(sha256 {inputs['checkpoint_sha256']})",
              f"and data-src/earthmaps/{map_key}-land.png and -thinwater.png.",
              f"{label}: {kpix} K pixels (every offered scale's), {kplus} K+ pixels in {len(rows)} rows.",
              "Name-free data: scripts/bandfix.lua reads it with config.lua's bandfix group.",
              "Never edit by hand: rerun the tool (plan hard rule 9)."]
    sp = out_dir / shared_name
    _write_lf(sp, render_rows(header, rows, {"format": BANDFIX_EMITTER, "width": mref.W, "height": mref.H,
                                             "k_pixels": kpix}))
    rec = {"format": BANDFIX_FORMAT, "tool": "tools/build_geo.py", "emitter_version": BANDFIX_EMITTER,
           "map": map_key, "inputs": inputs,
           "rule": {"band": "closed: a sample point at least half a reference pixel from every other-class square "
                            "is outside the band (S12)",
                    "k": "a scored pixel holding a tile outside the band whose fit lies within margin_px of the "
                         "wrong side, or within correction_tiles of a tile that may be of the other class (the game "
                         "grows water into 2 x 2 blocks), at some offered scale, and every scored pixel with a pixel "
                         "of the other class around it, so the coast follows the reference at the handler's write "
                         "threshold everywhere; the scale's waterway footprint masks it there",
                    "fill": "a K pixel whose band region at the save's scale holds no 2 x 2 block of tiles is "
                            "written whole; the handler decides it from the shared table",
                    "pricing": "S12's measures: the band rule's writes with the fit alone deciding (detail 0), "
                               "every scored pixel, no masks, the map's own chunk grid (city offset 0)",
                    "shipped": "the shipped rule's writes with the fit alone deciding: K pixels outside the "
                               "scale's masks, fill pixels whole"},
           "shared": {"file": f"terra-nauvis/scripts/generated/{shared_name}", "sha256": sha256_file(sp),
                      "bytes": sp.stat().st_size, "payload_chars": sum(len(p) for p in rows.values()),
                      "rows": len(rows), "k_pixels": kpix, "kplus_pixels": kplus},
           "scales": {}}
    for s in scales:
        t0 = time.time()
        reach = P1[s]["reach"]
        thin = thin_lut(s, reach)
        M = masks[s] & Kp
        Keff = K & ~masks[s]
        fill = Keff & thin[om]
        shipped, dirty = bandfix_pass2(B, cls, om, Gp, lines, s, Keff, fill, L, P1[s])
        bits = M.astype(np.uint8)
        mrows = encode_runs(bits, M, 2, B)
        round_trip(mrows, bits, M, 2, B, f"{map_key} s{s} masks")
        name = bandfix_file(map_key, s, B["version"])
        mheader = [f"Generated by tools/build_geo.py (band fix emitter {BANDFIX_EMITTER}) from",
                   f"data-src/waterways/manifest-{map_key}.json (sha256 {P1[s]['ww_sha']})",
                   f"and {shared_name}.",
                   f"{label} at scale {s}: {int(M.sum())} K+ pixels inside a waterway, canal, dam or basin footprint",
                   f"in {len(mrows)} rows (runs of open 0 and masked 1 over each row's span).",
                   "Name-free data: scripts/bandfix.lua reads it with config.lua's bandfix group.",
                   "Never edit by hand: rerun the tool (plan hard rule 9)."]
        p = out_dir / name
        _write_lf(p, render_rows(mheader, mrows, {"format": BANDFIX_EMITTER, "scale": s, "width": mref.W,
                                                  "height": mref.H, "masked_pixels": int(M.sum())}))
        nchunks = P1[s]["nchunks"]
        srec = {"file": f"terra-nauvis/scripts/generated/{name}", "sha256": sha256_file(p), "bytes": p.stat().st_size,
                "data_bytes_with_shared": p.stat().st_size + rec["shared"]["bytes"],
                "k_pixels_this_scale": int(P1[s]["K"].sum()), "k_pixels_writable": int(Keff.sum()),
                "fill_pixels": int(fill.sum()), "masked_kplus_pixels": int(M.sum()),
                "footprint_pixels": int(masks[s].sum()), "waterway_manifest_sha256": P1[s]["ww_sha"],
                "f32_sensitive_tiles": P1[s]["f32_sensitive_tiles"],
                "s12_rule": chunk_stats(P1[s]["s12"], nchunks, P1[s]["w2l"]),
                "shipped_rule": chunk_stats(shipped, nchunks),
                "chunks_read": {"chunks": int(dirty.sum()), "share": round(float(dirty.mean()), 6)},
                "seconds": round(t[s] + time.time() - t0, 1)}
        rec["scales"][str(s)] = srec
        log(f"{map_key} s{s}: K {srec['k_pixels_this_scale']} (writable {srec['k_pixels_writable']}, fill "
            f"{srec['fill_pixels']}); S12 rule {srec['s12_rule']['share']:.4f} of {nchunks} chunks "
            f"{srec['s12_rule']['tiles_per_touched_chunk']}; shipped {srec['shipped_rule']['share']:.4f} "
            f"{srec['shipped_rule']['tiles_per_touched_chunk']}; read {srec['chunks_read']['share']:.4f}; "
            f"mask file {srec['bytes']} B [{srec['seconds']}s]")
    log(f"{map_key} shared table: K {kpix}, K+ {kplus}, {rec['shared']['bytes']} B")
    if manifest:
        BANDFIX_DATA.mkdir(parents=True, exist_ok=True)
        _write_json(BANDFIX_DATA / f"manifest-{map_key}.json", rec)
    return rec


def emit_bandfix_masks(map_key, out_dir=BANDFIX_GENERATED, log=print):
    """The map's per-scale mask tables alone, from the committed K+ table and the waterway manifests: the K+
    table reads no waterway, so after a waterway change this writes what a full emission would, in a minute
    instead of half an hour. The manifest keeps its pricing, which masks barely move."""
    import numpy as np
    import earthgeo as eg
    cfg, B = bandfix_cfg()
    mref = eg.MapRef(map_key)
    cls = bandfix_classes(map_key, mref, B)
    order = B["symbol_order"]
    nsym = len(order)
    shared_name = bandfix_shared_file(map_key, B["version"])
    rows, _ = read_bandfix_table(Path(out_dir) / shared_name)
    sym = np.full(cls.shape, order.index("none"), np.uint8)
    for r, payload in rows.items():
        c0, vals = decode_runs(payload, nsym, B)
        sym[r, c0:c0 + len(vals)] = vals
    Kp = sym != order.index("none")
    scored = cls != 2
    label = cfg["maps"][map_key]["display"]
    mp = BANDFIX_DATA / f"manifest-{map_key}.json"
    rec = json.loads(mp.read_text(encoding="utf-8"))
    for s in [int(x) for x in cfg["scales"]["values"]]:
        mask, ww_sha = waterway_footprint(cfg, mref, map_key, s, float(B["mask_margin_tiles"]))
        mask &= scored
        M = mask & Kp
        bits = M.astype(np.uint8)
        mrows = encode_runs(bits, M, 2, B)
        round_trip(mrows, bits, M, 2, B, f"{map_key} s{s} masks")
        name = bandfix_file(map_key, s, B["version"])
        mheader = [f"Generated by tools/build_geo.py (band fix emitter {BANDFIX_EMITTER}) from",
                   f"data-src/waterways/manifest-{map_key}.json (sha256 {ww_sha})",
                   f"and {shared_name}.",
                   f"{label} at scale {s}: {int(M.sum())} K+ pixels inside a waterway, canal, dam or basin footprint",
                   f"in {len(mrows)} rows (runs of open 0 and masked 1 over each row's span).",
                   "Name-free data: scripts/bandfix.lua reads it with config.lua's bandfix group.",
                   "Never edit by hand: rerun the tool (plan hard rule 9)."]
        f = Path(out_dir) / name
        _write_lf(f, render_rows(mheader, mrows, {"format": BANDFIX_EMITTER, "scale": s, "width": mref.W,
                                                  "height": mref.H, "masked_pixels": int(M.sum())}))
        srec = rec["scales"][str(s)]
        srec.update({"sha256": sha256_file(f), "bytes": f.stat().st_size,
                     "data_bytes_with_shared": f.stat().st_size + rec["shared"]["bytes"],
                     "masked_kplus_pixels": int(M.sum()), "footprint_pixels": int(mask.sum()),
                     "waterway_manifest_sha256": ww_sha})
        log(f"{map_key} s{s}: {int(M.sum())} masked K+ pixels, {f.stat().st_size} B")
    rec["inputs"]["bandfix_config_sha256"] = bandfix_digest(B)
    _write_json(mp, rec)
    return rec


TABLE_ROW_RE = None


def read_bandfix_table(path):
    """(rows {row: payload}, fields {name: number}) of a generated band-fix table file, parsed from its
    Lua text (the R[...] lines with their backslash-z continuations, then the return line)."""
    import re
    global TABLE_ROW_RE
    if TABLE_ROW_RE is None:
        TABLE_ROW_RE = re.compile(r'^R\[(\d+)\] = "(.*)$')
    rows, cur, buf = {}, None, []
    fields = {}
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if cur is not None:
            text = line.lstrip(" ")
            if text.endswith("\\z"):
                buf.append(text[:-2])
            else:
                buf.append(text[:-1])
                rows[cur] = "".join(buf)
                cur = None
            continue
        m = TABLE_ROW_RE.match(line)
        if m:
            text = m.group(2)
            if text.endswith("\\z"):
                cur, buf = int(m.group(1)), [text[:-2]]
            else:
                rows[int(m.group(1))] = text[:-1]
        elif line.startswith("return {rows = R"):
            for k, v in re.findall(r"(\w+) = (-?\d+)", line):
                fields[k] = int(v)
    return rows, fields


class BandfixRule:
    """The handler's rule (terra-nauvis/scripts/bandfix.lua) in Python, read from the committed tables, so
    a check can compute the exact tiles the game must write from a fix-off dump of the same chunks."""

    def __init__(self, map_key, scale, generated=BANDFIX_GENERATED):
        import numpy as np
        cfg, B = bandfix_cfg()
        self.cfg, self.B, self.s = cfg, B, int(scale)
        m = cfg["maps"][map_key]
        self.W, self.H, self.wr, self.hr = m["width_px"], m["height_px"], m["wr"], m["hr"]
        shared, sf = read_bandfix_table(Path(generated) / bandfix_shared_file(map_key, B["version"]))
        masks, mf = read_bandfix_table(Path(generated) / bandfix_file(map_key, scale, B["version"]))
        if sf.get("width") != self.W or sf.get("height") != self.H or mf.get("scale") != self.s:
            raise SystemExit(f"RESULT fail the {map_key} tables do not match config.lua's map or scale {scale}")
        order = B["symbol_order"]
        self.at = {role: n for n, role in enumerate(order)}
        nsym = len(order)
        self.rows = {}
        for r, payload in shared.items():
            c0, vals = decode_runs(payload, nsym, B)
            row = np.array(vals, np.uint8)
            if r in masks:
                m0, bits = decode_runs(masks[r], 2, B)
                b = np.array(bits, bool)
                seg = row[m0 - c0:m0 - c0 + len(b)]
                land = np.isin(seg, [self.at["land"], self.at["land_k"]])
                water = np.isin(seg, [self.at["water"], self.at["water_k"]])
                seg[b & land] = self.at["land_masked"]
                seg[b & water] = self.at["water_masked"]
            self.rows[r] = (c0, row)
        nb = [tuple(x) for x in B["neighbours"]]
        self.nb = nb
        self.reach = reach_lut(self.s, nb)
        self.thin = thin_lut(self.s, self.reach)
        self.landish = {self.at["land"], self.at["land_k"], self.at["land_masked"]}
        self.k = {self.at["water_k"], self.at["land_k"]}
        self.open = {self.at[r] for r in ("water", "land", "water_k", "land_k")}

    def sym(self, c, r):
        e = self.rows.get(r)
        if e is None:
            return self.at["none"]
        c0, row = e
        k = c - c0
        return int(row[k]) if 0 <= k < len(row) else self.at["none"]

    def land(self, c, r):
        if c < 0 or r < 0 or c >= self.W or r >= self.H:
            return False
        return self.sym(c, r) in self.landish

    def mask(self, c, r, me):
        m = 0
        for b, (dc, dr) in enumerate(self.nb):
            if self.land(c + dc, r + dr) != me:
                m |= 1 << b
        return m

    def chunk(self, chx, chy, wet, kept, cx=0, cy=0):
        """The writes [(lx, ly, land)] of one chunk, in the handler's order, from its generated classes:
        wet[ly][lx] (player-blocking water) and kept[ly][lx] (water a player walks), 32 x 32."""
        s, CT = self.s, int(self.B["chunk_tiles"])
        r2 = int(self.B["spawn_keep_tiles"]) ** 2
        gx0, gy0 = chx * CT + cx, chy * CT + cy
        c0, c1 = gx0 // s + self.wr, (gx0 + CT - 1) // s + self.wr
        r0, r1 = gy0 // s + self.hr, (gy0 + CT - 1) // s + self.hr
        if not any(self.sym(c, r) in self.k for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)):
            return []
        x0, y0 = chx * CT, chy * CT
        dx = x0 if x0 > 0 else (-(x0 + CT - 1) if x0 + CT - 1 < 0 else 0)
        dy = y0 if y0 > 0 else (-(y0 + CT - 1) if y0 + CT - 1 < 0 else 0)
        near = dx * dx + dy * dy < r2

        def spawn_kept(lx, ly):
            return near and (x0 + lx) ** 2 + (y0 + ly) ** 2 < r2
        wrote = {}
        queue = []
        pm = {}
        for ly in range(CT):
            gy = gy0 + ly
            r, j = gy // s + self.hr, gy % s
            for lx in range(CT):
                gx = gx0 + lx
                c, i = gx // s + self.wr, gx % s
                code = self.sym(c, r)
                if code not in self.k:
                    continue
                land = code in self.landish
                if kept[ly][lx] or bool(wet[ly][lx]) != land or spawn_kept(lx, ly):
                    continue
                if (c, r) not in pm:
                    pm[(c, r)] = self.mask(c, r, land)
                m = pm[(c, r)]
                if self.thin[m] or (m & int(self.reach[j, i])) == 0:
                    wrote[(lx, ly)] = land
                    queue.append((lx, ly))

        def post_wet(lx, ly):
            if (lx, ly) in wrote:
                return not wrote[(lx, ly)]
            return bool(wet[ly][lx])

        def open_class(lx, ly):
            gx, gy = gx0 + lx, gy0 + ly
            code = self.sym(gx // s + self.wr, gy // s + self.hr)
            return (code in self.landish) if code in self.open else None
        q = 0
        while q < len(queue):
            lx, ly = queue[q]
            for dx_, dy_ in ((1, 0), (0, 1)):
                w = post_wet(lx, ly)
                ax, ay, bx, by = lx + dx_, ly + dy_, lx - dx_, ly - dy_
                a_in = 0 <= ax < CT and 0 <= ay < CT
                b_in = 0 <= bx < CT and 0 <= by < CT
                if (a_in and post_wet(ax, ay) == w) or (b_in and post_wet(bx, by) == w):
                    continue
                for nx, ny, inside in ((ax, ay, a_in), (bx, by, b_in)):
                    if inside and (nx, ny) not in wrote and not kept[ny][nx] and not spawn_kept(nx, ny) \
                            and open_class(nx, ny) == (not w):
                        wrote[(nx, ny)] = not w
                        queue.append((nx, ny))
                        break
            q += 1
        return [(lx, ly, wrote[(lx, ly)]) for lx, ly in queue]


def bandfix_files(map_key, B, scales):
    return [bandfix_shared_file(map_key, B["version"])] + [bandfix_file(map_key, s, B["version"]) for s in scales]


def check_bandfix(map_key, scales=None):
    """T16: two emissions byte-identical to each other and to the committed tables (every offered scale:
    the shared table is the union over them)."""
    cfg, B = bandfix_cfg()
    scales = [int(s) for s in cfg["scales"]["values"]]
    fails = []
    with tempfile.TemporaryDirectory(prefix="tn-bandfix-") as td:
        runs = []
        for n in range(2):
            d = Path(td) / f"run{n}"
            emit_bandfix(map_key, d, manifest=False, scales=scales, log=lambda *_: None)
            runs.append(d)
        for name in bandfix_files(map_key, B, scales):
            a, b = (runs[0] / name).read_bytes(), (runs[1] / name).read_bytes()
            committed = BANDFIX_GENERATED / name
            if a != b:
                fails.append(f"{name}: two emissions differ")
            if not committed.exists():
                fails.append(f"{name}: no committed file")
            elif committed.read_bytes() != a:
                fails.append(f"{name}: the committed file differs from a fresh emission (rerun build_geo.py emit "
                             f"--bandfix)")
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("emit", "check", "offline"):
        p = sub.add_parser(name)
        p.add_argument("--map", required=True)
        if name in ("emit", "check"):
            p.add_argument("--bandfix", action="store_true",
                           help="the Exact coastlines K+ tables and their pricing instead of the fit bodies")
            p.add_argument("--masks-only", action="store_true",
                           help="with --bandfix on emit: rewrite the mask tables from the committed K+ table")
            p.add_argument("--scales", help="comma list of scales (default: every offered scale)")
    p = sub.add_parser("refit-islands")
    p.add_argument("--map", required=True)
    p.add_argument("--src", default="model-8192.npz")
    p.add_argument("--dst", default="model-8192-t1e.npz")
    p = sub.add_parser("fit")
    p.add_argument("--map", required=True)
    p.add_argument("--work", help="checkpoint folder outside the repo (default "
                                  "%%FACTORIO_WS%%/previews/earth-build/fits/<map>)")
    p.add_argument("--nmax", type=int, default=65536)
    p.add_argument("--stop-agreement", type=float, default=FIT_BAR,
                   help="stop extra-steps growth steps after the first step whose agreement reaches this")
    p.add_argument("--extra-steps", type=int, default=2)
    p.add_argument("--max-steps", type=int, help="run at most this many growth steps now (resume later)")
    p.add_argument("--through", type=int, default=8192,
                   help="always run through this term count (the curve compares the shipped checkpoint with it)")
    p.add_argument("--region", type=parse_region, action="append",
                   help="lon0,lon1,lat0,lat1,weight: multiply the fit's weight on the pixels of this box (degrees "
                        "in the map's own frame; repeatable, overlaps take the largest); off by default")
    p.add_argument("--start-from", help="continue the growth from this checkpoint of the same reference (an "
                                        "earlier fit's growth step) instead of the least-squares start")
    p = sub.add_parser("curve")
    p.add_argument("--map", required=True)
    p.add_argument("--work")
    p.add_argument("--min-sample", type=float, default=0.985)
    p.add_argument("--only", help="comma list of term targets to evaluate instead")
    p = sub.add_parser("adopt")
    p.add_argument("--map", required=True)
    p.add_argument("--work")
    p.add_argument("--budget", type=int, help="a region-weighted fit grown with --start-from: ship its largest "
                                              "evaluated step within this many terms (at most 8,192)")
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        st = fit(a.map, a.work or default_work(a.map), a.nmax, a.stop_agreement, a.extra_steps, a.max_steps,
                 a.through, a.region, a.start_from)
        last = st["points"][-1] if st["points"] else {}
        print(f"RESULT ok fit {a.map} steps={len(st['points'])} terms={last.get('terms')} "
              f"agreement={last.get('sample_agreement')}")
        return 0
    if a.cmd == "curve":
        only = {int(x) for x in a.only.split(",")} if a.only else None
        doc = curve(a.map, a.work or default_work(a.map), a.min_sample, only)
        n = sum(1 for p in doc["points"] if "t1" in p)
        print(f"RESULT ok curve {a.map} evaluated={n} of {len(doc['points'])}")
        return 0
    if a.cmd == "adopt":
        rep = adopt(a.map, a.work or default_work(a.map), budget=a.budget)
        print(json.dumps({k: {"checkpoint": v["checkpoint"], "terms": v["terms"], "t1": v["t1"]["agreement"]}
                          for k, v in rep.items()}, indent=1))
        print(f"RESULT ok adopted {rep['geo']['checkpoint']} and {rep['land_coarse']['checkpoint']}")
        return 0
    scales = [int(x) for x in a.scales.split(",")] if getattr(a, "scales", None) else None
    if a.cmd == "emit" and a.bandfix and a.masks_only:
        rec = emit_bandfix_masks(a.map)
        print(f"RESULT ok rewrote {[r['file'] for r in rec['scales'].values()]} and "
              f"data-src/bandfix/manifest-{a.map}.json")
        return 0
    if a.cmd == "emit" and a.bandfix:
        rec = emit_bandfix(a.map, scales=scales)
        print(f"RESULT ok emitted {[r['file'] for r in rec['scales'].values()]} and "
              f"data-src/bandfix/manifest-{a.map}.json")
        return 0
    if a.cmd == "check" and a.bandfix:
        fails = check_bandfix(a.map, scales)
        for f in fails:
            print(f"FAIL {f}")
        print(f"RESULT {'ok' if not fails else 'fail'} failed={len(fails)} two band-fix emissions byte-identical to "
              f"the committed tables")
        return 0 if not fails else 1
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
