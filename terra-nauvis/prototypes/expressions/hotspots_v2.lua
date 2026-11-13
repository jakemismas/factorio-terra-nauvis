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
-- to the footprint without it, so the wider field is not one solid biter base (as Indonesia's would be).
local cfg = require("prototypes.config")
local V = require("prototypes.hotspot_rows_v2")
local H3 = cfg.hotspots_v3
local H4 = cfg.hotspots_v4
local H5 = cfg.hotspots_v5

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

-- The solid ores' third version (config.lua hotspots_v2.v3, which says why): the second table's rows, footprints, room,
-- candidates, blob and lobe noise, with a row's ore set by vanilla's large patch and per-tile ore at its distance
-- (prototypes/ore_curves.lua) instead of by its footprint's area. A row's candidates carry W bodies of body_tiles each
-- on average; data-final-fixes.lua's richness wrapper gives the ore per tile.
local OC = require("prototypes.ore_curves")
local V3 = H2.v3
-- 1 where a lean row keeps its full field on the save's map and scale, 0 where its footprint touches a stronger row's
-- of its ore (the near bodies' pair lists, hotspots_v5.touch tiles apart or closer).
local function far_keep(r, fade)
  return "(" .. by_map(function(M)
    local touch = {}
    for _, o in ipairs(fade.lean.touching[M.key][r.id] or {}) do
      local b = BY_ID[o.id]
      if b.resource == r.resource then
        touch[#touch + 1] = "(" .. num(o.d) .. " * " .. S .. " < " .. footprint(r) .. " + " .. footprint(b) .. " + " ..
          num(H5.touch) .. ")"
      end
    end
    return #touch == 0 and "1" or ("(1 - min(1, " .. table.concat(touch, " + ") .. "))")
  end) .. ")"
end

local function v3_row(h, r, j, Q, T, fade)
  local R, sr, st, room, held, W = "R" .. j, "sr" .. j, "s" .. j, "room" .. j, "held" .. j, "w" .. j
  local rivals = {}
  for _, id in ipairs(V.rivals[r.id] or {}) do
    rivals[#rivals + 1] = BY_ID[id]
  end
  local L = {}
  L[R] = footprint(r)
  L[sr] = "if(" .. R .. " > " .. num(H2.spread_from) .. ", " .. num(H2.core_share) .. " * " .. R .. ", min(" ..
    num(HC.core_share) .. " * " .. R .. ", sqrt(" .. num(SP.max_spots) .. " * hs_pc / pi), " .. R .. " - hs_tight))"
  local kr = V3.k[r.strength]
  local hd, gd = "h" .. j, "g" .. j
  if fade then
    -- 1.2.0 (config.lua hotspots_v4): h the design over L here, min(K, total_cap / L) * b, and g the faded field over
    -- L, min(h, near) + max(h - near, 0) * t. The start disc shrinks toward the disc of per_cone candidates a cone
    -- as t falls, so a faded field's few bodies stand together as the full field's many do, and is the third
    -- version's at t = 1.
    local F = H4.fade
    -- a fade table (crude oil, hotspots_v4.oil) brings its own near
    local near = type(fade) == "table" and fade.near or F.near
    if type(fade) == "table" and fade.lean then
      -- lean ore (hotspots_v5): the design C[K] * b over L here, of which the spots carry t (the near field is the
      -- near body at the row's centre, fading out with t: hotspots_v5.near)
      -- a row whose footprint touches a stronger row's of its ore on the save's map and scale holds no field of its
      -- own: the fields would read as one, over that ore's design
      L[hd] = num(H5.caps[kr]) .. " * hs_b * hs_sz / max(1, hs_l) * " .. far_keep(r, fade)
      L[gd] = "(" .. hd .. " * hs_t)"
    else
      L[hd] = "min(" .. num(kr) .. ", " .. num(V3.far.total_cap[kr]) .. " / max(1, hs_l)) * hs_b"
      L[gd] = "(min(" .. hd .. ", " .. num(near) .. ") + max(" .. hd .. " - " .. num(near) .. ", 0) * hs_t)"
    end
    if not (type(fade) == "table" and fade.lean) then
      -- (lean ore keeps the whole start disc: a near field is one to three bodies of the narrow draw wherever they
      -- fall, and a disc of a few candidates held a field to a third of its design or nothing)
      L["sf" .. j] = L[sr]
      L[sr] = "min(sf" .. j .. ", hs_t * sf" .. j .. " + (1 - hs_t) * sqrt(" .. num(F.per_cone) .. " * hs_v * " ..
        gd .. " * hs_pc / pi))"
    end
  end
  L[room] = room_of(h, r, rivals, R)
  L[st] = "(" .. DEPTH .. r.id .. SUFFIX .. " > " .. num(r.radius_px) .. " * " .. S .. " - " .. sr .. ") * (" .. room ..
    " > " .. num(SP.min_room) .. ")"
  for k, v in pairs(L) do
    T[k], Q[k] = v, v
  end
  -- W in body_tiles cones, its total held to far.total_cap and its count to top_share of the start disc's candidates
  Q[held] = "pi * " .. sr .. " * " .. sr .. " / hs_pc"
  if type(fade) == "table" and fade.lean then
    -- lean ore: W over the candidates held (the game copies a local at every read, so the row reads held once here
    -- and once in its quantity, not in W and the quantity and fr each)
    local wq = "wq" .. j
    Q[wq] = "min(hs_v * " .. gd .. " / max(1, " .. held .. "), " .. num(H2.top_share) .. ")"
    Q["q" .. j] = st .. " * " .. num(OC.body_quantity(h)) .. " * " .. wq .. " * hs_f ^ " ..
      num(V3.body_power - 1) .. " * hs_ff"
    T[held], T[wq] = Q[held], Q[wq]
    T["fr" .. j] = st .. " * " .. wq .. " / " .. num(H2.top_share)
    T["c" .. j] = st .. " * " .. room
    return
  end
  if fade then
    -- 1.2.0: W the bodies' worth of L * g at the faded ore per tile (hs_v), still held to top_share
    Q[W] = "min(hs_v * " .. gd .. ", " .. num(H2.top_share) .. " * " .. held .. ")"
  else
    Q[W] = "min(" .. num(kr) .. " * hs_w, " ..
      num(V3.area_fit / (V3.per_tile * V3.body_tiles) * V3.far.total_cap[kr]) .. " * " .. K.hotspot_amount ..
      " / hs_p, " .. num(H2.top_share) .. " * " .. held .. ")"
  end
  -- the row's quantity, W cones' tiles in far bodies of hs_f ^ 1.5 a cone's quantity, spread over its start disc's
  -- candidates: the density its regions reach
  -- (1.2.0: inside vanilla's quantity fade, where L is 0, the faded disc holds no candidate, and the quantity reads
  -- 0 there, not 0 / 0: a NaN in one row's share took the whole spot region's target, and its fields with it)
  Q["q" .. j] = st .. " * " .. num(OC.body_quantity(h)) .. " * " .. W .. " * hs_f ^ " .. num(V3.body_power - 1) ..
    " * hs_ff / " .. (fade and ("max(1, " .. held .. ")") or held)
  -- the share of a cone a body at this row's candidates holds: hs_f, or more where W / hs_f bodies would outnumber
  -- top_share of the candidates (a small disc, Carrara): fewer, larger bodies then hold the same tiles, a little richer
  for _, k in ipairs({held, W}) do
    T[k] = Q[k]
  end
  T["fr" .. j] = st .. " * " .. W .. " / (" .. num(H2.top_share) .. " * max(1, " .. held .. "))"
  T["c" .. j] = st .. " * " .. room
end

-- One map's spot noise of a resource's third version, as locals of its body. Every candidate in a start disc offers a
-- body (size a power of a uniform draw, mean 1, of a body_tiles cone's quantity), and the region's target, the
-- row's quantity, takes them in an order a draw and the lobe noise set until it is reached: so a field holds W
-- bodies' worth, its bodies gather where the lobe is low, and the last one is cut to fit. Bodies dealt by a draw
-- against a share held one field to a third of its design and another to three times it in test runs.
local function v3_spot(h, rows, i, T, index, part)
  local fav, cap = {}, {}
  for _, r in ipairs(rows) do
    fav[#fav + 1] = "s" .. index[r.id]
    cap[#cap + 1] = "c" .. index[r.id]
  end
  local least = num((SP.min_radius / h.rq) ^ (1 / SP.cube_root))
  T["raw" .. i] = "(" .. part.qty .. " > 0) * hs_land * " .. num(OC.body_quantity(h)) .. " * hs_g * hs_s ^ hs_pw" ..
    " * hs_fr ^ " .. num(V3.body_power)
  T["qm" .. i] = "raw" .. i .. " * (raw" .. i .. " > " .. least .. ")"
  local radius_cap = #cap == 1 and cap[1] or ("max(" .. table.concat(cap, ", ") .. ")")
  local spacing = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", " .. num(SP.spacing) .. ", " ..
    num(SP.spacing_fine) .. ")"
  T["spot" .. i] = "spot_noise{x = x, y = y, density_expression = " .. part.qty .. " * hs_land / hs_pc" ..
    ", spot_quantity_expression = qm" .. i ..
    ", spot_radius_expression = max(" .. num(SP.min_radius) .. ", min(" .. radius_cap .. ", " .. num(h.rq) ..
    " * max(1, qm" .. i .. ") ^ " .. num(SP.cube_root) .. "))" ..
    ", spot_favorability_expression = " .. sum(fav, "0") .. " * hs_land * (" .. num(V3.order_base) .. " + hs_u - " ..
    num(V3.lobe_gain) .. " * clamp(" .. H2.lobe.name .. ", -1, 1))" ..
    ", seed0 = map_seed, seed1 = " .. num(h.seed1) .. ", region_size = " .. num(SP.region_size) ..
    ", candidate_spot_count = " .. CANDIDATES .. ", suggested_minimum_candidate_point_spacing = " .. spacing ..
    ", hard_region_target_quantity = 1, basement_value = " .. num(SP.basement) ..
    ", maximum_spot_basement_radius = " .. num(SP.basement_radius) .. "}"
  return "spot" .. i
end

-- The quantity body's terms for the fade (1.2.0): L, t, b and the unit of bodies one L asks for.
local function fade_terms(h, Q, fade)
  -- 1.2.0 (config.lua hotspots_v4): L, the start fade t and the scale bonus b at a candidate, and the bodies one
  -- L asks for at the faded ore per tile, 1 + (per_tile - 1) * t times P(d). L, t and that unit stand in named
  -- terms (hotspots_v4.terms): every row reads them several times. A fade table (crude oil) brings its own L,
  -- area fit and yield per tile, wells a tile times a well's yield before the fade's multiple.
  local oil = type(fade) == "table" and fade
  local TM = H4.terms
  local per_tile = (oil and oil.density) and ("max(1, " .. num(oil.density) .. " * " .. oil.well .. ")") or
    ("max(1, " .. OC.area_per_tile(h) .. ")")
  local unit = TM.unit[h.resource]
  if oil and oil.lean then
    -- lean ore (hotspots_v5): the cones one L asks for at the faded per tile, near_per_tile (crude oil near_well a
    -- well) inside r_in and per_tile times vanilla's past r_out, under a name of its own
    unit = oil.lean.unit
    -- the area fit blends from near_fit (a field of a cone or two loses little) to the full fields' with t
    local af = oil.oil and H5.oil_area_fit or V3.area_fit
    local nf = oil.oil and H5.oil_near_fit or H5.near_fit
    local near = num(oil.lean.near_pt) .. " * " .. OC.size_root(h.resource)
    def(unit, "(" .. num(nf / V3.body_tiles) .. " + " .. num((af - nf) / V3.body_tiles) .. " * " ..
      TM.fade .. ") * " .. K.hotspot_amount .. " * " .. TM.large[h.resource] .. " / (" .. near ..
      " + (" .. num(V3.per_tile) .. " * " .. per_tile .. " - " .. near .. ") * " .. TM.fade .. ")")
    -- (the full design follows the size slider as vanilla's patch quantity does)
    Q.hs_sz = OC.size(h.resource)
  elseif not (oil and oil.large_only) then
    def(TM.large[h.resource], oil and oil.large or OC.large(h))
    def(unit, num((oil and oil.area_fit or V3.area_fit) / V3.body_tiles) .. " * " ..
      K.hotspot_amount .. " * " .. TM.large[h.resource] .. " / (" .. OC.faded_per_tile(TM.fade) .. " * " ..
      per_tile .. ")")
  end
  Q.hs_l = TM.large[h.resource]
  Q.hs_t = TM.fade
  Q.hs_b = OC.bonus()
  Q.hs_v = unit
end

-- The size draws of a body's spots (1.2.0): the far fields' narrow draw for crude oil, and for lean near fields.
local function fade_draws(T, fade, FS)
if type(fade) == "table" and (fade.oil or fade.density) then
  -- crude oil: a field of a few cones takes the far fields' narrower size draw, so one draw does not set its wells
  T.hs_g, T.hs_pw = num(FS.gain), num(FS.power)
end
end

-- The blob's share on a lean near field (hotspots_v5.near_blob), blending to the whole blob with t: its low octave
-- lifts or sinks a lone body whole.
local function near_blob(fade)
  if type(fade) == "table" and fade.lean and not fade.density then
    return " * (" .. num(H5.near_blob) .. " + " .. num(1 - H5.near_blob) .. " * hs_t)"
  end
  return ""
end

-- A lean near field (hotspots_v5.near): one body at the jittered centre of each row that carries at the save's
-- scale, the named expression of its radius less the distance to the nearest such centre (the basement elsewhere),
-- and the body's term: a cone of near_plateau times the peak cap's height, fading out with t and in over the
-- starting area's second radius, so a carrier holds one body of near_total whatever the spots' regions pool, and
-- nothing else round the start.
local function near_term(h, fade)
  local N = fade.lean.near_body
  def(N.name, by_map(function(M)
    local parts = {}
    for _, r in ipairs(rows_of(M.key, h.resource)) do
      -- (held inside the row's footprint, less the blob's reach, as its spots are)
      local inside = "min(" .. num(N.radius) .. " * " .. OC.size_root(h.resource) .. ", " .. footprint(r) .. " - " ..
        num(blob_reach(h)) .. ") - " .. PD .. r.id .. SUFFIX .. " * " .. S
      local touch = {}
      for _, o in ipairs(fade.lean.touching[M.key][r.id] or {}) do
        local b = BY_ID[o.id]
        touch[#touch + 1] = "(" .. num(o.d) .. " * " .. S .. " < " .. footprint(r) .. " + " .. footprint(b) .. " + " ..
          num(H5.touch) .. ") + (" .. num(o.d - o.j) .. " * " .. S .. " < " .. num(o.ra) .. " * " ..
          OC.size_root(r.resource) .. " + " .. num(o.rb) .. " * " .. OC.size_root(b.resource) .. " + " ..
          num(H5.touch) .. ")"
      end
      parts[#parts + 1] = #touch == 0 and inside or
        ("if(" .. table.concat(touch, " + ") .. " < 1, " .. inside .. ", " .. num(SP.basement) .. ")")
    end
    return #parts == 0 and num(SP.basement) or #parts == 1 and parts[1] or ("max(" .. table.concat(parts, ", ") .. ")")
  end))
  -- none inside vanilla's starting resource radius (whatever the starting area slider), whole from twice it
  local grow = "(1 - hs_t) * clamp(distance / " .. num(cfg.resources.lean.start_tiles) .. " - 1, 0, 1)"
  -- (its radius follows the size slider's cube root, as a vanilla patch's does, at the same height)
  return "if(" .. N.name .. " * " .. grow .. " > 0, " .. num(N.height / N.radius) .. " / " ..
    OC.size_root(h.resource) .. " * " .. N.name .. " * " .. grow .. ", " .. num(SP.basement) .. ")"
end

-- A third version's body: its spots (and a lean near body), plus the blob but on crude oil.
local function body_def(h, name, T, fade)
  local G = V3.grain
  local spot = "hs_spot"
  if type(fade) == "table" and fade.lean then
    T.hs_near = near_term(h, fade)
    spot = "max(hs_spot, hs_near)"
  end
  if type(fade) == "table" and fade.blob == 0 then
    -- crude oil (hotspots_v4.oil): plain cones, so a field's area, and so its well count, follows its quantity
    def(name, spot, T)
    return
  end
  def(name, spot .. " + (min(" .. B.name .. " - " .. num(B.mean) .. ", " .. num(B.cap) .. ") + " ..
    "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(G.seed1) .. ", input_scale = " ..
    num(1 / G.wavelength) .. ", output_scale = " .. num(G.output) .. "}) * " ..
    num(V3.blob_scale * blob_height(h)) .. " * hs_f ^ " .. num(V3.far.blob_power) .. near_blob(fade), T)
end

-- A resource's third version: its quantity body, then its body.
local function v3_bodies(h, name, part, fade)
  local T = {hs_pc = PER_CANDIDATE}
  T.hs_tight = "if(" .. S .. " > " .. num(SP.fine_scale) .. ", -inf, " .. num(blob_reach(h) + SP.min_room) .. ")"
  local Q = {hs_pc = PER_CANDIDATE, hs_tight = T.hs_tight}
  -- bodies per unit of K at a candidate: the amount setting times L(d) over the area per_tile * P(d) asks of each
  if fade then
    fade_terms(h, Q, fade)
  else
    Q.hs_p = "max(1, " .. OC.area_per_tile(h) .. ")"
    Q.hs_w = num(V3.area_fit / (V3.per_tile * V3.body_tiles)) .. " * " .. K.hotspot_amount .. " * " .. OC.large(h) ..
      " / hs_p"
  end
  -- a far field's body size (ore_curves.lua body_scale): the quantity and spots read it, the richness wrapper too
  if type(fade) == "table" and (fade.oil or fade.density) then
    -- crude oil: full-size bodies (one unit of K asks for over a cone of wells at every distance, so body_scale would
    -- read 1)
    Q.hs_f = "1"
  else
    Q.hs_f = OC.body_scale(h)
  end
  T.hs_f = Q.hs_f
  -- far bodies lose less to the blob and the trim than the near ones area_fit was fitted on: far.fit takes it back,
  -- ramped in from fit_from so a near field (hs_f 1) keeps its quantity
  Q.hs_ff = "(" .. num(V3.far.fit) .. " + " .. num(1 - V3.far.fit) .. " * clamp((hs_f - " .. num(V3.far.fit_from) ..
    ") / " .. num(1 - V3.far.fit_from) .. ", 0, 1))"
  local index = {}
  for j, r in ipairs(rows_of(nil, h.resource)) do
    index[r.id] = tostring(j)
    v3_row(h, r, tostring(j), Q, T, fade)
  end
  local fr = {"hs_f"}
  for j = 1, #rows_of(nil, h.resource) do
    fr[#fr + 1] = "fr" .. j
  end
  T.hs_fr = "min(1, max(" .. table.concat(fr, ", ") .. "))"
  T.hs_w, T.hs_p = Q.hs_w, Q.hs_p
  if fade then
    T.hs_l, T.hs_t, T.hs_b, T.hs_v, T.hs_sz = Q.hs_l, Q.hs_t, Q.hs_b, Q.hs_v, Q.hs_sz
  end
  part = part or V3.parts[h.resource]
  def(part.qty, by_map(function(M) return map_qty(rows_of(M.key, h.resource), index) end), Q)
  local branch = {}
  for i, M in ipairs(MAPS) do
    local rows = rows_of(M.key, h.resource)
    branch[i] = #rows > 0 and v3_spot(h, rows, i, T, index, part) or num(SP.basement)
  end
  T.hs_spot = by_map(function(M)
    for i, X in ipairs(MAPS) do
      if X == M then
        return branch[i]
      end
    end
  end)
  T.hs_u = "random_penalty{x = x, y = y, source = 1, amplitude = 1, seed = " .. num(h.seed1) .. "}"
  T.hs_s = "random_penalty{x = x, y = y, source = 1, amplitude = 1, seed = " .. num(h.seed1 + V3.size.seed) .. "}"
  -- a far field's few bodies take a narrower size draw (far.size), so one draw does not set its total
  local FS = V3.far.size
  T.hs_g = "if(hs_f < 1, " .. num(FS.gain) .. ", " .. num(V3.size.gain) .. ")"
  T.hs_pw = "if(hs_f < 1, " .. num(FS.power) .. ", " .. num(V3.size.power) .. ")"
  if type(fade) == "table" and fade.lean and not fade.density then
    -- lean ore: a faded field of one or two cones takes the far fields' narrower size draw, blending to the near
    -- draw with t, so one draw does not set its total
    T.hs_g = "if(hs_f < 1, " .. num(FS.gain) .. ", " .. num(FS.gain) .. " + " .. num(V3.size.gain - FS.gain) ..
      " * hs_t)"
    T.hs_pw = "if(hs_f < 1, " .. num(FS.power) .. ", " .. num(FS.power) .. " + " .. num(V3.size.power - FS.power) ..
      " * hs_t)"
  end
  fade_draws(T, fade, FS)
  T.hs_land = "(" .. K.land_coarse .. " > " .. num(HC.land_px) .. ")"
  body_def(h, name, T, fade)
end

for _, h in ipairs(HC.resources) do
  if V3.bodies[h.resource] then
    v3_bodies(h, V3.bodies[h.resource])
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
-- 0.3.0's presets read the solid ores' third version (H2.v3), so the shares follow its bodies.
local function trimmed_of(h, bodies)
  local slope = SP.cone_factor / (math.pi * h.rq * h.rq * h.rq)
  local v3 = (bodies or V3.bodies)[h.resource]
  if not v3 then
    return H2.bodies[h.resource] .. " - " .. num(RS.richness_v2.edge.trim * slope) .. " * " ..
      RS.richness_v2.edge.wobble
  end
  -- a far field's bodies are narrower (ore_curves.lua height_scale): the trim follows them, as probability_v3's does
  return v3 .. " - " .. num(V3.trim * slope) .. " * " .. RS.richness_v2.edge.wobble .. " * " .. OC.height_scale(h)
end
local function trimmed_list(bodies)
  local list = {}
  for _, h in ipairs(HC.resources) do
    if H2.bodies[h.resource] and not h.fluid then
      list[#list + 1] = trimmed_of(h, bodies)
    end
  end
  return list
end
local trimmed = trimmed_list()
local function open_v2(name, margin, floor, list)
  def(name, "if(" .. K.hotspots .. " > " .. num(cfg.ridges.switch_threshold) .. ", clamp(-max(" ..
    table.concat(list or trimmed, ", ") .. ") / " .. num(margin) .. ", " .. num(floor) .. ", 1), 1)")
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
local function gap_body(name)
  local GL, GI = {}, {}
  for j, r in ipairs(V.rows) do
    GI[r.id] = "g" .. j
    GL["g" .. j] = PD .. r.id .. SUFFIX .. " * " .. S .. " - " .. footprint(r)
  end
  def(name, "if(" .. K.hotspots .. " > " .. num(cfg.ridges.switch_threshold) .. ", " .. by_map(function(M)
    local parts = {}
    for _, r in ipairs(rows_of(M.key, nil)) do
      parts[#parts + 1] = GI[r.id]
    end
    return #parts == 0 and num(NP.no_gap) or #parts == 1 and parts[1] or ("min(" .. table.concat(parts, ", ") .. ")")
  end) .. ", " .. num(NP.no_gap) .. ")", GL)
end
gap_body(H2.gap)

-- Regional scarcity (config.lua resources.scarcity). A resource's province weight: 1 within reach_px of any of its
-- footprints on the map (scaled), falling to 0 over a width that varies from a hard edge to about wide.px, the edge
-- moved in and out by a ragged noise; read only at spot candidates. Not gated by the hotspot switch: the provinces
-- are geology, the rows only where they stand.
local SC = RS.scarcity
local function wave_px(wavelength_px, seed1)
  return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = 1 / (" ..
    num(wavelength_px) .. " * " .. S .. ")}"
end
local function level_share(res)
  local sh = SC.shares[res]
  return "if(" .. K.scarcity .. " > " .. num((SC.levels.medium + SC.levels.strong) / 2) .. ", " .. num(sh.strong) ..
    ", if(" .. K.scarcity .. " > " .. num((SC.levels.off + SC.levels.medium) / 2) .. ", " .. num(sh.medium) .. ", 1))"
end
for _, res in ipairs({"iron-ore", "copper-ore", "coal", "stone", "uranium-ore", "crude-oil"}) do
  local N = SC.names[res]
  local PL = {}
  for j, r in ipairs(rows_of(nil, res)) do
    PL["g" .. j] = PD .. r.id .. SUFFIX .. " * " .. S .. " - " .. footprint(r)
  end
  local index = {}
  for j, r in ipairs(rows_of(nil, res)) do
    index[r.id] = "g" .. j
  end
  PL.gap = by_map(function(M)
    local parts = {}
    for _, r in ipairs(rows_of(M.key, res)) do
      parts[#parts + 1] = index[r.id]
    end
    return #parts == 0 and num(SC.no_gap) or #parts == 1 and parts[1] or ("min(" .. table.concat(parts, ", ") .. ")")
  end)
  PL.edge = "(" .. num(SC.reach_px) .. " + " .. num(SC.rag.px) .. " * " ..
    wave_px(SC.rag.wavelength_px, SC.rag.seed1) .. ") * " .. S
  PL.wide = "max(1, " .. num(SC.wide.px) .. " * " .. S .. " * (" .. num(SC.wide.base) .. " + " .. num(SC.wide.gain) ..
    " * " .. wave_px(SC.wide.wavelength_px, SC.wide.seed1) .. "))"
  def(N.province, "clamp((edge + wide - gap) / wide, 0, 1)", PL)
  -- The keep: 0 or 1 for a whole spot region. near is the region's nearest point to the spawn, which sits at the
  -- origin on Earth presets.
  -- (spot regions are centred on multiples of the region size: rx * R is the region's centre)
  local R, H = num(SC.region), num(SC.region / 2)
  local KL = {
    rx = "floor((x + " .. H .. ") / " .. R .. ")",
    ry = "floor((y + " .. H .. ") / " .. R .. ")",
    nx = "max(0, max(rx * " .. R .. " - " .. H .. ", -(rx * " .. R .. " + " .. H .. ")))",
    ny = "max(0, max(ry * " .. R .. " - " .. H .. ", -(ry * " .. R .. " + " .. H .. ")))",
    ramp = "clamp((sqrt(nx * nx + ny * ny) - " .. num(SC.ramp.from) .. " * " .. S .. " - " .. num(SC.ramp.margin) ..
      ") / (" .. num(SC.ramp.full - SC.ramp.from) .. " * " .. S .. "), 0, 1)",
    -- a hash of the region and the map seed in [0, 1), the same at every candidate of the region (random_penalty
    -- with a region's constant x and y was measured to vary inside it)
    hash = "sin(rx * " .. num(SC.hash.a) .. " + ry * " .. num(SC.hash.b) .. " + " .. num(N.seed) .. " + " ..
      num(SC.hash.seed_gain) .. " * map_seed_small) * " .. num(SC.hash.gain),
    draw = "hash - floor(hash)",
    bar = "1 - (1 - " .. level_share(res) .. ") * ramp * (1 - " .. N.province .. ")",
  }
  -- a bar of 1 (off, or a region touching the near disc) keeps the region whatever the draw
  def(N.keep, "max(bar >= 1, draw < bar)", KL)
end

-- The factor of a row's ore per tile (hotspots_v3 rich): pairs of {factor, largest scale it applies at, 0 for every
-- scale}, multiplied.
local function rich_factor(pairs3)
  local factor = {}
  for _, f in ipairs(pairs3) do
    local at = "(1 + " .. num(f[1] - 1) .. " * (" .. S .. " <= " .. num(f[2]) .. "))"
    factor[#factor + 1] = f[2] > 0 and at or num(f[1])
  end
  return table.concat(factor, " * ")
end

-- A resource's per-tile body: 1, plus each factored row's factor less 1 inside its footprint.
local function rich_body(h)
  local terms = {"1"}
  for _, r in ipairs(rows_of(nil, h.resource)) do
    local pairs3 = V.rich and V.rich[r.id]
    if pairs3 then
      terms[#terms + 1] = "(" .. rich_factor(pairs3) .. " - 1) * (" .. DEPTH .. r.id .. SUFFIX .. " > " ..
        num(r.radius_px) .. " * " .. S .. " - " .. footprint(r) .. ")"
    end
  end
  return table.concat(terms, " + ")
end

-- The third hotspot table's bodies (config.lua hotspots_v3, 0.3.1): the same method on the rows of
-- prototypes/hotspot_rows_v3.lua, under new names. V and its index are rebound to those rows; nothing above reads
-- them after this point.
local function third_table()
  V = require("prototypes.hotspot_rows_v3")
  for id in pairs(BY_ID) do
    BY_ID[id] = nil
  end
  for _, r in ipairs(V.rows) do
    BY_ID[r.id] = r
  end
  for _, h in ipairs(HC.resources) do
    local name = H3.bodies[h.resource]
    if name then
      v3_bodies(h, name, H3.parts[h.resource])
      -- ore per tile raised on a factored row's footprint, 1 elsewhere (data-final-fixes.lua richness reads it)
      if H3.rich_body[h.resource] then
        def(H3.rich_body[h.resource], rich_body(h))
      end
    end
  end
  gap_body(H3.gap)
  local trimmed3 = trimmed_list(H3.bodies)
  open_v2(OT.open_v3, OT.margin, OT.floor, trimmed3)
  open_v2(OT.plants.open_v3, OT.plants.margin, OT.plants.floor, trimmed3)
end
third_table()

-- The start fade and the scale bonus (config.lua hotspots_v4, 1.2.0): the third table's rows (V stays rebound to them)
-- under the solid ores' fifth bodies, and the trees' shares that follow those bodies.
local function fourth_bodies()
  def(H4.terms.fade, OC.fade("distance"))
  for _, h in ipairs(HC.resources) do
    local name = H4.bodies[h.resource]
    if name then
      v3_bodies(h, name, H4.parts[h.resource], true)
    end
  end
  -- crude oil on the solid rule (hotspots_v4.oil): its L, its wells' yield per tile and its own fits
  local O = H4.oil
  for _, h in ipairs(HC.resources) do
    if h.resource == "crude-oil" then
      v3_bodies(h, O.body, {qty = O.qty}, {near = O.near, area_fit = O.area_fit, density = O.density, blob = O.blob,
                                           large = OC.oil_large(h), well = OC.oil_well_base(h) .. " * " ..
                                             OC.oil_factor()})
    end
  end
  local trimmed4 = trimmed_list(H4.bodies)
  open_v2(OT.open_v5, OT.margin, OT.floor, trimmed4)
  open_v2(OT.plants.open_v5, OT.plants.margin, OT.plants.floor, trimmed4)
end
fourth_bodies()

-- A row's footprint at the fine scale, as footprint() reads it at scale 1: a row that touches a carrier there
-- touches it at no larger scale.
local function fine_footprint(r)
  local R = math.min(math.max(r.radius_px, HC.floor_tiles), r.cap_px)
  return r.least_tiles and math.max(r.least_tiles, R) or R
end

-- A lean near body's radius and height (hotspots_v5.near): a cone of near_plateau times the peak cap's height reads
-- the capped ore per tile (a well's capped yield over the wells' density, for crude oil) inside 1 - 1 / near_plateau
-- of its radius and falls to 0 at its edge, so near_total is that ore per tile times pi r^2 times
-- 1 - q + q^2 / cone_factor, q = 1 / near_plateau (the capped top's share of the disc, the cone's volume below it).
local function near_radius(oil)
  local F = H4.fade
  local q = 1 / H5.near_plateau
  local share = 1 - q + q * q / SP.cone_factor
  local top = oil and (oil.rich_fit * F.peak * H5.near_well * oil.density) or
    (V3.rich_fit * F.peak_fit * F.peak * H5.near_per_tile)
  local total = oil and H5.oil_near_total or H5.near_total
  return math.sqrt(total / (top * math.pi * share))
end
local function near_body(h, oil)
  return {name = H5.near[h.resource], radius = near_radius(oil),
          height = H5.near_plateau * H4.fade.peak * OC.body_height(h)}
end

-- A hotspot row's site: its centre, and the jitter radius in reference pixels regions.lua moves it by per seed (the
-- first table's rows carry neither: hotspots_v5.sites holds theirs).
local function site(r)
  local lat, lon, jitter = r.lat, r.lon, r.jitter_km
  if not lat and H5.sites[r.id] then
    lat, lon, jitter = table.unpack(H5.sites[r.id])
  end
  return lat and {lat = lat, lon = lon, jitter = (jitter or 0) * H5.jitter_px_per_km} or nil
end

-- The near bodies' pairs, map by map (a row stands on the maps that adopt it): each row lists every stronger row
-- (by strength, the table's order between equals) of its ore or a declared rival that it can touch at some scale and
-- size slider: where their footprints and `touch` tiles do at the fine scale, or where their near bodies at the
-- largest size slider, moved toward each other by both jitter radii, come within `touch` tiles (the distance at which
-- wells read as one field). A row holds no near body where it touches a listed row at the save's scale and size, so
-- no two near bodies of one ore, or of rivals, ever stand together; a row of a chain can lose its body to a
-- stronger row that lost its own.
local function rivals_of(a, b)
  for _, x in ipairs(V.rivals[a.id] or {}) do
    if x == b.id then
      return true
    end
  end
  for _, x in ipairs(V.rivals[b.id] or {}) do
    if x == a.id then
      return true
    end
  end
  return false
end
local function stronger_touching(rows, radius)
  local PXD = cfg.coordinates.px_per_degree
  local most = H5.size_max ^ V3.cube_root
  local order = {}
  for i, r in ipairs(rows) do
    order[#order + 1] = {i = i, r = r}
  end
  table.sort(order, function(x, y)
    local sx, sy = x.r.strength or 0, y.r.strength or 0
    if sx ~= sy then
      return sx > sy
    end
    return x.i < y.i
  end)
  local touching = {}
  for n, ea in ipairs(order) do
    local a = ea.r
    -- (a row with no site would pass every test unread, so it stops the data stage instead)
    local sa = site(a) or error("hotspot row " .. a.id .. " has no site for the near bodies' test")
    local list = {}
    for m = 1, n - 1 do
      local b = order[m].r
      if (a.resource == b.resource or rivals_of(a, b)) and not a.offshore and not b.offshore then
        local sb = site(b)
        local d = math.sqrt((sa.lon - sb.lon) ^ 2 + (sa.lat - sb.lat) ^ 2) * PXD
        local j = sa.jitter + sb.jitter
        local ra, rb = radius(a.resource), radius(b.resource)
        if d < fine_footprint(a) + fine_footprint(b) + H5.touch or d - j < (ra + rb) * most + H5.touch then
          list[#list + 1] = {id = b.id, d = d, j = j, ra = ra, rb = rb}
        end
      end
    end
    touching[a.id] = #list > 0 and list or nil
  end
  return touching
end
local function carrier_lists(O)
  local r_solid, r_oil = near_radius(), near_radius(O)
  local function radius(resource)
    return resource == "crude-oil" and r_oil or r_solid
  end
  local by_map_key = {}
  for _, M in ipairs(MAPS) do
    by_map_key[M.key] = stronger_touching(rows_of(M.key, nil), radius)
  end
  return by_map_key
end

local function fifth_bodies()
  local O = H4.oil
  local touching = carrier_lists(O)
  def(H5.rich_body.stone, "1 + (" .. H3.rich_body.stone .. " - 1) * " .. H4.terms.fade)
  for _, h in ipairs(HC.resources) do
    local name = H5.bodies[h.resource]
    if name then
      v3_bodies(h, name, H5.parts[h.resource], {near = H4.fade.near, large_only = true,
                                                 lean = {near_pt = H5.near_per_tile, unit = H5.unit[h.resource],
                                                         touching = touching, near_body = near_body(h)}})
    elseif h.resource == "crude-oil" then
      v3_bodies(h, H5.oil.body, {qty = H5.oil.qty},
                {near = O.near, area_fit = O.area_fit, density = O.density, blob = O.blob, oil = true,
                 large_only = true, large = OC.oil_large(h), well = OC.oil_well_base(h) .. " * " .. OC.oil_factor(),
                 lean = {near_pt = O.density * H5.near_well, unit = H5.unit[h.resource], touching = touching,
                         near_body = near_body(h, O)}})
    end
  end
  local trimmed5 = trimmed_list(H5.bodies)
  open_v2(OT.open_v6, OT.margin, OT.floor, trimmed5)
  open_v2(OT.plants.open_v6, OT.plants.margin, OT.plants.floor, trimmed5)
end
fifth_bodies()

data:extend(E)
