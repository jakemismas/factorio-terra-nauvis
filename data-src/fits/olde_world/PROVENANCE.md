# Old World coast fit: provenance

The checkpoints here are the inputs of `tools/build_geo.py` for Old World (ARCHITECTURE.md,
"Build-time data flow", step 2; milestone `olde-world-atlantic`). The T16 data-src row re-hashes every
file of
this folder against the table below, and the gate's `geo_emit` row re-emits the two generated bodies
from them twice and compares each byte for byte with the committed Lua.

## Source

Old World's first native-resolution fit (design experiment 5), made with `tools/build_geo.py fit`,
S1-fit's fitter ported operation for operation,
from the repo root with Python 3.13, numpy 2.5.1 and Pillow 12.2.0, its work folder outside the repo:

```
python tools/build_geo.py fit --map olde_world --work <work folder>/fits-olde-world-atlantic/olde_world
python tools/build_geo.py curve --map olde_world --work <work folder>/fits-olde-world-atlantic/olde_world
python tools/build_geo.py adopt --map olde_world --work <work folder>/fits-olde-world-atlantic/olde_world
```

Target: the reference signed distance soft-saturated as `4 * tanh(sdf / 4)` px, thin water
filled as land with weight 0; tents on dyadic grids from 1 to 1024 px (K 10); greedy selection
growing 1.25 times per step from 64 terms; one-sided refit with margin 1 px (lam 0.0001, 4 Newton
steps, at most 150 CG iterations). Every growth step's checkpoint was kept and scored; the fit
stopped two steps after the first step at or above 0.991 and not before 8,192 terms. Peak working set
1,732 MB in the fit process (native resolution fits in memory, so no 2x subsample was needed); fit
time 0.67 h over 29 growth steps on the E-cores at idle priority (the fit ran pinned to logical
processors 16 to 23 beside a live gate run).

The curve record (`curve.json`; t1_metrics over every reference pixel centre, thin water
excluded, islands 4-connected, scored with `build_geo.py curve`):

| Checkpoint | Terms | Agreement | Coast p99 | Coast max | Islands of 65 px or more present |
|---|---|---|---|---|---|
| `model-64.npz` | 64 | 0.823311 | 65.00 px | >64 px (t1_metrics' cap) | 110 of 374 |
| `model-128.npz` | 128 | 0.925382 | 65.00 px | >64 px (t1_metrics' cap) | 111 of 374 |
| `model-256.npz` (coarse field) | 256 | 0.957532 | 65.00 px | >64 px (t1_metrics' cap) | 115 of 374 |
| `model-512.npz` | 512 | 0.972830 | 29.77 px | >64 px (t1_metrics' cap) | 111 of 374 |
| `model-1024.npz` | 1,024 | 0.982046 | 17.33 px | >64 px (t1_metrics' cap) | 136 of 374 |
| `model-1455.npz` | 1,455 | 0.985275 | 12.90 px | >64 px (t1_metrics' cap) | 144 of 374 |
| `model-1819.npz` | 1,819 | 0.986888 | 10.79 px | >64 px (t1_metrics' cap) | 157 of 374 |
| `model-2048.npz` | 2,048 | 0.987705 | 9.92 px | >64 px (t1_metrics' cap) | 168 of 374 |
| `model-2274.npz` | 2,274 | 0.988441 | 9.19 px | >64 px (t1_metrics' cap) | 172 of 374 |
| `model-2842.npz` | 2,842 | 0.989657 | 7.91 px | >64 px (t1_metrics' cap) | 184 of 374 |
| `model-3553.npz` | 3,553 | 0.990749 | 6.67 px | >64 px (t1_metrics' cap) | 196 of 374 |
| `model-4096.npz` (shipped) | 4,096 | 0.991420 | 6.04 px | >64 px (t1_metrics' cap) | 206 of 374 |
| `model-4441.npz` | 4,441 | 0.991796 | 5.70 px | >64 px (t1_metrics' cap) | 214 of 374 |
| `model-5551.npz` | 5,551 | 0.992673 | 4.74 px | >64 px (t1_metrics' cap) | 240 of 374 |
| `model-6939.npz` | 6,939 | 0.993478 | 4.30 px | 62.45 px | 260 of 374 |
| `model-8192.npz` | 8,192 | 0.994058 | 3.54 px | 62.45 px | 277 of 374 |

The shipped coast fit is the smallest checkpoint at or above T1's 0.991 (4,096 terms); the
coarse land field is the fit's 256-term checkpoint. numpy's `savez` stamps the zip
entries with the run's time, so a rerun writes other bytes holding the same arrays; the committed
files are the inputs of record.

## Emission

```
python tools/build_geo.py emit --map olde_world
```

`fit.json` names the checkpoint of each body; the tool writes
`terra-nauvis/prototypes/generated/geo_olde_world_v1.lua` (from `model-4096.npz`) and
`terra-nauvis/prototypes/generated/land_coarse_olde_world_v1.lua` (from `model-256.npz`) and
records terms, factors, row groups, input and output sha256 in `manifest.json`.

## Files and sha256

| File | sha256 | Source |
|---|---|---|
| `curve.json` | `c0cccf2eb2aea77d6ecfb071e85d5684f5de4998a7033cfa9a70519b98f3904c` | `build_geo.py curve` over the fit's work folder, copied by `adopt` |
| `model-4096.npz` | `bb0ab3adc7931212881690a2c97f1123d245817ea88485d1bee925685345b37a` | `build_geo.py fit` growth step of 4,096 terms, copied by `adopt` |
| `model-256.npz` | `c0d42bdc216603a5c99a1f50fb0720b39fda91e2b249d9df765d82b9fb31d9f5` | `build_geo.py fit` growth step of 256 terms, copied by `adopt` |
| `fit.json` | `6334d6e6e9df1d921463c1938d2b393a7cd5844fdb07a30f9630229225660aff` | `build_geo.py adopt`: which checkpoint each body uses |
| `manifest.json` | `9b574f6a9bfcac6a0c388b5beac59c7cada36985201c40999ba70e9d86e0640d` | `build_geo.py emit` |
