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

## Swap stage

2026-10-30, the refit, tn_geo 20: the same method as Old World's swap stage (its PROVENANCE.md), prune with
`build_geo.py prune` and regrow with `--thrift`, on the coasts the new-game preview showed as computer-made shapes:
Britain to Denmark 6, the Gulf of Guayaquil 16, the Bahamas 8, the Isle of Man 16, and the Americas 2. From
`model-8674.npz`, work folders outside the repo:

```
R4="--region=-11,16,49,61,6 --region=-84,-76,-7,2,16 --region=-83,-70,19,29,8 --region=-6,-3.5,53.5,55,16"
R5="--region=-170,-30,-60,80,2 $R4"
python tools/build_geo.py prune --map atlantic --checkpoint data-src/fits/atlantic/model-8674.npz --work p1 --drop 250 --cycles 4 $R4
python tools/build_geo.py fit --map atlantic --work g1 --start-from p1/model-8174.npz --stop-agreement 0.9999 --nmax 10200 --step-terms 8400,8600,8800,9000,9250,9500,9700,9900,10000,10100 $R5 --hold=-11,16,49,61,0.8 --hold=-84,-76,-7,2,0.5 --hold=-83,-70,19,29,0.75 --hold=-6,-3.5,53.5,55,0.5 --thrift
python tools/build_geo.py prune --map atlantic --checkpoint g1/model-10200.npz --work p2 --drop 300 --cycles 3 $R5
python tools/build_geo.py fit --map atlantic --work g2 --start-from p2/model-9300.npz --stop-agreement 0.9999 --nmax 10400 --step-terms 9400,9500,9600,9700,9800,9900,10000,10100,10200,10300 $R5 --hold=-84,-76,-7,2,0.5 --hold=-6,-3.5,53.5,55,0.5 --thrift
# three rounds, each from the last step of the one before, then a fourth with no --hold:
python tools/build_geo.py prune --map atlantic --checkpoint gN/model-10400.npz --work pM --drop 300 --cycles 3 $R5
python tools/build_geo.py fit --map atlantic --work gM --start-from pM/model-9500.npz --stop-agreement 0.9999 --nmax 10400 --step-terms 9600,9700,9800,9900,10000,10100,10200,10300 $R5 --hold=-84,-76,-7,2,0.5 --hold=-6,-3.5,53.5,55,0.5 --thrift
python tools/build_geo.py curve --map atlantic --work g6 --only 10400
python tools/build_geo.py adopt --map atlantic --work g6 --budget 10400 --file-version 2
```

Each step's checkpoint, first 16 of its sha256: p1 8,174 `5ae1eca2f5308865`; g1 10,200 `93068a80c28fe510`; p2 9,300
`5ed42546b06b8b57`; g2 10,400 `44a06276cc17e8f1`; p3 9,500 `e499e461f4481abc`; g3 10,400 `5c8275f8db3b500c`; p4 9,500
`c831533bea6bc3b5`; g4 10,400 `e35a20f9cdd82512`; p5 9,500 `51265d4189fe4edf`; g5 10,400 `5d4ebec5fc455de1`; p6 9,500
`727fccd7c3a0d383` (`model-9500.npz`, the shipped fit's start); g6 10,400 (`model-10400.npz`).

`model-10400.npz` by t1_metrics: agreement 0.991931, coast p99 5.1478 px against 5.5, coast max
54.4 px against 54.7, islands of 65 px or more present 413 of 697 against 397. It reads 83,776 Tile by the
measured costs (5 a term, 6.5 a factor, 4 a row group) against `model-8674.npz`'s 79,360. `geo_atlantic_v1.lua` and
`model-8674.npz` stay for the worlds of tn_geo 17.

## Emission

```
python tools/build_geo.py emit --map atlantic
```

`fit.json` names the checkpoint of each body; the tool writes
`terra-nauvis/prototypes/generated/geo_atlantic_v2.lua` (from `model-10400.npz`) and
`terra-nauvis/prototypes/generated/land_coarse_atlantic_v1.lua` (from `model-256.npz`) and
records terms, factors, row groups, input and output sha256 in `manifest.json`.

## Files and sha256

| File | sha256 | Source |
|---|---|---|
| `curve.json` | `614b80086a892e7a00915b52f6ae61a05320852868cbed572b566c4b0d35799a` | `build_geo.py curve` over the fit's work folders, merged by `adopt --budget` |
| `model-10400.npz` | `ec0a149c949a03d8f259986dae3dd70215a029298a9f674bba7836ef030c50d2` | the swap stage's growth step of 10,400 terms, copied by `adopt` |
| `model-9500.npz` | `727fccd7c3a0d3832fd6e2c0fc7ba1adf011cc8424df2d6a260f57fdbf82db1b` | the last prune of the swap stage: the shipped fit's `--start-from` |
| `model-8674.npz` | `9ff17ccafb972b0d1e6c40d00dc193d8797f32dd21634c6d3c7b13f7f2280fe9` | `build_geo.py fit` growth step of 8,674 terms: the fit of tn_geo 17, which `geo_atlantic_v1.lua` holds |
| `model-256.npz` | `a793e2c60335f0b55a05641426be0f105a1c8feff09d346f4719da9c2ce6de90` | `build_geo.py fit` growth step of 256 terms, copied by `adopt` |
| `fit.json` | `6e22ece51c52bd09bcf0671ba974cac8459d168bf4328fa1dc4dccaed83f9c6d` | `build_geo.py adopt --budget 10400 --file-version 2`: which checkpoint each body uses |
| `manifest.json` | `3f6ec8867de451072acd5c65e4626acd0b18bf47d90b52e8e707458647ea8ee6` | `build_geo.py emit` |
