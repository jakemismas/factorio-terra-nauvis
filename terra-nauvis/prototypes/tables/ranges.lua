-- Ridge ranges (ARCHITECTURE.md, slice contract 8; APPROVALS 5; DECISIONS 05:55 and 06:45; slice ridges).
-- Written by tools/build_ranges.py (writer 2) from
--   data-src/approvals/approvals-data.json sha256 33ce91d5e5303fb47825d52593e942d22f2d16e7f03b3d11cab4fd97eaa24c5a
--   docs/plan/research/R7b-geography.json sha256 480c9f20e0a33decc79786b2c4b7a38fe3b8ba8d8b5d8706783f11d913be7729
--   data-src/ridges/vertex-heights.json sha256 b8693d54f23dad1c4e3f05c15e2721d9f4b9b3c508532130c3eb55a13d69c454
-- Never edit by hand: an approval edit is an edit of approvals-data.json, then
-- `python tools/build_ranges.py emit`; the static gate row re-emits this file and fails on a difference.
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through
-- tools/tnconfig.py's loader. prototypes/expressions/ridges.lua turns each map's ranges into the map's
-- crest distance and openings. Fields: id; name (R7b's, ASCII); crest_km (ground km along the crest);
-- crest (R7b's crest polyline, lat and lon per vertex); heights (metres, one per crest vertex: the
-- ridge's width follows them); segments (per map that holds any vertex, the crest segments its ridge
-- reads, from 1); openings: kind (pass: an adopted pass at the crest point that
-- serves it; gap: an unnamed pass-width gap at the lowest-curvature crest point, at least one every
-- 400 km of crest; edge: where a range cut by the map's edge with no pass on that map meets the
-- edge), id, lat and lon (on the crest), seg (the crest segment it lies on), arc_km (from the first
-- vertex), tip (-1 or 1 at the crest's first or last vertex: the opening also clears the end cap),
-- vertex (an interior crest vertex the opening sits on: it opens across the bend's bisector) and maps
-- (the maps that open it). Degrees throughout.
return {
  ranges = {
    {
      id = "alps", name = "Alps", crest_km = 1016.3,
      crest = {
        {44.3343, 8.3491}, {44.1492, 7.5619}, {44.6675, 7.0917}, {45.2603, 6.9008}, {45.8328, 6.865}, {45.8689, 7.1706},
        {45.9369, 7.8667}, {46.2517, 8.0333}, {46.5562, 8.5678}, {46.3822, 9.9081}, {46.8853, 10.8672},
        {47.0033, 11.5075}, {47.0749, 12.6952}, {47.2667, 13.7617}, {47.6325, 15.8297},
      },
      heights = {
        436, 1871, 3841, 2081, 4808, 2469, 4634, 2005, 2106, 4049, 3768, 1370, 3798, 2862, 985,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
      },
      openings = {
        {kind = "pass", id = "cadibona", seg = 1, arc_km = 0, lat = 44.3343, lon = 8.3491, tip = -1,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "col_de_tende", seg = 2, arc_km = 66, lat = 44.1492, lon = 7.5619, vertex = 2,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "montgenevre", seg = 3, arc_km = 169.7, lat = 44.9746036, lon = 6.9928031,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "mont_cenis", seg = 4, arc_km = 202.3, lat = 45.2603, lon = 6.9008, vertex = 4,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "little_st_bernard", seg = 4, arc_km = 249, lat = 45.6800402, lon = 6.8745525,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "great_st_bernard", seg = 6, arc_km = 290, lat = 45.8689, lon = 7.1706, vertex = 6,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "simplon", seg = 8, arc_km = 381.7, lat = 46.2517, lon = 8.0333, vertex = 8,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "gotthard", seg = 9, arc_km = 434.8, lat = 46.5562, lon = 8.5678, vertex = 9,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "splugen", seg = 9, arc_km = 493.3, lat = 46.4588294, lon = 9.3178334,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "reschen", seg = 10, arc_km = 607, lat = 46.7517998, lon = 10.6126978,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "brenner", seg = 12, arc_km = 681.8, lat = 47.0033, lon = 11.5075, vertex = 12,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "semmering", seg = 14, arc_km = 1016.3, lat = 47.6325, lon = 15.8297, tip = 1,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "pyrenees", name = "Pyrenees", crest_km = 448.5,
      crest = {
        {43.3092, -1.6356}, {43.0203, -1.3239}, {42.945, -0.7211}, {42.7936, -0.5458}, {42.8386, -0.29},
        {42.7767, -0.1431}, {42.6667, 0.0333}, {42.6322, 0.6578}, {42.6672, 1.3972}, {42.3833, 2.1167},
        {42.4639, 2.8656}, {42.3192, 3.3219},
      },
      heights = {
        905, 1057, 2504, 1632, 3144, 3298, 3355, 3404, 3143, 2910, 290, 100,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
      },
      openings = {
        {kind = "pass", id = "roncevaux", seg = 2, arc_km = 40.9, lat = 43.0203, lon = -1.3239, vertex = 2,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "somport", seg = 4, arc_km = 112.7, lat = 42.7936, lon = -0.5458, vertex = 4,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "puymorens", seg = 9, arc_km = 314.1, lat = 42.5169136, lon = 1.7780773,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "le_perthus", seg = 11, arc_km = 407.7, lat = 42.4639, lon = 2.8656, vertex = 11,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "carpathians", name = "Carpathian Mountains", crest_km = 1319.1,
      crest = {
        {48.1736, 16.9783}, {48.4167, 17.25}, {49.5833, 19.5333}, {49.164, 20.134}, {49.418, 21.696},
        {49.0028, 22.8875}, {48.8271, 23.1758}, {48.16, 24.5003}, {47.538, 24.6972}, {46.955, 25.9457},
        {45.5128, 25.5722}, {45.6, 24.7378}, {45.3411, 23.5406}, {45.3661, 22.8944}, {44.6711, 22.5297},
      },
      heights = {
        212, 768, 1725, 2656, 502, 889, 841, 2061, 2303, 1907, 1033, 2544, 2519, 2509, 100,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14},
      },
      openings = {
        {kind = "gap", id = "carpathians_gap_1", seg = 2, arc_km = 139.2, lat = 49, lon = 18.39165,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "dukla", seg = 5, arc_km = 425.3, lat = 49.418, lon = 21.696, vertex = 5,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "uzhok", seg = 6, arc_km = 523.4, lat = 49.0028, lon = 22.8875, vertex = 6,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "verecke", seg = 7, arc_km = 552.1, lat = 48.8271, lon = 23.1758, vertex = 7,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "tihuta", seg = 9, arc_km = 782.1, lat = 47.3510356, lon = 25.0975861,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "predeal", seg = 11, arc_km = 1022.7, lat = 45.5128, lon = 25.5722, vertex = 11,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "turnu_rosu", seg = 12, arc_km = 1125.2, lat = 45.5024863, lon = 24.286879,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "iron_gates", seg = 14, arc_km = 1319.1, lat = 44.6711, lon = 22.5297, tip = 1,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "caucasus", name = "Greater Caucasus", crest_km = 1197.6,
      crest = {
        {45.2, 37.2}, {43.9411, 39.9019}, {43.2436, 41.7272}, {43.355, 42.4392}, {43.0006, 43.1122}, {42.7061, 43.7931},
        {42.6992, 44.5183}, {42.5733, 45.3175}, {41.2244, 47.8583}, {41.2725, 48.0044}, {40.4639, 49.9583},
      },
      heights = {
        100, 2867, 4046, 5642, 5193, 2911, 5054, 4493, 4466, 4243, 100,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "gap", id = "caucasus_gap_1", seg = 2, arc_km = 327.9, lat = 43.6383433, lon = 40.6941894,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "edge", id = "caucasus_edge_europe_1", seg = 3, arc_km = 470.3, lat = 43.3349626, lon = 42.3111333,
         maps = {"europe"}},
        {kind = "pass", id = "mamison", seg = 6, arc_km = 612.6, lat = 42.7061, lon = 43.7931, vertex = 6,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "jvari", seg = 6, arc_km = 666.9, lat = 42.6997793, lon = 44.4574142,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "darial", seg = 7, arc_km = 679.1, lat = 42.6855961, lon = 44.6046563,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "caucasus_gap_2", seg = 8, arc_km = 897.3, lat = 41.7451336, lon = 46.8774416,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "derbent", seg = 10, arc_km = 1197.6, lat = 40.4640481, lon = 49.9579421, tip = 1,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "scandinavian", name = "Scandinavian Mountains (Scandes)", crest_km = 1273.7,
      crest = {
        {60.05, 7.4167}, {60.5333, 7.4167}, {61.0539, 8.2144}, {61.6364, 8.3125}, {62.3198, 9.2677}, {63.0202, 12.1988},
        {66.0122, 14.3386}, {67.133, 16.0766}, {67.9044, 18.5283}, {69.06, 20.5486}, {69.3228, 21.2789},
      },
      heights = {
        1200, 1863, 1000, 2469, 2286, 1762, 1916, 1908, 2097, 500, 1365,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "pass", id = "filefjell", seg = 3, arc_km = 126, lat = 61.0539, lon = 8.2144, vertex = 3,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "hjerkinn", seg = 5, arc_km = 289.8, lat = 62.3525674, lon = 9.4048283,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "scandinavian_gap_1", seg = 6, arc_km = 581.7, lat = 64.1477957, lon = 13.0052269,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "scandinavian_gap_2", seg = 7, arc_km = 909.4, lat = 66.8599625, lon = 15.6532068,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "apennines", name = "Apennine Mountains", crest_km = 1071.4,
      crest = {
        {44.3343, 8.3491}, {44.5506, 8.8878}, {44.4716, 9.9283}, {44.2883, 10.3912}, {44.1939, 10.7014},
        {44.0935, 11.2782}, {43.8667, 11.7}, {42.8167, 13.2667}, {42.4692, 13.5656}, {42.0869, 14.0875},
        {41.4333, 14.3667}, {39.8947, 16.2175}, {38.1589, 15.9211},
      },
      heights = {
        436, 772, 1041, 2121, 2165, 903, 1654, 2476, 2912, 2793, 2050, 2248, 1955,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
      },
      openings = {
        {kind = "pass", id = "cisa", seg = 3, arc_km = 132, lat = 44.4716, lon = 9.9283, vertex = 3,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "futa", seg = 6, arc_km = 248.3, lat = 44.0935, lon = 11.2782, vertex = 6,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "apennines_gap_1", seg = 7, arc_km = 376.6, lat = 43.3417, lon = 12.48335,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "apennines_gap_2", seg = 11, arc_km = 724, lat = 40.9093587, lon = 14.9969551,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "balkan", name = "Balkan Mountains (Stara Planina)", crest_km = 507.9,
      crest = {
        {43.8347, 22.3692}, {43.3939, 22.6817}, {43.1225, 23.1253}, {43.0433, 23.3528}, {42.8331, 23.6685},
        {42.7806, 24.6058}, {42.7175, 24.9167}, {42.7667, 25.3167}, {42.9175, 26.4506}, {42.7014, 27.8997},
      },
      heights = {
        1000, 2169, 1444, 400, 1687, 1520, 2376, 1185, 700, 60,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9},
      },
      openings = {
        {kind = "pass", id = "petrohan", seg = 3, arc_km = 102, lat = 43.1225, lon = 23.1253, vertex = 3,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "iskar", seg = 4, arc_km = 122.5, lat = 43.0433, lon = 23.3528, vertex = 4,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "beklemeto", seg = 6, arc_km = 233.9, lat = 42.7806, lon = 24.6058, vertex = 6,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "shipka", seg = 8, arc_km = 293.4, lat = 42.7667, lon = 25.3167, vertex = 8,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "pass", id = "kotel", seg = 9, arc_km = 387.3, lat = 42.9175, lon = 26.4506, vertex = 9,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "dinaric", name = "Dinaric Alps", crest_km = 604.7,
      crest = {
        {45.7833, 14.2167}, {45.5815, 14.4315}, {45.4283, 14.745}, {44.3673, 15.5046}, {43.9451, 16.5969},
        {43.1281, 19.0347}, {42.442, 19.8126},
      },
      heights = {
        609, 1796, 1528, 1757, 1831, 2523, 2694,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6},
        atlantic = {1, 2, 3, 4, 5, 6},
        olde_world = {1, 2, 3, 4, 5, 6},
      },
      openings = {
        {kind = "pass", id = "postojna", seg = 1, arc_km = 0, lat = 45.7833, lon = 14.2167, tip = -1,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "dinaric_gap_1", seg = 5, arc_km = 344.5, lat = 43.7356572, lon = 17.2218446,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "urals", name = "Ural Mountains", crest_km = 2413.4,
      crest = {
        {69.2036, 62.6078}, {66.7208, 64.3917}, {65.0333, 60.1167}, {63.9185, 59.1805}, {59.5167, 59.05},
        {54.515, 58.84}, {54.255, 58.102}, {48.65, 58.55},
      },
      heights = {
        423, 1472, 1894, 1617, 1519, 1582, 1640, 657,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7},
        olde_world = {1, 2, 3, 4, 5, 6, 7},
      },
      openings = {
        {kind = "gap", id = "urals_gap_1", seg = 1, arc_km = 146.3, lat = 67.9331083, lon = 63.5206525,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "urals_gap_2", seg = 2, arc_km = 476.5, lat = 65.5295185, lon = 61.3737869,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "urals_gap_3", seg = 4, arc_km = 841.6, lat = 62.5347202, lon = 59.1394751,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "babinov", seg = 5, arc_km = 1206.7, lat = 59.2516689, lon = 59.0388725,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "urals_gap_4", seg = 5, arc_km = 1410.1, lat = 57.4233733, lon = 58.9621102,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "urals_gap_5", seg = 5, arc_km = 1673.5, lat = 55.0550389, lon = 58.8626739,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "urals_gap_6", seg = 7, arc_km = 2043.4, lat = 51.9730911, lon = 58.2843899,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "atlas", name = "Atlas Mountains (High Atlas, Saharan Atlas, Aures)", crest_km = 2091.2,
      crest = {
        {30.4214, -9.5831}, {31.0596, -7.9151}, {31.2858, -7.3808}, {31.5083, -6.4433}, {32.4778, -4.9269},
        {32.8667, 0.4833}, {34.05, 2.0667}, {34.6667, 3.4}, {35.3183, 6.6375}, {35.2067, 8.6831}, {36.75, 10.75},
      },
      heights = {
        200, 4167, 2260, 4071, 3747, 2236, 1700, 1500, 2328, 1544, 100,
      },
      segments = {
        europe = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "pass", id = "tizi_n_tichka", seg = 3, arc_km = 231.2, lat = 31.2858, lon = -7.3808, vertex = 3,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "atlas_gap_1", seg = 5, arc_km = 566.9, lat = 32.5269889, lon = -4.2426067,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "atlas_gap_2", seg = 5, arc_km = 929, lat = 32.804113, lon = -0.3873825,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "edge", id = "atlas_edge_europe_1", seg = 7, arc_km = 1211.8, lat = 34.0666333, lon = 2.1026611,
         maps = {"europe"}},
        {kind = "gap", id = "atlas_gap_3", seg = 7, arc_km = 1310.1, lat = 34.4987401, lon = 3.0368722,
         maps = {"europe", "atlantic", "olde_world"}},
        {kind = "gap", id = "atlas_gap_4", seg = 9, arc_km = 1700.6, lat = 35.2891296, lon = 7.1721863,
         maps = {"europe", "atlantic", "olde_world"}},
      },
    },
    {
      id = "zagros", name = "Zagros Mountains", crest_km = 1610.6,
      crest = {
        {36.7342, 44.8625}, {33.2211, 47.105}, {33.3403, 49.3044}, {32.3644, 50.0775}, {30.95, 51.4333},
        {30.7083, 51.5986}, {27.1961, 56.2878},
      },
      heights = {
        3607, 2790, 4070, 4221, 4409, 2200, 100,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6},
        olde_world = {1, 2, 3, 4, 5, 6},
      },
      openings = {
        {kind = "gap", id = "zagros_gap_1", seg = 1, arc_km = 305.1, lat = 34.3026386, lon = 46.4146267,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "zagros_gap_2", seg = 3, arc_km = 675.4, lat = 33.1178777, lon = 49.4806011,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "persian_gates", seg = 6, arc_km = 1010.2, lat = 30.7083, lon = 51.5986, vertex = 6,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "zagros_gap_3", seg = 6, arc_km = 1310.4, lat = 28.9521376, lon = 53.9432833,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "hindu_kush", name = "Hindu Kush", crest_km = 690.6,
      crest = {
        {34.6453, 67.6242}, {35.3137, 69.0371}, {35.6631, 69.7873}, {36.2542, 71.8433}, {36.4317, 71.8283},
        {37.0872, 74.4842},
      },
      heights = {
        5050, 3878, 3848, 7708, 7492, 4923,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5},
        olde_world = {1, 2, 3, 4, 5},
      },
      openings = {
        {kind = "pass", id = "salang", seg = 2, arc_km = 148.6, lat = 35.3137, lon = 69.0371, vertex = 2,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "khawak", seg = 3, arc_km = 226.9, lat = 35.6631, lon = 69.7873, vertex = 3,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "hindu_kush_gap_1", seg = 5, arc_km = 535, lat = 36.6751093, lon = 72.8145253,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "wakhjir", seg = 5, arc_km = 690.6, lat = 37.0871849, lon = 74.4841388, tip = 1,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "himalaya", name = "Himalayas", crest_km = 2312.4,
      crest = {
        {35.2375, 74.5892}, {34.2789, 75.4719}, {30.3758, 79.9708}, {28.6961, 83.4953}, {28.5961, 83.8203},
        {27.9883, 86.9253}, {27.7025, 88.1467}, {27.8242, 89.27}, {28.0483, 90.4542}, {28.2275, 90.6167},
        {29.6292, 95.0558},
      },
      heights = {
        8126, 3528, 7816, 8167, 8091, 8849, 8586, 7326, 7570, 7538, 7782,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        olde_world = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "pass", id = "zoji_la", seg = 2, arc_km = 133.7, lat = 34.2789, lon = 75.4719, vertex = 2,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "himalaya_gap_1", seg = 2, arc_km = 496.9, lat = 31.9384997, lon = 78.1695575,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "himalaya_gap_2", seg = 3, arc_km = 878.4, lat = 29.7749158, lon = 81.2316301,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "himalaya_gap_3", seg = 5, arc_km = 1269.2, lat = 28.3862971, lon = 84.8920966,
         maps = {"atlantic", "olde_world"}},
        {kind = "pass", id = "nathu_la", seg = 7, arc_km = 1660, lat = 27.7709604, lon = 88.7785944,
         maps = {"atlantic", "olde_world"}},
        {kind = "gap", id = "himalaya_gap_4", seg = 10, arc_km = 1986.2, lat = 28.6335038, lon = 91.9024897,
         maps = {"atlantic", "olde_world"}},
      },
    },
    {
      id = "appalachians", name = "Appalachian Mountains", crest_km = 3031.8,
      crest = {
        {33.4855, -85.8087}, {35.5628, -83.4986}, {35.7648, -82.2651}, {36.6598, -81.5446}, {38.6997, -79.5328},
        {40.9677, -75.1199}, {42.6373, -73.166}, {44.2705, -71.3033}, {45.9044, -68.9213}, {48.9872, -65.9486},
        {49.325, -57.8042},
      },
      heights = {
        735, 2025, 2037, 1746, 1482, 100, 1064, 1917, 1606, 1268, 814,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
      },
      openings = {
        {kind = "pass", id = "cumberland_gap", seg = 2, arc_km = 321.2, lat = 35.5769168, lon = -83.412397,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_1", seg = 4, arc_km = 633.4, lat = 37.2822806, lon = -80.9306942,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_2", seg = 5, arc_km = 960, lat = 39.3334699, lon = -78.2996592,
         maps = {"atlantic"}},
        {kind = "pass", id = "delaware_water_gap", seg = 6, arc_km = 1286.6, lat = 40.9677, lon = -75.1199, vertex = 6,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_3", seg = 7, arc_km = 1609.8, lat = 43.1693506, lon = -72.5591848,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_4", seg = 8, arc_km = 1920.8, lat = 45.2234186, lon = -69.9140766,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_5", seg = 9, arc_km = 2276.3, lat = 47.7641923, lon = -67.1279289,
         maps = {"atlantic"}},
        {kind = "gap", id = "appalachians_gap_6", seg = 10, arc_km = 2654, lat = 49.1098797, lon = -62.9907768,
         maps = {"atlantic"}},
      },
    },
    {
      id = "rockies", name = "Rocky Mountains", crest_km = 2329.4,
      crest = {
        {53.1106, -119.1564}, {52.8925, -118.4639}, {52.1472, -117.4417}, {51.4525, -116.2858}, {48.5731, -113.5167},
        {48.3183, -113.3552}, {44.9742, -113.445}, {43.1842, -109.6542}, {42.3303, -108.9738}, {40.255, -105.6151},
        {39.1178, -106.4453}, {36.5569, -105.4169},
      },
      heights = {
        3954, 1131, 3747, 1625, 2444, 1589, 2260, 4209, 2301, 4346, 4401, 4013,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
      },
      openings = {
        {kind = "pass", id = "yellowhead", seg = 2, arc_km = 52.3, lat = 52.8925, lon = -118.4639, vertex = 2,
         maps = {"atlantic"}},
        {kind = "pass", id = "kicking_horse", seg = 4, arc_km = 271.1, lat = 51.4525, lon = -116.2858, vertex = 4,
         maps = {"atlantic"}},
        {kind = "gap", id = "rockies_gap_1", seg = 4, arc_km = 462.7, lat = 49.9859299, lon = -114.8754092,
         maps = {"atlantic"}},
        {kind = "pass", id = "marias", seg = 6, arc_km = 678.1, lat = 48.3183, lon = -113.3552, vertex = 6,
         maps = {"atlantic"}},
        {kind = "pass", id = "lemhi", seg = 7, arc_km = 1050, lat = 44.9742, lon = -113.445, vertex = 7,
         maps = {"atlantic"}},
        {kind = "gap", id = "rockies_gap_2", seg = 7, arc_km = 1267.4, lat = 43.9004525, lon = -111.1710548,
         maps = {"atlantic"}},
        {kind = "pass", id = "south_pass", seg = 9, arc_km = 1522.4, lat = 42.3303, lon = -108.9738, vertex = 9,
         maps = {"atlantic"}},
        {kind = "gap", id = "rockies_gap_3", seg = 9, arc_km = 1707.5, lat = 41.2725882, lon = -107.2619817,
         maps = {"atlantic"}},
        {kind = "gap", id = "rockies_gap_4", seg = 10, arc_km = 1980, lat = 39.5148102, lon = -106.1554672,
         maps = {"atlantic"}},
      },
    },
    {
      id = "andes", name = "Andes", crest_km = 7334.8,
      crest = {
        {8.5417, -71.0458}, {2.93, -76.03}, {-0.6806, -78.4378}, {-1.4692, -78.8175}, {-9.1217, -77.6042},
        {-16.6333, -67.7908}, {-18.1081, -68.8831}, {-27.1097, -68.5414}, {-32.6531, -70.0117}, {-41.1608, -71.8875},
        {-46.595, -73.3458}, {-49.2713, -73.0432},
      },
      heights = {
        4978, 5364, 5897, 6263, 6768, 6438, 6542, 6893, 6961, 3470, 4058, 3405,
      },
      segments = {
        atlantic = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
      },
      openings = {
        {kind = "gap", id = "andes_gap_1", seg = 1, arc_km = 338.3, lat = 6.2615393, lon = -73.0709932,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_2", seg = 1, arc_km = 707.5, lat = 3.773448, lon = -75.2808663,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_3", seg = 2, arc_km = 1092, lat = 0.9886655, lon = -77.3246173,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_4", seg = 4, arc_km = 1484.3, lat = -2.1078302, lon = -78.7162455,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_5", seg = 4, arc_km = 1880.5, lat = -5.6269131, lon = -78.1582967,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_6", seg = 5, arc_km = 2278.5, lat = -9.1476129, lon = -77.5703466,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_7", seg = 5, arc_km = 2677.6, lat = -11.3650437, lon = -74.6734224,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_8", seg = 5, arc_km = 3077.1, lat = -13.5851531, lon = -71.7729988,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_9", seg = 5, arc_km = 3476.8, lat = -15.8066019, lon = -68.8708255,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_10", seg = 7, arc_km = 3876.7, lat = -18.5600971, lon = -68.8659422,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_11", seg = 7, arc_km = 4276.7, lat = -22.1546372, lon = -68.7294938,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_12", seg = 7, arc_km = 4676.6, lat = -25.7494481, lon = -68.5930351,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_13", seg = 8, arc_km = 5076.6, lat = -29.2889639, lon = -69.1194156,
         maps = {"atlantic"}},
        {kind = "pass", id = "uspallata", seg = 9, arc_km = 5476.6, lat = -32.7962343, lon = -70.0432586,
         maps = {"atlantic"}},
        {kind = "pass", id = "los_libertadores", seg = 9, arc_km = 5480.8, lat = -32.8334349, lon = -70.0514607,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_14", seg = 9, arc_km = 5807.8, lat = -35.7299459, lon = -70.6900911,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_15", seg = 9, arc_km = 6171.3, lat = -38.9496579, lon = -71.3999816,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_16", seg = 10, arc_km = 6553.1, lat = -42.3273641, lon = -72.2005544,
         maps = {"atlantic"}},
        {kind = "gap", id = "andes_gap_17", seg = 10, arc_km = 6944, lat = -45.7788073, lon = -73.1267698,
         maps = {"atlantic"}},
      },
    },
  },
}
