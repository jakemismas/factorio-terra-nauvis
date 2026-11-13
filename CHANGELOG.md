# Changelog

All notable changes to Terra Nauvis are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). The changelog players see in the game is
`terra-nauvis/changelog.txt`.

Versions before 1.0.0 were released from an earlier repository and have no tags here. Names such as `tn_geo 21`
or `tn_enemy_v2` are identifiers in the code: a geography version and a named noise expression.

## [1.2.0] - 2026-11-12

Version 1.2.0 follows 1.1.0. Worlds made with earlier versions keep loading unchanged, their ore included, and the
new ore applies to new worlds only.

### Added

- Lean ore, a new startup option, on by default. Ordinary ore patches hold about 500 thousand ore within 1,000
  tiles of the spawn and at most 5 million anywhere. These amounts are at the default ore sliders and follow each
  ore's size and richness sliders. The starting patches stay the base game's.

### Changed

- Ore hotspots start small near the spawn and grow to their full size from 1,000 to 3,000 tiles out, their extra
  nests with them. Both distances follow the Starting area slider. With Lean ore a hotspot within 1,000 tiles is
  one field of up to 1 million and none stands within 150 tiles of the spawn. With Lean ore off it holds no more
  than the base game's large patch at its distance.
- Full ore hotspots hold up to 50 million at map scale 6, 71 million at 12 and 100 million at 24 with Lean ore, at
  the default ore sliders. With Lean ore off they hold their 1.1.0 size times 1.4 at scale 12 and twice at scale 24.
- Oil hotspots on land follow the same rules as the ore hotspots, with wells as far apart as the base game's. They
  no longer grow with the square of the map scale. Offshore oil fields keep their rule.
- With Lean ore, hotspot fields that touch share one field instead of stacking into one oversized field.

## [1.1.0] - 2026-11-10

Version 1.1.0 follows 1.0.0. Worlds made with earlier versions keep loading unchanged, their Moscow zone
included, and the new terrain applies to new worlds only.

### Added

- The Moscow zone keeps the snow it covers, on new worlds beside Alien Biomes. At Chaos the north snow of the
  North snow setting and the snowy western end of the Caucasus by the Kerch Strait stay snow, the range with its
  grey rim, and the zone meets them through heat ground, black ash and grey rock, with grey rock between the snow
  fields and dead trees on the snow. At Corrupted the blue and purple ground stops wherever the world lays snow,
  and the range keeps its grey rim.

## [1.0.0] - 2026-11-10

Version 1.0.0 follows 0.4.0. Worlds made with 0.3.x and 0.4.0 keep loading unchanged; the new terrain applies
to new worlds only.

### Added

- Great forests have their own ground: on new worlds beside Alien Biomes, the ground inside a great forest turns
  to forest ground and the trees fill in. Older worlds keep their forests.
- River deltas: on new Atlantic and Old World worlds the Nile, Amazon, Niger, Indus, Mississippi, Orinoco and
  Lena deltas fan out into shallow side channels on wet green ground. Older worlds keep their river mouths.
- Deserts in the Middle East: on new worlds beside Alien Biomes, Arabia, the Syrian desert, Mesopotamia and the
  Iranian plateau draw the pale cream sand, broken by patches of older ground, while the Sahara, Sinai, the Negev
  and the Levant coast keep their tan sand. The ranges keep their snow and grey rim. Older worlds keep their
  ground.
- Patagonia as a dry steppe: on new Atlantic worlds beside Alien Biomes, the plains east of the Andes from 30 S
  to Tierra del Fuego draw dry grass and dirt instead of sand. The Andes keep their snow and grey rim. Older
  worlds keep their ground.

### Changed

- With Destroyed Europe on, the snowy ranges inside the zone keep their snow and grey rim on new worlds, and the
  heat ground starts outside the rim.
- With Destroyed Europe on, the ranges the zone encloses, such as the Alps and the northern Apennines, carry
  dead trees where living ones stood, on new worlds. The Pyrenees and the ranges outside the zone keep their
  living trees.
- Koppen biomes was an experiment in 0.4.0 and is shelved: the setting is hidden and off, new worlds use the
  0.3.2 climate, and worlds made with it on keep it.
- Fewer settings: Canals, Exact coastlines, Great forests and Ore hotspot size are now always at their defaults
  (on, on, on and Normal) and no longer show in the mod settings. Worlds made with another value keep it.
- The mod is titled Terra Nauvis: Earth Maps, with a shorter description. The mod ID, every setting name and
  the log and chat prefix stay as they were.

## [0.4.0] - 2026-11-08

### Added

- Koppen climate biomes, on by default: every tile's ground, trees and decoratives follow the Koppen-Geiger
  climate computed for its place on Earth, so deserts, grasslands, forests, taiga and polar ground each read
  as themselves, with Alien Biomes or on the base game alone. Turn Koppen biomes off in the mod settings to
  keep the plain Terra Nauvis 0.3.2 climate.
- One-click world creation: pick a Terra Nauvis preset at the top of the new-game screen and the whole world
  is configured, with no second choice in the Map type dropdown. The Map type entries stay as an advanced path
  and keep older saves loading.

### Changed

- Atlantic past scale 6, on new worlds made from a Terra Nauvis preset: islands the coast fit missed are drawn
  from the reference map and coasts fray at tile scale, with fewer straight runs and right angles, matching
  the Old World. Scales 1 to 6 keep their coasts.
- Chaos zones on new worlds (Destroyed Europe, and the Moscow zone at Chaos): the grey rocky transition
  reaches the zone edge, the black-ash edge frays instead of running straight, and the cold fringe no longer
  shows snow specks or marsh.
- Worlds made with 0.3.x keep loading unchanged; the new terrain applies to new worlds only.

## [0.3.2] - 2026-11-03

### Changed

- Old World past scale 6, on new worlds made from a Terra Nauvis preset: islands the coast fit missed
  (Okinawa, the Visayas, the Solomons, Yapen, the Kurils, Shark Bay and more) are drawn from the reference
  map, the Sognefjord is open from the sea to its inner arms, and the Aral is two basins again without the
  square island. Scales 1 to 6 keep their coasts.
- Old World past scale 6, on new worlds: coasts fray at tile scale, with fewer straight runs and right angles,
  and a world made from the Map type entry alone now gets the same coasts as one made from the preset.
- Old World past scale 6, on new worlds: the Volga's Samara Bend draws as a bend instead of a hook. Every
  other river keeps its course.
- Chaos zones on new worlds (Destroyed Europe, and the Moscow zone at Chaos): the zone fades from heat ground
  through black ash into a grey rocky strip, with no red grass or dry dirt band and no patches of outside
  ground inside the zone under High North snow. Its edges fray at tile level and bend every few dozen tiles,
  so no edge runs straight for a hundred tiles any more, and the Moscow zone's own edge frays as Destroyed
  Europe's does.
- Worlds made on 0.3.1 keep loading unchanged; the new terrain applies to new worlds only.

## [0.3.1] - 2026-11-03

### Added

- North snow setting (Low, Medium, High; Medium by default): on new worlds the snow of northern Eurasia
  reaches about 61 to 64 N at Medium and about 57 to 60 N at High; Low keeps the 0.3.0 line. Iceland,
  Greenland and the Americas keep the 0.3.0 line. The grey square in western Russia near the Valdai Hills is
  gone.
- Moscow zone setting (Normal, Chaos, Corrupted; Normal by default; needs Alien Biomes): Chaos turns the
  region from the Baltic states and southern Finland to the Volga bend and the Black Sea into a Destroyed
  Europe wasteland that fades through ordered bands into normal ground; Corrupted makes it Alien Biomes' blue
  and purple lands like Blue corrupted UK, running straight into the north snow.

### Changed

- Atlantic: Frankfurt and Moscow join the spawn cities (pick them in Spawn city: Atlantic; random still picks
  among the other 50, so a random world keeps its city).
- Old World past scale 6, on new worlds made from a Terra Nauvis preset: coasts from the detailed fit again,
  regrown in Croatia (Krk, Cres, Hvar, Brac and the other islands), at Europe's small islands and at Crozon.
  Scales 1 to 6 keep theirs, and a world made from the Map type entry alone keeps the lean fit.
- Hotspots on new worlds: Marmara, Portland, Sumbawa, Aswan and Collahuasi stand on land now, the small stone
  discs hold their design total and Shuitou moved inland.
- Destroyed Europe on new worlds fades into ordinary ground through ordered, ragged bands: dry dirt, scorched
  red grass and black ash, then heat ground from heat 1 inward; at the Pyrenees it runs up to the massif's
  snow.
- Blue corrupted covers the United Kingdom only on new worlds (setting renamed Blue corrupted UK); Australia
  keeps its own climate.
- Worlds made on 0.3.0 keep loading unchanged; the new terrain and settings apply to new worlds only.

## [0.3.0] - 2026-11-01

### Changed

- Exact coastlines at scales 1 and 2 on new Old World and Atlantic worlds (tn_geo 21 and 22): a tile reads the
  reference blurred and interpolated between pixel centres, moved by the warp tables plus a short tile noise,
  in every K+ pixel. Specks and islets of up to 8 tiles with nothing to join go under.
- River sets of tn_geo 21, 22 and 23 at scales 1 and 2 take a wider bank noise, so each bank wanders on its
  own.
- The spawn lake of tn_geo 21 and 22 takes a third warp row up to scale 2.
- New worlds (tn_geo 21 to 23): biter bases stand scattered instead of in even rows, trees thin out on hotspot
  ore, and Batu Hijau's copper keeps off Lombok.
- Ordinary ore patches on new worlds are vanilla's own again, in size, shape and richness for their distance
  from the spawn, and keep out of ore hotspots. Presets set the ore sliders to 1. Past about 1,000 tiles from
  the spawn they grow richer at half vanilla's pace, and from about 4,000 tiles they stop growing.
- An ore hotspot on new worlds holds three to six times a large ordinary patch at its distance, at most about
  100 million, about 1.75 times as rich per tile as vanilla's ordinary ore, in more bodies for a stronger
  field. Far out it is two to two and a half times as rich per tile as the ordinary ore round it, so far
  fields spread over a district of large bodies instead of a few small rich ones. The map's ore size and
  richness sliders reach hotspots, and the Ore hotspot size setting adds or removes bodies.
- A start with less than nine tenths of vanilla's average coal gets topped up to that average.
- New worlds: the snow line runs north of Russia's main lowland, a spawn in the cold north starts in a
  clearing off the snow, and palms grow on warm Mediterranean shores (with Destroyed Europe on as well).
- With Space Age, the plants and decoratives Terra Nauvis re-lists keep the tiles of the other planets that
  place them.
- New worlds beside Alien Biomes keep its blue and purple trees, plants and ground inside the Blue corrupted
  zone; outside it each blue tile takes a green, brown or orange counterpart.
- At scale 12 on new Old World and Atlantic worlds (tn_geo 21, 22) rivers take a finer warp octave and ford
  ends a finer noise, so banks run straight for shorter stretches; scales 1 to 6 and 24 keep their tiles.
- New worlds: trees and plants beside hotspot ore thin out only where ore lies, not on the band a field's
  wandering outline leaves bare (tn_ore_open_v2, tn_ore_open_plants_v2).
- New worlds: with Destroyed Europe on, great forests inside the zone stand as dead forests
  (tn_destroyed_dead_v2); with Blue corrupted on, Alien Biomes' green and olive plants no longer grow inside
  the blue zone (tn_zone_plants).
- New worlds: marsh pools fray along their edges in tiles (tn_marsh_water_mud_v2), so their shores run
  straight for shorter stretches.
- Inland lakes of the 0.3.0 geography versions (tn_inland_lakes_europe_v6, _atlantic_v3, _olde_world_v3) hold
  a floor off every lake spot, so the shore noise leaves no water specks between lakes (Old World 12 at
  Frankfurt, a 3,072 tile window: 1,157 water bodies of 1 to 4 tiles to 27).
- With Destroyed Europe or Blue corrupted on beside Alien Biomes, the tiles only the zone places (Alien
  Biomes' orange heat bands, black and red sand and dirt; the Blue zone's dirt) absorb pollution like grass-1
  (7.5e-6 a second) and the zone's dead tree copies like tree-01 (0.001 a second), in
  prototypes/zone_look.lua. Grey dirt 6, which also lies outside the zone, keeps its value. A prototype
  change, so saves made before take it.
- Zone recolour (prototypes/zone_look.lua): with a zone on beside Alien Biomes, each light brown or
  dirt-coloured decal and plant of its list (config.lua zone_look.zones) gets a tinted copy, ember red for
  Destroyed Europe and blue-purple for Blue corrupted, which takes the original's probability inside the zone
  behind the zone's key while the original keeps it outside. Spawner and worm creep (zone_look.creep) gets a
  copy per zone in every spawn list, kept to the zone's own ground by the collision layers tn_zone_ground and
  tn_off_zone_<id>. Biter Cleanup clears creep by name and does not know the copies.
- With a zone on beside Alien Biomes, its own ground walks at speed 1 and caps vehicle friction at 2 (Alien
  Biomes' heat bands walked at 0.9 to 0.7 with friction 4 to 16; its black and red sand at 0.8), and with
  Space Age the tree farm plant (tree-plant) lists the zones' ground among its plot tiles. Prototype changes,
  so saves made before take them.
- The tooltips of canals, great forests, ridges, hotspots, inland lakes and both zones give each layer's map
  generation cost at Old World 12 beside Alien Biomes (noise program complexity), and the Destroyed Europe and
  Blue tooltips and README rows say what the zone does to speed, pollution and creep.
- Beside Alien Biomes with Space Age, the tree farm plant (tree-plant) lists the vanilla land tiles again
  (Space Age's own list, tiles.vanilla.tiles): Alien Biomes rewrites the list to its own tiles, and Earth
  presets restore vanilla grass, dirt, sand and red desert, where agricultural towers planted nothing.
- With Destroyed Europe on beside Alien Biomes, the zone's ground on new worlds is mostly cracked volcanic
  heat ground with lava pools, without the light grey and red sand patches; the Alps inside it take that heat
  ground instead of brown dirt, and its dead great forests stand half as dense.
- Destroyed Europe on new worlds takes in Jutland and the north German coast while the Danish islands stay
  out, reaches the foothills of the Pyrenees, and takes in Veneto, Friuli and western Istria. The band between
  its heat ground and ordinary land varies in width and breaks in places.
- The grey rims along snow lines, on mountain ranges and in the cold north, are narrow and ragged on new
  worlds and break in places, instead of wide grey bands. Desert ranges such as the Atlas and the Zagros carry
  no snow.
- Biomes on new worlds are about 1.5 times larger: the presets open the Moisture and Terrain type sliders, and
  Alien Biomes' temperature sliders, at 150 percent scale.
- Deserts on new worlds meet grass across a narrower, broken band of dirt. The Namib is a desert; Sicily,
  Greece and Cyprus take grass and dirt instead of sand; the Pacific coast of North America, southern Chile,
  Japan, Korea and eastern Madagascar are greener.
- The snow line across northern Europe and Siberia on new worlds runs at the tree line, about 64 to 70 N, with
  green taiga south of it.
- New worlds have savanna and dry scrub in East Africa, the Karoo, the Cerrado and the Caatinga, a greener
  Pampas and northern Australia, and grass and scrub in California and central Chile instead of sand.
- Great forests grow in Borneo, Sumatra, New Guinea, the Pacific Northwest, the Appalachians and Valdivia, and
  marshes spread in the Sundarbans, the Inner Niger Delta and the Mekong delta, on new worlds of the maps that
  hold them.
- New worlds have ten more mountain ranges with cliff ridges, snow and rock fields on the maps that hold them:
  the Taurus, the Talysh, the Alborz, the Ethiopian Highlands, the Tian Shan, the Altai, the Gobi Altai, the
  Great Dividing Range, the Sierra Nevada and the Cascades. Cliffs on every range stand as walls with short
  breaks, so straight cliff runs are shorter, the Alps, the Pyrenees and the Zagros included.
- Each map keeps only its 0.3.0 geography version, so the game starts about 4.5 seconds faster with a large
  mod pack. Worlds made on versions before 0.3.0 no longer load.
- Ground seams on new worlds fray finely, so grass, dirt, sand and snow meet along ragged edges instead of
  long smooth lines, and inside Destroyed Europe the heat ground frays against its rock.
- With Destroyed Europe on, the zone's light grey sand and red dirt patches are gone on new worlds: they break
  into heat ground and black ash.
- Inland lakes on new worlds no longer fold into L shapes, and fewer small water specks sit beside them.
- At scale 12 on new Old World and Atlantic worlds, rivers meander, so their banks no longer run straight for
  hundreds of tiles, and the ends of fords are rougher.
- New Old World worlds at scales 12 and 24 generate faster: their coast fit costs about 28 percent less, and
  the Thames and Cotentin shores are cleaned up.
- Ore hotspots on new worlds have rougher outlines, and each field's design total is capped by its strength,
  at about 46 to 73 million.
- The first range table's unused ridge bodies are gone, so the game starts a little faster with a large mod
  pack.
- The README describes 0.3.0, with a new map render and in-game shots.
- The Ore hotspot amount setting is now called Ore hotspot size, and its values read Small, Normal, Large and
  Huge instead of 50, 100, 200 and 400 percent; the values themselves are unchanged.
- The new setting Regional scarcity, Medium by default, makes ordinary ore patches on new worlds rarer outside
  the regions where each resource is found on Earth, from about 1,500 tiles from the spawn at scale 12: whole
  patches drop out, uranium and oil most, stone least, and the patches that remain keep their size. The start
  and the hotspots stay the same.
- The snow on the old ranges of new worlds frays at its edges like the new ranges' snow, so southern Norway's
  massif loses its long straight eastern edge.

## [0.2.0] - 2026-11-01

### Added

- Map scales 12 and 24. Each geography version carries its own scale list, so released versions keep 1 to 6.
  Europe serves the new scales through an entry of its own on its released chain, with no new tn_geo.
- The startup setting Blue corrupted UK and Australia, default off, needs Alien Biomes. Tiles take a class per
  tile. Trees and plants follow Alien Biomes' own climate boxes through a redirect of temperature, moisture
  and aux inside the zone.
- A second hotspot table for new worlds, built from a sourced list of the world's great deposits
  (`data-src/hotspots/deposits-research.md`): the Pilbara, Shanxi, Kalimantan, the Bowen Basin, Grasberg,
  Olympic Dam, the Witwatersrand, Rumaila and West Qurna and about ninety more. Old World goes from 63 fields
  to 136, Atlantic from 77 to 180 and Europe from 21 to 27.
- A wide field is now a district: its ore stands in many bodies across its footprint, gathered in lobes, where
  it stood in one blob at the centre of an empty disc. Size and richness follow the deposit's rank.
- A hotspot row may set the least its ore footprint reaches at low scales. Grasberg, Kalimantan and South
  Sumatra stand wider than a regular patch at scale 1, and Batu Hijau and Sumatra's Rokan and Pendopo oil
  fields are new rows.
- Hotspot lobes grow with the map past scale 6.
- Nests over a hotspot footprint stand in irregular clusters with gaps, in new worlds. They read
  `tn_enemy_v2`, which replaces the live enemy expression over the footprint, and they keep off wells.

### Changed

- The spawn lake of new Old World and Atlantic worlds takes a gentler warp and a four-row shore noise, so its
  shore has fewer straight runs and right-angle corners. A near-straight stretch of 10 to 12 tiles can remain.
- New Old World and Atlantic worlds draw transitions on the tiles Exact coastlines writes: `set_tiles` runs
  with tile correction from tn_geo 19.
- From scale 3 on those worlds a written coast follows the blurred reference through a warp, in either class
  of K pixel, so it leaves the raster's pixel sides. Written land takes the ground beside it, a shallow tile
  closed in by land takes the land, and written land stays off the spawn lake. Worlds made before 0.2.0 keep
  their coast.
- New worlds with Destroyed Europe read a second outline (`prototypes/tables/zone_outline.lua`) with no start
  cut. Barrier depth counts land edges only, so the zone runs to the shore on sea sides. Its heart is heat
  ground with lava pools, black sand and grey dirt. A data-driven exclusion (`prototypes/zone_exclusion.lua`)
  keeps living trees, palms and coloured plants out, switched on a key saves never hold. Dead tree copies
  carry no tile list. Rock and dead trees thin round the spawn. Worlds made before keep their zone.
- New worlds cap the temperature north of a snow line that follows the real winter line, plain and tile fields
  alike, so Russia and the far north read as frozen snow and ice, with snow trees, behind a band of grey
  wasteland. New worlds without Alien Biomes draw that ground and a massif's snow as
  `terra-nauvis-frozen-ground`, a tile of the mod's own.
- New worlds draw cold ground on a range from one field per crest piece, in place of a reach that follows
  vertex heights and formed a cone on each high vertex, so a massif's width is a share of its range's reach at
  every scale.
- New worlds keep palms south of about 35.5 degrees north, on warm ground off the ranges.
- The palm copies are built at data-final-fixes from the installed palms and held to a digest, so the mod
  ships no Alien Biomes text. `prototypes/generated/palms_ab_v1.lua` is gone, and worlds of every release keep
  their palm bodies.
- New Old World and Atlantic worlds fade a river's warp over the last 36 to 120 tiles to the sea, where the
  first version faded it over 180 to 480 at scale 6 and decided the lower reach of 21 of Old World's 37
  rivers. The Mississippi keeps its long fade for its delta.
- The game's start falls from 6.66 s to 4.01 s on the base game with no tile or entity moved: a heavy term
  read by repeated terms takes a name instead of a local, on the new versions' waterways and the second
  hotspot table. 0.1.2 takes 2.50 s.
- Ground's wandering coast edge is capped so thin inlets stay open, and the Elbe's carved head ends below
  Pardubice on both maps.
- New Atlantic worlds carve all 32 rivers at every scale. The Niger, Mackenzie, Mississippi, Congo, Nile,
  Zambezi, Amazon, St. Lawrence, Parana and Orinoco are routed again from the highest reach EarthMaps draws to
  the sea, through their main stems, with a ford every 60 reference pixels; the Nile follows the Great Bend,
  the Mississippi its own valley and the Congo its arc. Worlds made before 0.2.0 keep their terrain.
- New Atlantic and Old World worlds carry the Rhine, Rhone, Danube, Elbe, Vistula, Dnieper and Po to their
  upper reaches, the Volga too on Old World, each thinning to a stream. Old World's Ob, Nile, Lena, Congo and
  Mekong follow their drawn courses instead of crossing land on straight lines.
- Exact coastlines on those new worlds leaves a lake's rivers to the land, so the Alps lose their blunt heads,
  cut stubs and straight raster reaches, keeps a lake's shore where a river runs through it, and shapes a
  delta up to the river.
- A map's generated waterway files and Exact coastlines tables take versions of their own (`waterway_files` on
  a geography version, `bandfix.generations`), and a save picks its tables by its own tn_geo. `--masks-only`
  and a full band-fix emission write the newest generation only, and the static rows hold every generation's
  tables to the tag.
- New Old World and Atlantic worlds draw new coast fits, for the new-game preview, where the noise coast is
  all that shows. Old World spends 9,360 terms in place of 8,192 for about the same Tile, Europe better in
  every box and the rest of the map much crisper, the Chukotka notch gone. Atlantic spends 10,400 in place of
  8,674 on the Gulf of Guayaquil, the Bahamas, Britain, Ireland, Denmark, the Isle of Man and the Americas.
  Worlds made before 0.2.0 keep their terrain (tn_geo 19 and 20).
- `tools/build_geo.py prune` drops the terms that matter least per Tile, and `fit` takes hold boxes, a
  footprint weight, explicit steps, `--restore` and `--thrift`, so a refit can spend Tile where the fit is
  poor without moving a coast already paid for. `fit` ends its schedule at `--nmax`, `round` rounds a
  checkpoint's coefficients, and a region fit's budget may reach 10,842 terms: the Tile rows bind it.
- Ridges for new worlds are wandering lines instead of the outline of a band: no boxes at scale 1, no ranks of
  parallel flanks, and a range shows its cliff faces. Existing worlds keep their ridges.
- Destroyed Europe, new worlds only: a broad barrier of black ash, red rock and scorched red grass now stands
  between the lava and ordinary land, fraying into it with no clean edge, and the lava is separated patches
  and flows at about a seventh of the land, down from about two fifths. A world made before keeps its zone,
  chunk for chunk.

### Fixed

- On new worlds five fields stand on their real ground: the Kuzbass, Nord-Pas-de-Calais, Hassi Messaoud, Arlit
  and Anshan each sat further from their deposit than their own radius.

## [0.1.2] - 2026-10-31

A patch for a defect 0.1.1 introduced. It only reaches you if you remove or disable Terra Nauvis in a played
world and later add it back. Terrain does not change.

### Fixed

- Removing or disabling Terra Nauvis in a played world and adding it back no longer rewrites land within about
  190 tiles of the spawn or destroys buildings there. 0.1.1 did this on Atlantic and Old World worlds with
  Exact coastlines on, with no warning: a test world on Old World lost 78 of 400 landfill tiles and 25 of 133
  chests. What it already destroyed does not come back, so load a save from before you added the mod back.
- The same steps no longer add start ore to a played world. This affected 0.1.0 and 0.1.1 on every Terra
  Nauvis map.
- A start whose spawn tile lies in a river now gets the start ore guarantee. Before, such a start placed no
  ore patch, as at London on Atlantic at map scale 3. This applies to new worlds.

### Changed

- A tag run of the static rows compares with the earlier releases alone, so main moving on cannot refuse a
  good tag.

## [0.1.1] - 2026-10-30

A patch for existing and new worlds. Terrain does not change: a mid-game save made on 0.1.0 and loaded on this
build shows 0 of 3,694 new chunks differing.

### Fixed

- The game no longer fails to load when an Alien Biomes tile group that Terra Nauvis adopts is disabled.
- The start ore guarantee counts land after Exact coastlines has written it, so a river cannot cut a start off
  from an ore it counted. This applies to new worlds.
- The Exact coastlines drift line no longer says a Map type world follows the setting.

### Changed

- Corrected the Atlantic preset, tooltips and README where they overclaimed.
- `release.yml` runs the static rows, so a commit CI rejects cannot ship.

## [0.1.0] - 2026-10-30

First release of Terra Nauvis, for Factorio 2.1.

### Summary

- Three Earth maps as map-gen presets and Map type entries: Terra Nauvis: Europe, Atlantic and Old World, with
  real coastlines at map scales 1 to 6 in an endless deep ocean. Exact coastlines, on by default on Atlantic
  and Old World, holds every shore to the reference with islets, and written land carries trees and ground
  cover.
- A spawn at a chosen or random city on every map (40, 50 and 33 cities), with land around it, a lake nearby,
  the starting ore and an enemy-free start.
- Waterways: great rivers with walkable fords that narrow with the map scale and carry ships at scale 6,
  straits and canals that ships can sail at every scale, and bays and headlands where a map's frame cuts
  through land.
- Earth climate with or without Alien Biomes, Alien Biomes ground by real region, marshes, 16 great forests,
  and the base game's trees, rocks and plants beside Alien Biomes.
- Cliff ridges along 16 mountain ranges with passes, the only cliffs on a map, and highlands of rocks, stony
  ground, and beside Alien Biomes grey rock and snow. Beside Alien Biomes every Nauvis world's cliffs use its
  grey stone art.
- Regular ore in lobed fields gathered in provinces, historic ore hotspots with heavier biters that ignore the
  map sliders, and offshore oil fields with the Oil Rig mod.
- Options: Canals, Great forests, Ridges, Ore hotspots, Ore hotspot amount, Inland lakes, Destroyed Europe
  with Alien Biomes, Exact coastlines, and City markers on the map view.
- Noise draws almost all of the terrain, so the new-game preview shows the map, with the noise coast. Control
  scripts handle what noise cannot: the start of a new world, the guards and warnings, the city markers and
  the Exact coastlines handler.
- Compatibility: Alien Biomes is optional, Space Age works and its other planets stay as they are, RSO is not
  supported and the game warns when it is active.
- Tooling: the static rows, the frozen body registry, reproducible zips, CI on every push and a release built
  by a `v*` tag.
- Verification before release: one security review pass and the in-game playability checks. No multiplayer
  desync test had run, so 0.1.0 was for single player.

### Added

- Ore hotspot amount startup setting: 50, 100, 200 or 400 percent, default 100. It multiplies hotspot richness
  and nothing else, so no hotspot moves or grows.
- Destroyed Europe grows south and differs every seed: the zone runs from France through Switzerland, southern
  Germany, Austria and Slovenia to Ljubljana and down Italy to about Rome, keeping the old zone's coverage
  north of the Alps. The outline lives in `data-src/approvals/destroyed-zone.json`: 15 vertices, each moved
  per seed by up to its own jitter of 30 to 110 km. Three keep paths (Britain, Denmark with the Kiel Canal,
  the Carpathian crest) replace the six exclusion rows. The random pool skips every city the outline can reach
  at any seed (266 km): 18 of Europe's 40. The heat noise runs at 24 tiles instead of 96.
- Start ore guarantee: `scripts/start_ore.lua`, called once from `start.on_init` on an Earth or Map-type-only
  world, floods the land the spawn reaches on foot (water tiles block, within 160 tiles) and, for iron,
  copper, coal and stone, places one patch of half vanilla's mean starting amount on that land where the
  reached amount within 150 tiles is under half of it (config.lua `start_ore`). It is skipped for an ore
  control at size 0 and with RSO's "Ore in starting area" off; beside RSO it adds only what that start lacks.
  It fixes the ore-starved starts of Stockholm (scales 1 to 3) and Athens (scale 5). No noise body changes.
- Climate grain on all three maps beside Alien Biomes: Alien Biomes' tile scores read frayed copies of
  temperature, moisture and aux through `tn_tile_temperature`, `tn_tile_moisture` and `tn_tile_aux`, each
  adding `noise_layer_noise(19)`, the call that frays grass-1's own edges, outside the temperate band. Every
  base world keeps its program, and trees and decoratives keep the plain fields. It is not free: paired CPU
  reads a median 2.2 percent slower at Frankfurt and 1.5 at Moscow. `climate.grain.maps = {}` in config.lua
  turns it off.
- The list hook: beside Alien Biomes, Earth maps stop walking its long tile restrictions on every vanilla land
  tile. 111 decoratives and 64 trees take the vanilla land tiles at the front of the list and multiply their
  probability by the new body `tn_ab_keep_v1`, 0 where vanilla land may lie, so those tiles add no placement;
  the 13 extended decoratives and 5 dead trees take the same front, order only. Tiles do not move. Decoratives
  and trees only Alien Biomes has lose their placements on adopted tiles and water-mud where vanilla land may
  also lie, and thin along the temperate band's edges: about 7 percent of them over nine edge windows.
- Spawn cities on Atlantic and Old World: their geography version 6 (`tn_geo` 17 and 18) carries the spawn
  city, with the city tables `prototypes/tables/cities_atlantic.lua` and `cities_olde_world.lua` merged by
  `prototypes/city_tables.lua`, the city fold, the spawn lake, start mask version 2, the soft map edge, and
  bearings from `tools/build_spawn.py`. Old World's table moves Prague to the real city and appends Frankfurt,
  Aachen and Moscow. 84 new bodies are registered. `tools/tnlua.py` gains Lua patterns (find, match, gmatch,
  gsub) and seeds data.raw from a reduced copy of the base game's prototypes.
- Map type start: a world made from a Map type entry alone gets the start a preset world gets. `start.on_init`
  reads the city back at (0, 0) through the fold the entry reads, sets the start message with the world size
  at the scale read back there as freeplay's intro, and records the RSO warning; `guards.map_type_geography`
  names the version whose entry the world reads. The cliff reset and the warning without Alien Biomes stay
  Earth-only, and a world that is neither gets nothing.
- Spawn correctness: a world made from the Atlantic or Old World Map type entry alone reads the layer chain's
  offset fallbacks (`tn_cx/cy_<map>_v2`), which now name the city fold, so its offshore stamp sits on the
  spawn's ground (before, the chain was 28,266 tiles off at Frankfurt). Destroyed Europe's random pool is now
  defined for Atlantic (`tn_city_pool_atlantic_v1`) and Old World (`tn_city_pool_olde_world_v1`), and Old
  World's zone list adds Frankfurt and Aachen, which lie inside the polygon: 20 Old World seeds with the zone
  on spawned outside it, and a 400-seed sweep per map picked no zone city.
- Europe's real coastline at map scales 1 to 6: `tools/build_geo.py` emits the coast fit from
  `data-src/fits/europe/` as `geo_europe_v1.lua` (8,192 tents plus a local refit of 66) and
  `land_coarse_europe_v1.lua` (256 tents). The Terra Nauvis: Europe preset bakes `tn_map`, `tn_scale`,
  `tn_geo` and the city offset and holds the water slider's three readers, so the slider moves nothing on a
  preset world. `tn_elevation_europe_v1` puts deep water beyond the 14,400 x 10,224 tiles of scale 6.
  `scripts/guards.lua` adds the Map type notice and the drift line. Twelve bodies are registered.
- Mod skeleton and tooling: the `terra-nauvis` 0.1.0 mod with `prototypes/config.lua` as the single source of
  names and constants, the Map scale startup setting (1 to 6, default 6), the GPLv3 `LICENSE` and a written
  source offer. `tools/build_zip.py` builds byte-reproducible zips, and its `--release` refuses any Earth body
  `tests/frozen.json` does not register. Also the test runner `tools/earth_test.py`, the static rows of
  `tools/tn_static.py`, the lint toolchain (luacheck 1.2.0, luaparser 4.2.0), EarthMaps' reference rasters in
  `data-src/earthmaps/`, and the `ci.yml` and `release.yml` GitHub workflows.
- Spawn at a chosen city on Europe: the startup setting "Spawn city: Europe" (Random, the default, plus 40 of
  the 41 EarthMaps Europe cities), the city table `prototypes/tables/cities.lua` and the city fold
  (`tn_city_europe`, baked per save). The base game's starting ore and enemy-free start follow the spawn
  through the `distance` redirect. A spawn lake lies about 72 tiles out on an inland bearing from
  `tools/build_spawn.py`, land is guaranteed within 16 tiles, and sparse inland lakes come by spot noise (8
  per 1,024-tile region). Also the start message, the RSO warning, `tn_geo` 2 and 20 new bodies (32 in all).
- `tools/tnlua.py` runs the settings and data stages offline, so CI checks registered bodies without the game.
- The Atlantic and Old World maps: the presets "Terra Nauvis: Atlantic" and "Terra Nauvis: Old World", each
  from its own native-resolution fit (Old World 4,096 tents at 0.991420, Atlantic 8,674 at 0.991198). Their
  Map type entries are `tn_elevation_atlantic_v1` and `tn_elevation_olde_world_v1`. `tools/build_geo.py` gains
  `fit`, `curve` and `adopt`. Geography version 1 is `tn_geo` 3 for Atlantic and 4 for Old World, with 22 new
  bodies. The startup settings `terra-nauvis-spawn-city-atlantic` (random plus 50 cities) and
  `terra-nauvis-spawn-city-old-world` (random plus 30) default to random.
- Waterways on every map at every scale: rivers, nine straits and canals, carved by `tools/build_waterways.py`
  from `data-src/waterways/` into 18 generated files. Rivers are `max(7, k x scale)` tiles wide by class (18
  and 12 at scale 6); Gibraltar, Dover and the Great Belt are two-way at 11 tiles. Every river has a walkable
  `water-shallow` ford every 60 reference px, 8 tiles long. The startup setting Canals (`terra-nauvis-canals`,
  default on) covers Kiel and Corinth on every map, Suez on Atlantic and Old World and Panama on Atlantic.
  Atlantic keeps all 32 rivers at scale 1, 24 at scale 2 and Europe's 22 from scale 3.
- The shared region layer that marshes, great forests, hotspots, the biter multiplier and Destroyed Europe
  read by name: 112 rows in `prototypes/tables/regions.lua` (the destroyed polygon with six exclusion rows, 16
  forests, 12 marshes, 77 hotspots), written by `tools/build_regions.py`. Each row's signed distance, weight
  and depth and the layer aggregates (`tn_tree_mult`, `tn_marsh_w`, `tn_hotspot_w`, `tn_enemy_mult` and
  others) are built in `prototypes/expressions/regions.lua` in one region frame for all three maps, with one
  shared warp. 515 bodies are registered. Nothing read the layer yet, so no map changed.
- Earth climate on every preset, after EarthMaps' layout: temperature from latitude with Eurasia's continental
  cold and seven dry belts cut from EarthMaps' painted sand, in an Alien Biomes variant and a fallback without
  it, reached through the presets' `temperature`, `moisture` and `aux` redirects, each the Earth mean plus a
  seeded spread. Beside Alien Biomes the 19 vanilla land tiles are re-listed with a temperate lean and its
  palms move to Earth copies that read a constant (`tools/build_palms.py`). The 12 marshes come from the
  region layer's marsh weight, with water-mud pools on land. `tn_geo` 8 to 10.
- Great forests: the startup setting Great forests (default on, baked per save as `tn_forests_on`) puts every
  living tree's own probability under the hook `if(tn_forests_on > 0.5, min(1, (own) * tn_tree_mult), own)`,
  which Earth presets point at the region layer's multiplier for the 16 forests (boost 2). The base game's
  dead and dry trees are left alone. Beside Alien Biomes the base game's 15 living trees, its rocks and its
  decals are rebuilt from `prototypes/tables/vanilla.lua` and restricted to vanilla land, and the 11 vanilla
  decoratives Alien Biomes takes off Nauvis are re-listed. 85 bodies are registered in `tests/frozen.json`.
- Cliff ridges along the 16 ranges, the only cliffs on a map: `prototypes/tables/ranges.lua` (crest polylines,
  54 passes and 53 unnamed gaps), written by `tools/build_ranges.py`, and the cliff bodies in
  `prototypes/expressions/ridges.lua` in contour units, so the frequency, continuity and richness sliders are
  inert. Openings are 20-tile slots across the crest, and the start disc `max(150, starting_area_radius) + 8`
  is ridge-free. The startup setting Ridges (on; off gives 0 cliffs) is baked per save as `tn_ridges`. An ore
  clearance keeps iron, copper, coal, stone, uranium and crude oil off a crest band.
- Ore hotspots, offshore fields, a richness ramp, sparser base ore and heavier biters inside hotspots:
  `prototypes/tables/hotspots.lua` holds 77 rows (Europe 21, Atlantic 77, Old World 63), written by
  `tools/build_hotspots.py`. `prototypes/expressions/` holds `resources.lua` (one spot noise per resource over
  its rows' footprints, with the ramp `1 + 0.5 clamp((d - 450) / 3550, 0, 1)` on the four solid ores) and
  `enemies.lua` (multiplier 4 inside each footprint). The startup setting Ore hotspots (on) is baked as
  `tn_hotspots`, and ore frequency is 0.75 for the six base resources in every preset.
- Soft map edge and the Inland lakes switch: each map's next geography version (Europe's v6, `tn_geo` 14;
  Atlantic's and Old World's v5, 15 and 16) sinks land the map's box cuts into deep water across a
  noise-warped band 4 to 20 reference px inside the box (config.lua `coast.edge_band`: width 12 px, warp 8 px
  from three basis octaves of 32, 12 and 4 px), so the cut reads as a wavy coastline with a beach and a
  deepwater line. Europe's v6 reads its inland lakes through the per-save toggle `tn_inland_lakes` (startup
  setting Inland lakes, default off).
- The optional Destroyed Europe zone: the startup setting `terra-nauvis-destroyed-europe` (default off), baked
  as `tn_destroyed`, on only with the setting and Alien Biomes. `prototypes/expressions/destroyed.lua` holds
  the zone `tn_destroyed_zone_v1` (a 14-vertex polygon less its six exclusion rows, cut by the start disc) and
  its heat `tn_destroyed_heat_v1` (a heat-1 rim at 100.5 climbing over 61 tiles to a core near 130).
  `prototypes/tables/destroyed.lua` lists the zone cities per map (Europe 7 of 40, Atlantic and Old World
  Prague), and the pool `tn_city_pool_europe_v1` keeps a random spawn off a zone city.
- Exact coastlines, acting on no map yet: the startup setting Exact coastlines (`terra-nauvis-exact-coast`,
  default off) and the per-save switch `tn_bandfix`, which a map's preset bakes only when the setting is on
  and config.lua's `bandfix.maps` lists the map. `scripts/bandfix.lua`, the only per-chunk handler, acts on
  Nauvis alone: it corrects the wrong tiles of the K pixels outside the half-pixel band, never kept water,
  waterway footprints or the spawn keep disc. `tools/build_geo.py emit --bandfix` writes one K+ table per map
  for every scale plus per-scale mask tables in `scripts/generated/`, priced in `data-src/bandfix/`.
- Compatibility and completeness checks, with no new feature: suite rows for a full mod pack, the base game's
  completeness rules, a benchmark against vanilla, EarthMaps and Factorio World, and Space Age
  (`tools/sa_compat.py`). The test-only probe `tools/mods/ea-cc-probe` is new, and
  `tools/mods/ea-sa-probe` gains a wide block set and cargo pod landings.
- City markers and size context: the runtime-global setting City markers (`terra-nauvis-city-markers`, default
  off) and `scripts/markers.lua` draw one rendering object in chart mode per city of an Earth world's map, the
  city's name at the tile holding its reference pixel centre, drawn or removed when the setting changes. Every
  scale label, the scale tooltip and every preset description carry two footprints, a 1k SPM factory core of
  683 x 813 tiles and a 9.45k SPM megabase map of 10,000 x 6,000 tiles. One poster per map comes from
  `tools/contact_sheet.py poster`, 2,400 px wide with a legend and scale bars.

### Changed

- Destroyed Europe turns red: a macro noise over the depth gives a class per tile, so lava, black ash, red
  rock and rim red grass mix with no contour. The heat rises to a mean of 142 and starts 30 px in, so the rim
  keeps the climate's trees. Heat-4 covers 16 to 28 percent of the land sampled.
- Beside Alien Biomes the ground follows Earth's biomes instead of latitude alone (`climate.tile_belts`): the
  Congo, the Amazon and South-East Asia are deep green, the Sahara golden with some red rock, Central Asia and
  the Gobi pale sand and gravel, Tibet cold grey and Greenland white. Orange grass is gone.
- Regular ore patches on Earth presets read as natural mineral fields: lobed outlines with satellites, a few
  large fields among many small ones, gathered in provinces, and a richness plateau with pockets instead of a
  cone. Default worlds are unchanged (`resources.natural`).
- Hotspots listen only to the mod's settings: no map slider reaches them, and size none no longer removes
  them.
- A hotspot's ore never leaves its disc, at any scale, seed or amount; a row's disc is an exact circle of
  radius R about its centre. Regular ore of every kind stays out of hotspot discs and different ores' hotspots
  never interleave, by a test on each spot's candidate, so the rules add almost nothing per tile.
- Hotspot jitter is halved, so a disc stands at most a quarter of its radius off its real site.
- Mountain ranges read as highlands, not as a cliff line on grass: big rocks thicken round each range, clear
  of its passes and of every start; the ground leans to dry dirt, and beside Alien Biomes the tops of tall
  ranges turn to grey ground and snow (`ridges.high`, `ridges.ground`, `ridges.rocks`).
- The map's outline reads as a natural ocean margin: where the box cuts land (Europe's North Africa, Russia
  and Anatolia, and Chukotka on Atlantic and Old World) land ends in bays and headlands up to a few hundred
  tiles deep at scale 6, and every spawn city keeps its ground at every seed (`coast.edge_band.outline`).
- Europe's coast is one crisp line too: its geography reads the fit through the coast warp, which ends the
  dark spray on cold coasts, with a thinner shallow rim. Its land agreement with the reference moves from
  97.68 to 97.65 percent at scale 1 (`coast.warp`).
- The soft map edge's strip holds no flat run on Europe and Atlantic: the warp's sum folds back at its bounds
  instead of clamping there (`coast.edge_band.fold_geographies`).
- On Atlantic, Exact coastlines takes written land from a lattice shared across chunk borders and from the
  chunk's corners, so it draws no rectangles of one tile along chunk borders (`bandfix.smooth.corners`).
- Small marshes on Europe and Atlantic read the shared roughness harder, so the Danube delta's outline is no
  disc edge. No noise call is added and Old World keeps its bodies' values (`regions.marsh.edge_gain`).
- Old World's and Atlantic's coasts are crisp lines: their geography versions read the coast fit at warped
  coordinates instead of adding the lattice detail, which dithered a low-slope fit into a band of speckles up
  to 24 tiles wide, and their shallows narrow to a rim like Europe's (`coast.warp`).
- Beside Alien Biomes, temperate ground keeps the base game's plants: every vanilla decorative and dead tree
  reads the vanilla-scale temperature and the base game's own score where vanilla land lies. Brown asterisks
  no longer carpet the ground outside it (`trees.decor`).
- Exact coastlines acts on Old World and Atlantic and is on by default. Atlantic gains K+ tables. The handler
  queries only wrong tiles and writes along a blurred, wobbling reference instead of the raster's stairs;
  written land takes the ground around it and false islands sink into deep water.
- Land Exact coastlines writes takes the trees, rocks and decoratives of the land beside it, so a written
  coast no longer runs as a bare strip: `scripts/coastcover.lua` reads a rate and a sample from the chunk and
  draws per tile with a generator seeded per chunk.
- `tools/build_geo.py emit --map <map> --bandfix --masks-only` rewrites the mask tables from the committed K+
  table in about a minute, for a change that moves waterways only.
- Exact coastlines holds every shore to the reference alike: the write band narrows from half a pixel to about
  a fifth, K covers every coast pixel, the sea's thin water opens as channels and inlets, and islets the
  raster lost return from a vector coastline (`tools/build_islets.py`, `data-src/bandfix/islets-<map>.json`).
- Beside Alien Biomes, razor edges are gone: a cold spot in temperate land frays; a marsh has no dark rim of
  one width and its edge wanders with the pools; aux folds back at its cap, so dry land keeps its tile mix;
  natural moisture stops at 0.92, so forests fill in instead of ringing a moisture peak.
- Destroyed Europe's start disc has an irregular edge and only widens past its 150 tiles.
- Old World's and Atlantic's vanilla land tiles each add a noise of their own beside Alien Biomes, so dry land
  is a patchwork instead of concentric bands with an even dark rim. Europe keeps its look.
- A river thins to a stream at its source instead of ending in a round finger, on all three maps.
- Beside Alien Biomes an Earth preset's land tiles read two of twelve shared noise fields instead of a
  six-octave noise each, which takes Old World's Tile complexity at scale 6 under the generation cost knee.
  Land and water do not move; patches of Alien Biomes ground fall in new places (`tiles.noise_share`).
- Rivers scale down with the map: a river is `max(3, k s)` tiles wide, k 3 for a major river and 2 for the
  rest, so scales 1 to 3 draw rivers of about 3 to 9 tiles where they drew 11, and only scale 6 still carries
  boats everywhere. A river under scale 4 takes no turning basin.
- Rivers, lakes and turning basins read as natural water: `tools/build_waterways.py` smooths a river by at
  least 12 reference px and draws a basin as a short capsule; `waterways.lua` reads every set through one
  shared warp, so the banks wander. Old World at scale 6 ships 926 river segments against 1,339.
- One geography version per map: Europe v6 (tn_geo 14), Atlantic v6 (17) and Old World v6 (18) stay and every
  superseded version goes. 442 bodies dropped, 18 re-registered, noise text 6.50 MB to 3.55 MB, and time to
  load mods falls from 12.0 s to 2.81 s (vanilla 0.52 s). 36 of 36 previews are pixel-identical.
- Until the first release, `tests/unreleased-moves.json` names every landed record that moved and
  `tools/refreeze.py` writes it with the registry from fresh dumps; the release build excuses a record only at
  a listed hash, and a release tag voids the file.
- The climate noise (temperature, moisture, aux, fallback and Alien Biomes) takes a seed1 shift folded from
  the city offset, so each spawn city of a seed has its own tile texture, at no per-tile cost.
- A startup toggle's drift line for Great forests, Ridges, Ore hotspots and Destroyed Europe says the setting
  applies to new worlds only (`drift-toggle-new-only`).
- The north without Alien Biomes: the fallback climate keeps the boreal belt moist and warm enough for
  vanilla's cold trees up to a treeline near 70N, and the great-forests hook gains a boreal lift
  (`tn_tree_lift_v1`). On Old World at scale 6, seed 1000, sand in Siberia goes from 21.7 to 0 percent.
- Startup: each repeated geography body is defined once per chain class, so the newest version of a class
  keeps the coast fit, coarse land field and waterway sets and every older one names them. The dumped noise
  text drops from 13.5 MB to 5.64 MB and "Time to load mods" from 8.24 s to 3.22 s (vanilla 0.46 s).
- The startup setting Exact coastlines (`terra-nauvis-exact-coast`) is hidden (`hidden = true`, default still
  off, the handler and its tables kept): `bandfix.maps` is empty, so it acts on no map and a visible switch
  would mislead. settings.lua now passes a setting's `hidden` field.
- Old World's coasts of Britain, Ireland, the Channel, Denmark and the Baltic: its coast fit grows from 4,096
  to 8,192 terms with Europe weighted 16 times, so the new terms go to Europe's coasts (Europe box agreement
  0.973 to 0.988, worst coast error in Britain 10.5 to 3.5 px).
- Test runs rely on isolated game instances alone to protect the player's own profile, and
  `tools/build_zip.py --out-dir` takes any folder, the game's mods folder included.
- The test runner's game build pin moves to Factorio 2.1.24 build 87808 after Steam's 2026-10-29 update:
  `tests/baselines/build-87808.json` and `tests/budgets.json` re-measured equal to 2.1.23's in every value,
  with no body re-registered.
- The test runner re-derives the suite evidence of every pending feature before it lands. `tools/oracle.py`
  parses the city table once per file content and `tools/tn_static.py` keeps each Lua file's parse per text,
  which cut the static rows from 66 s to 19 s.

### Removed

- Geography versions 1 to 5 of each map (tn_geo 1 to 13, 15 and 16), start mask version 1, and the chain class
  routing and layer chain redirect that served them.
- The river-safe starts files `prototypes/generated/starts_<map>_v1.lua`: no code read them, and Old World's
  file still held Prague's old grid point and lacked Frankfurt, Aachen and Moscow. `build_waterways.py` no
  longer emits them; the manifests keep each city's per-scale start record.
- The placeholder Terra Nauvis: Europe preset, its two noise bodies, its config group and every placeholder
  text.
- The chained profile guard (snapshot and check, the journal) and `earth_test.py guard-rebaseline`; the
  guard-bracket token that `game_selftest.py`, `dump_render.py run` and `oracle.py probe` checked; and the
  write guards (`tnguard.live_output_problem`, `refuse_live_outputs`) in every tool.
