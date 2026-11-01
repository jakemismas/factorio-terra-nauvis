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
Atlantic's ten rivers beyond Europe are routed again at import through `RIVER_WAYPOINTS`, S4's method over
the same rasters, keeping S4's sea end: each carries its waypoints in `route`.
Each `manifest-<map>.json` is written by `python tools/build_waterways.py emit` beside the generated
files it describes. A cut under the plan's waterway cut order is an edit to `<map>.json` (a river
removed from the bottom of its list, or a tolerance raised) regenerated in the same commit, with a
the design notes entry citing the timed run (design section 6.3).

| File | sha256 | Role |
|---|---|---|
| `atlantic.json` | `347f46e4fe1865c5f178a5d06b2db223db33ea667566bdb43d204df6e04d8306` | tool input |
| `europe.json` | `fbc9c088c3f92b48d6164cd005dd96a448906c2734153ac72cb224f894440059` | tool input |
| `manifest-atlantic-past.json` | `fc5facaced5f34b0b544818d9f1d29305f4be9f5ed2b7d8021b1990ba4fa8665` | emission manifest |
| `manifest-atlantic.json` | `cb5cb6e20bff478f211faede20c97ab94c80b2d995b85231ef6840679b898e5e` | emission manifest |
| `manifest-europe-past.json` | `6327b8c45f6a28b8e2edafe48c6e9a11b23cc1d5e83d398f7a8bd69e4c1e4c9c` | emission manifest |
| `manifest-europe.json` | `2ceef505dd4c41b6b5fac451033d27eadc29a80f302b0655cdfe486be171118d` | emission manifest |
| `manifest-olde_world-past.json` | `9e42971f695b9e3b21cfd053a9fa131e886d3294bdb2afb936d26af7ad0b74df` | emission manifest |
| `manifest-olde_world.json` | `f02a5b781146c97c3a568959e265324e615b5750504203de5a8e15e3b67523c5` | emission manifest |
| `olde_world.json` | `878a785f8e48ee5447e76efac38274c3b98575d846e028609d75a9361a79305f` | tool input |
