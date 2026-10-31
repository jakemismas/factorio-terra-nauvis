-- The region layer (ARCHITECTURE.md, "Region layer"; S10 design (d), design notes 07:45; milestone region-layer).
--
-- Every row of prototypes/tables/regions.lua becomes three named expressions, in reference pixels of
-- the region frame (config.lua regions.frame):
--   row.sd .. id .. suffix      the signed distance to the row's shape, positive inside, at the query
--                               point moved by the row's share of the shared warp, plus the shared
--                               edge roughness
--   row.w .. id .. suffix       the membership weight clamp(mid + sd / width, 0, 1), the soft edge
--   row.depth .. id .. suffix   the same signed distance in tiles
-- A marsh row's signed distance also reads the marsh outline noise and its weight a wider ramp (config.lua
-- regions.marsh), so no marsh shows its exact disc or path.
-- A hotspot row's disc sits at its adopted centre moved per seed by up to its jitter radius (S6's
-- linear fold of map_seed: constants only, so it folds the same on every peer); row.hu and row.hv
-- name that centre. The destroyed zone's polygon moves each vertex by the same fold (seeded_polygon).
-- Each layer's rows on a map make the layer's aggregates, the interface consumers
-- read (names in config.lua regions.names):
--   destroyed_sd, _w, _depth          min(max(include sd), -exclude sd, ...): exclusion rows (warp 0)
--                                     keep protected features out of the zone whatever the warp does
--   forest_w, forest_sum, tree_mult   the largest forest weight; the sum of boost times weight;
--                                     1 + forest_boost * forest_sum
--   marsh_w                           the largest marsh weight
--   hotspot_w, enemy_mult             the largest hotspot weight; 1 + the sum of (mult - 1) * weight
--
-- The query point is each map's own coordinate chain moved into the region frame by the map's
-- whole-pixel offset, so every row sits at its geography on every map and at every scale. The warp
-- and the roughness are anchored to the same frame: each octave is a basis_noise whose offsets make it
-- read the frame's reference pixels, so a seed's soft edges are one field in geography, the same on
-- every map, at every scale and for every spawn city. S10's octaves are built one by one because
-- 2.1.23's multioctave_noise offsets do not shift its input as basis_noise's do (measured in this
-- milestone); the weights are multioctave_noise's own (the coarsest 1, each finer persistence times the
-- last, over their root sum of squares). The per-save map number picks the map's chain, offsets and
-- rows, so each choice folds to one map's (U5: an if() on a folded number, never a per-tile
-- condition). The layer reads only x, y, map_seed and per-save constants through the chain, so it is
-- firewall-clean (S10 1.6) and the Entity program may read it. With no consumer nothing here compiles
-- (unreferenced expressions are free, R6 Q4). tn_map has no prototype: consumers are preset-only
--.
--
-- One named expression per quantity (A-7; S10: a copy under another name costs about +646): every
-- consumer reads these names, and a T16 static row fails any region formula outside this file.
local cfg = require("prototypes.config")
local T = require("prototypes.tables.regions")

local R = cfg.regions
local N = R.names
local K = cfg.keys
local SUF = N.suffix
local W = R.warp
local RO = R.rough
local JT = R.jitter

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- name minus a constant, and name plus one, spelled without a double sign
local function minus(name, c)
  if c == 0 then
    return name
  end
  if c < 0 then
    return name .. " + " .. num(-c)
  end
  return name .. " - " .. num(c)
end
local function plus(name, c)
  return minus(name, -c)
end

-- The region frame and each map's whole-pixel offset into it (u_frame = u_map + du).
local F = cfg.maps[R.frame]
local PPD = cfg.coordinates.px_per_degree

local function whole(v, what)
  local r = math.floor(v + 1 / 2)
  if math.abs(v - r) > R.frame_tolerance_px then
    error(cfg.identity.title .. " regions: " .. what .. " is not a whole pixel from " .. R.frame .. "'s raster")
  end
  return r
end

local MAPS = {}
for _, key in ipairs(cfg.map_order) do
  -- the geography version config.lua's layer_chain_geo names for the map, the chain the layer was
  -- registered against; every later version keeps that frame (the same city offset under names of its
  -- own), so its preset worlds read the same values here through the frozen offset fallbacks
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
                       du = whole((m.lon_left_edge - F.lon_left_edge) * PPD, key .. " u"),
                       dv = whole((F.lat_top_edge - m.lat_top_edge) * PPD, key .. " v")}
  end
end

local function to_px(lat, lon)
  return (lon - F.lon_left_edge) * PPD - 1 / 2, (F.lat_top_edge - lat) * PPD - 1 / 2
end

-- One text per map, folded on the per-save map number: if(map == id1, t1, if(map == id2, t2, t3)).
-- A text the same on every map needs no fold.
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

local function joined(fn, parts, empty)
  if #parts == 0 then
    return empty
  end
  if #parts == 1 then
    return parts[1]
  end
  if #parts > R.max_arguments then
    error(cfg.identity.title .. " regions: " .. fn .. " over " .. #parts .. " rows exceeds the noise language's limit")
  end
  return fn .. "(" .. table.concat(parts, ", ") .. ")"
end

-- The query point: the map's chain moved into the frame (unwarped).
local QU, QV = N.u .. SUF, N.v .. SUF
def(QU, by_map(function(M) return plus(M.g.u, M.du) end))
def(QV, by_map(function(M) return plus(M.g.v, M.dv) end))

-- The noise anchor: offsets that make a noise read the frame's reference pixels, (u - frame wr) at the
-- frame map's own origin, whatever the map, the scale and the spawn city. The noise calls keep x = x,
-- y = y with the shift in offset_x and offset_y (A-12); these fold to constants per save.
local corner = "floor(" .. K.scale .. " / " .. num(cfg.coordinates.corner_offset_divisor) .. ")"
local function anchor(c_name, radius, frame_radius, d)
  local k = radius + d - frame_radius
  local text = c_name .. " - " .. corner
  if k > 0 then
    text = text .. " + " .. K.scale .. " * " .. num(k)
  elseif k < 0 then
    text = text .. " - " .. K.scale .. " * " .. num(-k)
  end
  return text
end
def(N.ox, by_map(function(M) return anchor(M.g.cx, M.m.wr, F.wr, M.du) end))
def(N.oy, by_map(function(M) return anchor(M.g.cy, M.m.hr, F.hr, M.dv) end))

-- One octave: basis noise at wavelength_px times 2^k reference pixels, shifted along x by its index
-- times octave_shift_px so the octaves of one seed1 never share a lattice zero.
local function octave(seed1, P, k, j)
  local ox = N.ox
  if j > 0 then
    ox = ox .. " + " .. K.scale .. " * " .. num(j * R.octave_shift_px)
  end
  return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = 1 / (" ..
    num(P.wavelength_px * 2 ^ k) .. " * " .. K.scale .. "), output_scale = 1, offset_x = " .. ox .. ", offset_y = " ..
    N.oy .. "}"
end

-- S10's multi-octave noise from its octaves: the coarsest first at weight 1, each finer persistence
-- times the last, normalized by the root sum of the squared weights (multioctave_noise's weights).
local function noise(seed1, P)
  local parts, norm = {}, 0
  for j = 0, P.octaves - 1 do
    local w = P.persistence ^ j
    norm = norm + w * w
    parts[#parts + 1] = num(w) .. " * " .. octave(seed1, P, P.octaves - 1 - j, j)
  end
  return "(" .. table.concat(parts, " + ") .. ") / " .. num(math.sqrt(norm))
end

-- The shared warp: two noises, the displacement vector clamped to clamp_px in length, so a row's
-- edge moves at most its share of clamp_px plus the roughness clamp from its shape (S10: 27 px).
def(N.ax, num(W.amplitude_px) .. " * " .. noise(W.seed1_x, W))
def(N.ay, num(W.amplitude_px) .. " * " .. noise(W.seed1_y, W))
def(N.wk, num(W.clamp_px) .. " / max(" .. num(W.clamp_px) .. ", sqrt(" .. N.ax .. " * " .. N.ax .. " + " .. N.ay ..
  " * " .. N.ay .. "))")
def(N.wx, N.ax .. " * " .. N.wk)
def(N.wy, N.ay .. " * " .. N.wk)
-- The shared edge roughness, added to every signed distance.
def(N.rough, "clamp(" .. num(RO.amplitude_px) .. " * " .. noise(RO.seed1, RO) .. ", " .. num(-RO.clamp_px) .. ", " ..
  num(RO.clamp_px) .. ")")

-- The query point for a warp share: unwarped at 0, the full warp at 1, a share of it between.
local made = {}
local function query(share)
  local h = math.floor(share * R.share_hundredths + 1 / 2)
  if h == 0 then
    return QU, QV
  end
  local u, v = N.u .. N.share .. h .. SUF, N.v .. N.share .. h .. SUF
  if not made[h] then
    made[h] = true
    if h == R.share_hundredths then
      def(u, QU .. " + " .. N.wx)
      def(v, QV .. " + " .. N.wy)
    else
      def(u, QU .. " + " .. num(share) .. " * " .. N.wx)
      def(v, QV .. " + " .. num(share) .. " * " .. N.wy)
    end
  end
  return u, v
end

-- A hotspot's centre coordinate: base + (2 * frac(seed fold + phase) - 1) * reach, where the reach is
-- the jitter radius over sqrt(2), so the jitter box stays inside the jitter radius (S6).
local function jittered(base, mult, phase, reach)
  return num(base) .. " + (2 * ((map_seed_small * " .. num(mult) .. " + floor(map_seed_normalized * " ..
    num(JT.high_bits) .. ") * " .. num(JT.mult_high) .. " + " .. num(phase) .. ") % 1) - 1) * " .. num(reach)
end

-- The signed distance of a shape at (qu, qv), with its locals. A disc's centre is a number, or the
-- name of a hotspot's jittered centre.
local function from(q, c)
  if type(c) == "number" then
    return minus(q, c)
  end
  return q .. " - " .. c
end

local function disc(cu, cv, r, qu, qv)
  return num(r) .. " - sqrt(du * du + dv * dv)", {du = from(qu, cu), dv = from(qv, cv)}
end

local function lines(pts, qu, qv, closed)
  local L, d2s, cross, n = {}, {}, {}, #pts
  for i = 1, closed and n or n - 1 do
    local a, b = pts[i], pts[i % n + 1]
    local ex, ey = b[1] - a[1], b[2] - a[2]
    local s = tostring(i)
    L["du" .. s] = minus(qu, a[1])
    L["dv" .. s] = minus(qv, a[2])
    L["t" .. s] = "clamp((du" .. s .. " * " .. num(ex) .. " + dv" .. s .. " * " .. num(ey) .. ") * " ..
      num(1 / (ex * ex + ey * ey)) .. ", 0, 1)"
    L["qx" .. s] = "du" .. s .. " - t" .. s .. " * " .. num(ex)
    L["qy" .. s] = "dv" .. s .. " - t" .. s .. " * " .. num(ey)
    d2s[#d2s + 1] = "qx" .. s .. " * qx" .. s .. " + qy" .. s .. " * qy" .. s
    if closed and ey ~= 0 then
      -- the edge straddles the point's row and crosses it to the right (the crossing number)
      cross[#cross + 1] = "((" .. qv .. " < " .. num(a[2]) .. ") != (" .. qv .. " < " .. num(b[2]) .. ")) * (" ..
        qu .. " < " .. num(a[1]) .. " + dv" .. s .. " * " .. num(ex / ey) .. ")"
    end
  end
  L.d2 = joined("min", d2s, nil)
  return L, cross
end

local function polygon(pts, qu, qv)
  local L, cross = lines(pts, qu, qv, true)
  L.inside = "(" .. table.concat(cross, " + ") .. ") % 2"
  return "(2 * inside - 1) * sqrt(d2)", L
end

-- A polygon whose every vertex moves per seed by up to its own jitter radius: polygon()'s formulas with the
-- vertices and edges as locals, which are constants per save and fold, so the program costs what a fixed
-- polygon of as many vertices costs. Each vertex has its own multipliers, so a seed moves the vertices
-- independently. An edge whose two ends land on one row has no crossing, so its slope is never read.
local function seeded_polygon(pts, r, qu, qv)
  local L, d2s, cross, n = {}, {}, {}, #pts
  for i, p in ipairs(pts) do
    local s = tostring(i)
    local reach = r.vertex_jitter_km[i] / R.km_per_px / math.sqrt(2)
    local step = i * JT.vertex_step
    L["au" .. s] = jittered(p[1], (JT.mult_x + step) % 1, r.vertex_phase[i], reach)
    L["av" .. s] = jittered(p[2], (JT.mult_y + step) % 1, r.vertex_phase[i], reach)
  end
  for i = 1, n do
    local s, e = tostring(i), tostring(i % n + 1)
    local ex, ey = "ex" .. s, "ey" .. s
    L[ex] = "au" .. e .. " - au" .. s
    L[ey] = "av" .. e .. " - av" .. s
    L["du" .. s] = qu .. " - au" .. s
    L["dv" .. s] = qv .. " - av" .. s
    L["t" .. s] = "clamp((du" .. s .. " * " .. ex .. " + dv" .. s .. " * " .. ey .. ") / (" .. ex .. " * " .. ex ..
      " + " .. ey .. " * " .. ey .. "), 0, 1)"
    L["qx" .. s] = "du" .. s .. " - t" .. s .. " * " .. ex
    L["qy" .. s] = "dv" .. s .. " - t" .. s .. " * " .. ey
    L["sl" .. s] = "if(abs(" .. ey .. ") < " .. num(JT.flat_px) .. ", 0, " .. ex .. " / " .. ey .. ")"
    d2s[#d2s + 1] = "qx" .. s .. " * qx" .. s .. " + qy" .. s .. " * qy" .. s
    cross[#cross + 1] = "((" .. qv .. " < av" .. s .. ") != (" .. qv .. " < av" .. e .. ")) * (" .. qu .. " < au" ..
      s .. " + dv" .. s .. " * sl" .. s .. ")"
  end
  L.d2 = joined("min", d2s, nil)
  L.inside = "(" .. table.concat(cross, " + ") .. ") % 2"
  return "(2 * inside - 1) * sqrt(d2)", L
end

local function path(pts, r, qu, qv)
  local L = lines(pts, qu, qv, false)
  return num(r) .. " - sqrt(d2)", L
end

local function row_names(r)
  local rn = N.row
  return {sd = rn.sd .. r.id .. SUF, w = rn.w .. r.id .. SUF, depth = rn.depth .. r.id .. SUF,
          hu = rn.hu .. r.id .. SUF, hv = rn.hv .. r.id .. SUF}
end

local function weight(sd_name, width_px)
  return "clamp(" .. num(R.ramp.mid) .. " + " .. sd_name .. " / " .. num(width_px or R.ramp.width_px) .. ", 0, 1)"
end

-- A marsh's own edge (config.lua regions.marsh): the one outline noise every marsh row reads at its
-- own amplitude, and the row's wider ramp, both from the row's radius in reference pixels.
local MH = R.marsh
def(N.marsh_rough, noise(MH.seed1, MH))

local function marsh_edge(r)
  local radius = r.radius_km / R.km_per_px
  local ramp = math.min(MH.ramp_cap_px, MH.ramp_share * radius)
  return math.min(MH.cap_px, MH.share * radius), math.max(R.ramp.width_px, ramp)
end

-- A marsh row's gain on the shared roughness (config.lua regions.marsh.edge_gain), folded on the map.
local function marsh_gain(r)
  local G = MH.edge_gain
  local gain = math.min(G.top, math.max(MH.rough_gain, G.share * r.radius_km / R.km_per_px))
  return by_map(function(M) return num(G.maps[M.key] and gain or MH.rough_gain) end)
end

-- Every row: its signed distance, weight and depth (and a hotspot's jittered centre).
local ROWS = {}
for _, r in ipairs(T.rows) do
  local nm = row_names(r)
  local qu, qv = query(r.warp)
  local text, L
  if r.shape == "disc" then
    local cu, cv = to_px(r.lat, r.lon)
    if r.layer == "hotspot" then
      local reach = r.jitter_km / R.km_per_px / math.sqrt(2)
      def(nm.hu, jittered(cu, JT.mult_x, r.phase, reach))
      def(nm.hv, jittered(cv, JT.mult_y, r.phase, reach))
      text, L = disc(nm.hu, nm.hv, r.radius_km / R.km_per_px, qu, qv)
    else
      text, L = disc(cu, cv, r.radius_km / R.km_per_px, qu, qv)
    end
  else
    local pts = {}
    for i, ll in ipairs(r.latlon) do
      local u, v = to_px(ll[1], ll[2])
      pts[i] = {u, v}
    end
    if r.vertex_jitter_km then
      text, L = seeded_polygon(pts, r, qu, qv)
    elseif r.shape == "polygon" then
      text, L = polygon(pts, qu, qv)
    else
      text, L = path(pts, r.radius_km / R.km_per_px, qu, qv)
    end
  end
  if r.layer == "marsh" then
    local amplitude, width = marsh_edge(r)
    def(nm.sd, "(" .. text .. ") + (" .. marsh_gain(r) .. ") * " .. N.rough .. " + " .. num(amplitude) .. " * (" ..
      N.marsh_rough .. " + " .. num(MH.bias) .. ")", L)
    def(nm.w, weight(nm.sd, width))
  else
    def(nm.sd, "(" .. text .. ") + " .. N.rough, L)
    def(nm.w, weight(nm.sd))
  end
  def(nm.depth, nm.sd .. " * " .. K.scale)
  ROWS[#ROWS + 1] = {row = r, names = nm}
end

-- A map's rows of a layer (and of a destroyed mode).
local function on_map(M, layer, mode)
  local out = {}
  for _, x in ipairs(ROWS) do
    local r = x.row
    if r.layer == layer and (mode == nil or (r.mode or "include") == mode) then
      for _, mk in ipairs(r.maps) do
        if mk == M.key then
          out[#out + 1] = x
          break
        end
      end
    end
  end
  return out
end

local function each(list, fn)
  local out = {}
  for _, x in ipairs(list) do
    out[#out + 1] = fn(x)
  end
  return out
end

-- The destroyed zone.
def(N.destroyed_sd, by_map(function(M)
  local inc = joined("max", each(on_map(M, "destroyed", "include"), function(x) return x.names.sd end), "-inf")
  local parts = {inc}
  for _, x in ipairs(on_map(M, "destroyed", "exclude")) do
    parts[#parts + 1] = "-" .. x.names.sd
  end
  return joined("min", parts, inc)
end))
def(N.destroyed_w, weight(N.destroyed_sd))
def(N.destroyed_depth, N.destroyed_sd .. " * " .. K.scale)

-- Great forests.
local function boosted(x)
  if x.row.boost == 1 then
    return x.names.w
  end
  return num(x.row.boost) .. " * " .. x.names.w
end
def(N.forest_w, by_map(function(M) return joined("max", each(on_map(M, "forest"), function(x) return x.names.w end),
  "0") end))
def(N.forest_sum, by_map(function(M)
  local terms = each(on_map(M, "forest"), boosted)
  return #terms > 0 and table.concat(terms, " + ") or "0"
end))
def(N.tree_mult, "1 + " .. num(R.forest_boost) .. " * " .. N.forest_sum)

-- Marshes.
def(N.marsh_w, by_map(function(M) return joined("max", each(on_map(M, "marsh"), function(x) return x.names.w end),
  "0") end))

-- Hotspot regions and the biter multiplier inside them.
def(N.hotspot_w, by_map(function(M) return joined("max", each(on_map(M, "hotspot"), function(x) return x.names.w end),
  "0") end))
def(N.enemy_mult, by_map(function(M)
  local terms = each(on_map(M, "hotspot"), function(x) return num(x.row.mult - 1) .. " * " .. x.names.w end)
  return "1" .. (#terms > 0 and (" + " .. table.concat(terms, " + ")) or "")
end))

data:extend(E)
