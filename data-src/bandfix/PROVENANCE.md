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
| `manifest-atlantic.json` | `45fdaeefed9439e661ffc9fc5b23b5990c2340b20ec3b4c7a5b8f5bb44963ef9` | emission manifest |
| `manifest-europe.json` | `ad2a0a4e2f8ba735f63dfa8b83ef3bf024a94c84f3e0135e60b4c41093635da1` | emission manifest |
| `manifest-olde_world.json` | `aa399d180df1993f9abaa77b30bb1915981dd9e230159e3dd527a3c83c567b77` | emission manifest |
| `islets-atlantic.json` | `0e73d0d8c88335b68f62c55d536e03be8225a9ddf2a124f2e9eb62bd46e10c04` | islets the raster lacks (`tools/build_islets.py`) |
| `islets-europe.json` | `2af133292cf312976dfaa0d1c3d3f669e0eda9ae8871a7110d6945a740fd90db` | islets the raster lacks (`tools/build_islets.py`) |
| `islets-olde_world.json` | `5838e39dbc88ebca0425e4c2f5704c178337b280865cd99e648f99fd35c979f3` | islets the raster lacks (`tools/build_islets.py`) |

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

2026-10-30, a development branch: the tables read the reference through `build_geo.py bandfix_classes`. Thin water of the
ocean class within `bandfix.channel_px` pixels of open water along thin water counts as water, and K holds every
scored pixel that touches the other class, because the handler's write band narrowed to about a fifth of a pixel.
`islets-<map>.json` lists the pixels of islands the reference raster lacks, written by `python tools/build_islets.py
--map <map> --shp <folder>/Ecoregions2017.shp` from RESOLVE Ecoregions 2017 (Dinerstein et al., CC BY 4.0,
https://storage.googleapis.com/teow2016/Ecoregions2017.zip, 149,248,653 bytes, the file research R7b downloaded, sha256
below): polygons registered to the raster block by block, in open sea with a clear pixel between them and all
reference land. Only the K+ tables read these lists; the reference rasters and the coast fit are unchanged.
`Ecoregions2017.zip` sha256 `be36d6209e443038d02e309f0447c6e7f2a62f5fe60c605ffe90d064952f2a60`.
