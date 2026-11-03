# Ridge vertex heights: provenance

`vertex-heights.json` gives every crest vertex of the design notes a height in
metres, so a ridge can run wider where the real mountain is taller (2026-10-30 10:21). The repo
holds no elevation raster: the EarthMaps rasters carry land classes only, the fit rasters land and
water, and R7b one highest point per range. So the values here are the published elevations of the
peaks and passes R7b's vertices name, entered by hand and rounded to the metre. A vertex that names
an area rather than a summit (a plateau, massif, gorge, cape or peninsula) has a representative
height. They only set a ridge's width, so a few metres either way change nothing a player can see.

`tools/build_ranges.py` checks one value per vertex and that no vertex tops R7b's
`highest_elevation_m` by more than 1 m, copies them into `prototypes/tables/ranges.lua`, and records this
file's sha256 in the table's header.

## ranges-v2.json (0.3.0, the second ranges table)

`ranges-v2.json` holds ranges the released table lacked (Earth mods recommendation 4, approved by the maintainer on
2026-11-01): the central Alborz, the Tian Shan (four sections), the Cascades (four sections) and the Altai (two
sections). Each crest vertex names a summit, pass, gorge or massif; its latitude, longitude and height are the
published values as the worker's author knew them (entered by hand, 2026-11-02), not re-read from a cited page, so a
vertex may sit a few tenths of a degree off. A vertex that names an area carries a representative height and
`rep: true`. Heights set a section's snow verdict and its highland reach.

The second table draws snow, a narrow grey rim and highland rocks, and no cliffs. The cold field reads one snow
verdict per crest piece, from the piece's highest vertex, so a long range is split into sections at its real passes
and gorges, and only sections whose highest peak clears their snow line are listed. The Taurus, the Talysh, the
eastern Alborz, the Ethiopian Highlands, the Great Dividing Range, the Sierra Nevada, the southern Oregon and Lassen
Cascades and the Gobi Altai were built and dropped: without cliffs or snow they drew highland rocks alone. A row may
carry `cold: false` to add no cold field. `tools/build_ranges.py emit2` writes `prototypes/tables/ranges_v2.lua`
from this file and records its sha256; the static ranges row re-emits it.
