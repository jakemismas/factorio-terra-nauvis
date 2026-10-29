#!/usr/bin/env python3
"""Spawn bearings emitter (milestone spawn-cities; T7 (b), JI-08).

  python tools/build_spawn.py emit --map europe     write terra-nauvis/prototypes/generated/spawn_<map>_v1.lua
  python tools/build_spawn.py check --map europe    emit twice into memory and compare byte for byte with
                                                    the committed file (the gate's sc_dump_facts row)

The spawn lake and the starting ore must lie on the spawn's own land (T7 (b): each reached on foot
from the spawn tile). S7's seed-folded lake angle put the lake north of every city at seed 1000,
which at scale 1 is open water for Tallinn, Amsterdam and Stockholm, and starting ore follows
vanilla's spot noise, which does not know the sea: at scale 1 Tallinn's copper and Helsinki's stone
landed across the Gulf of Finland, and a bias along the lake's bearing sent Paris's copper to
England. So per city and integer scale the tool reads the land component that holds the city's
pixel in the reference land raster (thin water counted as land, as the fit fills it; 4-connected,
inside a window of 1.5 start radii), and writes, in sixteenths of a turn (0 east, 4 south: world y
and raster rows both grow southward):

  - bearings: the lake's bearing, the one whose lake disc and straight path from the city's pixel
    centre lie most fully in that component, ties broken by a per-city preferred bearing so lakes do
    not all face one way;
  - bias, bias_width and coastal: the starting-ore bias the start mask multiplies, the half-plane
    clamp(1 + (x, y) . b / width, 0, 1) on bearing b, or none (coastal 0). Vanilla's starting ore
    takes, per ore, the best-scoring of about 11 spot-noise candidates inside the start disc, so a
    bias can only steer among them: the tool scores every bearing and width of spawn.bias.widths,
    and no bias, by the share of starting patches it would leave off the city's own land, over
    spawn.bias.layouts random candidate layouts (a fixed seed, so independent of the map seed and
    reproducible; spawn.bias.ores ores of spawn.bias.candidates candidates each in the start
    region, at least spawn.bias.spacing tiles apart), with the start mask as the game evaluates it
    (the coarse field from the map's coarse checkpoint, and the spawn lake without its noise) and
    vanilla's favorability (2 * mask - distance / radius, the mask term 0 within `excluder`
    tiles); a patch fails when under spawn.bias.share of its sample points (the centre and rings
    of spawn.bias.patch tiles) lie on the component, off the spawn lake and inside the start disc.
    The bias goes on only where it lowers the failure share by more than spawn.bias.margin; ties
    take the widest width, then the lowest bearing.

The lake geometry comes from config.lua (spawn.lake: its distance, and its radius offset * divisor
plus the noise amplitude); the start disc's radius is spawn.bias.radius. The output is name-free
data keyed by the city setting's values.
"""
import argparse
import hashlib
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_geo  # noqa: E402  (it imports numpy only inside its functions)

EMITTER_VERSION = 3
GENERATED = REPO / "terra-nauvis" / "prototypes" / "generated"
CITIES = REPO / "terra-nauvis" / "prototypes" / "tables" / "cities.lua"
SCALES = (1, 2, 3, 4, 5, 6)
PATH_STEP_PX = 0.25
FIELDS = ("bearings", "bias", "bias_width", "coastal")
WINDOW_RADII = 1.5


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def preferred(key, steps):
    """A per-city bearing to break ties, stable and spread over the turn."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % steps


class Component:
    """The 4-connected land component holding a pixel, inside a square window around it (pixels off
    the window or off the raster are outside the component). A city pixel that is water takes the
    component of the nearest land pixel in the window."""

    def __init__(self, land, col, row, radius_px):
        import numpy as np
        import nav
        H, W = land.shape
        r = int(math.ceil(radius_px)) + 2
        self.r0, self.c0 = row - r, col - r
        win = np.zeros((2 * r + 1, 2 * r + 1), bool)
        ys0, ys1 = max(0, self.r0), min(H, row + r + 1)
        xs0, xs1 = max(0, self.c0), min(W, col + r + 1)
        win[ys0 - self.r0:ys1 - self.r0, xs0 - self.c0:xs1 - self.c0] = land[ys0:ys1, xs0:xs1]
        lab, _ = nav.labels(win, 4)
        k = lab[r, r]
        if k < 0:
            ys, xs = np.nonzero(lab >= 0)
            if ys.size:
                i = int(np.argmin((ys - r) ** 2 + (xs - r) ** 2))
                k = lab[ys[i], xs[i]]
        self.mask = (lab == k) if k >= 0 else np.zeros_like(win)

    def at(self, xs, ys):
        """Membership of pixels (integer arrays of columns and rows)."""
        import numpy as np
        rr, cc = ys - self.r0, xs - self.c0
        ok = (rr >= 0) & (rr < self.mask.shape[0]) & (cc >= 0) & (cc < self.mask.shape[1])
        out = np.zeros(np.shape(xs), bool)
        out[ok] = self.mask[rr[ok], cc[ok]]
        return out

    def disc(self, cx, cy, radius):
        """(share of the pixels whose centres lie within `radius` px of (cx, cy) that are in the
        component, their centroid offset from (cx, cy) over the component's pixels)."""
        import numpy as np
        r = max(radius, 0.5)
        ys, xs = np.mgrid[int(math.floor(cy - r - 1)):int(math.ceil(cy + r + 1)) + 1,
                          int(math.floor(cx - r - 1)):int(math.ceil(cx + r + 1)) + 1]
        inside = (xs + 0.5 - cx) ** 2 + (ys + 0.5 - cy) ** 2 <= r * r
        if not inside.any():
            inside = (xs == int(math.floor(cx))) & (ys == int(math.floor(cy)))
        member = self.at(xs, ys) & inside
        share = float(member.sum()) / float(inside.sum())
        if member.any():
            cen = (float((xs[member] + 0.5).mean()) - cx, float((ys[member] + 0.5).mean()) - cy)
        else:
            cen = (0.0, 0.0)
        return share, cen

    def path(self, x0, y0, x1, y1):
        import numpy as np
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / PATH_STEP_PX) + 1)
        t = np.linspace(0.0, 1.0, n)
        xs = np.floor(x0 + t * (x1 - x0)).astype(int)
        ys = np.floor(y0 + t * (y1 - y0)).astype(int)
        return float(self.at(xs, ys).mean())


def layouts(cfg):
    """The Monte Carlo candidate layouts (n x ores x candidates x 2, tiles from the spawn): uniform
    points in the start region, each rejected within `spacing` of the 60 points drawn before it."""
    import numpy as np
    B = cfg["spawn"]["bias"]
    rng = np.random.default_rng(int(B["seed"]))
    per, ores, half = int(B["candidates"]), int(B["ores"]), B["region"] / 2
    out = np.empty((int(B["layouts"]), per * ores, 2))
    for n in range(out.shape[0]):
        k = 0
        while k < per * ores:
            q = rng.uniform(-half, half, 2)
            lo = max(0, k - 60)
            if k == lo or (((out[n, lo:k] - q) ** 2).sum(1) >= B["spacing"] ** 2).all():
                out[n, k] = q
                k += 1
    return out.reshape(out.shape[0], per, ores, 2).transpose(0, 2, 1, 3)


def bias_for(cfg, comp, coarse, col, row, s, lake_xy, cands):
    """(bias bearing, width, on flag) of one city at one scale (module docstring)."""
    import numpy as np
    B = cfg["spawn"]["bias"]
    L = cfg["spawn"]["lake"]
    M = cfg["_start_mask"]
    x, y = cands[..., 0], cands[..., 1]
    d = np.hypot(x, y)

    def lake(px, py):
        return L["magnitude"] * (np.hypot(px - lake_xy[0], py - lake_xy[1]) / L["divisor"] - L["offset"])

    H, W = coarse.shape
    u, v = col + x / s, row + y / s
    i0 = np.clip(np.floor(u).astype(int), 0, W - 2)
    j0 = np.clip(np.floor(v).astype(int), 0, H - 2)
    fu, fv = np.clip(u - i0, 0, 1), np.clip(v - j0, 0, 1)
    c = (coarse[j0, i0] * (1 - fu) * (1 - fv) + coarse[j0, i0 + 1] * fu * (1 - fv) +
         coarse[j0 + 1, i0] * (1 - fu) * fv + coarse[j0 + 1, i0 + 1] * fu * fv)
    base = np.clip((np.minimum(M["coarse_gain"] * c, lake(x, y)) - M["floor"]) / M["span"], 0, 1)
    ring = np.array([(0.0, 0.0)] + [(r * math.cos(a), r * math.sin(a)) for r in B["patch"]
                                    for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)])
    px, py = x[..., None] + ring[:, 0], y[..., None] + ring[:, 1]
    cc = np.floor(col + 0.5 + px / s).astype(int)
    rr = np.floor(row + 0.5 + py / s).astype(int)
    ok = comp.at(cc, rr) & (lake(px, py) > 0) & (np.hypot(px, py) <= B["radius"])
    good = ok.mean(-1) >= B["share"]
    inside = (d < B["radius"]) & (d > B["excluder"])
    pen = np.minimum(1.0, d / B["radius"])

    def failure(mask):
        fav = 2 * mask * inside - pen
        i = np.argmax(fav, axis=-1)
        return round(1.0 - float(np.take_along_axis(good, i[..., None], -1).mean()), 4)

    off = failure(base)
    steps = int(L["bearings"])
    best = None
    for w in sorted(B["widths"], reverse=True):
        for b in range(steps):
            th = 2 * math.pi * b / steps
            f = failure(base * np.clip(1 + (x * math.cos(th) + y * math.sin(th)) / w, 0, 1))
            if best is None or f < best[0]:
                best = (f, b, w)
    if best[0] < off - B["margin"]:
        return best[1], best[2], 1
    return 0, max(B["widths"]), 0


def bearings_for(cfg, land, key, col, row, scale, coarse, cands):
    """(lake bearing, bias bearing, bias width, coastal flag) of one city at one scale."""
    L = cfg["spawn"]["lake"]
    B = cfg["spawn"]["bias"]
    steps = int(L["bearings"])
    s = int(scale)
    d = L["distance"] / s
    radius = (L["offset"] * L["divisor"] + L["noise"]["amplitude"]) / s
    start = B["radius"] / s
    comp = Component(land, col, row, max(start, d + 2 * radius) * WINDOW_RADII)
    x0, y0 = col + 0.5, row + 0.5
    scores = []
    for k in range(steps):
        th = 2 * math.pi * k / steps
        cx, cy = x0 + d * math.cos(th), y0 + d * math.sin(th)
        disc, _ = comp.disc(cx, cy, radius)
        wide, _ = comp.disc(cx, cy, radius * 2)
        path = comp.path(x0, y0, cx, cy)
        scores.append((round(min(disc, path), 6), round(wide, 6)))
    pref = preferred(key, steps)
    lake = max(range(steps), key=lambda k: (scores[k][0], scores[k][1],
                                            -min((k - pref) % steps, (pref - k) % steps), -k))
    th = 2 * math.pi * lake / steps
    bias, width, on = bias_for(cfg, comp, coarse, col, row, s,
                               (L["distance"] * math.cos(th), L["distance"] * math.sin(th)), cands)
    return lake, bias, width, on


def render(rows, header):
    out = list(header)
    out.append("return {")
    for field in FIELDS:
        out.append(f"  {field} = {{")
        for key, rec in rows:
            k = key if key.replace("_", "").isalnum() and not key[0].isdigit() and "-" not in key else f'["{key}"]'
            out.append(f"    {k} = {{{', '.join(str(v) for v in rec[field])}}},")
        out.append("  },")
    out.append("}")
    return "\n".join(out) + "\n"


def emit_text(map_key):
    import earthgeo as eg
    import tnconfig
    cfg = tnconfig.load()
    g = spawn_record(cfg, map_key)
    values = cfg["settings"][g["city_setting"]]["allowed_values"]
    table = tnconfig.load(CITIES)[map_key]["cities"]
    m = cfg["maps"][map_key]
    ppd = cfg["coordinates"]["px_per_degree"]
    mref = eg.MapRef(map_key)
    land = mref.land.astype(bool) | mref.thin.astype(bool)
    cfg["_start_mask"] = start_mask_of(cfg, map_key)
    ckpt = coarse_checkpoint(map_key)
    coarse = build_geo.pixel_values(*build_geo.load_model(ckpt)).astype("float64")
    cands = layouts(cfg)
    rows = []
    for v in values[1:]:
        c = table[v]
        col = math.floor((c["lon"] - m["lon_left_edge"]) * ppd)
        row = math.floor((m["lat_top_edge"] - c["lat"]) * ppd)
        rec = {f: [] for f in FIELDS}
        for s in SCALES:
            for f, x in zip(FIELDS, bearings_for(cfg, land, v, col, row, s, coarse, cands)):
                rec[f].append(x)
        rows.append((v, rec))
    png = REPO / "data-src" / "earthmaps" / f"{map_key}-land.png"
    thin = REPO / "data-src" / "earthmaps" / f"{map_key}-thinwater.png"
    header = [
        f"-- Generated by tools/build_spawn.py (emitter {EMITTER_VERSION}) from data-src/earthmaps/{map_key}-land.png",
        f"-- (sha256 {sha256_file(png)}),",
        f"-- data-src/earthmaps/{map_key}-thinwater.png (sha256 {sha256_file(thin)})",
        f"-- prototypes/tables/cities.lua (sha256 {sha256_file(CITIES)})",
        f"-- and the coarse checkpoint data-src/fits/{map_key}/{ckpt.name}",
        f"-- (sha256 {sha256_file(ckpt)}).",
        "-- Per city (the spawn-city setting's values) and scale 1 to 6: the spawn lake's bearing, inside",
        "-- the land component holding the city, and the starting-ore bias bearing, both in sixteenths of",
        "-- a turn (0 east, 4 south); the bias width in tiles; and 1 where the start mask's bias is on.",
        "-- Name-free data; never edit by hand: rerun the tool (plan hard rule 9).",
    ]
    return render(rows, header)


def coarse_checkpoint(map_key):
    """The map's coarse checkpoint (data-src/fits/<map>/fit.json's land_coarse body)."""
    return build_geo.FITS / map_key / build_geo.fit_spec(map_key)["bodies"]["land_coarse"]["checkpoint"]


def start_mask_of(cfg, map_key):
    """The numbers of the start mask version the map's newest geography version names."""
    import tnconfig
    name = tnconfig.geography_versions(cfg)[map_key][-1]["start_mask"]
    for m in cfg["start_mask"]["versions"]:
        if m["name"] == name:
            return m
    raise SystemExit(f"config.lua names start mask {name}, which start_mask.versions lacks")


def spawn_record(cfg, map_key):
    """The spawn record of the map's newest geography version (the one its preset names), whose
    bearings file this tool writes."""
    import tnconfig
    sp = tnconfig.spawn_of(tnconfig.geography_versions(cfg)[map_key][-1])
    if not sp:
        raise SystemExit(f"config.lua gives {map_key}'s newest geography version no spawn record")
    return sp


def out_path(map_key):
    """The bearings file the newest version's spawn record names (prototypes/generated/...)."""
    import tnconfig
    return REPO / "terra-nauvis" / spawn_record(tnconfig.load(), map_key)["bearings"]


def emit(map_key):
    text = emit_text(map_key)
    out_path(map_key).write_text(text, encoding="utf-8", newline="\n")
    print(f"RESULT ok wrote {out_path(map_key).relative_to(REPO).as_posix()} sha256 {sha256_file(out_path(map_key))}")
    return 0


def check(map_key):
    """Failures: two emissions differ, or one differs from the committed file."""
    a, b = emit_text(map_key), emit_text(map_key)
    fails = []
    if a != b:
        fails.append("two emissions differ")
    have = out_path(map_key).read_text(encoding="utf-8") if out_path(map_key).exists() else None
    if have != a:
        fails.append(f"{out_path(map_key).name} differs from a fresh emission (rerun: python tools/build_spawn.py emit "
                     f"--map {map_key})")
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("emit", "check"):
        p = sub.add_parser(name)
        p.add_argument("--map", default="europe")
    a = ap.parse_args(argv)
    if a.cmd == "emit":
        return emit(a.map)
    fails = check(a.map)
    print(f"RESULT {'ok' if not fails else 'fail'} check {a.map}: {fails or 'two emissions equal the committed file'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
