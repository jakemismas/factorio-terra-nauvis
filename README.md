![Terra Nauvis: Earth Maps. The title on one line over a dimmed in-game view of the Alps with snow, a river and forest, beside a small render of Europe and the Mediterranean from the mod's Atlantic map.](docs/images/banner.png)

![The whole Atlantic map: the Americas, Europe, Africa, Asia and Australia in a deep ocean, with snow in the far north and white mountain ranges](docs/images/world-atlantic.jpg)

*The whole Atlantic map at scale 6, seed 1000, with Alien Biomes and every setting at its default (Destroyed
Europe and Blue corrupted UK off).*

Terra Nauvis is a mod for Factorio 2.1 that turns Nauvis into Earth. It has three maps (Europe, the Old World,
the Atlantic) with real coastlines, rivers, mountain ranges and ore fields, in eight sizes, and you start at a
real city.
Version 1.2.0 needs Factorio 2.1.24 or newer and runs on the base game. Alien Biomes is optional.

## Under the hood

The land is drawn by noise expressions, the game's own map generation language, so the new-game preview shows
the real map and nothing runs per tick. Each coastline is a sum of small tent functions fitted to a reference
raster (8,258 terms for Europe, 10,400 for the Atlantic and 9,360 for the Old World at scales 1 to 6), written
out as Lua by [tools/build_geo.py](tools/build_geo.py). The text of every named expression is registered by hash
in [tests/frozen.json](tests/frozen.json), 2,360 records, and the release build refuses a changed entry
([tools/tnfrozen.py](tools/tnfrozen.py)), so a world keeps its terrain through every update. On the base game
the tile program is about 10 to 15 times as complex as the vanilla one and the entity program 2 to 3.5 times
([tests/budgets.json](tests/budgets.json)), and one script,
[scripts/bandfix.lua](terra-nauvis/scripts/bandfix.lua), is the only per-chunk handler: it holds coast tiles to
the source raster as chunks generate. The tests run the real game headless as the oracle, a Lua interpreter
written in Python ([tools/tnlua.py](tools/tnlua.py)) runs the data stage without the game for the checks that
need no world, and [ARCHITECTURE.md](ARCHITECTURE.md) has the rest.

## Install

1. Download `terra-nauvis_1.2.0.zip` from the
   [Releases page](https://github.com/jakemismas/factorio-terra-nauvis/releases).
2. Put the zip in your mods folder. Do not unzip it.
   - Windows: `%APPDATA%\Factorio\mods`
   - Linux: `~/.factorio/mods`
   - macOS: `~/Library/Application Support/factorio/mods`
3. Optional: install Alien Biomes from the mod portal. It adds more ground types, and the three zone settings
   need it.

In multiplayer every player needs the same Terra Nauvis zip in their mods folder.

## Create a world

1. Main menu > Settings > Mod settings > Startup. Set the map scale and spawn city, plus any option below. The
   defaults give a normal Earth, so you can skip this.
2. New game > pick a Terra Nauvis preset (Europe, Old World or Atlantic) at the top of the screen.
3. Check the preview and play.

Settings are read once, when the world is created. Changing them later only affects worlds you make afterwards,
and a mod update never changes an existing world.

## The three maps

Outside each map is endless deep ocean. Map scale is how many tiles each pixel of the source map becomes: at
scale 1 a tile is about 2.5 km, at scale 6 about 410 m, at scale 12 about 205 m and at scale 24 about 103 m. A
higher scale is the same map with more room; it does not add places.

| Map | Covers | Scale 1 | Scale 6 (default) | Scale 12 | Scale 24 |
|---|---|---|---|---|---|
| Europe | Ireland to Moscow, the North Cape to Crete | 2,400 x 1,704 | 14,400 x 10,224 | 28,800 x 20,448 | 57,600 x 40,896 |
| Old World | Europe, Africa, Asia and Australia | 8,963 x 5,847 | 53,778 x 35,082 | 107,556 x 70,164 | 215,112 x 140,328 |
| Atlantic | The whole world but Antarctica, Americas included | 15,689 x 6,524 | 94,134 x 39,144 | 188,268 x 78,288 | 376,536 x 156,576 |

Sizes are in tiles. The picture at the top is the Atlantic map; these are the other two, also at scale 6 with
every setting at its default.

![The whole Old World map: Europe, Africa, Asia and Australia](docs/images/world-old-world.jpg)

![The whole Europe map: Ireland to Moscow, the North Cape to Crete](docs/images/world-europe.jpg)

## Settings

Twelve startup settings and one runtime setting. Every default gives a normal Earth.

| Setting | Default | What it does |
|---|---|---|
| Map scale | 6 | 1, 2, 3, 4, 5, 6, 12 or 24 tiles per pixel of the source map. See the sizes above |
| Spawn city: Europe | Random | The city the world starts at, from 40. The map moves so the city sits at the spawn, with land around it, a lake nearby, the starting ore and the usual enemy-free start |
| Spawn city: Atlantic | Random | The same, from 52 cities. Random picks one of the first 50 from the map seed |
| Spawn city: Old World | Random | The same, from 33 cities |
| Ore hotspots | On | Dense ore fields at real mining sites such as Kiruna, the Ruhr, the Donbas, Ghawar and the Copperbelt (27 fields on Europe, 136 on the Old World, 180 on the Atlantic), with about three times the usual biter nests inside. Since 1.2.0 a field near the spawn starts small, with no extra nests, and grows to its full size by about 3,000 tiles (both distances follow the Starting area slider). Full fields hold 1.4 times as much at scale 12 and twice as much at 24 as at scale 6, and oil fields on land follow the same rule. With Cargo Ships: Oil Rig there are offshore oil fields too |
| Lean ore | On | Ordinary ore patches are small: a typical patch within 1,000 tiles of the spawn holds about 500 thousand ore and none anywhere holds over 5 million, at the default ore sliders, which these amounts follow. Hotspots hold up to 1 million within 1,000 tiles, none within 150 tiles of the spawn, and up to 50 million at full size (71 million at scale 12, 100 million at 24). The starting patches are the base game's. Off keeps the base game's ordinary ore and larger hotspots |
| Regional scarcity | Medium | Off, Medium or Strong. Far from the spawn, ordinary ore patches get rarer outside the regions that hold that resource on Earth. At Medium about 20 percent of the uranium patches remain there, 35 percent of the oil, 50 of the copper, 65 of the iron, 75 of the coal and 95 of the stone. The start and the hotspots are not affected |
| Ridges | On | Cliff ridges along the mountain ranges (10 on Europe, 21 on the Old World, 26 on the Atlantic), with passes wide enough for a double track. They are the only cliffs on the map; Off gives a map with none, and in the Alps the snow goes with them (see the clip below) |
| Inland lakes | Off | Scatters small random lakes across the land, about eight in every 1,024 by 1,024 tiles |
| Destroyed Europe | Off | Turns the heart of Europe, from France to Poland and down Italy to about Rome, into a volcanic wasteland whose outline differs on every seed. The snowy ranges it encloses keep their snow and grow dead trees instead of living ones: the Alps, the eastern Alps and, on the Old World, the northern Apennines. The Pyrenees and the ranges outside the zone keep their living trees. Needs Alien Biomes |
| Blue corrupted UK | Off | Turns the United Kingdom into Alien Biomes' blue and purple lands. Needs Alien Biomes |
| Moscow zone | Normal | Normal, Chaos or Corrupted: the same two looks for a zone from the Baltic states to the Volga bend. Since 1.1.0 the north snow and the western end of the Caucasus stay snow inside the zone, with dead trees on them at Chaos. Chaos and Corrupted need Alien Biomes |
| North snow | Medium | Low, Medium or High: how far south the snow of northern Eurasia reaches. Medium is about 61 to 64 N, High about 57 to 60 N |
| City markers | Off | Shows city names on the map view. This is the one setting you can change in a running game |

The clips below are in-game shots of the Atlantic map (seed 1000, spawn Frankfurt, Alien Biomes) at scale 6
unless the clip is about scale, with every other setting at its default.

Map scale: the Rhine by Koblenz at scales 6, 12 and 24, at the same zoom, so a larger scale shows a shorter
stretch of a wider river.

![Map scale 6, 12 and 24: the Rhine by Koblenz grows wider at each scale](docs/images/gifs/terra-nauvis-scale.gif)

Ridges on and off, in the Alps.

![Ridges on and off in the Alps](docs/images/gifs/terra-nauvis-ridges.gif)

North snow at Low, Medium and High, over northern Russia at about 40 E, from 58 to 68 N.

![North snow at Low, Medium and High: the snow line moves south at each step](docs/images/gifs/terra-nauvis-north-snow.gif)

Inland lakes off and on.

![Inland lakes off and on: a lake appears in open country](docs/images/gifs/terra-nauvis-inland-lakes.gif)

Destroyed Europe off and on, from the Rhine to the Adriatic. The ranges inside the zone keep their snow.

![Destroyed Europe off and on: green land turns to dark volcanic ground, the Alps stay white](docs/images/gifs/terra-nauvis-destroyed-europe.gif)

![Europe with both zones on: Destroyed Europe red from France to Poland with the Alps white inside it, and the United Kingdom blue and purple](docs/images/zones-europe.jpg)

*Both zones on, from a whole-map render of the Atlantic map at scale 6. Renders use the map view's colours, so
the volcanic ground that is dark in the world shows red here.*

Blue corrupted UK off and on, over southern England and the Channel.

![Blue corrupted UK off and on](docs/images/gifs/terra-nauvis-blue-corrupted.gif)

Moscow zone at Normal, Chaos and Corrupted, a view about 1,500 km across south of Moscow; the zone's eastern
edge shows at the right.

![Moscow zone at Normal, Chaos and Corrupted](docs/images/gifs/terra-nauvis-moscow-zone.gif)

## Other Features

These are features, not settings.

- **Canals.** Kiel and Corinth on every map, Suez on the Old World and the Atlantic, Panama on the Atlantic, as
  sea-level channels at least 7 tiles wide.
- **Exact coastlines.** On the Old World and the Atlantic at scales 1 to 6, each chunk's coast is held to the
  source map as it generates, so channels and islets narrower than a pixel come back. The preview shows the
  noise coast, which is the same shape without that last detail.
- **River fords.** Every great river has stretches of shallow water you can walk across.
- **Marshes.** Wet ground with pools at real wetlands such as the Sundarbans and the Inner Niger Delta.
- **Great forests.** The 22 great forests of Earth, from the Black Forest and the Scandinavian taiga to the
  Congo, the Amazon, Borneo and New Guinea, on the maps that hold them. Beside Alien Biomes the ground inside
  one is forest ground under dense trees.

  ![The Black Forest: forest ground under dense trees](docs/images/great-forest.jpg)

- **River deltas.** The great rivers fan out into shallow side channels at their mouths, across wet green ground
  on most of them: the Nile and the Niger on the Old World and the Atlantic, the Indus and the Lena on the Old
  World, the Amazon, the Mississippi and the Orinoco on the Atlantic.

  ![The Nile delta: side channels fan out to the sea through dense forest](docs/images/delta-nile.jpg)

## Compatibility

- **Factorio.** 2.1.24 or newer. The base game is enough.
- **Alien Biomes.** Optional. With it the ground follows real regions across a wider palette, and Destroyed
  Europe, Blue corrupted UK and the Moscow zone need it.
- **Space Age.** Works. Terra Nauvis changes Nauvis only, and the other planets generate as they do without it.
- **Cargo Ships and Cargo Ships: Oil Rig.** Canals and straits are open water at every scale. The Oil Rig adds
  offshore oil fields.
- **RSO.** Not supported. It replaces the map's ore with its own, and the game warns when it is active.

## Pictures

In-game shots of the Atlantic map at scale 6, seed 1000, with Alien Biomes and default settings unless the
caption names a zone.

| | |
|---|---|
| ![The Cyclades and the coast of Attica](docs/images/coast.jpg) The Aegean: the Cyclades and the coast of Attica | ![A ford across the Mississippi](docs/images/river.jpg) A ford on the Mississippi: shallow water you can walk across |
| ![Cliff walls with a gap between them in the snow of the Alps](docs/images/cliffs.jpg) Cliff ridges in the snow of the Alps, with a gap between them | ![Dark coal fields by the Rhine](docs/images/hotspot.jpg) The Ruhr ore hotspot: coal by the Rhine |
| ![Sand, rock and biter nests in the Sahara](docs/images/sahara.jpg) The Sahara: sand, rock and biter nests | ![Savanna by Lake Victoria](docs/images/savanna.jpg) Savanna by Lake Victoria |
| ![Mixed forest in Siberia](docs/images/taiga.jpg) Forest in Siberia at about 60 N | ![Snow and conifers above green taiga](docs/images/taiga-snow.jpg) The snow line across the taiga near 62 N, North snow at Medium |
| ![Scandinavia and the Baltic on a map render](docs/images/scandinavia.jpg) Scandinavia and the Baltic, from a map render | ![A sea-level canal across the isthmus of Panama](docs/images/canal-panama.jpg) The Panama canal |
| ![A dead forest inside Destroyed Europe](docs/images/dead-forest.jpg) Destroyed Europe: the Black Forest as a dead forest | ![Snowy Alps inside Destroyed Europe](docs/images/destroyed-alps.jpg) Destroyed Europe: the Alps keep their snow |

## Contributing and bug reports

Found something wrong? Open a
[bug report](https://github.com/jakemismas/factorio-terra-nauvis/issues/new?template=bug_report.yml); the form
asks for the map, scale, city and seed, which is what it takes to find the same place again. To propose a change
or send a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## How this was built

I am a software developer. I designed the mod, planned each sprint, set the rules and the tests, reviewed the
code and tested every build in the game.

The code was written with AI coding agents (Claude Code) working as a build team under my direction. Agents
worked in parallel, each in its own git worktree, on one feature with written acceptance criteria that had to
pass before the feature merged. A headless test harness runs the real game, so a result is measured, not
assumed. The append-only rule is enforced by tests, not by convention. Separate review passes were asked to
refute a change, not to confirm it. Every visual change was judged on in-game screenshots.

## About this repository

The history here is a rebuild. The mod was rebuilt several times during development, and the original
repository held working notes and material that was not safe to publish publicly, and lots of cursed issues, so the history was reconstructed with
each change dated when it was first made. The intermediate commits show how the code grew and are not each a
working build; the tagged release is the tested build.

## Licence and credits

Written by Jake Mismas and released under the GNU General Public License version 3: see [LICENSE](LICENSE). The
mod is built on [EarthMaps](https://github.com/HySpeed/EarthMaps) by HySpeed (GPLv3) (THANK YOU THIS GUY IS THE 🐐), which descends from
Factorio World by TheOddler (ANOTHER 🐐). Forest and marsh outlines come from RESOLVE Ecoregions 2017 (CC BY 4.0), and canal
routes use data from OpenStreetMap contributors. The screenshots show the art of Factorio and of Alien Biomes, which belongs to
their authors. [NOTICE.md](NOTICE.md) has the full notices and what is not covered by the GPL.

Factorio is a trademark of Wube Software Ltd. Terra Nauvis is an unofficial mod.
