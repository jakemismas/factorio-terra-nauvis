-- Spawn expressions (ARCHITECTURE.md, "Expression inventory"; milestones europe-coast and spawn-cities).
--
-- The start mask: vanilla's starting_resources_lake_mask reads elevation
-- in every starting-ore spot noise, which on an Earth preset would carry the fine coast into the
-- Entity program. Earth presets point that key at a start mask version (config.lua's start_mask;
-- each geography version names the one its preset bakes), and every version stays defined,
-- unchanged, for the saves that name it. Each version names its formula:
--   1: vanilla's mask with the map's coarse land field in place of elevation,
--      clamp((scale * tn_land_coarse - floor) / span, 0, 1) (europe-coast).
--   2: the coarse field in reference pixels and the map's spawn lake, as vanilla's mask reads its
--      own starting lake through elevation, times the map's starting-ore bias,
--      clamp((min(gain * tn_land_coarse, tn_spawn_lake) - floor) / span, 0, 1) * tn_spawn_bias
--      (spawn-cities).
-- Neither reads a firewall name. tn_land_coarse, tn_spawn_lake and tn_spawn_bias are preset keys:
-- each Earth preset names its map's bodies.
--
-- The spawn (spawn-cities; S7 option ii): every geography read of a version with a spawn record
-- shifts by the chosen city's offset, so the city sits at world (0, 0), where vanilla's start
-- features stay: the 196 starting chunks, freeplay's crash site, the starting ore and the enemy-free
-- disc, which read distance, redirected on Earth presets to the distance from the origin. The city
-- fold turns the map-qualified per-save city number (0 random) into the resolved index and the tile
-- offset of the city's pixel centre, scale (col - wr) + floor(scale / 2) (the tile holding the
-- centre, S8's convention); it folds to constants, so the chain's constant slots accept it (S7: Tile
-- 9,350 for 1, 30 or 50 cities). Also here: each map's analytic spawn lake and starting-ore bias,
-- both on the city's generated bearing (tools/build_spawn.py), the start land guarantee and each
-- version's inland lakes, which the version's elevation entry composes (coast.lua). Every number
-- comes from config.lua, the city tables and the generated bearings (S-5). A body that several
-- versions name is defined once, and two versions that would build it differently fail at load.
local cfg = require("prototypes.config")
local cities = require("prototypes.tables.cities")
-- destroyed-europe: the cities its zone covers, which a random pick on a world with the zone on skips
local destroyed = require("prototypes.tables.destroyed")

-- One require per generated file the release registry lists (the registration scan reads literal
-- module names), keyed by its path as config.lua's release_registry files and spawn records name it.
local FILES = {
  ["prototypes/generated/spawn_europe_v1.lua"] = require("prototypes.generated.spawn_europe_v1"),
}

local K = cfg.keys
local S = cfg.spawn

local function num(v)
  return string.format(cfg.number_format, v)
end

-- A number as an operand: negative values in parentheses, so "a - b" never reads "a - -b".
local function operand(v)
  if v < 0 then
    return "(" .. num(v) .. ")"
  end
  return num(v)
end

local E, defined = {}, {}
local function text_of(expression, locals)
  local keys = {}
  for k in pairs(locals or {}) do
    keys[#keys + 1] = k
  end
  table.sort(keys)
  local parts = {expression}
  for _, k in ipairs(keys) do
    parts[#parts + 1] = k .. "=" .. locals[k]
  end
  return table.concat(parts, "\n")
end

local function def(name, expression, locals)
  local text = text_of(expression, locals)
  if defined[name] ~= nil then
    if defined[name] ~= text then
      error("two geography versions build " .. name .. " differently: a changed body takes a new name")
    end
    return
  end
  defined[name] = text
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The formulas a start mask version can name, by number. A registered version keeps its formula
-- for good, so a change is a new formula under a new version.
local FORMULAS = {
  function(M)
    return "clamp((" .. K.scale .. " * " .. K.land_coarse .. " - " .. num(M.floor) .. ") / " .. num(M.span) ..
      ", 0, 1)"
  end,
  function(M)
    return "clamp((min(" .. num(M.coarse_gain) .. " * " .. K.land_coarse .. ", " .. K.spawn_lake .. ") - " ..
      num(M.floor) .. ") / " .. num(M.span) .. ", 0, 1) * " .. K.spawn_bias
  end,
}

for _, M in ipairs(cfg.start_mask.versions) do
  local formula = FORMULAS[M.formula]
  if not formula then
    error("the start mask " .. M.name .. " names formula " .. tostring(M.formula) .. ", which spawn.lua lacks")
  end
  def(M.name, formula(M))
end

-- One basis-noise octave; with (cx, cy) it reads geo tiles (the offset is added before the input
-- scale), so the same ground gets the same noise at every spawn.
local function noise(seed1, wavelength, cx, cy)
  local shift = ""
  if cx then
    shift = ", offset_x = " .. cx .. ", offset_y = " .. cy
  end
  return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = " .. num(1) ..
    " / " .. num(wavelength) .. shift .. "}"
end

-- Destroyed Europe's random pool (milestone destroyed-europe; APPROVALS 10): the city fold's hash modulo the
-- number of the map's cities outside the zone, then that city's index of 1 to n. A preset with the zone on
-- and the spawn city at random bakes this body as the map's city number, so the fold resolves it as it
-- resolves a chosen city; the index folds to a constant like the fold's own pick.
local function pool_body(name, key, setting, tbl)
  local inside = {}
  for _, value in ipairs(destroyed.zone_cities[key] or {}) do
    if not tbl.cities[value] then
      error("prototypes/tables/destroyed.lua lists " .. value .. ", which the city table of " .. key .. " lacks")
    end
    inside[value] = true
  end
  local pool = {}
  for i, value in ipairs(setting.allowed_values) do
    if i > 1 and not inside[value] then
      pool[#pool + 1] = i - 1
    end
  end
  local H = S.hash
  local text = num(pool[#pool])
  for k = #pool - 1, 1, -1 do
    text = "if(pool_pick == " .. num(k) .. ", " .. num(pool[k]) .. ", " .. text .. ")"
  end
  def(name, text, {pool_pick = "(map_seed_small * " .. num(H.small_mult) .. " + floor(map_seed / " ..
    num(H.high_div) .. ") * " .. num(H.high_mult) .. ") % " .. num(#pool) .. " + 1"})
end

-- The spawn bodies of one geography version of a map (its spawn record names them).
local function spawn(map_key, v)
  local sp = v.spawn
  local m = cfg.maps[map_key]
  local setting = cfg.settings[sp.city_setting]
  local tbl = cities[map_key]
  if not (setting and tbl) then
    error("config.lua gives " .. v.entry .. " a spawn record without its setting or city table")
  end
  local data = FILES[sp.bearings]
  if not data then
    error("no generated spawn bearings are loaded from " .. tostring(sp.bearings) .. " for " .. v.entry)
  end
  local s = K.scale
  local dist = sp.distance

  -- distance on Earth presets: from the spawn, which the shift keeps at the origin, whatever
  -- starting_points holds (S7: one patch per ore, 0 enemies within 150 tiles).
  def(dist, "sqrt(x * x + y * y)")

  -- The start land guarantee: land inside `radius` tiles of the spawn, -inf (neutral for max) beyond.
  local G = S.land
  def(sp.start_land, "if(" .. dist .. " < " .. num(G.radius) .. ", (" .. num(G.radius) .. " - " .. dist .. ") * " ..
    num(G.slope) .. " + " .. num(cfg.coast.transfer_offset) .. ", -inf)")

  -- The cities in the setting's order (its first value is random), as reference pixels.
  local px = cfg.coordinates.px_per_degree
  local list = {}
  for i, value in ipairs(setting.allowed_values) do
    if i > 1 then
      local c = tbl.cities[value]
      if not c then
        error("the city table of " .. map_key .. " has no row " .. value)
      end
      list[#list + 1] = {value = value, col = math.floor((c.lon - m.lon_left_edge) * px),
                         row = math.floor((m.lat_top_edge - c.lat) * px)}
    end
  end
  local n = #list
  local H = S.hash
  -- random (0): the folded hash of map_seed, an index of 1 to n
  def(sp.city_index, "if(" .. sp.city .. " > 0, " .. sp.city .. ", (map_seed_small * " .. num(H.small_mult) ..
    " + floor(map_seed / " .. num(H.high_div) .. ") * " .. num(H.high_mult) .. ") % " .. num(n) .. " + 1)")

  -- Destroyed Europe's random pool (milestone destroyed-europe; APPROVALS 10): pool_body above, one per map
  -- (every version with a spawn record names the same body, which def defines once).
  local pool_name = cfg.destroyed and cfg.destroyed.pools[map_key]
  if pool_name then
    pool_body(pool_name, map_key, setting, tbl)
  end

  local function chain(field, radius)
    local text = "0"
    for k = n, 1, -1 do
      text = "if(" .. sp.city_index .. " == " .. num(k) .. ", " .. operand(list[k][field] - radius) .. ", " .. text ..
        ")"
    end
    return text
  end
  local corner = "floor(" .. s .. " / " .. num(cfg.coordinates.corner_offset_divisor) .. ")"
  def(v.city_offset[1], s .. " * " .. chain("col", m.wr) .. " + " .. corner)
  def(v.city_offset[2], s .. " * " .. chain("row", m.hr) .. " + " .. corner)

  -- The city's generated bearing and coastal flag at the save's scale: an if() chain over the index,
  -- each branch one over the scale; folds to a constant like the offsets.
  local function by_city_scale(field, value_of)
    local text = "0"
    for k = n, 1, -1 do
      local per_scale = data[field][list[k].value]
      if not per_scale then
        error("the spawn bearings of " .. map_key .. " lack " .. list[k].value)
      end
      local inner = value_of(per_scale[#per_scale])
      for si = #per_scale - 1, 1, -1 do
        inner = "if(" .. s .. " == " .. num(si) .. ", " .. value_of(per_scale[si]) .. ", " .. inner .. ")"
      end
      text = "if(" .. sp.city_index .. " == " .. num(k) .. ", " .. inner .. ", " .. text .. ")"
    end
    return text
  end
  local L = S.lake
  local turn = 2 * math.pi / L.bearings
  local angle = by_city_scale("bearings", function(b)
    return operand(b * turn)
  end)

  -- The spawn lake: centre `distance` tiles out on the bearing; water where d + n is under
  -- offset * divisor.
  def(sp.spawn_lake, num(L.magnitude) .. " * ((lake_d + lake_n) / " .. num(L.divisor) .. " - " .. num(L.offset) ..
    ")", {
      lake_angle = angle,
      lake_x = num(L.distance) .. " * cos(lake_angle)",
      lake_y = num(L.distance) .. " * sin(lake_angle)",
      lake_d = "sqrt((x - lake_x) * (x - lake_x) + (y - lake_y) * (y - lake_y))",
      lake_n = num(L.noise.amplitude) .. " * " .. noise(L.noise.seed1, L.noise.wavelength),
    })

  -- The starting-ore bias: on a coastal start, a tilt of the start area toward the city's own land
  -- (the generated bias bearing and width).
  def(sp.spawn_bias, "if(bias_on > 0, clamp(1 + (x * cos(bias_angle) + y * sin(bias_angle)) / bias_width, 0, 1), 1)",
    {
      bias_on = by_city_scale("coastal", operand),
      bias_angle = by_city_scale("bias", function(b)
        return operand(b * turn)
      end),
      bias_width = by_city_scale("bias_width", operand),
    })

  -- The inland lakes: spot noise in the version's geo tiles, a fixed count of conical spots per
  -- region, with rough shores; positive (no lake) within coast_px of the version's coast fit and
  -- inside start_radii start radii of the spawn.
  local I = S.inland_lakes
  local quantity = math.pi * I.radius * I.radius / I.cone_divisor   -- a cone of peak 1
  local spots = "spot_noise{x = " .. v.gx .. ", y = " .. v.gy .. ", density_expression = " ..
    num(quantity * I.per_region / (I.region * I.region)) .. ", spot_quantity_expression = " .. num(quantity) ..
    ", spot_radius_expression = " .. num(I.radius) .. ", spot_favorability_expression = " .. num(1) ..
    ", seed0 = map_seed, seed1 = " .. num(I.seed1) .. ", basement_value = " .. num(0) ..
    ", maximum_spot_basement_radius = " .. num(2 * I.radius) .. ", region_size = " .. num(I.region) ..
    ", candidate_spot_count = " .. num(I.candidates) .. ", suggested_minimum_candidate_point_spacing = " ..
    num(I.spacing) .. ", hard_region_target_quantity = " .. num(1) .. "}"
  def(sp.inland_lakes, "max(" .. num(I.gain) .. " * (" .. num(I.level) .. " - lake_spot) + lake_shore, " ..
    num(I.coast_gain) .. " * (" .. num(I.coast_px) .. " - " .. v.geo .. "), (" .. num(I.start_radii) ..
    " * starting_area_radius - " .. dist .. ") * " .. num(I.start_slope) .. ")", {
      lake_spot = spots,
      lake_shore = num(I.shore.amplitude) .. " * " .. noise(I.shore.seed1, I.shore.wavelength, v.cx, v.cy),
    })
end

for _, key in ipairs(cfg.map_order) do
  local g = cfg.geography[key]
  for _, v in ipairs(g and g.versions or {}) do
    if v.spawn then
      spawn(key, v)
    end
  end
end

data:extend(E)
