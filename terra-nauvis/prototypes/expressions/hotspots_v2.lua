-- The second hotspot table's bodies (config.lua hotspots_v2; ARCHITECTURE.md, release versioning rule 14): new
-- worlds' presets name these in the place of the first table's, so a world keeps the table it was made on, and
-- no released body moves. prototypes/expressions/resources.lua explains the method: this file differs from it in
-- the rows it reads and in how a row spends its candidates.
--
-- The first table starts a row's spots inside the disc that holds 32 candidates, so a footprint of 500 tiles held
-- one blob of 100 and a wide empty ring. Here a footprint over spread_from tiles starts its spots across core_share
-- of itself, and only base_bodies + R / tiles_per_body of the candidates there carry ore: a low-frequency noise moves
-- the bar, so bodies gather in lobes, and a few large stand among many small, as in the first table. A footprint up
-- to spread_from is built as the first table builds it, to the bit from scale 2 up, so the rows round a start stay as
-- they were. At the fine scale such a row's disc can hold too few candidates to count on half of them, and each of
-- up to few_bodies carries ore, so a row stands empty less often.
--
-- No map slider reaches a hotspot: the switch and the amount setting are its only controls. Ore never leaves a
-- footprint at any scale, seed or amount: a cone is held to its room, as in the first table. A row's least_tiles
-- raises its footprint at low scales, where the table's floor is no wider than a regular patch; the enemy layer keeps
-- to the footprint without it, so the wider field is not one solid biter base.
local cfg = require("prototypes.config")
local V = require("prototypes.hotspot_rows_v2")

local HC = cfg.hotspots
local H2 = cfg.hotspots_v2
local RS = cfg.resources
local K = cfg.keys
local S = K.scale
local SUFFIX = cfg.regions.names.suffix
local DEPTH = cfg.regions.names.row.depth
local PD = cfg.regions.names.row.pd
local SP = HC.spot
local TG = HC.target
local B = HC.blob
local RP = RS.ramp

local function num(v)
  return string.format(cfg.number_format, v)
end

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

local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] then
    MAPS[#MAPS + 1] = {key = key, id = cfg.maps[key].id}
  end
end

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

local BY_ID = {}
for _, r in ipairs(V.rows) do
  BY_ID[r.id] = r
end

-- The rows of a resource on a map; either may be nil, for every one.
local function rows_of(map_key, resource)
  local out = {}
  for _, r in ipairs(V.rows) do
    if resource == nil or r.resource == resource then
      local on = map_key == nil
      for _, mk in ipairs(r.maps) do
        on = on or mk == map_key
      end
      if on then
        out[#out + 1] = r
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

local function footprint(r)
  local R = "min(max(" .. num(r.radius_px) .. " * " .. S .. ", " .. num(HC.floor_tiles) .. "), " .. num(r.cap_px) ..
    " * " .. S .. ")"
  return r.least_tiles and ("max(" .. num(r.least_tiles) .. ", " .. R .. ")") or R
end

local distance_factor = "clamp((distance - " .. num(TG.fade_from) .. ") / " .. num(TG.fade_span) .. ", 0, 1) * (1 + " ..
  "clamp((distance - " .. num(TG.double_from) .. ") / " .. num(TG.double_span) .. ", 0, 1)) * max((distance + " ..
  num(TG.rich_offset) .. ") / " .. num(TG.rich_span) .. ", 1) * " .. RP.name

local CANDIDATES = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", " .. num(SP.candidates) .. ", " ..
  num(SP.candidates_fine) .. ")"
local PER_CANDIDATE = "(" .. num(SP.region_size * SP.region_size) .. " / " .. CANDIDATES .. ")"

local function blob_height(h)
  local unit = TG.per_km2 / h.spots_per_km2 * h.base_density * h.mean_size
  local q_ref = TG.reference_strength * unit * TG.reference_factor / HC.patches
  return SP.cone_factor * q_ref ^ SP.cube_root / (math.pi * h.rq * h.rq) / B.divisor
end
local function blob_reach(h)
  return B.cap * blob_height(h) / (SP.cone_factor / (math.pi * h.rq * h.rq * h.rq))
end

local function room_of(h, r, rivals, R)
  local edge = num(blob_reach(h))
  local parts = {R .. " - " .. PD .. r.id .. SUFFIX .. " * " .. S .. " - " .. edge}
  for _, o in ipairs(rivals) do
    parts[#parts + 1] = PD .. o.id .. SUFFIX .. " * " .. S .. " - " .. footprint(o) .. " - " .. edge
  end
  return #parts == 1 and parts[1] or ("min(" .. table.concat(parts, ", ") .. ")")
end

-- One row's terms, shared by every map that adopts it: R<j> its footprint, q<j> its share of a candidate's quantity,
-- s<j> where its spots start, c<j> the radius it allows there, b<j> its bar. T takes what the resource's body reads,
-- Q what its quantity body reads and Bars what its bars body reads. The chain from a bar to a spot reads each local
-- many times and the game copies a local at every read, so a row's quantity and bar stand in named bodies of their
-- own: as locals of the resource's body they added 1.8 s to every start.
local function row_locals(h, r, j, T, Q, Bars)
  local L = {}
  local unit = TG.per_km2 / h.spots_per_km2 * h.base_density * h.mean_size
  local R, sr, st, room = "R" .. j, "sr" .. j, "s" .. j, "room" .. j
  L[R] = footprint(r)
  L[sr] = "if(" .. R .. " > " .. num(H2.spread_from) .. ", " .. num(H2.core_share) .. " * " .. R .. ", min(" ..
    num(HC.core_share) .. " * " .. R .. ", sqrt(" .. num(SP.max_spots) .. " * hs_pc / pi), " .. R .. " - hs_tight))"
  local rivals = {}
  for _, id in ipairs(V.rivals[r.id] or {}) do
    rivals[#rivals + 1] = BY_ID[id]
  end
  L[room] = room_of(h, r, rivals, R)
  L[st] = "(" .. DEPTH .. r.id .. SUFFIX .. " > " .. num(r.radius_px) .. " * " .. S .. " - " .. sr .. ") * (" .. room ..
    " > " .. num(SP.min_room) .. ")"
  -- a row over strength_top holds more than the first table's density floor, so rank reaches a wide footprint
  local floor = TG.density_floor * math.max(r.strength, H2.strength_top) / H2.strength_top
  local amount = "max(" .. num(r.strength * unit) .. ", " .. num(floor * h.base_density * RS.frequency) .. " * pi * " ..
    R .. " * " .. R .. ")"
  for k, v in pairs(L) do
    T[k], Q[k], Bars[k] = v, v, v
  end
  -- the candidates the start disc holds, and the share of them that carry ore
  local held = "held" .. j
  Q[held] = "pi * " .. sr .. " * " .. sr .. " / hs_pc"
  Bars[held] = Q[held]
  Q["q" .. j] = st .. " * " .. amount .. " / " .. held
  T["c" .. j] = st .. " * " .. room
  local top = num(H2.top_share)
  local wanted = "(" .. num(H2.base_bodies) .. " + " .. R .. " / " .. num(H2.tiles_per_body) .. ")"
  -- a row of this table counts on few_bodies at every scale; the first table's rows, round the starts, at the fine one
  local few = r.layer and num(H2.few_bodies) or "hs_few"
  local most = "if(" .. R .. " > " .. num(H2.spread_from) .. ", min(" .. top .. ", " .. wanted .. " / " .. held ..
    "), " .. top .. ")"
  Bars["b" .. j] = st .. " * (1 - min(1, max(" .. few .. " / " .. held .. ", " .. most .. ")))"
end

-- A map's quantity and bars of a resource, as the expressions its named bodies choose between.
local function map_qty(rows, index)
  local qty = {}
  for _, r in ipairs(rows) do
    qty[#qty + 1] = "q" .. index[r.id]
  end
  return sum(qty, "0")
end
local function map_bars(rows, index)
  local bar = {}
  for _, r in ipairs(rows) do
    bar[#bar + 1] = "b" .. index[r.id]
  end
  return #bar == 0 and "0" or #bar == 1 and bar[1] or ("max(" .. table.concat(bar, ", ") .. ")")
end

-- One resource's spot noise on one map, as locals of its body: the map's i, its rows' numbers j in `index`, and the
-- resource's named quantity and bars bodies.
local function map_spot(h, rows, i, L, index, part)
  local fav, cap = {}, {}
  for _, r in ipairs(rows) do
    local j = index[r.id]
    fav[#fav + 1] = "s" .. j
    cap[#cap + 1] = "c" .. j
  end
  L["bar" .. i] = part.bars .. " + " .. num(H2.lobe.gain) .. " * " .. H2.lobe.name .. " * (" .. part.bars .. " > " ..
    num(H2.lobe.above) .. ")"
  L["open" .. i] = "max(" .. num(H2.min_gap) .. ", 1 - bar" .. i .. ")"
  L["kept" .. i] = "clamp((hs_u - bar" .. i .. ") / open" .. i .. ", 0, 1)"
  local q = "qm" .. i
  local raw = "raw" .. i
  L[raw] = "hs_each * " .. part.qty .. " * hs_land * " .. num(H2.size.gain) .. " * kept" .. i .. " ^ " ..
    num(H2.size.power) .. " / open" .. i
  L[q] = raw .. " * (" .. raw .. " > " .. num((SP.min_radius / h.rq) ^ (1 / SP.cube_root)) .. ")"
  local radius_cap = #cap == 1 and cap[1] or ("max(" .. table.concat(cap, ", ") .. ")")
  local spacing = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", " .. num(SP.spacing) .. ", " ..
    num(SP.spacing_fine) .. ")"
  L["spot" .. i] = "spot_noise{x = x, y = y, density_expression = " .. q .. " / hs_pc" ..
    ", spot_quantity_expression = " .. q ..
    ", spot_radius_expression = max(" .. num(SP.min_radius) .. ", min(" .. radius_cap .. ", " .. num(h.rq) ..
    " * max(1, " .. q .. ") ^ " .. num(SP.cube_root) .. "))" ..
    ", spot_favorability_expression = " .. sum(fav, "0") .. " * (1 + hs_land + hs_grade)" ..
    ", seed0 = map_seed, seed1 = " .. num(h.seed1) .. ", region_size = " .. num(SP.region_size) ..
    ", candidate_spot_count = " .. CANDIDATES .. ", suggested_minimum_candidate_point_spacing = " .. spacing ..
    ", hard_region_target_quantity = 1, basement_value = " .. num(SP.basement) ..
    ", maximum_spot_basement_radius = " .. num(SP.basement_radius) .. "}"
  return "spot" .. i
end

-- Past from_scale the lobes grow with the map: at a fixed width a footprint of 1,000 tiles reads as even round spots.
def(H2.lobe.name, "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(H2.lobe.seed1) ..
  ", input_scale = 1 / (" .. num(H2.lobe.wavelength) .. " * max(1, " .. S .. " / " .. num(H2.lobe.from_scale) .. "))}")

for _, h in ipairs(HC.resources) do
  local name = H2.bodies[h.resource]
  if name then
    local L, branch, index = {hs_pc = PER_CANDIDATE}, {}, {}
    -- at the fine scale a small row's disc can hold no cone with room, or too few candidates to count on
    L.hs_tight = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", -inf, " .. num(blob_reach(h) + SP.min_room) .. ")"
    local Q = {hs_pc = PER_CANDIDATE, hs_tight = L.hs_tight}
    local Bars = {hs_pc = PER_CANDIDATE, hs_tight = L.hs_tight}
    Bars.hs_few = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", 0, " .. num(H2.few_bodies) .. ")"
    for j, r in ipairs(rows_of(nil, h.resource)) do
      index[r.id] = tostring(j)
      row_locals(h, r, tostring(j), L, Q, Bars)
    end
    local part = H2.parts[h.resource]
    def(part.qty, by_map(function(M) return map_qty(rows_of(M.key, h.resource), index) end), Q)
    def(part.bars, by_map(function(M) return map_bars(rows_of(M.key, h.resource), index) end), Bars)
    for i, M in ipairs(MAPS) do
      local rows = rows_of(M.key, h.resource)
      branch[i] = #rows > 0 and map_spot(h, rows, i, L, index, part) or num(SP.basement)
    end
    L.hs_spot = by_map(function(M)
      for i, X in ipairs(MAPS) do
        if X == M then
          return branch[i]
        end
      end
    end)
    L.hs_each = distance_factor
    L.hs_u = "random_penalty{x = x, y = y, source = 1, amplitude = 1, seed = " .. num(h.seed1) .. "}"
    L.hs_land = "(" .. K.land_coarse .. " > " .. num(HC.land_px) .. ")"
    L.hs_grade = "clamp((" .. minus(K.land_coarse, HC.land_px) .. ") / " .. num(HC.land_grade_px) .. ", 0, 1)"
    def(name, "hs_spot + min(" .. B.name .. " - " .. num(B.mean) .. ", " .. num(B.cap) .. ") * " ..
      num(blob_height(h)), L)
  end
end

-- Trees off the table's solid ore (config.lua resources.ore_trees): the hook key's off value, and the share of a
-- tree's probability left near the ore, 1 with hotspots off.
local OT = RS.ore_trees
local solid = {}
for _, resource in ipairs(RS.ramped) do
  solid[#solid + 1] = H2.bodies[resource]
end
solid[#solid + 1] = H2.bodies["uranium-ore"]
def(OT.key, "0")
local function open(name, margin, floor)
  def(name, "if(" .. K.hotspots .. " > " .. num(cfg.ridges.switch_threshold) .. ", clamp(-max(" ..
    table.concat(solid, ", ") .. ") / " .. num(margin) .. ", " .. num(floor) .. ", 1), 1)")
end
open(OT.open, OT.margin, OT.floor)
open(OT.plants.open, OT.plants.margin, OT.plants.floor)

-- The shares' next versions: each solid body less the wobble its ore's probability takes, in its cone's least slope
-- (data-final-fixes.lua probability_v3), so the shares follow the ore that stands.
local trimmed = {}
for _, h in ipairs(HC.resources) do
  if H2.bodies[h.resource] and not h.fluid then
    local slope = SP.cone_factor / (math.pi * h.rq * h.rq * h.rq)
    trimmed[#trimmed + 1] = H2.bodies[h.resource] .. " - " .. num(RS.richness_v2.edge.trim * slope) .. " * " ..
      RS.richness_v2.edge.wobble
  end
end
local function open_v2(name, margin, floor)
  def(name, "if(" .. K.hotspots .. " > " .. num(cfg.ridges.switch_threshold) .. ", clamp(-max(" ..
    table.concat(trimmed, ", ") .. ") / " .. num(margin) .. ", " .. num(floor) .. ", 1), 1)")
end
open_v2(OT.open_v2, OT.margin, OT.floor)
open_v2(OT.plants.open_v2, OT.plants.margin, OT.plants.floor)

-- The wobble that moves a solid hotspot ore's outline inward (config.lua resources.richness_v2.edge).
local ED = RS.richness_v2.edge
local function wave(wavelength, seed1)
  return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = 1 / " ..
    num(wavelength) .. "}"
end
def(ED.wobble, "clamp(" .. num(ED.mid) .. " + " .. num(ED.amp) .. " * (" .. wave(ED.long, ED.seed1) .. " + " ..
  num(ED.half) .. " * " .. wave(ED.short, ED.seed1 + 1) .. "), 0, 1)")

-- Regular ore keeps out of every footprint of the table, as the first gap body does for the first table's.
local NP = RS.natural
local GL, GI = {}, {}
for j, r in ipairs(V.rows) do
  GI[r.id] = "g" .. j
  GL["g" .. j] = PD .. r.id .. SUFFIX .. " * " .. S .. " - " .. footprint(r)
end
def(H2.gap, "if(" .. K.hotspots .. " > " .. num(cfg.ridges.switch_threshold) .. ", " .. by_map(function(M)
  local parts = {}
  for _, r in ipairs(rows_of(M.key, nil)) do
    parts[#parts + 1] = GI[r.id]
  end
  return #parts == 0 and num(NP.no_gap) or #parts == 1 and parts[1] or ("min(" .. table.concat(parts, ", ") .. ")")
end) .. ", " .. num(NP.no_gap) .. ")", GL)

data:extend(E)
