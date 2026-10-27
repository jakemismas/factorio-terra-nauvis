# Architecture

Binding design for Earth Atlas (mod ID `earth-atlas`) in the first release: Factorio 2.1.23 (build 87750),
base game, Alien Biomes 0.8.0 optional. The disagreements with the earlier design notes found while writing this file are listed in "Conflicts and open items". This file is
living: during a build it changes only through fit-review patches folded in at a milestone commit, and
whenever a milestone changes a binding contract (Universal Definition of Done).

Conventions. Every measured fact carries a source tag that the Sources table at the end resolves to
a path. "est." marks an estimate, "derived" marks arithmetic on cited numbers, and UNVERIFIED marks
a claim no run settled. TQ2 tags the Phase 4 quiet-window benchmark, whose numbers filled every
starting value that waited for it; the values in force live in the plan's section 6.
Names use the default prefixes (`earth-atlas` for the mod, settings and presets; `earth_` for noise
names). `prototypes/config.lua` owns the real strings. LP means logical processors. Milestone numbers
here run 0 to 14 in build order; the plan numbers milestones per part, so a milestone id (`waterways`) is the
stable reference. Revised after the design review: "decision n" cites the binding decisions in
the design notes.

## Overview

```
BUILD TIME (tools/)             DATA STAGE (every peer)           GENERATION (every peer, engine)
data-src/earthmaps rasters      settings.lua                      Tile program
  build_geo.py --------+        data.lua: Earth named               elevation: coast fit, waterways,
curated waterway lists |          expressions and three             lakes, far field (Tile only)
  build_waterways.py --+-->       presets, per-save values baked    climate, tile scores
prototypes/generated/*.lua      data-final-fixes.lua: wrappers    Entity program
prototypes/tables/*.lua --->      around live autoplace, gated      trees, ore, enemies, oil;
  (approval data)                 hooks on shared prototypes        land from earth_land_coarse
tests/frozen.json <-- freeze                                      Cliff program: ridges
                                CONTROL (every peer, main thread): one-time events; per-map band fix
```

- **Data stage.** Builds every Earth named noise expression and three map-gen presets (Earth:
  Europe, Earth: Atlantic, Earth: Old World). A preset bakes every map-shaping value (map, scale,
  city, geography release, toggles) into `basic_settings.property_expression_names`, so a save keeps
  its map for life whatever the startup settings say later (S2).
- **Generation.** The engine compiles what the chosen preset reaches into its Tile, Entity and
  Cliff programs and runs them on worker threads; every peer generates every chunk itself, and the
  results are applied inside the game update (R8). A default-preset world compiles none of it (S3,
  S10).
- **Where the cost sits.** The coast fit is the one expensive term (Europe at 8,192 terms: Tile
  complexity 82,139 est. against vanilla's 10,068; S1-fit; 73,296 over a constant-coast twin, S9). It
  lives only in the Tile program. Entity and Cliff read cheap shared fields, because any per-tile
  reader there compiles the fit a second time (TQ1b); their one land field is `earth_land_coarse`, a
  separate 256-term fit.
- **Control stage.** One-time work only: world detection, the start message, warnings at creation
  and to each created player, guards, the cliff "none" reset, and map markers when their setting
  changes. No `on_tick`, no `on_nth_tick`; `on_chunk_generated` exists only in the band fix, and only
  on saves whose map's preset carried the band-fix key.
- **Tooling.** `tools/earth_test.py` is the gate: one command under 10 minutes per milestone,
  thresholds parsed from the plan's threshold table, a live-profile guard around every
  command that launches the game. It runs the game only through the workspace's `fh.py`,
  isolated from `%APPDATA%\Factorio`.

## Module map

Repo paths are relative to the repo root; mod files live under `earth-atlas/`, the zip's root folder.

| Path | Responsibility | Contract it exposes | First milestone |
|---|---|---|---|
| `earth-atlas/info.json` | Identity and dependencies: `base >= 2.1.23`, `? alien-biomes`, `? cargo-ships-oil-rig`, `? rso-mod`; `factorio_version` "2.1" | name equals the config ID; title at most 100 characters; no Space Age feature flag (mod-dev rule 4) | 0 |
| `earth-atlas/settings.lua` | Startup: scale (string values "1" to "6", default "6"), spawn city per map ("random" plus city keys), toggles hotspots, great-forests, ridges, canals, destroyed-europe. Runtime-global: city-markers | values are short ASCII tokens, so labels can change without invalidating stored values (S11); names and defaults from config | 0; cities 2; each toggle with its milestone |
| `earth-atlas/data.lua` | Requires config, tables, every released generated file and the expression modules; defines the Earth named expressions; builds the presets | `data:extend` only on Earth names, never on another mod's or vanilla's names | 0 |
| `earth-atlas/data-updates.lua` | Empty in the first release; reserved for edits that must follow every mod's data.lua and precede every data-final-fixes | none | 0 |
| `earth-atlas/data-final-fixes.lua` | Everything that reads other mods' final state: entity wrappers (ores, enemies, offshore oil), gated hooks on shared prototypes (vanilla tiles, trees, rocks and decoratives beside AB; marsh tiles without AB; forest boost; AB palm switch; the Earth-gated ridge exclusion on ore probability) | hooks follow the stable-hook rule (Expression graph) | 6 |
| `earth-atlas/control.lua` | Event wiring only | registers exactly the events in "Control stage" | 0 |
| `earth-atlas/locale/en/earth-atlas.cfg` | Setting names and descriptions; `[string-mod-setting] <setting>-<value>=<label>` for every dropdown value, with world size; preset names and descriptions; messages | every used key exists; no line without `=` (a missing `=` fails the load, S11) | 0 |
| `earth-atlas/changelog.txt`, `LICENSE`, `thumbnail.png` | Factorio changelog, GPLv3 (EarthMaps data reuse), thumbnail (later) | | 0, 13 |
| `prototypes/config.lua` | The single source of names and constants (table below) | pure data: reads no `data`, `settings`, `game` or `script`, so the settings, data and control stages and the Python tools (through a luaparser loader) read one file | 0 |
| `prototypes/presets.lua` | The three presets from config, `settings.startup` and `mods` | the redirect table under "Expression graph"; AB keys only with AB loaded, Oil Rig keys only with the Oil Rig | 0 (placeholder), 1 |
| `prototypes/expressions/coast.lua` | Coordinate chain, coast transfer, lattice detail, far-field box, elevation composition; the coarse land key `earth_land_coarse` | the firewall names: Tile only; `earth_land_coarse` is the one land field outside Tile | 1 |
| `prototypes/expressions/spawn.lua` | City fold, random pick, spawn offsets, spawn lake, inland lakes, `distance`, start mask | `earth_cx`, `earth_cy` and the city index readable at (0, 0) | 1, 2 |
| `prototypes/expressions/climate.lua` | Temperature, moisture and aux (AB and fallback variants), vanilla-scale temperature, slider hooks, marsh and destroyed-zone lifts | firewall-clean: Entity reads it through AB trees | 6 |
| `prototypes/expressions/regions.lua` | Region layer, S10 design (d): table rows, the shared warp, per-region outputs and layer aggregates (section "Region layer") | consumers read only the interface names; no region formula anywhere else (S10) | 5 |
| `prototypes/expressions/tiles.lua` | Bodies behind the tile hooks: vanilla tiles beside AB, marsh tiles | | 6 |
| `prototypes/expressions/trees.lua` | Restored vanilla tree bodies, forest-boost multiplier, AB palm switch | | 6, 7 |
| `prototypes/expressions/resources.lua` | Ore wrappers (richness ramp, hotspots), offshore-oil wrapper, offshore field stamps | | 9 |
| `prototypes/expressions/enemies.lua` | Enemy-layer wrapper | | 9 |
| `prototypes/expressions/ridges.lua` | `cliff_elevation` and `cliffiness` from the ranges table | slider-proof, contour units (S5) | 8 |
| `prototypes/expressions/destroyed.lua` | Destroyed-zone consumers: temperature lift, start mask, random-pool switch | | 10 |
| `prototypes/expressions/waterways.lua` | Loads the generated waterway sets; canals and dams switch | | 4 |
| `prototypes/generated/` | `geo_<map>_v<n>.lua`, `coarse_<map>_v<n>.lua`, `waterways_<map>_s<k>_v<n>.lua`, `bandfix_<map>_v<n>.lua` | machine-written; the header records tool version and input sha256; never hand-edited; one file per released version | 1, 3, 4, 11 |
| `prototypes/tables/` | `cities`, `hotspots`, `forests`, `ranges`, `canals`, `marshes`, `regions`, `destroyed`: approval data in degrees, with sources; hotspot rows take the adopted centre (`lat`, `lon` in `approvals-data.json`), which decision 16 moved inland for one hotspot | versioned by release (copy-on-write after a release) | per milestone |
| `scripts/start.lua` | `on_init`: world detection, storage, D29 message, cliff "none" reset, D12 and D32 warnings logged and recorded in `storage` for the per-player path | | 2, 8 |
| `scripts/guards.lua` | Missing-name guard, drift line, D33 surface guard, per-player RSO and Destroyed Europe warnings (`on_player_created`) | | 1, 2 |
| `scripts/markers.lua` | D28 city markers | no per-chunk event | 13 |
| `scripts/bandfix.lua` | Tolerance-band coast fix | the only per-chunk handler | 11 |
| `tools/earth_test.py` | Runner: `gate --through <milestone-id>` (each milestone's testCommand, under 10 minutes), `suite <milestone-id>` (full variants into the content-hash cache), `install-check`, `baseline` and `freeze` commands | finds fh.py through `FACTORIO_WS` (default `%FACTORIO_WS%`) and refuses to run without it; never writes tracked files while gating; trusts no verdict file, only cache entries whose key it recomputes; parses the perf thresholds from the plan's threshold table; a guard snapshot and check around every command that launches the game | 0 |
| `tools/build_geo.py` | Tents fit and emitter | reproducible emission (Build-time data flow) | 1 |
| `tools/build_waterways.py` | Waterway vectorisation, per-scale smoothing and simplification | | 4 |
| `tools/build_zip.py` | Packaging; `--release` | byte-reproducible zip; `--release` refuses an Earth body missing from tests/frozen.json, which every milestone from `europe-coast` on keeps complete, so it works at any point of the release | 0 |
| `tools/t1_metrics.py`, `oracle.py`, `dump_render.py`, `contact_sheet.py`, `nav.py`, `earthgeo.py` | S8's tools with their self-tests; `earthgeo.py` holds the pixel conventions | conventions equal config.lua's | 0 |
| `tools/perf.py` | T15 timing: TQ1b block, 8 LP affinity, quiet-window protocol, census check | | 0 |
| lint config | selene or luacheck installed per user (version recorded), luaparser 4.2.0 as the syntax floor | | 0 |
| `data-src/earthmaps/` | Decoded rasters, reference JSON, provenance, GPLv3 notice | read-only tool input | 0 |
| `tests/` | `oracle/<map>.json`, `budgets.json` (measured values only, never thresholds), `frozen.json`, `baselines/` | the gate reads main's committed copies | 0 |
| the design notes, `docs/posters/` | Plan documents; posters (D30) | | 13 |

`prototypes/config.lua` holds:

| Group | Contents |
|---|---|
| Identity | mod ID, title; setting, preset, expression and locale prefixes |
| Maps | key (`europe`, `atlantic`, `olde_world`; settings say `old-world`, APPROVALS 1a), preset name, display name, raster size, `wr` and `hr`, georeference, world size per scale |
| Scales | 1 to 6, default 6; the coordinate-chain constant `floor(s / 2)` |
| Toggles | setting name, preset key, default, mechanism (name switch or hook gate), on and off values |
| Keys | every `property_expression_names` key any Earth preset sets (D33 guard, missing-name guard, T14) |
| Release registry | per release: geography id, every released name, the generated files it loads |
| Tunables | transfer gain and sign offset, detail amplitude, ramp, hotspot and enemy constants, every `seed1`, ore frequency 0.75, the forest boost (2; a per-family data value), the random-oil sea threshold on `earth_land_coarse`, the band-fix default per map |

## Build-time data flow

1. **Reference.** EarthMaps (GPLv3, `HySpeed/EarthMaps` commit `23c647b8`, world and city files with
   their sha256 in each map's JSON) is decoded by S8's `earthmaps_decode.py` (version 1) into
   `data-src/earthmaps/<map>-classes.png`, `<map>-land.png`, `<map>-thinwater.png` and `<map>.json`
   (plate carree at 45 px per degree, edges, `wr` and `hr`, cities, thin water, coast statistics).
   Sizes: europe 2400 x 1704, atlantic 15689 x 6524, olde_world 8963 x 5847 px; Europe is an exact
   crop of the Atlantic raster (S8 reference JSON). Committed once with a provenance file and the
   GPLv3 notice.
2. **Coast fit** (`tools/build_geo.py`, S1-fit's method). Target: the signed distance soft-saturated
   as `4 * tanh(sdf / 4)` px, thin water filled as land with weight 0; tents on dyadic grids from 1 to
   1024 px; greedy selection growing 1.25 times per step; one-sided refit. Europe and Olde World start
   from the existing 8,192-term checkpoints (offline, thin water excluded: Europe 99.184 percent, Olde
   World 99.300 percent; the build's T1 also masks waterway corridors and lake footprints, REVIEW;
   S1-fit). Olde World is refit at growth 1.25 for
   the smallest checkpoint at or above 99.1 percent; Atlantic gets its first full or 2x fit with the
   same rule (milestone 3). Output: `prototypes/generated/geo_<map>_v<n>.lua`, one scale-independent
   named expression per map that reads the coordinate chain, with row and column factors as shared
   local expressions and balanced parenthesis trees (S1-fit: 131,072 terms compiled and rendered, 4.2
   MB of data.lua), coefficients printed as float32 `%.9g`. A manifest beside it records terms,
   offline T1 numbers, input sha256, fit parameters, emitter version and output sha256. Emission is
   reproducible: the same model gives byte-identical Lua, and the gate re-emits from the committed
   model and compares. A refit is a manual, recorded tool run. The same tool emits each map's coarse
   land field from the 256-term checkpoint of the same fit (S9 used Europe's `model-256.npz`, 94.5
   percent offline): `prototypes/generated/coarse_<map>_v<n>.lua`, scale-independent, reading the
   coordinate chain, in the same reference-pixel units. Europe's lands in `europe-coast`,
   the other two with their fits in `olde-world-atlantic`; its checkpoint is committed under
   `data-src/fits/` beside the shipped model.
3. **Waterways** (`tools/build_waterways.py`, S4's method). Least-cost paths through thin water
   between snapped waypoints, extended through drawn water to open sea at least 6 px from land, land
   gaps bridged. Per scale: smoothing until no 17-tile stretch turns more than 90 degrees, then
   Douglas-Peucker at 2 tiles (scales 1 to 3) or 3 tiles (4 to 6), and turning basins where the bend
   rule still fails (Dardanelles at every scale; Rhine, Garonne and Little Belt at 6). Half-width
   `hw(s) = max(F / 2 + 0.25, 0.5 s, 0.5 w s / 2.471)` tiles, `F` 7 for one track and 11 for the
   two-way straits; canals `max(7, s)` wide (APPROVALS 6); dams `max(1.5, 0.5 s)` (S4). Output:
   `waterways_<map>_s<k>_v<n>.lua` for k = 1 to 6, with separate named sets for rivers and straits,
   canals and dams, plus a manifest with segment counts, bend-rule results and the T1 corridor masks.
4. **Tables.** `prototypes/tables/*.lua` hold approval data in degrees. The data stage converts them
   into the coordinate chain's frame with the reference JSON's pixel-centre formula
   (`lon = lon_left_edge + (col + 0.5) / 45`), through one shared number formatter so strings are
   byte-stable.
5. **Data stage.** `data.lua` loads every generated version the release registry lists (old versions
   stay loadable), then builds expression strings from the tables. Unused expressions are parsed but
   never compiled (noise rule 9).
6. **Freeze.** From `europe-coast` on, the milestone that adds a versioned Earth body registers it:
   `earth_test.py freeze` appends the sha256 of every new Earth named expression and noise function,
   as `--dump-data` writes them on M1 (and on M2 for AB-only bodies), to `tests/frozen.json` (decision
   21). It never changes an existing entry. The gate fails when a registered name is missing or its
   hash changed, so `build_zip.py --release` finds every body at any point of the release.
7. **Package.** `build_zip.py` writes `earth-atlas_<version>.zip` with one top folder, fixed
   timestamps and entry order: two builds give one sha256 (T16).

Generated files are rebuilt by their tool in the same commit as the change that needs them, and never
edited by hand.

## Coordinates and names

### The coordinate chain

Defined once (`coast.lua`, offsets in `spawn.lua`), mirrored by `tools/earthgeo.py`, shared by every
module:

| Name | Expression | Source |
|---|---|---|
| `earth_cx`, `earth_cy` | if() chain over the map's city table on `earth_city` (0 picks the folded hash of `map_seed`) giving `s (c - wr) + floor(s / 2)` for the city's pixel column c, the tile holding the city's pixel centre (S8 oracle convention), and the same for rows; folds to two constants | S7: Tile 9,350 for 1, 30 or 50 cities and for random; 10,039 for the same chain evaluated per tile |
| `earth_gx`, `earth_gy` | `x + earth_cx`, `y + earth_cy`: the chosen city sits at world (0, 0) | S7 (spawn by shift) |
| `earth_u`, `earth_v` | `(earth_gx - floor(earth_scale / 2)) / earth_scale + wr`, the same with `hr`; `wr`, `hr` folded from `earth_map` | derived below |

Frame: pixel centres sit at integer `u`, `v` (S1-fit's model frame). T1 scores with the floor
convention: at scale s, pixel c covers tiles `s(c - wr)` to `s(c - wr) + s - 1`, a pixel is
represented by the tile holding its centre, and the game evaluates a tile at its integer corner
(S8: 28 of 262,144 tiles disagreed with corner sampling, 563 with centre sampling). The
`floor(s / 2)` term makes that corner read the fit exactly at the pixel centre at every integer
scale (derived). S1-fit's emitter maps tile x to `u = x / s + wr`, EarthMaps' own placement, which
S8 measured half a pixel off the floor convention; against this chain it is off by `floor(s / 2) / s`
px: 0 at scale 1, the only scale S1-fit ran in game, and 0.5 px at scale 6. S10 and S1-cloud used
pixel-edge coordinates (`+ 0.5`); the build keeps one frame.
Noise calls keep `x = x, y = y` and take scale and shift through `input_scale`, `offset_x` and
`offset_y` (noise rule 8; folded per-save numbers fill those constant slots, S2 Q4 and S7). The
constant lives in config.lua and earthgeo.py only; milestone 1 proves it with T1 at scales 1, 3 and 6.

### Naming

| Kind | Pattern | Example |
|---|---|---|
| Setting, preset | `earth-atlas-<name>`, `earth-atlas-<map>` | `earth-atlas-scale` |
| Per-save number (no prototype) | `earth_<param>` | `earth_scale` |
| Hook gate (prototype "0") | `earth_on`, `earth_<feature>_on` | `earth_forests_on` |
| Key (name switch or version selector; no prototype unless it feeds a hook) | `earth_<key>` | `earth_canals`, `earth_coast` |
| Released body | `earth_<thing>[_<map>][_s<k>]_v<n>` | `earth_geo_europe_v1`, `earth_ww_europe_s6_v1`, `earth_land_coarse_europe_v1` |
| Region layer | the interface names under "Region layer", each body with its `_v<n>` | `earth_destroyed_depth_v1`, `earth_tree_mult_v1` |
| Neutral bodies | `earth_zero`, `earth_one`, `earth_none` (+inf, neutral for `min`) | |

Every body is `_v1` until the first release.

## Expression graph

### Programs and the firewall

- Three programs compile per surface: Tile, Entity and Cliff (vanilla complexity 10,068, 8,549 and
  287; S1-fit, R6).
- A named expression read by several consumers in one program compiles once; the same body under
  another name compiles again: 8 consumers of one name cost Tile +14, 8 identical copies +4,522
  (S10).
- A per-tile reader of the coast in a second program compiles it again: AB plus a 16,253-point
  cloud measured Entity 186,342 against AB's 24,377 and a 3.14 times forced-generation increment
  (TQ1b).
- Under a plain `elevation` redirect, Entity complexity already grows with the tent count: 8,593,
  8,717 and 9,545 at 1,024, 4,096 and 32,768 terms (S1-fit); 8,717 and 9,129 at 4,096 and 16,384
  (TQ1b). The reader is vanilla starting ore: `starting_resources_lake_mask` is
  `clamp((elevation - 1) / 10, 0, 1)` and sits in the favorability of every starting-ore spot noise,
  evaluated per candidate (R6 Q3; vanilla `core/prototypes/noise-programs.lua:270-274`,
  `core/prototypes/noise-functions.lua:211-219`).

**Firewall rule (binding).** The fine field is `earth_elevation_v<n>` and every term only it reads:
the coast fit, the detail, the far-field box, the start land guarantee, the waterway sets, the
inland lakes and the offshore field stamps. Only the Tile program reads them, and only through the
`elevation` property; the analytic spawn lake is firewall-clean, because it reads only `x`, `y` and
`map_seed`. Every expression the Entity or Cliff program reaches (climate, `distance`, the region
layer, hotspot and enemy terms, ridges, the start mask, the sea mask, the palm switch, tree hooks)
reads only `x`, `y`, `map_seed` and the map-setting constants, per-save numbers and keys, the
coordinate chain, built-in noise, analytic terms built from tables, `earth_land_coarse`, and other
firewall-clean names.

**The coarse land field (decision 8, binding).** The Entity program knows land from one field,
`earth_land_coarse`: a preset key that each Earth preset maps to its map's
`earth_land_coarse_<map>_v<n>`, a tents-256 fit of the coast's own target (S9 used Europe's 256-term
checkpoint in the composite Phase 4 times), defined and budgeted in `europe-coast`. Every Entity-side
land reader uses it and nothing finer: the redirected `starting_resources_lake_mask` (vanilla starting
ore; S9: the coarse field plus the spawn lake), S6's land-aware hotspot and enemy terms through that
mask, the random offshore-oil sea mask, and any later reader. It is coarse: 94.5 percent offline on
S1-fit's curve, and the design review put its coast at p99 14.6 px on Europe, about 88 tiles at scale
6, so the start mask and the sea mask are approximate near coasts; T7 (b) and T8 measure the effect.
The known Entity readers of `elevation` in the maintainer's pack are both redirected on Earth presets: vanilla
starting ore through `starting_resources_lake_mask` (`europe-coast`) and AB's two palms (R3 4.1;
`climate-tiles`).

**Isolation check** (gate perf step, from `europe-coast` on M1 and from `climate-tiles` on M2;
decision 8, S9's method):

- (a) Entity and Cliff complexity, down to the expression, unique, operation and register counts, are
  identical between the real build and a twin whose fine coast is a constant. S9 made the coast field
  (tents, box and detail) the constant 8, and both programs stayed identical on M1 and M2. The twin's
  Tile row must differ in the same run, the positive control. This replaces the comparison of
  a 4,096-term and an 8,192-term build, which only sees a leak that grows with the tent count.
- (b) A static walk of the M1 and M2 dumps: no Entity or Cliff root (entity, decorative and cliff
  autoplace, and the preset keys that feed them) reaches a firewall name. It catches what (a) cannot:
  a waterway, lake or detail leak does not change when the coast does (PERF-12).

### Expression inventory

| Name | Module | Reads | Program | Milestone |
|---|---|---|---|---|
| `earth_map`, `earth_scale`, `earth_city`, `earth_geo` | presets | per-save numbers, no prototype | fold into every program | 1, 2 |
| `earth_on`, `earth_forests_on` | presets | hook gates, prototype "0", Earth presets set 1 (forests by toggle) | Tile, Entity | 6, 7 |
| `earth_cx`, `earth_cy`, `earth_city_index_v<n>` | spawn | city tables, `earth_city`, `earth_scale`, `map_seed` | all; control reads the index at (0, 0) | 2 |
| `earth_gx`, `earth_gy`, `earth_u`, `earth_v` | coast | `x`, `y`, offsets, map constants | all | 1 |
| `earth_geo_<map>_v<n>` | generated | `earth_u`, `earth_v` | Tile only | 1, 3 |
| `earth_land_coarse_<map>_v<n>`, through the key `earth_land_coarse` | generated | `earth_u`, `earth_v`; the 256-term checkpoint of the map's fit | Entity (the only land field outside Tile) | 1 (Europe), 3 |
| `earth_detail_v<n>` | coast | `earth_u`, `earth_v`, basis noise; 0 at pixel centres, amplitude set by the fit's gradient | Tile only | 1 |
| `earth_far_v<n>` | coast | `earth_u`, `earth_v`, the map's extent | Tile only | 1 |
| `earth_ww_*`, `earth_canals_*`, `earth_dams_*` (per map, scale, version) | generated | `earth_gx`, `earth_gy` | Tile only | 4 |
| `earth_spawn_lake_v<n>` | spawn | `x`, `y`, `map_seed`: analytic lake about 72 tiles out at a seed-folded angle (S7: nearest water 42.6 tiles) | Tile; Entity only inside the start mask | 2 |
| `earth_inland_lakes_v<n>` | spawn | `earth_gx`, `earth_gy`, `map_seed`; fixed density, kept out of the start radius | Tile only | 2 |
| `earth_fields_<map>_v<n>` | resources | field table, jitter constants | Tile only | 9 |
| `earth_elevation_v<n>` | coast | the composition below | Tile only | 1 |
| `earth_start_mask_v<n>` | spawn | `earth_land_coarse`, the spawn lake, `distance`: `clamp((e - 1) / 10, 0, 1)` with `e = min(earth_scale * earth_land_coarse, earth_spawn_lake)`, S9's form without its far-field box (every tent is 0 outside the raster, S1-fit); no firewall name | Entity | 1, refined 2 |
| `earth_sea_v<n>` | resources | `earth_land_coarse` below the configured offshore threshold, so rivers, canals, D15 lakes and marshes, which the coarse field reads as land, fall outside it (FEAS-07). Large drawn lakes the coarse field reads as water (Ladoga, the Great Lakes) are not excluded by the threshold; `resources-enemies` excludes them through table rows or records the exception, with the threshold | Entity | 9 |
| `earth_distance_v<n>` | spawn | `sqrt(x * x + y * y)` | Entity, Cliff | 2 |
| `earth_temperature_*`, `earth_moisture_*`, `earth_aux_*` (AB and fallback variants) | climate | latitude from `earth_v`, noise, slider controls (`control:hot` and `control:cold` only when AB is loaded, R3 6), region aggregates, `earth_destroyed` | Tile, Entity | 6, 10 |
| `earth_temperature_vanilla_v<n>` | climate | 0.45 times Earth temperature (S3) | Entity | 7 |
| region layer: the interface under "Region layer" (`earth_sd_<id>`, `earth_w_<id>`, `earth_depth_<id>`, `earth_destroyed_*`, `earth_forest_w`, `earth_forest_sum`, `earth_tree_mult`, `earth_marsh_w`, `earth_hotspot_w`, `earth_enemy_mult`) | regions | `earth_u`, `earth_v`, `map_seed`, the shared warp, table shapes, folded hotspot jitter | whichever program reads them: Tile for the zone and marsh lifts, Entity for forests, hotspots and the enemy layer | 5 |
| `earth_vtile_<tile>_v<n>`, `earth_marsh_<tile>_v<n>` | tiles | climate, region aggregates, `elevation` | Tile | 6 |
| `earth_vtree_<tree>_p_v<n>`, `_r_v<n>`, `earth_tree_mult_v<n>`, `earth_palm_const_v<n>` | trees | vanilla-scale temperature, moisture, `distance`, forest aggregates | Entity | 6, 7 |
| `earth_ore_<ore>_p_v<n>`, `_r_v<n>`, `earth_offshore_p_v<n>`, `_r_v<n>` | resources | live autoplace text, hotspot terms on the hotspot rows' membership, ramp on `distance`, start mask, sea mask | Entity | 9 |
| `earth_enemy_v<n>` | enemies | live `enemy_base_probability`, `earth_enemy_mult` | Entity | 9 |
| `earth_cliff_elevation_v<n>`, `earth_cliffiness_v<n>` | ridges | crest polylines in geo tiles, `earth_ridges`, `distance` | Cliff | 8 |

### Preset redirects

Each Earth preset sets these `property_expression_names` keys:

| Key | Value | Program | Milestone | Why |
|---|---|---|---|---|
| `elevation` | `earth_elevation_v<n>` | Tile | 1 | coast, waterways, lakes |
| `starting_resources_lake_mask` | `earth_start_mask_v<n>` | Entity | 1 | the vanilla mask reads `elevation` in every starting-ore spot noise (R6 Q3); without the redirect the fine field enters the Entity program. The Earth mask reads `earth_land_coarse` |
| `earth_land_coarse` | `earth_land_coarse_<map>_v<n>` | Entity | 1 | the one land field outside Tile |
| `distance` | `earth_distance_v<n>` | Entity, Cliff | 2 | start features at the spawn whatever `starting_points` holds; D31 can extend it (S7) |
| `temperature`, `moisture`, `aux` | the AB or fallback variant, chosen at data stage from `mods` | Tile, Entity | 6 | S3 |
| `earth_palm_elevation` (AB loaded) | `earth_palm_const_v<n>` | Entity | 6 | AB palms read `elevation` (R3 4.1); REVIEW |
| `cliff_elevation`, `cliffiness` | `earth_cliff_elevation_v<n>`, `earth_cliffiness_v<n>` | Cliff | 8 | S5 |
| `entity:<ore>:probability`, `entity:<ore>:richness` for iron, copper, coal, stone, uranium, crude oil | `earth_ore_*` | Entity | 9 | S6 (the preset route renders byte-identical to an in-place edit) |
| `enemy_base_probability` | `earth_enemy_v<n>` | Entity | 9 | S6 |
| `entity:offshore-oil:probability`, `:richness` (Oil Rig loaded) | `earth_offshore_*` | Entity | 9 | R4 4.7 |
| `earth_map`, `earth_scale`, `earth_city`, `earth_geo` | numbers | fold | 1, 2 | S2 |
| `earth_on`, `earth_forests_on` | 1 (forests: 1 or 0 by toggle) | hooks | 6, 7 | S3, S10 |
| `earth_coast` | `earth_geo_<map>_v<n>` | Tile | 1 | version selector |
| `earth_waterways`, `earth_canals` | the map's set for the save's scale; canals set or dams set | Tile | 4 | per-scale polylines picked by name (REVIEW) |
| `earth_ridges`, `earth_hotspots`, `earth_destroyed` | the live body or a neutral body | Cliff, Entity, Tile | 8, 9, 10 | name switches (S2) |
| hook keys (`earth_vtile_<tile>`, `earth_marsh_<tile>`, `earth_vtree_<tree>_p`, `_r`, `earth_tree_mult`) | versioned bodies | Tile, Entity | 6, 7 | stable hooks |
| `earth_bandfix` | 1 in the presets of each map whose default is on, absent in the others (absent means off): one per-save key per map | control only | 11 | decision 9 |

Beside the keys, each preset sets `basic_settings.autoplace_controls` frequency 0.75 for the six base
resources and leaves the planet entries neutral (D20; planet values multiply preset values, noise
known gotcha). Every redirect value must name a defined noise expression or be a number: anything
else is ignored with only a log line (noise rule 3). No redirect target reads the property it
replaces (`Parameter 'arg_register' expects Number, None given.`).

### Stable hooks on shared prototypes

A shared prototype (a vanilla or AB tile, tree, rock or decorative) compiles on every world that lists
it, so its autoplace text cannot be versioned per save. Every Earth edit to one is a stable hook:

```
if(<gate> > 0.5, <on branch>, <off value>)
```

The gate has a prototype default of "0" and Earth presets set it to 1. The on branch is a key, or a
fixed formula around one (the forest boost multiplies the original probability by its key, S10). The
key has a neutral prototype default (the off value, or 1 for a multiplier), and Earth presets map it
to a versioned body. The hook text never changes after release; the logic lives in the versioned
body. The outermost `if()` folds away on non-Earth worlds at identical complexity (S3, S10); a gate
placed inside the score instead cost default worlds Tile +7,489 and Entity +62 (S3). The palm hook
needs no gate: its key's default is AB's own `elevation`.

| Hook | Gate | Key | Off value | Milestone |
|---|---|---|---|---|
| 19 vanilla land tiles re-listed on Nauvis beside AB | `earth_on` | `earth_vtile_<tile>` | `-inf` | 6 |
| `water-mud`, `water-shallow` registered on Nauvis without AB (marshes) | `earth_on` | `earth_marsh_<tile>` | `-inf` | 6 |
| AB palms: `elevation` replaced by the key | none | `earth_palm_elevation` | `elevation` | 6 |
| 15 restored vanilla living trees beside AB (probability, richness) | `earth_on` | `earth_vtree_<tree>_p`, `_r` | `0` | 7 |
| Forest boost on every living tree (15 vanilla, 67 AB) | `earth_forests_on` | `earth_tree_mult` inside `min(1, (orig) * earth_tree_mult)` | `orig` | 7 |
| Vanilla rocks, decals and decoratives beside AB (R3 3.4 items 4 to 6) | `earth_on` | per name | `-inf` or `0` | 7 (design note 10) |

Tile scores that must lose return `-inf`, never a small or negative number (noise rule 4).

### Region layer (S10 design (d))

Every per-region quantity comes from one layer in `regions.lua`, built from the approval tables
(`regions`, `forests`, `marshes`, `destroyed`, `hotspots`). Design (d) won S10: exact discs, polygons
and buffered paths on one shared domain warp. For 20 Europe regions read in full it cost Tile 13,372
and Entity 11,840 (vanilla 10,068 and 8,549) and drew the approved polygons with IoU 1.0. The
runner-up, (b) a Voronoi of region centres (Tile 11,200, Entity 9,668), turns polygons into discs
(shape match 0.20 to 0.41); it is the fallback for forests if timing shows the Entity program cannot
afford their outlines (S10 1.7).

- **Rows.** Each row has an id, a layer (destroyed, forest, marsh, hotspot), a shape (a disc with
  lat, lon and radius in km, or a polygon or buffered path with lat and lon vertices), a warp share,
  and a boost (forests) or multiplier (hotspots). Exclusion rows (`mode = "exclude"`, warp 0) keep
  protected features out of a zone. An approval edit is a row edit: S10's Spessart row added a forest
  for Entity +30 with no code file changed.
- **Query point.** Rows are evaluated in reference pixels at `earth_u`, `earth_v`, the coordinate
  chain, so the build keeps one frame (S10 itself used pixel-edge coordinates).
- **Shared warp.** Two 3-octave `multioctave_noise`, `seed1` 7801 and 7802, wavelength 96 px,
  amplitude 12 px, clamped to 24 px; each row follows its share of it. Edge roughness: 2 octaves at
  6 px, `seed1` 7803, amplitude 1.5 px, clamped to 3 px, added to every signed distance. Noise calls
  keep `x = x, y = y` (A-12). Warp, roughness and ramp are in reference pixels, so regions keep their
  look at every scale (only scale 6 was run, S10 open question 3).
- **Warp shares.** The destroyed polygon 1; forest discs 0.25; the Carpathian and Dinaric outlines
  0.4; exclusion rows 0. Six exclusion rows cut the destroyed zone: the Kiel Canal as a 25 km buffered
  path, and Semmering, Dukla, Gotthard, Brenner and South Foreland as 20 km discs. They kept all 100
  protected points outside at every seed for Tile +377 (S10 section 3).
- **Hotspot rows.** Each adopted hotspot is a disc row of radius r at its adopted centre (APPROVALS
  2, which moves one inland under decision 16) plus S6's jitter of up to j = r/2, a linear fold of
  `map_seed` that folds to constants (S10, "Skipped"). Warp 0, so the disc keeps the geometry that
  APPROVALS 12's city removal assumes: roughness (3 px) and the outer half of the ramp (3 px) reach
  at most about 15 km past r, inside that table's 50 km margin (derived). Ore and the enemy layer read
  this one disc.

Interface. Consumers read these names and nothing else; each body carries its `_v<n>`:

| Name | Meaning | Read by |
|---|---|---|
| `earth_sd_<id>` | signed distance to row `<id>` in reference pixels, positive inside, at the warped point plus roughness | the aggregates |
| `earth_w_<id>` | membership weight `clamp(0.5 + sd / 6, 0, 1)`: a 6 px ramp, 36 tiles at scale 6 | the aggregates; per-region consumers, such as each hotspot's ore terms |
| `earth_depth_<id>` | the same signed distance in tiles | consumers that grade by depth |
| `earth_destroyed_sd`, `earth_destroyed_w`, `earth_destroyed_depth` | the zone after its rows: `min(include sd, -exclude sd ...)` | the climate lift (temperature above 100), zeroed inside the start radius; the random-pool switch (`destroyed-europe`) |
| `earth_forest_w` | the largest forest weight | forest tiles and decoratives; T10 |
| `earth_forest_sum` | the sum of row boost times weight (row boost 1 by default) | `earth_tree_mult` |
| `earth_tree_mult` | `1 + forest_boost * earth_forest_sum`, forest boost 2 from config | the forest-boost hook on every living tree (S10: probability times 1 + 2 w) |
| `earth_marsh_w` | the largest marsh weight; the same pattern, not measured by S10 | the marsh moisture lift and the marsh tiles (`climate-tiles`) |
| `earth_hotspot_w` | the largest weight over the hotspot rows | the enemy multiplier's footprint; T9 |
| `earth_enemy_mult` | `1 + sum((mult - 1) * w)` over the hotspot rows, mult 4 (APPROVALS 1b) | `earth_enemy_v<n>` |

- **One name per quantity (A-7).** A copy of the layer under another name costs about +646
  complexity, while eight consumers of one name cost +14 together (S10). T16 fails any region formula
  outside `regions.lua` and any re-emitted copy.
- **Cost and zero cost.** A program pays the shared warp (+518) once if it reads any region; a disc
  costs +29 and a polygon edge +51.8 (S10). Every consumer sits behind an outermost `if()` on its gate
  or behind a name switch, so with the toggles off the layer compiles to nothing: S10's switches-off
  worlds were byte-identical to vanilla and to AB alone at three seeds, with identical complexity.
  Europe's forests cost Entity +2,332 (+2,538 over AB); Atlantic's and Old World's about +5,600 and
  +5,000 (projected, S10).
- **Firewall-clean.** The layer reads only `x`, `y`, `map_seed`, per-save constants and the
  coordinate chain (S10 1.6), so the Entity program may read it.
- **Per seed.** The destroyed zone's IoU between seeds is 0.903 to 0.925 and with the approved polygon
  0.935 to 0.938; cities within about 40 km of its edge may flip per seed (S10: 7 of 84 inside and 3
  of 41 outside), and a city that must stay on one side gets its own row.

### Elevation composition

Order is binding; constants live in config.lua.

1. `c = earth_coast + earth_detail_v<n>` in pixel units. The detail is 0 at pixel centres, so T1 sees
   the fit alone.
2. Transfer: `e = gain * c + if(c > 0, offset, -offset)`, a sign offset (`sign` does not exist in
   2.1.23, noise notes). The offset clears vanilla's land-win margin (land beat water down to about
   -0.027 in S1-fit and -0.0100 in S8), so the tile class equals the sign of `c`. The gain sets the
   shore band AB reads (its shore term reads elevation up to 5; REVIEW). This replaces S1-fit's
   untested 1000 times gain (design review note). Milestone 1 sets both for vanilla; milestone 6 recalibrates
   with AB under the elevation body's next `_v<n>`: beach band present, deepwater below
   -5.5 offshore (R3 3.1).
3. Far field: `min(e, earth_far_v<n>)`, deep water beyond the map's box out to at least 100,000 tiles
   (D15). Every tent is 0 outside the raster (S1-fit).
4. Start land guarantee (`spawn-cities`; design note 14): `max(e, g)`, with `g` positive
   within the guarantee radius of the spawn, so a city whose pixel is water (three on Atlantic, R1
   section 11) starts on land. It precedes dams and carves, so a named waterway still cuts through it:
   D16 wins over the guarantee.
5. Dams: `max(e, 4 * (hw_dam - d * s))` for the canals-off set (S4).
6. Carves: `min(e, max(-2.2 or -6, 4 * (d * s - hw)))` for rivers (-2.2: plain `water` in vanilla
   and AB) and straits (-6: deepwater in both), and for canals when on (S4). Dams come first so a dam
   never closes a named waterway.
7. Lakes: `min(e, earth_spawn_lake_v<n>, earth_inland_lakes_v<n>)`.
8. Offshore fields: `min(e, -6)` inside each jittered field disc where `e` is already below 0
   (APPROVALS 3).

No step reads `control:water:*` or `segmentation_multiplier`, so the water slider is inert (D15).

**No river cuts a start area (decision 18, binding).** The spawn, its start lake and its starting ore
sit on one walkable side of any waterway. The composition alone does not ensure it, because vanilla's
starting patches know nothing of rivers, and curated rivers cross the start discs of about ten Europe
cities at scale 6 (JI-08: London, Lisbon, Warsaw, Belgrade and others). `waterways` picks the
mechanism, for example a folded per-city nudge of the spawn to the nearest bank with 12 clear tiles
that keeps the lake and ore on that bank, records it in design notes, and T7 (d) checks every
city at scales 1 and 6. Any Entity-side term it adds is analytic from tables, never a waterway set
(firewall rule).

## Per-save parameters and versioning

### Parameter scheme

| Value | Mechanism | Measured basis |
|---|---|---|
| Map | the preset itself, plus the number `earth_map` for control code | S2: one elevation name per preset, no map selector |
| Scale, city, geography release | numbers `earth_scale`, `earth_city`, `earth_geo` | S2 Q4: numbers fill constant-only slots and compile like literals |
| Toggles reached through preset keys (canals, ridges, hotspots, destroyed) | name switch: key to the live body or a neutral body | S2: a switch set to off costs the same as no term (425 operations against 433 for a numeric 0) |
| Toggles acting through hooks (great forests) | numeric gate with a prototype "0", outermost `if()` | S3 gate rule; S10 zero-cost identity |
| Versions of a leaf (coast fit, waterway set) | key to the versioned name | S2 Q5 |
| Band fix | key `earth_bandfix`, set per map: each map's preset carries it only when that map's default is on, and absent means off; read by control only | decision 9 |

Rules:

- Never multiply by a toggle: a numeric toggle at 0 still compiles 8 of its term's 10 operations (S2;
  design notes 03:45).
- No prototype fallback for per-save numbers or name-switch keys: a world missing one fails at
  creation with `Unknown variable` (exit 1) instead of drifting (S2). Gates and hook keys are the only
  Earth names with prototype defaults, because non-Earth worlds compile the hooks, and their defaults
  are always the off branch.
- Values read back as strings; control code uses `tonumber` (S7).
- A body never reads a key that saves made before the body existed could lack: new keys are read
  only by new bodies or behind a hook default.
- Servers create worlds by one route only: `--preset` with the server's settings, or a full
  `--map-gen-settings` file; combining them reset `starting_area` (S2 Q2).
- A milestone that adds a per-save value extends the drift line and the key list in config, and adds its
  own T11 row that flips the value, A then B then load.

### Guards (`scripts/guards.lua`)

- **Missing-name guard** (`on_configuration_changed`, Earth worlds): every Earth key in the Nauvis
  surface's `property_expression_names` whose value is a name must exist in
  `prototypes.named_noise_expression` (present in the 2.1.23 runtime docs), and every hook key must
  be present. A miss prints a loud error (`log` and a red `game.print`) naming key and value, because
  a dropped name silently gives new chunks vanilla terrain (design review note).
- **Drift line** (`on_configuration_changed` with `mod_startup_settings_changed`, which arrives with
  empty `mod_changes`, mod-dev rule 7): one info line per stored scale, city or toggle that differs
  from the current startup setting, for example "this save keeps scale 3; the setting applies to new
  worlds only" (S2 Q3). It never changes the world. Whether `game.print` at load reaches a GUI player
  is UNVERIFIED (S2); the log line is certain.

### Release versioning policy

1. A body is registered when the milestone that adds it lands, from `europe-coast` on, and
   released when it ships in a release zip. From registration on its text is immutable:
   `tests/frozen.json` holds its sha256, and the gate fails on a missing or changed registered name.
2. Changes ship under new names (`_v<n+1>`), presets for new worlds point at them, and old names stay
   defined forever. An A save under changed code seamed 3 chunks out of the generated area; with the
   new body under a new name it differed in 0 of 41,984 tiles (S2 Q5).
3. The rule covers every named expression and noise function a released body reads, vanilla ones
   included: Earth copies them under Earth names (design review note; a game update to `elevation_nauvis`
   would otherwise seam old saves, S2). Exception: entity wrappers around the pack's live autoplace
   (ores, enemies, offshore oil) wrap it on purpose, so bobenemies' intensity cap and the Oil Rig's
   patch set keep acting (S6, R4, R5). There Earth freezes its own terms only, and old saves' ore and
   enemies follow game and pack updates as vanilla saves do.
4. `earth_geo` increments whenever a geography name a preset points at changes. Control code keys
   release-coupled data (city tables for the message and markers, band-fix data) by the save's
   `earth_geo`, never by "latest".
5. A released table version is never edited; an approval edit after release creates the next version
   (copy-on-write), and expressions built from it take the next suffix.
6. One generated file per released version; tools refuse to overwrite a released one.
7. Hook text on shared prototypes never changes after release.
8. Registration starts in `europe-coast`, so the first release never changes a registered body in place
   either: a later milestone that needs a different body (for example `climate-tiles` recalibrating the
   transfer with AB) ships it under the next `_v<n>` and points the presets at it (decision 21, TST-09).
   Saves made with the first release builds still carry no compatibility promise to players. T11's upgrade seam
   test runs from the second release on (test notes T11).
9. The expression prefix joins the released registry at the first release: D36's rename is a data
   edit only until then. Registered names before 0.1.0 change with the prefix in the rename dry run,
   which builds its own registry under the test ID.

## Control stage

### Events

| Event | Script | Work |
|---|---|---|
| `on_init` | start, guards, markers | Earth world means the Nauvis surface's `property_expression_names` holds `earth_geo`; never decided from `settings.startup` or a noise fallback. Non-Earth: run the D33 sweep and stop. Earth: fill `storage.earth` (schema, map, scale, city, geo, toggles) from those values with `tonumber`; read the resolved city index with `calculate_tile_properties` at (0, 0), because the random pick folds in float32 and Lua cannot recompute it (S7: seed 4294967295 gave city 8, the integer hash city 1); set the D29 intro through `remote.call("freeplay", "set_custom_intro_message", ...)` when that interface exists, plus a log line; cliff "none" reset (ridges on and `nauvis_cliff` size 0: write size 1 back with a whole-table assignment and log it; S5 restored 330 of 330 cliffs); D32 RSO warning when `script.active_mods["rso-mod"]` (log `RSO-WARNING` and a localised print, S11); D12 warning when Destroyed Europe was requested without AB (`on_init` runs under the creating settings); both recorded in `storage.earth.warnings` for the per-player path; D33 sweep; markers if their setting is on; band-fix flag from the save's own key (milestone 11) |
| `on_load` | control | re-register the band-fix handler when `storage.earth.bandfix`; never writes storage (mod-dev rule 9) |
| `on_configuration_changed` | guards | missing-name guard; drift line; D33 sweep; storage schema migration written to be harmless on storage that `on_init` built (mod-dev rule 6) |
| `on_surface_created` | guards | D33 guard on the new surface (it fires inside `LuaPlanet.create_surface`, S11) |
| `on_player_created` | guards | send each warning in `storage.earth.warnings`, RSO (D32) and Destroyed Europe without AB (D12), to the new player on an Earth world: S11 found that `game.print` in `on_init` reaches no player. Tested on a loopback server with a scripted player, a route still UNVERIFIED (Conflicts, item 15) |
| `on_runtime_mod_setting_changed` | markers | D28 markers on or off |
| `on_chunk_generated` | bandfix | registered only when `storage.earth.bandfix` (milestone 11) |
| `on_chunk_deleted`, `on_surface_cleared`, `on_surface_deleted` | bandfix | only if the band fix keeps per-chunk keys (worldgen-runtime rule 1) |

Never registered: `on_tick`, `on_nth_tick`, `on_chunk_charted`, or any other per-tick or per-chunk
event. T16 checks the registrations statically.

### Rules

- Control code reads save state only: the surface's `property_expression_names`, `storage`,
  `calculate_tile_properties`, `script.active_mods`. Per-user settings never steer game logic, and
  `math.random` is never called; any `LuaRandomGenerator` (band fix only) takes a hashed seed
  (worldgen-runtime rule 7).
- `calculate_tile_properties` runs only on Earth worlds, where every per-save name it needs exists.
- Messages go to `log` (the harness reads it) and to `game.print`; `print` reaches stdout only.
- Handlers are registered in both `on_init` and `on_load` from saved state (mod-dev gotcha:
  registrations are not saved).

### D33 surface guard

- Keys: config's list of every key any Earth preset sets.
- On every surface other than Nauvis, remove (write `""`) each listed key whose value equals the
  save's own value in `game.default_map_gen_settings.property_expression_names`, which is what a new
  surface inherits (S11), with a whole-table assignment. A planet that sets a key itself keeps it,
  because its value differs. A non-Earth save matches nothing.
- Runs in `on_surface_created` and as a sweep over `game.surfaces` in `on_init` and
  `on_configuration_changed`: surfaces created inside an `on_init` never raised the event (S11).
- Cost: nothing per chunk. It cannot fix such a planet's new-game preview (cosmetic, S11).
- S11's probe matched the `earth_` prefix and recommended comparing with `prototypes.map_gen_preset`.
  This design compares with the save's own values instead, so a startup-setting change since creation
  cannot hide a key, and number values are covered.

## Compatibility

### Dependencies and load order

- `info.json` declares `base >= 2.1.23`, `? alien-biomes`, `? cargo-ships-oil-rig`, `? rso-mod`. Any
  version bound on a `?` dependency stays at or below the installed version (AB 0.8.0, Oil Rig 2.1.2,
  RSO 7.1.4): an older installed target is fatal at startup (mod-management rule 6). No mod in the
  pack declares a dependency on Earth, so no cycle can form (mod-dev rule 5).
- Every Earth stage runs after AB, the Oil Rig, bobenemies and RSO in every live modset (S11: Earth at
  load positions 3, 7, 72, 76 and 71 in M2 to M6).
- Earth never redefines another mod's or vanilla's named expression; the later loader would win
  silently (known noise gotcha). It edits shared prototypes only through stable hooks; it makes no
  global `cliff_removal_probability` edit.

### Alien Biomes

- AB overwrites `temperature`, `moisture` and `aux` in place and never writes
  `property_expression_names` (R3). Earth presets redirect all three; on Earth worlds 99.99 to 100
  percent of sampled AB land sat inside its tile's temperature box, and default-preset worlds stayed
  hash-identical to AB alone (S3).
- AB nils vanilla trees, rocks and decals in its data stage, before a dependent mod can snapshot them:
  Earth copies them from vanilla source (R3 3.4). Restored trees, tiles, rocks and decoratives sit
  behind stable hooks (R3 3.4 item 8).
- Earth expressions that read `control:hot` or `control:cold` exist only when `mods["alien-biomes"]`
  is set (R3 6).
- AB places all water from `elevation`: water below 0, deepwater below about -5.5 (R3 3.1). Its
  coastal shallows also read `segmentation_multiplier` (the water slider's frequency, R3 3.1), so
  with AB the slider may still move the shallow fringe; T4 on M2 measures it (open).
- AB trees ignore the trees size slider except "none" (S3); the forest boost hooks AB's 67 living
  trees (S10).
- Without AB, Earth touches no vanilla tile or tree autoplace except the gated marsh-tile
  registration and the forest-boost hook; the fallback climate dries the north and keeps the desert
  on vanilla sand (S3 section 4). Destroyed Europe requested without AB leaves the world equal to
  "off" and warns at creation and to every created player.

### RSO (D32)

- Unsupported and warned. RSO zeroes every resource without a `tile_restriction` and places ore by
  script; previews then show 0 ore (mod-management rule 5; S11 M5: iron 0).
- Earth's wrappers are built after RSO's data-final-fixes, around RSO's zeroed expressions, so on an
  Earth world with RSO only Earth's own ore terms (hotspots, offshore fields) stay in noise and RSO
  scripts the rest (derived; milestone 9's T13 M5 row measures it).
- The warning fires on Earth worlds only: once at creation and once to every created player, from
  `on_player_created`. Creation continues (S11).
- RSO forces start-area generation in its own `on_init`; the band fix stays idempotent anyway
  (worldgen-runtime rule 1).

### Cargo Ships and the Oil Rig

- The Oil Rig's seventh regular patch set re-deals every vanilla ore patch (R4 4.3): iron 876 without
  it, 684 with it, at seed 1000 in S11's window. Ore baselines include it. Earth hotspots use their own
  patch set (`seed1` 7301) and do not move (S6).
- Wells take any water tile, and `no_shallow_oil` is forced off with AB (R4 4.2). With the Oil Rig
  loaded, Earth presets redirect `entity:offshore-oil:*` to the Oil Rig's live expression times the
  sea mask `earth_sea_v<n>`, which reads `earth_land_coarse`, plus the field terms
  (APPROVALS 3). The offshore threshold is set in `resources-enemies` with a design note (FEAS-07).
- The Oil Rig re-adds offshore oil in `on_init` and `on_configuration_changed`, calls
  `regenerate_entity`, and writes Nauvis map settings by read, modify and write, which keeps
  `property_expression_names` (S11, R4 4.6).
- Waterway widths follow R4's ship geometry: 7 tiles single track, 11 for two-way straits (S4).

### bobenemies and the rest of the pack

- bobenemies caps `enemy_base_intensity` at distance 1600 and swaps spawners 1:1 per chunk (R5, S6).
  Earth's enemy layer reads the live intensity through `enemy_base_radius` and
  `enemy_base_frequency`, so the cap applies; Earth never copies those bodies (versioning rule 3).
- minime's hidden surfaces are handled by the D33 guard (T14 runtime part). factorio-admin-command-
  center's dormant ore regeneration would re-place ore through Earth's redirects. mining-scars and
  nuclear-scorch rewrite tiles at play time only. mapshot is never used for posters (D30). Fill4Me's
  logged error is unrelated (S11).

### Space Age

Not installed. A preset key reaches every planet that does not set that key itself, and the D33 guard
removes it (S11). Gated hooks on vanilla tiles would hide them from any other planet that lists them
(AB's own comment says removing vanilla tile autoplace broke Space Age, R3 3.2). UNVERIFIED; smoke
step 8.

## Performance budgets

**Threshold table (decision 3, binding).** Every threshold the perf gate enforces (the Tile cap, each
milestone's allocations per program and map, the time allocations and the timed limits) lives in a table
in the design notes, which milestones cannot stage, and the gate parses that table. `tests/budgets.json`
holds measured values only: complexity rows, censuses, hashes and recorded ratios. Loosening a
threshold takes a the design notes entry and a plan revision between parts, never a change inside a
milestone. Deterministic measured values (complexity, operation counts, image hashes, entity counts) must
equal the gate's measurement; a timed ratio is compared with its threshold and a tolerance, never by
equality. The rows below explain the numbers; the plan's table is what the gate enforces.

| Budget | Value | Source | Enforced by |
|---|---|---|---|
| Forced generation, full program, Earth over vanilla, 8 LP (TQ1b block, affinity 0xFF), per map at scales 6 and 1 | at most 1.5x: the binding performance rule (the plan's P1). TQ2: S9's Europe composite 1.26x on TQ1b's block and 1.19x far, 1.00 to 1.03x at 24 LP | D7; TQ2 | the gate (Europe at scale 6, every milestone); the suite of every milestone that adds Tile or Entity work, per map; `ridges` completes and times every map's full program |
| Same, Earth plus AB over AB alone | at most 1.5x (the plan's P2). AB alone is 1.00 to 1.05x vanilla at 24 LP and 1.19 to 1.21x at 8 LP; TQ2 timed S9's composite at 1.59 to 1.66x AB alone at 8 LP, over the bar, so `climate-tiles` runs the flip rule for Alien Biomes worlds (cut order below) | decision 5; REVIEW, TQ1b, TQ2 | the same, from `climate-tiles` |
| Relative limit per milestone | the formula and the per-milestone time allocations in the plan's table (section 6.3), read against TQ2's whole composite (1.26x vanilla and 1.66x AB alone on TQ1b's block at 8 LP) | decisions 3 and 5; TQ2 | gate perf step |
| Same, 24 LP | at most 1.5x | D7 | release suite |
| Exploring, the in-play lag (asynchronous generation, R8 2.8) | gated in real time at 60 UPS on a loopback server, TQ2's frontier at 24 LP: ticks over 20 ms, the p99 interval and the longest interval (the plan's P4 to P6), against vanilla (AB: AB alone); benchmark mode recorded per milestone, its `scriptUpdate` gated (P7). TQ2: 2 late ticks of 2,160 (EarthMaps 108, Factorio World 120), p99 17.6 against vanilla's 17.5 ms; benchmark mode 4.46x vanilla's mean, because a column's tile step (78 ms on S9's composite) lands inside a tick only when ticks run back to back | decision 7 as design notes 10:20 restates it; TQ2 | milestone suites from `europe-coast`, re-validated by the gate perf step |
| First column into empty land | a request into empty land builds a 7 x 17 chunk support neighbourhood, 7 columns of tile work at once; TQ2: 466 ms of main thread in benchmark mode, a 302 ms interval at 60 UPS (505 with AB), longer than either world mod's longest (41 and 86 ms); the plan's P6 limits it, and `europe-coast` traces and reduces it | TQ2 | milestone suites from `europe-coast` |
| Tile complexity per world | a diagnostic cap with per-feature allocations in the plan's table (P10, P11, section 6.3). the review's provisional 113,000 sat on the 8 LP chord between tents 4,096 (0.993x) and 16,384 (1.641x), which reaches 1.5x near 121,600; TQ2 timed S9's composite (Tile 112,387) at 1.26x, under the chord's 1.44 estimate, while with AB (173,325) it timed 1.66x AB alone, so on M2 the timed rule binds, not the cap | decisions 3 and 5; REVIEW, TQ1b, TQ2 | gate perf step (T15a) |
| Europe, measured | S9's composite at scale 6, toggles on: Tile 112,387, Entity 12,443, Cliff 124 (with AB 173,325, 25,259, 124), without inland lakes, marshes, turning basins or the land guarantee | S9; TQ2 (the same numbers) | timed by TQ2: 1.19 to 1.26x vanilla and 1.59 to 1.66x AB alone at 8 LP |
| Olde World, estimated | tents about 78,300 + waterways about 32,700 + about 2,000 | REVIEW | untimed (TQ2 timed Europe only); `olde-world-atlantic` times it |
| Atlantic | first fit 69,000 to 96,000 (6,800 to 10,400 terms, est.); its waterways get the cap minus the coast minus the headroom the plan reserves for later Tile work (lakes, basins, marshes, offshore stamps; FEAS-08) | REVIEW; FEAS-08 | `olde-world-atlantic` |
| Entity complexity | per-feature allocations in the plan's table (P12, P13, section 6.3); TQ2 measured Europe's composite unchanged (12,443; 25,259 with AB), and Atlantic's and Old World's ceilings stay provisional. Measured increments: hotspots with the enemy layer +1,491 (S6); Europe forests +2,332 (base) and +2,538 over AB (S10); destroyed zone +592 through climate (S3); Atlantic and Old World forests about +5,600 and +5,000 (projected, S10); `earth_land_coarse` inside S9's 12,443, not isolated | S3, S6, S9, S10, TQ2 | gate perf step (T15a) |
| Entity with AB | Earth plus AB 22,507 against AB alone 24,377 with S3's analytic climate; S9's composite 25,259 | S3, S9 | M2 rows |
| Cliff complexity | vanilla 287; ridges about 4.4 per range segment; S9's whole Cliff program 124 for three Europe ranges | S5, S9 | T15a |
| Isolation | Entity and Cliff identical between the real build and the constant-coast twin, with and without AB, while the twin's Tile differs; no Entity or Cliff root reaches a firewall name | decision 8; S9 | gate perf step |
| Earth Lua per chunk | 0 without the band fix; `scriptUpdate` within 0.01 ms per tick of vanilla | brief section 5, test notes 5.5 | T16 static allowlist; gate perf step |
| Band fix, when on | per map: average at most 0.24 ms per generated chunk and no handler tick above 2 ms, measured on Europe at scale 1 and on Olde World at scale 6, both at 8 LP | design notes 07:05 | `coast-band-fix` |
| Preview time | reported, not gated: TQ2 measured S9's composite at 5.09x vanilla at 1024 px (6.27x at 256 px), against the 5.4 to 6.5x estimate (REVIEW); tents 4,096 2.94x, AB alone 4.05x (TQ1b) | design notes 07:05 and 10:20 (D8 reading); TQ2 | release suite |
| Trees and saves | great forests 2.0x the trees of the same chunks without the boost (accept 1.6 to 2.5); at most 0.1 percent of trees moved outside; trees per generated block at most +27 percent on Europe (+17 Atlantic, +19 Old World); the T10 block's save at most +3 percent; against the same pack without Earth, reported only | decision 15; S10 4.4 | `trees-forests` (T10) |
| Save size | the forced block's increment between two server saves, gated by the plan's P19 against vanilla (AB: AB alone); the whole save reported. TQ2: increment 1.07x vanilla (0.72x AB alone with AB); whole save 1.50x, because the composite stores its start area about 280 KB larger than vanilla's, twice (`level-init.dat` and `level.dat`), cause untraced; `europe-coast` traces and reduces it | design notes 10:20; TQ2 | milestone suites from `europe-coast` |
| Startup time, memory, data size | reported. TQ2 reference: data stage 0.530 s against vanilla's 0.368, a new map's first 120 ticks 13.5 ms against 13.2 (EarthMaps 7,035, Factorio World 1,690), peak working set while exploring 221 MB against 205; TQ2's prototype held Europe only, so the shipped mod's startup and memory run somewhat higher (TQ2 caveat) | design section 6; TQ2 | release suite |

Measurement rules: complexity ranks variants of one program and is not time (noise rule 8);
summed complexity predicted preview time within about 20 percent but not forced generation (TQ1b);
every timed number follows the quiet-window protocol (one game process, CPU under 25 percent before
each repetition, block census checked, ratios formed within one group; TQ1b). The gate needs the
machine to itself: with the maintainer playing, the timed step fails closed.

Cut order when a map exceeds its budget (design review note): waterway segments first (tolerance up, then
rivers out from the bottom of APPROVALS 7's list, each through a design note, Europe's 22 rivers
as a floor; JI-03), tent terms second, never below 99 percent preview-mode T1. A later milestone that
exceeds its reserve may trigger the waterway cut order through a design note and a
`data-src/waterways` edit (FEAS-08). If a map still cannot fit, it takes the runner-up: tents 4,096
plus the band fix, with its preview shortfall stated. If that map then ships below
0.990, its T1 row carries the recorded number and the shortfall is listed for the maintainer; the build does not
loop on it. For Alien Biomes worlds the same order runs in `climate-tiles` against
M2t/BABt: waterways cut to a 1 px tolerance first, then a cheaper geography chosen
at the data stage only when `alien-biomes` is loaded, baked per save as `earth_geo` and registered
as the next geography version, while base worlds keep their fit and both geographies stay defined
in every install.

## Invariants

Design constraints (each enforced by the gate):

| # | Invariant | Enforced by |
|---|---|---|
| S-1 | Every game run goes through `%FACTORIO_WS%\tools\fh.py` with its own instance and modset, and every run that writes data has a RESULT line reading `isolated=yes`; nothing launches the game against, or writes to, `%APPDATA%\Factorio` | `earth_test.py` refuses any other RESULT on a run that writes data (`--version` and `--help` runs are exempt and say so; a loopback server passes with `exit=timeout`, TST-11); a live-profile guard snapshot and check around every command that launches the game, gate, suites, install-check and perf (G9) |
| S-2 | Registered expression bodies are byte-frozen (`tests/frozen.json`, from `europe-coast` on); names are append-only | gate freeze check on the M1 and M2 dumps; `build_zip.py --release` refuses unregistered bodies |
| S-3 | The Entity and Cliff programs never read the fine coast field; their one land field is `earth_land_coarse` | isolation check (a) against the constant-coast twin and (b) the static walk |
| S-4 | No per-tick handler, and no per-chunk handler except the band fix, which is registered only on saves whose map's preset carried the band-fix key | T16 static registration allowlist; `scriptUpdate` in T15c and T15d |
| S-5 | All names (mod ID, settings, expressions, presets, locale keys) come from `prototypes/config.lua` | T16: no literal names or coordinates outside config and tables; D36 rename dry run |

Design invariants (binding, from the reports):

| # | Invariant | Source |
|---|---|---|
| A-1 | Default-preset worlds stay byte-identical and complexity-identical to the same modset without Earth (T13 zero-cost rows); Earth makes no global `cliff_removal_probability` edit | S3, S10 |
| A-2 | Every Earth edit to a shared prototype's autoplace is a stable hook, and a gated hook's outermost node is the gate `if()` | S3 |
| A-3 | No redirect target reads the property it replaces | noise notes |
| A-4 | Map-shaping values are baked into the preset; no expression reads a startup setting at generation time; control code reads map, scale and flags from the save | S2 Q1, design review note |
| A-5 | Toggles never multiply; selection is a name switch or an `if()` on a folded parameter | S2, design notes 03:45 |
| A-6 | No prototype fallback for per-save numbers or name-switch keys; gates and hook keys are the only Earth names with defaults, and those defaults are neutral (gates default to off) | S2 |
| A-7 | One named expression per shared quantity; no formula re-emitted under a second name | S10 |
| A-8 | Water and cliffs sliders are inert under Earth presets: elevation reads no water control; cliff expressions use contour units and never read `cliff_richness`; "none" is reset once in `on_init` | S5, D15, D19 |
| A-9 | Tile scores that must lose return `-inf` | noise rule 4 |
| A-10 | No constant that folds to NaN (`0 / 0`, `sqrt(-1)`, `log2(-1)`) | noise rule 5 |
| A-11 | Noise layers separate by `seed1`, never `seed0`: hotspots 7301, enemy layer 7123, region warp 7801 and 7802, region edge roughness 7803; new layers record new values in config | noise rule 6, S6, S10 |
| A-12 | Noise calls take `x = x, y = y` with scale and shift in `input_scale`, `offset_x`, `offset_y` | noise rule 8 |
| A-13 | Nauvis only: the D33 guard removes Earth keys from every other surface | S11 |
| A-14 | Generated files are rebuilt by their tool in the same commit, never hand-edited, and reproducible from committed inputs | design notes DoD |
| A-15 | Shipped text holds no em or en dash; every dropdown value has a locale key; no locale line lacks `=` | design notes, S11 |
| A-16 | Control code is deterministic: save state only, no `math.random`, hashed seeds | worldgen-runtime rule 7 |
| A-17 | The gate never writes tracked files; it reads main's committed measured values, takes every perf threshold from the plan's threshold table, and trusts no verdict file | decisions 1 and 3; test notes 5.3 |
| A-18 | D25 wins inside the start area: no ridge cliff within the start radius, and the range resumes outside it; a known local exception listed for the maintainer | decision 12; APPROVALS 5 and 11 |
| A-19 | No river cuts a start area: the spawn, its start lake and its starting ore sit on one walkable side of any waterway | decision 18; T7 (d) |

## Milestone contracts

Each milestone's binding additions. Checks are test notes ids; the plan's acceptance criteria are
authoritative for thresholds, and the perf gate reads them from the plan's threshold table (decision
3). Headings give this file's build-order number and the plan's part and order; builders find their
milestone under "### Milestone <order>: <id>" in the design notes.

Every milestone: its gate stays under 10 minutes; a milestone that adds a per-save value adds
its T11 row; from `europe-coast` on, a milestone registers each versioned body it adds in
`tests/frozen.json`; a milestone that adds Tile or Entity work times each shipped map's
program at 8 LP at scales 6 and 1 in its suite.

### 0. `toolchain` (part 1, order 0)

- **Introduces.** The mod skeleton (info.json, settings.lua with the scale setting, locale, LICENSE,
  changelog.txt, control.lua registering nothing yet), config.lua, a placeholder Earth: Europe preset
  with a coarse land shape so installCheck has an Earth preview, `tools/earth_test.py` (`gate`,
  `suite`, `install-check`, `baseline`, `freeze`; the content-hash cache; the guard around every
  command; the threshold-table parser), `build_zip.py`, `perf.py`, the lint setup, S8's tools and
  `earthgeo.py` with their self-tests, `data-src/earthmaps/` with provenance, ported copies of the S8
  reference JSONs and `approvals-data.json` with their sha256, `tests/budgets.json` for
  measured values, an empty `tests/frozen.json` with its checker, `tests/baselines/` for build
  87750, and the T3 oracle's brief-sourced climate rows.
- **Contract.** The runner refuses to run without `FACTORIO_WS` and fh.py; every game run is isolated
  (S-1); the build is pinned to 2.1.23 build 87750 (G8); zips are byte-reproducible; the placeholder
  preset's names are never released, and `europe-coast` retires the preset with every registration it
  made. The gate's wall time is measured here, and a deliberately heavy probe shows which
  `mapGenerator*` column moves (PERF-15).
- **Gate.** T16, T13 load on M1, tool self-tests (S8: 62, 760, 10, 4 and 10 offline checks and the
  31-check game suite).

### 1. `europe-coast` (part 2, order 0)

- **Introduces.** `build_geo.py` and `geo_europe_v1` from the existing 8,192-term checkpoint;
  `earth_land_coarse_europe_v1` from its 256-term checkpoint, defined and budgeted here;
  the coordinate chain with the `floor(s / 2)` constant (`earth_cx`, `earth_cy` are 0 until
  `spawn-cities`); the transfer, detail and far-field box; `earth_elevation_v1`; the real Earth: Europe
  preset; scale 1 to 6 with world-size labels (APPROVALS 1c); `earth_map`, `earth_scale`, `earth_geo`;
  the `starting_resources_lake_mask` redirect to `earth_start_mask_v1`, which reads the coarse field;
  `scripts/guards.lua` with the missing-name guard and the drift line; the first `tests/frozen.json`
  entries.
- **Contract.** The firewall and the isolation check, (a) against the constant-coast twin on M1 and
  (b) the static walk, start here. The lake-mask redirect belongs here, not in
  `spawn-cities`, because vanilla starting ore would otherwise carry the fit into the Entity program
  and fail (a). The preset's geography names and `earth_geo` are chosen in one place at the data
  stage, so `climate-tiles` can give Alien Biomes worlds a cheaper geography without touching base
  worlds.
- **Gate.** T1 for Europe at scales 1, 3 and 6 from preview mode or dumped tiles, thin water and
  corridors masked, at least 99.1 percent; T2; T11 (map, scale, geography id); T15: the gate's timed
  row at 8 LP and the exploring rows start here, in real time and in benchmark mode (decision 7 as
  design notes 10:20 restates it), with the save increment, the first measured values recorded; the
  first-column hitch and the start-area save excess traced and a reduction of each tried (design notes
  10:20); V1 contact sheets; the drift line. REVIEW's deciding experiment: time tents
  8,192 alone and the Europe program at 24 and 8 LP, and record the chord's error.

### 2. `spawn-cities` (part 2, order 1)

- **Introduces.** City tables and per-map city settings with random, minus the cities APPROVALS 12
  removes; `earth_city`, `earth_cx`, `earth_cy`, `earth_city_index_v1` (random is the folded hash of
  `map_seed`, S7); the analytic spawn lake; the start land guarantee (composition step 4); sparse
  inland lakes at a fixed density; the `distance` redirect; a refined start mask for coastal and
  low-lying cities (vanilla's mask starves starting ore below elevation 11, S7); `scripts/start.lua`
  (world detection, storage, D29 message); the D32 warning at creation and to every created player
; the D33 guard.
- **Contract.** Starting ore and the enemy-free start come from vanilla's own terms through
  `distance` at the origin, the lake from the analytic spawn lake (S7: one patch per ore, 0 enemies
  within 150 tiles, nearest water 42.6 tiles). Under the shift every world coordinate converts as
  `world = geo - (earth_cx, earth_cy)`.
- **Gate.** T7 first on a coastal and low-lying sample (London, Lisbon, Oslo, Amsterdam and Helsinki
  at scale 1; FEAS-06), then every Europe city at scales 1, 3 and 6 (fast subset in the gate); T4
  starting-area row; T11 city flip; T13 M5 warning line and its player path
; T14 synthetic planet; T18 (a) and (c); V2 city crops.

### 3. `olde-world-atlantic` (part 3, order 0)

- **Introduces.** `geo_olde_world_v1` (smallest checkpoint at or above 99.1 percent from a refit at
  growth 1.25) and `geo_atlantic_v1` (first full or 2x fit, memory-bounded, same rule), each with its
  coarse land field; their presets, city lists and budget rows.
- **Contract.** Atlantic's waterways get the cap minus its coast minus the headroom the plan reserves
  for later Tile work (FEAS-08). Each 1,000 tent terms saved frees about 8,200 Tile complexity, about
  240 waterway segments (est., REVIEW).
- **Gate.** T1 and T15 per map (each map's block at scales 6 and 1); T7 for their cities; V1 contact
  sheets.

### 4. `waterways` (part 4, order 0)

- **Introduces.** `build_waterways.py`; the generated sets for scales 1 to 6 per map; curated rivers
  in APPROVALS 7's priority order inside the cap, written to `data-src/waterways/<map>.json` and bound
  to that list by T16 (rows leave only from the bottom, each through a design note, with Europe's
  22 as a floor; JI-03); straits open, with Gibraltar, Dover and the Great Belt in the two-way class;
  isthmuses closed; the canals key with dams (Kiel and Corinth on every map, Suez on Olde World and
  Atlantic, Panama on Atlantic; APPROVALS 6); turning basins; T1 corridor masks; the mechanism that
  keeps spawn, lake and starting ore on one bank where a river crosses a start area.
- **Contract.** Composition steps 5 and 6. Only the selected scale's set and the selected canal branch
  compile (S4: Tile 19,620 off and 20,161 on at scale 1).
- **Gate.** T5 per feature per scale 1 to 6, canals on and off, plus the no-dam control and the M3
  Cargo Ships placement probe; T3 strait and canal rows go live; T7 re-run for
  every city of every map, (d) included; T11 canals flip; T1 masks and the thin-water
  report; T15 per map; T15e river and canal-island paths (PERF-09); V2 straits and river mouths.

### 5. `region-layer` (part 4, order 1)

- **Introduces.** The layer described under "Region layer": rows from the tables, the shared warp and
  roughness, per-row warp shares, the six exclusion rows, hotspot rows at their adopted centres, the
  per-region outputs and the aggregates.
- **Contract.** Consumers read the interface names only; a static check fails any region formula
  outside `regions.lua` (S10). An approval edit is a table row with no code change (S10: the Spessart
  row added a forest for Entity +30). The layer is firewall-clean (S10 1.6). Runner-up (b), a Voronoi
  of centres, if timing shows the Entity program cannot afford forest outlines (S10 1.7). Its
  allocation is a row of the plan's threshold table (section 6.3: 0 everywhere, since nothing reads
  the layer yet).
- **Gate.** T3 membership (protected features outside at every seed) and locality on sampled
  membership (FEAS-19); T2 per-seed edges (destroyed zone IoU 0.5 to 0.95 between seeds, S10
  measured 0.90 to 0.93; other rows by edge displacement, FEAS-20); T13 switches-off identity; T15.

### 6. `climate-tiles` (part 5, order 0)

- **Introduces.** Earth temperature, moisture and aux after EarthMaps' class layout (D9), in an AB
  variant and a fallback (S3 section 4), with S3's slider hooks (hot and cold shift 125/6 per unit;
  moisture and aux bias 2.2 times the bias; frequencies through `input_scale`); `earth_on` and the
  tile hooks: the 19 vanilla tiles beside AB with S3's bonus rule, marsh tiles (`water-mud`,
  `water-shallow` registered on Nauvis without AB; the marsh region lifts moisture into the wet band
  through `earth_marsh_w` and lets `water-mud` win, APPROVALS 8), the adopted AB temperate tiles
  (APPROVALS 9); the AB palm switch; the transfer recalibrated with AB, under the elevation body's next
  `_v<n>`.
- **Contract.** Climate is firewall-clean (AB trees read it in the Entity program); a climate fit, if
  used, is its own coarse field, never the coast fit. M2 joins the gate here: its load, its zero-cost
  row (M2 default against BAB), the isolation check with AB and the M2t/BABt timing. TQ2 timed S9's
  composite at 1.59 to 1.66x AB alone at 8 LP, so this milestone runs the flip rule for Alien Biomes
  worlds until every map's M2t/BABt meets
  the plan's P2. The palm switch
  lands here because AB palms read `elevation` (R3 4.1) and (a) runs with AB from this milestone on. Palm
  mechanism: the hook in the hooks table; if the M2 zero-cost row shows any change, fall back to
  preset keys `entity:<palm>:probability` holding an Earth copy that reads the switch. D11's limit to
  the adopted AB tiles comes from climate shaping or preset tile keys, never from a redirect that
  reads its own property.
- **Gate.** T3 climate and tile family, with the brief-sourced named places and the D11 numeric row
, and locality at preview level (FEAS-19); T4 climate slider rows, moisture and aux
  frequency included; T5 re-run, since the transfer changed; T10 climate bands;
  T13 M2 and M6; T15 per map with M2/BAB; V3.

### 7. `trees-forests` (part 5, order 1)

- **Introduces.** The 15 restored vanilla living trees beside AB (copied from vanilla source,
  temperature on the vanilla scale, restricted to vanilla tiles; S3); vanilla rocks, decals and
  decoratives beside AB behind hooks (design note 10); AB trees by climate through the
  redirect, no edit; the forest-boost hook on every living tree, boost 2 by default as a per-family
  data value (S10: 1.68 to 1.79 times inside with vanilla trees, 2.11 to 2.43 with AB); the D27
  absorption table (a report; no absorption edits).
- **Gate.** T10 with decision 15's budget; T4 trees rows; T11 forests flip; T17; the D27 table and
  T15e driver 3 (JI-18); T15 per map including Entity isolation; V4 at a great forest.

### 8. `ridges` (part 6, order 0)

- **Introduces.** Crest polylines from the ranges table; `cliff_elevation = cliff_elevation_0 +
  cliff_elevation_interval * f` with the only contour at f = 1 and each flank 16.37 tiles out (off the
  4-tile lattice: exact lattice hits delete cliffs); `cliffiness = 10 * (1 - pass mask)`, 0 inside the
  start radius through `distance` (D25 wins there); passes at least a 12-tile cliffiness
  gap (8 tiles clear; S5 recommends 16 to 20 as the default); the 400 km unnamed-gap rule (design notes
  05:55, 06:45; APPROVALS 5); the ridges key (off: a constant crest distance); the cliff "none" reset
  in `start.lua`; on Earth worlds, an Earth-gated ridge exclusion that multiplies ore probability so
  ore never lands on a ridge cell, through the preset's ore keys until `resources-enemies` folds it
  into its wrappers.
- **Contract.** A start area on a crest is a designed opening: no ridge cell inside it, the range
  resuming outside, a known exception listed for the maintainer together with the cliffs-slider
  "none" preview and the 196 starting chunks (JI-17). This milestone completes every map's full program,
  so its suite times each map at scales 6 and 1.
- **Gate.** T6 (facing at least 0.9; both-flank coverage at least 0.85 over the crest minus its
  openings at scales 3 to 6, reported at 1 and 2; flood fill through the openings, each at
  least 8 tiles clear; spawns at Bern and at Andorra la Vella for decision 12); T4 identity rows go
  live: the water slider and the cliff rows; T7 (a) re-run; T11 ridges flip; T15 per map
  with the Cliff allocation; V2 passes.

### 9. `resources-enemies` (part 6, order 1)

- **Introduces.** Ore frequency 0.75 in the presets; the richness ramp `1 + 0.5 * clamp((distance -
  450) / 3550, 0, 1)` on the four solid ores (S6 Q5: 1.01, 1.09, 1.23 and 1.50 at 512, 1024, 2048 and
  4096 tiles); hotspots per S6 A5 on the region layer's hotspot rows at their adopted centres
  (APPROVALS 2: decision 16 moved Baku inland and listed Portland and Marmara Island for the maintainer), with a
  shared blob (one `spot_noise` per resource in its own patch set, `seed1` 7301; jitter from the
  linear fold of `map_seed`; combined as `max(live, (size > 0) * clamp(v, 0, 1))`); the enemy layer
  per S6 A6E (`seed1` 7123; live probability times `earth_enemy_mult`, multiplier 4 inside each
  jittered disc, design note 6; active only beyond twice `starting_area_radius`), joined as
  `max(live, layer)`; offshore fields as a deep-water stamp in the composition (Tile) plus an Oil Rig
  wrapper term (Entity); random offshore oil masked by `earth_sea_v<n>`, whose offshore threshold on
  `earth_land_coarse` this milestone sets with a design note (FEAS-07).
- **Contract.** Wrappers are built in data-final-fixes around the live expressions. Every land reader
  here uses `earth_land_coarse`, never a waterway set or the fine coast. Hotspot amounts
  are judged on each disc's land part.
- **Gate.** T8, T9, T4 ore, enemy and offshore-oil rows (M3), T5 re-run (offshore stamps),
  T7 (a) re-run, T11 hotspots flip, T15 per map; T13 M3 and M5 rows; V4 at a hotspot; V2 offshore
  fields.

### 10. `destroyed-europe` (part 7, order 0)

- **Introduces.** The zone from the region layer's `earth_destroyed_depth` (S10), routed through
  climate: temperature above 100 inside, so AB's volcanic tiles and its volcanic tree follow (S3);
  zero inside the start radius; while on, random never picks a city inside the zone (folded pool
  switch; 8 of 41 Europe cities lie inside, APPROVALS 10); without AB the world equals "off", and the
  warning goes to the log at creation and to every created player.
- **Gate.** V3 at three seeds; T2; T3 membership; T11 zone flip; T13 the warning's player
  path; T15 with the zone on, on M2 (PERF-05).

### 11. `coast-band-fix` (part 7, order 1)

- **Introduces.** `scripts/bandfix.lua` and `bandfix_<map>_v<n>.lua`: one reference raster per map,
  which serves every scale and noise release, plus a dirty-chunk list per scale that is coupled to
  the geography release and keyed by `earth_geo` (S12: Europe 97.6 KB of raster and 1.1 to 11.0 KB
  of lists at scales 1 to 6; Olde World 526.7 KB and 6.2 to 48.8 KB). The handler also skips the
  waterway, lake and dam masks, which are coupled to the waterway release.
- **Contract.** `on_chunk_generated` is registered only when the save's band-fix key is 1. The key
  is per map: each map's preset carries it only when that map's default is on, and absent
  means off, so adding the milestone never touches old saves. The handler acts on Nauvis only and is a
  pure function of chunk position, the chunk's generated tiles and the shipped data. It rewrites only
  tiles whose reference pixel lies at least half a pixel from the reference coast where the noise is
  wrong, in one `set_tiles` call per chunk, never outside the chunk (worldgen-runtime rule 8), and
  idempotently: S1-hybrid's whole-pixel ancestor was exact on 29,241 of 29,241 tiles, a second pass
  wrote 0 tiles, and generation order did not matter. The band rule reads "at least half a pixel":
  the strict "more than" leaves 82 percent of Europe's wrong pixel centres and fails check (c) (S12).
  Known costs: the preview shows only the noise; 42 to 50 percent of written tiles turn water into
  land, which stays bare (S12); `set_tiles` destroys colliding entities placed by earlier handlers
  (worldgen-runtime). Estimated average 0.104 ms per generated chunk on Europe at scale 1 (S12); the
  open risk is (a)'s 2 ms tick limit, since an Olde World chunk at scale 6 writes 203 tiles on average
  and up to a whole chunk (S12, UNVERIFIED in game).
- **Acceptance**. Checks (a) to (d) run on
  Europe at scale 1 and on Olde World at scale 6, both at 8 LP, and on M2 for a map whose Alien
  Biomes geography `climate-tiles` moved to tents 4,096: (a) handler average at
  most 0.24 ms per generated chunk and no handler tick above 2 ms; (b) a clean loopback desync run,
  host at 24 LP and client at 8 LP, with the `storage` diff; (c) dumped-tile T1 of 100 percent at
  scored pixel centres with max deviation at most 0.5 px; (d) the base's float32 replication
  predicts the game outside the band. They are measurement rows: the milestone passes when every check
  is measured and recorded and each map's default equals the rule, on only if all four pass for
  that map. A failing
  measurement sets that map's default off and is not a halt. Atlantic, never priced (S12),
  ships off. The design notes report the outcome per map. A map whose fix ends off and whose agreement
  stays under 0.990 falls under decision 10.
- **Gate.** The four checks; T11 key flip; T5 re-run; T12 (b).

### 12. `compat-completeness` (part 8, order 0)

- **Introduces.** T12 (same seed twice; loopback desync with host at 24 LP and client at 8 LP while
  exploring); T13 M0 to M6 with BAB and BL; T14; T17, which needs every vanilla autoplaced name on M2
  (restored in `trees-forests`); the D34 load test of the rest of the pack; M4t/BLt forced
  generation gated at 1.5 at 8 LP, exploring in real time against BL by the plan's P4 to P6, and a
  `scriptUpdate` bound against BL (the plan's P15; PERF-08).

### 13. `extras` (part 9, order 0)

- **Introduces.** `scripts/markers.lua` (D28: rendering objects in chart mode or one-shot chart tags,
  placed at `world = geo - (earth_cx, earth_cy)` from the save's table version; no per-chunk event;
  the rendering-object route is tested headless whenever chart tags cannot be, TST-29); posters from
  dumped tiles or stitched previews, never a mapshot render (D30); size context in labels and preset
  descriptions (D3), with the footprint figures labelled as reported community examples (JI-12); the
  hand-out script and text in `tools/handout/` (D6: zip, sha256, PowerShell installer, tested only
  against a scratch mods directory and a `file://` base, TST-02). README.md is the release handoff's
  (design note 8).

### 14. `release` (part 10, order 0)

- **Introduces.** Version 0.1.0; `tests/frozen.json`, kept complete since `europe-coast`,
  gets the release's last entries from `earth_test.py freeze`; packaging with `build_zip.py
  --release`; TESTING.md from the milestones' smoke sections; the release suite (`earth_test.py suite
  release`) with V1 to V5; the security review runs first. From this release on the
  versioning policy applies to released bodies in full. Kickoff needs the recorded human smoke pass on
  the parent issue and every other sub-issue closed.

## Conflicts and open items

Items 1 to 9 are settled; each keeps its record. Items 10 to 17 are open.

1. **`cliff_removal_probability = 0` against default-world identity.** design notes's ridges milestone set
   it on resources, a global prototype number that no gate can scope: default-preset worlds would
   keep vanilla cliffs that ore used to remove (S5: 88 ore tiles under cliffs on the test ridge),
   breaking A-1 and T13's zero-cost rows. Settled by design notes 08:00: no global edit; on Earth worlds
   an Earth-gated ridge exclusion multiplies ore probability (milestone 8). The pre-revision plan's
   `ridges` text still names the global edit; its revision carries design notes 08:00.
2. **Lake-mask redirect timing.** Settled: `europe-coast` redirects
   `starting_resources_lake_mask`, or its isolation check fails (S1-fit, TQ1b, R6).
3. **Palm switch timing.** Settled: the AB palm switch ships
   in `climate-tiles`, where M2 joins the gate.
4. **Coordinate convention.** Settled: S1-fit's emitter (EarthMaps' placement) and
   T1's floor convention (S8) differ by `floor(s / 2) / s` px, 0.5 px at scale 6; the build bakes one
   recorded offset constant, and `europe-coast`'s T1 at scales 3 and 6 is the proof.
5. **Entity budget.** REVIEW's "Entity about 10,200" predates S10, whose forests alone add +2,332 on
   Europe and a projected +5,000 to +5,600 on the larger maps; S9's Europe composite measured 12,443.
   The per-feature allocations live in the plan's threshold table (P12, P13, section 6.3; decisions 3
   and 5); TQ2 measured the composite's Entity unchanged (12,443; 25,259 with AB), so Europe's
   ceilings stand, Atlantic's and Old World's stay provisional, and S10's runner-up (b) is the
   fallback.
6. **Land awareness in the Entity program.** Settled by decision 8: one coarse field,
   `earth_land_coarse`, serves the start mask, the land-aware hotspot and enemy terms and the sea mask.
7. **Owner for rocks, decals and decoratives beside AB.** Settled: `trees-forests` restores them (plan
   reconciliation 10); T17 needs them on M2.
8. **test notes names.** Settled: test notes now uses the plan's paths (`tools/earth_test.py`,
   `tests/budgets.json` for measured values, `tests/frozen.json`, `tests/baselines/`) and scales 1 to
   6, and takes thresholds from the plan's table.
9. **Freeze point.** Settled by decision 21: bodies are registered in `tests/frozen.json` from
   `europe-coast` on, so `build_zip.py --release` works at any point. Consequence for the
   plan: a registered body never changes in place, even in the first release, so a later change such as
   `climate-tiles`' transfer recalibration ships under the next `_v<n>`; the D36 rename dry run builds
   its own registry under the test ID.
10. **Space Age.** Gated vanilla-tile hooks could hide those tiles on Space Age planets; UNVERIFIED.
11. **Water slider with AB.** AB's coastal shallows read `segmentation_multiplier`; T4's water row on
    M2 against BAB, live from `ridges`, shows whether the slider is still visible there.
12. **Composite timing.** TQ2 timed S9's composite: on base it meets the timed
    rule (1.19 to 1.26x vanilla at 8 LP) and beats both world mods on generation, on real-time late
    ticks and p99 and on startup, while its first-column hitch is longer than either mod's longest
    interval; with AB it takes 1.59 to 1.66x AB alone at 8 LP, over the rule. The
    starting values are in the plan's section 6. Open until the build measures them: whether
    `climate-tiles` brings M2 under the rule by waterway simplification or needs the Alien Biomes
    geography, and what `europe-coast`'s traces of the first-column hitch and the start-area save
    excess find.
13. **Hotspots at sea.** Computed from the reference land mask in APPROVALS 2: three
    adopted onshore hotspots had discs more than half water. `oil-baku-absheron` moves its centre
    19.9 km west, within its jitter radius, which takes its disc from 61 to 47 percent water;
    `stone-portland` (90 percent water, 65 at best within j) and `stone-marmara-island` (90, 85 at
    best) stay at their cited sites, listed for the maintainer. No city removal changed.
14. **D25 against D19 inside start areas.** At scale 6, 8 of Europe's 40 cities lie within
    150 tiles of a crest (23 at scale 1), Aktobe on Atlantic, and Aktobe and Delhi on Old World
    (APPROVALS 5); each such start opens a gap in its range. Listed for the maintainer with the cliffs-slider
    "none" preview and the 196 starting chunks (JI-17).
15. **Scripted player headless.** No headless way to create a player is known: the local
    runtime API offers `LuaSimulation.create_test_player` only inside simulations, and fh.py refuses the
    graphical `--mp-connect`. `spawn-cities` proves a route on a loopback server or records in
    design notes why none exists, and smoke step 4 then carries the per-player warnings. UNVERIFIED.
16. **Rivers through start areas.** `waterways` chooses how spawn, lake and starting ore
    stay on one bank (composition, "No river cuts a start area") and records it in design notes.
17. **Band fix on Atlantic.** The flip checks run on Europe at scale 1 and on Olde World at
    scale 6; Atlantic has no priced fit (S12) and no measurement, so its default ships off.

## Sources

Paths are relative to the repo root unless they start with `%FACTORIO_GAME%`.

| Tag | Path |
|---|---|
| design notes | the design notes |
| design notes | the design notes (sections cited by time) |
| REVIEW | the design notes |
| S1-fit | the design notes; code `spikes/S1-fit/` (`common.py`, `emit.py`) |
| S1-hybrid | the design notes |
| S2 | the design notes |
| S3 | the design notes |
| S4 | the design notes |
| S5 | the design notes |
| S6 | the design notes |
| S7 | the design notes |
| S8 | the design notes; `spikes/S8-tooling/README.md`; `spikes/S8-tooling/reference/<map>.json` |
| S9 | the design notes; code `spikes/S9-composite/` (the coarse field and the constant-coast twin) |
| S10 | the design notes |
| S11 | the design notes |
| S12 | the design notes (used for `coast-band-fix`) |
| Decisions, finding ids | the design notes (findings such as TST-08) |
| TQ1b | the design notes |
| TQ2 | the design notes (Phase 4, group `b20261027-0821`); its consequences in the design notes 10:20 |
| R3, R4, R5, R6, R8 | the design notes, `R4-cargo-ships.md`, `R5-mod-sweep.md`, `R6-noise-capabilities.md`, `R8-perf-footprint.md` |
| test notes, APPROVALS | the design notes |
| Vanilla | `%FACTORIO_GAME%\data\core\prototypes\noise-programs.lua:270-274`, `noise-functions.lua:211-219` |
