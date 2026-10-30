# Atlantic coast fit: provenance

The checkpoints here are the inputs of `tools/build_geo.py` for Atlantic (ARCHITECTURE.md,
"Build-time data flow", step 2; milestone `olde-world-atlantic`). The T16 data-src row re-hashes every
file of
this folder against the table below, and the gate's `geo_emit` row re-emits the two generated bodies
from them twice and compares each byte for byte with the committed Lua.

## Source

Atlantic's first native-resolution fit (design experiment 4), made with `tools/build_geo.py fit`,
S1-fit's fitter ported operation for operation,
from the repo root with Python 3.13, numpy 2.5.1 and Pillow 12.2.0, its work folder outside the repo:

```
python tools/build_geo.py fit --map atlantic --work <work folder>/fits-olde-world-atlantic/atlantic
python tools/build_geo.py curve --map atlantic --work <work folder>/fits-olde-world-atlantic/atlantic
python tools/build_geo.py adopt --map atlantic --work <work folder>/fits-olde-world-atlantic/atlantic
```

Target: the reference signed distance soft-saturated as `4 * tanh(sdf / 4)` px, thin water
filled as land with weight 0; tents on dyadic grids from 1 to 1024 px (K 10); greedy selection
growing 1.25 times per step from 64 terms; one-sided refit with margin 1 px (lam 0.0001, 4 Newton
steps, at most 150 CG iterations). Every growth step's checkpoint was kept and scored; the fit
stopped two steps after the first step at or above 0.991 and not before 8,192 terms. Peak working set
3,408 MB in the fit process (native resolution fits in memory, so no 2x subsample was needed); fit
time 1.37 h over 32 growth steps on the E-cores at idle priority (the fit ran pinned to logical
processors 16 to 23 beside a live gate run).

The curve record (`curve.json`; t1_metrics over every reference pixel centre, thin water
excluded, islands 4-connected, scored with `build_geo.py curve`):

| Checkpoint | Terms | Agreement | Coast p99 | Coast max | Islands of 65 px or more present |
|---|---|---|---|---|---|
| `model-64.npz` | 64 | 0.820599 | 65.00 px | >64 px (t1_metrics' cap) | 148 of 697 |
| `model-128.npz` | 128 | 0.924584 | 65.00 px | >64 px (t1_metrics' cap) | 189 of 697 |
| `model-256.npz` (coarse field) | 256 | 0.952318 | 58.86 px | >64 px (t1_metrics' cap) | 174 of 697 |
| `model-512.npz` | 512 | 0.966854 | 36.12 px | >64 px (t1_metrics' cap) | 195 of 697 |
| `model-1024.npz` | 1,024 | 0.976327 | 23.12 px | >64 px (t1_metrics' cap) | 209 of 697 |
| `model-2048.npz` | 2,048 | 0.982878 | 14.23 px | >64 px (t1_metrics' cap) | 234 of 697 |
| `model-2842.npz` | 2,842 | 0.985299 | 11.42 px | >64 px (t1_metrics' cap) | 259 of 697 |
| `model-3553.npz` | 3,553 | 0.986634 | 9.62 px | >64 px (t1_metrics' cap) | 273 of 697 |
| `model-4096.npz` | 4,096 | 0.987494 | 8.75 px | >64 px (t1_metrics' cap) | 280 of 697 |
| `model-4441.npz` | 4,441 | 0.988011 | 8.28 px | >64 px (t1_metrics' cap) | 293 of 697 |
| `model-5551.npz` | 5,551 | 0.989144 | 7.38 px | >64 px (t1_metrics' cap) | 328 of 697 |
| `model-6939.npz` | 6,939 | 0.990148 | 6.50 px | 60.15 px | 354 of 697 |
| `model-8192.npz` | 8,192 | 0.990915 | 5.52 px | 55.66 px | 387 of 697 |
| `model-8674.npz` (shipped) | 8,674 | 0.991198 | 5.50 px | 54.72 px | 397 of 697 |
| `model-10842.npz` | 10,842 | 0.992051 | 4.53 px | 54.37 px | 436 of 697 |
| `model-13553.npz` | 13,553 | 0.992804 | 4.30 px | 54.80 px | 473 of 697 |

The shipped coast fit is the smallest checkpoint at or above T1's 0.991 (8,674 terms); the
coarse land field is the fit's 256-term checkpoint. numpy's `savez` stamps the zip
entries with the run's time, so a rerun writes other bytes holding the same arrays; the committed
files are the inputs of record.

## Emission

```
python tools/build_geo.py emit --map atlantic
```

`fit.json` names the checkpoint of each body; the tool writes
`terra-nauvis/prototypes/generated/geo_atlantic_v1.lua` (from `model-8674.npz`) and
`terra-nauvis/prototypes/generated/land_coarse_atlantic_v1.lua` (from `model-256.npz`) and
records terms, factors, row groups, input and output sha256 in `manifest.json`.

## Files and sha256

| File | sha256 | Source |
|---|---|---|
| `curve.json` | `86e6707b798b94db539fcddda9690702b57fc3b30efb52024dea2a8c26d55af4` | `build_geo.py curve` over the fit's work folder, copied by `adopt` |
| `model-8674.npz` | `9ff17ccafb972b0d1e6c40d00dc193d8797f32dd21634c6d3c7b13f7f2280fe9` | `build_geo.py fit` growth step of 8,674 terms, copied by `adopt` |
| `model-256.npz` | `a793e2c60335f0b55a05641426be0f105a1c8feff09d346f4719da9c2ce6de90` | `build_geo.py fit` growth step of 256 terms, copied by `adopt` |
| `fit.json` | `158300d0c3a3ec1077db31629c17e4b08c9a5d64c413e1e0934461f7189fd94e` | `build_geo.py adopt`: which checkpoint each body uses |
| `manifest.json` | `9f06e70d3de32242136ff4be16af5f973593919e0aa3bf1c0e02668688b0e14d` | `build_geo.py emit` |
