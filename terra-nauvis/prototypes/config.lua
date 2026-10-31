-- Terra Nauvis: the single source of names and constants (ARCHITECTURE.md, "Module map").
--
-- Pure data: this file reads no data, settings, game or script and calls no function, so the
-- settings, data and control stages (through require) and the Python tools (tools/tnconfig.py,
-- through luaparser) all read this one file. Every name the mod defines derives from ID or NOISE,
-- so renaming the mod is an edit here (D36). No other Lua file spells an Earth name or a map
-- coordinate (T16 name scan and design rules).

local ID = "terra-nauvis"
local NOISE = "tn_"

-- Per-save keys every Earth preset bakes (ARCHITECTURE.md, "Preset redirects"). tn_map and tn_geo
-- have no prototype: a preset world that lacks one fails loudly instead of drifting (S2), and
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

-- Each map's geography. Every name a map's elevation entry reads is bound to that map: its coordinate
-- chain carries the map's radii and extent and reads the city offset through the map's own
-- map-qualified per-save names, so a Map type pick alone (which sets only elevation) still renders the
-- map, and no map-dependent value reaches the entry through tn_map or a shared key. Each map keeps one
-- geography version until the first release.
-- The generated files (tools/build_geo.py): name-free data that a geography version's fit bodies
-- bind to its own chain, so a later version binds the same files instead of emitting new ones.
local EU_GEO_FILE = "prototypes/generated/geo_europe_v1.lua"
local EU_LAND_COARSE_FILE = "prototypes/generated/land_coarse_europe_v1.lua"

local AT_GEO_FILE = "prototypes/generated/geo_atlantic_v1.lua"
local AT_LAND_COARSE_FILE = "prototypes/generated/land_coarse_atlantic_v1.lua"

local OW_GEO_FILE = "prototypes/generated/geo_olde_world_v1.lua"
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
local EU_SPAWN_LAKE = NOISE .. "spawn_lake_europe_v1"
local EU_SPAWN_BIAS = NOISE .. "spawn_bias_europe_v1"
local START_LAND = NOISE .. "start_land_v1"
local DISTANCE = NOISE .. "distance_v1"
-- The spawn bearings per city and scale (tools/build_spawn.py): name-free data.
local EU_SPAWN_FILE = "prototypes/generated/spawn_europe_v1.lua"

local START_MASK2 = NOISE .. "start_mask_v2"

-- Waterways (milestone waterways). Per map and scale, four generated sets (tools/build_waterways.py):
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
local AT_WW_FILES = {"prototypes/generated/waterways_atlantic_s1_v1.lua",
                     "prototypes/generated/waterways_atlantic_s2_v1.lua",
                     "prototypes/generated/waterways_atlantic_s3_v1.lua",
                     "prototypes/generated/waterways_atlantic_s4_v1.lua",
                     "prototypes/generated/waterways_atlantic_s5_v1.lua",
                     "prototypes/generated/waterways_atlantic_s6_v1.lua"}
local OW_WW_FILES = {"prototypes/generated/waterways_olde_world_s1_v1.lua",
                     "prototypes/generated/waterways_olde_world_s2_v1.lua",
                     "prototypes/generated/waterways_olde_world_s3_v1.lua",
                     "prototypes/generated/waterways_olde_world_s4_v1.lua",
                     "prototypes/generated/waterways_olde_world_s5_v1.lua",
                     "prototypes/generated/waterways_olde_world_s6_v1.lua"}
-- Each map's sets, as the version that composes them names them (one table for both places).

-- The region layer (milestone region-layer): every region body carries its version suffix. These are its
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
  K_TILE_T = NOISE .. "tile_temperature",
  K_TILE_M = NOISE .. "tile_moisture",
  K_TILE_A = NOISE .. "tile_aux",
  VT_BONUS_G = NOISE .. "vtile_bonus_v2",
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
  MARSH_SHALLOW = NOISE .. "marsh_water_shallow",
  MARSH_SHALLOW_BODY = NOISE .. "marsh_water_shallow_v1",
  MARSH_GRASS = NOISE .. "marsh_grass",
  MARSH_GRASS_BODY = NOISE .. "marsh_grass_v1",
  PALM_CONST = NOISE .. "palm_const_v1",
  PALM_A_P = NOISE .. "palm_a_p_v1",
  PALM_A_R = NOISE .. "palm_a_r_v1",
  PALM_B_P = NOISE .. "palm_b_p_v1",
  PALM_B_R = NOISE .. "palm_b_r_v1",
  PALM_A_P_KEY = "entity:tree-palm-a:probability",
  PALM_A_R_KEY = "entity:tree-palm-a:richness",
  PALM_B_P_KEY = "entity:tree-palm-b:probability",
  PALM_B_R_KEY = "entity:tree-palm-b:richness",
}

-- Trees and great forests (milestone trees-forests). The great-forests gate (prototype 0; Earth presets 1 or
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
  ["huge-rock"] = {key = VR .. "huge_rock", body = VR .. "huge_rock_v1"},
  ["big-rock"] = {key = VR .. "big_rock", body = VR .. "big_rock_v1"},
  ["big-sand-rock"] = {key = VR .. "big_sand_rock", body = VR .. "big_sand_rock_v1"},
  ["medium-rock"] = {key = VR .. "medium_rock", body = VR .. "medium_rock_v1"},
  ["small-rock"] = {key = VR .. "small_rock", body = VR .. "small_rock_v1"},
  ["tiny-rock"] = {key = VR .. "tiny_rock", body = VR .. "tiny_rock_v1"},
  ["medium-sand-rock"] = {key = VR .. "medium_sand_rock", body = VR .. "medium_sand_rock_v1"},
  ["small-sand-rock"] = {key = VR .. "small_sand_rock", body = VR .. "small_sand_rock_v1"},
  ["red-desert-decal"] = {key = VR .. "red_desert_decal", body = VR .. "red_desert_decal_v1"},
  ["sand-decal"] = {key = VR .. "sand_decal", body = VR .. "sand_decal_v1"},
  ["sand-dune-decal"] = {key = VR .. "sand_dune_decal", body = VR .. "sand_dune_decal_v1"},
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

-- Ridges (milestone ridges; ARCHITECTURE.md milestone contract 8; S5). The toggle key tn_ridges is a name
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
  RD_HEIGHT = NOISE .. "ridge_height" .. RD_V,
  RD_FREE = NOISE .. "ridge_free" .. RD_V,
  RD_CLIFF_ELEVATION = NOISE .. "cliff_elevation" .. RD_V,
  RD_CLIFFINESS = NOISE .. "cliffiness" .. RD_V,
  RD_CLEAR = NOISE .. "ridge_clear" .. RD_V,
  EU_CREST = NOISE .. "crest_europe" .. RD_V,
  AT_CREST = NOISE .. "crest_atlantic" .. RD_V,
  OW_CREST = NOISE .. "crest_olde_world" .. RD_V,
  EU_OPENINGS = NOISE .. "openings_europe" .. RD_V,
  AT_OPENINGS = NOISE .. "openings_atlantic" .. RD_V,
  OW_OPENINGS = NOISE .. "openings_olde_world" .. RD_V,
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
  EU_DEPTH = NOISE .. "ridge_depth_europe" .. RD_V,
  AT_DEPTH = NOISE .. "ridge_depth_atlantic" .. RD_V,
  OW_DEPTH = NOISE .. "ridge_depth_olde_world" .. RD_V,
  EU_NEAR = NOISE .. "ridge_near_europe" .. RD_V,
  AT_NEAR = NOISE .. "ridge_near_atlantic" .. RD_V,
  OW_NEAR = NOISE .. "ridge_near_olde_world" .. RD_V,
  EU_KEEP = NOISE .. "ridge_keep_europe" .. RD_V,
  AT_KEEP = NOISE .. "ridge_keep_atlantic" .. RD_V,
  OW_KEEP = NOISE .. "ridge_keep_olde_world" .. RD_V,
  ORE_IRON = ORE .. "iron_ore_p" .. RD_V,
  ORE_COPPER = ORE .. "copper_ore_p" .. RD_V,
  ORE_COAL = ORE .. "coal_p" .. RD_V,
  ORE_STONE = ORE .. "stone_p" .. RD_V,
  ORE_URANIUM = ORE .. "uranium_ore_p" .. RD_V,
  ORE_OIL = ORE .. "crude_oil_p" .. RD_V,
}

-- Resources and enemies (milestone resources-enemies; ARCHITECTURE.md milestone contract 9; S6 A5 and A6E).
-- The hotspots toggle tn_hotspots is a name switch to tn_one and tn_zero, read by the Entity bodies
-- through a folded if(); each map's elevation entry reads its offshore stamp through the map-qualified
-- key tn_fields_<map>, a Map type fallback, so the entry stays a Map type entry (design notes,
-- resources-enemies). Every hotspot body reads the region layer's rows and tn_land_coarse only.
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
  EU_FIELDS_KEY = NOISE .. "fields_europe",
  EU_FIELDS = NOISE .. "fields_europe" .. RE_V,
  AT_FIELDS_KEY = NOISE .. "fields_atlantic",
  AT_FIELDS = NOISE .. "fields_atlantic" .. RE_V,
  OW_FIELDS_KEY = NOISE .. "fields_olde_world",
  OW_FIELDS = NOISE .. "fields_olde_world" .. RE_V,
}

-- The soft map edge and the inland lakes switch (milestone edge-and-lakes
-- 2026-10-29 16:05 and 17:50): the far-field box sinks land into deep water across a noise-warped band
-- just inside the extent (coast.edge_band), so a coast the box cuts reads as a wavy coastline, and a
-- map's inland lakes compose only when the per-save switch tn_inland_lakes names tn_one. Europe's
-- version 6 carries these names.
-- edge-and-lakes' names (one table: the 200-local limit)
local ELN = {
  K_INLAND_LAKES = NOISE .. "inland_lakes",
  EU6_ENTRY = NOISE .. "elevation_europe_v6",
  EU6_GEO = NOISE .. "geo_europe_v6",
  EU6_LAND_COARSE = NOISE .. "land_coarse_europe_v6",
  EU6_DETAIL = NOISE .. "detail_europe_v6",
  EU6_FAR = NOISE .. "far_europe_v6",
  EU6_GX = NOISE .. "gx_europe_v6",
  EU6_GY = NOISE .. "gy_europe_v6",
  EU6_U = NOISE .. "u_europe_v6",
  EU6_V = NOISE .. "v_europe_v6",
  EU6_CX = NOISE .. "cx_europe_v6",
  EU6_CY = NOISE .. "cy_europe_v6",
  EU6_LAKES = NOISE .. "inland_lakes_europe_v5",
  EU6_SHORE = NOISE .. "shore_europe_v3",
  EU_WW4 = {NOISE .. "ww_europe_s1_v4", NOISE .. "ww_europe_s2_v4", NOISE .. "ww_europe_s3_v4",
            NOISE .. "ww_europe_s4_v4", NOISE .. "ww_europe_s5_v4", NOISE .. "ww_europe_s6_v4"},
  EU_CANALS4 = {NOISE .. "canals_europe_s1_v4", NOISE .. "canals_europe_s2_v4", NOISE .. "canals_europe_s3_v4",
                NOISE .. "canals_europe_s4_v4", NOISE .. "canals_europe_s5_v4", NOISE .. "canals_europe_s6_v4"},
  EU_DAMS4 = {NOISE .. "dams_europe_s1_v4", NOISE .. "dams_europe_s2_v4", NOISE .. "dams_europe_s3_v4",
              NOISE .. "dams_europe_s4_v4", NOISE .. "dams_europe_s5_v4", NOISE .. "dams_europe_s6_v4"},
  EU_FORDS4 = {NOISE .. "fords_europe_s1_v4", NOISE .. "fords_europe_s2_v4", NOISE .. "fords_europe_s3_v4",
               NOISE .. "fords_europe_s4_v4", NOISE .. "fords_europe_s5_v4", NOISE .. "fords_europe_s6_v4"},
}
local EU_SETS4 = {ww = ELN.EU_WW4, canals = ELN.EU_CANALS4, dams = ELN.EU_DAMS4, fords = ELN.EU_FORDS4}
-- The Old World and Atlantic spawn city (first release, 2026-10-30): each map's spawn-city
-- setting moves the spawn through the city fold, with the spawn lake, start mask version 2 and the
-- inland lakes behind the inland lakes switch, and the soft map edge, as Europe's version 6 does:
-- Atlantic's and Old World's version 6. One table: the 200-local limit.
local OAS = {
  AT6_ENTRY = NOISE .. "elevation_atlantic_v6",
  AT6_GEO = NOISE .. "geo_atlantic_v6",
  AT6_LAND_COARSE = NOISE .. "land_coarse_atlantic_v6",
  AT6_DETAIL = NOISE .. "detail_atlantic_v6",
  AT6_FAR = NOISE .. "far_atlantic_v6",
  AT6_GX = NOISE .. "gx_atlantic_v6",
  AT6_GY = NOISE .. "gy_atlantic_v6",
  AT6_U = NOISE .. "u_atlantic_v6",
  AT6_V = NOISE .. "v_atlantic_v6",
  AT6_CX = NOISE .. "cx_atlantic_v6",
  AT6_CY = NOISE .. "cy_atlantic_v6",
  AT6_LAKES = NOISE .. "inland_lakes_atlantic_v1",
  AT6_SHORE = NOISE .. "shore_atlantic_v4",
  AT_CITY = NOISE .. "city_atlantic",
  AT_CITY_INDEX = NOISE .. "city_index_atlantic_v1",
  AT_CITY_CX = NOISE .. "city_cx_atlantic_v1",
  AT_CITY_CY = NOISE .. "city_cy_atlantic_v1",
  AT_SPAWN_LAKE = NOISE .. "spawn_lake_atlantic_v1",
  AT_SPAWN_BIAS = NOISE .. "spawn_bias_atlantic_v1",
  AT_SPAWN_FILE = "prototypes/generated/spawn_atlantic_v1.lua",
  AT_WW5 = {NOISE .. "ww_atlantic_s1_v5", NOISE .. "ww_atlantic_s2_v5", NOISE .. "ww_atlantic_s3_v5",
            NOISE .. "ww_atlantic_s4_v5", NOISE .. "ww_atlantic_s5_v5", NOISE .. "ww_atlantic_s6_v5"},
  AT_CANALS5 = {NOISE .. "canals_atlantic_s1_v5", NOISE .. "canals_atlantic_s2_v5", NOISE .. "canals_atlantic_s3_v5",
                NOISE .. "canals_atlantic_s4_v5", NOISE .. "canals_atlantic_s5_v5", NOISE .. "canals_atlantic_s6_v5"},
  AT_DAMS5 = {NOISE .. "dams_atlantic_s1_v5", NOISE .. "dams_atlantic_s2_v5", NOISE .. "dams_atlantic_s3_v5",
              NOISE .. "dams_atlantic_s4_v5", NOISE .. "dams_atlantic_s5_v5", NOISE .. "dams_atlantic_s6_v5"},
  AT_FORDS5 = {NOISE .. "fords_atlantic_s1_v5", NOISE .. "fords_atlantic_s2_v5", NOISE .. "fords_atlantic_s3_v5",
               NOISE .. "fords_atlantic_s4_v5", NOISE .. "fords_atlantic_s5_v5", NOISE .. "fords_atlantic_s6_v5"},
  OW6_ENTRY = NOISE .. "elevation_olde_world_v6",
  OW6_GEO = NOISE .. "geo_olde_world_v6",
  OW6_LAND_COARSE = NOISE .. "land_coarse_olde_world_v6",
  OW6_DETAIL = NOISE .. "detail_olde_world_v6",
  OW6_FAR = NOISE .. "far_olde_world_v6",
  OW6_GX = NOISE .. "gx_olde_world_v6",
  OW6_GY = NOISE .. "gy_olde_world_v6",
  OW6_U = NOISE .. "u_olde_world_v6",
  OW6_V = NOISE .. "v_olde_world_v6",
  OW6_CX = NOISE .. "cx_olde_world_v6",
  OW6_CY = NOISE .. "cy_olde_world_v6",
  OW6_LAKES = NOISE .. "inland_lakes_olde_world_v1",
  OW6_SHORE = NOISE .. "shore_olde_world_v4",
  OW_CITY = NOISE .. "city_olde_world",
  OW_CITY_INDEX = NOISE .. "city_index_olde_world_v1",
  OW_CITY_CX = NOISE .. "city_cx_olde_world_v1",
  OW_CITY_CY = NOISE .. "city_cy_olde_world_v1",
  OW_SPAWN_LAKE = NOISE .. "spawn_lake_olde_world_v1",
  OW_SPAWN_BIAS = NOISE .. "spawn_bias_olde_world_v1",
  OW_SPAWN_FILE = "prototypes/generated/spawn_olde_world_v1.lua",
  OW_WW5 = {NOISE .. "ww_olde_world_s1_v5", NOISE .. "ww_olde_world_s2_v5", NOISE .. "ww_olde_world_s3_v5",
            NOISE .. "ww_olde_world_s4_v5", NOISE .. "ww_olde_world_s5_v5", NOISE .. "ww_olde_world_s6_v5"},
  OW_CANALS5 = {NOISE .. "canals_olde_world_s1_v5", NOISE .. "canals_olde_world_s2_v5",
                NOISE .. "canals_olde_world_s3_v5", NOISE .. "canals_olde_world_s4_v5",
                NOISE .. "canals_olde_world_s5_v5", NOISE .. "canals_olde_world_s6_v5"},
  OW_DAMS5 = {NOISE .. "dams_olde_world_s1_v5", NOISE .. "dams_olde_world_s2_v5", NOISE .. "dams_olde_world_s3_v5",
              NOISE .. "dams_olde_world_s4_v5", NOISE .. "dams_olde_world_s5_v5", NOISE .. "dams_olde_world_s6_v5"},
  OW_FORDS5 = {NOISE .. "fords_olde_world_s1_v5", NOISE .. "fords_olde_world_s2_v5",
               NOISE .. "fords_olde_world_s3_v5", NOISE .. "fords_olde_world_s4_v5",
               NOISE .. "fords_olde_world_s5_v5", NOISE .. "fords_olde_world_s6_v5"},
}
local OAS_SETS = {
  atlantic = {ww = OAS.AT_WW5, canals = OAS.AT_CANALS5, dams = OAS.AT_DAMS5, fords = OAS.AT_FORDS5},
  olde_world = {ww = OAS.OW_WW5, canals = OAS.OW_CANALS5, dams = OAS.OW_DAMS5, fords = OAS.OW_FORDS5},
}
-- Destroyed Europe (milestone destroyed-europe; APPROVALS 10; D12; S3 section 6). The toggle key tn_destroyed
-- is a name switch to tn_one and tn_zero, baked on only when its setting is on and Alien Biomes is loaded
-- (FEAS-17: without AB the switch drops at the data stage). The key (K) and the bodies, one table so this
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
  temperature = NOISE .. "temperature_ab_v2",
  pool_europe = NOISE .. "city_pool_europe_v1",
  pool_atlantic = NOISE .. "city_pool_atlantic_v1",
  pool_olde_world = NOISE .. "city_pool_olde_world_v1",
}

-- Exact coastlines (milestone coast-band-fix): the per-save name switch a map's preset carries, set to the
-- neutral body tn_one, only when the startup setting is on and that map passed all four flip checks
--. Absent means off, and no prototype defines it: control code alone reads it. One table, as
-- the destroyed-europe names are (Lua's 200 locals per function).
local BFN = {
  K = NOISE .. "bandfix",
}

return {
  identity = {
    id = ID,
    title = "Terra Nauvis",
    version = "0.1.0",
    author = "Jake Mismas",
    factorio_version = "2.1",
    base_version = "2.1.24",
    setting_prefix = ID .. "-",
    noise_prefix = NOISE,
  },

  -- Reference-pixel conventions, mirrored by tools/earthgeo.py (U2): plate carree at
  -- px_per_degree; pixel (col, row) spans [col, col + 1) with its centre at
  -- lon = lon_left_edge + (col + 0.5) / px_per_degree and lat = lat_top_edge - (row + 0.5) / px_per_degree.
  -- At scale s, tile t samples pixel floor(t / s + wr) (the floor origin). The integer-corner
  -- offset is floor(s / corner_offset_divisor) tiles: the coordinate chain reads the fit at
  -- u = (gx - floor(s / 2)) / s + wr, so the tile holding a pixel centre, evaluated at its integer
  -- corner, reads the fit exactly at that centre at every integer scale (design notes 08:00; T1 and T3
  -- prove it at scales 1, 3 and 6 against a test build without it). This is the one copy of the
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
  -- the T16 append-only row against main and origin/main; ARCHITECTURE.md, "Release versioning
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

  -- Integer scales 1 to 6 tiles per reference pixel. The scale
  -- setting's locale labels carry each map's world size W s x H s in tiles (APPROVALS 1c); the T16
  -- locale row checks every label against these sizes.
  scales = {values = {1, 2, 3, 4, 5, 6}, default = 6},

  -- Mod settings. Values are short ASCII tokens, so labels can change without invalidating stored
  -- values (S11). Each milestone that adds a setting adds it here and to tests/design-rules.json.
  settings = {
    scale = {
      name = ID .. "-scale", type = "string-setting", setting_type = "startup",
      default_value = "6", allowed_values = {"1", "2", "3", "4", "5", "6"}, order = "a",
    },
    -- The spawn city per map (APPROVALS 1a, default random; APPROVALS 12 removes Luxembourg):
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
    -- The new maps' spawn cities (milestone olde-world-atlantic; APPROVALS 1a and 12, default random), in
    -- the same shape. No geography version reads them yet: the city fold that does arrives with each
    -- map's spawn record, and until then the gate refuses them (design notes 2026-10-28 16:30,
    -- olde-world-atlantic).
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
    -- Canals (milestone waterways; APPROVALS 1a and 6, default on): Kiel and Corinth on every map, Suez on
    -- Old World and Atlantic, Panama on Atlantic, open at max(7, scale) tiles; off keeps every
    -- isthmus closed, the drawn leaks under a dam. Baked per save through the toggle tn_canals.
    canals = {
      name = ID .. "-canals", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-d",
    },
    -- Great forests (milestone trees-forests; APPROVALS 1a and 4, default on; D26): the 16 adopted forests of
    -- the region layer hold about twice the trees of the land around them. Baked per save through the hook
    -- gate tn_forests_on.
    great_forests = {
      name = ID .. "-great-forests", type = "bool-setting", setting_type = "startup", default_value = true,
      order = "c-b",
    },
    -- Ridges (milestone ridges; APPROVALS 1a, D19, default on): cliff ridges along the 16 adopted ranges with
    -- rail-width passes, the only cliffs on a Terra Nauvis world. Baked per save through the toggle
    -- tn_ridges; off gives 0 cliffs (S5: a constant crest distance places none).
    ridges = {
      name = ID .. "-ridges", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-c",
    },
    -- Hotspots (milestone resources-enemies; APPROVALS 1a and 2, D21 to D24, default on): historical ore
    -- hotspots with heavier biters and the offshore fields' deepwater discs and wells. Baked per save
    -- through the toggle tn_hotspots and each map's offshore stamp key.
    hotspots = {
      name = ID .. "-hotspots", type = "bool-setting", setting_type = "startup", default_value = true, order = "c-a",
    },
    -- Inland lakes (milestone edge-and-lakes): spawn-cities'
    -- sparse random inland lakes. Off leaves the spawn lake at the chosen city, the rivers and the real
    -- lakes of the coast fit as the only fresh water. Baked per save through the toggle tn_inland_lakes.
    inland_lakes = {
      name = ID .. "-inland-lakes", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-e",
    },
    -- Destroyed Europe (milestone destroyed-europe; APPROVALS 1a and 10, D12, default off): Alien Biomes volcanic
    -- ground inside R7b's polygon, its edges moving with the map seed, never at the spawn. It needs Alien
    -- Biomes: without it the toggle bakes off and the mod warns. Baked per save through the
    -- toggle tn_destroyed.
    destroyed_europe = {
      name = ID .. "-destroyed-europe", type = "bool-setting", setting_type = "startup", default_value = false,
      order = "c-f",
    },
    -- Exact coastlines (milestone coast-band-fix; on by default since the order of 2026-10-30:
    -- Old World's and Atlantic's coasts need it to reach Europe's): a new world's preset bakes the band-fix
    -- key from it, for the maps bandfix.maps lists.
    exact_coast = {
      name = ID .. "-exact-coast", type = "bool-setting", setting_type = "startup", default_value = true,
      order = "c-g",
    },
    -- City markers (milestone extras; APPROVALS 1a, D28, default off): runtime-global, so any admin can switch
    -- it in a running game; on, the map view shows every city of the world's map (scripts/markers.lua).
    city_markers = {
      name = ID .. "-city-markers", type = "bool-setting", setting_type = "runtime-global", default_value = false,
      order = "d-a",
    },
  },
  setting_order = {"scale", "spawn_city_europe", "spawn_city_atlantic", "spawn_city_olde_world", "canals",
                   "great_forests", "ridges", "hotspots", "inland_lakes",
                   "destroyed_europe", "exact_coast", "city_markers"},

  -- Map-gen presets, sorted right after Default ("a") and before Rich resources ("b") (S13).
  -- withheld_with lists the mods whose presence withholds a preset (presets.lua defines no such
  -- preset while one is loaded). From europe-coast to region-layer every preset listed Alien Biomes:
  -- its 0.8.0 palms (tree-palm-a, tree-palm-b) read elevation in the Entity program, so beside it a
  -- preset carried its fine field there and broke design constraint 3 (design notes 2026-10-28 05:30,
  -- the preset withheld beside Alien Biomes). climate-tiles ships the palm switch (plan
  -- reconciliation 9: every Earth preset points each palm's keys at an Earth copy that reads the
  -- palm constant where AB reads elevation; tiles.palm), so the lists are empty and the presets are
  -- offered beside Alien Biomes again. Withholding acted on new worlds only: a world made from a
  -- preset that later loads beside a listed mod still names its fine field, so control code warns
  -- once and records it while a list names that mod (scripts/guards.lua; design notes 2026-10-28 07:20,
  -- a preset save beside Alien Biomes). A save made before the switch keeps its palms on its fine
  -- field for life: no load writes the palm keys into it.
  presets = {
    europe = {name = ID .. "-europe", map = "europe", order = "a-tn-a", withheld_with = {}},
    atlantic = {name = ID .. "-atlantic", map = "atlantic", order = "a-tn-b", withheld_with = {}},
    olde_world = {name = ID .. "-old-world", map = "olde_world", order = "a-tn-c", withheld_with = {}},
  },
  preset_order = {"europe", "atlantic", "olde_world"},

  -- The per-save keys (U6): map, scale and geography release are numbers every Earth preset bakes;
  -- land_coarse names the map's coarse land field; elevation, start_mask and distance
  -- are the vanilla properties the presets redirect (distance from spawn-cities: vanilla's starting
  -- ore and enemy-free start follow the spawn through it, S7); spawn_lake and spawn_bias name the
  -- map's spawn lake and starting-ore bias for the shared start mask v2 (spawn-cities).
  keys = {
    map = K_MAP, scale = K_SCALE, geo = K_GEO, land_coarse = K_LAND_COARSE,
    elevation = "elevation", start_mask = "starting_resources_lake_mask", distance = "distance",
    spawn_lake = K_SPAWN_LAKE, spawn_bias = K_SPAWN_BIAS,
    -- waterways: the hook gate (prototype off, Earth presets on), the ford key (prototype off, Earth
    -- presets name the map's ford set for the save's scale) and the canals switch (a toggle)
    on = K_ON, fords = K_FORDS, canals = K_CANALS,
    -- ridges: the toggle, the map's crest and openings keys, and the two cliff properties the presets
    -- redirect (S5)
    ridges = RDN.K_RIDGES, crest = RDN.K_CREST, openings = RDN.K_OPENINGS, band = RDN.K_BAND,
    cliff_elevation = "cliff_elevation", cliffiness = "cliffiness",
    -- resources-enemies: the hotspots toggle, each map's offshore stamp key and the enemy property
    hotspots = REN.K_HOTSPOTS, enemy = "enemy_base_probability",
    fields = {europe = REN.EU_FIELDS_KEY, atlantic = REN.AT_FIELDS_KEY, olde_world = REN.OW_FIELDS_KEY},
    -- edge-and-lakes: the inland lakes switch (a toggle)
    inland_lakes = ELN.K_INLAND_LAKES,
    -- destroyed-europe: the zone toggle
    destroyed = DE.K,
    -- coast-band-fix: the band-fix key (no prototype; control only)
    bandfix = BFN.K,
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
  -- retired. After the first release
  -- a map's versions only grow again: a later version takes names of its own and an older one stays
  -- defined, unchanged, for the worlds that name it.
  --
  -- geo_id is the version's geography release, the number its preset bakes as tn_geo. tn_geo is
  -- one id space across every map: each geography release of any map takes the next unused
  -- integer and keeps it for good, so no two maps or versions share one, and release_registry
  -- names each with its map, which is how control code resolves a save's tn_geo (ARCHITECTURE.md,
  -- "Release versioning policy", rule 4; tnconfig's id-space check). The next unused id is 19.
  geography = {
    europe = {
      map_type_order = "3000-tn-a",
      versions = {
        {
          -- Version 6: the spawn at the chosen city, the waterways, the shore body, the offshore field
          -- stamp, the soft map edge in its far-field box (edge = true: coast.edge_band) and its inland
          -- lakes read through the inland lakes switch (lakes: the per-save toggle key, a Map type
          -- fallback mirroring the setting), so with the switch off only the spawn lake, the waterways
          -- and the coast fit's own water remain.
          geo_id = 14,
          entry = ELN.EU6_ENTRY,
          geo = ELN.EU6_GEO, land_coarse = ELN.EU6_LAND_COARSE, detail = ELN.EU6_DETAIL, far = ELN.EU6_FAR,
          gx = ELN.EU6_GX, gy = ELN.EU6_GY, u = ELN.EU6_U, v = ELN.EU6_V,
          cx = ELN.EU6_CX, cy = ELN.EU6_CY, city_offset = {EU_CITY_CX, EU_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = EU_GEO_FILE, land_coarse = EU_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = ELN.EU6_CX, map_qualified = true, frozen = true},
            {name = ELN.EU6_CY, map_qualified = true, frozen = true},
            {name = EU_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.EU_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_europe", city = EU_CITY, city_index = EU_CITY_INDEX,
            spawn_lake = EU_SPAWN_LAKE, spawn_bias = EU_SPAWN_BIAS, inland_lakes = ELN.EU6_LAKES,
            start_land = START_LAND, distance = DISTANCE, bearings = EU_SPAWN_FILE,
          },
          waterways = EU_SETS4,
          shore = ELN.EU6_SHORE,
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
          -- Version 6 (Atlantic): the composition of Europe's version 6: the city fold moves every
          -- geography read, the spawn lake and starting-ore bias sit on the city's generated bearing
          -- (start mask version 2), and the inland lakes compose through the inland lakes switch.
          geo_id = 17,
          entry = OAS.AT6_ENTRY,
          geo = OAS.AT6_GEO, land_coarse = OAS.AT6_LAND_COARSE, detail = OAS.AT6_DETAIL, far = OAS.AT6_FAR,
          gx = OAS.AT6_GX, gy = OAS.AT6_GY, u = OAS.AT6_U, v = OAS.AT6_V,
          cx = OAS.AT6_CX, cy = OAS.AT6_CY, city_offset = {OAS.AT_CITY_CX, OAS.AT_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = AT_GEO_FILE, land_coarse = AT_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.AT6_CX, map_qualified = true, frozen = true},
            {name = OAS.AT6_CY, map_qualified = true, frozen = true},
            {name = OAS.AT_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.AT_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_atlantic", city = OAS.AT_CITY, city_index = OAS.AT_CITY_INDEX,
            spawn_lake = OAS.AT_SPAWN_LAKE, spawn_bias = OAS.AT_SPAWN_BIAS, inland_lakes = OAS.AT6_LAKES,
            start_land = START_LAND, distance = DISTANCE, bearings = OAS.AT_SPAWN_FILE,
          },
          waterways = OAS_SETS.atlantic,
          shore = OAS.AT6_SHORE,
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
          -- Version 6 (Old World): the composition of Europe's version 6: the city fold moves every
          -- geography read, the spawn lake and starting-ore bias sit on the city's generated bearing
          -- (start mask version 2), and the inland lakes compose through the inland lakes switch.
          geo_id = 18,
          entry = OAS.OW6_ENTRY,
          geo = OAS.OW6_GEO, land_coarse = OAS.OW6_LAND_COARSE, detail = OAS.OW6_DETAIL, far = OAS.OW6_FAR,
          gx = OAS.OW6_GX, gy = OAS.OW6_GY, u = OAS.OW6_U, v = OAS.OW6_V,
          cx = OAS.OW6_CX, cy = OAS.OW6_CY, city_offset = {OAS.OW_CITY_CX, OAS.OW_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = OW_GEO_FILE, land_coarse = OW_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = OAS.OW6_CX, map_qualified = true, frozen = true},
            {name = OAS.OW6_CY, map_qualified = true, frozen = true},
            {name = OAS.OW_CITY, map_qualified = true},
            {name = K_CANALS, map_qualified = false},
            {name = REN.OW_FIELDS_KEY, map_qualified = true},
            {name = ELN.K_INLAND_LAKES, map_qualified = false},
          },
          spawn = {
            city_setting = "spawn_city_olde_world", city = OAS.OW_CITY, city_index = OAS.OW_CITY_INDEX,
            spawn_lake = OAS.OW_SPAWN_LAKE, spawn_bias = OAS.OW_SPAWN_BIAS, inland_lakes = OAS.OW6_LAKES,
            start_land = START_LAND, distance = DISTANCE, bearings = OAS.OW_SPAWN_FILE,
          },
          waterways = OAS_SETS.olde_world,
          shore = OAS.OW6_SHORE,
          fields = REN.OW_FIELDS_KEY,
          edge = true,
          lakes = ELN.K_INLAND_LAKES,
        },
      },
    },
  },

  -- The chain every map-wide layer reads (the region layer, the climate and the layers after them):
  -- per map, the geography release (tn_geo) whose coordinate chain their bodies read. Since the
  -- superseded versions were retired that is each map's own version, so a preset world and a
  -- Map-type-only world read one chain per map. A later version that keeps the frame keeps this row (the
  -- same city offset under names of its own); a version that moves the frame needs layer bodies of its
  -- own.
  layer_chain_geo = {europe = 14, atlantic = 17, olde_world = 18},

  -- The water slider (D15: inert on Earth presets). Vanilla 2.1.23 reads control:water:* in exactly
  -- three named expressions (core/prototypes/noise-programs.lua): water_level (10 * log2 of the
  -- size), segmentation_multiplier (the frequency) and nauvis_segmentation_multiplier (1.5 times
  -- the frequency). Earth elevation reads none of them, but vanilla cliffs, moisture and aux still
  -- do on an Earth preset, so every Earth preset bakes each as its value at the default slider: the
  -- slider then moves nothing, and at the default slider nothing changes (design notes 2026-10-28
  -- 05:30, the water slider). The gate's water_inert row walks every root of each preset for any
  -- other reader and previews the slider's extremes.
  water_slider = {
    {key = "water_level", value = 0},
    {key = "segmentation_multiplier", value = 1},
    {key = "nauvis_segmentation_multiplier", value = 1.5},
  },

  -- Every property_expression_names key any Earth preset sets, for every geography version (each
  -- version's own city offset names join it; tnconfig checks every key a version's preset bakes is
  -- here): the missing-name guard, T14 and the Nauvis-only surface guard read it, which strips
  -- exactly these keys from every other surface (D33). From climate-tiles also the climate redirects,
  -- the marsh keys, the palm keys, and with Alien Biomes the vanilla tile keys and the exclusion key
  -- (absent keys are by design on a world without AB).
  preset_keys = {"elevation", "starting_resources_lake_mask", K_LAND_COARSE, K_MAP, K_SCALE, K_GEO,
                 "water_level", "segmentation_multiplier", "nauvis_segmentation_multiplier",
                 "distance", EU_CITY, K_SPAWN_LAKE, K_SPAWN_BIAS, K_ON, K_FORDS, K_CANALS,
                 "temperature", "moisture", "aux", CT.MARSH_MUD, CT.MARSH_SHALLOW, CT.MARSH_GRASS,
                 CT.VT_GRASS_1, CT.VT_GRASS_2, CT.VT_GRASS_3, CT.VT_GRASS_4, CT.VT_DRY_DIRT, CT.VT_DIRT_1,
                 CT.VT_DIRT_2, CT.VT_DIRT_3,
                 CT.VT_DIRT_4, CT.VT_DIRT_5, CT.VT_DIRT_6, CT.VT_DIRT_7, CT.VT_SAND_1, CT.VT_SAND_2, CT.VT_SAND_3,
                 CT.VT_RED_0, CT.VT_RED_1,
                 CT.VT_RED_2, CT.VT_RED_3, CT.AB_EXCLUDE, CT.PALM_A_P_KEY,
                 CT.PALM_A_R_KEY, CT.PALM_B_P_KEY, CT.PALM_B_R_KEY,
                 -- trees-forests: the great-forests gate and multiplier key, and with Alien Biomes the restored
                 -- vanilla trees', rocks' and decoratives' keys
                 TFN.K_FORESTS_ON, TFN.K_TREE_MULT, TFN.K_TREE_LIFT,
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
                 "entity:iron-ore:probability", "entity:copper-ore:probability", "entity:coal:probability",
                 "entity:stone:probability", "entity:uranium-ore:probability", "entity:crude-oil:probability",
                 -- resources-enemies: the richness keys, the enemy property, the hotspots toggle, each map's
                 -- offshore stamp key and, with the Oil Rig loaded, the offshore-oil keys
                 "entity:iron-ore:richness", "entity:copper-ore:richness", "entity:coal:richness",
                 "entity:stone:richness", "entity:uranium-ore:richness", "entity:crude-oil:richness",
                 "enemy_base_probability", REN.K_HOTSPOTS, REN.EU_FIELDS_KEY, REN.AT_FIELDS_KEY, REN.OW_FIELDS_KEY,
                 "entity:offshore-oil:probability", "entity:offshore-oil:richness",
                 -- edge-and-lakes: the inland lakes switch and the new versions' city offset names
                 ELN.K_INLAND_LAKES, ELN.EU6_CX, ELN.EU6_CY,
                 -- the Old World and Atlantic spawn city: the maps' city numbers and the new versions' offset names
                 OAS.AT_CITY, OAS.OW_CITY, OAS.AT6_CX, OAS.AT6_CY, OAS.OW6_CX, OAS.OW6_CY,
                 -- destroyed-europe: the zone toggle (temperature and the city numbers are listed above)
                 DE.K,
                 -- coast-band-fix: the band-fix key, on presets whose map the setting acts on
                 BFN.K},

  -- The fine field per map (design constraint 3): map key -> {the map's elevation entry and every term
  -- only it reads}. The constant-coast twin turns each into a constant; no Entity,
  -- decorative or Cliff root on a Terra Nauvis preset may reach one. The start land guarantee is
  -- analytic but belongs to the field by ARCHITECTURE.md's firewall rule; the spawn lake, the bias,
  -- distance and the city fold are firewall-clean (the start mask reads the lake and the bias).
  firewall = {
    -- each map's entry and the terms only it reads; the ford sets reach Tile only, through the
    -- water-shallow hook
    europe = {
      ELN.EU6_ENTRY, ELN.EU6_GEO, ELN.EU6_DETAIL, ELN.EU6_FAR, ELN.EU6_LAKES, ELN.EU6_SHORE, REN.EU_FIELDS,
      START_LAND, ELN.EU_WW4[1], ELN.EU_WW4[2], ELN.EU_WW4[3], ELN.EU_WW4[4], ELN.EU_WW4[5], ELN.EU_WW4[6],
      ELN.EU_CANALS4[1], ELN.EU_CANALS4[2], ELN.EU_CANALS4[3], ELN.EU_CANALS4[4], ELN.EU_CANALS4[5],
      ELN.EU_CANALS4[6], ELN.EU_DAMS4[1], ELN.EU_DAMS4[2], ELN.EU_DAMS4[3], ELN.EU_DAMS4[4], ELN.EU_DAMS4[5],
      ELN.EU_DAMS4[6], ELN.EU_FORDS4[1], ELN.EU_FORDS4[2], ELN.EU_FORDS4[3], ELN.EU_FORDS4[4], ELN.EU_FORDS4[5],
      ELN.EU_FORDS4[6],
    },
    atlantic = {
      OAS.AT6_ENTRY, OAS.AT6_GEO, OAS.AT6_DETAIL, OAS.AT6_FAR, OAS.AT6_LAKES, OAS.AT6_SHORE, REN.AT_FIELDS,
      START_LAND, OAS.AT_WW5[1], OAS.AT_WW5[2], OAS.AT_WW5[3], OAS.AT_WW5[4], OAS.AT_WW5[5], OAS.AT_WW5[6],
      OAS.AT_CANALS5[1], OAS.AT_CANALS5[2], OAS.AT_CANALS5[3], OAS.AT_CANALS5[4], OAS.AT_CANALS5[5],
      OAS.AT_CANALS5[6], OAS.AT_DAMS5[1], OAS.AT_DAMS5[2], OAS.AT_DAMS5[3], OAS.AT_DAMS5[4], OAS.AT_DAMS5[5],
      OAS.AT_DAMS5[6], OAS.AT_FORDS5[1], OAS.AT_FORDS5[2], OAS.AT_FORDS5[3], OAS.AT_FORDS5[4], OAS.AT_FORDS5[5],
      OAS.AT_FORDS5[6],
    },
    olde_world = {
      OAS.OW6_ENTRY, OAS.OW6_GEO, OAS.OW6_DETAIL, OAS.OW6_FAR, OAS.OW6_LAKES, OAS.OW6_SHORE, REN.OW_FIELDS,
      START_LAND, OAS.OW_WW5[1], OAS.OW_WW5[2], OAS.OW_WW5[3], OAS.OW_WW5[4], OAS.OW_WW5[5], OAS.OW_WW5[6],
      OAS.OW_CANALS5[1], OAS.OW_CANALS5[2], OAS.OW_CANALS5[3], OAS.OW_CANALS5[4], OAS.OW_CANALS5[5],
      OAS.OW_CANALS5[6], OAS.OW_DAMS5[1], OAS.OW_DAMS5[2], OAS.OW_DAMS5[3], OAS.OW_DAMS5[4], OAS.OW_DAMS5[5],
      OAS.OW_DAMS5[6], OAS.OW_FORDS5[1], OAS.OW_FORDS5[2], OAS.OW_FORDS5[3], OAS.OW_FORDS5[4], OAS.OW_FORDS5[5],
      OAS.OW_FORDS5[6],
    },
  },

  -- Per geography release: {release = <version>, map = <map key>, geography = <tn_geo id>, names =
  -- {<noise names>}, files = {<generated files>}}. Every name here is registered in
  -- tests/frozen.json by the milestone that adds it and never changes in place. Each row
  -- names one geography id with the map it belongs to; an id appears in one row only and never
  -- moves to another map, and each geography version's geo_id has its row under its map
  -- (tnconfig's id-space check).
  release_registry = {
    -- The region layer (milestone region-layer): its fixed names, and under files the region table, which
    -- releases every name regions.lua composes from it (a stem of regions.names.row, a row id and the
    -- suffix; a warped query point per share). It belongs to no geography. tools/tnconfig.py composes
    -- those names by the same rule, so the dump facts, the T16 rows and build_zip.py --release see each.
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
               CT.VT_GRASS_1, CT.VT_GRASS_2, CT.VT_GRASS_3, CT.VT_GRASS_4, CT.VT_DRY_DIRT, CT.VT_DIRT_1, CT.VT_DIRT_2,
               CT.VT_DIRT_3,
               CT.VT_DIRT_4, CT.VT_DIRT_5, CT.VT_DIRT_6, CT.VT_DIRT_7, CT.VT_SAND_1, CT.VT_SAND_2, CT.VT_SAND_3,
               CT.VT_RED_0, CT.VT_RED_1,
               CT.VT_RED_2, CT.VT_RED_3, CT.VT_BONUS, CT.VT_BONUS_G, CT.AB_EXCLUDE, CT.AB_EXCLUDE_BODY,
               CT.AB_EXCLUDE_BODY_G, CT.K_TILE_T, CT.K_TILE_M, CT.K_TILE_A, CT.MARSH_MUD,
               CT.MARSH_POOL, CT.MARSH_MUD_BODY, CT.MARSH_SHALLOW,
               CT.MARSH_SHALLOW_BODY, CT.MARSH_GRASS, CT.MARSH_GRASS_BODY},
    },
    -- The palm switch (climate-tiles): the constant and the copies of Alien Biomes 0.8.0's palm autoplace,
    -- built on every load from the generated table, with or without Alien Biomes (tiles.palm).
    {
      release = "0.1.0",
      names = {CT.PALM_CONST, CT.PALM_A_P, CT.PALM_A_R, CT.PALM_B_P, CT.PALM_B_R},
      files = {"prototypes/generated/palms_ab_v1.lua"},
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
    -- The ridges (milestone ridges): no geography of their own; each map's crest and openings bodies read
    -- prototypes/tables/ranges.lua, and the shared bodies with the toggle's neutral pair (waterways') read
    -- them.
    {
      release = "0.1.0",
      names = {RDN.EU_CREST, RDN.AT_CREST, RDN.OW_CREST, RDN.EU_OPENINGS, RDN.AT_OPENINGS, RDN.OW_OPENINGS,
      RDN.EU_BAND, RDN.AT_BAND, RDN.OW_BAND, RDN.RD_HEIGHT,
               RDN.EU_WANDER_U, RDN.AT_WANDER_U, RDN.OW_WANDER_U, RDN.EU_WANDER_V, RDN.AT_WANDER_V, RDN.OW_WANDER_V,
               RDN.EU_RUN, RDN.AT_RUN, RDN.OW_RUN, RDN.EU_DEPTH, RDN.AT_DEPTH, RDN.OW_DEPTH,
               RDN.EU_NEAR, RDN.AT_NEAR, RDN.OW_NEAR, RDN.EU_KEEP, RDN.AT_KEEP, RDN.OW_KEEP, RDN.RD_FREE,
               RDN.RD_CLIFF_ELEVATION, RDN.RD_CLIFFINESS, RDN.RD_CLEAR, RDN.ORE_IRON, RDN.ORE_COPPER, RDN.ORE_COAL,
               RDN.ORE_STONE, RDN.ORE_URANIUM,
               RDN.ORE_OIL},
      files = {"prototypes/tables/ranges.lua"},
    },
    -- The hotspot, ramp, sea and enemy bodies and the wrappers of the pack's live autoplace (milestone
    -- resources-enemies): no geography of their own. The Oil Rig's offshore-oil wrappers exist only
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
               REN.ORE_URANIUM_P2, REN.ORE_URANIUM_R, REN.ORE_OIL_P2, REN.ORE_OIL_R, REN.OFFSHORE_P, REN.OFFSHORE_R},
      files = {"prototypes/tables/hotspots.lua"},
    },
    -- The soft map edge and the inland lakes switch (milestone edge-and-lakes): each map's next geography
    -- version, every name its own. The switch's prototype is a Map type fallback that mirrors the
    -- inland lakes setting, so no row registers it (U3's one exemption).
    {
      release = "0.1.0",
      map = "europe",
      geography = 14,
      names = {
               ELN.EU6_GX, ELN.EU6_GY, ELN.EU6_U, ELN.EU6_V, ELN.EU6_GEO, ELN.EU6_LAND_COARSE, ELN.EU6_DETAIL,
               ELN.EU6_FAR,
               ELN.EU6_ENTRY, ELN.EU6_CX, ELN.EU6_CY, ELN.EU6_LAKES, ELN.EU6_SHORE, REN.EU_FIELDS,
               START_MASK2, EU_CITY_INDEX, EU_CITY_CX, EU_CITY_CY, EU_SPAWN_LAKE, EU_SPAWN_BIAS, START_LAND, DISTANCE,
               K_ON, K_FORDS, ONE, ZERO,
               ELN.EU_WW4[1], ELN.EU_WW4[2], ELN.EU_WW4[3], ELN.EU_WW4[4], ELN.EU_WW4[5], ELN.EU_WW4[6],
               ELN.EU_CANALS4[1], ELN.EU_CANALS4[2], ELN.EU_CANALS4[3], ELN.EU_CANALS4[4], ELN.EU_CANALS4[5],
               ELN.EU_CANALS4[6],
               ELN.EU_DAMS4[1], ELN.EU_DAMS4[2], ELN.EU_DAMS4[3], ELN.EU_DAMS4[4], ELN.EU_DAMS4[5], ELN.EU_DAMS4[6],
               ELN.EU_FORDS4[1], ELN.EU_FORDS4[2], ELN.EU_FORDS4[3], ELN.EU_FORDS4[4], ELN.EU_FORDS4[5],
               ELN.EU_FORDS4[6]},
      files = {EU_GEO_FILE, EU_LAND_COARSE_FILE, EU_SPAWN_FILE, "prototypes/tables/hotspots.lua",
               EU_WW_FILES[1], EU_WW_FILES[2], EU_WW_FILES[3], EU_WW_FILES[4], EU_WW_FILES[5], EU_WW_FILES[6]},
    },
    -- The Old World and Atlantic spawn city: each map's version 6.
    {
      release = "0.1.0",
      map = "atlantic",
      geography = 17,
      names = {
               OAS.AT6_GX, OAS.AT6_GY, OAS.AT6_U, OAS.AT6_V, OAS.AT6_GEO, OAS.AT6_LAND_COARSE, OAS.AT6_DETAIL,
               OAS.AT6_FAR,
               OAS.AT6_ENTRY, OAS.AT6_CX, OAS.AT6_CY, OAS.AT6_LAKES, OAS.AT6_SHORE, REN.AT_FIELDS,
               OAS.AT_CITY_INDEX, OAS.AT_CITY_CX, OAS.AT_CITY_CY, OAS.AT_SPAWN_LAKE,
               OAS.AT_SPAWN_BIAS,
               OAS.AT_WW5[1], OAS.AT_WW5[2], OAS.AT_WW5[3], OAS.AT_WW5[4], OAS.AT_WW5[5], OAS.AT_WW5[6],
               OAS.AT_CANALS5[1], OAS.AT_CANALS5[2], OAS.AT_CANALS5[3], OAS.AT_CANALS5[4], OAS.AT_CANALS5[5],
               OAS.AT_CANALS5[6],
               OAS.AT_DAMS5[1], OAS.AT_DAMS5[2], OAS.AT_DAMS5[3], OAS.AT_DAMS5[4], OAS.AT_DAMS5[5], OAS.AT_DAMS5[6],
               OAS.AT_FORDS5[1], OAS.AT_FORDS5[2], OAS.AT_FORDS5[3], OAS.AT_FORDS5[4], OAS.AT_FORDS5[5],
               OAS.AT_FORDS5[6]},
      files = {AT_GEO_FILE, AT_LAND_COARSE_FILE, OAS.AT_SPAWN_FILE, "prototypes/tables/hotspots.lua",
               AT_WW_FILES[1], AT_WW_FILES[2], AT_WW_FILES[3], AT_WW_FILES[4], AT_WW_FILES[5],
               AT_WW_FILES[6]},
    },
    {
      release = "0.1.0",
      map = "olde_world",
      geography = 18,
      names = {
               OAS.OW6_GX, OAS.OW6_GY, OAS.OW6_U, OAS.OW6_V, OAS.OW6_GEO, OAS.OW6_LAND_COARSE, OAS.OW6_DETAIL,
               OAS.OW6_FAR,
               OAS.OW6_ENTRY, OAS.OW6_CX, OAS.OW6_CY, OAS.OW6_LAKES, OAS.OW6_SHORE, REN.OW_FIELDS,
               OAS.OW_CITY_INDEX, OAS.OW_CITY_CX, OAS.OW_CITY_CY, OAS.OW_SPAWN_LAKE,
               OAS.OW_SPAWN_BIAS,
               OAS.OW_WW5[1], OAS.OW_WW5[2], OAS.OW_WW5[3], OAS.OW_WW5[4], OAS.OW_WW5[5], OAS.OW_WW5[6],
               OAS.OW_CANALS5[1], OAS.OW_CANALS5[2], OAS.OW_CANALS5[3], OAS.OW_CANALS5[4], OAS.OW_CANALS5[5],
               OAS.OW_CANALS5[6],
               OAS.OW_DAMS5[1], OAS.OW_DAMS5[2], OAS.OW_DAMS5[3], OAS.OW_DAMS5[4], OAS.OW_DAMS5[5], OAS.OW_DAMS5[6],
               OAS.OW_FORDS5[1], OAS.OW_FORDS5[2], OAS.OW_FORDS5[3], OAS.OW_FORDS5[4], OAS.OW_FORDS5[5],
               OAS.OW_FORDS5[6]},
      files = {OW_GEO_FILE, OW_LAND_COARSE_FILE, OAS.OW_SPAWN_FILE, "prototypes/tables/hotspots.lua",
               OW_WW_FILES[1], OW_WW_FILES[2], OW_WW_FILES[3], OW_WW_FILES[4], OW_WW_FILES[5],
               OW_WW_FILES[6]},
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
    -- The list hook's body (tiles.scan), defined on every load like the other tile bodies.
    {
      release = "0.1.0",
      names = {CT.AB_KEEP_BODY},
    },
  },

  -- Elevation composition tunables (ARCHITECTURE.md, "Elevation composition"; S9's values):
  --   transfer: e = tn_scale * c + if(c > 0, offset, -offset) with c clamped to +-clamp_px, so the
  --     tile class is the sign of c (vanilla land beat water down to elevation -0.027, S1-fit);
  --   detail: lattice detail of amplitude_px, zero at every pixel-centre tile (basis noise is 0 on
  --     its lattice), one octave per row, each with its own seed1 (A-11) and lattice frequency
  --     per reference pixel;
  --   far_floor: the elevation beyond the map's extent, deep water out to any distance (D15);
  --   edge_water, edge_min_scale: the elevation of the extent's outermost tile ring at scales from
  --     edge_min_scale up. The game lets deepwater border only water (its allowed_neighbors), so a
  --     land tile on the extent's edge turns the first tile beyond it to plain water; plain water
  --     (deepwater wins only below -2) on that ring keeps deep water from 1 tile out. From scale 3
  --     the ring tile is never the tile that holds a pixel centre, so T1 is unchanged; at scales 1
  --     and 2 it would be, and there the reference pixel keeps its class (design notes 2026-10-28
  --     05:30, deep water 1 tile beyond the edge).
  coast = {
    transfer_offset = 0.1,
    transfer_clamp_px = 16,
    detail_amplitude_px = 0.45,
    detail_clamp = 1,
    detail_octaves = {
      {seed1 = 7101, frequency = 1, weight = 1},
      {seed1 = 7102, frequency = 2, weight = 0.5},
      {seed1 = 7103, frequency = 4, weight = 0.25},
    },
    -- The coast warp (the maintainer's rule of 2026-10-30 10:05: a land coast is one crisp line). Added to a coast fit
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
      geographies = {14, 17, 18},
      water_gain = {[14] = 1.5, [17] = 2.5, [18] = 2.5},
      u = {{seed1 = 7411, wavelength_px = 5, amplitude_px = 0.45},
           {seed1 = 7413, wavelength_px = 1.2, amplitude_px = 0.22}},
      v = {{seed1 = 7412, wavelength_px = 5, amplitude_px = 0.45},
           {seed1 = 7414, wavelength_px = 1.2, amplitude_px = 0.22}},
    },
    far_floor = -100,
    edge_water = -1,
    edge_min_scale = 3,
    -- The soft map edge (milestone edge-and-lakes): a version with
    -- edge = true replaces its box's inside (inf, and the edge_water ring) with a second coast, the
    -- version's own transfer of b = clamp(d / tn_scale + warp - width_px, -transfer_clamp_px,
    -- transfer_clamp_px), d the box distance in tiles, so land sinks into deep water where b < 0 with
    -- the same beach and deepwater profile as a real coast. warp = warp_px * clamp(sum of the octaves,
    -- -1, 1), each octave a basis noise in geo tiles with its own seed1 and wavelength in reference px,
    -- so the cut reads as a wavy coastline that moves with the map seed. The band's water edge lies
    -- between width_px - warp_px and width_px + warp_px reference px inside the box: never closer than
    -- 4 px, so every land column the box cuts ends in water before it, and never deeper than 20 px,
    -- short of the nearest land the box does not cut (Cyprus 22 px, Alaska 24 px, Ireland and Stewart
    -- Island 25 px; design notes, edge-and-lakes). T1 masks reference land within width_px + warp_px + 1
    -- px of the box (mask_px), plus the side's margin where outline below gives it one; the band-fix
    -- handler writes nothing in that same reach (scripts/bandfix.lua, edge_band_reach in earth_test.py).
    -- fold_geographies: these read the octaves' sum folded back at +-1 instead of clamped there. A clamp
    -- pins about a fifth of the edge to one distance from the box, so it drew dead straight coast and
    -- square bays for hundreds of tiles along it.
    edge_band = {
      width_px = 12,
      warp_px = 8,
      mask_px = 21,
      fold_geographies = {14, 17},
      octaves = {
        {seed1 = 7401, wavelength_px = 32, weight = 1},
        {seed1 = 7402, wavelength_px = 12, weight = 0.5},
        {seed1 = 7403, wavelength_px = 4, weight = 0.25},
      },
      -- The margin's outline (the maintainer's ask of 2026-10-30 16:20: at a far map view the box still read as a
      -- straight rectangle): a side's water edge moves further in by margin px * share, where margin is
      -- the map's table for that side, {along px, margin px} knots read piecewise linearly and 0 for a
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

  -- The start mask: vanilla's starting_resources_lake_mask with the map's coarse land
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
  -- start mask can keep every ore on the spawn's land (design notes 2026-10-29 00:30: even an oracle
  -- mask loses some). Once, in on_init of an Earth or Map-type-only world, scripts/start_ore.lua
  -- floods the land reached on foot from the spawn (4-connected tiles without `water_layer` within
  -- `grid` tiles), sums each ore's amount on those tiles within `radius` tiles, and where that is
  -- under `trigger` times `reference` (vanilla's mean starting amount within 150 tiles at seeds
  -- 1000, 1002 and 1004, times the control's richness) places one patch of `fill` times it on
  -- reached land: the nearest centre `min_distance` (vanilla's starting-patch excluder) to radius -
  -- r tiles out (rings every `ring_step` tiles, about `arc_step` tiles apart on a ring, at least
  -- `min_ring_points`) whose disc of r + `land_margin` tiles is all reached land and holds no
  -- resource within r + `ore_margin`. r is the disc that holds the amount at `density` per tile,
  -- shrunk by `shrink` down to `min_radius` when nothing fits. An ore whose control size is 0 is left
  -- alone. Beside RSO the pass runs the same way on what RSO placed, read after RSO's on_init (the
  -- `? rso-mod` dependency orders it first), so it adds only where RSO's own start fell short
  --; with `rso_start` off, RSO's
  -- "Ore in starting area", the player asked for no ore there and the whole pass stands down. Scripted
  -- ore never shows in a map preview.
  start_ore = {
    ores = {
      {resource = "iron-ore", reference = 368000, density = 540},
      {resource = "copper-ore", reference = 357000, density = 860},
      {resource = "coal", reference = 266000, density = 890},
      {resource = "stone", reference = 159000, density = 750},
    },
    rso_start = "rso-ore-in-start-area",
    resource_type = "resource",
    water_layer = "water_tile",
    grid = 160,
    radius = 150,
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
    -- A placed patch's outline: inner of its radius
    -- moved by gain times the hotspot blob's deviation from its mean over the disc, never past the radius
    -- find_spot proved land for; grow widens that radius so the kept tiles hold about the planned area.
    outline = {blob = REN.HS_BLOB, inner = 0.7, gain = 0.3, grow = 1.25},
  },

  -- The spawn (milestone spawn-cities; S7 option ii, the shift; D15, D25, D29): the numbers spawn.lua
  -- builds every spawn body from (the names are each geography version's own, in its spawn record).
  --   hash: random is (map_seed_small * small_mult + floor(map_seed / high_div) * high_mult) % N + 1
  --     over the map's N cities (S7). Every intermediate stays below 2^24, so float32 folds it
  --     exactly; map_seed itself is a float32, so seed 4294967295 reads as 4294967296 (S7: its city
  --     differs from the integer hash's), which is why control reads the index back and never
  --     recomputes it.
  --   lake: the spawn lake, vanilla's starting-lake shape magnitude * ((d + n) / divisor - offset),
  --     d the distance from a centre `distance` tiles from the spawn on the city's generated bearing
  --     at the save's scale (one of `bearings` steps of a turn), n one basis-noise octave; water
  --     where d + n < offset * divisor (S7: about 1,850 water tiles, nearest water 42.6 tiles). The
  --     bearing points at land reached on foot (tools/build_spawn.py): S7's seed-folded angle put
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
  --     `radius` tiles of the spawn and -inf beyond, joined to the elevation by max() after the
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
  --   warp (both lakes, the decision of 2026-10-30): octave rows of a domain warp, a basis noise per axis
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
    },
  },

  -- Ridges (milestone ridges; ARCHITECTURE.md milestone contract 8; S5; APPROVALS 5 and 11). Every number the
  -- ridge bodies use; prototypes/expressions/ridges.lua builds them from prototypes/tables/ranges.lua:
  --   ramp_tiles, bias_tiles, contour   cliff_elevation = cliff_elevation_0 + cliff_elevation_interval * f,
  --              f = clamp(1 + h, low, high), h = (depth - bias) / ramp * stretch + fray (ridges.lua), so
  --              the contours are the ridge's edge and, ramp_tiles further in, one ring; the noise keeps
  --              them off the 4-tile lattice (S5: an exact lattice hit deletes the cliffs) and no term
  --              reads cliff_richness, so frequency, continuity and richness are inert
  --   width      a vertex's half-width in tiles: min_tiles + gain_tiles * (height / ref_m) ^ power, tip_tiles
  --              at a crest's end vertices (below zero, so the ridge ends in a taper, never a cap)
  --   wander     the wandering axis: per axis of the chain, noise rows in reference pixels, so one shape
  --              on the map at every scale (at scale 6, about 100 and 36 tiles over 1,500 and 300)
  --   run_base, run   the width's multiplier: base plus noise rows in tiles, floored at 0
  --   stretch, stretch_floor, fray   the height's noise rows: the depth's multiplier (floored, or a ring
  --              would open wherever it crosses 0) and the term added to it, in contours
  --   gaps       noise gaps: an opening where the noise rows read under threshold, plus thin_gain as the
  --              ridge's width at the tile falls from thin_tiles to 0, less collar_gain inside a collar
  --              Read in real sprites, wavelengths under about 70 tiles made zigzags at cliff spacing, stubs
  --              and tiny loops, since a cliff cell is 4 tiles: keep every row of run, stretch, fray and gaps
  --              above that, and a line flat to one lattice row stays broken by fray, about 4 tiles
  --   collar_tiles   the radius round an opening's slot where the ridge stands whole (ridges.lua keep)
  --   flank_tiles   the near edge of the ridge from S5's measurements: earth_test.py's T6 metrics read it
  --   cliffiness   the cliffiness of a ridge cell; 0 inside an opening and inside the ridge-free start
  --   pass_tiles   an opening's cliffiness gap along the crest (APPROVALS 5: at least 12, for 8 tiles
  --              clear; S5 measured 16 clear from a 16-tile gap, but a 16-tile slot read 7.5 at Verecke
  --              on the milestone's T6, at the limit, and the wander shears a slot by up to a third: 24 read 7.5
  --              on a diagonal crest, the limit again, so 28), reach_tiles
  --              its least half-length across, reach_margin_tiles how far it outreaches the half-width;
  --              tip_tiles how far past a crest's end vertex an opening there reaches
  --   edge_tiles, edge_reach_tiles   a range cut by a map's edge with no pass on that map: no ridge cell
  --              within edge_tiles of the edge and edge_reach_tiles of the crossing (APPROVALS 5)
  --   start      the ridge-free disc round the spawn: max(radius_tiles, starting_area_radius) plus
  --              margin_tiles, the 4-tile lattice cell and a cliff's box (decision 12; T7: 0 cliffs and
  --              0 ridge cliffiness within 150 tiles)
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
  --              y (an in-game T8 found ore 23.4 to 23.97 tiles from a crest by centre, every one with
  --              its corner outside 24), so the band reads the centre
  --   switch_threshold   the toggle reads on above it (its bodies are 1 and 0)
  --   reset_size   the cliff control's size the on_init reset writes when the slider was none (S5)
  --   ores       the Earth ores whose live probability is wrapped (resource, preset key, wrapper)
  --   water      the water frequency slider's two vanilla readers stay group 0's water_slider
  --              (D15), baked on every Earth preset at their default-slider values
  -- Names carry the ridges' version suffix; a changed body ships under the next one.
  ridges = {
    flank_tiles = 16.37,
    ramp_tiles = 24,
    bias_tiles = 3,
    contour = {low = 0.5, high = 2.5},
    width = {ref_m = 4800, min_tiles = 10, gain_tiles = 38, power = 0.8, tip_tiles = -20},
    wander = {
      u = {{seed1 = 7501, wavelength = 250, amplitude = 16}, {seed1 = 7502, wavelength = 50, amplitude = 6}},
      v = {{seed1 = 7503, wavelength = 250, amplitude = 16}, {seed1 = 7504, wavelength = 50, amplitude = 6}},
    },
    run_base = 1.15,
    run = {{seed1 = 7505, wavelength = 420, amplitude = 0.55}, {seed1 = 7506, wavelength = 120, amplitude = 0.32}},
    stretch = {{seed1 = 7507, wavelength = 100, amplitude = 0.6}},
    stretch_floor = 0.4,
    fray = {{seed1 = 7508, wavelength = 90, amplitude = 0.3}},
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
    names = {
      height = RDN.RD_HEIGHT, free = RDN.RD_FREE, cliff_elevation = RDN.RD_CLIFF_ELEVATION,
      cliffiness = RDN.RD_CLIFFINESS,
      clear = RDN.RD_CLEAR,
      crest = {europe = RDN.EU_CREST, atlantic = RDN.AT_CREST, olde_world = RDN.OW_CREST},
      openings = {europe = RDN.EU_OPENINGS, atlantic = RDN.AT_OPENINGS, olde_world = RDN.OW_OPENINGS},
      band = {europe = RDN.EU_BAND, atlantic = RDN.AT_BAND, olde_world = RDN.OW_BAND},
      wander_u = {europe = RDN.EU_WANDER_U, atlantic = RDN.AT_WANDER_U, olde_world = RDN.OW_WANDER_U},
      wander_v = {europe = RDN.EU_WANDER_V, atlantic = RDN.AT_WANDER_V, olde_world = RDN.OW_WANDER_V},
      run = {europe = RDN.EU_RUN, atlantic = RDN.AT_RUN, olde_world = RDN.OW_RUN},
      depth = {europe = RDN.EU_DEPTH, atlantic = RDN.AT_DEPTH, olde_world = RDN.OW_DEPTH},
      near = {europe = RDN.EU_NEAR, atlantic = RDN.AT_NEAR, olde_world = RDN.OW_NEAR},
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

  -- Resources (milestone resources-enemies; ARCHITECTURE.md milestone contract 9; D20, D23; S6 Q5): the
  -- presets' frequency for the six base resources (planet entries stay neutral), the richness ramp
  -- 1 + gain * clamp((distance - from) / span, 0, 1) on the four solid ores (S6 Q5: 1.01, 1.09, 1.23
  -- and 1.50 at 512, 1024, 2048 and 4096 tiles, 1.000 inside 450), each Earth ore's wrapper names
  -- (p_v1 is ridges' probability wrapper, which the next version reads), the Oil Rig's offshore-oil
  -- wrappers and the random offshore-oil sea mask: tn_land_coarse below minus threshold_px, the
  -- smallest whole threshold at which no reference river pixel more than 16 px from the sea lies in
  -- the mask on any map.
  resources = {
    frequency = 0.75,
    controls = {"iron-ore", "copper-ore", "coal", "stone", "uranium-ore", "crude-oil"},
    ramp = {name = REN.RAMP, from = 450, span = 3550, gain = 0.5},
    ramped = {"iron-ore", "copper-ore", "coal", "stone"},
    ores = {
      {resource = "iron-ore", probability = "entity:iron-ore:probability", richness = "entity:iron-ore:richness",
       p_v1 = RDN.ORE_IRON, p = REN.ORE_IRON_P2, r = REN.ORE_IRON_R},
      {resource = "copper-ore", probability = "entity:copper-ore:probability",
       richness = "entity:copper-ore:richness", p_v1 = RDN.ORE_COPPER, p = REN.ORE_COPPER_P2, r = REN.ORE_COPPER_R},
      {resource = "coal", probability = "entity:coal:probability", richness = "entity:coal:richness",
       p_v1 = RDN.ORE_COAL, p = REN.ORE_COAL_P2, r = REN.ORE_COAL_R},
      {resource = "stone", probability = "entity:stone:probability", richness = "entity:stone:richness",
       p_v1 = RDN.ORE_STONE, p = REN.ORE_STONE_P2, r = REN.ORE_STONE_R},
      {resource = "uranium-ore", probability = "entity:uranium-ore:probability",
       richness = "entity:uranium-ore:richness", p_v1 = RDN.ORE_URANIUM, p = REN.ORE_URANIUM_P2, r = REN.ORE_URANIUM_R},
      {resource = "crude-oil", probability = "entity:crude-oil:probability", richness = "entity:crude-oil:richness",
       p_v1 = RDN.ORE_OIL, p = REN.ORE_OIL_P2, r = REN.ORE_OIL_R},
    },
    offshore = {resource = "offshore-oil", probability = "entity:offshore-oil:probability",
                richness = "entity:offshore-oil:richness", p = REN.OFFSHORE_P, r = REN.OFFSHORE_R},
    sea = {name = REN.SEA, threshold_px = 7},
  },

  -- Hotspots (milestone resources-enemies; S6 A5 with a shared blob; APPROVALS 2; decisions 8 and 16). The
  -- rows are prototypes/tables/hotspots.lua (tools/build_hotspots.py writes it from the approval data):
  -- each row's disc is the region layer's row of the same id, jittered per seed there. At scale s a
  -- row's footprint radius is R = min(max(r * s, floor_tiles), cap * s) tiles (r its radius and cap
  -- r + 50 km, both in reference pixels: APPROVALS 2's floor at small scales, capped where it would
  -- pass the city-removal distance), read through the region layer's depth, so the footprint is the
  -- disc's roughened distance under R:
  --   core_share   spots start at land candidates inside a row's start disc, core_share of R (S6:
  --              core 112 of a 160-tile disc; here 0.75, so the smallest holds about 4 candidates at
  --              scale 1) and at most the disc holding spot.max_spots candidates, and reach at most the
  --              rest of R, so ore stays inside R
  --   enemy_share   extra bases start inside this share of R (S6: 40 tiles inside a 160-tile disc)
  --   patches    S6's spots per hotspot (4 of 5 M): the blob's reference spot height only
  --   land_px, sea_px   a candidate is land where tn_land_coarse is above land_px, and sea (offshore
  --              rows) where it is below minus sea_px (decision 8: the one land field outside Tile); the
  --              coarse field's zero contour runs inland of narrow coasts, so the land gate sits 4 px
  --              seaward of it (an offline probe of every adopted core at scales 1 and 6: at 0, 22
  --              cores pass under 0.6 of their reference land, Pentelicus none of it; at -4 none)
  --   land_grade_px   favourability rises over this many px of tn_land_coarse past the gate, so a
  --              region places its most inland candidates first
  --   spot       one spot_noise per resource, each with its own seed1 (A-11), region_size tiles, its
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
  --              for offshore rows) from the raster (decision 16; FEAS-12); reference_strength and
  --              reference_factor give the blob's typical spot height; density_floor raises a large
  --              footprint's amount to that many times vanilla's mean amount per tile over its area
  --              (base_density times frequency, S6's lowest measured ratio 15), so a disc of hundreds
  --              of tiles at scale 6 still holds the density T8 asks (Kursk at strength 3 held 4.95
  --              times vanilla's mean over its 243-tile footprint without it)
  --   blob       the shared texture on every spot (S6 A5c42s): three basis noises, added as
  --              (blob - mean) * height / divisor where a spot is positive
  --   resources  per resource its seed1, vanilla's base_density, spots per km2, rq factor and mean
  --              random spot size (base/prototypes/entity/resources.lua; the Oil Rig's for offshore oil,
  --              R4 4.1), fluids their well penalty and additional richness, sea for offshore fields
  hotspots = {
    floor_tiles = 48,
    core_share = 0.75,
    enemy_share = 0.75,
    patches = 4,
    land_px = -4,
    sea_px = 0,
    land_grade_px = 8,
    spot = {region_size = 512, candidates = 512, candidates_fine = 1024, fine_scale = 1, spacing = 16,
            spacing_fine = 8, max_spots = 32, basement = -100000, basement_radius = 128, min_radius = 1,
            cube_root = 1 / 3, cone_factor = 3},
    target = {fade_from = 150, fade_span = 300, double_from = 300, double_span = 1300, rich_offset = 1000,
              rich_span = 2600, per_km2 = 1000000, reference_strength = 2, reference_factor = 2,
              density_floor = 15},
    -- A row's bodies of ore (equal round spots on a blue-noise grid read as polka
    -- dots): half the candidates carry nothing and the rest share the amount by a squared uniform, so a
    -- few large bodies stand among small ones; mean 1 over all candidates, so a row's amount holds on
    -- average. The blob reaches past each cone's rim, which is what lets an outline leave the circle.
    size = {keep = 0.5, power = 2, gain = 6},
    blob = {name = REN.HS_BLOB, seed1 = 7302, mean = 1 / 3, divisor = 3.5,
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

  -- The offshore field stamps (milestone resources-enemies; APPROVALS 3): each map's body is
  -- stamp_elevation inside every adopted offshore row's footprint grown by cover_px (the region
  -- layer's edge roughness plus a well's box), else 0, and the map's newer elevation entry takes
  -- min(elevation, stamp) where the ground is already water, so every well the Entity program places
  -- inside the footprint stands on deepwater. A row's centre is the region layer's jittered centre
  -- moved onto the map's own chain by the map's whole-pixel frame offset (hotspots.lua). -6 is
  -- deepwater with and without Alien Biomes (S4 2; R3 3.1).
  fields = {
    stamp_elevation = -6,
    cover_px = 4,
    names = {europe = REN.EU_FIELDS, atlantic = REN.AT_FIELDS, olde_world = REN.OW_FIELDS},
  },

  -- The enemy layer (milestone resources-enemies; S6 A6E; APPROVALS 1b): a second spot_noise built like
  -- vanilla's enemy_base_probability (base/prototypes/noise-expressions.lua:19-50) in its own seed1,
  -- density (mult - 1) times vanilla's at candidates inside enemy_share of a hotspot footprint, on land,
  -- active only beyond start_factor times starting_area_radius; the wrapper takes max(live, layer), so
  -- bobenemies' intensity cap reaches it through enemy_base_radius and enemy_base_frequency (R5).
  enemies = {
    layer = REN.ENEMY_LAYER,
    wrapper = REN.ENEMY,
    seed1 = 7123,
    region_size = 512,
    candidates = 100,
    basement = -1000,
    basement_radius = 128,
    start_factor = 2,
    quantity_factor = 1 / 90,
    radius_power = 3,
    blob = {octaves = {{input_scale = 1 / 8, output_scale = 1}, {input_scale = 1 / 24, output_scale = 1},
                       {input_scale = 1 / 64, output_scale = 2}},
            mean = 0.5, radius_divisor = 150, near = 0.1, far = 0.9, far_distance = 3000, offset = 0.3,
            start_depth = 20},
  },

  -- Destroyed Europe (milestone destroyed-europe; ARCHITECTURE.md milestone contract 10; APPROVALS 10; S3 section 6;
  -- R3 7.1). prototypes/expressions/destroyed.lua builds, from the region layer's interface names only:
  --   zone   min(tn_destroyed_depth, d - max(start.radius_tiles, starting_area_radius)) in tiles, d the
  --          distance to the spawn, so the zone is positive inside its seeded outline less its keep rows
  --          (regions.lua seeded_polygon: vertices and edges move with the seed) and never inside the start
  --          disc, where every spawn city keeps normal ground and trees (T7); the zone's own start mask, d read from
  --          start.distance (the spawn distance body every spawn record names)
  --   heat   where the zone is positive, clamp(rim + min(per_tile * zone, ramp) + noise, rim, cap) in Alien
  --          Biomes units: a heat-1 rim (100 to 120) that climbs within ramp / per_tile tiles to a core
  --          mixing heat-1 to heat-4 (R3 7.1: heat-2 from 120, heat-3 from 135, heat-4 from 145 to 150; S3's
  --          small disc ramped 0.49 per tile to its cap, which on this zone would pave it with heat-4);
  --          -inf elsewhere, neutral for max(); the noise is in tiles, a texture, not geography, and fine enough
  --          that a chunk rarely holds one heat band alone (at 96 tiles 48 percent of land chunks did, at 24, 2)
  --   temperature   the Alien Biomes temperature's next version: max(climate-tiles' first version, heat)
  --          with the toggle on, the first version alone off (a folded if() on the switch, U5)
  --   pools  per map with a city fold, its random pick over the cities outside the zone: the fold's hash
  --          modulo the pool's size, then the pool's k-th city (prototypes/tables/destroyed.lua lists the
  --          zone cities); a preset with the toggle on and the spawn city at random bakes it as the map's
  --          city number, so the first fold reads it and resolves it as a chosen city (APPROVALS 10)
  destroyed = {
    names = {zone = DE.zone, heat = DE.heat, temperature = DE.temperature, fine = DE.chaos_fine},
    pools = {europe = DE.pool_europe, atlantic = DE.pool_atlantic, olde_world = DE.pool_olde_world},
    start = {radius_tiles = 150, distance = DISTANCE},
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
              black_dirt = "mineral-black-dirt-1", red_sand = "mineral-red-sand-1", red_dirt = "mineral-red-dirt-1"},
      tiles = {
        {tile = "vegetation-red-grass-1", class = 1, body = DE.chaos_grass},
        {tile = "mineral-black-sand-1", class = 2, body = DE.chaos_black_sand},
        {tile = "mineral-black-dirt-1", class = 3, body = DE.chaos_black_dirt},
        {tile = "mineral-red-sand-1", class = 4, body = DE.chaos_red_sand},
        {tile = "mineral-red-dirt-1", class = 5, body = DE.chaos_red_dirt},
      },
    },
    switch_threshold = 0.5,
  },

  -- Control-stage messages: the locale section and keys (locale/en/terra-nauvis.cfg). notice_withheld
  -- is the Map type notice where the map's preset is withheld (presets.withheld_with); drift_update
  -- is the drift line for a Map type fallback that moved with the mod itself rather than with a
  -- startup setting (a frozen fallback never should: the line is a tripwire); withheld_beside warns
  -- an Earth world whose preset is withheld beside a mod it now loads with; start is the start
  -- message (D29), rso the RSO warning (D32) and drift_city the drift line for a changed spawn-city
  -- setting on an Earth world (spawn-cities); destroyed_no_ab is the D12 warning, Destroyed Europe on
  -- without Alien Biomes (destroyed-europe). Messages name a world's
  -- map by its preset's name, which no version changes. A stored warning keeps its key here
  -- (scripts/guards.lua record_warning; ARCHITECTURE.md, "Guards", stored records), so a key that
  -- saves can hold is never removed or renamed: retire a message by leaving its key and locale
  -- entry in place (the T16 append-only row checks these keys against main and origin/main).
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
      start_ore = "start-ore",
      start_ore_none = "start-ore-none",
    },
  },

  -- Toggles, keyed like settings: key -> {setting = <settings key>, preset_key = <key>, default,
  -- mechanism = "name switch" or "hook gate", on = <name>, off = <name>, maps = {<map keys>}};
  -- toggle_order lists the keys. Each toggle arrives with its milestone.
  toggles = {
    -- Canals (waterways): a name switch read by every waterways version's entry through a folded if(), so
    -- only the selected branch compiles (S4: Tile 19,620 off and 20,161 on at scale 1).
    -- map_type_follows: its Map type fallback mirrors the setting, so the drift line says a world made
    -- from the map type alone follows it; every other toggle reaches new preset worlds only.
    canals = {setting = "canals", preset_key = K_CANALS, default = true, mechanism = "name switch",
              on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}, map_type_follows = true},
    -- Great forests (trees-forests): the hook gate of the boost on every living tree, outermost in the
    -- hook, so on every other world the hook folds to the tree's own autoplace. Its values are the
    -- numbers 1 and 0 as strings, so a save reads them back as it stored them (S7) and the drift line
    -- compares like with like.
    great_forests = {setting = "great_forests", preset_key = TFN.K_FORESTS_ON, default = true, mechanism = "hook gate",
                     on = "1", off = "0", maps = {"europe", "atlantic", "olde_world"}},
    -- Ridges (milestone ridges): a name switch read by the ridge bodies through a folded if(), so ridges off
    -- compiles to a constant crest distance and 0 cliffs (S5; U5).
    ridges = {setting = "ridges", preset_key = RDN.K_RIDGES, default = true, mechanism = "name switch",
              on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}},
    -- Hotspots (milestone resources-enemies): a name switch read by the ore, enemy and offshore-oil wrappers
    -- through a folded if(), so hotspots off compiles each wrapper to the live expression alone; each
    -- map's offshore stamp key follows the same setting (presets.lua).
    hotspots = {setting = "hotspots", preset_key = REN.K_HOTSPOTS, default = true, mechanism = "name switch",
                on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"}},
    -- Inland lakes (milestone edge-and-lakes): a name switch read by a version with a lakes field through a
    -- folded if(), so off compiles to the spawn lake alone (the spot noise is never evaluated) and on to
    -- the previous version's composition (U5). Every map lists it: a map's version without a spawn
    -- record bakes it unread.
    inland_lakes = {setting = "inland_lakes", preset_key = ELN.K_INLAND_LAKES, default = false,
                    mechanism = "name switch", on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"},
                    map_type_follows = true},
    -- Destroyed Europe (destroyed-europe): a name switch read by the temperature's next version through a
    -- folded if(), so the zone off compiles to climate-tiles' temperature alone. `requires` names the mod
    -- without which a preset bakes it off whatever the setting says (FEAS-17), and the drift line
    -- compares with the same rule.
    destroyed_europe = {setting = "destroyed_europe", preset_key = DE.K, default = false,
                        mechanism = "name switch", on = ONE, off = ZERO, maps = {"europe", "atlantic", "olde_world"},
                        requires = "alien-biomes"},
  },
  toggle_order = {"canals", "great_forests", "ridges", "hotspots", "inland_lakes", "destroyed_europe"},

  -- Stable hooks on shared prototypes (ARCHITECTURE.md, "Stable hooks"): if(gate > threshold, on
  -- branch, off value), whose outermost if() folds away on worlds without the gate. The gate's
  -- prototype holds gate_off, Earth presets gate_on; the ford key's prototype holds its off value.
  hooks = {
    threshold = 0.5, gate_off = 0, gate_on = 1,
    fords = {tile = "water-shallow", key = K_FORDS, off = "-inf"},
  },
  -- The canals switch's neutral bodies.
  neutral = {one = ONE, zero = ZERO},

  -- Waterways (milestone waterways; ARCHITECTURE.md, "Build-time data flow" step 3 and "Elevation
  -- composition" steps 5 and 6). tools/build_waterways.py reads every number below; the mod reads
  -- the set names and the hook values.
  --   sets: per map, the generated set names by scale (index = scale): ww (rivers, straits and
  --     turning basins, min() into the entry), canals (min(), canals on), dams (max(), canals off) and
  --     fords (the water-shallow hook's on branch, through tn_fords). The geography version that
  --     composes a map's sets names the same table as its `waterways` field, and the sets bind to
  --     that version's chain, so one version per map composes them.
  --   widths: a river is max(river_floor_tiles, k s) tiles wide
  --     by its class, so it scales with the map; a strait max(floor / 2 + margin, s / 2,
  --     w s / (2 km_per_px)) with floor two_way_tiles for the two-way straits; a canal max(floor / 2
  --     + margin, s / 2); a dam max(dam.floor_tiles, dam.per_scale s).
  --   depth: the carve's floor, plain water in vanilla and Alien Biomes for rivers and canals,
  --     deepwater for straits (S4); slope: elevation per tile from the carve's edge.
  --   tolerance_tiles: Douglas-Peucker per scale (review note 8; raised by the decision of 2026-10-30:
  --     the warp hides the vertices on a gentle reach, and every segment costs per tile); a river's bends
  --     take less, down to the scale's smoothing.least_tiles, so no vertex turns by more than kink_degrees
  --     where the curve allows it (bend_tiles: the arm of the curvature estimate); smoothing: S4's box windows in
  --     tiles, tried smallest first from min_window_px reference px until the smoothed centreline (simplified
  --     at fine_tolerance_tiles) obeys the bend rule, for rivers; the drawn_kinds (straits and canals, sea
  --     passages the coast
  --     fit fills as land) keep their drawn course unsmoothed, their R7b points (a strait's waypoints
  --     and narrowest point, a canal's route vertices) held within their half-width less one tile;
  --     bend: R4's rule, no window_tiles
  --     stretch turning more than limit_degrees; basin_tiles: the turning basin where it still fails
  --     (R4 W10).
  --   ford: every every_px reference px of a river's path, max(least_length_tiles, length_tiles s /
  --     full_scale) long along it before its rough edge (natural.ford_edge), spanning the
  --     carve plus margin_tiles, its banks bank_tiles beyond the carve on reference land; score
  --     beats every water tile's autoplace inside it.
  --   start: a spawn whose clear_tiles disc a corridor crosses moves to the nearest tile
  --     with clear_tiles of land around it; radius_tiles is the start area the bank masks cover.
  waterways = {
    version = 1,
    sets = {europe = EU_SETS4, atlantic = OAS_SETS.atlantic, olde_world = OAS_SETS.olde_world},
    floor_tiles = 7, river_floor_tiles = 3, two_way_tiles = 11, margin_tiles = 0.25,
    river_k = {major = 3, minor = 2},
    km_per_px = 2.471,
    depth = {river = -2.2, strait = -6, canal = -2.2},
    slope = 4,
    dam = {floor_tiles = 1.5, per_scale = 0.5},
    tolerance_tiles = {3, 4, 6, 8, 10, 12},
    smoothing = {windows = {1, 5, 9, 13, 17, 25, 33, 49, 65, 97}, passes = 3, step_tiles = 1, min_window_px = 12,
                 fine_tolerance_tiles = 0.5, drawn_kinds = {"strait", "canal"}, kink_degrees = 30, bend_tiles = 8,
                 least_tiles = {2.5, 2, 1, 1, 1, 1}},
    bend = {window_tiles = 17, limit_degrees = 90},
    basin_tiles = 30,
    ford = {every_px = 60, length_tiles = 10, full_scale = 6, least_length_tiles = 5, margin_tiles = 3, bank_tiles = 3,
            score = 10000, jitter = 0.3},
    vertex_grid = 16,
    start = {clear_tiles = 12, radius_tiles = 150},
    -- The natural course (the decision of 2026-10-30, "not perfect lines, with perfect edges"; waterways.lua
    -- and tools/build_waterways.py).
    --   warp: one octave per row, a basis noise per axis (seed1x, seed1y) of wavelength {a, b} = a + b s tiles
    --     and amplitude {a, b} = a + b s tiles at scale s, added to the geo tiles every set reads; passage is
    --     the share a strait, canal or dam reads. The first two rows are the meanders, the last the banks,
    --     short enough that the two banks of a river differ. noise_peak: basis noise's peak, for the warp's reach.
    --   width: W = 1 + amplitude * clamp(noise, -1, 1), a river's half-width factor. A river's half-width is
    --     held at floor_half_tiles by scale wherever W and the warp squeeze it, on the width grid so the floor
    --     shares a class: a river scales down with the map even where a boat no longer
    --     fits, so only scale 6 keeps T5's 7-tile disc, and 1.5 is what still draws an unbroken river.
    --     tip_half_tiles holds a tapered source where W could take it under that.
    --   bank: B = amplitude {a, b} * (half + half * clamp(noise, -1, 1)) tiles of wavelength {a, b} tiles at
    --     scale s (a + b s), the fine irregularity every river and passage bank adds to its half-width.
    --   ford_edge: J = amplitude {a, b} * noise tiles of wavelength {a, b} tiles at scale s, added to a ford's
    --     rectangle on every side, so its two edges across the river are irregular and not parallel.
    --   profile: a river's half-width factor from source at its inland end to mouth where it meets the coast
    --     fit, tip at the very source over taper_tiles {a, b} = a + b s, on a step_tiles grid, twice as coarse
    --     for the taper below taper_full_scale.
    --   basin: a turning basin's capsule, half_length_tiles each way along the course, radius_tiles wide; a
    --     river takes one only from least_river_scale up, where a ship fits it.
    --   deloop: a river's hooks cut, tools/build_waterways.py deloop.
    --   runs: a river's segments over max_px reference px take a vertex every step_px, off their line by
    --     amplitude step_px times least to 1, on alternating sides (tools/build_waterways.py break_runs).
    --   spawn_fade: the warp is 0 within inner_tiles of the spawn and whole beyond outer_tiles.
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
               floor_half_tiles = {1.5, 1.5, 2.25, 3.75, 4.5, 5.5}},
      bank = {seed1 = 7508, wavelength = {8, 1}, amplitude = {0.6, 0.15}, half = 0.5},
      ford_edge = {seed1 = 7509, wavelength = {5, 0.5}, amplitude = {0.6, 0.2}},
      profile = {source = 0.7, mouth = 1.35, tip = 0.55, taper_tiles = {10, 30}, step_tiles = 0.75,
                 taper_full_scale = 6},
      basin = {half_length_tiles = 8, radius_tiles = 12, least_river_scale = 4},
      deloop = {gap_px = 8, arc_px = 30, reach_px = 400},
      runs = {max_px = 60, step_px = 36, amplitude = 0.2, least = 0.4},
      spawn_fade = {inner_tiles = 40, outer_tiles = 200},
      ponds = {max_px = 32, reach_px = 3, margin_px = 1.5, height = 20},
    },
  },

  -- The region layer (milestone region-layer; ARCHITECTURE.md, "Region layer"; S10 design (d), design notes
  -- 07:45): the rows of prototypes/tables/regions.lua as exact signed distances in reference pixels
  -- at a query point on the coordinate chain, displaced by one shared domain warp and roughened by
  -- one shared edge noise, with each layer's aggregates. Every row is evaluated in the frame map's
  -- reference pixels: each map's raster sits on that grid at px_per_degree (Europe is an exact crop of
  -- Atlantic's raster; Old World's edges are whole pixels away), so a map's own chain moves into the
  -- frame by a whole-pixel offset and a row sits at its geography on every map and at every scale.
  --   warp      two multi-octave noises (seed1 per axis), wavelength_px the finest octave, amplitude_px
  --             times the noise, the vector clamped to clamp_px in length; a row follows its share
  --   rough     one multi-octave noise added to every signed distance, clamped to +-clamp_px
  --   octave_shift_px  each octave's x shift per octave index (its own lattice: no shared zero); every
  --             octave is a basis_noise anchored to the frame (multioctave_noise offsets are not
  --             shifts in 2.1.23, measured by this milestone)
  --   ramp      membership weight clamp(mid + sd / width_px, 0, 1)
  --   jitter    a hotspot's centre moves by up to its jitter radius per seed: S6's linear fold of
  --             map_seed_small and the seed's high bits, plus the row's phase (A-11: no new noise)
  --   names     the interface and internal names; a row's names are row.<kind> .. <row id> .. suffix
  -- Names carry the layer's version suffix; a changed body ships under the next one.
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
    jitter = {mult_x = 0.6180339887, mult_y = 0.4142135624, mult_high = 0.569840291, high_bits = 65536,
              vertex_step = 0.7548776662, flat_px = 0.001},
    names = {
      suffix = RG_V,
      row = {sd = NOISE .. "sd_", w = NOISE .. "w_", depth = NOISE .. "depth_", hu = NOISE .. "hu_",
             hv = NOISE .. "hv_"},
      share = "_k",
      destroyed_sd = RG_DESTROYED_SD, destroyed_w = RG_DESTROYED_W, destroyed_depth = RG_DESTROYED_DEPTH,
      forest_w = RG_FOREST_W, forest_sum = RG_FOREST_SUM, tree_mult = RG_TREE_MULT, marsh_w = RG_MARSH_W,
      hotspot_w = RG_HOTSPOT_W, enemy_mult = RG_ENEMY_MULT,
      -- the query point: u, v .. suffix unwarped; u, v .. share .. <hundredths> .. suffix for a share
      u = RG_U, v = RG_V_, ox = RG_OX, oy = RG_OY, ax = RG_AX, ay = RG_AY, wk = RG_WK, wx = RG_WX, wy = RG_WY,
      rough = RG_ROUGH, marsh_rough = RG_MARSH_ROUGH,
    },
  },

  -- The shore body (milestone climate-tiles; ARCHITECTURE.md, "Elevation composition" step 2, recalibrated
  -- with Alien Biomes, design experiment 9): the sign-offset transfer of v1 with its own land and water
  -- gains, so the tile class is still the sign of c (T1 unchanged) while
  --   land  e = max(land.min, land.per_scale * s) * c + offset: elevation 5, where AB's shore term ends,
  --         sits about 4 tiles inland at scale 2 and up and 2 tiles at scale 1 (beach band, R3 2.1);
  --   water e = max(water.min, water.per_scale * s) * c - offset: AB's deepwater line, -5.5 (R3 3.1),
  --         sits about 6 tiles offshore at scale 3 and up and 2.7 tiles at scale 1, where the fit's
  --         saturation (about 4 px) left v1's open sea at -4.1, shallow water under AB.
  -- c, its clamp and the far-field box are v1's (the coast group above); the carves and dams of v2 keep
  -- their absolute depths, so rivers stay plain water and straits deep in vanilla and AB alike.
  -- Each version that composes it names its own shore body (geography.<map>.versions[n].shore).
  shore = {
    land = {per_scale = 1.25, min = 2.5},
    water = {per_scale = 0.9, min = 2},
  },

  -- The Earth climate (milestone climate-tiles; ARCHITECTURE.md, "Expression inventory" and "Alien Biomes";
  -- S3 sections 1 to 4; D9). Temperature is in Alien Biomes units (below 0 frozen, 25 to 65 temperate,
  -- 65 hot, above 100 volcanic) in both variants; the fallback hands vanilla consumers scale times it.
  --   lat, lon  degrees on the map's own chain: lat_top_edge - (v + 1/2) / px_per_degree and
  --             lon_left_edge + (u + 1/2) / px_per_degree, folded on tn_map; the latitude meanders by up
  --             to degrees times one basis noise octave of wavelength_px (seed1, A-11)
  --   temperature  ref_t at ref_lat, per_degree warmer toward the equator, clamped to min and cap; minus
  --             continental.t at full continentality (longitude lon_start + lon_span and east, latitude
  --             lat_start + lat_span and north: D9's cold Russia); plus desert_heat in the dry belts;
  --             plus noise; Alien Biomes adds its hot and cold shift, shift_per_unit per slider unit as
  --             its own average (R3 1.1), and scales the noise input by their mean frequency (S3 3)
  --   moisture  the Earth mean (base, plus equatorial within the equatorial latitude ramp, minus dry in
  --             the dry belts; the fallback caps the mean by temperature, S3 4: the dry north) plus the
  --             spread and bias times the moisture bias; with Alien Biomes the marsh weight lifts it to
  --             marsh times the weight (APPROVALS 8)
  --   aux       the Earth mean (base; the fallback pulls cold land toward cold_aux and dry land down by
  --             dry_pull, S3 4) plus the spread, capped (Alien Biomes: ab_cap, under AB's alien palette
  --             from 0.6; the fallback's cold land: cold_cap, under vanilla red desert), then bias times
  --             the aux bias; with Alien Biomes dry temperate land is lifted by red.lift (vanilla red
  --             desert, where non-adopted AB tiles are excluded)
  --   spread    every real climate zone is a patchwork of several tiles that changes with the seed
  --             (The quality bar: a real biome never reads as one tile): each field adds a seeded multioctave
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
      -- taiga: before the scale, a core from
      -- treeline_t up to plateau is lifted to plateau, so the boreal belt sits inside the vanilla cold
      -- trees' 0 to 15 band; below treeline_t it falls by slope per unit, so the tundra and the arctic
      -- stay treeless (core -20 maps to -10 before the scale)
      fallback = {scale = 0.45, min = -20, max = 50, taiga = {plateau = 10, treeline_t = -16, slope = 5}},
    },
    moisture = {
      base = 0.68, equatorial = 0.12, equatorial_lat = 4, equatorial_ramp = 8, dry = 0.55, marsh = 0.9,
      noise = {amplitude = 0.32, wavelength_px = 40, octaves = 3, persistence = 0.6, seed1 = 7603},
      spread = {dry = 0.7, cold = 0.55},
      ab_bias = 2.2,
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
    -- The grain: Alien Biomes scores a tile by
    -- plateau_peak_to_noise_expression, min(peak * 20, 1), whose box edge is far steeper than its own
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
    -- hot_span over hot_t and at none between, so temperate land keeps its character. A coarser noise
    -- only redraws the blobs (the temperate patch noise, 60 tiles and up at scale 6, left razor edges).
    -- Each key's prototype is its plain field, so a preset that names none keeps its program.
    grain = {maps = {atlantic = true, europe = true, olde_world = true}, layer = 19,
             temperature = 3, moisture = 0.09, aux = 0.09,
             cold_t = 32, cold_span = 10, hot_t = 58, hot_span = 7,
             prefixes = {"vegetation-", "mineral-", "frozen-", "volcanic-"},
             keys = {temperature = CT.K_TILE_T, moisture = CT.K_TILE_M, aux = CT.K_TILE_A}},
    -- the coldness the fallback's pulls and spread read: 0 at core cold.t and warmer, 1 at
    -- cold.t - cold.span and colder
    cold = {t = 10, span = 30},
    -- The dry belts after EarthMaps' painted sand (D9; R1 section 6): the sand share of land per 10 x 10
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
    names = {lat = CT.CL_LAT, lon = CT.CL_LON, dry = CT.CL_DRY, core = CT.CL_CORE, shift = CT.CL_SHIFT,
             ab = {temperature = CT.CL_T_AB, moisture = CT.CL_M_AB, aux = CT.CL_A_AB},
             grain = {field = CT.CL_GRAIN, temperature = CT.CL_T_AB_G, moisture = CT.CL_M_AB_G, aux = CT.CL_A_AB_G},
             fallback = {temperature = CT.CL_T_FB, moisture = CT.CL_M_FB, aux = CT.CL_A_FB}},
    -- The climate bands the T3 oracle and the D11 row read, in Alien Biomes units (R3 4.1).
    bands = {frozen_below = 0, cold_below = 25, hot_from = 65, dry_below = 0.4},
  },

  -- The tile hooks (milestone climate-tiles; ARCHITECTURE.md, "Stable hooks"; S3 section 2; APPROVALS 8 and
  -- 9). Every hook is if(tn_on > threshold, <on branch>, <off value>), so worlds without an Earth
  -- preset compile the off value alone (A-2; S3: a gate inside the score cost default worlds Tile
  -- +7,489).
  --   vanilla   with Alien Biomes: the 19 vanilla land tiles AB takes off Nauvis (R3 3.2), re-listed;
  --             on branch (vanilla score) + the tile's key, off value -inf; every key names one bonus
  --             body: +bonus on land where the temperate lean plus patch noise passes (S3: lean
  --             1 - |T - lean_t| / lean_span), 0 elsewhere in the exclusion's temperate band, -inf
  --             outside it, on water and inside marshes (marsh_cut)
  --   exclude   with Alien Biomes: every AB land tile (by prefix) outside APPROVALS 9's adopted set; on
  --             branch (AB score) + the key, off value AB's score; the body is -inf from temperate_from
  --             to temperate_below outside marshes, 0 elsewhere (D11: only the adopted AB tiles in
  --             temperate bands)
  --   marsh     water-mud (registered on Nauvis without AB) and water-shallow (the ford hook's tile):
  --             on branch max(the key, AB's own expression where AB defines one); water-mud pools on
  --             land inside marshes where pool noise passes a cut that falls with the marsh weight,
  --             outside the start clearing; water-shallow along open water down to shallow_depth;
  --             without Alien Biomes grass-1 (APPROVALS 8's grass between the pools) behind a gated hook,
  --             (score) + the grass key, its own score off: the key's body gives +bonus on land inside
  --             marshes (marsh_cut), 0 elsewhere (with AB the vanilla tile keys keep vanilla out of
  --             marshes, so AB's wetland grass lies between the pools)
  --   palm      with or without Alien Biomes (so a world that gains it later meets the switch too;
  --             design notes 2026-10-29 18:40): Earth presets point each AB palm's
  --             entity:<tree>:probability and :richness keys at Earth copies of its expressions with
  --             every local expression, the
  --             constant where AB reads elevation (the richness too: its locals are in its scope, so
  --             the isolation walk reads them with it)
  --. ARCHITECTURE.md's hook form (a key whose prototype
  --             is elevation) added one processed expression to M2's default Entity program, which the
  --             zero-cost row compares, so the milestone takes ARCHITECTURE.md's named fallback: AB's
  --             prototypes stay untouched. The copies are Earth-owned data:
  --             trees.lua builds them on every load from `table`, Alien Biomes 0.8.0's palm autoplace
  --             frozen by tools/build_palms.py, each function they call carried as a local function
  --             named local_prefix plus its name, so no Alien Biomes version changes a registered
  --             copy; data-final-fixes.lua compares the live palm autoplace with the table and, on any
  --             difference or a missing palm, points both keys at `neutral` (no palms) and logs it
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
      body = CT.VT_BONUS, body_grain = CT.VT_BONUS_G,
      bonus = 10, lean_t = 45, lean_span = 30, lean_cut = 0.5,
      patch = {amplitude = 0.36, clamp = 0.45, wavelength_px = 10, octaves = 3, persistence = 0.5, seed1 = 7605},
      -- the patch's finest octave is 10 px (60 tiles at scale 6), so where it failed the lean the hole in
      -- the bonus showed as a smooth oval of Alien Biomes ground; the marsh pool noise, already in the
      -- Tile program, carries the edge down to 3 px at no cost
      fine = 0.15,
      -- marsh ground starts where the lifted moisture has cleared Alien Biomes' mid band (0.4 to 0.6, its
      -- beige and grey dirt): at 0.5 those tiles ran round every marsh as a one-width rim
      marsh_cut = 0.68,
    },
    -- APPROVALS 9's adopted Alien Biomes tiles: six land tiles plus water-mud (approvals-data.json has
    -- no section 9 rows; the T16 approvals row compares this list with APPROVALS.md's checked rows).
    ab_adopted = {"vegetation-turquoise-grass-1", "vegetation-olive-grass-2", "mineral-grey-dirt-1",
                  "mineral-beige-dirt-1", "mineral-cream-sand-1", "mineral-grey-sand-1", "water-mud"},
    exclude = {
      prefixes = {"vegetation-", "mineral-"},
      key = CT.AB_EXCLUDE, off = "0", body = CT.AB_EXCLUDE_BODY, body_grain = CT.AB_EXCLUDE_BODY_G,
      temperate_from = 25, temperate_below = 65, marsh_cut = 0.68,
    },
    -- The list hook (Alien Biomes' long tile restrictions, design notes 2026-10-30 12:55): the game walks a
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
      water_mud = {tile = "water-mud", key = CT.MARSH_MUD, off = "-inf", body = CT.MARSH_MUD_BODY},
      water_shallow = {key = CT.MARSH_SHALLOW, off = "-inf", body = CT.MARSH_SHALLOW_BODY},
      grass = {tile = "grass-1", key = CT.MARSH_GRASS, off = "0", body = CT.MARSH_GRASS_BODY, bonus = 10},
      score = 50, shallow_score = 300, shallow_depth = 1.5, start_clear_tiles = 64,
      pool = {name = CT.MARSH_POOL, cut = 0.3, cut_per_weight = 1, wavelength_px = 3, octaves = 2, persistence = 0.5,
              seed1 = 7606},
    },
    palm = {body = CT.PALM_CONST, value = 1, reads = "elevation",
            table = "prototypes.generated.palms_ab_v1", local_prefix = "palm_", neutral = ZERO, tolerance = 1e-9,
            copies = {{tree = "tree-palm-a", field = "probability", key = CT.PALM_A_P_KEY, body = CT.PALM_A_P},
                      {tree = "tree-palm-a", field = "richness", key = CT.PALM_A_R_KEY, body = CT.PALM_A_R},
                      {tree = "tree-palm-b", field = "probability", key = CT.PALM_B_P_KEY, body = CT.PALM_B_P},
                      {tree = "tree-palm-b", field = "richness", key = CT.PALM_B_R_KEY, body = CT.PALM_B_R}}},
  },

  -- Trees and great forests (milestone trees-forests; ARCHITECTURE.md, "Stable hooks" and "Region layer"; S3
  -- section 5, S10 section 4, R3 3.4 items 3 to 6; design note 10).
  --   boost     every living tree's probability becomes if(gate > hooks.threshold, min(cap, (own) * key),
  --             own): the gate's prototype holds gate_off and Earth presets bake the great-forests toggle;
  --             the key's prototype holds key_off (a neutral multiplier) and Earth presets name the region
  --             layer's multiplier (regions.names.tree_mult: 1 + forest boost 2 times the forest sum, S10).
  --             The base game's dead and dry trees are left alone (prototypes/tables/vanilla.lua, S10),
  --             and so are Alien Biomes' palm prototypes (tiles.palm.copies' trees stay AB's)
  --             The lift is added to the probability
  --             before the multiplier: its key's prototype holds lift_off and Earth presets name lift_body,
  --             lift_per_sum times the forest sum times the boreal weight (0 at climate core
  --             boreal_from_t and warmer, 1 at boreal_full_t and colder), so the boreal great forests fill
  --             the gaps between vanilla's tree patches while every other forest keeps the multiplier alone
  --   palm      on Earth presets with Alien Biomes the palms read their Earth copies (tiles.palm), so each
  --             palm's probability key names its second version, the boost's formula around the
  --             registered first
  --   restore   with Alien Biomes, the base game's living trees, rocks and decals AB takes off Nauvis,
  --             rebuilt from prototypes/tables/vanilla.lua: each behind the gate keys.on with its key, whose
  --             prototype holds the off value and which Earth presets point at its body, restricted to the
  --             vanilla land tiles (tiles.vanilla.tiles), so AB's land keeps AB's own (S3). The restored trees
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
    palm = {{key = CT.PALM_A_P_KEY, body = TFN.PALM_A_P2, base = CT.PALM_A_P},
            {key = CT.PALM_B_P_KEY, body = TFN.PALM_B_P2, base = CT.PALM_B_P}},
    temperature = TFN.TF_VTEMP,
    decor = {box = "tn_vbox", thin = {["brown-asterisk"] = 0.5, ["brown-asterisk-mini"] = 0.25,
                                      ["red-desert-bush"] = 0.25, ["white-desert-bush"] = 0.25}},
    restore = {
      trees = TF_TREES, tree_off = "0", richness = TFN.TF_VTREE_R,
      rocks = TF_ROCKS, rock_off = "0",
      decoratives = TF_DECO, deco_off = "-inf", deco_body = TFN.TF_VDECO, deco_on = "0",
    },
  },

  -- Exact coastlines (milestone coast-band-fix; ARCHITECTURE.md, "Control stage"; S12, S13-bandfix; design notes
  -- 07:05, 12:35 and 13:45). On a save whose Nauvis surface carries the key, scripts/bandfix.lua's
  -- on_chunk_generated handler rewrites, where the generated land or water is wrong, the tiles of the K
  -- pixels of the save's map and scale: scored reference pixels (not thin water) outside every waterway,
  -- canal, dam and ford footprint that hold a tile the coast fit may misclassify at least half a
  -- reference pixel from the reference coast (S12's closed band rule). tools/build_geo.py emits each
  -- map's K+ table (K and its 8 neighbours) per scale into scripts/generated/ and prices it in
  -- data-src/bandfix/.
  --   setting, key, on  the startup bool, the per-save name switch and its value when on: a map's preset
  --       carries the key only when the setting is on and the map is listed in maps; absent means off
  --   maps  the maps whose four flip checks passed (decision 9; test notes 5.9), in map order; none
  --       until the milestone suite measures them, so the setting acts on no map yet. Atlantic, never priced
  --       (S12), is never listed
  --   checks  each flip-checked map's measured configuration, its scale
  --   tables  per map with K+ tables: the geography ids (tn_geo) they serve. They follow the coast fit, the
  --       reference and the waterway footprints, so a later geography that keeps all three may be listed
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
  --       the pixel's class by at least threshold + wobble * a smooth tile noise (3/4 is half a pixel from a
  --       straight coast); in a fill pixel it reads within thin of its value at the pixel's centre, a blob. octaves
  --       name the noise's cells per period_tiles and weights, hash its lattice values, shift_tiles the second
  --       reading the deep-water line takes; written land takes the nearest land on a lattice of the chunk's
  --       own tiles, lattice_tiles apart; spline_centre and ease are the formulas' own constants
  --   row_cache  decoded table rows a peer keeps in memory, the oldest evicted one at a time (a cache of
  --       shipped data, never game state): at scale 6 they span 12,288 tiles north to south
  --   encoding  each table row is its first column, then runs (length - 1) * #symbol_order + symbol index
  --       (0-based in symbol_order), every number a varint of varint_base digits written in alphabet (a
  --       digit at or above varint_base continues the number); a decoded row is one symbol character per
  --       pixel: none (outside K+), water, land, a K pixel of either class (band), a fill pixel of either
  --       class, thin water, and a pixel of either class inside a waterway footprint (masked)
  bandfix = {
    setting = "exact_coast", key = BFN.K, on = ONE,
    maps = {"atlantic", "olde_world"},
    checks = {europe = {scale = 1}, atlantic = {scale = 4}, olde_world = {scale = 6}},
    tables = {europe = {geographies = {14}}, atlantic = {geographies = {17}}, olde_world = {geographies = {18}}},
    version = 1,
    float_margin_px = 0.01,
    correction_tiles = 2,
    mask_margin_tiles = 3,
    spawn_keep_tiles = 24,
    chunk_tiles = 32,
    row_cache = 2048,
    new_water = "water", new_deep = "deepwater", land_fallback = "sand-1", ground_rings = 3,
    smooth = {min_scale = 3, threshold = 0.72, wobble = 0.22, thin = 0.35, spline_centre = 0.75, ease = 3,
              period_tiles = 64, lattice_tiles = 4, shift_tiles = {21, 32},
              octaves = {{cells = 4, weight = 1}, {cells = 12, weight = 0.6}},
              hash = {x = 73, y = 179, seed = 283, modulus = 1021, mix = 31, half = 510},
              -- corners: on these maps written land takes the nearest land within reach steps of step tiles on a
              -- lattice that reaches past the chunk, read a little off the tile, and farther out the ground of the
              -- chunk's nearest corner, each the first land on rings of samples round that corner, the borders between
              -- corners wandering by wander of a chunk. Picked per chunk, the ground drew rectangles of one tile with
              -- straight sides along chunk borders wherever a coast was written far from its land (Danube delta,
              -- Amazon mouth, Gulf coast; the maintainer's straight blocky edge).
              corners = {maps = {atlantic = true}, step = 8, reach = 2, rings = {16, 48}, wander = 0.4}},
    neighbours = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {-1, 1}, {1, -1}, {-1, -1}},
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    varint_base = 32,
    symbols = {none = "a", water = "b", land = "c", water_k = "d", land_k = "e", water_fill = "f",
               land_fill = "g", thin = "h", water_masked = "i", land_masked = "j"},
    symbol_order = {"none", "water", "land", "water_k", "land_k", "water_fill", "land_fill", "thin",
                    "water_masked", "land_masked"},
  },

  -- Cover for the land Exact coastlines writes (scripts/coastcover.lua; design notes 2026-10-30 coastcover). A group of
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
  --   hash  the per-chunk seed (factorio-worldgen-runtime, hashed per-chunk seeds): a multiplicative step
  --       modulo 2^32 per coordinate, floor keeping it out of the seeds that are all one generator
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

  -- City markers (milestone extras; APPROVALS 1a, D28; ARCHITECTURE.md milestone contract 13). With the setting on,
  -- scripts/markers.lua draws one text per city of the save's map, its name from the map's city table, at the
  -- tile holding the city's reference pixel centre: world = geo - the city offset, the conversion of
  -- spawn-cities' force-spawn probe (T18 (c)). They are rendering objects in chart mode: drawn on the map view
  -- only, for every force, the same size on screen at every zoom; they need no charted chunk and no per-chunk
  -- event, so the headless T18 check reads them with rendering.get_all_objects.
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

  -- The size context of the scale labels, the scale tooltip and the preset descriptions (milestone extras; D3,
  -- JI-12). World sizes are maps' width_px and height_px times the scale (APPROVALS 1c, approvals-data.json
  -- world_size_tiles); each preset description gives its map's size at preset_scales. No measured footprint of a
  -- late-game factory exists (R8 section 1: every row graded REPORTED), so the locale carries R8's two figures
  -- as reported community examples, never as measurements: each footprint below is its R8 row's figure in
  -- tiles, and every text that carries one says reported_phrase before it. The T16 locale row checks every
  -- figure of those texts against this table, the maps and R8.
  size_context = {
    reported_phrase = "reported community examples",
    preset_scales = {1, 6},
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
