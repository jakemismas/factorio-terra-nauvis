-- The third hotspot table (config.lua hotspots_v3; ARCHITECTURE.md, release versioning rule 14).
-- Written by tools/build_hotspots.py (writer 1) from
--   data-src/hotspots/hotspots-v3.json sha256 289b001132d4033eb7f4f1faf98d4029bb37a8efb0362e066b7537a9c4e3b94e
-- Never edit by hand: an edit is an edit of that file, then `python tools/build_hotspots.py emit3`; the static gate
-- row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua. rows: rows of the first two tables moved onto land, each with the region fields of
-- prototypes/tables/regions.lua and the hotspot fields of the second table. retired: the ids of the first two tables
-- this table's readers do not read. rich: per row, the factor its ore per tile is raised by over the rule's, so a
-- small disc holds its design total in the room it has. rivals: per row of the whole set, the rows of another ore
-- whose footprints it keeps out of.
return {
  rows = {
    {
      id = "stone_marmara_island_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "stone",
      lat = 40.15, lon = 27.64, radius_km = 15, jitter_km = 4, phase = 0.701147496, strength = 2, radius_px = 6.070417,
      cap_px = 26.30514, offshore = false,
      maps = {"europe", "atlantic", "olde_world"},
      share = {europe = 1, atlantic = 1, olde_world = 1},
      source = "hotspots-v3.json stone-marmara-island-3 (a moved row)",
    },
    {
      id = "stone_portland_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "stone", lat = 50.76,
      lon = -2.22, radius_km = 10, jitter_km = 4, phase = 0.67846436, strength = 2, radius_px = 4.046945,
      cap_px = 24.281667, offshore = false,
      maps = {"europe", "atlantic", "olde_world"},
      share = {europe = 1, atlantic = 1, olde_world = 1},
      source = "hotspots-v3.json stone-portland-3 (a moved row)",
    },
    {
      id = "copper_sumbawa_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "copper-ore",
      lat = -8.75, lon = 117.19, radius_km = 30, jitter_km = 8, phase = 0.996592679, strength = 3,
      radius_px = 12.140834, cap_px = 32.375556, least_tiles = 60, offshore = false,
      maps = {"atlantic", "olde_world"},
      share = {atlantic = 1, olde_world = 1},
      source = "hotspots-v3.json copper-sumbawa-3 (a moved row)",
    },
    {
      id = "stone_aswan_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "stone", lat = 24.1,
      lon = 33.05, radius_km = 15, jitter_km = 4, phase = 0.067685, strength = 2, radius_px = 6.070417,
      cap_px = 26.30514, offshore = false,
      maps = {"atlantic", "olde_world"},
      share = {atlantic = 1, olde_world = 1},
      source = "hotspots-v3.json stone-aswan-3 (a moved row)",
    },
    {
      id = "stone_estremoz_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "stone", lat = 38.8,
      lon = -7.45, radius_km = 15, jitter_km = 7.5, phase = 0.810917243, strength = 2, radius_px = 6.070417,
      cap_px = 26.30514, least_tiles = 60, offshore = false,
      maps = {"europe", "atlantic", "olde_world"},
      share = {europe = 1, atlantic = 1, olde_world = 1},
      source = "hotspots-v3.json stone-estremoz-3 (a moved row)",
    },
    {
      id = "stone_shuitou_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "stone", lat = 24.8,
      lon = 118.36, radius_km = 20, jitter_km = 4, phase = 0.336305067, strength = 2, radius_px = 8.093889,
      cap_px = 28.328612, offshore = false,
      maps = {"atlantic", "olde_world"},
      share = {atlantic = 0.971, olde_world = 0.971},
      source = "hotspots-v3.json stone-shuitou-3 (a moved row)",
    },
    {
      id = "copper_collahuasi_3", layer = "hotspot", shape = "disc", warp = 0, mult = 4, resource = "copper-ore",
      lat = -20.98, lon = -68.38, radius_km = 45, jitter_km = 12, phase = 0.899419746, strength = 3,
      radius_px = 18.211251, cap_px = 38.445973, offshore = false,
      maps = {"atlantic"},
      share = {atlantic = 1},
      source = "hotspots-v3.json copper-collahuasi-3 (a moved row)",
    },
  },
  retired = {
    "stone_marmara_island", "stone_portland", "stone_aswan", "copper_sumbawa", "stone_estremoz", "stone_shuitou",
    "copper_collahuasi",
  },
  rich = {
    stone_aswan_3 = {{1.45, 0}},
    stone_carrara = {{2.5, 6}},
    stone_denizli = {{1.4, 0}},
    stone_estremoz_3 = {{1.4, 0}, {1.3, 6}},
    stone_mutoko = {{1.5, 0}},
    stone_pentelicus = {{1.4, 0}},
    stone_shuitou_3 = {{1.3, 0}},
  },
  rivals = {
    coal_donbas = {"iron_kursk_magnetic_anomaly"},
    coal_godavari = {"iron_bailadila", "stone_khammam"},
    coal_jharia_damodar = {"uranium_singhbhum"},
    coal_ordos = {"iron_bayan_obo"},
    coal_powder_river = {"uranium_wyoming"},
    coal_south_sumatra = {"oil_south_sumatra"},
    coal_tavan_tolgoi = {"copper_oyu_tolgoi"},
    copper_uchaly = {"iron_magnitogorsk"},
    iron_barbil = {"coal_talcher_ib", "uranium_singhbhum"},
    iron_gol_e_gohar = {"copper_sarcheshmeh"},
    iron_kryvbas = {"uranium_kirovohrad"},
    oil_abu_dhabi = {"offshore_upper_zakum"},
    oil_baku_absheron = {"offshore_caspian_acg"},
    oil_basra_kuwait = {"offshore_safaniya"},
    oil_maracaibo = {"coal_cerrejon"},
    oil_niger_delta = {"offshore_nigeria_deepwater"},
    oil_orinoco_belt = {"iron_cerro_bolivar"},
    stone_estremoz_3 = {"copper_iberian_pyrite_belt"},
    uranium_olympic_dam = {"copper_olympic_dam"},
    uranium_tummalapalle = {"iron_bellary_hospet"},
    uranium_witwatersrand = {"coal_witbank_highveld"},
  },
}
