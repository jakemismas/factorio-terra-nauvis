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
| `manifest-atlantic.json` | `1afcedc50768cd2d66f3f7fa88dd91b637404a5477d8dc7a7123fa8f212e7400` | emission manifest |
| `manifest-europe.json` | `605b1434669c36db237db2df8d5776b72ac43311b3b22bd5baf13559264c73de` | emission manifest |
| `manifest-olde_world.json` | `806db59d428b7d0aa0580707f3a1809296a34903da2184b3a5a155462641980e` | emission manifest |
| `olde_world.json` | `6ad48c12e3cb798eb90c0ba236a0a165ca58120526aca1cd4fe43acaac2a9dd5` | tool input |
