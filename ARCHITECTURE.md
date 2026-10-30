# Architecture

Binding design for Terra Nauvis (mod ID `terra-nauvis`) in the first release: Factorio 2.1, written against
2.1.23 (build 87750) and tested on 2.1.24 (build 87808) since Steam's 2026-10-29 update (G8;
design notes 2026-10-29 09:00), base game, Alien Biomes 0.8.0 optional. The disagreements with the earlier design notes found while writing this file are listed in
"Conflicts and open items". This file is living: during a build it changes only through fit-review
patches folded in at a milestone commit, and whenever a milestone changes a binding contract (Universal
Definition of Done).

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
  thresholds parsed from the plan's threshold table, the workspace lock around every
  command that launches the game. It runs the game only through the workspace's `fh.py`, isolated
  from `%APPDATA%\Factorio`; fh.py isolation (G1) is the only live-profile protection (the maintainer,
  2026-10-27 23:47). GitHub Actions never runs the game: `ci.yml` runs the static
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
| `terra-nauvis/data-final-fixes.lua` | Everything that reads other mods' final state: entity wrappers (ores, enemies, offshore oil), gated hooks on shared prototypes (the `water-shallow` hook for fords and marshes; vanilla tiles, trees, rocks and decoratives beside AB; marsh tiles and `grass-1` between the marsh pools without AB; forest boost; AB palm switch; the Earth-gated ridge exclusion on ore probability) | hooks follow the stable-hook rule (Expression graph) | 4 (fords), 6 |
| `terra-nauvis/control.lua` | Event wiring only | registers exactly the events in "Control stage" | 0 |
| `terra-nauvis/locale/en/terra-nauvis.cfg` | Setting names and descriptions; `[string-mod-setting] <setting>-<value>=<label>` for every dropdown value, with world size; preset names and descriptions; the `[noise-expression]` Map type names "Terra Nauvis: <map>"; messages, the Map type notice among them | every used key exists; no line without `=` (a missing `=` fails the load, S11) | 0; Map type names 1 and 3 |
| `terra-nauvis/changelog.txt`, `LICENSE`, `SOURCE-OFFER.txt`, `thumbnail.png` | Factorio changelog, GPLv3 (EarthMaps data reuse), the written source offer (GPLv3 section 6: the zip tells a recipient how to get the mod, `tools/` and `data-src/` from the author), thumbnail (later) | `tools/build_zip.py` ships every file of the folder and refuses anything but Lua, JSON, cfg, txt, png, md and LICENSE | 0, 13 |
| `terra-nauvis/prototypes/config.lua` | The single source of names and constants (table below) | pure data: reads no `data`, `settings`, `game` or `script` and calls no function, so the settings, data and control stages and the Python tools (through `tools/tnconfig.py`, a luaparser loader of that subset) read one file; `europe-coast` retired the placeholder group with every name it marked | 0 |
| `terra-nauvis/prototypes/presets.lua` | The three presets from config, `settings.startup` and `mods`, ordered right after Default; the prototype-level fallbacks the Map type entries read, built from the same table | the redirect table under "Expression graph"; AB keys only with AB loaded, except the four palm keys, which every preset bakes (their copies are defined on every load, so a world that gains AB later meets the palm switch too; design notes 2026-10-29 18:40), Oil Rig keys only with the Oil Rig; each fallback equals what its geography version's preset bakes, for every version (section "Map type entries"); a preset's geography (its elevation entry, coarse field and `tn_geo`) is chosen in one place, `geography()`, so `climate-tiles` can give Alien Biomes worlds a cheaper one; `toolchain`'s placeholder preset, withheld beside Alien Biomes, retired with `europe-coast` | 0 (placeholder), 1 |
| `terra-nauvis/prototypes/expressions/coast.lua` | Coordinate chain, coast transfer, lattice detail, far-field box, elevation composition, emitted for every geography version of each map as that version's elevation entry over its own chain (`tn_<x>_<map>_v<n>`), older versions unchanged; the map's coarse land field, which the preset key `tn_land_coarse` names. `toolchain`'s placeholder shape retired with `europe-coast` | the firewall names: Tile only; `tn_land_coarse` is the one land field outside Tile; the newest entry of each map carries the Map type fields | 0 (placeholder), 1 |
| `terra-nauvis/prototypes/expressions/spawn.lua` | City fold, random pick, spawn offsets, spawn lake, inland lakes, `distance`, every start mask version from its formula (`tn_start_mask_v1` on the coarse field lands first) | each map's city offset names (Europe's v1 chain reads `tn_cx_europe_v1` and `tn_cy_europe_v1`, constants that never move; a city spawn reaches a later entry through names of its own) and the city index readable at (0, 0) | 1 (start mask), 2 |
| `terra-nauvis/prototypes/expressions/climate.lua` | Temperature, moisture and aux (AB and fallback variants), vanilla-scale temperature, slider hooks, marsh and destroyed-zone lifts | firewall-clean: Entity reads it through AB trees | 6 |
| `terra-nauvis/prototypes/expressions/regions.lua` | Region layer, S10 design (d): table rows, the shared warp, per-region outputs and layer aggregates (section "Region layer") | consumers read only the interface names; no region formula anywhere else (S10); the static `regions` row fails any read of config.lua's `regions` group outside this file but a full dotted path to an interface name | 5 |
| `terra-nauvis/prototypes/expressions/tiles.lua` | Bodies behind the tile hooks: vanilla tiles beside AB, marsh tiles | | 6 |
| `terra-nauvis/prototypes/expressions/trees.lua` | The great-forests gate and multiplier key at their off values and the boost formula (`M.boost`, which data-final-fixes and the palms' second versions share); the vanilla-scale temperature; the restored vanilla trees', rocks', decals' and decoratives' keys and Earth bodies from `tables/vanilla.lua`; the AB palm switch | the bodies read the base game's shared tree and rock helpers by name | 6, 7 |
| `terra-nauvis/prototypes/expressions/resources.lua` | Ore wrappers (richness ramp, hotspots), offshore-oil wrapper, offshore field stamps | | 9 |
| `terra-nauvis/prototypes/expressions/enemies.lua` | Enemy-layer wrapper | | 9 |
| `terra-nauvis/prototypes/expressions/ridges.lua` | `cliff_elevation` and `cliffiness` from the ranges table: per map the squared crest distance (`tn_crest_<map>_v<n>`), the openings (`tn_openings_<map>_v<n>`) and the Entity-side crest band (`tn_band_<map>_v<n>`); the shared effective crest distance, ridge-free start disc, cliff properties and ore clearance; the toggle's neutral pair `tn_one` and `tn_zero` unless waterways defined them first | slider-proof, contour units (S5); the per-map bodies read only their map's chain and the scale (firewall-clean); the toggle never multiplies (U5) | 8 |
| `terra-nauvis/prototypes/expressions/destroyed.lua` | Destroyed-zone consumers: temperature lift, start mask, random-pool switch | | 10 |
| `terra-nauvis/prototypes/expressions/waterways.lua` | Loads the generated waterway sets per map and scale (locals X and Y bound to the geo tiles of the geography version that composes them, its `waterways` record), the hook gate `tn_on` and ford key `tn_fords` prototypes, the canals switch's neutral bodies, and the entry composition `coast.lua` wraps around the rest of that version's composition | the sets reach Tile only (firewall names); the ford set through the `water-shallow` hook alone | 4 |
| `terra-nauvis/prototypes/generated/` | `geo_<map>_v<n>.lua`, `land_coarse_<map>_v<n>.lua`, `waterways_<map>_s<k>_v<n>.lua` (with the ford sets), `bandfix_<map>_v<n>.lua` | machine-written; the header records tool version and input sha256; name-free data (the tents read the locals `U` and `V`, which `coast.lua` binds to the map's chain), every line within 120 columns through Lua 5.2's backslash-z continuation; never hand-edited; one file per released version | 1, 3, 4, 11 |
| `terra-nauvis/prototypes/tables/` | `cities`, `hotspots`, `ranges`, `canals`, `regions` (the forest and marsh rows among them), `destroyed`: approval data in degrees, with sources; hotspot rows take the adopted centre (`lat`, `lon` in `approvals-data.json`), which decision 16 moved inland for one hotspot | versioned by release (copy-on-write after a release) | per milestone |
| `terra-nauvis/scripts/start.lua` | `on_init`: world detection, storage, D29 message, cliff "none" reset, D12 and D32 warnings stored through `guards.record_warning` for the per-player path (section "Guards", stored records) | | 2, 8 |
| `terra-nauvis/scripts/guards.lua` | Missing-name guard, drift line, the Map type notice, D33 surface guard, per-player notice, RSO and Destroyed Europe warnings (`on_player_created`); `record_warning`, the one writer of the stored warnings, and the validated readers of every stored record | owns `storage.earth.warnings`, `storage.earth.sent` and `storage.map_type.sent` (T16 storage row) | 1, 2 |
| `terra-nauvis/scripts/markers.lua` | D28 city markers | no per-chunk event | 13 |
| `terra-nauvis/scripts/bandfix.lua` | Tolerance-band coast fix | the only per-chunk handler | 11 |
| `tools/earth_test.py` | Runner: `gate --through <milestone-id>` (each milestone's testCommand, under 10 minutes; `--cold` ignores the FG cache to time the cold gate; the FG rows of every milestone up to `<milestone-id>`, and the suite evidence of every milestone the gate lands, `<milestone-id>` with each earlier milestone of its group that no reference ref has landed (`gate_evidence_slices` over `pending_slices`), each held to its own manifest, never a landed milestone's, with the live sample drawn over all their checks and a deterministic one compared exactly with its re-derived evidence; design notes 2026-10-29 11:05), `suite <milestone-id>` (full variants into the content-hash cache; `--only <check>`), `install-check`, `baseline`, `freeze` and `static` commands (`suite` and `freeze` write the milestone's frozen snapshot into its suite manifest; the frozen row holds the registry to the earlier milestones' snapshots and the offline bodies of `tools/tnlua.py` to the game's dump); the milestone registry (FG rows, SS checks, live-sample pools, oracle properties and the dumps the frozen row reads, per milestone: one module-level literal, which `tnfrozen.runner_registry` reads for CI and the release build, and the only source of the dump labels a `tests/frozen.json` record may name) | finds fh.py through `FACTORIO_WS` (default `%FACTORIO_WS%`) and refuses to run a game-launching command without it; `static` launches nothing and needs neither, so CI runs it; validates every milestone id (`SLICE_ID` and the registry) before it builds any path and keeps each output directory inside its output root; never writes tracked files while gating, and writes state and tracked files atomically (temp file plus replace); trusts no verdict file, only cache entries whose key it recomputes, each key covering what its check measures (the M0 timing rows: vanilla program signatures, the driver mods, the timing machinery, fh.py, the build and the record format); re-derives suite evidence from raw outputs alone: each timed repetition's validity from its run directory, the affinity watcher's records and the persisted monitor reads (never the runner's `reps.jsonl` verdicts, only cross-checked), the walker's affinity the same way, the server saves' sizes from the files, and the game self-test by replaying a copy of its stored runs (`game_selftest.py --replay`, which launches nothing); parses every cell of the plan's section 6 (6.2 limits bound by program, modset and map; 6.3 allocations per modset and map, "every other milestone" included) and fails closed on one it cannot read; a 6.2 From cell naming no milestone (P3) is in force from the first milestone, and a row in force that no check of the runner consumes (`LIMIT_CONSUMERS`) fails the section6 row; rule 5's extra group of 7 reps per config for a timed ratio within 0.03 of a limit, decided pooled (in the gate only when it fits the budget, else it fails closed naming the ratio); the workspace lock around every command that launches the game, every game launch while the command holds it, and G1 on every run, a run that may have left its instance stopping the command (`tnguard.run_breach`); fh.py isolation is the only live-profile protection, so no guard snapshot or check brackets a command (G9 retired, design notes 2026-10-28) | 0 |
| `tools/build_spawn.py` | Spawn bearings emitter (`spawn-cities`): `emit` writes the bearings file the newest geography version's spawn record names (`prototypes/generated/spawn_<map>_v<n>.lua`: per city and scale, from the land component holding the city in the reference land raster, the spawn lake's bearing, and the starting-ore bias bearing, width and on flag chosen by the share of starting patches left off that land over a fixed draw of random spot-noise candidate layouts, scored with the start mask as the game evaluates it from the coarse checkpoint) from the raster, the city table and the map's coarse checkpoint; `check` (the gate's `sc_dump_facts`) re-emits twice and compares byte for byte with the committed file | name-free data; numpy imported by the gate's rows only, never by `static` | 2 |
| `tools/build_geo.py` | Tents emitter and fitter: `emit`, `check` (two emissions byte-identical to the committed files), `refit-islands` (the recorded T1-e local refit), `offline` (T1 of the checkpoints), `fit` (S1-fit's fitter, ported operation for operation, resumable from a work folder outside the repo), `curve` (t1_metrics' T1 of the fit's checkpoints) and `adopt` (the shipped checkpoints and the curve into `data-src/fits/<map>/`, with `fit.json`) | reproducible emission (Build-time data flow); a fit resumes after its newest completed growth step and reproduces an uninterrupted run; numpy imported by the gate's `geo_emit` row only, never by `static` | 1, 3 |
| `data-src/fits/<map>/` | The map's fit checkpoints (`model-*.npz`), `fit.json` (which checkpoint each body uses), the emission `manifest.json` and `curve.json`, with a `PROVENANCE.md` the T16 data-src row re-hashes | read-only tool input; a refit is a recorded tool run | 1 (Europe), 3 |
| `tools/build_waterways.py` | Waterway import (S4's paths; straits re-routed through R7b's narrowest points, canals along R7b's routes), per-scale smoothing (rivers) and simplification, widths by class, fords, turning basins, the plan's cut order as data, T1 corridor masks, river-safe starts; `import`, `emit`, `check`, `rivers`, `mask`, `offline`, `cuts` | reproducible emission: the same inputs give byte-identical Lua and manifests; numpy imported by the gate's `ww_emit` row only; the manifests carry every shipped polyline, ford, basin, cut and start | 4 |
| `tools/build_regions.py` | The region table's writer (`emit`, `check`, `list`) from `approvals-data.json` and R7b by S10's tuned rules, and the region geometry the oracle and the runner share (the frame, each map's whole-pixel offset, nominal signed distances, drift bounds) | the committed table equals a fresh emission byte for byte (the static `regions` row); pure Python, no numpy at import (CI's static run imports it) | 5 |
| `tools/build_ranges.py` | The ranges table's writer (`emit`, `check`, `list`) from `approvals-data.json` and R7b: the 16 ranges' crest polylines, the adopted passes at approvals' `arc_km`, the 400 km unnamed gaps (the rule's count per pass-free stretch, each at the middle of the longest straight piece of crest in its window), the map-edge openings (APPROVALS 5) and the segments each map's ridge reads; `table_findings` (the static `ranges` row) | the committed table equals a fresh emission byte for byte, its passes are approvals' adopted ones, its gaps the rule's, and no pass-free stretch exceeds 400 km on the whole crest or on any map; pure Python, no numpy at import | 8 |
| `tools/build_zip.py` | Packaging; `--release`; `--check-tag <tag>` (release.yml's tag check: the tag is `v` plus info.json's version, names the checked-out commit and sits on origin/main); `--out-dir <folder>` (a folder outside the checkout is a landing); `--release --push-tag` (the release tag step, which the `release` milestone adds: not in the tool yet, and the landed-tag check stands in for its origin/main rule until then) | byte-reproducible zip (stored entries, fixed timestamps and attributes, sorted), the same on this machine and on GitHub's `windows-latest` runner; `--release` refuses while config.lua marks a placeholder name, refuses a `tests/frozen.json` record that breaks the `tnfrozen` contract (a dump label the runner's milestone registry does not assign among them, the registry read from the runner's source), refuses any unregistered Earth body: every noise name config.lua defines, released bodies and firewall bodies alike, missing from tests/frozen.json, the Map type fallbacks excepted (design constraint 2), which every milestone from `europe-coast` on keeps complete, so from then it works at any point of the release; and refuses a moved body: every Earth body the mod's code builds offline (`tools/tnlua.py`) must equal its record, every registered name must still be built, every record of a milestone's frozen snapshot must stand, and nothing an earlier release tag fixes may move (the T16 append-only rule); the gate's frozen row checks the dumped bodies themselves and holds the offline reading to them; a landing (a zip built outside the checkout, such as into the live mods folder) gets the release's body and snapshot checks, refuses to change or drop a body of a zip of this mod already in the folder (read offline from that zip) or a record its build record's snapshot holds, reads nothing else there, and writes its bodies and snapshot into its own build record; `--push-tag` (from `release`) pushes only the tag `v<version>` on `origin/main`'s head when it carries the release trailer | 0; tag step 14 |
| `.github/workflows/ci.yml` | On every push and pull request: `earth_test.py static` and `build_zip.py`, the zip uploaded as an artifact | no game, no fh.py, no `FACTORIO_WS`; `contents: read`; actions pinned to full commit SHAs | 0 |
| `.github/workflows/release.yml` | On a pushed tag `v*`, from a full-history checkout: checks the tag against `info.json`, the checked-out commit and origin/main (a tag whose commit main's history does not hold is refused, since the release does not wait on CI), runs `build_zip.py --release` (the offline body check, the milestones' snapshots and the earlier release tags), publishes the GitHub release with the zip and its `.sha256` | the workflow's own `GITHUB_TOKEN` with `contents: write` and the preinstalled `gh`, no other secret; no game | 0 |
| `tools/t1_metrics.py`, `oracle.py`, `dump_render.py`, `contact_sheet.py`, `nav.py`, `earthgeo.py`, `earthmaps_decode.py`, `game_selftest.py` | S8's tools with their self-tests, ported from `spikes/S8-tooling` in an earlier prototype; `earthgeo.py` holds the pixel conventions and reads them from config.lua; `oracle.py extend` and `validate` build and check `tests/oracle/<map>.json`; the game self-test uses content-hashed `ea-s8-*` modsets, and `game_selftest.py --replay` re-derives its 31 verdicts from a finished run's stored outputs (every game command answered from its own `run.json`, nothing launched) | conventions equal config.lua's; rasters from `data-src/`, the oracle from `tests/oracle/`, the workspace from `FACTORIO_WS` | 0 |
| `tools/tnconfig.py` | The luaparser loader of config.lua (local assignments, table constructors, literals, `..` and arithmetic; anything else fails closed) and the schema accessors of its groups (`firewall_names`, `geography_versions` and `geography` (every version per map, and each map's newest), `fallbacks` (every version's, per map), `start_masks`, `baked_names` (what a version's preset bakes, the mirror of `presets.lua`), `release_registry`, `toggles`, `placeholder_names`, `noise_names`, `unregistered_names`, `schema_problems`, `defined_names`), plus the region layer's names (`region_names`, `region_row_name`, `region_query_names`), composed from config.lua's stems and suffix and the ids of the region table beside the loaded config.lua exactly as `regions.lua` composes them | the one way Python reads Earth names and constants; an accessor raises on a wrong shape and never reads one as empty; `noise_names` holds every region body, released through the `release_registry` row that lists the region table under `files`, so the dump facts, the T16 rows and `build_zip.py --release` read one naming rule; `schema_problems` also reconciles the stores of Earth body names: every firewall body but the placeholder's sits in a `release_registry` row, a regions group's table is listed by one, and every noise name carries the noise prefix | 0 |
| `tools/tnguard.py` | G1's fail-fast check, shared by the repo tools that launch the game through fh.py (`run_breach`: a run whose RESULT line or `run.json` shows it may have left its instance stops every further game run of its command; design constraint 1), and their path helpers (`absolute_output`, the workspace and the runner's evidence tree) | refuses no output path: copying the built zip into the live mods folder is allowed, and the write guards, the guard-bracket token and the option declarations it held are retired; launches nothing | 0 |
| `tools/tnfrozen.py` | The `tests/frozen.json` contract every reader and writer of the registry shares (the gate's frozen row and `freeze`, the T16 frozen and append-only rows, `build_zip.py --release`): the file keys, the record `{type, sha256, dump, milestone, registered}`, the hash's field list, the runner's milestone registry read statically (`runner_registry`), record and file validation, and whole-record comparison (`record_changes`) | a record's dump label must be one the runner's registry assigns and the record's milestone could have produced, never skipped when it is not; `runner_registry` reads earth_test.py's one module-level `REGISTRY` literal and fails closed when the runner assigns it otherwise or names it in other code that runs at import, and the gate's frozen row checks that reading against the live registry; the shared body hash (`body_hash`) and Earth-body selection, the offline bodies (`offline_bodies`, through `tools/tnlua.py`) held to their records (`body_problems`), and the snapshots a group's earlier milestones and a landed zip's build record keep (`snapshot`, `snapshot_problems`, `suite_snapshots`, `unsnapshotted_problems`: a record a snapshot holds never changes or leaves the registry, and a snapshot whose sha256 does not cover its bodies fails closed); launches nothing | 1 |
| `tools/tnlua.py` | The mod's settings and data stages run offline: a Lua 5.2 subset interpreter over luaparser's tree, with stubs for `data` (`data.raw` with vanilla's default `map-gen-presets` only, and `data:extend`), `settings.startup` (the settings stage's defaults) and `mods` (`base`), reading the mod from a folder or a zip | numbers are doubles and print as Lua 5.2 does (`%.14g`); `string.format`, `table`, `math` and the globals the mod uses; fails closed on any construct or call outside the subset, a require outside the mod, a text built from an address and a sort tie between distinct values; the gate's frozen row holds its bodies equal to the game's M1 dump on every run (34 of 34 at its introduction) | 1 |
| `tools/tn_static.py` | T16's static rows and their run-time fixture controls (lint, info.json, locale, dashes, registration, the stored-records contract, names, design rules, workflow scan, attribution scan, data-src hashes, frozen and budgets shape, the offline bodies row, the append-only row against main, origin/main, a pull request's base, every release tag and the earlier milestones' frozen snapshots, fallbacks, zip) | no game, no fh.py, no FACTORIO_WS; reads git refs only for the append-only references; needs only luaparser and the linter; the bodies row runs the mod's settings and data stages offline (`tools/tnlua.py`) and holds every body built there to its record, so CI fails a registered body changed in place through its code; the mod scans read `build_zip.py`'s own file classification (shipped and refused files), so no file in the mod folder escapes them; the registration scan is an allowlist over every use of `script`, `defines.events`, `require` and indirect global access; the name scan reads string literals and identifiers (dot-index fields, table-constructor keys, method names) of every mod Lua file and of `tools/mods/` (its Lua and `info.json` files too); the frozen row requires every noise name config.lua defines, but the placeholder's and the fallbacks, to be registered, and every record to hold the `tnfrozen` contract against the runner's milestone registry, read statically from `earth_test.py`; the attribution scan reads every file of its trees (dot and build folders included); no row scans `tools/` or `tests/` for game launches, live-profile paths or copies into a mods folder (the launch scan and the output-options row are retired, design notes 2026-10-28; the workflow scan still keeps both workflows off the game) | 0 |
| `tools/mods/` | Test-only mods, never shipped: `ea-region-probe` (region-layer: named expressions read with calculate_tile_properties at points and on grids in geo tiles, no chunk generated, the spawn offset read in the game), S8's `ep-s8-dump`, `ep-s8-probe`, `ep-s8-disc-world`; TQ1's timer `tq1-gen` (block from a runtime-global setting); TQ2's driver `tq2-driver` (forced, explore, walk, rtexplore and save jobs); `ea-coast-twin` (isolation (a)'s constant-coast twin, named at run time by the runner; also the detail-off build of T3), `ea-drop-name` (the missing-name guard's test build: the names the runner gives it dropped, with every preset key that names them), `ea-leak-fixture` (the isolation checks' positive controls: a test-only preset carrying the first Earth preset's keys without the start mask, and one carrying all of them plus an entity and a decorative autoplace key redirected to fixture bodies that read the fine field; values that are numbers stay numbers) and `ea-heavy-probe` (PERF-15) | they get any Earth name from the runner at run time, so a rename stays a config edit (the T16 name scan reads them) | 0 |
| `tools/affinity_watch.ps1` | TQ1b's affinity watcher, `-Mask` 0xFFFF (the 16 LP proxy, its default) or 0xFF (the 8 LP diagnostic) | with `tools/perf.py`, the only script that names the game's process image, and it never launches one | 0 |
| `tools/perf.py` | T15 timing: TQ1b block, 16 LP affinity (0xFFFF, the weaker-machine proxy) with 8 LP (0xFF) recorded as a diagnostic, quiet-window protocol, census check (a wholly suspended game process is parked, not running); the kill-on-close job object every fh.py launch runs in; the parsers (force time, `--verbose` complexity, `--benchmark-verbose all`, real-time intervals) | the one process-inspection module: it lists, watches and pins game processes fh.py started, and never launches one | 0 |
| `tools/lint/` | luacheck 1.2.0 installed per user under `%FACTORIO_WS%\downloads\luacheck-1.2.0\` (`manifest.json` records version, source and sha256; `luacheckrc.lua` declares each stage's globals; `fetch_linter.py` installs it in CI), luaparser 4.2.0 as the syntax floor (`requirements.txt`), and the warnings allow-list | the linter's checked-file count equals the zip's Lua file count | 0 |
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
| Maps | key (`europe`, `atlantic`, `olde_world`; settings say `old-world`, APPROVALS 1a), preset name, display name, raster size, `wr` and `hr`, georeference, world size per scale | `maps = {<key> = {key, id, setting_key, display, width_px, height_px, wr, hr, lon_left_edge, lat_top_edge}}`, `map_order = {<keys>}`; `id` is the map's `tn_map` value, a positive integer unique across maps that saves hold, so it never changes (tnconfig's id-space check; the T16 append-only row); the plan's tables name maps by `display` |
| Scales | 1 to 6, default 6; the coordinate-chain constant `floor(s / 2)` | `scales = {values = {...}, default}` |
| Settings and presets | each setting's name, type, default and values; each preset's name, map, order and the mods whose presence withholds it (Alien Biomes until `climate-tiles`) | `settings = {<key> = {...}}` with `setting_order`; `presets = {<key> = {name, map, order, withheld_with = {<mod names>}}}` with `preset_order` |
| Toggles | setting name, preset key, default, mechanism (name switch or hook gate), on and off values; Exact coastlines with the maps it may act on | `toggles = {<key> = {setting = <settings key>, preset_key, default, mechanism = "name switch" or "hook gate", on, off, maps}}` with `toggle_order` |
| Keys | every `property_expression_names` key any Earth preset sets, for every geography version (the missing-name guard, T14 and the D33 Nauvis-only guard, which strips exactly these from other planets' surfaces, so tnconfig fails a key a version's preset bakes that the list lacks) | `preset_keys = {<keys>}`; the Map type fallbacks live in each geography version (row Geography); a top-level `fallbacks` group is retired and fails the schema check |
| Firewall | per map, the fine field: the map's elevation entry and every term only it reads (design constraint 3; the isolation checks and the constant-coast twin read it) | `firewall = {<map key> = {<noise names>}}`; in `toolchain` the placeholder's `firewall = {<keys of placeholder.names>}` (its elevation) supplies it, and an empty field fails every isolation check |
| Placeholder (retired) | `toolchain`'s placeholder preset; `europe-coast` removed the group, its names and every placeholder text, and the tools read its absence as empty | `placeholder = {preset, map, scale, spawn_px, shore_tiles, sea_floor, start_mask_floor, start_mask_span, names = {<key> = <noise name>}, keys = {<keys of names>}, firewall = {<keys>}, withheld_with = {<mod names>}}`; `withheld_with` lists the mods whose presence withholds the placeholder preset (`alien-biomes`) |
| Keys | the per-save keys every Earth preset bakes: map, scale, geography release, the coarse-field key, and the vanilla properties the presets redirect | `keys = {map, scale, geo, land_coarse, elevation, start_mask}` |
| Geography | per map: the Map type order, and every version of the map's elevation entry, oldest first and the newest last. A version is what one geography release points a preset at: its geography id (`tn_geo`, in the one id space across maps and versions of versioning rule 4), its entry, the bodies only that entry reads, its coarse field, its chain with city offset names of its own and the offset its preset bakes there (integers, or names of the expressions that fold it), the start mask version its preset names, the generated file each fit body binds (name-free data, so a later version binds the same files to its own chain), and the Map type fallbacks its entry reads, each valued as that version's preset bakes it; from `spawn-cities` a version may hold a spawn record (its map's spawn-city setting and per-save city number, the resolved index control reads at (0, 0), the spawn lake and starting-ore bias the start mask reads, its own inland lakes, the start land guarantee, the `distance` body and the generated spawn bearings), and then its city offset names name the city fold. The preset names the newest version, whose entry alone carries the Map type fields; older versions stay defined, unchanged; `presets.lua` picks a preset's version here | `geography = {<map key> = {map_type_order, versions = {{geo_id, entry, geo, land_coarse, detail, far, gx, gy, u, v, cx, cy, city_offset, start_mask, fits = {geo, land_coarse}, fallbacks = {{name, map_qualified, frozen}, ...}, spawn = {city_setting, city, city_index, spawn_lake, spawn_bias, inland_lakes, start_land, distance, bearings} (optional)}, ...}}}`; no two versions of a map share a noise name of their own (its chain, entry, fit, detail and box names and its inland lakes, which read its chain; a later version never re-points an older one's), while the spawn bodies that read no chain (the city fold, the spawn lake and bias, the guarantee, `distance`) may serve several versions, as a start mask version does; each `geo_id` is unique across every version of every map and has its release-registry row under the same map, each version's entry, coast, detail and box, and with a spawn record its inland lakes and the guarantee, are in its map's firewall while the spawn lake, bias, fold and `distance` are not, a spawn record's city number is a fallback that mirrors its setting and its version's city offset values name the fold, its start mask is a `start_mask` version and its fits and spawn bearings are release-registry files; a fallback name listed by two versions or maps carries the same flags; `tnconfig.geography` returns each map's newest version with `map_type_order`, `entry_versions` (every version's entry, oldest first) and its spawn record's fields copied to the top level, for the readers that want the preset's version |
| Messages | control code's locale section and keys (the notice and its withheld-preset variant, the drift lines, the missing-name line, the withheld-preset warning; from `spawn-cities` the start message, the RSO warning and the city drift line); a stored warning names its key here, so a key saves can hold is never removed or renamed (section "Guards", stored records; the T16 append-only row) | `messages = {section, keys = {notice, notice_withheld, drift_scale, drift_follows, drift_update, missing_name, withheld_beside, start, rso, drift_city}}`, each key a distinct locale key |
| Water slider | vanilla's readers of the water slider, which every Earth preset bakes at their default-slider values (D15) | `water_slider = {{key = <vanilla noise name>, value = <number>}, ...}`, each key also in `preset_keys` |
| Spawn | from `spawn-cities`: the numbers every spawn body is built from (the names are each geography version's own, in its spawn record): the random fold's constants (S7's hash), the spawn lake, the starting-ore bias, the start land guarantee and the inland lakes' spot-noise constants | `spawn = {random_value, hash = {small_mult, high_mult, high_div}, lake = {distance, bearings, magnitude, offset, divisor, noise}, bias = {radius, excluder, widths, seed, layouts, ores, candidates, region, spacing, patch, share, margin}, land = {radius, slope}, inland_lakes = {seed1, region, per_region, radius, level, gain, candidates, spacing, cone_divisor, shore, coast_px, coast_gain, start_radii, start_slope}}`; `keys` gains `distance`, `spawn_lake` and `spawn_bias` |
| Release registry | per geography release: the release, the map and its `tn_geo` id, every released name, the generated files it loads; a row that lists the region table under `files` also releases every name `regions.lua` composes from it; how control code and the tools resolve a save's `tn_geo` to its map (versioning rule 4) | `release_registry = {{release = <version>, map = <map key>, geography = <tn_geo id>, names = {<noise names>}, files = {<generated files>}}, ...}`; `map` and `geography` come together, and a geography id appears in one row only |
| Ridges | the ridge bodies' numbers (flank and ramp in contour units, cliffiness, the openings' gap along the crest and reach across it, the edge band, the ridge-free start disc, the ore clearance, the band's angle, the switch threshold, the cliff reset's size) and names (the shared bodies, each map's crest, openings and band), and the Earth ores the clearance wraps (milestone ridges) | `ridges = {flank_tiles, ramp_tiles, contour = {low, high}, cliffiness, pass_tiles, reach_tiles, tip_tiles, edge_tiles, edge_reach_tiles, start = {radius_tiles, margin_tiles}, ore_clear_tiles, band_max_angle_degrees, centre_tiles, switch_threshold, reset_size, max_arguments, names = {d2, free, cliff_elevation, cliffiness, clear, crest = {<map>}, openings = {<map>}, band = {<map>}}, ores = {{resource, key, name}, ...}}` (the water frequency slider's two vanilla readers stay group 0's `water_slider` constants; T4); `neutral = {one, zero}` |
| Regions | the region layer (milestone region-layer): the frame map, km per px, the warp, roughness, ramp, jitter and octave shift, the forest boost, and the names: the aggregates and the layer's own fixed names in full (also a geography-free `release_registry` row, which lists the region table under `files`), the row name stems that each row id and the version suffix complete | `regions = {frame, frame_tolerance_px, km_per_px, warp, rough, ramp, share_hundredths, octave_shift_px, max_arguments, forest_boost, jitter, names = {suffix, row = {sd, w, depth, hu, hv}, share, <aggregates>, u, v, ox, oy, ax, ay, wk, wx, wy, rough}}` |
| Tunables | the elevation composition (`coast`: transfer offset 0.1 and clamp 16 px, detail amplitude 0.45 px and its octaves with their `seed1` 7101 to 7103, the far floor -100, the edge water -1 from scale 3) and the start mask (`start_mask.versions`: every version, oldest first, each naming its formula, which `spawn.lua` builds from the version's numbers; v1 is formula 1, floor 1, span 10; v2 (`spawn-cities`) is formula 2, floor 1, span 10, coarse gain 2), from `europe-coast`; later: detail amplitude, ramp, hotspot and enemy constants, every `seed1`, ore frequency 0.75, the forest boost (2; a per-family data value), the random-oil sea threshold on `tn_land_coarse`, the maps Exact coastlines may act on, river width factors (k = 3 major, 2 minor), ford spacing (60 reference px) and length (8 tiles), the Map type and preset orders | keyed tables of numbers, one group per expression module, added by the milestone that reads them; `start_mask = {versions = {{name, formula, <parameter> = <number>, ...}, ...}}`, a top-level `start_mask_versions` group retired and failing the schema check |

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
   same rule (milestone 3). Milestone 3 fits both at native resolution with `build_geo.py fit`, S1-fit's
   fitter ported operation for operation (it reproduces Europe's 256-term checkpoint bit for bit),
   which leaves every growth step's checkpoint and the fit state in a work folder outside the repo
   and resumes after the newest completed step; `curve` scores the checkpoints with t1_metrics and
   `adopt` copies the smallest at or above the bar, the 256-term one and the curve into
   `data-src/fits/<map>/`. Output: `prototypes/generated/geo_<map>_v<n>.lua`, one scale-independent
   named expression per map that reads the coordinate chain, with row and column factors as shared
   local expressions and balanced parenthesis trees (S1-fit: 131,072 terms compiled and rendered, 4.2
   MB of data.lua), coefficients printed as float32 `%.9g`. A manifest (`data-src/fits/<map>/manifest.json`) records terms,
   offline T1 numbers, input sha256, fit parameters, emitter version and output sha256. Emission is
   reproducible: the same model gives byte-identical Lua, and the gate re-emits from the committed
   model and compares. A refit is a manual, recorded tool run. The same tool emits each map's coarse
   land field from the 256-term checkpoint of the same fit (S9 used Europe's `model-256.npz`, 94.5
   percent offline): `prototypes/generated/land_coarse_<map>_v<n>.lua`, scale-independent, reading the
   coordinate chain, in the same reference-pixel units. Europe's lands in `europe-coast`,
   the other two with their fits in `olde-world-atlantic`; its checkpoint is committed under
   `data-src/fits/` beside the shipped model.
3. **Waterways** (`tools/build_waterways.py`, S4's method). Least-cost paths through thin water
   between snapped waypoints, extended through drawn water to open sea at least 6 px from land, land
   gaps bridged. Per scale: smoothing until no 17-tile stretch turns more than 90 degrees, then
   Douglas-Peucker at 2 tiles (scales 1 to 3) or 3 tiles (4 to 6), and turning basins where the bend
   rule still fails (S4, on its own paths: Dardanelles at every scale; Rhine, Garonne and Little Belt
   at 6; on the re-routed straits only the rivers' remain, design notes waterways). Rivers are
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
   without changing its registered hash. The Map type fallbacks that mirror startup settings are not
   registered, and a frozen fallback is (section "Map type entries"). Each entry is a whole record,
   `{type, sha256, dump, milestone, registered}`, under one contract (`tools/tnfrozen.py`) that every
   reader enforces: the gate's frozen row, `freeze` itself, the T16 frozen and append-only rows and
   `build_zip.py --release`. The dump label names the dump the frozen row reads the body from, so it
   must be a label the runner's milestone registry assigns, and one the record's milestone could have
   produced: a label no entry assigns (a hand relabel to a later milestone's dump, a typo such as `M1`)
   or a missing one fails in every reader and is never skipped, and `freeze` refuses to run on such
   a registry. The gate's frozen row reads every registered body from the dump its record names: a
   well-formed record whose dump the command did not produce (a later milestone's, when the gate runs
   through an earlier milestone) fails too, so no record goes unread.
   Freeze never changes an existing record, and once a reference holds a record the append-only
   checks compare it whole, so a relabel, a retype, a new milestone or date moves it as a new hash does.
   The references are every landed state: main, origin/main, a pull request's base and every
   `v<x.y.z>` release tag; a group's earlier milestone, whose suite manifest
   (`tests/baselines/suites/<milestone>.json`) carries a `frozen` snapshot of the records registered
   through it (written by `suite` and `freeze`; an earlier milestone's snapshot only grows, and a record
   of an earlier milestone without one that no reference holds fails closed); and a zip copied out of
   the checkout, whose build record carries its bodies and its registry's snapshot (step 7). The
   gate fails when a registered name is missing from its dump or its hash changed, so `build_zip.py
   --release` finds every body at any point of the release. The bodies are code built from
   data, so the dump is not the only reader of a body: `tools/tnlua.py` runs the mod's settings and
   data stages offline (a Lua 5.2 subset over luaparser's tree, with stubs for `data`,
   `settings.startup` and `mods`), and every body it builds is held to its record by the T16
   `bodies` row (CI), by `build_zip.py --release` and by a landing; the gate's frozen row holds that
   offline reading equal to the game's dump on every run.
7. **Package.** `build_zip.py` writes `terra-nauvis_<version>.zip` with one top folder, fixed
   timestamps and entry order: two builds give one sha256 (T16), on this machine and on GitHub's
   `windows-latest` runner alike (the repo checks out LF everywhere, `.gitattributes`). `ci.yml`
   uploads that zip as an artifact on every push and pull request; `release.yml` builds the release
   zip on a pushed `v*` tag and publishes it with its `.sha256` as a GitHub release.
   The release does not wait on CI, so its full-history checkout's tag check refuses a tag that is
   not the checked-out commit or whose commit is not on origin/main, and its build applies the
   offline body check, the milestones' snapshots and every earlier release tag. A zip built into a
   folder outside the checkout (the live mods folder) is a landing: it gets the release's body and
   snapshot checks, may not change or drop a body of a zip of this mod already in that folder (read
   offline from the zip itself) nor a record of the build record beside it, and records its own
   bodies and snapshot there.

Generated files are rebuilt by their tool in the same commit as the change that needs them, and never
edited by hand.

## Coordinates and names

### The coordinate chain

Defined once (`coast.lua`, offsets in `spawn.lua`), mirrored by `tools/earthgeo.py`, shared by every
module:

| Name | Expression | Source |
|---|---|---|
| `tn_cx_<map>_v<n>`, `tn_cy_<map>_v<n>` (the city offset names of chain version n: each version of a map's chain reads offset names of its own, and a landed version's names never move, section "Map type entries", binding; design notes 2026-10-28 07:20) | Europe's v1 (`europe-coast`): per-save numbers the preset bakes 0, with frozen fallbacks 0 registered in `tests/frozen.json`; no later version re-points them. From `spawn-cities` (Europe's v2 entry): new names, `tn_cx_europe_v2` and `tn_cy_europe_v2`, per-save keys the preset points at the city fold `tn_city_cx_europe_v1` and `tn_city_cy_europe_v1` (each frozen fallback's body names the same fold), whose value is the if() chain over the map's city table on `tn_city_index_europe_v1` (the per-save number `tn_city_europe`, or for 0 the float32 fold `(map_seed_small * 157 + floor(map_seed / 65536) * 97) % n + 1`) giving `s (c - wr) + floor(s / 2)` for the city's pixel column c, the tile holding the city's pixel centre (S8 oracle convention), and the same for rows; folds to two constants | S7: Tile 9,350 for 1, 30 or 50 cities and for random; 10,039 for the same chain evaluated per tile; `spawn-cities` read the index back at five seeds equal to `tools/oracle.py`'s float32 model |
| `tn_gx_<map>_v<n>`, `tn_gy_<map>_v<n>` | `x + tn_cx_<map>_v<n>`, `y + tn_cy_<map>_v<n>`, the same version's offset names (v2 reads v2's names through a chain of its own, never v1's): the chosen city sits at world (0, 0) | S7 (spawn by shift) |
| `tn_u_<map>_v<n>`, `tn_v_<map>_v<n>` | `(tn_gx_<map>_v<n> - floor(tn_scale / 2)) / tn_scale + wr`, the same with `tn_gy_<map>_v<n>` and `hr`, the map's own `wr` and `hr` from config: what the same version's entry, detail, box and coarse field read. The generic `tn_gx`, `tn_gy`, `tn_u` and `tn_v` with `wr`, `hr` folded from `tn_map` serve preset-only consumers and arrive with the first one | derived below |

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
box (from `edge-and-lakes` with its edge band), the start land guarantee, the waterway and ford sets, the inland lakes and the offshore field
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
| `tn_cx_<map>_v<n>`, `tn_cy_<map>_v<n>` (each chain version's own offset names) | presets | v1: constants 0 (frozen fallbacks); v2: per-save keys naming the city fold, with frozen fallbacks naming it too | all | 1 (v1), 2 |
| `tn_city_<map>` (a fallback mirroring the spawn-city setting), `tn_city_index_<map>_v<n>`, `tn_city_cx_<map>_v<n>`, `tn_city_cy_<map>_v<n>` | spawn | the map's city table (`prototypes/tables/cities.lua`, in the setting's order), `tn_city_<map>`, `tn_scale`, `map_seed`, `map_seed_small` | all; control reads the index at (0, 0) | 2 |
| `tn_start_land_v<n>` | spawn | `tn_distance_v<n>`: `if(d < 16, (16 - d) * 0.5 + 0.1, -inf)`, land within 16 tiles of the spawn (the tile correction step waters the guarantee's outer ring next to the sea, so 16 keeps 12 dry) | Tile only (firewall by rule, though analytic) | 2 |
| `tn_gx_<map>_v<n>`, `tn_gy_<map>_v<n>`, `tn_u_<map>_v<n>`, `tn_v_<map>_v<n>` | coast | `x`, `y`, the same version's city offset names, `tn_scale`, the map's constants | all | 1 (Europe), 3 |
| `tn_geo_<map>_v<n>` | generated | the same version's `tn_u_<map>_v<n>`, `tn_v_<map>_v<n>` (a later version binds the same generated file to its own chain) | Tile only | 1, 3 |
| `tn_land_coarse_<map>_v<n>`, through the key `tn_land_coarse` | generated | the same version's `tn_u_<map>_v<n>`, `tn_v_<map>_v<n>`; the 256-term checkpoint of the map's fit | Entity (the only land field outside Tile) | 1 (Europe), 3 |
| `tn_detail_<map>_v<n>` | coast | basis noise on the map's chain offsets; 0 at pixel centres, amplitude set by the fit's gradient | Tile only | 1 |
| `tn_far_<map>_v<n>` | coast | the same version's `tn_gx_<map>_v<n>`, `tn_gy_<map>_v<n>`, the map's extent W s x H s | Tile only | 1 |
| `tn_ww_*`, `tn_canals_*`, `tn_dams_*`, `tn_fords_*` (per map, scale, version) | generated | `tn_gx`, `tn_gy` | Tile only | 4 |
| `tn_spawn_lake_<map>_v<n>`, `tn_spawn_bias_<map>_v<n>` (through the preset keys `tn_spawn_lake`, `tn_spawn_bias` for the start mask) | spawn | `x`, `y`, `map_seed`, `tn_city_index_<map>_v<n>`, `tn_scale` and the map's generated spawn bearings (`prototypes/generated/spawn_<map>_v<n>.lua`, `tools/build_spawn.py`): the analytic lake about 72 tiles out on the city's lake bearing at the save's scale (inside the land component holding the city), vanilla's starting-lake shape `2.5 ((d + n) / 8 - 3)` (S7: nearest water 42.6 tiles); where the generated table turns it on, the bias clamp(1 + (x, y) . b / w, 0, 1) on the city's generated bearing b and width w (50 to 150 tiles), else 1: `tools/build_spawn.py` picks them, or no bias, per city and scale by the share of starting patches left off the city's own land over 150 random candidate layouts (vanilla takes each ore's best of about 11 candidates in the start disc, so a bias only steers among them; design notes 2026-10-29 00:30) | the lake: Tile, and Entity inside the start mask; the bias: Entity | 2 |
| `tn_inland_lakes_<map>_v<n>` | spawn | the map's `tn_gx_<map>`, `tn_gy_<map>` (spot noise in geo tiles: 8 conical spots of radius 24 per 1,024-tile region, water where `12 (1/3 - spot) + shore < 0`), its fit `tn_geo_<map>` (no lake under 2.5 px from the coast), `tn_distance_v<n>` and `starting_area_radius` (none within 1.5 start radii); design water fraction 0.61 percent of eligible land, fixed in tiles | Tile only | 2 |
| `tn_fields_<map>_v<n>`, through the map-qualified key `tn_fields_<map>` | resources | the hotspot table's offshore rows, the region layer's jittered centres `tn_hu_<id>`, `tn_hv_<id>` moved onto the map's chain by its frame offset; -6 inside each footprint grown by 4 px, else 0; the key is a Map type fallback (`tn_zero` with hotspots off) | Tile only | 9 |
| `tn_elevation_<map>_v<n>` | coast | the composition below, one entry per map; the newest version carries `intended_property = "elevation"`, the `[noise-expression]` name "Terra Nauvis: <map>" and its order (the Map type entry) | Tile only | 1 (Europe), 3 |
| `tn_start_mask_v<n>` | spawn | v1: `clamp((tn_scale * tn_land_coarse - floor) / span, 0, 1)`, floor 1 and span 10 from config; it reads neither the spawn lake nor the far-field box (a firewall name). v2 (`spawn-cities`): `clamp((min(2 * tn_land_coarse, tn_spawn_lake) - 1) / 10, 0, 1) * tn_spawn_bias`, the coarse field in reference pixels (full from 5.5, graded below, the same at every scale), the map's spawn lake and its starting-ore bias, through preset keys | Entity | 1, refined 2 |
| `tn_sea_v<n>` | resources | `tn_land_coarse` below the configured offshore threshold, so rivers, canals, D15 lakes and marshes, which the coarse field reads as land, fall outside it (FEAS-07). Large drawn lakes the coarse field reads as water (Ladoga, the Great Lakes) are not excluded by the threshold; `resources-enemies` excludes them through table rows or records the exception, with the threshold | Entity | 9 |
| `tn_distance_v<n>` | spawn | `sqrt(x * x + y * y)` | Entity, Cliff | 2 |
| `tn_temperature_*`, `tn_moisture_*`, `tn_aux_*` (AB and fallback variants) | climate | latitude from `tn_v`, noise, slider controls (`control:hot` and `control:cold` only when AB is loaded, R3 6), region aggregates, `tn_destroyed` | Tile, Entity | 6, 10 |
| `tn_lat_v1`, `tn_lon_v1`, `tn_dry_v1`, `tn_t_core_v1` | climate | each map's `tn_u`, `tn_v` folded on `tn_map` (preset-only), a meander noise, the dry belts of `config.lua` (EarthMaps' painted sand, design notes climate-tiles) | Tile, Entity | 6 |
| `tn_shore_<map>_v1` | coast | the map's fit, detail and far-field box: v1's transfer with land and water gains for AB's beach band and deepwater line | Tile only (firewall) | 6 |
| `tn_vtile_<tile>` (keys), `tn_vtile_bonus_v1`, `tn_ab_exclude`, `tn_ab_exclude_v1`, `tn_marsh_water_mud(_v1)`, `tn_marsh_water_shallow(_v1)` | tiles | `temperature`, `elevation`, `distance`, `tn_marsh_w` | Tile | 6 |
| `tn_palm_const_v1`, `tn_palm_<a|b>_<p|r>_v1` | trees (from `prototypes/generated/palms_ab_v1.lua`, `tools/build_palms.py`) | the Earth copies of AB 0.8.0's palm probability and richness, frozen as Earth data with the functions they call as local functions, with the constant where AB reads `elevation`; defined on every load, with or without AB | Entity | 6 |
| `tn_temperature_vanilla_v<n>` | trees | the redirected temperature on the fallback climate's vanilla scale and clamp (0.45 times, S3), read by the restored vanilla trees beside AB | Entity | 7 |
| region layer: the interface under "Region layer" (`tn_sd_<id>`, `tn_w_<id>`, `tn_depth_<id>`, `tn_destroyed_*`, `tn_forest_w`, `tn_forest_sum`, `tn_tree_mult`, `tn_marsh_w`, `tn_hotspot_w`, `tn_enemy_mult`) | regions | `tn_u`, `tn_v`, `map_seed`, the shared warp, table shapes, folded hotspot jitter | whichever program reads them: Tile for the zone and marsh lifts, Entity for forests, hotspots and the enemy layer | 5 |
| `tn_vtile_<tile>_v<n>`, `tn_marsh_<tile>_v<n>` | tiles | climate, region aggregates, `elevation` | Tile | 6 |
| `tn_vtree_<tree>_p_v<n>` (one shared richness body `tn_vtree_r_v1`), `tn_vrock_<name>_v<n>`, `tn_vdeco_v1`, `tn_temperature_vanilla_v<n>`, `tn_palm_<a|b>_p_v2`, `tn_palm_const_v<n>` | trees | the base game's texts from `tables/vanilla.lua` with the vanilla-scale temperature (the fallback climate's scale and clamp on the redirected temperature), moisture, aux, `distance` and the base game's shared helpers; the palms' second versions the boost around their first; the forest aggregate only through the key `tn_tree_mult`, which presets point at region-layer's `tn_tree_mult_v1` | Entity | 6, 7 |
| `tn_ore_<ore>_p_v<n>`, `_r_v<n>`, `tn_offshore_p_v<n>`, `_r_v<n>` | resources | live autoplace text, hotspot terms on the hotspot rows' membership, ramp on `distance`, start mask, sea mask | Entity | 9 |
| `tn_hs_<resource>_v<n>`, `_p_v<n>`, `_r_v<n>`, `tn_hs_blob_v<n>`, `tn_ore_ramp_v<n>` | resources | per resource one spot noise over its rows' footprints `min(max(r s, 48), cap s)` read through `tn_depth_<id>`, land from `tn_land_coarse`, `distance`, the size and richness controls, never frequency | Entity | 9 |
| `tn_enemy_layer_v<n>` | enemies | `tn_depth_<id>`, `tn_land_coarse`, vanilla's `enemy_base_radius` and `enemy_base_frequency` by name | Entity | 9 |
| `tn_enemy_v<n>` | enemies | live `enemy_base_probability`, `tn_enemy_mult` | Entity | 9 |
| `tn_cliff_elevation_v<n>`, `tn_cliffiness_v<n>`, `tn_ridge_d2_v<n>`, `tn_ridge_free_v<n>` | ridges | the keys `tn_ridges`, `tn_crest` and `tn_openings`, `distance`, `starting_area_radius` and the cliff map constants in contour units | Cliff | 8 |
| `tn_crest_<map>_v<n>`, `tn_openings_<map>_v<n>` | ridges | the map's chain `tn_u_<map>`, `tn_v_<map>`, `tn_scale`; crest polylines and openings from `prototypes/tables/ranges.lua` | Cliff | 8 |
| `tn_band_<map>_v<n>`, `tn_ridge_clear_v<n>`, `tn_ore_<ore>_p_v<n>` | ridges | the map's chain and the scale (the band, a superset of the tiles within `ore_clear_tiles` of a crest, 3 operations per segment); the clearance reads `tn_band`, `tn_ridges` and the start disc; each ore wrapper the live probability times the clearance | Entity | 8 |

### Preset redirects

Each Earth preset sets these `property_expression_names` keys:

| Key | Value | Program | Milestone | Why |
|---|---|---|---|---|
| `elevation` | `tn_elevation_<map>_v<n>`, the map's own Map type entry | Tile | 1, 3 | coast, waterways, lakes; the preset and the Map type pick name one entry |
| `starting_resources_lake_mask` | `tn_start_mask_v<n>` | Entity | 1 | the vanilla mask reads `elevation` in every starting-ore spot noise (R6 Q3); without the redirect the fine field enters the Entity program. The Earth mask reads `tn_land_coarse` |
| `tn_land_coarse` | `tn_land_coarse_<map>_v<n>` | Entity | 1 | the one land field outside Tile |
| `distance` | `tn_distance_v<n>` | Entity, Cliff | 2 | start features at the spawn whatever `starting_points` holds; D31 can extend it (S7) |
| `temperature`, `moisture`, `aux` | the AB or fallback variant, chosen at data stage from `mods` | Tile, Entity | 6 | S3 |
| `entity:tree-palm-a:probability`, `:richness`, the same for `tree-palm-b` (every preset, AB loaded or not: a world made without AB that gains it later meets the switch; design notes 2026-10-29 18:40) | `tn_palm_a_p_v1`, `tn_palm_a_r_v1`, `tn_palm_b_p_v1`, `tn_palm_b_r_v1`: Earth copies of AB's palm expressions with `tn_palm_const_v1` where AB reads `elevation`; from trees-forests each probability key names its second version `tn_palm_<a|b>_p_v2` (AB loaded), the great-forests hook around the first | Entity | 6, 7 | AB palms read `elevation` (R3 4.1); REVIEW; the hook form cost M2's default Entity a processed expression, so the fallback below ships; AB's palm prototypes carry no hook, so the frozen palm table reads them raw |
| `tn_ab_exclude` (AB loaded) | `tn_ab_exclude_v1` | Tile | 6 | D11: non-adopted AB tiles out of temperate bands |
| `tn_marsh_water_mud`, `tn_marsh_water_shallow` | their `_v1` bodies | Tile | 6 | APPROVALS 8 |
| `cliff_elevation`, `cliffiness` | `tn_cliff_elevation_v<n>`, `tn_cliffiness_v<n>` | Cliff | 8 | S5 |
| `tn_crest`, `tn_openings`, `tn_band` | the map's `tn_crest_<map>_v<n>`, `tn_openings_<map>_v<n>`, `tn_band_<map>_v<n>` | Cliff, Entity | 8 | per-map bodies reached by key, as `tn_land_coarse` |
| `entity:<ore>:probability` for iron, copper, coal, stone, uranium, crude oil (from `ridges`; `resources-enemies` moves them to its wrappers' next version) | `tn_ore_<ore>_p_v<n>`, added in data-final-fixes around the live probability | Entity | 8, 9 | design notes 08:00: the ridge exclusion acts only through Earth ore probability |
| `entity:<ore>:probability`, `entity:<ore>:richness` for iron, copper, coal, stone, uranium, crude oil | `tn_ore_*` | Entity | 9 | S6 (the preset route renders byte-identical to an in-place edit) |
| `enemy_base_probability` | `tn_enemy_v<n>` | Entity | 9 | S6 |
| `entity:offshore-oil:probability`, `:richness` (Oil Rig loaded) | `tn_offshore_*` | Entity | 9 | R4 4.7 |
| `tn_map`, `tn_scale`, `tn_city`, `tn_geo`; each map's city offset names, per version of its chain (`tn_cx_europe_v1`, `tn_cy_europe_v1`; from `spawn-cities` `tn_cx_europe_v2`, `tn_cy_europe_v2`) | numbers; from `spawn-cities` the newest version's offset names name the map's city fold and the map-qualified city number `tn_city_<map>` is baked | fold | 1, 2 | S2 |
| `tn_spawn_lake`, `tn_spawn_bias` | the map's `tn_spawn_lake_<map>_v<n>`, `tn_spawn_bias_<map>_v<n>` | Entity (the start mask) | 2 | the shared start mask v2 reads the map's lake and bias, as it reads `tn_land_coarse` |
| `water_level`, `segmentation_multiplier`, `nauvis_segmentation_multiplier` | 0, 1 and 1.5, their values at the default water slider (config.lua `water_slider`) | Tile, Entity, Cliff | 1 | D15: 2.1.23's only readers of `control:water:*`, which vanilla cliffs, moisture and aux still read on an Earth preset, so the slider is inert on preset worlds |
| `tn_on`, `tn_forests_on` | 1 (forests: 1 or 0 by toggle) | hooks | 4, 6, 7 | S3, S10 |
| `tn_fords` | the map's ford set for the save's scale | Tile (the `water-shallow` hook) | 4 | design notes 12:35 |
| `tn_coast` | not set: each map's entry names its own `tn_geo_<map>_v<n>`, and a later fit ships in the entry's next version (fit review, `europe-coast`) | | | |
| `tn_canals` | the canals toggle, a name switch to `tn_one` or `tn_zero`; each map's entry picks its own waterway, canal and dam sets by name through the folded `tn_scale` (an `if(tn_scale == k, ...)` chain), so no set name is a key | Tile | 4 | per-scale polylines picked by name (REVIEW); only the selected scale and canal branch compile (S4) |
| `tn_ridges`, `tn_hotspots`, `tn_destroyed` | the live body or a neutral body (ridges: `tn_one` on, `tn_zero` off, read by a folded `if()` as waterways' canals switch is) | Cliff, Entity, Tile | 8, 9, 10 | name switches (S2) |
| `tn_inland_lakes` | the inland lakes toggle, a name switch to `tn_one` or `tn_zero` (default off); a version with a lakes field reads its inland lakes through a folded `if(tn_inland_lakes > 0.5, <lakes>, inf)`, so off compiles to the spawn lake alone; its prototype is a Map type fallback that mirrors the setting | Tile | 9a | the decision 2026-10-29 17:50 |
| hook keys (`tn_vtile_<tile>`, `tn_marsh_<tile>`, `tn_vtree_<tree>_p`, `_r`, `tn_tree_mult`) | versioned bodies (every `tn_vtile_<tile>` names the one `tn_vtile_bonus_v1`, A-7) | Tile, Entity | 6, 7 | stable hooks |
| `tn_bandfix` | a name switch, `tn_one`, in a map's preset only when the startup setting Exact coastlines is on and that map passed all four flip checks; absent otherwise, and absent means off | control only | 11 | decision 9 and 12:35 |

Beside the keys, each preset sets `basic_settings.autoplace_controls` frequency 0.75 for the six base
resources and leaves the planet entries neutral (D20; planet values multiply preset values, noise
known gotcha). Every redirect value must name a defined noise expression or be a number: anything
else is ignored with only a log line (noise rule 3). No redirect target reads the property it
replaces (`Parameter 'arg_register' expects Number, None given.`). The presets sort right after
Default: S13 used order "a-tn-a" to "-c" under Default's "a" and before Rich resources' "b".
A preset is not defined while a mod of its config.lua `withheld_with` list is loaded: beside Alien
Biomes the presets were withheld until `climate-tiles`' palm switch (section "Alien Biomes"), which
empties every list, and their fallbacks stay defined, so each map's Map type entry still works there.
Withholding reaches new worlds only: a world made from a preset that later loads beside such a mod
keeps naming its fine field, so control code warns it once and records it (section "Guards"). How a
save made before the switch meets it: section "Alien Biomes".

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
  one its preset names. config.lua's `geography.<map>.versions` holds every version of a map's
  entry, oldest first and the newest last, each with the names, fallbacks and start mask of its own,
  and an older version still counts: control code identifies a
  Map-type-only world by any of them and, after `on_init`, by its record in `storage`, never by the
  Map type fields only the newest carries (design notes 2026-10-28 07:20, worlds identified by any
  entry version).
- **Fallbacks.** A Map type pick sets only `elevation` (`spikes/S13-gui/mgs-maptype-europe.json`),
  so every other name the entry reads needs a prototype-level fallback: a named expression whose
  body is the value the preset bakes under the current startup settings, built from the same table
  as the preset. Surface values beat prototype names (S2), so preset worlds and saves keep their own
  values, and the fallbacks act only on a world made from the Map type alone, which therefore
  follows the startup settings at every load (S2: a value left only as a prototype followed the new
  settings). A fallback that mirrors a startup setting (`tn_scale`) is not registered in
  `tests/frozen.json` (U3's one exemption); a fallback no setting moves is a constant, marked
  `frozen` in config.lua and registered like every Earth body (Europe's city offset names,
  `tn_cx_europe_v1` and `tn_cy_europe_v1`, 0). T16 checks that each equals what its preset bakes.
- **A stamp's layer chain fallbacks (`resources-enemies`).** A version with an offshore stamp reads
  its stamp key `tn_fields_<map>`, a fallback the world follows with the hotspots setting (the stamp
  body or `tn_zero`, with its own drift line), and through the stamp body the layer chain's frozen
  city offset fallbacks (config.lua `layer_chain_geo`; on Europe the city fold behind them). Its
  preset bakes none of those, so both routes read one registered body; T16 (`ec_dump_facts`,
  `owa_dump_facts`) holds the entry's per-save reads to its own fallbacks plus exactly those
.
- **A landed entry's values never move with the mod (binding).** Every name a landed map entry
  reads through a prototype either mirrors a startup setting, which the world follows by design
  (Contradictions item 15), or is a registered body, frozen by the gate's frozen row. No later
  version re-points such a name in place: an entry that needs another value (a city spawn) takes
  names of its own and so its own chain, and its coast, coarse, detail and box bodies under its
  version, which the generated files' name-free data makes a binding in `coast.lua`, not a new
  file. A Map-type-only world therefore moves only with its startup settings, never with a mod
  update.
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
- **Notice.** A world whose Nauvis surface names a version of a map's elevation entry for
  `elevation` and holds no `tn_geo` is a Map-type-only world (section "Guards"). Control code logs a
  one-time notice that names the map's preset and what it adds (Earth climate, ridges and hotspots,
  and fords from `waterways` on), warns that a changed scale setting can move the terrain of chunks
  generated later (the scale fallback follows the setting; every other value it reads is frozen, so
  no mod update moves it), and sends it to each created player (Control stage). Where the map's preset is withheld (beside Alien Biomes until
  `climate-tiles`) the notice says so instead of naming a preset the new-game screen does not list.
  Every message names the map by its preset's name, which no version changes, never by an entry's
  `[noise-expression]` name, which only the newest version keeps. Such a world is not an Earth world
  for the start message, the missing-name guard or the band fix.
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
placed inside the score instead cost default worlds Tile +7,489 and Entity +62 (S3). Folded hooks
still add parsed nodes to Tile's processed-expression counts, which the zero-cost row allows; Entity's
counts must match exactly, which is why the palms take preset keys instead of a hook (design notes,
climate-tiles).

| Hook | Gate | Key | Off value | Milestone |
|---|---|---|---|---|
| 19 vanilla land tiles re-listed on Nauvis beside AB | `tn_on` | `tn_vtile_<tile>` | `-inf` | 6 |
| `water-shallow` registered on Nauvis: fords, then marshes without AB | `tn_on` | `tn_fords` (4), joined by `tn_marsh_water_shallow` (6) in one hook | `-inf`, or AB's own `water-shallow` expression where AB defines one | 4, 6 |
| `water-mud` (marshes): registered on Nauvis without AB; with AB its inland shallows join the max() and stay the off value | `tn_on` | `tn_marsh_water_mud` | `-inf`, or AB's own `water-mud` expression | 6 |
| Every non-adopted AB land tile on Nauvis (D11; APPROVALS 9): `(score) + key` | `tn_on` | `tn_ab_exclude` | the tile's own score | 6 |
| AB palms: no hook (their prototypes stay AB's); Earth presets redirect each palm's probability and richness keys to Earth copies (Preset redirects), or to the neutral body when the installed palm differs from the frozen table (`data-final-fixes.lua`, logged; the gate's dump facts fail) | none | `entity:tree-palm-*:probability`, `:richness` | AB's own palms | 6 |
| 15 restored vanilla living trees beside AB (probability, richness) | `tn_on` | `tn_vtree_<tree>_p`, `_r` | `0` | 7 |
| Forest boost on every living tree (15 vanilla, 65 AB; AB's two palms take it through the second versions of their copies, their prototypes stay AB's) | `tn_forests_on` | `tn_tree_mult` inside `min(1, (orig) * tn_tree_mult)` | `orig` | 7 |
| Vanilla rocks, decals and decoratives beside AB (R3 3.4 items 4 to 6): 3 rock entities and 8 rock and decal decoratives rebuilt from `tables/vanilla.lua` on vanilla land and listed on Nauvis; 11 decoratives AB takes off Nauvis re-listed as `(score) + key` on vanilla land; the AB-restricted vanilla decoratives and dead trees with the vanilla land tiles appended (no gate: vanilla land exists on Earth worlds only) | `tn_on` | per name: `tn_vrock_<name>` (rebuilt, off `0`), `tn_vdeco_<name>` (re-listed, off `-inf`, every one naming `tn_vdeco_v1`) | `0` or `-inf` | 7 (design note 10) |

Tile scores that must lose return `-inf`, never a small or negative number (noise rule 4).

### Region layer (S10 design (d))

Every per-region quantity comes from one layer, built by `prototypes/expressions/regions.lua` from
the rows of `prototypes/tables/regions.lua`, which `tools/build_regions.py` writes from
`approvals-data.json` and R7b (the destroyed polygon with its exclusion rows, the adopted forests,
marshes and hotspots; design notes, region-layer). Design (d) won S10: exact discs, polygons and buffered
paths on one shared domain warp. For 20 Europe regions read in full it cost Tile 13,372 and Entity
11,840 (vanilla 10,068 and 8,549) and drew the approved polygons with IoU 1.0. The runner-up, (b) a
Voronoi of region centres (Tile 11,200, Entity 9,668), turns polygons into discs (shape match 0.20 to
0.41); it is the fallback for forests if timing shows the Entity program cannot afford their
outlines (S10 1.7).

- **Rows.** Each row has an id, a layer (destroyed, forest, marsh, hotspot), a shape (a disc with
  lat, lon and radius in km, or a polygon or buffered path with lat and lon vertices), a warp share,
  the maps that adopt it, and a boost (forests) or a biter multiplier, jitter radius and phase
  (hotspots). Exclusion rows (`mode = "exclude"`, warp 0) keep protected features out of the zone.
  The table is tool-written, so an approval edit is an edit of `approvals-data.json` and a rerun of
  `build_regions.py emit`; the static `regions` row re-emits it and fails on any difference. S10's
  Spessart row added a forest with no code file changed; `rl_locality` repeats that test in a staged
  copy. the first release holds 112 rows: the polygon, 6 exclusion rows, 16 forests, 12 marshes and 77
  hotspots; Europe reads 7, 9, 5 and 21 of them per layer, Atlantic 7, 16, 12 and 77, Old World 7,
  14, 10 and 63.
- **Frame and query point.** Rows are evaluated in the region frame: Europe's reference pixels (pixel
  centres at integer u, v, the chain's frame), which every map's raster shares at 45 px per degree
  (Europe is an exact crop of Atlantic's; Old World's edges are whole pixels away). The query point
  `tn_region_u_v1`, `tn_region_v_v1` is the map's own chain (`tn_u_<map>_v1`, `tn_v_<map>_v1`) plus
  the map's whole-pixel offset (Atlantic -7,093 and -686, Old World -367 and -457), chosen by
  `tn_map` through a folded `if()` chain, so a row sits at its geography on every map and every
  scale. The generic `tn_u`, `tn_v` of the coordinate-chain table stay undefined (no reader yet).
- **Shared warp.** Two 3-octave noises, `seed1` 7801 and 7802, finest wavelength 96 px, amplitude
  12 px, the displacement vector clamped to 24 px in length (a radial clamp, so a row's edge moves at
  most its share of 24 px plus the roughness clamp: the stated 27 px holds at diagonal edges too);
  each row follows its share of it. Edge roughness: 2 octaves at 6 px, `seed1` 7803, amplitude 1.5
  px, clamped to 3 px, added to every signed distance. Each octave is a `basis_noise` whose
  `offset_x` and `offset_y` (`tn_region_ox_v1`, `tn_region_oy_v1`, folded per save) make it read the
  frame's reference pixels, weighted as multioctave_noise weights its octaves (the coarsest 1, each
  finer persistence 0.5 times the last, over their root sum of squares) and shifted along x by its
  octave index times 10,000.37 px so no two octaves share a lattice zero. In 2.1.23 the offsets of
  `multioctave_noise` do not shift its input as those of `basis_noise` do (measured: offset 960 is not
  `x + 960`), which is why the octaves are built one by one. A seed's soft edges are therefore one
  field in geography: the zone is bit-identical on all three maps and at scales 1 and 6, and a spawn
  city never changes it.
- **Warp shares.** The destroyed polygon 1; forest discs 0.25; thin forest outlines (area over
  perimeter under 25 px: the Carpathian, Dinaric and Hyrcanian outlines) 0.4, the other outlines 1;
  marshes 0 (deltas and coasts stay put, roughness only); exclusion rows and hotspots 0. Six exclusion
  rows cut the destroyed zone: the Kiel Canal as a 25 km buffered path, and Semmering, Dukla,
  Gotthard, Brenner and South Foreland as 20 km discs (S10's rule: every protected feature outside the
  polygon within 75 km of it). They kept all 100 protected points outside at every seed for Tile +377
  (S10 section 3).
- **Hotspot rows.** Each adopted hotspot is a disc row of radius r at its adopted centre (APPROVALS
  2, which moves one inland under decision 16) plus S6's jitter of up to j = r/2: the centre
  `tn_hu_<id>_v1`, `tn_hv_<id>_v1` (region-frame px) moves per axis by
  `(2 frac(map_seed_small m + floor(map_seed_normalized 65536) 0.569840291 + phase) - 1) j / sqrt(2)`,
  constants only, with m 0.6180339887 for u and 0.4142135624 for v and a per-row phase (the CRC-32 of
  its id, so adding a row never moves another). Warp 0, so the disc keeps the geometry that APPROVALS
  12's city removal assumes: roughness (3 px) and the outer half of the ramp (3 px) reach at most
  about 15 km past r, inside that table's 50 km margin (derived). Ore and the enemy layer read this
  one disc.

Interface. Consumers read these names and nothing else; each body carries its `_v<n>` (config.lua
`regions.names`), and the static `regions` row fails any other read of the `regions` group outside
`regions.lua`:

| Name | Meaning | Read by |
|---|---|---|
| `tn_sd_<id>` | signed distance to row `<id>` in reference pixels, positive inside, at the warped point plus roughness | the aggregates |
| `tn_w_<id>` | membership weight `clamp(0.5 + sd / 6, 0, 1)`: a 6 px ramp, 36 tiles at scale 6 | the aggregates; per-region consumers, such as each hotspot's ore terms |
| `tn_depth_<id>` | the same signed distance in tiles | consumers that grade by depth |
| `tn_hu_<id>`, `tn_hv_<id>` | a hotspot row's jittered centre in region-frame pixels, a per-save constant | T2; ore spot placement if wanted |
| `tn_destroyed_sd`, `tn_destroyed_w`, `tn_destroyed_depth` | the zone after its rows: `min(include sd, -exclude sd ...)` | the climate lift (temperature above 100), zeroed inside the start radius; the random-pool switch (`destroyed-europe`) |
| `tn_forest_w` | the largest forest weight of the map's forests | forest tiles and decoratives; T10 |
| `tn_forest_sum` | the sum of row boost times weight (row boost 1 by default) | `tn_tree_mult` |
| `tn_tree_mult` | `1 + forest_boost * tn_forest_sum`, forest boost 2 from config | the forest-boost hook on every living tree (S10: probability times 1 + 2 w) |
| `tn_marsh_w` | the largest marsh weight; the same pattern, not measured by S10 | the marsh moisture lift and the marsh tiles (`climate-tiles`) |
| `tn_hotspot_w` | the largest weight over the hotspot rows | the enemy multiplier's footprint; T9 |
| `tn_enemy_mult` | `1 + sum((mult - 1) * w)` over the hotspot rows, mult 4 (APPROVALS 1b) | `tn_enemy_v<n>` |

The layer's own names (the query point and its warped shares `tn_region_u_k<hundredths>_v1`, the
anchor, the warp and the roughness) are read by nothing outside it (rl_dump_facts). Each aggregate
is one body whose per-map branches, folded on `tn_map`, read exactly that map's rows. A row's names
are config.lua names: a stem and the suffix from config.lua around the row's id, which
`tools/tnconfig.py` composes by the same rule as `regions.lua`, so every reader of config's names
sees all of them.

- **One name per quantity (A-7).** A copy of the layer under another name costs about +646
  complexity, while eight consumers of one name cost +14 together (S10). T16 fails any region formula
  outside `regions.lua` (static row) and any re-emitted copy in the dump (rl_dump_facts).
- **Cost and zero cost.** A program pays the shared warp (+518) once if it reads any region; a disc
  costs +29 and a polygon edge +51.8 (S10). Unreferenced, the layer costs nothing: with it in place
  every program of every preset at scales 1 and 6 and of the default world compiles, and every
  preview renders, identically to the build before it (the gate holds the recorded previews and the
  T15a rows equal to main's copies while no consumer is registered: `zero_change`). Read through a
  test MGS (moisture, aux and temperature to `tn_destroyed_w`, `tn_forest_w` and `tn_enemy_mult`),
  it adds Entity +3,234 and Tile +2,029 on Europe, +8,343 and +5,390 on Atlantic, +7,295 and +4,779
  on Old World (`rl_read_cost`). Every consumer sits behind an outermost `if()` on its gate or behind a name
  switch, so with the toggles off the layer compiles to nothing: S10's switches-off worlds were
  byte-identical to vanilla and to AB alone at three seeds, with identical complexity. Europe's
  forests cost Entity +2,332 (+2,538 over AB); Atlantic's and Old World's about +5,600 and +5,000
  (projected, S10).
- **Firewall-clean.** The layer reads only `x`, `y`, `map_seed`, per-save constants and the
  coordinate chain (S10 1.6), so the Entity program may read it; `tn_map` has no prototype, so a
  consumer reads the layer on preset worlds only.
- **Per seed.** The destroyed zone's IoU between seeds is 0.9153 to 0.9225 and with the approved polygon
  0.9429 to 0.9443 on every map at scales 1 and 6, its furthest pixel 22.5 px beyond the polygon (S10:
  0.903 to 0.925, 0.935 to 0.938, 22 px). Cities within about 40 km of its edge may flip per seed (at
  the canonical seeds Przemysl, Rzeszow, Royan, Limoges and others, all within 40 km), and a city that
  must stay on one side gets its own row. The design lets an edge move up to 27 px (66.7 km), further
  than T3's 40 km listing margin; at the canonical seeds no place 40 km or more from an edge flips.

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
3. Far field: `min(e, tn_far_<map>_v<n>)`, a hard cut on the map's W s x H s extent (`if(d < 0, far floor,
   if(d < ring, edge water, inf))` with `d` the signed tile distance to it), deep water beyond the extent
   out to any distance (D15). Tents can reach past the raster edge, so the box, not the fit, ends the map.
   The game lets deepwater border only water (its `allowed_neighbors`), so a land tile on the extent's
   edge would turn the first tile beyond it to plain water; from scale 3, where the extent's outermost
   tile never holds a pixel centre, that tile reads the edge water (-1, plain water), and deep water
   starts 1 tile out. At scales 1 and 2 the outermost tile can hold a pixel centre, so it keeps its
   class (T1) and a land edge keeps the game's plain-water tile beyond it (design notes 2026-10-28 05:30, deep water 1
   tile beyond the edge).
4. Start land guarantee (`spawn-cities`; design note 14): `max(e, g)`, with `g =
   tn_start_land_v<n>` positive within 16 tiles of the spawn and `-inf` beyond, so a city whose pixel
   is water (three on Atlantic, R1 section 11) starts on land. It precedes dams and carves, so a
   named waterway still cuts through it:
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

No step reads `control:water:*` or `segmentation_multiplier`. Vanilla cliffs, moisture and aux still do,
through `water_level`, `segmentation_multiplier` and `nauvis_segmentation_multiplier`, 2.1.23's only
readers of the water slider, so every Earth preset bakes those three at their default-slider values
(section "Preset redirects"): the slider is inert on preset worlds, cliffs and land included (D15;
the gate's `water_inert` row). A Map-type-only world sets only `elevation`, so its cliffs and climate
still follow the slider.

From `waterways` the dams and carves join as a wrapper around the rest of the composing version's
own composition, in a geography version with every name its own (Europe's version 3 over version
2's spawn terms, Atlantic's and Old World's version 2): `elevation = min(max(<steps 1 to 4 and 7>,
dams), carves)`. The guarantee and the lakes come first, so a named waterway still cuts the
guarantee, carves and lakes commute under `min()`, and no lake can reopen a dammed isthmus
.

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
  Map type pick sets nothing else; a fallback no setting moves is frozen
  (section "Map type entries"). Every other per-save number and key has
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
  names a version of a map's elevation entry for `elevation`, any of config.lua's geography versions
  and defined in `prototypes.named_noise_expression`, and holds no `tn_geo`; an older version still
  counts, since only the newest carries the Map type fields, and after `on_init` the record in
  `storage.map_type` identifies the world), one log line naming the map's preset and what it adds,
  and warning that a changed scale setting can move the terrain of chunks generated later (where the
  map's preset is withheld, beside Alien Biomes until `climate-tiles`, the variant says the preset is
  not offered there); each created player receives it once (S11: `game.print` in `on_init` reaches
  no player), built when it is sent from that version's text and the mods active then, so no stored
  message outlives its locale key. `on_init` also records the fallback values the world was created
  with, read from `prototypes.named_noise_expression`, never from `settings.startup`.
- **Drift line** (`on_configuration_changed` with `mod_startup_settings_changed`, which arrives with
  empty `mod_changes`, mod-dev rule 7): one info line per stored scale, city or toggle that differs
  from the current startup setting, for example "this world keeps map scale 3 for life, as every
  world made from a Terra Nauvis preset does; the scale setting (now 5) applies to new worlds and to
  worlds that use a Terra Nauvis map type alone" (S2 Q3). No player-facing text promises that a
  changed setting reaches new worlds only: a Map-type-only world follows it, so the setting's own
  description says so before any change, beside the Map type notice (review round 3, design notes
  2026-10-28 10:00). On a Map-type-only world it runs on every `on_configuration_changed`, a mod
  update as well as a setting change (a same-version mod whose content changed raises the event too:
  its checksum differs, measured in design notes 2026-10-28 05:30), compares the recorded fallback values with the current
  ones, for exactly the names recorded at creation, and says instead that the world follows the
  changed setting, or this version of the mod for a value the mod itself moved (which the frozen
  fallbacks forbid a real build: that line is a tripwire), so new chunks may not match. Each line
  names the map by its preset. It never changes the world. Whether `game.print` at load reaches a
  GUI player is UNVERIFIED (S2); the log line is certain. A headless server's load has no player
  connected, so there the log line is all that remains, and the record moves on, so the line is not
  repeated: on that route the setting's description and the notice are the warnings a player gets.
- **Withheld-preset warning** (`on_configuration_changed` and `on_init`, Earth worlds): withholding a
  preset beside a mod (config.lua `withheld_with`) reaches new worlds only. An Earth world whose
  map's preset lists an active mod, either a preset world loaded later beside Alien Biomes or a world
  made beside it from the preset's full map-gen-settings file, still names its fine field for
  `elevation`, and AB's palms then compile it into the Entity program for every new chunk. No load
  can change a save's names, so this route is outside S-3's checks by design, as the Map type route
  is: one loud warning (`log` and a red `game.print`) per withholding mod, once per save, recorded in
  `storage.earth.withheld_beside` and, through `record_warning`, in `storage.earth.warnings`, which
  each created player receives and `climate-tiles`' palm switch can read (design notes 2026-10-28 07:20,
  a preset save beside Alien Biomes). From `climate-tiles` no preset lists a mod, so no load raises
  it; a save that holds the record keeps it, the palm switch reads none of it, and the text, built
  from this version's locale when a player receives it, stays true for that save: the world was
  made by a version that did not support the mod there, and keeps its palms on the fine field for
  life (section "Alien Biomes"; design notes 2026-10-29 18:40).
- **Stored records** (binding on every milestone that warns a player or reads storage; design notes
  2026-10-28 11:50). `scripts/guards.lua` owns the per-player send path, and every other milestone
  writes to it only through `guards.record_warning(key, args)`:
  - `storage.earth.warnings` is a list of records `{key = <a key of config.lua messages.keys>, args =
    {<LocalisedString>, ...}}`; a player receives one as `{messages.section .. "." ..
    messages.keys[key], table.unpack(args)}`, its text built when it is sent, from that version's
    locale. `record_warning` checks the key and that `args` is a table, stores the record and says it
    at once (`log` and a red `game.print`); a call that breaks that is logged and stores nothing.
  - `storage.earth.sent[player_index]` is the number of records that player has received, and
    `storage.map_type.sent[player_index]` is `true` once that player has had the Map type notice.
  - `storage.earth` also holds `schema`, `map`, `scale`, `geo` (the surface's `tn_map`, `tn_scale`
    and `tn_geo` as numbers) and `withheld_beside` (mod name to tick); `storage.map_type` holds
    `schema`, `map` (a map key) and `fallbacks`, a list of `{name, value}` with the fallback bodies
    the world was made with.
  - A stored key is never removed from or renamed in `messages.keys`: retiring a message keeps its
    key and locale entry. The readers still check every stored field before use: a record of
    another shape, or one whose key this version lacks, is skipped with one log line, and a count
    that is not a number reads as none sent, so no stored record can stop a load or a player's
    creation.
  - `scripts/guards.lua` builds `storage.earth` and `storage.map_type` in `on_init`; every other file
    adds or changes fields of its own and never replaces either table, or `storage` itself, which
    would drop the stored warnings and counts.
  - T16 enforces it: the storage row keeps every other file of the mod off the `warnings` and `sent`
    fields and off wholesale assignments to `storage`, `storage.earth` and `storage.map_type`, and
    requires each `record_warning` call to name a literal key of `messages.keys`; the append-only
    row fails a removed or renamed key against main and origin/main.

### Release versioning policy

1. A body is registered when the milestone that adds it lands, from `europe-coast` on, and
   released when it ships in a release zip. From registration on its text is immutable:
   `tests/frozen.json` holds its record (sha256 and the dump the gate reads it from, among others),
   and the gate fails on a missing or changed registered name and on a record that changed or breaks
   the record contract (Build-time data flow, step 6).
2. Changes ship under new names (`_v<n+1>`), presets for new worlds point at them, and old names stay
   defined forever. An A save under changed code seamed 3 chunks out of the generated area; with the
   new body under a new name it differed in 0 of 41,984 tiles (S2 Q5).
3. The rule covers every named expression and noise function a released body reads, vanilla ones
   included: Earth copies them under Earth names (design review note; a game update to `elevation_nauvis`
   would otherwise seam old saves, S2). Exception: entity wrappers around the pack's live autoplace
   (ores, enemies, offshore oil) wrap it on purpose, so bobenemies' intensity cap and the Oil Rig's
   patch set keep acting (S6, R4, R5). There Earth freezes its own terms only, and old saves' ore and
   enemies follow game and pack updates as vanilla saves do.
4. `tn_geo` is one id space across every map. Each geography release,
   a map's set of geography names a preset points at, takes the next unused positive integer and
   keeps it for good: a change to any geography name a preset points at ships a new release with a
   new id, and no id is reused, renumbered or shared by two maps. config.lua's `release_registry`
   lists every geography release with its `map` and `geography` id, and each geography version's
   `geo_id` (`geography.<map>.versions[n].geo_id`) names its release; the newest version's is the one
   the map's preset bakes. Control code keys release-coupled data (city
   tables for the message and markers, band-fix data) by the save's `tn_geo` alone, resolved through
   `release_registry` (tnconfig's `geo_maps` is the tools' copy), never by "latest" and never by
   scanning maps for a `geo_id`. `tn_map` ids (`maps.<key>.id`) are a second space with the same
   rules. tnconfig's id-space check fails a shared or malformed id and a `geo_id` without its row
   under its own map; the T16 append-only row fails an id that moved against main or origin/main.
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
    fallbacks that mirror startup settings are never registered, and T16 checks them against the
    presets instead; a frozen fallback is registered, so no later version can move the worlds that
    read it (section "Map type entries", binding).

## Control stage

### Events

| Event | Script | Work |
|---|---|---|
| `on_init` | start, guards, markers | Earth world means the Nauvis surface's `property_expression_names` holds `tn_geo`; never decided from `settings.startup` or a noise fallback. A Map-type-only world (the surface names any version of a map's elevation entry for `elevation` and holds no `tn_geo`; milestone 1): log the Map type notice, record the world and its fallback values in `storage.map_type`, run the D33 sweep (Terra Nauvis's own values only) and stop. Other non-Earth worlds: stop (the D33 sweep runs and touches nothing there). Earth: fill `storage.earth` (schema, map, scale, city, geo, toggles) from those values with `tonumber`; read the resolved city index with `calculate_tile_properties` at (0, 0), because the random pick folds in float32 and Lua cannot recompute it (S7: seed 4294967295 gave city 8, the integer hash city 1); set the D29 intro through `remote.call("freeplay", "set_custom_intro_message", ...)` when that interface exists, plus a log line; cliff "none" reset (ridges on and `nauvis_cliff` size 0: write size 1 back with a whole-table assignment and log it; S5 restored 330 of 330 cliffs); D32 RSO warning when `script.active_mods["rso-mod"]` (log `RSO-WARNING` and a localised print, S11); D12 warning when Destroyed Europe was requested without AB (`on_init` runs under the creating settings); both stored through `guards.record_warning` as `{key, args}` records in `storage.earth.warnings` for the per-player path (section "Guards", stored records); D33 sweep; markers if their setting is on; band-fix flag from the save's own key (milestone 11) |
| `on_load` | control | re-register the band-fix handler when `storage.earth.bandfix`; never writes storage (mod-dev rule 9) |
| `on_configuration_changed` | guards | missing-name guard (Earth worlds); drift line (Earth and Map-type-only worlds); withheld-preset warning (Earth worlds, milestone 1; also at `on_init` for a world made beside a withholding mod); D33 sweep; storage schema migration written to be harmless on storage that `on_init` built (mod-dev rule 6) |
| `on_surface_created` | guards | D33 guard on the new surface (it fires inside `LuaPlanet.create_surface`, S11) |
| `on_player_created` | guards | send each stored message to the new player once: the Map type notice on a Map-type-only world (milestone 1), and on an Earth world each warning in `storage.earth.warnings` it has not had (`storage.earth.sent` counts them; every record's shape checked first, section "Guards", stored records), the withheld-preset warning (milestone 1), RSO (D32) and Destroyed Europe without AB (D12): S11 found that `game.print` in `on_init` reaches no player. Tested on a loopback server with a scripted player, a route still UNVERIFIED (Conflicts, item 15) |
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
  because its value differs.
- Only an Earth or a Map-type-only world is touched (`kind` of the Nauvis surface is set), and only a
  default that is Terra Nauvis's: on an Earth world every listed key, because the defaults hold
  `tn_geo` and an Earth preset or file wrote them; otherwise a key of the mod's own (`tn_` prefix) or
  a default that names one of its noise expressions. Several listed keys are vanilla's (`elevation`,
  `distance`, `starting_resources_lake_mask` and the water slider's), and vanilla presets set some
  of them (Island and Lakes set `elevation`, ribbon-world too), so a save made without Terra Nauvis
  that gains it is never touched, and a Map-type-only world keeps every vanilla value. T14's
  negative control holds it: an Island world, new and with the mod added to its save, keeps the
  inherited `elevation_island` on both probe surfaces.
- From `ridges` a default that is not an Earth world's is stripped only through
  `guards.earth_valued(key, value)`: the default value names an Earth body (it carries config's noise
  prefix) or the key is an Earth per-save key.
- From `ridges` the list holds vanilla properties (`cliff_elevation`, `cliffiness`, the six ore
  probabilities; `elevation`, the water slider's readers,
  `starting_resources_lake_mask`, `distance` and the climate properties from earlier milestones).
  Vanilla's Lakes and Island presets set `cliffiness = cliffiness_basic` and `cliff_elevation =
  cliff_elevation_from_elevation`, the values Space Age's Vulcanus, Gleba, Fulgora and Aquilo set
  themselves (`moisture_basic` and `aux_basic` likewise on Fulgora and Aquilo), so the value
  comparison alone would blank those planets' own keys on a world that is no Earth map. The Earth-value
  rule (S11's own: compare with the Earth presets' values) makes a non-Earth save match nothing by
  construction. The static `d33_guard` row requires the guard to strip through `earth_valued`, with
  fixtures in which a value-only guard fails.
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

- Until `climate-tiles`' palm switch, every Terra Nauvis preset is withheld beside AB (config.lua
  `presets.<key>.withheld_with`): AB 0.8.0's `tree-palm-a` and `tree-palm-b` read `elevation` in the
  Entity program, so a preset there would carry its fine field into it (S-3). Each map's Map type
  entry stays, outside S-3 by design, and its notice says the preset is not offered beside AB. The
  gate's `ab_withheld` row checks it.
  Withholding reaches new worlds only: a world made from a preset without AB and later loaded beside
  it (AB places its trees under the `trees` control the surface already has) names its fine field
  for good, so its palms read it in the Entity program from then on. That save route is outside
  S-3 by design: the guards warn it once and record it in storage for the palm switch, and
  `ab_withheld` checks the warning (section "Guards"; design notes 2026-10-28 07:20). The maintainer may rule
  otherwise (option (b) of design notes 2026-10-28 05:30 pulls the palm switch forward).
- The palm switch shipped in `climate-tiles`, which empties every `withheld_with`, so the presets are
  offered beside AB again. How a preset save meets it (design notes 2026-10-29 18:40, the migration
  record for this route):
  - A world made from a preset by a build from `europe-coast` to `region-layer` names no palm key.
    Loaded beside AB it keeps AB's own palms on its fine field for life, so its palm placement has
    no seam and its new chunks keep the Entity cost its warning names. No load writes the palm keys
    into it: the guards change no Nauvis key (section "Guards"), and a switch written at load would
    end AB's palm band at the edge of the generated area. Saves that met AB under one of those builds
    hold the warning and `storage.earth.withheld_beside`; one that first meets AB from
    `climate-tiles` on is not warned, since no preset lists a mod. Both are accepted because no
    release shipped those builds: the first release saves carry no compatibility promise (Release versioning
    policy, rule 8), so such saves are test worlds.
  - A world made from a preset by `climate-tiles` or later carries the four palm keys whether or not
    AB was loaded (Preset redirects; the copies are defined on every load), so when it gains AB its
    palms read the copies from AB's first chunk on, as a world made beside AB does; chunks generated
    before AB hold no AB palms, so there is no seam. The other AB keys stay AB-only: such a world
    keeps its fallback climate and takes AB's own tiles over it (Tile only, outside S-3).
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

Installed since 2026-10-28 and pinned off in every runner modset. The maintainer's
rule (2026-10-28): Terra Nauvis must work with Space Age and never touch other planets. A preset key
reaches every planet that does not set that key itself, so every key an Earth preset sets is listed in
config.lua's `preset_keys` (tnconfig's schema check fails a baked key it lacks), and the D33 guard
(`scripts/guards.lua` `surface_guard`, from `spawn-cities`) removes exactly those keys from every other
surface (S11). The `sa-compat` run on the `spawn-cities` draft (`previews/earth-build/sa-compat/r1`,
with space-age, quality, elevated-rails and recycler on) found Vulcanus, Fulgora, Gleba, Aquilo and the
platform generating as without Terra Nauvis once the guard ran, and the inherited keys without it.
Gated hooks on vanilla tiles would hide them from any other planet that lists them (AB's own comment
says removing vanilla tile autoplace broke Space Age, R3 3.2). The GUI and play remain smoke step 8.

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
| A Map type entry picked alone | reported, not gated: its Tile, Entity and Cliff complexity and its forced-generation ratio at 16 LP, scale 6, against M0 (M2: BAB), with the same pair at 8 LP recorded beside it; vanilla's starting-ore mask and AB's palms read the fine field there (Map type entries) | design notes 12:35; TQ1b; design section 6.2 | `europe-coast`, `olde-world-atlantic`, `climate-tiles` |
| Earth Lua per chunk | 0 without the band fix; `scriptUpdate` within 0.01 ms per tick of vanilla | brief section 5, test notes 5.5 | T16 static allowlist; gate perf step |
| Band fix, when on (Exact coastlines) | per map: average at most 0.24 ms per generated chunk and no handler tick above 2 ms, measured on Europe at scale 1 and on Olde World at scale 6, both at 16 LP, with 8 LP recorded | design notes 07:05 and 12:35 | `coast-band-fix` |
| Preview time | reported, not gated: TQ2 measured S9's composite at 5.09x vanilla at 1024 px (6.27x at 256 px), against the 5.4 to 6.5x estimate (REVIEW); tents 4,096 2.94x, AB alone 4.05x (TQ1b) | design notes 07:05 and 10:20 (D8 reading); TQ2; test notes 5.5 | milestone suites from `europe-coast` (`preview_time`, T15-f: 1024 and 256 px centred on the T15b block, seed 1000, `--threads 8`, 7 valid repetitions per config, the `Map preview generation time` line); release suite |
| Trees and saves | great forests 2.0x the trees of the same chunks without the boost (accept 1.6 to 2.5); at most 0.1 percent of trees moved outside; trees per generated block at most +27 percent on Europe (+17 Atlantic, +19 Old World); the T10 block's save at most +3 percent; against the same pack without Earth, reported only | decision 15; S10 4.4 | `trees-forests` (T10) |
| Save size | the forced block's increment between two server saves, gated by the plan's P19 against vanilla (AB: AB alone); the whole save reported. TQ2: increment 1.07x vanilla (0.72x AB alone with AB); whole save 1.50x, because the composite stores its start area about 280 KB larger than vanilla's, twice (`level-init.dat` and `level.dat`), cause untraced; `europe-coast` traces and reduces it | design notes 10:20; TQ2 | milestone suites from `europe-coast` |
| Startup time, memory, data size | reported. TQ2 reference: data stage 0.530 s against vanilla's 0.368, a new map's first 120 ticks 13.5 ms against 13.2 (EarthMaps 7,035, Factorio World 1,690), peak working set while exploring 221 MB against 205; TQ2's prototype held Europe only, so the shipped mod's startup and memory run somewhat higher (TQ2 caveat) | design section 6; TQ2 | peak working set while exploring, M1 minus M0: milestone suites from `europe-coast` (the benchmark-mode walker at 16 and 8 LP, the real-time runs at 24 LP; `perf.Monitor` reads each game process's peak, kept in the monitor record beside the run); startup: release suite (T15d) |

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
| S-1 | Every game run goes through `%FACTORIO_WS%\tools\fh.py` with its own instance, modset and new `--out`, and every run that writes data has a RESULT line reading `ok`, `isolated=yes` and `errors=0`, so no test run points the game at `%APPDATA%\Factorio`; copying the built zip into the live mods folder is allowed, and players still get the zip of a GitHub release by hand | G1, the only live-profile protection: `earth_test.py` refuses any other RESULT on a run that writes data (`--version` and `--help` runs are exempt and say so; a loopback server passes with `exit=timeout`, TST-11), and a run whose `run.json` records isolation as anything but true, a NOT-ISOLATED RESULT or a run on another build (G8) stops every further game run of the command at once (no row or group loop catches it: the job is terminated before the lock is released), across the runner's parallel workers too (the first breach in any worker stops the command and terminates the job at once, every worker checks the stop before each job and nothing launches after it: the `lane_stop` runner controls), as do the game self-test and `dump_render.py` on their own runs; fh.py itself refuses graphical and portal flags and a repeated `--config`, `-c` or `--mod-directory`. The chained G9 guard, the write guards and the T16 launch and output-options scans are retired |
| S-2 | Registered expression bodies are byte-frozen in their generation fields (`tests/frozen.json`, from `europe-coast` on); names are append-only; the Map type fallbacks that mirror startup settings are the one exemption (a frozen fallback, a constant a landed entry reads, is registered) | the gate's frozen row on the dumps the runner's registry names (M1; M2 from `climate-tiles`): every Earth body (a prefixed or config-defined noise body) registered unless it is the placeholder's or a fallback, every registered body present and unchanged in the dump its record names, with the exact freeze command on a failure, every record holding the `tools/tnfrozen.py` contract (all five fields, the dump label one the registry assigns and the record's milestone could have produced, so no record can switch the row off for its body; the static reading of the registry checked against the live one), and the registry append-only against the union of main's and origin/main's `tests/frozen.json`, whole records compared, failing closed when that reference cannot be read; `freeze` refuses a registry that breaks the contract or a body changed in place; the T16 append-only row, the same comparison without the game, which CI runs on a full-history checkout, and which also fixes the data a landed row's bodies are built from once a reference holds a release row (config.lua's coordinates, number format, coast, spawn, keys, start mask and geography versions and map geometry, the landed release rows, every file a landed row or version binds, each map table of `prototypes/tables/`, and the allowed values of every setting a version's spawn record names, held exactly, since the city fold's random pick folds over their count and presets bake a city as its position; a table may gain keys and a versions list entries at its end, nothing else changes), so a regenerated file or an edited constant fails on a pull request that never reaches the gate; the T16 frozen row (the record contract, and every noise name config.lua defines, the region table's composed names included, the same exemptions, against `tests/frozen.json`) and fallback check; config.lua's schema (every firewall body but the placeholder's in a release row, every noise name prefixed); `build_zip.py --release` refuses a record that breaks the contract and any other unregistered body |
| S-3 | On Terra Nauvis presets the Entity and Cliff programs never read the fine coast field; their one land field is `tn_land_coarse`. A Map type entry picked alone is outside this by design and is timed and reported (Map type entries) | isolation check (a) against the constant-coast twin and (b) the static walk, gating from `toolchain` (whose placeholder preset redirects the start mask too), each with its positive controls on the test-only `ea-leak-fixture` presets (the start-mask route; for (b) also a redirected entity and decorative autoplace key, which the walk follows as the program reads it); beside Alien Biomes, whose palms read `elevation`, every preset whose `withheld_with` lists AB is not defined (toolchain's placeholder, then from `europe-coast` the real presets, design notes 2026-10-28 05:30, the preset withheld beside Alien Biomes), which the gate's `ab_withheld` row checks on M1 plus the live AB copy: no withheld preset in the dump, isolation (b) on every preset that is defined there, the Map type entries and fallbacks still defined, and its control walking each withheld preset's own redirects to the fine field through the palms. A preset world loaded later beside AB is outside these checks by design: it is warned once and recorded (Guards; `ab_withheld`'s save route). `climate-tiles` ships the palm switch and the M2 isolation checks (design note 9) and lifts the withholding; from then every preset bakes the palm keys with or without AB (`ct_dump_facts` on M1 and M2), so only a save made before the switch keeps its palms on the fine field beside AB, for life and by design (section "Alien Biomes"; design notes 2026-10-29 18:40) |
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
  `suite`, `install-check`, `baseline`, `freeze`; the content-hash cache; the workspace lock around
  every command; the threshold-table parser), `build_zip.py`, `perf.py`, the lint setup, S8's tools and
  `earthgeo.py` with their self-tests, `data-src/earthmaps/` with provenance, ported copies of the S8
  reference JSONs and `approvals-data.json` with their sha256, `tests/budgets.json` for
  measured values, an empty `tests/frozen.json` with its checker (hashing generation fields only),
  `tests/baselines/` for build 87750, the T3 oracle's brief-sourced climate rows, the
  `static` command, and `.github/workflows/ci.yml` and `release.yml`.
- **Contract.** The runner refuses to run a game-launching command without `FACTORIO_WS` and fh.py;
  `static` launches nothing and runs in CI; every game run is isolated
  (S-1); the build is pinned to one game build (G8: 2.1.24 build 87808 since design notes 2026-10-29
  09:00, 2.1.23 build 87750 before); zips are byte-reproducible, here and on
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
  that dump with the placeholder's redirects to the fine field through the palms. `europe-coast`
  withholds its real presets beside AB the same way until `climate-tiles`' palm switch, and the row
  became `ab_withheld`, which speaks for every withheld preset (S-3; design notes 2026-10-28 05:30).
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
    `tools/tnconfig.py`, because `release.yml` runs without the game (from `spawn-cities`' group it also
    builds them offline through `tools/tnlua.py` and holds each to its record, design notes 2026-10-29
    08:30); from `region-layer` on, with the names composed from the region table that a release row lists).
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
  - *Launch scan (retired).* The launch scan, its vendored fh.py flag sets
    (`tools/lint/fh-flags.json`) and the gate's fh_flags row are retired with the write guards and the
    chained G9 guard: fh.py
    isolation (G1) is the only live-profile protection, fh.py itself refuses graphical and portal
    flags at launch, and copying the built zip into the live mods folder is allowed. Every scan
    fixture that remains (workflow, attribution) is generated at run time in a temporary directory
    outside the scanned trees and never committed, so the real scans need no exemptions.
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
    owner is dead is free.
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
  the coordinate chain with the `floor(s / 2)` constant (its city offset names `tn_cx_europe_v1`
  and `tn_cy_europe_v1` are frozen 0: a city spawn reaches the entry's next version through names of
  its own); the transfer, detail and far-field box; `tn_elevation_europe_v1`, also Europe's
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
- **Build note** (process, not a contract). The build hands the builder only the args record, so
  before writing code the builder reads its issue, the plan's "### Milestone 0: europe-coast" with its
  sections 2, 4, 5 and 6, and this file's europe-coast section with "Map type entries", "Elevation
  composition", "Per-save parameters and versioning" and "Control stage". Order of work: the final
  code change, then `python tools/earth_test.py baseline`, then `python tools/earth_test.py suite
  europe-coast` last.
- **Fit review, folded in.** The accepted patches beyond the rows above; where the build decided
  differently, the design notes entry named here governs.
  - *Runner registry and section 6.* The registry holds europe-coast (FG rows `ec_dump_facts`,
    `geo_emit`, `t1_t2_grids`, `t3_oracle`, `t11_pair`, `t12_twice`, `t13_routes`, `maptype_route`,
    `t16_guard`, and from the review `water_inert`; its suite checks; `oracle_properties` land and
    water, which `tests/oracle/expressions.json` maps to `elevation`). P1, P4, P5, P6, P7 and P19
    have consumers in `LIMIT_CONSUMERS`; the runner control for a row in force without a consumer
    now uses P2 at `climate-tiles`.
  - *The placeholder retired in the runner.* The toolchain rows run on the real Europe preset:
    `t13_dump_facts` holds the dumped preset to config.lua's table, `t13_preset_preview` (renamed from
    `t13_placeholder`) and `t13_scenario` use Europe, `tests/budgets.json` holds Europe's rows at
    scales 1 to 6 with toggles on and off, and the baseline record keys Europe's preview. Exactly one
    Earth body, the newest Europe entry, carries `intended_property`.
  - *A Europe-bound entry.* Europe's chain is its own (`tn_gx_europe_v1`, `tn_gy_europe_v1`,
    `tn_u_europe_v1`, `tn_v_europe_v1`, with Europe's radii and extent from config), the detail and box
    are per map, and the entry names `tn_geo_europe_v1` directly; it reads only `tn_scale` and the
    map-qualified `tn_cx_europe_v1` and `tn_cy_europe_v1` (design notes 2026-10-28 03:40, the Europe-bound
    entry; the names took the chain's version in design notes 2026-10-28 07:20). The generic chain arrives
    with its first preset-only consumer.
  - *The city offset route.* `tn_cx_europe_v1` and `tn_cy_europe_v1` (renamed from `tn_cx_europe` and
    `tn_cy_europe`) are baked 0 with frozen fallbacks 0, registered in `tests/frozen.json`, so no
    later build can move a Map-type-only world made from this entry; `spawn-cities` gives its v2
    entry names and a chain of its own and binds the same name-free generated files to it. They have
    no T11 row, since no setting moves them (design notes 2026-10-28 07:20 supersedes the in-place
    re-point of design notes 03:40).
  - *Timed positions.* Every timed block and band is Phase 4's, fixed in geo coordinates through
    London's pixel and placed through the save's offset; the scale 1 block holds the scale 6 block's
    extent clear of the start area. Land 92.3 and 79.9 percent.
  - *Generated files and T16.* `build_geo.py` writes name-free data within 120 columns; the gate's
    `geo_emit` row re-emits both files twice with a lazy numpy import; S9's constants live in
    config.lua (`coast`, `start_mask`; A-11); `data-src/fits/europe/` carries its `PROVENANCE.md`, which
    T16's data-src row re-hashes; `.gitattributes` marks `*.npz` binary.
  - *Measured, not designed.* T1 previews run with cliff richness 0 and read player-blocking water
    colours; the two creation routes agree on content while their benchmark checksums differ; the
    first-column hitch and the start-area save excess are the coast program's (design notes, the T1,
    T3 and T13, hitch and save-excess entries).
  - *Review, folded in*. Every Earth preset bakes vanilla's three water-slider readers
    (`water_inert` row); the presets are withheld beside Alien Biomes until `climate-tiles`
    (`ab_withheld` row); the Map type notice warns that a mod update can move such a world, and its
    drift line runs on every configuration change (T18 suite check, a moved-offset build); from
    scale 3 the extent's outermost tiles are plain water, so deep water starts 1 tile beyond every
    edge, and T3 measures the extent from the far-field switch and carries its exit-0 guards; T11
    compares entities as well as tiles and reads back every baked value; the V1 contact sheets are
    committed under `tests/baselines/suites/europe-coast/v1/`, with smoke step 2's preview in the
    manifest.
  - *Review round 2, folded in*. A Map-type-only world is identified by
    any version of its map's entry and then by `storage`, and every message names its map by the
    preset (T18's older-entry build proves both); the city offset names are pinned to the entry's
    version and registered; a preset world loaded later beside Alien Biomes is warned once and
    recorded (`ab_withheld`'s save route); a breach in one of the runner's workers stops every worker at
    once (`lane_stop` runner controls); T2 reads back each run's seed with M0's grid as its positive
    control, `t3_detail` probes off-centre tiles and the on-grid's T1, `t12_twice` and `t13_routes`
    prove Earth active against M0.
  - *Review round 3, folded in*. No player-facing text says a changed
    scale setting reaches new worlds only: the setting's description, the drift line, the preset's
    description and the mod's changelog say that a preset world keeps its scale and that a world
    using a Map type alone follows the setting, which moves its new chunks (the route beside Alien
    Biomes). Section 6.2's recorded rows are complete for this milestone: the walker and the Map type
    route's forced pair also run at 8 LP as the diagnostic, `preview_time` records T15-f, and the
    exploring runs keep each game process's peak working set (T15-h), M1 minus M0.
  - *Review run 2's review, folded in*. A `tests/frozen.json` record's
    dump label can no longer switch the frozen row off for its body: every record holds the
    `tools/tnfrozen.py` contract in every reader (a label the runner's milestone registry does not
    assign, a typo, a missing label or one the record's milestone could not have produced fails and is
    never skipped; `freeze` refuses such a registry), and the append-only checks compare whole
    records, so a relabel of a landed record fails like a new hash. The coordinate chain's rows
    name the offset per chain version: v1's are the frozen 0s, and `spawn-cities`' v2 reads names
    and a chain of its own.
  - *Group build with `spawn-cities`, folded in*. The gate's frozen
    row reads every registered body or fails: a record whose dump the command did not produce
    fails like an unknown label. config.lua holds every version per map: `geography.<map>.versions`
    (each version with its own names, `tn_geo` id, city offset, start mask, generated files and Map
    type fallbacks), `start_mask.versions` (each naming its formula), and no top-level `fallbacks`
    group; `presets.lua` bakes the newest version and values every version's fallbacks from that
    version's own table, `coast.lua` emits every version over its own chain, `spawn.lua` every start
    mask version, and `guards.lua` records the fallbacks of the version a Map-type-only world names.
    The dumped prototypes are byte-identical to the one-version layout's. T16 holds the documented
    next version (names of its own, the next `tn_geo` id, the same generated files) as a positive
    control and its re-pointing, shared-id, unkeyed, unwalled and stray-file variants as negative
    ones; the coordinate chain, inventory and `spawn-cities` and `extras` contracts name each chain
    version's own offset names. The V1 sheets' preview panel tiles every T1 preview of its scale, so
    the whole-map sheets at scales 3 and 6 and the crops on a preview edge show their whole window
. The runner's kill control checks the probe's own games, by
    ancestry, pid and start time, so another run's game on the shared machine is no failure
, and the timing census leaves out a wholly suspended game process
    (a draft the run's governor parks while the workspace lock is held), which becomes foreign the
    moment it runs.

### 2. `spawn-cities` (part 2, order 1)

- **Introduces.** City tables and per-map city settings with random, minus the cities APPROVALS 12
  removes; `tn_city_europe`, the v2 chain's own offset names `tn_cx_europe_v2` and `tn_cy_europe_v2`,
  `tn_city_index_europe_v1` (random is the folded hash of
  `map_seed`, S7); the analytic spawn lake; the start land guarantee (composition step 4); sparse
  inland lakes at a fixed density; the `distance` redirect; a refined start mask for coastal and
  low-lying cities (vanilla's mask starves starting ore below elevation 11, S7); `scripts/start.lua`
  (world detection, storage, D29 message); the D32 warning at creation and to every created player
, on the per-player path `europe-coast` opened for the Map type notice; the D33 guard;
  Europe's city setting reaching its elevation entry through a map-qualified name with its own
  fallback, so a Map type pick spawns at the setting's city. That name belongs to the entry's next
  version (`tn_elevation_europe_v2`) and its own chain: v1's offset constants never move (section
  "Map type entries", binding), so v2's coordinate chain, coast, coarse, detail and box bodies ship
  under v2 names, bound to the same name-free generated files (config.lua's `fits`), and v2 joins
  `geography.europe.versions` after v1 as a version of its own: its next `tn_geo` id with its own
  release row, its fallbacks (`tn_scale` and the city setting's map-qualified name), its start mask
  version (`start_mask.versions`, a formula of its own for the spawn lake), its offset names in
  `preset_keys` and its fine field in the firewall; v1's record stays as written (design notes
  2026-10-28 17:40).
- **Contract.** Starting ore and the enemy-free start come from vanilla's own terms through
  `distance` at the origin, the lake from the analytic spawn lake (S7: one patch per ore, 0 enemies
  within 150 tiles, nearest water 42.6 tiles). Under the shift every world coordinate converts as
  `world = geo - (tn_cx_<map>_v<n>, tn_cy_<map>_v<n>)`, the save's own chain version's offsets;
  `tools/oracle.py` holds the conversion and the float32 model of the random fold, and control code
  never recomputes the city: it reads the index back at (0, 0) and resolves the city table through
  the save's `tn_geo` (the release registry), never the newest version.
- **Build notes** (design notes 2026-10-28 20:00, which supersede the draft's 05:40 entries where they
  differ). Europe's version 2 is `geography.europe.versions[2]` with every name its own (`_v2`
  chain, entry, coast, coarse, detail and box, bound to version 1's generated files), geography id
  2 with its own release row, the frozen offset fallbacks `tn_cx_europe_v2` and `tn_cy_europe_v2`
  naming the city fold, the city number `tn_city_europe` as a fallback that mirrors the setting, a
  spawn record (`spawn = {...}`) naming the spawn bodies, and `tn_start_mask_v2` (formula 2); every
  version 1 name and record is unchanged. The city setting's values live in config.lua and the rows
  (degrees) in `prototypes/tables/cities.lua`; inland lakes are spot noise; the europe-coast T1, T2
  and T3 rows score the coast in a coast-only world (the preset's keys with version 2's offset names
  0 and the lake and guarantee bodies neutralised through `property_expression_names`), and timed
  positions place through the runner world's spawn offset; T14's runtime control is a staged build
  with the surface guard disabled; no player can be scripted headless, so the per-player sends stay
  with smoke steps 4 and 1. A group's gate meets the allocations of every unlanded milestone up to it
  together.
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
- **Build notes** (binding for the runner; design notes, olde-world-atlantic).
  - *Every map from here.* The registry entry adds FG rows `owa_dump_facts` (the three entries,
    their locale, orders and fallbacks, and no entry reading another map's name, through the
    prototype names and through each preset), `owa_routes` (route parity per new preset),
    `owa_maptype` (the elevation-only route per new map, with its notice) and `owa_t7_random` (T7 and
    T18 (a) at random per new map), and the suite checks `owa_fits`, `owa_t1_grids` (grid T1 at
    scales 1, 3 and 6 and T2 at 1 and 6), `owa_t1_windows` (twenty 1024 px windows on the densest
    coast), `owa_v1_sheets`, `owa_t7` (every city plus random), `owa_t11`, `owa_maptype_cost` and
    `owa_t15b`. From this milestone T15a, the baseline and isolation (a) at scale 1 cover every
    preset's map (`budget_maps`); europe-coast's own rows stay Europe's.
  - *Controls* (U1, project rule 6). The no-leak (A-21) and fallback checks are pure functions over a
    dump (`entry_isolation_findings`, `fallback_findings`); `owa_dump_facts` also runs them on a copy
    of the M1 dump in which the first new map's geo body gains a local reading Europe's geo body and
    its cx fallback reads 1, and each must fail, A-21 on both its routes (the Map type route and the
    preset's). `owa_controls` holds `fit_record`'s selection rules
    (`fit_findings`: growth 1.25 at step 1, the smallest checkpoint at or above 0.991, the 256-term
    coarse field) to fixtures that must each fail, the smallest-checkpoint rule once for every
    smaller step raised to 0.991 in turn, beside the committed records, which must pass.
  - *Coast views.* The 256 px window at the spawn is all land on Atlantic and Old World (and
    renders byte for byte as Europe's there), so each new map's route parity and Map type previews
    sit on the nearest window holding 15 to 85 percent reference water (`map_view`), and each map's
    elevation-only preview is compared there with the other maps' entries.
  - *Timed blocks.* The new maps have no Phase 4 block, so each map's scale 6 block is the 16 x 16
    chunk block nearest its spawn whose reference land, and its scale 1 twin's (europe_block's
    rule), both lie in 50 to 95 percent (`map_positions`), fixed in geo coordinates like Europe's.
  - *T1-e* is reported per size bucket on the new maps (plan 6.1); T1-a reads a flipped map's bar
    from `tests/baselines/t1-bars.json`, else 0.991.
  - *Flipped bars*. `tests/baselines/t1-bars.json` is `{"maps": {<map>: {bar, decision,
    checkpoint}}}`, refused whole (`t1_bar_findings`) unless every row is a new map's (europe-coast's
    rows read 0.991 and would ignore it), its bar is under 0.991, its decision is the heading text of
    exactly one the design notes entry whose body names the map, cites its `owa-t15b-<map>-` run
    directories, states the bar as the file writes it and names the best-fit checkpoint, and
    `fit.json` ships that checkpoint (`fit_findings`). `owa_t15b` fails a fired flip with no bar and a
    bar on a map whose flip did not fire (`flip_findings`); `owa_controls` holds each rule to a
    fixture that must fail.
  - *Spawn cities.* The new maps' city data ships in `spawn-cities`' shape (`spawn_city_atlantic`,
    `spawn_city_olde_world`, their dropdown locale and design-rules rows, and each map's table in
    `prototypes/tables/cities.lua`); `owa_dump_facts` holds each dropdown to EarthMaps' list minus
    APPROVALS 12's removals plus random, and each table's keys, source order, names and positions
    to the dropdown and EarthMaps (`city_table_findings`). The fold and the entry's spawn terms join
    with `spawn-cities`' mechanism, through the same per-map geography fields Europe takes there;
    until a map carries them, `owa_dump_facts` fails its spawn-city setting as one no save records
    (`city_fold_findings`), and with them it requires the per-save city among `preset_keys` with a
    map-qualified fallback and the city offset naming the fold. Integrating means: the new maps'
    geography fields as Europe's, their spawn bearings and fold bodies, each entry composed with the
    spawn terms, and the oracle rows T7 reads. The composition goes either into v1, which is not on
    `main`: drop the draft's `tests/frozen.json` entry of every body it changes (`freeze` refuses a
    registered body that changed) and let `freeze` register the composed bodies; or into a v2 that
    takes over the Map type fields, v1 kept defined and registered.
  - *T7.* `owa_t7_random` (FG; design section 5 step 8) runs `spawn-cities`' `t7_random` on each new
    map; `owa_t7` (SS) first checks T7 (a) against the reference data with no game
    (`owa_t7_reference`: each city's EarthMaps pixel land or one of Kovdor, Johannesburg and Chengdu,
    which the start land guarantee carries; every city outside each adopted hotspot's margin), then
    runs every city plus random at scales 1, 3 and 6 through `sc_t7_eval` and random at S7's five
    seeds against the float32 model. Both run on `spawn-cities`' machinery by name and fail closed
    while a map has no fold or the runner lacks it (`owa_t7_gaps`).
  - *Frames.* `map_view` and `map_positions` place views and timed blocks through `map_offset`
    (the baked offset, else `spawn-cities`' `runner_offset`, else a refusal); the timed blocks are
    chosen in the geo frame and moved into the timed world's chunks. T1, T2 and V1 score the new maps
    in the geo frame (`t1_frame_mgs`: the preset while the offset is baked 0, else `spawn-cities`'
    coast-only world), where `coast_windows`, the grids and the band probes sit.
  - *City halves of T11 and T13.* A map's geography carries the city fold when it holds
    `city_setting`, `city` and `city_index` (`city_fold`). `owa_t11` then flips the city with the
    scale (A the setting's default, random; B the dropdown's last city) and requires the index read
    back at (0, 0) under B to equal fresh A's, fresh B's to differ, and the city drift line once
    (`t11_city_findings`); `owa_maptype` reads the index back on the elevation-only world and on the
    preset world and requires them equal, each a city of the table (`maptype_city_findings`). A map
    without the fold fails both closed, so the milestone cannot land with its city untested.

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

- **Build notes** (binding for the runner; design notes, waterways).
  - *Registry.* FG rows `ww_dump_facts` (the hook text outermost, Nauvis listing the tile, the
    presets' gate, ford key and canals switch, each entry's per-scale pick and no other body naming a
    set), `ww_emit` (two emissions of all 18 files byte-identical, the manifests' hashes, JI-03),
    `ww_t3` (the strait, isthmus and canal oracle rows at Europe's scale 6 in both canal states) and
    `ww_ford` (one Europe ford at scale 6); suite checks `ww_t5`, `ww_fords`, `ww_widths`, `ww_bend`,
    `ww_t1`, `ww_t3_maps` (the oracle rows on every map at scales 1 and 6), `ww_t11`, `ww_m3`,
    `ww_paths`, `ww_v2`, `ww_t7`, `ww_ab`, `ww_t13_m2` (the default preset beside Alien Biomes against
    Alien Biomes alone), `ww_off` (canals off compiles no canal set; the toggles-off budgets rows),
    `ww_t15b`, `ww_maptype_cost` (each map's newest entry picked alone through the Map type route:
    Tile, Entity and Cliff complexity and forced generation against M0 at scale 6 and 16 LP, timed
    and reported, never gated, Contradictions item 15; also in the gate's timed live sample) and
    europe-coast's exploring rows (`walker_m1`, `rt_m1`, `save_m1`), re-timed with waterways in place.
  - *Presets per scale and the oracle's context.* From this milestone an MGS file pinned to another
    startup scale also points the ford key at that scale's ford set (`pin_scale`, as presets.lua
    bakes it), the dump facts expect each preset's gate, ford key and toggles (`expected_pen`), and
    T3's oracle row judges every place under the preset's toggle context (`oracle_context`: canals
    on at default settings), so the canal rows read their `expect_when canals` values; the Map type
    rows' water masks count the ford tile as water on both sides (`ford_colours`), since a Map type
    world has no fords.
  - *Channels and fords.* Every waterway channel check is S4's disc (`nav.connected_disc`: a disc of
    the channel's width stepping between valid centres 8-connected), never `nav.py`'s axis-aligned
    square, which needs a 9.9-tile channel on a diagonal. A ford's banks must be land in the
    reference and the shipped coast fit. It sits on a straight reach whose banks clear the coast
    detail's amplitude (the fit's 3 x 3 minimum, so they are land at every seed) where its interval
    has one, else on the least bending such reach with its rectangle widened by the bend, else where
    its banks come nearest to clearing the detail (`bank_margin_px` in the manifest); T5 counts its
    length along the river's centreline. An interval is skipped only where every position has a
    bank that is water in the reference or the fit; its manifest row says so, `ww_fords` accepts
    that one reason only, and every placed ford must pass (no share of failures is allowed) but the
    marked fords named in `WW_FORDS_EXCUSED` and design notes, which may fail only where a bank reads
    water in the world.
  - *Required basins.* T5's bend criterion names basins for the Dardanelles at every scale and for
    the Rhine, the Garonne and the Little Belt at scale 6. Where the bend rule places none on a map
    that carries the feature, `build_waterways.py` draws one 30 x 30 basin at the shipped polyline's
    sharpest 17-tile stretch, in the feature's own set (`REQUIRED_BASINS`), and `ww_bend` requires
    all of them.
  - *A-1 and the stable hook.* The dump facts' vanilla-prototype check (A-1) accepts a vanilla
    prototype that differs by a stable hook alone (`stable_hook_change`): the ford tile's autoplace
    wrapped in exactly the gated hook text, and Nauvis listing that tile; any other change fails
    (`ww_controls`, in the offline self-tests).
  - *Toggles-off rows.* From this milestone `tests/budgets.json`'s off row of a map some toggle lists is
    measured with every toggle off (`budget_jobs`); a map no toggle lists keeps one measurement.
    The zero-cost comparison (`zero_cost_diffs`) holds operations, registers and the estimate in
    every program and the expression counts outside Tile, in the gate row and the baseline alike.
  - *T1 everywhere.* From this milestone `t1_eval` masks each map's D16 corridors at the row's scale,
    read from the committed manifest, in every T1 row of every milestone.
  - *Cuts as data.* `data-src/waterways/<map>.json` keeps APPROVALS 7's adopted rows whole; its `cuts`
    give per scale the tolerance and the number of rivers carved from the top of the list (the
    plan's cut order); the T16 data-src row holds them to Europe's rivers and raised tolerances.
  - *Spawn moves.* The manifests' `starts` hold each city's move and bank half-planes per scale, and
    `build_waterways.py` emits the same per map as name-free data,
    `prototypes/generated/starts_<map>_v1.lua`: `moves[city][scale] = {dx, dy}` and
    `banks[city][scale] = {{nx, ny, c}, ...}`, keyed by the spawn-city setting's values, the moved
    spawn's side being `nx x + ny y + c >= 0` in world tiles with the moved spawn at (0, 0). They
    join spawn-cities' mechanism under those bodies' next versions, each registered and named by
    every preset: the city fold adds the city's move to its offset (an if() chain over the city
    index and the folded scale, as the spawn bearings are read, so it folds to constants), and the
    spawn lake and the start mask multiply by the city's half-planes (constants per city and scale,
    so no waterway set enters Entity). `ww_t7` selects each city through the preset's per-save city
    number and fails with "spawn moves not wired" until the fold's offset at the spawn equals the
    city's tile plus its move.

### 5. `region-layer` (part 4, order 1)

- **Introduces.** The layer described under "Region layer": rows from the tables, the shared warp and
  roughness, per-row warp shares, the six exclusion rows, hotspot rows at their adopted centres, the
  per-region outputs and the aggregates; `tools/build_regions.py`, which writes the table and holds
  the geometry; the test mod `tools/mods/ea-region-probe`; the oracle's region expectations and the
  strait-end and interior places (`oracle.py regions`).
- **Contract.** Consumers read the interface names only; a static check fails any region formula
  outside `regions.lua` (S10). An approval edit is a table row with no code change (S10: the Spessart
  row added a forest for Entity +30). The layer is firewall-clean (S10 1.6). Runner-up (b), a Voronoi
  of centres, if timing shows the Entity program cannot afford forest outlines (S10 1.7). Its
  allocation is a row of the plan's threshold table (section 6.3: 0 everywhere, since nothing reads
  the layer yet).
- **Gate.** T3 membership (protected features outside at every seed) and locality on sampled
  membership (FEAS-19); T2 per-seed edges (destroyed zone IoU 0.5 to 0.95 between seeds, S10
  measured 0.90 to 0.93; other rows by edge displacement, FEAS-20); T13 switches-off identity; T15.
- **Build notes** (binding for the runner; design notes, region-layer).
  - *Rows.* FG `rl_dump_facts` (every row's bodies and the aggregates in the M1 dump, no copy under
    another name, nothing outside the layer reading its own names, each aggregate reading exactly its
    map's rows, every body registered, firewall-clean, no preset reading the layer yet, with positive
    controls) and `rl_t3_oracle` (Europe at scale 6 at the three seeds); SS `rl_t3_maps`,
    `rl_t2_zone` (seed 1000 repeated on every map at scales 1 and 6, each repeat's every grid and
    hotspot centre equal to the first run's bit for bit), `rl_locality` and `rl_read_cost`; the
    static `regions` row; `rl_runner_controls`.
    The milestone adds no timed row, so its gate's live timed sample is `t15b_m1` on the current build.
  - *Unchanged generation (T13, T15 FG).* The registry marks the milestone `unchanged`, so while it is
    the newest registered milestone (`zero_change_scope`) the FG row `zero_change` requires the 256 px
    preview hashes `tests/baselines/build-<build>.json` records for M0 and every map's preset at
    seeds 1000, 1002 and 1004 to equal main's committed copy (rule 5's comparison with main; a
    changed or missing hash fails, with positive controls), and `t15a_rows` requires every Earth
    row's Tile, Entity and Cliff complexity to equal main's same row, a decrease included. The first
    consumer milestone registered after it retires both comparisons.
  - *The oracle.* A place's `region` expectation is `{key: inside}` over `destroyed` and
    `row:<id>`, from the nominal shapes, with `region_margin_km` (the distance to the nominal edge;
    within 40 km a flip is listed) and `region_hard` (S10's protected features: never listed);
    `oracle.py validate` re-derives them, so they cannot drift from the table.

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
  lands here because AB palms read `elevation` (R3 4.1) and (a) runs with AB from this milestone on, and
  with it the milestone empties each preset's `withheld_with`, so the presets return beside AB. Saves
  made from a preset earlier and loaded beside AB carry `storage.earth.withheld_beside` (the
  europe-coast guard's record) and no palm-switch key: the milestone decides whether such a save keeps
  its palms on the fine field or meets the switch as a seam in palm placement, and records it.
  Recorded (section "Alien Biomes"; design notes 2026-10-29 18:40): such a save keeps its palms on the
  fine field for life, with no seam, and every preset from this milestone on bakes the palm keys with or
  without AB, so a world made without AB that gains it later meets the switch. Palm
  mechanism: the hook form changed M2's default Entity counts, so the fallback ships: preset keys
  `entity:<palm>:probability` and `:richness` holding Earth copies that read `tn_palm_const_v1`
. D11's limit to the adopted AB tiles comes from the gated exclusion hook
  on every non-adopted AB land tile and from climate shaping (aux below AB's alien palette), never
  from a redirect that reads its own property. Marshes read the region layer's `tn_marsh_w` only;
  the moisture lift ships with the AB variant alone (M1's Entity allocation), so on M1 a marsh is its
  Tile-side pools and fringe. The climate's deserts follow EarthMaps' painted sand through the dry
  belts in `config.lua`.
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
  absorption table (a report; no absorption edits). As built: the forests
  are region-layer's rows, read through the key `tn_tree_mult` alone; the startup setting Great
  forests bakes the gate `tn_forests_on` ("1" or "0"); the vanilla texts live in `tables/vanilla.lua`;
  the palms take the boost through second versions of climate-tiles' copies.
- **Zero cost.** The folded hook on every living tree, and beside AB the restored trees and rocks, add
  parsed nodes to every world's Entity program; operations, registers and complexity stay identical, so
  `zero_cost_diffs` compares Entity's parsed counts no longer.
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
- **Build notes** (binding for the runner; design notes, ridges).
  - *Table.* `tools/build_ranges.py` writes `prototypes/tables/ranges.lua` from `approvals-data.json` and
    R7b; the static `ranges` row re-emits it and checks its rows against the approval data (16
    ranges, 54 adopted passes, 53 unnamed gaps, Europe's two edge openings, no pass-free stretch over
    400 km on any map). An approval edit is a data edit and a rerun of `emit`.
  - *Geometry.* One contour at `flank_tiles` 16.37 each side (off the 4-tile lattice), `ramp_tiles` 32;
    an opening is a slot `pass_tiles` 20 along the crest and `reach_tiles` 32 to each side of it (S5's
    calibration: a 16-tile gap gave 16 tiles clear; S9's 20-tile disc gave 3 to 9 at Brenner; the
    draft's T6 read 7.5 at Verecke with 16, at the limit, so 20); an opening at a crest vertex lies
    across the bend's bisector, and one at a crest's end vertex reaches `tip_tiles` 24 past it, so the
    end cap goes with it; an edge opening clears `edge_tiles` 16 along the map's edge within 256 tiles
    of the crossing; the start disc is `max(150, starting_area_radius) + 8`.
  - *Ore clearance.* The Entity program reads each map's crest band, a superset of the tiles whose
    centre lies within `ore_clear_tiles` 24 of a crest built from axis-monotone pieces (3 operations
    per segment), never the exact distance (Entity +3,028 on Europe against the +2,000 allocation);
    the band is read at the tile's centre (`centre_tiles` 0.5 on from the integer corner the program
    samples), where the ore entity stands. The Cliff program keeps the exact distance. No resource
    prototype changes (A-1).
  - *Rows.* FG `rd_dump_facts`, `rd_offline` (no game run: the live sample's P1 call, the registry's
    ratio checks, rd_geo against oracle.place_tile, P2's rule, and the crest band mirror: ridges.lua's
    band pieces ported, every tile centre within `ore_clear_tiles` of a kept crest segment inside the
    band on every map at scales 1 and 6, its term count equal to the M1 dump's band body's),
    `rd_t4_fg` and `rd_t7_fg` (each map's own spawn at seed 1000 and scale 6: 0 cliffs and 0 ridge
    cliffiness within 150 tiles, so the T7 cliff criteria hold in every later gate; its positive
    control is Bern with the start disc redirected to the off body), the static `ranges` and
    `d33_guard` rows; SS `rd_t6`, `rd_t6_start`, `rd_t4`, `rd_t7`, `rd_t8` (every map's preset round
    ranges that exercise both band axes: Europe's Alps, Pyrenees and Carpathians, Atlantic's Andes,
    Rockies and Appalachians, Old World's Himalaya, Urals and Zagros, at scales 1 and 6 and the three
    seeds, with a vanilla-keys control per map), `rd_t11`, `rd_v2` (a 256 px preview at every opening
    of every map that opens it, at scales 1 and 6, listed for the verification pass; V4 is `rd_t6`'s
    dumped-tile render of a ridge with a pass), `rd_t15b` (every map, P1 by the relative rule, P2 on
    M2t/BABt) and `rd_t15e` (a trigger). `rd_dump_facts`, `rd_t4_fg`, `rd_t4`, `rd_t6` and `rd_t15b`
    run M1 against M0 and M2 against BAB: the registry names the m2 dump for ridges, and an M2 half
    whose dumps the dumps row did not produce fails closed. Spawns are set by explicit city offsets in
    a full MGS file, so the rows hold before and after `spawn-cities`' fold. The T1 previews without
    cliffs also turn the ridges off: ridge cliffs never read cliff richness.

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
- **Build notes** (binding for the runner; design notes, resources-enemies).
  - *Table.* `tools/build_hotspots.py` writes `prototypes/tables/hotspots.lua` from `approvals-data.json`:
    the 77 adopted rows keyed by their region rows' ids, strength, biter multiplier, radius and r + 50 km
    cap in reference pixels, land share per map (water share for a field) and each map's frame offset;
    the static `hotspots` row re-emits it and checks it against the region table's hotspot rows.
  - *Hotspots.* One spot noise per resource, each with its own `seed1` (7301 to 7361) and no
    `skip_span`; footprint `min(max(r s, 48), cap s)` tiles round the region layer's jittered centre,
    read through `tn_depth_<id>`; spots start at land candidates (`tn_land_coarse` above -4) inside
    the start disc, min(0.75 R, the disc of 32 candidates), and reach at most the rest of R; 512
    candidates per 512-tile region (1,024 at scale 1); amount = max(strength x vanilla's patch amount,
    15 x vanilla's mean per tile x the footprint's area) x vanilla's distance factor x the ramp, spread
    over the start disc's expected candidates, with the region target the sum of its candidates'
    quantities, so rows sharing a region never draw on each other's target and the land share applies
    in game; fluids keep a well penalty.
  - *Elevation.* Each map's entry v2 wraps v1 in the offshore stamp through the map-qualified fallback
    key `tn_fields_<map>`; v2 carries the Map type fields; geography id 2.
  - *Registration.* The Oil Rig's offshore-oil wrappers exist only beside the Oil Rig: they are in the
    release registry and registered from the M3 dump with the `live` mask (their own expression; the
    Oil Rig text they wrap follows the pack, versioning rule 3), which the frozen row and `freeze`
    produce; `re_dump_facts` pins their locals to the live autoplace in the same dump.
  - *Rows.* FG `re_dump_facts` (with the M2 and M3 isolation walk) and `re_t4_fg`; SS `re_t8`,
    `re_t8_base`, `re_t8_m3`, `re_t4_oil`, `re_t9`, `re_t4` (M0 controls), `re_t7`, `re_t2`, `re_t11`,
    `re_t5` (waterways' T5 checks on this build), `re_t15b` (M1t/M0t and M2t/BABt), `re_explore` (M1/M0
    and M2/BAB), `re_t15e`. T8 reports rows inside vanilla's start fade, inside ridges' ore clearance
    (read in game) or listed for the maintainer, and judges density against vanilla's mean. The offshore
    rows tell field wells from random wells by a hotspots-on and hotspots-off pair, never by geometry, and
    T4 offshore reads frequency inertness from the field bodies' values. Spawns at London by explicit city offsets in full MGS files, which now carry the
    preset's autoplace controls (frequency 0.75) so the MGS and preset routes stay equal (T13).
- **Gate.** T8, T9, T4 ore, enemy and offshore-oil rows (M3), T5 re-run (offshore stamps),
  T7 (a) re-run, T11 hotspots flip, T15 per map; T13 M3 and M5 rows; V4 at a hotspot; V2 offshore
  fields.

### 9a. `edge-and-lakes` (part 6, order 2)

- **Introduces.** Each map's next geography version (Europe's version 6, `tn_geo` 14; Atlantic's and
  Old World's version 5, `tn_geo` 15 and 16, every name its own): its far-field box carries
  the soft map edge (config.lua `coast.edge_band`): inside the extent a second coast, the version's own
  transfer of b = clamp(d / s + warp - 12, -16, 16) reference px, warp = 8 px times three clamped basis
  octaves (32, 12 and 4 px, seed1 7401 to 7403, in geo tiles), so land the box cuts sinks into deep
  water along a wavy coast 4 to 20 px inside the box with a real coast's beach and deepwater profile,
  and the ring of plain water is gone (every box tile is deep). A version with a spawn record and a
  `lakes` field reads its inland lakes through the toggle `tn_inland_lakes` (startup setting Inland
  lakes, default off); the spawn lake is unchanged.
- **Contract.** With the switch on a world equals the previous version's outside the band's T1 mask;
  with it off it equals that world with the inland lakes body neutral. T1 masks reference land within
  `mask_px` (21) of the box on every map whose newest version carries the band and reports
  `edge_band_share`; `coast-band-fix` must leave that mask alone (its handler skips it as it skips the
  waterway, lake and dam masks), or it would rebuild the straight cut.
- **Gate.** FG `el_dump_facts`, `el_offline` (the band's reach against the nearest uncut land, the mask
  share and a T1 control); SS `el_lakes` (switch off against the neutral lakes body, on against the
  previous version, the spawn window in all three) and `el_edge` (every box-cut land line ends in water
  before the box; beyond the mask the previous version holds); T3's oracle row reads the band at the
  box; spawn-cities' T3 inland-lake rows run with the switch on.

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
  placed at `world = geo - (tn_cx_<map>_v<n>, tn_cy_<map>_v<n>)` (the save's own chain version)
  from the save's table version; no per-chunk event;
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

Items 1 to 9 are settled; each keeps its record. Items 10 to 22 are open.

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
22. **M2 Entity allocation for the restored trees (trees-forests).** Section 6.3's M2 row for
    `trees-forests` budgets rocks and decoratives (+1,000) over the forests; the restored vanilla trees
    cost about +4,000 more on every map beside AB, so the T15a M2 rows exceed the allocation (Europe
    +6,848 against +4,500) while P13's caps hold. Open for a plan revision between parts (decision 3;
    design notes, trees-forests).

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
