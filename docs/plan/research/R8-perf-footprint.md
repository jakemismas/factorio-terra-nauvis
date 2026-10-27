# R8: factory footprints, where map generation runs, and what the world costs during play

Research only: no game runs, nothing committed. Factorio 2.1.23 (build 87750), base game, written
2026-10-27. Feeds P11 (the D3 size context), P12 and section 5 (performance), T5, T6, T9, T10 and T15.

## How to read this

- Tags: `[W:url]` a web page fetched during this run; `[L:path:line]` a local file on this machine (`[L:local ...]` for
  unpublished notes)
  (`%FACTORIO_GAME%` is the Steam install, `%FACTORIO_WS%` the workspace); `[R:path]` an artifact of an earlier harness run on this machine.
- Grades: **CONFIRMED** (a Wube statement, local game data or docs, or a local measurement),
  **REPORTED** (a community post that was fetched), **INFERENCE** (reasoning from cited facts, with
  the reasoning shown), **UNVERIFIED** (a search snippet only, one weak source, or nothing).
- Quotes are as an extraction step returned them and may not be word for word. A first research pass fetched most pages; 13 were fetched again by the
  author ("re-fetched") and agreed on every point used, and 4 were fetched by the author alone
  ("author"). Quotes containing dashes are shortened or paraphrased, as marked.
- 1 tile is 1 m (the wiki's convention); 1 chunk is 32 x 32 tiles.

## Verdicts

### 1. Factory footprints (for the D3 size context)

The citable record is thin. Nobody publishes measured footprints of ordinary bases; what exists is
designers posting the size of compact builds, plus one megabase that stated its map extent.

| Stage | Footprint | Scope | Version | Grade | Source |
|---|---|---|---|---|---|
| First rocket, typical player | none found | | | gap | section 1.3 |
| First rocket, lower bound | 63 chunks (64,512 tiles of area), shape not given | whole base, in a chunk-buying challenge mod | 2.1, modded | REPORTED | [W:https://mods.factorio.com/mod/territorio] |
| About 200 SPM | "5 chunks square", read as 160 x 160 tiles | core with smelting and refinery, no mining | 0.17 | REPORTED, wording ambiguous | [W:https://forums.factorio.com/viewtopic.php?p=465828] |
| 462 SPM (density record) | 162 x 132 tiles | core only (resources and power from outside, inferred) | not stated | REPORTED | [W:https://forums.factorio.com/viewtopic.php?p=513652] |
| 1k SPM | 683 x 813 tiles (about 21 x 25 chunks) | core blueprint, non-beaconed, tileable, no mining | 1.1.101 | REPORTED (site-computed size) | [W:https://factoriobin.com/post/EhaghFV6] (re-fetched) |
| 2.7k SPM | 399 x 786 tiles (about 12 x 25 chunks) | core from raw resources, beaconed, no mining | 0.17 | REPORTED | [W:https://forums.factorio.com/viewtopic.php?p=506746] (author) |
| 5k SPM | none found | | | gap | section 1.3 |
| 9.45k SPM | map spans x -4000 to +6000, y -3000 to +3000: 10,000 x 6,000 tiles (312.5 x 187.5 chunks) | the whole map including every outpost; an upper bound, not built area | 0.17.79, three mods | REPORTED | [W:https://forums.factorio.com/viewtopic.php?p=475463] (re-fetched) |
| 1 rocket defense per minute (0.11) | 6 km x 6 km with 216 ore outposts | whole base | 0.11 | REPORTED, historic | [W:https://alt-f4.blog/ALTF4-13/] |

Read with care. Core footprints vary about 2x with design density alone (the non-beaconed 1k core
is larger than the beaconed 2.7k core), and the only 10k-class number is a 0.17 map extent built
with ore size and richness at 600% (fewer, bigger outposts) and enemies, cliffs and pollution off.
Wording the setting can carry, with a citation per number: "a 1k SPM factory core is about
0.7 x 0.8 km; a 9.45k SPM megabase with all its mining fit in a 10 x 6 km map". Measuring public
2.0 or 2.1 megabase saves in the harness would replace these with numbers taken on this machine
(1.1 saves cannot be loaded, section 1.4).

### 2. Where map generation runs

**The noise hypothesis is half right.** CONFIRMED: chunk generation work runs on worker threads
(parallelised since 0.10.0; FFF #390 "Map generation already runs in multiple threads where
possible"; the 2.1.23 API says forced generation uses "all available threads"; a 4096 px preview
here takes 33.8 s on 1 thread and 3.0 s on 24). Not established: that this makes generation free
for the game update. Four facts point the other way, and no Wube statement settles them:

1. Every peer generates every chunk itself, in lockstep: FFF #415's desync existed only because two
   machines with different core counts generated slightly different chunks (CONFIRMED in effect).
2. Results enter the game at deterministic ticks: a 49-chunk request arrived on the same ticks under
   a full-speed benchmark and a real-time server (CONFIRMED locally). INFERENCE: when workers are
   late, the update must wait for them.
3. The 2.1.23 benchmark reports map generation among the update timings, split into `Prepare`,
   `Compute` and `Apply` phases for tiles and entities (the columns exist, CONFIRMED; what each one
   measures, UNVERIFIED).
4. On this machine forced generation blocks the main thread for 2.5 to 4 ms per vanilla chunk, while
   a preview spends about 0.18 ms of wall time per chunk on 24 threads (both CONFIRMED locally).
   INFERENCE: in-game generation does much more than evaluating noise, and most of the extra does
   not spread across cores.

An `on_chunk_generated` handler runs inside the update on every peer (CONFIRMED in effect by FFF
#415 and by handlers firing synchronously inside forced generation; the main thread is INFERENCE
from the single-threaded update kovarex described). EarthMaps' 2.5 to 3 ms of Lua per chunk is
therefore paid by every peer, inside the update, on top of whatever the engine's own generation
costs there. Dropping the handler removes that cost for certain. How much engine time stays in the
update is the measurement section 5 needs (`mapGenerator*` columns, section 2.8).

### 3. Gameplay lag a worldgen mod controls, ranked

1. **Enemy bases: how many and where.** Chunks with biters stay active "because they have things to
   do (biters to build bases, attack, spawn)" (Rseding91); one player's entity update fell from 8 ms
   to 3 ms after killing all biters. Every attack group is a path request; one 0.17 save had "about
   900 pathfinding requests" queued at once. Ore hotspots carrying dense nests put active chunks and
   attack sources next to outposts.
2. **Water and cliff geometry.** Units collide with water and cliffs (the default unit mask shares
   the `player` layer with both), while shallow and mud water share no layer with it (walkable by
   the masks; the data file's comment names only the character). The pathfinder's chunk layer knows
   water but ignores all entities, cliffs included, so a cliff ridge is invisible to the heuristic
   (FFF #317). Long rivers and ridges mean long detours and failed searches. Per-tick work is capped
   in steps (1000 steps, 8000 work, up to 4x under overload), so detours mostly show as queued,
   slower and failed attacks (INFERENCE; the caps count steps, not milliseconds).
3. **Pollution sinks.** What the cloud crosses decides how many spawners it reaches, and so how often
   attacks are sent. Per tile per second: water 0.000025, grass and dirt 0.000018, sand and red desert
   0.000015 (17% below grass), concrete and landfill 0. A living tree absorbs 0.001 per second, as
   much as about 56 grass tiles. A spawner takes about 20 per 64 ticks, about a thousand times a chunk
   of grass. Deserts with few trees let the cloud run far; forests stop it and soak 10 more per tree
   damage step. Evolution counts pollution produced, not absorbed, so the landscape changes attack
   frequency, not evolution.
4. **Chunk generation during play.** The game generates a 20-chunk radius around every player over
   time; revealing and pollution generate more; every peer does all of it. Lua per chunk multiplies
   this; noise alone keeps it to the engine's own share.
5. **Entity count and save size.** The 32 x 32 chunks around spawn hold 20.5 to 33.1 living trees per
   chunk in vanilla (measured here); great forests raise that. A local water-off map saved 23% larger
   than the same map with water. Save size drives autosave pauses and join time.
6. **Decoratives cost frames, not updates.** GPU load when zoomed out (FPS); UPS was unaffected in
   every report found. About 270 per chunk in one local sample.

## 1. Factory footprints (question 1)

### 1.1 What was found

- **9.45k SPM, Bored_Mike, 2020.** "This map goes from x=-4000 to x=+6000, y=-3000 to y=+3000."
  The base "will do 9450 spm (non-military), uses about 850 trains and about 70k bots". Mods:
  Nanobots, Power Armor MK3, Advanced Solar. Settings: iron, copper, stone and coal "Frequency =
  50%, Size = 600%, Richness = 600%", "No Cliffs", "No Enemy bases", "No Pollution". Version
  0.17.79. A search summary of the thread says the whole map was revealed before building, so the
  extent is the map, not the built area (UNVERIFIED detail). DERIVED: 60 million tiles is 58,594
  chunks, about 0.16 SPM per chunk over the whole map.
  [W:https://forums.factorio.com/viewtopic.php?p=475463] (re-fetched)
- **2.7k SPM core, Neutrality, 2020.** "Mega-base-in-a-box, 2.7k of all 7 sciences/min from raw
  resources, no bots, vanilla 0.17"; "Dimensions: 399x786 (313,614 tiles)". Mining is outside; the
  post lists "Creative mode" and "Bottleneck" as design-time mods.
  [W:https://forums.factorio.com/viewtopic.php?p=506746] (author)
- **1k SPM core blueprint.** "Non-beaconed MegaBase", "Tileable 1k Science Per minute", size field
  "683 x 813", Factorio 1.1.101, posted "3 years ago"; mining, smelting and power contents are not
  described. [W:https://factoriobin.com/post/EhaghFV6] (re-fetched)
- **462 SPM density record.** "6 science: 462spm ÷ (162m × 132m) = 21.60kspm/km^2".
  [W:https://forums.factorio.com/viewtopic.php?p=513652]
- **200 SPM compact, Khagan, 2019.** "It all fits in 5 chunks square, including smelters and
  refinery."; ore, coal, oil and water arrive from outside. It was fetched twice, independently.
  [W:https://forums.factorio.com/viewtopic.php?p=465828]
- **First rocket, lower bound.** Territorio (a 2.1 mod where the player buys chunks): "63 chunks was
  enough to fully automate every pre-space science pack" and "to launch a rocket without ever
  building nuclear power." [W:https://mods.factorio.com/mod/territorio]
- **Historic.** DaveMcW's 0.11 base: "This 6km-by-6km base shook the community", with "216 trains
  importing ore from 216 resource outposts". [W:https://alt-f4.blog/ALTF4-13/]
- **No dimensions** in: the 1k SPM construction set (map view image only)
  [W:https://forums.factorio.com/viewtopic.php?p=561524], Khagan's 1200 SPM build
  [W:https://forums.factorio.com/viewtopic.php?p=591373], the factoriobench map pages including
  flame_Sla's 10k and 50k maps [W:https://factoriobench.com/], and Alt-F4's mentions of 5.8k, 10k
  and 20k SPM bases [W:https://alt-f4.blog/ALTF4-13/].

### 1.2 Map scale facts that frame the comparison

- The default starting area radius is 150 tiles (`starting_area_radius` 150 at
  `starting_area = 1`, 300 at 2, measured). [L:local research notes]
  Vanilla trees are cleared in a radius of 128 tiles plus a 64-tile border.
  [L:%FACTORIO_GAME%\data\base\prototypes\entity\trees.lua:9-10]
- `map_width` reads 2,000,000 on an unlimited map. [L:local research notes]
  The wiki gives the same limit and puts the border about 200 game-minutes away by train.
  [W:https://wiki.factorio.com/Map_generator]
- Uranium is placed far out on purpose: a 2.0.11 Space Age player found none within 900 m of the
  start, and Rseding91 replied "uranium is intentionally generated far from the starting area. This
  is not a bug." [W:https://forums.factorio.com/viewtopic.php?p=627378]
- The game generates, over time, 41 x 41 chunks (1,312 x 1,312 tiles) around each player (section
  2.6), so an Earth map smaller than that is generated whole by a player standing in it.

### 1.3 Not found

A typical first-rocket base size, any 5k SPM size, outpost distances at first rocket or late game,
charted-area sizes at those stages, any author-stated megabase footprint in 1.1, 2.0 or 2.1, and any
Space Age footprint. Reddit could not be reached (blocked for web search, mirrors down) and no
YouTube descriptions were read.

### 1.4 How to get better numbers

Load public 2.0 or 2.1 megabase saves in the harness and measure the bounding box of player-force
entities, with and without outposts (a scenario run with `--save`, extents written to
script-output). Saves from 1.1 and older are out: "2.1.0 and above cannot migrate saves from
version 1.1 and below" [L:local research notes], which rules out
most published benchmark maps (flame_Sla's 10k page says "Saved with Factorio 1.0.0").
Downloads go to `%FACTORIO_WS%\downloads\<name>\` as untrusted data.

## 2. Where map generation runs (question 2)

### 2.1 Worker threads: CONFIRMED

- 0.10.0 (June 2014): "Parallelised map generation, the hiccups when new part of map is generated
  should be smaller or non-existent." [L:%FACTORIO_GAME%\data\changelog.txt:18153]
- kovarex, 2014: "No, the game updates is ran in single thread." and "Moving the game simulation
  (apart the map generation) to individual threads divided by chunks is not so easy".
  [W:https://forums.factorio.com/viewtopic.php?p=37471]
- FFF #390 (Earendel and Genhis, 2023-12-22): "Map generation already runs in multiple threads where
  possible"; three noise programs per surface instead of one ("tiles, cliffs, entities +
  decoratives"); "fewer noise operations (6'016 → 2'233)"; "25% faster chunk generation on average
  (4.8 ms → 3.58 ms)". The post does not say whether 3.58 ms is per thread or wall time, and says
  nothing about the main thread. [W:https://factorio.com/blog/post/fff-390]
- 2.0.7: "Added automatic splitting of repeated noise expressions into separate procedures which
  increased map generation speed." [L:%FACTORIO_GAME%\data\changelog.txt:4259]
- The 2.1.23 API: `force_generate_chunk_requests` "Blocks and generates all chunks that have been
  requested using all available threads." [L:%FACTORIO_GAME%\doc-html\runtime-api.json, LuaSurface.force_generate_chunk_requests]
- FFF #415 (Rseding, 2024-06-14), section "Deterministic multithreading is hard": "The logic to
  generate chunks 'right now' would attempt to use all of your available CPU cores", which made the
  results depend slightly on the core count, a bug present since July 2017 and fixed in 2.0; "it
  just goes to show that multithreading is hard, deterministic multithreading even more so."
  [W:https://factorio.com/blog/post/fff-415] (re-fetched)
- Oxyd, 2019: "Parallelising anything gamestate-related in Factorio is difficult because of our
  multiplayer design". [W:https://forums.factorio.com/viewtopic.php?p=442901]
- Here, a vanilla 4096 px preview (16,384 chunks) took 33.8 s on 1 thread, 7.7 s on 4, 3.0 s on 24
  and 3.0 s with no flag: about 2 ms of single-thread work per chunk for preview data, 0.18 ms of wall
  time per chunk on all cores. [L:local research notes]

### 2.2 How generated chunks enter the game state

No Wube text describes the hand-off. What is known:

- Generation is paced in ticks, not wall time: a radius-3 request (49 chunks) made at tick 14
  arrived over ticks 45 to 74, on identical ticks under a full-speed benchmark and a real-time
  server; a single request arrived 30 ticks later (not a contract). CONFIRMED locally.
  [L:local reference notes]
  A 2016 report found chart-driven generation ran faster at higher game speed while using 5% CPU,
  and a moderator called that intended. [W:https://forums.factorio.com/viewtopic.php?p=175539]
- The 2.1.23 benchmark lists, in this order: `mapGenerator`, `mapGeneratorBasicTilesSupportCompute`,
  `...BasicTilesSupportApply`, `...CorrectedTilesPrepare`, `...CorrectedTilesCompute`,
  `...CorrectedTilesApply`, `...Variations`, `...EntitiesPrepare`, `...EntitiesCompute`,
  `...EntitiesApply`. [R:%FACTORIO_WS%\previews\research\harness-B\p10-bv-all\stdout.txt:36]
  The wiki calls `--benchmark-verbose` values "Update timings" from the show-time-usage view.
  [W:https://wiki.factorio.com/Command_line_parameters] INFERENCE (unverified): `Compute` is the
  parallel noise work, `Apply` writes results into the map inside the update, and the phases follow
  the chunk statuses (basic_tiles, corrected_tiles, tiles, entities).
- `on_chunk_generated` fires when a chunk reaches status `entities`, with tiles, trees, ore and
  decoratives already placed. [L:local reference notes, Core facts]
- Staff confirmed a 2.0.23 bug where tiles set in the same tick as a forced generation were
  overwritten ("This is now fixed for the next release"); a user's guess of a "processed < 10" cap
  per pass in MapGenerationManager.cpp was not confirmed (UNVERIFIED).
  [W:https://forums.factorio.com/123535]

### 2.3 What costs main-thread time

- **A Lua handler: all of it.** EarthMaps' pattern costs 2.5 to 3 ms per chunk (`set_tiles` 0.56,
  `regenerate_decorative` 0.84 to 1.15, `regenerate_entity` 0.83 to 1.07, building the tile table
  0.22). A tick at 60 UPS is 16.7 ms. CONFIRMED locally. [L:local reference notes, rule 9]
- **Forced generation: all of it, blocking.** 2.5 to 4 ms per chunk of wall time (441 chunks 1.1 s,
  49 chunks 0.2 s), main thread blocked. CONFIRMED locally.
  [L:local reference notes]
  Against the preview's 0.18 ms per chunk on the same machine, in-game generation is 14 to 22 times
  slower per chunk even with every core available (INFERENCE: a large serial part, such as placing
  entities with collision checks, correcting tiles and writing into the map).
- **The engine's own phases during ordinary generation: unmeasured.** The `Apply` and `Prepare`
  columns, and any wait on late workers, are the candidates. No source quantifies them. If they
  carry most of the 2.5 to 4 ms, vanilla exploration already costs the update about as much per
  chunk as EarthMaps' Lua adds (INFERENCE).
- **Side effects of new chunks.** Rseding91 (0.14.7) told a player with `max_expansion_distance`
  raised to 30: "Set it back to the default 7 and you won't get the massive lag from chunk
  generation." [W:https://forums.factorio.com/viewtopic.php?p=208334] The default is 5 in 2.1.23.
  [L:%FACTORIO_GAME%\data\base\prototypes\map-settings.lua:51] INFERENCE: some enemy bookkeeping runs
  per new chunk and scales with the expansion radius.

### 2.4 Multiplayer

- **Every peer generates.** FFF #415's bug needed "two computers with a different number CPU
  cores" (as returned by the extraction step), and boskid reproduced a 1.1.109 desync between an
  i9-14900k and an i7-5820k ("Core of the issue is that when there are multiple chunks generation
  requests forced to complete now"). [W:https://factorio.com/blog/post/fff-415]
  [W:https://forums.factorio.com/113601] CONFIRMED in effect: if the server sent chunks, core counts
  could not desync anyone.
- **Generation-time desyncs keep being fixed**, which only happens if generation is part of the
  lockstep simulation: 2.0.7 "Fixed a desync when setting tiles during chunk generation that resulted
  from force_generate_chunk_requests()". [L:%FACTORIO_GAME%\data\changelog.txt:4879]
- **Join cost grows with the map.** A player on a many-surface modded server reported joiners waiting
  for the map download as the generated map grew. [W:https://forums.factorio.com/viewtopic.php?p=692104] (re-fetched)
- INFERENCE: a slow client must keep up with all generation any player triggers, plus every Lua
  handler, or it falls behind and must catch up.

### 2.5 `on_chunk_generated` runs in the update on every peer

- The docs say only "Called when a chunk is generated." [W:https://lua-api.factorio.com/latest/events.html]
- Handlers fire synchronously inside `force_generate_chunk_requests()` outside `on_init` and other
  chunk handlers. [L:local reference notes]
- FFF #415's desync needed "A mod needed to listen to the chunk generated event and change the tiles
  on a chunk when it happened." [W:https://factorio.com/blog/post/fff-415]
- Rseding91: "You can not queue more chunks to generate during the chunk generated event because it
  leads to potential infinite recursion." [W:https://forums.factorio.com/viewtopic.php?p=583606]
- A non-staff answer: "All clients have to run the exact same code at the exact same time and get
  the exact same result". [W:https://forums.factorio.com/viewtopic.php?p=278216]
- Verdict: runs on every peer, inside the deterministic update (CONFIRMED in effect); on the main
  thread (INFERENCE from the single-threaded update; no explicit Wube sentence was found).

### 2.6 What generates chunks during play

- **Every player, all the time.** "20 chunks distance in each direction around each player is slowly
  generated over time" [W:https://wiki.factorio.com/Chunk] (re-fetched). Rseding91: "far away chunk
  generation was implemented in 0.9.0 so enemies would generate around the player", a counter to "I
  never leave spawn and so no chunks with nests ever generate and I never get attacked"; he promised
  the radius as a utility constant for 2.1 [W:https://forums.factorio.com/viewtopic.php?p=692104]
  (re-fetched), and it shipped: `far_away_chunk_generation_radius = 20`
  [L:%FACTORIO_GAME%\data\core\prototypes\utility-constants.lua:430], listed in 2.1.7 as
  `far_way_chunk_generation_radius` [L:%FACTORIO_GAME%\data\changelog.txt:865]. A user's reading of
  the disassembly: "about 1 chunk per second in a 20-radius around the player", "a minimum of 41x41
  = 1681 chunks per surface" (rate UNVERIFIED). The mod could lower the constant in data, but it is
  global and exists to make nests appear near idle players (design choice, not researched further).
- **Preloading.** "Outside of the visible chunk area, an invisible area of about 3 chunks wide is
  generated as a preloading mechanism." [W:https://wiki.factorio.com/Map_generator]
- **Revealing.** "Players, radars, roboports, spidertrons, and fired artillery shells reveal chunks",
  and chunks are generated "immediately if revealed directly and not yet generated."
  [W:https://wiki.factorio.com/Chunk] (re-fetched) Radars chart a 7 x 7 chunk area about once a second
  and one distant chunk per 33.333 s within 29 x 29 chunks; the page does not say whether scanning
  creates chunks (UNVERIFIED). [W:https://wiki.factorio.com/Radar]
- **Pollution.** "Pollution can generate new chunks if it needs to spread to them."
  [W:https://wiki.factorio.com/Pollution] (re-fetched) Rseding91: "The map size doesn't increase that
  much from pollution unless you change the spread parameters".
  [W:https://forums.factorio.com/viewtopic.php?p=463491]
- **Scripts.** `request_to_generate_chunks` (asynchronous) and `force_generate_chunk_requests`
  (blocking).

### 2.7 `--benchmark` and `--benchmark-verbose`

- From 2.1.23's `--help`: `--benchmark FILE` "load save and run benchmark"; `--benchmark-ticks N`
  default 1000; `--benchmark-runs N` "map will reload after each run"; `--benchmark-verbose timings`
  "comma separated list of timings to output each tick. "all", "timestamp", "entities", as well as
  all other values seen in the debug view are allowed here."; `--threads` applies to "generating map
  previews". [L:%FACTORIO_WS%\notes\harness-proof\factorio-help-2.1.23.txt:64-65,87-105]
  The wiki adds "Update timings" and "Timings are returned in nanoseconds."
  [W:https://wiki.factorio.com/Command_line_parameters]
- Measured here: the run prints `Performed N updates in X ms`, `avg/min/max` and a checksum of
  entities and tiles (not `storage`); `all` gives 112 columns per tick; a list without `entities` or
  `all` crashes 2.1.23; the max of a short run comes from its first ticks; charting never progresses
  under `--benchmark`; the save is never modified.
  [L:local reference notes]
- Columns that matter for this mod: `wholeUpdate`, `gameUpdate`, the ten `mapGenerator*` columns,
  `scriptUpdate`, `pollutionUpdate`, `pathFinder`, `commander`, `chartUpdate`, `entityUpdate`, and the
  `EnemySpawner` and `Unit` entity classes. [R:%FACTORIO_WS%\previews\research\harness-B\p10-bv-all\stdout.txt:36]
- Not headless: `--benchmark-graphics` and `--benchmark-frame` measure rendering, so the harness
  cannot measure FPS costs such as decoratives (fh.py refuses graphical flags).

### 2.8 The test section 5 needs

Same seeds and region, one quiet group: a scenario that calls `request_to_generate_chunks` (not
forced) for a fixed block at tick 1, then `--benchmark-ticks` long enough to drain it, with
`--benchmark-verbose all`. Compare, per tick, `wholeUpdate`, the `mapGenerator*` sum and
`scriptUpdate` for vanilla, EarthMaps and each candidate, plus the tick span over which the chunks
arrive. The hypothesis holds on this machine if a candidate's `mapGenerator*` sum is close to
vanilla's and its `scriptUpdate` is near zero. One 24-thread machine says nothing about a 4-core
client; pinning the process to 4 cores is worth a try (UNTESTED with fh.py).

## 3. Gameplay-time costs driven by world generation (question 3)

### 3.1 Biter pathfinding around water, rivers and cliffs

**What blocks a biter (CONFIRMED, local data).** The default unit collision mask is `player`,
`train`, `is_object`, the same as the character's.
[L:%FACTORIO_GAME%\data\core\lualib\collision-mask-defaults.lua:175,192] Water, deep water and their
green variants carry `player`, so units cannot cross them; `water-shallow` and `water-mud` use a
mask without `player` ("walkable by character but not buildable"), so by the masks units can cross
them too (INFERENCE for biters: the comment names only the character, and whether the pathfinder's
chunk layer treats shallow water as land was not found).
[L:%FACTORIO_GAME%\data\base\prototypes\tile\tile-collision-masks.lua:18-28,42-55]
[L:%FACTORIO_GAME%\data\base\prototypes\tile\tiles.lua:961,1012,1058,1110,1155,1244] Cliffs carry
`player` too. [L:%FACTORIO_GAME%\data\core\lualib\collision-mask-defaults.lua:177] Whether biters can
destroy a cliff was not found (UNVERIFIED). Base-game biters need a contiguous path: 2.0 added
discontiguous pathfinding to the API, but "nothing in the base game currently makes use of it."
[W:https://factorio.com/blog/post/fff-425]

**How the pathfinder works (FFF #317, Oxyd, TOGoS and Klonan, 2019-10-18, re-fetched).** A base
pathfinder finds the real path, and an abstract chunk-level pathfinder supplies its heuristic. The
abstract layer is built from tiles only: "we can ignore all entities and consider the tiles only",
with water impassable and land passable; it is updated on tile changes such as landfill, not on
entities, and its route is "merely as a 'suggestion' for the real search". The motivating case was
artillery aggroing "massive numbers of biters on the far end of a large lake", who then "all try to
pathfind around the lake". [W:https://factorio.com/blog/post/fff-317]
INFERENCE: water of any shape is routed around at chunk level cheaply, while a cliff ridge is
invisible to the heuristic, so the base search must expand nodes along the ridge to find its end or
a pass. No Wube source states this cost difference.

**Budgets (CONFIRMED, 2.1.23 `map-settings.lua`; the runtime docs give the same defaults).**

- `max_steps_worked_per_tick = 1000`, `max_work_done_per_tick = 8000`, multiplied by 2, 3 or 4 when
  more than 0, 100 or 500 requesters wait. [L:%FACTORIO_GAME%\data\base\prototypes\map-settings.lua:144,146,206-207]
  [W:https://lua-api.factorio.com/latest/concepts/PathFinderMapSettings.html]
- In 0.17.59 the default was 100, and Oxyd warned "the higher the value of this setting, the bigger
  the UPS impact of pathfinding will be"; the reporter's UPS fell to about 40 for several seconds,
  "only really" from "the nests on the left side of the bottom left lake" (his save had 10000).
  [W:https://forums.factorio.com/viewtopic.php?p=445926] (re-fetched) INFERENCE: 2.1.23 allows ten
  times the per-tick pathfinding work of the 0.17 default.
- Requests under 100 tiles direct distance are short; a short request over 1000 steps is
  rescheduled as long; short requests get half the steps per tick; 10 requests per tick are accepted
  regardless of length, up to 100 if short. [L:...\map-settings.lua:189-198]
- A search ends when its steps exceed 2000 times the start-to-goal estimate, after at least 2000
  steps; unreachable results go to a negative cache; "If a behavior fails this many times, the enemy
  (or enemy group) is destroyed": `max_failed_behavior_count = 3`. [L:...\map-settings.lua:200-215]
  FFF #121: "Determining that there is no way to get from one point to the other can take quit
  [sic] a considerable amount of time", which is why unreachability is cached.
  [W:https://factorio.com/blog/post/fff-121]

**Reports tying cost to water and cliffs (REPORTED, all 0.14 to 0.18, before or around the current
pathfinder).**

- Oxyd, 0.16.16: biters "pathfinding and since there is a lot of them and there is a large body of
  water between them, it takes a lot of time and possibly fails for a lot of them", and "the
  pathfinder is too busy to give any paths to other biters that want to attack your base".
  [W:https://forums.factorio.com/viewtopic.php?p=333203]
- Oxyd, 0.17.56, on groups "stuck on cliffs": "There are about 900 pathfinding requests currently
  going on in that save.", "The biters you are seeing aren't frozen, they are waiting for a path."
  [W:https://forums.factorio.com/viewtopic.php?p=442901]
- Oxyd, 0.17.54: "they struggled to pathfind around the lakes. Which should be fixed in 0.17.59."
  [W:https://forums.factorio.com/viewtopic.php?t=72985]; the changelog has the fix: 0.17.59 "Fixed
  that biters had difficulty pathfinding around crescent-shaped lakes."
  [L:%FACTORIO_GAME%\data\changelog.txt:9153]
- Rseding91, 0.14.22, on attacking a turret on an island: "This is a current limit of the path
  finding system for biters." (Won't fix). [W:https://forums.factorio.com/viewtopic.php?p=255621]
  Current behaviour toward unreachable island targets: not found (UNVERIFIED).
- The only measured pathfinder times found are from a 0.18.36 grouping bug under artillery aggro:
  "hit 100ms pathfinder with 300ms peak", "running at 4 ups". [W:https://forums.factorio.com/86920]
- Changelog, CONFIRMED: 0.16.21 "Fixed that biters would not be able to path find close to cliffs.";
  0.17.49 "Reduced the UPS impact of a large number of biters trying to pathfind."; 0.17.70 "Fixed
  that biter pathfinding could cause unreasonably large save files."; 1.1.0 "Fixed that biters could
  get stuck trying to pathfind toward spidertron, causing performance issues."; 1.1.6 "Fixed that
  biters sometimes couldn't pathfind near the edge of generated chunks."
  [L:%FACTORIO_GAME%\data\changelog.txt:11928,9429,8794,7201,6853]

No 1.1 or 2.x measurement of pathfinder time against lakes, rivers or cliffs was found. The
`pathFinder` and `commander` columns can measure it here (section 2.7).

### 3.2 Pollution: absorption by tiles, trees and spawners

Local values (CONFIRMED); the wiki's table matches them exactly.

| Sink | Rate | Per chunk per minute | Source |
|---|---|---|---|
| Water tiles (all six) | 0.000025 per tile per second | 1.536 | [L:%FACTORIO_GAME%\data\base\prototypes\tile\tile-pollution-values.lua:4] |
| Grass and dirt tiles | 0.000018 | 1.106 | same file:5-6 |
| Sand and red desert tiles | 0.000015 | 0.922 | same file:7-8 |
| Nuclear ground | half of water, 0.0000125 | 0.768 | [L:...\tile\tiles.lua:26-33] |
| Stone path, concrete, refined concrete, landfill, lab tiles | none defined (0 on the wiki) | 0 | tiles.lua defines no `absorptions_per_second` after line 1960 |
| Out-of-map tiles | 0.0001 | 6.144 | tile-pollution-values.lua:3 |
| Living tree | 0.001 per second | 0.06 per tree | [L:...\entity\trees.lua:6] |
| Dead and dry trees (5 types) | 0.0001 per second | 0.006 per tree | [L:...\entity\trees.lua:7] |
| Spawner (biter and spitter) | 20 plus 1% of the chunk's pollution | about 1,100 or more | [L:...\entity\enemies.lua:174,833] |

- How it works: a chunk's "natural absorption rate per second which is determined by the sum of the
  pollution absorption of its floor"; pollution is "updated per chunk every 64 ticks" and spreads at
  2% per 64 ticks to the four neighbours once a chunk holds 15; spawners absorb "20 + 0.01 *
  [chunk's pollution]" every 64 ticks while the chunk holds more than 20, until they hold "more than
  3 times the amount needed to send the most expensive unit". [W:https://wiki.factorio.com/Pollution]
  (re-fetched) The local property is named `absorptions_per_second`, so whether the spawner's 20 is
  per second or per 64 ticks is UNVERIFIED; it is about three orders of magnitude above a chunk of
  tiles either way.
- 2.0.7: "Greatly increased default tile pollution absorption." [L:%FACTORIO_GAME%\data\changelog.txt:4303]
  The wiki history gives the multipliers (out of map x10, water and nuclear ground x5, the rest about
  x2.5; REPORTED, paraphrased by the extraction step).
- **Deserts absorb less.** Sand and red desert absorb 17% less per tile than grass and dirt, and water
  39% more. The larger lever is trees: one living tree equals about 56 grass tiles. A treeless desert
  chunk takes 0.92 per minute, while trees alone average 1.26 to 2.01 per minute per chunk in the
  32 x 32 chunks around spawn at seeds 1000, 1002 and 1004 (20.5 to 33.1 living and 3.3 to 5.1 dead
  or dry trees per chunk; vanilla, real generation, computed from the stored counts).
  [R:%FACTORIO_WS%\previews\research\harness-C\real-1000\script-output\fhC\count.json and the 1002
  and 1004 runs]
- **Tree damage.** Map settings: `min_pollution_to_damage_trees = 60`,
  `pollution_with_max_forest_damage = 150`, `pollution_per_tree_damage = 50`,
  `pollution_restored_per_tree_damage = 10`. [L:%FACTORIO_GAME%\data\base\prototypes\map-settings.lua:27-30]
  The wiki: above 60 in a chunk, "once per second" trees lose leaves or turn greyer, each step
  absorbs 10 pollution, damage stops once grey plus leaves lost passes 120%, and half of trees stop
  one stage earlier. [W:https://wiki.factorio.com/Pollution] (re-fetched) Leaf loss also lowers the
  tree's continuous absorption (wiki stage values 0.001, 0.00067, 0.00033 and 0 per second; REPORTED).
  `AirbornePollutantPrototype::damages_trees`: "When they do, some amount of pollution is removed from
  the chunk equal to the map's `pollution_restored_per_tree_damage` setting."
  [L:%FACTORIO_GAME%\doc-html\prototype-api.json, AirbornePollutantPrototype.damages_trees]
- **The damage buffer depends on the tree's graphics.** boskid, 2.1.7: damaged planted trees consumed
  "26/m in 2.1.6 but only 13/m in 2.1.7", because they went from "12 variations each with progression
  count of 4" to "8 variations each with progression count of 2"; Rseding91: the amount is "part of
  the tree graphics definitions"; fixed in 2.1.13. [W:https://forums.factorio.com/134307] (re-fetched)
  INFERENCE: Alien Biomes trees buffer a different amount than vanilla trees if their variations have
  other progression counts.
- **Trees cost pollution-update time.** 2.1.18: "Improved performance of pollution update when all
  trees on a chunk no longer accept pollution damage." [L:%FACTORIO_GAME%\data\changelog.txt:188]
  INFERENCE: tree damage bookkeeping is part of the per-chunk pollution update, so forest chunks under
  a cloud cost more update time than bare ones until their trees are spent.
- Whether pollution ever removes vanilla trees, or lets them recover, was not found. 2.1.18 removed
  `PollutionSettings::max_pollution_to_restore_trees` [L:%FACTORIO_GAME%\data\changelog.txt:226],
  which suggests a recovery mechanic was tried in 2.1 and dropped (INFERENCE).

### 3.3 Enemy expansion and attack frequency

**Attacks are bought with pollution (CONFIRMED, local data).** A unit leaves its spawner once the
spawner has absorbed its price: small biter 4, medium 20, big 80, behemoth 400; small spitter 4,
medium 12, big 30, behemoth 200 ("The pollution amount that has to be absorbed by the unit's spawner
before the unit will leave the spawner and attack the source of the pollution").
[L:%FACTORIO_GAME%\data\base\prototypes\entity\enemies.lua:103,346,406,467,518,574,631,688]
[L:%FACTORIO_GAME%\doc-html\prototype-api.json, UnitPrototype.absorptions_to_join_attack]
Groups gather for 1 to 10 minutes; at most 30 groups gather at once and a group holds at most 200.
[L:...\map-settings.lua:107-108,128,132] The wiki: nests "will only aggressively engage the player's
factory if the pollution cloud of the factory reaches a nest", and "Every 1 to 10 minutes (random)
the mustered biters launch an attack." [W:https://wiki.factorio.com/Enemies]
[W:https://wiki.factorio.com/Pollution] FFF #425: "When an attack party is formed, they pathfind
towards the nearest chunk with a locally maximum level of pollution." [W:https://factorio.com/blog/post/fff-425]

**Evolution (CONFIRMED).** 0.000004 per second, 0.002 per destroyed spawner, 0.0000009 per unit of
pollution. [L:...\map-settings.lua:38,40,42] The wiki: "The evolution factor is not increased by the
spreading/absorbed pollution, but by the pollution produced". [W:https://wiki.factorio.com/Pollution]
INFERENCE: the absorption landscape changes how often attacks come, not how fast enemies evolve.

**Expansion in 2.1.23 (CONFIRMED, local data).** Every 10 to 60 minutes
(`cooldown = lerp(max, min, -e^2 + 2e)` on evolution), 3 to 5 chunks beyond existing bases, groups
of 5 to 10 scaled by `8 ^ evolution`, candidate score `1 / (1 + player + base)` from player buildings
within 3 chunks and enemy bases within 6. [L:...\map-settings.lua:45-101] Water limits it: "A chunk
has to have at most this much percent unbuildable tiles for it to be considered a candidate. This is
to avoid chunks full of water to be marked as candidates." (`max_colliding_tiles_coefficient =
0.8`) [L:...\map-settings.lua:79-81]; the candidate check uses `building_collision_mask`, which
includes `water_tile` ("used by Commander::findNewBasePosition, ExpansionPlanner::isChunkValidCandidate").
[L:%FACTORIO_GAME%\data\core\prototypes\utility-constants.lua:585]

**What 2.1 changed.** 1.1.110 used `max_expansion_distance = 7`, `max_colliding_tiles_coefficient =
0.9`, settlers up to 20 and a 4-minute minimum cooldown (fetched copy of
`wube/factorio-data` 1.1.110). 2.1.7: "Reworked enemy expansion planner to reduce expansions in
already infested areas.", added `min_expansion_distance`, and "Biter/spitter spawners will emit a
cloud of damaging acid if they are blocked from spawning units."
[L:%FACTORIO_GAME%\data\changelog.txt:657,822,692] FFF #445 (Klonan, 2026-08-07, re-fetched): "The
expansion planner time between expansions didn't scale with the number of candidates", the rewrite
gives "significantly fewer candidate chunks" placed "close to open areas or areas the player has
cleared before"; "the bases will start smaller (from 20 down to 10), but scale to the same max size
of 80"; "Expansion groups are generally bigger but less frequent." [W:https://factorio.com/blog/post/fff-445]
Caution: the 2.1.23 runtime docs still list the 1.1 expansion defaults (settlers up to 20, a
14,400-tick minimum cooldown), so take defaults from `map-settings.lua`, not the docs.
[W:https://lua-api.factorio.com/latest/concepts/EnemyExpansionMapSettings.html]

### 3.4 Entities, save size, autosave and joining

- **Active chunks.** "To reduce computation, entire chunks are set inactive when nothing important is
  happening in them. Chunks with only fish or idling enemies may be set inactive"
  [W:https://wiki.factorio.com/Chunk] (re-fetched). Rseding91 on many active chunks far from a base:
  "They're active because they have things to do (biters to build bases, attack, spawn)." The
  reporter's entity update fell "from 8ms+ to 3ms" after killing all biters; the cause was a mod
  shrinking biter collision boxes so "a lot of biters got stuck inside rocks, cliffs and nests".
  [W:https://forums.factorio.com/viewtopic.php?p=439811] (re-fetched) 2.1.7: "Remote view will activate
  chunks when zoomed in, so biters and fish move around." [L:%FACTORIO_GAME%\data\changelog.txt:670]
- **Idle world entities.** Rseding91: tree stumps (corpses) are "only updated once every 195 ticks",
  and the debug count is "the total number of updatable entities that exist in the world".
  [W:https://forums.factorio.com/viewtopic.php?p=299885] No Wube statement says living trees, rocks
  or cliffs are outside the update set (INFERENCE that they cost memory and save size, not UPS;
  UNVERIFIED).
- **Save size and RAM.** Rseding91 on a 0.13 map with over 10 million decorative entities: "The save
  file alone takes 4.2 GB of RAM to load". [W:https://forums.factorio.com/viewtopic.php?p=200815]
- **Local save sizes (existing artifacts, not a controlled test).** Seed 1004, the same four generated
  windows: vanilla 4,249,659 bytes; cliffs off 4,243,305; trees, enemies, water and cliffs all off
  4,161,035; water off (all land, 29% more trees in the windows) 5,212,631, so 23% larger.
  [R:%FACTORIO_WS%\previews\research\harness-C\real-1004\scenario.zip and the real-nocliffs-1004,
  real-bare-1004 and real-nowater-1004 runs] INFERENCE: land carrying trees and nests costs save
  bytes, water and bare land little; separating trees, enemies and decoratives needs a controlled run.
- **Autosave and join.** The wiki says save time "is not related to UPS"
  [W:https://wiki.factorio.com/Tutorial:Diagnosing_performance_issues], but in multiplayer "Autosaves
  in multiplayer are performed at the same time by all clients" (0.11.17), and since 0.14 the server
  does not wait for slow clients [W:https://wiki.factorio.com/Multiplayer]. Non-blocking saving
  exists on Linux only (search snippets, UNVERIFIED). INFERENCE: on a Windows host each autosave
  pauses play for its duration, which grows with save size.

### 3.5 Decoratives: frames, not updates

- FFF #157 (kovarex, 2016-09-23, re-fetched): as entities "there could be tens of millions of these on
  big maps", "which can multiply the size of the save and ram required to hold it"; the new form takes
  "3 bytes of memory per decorative instead of approximately 300 bytes when it exists as an entity",
  "saved per chunk in a very compressed format", planned for 0.15, and entity searches would no
  longer "iterate through tons of these decoratives uselessly." [W:https://www.factorio.com/blog/post/fff-157]
- 0.16: "When decoratives are on, my GPU usage goes from 10% to 100% and my FPS drops to ~35-40 when
  zoomed out." and "UPS is fine"; posila added "Separate lower object atlas", which "On most GPUs this
  will lower GPU load when drawing lots of decoratives", at the cost of "higher CPU usage in
  rendering". [W:https://forums.factorio.com/viewtopic.php?p=329412] (re-fetched)
- 2.1.7: a Vulcanus draw-call regression from decoratives when zoomed out; Rseding91 "Nothing has
  changed about rendering decoratives in 2.1." and later "it's now fixed for the next release".
  [W:https://forums.factorio.com/134118]
- Local count: script-painted lab chunks regenerated to 32,734 decoratives and 2,029 trees over 121
  chunks, about 270 decoratives per chunk. [L:local research notes]
- The 2.x storage format and per-decorative size were not found. The harness cannot measure FPS.

### 3.6 Map size and per-chunk updates

- Pollution and enemies work per chunk: "Pollution and spores are calculated and spread on a chunk
  basis.", "Enemy expansion is calculated on a chunk basis.", "Enemy pathfinding works in multiple
  stages, and the first stage is chunk-based." [W:https://wiki.factorio.com/Chunk]
- Radars cost chart time: "Related to refreshing chunks of your map, usually done by radars."
  [W:https://wiki.factorio.com/Tutorial:Diagnosing_performance_issues]
- No Wube statement was found that generated but idle chunks cost no UPS, or on how the pollution
  update scales (polluted chunks or all chunks). INFERENCE from the inactive-chunk rule: idle
  generated chunks cost memory, save time and join time rather than update time.

## 4. What this means for the Earth mod

Ranked by expected effect on play, each with the check that settles it. All are INFERENCE from the
sections above unless marked.

1. **No `on_chunk_generated` handler.** It is the only per-chunk main-thread cost that is certain,
   and every peer pays it (2.3, 2.5). Keep script to one-time work, and push anything per-chunk that
   survives into a budgeted per-tick queue. Check: section 2.8. Other mods in the maintainer's pack keep their
   own chunk handlers whatever this mod does: an RSO-style placement probe cost about 0.8 ms per chunk
   [L:local reference notes], and
   bobenemies swaps the spawners in every new Nauvis chunk from `on_chunk_generated`
   [L:local research notes].
2. **Nest density and placement are the largest play-time lever.** Active chunks, attack sources,
   path requests and expansion all scale with nests (3.3, 3.4). Hotspot nests next to outposts raise
   all four at once. Check: a long benchmark with pollution on, comparing `entityUpdate`,
   `EnemySpawner`, `Unit`, `commander` and `pathFinder` against vanilla at equal distance (T9).
3. **Rivers and ridges are biter walls.** Deep-water rivers cannot be crossed by biters (3.1), so a
   river that cuts the land forces every attack from the far side to path around its source, or to
   fail and be cached as unreachable; a river reaching the sea at both ends makes an island that
   biters cannot path across at all. Cliff ridges are walls the chunk-level heuristic cannot see.
   Passes (T6) bound ridge detours. For rivers the trade-off is open: shallow-water fords would let
   biters (and players) cross, but may break Cargo Ships navigability (T5, R4's question). Check:
   `pathFinder` time and failed-path counts with nests behind a river, behind a ridge, and on open
   ground.
4. **Climate is a pollution and difficulty lever.** A tree-poor Sahara lets the cloud run far and
   reach more nests; a great forest stops it and soaks 10 per damage step, at some pollution-update
   cost while its trees take damage (3.2). Vanilla and Alien Biomes trees may buffer different
   amounts. Check: cloud extent and attacks per hour from the same factory placed in desert, grass and
   forest (scenario with a fixed polluter, `pollutionUpdate` column, chunk pollution dump).
5. **Forests cost entities and save bytes.** Great forests raise tree counts above the measured 20.5
   to 33.1 living trees per chunk near spawn, and save size drives autosave pauses on a Windows host
   and join time (3.4). Set the T10 budget in trees per chunk and bytes per generated chunk. Check:
   save size after the same generated block, with trees on and off, against vanilla.
6. **Exploration generates for everyone.** Far-away generation (20 chunks around each player),
   preloading, revealing and pollution all generate chunks during play, on every peer (2.6). At small
   Earth scales the whole map may be generated early in a game. Check: section 2.8, plus a count of
   generated chunks after a fixed benchmark span with one idle player.
7. **Decoratives only cost frames.** Keep decorative density at vanilla levels or below in dense
   biomes; this cannot be measured headless (3.5, 2.7).

## 5. Gaps, skipped work and why

- **No game runs, by contract.** Every cost for this mod's candidates is unmeasured; sections 2.8 and
  4 list the runs that would measure them.
- **Footprints.** No typical first-rocket base, no 5k SPM base, no 2.x megabase footprint, no outpost
  distances. Reddit was unreachable (blocked for web search, mirrors down) and YouTube was not
  searched. Public 1.x saves cannot be loaded in 2.1 (1.4).
- **Threading.** No Wube statement on the worker-to-update hand-off, on whether ordinary generation
  overlaps the update, or on what each `mapGenerator*` column measures; the "processed < 10" cap is a
  user's guess.
- **Pathfinding.** No 1.1 or 2.x measurement of pathfinder time against water or cliffs; current
  behaviour toward unreachable island targets unknown; whether biters can destroy cliffs not found;
  the version where `max_steps_worked_per_tick` went from 100 to 1000 not found.
- **Pollution.** The spawner absorption unit (per second or per 64 ticks); whether pollution removes
  vanilla trees in 2.1; 2.x tree and decorative memory sizes; how the pollution update scales.
- **Saves and multiplayer.** Blocking autosave on Windows, the 2.x join flow and catch-up, and whether
  radar scanning creates chunks are UNVERIFIED.
- **Docs drift.** The runtime docs' expansion defaults are stale (3.3); data files win.
- **Search-snippet-only items** were used only where marked UNVERIFIED: the revealed-map detail of
  the 9.45k base, non-blocking saving on Linux.

## Sources

Web, fetched during this run. "re-fetched" means fetched in the first pass and again in a check, with agreement; the rest were fetched once.

| Source | Author, date | Used for |
|---|---|---|
| https://forums.factorio.com/viewtopic.php?p=475463 "9.45K SPM Megabase (mostly belts and trains, some bots)" (re-fetched) | Bored_Mike, 2020-01-26 | 1.1 |
| https://forums.factorio.com/viewtopic.php?p=506746 "Mega-base-in-a-box, 2.7k of all 7 sciences/min from raw resources, no bots, vanilla 0.17" (author) | Neutrality, 2020-08-15 | 1.1 |
| https://factoriobin.com/post/EhaghFV6 "Non-beaconed MegaBase" (re-fetched) | anonymous, 1.1.101 | 1.1 |
| https://forums.factorio.com/viewtopic.php?p=513652 "Challenge: maximize research density" | pichutarius, 2020 and 2021 | 1.1 |
| https://forums.factorio.com/viewtopic.php?p=465828 "Compact 200 spm (0.17)" (fetched twice) | Khagan, 2019-11-12 | 1.1 |
| https://forums.factorio.com/viewtopic.php?p=591373 (Compact 1200 spm, no dimensions) (author) | Khagan, 2023-09-14 | 1.1 |
| https://forums.factorio.com/viewtopic.php?p=561524 "1K+ SPM from raw material Megabase Construction Set" | AlienRaven, 2022-02-11 | 1.1 |
| https://mods.factorio.com/mod/territorio "Territorio" | Lecheric, 2026 | 1.1 |
| https://alt-f4.blog/ALTF4-13/ "Alt-F4 #13 - Megabase Archaeology" | stringweasel, 2020-11-13 | 1.1 |
| https://factoriobench.com/ and its flame_Sla 10k map page | gujarat6, 2026 | 1.1, 1.4 |
| https://wiki.factorio.com/Map_generator | wiki, edited 2026-09-09 | 1.2, 2.6 |
| https://forums.factorio.com/viewtopic.php?p=627378 "[2.0.11][SA] Uranium ore patches placed >1km away from starting area" | kubel34, Rseding91, 2024-10-28 | 1.2 |
| https://forums.factorio.com/viewtopic.php?p=37471 "Multithreading question" | kovarex, 2014-07-23 | 2.1 |
| https://factorio.com/blog/post/fff-390 "Friday Facts #390 - Noise expressions 2.0" (author) | Earendel, Genhis, 2023-12-22 | 2.1 |
| https://factorio.com/blog/post/fff-415 "Friday Facts #415 - Fix, Improve, Optimize" (re-fetched) | Rseding, 2024-06-14 | 2.1, 2.4, 2.5 |
| https://forums.factorio.com/113601 "[1.1.107] Desync when using request_to_generate_chunks" | boskid, 2024-06-13 | 2.4 |
| https://forums.factorio.com/123535 "[2.0.23] LuaSurface::force_generate_chunk_requests() works differently than advertised" | Quezler, Rseding91, 2024-12-02 | 2.2 |
| https://forums.factorio.com/viewtopic.php?p=175539 "map generation speed depends on game speed" | 2016 | 2.2 |
| https://forums.factorio.com/viewtopic.php?p=208334 "[0.14.7] Map generation runs when not near edge of map" | Rseding91, 2016-09-20 | 2.3 |
| https://forums.factorio.com/viewtopic.php?p=583606 "[1.1.80] asking to generate chunks while forcing chunk generation fails" | Rseding91, 2023-04-02 | 2.5 |
| https://forums.factorio.com/viewtopic.php?p=278216 "Can someone explain what "client" executes on_events?" | Nexela (non-staff), 2017-05-19 | 2.5 |
| https://lua-api.factorio.com/latest/events.html | Wube, 2.1.23 | 2.5 |
| https://forums.factorio.com/viewtopic.php?p=692104 "Configurable Player::generateFarAwayChunks" (re-fetched) | zhuyifei1999, Rseding91, 2026-05-06 | 2.4, 2.6 |
| https://wiki.factorio.com/Chunk (re-fetched) | wiki, edited 2026-10-24 | 2.6, 3.4, 3.6 |
| https://wiki.factorio.com/Radar (author) | wiki, edited 2026-10-24 | 2.6 |
| https://wiki.factorio.com/Command_line_parameters | wiki, edited 2026-10-23 | 2.2, 2.7 |
| https://factorio.com/blog/post/fff-317 "Friday Facts #317 - New pathfinding algorithm" (re-fetched) | Oxyd, TOGoS, Klonan, 2019-10-18 | 3.1 |
| https://factorio.com/blog/post/fff-121 "Friday Facts #121 - Path Finder Optimisation II" | Tomas, 2016-01-15 | 3.1 |
| https://factorio.com/blog/post/fff-425 "Friday Facts #425 - Behind the legs" | StrangePan, Earendel, 2024-08-23 | 3.1, 3.3 |
| https://lua-api.factorio.com/latest/concepts/PathFinderMapSettings.html | Wube, 2.1.23 | 3.1 |
| https://forums.factorio.com/viewtopic.php?p=445926 "[Oxyd] [0.17.59] Intermittent UPS drop on Biter path finding" (re-fetched) | Hannibal08, Oxyd, 2019-07 | 3.1 |
| https://forums.factorio.com/viewtopic.php?p=333203 "[Oxyd] biters still inactive - pathfinding over landfill?" | Oxyd, 2018-01 | 3.1 |
| https://forums.factorio.com/viewtopic.php?p=442901 "[Oxyd] [0.17.56] Biter groups get stuck on cliffs and go idle" | Oxyd, 2019-07 | 2.1, 3.1 |
| https://forums.factorio.com/viewtopic.php?t=72985 "[Oxyd] [0.17.54] Biters are ideling / not finding way to base" | Oxyd, 2019-07-22 | 3.1 |
| https://forums.factorio.com/viewtopic.php?p=255621 "[14.22] Path finding/general ai bug" | Rseding91, 2017-05-15 | 3.1 |
| https://forums.factorio.com/86920 "[0.18.36] Biters not grouping before attacking" | darklich14, Oxyd, 2020-07 | 3.1 |
| https://wiki.factorio.com/Pollution (re-fetched) | wiki, edited 2026-07-15 | 2.6, 3.2, 3.3 |
| https://forums.factorio.com/134307 "[Genhis][2.1.7] Tree farm pollution mitigation broken" (re-fetched) | boskid, Rseding91, Genhis, 2026-06 to 08 | 3.2 |
| https://wiki.factorio.com/Enemies | wiki, edited 2026-10-09 | 3.3 |
| https://factorio.com/blog/post/fff-445 "Friday Facts #445 - The Biters Bite Back" (re-fetched) | Klonan, 2026-08-07 | 3.3 |
| https://lua-api.factorio.com/latest/concepts/EnemyExpansionMapSettings.html | Wube, 2.1.23 | 3.3 |
| https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/map-settings.lua | Wube | 3.3 |
| https://forums.factorio.com/viewtopic.php?p=439811 "[0.17.52] Many active chunks far outside my base" (re-fetched) | YunoAloe, Rseding91, 2019-07-01 | 3.4 |
| https://forums.factorio.com/viewtopic.php?p=299885 "[0.15.31]Nuke Creates Thousands of active entities" | Rseding91, 2017-07-30 | 3.4 |
| https://forums.factorio.com/viewtopic.php?p=200815 "[0.13.20] Medium sized map has almost 10 million decorative entities" | Rseding91, 2016-08-30 | 3.4 |
| https://forums.factorio.com/viewtopic.php?p=463491 "Disable pollution generating chunks" | Rseding91, 2019-10-29 | 2.6 |
| https://wiki.factorio.com/Tutorial:Diagnosing_performance_issues | wiki | 3.4, 3.6 |
| https://wiki.factorio.com/Multiplayer | wiki | 3.4 |
| https://www.factorio.com/blog/post/fff-157 "Friday Facts #157 - We are able to eat paper, but we don't do it" (re-fetched) | kovarex, 2016-09-23 | 3.5 |
| https://forums.factorio.com/viewtopic.php?p=329412 "[posila][16.0][Windows 10]Decoratives causing excessive GPU usage" (re-fetched) | Thomasnotused, posila, 2017-12 to 2018-01 | 3.5 |
| https://forums.factorio.com/134118 "[2.1.7] Large rendering performance regression on Linux" | SteveofDoom, Rseding91, 2026-06 to 07 | 3.5 |

Local files (read in this run):

- `%FACTORIO_GAME%\data\changelog.txt`: lines 188, 226, 657, 670, 692, 822, 865, 4259, 4303, 4879,
  6853, 7201, 8794, 9153, 9429, 11928, 18153.
- `%FACTORIO_GAME%\data\base\prototypes\map-settings.lua`: lines 27-30, 38-42, 45-101, 107-132,
  144-215.
- `%FACTORIO_GAME%\data\base\prototypes\tile\tile-pollution-values.lua:3-8`;
  `...\tile\tiles.lua:26-33,961,1012,1058,1110,1155,1244`; `...\tile\tile-collision-masks.lua:18-28,42-55`.
- `%FACTORIO_GAME%\data\base\prototypes\entity\trees.lua:6-10`;
  `...\entity\enemies.lua:103,174,346,406,467,518,574,631,688,833`.
- `%FACTORIO_GAME%\data\core\prototypes\utility-constants.lua:430,584-586`;
  `%FACTORIO_GAME%\data\core\lualib\collision-mask-defaults.lua:175,177,192`.
- `%FACTORIO_GAME%\doc-html\runtime-api.json` (LuaSurface.force_generate_chunk_requests) and
  `prototype-api.json` (EntityPrototype.emissions_per_second, AirbornePollutantPrototype.damages_trees,
  UnitPrototype.absorptions_to_join_attack).
- `%FACTORIO_WS%\notes\harness-proof\factorio-help-2.1.23.txt:64-65,87-105`.
- Local research notes on the harness, noise, runtime and mod management (not published).
- Local reference notes on chunk generation, determinism and test runs (not published).

Earlier harness artifacts on this machine:

- `%FACTORIO_WS%\previews\research\harness-B\p10-bv-all\stdout.txt:36` (the `--benchmark-verbose all`
  header).
- `%FACTORIO_WS%\previews\research\harness-C\real-1000`, `real-1002`, `real-1004`,
  `real-nocliffs-1004`, `real-bare-1004`, `real-nowater-1004` (`scenario.zip` sizes and
  `script-output\fhC\count.json`).
