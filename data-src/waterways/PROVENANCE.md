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
| `atlantic.json` | `bfb20f2f98282401f8fa72e7080877579d687c20dbc4fa53f60eec68d6b5f938` | tool input |
| `europe.json` | `fbc9c088c3f92b48d6164cd005dd96a448906c2734153ac72cb224f894440059` | tool input |
| `manifest-atlantic.json` | `9faa823930378123700e0f2cd1c6fbe0248ef3302bc160eeb32395c61a0492d4` | emission manifest |
| `manifest-europe.json` | `f505b32c6443b5125babce3571e945343ef12f67971a548de8376612ee66cf3b` | emission manifest |
| `manifest-olde_world.json` | `a4e7e29ac1f973cb462cc035cf14c275f7faea97a71fe3d216c51d2ed56f7061` | emission manifest |
| `olde_world.json` | `3ebeeb17b20c28ff38f195591783e53910332b4f41fa57fcb60a5e421f8fe66a` | tool input |
