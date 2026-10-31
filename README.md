# Terra Nauvis

Terra Nauvis turns Nauvis into Earth. Pick one of three maps on the new-game screen and play on real
coastlines, with great rivers, forests and deserts where you expect them, and a start at a real city.

Version 0.1.0, for Factorio 2.1.

![The Terra Nauvis: Old World map at map scale 6](docs/images/old-world.jpg)

*Old World at map scale 6, seed 1000, from the game's map preview with the base game's tiles.*

## The three maps

| Preset | What it covers | World size at scale 1 | World size at scale 6 | Spawn cities |
|---|---|---|---|---|
| Terra Nauvis: Europe | Europe from Portugal to western Russia and Turkey, with a strip of North Africa | 2,400 x 1,704 tiles | 14,400 x 10,224 tiles | 40 |
| Terra Nauvis: Atlantic | The whole world, centred on the Atlantic | 15,689 x 6,524 tiles | 94,134 x 39,144 tiles | 50 |
| Terra Nauvis: Old World | Europe, Africa, Asia and Australia | 8,963 x 5,847 tiles | 53,778 x 35,082 tiles | 33 |

Every map sits in an endless deep ocean and comes with:

- Great rivers with walkable fords, and straits and canals wide enough for ships. Rivers narrow with
  the map scale, from about 3 tiles wide at scale 1 to about 12 to 18 at scale 6, the scale ships
  need.
- Earth climate: a frozen far north, cold Scandinavia and Russia, temperate Europe and hot deserts.
- Marshes and 16 great forests, from the Black Forest to the Congo and the Amazon on the maps that
  hold them.
- Cliff ridges along 16 mountain ranges, with passes at their historic crossings. Big rocks and
  stony ground gather round each range, and beside Alien Biomes tall ranges turn to grey rock and
  snow.
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
every startup setting below for life, and a message tells you when a setting no longer matches.

The Terrain tab's **Map type** list also names the three maps. Picking only the map type gives you
that map's coast, rivers and spawn with the base game's climate and none of the rest, and that world
follows later changes to the scale and spawn city settings, which moves any terrain it generates
afterwards. Use the preset unless you want exactly that.

## Settings

All of these are startup settings except City markers, which is on the Map tab.

| Setting | Default | What it does |
|---|---|---|
| Map scale | 6 | The size of the world: each pixel of the reference map becomes 1 to 6 tiles. |
| Spawn city: Europe | Random | Where a Europe game starts: Random or one of 40 cities. |
| Spawn city: Atlantic | Random | Where an Atlantic game starts: Random or one of 50 cities. |
| Spawn city: Old World | Random | Where an Old World game starts: Random or one of 33 cities. |
| Canals | On | Opens the Kiel and Corinth canals on every map, Suez on Atlantic and Old World, and Panama on Atlantic, as sea-level channels at least 7 tiles wide that Cargo Ships can use. Off keeps every isthmus closed. |
| Great forests | On | Gives the 16 great forests about twice the trees of the land around them. Trees still follow the climate, so a forest in a cold or dry place stays thinner. |
| Ridges | On | Places cliff ridges along 16 mountain ranges, the only cliffs on the map, with passes at their historic crossings and a gap at least every 400 km, each wide enough for a double track. No ridge crosses the starting area. Off gives a map with no cliffs. |
| Ore hotspots | On | Adds dense ore at historic sites, in a disc that moves a little with the map seed, with about three times the base game's biter nests inside it, and offshore oil fields on deep water where the Oil Rig mod is installed. The map's ore sliders do not reach a hotspot, and ordinary ore stays out of its disc. No field lies at a spawn city. Off gives the base game's ore, in the map's lobed fields. |
| Ore hotspot amount | 100 percent | How much ore and oil every hotspot holds: 50, 100, 200 or 400 percent. It changes richness only, never a hotspot's place or size. |
| Inland lakes | Off | Scatters small random lakes across the land, away from coasts and the starting area. Off leaves only the lake at the spawn city, the rivers and the real lakes of the map. |
| Destroyed Europe | Off | Needs Alien Biomes. Turns the heart of Europe, from France across Germany and Poland to Ljubljana and down Italy to about Rome, into a red wasteland of lava, black ash, red rock and scorched red grass, patches mixed, with an outline that differs on every map seed and reds on the map view. Britain, Denmark, the Kiel Canal and the Carpathians stay outside, and the start area stays normal. A random spawn city never lands inside the zone; a chosen one can. Without Alien Biomes nothing changes and the game warns. |
| Exact coastlines | On | On Atlantic and Old World it holds a new world's coast to the EarthMaps reference as chunks generate, on every shore, so channels and islets narrower than a pixel come back, and land made from sea takes the trees and ground cover of the land beside it. The map preview still shows the noise coast. Europe's map keeps its noise coast. |
| City markers | Off | Names every city on the map view. It changes nothing in the world, so you can switch it at any time in a running game. Worlds made from a Map type entry alone get no markers. |

## Compatibility

- **Alien Biomes:** optional. With it, the ground follows real regions: deep green rainforests,
  golden deserts, pale sand and gravel across Central Asia, dry yellow steppes, cold grey Tibet, pale
  tundra and a white Greenland. Temperate Europe keeps its ground, and the base game's trees, rocks
  and plants grow beside Alien Biomes' own. Without it, the base game's tiles follow the climate.
  Destroyed Europe needs it.
- **Grey cliffs beside Alien Biomes:** with Terra Nauvis and Alien Biomes both on, every Nauvis
  world's cliffs use Alien Biomes' grey stone art, not only Terra Nauvis worlds and saves made
  without this mod too. It changes the look only: no cliff moves.
- **Space Age:** works, and is not required. Terra Nauvis changes Nauvis only, so the other planets
  generate as they do without it.
- **RSO:** not supported. RSO replaces the map's ore with its own, so you do not get the designed
  start ore, ore hotspots may not match the map, and the preview shows no ore. Where RSO's start is
  short of an ore, Terra Nauvis adds a patch, unless RSO's Ore in starting area setting is off. The
  game warns you at the start and carries on. Turn RSO off to get the designed start.
- **Cargo Ships and its Oil Rig:** straits and canals are wide enough for ships at every scale, and
  rivers at scale 6. Offshore oil fields appear on deep water when the Oil Rig mod is installed.
- **Large packs:** on a build from earlier on release day, the maintainer's pack of 83 mods, with Space Age,
  Alien Biomes, RSO, Cargo Ships, Bob's Enemies, Big Monsters and Dectorio, ran with no errors, saved
  and reloaded clean, and gave the same world on four separate creates. Those mods change ore,
  enemies and looks, so a world in a pack will not match the previews on this page.

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
- **Atlantic's great rivers are fragments at scale 3 and up.** Only Europe's 22 rivers are carved
  there, so the Amazon, Mississippi, Nile, Congo and six more show only as short pieces where Exact
  coastlines writes the reference's water. Scale 2 keeps the Niger and the Mackenzie, and scale 1
  carves all ten. Europe and Old World keep every river at every scale.
- **Ships need scale 6 on rivers.** Rivers at scales 1 to 3 are too thin for ships, and scales 4 and
  5 were not checked. At every scale a river thins to a stream at its source.
- **Some shapes still read as computer-made.** At scale 6 cliffs can run in near-parallel east-west
  rows, like terraces, the Alps' snow shows a sharp seam, and Greenland and Arctic Canada read as long
  east-west streaks.
- **New chunks cost more than in the base game.** On Old World at scale 6, at Frankfurt, generating
  chunks took 1.085 times as long as the base game, and beside Alien Biomes 1.122 times as long as
  Alien Biomes alone. Moving fast into new land can bring brief stalls. Nothing runs per tick once
  chunks exist. Terra Nauvis also adds a few seconds to the game's startup.
- **A world keeps its terrain.** A world keeps the terrain it was started on. Later releases add
  terrain for new worlds and never change an existing save's terrain. A world made from a Map type
  entry alone still follows the scale and spawn city settings.
- **An existing save stays as it is.** Adding the mod to a world made without it changes nothing on
  that world's surfaces, apart from the grey cliff art beside Alien Biomes.
- **Testing was light for this release.** A crash matrix, a pack run and one security pass ran on
  builds from earlier on release day, before the last terrain changes. The final build had load and
  chunk time checks. The full timing, determinism and save suites have not run on it.
- **Not on the Mod Portal.** The GitHub release is the only source.

## License and credits

Terra Nauvis is by Jake Mismas, under the GNU General Public License version 3: see
`terra-nauvis/LICENSE`, and `terra-nauvis/SOURCE-OFFER.txt` for how to get the source. Its map data
derives from [EarthMaps](https://github.com/HySpeed/EarthMaps) by HySpeed, also GPLv3. The islets the
EarthMaps raster lacks are derived from
[RESOLVE Ecoregions 2017](https://ecoregions.appspot.com/) by Dinerstein et al., under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## For developers

`python tools/earth_test.py static` runs the static checks and `python tools/build_zip.py` builds the
zip. `TESTING.md` is the release smoke test, `CHANGELOG.md` the build record, and `ARCHITECTURE.md`
and the design notes hold the design.
