# Waterways: provenance

The inputs and the emission manifests of `tools/build_waterways.py` (ARCHITECTURE.md, "Build-time data
flow", step 3; milestone `waterways`). The T16 data-src row re-hashes every file of this folder against the
table below, and the gate's `ww_emit` row re-emits the generated sets from the inputs twice and
compares each byte for byte with the committed Lua.

## Source

Each `<map>.json` is written by `python tools/build_waterways.py import` from S4's path extraction
(`spikes/S4-rivers/results/<map>-features.json` in an earlier prototype on
the prototype branch, read with `git show`; TST-23) and from `data-src/approvals/approvals-data.json`:
APPROVALS 7's adopted rivers in priority order with their class, S4's nine straits, and the canals and
dams APPROVALS 6 puts on the map. S4's own commands, run from the Factorio workspace with numpy and
Pillow on the S8 reference rasters (S4 README): `python mod/spikes/S4-rivers/s4.py vectorise`.
Each `manifest-<map>.json` is written by `python tools/build_waterways.py emit` beside the generated
files it describes. A cut under the plan's waterway cut order is an edit to `<map>.json` (a river
removed from the bottom of its list, or a tolerance raised) regenerated in the same commit, with a
the design notes entry citing the timed run (design section 6.3).

| File | sha256 | Role |
|---|---|---|
| `atlantic.json` | `4f0afa291b5f20b3a9b6d7d404a9a7934c2a11f334a66ff3ad574795b802ae71` | tool input |
| `europe.json` | `b01dba527aa943241b9d2287ad26e9363efc0d98ecd5e4bea79b3811b12bb3d0` | tool input |
| `manifest-atlantic.json` | `ca6b84028a2eeab255b8d17e4d8ee7ffd4d634607ce9c137176a458992696552` | emission manifest |
| `manifest-europe.json` | `541aefa8e1398dbbee49009bcd91a58ae769473e86e4744a74999f04da0e2313` | emission manifest |
| `manifest-olde_world.json` | `4f5d39032f4fc9801133afe1ac7c0623f3136108813c79425c56480b4ee78b65` | emission manifest |
| `olde_world.json` | `6ad48c12e3cb798eb90c0ba236a0a165ca58120526aca1cd4fe43acaac2a9dd5` | tool input |
