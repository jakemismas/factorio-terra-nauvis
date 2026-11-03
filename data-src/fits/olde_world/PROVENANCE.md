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

## Lean stage (2026-11-02, the coast fit's cost; config.lua coast.split)

Past scale 6 the map reads a lean fit, a refit of the same reference to about 30 percent less Tile, so a scale 12 or
24 world generates faster; scales 1 to 6 keep `model-9360.npz`, from which the band fix's tables are built. Lean
growth starts from the base stage's 4,096-term step and is weighted toward Europe and the places players know (the
Thames, Calais, Brittany, the Cotentin, Jutland and the Danish straits, Venice and the Rhine by Koblenz, 64), then
regrows the reference islands of up to 400 px that `model-9360.npz` draws and the lean fit had lost (`--restore`,
weight 32), prunes 400 terms with a refit to the reference, regrows Europe's lost islands again, and grows 40 terms on
Brest, Crozon and Alderney, which the prune had smoothed away (weight 1,024). Work folders outside the repo
(`<work folder>/fits-coast2`):

```
W7="--region=-12,45,35,72,16 --region=172,180,60,68,6 --region=95,150,-12,46,2 --region=-20,52,-36,35,2 --region=112,180,-50,-10,2 --region=45,95,0,35,2 --region=45,180,46,80,2"
PL="--region=-0.5,2.0,51.0,52.0,64 --region=1.0,3.0,50.5,51.4,64 --region=-5.5,-2.5,47.3,49.0,64 --region=-2.5,-0.8,48.5,49.9,64 --region=7.5,13.5,54.0,58.0,64 --region=11.5,13.8,44.8,46.0,64 --region=6.5,8.5,49.8,51.0,64"
python tools/build_geo.py fit --map olde_world --work A --start-from data-src/fits/olde_world/model-4096.npz --nmax 8000 --through 8000 --stop-agreement 0.9999 --step-terms 4600,5000,5500,6000,6500,7000,7500 $W7 --footprint 6,32,0.4 --thrift
python tools/build_geo.py fit --map olde_world --work D --start-from A/model-5000.npz --nmax 6000 --through 6000 --stop-agreement 0.9999 --step-terms 5300,5600,5800 $W7 --region=-18,-15.5,12.5,16.5,16 $PL --footprint 6,32,0.4 --thrift
python tools/build_geo.py fit --map olde_world --work F --start-from D/model-5600.npz --nmax 6300 --through 6300 --stop-agreement 0.9999 --step-terms 5750,5900,6050,6200 $W7 --region=-18,-15.5,12.5,16.5,16 $PL --footprint 6,32,0.4 --thrift --restore=data-src/fits/olde_world/model-9360.npz,-180,180,-90,90,32
python tools/build_geo.py prune --map olde_world --checkpoint F/model-6050.npz --work G --drop 200 --cycles 2 $W7 --region=-18,-15.5,12.5,16.5,16 $PL
python tools/build_geo.py fit --map olde_world --work H --start-from G/model-5650.npz --nmax 5800 --through 5800 --stop-agreement 0.9999 --step-terms 5700,5750 $W7 --region=-18,-15.5,12.5,16.5,16 $PL --region=-5.3,-4.0,47.9,48.7,256 --footprint 6,32,0.4 --thrift --restore=data-src/fits/olde_world/model-9360.npz,-12,45,35,72,32
python tools/build_geo.py fit --map olde_world --work I --start-from H/model-5800.npz --nmax 5880 --through 5880 --stop-agreement 0.9999 --step-terms 5820,5840,5860 $W7 --region=-18,-15.5,12.5,16.5,16 $PL --region=-5.3,-4.0,47.9,48.7,1024 --region=-2.4,-2.0,49.6,49.8,1024 --footprint 6,32,0.4 --thrift
```

A stopped after its 6,000-term step and D after 6,000; F restored 170 islands and H 63. Each step's checkpoint, first
16 of its sha256: A 5,000 `94f780b67289f724`; D 5,600 `6a2dd2f37767a5da`; F 6,050 `03690fd45edae678`; G 5,650
`d392732ee673afee`; H 5,800 `64283c809f7fa48a`; I 5,840 `10b166e08a48297d` (`model-lean-5840.npz`).

`model-lean-5840.npz` against `model-9360.npz`, t1_metrics over every reference pixel centre (the earlier tables'
measure; boxes with only the box covered):

| Checkpoint | Terms | Tile (5 a term, 6.5 a factor, 4 a row group) | Agreement | Coast p99 | Islands of 65 px or more present | Europe box: agreement, p99, islands | Britain | Scandinavia | Mediterranean |
|---|---|---|---|---|---|---|---|---|---|
| `model-9360.npz` (scales 1 to 6) | 9,360 | 77,449 | 0.994454 | 3.81 px | 277 of 374 | 0.9893, 1.58 px, 73 of 77 | 13 of 13 | 31 of 34 | 22 of 25 |
| `model-lean-5840.npz` (past scale 6) | 5,840 | 55,477 | 0.992217 | 5.70 px | 267 of 374 | 0.9816, 3.54 px, 72 of 77 | 13 of 13 | 30 of 34 | 22 of 25 |

Inside the place boxes the lean fit keeps the fine fit's coast p99 against the reference: the Rhine by Koblenz 0.71
px, the Thames 1.57, Brittany 1.50, Jutland and the Danish straits 1.58, Venice 1.57 (`model-9360.npz`: 0.71, 1.50,
1.50, 1.58, 1.50). Components of the fit's class at pixel centres with no pixel of that class in the reference: 17
islets of 206 px and 29 lakes of 304 px (`model-9360.npz`: 25 of 135 px and 26 of 209 px).

## Regrowth stage (0.3.1, the coasts past scale 6; config.lua coast.next)

Past scale 6 a new world reads `model-next-10100.npz`, the fine fit `model-9360.npz` grown on: first on Istria, the
Kvarner islands and Dalmatia at weight 1,024, then a step on Europe's place boxes and the worst cells of the coast audit,
then on Crozon and the Rade de Brest at weight 4,096, then only on the reference islands of 3 to 400 px in Europe that
the fit drew under half of (`--restore=reference`, weight 256). Each stage keeps the fine fit's region weights and
footprint. Scales 1 to 6 keep `model-9360.npz` (the band fix's tables), and spawn and waterway inputs still read it.
Work folders outside the repo (`<work folder>/p31-c/fits`):

```
W7="--region=-12,45,35,72,16 --region=172,180,60,68,6 --region=95,150,-12,46,2 --region=-20,52,-36,35,2 --region=112,180,-50,-10,2 --region=45,95,0,35,2 --region=45,180,46,80,2"
HR="--region=13.3,18.3,42.4,45.8,1024"
python tools/build_geo.py fit --map olde_world --work ow-r1 --start-from data-src/fits/olde_world/model-9360.npz --nmax 9600 --through 9600 --stop-agreement 0.9999 --step-terms 9400,9440,9480,9520,9560 $W7 $HR --footprint 6,32,0.4 --thrift
EXT="the 28 worst cells of the audit off the 180 E edge at 256, the place boxes Zeeland, the Wadden, Denmark, the Limfjord, the Aegean, Sognefjord and Hardangerfjord at 512, four islands of 65 px or more at 256 (fits/r3_boxes.txt)"
python tools/build_geo.py fit --map olde_world --work ow-r3 --start-from ow-r1/model-9440.npz --nmax 9840 --through 9840 --stop-agreement 0.9999 --step-terms 9480,... $W7 $HR --region=-5.3,-4.0,47.9,48.7,1024 --region=-2.4,-2.0,49.6,49.8,1024 $EXT --footprint 6,32,0.4 --thrift
python tools/build_geo.py fit --map olde_world --work ow-r7 --start-from ow-r3/model-9480.npz --nmax 9540 --through 9540 --stop-agreement 0.9999 --step-terms 9500,9520 $W7 $HR --region=-4.8,-4.0,48.0,48.6,4096 $EXT --footprint 6,32,0.4 --thrift
python tools/build_geo.py fit --map olde_world --work ow-r8 --start-from ow-r7/model-9540.npz --nmax 10100 --through 10100 --stop-agreement 0.9999 --step-terms 9620,9700,9780,9860,9940,10020 $W7 $HR --region=-4.8,-4.0,48.0,48.6,4096 $EXT --footprint 6,32,0.4 --thrift --restore=reference,-12,45,35,72,256
```

ow-r1 ran through its 9,440-term step and ow-r3 through 9,480 (both stopped there). The emission adds
`terra-nauvis/prototypes/generated/geo_olde_world_v4.lua` (the `geo_next` body of `fit.json`).

## Emission

```
python tools/build_geo.py emit --map olde_world
```

`fit.json` names the checkpoint of each body (and the region fit's budget); the tool writes
`terra-nauvis/prototypes/generated/geo_olde_world_v2.lua` (from `model-9360.npz`),
`terra-nauvis/prototypes/generated/geo_olde_world_v3.lua` (from `model-lean-5840.npz`, the lean stage's `geo_lean` body) and
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
| `model-lean-5840.npz` | `10b166e08a48297dfa765b70d3235671d2ac38b32567498473aa9f73283fc4e1` | the lean stage's last growth step (I), copied: the `geo_lean` body, read past scale 6 |
| `model-next-10100.npz` | `a6268664795275bf06d86c71076767a4c9ece8596fb4c95e728c216c5529d667` | the regrowth stage's last growth step, copied: the `geo_next` body, read past scale 6 (0.3.1) |
| `fit.json` | `6c49bb8145e0826ba79063fa2c4ebf3f17e6d249b6beddd3a59b4433df1f8b1d` | `build_geo.py adopt --budget 9360 --file-version 2`: which checkpoint each body uses |
| `manifest.json` | `7ed63d472e1354cde3e461cf8b9c5e1d263d597ebc7923d8d9a1dd781f0c50d3` | `build_geo.py emit` |
