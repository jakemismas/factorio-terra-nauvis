-- Terra Nauvis: the single source of names and constants (ARCHITECTURE.md, "Module map").
--
-- Pure data: this file reads no data, settings, game or script and calls no function, so the
-- settings, data and control stages (through require) and the Python tools (tools/tnconfig.py,
-- through luaparser) all read this one file. Every name the mod defines derives from ID or NOISE,
-- so renaming the mod is an edit here. No other Lua file spells an Earth name or a map
-- coordinate (the static name scan and the design rules check it).

local ID = "terra-nauvis"
local NOISE = "tn_"

-- The scale lists. A version in a v* tag was built on `released`: waterways.lua loops a version's list and writes it
-- into frozen text, and a landed row never changes, so a version without `scales` reads `released`. `offered` is what
-- the setting lists, and a version that is not yet released names it as its `scales`. Names and files by scale are
-- lists in the order of the version's own list, so a scale is a value and never a position.
local SCALE_LISTS = {released = {1, 2, 3, 4, 5, 6}, offered = {1, 2, 3, 4, 5, 6, 12, 24}}

-- Per-save keys every Earth preset bakes (ARCHITECTURE.md, "Preset redirects"). tn_map and tn_geo
-- have no prototype: a preset world that lacks one fails loudly instead of drifting, and
-- control code reads them from the surface. tn_scale is read by every map's elevation entry, so it
-- also has a prototype-level fallback (the Map type route); tn_land_coarse is a preset key only.
local K_MAP = NOISE .. "map"
local K_SCALE = NOISE .. "scale"
local K_GEO = NOISE .. "geo"
local K_LAND_COARSE = NOISE .. "land_coarse"
-- spawn-cities: the keys the shared start mask v2 reads, which each Earth preset maps to its map's
-- spawn lake and starting-ore bias (preset keys only, like tn_land_coarse).
local K_SPAWN_LAKE = NOISE .. "spawn_lake"
local K_SPAWN_BIAS = NOISE .. "spawn_bias"
-- Koppen biomes (0.4.0): the toggle key a new world bakes (tn_koppen), orthogonal to elevation. The
-- class field and its four fitted fields are new bodies (climate.koppen.names); the centroid snap
-- that drives tiles is built on them (KOPPEN_CLASS2 and the snaps in CT).
local K_KOPPEN = NOISE .. "koppen"

-- Each map's geography. Every name a map's elevation entry reads is bound to that map: its coordinate
-- chain carries the map's radii and extent and reads the city offset through the map's own
-- map-qualified per-save names, so a Map type pick alone (which sets only elevation) still renders the
-- map, and no map-dependent value reaches the entry through tn_map or a shared key. Each map keeps one
-- geography version (issue #1; 0.3.0 dropped the versions before each map's newest).
-- The generated files (tools/build_geo.py): name-free data that a geography version's fit bodies
-- bind to its own chain, so a later version binds the same files instead of emitting new ones.
local EU_GEO_FILE = "prototypes/generated/geo_europe_v1.lua"
local EU_LAND_COARSE_FILE = "prototypes/generated/land_coarse_europe_v1.lua"
local AT_LAND_COARSE_FILE = "prototypes/generated/land_coarse_atlantic_v1.lua"
local OW_LAND_COARSE_FILE = "prototypes/generated/land_coarse_olde_world_v1.lua"

-- The spawn bodies (spawn.lua). The city number is a map-qualified per-save number that mirrors the
-- map's spawn-city setting (0 random, k the k-th city of the setting); the fold turns it, or the
-- folded hash of map_seed, into the resolved index control reads back at (0, 0) and the tile offset
-- of the city's pixel centre. The inland lakes read the version's chain, so each version that has
-- them takes its own; the other spawn bodies read no chain and serve every version that names them.
local EU_CITY = NOISE .. "city_europe"
local EU_CITY_INDEX = NOISE .. "city_index_europe_v1"
local EU_CITY_CX = NOISE .. "city_cx_europe_v1"
local EU_CITY_CY = NOISE .. "city_cy_europe_v1"
local START_LAND = NOISE .. "start_land_v1"
local DISTANCE = NOISE .. "distance_v1"
-- The spawn bearings per city and scale (tools/build_spawn.py): name-free data.
local EU_SPAWN_FILE = "prototypes/generated/spawn_europe_v1.lua"

local START_MASK2 = NOISE .. "start_mask_v2"

-- Waterways. Per map and scale, four generated sets (tools/build_waterways.py):
-- rivers, straits and turning basins (ww), canals, dams and fords, name-free data that waterways.lua
-- binds to the chain of the geography version that composes them. The hook gate tn_on, the ford key
-- tn_fords and the canals switch tn_canals are shared keys; tn_one and tn_zero are the switch's
-- neutral bodies.
local K_ON = NOISE .. "on"
local K_FORDS = NOISE .. "fords"
local K_CANALS = NOISE .. "canals"
local ONE = NOISE .. "one"
local ZERO = NOISE .. "zero"
local EU_WW_FILES = {"prototypes/generated/waterways_europe_s1_v1.lua",
                     "prototypes/generated/waterways_europe_s2_v1.lua",
                     "prototypes/generated/waterways_europe_s3_v1.lua",
                     "prototypes/generated/waterways_europe_s4_v1.lua",
                     "prototypes/generated/waterways_europe_s5_v1.lua",
                     "prototypes/generated/waterways_europe_s6_v1.lua"}

-- The region layer: every region body carries its version suffix. These are its
-- fixed names; a row's own names come from the row name stems below and the row's id.
local RG_V = "_v1"
local RG_DESTROYED_SD = NOISE .. "destroyed_sd" .. RG_V
local RG_DESTROYED_W = NOISE .. "destroyed_w" .. RG_V
local RG_DESTROYED_DEPTH = NOISE .. "destroyed_depth" .. RG_V
local RG_FOREST_W = NOISE .. "forest_w" .. RG_V
local RG_FOREST_SUM = NOISE .. "forest_sum" .. RG_V
local RG_TREE_MULT = NOISE .. "tree_mult" .. RG_V
local RG_MARSH_W = NOISE .. "marsh_w" .. RG_V
local RG_HOTSPOT_W = NOISE .. "hotspot_w" .. RG_V
local RG_ENEMY_MULT = NOISE .. "enemy_mult" .. RG_V
local RG_U = NOISE .. "region_u"
local RG_V_ = NOISE .. "region_v"
local RG_OX = NOISE .. "region_ox" .. RG_V
local RG_OY = NOISE .. "region_oy" .. RG_V
local RG_AX = NOISE .. "region_ax" .. RG_V
local RG_AY = NOISE .. "region_ay" .. RG_V
local RG_WK = NOISE .. "region_wk" .. RG_V
local RG_WX = NOISE .. "region_wx" .. RG_V
local RG_WY = NOISE .. "region_wy" .. RG_V
local RG_ROUGH = NOISE .. "region_rough" .. RG_V
local RG_MARSH_ROUGH = NOISE .. "region_marsh_rough" .. RG_V
-- 1.0.0: the river deltas (regions_v3): the marsh aggregate over three tables, the delta weight and the channel field
local RG_MARSH_W3 = NOISE .. "marsh_w_v3"
local RG_DELTA_W = NOISE .. "delta_w_v1"
local RG_DELTA_U = NOISE .. "delta_u_v1"
local RG_DELTA_V = NOISE .. "delta_v_v1"
local RG_DELTA_BANK = NOISE .. "delta_bank_v1"
local RG_DELTA_CH = NOISE .. "delta_channel_v1"
-- 0.3.0: the forest and marsh aggregates over both region tables (regions_v2)
local RG_FOREST_W2 = NOISE .. "forest_w_v2"
local RG_FOREST_SUM2 = NOISE .. "forest_sum_v2"
local RG_MARSH_W2 = NOISE .. "marsh_w_v2"

-- The Earth climate: latitude and longitude on the map's chain, the dry belts, the temperature core and
-- the Alien Biomes and fallback variants the presets redirect temperature, moisture and aux to.

-- The tile hooks: one key per restored vanilla land tile (prototype -inf), all pointed by the presets at
-- one shared bonus body; the Alien Biomes exclusion key (prototype 0) and its body; the marsh keys
-- (prototype -inf) and their bodies; the palm constant and the Earth copies of AB's palm autoplace.
-- climate-tiles' names (one table: Lua allows 200 locals in config.lua's main function)
local CT = {
  CL_LAT = NOISE .. "lat_v1",
  CL_LON = NOISE .. "lon_v1",
  CL_DRY = NOISE .. "dry_v1",
  CL_CORE = NOISE .. "t_core_v1",
  CL_MEANDER = NOISE .. "climate_meander_v1",
  CL_SHIFT = NOISE .. "climate_shift_v1",
  CL_T_AB = NOISE .. "temperature_ab_v1",
  CL_M_AB = NOISE .. "moisture_ab_v1",
  CL_A_AB = NOISE .. "aux_ab_v1",
  CL_GRAIN = NOISE .. "climate_grain_v1",
  CL_T_AB_G = NOISE .. "temperature_ab_v3",
  CL_M_AB_G = NOISE .. "moisture_ab_v2",
  CL_A_AB_G = NOISE .. "aux_ab_v2",
  CL_T_AB_GV = NOISE .. "temperature_veg_v1",
  CL_BELT_T = NOISE .. "tile_belt_t_v1",
  CL_BELT_TV = NOISE .. "tile_belt_tv_v1",
  CL_BELT_M = NOISE .. "tile_belt_m_v1",
  CL_BELT_A = NOISE .. "tile_belt_a_v1",
  CL_BELT_WILD = NOISE .. "tile_belt_wild_v1",
  CL_LIFT_M = NOISE .. "lift_m_v1",
  CL_LIFT_BARE = NOISE .. "lift_bare_v1",
  CL_LIFT_J = NOISE .. "lift_j_v1",
  CL_M_AB_L = NOISE .. "moisture_ab_v3",
  CL_M_AB_GL = NOISE .. "moisture_ab_v4",
  CL_N_D = NOISE .. "north_d_v1",
  CL_N_DROP = NOISE .. "north_drop_v1",
  CL_N_LEAD = NOISE .. "north_lead_v1",
  CL_N_BELT = NOISE .. "north_belt_v1",
  CL_T_AB_N = NOISE .. "temperature_ab_v4",
  CL_T_AB_G2 = NOISE .. "temperature_ab_v5",
  CL_T_AB_GV2 = NOISE .. "temperature_veg_v2",
  CL_GRAIN2 = NOISE .. "climate_grain_v2",
  CL_M_AB_G2 = NOISE .. "moisture_ab_v5",
  CL_M_AB_N = NOISE .. "moisture_ab_v6",
  CL_A_AB_G2 = NOISE .. "aux_ab_v3",
  CL_N_D2 = NOISE .. "north_d_v2",
  CL_N_DROP2 = NOISE .. "north_drop_v2",
  CL_N_LEAD2 = NOISE .. "north_lead_v2",
  CL_N_BELT2 = NOISE .. "north_belt_v2",
  CL_N_CLEAR = NOISE .. "north_clear_v1",
  CL_N_CLEAR_W = NOISE .. "north_clear_warp_v1",
  CL_T_AB_N2 = NOISE .. "temperature_ab_v6",
  CL_T_AB_G3 = NOISE .. "temperature_ab_v7",
  CL_T_AB_GV3 = NOISE .. "temperature_veg_v3",
  CL_GRAIN3 = NOISE .. "climate_grain_v3",
  CL_M_AB_G3 = NOISE .. "moisture_ab_v7",
  CL_M_AB_N2 = NOISE .. "moisture_ab_v8",
  CL_A_AB_G3 = NOISE .. "aux_ab_v4",
  K_NORTH_SNOW = NOISE .. "north_snow",
  CL_N_SNOW_W = NOISE .. "north_snow_w_v1",
  CL_N_RIM_KEEP = NOISE .. "north_rim_keep_v1",
  CL_N_D3 = NOISE .. "north_d_v3",
  CL_N_DROP3 = NOISE .. "north_drop_v3",
  CL_N_DROP4 = NOISE .. "north_drop_v4",
  CL_N_LEAD3 = NOISE .. "north_lead_v3",
  CL_N_BELT3 = NOISE .. "north_belt_v3",
  CL_T_AB_N3 = NOISE .. "temperature_ab_v8",
  CL_T_AB_G4 = NOISE .. "temperature_ab_v9",
  CL_T_AB_GV4 = NOISE .. "temperature_veg_v4",
  CL_GRAIN4 = NOISE .. "climate_grain_v4",
  CL_M_AB_G4 = NOISE .. "moisture_ab_v9",
  CL_M_AB_N3 = NOISE .. "moisture_ab_v10",
  CL_A_AB_G4 = NOISE .. "aux_ab_v5",
  CL_M_AB_V = NOISE .. "moisture_ab_v11",
  CL_A_AB_V = NOISE .. "aux_ab_v6",
  FROZEN_BODY3 = NOISE .. "frozen_ground_v3",
  CL_RAGGED = NOISE .. "band_ragged_v1",
  CL_BELT_M2 = NOISE .. "tile_belt_m_v2",
  CL_BELT_EDGE2 = NOISE .. "tile_belt_edge_v1",
  CL_LIFT_M2 = NOISE .. "lift_m_v2",
  -- 1.0.0: the Middle East's sand desert (climate.desert): the two warps, the depths in degrees of the plain rows,
  -- of the rows with patches of old ground and of the keep rows, the patches, the weight, the sand weight, the two
  -- bodies a new world's preset names over the tile temperature and tile aux keys, the name each of those reads what
  -- it wraps through, and the band tests' five bodies with the sand weight
  DS_WARP_A = NOISE .. "desert_warp_a_v1",
  DS_WARP_B = NOISE .. "desert_warp_b_v1",
  DS_DEPTH = NOISE .. "desert_depth_v1",
  DS_DEPTH_FLATS = NOISE .. "desert_depth_flats_v1",
  DS_KEEP = NOISE .. "desert_keep_v1",
  DS_FLATS = NOISE .. "desert_flats_v1",
  DS_W = NOISE .. "desert_w_v1",
  DS_TILE_T = NOISE .. "desert_tile_t_v1",
  DS_TILE_T_UNDER = NOISE .. "desert_tile_t_under",
  DS_TILE_A = NOISE .. "desert_tile_a_v1",
  DS_TILE_A_UNDER = NOISE .. "desert_tile_a_under",
  DS_SAND = NOISE .. "desert_sand_v1",
  DS_COAST = NOISE .. "desert_coast_v1",
  DS_VANILLA = NOISE .. "desert_vtile_bonus_v1",
  DS_VANILLA_HIGH = NOISE .. "desert_vtile_bonus_high_v1",
  DS_VANILLA_NEXT = NOISE .. "desert_vtile_bonus_fray_v1",
  DS_VANILLA_NEXT_HIGH = NOISE .. "desert_vtile_bonus_fray_high_v1",
  DS_EXCLUDE = NOISE .. "desert_ab_exclude_v1",
  -- 1.0.0: Patagonia and the Monte as dry steppe (climate.steppe): the depth in degrees of the rows, the weight, the
  -- patches, the three bodies a new Atlantic world's preset names over the tile moisture, tile aux and grass
  -- temperature keys, the reach and the body it names over the living trees' multiplier, and the name each of
  -- those reads what it wraps through
  SP_DEPTH = NOISE .. "steppe_depth_v1",
  SP_W = NOISE .. "steppe_w_v1",
  SP_PATCH = NOISE .. "steppe_patch_v1",
  SP_TILE_M = NOISE .. "steppe_tile_m_v1",
  SP_TILE_M_UNDER = NOISE .. "steppe_tile_m_under",
  SP_TILE_A = NOISE .. "steppe_tile_a_v1",
  SP_TILE_A_UNDER = NOISE .. "steppe_tile_a_under",
  SP_TILE_TV = NOISE .. "steppe_tile_tv_v1",
  SP_TILE_TV_UNDER = NOISE .. "steppe_tile_tv_under",
  SP_REACH = NOISE .. "steppe_reach_v1",
  SP_TREES = NOISE .. "steppe_tree_mult_v1",
  SP_TREES_UNDER = NOISE .. "steppe_tree_mult_under",
  TM_1 = NOISE .. "tile_mix_1_v1",
  TM_2 = NOISE .. "tile_mix_2_v1",
  TM_3 = NOISE .. "tile_mix_3_v1",
  TM_4 = NOISE .. "tile_mix_4_v1",
  TM_5 = NOISE .. "tile_mix_5_v1",
  TM_6 = NOISE .. "tile_mix_6_v1",
  TM_7 = NOISE .. "tile_mix_7_v1",
  TM_8 = NOISE .. "tile_mix_8_v1",
  TM_9 = NOISE .. "tile_mix_9_v1",
  TM_10 = NOISE .. "tile_mix_10_v1",
  TM_11 = NOISE .. "tile_mix_11_v1",
  TM_12 = NOISE .. "tile_mix_12_v1",
  TM2_1 = NOISE .. "tile_mix_1_v2",
  TM2_2 = NOISE .. "tile_mix_2_v2",
  TM2_3 = NOISE .. "tile_mix_3_v2",
  TM2_4 = NOISE .. "tile_mix_4_v2",
  TM2_5 = NOISE .. "tile_mix_5_v2",
  TM2_6 = NOISE .. "tile_mix_6_v2",
  TM2_7 = NOISE .. "tile_mix_7_v2",
  TM2_8 = NOISE .. "tile_mix_8_v2",
  TM2_9 = NOISE .. "tile_mix_9_v2",
  TM2_10 = NOISE .. "tile_mix_10_v2",
  TM2_11 = NOISE .. "tile_mix_11_v2",
  TM2_12 = NOISE .. "tile_mix_12_v2",
  TM_FRAY = NOISE .. "tile_mix_fray_v1",
  TM3_1 = NOISE .. "tile_mix_1_v3",
  TM3_2 = NOISE .. "tile_mix_2_v3",
  TM3_3 = NOISE .. "tile_mix_3_v3",
  TM3_4 = NOISE .. "tile_mix_4_v3",
  TM3_5 = NOISE .. "tile_mix_5_v3",
  TM3_6 = NOISE .. "tile_mix_6_v3",
  TM3_7 = NOISE .. "tile_mix_7_v3",
  TM3_8 = NOISE .. "tile_mix_8_v3",
  TM3_9 = NOISE .. "tile_mix_9_v3",
  TM3_10 = NOISE .. "tile_mix_10_v3",
  TM3_11 = NOISE .. "tile_mix_11_v3",
  TM3_12 = NOISE .. "tile_mix_12_v3",
  TM_FRAY2 = NOISE .. "tile_mix_fray_v2",
  K_TILE_T = NOISE .. "tile_temperature",
  K_TILE_TV = NOISE .. "tile_temperature_veg",
  K_TILE_M = NOISE .. "tile_moisture",
  K_TILE_A = NOISE .. "tile_aux",
  VT_BONUS_G = NOISE .. "vtile_bonus_v2",
  VT_MIX = NOISE .. "vtile_mix",
  VT_BONUS_H = NOISE .. "vtile_bonus_v3",
  VT_BONUS_F = NOISE .. "vtile_bonus_v4",
  VT_BONUS_FH = NOISE .. "vtile_bonus_v5",
  AB_EXCLUDE_BODY_G = NOISE .. "ab_exclude_v2",
  CL_T_FB = NOISE .. "temperature_fb_v1",
  CL_M_FB = NOISE .. "moisture_fb_v1",
  CL_A_FB = NOISE .. "aux_fb_v1",
  VT_GRASS_1 = NOISE .. "vtile_grass_1",
  VT_GRASS_2 = NOISE .. "vtile_grass_2",
  VT_GRASS_3 = NOISE .. "vtile_grass_3",
  VT_GRASS_4 = NOISE .. "vtile_grass_4",
  VT_DRY_DIRT = NOISE .. "vtile_dry_dirt",
  VT_DIRT_1 = NOISE .. "vtile_dirt_1",
  VT_DIRT_2 = NOISE .. "vtile_dirt_2",
  VT_DIRT_3 = NOISE .. "vtile_dirt_3",
  VT_DIRT_4 = NOISE .. "vtile_dirt_4",
  VT_DIRT_5 = NOISE .. "vtile_dirt_5",
  VT_DIRT_6 = NOISE .. "vtile_dirt_6",
  VT_DIRT_7 = NOISE .. "vtile_dirt_7",
  VT_SAND_1 = NOISE .. "vtile_sand_1",
  VT_SAND_2 = NOISE .. "vtile_sand_2",
  VT_SAND_3 = NOISE .. "vtile_sand_3",
  VT_RED_0 = NOISE .. "vtile_red_desert_0",
  VT_RED_1 = NOISE .. "vtile_red_desert_1",
  VT_RED_2 = NOISE .. "vtile_red_desert_2",
  VT_RED_3 = NOISE .. "vtile_red_desert_3",
  VT_BONUS = NOISE .. "vtile_bonus_v1",
  AB_EXCLUDE = NOISE .. "ab_exclude",
  AB_EXCLUDE_BODY = NOISE .. "ab_exclude_v1",
  AB_KEEP_BODY = NOISE .. "ab_keep_v1",
  MARSH_MUD = NOISE .. "marsh_water_mud",
  MARSH_POOL = NOISE .. "marsh_pool_v1",
  MARSH_MUD_BODY = NOISE .. "marsh_water_mud_v1",
  MARSH_MUD_BODY2 = NOISE .. "marsh_water_mud_v2",
  MARSH_FRAY = NOISE .. "marsh_pool_fray_v1",
  MARSH_SHALLOW = NOISE .. "marsh_water_shallow",
  MARSH_SHALLOW_BODY = NOISE .. "marsh_water_shallow_v1",
  MARSH_MUD_BODY3 = NOISE .. "marsh_water_mud_v3",
  MARSH_SHALLOW_BODY2 = NOISE .. "marsh_water_shallow_v2",
  MARSH_GRASS = NOISE .. "marsh_grass",
  MARSH_GRASS_BODY = NOISE .. "marsh_grass_v1",
  FROZEN_KEY = NOISE .. "frozen_ground",
  FROZEN_BODY = NOISE .. "frozen_ground_v1",
  FROZEN_BODY2 = NOISE .. "frozen_ground_v2",
  PALM_CONST = NOISE .. "palm_const_v1",
  PALM_A_P = NOISE .. "palm_a_p_v1",
  PALM_A_R = NOISE .. "palm_a_r_v1",
  PALM_B_P = NOISE .. "palm_b_p_v1",
  PALM_B_R = NOISE .. "palm_b_r_v1",
  PALM_A_P_KEY = "entity:tree-palm-a:probability",
  PALM_A_R_KEY = "entity:tree-palm-a:richness",
  PALM_B_P_KEY = "entity:tree-palm-b:probability",
  PALM_B_R_KEY = "entity:tree-palm-b:richness",
  -- Koppen biomes (0.4.0): the four smooth fitted fields and
  -- the A/B/C/D/E classifier, new released bodies no older save names (new names only).
  KOPPEN_TANN = NOISE .. "koppen_tann_v1",
  KOPPEN_SEASON = NOISE .. "koppen_season_v1",
  KOPPEN_TCOLD = NOISE .. "koppen_tcold_v1",
  KOPPEN_TWARM = NOISE .. "koppen_twarm_v1",
  KOPPEN_PANN = NOISE .. "koppen_pann_v1",
  KOPPEN_SW = NOISE .. "koppen_sw_v1",
  KOPPEN_CLASS = NOISE .. "koppen_class_v1",
  -- Koppen biomes (0.4.0): the warped classifier the snap reads and the three axis-snap
  -- bodies (plus the vegetation-temperature snap) the preset points the climate axes at when Koppen
  -- is on (prototypes/expressions/climate_koppen.lua). New
  -- released bodies no older save names.
  KOPPEN_CLASS2 = NOISE .. "koppen_class_v2",
  KOPPEN_T_SNAP = NOISE .. "koppen_t_snap_v1",
  KOPPEN_M_SNAP = NOISE .. "koppen_m_snap_v1",
  KOPPEN_A_SNAP = NOISE .. "koppen_a_snap_v1",
  KOPPEN_TV_SNAP = NOISE .. "koppen_tv_snap_v1",
  -- Koppen biomes (0.4.0; climate.koppen.compose): the composition bodies the preset points the
  -- climate axes at when Koppen is on - the cold-north/spawn-aware temperature and its vegetation cap on the
  -- Koppen snap, and the green-lifted moisture snap for the oceanic belt. New bodies, no older save names.
  KOPPEN_COOL_T = NOISE .. "koppen_cool_t_v1",
  KOPPEN_CN_T = NOISE .. "koppen_cn_t_v1",
  KOPPEN_CN_TV = NOISE .. "koppen_cn_tv_v1",
  KOPPEN_M_SNAP2 = NOISE .. "koppen_m_snap_v2",
}

-- Trees and great forests. The great-forests gate (prototype 0; Earth presets 1 or
-- 0 by the setting) and the multiplier key (prototype 1; Earth presets name the region layer's
-- multiplier) of the boost hook on every living tree; the vanilla-scale temperature the restored vanilla
-- trees read; per restored vanilla tree a probability and a richness key (prototype 0) and its Earth
-- body, every richness key naming one shared body; per rebuilt vanilla rock or decal a key (prototype 0)
-- and its body; per re-listed vanilla decorative a key (prototype -inf), all naming one shared body; and
-- the palms' second probability versions, which take the boost around climate-tiles' registered copies.
-- trees-forests' single names (one table: the 200-local limit)
local TFN = {
  K_FORESTS_ON = NOISE .. "forests_on",
  K_TREE_MULT = NOISE .. "tree_mult",
  K_TREE_LIFT = NOISE .. "tree_lift",
  TF_LIFT = NOISE .. "tree_lift_v1",
  TF_VTEMP = NOISE .. "temperature_vanilla_v1",
  TF_VTREE_R = NOISE .. "vtree_r_v1",
  TF_VDECO = NOISE .. "vdeco_v1",
  PALM_A_P2 = NOISE .. "palm_a_p_v2",
  PALM_B_P2 = NOISE .. "palm_b_p_v2",
  PALM_A_P3 = NOISE .. "palm_a_p_v3",
  PALM_B_P3 = NOISE .. "palm_b_p_v3",
  PALM_ALLOW = NOISE .. "palm_allow_v1",
  PALM_A_P4 = NOISE .. "palm_a_p_v4",
  PALM_B_P4 = NOISE .. "palm_b_p_v4",
  PALM_ALLOW2 = NOISE .. "palm_allow_v2",
  PALM_MED = NOISE .. "palm_med_v1",
  PALM_SHORE = NOISE .. "palm_shore_v1",
  PALM_B_P5 = NOISE .. "palm_b_p_v5",
  NB_KEY = NOISE .. "no_blue",
  NB_OPEN = NOISE .. "no_blue_open_v1",
  NB_TILE = NOISE .. "no_blue_tile_v1",
  NB_OUT = NOISE .. "no_blue_out_v1",
  ZP_KEY = NOISE .. "zone_plants",
  -- 1.0.0: the great forests' ground (trees.ground): the weight key (prototype 0) and its two bodies, the moisture
  -- trees and decoratives read and the tile moisture inside an outline, the tree lift's second version, the weight
  -- trees take and the multiplier on the ground weight with its zone body
  K_FOREST_GROUND = NOISE .. "forest_ground",
  FG_W = NOISE .. "forest_ground_v1",
  FG_W_ZONE = NOISE .. "forest_ground_zone_v1",
  FG_M = NOISE .. "forest_moisture_v1",
  FG_TM = NOISE .. "forest_tile_moisture_v1",
  TF_LIFT2 = NOISE .. "tree_lift_v2",
  FG_TREES = NOISE .. "forest_trees_v1",
  FG_MULT = NOISE .. "forest_tree_mult_v1",
  FG_MULT_ZONE = NOISE .. "forest_tree_mult_zone_v1",
}
local VT = NOISE .. "vtree_"
local TF_TREES = {
  ["tree-01"] = {p = VT .. "tree_01_p", r = VT .. "tree_01_r", body = VT .. "tree_01_p_v1"},
  ["tree-02"] = {p = VT .. "tree_02_p", r = VT .. "tree_02_r", body = VT .. "tree_02_p_v1"},
  ["tree-02-red"] = {p = VT .. "tree_02_red_p", r = VT .. "tree_02_red_r", body = VT .. "tree_02_red_p_v1"},
  ["tree-03"] = {p = VT .. "tree_03_p", r = VT .. "tree_03_r", body = VT .. "tree_03_p_v1"},
  ["tree-04"] = {p = VT .. "tree_04_p", r = VT .. "tree_04_r", body = VT .. "tree_04_p_v1"},
  ["tree-05"] = {p = VT .. "tree_05_p", r = VT .. "tree_05_r", body = VT .. "tree_05_p_v1"},
  ["tree-06"] = {p = VT .. "tree_06_p", r = VT .. "tree_06_r", body = VT .. "tree_06_p_v1"},
  ["tree-06-brown"] = {p = VT .. "tree_06_brown_p", r = VT .. "tree_06_brown_r", body = VT .. "tree_06_brown_p_v1"},
  ["tree-07"] = {p = VT .. "tree_07_p", r = VT .. "tree_07_r", body = VT .. "tree_07_p_v1"},
  ["tree-08"] = {p = VT .. "tree_08_p", r = VT .. "tree_08_r", body = VT .. "tree_08_p_v1"},
  ["tree-08-brown"] = {p = VT .. "tree_08_brown_p", r = VT .. "tree_08_brown_r", body = VT .. "tree_08_brown_p_v1"},
  ["tree-08-red"] = {p = VT .. "tree_08_red_p", r = VT .. "tree_08_red_r", body = VT .. "tree_08_red_p_v1"},
  ["tree-09"] = {p = VT .. "tree_09_p", r = VT .. "tree_09_r", body = VT .. "tree_09_p_v1"},
  ["tree-09-brown"] = {p = VT .. "tree_09_brown_p", r = VT .. "tree_09_brown_r", body = VT .. "tree_09_brown_p_v1"},
  ["tree-09-red"] = {p = VT .. "tree_09_red_p", r = VT .. "tree_09_red_r", body = VT .. "tree_09_red_p_v1"},
}
local VR = NOISE .. "vrock_"
local TF_ROCKS = {
  ["huge-rock"] = {key = VR .. "huge_rock", body = VR .. "huge_rock_v1", high = VR .. "huge_rock_v2"},
  ["big-rock"] = {key = VR .. "big_rock", body = VR .. "big_rock_v1", high = VR .. "big_rock_v2"},
  ["big-sand-rock"] = {key = VR .. "big_sand_rock", body = VR .. "big_sand_rock_v1", high = VR .. "big_sand_rock_v2",
                       cold = VR .. "big_sand_rock_v3", cold_high = VR .. "big_sand_rock_v4"},
  ["medium-rock"] = {key = VR .. "medium_rock", body = VR .. "medium_rock_v1"},
  ["small-rock"] = {key = VR .. "small_rock", body = VR .. "small_rock_v1"},
  ["tiny-rock"] = {key = VR .. "tiny_rock", body = VR .. "tiny_rock_v1"},
  ["medium-sand-rock"] = {key = VR .. "medium_sand_rock", body = VR .. "medium_sand_rock_v1",
                          cold = VR .. "medium_sand_rock_v2"},
  ["small-sand-rock"] = {key = VR .. "small_sand_rock", body = VR .. "small_sand_rock_v1",
                         cold = VR .. "small_sand_rock_v2"},
  ["red-desert-decal"] = {key = VR .. "red_desert_decal", body = VR .. "red_desert_decal_v1",
                          cold = VR .. "red_desert_decal_v2"},
  ["sand-decal"] = {key = VR .. "sand_decal", body = VR .. "sand_decal_v1", cold = VR .. "sand_decal_v2"},
  ["sand-dune-decal"] = {key = VR .. "sand_dune_decal", body = VR .. "sand_dune_decal_v1",
                         cold = VR .. "sand_dune_decal_v2"},
}
local VD = NOISE .. "vdeco_"
local TF_DECO = {
  ["light-mud-decal"] = VD .. "light_mud_decal", ["green-asterisk"] = VD .. "green_asterisk",
  ["green-asterisk-mini"] = VD .. "green_asterisk_mini", ["green-bush-mini"] = VD .. "green_bush_mini",
  ["green-carpet-grass"] = VD .. "green_carpet_grass", ["green-croton"] = VD .. "green_croton",
  ["green-desert-bush"] = VD .. "green_desert_bush", ["green-hairy-grass"] = VD .. "green_hairy_grass",
  ["green-pita"] = VD .. "green_pita", ["green-pita-mini"] = VD .. "green_pita_mini",
  ["green-small-grass"] = VD .. "green_small_grass",
}

-- Ridges (ARCHITECTURE.md, "Expression inventory"). The toggle key tn_ridges is a name
-- switch to waterways' neutral bodies tn_one and tn_zero (the canals switch reads the same pair); the
-- per-map keys tn_crest and tn_openings name the map's crest distance and openings bodies, so the
-- cliff properties, the effective crest distance, the ridge-free start disc, the ore clearance and
-- the ore wrappers are one body each on every map.
local RD_V = "_v1"
local ORE = NOISE .. "ore_"
-- ridges' names (one table: the 200-local limit)
local RDN = {
  K_RIDGES = NOISE .. "ridges",
  K_CREST = NOISE .. "crest",
  K_OPENINGS = NOISE .. "openings",
  K_BAND = NOISE .. "band",
  K_HIGH = NOISE .. "high",
  K_PASSES = NOISE .. "passes",
  K_ROCK_LIFT = NOISE .. "rock_lift",
  K_GROUND = NOISE .. "ground_lean",
  K_HIGH_TILE = NOISE .. "high_tile",
  RD_RISE = NOISE .. "highland_rise" .. RD_V,
  RD_RISE_TILE = NOISE .. "highland_rise_tile" .. RD_V,
  RD_FRAY = NOISE .. "highland_fray" .. RD_V,
  RD_FRAY_TILE = NOISE .. "highland_fray_tile" .. RD_V,
  RD_MASSIF = NOISE .. "highland_massif" .. RD_V,
  RD_HIGH_TILE = NOISE .. "highland_tile" .. RD_V,
  RD_GATE = NOISE .. "highland_gate" .. RD_V,
  RD_LAPSE = NOISE .. "highland_lapse" .. RD_V,
  RD_GROUND = NOISE .. "highland_ground" .. RD_V,
  RD_HIGH = NOISE .. "highland" .. RD_V,
  RD_ROCK_LIFT = NOISE .. "highland_rocks" .. RD_V,
  RD_ROCK_LIFT_AB = NOISE .. "highland_rocks_ab" .. RD_V,
  RD_ROCK_DENSITY = NOISE .. "rock_density" .. RD_V,
  RD_HEIGHT = NOISE .. "ridge_height" .. RD_V,
  RD_FREE = NOISE .. "ridge_free" .. RD_V,
  RD_CLIFFINESS = NOISE .. "cliffiness" .. RD_V,
  RD_CLEAR = NOISE .. "ridge_clear" .. RD_V,
  RD_COLD_F = NOISE .. "highland_cold_v1",
  RD_COLD_FRAY = NOISE .. "highland_cold_fray_v1",
  RD_COLD_GATED = NOISE .. "highland_cold_gated_v1",
  RD_COLD_REACH = NOISE .. "highland_cold_reach_v1",
  RD_COLD_HIGH = NOISE .. "highland_cold_high_v1",
  RD_COLD_CAP = NOISE .. "highland_cold_cap_v1",
  EU_COLD = NOISE .. "highland_cold_europe_v1",
  AT_COLD = NOISE .. "highland_cold_atlantic_v1",
  OW_COLD = NOISE .. "highland_cold_olde_world_v1",
  -- 0.3.0: the cold field's next versions (the desert snow line) and the rim's cap (ridges.cold)
  RD_COLD_F2 = NOISE .. "highland_cold_v2",
  RD_COLD_GATED2 = NOISE .. "highland_cold_gated_v2",
  RD_COLD_HIGH2 = NOISE .. "highland_cold_high_v2",
  RD_COLD_CAP2 = NOISE .. "highland_cold_cap_v2",
  EU_COLD2 = NOISE .. "highland_cold_europe_v2",
  AT_COLD2 = NOISE .. "highland_cold_atlantic_v2",
  OW_COLD2 = NOISE .. "highland_cold_olde_world_v2",
  EU_BAND = NOISE .. "band_europe" .. RD_V,
  AT_BAND = NOISE .. "band_atlantic" .. RD_V,
  OW_BAND = NOISE .. "band_olde_world" .. RD_V,
  EU_WANDER_U = NOISE .. "ridge_u_europe" .. RD_V,
  AT_WANDER_U = NOISE .. "ridge_u_atlantic" .. RD_V,
  OW_WANDER_U = NOISE .. "ridge_u_olde_world" .. RD_V,
  EU_WANDER_V = NOISE .. "ridge_v_europe" .. RD_V,
  AT_WANDER_V = NOISE .. "ridge_v_atlantic" .. RD_V,
  OW_WANDER_V = NOISE .. "ridge_v_olde_world" .. RD_V,
  EU_RUN = NOISE .. "ridge_run_europe" .. RD_V,
  AT_RUN = NOISE .. "ridge_run_atlantic" .. RD_V,
  OW_RUN = NOISE .. "ridge_run_olde_world" .. RD_V,
  EU_KEEP = NOISE .. "ridge_keep_europe" .. RD_V,
  AT_KEEP = NOISE .. "ridge_keep_atlantic" .. RD_V,
  OW_KEEP = NOISE .. "ridge_keep_olde_world" .. RD_V,
  ORE_IRON = ORE .. "iron_ore_p" .. RD_V,
  ORE_COPPER = ORE .. "copper_ore_p" .. RD_V,
  ORE_COAL = ORE .. "coal_p" .. RD_V,
  ORE_STONE = ORE .. "stone_p" .. RD_V,
  ORE_URANIUM = ORE .. "uranium_ore_p" .. RD_V,
  ORE_OIL = ORE .. "crude_oil_p" .. RD_V,
  -- The line field, the bodies new worlds point at (ridges.preset): the old names above stay defined for every
  -- save that names them.
  RD_CLIFF_ELEVATION2 = NOISE .. "cliff_elevation_v2",
  EU_CREST2 = NOISE .. "crest_europe_v2",
  AT_CREST2 = NOISE .. "crest_atlantic_v2",
  OW_CREST2 = NOISE .. "crest_olde_world_v2",
  EU_OPENINGS2 = NOISE .. "openings_europe_v2",
  AT_OPENINGS2 = NOISE .. "openings_atlantic_v2",
  OW_OPENINGS2 = NOISE .. "openings_olde_world_v2",
  EU_LINE_DEPTH = NOISE .. "line_depth_europe" .. RD_V,
  AT_LINE_DEPTH = NOISE .. "line_depth_atlantic" .. RD_V,
  OW_LINE_DEPTH = NOISE .. "line_depth_olde_world" .. RD_V,
  EU_LINE_SIDE = NOISE .. "line_side_europe" .. RD_V,
  AT_LINE_SIDE = NOISE .. "line_side_atlantic" .. RD_V,
  OW_LINE_SIDE = NOISE .. "line_side_olde_world" .. RD_V,
  EU_LINE_NEAR = NOISE .. "line_near_europe" .. RD_V,
  AT_LINE_NEAR = NOISE .. "line_near_atlantic" .. RD_V,
  OW_LINE_NEAR = NOISE .. "line_near_olde_world" .. RD_V,
  EU_LINE_REACH = NOISE .. "line_reach_europe" .. RD_V,
  AT_LINE_REACH = NOISE .. "line_reach_atlantic" .. RD_V,
  OW_LINE_REACH = NOISE .. "line_reach_olde_world" .. RD_V,
  EU_LINE_ALONG = NOISE .. "line_along_europe" .. RD_V,
  AT_LINE_ALONG = NOISE .. "line_along_atlantic" .. RD_V,
  OW_LINE_ALONG = NOISE .. "line_along_olde_world" .. RD_V,
  -- 0.3.0: the union of both range tables (ranges.lua and ranges_v2.lua), the bodies
  -- new worlds point at (ridges.preset): the highland, tile reach and passes over both tables. The bodies above read
  -- the first table alone and stay as they are.
  EU_HIGH2 = NOISE .. "highland_europe_v2",
  AT_HIGH2 = NOISE .. "highland_atlantic_v2",
  OW_HIGH2 = NOISE .. "highland_olde_world_v2",
  EU_HIGH_TILE2 = NOISE .. "highland_tile_europe_v2",
  AT_HIGH_TILE2 = NOISE .. "highland_tile_atlantic_v2",
  OW_HIGH_TILE2 = NOISE .. "highland_tile_olde_world_v2",
  EU_PASSES2 = NOISE .. "passes_europe_v2",
  AT_PASSES2 = NOISE .. "passes_atlantic_v2",
  OW_PASSES2 = NOISE .. "passes_olde_world_v2",
  -- 0.3.0, second round: the union's line field, keep, run and crest band (both tables take cliffs)
  EU_CREST3 = NOISE .. "crest_europe_v3",
  AT_CREST3 = NOISE .. "crest_atlantic_v3",
  OW_CREST3 = NOISE .. "crest_olde_world_v3",
  EU_OPENINGS3 = NOISE .. "openings_europe_v3",
  AT_OPENINGS3 = NOISE .. "openings_atlantic_v3",
  OW_OPENINGS3 = NOISE .. "openings_olde_world_v3",
  EU_LINE_DEPTH2 = NOISE .. "line_depth_europe_v2",
  AT_LINE_DEPTH2 = NOISE .. "line_depth_atlantic_v2",
  OW_LINE_DEPTH2 = NOISE .. "line_depth_olde_world_v2",
  EU_LINE_SIDE2 = NOISE .. "line_side_europe_v2",
  AT_LINE_SIDE2 = NOISE .. "line_side_atlantic_v2",
  OW_LINE_SIDE2 = NOISE .. "line_side_olde_world_v2",
  EU_LINE_NEAR2 = NOISE .. "line_near_europe_v2",
  AT_LINE_NEAR2 = NOISE .. "line_near_atlantic_v2",
  OW_LINE_NEAR2 = NOISE .. "line_near_olde_world_v2",
  EU_LINE_REACH2 = NOISE .. "line_reach_europe_v2",
  AT_LINE_REACH2 = NOISE .. "line_reach_atlantic_v2",
  OW_LINE_REACH2 = NOISE .. "line_reach_olde_world_v2",
  EU_LINE_ALONG2 = NOISE .. "line_along_europe_v2",
  AT_LINE_ALONG2 = NOISE .. "line_along_atlantic_v2",
  OW_LINE_ALONG2 = NOISE .. "line_along_olde_world_v2",
  EU_KEEP2 = NOISE .. "ridge_keep_europe_v2",
  AT_KEEP2 = NOISE .. "ridge_keep_atlantic_v2",
  OW_KEEP2 = NOISE .. "ridge_keep_olde_world_v2",
  EU_RUN2 = NOISE .. "ridge_run_europe_v2",
  AT_RUN2 = NOISE .. "ridge_run_atlantic_v2",
  OW_RUN2 = NOISE .. "ridge_run_olde_world_v2",
  EU_BAND2 = NOISE .. "band_europe_v2",
  AT_BAND2 = NOISE .. "band_atlantic_v2",
  OW_BAND2 = NOISE .. "band_olde_world_v2",
}

-- Resources and enemies (ARCHITECTURE.md, "Expression inventory").
-- The hotspots toggle tn_hotspots is a name switch to tn_one and tn_zero, read by the Entity bodies
-- through a folded `if`; each map's elevation entry reads its offshore stamp through the map-qualified
-- key tn_fields_<map>, a Map type fallback, so the entry stays a Map type entry (ARCHITECTURE.md,
-- "Map type entries"). Every hotspot body reads the region layer's rows and tn_land_coarse only.
local RE_V = "_v1"
local HS = NOISE .. "hs_"
-- The wrappers of the pack's live autoplace, built in data-final-fixes.lua: the ore probability
-- wrappers' next version (ridges' _v1 stay defined), the richness wrappers, the enemy wrapper and,
-- with the Oil Rig loaded, its offshore-oil wrappers.
-- Each map's offshore field stamp (Tile only, a firewall body) and the map-qualified key its
-- elevation entry reads it through; the entry's next version wraps the previous one in the stamp.

-- resources-enemies' names (one table: the 200-local limit)
local REN = {
  K_HOTSPOTS = NOISE .. "hotspots",
  HS_BLOB = HS .. "blob" .. RE_V,
  HS_IRON = HS .. "iron_ore" .. RE_V,
  HS_IRON_P = HS .. "iron_ore_p" .. RE_V,
  HS_IRON_R = HS .. "iron_ore_r" .. RE_V,
  HS_COPPER = HS .. "copper_ore" .. RE_V,
  HS_COPPER_P = HS .. "copper_ore_p" .. RE_V,
  HS_COPPER_R = HS .. "copper_ore_r" .. RE_V,
  HS_COAL = HS .. "coal" .. RE_V,
  HS_COAL_P = HS .. "coal_p" .. RE_V,
  HS_COAL_R = HS .. "coal_r" .. RE_V,
  HS_STONE = HS .. "stone" .. RE_V,
  HS_STONE_P = HS .. "stone_p" .. RE_V,
  HS_STONE_R = HS .. "stone_r" .. RE_V,
  HS_URANIUM = HS .. "uranium_ore" .. RE_V,
  HS_URANIUM_P = HS .. "uranium_ore_p" .. RE_V,
  HS_URANIUM_R = HS .. "uranium_ore_r" .. RE_V,
  HS_OIL = HS .. "crude_oil" .. RE_V,
  HS_OIL_P = HS .. "crude_oil_p" .. RE_V,
  HS_OIL_R = HS .. "crude_oil_r" .. RE_V,
  HS_OFFSHORE = HS .. "offshore_oil" .. RE_V,
  HS_OFFSHORE_P = HS .. "offshore_oil_p" .. RE_V,
  HS_OFFSHORE_R = HS .. "offshore_oil_r" .. RE_V,
  RAMP = NOISE .. "ore_ramp" .. RE_V,
  SEA = NOISE .. "sea" .. RE_V,
  ENEMY_LAYER = NOISE .. "enemy_layer" .. RE_V,
  ENEMY = NOISE .. "enemy" .. RE_V,
  ORE_IRON_P2 = ORE .. "iron_ore_p_v2",
  ORE_IRON_R = ORE .. "iron_ore_r" .. RE_V,
  ORE_COPPER_P2 = ORE .. "copper_ore_p_v2",
  ORE_COPPER_R = ORE .. "copper_ore_r" .. RE_V,
  ORE_COAL_P2 = ORE .. "coal_p_v2",
  ORE_COAL_R = ORE .. "coal_r" .. RE_V,
  ORE_STONE_P2 = ORE .. "stone_p_v2",
  ORE_STONE_R = ORE .. "stone_r" .. RE_V,
  ORE_URANIUM_P2 = ORE .. "uranium_ore_p_v2",
  ORE_URANIUM_R = ORE .. "uranium_ore_r" .. RE_V,
  ORE_OIL_P2 = ORE .. "crude_oil_p_v2",
  ORE_OIL_R = ORE .. "crude_oil_r" .. RE_V,
  OFFSHORE_P = NOISE .. "offshore_p" .. RE_V,
  OFFSHORE_R = NOISE .. "offshore_r" .. RE_V,
  K_HS_AMOUNT = NOISE .. "hotspot_amount",
  K_SCARCITY = NOISE .. "scarcity",
  ORE_FN = ORE .. "all_patches" .. RE_V,
  ORE_GAP = ORE .. "gap" .. RE_V,
  ORE_PATCH_IRON = ORE .. "iron_ore_patches" .. RE_V,
  ORE_PATCH_COPPER = ORE .. "copper_ore_patches" .. RE_V,
  ORE_PATCH_COAL = ORE .. "coal_patches" .. RE_V,
  ORE_PATCH_STONE = ORE .. "stone_patches" .. RE_V,
  ORE_PATCH_URANIUM = ORE .. "uranium_ore_patches" .. RE_V,
  ORE_PATCH_OIL = ORE .. "crude_oil_patches" .. RE_V,
  ORE_PATCH_OFFSHORE = ORE .. "offshore_oil_patches" .. RE_V,
  EU_FIELDS_KEY = NOISE .. "fields_europe",
  EU_FIELDS = NOISE .. "fields_europe" .. RE_V,
  AT_FIELDS_KEY = NOISE .. "fields_atlantic",
  AT_FIELDS = NOISE .. "fields_atlantic" .. RE_V,
  OW_FIELDS_KEY = NOISE .. "fields_olde_world",
  OW_FIELDS = NOISE .. "fields_olde_world" .. RE_V,
}

-- The soft map edge and the inland lakes switch (both from playtesting): the far-field box sinks land
-- into deep water across a noise-warped band just inside the extent (coast.edge_band), so a coast the
-- box cuts reads as a wavy coastline, and a
-- map's inland lakes compose only when the per-save switch tn_inland_lakes names tn_one. Europe's
-- version 6 carried these names; its frame (config.lua frames) keeps the chain names.
-- edge-and-lakes' names (one table: the 200-local limit)
local ELN = {
  K_INLAND_LAKES = NOISE .. "inland_lakes",
  EU6_GX = NOISE .. "gx_europe_v6",
  EU6_GY = NOISE .. "gy_europe_v6",
  EU6_U = NOISE .. "u_europe_v6",
  EU6_V = NOISE .. "v_europe_v6",
  EU6_CX = NOISE .. "cx_europe_v6",
  EU6_CY = NOISE .. "cy_europe_v6",
  -- Europe's scale 12 and 24 waterway files, which version 7 binds with the scale 1 to 6 files.
  EUX_WW_FILES = {"prototypes/generated/waterways_europe_s12_v1.lua",
                  "prototypes/generated/waterways_europe_s24_v1.lua"},
  -- 0.3.0: Europe's version 7, the composition of version 6 and its scale extension under names of its own, at
  -- every offered scale.
  EU7_ENTRY = NOISE .. "elevation_europe_v7",
  EU7_GEO = NOISE .. "geo_europe_v7",
  EU7_LAND_COARSE = NOISE .. "land_coarse_europe_v7",
  EU7_DETAIL = NOISE .. "detail_europe_v7",
  EU7_FAR = NOISE .. "far_europe_v7",
  EU7_GX = NOISE .. "gx_europe_v7",
  EU7_GY = NOISE .. "gy_europe_v7",
  EU7_U = NOISE .. "u_europe_v7",
  EU7_V = NOISE .. "v_europe_v7",
  EU7_CX = NOISE .. "cx_europe_v7",
  EU7_CY = NOISE .. "cy_europe_v7",
  EU7_LAKES = NOISE .. "inland_lakes_europe_v6",
  EU7_SHORE = NOISE .. "shore_europe_v4",
  EU7_SPAWN_LAKE = NOISE .. "spawn_lake_europe_v2",
  EU7_SPAWN_BIAS = NOISE .. "spawn_bias_europe_v2",
  EU_WW5 = {NOISE .. "ww_europe_s1_v5", NOISE .. "ww_europe_s2_v5", NOISE .. "ww_europe_s3_v5",
    NOISE .. "ww_europe_s4_v5", NOISE .. "ww_europe_s5_v5", NOISE .. "ww_europe_s6_v5",
    NOISE .. "ww_europe_s12_v5", NOISE .. "ww_europe_s24_v5"},
  EU_CANALS5 = {NOISE .. "canals_europe_s1_v5", NOISE .. "canals_europe_s2_v5", NOISE .. "canals_europe_s3_v5",
    NOISE .. "canals_europe_s4_v5", NOISE .. "canals_europe_s5_v5", NOISE .. "canals_europe_s6_v5",
    NOISE .. "canals_europe_s12_v5", NOISE .. "canals_europe_s24_v5"},
  EU_DAMS5 = {NOISE .. "dams_europe_s1_v5", NOISE .. "dams_europe_s2_v5", NOISE .. "dams_europe_s3_v5",
    NOISE .. "dams_europe_s4_v5", NOISE .. "dams_europe_s5_v5", NOISE .. "dams_europe_s6_v5",
    NOISE .. "dams_europe_s12_v5", NOISE .. "dams_europe_s24_v5"},
  EU_FORDS5 = {NOISE .. "fords_europe_s1_v5", NOISE .. "fords_europe_s2_v5", NOISE .. "fords_europe_s3_v5",
    NOISE .. "fords_europe_s4_v5", NOISE .. "fords_europe_s5_v5", NOISE .. "fords_europe_s6_v5",
    NOISE .. "fords_europe_s12_v5", NOISE .. "fords_europe_s24_v5"},
  EU7_WARP = {
    NOISE .. "warp_x_europe_s1_v2", NOISE .. "warp_y_europe_s1_v2",
    NOISE .. "warp_xp_europe_s1_v2", NOISE .. "warp_yp_europe_s1_v2",
    NOISE .. "warp_x_europe_s2_v2", NOISE .. "warp_y_europe_s2_v2",
    NOISE .. "warp_xp_europe_s2_v2", NOISE .. "warp_yp_europe_s2_v2",
    NOISE .. "warp_x_europe_s3_v2", NOISE .. "warp_y_europe_s3_v2",
    NOISE .. "warp_xp_europe_s3_v2", NOISE .. "warp_yp_europe_s3_v2",
    NOISE .. "warp_x_europe_s4_v2", NOISE .. "warp_y_europe_s4_v2",
    NOISE .. "warp_xp_europe_s4_v2", NOISE .. "warp_yp_europe_s4_v2",
    NOISE .. "warp_x_europe_s5_v2", NOISE .. "warp_y_europe_s5_v2",
    NOISE .. "warp_xp_europe_s5_v2", NOISE .. "warp_yp_europe_s5_v2",
    NOISE .. "warp_x_europe_s6_v2", NOISE .. "warp_y_europe_s6_v2",
    NOISE .. "warp_xp_europe_s6_v2", NOISE .. "warp_yp_europe_s6_v2",
    NOISE .. "warp_x_europe_s12_v2", NOISE .. "warp_y_europe_s12_v2",
    NOISE .. "warp_xp_europe_s12_v2", NOISE .. "warp_yp_europe_s12_v2",
    NOISE .. "warp_x_europe_s24_v2", NOISE .. "warp_y_europe_s24_v2",
    NOISE .. "warp_xp_europe_s24_v2", NOISE .. "warp_yp_europe_s24_v2",
  },
}
-- The Old World and Atlantic spawn city: each map's spawn-city
-- setting moves the spawn through the city fold, with the spawn lake, start mask version 2 and the
-- inland lakes behind the inland lakes switch, and the soft map edge, as Europe's version 6 did:
-- Atlantic's and Old World's version 6, whose frames keep the chain names, and the files and names the 0.3.0
-- versions share with them. One table: the 200-local limit.
local OAS = {
  AT6_GX = NOISE .. "gx_atlantic_v6",
  AT6_GY = NOISE .. "gy_atlantic_v6",
  AT6_U = NOISE .. "u_atlantic_v6",
  AT6_V = NOISE .. "v_atlantic_v6",
  AT6_CX = NOISE .. "cx_atlantic_v6",
  AT6_CY = NOISE .. "cy_atlantic_v6",
  AT_CITY = NOISE .. "city_atlantic",
  AT_CITY_INDEX = NOISE .. "city_index_atlantic_v1",
  AT_CITY_CX = NOISE .. "city_cx_atlantic_v1",
  AT_CITY_CY = NOISE .. "city_cy_atlantic_v1",
  OW6_GX = NOISE .. "gx_olde_world_v6",
  OW6_GY = NOISE .. "gy_olde_world_v6",
  OW6_U = NOISE .. "u_olde_world_v6",
  OW6_V = NOISE .. "v_olde_world_v6",
  OW6_CX = NOISE .. "cx_olde_world_v6",
  OW6_CY = NOISE .. "cy_olde_world_v6",
  OW_CITY = NOISE .. "city_olde_world",
  OW_CITY_INDEX = NOISE .. "city_index_olde_world_v1",
  OW_CITY_CX = NOISE .. "city_cx_olde_world_v1",
  OW_CITY_CY = NOISE .. "city_cy_olde_world_v1",
  OW7_GEO_FILE = "prototypes/generated/geo_olde_world_v2.lua",
  -- The lean fit (data-src/fits/olde_world PROVENANCE, stage lean): the coast fit past scale 6 (coast.split).
  OW8_LEAN_FILE = "prototypes/generated/geo_olde_world_v3.lua",
  OW7_SPAWN_FILE = "prototypes/generated/spawn_olde_world_v2.lua",
  OW7_WW_FILES = {"prototypes/generated/waterways_olde_world_s1_v2.lua",
                   "prototypes/generated/waterways_olde_world_s2_v2.lua",
                   "prototypes/generated/waterways_olde_world_s3_v2.lua",
                   "prototypes/generated/waterways_olde_world_s4_v2.lua",
                   "prototypes/generated/waterways_olde_world_s5_v2.lua",
                   "prototypes/generated/waterways_olde_world_s6_v2.lua",
                   "prototypes/generated/waterways_olde_world_s12_v2.lua",
                   "prototypes/generated/waterways_olde_world_s24_v2.lua"},
  AT7_GEO_FILE = "prototypes/generated/geo_atlantic_v2.lua",
  AT7_SPAWN_FILE = "prototypes/generated/spawn_atlantic_v2.lua",
  AT7_WW_FILES = {"prototypes/generated/waterways_atlantic_s1_v2.lua",
                   "prototypes/generated/waterways_atlantic_s2_v2.lua",
                   "prototypes/generated/waterways_atlantic_s3_v2.lua",
                   "prototypes/generated/waterways_atlantic_s4_v2.lua",
                   "prototypes/generated/waterways_atlantic_s5_v2.lua",
                   "prototypes/generated/waterways_atlantic_s6_v2.lua",
                   "prototypes/generated/waterways_atlantic_s12_v2.lua",
                   "prototypes/generated/waterways_atlantic_s24_v2.lua"},
  -- 0.3.0: Old World's and Atlantic's version 8, the composition of version 7 under names of their own.
  OW8_ENTRY = NOISE .. "elevation_olde_world_v8",
  OW8_GEO = NOISE .. "geo_olde_world_v8",
  -- The two fits OW8_GEO picks between by the folded scale (coast.geo_split).
  OW8_GEO_FINE = NOISE .. "geo_fine_olde_world_v1",
  OW8_GEO_LEAN = NOISE .. "geo_lean_olde_world_v1",
  -- 0.3.1: Old World's geo body past scale 6, which a new world's preset names over OW8_GEO (coast.next): the fine
  -- fit regrown in place boxes (data-src/fits/olde_world PROVENANCE, regrowth stage), bound to version 8's warped
  -- chain.
  OW9_GEO = NOISE .. "geo_olde_world_v9",
  OW9_GEO_FILE = "prototypes/generated/geo_olde_world_v4.lua",
  -- 0.3.2: Old World's Map type version (geography 24, map_type_of 21): its entry, shore, inland lakes and the frayed
  -- coast fit they read past scale 6 (coast_fray).
  OW9_ENTRY = NOISE .. "elevation_olde_world_v9",
  OW9_SHORE = NOISE .. "shore_olde_world_v7",
  OW9_LAKES = NOISE .. "inland_lakes_olde_world_v4",
  OW_GEO_FRAY1 = NOISE .. "geo_fray_olde_world_v1",
  -- with coast.overlay: the frayed fit and overlay layers the frayed geo body combines
  OW_FIT_FRAY1 = NOISE .. "geo_fray_fit_olde_world_v1",
  OW_LAND_FRAY1 = NOISE .. "overlay_land_fray_olde_world_v1",
  OW_WATER_FRAY1 = NOISE .. "overlay_water_fray_olde_world_v1",
  -- 0.3.2: the version 9 river and ford sets at scales 12 and 24, built from waterways.next's files (the Samara Bend
  -- rounded); its other scales and kinds read version 8's sets.
  OW_WW8 = {NOISE .. "ww_olde_world_s12_v8", NOISE .. "ww_olde_world_s24_v8"},
  OW_FORDS8 = {NOISE .. "fords_olde_world_s12_v8", NOISE .. "fords_olde_world_s24_v8"},
  -- the version 9 river warp at scale 12 round the Samara Bend (waterways.next calm): x then y
  OW_WARP3 = {NOISE .. "warp_x_olde_world_s12_v3", NOISE .. "warp_y_olde_world_s12_v3"},
  OW9_WW_FILES = {"prototypes/generated/waterways_olde_world_s12_v3.lua",
                  "prototypes/generated/waterways_olde_world_s24_v3.lua"},
  -- 0.3.2: Old World's geo body past scale 6 over OW9_GEO (coast.overlay): its land and water layers drawn from the
  -- reference raster, combined with it by max and min, each layer bound to version 8's warped chain.
  OW10_GEO = NOISE .. "geo_olde_world_v10",
  OW10_LAND = NOISE .. "overlay_land_olde_world_v1",
  OW10_WATER = NOISE .. "overlay_water_olde_world_v1",
  OW10_LAND_FILE = "prototypes/generated/overlay_land_olde_world_v1.lua",
  OW10_WATER_FILE = "prototypes/generated/overlay_water_olde_world_v1.lua",
  OW8_LAND_COARSE = NOISE .. "land_coarse_olde_world_v8",
  OW8_DETAIL = NOISE .. "detail_olde_world_v8",
  OW8_FAR = NOISE .. "far_olde_world_v8",
  OW8_GX = NOISE .. "gx_olde_world_v8",
  OW8_GY = NOISE .. "gy_olde_world_v8",
  OW8_U = NOISE .. "u_olde_world_v8",
  OW8_V = NOISE .. "v_olde_world_v8",
  OW8_CX = NOISE .. "cx_olde_world_v8",
  OW8_CY = NOISE .. "cy_olde_world_v8",
  OW8_LAKES = NOISE .. "inland_lakes_olde_world_v3",
  OW8_SHORE = NOISE .. "shore_olde_world_v6",
  OW8_SPAWN_LAKE = NOISE .. "spawn_lake_olde_world_v3",
  OW8_SPAWN_BIAS = NOISE .. "spawn_bias_olde_world_v3",
  OW_WW7 = {NOISE .. "ww_olde_world_s1_v7", NOISE .. "ww_olde_world_s2_v7", NOISE .. "ww_olde_world_s3_v7",
    NOISE .. "ww_olde_world_s4_v7", NOISE .. "ww_olde_world_s5_v7", NOISE .. "ww_olde_world_s6_v7",
    NOISE .. "ww_olde_world_s12_v7", NOISE .. "ww_olde_world_s24_v7"},
  OW_CANALS7 = {NOISE .. "canals_olde_world_s1_v7", NOISE .. "canals_olde_world_s2_v7",
    NOISE .. "canals_olde_world_s3_v7", NOISE .. "canals_olde_world_s4_v7", NOISE .. "canals_olde_world_s5_v7",
    NOISE .. "canals_olde_world_s6_v7",
    NOISE .. "canals_olde_world_s12_v7", NOISE .. "canals_olde_world_s24_v7"},
  OW_DAMS7 = {NOISE .. "dams_olde_world_s1_v7", NOISE .. "dams_olde_world_s2_v7", NOISE .. "dams_olde_world_s3_v7",
    NOISE .. "dams_olde_world_s4_v7", NOISE .. "dams_olde_world_s5_v7", NOISE .. "dams_olde_world_s6_v7",
    NOISE .. "dams_olde_world_s12_v7", NOISE .. "dams_olde_world_s24_v7"},
  OW_FORDS7 = {NOISE .. "fords_olde_world_s1_v7", NOISE .. "fords_olde_world_s2_v7", NOISE .. "fords_olde_world_s3_v7",
    NOISE .. "fords_olde_world_s4_v7", NOISE .. "fords_olde_world_s5_v7", NOISE .. "fords_olde_world_s6_v7",
    NOISE .. "fords_olde_world_s12_v7", NOISE .. "fords_olde_world_s24_v7"},
  OW_MOUTH2 = {NOISE .. "mouth_olde_world_s1_v2", NOISE .. "mouth_olde_world_s2_v2", NOISE .. "mouth_olde_world_s3_v2",
    NOISE .. "mouth_olde_world_s4_v2", NOISE .. "mouth_olde_world_s5_v2", NOISE .. "mouth_olde_world_s6_v2",
    NOISE .. "mouth_olde_world_s12_v2", NOISE .. "mouth_olde_world_s24_v2"},
  OW_WARP2 = {
    NOISE .. "warp_x_olde_world_s1_v2", NOISE .. "warp_y_olde_world_s1_v2",
    NOISE .. "warp_xp_olde_world_s1_v2", NOISE .. "warp_yp_olde_world_s1_v2",
    NOISE .. "warp_x_olde_world_s2_v2", NOISE .. "warp_y_olde_world_s2_v2",
    NOISE .. "warp_xp_olde_world_s2_v2", NOISE .. "warp_yp_olde_world_s2_v2",
    NOISE .. "warp_x_olde_world_s3_v2", NOISE .. "warp_y_olde_world_s3_v2",
    NOISE .. "warp_xp_olde_world_s3_v2", NOISE .. "warp_yp_olde_world_s3_v2",
    NOISE .. "warp_x_olde_world_s4_v2", NOISE .. "warp_y_olde_world_s4_v2",
    NOISE .. "warp_xp_olde_world_s4_v2", NOISE .. "warp_yp_olde_world_s4_v2",
    NOISE .. "warp_x_olde_world_s5_v2", NOISE .. "warp_y_olde_world_s5_v2",
    NOISE .. "warp_xp_olde_world_s5_v2", NOISE .. "warp_yp_olde_world_s5_v2",
    NOISE .. "warp_x_olde_world_s6_v2", NOISE .. "warp_y_olde_world_s6_v2",
    NOISE .. "warp_xp_olde_world_s6_v2", NOISE .. "warp_yp_olde_world_s6_v2",
    NOISE .. "warp_x_olde_world_s12_v2", NOISE .. "warp_y_olde_world_s12_v2",
    NOISE .. "warp_xp_olde_world_s12_v2", NOISE .. "warp_yp_olde_world_s12_v2",
    NOISE .. "warp_x_olde_world_s24_v2", NOISE .. "warp_y_olde_world_s24_v2",
    NOISE .. "warp_xp_olde_world_s24_v2", NOISE .. "warp_yp_olde_world_s24_v2",
  },
  AT8_ENTRY = NOISE .. "elevation_atlantic_v8",
  AT8_GEO = NOISE .. "geo_atlantic_v8",
  AT8_LAND_COARSE = NOISE .. "land_coarse_atlantic_v8",
  AT8_DETAIL = NOISE .. "detail_atlantic_v8",
  AT8_FAR = NOISE .. "far_atlantic_v8",
  AT8_GX = NOISE .. "gx_atlantic_v8",
  AT8_GY = NOISE .. "gy_atlantic_v8",
  AT8_U = NOISE .. "u_atlantic_v8",
  AT8_V = NOISE .. "v_atlantic_v8",
  AT8_CX = NOISE .. "cx_atlantic_v8",
  AT8_CY = NOISE .. "cy_atlantic_v8",
  AT8_LAKES = NOISE .. "inland_lakes_atlantic_v3",
  AT8_SHORE = NOISE .. "shore_atlantic_v6",
  AT8_SPAWN_LAKE = NOISE .. "spawn_lake_atlantic_v3",
  AT8_SPAWN_BIAS = NOISE .. "spawn_bias_atlantic_v3",
  -- 0.3.1: Atlantic's next spawn folds over the city table's version 2 (spawn_next), which a new world whose spawn
  -- city is past the released folds' cities names over the released ones.
  AT_CITY_CX2 = NOISE .. "city_cx_atlantic_v2",
  AT_CITY_CY2 = NOISE .. "city_cy_atlantic_v2",
  AT9_SPAWN_LAKE = NOISE .. "spawn_lake_atlantic_v4",
  AT9_SPAWN_BIAS = NOISE .. "spawn_bias_atlantic_v4",
  AT9_SPAWN_FILE = "prototypes/generated/spawn_atlantic_v3.lua",
  AT_WW7 = {NOISE .. "ww_atlantic_s1_v7", NOISE .. "ww_atlantic_s2_v7", NOISE .. "ww_atlantic_s3_v7",
    NOISE .. "ww_atlantic_s4_v7", NOISE .. "ww_atlantic_s5_v7", NOISE .. "ww_atlantic_s6_v7",
    NOISE .. "ww_atlantic_s12_v7", NOISE .. "ww_atlantic_s24_v7"},
  AT_CANALS7 = {NOISE .. "canals_atlantic_s1_v7", NOISE .. "canals_atlantic_s2_v7", NOISE .. "canals_atlantic_s3_v7",
    NOISE .. "canals_atlantic_s4_v7", NOISE .. "canals_atlantic_s5_v7", NOISE .. "canals_atlantic_s6_v7",
    NOISE .. "canals_atlantic_s12_v7", NOISE .. "canals_atlantic_s24_v7"},
  AT_DAMS7 = {NOISE .. "dams_atlantic_s1_v7", NOISE .. "dams_atlantic_s2_v7", NOISE .. "dams_atlantic_s3_v7",
    NOISE .. "dams_atlantic_s4_v7", NOISE .. "dams_atlantic_s5_v7", NOISE .. "dams_atlantic_s6_v7",
    NOISE .. "dams_atlantic_s12_v7", NOISE .. "dams_atlantic_s24_v7"},
  AT_FORDS7 = {NOISE .. "fords_atlantic_s1_v7", NOISE .. "fords_atlantic_s2_v7", NOISE .. "fords_atlantic_s3_v7",
    NOISE .. "fords_atlantic_s4_v7", NOISE .. "fords_atlantic_s5_v7", NOISE .. "fords_atlantic_s6_v7",
    NOISE .. "fords_atlantic_s12_v7", NOISE .. "fords_atlantic_s24_v7"},
  AT_MOUTH2 = {NOISE .. "mouth_atlantic_s1_v2", NOISE .. "mouth_atlantic_s2_v2", NOISE .. "mouth_atlantic_s3_v2",
    NOISE .. "mouth_atlantic_s4_v2", NOISE .. "mouth_atlantic_s5_v2", NOISE .. "mouth_atlantic_s6_v2",
    NOISE .. "mouth_atlantic_s12_v2", NOISE .. "mouth_atlantic_s24_v2"},
  AT_WARP2 = {
    NOISE .. "warp_x_atlantic_s1_v2", NOISE .. "warp_y_atlantic_s1_v2",
    NOISE .. "warp_xp_atlantic_s1_v2", NOISE .. "warp_yp_atlantic_s1_v2",
    NOISE .. "warp_x_atlantic_s2_v2", NOISE .. "warp_y_atlantic_s2_v2",
    NOISE .. "warp_xp_atlantic_s2_v2", NOISE .. "warp_yp_atlantic_s2_v2",
    NOISE .. "warp_x_atlantic_s3_v2", NOISE .. "warp_y_atlantic_s3_v2",
    NOISE .. "warp_xp_atlantic_s3_v2", NOISE .. "warp_yp_atlantic_s3_v2",
    NOISE .. "warp_x_atlantic_s4_v2", NOISE .. "warp_y_atlantic_s4_v2",
    NOISE .. "warp_xp_atlantic_s4_v2", NOISE .. "warp_yp_atlantic_s4_v2",
    NOISE .. "warp_x_atlantic_s5_v2", NOISE .. "warp_y_atlantic_s5_v2",
    NOISE .. "warp_xp_atlantic_s5_v2", NOISE .. "warp_yp_atlantic_s5_v2",
    NOISE .. "warp_x_atlantic_s6_v2", NOISE .. "warp_y_atlantic_s6_v2",
    NOISE .. "warp_xp_atlantic_s6_v2", NOISE .. "warp_yp_atlantic_s6_v2",
    NOISE .. "warp_x_atlantic_s12_v2", NOISE .. "warp_y_atlantic_s12_v2",
    NOISE .. "warp_xp_atlantic_s12_v2", NOISE .. "warp_yp_atlantic_s12_v2",
    NOISE .. "warp_x_atlantic_s24_v2", NOISE .. "warp_y_atlantic_s24_v2",
    NOISE .. "warp_xp_atlantic_s24_v2", NOISE .. "warp_yp_atlantic_s24_v2",
  },
  -- 0.3.2: Atlantic's geo body past scale 6, which a new world's preset names over AT8_GEO (coast.next): the coast fit
  -- regrown in place boxes (data-src/fits/atlantic PROVENANCE, next stage), bound to version 8's warped chain.
  AT9_GEO = NOISE .. "geo_atlantic_v9",
  AT9_GEO_FILE = "prototypes/generated/geo_atlantic_v3.lua",
  -- 0.3.2: Atlantic's Map type version (geography 25, map_type_of 22): its entry, shore, inland lakes and the frayed
  -- coast fit they read past scale 6 (coast_fray).
  AT9_ENTRY = NOISE .. "elevation_atlantic_v9",
  AT9_SHORE = NOISE .. "shore_atlantic_v7",
  AT9_LAKES = NOISE .. "inland_lakes_atlantic_v4",
  AT_GEO_FRAY1 = NOISE .. "geo_fray_atlantic_v1",
  -- with coast.overlay: the frayed fit and overlay layers the frayed geo body combines
  AT_FIT_FRAY1 = NOISE .. "geo_fray_fit_atlantic_v1",
  AT_LAND_FRAY1 = NOISE .. "overlay_land_fray_atlantic_v1",
  AT_WATER_FRAY1 = NOISE .. "overlay_water_fray_atlantic_v1",
  -- 0.3.2: Atlantic's geo body past scale 6 over AT9_GEO (coast.overlay): its land and water layers drawn from the
  -- reference raster, combined with it by max and min, each layer bound to version 8's warped chain.
  AT10_GEO = NOISE .. "geo_atlantic_v10",
  AT10_LAND = NOISE .. "overlay_land_atlantic_v1",
  AT10_WATER = NOISE .. "overlay_water_atlantic_v1",
  AT10_LAND_FILE = "prototypes/generated/overlay_land_atlantic_v1.lua",
  AT10_WATER_FILE = "prototypes/generated/overlay_water_atlantic_v1.lua",
}
local OAS_SETS = {
  atlantic_v8 = {ww = OAS.AT_WW7, canals = OAS.AT_CANALS7, dams = OAS.AT_DAMS7, fords = OAS.AT_FORDS7},
  olde_world_v8 = {ww = OAS.OW_WW7, canals = OAS.OW_CANALS7, dams = OAS.OW_DAMS7, fords = OAS.OW_FORDS7},
  -- 0.3.2: Old World's version 9 (a Map type version): version 8's sets, the rivers and fords past scale 6 of their own
  olde_world_v9 = {
    ww = {OAS.OW_WW7[1], OAS.OW_WW7[2], OAS.OW_WW7[3], OAS.OW_WW7[4], OAS.OW_WW7[5], OAS.OW_WW7[6], OAS.OW_WW8[1],
          OAS.OW_WW8[2]},
    canals = OAS.OW_CANALS7, dams = OAS.OW_DAMS7,
    fords = {OAS.OW_FORDS7[1], OAS.OW_FORDS7[2], OAS.OW_FORDS7[3], OAS.OW_FORDS7[4], OAS.OW_FORDS7[5],
             OAS.OW_FORDS7[6], OAS.OW_FORDS8[1], OAS.OW_FORDS8[2]},
  },
  europe_v7 = {ww = ELN.EU_WW5, canals = ELN.EU_CANALS5, dams = ELN.EU_DAMS5, fords = ELN.EU_FORDS5},
}
-- Destroyed Europe (ARCHITECTURE.md, "Expression inventory"). The toggle key tn_destroyed
-- is a name switch to tn_one and tn_zero, baked on only when its setting is on and Alien Biomes is loaded
-- (without Alien Biomes the switch drops at the data stage). The key (K) and the bodies, one table so this
-- file stays under Lua's 200 locals per function: the zone (the region layer's zone depth cut by the start
-- disc), its heat, the next version of climate-tiles' Alien Biomes temperature, which lifts the zone above
-- 100, and per map with a city fold the random pick over the cities outside the zone.
local DE = {
  chaos_fine = NOISE .. "destroyed_fine_v1",
  chaos_macro = NOISE .. "destroyed_macro_v1",
  chaos_kind = NOISE .. "destroyed_kind_v1",
  chaos_class = NOISE .. "destroyed_class_v1",
  chaos_grass = NOISE .. "chaos_red_grass_v1",
  chaos_black_sand = NOISE .. "chaos_black_sand_v1",
  chaos_black_dirt = NOISE .. "chaos_black_dirt_v1",
  chaos_red_dirt = NOISE .. "chaos_red_dirt_v1",
  chaos_red_sand = NOISE .. "chaos_red_sand_v1",
  K = NOISE .. "destroyed",
  zone = NOISE .. "destroyed_zone_v1",
  heat = NOISE .. "destroyed_heat_v1",
  zone2 = NOISE .. "destroyed_zone_v2",
  heat2 = NOISE .. "destroyed_heat_v2",
  class2 = NOISE .. "destroyed_class_v2",
  edge = NOISE .. "destroyed_edge_v1",
  blob = NOISE .. "destroyed_blob_v1",
  flow = NOISE .. "destroyed_flow_v1",
  lava = NOISE .. "destroyed_lava_v1",
  kind2 = NOISE .. "destroyed_kind_v2",
  macro2 = NOISE .. "destroyed_macro_v2",
  reach = NOISE .. "destroyed_reach_v1",
  open = NOISE .. "destroyed_open_v1",
  thin = NOISE .. "destroyed_thin_v1",
  clear = NOISE .. "destroyed_clear",
  dead = NOISE .. "destroyed_dead_v1",
  dead2 = NOISE .. "destroyed_dead_v2",
  dead_noise = NOISE .. "destroyed_dead_noise_v1",
  palm_a = NOISE .. "destroyed_palm_a_v1",
  palm_b = NOISE .. "destroyed_palm_b_v1",
  palm_a2 = NOISE .. "destroyed_palm_a_v2",
  palm_b2 = NOISE .. "destroyed_palm_b_v2",
  chaos_grey = NOISE .. "chaos_grey_dirt_v1",
  out_land = NOISE .. "destroyed_outline_land_v1",
  out_sea = NOISE .. "destroyed_outline_sea_v1",
  out_inside = NOISE .. "destroyed_outline_inside_v1",
  out_sd = NOISE .. "destroyed_outline_sd_v1",
  out_isles = NOISE .. "destroyed_outline_isles_v1",
  out_present = NOISE .. "destroyed_outline_present_v1",
  out_depth = NOISE .. "destroyed_outline_depth_v1",
  -- 0.3.0's next outline (prototypes/tables/zone_outline_v2.lua), its cuts, and the next zone and class
  out_land2 = NOISE .. "destroyed_outline_land_v2",
  out_sea2 = NOISE .. "destroyed_outline_sea_v2",
  out_inside2 = NOISE .. "destroyed_outline_inside_v2",
  out_sd2 = NOISE .. "destroyed_outline_sd_v2",
  out_present2 = NOISE .. "destroyed_outline_present_v2",
  out_depth2 = NOISE .. "destroyed_outline_depth_v2",
  out_nordic = NOISE .. "destroyed_outline_nordic_v1",
  out_iberia = NOISE .. "destroyed_outline_iberia_v1",
  zone3 = NOISE .. "destroyed_zone_v3",
  heat3 = NOISE .. "destroyed_heat_v3",
  class3 = NOISE .. "destroyed_class_v3",
  gap = NOISE .. "destroyed_gap_v1",
  -- 0.3.1's devastation field (destroyed.dev): one ordered gradient from the zone's edge in
  dev = NOISE .. "destroyed_dev_v1",
  dev_ragged = NOISE .. "destroyed_dev_ragged_v1",
  dev_width = NOISE .. "destroyed_dev_width_v1",
  heat4 = NOISE .. "destroyed_heat_v4",
  class4 = NOISE .. "destroyed_class_v4",
  reach2 = NOISE .. "destroyed_reach_v2",
  open2 = NOISE .. "destroyed_open_v2",
  out_present3 = NOISE .. "destroyed_outline_present_v3",
  out_depth3 = NOISE .. "destroyed_outline_depth_v3",
  chaos_dry = NOISE .. "chaos_brown_dirt_v1",
  dev_wobble_a = NOISE .. "destroyed_dev_wobble_a_v1",
  dev_wobble_b = NOISE .. "destroyed_dev_wobble_b_v1",
  dev_fray = NOISE .. "destroyed_dev_fray_v1",
  -- 0.3.2's next devastation field (destroyed.dev.next): the position with a finer fray, the width at a jogged point
  dev2 = NOISE .. "destroyed_dev_v2",
  dev_width2 = NOISE .. "destroyed_dev_width_v2",
  dev_jog_x = NOISE .. "destroyed_dev_jog_x_v1",
  dev_jog_y = NOISE .. "destroyed_dev_jog_y_v1",
  dev_fray2 = NOISE .. "destroyed_dev_fray_v2",
  class5 = NOISE .. "destroyed_class_v5",
  chaos_grey2 = NOISE .. "chaos_grey_rock_v1",
  -- 0.4.0: the next class's successor with a widened grey band; no preset names it
  class6 = NOISE .. "destroyed_class_v6",
  -- 0.4.0: class6's successor, the class the 0.4.0 presets name; grey rock also covers the dev>0 zone fringe
  -- (reach<=0), so the frayed zone edge reads grey rock instead of the Koppen base where Alien Biomes placed snow.
  class7 = NOISE .. "destroyed_class_v7",
  -- 1.0.0: the position that also yields to every range's snow and grey rim (destroyed.dev.ranges)
  dev3 = NOISE .. "destroyed_dev_v3",
  -- 1.0.0: the trees of a range the zone encloses (destroyed.dev.range_trees): their reach, the trees' mask key
  -- and its body, and the dead trees' next body
  tree_reach = NOISE .. "destroyed_tree_reach_v1",
  range_open = NOISE .. "destroyed_range_open",
  range_open1 = NOISE .. "destroyed_range_open_v1",
  dead3 = NOISE .. "destroyed_dead_v3",
  -- 1.1.0: the position that also yields to the north snow inside the Moscow zone at Chaos, the class that lays
  -- grey rock on the ground it gives back where the world lays no snow, and the open mask that holds the zone's plants
  -- there (moscow.keep.chaos)
  dev4 = NOISE .. "destroyed_dev_v4",
  class8 = NOISE .. "destroyed_class_v8",
  open3 = NOISE .. "destroyed_open_v3",
  -- 0.3.1's Moscow zone (config.lua moscow): its outline, the Moscow position, the picklist's key and the Europe key
  mz_land = NOISE .. "moscow_outline_land_v1",
  mz_sea = NOISE .. "moscow_outline_sea_v1",
  mz_inside = NOISE .. "moscow_outline_inside_v1",
  mz_sd = NOISE .. "moscow_outline_sd_v1",
  mz_present = NOISE .. "moscow_outline_present_v1",
  mz_depth = NOISE .. "moscow_outline_depth_v1",
  mz_dev = NOISE .. "moscow_dev_v1",
  mz_dev2 = NOISE .. "moscow_dev_v2",
  mz_key = NOISE .. "moscow",
  eu_key = NOISE .. "destroyed_europe",
  temperature = NOISE .. "temperature_ab_v2",
  pool_europe = NOISE .. "city_pool_europe_v1",
  pool_atlantic = NOISE .. "city_pool_atlantic_v1",
  pool_olde_world = NOISE .. "city_pool_olde_world_v1",
}

-- Blue corrupted UK and Australia (config.lua blue). One table, as the destroyed-europe names are.
local BC = {
  K = NOISE .. "blue",
  reach = NOISE .. "blue_reach_v1",
  open = NOISE .. "blue_open_v1",
  macro = NOISE .. "blue_macro_v1",
  kind = NOISE .. "blue_kind_v1",
  dry = NOISE .. "blue_dry_v1",
  field = NOISE .. "blue_field_v1",
  class = NOISE .. "blue_class_v1",
  keep = NOISE .. "blue_keep_v1",
  keep_under = NOISE .. "blue_keep_under_v1",
  temperature = NOISE .. "blue_temperature_v1",
  temperature_under = NOISE .. "blue_temperature_under",
  moisture = NOISE .. "blue_moisture_v1",
  moisture_under = NOISE .. "blue_moisture_under",
  aux = NOISE .. "blue_aux_v1",
  aux_under = NOISE .. "blue_aux_under",
  palm_a = NOISE .. "blue_palm_a_v1",
  palm_a_under = NOISE .. "blue_palm_a_under",
  palm_b = NOISE .. "blue_palm_b_v1",
  palm_b_under = NOISE .. "blue_palm_b_under",
  mauve_2 = NOISE .. "blue_mauve_grass_2_v1",
  mauve_1 = NOISE .. "blue_mauve_grass_1_v1",
  purple_2 = NOISE .. "blue_purple_grass_2_v1",
  purple_1 = NOISE .. "blue_purple_grass_1_v1",
  blue_2 = NOISE .. "blue_blue_grass_2_v1",
  blue_1 = NOISE .. "blue_blue_grass_1_v1",
  aubergine_dirt = NOISE .. "blue_aubergine_dirt_v1",
  purple_dirt = NOISE .. "blue_purple_dirt_v1",
  aubergine_rim = NOISE .. "blue_aubergine_rim_v1",
  out_britain = NOISE .. "blue_outline_britain_v1",
  out_australia = NOISE .. "blue_outline_australia_v1",
  out_sea = NOISE .. "blue_outline_sea_v1",
  out_ulster = NOISE .. "blue_outline_ulster_v1",
  out_land = NOISE .. "blue_outline_land_v1",
  out_depth = NOISE .. "blue_outline_depth_v1",
  -- 0.3.1's next outline (prototypes/tables/zone_blue_v2.lua): the United Kingdom alone
  out_britain2 = NOISE .. "blue_outline_britain_v2",
  out_sea2 = NOISE .. "blue_outline_sea_v2",
  out_ulster2 = NOISE .. "blue_outline_ulster_v2",
  out_land2 = NOISE .. "blue_outline_land_v2",
  out_depth2 = NOISE .. "blue_outline_depth_v2",
  -- 0.3.1's Moscow zone when Corrupted (config.lua moscow): the UK key, the union of the outlines, the Moscow depth and
  -- its gap to the Chaos zone, the class with the snow join and the grey rim's keep
  uk_key = NOISE .. "blue_uk",
  out_depth3 = NOISE .. "blue_outline_depth_v3",
  mz_corrupt = NOISE .. "moscow_corrupt_depth_v1",
  mz_gap = NOISE .. "moscow_corrupt_gap_v1",
  class_under = NOISE .. "blue_class_under_v1",
  class2 = NOISE .. "blue_class_v2",
  rim_keep = NOISE .. "corrupt_rim_keep_v1",
  mz_snow_0 = NOISE .. "moscow_snow_0_v1",
  mz_snow_2 = NOISE .. "moscow_snow_2_v1",
  -- 1.1.0: the class that leaves the world's own snow and the enclosed ranges' grey rim inside the Corrupted Moscow
  -- zone (moscow.keep.corrupted)
  class3 = NOISE .. "blue_class_v3",
}

-- Exact coastlines: the per-save name switch a map's preset carries, set to the
-- neutral body tn_one, only when the startup setting is on and that map passed all four flip checks
-- (design rule 9). Absent means off, and no prototype defines it: control code alone reads it. One table, as
-- the destroyed-europe names are (Lua's 200 locals per function).
local BFN = {
  K = NOISE .. "bandfix",
}

return {
  identity = {
    id = ID,
    title = "Terra Nauvis",
    -- 1.0.0: the name the mod list and the mod portal show (info.json title, locale mod-name). `title` above
    -- stays the short name that starts every log and chat line.
    mod_title = "Terra Nauvis: Earth Maps",
    version = "1.1.0",
    author = "Jake Mismas",
    homepage = "https://github.com/jakemismas/factorio-terra-nauvis",
    factorio_version = "2.1",
    base_version = "2.1.24",
    setting_prefix = ID .. "-",
    noise_prefix = NOISE,
  },

  -- Reference-pixel conventions, mirrored by tools/earthgeo.py: plate carree at
  -- px_per_degree; pixel (col, row) spans [col, col + 1) with its centre at
  -- lon = lon_left_edge + (col + 0.5) / px_per_degree and lat = lat_top_edge - (row + 0.5) / px_per_degree.
  -- At scale s, tile t samples pixel floor(t / s + wr) (the floor origin). The integer-corner
  -- offset is floor(s / corner_offset_divisor) tiles: the coordinate chain reads the fit at
  -- u = (gx - floor(s / 2)) / s + wr, so the tile holding a pixel centre, evaluated at its integer
  -- corner, reads the fit exactly at that centre at every integer scale (the coordinate tests prove it
  -- at scales 1, 3 and 6 against a test build without it). This is the one copy of the
  -- constant; tools/earthgeo.py reads it from here.
  coordinates = {
    px_per_degree = 45,
    origin = "floor",
    corner_offset_divisor = 2,
  },

  -- The one number formatter every expression string uses, so the text is byte-stable.
  number_format = "%.9g",

  -- EarthMaps reference rasters (data-src/earthmaps/<key>.json): size, EarthMaps radii and edges.
  -- id is the map's tn_map value (control code reads the map from it): a positive integer, one per
  -- map, never reused or changed once landed, because saves hold it (tnconfig's id-space check and
  -- the static append-only check against main and origin/main; ARCHITECTURE.md, "Release versioning
  -- policy", rule 4).
  maps = {
    europe = {
      key = "europe", id = 1, setting_key = "europe", display = "Europe",
      width_px = 2400, height_px = 1704, wr = 1200, hr = 852,
      lon_left_edge = -11.0222, lat_top_edge = 71.9333,
    },
    atlantic = {
      key = "atlantic", id = 2, setting_key = "atlantic", display = "Atlantic",
      width_px = 15689, height_px = 6524, wr = 7844, hr = 3262,
      lon_left_edge = -168.6444, lat_top_edge = 87.1778,
    },
    olde_world = {
      key = "olde_world", id = 3, setting_key = "old-world", display = "Old World",
      width_px = 8963, height_px = 5847, wr = 4481, hr = 2923,
      lon_left_edge = -19.1778, lat_top_edge = 82.0889,
    },
  },
  map_order = {"europe", "atlantic", "olde_world"},

  -- Integer scales in tiles per reference pixel. The scale setting's locale labels carry each map's world
  -- size W s x H s in tiles; the static locale check tests every label against these sizes. values is
  -- what the setting offers; released is what a geography version without a `scales` field of its own
  -- serves; exact_coast is where Exact coastlines acts. Past scale 6 a written coast
  -- follows reference pixels 12 and 24 tiles across, so it reads as long straight runs and stairs where the
  -- noise coast reads as land.
  scales = {values = SCALE_LISTS.offered, released = SCALE_LISTS.released, exact_coast = SCALE_LISTS.released,
            default = 6},

  -- Scales past a released version's list, per map. That version's entry, spawn bodies and sets are frozen, and its
  -- entry falls through to the scale 6 sets and the scale 6 ponds at any other scale, so these scales read an entry
  -- of their own: the same composition on the same chain, fit and spawn bodies, by name, over sets of their own. It
  -- takes no tn_geo: nothing but the elevation name and the ford set differs, and no save of the version holds these
  -- scales. geo_id names the version it extends; waterway_files its slot in
  -- waterways.lua FILES.
  scale_extensions = {},

  -- Mod settings. Values are short ASCII tokens, so labels can change without invalidating stored
  -- values. Each new setting goes here and into tests/design-rules.json.
  settings = {
    scale = {
      name = ID .. "-scale", type = "string-setting", setting_type = "startup",
      default_value = "6", allowed_values = {"1", "2", "3", "4", "5", "6", "12", "24"}, order = "a",
    },
    -- The spawn city per map (default random; Luxembourg is not offered):
    -- "random", then every city of the map's table in prototypes/tables/cities.lua. A value's
    -- position gives the per-save number the preset bakes (random 0, the first city 1), so this
    -- order is the fold's order and never changes once landed (saves hold the number).
    spawn_city_europe = {
      name = ID .. "-spawn-city-europe", type = "string-setting", setting_type = "startup",
      default_value = "random",
      allowed_values = {
        "random", "tirana", "andorra-la-vella", "vienna", "minsk", "brussels", "sarajevo", "sofia", "zagreb",
        "prague", "tallinn", "helsinki", "paris", "berlin", "athens", "budapest", "rome", "pristina", "riga",
        "vaduz", "vilnius", "chisinau", "monaco", "podgorica", "amsterdam", "skopje", "oslo", "warsaw",
        "lisbon", "bucharest", "moscow", "san-marino", "belgrade", "bratislava", "ljubljana", "madrid",
        "stockholm", "bern", "ankara", "kyiv", "london",
      },
      order = "b-a",
    },
    -- The new maps' spawn cities (default random), in the same shape, read by each map's city fold.
    spawn_city_atlantic = {
      name = ID .. "-spawn-city-atlantic", type = "string-setting", setting_type = "startup",
      default_value = "random",
      allowed_values = {
        "random", "prague", "madrid", "london", "kovdor", "munguy", "xeta", "yakutia", "zyryanka", "kharkiv",
        "huambo", "mongo", "dangila", "bamako", "akka", "waddan", "johannesburg", "songea", "tabuk", "chengdu",
        "nanchang", "songling", "delhi", "hampi", "bam", "aktobe", "semey", "moron", "bangkok", "mexico-city",
        "ellesmere-island", "fort-liard", "hearst", "mid-baffin", "okak", "saskatoon", "yellowknife", "qaanaaq",
        "summit-camp", "uranienborg", "albany", "boise", "minneapolis", "el-paso", "hughes", "montgomery", "cordoba",
        "palmas", "iquitos", "griffith", "newman",
        -- Appended values (spawn_next): every earlier value keeps its number.
        "frankfurt", "moscow", "null",
      },
      order = "b-b",
    },
    spawn_city_olde_world = {
      name = ID .. "-spawn-city-old-world", type = "string-setting", setting_type = "startup",
      default_value = "random",
      allowed_values = {
        "random", "prague", "madrid", "london", "kovdor", "munguy", "xeta", "yakutia", "zyryanka", "kharkiv",
        "huambo", "mongo", "dangila", "bamako", "akka", "waddan", "johannesburg", "songea", "tabuk", "chengdu",
        "nanchang", "songling", "delhi", "hampi", "bam", "aktobe", "semey", "moron", "bangkok", "griffith", "newman",
        "frankfurt", "aachen", "moscow",
      },
      order = "b-c",
    },
    -- Canals (default on): Kiel and Corinth on every map, Suez on
    -- Old World and Atlantic, Panama on Atlantic, open at max(7, scale) tiles; off keeps every
    -- isthmus closed, the drawn leaks under a dam. Baked per save through the toggle tn_canals.
    -- 1.0.0: hidden and pinned on (hidden with forced_value), so every new world has its canals; a world
    -- made with the setting off keeps the value its preset baked.
    canals = {
      name = ID .. "-canals", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-d",
      hidden = true, forced_value = true,
    },
    -- Great forests (default on): the 16 adopted forests of
    -- the region layer hold about twice the trees of the land around them. Baked per save through the hook
    -- gate tn_forests_on.
    -- 1.0.0: hidden and pinned on (hidden with forced_value); a world made with the setting off keeps the
    -- value its preset baked.
    great_forests = {
      name = ID .. "-great-forests", type = "bool-setting", setting_type = "startup", default_value = true,
      order = "c-b", hidden = true, forced_value = true,
    },
    -- Ridges (default on): cliff ridges along the 16 adopted ranges with
    -- rail-width passes, the only cliffs on a Terra Nauvis world. Baked per save through the toggle
    -- tn_ridges; off gives 0 cliffs (a constant crest distance places none).
    ridges = {
      name = ID .. "-ridges", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-c",
    },
    -- Hotspots (default on): historical ore
    -- hotspots with heavier biters and the offshore fields' deepwater discs and wells. Baked per save
    -- through the toggle tn_hotspots and each map's offshore stamp key.
    hotspots = {
      name = ID .. "-hotspots", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-a",
    },
    -- Hotspot amount: the ore and oil in every hotspot, a percentage of what
    -- the rows hold. On the first two tables it multiplies richness and nothing else, so no footprint moves; on
    -- 0.3.0's solid ores (hotspots_v2.v3) 100 is the designed amount and the percentage multiplies the field's
    -- bodies, so its ore per tile stays as designed, and the map's size and richness sliders reach it too. Oil
    -- keeps the richness rule. Baked per save through tn_hotspot_amount.
    -- 1.0.0: hidden and pinned at 100. The game applies forced_value to bool settings only, so the pin is
    -- the one-entry allowed_values: a stored 50, 200 or 400 is no longer valid and reads as the default. A
    -- world made at another amount keeps the number its preset baked.
    hotspot_amount = {
      name = ID .. "-hotspot-amount", type = "string-setting", setting_type = "startup", default_value = "100",
      allowed_values = {"100"}, order = "c-aa", hidden = true,
    },
    -- Regional scarcity (0.3.0, default medium): past about 1,500 tiles from the spawn at scale
    -- 12, regular ore outside each resource's provinces keeps a share of its patches (resources.scarcity). Baked
    -- per save through tn_scarcity (0 off, 1 medium, 2 strong).
    regional_scarcity = {
      name = ID .. "-regional-scarcity", type = "string-setting", setting_type = "startup", default_value = "medium",
      allowed_values = {"off", "medium", "strong"}, order = "c-ab",
    },
    -- Inland lakes (default off): spawn-cities'
    -- sparse random inland lakes. Off leaves the spawn lake at the chosen city, the rivers and the real
    -- lakes of the coast fit as the only fresh water. Baked per save through the toggle tn_inland_lakes.
    inland_lakes = {
      name = ID .. "-inland-lakes", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-e",
    },
    -- Destroyed Europe (default off): Alien Biomes volcanic
    -- ground inside the zone's polygon, its edges moving with the map seed, never at the spawn. It needs Alien
    -- Biomes: without it the toggle bakes off and the mod warns (design rule 25). Baked per save through the
    -- toggle tn_destroyed.
    destroyed_europe = {
      name = ID .. "-destroyed-europe", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-f",
    },
    -- Blue corrupted UK (default off): Alien Biomes' mauve grass, with blue and purple ground mixed in, on the UK
    -- (worlds made before 0.3.1 also on Australia). It needs Alien Biomes: without it the toggle bakes off. Baked per
    -- save through the toggle tn_blue.
    blue_corrupted = {
      name = ID .. "-blue-corrupted", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-fa",
    },
    -- North snow (0.3.1, default medium): how far south the snow line of Eurasia lies, low the 0.3.0 line, medium about
    -- twice its depth, high about three times. Baked per save through tn_north_snow (the level's index,
    -- climate.north_snow).
    north_snow = {
      name = ID .. "-north-snow", type = "string-setting", setting_type = "startup", default_value = "medium",
      allowed_values = {"low", "medium", "high"}, order = "c-fc",
    },
    -- Moscow zone (0.3.1, default normal): normal leaves the region as it is, chaos makes it a Destroyed Europe zone,
    -- corrupted a Blue corrupted one, inside one outline (config.lua moscow). It needs Alien Biomes: without it the
    -- level bakes normal and the mod warns. Baked per save through tn_moscow (the level's index).
    moscow_zone = {
      name = ID .. "-moscow-zone", type = "string-setting", setting_type = "startup", default_value = "normal",
      allowed_values = {"normal", "chaos", "corrupted"}, order = "c-fb",
    },
    -- Exact coastlines (on by default, because Old World's and Atlantic's coasts need it to match
    -- Europe's): a new world's preset bakes the band-fix
    -- key from it, for the maps bandfix.maps lists.
    -- 1.0.0: hidden and pinned on (hidden with forced_value); a world made with the setting off keeps its
    -- preset's key unset, so its coast stays as it generated.
    exact_coast = {
      name = ID .. "-exact-coast", type = "bool-setting", setting_type = "startup", default_value = true,
      order = "c-g", hidden = true, forced_value = true,
    },
    -- Koppen biomes (0.4.0, default on): the headline climate feature of 0.4.0. On, a new
    -- world's tiles, trees and decoratives follow Koppen-Geiger classes computed per tile from four
    -- smooth climate fields; off keeps the continuous 0.3.2 climate. Baked per save through the toggle
    -- tn_koppen. The class field (tn_koppen_class_v1) is computed per tile, and the centroid snap
    -- over the warped classifier drives the tiles.
    -- 1.0.0: shelved. The setting is hidden and pinned off (hidden with forced_value, which the game
    -- applies to a bool setting whatever mod-settings.dat stored), so every new world bakes tn_koppen
    -- off and takes the continuous 0.3.2 climate. Every Koppen body stays defined, so a world made on
    -- 0.4.0 with the setting on keeps the Koppen names its save holds.
    koppen = {
      name = ID .. "-koppen", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-aaa", hidden = true, forced_value = false,
    },
    -- City markers (default off): runtime-global, so any admin can switch
    -- it in a running game; on, the map view shows every city of the world's map (scripts/markers.lua).
    city_markers = {
      name = ID .. "-city-markers", type = "bool-setting", setting_type = "runtime-global", default_value = false,
      order = "d-a",
    },
  },
  setting_order = {"scale", "koppen", "spawn_city_europe", "spawn_city_atlantic", "spawn_city_olde_world", "canals",
                   "great_forests", "ridges", "hotspots", "hotspot_amount", "regional_scarcity",
                   "inland_lakes",
                   "destroyed_europe", "blue_corrupted", "moscow_zone", "north_snow", "exact_coast", "city_markers"},

  -- Map-gen presets, sorted right after Default ("a") and before Rich resources ("b").
  -- withheld_with lists the mods whose presence withholds a preset (presets.lua defines no such
  -- preset while one is loaded). From europe-coast to region-layer every preset listed Alien Biomes:
  -- its 0.8.0 palms (tree-palm-a, tree-palm-b) read elevation in the Entity program, so beside it a
  -- preset carried its fine field there and broke the firewall (ARCHITECTURE.md, "Programs and the
  -- firewall"), so the preset was withheld beside Alien Biomes. climate-tiles ships the palm switch
  -- (every Earth preset points each palm's keys at an Earth copy that reads the palm constant where
  -- AB reads elevation; tiles.palm), so the lists are empty and the presets are
  -- offered beside Alien Biomes again. Withholding acted on new worlds only: a world made from a
  -- preset that later loads beside a listed mod still names its fine field, so control code warns
  -- once and records it while a list names that mod (scripts/guards.lua). A save made before the
  -- switch keeps its palms on its fine field for life: no load writes the palm keys into it.
  presets = {
    europe = {name = ID .. "-europe", map = "europe", order = "a-tn-a", withheld_with = {}},
    atlantic = {name = ID .. "-atlantic", map = "atlantic", order = "a-tn-b", withheld_with = {}},
    olde_world = {name = ID .. "-old-world", map = "olde_world", order = "a-tn-c", withheld_with = {}},
  },
  preset_order = {"europe", "atlantic", "olde_world"},

  -- The new-game Terrain tab: the properties it offers as dropdowns besides elevation (each one an
  -- intended_property beside Alien Biomes) and every expression a Terra Nauvis preset can select under
  -- them, in any settings combination, Koppen biomes on included for the worlds made with 0.4.0. The
  -- dropdown shows a selected expression by its [noise-expression] locale name, so the locale names each
  -- one. tools/terrain_names.py collects the names from the presets and checks this list against them.
  terrain_tab = {
    properties = {"aux", "moisture", "temperature"},
    names = {
      "tn_aux_ab_v6", "tn_aux_fb_v1", "tn_blue_aux_v1", "tn_koppen_a_snap_v1",
      "tn_forest_moisture_v1", "tn_moisture_ab_v11", "tn_moisture_fb_v1", "tn_blue_moisture_v1",
      "tn_koppen_m_snap_v1",
      "tn_temperature_ab_v8", "tn_temperature_fb_v1", "tn_blue_temperature_v1", "tn_koppen_t_snap_v1",
    },
  },

  -- The per-save keys: map, scale and geography release are numbers every Earth preset bakes;
  -- land_coarse names the map's coarse land field (design rule 8); elevation, start_mask and distance
  -- are the vanilla properties the presets redirect (distance from spawn-cities: vanilla's starting
  -- ore and enemy-free start follow the spawn through it); spawn_lake and spawn_bias name the
  -- map's spawn lake and starting-ore bias for the shared start mask v2 (spawn-cities).
  keys = {
    map = K_MAP, scale = K_SCALE, geo = K_GEO, land_coarse = K_LAND_COARSE,
    elevation = "elevation", start_mask = "starting_resources_lake_mask", distance = "distance",
    spawn_lake = K_SPAWN_LAKE, spawn_bias = K_SPAWN_BIAS,
    -- waterways: the hook gate (prototype off, Earth presets on), the ford key (prototype off, Earth
    -- presets name the map's ford set for the save's scale) and the canals switch (a toggle)
    on = K_ON, fords = K_FORDS, canals = K_CANALS,
    -- ridges: the toggle, the map's crest and openings keys, and the two cliff properties the presets
    -- redirect
    ridges = RDN.K_RIDGES, crest = RDN.K_CREST, openings = RDN.K_OPENINGS, band = RDN.K_BAND,
    high = RDN.K_HIGH, passes = RDN.K_PASSES, rock_lift = RDN.K_ROCK_LIFT, ground = RDN.K_GROUND,
    high_tile = RDN.K_HIGH_TILE,
    cliff_elevation = "cliff_elevation", cliffiness = "cliffiness",
    -- resources-enemies: the hotspots toggle, each map's offshore stamp key and the enemy property
    hotspots = REN.K_HOTSPOTS, enemy = "enemy_base_probability", hotspot_amount = REN.K_HS_AMOUNT,
    scarcity = REN.K_SCARCITY, north_snow = CT.K_NORTH_SNOW,
    fields = {europe = REN.EU_FIELDS_KEY, atlantic = REN.AT_FIELDS_KEY, olde_world = REN.OW_FIELDS_KEY},
    -- edge-and-lakes: the inland lakes switch (a toggle)
    inland_lakes = ELN.K_INLAND_LAKES,
    -- destroyed-europe: the zone toggle
    destroyed = DE.K,
    -- Blue corrupted UK and Australia: the zone toggle
    blue = BC.K,
    -- 0.3.1: the Moscow zone's level, and whether Destroyed Europe's and Blue corrupted's own outlines are on
    moscow = DE.mz_key, destroyed_europe = DE.eu_key, blue_uk = BC.uk_key,
    -- coast-band-fix: the band-fix key (no prototype; control only)
    bandfix = BFN.K,
    -- Koppen biomes (0.4.0): the toggle key a new world bakes (the preset points the axes at the Koppen
    -- bodies when it is on)
    koppen = K_KOPPEN,
  },

  -- Each map's geography (ARCHITECTURE.md, "Map type entries"): map_type_order, the order of the
  -- map's Map type entry, and `versions`, the map's elevation entries, the newest last. A version is
  -- what one geography release points a preset at: its entry, the bodies only that entry reads (coast
  -- fit, detail, far-field box), its coarse land field, its coordinate chain with city offset names of
  -- its own and the offset its preset bakes there, the start mask its preset names (a start_mask
  -- version), the generated files its fit bodies bind (name-free data, so a later version binds the
  -- same files to its own chain), the Map type fallbacks its entry reads, and its geography release id.
  -- The map's preset names the newest version, whose entry carries the Map type fields
  -- (intended_property, localised_name and map_type_order). presets.lua picks a preset's version here,
  -- in one place at the data stage.
  --
  -- One version per map: nothing had shipped and no saves existed, so every superseded version was
  -- retired (issue #1). After the first release
  -- a map's versions only grow again: a later version takes names of its own and an older one stays
  -- defined, unchanged, for the worlds that name it (design rule 21). 0.3.0 collapsed them again to one per map
  -- (no world existed on any earlier version): tests/collapsed.json names every version,
  -- row, record and file that left, and each dropped version's chain stays as its map's frame (frames below).
  --
  -- geo_id is the version's geography release, the number its preset bakes as tn_geo. tn_geo is
  -- one id space across every map: each geography release of any map takes the next unused
  -- integer and keeps it for good, so no two maps or versions share one, and release_registry
  -- names each with its map, which is how control code resolves a save's tn_geo (ARCHITECTURE.md,
  -- "Release versioning policy", rule 4; tnconfig's id-space check). The next unused id is 26.
  geography = {
    europe = {
      map_type_order = "3000-tn-a",
      versions = {
        {
          -- Version 7 (Europe, 0.3.0): version 6 and its scale extension in one version at every offered
          -- scale, every body that reads the chain under a name of its own, the fit, frame and generated files kept.
          -- The bearings file holds version 6's list, so a scale past it reads its scale 6 row, as the extension did.
          geo_id = 23,
          entry = ELN.EU7_ENTRY,
          geo = ELN.EU7_GEO, land_coarse = ELN.EU7_LAND_COARSE, detail = ELN.EU7_DETAIL, far = ELN.EU7_FAR,
          gx = ELN.EU7_GX, gy = ELN.EU7_GY, u = ELN.EU7_U, v = ELN.EU7_V,
          cx = ELN.EU7_CX, cy = ELN.EU7_CY, city_offset = {EU_CITY_CX, EU_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = EU_GEO_FILE, land_coarse = EU_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = ELN.EU7_CX, map_qualified = true, frozen = true},
            {name = ELN.EU7_CY, map_qualified = true, frozen = true},
            {name = EU_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.EU_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_europe", city = EU_CITY, city_index = EU_CITY_INDEX,
            spawn_lake = ELN.EU7_SPAWN_LAKE, spawn_bias = ELN.EU7_SPAWN_BIAS, inland_lakes = ELN.EU7_LAKES,
            lake_floor = true, start_land = START_LAND, distance = DISTANCE, bearings = EU_SPAWN_FILE,
          },
          waterways = OAS_SETS.europe_v7,
          scales = SCALE_LISTS.offered,
          warp = ELN.EU7_WARP,
          shore = ELN.EU7_SHORE,
          fields = REN.EU_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
      },
    },
    atlantic = {
      map_type_order = "3000-tn-b",
      versions = {
        {
          -- Version 8 (Atlantic, 0.3.0): the composition of version 7, every body that reads the chain under a
          -- name of its own, the fit, frame and generated files kept.
          geo_id = 22,
          entry = OAS.AT8_ENTRY,
          geo = OAS.AT8_GEO, land_coarse = OAS.AT8_LAND_COARSE, detail = OAS.AT8_DETAIL, far = OAS.AT8_FAR,
          gx = OAS.AT8_GX, gy = OAS.AT8_GY, u = OAS.AT8_U, v = OAS.AT8_V,
          cx = OAS.AT8_CX, cy = OAS.AT8_CY, city_offset = {OAS.AT_CITY_CX, OAS.AT_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = OAS.AT7_GEO_FILE, land_coarse = AT_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.AT8_CX, map_qualified = true, frozen = true},
            {name = OAS.AT8_CY, map_qualified = true, frozen = true},
            {name = OAS.AT_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.AT_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_atlantic", city = OAS.AT_CITY, city_index = OAS.AT_CITY_INDEX,
            spawn_lake = OAS.AT8_SPAWN_LAKE, spawn_bias = OAS.AT8_SPAWN_BIAS, inland_lakes = OAS.AT8_LAKES,
            lake_floor = true, start_land = START_LAND, distance = DISTANCE, bearings = OAS.AT7_SPAWN_FILE,
          },
          waterways = OAS_SETS.atlantic_v8,
          scales = SCALE_LISTS.offered,
          waterway_files = 2,
          mouths = OAS.AT_MOUTH2,
          warp = OAS.AT_WARP2,
          shore = OAS.AT8_SHORE,
          fields = REN.AT_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
        {
          -- Version 9 (Atlantic, 0.3.2), a Map type version (map_type_of): the composition of version 8 (geo_id
          -- 22) by name, its chain, box, spawn bodies and sets, with an entry, shore and inland lakes of its own that
          -- read `geo` past above_scale and version 8's geo up to it. `geo` is the frayed coast fit (coast_fray): the
          -- generated fit fits.geo names, bound to version 8's warped chain plus the fray. A Map-type-only world names
          -- this entry; the Atlantic preset keeps version 8 (tn_geo 22) and names this entry for elevation at
          -- every scale (0.4.0 one-click; below above_scale it folds to version 8's composition), so both routes read
          -- one entry. fits.geo is the one field that names the coast fit past
          -- scale 6: the generated file of the preset's next geo body (coast.next). Waterways reuse version 8's sets
          -- (atlantic_v8): the river and ford sets are drawn against the unchanged geo body (model-10400), so the new
          -- next + overlay coast needs no re-emission.
          geo_id = 25,
          map_type_of = {geo_id = 22, above_scale = 6},
          entry = OAS.AT9_ENTRY,
          geo = OAS.AT_GEO_FRAY1, land_coarse = OAS.AT8_LAND_COARSE, detail = OAS.AT8_DETAIL, far = OAS.AT8_FAR,
          fray_overlay = {fit = OAS.AT_FIT_FRAY1, land = OAS.AT_LAND_FRAY1, water = OAS.AT_WATER_FRAY1},
          gx = OAS.AT8_GX, gy = OAS.AT8_GY, u = OAS.AT8_U, v = OAS.AT8_V,
          cx = OAS.AT8_CX, cy = OAS.AT8_CY, city_offset = {OAS.AT_CITY_CX, OAS.AT_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = OAS.AT9_GEO_FILE, land_coarse = AT_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.AT8_CX, map_qualified = true, frozen = true},
            {name = OAS.AT8_CY, map_qualified = true, frozen = true},
            {name = OAS.AT_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.AT_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_atlantic", city = OAS.AT_CITY, city_index = OAS.AT_CITY_INDEX,
            spawn_lake = OAS.AT8_SPAWN_LAKE, spawn_bias = OAS.AT8_SPAWN_BIAS, inland_lakes = OAS.AT9_LAKES,
            lake_floor = true, start_land = START_LAND, distance = DISTANCE, bearings = OAS.AT7_SPAWN_FILE,
          },
          waterways = OAS_SETS.atlantic_v8,
          scales = SCALE_LISTS.offered,
          waterway_files = 2,
          mouths = OAS.AT_MOUTH2,
          warp = OAS.AT_WARP2,
          shore = OAS.AT9_SHORE,
          fields = REN.AT_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
      },
    },
    olde_world = {
      map_type_order = "3000-tn-c",
      versions = {
        {
          -- Version 8 (Old World, 0.3.0): the composition of version 7, every body that reads the chain under a
          -- name of its own, the fit, frame and generated files kept.
          geo_id = 21,
          entry = OAS.OW8_ENTRY,
          geo = OAS.OW8_GEO, land_coarse = OAS.OW8_LAND_COARSE, detail = OAS.OW8_DETAIL, far = OAS.OW8_FAR,
          gx = OAS.OW8_GX, gy = OAS.OW8_GY, u = OAS.OW8_U, v = OAS.OW8_V,
          cx = OAS.OW8_CX, cy = OAS.OW8_CY, city_offset = {OAS.OW_CITY_CX, OAS.OW_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = OAS.OW7_GEO_FILE, land_coarse = OW_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.OW8_CX, map_qualified = true, frozen = true},
            {name = OAS.OW8_CY, map_qualified = true, frozen = true},
            {name = OAS.OW_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.OW_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_olde_world", city = OAS.OW_CITY, city_index = OAS.OW_CITY_INDEX,
            spawn_lake = OAS.OW8_SPAWN_LAKE, spawn_bias = OAS.OW8_SPAWN_BIAS, inland_lakes = OAS.OW8_LAKES,
            lake_floor = true, start_land = START_LAND, distance = DISTANCE, bearings = OAS.OW7_SPAWN_FILE,
          },
          waterways = OAS_SETS.olde_world_v8,
          scales = SCALE_LISTS.offered,
          waterway_files = 2,
          mouths = OAS.OW_MOUTH2,
          warp = OAS.OW_WARP2,
          shore = OAS.OW8_SHORE,
          fields = REN.OW_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
        {
          -- Version 9 (Old World, 0.3.2), a Map type version (map_type_of): the composition of version 8 (geo_id
          -- 21) by name, its chain, box, spawn bodies and sets, with an entry, shore and inland lakes of its own that
          -- read `geo` past above_scale and version 8's geo up to it. `geo` is the frayed coast fit (coast_fray): the
          -- generated fit fits.geo names, bound to version 8's warped chain plus the fray. A Map-type-only world names
          -- this entry; the Old World preset keeps version 8 (tn_geo 21) and names this entry for elevation at
          -- every scale (0.4.0 one-click; below above_scale it folds to version 8's composition), so both routes read
          -- one entry. fits.geo is the one field that names the coast fit past
          -- scale 6: the generated file of the preset's next geo body (coast.next).
          geo_id = 24,
          map_type_of = {geo_id = 21, above_scale = 6},
          entry = OAS.OW9_ENTRY,
          geo = OAS.OW_GEO_FRAY1, land_coarse = OAS.OW8_LAND_COARSE, detail = OAS.OW8_DETAIL, far = OAS.OW8_FAR,
          fray_overlay = {fit = OAS.OW_FIT_FRAY1, land = OAS.OW_LAND_FRAY1, water = OAS.OW_WATER_FRAY1},
          gx = OAS.OW8_GX, gy = OAS.OW8_GY, u = OAS.OW8_U, v = OAS.OW8_V,
          cx = OAS.OW8_CX, cy = OAS.OW8_CY, city_offset = {OAS.OW_CITY_CX, OAS.OW_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = OAS.OW9_GEO_FILE, land_coarse = OW_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.OW8_CX, map_qualified = true, frozen = true},
            {name = OAS.OW8_CY, map_qualified = true, frozen = true},
            {name = OAS.OW_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.OW_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_olde_world", city = OAS.OW_CITY, city_index = OAS.OW_CITY_INDEX,
            spawn_lake = OAS.OW8_SPAWN_LAKE, spawn_bias = OAS.OW8_SPAWN_BIAS, inland_lakes = OAS.OW9_LAKES,
            lake_floor = true, start_land = START_LAND, distance = DISTANCE, bearings = OAS.OW7_SPAWN_FILE,
          },
          waterways = OAS_SETS.olde_world_v9,
          scales = SCALE_LISTS.offered,
          waterway_files = 2,
          mouths = OAS.OW_MOUTH2,
          warp = OAS.OW_WARP2,
          shore = OAS.OW9_SHORE,
          fields = REN.OW_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
      },
    },
  },

  -- The next spawn folds (0.3.1), per geography version: the version's released spawn record serves the first `served`
  -- cities of its setting, and its folds keep their text. A new world whose city number is past them names these
  -- bodies over the released ones (presets.lua spawn_next_values): the city offset (the version's own cx and cy and
  -- its map's frame), the spawn lake (under the key and the name the entry reads) and the starting-ore bias, each built
  -- from the map's newest city table and its own bearings file by the released record's resolved index, whose random
  -- pick stays on the served cities, so a random world keeps its city. A Map-type-only world reads the released folds
  -- (frozen fallbacks), so there a city past them falls back to random.
  spawn_next = {versions = {
    [22] = {served = 50, city_offset = {OAS.AT_CITY_CX2, OAS.AT_CITY_CY2}, spawn_lake = OAS.AT9_SPAWN_LAKE,
            spawn_bias = OAS.AT9_SPAWN_BIAS, bearings = OAS.AT9_SPAWN_FILE},
    -- 0.4.0: the Atlantic Map-type version (geo 25) names the appended spawn_city_atlantic, so the next-folds
    -- waiver requires its own served count; a Map-type world only ever reads `served` (presets.lua fallback
    -- loop resets an appended city to random), never a next-fold body, so no body fields are carried here.
    [25] = {served = 50},
  }},

  -- The chain every map-wide layer reads (the region layer, the climate and the layers after them):
  -- per map, the geography release (tn_geo) whose coordinate chain their bodies read. Since the
  -- superseded versions were retired that is each map's own version, so a preset world and a
  -- Map-type-only world read one chain per map. A later version that keeps the frame keeps this row (the
  -- same city offset under names of its own); a version that moves the frame needs layer bodies of its
  -- own.
  layer_chain_geo = {europe = 14, atlantic = 17, olde_world = 18},

  -- The frames (0.3.0: one geography version per map, since no world existed on an earlier
  -- version): the coordinate chain of each layer_chain_geo release, kept when its version was dropped, because every
  -- map-wide layer body reads it by name. A frame is that chain alone: its geo tiles and reference pixels on the
  -- city offset names cx and cy, which no preset bakes, so they are frozen Map type fallbacks valued as the map's
  -- city fold (city_offset), the offset the 0.3.0 version's own names carry too. coast.lua defines the chain,
  -- presets.lua the two fallbacks.
  frames = {
    europe = {
      geo_id = 14, gx = ELN.EU6_GX, gy = ELN.EU6_GY, u = ELN.EU6_U, v = ELN.EU6_V, cx = ELN.EU6_CX, cy = ELN.EU6_CY,
      city_offset = {EU_CITY_CX, EU_CITY_CY},
      fallbacks = {{name = ELN.EU6_CX, map_qualified = true, frozen = true},
                   {name = ELN.EU6_CY, map_qualified = true, frozen = true}},
    },
    atlantic = {
      geo_id = 17, gx = OAS.AT6_GX, gy = OAS.AT6_GY, u = OAS.AT6_U, v = OAS.AT6_V, cx = OAS.AT6_CX, cy = OAS.AT6_CY,
      city_offset = {OAS.AT_CITY_CX, OAS.AT_CITY_CY},
      fallbacks = {{name = OAS.AT6_CX, map_qualified = true, frozen = true},
                   {name = OAS.AT6_CY, map_qualified = true, frozen = true}},
    },
    olde_world = {
      geo_id = 18, gx = OAS.OW6_GX, gy = OAS.OW6_GY, u = OAS.OW6_U, v = OAS.OW6_V, cx = OAS.OW6_CX, cy = OAS.OW6_CY,
      city_offset = {OAS.OW_CITY_CX, OAS.OW_CITY_CY},
      fallbacks = {{name = OAS.OW6_CX, map_qualified = true, frozen = true},
                   {name = OAS.OW6_CY, map_qualified = true, frozen = true}},
    },
  },

  -- The water slider (inert on Earth presets). Vanilla 2.1.23 reads control:water:* in exactly
  -- three named expressions (core/prototypes/noise-programs.lua): water_level (10 * log2 of the
  -- size), segmentation_multiplier (the frequency) and nauvis_segmentation_multiplier (1.5 times
  -- the frequency). Earth elevation reads none of them, but vanilla cliffs, moisture and aux still
  -- do on an Earth preset, so every Earth preset bakes each as its value at the default slider: the
  -- slider then moves nothing, and at the default slider nothing changes. The gate's water_inert row
  -- walks every root of each preset for any other reader and previews the slider's extremes.
  water_slider = {
    {key = "water_level", value = 0},
    {key = "segmentation_multiplier", value = 1},
    {key = "nauvis_segmentation_multiplier", value = 1.5},
  },

  -- Every property_expression_names key any Earth preset sets, for every geography version (each
  -- version's own city offset names join it; tnconfig checks every key a version's preset bakes is
  -- here): the missing-name guard, the isolation walker (t14_walker) and the Nauvis-only surface guard
  -- read it, which strips exactly these keys from every other surface (ARCHITECTURE.md, "D33 surface
  -- guard"). From climate-tiles also the climate redirects,
  -- the marsh keys, the palm keys, and with Alien Biomes the vanilla tile keys and the exclusion key
  -- (absent keys are by design on a world without AB).
  preset_keys = {"elevation", "starting_resources_lake_mask", K_LAND_COARSE, K_MAP, K_SCALE, K_GEO,
                 -- the barrier's re-points (destroyed.barrier): a preset with the zone on names their next versions
                 DE.heat, DE.chaos_class, DE.clear,
                 -- 0.3.0: the barrier's zone and the outline's presence and depth, which presets point at their next
                 -- versions (destroyed.barrier.next, destroyed.outline.next)
                 DE.zone2, DE.out_present, DE.out_depth,
                 -- 0.3.1: the barrier's reach and open mask, which presets point at the devastation field's
                 -- (destroyed.dev)
                 DE.reach, DE.open,
                 -- 1.0.0: the trees' mask on a range the zone encloses (destroyed.dev.range_trees)
                 DE.range_open,
                 REN.HS_IRON, REN.HS_COPPER, REN.HS_COAL, REN.HS_STONE, REN.HS_URANIUM, REN.HS_OIL, REN.ORE_GAP,
                 REN.ENEMY_LAYER,
                 -- 0.3.0: the trees' hook gate off hotspot ore (resources.ore_trees), and its shares, which presets
                 -- point at their next versions
                 NOISE .. "ore_trees", NOISE .. "ore_open_v1", NOISE .. "ore_open_plants_v1",
                 -- 0.3.0: the forest and marsh aggregates, which presets point at the second region table's
                 RG_FOREST_W, RG_FOREST_SUM, RG_MARSH_W,
                 "water_level", "segmentation_multiplier", "nauvis_segmentation_multiplier",
                 "distance", EU_CITY, K_SPAWN_LAKE, K_SPAWN_BIAS, K_ON, K_FORDS, K_CANALS,
                 "temperature", "moisture", "aux", CT.MARSH_MUD, CT.MARSH_SHALLOW, CT.MARSH_GRASS,
                 -- 0.3.0: the spread's frequency sliders at the biome size (climate.size)
                 "control:moisture:frequency", "control:aux:frequency",
                 CT.VT_GRASS_1, CT.VT_GRASS_2, CT.VT_GRASS_3, CT.VT_GRASS_4, CT.VT_DRY_DIRT, CT.VT_DIRT_1,
                 CT.VT_DIRT_2, CT.VT_DIRT_3,
                 CT.VT_DIRT_4, CT.VT_DIRT_5, CT.VT_DIRT_6, CT.VT_DIRT_7, CT.VT_SAND_1, CT.VT_SAND_2, CT.VT_SAND_3,
                 CT.VT_RED_0, CT.VT_RED_1,
                 CT.VT_RED_2, CT.VT_RED_3, CT.AB_EXCLUDE, CT.TM_1, CT.TM_2, CT.TM_3, CT.TM_4, CT.TM_5, CT.TM_6, CT.TM_7,
                 CT.TM_8, CT.TM_9, CT.TM_10, CT.TM_11, CT.TM_12, CT.FROZEN_KEY, CT.PALM_A_P_KEY,
                 CT.PALM_A_R_KEY, CT.PALM_B_P_KEY, CT.PALM_B_R_KEY,
                 -- trees-forests: the great-forests gate and multiplier key, and with Alien Biomes the restored
                 -- vanilla trees', rocks' and decoratives' keys
                 TFN.K_FORESTS_ON, TFN.K_TREE_MULT, TFN.K_TREE_LIFT,
                 -- 1.0.0: the great forests' ground weight (trees.ground)
                 TFN.K_FOREST_GROUND,
                 TF_TREES["tree-01"].p, TF_TREES["tree-01"].r, TF_TREES["tree-02"].p, TF_TREES["tree-02"].r,
                 TF_TREES["tree-02-red"].p, TF_TREES["tree-02-red"].r, TF_TREES["tree-03"].p, TF_TREES["tree-03"].r,
                 TF_TREES["tree-04"].p, TF_TREES["tree-04"].r, TF_TREES["tree-05"].p, TF_TREES["tree-05"].r,
                 TF_TREES["tree-06"].p, TF_TREES["tree-06"].r, TF_TREES["tree-06-brown"].p,
                 TF_TREES["tree-06-brown"].r, TF_TREES["tree-07"].p, TF_TREES["tree-07"].r, TF_TREES["tree-08"].p,
                 TF_TREES["tree-08"].r, TF_TREES["tree-08-brown"].p, TF_TREES["tree-08-brown"].r,
                 TF_TREES["tree-08-red"].p, TF_TREES["tree-08-red"].r, TF_TREES["tree-09"].p, TF_TREES["tree-09"].r,
                 TF_TREES["tree-09-brown"].p, TF_TREES["tree-09-brown"].r, TF_TREES["tree-09-red"].p,
                 TF_TREES["tree-09-red"].r,
                 TF_ROCKS["huge-rock"].key, TF_ROCKS["big-rock"].key, TF_ROCKS["big-sand-rock"].key,
                 TF_ROCKS["medium-rock"].key, TF_ROCKS["small-rock"].key, TF_ROCKS["tiny-rock"].key,
                 TF_ROCKS["medium-sand-rock"].key, TF_ROCKS["small-sand-rock"].key, TF_ROCKS["red-desert-decal"].key,
                 TF_ROCKS["sand-decal"].key, TF_ROCKS["sand-dune-decal"].key,
                 TF_DECO["light-mud-decal"], TF_DECO["green-asterisk"], TF_DECO["green-asterisk-mini"],
                 TF_DECO["green-bush-mini"], TF_DECO["green-carpet-grass"], TF_DECO["green-croton"],
                 TF_DECO["green-desert-bush"], TF_DECO["green-hairy-grass"], TF_DECO["green-pita"],
                 TF_DECO["green-pita-mini"], TF_DECO["green-small-grass"],
                 -- ridges: the toggle, the map's ridge keys, the two cliff properties and the Earth ores'
                 -- probability keys (data-final-fixes.lua points them at the clearance wrappers)
                 RDN.K_RIDGES, RDN.K_CREST, RDN.K_OPENINGS, RDN.K_BAND, "cliff_elevation", "cliffiness",
                 RDN.K_HIGH, RDN.K_PASSES, RDN.K_ROCK_LIFT, RDN.K_GROUND, RDN.K_HIGH_TILE,
                 "entity:huge-rock:probability", "entity:big-rock:probability", "entity:big-sand-rock:probability",
                 "entity:iron-ore:probability", "entity:copper-ore:probability", "entity:coal:probability",
                 "entity:stone:probability", "entity:uranium-ore:probability", "entity:crude-oil:probability",
                 -- resources-enemies: the richness keys, the enemy property, the hotspots toggle, each map's
                 -- offshore stamp key and, with the Oil Rig loaded, the offshore-oil keys
                 "entity:iron-ore:richness", "entity:copper-ore:richness", "entity:coal:richness",
                 "entity:stone:richness", "entity:uranium-ore:richness", "entity:crude-oil:richness",
                 "enemy_base_probability", REN.K_HOTSPOTS, REN.EU_FIELDS_KEY, REN.AT_FIELDS_KEY, REN.OW_FIELDS_KEY,
                 "entity:offshore-oil:probability", "entity:offshore-oil:richness",
                 -- the ore patch redirects and the hotspot amount
                 "default-iron-ore-patches", "default-copper-ore-patches", "default-coal-patches",
                 "default-stone-patches", "default-uranium-ore-patches", "default-crude-oil-patches",
                 "default-offshore-oil-patches", REN.K_HS_AMOUNT,
                 -- 0.3.0: the regional scarcity level
                 REN.K_SCARCITY,
                 -- 0.3.1: the north snow level
                 CT.K_NORTH_SNOW,
                 -- edge-and-lakes: the inland lakes switch and the new versions' city offset names
                 ELN.K_INLAND_LAKES, ELN.EU6_CX, ELN.EU6_CY,
                 -- the Old World and Atlantic spawn city: the maps' city numbers and the new versions' offset names
                 OAS.AT_CITY, OAS.OW_CITY, OAS.AT6_CX, OAS.AT6_CY, OAS.OW6_CX, OAS.OW6_CY,
                 OAS.OW8_CX, OAS.OW8_CY, OAS.AT8_CX, OAS.AT8_CY, ELN.EU7_CX, ELN.EU7_CY,
                 -- destroyed-europe: the zone toggle (temperature and the city numbers are listed above)
                 DE.K,
                 -- Blue corrupted UK and Australia: the zone toggle, and with it on the names each redirect wraps
                 BC.K, BC.temperature_under, BC.moisture_under, BC.aux_under, BC.palm_a_under, BC.palm_b_under,
                 CT.AB_KEEP_BODY,
                 -- 0.3.1: Blue corrupted UK's outline depth, which a new world with the zone on names the next one
                 BC.out_depth,
                 -- 0.3.1: the Moscow zone's level, the Europe and UK keys, and with Corrupted the Blue class and the
                 -- north rim's keep, which presets name over their first names
                 DE.mz_key, DE.eu_key, BC.uk_key, BC.class, CT.CL_N_RIM_KEEP,
                 -- coast-band-fix: the band-fix key, on presets whose map the setting acts on
                 BFN.K,
                 -- 0.3.1: the spawn lake name Atlantic's entry reads, which a preset past the released folds' cities
                 -- points at the next one (spawn_next)
                 OAS.AT8_SPAWN_LAKE,
                 -- 0.3.1: Old World's geo body, which a preset past scale 6 points at the next one (coast.next)
                 OAS.OW8_GEO,
                 -- 0.4.0: the Koppen toggle; the preset points the axes at the Koppen bodies when it is on
                 K_KOPPEN,
                 -- 0.4.0: the per-tile Koppen climate keys and the no-blue/zone-plants keys the preset
                 -- bakes when Koppen and Alien Biomes are on, so the Nauvis-only guard (scripts/guards.lua) strips them
                 CT.K_TILE_T, CT.K_TILE_M, CT.K_TILE_A, CT.K_TILE_TV, TFN.NB_KEY, TFN.ZP_KEY,
                 -- 0.4.0: keys an ab / zone-on preset bakes but preset_keys lacked, so the Nauvis-only
                 -- guard left them on other surfaces (ARCHITECTURE.md, "D33 surface guard").
                 -- atlantic/olde_world ab grain mix (VT_MIX); europe zone-on devastation field position,
                 -- width, dead-forest, north drop
                 CT.VT_MIX, CT.CL_N_DROP3, DE.dev, DE.dev_width, DE.dead,
                 -- 1.0.0: the names the Middle East desert's bodies read what they wrap through (climate.desert)
                 CT.DS_TILE_T_UNDER, CT.DS_TILE_A_UNDER,
                 -- 1.0.0: the names the Patagonian steppe's bodies read what they wrap through (climate.steppe)
                 CT.SP_TILE_M_UNDER, CT.SP_TILE_A_UNDER, CT.SP_TILE_TV_UNDER, CT.SP_TREES_UNDER},

  -- The fine field per map (ARCHITECTURE.md, "Programs and the firewall"): map key -> {the map's
  -- elevation entry and every term
  -- only it reads}. The constant-coast twin turns each into a constant; no Entity,
  -- decorative or Cliff root on a Terra Nauvis preset may reach one. The start land guarantee is
  -- analytic but belongs to the field by ARCHITECTURE.md's firewall rule; the spawn lake, the bias,
  -- distance and the city fold are firewall-clean (the start mask reads the lake and the bias).
  firewall = {
    -- each map's entry and the terms only it reads; the ford sets reach Tile only, through the
    -- water-shallow hook
    europe = {
      REN.EU_FIELDS, START_LAND, ELN.EU7_ENTRY, ELN.EU7_GEO, ELN.EU7_DETAIL, ELN.EU7_FAR, ELN.EU7_LAKES,
      ELN.EU7_SHORE, ELN.EU_WW5[1], ELN.EU_WW5[2], ELN.EU_WW5[3], ELN.EU_WW5[4], ELN.EU_WW5[5], ELN.EU_WW5[6],
      ELN.EU_WW5[7], ELN.EU_WW5[8], ELN.EU_CANALS5[1], ELN.EU_CANALS5[2], ELN.EU_CANALS5[3], ELN.EU_CANALS5[4],
      ELN.EU_CANALS5[5], ELN.EU_CANALS5[6], ELN.EU_CANALS5[7], ELN.EU_CANALS5[8], ELN.EU_DAMS5[1], ELN.EU_DAMS5[2],
      ELN.EU_DAMS5[3], ELN.EU_DAMS5[4], ELN.EU_DAMS5[5], ELN.EU_DAMS5[6], ELN.EU_DAMS5[7], ELN.EU_DAMS5[8],
      ELN.EU_FORDS5[1], ELN.EU_FORDS5[2], ELN.EU_FORDS5[3], ELN.EU_FORDS5[4], ELN.EU_FORDS5[5], ELN.EU_FORDS5[6],
      ELN.EU_FORDS5[7], ELN.EU_FORDS5[8], ELN.EU7_WARP[1], ELN.EU7_WARP[2], ELN.EU7_WARP[3], ELN.EU7_WARP[4],
      ELN.EU7_WARP[5], ELN.EU7_WARP[6], ELN.EU7_WARP[7], ELN.EU7_WARP[8], ELN.EU7_WARP[9], ELN.EU7_WARP[10],
      ELN.EU7_WARP[11], ELN.EU7_WARP[12], ELN.EU7_WARP[13], ELN.EU7_WARP[14], ELN.EU7_WARP[15], ELN.EU7_WARP[16],
      ELN.EU7_WARP[17], ELN.EU7_WARP[18], ELN.EU7_WARP[19], ELN.EU7_WARP[20], ELN.EU7_WARP[21], ELN.EU7_WARP[22],
      ELN.EU7_WARP[23], ELN.EU7_WARP[24], ELN.EU7_WARP[25], ELN.EU7_WARP[26], ELN.EU7_WARP[27], ELN.EU7_WARP[28],
      ELN.EU7_WARP[29], ELN.EU7_WARP[30], ELN.EU7_WARP[31], ELN.EU7_WARP[32],
    },
    atlantic = {
      REN.AT_FIELDS, START_LAND, OAS.AT8_ENTRY, OAS.AT8_GEO, OAS.AT9_GEO, OAS.AT8_DETAIL, OAS.AT8_FAR,
      OAS.AT10_GEO, OAS.AT10_LAND, OAS.AT10_WATER,
      OAS.AT8_LAKES,
      -- 0.4.0: the Map type version 9's own bodies (geography 25); waterways reuse version 8's sets
      OAS.AT9_ENTRY, OAS.AT9_SHORE, OAS.AT9_LAKES, OAS.AT_GEO_FRAY1, OAS.AT_FIT_FRAY1, OAS.AT_LAND_FRAY1,
      OAS.AT_WATER_FRAY1,
      OAS.AT8_SHORE, OAS.AT_WW7[1], OAS.AT_WW7[2], OAS.AT_WW7[3], OAS.AT_WW7[4], OAS.AT_WW7[5], OAS.AT_WW7[6],
      OAS.AT_WW7[7], OAS.AT_WW7[8], OAS.AT_CANALS7[1], OAS.AT_CANALS7[2], OAS.AT_CANALS7[3], OAS.AT_CANALS7[4],
      OAS.AT_CANALS7[5], OAS.AT_CANALS7[6], OAS.AT_CANALS7[7], OAS.AT_CANALS7[8], OAS.AT_DAMS7[1], OAS.AT_DAMS7[2],
      OAS.AT_DAMS7[3], OAS.AT_DAMS7[4], OAS.AT_DAMS7[5], OAS.AT_DAMS7[6], OAS.AT_DAMS7[7], OAS.AT_DAMS7[8],
      OAS.AT_FORDS7[1], OAS.AT_FORDS7[2], OAS.AT_FORDS7[3], OAS.AT_FORDS7[4], OAS.AT_FORDS7[5], OAS.AT_FORDS7[6],
      OAS.AT_FORDS7[7], OAS.AT_FORDS7[8], OAS.AT_MOUTH2[1], OAS.AT_MOUTH2[2], OAS.AT_MOUTH2[3], OAS.AT_MOUTH2[4],
      OAS.AT_MOUTH2[5], OAS.AT_MOUTH2[6], OAS.AT_MOUTH2[7], OAS.AT_MOUTH2[8], OAS.AT_WARP2[1], OAS.AT_WARP2[2],
      OAS.AT_WARP2[3], OAS.AT_WARP2[4], OAS.AT_WARP2[5], OAS.AT_WARP2[6], OAS.AT_WARP2[7], OAS.AT_WARP2[8],
      OAS.AT_WARP2[9], OAS.AT_WARP2[10], OAS.AT_WARP2[11], OAS.AT_WARP2[12], OAS.AT_WARP2[13], OAS.AT_WARP2[14],
      OAS.AT_WARP2[15], OAS.AT_WARP2[16], OAS.AT_WARP2[17], OAS.AT_WARP2[18], OAS.AT_WARP2[19], OAS.AT_WARP2[20],
      OAS.AT_WARP2[21], OAS.AT_WARP2[22], OAS.AT_WARP2[23], OAS.AT_WARP2[24], OAS.AT_WARP2[25], OAS.AT_WARP2[26],
      OAS.AT_WARP2[27], OAS.AT_WARP2[28], OAS.AT_WARP2[29], OAS.AT_WARP2[30], OAS.AT_WARP2[31], OAS.AT_WARP2[32],
    },
    olde_world = {
      REN.OW_FIELDS, START_LAND, OAS.OW8_ENTRY, OAS.OW8_GEO, OAS.OW9_GEO, OAS.OW8_DETAIL, OAS.OW8_FAR,
      OAS.OW10_GEO, OAS.OW10_LAND, OAS.OW10_WATER,
      OAS.OW8_LAKES,
      -- 0.3.2: the Map type version 9's own bodies (geography 24)
      OAS.OW9_ENTRY, OAS.OW9_SHORE, OAS.OW9_LAKES, OAS.OW_GEO_FRAY1, OAS.OW_WW8[1], OAS.OW_WW8[2], OAS.OW_FORDS8[1],
      OAS.OW_FORDS8[2], OAS.OW_WARP3[1], OAS.OW_WARP3[2], OAS.OW_FIT_FRAY1, OAS.OW_LAND_FRAY1, OAS.OW_WATER_FRAY1,
      OAS.OW8_SHORE, OAS.OW_WW7[1], OAS.OW_WW7[2], OAS.OW_WW7[3], OAS.OW_WW7[4], OAS.OW_WW7[5], OAS.OW_WW7[6],
      OAS.OW_WW7[7], OAS.OW_WW7[8], OAS.OW_CANALS7[1], OAS.OW_CANALS7[2], OAS.OW_CANALS7[3], OAS.OW_CANALS7[4],
      OAS.OW_CANALS7[5], OAS.OW_CANALS7[6], OAS.OW_CANALS7[7], OAS.OW_CANALS7[8], OAS.OW_DAMS7[1], OAS.OW_DAMS7[2],
      OAS.OW_DAMS7[3], OAS.OW_DAMS7[4], OAS.OW_DAMS7[5], OAS.OW_DAMS7[6], OAS.OW_DAMS7[7], OAS.OW_DAMS7[8],
      OAS.OW_FORDS7[1], OAS.OW_FORDS7[2], OAS.OW_FORDS7[3], OAS.OW_FORDS7[4], OAS.OW_FORDS7[5], OAS.OW_FORDS7[6],
      OAS.OW_FORDS7[7], OAS.OW_FORDS7[8], OAS.OW_MOUTH2[1], OAS.OW_MOUTH2[2], OAS.OW_MOUTH2[3], OAS.OW_MOUTH2[4],
      OAS.OW_MOUTH2[5], OAS.OW_MOUTH2[6], OAS.OW_MOUTH2[7], OAS.OW_MOUTH2[8], OAS.OW_WARP2[1], OAS.OW_WARP2[2],
      OAS.OW_WARP2[3], OAS.OW_WARP2[4], OAS.OW_WARP2[5], OAS.OW_WARP2[6], OAS.OW_WARP2[7], OAS.OW_WARP2[8],
      OAS.OW_WARP2[9], OAS.OW_WARP2[10], OAS.OW_WARP2[11], OAS.OW_WARP2[12], OAS.OW_WARP2[13], OAS.OW_WARP2[14],
      OAS.OW_WARP2[15], OAS.OW_WARP2[16], OAS.OW_WARP2[17], OAS.OW_WARP2[18], OAS.OW_WARP2[19], OAS.OW_WARP2[20],
      OAS.OW_WARP2[21], OAS.OW_WARP2[22], OAS.OW_WARP2[23], OAS.OW_WARP2[24], OAS.OW_WARP2[25], OAS.OW_WARP2[26],
      OAS.OW_WARP2[27], OAS.OW_WARP2[28], OAS.OW_WARP2[29], OAS.OW_WARP2[30], OAS.OW_WARP2[31], OAS.OW_WARP2[32],
    },
  },

  -- Per geography release: {release = <version>, map = <map key>, geography = <tn_geo id>, names =
  -- {<noise names>}, files = {<generated files>}}. Every name here is registered in
  -- tests/frozen.json by the change that adds it and never changes in place (design rule 21). Each row
  -- names one geography id with the map it belongs to; an id appears in one row only and never
  -- moves to another map, and each geography version's geo_id has its row under its map
  -- (tnconfig's id-space check).
  release_registry = {
    -- The region layer: its fixed names, and under files the region table, which
    -- releases every name regions.lua composes from it (a stem of regions.names.row, a row id and the
    -- suffix; a warped query point per share). It belongs to no geography. tools/tnconfig.py composes
    -- those names by the same rule, so the dump facts, the static rows and build_zip.py --release see each.
    {
      release = "0.1.0",
      names = {RG_DESTROYED_SD, RG_DESTROYED_W, RG_DESTROYED_DEPTH, RG_FOREST_W, RG_FOREST_SUM, RG_TREE_MULT,
               RG_MARSH_W, RG_HOTSPOT_W, RG_ENEMY_MULT, RG_U .. RG_V, RG_V_ .. RG_V, RG_OX, RG_OY, RG_AX, RG_AY, RG_WK,
               RG_WX, RG_WY, RG_ROUGH, RG_MARSH_ROUGH},
      files = {"prototypes/tables/regions.lua"},
    },
    -- The climate and tile bodies (climate-tiles). They belong to no geography: every map's preset names
    -- them. The hook keys hold their off values. The Alien Biomes variants read AB's hot and cold
    -- controls, so they exist only with Alien Biomes and are registered from the M2 dump.
    {
      release = "0.1.0",
      names = {CT.CL_LAT, CT.CL_LON, CT.CL_MEANDER, CT.CL_DRY, CT.CL_CORE, CT.CL_SHIFT, CT.CL_T_AB, CT.CL_M_AB,
               CT.CL_A_AB, CT.CL_GRAIN, CT.CL_T_AB_G, CT.CL_M_AB_G, CT.CL_A_AB_G, CT.CL_T_FB,
      CT.CL_M_FB, CT.CL_A_FB,
               CT.TM_1, CT.TM_2, CT.TM_3, CT.TM_4, CT.TM_5, CT.TM_6, CT.TM_7, CT.TM_8, CT.TM_9, CT.TM_10, CT.TM_11,
               CT.TM_12,
               CT.VT_GRASS_1, CT.VT_GRASS_2, CT.VT_GRASS_3, CT.VT_GRASS_4, CT.VT_DRY_DIRT, CT.VT_DIRT_1, CT.VT_DIRT_2,
               CT.VT_DIRT_3,
               CT.VT_DIRT_4, CT.VT_DIRT_5, CT.VT_DIRT_6, CT.VT_DIRT_7, CT.VT_SAND_1, CT.VT_SAND_2, CT.VT_SAND_3,
               CT.VT_RED_0, CT.VT_RED_1,
               CT.VT_RED_2, CT.VT_RED_3, CT.VT_BONUS, CT.VT_BONUS_G, CT.VT_BONUS_H, CT.AB_EXCLUDE, CT.AB_EXCLUDE_BODY,
               CT.AB_EXCLUDE_BODY_G, CT.K_TILE_T, CT.K_TILE_M, CT.K_TILE_A, CT.K_TILE_TV, CT.CL_T_AB_GV, CT.CL_BELT_T,
               CT.CL_BELT_TV, CT.CL_BELT_M, CT.CL_BELT_A, CT.CL_BELT_WILD, CT.MARSH_MUD,
               CT.MARSH_POOL, CT.MARSH_MUD_BODY, CT.MARSH_SHALLOW,
               CT.MARSH_SHALLOW_BODY, CT.MARSH_GRASS, CT.MARSH_GRASS_BODY},
    },
    -- The climate re-points after the first release. They belong to no geography either; each exists only
    -- with Alien Biomes and is registered from the M2 dump.
    {
      release = "0.2.0",
      names = {CT.CL_LIFT_M, CT.CL_LIFT_BARE, CT.CL_LIFT_J, CT.CL_M_AB_L, CT.CL_M_AB_GL, CT.VT_BONUS_F, CT.VT_BONUS_FH,
               CT.TM_FRAY, CT.TM2_1, CT.TM2_2, CT.TM2_3,
               CT.TM2_4, CT.TM2_5, CT.TM2_6, CT.TM2_7, CT.TM2_8, CT.TM2_9, CT.TM2_10, CT.TM2_11, CT.TM2_12},
    },
    -- The cold north, the highland's cold field and the palm mask. They belong to no geography; each exists only with
    -- Alien Biomes and is registered from the M2 dump, but for the mask and the palms' third versions, defined on every
    -- load as the palm copies are.
    {
      release = "0.2.0",
      names = {CT.CL_N_D, CT.CL_N_DROP, CT.CL_N_LEAD, CT.CL_N_BELT, CT.CL_T_AB_N, CT.CL_T_AB_G2, CT.CL_T_AB_GV2,
               CT.CL_GRAIN2, CT.CL_M_AB_G2, CT.CL_M_AB_N, CT.CL_A_AB_G2, TFN.PALM_A_P3, TFN.PALM_B_P3, TFN.PALM_ALLOW,
               CT.FROZEN_KEY, CT.FROZEN_BODY, RDN.RD_COLD_F, RDN.RD_COLD_FRAY, RDN.RD_COLD_GATED, RDN.RD_COLD_REACH,
               RDN.RD_COLD_HIGH,
               RDN.RD_COLD_CAP, RDN.EU_COLD,
               RDN.AT_COLD, RDN.OW_COLD},
    },
    -- The cold north's second line and its spawn clearing, the palm mask's shore version and the zone's palms around
    -- it, and the tan rocks' cold versions. No geography; the climate bodies exist only with Alien Biomes, but for the
    -- line, the clearing and the frozen tile's body, which worlds without it read.
    {
      release = "0.3.0",
      names = {CT.CL_N_D2, CT.CL_N_DROP2, CT.CL_N_LEAD2, CT.CL_N_BELT2, CT.CL_N_CLEAR, CT.CL_N_CLEAR_W, CT.CL_T_AB_N2,
               CT.CL_T_AB_G3,
               CT.CL_T_AB_GV3, CT.CL_GRAIN3, CT.CL_M_AB_G3, CT.CL_M_AB_N2, CT.CL_A_AB_G3, CT.FROZEN_BODY2, CT.CL_RAGGED,
               CT.CL_BELT_M2, CT.CL_BELT_EDGE2, CT.CL_LIFT_M2, RDN.RD_COLD_F2, RDN.RD_COLD_GATED2, RDN.RD_COLD_HIGH2,
               RDN.RD_COLD_CAP2,
               RDN.EU_COLD2, RDN.AT_COLD2, RDN.OW_COLD2, CT.TM_FRAY2, CT.TM3_1, CT.TM3_2, CT.TM3_3, CT.TM3_4, CT.TM3_5,
               CT.TM3_6, CT.TM3_7, CT.TM3_8, CT.TM3_9, CT.TM3_10, CT.TM3_11, CT.TM3_12,
               TFN.PALM_A_P4, TFN.PALM_B_P4, TFN.PALM_ALLOW2, TFN.PALM_MED, TFN.PALM_SHORE, DE.palm_a2, DE.palm_b2,
               TFN.PALM_B_P5, DE.dead2, TFN.ZP_KEY, TFN.NB_KEY, TFN.NB_OPEN, TFN.NB_TILE, TFN.NB_OUT,
               TF_ROCKS["big-sand-rock"].cold, TF_ROCKS["big-sand-rock"].cold_high, TF_ROCKS["medium-sand-rock"].cold,
               TF_ROCKS["small-sand-rock"].cold, TF_ROCKS["red-desert-decal"].cold, TF_ROCKS["sand-decal"].cold,
               TF_ROCKS["sand-dune-decal"].cold},
      files = {"prototypes/tables/palm_coast.lua"},
    },
    -- The cold north of 0.3.1 (climate.north3, climate.north_snow): the line shifted by the North snow level, the snow
    -- weight and the rim's keep. No geography; defined on every load, as the second line is.
    {
      release = "0.3.1",
      names = {CT.CL_N_D3, CT.CL_N_SNOW_W, CT.CL_N_RIM_KEEP, CT.CL_N_DROP3, CT.CL_N_LEAD3, CT.CL_N_BELT3, CT.CL_T_AB_N3,
               CT.CL_T_AB_G4, CT.CL_T_AB_GV4, CT.CL_GRAIN4, CT.CL_M_AB_G4, CT.CL_M_AB_N3, CT.CL_A_AB_G4,
               CT.FROZEN_BODY3, CT.CL_M_AB_V, CT.CL_A_AB_V},
    },
    -- The second region table (0.3.0): under files its table, which releases the row names
    -- regions.lua composes from it, and the forest and marsh aggregates over both tables, which a preset names over the
    -- first table's (regions_v2.points). No geography.
    {
      release = "0.3.0",
      names = {RG_FOREST_W2, RG_FOREST_SUM2, RG_MARSH_W2},
      files = {"prototypes/tables/regions_v2.lua"},
    },
    -- The marsh pools' frayed edge (0.3.0). No geography; a preset names the second water-mud body over the first.
    {
      release = "0.3.0",
      names = {CT.MARSH_FRAY, CT.MARSH_MUD_BODY2},
    },
    -- The river deltas (1.0.0; regions_v3): under files the third region table, which releases the row names
    -- regions.lua composes from its marsh rows; the marsh aggregate over three tables, the delta weight, the channel
    -- field with its warped point and bank, and the water-mud and water-shallow bodies that read them. No geography:
    -- a preset of the maps regions_v3.maps lists names them over the second table's (regions_v3.points).
    {
      release = "1.0.0",
      names = {RG_MARSH_W3, RG_DELTA_W, RG_DELTA_U, RG_DELTA_V, RG_DELTA_BANK, RG_DELTA_CH, CT.MARSH_MUD_BODY3,
               CT.MARSH_SHALLOW_BODY2},
      files = {"prototypes/tables/regions_v3.lua"},
    },
    -- The Chaos zone's next outline, zone and class (0.3.0; destroyed.outline.next, destroyed.barrier.next). They exist
    -- with Alien Biomes only, as the barrier's bodies do; a preset with the zone on names them over the released ones.
    {
      release = "0.3.0",
      names = {DE.out_land2, DE.out_sea2, DE.out_inside2, DE.out_sd2, DE.out_present2, DE.out_depth2, DE.out_nordic,
               DE.out_iberia, DE.zone3, DE.heat3, DE.class3, DE.gap},
      files = {"prototypes/tables/zone_outline_v2.lua"},
    },
    -- The Chaos zone's devastation field (0.3.1; destroyed.dev). The presence and depth are defined on every load, as
    -- the outline's are; the rest exist with Alien Biomes only. A preset with the zone on names them over the
    -- barrier's.
    {
      release = "0.3.1",
      names = {DE.dev, DE.dev_ragged, DE.dev_width, DE.heat4, DE.class4, DE.reach2, DE.open2, DE.out_present3,
               DE.out_depth3, DE.chaos_dry, DE.dev_wobble_a, DE.dev_wobble_b,
               DE.dev_fray},
    },
    -- The next devastation field (0.3.2; destroyed.dev.next): Alien Biomes only, named over dev, width and class by a
    -- preset with the zone on, which also names the cold north's zone drop (climate.north3) over its drop.
    {
      release = "0.3.2",
      names = {DE.dev2, DE.dev_width2, DE.dev_jog_x, DE.dev_jog_y, DE.dev_fray2, DE.mz_dev2, DE.class5, DE.chaos_grey2,
               CT.CL_N_DROP4},
    },
    -- Koppen biomes (0.4.0; climate.koppen): the four smooth fitted fields and the A/B/C/D/E
    -- classifier (prototypes/expressions/climate_koppen.lua). No geography; defined on every load (base and
    -- beside Alien Biomes alike, as they read only the shared climate axes, the highland field and the tile
    -- belts). The toggle (tn_koppen) is a preset key, not a body.
    {
      release = "0.4.0",
      names = {CT.KOPPEN_TANN, CT.KOPPEN_SEASON, CT.KOPPEN_TCOLD, CT.KOPPEN_TWARM, CT.KOPPEN_PANN, CT.KOPPEN_SW,
               CT.KOPPEN_CLASS},
    },
    -- Koppen biomes (0.4.0; climate.koppen.snap): the warped classifier the snap reads and
    -- the three axis-snap bodies plus the vegetation-temperature snap, which the preset points the
    -- climate axes and the grain tile keys at when Koppen is on (presets.lua koppen_names). New bodies,
    -- no older save names them; reached only when a 0.4.0 preset bakes tn_koppen on beside Alien Biomes.
    {
      release = "0.4.0",
      names = {CT.KOPPEN_CLASS2, CT.KOPPEN_T_SNAP, CT.KOPPEN_M_SNAP, CT.KOPPEN_A_SNAP, CT.KOPPEN_TV_SNAP},
    },
    -- Koppen biomes (0.4.0; climate.koppen.compose): the cold-north/spawn-aware temperature and
    -- its vegetation cap, and the green-lifted moisture snap, which the preset points the climate axes and
    -- the grain tile keys at when Koppen is on (presets.lua koppen_names). New bodies, no older save names
    -- them; reached only when a 0.4.0 preset bakes tn_koppen on beside Alien Biomes. The Chaos/Corrupted/
    -- Moscow zone, the north snow and the spawn clearing compose over them with no body change.
    {
      release = "0.4.0",
      names = {CT.KOPPEN_COOL_T, CT.KOPPEN_CN_T, CT.KOPPEN_CN_TV, CT.KOPPEN_M_SNAP2},
    },
    -- The Middle East's sand desert (1.0.0; climate.desert): Alien Biomes only, as the climate bodies it wraps are.
    -- No geography: a 1.0.0 preset beside Alien Biomes names the two bodies over the tile temperature and tile aux
    -- keys, each under name at what the key held, and the band tests' bodies with the sand weight over the vanilla
    -- tile and exclusion keys.
    {
      release = "1.0.0",
      names = {CT.DS_WARP_A, CT.DS_WARP_B, CT.DS_DEPTH, CT.DS_DEPTH_FLATS, CT.DS_KEEP, CT.DS_FLATS, CT.DS_W,
               CT.DS_SAND, CT.DS_COAST, CT.DS_TILE_T, CT.DS_TILE_T_UNDER, CT.DS_TILE_A, CT.DS_TILE_A_UNDER,
               CT.DS_VANILLA, CT.DS_VANILLA_HIGH, CT.DS_VANILLA_NEXT, CT.DS_VANILLA_NEXT_HIGH, CT.DS_EXCLUDE},
    },
    -- Patagonia and the Monte as dry steppe (1.0.0; climate.steppe): Alien Biomes only, as the climate bodies it wraps
    -- are. No geography: a 1.0.0 Atlantic preset beside Alien Biomes names the three bodies over the tile moisture,
    -- tile aux and grass temperature keys and the tree body over the living trees' multiplier, and each under name at
    -- what the key held.
    {
      release = "1.0.0",
      names = {CT.SP_DEPTH, CT.SP_W, CT.SP_PATCH, CT.SP_TILE_M, CT.SP_TILE_M_UNDER, CT.SP_TILE_A, CT.SP_TILE_A_UNDER,
               CT.SP_TILE_TV, CT.SP_TILE_TV_UNDER, CT.SP_REACH, CT.SP_TREES, CT.SP_TREES_UNDER},
    },
    -- The Chaos zone's class successors (0.4.0; destroyed.dev.next.class2): Alien Biomes only, as
    -- class5 is. Named over class5 by a 0.4.0 preset with the zone on (presets.lua points the zone's class at
    -- class7). class6 widens the grey band; class7 (the active body) extends grey rock to the
    -- dev>0 fringe. New bodies, no older save names them; both ship in the Alien Biomes data stage.
    {
      release = "0.4.0",
      names = {DE.class6, DE.class7},
    },
    -- The Chaos zone's range yield (1.0.0; destroyed.dev.ranges): Alien Biomes only, as the next position is. A
    -- preset with Destroyed Europe on names it over dev, so the ranges inside the zone keep their snow and grey rim.
    -- A new body, which no older save names.
    {
      release = "1.0.0",
      names = {DE.dev3},
    },
    -- The trees of a range the zone encloses (1.0.0; destroyed.dev.range_trees): Alien Biomes only, as the exclusion
    -- is. The mask key's own body is 1, so a world whose preset names none of these keeps its trees; a preset with
    -- Destroyed Europe on names the mask and the dead trees' next body over the key and dead.
    {
      release = "1.0.0",
      names = {DE.tree_reach, DE.range_open, DE.range_open1, DE.dead3},
    },
    -- The snow the Moscow zone encloses (1.1.0, moscow.keep): Alien Biomes only, as the next position and Blue
    -- corrupted's class are. A preset with the zone at Chaos names the position over dev, the class over the zone's
    -- class and the mask over its open mask, one at Corrupted its class over Blue corrupted's. New bodies, which no
    -- older save names.
    {
      release = "1.1.0",
      names = {DE.dev4, DE.class8, DE.open3, BC.class3},
    },
    -- The second hotspot table's bodies: under files its table, which releases the row names regions.lua composes
    -- from it, as the region table does. No geography: a preset names them over the first table's (rule 15).
    {
      release = "0.2.0",
      names = {HS .. "lobe_v2", HS .. "iron_ore_v2", HS .. "copper_ore_v2", HS .. "coal_v2", HS .. "stone_v2",
               HS .. "uranium_ore_v2", HS .. "crude_oil_v2", NOISE .. "ore_gap_v2", NOISE .. "enemy_layer_v2",
               HS .. "iron_ore_qty_v2", HS .. "iron_ore_bars_v2", HS .. "copper_ore_qty_v2",
               HS .. "copper_ore_bars_v2",
               HS .. "coal_qty_v2", HS .. "coal_bars_v2", HS .. "stone_qty_v2", HS .. "stone_bars_v2",
               HS .. "uranium_ore_qty_v2", HS .. "uranium_ore_bars_v2", HS .. "crude_oil_qty_v2",
               HS .. "crude_oil_bars_v2", NOISE .. "enemy_v2"},
      files = {"prototypes/tables/hotspots_v2.lua"},
    },
    -- The scattered bases (enemies.scatter), the richness by place (resources.richness_v2) and the trees off hotspot
    -- ore (resources.ore_trees, its hook key holding its off value): no geography; 0.3.0's presets name them.
    {
      release = "0.3.0",
      names = {NOISE .. "enemy_v3", ORE .. "iron_ore_r_v2", ORE .. "copper_ore_r_v2", ORE .. "coal_r_v2",
               ORE .. "stone_r_v2", ORE .. "uranium_ore_r_v2", ORE .. "crude_oil_r_v2", ORE .. "copper_ore_p_v3",
               ORE .. "iron_ore_p_v3", ORE .. "coal_p_v3", ORE .. "stone_p_v3", ORE .. "uranium_ore_p_v3",
               NOISE .. "ore_wobble_v1", NOISE .. "ore_trees", NOISE .. "ore_open_v1", NOISE .. "ore_open_plants_v1",
               NOISE .. "ore_open_v2", NOISE .. "ore_open_plants_v2"},
    },
    -- The third hotspot table's bodies (0.3.1): under files its table, which releases the row names regions.lua
    -- composes from it. No geography: 0.3.1's presets name them over the second table's.
    {
      release = "0.3.1",
      names = {HS .. "iron_ore_v4", HS .. "copper_ore_v4", HS .. "coal_v4", HS .. "stone_v4", HS .. "uranium_ore_v4",
               HS .. "iron_ore_qty_v4", HS .. "copper_ore_qty_v4", HS .. "coal_qty_v4", HS .. "stone_qty_v4",
               HS .. "uranium_ore_qty_v4", HS .. "stone_rich_v1", NOISE .. "ore_gap_v3", NOISE .. "enemy_layer_v3",
               NOISE .. "enemy_v4", NOISE .. "enemy_v5", ORE .. "iron_ore_r_v3", ORE .. "copper_ore_r_v3",
               ORE .. "coal_r_v3", ORE .. "stone_r_v3", ORE .. "uranium_ore_r_v3", ORE .. "iron_ore_p_v4",
               ORE .. "copper_ore_p_v4", ORE .. "coal_p_v4", ORE .. "stone_p_v4", ORE .. "uranium_ore_p_v4",
               NOISE .. "ore_open_v3", NOISE .. "ore_open_plants_v3"},
      files = {"prototypes/tables/hotspots_v3.lua"},
    },
    -- Ore at vanilla's measure: regular patches on vanilla's function with the footprint gap,
    -- and the solid hotspots' third version (resources.natural.fn2, hotspots_v2.v3); 0.3.0's presets name them.
    {
      release = "0.3.0",
      names = {ORE .. "all_patches_v2", ORE .. "iron_ore_patches_v2", ORE .. "copper_ore_patches_v2",
               ORE .. "coal_patches_v2", ORE .. "stone_patches_v2", ORE .. "uranium_ore_patches_v2",
               ORE .. "crude_oil_patches_v2", ORE .. "offshore_oil_patches_v2",
               HS .. "iron_ore_v3", HS .. "copper_ore_v3", HS .. "coal_v3", HS .. "stone_v3", HS .. "uranium_ore_v3",
               HS .. "iron_ore_qty_v3", HS .. "copper_ore_qty_v3", HS .. "coal_qty_v3", HS .. "stone_qty_v3",
               HS .. "uranium_ore_qty_v3"},
    },
    -- Regional scarcity (resources.scarcity): each resource's province weight and the keep its regular patch density
    -- reads; no geography; 0.3.0's patch bodies read them.
    {
      release = "0.3.0",
      names = {ORE .. "province_iron_ore_v1", ORE .. "province_copper_ore_v1", ORE .. "province_coal_v1",
               ORE .. "province_stone_v1", ORE .. "province_uranium_ore_v1", ORE .. "province_crude_oil_v1",
               ORE .. "keep_iron_ore_v1", ORE .. "keep_copper_ore_v1", ORE .. "keep_coal_v1", ORE .. "keep_stone_v1",
               ORE .. "keep_uranium_ore_v1", ORE .. "keep_crude_oil_v1"},
    },
    -- The palm switch (climate-tiles): the constant and the copies of the installed palm autoplace, built at
    -- data-final-fixes (tiles.palm); with no Alien Biomes each copy is the neutral body.
    {
      release = "0.1.0",
      names = {CT.PALM_CONST, CT.PALM_A_P, CT.PALM_A_R, CT.PALM_B_P, CT.PALM_B_R},
    },
    -- The tree bodies (trees-forests). They belong to no geography. The hook keys and the gate hold their
    -- off values; the palms' second versions wrap climate-tiles' copies, defined on every load as the
    -- copies are (trees.lua).
    {
      release = "0.1.0",
      names = {TFN.K_FORESTS_ON, TFN.K_TREE_MULT, TFN.K_TREE_LIFT, TFN.TF_LIFT, TFN.TF_VTEMP, TFN.TF_VTREE_R,
               TFN.TF_VDECO, TFN.PALM_A_P2,
      TFN.PALM_B_P2,
               TF_TREES["tree-01"].p, TF_TREES["tree-01"].r, TF_TREES["tree-01"].body,
               TF_TREES["tree-02"].p, TF_TREES["tree-02"].r, TF_TREES["tree-02"].body,
               TF_TREES["tree-02-red"].p, TF_TREES["tree-02-red"].r, TF_TREES["tree-02-red"].body,
               TF_TREES["tree-03"].p, TF_TREES["tree-03"].r, TF_TREES["tree-03"].body,
               TF_TREES["tree-04"].p, TF_TREES["tree-04"].r, TF_TREES["tree-04"].body,
               TF_TREES["tree-05"].p, TF_TREES["tree-05"].r, TF_TREES["tree-05"].body,
               TF_TREES["tree-06"].p, TF_TREES["tree-06"].r, TF_TREES["tree-06"].body,
               TF_TREES["tree-06-brown"].p, TF_TREES["tree-06-brown"].r, TF_TREES["tree-06-brown"].body,
               TF_TREES["tree-07"].p, TF_TREES["tree-07"].r, TF_TREES["tree-07"].body,
               TF_TREES["tree-08"].p, TF_TREES["tree-08"].r, TF_TREES["tree-08"].body,
               TF_TREES["tree-08-brown"].p, TF_TREES["tree-08-brown"].r, TF_TREES["tree-08-brown"].body,
               TF_TREES["tree-08-red"].p, TF_TREES["tree-08-red"].r, TF_TREES["tree-08-red"].body,
               TF_TREES["tree-09"].p, TF_TREES["tree-09"].r, TF_TREES["tree-09"].body,
               TF_TREES["tree-09-brown"].p, TF_TREES["tree-09-brown"].r, TF_TREES["tree-09-brown"].body,
               TF_TREES["tree-09-red"].p, TF_TREES["tree-09-red"].r, TF_TREES["tree-09-red"].body,
               TF_ROCKS["huge-rock"].key, TF_ROCKS["huge-rock"].body, TF_ROCKS["big-rock"].key,
               TF_ROCKS["big-rock"].body, TF_ROCKS["big-sand-rock"].key, TF_ROCKS["big-sand-rock"].body,
               TF_ROCKS["medium-rock"].key, TF_ROCKS["medium-rock"].body, TF_ROCKS["small-rock"].key,
               TF_ROCKS["small-rock"].body, TF_ROCKS["tiny-rock"].key, TF_ROCKS["tiny-rock"].body,
               TF_ROCKS["medium-sand-rock"].key, TF_ROCKS["medium-sand-rock"].body, TF_ROCKS["small-sand-rock"].key,
               TF_ROCKS["small-sand-rock"].body, TF_ROCKS["red-desert-decal"].key, TF_ROCKS["red-desert-decal"].body,
               TF_ROCKS["sand-decal"].key, TF_ROCKS["sand-decal"].body, TF_ROCKS["sand-dune-decal"].key,
               TF_ROCKS["sand-dune-decal"].body,
               TF_DECO["light-mud-decal"], TF_DECO["green-asterisk"], TF_DECO["green-asterisk-mini"],
               TF_DECO["green-bush-mini"], TF_DECO["green-carpet-grass"], TF_DECO["green-croton"],
               TF_DECO["green-desert-bush"], TF_DECO["green-hairy-grass"], TF_DECO["green-pita"],
               TF_DECO["green-pita-mini"], TF_DECO["green-small-grass"]},
    },
    -- The great forests' ground (1.0.0; trees.ground): the weight key, holding its off value, on every load; the
    -- weight, the forest's moistures, the tree lift's second version and the multiplier on the weight with Alien
    -- Biomes only, as the climate bodies they read are. No geography: a 1.0.0 preset with the forests on names them.
    {
      release = "1.0.0",
      names = {TFN.K_FOREST_GROUND, TFN.FG_W, TFN.FG_W_ZONE, TFN.FG_TREES, TFN.FG_M, TFN.FG_TM, TFN.TF_LIFT2,
               TFN.FG_MULT, TFN.FG_MULT_ZONE},
    },
    -- The ridges: no geography of their own; each map's crest and openings bodies read
    -- prototypes/tables/ranges.lua, and the shared bodies with the toggle's neutral pair (waterways') read
    -- them.
    {
      release = "0.1.0",
      names = {RDN.EU_BAND, RDN.AT_BAND, RDN.OW_BAND, RDN.RD_HEIGHT, RDN.EU_WANDER_U, RDN.AT_WANDER_U,
               RDN.OW_WANDER_U, RDN.EU_WANDER_V, RDN.AT_WANDER_V, RDN.OW_WANDER_V, RDN.EU_RUN, RDN.AT_RUN,
               RDN.OW_RUN, RDN.EU_KEEP, RDN.AT_KEEP, RDN.OW_KEEP, RDN.RD_FREE, RDN.K_ROCK_LIFT, RDN.K_GROUND,
               RDN.K_HIGH_TILE, RDN.RD_RISE, RDN.RD_GATE, RDN.RD_LAPSE, RDN.RD_GROUND, RDN.RD_HIGH, RDN.RD_RISE_TILE,
               RDN.RD_HIGH_TILE, RDN.RD_FRAY, RDN.RD_FRAY_TILE, RDN.RD_MASSIF, RDN.RD_ROCK_LIFT, RDN.RD_ROCK_LIFT_AB,
               RDN.RD_ROCK_DENSITY, TF_ROCKS["huge-rock"].high, TF_ROCKS["big-rock"].high,
               TF_ROCKS["big-sand-rock"].high, RDN.RD_CLIFFINESS, RDN.RD_CLEAR, RDN.ORE_IRON, RDN.ORE_COPPER,
               RDN.ORE_COAL, RDN.ORE_STONE, RDN.ORE_URANIUM, RDN.ORE_OIL},
      files = {"prototypes/tables/ranges.lua"},
    },
    -- The line field: no geography of its own, the same as the ridges row above.
    {
      release = "0.2.0",
      names = {RDN.RD_CLIFF_ELEVATION2, RDN.EU_CREST2, RDN.AT_CREST2, RDN.OW_CREST2, RDN.EU_OPENINGS2, RDN.AT_OPENINGS2,
               RDN.OW_OPENINGS2, RDN.EU_LINE_DEPTH, RDN.AT_LINE_DEPTH, RDN.OW_LINE_DEPTH, RDN.EU_LINE_SIDE,
               RDN.AT_LINE_SIDE, RDN.OW_LINE_SIDE, RDN.EU_LINE_NEAR, RDN.AT_LINE_NEAR, RDN.OW_LINE_NEAR,
               RDN.EU_LINE_REACH, RDN.AT_LINE_REACH, RDN.OW_LINE_REACH, RDN.EU_LINE_ALONG, RDN.AT_LINE_ALONG,
               RDN.OW_LINE_ALONG},
    },
    -- The ridges' union (0.3.0): under files the second range table, which releases the
    -- ranges it holds; the next highland, tile reach and passes over both tables, which a preset names over the first
    -- table's. No geography.
    {
      release = "0.3.0",
      names = {RDN.EU_HIGH2, RDN.AT_HIGH2, RDN.OW_HIGH2, RDN.EU_HIGH_TILE2, RDN.AT_HIGH_TILE2, RDN.OW_HIGH_TILE2,
               RDN.EU_PASSES2, RDN.AT_PASSES2, RDN.OW_PASSES2,
               RDN.EU_CREST3, RDN.AT_CREST3, RDN.OW_CREST3, RDN.EU_OPENINGS3, RDN.AT_OPENINGS3, RDN.OW_OPENINGS3,
               RDN.EU_LINE_DEPTH2, RDN.AT_LINE_DEPTH2, RDN.OW_LINE_DEPTH2, RDN.EU_LINE_SIDE2, RDN.AT_LINE_SIDE2,
               RDN.OW_LINE_SIDE2, RDN.EU_LINE_NEAR2, RDN.AT_LINE_NEAR2, RDN.OW_LINE_NEAR2, RDN.EU_LINE_REACH2,
               RDN.AT_LINE_REACH2, RDN.OW_LINE_REACH2, RDN.EU_LINE_ALONG2, RDN.AT_LINE_ALONG2, RDN.OW_LINE_ALONG2,
               RDN.EU_KEEP2, RDN.AT_KEEP2, RDN.OW_KEEP2, RDN.EU_RUN2, RDN.AT_RUN2, RDN.OW_RUN2, RDN.EU_BAND2,
               RDN.AT_BAND2, RDN.OW_BAND2},
      files = {"prototypes/tables/ranges_v2.lua"},
    },
    -- The hotspot, ramp, sea and enemy bodies and the wrappers of the pack's live autoplace:
    -- no geography of their own. The Oil Rig's offshore-oil wrappers exist only
    -- with the Oil Rig loaded, so tests/frozen.json registers them from the M3 dump with the "live"
    -- mask (their own composition; the Oil Rig text they wrap follows the pack, versioning rule 3).
    {
      release = "0.1.0",
      names = {REN.HS_BLOB, REN.HS_IRON, REN.HS_IRON_P, REN.HS_IRON_R, REN.HS_COPPER, REN.HS_COPPER_P,
      REN.HS_COPPER_R, REN.HS_COAL, REN.HS_COAL_P,
               REN.HS_COAL_R, REN.HS_STONE, REN.HS_STONE_P, REN.HS_STONE_R, REN.HS_URANIUM, REN.HS_URANIUM_P,
               REN.HS_URANIUM_R, REN.HS_OIL, REN.HS_OIL_P,
               REN.HS_OIL_R, REN.HS_OFFSHORE, REN.HS_OFFSHORE_P, REN.HS_OFFSHORE_R, REN.RAMP, REN.SEA,
               REN.ENEMY_LAYER, REN.ENEMY, REN.ORE_IRON_P2,
               REN.ORE_IRON_R, REN.ORE_COPPER_P2, REN.ORE_COPPER_R, REN.ORE_COAL_P2, REN.ORE_COAL_R, REN.ORE_STONE_P2,
               REN.ORE_STONE_R,
               REN.ORE_URANIUM_P2, REN.ORE_URANIUM_R, REN.ORE_OIL_P2, REN.ORE_OIL_R, REN.OFFSHORE_P, REN.OFFSHORE_R,
               REN.ORE_FN, REN.ORE_GAP, REN.ORE_PATCH_IRON, REN.ORE_PATCH_COPPER, REN.ORE_PATCH_COAL,
               REN.ORE_PATCH_STONE, REN.ORE_PATCH_URANIUM, REN.ORE_PATCH_OIL, REN.ORE_PATCH_OFFSHORE},
      files = {"prototypes/tables/hotspots.lua"},
    },
    -- Each map's version 6 (0.1.0), dropped in 0.3.0 (one geography version per map) but for its frame (config.lua
    -- frames), the chain every map-wide layer reads, and the shared bodies the 0.3.0 versions still name: the
    -- offshore stamp, the start mask, the city fold, the start land guarantee, distance and the hook gate's keys.
    -- tests/collapsed.json names what each row lost.
    {
      release = "0.1.0",
      map = "europe",
      geography = 14,
      names = {ELN.EU6_GX, ELN.EU6_GY, ELN.EU6_U, ELN.EU6_V, ELN.EU6_CX, ELN.EU6_CY,
               REN.EU_FIELDS, START_MASK2, EU_CITY_INDEX, EU_CITY_CX, EU_CITY_CY, START_LAND, DISTANCE, K_ON, K_FORDS,
               ONE, ZERO},
      files = {EU_GEO_FILE, EU_LAND_COARSE_FILE, EU_SPAWN_FILE, "prototypes/tables/hotspots.lua", EU_WW_FILES[1],
               EU_WW_FILES[2], EU_WW_FILES[3], EU_WW_FILES[4], EU_WW_FILES[5], EU_WW_FILES[6]},
    },
    {
      release = "0.1.0",
      map = "atlantic",
      geography = 17,
      names = {OAS.AT6_GX, OAS.AT6_GY, OAS.AT6_U, OAS.AT6_V, OAS.AT6_CX, OAS.AT6_CY,
               REN.AT_FIELDS, OAS.AT_CITY_INDEX, OAS.AT_CITY_CX, OAS.AT_CITY_CY},
      files = {AT_LAND_COARSE_FILE, "prototypes/tables/hotspots.lua"},
    },
    {
      release = "0.1.0",
      map = "olde_world",
      geography = 18,
      names = {OAS.OW6_GX, OAS.OW6_GY, OAS.OW6_U, OAS.OW6_V, OAS.OW6_CX, OAS.OW6_CY,
               REN.OW_FIELDS, OAS.OW_CITY_INDEX, OAS.OW_CITY_CX, OAS.OW_CITY_CY},
      files = {OW_LAND_COARSE_FILE, "prototypes/tables/hotspots.lua"},
    },
    -- 0.3.0: Old World's version 8, version 7's composition under names of its own.
    {
      release = "0.3.0",
      map = "olde_world",
      geography = 21,
      names = {
               OAS.OW8_GX, OAS.OW8_GY, OAS.OW8_U, OAS.OW8_V, OAS.OW8_GEO, OAS.OW8_GEO_FINE, OAS.OW8_GEO_LEAN,
               OAS.OW8_LAND_COARSE, OAS.OW8_DETAIL,
               OAS.OW8_FAR, OAS.OW8_ENTRY, OAS.OW8_CX, OAS.OW8_CY, OAS.OW8_LAKES, OAS.OW8_SHORE, OAS.OW8_SPAWN_LAKE,
               OAS.OW8_SPAWN_BIAS, OAS.OW_WW7[1], OAS.OW_WW7[2], OAS.OW_WW7[3], OAS.OW_WW7[4], OAS.OW_WW7[5],
               OAS.OW_WW7[6], OAS.OW_WW7[7], OAS.OW_WW7[8], OAS.OW_CANALS7[1], OAS.OW_CANALS7[2], OAS.OW_CANALS7[3],
               OAS.OW_CANALS7[4], OAS.OW_CANALS7[5], OAS.OW_CANALS7[6], OAS.OW_CANALS7[7], OAS.OW_CANALS7[8],
               OAS.OW_DAMS7[1], OAS.OW_DAMS7[2], OAS.OW_DAMS7[3], OAS.OW_DAMS7[4], OAS.OW_DAMS7[5], OAS.OW_DAMS7[6],
               OAS.OW_DAMS7[7], OAS.OW_DAMS7[8], OAS.OW_FORDS7[1], OAS.OW_FORDS7[2], OAS.OW_FORDS7[3],
               OAS.OW_FORDS7[4], OAS.OW_FORDS7[5], OAS.OW_FORDS7[6], OAS.OW_FORDS7[7], OAS.OW_FORDS7[8],
               OAS.OW_MOUTH2[1], OAS.OW_MOUTH2[2], OAS.OW_MOUTH2[3], OAS.OW_MOUTH2[4], OAS.OW_MOUTH2[5],
               OAS.OW_MOUTH2[6], OAS.OW_MOUTH2[7], OAS.OW_MOUTH2[8], OAS.OW_WARP2[1], OAS.OW_WARP2[2],
               OAS.OW_WARP2[3], OAS.OW_WARP2[4], OAS.OW_WARP2[5], OAS.OW_WARP2[6], OAS.OW_WARP2[7], OAS.OW_WARP2[8],
               OAS.OW_WARP2[9], OAS.OW_WARP2[10], OAS.OW_WARP2[11], OAS.OW_WARP2[12], OAS.OW_WARP2[13],
               OAS.OW_WARP2[14], OAS.OW_WARP2[15], OAS.OW_WARP2[16], OAS.OW_WARP2[17], OAS.OW_WARP2[18],
               OAS.OW_WARP2[19], OAS.OW_WARP2[20], OAS.OW_WARP2[21], OAS.OW_WARP2[22], OAS.OW_WARP2[23],
               OAS.OW_WARP2[24], OAS.OW_WARP2[25], OAS.OW_WARP2[26], OAS.OW_WARP2[27], OAS.OW_WARP2[28],
               OAS.OW_WARP2[29], OAS.OW_WARP2[30], OAS.OW_WARP2[31], OAS.OW_WARP2[32]},
      files = {
               OAS.OW7_GEO_FILE, OAS.OW8_LEAN_FILE, OW_LAND_COARSE_FILE, OAS.OW7_SPAWN_FILE,
               "prototypes/tables/hotspots.lua",
               OAS.OW7_WW_FILES[1], OAS.OW7_WW_FILES[2], OAS.OW7_WW_FILES[3], OAS.OW7_WW_FILES[4],
               OAS.OW7_WW_FILES[5], OAS.OW7_WW_FILES[6], OAS.OW7_WW_FILES[7], OAS.OW7_WW_FILES[8]},
    },
    -- 0.3.1: Old World's next geo body (coast.next), which a new world's preset names over version 8's past scale 6.
    {
      release = "0.3.1",
      names = {OAS.OW9_GEO},
      files = {OAS.OW9_GEO_FILE},
    },
    -- 0.3.2: Old World's Map type version 9 (geography 24), which a Map-type-only world names and the preset names for
    -- elevation past scale 6, and the coast fray its coast reads there.
    {
      release = "0.3.2",
      map = "olde_world",
      geography = 24,
      names = {OAS.OW9_ENTRY, OAS.OW9_SHORE, OAS.OW9_LAKES, OAS.OW_GEO_FRAY1, OAS.OW_WW8[1], OAS.OW_WW8[2],
               OAS.OW_FORDS8[1], OAS.OW_FORDS8[2], OAS.OW_WARP3[1], OAS.OW_WARP3[2], OAS.OW_FIT_FRAY1,
               OAS.OW_LAND_FRAY1, OAS.OW_WATER_FRAY1},
      files = {OAS.OW9_WW_FILES[1], OAS.OW9_WW_FILES[2]},
    },
    -- 0.3.2: Old World's geo body over the next one (coast.overlay) and its two layers, which a new world's preset
    -- names over version 8's past scale 6.
    {
      release = "0.3.2",
      names = {OAS.OW10_GEO, OAS.OW10_LAND, OAS.OW10_WATER},
      files = {OAS.OW10_LAND_FILE, OAS.OW10_WATER_FILE},
    },
    -- 0.3.1: Atlantic's next spawn folds (spawn_next) and the city table's version 2 they are built from. No
    -- geography: a new world names them over version 8's folds by preset.
    {
      release = "0.3.1",
      names = {OAS.AT_CITY_CX2, OAS.AT_CITY_CY2, OAS.AT9_SPAWN_LAKE, OAS.AT9_SPAWN_BIAS},
      files = {"prototypes/tables/cities_atlantic_v2.lua", OAS.AT9_SPAWN_FILE},
    },
    -- 0.3.0: Atlantic's version 8, version 7's composition under names of its own.
    {
      release = "0.3.0",
      map = "atlantic",
      geography = 22,
      names = {
               OAS.AT8_GX, OAS.AT8_GY, OAS.AT8_U, OAS.AT8_V, OAS.AT8_GEO, OAS.AT8_LAND_COARSE, OAS.AT8_DETAIL,
               OAS.AT8_FAR, OAS.AT8_ENTRY, OAS.AT8_CX, OAS.AT8_CY, OAS.AT8_LAKES, OAS.AT8_SHORE, OAS.AT8_SPAWN_LAKE,
               OAS.AT8_SPAWN_BIAS, OAS.AT_WW7[1], OAS.AT_WW7[2], OAS.AT_WW7[3], OAS.AT_WW7[4], OAS.AT_WW7[5],
               OAS.AT_WW7[6], OAS.AT_WW7[7], OAS.AT_WW7[8], OAS.AT_CANALS7[1], OAS.AT_CANALS7[2], OAS.AT_CANALS7[3],
               OAS.AT_CANALS7[4], OAS.AT_CANALS7[5], OAS.AT_CANALS7[6], OAS.AT_CANALS7[7], OAS.AT_CANALS7[8],
               OAS.AT_DAMS7[1], OAS.AT_DAMS7[2], OAS.AT_DAMS7[3], OAS.AT_DAMS7[4], OAS.AT_DAMS7[5], OAS.AT_DAMS7[6],
               OAS.AT_DAMS7[7], OAS.AT_DAMS7[8], OAS.AT_FORDS7[1], OAS.AT_FORDS7[2], OAS.AT_FORDS7[3],
               OAS.AT_FORDS7[4], OAS.AT_FORDS7[5], OAS.AT_FORDS7[6], OAS.AT_FORDS7[7], OAS.AT_FORDS7[8],
               OAS.AT_MOUTH2[1], OAS.AT_MOUTH2[2], OAS.AT_MOUTH2[3], OAS.AT_MOUTH2[4], OAS.AT_MOUTH2[5],
               OAS.AT_MOUTH2[6], OAS.AT_MOUTH2[7], OAS.AT_MOUTH2[8], OAS.AT_WARP2[1], OAS.AT_WARP2[2],
               OAS.AT_WARP2[3], OAS.AT_WARP2[4], OAS.AT_WARP2[5], OAS.AT_WARP2[6], OAS.AT_WARP2[7], OAS.AT_WARP2[8],
               OAS.AT_WARP2[9], OAS.AT_WARP2[10], OAS.AT_WARP2[11], OAS.AT_WARP2[12], OAS.AT_WARP2[13],
               OAS.AT_WARP2[14], OAS.AT_WARP2[15], OAS.AT_WARP2[16], OAS.AT_WARP2[17], OAS.AT_WARP2[18],
               OAS.AT_WARP2[19], OAS.AT_WARP2[20], OAS.AT_WARP2[21], OAS.AT_WARP2[22], OAS.AT_WARP2[23],
               OAS.AT_WARP2[24], OAS.AT_WARP2[25], OAS.AT_WARP2[26], OAS.AT_WARP2[27], OAS.AT_WARP2[28],
               OAS.AT_WARP2[29], OAS.AT_WARP2[30], OAS.AT_WARP2[31], OAS.AT_WARP2[32]},
      files = {
               OAS.AT7_GEO_FILE, AT_LAND_COARSE_FILE, OAS.AT7_SPAWN_FILE, "prototypes/tables/hotspots.lua",
               OAS.AT7_WW_FILES[1], OAS.AT7_WW_FILES[2], OAS.AT7_WW_FILES[3], OAS.AT7_WW_FILES[4],
               OAS.AT7_WW_FILES[5], OAS.AT7_WW_FILES[6], OAS.AT7_WW_FILES[7], OAS.AT7_WW_FILES[8]},
    },
    -- 0.4.0: Atlantic's next geo body (coast.next), which a new world's preset names over version 8's past scale 6.
    {
      release = "0.4.0",
      names = {OAS.AT9_GEO},
      files = {OAS.AT9_GEO_FILE},
    },
    -- 0.4.0: Atlantic's Map type version 9 (geography 25), which a Map-type-only world names and the preset names for
    -- elevation past scale 6, and the coast fray its coast reads there. Waterways reuse version 8's sets,
    -- so no new waterway files: the river and ford bodies are already released in the geography-22 row.
    {
      release = "0.4.0",
      map = "atlantic",
      geography = 25,
      names = {OAS.AT9_ENTRY, OAS.AT9_SHORE, OAS.AT9_LAKES, OAS.AT_GEO_FRAY1, OAS.AT_FIT_FRAY1,
               OAS.AT_LAND_FRAY1, OAS.AT_WATER_FRAY1},
    },
    -- 0.4.0: Atlantic's geo body over the next one (coast.overlay) and its two layers, which a new world's preset
    -- names over version 8's past scale 6.
    {
      release = "0.4.0",
      names = {OAS.AT10_GEO, OAS.AT10_LAND, OAS.AT10_WATER},
      files = {OAS.AT10_LAND_FILE, OAS.AT10_WATER_FILE},
    },
    -- 0.3.0: Europe's version 7, version 6 and its scale extension under names of its own.
    {
      release = "0.3.0",
      map = "europe",
      geography = 23,
      names = {
               ELN.EU7_GX, ELN.EU7_GY, ELN.EU7_U, ELN.EU7_V, ELN.EU7_GEO, ELN.EU7_LAND_COARSE, ELN.EU7_DETAIL,
               ELN.EU7_FAR, ELN.EU7_ENTRY, ELN.EU7_CX, ELN.EU7_CY, ELN.EU7_LAKES, ELN.EU7_SHORE, ELN.EU7_SPAWN_LAKE,
               ELN.EU7_SPAWN_BIAS, ELN.EU_WW5[1], ELN.EU_WW5[2], ELN.EU_WW5[3], ELN.EU_WW5[4], ELN.EU_WW5[5],
               ELN.EU_WW5[6], ELN.EU_WW5[7], ELN.EU_WW5[8], ELN.EU_CANALS5[1], ELN.EU_CANALS5[2], ELN.EU_CANALS5[3],
               ELN.EU_CANALS5[4], ELN.EU_CANALS5[5], ELN.EU_CANALS5[6], ELN.EU_CANALS5[7], ELN.EU_CANALS5[8],
               ELN.EU_DAMS5[1], ELN.EU_DAMS5[2], ELN.EU_DAMS5[3], ELN.EU_DAMS5[4], ELN.EU_DAMS5[5], ELN.EU_DAMS5[6],
               ELN.EU_DAMS5[7], ELN.EU_DAMS5[8], ELN.EU_FORDS5[1], ELN.EU_FORDS5[2], ELN.EU_FORDS5[3],
               ELN.EU_FORDS5[4], ELN.EU_FORDS5[5], ELN.EU_FORDS5[6], ELN.EU_FORDS5[7], ELN.EU_FORDS5[8],
               ELN.EU7_WARP[1], ELN.EU7_WARP[2], ELN.EU7_WARP[3], ELN.EU7_WARP[4], ELN.EU7_WARP[5], ELN.EU7_WARP[6],
               ELN.EU7_WARP[7], ELN.EU7_WARP[8], ELN.EU7_WARP[9], ELN.EU7_WARP[10], ELN.EU7_WARP[11],
               ELN.EU7_WARP[12], ELN.EU7_WARP[13], ELN.EU7_WARP[14], ELN.EU7_WARP[15], ELN.EU7_WARP[16],
               ELN.EU7_WARP[17], ELN.EU7_WARP[18], ELN.EU7_WARP[19], ELN.EU7_WARP[20], ELN.EU7_WARP[21],
               ELN.EU7_WARP[22], ELN.EU7_WARP[23], ELN.EU7_WARP[24], ELN.EU7_WARP[25], ELN.EU7_WARP[26],
               ELN.EU7_WARP[27], ELN.EU7_WARP[28], ELN.EU7_WARP[29], ELN.EU7_WARP[30], ELN.EU7_WARP[31],
               ELN.EU7_WARP[32]},
      files = {
               EU_GEO_FILE, EU_LAND_COARSE_FILE, EU_SPAWN_FILE, "prototypes/tables/hotspots.lua", EU_WW_FILES[1],
               EU_WW_FILES[2], EU_WW_FILES[3], EU_WW_FILES[4], EU_WW_FILES[5], EU_WW_FILES[6], ELN.EUX_WW_FILES[1],
               ELN.EUX_WW_FILES[2]},
    },
    -- The Destroyed Europe bodies (destroyed-europe). They belong to no geography: the zone and its heat
    -- read the region layer's zone depth and the spawn distance; the temperature's next version reads
    -- climate-tiles' Alien Biomes temperature, so it exists only with Alien Biomes and is registered from
    -- the M2 dump; each pool reads its map's city fold hash and prototypes/tables/destroyed.lua.
    {
      release = "0.1.0",
      names = {DE.zone, DE.heat, DE.temperature, DE.pool_europe, DE.pool_atlantic, DE.pool_olde_world,
               DE.chaos_fine, DE.chaos_macro, DE.chaos_kind, DE.chaos_class, DE.chaos_grass, DE.chaos_black_sand,
               DE.chaos_black_dirt, DE.chaos_red_dirt, DE.chaos_red_sand},
      files = {"prototypes/tables/destroyed.lua"},
    },
    -- The barrier and the lava patches after the first release (destroyed.barrier). They exist with Alien Biomes
    -- only and are registered from the M2 dump.
    {
      release = "0.2.0",
      names = {DE.zone2, DE.heat2, DE.class2, DE.edge, DE.blob, DE.flow, DE.lava, DE.kind2, DE.macro2, DE.reach,
               DE.open, DE.thin, DE.clear, DE.dead, DE.dead_noise, DE.palm_a, DE.palm_b, DE.chaos_grey, DE.out_land,
               DE.out_sea, DE.out_inside, DE.out_sd, DE.out_isles, DE.out_present, DE.out_depth},
      files = {"prototypes/tables/zone_outline.lua"},
    },
    -- Blue corrupted UK and Australia (blue). They exist with Alien Biomes only, the key and the under names aside.
    {
      release = "0.2.0",
      names = {BC.K, BC.reach, BC.open, BC.macro, BC.kind, BC.dry, BC.field, BC.class, BC.keep, BC.keep_under,
               BC.temperature, BC.temperature_under, BC.moisture, BC.moisture_under, BC.aux, BC.aux_under, BC.palm_a,
               BC.palm_a_under, BC.palm_b, BC.palm_b_under, BC.mauve_2, BC.mauve_1, BC.purple_2, BC.purple_1, BC.blue_2,
               BC.blue_1, BC.aubergine_dirt, BC.purple_dirt, BC.aubergine_rim, BC.out_britain, BC.out_australia,
               BC.out_sea, BC.out_ulster, BC.out_land, BC.out_depth},
      files = {"prototypes/tables/zone_blue.lua"},
    },
    -- The Moscow zone (0.3.1; config.lua moscow): its outline, the Moscow position, the keys, and the Corrupted bodies.
    -- The outline and keys are defined on every load; the rest exist with Alien Biomes only. Under files its table.
    {
      release = "0.3.1",
      names = {DE.mz_land, DE.mz_sea, DE.mz_inside, DE.mz_sd, DE.mz_present, DE.mz_depth, DE.mz_dev, DE.mz_key,
               DE.eu_key, BC.uk_key, BC.out_depth3, BC.mz_corrupt, BC.mz_gap, BC.class_under, BC.class2, BC.rim_keep,
               BC.mz_snow_0, BC.mz_snow_2},
      files = {"prototypes/tables/zone_moscow.lua"},
    },
    -- Blue corrupted UK's next outline (0.3.1; blue.outline.next): the United Kingdom alone. No geography; defined on
    -- every load, as the first outline's bodies are; a preset with the zone on names the next depth over the first.
    {
      release = "0.3.1",
      names = {BC.out_britain2, BC.out_sea2, BC.out_ulster2, BC.out_land2, BC.out_depth2},
      files = {"prototypes/tables/zone_blue_v2.lua"},
    },
    -- The list hook's body (tiles.scan), defined on every load like the other tile bodies.
    {
      release = "0.1.0",
      names = {CT.AB_KEEP_BODY, CT.VT_MIX},
    },
  },

  -- Elevation composition tunables (ARCHITECTURE.md, "Elevation composition"):
  --   transfer: e = tn_scale * c + if(c > 0, offset, -offset) with c clamped to +-clamp_px, so the
  --     tile class is the sign of c (vanilla land beat water down to elevation -0.027);
  --   detail: lattice detail of amplitude_px, zero at every pixel-centre tile (basis noise is 0 on
  --     its lattice), one octave per row, each with its own seed1 and lattice frequency
  --     per reference pixel;
  --   far_floor: the elevation beyond the map's extent, deep water out to any distance;
  --   edge_water, edge_min_scale: the elevation of the extent's outermost tile ring at scales from
  --     edge_min_scale up. The game lets deepwater border only water (its allowed_neighbors), so a
  --     land tile on the extent's edge turns the first tile beyond it to plain water; plain water
  --     (deepwater wins only below -2) on that ring keeps deep water from 1 tile out. From scale 3
  --     the ring tile is never the tile that holds a pixel centre, so the pixel-centre coast check is
  --     unchanged; at scales 1 and 2 it would be, and there the reference pixel keeps its class.
  coast = {
    -- split: the geography versions listed (by geo_id) read their fine fit (the version's fits.geo) up to max_scale
    -- and a lean fit, a refit of the same reference to a smaller Tile budget (data-src/fits PROVENANCE, stage lean),
    -- past it, each under a name of its own; the version's geo body picks one by the folded scale. Scales up to
    -- max_scale keep the fine fit, which the band fix's tables were built from.
    split = {max_scale = 6, versions = {
      [21] = {fine = OAS.OW8_GEO_FINE, lean = OAS.OW8_GEO_LEAN, lean_file = OAS.OW8_LEAN_FILE},
    }},
    -- next (0.3.1): per geography version, a geo body a new world's preset names over the version's own past
    -- above_scale (presets.lua), so scales up to above_scale bake nothing new and the band fix's tables stay valid.
    -- `file`: a generated fit bound to the version's warped chain, as its own fits are; `reads`: a fit it defines.
    next = {versions = {
      [21] = {body = OAS.OW9_GEO, file = OAS.OW9_GEO_FILE, above_scale = 6},
      [22] = {body = OAS.AT9_GEO, file = OAS.AT9_GEO_FILE, above_scale = 6},
    }},
    -- overlay (0.3.2): per geography version, a geo body over its next body (`over`) that a new world's preset names in
    -- place of both past above_scale: min(max(over, land - offset_px), offset_px - water). The land and water layers
    -- are generated from the reference raster (data-src/fits PROVENANCE, overlay stage) and bound to the version's
    -- warped chain. Away from its mask the land term reads exactly -offset_px and the water term +offset_px, so every
    -- other coast is the next body's to the bit; offset_px stays above any value a fit reaches.
    overlay = {offset_px = 1024, versions = {
      [21] = {body = OAS.OW10_GEO, over = OAS.OW9_GEO, above_scale = 6, land = OAS.OW10_LAND,
              land_file = OAS.OW10_LAND_FILE, water = OAS.OW10_WATER, water_file = OAS.OW10_WATER_FILE},
      [22] = {body = OAS.AT10_GEO, over = OAS.AT9_GEO, above_scale = 6, land = OAS.AT10_LAND,
              land_file = OAS.AT10_LAND_FILE, water = OAS.AT10_WATER, water_file = OAS.AT10_WATER_FILE},
    }},
    transfer_offset = 0.1,
    transfer_clamp_px = 16,
    detail_amplitude_px = 0.45,
    detail_clamp = 1,
    detail_octaves = {
      {seed1 = 7101, frequency = 1, weight = 1},
      {seed1 = 7102, frequency = 2, weight = 0.5},
      {seed1 = 7103, frequency = 4, weight = 0.25},
    },
    -- The coast warp (a land coast is one crisp line). Added to a coast fit
    -- of few terms per pixel, the lattice detail is a dithered halo: Old World's and Atlantic's fits cross
    -- zero at a median slope of 0.75 and 0.6 per px (Europe 1.46, their 5th percentile about 0.2), so a
    -- detail of 0.45 flips the sign of c up to 2 px either side of the coast, in speckles 1 px wide.
    -- The geographies listed read their fit at warped coordinates instead and their detail body is 0: u
    -- and v each add these terms, amplitude_px * basis_noise at wavelength_px reference px, geo-locked
    -- through the city offset. That moves the coast by the same bounded distance at any slope, so its
    -- roughness stays one line. The noise calls are 4 against the detail's 3. water_gain multiplies their
    -- shore body's water gain, so the shallows' width, set by the fit's slope, reads like Europe's rim.
    -- Europe joined the list for its cold coasts: on white ground the lattice detail read as a dark spray 10 to
    -- 20 tiles wide off Norway and the Baltic. Its steeper fit keeps the shallows thin at a lower gain.
    warp = {
      geographies = {14, 17, 18, 19, 20, 21, 22, 23},
      water_gain = {[14] = 1.5, [17] = 2.5, [18] = 2.5, [19] = 2.5, [20] = 2.5, [21] = 2.5, [22] = 2.5, [23] = 1.5},
      u = {{seed1 = 7411, wavelength_px = 5, amplitude_px = 0.45},
           {seed1 = 7413, wavelength_px = 1.2, amplitude_px = 0.22}},
      v = {{seed1 = 7412, wavelength_px = 5, amplitude_px = 0.45},
           {seed1 = 7414, wavelength_px = 1.2, amplitude_px = 0.22}},
      -- past_six: past above_scale the finest octave above is wavelength_px times the scale in tiles, 29 tiles at
      -- scale 24, so a coast reads as straight runs of stairs at player zoom. The listed geographies add one octave
      -- per axis fixed in tiles, scale 6's finest, at any scale past it; up to it the term folds to 0.
      past_six = {geographies = {19, 20, 21, 22}, above_scale = 6, wavelength_tiles = 7.2, amplitude_tiles = 1.32,
                  seed1 = {u = 7415, v = 7416}},
      -- tile_octaves: the listed geographies add these octaves per axis, fixed in tiles, from min_scale up, so a coast
      -- leaves the fit's pixel lattice between the octaves above; below min_scale each folds to 0. Past scale 6 only:
      -- up to 6 Exact coastlines writes most coasts on Old World and Atlantic.
      tile_octaves = {geographies = {}, terms = {
        {min_scale = 12, max_scale = 12, wavelength_tiles = 7, amplitude_tiles = 0.6, seed1 = {u = 7417, v = 7418}},
      }},
    },
    far_floor = -100,
    edge_water = -1,
    edge_min_scale = 3,
    -- The soft map edge: a version with
    -- edge = true replaces its box's inside (inf, and the edge_water ring) with a second coast, the
    -- version's own transfer of b = clamp(d / tn_scale + warp - width_px, -transfer_clamp_px,
    -- transfer_clamp_px), d the box distance in tiles, so land sinks into deep water where b < 0 with
    -- the same beach and deepwater profile as a real coast. warp = warp_px * clamp(sum of the octaves,
    -- -1, 1), each octave a basis noise in geo tiles with its own seed1 and wavelength in reference px,
    -- so the cut reads as a wavy coastline that moves with the map seed. The band's water edge lies
    -- between width_px - warp_px and width_px + warp_px reference px inside the box: never closer than
    -- 4 px, so every land column the box cuts ends in water before it, and never deeper than 20 px,
    -- short of the nearest land the box does not cut (Cyprus 22 px, Alaska 24 px, Ireland and Stewart
    -- Island 25 px). The pixel-centre coast check masks reference land within width_px + warp_px + 1
    -- px of the box (mask_px), plus the side's margin where outline below gives it one; the band-fix
    -- handler writes nothing in that same reach (scripts/bandfix.lua, edge_band_reach in earth_test.py).
    -- fold_geographies: these read the octaves' sum folded back at +-1 instead of clamped there. A clamp
    -- pins about a fifth of the edge to one distance from the box, so it drew dead straight coast and
    -- square bays for hundreds of tiles along it, and straight lines ruin the map.
    edge_band = {
      width_px = 12,
      warp_px = 8,
      mask_px = 21,
      fold_geographies = {14, 17, 20, 22, 23},
      octaves = {
        {seed1 = 7401, wavelength_px = 32, weight = 1},
        {seed1 = 7402, wavelength_px = 12, weight = 0.5},
        {seed1 = 7403, wavelength_px = 4, weight = 0.25},
      },
      -- The margin's outline (at a far map view the box still read as a straight rectangle): a side's
      -- water edge moves further in by margin px * share, where margin is the map's table for that side,
      -- {along px, margin px} knots read piecewise linearly and 0 for a
      -- side with no table, and share = floor + the sum of each band's share * (0.5 + 0.5 * n / (1 + |n|)),
      -- n the band's gain times its octaves' weighted sum, each octave a basis noise in geo tiles. Two
      -- bands, so a stretch where the low one sits at its lowest still has bays of its own; a soft limit
      -- for the same reason, as a clamp would leave flat runs at one depth, which read as the box. The
      -- floor and the band shares sum to 1, so the outline stays between floor and all of the margin,
      -- moves with the map seed and never passes the table, whatever the seed: the table is the
      -- protection. Where a table reads 0 (the sea below Cyprus, the Atlantic beside Ireland, the east
      -- end of the Black Sea) the band is the plain 4 to 20 px strip above.
      outline = {
        floor = 0.2,
        bands = {
          {share = 0.45, gain = 1.6, octaves = {{seed1 = 7421, wavelength_px = 311, weight = 1}}},
          {share = 0.35, gain = 2.2, octaves = {{seed1 = 7422, wavelength_px = 137, weight = 1},
                                                {seed1 = 7423, wavelength_px = 59, weight = 0.7}}},
        },
        margins = {
          europe = {
            right = {{255, 0}, {300, 60}, {345, 100}, {640, 170}, {700, 100}, {820, 100}, {880, 150}, {1040, 170},
                     {1085, 60}, {1125, 60}, {1300, 6}, {1330, 0}, {1365, 0}, {1400, 20}, {1440, 120}, {1704, 300}},
            bottom = {{190, 0}, {260, 26}, {300, 18}, {360, 22}, {420, 18}, {500, 40}, {780, 80}, {900, 80},
                      {965, 0}, {2100, 0}, {2140, 6}, {2300, 170}, {2400, 300}},
          },
          atlantic = {
            right = {{735, 0}, {790, 160}, {830, 260}, {900, 110}, {970, 260}, {1010, 200}, {1060, 60}, {1125, 0}},
          },
          olde_world = {
            right = {{506, 0}, {561, 160}, {601, 260}, {671, 110}, {741, 260}, {781, 200}, {831, 60}, {896, 0}},
          },
        },
      },
    },
  },

  -- The coast fray (0.3.2), read past scale 6 by a Map type version's coast fit (geography map_type_of). The fit
  -- is a sum of bilinear tents on the reference pixel lattice, so between pixel centres its zero line runs straight
  -- for up to a pixel (12 or 24 tiles) and turns along the tents' axis-aligned asymptotes, and the coast warp's
  -- past_six octave (7.2 tiles, 1.32 tiles) bends that into notches with right-angled corners at player zoom. The
  -- version's fit reads these octaves on each warped axis in place of past_six: amplitude_tiles / scale * basis_noise
  -- at wavelength_tiles, fixed in tiles and geo-locked through the version's city offset. A warp moves the coast
  -- without changing what it encloses while its slope stays well under 1, so it adds next to no islet or pool; an
  -- added value (a jitter on the fit) flips the fit's sign in patches wherever it is flat near zero, so it is refused.
  coast_fray = {
    octaves = {
      {seed1 = {u = 7431, v = 7432}, wavelength_tiles = 6.1, amplitude_tiles = 0.6},
      {seed1 = {u = 7433, v = 7434}, wavelength_tiles = 3.3, amplitude_tiles = 0.5},
    },
  },












  -- The start mask (design rule 8): vanilla's starting_resources_lake_mask with the map's coarse land
  -- field in place of elevation. `versions` holds every version: a geography version names the one
  -- its preset bakes. Each names its formula (spawn.lua builds formula n from the version's numbers).
  -- Formula 2 (spawn-cities) reads the coarse field in reference pixels, so it is the same at every
  -- scale, and keeps starting ore off the spawn lake as vanilla's mask does with its own lake:
  -- clamp((min(coarse_gain * tn_land_coarse, tn_spawn_lake) - floor) / span, 0, 1) * tn_spawn_bias.
  -- It is full where the coarse field reads 5.5 or more and graded below it, so starting ore prefers
  -- ground well inside the coast (the coarse field is no calibrated distance: near coasts it reads land
  -- over estuaries and inlets, which at scale 1 lie inside the start area; spawn-cities measured
  -- London's stone there). On a coastal start the bias tilts the start area toward the city's own land.
  start_mask = {
    versions = {
      {name = START_MASK2, formula = 2, floor = 1, span = 10, coarse_gain = 2},
    },
  },

  -- The start ore guarantee: vanilla's starting patches pick
  -- among a few fixed spot-noise candidates per ore, so on archipelago and peninsula starts no
  -- start mask can keep every ore on the spawn's land (even an oracle mask loses some). Once, in on_init
  -- of an Earth or Map-type-only world, scripts/start_ore.lua floods the land reached on foot from the
  -- spawn (4-connected tiles without `water_layer` within
  -- `grid` tiles; a spawn tile in water starts from where a character lands within `seed_radius`),
  -- sums each ore's amount on those tiles within `radius` tiles, and where that is
  -- under `trigger` times `reference` (vanilla's mean starting amount within 150 tiles at seeds
  -- 1000, 1002 and 1004, times the control's richness) places one patch of `fill` times it on
  -- reached land: the nearest centre `min_distance` (vanilla's starting-patch excluder) to radius -
  -- r tiles out (rings every `ring_step` tiles, about `arc_step` tiles apart on a ring, at least
  -- `min_ring_points`) whose disc of r + `land_margin` tiles is all reached land and holds no
  -- resource within r + `ore_margin`. r is the disc that holds the amount at `density` per tile,
  -- shrunk by `shrink` down to `min_radius` when nothing fits. An ore whose control size is 0 is left
  -- alone. Beside RSO the pass runs the same way on what RSO placed, read after RSO's on_init (the
  -- `? rso-mod` dependency orders it first), so it adds only where RSO's own start fell short
  -- (at seed 1002 it added one stone patch of 68,390 on 33 tiles); with `rso_start` off, RSO's
  -- "Ore in starting area", the player asked for no ore there and the whole pass stands down. Scripted
  -- ore never shows in a map preview.
  -- An ore row may carry its own trigger and top_up (0.3.0: Prague's start held 143,335 coal, over
  -- half of vanilla's mean, so it got nothing and the next coal stood 496 tiles out past the first nests): under
  -- trigger times the reference it gets a patch of top_up times the reference less what it holds (not fill times the
  -- reference), so a thin start reaches top_up of vanilla's mean and a start at or over trigger of it gets nothing.
  start_ore = {
    ores = {
      {resource = "iron-ore", reference = 368000, density = 540},
      {resource = "copper-ore", reference = 357000, density = 860},
      {resource = "coal", reference = 266000, density = 890, trigger = 0.9, top_up = 1},
      {resource = "stone", reference = 159000, density = 750},
    },
    rso_start = "rso-ore-in-start-area",
    resource_type = "resource",
    water_layer = "water_tile",
    grid = 160,
    radius = 150,
    seed_radius = 32,
    trigger = 0.5,
    fill = 0.5,
    min_distance = 40,
    ring_step = 4,
    arc_step = 8,
    min_ring_points = 8,
    land_margin = 2,
    ore_margin = 3,
    shrink = 0.75,
    min_radius = 4,
    -- A placed patch's outline (a plain disc reads as computer-made): inner of its radius
    -- moved by gain times the hotspot blob's deviation from its mean over the disc, never past the radius
    -- find_spot proved land for; grow widens that radius so the kept tiles hold about the planned area.
    outline = {blob = REN.HS_BLOB, inner = 0.7, gain = 0.3, grow = 1.25},
  },

  -- The spawn (the map shifts so the chosen city sits at the spawn): the numbers spawn.lua
  -- builds every spawn body from (the names are each geography version's own, in its spawn record).
  --   hash: random is (map_seed_small * small_mult + floor(map_seed / high_div) * high_mult) % N + 1
  --     over the map's N cities. Every intermediate stays below 2^24, so float32 folds it
  --     exactly; map_seed itself is a float32, so seed 4294967295 reads as 4294967296 (its city
  --     differs from the integer hash's), which is why control reads the index back and never
  --     recomputes it.
  --   lake: the spawn lake, vanilla's starting-lake shape magnitude * ((d + n) / divisor - offset),
  --     d the distance from a centre `distance` tiles from the spawn on the city's generated bearing
  --     at the save's scale (one of `bearings` steps of a turn), n one basis-noise octave; water
  --     where d + n < offset * divisor (about 1,850 water tiles, nearest water 42.6 tiles). The
  --     bearing points at land reached on foot (tools/build_spawn.py): a seed-folded angle put
  --     the lake in open water north of coastal cities. Analytic in x, y, map_seed and per-save
  --     numbers, so it is firewall-clean and the start mask reads it too.
  --   bias: where the generated table turns it on, the start mask is multiplied by the half-plane
  --     clamp(1 + (x, y) . b / w, 0, 1), b the city's generated bias bearing and w its width (one of
  --     `widths` tiles), else by 1. Vanilla's starting ore does not know the sea (at scale 1
  --     Tallinn's copper and Helsinki's stone landed across the Gulf of Finland), and it takes, per
  --     ore, the best of about 11 spot-noise candidates in the start disc, so tools/build_spawn.py
  --     picks each city's bearing and width, or none, by the share of starting patches left off the
  --     city's own land over `layouts` random candidate layouts (from `seed`: `ores` ores of
  --     `candidates` candidates in a `region`-tile square, at least `spacing` apart), scored with
  --     this start mask and vanilla's favorability (the mask term 0 within `excluder` tiles, the
  --     start disc `radius` tiles); a patch is lost when under `share` of its centre and its rings
  --     at `patch` tiles lie on that land, and the bias goes on only where it lowers the lost share
  --     by more than `margin`. The draw is fixed, so the table does not depend on the map seed.
  --   land: the start land guarantee, (radius - distance) * slope + the transfer offset inside
  --     `radius` tiles of the spawn and -inf beyond, joined to the elevation by max after the
  --     far-field box and before dams and carves, so a named waterway still cuts it. The
  --     tile correction step waters the guarantee's outer ring next to the sea, so 16 keeps 12 dry.
  --   inland_lakes: sparse lakes at a fixed density: spot noise in geo tiles places exactly
  --     per_region conical spots of `radius` tiles and peak 1 in every square region of `region`
  --     tiles (hard_region_target_quantity), at random points at least about `spacing` apart; water
  --     where gain * (level - spot) + shore noise < 0 (a spot's quantity is its cone volume,
  --     pi radius^2 peak / cone_divisor), a lake of about radius * (1 - level) tiles (16 at 24 and
  --     1/3), so the design water fraction is per_region * pi * (radius * (1 - level))^2 / region^2
  --     (0.61 percent). Kept coast_px reference pixels inside the coast fit (no lake on a shore, a
  --     small island or an isthmus) and out of start_radii start radii of the spawn.
  --   warp (both lakes): octave rows of a domain warp, a basis noise per axis
  --     (seed1x, seed1y) of wavelength tiles times amplitude tiles, so no lake reads as a disc; size moves
  --     an inland lake's level by amplitude times a clamped low-frequency noise, so they are not all one
  --     size; the level stays far enough above 0 that the shore noise cannot open water off a spot.
  spawn = {
    random_value = "random",
    hash = {small_mult = 157, high_mult = 97, high_div = 65536},
    lake = {distance = 72, bearings = 16, magnitude = 2.5, offset = 3, divisor = 8,
            noise = {seed1 = 7201, wavelength = 12, amplitude = 4},
            warp = {{seed1x = 7205, seed1y = 7206, wavelength = 90, amplitude = 12},
                    {seed1x = 7207, seed1y = 7208, wavelength = 30, amplitude = 5}}},
    -- The spawn lake's shore on the geographies listed: noise rows of seed1, wavelength and amplitude
    -- tiles in place of lake.noise, and warp rows in place of lake.warp. lake.warp's rows can cancel
    -- the identity: on 13 percent of tiles a warped axis moves under 0.3 tiles per tile, so a band of
    -- rows or columns reads one lake distance and the shore runs straight along that axis, and where
    -- both axes stall it turns at a right angle. These warp rows keep each axis above 0.3 on all but
    -- 0.7 percent; the noise rows, wavelengths about 2.2 apart, give the shape back without a
    -- direction. lake keeps its rows for the released bodies and tools/build_spawn.py.
    lake_shape = {geographies = {19, 20},
                  noise = {{seed1 = 7201, wavelength = 31, amplitude = 3.5},
                           {seed1 = 7214, wavelength = 14.3, amplitude = 2},
                           {seed1 = 7215, wavelength = 6.6, amplitude = 1.1},
                           {seed1 = 7216, wavelength = 3.4, amplitude = 0.45}},
                  warp = {{seed1x = 7205, seed1y = 7206, wavelength = 90, amplitude = 8},
                          {seed1x = 7207, seed1y = 7208, wavelength = 30, amplitude = 3}}},
    -- lake_next: lake_shape's rows for the geographies listed, before lake_shape. Up to scale 2 a shore that bends
    -- gently still ran ten to twelve tiles along one axis; the short warp row moves it a tile or two every few tiles
    -- there. At scale 6 the lake already reads well, so the row stops past max_scale.
    lake_next = {geographies = {21, 22},
                 noise = {{seed1 = 7201, wavelength = 31, amplitude = 3.5},
                          {seed1 = 7214, wavelength = 14.3, amplitude = 2},
                          {seed1 = 7215, wavelength = 6.6, amplitude = 1.1},
                          {seed1 = 7216, wavelength = 3.4, amplitude = 0.45}},
                 warp = {{seed1x = 7205, seed1y = 7206, wavelength = 90, amplitude = 8},
                         {seed1x = 7207, seed1y = 7208, wavelength = 30, amplitude = 3},
                         {seed1x = 7217, seed1y = 7218, wavelength = 12, amplitude = 2.5, max_scale = 2}}},
    bias = {radius = 150, excluder = 40, widths = {50, 75, 100, 150}, seed = 7203, layouts = 150, ores = 4,
            candidates = 32, region = 450, spacing = 30, patch = {7, 14}, share = 0.5, margin = 0.005},
    land = {radius = 16, slope = 0.5},
    inland_lakes = {
      seed1 = 7202, region = 1024, per_region = 8, radius = 24, level = 1 / 3, gain = 12, candidates = 32,
      spacing = 128, cone_divisor = 3,
      shore = {seed1 = 7204, wavelength = 8, amplitude = 1},
      warp = {{seed1x = 7209, seed1y = 7210, wavelength = 48, amplitude = 12},
              {seed1x = 7211, seed1y = 7212, wavelength = 16, amplitude = 4}},
      size = {seed1 = 7213, wavelength = 256, amplitude = 0.2},
      coast_px = 2.5, coast_gain = 20, start_radii = 1.5, start_slope = 0.25,
      -- floor: away from every spot the term holds at least this, so the shore noise cannot dip single tiles below 0
      -- (1,159 water specks of 1 to 4 tiles in a 3,072 tile window at Frankfurt, Old World 12). Only a version whose
      -- spawn record sets lake_floor reads it, so the bodies of earlier versions stay byte-identical.
      floor = 0.5,
      -- The same versions warp with warp_floor and hold the fine shore noise at or above shore_min: at warp's
      -- amplitudes the warp's slope passed 1 and folded cones into L shapes with straight
      -- sides (Atlantic 12, 137,-212), and folds and the shore noise's dips cut 1 to 10 tile pools off the shores.
      warp_floor = {{seed1x = 7209, seed1y = 7210, wavelength = 48, amplitude = 8},
                    {seed1x = 7211, seed1y = 7212, wavelength = 16, amplitude = 1}},
      shore_min = -0.5,
    },
  },

  -- Ridges (ARCHITECTURE.md, "Expression inventory"). Every number the
  -- ridge bodies use; prototypes/expressions/ridges.lua builds them from prototypes/tables/ranges.lua:
  --   ramp_tiles, bias_tiles, contour   cliff_elevation = cliff_elevation_0 + cliff_elevation_interval * f,
  --              f = clamp(1 + h, low, high), h = (depth - bias) / ramp + fray (ridges.lua), so the one
  --              contour is the ridge's edge: a second one ran parallel to it as ranks (read on real
  --              sprites at Old World scale 6). The noise keeps it off the 4-tile lattice (an exact
  --              lattice hit deletes the cliffs) and no term reads cliff_richness, so frequency,
  --              continuity and richness are inert. ramp_tiles sets how far the fray moves the edge
  --   width      a vertex's half-width in tiles: min_tiles + gain_tiles * (height / ref_m) ^ power, tip_tiles
  --              at a crest's end vertices (below zero, so the ridge ends in a taper, never a cap)
  --   wander     the wandering axis: per axis of the chain, noise rows in reference pixels, so one shape
  --              on the map at every scale (at scale 6, about 100 and 36 tiles over 1,500 and 300)
  --   run_base, run   the width's multiplier: base plus noise rows in tiles, floored at 0
  --   fray       the height's noise row, in contours: at 64 tiles and 0.3 it breaks long east-west lines
  --              (longest straight 8 cliffs in the Alps). A depth multiplier here floated closed loops off
  --   gaps       noise gaps: an opening where the noise rows read under threshold, plus thin_gain as the
  --              ridge's width at the tile falls from thin_tiles to 0, less collar_gain inside a collar
  --              Read in real sprites, rows at 34 and 40 tiles made zigzags at cliff spacing, stubs and tiny
  --              loops, since a cliff cell is 4 tiles; the shortest row here, fray's 64, draws none
  --   collar_tiles   the radius round an opening's slot where the ridge stands whole (ridges.lua keep)
  --   flank_tiles   the near edge of the ridge as measured: earth_test.py's ridge metrics read it
  --   cliffiness   the cliffiness of a ridge cell; 0 inside an opening and inside the ridge-free start
  --   pass_tiles   an opening's cliffiness gap along the crest (at least 12, for 8 tiles
  --              clear; a 16-tile gap once measured 16 clear, but a 16-tile slot read 7.5 at Verecke
  --              in the ridge metrics, at the limit, and the wander shears a slot by up to a third: 24 read 7.5
  --              on a diagonal crest, the limit again, so 28), reach_tiles
  --              its least half-length across, reach_margin_tiles how far it outreaches the half-width;
  --              tip_tiles how far past a crest's end vertex an opening there reaches
  --   edge_tiles, edge_reach_tiles   a range cut by a map's edge with no pass on that map: no ridge cell
  --              within edge_tiles of the edge and edge_reach_tiles of the crossing
  --   start      the ridge-free disc round the spawn: max(radius_tiles, starting_area_radius) plus
  --              margin_tiles, the 4-tile lattice cell and a cliff's box (design rule 12; the start checks
  --              find 0 cliffs and 0 ridge cliffiness within 150 tiles)
  --   ore_clear_tiles   no ore within this of a crest outside the start disc, past the
  --              flank cliffs' boxes, so no ore entity stands on a ridge cell
  --   band_margin_px   the crest band reads the segments within this of the map's extent, the reach of
  --              the ore clearance at scale 1, however far the cliffs reach
  --   band_max_angle_degrees   the ore clearance reads, in the Entity program, each map's crest band: a
  --              superset of the tiles within ore_clear_tiles of a crest, built from crest pieces monotone
  --              along one axis whose segments lie within this angle of it, each a piecewise-linear
  --              function of that axis (3 operations per segment against 14 for an exact distance, which
  --              measured Entity +3,028 on Europe), its half-height ore_clear_tiles over the cosine of the
  --              piece's steepest angle
  --   centre_tiles   where the band is read inside a tile: the Entity program samples a tile at its
  --              integer corner while an ore entity stands at the tile's centre, half a tile on in x and
  --              y (an in-game check found ore 23.4 to 23.97 tiles from a crest by centre, every one with
  --              its corner outside 24), so the band reads the centre
  --   switch_threshold   the toggle reads on above it (its bodies are 1 and 0)
  --   reset_size   the cliff control's size the on_init reset writes when the slider was none
  --   high       the highland band round each range (a cliff squiggle on plain grass does not
  --              read as a mountain). A crest piece's reach in reference pixels is min_px + gain_px * (height /
  --              ref_m) ^ power, height the mean of the piece's mean and highest vertex; the band reads the crest
  --              band's own pieces, so the Entity program pays only per piece. The field is (largest reach less
  --              distance, plus the region layer's warp at fray_warp and for tile scores its roughness at
  --              fray_rough) over the falloff, clamped to 0 to 1, so a tall range is wider and stronger than a low
  --              one, and it fades in start.ramp_tiles outside the ridge-free start disc. Rocks: reach S * px +
  --              rock_tiles / S tiles over S * fall_px + rock_fall / S, so at scale 6 the terms are 30 and 36
  --              tiles, and at low scales, where a range is a few dozen tiles wide, the band stays flat across
  --              the crest instead of crowding it (the ridge metrics' rock ratio read 1.85 to 2.5 at scale 1 with the
  --              terms fixed). Tile scores: reach S * px over S * fall_px + fall_tiles.
  --              fray_massif: the tiles' rise also takes the marsh outline noise, a few hundred tiles at scale 6 and
  --              already in the Tile program, so the grey and the snow break into massifs instead of one band
  --   ground     tile scores alone read these, and they read a reach that follows the vertex heights along each
  --              piece (the Entity program, near its limit, keeps one reach per piece), so trees and decoratives
  --              keep the plain fields and the forests on the slopes stay. lean: the stony vanilla tiles' score at
  --              full highland. lapse_per_px2, lapse_from_px: beside Alien Biomes the tile temperature falls by
  --              lapse_per_px2 times the square of the rise over lapse_from_px in reference pixels, so the crest
  --              alone of a tall range leaves the temperate band for Alien Biomes' grey ground and, at the top, its
  --              snow, and a low range keeps its ground. cold_t, cold_min: the fall scales by the climate core
  --              over cold_t, at least cold_min, because ground already near frozen needs no lapse: at full fall
  --              the Urals drew a white stripe down their axis. fray: the grain's noise grows by this at full
  --              highland, or the grey ground's edge is a smooth line where the lapse is steep. massif: the rise over
  --              lapse_from_px scales by 1 + gain times the region layer's second warp, within low and high, so a
  --              long even crest (the east Caucasus, the Himalaya) breaks into massifs and low saddles every
  --              thousand tiles or so at scale 6 instead of one white tube. floor: the lapse stops
  --              here, because under about -50 every frozen tile scores below Alien Biomes' water-mud, which
  --              flooded the Himalaya at scale 6. moisture: the tile moisture's fall at full highland, off the
  --              wet grasses onto mineral ground
  --   rocks      the lift at full highland on rock_density as the three big vanilla rocks read it (each one's
  --              high body; rock decoratives keep vanilla's, they are ground cover), and on Alien Biomes' big
  --              rocks, whose noise threshold is far sharper; clear_tiles the radius round an opening of a kind in
  --              clear_kinds that keeps no lift, fade_tiles how far it fades back in. Unnamed gaps are not listed:
  --              each disc costs Entity about 14, and with them Old World read 32,067. To hold Entity under its
  --              limit at scale 1 too, the Entity band reads no cosine and no roughness, skips a piece shorter than
  --              short_px (its neighbours' reach covers it). ab_skip holds only the volcanic pair, whose peak
  --              reads differently: every other rock takes the hook, because Alien Biomes' rocks share one compiled
  --              text, and hooking 17 of the 29 split them in two, which grew a default world's Entity program by 15
  --              operations and 30 complexity
  --   line       the bodies new worlds take: ridges.lua, "The line field". base_tiles, gain, width_max_tiles: the
  --              reach, the distance from one contour to the next and the noise's scale. mask: no cliff past this
  --              many reaches of the crest, and the radius of the gap where a range's hand reverses. side_min_tiles:
  --              the width a side line needs, and side_keep the collar it keeps out of, both at side_level, the
  --              height between one contour and the next. fit_scale, fit_power: fit. turn_px: an east-west piece at
  --              least this long picks the hand. pass_min_tiles: a slot shrinks with fit, to this at the least,
  --              because a low scale packs the same passes into a shorter crest and the Alps at scale 1 are a
  --              28-tile slot every 40 tiles. snip: a short gap where the fine row passes this, so gaps come in two
  --              sizes. cut_share, cut_px: each crest corner cut this share of its segments, at most this many
  --              reference px. contour: three contours, the line and one side line each way. waves: a line's bends,
  --              tiles along the crest, amplitude in reaches, phase the row of run whose slow noise moves it, by
  --              phase reaches of noise. shear: how far a bend's phase leans with the distance from the crest. fine,
  --              stretch: ridges.lua's h; fine is in tiles. gaps as gaps below, with the threshold the line takes
  --   preset     what a new world's preset points at. names holds every body, and a save keeps the names it was made
  --              with, so a new value here moves new worlds and no save
  --   ores       the Earth ores whose live probability is wrapped (resource, preset key, wrapper)
  --   water      the water frequency slider's two vanilla readers stay the first water_slider,
  --              baked on every Earth preset at their default-slider values
  -- Names carry the ridges' version suffix; a changed body ships under the next one (design rule 21).
  ridges = {
    line = {
      base_tiles = 20, gain = 0.7, width_max_tiles = 50, mask = 1.9, side_min_tiles = 48, side_keep = 0.5,
      side_level = 0.5, fit_scale = 6, fit_power = 0.5, turn_px = 60, pass_min_tiles = 16, snip = 1.15, cut_share = 0.3,
      cut_px = 16, pass_tiles = 34,
      -- pass_tiles is the line bodies' slot: released bodies read ridges.pass_tiles, so that one stays
      contour = {low = -0.5, high = 2.5},
      waves = {{tiles = 210, amplitude = 0.3, phase = 1}, {tiles = 134, amplitude = 0.2, phase = 2},
               {tiles = 83, amplitude = 0.1, phase = 1}, {tiles = 53, amplitude = 0.05, phase = 2}},
      phase = 1.5, shear = 0.3,
      fine = {{seed1 = 7511, wavelength = 36, amplitude = 6}},
      stretch = {seed1 = 7509, wavelength = 96, gain = 0.35, floor = 0.6},
      gaps = {threshold = -0.6, thin_tiles = 26, thin_gain = 2.2},
      names = {
        cliff_elevation = RDN.RD_CLIFF_ELEVATION2,
        crest = {europe = RDN.EU_CREST2, atlantic = RDN.AT_CREST2, olde_world = RDN.OW_CREST2},
        openings = {europe = RDN.EU_OPENINGS2, atlantic = RDN.AT_OPENINGS2, olde_world = RDN.OW_OPENINGS2},
        depth = {europe = RDN.EU_LINE_DEPTH, atlantic = RDN.AT_LINE_DEPTH, olde_world = RDN.OW_LINE_DEPTH},
        side = {europe = RDN.EU_LINE_SIDE, atlantic = RDN.AT_LINE_SIDE, olde_world = RDN.OW_LINE_SIDE},
        near = {europe = RDN.EU_LINE_NEAR, atlantic = RDN.AT_LINE_NEAR, olde_world = RDN.OW_LINE_NEAR},
        reach = {europe = RDN.EU_LINE_REACH, atlantic = RDN.AT_LINE_REACH, olde_world = RDN.OW_LINE_REACH},
        along = {europe = RDN.EU_LINE_ALONG, atlantic = RDN.AT_LINE_ALONG, olde_world = RDN.OW_LINE_ALONG},
      },
    },
    -- What a new world's preset points at, split from names, which holds every body: a save keeps the names it was
    -- made with, so moving a value here moves new worlds and no save. No geography name is among them, so a new
    -- value here takes no tn_geo.
    preset = {
      cliff_elevation = RDN.RD_CLIFF_ELEVATION2,
      -- 0.3.0: the union of both range tables (ridges.union): its chopped line field, crest band, highland
      crest = {europe = RDN.EU_CREST3, atlantic = RDN.AT_CREST3, olde_world = RDN.OW_CREST3},
      openings = {europe = RDN.EU_OPENINGS3, atlantic = RDN.AT_OPENINGS3, olde_world = RDN.OW_OPENINGS3},
      band = {europe = RDN.EU_BAND2, atlantic = RDN.AT_BAND2, olde_world = RDN.OW_BAND2},
      high = {europe = RDN.EU_HIGH2, atlantic = RDN.AT_HIGH2, olde_world = RDN.OW_HIGH2},
      passes = {europe = RDN.EU_PASSES2, atlantic = RDN.AT_PASSES2, olde_world = RDN.OW_PASSES2},
      high_tile = {europe = RDN.EU_HIGH_TILE2, atlantic = RDN.AT_HIGH_TILE2, olde_world = RDN.OW_HIGH_TILE2},
    },
    -- The union (0.3.0): ridges.lua's next line field, keep, run, crest band, highland,
    -- tile reach and passes over both range tables, ranges.lua (released, 16 ranges) and ranges_v2.lua
    -- (data-src/ridges/ranges-v2.json, the ranges it lacked), which a preset names (preset above); the cold field's
    -- second version (names.cold2, 0.3.0) reads the union's pieces too. cold: a second-table piece enters the cold
    -- field only when its top clears its snow line, and outside the snow edge its field falls reach / ref_px times
    -- faster (ridges.lua highland), so its grey rim is as narrow as a ref_px piece's; past its ends its distance is
    -- the distance across plus taper times the distance past the end, so the snow ends in a V with diagonal sides,
    -- and fray times the ragged factor plus the edge rows (field units, wavelengths in tiles) fray its edge, which the
    -- slow region noise left smooth for hundreds of tiles.
    union = {
      -- wide: the first table's pieces also take these rows (0.3.0, the cold field's second version): their reach is a
      -- crest's whole length, and with the edge rows alone southern Norway's east edge still ran straight for about
      -- 1,000 tiles at map view
      cold = {ref_px = 15, fray = 0.05, taper = 1,
              edge = {{seed1 = 7523, tiles = 26, amplitude = 0.05}, {seed1 = 7524, tiles = 70, amplitude = 0.07}},
              wide = {{seed1 = 7531, tiles = 240, amplitude = 0.12}, {seed1 = 7532, tiles = 560, amplitude = 0.12}}},
      -- field: the union's line field (ridges.lua line_bodies): each chop row is a gap where sin(2 pi / tiles * axis +
      -- phase * slow noise + jitter) passes level, axis the map's x or y in tiles and jitter fast noise in tiles; the x
      -- row cuts every east-west run and the y row every north-south one, so no cliff holds one row of the 4-tile
      -- lattice for long (under 50 tiles at scales 12 and 24), and the jitter spaces the gaps unevenly.
      -- line: its bodies.
      field = {chop = {{axis = "x", tiles = 28, level = 0.75, phase = 3, run = 2,
                        jitter = {seed1 = 7525, wavelength = 15, amplitude = 2.5}},
                       {axis = "y", tiles = 28, level = 0.75, phase = 3, run = 1,
                        jitter = {seed1 = 7526, wavelength = 15, amplitude = 2.5}}}},
      line = {
        crest = {europe = RDN.EU_CREST3, atlantic = RDN.AT_CREST3, olde_world = RDN.OW_CREST3},
        openings = {europe = RDN.EU_OPENINGS3, atlantic = RDN.AT_OPENINGS3, olde_world = RDN.OW_OPENINGS3},
        depth = {europe = RDN.EU_LINE_DEPTH2, atlantic = RDN.AT_LINE_DEPTH2, olde_world = RDN.OW_LINE_DEPTH2},
        side = {europe = RDN.EU_LINE_SIDE2, atlantic = RDN.AT_LINE_SIDE2, olde_world = RDN.OW_LINE_SIDE2},
        near = {europe = RDN.EU_LINE_NEAR2, atlantic = RDN.AT_LINE_NEAR2, olde_world = RDN.OW_LINE_NEAR2},
        reach = {europe = RDN.EU_LINE_REACH2, atlantic = RDN.AT_LINE_REACH2, olde_world = RDN.OW_LINE_REACH2},
        along = {europe = RDN.EU_LINE_ALONG2, atlantic = RDN.AT_LINE_ALONG2, olde_world = RDN.OW_LINE_ALONG2},
      },
      names = {
        keep = {europe = RDN.EU_KEEP2, atlantic = RDN.AT_KEEP2, olde_world = RDN.OW_KEEP2},
        run = {europe = RDN.EU_RUN2, atlantic = RDN.AT_RUN2, olde_world = RDN.OW_RUN2},
        band = {europe = RDN.EU_BAND2, atlantic = RDN.AT_BAND2, olde_world = RDN.OW_BAND2},
        high_map = {europe = RDN.EU_HIGH2, atlantic = RDN.AT_HIGH2, olde_world = RDN.OW_HIGH2},
        high_tile_map = {europe = RDN.EU_HIGH_TILE2, atlantic = RDN.AT_HIGH_TILE2, olde_world = RDN.OW_HIGH_TILE2},
        passes = {europe = RDN.EU_PASSES2, atlantic = RDN.AT_PASSES2, olde_world = RDN.OW_PASSES2},
      },
    },
    flank_tiles = 16.37,
    ramp_tiles = 48,
    bias_tiles = 3,
    contour = {low = 0.5, high = 1.5},
    width = {ref_m = 4800, min_tiles = 10, gain_tiles = 38, power = 0.8, tip_tiles = -20},
    wander = {
      u = {{seed1 = 7501, wavelength = 250, amplitude = 16}, {seed1 = 7502, wavelength = 50, amplitude = 6}},
      v = {{seed1 = 7503, wavelength = 250, amplitude = 16}, {seed1 = 7504, wavelength = 50, amplitude = 6}},
    },
    run_base = 1.15,
    run = {{seed1 = 7505, wavelength = 420, amplitude = 0.55}, {seed1 = 7506, wavelength = 120, amplitude = 0.32}},
    fray = {{seed1 = 7508, wavelength = 64, amplitude = 0.3}},
    gaps = {noise = {{seed1 = 7509, wavelength = 96, amplitude = 1}, {seed1 = 7510, wavelength = 72, amplitude = 0.25}},
            threshold = -0.35, thin_tiles = 26, thin_gain = 2.2, collar_gain = 3},
    -- The cliff's art beside Alien Biomes. It ships whole grey stone cliff sheets its code leaves unused
    -- (they lack vanilla's -lower split, data.lua's TODO), and its ground is grey and white where
    -- vanilla's art is orange brown, so vanilla's cliff draws those sheets on one layer. A planet's
    -- cliff_settings beat a preset's (measured: name and cliff_smoothing both ignored), so the art goes
    -- on the prototype: every Nauvis world beside Alien Biomes, map colour and collision unchanged.
    cliff_art = {cliff = "cliff", mod = "alien-biomes-graphics", from = "__base__/", to = "__alien-biomes-graphics__/"},
    cliffiness = 10,
    pass_tiles = 28,
    reach_tiles = 32,
    reach_margin_tiles = 40,
    collar_tiles = 96,
    tip_tiles = 24,
    edge_tiles = 16,
    edge_reach_tiles = 256,
    start = {radius_tiles = 150, margin_tiles = 8},
    ore_clear_tiles = 24,
    band_margin_px = 40,
    band_max_angle_degrees = 60,
    centre_tiles = 0.5,
    switch_threshold = 0.5,
    reset_size = 1,
    max_arguments = 255,
    high = {ref_m = 4800, min_px = 8, gain_px = 42, power = 0.9, rock_tiles = 180, rock_fall = 216, fall_px = 44,
            fall_tiles = 36,
            fray_warp = 0.7, fray_rough = 2, fray_massif = 9, start = {ramp_tiles = 96}},
    ground = {lean = 6, lapse_per_px2 = 0.03, lapse_from_px = 7, cold_t = 30, cold_min = 0.15, floor = -12,
              moisture = 0.2, fray = 2, massif = {gain = 0.04, low = 0.72, high = 1.15}},
    -- The cold field: the released tile reach follows each vertex's height, and heights zigzag along a crest (the Alps:
    -- 4808, 2469, 4634, 2005), so cold ground formed a cone on one vertex, and a threshold across a cone has no minimum
    -- size. Here each crest piece reads one field, 1 on its crest and 0 at its reach, the Entity band's one reach per
    -- piece times fit, max(1, (fit_scale / scale) ^ fit_power), so a piece has a massif or has none, and a massif's
    -- width is a share of its reach at every scale. A piece counts only if its highest vertex clears the snow line at
    -- its latitude less grey_m, and one short of the snow line reaches grey_reach of the way and stops at grey_top,
    -- under snow_at. The snow line is snow_m to snow_lat degrees and falls snow_per_degree past it, to snow_min_m. The
    -- outline is regions.lua's highland_cold: the region layer's warps, wavelength 96 px, with the marsh outline and
    -- roughness. Those only move an edge that sits well inside the field, so they add no specks. Tile temperature is
    -- capped by the field: top_t at its 0, falling to snow_t at snow_at, floor_t past. A cap, not a lapse, so hot and
    -- cool ranges match. The grain's noise is 6 to 48 tiles at every scale, and past fit_scale a field's slope per tile
    -- falls, so its fray would widen with the scale: the fray takes min(1, fit_scale / scale) and keeps its width in
    -- tiles.
    -- The grey rim (0.3.0: the grey round every range was far too wide, and Italy's Apennines and southern
    -- Scandinavia read grey): inside the snow the cap falls as before (top_t at field 0, snow_t at snow_at, so 0 at the
    -- snow edge, field snow_at * top_t / (top_t - snow_t)), but outside it the cap reaches top_t only band times the
    -- ragged factor (climate.ragged) short of that edge and stops binding past it, so the grey ground (Alien Biomes'
    -- T 0 to 30) is a rim of band in field units on average, breaking where the factor is 0 and up to its max times
    -- wider, instead of the whole reach. band_min keeps the division finite. The tile moisture is held in grey dirt's
    -- band only where the cap is under top_t, fully from grey_t, and in proportion to the factor under grey_w, so the
    -- snow's frayed edge meets the ground beside it where the rim breaks (and inside the snow the cap falls up to steep
    -- times faster there, so that fray thins too); under -snow_deep (deep snow) always
    -- (climate.lua). A piece's snow line rises dry_rise_m times the dry weight at the piece (climate.dry_belts): the
    -- Atlas and the Zagros, short of a desert line, had snow islands in a grey sea.
    cold = {fit_scale = 6, fit_power = 0.15, snow_m = 5200, snow_lat = 25, snow_per_degree = 105, snow_min_m = 1200,
            grey_m = 1300, grey_top = 0.3, grey_reach = 0.7, snow_at = 0.66, top_t = 30, snow_t = -8, floor_t = -24,
            fray_warp = 0.012, fray_marsh = 0.12, fray_rough = 0.03, massif = 0.045, high_at = 0.6, off = 1000,
            cap_grain = 0.35, start_fall = 2.2, band = 0.08, band_min = 0.002, grey_t = 20, dry_rise_m = 1500,
            grey_w = 0.3, snow_deep = 3, steep = 5},
    rocks = {gain = 1, gain_ab = 0.4, clear_tiles = 36, fade_tiles = 24, short_px = 40,
             clear_kinds = {pass = true},
             ab_prefixes = {"huge-rock-", "big-rock-", "sand-big-rock-"},
             ab_skip = {"volcanic"}},
    names = {
      high = RDN.RD_HIGH, rock_lift = RDN.RD_ROCK_LIFT, rock_lift_ab = RDN.RD_ROCK_LIFT_AB,
      rise = RDN.RD_RISE, gate = RDN.RD_GATE, lapse = RDN.RD_LAPSE, ground = RDN.RD_GROUND,
      rise_tile = RDN.RD_RISE_TILE, high_tile = RDN.RD_HIGH_TILE,
      cold = {field = RDN.RD_COLD_F, gated = RDN.RD_COLD_GATED, reach = RDN.RD_COLD_REACH, high = RDN.RD_COLD_HIGH,
              cap = RDN.RD_COLD_CAP,
              map = {europe = RDN.EU_COLD, atlantic = RDN.AT_COLD, olde_world = RDN.OW_COLD}},
      -- 0.3.0 (the cold north's second line reads these): the dry pieces' risen snow line and the ragged rim's cap
      cold2 = {field = RDN.RD_COLD_F2, gated = RDN.RD_COLD_GATED2, high = RDN.RD_COLD_HIGH2, cap = RDN.RD_COLD_CAP2,
               map = {europe = RDN.EU_COLD2, atlantic = RDN.AT_COLD2, olde_world = RDN.OW_COLD2}},
      rock_density = RDN.RD_ROCK_DENSITY,
      height = RDN.RD_HEIGHT, free = RDN.RD_FREE,
      cliffiness = RDN.RD_CLIFFINESS,
      clear = RDN.RD_CLEAR,
      band = {europe = RDN.EU_BAND, atlantic = RDN.AT_BAND, olde_world = RDN.OW_BAND},
      wander_u = {europe = RDN.EU_WANDER_U, atlantic = RDN.AT_WANDER_U, olde_world = RDN.OW_WANDER_U},
      wander_v = {europe = RDN.EU_WANDER_V, atlantic = RDN.AT_WANDER_V, olde_world = RDN.OW_WANDER_V},
      run = {europe = RDN.EU_RUN, atlantic = RDN.AT_RUN, olde_world = RDN.OW_RUN},
      keep = {europe = RDN.EU_KEEP, atlantic = RDN.AT_KEEP, olde_world = RDN.OW_KEEP},
    },
    ores = {
      {resource = "iron-ore", key = "entity:iron-ore:probability", name = RDN.ORE_IRON},
      {resource = "copper-ore", key = "entity:copper-ore:probability", name = RDN.ORE_COPPER},
      {resource = "coal", key = "entity:coal:probability", name = RDN.ORE_COAL},
      {resource = "stone", key = "entity:stone:probability", name = RDN.ORE_STONE},
      {resource = "uranium-ore", key = "entity:uranium-ore:probability", name = RDN.ORE_URANIUM},
      {resource = "crude-oil", key = "entity:crude-oil:probability", name = RDN.ORE_OIL},
    },
  },

  -- Resources (ARCHITECTURE.md, "Expression inventory"): the
  -- presets' frequency for the six base resources (planet entries stay neutral), the richness ramp
  -- 1 + gain * clamp((distance - from) / span, 0, 1) on the four solid ores (1.01, 1.09, 1.23
  -- and 1.50 at 512, 1024, 2048 and 4096 tiles, 1.000 inside 450), each Earth ore's wrapper names
  -- (p_v1 is ridges' probability wrapper, which the next version reads), the Oil Rig's offshore-oil
  -- wrappers and the random offshore-oil sea mask: tn_land_coarse below minus threshold_px, the
  -- smallest whole threshold at which no reference river pixel more than 16 px from the sea lies in
  -- the mask on any map.
  resources = {
    -- frequency is 0.75, which the first two hotspot tables' density floors read (their bodies keep it);
    -- preset_frequency is what 0.3.0's presets set on the six controls (at default sliders regular
    -- patches match vanilla's, and frequency changes vanilla's patch count, never a patch)
    frequency = 0.75,
    preset_frequency = 1,
    controls = {"iron-ore", "copper-ore", "coal", "stone", "uranium-ore", "crude-oil"},
    ramp = {name = REN.RAMP, from = 450, span = 3550, gain = 0.5},
    ramped = {"iron-ore", "copper-ore", "coal", "stone"},
    -- r2: 0.3.0's richness wrapper (richness_v2), and p3 its probability wrapper of a solid ore (edge_v1, lombok).
    -- r3 and p4: 0.3.1's, which read the fourth solid bodies (hotspots_v3.bodies) of the third hotspot table.
    ores = {
      {resource = "iron-ore", probability = "entity:iron-ore:probability", richness = "entity:iron-ore:richness",
       p_v1 = RDN.ORE_IRON, p = REN.ORE_IRON_P2, r = REN.ORE_IRON_R, r2 = ORE .. "iron_ore_r_v2",
       p3 = ORE .. "iron_ore_p_v3", r3 = ORE .. "iron_ore_r_v3", p4 = ORE .. "iron_ore_p_v4"},
      {resource = "copper-ore", probability = "entity:copper-ore:probability",
       richness = "entity:copper-ore:richness", p_v1 = RDN.ORE_COPPER, p = REN.ORE_COPPER_P2, r = REN.ORE_COPPER_R,
       r2 = ORE .. "copper_ore_r_v2", p3 = ORE .. "copper_ore_p_v3", r3 = ORE .. "copper_ore_r_v3",
       p4 = ORE .. "copper_ore_p_v4"},
      {resource = "coal", probability = "entity:coal:probability", richness = "entity:coal:richness",
       p_v1 = RDN.ORE_COAL, p = REN.ORE_COAL_P2, r = REN.ORE_COAL_R, r2 = ORE .. "coal_r_v2", p3 = ORE .. "coal_p_v3",
       r3 = ORE .. "coal_r_v3", p4 = ORE .. "coal_p_v4"},
      {resource = "stone", probability = "entity:stone:probability", richness = "entity:stone:richness",
       p_v1 = RDN.ORE_STONE, p = REN.ORE_STONE_P2, r = REN.ORE_STONE_R, r2 = ORE .. "stone_r_v2",
       p3 = ORE .. "stone_p_v3", r3 = ORE .. "stone_r_v3", p4 = ORE .. "stone_p_v4"},
      {resource = "uranium-ore", probability = "entity:uranium-ore:probability",
       richness = "entity:uranium-ore:richness", p_v1 = RDN.ORE_URANIUM, p = REN.ORE_URANIUM_P2, r = REN.ORE_URANIUM_R,
       r2 = ORE .. "uranium_ore_r_v2", p3 = ORE .. "uranium_ore_p_v3", r3 = ORE .. "uranium_ore_r_v3",
       p4 = ORE .. "uranium_ore_p_v4"},
      {resource = "crude-oil", probability = "entity:crude-oil:probability", richness = "entity:crude-oil:richness",
       p_v1 = RDN.ORE_OIL, p = REN.ORE_OIL_P2, r = REN.ORE_OIL_R, r2 = ORE .. "crude_oil_r_v2"},
    },
    -- 0.3.0's richness (new worlds; data-final-fixes.lua ore_wrappers). The game's richness grows with the tiles to the
    -- spawn, (rich_offset + d) / rich_span, with no cap, so past ref_scale a place read ref_scale / scale times as rich
    -- per tile as on the reference map, about 4 times at 24: past ref_scale the wrapper reads the distance as the
    -- reference map has it, so one place holds one richness at 6, 12 and 24. A hotspot's amount grows its area with
    -- that factor and its height only as its cube root, so far out its ore read poorer per tile than the regular ore
    -- round it (half at scale 1, a fifth at 6, a sixteenth at 24, in Indonesia); a solid hotspot ore's richness is
    -- lifted by max(1, lift * F / F_own ^ (1/3)), F the factor (and the ramp, on a ramped ore) at the reference
    -- distance and F_own the one its amount took, so it reads about lift times the regular ore round it. Crude oil's
    -- wells keep their yield.
    -- lombok: Batu Hijau's footprint is wider than the Alas Strait at scales 1 and 2, so that row's copper keeps east
    -- of the strait's middle, lon cut_lon, read on each map's own chain, within reach_px of the row's centre.
    -- edge: a field's outline was a large cone's smooth circle, or its footprint's where cones fill it. u = clamp(mid +
    -- amp * (n1 + half * n2), 0, 1), of two basis noises of wavelengths `long` and `short` tiles (the wobble body),
    -- lowers a solid hotspot ore's value by trim tiles of its cone's least slope times u, so its outline wanders up to
    -- trim tiles inward and its thin rims open into pockets. Lowering the value never moves ore outward, and its
    -- richness stays the hotspot's own where ore remains. A mask on the distance past the nearest footprint read every
    -- row's distance per tile (Entity +3,400) and is not used.
    -- vanilla: regular ore reads the live richness as it is, at the real tile distance
    -- and without the ramp, so a regular patch holds vanilla's ore for its band in real tiles at every scale (the
    -- ref_scale reading left far bands at 0.6 to 0.8 of vanilla's, the ramp put them up to 1.5 times over it); a
    -- solid hotspot's richness is the third hotspot table's (hotspots_v2.v3), which no longer takes the lift.
    richness_v2 = {vanilla = true, ref_scale = 6, rich_offset = 1000, rich_span = 2600, lift = 1.25, cube_root = 1 / 3,
                   lombok = {resource = "copper-ore", row = "copper_sumbawa", row3 = "copper_sumbawa_3",
                             cut_lon = 116.765, reach_px = 70},
                   edge = {wobble = NOISE .. "ore_wobble_v1", seed1 = 7441, trim = 6, mid = 0.5, amp = 0.35, half = 0.5,
                           long = 32, short = 12}},
    -- Trees off a hotspot's solid ore (0.3.0, new worlds; data-final-fixes.lua): forest stood on whole coal fields
    -- (27,003 trees on East Kalimantan's at scale 6), and dark coal under it read as forest at player height; with the
    -- trees gone, flowers and grass still hid it. Every tree's probability takes the zone exclusion's hook
    -- (prototypes/zone_exclusion.lua) on `key`, whose prototype holds 0 and which new presets name tn_one, times
    -- `open`: clamp(-v / margin, floor, 1) with v the largest solid hotspot body, so trees thin over about margin / 900
    -- tiles toward the ore and floor of them stand on it. Every plant but the kinds plants.keep names takes the same
    -- hook times plants.open, clamp(-v / plants.margin, plants.floor, 1): a share stays on the ore and none goes off
    -- it, since a bare band round the ore and an ore field with no plants at all both showed a cone field's long
    -- straight edges. open_v2 and plants.open_v2 read v less the outline wobble the ore's probability takes
    -- (richness_v2.edge), so trees and plants thin where ore stands and not where the wobble took it away: v1 left a
    -- bare band up to trim tiles wide beside Grasberg's copper at scale 24. Presets name the v2 bodies in the v1 names'
    -- place, so a world made with v1 keeps it.
    ore_trees = {key = NOISE .. "ore_trees", open = NOISE .. "ore_open_v1", open_v2 = NOISE .. "ore_open_v2",
                 margin = 2500, floor = 0.08,
                 open_v3 = NOISE .. "ore_open_v3",
                 plants = {open = NOISE .. "ore_open_plants_v1", open_v2 = NOISE .. "ore_open_plants_v2",
                           open_v3 = NOISE .. "ore_open_plants_v3", margin = 300,
                           floor = 0.35,
                           keep = {"rock", "decal", "crater", "puddle", "stone"}, drop = {}}},
    offshore = {resource = "offshore-oil", probability = "entity:offshore-oil:probability",
                richness = "entity:offshore-oil:richness", p = REN.OFFSHORE_P, r = REN.OFFSHORE_R},
    sea = {name = REN.SEA, threshold_px = 7},
    -- Natural regular patches (with RSO off these are the ore a player sees all
    -- game, and round equal discs on an even spacing read as computer-made). Every Earth preset redirects
    -- each live patch expression in `bodies` to an Earth copy of it that calls `fn`, a copy of `vanilla_fn`,
    -- so no resource prototype and no default world changes, and the pack's own patch parameters and
    -- patch set count stay live. The copy differs from vanilla in five ways:
    --   size      a spot's size is size.floor + size.gain * u ^ size.power of the typical quantity, u
    --             uniform: mean 1 / 1.7, so about 1.7 times vanilla's spots, a few large among many small
    --   radius    the typical spot's radius times sqrt(size), capped at radius_cap, so every spot has one
    --             height, ore area follows ore amount, and noise moves an outline by a share of that spot's
    --             own radius (vanilla's cones share a slope: the same noise swamps a small spot); an ore
    --             whose vanilla spot size is fixed (crude oil) takes fixed_radius of it, since its amount
    --             counts wells and the outline noise grows a field's area
    --   province  candidates are taken best first on a low-frequency noise of `wavelength` tiles, shifted
    --             per ore by `offset`, so ore gathers in provinces instead of an even spacing
    --   outline   weights of the octaves added to the spot, in vanilla's blob amplitude, capped at `cap` so a
    --             spot's reach is bounded; `vary` lets the coarse octave scale the rest patch by patch, and
    --             `warp` moves the spots' coordinates by the 64 and coarse octaves. The starting patches read
    --             the same octaves at start_w64 and start_coarse and the same rim, so the first ore a player
    --             meets is as uneven as the rest; those weights stay low because an octave wider than a start
    --             patch raises or sinks the whole patch, which is unfair, and start_level takes back what the rim
    --             adds to a start's amount. `basement` deepens vanilla's basement
    --   rim       near a patch's edge, within rim.width of the height either side, blobs0 is added at rim.gain
    --             falling to 0, so edges fray into islets and satellites and neither the interior nor the far
    --             field moves; a tile with ore lies within `reach` of a spot's radius
    --   richness  v / (1 + plateau * v / height), v the field, height the typical spot's: a plateau instead of
    --             a cone, times 1 + pockets * blobs0 with blobs0 clamped so the factor stays positive (below
    --             zero it turns the far field's basement into ore), and `level` holds the budget; level_few
    --             is the same for an ore of a mean spot size over 2 (uranium), whose few spots per region
    --             overshoot the target less once they are smaller
    -- Regular ore stays out of hotspot footprints: a candidate keeps its quantity only where `gap` (tiles from
    -- the nearest footprint on the map) exceeds reach times its radius plus the warp's most.
    natural = {
      fn = REN.ORE_FN,
      vanilla_fn = "resource_autoplace_all_patches",
      gap = REN.ORE_GAP,
      no_gap = 1000000,
      size = {floor = 0.25, gain = 1.35, power = 3, radius_cap = 40, fixed_radius = 0.94},
      province = {seed1 = 7405, wavelength = 320, offset = 4096, base = 2},
      outline = {coarse = {seed1 = 7406, wavelength = 128}, fine = 8, mid = 24, broad = 64, w24 = 2, w64 = 4,
                 w128 = 3.5, mean = 1 / 3, vary = 0.3, cap = 8, start_w64 = 1.5, start_coarse = 0.5, start_mean = 0.25,
                 start_level = 0.75,
                 basement = 4},
      -- vanilla's own regular spot_noise numbers (core/prototypes/noise-functions.lua), and how far blobs0 may
      -- move the pockets
      spot = {region_size = 1024, spacing = 45.254833995939045, basement_radius = 128, cube_root = 1 / 3},
      pocket_clamp = 2,
      warp = {amplitude = 12},
      plateau = 2,
      pockets = 0.35,
      level = 0.92,
      level_few = 1.3,
      few_size = 2,
      reach = 2.5,
      warp_reach = 22,
      rim = {width = 0.5, gain = 5},
      -- 0.3.0: the shape terms above spread a patch over about 1.25 times
      -- vanilla's tiles and 1.45 times its span, and the spot sizes add a tail of merged clusters, so ordinary
      -- patches read huge in game while holding 0.3 to 0.8 of vanilla's ore. New presets point each live patch
      -- expression at body2, which calls fn2: vanilla's function as the game ships it, and nothing more than
      -- this map's one rule, that regular ore keeps out of every hotspot footprint (`gap` over gap_reach times the
      -- largest spot's radius vanilla allows there; a cleared candidate carries nothing and ranks last, so the
      -- region's ore goes to the candidates outside). With hotspots off it is vanilla's function to the tile.
      fn2 = ORE .. "all_patches_v2",
      gap_reach = 2,
      -- vanilla's spot radius cap and cube root, and the two texts of its regular spot noise fn2 swaps (a cleared
      -- candidate ranks last and takes a radius of 1: a spot of no quantity and no radius is not one the game makes)
      gap_radius = {cap = 32, cube_root = "1 / 3"},
      -- flat (far ore grew too much, and hotspots stay what players seek out): regular ore
      -- reads the distance d' = min(d, knee) + rate * clamp(d - knee, 0, stop - knee), so out to knee tiles it is
      -- as before, and past it a patch's richness and size grow at rate times vanilla's pace and stop at `stop`
      -- (real tiles from the spawn at every scale). fn2 keeps vanilla's density and spot quantities at the real
      -- distance, so every regular spot stays where it was: the spots' output takes vanilla's quantity growth at
      -- d' over that at d, the blob reads d', and the richness wrapper (richness_v2) takes vanilla's richness
      -- factor at d' over that at d. Hotspots read prototypes/ore_curves.lua at the real distance, unchanged.
      flat = {knee = 1000, rate = 0.5, stop = 4000},
      -- the keep each body passes fn2 (resources.scarcity); the offshore oil body passes 1
      keep_param = "scarcity_keep",
      density_old = "density_expression = regular_density_at(distance),",
      density_new = "density_expression = scarcity_keep * regular_density_at(distance),",
      -- and, since a region places its first spot whatever its target (measured: a density of 0 left uranium and
      -- oil as they were), the spots' quantity too: a dropped region's one spot carries nothing, at radius 1 as a
      -- cleared candidate does, and is the candidate nearest the region's centre (its favourability), so the flat 0
      -- such a spot leaves out to maximum_spot_basement_radius stays clear of every other region's spots; where the
      -- spots read exactly 0 with scarcity on (on_param), the blob may only lower the field, so no speck of ore
      -- grows out of that flat 0
      on_param = "scarcity_on",
      quantity_old = "clear * (",
      quantity_new = "clear * scarcity_keep * (",
      radius_old = "max(1 - clear,",
      radius_new = "max(1 - clear * scarcity_keep,",
      favour_old = "spot_favorability_expression = clear,",
      favour_new = "spot_favorability_expression = clear * (scarcity_keep + (1 - scarcity_keep) * " ..
        "(1 - sqrt((x - region_mid_x) ^ 2 + (y - region_mid_y) ^ 2) / 1024)),",
      split_at = "maximum_spot_basement_radius = 128}",
      split_join = " + ",
      fn2_swaps = {
        {old = "spot_favorability_expression = 1,", new = "spot_favorability_expression = clear,"},
        {old = "spot_radius_expression = min(32, regular_rq_factor * regular_spot_quantity_expression ^ (1/3)),",
         new = "spot_radius_expression = max(1 - clear, min(32, regular_rq_factor * " ..
           "regular_spot_quantity_expression ^ (1/3))),"},
      },
      bodies = {
        {live = "default-iron-ore-patches", scarcity = "iron-ore",
         name = REN.ORE_PATCH_IRON, name2 = ORE .. "iron_ore_patches_v2"},
        {live = "default-copper-ore-patches", scarcity = "copper-ore",
         name = REN.ORE_PATCH_COPPER, name2 = ORE .. "copper_ore_patches_v2"},
        {live = "default-coal-patches", scarcity = "coal",
         name = REN.ORE_PATCH_COAL, name2 = ORE .. "coal_patches_v2"},
        {live = "default-stone-patches", scarcity = "stone",
         name = REN.ORE_PATCH_STONE, name2 = ORE .. "stone_patches_v2"},
        {live = "default-uranium-ore-patches", scarcity = "uranium-ore",
         name = REN.ORE_PATCH_URANIUM, name2 = ORE .. "uranium_ore_patches_v2"},
        {live = "default-crude-oil-patches", scarcity = "crude-oil",
         name = REN.ORE_PATCH_OIL, name2 = ORE .. "crude_oil_patches_v2"},
        {live = "default-offshore-oil-patches", name = REN.ORE_PATCH_OFFSHORE,
         name2 = ORE .. "offshore_oil_patches_v2"},
      },
    },
    -- Regional scarcity (0.3.0): regular ore thins out away from its real regions past the start. Hotspots become
    -- destinations a long game needs. Outside a resource's provinces, a share `medium` or `strong` of its regular
    -- patches stays (the setting's level, tn_scarcity: 0 off, 1 medium, 2 strong); inside them, and inside
    -- ramp.from * scale tiles of the spawn, all of them. The keep multiplies fn2's regular spot density alone, so the
    -- spot quantities, radii and favourabilities stay vanilla's and the spots a region keeps are the first ones its
    -- Off world takes, in the same places and at the same size: whole patches drop out. The keep is 0 or 1 per spot
    -- region (vanilla's 1,024 tile squares, region_size, centred on its multiples: measured from the Off world's one
    -- uranium spot per region). A region places its first spot whatever its target, so the keep zeroes the spots'
    -- quantity too (resources.natural.quantity_new). The draw is per region and resource (a sine hash of the
    -- region's index, the resource's seed and map_seed_small; random_penalty with a region's constant x and y was
    -- measured to vary inside the region); the bar is 1 - (1 - share) * ramp * (1 - province), the ramp read at
    -- the region's nearest point to the spawn (plus margin tiles, a spot's reach), so a region touching the near
    -- disc keeps everything. Provinces: per resource the soft union of discs around its hotspot rows on the map
    -- (hotspot_rows_v2: real deposits), reach_px past each footprint, the edge moved by a ragged noise (rag) and soft
    -- over a width that varies from 0 (a hard edge) to about wide.px (NO PERFECT BANDS). No raster is read.
    scarcity = {
      key = REN.K_SCARCITY,
      setting = "regional_scarcity",
      levels = {off = 0, medium = 1, strong = 2},
      shares = {
        ["uranium-ore"] = {medium = 0.20, strong = 0.08},
        ["crude-oil"] = {medium = 0.35, strong = 0.15},
        ["copper-ore"] = {medium = 0.50, strong = 0.30},
        ["iron-ore"] = {medium = 0.65, strong = 0.40},
        ["coal"] = {medium = 0.75, strong = 0.55},
        ["stone"] = {medium = 0.95, strong = 0.80},
      },
      names = {
        ["iron-ore"] = {province = ORE .. "province_iron_ore_v1", keep = ORE .. "keep_iron_ore_v1", seed = 7411},
        ["copper-ore"] = {province = ORE .. "province_copper_ore_v1", keep = ORE .. "keep_copper_ore_v1", seed = 7412},
        ["coal"] = {province = ORE .. "province_coal_v1", keep = ORE .. "keep_coal_v1", seed = 7413},
        ["stone"] = {province = ORE .. "province_stone_v1", keep = ORE .. "keep_stone_v1", seed = 7414},
        ["uranium-ore"] = {province = ORE .. "province_uranium_ore_v1", keep = ORE .. "keep_uranium_ore_v1",
                           seed = 7415},
        ["crude-oil"] = {province = ORE .. "province_crude_oil_v1", keep = ORE .. "keep_crude_oil_v1", seed = 7416},
      },
      -- tiles per unit of scale: full keep inside from, the full share from full (1,500 and 3,000 at scale 12)
      ramp = {from = 125, full = 250, margin = 64},
      region = 1024,
      hash = {a = 12.9898, b = 78.233, seed_gain = 0.0137, gain = 43758.5453},
      reach_px = 60,
      rag = {px = 24, wavelength_px = 90, seed1 = 7421},
      wide = {px = 36, base = 0.3, gain = 0.9, wavelength_px = 70, seed1 = 7422},
      no_gap = 1000000,
    },
  },

  -- Hotspots (with a shared blob; design rules 8 and 16). The
  -- rows are prototypes/tables/hotspots.lua (tools/build_hotspots.py writes it from its source data):
  -- each row's disc is the region layer's row of the same id, jittered per seed there. At scale s a
  -- row's footprint radius is R = min(max(r * s, floor_tiles), cap * s) tiles (r its radius and cap
  -- r + 50 km, both in reference pixels: a floor at small scales, capped where it would
  -- pass the city-removal distance), read through the region layer's depth, so the footprint is the
  -- disc's roughened distance under R:
  --   core_share   spots start at land candidates inside a row's start disc, core_share of R (the
  --              reference design had core 112 of a 160-tile disc; here 0.75, so the smallest holds
  --              about 4 candidates at scale 1) and at most the disc holding spot.max_spots
  --              candidates, and reach at most the
  --              rest of R, so ore stays inside R
  --   enemy_share   extra bases start inside this share of R (the reference design: 40 tiles inside a
  --              160-tile disc)
  --   patches    the reference design's spots per hotspot (4 of 5 M): the blob's reference spot height only
  --   land_px, sea_px   a candidate is land where tn_land_coarse is above land_px, and sea (offshore
  --              rows) where it is below minus sea_px (design rule 8: the one land field outside Tile); the
  --              coarse field's zero contour runs inland of narrow coasts, so the land gate sits 4 px
  --              seaward of it (an offline probe of every adopted core at scales 1 and 6: at 0, 22
  --              cores pass under 0.6 of their reference land, Pentelicus none of it; at -4 none)
  --   land_grade_px   favourability rises over this many px of tn_land_coarse past the gate, so a
  --              region places its most inland candidates first
  --   spot       one spot_noise per resource, each with its own seed1, region_size tiles, its
  --              candidates per region (candidates_fine at scales up to fine_scale, where footprints
  --              are smallest, so even the smallest core holds several candidates), at most max_spots
  --              per row, and a hard region target equal to the sum of its land candidates' quantities,
  --              so every one is placed and rows of a resource sharing a region never draw on each
  --              other's target (a shared target let Marmara's candidates take all of Pentelicus' and
  --              Kryvbas' all of Kursk's on one Europe seed at scale 1); a region places its most
  --              inland candidates first
  --   target     a row's amount: strength * share * per_km2 / spots_per_km2 * base_density * mean_size *
  --              size * f(d) * ramp(d) with f vanilla's patch quantity and richness factor at the
  --              candidate's distance d (core/prototypes/noise-functions.lua:205-207, 264-280;
  --              core/lualib/resource-autoplace.lua:115-120), share the disc's land share (water share
  --              for offshore rows) from the raster (design rule 16); reference_strength and
  --              reference_factor give the blob's typical spot height; density_floor raises a large
  --              footprint's amount to that many times vanilla's mean amount per tile over its area
  --              (base_density times frequency, the lowest measured ratio 15), so a disc of hundreds
  --              of tiles at scale 6 still holds the density the ore checks ask (Kursk at strength 3 held 4.95
  --              times vanilla's mean over its 243-tile footprint without it)
  --   blob       the shared texture on every spot: three basis noises, added as
  --              (blob - mean) * height / divisor where a spot is positive
  --   resources  per resource its seed1, vanilla's base_density, spots per km2, rq factor and mean
  --              random spot size (base/prototypes/entity/resources.lua; for offshore oil the values of
  --              Cargo Ships: Oil Rig's own offshore-oil, so the fields match that mod's wells; NOTICE.txt),
  --              fluids their well penalty and additional richness, sea for offshore fields
  hotspots = {
    floor_tiles = 48,
    amount_percent = 100,
    -- A row gives way to each smaller row of another ore whose disc can touch its own at some scale and seed
    -- (cap radius plus the halved jitter, on a shared map): those are its rivals, and its cones keep out of
    -- them, so different ores never interleave. Five pairs out of the 77 rows; a table edit that moves a row
    -- needs this list checked.
    rivals = {
      coal_donbas = {"iron_kursk_magnetic_anomaly"},
      coal_south_wales = {"stone_portland"},
      oil_baku_absheron = {"offshore_caspian_acg"},
      oil_basra_kuwait = {"offshore_safaniya"},
      oil_niger_delta = {"offshore_nigeria_deepwater"},
    },
    core_share = 0.75,
    enemy_share = 0.75,
    patches = 4,
    land_px = -4,
    sea_px = 0,
    land_grade_px = 8,
    spot = {region_size = 512, candidates = 512, candidates_fine = 1024, fine_scale = 1, spacing = 16,
            spacing_fine = 8, max_spots = 32, basement = -100000, basement_radius = 128, min_radius = 1,
            min_room = 3, cube_root = 1 / 3, cone_factor = 3},
    target = {fade_from = 150, fade_span = 300, double_from = 300, double_span = 1300, rich_offset = 1000,
              rich_span = 2600, per_km2 = 1000000, reference_strength = 2, reference_factor = 2,
              density_floor = 15},
    -- A row's bodies of ore (equal round spots on a blue-noise grid read as polka
    -- dots): half the candidates carry nothing and the rest share the amount by a squared uniform, so a
    -- few large bodies stand among small ones; mean 1 over all candidates, so a row's amount holds on
    -- average. The blob reaches past each cone's rim, which is what lets an outline leave the circle, but
    -- never past the footprint (a hard rule at every scale, seed and amount): blob.cap bounds
    -- the blob's rise, and a cone's slope is at least cone_factor / (pi * rq ^ 3) once its quantity holds a
    -- spot of min_radius, so a tile with ore lies within the cone's radius plus cap * height / divisor over
    -- that slope. A candidate's radius is held to its room: the row's disc less that reach, and less any rival
    -- row a different ore's spots must keep out of (tn_pd_ reads the plain distance to a row's jittered
    -- centre). A hotspot row's disc takes no edge roughness, so its footprint is exact.
    size = {keep = 0.5, power = 2, gain = 6},
    blob = {name = REN.HS_BLOB, seed1 = 7302, mean = 1 / 3, divisor = 3.5, cap = 2,
            octaves = {{input_scale = 1 / 8, output_scale = 1}, {input_scale = 1 / 24, output_scale = 1},
                       {input_scale = 1 / 64, output_scale = 1.5}}},
    resources = {
      {resource = "iron-ore", seed1 = 7301, base_density = 10, spots_per_km2 = 2.5, rq = 0.11, mean_size = 1.125,
       names = {v = REN.HS_IRON, p = REN.HS_IRON_P, r = REN.HS_IRON_R}},
      {resource = "copper-ore", seed1 = 7311, base_density = 8, spots_per_km2 = 2.5, rq = 0.11, mean_size = 1.125,
       names = {v = REN.HS_COPPER, p = REN.HS_COPPER_P, r = REN.HS_COPPER_R}},
      {resource = "coal", seed1 = 7321, base_density = 8, spots_per_km2 = 2.5, rq = 0.1, mean_size = 1.125,
       names = {v = REN.HS_COAL, p = REN.HS_COAL_P, r = REN.HS_COAL_R}},
      {resource = "stone", seed1 = 7331, base_density = 4, spots_per_km2 = 2.5, rq = 0.1, mean_size = 1.125,
       names = {v = REN.HS_STONE, p = REN.HS_STONE_P, r = REN.HS_STONE_R}},
      {resource = "uranium-ore", seed1 = 7341, base_density = 0.9, spots_per_km2 = 1.25, rq = 0.1, mean_size = 3,
       names = {v = REN.HS_URANIUM, p = REN.HS_URANIUM_P, r = REN.HS_URANIUM_R}},
      {resource = "crude-oil", seed1 = 7351, base_density = 8.2, spots_per_km2 = 1.8, rq = 0.1, mean_size = 1,
       fluid = {penalty = 48, additional = 220000, seed = 7352},
       names = {v = REN.HS_OIL, p = REN.HS_OIL_P, r = REN.HS_OIL_R}},
      {resource = "offshore-oil", seed1 = 7361, base_density = 10, spots_per_km2 = 1.8, rq = 0.1, mean_size = 3.5,
       fluid = {penalty = 100, additional = 350000, seed = 7362}, sea = true,
       names = {v = REN.HS_OFFSHORE, p = REN.HS_OFFSHORE_P, r = REN.HS_OFFSHORE_R}},
    },
  },

  -- The second hotspot table (ARCHITECTURE.md, "Release versioning policy", rule 14): rows from
  -- data-src/hotspots/hotspots-v2.json, every one resting on data-src/hotspots/deposits-research.md, over what
  -- the first table keeps (prototypes/hotspot_rows_v2.lua). `points` is what a new world's preset names in the
  -- first table's place: a released name to a body of this table, which never reads that name, so a world keeps
  -- the table it was made on. A footprint of R tiles over spread_from holds base_bodies + R / tiles_per_body ore
  -- bodies across core_share of R; where a row keeps few of its candidates (its bar over lobe.above), lobe moves the
  -- bar by gain times a noise, so its bodies gather; size is the first table's, a few large among many small. Up
  -- to spread_from a row is built as the first table builds it. A row's strength over strength_top lifts the
  -- density floor by strength over strength_top, so rank reaches a wide footprint; few_bodies is for the fine scale.
  -- A row may carry least_tiles, the least its ore footprint reaches in tiles at any scale (tools/build_hotspots.py).
  hotspots_v2 = {
    enemy_layer = NOISE .. "enemy_layer_v2",
    gap = NOISE .. "ore_gap_v2",
    bodies = {["iron-ore"] = HS .. "iron_ore_v2", ["copper-ore"] = HS .. "copper_ore_v2", coal = HS .. "coal_v2",
              stone = HS .. "stone_v2", ["uranium-ore"] = HS .. "uranium_ore_v2", ["crude-oil"] = HS .. "crude_oil_v2"},
    -- each resource's quantity and bars stand in bodies of their own (expressions/hotspots_v2.lua row_locals)
    parts = {["iron-ore"] = {qty = HS .. "iron_ore_qty_v2", bars = HS .. "iron_ore_bars_v2"},
             ["copper-ore"] = {qty = HS .. "copper_ore_qty_v2", bars = HS .. "copper_ore_bars_v2"},
             coal = {qty = HS .. "coal_qty_v2", bars = HS .. "coal_bars_v2"},
             stone = {qty = HS .. "stone_qty_v2", bars = HS .. "stone_bars_v2"},
             ["uranium-ore"] = {qty = HS .. "uranium_ore_qty_v2", bars = HS .. "uranium_ore_bars_v2"},
             ["crude-oil"] = {qty = HS .. "crude_oil_qty_v2", bars = HS .. "crude_oil_bars_v2"}},
    -- 0.3.0's presets name the third table's solid bodies (v3 below) in the first table's place; crude oil keeps v2
    points = {[REN.HS_IRON] = HS .. "iron_ore_v3", [REN.HS_COPPER] = HS .. "copper_ore_v3",
              [REN.HS_COAL] = HS .. "coal_v3", [REN.HS_STONE] = HS .. "stone_v3",
              [REN.HS_URANIUM] = HS .. "uranium_ore_v3",
              [REN.HS_OIL] = HS .. "crude_oil_v2", [REN.ORE_GAP] = NOISE .. "ore_gap_v2",
              [REN.ENEMY_LAYER] = NOISE .. "enemy_layer_v2"},
    -- The solid ores' third version (0.3.0, new worlds). The
    -- second table's amount grew with the footprint's area and the distance, and the richness wrapper lifted it
    -- again, so a field held 10 M (the Ore Mountains) to 2.1 billion (Kiruna) at scale 12, 1.6 to 3.7 times the
    -- regular ore round it per tile at amount 200. Here, per resource and in real tiles d to the spawn:
    --   L(d) = p90 * size_max * Q(min(d, cap_distance)) * f(min(d, cap_distance)), vanilla's large (p90) regular
    --          patch: Q vanilla's regular spot quantity, its fade in, double density and size slider, f vanilla's
    --          richness distance factor, p90 fitted per ore on a measured vanilla baseline; cap_distance holds a
    --          world-class (K 6) iron field at about 100 M, the design ceiling, so every total stays in tens of
    --          millions
    --   P(d) = per_tile_fit * q / (pi * r^2) * f(d), vanilla's mean regular ore per tile, q = mean_size * Q(d),
    --          r = min(radius_cap, rq * q^(1/3)) its typical spot
    --   a row's total is K * amount * L(d), K by its strength (k), its ore per tile per_tile * P(d) times the
    --   richness slider, so it reads per_tile times the regular ore round it, and the rest is area: the row
    --   carries W = area_fit * K * amount * L(d) / (per_tile * P(d) * body_tiles) bodies' worth (at most top_share
    --   of its start disc's candidates), each body a cone of body_tiles tiles on average (size: gain * k^power of a
    --   uniform k, mean 1): every candidate in the start disc offers one, and the region's target, the row's W
    --   bodies' worth, takes them in the order order_base + a draw - lobe_gain * lobe sets until it is reached, so
    --   a field holds its design wherever its draws fall, its bodies gather where the lobe is low and the last one
    --   is cut to fit (dealing bodies by a draw against a share held one field to a third of its design and another
    --   to three times it in test runs); the
    --   richness wrapper sets a tile to rich_fit * per_tile * P(d) * min(v, peak_cap * h) / h, h the mean height
    --   of a body_tiles cone, so a larger body reads richer, as vanilla's do. area_fit and rich_fit take back what the
    --   outline wobble, the blob and the room trim from a cone (measured). The sliders reach it as
    --   they reach vanilla's patches (size: Q; richness: per tile), the amount setting as more bodies, and
    --   frequency not at all. Footprints, rows, rivals, the blob, the lobes' noise, the gap and the nests are the
    --   second table's.
    v3 = {
      bodies = {["iron-ore"] = HS .. "iron_ore_v3", ["copper-ore"] = HS .. "copper_ore_v3", coal = HS .. "coal_v3",
                stone = HS .. "stone_v3", ["uranium-ore"] = HS .. "uranium_ore_v3"},
      parts = {["iron-ore"] = {qty = HS .. "iron_ore_qty_v3"}, ["copper-ore"] = {qty = HS .. "copper_ore_qty_v3"},
               coal = {qty = HS .. "coal_qty_v3"}, stone = {qty = HS .. "stone_qty_v3"},
               ["uranium-ore"] = {qty = HS .. "uranium_ore_qty_v3"}},
      k = {[1] = 3, [2] = 3, [3] = 4, [4] = 5, [5] = 6},
      cap_distance = 2000,
      size_max = {["iron-ore"] = 2, ["copper-ore"] = 2, coal = 2, stone = 2, ["uranium-ore"] = 4},
      p90 = {["iron-ore"] = 0.9, ["copper-ore"] = 0.93, coal = 0.92, stone = 0.92, ["uranium-ore"] = 1.05},
      per_tile_fit = 1.05,
      per_tile = 1.75,
      -- past where per_tile times vanilla's P(d) passes flat_ratio times the flattened regular ore per tile
      -- (resources.natural.flat), a field's per tile is held there and its total spreads over more tiles
      -- (ore_curves.lua per_tile; never tiny rich bodies); 2.2 reads 2.1 to 2.7 times the regular ore
      -- in game (the design's P is the typical spot's, a little under a measured patch's mean)
      flat_ratio = 2.2,
      -- far fields at full body size held 1.12 times the cap tip's totals: their area reads flat_fit less
      flat_fit = 0.9,
      radius_cap = 32,
      quantity = {per_km2 = 1000000, fade_from = 150, fade_span = 300, double_from = 300, double_span = 1300},
      body_tiles = 600,
      size = {gain = 2.5, power = 1.5, seed = 1},
      order_base = 2,
      lobe_gain = 0.5,
      -- a tile reads at most peak_cap times a body_tiles cone's mean height, so crowded bodies in a small footprint
      -- (Carrara) do not stack into ore several times the design's per tile
      peak_cap = 4,
      -- the shared blob at blob_scale of the second table's height, and the outline wobble's trim in tiles (p3 and
      -- the tree shares read it for these bodies): at full height and 6 tiles they ate most of a body_tiles cone
      blob_scale = 0.5,
      trim = 3,
      -- the outline's grain (Kiruna's edge read blocky): a body is a cone plus the shared blob, whose
      -- finest wave is 8 tiles, so its outline was a smooth curve and its digitized sides ran straight for 8 to 15
      -- tiles (Kiruna at 12; with the blob off a body is a plain circle). One more basis
      -- wave of `wavelength` tiles at `output` of the blob's, under the same height, roughens the outline as vanilla's
      -- patches are rough: at 0.6 the three fields' straight runs fell to vanilla's rate and their ore held 1.01 to
      -- 1.02; at 1.2 every field shed 10 to 14 fragments
      grain = {seed1 = 7445, wavelength = 4, output = 0.6},
      -- far fields: past about 10,000 tiles at scale 12 a design asks for under one or
      -- two body_tiles cones (vanilla's ore per tile grows with distance, the total is held), so a field was one or
      -- two whole bodies of a drawn size and held 0.03 to 2.9 times its design (33 over 100 M, 21 under half). Where
      -- a strength-k_ref row would hold under `bodies` cones, every body's tiles scale by f = k_ref * W1 / bodies
      -- (ore_curves.lua body_scale, W1 the cones one unit of k asks for, never under `least`): its quantity by
      -- f ^ 1.5, its height by f ^ 0.5 (the richness wrapper divides by it, so ore per tile stays the design's), the
      -- blob under it by f ^ blob_power (the blob's waves do not shrink with the body), the outline trim by f ^ 0.5,
      -- and its size draw narrows to `size` (one large draw set a field's total). So a world-class far field is about
      -- `bodies` large bodies and a strength-3 one about half that. A small disc whose candidates cannot hold that
      -- many takes fewer, larger ones (hotspots_v2.lua fr). Far bodies lose less to the blob and the trim than the
      -- near ones area_fit was fitted on: `fit` takes that back, ramped in below f = fit_from. A row's design total is
      -- held to total_cap by its K: each is the 100 M ceiling over the worst total /
      -- design its K reached at scales 6 and 12 (K 3 1.95, K 4 1.75, K 5 1.35, K 6 1.26), less 8 percent,
      -- so no field passes 100 M at amount 100; the amount setting multiplies it.
      far = {bodies = 5, k_ref = 6, least = 0.06, blob_power = 1, fit = 0.91, fit_from = 0.7,
             total_cap = {[3] = 46000000, [4] = 52000000, [5] = 68000000, [6] = 73000000},
             size = {gain = 1.5, power = 0.5}},
      area_fit = 1.65,
      rich_fit = 0.74,
      cube_root = 1 / 3,
      body_power = 3 / 2,
    },
    core_share = 0.75,
    spread_from = 120,
    few_bodies = 5,
    base_bodies = 8,
    tiles_per_body = 14,
    strength_top = 3,
    top_share = 0.5,
    min_gap = 0.01,
    size = {gain = 3, power = 2},
    lobe = {name = HS .. "lobe_v2", seed1 = 7371, wavelength = 96, from_scale = 6, gain = 0.5, above = 0.5},
    -- Nests over a footprint (expressions/enemies.lua, whose head says why). A tile holds a cluster where
    --   min(spot, level) + lobe * lobe noise + grain octaves + bonuses > offset
    -- so the lobe noise that gathers ore bodies holds nests off them from full_scale up, and at a small map, whose
    -- footprints are narrower than a lobe, small_map stands in for it. near holds clusters round a start, where cones
    -- are few; capped follows a mod's cap on the enemy radius (bobenemies'), so a capped pack keeps fewer nests, as it
    -- does outside a footprint; radius is vanilla's enemy_base_radius, to read that cap by. height is under the 0.25 at
    -- which spawners lock into rows. clear keeps oil rows' wells free. spots: more cones past spots_from, so they cover
    -- a footprint and the live bases are gone from it.
    nests = {wrapper = NOISE .. "enemy_v2", outside = -1000000, spots = 2, spots_from = 600, spots_span = 1800,
             level = 0.3, lobe = 0.55, full_scale = 6, grain = {0.2, 0.3, 0.6}, offset = 0.66, small_map = 0.2,
             near = 0.4, full_distance = 2400, capped = 1, radius = {base = 15, gain = 4, span = 325}, height = 0.16,
             clear = 10},
  },

  -- The third hotspot table (0.3.1, new worlds; tables/hotspots_v3.lua; release versioning rule 14): the
  -- rows of the first two tables whose discs stood in the sea or a lake, moved onto land under new ids (Marmara,
  -- Portland, Sumbawa, Aswan), and for small discs `rich`, the factor on a row's ore per tile (up to 3) that lets the
  -- disc hold its design total in the room it has. Everything of the second table's solid method (hotspots_v2.v3)
  -- is read as it is; only the rows differ, so the solid ores' fourth bodies, the gap, the enemy layer and nests, the
  -- trees' shares and the probability and richness wrappers stand under new names, which 0.3.1's presets name in
  -- their place (`points`; data-final-fixes.lua names the wrappers and the shares). A world made before keeps the
  -- bodies it was made on. rich_body is the per-ore body of the factor: 1 outside a factored row's footprint.
  hotspots_v3 = {
    enemy_layer = NOISE .. "enemy_layer_v3",
    gap = NOISE .. "ore_gap_v3",
    nests = NOISE .. "enemy_v4",
    scatter = NOISE .. "enemy_v5",
    bodies = {["iron-ore"] = HS .. "iron_ore_v4", ["copper-ore"] = HS .. "copper_ore_v4", coal = HS .. "coal_v4",
              stone = HS .. "stone_v4", ["uranium-ore"] = HS .. "uranium_ore_v4"},
    parts = {["iron-ore"] = {qty = HS .. "iron_ore_qty_v4"}, ["copper-ore"] = {qty = HS .. "copper_ore_qty_v4"},
             coal = {qty = HS .. "coal_qty_v4"}, stone = {qty = HS .. "stone_qty_v4"},
             ["uranium-ore"] = {qty = HS .. "uranium_ore_qty_v4"}},
    rich_body = {stone = HS .. "stone_rich_v1"},
    points = {[REN.HS_IRON] = HS .. "iron_ore_v4", [REN.HS_COPPER] = HS .. "copper_ore_v4",
              [REN.HS_COAL] = HS .. "coal_v4", [REN.HS_STONE] = HS .. "stone_v4",
              [REN.HS_URANIUM] = HS .. "uranium_ore_v4", [REN.ORE_GAP] = NOISE .. "ore_gap_v3",
              [REN.ENEMY_LAYER] = NOISE .. "enemy_layer_v3"},
  },

  -- The offshore field stamps: each map's body is
  -- stamp_elevation inside every adopted offshore row's footprint grown by cover_px (the region
  -- layer's edge roughness plus a well's box), else 0, and the map's newer elevation entry takes
  -- min(elevation, stamp) where the ground is already water, so every well the Entity program places
  -- inside the footprint stands on deepwater. A row's centre is the region layer's jittered centre
  -- moved onto the map's own chain by the map's whole-pixel frame offset (hotspots.lua). -6 is
  -- deepwater with and without Alien Biomes.
  fields = {
    stamp_elevation = -6,
    cover_px = 4,
    names = {europe = REN.EU_FIELDS, atlantic = REN.AT_FIELDS, olde_world = REN.OW_FIELDS},
  },

  -- The enemy layer: a second spot_noise built like
  -- vanilla's enemy_base_probability (base/prototypes/noise-expressions.lua:19-50) in its own seed1,
  -- density (mult - 1) times vanilla's at candidates inside enemy_share of a hotspot footprint, on land,
  -- active only beyond start_factor times starting_area_radius; the wrapper takes max(live, layer), so
  -- bobenemies' intensity cap reaches it through enemy_base_radius and enemy_base_frequency.
  -- `base`: the layer holds none of that expression's text or numbers. At load time prototypes/installed.lua reads
  -- the installed expression `name` in parts: the `fn` call it opens with (its arguments, of which the layer
  -- rewrites the three `args` name and its own `own`), the texture terms added to it (calls of the local function
  -- `texture`, and the last term that opens with `start`, the start clearing), the local expressions `radius` and
  -- `quantity`, and the texture function, whose `own` the layer rewrites too. `digest` is the digest of those
  -- texts as Factorio `game` holds them (tools/build_installed.py): a text that changed since is logged and read
  -- the same way, and one that no longer has this shape leaves each layer `neutral`, under which every wrapper
  -- keeps the live expression.
  enemies = {
    layer = REN.ENEMY_LAYER,
    wrapper = REN.ENEMY,
    seed1 = 7123,
    start_factor = 2,
    base = {name = "enemy_base_probability", fn = "spot_noise", own = "seed1", texture = "blob", start = "min",
            radius = "spot_radius_expression", quantity = "spot_quantity_expression", basement = "basement_value",
            args = {density = "density_expression", quantity = "spot_quantity_expression",
                    favorability = "spot_favorability_expression"},
            game = "2.1.24", digest = "d1290147bfc818d9", neutral = "-inf"},
    -- Scattered nests (0.3.0, new worlds; data-final-fixes.lua enemy_wrapper). Where a base's height passes the spawner
    -- cap of 0.25, a spawner goes down wherever its box fits, in the order the generator walks the tiles, so bases fill
    -- in even rows at box spacing. The wrapper keeps the height only on random runs of `run` tiles along a row, each
    -- row's runs shifted by a random phase, and -1 on the rest, so a spawner or worm can start only there. A run is
    -- kept when its draw is under run_share and under the two runs' on each side in the row (about 0.19 of the runs at
    -- 0.5), so kept runs stand two runs apart: with one apart a failed spawner's run and its neighbour's held four
    -- worms in a line over 16 tiles at Moscow. A kept run usually takes a spawner, whose box then covers it, and
    -- otherwise a worm. Single tiles gave too few spawners for the worms, and square cells lined spawners up on the
    -- cells' top rows; a run starts at any tile of a row and its row is any row. Every spawner and worm that reads
    -- enemy_base_probability (the base game's, and bobenemies' and Big-Monsters' worms through enemy_autoplace_base)
    -- scatters the same way. Inside a hotspot footprint the share takes footprint_share; ore_margin is how far below
    -- zero a solid hotspot ore body still keeps nests off (about 3 tiles of a cone's slope); seed and seed + 1 are the
    -- draws'.
    scatter = {wrapper = NOISE .. "enemy_v3", seed = 7431, run = 5, run_share = 0.5, footprint_share = 0.6,
               ore_margin = 2000},
  },

  -- Destroyed Europe (ARCHITECTURE.md, "Expression inventory").
  -- prototypes/expressions/destroyed.lua builds, from the region layer's interface names only:
  --   zone   min(tn_destroyed_depth, d - max(start.radius_tiles, starting_area_radius) - warp) in tiles, d the
  --          distance to the spawn, so the zone is positive inside its seeded outline less its keep rows
  --          (regions.lua seeded_polygon: vertices and edges move with the seed) and never inside the start
  --          disc, where every spawn city keeps normal ground and trees; the zone's own start mask, d read from
  --          start.distance (the spawn distance body every spawn record names). The warp is at least 0, so
  --          the disc only grows past its radius: at 0 it was a perfect circle of normal ground in black rock
  --   heat   where the zone is positive, clamp(rim + min(per_tile * zone, ramp) + noise, rim, cap) in Alien
  --          Biomes units: a heat-1 rim (100 to 120) that climbs within ramp / per_tile tiles to a core
  --          mixing heat-1 to heat-4 (heat-2 from 120, heat-3 from 135, heat-4 from 145 to 150; a small
  --          disc ramped 0.49 per tile to its cap, which on this zone would pave it with heat-4);
  --          -inf elsewhere, neutral for max; the noise is in tiles, a texture, not geography, and fine enough
  --          that a chunk rarely holds one heat band alone (at 96 tiles 48 percent of land chunks did, at 24, 2)
  --   temperature   the Alien Biomes temperature's next version: max(climate-tiles' first version, heat)
  --          with the toggle on, the first version alone off (a folded `if` on the switch)
  --   pools  per map with a city fold, its random pick over the cities outside the zone: the fold's hash
  --          modulo the pool's size, then the pool's k-th city (prototypes/tables/destroyed.lua lists the
  --          zone cities); a preset with the toggle on and the spawn city at random bakes it as the map's
  --          city number, so the first fold reads it and resolves it as a chosen city
  destroyed = {
    names = {zone = DE.zone, heat = DE.heat, temperature = DE.temperature, fine = DE.chaos_fine},
    pools = {europe = DE.pool_europe, atlantic = DE.pool_atlantic, olde_world = DE.pool_olde_world},
    -- warp_tiles: the start cut moves out by 0 to twice this along the fine noise, so its edge is organic
    -- and no zone tile ever lies inside radius_tiles
    start = {radius_tiles = 150, distance = DISTANCE, warp_tiles = 60},
    heat = {rim = 112, per_tile = 0.49, ramp = 30, cap = 149.5, lift_px = 30, lift_fray_px = 12,
            noise = {amplitude = 20, wavelength_tiles = 24, octaves = 3, persistence = 0.6, seed1 = 7901}},
    -- The red palette: a class per tile from a macro noise over the depth, so
    -- the patches mix and follow no contour. e = min(depth, sat_px) + mac_px * macro, in reference
    -- pixels: under rim_px red grass fraying into normal ground, under mid_px black ash or red rock,
    -- above it the volcanic tiles the heat picks. score beats the vanilla bonus (10) and loses to marsh
    -- pools (50), shallows and fords; water stays water by the elevation gate.
    chaos = {
      names = {macro = DE.chaos_macro, kind = DE.chaos_kind, class = DE.chaos_class},
      score = 20, sat_px = 100, mac_px = 50, rim_px = 30, mid_px = 70,
      grass = {per_px = 1 / 30, fine = 0.8, cut = 0.45},
      black_below = -0.25,
      macro = {wavelength_px = 10, octaves = 4, persistence = 0.6, seed1 = 7902},
      kind = {wavelength_px = 6, octaves = 3, persistence = 0.6, seed1 = 7903},
      tile = {grass = "vegetation-red-grass-1", black_sand = "mineral-black-sand-1",
              black_dirt = "mineral-black-dirt-1", red_sand = "mineral-red-sand-1", red_dirt = "mineral-red-dirt-1",
              grey_dirt = "mineral-grey-dirt-6"},
      tiles = {
        {tile = "vegetation-red-grass-1", class = 1, body = DE.chaos_grass},
        {tile = "mineral-black-sand-1", class = 2, body = DE.chaos_black_sand},
        {tile = "mineral-black-dirt-1", class = 3, body = DE.chaos_black_dirt},
        {tile = "mineral-red-sand-1", class = 4, body = DE.chaos_red_sand},
        {tile = "mineral-red-dirt-1", class = 5, body = DE.chaos_red_dirt},
        -- the released class bodies never return this class, so its score is -inf on every save they serve
        {tile = "mineral-grey-dirt-6", class = 6, body = DE.chaos_grey},
      },
    },
    -- The barrier: a world made after the first release names these bodies in place of
    -- heat and class, so a save keeps its zone. Everything here is in reference pixels, so it scales with the map.
    -- The heat tiles are ordinary buildable ground; only heat 3 and 4 read as lava.
    --   zone   the old zone cut inward by 0 to 2 * fray_px along the edge noise: inward only, so nothing spills past
    --          the outline onto Denmark, Britain or the Carpathians, and the long curve of the outline goes
    --   lava   the blob noise plus a ridge along the flow noise's zero, which tapers away as the blob falls, so a
    --          flow is a tendril off a patch and no zero contour closes round a piece of land
    --   heat   a temperature that climbs with lava, lava_at being the foot of heat 3, so a patch cools outward
    --          through heat 2 and heat 1 and the fine noise breaks the bands
    --   class  ordinary ground outside the old zone and past the feather, which moves the wasteland's edge in by
    --          feather_in, more or less the fine and kind noises, so the old outline never shows as a cut; then
    --          heat ground over ground_at, once past the barrier; every lifted tile is wasteland, or a bare class
    --          0 there would come out heat ground, in specks of lava in the barrier; then
    --          grass by depth and noise, then black or red rock, black more often inward. core is 0 in the
    --          barrier and 1 past it: barrier_px wide, more or less barrier_mac by the macro noise, so no ring of
    --          one width, and no noise value clears the penalty at core 0. Every class edge takes the grain, and
    --          sand against dirt is a cut off zero as well: noise is 0 on its lattice, so a contour at or near 0 ran
    --          20 to 30 tiles dead straight, along an axis or a diagonal
    -- next (0.3.0): a preset with the zone on names the next zone, heat and class over the
    -- released ones, and every reader follows by name.
    --   zone   the next outline's depth (destroyed.outline.next), cut by the edge noise as before and frayed at tile
    --          level (next.fray). The reach reads it as it is, so the wasteland's edge frays as before
    --   heat, class   read it shifted by the gap, the depth plus clamp(mid + amp * gap noise, low, top), and the heat
    --          stops at the reach. The barrier between the wasteland's edge and the heat ground, and the heart past it,
    --          narrow to nothing where the shift is high and run wider where it is low, along the edge: no band of one
    --          width (no perfect bands). A shift keeps every noise that frays the barrier's inner edge whole, where a
    --          stretch of the depth shrank them and the edge followed the outline's smooth contour. The class
    --          takes heat ground from next.ground_at, so heat 1 to 3 cover most of the zone past the barrier, and a
    --          rock palette of black ash, black sand and red dirt alone: no grey dirt and no red sand
    barrier = {
      names = {zone = DE.zone2, heat = DE.heat2, class = DE.class2, edge = DE.edge, blob = DE.blob, flow = DE.flow,
               lava = DE.lava, kind = DE.kind2, macro = DE.macro2, reach = DE.reach, open = DE.open, thin = DE.thin,
               dead = DE.dead, dead_noise = DE.dead_noise, dead2 = DE.dead2, zone3 = DE.zone3, heat3 = DE.heat3,
               class3 = DE.class3, gap = DE.gap},
      fray_px = 24, feather_in = 20, feather_px = 20, feather_kind = 25, feather_grain = 14, lift_px = 40,
      barrier_px = 68, barrier_mac = 20, ramp_px = 30, penalty = 3,
      lava_at = 0.75, ground_at = 0.06, ground_fine = 0.12, ground_grain = 0.18, t_at = 135, gain = 12, gain_hot = 25,
      fine = 7,
      flow_from = -0.35, flow_span = 0.5, flow_width = 0.13, flow_lift = 0.9,
      grass_px = 60, grass_mac = 0.9, grass_fine = 0.25, grass_cut = 0.7, grass_heart = 2,
      black_below = -0.25, black_in = 0.45, black_mac = 0.5, black_fine = 0.15, black_grain = 0.3,
      sand_mac = 1, sand_grain = 0.3, sand_cut = -0.5,
      -- The heart: past heart_px the heat ground wins most tiles, so the middle of the zone is cracked basalt with lava
      -- pools, and what rock stays there is black and grey, rarely red.
      heart_px = 110, heart_mac = 20, heart_ramp = 60, heart_gain = 0.6, heart_black = 0.9,
      grey_at = 0.45, grey_out = 0.6, grey_mac = 1, grey_kind = 0.35, grey_grain = 0.3, t_grain = 4,
      next = {ground_at = -0.35,
              -- ground: the fine and grain shares of the heat ground's edge against the rock (0.3.0, to the bar
              -- of no straight runs over about 6 tiles). At the released 0.12 and 0.18 the lava blob's 60-tile contour
              -- drew that edge, a line running straight for 70 tiles east of the Rhine at scale 12.
              ground = {fine = 0.35, grain = 0.45},
              -- gap: a shift in reference pixels, clamp(mid + amp * noise, low, top); at top the heat ground starts at
              -- the wasteland's frayed edge (the barrier breaks), at low the barrier runs low pixels wider
              gap = {wavelength_px = 36, octaves = 3, persistence = 0.55, seed1 = 7908, mid = 40, amp = 110,
                     low = -40, top = 140},
              -- The zone's depth frays in reference pixels (px: size and wavelength) and in tiles (tiles, at most cap
              -- reference pixels): where the edge noise saturates, the heat ground in a gap would start on the
              -- outline's own smooth contour, a long straight run at scale 12.
              fray = {px = {size = 4, wavelength = 3, octaves = 3, persistence = 0.6, seed1 = 7916},
                      tiles = {size = 6, cap = 1.5, wavelength = 9, octaves = 2, persistence = 0.5, seed1 = 7910}}},
      -- rock3: the next class's rock, which takes the light grey and the red sand out of the zone.
      -- Black sand drew as flat light grey and red dirt as red sand. Where either stood, the tile is heat ground (the
      -- cracked basalt) where core plus the macro, fine and grain shares passes heat_at and the
      -- lift holds, else black ash: past the barrier most of it turns to basalt with ragged black ash left in it, and
      -- in the barrier basalt patches break up the black ash, so no red field turns into one flat colour.
      rock3 = {heat_at = 0.75, mac = 0.5, fine = 0.25, grain = 0.25},
      -- The spawn sits inside the zone now: the first tiles stay below heat 3, which slows a player on foot, and the
      -- cap lifts with distance so no ring shows. It only ever lowers the heat, so the start is cooler, never cleared.
      -- Volcanic rock stands ten times as thick as ordinary rock, so inside the zone it and the dead trees thin out to
      -- rock_floor round the spawn, leaving room to build, and come back over rock_span.
      start = {cool_tiles = 90, cap = 134, per_tile = 0.1, rock_tiles = 110, rock_span = 130, rock_floor = 0.1},
      -- floor_tiles: a patch measured in reference pixels shrinks to specks at scale 1, so each noise stops at a width
      -- that still reads as a place from a player's height
      edge = {wavelength_px = 16, octaves = 5, persistence = 0.7, seed1 = 7904},
      blob = {wavelength_px = 5, octaves = 4, persistence = 0.7, seed1 = 7905, floor_tiles = 19},
      flow = {wavelength_px = 12, octaves = 3, persistence = 0.5, seed1 = 7906, floor_tiles = 37},
      kind = {wavelength_px = 6, octaves = 3, persistence = 0.6, seed1 = 7903, floor_tiles = 27},
      macro = {wavelength_px = 10, octaves = 4, persistence = 0.6, seed1 = 7902, floor_tiles = 33},
      -- swing_tiles: a noise measured in tiles moves an edge by at most this many tiles per reference pixel of its
      -- amplitude. In pixels alone the same noise would scatter specks over a band that grows with the scale, and
      -- reads as dither on the large maps.
      swing_tiles = 6,
      -- open_px: the exclusion's mask stands this far past the wasteland, in the units of reach, where the grain alone
      -- swings the edge by more than this across one tile. A tree stands up to a tile from the point its probability
      -- was read at, and one living tree on a wasteland tile shows.
      open_px = 8,
      -- Dead trees: tile-scale groves, thin between them, none on the lava colours.
      dead = {wavelength_tiles = 40, octaves = 3, persistence = 0.6, seed1 = 7907, cut = -0.1, span = 0.9, peak = 0.1,
              -- A Great forest in the zone is a dead forest (dead2, which a new world's preset names in dead's place):
              -- with the forests on, the dead trees rise to forest.peak times the forest weight times gain, clamped to
              -- 1, in clumps of the same noise from floor up, and thin near the spawn as the rest do.
              -- peak and floor 0.25 and 0.15 (less dense than at first): about 0.08 trees a tile at the
              -- forests' middle, two and a half times the plain zone's
              forest = {peak = 0.25, gain = 2, floor = 0.15}},
    },
    -- The outline a world made after the first release reads (prototypes/tables/zone_outline.lua). The barrier stands
    -- between the zone and ordinary land, so its depth counts land edges alone and the zone runs to the shore on every
    -- sea side. squeeze: an edge meant for the sea that lands on an island still gets a barrier, narrower by this
    -- factor, so no seed shows a hard cut.
    outline = {
      names = {land = DE.out_land, sea = DE.out_sea, inside = DE.out_inside, sd = DE.out_sd, isles = DE.out_isles,
               present = DE.out_present, depth = DE.out_depth},
      squeeze = 6,
      -- 0.3.0's next outline (prototypes/tables/zone_outline_v2.lua): the same bodies under their next names, the
      -- released isles line, and the cuts by id. A sea cut reads cut_px inside and -cut_px outside.
      next = {land = DE.out_land2, sea = DE.out_sea2, inside = DE.out_inside2, sd = DE.out_sd2, isles = DE.out_isles,
              present = DE.out_present2, depth = DE.out_depth2,
              cuts = {nordic = DE.out_nordic, iberia = DE.out_iberia}},
      cut_px = 1000,
      -- A land cut's edge in the presence frays at tile level by about size tiles (at most cap reference pixels): the
      -- shared roughness alone is a smooth curve there, which the tile grid turns into straight runs.
      cut_fray = {size = 6, cap = 1.5, wavelength = 9, octaves = 2, persistence = 0.5, seed1 = 7909},
      -- The next outline's own contour in the presence, where the feather lets the wasteland reach it: px in reference
      -- pixels (size and wavelength), tiles in tiles, at most cap reference pixels.
      edge_fray = {px = {size = 4, wavelength = 3, octaves = 3, persistence = 0.6, seed1 = 7914},
                   tiles = {size = 6, cap = 1.5, wavelength = 9, octaves = 2, persistence = 0.5, seed1 = 7915}},
    },
    -- What a zone keeps out (prototypes/zone_exclusion.lua). Data, so another zone can state its own: a tree or plant
    -- that can stand on `tiles` goes where `open` is 0, unless `plants` keeps it; `key` holds 0 on its prototype and
    -- a preset with the zone on names tn_one, so a world made before reads the off branch. Palms keep AB's prototypes
    -- (tiles.palm), so their preset keys name these bodies instead. Dead trees: every original leaves and copies come
    -- back with no tile list, since only dry-tree may stand on heat ground and widening an original's list would put
    -- it on saves that hold the volcanic tiles already.
    exclusion = {
      key = DE.clear, open = DE.open, thin = DE.thin, dead = DE.dead, dead_peak = 0.1,
      -- 1.0.0: every tree's mask on a range the zone encloses, whose own body is 1 (destroyed.dev.range_trees)
      range_open = DE.range_open,
      dead_order = "zz[" .. ID .. "]-",
      tiles = {"volcanic-orange-heat-1", "volcanic-orange-heat-2", "volcanic-orange-heat-3", "volcanic-orange-heat-4",
               "vegetation-red-grass-1", "mineral-black-sand-1", "mineral-black-dirt-1", "mineral-red-sand-1",
               "mineral-red-dirt-1", "mineral-grey-dirt-6"},
      plants = {drop = {"blue", "turquoise", "mauve", "purple", "violet", "green", "olive", "yellow", "puddle",
                        "wetland"},
                keep = {"red", "orange", "brown", "rock", "decal", "crater"}},
      -- next: a new world's zone wraps the palms' fourth versions, so the palm mask holds outside the zone as well; the
      -- first bodies wrap the second versions, which bypassed the mask.
      palms = {{key = CT.PALM_A_P_KEY, inner = TFN.PALM_A_P2, body = DE.palm_a,
                next = {inner = TFN.PALM_A_P4, body = DE.palm_a2}},
               {key = CT.PALM_B_P_KEY, inner = TFN.PALM_B_P2, body = DE.palm_b,
                next = {inner = TFN.PALM_B_P5, body = DE.palm_b2}}},
      -- boost: what a zone wants more of, inside it alone. The pools read as volcanic ground, and Alien Biomes' sand
      -- and grey ground carry a tenth of the rock its black dirt does.
      boost = {{type = "optimized-decorative", name = "lava-decal-orange", gain = 3},
               {type = "simple-entity", name = "sand-big-rock-black", gain = 8},
               {type = "simple-entity", name = "big-rock-grey", gain = 4},
               {type = "simple-entity", name = "huge-rock-grey", gain = 4}},
      dead_trees = {{tree = "dead-tree-desert", copy = ID .. "-dead-tree-desert", share = 0.3},
                    {tree = "dead-grey-trunk", copy = ID .. "-dead-grey-trunk", share = 0.3},
                    {tree = "dead-dry-hairy-tree", copy = ID .. "-dead-dry-hairy-tree", share = 0.2},
                    {tree = "dry-hairy-tree", copy = ID .. "-dry-hairy-tree", share = 0.1},
                    {tree = "dry-tree", copy = ID .. "-dry-tree", share = 0.1}},
    },
    -- Alien Biomes' heat bands differ by a few RGB steps, so heat 1 and heat 2 read as one dark grey on the map
    -- view. With the zone on they take this ramp, cool to hot, in 0 to 255 values. It stays red to the top:
    -- heat 4 is a fifth of the palette's ground, and the zone reads red (a yellow top read as yellow blobs).
    map_colors = {families = {"orange", "green", "blue", "purple"},
                  bands = {{r = 52, g = 38, b = 38}, {r = 86, g = 36, b = 32}, {r = 168, g = 40, b = 22},
                           {r = 226, g = 62, b = 24}}},
    -- A range in the zone (climate.lua, the cold north's second grain temperature): the highland's cap pulled the
    -- zone's lift under Alien Biomes' volcanic band, so the Alps north of Italy drew as brown and beige wasteland.
    -- Inside the lift the temperature stays at least this (heat 1, cracked basalt), so a range in the zone is Chaos
    -- ground.
    range_heat = 106,
    switch_threshold = 0.5,
    -- The devastation field (0.3.1; prototypes/expressions/destroyed.lua): a new world with the zone on names these
    -- over the barrier's heat, class, reach and open mask, so the zone fades into ordinary ground as one ordered
    -- gradient: from its edge in, dry dirt, scorched red grass, black ash, then heat ground climbing from heat 1
    -- through heat 2 and heat 3 into the lava blob's mix. Every class is a cut on one position in tiles, never a noise
    -- of its own, so no class stands outside its band.
    --   dev     the position: the next outline's depth less start_px, moved out and in by the ragged offset (px times
    --           a noise of wavelength_px and two coarser octaves), all in reference pixels times the scale, so it
    --           scales with the map; outside the presence it is outside_tiles
    --   width   the gradient's width in tiles: width_px times the scale times clamp(1 + amp * noise, low, high), so it
    --           narrows to almost nothing in places and runs more than twice as wide in others (NO PERFECT BANDS)
    --   cuts    dry_at, scorched_at, ash_at and heat_at, in widths from the edge, each moved by wobble times its share
    --           of the two wobble noises, so each band narrows, widens and breaks on its own
    --   fray    each cut moves by its own share of the zone's noises, macro and kind in reference pixels, fine and
    --           grain in tiles: about a tenth of each octave's wavelength, so an edge bends at every scale and seldom
    --           closes round an island
    --   ramp    from the heat cut in, the heat ground's temperature rises from heat 1 by ramp degrees a width, and the
    --           lava blob's temperature (the barrier's) takes over where it is cooler
    --   pyrenees  the Iberia cut moves strip_px into Spain, under the massif's snow (regions.lua), and near the cut
    --           (up to gate_px north of it) the position yields to the snow: snow_px pixels a unit of the highland's
    --           cold field under snow_at, the field at the snow's north edge, less south pixels a pixel of the cut's
    --           depth, so the zone's edge stands on the snow's own frayed edge and never passes the snow into Spain
    dev = {
      names = {dev = DE.dev, ragged = DE.dev_ragged, width = DE.dev_width, heat = DE.heat4, class = DE.class4,
               reach = DE.reach2, open = DE.open2, present = DE.out_present3, depth = DE.out_depth3,
               wobble_a = DE.dev_wobble_a, wobble_b = DE.dev_wobble_b, fray = DE.dev_fray},
      start_px = 40, width_px = 22, outside_tiles = -100000,
      ragged = {px = 18, wavelength_px = 25, octaves = 3, persistence = 0.5, seed1 = 7917},
      width = {amp = 1.6, low = 0.03, high = 2.4, wavelength_px = 40, octaves = 2, persistence = 0.5, seed1 = 7918},
      wobble = {a = {wavelength_px = 50, octaves = 2, persistence = 0.5, seed1 = 7919},
                b = {wavelength_px = 50, octaves = 2, persistence = 0.5, seed1 = 7920}},
      cuts = {
        dry = {at = 0, a = 0, b = 0, kind = 5, macro = 0, fine = 8, grain = 1},
        scorched = {at = 0.25, a = 0.15, b = 0, kind = 0, macro = 6, fine = -8, grain = 1},
        ash = {at = 0.5, a = 0, b = -0.18, kind = -5, macro = -4, fine = 6, grain = 1},
        heat = {at = 1, a = 0.12, b = -0.12, kind = 4, macro = -4, fine = -6, grain = 1},
      },
      -- the tile fray every cut adds: basis noises in tiles, finest first, so no edge runs straight along the grid
      tile_fray = {{tiles = 6, amp = 1.4, seed1 = 7921}, {tiles = 13, amp = 2.2, seed1 = 7922},
                   {tiles = 27, amp = 3, seed1 = 7923}},
      ramp = 60,
      open_tiles = 2,
      pyrenees = {strip_px = 30, snow_at = 0.6, snow_px = 20, south = 0.3, gate_px = 25, gate_per_px = 10},
      -- the dry dirt: class 7 of the red palette's class body, with the same score
      -- 0.3.2: the next class's grey rock (dev.next.class), whose score folds to -inf on every world made before
      tiles = {{tile = "mineral-brown-dirt-1", class = 7, body = DE.chaos_dry},
               {tile = "mineral-grey-dirt-2", class = 8, body = DE.chaos_grey2}},
      -- 0.3.2: a new world with the zone on names these over dev and width (presets.lua destroyed_values), and every
      -- cut reads them by name. The width noise runs from under a tenth of width_px to more than twice it within a
      -- few hundred tiles, so where it changes fastest the black ash and heat cuts followed its smooth contour, a line
      -- running straight for 100 tiles and more, which the tile fray (a few tiles) could not bend.
      --   jog    the width reads its noise at a point moved by jog_x and jog_y, basis noises in tiles, so its contour
      --          frays by about their size however fast the width changes
      --   fray   a finer tile fray the position adds, basis noises in tiles, so the cuts that follow the position's
      --          own contour (dry dirt first) bend within every few dozen tiles. Its two coarse octaves stay small
      --          beside the bands' width and its finest two small beside a tile's step of the field, so the class
      --          sequence bends without leaving islands of one class in the next; each zone's presence takes it too
      --          (over the scale, in reference pixels), so the zone's own outer edge frays as its cuts do; inside the
      --          Pyrenees' snow yield it ramps in over snow_ramp_tiles from the zone's edge, which stays on the snow's
      --          own edge, and the yield's gate line frays by the outline's edge fray and this fray
      next = {
        names = {dev = DE.dev2, width = DE.dev_width2, jog_x = DE.dev_jog_x, jog_y = DE.dev_jog_y,
                 fray = DE.dev_fray2, class = DE.class5, class2 = DE.class6},
        --   class  the next class: heat ground, black ash, then grey rock (grey, a class of the red palette) out to the
        --          zone's edge, with no scorched red grass or dry dirt. Where the grey band would be under thin tiles
        --          of the position wide, the black ash runs to the edge instead, so the band breaks off rather than
        --          thinning to a bright line one to three tiles wide. The black ash also reaches out over the grey band
        --          by its share of the break noise (reference pixels) over at, in full span over it, so the band
        --          narrows and breaks off along part of every edge; the noise is coarse beside the band, so its ash cut
        --          never folds back into islands. grey is the grey rock's class in tiles above (Alien Biomes' grey
        --          dirt 2, which reads as rock and stones beside the black ash)
        class = {thin = 16, grey = 8,
                 brk = {wavelength_px = 90, octaves = 2, persistence = 0.5, seed1 = 7937, at = 0.4, span = 0.5}},
        -- 0.4.0 (destroyed.lua class6): the next class's successor under DE.class6 (a preset that repoints
        -- dev.next.names.class to class2.name selects it). Three fixes over class5, all inside the
        -- Chaos/Moscow-chaos zone:
        --   the grey band no longer pinches below 10%: the black-ash boundary moves inward by ash_shift
        --        widths and the thin break drops from 16 to 2, so the grey rock reaches the zone's outer
        --        edge where the width noise narrows (57.5N 46E), instead of black ash eating the strip
        --   the black-ash edge has no straight run over ~55 tiles: ash_fray, finer basis noises in tiles
        --        added to the black-ash boundary, breaks the runs the smooth width/position contour left
        --   no outside snow tile inside the zone under High snow: heat ground (class 0) becomes grey
        --        rock wherever the North snow weight (climate.north_snow) is over snow_cut, so the palette
        --        overlay covers the snow-prone tiles the Koppen compose left at a cold temperature
        -- 0.4.0 (destroyed.lua class7): class6's successor, name2 = DE.class7, same params.
        -- class6 only painted grey rock where reach > 0 (the dry-cut core), so the dev > 0 zone fringe (reach <= 0,
        -- the frayed outer edge) fell back to class 0 (the Koppen base), where Alien Biomes' frozen-snow spot noise
        -- out-placed the cold edge under High snow. class7 assigns the fringe (reach <= 0 and dev > 0) the grey-rock
        -- class wholesale, so grey rock is scored and placed there; dev <= 0 (the surrounding Koppen) stays class 0,
        -- byte-identical, and reach > 0 keeps class6's body. The 0.4.0 presets repoint class to name2.
        class2 = {name = DE.class6, name2 = DE.class7, thin = 2, grey = 8, ash_shift = 0.22, snow_cut = 0.5,
                  ash_fray = {{tiles = 5.3, amp = 2.5, seed1 = 7941}, {tiles = 11.7, amp = 4.5, seed1 = 7942},
                              {tiles = 2.9, amp = 1.5, seed1 = 7943}}},
        jog = {{tiles = 7.3, amp = 1, seed1 = 7926}, {tiles = 15.7, amp = 2, seed1 = 7927},
               {tiles = 31.1, amp = 4, seed1 = 7928}, {tiles = 63.7, amp = 6, seed1 = 7933},
               {tiles = 127.3, amp = 12, seed1 = 7934}},
        fray = {{tiles = 4.7, amp = 1.5, seed1 = 7929}, {tiles = 9.1, amp = 3, seed1 = 7930},
                {tiles = 17.3, amp = 8, seed1 = 7931}, {tiles = 34.9, amp = 10, seed1 = 7932},
                {tiles = 69.7, amp = 4, seed1 = 7935}, {tiles = 139.1, amp = 8, seed1 = 7936}},
        jog_shift = 40000,
        snow_ramp_tiles = 48,
      },
      -- 1.0.0 (destroyed.lua, the range yield): a new world with Destroyed Europe's own outline on names this
      -- position over dev. It is the next position, less wherever a range's cold field (ridges.cold, the field the
      -- snow and the grey rim are cut from) says a snowy range stands. ds is that field's fall from the snow's edge
      -- (0 on the edge, negative in the snow). The range's position is px reference pixels a unit of ds, 0 on the
      -- grey rim at rim of its width out from the snow's edge (the rim is ridges.cold.band times the ragged factor
      -- wide, so where it breaks the zone's edge stands on the snow's), plus steep_px a unit past steep_from. Every
      -- cut, the reach, the heat and the class read the position by name, so the zone treats a range as it treats
      -- its own outer edge: heat ground, black ash, then grey rock up to the range's own grey rim, and past it the
      -- rim and the snow are the climate's, with no lift, no palette and no snow ban. The gentle first slope gives
      -- the grey rock room beside the rim; the steep one ends the band about steep_from out, before the flat top of
      -- a range too low for snow (ds 0.22 there), which stays the zone's heat ground. On the steep slope a tile is
      -- many tiles of the position, so the cuts' own frays move the black ash and heat edges by a tile or two, and
      -- along a straight crest they would run on the cold field's straight contour: the steep term reads ds moved by
      -- fray.next units a tile of the next position's fray and fray.tile units a tile of the cuts' tile fray, a few
      -- tiles of ground each on a range's flank. With ridges off no range stands and the term is off_tiles, which
      -- never binds.
      -- in_px: toward the crest from the zero line the position falls in_px a unit instead of px. On the gentle px
      -- the cuts' frays, some tens of tiles of the position, put the reach 10 to 20 tiles inside the rim and the
      -- snow, where the snow ban and the palette followed it; at in_px they reach a tile or two.
      ranges = {name = DE.dev3, px = 100, in_px = 1000, rim = 0.67, steep_px = 300, steep_from = 0.12,
                fray = {next = 0.002, tile = 0.006}, off_tiles = 100000},
      -- 1.0.0 (destroyed.lua, the trees of an enclosed range): the ground follows the yielding position, the trees
      -- the zone's own (the next position) wherever that lies deeper than deep_px reference pixels and deep_tiles
      -- tiles, less that margin. A range the zone encloses lies far deeper than that, so no living tree stands on it:
      -- where the yield gave the ground back and the trees' reach holds it, every tree takes the mask. The dead trees
      -- stand there at the zone's density or at convert times the likeliest restored tree's probability, where a
      -- living tree would have stood, whichever is more, fading out over snow.span of the cold field from snow.at past
      -- the snow's edge, so the snow stays bare. The restored trees' probability reads the climate, not the tiles they
      -- may stand on, so it runs above the trees it stood for where their tiles are missing; at convert 1 the dead
      -- trees number about the living and dead trees they stand in for. A range on the zone's edge, the Pyrenees on
      -- the Iberia cut, is never that deep: its trees follow the ground, as before.
      range_trees = {reach = DE.tree_reach, key = DE.range_open, open = DE.range_open1, dead = DE.dead3,
                     deep_px = 20, deep_tiles = 50, convert = 1, snow = {at = 0, span = 0.01}},
    },
  },

  -- The Moscow zone (0.3.1; prototypes/tables/zone_moscow.lua): a startup picklist, normal (no zone), chaos (Destroyed
  -- Europe's devastation field over its outline) or corrupted (Blue corrupted's ground, trees and climate over it).
  -- Baked per save through key, the level's index; without Alien Biomes it bakes normal and the mod warns. Either
  -- zone's machinery may now run for the Moscow zone alone, so europe.key and uk.key bake whether Destroyed Europe's
  -- and Blue corrupted's own outlines are on (1 with the setting on beside Alien Biomes, else 0).
  --   dev      the Moscow position in tiles (destroyed.lua): the outline's depth less start_px plus ragged_share of
  --            the shared ragged offset, so the zone's edge keeps to the drawn outline; with chaos the devastation
  --            field is the larger of it and Europe's
  --   corrupt  the Corrupted zone's depth in reference pixels: the outline's plus fray times the devastation field's
  --            tile fray (destroyed.dev.tile_fray, tiles over the scale), never nearer the Chaos zone's wasteland
  --            than gap pixels (clamp(mid + amp * noise, low, top)), so ordinary ground between the two zones narrows
  --            to nothing in places and never runs as an even strip; union is the depth Blue corrupted reads, the
  --            larger of the UK's (with the UK key on) and this one (with corrupted)
  --   snow     the Corrupted Moscow zone's edge (within outer_tiles outside and strip_tiles inside its outline): its
  --            dirt and rim classes take its grass classes, and where the north snow's weight (climate.north_snow) is
  --            over at its fringe, fringe_tiles past the edge, takes snow (tiles, scored like the zone's), so the zone
  --            runs straight from blue and purple into snow; the grey rim's keep is 0 inside the zone and keep_tiles
  --            past it, frayed by fray tiles of noise, rising to 1 over ramp_tiles
  moscow = {
    setting = "moscow_zone", key = DE.mz_key, requires = "alien-biomes",
    levels = {{value = "normal", index = 0}, {value = "chaos", index = 1}, {value = "corrupted", index = 2}},
    chaos = 1, corrupted = 2, match = 0.5, values = {normal = "normal", chaos = "chaos", corrupted = "corrupted"},
    europe = {key = DE.eu_key, on = 1, off = 0}, uk = {key = BC.uk_key, on = 1, off = 0},
    outline = {names = {land = DE.mz_land, sea = DE.mz_sea, inside = DE.mz_inside, sd = DE.mz_sd,
                        present = DE.mz_present, depth = DE.mz_depth}},
    dev = DE.mz_dev, start_px = 6, ragged_share = 0.6,
    -- 0.3.2: the next Moscow position, read by the next devastation field (destroyed.dev.next): its presence takes
    -- the field's next fray over the scale, since the outline's own contour, a smooth curve, drew the zone's edge
    -- wherever the field reached it
    next = {dev = DE.mz_dev2},
    corrupt = {depth = BC.mz_corrupt, union = BC.out_depth3, big_px = 4000, fray = 14,
               gap = {name = BC.mz_gap, wavelength_px = 30, octaves = 2, persistence = 0.5, seed1 = 7924, mid = 3,
                      amp = 9, low = 0, top = 12}},
    snow = {class = BC.class2, under = BC.class_under, rim_keep = BC.rim_keep, w = CT.CL_N_SNOW_W,
            north_keep = CT.CL_N_RIM_KEEP, at = 0.05, strip_tiles = 480, keep_tiles = 56, ramp_tiles = 64,
            fringe_tiles = 60, fringe_fray = 18, outer_tiles = 240,
            fray = {tiles = 40, amp = 24, octaves = 2, persistence = 0.5, seed1 = 7925},
            tiles = {{tile = "frozen-snow-0", class = 10, body = BC.mz_snow_0},
                     {tile = "frozen-snow-2", class = 11, body = BC.mz_snow_2}}},
    -- 1.1.0 (new worlds): the zone keeps the snow it encloses, the north snow of the North snow setting and the snowy
    -- ranges (the western Caucasus by the Kerch Strait) with their grey rim.
    --   chaos      a preset with the zone at Chaos names this position over the devastation field's (destroyed.dev):
    --              the next position less the range yield (destroyed.dev.ranges), and inside the Moscow zone also
    --              less the north snow's own position, rn tiles: px reference pixels a unit of ne south of the snow's
    --              edge and in_px a unit into it, never under floor_px units. ne is in reference pixels: the cold
    --              north's temperature near its line, the line's fall of climate.north2.south_per_degree a degree of
    --              latitude plus noise times the climate's own temperature noise, less t_at, over that fall, times
    --              coordinates.px_per_degree, plus fray.next tiles of the next position's fray and fray.tile tiles of
    --              the cuts' tile fray (destroyed.dev.next, destroyed.dev). It reads no zone body and no grain, and
    --              its zero line runs where that temperature is t_at, a little short of the snow's frayed edge. Every
    --              reader of the position follows by name: the heat stops short of the snow, the class runs heat
    --              ground, black ash and grey rock up to it, the snow ban lifts, and the trees there follow the zone's
    --              own position as on an enclosed range (destroyed.dev.range_trees), which the preset names for this
    --              zone too. Where the Moscow outline is absent (its position at outside_tiles) the position is dev3's,
    --              or the next position where no range binds, bit for bit. The preset also
    --              names class over the zone's class: inside the Moscow outline, where the zone's own position (the
    --              next one) is in and ne is under 0, the ground the north snow takes back is the world's snow where
    --              its tile temperature (climate.grain.keys) is under t_below and the reach is out, and grey rock
    --              (destroyed.dev.next.class2's grey) everywhere else, so no green or brown ground stands in the zone
    --              between the snow fields, and where the zone's own position is in and ne is not under 0 the zone's
    --              class less its snow rule (class2's snow_cut), whose grey stood for snow that now lies outside the
    --              zone. Elsewhere it is the zone's class, value for value. And it names open over the open mask
    --              (destroyed.exclusion): 0 on that same ground, where the reach alone left it open, so the zone's
    --              plant rule holds there too (no green grass or flowers on the grey rock), and the zone's mask
    --              elsewhere
    --   corrupted  a preset with the zone at Corrupted names this class over Blue corrupted's: inside the Moscow
    --              outline, wherever the tile temperature is under t_below, where the world lays snow, or the range
    --              cold field (ridges.cold) passes the grey rim's outer edge, rim times its width (band times the
    --              ragged factor) from the snow's edge, and the tile temperature is under t_rim (the rim's outer part
    --              is the world's grass, which would stand in the zone), it is class 0, so the world's own snow and
    --              grey rim show, and everywhere else it is the zone's class. The zone's climate, trees and plants
    --              stay the zone's, so its trees stand on the rim where their tiles allow, and no tree of the zone
    --              stands on snow
    keep = {
      chaos = {name = DE.dev4, class = DE.class8, open = DE.open3, t_at = 1, noise = 1, px = 3, in_px = 20,
               floor_px = 100, fray = {next = 1, tile = 1}, t_below = 0},
      corrupted = {class = BC.class3, t_below = 0, rim = 1, t_rim = 22},
    },
  },

  -- Blue corrupted UK and Australia (prototypes/expressions/blue.lua, prototypes/tables/zone_blue.lua). Mostly mauve
  -- grass, the ground of Alien Biomes' high-aux box at temperature 20 to 40, with its blue and purple neighbours mixed
  -- in. Tiles take a class per tile, as Destroyed Europe's do. Trees and plants follow Alien Biomes' own climate boxes:
  -- a preset with the zone on redirects the three climate fields inside it, so they are the ones that box grows.
  -- Everything here is in reference pixels, so it scales with the map, with a floor in tiles where a patch would shrink
  -- to specks. No scale list and no ceiling in tiles.
  --   field   macro + kind_share * kind. Below lo the ground is blue, above hi purple, and the temperature follows the
  --           same field, so a patch's trees and plants match its ground. lo and hi map to the box's edges
  --   dry     a noise of its own: below dirt_at the grass opens to aubergine and purple dirt, and the moisture's
  --           plateaus follow it
  --   fine, grain   move each class edge at tile level, and no cut sits at 0, where a noise contour runs straight
  --   reach   positive inside. A shape's sea edge never shows, since the coast is the zone's edge: only the Ulster
  --           border has one, frayed by feather_px, feather_kind and feather_grain, with a dark rim rim_px wide
  blue = {
    names = {reach = BC.reach, open = BC.open, macro = BC.macro, kind = BC.kind, dry = BC.dry,
             field = BC.field, class = BC.class, keep = BC.keep, keep_under = BC.keep_under},
    outline = {
      names = {britain = BC.out_britain, australia = BC.out_australia, sea = BC.out_sea, ulster = BC.out_ulster,
               land = BC.out_land, depth = BC.out_depth},
      -- 0.3.1: a new world with the zone on reads the next outline's depth in place of the first (presets.lua
      -- blue_values), which holds the United Kingdom alone
      next = {britain = BC.out_britain2, sea = BC.out_sea2, ulster = BC.out_ulster2, land = BC.out_land2,
              depth = BC.out_depth2},
      inside_px = 4000,
    },
    climate = {
      temperature = {body = BC.temperature, under = BC.temperature_under},
      moisture = {body = BC.moisture, under = BC.moisture_under},
      aux = {body = BC.aux, under = BC.aux_under},
    },
    t_at = 30, t_per_field = 12.5, aux_at = 0.87, aux_span = 0.08, aux_low = 0.8, aux_high = 0.98,
    -- Alien Biomes puts each tree's moisture in a band 0.1 wide, so a moisture that slopes grows trees along its
    -- contours, in long thin lines. These are plateaus instead, each with a hard edge frayed by the same noise:
    -- woodland just off the grassland trees' band, dry wood on the dryland trees', and open ground between the bands.
    m_wood = 0.62, m_dry = 0.4, m_open = 0.75, wood_at = 0.45, dry_at = -0.55,
    score = 40,
    macro = {wavelength_px = 14, octaves = 4, persistence = 0.6, seed1 = 7911, floor_tiles = 48},
    kind = {wavelength_px = 5, octaves = 3, persistence = 0.6, seed1 = 7912, floor_tiles = 24},
    dry = {wavelength_px = 9, octaves = 3, persistence = 0.6, seed1 = 7913, floor_tiles = 36},
    kind_share = 0.4, lo = -0.85, hi = 0.75, dirt_at = -0.95, side_at = 0.42,
    edge_fine = 0.22, edge_grain = 0.42, side_grain = 0.7,
    feather_in = 5, feather_px = 7, feather_kind = 7, feather_grain = 5, rim_px = 9, rim_mac = 4, rim_grain = 2,
    swing_tiles = 6, open_px = 2,
    tile = {mauve_2 = "vegetation-mauve-grass-2", mauve_1 = "vegetation-mauve-grass-1",
            purple_2 = "vegetation-purple-grass-2", purple_1 = "vegetation-purple-grass-1",
            blue_2 = "vegetation-blue-grass-2", blue_1 = "vegetation-blue-grass-1",
            aubergine_dirt = "mineral-aubergine-dirt-1", purple_dirt = "mineral-purple-dirt-2",
            aubergine_rim = "mineral-aubergine-dirt-2"},
    -- class 0 is the world's own ground. map: Alien Biomes' colours sit near black on the map view, and with the zone
    -- on these bring the same hues up to read at a glance. Map colours only; no world changes.
    tiles = {
      {tile = "vegetation-mauve-grass-2", class = 1, body = BC.mauve_2, map = {r = 88, g = 72, b = 150}},
      {tile = "vegetation-mauve-grass-1", class = 2, body = BC.mauve_1, map = {r = 104, g = 88, b = 170}},
      {tile = "vegetation-purple-grass-2", class = 3, body = BC.purple_2, map = {r = 110, g = 52, b = 150}},
      {tile = "vegetation-purple-grass-1", class = 4, body = BC.purple_1, map = {r = 132, g = 68, b = 168}},
      {tile = "vegetation-blue-grass-2", class = 5, body = BC.blue_2, map = {r = 54, g = 76, b = 138}},
      {tile = "vegetation-blue-grass-1", class = 6, body = BC.blue_1, map = {r = 62, g = 92, b = 164}},
      {tile = "mineral-aubergine-dirt-1", class = 7, body = BC.aubergine_dirt, map = {r = 84, g = 76, b = 112}},
      {tile = "mineral-purple-dirt-2", class = 8, body = BC.purple_dirt, map = {r = 92, g = 94, b = 168}},
      {tile = "mineral-aubergine-dirt-2", class = 9, body = BC.aubergine_rim, map = {r = 66, g = 60, b = 84}},
    },
    -- What the zone keeps out (prototypes/zone_exclusion.lua). Alien Biomes' trees read the climate softly, so a tree
    -- out of its box still stands where its own noise peaks: its cyan and its greens would show as loud clumps.
    -- keep_trees holds the violet, purple, white and blue trees, the dead ones and no others. Plants hold to their
    -- boxes, so only the yellow flowers and the orange fluff and mud take a hook: an empty word is in every name.
    exclusion = {
      key = BC.K, open = BC.open,
      tiles = {"vegetation-mauve-grass-2", "vegetation-mauve-grass-1", "vegetation-purple-grass-2",
               "vegetation-purple-grass-1", "vegetation-blue-grass-2", "vegetation-blue-grass-1",
               "mineral-aubergine-dirt-1", "mineral-purple-dirt-2", "mineral-aubergine-dirt-2"},
      keep_trees = {["tree-grassland-i"] = true, ["tree-grassland-m"] = true, ["tree-grassland-h2"] = true,
                    ["tree-grassland-h3"] = true, ["tree-grassland-e"] = true, ["tree-wetland-h"] = true,
                    ["tree-wetland-f"] = true, ["tree-dryland-m"] = true, ["tree-dryland-d"] = true,
                    ["tree-desert-l"] = true, ["tree-desert-n"] = true, ["tree-desert-j"] = true,
                    ["dead-grey-trunk"] = true, ["dead-dry-hairy-tree"] = true, ["dry-hairy-tree"] = true,
                    ["dry-tree"] = true, ["dead-tree-desert"] = true},
      plants = {keep = {""}, drop = {"green-yellow", "brown-fluff", "cracked-mud"}},
    },
    -- Palms keep Alien Biomes' prototypes (tiles.palm), so their preset keys name these bodies: each wraps whatever the
    -- key held, the zone's Destroyed Europe body included.
    palms = {{key = CT.PALM_A_P_KEY, body = BC.palm_a, under = BC.palm_a_under},
             {key = CT.PALM_B_P_KEY, body = BC.palm_b, under = BC.palm_b_under}},
    -- Blue only in the zone: on a new world beside Alien Biomes its blue, teal, purple, violet, lilac and mauve tiles,
    -- plants and trees place nowhere outside the zone, and nowhere at all with the zone off. Each takes the zone's hook
    -- pattern on its probability, gated on key (prototype 0, so a world made before folds to its own text): a tree or
    -- plant times open, 1 inside the zone's open band and 0 elsewhere; a tile plus tile, 0 there and -inf elsewhere.
    -- Inside the zone both are the identity. Tiles and plants by name; trees by leaf colour, those whose colour list is
    -- half or more in hue 165 to 325 (saturation over 0.15) plus the zone's own mauve and pink keep trees. Alien
    -- Biomes' violet palm (tree-palm-b) takes open through its preset key's body.
    -- No normal plant in the zone: on a new world (key, prototype 0) the green and olive plants that can stand on the
    -- zone's tiles take the zone's open with the zone on, so the zone keeps its own purple, blue and white plants.
    plants2 = {key = TFN.ZP_KEY, words = {"green", "olive"}},
    no_blue = {
      key = TFN.NB_KEY, open = TFN.NB_OPEN, tile = TFN.NB_TILE, out = TFN.NB_OUT,
      -- A blue tile's counterpart takes the max of its own score and the blue tile's outside the zone (out: 0 there,
      -- -inf inside), so the ground keeps its pattern in green, brown or orange.
      swap = {["vegetation-"] = "green", ["mineral-"] = "brown", ["volcanic-"] = "orange"},
      words = {"blue", "turquoise", "purple", "violet", "mauve", "lilac", "aubergine", "dustyrose"},
      tile_prefixes = {"vegetation-", "mineral-", "volcanic-"},
      trees = {"tree-desert-b", "tree-desert-l", "tree-desert-m", "tree-desert-n", "tree-dryland-d", "tree-dryland-m",
               "tree-dryland-n", "tree-dryland-o", "tree-grassland-e", "tree-grassland-h2", "tree-grassland-h3",
               "tree-grassland-i", "tree-grassland-m", "tree-grassland-p", "tree-grassland-q", "tree-wetland-f",
               "tree-wetland-h", "tree-wetland-j", "tree-wetland-k", "tree-wetland-l"},
    },
  },

  -- Control-stage messages: the locale section and keys (locale/en/terra-nauvis.cfg). notice_withheld
  -- is the Map type notice where the map's preset is withheld (presets.withheld_with); drift_update
  -- is the drift line for a Map type fallback that moved with the mod itself rather than with a
  -- startup setting (a frozen fallback never should: the line is a tripwire); withheld_beside warns
  -- an Earth world whose preset is withheld beside a mod it now loads with; start is the start
  -- message, rso the RSO warning and drift_city the drift line for a changed spawn-city
  -- setting on an Earth world (spawn-cities); destroyed_no_ab is the warning for Destroyed Europe on
  -- without Alien Biomes (destroyed-europe). Messages name a world's
  -- map by its preset's name, which no version changes. A stored warning keeps its key here
  -- (scripts/guards.lua record_warning; ARCHITECTURE.md, "Guards", stored records), so a key that
  -- saves can hold is never removed or renamed: retire a message by leaving its key and locale
  -- entry in place (the static append-only check tests these keys against main and origin/main).
  messages = {
    section = ID,
    keys = {
      notice = "map-type-notice",
      notice_withheld = "map-type-notice-withheld",
      drift_scale = "drift-scale",
      drift_follows = "drift-follows",
      drift_update = "drift-update",
      missing_name = "missing-name",
      withheld_beside = "withheld-beside",
      start = "start-message",
      rso = "rso-warning",
      drift_city = "drift-city",
      drift_toggle = "drift-toggle",
      drift_toggle_new = "drift-toggle-new-only",
      toggle_on = "toggle-on",
      toggle_off = "toggle-off",
      cliff_reset = "cliff-reset",
      destroyed_no_ab = "destroyed-no-ab",
      moscow_no_ab = "moscow-no-ab",
      start_ore = "start-ore",
      start_ore_none = "start-ore-none",
    },
  },

  -- Toggles, keyed like settings: key -> {setting = <settings key>, preset_key = <key>, default,
  -- mechanism = "name switch" or "hook gate", on = <name>, off = <name>, maps = {<map keys>}};
  -- toggle_order lists the keys. Each toggle arrives with its feature.
  toggles = {
    -- Canals (waterways): a name switch read by every waterways version's entry through a folded `if`, so
    -- only the selected branch compiles (Tile 19,620 off and 20,161 on at scale 1).
    -- map_type_follows: its Map type fallback mirrors the setting, so the drift line says a world made
    -- from the map type alone follows it; every other toggle reaches new preset worlds only.
    canals = {setting = "canals", preset_key = K_CANALS, default = true, mechanism = "name switch",
              on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}, map_type_follows = true},
    -- Great forests (trees-forests): the hook gate of the boost on every living tree, outermost in the
    -- hook, so on every other world the hook folds to the tree's own autoplace. Its values are the
    -- numbers 1 and 0 as strings, so a save reads them back as it stored them and the drift line
    -- compares like with like.
    great_forests = {setting = "great_forests", preset_key = TFN.K_FORESTS_ON, default = true, mechanism = "hook gate",
                     on = "1", off = "0", maps = {"europe", "atlantic", "olde_world"}},
    -- Ridges: a name switch read by the ridge bodies through a folded `if`, so ridges off
    -- compiles to a constant crest distance and 0 cliffs.
    ridges = {setting = "ridges", preset_key = RDN.K_RIDGES, default = true, mechanism = "name switch",
              on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}},
    -- Hotspots: a name switch read by the ore, enemy and offshore-oil wrappers
    -- through a folded `if`, so hotspots off compiles each wrapper to the live expression alone; each
    -- map's offshore stamp key follows the same setting (presets.lua).
    hotspots = {setting = "hotspots", preset_key = REN.K_HOTSPOTS, default = true, mechanism = "name switch",
                on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}},
    -- Inland lakes: a name switch read by a version with a lakes field through a
    -- folded `if`, so off compiles to the spawn lake alone (the spot noise is never evaluated) and on to
    -- the previous version's composition. Every map lists it: a map's version without a spawn
    -- record bakes it unread.
    inland_lakes = {setting = "inland_lakes", preset_key = ELN.K_INLAND_LAKES, default = false,
                    mechanism = "name switch", on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"},
                    map_type_follows = true},
    -- Destroyed Europe (destroyed-europe): a name switch read by the temperature's next version through a
    -- folded `if`, so the zone off compiles to climate-tiles' temperature alone. `requires` names the mod
    -- without which a preset bakes it off whatever the setting says, and the drift line
    -- compares with the same rule.
    destroyed_europe = {setting = "destroyed_europe", preset_key = DE.K, default = false,
                        mechanism = "name switch", on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"},
                        requires = "alien-biomes"},
    -- Blue corrupted UK and Australia: a name switch read by the zone's tile scores through a folded `if`. `requires`
    -- as Destroyed Europe's. Every map holds some of the zone, Europe the UK alone.
    blue_corrupted = {setting = "blue_corrupted", preset_key = BC.K, default = false,
                      mechanism = "name switch", on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"},
                      requires = "alien-biomes"},
    -- Koppen biomes (0.4.0, default on): a name switch baked as tn_koppen. presets.lua reads it in its
    -- baked function (koppen_names) to point temperature/moisture/aux at the Koppen snap bodies when on. Orthogonal to
    -- elevation, so one-click world creation is preserved.
    -- 1.0.0: the setting is hidden and pinned off, so a new world bakes the off value; the toggle stays
    -- for the worlds that baked it on.
    koppen = {setting = "koppen", preset_key = K_KOPPEN, default = false, mechanism = "name switch",
              on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}},
  },
  toggle_order = {"canals", "great_forests", "ridges", "hotspots", "inland_lakes", "destroyed_europe",
                  "blue_corrupted", "koppen"},

  -- Stable hooks on shared prototypes (ARCHITECTURE.md, "Stable hooks"): if(gate > threshold, on
  -- branch, off value), whose outermost `if` folds away on worlds without the gate. The gate's
  -- prototype holds gate_off, Earth presets gate_on; the ford key's prototype holds its off value.
  hooks = {
    threshold = 0.5, gate_off = 0, gate_on = 1,
    fords = {tile = "water-shallow", key = K_FORDS, off = "-inf"},
  },
  -- The canals switch's neutral bodies.
  neutral = {one = ONE, zero = ZERO},

  -- Waterways (ARCHITECTURE.md, "Build-time data flow" step 3 and "Elevation
  -- composition" steps 5 and 6). tools/build_waterways.py reads every number below; the mod reads
  -- the set names and the hook values.
  --   sets: per map, the generated set names by scale (index = scale): ww (rivers, straits and
  --     turning basins, min into the entry), canals (min, canals on), dams (max, canals off) and
  --     fords (the water-shallow hook's on branch, through tn_fords). The geography version that
  --     composes a map's sets names the same table as its `waterways` field, and the sets bind to
  --     that version's chain, so one version per map composes them.
  --   widths: a river is max(river_floor_tiles, k s) tiles wide
  --     by its class, so it scales with the map; a strait max(floor / 2 + margin, s / 2,
  --     w s / (2 km_per_px)) with floor two_way_tiles for the two-way straits; a canal max(floor / 2
  --     + margin, s / 2); a dam max(dam.floor_tiles, dam.per_scale s).
  --   depth: the carve's floor, plain water in vanilla and Alien Biomes for rivers and canals,
  --     deepwater for straits; slope: elevation per tile from the carve's edge.
  --   tolerance_tiles: Douglas-Peucker per scale (raised, because the warp hides the vertices on a
  --     gentle reach and every segment costs per tile); a river's bends
  --     take less, down to the scale's smoothing.least_tiles, so no vertex turns by more than kink_degrees
  --     where the curve allows it (bend_tiles: the arm of the curvature estimate); smoothing: box windows in
  --     tiles, tried smallest first from min_window_px reference px until the smoothed centreline (simplified
  --     at fine_tolerance_tiles) obeys the bend rule, for rivers; the drawn_kinds (straits and canals, sea
  --     passages the coast
  --     fit fills as land) keep their drawn course unsmoothed, their drawn points (a strait's waypoints
  --     and narrowest point, a canal's route vertices) held within their half-width less one tile;
  --     bend: the bend rule, no window_tiles
  --     stretch turning more than limit_degrees; basin_tiles: the turning basin where it still fails.
  --   ford: every every_px reference px of a river's path, max(least_length_tiles, length_tiles s /
  --     full_scale) long along it before its rough edge (natural.ford_edge), spanning the
  --     carve plus margin_tiles, its banks bank_tiles beyond the carve on reference land; score
  --     beats every water tile's autoplace inside it.
  --   versions: a map's generated files when a release moved that map alone; else version. Its geography version
  --     names the same number as waterway_files, and an older version keeps reading its own.
  --   start (design rule 18): a spawn whose clear_tiles disc a corridor crosses moves to the nearest tile
  --     with clear_tiles of land around it; radius_tiles is the start area the bank masks cover.
  waterways = {
    version = 1,
    versions = {atlantic = 2, olde_world = 2},
    -- next (0.3.2): a map's files past its released ones at some scales, emitted as `version` for `scales` beside them
    -- (tools/build_waterways.py, manifest-<map>-next.json), with `round` applied: each listed river's course inside
    -- box_px (reference px: first column, first row, last column, last row) and one vertex beyond each end corner-cut
    -- `passes` times, so a tight bend the simplification left as a few long segments meeting at sharp vertices reads as
    -- one curve, then simplified at simplify_tiles. The Volga's Samara Bend (48.5 to 50.4 E, 53.0 to 54.4 N, Tolyatti
    -- to Syzran) at scales 12 and 24. calm: at its scale the next river and ford sets read the rivers' warp under
    -- names of their own (warp, x then y), whose fine meander (natural.warp_fine) fades to 0 within inner_tiles of
    -- centre_px (reference px) and is whole past outer_tiles: there the meander octaves, 34 tiles at 230 and 13 at 95,
    -- bent the bend's two reaches by different amounts into a hook with near-right corners. Every tile past
    -- outer_tiles reads the warp it read before, so no other river moves.
    next = {olde_world = {version = 3, scales = {12, 24}, round = {
      {river = "volga", box_px = {3040, 1245, 3126, 1308}, passes = 4, simplify_tiles = 0.5},
    }, calm = {scale = 12, centre_px = {3112, 1295}, inner_tiles = 160, outer_tiles = 320, warp = OAS.OW_WARP3}}},
    sets = {europe = OAS_SETS.europe_v7, atlantic = OAS_SETS.atlantic_v8, olde_world = OAS_SETS.olde_world_v9},
    floor_tiles = 7, river_floor_tiles = 3, two_way_tiles = 11, margin_tiles = 0.25,
    river_k = {major = 3, minor = 2},
    river_cap_tiles = {major = 48, minor = 36},
    km_per_px = 2.471,
    depth = {river = -2.2, strait = -6, canal = -2.2},
    slope = 4,
    dam = {floor_tiles = 1.5, per_scale = 0.5},
    tolerance_tiles = {3, 4, 6, 8, 10, 12, 24, 48},
    smoothing = {windows = {1, 5, 9, 13, 17, 25, 33, 49, 65, 97}, passes = 3, step_tiles = 1, min_window_px = 12,
                 fine_tolerance_tiles = 0.5, drawn_kinds = {"strait", "canal"}, kink_degrees = 30, bend_tiles = 8,
                 least_tiles = {2.5, 2, 1, 1, 1, 1, 1, 1},
                 windows_past_six = {145, 193, 289, 385}},
    bend = {window_tiles = 17, limit_degrees = 90},
    basin_tiles = 30,
    ford = {every_px = 60, length_tiles = 10, full_scale = 6, least_length_tiles = 5, margin_tiles = 3, bank_tiles = 3,
            score = 10000, jitter = 0.3},
    vertex_grid = 16,
    start = {clear_tiles = 12, radius_tiles = 150},
    -- The natural course (not perfect lines, with perfect edges; waterways.lua
    -- and tools/build_waterways.py).
    --   warp: one octave per row, a basis noise per axis (seed1x, seed1y) of wavelength {a, b} = a + b s tiles
    --     and amplitude {a, b} = a + b s tiles at scale s, added to the geo tiles every set reads; passage is
    --     the share a strait, canal or dam reads. The first two rows are the meanders, the last the banks,
    --     short enough that the two banks of a river differ. noise_peak: basis noise's peak, for the warp's reach.
    --   width: W = 1 + amplitude * clamp(noise, -1, 1), a river's half-width factor. A river's half-width is
    --     held at floor_half_tiles by scale wherever W and the warp squeeze it, on the width grid so the floor
    --     shares a class: a river scales down with the map even where a boat no longer
    --     fits, so only scale 6 keeps the 7-tile navigation disc, and 1.5 is what still draws an unbroken river.
    --     tip_half_tiles holds a tapered source where W could take it under that; files of version 2 hold
  --     tip_half_tiles_v2, because at 1 the game's water correction broke a stream's last tiles into dashes.
    --   bank: B = amplitude {a, b} * (half + half * clamp(noise, -1, 1)) tiles of wavelength {a, b} tiles at
    --     scale s (a + b s), the fine irregularity every river and passage bank adds to its half-width.
    --   ford_edge: J = amplitude {a, b} * noise tiles of wavelength {a, b} tiles at scale s, added to a ford's
    --     rectangle on every side, so its two edges across the river are irregular and not parallel. Past
    --     hold_above, J keeps that scale's numbers: at scale 24 a 17-tile wavelength left a ford's end straight.
    --   profile: a river's half-width factor from source at its inland end to mouth where it meets the coast
    --     fit, on a step_tiles grid. A source thins to tip over taper_tiles {a, b} = a + b s by the distance
    --     to the nearest source (a set's T), not by segment: one width per segment left a round finger. A ford
    --     in the taper sizes itself on a grid twice as coarse below taper_full_scale. step_per_scale: the grid is
    --     this many tiles per scale where that is coarser, which starts past scale 6: a width class costs Tile, and
    --     a step of 0.75 tiles shows nothing on a river 36 tiles wide.
    --   basin: a turning basin's capsule, half_length_tiles each way along the course, radius_tiles wide; a
    --     river takes one only from least_river_scale up, where a ship fits it.
    --   deloop: a river's hooks cut, tools/build_waterways.py deloop.
    --   runs: a river's segments over max_px reference px take a vertex every step_px, off their line by
    --     amplitude step_px times least to 1, on alternating sides (tools/build_waterways.py break_runs).
    --   spawn_fade: the warp is 0 within inner_tiles of the spawn and whole beyond outer_tiles, or outer_per_scale
    --     tiles per scale where that is farther, which starts past scale 6: the warp's amplitude grows with the scale,
    --     and a fade that stays 160 tiles long folds a river back on itself at scale 24.
    --   mouth (files of version 2): the warp is 0 within inner_tiles of where a river meets the sea and whole beyond
    --     outer_tiles, and the band-fix masks narrow with it, so a delta keeps Exact coastlines' shore. Tiles, not px:
    --     the warp is about the same size in tiles at every scale, and a fade in px cut rivers from the sea at low
    --     scales. rivers: a river's own fade, in px. Only a delta needs a long one: the warp is what hides a polyline's
    --     straight runs, so a long fade on every river ruled the lower reach of 21 of Old World's 37
    --     straight. inner_per_scale, outer_per_scale: past scale 6 the fade takes this many tiles per scale, for
    --     the same reason as spawn_fade.
    --   ponds: water components of the coast fit of at most max_px px within reach_px of a river's cells take
    --     land, height at the centre and 0 margin_px beyond the component's farthest pixel.
    natural = {
      warp = {
        {seed1x = 7501, seed1y = 7502, wavelength = {60, 50}, amplitude = {2, 3.8}, passage = 0},
        {seed1x = 7503, seed1y = 7504, wavelength = {30, 12}, amplitude = {1.5, 0.9}, passage = 0.3},
        {seed1x = 7505, seed1y = 7506, wavelength = {14, 1.5}, amplitude = {0.6, 0.2}, passage = 1},
      },
      noise_peak = 1.7,
      width = {seed1 = 7507, wavelength = {60, 60}, amplitude = 0.3, tip_half_tiles = 1,
               tip_half_tiles_v2 = 1.5,
               floor_half_tiles = {1.5, 1.5, 2.25, 3.75, 4.5, 5.5, 9, 12}},
      bank = {seed1 = 7508, wavelength = {8, 1}, amplitude = {0.6, 0.15}, half = 0.5},
      -- low_bank: bank's rows for the river sets of the geographies listed at scales up to max_scale. There a river
      -- is three to five tiles wide, and bank's 0.75 tiles left its two sides parallel lines stepping one tile at a
      -- time. gain scales the noise before the clamp, so the bank seldom rests flat at either end of its range.
      low_bank = {geographies = {21, 22, 23}, max_scale = 2, seed1 = 7510, wavelength = {6, 0}, amplitude = {1.5, 0},
                  half = 0.5, gain = 0.6},
      ford_edge = {seed1 = 7509, wavelength = {5, 0.5}, amplitude = {0.6, 0.2}, hold_above = 6},
      -- ford_fine: the listed geographies add these octaves to J, fixed in tiles, past ford_edge.hold_above.
      -- soft: the ford set alone adds these octaves to J, then under at tiles J falls at slope, so a ford's end keeps
      -- its wiggle where the noise runs low but seldom pulls back from a bank, and bias_tiles lengthens it everywhere:
      -- with the fine octaves alone a ford read as a pale rectangle across its river (f-eyetest row 5).
      ford_fine = {geographies = {21, 22}, max_scale = 12,
                   octaves = {{seed1 = 7523, wavelength_tiles = 9, amplitude_tiles = 2.0},
                              {seed1 = 7524, wavelength_tiles = 5, amplitude_tiles = 0.8}},
                   soft = {bias_tiles = 1.5, at = -3, slope = 0.3,
                           octaves = {{seed1 = 7547, wavelength_tiles = 17, amplitude_tiles = 3.2}}}},
      -- bank_fine: the listed geographies' river sets (kind) widen B by these octaves, fixed in tiles, so a bank
      -- tangent to a grid axis on a meander breaks within a few tiles instead of running straight along it.
      bank_fine = {geographies = {21, 22}, min_scale = 12, max_scale = 12, kind = "ww",
                   octaves = {{seed1 = 7548, wavelength_tiles = 11, amplitude_tiles = 1.6}}},
      -- warp_fine: the listed geographies' rivers bend by these octaves, fixed in tiles, from min_scale up. They fade
      -- in over fade_outer_tiles from the spawn_fade's inner disc, not spawn_fade's longer reach: the meander octaves
      -- are what keep a reach near the spawn from running straight along a grid axis (f-eyetest rows 1 and 8).
      warp_fine = {geographies = {21, 22}, min_scale = 12, max_scale = 12, fade_outer_tiles = 220,
                   octaves = {{seed1x = 7525, seed1y = 7526, wavelength_tiles = 7, amplitude_tiles = 1.1},
                              {meander = true, seed1x = 7541, seed1y = 7542,
                               wavelength_tiles = 230, amplitude_tiles = 34},
                              {meander = true, seed1x = 7543, seed1y = 7544,
                               wavelength_tiles = 95, amplitude_tiles = 13},
                              {meander = true, seed1x = 7545, seed1y = 7546,
                               wavelength_tiles = 38, amplitude_tiles = 4.5}}},
      profile = {source = 0.7, mouth = 1.35, tip = 0.12, taper_tiles = {10, 45}, step_tiles = 0.75,
                 step_per_scale = 0.125, taper_full_scale = 6},
      basin = {half_length_tiles = 8, radius_tiles = 12, least_river_scale = 4},
      deloop = {gap_px = 8, arc_px = 30, reach_px = 400},
      runs = {max_px = 60, step_px = 36, amplitude = 0.2, least = 0.4},
      spawn_fade = {inner_tiles = 40, outer_tiles = 200, outer_per_scale = 33.3},
      ponds = {max_px = 32, reach_px = 3, margin_px = 1.5, height = 20},
      mouth = {inner_tiles = 36, outer_tiles = 120, inner_per_scale = 6, outer_per_scale = 20,
               rivers = {mississippi = {inner_px = 30, outer_px = 80}}},
    },
  },

  -- The region layer (ARCHITECTURE.md, "Region layer"): the rows of prototypes/tables/regions.lua as
  -- exact signed distances in reference pixels at a query point on the coordinate chain, displaced by
  -- one shared domain warp and roughened by
  -- one shared edge noise, with each layer's aggregates. Every row is evaluated in the frame map's
  -- reference pixels: each map's raster sits on that grid at px_per_degree (Europe is an exact crop of
  -- Atlantic's raster; Old World's edges are whole pixels away), so a map's own chain moves into the
  -- frame by a whole-pixel offset and a row sits at its geography on every map and at every scale.
  --   warp      two multi-octave noises (seed1 per axis), wavelength_px the finest octave, amplitude_px
  --             times the noise, the vector clamped to clamp_px in length; a row follows its share
  --   rough     one multi-octave noise added to every signed distance, clamped to +-clamp_px
  --   octave_shift_px  each octave's x shift per octave index (its own lattice: no shared zero); every
  --             octave is a basis_noise anchored to the frame (multioctave_noise offsets are not
  --             shifts in 2.1.23, measured for this layer)
  --   ramp      membership weight clamp(mid + sd / width_px, 0, 1)
  --   jitter    a hotspot's centre moves by up to its jitter radius per seed: a linear fold of
  --             map_seed_small and the seed's high bits, plus the row's phase (no new noise)
  --   names     the interface and internal names; a row's names are row.<kind> .. <row id> .. suffix
  -- Names carry the layer's version suffix; a changed body ships under the next one (design rule 21).
  regions = {
    frame = "europe",
    frame_tolerance_px = 0.01,
    km_per_px = 2.471,
    warp = {amplitude_px = 12, clamp_px = 24, wavelength_px = 96, octaves = 3, persistence = 0.5, seed1_x = 7801,
            seed1_y = 7802},
    rough = {amplitude_px = 1.5, clamp_px = 3, wavelength_px = 6, octaves = 2, persistence = 0.5, seed1 = 7803},
    ramp = {mid = 0.5, width_px = 6},
    -- A marsh's own edge (an exact disc or box of pools reads as computer-made at any
    -- zoom). One more noise, wavelength_px the finest octave, joins every marsh row's signed distance at
    -- share of the row's radius, at most cap_px, over rough_gain times the shared roughness, and the
    -- row's ramp widens to ramp_share of its radius, at most ramp_cap_px and never under ramp.width_px,
    -- so the pools thin out into dry ground across the band instead of stopping at a line. Marsh rows
    -- are the Tile program's only readers of the region noise, so these two octaves cost that program
    -- little. bias leans the noise outward, so a small delta's seed rarely sinks it below the marsh cut
    -- (the Danube delta vanished at seed 1002 without it). A marsh's reach is the row's radius plus about
    -- 2 times its amplitude, the most basis noise and the bias reach. edge_gain: on these maps the shared
    -- roughness joins at share of the row's radius, between rough_gain and top: the outline noise is far longer
    -- than a small delta, so it only grew or shrank the disc, and the Danube delta stayed a round plate on the
    -- coast at every seed. The roughness is compiled already, so this costs no noise call.
    marsh = {wavelength_px = 24, octaves = 2, persistence = 0.5, seed1 = 7804, share = 0.6, cap_px = 24,
             bias = 0.35, rough_gain = 2, ramp_share = 0.6, ramp_cap_px = 24,
             edge_gain = {maps = {europe = true, atlantic = true}, share = 0.35, top = 5}},
    share_hundredths = 100,
    octave_shift_px = 10000.37,
    max_arguments = 255,
    forest_boost = 2,
    -- hotspot_share: a hotspot stays on its real place: a table's jitter radius is half
    -- the row's radius, up to 100 km, so a disc could stand half a radius off the site; a quarter stays on it.
    jitter = {mult_x = 0.6180339887, mult_y = 0.4142135624, mult_high = 0.569840291, high_bits = 65536,
              vertex_step = 0.7548776662, flat_px = 0.001, hotspot_share = 0.5},
    names = {
      suffix = RG_V,
      row = {sd = NOISE .. "sd_", w = NOISE .. "w_", depth = NOISE .. "depth_", hu = NOISE .. "hu_",
             hv = NOISE .. "hv_", pd = NOISE .. "pd_"},
      share = "_k",
      destroyed_sd = RG_DESTROYED_SD, destroyed_w = RG_DESTROYED_W, destroyed_depth = RG_DESTROYED_DEPTH,
      forest_w = RG_FOREST_W, forest_sum = RG_FOREST_SUM, tree_mult = RG_TREE_MULT, marsh_w = RG_MARSH_W,
      hotspot_w = RG_HOTSPOT_W, enemy_mult = RG_ENEMY_MULT,
      highland_fray = RDN.RD_FRAY, highland_fray_tile = RDN.RD_FRAY_TILE, highland_massif = RDN.RD_MASSIF,
      highland_cold = RDN.RD_COLD_FRAY,
      -- the query point: u, v .. suffix unwarped; u, v .. share .. <hundredths> .. suffix for a share
      u = RG_U, v = RG_V_, ox = RG_OX, oy = RG_OY, ax = RG_AX, ay = RG_AY, wk = RG_WK, wx = RG_WX, wy = RG_WY,
      rough = RG_ROUGH, marsh_rough = RG_MARSH_ROUGH,
    },
  },

  -- The river deltas (1.0.0): prototypes/tables/regions_v3.lua holds a marsh row on each great delta the first two
  -- tables lack and the delta's distributaries as channel rows, polylines traced along the water of the reference
  -- raster. No elevation moves and no geography release: a marsh row lifts the moisture as every marsh does, so a
  -- delta is green in a desert, and a channel is drawn in the ford tile, walkable shallow water on land from the
  -- river to the sea, which Exact coastlines never rewrites. The main stem stays the one ship channel.
  --   maps      the maps whose new worlds name the bodies (points); Europe holds no row and keeps its names
  --   names     marsh_w: the marsh aggregate over the three tables; delta_w: the largest weight of this table's
  --             marsh rows; u, v: the region query point moved by the channel warp; bank: a channel's half-width
  --             factor; channel: tiles inside the nearest channel (above 0 inside); water_mud: the pools, thinned
  --             by pool_damp times delta_w so the channels stay the delta's water; water_shallow: the first body
  --             and the channels on land outside the start clearing
  --   channel   half_tiles {a, b}: a channel's half-width a + b s tiles at scale s times the row's width, at least
  --             least_half_tiles; warp: octaves of wavelength {a, b} and amplitude {a, b} tiles, as waterways.natural
  --             spells them, a basis noise per axis anchored to the region frame, on top of the rivers' own warp,
  --             which the channels read by name: a polyline's straight runs bend where a river's mouth fade holds
  --             that warp at 0, and their amplitude stays under a river's half-width, since a row that leaves a
  --             river starts on that river's course at the save's map and scale (the table's starts);
  --             bank: the half-width factor 1 + amplitude * noise
  regions_v3 = {
    maps = {atlantic = true, olde_world = true},
    names = {marsh_w = RG_MARSH_W3, delta_w = RG_DELTA_W, u = RG_DELTA_U, v = RG_DELTA_V, bank = RG_DELTA_BANK,
             channel = RG_DELTA_CH, water_mud = CT.MARSH_MUD_BODY3, water_shallow = CT.MARSH_SHALLOW_BODY2},
    points = {[RG_MARSH_W] = RG_MARSH_W3, [CT.MARSH_MUD] = CT.MARSH_MUD_BODY3,
              [CT.MARSH_SHALLOW] = CT.MARSH_SHALLOW_BODY2},
    channel = {half_tiles = {1.5, 0.9}, least_half_tiles = 2.5, pool_damp = 0.5,
               warp = {{seed1x = 7811, seed1y = 7812, wavelength = {40, 14}, amplitude = {0.5, 1.4}},
                       {seed1x = 7813, seed1y = 7814, wavelength = {14, 2}, amplitude = {0.4, 0.5}}},
               bank = {seed1 = 7815, wavelength = {9, 1}, amplitude = 0.3}},
  },

  -- The second region table (0.3.0): prototypes/tables/regions_v2.lua
  -- holds the great forests and marshes outside Europe that the released first table lacks (9 of its 16 forests and 6
  -- of its 12 marshes lie in Europe). Its rows take the first table's names and bodies; names are the forest and marsh
  -- aggregates over both tables' rows, which every new world reads through the first aggregates' names (points), so
  -- every consumer (trees, the marsh pools and moisture, the vanilla tiles' marsh cut, the zone's dead forest) reads
  -- them unchanged.
  regions_v2 = {
    names = {forest_w = RG_FOREST_W2, forest_sum = RG_FOREST_SUM2, marsh_w = RG_MARSH_W2},
    points = {[RG_FOREST_W] = RG_FOREST_W2, [RG_FOREST_SUM] = RG_FOREST_SUM2, [RG_MARSH_W] = RG_MARSH_W2},
  },

  -- The shore body (ARCHITECTURE.md, "Elevation composition" step 2, recalibrated
  -- with Alien Biomes): the sign-offset transfer of v1 with its own land and water
  -- gains, so the tile class is still the sign of c (the pixel-centre coast check is unchanged) while
  --   land  e = max(land.min, land.per_scale * s) * c + offset: elevation 5, where AB's shore term ends,
  --         sits about 4 tiles inland at scale 2 and up and 2 tiles at scale 1 (the beach band);
  --   water e = max(water.min, water.per_scale * s) * c - offset: AB's deepwater line, -5.5,
  --         sits about 6 tiles offshore at scale 3 and up and 2.7 tiles at scale 1, where the fit's
  --         saturation (about 4 px) left v1's open sea at -4.1, shallow water under AB.
  -- c, its clamp and the far-field box are v1's (the coast group above); the carves and dams of v2 keep
  -- their absolute depths, so rivers stay plain water and straits deep in vanilla and AB alike.
  -- Each version that composes it names its own shore body (geography.<map>.versions[n].shore).
  shore = {
    land = {per_scale = 1.25, min = 2.5},
    water = {per_scale = 0.9, min = 2},
  },

  -- The Earth climate (ARCHITECTURE.md, "Expression inventory" and "Alien Biomes").
  -- Temperature is in Alien Biomes units (below 0 frozen, 25 to 65 temperate,
  -- 65 hot, above 100 volcanic) in both variants; the fallback hands vanilla consumers scale times it.
  --   lat, lon  degrees on the map's own chain: lat_top_edge - (v + 1/2) / px_per_degree and
  --             lon_left_edge + (u + 1/2) / px_per_degree, folded on tn_map; the latitude meanders by up
  --             to degrees times one basis noise octave of wavelength_px (seed1)
  --   temperature  ref_t at ref_lat, per_degree warmer toward the equator, clamped to min and cap; minus
  --             continental.t at full continentality (longitude lon_start + lon_span and east, latitude
  --             lat_start + lat_span and north: the cold Russian interior); plus desert_heat in the dry
  --             belts; plus noise; Alien Biomes adds its hot and cold shift, shift_per_unit per slider unit
  --             as its own average, and scales the noise input by their mean frequency
  --   moisture  the Earth mean (base, plus equatorial within the equatorial latitude ramp, minus dry in
  --             the dry belts; the fallback caps the mean by temperature: the dry north) plus the
  --             spread and bias times the moisture bias; with Alien Biomes the marsh weight lifts it to
  --             marsh times the weight
  --   aux       the Earth mean (base; the fallback pulls cold land toward cold_aux and dry land down by
  --             dry_pull) plus the spread, capped (Alien Biomes: ab_cap, under AB's alien palette
  --             from 0.6; the fallback's cold land: cold_cap, under vanilla red desert), then bias times
  --             the aux bias; with Alien Biomes dry temperate land is lifted by red.lift (vanilla red
  --             desert, where non-adopted AB tiles are excluded)
  --   spread    every real climate zone is a patchwork of several tiles that changes with the seed
  --             (the bar: a real biome never reads as one tile): each field adds a seeded multioctave
  --             noise after its caps and pulls, so they move the mean and never flatten the noise. Its
  --             sd is about 0.7 times amplitude (normalized multioctave_noise): moisture about 0.22,
  --             aux 0.14 and temperature 4.2 AB units, against vanilla's about 0.39 moisture and 0.2 aux
  --             (core noise-programs.lua: moisture_noise and aux_noise), whose coarsest octaves the
  --             Earth layout replaces. The moisture spread shrinks by spread.dry times the dry weight, so
  --             the dry belts stay hot desert, and on the fallback by spread.cold times the coldness
  --             (clamp((cold.t - core) / cold.span, 0, 1)), so the far north stays dry and dead ground
  -- Every noise call keeps x = x, y = y with its wavelength in reference pixels through input_scale: the
  -- finest octave is wavelength_px, each further octave twice as large (multioctave_noise).
  climate = {
    -- the pixel centre in reference pixels (lat_top_edge - (v + centre_px) / px_per_degree)
    centre_px = 0.5,
    -- The latitude meander's noise is one named field, and the dry belts read it again at their own
    -- reach: a belt is a latitude and longitude box, whose edge ran dead straight for thousands of tiles
    -- on the map view until it wandered by about this many degrees (no new noise, one more use of it).
    meander = {name = CT.CL_MEANDER, degrees = 0.6, wavelength_px = 360, seed1 = 7601, dry_lat = 3, dry_lon = 4},
    -- The city offset folded into a seed1 shift (tiles modulo `modulus`, x times `stride` plus y): each
    -- spawn city's climate noise gets its own seed (climate.lua). The largest value stays under 2^24, so
    -- float32 holds it exactly.
    city_shift = {modulus = 4093, stride = 257},
    temperature = {
      ref_lat = 54, ref_t = 25, per_degree = 2.2, min = -20, cap = 78,
      continental = {t = 6, lon_start = 15, lon_span = 45, lat_start = 35, lat_span = 10},
      desert_heat = 12,
      noise = {amplitude = 6, wavelength_px = 40, octaves = 3, persistence = 0.6, seed1 = 7602},
      ab = {shift_per_unit = 20.8333333, min = -20, max = 99},
      -- taiga (the north read as bare sand and dirt): before the scale, a core from
      -- treeline_t up to plateau is lifted to plateau, so the boreal belt sits inside the vanilla cold
      -- trees' 0 to 15 band; below treeline_t it falls by slope per unit, so the tundra and the arctic
      -- stay treeless (core -20 maps to -10 before the scale)
      fallback = {scale = 0.45, min = -20, max = 50, taiga = {plateau = 10, treeline_t = -16, slope = 5}},
    },
    moisture = {
      base = 0.68, equatorial = 0.12, equatorial_lat = 4, equatorial_ramp = 8, dry = 0.55, marsh = 0.9,
      noise = {amplitude = 0.32, wavelength_px = 40, octaves = 3, persistence = 0.6, seed1 = 7603},
      spread = {dry = 0.7, cold = 0.55},
      ab_bias = 2.2, ab_top = 0.92,
      -- north: the boreal belt is moist (the vanilla cold trees want 0.4 to 0.8): the cap rises to wet
      -- from core wet_from_t to wet_full_t, falls to frozen from core frozen_from_t to frozen_full_t,
      -- and a floor (full at core floor_full_t, none from floor_from_t) keeps sand, light dirt and
      -- dry dirt out of the north
      fallback = {cap_base = 0.26, cap_per_t = 0.6, cap_t = 40, bias = 1,
                  north = {wet = 0.64, wet_from_t = 20, wet_full_t = 10, frozen = 0.45, frozen_from_t = -16,
                           frozen_full_t = -20, floor = 0.42, floor_from_t = 12, floor_full_t = 4}},
    },
    aux = {
      base = 0.35,
      noise = {amplitude = 0.2, wavelength_px = 48, octaves = 3, persistence = 0.6, seed1 = 7604},
      ab_bias = 2.2, ab_cap = 0.5,
      red = {lift = 0.5, t_lo = 25, t_hi = 65, ramp = 5},
      -- cold_span: the aux pull and cap reach full strength cold_span below climate.cold.t (sooner than
      -- the moisture spread's cold), so the boreal belt keeps grass-2, beach sand and red desert out
      fallback = {cold_aux = 0.3, cold_cap = 0.45, cold_span = 12, dry_pull = 0.15, bias = 1},
    },
    -- The grain (Europe's biomes look best): Alien Biomes scores a tile through a steep
    -- clamp of its peak value, whose box edge is far steeper than its own
    -- noise can move, so at scale 6, where the spread's finest octave is 240 tiles, every edge outside
    -- the temperate band is a razor line round a flat blob. Europe hides it: 54 percent of its land is
    -- temperate, against 18 on Old World and Atlantic, where vanilla tiles and their patch noise win.
    -- Beside Alien Biomes, every map below gives the tile scores alone frayed copies of the three
    -- fields (Europe too: its Moscow had the same razor edges): each Alien Biomes tile with a prefix
    -- below reads keys.tile on its on branch, and the temperate bonus and exclusion read the
    -- temperature copy, so their edge frays too. A copy adds
    -- noise_layer_noise(layer), 6 to 48 tiles at every scale, the same call as grass-1's, so the Tile
    -- program shares it; trees and decoratives keep the plain fields, so placement stays as it was.
    -- The amounts are per unit (aux inside its cap), at full weight cold_span under cold_t and
    -- hot_span over hot_t and at none between, so temperate land keeps its character. The weight reads
    -- the temperature and not its core: read on the core, a cold spot in temperate land took no grain,
    -- and its edge was a razor arc and straight shards where two fields' contours crossed (Prague,
    -- Frankfurt). A coarser noise only redraws the blobs (the temperate patch noise, 60 tiles and up at
    -- scale 6, left razor edges).
    -- Each key's prototype is its plain field, so a preset that names none keeps its program.
    grain = {maps = {atlantic = true, europe = true, olde_world = true}, layer = 19,
             temperature = 3, moisture = 0.09, aux = 0.09,
             cold_t = 32, cold_span = 10, hot_t = 58, hot_span = 7,
             prefixes = {"vegetation-", "mineral-", "frozen-", "volcanic-"},
             keys = {temperature = CT.K_TILE_T, moisture = CT.K_TILE_M, aux = CT.K_TILE_A},
             -- Vegetation tiles read a temperature of their own, so a belt can repaint grass without
             -- moving bare ground, and veg_cap holds it under Alien Biomes' orange grass (T 80 and up, a
             -- rust colour no real grassland has); veg_zone_t is the natural ceiling, over which only
             -- Destroyed Europe's heat lies, and which keeps the zone's tiles as they were.
             veg_prefix = "vegetation-", veg_key = CT.K_TILE_TV, veg_cap = 79.5, veg_zone_t = 99,
             -- 0.3.0 (the bar: no straight runs over about 6 tiles): the zone takes no grain, so its heat bands met
             -- on the contours of the heat's 24-tile noise and ran straight for 20 to 39 tiles (Prague, Frankfurt).
             -- The cold north's second tile temperature adds zone_fray times noise_layer_noise inside the zone's lift,
             -- never past the lift's rim or cap (near the spawn its cooler cap), so no ground outside the volcanic band
             -- shows through and no heat 3 lands by the start.
             zone_fray = 5,
             -- Alien Biomes deals its ice tiles half of all frozen ground by one noise's sign, and their grey
             -- blue covered more of the Arctic than snow did: each gives up this much score, so ice
             -- keeps to the noise's lows.
             ice = {["frozen-snow-5"] = 0.35, ["frozen-snow-6"] = 0.35, ["frozen-snow-7"] = 0.35,
                    ["frozen-snow-8"] = 0.35, ["frozen-snow-9"] = 0.35},
             -- Two of Alien Biomes' four green grasses read brown (their textures average 67, 55, 28 and 67,
             -- 49, 25, the first two 66, 59, 20 and 74, 61, 24), which a rainforest should not: the same
             -- handicap keeps them to the noise's highs.
             brown = {["vegetation-green-grass-3"] = 0.12, ["vegetation-green-grass-4"] = 0.25}},
    -- The tile belts (use Alien Biomes where it makes sense): Alien Biomes colours its
    -- tiles by one temperature and moisture ladder, so latitude alone paints the Congo as yellow and
    -- orange grass, Tibet like the Sahel and the steppes like Germany. A belt is a latitude and longitude
    -- box with soft edges, as a dry belt is, that moves only the fields tile scores read (the grain's
    -- bodies, so trees and decoratives keep their climate): t the tile temperature, tv the vegetation
    -- tiles' temperature on top of it, m the moisture and `a` the aux (outside its cap). wild takes the
    -- belt out of the temperate band, so a dry steppe at Germany's latitude is not vanilla land.
    -- Every number was read from whole-map tile counts.
    tile_belts = {
      {id = "hot", lat = {-36, 36}, lon = {-180, 180}, ramp = {4, 1}, a = -0.16},
      {id = "sahara_arabia", lat = {15, 35.5}, lon = {-20, 62}, ramp = {3, 4}, a = -0.03},
      -- maghreb (0.3.0): the Tell coast from Morocco to Tunisia is Mediterranean ground, which the Atlas's grey covered
      -- until its snow line rose in the dry belt (ridges.cold.dry_rise_m); without it the Sahara ran to the sea.
      {id = "maghreb", since = "0.3.0", lat = {33, 37.4}, lon = {-10, 11.5}, ramp = {1.2, 2}, m = 0.3},
      -- namib (0.3.0: the true deserts read as desert): the coast from Namibe to the Orange is the driest
      -- ground in Africa, but the southern Africa dry belt fades out toward its sea edge; this takes the grass off it.
      {id = "namib", since = "0.3.0", lat = {-29, -16}, lon = {11, 16.5}, ramp = {1.5, 1.5}, m = -0.35},
      -- The sanity pass (0.3.0: nothing out of place): the dry belts' boxes reach rainforest and humid ground,
      -- where the spread's lows drew desert or tan dry dirt: the Pacific coast from San Francisco to Puget Sound,
      -- Chile's Valdivian south, Japan and Korea north of the japan belt, and Madagascar's rainforest east.
      {id = "pacific_nw", since = "0.3.0", lat = {37.5, 50}, lon = {-126, -121.2}, ramp = {2, 1.2}, m = 0.35},
      {id = "valdivia", since = "0.3.0", lat = {-56, -37.5}, lon = {-76.5, -72}, ramp = {2, 1.2}, m = 0.4},
      {id = "east_asia_wet", since = "0.3.0", lat = {30, 46}, lon = {124, 146}, ramp = {2, 2}, m = 0.18},
      {id = "madagascar_east", since = "0.3.0", lat = {-25.5, -12}, lon = {47.4, 51}, ramp = {1, 1}, m = 0.3},
      -- The Sahara belt's meander reaches 38 N and more, so Greece, Crete and Sicily read as Saharan sand (Sicily was
      -- spared only while Etna's cap held it temperate): the Mediterranean's northern shores take the moisture of a dry
      -- scrub, dirt and grass, not dunes.
      {id = "mediterranean", since = "0.3.0", lat = {33.5, 41.5}, lon = {-10, 36}, ramp = {1.5, 3}, m = 0.4},
      -- Savannas, dry scrub and Mediterranean coasts (0.3.0): EarthMaps
      -- paints these as dry land, and the global hot belt alone drew them as the same even grass as their humid
      -- neighbours, or, inside a dry belt's box, as desert where the real ground is savanna or scrub. Moisture only, so
      -- trees and decoratives keep their climate: the savannas of East Africa and the Cerrado and the dry scrub of the
      -- Caatinga and the Karoo take dry dirt and sand among their grass, the Pampas a wetter grassland, and northern
      -- Australia's savanna and California's and central Chile's Mediterranean coasts, inside the dry belts, grass and
      -- scrub instead of dunes. The Mediterranean basin's own interiors (the Meseta, Anatolia) lie in the temperate
      -- band, whose vanilla tiles read the released moisture, so no row here reaches them; their ground is a third dirt
      -- already. edge: the row takes the dry belts' desert edge (climate.desert_edge) at its weight, so the dirt
      -- between the sand it draws and the grass breaks and varies (no perfect bands): without it an even dirt ring 300
      -- tiles wide, never under 2 tiles, ran round every sand patch in the Karoo and the Caatinga.
      {id = "east_africa", since = "0.3.0", lat = {-11, 3}, lon = {29.5, 41}, ramp = {2, 1.5}, m = -0.08,
       edge = true},
      {id = "karoo", since = "0.3.0", lat = {-33.6, -29}, lon = {18.5, 26.5}, ramp = {1, 1.5}, m = -0.28, edge = true},
      {id = "cerrado", since = "0.3.0", lat = {-21, -5}, lon = {-56, -43}, ramp = {2, 2}, m = -0.08, edge = true},
      {id = "caatinga", since = "0.3.0", lat = {-14.5, -3}, lon = {-43.5, -36}, ramp = {1.5, 1.2}, m = -0.22,
       edge = true},
      {id = "pampas", since = "0.3.0", lat = {-38.5, -30.5}, lon = {-64, -57.5}, ramp = {1.5, 1.5}, m = 0.15},
      {id = "north_australia", since = "0.3.0", lat = {-18.5, -10.5}, lon = {121, 146}, ramp = {2.5, 2}, m = 0.3},
      {id = "california", since = "0.3.0", lat = {32, 41}, lon = {-125, -116.8}, ramp = {1.2, 1}, m = 0.5},
      {id = "chile_central", since = "0.3.0", lat = {-37.5, -30}, lon = {-74, -69.5}, ramp = {1.2, 0.8}, m = 0.5},
      {id = "sahel", lat = {9, 18}, lon = {-18, 42}, ramp = {3, 4}, m = 0.5},
      {id = "congo", lat = {-12, 8}, lon = {6, 34}, ramp = {2, 3}, tv = -40, m = 0.2},
      {id = "guinea", lat = {3, 10}, lon = {-15, 10}, ramp = {2, 3}, tv = -40, m = 0.2},
      {id = "se_asia", lat = {-11, 23}, lon = {92, 156}, ramp = {3, 4}, tv = -40, m = 0.2},
      {id = "south_china", lat = {20, 34.5}, lon = {100, 123}, ramp = {3, 4}, tv = -36, m = 0.12},
      {id = "japan", lat = {30, 37}, lon = {126, 142}, ramp = {2, 3}, tv = -33, m = 0.12},
      {id = "india", lat = {7, 31}, lon = {73, 92}, ramp = {3, 3}, tv = -25, m = 0.5},
      {id = "amazon", lat = {-16, 6}, lon = {-80, -44}, ramp = {2, 3}, tv = -40, m = 0.2},
      {id = "central_america", lat = {7, 20}, lon = {-94, -76}, ramp = {2, 3}, tv = -38, m = 0.15},
      {id = "us_south", lat = {28, 37}, lon = {-97, -75}, ramp = {2, 3}, tv = -32, m = 0.1},
      {id = "iran", lat = {25, 38}, lon = {44, 70}, ramp = {2, 3}, t = -33, a = 0.08, wild = true},
      {id = "dry_heart", lat = {34, 53}, lon = {44, 122}, ramp = {2, 4}, a = -0.5, wild = true},
      {id = "central_asia_pale", lat = {36, 49}, lon = {46, 86}, ramp = {3, 4}, a = -0.12},
      {id = "steppe", lat = {45, 56}, lon = {46, 118}, ramp = {3, 4}, t = 14, tv = 26, m = 0.4, wild = true},
      {id = "pontic", lat = {43, 53}, lon = {26, 52}, ramp = {2, 4}, tv = 30, m = -0.05, wild = true},
      {id = "tibet", lat = {28, 39}, lon = {74, 104}, ramp = {1.5, 3}, t = -50, tv = -12, m = -0.35, a = 0.1,
       wild = true},
      {id = "tundra_warm_old", lat = {60, 90}, lon = {0, 180}, ramp = {6, 1}, t = 18},
      {id = "tundra_warm_new", lat = {58, 90}, lon = {-170, -64}, ramp = {6, 1}, t = 16},
      {id = "tundra_bare_old", lat = {62, 90}, lon = {0, 180}, ramp = {4, 1}, tv = -12, m = -0.2},
      {id = "tundra_pale_old", lat = {66.5, 90}, lon = {0, 180}, ramp = {4, 1}, a = -0.2},
      {id = "tundra_bare_new", lat = {60, 90}, lon = {-170, -64}, ramp = {4, 1}, tv = -12, m = -0.2},
      {id = "tundra_pale_new", lat = {64.5, 90}, lon = {-170, -64}, ramp = {4, 1}, a = -0.2},
      {id = "cool_edge", lat = {52, 62}, lon = {-180, 180}, ramp = {2, 1}, a = 0.12},
      {id = "greenland_west", lat = {58, 90}, lon = {-62, -27}, ramp = {2, 2}, t = -18},
      {id = "greenland_north_east", lat = {69, 90}, lon = {-28, -10}, ramp = {1, 2}, t = -18},
      {id = "iceland", lat = {63, 67}, lon = {-26, -12}, ramp = {0.5, 1}, tv = -30, m = -0.2, a = 0.4},
      {id = "taiga", lat = {54, 65}, lon = {45, 140}, ramp = {3, 4}, m = 0.1},
      {id = "siberia_warm", lat = {57, 68}, lon = {56, 180}, ramp = {2, 6}, t = 3.5},
      {id = "canada", lat = {49, 62}, lon = {-125, -60}, ramp = {3, 4}, m = 0.1},
      {id = "plains", lat = {33, 53}, lon = {-106, -95}, ramp = {3, 3}, tv = 25, m = 0.3, a = -0.5, wild = true},
      {id = "sw_desert", lat = {24, 38}, lon = {-122, -103}, ramp = {3, 3}, a = -0.05},
      {id = "great_basin", lat = {36, 46}, lon = {-124, -103}, ramp = {2, 3}, a = -0.5, wild = true},
      {id = "patagonia", lat = {-56, -36}, lon = {-76, -62}, ramp = {3, 3}, a = -0.5, wild = true},
      {id = "australia", lat = {-31, -18}, lon = {118, 142}, ramp = {3, 4}, a = 0.2},
    },
    tile_belts_wander = {lat = 1.5, lon = 2},
    -- The biome size (0.3.0: larger biomes, so that each climate reads as one region): every new world's preset
    -- sets the spread's
    -- frequency controls, which climate.lua multiplies into each noise's input scale, to 1 / factor, so each
    -- wavelength above is factor times longer: the Moisture and Terrain type scale sliders (the properties under
    -- keys) and, beside Alien Biomes, its hot and cold frequency (the controls under ab_controls), which the
    -- temperature spread averages. No body changes: a world made before keeps its own values.
    size = {factor = 1.5, keys = {"control:moisture:frequency", "control:aux:frequency"},
            ab_controls = {"hot", "cold"}},
    -- The desert edge (0.3.0: the dry belts read as a lot of wasteland and not a lot of desert): the dry dirt
    -- between a
    -- desert's sand and the grass round it ran about 600 tiles wide at scale 12 along the Sahel, an even brown ribbon.
    -- Where the dry weight passes dry_from (fully dry_from + 1 / dry_gain on: the belts' outer ramps, Sicily and
    -- Andalusia, keep their scrub of dirt and grass), the 0.3.0 tile moisture is pulled away from mid, the middle of
    -- Alien Biomes' dirt band (0.4 to 0.6), by min(max, gain / max(floor, ragged factor)), so the dirt narrows by about
    -- gain, breaks where the factor is 0 and widens where it is high; the wet side rises no further than top, into the
    -- grass.
    -- bottom: the dry side falls no further than this, inside the sand's box, where sand still outscores Alien Biomes'
    -- water-mud (at moisture 0 the sand's fit is 0 and water-mud specks covered 3 percent of the Sahara).
    desert_edge = {dry_from = 0.2, dry_gain = 6, gain = 3.5, max = 30, floor = 0.05, mid = 0.5, top = 0.66,
                   bottom = 0.1},
    -- The ragged factor (0.3.0: no perfect bands): the width of the grey rim at a range's snow
    -- (ridges.cold.band), of the cold north's lead (north2) and of the desert edge's dirt (desert_edge) times
    -- clamp(mean + amplitude * noise, 0, max), one named noise of octaves from wavelength_tiles up (about 0.7 sd; in
    -- tiles, so the outline is ragged at player zoom at every scale), so a band varies along its length, is missing
    -- where the factor is 0 (about a fifth of it) and runs up to max times its mean width elsewhere (rarely: a factor
    -- held at a low max sat flat over wide patches and drew a band of one width there).
    ragged = {name = CT.CL_RAGGED, wavelength_tiles = 12, octaves = 6, persistence = 0.7, seed1 = 7621, mean = 1,
              amplitude = 1.6, max = 3},
    -- The lifts: tile_belts' boxes for what shipped after the first release, whose own table is an input of
    -- registered bodies. A lift adds to the moisture both a tree and a tile reads, under the natural top.
    -- russian_plain (Moscow read as a weak start): the spread's dry lows sat in Alien
    -- Biomes' grey dirt and sand box (T 0 to 30, moisture under 0.6) over a third of the Moscow window, a
    -- flat pale plain; lifted, those lows reach the cold grasses and the grey keeps to the deepest of them.
    -- j: Alien Biomes' cold trees grow in two narrow moisture bands, round 0.58 and past 0.86, so where the
    -- field crosses one on a long slope they drew a rope of forest one contour wide, an arc or a whole ring
    -- round a dry low (the ring 2,400 tiles north-east of Moscow), and the lift brings more of those slopes
    -- into the bands. j shakes the moisture trees and decoratives read by that much of `jitter`, so a rope
    -- scatters into loose stands; tiles keep their own field.
    -- bare: how much of m trees and decoratives do not take on Alien Biomes ground. Lifted, most of the field sat
    -- in the wet band round 0.9, the grass let its trees onto what had been grey dirt (their tile lists stop them
    -- there), and 0.14 of shake reached across the 0.3 between the bands, so forest fell evenly on the whole start:
    -- at seed 1000 within 256 tiles of Moscow 1.6 percent of the ground had 10 clear tiles round it, 20 in v0.1.2.
    -- A longer shake is no cure: at 32 tiles it draws its own contours as worms of forest.
    lifts = {
      {id = "russian_plain", lat = {49, 62}, lon = {24, 60}, ramp = {3, 5}, m = 0.22, bare = 0.22},
      -- nordic (0.3.0: southern Norway, Sweden and Finland should read green and lush): south of the
      -- snow line the ground is Alien Biomes' cold T 0 to 30, where the spread's lows below moisture 0.6 are its grey
      -- dirt and sand; lifted, those lows reach the cold grasses and the grey keeps to the deepest of them.
      {id = "nordic", since = "0.3.0", lat = {54, 65}, lon = {0, 33}, ramp = {2, 4}, m = 0.3},
      {id = "boreal", lat = {50, 74}, lon = {22, 180}, ramp = {4, 8}, j = 0.04},
      -- central_europe (the four start cities by eye): the spread's lows drew flat tan dirt across a third of
      -- Frankfurt's window and grey patches round Prague, in land that reads green; a smaller lift keeps
      -- them as pockets. Atlantic and Old World only: Europe's own biomes stay as they are.
      {id = "central_europe", lat = {45, 56}, lon = {-3, 26}, ramp = {3, 5}, m = 0.12,
       maps = {atlantic = true, olde_world = true}},
    },
    -- Vanilla tiles score the same moisture trees read, so a shake there draws a maze of dirt five tiles wide, on
    -- their cold islands too, where no temperature tells them from Alien Biomes ground: the shake is multiplied
    -- by tiles.scan's body, 0 where a vanilla land tile may lie and already in the Entity program.
    jitter = {wavelength_tiles = 5, seed1 = 7607},
    tile_belts_wild = {lift = 1000, cut = 0.5, fine = 0.25, keep = 0.8},
    -- The cold north: front is the snow line, {longitude, latitude}, west to east, after the real winter line: far
    -- north in the mild west, down across Russia, up again over the Pacific. d, degrees north of it, reads the
    -- meandering latitude plus meander times the climate meander, no new noise, and one basis noise of wave_px, so the
    -- line bends a degree or two and follows no latitude. The core stops at a cap of d: south_per_degree warmer per
    -- degree south, near_per_degree colder for near_degrees north of the line, far_per_degree after that. The cap
    -- lowers the plain temperature too, because Alien Biomes' snow trees (T -15 to 0, on frozen-snow-0 to 4 alone) need
    -- it: near_degrees and near_per_degree put the plain field at -7.5 or so, the middle of their window, and
    -- far_per_degree keeps it inside for 12 degrees more, to the real tree line. The tile belts that warm the tundra
    -- stop across belt_ramp from belt_from degrees south of the line. lead_degrees south of the line, over lead_ramp,
    -- the tile moisture stops at lead_top, so the cold grasses give way to Alien Biomes' grey and white ground, a band
    -- of wasteland that leads in.
    north = {
      front = {{-180, 58}, {-170, 61}, {-150, 62}, {-130, 61}, {-110, 58}, {-95, 55.5}, {-80, 53}, {-65, 52}, {-55, 51},
               {-40, 60}, {-20, 64.5}, {-5, 62.5}, {5, 61.5}, {12, 60.5}, {18, 60}, {25, 59}, {30, 56.5}, {37, 52.5},
               {45, 49.5}, {55, 50.5}, {75, 52}, {90, 51.5}, {105, 50.5}, {120, 50}, {135, 48.5}, {150, 50}, {165, 53},
               {180, 57}},
      meander = 1.5, wave = {seed1 = 7608, wave_px = 110, amplitude = 0.7},
      south_per_degree = 4, near_per_degree = 5, near_degrees = 1.5, far_per_degree = 0.5,
      belt_from = 6, belt_ramp = 4, lead_degrees = 5, lead_ramp = 1.5, lead_top = 0.56, aux_floor = 0.45, aux_high = 4,
      names = {d = CT.CL_N_D, drop = CT.CL_N_DROP, lead = CT.CL_N_LEAD, belt = CT.CL_N_BELT, temperature = CT.CL_T_AB_N,
               moisture = CT.CL_M_AB_N,
               grain = {field = CT.CL_GRAIN2, temperature = CT.CL_T_AB_G2, veg = CT.CL_T_AB_GV2,
                        moisture = CT.CL_M_AB_G2, aux = CT.CL_A_AB_G2}},
    },
    -- The cold north of 0.3.0, every other value as in north. Every Alien Biomes snow and ice tile walks at 0.8 of
    -- normal speed (frozen-snow-0 to 9, measured in the data dump), so the line runs north of the main lowland routes,
    -- the belt from Moscow past Kazan, Yekaterinburg, Omsk and Novosibirsk to Irkutsk, and the grey lead-in lies over
    -- them; the far north stays snow. The meander is smaller and the core rises south_per_degree per degree south of
    -- the line, twice north's, so the line's wander and the cold fringe south of it stay off that belt: north's reached
    -- 3.7 degrees each way and left patches of snow 3 degrees south of it. The clearing keeps snow off every spawn:
    -- within inner_tiles of the start, warped by warp of a noise of octaves from wave_tiles up, the temperature rises
    -- to at least t, and it fades out by outer_tiles. Tiles, not px: a start base is the same size at every scale.
    -- Where it warms the ground by m_span or more, the tile moisture rises to at least m, grey dirt's band: drier, the
    -- clearing was Alien Biomes' grey sand, which walks as slowly as its snow. The warp's noise frays that edge by
    -- m_fray times c (1 - c) of the clearing c, a quarter of m_fray at its half and none at its core or outside, or it
    -- drew an arc of one grey against another.
    north2 = {
      front = {{-180, 58}, {-170, 61}, {-150, 62}, {-130, 61}, {-110, 58}, {-95, 55.5}, {-80, 53}, {-65, 52}, {-55, 51},
               {-40, 60}, {-20, 64.5}, {-5, 64}, {5, 65.5}, {12, 66.5}, {18, 67}, {25, 67.5}, {37, 67.5}, {45, 67},
               {55, 67}, {60, 66.5}, {70, 66.5}, {80, 67}, {90, 68.5}, {100, 70}, {120, 70}, {135, 69.5}, {150, 68.5},
               {160, 67}, {170, 64}, {180, 62}},
      meander = 1, south_per_degree = 8,
      -- The taiga (0.3.0): the Eurasian line runs at the real tree line,
      -- 66 to 68 N and 70 N on Taimyr, not at 59 to 62.5 N, where it put most of the three taiga great forests on snow.
      -- South of it the continental core is still below Alien Biomes' frozen point from about 62.6 N in Siberia, so the
      -- core is held at least per_degree per degree south of the line, up to t: the cold trees' window (T 0 to 10, on
      -- grass), with the slope and the fray of the line. lon_from and lon_ramp keep it to Eurasia (Iceland and
      -- Greenland keep their own ground). The lead (lead_t) reads that slope as if it went on past t: on the floor
      -- itself, t plus noise sat under lead_t times the factor wherever the factor passed 2, and the rim spread in grey
      -- blotches 3 degrees deep.
      -- The tundra belts were drawn for ground north of the old line, under snow: on the cold grasses south of the new
      -- one, tundra_bare_old's tv -12 held the grasses' temperature under Alien Biomes' grey dirt and its m -0.2 and
      -- tundra_pale_old's a -0.2 drew grey and white dirt over most of 60 to 70 N. In the taiga, the ground south of
      -- w_north degrees north of the line (none from w_ramp further on: the snow's edge wanders with the noise) where
      -- the plain core is under m_core (fully under m_core_full: the boreal north, not the steppe south of it), the
      -- tiles take none of a belt's cooling of the grasses or pull on the aux, and their moisture lifts by m, no
      -- further than m_top: on cold ground at 0.9 and up Alien Biomes' water-mud outscores its grey and drew one-tile
      -- puddles.
      taiga = {t = 8, per_degree = 8, lon_from = -8, lon_ramp = 6, m = 0.45, w_north = 1, w_ramp = 0.5, m_core = 10,
               m_core_full = 4, m_top = 0.86},
      -- The lead (0.3.0: the grey band south of the line covered southern Scandinavia, the Baltic,
      -- Russia at 55 to 60 N, Siberia and Canada): the ground whose temperature is under lead_t times the ragged factor
      -- (climate.ragged), over lead_t_ramp, a rim on the snow's edge that breaks and widens along it, instead of
      -- north's even 5 degrees south of the line and everything north of it.
      lead_t = 4, lead_t_ramp = 1, ragged = true,
      clear = {inner_tiles = 96, outer_tiles = 224, t = 8, warp = 0.3, wave_tiles = 40, octaves = 3, persistence = 0.5,
               seed1 = 7609, m = 0.48, m_span = 4, m_fray = 3.2},
      names = {d = CT.CL_N_D2, drop = CT.CL_N_DROP2, lead = CT.CL_N_LEAD2, belt = CT.CL_N_BELT2,
               temperature = CT.CL_T_AB_N2, moisture = CT.CL_M_AB_N2, clear = CT.CL_N_CLEAR,
               clear_warp = CT.CL_N_CLEAR_W,
               grain = {field = CT.CL_GRAIN3, temperature = CT.CL_T_AB_G3, veg = CT.CL_T_AB_GV3,
                        moisture = CT.CL_M_AB_G3, aux = CT.CL_A_AB_G3}},
    },
    -- The North snow setting (0.3.1): one row per level, {value, index, shift_deg}. index is what a save bakes under
    -- key (tn_north_snow); shift_deg is how many degrees south the Eurasian line (north2.front) lies, in full
    -- where north2.taiga's longitude gate is 1 (from lon_from + lon_ramp), so Iceland, Greenland and the Americas
    -- keep the 0.3.0 line at every level. Another level is one more row. w is the snow weight for the zones that meet
    -- the snow: tn_north_snow_w_v1 is 1 north of the world's line (ragged as the frozen tile's edge is) and 0
    -- south of it, over ramp degrees; tn_north_rim_keep_v1 is a constant 1 that the grey rim is multiplied by and
    -- a zone may redirect.
    north_snow = {
      setting = "north_snow", key = CT.K_NORTH_SNOW,
      levels = {{value = "low", index = 0, shift_deg = 0}, {value = "medium", index = 1, shift_deg = 6},
                {value = "high", index = 2, shift_deg = 9}},
      ramp = 0.4, fray = 0.5,
      names = {w = CT.CL_N_SNOW_W, rim_keep = CT.CL_N_RIM_KEEP},
    },
    -- The cold north of 0.3.1, every other value as in north2: the line shifted by the world's level
    -- (north_snow), and the bodies that read it under names of their own.
    -- The Valdai square (valdai): a low of the released moisture spread (150 to 600 tiles of grey dirt in a square) in
    -- Russia's forest. In a soft box of lon and lat, its edge warped by up to warp_deg degrees of a noise of
    -- wave_tiles, the tile moisture is held at floor plus amp times a noise of wave_tiles at least, above Alien
    -- Biomes' grey dirt, and nowhere else.
    north3 = {
      rim_keep = CT.CL_N_RIM_KEEP,
      valdai = {lon = {29.5, 38}, lat = {54.5, 62}, ramp = 1.5, floor = 0.86, amp = 0.03, aux = 0.55,
                wave_tiles = 320, warp_deg = 0.4, seed1 = 7621, seed1_warp = 7622,
                names = {moisture = CT.CL_M_AB_V, aux = CT.CL_A_AB_V}},
      -- zone_drop (0.3.2): the drop with none inside a Chaos zone's heat ground (the zone's lift over the natural
      -- ceiling), which a preset with the zone on names over drop: High snow's drop of 12 to 15 degrees took the heat
      -- ground's rim under Alien Biomes' volcanic floor and drew its yellow and orange grasses there
      zone_drop = CT.CL_N_DROP4,
      names = {d = CT.CL_N_D3, drop = CT.CL_N_DROP3, lead = CT.CL_N_LEAD3, belt = CT.CL_N_BELT3,
               temperature = CT.CL_T_AB_N3, moisture = CT.CL_M_AB_N3, clear = CT.CL_N_CLEAR,
               clear_warp = CT.CL_N_CLEAR_W,
               grain = {field = CT.CL_GRAIN4, temperature = CT.CL_T_AB_G4, veg = CT.CL_T_AB_GV4,
                        moisture = CT.CL_M_AB_G4, aux = CT.CL_A_AB_G4}},
    },
    -- the coldness the fallback's pulls and spread read: 0 at core cold.t and warmer, 1 at
    -- cold.t - cold.span and colder
    cold = {t = 10, span = 30},
    -- The dry belts after EarthMaps' painted sand: the sand share of land per 10 x 10
    -- degree cell of the Atlantic raster (classes s and S) is 61 to 99 percent from 10 to 30 N between
    -- 20 W and 70 E, 42 to 82 percent from 30 to 40 N there, 24 to 82 percent from 40 to 50 N between
    -- 40 E and 120 E, 30 to 61 percent in North America's south-west, 45 to 76 percent in the Namib and
    -- Kalahari, 25 to 56 percent in Australia and 18 to 49 percent along the southern Andes, and 0 to 29
    -- percent in East Asia, India's east and the Americas' east. Each belt is
    -- a latitude and longitude box with soft edges: full weight ramp degrees inside each edge, 0 at it;
    -- the dry weight is the largest belt weight. A map reads only the belts that reach its extent.
    dry_belts = {
      {id = "sahara_arabia", lat = {9, 38}, lon = {-20, 80}, ramp = {3, 4}},
      {id = "horn_of_africa", lat = {-3, 13}, lon = {38, 53}, ramp = {3, 3}},
      {id = "central_asia", lat = {35, 51}, lon = {46, 120}, ramp = {3, 5}},
      {id = "north_america_sw", lat = {22, 44}, lon = {-122, -100}, ramp = {3, 4}},
      {id = "southern_africa", lat = {-30, -15}, lon = {11, 27}, ramp = {3, 3}},
      {id = "australia", lat = {-35, -17}, lon = {113, 147}, ramp = {3, 4}},
      {id = "south_america_sw", lat = {-56, -16}, lon = {-76, -63}, ramp = {3, 3}},
    },
    -- The Middle East's sand desert (1.0.0; new worlds beside Alien Biomes). Alien Biomes has two desert sands: tan
    -- dune sand (its temperature box 60 to 100) and cream sand, the pale yellow sand with dark specks (30 to 60, aux
    -- under 0.3). The Sahara reads tan. Arabia read tan, the Syrian desert tan with brown blocks, Mesopotamia four
    -- sand colours, and the Iranian plateau cream and beige. Inside the rows below, ground that is desert sand
    -- already takes the cream sand: its tile temperature falls to t and its tile aux to a, each only where it was
    -- above, so the Sahara, the Levant coast, Sinai and the Negev stay tan. Cream sand lies inside the temperate band
    -- (tiles.exclude), where only adopted Alien Biomes tiles stand and the base game's tiles take a bonus, so the
    -- band tests' bodies read the sand weight too, band_gain times beside the wild belt (tiles.lua): inside the rows
    -- the ground counts as a wild belt's, as the Iranian plateau's does by its iran belt.
    --   rows    capsules in degrees: every point within r of the segment from {lat, lon} `from` to `to`; a row with
    --           flats = true leaves patches of its old ground (tan in Arabia, beige on the plateau)
    --   keep    capsules the weight is none in, on the plain position (no warp: they guard real places): ground
    --           the rows' reach must not touch (the Caspian shore's forest); none within keep_ramp of the capsule's
    --           edge inward, fading out to the edge
    --   depth   the largest r minus distance over the rows, degrees inside the nearest edge, read at a point warped
    --           by up to about warp.degrees of two noises of octaves from warp.wavelength_px up, so no edge is an arc
    --   root    the exponent of the capsule's distance, a square root
    --   edge    the outline moves by mid_tiles of the tile scores' shared noise field number mix (24 to 768 tiles)
    --           and fray_tiles of the grain's (6 to 48), in tiles at every scale, and the ramp is ramp degrees times a
    --           width that follows the second warp between width_min and width_max, so the edge is ragged at two
    --           scales and swells and thins along its length
    --   flats   the patches of old ground: where a noise of octaves from wavelength_px up passes cut (soft wide, its
    --           rim moved by mid of the shared field number mix, by rag of the ragged factor and frayed by fray of
    --           the grain's noise) a flats row has no weight, in patches of no fixed shape and no smooth side
    --   cap     none at a range: the weight falls with the highland's temperature cap from cap.full to none at
    --           cap.from, so no snow, no grey rim and none of the rim's aux floor moves
    --   dry     none on moist ground: the weight falls with the tile moisture from dry.from to none at dry.full, the
    --           top of Alien Biomes' sand box and the middle of its dirt, so grass, forest ground and marsh keep their
    --           ground and the sand ends where it ended before
    --   ground  what counts as Alien Biomes ground, read on the temperature under the desert: past the temperate
    --           band's top once the tile belts' cooling is taken off again (from band_from, full at band_full), or
    --           lifted out of the band by a wild belt, by the band tests' own measure (tile_belts_wild.cut and fine,
    --           over wild_soft). On the temperate band's own ground the weight is none, so the grass and dirt north
    --           of 35 N keep their ground and their edge. On cold ground it is none too, up to cold_from (the top of
    --           Alien Biomes' grey band) and full from cold_full, whatever the cap reads there
    --   coast   none west of a line down the Red Sea's middle, the Gulf of Aqaba's and the rift to the Beqaa:
    --           Africa, Sinai, the Negev and the Levant coast stay tan, and the cream meets them at the water where
    --           there is water. The line is on the plain position (points, lon and land by lat between them), soft
    --           over soft_tiles and moved by mid_tiles of the shared field number mix and fray_tiles of the grain's
    --           noise, so over water it stays in the water; where it runs on land, in the rift, it takes land's
    --           values instead, ragged at the outline's two scales, and stands shift_tiles east, so its ragged edge
    --           stays off the Negev, the hills west of the Dead Sea and the valley floor. Past its ends it fades out
    --           over taper degrees
    --   band    the band tests' bodies with the sand weight; band_gain lifts the ground out of the band once the
    --           weight passes the wild cut over band_gain, while the tile temperature is still above the band
    --   under   each body reads what it wraps through its under name, which the preset points at whatever the key
    --           held, so it composes with any other body that wraps the same key
    -- What it leaves alone: the tile moisture (pulled dry, it cut the grass on a range's foothills along straight
    -- lines) and the temperate ground north of 35 N (turned to sand, it met the grass on one hard brown band).
    -- No green strip follows the Euphrates: only Old World draws that river, and its course moves with the scale, so
    -- a strip placed in degrees stood on bare sand beside the river at scale 12 and along no river at all on the
    -- other maps. A river-side green has to read the waterway's own distance.
    desert = {
      names = {warp_a = CT.DS_WARP_A, warp_b = CT.DS_WARP_B, depth = CT.DS_DEPTH, depth_flats = CT.DS_DEPTH_FLATS,
               keep = CT.DS_KEEP, flats = CT.DS_FLATS, w = CT.DS_W, sand = CT.DS_SAND, coast = CT.DS_COAST},
      tile = {temperature = {body = CT.DS_TILE_T, under = CT.DS_TILE_T_UNDER},
              aux = {body = CT.DS_TILE_A, under = CT.DS_TILE_A_UNDER}},
      band = {vanilla = CT.DS_VANILLA, vanilla_high = CT.DS_VANILLA_HIGH, vanilla_next = CT.DS_VANILLA_NEXT,
              vanilla_next_high = CT.DS_VANILLA_NEXT_HIGH, exclude = CT.DS_EXCLUDE},
      band_gain = 20,
      rows = {
        {id = "syrian_desert", from = {31.6, 38.6}, to = {34.6, 39.6}, r = 2.1, flats = true},
        {id = "jordan", from = {29.8, 36.0}, to = {32.8, 36.4}, r = 1.0, flats = true},
        {id = "iraq_west", from = {33.8, 40.6}, to = {30.8, 43.6}, r = 2.0, flats = true},
        {id = "mesopotamia", from = {35.2, 42.4}, to = {31.0, 46.6}, r = 1.8},
        {id = "arabia_north_east", from = {30.0, 46.0}, to = {22.8, 46.6}, r = 2.8, flats = true},
        {id = "hasa", from = {27.5, 49.2}, to = {24.6, 50.6}, r = 1.6, flats = true},
        {id = "hejaz", from = {28.8, 36.4}, to = {17.8, 42.4}, r = 2.4, flats = true},
        {id = "najd", from = {29.5, 41.0}, to = {21.0, 47.0}, r = 3.5, flats = true},
        {id = "rub_al_khali", from = {21.0, 46.5}, to = {19.6, 54.8}, r = 2.3, flats = true},
        {id = "trucial_coast", from = {23.5, 51.5}, to = {22.5, 55.5}, r = 1.6, flats = true},
        {id = "dasht_e_kavir", from = {34.8, 51.6}, to = {34.4, 56.4}, r = 1.9, flats = true},
        {id = "iran_centre", from = {33.6, 53.0}, to = {30.4, 56.4}, r = 1.8, flats = true},
        {id = "iran_east", from = {34.6, 56.4}, to = {31.0, 60.2}, r = 1.8, flats = true},
        {id = "dasht_e_lut", from = {32.0, 57.8}, to = {28.4, 59.2}, r = 2.0, flats = true},
      },
      keep = {
        {id = "caspian_shore", from = {37.2, 49.2}, to = {36.75, 53.8}, r = 0.9},
      },
      keep_ramp = 0.4,
      root = 0.5, ramp = 0.6,
      edge = {mix = 3, mid_tiles = 70, fray_tiles = 28, width_per_noise = 0.8, width_min = 0.3, width_max = 2.2},
      warp = {degrees = 0.6, wavelength_px = 16, octaves = 4, persistence = 0.5, seed1_a = 7651, seed1_b = 7652},
      flats = {wavelength_px = 8, octaves = 4, persistence = 0.6, seed1 = 7653, cut = 1.0, soft = 0.06, mix = 4,
               mid = 0.45, rag = 0.3, fray = 0.45},
      cap = {from = 200, full = 300},
      dry = {from = 0.45, full = 0.58},
      ground = {band_from = 65, band_full = 69, wild_soft = 0.02, cold_from = 30, cold_full = 36},
      -- {lat, lon, land} along the Red Sea's middle, the Gulf of Aqaba's and on up the rift through the Dead Sea and
      -- the Sea of Galilee to the Beqaa, south to north; land is 1 where the line runs on land
      coast = {points = {{13.5, 42.7, 0}, {14.5, 42.1, 0}, {15.5, 41.2, 0}, {16.5, 41.0, 0}, {17.5, 40.5, 0},
                         {18.5, 39.65, 0}, {19.5, 39.0, 0}, {20.5, 38.4, 0}, {21.5, 38.0, 0}, {22.5, 37.7, 0},
                         {23.5, 37.0, 0}, {24.5, 36.3, 0}, {25.5, 35.8, 0}, {26.5, 35.15, 0}, {27.5, 34.6, 0},
                         {28.0, 34.75, 0}, {28.2, 34.61, 0}, {28.4, 34.735, 0}, {28.6, 34.745, 0}, {28.8, 34.71, 0},
                         {29.0, 34.745, 0}, {29.1, 34.8, 0}, {29.2, 34.845, 0}, {29.3, 34.89, 0}, {29.4, 34.89, 0},
                         {29.6, 34.954, 1}, {31.0, 35.4, 1}, {31.6, 35.5, 1}, {32.8, 35.58, 1}, {33.3, 35.65, 1},
                         {34.0, 35.95, 1}, {34.6, 36.35, 1}},
               soft_tiles = 8, mid_tiles = 8, fray_tiles = 6, shift_tiles = 0,
               land = {soft_tiles = 40, mid_tiles = 55, fray_tiles = 25, shift_tiles = 70}, mix = 5, taper = 0.4,
               fields = {lat = 1, lon = 2, land = 3}},
      t = 45, a = 0.15,
    },
    -- Patagonia and the Monte as dry steppe (1.0.0; new Atlantic worlds beside Alien Biomes). Until 1.0.0 the dry
    -- belt and the patagonia tile belt held the tile moisture at the foot of Alien Biomes' sand box from Mendoza to
    -- Tierra del Fuego, so the land east of the Andes read as one dune sea in tan, beige and cream. The real ground is
    -- a cold steppe of bunch grass and low shrubs on gravel, with the Monte's dry shrubland to its north. Inside the
    -- rows the tile moisture rises to a target between Alien Biomes' dirt and grass bands, the tile aux moves to the
    -- band of its brown, beige and grey dirts, and the grasses' own temperature rises to the olive grass, each only
    -- toward its target, so wetter ground, the Pampas' green and the Chilean side keep what they had.
    --   rows    capsules in degrees: every point within r of the segment from {lat, lon} `from` to `to`
    --   depth   the largest r minus distance over the rows, degrees inside the nearest edge, read at a point warped by
    --           warp.degrees of the desert's two warps (16 reference pixels and up), so no edge is an arc
    --   root    the exponent of the capsule's distance, a square root
    --   edge    the outline moves by mid_tiles of the tile scores' shared noise field number mix (24 to 768 tiles) and
    --           fray_tiles of the grain's (6 to 48), in tiles at every scale, and the ramp is ramp degrees times a
    --           width that follows the second warp between width_min and width_max, so the edge is ragged at two
    --           scales and swells and thins along its length
    --   cap     none at a range: the weight falls with the highland's temperature cap from cap.full to none at
    --           cap.from, over the grey rim's top (ridges.cold top_t 30), so no snow, grey rim or rim moisture moves
    --   crest   none west of the Andes' crest, where a gap in the range leaves the cap high: the crest's longitude,
    --           linear in latitude between the points (the ranges table's Andes crest, then its southern end to the
    --           Strait of Magellan), on the plain position; the weight rises from none at from degrees east of it to
    --           full at full. The trees' reach takes it too
    --   patch   a noise of octaves from wavelength_tiles up, in tiles at every scale: grass and bare ground in patches
    --   m       the tile moisture's target: mid plus amp times the patches plus fine times the grain, within min and
    --           max; Alien Biomes' dirt is 0.4 to 0.6 and its grass from 0.6
    --   a       the tile aux's target: mid plus amp times shared field number mix, within min and max: brown dirt over
    --           temperature 60, beige from 30, grey under 30, all from aux 0.3; red and dusty rose start at 0.6
    --   veg     the grasses' temperature floor: floor plus amp times shared field number mix, within min and max, in
    --           Alien Biomes' olive grass (50 to 65); a warmer grass keeps its own (yellow from 65)
    --   dry     the aux and the grasses' temperature move only on ground that was sand: in full under dry.from of the
    --           tile moisture under the steppe, none from dry.full (Alien Biomes' dirt starts at 0.4), so grass and
    --           dirt that stood before (the Pampas' edge, the Chilean side, the Monte's grass, cold grey ground) keep
    --           their colour
    --   trees   Alien Biomes' wetland and grassland trees stand on its grass and dirt and not on its sand, so the new
    --           ground would carry their clumps where the steppe has almost none. On the rows marked thin, the living
    --           trees' multiplier falls by thin times the reach (the depth over those rows on the plain position, no
    --           warp, full from ramp degrees inside: a slow change in density, no line) times the dryness (none from
    --           the moisture trees read at dry.full, the forests of the Andes' east side at 0.8 and more; full under
    --           dry.from, the steppe at 0.1 to 0.25). The Monte keeps its trees.
    steppe = {
      names = {depth = CT.SP_DEPTH, w = CT.SP_W, patch = CT.SP_PATCH},
      tile = {moisture = {body = CT.SP_TILE_M, under = CT.SP_TILE_M_UNDER},
              aux = {body = CT.SP_TILE_A, under = CT.SP_TILE_A_UNDER},
              veg = {body = CT.SP_TILE_TV, under = CT.SP_TILE_TV_UNDER}},
      maps = {atlantic = true},
      rows = {
        {id = "monte", from = {-32.0, -68.0}, to = {-37.0, -67.0}, r = 1.8},
        {id = "north_patagonia", from = {-36.5, -69.5}, to = {-41.5, -67.0}, r = 2.4, thin = true},
        {id = "rio_negro", from = {-39.0, -67.0}, to = {-41.0, -63.8}, r = 1.6, thin = true},
        {id = "chubut", from = {-41.5, -69.0}, to = {-46.5, -68.0}, r = 2.8, thin = true},
        {id = "santa_cruz", from = {-46.0, -70.0}, to = {-52.0, -70.0}, r = 2.6, thin = true},
        {id = "santa_cruz_coast", from = {-46.8, -67.0}, to = {-50.5, -68.6}, r = 1.5, thin = true},
        {id = "fuego", from = {-52.2, -70.2}, to = {-54.6, -66.8}, r = 1.4, thin = true},
      },
      root = 0.5, ramp = 0.4,
      edge = {mix = 3, mid_tiles = 70, fray_tiles = 28, width_per_noise = 0.8, width_min = 0.3, width_max = 2.2},
      warp = {a = CT.DS_WARP_A, b = CT.DS_WARP_B, degrees = 0.8},
      cap = {from = 35, full = 55},
      crest = {points = {{-27.1097, -68.5414}, {-32.6531, -70.0117}, {-41.1608, -71.8875}, {-46.595, -73.3458},
                         {-49.2713, -73.0432}, {-51.5, -73.4}, {-53.0, -73.6}},
               from = 0, full = 0.3},
      patch = {wavelength_tiles = 32, octaves = 5, persistence = 0.55, seed1 = 7671},
      m = {mid = 0.6, amp = 0.16, fine = 0.1, min = 0.42, max = 0.85},
      a = {mid = 0.42, amp = 0.12, mix = 6, min = 0.24, max = 0.56},
      dry = {from = 0.36, full = 0.4},
      veg = {floor = 57, amp = 5, mix = 8, min = 51, max = 64},
      trees = {reach = CT.SP_REACH, body = CT.SP_TREES, under = CT.SP_TREES_UNDER, thin = 0.85, ramp = 1,
               dry = {from = 0.35, full = 0.5}},
    },
    names = {lat = CT.CL_LAT, lon = CT.CL_LON, dry = CT.CL_DRY, core = CT.CL_CORE, shift = CT.CL_SHIFT,
             ab = {temperature = CT.CL_T_AB, moisture = CT.CL_M_AB, aux = CT.CL_A_AB},
             grain = {field = CT.CL_GRAIN, temperature = CT.CL_T_AB_G, moisture = CT.CL_M_AB_G, aux = CT.CL_A_AB_G,
                      veg = CT.CL_T_AB_GV},
             belts2 = {m = CT.CL_BELT_M2, edge = CT.CL_BELT_EDGE2}, lift2 = {m = CT.CL_LIFT_M2},
             belts = {t = CT.CL_BELT_T, tv = CT.CL_BELT_TV, m = CT.CL_BELT_M, a = CT.CL_BELT_A,
                      wild = CT.CL_BELT_WILD},
             lift = {m = CT.CL_LIFT_M, bare = CT.CL_LIFT_BARE, j = CT.CL_LIFT_J, ab = CT.CL_M_AB_L,
                     grain = CT.CL_M_AB_GL},
             fallback = {temperature = CT.CL_T_FB, moisture = CT.CL_M_FB, aux = CT.CL_A_FB}},
    -- What a new world's preset points the climate properties and keys at. names above holds every body by its
    -- role and the bodies read one another through it, so it can never move; a re-point is one line here.
    points = {ab = {temperature = CT.CL_T_AB, moisture = CT.CL_M_AB_V, aux = CT.CL_A_AB_V},
              grain = {temperature = CT.CL_T_AB_G4, moisture = CT.CL_M_AB_N3, aux = CT.CL_A_AB_G4,
                       veg = CT.CL_T_AB_GV4},
              north = CT.CL_T_AB_N3,
              fallback = {temperature = CT.CL_T_FB, moisture = CT.CL_M_FB, aux = CT.CL_A_FB}},
    -- The climate bands the oracle (t3_oracle) and the climate checks read, in Alien Biomes units.
    bands = {frozen_below = 0, cold_below = 25, hot_from = 65, dry_below = 0.4},
    -- Koppen biomes (0.4.0). A quantizer in front of the three
    -- climate axes: four smooth fitted fields (annual mean temperature Tann, coldest- and warmest-month
    -- temperature Tcold/Twarm in Alien Biomes units, an annual precipitation proxy Pann, and a dry-season
    -- regime s_w), then the standard A/B/C/D/E cascade into the 14 shipped classes (tn_koppen_class_v1,
    -- prototypes/expressions/climate_koppen.lua), and a centroid snap (snap below) that drives tiles, trees
    -- and decoratives. The thresholds are in the mod's own field units (AB temperature, the moisture
    -- proxy), calibrated in game against an offline class-map preview, not real Celsius or mm.
    koppen = {
      key = K_KOPPEN,
      names = {tann = CT.KOPPEN_TANN, season = CT.KOPPEN_SEASON, tcold = CT.KOPPEN_TCOLD,
               twarm = CT.KOPPEN_TWARM, pann = CT.KOPPEN_PANN, sw = CT.KOPPEN_SW, class = CT.KOPPEN_CLASS},
      -- CAVEAT 5 (binding): fold the ridges highland field (tn_high_tile, 0..1, 0 off ridges) into Tann and
      -- so into Tcold/Twarm, so Tibet, the Alps and the Andes classify cold (tundra/boreal), not warm by
      -- latitude. lapse_t is the AB-temperature drop at full highland membership.
      highland = {lapse_t = 55},
      -- seasonality = clamp((amp0 + per_deg * |lat|) * (1 + continentality * cont_box), 0, max), where
      -- cont_box is the Eurasia-interior continental box of climate.temperature.continental (0..1), so
      -- continental interiors get colder winters (lower Tcold) and hotter summers (higher Twarm).
      season = {amp0 = 2, per_deg = 0.5, max = 45, continentality = 0.85},
      -- precip proxy Pann = moisture_mean (reused from climate.moisture) + the tile-belt m sum (CL_BELT_M),
      -- monotone in real precipitation. aridity Pth (proxy units) = base + per_t * Tann + the regime term
      -- (summer-dry lowers it, winter-dry raises it, the standard Koppen 0.5/1.0/1.4 P-sum spirit). B (arid)
      -- when Pann < Pth; desert when Pann < desert_frac * Pth, else steppe.
      aridity = {base = 0.3, per_t = 0.0025, summer_dry = -0.05, neutral = 0, winter_dry = 0.12, desert_frac = 0.62},
      -- the cascade thresholds, AB temperature units and the precip proxy. cd_tcold is the classic
      -- Koppen C/D boundary (-3C), kept swappable here. sw_hi/sw_lo are the summer-dry/winter-dry regime cuts
      -- (0.33 standard). Calibrated in game.
      thresholds = {a_tcold = 61, bwh_tann = 76, e_twarm = 42, ef_tann = -23, cd_tcold = -6,
                    cfa_twarm = 84, dfa_twarm = 74, dfb_twarm = 50, dfc_tcold = -58,
                    af_pann = 0.95, af_sw = -0.1, cs_sw = 0.2, sw_hi = 0.33, sw_lo = -0.33},
      -- the 14 class ids (in cascade order), the value tn_koppen_class_v1 returns per tile.
      classes = {af = 1, amaw = 2, bwh = 3, bwk = 4, bs = 5, cs = 6, cfa = 7, cfb = 8,
                 dfa = 9, dfb = 10, dfc = 11, dfd = 12, et = 13, ef = 14},
      -- the dry-season regime s_w = clamp(sum(summer-dry box weights) - sum(winter-dry box weights), -1, 1),
      -- reusing climate.tile_belts' boxes by id: Mediterranean boxes run summer-dry (+), monsoon and savanna
      -- boxes winter-dry (-). belt_weight and the belt wander mirror climate.lua.
      regime = {summer_dry = {"mediterranean", "california", "chile_central", "maghreb"},
                winter_dry = {"india", "se_asia", "south_china", "sahel", "east_africa", "north_australia"}},
      -- the boundary warp: the cascade temperatures wander by warp_t times the existing climate
      -- meander (no new noise call), so class edges are not latitude lines. The extra mid-wavelength warp and
      -- the centroid transition blend are in snap below.
      warp_t = 1.5,
      -- The centroid snap: each class's Alien Biomes
      -- (T, M, A) centroid, indexed by the class id (classes above), the value the axis-snap bodies
      -- point the climate axes at when Koppen is on. Every T is below the grain veg_cap (79.5), so no
      -- class signs orange grass (the palette allows none); every A is at or below aux ab_cap (0.5), so
      -- no class reaches Alien Biomes' alien palette. AB units, as the fields are.
      centroids = {
        {t = 75, m = 0.90, a = 0.30}, -- 1  Af       tropical rainforest
        {t = 72, m = 0.55, a = 0.35}, -- 2  Am/Aw    tropical monsoon & savanna
        {t = 76, m = 0.06, a = 0.42}, -- 3  BWh      hot desert
        {t = 40, m = 0.08, a = 0.42}, -- 4  BWk      cold desert
        {t = 52, m = 0.30, a = 0.40}, -- 5  BS       steppe / semi-arid
        {t = 60, m = 0.42, a = 0.38}, -- 6  Cs       mediterranean (dry summer)
        {t = 62, m = 0.70, a = 0.30}, -- 7  Cfa/Cwa  humid subtropical
        {t = 48, m = 0.72, a = 0.28}, -- 8  Cfb      oceanic / marine temperate
        {t = 45, m = 0.60, a = 0.30}, -- 9  Dfa/Dwa  continental, hot summer
        {t = 35, m = 0.62, a = 0.30}, -- 10 Dfb      continental, warm summer
        {t = 22, m = 0.58, a = 0.32}, -- 11 Dfc/Dwc  boreal / taiga
        {t = 8,  m = 0.50, a = 0.35}, -- 12 Dfd      extreme subarctic
        {t = -5, m = 0.45, a = 0.45}, -- 13 ET       tundra
        {t = -18, m = 0.40, a = 0.50}, -- 14 EF      ice cap
      },
      -- The snap: the axis is the class centroid blended toward the continuous
      -- mean by blend (0 at the centroid, 1 at the continuous field), so a class boundary ramps instead
      -- of stepping - the continuous field sits near the threshold value there, so the ramp interpolates
      -- the two neighbouring centroids - plus the existing per-axis spread noise (climate.lua T/M/A noise,
      -- the same seeds) so each class is a patchwork, plus a Tile-only fray on temperature
      -- (noise_layer_noise on the grain layer, already in the Tile program) that breaks Alien Biomes'
      -- razor tile-score edges. Moisture clamps to ab_top, aux folds under ab_cap, and the vegetation
      -- temperature caps at veg_cap so no spread can carry a class into orange grass.
      snap = {
        names = {class = CT.KOPPEN_CLASS2, t = CT.KOPPEN_T_SNAP, m = CT.KOPPEN_M_SNAP,
                 a = CT.KOPPEN_A_SNAP, tv = CT.KOPPEN_TV_SNAP},
        blend = {t = 0.25, m = 0.25, a = 0},
        -- the extra mid-wavelength boundary warp: a basis noise on class_v2's cascade
        -- temperatures, on top of v1's warp_t * meander, so class edges wander on a shorter wavelength
        -- and no edge runs straight (measured at zoom 0.25).
        warp2 = {amplitude = 0.3, wavelength_px = 3, octaves = 3, persistence = 0.6, seed1 = 7630},
        -- the Tile razor-edge fray on temperature (reuses the grain noise layer, already in the Tile
        -- program); veg_margin keeps the vegetation-temperature snap strictly under veg_cap.
        fray = {amplitude = 4, veg_margin = 0.5},
      },
      -- Composition and greenness. New names
      -- only; the released cold-north, zone and spawn bodies are untouched. Koppen is the base biome
      -- layer; the overrides win where they apply:
      --   temperature (compose.names.t) - the Koppen snap lowered by the cold north's drop north of the
      --   snow line (so the class deepens into Dfc/ET/EF and the frozen tile still overrides), and warmed
      --   to the spawn clearing's floor at spawn (a playable cold-grass start; the frozen weight is cleared
      --   by the same clearing in tiles.lua, so no spawn on snow). It reads the released drop by name
      --   (climate.north3.names.drop), which a preset with a zone on redirects to the zone drop
      --   (climate.north3.zone_drop), so the Chaos heat ground keeps its heat under High snow.
      --   The Chaos/Corrupted/Moscow zone tile look is a tile-score overlay (destroyed.lua/blue.lua) taken
      --   by max in data-final-fixes, so it wins inside its outline over the Koppen tiles and fades to the
      --   Koppen base at its edge with no new body here; the zone trees are the zone's own dead/excluded set.
      --   Scarcity is ore-only (resources.lua), orthogonal.
      compose = {
        names = {cool_t = CT.KOPPEN_COOL_T, t = CT.KOPPEN_CN_T, tv = CT.KOPPEN_CN_TV, m = CT.KOPPEN_M_SNAP2},
        -- Frankfurt/oceanic greenness (measured at Frankfurt, class Cfb, scale 12): the Koppen Cfb tile
        -- reads browner than the v0.3.2 OFF baseline because the ground is both drier and warmer than the
        -- continuous climate there (OFF tile moisture 0.74, temperature 29; the snap gave 0.67 and 40).
        -- The brown is dirt, not off-palette grass, so two per-class lifts on the Tile-only grain keys
        -- (new names, trees unchanged) bring the oceanic/temperate/boreal ground back to the OFF look:
        --   green - added to the moisture snap (Tile-only grain key), under ab_top so no forest ring
        --   cool  - subtracted from the tile temperature (via the cooled base compose.names.cool_t), so the
        --           oceanic/temperate ground reads as cool green grass, not the warm dry grass the snap
        --           centroid gives. Tile-only (the roles keep the plain snap for the Entity budget), a cheap
        --           per-class offset on the snap with no new noise.
        -- Indexed by the class id (koppen.classes); an absent class lifts 0.
        green = {[6] = 0.04, [7] = 0.08, [8] = 0.08, [9] = 0.06, [10] = 0.06, [11] = 0.04},
        cool = {[6] = 4, [7] = 8, [8] = 10, [9] = 6, [10] = 6, [11] = 4},
      },
    },
  },

  -- The tile hooks (ARCHITECTURE.md, "Stable hooks"). Every hook is
  -- if(tn_on > threshold, <on branch>, <off value>), so worlds without an Earth
  -- preset compile the off value alone (a gate inside the score cost default worlds Tile
  -- +7,489).
  --   vanilla   with Alien Biomes: the 19 vanilla land tiles AB takes off Nauvis, re-listed;
  --             on branch (vanilla score) + the tile's key, off value -inf; every key names one bonus
  --             body: +bonus on land where the temperate lean plus patch noise passes (lean
  --             1 - |T - lean_t| / lean_span), 0 elsewhere in the exclusion's temperate band, -inf
  --             outside it, on water and inside marshes (marsh_cut)
  --   exclude   with Alien Biomes: every AB land tile (by prefix) outside the adopted set (ab_adopted); on
  --             branch (AB score) + the key, off value AB's score; the body is -inf from temperate_from
  --             to temperate_below outside marshes, 0 elsewhere (only the adopted AB tiles in
  --             temperate bands)
  --   marsh     water-mud (registered on Nauvis without AB) and water-shallow (the ford hook's tile):
  --             on branch max(the key, AB's own expression where AB defines one); water-mud pools on
  --             land inside marshes where pool noise passes a cut that falls with the marsh weight,
  --             outside the start clearing; water-shallow along open water down to shallow_depth;
  --             without Alien Biomes grass-1 (the grass between the pools) behind a gated hook,
  --             (score) + the grass key, its own score off: the key's body gives +bonus on land inside
  --             marshes (marsh_cut), 0 elsewhere (with AB the vanilla tile keys keep vanilla out of
  --             marshes, so AB's wetland grass lies between the pools)
  --   palm      with or without Alien Biomes (so a world that gains it later meets the switch too):
  --             Earth presets point each AB palm's
  --             entity:<tree>:probability and :richness keys at Earth copies of its expressions with
  --             every local expression, the
  --             constant where AB reads elevation (the richness too: its locals are in its scope, so
  --             the isolation walk reads them with it)
  --             The plain hook form (a key whose prototype
  --             is elevation) added one processed expression to M2's default Entity program, which the
  --             zero-cost row compares, so the design takes the fallback instead: AB's
  --             prototypes stay untouched. data-final-fixes.lua builds the
  --             copies from the installed palm autoplace, each function they call carried as a local
  --             function named local_prefix plus its name, after holding the palms to `digest`, so no
  --             Alien Biomes version changes a registered copy: `digest` is tools/build_palms.py's
  --             digest of Alien Biomes `version`'s palms, and on any difference, a missing palm or no
  --             Alien Biomes each copy is `neutral`, and beside Alien Biomes both keys name it (no
  --             palms) and the log says why
  tiles = {
    vanilla = {
      tiles = {"grass-1", "grass-2", "grass-3", "grass-4", "dry-dirt", "dirt-1", "dirt-2", "dirt-3", "dirt-4",
               "dirt-5", "dirt-6", "dirt-7", "sand-1", "sand-2", "sand-3", "red-desert-0", "red-desert-1",
               "red-desert-2", "red-desert-3"},
      keys = {["grass-1"] = CT.VT_GRASS_1, ["grass-2"] = CT.VT_GRASS_2, ["grass-3"] = CT.VT_GRASS_3,
      ["grass-4"] = CT.VT_GRASS_4,
              ["dry-dirt"] = CT.VT_DRY_DIRT, ["dirt-1"] = CT.VT_DIRT_1, ["dirt-2"] = CT.VT_DIRT_2,
              ["dirt-3"] = CT.VT_DIRT_3,
              ["dirt-4"] = CT.VT_DIRT_4, ["dirt-5"] = CT.VT_DIRT_5, ["dirt-6"] = CT.VT_DIRT_6,
              ["dirt-7"] = CT.VT_DIRT_7,
              ["sand-1"] = CT.VT_SAND_1, ["sand-2"] = CT.VT_SAND_2, ["sand-3"] = CT.VT_SAND_3,
              ["red-desert-0"] = CT.VT_RED_0,
              ["red-desert-1"] = CT.VT_RED_1, ["red-desert-2"] = CT.VT_RED_2, ["red-desert-3"] = CT.VT_RED_3},
      off = "-inf",
      body = CT.VT_BONUS, body_grain = CT.VT_BONUS_G, body_high = CT.VT_BONUS_H,
      -- What a preset names: the bodies that fray the edge of the bonus's holes (the cream and beige ground at
      -- Frankfurt, a smooth blob with a razor edge at any zoom): fray times the grain's noise, 6 to 48 tiles, on the
      -- lean, on land warmer than fray_t to fray_t + fray_span. Colder, it would carry vanilla tiles past
      -- tiles.scan's body, whose 0 is the only thing telling them from Alien Biomes ground in the Entity program.
      -- Atlantic and Old World only: Europe keeps its released bonus.
      next = {grain = CT.VT_BONUS_F, high = CT.VT_BONUS_FH, maps = {atlantic = true, olde_world = true}},
      fray = 0.32, fray_t = 26, fray_span = 6,
      -- the vanilla tiles that read as dry, stony ground on a range: ridges.high.ground.lean lifts their score
      stony = {"dirt-4", "dirt-5", "dirt-6", "dry-dirt"},
      bonus = 10, lean_t = 45, lean_span = 30, lean_cut = 0.5,
      patch = {amplitude = 0.36, clamp = 0.45, wavelength_px = 10, octaves = 3, persistence = 0.5, seed1 = 7605},
      -- the patch's finest octave is 10 px (60 tiles at scale 6), so where it failed the lean the hole in
      -- the bonus showed as a smooth oval of Alien Biomes ground; the marsh pool noise, already in the
      -- Tile program, carries the edge down to 3 px at no cost
      fine = 0.15,
      -- marsh ground starts where the lifted moisture has cleared Alien Biomes' mid band (0.4 to 0.6, its
      -- beige and grey dirt): at 0.5 those tiles ran round every marsh as a one-width rim
      marsh_cut = 0.68,
      -- The mix (the combined build by eye): every vanilla land tile thresholds one moisture field, so
      -- at scale 6 each dry lobe stood in concentric bands, a contour map with an even dark rim. A
      -- noise shared by the tiles only wiggles the contours; each tile needs its own, so each adds
      -- amount times a noise of its own, the `first_seed1`-th and on of the tile noises, read through
      -- noise_share's fields as Alien Biomes' tiles read theirs, which the Tile
      -- program already holds (about 6,800 in noises of its own). A tile's score falls 20 per unit of moisture past
      -- its box, so a tile reaches about amount / 20 past it: the mix redraws boundaries and never puts
      -- sand in a wet meadow. It acts only where the tile holds its bonus: where the lean fails vanilla
      -- competes with Alien Biomes at its bare score, and a low mix there sinks every vanilla tile under
      -- water-mud, in pale blue patches. Beside Alien Biomes only. Europe stays out (its
      -- biomes stay as they are): it keeps the key's prototype, 0.
      mix = {key = CT.VT_MIX, off = "0", amount = 2.5, maps = {atlantic = true, olde_world = true}, first_seed1 = 1001},
    },
    -- The adopted Alien Biomes tiles: six land tiles plus water-mud.
    ab_adopted = {"vegetation-turquoise-grass-1", "vegetation-olive-grass-2", "mineral-grey-dirt-1",
                  "mineral-beige-dirt-1", "mineral-cream-sand-1", "mineral-grey-sand-1", "water-mud"},
    exclude = {
      prefixes = {"vegetation-", "mineral-"},
      key = CT.AB_EXCLUDE, off = "0", body = CT.AB_EXCLUDE_BODY, body_grain = CT.AB_EXCLUDE_BODY_G,
      temperate_from = 25, temperate_below = 65, marsh_cut = 0.68,
    },
    -- The noise share: Alien Biomes gives each of its 156 land tiles a
    -- noise of its own, 56,916 of Old World's 191,543 Tile complexity beside it and the whole
    -- of what lifts that program over the knee. On an Earth preset's on branch
    -- a tile reads two of twelve shared fields at equal weight instead: `weight` keeps
    -- the variance, a field pair of its own keeps two tiles' scores uncorrelated, or at +-0.5 where their
    -- pairs share one field, and tiles of one family, whose seeds run in order, never share a pair. `steps`
    -- is the distance from a tile's first field to its second, so seed s reads fields s % 12 and that
    -- plus steps[j % 5 + 1], j = floor(s / 12), signed by floor(j / 5) % 4: two tiles with one pair differ
    -- in sign.
    -- `call`: the fields are the tiles' own noise in this mod's seeds, and this mod ships none of that noise's
    -- arguments. At load time prototypes/installed.lua reads them from the installed tiles: of the calls of `fn`
    -- in the land tiles' scores, grouped by every argument but `own`, the group the most tiles hold, each exactly
    -- once, and builds each field from that call's own text with a seed from first_seed1 on. `digest` is that argument
    -- set's digest as Alien Biomes `version` writes it (tools/build_installed.py prints it from a dump). On any
    -- other set, or where no such call stands, every tile keeps its own noise, each field and each fray version's
    -- noise is `neutral`, and the log says so. data-final-fixes.lua knows a tile's call by the same reading.
    noise_share = {
      fields = {CT.TM_1, CT.TM_2, CT.TM_3, CT.TM_4, CT.TM_5, CT.TM_6, CT.TM_7, CT.TM_8, CT.TM_9, CT.TM_10, CT.TM_11,
                CT.TM_12},
      first_seed1 = 7741, weight = 0.7071, steps = {5, 3, 2, 4, 1}, sign_patterns = 4,
      call = {fn = "multioctave_noise", own = "seed1", version = "0.8.0", digest = "f38db1fb8dbaf999", neutral = "0"},
      -- The fray (the seam in the Alps' snow): a snow tile's score is its box, the same for all ten, plus a pair of
      -- these fields, so two snow tiles meet on one contour of smooth noise, and the seam can run dead straight
      -- for 34 tiles; no climate field moves it. Each field's next version, which a preset names in its place,
      -- adds noise_layer_noise, 6 to 48 tiles, finer than the contour bends, by `weights`, so no two of the ten
      -- tiles' pairs take the same share (they differ by 0.125 or more), and only where the tile temperature
      -- is under t, so every other ground keeps its fields to within span of it.
      -- noise and fine: noise_layer_noise alone decided between two ice tiles wherever their pairs nearly tied, so
      -- its 6-tile octave cut the ice into patches 3 to 8 tiles across, which the tile grid draws as squares with
      -- straight sides. `noise`, 16 to 128 tiles at `gain`, moves the seams instead, and noise_layer_noise at
      -- `fine` of it only roughens their edges, too weak to cut a patch of its own.
      noise = {seed1 = 7633, wavelength_tiles = 16, octaves = 4, persistence = 0.6, output_scale = 2 / 3, gain = 2},
      fine = 0.25,
      fray = {body = CT.TM_FRAY, amount = 0.8, t = 2, span = 4,
              weights = {0.25, -0.25, 0.875, -1, 1, 0.375, -0.375, 0.75, -0.75, -0.5, 0.5, -0.875},
              fields = {CT.TM2_1, CT.TM2_2, CT.TM2_3, CT.TM2_4, CT.TM2_5, CT.TM2_6, CT.TM2_7, CT.TM2_8, CT.TM2_9,
                        CT.TM2_10, CT.TM2_11, CT.TM2_12}},
      -- The fray on all ground (0.3.0, to the bar of no straight runs over about 6 tiles on natural edges).
      -- Two tiles of one box meet on a contour of their pairs' difference wherever the ground is not cold:
      -- Alien Biomes' yellow
      -- grasses and tan dirts (Bamako, Rio), and through the vanilla mix the vanilla grasses (New York), whose seams
      -- ran straight along the axes for 15 to 40 tiles. fray2's fields add the fray at `warm` on every ground and at
      -- fray's amount on the cold, so a preset naming them keeps the snow's seams as they were.
      -- fine: noise_layer_noise's share in fray2: at fray's 0.25 the seams bent only on fray's own 16 tiles and still
      -- ran straight for 20 tiles at Bamako.
      fray2 = {body = CT.TM_FRAY2, warm = 0.8, fine = 1,
               fields = {CT.TM3_1, CT.TM3_2, CT.TM3_3, CT.TM3_4, CT.TM3_5, CT.TM3_6, CT.TM3_7, CT.TM3_8, CT.TM3_9,
                         CT.TM3_10, CT.TM3_11, CT.TM3_12}},
    },
    -- The list hook (Alien Biomes' long tile restrictions): the game walks a
    -- restriction entry by entry for every tile of a chunk, so a vanilla land tile, on no AB list, costs a
    -- whole walk per AB decorative and tree, 19,000 entries a tile at Frankfurt, whatever the probability
    -- says. Beside Alien Biomes each AB-only autoplace on Nauvis with a list longer than vanilla.tiles
    -- takes the vanilla land tiles at the front of its list (they end the walk on their first entries)
    -- and, on its on branch, (own probability) * body. `body` is 0 where the vanilla tile body is not
    -- -inf on land, 1 elsewhere: it is that bonus body without its elevation term, so it reads no fine
    -- field and may run in the Entity program. `margin` widens its band and lean, in temperature units,
    -- over climate.grain's fray: the grain stays out of the Entity program (trees and decoratives keep
    -- the plain fields), so the body can only cover the frayed edge from outside. The fray's bound is 6
    -- (grain.temperature 3 times noise_layer_noise's peak of 2), but full cover strips Alien Biomes' trees
    -- along the band's edges, and a stray plant on a frayed edge reads better than a bare fringe, so 2 lets
    -- about 0.4 percent of these onto vanilla land. `types` pairs each prototype
    -- type with the settings group on_nauvis reads; Alien Biomes' palms keep their list (their keys already
    -- name Earth copies).
    scan = {body = CT.AB_KEEP_BODY, margin = 2,
            types = {{type = "optimized-decorative", group = "decorative"}, {type = "tree", group = "entity"}}},
    marsh = {
      water_mud = {tile = "water-mud", key = CT.MARSH_MUD, off = "-inf", body = CT.MARSH_MUD_BODY,
                   body2 = CT.MARSH_MUD_BODY2},
      water_shallow = {key = CT.MARSH_SHALLOW, off = "-inf", body = CT.MARSH_SHALLOW_BODY},
      grass = {tile = "grass-1", key = CT.MARSH_GRASS, off = "0", body = CT.MARSH_GRASS_BODY, bonus = 10},
      score = 50, shallow_score = 300, shallow_depth = 1.5, start_clear_tiles = 64,
      pool = {name = CT.MARSH_POOL, cut = 0.3, cut_per_weight = 1, wavelength_px = 3, octaves = 2, persistence = 0.5,
              seed1 = 7606},
      -- 0.3.0: the pool noise is in reference pixels, so at scale 12 its finest octave is 18 tiles and a pool edge
      -- ran straight for 25 tiles (Florida, Atlantic 12). fray is the same pool noise read at a point warped by up to
      -- about amplitude_tiles in tiles at every scale, so each edge wanders a few tiles while the pools keep their
      -- place and size (adding a noise to the field moved whole pools at scale 12). Only body2 reads it; new worlds
      -- name it.
      fray = {name = CT.MARSH_FRAY, wavelength_tiles = 8, octaves = 2, persistence = 0.5, seed1_x = 7607,
              seed1_y = 7608, amplitude_tiles = 4},
      -- the tile scores' marsh ground: the weight frayed by the pool noise, already in the Tile program,
      -- so the edge wanders with the pools and is no razor line beside the climate grain
      edge = "(" .. RG_MARSH_W .. " + 0.2 * " .. CT.MARSH_POOL .. ")",
    },
    palm = {body = CT.PALM_CONST, value = 1, reads = "elevation", local_prefix = "palm_", neutral = ZERO,
            digest = {version = "0.8.0", value = "d318706b4dd4b5b5", bases = {2166136261, 3735928559}, prime_low = 403,
                      prime_shift = 24, word = 4294967296, hex = "%08x", number = "%.9g",
                      reads = {"elevation", "moisture", "temperature", "aux"}},
            copies = {{tree = "tree-palm-a", field = "probability", key = CT.PALM_A_P_KEY, body = CT.PALM_A_P},
                      {tree = "tree-palm-a", field = "richness", key = CT.PALM_A_R_KEY, body = CT.PALM_A_R},
                      {tree = "tree-palm-b", field = "probability", key = CT.PALM_B_P_KEY, body = CT.PALM_B_P},
                      {tree = "tree-palm-b", field = "richness", key = CT.PALM_B_R_KEY, body = CT.PALM_B_R}}},
    -- Where a palm may stand on an Earth preset. Alien Biomes reads elevation to keep its palms to the beach, and the
    -- Earth copies read a constant there, since elevation may not reach the Entity program, so palms took every sand
    -- tile in their climate box, grey and white sand included, inland as far as the box ran; and a range lowers the
    -- temperature tiles read and not the one trees read, so they stood on cold sand on the ranges. The mask works in
    -- fields the Entity program already holds: warm_t on the temperature plus the tile belts, none inside the rocks'
    -- highland reach grown by margin_px, which covers the cold field's outline, and none north of lat, which holds all
    -- of Europe. A coast test on the coarse land field would keep palms on the Mediterranean, and costs Entity 2,927 on
    -- Old World at scale 6.
    palm_allow = {body = TFN.PALM_ALLOW, warm_t = 31, margin_px = 14, lat = 35.5},
    -- The mask of 0.3.0: palm_allow's tests, with warm, low Mediterranean shores let in north of lat. A shore is
    -- within band_px reference px of the coast line in prototypes/tables/palm_coast.lua (its header says how it was
    -- traced), on the warm stretches only, so the Adriatic's north, the Aegean and the Black Sea stay out. Distances
    -- are in degrees with longitude times lon_scale, cos(38 degrees) written out: the offline data stage's cosine
    -- need not match the game's to the last digit, and a body must build the same text in both.
    -- Alien Biomes' palms want moisture 0.4 to 1 and aux under 0.5, which the dry Mediterranean summer coast rarely
    -- reads, so the mask alone let in a few dozen. On those shores (north of lat and warm) each palm also takes shore:
    -- at most p per tile, falling to 0 at band_px from the coast line, in groves of a basis noise of wave_tiles. Alien
    -- Biomes' list still keeps them to sand. Most of these shores lie inside a range's rock band, which reaches
    -- ridges.high.rock_tiles past the range's own reach, so low reads the band less those tiles, with the fray, in px:
    -- reach_px, negative, is outside the reach. On Old World at scale 1 it let in 74 percent of the shore within 8 px
    -- of the sea and 3.8 percent of the grey, white and snow ground there.
    palm_allow2 = {body = TFN.PALM_ALLOW2, med = TFN.PALM_MED, band_px = 8, lon_scale = 0.788,
                   file = "prototypes/tables/palm_coast.lua",
                   shore = {body = TFN.PALM_SHORE, p = 0.05, seed1 = 7610, wave_tiles = 20, grove_mid = 0.5,
                            grove = 0.6, reach_px = -20}},
    -- The north and the massifs without Alien Biomes: the base game has no cold tile and a tint only darkens its tan
    -- art, so the mod has one tile of its own, a copy of `copy` with procedural art (tools/build_frozen_tile.py). It is
    -- defined on every load, so a world that later gains or loses Alien Biomes still finds it, and listed on Nauvis
    -- only without Alien Biomes. Its key holds off, so every other world compiles nothing; the body scores `score` on
    -- land north of the snow line and on a massif's snow, moved by `fray` degrees of the grain's noise.
    -- body2 reads climate.north2's line and its clearing, clear_deg degrees south per unit of clearing, and a new
    -- world's preset names it.
    frozen = {tile = ID .. "-frozen-ground", copy = "dirt-4", picture = "__" .. ID .. "__/graphics/frozen-ground.png",
              key = CT.FROZEN_KEY, body = CT.FROZEN_BODY, body2 = CT.FROZEN_BODY2, body3 = CT.FROZEN_BODY3,
              clear_deg = 30,
              off = "-inf", score = 100, fray = 0.5, cold = 8,
              art_scale = 2,
              -- Base decoratives list no tiles, so grass tufts covered this ground. They collide with doodad, and
              -- buildings and trees do not, so this keeps it bare and leaves it buildable.
              collision_mask = {layers = {ground_tile = true, doodad = true}},
              order = "b[natural]-b[dirt]-z[frozen]", map_color = {r = 214, g = 220, b = 229}},
  },

  -- Trees and great forests (ARCHITECTURE.md, "Stable hooks" and "Region layer").
  --   boost     every living tree's probability becomes if(gate > hooks.threshold, min(cap, (own) * key),
  --             own): the gate's prototype holds gate_off and Earth presets bake the great-forests toggle;
  --             the key's prototype holds key_off (a neutral multiplier) and Earth presets name the region
  --             layer's multiplier (regions.names.tree_mult: 1 + forest boost 2 times the forest sum).
  --             The base game's dead and dry trees are left alone (prototypes/tables/vanilla.lua),
  --             and so are Alien Biomes' palm prototypes (tiles.palm.copies' trees stay AB's)
  --             The lift (the taiga read as bare ground) is added to the probability
  --             before the multiplier: its key's prototype holds lift_off and Earth presets name lift_body,
  --             lift_per_sum times the forest sum times the boreal weight (0 at climate core
  --             boreal_from_t and warmer, 1 at boreal_full_t and colder), so the boreal great forests fill
  --             the gaps between vanilla's tree patches while every other forest keeps the multiplier alone
  --   palm      on Earth presets with Alien Biomes the palms read their Earth copies (tiles.palm), so each
  --             palm's probability key names its second version, the boost's formula around the
  --             registered first (design rule 21)
  --   restore   with Alien Biomes, the base game's living trees, rocks and decals AB takes off Nauvis,
  --             rebuilt from prototypes/tables/vanilla.lua: each behind the gate keys.on with its key, whose
  --             prototype holds the off value and which Earth presets point at its body, restricted to the
  --             vanilla land tiles (tiles.vanilla.tiles), so AB's land keeps AB's own. The restored trees
  --             read the Earth temperature on the vanilla scale (temperature, from the fallback climate's
  --             scale and clamp), and every richness key names one shared body. The decoratives AB keeps but
  --             takes off Nauvis are re-listed as (own score) + key, the key's prototype -inf and its body
  --             deco_on; the vanilla decoratives and dead trees AB restricts to its tiles get the vanilla land
  --             tiles appended. The re-listed scores read that vanilla-scale temperature too: their boxes are
  --             vanilla's 10 to 20, and Earth's temperature runs at 28 to 44 at Frankfurt beside AB
  --   decor     beside Alien Biomes the extended decoratives and the two garballos take the base game's score
  --             (prototypes/tables/vanilla.lua decor, under the local `box`, on that same temperature) wherever
  --             tiles.scan.body is 0, the band where vanilla land lies, and keep their own score elsewhere, so
  --             temperate ground keeps M1's plants (AB's score lays brown asterisks on every tile of it) and
  --             AB's land keeps AB's. `thin` scales a score that saturates outside the band: at 1 every tile
  --             holds one, a carpet, and the two desert bushes, at 0.4 each, fill a third of the Sahara with
  --             220 a chunk where the base game's sand holds 45
  trees = {
    boost = {gate = TFN.K_FORESTS_ON, gate_off = "0", key = TFN.K_TREE_MULT, key_off = "1", cap = 1,
             lift = TFN.K_TREE_LIFT, lift_off = "0", lift_body = TFN.TF_LIFT, lift_per_sum = 0.25,
             boreal_from_t = 18, boreal_full_t = 10},
    -- The great forests' ground (1.0.0; new worlds with the forests on, beside Alien Biomes). Until 1.0.0 a great
    -- forest only multiplied the trees its climate already grew, so a forest on dry ground stayed dirt with a few
    -- trees (the Black Forest at seed 1000: moisture 0.36, no grass, trees on 8 percent of its tiles).
    --   w, w_zone  the ground weight (regions.lua): the weight ramp, ramp_px wide, on the largest forest signed
    --           distance. edge moves each row's distance first: by share of its radius, at most cap_px, times the
    --           marsh outline noise plus bias, and by wide_share of its radius, at most wide_cap_px, times the
    --           warp's second noise (a disc, which only stands in for a real outline, takes disc_wide_share of its
    --           radius uncapped: at the cap the Amazon was a round green plate 6,400 tiles across on the whole-map
    --           view), with rough times the shared roughness on top. So a small forest shows lobes and bays with a
    --           frayed rim, never its exact disc, a continent-wide one loses the straight sides of its polygon on
    --           the whole-map view, and the bias leans outward, so a small forest keeps its ground at every seed.
    --           w_zone is w with none inside a Chaos zone's reach, where the ground, the trees and the dead forests
    --           stay the zone's own
    --   key     the weight a world reads, 0 by its prototype; a preset names w, or w_zone with a zone on
    --   trees   the key's weight for trees: none within spawn.inner_tiles of the start and all of it from
    --           spawn.outer_tiles, so no world starts inside a wall of trees
    --   moisture, tile_moisture  inside the weight the moisture trees and decoratives read rises to m (Alien Biomes'
    --           wetland trees peak at 0.9, under the natural top) and the tile moisture to tile_m plus tile_amp of a
    --           noise wave_tiles long (grass-1 on vanilla ground, Alien Biomes' grasses elsewhere; under 0.9, where
    --           its mud outscores cold ground), each only where it was lower, so no wet forest dries. glade: Alien
    --           Biomes' wetland trees live within 0.05 of 0.9, and at 0.9 everywhere they stood wall to wall (trees
    --           on 35 percent of the taiga's tiles, no ground in sight); the level falls by up to glade.m along a
    --           noise glade.wave_tiles long (mid and gain shape its share), so stands and open glades alternate
    --   lift    the tree lift's second version: the first, or lift_per_w times the trees' weight where that is more,
    --           so every great forest fills the gaps between the base game's tree patches, not the boreal ones alone
    --   mult, mult_zone  the tree multiplier on the ground weight, 1 + mult_per_w times it, so the denser trees stand
    --           on the forest's ground; mult_zone keeps the first multiplier inside a Chaos zone's reach
    ground = {key = TFN.K_FOREST_GROUND, key_off = "0", w = TFN.FG_W, w_zone = TFN.FG_W_ZONE, trees = TFN.FG_TREES,
              moisture = TFN.FG_M, tile_moisture = TFN.FG_TM, lift = TFN.TF_LIFT2, mult = TFN.FG_MULT,
              mult_zone = TFN.FG_MULT_ZONE,
              ramp_px = 8,
              edge = {share = 0.35, cap_px = 6, bias = 0.5, wide_share = 0.12, wide_cap_px = 40, disc_wide_share = 0.2,
                      rough = 2},
              spawn = {inner_tiles = 96, outer_tiles = 256},
              m = 0.9, tile_m = 0.84, tile_amp = 0.03, wave_tiles = 96, seed1 = 7641, lift_per_w = 0.45,
              glade = {m = 0.06, mid = 0.5, gain = 1.2, wave_tiles = 160, seed1 = 7642},
              mult_per_w = 3},
    -- next2: the second version times tiles.palm_allow2's mask, which a new world's preset names
    palm = {{key = CT.PALM_A_P_KEY, body = TFN.PALM_A_P2, base = CT.PALM_A_P, next = TFN.PALM_A_P3,
             next2 = TFN.PALM_A_P4},
            {key = CT.PALM_B_P_KEY, body = TFN.PALM_B_P2, base = CT.PALM_B_P, next = TFN.PALM_B_P3,
             next2 = TFN.PALM_B_P4, next3 = TFN.PALM_B_P5}},
    temperature = TFN.TF_VTEMP,
    decor = {box = "tn_vbox", thin = {["brown-asterisk"] = 0.5, ["brown-asterisk-mini"] = 0.25,
                                      ["red-desert-bush"] = 0.25, ["white-desert-bush"] = 0.25}},
    restore = {
      trees = TF_TREES, tree_off = "0", richness = TFN.TF_VTREE_R,
      rocks = TF_ROCKS, rock_off = "0",
      decoratives = TF_DECO, deco_off = "-inf", deco_body = TFN.TF_VDECO, deco_on = "0",
      -- The base game's tan rocks and sand decals list no tiles and read moisture and aux alone, so beside Alien Biomes
      -- they lay sand-coloured rocks on its snow and grey ground. A row's cold version, which a new world's preset
      -- would name, is its body times clamp((temperature - lo) / span, 0, 1): none at lo and colder, the whole body
      -- from lo + span. Defined and registered; no preset names them yet: not shown at player zoom in the full pack.
      cold = {lo = 2, span = 10},
    },
  },

  -- Exact coastlines (ARCHITECTURE.md, "Exact coastlines"). On a save whose Nauvis surface carries the key,
  -- scripts/bandfix.lua's on_chunk_generated handler rewrites, where the generated land or water is wrong,
  -- the tiles of the K
  -- pixels of the save's map and scale: scored reference pixels (not thin water, except the sea's) outside
  -- every waterway, canal, dam and ford footprint that touch the other class, or hold a tile the coast fit
  -- may misclassify at least half a reference pixel from the reference coast (the closed band rule).
  -- tools/build_geo.py emits each map's K+ table (K and its 8 neighbours) per scale into scripts/generated/
  -- and prices it in data-src/bandfix/.
  --   setting, key, on  the startup bool, the per-save name switch and its value when on: a map's preset
  --       carries the key only when the setting is on and the map is listed in maps; absent means off
  --   maps  the maps whose four flip checks passed (design rule 9), in map order; none
  --       until the test suite measures them, so the setting acts on no map yet. Atlantic, never priced,
  --       is never listed
  --   checks  each flip-checked map's measured configuration, its scale
  --   tables  per map with K+ tables: the geography ids (tn_geo) they serve. They follow the coast fit, the
  --       reference and the waterway footprints, so a later geography that keeps all three may be listed
  --   channel_px  thin water of the ocean class within this many pixels of open water along thin water counts as
  --       water in the tables (tools/build_geo.py sea_channels), so straits, sounds and inlets narrower than three
  --       pixels open up; a river drawn in that class stops being one here, and only the handler ever writes them
  --   float_margin_px  float32 slack over the lattice detail's bound (coast.detail_amplitude_px times
  --       coast.detail_clamp): a tile counts as possibly wrong unless the fit alone is right by more
  --   correction_tiles  the game's own tile stage grows water so every water tile lies in a 2 x 2 block of
  --       water (measured on Europe at scale 6: no generated water tile outside one, 1,078 tiles the fit
  --       makes land for sure turned water, every one within 2 tiles of possible water), so a tile also
  --       counts as possibly wrong while a tile of the other possible class lies within this many tiles
  --   mask_margin_tiles  waterway, canal, dam and basin footprints grow by this many tiles before they mask
  --       pixels; a ford spans its carve plus waterways.ford.margin_tiles
  --   spawn_keep_tiles  no tile within this radius of the spawn (world 0, 0) is written, so spawn-cities'
  --       start land guarantee and the spawn tile keep what the noise draws
  --   fill  K pixels whose band region holds no 2 x 2 block of tiles (an islet or a channel narrower than
  --       a pixel) are written whole instead of as a one-tile line; the tool marks them
  --   new_water, new_deep, land_fallback  the tile a written water tile gets, the one it gets in open sea
  --       (a pixel with no land among its 8 neighbours); land_fallback is written land in a chunk that shows no land
  --       on its lattice nor on ground_rings rings of chunks around it
  --   smooth  the write rule at scales from min_scale up: the reference blurred by a quadratic B-spline must read
  --       the pixel's class by at least threshold + wobble * a smooth tile noise (0 on a straight coast, 3/4 half a
  --       pixel from it, so 0.3 is a fifth of a pixel and the wobble moves it about a tenth of one; a wider band left
  --       every shore outside Europe riding the band's edge); in a fill pixel it reads within thin of its value at
  --       the pixel's centre, a blob. octaves
  --       name the noise's cells per period_tiles and weights, hash its lattice values, shift_tiles the second
  --       reading the deep-water line takes; written land takes the nearest land on a lattice of the chunk's
  --       own tiles, lattice_tiles apart; spline_centre and ease are the formulas' own constants
  --   row_cache  decoded table rows a peer keeps cached, the oldest evicted one at a time (a cache of
  --       shipped data, never game state): at scale 6 they span 12,288 tiles north to south
  --   generations  by map, the tables a later geography version reads, oldest first: version names their files,
  --       shared the version of their K+ table when an older one still holds because the coast did not move, and
  --       geographies the tn_geo ids that read them; every other id reads `version`. A released table is never
  --       emitted again: emission writes the map's newest generation only (ARCHITECTURE.md, "Release
  --       versioning policy", rule 6). sea_px: only
  --       a body of open water of at least this many pixels seeds channel_px, so a lake's rivers stay thin water.
  --   encoding  each table row is its first column, then runs (length - 1) * #symbol_order + symbol index
  --       (0-based in symbol_order), every number a varint of varint_base digits written in alphabet (a
  --       digit at or above varint_base continues the number); a decoded row is one symbol character per
  --       pixel: none (outside K+), water, land, a K pixel of either class (band), a fill pixel of either
  --       class, thin water, and a pixel of either class inside a waterway footprint (masked)
  bandfix = {
    setting = "exact_coast", key = BFN.K, on = ONE,
    maps = {"atlantic", "olde_world"},
    checks = {europe = {scale = 1}, atlantic = {scale = 4}, olde_world = {scale = 6}},
    tables = {europe = {geographies = {14, 23}}, atlantic = {geographies = {17, 20, 22}},
              olde_world = {geographies = {18, 19, 21}}},
    version = 1,
    generations = {olde_world = {{version = 2, geographies = {19, 21}, sea_px = 5000}},
                   atlantic = {{version = 2, geographies = {20, 22}, sea_px = 5000}}},
    float_margin_px = 0.01,
    channel_px = 40,
    correction_tiles = 2,
    mask_margin_tiles = 3,
    spawn_keep_tiles = 24,
    chunk_tiles = 32,
    row_cache = 2048,
    new_water = "water", new_deep = "deepwater", land_fallback = "sand-1", ground_rings = 3,
    smooth = {min_scale = 3, threshold = 0.3, wobble = 0.18, thin = 0.35, spline_centre = 0.75, ease = 3,
              period_tiles = 64, lattice_tiles = 4, shift_tiles = {21, 32},
              octaves = {{cells = 4, weight = 1}, {cells = 12, weight = 0.6}},
              hash = {x = 73, y = 179, seed = 283, modulus = 1021, mix = 31, half = 510},
              -- corners: on these maps written land takes the nearest land within reach steps of step tiles on a
              -- lattice that reaches past the chunk, read a little off the tile, and farther out the ground of the
              -- chunk's nearest corner, each the first land on rings of samples round that corner, the borders
              -- between corners wandering by wander of a chunk. Picked per chunk, the ground drew rectangles of one
              -- tile with straight sides along chunk borders wherever a coast was written far from its land (Danube
              -- delta, Amazon mouth, Gulf coast; the straight blocky edge).
              corners = {maps = {atlantic = true}, step = 8, reach = 2, rings = {16, 48}, wander = 0.4}},
    neighbours = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {-1, 1}, {1, -1}, {-1, -1}},
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    varint_base = 32,
    symbols = {none = "a", water = "b", land = "c", water_k = "d", land_k = "e", water_fill = "f",
               land_fill = "g", thin = "h", water_masked = "i", land_masked = "j"},
    symbol_order = {"none", "water", "land", "water_k", "land_k", "water_fill", "land_fill", "thin",
                    "water_masked", "land_masked"},
  },

  -- Cover for the land Exact coastlines writes (scripts/coastcover.lua). A group of
  -- its own: the bandfix group is hashed into the K+ tables' manifests.
  --   reach_tiles  the box the cover is read from: the written land's bounding box grown by this, inside the chunk
  --   min_land_tiles  a box with less land widens to the whole chunk
  --   types, entity_limit  the entities read and how many: the rate still counts every one of them
  --   decorative_land, decorative_limit  decoratives are read from the middle rows of the box, about this much land,
  --       and at most this many, a bound on a very dense patch
  --   tries  draws per tile until the sample holds something the tile's ground allows
  --   offset  a tree's position inside its tile, from each side, in tiles
  --   edge_gap  an entity's collision box keeps this clear of the chunk's edge, the reach of a neighbour's tree
  --   inset_tiles  every read keeps this many tiles inside the chunk's edge, past the reach of a neighbour's rock
  --   check_collision  create_decoratives' own check
  --   hash  the per-chunk seed (hashed from the chunk's position, so a draw does not depend on the order
  --       chunks generate in): a multiplicative step
  --       modulo 2^32 per coordinate, floor keeping it out of the seeds that are all one generator
  -- The band fix's write rule for geographies released after the first release, tn_geo from_geo and up. A save's
  -- tn_geo picks its rule in scripts/bandfix.lua, so no world made before keeps writing other tiles. This group
  -- stays out of `bandfix`, whose whole text the K+ tables' manifests hash. A pixel's straight side is the raster's:
  -- at scale 6 it ran 24 tiles dead straight round a pond and a strait, and 52 at Severnaya Zemlya, because the
  -- blur's edge moved only a tile either way. threshold and wobble move it half a pixel, and fill pixels by
  -- thin_wobble, so such a side wanders; a written shape comes in by about a quarter of a pixel for it. corners:
  -- every map's written land takes bandfix.smooth.corners' ground, or a rectangle of one tile stands wherever a
  -- coast is written far from land (Severnaya Zemlya's grey block, the stripes along its south coast).
  -- cap: where the wobble lifts the threshold past the middle of a narrow inlet nothing writes it, and the inlet
  -- pinches into a string of pools (Britain's box held 88 water bodies uncapped, 56 at this cap, 51 on the plain rule)
  -- correct_tiles: set_tiles' own flag. Off, the game draws no transition on a written tile.
  -- warp: scales from smooth.min_scale read the blurred reference at a tile moved by a smooth noise, so the coast
  -- leaves the raster's lines. px is the move's scale in reference pixels, limit_px its hard limit (under 1, or a read
  -- leaves K+), margin the field's dead zone where the generated coast stays (about a sixth of a pixel), steps the
  -- least blur lookup grid per pixel. Up to fine_scale the noise moves tiles at its own wavelengths; above it the rest
  -- of the move runs at wavelengths longer by scale / fine_scale, because a move longer than its wavelength folds the
  -- coast into speckle. period_tiles is coprime to smooth.period_tiles, so the two tables repeat together only past
  -- 3,900 tiles; shift_tiles decorrelate the x and y reads. lake_reach_tiles: how far from the spawn the spawn lake can
  -- reach. ground_warp: how far, in lattice steps, written land reads the ground beside it off its tile, so no node
  -- shows. pond_tiles: written water of at most this many tiles, with no water to join, stays land. slit_passes: how
  -- many times a written water tile one tile wide is taken back, as each pass can leave a shorter slit behind it.
  bandfix_next = {from_geo = 19, threshold = 0.55, wobble = 0.45, thin_wobble = 0.25, cap = 0.65, correct_tiles = true,
                  lake_reach_tiles = 128, ground_warp = 1.2, pond_tiles = 4, slit_passes = 2,
                  warp = {px = 1.4, limit_px = 0.95, margin = 0.3, steps = 8, fine_scale = 6, period_tiles = 61,
                          shift_tiles = {wx = 37, wy = 19, x = 29, y = 11, ywx = 5, ywy = 47},
                          octaves = {{cells = 5, weight = 1}, {cells = 14, weight = 0.6}, {cells = 30, weight = 0.3}}}},

  -- The band fix below smooth.min_scale for geographies from from_geo on (scripts/bandfix.lua). There a reference
  -- pixel is one or two tiles, so the closed rule wrote the raster itself: square islets, slabs and long straight
  -- sides. Instead a tile reads the reference blurred by kernel (each axis, over the pixel's neighbours) and
  -- interpolated between pixel centres, at the tile moved by bandfix_next's warp tables, and takes the class that
  -- field holds past margin, in every pixel of the K+ table. A pixel outside K+ holds the class of the nearest K+
  -- pixel, found within search_px. warp: per scale, fine scales the tables at their own wavelengths, coarse a copy
  -- coarse_x times longer, both in tiles, and limit_tiles caps the move on each axis; rough scales a tile noise of
  -- rough's octaves added to the field, which a warp alone leaves straight for ten tiles wherever it runs flat;
  -- pond_tiles is bandfix_next's for the scale. islet_tiles: land the field read, written or generated, of at most
  -- this many tiles with no land to join goes under, like written ponds.
  bandfix_low = {from_geo = 21, search_px = 6, kernel = {1, 2, 1}, margin = 0.1, islet_tiles = 8,
                 rough = {period_tiles = 59,
                          octaves = {{cells = 6, weight = 1}, {cells = 10, weight = 0.8}, {cells = 17, weight = 0.5}}},
                 warp = {{scale = 1, fine = 1.8, coarse = 1.2, coarse_x = 4, limit_tiles = 2.5, rough = 2,
                          pond_tiles = 6},
                         {scale = 2, fine = 2.4, coarse = 1.8, coarse_x = 3, limit_tiles = 4, rough = 2,
                          pond_tiles = 16}}},

  coastcover = {
    reach_tiles = 8,
    min_land_tiles = 32,
    types = {"tree", "simple-entity"},
    entity_limit = 32,
    decorative_land = 96,
    decorative_limit = 160,
    tries = 6,
    offset = 0.1,
    edge_gap = 0.6,
    inset_tiles = 2,
    check_collision = false,
    hash = {modulus = 4294967296, mul = 1103515245, add = 12345, coord = 65536, x = 2654435761, y = 2246822519,
            floor = 342},
  },

  -- City markers (ARCHITECTURE.md, "Control stage"). With the setting on,
  -- scripts/markers.lua draws one text per city of the save's map, its name from the map's city table, at the
  -- tile holding the city's reference pixel centre: world = geo - the city offset, the conversion of
  -- spawn-cities' force-spawn probe (t18_force_spawn). They are rendering objects in chart mode: drawn on the map
  -- view only, for every force, the same size on screen at every zoom; they need no charted chunk and no per-chunk
  -- event, so a headless check reads them with rendering.get_all_objects.
  --   centre       where a marker stands inside its tile, in tiles from the tile's corner
  --   text_scale   the text's size on screen (it scales with zoom)
  markers = {
    setting = "city_markers",
    render_mode = "chart",
    centre = 0.5,
    text_scale = 1.5,
    color = {r = 1, g = 0.9, b = 0.45, a = 1},
    alignment = "center",
    vertical_alignment = "middle",
  },

  -- The zones' ground and look (prototypes/zone_look.lua), beside Alien Biomes with each zone's startup setting on.
  -- shared: zone tiles that also lie outside the zones, so they keep their own values and take no zone creep (a census
  -- of whole Old World and Atlantic previews at scale 1: grey dirt 6 lies 77 to 87 percent outside the
  -- zone, every other Destroyed Europe tile 0 to 17 pixels, and the Blue tiles nowhere, by blue.no_blue).
  --   ground    pollution absorption per second on the zone's own ground (grass-1's), its walking speed and the cap
  --             on its vehicle friction (grass is 1.6; Alien Biomes' heat bands run 2 to 16 and slow the walk to 0.7);
  --             the zone's dead tree copies absorb as a living base tree does (tree-01's)
  --   plant     Space Age's tree farm plant, whose plot list gains the zones' ground and, beside Alien Biomes, the
  --             vanilla land tiles (tiles.vanilla.tiles, Space Age's own list), which Alien Biomes' list drops
  --   creep     the decals spawners and worms drop round them, in spawn_types' spawn lists; each zone takes a tinted
  --             copy of each, kept to the zone's own ground by collision layers (layers.zone on every zone's ground,
  --             layers.off .. id on every other tile)
  --   zones     per zone its setting, the config section whose exclusion holds its tiles, key, open and dead tree
  --             copies, a tint (a multiply: Destroyed Europe ember red, Blue blue-purple) and the light brown and
  --             dirt-coloured decoratives it recolours inside the zone, picked by their sprites' mean colour (hue 15 to
  --             50 degrees) and a census of boxes in each zone at Old World 12, less those the zone's exclusion keeps
  --             out already (Destroyed Europe drops white and garballo plants, Blue cracked mud). Destroyed Europe
  --             keeps its dark red-brown grass and crotons: on black ground they read as the ember it asks for
  zone_look = {
    shared = {"mineral-grey-dirt-6"},
    ground = {absorption = 7.5e-6, tree_absorption = 0.001, walking_speed = 1, friction_cap = 2},
    plant = {name = "tree-plant"},
    creep = {"enemy-decal", "enemy-decal-transparent", "worms-decal", "shroom-decal", "lichen-decal", "light-mud-decal",
             "dark-mud-decal"},
    spawn_types = {"unit-spawner", "turret"},
    layers = {zone = NOISE .. "zone_ground", off = NOISE .. "off_zone_"},
    color = {channels = {"r", "g", "b", "a"}, max = 255},
    zones = {
      {id = "chaos", setting = "destroyed_europe", section = "destroyed", tint = {r = 0.46, g = 0.19, b = 0.15},
       decoratives = {"cracked-mud-decal", "red-desert-bush", "brown-asterisk", "brown-asterisk-mini"}},
      {id = "blue", setting = "blue_corrupted", section = "blue", tint = {r = 0.5, g = 0.42, b = 0.95},
       decoratives = {"red-desert-bush", "white-desert-bush", "brown-asterisk", "brown-asterisk-mini",
                      "garballo-mini-dry", "brown-hairy-grass", "brown-carpet-grass", "red-croton"}},
    },
  },

  -- The size context of the scale labels, the scale tooltip and the preset descriptions. World sizes are maps'
  -- width_px and height_px times the scale; each preset description gives its map's size at preset_scales. No
  -- measured footprint of a late-game factory exists (every source found only reports one), so the locale
  -- carries two figures as reported community examples, never as measurements: each footprint below is its
  -- source's figure in tiles (r8_row names the source table's row), and every text that carries one says
  -- reported_phrase before it. The static locale check tests every figure of those texts against this table
  -- and the maps.
  size_context = {
    reported_phrase = "reported community examples",
    preset_scales = {1, 24},
    footprints = {
      {key = "core_1k", r8_row = "1k SPM", width = 683, height = 813,
       what = "a 1k SPM factory core blueprint, non-beaconed, without mining (Factorio 1.1.101)",
       source = "https://factoriobin.com/post/EhaghFV6"},
      {key = "megabase_9k", r8_row = "9.45k SPM", width = 10000, height = 6000,
       what = "the map of a 9.45k SPM megabase with every outpost, an upper bound (Factorio 0.17.79)",
       source = "https://forums.factorio.com/viewtopic.php?p=475463"},
    },
  },
}
