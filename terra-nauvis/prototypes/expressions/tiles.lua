-- Bodies behind the tile hooks (ARCHITECTURE.md, "Stable hooks"; contract 6; S3 section 2;
-- APPROVALS 8 and 9). data-final-fixes.lua writes the hooks on the shared tiles; this file defines the
-- keys they read, each holding its off value, and the versioned bodies Earth presets point them at.
--   tn_vtile_<tile>      the 19 vanilla land tiles beside Alien Biomes: every key names one bonus body,
--                        +bonus on land where S3's temperate lean plus patch noise passes, -inf
--                        elsewhere and inside marshes, so vanilla follows temperature (D11) and marshes
--                        keep their wetland biome (APPROVALS 8)
--   tn_ab_exclude        every non-adopted Alien Biomes land tile: -inf in the temperate band outside
--                        marshes, 0 elsewhere (D11: only APPROVALS 9's tiles mix into temperate zones)
--   tn_ab_keep_v1        0 where a vanilla land tile may lie, 1 elsewhere: AB's long-listed decoratives and
--                        trees multiply by it (the list hook; config.lua tiles.scan), and it reads no fine field
--   tn_tile_mix_<n>_v1   beside Alien Biomes: the twelve shared noise fields AB's land tile scores read on
--                        their on branch, in place of a six-octave noise per tile (config.lua tiles.noise_share)
--   tn_marsh_water_mud   water-mud pools on land inside marshes, outside the start clearing
--   tn_marsh_water_shallow  water-shallow along open water inside marshes, above shallow_depth, so a
--                        river's floor (-2.2) stays player-blocking water (T5)
--   tn_marsh_grass       without Alien Biomes: grass-1 between the pools, +bonus on marsh land, 0 elsewhere
-- Marshes read the region layer's marsh weight, the shared region expression, and nothing else of the
-- layer (T16; D13). These bodies read elevation and run in the Tile program only, behind the gate, but
-- for tn_ab_keep_v1, which reads no elevation and runs in the Entity program.
local cfg = require("prototypes.config")

local V = cfg.tiles.vanilla
local X = cfg.tiles.exclude
local S = cfg.tiles.scan
local MS = cfg.tiles.marsh
local K = cfg.keys
local MARSH_W = cfg.regions.names.marsh_w

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

local function noise(P)
  return "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(P.seed1) .. ", octaves = " ..
    num(P.octaves) .. ", persistence = " .. num(P.persistence) .. ", input_scale = 1 / (" .. num(P.wavelength_px) ..
    " * " .. K.scale .. "), output_scale = 1}"
end

-- The keys, each at its off value (a world whose preset lacks one keeps the tile off).
for _, t in ipairs(V.tiles) do
  def(V.keys[t], V.off)
end
def(X.key, X.off)
def(V.mix.key, V.mix.off)
def(MS.water_mud.key, MS.water_mud.off)
def(MS.water_shallow.key, MS.water_shallow.off)
def(MS.grass.key, MS.grass.off)

-- The marsh pool noise, one named field: the pools read it and the vanilla bonus's edge reads it too.
def(MS.pool.name, noise(MS.pool))

-- The vanilla bonus: S3's lean, 1 at lean_t falling to 0 lean_span away, plus clamped patch noise,
-- gives +bonus on land below the band's top (temperate_below: the lean plus patch passes up to about
-- 73.5, inside the hot band and D11's desert bin, where AB's tiles score at most about 1.5, so the
-- bonus stops at the band's top); elsewhere in the temperate band vanilla keeps its own score (0), so
-- vanilla and the adopted AB tiles compete there by fit and AB's inland shallows stay patches, as in AB
-- alone (with -inf there, water-mud covered the band wherever the lean failed: draft render
-- pv-m2-s1-eu-1); at and above the band's top, below its bottom where the lean fails, on water and
-- inside marshes -inf. The lean still reaches below the band's bottom, on its cold side.
local function vanilla_bonus(t, marsh, extra)
  return "if(" .. marsh .. " > " .. num(V.marsh_cut) .. ", if(aux > " .. num(cfg.climate.aux.ab_cap) ..
    ", if(elevation > 0, " .. num(V.bonus) .. ", -inf), -inf), if(elevation > 0, if(" .. t .. " >= " ..
    num(X.temperate_below) .. ", -inf, if(1 - abs(" .. t .. " - " .. num(V.lean_t) .. ") / " .. num(V.lean_span) ..
    " + patch + " .. num(V.fine) .. " * " .. MS.pool.name .. (extra or "") .. " - " .. num(V.lean_cut) .. " > 0, " ..
    num(V.bonus) ..
    ", if(" .. t .. " >= " .. num(X.temperate_from) .. ", 0, -inf))), -inf))"
end
local PATCH = {patch = "clamp(" .. num(V.patch.amplitude) .. " * " .. noise(V.patch) .. ", " .. num(-V.patch.clamp) ..
  ", " .. num(V.patch.clamp) .. ")"}
def(V.body, vanilla_bonus("temperature", MARSH_W), PATCH)

-- A wild belt (config.lua climate.tile_belts) lies out of the temperate band whatever its temperature:
-- the band tests read the temperature lifted past the band's top there, so neither the vanilla bonus nor
-- the exclusion applies, and the pool noise frays the belt's edge. The list hook below opens only well inside
-- a belt, keep, since it runs in the Entity program without that noise: shut, a steppe has no tree at all, no
-- wood at a start in it.
local W = cfg.climate.tile_belts_wild
local function band_t(t, weight)
  return t .. " + " .. num(W.lift) .. " * (" .. weight .. " > " .. num(W.cut) .. ")"
end
local WILD = cfg.climate.names.belts.wild
local WILD_TILE = WILD .. " + " .. num(W.fine) .. " * " .. MS.pool.name

-- The list hook's factor: vanilla_bonus's every condition but elevation, on plain temperature, as 0 where
-- that body may not be -inf and 1 where it surely is, so a change to one belongs in the other. The bonus
-- reads the grain's frayed copy on a preset, and this runs in the Entity program, which keeps the plain
-- fields, so the band's edges and the lean widen by scan.margin to cover the fray (config.lua tiles.scan).
def(S.body, "if(" .. MS.edge .. " > " .. num(V.marsh_cut) .. ", if(aux > " .. num(cfg.climate.aux.ab_cap) ..
  ", 0, 1), if(band_t >= " .. num(X.temperate_below + S.margin) .. ", 1, if(1 - abs(temperature - " ..
  num(V.lean_t) .. ") / " .. num(V.lean_span) .. " + patch + " .. num(V.fine) .. " * " .. MS.pool.name .. " - " ..
  num(V.lean_cut - S.margin / V.lean_span) .. " > 0, 0, if(temperature >= " .. num(X.temperate_from - S.margin) ..
  ", 0, 1))))", {patch = PATCH.patch, band_t = band_t("temperature", WILD .. " - " .. num(W.keep - W.cut))})

-- The exclusion of non-adopted Alien Biomes land tiles from the temperate band.
-- Inside a marsh the tiles open up to AB's wet ground, but not to its alien palette: a dry belt's red
-- lift can carry aux past the climate's cap there (the Volga delta went purple), and vanilla's bonus
-- body takes that ground instead, since with nothing else open AB's water-mud would flood it.
local function exclusion(t, marsh)
  return "if(" .. t .. " >= " .. num(X.temperate_from) .. ", if(" .. t .. " < " .. num(X.temperate_below) ..
    ", if(" .. marsh .. " > " .. num(X.marsh_cut) .. ", if(aux > " .. num(cfg.climate.aux.ab_cap) ..
    ", -inf, 0), -inf), 0), 0)"
end
def(X.body, exclusion("temperature", MARSH_W))

-- The grain's tile copies (config.lua climate.grain): each key is its plain field, and the bonus and
-- exclusion versions read the temperature copy, so the temperate band's edge frays with the tiles. Tile
-- scores alone read them; they exist only with Alien Biomes, as the fields' grain bodies do.
if mods["alien-biomes"] then
  local GK = cfg.climate.grain.keys
  for field, key in pairs(GK) do
    def(key, field)
  end
  def(cfg.climate.grain.veg_key, "temperature")
  def(V.body_grain, vanilla_bonus("band_t", MS.edge), {patch = PATCH.patch, band_t = band_t(GK.temperature, WILD_TILE)})
  -- The stony tiles on a range: the bonus with the highland's lean.
  def(V.body_high, V.body_grain .. " + " .. cfg.ridges.names.ground)
  -- The bodies a new world's preset names: the same bonus with the lean frayed by the grain's noise.
  local LEAN_FRAY = " + " .. num(V.fray) .. " * clamp((band_t - " .. num(V.fray_t) .. ") / " .. num(V.fray_span) ..
    ", 0, 1) * noise_layer_noise(" .. num(cfg.climate.grain.layer) .. ")"
  def(V.next.grain, vanilla_bonus("band_t", MS.edge, LEAN_FRAY),
    {patch = PATCH.patch, band_t = band_t(GK.temperature, WILD_TILE)})
  def(V.next.high, V.next.grain .. " + " .. cfg.ridges.names.ground)
  def(X.body_grain, exclusion("band_t", MS.edge), {band_t = band_t(GK.temperature, WILD_TILE)})
  -- The shared fields of the tile scores' noise (config.lua tiles.noise_share), read on the on branch alone.
  local NS = cfg.tiles.noise_share
  local function shared_field(i)
    return "multioctave_noise{x = x, y = y, offset_x = " .. num(NS.offset_x) .. ", persistence = " ..
      num(NS.persistence) .. ", seed0 = map_seed, seed1 = " .. num(NS.first_seed1 + i - 1) .. ", octaves = " ..
      num(NS.octaves) .. ", input_scale = 1 / " .. num(NS.wavelength_tiles) .. ", output_scale = " ..
      num(NS.output_scale) .. "}"
  end
  for i, name in ipairs(NS.fields) do
    def(name, shared_field(i))
  end
  -- The fray, and each field's next version: the same noise text, for a preset names it in the field's place, so it
  -- cannot read the field by name.
  local FR, FN = NS.fray, NS.noise
  def(FR.body, num(FR.amount) .. " * clamp((" .. num(FR.t) .. " - " .. GK.temperature .. ") / " .. num(FR.span) ..
    ", 0, 1) * (" .. num(FN.gain) .. " * multioctave_noise{x = x, y = y, persistence = " .. num(FN.persistence) ..
    ", seed0 = map_seed, seed1 = " .. num(FN.seed1) .. ", octaves = " .. num(FN.octaves) .. ", input_scale = 1 / " ..
    num(FN.wavelength_tiles) .. ", output_scale = " .. num(FN.output_scale) .. "} + " .. num(NS.fine) ..
    " * noise_layer_noise(" .. num(cfg.climate.grain.layer) .. "))")
  for i, name in ipairs(FR.fields) do
    def(name, shared_field(i) .. " + " .. num(FR.weights[i]) .. " * " .. FR.body)
  end
end

-- The frozen tile (config.lua tiles.frozen): the key at its off value, and the body north of the snow line and on a
-- massif's snow.
local FZ = cfg.tiles.frozen
def(FZ.key, FZ.off)
local function frozen_body(name, d)
  def(name, "if(elevation > 0, if(max(" .. d .. " + " .. num(FZ.fray) ..
    " * noise_layer_noise(" .. num(cfg.climate.grain.layer) .. ") * min(1, " .. num(cfg.ridges.cold.fit_scale) ..
    " / " .. K.scale .. "), " ..
    num(FZ.cold) .. " * (" .. cfg.ridges.names.cold.gated .. " - " .. num(cfg.ridges.cold.snow_at) .. ")) > 0, " ..
    num(FZ.score) .. ", " .. FZ.off .. "), " .. FZ.off .. ")")
end
frozen_body(FZ.body, cfg.climate.north.names.d)
local N2 = cfg.climate.north2.names
frozen_body(FZ.body2, N2.d .. " - " .. num(FZ.clear_deg) .. " * " .. N2.clear)

-- Marsh pools: inside a marsh (weight above marsh_cut; normalized noise alone passes the weight-0 cut
-- on about 3 percent of tiles, draft run pv-m1-s1-eu-11), the pool noise passes a cut that falls as
-- the weight rises (cut at weight 1, cut + cut_per_weight at weight 0), on land, away from the start.
local P = MS.pool
def(MS.water_mud.body, "if(elevation > 0, if(distance > " .. num(MS.start_clear_tiles) .. ", if(" .. MARSH_W ..
  " > " .. num(V.marsh_cut) .. ", if(pool + " .. num(P.cut_per_weight) .. " * " .. MARSH_W .. " - " ..
  num(P.cut + P.cut_per_weight) .. " > 0, " .. num(MS.score) .. ", -inf), -inf), -inf), -inf)",
  {pool = P.name})
-- body2: the same pools read at a point warped in tiles (config.lua tiles.marsh.fray), so no pool edge runs straight at
-- scales 12 and 24. Only new worlds name it.
local F = MS.fray
local function warp(seed)
  return "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed) .. ", octaves = " ..
    num(F.octaves) .. ", persistence = " .. num(F.persistence) .. ", input_scale = 1 / " .. num(F.wavelength_tiles) ..
    ", output_scale = " .. num(F.amplitude_tiles) .. "}"
end
def(F.name, "multioctave_noise{x = x + " .. warp(F.seed1_x) .. ", y = y + " .. warp(F.seed1_y) ..
  ", seed0 = map_seed, seed1 = " .. num(P.seed1) .. ", octaves = " .. num(P.octaves) .. ", persistence = " ..
  num(P.persistence) .. ", input_scale = 1 / (" .. num(P.wavelength_px) .. " * " .. K.scale .. "), output_scale = 1}")
def(MS.water_mud.body2, "if(elevation > 0, if(distance > " .. num(MS.start_clear_tiles) .. ", if(" .. MARSH_W ..
  " > " .. num(V.marsh_cut) .. ", if(pool + " .. num(P.cut_per_weight) .. " * " .. MARSH_W .. " - " ..
  num(P.cut + P.cut_per_weight) .. " > 0, " .. num(MS.score) .. ", -inf), -inf), -inf), -inf)",
  {pool = F.name})
def(MS.water_shallow.body, "if(" .. MARSH_W .. " > " .. num(V.marsh_cut) .. ", if(elevation < 0, if(elevation > " ..
  num(-MS.shallow_depth) .. ", " .. num(MS.shallow_score) .. ", -inf), -inf), -inf)")
-- Without Alien Biomes: grass-1 between the pools (APPROVALS 8), +bonus on land inside marshes, 0
-- elsewhere, so grass-1 keeps its own score outside marshes and the pools (score) still beat it.
def(MS.grass.body, "if(" .. MARSH_W .. " > " .. num(V.marsh_cut) .. ", if(elevation > 0, " .. num(MS.grass.bonus) ..
  ", 0), 0)")

data:extend(E)

-- The mod's one tile: a copy of a base dirt with its own art, at half the base sheet's size.
local function deep(t)
  if type(t) ~= "table" then
    return t
  end
  local out = {}
  for k, v in pairs(t) do
    out[k] = deep(v)
  end
  return out
end

local function frozen_tile()
  local tile = deep(data.raw.tile[FZ.copy] or {})
  tile.type, tile.name, tile.order, tile.map_color = "tile", FZ.tile, FZ.order, FZ.map_color
  tile.autoplace, tile.factoriopedia_alternative = nil, nil
  tile.collision_mask = deep(FZ.collision_mask)
  for _, v in ipairs((tile.variants or {}).main or {}) do
    v.picture, v.y, v.scale = FZ.picture, v.y / FZ.art_scale, FZ.art_scale / 2
  end
  data:extend({tile})
end
frozen_tile()
