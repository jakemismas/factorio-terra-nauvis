-- Hotspots, the richness ramp, the random offshore-oil sea mask and the offshore field stamps
-- (ARCHITECTURE.md milestone contract 9; S6 A5 with a shared blob and Q5; APPROVALS 2 and 3; decisions 8
-- and 16; milestone resources-enemies).
--
-- Every row of prototypes/tables/hotspots.lua is a hotspot whose disc is the region layer's row of
-- the same id, jittered per seed there. At scale s its footprint radius is
--   R = min(max(r * s, floor_tiles), cap * s) tiles
-- (APPROVALS 2's floor at small scales, capped at r + 50 km), read through the row's depth in the
-- region layer, so the footprint is the disc's roughened distance under R. Per resource, one
-- spot_noise with its own seed1 places the spots (S6 A5): only land candidates inside a row's start
-- disc (core_share of R, at most the disc of max_spots candidates) carry quantity, and a spot reaches
-- at most the rest of R, so ore never leaves the footprint without a per-tile mask. Each row's amount
-- is strength times vanilla's regular patch amount at the candidate's distance (quantity and richness
-- factor) times the ramp, spread over the start disc's expected candidates, and the region's target is
-- the sum of its candidates' quantities, so the realised amount is scaled by the land share the gate
-- passes (decision 16; water share for an offshore field), with land from tn_land_coarse alone (decision
-- 8), and rows sharing a region never draw on each other's target. Frequency is never read, so the
-- hotspot bodies are bit-identical under the frequency slider; size scales the quantity and size
-- none removes the hotspot; richness scales it exactly (S6 Q2). The per-map rows fold on tn_map (a
-- preset-only number: the wrappers that read these bodies exist on preset worlds only).
--
-- Each map's offshore field stamp is stamp_elevation inside every offshore row's footprint grown by
-- cover_px, else 0, on the map's own chain (Tile only, a firewall body); the map's newer elevation
-- entry reads it through the map-qualified key tn_fields_<map>, a Map type fallback (coast.lua).
-- data-final-fixes.lua wraps the pack's live ore, enemy and offshore-oil autoplace around these.
-- Every name and number comes from config.lua (S-5).
local cfg = require("prototypes.config")
local T = require("prototypes.tables.hotspots")

local HC = cfg.hotspots
local RS = cfg.resources
local FD = cfg.fields
local K = cfg.keys
local S = K.scale
local SUFFIX = cfg.regions.names.suffix
local DEPTH = cfg.regions.names.row.depth
local HU = cfg.regions.names.row.hu
local HV = cfg.regions.names.row.hv

local function num(v)
  return string.format(cfg.number_format, v)
end

-- name minus a constant, spelled without a double sign
local function minus(name, c)
  if c == 0 then
    return name
  end
  if c < 0 then
    return name .. " + " .. num(-c)
  end
  return name .. " - " .. num(c)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- Each map with the chain every map-wide layer reads (config.lua layer_chain_geo), the one the region
-- layer's hotspot discs sit on: a later geography version keeps its frame, so the stamps never move.
local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  local g
  for _, v in ipairs((cfg.geography[key] or {}).versions or {}) do
    if v.geo_id == cfg.layer_chain_geo[key] then
      g = v
    end
  end
  if cfg.geography[key] and not g then
    error("config.lua layer_chain_geo names no geography version of " .. key .. " for the offshore stamps")
  end
  if g then
    MAPS[#MAPS + 1] = {key = key, id = cfg.maps[key].id, g = g}
  end
end

-- One text per map, folded on the per-save map number; a text the same on every map needs no fold.
local function by_map(fn)
  local texts, same = {}, true
  for i, M in ipairs(MAPS) do
    texts[i] = fn(M)
    same = same and texts[i] == texts[1]
  end
  if same then
    return texts[1]
  end
  local out = texts[#texts]
  for i = #texts - 1, 1, -1 do
    out = "if(" .. K.map .. " == " .. num(MAPS[i].id) .. ", " .. texts[i] .. ", " .. out .. ")"
  end
  return out
end

local function rows_of(map_key, resource)
  local out = {}
  for _, r in ipairs(T.rows) do
    if resource == nil or r.resource == resource then
      for _, mk in ipairs(r.maps) do
        if mk == map_key then
          out[#out + 1] = r
          break
        end
      end
    end
  end
  return out
end

local function sum(parts, empty)
  if #parts == 0 then
    return empty
  end
  return "(" .. table.concat(parts, " + ") .. ")"
end

-- A row's footprint radius R in tiles, folding per save (the scale is a per-save number).
local function footprint(r)
  return "min(max(" .. num(r.radius_px) .. " * " .. S .. ", " .. num(HC.floor_tiles) .. "), " .. num(r.cap_px) ..
    " * " .. S .. ")"
end

-- The richness ramp (D23; S6 Q5): 1 inside `from` tiles, rising to 1 + gain at from + span, flat after.
local RP = RS.ramp
def(RP.name, "1 + " .. num(RP.gain) .. " * clamp((distance - " .. num(RP.from) .. ") / " .. num(RP.span) .. ", 0, 1)")

-- The random offshore-oil sea mask (FEAS-07; design notes, resources-enemies): 1 where the coarse land
-- field reads open sea past the threshold, which leaves inland rivers, canals, lakes and marshes out.
def(RS.sea.name, K.land_coarse .. " < " .. num(-RS.sea.threshold_px))

-- The shared blob texture (S6 A5c42s).
local B = HC.blob
local blob = {}
for _, o in ipairs(B.octaves) do
  blob[#blob + 1] = "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(B.seed1) .. ", input_scale = " ..
    num(o.input_scale) .. ", output_scale = " .. num(o.output_scale) .. "}"
end
def(B.name, table.concat(blob, " + "))

-- Vanilla's regular patch amount per unit of the resource's target at distance d: the fade-in, the
-- double-density term and the richness factor (core/prototypes/noise-functions.lua:205-207,
-- 264-280; core/lualib/resource-autoplace.lua:115-120), times the ramp.
local TG = HC.target
local distance_factor = "clamp((distance - " .. num(TG.fade_from) .. ") / " .. num(TG.fade_span) .. ", 0, 1) * (1 + " ..
  "clamp((distance - " .. num(TG.double_from) .. ") / " .. num(TG.double_span) .. ", 0, 1)) * max((distance + " ..
  num(TG.rich_offset) .. ") / " .. num(TG.rich_span) .. ", 1) * " .. RP.name

local SP = HC.spot
local function control(resource, what)
  return "var('control:" .. resource .. ":" .. what .. "')"
end

-- Per save: tiles per candidate, and a row's start disc, where its spots start: core_share of its
-- footprint, at most the disc that holds max_spots candidates.
local CANDIDATES = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", " .. num(SP.candidates) .. ", " ..
  num(SP.candidates_fine) .. ")"
local PER_CANDIDATE = "(" .. num(SP.region_size * SP.region_size) .. " / " .. CANDIDATES .. ")"
local function start_radius(r)
  return "min(" .. num(HC.core_share) .. " * " .. footprint(r) .. ", sqrt(" .. num(SP.max_spots) .. " * " ..
    PER_CANDIDATE .. " / pi))"
end

-- One resource's spot noise on one map over its rows there, as local expressions of the resource's
-- body: the quantity "q<i>" and the spot "s<i>" for the map's index i. A map that adopts none of the
-- resource's rows has none; the body's spot folds to the basement there.
--
-- Every land candidate inside a row's start disc carries the row's amount over the disc's expected
-- candidates, and the region's target is exactly the sum of those quantities (the density is a
-- candidate's quantity over the tiles per candidate), so every one of them is placed and rows of a
-- resource that share a region never draw on each other's target. A row's realised amount is then
-- its amount times the share of its start disc the land gate passes (decision 16, read in game
-- through tn_land_coarse: decision 8), at every scale and jitter; the table's share lists the discs
-- more than half sea. A spot reaches at most the rest of the footprint past the start disc.
local function map_spot(h, rows, i, L)
  local unit = TG.per_km2 / h.spots_per_km2 * h.base_density * h.mean_size
  local qty, fav, cap = {}, {}, {}
  for _, r in ipairs(rows) do
    local sr = start_radius(r)
    local start = "(" .. DEPTH .. r.id .. SUFFIX .. " > " .. num(r.radius_px) .. " * " .. S .. " - " .. sr .. ")"
    -- the row's amount, at least density_floor times vanilla's mean amount per tile over the footprint
    local amount = "max(" .. num(r.strength * unit) .. ", " .. num(TG.density_floor * h.base_density * RS.frequency) ..
      " * pi * " .. footprint(r) .. " * " .. footprint(r) .. ")"
    qty[#qty + 1] = start .. " * " .. amount .. " / (pi * " .. sr .. " * " .. sr .. " / " .. PER_CANDIDATE .. ")"
    fav[#fav + 1] = start
    cap[#cap + 1] = start .. " * (" .. footprint(r) .. " - " .. sr .. ")"
  end
  local q = "q" .. i
  L[q] = "hs_each * " .. sum(qty, "0") .. " * hs_land * hs_size"
  local radius_cap = #cap == 1 and cap[1] or ("max(" .. table.concat(cap, ", ") .. ")")
  local spacing = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", " .. num(SP.spacing) .. ", " ..
    num(SP.spacing_fine) .. ")"
  L["s" .. i] = "spot_noise{x = x, y = y, density_expression = " .. q .. " / " .. PER_CANDIDATE ..
    ", spot_quantity_expression = " .. q ..
    ", spot_radius_expression = max(" .. num(SP.min_radius) .. ", min(" .. radius_cap .. ", " .. num(h.rq) ..
    " * max(1, " .. q .. ") ^ " .. num(SP.cube_root) .. "))" ..
    ", spot_favorability_expression = " .. sum(fav, "0") .. " * (1 + hs_land + hs_grade)" ..
    ", seed0 = map_seed, seed1 = " .. num(h.seed1) .. ", region_size = " .. num(SP.region_size) ..
    ", candidate_spot_count = " .. CANDIDATES .. ", suggested_minimum_candidate_point_spacing = " .. spacing ..
    ", hard_region_target_quantity = 1, basement_value = " .. num(SP.basement) ..
    ", maximum_spot_basement_radius = " .. num(SP.basement_radius) .. "}"
  return "s" .. i
end

for _, h in ipairs(HC.resources) do
  local N = h.names
  local L = {}
  local branch = {}
  for i, M in ipairs(MAPS) do
    local rows = rows_of(M.key, h.resource)
    branch[i] = #rows > 0 and map_spot(h, rows, i, L) or num(SP.basement)
  end
  L.hs_spot = by_map(function(M)
    for i, X in ipairs(MAPS) do
      if X == M then
        return branch[i]
      end
    end
  end)
  -- per candidate: the size slider times vanilla's distance curve and the ramp, and land (sea for a
  -- field: its spots start on open water) with its grade, how far past the gate the coarse field
  -- reads, so a region's spots go first to its most inland (for a field the farthest offshore)
  -- candidates (config hotspots.land_px)
  L.hs_each = control(h.resource, "size") .. " * " .. distance_factor
  -- per candidate: its share of the row's amount (config hotspots.size), so the spots stop being equal
  local Z = HC.size
  L.hs_size = num(Z.gain) .. " * clamp((random_penalty{x = x, y = y, source = 1, amplitude = 1, seed = " ..
    num(h.seed1) .. "} - " .. num(Z.keep) .. ") / " .. num(1 - Z.keep) .. ", 0, 1) ^ " .. num(Z.power)
  if h.sea then
    L.hs_land = "(" .. K.land_coarse .. " < " .. num(-HC.sea_px) .. ")"
    L.hs_grade = "clamp(-(" .. minus(K.land_coarse, -HC.sea_px) .. ") / " .. num(HC.land_grade_px) .. ", 0, 1)"
  else
    L.hs_land = "(" .. K.land_coarse .. " > " .. num(HC.land_px) .. ")"
    L.hs_grade = "clamp((" .. minus(K.land_coarse, HC.land_px) .. ") / " .. num(HC.land_grade_px) .. ", 0, 1)"
  end
  -- the blob's amplitude: a typical spot's height at the reference strength and distance factor
  local unit = TG.per_km2 / h.spots_per_km2 * h.base_density * h.mean_size
  local q_ref = TG.reference_strength * unit * TG.reference_factor / HC.patches
  local height = SP.cone_factor * q_ref ^ SP.cube_root / (math.pi * h.rq * h.rq)
  def(N.v, "hs_spot + (" .. B.name .. " - " .. num(B.mean) .. ") * " .. num(height / B.divisor), L)
  local size = "(" .. control(h.resource, "size") .. " > 0)"
  local richness = control(h.resource, "richness")
  if h.fluid then
    local F = h.fluid
    def(N.p, size .. " * clamp(" .. N.v .. ", 0, 1) * random_penalty{x = x, y = y, source = 1, amplitude = " ..
      num(F.penalty) .. ", seed = " .. num(F.seed) .. "}")
    def(N.r, size .. " * " .. richness .. " * (" .. N.v .. " * " .. num(F.penalty) .. " + " .. num(F.additional) .. ")")
  else
    def(N.p, size .. " * clamp(" .. N.v .. ", 0, 1)")
    def(N.r, size .. " * " .. N.v .. " * " .. richness)
  end
end

-- The offshore field stamps, one body per map on its own chain (Tile only).
local function stamp(M)
  local du, dv = T.frame_offset[M.key][1], T.frame_offset[M.key][2]
  local L, parts = {}, {}
  for _, r in ipairs(rows_of(M.key, nil)) do
    if r.offshore then
      local i = tostring(#parts + 1)
      L["du" .. i] = M.g.u .. " - (" .. minus(HU .. r.id .. SUFFIX, du) .. ")"
      L["dv" .. i] = M.g.v .. " - (" .. minus(HV .. r.id .. SUFFIX, dv) .. ")"
      local reach = "(min(max(" .. num(r.radius_px) .. ", " .. num(HC.floor_tiles) .. " / " .. S .. "), " ..
        num(r.cap_px) .. ") + " .. num(FD.cover_px) .. ")"
      parts[#parts + 1] = "(du" .. i .. " * du" .. i .. " + dv" .. i .. " * dv" .. i .. " < " .. reach .. " * " ..
        reach .. ")"
    end
  end
  if #parts == 0 then
    return "0", nil
  end
  local any = #parts == 1 and parts[1] or ("max(" .. table.concat(parts, ", ") .. ")")
  return num(FD.stamp_elevation) .. " * " .. any, L
end

for _, M in ipairs(MAPS) do
  local name = FD.names[M.key]
  if name then
    local text, L = stamp(M)
    def(name, text, L)
  end
end

data:extend(E)
