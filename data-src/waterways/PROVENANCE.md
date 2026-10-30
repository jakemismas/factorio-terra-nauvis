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
| `manifest-atlantic.json` | `b259bb8b8dded0623c6dedc735f4c1b98c28846c9f4b36d22aaec3b94361e51b` | emission manifest |
| `manifest-europe.json` | `36e19a04fbb5b7e306d0662b562a64b1ad428567f803f51767180c8268436c52` | emission manifest |
| `manifest-olde_world.json` | `7b9bc058a6be2e4ae9f8eeb1e8507c00b9936c32d8eae4f1deaad4ca124a9499` | emission manifest |
| `olde_world.json` | `3ebeeb17b20c28ff38f195591783e53910332b4f41fa57fcb60a5e421f8fe66a` | tool input |
