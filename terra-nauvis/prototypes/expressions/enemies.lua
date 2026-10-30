-- The enemy layer (ARCHITECTURE.md milestone contract 9; S6 A6E; APPROVALS 1b; D24; milestone
-- resources-enemies).
--
-- A second spot_noise built like vanilla's enemy_base_probability (base/prototypes/noise-
-- expressions.lua:19-50) in its own seed1: density (mult - 1) times vanilla's at candidates inside
-- enemy_share of a hotspot footprint (each row of prototypes/tables/hotspots.lua, its disc the region
-- layer's row of the same id, read through its depth), quantity and favourability on land only
-- (tn_land_coarse), and nothing within start_factor times starting_area_radius of the
-- spawn, where vanilla's own start term keeps the start free too. Spot radius, quantity and
-- frequency read vanilla's enemy_base_radius and enemy_base_frequency by name, so bobenemies'
-- intensity cap applies to the layer as it does to the live expression (R5). Outside its spots the
-- layer is -inf, so the wrapper data-final-fixes.lua builds, max(live, layer), equals the live
-- expression there to the bit. The per-map rows fold on tn_map (the wrapper is preset-only).
-- Every name and number comes from config.lua (S-5).
local cfg = require("prototypes.config")
local T = require("prototypes.tables.hotspots")

local HC = cfg.hotspots
local EN = cfg.enemies
local K = cfg.keys
local S = K.scale
local SUFFIX = cfg.regions.names.suffix
local DEPTH = cfg.regions.names.row.depth

local function num(v)
  return string.format(cfg.number_format, v)
end

local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] then
    MAPS[#MAPS + 1] = {key = key, id = cfg.maps[key].id}
  end
end

local function footprint(r)
  return "min(max(" .. num(r.radius_px) .. " * " .. S .. ", " .. num(HC.floor_tiles) .. "), " .. num(r.cap_px) ..
    " * " .. S .. ")"
end

-- A candidate inside enemy_share of the row's footprint (the disc's roughened distance).
local function core(r)
  return "(" .. DEPTH .. r.id .. SUFFIX .. " > " .. num(r.radius_px) .. " * " .. S .. " - " .. num(HC.enemy_share) ..
    " * " .. footprint(r) .. ")"
end

local LAND = "(" .. K.land_coarse .. " > " .. num(HC.land_px) .. ")"

-- One map's layer spot over its rows, or nothing where it adopts none.
local function map_spot(map_key)
  local mults, cores = {}, {}
  for _, r in ipairs(T.rows) do
    local on = false
    for _, mk in ipairs(r.maps) do
      on = on or mk == map_key
    end
    if on and r.mult > 1 then
      mults[#mults + 1] = num(r.mult - 1) .. " * " .. core(r)
      cores[#cores + 1] = core(r)
    end
  end
  if #cores == 0 then
    return nil
  end
  local any = "(" .. table.concat(cores, " + ") .. ")"
  return "spot_noise{x = x, y = y, density_expression = (" .. table.concat(mults, " + ") ..
    ") * spot_quantity_expression * max(0, enemy_base_frequency), spot_quantity_expression = " ..
    "spot_quantity_expression * " .. any .. " * " .. LAND .. ", spot_radius_expression = spot_radius_expression, " ..
    "spot_favorability_expression = " .. any .. " * (1 + " .. LAND .. "), seed0 = map_seed, seed1 = " ..
    num(EN.seed1) .. ", region_size = " .. num(EN.region_size) .. ", candidate_point_count = " .. num(EN.candidates) ..
    ", hard_region_target_quantity = 0, basement_value = " .. num(EN.basement) .. ", maximum_spot_basement_radius = " ..
    num(EN.basement_radius) .. "}"
end

local branch, any_map = {}, false
for i, M in ipairs(MAPS) do
  branch[i] = map_spot(M.key)
  any_map = any_map or branch[i] ~= nil
end

local E = {}
if any_map then
  local fold = branch[#branch] or num(EN.basement)
  for i = #branch - 1, 1, -1 do
    fold = "if(" .. K.map .. " == " .. num(MAPS[i].id) .. ", " .. (branch[i] or num(EN.basement)) .. ", " .. fold .. ")"
  end
  -- vanilla's blob and start terms, in the layer's own seed1
  local BL = EN.blob
  local blobs = {}
  for _, o in ipairs(BL.octaves) do
    blobs[#blobs + 1] = "blob(" .. num(o.input_scale) .. ", " .. num(o.output_scale) .. ")"
  end
  local texture = "(" .. table.concat(blobs, " + ") .. " - " .. num(BL.mean) .. ") * spot_radius_expression / " ..
    num(BL.radius_divisor) .. " * (" .. num(BL.near) .. " + " .. num(BL.far) .. " * clamp(distance / " ..
    num(BL.far_distance) .. ", 0, 1)) - " .. num(BL.offset) .. " + min(0, " .. num(BL.start_depth) ..
    " / starting_area_radius * distance - " .. num(BL.start_depth) .. ")"
  E[#E + 1] = {
    type = "noise-expression",
    name = EN.layer,
    expression = "if((spot > 0) * (distance > " .. num(EN.start_factor) .. " * starting_area_radius) > 0, spot + " ..
      texture .. ", -inf)",
    local_expressions = {
      spot_radius_expression = "max(0, enemy_base_radius)",
      spot_quantity_expression = "pi * " .. num(EN.quantity_factor) .. " * spot_radius_expression ^ " ..
        num(EN.radius_power),
      spot = fold,
    },
    local_functions = {
      blob = {
        parameters = {"input_scale", "output_scale"},
        expression = "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(EN.seed1) ..
          ", input_scale = input_scale, output_scale = output_scale}",
      },
    },
  }
end

if #E > 0 then
  data:extend(E)
end
