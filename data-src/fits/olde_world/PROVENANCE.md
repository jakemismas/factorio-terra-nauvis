# Old World coast fit: provenance

The checkpoints here are the inputs of `tools/build_geo.py` for Old World (ARCHITECTURE.md,
"Build-time data flow", step 2; milestone `olde-world-atlantic`). The T16 data-src row re-hashes every
file of
this folder against the table below, and the gate's `geo_emit` row re-emits the two generated bodies
from them twice and compares each byte for byte with the committed Lua.

## Source

Two stages of one fit lineage, both made with `tools/build_geo.py fit` (S1-fit's fitter ported
operation for operation; the design notes, olde-world-atlantic, the fitter entry) from the repo root
with Python 3.13, numpy 2.5.1 and Pillow 12.2.0, each work folder outside the repo.

Stage base (design experiment 5): Old World's first native-resolution fit, unweighted, which
shipped its 4,096-term step until 2026-10-30:

```
python tools/build_geo.py fit --map olde_world --work <work folder>/fits-olde-world-atlantic/olde_world
python tools/build_geo.py curve --map olde_world --work <work folder>/fits-olde-world-atlantic/olde_world
```

Target: the reference signed distance soft-saturated as `4 * tanh(sdf / 4)` px, thin water
filled as land with weight 0; tents on dyadic grids from 1 to 1024 px (K 10); greedy selection
growing 1.25 times per step from 64 terms; one-sided refit with margin 1 px (lam 0.0001, 4 Newton
steps, at most 150 CG iterations). Peak working set 1,732 MB; fit time 0.67 h over 29 growth steps.
Spread over Eurasia, Africa and Australia, its 4,096 terms left Britain, Ireland, the Channel,
Denmark and the Baltic as blobs: 851 of them sit in the Europe box below and 107 in the Britain box.

Stage region (2026-10-30, coastline report): the same fit continued from the base stage's
shipped `model-4096.npz` with the Europe box (longitude -12 to 45, latitude 35 to 72 in the map's
own frame) weighted 16 times in the hinge objective, the refits and the greedy scores, so the new
terms go to Europe's coasts, through 8,192 terms (the Europe map's own budget):

```
python tools/build_geo.py fit --map olde_world --work <work folder>/fits-ow-coast/ws4096-w16 --nmax 8192 --region=-12,45,35,72,16 --start-from data-src/fits/olde_world/model-4096.npz
python tools/build_geo.py curve --map olde_world --work <work folder>/fits-ow-coast/ws4096-w16
python tools/build_geo.py adopt --map olde_world --work <work folder>/fits-ow-coast/ws4096-w16 --budget 8192
```

Peak working set 1,939 MB; fit time 3.1 min over 4 growth steps. With the region off, two growth
steps of the unweighted fit reproduce the base stage's `model-64.npz` and `model-80.npz` array for
array. `adopt --budget` ships the largest region step within the budget and keeps the coarse land
field (the base stage's 256-term step, byte for byte), and `curve.json` holds the whole lineage:
the base stage's points through 4,096 terms (stage `base`, their params in `base_params`) and the
region steps (stage `region`). The fit check (earth_test.py `region_fit_findings`) holds a
region-weighted fit to the global bar and to its budget instead of the smallest-ships rule.

The curve record (`curve.json`; t1_metrics over every reference pixel centre, thin water excluded,
islands 4-connected, scored with `build_geo.py curve`), the base stage's steps abridged:

| Checkpoint | Stage | Terms | Agreement | Coast p99 | Coast max | Islands of 65 px or more present |
|---|---|---|---|---|---|---|
| `model-256.npz` (coarse field) | base | 256 | 0.957532 | 65.00 px | >64 px (t1_metrics' cap) | 115 of 374 |
| `model-1024.npz` | base | 1,024 | 0.982046 | 17.33 px | >64 px (t1_metrics' cap) | 136 of 374 |
| `model-2048.npz` | base | 2,048 | 0.987705 | 9.92 px | >64 px (t1_metrics' cap) | 168 of 374 |
| `model-4096.npz` (start) | base | 4,096 | 0.991420 | 6.04 px | >64 px (t1_metrics' cap) | 206 of 374 |
| `model-4441.npz` | region | 4,441 | 0.991674 | 6.04 px | >64 px (t1_metrics' cap) | 212 of 374 |
| `model-5551.npz` | region | 5,551 | 0.992114 | 6.04 px | >64 px (t1_metrics' cap) | 228 of 374 |
| `model-6939.npz` | region | 6,939 | 0.992465 | 6.04 px | >64 px (t1_metrics' cap) | 242 of 374 |
| `model-8192.npz` (shipped) | region | 8,192 | 0.992673 | 6.04 px | >64 px (t1_metrics' cap) | 246 of 374 |

The same t1_metrics inside the boxes (`crop_and_evaluate` with only the box covered; boxes in the
map's frame: Europe as above, Britain and Ireland longitude -11 to 2.5 and latitude 49.5 to 61,
the Channel and Benelux -6 to 8 and 48 to 54, Denmark and the southern Baltic 7 to 25 and 53 to
60, central Europe 4 to 18 and 47 to 53):

| Checkpoint | Terms in the Europe box | Europe | Britain | Channel | Denmark, Baltic | Central |
|---|---|---|---|---|---|---|
| base 4,096 | 851 | 0.97267, p99 5.52, max 31.66 px | 0.96508, p99 5.70, max 10.50 px | 0.96554, max 10.51 px | 0.94188, max 14.58 px | 0.99598, max 5.70 px |
| region 6,939 | 3,694 | 0.98560, p99 2.55, max 12.75 px | 0.98097, p99 2.55, max 8.63 px | 0.98299, max 8.63 px | 0.97119, max 9.50 px | 0.99762, max 4.74 px |
| region 8,192 | 4,947 | 0.98808, p99 2.12, max 7.38 px | 0.98442, p99 2.12, max 3.54 px | 0.98597, max 3.54 px | 0.97652, max 5.50 px | 0.99791, max 3.54 px |

The 8,192-term budget ships: it is the smallest step whose worst coast error in Britain and the
Channel is under 4 px (24 tiles at scale 6); 6,939 still leaves 8.6 px bulges there. Elsewhere the
map keeps the base stage's 4,096-term coast (global p99 6.04 px either way). Tile complexity of
the Old World Map type entry (the game's `--verbose`, elevation-only `--map-gen-settings`): 51,449
with the base stage's 4,096 terms, 85,883 with the region fit's 8,192 (Europe's entry 82,784).

Stage swap (2026-10-30, the refit, tn_geo 19): greedy growth never takes a term back, so a term its later
neighbours made redundant keeps its Tile, and Europe held 4,946 of the 8,192 terms while the rest of the map stayed at
the base stage's coast, which the new-game preview shows raw. Each round drops the terms with the least hinge
objective per Tile freed (`build_geo.py prune`, 300 terms a cycle with a refit between) and regrows from there with
`--thrift`, which ranks a term by gain per Tile: a term on a column and a row its level already reads costs 5 Tile,
one on fresh ones about 22. `--hold` keeps Europe's weight of 16 in the refits, so that coast stays where it is, while
new terms reach it at a share of that weight, and `--footprint 6,32,0.4` weighs the waterway footprints at scale 6,
where the band fix stays out and a player sees the raw fit. From `model-8192.npz`, work folders outside the repo:

```
python tools/build_geo.py prune --map olde_world --checkpoint data-src/fits/olde_world/model-8192.npz --work p1 --drop 300 --cycles 3 --region=-12,45,35,72,16
W6="--region=-12,45,35,72,16 --region=172,180,60,68,6 --region=95,150,-12,46,2 --region=-20,52,-36,35,2 --region=112,180,-50,-10,2 --region=45,95,0,35,2"
W7="$W6 --region=45,180,46,80,2"
G="--stop-agreement 0.9999 --hold=-12,45,35,72,0.35 --hold=-11,25,47,61,0.5 --footprint 6,32,0.4 --thrift"
python tools/build_geo.py fit --map olde_world --work g1 --start-from p1/model-7292.npz --nmax 9200 --step-terms 7500,7700,7900,8100,8300,8400,8500,8600,8700,8800,8900,9000,9100 $W6 $G
python tools/build_geo.py prune --map olde_world --checkpoint g1/model-9000.npz --work p2 --drop 300 --cycles 2 $W6
python tools/build_geo.py fit --map olde_world --work g2 --start-from p2/model-8400.npz --nmax 9200 --step-terms 8500,8600,8700,8800,8900,9000,9100 $W7 $G
python tools/build_geo.py prune --map olde_world --checkpoint g2/model-9200.npz --work p3 --drop 300 --cycles 3 $W7
python tools/build_geo.py fit --map olde_world --work g3 --start-from p3/model-8600.npz --nmax 9500 --step-terms 8700,8800,8900,9000,9100,9200,9300,9400 $W7 $G
# three times more, each from the last step of the one before, into p4 and g4, p5 and g5, p6 and g6:
python tools/build_geo.py prune --map olde_world --checkpoint gN/model-9500.npz --work pM --drop 300 --cycles 3 $W7
python tools/build_geo.py fit --map olde_world --work gM --start-from pM/model-8600.npz --nmax 9500 --step-terms 8700,8800,8900,9000,9100,9200,9300,9400 $W7 $G
python tools/build_geo.py curve --map olde_world --work g6 --only 9300
python tools/build_geo.py adopt --map olde_world --work g6 --budget 9300 --file-version 2
python tools/build_geo.py fit --map olde_world --work g7 --start-from data-src/fits/olde_world/model-9300.npz --nmax 9400 --step-terms 9320,9340,9360,9380 $W7 --stop-agreement 0.9999 --hold=-12,45,35,72,0.35 --hold=-11,25,47,61,0.5 --footprint 6,32,0.4 --thrift --restore=data-src/fits/olde_world/model-8192.npz,-12,45,35,72,64
python tools/build_geo.py curve --map olde_world --work g7 --only 9360
python tools/build_geo.py adopt --map olde_world --work g7 --budget 9360 --file-version 2
```

The last stage, `--restore`, grows only on the 44 Europe islands `model-8192.npz` draws and `model-9300.npz` does not, Elba,
Ikaria and Belle Ile among them: the prune takes a speck whose tent has little objective and private factors, while every
pixel count improves.

Each step's checkpoint, first 16 of its sha256: p1 7,292 `cc110b8876b7c4d6`; g1 9,000 `1ad04678b6ba58ef`; p2 8,400
`0c5d5a57f689bbeb`; g2 9,200 `5bfcb9ca4599097b`; p3 8,600 `bcee52ab74029412`; g3 9,500 `306174927aad0360`; p4 8,600
`1d2cae7129aa09e0`; g4 9,500 `4757c4ee2b451246`; p5 8,600 `4a3077f173cffbc1`; g5 9,500 `4eccd28a990bc5ad`; p6 8,600
`0967e1504e5b3179`; g6 9,300 (`model-9300.npz`, the last stage's start); g7 9,360 (`model-9360.npz`). The curve holds the
earlier stages through 9,300 terms as stage `base` and the last growth as stage `region`.

`model-9360.npz` by t1_metrics: agreement 0.994454, coast p99 3.8079 px against 6.04, coast max
47.5 px against over 64, islands of 65 px or more present 277 of 374 against 246. It reads 77,449 Tile by the
measured costs (5 a term, 6.5 a factor, 4 a row group) against `model-8192.npz`'s 77,018: 3,778 factors serve 9,360 terms
against 4,404 serving 8,192. `geo_olde_world_v1.lua`, `model-8192.npz` and `model-4096.npz` stay for the worlds of tn_geo
18 and this lineage.

## Emission

```
python tools/build_geo.py emit --map olde_world
```

`fit.json` names the checkpoint of each body (and the region fit's budget); the tool writes
`terra-nauvis/prototypes/generated/geo_olde_world_v2.lua` (from `model-9360.npz`) and
`terra-nauvis/prototypes/generated/land_coarse_olde_world_v1.lua` (from `model-256.npz`, unchanged)
and records terms, factors, row groups, input and output sha256 in `manifest.json`. numpy's
`savez` stamps the zip entries with the run's time, so a rerun writes other bytes holding the same
arrays; the committed files are the inputs of record.

## Files and sha256

| File | sha256 | Source |
|---|---|---|
| `curve.json` | `b2fa20001aadd008324a9ab88e8a2a9edf23694e9f9ce663c0f2fc283c946dd6` | `build_geo.py curve` over the stages' work folders, merged by `adopt --budget` |
| `model-9360.npz` | `9ced876567416c84859469ec5fe6a470f9e9b5761b3566b5b292d301580d0496` | the island stage's growth step of 9,360 terms, copied by `adopt` |
| `model-9300.npz` | `4537758e06ed23be31d6e991ee836380e4bdba84e7a89c068e610b28d022cc57` | the swap stage's growth step of 9,300 terms: the island stage's `--start-from` |
| `model-8192.npz` | `f28272b9d304191e074c25db1878fceb8057e37c876244535fa429a7817e594e` | the region stage's growth step of 8,192 terms: the fit of tn_geo 18, which `geo_olde_world_v1.lua` holds, and the island stage's `--restore` |
| `model-4096.npz` | `bb0ab3adc7931212881690a2c97f1123d245817ea88485d1bee925685345b37a` | the base stage's growth step of 4,096 terms: the region stage's `--start-from` |
| `model-256.npz` | `c0d42bdc216603a5c99a1f50fb0720b39fda91e2b249d9df765d82b9fb31d9f5` | the base stage's growth step of 256 terms: the coarse land field |
| `fit.json` | `2bb8d7c8d3e598a4b027bc8b03fbc41c78bcf063eab2d76b3c39dad09e4e25fa` | `build_geo.py adopt --budget 9360 --file-version 2`: which checkpoint each body uses |
| `manifest.json` | `008e16fe968c98d1b0b656d4c63c619936ffc90133c9097a03594b39c39cfe85` | `build_geo.py emit` |
