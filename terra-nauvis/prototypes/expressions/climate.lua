-- The Earth climate (ARCHITECTURE.md, "Expression inventory" and "Alien Biomes"; milestone climate-tiles;
-- S3 sections 1 to 4; D9).
--
-- Temperature, moisture and aux after EarthMaps' layout: latitude on each map's own chain (frozen in
-- the far north, cold from about 54 N, temperate, hot toward the tropics), Eurasia's continental cold
-- (D9: Russia is cold), and the dry belts EarthMaps paints as sand (config.lua climate.dry_belts, from
-- the measured sand share), which run hot and dry. Each Earth preset redirects temperature, moisture
-- and aux to the Alien Biomes variant when alien-biomes is loaded, else to the fallback (presets.lua):
--   Alien Biomes  temperature in AB units with AB's hot and cold shift and frequency, moisture and aux
--                 with AB's 2.2 times bias (R3 1.1); the marsh weight lifts moisture into the wet band;
--                 dry temperate land lifts aux toward vanilla red desert, inside the band where the
--                 exclusion hook keeps every non-adopted AB tile out (D11; tiles.lua)
--   fallback      temperature on the vanilla scale for vanilla trees and decoratives, the boreal belt
--                 lifted into the vanilla cold trees' band up to a treeline; the moisture mean capped by
--                 the warm-side cold, then raised again in the boreal belt (taiga grass and trees) and
--                 held at mid moisture above the treeline, with a floor that keeps sand and light dirt
--                 out of the north (no snow tile in the base game: the tundra and arctic read as the
--                 dark dirt-5 to dirt-7 and grass-4); the aux mean pulled low in the cold, under grass-2,
--                 beach sand and vanilla red desert, and down in the dry belts (vanilla sand)
-- Every field is the Earth mean plus a seeded spread (config.lua climate: spread), so each real climate
-- zone is a patchwork of several tiles that changes with the seed; the caps and pulls move the mean
-- and bound the result, never the spread alone.
-- The latitude, longitude and dry weight fold on the per-save map number (U5: one map's branch
-- compiles), so these bodies are preset-only, like tn_map, which has no prototype. Nothing here reads
-- elevation or any firewall name: Alien Biomes' trees and the vanilla trees read the climate in the
-- Entity program (ARCHITECTURE.md, "Programs and the firewall"). The marsh weight is the region layer's
-- interface name (S10 design (d)); the region formula lives in regions.lua alone.
-- Bodies that read Alien Biomes' hot and cold controls exist only with Alien Biomes (R3 6).
local cfg = require("prototypes.config")

local AB = mods["alien-biomes"] ~= nil

local K = cfg.keys
local C = cfg.climate
local N = C.names
local T = C.temperature
local M = C.moisture
local A = C.aux
local PPD = cfg.coordinates.px_per_degree
local MARSH_W = cfg.regions.names.marsh_w

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The maps with a geography, in order, with their extents in degrees, and the geography version
-- config.lua's layer_chain_geo names for each, the chain every map-wide layer reads. Every later
-- version keeps that frame (the same city offset under names of its own), so its preset worlds read
-- the same values here through the frozen offset fallbacks.
local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  local g
  for _, v in ipairs((cfg.geography[key] or {}).versions or {}) do
    if v.geo_id == cfg.layer_chain_geo[key] then
      g = v
    end
  end
  if cfg.layer_chain_geo[key] and not g then
    error("config.lua layer_chain_geo names geography " .. tostring(cfg.layer_chain_geo[key]) .. ", which " .. key ..
      " does not have")
  end
  if g then
    local m = cfg.maps[key]
    MAPS[#MAPS + 1] = {key = key, id = m.id, g = g, m = m,
                       lon = {m.lon_left_edge, m.lon_left_edge + m.width_px / PPD},
                       lat = {m.lat_top_edge - m.height_px / PPD, m.lat_top_edge}}
  end
end

-- One text per map, folded on the per-save map number.
local function by_map(fn)
  local out = fn(MAPS[#MAPS])
  for i = #MAPS - 1, 1, -1 do
    out = "if(" .. K.map .. " == " .. num(MAPS[i].id) .. ", " .. fn(MAPS[i]) .. ", " .. out .. ")"
  end
  return out
end

-- The city offset of the world's map folded into one constant added to each noise's seed1, so each
-- spawn city gets a climate texture of its own: the world shifts to put the city at the origin, so a
-- noise of plain x and y would repeat around every city of a seed. A seed folds at compile time; x + cx
-- would leave the engine's fast path, and multioctave_noise's offsets are no shifts (design notes
-- 2026-10-30 11:10).
local SH = C.city_shift
def(N.shift, by_map(function(X)
  return "(floor(" .. X.g.cx .. ") % " .. num(SH.modulus) .. ") * " .. num(SH.stride) .. " + floor(" .. X.g.cy ..
    ") % " .. num(SH.modulus)
end))

-- A noise of wavelength_px reference pixels, its input scale times `freq` (a slider's frequency or 1).
local function noise(P, freq)
  local scale = "1 / (" .. num(P.wavelength_px) .. " * " .. K.scale .. ")"
  if freq then
    scale = "(" .. freq .. ") / (" .. num(P.wavelength_px) .. " * " .. K.scale .. ")"
  end
  return num(P.amplitude) .. " * multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(P.seed1) ..
    " + " .. N.shift .. ", octaves = " .. num(P.octaves) .. ", persistence = " .. num(P.persistence) ..
    ", input_scale = " .. scale .. ", output_scale = 1}"
end

local function ramp_in(v, lo, hi, r)
  return "clamp(min(" .. v .. " - " .. num(lo) .. ", " .. num(hi) .. " - " .. v .. ") / " .. num(r) .. ", 0, 1)"
end

local function overlaps(a, b)
  return a[1] < b[2] and b[1] < a[2]
end

-- Latitude and longitude in degrees at the tile's reference pixel; the latitude meanders by one basis
-- noise octave, so climate fronts wander instead of running along rows.
local MD = C.meander
def(MD.name, "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(MD.seed1) .. ", input_scale = 1 / (" ..
  num(MD.wavelength_px) .. " * " .. K.scale .. "), output_scale = 1}")
def(N.lat, by_map(function(X)
  return num(X.m.lat_top_edge) .. " - (" .. X.g.v .. " + " .. num(C.centre_px) .. ") / " .. num(PPD)
end) .. " + " .. num(MD.degrees) .. " * " .. MD.name)
def(N.lon, by_map(function(X)
  return num(X.m.lon_left_edge) .. " + (" .. X.g.u .. " + " .. num(C.centre_px) .. ") / " .. num(PPD)
end))

-- The dry weight: the largest weight of the map's dry belts.
def(N.dry, by_map(function(X)
  local parts = {}
  for _, b in ipairs(C.dry_belts) do
    if overlaps(b.lat, X.lat) and overlaps(b.lon, X.lon) then
      parts[#parts + 1] = ramp_in("dry_lat", b.lat[1], b.lat[2], b.ramp[1]) .. " * " ..
        ramp_in("dry_lon", b.lon[1], b.lon[2], b.ramp[2])
    end
  end
  if #parts == 0 then
    return "0"
  end
  if #parts == 1 then
    return parts[1]
  end
  return "max(" .. table.concat(parts, ", ") .. ")"
end), {dry_lat = N.lat .. " + " .. num(MD.dry_lat) .. " * " .. MD.name,
       dry_lon = N.lon .. " + " .. num(MD.dry_lon) .. " * " .. MD.name})

-- The tile belts (config.lua climate.tile_belts): each field's sum over the belts that reach the map, on
-- the meandering latitude and longitude, so a belt's edge wanders as a dry belt's does, by less: at the dry
-- belts' reach a narrow belt broke off in ovals.
local BELT = N.belts
local BW = C.tile_belts_wander
local BELT_AT = {belt_lat = N.lat .. " + " .. num(BW.lat) .. " * " .. MD.name,
                 belt_lon = N.lon .. " + " .. num(BW.lon) .. " * " .. MD.name}
local function belt_weight(b)
  return ramp_in("belt_lat", b.lat[1], b.lat[2], b.ramp[1]) .. " * " ..
    ramp_in("belt_lon", b.lon[1], b.lon[2], b.ramp[2])
end
local function belt_list(X, field)
  local out = {}
  for _, b in ipairs(C.tile_belts) do
    if b[field] and overlaps(b.lat, X.lat) and overlaps(b.lon, X.lon) then
      out[#out + 1] = b
    end
  end
  return out
end
for _, field in ipairs({"t", "tv", "m", "a"}) do
  def(BELT[field], by_map(function(X)
    local parts = {}
    for _, b in ipairs(belt_list(X, field)) do
      parts[#parts + 1] = num(b[field]) .. " * " .. belt_weight(b)
    end
    return #parts == 0 and "0" or table.concat(parts, " + ")
  end), BELT_AT)
end
def(BELT.wild, by_map(function(X)
  local parts = {}
  for _, b in ipairs(belt_list(X, "wild")) do
    parts[#parts + 1] = belt_weight(b)
  end
  if #parts == 0 then
    return "0"
  end
  return #parts == 1 and parts[1] or ("max(" .. table.concat(parts, ", ") .. ")")
end), BELT_AT)

-- The temperature core in Alien Biomes units, before noise and sliders.
local CT = T.continental
def(N.core, "clamp(" .. num(T.ref_t) .. " + " .. num(T.per_degree) .. " * (" .. num(T.ref_lat) .. " - abs(" ..
  N.lat .. ")), " .. num(T.min) .. ", " .. num(T.cap) .. ") - " .. num(CT.t) .. " * clamp((" .. N.lon .. " - " ..
  num(CT.lon_start) .. ") / " .. num(CT.lon_span) .. ", 0, 1) * clamp((" .. N.lat .. " - " .. num(CT.lat_start) ..
  ") / " .. num(CT.lat_span) .. ", 0, 1) + " .. num(T.desert_heat) .. " * " .. N.dry)

-- The Earth moisture mean before the spread, caps and biases: the base, wetter at the equator, dry in
-- the dry belts.
local function moisture_mean()
  return num(M.base) .. " + " .. num(M.equatorial) .. " * clamp((" .. num(M.equatorial_lat + M.equatorial_ramp) ..
    " - abs(" .. N.lat .. ")) / " .. num(M.equatorial_ramp) .. ", 0, 1) - " .. num(M.dry) .. " * " .. N.dry
end

-- The coldness, 0 at core cold.t and warmer, 1 at cold.t - cold.span and colder.
local COLD = "clamp((" .. num(C.cold.t) .. " - " .. N.core .. ") / " .. num(C.cold.span) .. ", 0, 1)"

-- The spread: the seeded patchwork inside every climate zone, added after the caps and pulls so they
-- never flatten it (config.lua climate: spread). The moisture spread shrinks in the dry belts (and on
-- the fallback in the cold), so deserts stay dry and the far north dry and dead ground.
local MFREQ = "var('control:moisture:frequency')"
local AFREQ = "var('control:aux:frequency')"
local function moisture_spread(cold)
  local w = "1 - " .. num(M.spread.dry) .. " * " .. N.dry
  if cold then
    w = w .. " - " .. num(M.spread.cold) .. " * cold"
  end
  return "(" .. w .. ") * " .. noise(M.noise, MFREQ)
end

-- The fallback, with no Alien Biomes control: the vanilla scale for temperature, the cold cap on the
-- moisture mean, the cold and dry pulls on the aux mean and the cold cap on aux (S3 section 4).
local FB = T.fallback
local TG = FB.taiga
def(N.fallback.temperature, "clamp(" .. num(FB.scale) .. " * (max(c, min(" .. num(TG.plateau) .. ", " ..
  num(TG.plateau) .. " + " .. num(TG.slope) .. " * (c - " .. num(TG.treeline_t) .. "))) + " .. noise(T.noise) ..
  "), " .. num(FB.min) .. ", " .. num(FB.max) .. ")",
  {c = N.core})
local MF = M.fallback
local NO = MF.north
local function fall(from, full)
  return "clamp((" .. num(from) .. " - " .. N.core .. ") / " .. num(from - full) .. ", 0, 1)"
end
def(N.fallback.moisture, "clamp(max(min(mean, max(cap, wet)) + " .. moisture_spread(true) .. ", low) + " ..
  num(MF.bias) .. " * var('control:moisture:bias'), 0, 1)",
  {mean = moisture_mean(), cold = COLD,
   cap = num(MF.cap_base) .. " + " .. num(MF.cap_per_t) .. " * clamp(" .. N.core .. " / " .. num(MF.cap_t) ..
     ", 0, 1)",
   wet = num(NO.wet) .. " * " .. fall(NO.wet_from_t, NO.wet_full_t) .. " - " .. num(NO.wet - NO.frozen) .. " * " ..
     fall(NO.frozen_from_t, NO.frozen_full_t),
   low = num(NO.floor) .. " * " .. fall(NO.floor_from_t, NO.floor_full_t)})
local AF = A.fallback
def(N.fallback.aux, "clamp(min(" .. num(A.base) .. " + (" .. num(AF.cold_aux) .. " - " .. num(A.base) ..
  ") * cold - " .. num(AF.dry_pull) .. " * " .. N.dry .. " + " .. noise(A.noise, AFREQ) .. ", 1 - " ..
  num(1 - AF.cold_cap) .. " * cold) + " .. num(AF.bias) .. " * var('control:aux:bias'), 0, 1)",
  {cold = "clamp((" .. num(C.cold.t) .. " - " .. N.core .. ") / " .. num(AF.cold_span) .. ", 0, 1)"})

if AB then
  -- Alien Biomes' hot and cold sliders: their size shifts the temperature as AB's own average does, their
  -- mean frequency scales the noise (R3 1.1 and 1.3; S3 section 3).
  local TA = T.ab
  def(N.ab.temperature, "clamp(" .. N.core .. " + " .. noise(T.noise, "(var('control:hot:frequency') + " ..
    "var('control:cold:frequency')) / 2") .. " + " .. num(TA.shift_per_unit) .. " * (var('control:hot:size') - " ..
    "var('control:cold:size')), " .. num(TA.min) .. ", " .. num(TA.max) .. ")")
  -- The marsh's lift is a step at the marsh cut, not a ramp up the weight: rising through the vanilla
  -- tiles' moisture bands, the ramp drew them as a dark rim of one width round every marsh (a tide line).
  -- It starts above Alien Biomes' mid band wherever the frayed edge passes, or its beige sand rims the pools.
  local function ab_moisture(extra, edge)
    local cut = num(cfg.tiles.vanilla.marsh_cut)
    return "clamp(max(" .. moisture_mean() .. " + " .. moisture_spread(false) .. extra .. " + " ..
      num(M.ab_bias) .. " * var('control:moisture:bias'), if(" .. edge .. " > " .. cut .. ", " .. num(M.marsh) ..
      " * max(" .. MARSH_W .. ", " .. cut .. "), 0)), 0, 1)"
  end
  def(N.ab.moisture, ab_moisture("", MARSH_W))
  -- Natural aux stays under ab_cap, below AB's alien palette, whatever the spread; dry temperate land
  -- lifts toward vanilla red desert, a lift that is 0 wherever the AB temperature lies outside the
  -- exclusion band, so no alien AB colour can follow it.
  local R = A.red
  local function ab_aux(extra, over)
    return "clamp(min(" .. num(A.base) .. " + " .. noise(A.noise, AFREQ) .. extra .. ", " .. num(A.ab_cap) .. ") + " ..
      (over or "") .. num(R.lift) .. " * " .. N.dry .. " * clamp((" .. N.ab.temperature .. " - " .. num(R.t_lo) ..
      ") / " ..
      num(R.ramp) .. ", 0, 1) * clamp((" .. num(R.t_hi) .. " - " .. N.ab.temperature .. ") / " .. num(R.ramp) ..
      ", 0, 1) + " .. num(A.ab_bias) .. " * var('control:aux:bias'), 0, 1)"
  end
  def(N.ab.aux, ab_aux(""))

  -- The grain's bodies (config.lua climate.grain), which tile scores alone read. Temperature adds to
  -- the zone's lift, the version presets name, and stops at the natural ceiling unless the zone is
  -- already over it, so no grain reaches Alien Biomes' volcanic band outside the zone; aux adds under
  -- the cap, so no grain reaches its alien palette.
  local G, GN = C.grain, N.grain
  local T2 = cfg.destroyed.names.temperature
  -- The cold side reads the zone's lift and the hot side the unlifted temperature, so the zone takes no
  -- grain: full grain there lets Alien Biomes' tan sand through as specks in the volcanic rock.
  def(GN.field, "max(clamp((" .. num(G.cold_t) .. " - " .. T2 .. ") / " .. num(G.cold_span) .. ", 0, 1), clamp((" ..
    N.ab.temperature .. " - " .. num(G.hot_t) .. ") / " .. num(G.hot_span) .. ", 0, 1)) * noise_layer_noise(" ..
    num(G.layer) .. ")")
  def(GN.temperature, "min(" .. T2 .. " + " .. num(G.temperature) .. " * " .. GN.field .. ", max(" .. T2 .. ", " ..
    num(T.ab.max) .. "))")
  def(GN.moisture, ab_moisture(" + " .. num(G.moisture) .. " * " .. GN.field, cfg.tiles.marsh.edge))
  def(GN.aux, ab_aux(" + " .. num(G.aux) .. " * " .. GN.field))
end

data:extend(E)
