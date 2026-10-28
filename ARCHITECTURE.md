# Architecture

Binding design for Terra Nauvis (mod ID `terra-nauvis`) in the first release: Factorio 2.1.23 (build 87750),
base game, Alien Biomes 0.8.0 optional. The disagreements with the earlier design notes found while writing this file are listed in "Conflicts and open items". This file is
living: during a build it changes only through fit-review patches folded in at a milestone commit, and
whenever a milestone changes a binding contract (Universal Definition of Done).

Conventions. Every measured fact carries a source tag that the Sources table at the end resolves to
a path. "est." marks an estimate, "derived" marks arithmetic on cited numbers, and UNVERIFIED marks
a claim no run settled. TQ2 tags the Phase 4 quiet-window benchmark, whose numbers filled every
starting value that waited for it; the values in force live in the plan's section 6.
Names use the prefixes the maintainer chose (D36, design notes 12:35): `terra-nauvis` for the mod, settings and
presets, `tn_` for noise names; reports, spikes and design notes entries before 12:35 say `earth-atlas`
and `earth_`, and a cited name maps by prefix. `prototypes/config.lua` owns the real strings. LP
means logical processors. Milestone numbers
here run 0 to 14 in build order; the plan numbers milestones per part, so a milestone id (`waterways`) is the
stable reference. Revised after the design review: "decision n" cites the binding decisions in
the design notes.
Revised again for later decisions: the Map type entries, the Exact
coastlines setting, the 16 LP proxy, fords, river widths by class and GitHub releases.

## Overview

```
BUILD TIME (tools/)             DATA STAGE (every peer)           GENERATION (every peer, engine)
data-src/earthmaps rasters      settings.lua                      Tile program
  build_geo.py --------+        data.lua: Earth named               elevation: coast fit, waterways,
curated waterway lists |          expressions, three presets,       lakes, far field (Tile only)
  build_waterways.py --+-->       three Map type entries,           climate, tile scores, fords
prototypes/generated/*.lua        per-save values baked, fallbacks
prototypes/tables/*.lua --->    data-final-fixes.lua: wrappers    Entity program
  (approval data)                 around live autoplace, gated      trees, ore, enemies, oil;
tests/frozen.json <-- freeze      hooks on shared prototypes        land from tn_land_coarse
.github/workflows: CI, release                                    Cliff program: ridges
                                CONTROL (every peer, main thread): one-time events; per-map band fix
```

- **Data stage.** Builds every Earth named noise expression and three map-gen presets (Terra
  Nauvis: Europe, Terra Nauvis: Atlantic, Terra Nauvis: Old World), listed right after Default. A
  preset bakes every map-shaping value (map, scale, city, geography release, toggles) into
  `basic_settings.property_expression_names`, so a save keeps its map for life whatever the startup
  settings say later (S2). Each map's elevation expression is also a Map type entry in the Terrain
  tab (D2 amended, design notes 12:35): picked alone it gives the map's shape through prototype-level
  fallbacks that hold the current startup values (section "Map type entries").
- **Generation.** The engine compiles what the chosen preset reaches into its Tile, Entity and
  Cliff programs and runs them on worker threads; every peer generates every chunk itself, and the
  results are applied inside the game update (R8). A default-preset world compiles none of it (S3,
  S10).
- **Where the cost sits.** The coast fit is the one expensive term (Europe at 8,192 terms: Tile
  complexity 82,139 est. against vanilla's 10,068; S1-fit; 73,296 over a constant-coast twin, S9). It
  lives only in the Tile program. Entity and Cliff read cheap shared fields, because any per-tile
  reader there compiles the fit a second time (TQ1b); their one land field is `tn_land_coarse`, a
  separate 256-term fit.
- **Control stage.** One-time work only: world detection, the start message, warnings at creation
  and to each created player, guards, the cliff "none" reset, and map markers when their setting
  changes. No `on_tick`, no `on_nth_tick`; `on_chunk_generated` exists only in the band fix, and only
  on saves whose map's preset carried the band-fix key.
- **Tooling.** `tools/earth_test.py` is the gate: one command under 10 minutes per milestone,
  thresholds parsed from the plan's threshold table, a live-profile guard around every
  command that launches the game. It runs the game only through the workspace's `fh.py`,
  isolated from `%APPDATA%\Factorio`. GitHub Actions never runs the game: `ci.yml` runs the static
  checks and builds the zip on every push and pull request, and `release.yml` publishes the GitHub
  release when a `v*` tag is pushed.

## Module map

Repo paths are relative to the repo root; every mod file lives under `terra-nauvis/`, the zip's root folder,
so the `prototypes/` and `scripts/` rows below are `terra-nauvis/prototypes/...` and `terra-nauvis/scripts/...`
(folded in by `toolchain` from its fit review).

| Path | Responsibility | Contract it exposes | First milestone |
|---|---|---|---|
| `terra-nauvis/info.json` | Identity and dependencies: `base >= 2.1.23`, `? alien-biomes`, `? cargo-ships-oil-rig`, `? rso-mod`; `factorio_version` "2.1" | name equals the config ID; title at most 100 characters; no Space Age feature flag (mod-dev rule 4) | 0 |
| `terra-nauvis/settings.lua` | Startup: scale (string values "1" to "6", default "6"), spawn city per map ("random" plus city keys), toggles hotspots, great-forests, ridges, canals, destroyed-europe, exact-coast (Exact coastlines, design notes 12:35). Runtime-global: city-markers | values are short ASCII tokens, so labels can change without invalidating stored values (S11); names and defaults from config | 0; cities 2; each toggle with its milestone; exact-coast 11 |
| `terra-nauvis/data.lua` | Requires config, tables, every released generated file and the expression modules; defines the Earth named expressions; builds the presets | `data:extend` only on Earth names, never on another mod's or vanilla's names | 0 |
| `terra-nauvis/data-updates.lua` | Empty in the first release; reserved for edits that must follow every mod's data.lua and precede every data-final-fixes | none | 0 |
| `terra-nauvis/data-final-fixes.lua` | Everything that reads other mods' final state: entity wrappers (ores, enemies, offshore oil), gated hooks on shared prototypes (the `water-shallow` hook for fords and marshes; vanilla tiles, trees, rocks and decoratives beside AB; marsh tiles without AB; forest boost; AB palm switch; the Earth-gated ridge exclusion on ore probability) | hooks follow the stable-hook rule (Expression graph) | 4 (fords), 6 |
| `terra-nauvis/control.lua` | Event wiring only | registers exactly the events in "Control stage" | 0 |
| `terra-nauvis/locale/en/terra-nauvis.cfg` | Setting names and descriptions; `[string-mod-setting] <setting>-<value>=<label>` for every dropdown value, with world size; preset names and descriptions; the `[noise-expression]` Map type names "Terra Nauvis: <map>"; messages, the Map type notice among them | every used key exists; no line without `=` (a missing `=` fails the load, S11) | 0; Map type names 1 and 3 |
| `terra-nauvis/changelog.txt`, `LICENSE`, `SOURCE-OFFER.txt`, `thumbnail.png` | Factorio changelog, GPLv3 (EarthMaps data reuse), the written source offer (GPLv3 section 6: the zip tells a recipient how to get the mod, `tools/` and `data-src/` from the author), thumbnail (later) | `tools/build_zip.py` ships every file of the folder and refuses anything but Lua, JSON, cfg, txt, png, md and LICENSE | 0, 13 |
| `terra-nauvis/prototypes/config.lua` | The single source of names and constants (table below) | pure data: reads no `data`, `settings`, `game` or `script` and calls no function, so the settings, data and control stages and the Python tools (through `tools/tnconfig.py`, a luaparser loader of that subset) read one file; it marks the placeholder preset's names, which are never registered or released | 0 |
| `terra-nauvis/prototypes/presets.lua` | The three presets from config, `settings.startup` and `mods`, ordered right after Default; the prototype-level fallbacks the Map type entries read, built from the same table | the redirect table under "Expression graph"; AB keys only with AB loaded, Oil Rig keys only with the Oil Rig; each fallback equals what its preset bakes (section "Map type entries"); in `toolchain` the placeholder preset redirects `elevation` and `starting_resources_lake_mask` (to the placeholder's copy of vanilla's start mask on `elevation_nauvis`), so design constraint 3 holds on it; with a mod of `placeholder.withheld_with` loaded (Alien Biomes, whose two palms read `elevation` in the Entity program) the placeholder preset is not defined at all, since only `climate-tiles`' palm switch makes an Earth preset safe beside them (reconciliation 9) | 0 (placeholder), 1 |
| `terra-nauvis/prototypes/expressions/coast.lua` | Coordinate chain, coast transfer, lattice detail, far-field box, elevation composition, emitted once per map as that map's elevation entry; the coarse land key `tn_land_coarse`. In `toolchain` only the placeholder shape and its start mask | the firewall names: Tile only; `tn_land_coarse` is the one land field outside Tile; the newest entry of each map carries the Map type fields | 0 (placeholder), 1 |
| `terra-nauvis/prototypes/expressions/spawn.lua` | City fold, random pick, spawn offsets, spawn lake, inland lakes, `distance`, start mask | `tn_cx`, `tn_cy` and the city index readable at (0, 0) | 1, 2 |
| `terra-nauvis/prototypes/expressions/climate.lua` | Temperature, moisture and aux (AB and fallback variants), vanilla-scale temperature, slider hooks, marsh and destroyed-zone lifts | firewall-clean: Entity reads it through AB trees | 6 |
| `terra-nauvis/prototypes/expressions/regions.lua` | Region layer, S10 design (d): table rows, the shared warp, per-region outputs and layer aggregates (section "Region layer") | consumers read only the interface names; no region formula anywhere else (S10) | 5 |
| `terra-nauvis/prototypes/expressions/tiles.lua` | Bodies behind the tile hooks: vanilla tiles beside AB, marsh tiles | | 6 |
| `terra-nauvis/prototypes/expressions/trees.lua` | Restored vanilla tree bodies, forest-boost multiplier, AB palm switch | | 6, 7 |
| `terra-nauvis/prototypes/expressions/resources.lua` | Ore wrappers (richness ramp, hotspots), offshore-oil wrapper, offshore field stamps | | 9 |
| `terra-nauvis/prototypes/expressions/enemies.lua` | Enemy-layer wrapper | | 9 |
| `terra-nauvis/prototypes/expressions/ridges.lua` | `cliff_elevation` and `cliffiness` from the ranges table | slider-proof, contour units (S5) | 8 |
| `terra-nauvis/prototypes/expressions/destroyed.lua` | Destroyed-zone consumers: temperature lift, start mask, random-pool switch | | 10 |
| `terra-nauvis/prototypes/expressions/waterways.lua` | Loads the generated waterway sets; canals and dams switch; the ford key's bodies | | 4 |
| `terra-nauvis/prototypes/generated/` | `geo_<map>_v<n>.lua`, `coarse_<map>_v<n>.lua`, `waterways_<map>_s<k>_v<n>.lua` (with the ford sets), `bandfix_<map>_v<n>.lua` | machine-written; the header records tool version and input sha256; never hand-edited; one file per released version | 1, 3, 4, 11 |
| `terra-nauvis/prototypes/tables/` | `cities`, `hotspots`, `forests`, `ranges`, `canals`, `marshes`, `regions`, `destroyed`: approval data in degrees, with sources; hotspot rows take the adopted centre (`lat`, `lon` in `approvals-data.json`), which decision 16 moved inland for one hotspot | versioned by release (copy-on-write after a release) | per milestone |
| `terra-nauvis/scripts/start.lua` | `on_init`: world detection, storage, D29 message, cliff "none" reset, D12 and D32 warnings logged and recorded in `storage` for the per-player path | | 2, 8 |
| `terra-nauvis/scripts/guards.lua` | Missing-name guard, drift line, the Map type notice, D33 surface guard, per-player notice, RSO and Destroyed Europe warnings (`on_player_created`) | | 1, 2 |
| `terra-nauvis/scripts/markers.lua` | D28 city markers | no per-chunk event | 13 |
| `terra-nauvis/scripts/bandfix.lua` | Tolerance-band coast fix | the only per-chunk handler | 11 |
| `tools/earth_test.py` | Runner: `gate --through <milestone-id>` (each milestone's testCommand, under 10 minutes; `--cold` ignores the FG cache to time the cold gate; the FG rows of every milestone up to `<milestone-id>` and only `<milestone-id>`'s suite evidence), `suite <milestone-id>` (full variants into the content-hash cache; `--only <check>`), `install-check`, `baseline`, `freeze`, `static` and `guard-rebaseline --reason <text>` (A manual re-baseline of the chained guard by hand: it refuses unless stdin and stdout are an interactive terminal and the operator types back every changed path `fh.py guard check` lists, and no halt message names it) commands; the milestone registry (FG rows, SS checks, live-sample pools, oracle properties and the dumps the frozen row reads, per milestone) | finds fh.py through `FACTORIO_WS` (default `%FACTORIO_WS%`) and refuses to run a game-launching command without it; `static` launches nothing and needs neither, so CI runs it; validates every milestone id (`SLICE_ID` and the registry) before it builds any path and keeps each output directory inside its output root, refused by `tnguard.py` like every tool's; never writes tracked files while gating, and writes state and tracked files atomically (temp file plus replace); trusts no verdict file, only cache entries whose key it recomputes, each key covering what its check measures (the M0 timing rows: vanilla program signatures, the driver mods, the timing machinery, fh.py, the build and the record format); re-derives suite evidence from raw outputs alone: each timed repetition's validity from its run directory, the affinity watcher's records and the persisted monitor reads (never the runner's `reps.jsonl` verdicts, only cross-checked), the walker's affinity the same way, the server saves' sizes from the files, and the game self-test by replaying a copy of its stored runs (`game_selftest.py --replay`, which launches nothing); parses every cell of the plan's section 6 (6.2 limits bound by program, modset and map; 6.3 allocations per modset and map, "every other milestone" included) and fails closed on one it cannot read; a 6.2 From cell naming no milestone (P3) is in force from the first milestone, and a row in force that no check of the runner consumes (`LIMIT_CONSUMERS`) fails the section6 row; rule 5's extra group of 7 reps per config for a timed ratio within 0.03 of a limit, decided pooled (in the gate only when it fits the budget, else it fails closed naming the ratio); a guard snapshot and check around every command that launches the game, chained on the chain's last entry, with an append-only journal; every start also fails when a build instance (`test-instance/instances/ea-*`) wrote a game log after the chain's last clean end, a game run outside every chained bracket (after an entry that never finished, only the instances its launch ledger names may have), and prints every manual re-baseline in the part, which the gate's verdict line counts; every game launch inside the bracket, whose token it hands its child tools (`tnguard.py`) | 0 |
| `tools/build_geo.py` | Tents fit and emitter | reproducible emission (Build-time data flow) | 1 |
| `tools/build_waterways.py` | Waterway vectorisation, per-scale smoothing and simplification | | 4 |
| `tools/build_zip.py` | Packaging; `--release`; `--check-tag <tag>` (release.yml's tag check); `--release --push-tag` (the release tag step) | byte-reproducible zip (stored entries, fixed timestamps and attributes, sorted), the same on this machine and on GitHub's `windows-latest` runner; `--release` refuses while config.lua marks a placeholder name, and refuses any unregistered Earth body: every noise name config.lua defines, released bodies and firewall bodies alike, missing from tests/frozen.json, the Map type fallbacks excepted (design constraint 2), which every milestone from `europe-coast` on keeps complete, so from then it works at any point of the release; the gate's frozen row checks the dumped bodies themselves; `--push-tag` pushes only the tag `v<version>` on `origin/main`'s head when it carries the release trailer | 0; tag step 14 |
| `.github/workflows/ci.yml` | On every push and pull request: `earth_test.py static` and `build_zip.py`, the zip uploaded as an artifact | no game, no fh.py, no `FACTORIO_WS`; `contents: read`; actions pinned to full commit SHAs | 0 |
| `.github/workflows/release.yml` | On a pushed tag `v*`: checks the tag against `info.json`, runs `build_zip.py --release`, publishes the GitHub release with the zip and its `.sha256` | the workflow's own `GITHUB_TOKEN` with `contents: write` and the preinstalled `gh`, no other secret; no game | 0 |
| `tools/t1_metrics.py`, `oracle.py`, `dump_render.py`, `contact_sheet.py`, `nav.py`, `earthgeo.py`, `earthmaps_decode.py`, `game_selftest.py` | S8's tools with their self-tests, ported from `spikes/S8-tooling` in an earlier prototype; `earthgeo.py` holds the pixel conventions and reads them from config.lua; `oracle.py extend` and `validate` build and check `tests/oracle/<map>.json`; the game self-test uses content-hashed `ea-s8-*` modsets, and `game_selftest.py --replay` re-derives its 31 verdicts from a finished run's stored outputs (every game command answered from its own `run.json`, nothing launched) | conventions equal config.lua's; rasters from `data-src/`, the oracle from `tests/oracle/`, the workspace from `FACTORIO_WS` | 0 |
| `tools/tnconfig.py` | The luaparser loader of config.lua (local assignments, table constructors, literals, `..` and arithmetic; anything else fails closed) and the schema accessors of its groups (`firewall_names`, `fallbacks`, `release_registry`, `toggles`, `placeholder_names`, `noise_names`, `unregistered_names`, `schema_problems`, `defined_names`) | the one way Python reads Earth names and constants; an accessor raises on a wrong shape and never reads one as empty; `schema_problems` also reconciles the stores of Earth body names: every firewall body but the placeholder's sits in a `release_registry` row, and every noise name carries the noise prefix | 0 |
| `tools/tnguard.py` | The safety rails design constraint 1 shares across tools: the live-profile and mods-folder output refusal every tool's output options pass through (plain drive-letter paths only: extended-length, device and UNC spellings, admin shares among them, are refused; the live profile, from `APPDATA`, the known roaming folder and the home default, is matched by resolved path and by file identity of the nearest existing ancestor; a `mods` segment is matched as Windows opens it); the declaration of every tool option as written (`OUTPUT_ARGS`), read (`READ_ARGS`) or a value (`VALUE_ARGS`); and the guard-bracket check (`TN_BRACKET`) that `game_selftest.py`, `dump_render.py run`, `oracle.py probe` and the gate's kill probe pass before fh.py launches the game | the one module that names the live profile, to refuse it (the launch scan allows it that alone); launches nothing | 0 |
| `tools/tn_static.py` | T16's static rows and their run-time fixture controls (lint, info.json, locale, dashes, registration, names, design rules, launch scan, output options, workflow scan, attribution scan, data-src hashes, frozen and budgets shape, zip) | no game, no fh.py, no FACTORIO_WS, no git refs; needs only luaparser and the linter; the mod scans read `build_zip.py`'s own file classification (shipped and refused files), so no file in the mod folder escapes them; the registration scan is an allowlist over every use of `script`, `defines.events`, `require` and indirect global access; the name scan reads string literals and identifiers (dot-index fields, table-constructor keys, method names) of every mod Lua file and of `tools/mods/` (its Lua and `info.json` files too); the output-options row requires every argparse dest under `tools/` to be declared in `tnguard.py` and every tool with a written one to call its refusal; the frozen row requires every noise name config.lua defines, but the placeholder's and the fallbacks, to be registered; the launch and attribution scans read every file of their trees (dot and build folders included) and the launch scan the repo's root scripts too | 0 |
| `tools/mods/` | Test-only mods, never shipped: S8's `ep-s8-dump`, `ep-s8-probe`, `ep-s8-disc-world`; TQ1's timer `tq1-gen` (block from a runtime-global setting); TQ2's driver `tq2-driver` (forced, explore, walk, rtexplore and save jobs); `ea-coast-twin` (isolation (a)'s constant-coast twin, named at run time by the runner), `ea-leak-fixture` (the isolation checks' positive controls: a test-only preset carrying the first Earth preset's keys without the start mask, and one carrying all of them plus an entity and a decorative autoplace key redirected to fixture bodies that read the fine field; values that are numbers stay numbers) and `ea-heavy-probe` (PERF-15) | they get any Earth name from the runner at run time, so a rename stays a config edit (the T16 name scan reads them) | 0 |
| `tools/affinity_watch.ps1` | TQ1b's affinity watcher, `-Mask` 0xFFFF (the 16 LP proxy, its default) or 0xFF (the 8 LP diagnostic) | with `tools/perf.py`, the only script that names the game's process image, and it never launches one | 0 |
| `tools/perf.py` | T15 timing: TQ1b block, 16 LP affinity (0xFFFF, the weaker-machine proxy) with 8 LP (0xFF) recorded as a diagnostic, quiet-window protocol, census check; the kill-on-close job object every fh.py launch runs in; the parsers (force time, `--verbose` complexity, `--benchmark-verbose all`, real-time intervals) | the one process-inspection module: it lists, watches and pins game processes fh.py started, and never launches one | 0 |
| `tools/lint/` | luacheck 1.2.0 installed per user under `%FACTORIO_WS%\downloads\luacheck-1.2.0\` (`manifest.json` records version, source and sha256; `luacheckrc.lua` declares each stage's globals; `fetch_linter.py` installs it in CI), luaparser 4.2.0 as the syntax floor (`requirements.txt`), the vendored fh.py flag sets (`fh-flags.json`) the launch scan reads, and the warnings allow-list | the linter's checked-file count equals the zip's Lua file count | 0 |
| `data-src/earthmaps/` | Decoded rasters, reference JSON (byte copies of S8's), provenance, GPLv3 notice | read-only tool input; the gate regenerates the rasters with the decoder and compares them byte for byte | 0 |
| `data-src/approvals/` | `approvals-data.json`, a byte copy of `spikes/approvals/out/approvals-data.json`, with its provenance | read-only; the milestones load its rows into `terra-nauvis/prototypes/tables/` | 0 |
| `tests/` | `oracle/<map>.json` (with S8's place set as the fixture `oracle/s8/`), `budgets.json` (measured values only, never thresholds), `frozen.json`, `design-rules.json` (the APPROVALS 1a row of every existing setting), `baselines/` (`build-<n>.json`, `suites/<milestone>.json`) | the gate compares the working tree's measured values with its own measurement and with main's committed copies | 0 |
| the design notes, `docs/posters/` | Plan documents; posters (D30) | | 13 |

`prototypes/config.lua` holds the groups below. Their shapes are the contract every Python reader
uses through `tools/tnconfig.py`'s accessors, which raise on a wrong shape instead of reading it as
empty (an empty Lua table `{}` is an empty table of either shape); the T16 names row reports every
shape problem (`tnconfig.schema_problems`). Keyed groups pair with an order list, as `settings` with
`setting_order`.

| Group | Contents | Shape |
|---|---|---|
| Identity | mod ID, title; setting, preset, expression and locale prefixes | `identity = {id, title, version, author, factorio_version, base_version, setting_prefix, noise_prefix}` |
| Maps | key (`europe`, `atlantic`, `olde_world`; settings say `old-world`, APPROVALS 1a), preset name, display name, raster size, `wr` and `hr`, georeference, world size per scale | `maps = {<key> = {key, setting_key, display, width_px, height_px, wr, hr, lon_left_edge, lat_top_edge}}`, `map_order = {<keys>}`; the plan's tables name maps by `display` |
| Scales | 1 to 6, default 6; the coordinate-chain constant `floor(s / 2)` | `scales = {values = {...}, default}` |
| Settings and presets | each setting's name, type, default and values; each preset's name, map and order | `settings = {<key> = {...}}` with `setting_order`; `presets = {<key> = {name, map, order, placeholder}}` with `preset_order` |
| Toggles | setting name, preset key, default, mechanism (name switch or hook gate), on and off values; Exact coastlines with the maps it may act on | `toggles = {<key> = {setting = <settings key>, preset_key, default, mechanism = "name switch" or "hook gate", on, off, maps}}` with `toggle_order` |
| Keys | every `property_expression_names` key any Earth preset sets (D33 guard, missing-name guard, T14); per map, the names its elevation entry reads and whether each is map-qualified (the fallback list) | `preset_keys = {<keys>}`; `fallbacks = {<map key> = {{name = <noise name>, map_qualified = <bool>}, ...}}`: the Map type fallbacks, never registered in `tests/frozen.json`, exempt from `build_zip.py --release`'s registry check and part of the names config defines |
| Firewall | per map, the fine field: the map's elevation entry and every term only it reads (design constraint 3; the isolation checks and the constant-coast twin read it) | `firewall = {<map key> = {<noise names>}}`; in `toolchain` the placeholder's `firewall = {<keys of placeholder.names>}` (its elevation) supplies it, and an empty field fails every isolation check |
| Placeholder | the `toolchain` preset's map, scale, spawn pixel, shore, sea floor, the start mask's constants and its names (never registered or released; `europe-coast` retires it) | `placeholder = {preset, map, scale, spawn_px, shore_tiles, sea_floor, start_mask_floor, start_mask_span, names = {<key> = <noise name>}, keys = {<keys of names>}, firewall = {<keys>}, withheld_with = {<mod names>}}`; `withheld_with` lists the mods whose presence withholds the placeholder preset (`alien-biomes`) |
| Release registry | per release: geography id, every released name, the generated files it loads | `release_registry = {{release = <version>, geography = <id>, names = {<noise names>}, files = {<generated files>}}, ...}` |
| Tunables | transfer gain and sign offset, detail amplitude, ramp, hotspot and enemy constants, every `seed1`, ore frequency 0.75, the forest boost (2; a per-family data value), the random-oil sea threshold on `tn_land_coarse`, the maps Exact coastlines may act on, river width factors (k = 3 major, 2 minor), ford spacing (60 reference px) and length (8 tiles), the Map type and preset orders | keyed tables of numbers, one group per expression module, added by the milestone that reads them |

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
   rule still fails (Dardanelles at every scale; Rhine, Garonne and Little Belt at 6). Rivers are
   `max(7, k s)` tiles wide, k = 3 for a major river and 2 for the rest (the class column of APPROVALS
   7 in `approvals-data.json`; the maintainer, design notes 12:35), carved with half-width `max(3.75, k s / 2)` so
   S4's quarter-tile margin stays on the floor; straits keep S4's half-width
   `hw(s) = max(F / 2 + 0.25, 0.5 s, 0.5 w s / 2.471)` tiles, `F` 7 for one track and 11 for the
   two-way straits; canals `max(7, s)` wide (APPROVALS 6); dams `max(1.5, 0.5 s)` (S4). Fords: on
   each river, one ford every 60 reference px of path length, 8 tiles long and spanning the carve
. Output: `waterways_<map>_s<k>_v<n>.lua` for k = 1 to 6, with separate named
   sets for rivers and straits, canals, dams and fords, plus a manifest with segment counts, ford
   positions, bend-rule results and the T1 corridor masks.
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
   21). The hash covers the fields that shape generation (expression, local expressions and
   functions, a function's parameters), never the GUI fields `intended_property`, `localised_name`
   and `order`, so a newer elevation entry can take the Map type fields over from an older one
   without changing its registered hash. The Map type fallbacks mirror startup settings and are not
   registered (section "Map type entries"). It never changes an existing entry. The gate fails when
   a registered name is missing or its hash changed, so `build_zip.py --release` finds every body at
   any point of the release.
7. **Package.** `build_zip.py` writes `terra-nauvis_<version>.zip` with one top folder, fixed
   timestamps and entry order: two builds give one sha256 (T16), on this machine and on GitHub's
   `windows-latest` runner alike (the repo checks out LF everywhere, `.gitattributes`). `ci.yml`
   uploads that zip as an artifact on every push and pull request; `release.yml` builds the release
   zip on a pushed `v*` tag and publishes it with its `.sha256` as a GitHub release.

Generated files are rebuilt by their tool in the same commit as the change that needs them, and never
edited by hand.

## Coordinates and names

### The coordinate chain

Defined once (`coast.lua`, offsets in `spawn.lua`), mirrored by `tools/earthgeo.py`, shared by every
module:

| Name | Expression | Source |
|---|---|---|
| `tn_cx`, `tn_cy` | if() chain over the map's city table on `tn_city` (0 picks the folded hash of `map_seed`) giving `s (c - wr) + floor(s / 2)` for the city's pixel column c, the tile holding the city's pixel centre (S8 oracle convention), and the same for rows; folds to two constants | S7: Tile 9,350 for 1, 30 or 50 cities and for random; 10,039 for the same chain evaluated per tile |
| `tn_gx`, `tn_gy` | `x + tn_cx`, `y + tn_cy`: the chosen city sits at world (0, 0) | S7 (spawn by shift) |
| `tn_u`, `tn_v` | `(tn_gx - floor(tn_scale / 2)) / tn_scale + wr`, the same with `hr`; `wr`, `hr` folded from `tn_map` for the preset-only consumers; each map's elevation entry binds its own map's `wr`, `hr` and city table instead, through map-qualified names (section "Map type entries") | derived below |

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
| Setting, preset | `terra-nauvis-<name>`, `terra-nauvis-<map>` | `terra-nauvis-scale`, `terra-nauvis-exact-coast` |
| Per-save number (a prototype fallback only when a map's elevation entry reads it) | `tn_<param>` | `tn_scale` |
| Map-qualified per-save name (one fallback per map) | `tn_<name>_<map>` | `tn_city_europe` |
| Hook gate (prototype "0") | `tn_on`, `tn_<feature>_on` | `tn_forests_on` |
| Key (name switch or version selector; no prototype unless it feeds a hook or a map's elevation entry reads it) | `tn_<key>` | `tn_canals`, `tn_coast`, `tn_bandfix` |
| Map type entry (a map's elevation, newest version carries the GUI fields) | `tn_elevation_<map>_v<n>` | `tn_elevation_europe_v1` |
| Released body | `tn_<thing>[_<map>][_s<k>]_v<n>` | `tn_geo_europe_v1`, `tn_ww_europe_s6_v1`, `tn_land_coarse_europe_v1` |
| Region layer | the interface names under "Region layer", each body with its `_v<n>` | `tn_destroyed_depth_v1`, `tn_tree_mult_v1` |
| Neutral bodies | `tn_zero`, `tn_one`, `tn_none` (+inf, neutral for `min`) | |

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

**Firewall rule (binding, on Terra Nauvis presets).** The fine field is each map's elevation entry
`tn_elevation_<map>_v<n>` and every term only it reads: the coast fit, the detail, the far-field
box, the start land guarantee, the waterway and ford sets, the inland lakes and the offshore field
stamps. Only the Tile program reads them, and only through the `elevation` property and the
Tile-only ford hook; the analytic spawn lake is firewall-clean, because it reads only `x`, `y` and
`map_seed`. Every expression the Entity or Cliff program reaches (climate, `distance`, the region
layer, hotspot and enemy terms, ridges, the start mask, the sea mask, the palm switch, tree hooks)
reads only `x`, `y`, `map_seed` and the map-setting constants, per-save numbers and keys, the
coordinate chain, built-in noise, analytic terms built from tables, `tn_land_coarse`, and other
firewall-clean names.

**The coarse land field (decision 8, binding).** The Entity program knows land from one field,
`tn_land_coarse`: a preset key that each Earth preset maps to its map's
`tn_land_coarse_<map>_v<n>`, a tents-256 fit of the coast's own target (S9 used Europe's 256-term
checkpoint in the composite Phase 4 times), defined and budgeted in `europe-coast`. Every Entity-side
land reader uses it and nothing finer: the redirected `starting_resources_lake_mask` (vanilla starting
ore; S9: the coarse field plus the spawn lake), S6's land-aware hotspot and enemy terms through that
mask, the random offshore-oil sea mask, and any later reader. It is coarse: 94.5 percent offline on
S1-fit's curve, and the design review put its coast at p99 14.6 px on Europe, about 88 tiles at scale
6, so the start mask and the sea mask are approximate near coasts; T7 (b) and T8 measure the effect.
The known Entity readers of `elevation` in the maintainer's pack are both redirected on Earth presets: vanilla
starting ore through `starting_resources_lake_mask` (`europe-coast`) and AB's two palms (R3 4.1;
`climate-tiles`). A Map type entry picked alone sets only `elevation`, so neither redirect exists
there and both readers compile the fine field in the Entity program; that route is outside the
firewall by design, timed and reported, never gated (design note 15).

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
| `tn_map`, `tn_scale`, `tn_city`, `tn_geo` | presets | per-save numbers; `tn_map` and `tn_geo` never get a prototype; the scale and the map-qualified city names a map's elevation entry reads get prototype fallbacks (section "Map type entries") | fold into every program | 1, 2 |
| `tn_on`, `tn_forests_on` | presets | hook gates, prototype "0", Earth presets set 1 (forests by toggle) | Tile, Entity | 4 (`tn_on`, fords), 6, 7 |
| fallbacks for the names a map's elevation entry reads | presets | prototype-level named expressions valued as the preset bakes them under the current startup settings; surface values win (S2) | whatever the entry reads | 1, 3 |
| `tn_cx`, `tn_cy`, `tn_city_index_v<n>` | spawn | city tables, `tn_city`, `tn_scale`, `map_seed` | all; control reads the index at (0, 0) | 2 |
| `tn_gx`, `tn_gy`, `tn_u`, `tn_v` | coast | `x`, `y`, offsets, map constants | all | 1 |
| `tn_geo_<map>_v<n>` | generated | `tn_u`, `tn_v` | Tile only | 1, 3 |
| `tn_land_coarse_<map>_v<n>`, through the key `tn_land_coarse` | generated | `tn_u`, `tn_v`; the 256-term checkpoint of the map's fit | Entity (the only land field outside Tile) | 1 (Europe), 3 |
| `tn_detail_v<n>` | coast | `tn_u`, `tn_v`, basis noise; 0 at pixel centres, amplitude set by the fit's gradient | Tile only | 1 |
| `tn_far_v<n>` | coast | `tn_u`, `tn_v`, the map's extent | Tile only | 1 |
| `tn_ww_*`, `tn_canals_*`, `tn_dams_*`, `tn_fords_*` (per map, scale, version) | generated | `tn_gx`, `tn_gy` | Tile only | 4 |
| `tn_spawn_lake_v<n>` | spawn | `x`, `y`, `map_seed`: analytic lake about 72 tiles out at a seed-folded angle (S7: nearest water 42.6 tiles) | Tile; Entity only inside the start mask | 2 |
| `tn_inland_lakes_v<n>` | spawn | `tn_gx`, `tn_gy`, `map_seed`; fixed density, kept out of the start radius | Tile only | 2 |
| `tn_fields_<map>_v<n>` | resources | field table, jitter constants | Tile only | 9 |
| `tn_elevation_<map>_v<n>` | coast | the composition below, one entry per map; the newest version carries `intended_property = "elevation"`, the `[noise-expression]` name "Terra Nauvis: <map>" and its order (the Map type entry) | Tile only | 1 (Europe), 3 |
| `tn_start_mask_v<n>` | spawn | `tn_land_coarse`, the spawn lake, `distance`: `clamp((e - 1) / 10, 0, 1)` with `e = min(tn_scale * tn_land_coarse, tn_spawn_lake)`, S9's form without its far-field box (every tent is 0 outside the raster, S1-fit); no firewall name | Entity | 1, refined 2 |
| `tn_sea_v<n>` | resources | `tn_land_coarse` below the configured offshore threshold, so rivers, canals, D15 lakes and marshes, which the coarse field reads as land, fall outside it (FEAS-07). Large drawn lakes the coarse field reads as water (Ladoga, the Great Lakes) are not excluded by the threshold; `resources-enemies` excludes them through table rows or records the exception, with the threshold | Entity | 9 |
| `tn_distance_v<n>` | spawn | `sqrt(x * x + y * y)` | Entity, Cliff | 2 |
| `tn_temperature_*`, `tn_moisture_*`, `tn_aux_*` (AB and fallback variants) | climate | latitude from `tn_v`, noise, slider controls (`control:hot` and `control:cold` only when AB is loaded, R3 6), region aggregates, `tn_destroyed` | Tile, Entity | 6, 10 |
| `tn_temperature_vanilla_v<n>` | climate | 0.45 times Earth temperature (S3) | Entity | 7 |
| region layer: the interface under "Region layer" (`tn_sd_<id>`, `tn_w_<id>`, `tn_depth_<id>`, `tn_destroyed_*`, `tn_forest_w`, `tn_forest_sum`, `tn_tree_mult`, `tn_marsh_w`, `tn_hotspot_w`, `tn_enemy_mult`) | regions | `tn_u`, `tn_v`, `map_seed`, the shared warp, table shapes, folded hotspot jitter | whichever program reads them: Tile for the zone and marsh lifts, Entity for forests, hotspots and the enemy layer | 5 |
| `tn_vtile_<tile>_v<n>`, `tn_marsh_<tile>_v<n>` | tiles | climate, region aggregates, `elevation` | Tile | 6 |
| `tn_vtree_<tree>_p_v<n>`, `_r_v<n>`, `tn_tree_mult_v<n>`, `tn_palm_const_v<n>` | trees | vanilla-scale temperature, moisture, `distance`, forest aggregates | Entity | 6, 7 |
| `tn_ore_<ore>_p_v<n>`, `_r_v<n>`, `tn_offshore_p_v<n>`, `_r_v<n>` | resources | live autoplace text, hotspot terms on the hotspot rows' membership, ramp on `distance`, start mask, sea mask | Entity | 9 |
| `tn_enemy_v<n>` | enemies | live `enemy_base_probability`, `tn_enemy_mult` | Entity | 9 |
| `tn_cliff_elevation_v<n>`, `tn_cliffiness_v<n>` | ridges | crest polylines in geo tiles, `tn_ridges`, `distance` | Cliff | 8 |

### Preset redirects

Each Earth preset sets these `property_expression_names` keys:

| Key | Value | Program | Milestone | Why |
|---|---|---|---|---|
| `elevation` | `tn_elevation_<map>_v<n>`, the map's own Map type entry | Tile | 1, 3 | coast, waterways, lakes; the preset and the Map type pick name one entry |
| `starting_resources_lake_mask` | `tn_start_mask_v<n>` | Entity | 1 | the vanilla mask reads `elevation` in every starting-ore spot noise (R6 Q3); without the redirect the fine field enters the Entity program. The Earth mask reads `tn_land_coarse` |
| `tn_land_coarse` | `tn_land_coarse_<map>_v<n>` | Entity | 1 | the one land field outside Tile |
| `distance` | `tn_distance_v<n>` | Entity, Cliff | 2 | start features at the spawn whatever `starting_points` holds; D31 can extend it (S7) |
| `temperature`, `moisture`, `aux` | the AB or fallback variant, chosen at data stage from `mods` | Tile, Entity | 6 | S3 |
| `tn_palm_elevation` (AB loaded) | `tn_palm_const_v<n>` | Entity | 6 | AB palms read `elevation` (R3 4.1); REVIEW |
| `cliff_elevation`, `cliffiness` | `tn_cliff_elevation_v<n>`, `tn_cliffiness_v<n>` | Cliff | 8 | S5 |
| `entity:<ore>:probability`, `entity:<ore>:richness` for iron, copper, coal, stone, uranium, crude oil | `tn_ore_*` | Entity | 9 | S6 (the preset route renders byte-identical to an in-place edit) |
| `enemy_base_probability` | `tn_enemy_v<n>` | Entity | 9 | S6 |
| `entity:offshore-oil:probability`, `:richness` (Oil Rig loaded) | `tn_offshore_*` | Entity | 9 | R4 4.7 |
| `tn_map`, `tn_scale`, `tn_city`, `tn_geo` | numbers | fold | 1, 2 | S2 |
| `tn_on`, `tn_forests_on` | 1 (forests: 1 or 0 by toggle) | hooks | 4, 6, 7 | S3, S10 |
| `tn_fords` | the map's ford set for the save's scale | Tile (the `water-shallow` hook) | 4 | design notes 12:35 |
| `tn_coast` | `tn_geo_<map>_v<n>` | Tile | 1 | version selector |
| `tn_waterways`, `tn_canals` | the map's set for the save's scale; canals set or dams set | Tile | 4 | per-scale polylines picked by name (REVIEW) |
| `tn_ridges`, `tn_hotspots`, `tn_destroyed` | the live body or a neutral body | Cliff, Entity, Tile | 8, 9, 10 | name switches (S2) |
| hook keys (`tn_vtile_<tile>`, `tn_marsh_<tile>`, `tn_vtree_<tree>_p`, `_r`, `tn_tree_mult`) | versioned bodies | Tile, Entity | 6, 7 | stable hooks |
| `tn_bandfix` | a name switch, `tn_one`, in a map's preset only when the startup setting Exact coastlines is on and that map passed all four flip checks; absent otherwise, and absent means off | control only | 11 | decision 9 and 12:35 |

Beside the keys, each preset sets `basic_settings.autoplace_controls` frequency 0.75 for the six base
resources and leaves the planet entries neutral (D20; planet values multiply preset values, noise
known gotcha). Every redirect value must name a defined noise expression or be a number: anything
else is ignored with only a log line (noise rule 3). No redirect target reads the property it
replaces (`Parameter 'arg_register' expects Number, None given.`). The presets sort right after
Default: S13 used order "a-tn-a" to "-c" under Default's "a" and before Rich resources' "b".

### Map type entries (D2 amended; S13)

the maintainer wants the three maps in the Terrain tab's Map type dropdown as well as in the preset list. The
Terrain tab lists every noise expression whose `intended_property` is "elevation", labelled from the
`[noise-expression]` locale section (`data/core/locale/en/core.cfg:5256-5268`). The S13 probe
(`spikes/S13-gui/mods/terra-nauvis-probe`; screenshots the design notes) proved the route:
its three entries, order "3000-tn-a" to "-c", listed beside Nauvis, Lakes and Island; picking a
preset set Map type to the matching entry; a slider edit kept the preset's 40 keys; picking only
the Map type rendered Europe's shape and spawn with the base climate and no ridges or hotspots.
Binding rules:

- **One entry per map.** Each map's elevation is its own named expression,
  `tn_elevation_<map>_v<n>`, and the map's preset names it in `elevation`, so both routes generate
  one elevation. Only the newest version of a map's entry carries `intended_property`,
  `localised_name` (a `[noise-expression]` key whose text is "Terra Nauvis: <map>") and `order`, so
  the dropdown lists one entry per map; older versions stay defined for the saves that name them,
  and `tests/frozen.json` hashes only generation fields (Build-time data flow, step 6). Where
  `climate-tiles` gives Alien Biomes worlds their own geography, the entry that install lists is the
  one its preset names.
- **Fallbacks.** A Map type pick sets only `elevation` (`spikes/S13-gui/mgs-maptype-europe.json`),
  so every other name the entry reads needs a prototype-level fallback: a named expression whose
  body is the value the preset bakes under the current startup settings, built from the same table
  as the preset. Surface values beat prototype names (S2), so preset worlds and saves keep their own
  values, and the fallbacks act only on a world made from the Map type alone, which therefore
  follows the startup settings at every load (S2: a value left only as a prototype followed the new
  settings). Fallbacks mirror settings, so they are not registered in `tests/frozen.json`; T16
  checks that each equals what its preset bakes.
- **Map-qualified names.** One prototype fallback holds one value, so a value that differs by map
  (the chain's `wr` and `hr`, the city table and city setting, the coast, coarse, waterway, canal,
  dam, ford and offshore sets) reaches a map's entry only bound inside it or through a
  map-qualified name (`tn_<name>_<map>`), never through `tn_map` or a key the maps share. S13's
  placeholder maps read only the scale, so the probe never met this (derived). Map-independent
  values (the scale) keep one shared name and one fallback.
- **Gates stay off.** Hook gates keep their prototype "0", so a Map-type-only world has the map's
  shape and spawn with the base climate and no ridges, hotspots, forests, marshes or fords; the
  Entity readers of `elevation` compile the fine field there (firewall section), so the route is
  timed and reported, never held to P1, P2 or the isolation checks.
- **Notice.** A world whose Nauvis surface names a Map type entry for `elevation` and holds no
  `tn_geo` is a Map-type-only world. Control code logs a one-time notice that names the map's preset
  and what it adds (Earth climate, ridges and hotspots, and fords from `waterways` on) and sends it
  to each created player (Control stage). Such a world is not an Earth world for the start message,
  the missing-name guard or the band fix.
- **Order.** Entries sort Europe, Atlantic, Old World with vanilla's default entry first (S13's
  "3000-tn-a" to "-c" listed them after Lakes and before Island,
  the design notes); presets sort in the same sequence right after
  Default, before Rich resources (`03-preset-dropdown.png`).

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
| 19 vanilla land tiles re-listed on Nauvis beside AB | `tn_on` | `tn_vtile_<tile>` | `-inf` | 6 |
| `water-shallow` registered on Nauvis: fords, then marshes without AB | `tn_on` | `tn_fords` (4), joined by `tn_marsh_water_shallow` (6) in one hook | `-inf`, or AB's own `water-shallow` expression where AB defines one | 4, 6 |
| `water-mud` registered on Nauvis without AB (marshes) | `tn_on` | `tn_marsh_water_mud` | `-inf` | 6 |
| AB palms: `elevation` replaced by the key | none | `tn_palm_elevation` | `elevation` | 6 |
| 15 restored vanilla living trees beside AB (probability, richness) | `tn_on` | `tn_vtree_<tree>_p`, `_r` | `0` | 7 |
| Forest boost on every living tree (15 vanilla, 67 AB) | `tn_forests_on` | `tn_tree_mult` inside `min(1, (orig) * tn_tree_mult)` | `orig` | 7 |
| Vanilla rocks, decals and decoratives beside AB (R3 3.4 items 4 to 6) | `tn_on` | per name | `-inf` or `0` | 7 (design note 10) |

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
- **Query point.** Rows are evaluated in reference pixels at `tn_u`, `tn_v`, the coordinate
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
| `tn_sd_<id>` | signed distance to row `<id>` in reference pixels, positive inside, at the warped point plus roughness | the aggregates |
| `tn_w_<id>` | membership weight `clamp(0.5 + sd / 6, 0, 1)`: a 6 px ramp, 36 tiles at scale 6 | the aggregates; per-region consumers, such as each hotspot's ore terms |
| `tn_depth_<id>` | the same signed distance in tiles | consumers that grade by depth |
| `tn_destroyed_sd`, `tn_destroyed_w`, `tn_destroyed_depth` | the zone after its rows: `min(include sd, -exclude sd ...)` | the climate lift (temperature above 100), zeroed inside the start radius; the random-pool switch (`destroyed-europe`) |
| `tn_forest_w` | the largest forest weight | forest tiles and decoratives; T10 |
| `tn_forest_sum` | the sum of row boost times weight (row boost 1 by default) | `tn_tree_mult` |
| `tn_tree_mult` | `1 + forest_boost * tn_forest_sum`, forest boost 2 from config | the forest-boost hook on every living tree (S10: probability times 1 + 2 w) |
| `tn_marsh_w` | the largest marsh weight; the same pattern, not measured by S10 | the marsh moisture lift and the marsh tiles (`climate-tiles`) |
| `tn_hotspot_w` | the largest weight over the hotspot rows | the enemy multiplier's footprint; T9 |
| `tn_enemy_mult` | `1 + sum((mult - 1) * w)` over the hotspot rows, mult 4 (APPROVALS 1b) | `tn_enemy_v<n>` |

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

Order is binding; constants live in config.lua. Each map's entry `tn_elevation_<map>_v<n>` composes
its own map's terms; a name below that differs by map stands for that map's own, bound inside the
entry or read through its map-qualified name (section "Map type entries").

1. `c = tn_coast + tn_detail_v<n>` in pixel units. The detail is 0 at pixel centres, so T1 sees
   the fit alone.
2. Transfer: `e = gain * c + if(c > 0, offset, -offset)`, a sign offset (`sign` does not exist in
   2.1.23, noise notes). The offset clears vanilla's land-win margin (land beat water down to about
   -0.027 in S1-fit and -0.0100 in S8), so the tile class equals the sign of `c`. The gain sets the
   shore band AB reads (its shore term reads elevation up to 5; REVIEW). This replaces S1-fit's
   untested 1000 times gain (design review note). Milestone 1 sets both for vanilla; milestone 6 recalibrates
   with AB under each map's entry's next `_v<n>`: beach band present, deepwater below
   -5.5 offshore (R3 3.1).
3. Far field: `min(e, tn_far_v<n>)`, deep water beyond the map's box out to at least 100,000 tiles
   (D15). Every tent is 0 outside the raster (S1-fit).
4. Start land guarantee (`spawn-cities`; design note 14): `max(e, g)`, with `g` positive
   within the guarantee radius of the spawn, so a city whose pixel is water (three on Atlantic, R1
   section 11) starts on land. It precedes dams and carves, so a named waterway still cuts through it:
   D16 wins over the guarantee.
5. Dams: `max(e, 4 * (hw_dam - d * s))` for the canals-off set (S4).
6. Carves: `min(e, max(-2.2 or -6, 4 * (d * s - hw)))` for rivers (-2.2: plain `water` in vanilla
   and AB; `hw = max(3.75, k s / 2)` by the river's class, design notes 12:35) and straits (-6:
   deepwater in both; S4's `hw`), and for canals when on (S4). Dams come first so a dam never closes
   a named waterway. A ford changes no elevation: it stays in the river's water band, so the
   channel stays continuous, and the `water-shallow` hook (Stable hooks) makes its tiles walkable.
7. Lakes: `min(e, tn_spawn_lake_v<n>, tn_inland_lakes_v<n>)`.
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
| Map | the preset itself and the map's own elevation entry, also its Map type entry, plus the number `tn_map` for control code | S2: one elevation name per preset, no map selector; S13 |
| Scale, city, geography release | numbers `tn_scale`, `tn_city`, `tn_geo`; a map's elevation entry reads the scale and its map-qualified city name, each with a prototype fallback | S2 Q4: numbers fill constant-only slots and compile like literals |
| A Map type pick alone | prototype fallbacks valued as the preset bakes them under the current startup settings; no per-save pinning | S2 (prototype-only values follow the settings); S13 |
| Toggles reached through preset keys (canals, ridges, hotspots, destroyed) | name switch: key to the live body or a neutral body | S2: a switch set to off costs the same as no term (425 operations against 433 for a numeric 0) |
| Toggles acting through hooks (great forests) | numeric gate with a prototype "0", outermost `if()` | S3 gate rule; S10 zero-cost identity |
| Versions of a leaf (coast fit, waterway set) | key to the versioned name | S2 Q5 |
| Band fix (Exact coastlines) | name switch `tn_bandfix`: a map's preset carries it only when the startup setting `terra-nauvis-exact-coast` is on and that map passed all four flip checks; absent means off; read by control only | decision 9 and 12:35 |

Rules:

- Never multiply by a toggle: a numeric toggle at 0 still compiles 8 of its term's 10 operations (S2;
  design notes 03:45).
- Prototype defaults exist for three kinds of Earth name only: gates and hook keys, because
  non-Earth worlds compile the hooks, and their defaults are always the off branch; and the
  fallbacks of the names a map's elevation entry reads, valued as the preset bakes them, because a
  Map type pick sets nothing else. Every other per-save number and key has
  no prototype, so a preset world missing one fails at creation with `Unknown variable` (exit 1)
  instead of drifting (S2), and the missing-name guard covers the rest.
- Values read back as strings; control code uses `tonumber` (S7).
- A body never reads a key that saves made before the body existed could lack: new keys are read
  only by new bodies or behind a hook default.
- Servers create worlds by one route only: `--preset` with the server's settings, or a full
  `--map-gen-settings` file; combining them reset `starting_area` (S2 Q2).
- A milestone that adds a per-save value extends the drift line and the key list in config, and adds its
  own T11 row that flips the value, A then B then load.

### Guards (`scripts/guards.lua`)

- **Missing-name guard** (`on_configuration_changed`, Earth worlds, which hold `tn_geo`): every Earth
  key in the Nauvis surface's `property_expression_names` whose value is a name must exist in
  `prototypes.named_noise_expression` (present in the 2.1.23 runtime docs), and every hook key must
  be present. A miss prints a loud error (`log` and a red `game.print`) naming key and value, because
  a dropped name silently gives new chunks vanilla terrain (design review note). It stays silent on a
  Map-type-only world, whose missing keys are by design.
- **Map type notice** (`on_init`, then `on_player_created`): on a Map-type-only world (the surface
  names a Map type entry for `elevation`, which `prototypes.named_noise_expression[name]
  .intended_property` confirms, and holds no `tn_geo`), one log line and one stored message naming
  the map's preset and what it adds; each created player receives it once (S11: `game.print` in
  `on_init` reaches no player). It also records the fallback values the world was created with,
  read from `prototypes.named_noise_expression`, never from `settings.startup`.
- **Drift line** (`on_configuration_changed` with `mod_startup_settings_changed`, which arrives with
  empty `mod_changes`, mod-dev rule 7): one info line per stored scale, city or toggle that differs
  from the current startup setting, for example "this save keeps scale 3; the setting applies to new
  worlds only" (S2 Q3). On a Map-type-only world it compares the recorded fallback values with the
  current ones and says instead that the world follows the changed settings, so new chunks may not
  match. It never changes the world. Whether `game.print` at load reaches a GUI player is
  UNVERIFIED (S2); the log line is certain.

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
4. `tn_geo` increments whenever a geography name a preset points at changes. Control code keys
   release-coupled data (city tables for the message and markers, band-fix data) by the save's
   `tn_geo`, never by "latest".
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
   edit only until then. The maintainer settled the name on 2026-10-27 (Terra Nauvis, `tn_`),
   and the rename dry run still proves a rename stays a data edit: registered names change with the
   prefix there, under a registry it builds for the test ID.
10. Only the newest version of a map's elevation entry carries `intended_property`, `localised_name`
    and `order`. Moving those GUI fields to a newer version edits no registered body, because the
    registered hash covers generation fields only (Build-time data flow, step 6). The Map type
    fallbacks are never registered: they mirror startup settings, and T16 checks them against the
    presets instead.

## Control stage

### Events

| Event | Script | Work |
|---|---|---|
| `on_init` | start, guards, markers | Earth world means the Nauvis surface's `property_expression_names` holds `tn_geo`; never decided from `settings.startup` or a noise fallback. A Map-type-only world (the surface names a Map type entry for `elevation` and holds no `tn_geo`; milestone 1): log and store the Map type notice and the fallback values, run the D33 sweep and stop. Other non-Earth worlds: run the D33 sweep and stop. Earth: fill `storage.earth` (schema, map, scale, city, geo, toggles) from those values with `tonumber`; read the resolved city index with `calculate_tile_properties` at (0, 0), because the random pick folds in float32 and Lua cannot recompute it (S7: seed 4294967295 gave city 8, the integer hash city 1); set the D29 intro through `remote.call("freeplay", "set_custom_intro_message", ...)` when that interface exists, plus a log line; cliff "none" reset (ridges on and `nauvis_cliff` size 0: write size 1 back with a whole-table assignment and log it; S5 restored 330 of 330 cliffs); D32 RSO warning when `script.active_mods["rso-mod"]` (log `RSO-WARNING` and a localised print, S11); D12 warning when Destroyed Europe was requested without AB (`on_init` runs under the creating settings); both recorded in `storage.earth.warnings` for the per-player path; D33 sweep; markers if their setting is on; band-fix flag from the save's own key (milestone 11) |
| `on_load` | control | re-register the band-fix handler when `storage.earth.bandfix`; never writes storage (mod-dev rule 9) |
| `on_configuration_changed` | guards | missing-name guard (Earth worlds); drift line (Earth and Map-type-only worlds); D33 sweep; storage schema migration written to be harmless on storage that `on_init` built (mod-dev rule 6) |
| `on_surface_created` | guards | D33 guard on the new surface (it fires inside `LuaPlanet.create_surface`, S11) |
| `on_player_created` | guards | send each stored message to the new player once: the Map type notice on a Map-type-only world (milestone 1), and on an Earth world each warning in `storage.earth.warnings`, RSO (D32) and Destroyed Europe without AB (D12): S11 found that `game.print` in `on_init` reaches no player. Tested on a loopback server with a scripted player, a route still UNVERIFIED (Conflicts, item 15) |
| `on_runtime_mod_setting_changed` | markers | D28 markers on or off |
| `on_chunk_generated` | bandfix | registered only when `storage.earth.bandfix` (milestone 11) |
| `on_chunk_deleted`, `on_surface_cleared`, `on_surface_deleted` | bandfix | only if the band fix keeps per-chunk keys (worldgen-runtime rule 1) |

Never registered: `on_tick`, `on_nth_tick`, `on_chunk_charted`, or any other per-tick or per-chunk
event. T16 checks the registrations statically, as an allowlist: the global `script` appears only as
the base of a direct `script.on_event(defines.events.<name>, ...)` with an event of this table, a
lifecycle call in `control.lua` or `scripts/`, or a read of `script.mod_name`, `active_mods`,
`feature_flags` or `level`; an alias or other use of `script`, indirect global access (`_G`, `_ENV`,
`rawget` and the like), a `require` of anything but a file of the mod or an allowed core module (the
core `event_handler` library registers events), a computed index into `defines.events`, and any
reference to a per-tick event or, outside `scripts/bandfix.lua`, to a per-chunk event fail it.

### Rules

- Control code reads save state only: the surface's `property_expression_names`, `storage`,
  `calculate_tile_properties`, `script.active_mods`. Per-user settings never steer game logic, and
  `math.random` is never called; any `LuaRandomGenerator` (band fix only) takes a hashed seed
  (worldgen-runtime rule 7).
- `calculate_tile_properties` runs only on Earth worlds, where every per-save name it needs exists,
  and on Map-type-only worlds for the names their fallbacks supply.
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
- Without AB, Earth touches no vanilla tile or tree autoplace except the gated `water-shallow` hook
  (fords from `waterways`, marshes from `climate-tiles`), the gated `water-mud` marsh registration
  and the forest-boost hook; the fallback climate dries the north and keeps the desert on vanilla
  sand (S3 section 4). With AB, the `water-shallow` hook wraps AB's own `water-shallow` autoplace,
  which stays the off value, so AB's coastal shallows are unchanged on every world. Destroyed Europe
  requested without AB leaves the world equal to "off" and warns at creation and to every created
  player.

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
  sea mask `tn_sea_v<n>`, which reads `tn_land_coarse`, plus the field terms
  (APPROVALS 3). The offshore threshold is set in `resources-enemies` with a design note (FEAS-07).
- The Oil Rig re-adds offshore oil in `on_init` and `on_configuration_changed`, calls
  `regenerate_entity`, and writes Nauvis map settings by read, modify and write, which keeps
  `property_expression_names` (S11, R4 4.6).
- Waterway widths keep R4's ship floors: 7 tiles single track, 11 for two-way straits (S4); rivers
  grow above the floor with scale, `max(7, k s)` by class.
- Fords are `water-shallow`: it carries `water_tile`, the one tile layer waterway pieces need (CS
  water_rails.lua), lacks `player`, so characters and biters walk it, and no tile blocks a ship
  (R4 1.3). Masks only so far: `waterways` proves placement (`can_place_entity`) and walkability in
  game. Random offshore oil never reaches a ford, because the sea mask reads the coarse field, which
  reads rivers as land (FEAS-07).

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

**The weaker-machine proxy is 16 LP** (typical player PCs are only slightly
weaker than his 24-thread machine): affinity 0xFFFF, the eight P-cores with both hyperthreads (TQ1b
pinned 0xFF to four of them). Every timed threshold that runs on the proxy runs at 16 LP; 8 LP
(0xFF) is recorded beside it as a diagnostic and never gates. TQ2 timed 8 and 24 LP only; TQ3
re-timed its composite at 16 LP (the design notes): 1.045 and 1.048x
vanilla, 1.249 and 1.213x AB alone. The 8 LP figures below are history.

| Budget | Value | Source | Enforced by |
|---|---|---|---|
| Forced generation, full program, Earth over vanilla, 16 LP (TQ1b block, affinity 0xFFFF), per map at scales 6 and 1 | at most 1.5x: the binding performance rule (the plan's P1). TQ3: S9's Europe composite 1.045x on TQ1b's block and 1.048x far at 16 LP; TQ2: 1.26x and 1.19x at 8 LP, 1.00 to 1.03x at 24 LP | D7; TQ2; TQ3 and 13:20 | the gate (Europe at scale 6, every milestone); the suite of every milestone that adds Tile or Entity work, per map; `ridges` completes and times every map's full program |
| Same, Earth plus AB over AB alone | at most 1.5x at 16 LP (the plan's P2). AB alone is 1.00 to 1.05x vanilla at 24 LP and 1.19 to 1.21x at 8 LP; TQ3 timed S9's composite at 1.249 and 1.213x AB alone at 16 LP, inside the bar (TQ2: 1.59 to 1.66x at 8 LP, 1.20 to 1.23x at 24 LP), so `climate-tiles` keeps the flip rule for Alien Biomes worlds (cut order below) as a guard, for a map the build pushes over 1.5 at 16 LP | decision 5; REVIEW, TQ1b, TQ2, TQ3, 12:35 and 13:20 | the same, from `climate-tiles` |
| Relative limit per milestone | the formula and the per-milestone time allocations in the plan's table (section 6.3), read against TQ3's 16 LP composite (1.045x vanilla and 1.249x AB alone on TQ1b's block) until `europe-coast` records the build's own (TQ2 gave 1.26x and 1.66x at 8 LP) | decisions 3 and 5; TQ2 | gate perf step |
| Same, 24 LP | at most 1.5x (the plan's P3, whose From names no milestone, so it is in force from `toolchain`) | D7 | milestone and release suites: the runner holds every 24 LP forced-generation ratio of an Earth modset against its comparator to it wherever a suite records one (`toolchain` records none) |
| Exploring, the in-play lag (asynchronous generation, R8 2.8) | gated in real time at 60 UPS on a loopback server, TQ2's frontier at 24 LP: ticks over 20 ms, the p99 interval and the longest interval (the plan's P4 to P6), against vanilla (AB: AB alone); benchmark mode recorded per milestone, its `scriptUpdate` gated (P7). TQ2: 2 late ticks of 2,160 (EarthMaps 108, Factorio World 120), p99 17.6 against vanilla's 17.5 ms; benchmark mode 4.46x vanilla's mean, because a column's tile step (78 ms on S9's composite) lands inside a tick only when ticks run back to back | decision 7 as design notes 10:20 restates it; TQ2 | milestone suites from `europe-coast`, re-validated by the gate perf step |
| First column into empty land | a request into empty land builds a 7 x 17 chunk support neighbourhood, 7 columns of tile work at once; TQ2: 466 ms of main thread in benchmark mode, a 302 ms interval at 60 UPS (505 with AB), longer than either world mod's longest (41 and 86 ms); the plan's P6 limits it, and `europe-coast` traces and reduces it | TQ2 | milestone suites from `europe-coast` |
| Tile complexity per world | a diagnostic cap with per-feature allocations in the plan's table (P10, P11, section 6.3). the review's provisional 113,000 sat on the 8 LP chord between tents 4,096 (0.993x) and 16,384 (1.641x), which reaches 1.5x near 121,600; TQ2 timed S9's composite (Tile 112,387) at 1.26x at 8 LP, under the chord's 1.44 estimate, while with AB (173,325) it timed 1.66x AB alone at 8 LP, so on M2 the timed rule binds, not the cap | decisions 3 and 5; REVIEW, TQ1b, TQ2 | gate perf step (T15a) |
| Europe, measured | S9's composite at scale 6, toggles on: Tile 112,387, Entity 12,443, Cliff 124 (with AB 173,325, 25,259, 124), without inland lakes, marshes, turning basins or the land guarantee | S9; TQ2 (the same numbers) | timed by TQ2: 1.19 to 1.26x vanilla and 1.59 to 1.66x AB alone at 8 LP |
| Olde World, estimated | tents about 78,300 + waterways about 32,700 + about 2,000 | REVIEW | untimed (TQ2 timed Europe only); `olde-world-atlantic` times it |
| Atlantic | first fit 69,000 to 96,000 (6,800 to 10,400 terms, est.); its waterways get the cap minus the coast minus the headroom the plan reserves for later Tile work (lakes, basins, marshes, offshore stamps; FEAS-08) | REVIEW; FEAS-08 | `olde-world-atlantic` |
| Entity complexity | per-feature allocations in the plan's table (P12, P13, section 6.3); TQ2 measured Europe's composite unchanged (12,443; 25,259 with AB), and Atlantic's and Old World's ceilings stay provisional. Measured increments: hotspots with the enemy layer +1,491 (S6); Europe forests +2,332 (base) and +2,538 over AB (S10); destroyed zone +592 through climate (S3); Atlantic and Old World forests about +5,600 and +5,000 (projected, S10); `tn_land_coarse` inside S9's 12,443, not isolated | S3, S6, S9, S10, TQ2 | gate perf step (T15a) |
| Entity with AB | Earth plus AB 22,507 against AB alone 24,377 with S3's analytic climate; S9's composite 25,259 | S3, S9 | M2 rows |
| Cliff complexity | vanilla 287; ridges about 4.4 per range segment; S9's whole Cliff program 124 for three Europe ranges | S5, S9 | T15a |
| Isolation | Entity and Cliff identical between the real build and the constant-coast twin, with and without AB, while the twin's Tile differs; no Entity or Cliff root reaches a firewall name, on the presets | decision 8; S9 | gate perf step |
| A Map type entry picked alone | reported, not gated: its Tile, Entity and Cliff complexity and its forced-generation ratio at 16 LP, scale 6, against M0 (M2: BAB); vanilla's starting-ore mask and AB's palms read the fine field there (Map type entries) | design notes 12:35; TQ1b | `europe-coast`, `olde-world-atlantic`, `climate-tiles` |
| Earth Lua per chunk | 0 without the band fix; `scriptUpdate` within 0.01 ms per tick of vanilla | brief section 5, test notes 5.5 | T16 static allowlist; gate perf step |
| Band fix, when on (Exact coastlines) | per map: average at most 0.24 ms per generated chunk and no handler tick above 2 ms, measured on Europe at scale 1 and on Olde World at scale 6, both at 16 LP, with 8 LP recorded | design notes 07:05 and 12:35 | `coast-band-fix` |
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
M2t/BABt at 16 LP: waterways cut to a 1 px tolerance first, then a
cheaper geography chosen at the data stage only when `alien-biomes` is loaded, baked per save as
`tn_geo` and registered
as the next geography version, while base worlds keep their fit and both geographies stay defined
in every install.

## Invariants

Design constraints (each enforced by the gate):

| # | Invariant | Enforced by |
|---|---|---|
| S-1 | Every game run goes through `%FACTORIO_WS%\tools\fh.py` with its own instance and modset, and every run that writes data has a RESULT line reading `isolated=yes`; nothing launches the game against, or writes to, `%APPDATA%\Factorio`, and nothing in the repo installs into a mods folder (players get the zip of a GitHub release by hand) | `earth_test.py` refuses any other RESULT on a run that writes data (`--version` and `--help` runs are exempt and say so; a loopback server passes with `exit=timeout`, TST-11), and a run whose `run.json` records isolation as anything but true, a NOT-ISOLATED RESULT or a run on another build (G8) stops every further game run of the command at once (no row or group loop catches it: the job is terminated and the guard check runs), as do the game self-test and `dump_render.py` on their own runs; a live-profile guard snapshot and check around every command that launches the game, gate, suites, install-check and perf (G9), chained on the chain's last entry, re-baselined only by a part's first command after a clean previous part (the plan defines no other re-baseline: a dirty guard stops all game runs and is reported first on the parent issue, and only the maintainer clears it, by hand at an interactive terminal); every start fails on a build instance's game log newer than the chain's last clean end (a game run outside every chained bracket); the bracket token every repo tool that launches the game checks (`tools/tnguard.py`), and the output refusal of the live profile in every spelling (extended-length, device, UNC and NT-namespace spellings are refused outright), of a file with a second hard link or a folder holding one or a link into the profile, and of any folder named mods, for every option any tool writes, each judged at the absolute path the tool writes (a relative path joined to the tool's own base, never re-anchored by a subprocess) (each declared in `tnguard.py`, checked by T16); the T16 launch scan over every file of `tools/`, `tests/` and `.github/` and the root scripts |
| S-2 | Registered expression bodies are byte-frozen in their generation fields (`tests/frozen.json`, from `europe-coast` on); names are append-only; the Map type fallbacks, which mirror startup settings, are the one exemption | the gate's frozen row on the dumps the runner's registry names (M1; M2 from `climate-tiles`): every Earth body (a prefixed or config-defined noise body) registered unless it is the placeholder's or a fallback, every registered body present and unchanged, with the exact freeze command on a failure; the T16 frozen row (every noise name config.lua defines, the same exemptions, against `tests/frozen.json`) and fallback check; config.lua's schema (every firewall body but the placeholder's in a release row, every noise name prefixed); `build_zip.py --release` refuses any other unregistered body |
| S-3 | On Terra Nauvis presets the Entity and Cliff programs never read the fine coast field; their one land field is `tn_land_coarse`. A Map type entry picked alone is outside this by design and is timed and reported (Map type entries) | isolation check (a) against the constant-coast twin and (b) the static walk, gating from `toolchain` (whose placeholder preset redirects the start mask too), each with its positive controls on the test-only `ea-leak-fixture` presets (the start-mask route; for (b) also a redirected entity and decorative autoplace key, which the walk follows as the program reads it); beside Alien Biomes, whose palms read `elevation`, the placeholder preset is withheld, which the gate's `ab_placeholder` row checks on M1 plus the live AB copy, its control walking the palms to the fine field. That row speaks only for presets marked placeholder and retires with the placeholder in `europe-coast`. From `europe-coast` until `climate-tiles` the real presets are defined beside AB and AB's palms read their `elevation` entry, the fine field, in the Entity program (the leak design notes 17:55 measured on the placeholder): that leak is outside the gate in parts 2 to 4, and `climate-tiles` closes it with the palm switch and the M2 isolation checks (design note 9) |
| S-4 | No per-tick handler, and no per-chunk handler except the band fix, which is registered only on saves whose map's preset carried the band-fix key (Exact coastlines on, the map's checks passed) | T16 static registration allowlist; `scriptUpdate` in T15c and T15d |
| S-5 | All names (mod ID, settings, expressions, presets, locale keys) come from `prototypes/config.lua` | T16: no literal names or coordinates outside config and tables; D36 rename dry run |

Design invariants (binding, from the reports):

| # | Invariant | Source |
|---|---|---|
| A-1 | Default-preset worlds stay byte-identical and complexity-identical to the same modset without Earth (T13 zero-cost rows); Earth makes no global `cliff_removal_probability` edit | S3, S10 |
| A-2 | Every Earth edit to a shared prototype's autoplace is a stable hook, and a gated hook's outermost node is the gate `if()` | S3 |
| A-3 | No redirect target reads the property it replaces | noise notes |
| A-4 | Map-shaping values are baked into the preset; no expression reads a startup setting at generation time (the Map type fallbacks are constants built at the data stage); control code reads map, scale and flags from the save, or on a Map-type-only world from the fallbacks | S2 Q1, design review note; S13 |
| A-5 | Toggles never multiply; selection is a name switch or an `if()` on a folded parameter | S2, design notes 03:45 |
| A-6 | Prototype defaults exist only for gates and hook keys, whose defaults are neutral (gates default to off), and for the fallbacks of the names a map's elevation entry reads, valued as the preset bakes them; values that differ by map reach an entry only through map-qualified names | S2; S13 |
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
| A-20 | Every curated river carries a walkable `water-shallow` ford every 60 reference px of its length, 8 tiles long and spanning it, through which waterway pieces still place and ships still pass | design notes 12:35; R4 1.3 |
| A-21 | Each map's preset and its Map type entry name one elevation; a Map type pick alone renders that map's shape, never another map's | design notes 12:35; S13 |

## Milestone contracts

Each milestone's binding additions. Checks are test notes ids; the plan's acceptance criteria are
authoritative for thresholds, and the perf gate reads them from the plan's threshold table (decision
3). Headings give this file's build-order number and the plan's part and order; builders find their
milestone under "### Milestone <order>: <id>" in the design notes.

Every milestone: its gate stays under 10 minutes; a milestone that adds a per-save value adds
its T11 row; from `europe-coast` on, a milestone registers each versioned body it adds in
`tests/frozen.json`; a milestone that adds Tile or Entity work times each shipped map's
program at 16 LP at scales 6 and 1 in its suite, with 8 LP recorded beside it (decisions 5 and 6;
design notes 12:35); a milestone that changes a map's elevation ships the entry's next version, which
takes over the Map type fields.

### 0. `toolchain` (part 1, order 0)

- **Introduces.** The mod skeleton (info.json, settings.lua with the scale setting, locale, LICENSE,
  changelog.txt, control.lua registering nothing yet), config.lua, a placeholder Terra Nauvis: Europe preset
  with a coarse land shape so installCheck has an Earth preview, `tools/earth_test.py` (`gate`,
  `suite`, `install-check`, `baseline`, `freeze`; the content-hash cache; the guard around every
  command; the threshold-table parser), `build_zip.py`, `perf.py`, the lint setup, S8's tools and
  `earthgeo.py` with their self-tests, `data-src/earthmaps/` with provenance, ported copies of the S8
  reference JSONs and `approvals-data.json` with their sha256, `tests/budgets.json` for
  measured values, an empty `tests/frozen.json` with its checker (hashing generation fields only),
  `tests/baselines/` for build 87750, the T3 oracle's brief-sourced climate rows, the
  `static` command, and `.github/workflows/ci.yml` and `release.yml`.
- **Contract.** The runner refuses to run a game-launching command without `FACTORIO_WS` and fh.py;
  `static` launches nothing and runs in CI; every game run is isolated
  (S-1); the build is pinned to 2.1.23 build 87750 (G8); zips are byte-reproducible, here and on
  GitHub's `windows-latest` runner; the workflows never run the game and hold no secret but the
  workflow's own `GITHUB_TOKEN`; the placeholder
  preset's names are never released, and `europe-coast` retires the preset with every registration it
  made. The gate's wall time is measured here, and a deliberately heavy probe shows which
  `mapGenerator*` column moves (PERF-15).
- **Gate.** T16 (the workflow scan included), T13 load on M1, tool self-tests (S8: 62, 760, 10, 4
  and 10 offline checks and the 31-check game suite). Design constraint 3 holds on the placeholder
  preset too: it redirects `starting_resources_lake_mask` to `tn_placeholder_start_mask_europe`, a copy
  of vanilla 2.1.23's start mask that reads `elevation_nauvis`, so isolation (a) (Entity and Cliff
  equal between the real build and its constant-coast twin while Tile differs) and (b) (no firewall
  name under any Entity, decorative or Cliff root of the dump walk) gate from here. Their positive
  controls run on test-only presets of `tools/mods/ea-leak-fixture`: one carries every key of the
  first Earth preset but the start mask (numbers stay numbers), so the fine field alone is
  redirected and both checks must report vanilla's starting-ore mask reaching it; the other carries
  every key plus an entity and a decorative autoplace key (`entity:<name>:probability` and the like,
  the form the ore and offshore-oil redirects take from `resources-enemies`) redirected to fixture
  bodies that read the fine field, and (b) must follow both, since the walk reads a placed
  prototype's property keys through the preset (and the planet's own redirects) and its own
  autoplace text only when a key is not redirected. Beside Alien Biomes the placeholder preset is
  withheld, because AB's palms read `elevation`; the `ab_placeholder` row dumps M1 plus the live AB
  copy (`fh.py modset --from-live`), finds no preset marked placeholder there, and its control walks
  that dump with the placeholder's redirects to the fine field through the palms. The row retires
  with the placeholder in `europe-coast`; from then until `climate-tiles` the real presets exist
  beside AB, AB's palms read their `elevation` entry in the Entity program, and that leak is outside
  the gate until `climate-tiles`' palm switch and M2 isolation checks close it (S-3).
  P10 and P14 (and, as each milestone brings them into force, every complexity row of 6.2, bound by its
  program, modset and map), P18 (M0t against M0t at 16 LP, from suite evidence and the live sample,
  with rule 5's pooled group near a bound) and P3 (every 24 LP Earth ratio a suite records; none
  yet) gate from here. The frozen row already requires every Earth body of the M1 dump but the
  placeholder's to be registered, so it passes trivially here and binds from `europe-coast` on.
- **Build note** (process, not a contract). The build hands the builder only the args record, so
  before writing code the builder reads its issue, whose acceptance criteria the review
  audits, the plan's "### Milestone 0: toolchain" with its sections 2, 4, 5 and 6, this section, and
  test notes G1 to G10, T13, T16 and 5.2 to 5.6. Order of work: the final code change, then
  `python tools/earth_test.py baseline`, then `python tools/earth_test.py suite toolchain` last. A
  later change re-runs the suite, or the gate fails on stale suite evidence.
- **Fit review, folded in.** The accepted patches beyond the rows above; where the build decided
  differently, the design notes entry named here governs.
  - *Ported planning data.* `spikes/` on main is an ignored, empty shell, so every spike
    input is read with `git show` or `git archive` from the prototype branch (`45c86d706c21`).
    `data-src/earthmaps/<map>.json` and `data-src/approvals/approvals-data.json` are byte copies;
    each `PROVENANCE.md` records the planning commit, every file's sha256, EarthMaps commit
    `23c647b8` and the decoder command. T16's data-src row re-hashes the copies. The gate's data_src
    row regenerates the rasters with `python -I tools/earthmaps_decode.py` from
    `%FACTORIO_WS%\downloads\earthmaps\src` into its run directory (`--no-simulation`: the PNGs do
    not depend on it), compares each PNG byte for byte with the committed file and with the sha256
    its reference JSON records under `png`, and checks sizes and class counts against that JSON. No
    gate step reads `spikes/` or `previews/earth-plan/`.
  - *Porting fixes.* The S8, TQ1 and TQ2 tools derive no path root from their spike location:
    rasters and reference JSON come from `data-src/earthmaps/`, the oracle from `tests/oracle/`,
    docs from the repo root and the workspace from `FACTORIO_WS`. The game self-test and the timing
    jobs run on `ea-` instances and modsets; TQ2's `tq2-driver` is ported, not
    rewritten.
  - *Self-test counts.* 62 + 760 + 10 + 4 + 10 are S8's counts on S8's own inputs, and each offline
    self-test passes with zero failures; `oracle.py selftest` reproduces the 760 on S8's place set,
    the byte-copied fixture `tests/oracle/s8/`. `oracle.py validate` checks the rows
    `tests/oracle/<map>.json` adds (R7b, R7a, R1 and the brief's climate rows) separately: each has
    a source, its expectations are null or tagged per decisions 14 and 19, and `reference_holds` runs
    only where a land expectation exists. The issue evidence records the actual counts.
  - *Freeze and `--release`.* `earth_test.py freeze` and the frozen-body checker ship here; both
    hash generation fields only and are append-only, and the checker's controls make a changed hash
    and a missing name fail and a GUI-only field change pass. config.lua marks the placeholder's
    names: freeze never registers them, the checker exempts them, and `build_zip.py --release`
    refuses while one exists. `--release` finds Earth bodies statically from config.lua through
    `tools/tnconfig.py`, because `release.yml` runs without the game.
  - *T15a bootstrap.* `tests/budgets.json` keeps the placeholder preset's complexity rows under
    their own row key `placeholder`, never as `europe` rows. They meet the caps (P10, P14) and
    `toolchain`'s 6.3 allocation, differ from vanilla's 10,068 / 8,549 / 287 (G5), and
    `europe-coast` deletes them when it retires the preset. For a row main lacks (a map's first
    rows) the growth base is the comparator's row, M0, or BAB for M2 rows: the base 6.3's
    allocations were computed over (S9's Europe Entity minus its hotspot and forest increments,
    12,443 - 1,353 - 2,307 = 8,783, is the +234 over M0's 8,549 that 6.3 cites; derived).
  - *Positive controls and PERF-15.* The fit review assumed a placeholder without a start-mask
    redirect, with both isolation checks run as record-only controls reporting the leak through
    vanilla's starting-ore mask (R6 Q3). The build redirects the start mask instead and gates both
    checks from here, with the leak controls on `ea-leak-fixture` (design notes 15:25 and 16:40; Gate
    above). PERF-15 runs once in the milestone suite, record-only: the benchmark-mode walker times a
    deliberately heavy probe elevation (`tools/mods/ea-heavy-probe`) against M0 and records which
    `mapGenerator*` column moves, next to Phase 4's BasicTilesSupportCompute finding
    (BENCHMARKS.md:247-272).
  - *Section 6 parser.* The plan is read with `git show main:the design notes. The fit review
    parsed only the rows in force; the build parses every 6.2 and 6.3 cell in every gate, fails
    closed on an unreadable one, and fails on a TBD-P4 cell only where it is in force (design notes
    16:40 and 17:55).
  - *Launch scan.* `static` runs without fh.py, so `tools/lint/fh-flags.json` vendors fh.py's
    `GUI_FLAGS` and `FORBIDDEN_EXTRA` with fh.py's sha256, and the gate's fh_flags row, which has
    `FACTORIO_WS`, fails when they differ from fh.py's sets, read with `ast` and never imported.
    Flags match only as argv tokens bound for fh.py or a process launch (string constants in
    argument lists; tokens in `.ps1`, `.yml` and `.cmd` lines), never free text, so `python -m` and
    `git -c` pass. The game's process image is named only in `tools/perf.py` and
    `tools/affinity_watch.ps1`, never as a launched program, and `fh.py modset` is the only way a zip
    reaches a mod directory. Every scan fixture (launch, workflow, attribution) is generated at run
    time in a temporary directory outside the scanned trees and never committed, so the real scans
    need no exemptions.
  - *Attribution scan.* The scanner assembles its patterns from fragments at run time
    and writes its positive-control fixture into a temporary directory: no committed file, command
    line, CHANGELOG.md or the design notes holds a literal pattern, and the guard is never bypassed
    (U14).
  - *CI independence.* `static` and `build_zip.py` read only the checked-out tree: no git refs (a
    default `actions/checkout` has no local main on pull requests and branch pushes, so the
    plan-versus-main and budgets-versus-main comparisons are the gate's alone), no fh.py import and
    no `FACTORIO_WS`. The zip stores its entries uncompressed, so it is
    byte-identical on `windows-latest` whatever the zlib; the build record still names the
    interpreter and zlib, and CI pins Python 3.13.3. The release step compares the CI artifact with a
    local build after the part (design section 18). CI installs luaparser 4.2.0 and luacheck at the
    versions `tools/lint/` records and checks the linter's sha256.
  - *Lint.* No linter was on PATH, so luacheck 1.2.0 is downloaded under project rule 8 into its own
    directory under `%FACTORIO_WS%\downloads\` (version, source URL and sha256 in `tools/lint/`),
    with Factorio's globals declared per stage. The file-count rule covers the
    zip's Lua files (`terra-nauvis/`); luaparser parses every Lua file in the repo, `tools/mods/`
    included.
  - *Runner robustness.* Every fh.py launch runs in a kill-on-close job object, so a
    hard-killed runner takes its game tree with it. The workspace lock
    (`%FACTORIO_WS%\previews\earth-build\earth-test.lock`) records its owner's PID, and a lock whose
    owner is dead is free. The guard chain lives outside the repo under
    `%FACTORIO_WS%\previews\earth-build\guard\part-<n>\`, keyed by the part the command's milestone
    belongs to: a part's first command re-baselines, and every other command's start snapshot must
    equal the chain's last end snapshot.
  - *T16 scope.* The name scan covers the mod's Lua under `terra-nauvis/`, config.lua excepted, and
    `tools/mods/`, whose test mods get any Earth name from the runner at run time, so the D36 rename
    dry run stays a config edit. The placeholder shape takes every coordinate and constant from
    config.lua (S-5). settings.lua ships only the scale setting, so the design-rules check asserts
    APPROVALS 1a defaults only for settings that exist, and each later milestone adds its own rows. A
    dependency version has at least two numeric parts (mod-dev rule 4): `base >= 2.1.23` passes,
    and the `?` dependencies carry no version.
  - *Docs and source offer.* The builder writes the CHANGELOG [Unreleased] entry, with the
    measured cold and warm gate times and their run directories, and a the design notes entry for each
    fork (the linter, the placeholder shape, any gate row moved to the suite under rule 4); the
    commit step keeps them and adds no second entry. The zip's top folder
    carries `LICENSE` (GPLv3) and `SOURCE-OFFER.txt`, which tells a recipient how to obtain the
    corresponding source (the mod, `tools/` and `data-src/`) from the author (GPLv3 section 6).

### 1. `europe-coast` (part 2, order 0)

- **Introduces.** `build_geo.py` and `geo_europe_v1` from the existing 8,192-term checkpoint;
  `tn_land_coarse_europe_v1` from its 256-term checkpoint, defined and budgeted here;
  the coordinate chain with the `floor(s / 2)` constant (`tn_cx`, `tn_cy` are 0 until
  `spawn-cities`); the transfer, detail and far-field box; `tn_elevation_europe_v1`, also Europe's
  Map type entry, with its fallbacks and the Map type notice (section "Map type entries"); the real
  Terra Nauvis: Europe preset, ordered right after Default; scale 1 to 6 with world-size labels
  (APPROVALS 1c); `tn_map`, `tn_scale`, `tn_geo`; the `starting_resources_lake_mask` redirect to
  `tn_start_mask_v1`, which reads the coarse field; `scripts/guards.lua` with the missing-name guard,
  the drift line and the notice, and `on_player_created` for the notice; the first
  `tests/frozen.json` entries.
- **Contract.** The firewall and the isolation check, (a) against the constant-coast twin on M1 and
  (b) the static walk, start here. The lake-mask redirect belongs here, not in
  `spawn-cities`, because vanilla starting ore would otherwise carry the fit into the Entity program
  and fail (a). The preset's geography names and `tn_geo` are chosen in one place at the data
  stage, so `climate-tiles` can give Alien Biomes worlds a cheaper geography without touching base
  worlds.
- **Gate.** T1 for Europe at scales 1, 3 and 6 from preview mode or dumped tiles, thin water and
  corridors masked, at least 99.1 percent; T2; T11 (map, scale, geography id); T13 and T16 on the Map
  type entry (dump fields, locale, fallbacks, the elevation-only route) and T18 on its notice; T15:
  the gate's timed row at 16 LP and the exploring rows start here, in real time and in benchmark
  mode (decision 7 as design notes 10:20 restates it), with the save increment, the first measured values
  recorded; the Map type route timed and reported; the first-column hitch and the start-area save
  excess traced and a reduction of each tried; V1 contact sheets; the
  drift line. REVIEW's deciding experiment: time tents 8,192 alone and the Europe program at 24 and
  16 LP, with 8 LP for the chord TQ1b timed at 8 and 24 LP, and record the chord's error.

### 2. `spawn-cities` (part 2, order 1)

- **Introduces.** City tables and per-map city settings with random, minus the cities APPROVALS 12
  removes; `tn_city`, `tn_cx`, `tn_cy`, `tn_city_index_v1` (random is the folded hash of
  `map_seed`, S7); the analytic spawn lake; the start land guarantee (composition step 4); sparse
  inland lakes at a fixed density; the `distance` redirect; a refined start mask for coastal and
  low-lying cities (vanilla's mask starves starting ore below elevation 11, S7); `scripts/start.lua`
  (world detection, storage, D29 message); the D32 warning at creation and to every created player
, on the per-player path `europe-coast` opened for the Map type notice; the D33 guard;
  Europe's city setting reaching its elevation entry through a map-qualified name with its own
  fallback, so a Map type pick spawns at the setting's city.
- **Contract.** Starting ore and the enemy-free start come from vanilla's own terms through
  `distance` at the origin, the lake from the analytic spawn lake (S7: one patch per ore, 0 enemies
  within 150 tiles, nearest water 42.6 tiles). Under the shift every world coordinate converts as
  `world = geo - (tn_cx, tn_cy)`.
- **Gate.** T7 first on a coastal and low-lying sample (London, Lisbon, Oslo, Amsterdam and Helsinki
  at scale 1; FEAS-06), then every Europe city at scales 1, 3 and 6 (fast subset in the gate); T4
  starting-area row; T11 city flip; T13 M5 warning line and its player path
; T14 synthetic planet (the Map type entries and their fallbacks are allowed roots);
  T13 the Map type route's spawn; T18 (a) and (c), the notice's player path; V2 city crops.

### 3. `olde-world-atlantic` (part 3, order 0)

- **Introduces.** `geo_olde_world_v1` (smallest checkpoint at or above 99.1 percent from a refit at
  growth 1.25) and `geo_atlantic_v1` (first full or 2x fit, memory-bounded, same rule), each with its
  coarse land field; their presets, city lists and budget rows; `tn_elevation_olde_world_v1` and
  `tn_elevation_atlantic_v1`, each its map's Map type entry with its own map-qualified fallbacks.
- **Contract.** Atlantic's waterways get the cap minus its coast minus the headroom the plan reserves
  for later Tile work (FEAS-08). Each 1,000 tent terms saved frees about 8,200 Tile complexity, about
  240 waterway segments (est., REVIEW). No map's entry reads another map's name (A-21).
- **Gate.** T1 and T15 per map (each map's block at scales 6 and 1); T7 for their cities; T13 and T16
  on all three Map type entries (dump fields, locale, orders, the elevation-only route per map); V1
  contact sheets.

### 4. `waterways` (part 4, order 0)

- **Introduces.** `build_waterways.py`; the generated sets for scales 1 to 6 per map; curated rivers
  in APPROVALS 7's priority order inside the cap, written to `data-src/waterways/<map>.json` and bound
  to that list by T16 (rows leave only from the bottom, each through a design note, with Europe's
  22 as a floor; JI-03); straits open, with Gibraltar, Dover and the Great Belt in the two-way class;
  isthmuses closed; the canals key with dams (Kiel and Corinth on every map, Suez on Olde World and
  Atlantic, Panama on Atlantic; APPROVALS 6); turning basins; T1 corridor masks; the mechanism that
  keeps spawn, lake and starting ore on one bank where a river crosses a start area;
  rivers `max(7, k s)` wide by class and the fords, with the Earth gate `tn_on` and the
  `water-shallow` hook they need; the Map type notice names
  fords.
- **Contract.** Composition steps 5 and 6. Only the selected scale's set and the selected canal branch
  compile (S4: Tile 19,620 off and 20,161 on at scale 1). The `water-shallow` hook's outermost node is
  the gate, so default worlds stay identical (A-1, A-2).
- **Gate.** T5 per feature per scale 1 to 6, canals on and off, plus the no-dam control and the M3
  Cargo Ships placement probe, the fords (walkable bank to bank, waterway pieces place,
  ships pass) and the class widths; T3 strait and canal rows go live; T7 re-run for
  every city of every map, (d) included; T11 canals flip; T13 zero cost with the hook;
  T1 masks and the thin-water report; T15 per map; T15e river and canal-island paths with fords in
  place (PERF-09); V2 straits and river mouths.

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
  moisture and aux bias 2.2 times the bias; frequencies through `input_scale`); the tile hooks on the
  gate `tn_on` that `waterways` introduced: the 19 vanilla tiles beside AB with S3's bonus rule,
  marsh tiles (`water-mud` registered on Nauvis without AB, and the marsh key joining the
  `water-shallow` hook; the marsh region lifts moisture into the wet band through `tn_marsh_w` and
  lets `water-mud` win, APPROVALS 8), the adopted AB temperate tiles (APPROVALS 9); the AB palm
  switch; the transfer recalibrated with AB, under each map's elevation entry's next `_v<n>`, which
  takes over the Map type fields.
- **Contract.** Climate is firewall-clean (AB trees read it in the Entity program); a climate fit, if
  used, is its own coarse field, never the coast fit. M2 joins the gate here: its load, its zero-cost
  row (M2 default against BAB), the isolation check with AB and the M2t/BABt timing. TQ2 timed S9's
  composite at 1.59 to 1.66x AB alone at 8 LP and 1.20 to 1.23x at 24 LP; the bar now applies at 16
  LP, where TQ3 timed it at 1.249 and 1.213x, inside the bar. So
  this milestone re-times 16 LP and keeps the flip rule for Alien Biomes worlds (design notes 10:20; the cut
  order under Performance budgets) as a guard, for any map the build pushes over 1.5 there, until
  every map's M2t/BABt meets the plan's P2. The Map type route on M2 (AB's palms
  read the fine field through their key's default) is timed and reported. The palm switch
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
  per S6 A6E (`seed1` 7123; live probability times `tn_enemy_mult`, multiplier 4 inside each
  jittered disc, design note 6; active only beyond twice `starting_area_radius`), joined as
  `max(live, layer)`; offshore fields as a deep-water stamp in the composition (Tile) plus an Oil Rig
  wrapper term (Entity); random offshore oil masked by `tn_sea_v<n>`, whose offshore threshold on
  `tn_land_coarse` this milestone sets with a design note (FEAS-07).
- **Contract.** Wrappers are built in data-final-fixes around the live expressions. Every land reader
  here uses `tn_land_coarse`, never a waterway set or the fine coast. Hotspot amounts
  are judged on each disc's land part.
- **Gate.** T8, T9, T4 ore, enemy and offshore-oil rows (M3), T5 re-run (offshore stamps),
  T7 (a) re-run, T11 hotspots flip, T15 per map; T13 M3 and M5 rows; V4 at a hotspot; V2 offshore
  fields.

### 10. `destroyed-europe` (part 7, order 0)

- **Introduces.** The zone from the region layer's `tn_destroyed_depth` (S10), routed through
  climate: temperature above 100 inside, so AB's volcanic tiles and its volcanic tree follow (S3);
  zero inside the start radius; while on, random never picks a city inside the zone (folded pool
  switch; 8 of 41 Europe cities lie inside, APPROVALS 10); without AB the world equals "off", and the
  warning goes to the log at creation and to every created player.
- **Gate.** V3 at three seeds; T2; T3 membership; T11 zone flip; T13 the warning's player
  path; T15 with the zone on, on M2 (PERF-05).

### 11. `coast-band-fix` (part 7, order 1)

- **Introduces.** `scripts/bandfix.lua` and `bandfix_<map>_v<n>.lua`: one reference raster per map,
  which serves every scale and noise release, plus a dirty-chunk list per scale that is coupled to
  the geography release and keyed by `tn_geo` (S12: Europe 97.6 KB of raster and 1.1 to 11.0 KB
  of lists at scales 1 to 6; Olde World 526.7 KB and 6.2 to 48.8 KB). The handler also skips the
  waterway, lake and dam masks, which are coupled to the waterway release. The player-facing startup
  setting Exact coastlines (`terra-nauvis-exact-coast`, bool), whose tooltip names
  the maps it acts on.
- **Contract.** `on_chunk_generated` is registered only when the save carries the band-fix key. The
  key is a per-save name switch, baked like every other world value: a map's preset
  carries it only when Exact coastlines is on and that map passed all four checks, and
  absent means off, so adding the milestone never touches old saves and changing the setting never
  touches an existing save. The setting's `default_value` is true exactly when at least one map
  passed, so its default stays "on only where the four flip checks pass" until the maintainer rules on it
  after seeing the S13-bandfix renders with and without the fix. The handler acts on Nauvis only
  and is a pure function of chunk position, the chunk's generated tiles and the shipped data. It rewrites only
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
- **Acceptance**. Checks (a) to
  (d) run on Europe at scale 1 and on Olde World at scale 6, timed at 16 LP with 8 LP recorded, and
  on M2 for a map whose Alien Biomes geography `climate-tiles` moved to tents 4,096 (design notes
  10:20): (a) handler average at most 0.24 ms per generated chunk and no handler tick above 2 ms;
  (b) a clean loopback desync run, host at 24 LP and client at 8 LP (a determinism check across
  thread counts, not a timed threshold), with the `storage` diff; (c) dumped-tile T1 of 100 percent
  at scored pixel centres with max deviation at most 0.5 px; (d) the base's float32 replication
  predicts the game outside the band. They are measurement rows: the milestone passes when every check
  is measured and recorded and the setting acts on a map exactly when all four pass for that map. A
  failing measurement keeps that map without the fix and is not a halt. Atlantic, never
  priced (S12), never gets the key. The design notes report the outcome per map, for the decision on
  the default. A map the fix does not act on whose agreement stays under 0.990 falls under decision
  10.
- **Gate.** The four checks; T11 key flip through the setting; T16 setting default and tooltip; T5
  re-run; T12 (b).

### 12. `compat-completeness` (part 8, order 0)

- **Introduces.** T12 (same seed twice; loopback desync with host at 24 LP and client at 8 LP while
  exploring); T13 M0 to M6 with BAB and BL; T14; T17, which needs every vanilla autoplaced name on M2
  (restored in `trees-forests`); the D34 load test of the rest of the pack; M4t/BLt forced
  generation gated at 1.5 at 16 LP (8 LP recorded), exploring in real time against BL by the plan's
  P4 to P6, and a `scriptUpdate` bound against BL (the plan's P15; PERF-08 and
  12:35).

### 13. `extras` (part 9, order 0)

- **Introduces.** `scripts/markers.lua` (D28: rendering objects in chart mode or one-shot chart tags,
  placed at `world = geo - (tn_cx, tn_cy)` from the save's table version; no per-chunk event;
  the rendering-object route is tested headless whenever chart tags cannot be, TST-29); posters from
  dumped tiles or stitched previews, never a mapshot render (D30); size context in labels and preset
  descriptions (D3), with the footprint figures labelled as reported community examples (JI-12); the
  D36 rename dry run. No hand-out files: D6's exact zip reaches players as a GitHub release
  (`toolchain`'s `release.yml`). README.md is the release handoff's (plan
  reconciliation 8).

### 14. `release` (part 10, order 0)

- **Introduces.** Version 0.1.0; `tests/frozen.json`, kept complete since `europe-coast`,
  gets the release's last entries from `earth_test.py freeze`; packaging with `build_zip.py
  --release`; the tag step `build_zip.py --release --push-tag`, which part 10's `packageCommand` runs
  at handoff, once the release milestone's commit is on `main`, pushing only the tag
  `v0.1.0` and so starting `release.yml`; TESTING.md from the milestones' smoke sections; the release
  suite (`earth_test.py suite release`) with V1 to V5; the security review runs first.
  From this release on the versioning policy applies to released bodies in full. Kickoff needs the
  recorded human smoke pass on the parent issue and every other sub-issue closed.

## Conflicts and open items

Items 1 to 9 are settled; each keeps its record. Items 10 to 21 are open.

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
   `tn_land_coarse`, serves the start mask, the land-aware hotspot and enemy terms and the sea mask.
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
    interval; with AB it takes 1.59 to 1.66x AB alone at 8 LP, over 1.5, and 1.20 to 1.23x at 24
    LP. Since design notes 12:35 the rule applies at 16 LP, where TQ3 timed the same composite at
    1.045 and 1.048x vanilla and 1.249 and 1.213x AB alone, inside it. The
    starting values are in the plan's section 6. Open until the build measures them: whether the
    shipped program stays under the rule at 16 LP as features land (the `climate-tiles` flip rule
    stays as the guard), and what `europe-coast`'s traces of the first-column hitch and the
    start-area save excess find.
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
    scale 6; Atlantic has no priced fit (S12) and no measurement, so Exact coastlines never acts on
    it. The setting's default awaits the decision after the S13-bandfix renders
    (the design notes).
18. **The Map type route.** A Map type entry picked alone follows the startup
    settings at every load and compiles the fine field in the Entity program through vanilla's
    starting-ore mask and, with AB, AB's palms (section "Map type entries"); its cost is
    unmeasured until `europe-coast` times it, and it is reported, never gated. The S13 probe never
    gave two maps different per-save values, so the map-qualified rule is derived, and
    `olde-world-atlantic`'s per-map elevation-only checks are its first proof.
19. **The 16 LP proxy.** TQ3 timed the planning composite at 16 LP, the eight
    P-cores with hyperthreading, so P1 and P2 start from its ratios; `europe-coast`
    records the build's first. Whether 0xFFFF on the reference machine matches a typical player's PC is the maintainer's
    judgement, not a measurement (TQ3 marks a real 16-thread CPU UNVERIFIED).
20. **Fords in game.** R4 shows by collision masks that waterway pieces need only
    `water_tile` and that characters and biters walk `water-shallow`; engine behaviour is UNVERIFIED
    until `waterways` places pieces across a ford and floods walkability through it.
21. **River class (APPROVALS 7).** Major is the longest third of each map's adopted list, or an S4
    path over 1,000 map-km (path length times 2.471 km per reference px, the only river length any
    report gives), so a river's class can differ between maps.

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
| S13 | the new-game screen test, design notes 12:35: probe mod `spikes/S13-gui/mods/terra-nauvis-probe` (`data.lua` Map type entries, `data-final-fixes.lua` fallbacks and preset order, `control.lua` the `[TN-PROBE]` dump), `spikes/S13-gui/mgs-maptype-europe.json`, screenshots the design notes to `06`; S13-bandfix (`spikes/S13-bandfix/README.md`, renders the design notes, the coast with Exact coastlines off and on, untimed) is the spike the decision on the setting's default waits on |
| Decisions, finding ids | the design notes (findings such as TST-08) |
| TQ1b | the design notes |
| TQ2 | the design notes (Phase 4, group `b20261027-0821`); its consequences in the design notes 10:20 |
| TQ3 | the design notes (forced generation at 16 LP, group `b20261027-1223`); the design notes 13:20 |
| R3, R4, R5, R6, R8 | the design notes, `R4-cargo-ships.md`, `R5-mod-sweep.md`, `R6-noise-capabilities.md`, `R8-perf-footprint.md` |
| test notes, APPROVALS | the design notes |
| Vanilla | `%FACTORIO_GAME%\data\core\prototypes\noise-programs.lua:270-274`, `noise-functions.lua:211-219`; the `[noise-expression]` Map type labels `%FACTORIO_GAME%\data\core\locale\en\core.cfg:5256-5268`; preset orders `%FACTORIO_GAME%\data\base\prototypes\map-gen-presets.lua` (Default "a", Rich resources "b") |
