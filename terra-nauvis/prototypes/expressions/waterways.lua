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

local E = {}
-- The sets of the geography version that composes them, bound to its chain, for every offered scale.
for _, key in ipairs(cfg.map_order) do
  local versions = (cfg.geography[key] or {}).versions or {}
  local files = FILES[key]
  for _, g in ipairs(versions) do
    local sets = g.waterways
    for _, s in ipairs(sets and cfg.scales.values or {}) do
      local gen = files[s]
      if not gen then
        error("waterways.lua has no generated file for " .. key .. " at scale " .. s)
      end
      local function set(kind, expression, functions)
        local name = sets[kind][s]
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
