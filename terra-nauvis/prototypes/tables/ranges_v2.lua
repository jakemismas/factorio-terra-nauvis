-- Ridge ranges, second table (0.3.0, Earth mods recommendation 4): ranges the released table (ranges.lua) lacks.
-- Written by tools/build_ranges.py (writer 2) from
--   data-src/ridges/ranges-v2.json sha256 4436dcb7f2176a24cbab589858142223b6c0b6000c793abffab170bee73eb4a2
-- Never edit by hand: edit ranges-v2.json, then `python tools/build_ranges.py emit2`; the static gate row re-emits
-- this file and fails on a difference.
--
-- Pure data with ranges.lua's fields (see its header). Only the next ridge bodies read it (ridges.lua, the union of
-- both tables): the released bodies read ranges.lua alone, so no world made before changes. Passes are named passes
-- and gorges at the crest point nearest them; gaps follow the 400 km rule; edges the map-edge rule.
return {
  ranges = {
    {
      id = "taurus", name = "Taurus Mountains", crest_km = 1243.5,
      crest = {
        {36.55, 29.57}, {36.64, 30.13}, {37.63, 31.28}, {36.88, 32.15}, {37.4, 34.62}, {37.83, 35.16}, {38.33, 36.47},
        {37.95, 37.43}, {38.15, 38.55}, {38.4, 41.3}, {38.4, 42.12},
      },
      heights = {
        3016, 3070, 2992, 2877, 3524, 3756, 2957, 3081, 2500, 2800, 1500,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "gap", id = "taurus_gap_1", seg = 3, arc_km = 257.8, lat = 37.255, lon = 31.715,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "cilician_gates", seg = 5, arc_km = 542.2, lat = 37.4075871, lon = 34.629528,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "taurus_gap_2", seg = 8, arc_km = 886.9, lat = 38.0635923, lon = 38.0661166,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "talysh", name = "Talysh Mountains", crest_km = 258.9,
      crest = {
        {38.85, 48.3}, {38.45, 48.55}, {37.15, 48.95}, {36.74, 49.4},
      },
      heights = {
        2000, 2493, 2700, 350,
      },
      segments = {
        atlantic = {1, 2, 3},
        olde_world = {1, 2, 3},
      },
      openings = {
      },
    },
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
      id = "alborz_east", name = "Alborz (Elburz), eastern", crest_km = 343.1,
      crest = {
        {35.85, 52.95}, {36.4, 54.95}, {37.35, 56.2},
      },
      heights = {
        2100, 3945, 2000,
      },
      segments = {
        atlantic = {1, 2},
        olde_world = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "ethiopia_west", name = "Ethiopian Highlands, north-western plateau", crest_km = 861.8, cold = false,
      crest = {
        {15.33, 38.93}, {13.24, 38.37}, {11.72, 38.24}, {10.7, 37.85}, {10.05, 38.2}, {9.1, 38.75}, {8.15, 38.1},
      },
      heights = {
        2400, 4550, 4231, 4100, 1200, 3200, 3700,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6},
        olde_world = {1, 2, 3, 4, 5, 6},
      },
      openings = {
        {kind = "gap", id = "ethiopia_west_gap_1", seg = 2, arc_km = 320.1, lat = 12.5235019, lon = 38.3087206,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "abay_gorge", seg = 5, arc_km = 612.6, lat = 10.05, lon = 38.2, vertex = 5,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "ethiopia_east", name = "Ethiopian Highlands, south-eastern plateau", crest_km = 498.3, cold = false,
      crest = {
        {9.15, 41.6}, {7.83, 39.33}, {6.92, 39.78}, {6.2, 39.3},
      },
      heights = {
        3405, 4180, 4377, 3000,
      },
      segments = {
        atlantic = {1, 2, 3},
        olde_world = {1, 2, 3},
      },
      openings = {
        {kind = "gap", id = "ethiopia_east_gap_1", seg = 1, arc_km = 194, lat = 8.2659217, lon = 40.0796533,
         maps = {"atlantic", "olde_world"}},
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
      id = "cascades_oregon_south", name = "Cascade Range, Oregon (Three Sisters to Crater Lake)", crest_km = 251.7,
      crest = {
        {44.42, -121.87}, {44.103, -121.769}, {42.94, -122.11}, {42.2, -121.95},
      },
      heights = {
        1455, 3159, 2487, 1300,
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
      id = "cascades_lassen", name = "Cascade Range, Lassen", crest_km = 129.4,
      crest = {
        {40.95, -121.85}, {40.488, -121.505}, {39.9, -121.2},
      },
      heights = {
        900, 3189, 1500,
      },
      segments = {
        atlantic = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "sierra_north", name = "Sierra Nevada, northern (Tahoe)", crest_km = 185.1,
      crest = {
        {39.75, -120.7}, {39.32, -120.33}, {38.85, -120.16}, {38.33, -119.64},
      },
      heights = {
        2000, 2160, 3044, 2933,
      },
      segments = {
        atlantic = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "sierra_high", name = "Sierra Nevada, High Sierra (Yosemite to Whitney)", crest_km = 266.9,
      crest = {
        {38.33, -119.64}, {37.739, -119.271}, {36.578, -118.292}, {36.265, -118.118},
      },
      heights = {
        2933, 3999, 4421, 3695,
      },
      segments = {
        atlantic = {1, 2, 3},
      },
      openings = {
      },
    },
    {
      id = "sierra_south", name = "Sierra Nevada, southern (Kern Plateau to Tehachapi)", crest_km = 131.8,
      crest = {
        {36.265, -118.118}, {35.75, -118.3}, {35.1, -118.3},
      },
      heights = {
        3695, 2500, 1225,
      },
      segments = {
        atlantic = {1, 2},
      },
      openings = {
      },
    },
    {
      id = "gdr_north", name = "Great Dividing Range, Queensland", crest_km = 1913.5,
      crest = {
        {-13.75, 143.32}, {-17.4, 145.81}, {-21.03, 148.62}, {-25.05, 148.2}, {-26.87, 151.58}, {-27.56, 151.95},
      },
      heights = {
        823, 1622, 1259, 1000, 1135, 700,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5},
        olde_world = {1, 2, 3, 4, 5},
      },
      openings = {
        {kind = "gap", id = "gdr_north_gap_1", seg = 1, arc_km = 356.7, lat = -16.4313049, lon = 145.1491641,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "gdr_north_gap_2", seg = 2, arc_km = 735.1, lat = -19.2115076, lon = 147.2122965,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "gdr_north_gap_3", seg = 3, arc_km = 1124.3, lat = -22.2719491, lon = 148.4902441,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "gdr_north_gap_4", seg = 4, arc_km = 1518.9, lat = -25.4393806, lon = 148.9231355,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "gdr_south", name = "Great Dividing Range, New South Wales and Victoria", crest_km = 1324.2,
      crest = {
        {-28.3, 152.3}, {-30.43, 152.25}, {-31.95, 151.47}, {-32.3, 150.7}, {-33.7, 150.3}, {-36.456, 148.263},
        {-36.737, 147.305}, {-37.146, 146.44}, {-37.4, 145.1},
      },
      heights = {
        1100, 1584, 1586, 700, 1100, 2228, 1986, 1805, 800,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8},
      },
      openings = {
        {kind = "gap", id = "gdr_south_gap_1", seg = 2, arc_km = 318.4, lat = -31.1015668, lon = 151.9053802,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "gdr_south_gap_2", seg = 4, arc_km = 594, lat = -33.0894917, lon = 150.4744309,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "gdr_south_gap_3", seg = 5, arc_km = 959.1, lat = -35.9724167, lon = 148.6204235,
         maps = {"atlantic", "olde_world"}},
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
    {
      id = "gobi_altai", name = "Gobi Altai", crest_km = 717.6,
      crest = {
        {46.2, 95.5}, {44.95, 100.25}, {43.55, 103.8},
      },
      heights = {
        3500, 3957, 2825,
      },
      segments = {
        atlantic = {1, 2},
        olde_world = {1, 2},
      },
      openings = {
        {kind = "gap", id = "gobi_altai_gap_1", seg = 1, arc_km = 356.3, lat = 45.0722899, lon = 99.7852982,
         maps = {"atlantic", "olde_world"}},
      },
    },
  },
}
