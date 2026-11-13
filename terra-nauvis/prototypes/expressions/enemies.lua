-- The enemy layer (ARCHITECTURE.md, "Expression inventory" and "Stable hooks").
--
-- A second spot_noise built like vanilla's enemy_base_probability (base/prototypes/noise-
-- expressions.lua:19-50) in its own seed1, from the installed expression's own parts, which
-- prototypes/installed.lua reads at load time (config.lua enemies.base), so this file and config.lua
-- hold none of its text: density (mult - 1) times vanilla's at candidates inside
-- enemy_share of a hotspot footprint (each row of prototypes/tables/hotspots.lua, its disc the region
-- layer's row of the same id, read through its depth), quantity and favourability on land only
-- (tn_land_coarse, design rule 8), and nothing within start_factor times starting_area_radius of the
-- spawn, where vanilla's own start term keeps the start free too. Spot radius, quantity and
-- frequency read vanilla's enemy_base_radius and enemy_base_frequency by name, so bobenemies'
-- intensity cap applies to the layer as it does to the live expression. Outside its spots the
-- layer is -inf, so the wrapper data-final-fixes.lua builds, max(live, layer), equals the live
-- expression there to the bit. The per-map rows fold on tn_map (the wrapper is preset-only).
-- Every name and number comes from config.lua.
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
local installed = require("prototypes.installed")

-- The installed enemy base expression in parts, or nil where it has not the shape this version reads: every layer
-- is then neutral.
local EB = EN.base
local BASE, why = installed.enemy_base(data.raw["noise-expression"], EB)
if not BASE then
  log(cfg.identity.title .. ": " .. why .. ", so the enemy layer is off and the live expression places every base")
elseif not BASE.known then
  log(cfg.identity.title .. ": the installed " .. EB.name ..
    " is not the text this version was tested with; the enemy layer follows the installed text")
end

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
local function map_spot(map_key, rows, shared, clusters, fade)
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
  -- 1.2.0 (config.lua hotspots_v4): the density times the start fade's t at the candidate, and no cone where t is 0
  local faded, gate = "", ""
  if fade then
    faded, gate = "fade_t * ", " * (fade_t > 0)"
  end
  -- the installed spot call with the layer's density, quantity, favourability and seed
  return installed.render(BASE.spot, {
    [EB.args.density] = function(live)
      return faded .. more .. "(" .. table.concat(mults, " + ") .. ") * " .. live
    end,
    [EB.args.quantity] = function(live)
      return live .. " * " .. any .. " * " .. LAND .. gate
    end,
    [EB.args.favorability] = function()
      return any .. " * (1 + " .. LAND .. ")" .. gate
    end,
    [EB.own] = function()
      return num(EN.seed1)
    end,
  })
end

-- The second table's height: see the file's head and config.lua hotspots_v2.nests.
local function cluster_height(oil)
  local scaled = "min(1, " .. S .. " / " .. num(N2.full_scale) .. ")"
  local parts = {"min(spot, " .. num(N2.level) .. ")", num(N2.lobe) .. " * " .. scaled .. " * " .. H2.lobe.name}
  for i, scale in ipairs(BASE.scales) do
    parts[#parts + 1] = EB.texture .. "(" .. num(scale) .. ", " .. num(N2.grain[i]) .. ")"
  end
  parts[#parts + 1] = num(N2.small_map) .. " * (1 - " .. scaled .. ")"
  parts[#parts + 1] = num(N2.near) .. " * (1 - clamp(distance / " .. num(N2.full_distance) .. ", 0, 1))"
  local RD = N2.radius
  parts[#parts + 1] = num(N2.capped) .. " * (spot_radius_expression / (" .. num(RD.base) .. " + " .. num(RD.gain) ..
    " * clamp(distance, 0, " .. num(N2.full_distance) .. ") / " .. num(RD.span) .. ") - 1)"
  return "if(0 < " .. table.concat(parts, " + ") .. " - " .. num(N2.offset) .. ", " .. num(N2.height) .. ", -1) - " ..
    num(N2.clear) .. " * (" .. (oil or H2.bodies["crude-oil"]) .. " > 0)" .. BASE.start
end

local E = {}

-- Whether any map adopts a row of `rows` with a density over 1: only then does a layer stand.
local function adopted(rows)
  for _, M in ipairs(MAPS) do
    for _, r in ipairs(rows) do
      for _, mk in ipairs(r.maps) do
        if mk == M.key and r.mult > 1 then
          return true
        end
      end
    end
  end
  return false
end

-- The layer over `rows`, under `name`.
local function layer(name, rows, shared, clusters, fade, oil)
  if not BASE then
    if adopted(rows) then
      E[#E + 1] = {type = "noise-expression", name = name, expression = EB.neutral}
    end
    return
  end
  local branch, any_map = {}, false
  for i, M in ipairs(MAPS) do
    branch[i] = map_spot(M.key, rows, shared, clusters, fade)
    any_map = any_map or branch[i] ~= nil
  end
  if not any_map then
    return
  end
  local fold = branch[#branch] or BASE.basement
  for i = #branch - 1, 1, -1 do
    fold = "if(" .. K.map .. " == " .. num(MAPS[i].id) .. ", " .. (branch[i] or BASE.basement) .. ", " .. fold .. ")"
  end
  -- vanilla's texture and start terms, radius and quantity, with the texture function in the layer's own seed1
  local locals = shared or {}
  locals[EB.radius] = BASE.radius
  locals[EB.quantity] = BASE.quantity
  locals.spot = fold
  if fade then
    locals.fade_t = require("prototypes.ore_curves").fade("distance")
  end
  E[#E + 1] = {
    type = "noise-expression",
    name = name,
    expression = "if((spot > 0) * (distance > " .. num(EN.start_factor) .. " * starting_area_radius) > 0, " ..
      (clusters and cluster_height(oil) or ("spot + " .. BASE.texture)) .. ", -inf)",
    local_expressions = locals,
    local_functions = {
      [EB.texture] = {
        parameters = BASE.parameters,
        expression = installed.render(BASE.noise, {[EB.own] = function()
          return num(EN.seed1)
        end}),
      },
    },
  }
end

layer(EN.layer, T.rows)
-- The second hotspot table's rows (config.lua hotspots_v2): new worlds' presets name this body in the first one's
-- place.
layer(H2.enemy_layer, require("prototypes.hotspot_rows_v2").rows, {}, true)
-- The third table's rows (config.lua hotspots_v3, 0.3.1): the same layer over the rows with the moved discs.
layer(cfg.hotspots_v3.enemy_layer, require("prototypes.hotspot_rows_v3").rows, {}, true)
-- The start fade (config.lua hotspots_v4, 1.2.0): the third table's layer with its density times t, so a field's extra
-- nests fade toward the spawn with its ore. Where t is 0 no cone stands and the wrapper keeps the live bases, and past
-- r_out the layer is the third table's, its clusters kept clear of the fifth oil body's wells.
layer(cfg.hotspots_v4.enemy_layer, require("prototypes.hotspot_rows_v3").rows, {}, true, true, cfg.hotspots_v4.oil.body)
-- Lean ore (config.lua hotspots_v5): the same layer, its clusters kept clear of the lean oil body's wells.
layer(cfg.hotspots_v5.enemy_layer, require("prototypes.hotspot_rows_v3").rows, {}, true, true, cfg.hotspots_v5.oil.body)

if #E > 0 then
  data:extend(E)
end
