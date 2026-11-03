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
2026-11-01): the Taurus, the Talysh and the Alborz, the Ethiopian Highlands, the Tian Shan, the Cascades and the
Sierra Nevada, the Great Dividing Range, and the Altai with the Gobi Altai. Each crest vertex names a summit, pass,
gorge or massif; its latitude, longitude and height are the published values as the worker's author knew them
(entered by hand, 2026-11-02), not re-read from a cited page, so a vertex may sit a few tenths of a degree off. A
vertex that names an area carries a representative height and `rep: true`. Heights set a ridge's width, its
highland reach and its section's snow verdict.

The second table draws cliffs through the union's chopped line field (straight cliff runs
under 50 tiles at scales 12 and 24), highland rocks and, where a section's highest peak clears its snow line, snow
with a narrow ragged rim. The cold field reads one snow verdict per crest piece, so a long range is split into
sections at its real passes and gorges. A row with `cold: false` (the Ethiopian Highlands: Africa holds no snow)
adds no cold field. `tools/build_ranges.py emit2` writes `prototypes/tables/ranges_v2.lua` from this file and
records its sha256; the static ranges row re-emits it.
