-- Waterway expressions (ARCHITECTURE.md, "Expression inventory" and "Stable hooks"; milestone waterways).
--
-- Per map and scale, four named sets from the generated files (tools/build_waterways.py): the rivers,
-- straits and turning basins (ww), the canals, the dams and the fords. Each reads only its map's geo
-- tiles in the chain of the geography version that composes them (its `waterways` record), bound here
-- to the locals X and Y, so they live in the Tile program alone (firewall rule); that version's
-- elevation entry (coast.lua) picks the save's scale's ww, canal and dam sets by name through the
-- folded scale, and its preset points the ford key at the map's ford set for its scale, which the
-- water-shallow hook in data-final-fixes.lua reads behind the gate.
--
-- Also the shared bodies: the gate's and the ford key's prototypes, which hold their off values, and
-- the canals switch's two neutral bodies. Every name and number comes from config.lua (S-5).
local cfg = require("prototypes.config")

-- One require per generated file (the registration scan reads literal module names), by map and scale.
local FILES = {
  europe = {
    require("prototypes.generated.waterways_europe_s1_v1"),
    require("prototypes.generated.waterways_europe_s2_v1"),
    require("prototypes.generated.waterways_europe_s3_v1"),
    require("prototypes.generated.waterways_europe_s4_v1"),
    require("prototypes.generated.waterways_europe_s5_v1"),
    require("prototypes.generated.waterways_europe_s6_v1"),
  },
  atlantic = {
    require("prototypes.generated.waterways_atlantic_s1_v1"),
    require("prototypes.generated.waterways_atlantic_s2_v1"),
    require("prototypes.generated.waterways_atlantic_s3_v1"),
    require("prototypes.generated.waterways_atlantic_s4_v1"),
    require("prototypes.generated.waterways_atlantic_s5_v1"),
    require("prototypes.generated.waterways_atlantic_s6_v1"),
  },
  olde_world = {
    require("prototypes.generated.waterways_olde_world_s1_v1"),
    require("prototypes.generated.waterways_olde_world_s2_v1"),
    require("prototypes.generated.waterways_olde_world_s3_v1"),
    require("prototypes.generated.waterways_olde_world_s4_v1"),
    require("prototypes.generated.waterways_olde_world_s5_v1"),
    require("prototypes.generated.waterways_olde_world_s6_v1"),
  },
}

local H = cfg.hooks

local function num(v)
  return string.format(cfg.number_format, v)
end

-- A copy of a generated local function, so no two prototypes share one Lua table.
local function fn(f)
  local locals = {}
  for k, v in pairs(f.local_expressions or {}) do
    locals[k] = v
  end
  local params = {}
  for i, p in ipairs(f.parameters) do
    params[i] = p
  end
  return {parameters = params, expression = f.expression, local_expressions = locals}
end

-- A version's chain class: its map and its city offset, which its preset bakes for its offset names
-- and their frozen fallbacks hold, so every version of a class reads equal geo tiles in every world
-- that reads one of them (coast.lua's chain_class; every version of a map binds the same files). A
-- landed version (config.lua landed_geographies) is a class of its own: its records never change.
local LANDED = {}
for _, id in ipairs(cfg.landed_geographies or {}) do
  LANDED[id] = true
end

local function chain_class(key, g)
  local o = g.city_offset
  if not (o and o[1] ~= nil and o[2] ~= nil) then
    error("geography version " .. tostring(g.entry) .. " has no city offset")
  end
  if LANDED[g.geo_id] then
    return key .. "|landed|" .. tostring(g.geo_id)
  end
  return key .. "|" .. tostring(o[1]) .. "|" .. tostring(o[2])
end

local E = {}
-- The sets of every geography version that composes them, bound to its chain, for every offered scale,
-- once per chain class: the newest version of a class that composes waterways keeps the bodies, so the
-- world its preset makes compiles exactly the program it did, and every older one names them by set and
-- scale. The game parses every body's text at startup, and every version carrying the same sets cost
-- about 6 s of "Time to load mods". A version added to a class later takes
-- the bodies and turns the previous holder's into names (coast.lua's fit bodies, the same rule).
local REP = {}
for _, key in ipairs(cfg.map_order) do
  for _, g in ipairs((cfg.geography[key] or {}).versions or {}) do
    if g.waterways then
      REP[chain_class(key, g)] = g.waterways
    end
  end
end

for _, key in ipairs(cfg.map_order) do
  local versions = (cfg.geography[key] or {}).versions or {}
  local files = FILES[key]
  for _, g in ipairs(versions) do
    local sets = g.waterways
    local rep = sets and REP[chain_class(key, g)]
    for _, s in ipairs(sets and cfg.scales.values or {}) do
      local gen = files[s]
      if not gen then
        error("waterways.lua has no generated file for " .. key .. " at scale " .. s)
      end
      local function set(kind, expression, functions)
        local name = sets[kind][s]
        if rep ~= sets then
          E[#E + 1] = {type = "noise-expression", name = name, expression = rep[kind][s]}
          return
        end
        local locals = {X = g.gx, Y = g.gy}
        local lf = {}
        for _, f in ipairs(functions) do
          lf[f] = fn(gen.functions[f])
        end
        E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals,
                     local_functions = lf}
      end
      set("ww", gen.ww, {"seg"})
      set("canals", gen.canals, {"seg"})
      set("dams", gen.dams, {"seg"})
      set("fords", gen.fords, {"box"})
    end
  end
end

-- The hook gate and the ford key hold their off values; Earth presets set the gate and point the key at
-- the map's ford set (ARCHITECTURE.md, "Stable hooks"). The canals switch's neutral bodies.
E[#E + 1] = {type = "noise-expression", name = cfg.keys.on, expression = num(H.gate_off)}
E[#E + 1] = {type = "noise-expression", name = H.fords.key, expression = H.fords.off}
E[#E + 1] = {type = "noise-expression", name = cfg.neutral.one, expression = num(H.gate_on)}
E[#E + 1] = {type = "noise-expression", name = cfg.neutral.zero, expression = num(H.gate_off)}

data:extend(E)

-- coast.lua's entry of a version with waterways: the waterway composition wrapped around the rest of
-- the version's composition (ARCHITECTURE.md, "Elevation composition", steps 5 and 6). Dams come
-- first, so a dam never closes a named waterway; both come after the rest of the version's
-- composition, so no lake of an earlier step reopens a dammed isthmus, and min() makes the carves
-- and lakes order-free. Each set is picked by name through the folded scale, so only the save's
-- scale's sets compile, and the canals switch compiles only its selected branch (S4: Tile 19,620 off
-- and 20,161 on at scale 1).
local M = {}

local function by_scale(names)
  local values = cfg.scales.values
  local text = names[values[#values]]
  for i = #values - 1, 1, -1 do
    local s = values[i]
    text = "if(" .. cfg.keys.scale .. " == " .. num(s) .. ", " .. names[s] .. ", " .. text .. ")"
  end
  return text
end

function M.composition(sets, previous)
  if not sets then
    error("a waterways composition needs the version's waterway sets")
  end
  local on = cfg.keys.canals .. " > " .. num(H.threshold)
  return "min(max(" .. previous .. ", dam), carve, canal)", {
    dam = "if(" .. on .. ", -inf, " .. by_scale(sets.dams) .. ")",
    carve = by_scale(sets.ww),
    canal = "if(" .. on .. ", " .. by_scale(sets.canals) .. ", inf)",
  }
end

return M
