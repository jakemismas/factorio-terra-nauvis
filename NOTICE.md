# Notices

Terra Nauvis
Copyright (C) 2026 Jake Mismas

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License version 3 as published by the Free Software Foundation. It comes with no
warranty. See LICENSE. This covers the whole repository except the items under "Not covered by the
GPL" below.

## Modified work

Terra Nauvis is a modified work based on EarthMaps by HySpeed
(https://github.com/HySpeed/EarthMaps), GPLv3, version 2.1.2, commit 23c647b8. Modified by Jake
Mismas from 2026-10-26 to 2026-11-01: EarthMaps' world data was decoded into rasters, its rivers were
traced, and its coastlines were refitted as noise expressions and exact-coast tables. EarthMaps' own
thanks go to TheOddler, OARC, MojoD, Nexela, jmatya and its testers. EarthMaps descends from Factorio
World by TheOddler (GPLv3).

City positions come from EarthMaps, which took them from Mapcarta. They are approximate.

## Third-party data

Ecoregions: forest and marsh outlines, centres and areas, and the islets the EarthMaps raster lacks,
are derived from RESOLVE Ecoregions 2017. Dinerstein, E. et al. (2017), An Ecoregion-Based Approach to
Protecting Half the Terrestrial Realm, BioScience 67(6), 534-545,
https://doi.org/10.1093/biosci/bix014. Data: https://ecoregions.appspot.com/, licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Changed: polygons simplified, centroids and areas
computed, islets rasterised to the map grid.

OpenStreetMap: the Suez, Kiel and Corinth canal routes and two points at the Strait of Gibraltar use
data (c) OpenStreetMap contributors, available under the Open Database License
(https://www.openstreetmap.org/copyright). Changed: simplified and snapped to the map grid.

Wikipedia: place coordinates, lengths, heights, areas, water depths and some deposit figures were
read from Wikipedia articles, cited by URL or by name in docs/plan/research/R7b-geography.json (where some links pin a
revision) and R7a-hotspots.json, data-src/hotspots/deposits-research.md and .json,
data-src/approvals/approvals-data.json and tests/oracle/. Any Wikipedia text in those files is
available under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).

Ore hotspots: places and sizes are facts, cited per row in data-src/hotspots/deposits-research.md. Its
country tables quote the USGS Mineral Commodity Summaries 2026 data release, a United States government
work in the public domain. Figures credited to Global Energy Monitor are cited to its pages.

## Not covered by the GPL

Factorio is (c) Wube Software Ltd. Noise expression texts in
terra-nauvis/prototypes/tables/vanilla.lua come from the Factorio base game. They belong to Wube
Software, are not offered under the GPL, and are included under the Factorio Terms of Service
(https://factorio.com/terms-of-service), which let a mod include adaptations of Factorio assets. Wube
Software keeps all rights and may ask for their removal. Screenshots in this repository show Factorio's
interface and art, which are also Wube Software's.

## Other mods

Terra Nauvis can work beside Alien Biomes by Earendel, Cargo Ships, Cargo Ships: Oil Rig and Resource
Spawner Overhaul. The mod contains none of their content and refers to their prototypes by name only.

## Trademarks

Factorio is a trademark of Wube Software Ltd. Terra Nauvis is an unofficial mod, not made or endorsed
by Wube Software.
