-- Terra Nauvis: the single source of names and constants (ARCHITECTURE.md, "Module map").
--
-- Pure data: this file reads no data, settings, game or script and calls no function, so the
-- settings, data and control stages (through require) and the Python tools (tools/tnconfig.py,
-- through luaparser) all read this one file. Every name the mod defines derives from ID or NOISE,
-- so renaming the mod is an edit here (D36). No other Lua file spells an Earth name or a map
-- coordinate (T16 name scan and design rules).

local ID = "terra-nauvis"
local NOISE = "tn_"

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
  -- At scale s, tile t samples pixel floor(t / s + wr) (the floor origin); the tent mapping's
  -- integer-corner offset is floor(s / corner_offset_divisor) tiles (europe-coast proves it).
  coordinates = {
    px_per_degree = 45,
    origin = "floor",
    corner_offset_divisor = 2,
  },

  -- The one number formatter every expression string uses, so the text is byte-stable.
  number_format = "%.9g",

  -- EarthMaps reference rasters (data-src/earthmaps/<key>.json): size, EarthMaps radii and edges.
  maps = {
    europe = {
      key = "europe", setting_key = "europe", display = "Europe",
      width_px = 2400, height_px = 1704, wr = 1200, hr = 852,
      lon_left_edge = -11.0222, lat_top_edge = 71.9333,
    },
    atlantic = {
      key = "atlantic", setting_key = "atlantic", display = "Atlantic",
      width_px = 15689, height_px = 6524, wr = 7844, hr = 3262,
      lon_left_edge = -168.6444, lat_top_edge = 87.1778,
    },
    olde_world = {
      key = "olde_world", setting_key = "old-world", display = "Old World",
      width_px = 8963, height_px = 5847, wr = 4481, hr = 2923,
      lon_left_edge = -19.1778, lat_top_edge = 82.0889,
    },
  },
  map_order = {"europe", "atlantic", "olde_world"},

  -- Integer scales 1 to 6 tiles per reference pixel.
  scales = {values = {1, 2, 3, 4, 5, 6}, default = 6},

  -- Mod settings. Values are short ASCII tokens, so labels can change without invalidating stored
  -- values (S11). Each milestone that adds a setting adds it here and to tests/design-rules.json.
  settings = {
    scale = {
      name = ID .. "-scale", type = "string-setting", setting_type = "startup",
      default_value = "6", allowed_values = {"1", "2", "3", "4", "5", "6"}, order = "a",
    },
  },
  setting_order = {"scale"},

  -- Map-gen presets, sorted right after Default ("a") and before Rich resources ("b") (S13).
  presets = {
    europe = {name = ID .. "-europe", map = "europe", order = "a-tn-a", placeholder = true},
  },
  preset_order = {"europe"},

  -- The placeholder preset (milestone toolchain): a coarse land shape so installCheck has an Earth
  -- preview. The placeholder map's world extent at the placeholder scale is land (vanilla terrain
  -- inside) and everything beyond it is ocean; the world origin sits at the corner of reference
  -- pixel spawn_px (col, row), near the extent's west edge, so the coast shows beside the spawn.
  -- Its names are marked here as placeholder: freeze never registers them, the frozen checker
  -- skips them, and build_zip.py --release refuses while any exists. europe-coast retires it with
  -- every registration it made.
  --
  -- Design constraint 3 holds on this preset too: it redirects starting_resources_lake_mask to an
  -- Earth copy of vanilla's start mask that reads elevation_nauvis (vanilla 2.1.23's body,
  -- clamp((elevation - start_mask_floor) / start_mask_span, 0, 1), with elevation_nauvis in place
  -- of elevation), so no Entity, decorative or Cliff root reaches the placeholder shape.
  -- placeholder.firewall lists which of these names form the fine field (isolation checks).
  -- withheld_with lists the mods whose presence withholds the preset: Alien Biomes 0.8.0's palms
  -- read elevation in the Entity program, and only climate-tiles' palm switch makes an Earth
  -- preset safe beside them (design note 9). It withholds presets marked placeholder only:
  -- from europe-coast to climate-tiles the real presets exist beside AB with that leak outside the
  -- gate (ARCHITECTURE.md, S-3).
  placeholder = {
    preset = "europe",
    map = "europe",
    scale = 6,
    spawn_px = {16, 852},
    shore_tiles = 8,
    sea_floor = -20,
    start_mask_floor = 1,
    start_mask_span = 10,
    names = {
      elevation = NOISE .. "placeholder_elevation_europe",
      starting_resources_lake_mask = NOISE .. "placeholder_start_mask_europe",
    },
    keys = {"elevation", "starting_resources_lake_mask"},
    firewall = {"elevation"},
    withheld_with = {"alien-biomes"},
  },

  -- Every property_expression_names key any Earth preset sets (D33 guard, missing-name guard, T14).
  preset_keys = {"elevation", "starting_resources_lake_mask"},

  -- The fine field per map (design constraint 3): map key -> {the map's elevation entry and every
  -- term only it reads}. Empty until europe-coast adds Europe's.
  firewall = {},

  -- The Map type fallbacks per map (U3's one exemption): map key -> {{name = <noise name>,
  -- map_qualified = <bool>}, ...}, the names that map's elevation entry reads which a Map type pick
  -- leaves to prototype-level fallbacks. Never registered in tests/frozen.json. Empty until
  -- europe-coast.
  fallbacks = {},

  -- Per release: {release = <version>, geography = <id>, names = {<noise names>}, files =
  -- {<generated files>}}. Empty until europe-coast registers the first versioned bodies
  -- (tests/frozen.json).
  release_registry = {},

  -- Toggles, keyed like settings: key -> {setting = <settings key>, preset_key = <key>, default,
  -- mechanism = "name switch" or "hook gate", on = <name>, off = <name>, maps = {<map keys>}};
  -- toggle_order lists the keys. Each toggle arrives with its milestone.
  toggles = {},
  toggle_order = {},
}
