-- Waterway expressions (ARCHITECTURE.md, "Expression inventory" and "Stable hooks"; milestone waterways).
--
-- Per map and scale, four named sets from the generated files (tools/build_waterways.py): the rivers,
-- straits and turning basins (ww), the canals, the dams and the fords. Each reads only its map's geo
-- tiles in the chain of the geography version that composes them (its `waterways` record), warped and
-- bound here to the locals X, Y, XP, YP, W and B, so they live in the Tile program alone (firewall rule);
-- that version's
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

-- The natural course (config.lua natural): one warp of the geo tiles every set
-- of a version reads, so the fords stay on their rivers and the cost is a few noise evaluations per tile,
-- not per segment. Each octave is one basis noise per axis in geo tiles, anchored like the coast's detail,
-- so the same ground wanders the same way from every spawn. Rivers read X and Y, the whole warp; straits,
-- canals and dams read XP and YP, each octave at its passage share, so a passage keeps the places the
-- oracle tests. The warp fades out around the spawn, so a river stays where the river-safe starts measured
-- it. W is the rivers' low-frequency width modulation, B the fine bank noise of rivers and passages, which
-- only ever widens, so no floor moves. Every local reads constants and x, y alone.
local function natural_locals(g)
  local N = cfg.waterways.natural
  local s = cfg.keys.scale
  local function noise(seed1, wavelength)
    return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = 1 / (" ..
      num(wavelength[1]) .. " + " .. num(wavelength[2]) .. " * " .. s .. "), offset_x = " .. g.cx ..
      ", offset_y = " .. g.cy .. "}"
  end
  local locals = {}
  local rx, ry, px, py = {}, {}, {}, {}
  for i, o in ipairs(N.warp) do
    local nx, ny = "wx" .. i, "wy" .. i
    local amp = "(" .. num(o.amplitude[1]) .. " + " .. num(o.amplitude[2]) .. " * " .. s .. ")"
    locals[nx] = noise(o.seed1x, o.wavelength)
    locals[ny] = noise(o.seed1y, o.wavelength)
    rx[i], ry[i] = amp .. " * " .. nx, amp .. " * " .. ny
    px[i] = num(o.passage) .. " * " .. rx[i]
    py[i] = num(o.passage) .. " * " .. ry[i]
  end
  local F = N.spawn_fade
  locals.fade = "clamp((sqrt(x * x + y * y) - " .. num(F.inner_tiles) .. ") / " .. num(F.outer_tiles - F.inner_tiles) ..
    ", 0, 1)"
  local function warped(tile, parts)
    return tile .. " + fade * (" .. table.concat(parts, " + ") .. ")"
  end
  locals.X, locals.Y = warped(g.gx, rx), warped(g.gy, ry)
  locals.XP, locals.YP = warped(g.gx, px), warped(g.gy, py)
  locals.W = "1 + " .. num(N.width.amplitude) .. " * clamp(" .. noise(N.width.seed1, N.width.wavelength) .. ", -1, 1)"
  local half = num(N.bank.half)
  locals.B = "(" .. num(N.bank.amplitude[1]) .. " + " .. num(N.bank.amplitude[2]) .. " * " .. s .. ") * (" .. half ..
    " + " .. half .. " * clamp(" .. noise(N.bank.seed1, N.bank.wavelength) .. ", -1, 1))"
  return locals
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
        local locals = natural_locals(g)
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
-- and 20,161 on at scale 1). Beside the dams, the map's ponds (tools/build_waterways.py river_ponds): land
-- over the fit's own discs on a river's course, inline text per scale, so a carve still cuts them.
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

function M.composition(sets, previous, key, g)
  if not sets then
    error("a waterways composition needs the version's waterway sets")
  end
  local on = cfg.keys.canals .. " > " .. num(H.threshold)
  local ponds = {}
  for _, s in ipairs(cfg.scales.values) do
    ponds[s] = FILES[key][s].ponds
  end
  return "min(max(" .. previous .. ", dam, ponds), carve, canal)", {
    dam = "if(" .. on .. ", -inf, " .. by_scale(sets.dams) .. ")",
    ponds = by_scale(ponds),
    carve = by_scale(sets.ww),
    canal = "if(" .. on .. ", " .. by_scale(sets.canals) .. ", inf)",
    X = g.gx,
    Y = g.gy,
  }
end

return M
