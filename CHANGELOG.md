# Changelog

All notable changes to terra-nauvis are documented in this file. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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

### Changed

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
