# Ridge vertex heights: provenance

`vertex-heights.json` gives every crest vertex of the design notes a height in
metres, so a ridge can run wider where the real mountain is taller. The repo
holds no elevation raster: the EarthMaps rasters carry land classes only, the fit rasters land and
water, and R7b one highest point per range. So the values here are the published elevations of the
peaks and passes R7b's vertices name, entered by hand and rounded to the metre. A vertex that names
an area rather than a summit (a plateau, massif, gorge, cape or peninsula) has a representative
height. They only set a ridge's width, so a few metres either way change nothing a player can see.

`tools/build_ranges.py` checks one value per vertex and that no vertex tops R7b's
`highest_elevation_m` by more than 1 m, copies them into `prototypes/tables/ranges.lua`, and records this
file's sha256 in the table's header.
