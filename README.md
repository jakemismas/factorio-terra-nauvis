# Terra Nauvis

Terra Nauvis turns Nauvis into Earth. Pick one of three maps on the new-game screen and play on real
coastlines, with great rivers, forests and deserts where you expect them, and a start at a named city.

Version 0.2.0, for Factorio 2.1.

![The Terra Nauvis: Old World map at map scale 6](docs/images/old-world.jpg)

*Old World at map scale 6, seed 1000, from the game's map preview with the base game's tiles.*

## The three maps

| Preset | What it covers | World size at scale 1 | World size at scale 6 | Spawn cities |
|---|---|---|---|---|
| Terra Nauvis: Europe | Europe from Portugal to western Russia and Turkey, with a strip of North Africa | 2,400 x 1,704 tiles | 14,400 x 10,224 tiles | 40 |
| Terra Nauvis: Atlantic | The whole world but Antarctica, centred on the Atlantic | 15,689 x 6,524 tiles | 94,134 x 39,144 tiles | 50 |
| Terra Nauvis: Old World | Europe, Africa, Asia and Australia | 8,963 x 5,847 tiles | 53,778 x 35,082 tiles | 33 |

Every map sits in an endless deep ocean and comes with:

- Great rivers with walkable fords, and straits and canals wide enough for ships. Rivers narrow with
  the map scale, from about 3 tiles wide at scale 1 to about 12 to 18 at scale 6, the scale ships
  need.
- Earth climate: Russia and the far north under snow and ice with grey wasteland leading in,
  temperate Europe and hot deserts.
- Marshes and 16 great forests, from the Black Forest to the Congo and the Amazon on the maps that
  hold them.
- Cliff ridges along the map's mountain ranges (9 on Europe, 13 on Old World, 16 on Atlantic), with
  passes at their historic crossings. Big rocks and stony ground gather round each range, and
  tall ranges turn to grey rock and snow in whole massifs at every scale.
- Regular ore in lobed fields of many sizes, gathered in provinces, and historic ore fields at their
  real sites, such as Kiruna, the Ruhr and Ghawar, with heavier biters around them.
- A spawn at the city you choose, or a random one, with land around it, a lake nearby, starting ore
  and no biters in the starting area.
- Bays and headlands where a map's frame cuts through land, instead of a straight cut.

![The Terra Nauvis: Europe map at map scale 6](docs/images/europe.jpg)

*Europe at map scale 6, seed 1000.*

## Install

You need Factorio 2.1.24 or newer in the 2.1 series. Space Age is not required.

1. Download `terra-nauvis_<version>.zip` from the
   [latest release](https://github.com/jakemismas/terra-nauvis/releases/latest).
2. Put the zip in your mods folder. Do not unzip it, and keep only one `terra-nauvis_*.zip` there.
   - Windows: `%APPDATA%\Factorio\mods`
   - Linux: `~/.factorio/mods`
   - macOS: `~/Library/Application Support/factorio/mods`
3. Start Factorio, open **Mods**, check that Terra Nauvis is enabled, and confirm.

The release also carries `terra-nauvis_<version>.zip.sha256`, so you can check your download. The
repository's `latest` pre-release is a rolling build of the newest code: it changes on every push,
so use the tagged release to play.

## Start a world

1. In the main menu, open **Settings > Mod settings > Startup**.
2. Set **Map scale**. Scale 6, the default, is the largest world. Each value lists the world size of
   every map.
3. Set the spawn city for your map, such as **Spawn city: Old World**. Random picks a city from the
   map seed. Confirm, and let the game reload.
4. Open **Single player > New game**.
5. In the preset list at the top left, pick **Terra Nauvis: Old World**, or Europe or Atlantic. The
   preview shows the map around your spawn.
6. Press **Play**. The intro names your spawn city and the world size.

Set everything before you press Play. A world made from a preset keeps its scale, spawn city and
every startup setting below for life, and a message tells you when a setting no longer matches,
except Ore hotspot amount, which gives none.

The Terrain tab's **Map type** list also names the three maps. Picking only the map type gives you
that map's coast, rivers and spawn with the base game's climate and none of the rest, and that world
follows later changes to the scale, spawn city, Canals, Inland lakes and Ore hotspots settings,
which moves any terrain it generates afterwards. Use the preset unless you want exactly that.

## Settings

All of these are startup settings except City markers, which is on the Map tab.

| Setting | Default | What it does |
|---|---|---|
| Map scale | 6 | The size of the world: each pixel of the reference map becomes 1 to 6, 12 or 24 tiles. |
| Spawn city: Europe | Random | Where a Europe game starts: Random or one of 40 cities. |
| Spawn city: Atlantic | Random | Where an Atlantic game starts: Random or one of 50 cities. |
| Spawn city: Old World | Random | Where an Old World game starts: Random or one of 33 cities. |
| Canals | On | Opens the Kiel and Corinth canals on every map, Suez on Atlantic and Old World, and Panama on Atlantic, as sea-level channels at least 7 tiles wide that Cargo Ships can use. Off keeps every isthmus closed. |
| Great forests | On | Gives the map's great forests (9 on Europe, 14 on Old World, 16 on Atlantic) about twice the trees of the land around them, and the cold taiga forests more. Trees still follow the climate, so a forest in a dry place stays thinner. |
| Ridges | On | Places cliff ridges along the map's mountain ranges (9 on Europe, 13 on Old World, 16 on Atlantic), the only cliffs on the map, with passes at their historic crossings and a gap at least every 400 km, each wide enough for a double track. No ridge crosses the starting area. Off gives a map with no cliffs. |
| Ore hotspots | On | Adds dense ore at historic sites, across a footprint that moves a little with the map seed, with about three times the base game's biter nests inside it, and offshore oil fields on deep water where the Oil Rig mod is installed. The map's ore sliders do not reach a hotspot, and ordinary ore stays out of its disc. No field lies at a spawn city. Off gives the base game's ore, in the map's lobed fields. |
| Ore hotspot amount | 100 percent | How much ore and oil every hotspot holds: 50, 100, 200 or 400 percent. It changes richness only, never a hotspot's place or size. |
| Inland lakes | Off | Scatters small random lakes across the land, away from coasts and the starting area. Off leaves only the lake at the spawn city, the rivers and the real lakes of the map. |
| Destroyed Europe | Off | Needs Alien Biomes. Turns the heart of Europe, from France across Germany and Poland to Ljubljana and down Italy to about Rome, into a red wasteland: a heart of cracked basalt with lava pools, volcanic rock and dead trees, with patches of black and grey rock, and where the zone meets land a broad barrier of scorched red grass, black ash and red rock that frays into normal ground. It runs to the shore on every coast. All of it can be walked and built on, though the hot tiles slow you down. The outline differs on every map seed and the zone shows red on the map view. Britain, Denmark, the Kiel Canal and the Carpathians stay outside. A chosen spawn city inside the zone starts in it, on cooler ground with its starting ore; a random one never lands inside. Without Alien Biomes nothing changes and the game warns. |
| Blue corrupted UK and Australia | Off | Needs Alien Biomes. Turns the UK and Australia into Alien Biomes' blue and purple lands: mostly mauve grass, with blue grass, purple grass and purple dirt mixed in, and the violet, white and blue trees and plants that grow there. Europe holds the UK alone. In Ireland the zone stops at the border of Northern Ireland, which frays into normal ground. |
| Exact coastlines | On | On Atlantic and Old World it holds a new world's coast to the EarthMaps reference as chunks generate, except beside rivers, straits and canals, in the map's edge band and within 24 tiles of the spawn, so channels and islets narrower than a pixel come back, and land made from sea takes the trees and ground cover of the land beside it. The map preview still shows the noise coast. Europe's map keeps its noise coast, and a world made from a Map type entry alone gets none of this. |
| City markers | Off | Names every city on the map view. It changes nothing in the world, so you can switch it at any time in a running game. Worlds made from a Map type entry alone get no markers. |

## Compatibility

- **Alien Biomes:** optional. With it, the ground follows real regions: deep green rainforests,
  golden deserts, pale sand and gravel across Central Asia, dry yellow steppes, cold grey Tibet,
  a snowbound north and a white Greenland. Temperate Europe keeps its ground, and the base game's
  trees, rocks and plants grow beside Alien Biomes' own. Palms keep to warm, low ground south of about
  35.5 degrees north, so Europe has none. Without it, the base game's tiles follow the climate, and a
  frozen tile of Terra Nauvis's own covers the north and the massifs.
  Destroyed Europe needs it.
- **Grey cliffs beside Alien Biomes:** with Terra Nauvis and Alien Biomes both on, the cliffs of every
  Nauvis world use Alien Biomes' grey stone art: Terra Nauvis worlds, default worlds and older saves
  alike. It changes the look only, and no cliff moves.
- **Space Age:** works, and is not required. Terra Nauvis changes Nauvis only, so the other planets
  generate as they do without it.
- **RSO:** not supported. RSO replaces the map's ore with its own, so you do not get the designed
  start ore, ore hotspots may not match the map, and the preview shows no ore. Where RSO's start is
  short of an ore, Terra Nauvis adds a patch, unless RSO's Ore in starting area setting is off. The
  game warns you at the start and carries on. Turn RSO off to get the designed start.
- **Cargo Ships and its Oil Rig:** straits and canals are wide enough for ships at every scale, and
  carved rivers at scale 6; Known limits says which rivers Atlantic carves. Offshore oil fields
  appear on deep water when the Oil Rig mod is installed.
- **Large packs:** on the v0.1.0 zip, the maintainer's pack of 83 mods, with Space Age, Alien Biomes, Cargo
  Ships, Bob's Enemies, Big Monsters and Dectorio, ran with no errors with RSO off and with it on,
  saved and reloaded clean, and took a version upgrade in the middle of a game with no new chunk
  changing. On an earlier build the pack gave the same world on four separate creates. Those mods
  change ore, enemies and looks, so a world in a pack will not match the previews on this page.

## Known limits

- **Multiplayer is untested.** No two-instance desync test has run, so 0.1.0 is for single player.
- **RSO is not supported for the designed start ore.** With RSO on you get RSO's start, not the one
  the map was built around. Compatibility has the details.
- **The water and cliffs sliders do not change an Earth map.** The coast stays, and ridges are the
  only cliffs. A world started with cliffs at none gets its ridges back beyond the starting area.
  The ore sliders do not reach hotspots. The other map generation sliders work.
- **The new-game preview is small.** No mod can change its size, so it shows only the area around
  the spawn, never a whole map at a large scale.
- **The new-game preview shows blobby coasts.** Exact coastlines is a script that runs as chunks
  generate, and no mod can run a script on that screen, so Old World and Atlantic show their noise
  coast there, coarser than the world you get, most of all away from Europe. The coast refit that
  would improve it waits for a later version. Exact coastlines off leaves that noise coast in the
  world too.
- **Europe's map has the weakest coast of the three.** Exact coastlines does not run on it, so it
  keeps its noise coast, which strays further from the reference than the coasts of Old World and
  Atlantic. Old World gives you a closer Europe.
- **A coast is as fine as its reference.** The reference holds one pixel per 2.5 km or so, at every
  map scale and on every continent, so a written coast follows it to within a tile or two and shows
  nothing finer. Islets under a pixel are drawn a pixel wide. A channel narrower than a pixel opens
  only where the reference shows one, and the coast beside a river or strait keeps the noise's line.
- **Written coast can stay bare in places.** Land Exact coastlines writes copies the trees and ground
  cover of the land beside it. A chunk with no land of its own copies a neighbour, so if that
  neighbour generates later, the new land stays bare.
- **Atlantic worlds made before 0.2.0 keep broken great rivers at scale 3 and up.** New Atlantic worlds
  carve all 32 rivers at every scale, the Amazon, Mississippi, Nile, Congo and six more from their
  upper reaches to the sea. A world made before 0.2.0 keeps its terrain, so there those ten stay short
  pieces. A tributary the reference draws ends a few dozen tiles short of the river it joins.
- **Ships need scale 6 on rivers.** Rivers at scales 1 to 3 are too thin for ships, and scales 4 and
  5 were not checked. At every scale a river thins to a stream at its source.
- **Some shapes still read as computer-made.** Up close a ridge has short hooks, and where it bends hard
  a line can fold into a short gate or near ring. A wide range shows a main line and a side line running
  together. Greenland and Arctic Canada read as long east-west streaks. Worlds made before 0.2.0 keep their
  older ridges, in near-parallel rows, and the Alps' sharper snow seam.
- **A few rivers break for a short stretch.** At some seeds and scales a short upper piece of a river stands
  apart from the rest, the Neman at Atlantic scale 2 and Old World scale 5, the Guadalquivir at Old World scale
  4, the Euphrates or the Neman at some seeds at scale 6. A thin channel opened from the sea can end
  abruptly about 240 tiles inland at scale 6.
- **New chunks cost more than in the base game.** On Old World at scale 6, at Frankfurt, generating
  chunks took 1.054 times as long as the base game, and beside Alien Biomes 1.078 times as long as
  Alien Biomes alone. Moving fast into new land can bring brief stalls. Nothing runs per tick once
  chunks exist. Terra Nauvis also adds a few seconds to the game's startup, about 1.5 more than 0.1.2.
- **Saves keep their terrain.** A world keeps the terrain it was started on. Later releases add
  terrain for new worlds and never change an existing save's terrain. A world made from a Map type
  entry alone still follows the scale, spawn city, Canals, Inland lakes and Ore hotspots settings.
- **An existing save stays as it is.** Adding the mod to a world made without it changes nothing on
  that world's surfaces, apart from the grey cliff art beside Alien Biomes.
- **Testing.** The v0.1.0 zip ran the pack soak: far travel, long simulation, save and load, and a
  run with reloads that matched a straight run to the checksum. It also had a security review of the
  release tools. Scale 6 Old World was the soak's map. Atlantic at scale 4 had one shorter pack run,
  and Europe at scale 6 with Destroyed Europe on had one on the first patch's code. The full timing
  suite has not run on the v0.1.0 zip.
- **Most cities stand where EarthMaps put them.** On Atlantic and Old World a city sits at EarthMaps'
  own map point, which can lie far from the real place it names. Prague, Frankfurt, Aachen and
  Moscow on Old World stand at their real positions.
- **Not on the Mod Portal.** The GitHub release is the only source.

## License and credits

Terra Nauvis is by Jake Mismas, under the GNU General Public License version 3: see `LICENSE` and
`NOTICE.md`, and `terra-nauvis/SOURCE-OFFER.txt` for how to get the source. Its maps derive from
[EarthMaps](https://github.com/HySpeed/EarthMaps) by HySpeed, also GPLv3. Forests, marshes and islets
derive from [RESOLVE Ecoregions 2017](https://ecoregions.appspot.com/) by Dinerstein et al., under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Canal routes use data
(c) [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, under the Open Database
License. Base game expression texts in `terra-nauvis/prototypes/tables/vanilla.lua` belong to Wube
Software and are not under the GPL.

The hotspots' places and sizes are facts, listed with their sources in `data-src/hotspots/deposits-research.md`. Its
country tables quote the USGS Mineral Commodity Summaries 2026 data release, a United States government work in the
public domain. No dataset ships in the mod. Factorio is a trademark of Wube Software Ltd.; this is an unofficial mod.

## For developers

`python tools/earth_test.py static` runs the static checks and `python tools/build_zip.py` builds the
zip. The offline body checks and `build_zip.py --release` read `tests/vanilla-raw.json`, the base game's prototypes: `python tools/make_vanilla_raw.py --dump <base-only data-raw-dump.json>` makes it from an installed Factorio 2.1.
`TESTING.md` is the release smoke test, `CHANGELOG.md` the build record, and `ARCHITECTURE.md`
and the design notes hold the design.
