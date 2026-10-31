# Testing

Release smoke test, about 15 minutes in the real game. Run it on the zip you are about to release,
then record it in a comment on the parent issue that starts "Smoke pass" and names the zip's
version and sha256 and the `main` commit, with each step marked pass, fail or not run.

## Before you start

1. Back up `mod-list.json` and `mod-settings.dat` from `%APPDATA%\Factorio\mods`.
2. Run `python tools/earth_test.py static` and `python tools/build_zip.py --release` on `main`. Both
   must finish with no failed row.
3. Copy the zip to `%APPDATA%\Factorio\mods`, with no other `terra-nauvis_*.zip` beside it.

## Smoke checklist

Old World leads because it is the map the maintainer plays.

1. **Mods menu.** Open Mods. Terra Nauvis 0.1.0 shows its title, description and thumbnail, and
   enabling it shows no error.
2. **Startup settings.** Open Settings > Mod settings > Startup. Map scale offers 1 to 6 with every
   map's world size in each label. The spawn city lists offer Random plus 40 cities for Europe, 50 for
   Atlantic and 33 for Old World, and Old World lists Frankfurt, Aachen and Moscow. Ore hotspot amount
   offers 50, 100, 200 and 400 percent. Every setting has a tooltip, and no text reads "Unknown key".
3. **New-game screen.** Open Single player > New game. The preset list shows Terra Nauvis: Europe,
   Atlantic and Old World right after Default, each with a description naming its world size. Picking
   one sets the Terrain tab's Map type to the entry of the same name.
4. **Preview.** Pick Terra Nauvis: Old World at seed 1000. The preview shows the map around the
   spawn. Move the water slider to none and to its maximum: the preview does not change. Move
   moisture: the biomes shift and the coast stays.
5. **Start.** Set Map scale 6 and Spawn city: Old World to Frankfurt, then start a Terra Nauvis: Old
   World game. The intro names the city and the world size, 53,778 x 35,082 tiles. You stand on land
   with a lake nearby, iron, copper, coal and stone on the land you can walk to, and no biters in the
   starting area. With RSO active, the RSO warning shows in the run.
6. **Explore.** Travel for five minutes in one direction. The game does not crash, the terrain has no
   seams, and rivers, fords and forests look right on the map view.
7. **Saved settings.** Save, change Map scale, and load the save. A message says the world keeps its
   scale, and exploring further shows no seam. Set Map scale back.
8. **City markers.** In a running game, open Settings > Mod settings > Map and switch City markers on.
   The map view names the cities. Switch it off and the names go.
9. **Destroyed Europe without Alien Biomes.** With Alien Biomes disabled and Destroyed Europe on,
   start a Terra Nauvis game. The Destroyed Europe warning shows in the run. Turn the setting back off.
10. **Space Age, if you own it.** Start a Terra Nauvis game with Space Age enabled. Nauvis is Earth,
    and the other planets generate as they do without Terra Nauvis.

## Not in this smoke test

- Multiplayer: no desync test has run, so 0.1.0 is for single player.
- Exact coastlines: it is on by default on Old World and Atlantic and acts as chunks generate, so
  step 6 reaches it only if the route meets a coast. To check it, drive along a coast on either map:
  channels and islets the preview lacks appear, and new land carries trees. Europe's map keeps its
  noise coast.
