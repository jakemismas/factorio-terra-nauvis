-- Ridge ranges, second table (0.3.0, Earth mods recommendation 4): ranges the released table (ranges.lua) lacks.
-- Written by tools/build_ranges.py (writer 2) from
--   data-src/ridges/ranges-v2.json sha256 4f2b53430bc0a20c849eecb80c22c0184ac39eec7c0d4444b1567a3656e3a389
-- Never edit by hand: edit ranges-v2.json, then `python tools/build_ranges.py emit2`; the static gate row re-emits
-- this file and fails on a difference.
--
-- Pure data with ranges.lua's fields (see its header). Only the next ridge bodies read it (ridges.lua, the union of
-- both tables): the released bodies read ranges.lua alone, so no world made before changes. Passes are named passes
-- and gorges at the crest point nearest them; gaps follow the 400 km rule; edges the map-edge rule.
return {
  ranges = {
    {
      id = "alborz", name = "Alborz (Elburz), central", crest_km = 353.8,
      crest = {
        {36.74, 49.4}, {36.38, 50.97}, {35.88, 51.42}, {35.955, 52.11}, {35.85, 52.95},
      },
      heights = {
        350, 4850, 3964, 5610, 2100,
      },
      segments = {
        atlantic = {1, 2, 3, 4},
        olde_world = {1, 2, 3, 4},
      },
      openings = {
      },
    },
    {
      id = "tian_shan_west", name = "Tian Shan, western (Talas and Kyrgyz Ala-Too)", crest_km = 505,
      crest = {
        {41.55, 70.03}, {42.3, 72}, {42.55, 74.6}, {42.62, 75.9},
      },
      heights = {
        3309, 4482, 4895, 1500,
      },
      segments = {
        atlantic = {1, 2, 3},
        olde_world = {1, 2, 3},
      },
      openings = {
        {kind = "gap", id = "tian_shan_west_gap_1", seg = 2, arc_km = 290.7, lat = 42.425, lon = 73.3,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "tian_shan_central", name = "Tian Shan, central (Terskey Ala-Too to Khan Tengri)", crest_km = 712.8,
      crest = {
        {42.3, 76.2}, {42.1, 77.8}, {42.035, 80.13}, {42.7, 83}, {43.15, 84.6},
      },
      heights = {
        3500, 5000, 7439, 4800, 4000,
      },
      segments = {
        atlantic = {1, 2, 3, 4},
        olde_world = {1, 2, 3, 4},
      },
      openings = {
        {kind = "gap", id = "tian_shan_central_gap_1", seg = 3, arc_km = 363.1, lat = 42.1344139, lon = 80.5590495,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "tian_shan_east", name = "Tian Shan, eastern (Bogda Shan)", crest_km = 378.3,
      crest = {
        {43.3, 85.5}, {43.1, 86.8}, {43.8, 88.32}, {43.45, 89.8},
      },
      heights = {
        4000, 4484, 5445, 3000,
      },
      segments = {
        atlantic = {1, 2, 3},
        olde_world = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "karlik", name = "Karlik Tagh (easternmost Tian Shan)", crest_km = 179.3,
      crest = {
        {43.35, 93.1}, {43.1, 94.2}, {42.85, 95.2},
      },
      heights = {
        3500, 4886, 3000,
      },
      segments = {
        atlantic = {1, 2},
        olde_world = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "cascades_north", name = "Cascade Range, North Cascades", crest_km = 317.4,
      crest = {
        {49.85, -123}, {48.777, -121.813}, {48.112, -121.113}, {47.42, -121.41},
      },
      heights = {
        2678, 3286, 3213, 921,
      },
      segments = {
        atlantic = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "cascades_washington", name = "Cascade Range, Washington (Rainier and Adams)", crest_km = 204.4,
      crest = {
        {47.42, -121.41}, {46.853, -121.76}, {46.202, -121.491}, {45.7, -121.8},
      },
      heights = {
        921, 4392, 3743, 100,
      },
      segments = {
        atlantic = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "cascades_hood", name = "Cascade Range, Oregon (Hood and Jefferson)", crest_km = 144.2,
      crest = {
        {45.7, -121.8}, {45.374, -121.696}, {44.674, -121.8}, {44.42, -121.87},
      },
      heights = {
        100, 3429, 3199, 1455,
      },
      segments = {
        atlantic = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "cascades_shasta", name = "Cascade Range, Mount Shasta", crest_km = 148.9,
      crest = {
        {42.2, -121.95}, {41.409, -122.195}, {40.95, -121.85},
      },
      heights = {
        1300, 4322, 900,
      },
      segments = {
        atlantic = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "altai_russian", name = "Altai, Russian (Katun Range)", crest_km = 328.5,
      crest = {
        {50.3, 83.7}, {49.807, 86.59}, {49.15, 87.82},
      },
      heights = {
        2775, 4506, 4374,
      },
      segments = {
        atlantic = {1, 2},
        olde_world = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "altai_mongol", name = "Mongolian Altai", crest_km = 527.3,
      crest = {
        {49.15, 87.82}, {47, 91.6}, {46.6, 93.6},
      },
      heights = {
        4374, 4204, 4220,
      },
      segments = {
        atlantic = {1, 2},
        olde_world = {1, 2},
      },
      openings = {
        {kind = "gap", id = "altai_mongol_gap_1", seg = 1, arc_km = 248, lat = 47.7037856, lon = 90.3626468,
         maps = {"atlantic", "olde_world"}},
      },
    },
  },
}
