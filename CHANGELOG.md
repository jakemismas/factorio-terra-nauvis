# Changelog

All notable changes to terra-nauvis are documented in this file. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.2] - 2026-10-31

A patch for a defect 0.1.1 introduced. It only reaches you if you remove or disable Terra Nauvis in a played world and later add it back. Terrain does not change.

### Fixed

- Removing or disabling Terra Nauvis in a played world and adding it back no longer rewrites land within about 190 tiles of the spawn or destroys buildings there. 0.1.1 did this on Atlantic and Old World worlds with Exact coastlines on, with no warning: a test world on Old World lost 78 of 400 landfill tiles and 25 of 133 chests. What it already destroyed does not come back, so load a save from before you added the mod back.
- The same steps no longer add start ore to a played world. This affected 0.1.0 and 0.1.1 on every Terra Nauvis map.
- A start whose spawn tile lies in a river now gets the start ore guarantee. Before, such a start placed no ore patch, as at London on Atlantic at map scale 3. This applies to new worlds.

### Changed

- A tag run of the static rows compares with the earlier releases alone, so main moving on cannot refuse a good tag.

## [0.1.1] - 2026-10-30

A patch for existing and new worlds. Terrain does not change: a mid-game save made on 0.1.0 and loaded on this build shows 0 of 3,694 new chunks differing.

### Fixed

- The game no longer fails to load when an Alien Biomes tile group that Terra Nauvis adopts is disabled.
- The start ore guarantee counts land after Exact coastlines has written it, so a river cannot cut a start off from an ore it counted. This applies to new worlds.
- The Exact coastlines drift line no longer says a Map type world follows the setting.

### Changed

- Corrected the Atlantic preset, tooltips and README where they overclaimed.
- `release.yml` runs the static rows, so a commit CI rejects cannot ship.

## [0.1.0] - 2026-10-30

First release of Terra Nauvis, for Factorio 2.1. This summary is the whole release at a glance; the
`### Added` and `### Changed` entries under it are the build record, kept as written. Install, settings,
compatibility and known limits are in README.md, and the changelog players see in game is
`terra-nauvis/changelog.txt`.

### Summary

- Three Earth maps as map-gen presets and Map type entries: Terra Nauvis: Europe, Atlantic and Old
  World, with real coastlines at map scales 1 to 6 in an endless deep ocean. Exact coastlines, on by
  default on Atlantic and Old World, holds every shore to the reference with islets, and written land
  carries trees and ground cover.
- A spawn at a chosen or random city on every map (40, 50 and 33 cities), with land around it, a lake
  nearby, the starting ore and an enemy-free start.
- Waterways: great rivers with walkable fords that narrow with the map scale and carry ships at
  scale 6, straits and canals that ships can sail at every scale, and bays and headlands where a map's
  frame cuts through land.
- Earth climate with or without Alien Biomes, Alien Biomes ground by real region, marshes, 16 great
  forests, and the base game's trees, rocks and plants beside Alien Biomes.
- Cliff ridges along 16 mountain ranges with passes, the only cliffs on a map, and highlands of rocks,
  stony ground, and beside Alien Biomes grey rock and snow. Beside Alien Biomes every Nauvis world's
  cliffs use its grey stone art.
- Regular ore in lobed fields gathered in provinces, historic ore hotspots with heavier biters that
  ignore the map sliders, and offshore oil fields with the Oil Rig mod.
- Options: Canals, Great forests, Ridges, Ore hotspots, Ore hotspot amount, Inland lakes, Destroyed
  Europe with Alien Biomes, Exact coastlines, and City markers on the map view.
- Noise draws almost all of the terrain, so the new-game preview shows the map, with the noise coast.
  Control scripts handle what noise cannot: the start of a new world, the guards and warnings, the
  city markers and the Exact coastlines handler.
- Compatibility: Alien Biomes is optional, Space Age works and its other planets stay as they are,
  RSO is not supported and the game warns when it is active.
- Tooling: the static rows, the frozen body registry, reproducible zips, CI on every push and a
  release built by a `v*` tag.
- Verification: the fast finish replaced the plan's security review and suites with one security
  pass and the playability checks. What that leaves open is on
  its issue.

### Added

- Ore hotspot amount startup setting: 50, 100, 200 or 400 percent, default 100. It multiplies hotspot
  richness and nothing else, so no hotspot moves or grows.
- Destroyed Europe grows south and differs every seed:
  the zone now runs from France through Switzerland, southern Germany, Austria and Slovenia to Ljubljana
  and down Italy to about Rome, keeping the old zone's coverage north of the Alps. The outline lives in
  `data-src/approvals/destroyed-zone.json`: 15 vertices, each moved per seed by up to its own jitter of
  30 to 110 km through constants that fold, on a warp of 2.5 shares of the shared one. Three keep paths
  (Britain, Denmark with the Kiel Canal, the Carpathian crest) replace the six exclusion rows. The
  random pool skips every city the outline can reach at any seed (266 km): 18 of Europe's 40. The heat
  noise runs at 24 tiles instead of 96: single-tile land chunks in the zone fall from 441 of 919 to 15. Old World
  at scale 6, zone on: Tile 205,212 and Entity 31,955 against 205,392 and 32,135 before; previews in
  `previews/earth-build/feedback-1005/zone/sheet-*.png`.
- Start ore guarantee: `scripts/start_ore.lua`, called once from `start.on_init` on an
  Earth or Map-type-only world, floods the land the spawn reaches on foot (water tiles block,
  within 160 tiles) and, for iron, copper, coal and stone, places one patch of half vanilla's mean
  starting amount on that land where the reached amount within 150 tiles is under half of it
  (config.lua `start_ore`; skipped for an ore control at size 0 and with RSO's "Ore in starting
  area" off; beside RSO it reads what RSO placed and adds only what that start lacks, such as
  RSO's 33-tile stone patch at seed 1002). Fixes the ore-starved
  starts of Stockholm (scales 1 to 3), Athens (scale 5) and island starting patches such as
  Stockholm scale 1 coal at seed 1002. No noise body changes.

- Climate grain on all three maps beside Alien Biomes (Europe's biomes look
  best; Europe joined at integration for its Moscow). Alien Biomes' tile scores read frayed copies of
  temperature, moisture and aux
  through `tn_tile_temperature`, `tn_tile_moisture` and `tn_tile_aux`, each adding
  `noise_layer_noise(19)`, the call that frays grass-1's own edges, outside the temperate band; the
  temperate bonus and exclusion take grain versions. Every base world keeps its program, and trees
  and decoratives keep the plain fields.
  Beside Alien Biomes it is not free: paired CPU reads a median 2.2 percent slower at Frankfurt and
  1.5 at Moscow. `climate.grain.maps = {}` in config.lua turns it off.

- The list hook: beside Alien Biomes, Earth maps stop walking AB's long tile restrictions on every
  vanilla land tile. 111 decoratives and 64 trees take the vanilla land tiles at the front of the list and
  multiply their probability by the new body `tn_ab_keep_v1`, 0 where vanilla land may lie, so those tiles
  add no placement; the 13 extended decoratives and 5 dead trees take the same front, order only.
  Tiles do not move (dump and in-game hash); AB-only decoratives and trees lose their placements on
  adopted tiles and water-mud where vanilla land may also lie. The body reads plain temperature, so its
  band and lean are 2 wider than the grain-frayed tile bonus's, and these plants also thin along the
  temperate band's edges: about 7 percent of them over nine edge windows, while about 0.4 percent reach
  vanilla land on the frayed edge. See design notes 2026-10-30 12:55, 14:30 and 15:20.

- the first release fast finish: groups 1 to 3 and edge-and-lakes
  assembled on one branch. Atlantic's and Old World's version 6 (`tn_geo` 17 and 18) carry the spawn
  city the drafts lacked (every Old World start had landed at the map's offset 0, 0, in India): the
  per-map city tables `prototypes/tables/cities_atlantic.lua` and `cities_olde_world.lua` merged by
  `prototypes/city_tables.lua` (cities.lua is main's again), spawn records with the city fold, the
  spawn lake, start mask version 2 and the inland lakes behind the switch, the soft map edge, and
  bearings from `tools/build_spawn.py` emitter 4 (ported from an earlier prototype). Their
  presets also point the layer chain version's offset names (geography 6 and 7) at the fold, so the
  region layer, climate, ridges and stamps stay on the spawn's ground. Old World's table moves Prague
  to the real city and appends Frankfurt, Aachen and Moscow (the maintainer, 07:35); at seed 1000 and scale 6
  each of the four spawns on land with its lake and iron, copper, coal and stone in the start area
  (`previews/earth-build/fast/pv-ow-<city>-c`). 84 new bodies registered from the M1 dump; the M2
  dump hashes every registered body alike. The band-fix handler writes nothing inside the soft edge
  band and serves Europe 14 and Old World 16 and 18. `tools/tnlua.py` gains Lua patterns (find,
  match, gmatch, gsub), math.rad, deg, asin and acos, and seeds data.raw from
  `tests/vanilla-raw.json` (the base prototypes the hooks and wrappers read), so the bodies row and
  `build_zip.py --release` run the drafts' data-final-fixes.lua offline; the offline check holds M1
  records only.

- Fast finish fixups: a world made from a Map type entry alone gets the start a preset world gets
  (ported from an earlier prototype `bf25592`, its pack probe of 2026-10-29 11:05 and
  design notes 16:10 there): `start.on_init` reads the city back at (0, 0) through the fold the entry
  reads, sets the start message with the world size at the scale read back there as freeplay's
  intro, and records the RSO warning, which the player path already sends;
  `guards.map_type_geography` names the version whose entry the world reads. The cliff reset and
  the D12 warning stay Earth-only, and a world that is neither gets nothing.

- Spawn correctness: a world made from the Atlantic or Old World Map type entry
  alone reads the layer chain's offset fallbacks (`tn_cx/cy_<map>_v2`), which now name the city fold
  as the presets bake them, so its offshore stamp sits on the spawn's ground (Map type and preset
  worlds sample alike at Frankfurt, Aachen and Moscow on Old World and Prague on Atlantic; before,
  the chain was 28,266 tiles off at Frankfurt). Destroyed Europe's random pool is now defined for
  Atlantic (`tn_city_pool_atlantic_v1`) and Old World (`tn_city_pool_olde_world_v1`), and Old World's
  zone list adds Frankfurt and Aachen, which lie inside the polygon (zone depth 719 and 704 tiles at
  scale 6, Prague 699): 20 Old World seeds with the zone on spawned outside it, and a 400-seed sweep
  per map picked no zone city. The four fallbacks are re-registered and the two pools registered
  from the M1 dump.

- Milestone `europe-coast`: Europe's real coastline at map scales 1 to 6. `tools/build_geo.py`
  emits S1-fit's one-sided tent model as name-free generated Lua within 120 columns:
  `geo_europe_v1.lua` (8,192 tents plus the recorded T1-e local refit of 66 level-0 tents over the
  one island of 65 px or more the fit missed) and `land_coarse_europe_v1.lua` (the 256-tent
  checkpoint, the Entity program's one land field), from `data-src/fits/europe/` with its
  provenance. The real Terra Nauvis: Europe preset replaces the placeholder (retired with every
  registration and text it had), baking `tn_map`, `tn_scale`, `tn_geo` and Europe's city offset as
  numbers, and vanilla's three readers of the water slider (`water_level`, `segmentation_multiplier`,
  `nauvis_segmentation_multiplier`) at their default-slider values, so the slider moves nothing on
  a preset world, cliffs and land included (D15); beside Alien Biomes the preset is withheld until
  `climate-tiles`' palm switch, since AB's palms read `elevation` in the Entity program (design
  constraint 3). Europe's elevation entry `tn_elevation_europe_v1` composes the coast fit, the
  lattice detail (0 at every pixel centre), the sign-offset transfer and the far-field box (deep
  water at any distance beyond the 14,400 x 10,224 tiles of scale 6, from 1 tile out: from scale 3
  the extent's outermost tiles are plain water, because the game lets deep water border only water),
  reads only Europe-bound names and is Europe's Map type entry ("Terra Nauvis: Europe"), with
  prototype fallbacks for `tn_scale` (which follows the scale setting) and the frozen constants
  `tn_cx_europe_v1` and `tn_cy_europe_v1` (registered, so no later version moves a Map-type-only world;
  a city spawn reaches the entry's next version through names of its own);
  `starting_resources_lake_mask` reads the start mask on the coarse field; `scripts/guards.lua` adds
  the Map type notice (which warns that a changed scale setting can move such a world, and says so
  when the preset is withheld), the drift line (on every configuration change for a Map-type-only
  world), the missing-name guard, and a one-time warning, recorded in storage, when a world made from
  a preset loads beside a mod that withholds it (Alien Biomes); a Map-type-only world is identified by
  any version of its map's entry and then by storage, and every message names the map by its preset.
  The scale setting's labels carry each map's world size, and its description, like the drift line,
  the preset's description and `changelog.txt`, says that a preset world keeps its scale while a world
  using a Map type alone follows the setting, which moves the terrain of its new chunks (no text
  promises "new worlds only"). Twelve bodies are registered in
  `tests/frozen.json`. The runner gains europe-coast's rows and suite checks (with game
  runs in up to four workers, where a breach in one worker stops every worker at once; `water_inert` for the
  slider; T3 measuring the extent from the far-field switch with its exit-0 guards; T11 comparing
  entities and reading back every baked value; T2 reading back each run's seed with M0's grid as its
  positive control; `t3_detail`, `t12_twice` and `t13_routes` proving Earth active against M0; the
  walker and the Map type route's forced pair timed at 8 LP beside 16 LP as section 6.2's diagnostic,
  `preview_time` for T15-f, and the exploring runs' peak working set for T15-h), the
  toolchain rows run on Europe (`ab_placeholder` became `ab_withheld`), the V1 contact sheets are
  committed under `tests/baselines/suites/europe-coast/v1/`, and T16 gains the Map type locale,
  scale-label, fits-provenance and fallback rows and schema checks of config.lua's `geography`,
  `water_slider` and `withheld_with` groups. Review run 2 fixed the
  first run's last four review findings: stored warnings have one record shape and one writer
  (`guards.record_warning`), every stored record is checked before use, and the new T16 storage row
  keeps other files off the store; `tn_geo` is one id space across every map, `release_registry`
  rows name their map, and `tnconfig`'s id-space check fails a shared or unregistered id; T11
  generates S2's 41st chunk only after a whole-table `map_gen_settings` round trip and checks that the
  baked names survive it; and the append-only reference is the union of main and origin/main and
  fails closed, in the gate's frozen row, T15a's growth base and the new T16 append-only row (bodies,
  `tn_map` and `tn_geo` ids, stored message keys), which CI runs on a full-history checkout. Engine
  run 2's final review: `tests/frozen.json` follows one record contract,
  `tools/tnfrozen.py`, in every reader (the gate's frozen row, `freeze`, the T16 frozen and
  append-only rows and `build_zip.py --release`), so a record's dump label, which picks the dump the
  frozen row reads its body from, must be one the runner's milestone registry assigns and can no longer
  switch that row off (a relabel or a typo fails instead of being skipped, and `freeze` refuses it);
  the append-only checks compare whole records; and ARCHITECTURE's coordinate chain rows give each
  chain version offset names of its own (v1's frozen at 0, `spawn-cities`' v2 with its own names and
  chain). The group build with `spawn-cities`: the gate's frozen row
  reads every registered body or fails, so a record whose dump the command did not produce fails
  like an unknown label; and `config.lua` holds every version per map (`geography.<map>.versions`,
  each with its own names, `tn_geo` id, city offset, start mask, generated files and Map type
  fallbacks; `start_mask.versions`, each naming its formula; no top-level `fallbacks` group), which
  `presets.lua`, `coast.lua`, `spawn.lua`, `guards.lua` and the tools read per version, with the
  documented next version as a T16 positive control and its re-pointing, shared-id, unkeyed and
  unwalled variants as negative ones (the dumped prototypes are unchanged); the V1 sheets' preview
  panel tiles every T1 preview of its scale, so the whole-map sheets at scales 3 and 6 and the crops
  on a preview edge show their whole window; and the runner's kill
  control checks only the probe's own game processes, so another run's game on the shared
  machine no longer fails `runner_controls`, and the timing census
  leaves out wholly suspended game processes, which the run's draft governor parks while the
  workspace lock is held.
- Evidence (`tests/baselines/suites/europe-coast.json`; runs under `%FACTORIO_WS%\previews\earth-build`):
  T1 0.991846 at scales 1, 3 and 6 from cliff-free previews (p99 1.58 px, max 7.11 px, 86 of 86 land
  components of 65 px or more, thin water become land 42,625 px in 346 reaches of 20 px or more), the
  grid proxy the same at scales 1 and 6 and equal to the scale 1 preview pixel for pixel, 0
  differing grid bits at seeds 1002 and 1004 (each run on its own seed; M0's grid differs there in
  1,215,116 and 881,261 bits), and 0.990839 and 0.990239 at scales 3 and 6 without the
  integer-corner offset; detail on and off give equal grids at scales 1 to 6, with the detail-on grid
  at 0.991846 and 64 of 64 off-centre tiles reading a non-zero detail at scales 2 to 6; Tile 82,784
  to 82,890, Entity 8,553 and Cliff 287 at scales 1 to 6, Entity and Cliff equal to the
  constant-coast twin's at scales 1 and 6; P1 M1t/M0t 1.0207 at 16 LP (scale 6) and 1.026 (scale
  1), P3 1.0179 at 24 LP, the 8 LP diagnostic 1.1503 and 1.1681; real time P4 2 ticks over 20 ms,
  P5 1.0015, P6 210 to 245 ms; P7 +0.0004 ms per tick (-0.0002 at 8 LP); P19 1.0922 (whole save
  1.3768); the Map type route's forced generation 1.0194 times M0's at 16 LP (1.1415 at 8 LP);
  preview time 4.62 times M0's at 1024 px and 4.182 at 256 px; the peak working set while exploring
  210.5 against 202.5 MB in the walker at 16 LP and 224.0 against 209.0 MB in real time at 24 LP; the
  first-column hitch and the start-area save excess traced to the coast program (design notes
  2026-10-28 03:40); the water slider byte-identical at none, 6 and frequencies 6 and 1/6; deep water
  from 1 tile beyond every edge from scale 3, the measured extents 2,400 x 1,704 to 14,400 x 10,224;
  T11's tiles and entities 0 against fresh A at every scale pair, its 41st chunk generated after a
  whole-table map_gen_settings round trip that kept all 11 baked names; the Map-type-only world
  identified and labelled by its preset under a build whose entry lost its Map type fields; the
  withheld-preset warning once on a preset save loaded beside Alien Biomes; 12 V1 contact sheets,
  each read as a PNG; `install-check` ok (zip 75d54f90). These are the values of the group build's
  suite (`suite/20261028-180852-europe-coast`, 2,625.5 s, design notes 2026-10-28 19:05), run after
  this round's tool changes made every key stale; the Space Age rerun's are in design notes 14:40,
  Review run 2's in 12:50, review round 3's in 10:45, round 2's in 09:10, round 1's in 06:30 and the
  first suite's in 04:40. The group's final tree (2.1.24, after `spawn-cities`) is measured in
  design notes 2026-10-29 11:05 (`suite/20261029-124540-europe-coast`), the timing rows on Europe as
  `spawn-cities` places it.
- Gate wall time of `gate --through europe-coast` on the group's final tree (2.1.24;
  design notes 2026-10-29 11:05): cold 377.4 s (`gate/20261029-140420-europe-coast`, `--cold`, every
  FG key stale, 29 rows: the 26 FG rows 258.3 s, the suite evidence 16.6 s, live samples
  `t1_corner` 50.7 s and M1t/M0t 1.0002 at 16 LP 50.3 s), and warm 143.4 s
  (`gate/20261029-141044-europe-coast`, live samples `t18_drift` and 0.9946), both passing on a quiet
  machine. The live sample is drawn at random; this cold run drew the milestone's dearest check, and with
  the dearest draws seen (`t1_corner` 59.2 s, the timed group 86.5 s; design notes 2026-10-28 14:40)
  it would take 422.1 s, under 8 minutes, so no FG row moved to the suite. The group build's tree
  took 393.2 s cold and 169.5 s warm (`gate/20261028-185600-europe-coast`,
  `gate/20261028-185253-europe-coast`; 19:05), the tree before it 346.4 s cold on a quiet machine
  (`gate/20261028-142023-europe-coast`); beside a game holding about half the CPU, with Space Age
  installing mid-run, a cold run ran out of its 9 minutes (`gate/20261028-132422-europe-coast`).
- Milestone `toolchain`: the `terra-nauvis` 0.1.0 mod skeleton, with `prototypes/config.lua` as the
  single source of names and constants, the Map scale startup setting (1 to 6, default 6), the
  placeholder preset "Terra Nauvis: Europe" (Europe's extent at scale 6 with an ocean beside the
  spawn, and a copy of vanilla's start mask on `elevation_nauvis`, so design constraint 3 holds on
  it; withheld while Alien Biomes is loaded, whose palms read `elevation`), the GPLv3 `LICENSE` and a
  written source offer; byte-reproducible zips from `tools/build_zip.py` (`--release`, which refuses
  any Earth body `tests/frozen.json` does not register, and `--check-tag`; it refuses an output
  folder in the live profile, in any spelling (the NT namespace included), a mods folder, and a
  file with a second hard link or a folder holding one); the gate runner
  `tools/earth_test.py` (`gate`, `suite`, `install-check`, `baseline`, `static`, `freeze`, and
  `guard-rebaseline`, which is left to the maintainer at an interactive terminal) with content-hash keys,
  live-profile guard brackets chained on the chain's last entry with an append-only journal and a
  check for game logs written outside every bracket, the workspace lock and its bracket token, a
  kill-on-close job object around every fh.py launch, a stop of every further game run of a command
  as soon as one run may have left its instance or ran on another build, validated milestone ids, every
  tool output judged at the absolute path the tool writes, the section 6 parser that
  reads every cell of 6.2 and 6.3 (P3 in force from the first milestone, and no row in force without
  its check), rule 5's pooled group for a timed ratio near its limit, suite evidence re-derived from
  raw outputs alone (timed repetitions, the walker, the server saves, and the game self-test by
  replaying its stored runs), the frozen-body check over every Earth body of the dumps, and the
  isolation checks (a) and (b) gating from here, (b) walking each placed prototype's property keys
  through the preset's redirects, with their positive controls on the test-only `ea-leak-fixture`
  presets, plus the `ab_placeholder` row beside Alien Biomes (placeholder presets only; it retires
  with the placeholder in `europe-coast`, and the AB palm leak on the real presets stays outside the
  gate until `climate-tiles`); `tools/tnguard.py` (the
  bracket check, the live-profile output refusal every repo tool shares and the declaration of every
  tool option); `tools/perf.py` (the quiet-window protocol, the affinity watcher, the T15b timer, the
  benchmark-mode walker, the real-time and server-save jobs); `tools/tn_static.py` (T16's static
  rows, which `ci.yml` runs, the name scan reading identifiers and `tools/mods/` among them, and the
  workflow scan holding both workflows to their exact steps and commands); the lint
  toolchain (luacheck 1.2.0 per user, luaparser 4.2.0); S8's tools and test mods, TQ1's timer and
  TQ2's driver ported to `tools/` and `tools/mods/`;
  EarthMaps' reference rasters in `data-src/earthmaps/` and the approval data in `data-src/approvals/`,
  each with its provenance; the T3 oracle in `tests/oracle/` (S8's places plus R7b's, R7a's, R1's and
  the brief's rows); and the `ci.yml` and `release.yml` GitHub workflows.
- Gate wall time on this machine (decision 1; test notes open item 6): cold 162.4 s
  (`previews/earth-build/gate/20261027-191014-toolchain`, every FG key stale) and warm 128.7 s
  (`previews/earth-build/gate/20261027-191322-toolchain`), both with the rotating live sample (the
  31-check game self-test, replayed from its outputs, and an M0t against M0t pair at 16 LP), both
  far under 10 minutes; paths are under `%FACTORIO_WS%`.
- Evidence: S8's offline self-tests run 62 + 760 + 10 + 4 + 10 checks from `tools/` with no failure;
  the game self-test passes 31 of 31 through fh.py and again when replayed from its stored outputs;
  the oracle data passes 1,578 checks; T16's fixture controls 220 of 220 and the runner's 87 of 87
  behave; P18 reads M0t/M0t 0.9892 at 16 LP and 0.9998 at 8 LP, every repetition re-derived from its
  raw outputs (suite `previews/earth-build/suite/20261027-175324-toolchain`; the game self-test's
  evidence from suite `previews/earth-build/suite/20261027-190504-toolchain`); on the placeholder
  preset Entity 8,549 and Cliff 287 equal the constant-coast twin's while Tile differs (10,093
  against 8,777), and the dump walk finds no firewall path, while on the fixture presets it reaches
  the fine field through the start mask and through the redirected `entity:coal:probability` and
  `decorative:brown-asterisk:richness`; beside the live Alien Biomes copy no placeholder preset is
  defined, while the placeholder's redirects would reach the fine field through `tree-palm-b`.
- Milestone `spawn-cities`: Terra Nauvis: Europe spawns at the chosen city by shifting the
  geography (S7 option ii): the startup setting "Spawn city: Europe" (Random, the default, plus 40
  of the 41 EarthMaps Europe cities; Luxembourg removed for `iron-lorraine-minette`, APPROVALS 12),
  the city table `prototypes/tables/cities.lua`, the city fold (`tn_city_europe` baked per save,
  random a float32 fold of `map_seed`, the index readable at (0, 0)) reaching version 2's own chain
  through `tn_cx_europe_v2` and `tn_cy_europe_v2` on both the preset and the Map type route (version
  1's offsets stay frozen at 0); the `distance`
  redirect, so the starting ore and the enemy-free start of the base game follow the spawn; the
  analytic spawn lake about 72 tiles out on a per-city, per-scale inland bearing that
  `tools/build_spawn.py` emits from the reference raster (`prototypes/generated/spawn_europe_v1.lua`),
  with coastal starts tilting starting ore toward the land component holding the city on a bearing
  and width `tools/build_spawn.py` picks per city and scale by the share of starting patches left
  off that land over a fixed draw of random spot-noise candidate layouts (design notes 2026-10-29
  00:30); the start land guarantee (land within 16 tiles); sparse
  inland lakes by spot noise (8 per 1,024-tile region, about 16 tiles across, kept off coasts and
  out of the start area); Europe's elevation entry and start mask under their next versions
  (`tn_elevation_europe_v2`, which takes the Map type fields over, and `tn_start_mask_v2`, graded on
  the coarse field and the spawn lake), the v1 bodies defined and registered, `tn_geo` 2; the start
  message on freeplay's intro and in the log; the RSO warning at creation and to each created player;
  the Nauvis-only surface guard (D33), which touches only an Earth or Map-type-only world and there
  only Terra Nauvis's own values (a vanilla Island save, new and with the mod added, keeps
  `elevation_island` on every probe planet); the drift line for the spawn city; 20 new bodies in
  `tests/frozen.json` (32 in all, every europe-coast record unchanged). Runner: the float32 city model and the geo-to-world conversion in
  `tools/oracle.py`; S7's `measure()` and the freeplay intro in the dump probe; the test probes
  `ea-planet-probe`, `ea-player-probe` and `ea-force-spawn`; FG rows `sc_dump_facts`, `t14_walker`,
  `t15b_geo`, `t7_random` and `t13_maptype_city`; suite checks for the coastal sample, the city
  sweep, the five seeds, inland lakes, the starting-area slider, the city flip, RSO on the live pack,
  the player path, the planet guard and a second force's spawn, with Europe re-timed; the
  europe-coast T1, T2 and T3 rows score the coast in a coast-only world and its timed positions
  place through the spawn offset. Complexity at scale 6: Tile 83,022, Entity 8,534, Cliff 286
  (baseline `20261029-004141-spawn-cities`; the city fold and the bias tables fold to constants).
  T7 (b)'s ore bar is a rate over the seed 1000 sweep: every
  ore reachable within 150 tiles of every start, at most 1.5 percent of the sweep's 492 ore checks
  under half of vanilla's tiles, none at a start whose disc holds no sea by `tn_land_coarse` (read
  offline from the coarse checkpoint and held to the game's field at 9 probes per start), every one
  named in the report, with negative controls; the sweep has 5 under half (Athens scale 6, Oslo and
  Stockholm scale 3), all by the sea. T3's real-tile lakes square and its coast-only comparator run
  at scales 1 and 6, scale 1's placed from its density grid away from the start. The T16 append-only row
  also fixes the data landed bodies are built from (config.lua's constants, the landed release
  rows, the generated files, the city tables and, exactly, the spawn-city setting's list of values,
  whose order and length the city fold and every save's baked city number read) against main and
  origin/main.
- Registered bodies checked as bodies, without the game:
  `tools/tnlua.py` runs the mod's settings and data stages offline (a Lua 5.2 subset over
  luaparser's tree with stubs for `data`, `settings.startup` and `mods`; it fails closed outside the
  subset), and the new T16 `bodies` row (CI), `build_zip.py --release` and a zip built outside the
  checkout hold every body it builds to its `tests/frozen.json` record, so a body changed in place
  through `coast.lua`, `spawn.lua` or `presets.lua` fails CI and the release; the gate's frozen row
  holds the offline bodies equal to the game's M1 dump (34 of 34). `release.yml` checks out full
  history and its tag check refuses a tag that is not the checked-out commit or is not on
  origin/main; the append-only references add every `v<x.y.z>` release tag. Each milestone's suite
  manifest carries a `frozen` snapshot of the records registered through it (`suite`, `freeze`),
  and the gate's frozen row, the T16 append-only row, `freeze` and `--release` fail a record of an
  earlier milestone's snapshot that the registry changed or dropped, so a group's later milestone cannot
  rewrite an earlier one's registration before landing. A zip built into a folder outside the
  checkout (the live mods folder) is a landing: it may not change or drop a body of a zip of this
  mod already there, and its build record keeps its bodies and its registry's snapshot.
- Gate wall time through `spawn-cities`, on the group's final tree (2.1.24), where
  the gate re-derives both milestones' suite evidence and draws its live sample from both milestones' checks
: cold 374.3 s (`gate/20261029-135229-spawn-cities`, `--cold`, every
  FG key stale, 35 rows: the 31 FG rows of `toolchain`, `europe-coast` and `spawn-cities` 285.9 s,
  `spawn-cities`' own five 32.0 s, the suite evidence 15.7 s for `europe-coast` and 7.2 s for
  `spawn-cities`, live samples `t14_planet` 13.8 s and M1t/M0t 0.994 at 16 LP 50.1 s), started at 1
  percent CPU load with no other game running, and warm 174.2 s
  (`gate/20261029-135852-spawn-cities`, live samples `t18_drift` and 1.0209). With the dearest draws
  seen on 2.1.24 (`t1_corner` 53.6 s, the timed group 51.3 s) the cold gate would take 415.3 s, and
  with 2026-10-29 04:40's figures (59.2 s and 86.5 s) 456.1 s, under 8 minutes, so no FG row moved
  to the suite. Earlier trees: 407.2 s cold and 200.9 s warm at 04:40
  (`gate/20261029-043618-spawn-cities`, `gate/20261029-044334-spawn-cities`), and 430.5 s and
  231.4 s on 2.1.24 before this change, when the gate held `spawn-cities`' evidence alone (09:00).
- Milestone `olde-world-atlantic`: the presets "Terra Nauvis: Atlantic" and "Terra Nauvis: Old
  World" (`terra-nauvis-atlantic`, `terra-nauvis-old-world`, orders "a-tn-b" and "a-tn-c", after
  Europe and before Rich resources, withheld beside Alien Biomes as Europe's is), each from its own native-resolution fit at the smallest
  growth-1.25 checkpoint at or above 99.1 percent (Old World 4,096 tents at 0.991420, Atlantic
  8,674 at 0.991198, offline T1 from `curve.json`), with each map's 256-term coarse land field
  and descriptions naming the world size; their Map type entries `tn_elevation_atlantic_v1` and
  `tn_elevation_olde_world_v1` (orders "3000-tn-b" and "-c", so the Terrain tab lists Nauvis, Lakes,
  Europe, Atlantic, Old World, Island), each reading only its own chain, fit, detail, box and
  map-qualified city offsets, with fallbacks valued as its own preset bakes them; `tools/build_geo.py`
  `fit` (S1-fit's fitter ported operation for operation, resumable from a work folder outside the
  repo; it reproduces Europe's 256-term checkpoint bit for bit), `curve` and `adopt`; each map's
  geography version 1 (`tn_geo` 3 for Atlantic, 4 for Old World), with its city offset names
  `tn_cx_<map>_v1` and `tn_cy_<map>_v1` baked 0 under frozen fallbacks of 0, and its 11 bodies
  registered in `tests/frozen.json` (22 new, every group 0 record unchanged; restacked onto group
  0's tree, design notes 2026-10-29 10:30); the three maps' complexity rows in
  `tests/budgets.json`; the startup settings `terra-nauvis-spawn-city-atlantic` (random plus 50
  cities) and `terra-nauvis-spawn-city-old-world` (random plus 30), default random, with each map's
  table in `prototypes/tables/cities.lua`, which the gate refuses until `spawn-cities`' city fold
  reads them (`city_fold_findings`); and the runner's rows for every map (`owa_dump_facts`,
  `owa_routes`, `owa_maptype`, `owa_t7_random` in the gate; `owa_fits`, `owa_t1_grids`,
  `owa_t1_windows`, `owa_v1_sheets`, `owa_t7`, `owa_t11`, `owa_maptype_cost`, `owa_t15b` in the suite;
  T15a, the baseline and isolation (a) on every map), whose city parts (T7, T11's city flip, T13's
  read-back city index) fail closed on a map without the fold.
- Evidence (draft, on the draft's own isolated instance): Old World's fit 29 steps in 41 minutes at a 1.7 GB peak, Atlantic's 32 steps in 85 minutes at 3.4 GB (native resolution, no subsample); the port reproduces Europe's 256-term checkpoint array for array; Old World compiles Tile 51,438 to 51,544 at scales 6 to 1 (its 8,192-term step 89,154, so the 4,096 terms saved free 37,716 Tile), Entity 8,553 and Cliff 287 on every new map, Europe's rows unchanged; isolation (a) holds on all three presets at scales 6 and 1 and the dump walk (b) finds no firewall path; Old World's in-game grid equals its offline model on all 1,048,576 pixels of its densest coast window at scales 1 and 6, and at seeds 1000 and 1002; route parity, the Map type route over each new map's coast view and the notice naming each map's preset hold; T11 on Old World (scale 3 loaded under 5) matches fresh A in all 51,200 tiles and differs from fresh B in 17,564; `earth_test.py static` passes 14 of 14 rows. Atlantic's measured rows, the suite (timing, full grids, windows, contact sheets) and the gate remain for the build.
- Milestone `waterways`: APPROVALS 7's curated rivers, the nine D17 straits and the D18 canals
  carved on every map at every scale by `tools/build_waterways.py` from `data-src/waterways/`
  (APPROVALS 7's adopted rivers in priority order with their class, S4's paths, provenance) into
  `terra-nauvis/prototypes/generated/waterways_<map>_s<k>_v1.lua` (18 files, each with its rivers,
  straits and turning basins, canals, dams and fords) and `data-src/waterways/manifest-<map>.json`;
  rivers `max(7, k x scale)` tiles wide by class (18 and 12 at scale 6) on S4's smoothed paths;
  straits and canals on their drawn passages, every strait through its R7b narrowest point (the
  Dardanelles re-routed: S4's path ran north of the Gallipoli peninsula) and every canal along its
  R7b route, straight between its vertices; Gibraltar, Dover and the Great Belt two-way at 11
  tiles; a walkable `water-shallow`
  ford every 60 reference px of every river, 8 tiles long and spanning it, through the gated hook on
  `water-shallow` (`tn_on`, `tn_fords`), registered on Nauvis, on banks the coast fit holds as land
  beyond its detail where the interval has them, widened on a bending reach where no straight one
  does, an interval going without one only where every position has a bank in reference or fit
  water; turning basins where the
  bend rule fails on a shipped polyline (the Rhine and the Garonne at scale 6, as S4 found) and,
  where it places none, the criterion's others (the Dardanelles at every scale, the Little Belt at
  scale 6) at the passage's sharpest stretch; each map's river-safe starts as name-free data
  (`terra-nauvis/prototypes/generated/starts_<map>_v1.lua`: per city and scale the spawn's move and
  bank half-planes), which the next versions of spawn-cities' city fold, spawn lake and start mask
  read once spawn-cities is on main; each
  map's next geography version, every name its own (Europe's version 3, `tn_elevation_europe_v3`,
  over version 2's spawn at the city, `tn_geo` 5; Atlantic's and Old World's version 2,
  `tn_elevation_<map>_v2`, `tn_geo` 6 and 7; restacked onto group 0's tree, design notes 2026-10-29
  12:00), now the Map type entries, composing the canals-off dams and the carves around the rest of
  the version's composition, picking the save's scale's sets through the folded scale; the
  startup setting Canals (`terra-nauvis-canals`, default on: Kiel and Corinth on every map, Suez on
  Atlantic and Old World, Panama on Atlantic), baked per save as `tn_canals` with its Map type
  fallback and drift line; the Map type notice naming rivers and fords; the plan's waterway cut
  order per map and scale (Europe scale 6 at a 4-tile tolerance; Old World scales 5 and 6 at 4 and 6
  tiles; Atlantic keeps all 32 rivers at scale 1, 24 at scale 2 and Europe's 22 from scale 3, the
  Niger, Mackenzie, Mississippi, Congo, Nile, Zambezi, Amazon, St. Lawrence, Parana and Orinoco
  leaving Atlantic's larger scales from the bottom of its list); the 110 new Earth bodies
  registered in `tests/frozen.json` (every earlier record unchanged); the strait, isthmus and canal oracle rows live;
  every T1 row masking the D16 corridors; and the runner's rows (`ww_dump_facts`, `ww_emit`, `ww_t3`,
  `ww_ford` in the gate; `ww_t5`, `ww_fords`, `ww_widths`, `ww_bend`, `ww_t1`, `ww_t3_maps`,
  `ww_t11`, `ww_m3`, `ww_paths`, `ww_v2`, `ww_t7`, `ww_ab`, `ww_t13_m2`, `ww_off`, `ww_t15b`,
  `ww_maptype_cost` and the exploring rows in the suite), with `tools/mods/ea-ww-probe`, `nav.py`'s
  ford and cross-section reports, P1's relative rule for an added time allocation, and the budgets rows' toggles-off
  measurement on every map the canals toggle lists.
- Evidence (draft, on the draft's own isolated instance): `build_waterways.py check` re-emits all 18
  files twice byte for byte (51 s; with the three river-safe starts files, 21 files in 218 s on the
  E-cores); 2,853 fords on all maps and scales, 6 widened on a bending reach, 29 intervals in
  reference or fit water without one and 11 named fords whose banks lie within the coast detail
; the criterion's basins at the Dardanelles' and the Little Belt's sharpest stretches
  where the bend rule places none; `earth_test.py static` passes 14 of 14 rows; Europe at scale 6 reproduces S9's 844 river and strait segments
  before the cut; Tile with waterways at most 111,005 (Europe), 111,930 (Atlantic) and 111,799 (Old
  World) over scales 1 to 6 with canals on or off, Entity 8,553 and Cliff 287 unchanged on the
  presets (the Map type route, each map's v2 entry picked alone, also compiles the waterway sets
  for vanilla's starting-ore mask in Entity: `ww_maptype_cost` times and reports its Tile, Entity
  and Cliff complexity and its forced generation against M0 at scale 6 and 16 LP, never gated); the
  strait, isthmus and canal places of Europe at scale 6 reading their expectations in the real tile
  with canals on and off (21 and 21), and the first Danube ford walked, blocked without it, 8 tiles
  long, spanning and passing a 7-tile channel; in game every corridor of Europe at scales 1 and 6
  and of Atlantic and Old World at scale 1 (33, 33, 45 and 49) carrying S4's 7 or 11-tile channel
  end to end, no canal's seas sharing a water path with canals off on any map at scales 1 and 6,
  every strait reading water and every isthmus land with canals off on every map at scales 1 and
  6, and the fords and widths design notes records; the default preset byte-identical
  to M0 at seeds 1000, 1002 and 1004 with identical operations, registers and complexity; every
  oracle strait, canal and isthmus place inside its carve at every scale; `oracle.py validate` passes
  1,486 checks with waterways live; previews show the carve and a shallow ford across the Rhine and
  the Elbe at scale 6. The gate's cold and warm times, the suite and the baseline remain for the
  build engine.
- Milestone `region-layer`: the shared region layer (S10 design (d)) that marshes, great forests,
  hotspots, the biter multiplier and Destroyed Europe will read by name: 112 rows in
  `prototypes/tables/regions.lua` (R7b's destroyed polygon with S10's six exclusion rows, 16
  adopted forests, 12 marshes, 77 hotspots at their adopted centres with S6's jitter), written by
  the new `tools/build_regions.py` from `approvals-data.json` and R7b; each row's signed distance,
  weight and depth, each hotspot's jittered centre and the layer aggregates (`tn_destroyed_sd`,
  `_w`, `_depth`, `tn_forest_w`, `tn_forest_sum`, `tn_tree_mult`, `tn_marsh_w`, `tn_hotspot_w`,
  `tn_enemy_mult`), built in `prototypes/expressions/regions.lua` in one region frame for all three
  maps, with one shared warp anchored to it (S10's octaves as `basis_noise`, because
  `multioctave_noise` offsets do not shift its input in 2.1.23) and a radial 24 px clamp; the query
  point on each map's newest geography version's chain (Europe's version 3, Atlantic's and Old
  World's version 2; restacked onto the waterways restack, design notes 2026-10-29 13:30); the 515
  bodies registered in `tests/frozen.json`, each a name config.lua defines (`tools/tnconfig.py`
  composes the row names from config.lua's stems and suffix and the table's ids, as `regions.lua`
  does, so the dump facts, the static frozen row and `build_zip.py --release` see every one); the T3
  oracle's region expectations, strait ends and interior places (`oracle.py regions`, re-derived by
  `validate`); the test mod `tools/mods/ea-region-probe`; the static `regions` row (the table
  re-emits byte for byte, no region formula outside `regions.lua`); and the runner's rows
  (`rl_dump_facts`, `rl_t3_oracle` and `zero_change`, the recorded preview hashes against main's
  copy, with T15a's rows held equal to main's, in the gate;
  `rl_t3_maps`, `rl_t2_zone`, `rl_locality`, `rl_read_cost` in the suite). Nothing reads the layer
  yet, so no map changes.
- Evidence (draft, on the draft's own isolated instance, through the runner's own row and check
  functions): every program's complexity and every 256 px preview hash at seeds 1000, 1002 and 1004
  equal the build before it on every preset at scales 1 and 6 and on the default world; isolation (a)
  and (b) hold on every preset; T3 at the three seeds on every map at scales 1 and 6: 5,134 pass, 92
  listed within 40 km of an edge, 0 fail, every protected feature outside the zone; T2: the zone's
  seed-pair IoU 0.9153 to 0.9225 and IoU with the polygon 0.9429 to 0.9443 on every map at scales 1
  and 6, its furthest pixel 22.5 px beyond the polygon, the same zone on all three maps and at both
  scales, Europe's repeat at scale 6 identical (the suite now repeats seed 1000 on every map at both
  scales and compares every grid and hotspot centre), 66 forest and marsh edges moving per seed
  within their bounds, 161 hotspot centres within their jitter; the Spessart test copy changes only
  the table and only the
  forest aggregates inside the new row; read through a test MGS the layer adds Entity +3,234 and
  Tile +2,029 on Europe; `earth_test.py static` passes 15 of 15 rows. The gate's cold and warm wall
  times, `baseline` and the suite remain for the build.
- Milestone `climate-tiles`: the Earth climate after EarthMaps' layout on every Terra Nauvis preset:
  temperature from latitude on each map's chain with Eurasia's continental cold (D9: Russia cold)
  and seven dry belts cut from EarthMaps' painted sand, in an Alien Biomes variant (AB's hot, cold,
  moisture and aux sliders) and a fallback without AB (the far north dry and dead ground), reached
  through the presets' `temperature`, `moisture` and `aux` redirects, each the Earth mean plus a
  seeded spread so every climate zone is a patchwork of several tiles that changes with the seed;
  beside Alien Biomes the 19
  vanilla land tiles re-listed behind gated hooks with S3's temperate lean, the non-adopted AB land
  tiles excluded from temperate bands by a gated hook (D11; APPROVALS 9), and AB's palms on Earth
  copies that read a constant (the palm leak closed; ARCHITECTURE's preset-key fallback), whose keys
  every preset bakes with or without AB, so a world that gains AB later meets the switch, while a
  save made before the switch keeps its palms on the fine field for life (design notes 2026-10-29
  18:40, which also keeps the stored withheld-preset warning's text true); the 12
  adopted marshes (APPROVALS 8) from the region layer's marsh weight, with water-mud pools on land and
  water-shallow along open water joined to the ford hook, and AB's wetland biome; each map's next
  elevation entry (Europe's version 4, Atlantic's and Old World's version 3; `tn_geo` 8 to 10), the
  waterways around a shore body recalibrated for AB's beach band and deepwater line, carrying the Map
  type fields; AB 0.8.0's palms frozen as Earth data
  (`tools/build_palms.py`, `prototypes/generated/palms_ab_v1.lua`) with a check of the installed palms;
  without AB `grass-1` between the marsh pools; the milestone's bodies registered in `tests/frozen.json` by
  `freeze`, which now hashes every registered body in every dump that holds it; M2 in the gate (its
  dump, dump facts, zero-cost row, isolation (a) and (b), the climate oracle rows, the M2 budget rows
  under P11 and P13) and the T3, marsh census, D11, zone variety, T4 (with Alien Biomes' hot and cold
  sliders and M0 and BAB controls), V3, Map type, M6, design experiment 9 and timed suite checks
  (`ct_t15b` with the flip rule's guard, `walker_m2`, `rt_m2`, `save_m2`, `ct_maptype_t15b`). Gate cold
  and warm wall time: not yet measured (the build records them).
- Evidence (draft, on its own isolated instances, `previews/earth-build/draft-climate-tiles/`): M1
  default hash-identical to M0 and M2 default to BAB at seeds 1000, 1002 and 1004 with identical
  operations, registers and complexity; every brief climate row holds on all three maps at scale 1;
  EarthMaps' class agreement 1.000 per class; M2 Europe at scale 6 Tile 171,748 and Entity 17,414
  (base build 168,746 and 121,448, the palm leak); M1 Europe at scale 6 Tile 110,343 and Entity 8,352
  (base 110,490 and 8,553); the M2 isolation walk finds no firewall path on any preset.
- Milestone `trees-forests`: the great forests, the startup setting Great forests (default on,
  baked per save through the hook gate `tn_forests_on`): every living tree's own probability under
  the great-forests hook `if(tn_forests_on > 0.5, min(1, (own) * tn_tree_mult), own)` on every world,
  which Earth presets point at the region layer's multiplier for the 16 adopted forests (boost 2, S10),
  the base game's dead and dry trees and Alien Biomes' palm prototypes left alone, and the palms'
  second probability versions carrying the boost around climate-tiles' copies; beside Alien Biomes
  the base game's 15 living trees, its rocks and its decals rebuilt from `prototypes/tables/vanilla.lua`
  (the 2.1.23 texts) behind `tn_on`,
  each with its key and Earth body (the trees on the vanilla-scale Earth temperature) and restricted
  to vanilla land, the 11 vanilla decoratives AB takes off Nauvis re-listed behind the same gate, and
  the AB-restricted vanilla decoratives and dead trees extended onto vanilla land; 85 bodies
  registered in `tests/frozen.json`, all from the M1 dump (trees.lua defines each on every load); the
  zero-cost comparison letting the folded tree hooks join Entity's parsed counts (operations,
  registers and complexity identical); the dump
  facts and the FG forest-membership row; the T10 forest (every forest judged at every seed, ring
  ratios reported), save (M0 and BAB per generated chunk reported), climate and scatter, T17 (with its
  M0 calibration), T4 (every row at three seeds, frequency by patch texture), T3, palms, D27, T11, V4
  (woodland chosen from the forest runs) and timed suite checks (P2 bound to M2t/BABt by its relative
  rule, tf_t15b registered as later milestones' P1 and P2 base), every Earth probe run proving its preset
  applied (G5). Gate cold and warm wall time: not yet measured (the build records them).
- Evidence (draft, on its own isolated instances, `previews/earth-build/draft-trees-forests/`): M1
  and M2 default Entity programs keep 600 operations, 92 registers and complexity 8,549 and 1,743,
  187 and 24,377 (parsed expressions 2,097 and 4,899 against 2,063 and 4,607); on Europe at scale 6
  the Black Forest's 21 inside chunks hold 1.93 times the trees with the forests on (M1 1,155 to
  2,233; M2 1,158 to 2,234) at seed 1000; the isolation walk finds no firewall path on any preset on
  M1 or M2; Entity at scale 6 grows by +2,369, +5,733 and +5,122 on M1 (Europe, Atlantic, Old World)
  and by +6,848, +10,205 and +9,595 on M2, over the M2 allocation.
- Milestone `ridges`: cliff ridges along the 16 adopted ranges, the only cliffs on a Terra Nauvis
  world: `prototypes/tables/ranges.lua` (R7b's crest polylines, the 54 adopted passes at their
  approvals arcs, the 53 unnamed gaps the 400 km rule places at the middle of the longest straight
  piece of crest in each window, Europe's two map-edge openings, and the segments each map reads),
  written by the new `tools/build_ranges.py` from `approvals-data.json` and R7b; the cliff bodies in
  `prototypes/expressions/ridges.lua` in contour units (one contour 16.37 tiles out each side, so the
  frequency, continuity and richness sliders are inert; S5), rail-width openings as 20-tile slots
  across the crest (across the bend's bisector on a crest vertex, and on 24 tiles past a crest's end
  vertex), the ridge-free start disc `max(150, starting_area_radius) + 8` and an edge band
  where a cut range meets a map's edge; the startup setting Ridges (on; off gives 0 cliffs), baked per
  save as the name switch `tn_ridges` with the drift line; the cliff "none" reset in
  `scripts/start.lua`; the ore clearance that `data-final-fixes.lua` multiplies into the live
  probability of iron, copper, coal, stone, uranium and crude oil through each Earth preset's ore keys,
  reading a cheap crest band at each tile's centre in the Entity program, with no
  `cliff_removal_probability` edit; the water frequency slider's two vanilla
  readers, `segmentation_multiplier` and `nauvis_segmentation_multiplier`, stay group 0's
  `water_slider` constants on every Earth preset (T4; no pin bodies ship); `guards.earth_valued`, the
  D33 strip rule, with the static `d33_guard` row; the static `redefinitions` row (a mod Lua file
  defines each top-level function once, so a stale copy cannot silently replace one); the static
  `ranges` row; the runner's rows
  (`rd_dump_facts`, `rd_offline`, `rd_t4_fg`, `rd_t7_fg` in the gate; `rd_t6`, `rd_t6_start`, `rd_t4`,
  `rd_t7`, `rd_t8`, `rd_t11`, `rd_v2`, `rd_t15b`, `rd_t15e` in the suite), M1 against M0 and M2 against
  BAB wherever the criteria name M2; and the test mod `tools/mods/ea-path-probe` (T15e driver 2). The
  T1 previews without cliffs now also turn the ridges off.
- Evidence (draft, M1 on the draft's own isolated instance, through the runner's own row and check
  functions): against the build before it, every map's preset at scales 6 and 1 compiles Tile +0,
  Entity +1,098 and +1,086 on Europe, +1,961 and +1,949 on Atlantic, +1,591 and +1,579 on Old World
  (allocation +2,000), and Cliff 351, 706 and 526 at scale 6 (+64, +419, +239; allocation +1,300, P14
  2,000) and 336, 671 and 502 at scale 1. T6 at London's spawn: facing 0.9962 to 0.9973 and both-flank
  coverage 0.9426 to 0.9878 at scale 6, facing 0.9694 to 0.9792 and coverage 0.8741 to 0.981 at scale
  1; every opening at least 9.75 on nav.py walk (Cadibona at scale 1 listed as coastal); with every
  opening closed the sides never connect, open they do (the run's 96-tile end walls tested little of
  the Pyrenees at scale 1; re-evaluated offline on the run's retained dumps at London, Bern and
  Andorra, the walls sized from the ridge keep the sides apart and test 0.79 to 0.84 of each crest
  less its openings and wet ends at scale 1 and 0.91 to 0.98 at scale 6); the longest pass-free crest
  334.5 km; 0 cliffs beyond 48 tiles of a crest; rocks within 32 tiles 0.25 to 1.07 times the band
  beyond 48; ridges off 0 cliffs against 842 and 5,237 on. T6 at Bern and Andorra la Vella: 0 cliffs
  within 150 tiles, the ranges resuming beyond (106 and 1,665 cliffs at Bern, 12 and 624 at Andorra),
  coverage 0.9851 and 0.9313 at scale 6, the sides never meeting outside the openings. T4 at the Alps'
  Ligurian end, scale 6, the three seeds: the Earth preview stays byte-identical under water size none
  and 6 and the cliff sliders, the cliff signature identical; at cliffs none the start area holds 0
  cliffs (143 at normal) and the reset logs once and restores all 1,305 cliffs beyond it; water
  frequency moved the Earth preview at every seed, since vanilla trees (and on M2 Alien Biomes'
  shallows) read it through `segmentation_multiplier` and `nauvis_segmentation_multiplier`, which
  group 0's `water_slider` constants now hold on every Earth preset (not yet run in game on this view). T7 on 11 cities on or near crests
  (30 spawns at scales 1 and 6): 0 cliffs and 0 ridge cliffiness within 150 tiles. T8: 0 ore entities
  on a ridge cell at the three seeds at scales 1 and 6 (125 to 8,719 resources a dump), the
  vanilla-keys control 10,040 of 20,090, the default preset hash- and complexity-identical to M0. T11:
  an Alpine block keeps its 57 cliffs loaded with ridges off (fresh B 0), the drift line once. T15e
  driver 2 fires its trigger. On the final build `rd_dump_facts`, isolation (a) and
  (b) on every preset at scales 6 and 1, and the frozen row pass, and `rd_t4_fg` held every slider but
  water frequency before its readers were held constant, M0 changing under each. Offline after that run (no game):
  `earth_test.py static` passes 17 of 17 rows (187 fixture controls, the new `d33_guard` among them);
  `rd_offline` holds 31 of 31 checks and controls, among them the crest band mirror (0 of 8.2 million
  tile centres within the ore clearance outside the band on the three maps at scale 6), rd_geo equal
  to `oracle.place_tile` at pixel centres, and the live sample's P1 call resolving for every milestone
  whose timed_ss names t15b_m1. The M2 halves, `rd_t7_fg`, `rd_v2`, T8 on Atlantic and Old World, the
  timed T15 rows, the full T7 run, `baseline`, the suite and the gate remain for the build.
- Milestone `resources-enemies`: historical ore hotspots, offshore fields, a richness ramp, sparser
  base ore and heavier biters inside hotspots. `prototypes/tables/hotspots.lua` (the 77 adopted rows of
  APPROVALS 2 and 3: Europe 21, Atlantic 77, Old World 63, offshore fields included, each keyed by the
  region layer's hotspot row that holds its disc, with its strength, biter multiplier, radius and
  r + 50 km cap in reference pixels, and its land share per map), written by the new
  `tools/build_hotspots.py` and checked by the static `hotspots` row; `prototypes/expressions/
  resources.lua`: one spot noise per resource in its own `seed1` over its rows' footprints
  `min(max(r s, 48), cap s)` tiles (S6 A5 with the shared blob), each row's amount vanilla's patch
  amount at the candidate's distance times its strength and the ramp, spread over the land candidates
  of its start disc (`tn_land_coarse` above -4) with a region target equal to their sum, so rows
  sharing a region never draw on each other's target and the land share applies in game, size and
  richness acting and frequency inert; the richness ramp `1 + 0.5 clamp((d - 450) / 3550, 0, 1)` on the
  four solid ores; the random offshore-oil sea mask `tn_land_coarse < -7`; each map's offshore field
  stamp; `prototypes/expressions/enemies.lua`: S6 A6E's enemy layer (multiplier 4 inside each
  footprint, none within twice the starting area); each map's next elevation entry (Europe's v5,
  Atlantic's and Old World's v4; geography ids 11 to 13) composing the stamp last (`min(e, -6)` where
  the ground is water) through the map-qualified fallback key `tn_fields_<map>`, which a
  Map-type-only world follows with the hotspots setting under a drift line naming that setting,
  carrying the Map type fields; the wrappers in `data-final-fixes.lua` around the
  pack's live autoplace (ore probability v2 over ridges' v1, ore richness, `enemy_base_probability`,
  and the Oil Rig's offshore oil when it is loaded); the startup setting Ore hotspots (on), baked per
  save as the name switch `tn_hotspots` with the drift line; ore frequency 0.75 for the six base
  resources in every preset. The runner's rows: `re_dump_facts` and `re_t4_fg` in the gate;
  `re_t8`, `re_t8_base`, `re_t8_m3`, `re_t4_oil`, `re_t9`, `re_t4` (with M0 controls), `re_t7`, `re_t2`,
  `re_t11`, `re_t5` (waterways' T5 with the offshore stamps), `re_t15b` and `re_explore` (M1 against M0
  and M2 against BAB) and `re_t15e` in the suite; the Oil Rig's offshore-oil wrappers registered from
  the M3 dump with the live text masked, which the frozen row and `freeze` now produce; and the test mod `tools/mods/ea-polluter` (T15e driver
  1); a full preset MGS file now carries the preset's autoplace controls.
- Evidence (draft, M1 on the draft's own isolated instance): against the build before it, every
  map's preset compiles Entity +1,611 (scale 6) and +1,885 (scale 1) on Europe, +1,840 and +2,190 on
  Atlantic, +1,830 and +2,176 on Old World (allocation +2,300), Tile +80, +260 and +194 (allocations
  +200, +700, +500), Cliff unchanged; a 1,024-tile preview over Upper Silesia and Legnica at scale 6,
  seed 1000, holds 40.9 M of coal and 20.1 M of copper with hotspots on against 18.9 M and 13.7 M off,
  iron, stone and crude oil unchanged; every static row passes (187 positive controls). T8 on Europe,
  seed 1000, M1, passes at scale 1 (12 rows judged, 0.49 to 1.05 of their land-scaled targets, 83 to
  719 times vanilla's mean density; run before the density floor, which binds on no row at scale 1,
  the largest floor 0.17 of the strength term) and at scale 6 with it (15 rows, 0.47 to 1.48, 7.0 to
  259 times; the floor binds on 19 of 77 rows there), Entity 11,262 on Europe's default preset. The gate, the
  suite and the baseline are the build's: the workspace lock was held through most of the draft.
- Milestone `edge-and-lakes` (#TBD): each map's next
  geography version (Europe's v6, `tn_geo` 14; Atlantic's and Old World's v5, 15 and 16; every name its
  own, older versions unchanged) sinks land the map's box cuts into deep water across a noise-warped
  band 4 to 20 reference px inside the box (config.lua `coast.edge_band`: width 12 px, warp 8 px from
  three basis octaves of 32, 12 and 4 px, transferred as a second coast with the version's shore gains,
  so the cut reads as a wavy coastline with a beach and a deepwater line; the extent's ring of plain
  water is gone), and Europe's v6 reads its inland lakes through the new per-save toggle
  `tn_inland_lakes` (startup setting Inland lakes, default off; a folded `if()`, so off compiles to
  the spawn lake alone). T1 masks reference land within 21 px of the box (`edge_band_mask`, reported
  as `edge_band_share`), T2's seed comparisons mask it too, T3's far-field row reads the band at the
  box, and spawn-cities' T3 inland-lake rows run with the switch on. The runner's rows:
  `el_dump_facts` and `el_offline` in the gate; `el_lakes` and `el_edge` in the suite.
- Evidence (draft, isolated fh.py runs of this build against the draft base at seed 1000,
  `previews/earth-build/edge-and-lakes/r2/`): Tile +208 on every map with the switch on (Atlantic scale 4
  110,555, Old World scale 6 107,763, Europe scale 6 111,012; +67 on Europe with it off), Entity and Cliff
  unchanged; at the box every box-cut land line ends in water 4 px before it, the band's water edge 4.2 to
  20.3 px in, the previous version identical beyond the 21 px mask; switch off equals the neutral lakes
  body and switch on the previous version tile for tile in an inland window (2,119 lake tiles between
  them), and the spawn window is identical in all three. The edge band mask is 1.25 percent of Europe and
  under 0.01 percent of the other maps. The gate, the suite and the baseline are the build's.
- Milestone `destroyed-europe`: the optional Destroyed Europe zone. The startup setting Destroyed
  Europe (`terra-nauvis-destroyed-europe`, default off, APPROVALS 1a and 10), baked per save as the name
  switch `tn_destroyed`, on only with the setting and Alien Biomes (the toggle's new `requires` field;
  FEAS-17); `prototypes/expressions/destroyed.lua`: the zone `tn_destroyed_zone_v1`, the region layer's
  `tn_destroyed_depth_v1` (R7b's 14-vertex polygon less its six exclusion rows, edges moving with the
  seed) cut by the start disc `max(150, starting_area_radius)` around the spawn, its heat
  `tn_destroyed_heat_v1` (a heat-1 rim at 100.5 climbing over 61 tiles to a core near 130 that mixes Alien
  Biomes' four heat bands), and the Alien Biomes temperature's next version `tn_temperature_ab_v2`, which
  every Earth preset names with Alien Biomes and whose folded switch keeps climate-tiles' temperature with
  the zone off; `prototypes/tables/destroyed.lua`: APPROVALS 10's zone cities per map (Europe 7 of 40,
  Atlantic and Old World Prague); Europe's random pool `tn_city_pool_europe_v1` (spawn.lua), which a preset
  with the zone on and the spawn city at random bakes as the city number, so random never lands on a zone
  city while a chosen one still can; the D12 warning without Alien Biomes, logged at creation and sent to
  each created player through the stored-warning path; the drift line counts the pool as random and
  compares the toggle with its `requires` rule; four new bodies in `tests/frozen.json`. Runner: FG rows
  `de_dump_facts` (M1 and M2 dumps at the defaults and with the setting on: bodies, preset names, pools,
  registration, isolation (a) and (b) with the zone on, the zone-on M2 increment within 6.3's key-on
  allocation) and `de_pool` (offline: the table against the polygon, the pool's picks at T7's seeds);
  suite checks `de_t2` (with V3 renders), `de_t3`, `de_t7`, `de_t13`, `de_t18`, `de_t11` and `de_t15b`;
  `tools/oracle.py destroyed` writes the oracle's destroyed_zone expectations (the region expectation's
  `destroyed` key) and validate checks them. Climate-tiles' dump facts expect the next Alien Biomes
  temperature in every M2 preset, and the oracle control that turns trees-forests live keeps every later
  registry milestone live.
- Milestone `coast-band-fix`: Exact coastlines acts on no map yet: Europe at scale 1 and Old World at
  scale 6 await the four flip checks (handler time, desync, fidelity, prediction) in the milestone suite,
  and Atlantic, never priced, gets none. The startup setting Exact
  coastlines (`terra-nauvis-exact-coast`, bool, default off: design notes 13:45), whose tooltip names the
  maps it acts on; the per-save name switch `tn_bandfix` (`tn_one`), which a map's preset bakes only
  when the setting is on and config.lua's `bandfix.maps` lists the map, absent meaning off;
  `scripts/bandfix.lua`, the only per-chunk handler, registered from the save's own key in on_init and
  on_load and acting on Nauvis alone: the wrong tiles of the K pixels outside the half-pixel band (S12's
  closed rule), fill pixels whole and one-tile strips widened, never kept water,
  waterway footprints or the spawn keep disc; its drift line; `tools/build_geo.py emit --bandfix` with
  the offline pricing on the shipped bases (S12's method, the plan's T1 first) and one K+ table per map
  for every scale plus per-scale mask tables in `scripts/generated/`, priced in `data-src/bandfix/`; the
  rule's Python mirror (`build_geo.BandfixRule`); the T16 data-src rows for the tables; the FG rows
  `bf_dump_facts` and `bf_off` and the suite checks `bf_price`, `bf_t15`, `bf_t12`, `bf_t1c`, `bf_t1d`,
  `bf_slivers`, `bf_t11`, `bf_t5` and `bf_outcome`, with the test-only probe `tools/mods/ea-bf-probe`.
  Gate cold and warm wall time: not yet measured (the build records them).
- Evidence (draft, offline and on its own isolated instance,
  `previews/earth-build/draft-coast-band-fix/`): re-priced on the shipped bases with S12's method (band
  rule, fit alone, every scored pixel), Europe (8,258 terms) corrects 30.51, 12.80 and 6.98 percent of
  its chunks at scales 1, 3 and 6 with 26.3, 33.2 and 49.8 tiles per corrected chunk (p95 76, 102 and
  168; max 200, 334 and 515), as S12 priced the 8,192-term base; Old World's shipped 4,096-term base
  corrects 11.52, 4.62 and 2.69 percent with 74.9, 153.1 and 248.7 tiles (p95 214, 468 and 776; max 561,
  1,005 and 1,024), heavier per chunk than S12's 8,192-term estimate (62.0, 123.7, 203.3), which raises
  check (a)'s risk there; the K+ data is one K+ table per map, Europe 195,976 bytes and Old World
  748,965, plus per-scale mask tables of 64,605 and 171,918 bytes over the six scales (1,181,464 bytes
  for both maps, against about 5.2 MB as per-scale K+ tables). In game, the handler wrote exactly the
  tiles of its rule's mirror (1,212 in a Copenhagen square, 58,342 in the four S13 areas at scale 6, 0
  missing, 0 extra, 0 one-tile strips); the game's water correction left 25
  of 114,547 scored centres wrong there with the first tables, and the shipped tables, applied to the
  same fix-off tiles, leave 0 of 112,373.
- Milestone `compat-completeness`: no new feature. The suite rows that prove the mod against the maintainer's
  full pack, the base game's completeness rules, multiplayer determinism, the section 5 benchmark and
  Space Age: `cc_load` (T13 and D34: M0 to M6, BAB and BL each load through `dump-data` and `--create`
  with every mod's checksum line at R5's version, M4 to M6 holding every enabled live mod and none of
  the three disabled ones, the RSO warning once on M5, factorio-admin-command-center's regeneration
  off), `cc_t13_routes` (preset route equal to the full-MGS route on M3 to M6, every map),
  `cc_t13_zero` (a default world on M4 equal to BL's in every preview hash and program),
  `cc_t13_mods` (test notes 4.3's 17 interaction rows), `cc_t14` (minime's hidden surfaces on M4
  read the Earth map id as 0 or unrecognized, the unguarded copy beside minime as the positive
  control; the static walker on M1 and M2), `cc_t17` (every autoplaced vanilla name on every map on M1
  and M2, the block set calibrated on M0), `cc_t12` (twice, `--threads 1`, 8 LP, and the loopback save
  and load recipe with its bad probe on M1, M2 and M4), `cc_t15d_gen` and `cc_t15d_play` (T15d
  against vanilla, EarthMaps and Factorio World: forced generation at the spawn and 4,000 tiles out
  at 24, 16 and 8 LP, exploring in benchmark mode and in real time, the save pair, steady UPS, a new
  map's first 120 ticks and startup), `cc_t15_report` (each map's 16 LP headroom and the island-disc
  verdict, the next release input), and `cc_sa` and `cc_sa_more` (`tools/sa_compat.py` through the runner with
  its positive control and the engine-residue rule, then other seeds, scales and a chosen city, 491
  chunks per planet, Alien Biomes beside Space Age, cargo pod landings and the multiplayer recipe with
  the expansion on). The test-only probe `tools/mods/ea-cc-probe` (a census job, a surfaces job and
  T12's staged walker); `tools/mods/ea-sa-probe` gains a wide block set and cargo pod landings;
  `tools/sa_compat.py` gains a runner hook, variant staging and quick matrices. The pack-sized
  modsets are made per check and removed again. Gate cold and warm wall time: not yet measured (the
  engine records them).
- Evidence (draft, each check's run and derive code on its smallest case, game runs through the draft
  slots, `previews/earth-build/draft-compat-completeness/`): `cc_load` on M0 and M1 passes G1 to G3, every
  checksum line and the start message (`p2-cc_load-*`; the D34 counts fail only for the kinds not run);
  `cc_t12` on M1 passes whole: one checksum twice, with `--threads 1` and at 8 LP, 0 of 320 chunks
  differing, the loopback recipe's three paths on one checksum with equal storage, and the bad probe
  diverging (`p40-cc_t12-*`); `cc_t14` with minime in a small pack: minime's two hidden surfaces and the
  probe's control surface read the map id as unrecognized on Nauvis's Earth world, the control reads 1
  with the guard disabled, and the hook-aware walker holds on M1 and M2 with its three controls found
  (`p50-cc_t14-*`); `cc_t13_routes` on M3: the preset and full-MGS routes render the same preview on all
  three maps (`p22-cc_t13_routes-*`); `cc_t13_mods` on a 14-mod pack: the Alien Biomes, Big-Monsters,
  bobenemies and combat-mechanics-overhaul rows hold (hotspot boxes with hotspots on hold about twice
  the pack's enemies, 2,218 against 1,148, none in the start area) (`p31-cc_t13_mods-*`); `cc_t15d_gen`
  times the spawn block of Earth, EarthMaps and Factorio World and re-derives each repetition from its
  raw files (busy machine: every repetition is discarded for the other drafts' games, as the quiet
  window requires; read without that reason the per-chunk times give Earth 0.40 of EarthMaps' and 0.17
  of Factorio World's, UNVERIFIED) (`p20-cc_t15d_gen-*`); `cc_sa`'s judge rebuilt the 2026-10-28 run's
  report from its raw runs: the positive control holds on all four planets and the residue rule
  explains Gleba chunk (-3, 0) in the main and the travel comparisons. `cc_t17` fails on every map:
  the M0 calibration finds all 92 names, and the arid biome (red desert, its trees and decoratives)
  never generates on an Earth map (`p30-cc_t17-*`; design notes, compat-completeness).
- Milestone `extras`: the one-time extras. The runtime-global setting City markers
  (`terra-nauvis-city-markers`, default off, APPROVALS 1a, D28) and `scripts/markers.lua`: with it on, one
  rendering object in chart mode per city of an Earth world's map, the city's name at the tile holding its
  reference pixel centre (world = geo - the city offset read back from the save), drawn in `on_init` and
  drawn or removed when the setting changes; config.lua's `markers` group. The size context (D3, JI-12):
  every scale label, the scale tooltip and every preset description carry R8's two footprints, a 1k SPM
  factory core of 683 x 813 tiles and a 9.45k SPM megabase map of 10,000 x 6,000 tiles, called reported
  community examples, from config.lua's `size_context`, which the T16 locale row binds to R8, to
  approvals-data.json's world sizes and to every figure in those texts. One poster per map in
  `docs/posters/` (D30) from `tools/contact_sheet.py poster`, stitched from previews of the map's preset
  world at scale 1 and seed 1000, 2,400 px wide with a legend and scale bars. The T16 static rows
  `release_zip` (the release byte-reproducible, its `.sha256` matching, an unregistered body refused, the
  Map type fallbacks let through) and `tools_scan` (no graphical or portal flag and no map-export mod in
  tools/), with fixture controls for them and for the size context. Runner: the FG row `ex_static`; the
  suite checks `ex_t18_markers` (every map on M1, Europe at scale 1 and on M2, made with the setting off,
  Europe's Map type entry alone and the default preset, through `tools/mods/ea-marker-probe` appended to a
  staged copy), `ex_posters`
  (each poster's land equal to its map's V1 world's, the committed poster equal to a rebuild) and
  `ex_rename` (the D36 rename dry run under `earth-dry-run` and `edr_` with its own registry, tests/frozen.json
  unchanged). README.md stays the release handoff's. Gate cold and warm wall time: not yet measured (the
  engine records them).
- Evidence (draft, on its own isolated instances under `previews/earth-build/draft-extras/`, every game run
  RESULT ok, isolated=yes, errors=0). T18 (b) (`b30/mk-30-*`): Europe at scale 6, seed 1000 (offset 1239,
  3195), and at scale 1, seed 1002 (-856, 554), Atlantic (50 cities) and Old World (30) at scale 6, offset 0,
  and Europe on M2 at seed 1004 (2835, 2343): every city marked at its tile centre (0 tiles off), the offset
  read back equal to the oracle's model; none left after the setting went off at tick 2, in that same tick,
  and every city again after it came on at tick 4; a world made with it off showed none until then; Europe's
  Map type entry alone and the default preset, with it on, showed none. D36 (`b30/rename-30.json`): the test
  build `earth-dry-run_0.1.0.zip` changes only config.lua, info.json and the locale file, its M1 and M2 dumps
  show `Checksum of earth-dry-run` and hold no real name, all 832 bodies tests/frozen.json registers pass the
  frozen check under the registry built for the test ID, whose release passes and refuses a body dropped from
  it, and its Europe preset's 256 px preview at seed 1000 is the real build's byte for byte (6198d5600ad7f185)
  while its default preset's differs (b5ce38715e7fac56); tests/frozen.json is only read. V5 (`posters-1`,
  `posters-v1`): Europe 2,400 x 1,964 px from 1 preview, Atlantic 2,400 x 1,258 from 8, Old World 2,400 x
  1,826 from 6; each poster's land equals its V1 world's on every compared pixel (4,071,071, 102,281,169 and
  52,364,921; 0 differing; 18,529, 73,867 and 41,740 under cliffs), the V1 worlds scoring T1 0.991983,
  0.991262 and 0.991561. Static: locale, release_zip (`terra-nauvis_0.1.0.zip` reproduces; a dropped released
  body, a dropped firewall body and a registered fallback are refused) and tools_scan pass with 10 of 10
  fixture controls, the poster selftest 4 of 4; lint keeps the base's one W561 on presets.lua (design notes,
  extras). `baseline`, the suite and the gate remain for the build.

### Changed

- Destroyed Europe turns red: a macro noise over the depth gives a
  class per tile, so lava, black ash (`mineral-black-sand-1`, `mineral-black-dirt-1`), red rock
  (`mineral-red-sand-1`, `mineral-red-dirt-1`) and rim red grass (`vegetation-red-grass-1`) mix with no
  contour. The heat rises to a mean of 142 and starts 30 px in, so the rim keeps the climate's trees.
  Setting off: previews of all three maps hash the same as main. Heat-4 covers 16 to 28 percent of the
  land sampled; it walks at 0.7 and blocks nothing.
- Beside Alien Biomes the ground follows Earth's biomes instead of latitude alone: tile belts
  (`climate.tile_belts`) move only the fields tile scores read, so the Congo, the Amazon and South-East
  Asia are deep green, the Sahara golden with some red rock, Central Asia and the Gobi pale sand and
  gravel instead of one sheet of vanilla red desert, the Pontic and Kazakh steppes and the Great Plains
  dry yellow grass, Tibet cold grey, the Arctic pale tundra with snow in the far north and Greenland
  white. Orange grass is gone, ice keeps to the noise's lows, and temperate Europe keeps its tiles
.
- Regular ore patches on Earth presets read as natural mineral fields: lobed outlines with satellites,
  a few large fields among many small ones, gathered in provinces instead of an even spacing, and a
  richness plateau with pockets instead of a cone. Each preset redirects vanilla's patch expressions
  to an Earth copy, so default worlds, the wrappers and the pack's own patch settings are unchanged
  (`resources.natural`; a development branch).
- Hotspots listen only to the mod's settings: no map slider reaches them, and size none no longer
  removes them.
- A hotspot's ore never leaves its disc, at any scale, seed or amount; a row's disc is an exact circle
  of radius R about its centre, and the shaping happens inside it. Regular ore of every kind stays out
  of hotspot discs and different ores' hotspots never interleave, by a test on each spot's candidate,
  so the rules add almost nothing per tile.
- Hotspot jitter is halved, so a disc stands at most a quarter of its radius off its real site.
- Mountain ranges read as highlands, not as a cliff line on grass: big rocks thicken round each range,
  wider and stronger the taller it is, and clear of its passes and of every start;
  the ground leans to dry dirt, and beside Alien Biomes the tops of tall ranges turn to grey ground and
  snow. Tile scores alone read the lean, so the forests on the slopes stay
  (`ridges.high`, `ridges.ground`, `ridges.rocks`; design notes 2026-10-30 18:00, a development branch).
- The map's outline reads as a natural ocean margin at a far map view: where the box cuts land (Europe's
  North Africa, Russia and Anatolia, and Chukotka on Atlantic and Old World) land ends in bays and
  headlands up to a few hundred tiles deep at scale 6, instead of a thin wavy strip following a straight
  box. Each side has a margin table, so Cyprus, Ireland, the east end of the Black Sea, the lower Don and
  every spawn city keep their ground at every seed (`coast.edge_band.outline`; design notes 2026-10-30 17:35,
  a development branch).
- Europe's coast is one crisp line too: its geography reads the fit through the coast warp, which ends the
  dark spray on cold coasts, with a thinner shallow rim. Its land agreement with the reference moves from
  97.68 to 97.65 percent at scale 1 (`coast.warp`; design notes 2026-10-30 17:40, a development branch).
- The soft map edge's strip holds no flat run on Europe and Atlantic: the warp's sum folds back at its bounds
  instead of clamping there (`coast.edge_band.fold_geographies`).
- On Atlantic, Exact coastlines takes written land from a lattice shared across chunk borders and from the
  chunk's corners, so it draws no rectangles of one tile along chunk borders (`bandfix.smooth.corners`).
- Small marshes on Europe and Atlantic read the shared roughness harder, so the Danube delta's outline is no
  disc edge. No noise call is added and Old World keeps its bodies' values (`regions.marsh.edge_gain`).
- Old World's and Atlantic's coasts are crisp lines: their geography versions read the coast fit at
  warped coordinates instead of adding the lattice detail, which dithered a low-slope fit into a band
  of speckles up to 24 tiles wide, and their shallows narrow to a rim like Europe's. Europe's map is
  unchanged (`coast.warp`; design notes 2026-10-30 13:30, a development branch).
- Beside Alien Biomes, temperate ground keeps the base game's plants: every vanilla decorative and dead tree
  reads the vanilla-scale temperature and the base game's own score where vanilla land lies, and the restored
  trees also stand on the adopted Alien Biomes tiles. Brown asterisks no longer carpet the ground outside it
  (`trees.decor`; design notes 2026-10-30 18:40, a development branch).
- Exact coastlines acts on Old World and Atlantic and is on by default, visible in the settings menu.
  Atlantic gains K+ tables. The handler queries only wrong tiles, evicts its row cache one row at a
  time, and writes along a blurred, wobbling reference instead of the raster's stairs; written land
  takes the ground around it and false islands sink into deep water.
- Land Exact coastlines writes takes the trees, rocks and decoratives of the land beside it, so a written
  coast no longer runs as a bare strip: `scripts/coastcover.lua` reads a rate and a sample from the chunk and
  draws per tile with a generator seeded per chunk.
- `tools/build_geo.py emit --map <map> --bandfix --masks-only` rewrites the mask tables from the
  committed K+ table in about a minute, for a change that moves waterways only.
- Exact coastlines holds every shore to the reference alike: the write band narrows from half a pixel
  to about a fifth, K covers every coast pixel, the sea's thin water opens as channels and inlets, and
  islets the raster lost return from a vector coastline (`tools/build_islets.py`,
  `data-src/bandfix/islets-<map>.json`; design notes 2026-10-30 17:40, a development branch).
- Beside Alien Biomes, the combined build's razor edges are gone:
  the climate grain's weight reads the temperature, so a cold spot in temperate land frays; a marsh has no
  dark rim of one width and its edge wanders with the pools; aux folds back at its cap, so dry land keeps
  its tile mix; natural moisture stops at 0.92, so forests fill in instead of ringing a moisture peak.
- Destroyed Europe's start disc has an irregular edge and only widens past its 150 tiles.
- Old World's and Atlantic's vanilla land tiles each add a noise of their own beside Alien Biomes, so dry land
  is a patchwork instead of concentric bands with an even dark rim. Europe keeps its look.
- A river thins to a stream at its source instead of ending in a round finger, on all three maps.
- Beside Alien Biomes an Earth preset's land tiles read two of twelve shared noise fields instead of a
  six-octave noise each, which takes Old World's Tile complexity at scale 6 under the generation cost
  knee. Land and water do not move. The patches of Alien Biomes ground keep their size and look and fall in
  new places. A world without an Earth preset is unchanged (`tiles.noise_share`; design notes 2026-10-30
  17:20, a development branch).
- Rivers scale down with the map below the boat floor. A river is `max(3, k s)`
  tiles wide, k 3 for a major river and 2 for the rest, so scales 1 to 3 draw rivers of about 3 to 9
  tiles where they drew 11; only scale 6 still carries boats everywhere, and its waterway sets do not
  change. Fords shorten with the scale and a river under scale 4 takes no turning basin (design notes
  2026-10-30 16:45).
- Rivers, lakes and turning basins read as natural water on all three maps (on the
  Europe map: "way too perfect", "rectangles of water at places"). The rectangles were the turning
  basins, 30 x 30 Chebyshev squares; the Rhine's pair sat on an out-and-back hook in S4's route. The
  lines were the raster's octilinear path barely smoothed. `tools/build_waterways.py` (emitter 3) now
  cuts such hooks, smooths a river by at least 12 reference px, simplifies it with a tolerance that
  follows its bends and draws a basin as a short capsule on its course; a river's half-width follows a
  profile from source to mouth, with a tapered source. `waterways.lua` reads every set through one
  shared domain warp of the geo tiles (three octaves, faded out around the spawn), a low-frequency
  width noise and a fine bank noise, so the banks wander and stop being parallel for nine noise
  evaluations per tile, not per segment. Fords read the same warp, so they stay on their rivers, and
  they have rough edges, jittered spacing and keep out of a basin's pool. The longest straight segments
  take bends.
  Straits, canals and dams read a lighter warp. The coast fit's own discs on a river's course are
  filled (20 ponds on Old World, 7 on Europe, 5 on Atlantic). The start lake and the inland lakes get
  a warp of their own, and inland lakes vary in size. Old World at scale 6 ships 926 river segments
  against 1,339.
- One geography version per map: Europe v6
  (tn_geo 14), Atlantic v6 (17) and Old World v6 (18) stay, every superseded version goes, and the
  map-wide layers read those versions' chains. 442 bodies dropped, 18 re-registered, config.lua down by
  a third, noise text 6.50 MB to 3.55 MB. Time to load mods falls from 12.0 s on main to 2.81 s (median of three alternating runs, game at HIGH priority, on a machine other work kept loaded; vanilla 0.52 s). 36 of 36 previews (three maps, scales 1 and 6, three
  windows, base and beside Alien Biomes) are pixel-identical, and Tile complexity falls by 8 to 16.
- Until the first release, `tests/unreleased-moves.json` names every landed record that moved and
  `tools/refreeze.py` writes it with the registry from fresh dumps; the append-only row, the release
  build and a landing excuse a record only at a listed hash, and a release tag voids the file. The
  release input checks read release tags only.
- The climate noise (temperature, moisture, aux, fallback and Alien Biomes) takes a seed1 shift folded
  from the city offset, so each spawn city of a seed has its own tile texture, at no per-tile cost
.
- A startup toggle's drift line for Great forests, Ridges, Ore hotspots and Destroyed Europe says the
  setting applies to new worlds only (`drift-toggle-new-only`; audit minor).
- The north without Alien Biomes: the fallback climate (shared by the three maps) keeps
  the boreal belt moist and warm enough for vanilla's cold trees up to a treeline near 70N, pulls the
  cold aux low, and the great-forests hook gains a boreal lift (`tn_tree_lift_v1`) for the base game's
  living trees only. Old World at scale 6, seed 1000: sand in Siberia 21.7 to 0 percent, under 1 percent
  in Scandinavia, and the taiga windows go from 1 to 4 preview trees a chunk to 136 to 148 in Siberia
  and 80 in Scandinavia (Alien Biomes' own taiga: 110 to 129). Beside Alien Biomes the map is nearly
  unchanged; the Moscow window gains about 23 percent preview trees; a non-Earth world is byte-identical.
- Startup: each repeated geography body is defined once per chain class. Versions of
  a map with the same city offset (Europe 3 to 6 on the city fold; Atlantic and Old World 1 to 5 at
  0) read equal geo tiles in every world, so the newest version of a class keeps the coast fit,
  coarse land field and waterway sets and every older one names them (coast.lua, waterways.lua);
  the versions landed on main (geography 1 and 2) keep their own. The dumped noise text drops from
  13.5 MB to 5.64 MB and "Time to load mods" from 8.24 s to 3.22 s (median of six alternating runs,
  game at high priority, on a machine other work kept busy; vanilla 0.46 s), about 6.85 s to 2.7 s
  on a quiet one, short of the 2 s target. 238 bodies re-registered from
  a fresh M1 dump; 24 previews of the three
  maps at scales 1 and 6 (two preset windows each and an old Map type entry) are pixel-identical
  with unchanged Tile, Entity and Cliff complexity on every preset.
- The startup setting Exact coastlines (`terra-nauvis-exact-coast`) is hidden (`hidden = true`,
  default still off, the handler and its tables kept): `bandfix.maps` is empty, so it acts on no
  map and a visible switch would mislead. settings.lua now passes a setting's `hidden` field.
- Old World's coasts of Britain, Ireland, the Channel, Denmark and the Baltic: its coast fit grows from
  4,096 to 8,192 terms with Europe weighted 16 times, so the new terms go to Europe's coasts (Europe
  box agreement 0.973 to 0.988, worst coast error in Britain 10.5 to 3.5 px); the rest of the map
  keeps its coast and the coarse land field is unchanged.
- Live-profile protection is fh.py isolation alone (the decision, 2026-10-27 16:19 and
  23:47; design notes 2026-10-28 00:45): G1 (RESULT `ok`, `isolated=yes`, `errors=0`) is the only
  live-profile protection, and copying the built zip into the live mods folder is allowed.
  `tools/build_zip.py --out-dir` takes any folder, the live mods folder included. Design constraint 1
  in all ten args objects of the design notes section 20, project rule 2, sections 1, 4, 5 and 7, the
  part 10 live-profile-safety lens, ARCHITECTURE.md, test notes.md and the release-ops parameters
  say so. The workspace lock, G1, G8 and the stop of every further game run after a run that may
  have left its instance stay.
- The runner's game build pin (G8) moves to Factorio 2.1.24 build 87808 after Steam's 2026-10-29
  update: `tests/baselines/build-87808.json` and
  `tests/budgets.json` re-measured equal to 2.1.23's in every value, both group suites re-recorded
  (every deterministic check equal to its 2.1.23 record), the gate cold and warm and `install-check`
  pass on 2.1.24 with no body re-registered.
- The gate re-derives the suite evidence of every milestone it lands (design notes 2026-10-29
  11:05): through a milestone, each pending milestone (the gated one and every earlier milestone that no
  reference ref has landed) gets its own `suite_evidence:<id>` row, held to its own manifest with
  its own refresh command; the live sample is drawn over all their checks, and a deterministic live
  sample must equal its re-derived evidence exactly. The build runs only a group's last
  testCommand, so `gate --through spawn-cities` now holds `europe-coast`'s suite evidence as well; a
  landed milestone's evidence is never re-derived. To keep the cold gate inside rule 4's 8 minutes with
  the larger live pool, `tools/oracle.py` parses the city table once per file content
  (`city_table`), which cut the re-derivation of `spawn-cities`' evidence from about 20 s to under
  8 s, and `tools/tn_static.py` keeps each Lua file's parse per text as `tools/tnlua.py` already did,
  which cut the static rows (CI's `static` and the gate's first row) from 66 s to 19 s (the fixture
  controls, which re-parse the mod in every copy they edit, from 55.5 s to 12.9 s), with every row
  and control unchanged.

### Removed

- Geography versions 1 to 5 of each map (tn_geo 1 to 13, 15 and 16), start mask version 1, and the
  chain class routing and layer chain redirect that served them.
- The river-safe starts files `prototypes/generated/starts_<map>_v1.lua`: no code read them, and Old
  World's file still held Prague's old grid point and lacked Frankfurt, Aachen and Moscow.
  `build_waterways.py` no longer emits them; the manifests keep each city's per-scale start record.
  Prague at scale 1 and 6 spawns with no water within 12 tiles.
- The placeholder Terra Nauvis: Europe preset, its two noise bodies, its config group and every
  placeholder text; the gate's `ab_placeholder` row passes noting its retirement.
- The chained G9 guard (snapshot and check, part chaining, the stale build-log check, the journal)
  and `earth_test.py guard-rebaseline`; the guard-bracket token that `game_selftest.py`,
  `dump_render.py run`, `oracle.py probe` and the kill probe checked; the write guards
  (`tnguard.live_output_problem`, `refuse_live_outputs` and the option declarations) in every tool;
  the T16 launch scan and output-options row with their fixtures; and the gate's `fh_flags` row with
  `tools/lint/fh-flags.json`. Evidence, with the plan still at `main`'s copy (its revision
  fails the gate's `plan_main` row until it lands; design notes 2026-10-28 00:45): `baseline`,
  `suite toolchain` (371.6 s), `gate --through toolchain` (warm, 19 rows, 125.9 s) and
  `install-check` pass (`previews/earth-build/baseline/20261028-004908-toolchain`,
  `suite/20261028-004927-toolchain`, `gate/20261028-005558-toolchain` and
  `install-check/20261028-005821-toolchain`, under `%FACTORIO_WS%`); the zip's sha256 is unchanged
  (db639d10); T16 runs 13 rows with 161 of 161 fixture controls, and the runner 64 of 64 controls.
