-- Destroyed Europe (ARCHITECTURE.md, "Region layer" and milestone contract 10; milestone destroyed-europe;
-- APPROVALS 10; D12; S3 section 6; R3 7.1).
--
-- The zone reads one region-layer interface name, tn_destroyed_depth: the outline of
-- data-src/approvals/destroyed-zone.json less its keep rows (Britain, Denmark and the Carpathians), in tiles.
-- Each seed moves the outline's vertices and warps its edges harder than the shared warp, the same way on
-- every map. No region formula lives here (the static
-- regions row fails one outside regions.lua). The zone is cut by the start disc around the spawn, which the
-- spawn shift keeps at the origin on every map, so every spawn city, the zone's included, starts on normal
-- ground with normal trees (T7). Its heat climbs from a heat-1 rim to a core that mixes Alien Biomes' four
-- heat bands (R3 7.1), and the Alien Biomes temperature's next version lifts the zone to it, so AB's
-- volcanic tiles, its lava decals, volcanic rocks and the volcanic tree follow; nothing else changes
-- (APPROVALS 10: tiles only). The lift sits behind the toggle tn_destroyed, a name switch whose folded if()
-- compiles climate-tiles' first temperature alone when off (U5). Without Alien Biomes nothing here is
-- named by any preset: the toggle bakes off at the data stage and the presets keep the fallback climate
-- (FEAS-17), so the world equals the zone off. Every body is analytic in x, y, map_seed and per-save
-- numbers: firewall-clean, as the region layer is, so the Entity program, where Alien Biomes' trees read
-- temperature, may read it. Every number comes from config.lua's destroyed group (S-5).
local cfg = require("prototypes.config")

local AB = mods["alien-biomes"] ~= nil

local D = cfg.destroyed
local N = D.names
local DEPTH = cfg.regions.names.destroyed_depth
local K = cfg.keys

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The zone in tiles: positive inside, never inside the start disc (the zone's own start mask).
def(N.zone, "min(" .. DEPTH .. ", " .. D.start.distance .. " - max(" .. num(D.start.radius_tiles) ..
  ", starting_area_radius))")

-- The heat inside the zone: the rim climbs to rim + ramp, and the noise mixes the core's heat bands.
local H = D.heat
local NZ = H.noise
def(N.heat, "if(" .. N.zone .. " > 0, clamp(" .. num(H.rim) .. " + min(" .. num(H.per_tile) .. " * " .. N.zone ..
  ", " .. num(H.ramp) .. ") + heat_noise, " .. num(H.rim) .. ", " .. num(H.cap) .. "), -inf)", {
    heat_noise = num(NZ.amplitude) .. " * multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " ..
      num(NZ.seed1) .. ", octaves = " .. num(NZ.octaves) .. ", persistence = " .. num(NZ.persistence) ..
      ", input_scale = 1 / " .. num(NZ.wavelength_tiles) .. ", output_scale = 1}",
  })

-- The Alien Biomes temperature's next version (decision 21: climate-tiles' first stays defined, unchanged):
-- the zone's heat where it is hotter, with the toggle on. It reads AB's controls through the first
-- version, so it exists only with Alien Biomes, as that one does.
if AB then
  local T1 = cfg.climate.names.ab.temperature
  def(N.temperature, "if(" .. K.destroyed .. " > " .. num(D.switch_threshold) .. ", max(" .. T1 .. ", " .. N.heat ..
    "), " .. T1 .. ")")
end

data:extend(E)
