-- The Earth climate (ARCHITECTURE.md, "Expression inventory" and "Alien Biomes"; contract 6;
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

-- The maps with a geography, in order, with their extents in degrees, and the frame of the geography release
-- config.lua's layer_chain_geo names for each (config.lua frames), the chain every map-wide layer reads. Every later
-- version keeps that frame (the same city offset under names of its own), so its preset worlds read
-- the same values here through the frozen offset fallbacks.
local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  local g
  for _, v in ipairs({cfg.frames[key]}) do
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
-- would leave the engine's fast path, and multioctave_noise's offsets are no shifts (DECISIONS
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
-- A row with `since` ships after its table's first bodies: the released bodies leave it out, and only the next
-- version (names.belts2, names.lift2) sums it.
local function belt_list(X, field, belts, next)
  local out = {}
  for _, b in ipairs(belts or C.tile_belts) do
    if b[field] and overlaps(b.lat, X.lat) and overlaps(b.lon, X.lon) and (next or not b.since) then
      out[#out + 1] = b
    end
  end
  return out
end
local function belt_sum(field, next)
  return by_map(function(X)
    local parts = {}
    for _, b in ipairs(belt_list(X, field, nil, next)) do
      parts[#parts + 1] = num(b[field]) .. " * " .. belt_weight(b)
    end
    return #parts == 0 and "0" or table.concat(parts, " + ")
  end)
end
for _, field in ipairs({"t", "tv", "m", "a"}) do
  def(BELT[field], belt_sum(field), BELT_AT)
end
-- 0.3.0: the moisture belts with the rows since the release (the cold north's second line reads it). A row with
-- since and t, tv, a or wild needs that field's next body the same way, read by cold_north below.
local BELT2 = N.belts2
def(BELT2.m, belt_sum("m", true), BELT_AT)
-- 0.3.0: the largest weight of the rows that take the dry belts' desert edge (a row's edge = true), read by the cold
-- north's second line beside the dry weight.
def(BELT2.edge, by_map(function(X)
  local parts = {}
  for _, b in ipairs(C.tile_belts) do
    if b.edge and overlaps(b.lat, X.lat) and overlaps(b.lon, X.lon) then
      parts[#parts + 1] = belt_weight(b)
    end
  end
  if #parts == 0 then
    return "0"
  end
  return #parts == 1 and parts[1] or ("max(" .. table.concat(parts, ", ") .. ")")
end), BELT_AT)
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

-- The snow line (config.lua climate.north): d is degrees north of it. Worlds without Alien Biomes read it too, for the
-- mod's frozen tile.
local NF = C.north
-- climate.north2 is north with its own front, clearing and names; every other value is north's.
local NF2 = {}
for k, v in pairs(NF) do
  NF2[k] = v
end
for k, v in pairs(C.north2) do
  NF2[k] = v
end
-- climate.north3 is north2 with the North snow level's shift (config.lua climate.north_snow) and its own names.
local NS = C.north_snow
local NF3 = {}
for k, v in pairs(NF2) do
  NF3[k] = v
end
for k, v in pairs(C.north3) do
  NF3[k] = v
end
-- The level's shift in degrees, from the baked key: the nested if() folds to one constant per world. Each level's index
-- is a whole number, so the cut sits half way to the level below.
local function level_shift()
  local rows = {}
  for _, l in ipairs(NS.levels) do
    rows[#rows + 1] = l
  end
  table.sort(rows, function(a, b) return a.index < b.index end)
  local out = num(rows[1].shift_deg)
  for i = 2, #rows do
    out = "if(" .. NS.key .. " > " .. num((rows[i].index + rows[i - 1].index) / 2) .. ", " .. num(rows[i].shift_deg) ..
      ", " .. out .. ")"
  end
  return out
end
local function north_d(F)
  local front = {}
  for i = 2, #F.front do
    local a, b = F.front[i - 1], F.front[i]
    front[#front + 1] = num((b[2] - a[2]) / (b[1] - a[1])) .. " * (clamp(north_lon, " .. num(a[1]) .. ", " ..
      num(b[1]) .. ") - " .. num(a[1]) .. ")"
  end
  local shift = ""
  if F == NF3 then
    -- 0.3.1: the front lies shift degrees further south over Eurasia (the taiga's longitude gate), so d is that much
    -- greater; level low adds exactly 0.
    local TGN = F.taiga
    shift = " + (" .. level_shift() .. ") * clamp((north_lon - " .. num(TGN.lon_from) .. ") / " .. num(TGN.lon_ramp) ..
      ", 0, 1)"
  end
  def(F.names.d, N.lat .. " + " .. num(F.meander) .. " * " .. MD.name .. " + " .. num(F.wave.amplitude) ..
    " * basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(F.wave.seed1) .. ", input_scale = 1 / (" ..
    num(F.wave.wave_px) .. " * " .. K.scale .. "), output_scale = 1} - (" .. num(F.front[1][2]) .. " + " ..
    table.concat(front, " + ") .. ")" .. shift, {north_lon = N.lon})
end
north_d(NF)
north_d(NF2)
north_d(NF3)
-- The clearing round the spawn: 1 within inner_tiles of it, 0 past outer_tiles, on a distance the warp stretches by up
-- to warp of itself, so the edge is no circle.
local CL = NF2.clear
def(NF2.names.clear_warp, "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(CL.seed1) ..
  ", octaves = " .. num(CL.octaves) .. ", persistence = " .. num(CL.persistence) .. ", input_scale = 1 / " ..
  num(CL.wave_tiles) .. ", output_scale = 1}")
def(NF2.names.clear, "clamp((" .. num(CL.outer_tiles) .. " - distance * (1 + " .. num(CL.warp) .. " * " ..
  NF2.names.clear_warp .. ")) / " .. num(CL.outer_tiles - CL.inner_tiles) .. ", 0, 1)")
-- 0.3.1: the snow weight of the world's level, 1 north of its line and 0 south of it over ramp degrees, the frozen
-- tile's edge (the grain's fray, the spawn's clearing); and the rim's keep, the constant a zone may redirect.
local FZN = cfg.tiles.frozen
def(NS.names.w, "clamp((" .. NF3.names.d .. " - " .. num(FZN.clear_deg) .. " * " .. NF2.names.clear .. " + " ..
  num(NS.fray) .. " * noise_layer_noise(" .. num(C.grain.layer) .. ") * min(1, " .. num(cfg.ridges.cold.fit_scale) ..
  " / " .. K.scale .. ")) / " .. num(NS.ramp) .. ", 0, 1)")
def(NS.names.rim_keep, "1")
-- The ragged factor (config.lua climate.ragged): the grey rims' width multiplier, at the massif's snow (ridges.lua's
-- cap) and the cold north's lead. Worlds without Alien Biomes read it through the cap too.
local RG = C.ragged
def(RG.name, "clamp(" .. num(RG.mean) .. " + " .. num(RG.amplitude) .. " * multioctave_noise{x = x, y = y, " ..
  "seed0 = map_seed, seed1 = " .. num(RG.seed1) .. ", octaves = " .. num(RG.octaves) .. ", persistence = " ..
  num(RG.persistence) .. ", input_scale = 1 / " .. num(RG.wavelength_tiles) .. ", output_scale = 1}, 0, " ..
  num(RG.max) .. ")")

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
  -- The natural field stops at ab_top: Alien Biomes' wettest trees grow in a band round 0.9, so past its top
  -- they drew a ring round every moisture peak, a circle of forest about an empty middle.
  local function ab_moisture(extra, edge)
    local cut = num(cfg.tiles.vanilla.marsh_cut)
    return "clamp(max(min(" .. num(M.ab_top) .. ", " .. moisture_mean() .. " + " .. moisture_spread(false) .. extra ..
      " + " .. num(M.ab_bias) .. " * var('control:moisture:bias')), if(" .. edge .. " > " .. cut .. ", " ..
      num(M.marsh) .. " * max(" .. MARSH_W .. ", " .. cut .. "), 0)), 0, 1)"
  end
  def(N.ab.moisture, ab_moisture("", MARSH_W))
  -- The lifts (config.lua climate.lifts): a belt's sum, as the tile belts' are, on top of a released moisture:
  -- under the natural top, and no field falls for it. The jitter reaches only what trees and decoratives read.
  local function lift_sum(field, next)
    return by_map(function(X)
      local parts = {}
      for _, b in ipairs(belt_list(X, field, C.lifts, next)) do
        if not b.maps or b.maps[X.key] then
          parts[#parts + 1] = num(b[field]) .. " * " .. belt_weight(b)
        end
      end
      return #parts == 0 and "0" or table.concat(parts, " + ")
    end)
  end
  def(N.lift.m, lift_sum("m"), BELT_AT)
  def(N.lift.bare, lift_sum("bare"), BELT_AT)
  def(N.lift.j, lift_sum("j"), BELT_AT)
  def(N.lift2.m, lift_sum("m", true), BELT_AT)
  local function lifted(base, rest, lift)
    return "max(m, min(" .. num(M.ab_top) .. ", m + " .. (lift or N.lift.m) .. rest .. "))", {m = base}
  end
  -- Vanilla tiles score this field too, so scan's 0 keeps their whole lift, as it keeps them from the shake.
  local SCAN = cfg.tiles.scan.body
  local jittered, jitter_at = lifted(N.ab.moisture, " - " .. N.lift.bare .. " * " .. SCAN)
  local J = C.jitter
  def(N.lift.ab, "clamp(" .. jittered .. " + " .. N.lift.j .. " * " .. SCAN ..
    " * basis_noise{x = x, y = y, seed0 = map_seed, " ..
    "seed1 = " .. num(J.seed1) .. ", input_scale = 1 / " .. num(J.wavelength_tiles) .. ", output_scale = 1}, 0, 1)",
    jitter_at)
  -- Natural aux stays under ab_cap, below AB's alien palette, whatever the spread: it folds back at the
  -- cap instead of stopping there, because a hard stop pins every high aux to one value, and on dry land
  -- that value is dry-dirt's box alone, a flat brown plain hundreds of tiles wide. Dry temperate land
  -- lifts toward vanilla red desert, a lift that is 0 wherever the AB temperature lies outside the
  -- exclusion band, so no alien AB colour can follow it.
  local R = A.red
  local function ab_aux(extra, over)
    return "clamp(" .. num(A.ab_cap) .. " - abs(" .. num(A.base) .. " + " .. noise(A.noise, AFREQ) .. extra .. " - " ..
      num(A.ab_cap) .. ") + " .. (over or "") ..
      num(R.lift) .. " * " .. N.dry .. " * clamp((" .. N.ab.temperature .. " - " .. num(R.t_lo) .. ") / " ..
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
  -- grain: full grain there lets Alien Biomes' tan sand through as specks in the volcanic rock. A wild belt
  -- is Alien Biomes ground at a temperate core, so it takes the grain at full weight too. A range's lapse
  -- (ridges.lua) lowers both sides, so its grey and snowy crest frays like any cold ground, and the
  -- temperature the tiles read; the moisture falls off the wet grasses.
  local RN, GR = cfg.ridges.names, cfg.ridges.ground
  def(GN.field, "max(clamp((" .. num(G.cold_t) .. " - cold) / " .. num(G.cold_span) .. ", 0, 1), clamp((hot - " ..
    num(G.hot_t) .. ") / " .. num(G.hot_span) .. ", 0, 1), clamp(" .. BELT.wild ..
    ", 0, 1)) * noise_layer_noise(" .. num(G.layer) .. ") * (1 + " .. num(GR.fray) .. " * " .. RN.high_tile .. ")",
    {cold = T2 .. " - " .. RN.lapse, hot = N.ab.temperature .. " - " .. RN.lapse})
  def(GN.temperature, "max(t - " .. RN.lapse .. ", min(t, " .. num(GR.floor) .. "))",
    {t = "min(" .. T2 .. " + " .. num(G.temperature) .. " * " .. GN.field .. " + " .. BELT.t .. ", max(" .. T2 ..
       ", " .. num(T.ab.max) .. "))"})
  def(GN.veg, "if(" .. T2 .. " > " .. num(G.veg_zone_t) .. ", " .. GN.temperature .. ", min(" .. GN.temperature ..
    " + " .. BELT.tv .. ", " .. num(G.veg_cap) .. "))")
  def(GN.moisture, ab_moisture(" + " .. num(G.moisture) .. " * " .. GN.field .. " + " .. BELT.m .. " - " ..
    num(GR.moisture) .. " * " .. RN.high_tile, cfg.tiles.marsh.edge))
  def(GN.aux, ab_aux(" + " .. num(G.aux) .. " * " .. GN.field, BELT.a .. " + "))
  -- A range's lapse takes the moisture off the wet grasses, and the lift put it back: its rock and snow read as dark
  -- grass with specks of ice, and the western Alps kept under a third of their grey.
  def(N.lift.grain, lifted(GN.moisture, " * (1 - " .. RN.high_tile .. ")"))

  -- The cold north (config.lua climate.north) and the highland's cold field (ridges.cold), which a new world's preset
  -- names over the bodies above (climate.points). d is degrees north of the snow line. The fall lowers the core to the
  -- line's cap and keeps the temperature's noise, so the edge frays as any climate edge does, and it reads no zone: the
  -- zone's lift stays on top. The zone's lift also stands on the highland's cap, so no zone tile turns cold on a range.
  local RD_COLD = cfg.ridges.cold
-- 0.3.1: the lead's factor for the rim's keep (config.lua climate.north3.rim_keep), empty for the earlier lines.
  local function rim_keep_factor(F)
    if not F.rim_keep then
      return ""
    end
    return " * " .. F.rim_keep
  end
  -- 0.3.1: the Valdai square (config.lua climate.north3.valdai): inside a soft box with a warped edge the tile moisture
  -- is held at a floor above the grey dirt and the aux at a floor above the white ground, and nowhere else. The box
  -- weight and its two warped coordinates are local expressions of both bodies.
  local function valdai_locals(F)
    local V = F.valdai
    if not V then
      return {}
    end
    local function wave(seed, per)
      return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed) .. ", input_scale = 1 / " ..
        num(V.wave_tiles) .. ", output_scale = " .. num(per) .. "}"
    end
    return {v_lon = N.lon .. " + " .. wave(V.seed1_warp, V.warp_deg),
            v_lat = N.lat .. " + " .. wave(V.seed1_warp + 1, V.warp_deg),
            v_w = ramp_in("v_lon", V.lon[1], V.lon[2], V.ramp) .. " * " .. ramp_in("v_lat", V.lat[1], V.lat[2], V.ramp),
            v_floor = num(V.floor) .. " + " .. wave(V.seed1, V.amp)}
  end
  local function add_valdai(F, kept_at)
    if not F.valdai then
      return
    end
    for k, v in pairs(valdai_locals(F)) do
      kept_at[k] = v
    end
    kept_at.kept1 = kept_at.kept
    kept_at.kept = "max(kept1, v_w * v_floor)"
  end
  -- the aux's floor term: empty for the earlier lines
  local function valdai_aux(F)
    if not F.valdai then
      return ""
    end
    return ", " .. num(F.valdai.aux) .. " * v_w"
  end
  local function cold_north(F, zone_ranges)
    local NN = F.names
    local G2 = NN.grain
    -- 0.3.0 (north2, ragged): the cold field's next versions, the moisture belts and lift with their new rows
    local CG = F.ragged and RN.cold2 or RN.cold
    local BELT_M = F.ragged and BELT2.m or BELT.m
    local drop = "max(0, " .. N.core .. " - (" .. num(F.south_per_degree) .. " * max(0, -" .. NN.d .. ") - " ..
      num(F.near_per_degree) .. " * clamp(" .. NN.d .. ", 0, " .. num(F.near_degrees) .. ") - " ..
      num(F.far_per_degree) .. " * max(0, " .. NN.d .. " - " .. num(F.near_degrees) .. ")))"
    if F.taiga then
      -- 0.3.0 (north2): the taiga's floor under the core south of the line (config.lua climate.north2.taiga), a
      -- negative drop; it never exceeds the cap above, so at most one of the two terms is not 0.
      local TG2 = F.taiga
      drop = drop .. " - clamp((" .. N.lon .. " - " .. num(TG2.lon_from) .. ") / " .. num(TG2.lon_ramp) ..
        ", 0, 1) * max(0, min(" .. num(TG2.t) .. ", " .. num(TG2.per_degree) .. " * -" .. NN.d .. ") - " .. N.core ..
        ")"
    end
    def(NN.drop, drop)
    def(NN.belt, "clamp((" .. NN.d .. " + " .. num(F.belt_from) .. ") / " .. num(F.belt_ramp) .. ", 0, 1)")
    if F.ragged then
      -- 0.3.0: a rim that hugs the snow's own frayed edge: ground up to lead_t times the factor over 0 (the
      -- temperature, noise included, rises about 8 per degree south of the line), so it follows the edge where the
      -- noise pushes it, breaks where the factor is 0, and a warm patch north of the line takes a rim, not a grey blob
      -- (a degree-wide band drew grey and green blotches 500 tiles across, apart from the snow).
      -- The grain the tile temperature takes (G2.field) frays it as it frays the snow's edge: on the plain, smooth
      -- temperature the rim's outline ran along a latitude line where the factor sat at its max.
      local t_lead = NN.temperature
      if F.taiga then
        -- 0.3.0 (north2): past the taiga's floor the lead reads the floor's slope going on (config.lua
        -- climate.north2.taiga), so the rim stays on the line's edge.
        local TG2 = F.taiga
        t_lead = NN.temperature .. " + clamp((" .. N.lon .. " - " .. num(TG2.lon_from) .. ") / " .. num(TG2.lon_ramp) ..
          ", 0, 1) * max(0, " .. num(TG2.per_degree) .. " * -" .. NN.d .. " - max(" .. N.core .. ", " .. num(TG2.t) ..
          "))"
      end
      -- 0.3.1: times the rim's keep (config.lua climate.north3.rim_keep), 1 unless a zone redirects it
      def(NN.lead, "clamp((" .. num(F.lead_t) .. " * w - t - " .. num(G.temperature) .. " * " .. G2.field .. ") / " ..
        num(F.lead_t_ramp) .. ", 0, 1)" .. rim_keep_factor(F), {w = RG.name, t = t_lead})
    else
      def(NN.lead, "clamp((" .. NN.d .. " + " .. num(F.lead_degrees) .. ") / " .. num(F.lead_ramp) .. ", 0, 1)")
    end
    if F.clear then
      -- In the clearing the temperature rises to clear.t where it is colder, and only there, so a warm start keeps
      -- its own climate.
      def(NN.temperature, "t + " .. NN.clear .. " * max(0, " .. num(F.clear.t) .. " - t)",
        {t = T2 .. " - " .. NN.drop})
    else
      def(NN.temperature, T2 .. " - " .. NN.drop)
    end
    local T3 = NN.temperature
    -- 0.3.0 (north2): the taiga's weight (config.lua climate.north2.taiga): Eurasia, south of w_north degrees north of
    -- the line (none from w_ramp further), where the plain core is cold (full under m_core_full, none from m_core)
    local TW
    if F.taiga then
      local TG2 = F.taiga
      TW = "clamp((" .. N.lon .. " - " .. num(TG2.lon_from) .. ") / " .. num(TG2.lon_ramp) .. ", 0, 1) * clamp((" ..
        num(TG2.w_north + TG2.w_ramp) .. " - " .. NN.d .. ") / " .. num(TG2.w_ramp) .. ", 0, 1) * clamp((" ..
        num(TG2.m_core) .. " - " .. N.core .. ") / " .. num(TG2.m_core - TG2.m_core_full) .. ", 0, 1)"
    end
    def(G2.field, "max(clamp((" .. num(G.cold_t) .. " - cold) / " .. num(G.cold_span) .. ", 0, 1), clamp((hot - " ..
      num(G.hot_t) .. ") / " .. num(G.hot_span) .. ", 0, 1), clamp(" .. BELT.wild ..
      ", 0, 1)) * noise_layer_noise(" .. num(G.layer) .. ") * (1 + " .. num(GR.fray) .. " * " .. CG.high ..
      ") * min(1, " .. num(RD_COLD.fit_scale) .. " / " .. K.scale .. ")",
      {cold = "min(" .. T3 .. ", " .. CG.cap .. ")", hot = "min(" .. N.ab.temperature .. ", " .. CG.cap .. ")"})
    -- The cap takes a share of the grain: whole, it reaches 18 at full highland, and on a slope of a quarter degree a
    -- tile that scatters specks 75 tiles past the massif's edge.
    local capped = "min(t, " .. CG.cap .. " + " .. T2 .. " - " .. N.ab.temperature .. " + " ..
      num(G.temperature * RD_COLD.cap_grain) .. " * " .. G2.field .. ")"
    local t_at = {t = "min(" .. T3 .. " + " .. num(G.temperature) .. " * " .. G2.field .. " + " .. BELT.t ..
      " * (1 - " .. NN.belt .. "), max(" .. T3 .. ", " .. num(T.ab.max) .. "))"}
    if zone_ranges then
      -- Inside the zone's lift a range keeps the zone's ground (config.lua destroyed.range_heat): the cap stays off it.
      capped = "max(" .. capped .. ", if(" .. T2 .. " > " .. num(T.ab.max) .. ", min(t, " ..
        num(cfg.destroyed.range_heat) .. "), -inf))"
      -- 0.3.0: the zone's fray (config.lua climate.grain.zone_fray), inside the lift alone and within its rim and cap,
      -- and the spawn's cooler cap (destroyed.barrier.start), so the fray adds no heat 3 near the start
      local DH, BS = cfg.destroyed.heat, cfg.destroyed.barrier.start
      t_at.c = capped
      t_at.top = "min(" .. num(DH.cap) .. ", " .. num(BS.cap) .. " + " .. num(BS.per_tile) .. " * max(0, " ..
        cfg.destroyed.start.distance .. " - " .. num(BS.cool_tiles) .. "))"
      capped = "if(" .. T2 .. " > " .. num(T.ab.max) .. ", clamp(c + " .. num(G.zone_fray) .. " * noise_layer_noise(" ..
        num(G.layer) .. "), min(c, " .. num(DH.rim) .. "), max(c, top)), c)"
    end
    def(G2.temperature, capped, t_at)
    -- 0.3.0 (north2): in the taiga the tundra belts' cooling of the grasses (tundra_bare_old tv -12) is undone, or the
    -- grey took a degree and more south of the line
    local TV = BELT.tv
    if TW then
      TV = "(" .. BELT.tv .. " + " .. TW .. " * max(0, -" .. BELT.tv .. "))"
    end
    def(G2.veg, "if(" .. T3 .. " > " .. num(G.veg_zone_t) .. ", " .. G2.temperature .. ", min(" .. G2.temperature ..
      " + " .. TV .. ", " .. num(G.veg_cap) .. "))")
    -- 0.3.0 (north2, ragged): a massif's dry flank is its rim and snow alone, where the cap cools the ground under
    -- top_t (ridges.cold): over the whole reach, the moisture's fall and the lift's stop drew a wide grey or dirt ring.
    -- Where the ragged factor is under grey_w the rim thins out to none, the snow's frayed edge included, so the snow
    -- meets the ground beside it; deep in the snow (the cap under -snow_deep) it holds whatever the factor.
    local HIGH = CG.high
    if F.ragged then
      HIGH = "max(clamp((" .. num(-RD_COLD.snow_deep) .. " - " .. CG.cap .. ") / " .. num(RD_COLD.snow_deep) ..
        ", 0, 1), clamp((" .. num(RD_COLD.top_t) .. " - " .. CG.cap .. ") / " .. num(RD_COLD.top_t - RD_COLD.grey_t) ..
        ", 0, 1) * min(1, " .. C.ragged.name .. " / " .. num(RD_COLD.grey_w) .. "))"
    end
    def(G2.moisture, ab_moisture(" + " .. num(G.moisture) .. " * " .. G2.field .. " + " .. BELT_M .. " - " ..
      num(GR.moisture) .. " * " .. HIGH, cfg.tiles.marsh.edge))
    -- Alien Biomes' white ground sits under aux 0.3, so where aux dips across that line the grey ground of the
    -- wasteland and of a massif's flanks takes small pale islands: the floor keeps those two to the one grey family.
    local GREY = "max(" .. NN.lead .. ", clamp(" .. num(F.aux_high) .. " * " .. CG.high .. ", 0, 1))"
    if F.ragged then
      GREY = "max(" .. NN.lead .. ", " .. HIGH .. ")"
    end
    -- 0.3.0 (north2): in the taiga the tundra's pale pull (tundra_pale_old a -0.2) is undone too, or Alien Biomes'
    -- white dirt took the moisture lows
    local BA = BELT.a
    if TW then
      BA = "(" .. BELT.a .. " + " .. TW .. " * max(0, -" .. BELT.a .. "))"
    end
    local aux_at = valdai_locals(F)
    aux_at.a = ab_aux(" + " .. num(G.aux) .. " * " .. G2.field, BA .. " + ")
    def(G2.aux, "max(a, " .. num(F.aux_floor) .. " * " .. GREY .. valdai_aux(F) .. ")", aux_at)
    local kept, kept_at = lifted(G2.moisture, " * (1 - " .. HIGH .. ")", F.ragged and N.lift2.m or nil)
    kept_at.kept = kept
    if F.taiga then
      -- 0.3.0 (north2): the taiga's moisture lift (config.lua climate.north2.taiga.m), under its own top
      local TG2 = F.taiga
      kept_at.kept0 = kept
      kept_at.kept = "max(kept0, min(" .. num(TG2.m_top) .. ", kept0 + " .. num(TG2.m) .. " * " .. TW .. " * (1 - " ..
        HIGH .. ")))"
    end
    add_valdai(F, kept_at)
    -- 0.3.0 (north2, ragged): the desert edge (config.lua climate.desert_edge). In the dry belts the tile moisture is
    -- pulled away from the dirt band's middle by a gain over the ragged factor, so the dry dirt between sand and grass
    -- narrows by that gain, breaks where the factor is 0 and widens where it is high; the wet side rises no further
    -- than into the grass. Before the grey's cap, so a cold rim keeps its grey dirt.
    local K2 = "kept"
    if F.ragged then
      local DE2 = C.desert_edge
      kept_at.dz = "max(clamp(" .. num(DE2.dry_gain) .. " * (" .. N.dry .. " - " .. num(DE2.dry_from) .. "), 0, 1), " ..
        BELT2.edge .. ")"
      kept_at.dk = "min(" .. num(DE2.max) .. ", " .. num(DE2.gain) .. " / max(" .. num(DE2.floor) .. ", " ..
        RG.name .. "))"
      kept_at.sharp = "kept + dz * (clamp(" .. num(DE2.mid) .. " + (kept - " .. num(DE2.mid) .. ") * dk, min(kept, " ..
        num(DE2.bottom) .. "), max(kept, " .. num(DE2.top) .. ")) - kept)"
      K2 = "sharp"
    end
    -- The same ceiling on a massif's flanks: wet moisture there drew specks of Alien Biomes' wet dirt in the dark
    -- grass.
    if F.clear then
      -- A cold spawn's clearing would be Alien Biomes' grey sand, as slow as its snow: where the clearing warmed the
      -- ground, the tile moisture rises to clear.m, grey dirt's band. A warm start keeps its own.
      kept_at.lifted = K2 .. " - " .. GREY .. " * max(0, " .. K2 .. " - " .. num(F.lead_top) .. ")"
      kept_at.c = NN.clear
      def(NN.moisture, "max(lifted, " .. num(F.clear.m) .. " * clamp(c + " .. num(F.clear.m_fray) .. " * " ..
        NN.clear_warp .. " * c * (1 - c), 0, 1) * clamp((" .. num(F.clear.t) .. " - " .. T2 .. " + " .. NN.drop ..
        ") / " .. num(F.clear.m_span) .. ", 0, 1))", kept_at)
    else
      def(NN.moisture, K2 .. " - " .. GREY .. " * max(0, " .. K2 .. " - " .. num(F.lead_top) .. ")", kept_at)
    end
  end
  cold_north(NF)
  cold_north(NF2, true)
  cold_north(NF3, true)
  -- 0.3.1: the Valdai floor on the properties Alien Biomes' tiles and trees read (config.lua climate.north3.valdai),
  -- over the released bodies it reads by name: where the box weight is 0 they are the released bodies exactly.
  local VD = NF3.valdai
  local vm, va = valdai_locals(NF3), valdai_locals(NF3)
  vm.m, va.a = N.lift.ab, N.ab.aux
  def(VD.names.moisture, "max(m, v_w * v_floor)", vm)
  def(VD.names.aux, "max(a, " .. num(VD.aux) .. " * v_w)", va)
end

data:extend(E)
