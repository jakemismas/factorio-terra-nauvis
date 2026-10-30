-- Vanilla autoplace Earth restores beside Alien Biomes (ARCHITECTURE.md, "Stable hooks"; milestone
-- trees-forests; R3 3.4 items 3 to 6; S3 section 5; design note 10).
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through
-- tools/tnconfig.py's loader. Alien Biomes nils the autoplace of the 15 living vanilla trees, the three
-- vanilla rock entities and eight rock and decal decoratives in its data stage, before any mod that
-- loads after it can read them, so Earth keeps the base game's own texts here, as Factorio 2.1.23
-- (build 87750) loads them (--dump-data of the base game with Terra Nauvis, which changes none of them):
--   trees     each living tree's probability expression (base/prototypes/entity/trees.lua:3929-4215, the
--             named expressions tree_01 to tree_09_red) and its autoplace order and richness
--             (trees.lua:4271-4363); trees.lua builds each restored tree's Earth body from its text
--   rocks     the autoplace of huge-rock, big-rock and big-sand-rock (simple entities) and of the rock
--             and decal decoratives (base/prototypes/decorative/decoratives.lua:4345, 4506, 4669, 4790,
--             4943, 5104, 5260, 5415, 5574, 6357 and 6558)
--   relist    vanilla decoratives Alien Biomes keeps with their autoplace but takes off Nauvis
--             (AB/prototypes/disables.lua:21-51, AB/prototypes/decorative/vegetation.lua:43-54)
--   extend    vanilla decoratives Alien Biomes restricts to its own tiles (AB vegetation.lua:15-35,
--             AB rocks.lua:56-107), and vanilla's dead and dry trees, which AB restricts the same way
-- The texts are the base game's; they read the base game's shared helpers (trees_forest_path_cutout_faded,
-- tree_small_noise, rock_density, the core range and ramp functions) by name, as its own entities do.
-- The T16 dump facts compare every text here with the dumped base game (a game update changes them).
-- A released table version is never edited: a changed row ships as the next version (versioning rule 5).
return {
  version = 1,
  game = "2.1.23",
  trees = {
    {
      tree = "tree-01", expression = "tree_01", control = "trees",
      order = "a[tree]-b[forest]-a[wet]-c[cold]",
      text = "min(0.45, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=0, \z
        from_top=10, to_top=14, to_bottom=15},asymmetric_ramps{input=moisture, from_bottom=0.6, from_top=0.7, \z
        to_top=1, to_bottom=2})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * 0.1+ \z
        multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-01',octaves = 3,input_scale \z
        = 1/25 * control:trees:frequency,output_scale = 0.8})",
    },
    {
      tree = "tree-02", expression = "tree_02", control = "trees",
      order = "a[tree]-b[forest]-b[moist]-b[cold]",
      text = "min(0.4, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=0, \z
        from_top=10, to_top=14, to_bottom=15},asymmetric_ramps{input=moisture, from_bottom=0.4, from_top=0.5, \z
        to_top=0.7, to_bottom=0.8})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-02',octaves = \z
        3,input_scale = 1/25 * control:trees:frequency,output_scale = 0.75})",
    },
    {
      tree = "tree-02-red", expression = "tree_02_red", control = "trees",
      order = "a[tree]-b[forest]-c[medium]-b[cold]",
      text = "min(0.3, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=0, \z
        from_top=10, to_top=14, to_bottom=15},asymmetric_ramps{input=moisture, from_bottom=0.2, from_top=0.3, \z
        to_top=0.5, to_bottom=0.6})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-02-red',octaves = \z
        3,input_scale = 1/25 * control:trees:frequency,output_scale = 0.7})",
    },
    {
      tree = "tree-03", expression = "tree_03", control = "trees",
      order = "a[tree]-b[forest]-b[moist]-c[hot]",
      text = "min(0.4, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=15, \z
        from_top=16, to_top=35, to_bottom=45},asymmetric_ramps{input=moisture, from_bottom=0.4, from_top=0.5, \z
        to_top=0.7, to_bottom=0.8})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-03',octaves = \z
        3,input_scale = 1/35 * control:trees:frequency,output_scale = 0.75})",
    },
    {
      tree = "tree-04", expression = "tree_04", control = "trees",
      order = "a[tree]-b[forest]-a[wet]-b[medium]",
      text = "min(0.45, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=13, \z
        from_top=14, to_top=16, to_bottom=17},asymmetric_ramps{input=moisture, from_bottom=0.7, from_top=0.9, \z
        to_top=1, to_bottom=2})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * 0.1+ \z
        multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-04',octaves = 3,input_scale \z
        = 1/30 * control:trees:frequency,output_scale = 0.8})",
    },
    {
      tree = "tree-05", expression = "tree_05", control = "trees",
      order = "a[tree]-b[forest]-a[wet]-a[hot]",
      text = "min(0.45, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=15, \z
        from_top=16, to_top=35, to_bottom=45},asymmetric_ramps{input=moisture, from_bottom=0.6, from_top=0.7, \z
        to_top=1, to_bottom=2})+ min(0, distance/20 - 3)- 0.45 + 0.2 * control:trees:size+ tree_small_noise * 0.1+ \z
        multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-05',octaves = 3,input_scale \z
        = 1/40 * control:trees:frequency,output_scale = 0.8})",
    },
    {
      tree = "tree-06", expression = "tree_06", control = "trees",
      order = "a[tree]-b[forest]-d[dry]-c[cold]",
      text = "min(0.2, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=0, \z
        from_top=10, to_top=14, to_bottom=15},asymmetric_ramps{input=moisture, from_bottom=0.1, from_top=0.2, \z
        to_top=0.3, to_bottom=0.4})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-06',octaves = \z
        3,input_scale = 1/22 * control:trees:frequency,output_scale = 0.6})",
    },
    {
      tree = "tree-06-brown", expression = "tree_06_brown", control = "trees",
      order = "a[tree]-b[forest]-e[verydry]-c[cold]",
      text = "min(0.1, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=0, \z
        from_top=10, to_top=14, to_bottom=15},asymmetric_ramps{input=moisture, from_bottom=0, from_top=0.1, \z
        to_top=0.2, to_bottom=0.3})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-06-brown',octaves = \z
        3,input_scale = 1/22 * control:trees:frequency,output_scale = 0.5})",
    },
    {
      tree = "tree-07", expression = "tree_07", control = "trees",
      order = "a[tree]-b[forest]-b[moist]-a[medium]",
      text = "min(0.4, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=13, \z
        from_top=14, to_top=16, to_bottom=17},asymmetric_ramps{input=moisture, from_bottom=0.5, from_top=0.6, \z
        to_top=0.9, to_bottom=1})+ min(0, distance/20 - 3)- 0.45 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-07',octaves = \z
        3,input_scale = 1/40 * control:trees:frequency,output_scale = 0.75})",
    },
    {
      tree = "tree-08", expression = "tree_08", control = "trees",
      order = "a[tree]-b[forest]-c[medium]-a[medium]",
      text = "min(0.3, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=13, \z
        from_top=14, to_top=16, to_bottom=17},asymmetric_ramps{input=moisture, from_bottom=0.3, from_top=0.4, \z
        to_top=0.6, to_bottom=0.7})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-08',octaves = \z
        3,input_scale = 1/30 * control:trees:frequency,output_scale = 0.7})",
    },
    {
      tree = "tree-08-brown", expression = "tree_08_brown", control = "trees",
      order = "a[tree]-b[forest]-d[dry]-b[medium]",
      text = "min(0.2, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=13, \z
        from_top=14, to_top=16, to_bottom=17},asymmetric_ramps{input=moisture, from_bottom=0.2, from_top=0.3, \z
        to_top=0.4, to_bottom=0.5})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-08-brown',octaves = \z
        3,input_scale = 1/30 * control:trees:frequency,output_scale = 0.6})",
    },
    {
      tree = "tree-08-red", expression = "tree_08_red", control = "trees",
      order = "a[tree]-b[forest]-e[verydry]-b[medium]",
      text = "min(0.1, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=13, \z
        from_top=14, to_top=16, to_bottom=17},asymmetric_ramps{input=moisture, from_bottom=0.1, from_top=0.2, \z
        to_top=0.3, to_bottom=0.4})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-08-red',octaves = \z
        3,input_scale = 1/30 * control:trees:frequency,output_scale = 0.5})",
    },
    {
      tree = "tree-09", expression = "tree_09", control = "trees",
      order = "a[tree]-b[forest]-c[medium]-c[hot]",
      text = "min(0.3, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=15, \z
        from_top=16, to_top=35, to_bottom=45},asymmetric_ramps{input=moisture, from_bottom=0.2, from_top=0.3, \z
        to_top=0.5, to_bottom=0.6})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-09',octaves = \z
        3,input_scale = 1/25 * control:trees:frequency,output_scale = 0.7})",
    },
    {
      tree = "tree-09-brown", expression = "tree_09_brown", control = "trees",
      order = "a[tree]-b[forest]-d[dry]-a[hot]",
      text = "min(0.2, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=15, \z
        from_top=16, to_top=35, to_bottom=45},asymmetric_ramps{input=moisture, from_bottom=0.1, from_top=0.2, \z
        to_top=0.3, to_bottom=0.4})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-09-brown',octaves = \z
        3,input_scale = 1/25 * control:trees:frequency,output_scale = 0.6})",
    },
    {
      tree = "tree-09-red", expression = "tree_09_red", control = "trees",
      order = "a[tree]-b[forest]-e[verydry]-a[hot]",
      text = "min(0.1, trees_forest_path_cutout_faded,min(0,asymmetric_ramps{input=temperature, from_bottom=15, \z
        from_top=16, to_top=35, to_bottom=45},asymmetric_ramps{input=moisture, from_bottom=0, from_top=0.1, \z
        to_top=0.2, to_bottom=0.3})+ min(0, distance/20 - 3)- 0.5 + 0.2 * control:trees:size+ tree_small_noise * \z
        0.1+ multioctave_noise{x = x,y = y,persistence = 0.65,seed0 = map_seed,seed1 = 'tree-09-red',octaves = \z
        3,input_scale = 1/25 * control:trees:frequency,output_scale = 0.5})",
    },
  },
  tree_richness = "clamp(random_penalty_at(6, 1), 0, 1)",
  rocks = {
    {
      type = "simple-entity", name = "huge-rock",
      control = "rocks", order = "a[doodad]-a[rock]-a[huge]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        control = "control:rocks:size",
        multiplier = 0.07,
        penalty = 1.7,
        region_box = "range_select_base(moisture, 0.35, 1, 0.2, -10, 0)",
      },
    },
    {
      type = "simple-entity", name = "big-rock",
      control = "rocks", order = "a[doodad]-a[rock]-b[big]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        control = "control:rocks:size",
        multiplier = 0.17,
        penalty = 1.6,
        region_box = "range_select_base(moisture, 0.35, 1, 0.2, -10, 0)",
      },
    },
    {
      type = "simple-entity", name = "big-sand-rock",
      control = "rocks", order = "a[doodad]-a[rock]-b[big]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        aux_range = "range_select_base(aux, 0.3, 1, 0.3, -10, 0)",
        control = "control:rocks:size",
        moisture_range = "range_select_base(moisture, 0, 0.3, 0.2, -10, 0)",
        multiplier = 0.1,
        penalty = 1.6,
        region_box = "min(aux_range, moisture_range)",
      },
    },
    {
      type = "optimized-decorative", name = "medium-rock",
      control = "rocks", order = "a[doodad]-a[rock]-c[medium]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        control = "control:rocks:size",
        multiplier = 0.4,
        penalty = 1.4,
        region_box = "range_select_base(moisture, 0.35, 1, 0.2, -10, 0)",
      },
    },
    {
      type = "optimized-decorative", name = "small-rock",
      control = "rocks", order = "a[doodad]-a[rock]-d[small]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        control = "control:rocks:size",
        multiplier = 0.5,
        penalty = 1.3,
        region_box = "range_select_base(moisture, 0.35, 1, 0.2, -10, 0)",
      },
    },
    {
      type = "optimized-decorative", name = "tiny-rock",
      control = "rocks", order = "a[doodad]-a[rock]-e[tiny]", placement_density = 2,
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        control = "control:rocks:size",
        multiplier = 0.5,
        penalty = 1.2,
        region_box = "range_select_base(moisture, 0.35, 1, 0.2, -10, 0)",
      },
    },
    {
      type = "optimized-decorative", name = "medium-sand-rock",
      control = "rocks", order = "a[doodad]-a[rock]-c[medium]",
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        aux_range = "range_select_base(aux, 0.3, 1, 0.3, -10, 0)",
        control = "control:rocks:size",
        moisture_range = "range_select_base(moisture, 0, 0.3, 0.2, -10, 0)",
        multiplier = 0.3,
        penalty = 1.5,
        region_box = "min(aux_range, moisture_range)",
      },
    },
    {
      type = "optimized-decorative", name = "small-sand-rock",
      control = "rocks", order = "a[doodad]-a[rock]-d[small]", placement_density = 2,
      probability_expression = "multiplier * control * (region_box + rock_density - penalty)",
      local_expressions = {
        aux_range = "range_select_base(aux, 0.3, 1, 0.3, -10, 0)",
        control = "control:rocks:size",
        moisture_range = "range_select_base(moisture, 0, 0.3, 0.2, -10, 0)",
        multiplier = 0.5,
        penalty = 1.4,
        region_box = "min(aux_range, moisture_range)",
      },
    },
    {
      type = "optimized-decorative", name = "red-desert-decal",
      probability_expression = "clamp(-1.5 + noise_layer_noise('red-desert-decal')+ min(range_select(moisture, 0.3, \z
        0.7, 0.05, -1, 1),range_select(aux, 0.7, 1, 0.05, -1, 1)),0, 0.01)",
    },
    {
      type = "optimized-decorative", name = "sand-decal",
      probability_expression = "clamp(-1.5 + noise_layer_noise('sand-decal')+ min(range_select(moisture, 0.1, 1, \z
        0.05, -1, 1),range_select(aux, 0.4, 0.9, 0.05, -1, 1)),0, 0.01)",
    },
    {
      type = "optimized-decorative", name = "sand-dune-decal",
      probability_expression = "-0.8 - 0.4 * min(0.5, abs(grass_noise)) + 0.04 * noise_layer_noise('sand-decal')+ \z
        min(range_select(moisture, 0, 0.15, 0.4, -10, 1),range_select(aux, 0.0, 0.25, 0.4, -10, 1))",
    },
  },
  relist = {
    "light-mud-decal", "green-asterisk", "green-asterisk-mini", "green-bush-mini", "green-carpet-grass",
    "green-croton", "green-desert-bush", "green-hairy-grass", "green-pita", "green-pita-mini",
    "green-small-grass",
  },
  extend = {
    "brown-asterisk", "brown-asterisk-mini", "brown-carpet-grass", "brown-fluff", "brown-fluff-dry",
    "brown-hairy-grass", "cracked-mud-decal", "dark-mud-decal", "red-asterisk", "red-croton",
    "red-desert-bush", "red-pita", "white-desert-bush",
  },
  dead_trees = {"dead-dry-hairy-tree", "dead-grey-trunk", "dead-tree-desert", "dry-hairy-tree", "dry-tree"},
}
