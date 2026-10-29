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

-- Europe's geography (milestone europe-coast). Every name Europe's elevation entry reads is bound to
-- Europe: its coordinate chain carries Europe's radii and extent and reads the city offset through
-- Europe's own map-qualified per-save names, so a Map type pick alone (which sets only elevation)
-- still renders Europe, and no map-dependent value reaches the entry through tn_map or a shared key.
-- The city offset names belong to this version of the chain (_v1): their prototype bodies are
-- registered constants that no later version moves, so a Map-type-only world made from this entry
-- never shifts; a later entry that needs another offset takes names of its own (ARCHITECTURE.md,
-- "Map type entries"; design notes 2026-10-28 07:20).
local EU_ENTRY = NOISE .. "elevation_europe_v1"
local EU_GEO = NOISE .. "geo_europe_v1"
local EU_LAND_COARSE = NOISE .. "land_coarse_europe_v1"
local EU_DETAIL = NOISE .. "detail_europe_v1"
local EU_FAR = NOISE .. "far_europe_v1"
local EU_GX = NOISE .. "gx_europe_v1"
local EU_GY = NOISE .. "gy_europe_v1"
local EU_U = NOISE .. "u_europe_v1"
local EU_V = NOISE .. "v_europe_v1"
local EU_CX = NOISE .. "cx_europe_v1"
local EU_CY = NOISE .. "cy_europe_v1"
-- The generated files (tools/build_geo.py): name-free data that a geography version's fit bodies
-- bind to its own chain, so a later version binds the same files instead of emitting new ones.
local EU_GEO_FILE = "prototypes/generated/geo_europe_v1.lua"
local EU_LAND_COARSE_FILE = "prototypes/generated/land_coarse_europe_v1.lua"

local START_MASK = NOISE .. "start_mask_v1"

-- Europe's geography version 2 (milestone spawn-cities): the spawn at the chosen city. The city offset
-- moves with the city, and version 1's offset names are frozen at 0, so version 2 takes every name
-- of its own: its chain reads its own offset names, which its preset points at the city fold, and
-- its coast, coarse, detail and box bodies bind the same generated files to that chain (decision 21;
-- design notes 2026-10-28 07:20 and 17:40). Its entry composes version 1's terms with the start land
-- guarantee, the spawn lake and the map's inland lakes.
local EU2_ENTRY = NOISE .. "elevation_europe_v2"
local EU2_GEO = NOISE .. "geo_europe_v2"
local EU2_LAND_COARSE = NOISE .. "land_coarse_europe_v2"
local EU2_DETAIL = NOISE .. "detail_europe_v2"
local EU2_FAR = NOISE .. "far_europe_v2"
local EU2_GX = NOISE .. "gx_europe_v2"
local EU2_GY = NOISE .. "gy_europe_v2"
local EU2_U = NOISE .. "u_europe_v2"
local EU2_V = NOISE .. "v_europe_v2"
local EU2_CX = NOISE .. "cx_europe_v2"
local EU2_CY = NOISE .. "cy_europe_v2"
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
local EU2_LAKES = NOISE .. "inland_lakes_europe_v1"
local START_LAND = NOISE .. "start_land_v1"
local DISTANCE = NOISE .. "distance_v1"
-- The spawn bearings per city and scale (tools/build_spawn.py): name-free data.
local EU_SPAWN_FILE = "prototypes/generated/spawn_europe_v1.lua"

local START_MASK2 = NOISE .. "start_mask_v2"

return {
  identity = {
    id = ID,
    title = "Terra Nauvis",
    version = "0.1.0",
    author = "Jake Mismas",
    factorio_version = "2.1",
    base_version = "2.1.23",
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
  },
  setting_order = {"scale", "spawn_city_europe"},

  -- Map-gen presets, sorted right after Default ("a") and before Rich resources ("b") (S13).
  -- withheld_with lists the mods whose presence withholds a preset (presets.lua defines no such
  -- preset while one is loaded): Alien Biomes 0.8.0's palms (tree-palm-a, tree-palm-b) read
  -- elevation in the Entity program, so beside it this preset would carry its fine field there and
  -- break design constraint 3. climate-tiles ships the palm switch (design note 9) and
  -- empties the list; until then a world beside Alien Biomes gets Europe only through its Map type
  -- entry. Withholding acts on
  -- new worlds only: a world made from the preset that later loads beside a listed mod still names
  -- its fine field, so control code warns once and records it (scripts/guards.lua; design notes
  -- 2026-10-28 07:20, a preset save beside Alien Biomes).
  presets = {
    europe = {name = ID .. "-europe", map = "europe", order = "a-tn-a", withheld_with = {"alien-biomes"}},
  },
  preset_order = {"europe"},

  -- The per-save keys (U6): map, scale and geography release are numbers every Earth preset bakes;
  -- land_coarse names the map's coarse land field; elevation, start_mask and distance
  -- are the vanilla properties the presets redirect (distance from spawn-cities: vanilla's starting
  -- ore and enemy-free start follow the spawn through it, S7); spawn_lake and spawn_bias name the
  -- map's spawn lake and starting-ore bias for the shared start mask v2 (spawn-cities).
  keys = {
    map = K_MAP, scale = K_SCALE, geo = K_GEO, land_coarse = K_LAND_COARSE,
    elevation = "elevation", start_mask = "starting_resources_lake_mask", distance = "distance",
    spawn_lake = K_SPAWN_LAKE, spawn_bias = K_SPAWN_BIAS,
  },

  -- Each map's geography (ARCHITECTURE.md, "Map type entries"): map_type_order, the order of the
  -- map's Map type entry, and `versions`, every version of the map's elevation entry, oldest first
  -- and the newest last. A version is what one geography release points a preset at: its entry,
  -- the bodies only that entry reads (coast fit, detail, far-field box), its coarse land field, its
  -- coordinate chain with city offset names of its own and the offset its preset bakes there, the
  -- start mask its preset names (a start_mask version), the generated files its fit bodies bind
  -- (name-free data, so a later version binds the same files to its own chain), the Map type
  -- fallbacks its entry reads, and its geography release id. The map's preset names the newest
  -- version, whose entry alone carries the Map type fields (intended_property, localised_name and
  -- map_type_order); older versions stay defined, unchanged, for the worlds that name them, and
  -- control code identifies a Map-type-only world by any of them. A later version never re-points
  -- an older one's names: it takes names of its own (decision 21; design notes 2026-10-28 07:20).
  -- presets.lua picks a preset's version here, in one place at the data stage, so climate-tiles can
  -- give Alien Biomes worlds a cheaper geography without touching base worlds.
  --
  -- geo_id is the version's geography release, the number its preset bakes as tn_geo. tn_geo is
  -- one id space across every map: each geography release of any map takes the next unused
  -- integer and keeps it for good, so no two maps or versions share one, and release_registry
  -- names each with its map, which is how control code resolves a save's tn_geo (ARCHITECTURE.md,
  -- "Release versioning policy", rule 4; tnconfig's id-space check).
  geography = {
    europe = {
      map_type_order = "3000-tn-a",
      versions = {
        {
          geo_id = 1,
          entry = EU_ENTRY,
          geo = EU_GEO, land_coarse = EU_LAND_COARSE, detail = EU_DETAIL, far = EU_FAR,
          gx = EU_GX, gy = EU_GY, u = EU_U, v = EU_V,
          -- The city offset in geo tiles (the chosen city at world (0, 0)): per-save names the
          -- preset bakes as 0, each with a registered constant fallback of 0 that no later version
          -- moves. A later entry that spawns at a city reads names of its own through its own
          -- chain, so a world made from this entry keeps its terrain.
          cx = EU_CX, cy = EU_CY, city_offset = {0, 0},
          start_mask = START_MASK,
          fits = {geo = EU_GEO_FILE, land_coarse = EU_LAND_COARSE_FILE},
          -- The Map type fallbacks: {name = <noise name>, map_qualified = <bool>, frozen = <bool,
          -- optional>} for each per-save name this entry reads, which a Map type pick leaves to a
          -- prototype-level fallback valued as this version's preset bakes it (presets.lua; T16
          -- checks each). A fallback that mirrors a startup setting (frozen absent or false)
          -- follows the setting at every load and is U3's one exemption, never registered in
          -- tests/frozen.json; a frozen one is a constant no setting moves, registered like every
          -- Earth body, so no later version can move a world that reads it (ARCHITECTURE.md, "Map
          -- type entries", binding).
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = EU_CX, map_qualified = true, frozen = true},
            {name = EU_CY, map_qualified = true, frozen = true},
          },
        },
        {
          -- Version 2 (spawn-cities): the spawn at the chosen city. Every name is its own; the files
          -- are version 1's, bound to this version's chain.
          geo_id = 2,
          entry = EU2_ENTRY,
          geo = EU2_GEO, land_coarse = EU2_LAND_COARSE, detail = EU2_DETAIL, far = EU2_FAR,
          gx = EU2_GX, gy = EU2_GY, u = EU2_U, v = EU2_V,
          -- The offset names the preset points at the city fold (names, not numbers): the fold reads
          -- the map's city number, the scale and map_seed and folds to two constants (S7). Each
          -- fallback names the same fold, a constant body no setting moves, so it is frozen; the
          -- city number's own fallback mirrors the spawn-city setting, as the scale's does.
          cx = EU2_CX, cy = EU2_CY, city_offset = {EU_CITY_CX, EU_CITY_CY},
          start_mask = START_MASK2,
          fits = {geo = EU_GEO_FILE, land_coarse = EU_LAND_COARSE_FILE},
          fallbacks = {
            {name = K_SCALE, map_qualified = false},
            {name = EU2_CX, map_qualified = true, frozen = true},
            {name = EU2_CY, map_qualified = true, frozen = true},
            {name = EU_CITY, map_qualified = true},
          },
          -- The spawn (spawn.lua): the map's spawn-city setting (a settings key) and per-save city
          -- number, the resolved index, the spawn lake and starting-ore bias the start mask reads
          -- through the preset keys spawn_lake and spawn_bias, this version's inland lakes, the start
          -- land guarantee, the distance body the preset redirects distance to, and the generated
          -- spawn bearings. The entry composes the guarantee, the spawn lake and the inland lakes
          -- (coast.lua; ARCHITECTURE.md, "Elevation composition", steps 4 and 7).
          spawn = {
            city_setting = "spawn_city_europe", city = EU_CITY, city_index = EU_CITY_INDEX,
            spawn_lake = EU_SPAWN_LAKE, spawn_bias = EU_SPAWN_BIAS, inland_lakes = EU2_LAKES,
            start_land = START_LAND, distance = DISTANCE, bearings = EU_SPAWN_FILE,
          },
        },
      },
    },
  },

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
  -- exactly these keys from every other surface (D33).
  preset_keys = {"elevation", "starting_resources_lake_mask", K_LAND_COARSE, K_MAP, K_SCALE, K_GEO, EU_CX, EU_CY,
                 "water_level", "segmentation_multiplier", "nauvis_segmentation_multiplier",
                 "distance", EU2_CX, EU2_CY, EU_CITY, K_SPAWN_LAKE, K_SPAWN_BIAS},

  -- The fine field per map (design constraint 3): map key -> {every version's elevation entry and
  -- every term only it reads}. The constant-coast twin turns each into a constant; no Entity,
  -- decorative or Cliff root on a Terra Nauvis preset may reach one. The start land guarantee is
  -- analytic but belongs to the field by ARCHITECTURE.md's firewall rule; the spawn lake, the bias,
  -- distance and the city fold are firewall-clean (the start mask reads the lake and the bias).
  firewall = {
    europe = {EU_ENTRY, EU_GEO, EU_DETAIL, EU_FAR, EU2_ENTRY, EU2_GEO, EU2_DETAIL, EU2_FAR, EU2_LAKES, START_LAND},
  },

  -- Per geography release: {release = <version>, map = <map key>, geography = <tn_geo id>, names =
  -- {<noise names>}, files = {<generated files>}}. Every name here is registered in
  -- tests/frozen.json by the milestone that adds it and never changes in place. Each row
  -- names one geography id with the map it belongs to; an id appears in one row only and never
  -- moves to another map, and each geography version's geo_id has its row under its map
  -- (tnconfig's id-space check).
  release_registry = {
    {
      release = "0.1.0",
      map = "europe",
      geography = 1,
      names = {EU_GX, EU_GY, EU_U, EU_V, EU_GEO, EU_LAND_COARSE, EU_DETAIL, EU_FAR, EU_ENTRY, START_MASK, EU_CX,
               EU_CY},
      files = {EU_GEO_FILE, EU_LAND_COARSE_FILE},
    },
    -- Geography 2 (spawn-cities): version 2's own chain and bodies, its frozen offset fallbacks, the
    -- start mask v2 and the spawn bodies, and the spawn bearings they read; the geo and coarse files
    -- are geography 1's, bound to version 2's chain.
    {
      release = "0.1.0",
      map = "europe",
      geography = 2,
      names = {EU2_GX, EU2_GY, EU2_U, EU2_V, EU2_GEO, EU2_LAND_COARSE, EU2_DETAIL, EU2_FAR, EU2_ENTRY, START_MASK2,
               EU2_CX, EU2_CY, EU_CITY_INDEX, EU_CITY_CX, EU_CITY_CY, EU_SPAWN_LAKE, EU_SPAWN_BIAS, EU2_LAKES,
               START_LAND, DISTANCE},
      files = {EU_GEO_FILE, EU_LAND_COARSE_FILE, EU_SPAWN_FILE},
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
    far_floor = -100,
    edge_water = -1,
    edge_min_scale = 3,
  },

  -- The start mask: vanilla's starting_resources_lake_mask with the map's coarse land
  -- field in place of elevation. `versions` holds every version, oldest first: a geography version
  -- names the one its preset bakes, and older ones stay defined, unchanged, for the saves that name
  -- them. Each names its formula (spawn.lua builds formula n from the version's
  -- numbers): formula 1 is clamp((tn_scale * tn_land_coarse - floor) / span, 0, 1). Formula 2
  -- (spawn-cities) reads the coarse field in reference pixels instead, so it is the same at every
  -- scale, and keeps starting ore off the spawn lake as vanilla's mask does with its own lake:
  -- clamp((min(coarse_gain * tn_land_coarse, tn_spawn_lake) - floor) / span, 0, 1) * tn_spawn_bias.
  -- Formula 1 never reaches vanilla's full mask within 11 tiles of the coarse coast nor anywhere at
  -- scale 1 (S7: the mask starves starting ore below elevation 11); formula 2 is full where the
  -- coarse field reads 5.5 or more and graded below it, so starting ore prefers ground well inside
  -- the coast (the coarse field is no calibrated distance: near coasts it reads land over estuaries
  -- and inlets, which at scale 1 lie inside the start area; spawn-cities measured London's stone
  -- there). On a coastal start the bias tilts the start area toward the city's own land.
  start_mask = {
    versions = {
      {name = START_MASK, formula = 1, floor = 1, span = 10},
      {name = START_MASK2, formula = 2, floor = 1, span = 10, coarse_gain = 2},
    },
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
  spawn = {
    random_value = "random",
    hash = {small_mult = 157, high_mult = 97, high_div = 65536},
    lake = {distance = 72, bearings = 16, magnitude = 2.5, offset = 3, divisor = 8,
            noise = {seed1 = 7201, wavelength = 12, amplitude = 4}},
    bias = {radius = 150, excluder = 40, widths = {50, 75, 100, 150}, seed = 7203, layouts = 150, ores = 4,
            candidates = 32, region = 450, spacing = 30, patch = {7, 14}, share = 0.5, margin = 0.005},
    land = {radius = 16, slope = 0.5},
    inland_lakes = {
      seed1 = 7202, region = 1024, per_region = 8, radius = 24, level = 1 / 3, gain = 12, candidates = 32,
      spacing = 128, cone_divisor = 3,
      shore = {seed1 = 7204, wavelength = 8, amplitude = 1},
      coast_px = 2.5, coast_gain = 20, start_radii = 1.5, start_slope = 0.25,
    },
  },

  -- Control-stage messages: the locale section and keys (locale/en/terra-nauvis.cfg). notice_withheld
  -- is the Map type notice where the map's preset is withheld (presets.withheld_with); drift_update
  -- is the drift line for a Map type fallback that moved with the mod itself rather than with a
  -- startup setting (a frozen fallback never should: the line is a tripwire); withheld_beside warns
  -- an Earth world whose preset is withheld beside a mod it now loads with; start is the start
  -- message (D29), rso the RSO warning (D32) and drift_city the drift line for a changed spawn-city
  -- setting on an Earth world (spawn-cities). Messages name a world's
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
    },
  },

  -- Toggles, keyed like settings: key -> {setting = <settings key>, preset_key = <key>, default,
  -- mechanism = "name switch" or "hook gate", on = <name>, off = <name>, maps = {<map keys>}};
  -- toggle_order lists the keys. Each toggle arrives with its milestone.
  toggles = {},
  toggle_order = {},
}
