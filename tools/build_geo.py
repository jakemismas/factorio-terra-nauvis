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


def _newton(B, c, y, valid, m, lam, steps, tol, maxit, log):
    import numpy as np
    lamv = lam * B.precond()
    f = B.forward(c)
    J = _hinge_obj(f, c, y, valid, m, lamv)
    iters = 0
    for s in range(steps):
        a = ((y * f) < m) & valid
        cn, it = _pcg(B, c, a, (y * m).astype(np.float32), lam, tol, maxit)
        iters += it
        fn = B.forward(cn)
        Jn = _hinge_obj(fn, cn, y, valid, m, lamv)
        if Jn > J:
            # f is linear in c, so a damped step is the same blend of both evaluations
            best = (Jn, fn, cn)
            for step in (0.5, 0.25, 0.125):
                ft = f + step * (fn - f)
                ct = c + step * (cn - c)
                Jt = _hinge_obj(ft, ct, y, valid, m, lamv)
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


def fit(map_key, work, nmax, stop_agreement, extra_steps, max_steps=None, through=8192):
    """S1-fit's greedy fit at native resolution, resumable (see the section comment above)."""
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

    P = FIT_PARAMS
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
            R = valid * t
        else:
            act_px = ((y * f) < marg) & valid
            R = act_px * (y * marg - f)
            del act_px
        lv, fl = B.top_candidates(R, N - B.n())
        del R
        c = B.add(lv, fl, c)
        cg_ls = 0
        if first:
            c, cg_ls = _pcg(B, c, valid, t, P["lam"], P["tol"], P["maxit"])
        f = None
        c, f, J, cg_h = _newton(B, c, y, valid, marg, P["lam"], P["newton"], P["tol"], P["maxit"], log)
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


def adopt(map_key, work, version=1):
    """Copy the shipped checkpoints (the smallest at or above FIT_BAR, and the 256-term one) and the
    curve into data-src/fits/<map>/ and write its fit.json; the emitter reads only that folder."""
    import shutil
    work = Path(work)
    doc = json.loads((work / "curve.json").read_text(encoding="utf-8"))
    pts = [p for p in doc["points"] if "t1" in p]
    ship = next((p for p in sorted(pts, key=lambda p: p["terms"]) if p["t1"]["agreement"] >= FIT_BAR), None)
    if ship is None:
        raise SystemExit(f"RESULT fail no evaluated checkpoint of {map_key} reaches {FIT_BAR}")
    coarse = next((p for p in pts if p["terms_target"] == COARSE_TERMS), None)
    if coarse is None:
        raise SystemExit(f"RESULT fail the {COARSE_TERMS}-term checkpoint of {map_key} is not evaluated")
    dst = FITS / map_key
    dst.mkdir(parents=True, exist_ok=True)
    for p in (ship, coarse):
        shutil.copyfile(work / p["checkpoint"], dst / p["checkpoint"])
    _write_json(dst / "curve.json", doc)
    import tnconfig
    label = tnconfig.load()["maps"][map_key]["display"]
    spec = {"format": "tn-fit/1", "map": map_key,
            "note": f"Which checkpoint each generated body of {label} is emitted from (tools/build_geo.py). "
                    "See PROVENANCE.md.",
            # each note heads its generated file, so it stays short (the file's 120-column rule)
            "bodies": {"geo": {"checkpoint": ship["checkpoint"], "file": f"geo_{map_key}_v{version}.lua",
                               "note": f"{label}'s coast fit, the smallest checkpoint at or above {FIT_BAR}"},
                       "land_coarse": {"checkpoint": coarse["checkpoint"],
                                       "file": f"land_coarse_{map_key}_v{version}.lua",
                                       "note": f"{label}'s coarse land field, the {COARSE_TERMS}-tent checkpoint "
                                               "of the same fit"}}}
    _write_json(dst / "fit.json", spec)
    return {"geo": ship, "land_coarse": coarse}


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
    p = sub.add_parser("curve")
    p.add_argument("--map", required=True)
    p.add_argument("--work")
    p.add_argument("--min-sample", type=float, default=0.985)
    p.add_argument("--only", help="comma list of term targets to evaluate instead")
    p = sub.add_parser("adopt")
    p.add_argument("--map", required=True)
    p.add_argument("--work")
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        st = fit(a.map, a.work or default_work(a.map), a.nmax, a.stop_agreement, a.extra_steps, a.max_steps,
                 a.through)
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
        rep = adopt(a.map, a.work or default_work(a.map))
        print(json.dumps({k: {"checkpoint": v["checkpoint"], "terms": v["terms"], "t1": v["t1"]["agreement"]}
                          for k, v in rep.items()}, indent=1))
        print(f"RESULT ok adopted {rep['geo']['checkpoint']} and {rep['land_coarse']['checkpoint']}")
        return 0
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
