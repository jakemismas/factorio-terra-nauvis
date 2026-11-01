-- The enemy layer (ARCHITECTURE.md contract 9; S6 A6E; APPROVALS 1b;
-- D24).
--
-- A second spot_noise built like vanilla's enemy_base_probability (base/prototypes/noise-
-- expressions.lua:19-50) in its own seed1: density (mult - 1) times vanilla's at candidates inside
-- enemy_share of a hotspot footprint (each row of prototypes/tables/hotspots.lua, its disc the region
-- layer's row of the same id, read through its depth), quantity and favourability on land only
-- (tn_land_coarse, design rule 8), and nothing within start_factor times starting_area_radius of the
-- spawn, where vanilla's own start term keeps the start free too. Spot radius, quantity and
-- frequency read vanilla's enemy_base_radius and enemy_base_frequency by name, so bobenemies'
-- intensity cap applies to the layer as it does to the live expression (R5). Outside its spots the
-- layer is -inf, so the wrapper data-final-fixes.lua builds, max(live, layer), equals the live
-- expression there to the bit. The per-map rows fold on tn_map (the wrapper is preset-only).
-- Every name and number comes from config.lua (S-5).
--
-- The second table's layer is built otherwise. Far from a start vanilla's bases and this layer's cones both pass
-- enemy_autoplace_base's cap of 0.25 over most of their width, so a spawner goes down wherever its bounding box fits
-- and they lock into even rows at that spacing, the live bases as much as the layer's. So over a footprint the layer
-- stands in for the live expression (the wrapper config.lua hotspots_v2.nests names), as two values: clusters, where
-- the noise passes zero, at a height under the cap, and -1 between them. A height between the two would hold worms
-- alone, whose factor passes any small height, so there is none. See config.lua hotspots_v2.nests.
local cfg = require("prototypes.config")
local T = require("prototypes.tables.hotspots")

local HC = cfg.hotspots
local H2 = cfg.hotspots_v2
local N2 = H2.nests
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

-- The same over the whole of a row's ore footprint, so no live base stands in rows inside one.
local function whole(r)
  local R = footprint(r)
  R = r.least_tiles and ("max(" .. num(r.least_tiles) .. ", " .. R .. ")") or R
  return "(" .. DEPTH .. r.id .. SUFFIX .. " > " .. num(r.radius_px) .. " * " .. S .. " - " .. R .. ")"
end

local LAND = "(" .. K.land_coarse .. " > " .. num(HC.land_px) .. ")"

-- One map's layer spot over `rows`, or nothing where it adopts none. With `shared`, a row's core is a local of the
-- layer that every map reads, so its text stands once. With `clusters`, cones cover a footprint and only say where
-- clusters may stand.
local function map_spot(map_key, rows, shared, clusters)
  local mults, cores = {}, {}
  for j, r in ipairs(rows) do
    local on = false
    for _, mk in ipairs(r.maps) do
      on = on or mk == map_key
    end
    if on and r.mult > 1 then
      local c = clusters and whole(r) or core(r)
      if shared then
        shared["c" .. j] = c
        c = "c" .. j
      end
      mults[#mults + 1] = num(r.mult - 1) .. " * " .. c
      cores[#cores + 1] = c
    end
  end
  if #cores == 0 then
    return nil
  end
  local any = "(" .. table.concat(cores, " + ") .. ")"
  local more = clusters and ("(1 + " .. num(N2.spots) .. " * clamp((distance - " .. num(N2.spots_from) .. ") / " ..
    num(N2.spots_span) .. ", 0, 1)) * ") or ""
  return "spot_noise{x = x, y = y, density_expression = " .. more .. "(" .. table.concat(mults, " + ") ..
    ") * spot_quantity_expression * max(0, enemy_base_frequency), spot_quantity_expression = " ..
    "spot_quantity_expression * " .. any .. " * " .. LAND .. ", spot_radius_expression = spot_radius_expression, " ..
    "spot_favorability_expression = " .. any .. " * (1 + " .. LAND .. "), seed0 = map_seed, seed1 = " ..
    num(EN.seed1) .. ", region_size = " .. num(EN.region_size) .. ", candidate_point_count = " .. num(EN.candidates) ..
    ", hard_region_target_quantity = 0, basement_value = " .. num(EN.basement) .. ", maximum_spot_basement_radius = " ..
    num(EN.basement_radius) .. "}"
end

-- The second table's height: see the file's head and config.lua hotspots_v2.nests.
local function cluster_height(BL)
  local scaled = "min(1, " .. S .. " / " .. num(N2.full_scale) .. ")"
  local parts = {"min(spot, " .. num(N2.level) .. ")", num(N2.lobe) .. " * " .. scaled .. " * " .. H2.lobe.name}
  for i, o in ipairs(BL.octaves) do
    parts[#parts + 1] = "blob(" .. num(o.input_scale) .. ", " .. num(N2.grain[i]) .. ")"
  end
  parts[#parts + 1] = num(N2.small_map) .. " * (1 - " .. scaled .. ")"
  parts[#parts + 1] = num(N2.near) .. " * (1 - clamp(distance / " .. num(N2.full_distance) .. ", 0, 1))"
  local RD = N2.radius
  parts[#parts + 1] = num(N2.capped) .. " * (spot_radius_expression / (" .. num(RD.base) .. " + " .. num(RD.gain) ..
    " * clamp(distance, 0, " .. num(N2.full_distance) .. ") / " .. num(RD.span) .. ") - 1)"
  return "if(0 < " .. table.concat(parts, " + ") .. " - " .. num(N2.offset) .. ", " .. num(N2.height) .. ", -1) - " ..
    num(N2.clear) .. " * (" .. H2.bodies["crude-oil"] .. " > 0) + min(0, " .. num(BL.start_depth) ..
    " / starting_area_radius * distance - " .. num(BL.start_depth) .. ")"
end

local E = {}

-- The layer over `rows`, under `name`.
local function layer(name, rows, shared, clusters)
  local branch, any_map = {}, false
  for i, M in ipairs(MAPS) do
    branch[i] = map_spot(M.key, rows, shared, clusters)
    any_map = any_map or branch[i] ~= nil
  end
  if not any_map then
    return
  end
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
  local locals = shared or {}
  locals.spot_radius_expression = "max(0, enemy_base_radius)"
  locals.spot_quantity_expression = "pi * " .. num(EN.quantity_factor) .. " * spot_radius_expression ^ " ..
    num(EN.radius_power)
  locals.spot = fold
  E[#E + 1] = {
    type = "noise-expression",
    name = name,
    expression = "if((spot > 0) * (distance > " .. num(EN.start_factor) .. " * starting_area_radius) > 0, " ..
      (clusters and cluster_height(BL) or ("spot + " .. texture)) .. ", -inf)",
    local_expressions = locals,
    local_functions = {
      blob = {
        parameters = {"input_scale", "output_scale"},
        expression = "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(EN.seed1) ..
          ", input_scale = input_scale, output_scale = output_scale}",
      },
    },
  }
end

layer(EN.layer, T.rows)
-- The second hotspot table's rows (config.lua hotspots_v2): new worlds' presets name this body in the first one's
-- place.
layer(H2.enemy_layer, require("prototypes.hotspot_rows_v2").rows, {}, true)

if #E > 0 then
  data:extend(E)
end
