# Exact coastlines: provenance

The emission manifests of `tools/build_geo.py emit --map <map> --bandfix` (milestone `coast-band-fix`;
the design notes section 13; ARCHITECTURE.md, "Build-time data flow"). Each manifest records the inputs
its K+ tables were built from (the map's shipped coast fit checkpoint from `data-src/fits/<map>/fit.json`,
the reference rasters `data-src/earthmaps/<map>-land.png` and `-thinwater.png`, each scale's waterway
manifest `data-src/waterways/manifest-<map>.json` and config.lua's `bandfix` group), the generated
files with their sha256 (`terra-nauvis/scripts/generated/bandfix_<map>_v1.lua`, the map's K+ table, and
`bandfix_<map>_s<k>_v1.lua`, each scale's waterway masks over it), and per scale the pricing: S12's
measures (`s12_rule`: the share of the map's chunks the band rule corrects and the tiles per corrected
chunk, mean, p95 and max, with the coast fit alone deciding) beside the shipped rule's (`shipped_rule`:
K pixels outside the scale's masks, fill pixels whole) and the chunks the handler reads
(`chunks_read`). The plan's T1 (offline, first) reads scales 1, 3 and 6. The T16 data-src row re-hashes
every file of this folder against the table below; `build_geo.py check --map <map> --bandfix`
re-emits the tables twice and compares each byte for byte with the committed files.

| File | sha256 | Role |
|---|---|---|
| `manifest-atlantic.json` | `4fd2737cf5fb93d48915e64fdc618dff486c91c5e98111faeb21fb6d52359d38` | emission manifest |
| `manifest-europe.json` | `1a85ff2fcc9f04cda214f94b7c2864ecd0f1454a0d08ab876e4b59cd1ce908c7` | emission manifest |
| `manifest-olde_world.json` | `9c89e3840a841a3bda7196bfe206ab5245e72f404c2f3e0fa1d2a0205ae89be5` | emission manifest |

2026-10-30: `bandfix.tables` gained Europe's geography 14 and Old World's 16 and 18 (the soft-edge
versions; the handler skips the edge band on them). The emitter reads that list only to check the
map's membership, so the tables are unchanged: both manifests' `bandfix_config_sha256` was re-stamped
to the new group (the old digest recomputes exactly from the new group with the old lists).

2026-10-30, a development branch: Old World's and Atlantic's tables are built with the coast warp's reach in place
of the lattice detail's bound (`inputs.warp_reach_px`), `bandfix.tables` lists each map's one geography,
and Atlantic has tables. A manifest's `bandfix_config_sha256` was re-stamped after handler-only keys of the
group moved (`maps`, `new_deep`, `smooth`, `ground_rings`), which feed no table. The shipped rule's pricing
still counts S12's band, not the blurred write rule, so it is an estimate. After a change that moves
waterways only, `build_geo.py emit --map <map> --bandfix --masks-only` rewrites the mask tables from the
committed K+ table, byte-identical to a full emission.
