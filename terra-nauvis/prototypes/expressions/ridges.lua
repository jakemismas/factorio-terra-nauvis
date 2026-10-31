-- Ridges (ARCHITECTURE.md, milestone contract 8; S5; APPROVALS 5 and 11; milestone ridges; design notes 2026-10-30,
-- ridges that read as mountains).
--
-- Every range of prototypes/tables/ranges.lua (tools/build_ranges.py writes it from the approval data,
-- R7b and the vertex heights) becomes a messy band of cliffs around its crest polyline, written in
-- contour units so the cliffs slider is inert (S5):
--   cliff_elevation = cliff_elevation_0 + cliff_elevation_interval * clamp(1 + h, low, high)
--   cliffiness = cliffiness_on * (1 - opening) outside the ridge-free start disc, 0 inside it
-- never read cliff_richness, so continuity and richness have nothing to act on, and contours stand at
-- whole h whatever the frequency slider makes the interval. The clamp leaves one contour, the ridge's
-- edge at h = 0 with its high side inward, because more ran parallel to it as ranks. On each map:
--   depth    tiles inside the ridge: per crest segment the half-width at the tile's nearest crest point
--            (from the vertex heights, so wider where the mountain is taller, and below zero at a
--            crest's ends) times the run multiplier, minus the distance to that point; the largest
--            over the segments. Distances read the wandering axis, the map's chain pushed about by
--            slow noise, so a ridge wanders round its range's axis and never runs straight
--   run      the width's multiplier, slow noise: a ridge swells, thins and at 0 is gone, so it breaks
--            into runs that taper out instead of closing round their ends
--   h        (depth - bias) / ramp + fray: the fray moves the edge by up to about ramp tiles times its
--            amplitude along the strike, so a line never holds to one lattice row
--   opening  a slot across the crest at a pass or an unnamed gap (pass_tiles along the crest, past the
--            ridge's half-width to each side), moving with the wandering axis; where a range cut by the
--            map's edge has no pass on that map, a band along the edge near the crossing, so the ridge
--            stops short of the edge (APPROVALS 5); or a noise gap, more of them the thinner the ridge,
--            so a line breaks into cliffs of many lengths and a thin stretch frays into scattered ones
--   keep     1 at a slot, 0 past collar_tiles: it pulls the run to 1 and shuts the noise gaps, so round
--            a slot the ridge stands at its true width, a pass reads as a doorway in a wall and not as
--            one more gap, and the slot reaches right across the ridge
-- The bodies a preset names through a key, as tn_land_coarse is: the crest (h) and the openings, which
-- only the Cliff program reads, and the crest band (tn_band) the ore clearance reads in the Entity
-- program, a cheap superset of the tiles whose centre lies within ore_clear_tiles of the unwandered
-- crest (read at the centre, where an ore entity stands, not at the integer corner the program samples;
-- an exact distance there measured Entity +3,028 on Europe against the milestone's +2,000 allocation; this
-- milestone's design notes). Ore clears the axis only: where a ridge wanders off it an ore patch can take a
-- cliff out, which reads as one more gap. All read the map's own coordinate chain, so they are
-- firewall-clean. Shared bodies: the effective height, which the ridges toggle (a name switch to tn_one
-- or tn_zero) turns into -inf when off, so nothing of a ridge compiles and no cliff is placed (S5: a
-- constant field places none); the ridge-free start disc (D25 wins inside it); the two cliff
-- properties; and the ore clearance that data-final-fixes.lua multiplies into every Earth ore
-- probability, without a global cliff_removal_probability edit. Every noise reads the
-- frame's geo tiles, so a seed's ridges are one shape for every spawn city; only the Cliff program pays
-- for the noise, on the 4-tile lattice (S5). Every name and number comes from config.lua (S-5); the
-- toggle never multiplies (U5).
--
-- The highlands (a cliff squiggle on plain grass does not read as a mountain range; design notes
-- 18:00): a band round each range, wider and stronger the taller the range, faded in outside the ridge-free
-- start disc, frayed by noise the region layer already computes. It costs only what it reads again:
--   rocks    in the Entity program, on the crest band's own pieces and one reach per piece: lifts rock_density
--            as the three big vanilla rocks read it and Alien Biomes' big rocks by a hook, outside the openings
--   tiles    in the Tile program, at the wandering point with a reach that follows the vertex heights: lifts the
--            stony vanilla tiles' score and, beside Alien Biomes, lowers the tile temperature and moisture, so
--            the top of a tall range turns to Alien Biomes' grey ground and snow. Trees and decoratives keep the
--            plain fields
local cfg = require("prototypes.config")
local T = require("prototypes.tables.ranges")

local RD = cfg.ridges
local N = RD.names
local K = cfg.keys
local SW = cfg.toggles.ridges
local PPD = cfg.coordinates.px_per_degree

local function num(v)
  return string.format(cfg.number_format, v)
end

-- name minus a constant, spelled without a double sign
local function minus(name, c)
  if c < 0 then
    return name .. " + " .. num(-c)
  end
  return name .. " - " .. num(c)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- f(a, b, ...) over many parts, as a tree when they exceed the noise language's argument limit.
local function joined(fn, parts, empty)
  if #parts == 0 then
    return empty
  end
  if #parts == 1 then
    return parts[1]
  end
  if #parts <= RD.max_arguments then
    return fn .. "(" .. table.concat(parts, ", ") .. ")"
  end
  local groups, cur = {}, {}
  for _, p in ipairs(parts) do
    cur[#cur + 1] = p
    if #cur == RD.max_arguments then
      groups[#groups + 1] = fn .. "(" .. table.concat(cur, ", ") .. ")"
      cur = {}
    end
  end
  if #cur > 0 then
    groups[#groups + 1] = joined(fn, cur, empty)
  end
  return joined(fn, groups, empty)
end

-- A map's chain coordinates of a table point: pixel centres at integer u, v (ARCHITECTURE.md, "The
-- coordinate chain"), so the tile holding a pixel centre reads that centre.
local function to_px(m, lat, lon)
  return (lon - m.lon_left_edge) * PPD - 1 / 2, (m.lat_top_edge - lat) * PPD - 1 / 2
end

local function on_map(list, key)
  for _, k in ipairs(list or {}) do
    if k == key then
      return true
    end
  end
  return false
end

local S = K.scale
local scale2 = S .. " * " .. S

-- A vertex's half-width in tiles from its height; a crest's end vertices sit below zero, so the ridge
-- narrows to nothing on its last segment and frays out instead of closing round its end.
local function half_width(height, tip)
  if tip then
    return RD.width.tip_tiles
  end
  return RD.width.min_tiles + RD.width.gain_tiles * (height / RD.width.ref_m) ^ RD.width.power
end

-- The crest band of one run of consecutive kept segments (pts: chain px), as band terms of one piece
-- each: a piece is a run of segments monotone along one axis within band_max_angle_degrees of it,
-- longest first, and its term is 1 where the tile lies within the piece's half-height of the
-- piecewise-linear function f of that axis through the piece's vertices and within ore_clear_tiles
-- of its span. f = c + sum of slope * clamp(p, p0, p1) costs 3 operations per segment (the clamp
-- bounds fold with the scale), and the half-height ore_clear_tiles / cos(steepest angle) covers every
-- tile within ore_clear_tiles of a segment; beyond the span f stays flat, which covers the ends.
local MAXT = math.tan(math.rad(RD.band_max_angle_degrees))
local function band_pieces(pts, run)
  local out, i = {}, 1
  while i <= #run do
    local best
    for _, axis in ipairs({"x", "y"}) do
      local j, sign = i, nil
      while j <= #run do
        local a, b = pts[run[j]], pts[run[j] + 1]
        local c, o = b[1] - a[1], b[2] - a[2]
        if axis == "y" then
          c, o = o, c
        end
        local sg = c > 0
        if c == 0 or math.abs(o) > MAXT * math.abs(c) or (sign ~= nil and sg ~= sign) then
          break
        end
        sign = sg
        j = j + 1
      end
      if not best or j - i > best.n then
        best = {n = j - i, axis = axis}
      end
    end
    if best.n == 0 then
      -- a segment along no axis within the angle: band_max_angle_degrees is below half a right angle
      error(cfg.identity.title .. " ridges: band_max_angle_degrees leaves a segment on no axis")
    end
    out[#out + 1] = {axis = best.axis, first = i, last = i + best.n - 1}
    i = i + best.n
  end
  return out
end

-- A vertex's highland reach in reference pixels (config.lua ridges.high).
local function reach_px(height)
  local HG = RD.high
  return HG.min_px + HG.gain_px * (height / HG.ref_m) ^ HG.power
end

-- One band term (and its locals) for a piece; P and Q name the scaled axis and cross coordinates.
local function band_term(pts, run, piece, k, B, H, heights)
  local vs, tops = {}, {}
  for j = piece.first, piece.last do
    if j == piece.first then
      vs[#vs + 1] = pts[run[j]]
      tops[#tops + 1] = heights[run[j]]
    end
    vs[#vs + 1] = pts[run[j] + 1]
    tops[#tops + 1] = heights[run[j] + 1]
  end
  local p, q = "bu", "bv"
  local list = {}
  for n, v in ipairs(vs) do
    list[n] = piece.axis == "x" and {v[1], v[2], height = tops[n]} or {v[2], v[1], height = tops[n]}
  end
  if piece.axis == "y" then
    p, q = "bv", "bu"
  end
  if list[#list][1] < list[1][1] then
    local rev = {}
    for n = #list, 1, -1 do
      rev[#rev + 1] = list[n]
    end
    list = rev
  end
  local terms, c, steep = {}, list[1][2], 0
  -- the reach along the piece, the same clamps at the reach's own slopes
  local W, c2, sum, top, arc = {}, reach_px(list[1].height), list[1].height, list[1].height, 0
  for n = 2, #list do
    local a, b = list[n - 1], list[n]
    local slope = (b[2] - a[2]) / (b[1] - a[1])
    steep = math.max(steep, math.abs(slope))
    c = c - slope * a[1]
    local bounds = "clamp(" .. p .. ", " .. S .. " * " .. num(a[1]) .. ", " .. S .. " * " .. num(b[1]) .. ")"
    terms[#terms + 1] = num(slope) .. " * " .. bounds
    local rise = (reach_px(b.height) - reach_px(a.height)) / (b[1] - a[1])
    c2 = c2 - rise * a[1]
    W[#W + 1] = num(rise) .. " * " .. bounds
    sum, top = sum + b.height, math.max(top, b.height)
    arc = arc + (b[1] - a[1]) * math.sqrt(1 + slope * slope)
  end
  local half = RD.ore_clear_tiles * math.sqrt(1 + steep * steep)
  local mid, span = (list[1][1] + list[#list][1]) / 2, (list[#list][1] - list[1][1]) / 2
  local f = "f" .. k
  B[f] = S .. " * " .. num(c) .. " + " .. table.concat(terms, " + ")
  -- the piece's mean cosine, and its one reach for the Entity program: halfway between its mean vertex and its
  -- highest
  H[#H + 1] = {p = p, q = q, f = f, mid = mid, span = span, cos = 2 * span / arc, arc = arc,
               reach = reach_px((sum / #list + top) / 2),
               reach_text = S .. " * " .. num(c2) .. " + " .. table.concat(W, " + ")}
  return "(abs(" .. q .. " - " .. f .. ") < " .. num(half) .. ") * (abs(" .. p .. " - " .. S .. " * " .. num(mid) ..
    ") < " .. S .. " * " .. num(span) .. " + " .. num(RD.ore_clear_tiles) .. ")"
end

-- The crest segments of one range on a map, added to the crest body's locals and terms: each term is
-- the ridge's half-width at the tile's nearest crest point (from wide, tiles per vertex) minus the
-- distance to that point, so the largest term is how far inside the ridge the tile lies.
local function add_segments(C, pts, segs, wide)
  for _, i in ipairs(segs) do
    local a, b = pts[i], pts[i + 1]
    local dx, dy = b[1] - a[1], b[2] - a[2]
    local l2 = dx * dx + dy * dy
    if l2 > 0 then
      local s = tostring(#C.terms + 1)
      C.L["du" .. s] = minus(C.u, a[1])
      C.L["dv" .. s] = minus(C.v, a[2])
      C.L["t" .. s] = "clamp((du" .. s .. " * " .. num(dx) .. " + dv" .. s .. " * " .. num(dy) .. ") * " ..
        num(1 / l2) .. ", 0, 1)"
      C.L["qx" .. s] = "du" .. s .. " - t" .. s .. " * " .. num(dx)
      C.L["qy" .. s] = "dv" .. s .. " - t" .. s .. " * " .. num(dy)
      C.L["r" .. s] = S .. " * sqrt(qx" .. s .. " * qx" .. s .. " + qy" .. s .. " * qy" .. s .. ")"
      C.terms[#C.terms + 1] = "(" .. num(wide[i]) .. " + t" .. s .. " * " .. num(wide[i + 1] - wide[i]) .. ") * " ..
        C.run .. " - r" .. s
      C.near[#C.near + 1] = "r" .. s
    end
  end
end

-- One opening on a map: a slot across the crest at a pass or a gap; at an edge crossing, the tiles
-- within edge_tiles of the map's extent (its edges at -1/2 and W - 1/2 in this frame) and within
-- edge_reach_tiles of the crossing.
local function add_opening(O, m, pts, o, wide)
  local cu, cv = to_px(m, o.lat, o.lon)
  local a, b = pts[o.seg], pts[o.seg + 1]
  local dx, dy = b[1] - a[1], b[2] - a[2]
  local len = math.sqrt(dx * dx + dy * dy)
  -- across the crest the slot outreaches the ridge's half-width there, the collar holding the run at 1
  local along = len > 0 and math.max(0, math.min(1, ((cu - a[1]) * dx + (cv - a[2]) * dy) / (len * len))) or 0
  local reach = math.max(RD.reach_tiles, wide[o.seg] + along * (wide[o.seg + 1] - wide[o.seg]) + RD.reach_margin_tiles)
  if o.vertex and len > 0 then
    -- at an interior vertex: across the bisector of the incoming and the outgoing segment
    local p, q = pts[o.vertex - 1], pts[o.vertex]
    local ix, iy = q[1] - p[1], q[2] - p[2]
    local il = math.sqrt(ix * ix + iy * iy)
    if il > 0 then
      dx, dy = dx / len + ix / il, dy / len + iy / il
      len = math.sqrt(dx * dx + dy * dy)
    end
  end
  local s = tostring(#O.terms + 1)
  if RD.rocks.clear_kinds[o.kind] then
    O.named[#O.named + 1] = {cu, cv}
  end
  -- a pass moves with the wandering crest; an edge stays where the map's extent is
  local ou, ov = O.u, O.v
  if o.kind == "edge" then
    ou, ov = O.fixed_u, O.fixed_v
  end
  O.L["pu" .. s] = minus(ou, cu)
  O.L["pv" .. s] = minus(ov, cv)
  local pu, pv = "pu" .. s, "pv" .. s
  if o.kind == "edge" then
    O.L["ed" .. s] = "min(" .. ou .. " + 1 / 2, " .. num(m.width_px) .. " - 1 / 2 - " .. ou .. ", " .. ov ..
      " + 1 / 2, " .. num(m.height_px) .. " - 1 / 2 - " .. ov .. ")"
    O.terms[#O.terms + 1] = "(ed" .. s .. " * " .. S .. " < " .. num(RD.edge_tiles) .. ") * ((" .. pu .. " * " ..
      pu .. " + " .. pv .. " * " .. pv .. ") * " .. scale2 .. " < " .. num(RD.edge_reach_tiles ^ 2) .. ")"
  elseif len > 0 then
    -- along the crest, outward at a tip (the crest's end vertex): from pass_tiles / 2 inside it to
    -- tip_tiles past it, so the end cap goes too; elsewhere pass_tiles / 2 either side
    local tx, ty = dx / len, dy / len
    local slot = "abs(" .. pu .. " * " .. num(tx) .. " + " .. pv .. " * " .. num(ty) .. ") * " .. S .. " < " ..
      num(RD.pass_tiles / 2)
    if o.tip then
      tx, ty = tx * o.tip, ty * o.tip
      local lo, hi = -RD.pass_tiles / 2, RD.tip_tiles
      slot = "abs((" .. pu .. " * " .. num(tx) .. " + " .. pv .. " * " .. num(ty) .. ") * " .. S .. " - " ..
        num((lo + hi) / 2) .. ") < " .. num((hi - lo) / 2)
    end
    O.terms[#O.terms + 1] = "(" .. slot .. ") * (abs(" .. pv .. " * " .. num(tx) .. " - " .. pu .. " * " .. num(ty) ..
      ") * " .. S .. " < " .. num(reach) .. ")"
    -- the collar: the ridge stands whole round the slot, so a pass reads as a doorway and not one more gap
    O.keeps[#O.keeps + 1] = "clamp(1 - (" .. pu .. " * " .. pu .. " + " .. pv .. " * " .. pv .. ") * " .. scale2 ..
      " / " .. num(RD.collar_tiles ^ 2) .. ", 0, 1)"
  end
end

-- The crest band of one range on a map: its kept segments in runs of consecutive ones, each cut
-- into monotone pieces.
local function add_band(Bd, pts, segs, heights)
  local run = {}
  local function flush()
    if #run > 0 then
      for _, piece in ipairs(band_pieces(pts, run)) do
        Bd.terms[#Bd.terms + 1] = band_term(pts, run, piece, #Bd.terms + 1, Bd.L, Bd.pieces, heights)
      end
    end
    run = {}
  end
  for _, i in ipairs(segs) do
    if #run > 0 and i ~= run[#run] + 1 then
      flush()
    end
    run[#run + 1] = i
  end
  flush()
end

-- A segment the crest band reads: the ore clearance only reaches ore_clear_tiles, so a segment past
-- band_margin_px of the map's extent has no ore to clear, however far its cliffs reach.
local function in_band(m, a, b)
  local M = RD.band_margin_px
  return math.max(a[1], b[1]) >= -M and math.min(a[1], b[1]) < m.width_px + M and
    math.max(a[2], b[2]) >= -M and math.min(a[2], b[2]) < m.height_px + M
end

-- A map's highland reach and the named passes the rock lift keeps clear. The reach reads the crest band's
-- own pieces through the same locals, so in the Entity program the crest functions and the distance along
-- each piece cost nothing more: per piece the band is the largest reach less the wandering distance across
-- it, cut off past the piece's ends. Only the passes' squared distances cost per pass.
local function highland(key, Bd, O)
  local HG = RD.high
  local L = {wu = N.wander_u[key] .. " * " .. S .. " + " .. num(RD.centre_tiles),
             wv = N.wander_v[key] .. " * " .. S .. " + " .. num(RD.centre_tiles)}
  for k, v in pairs(Bd.L) do
    L[k] = v
  end
  local terms = {}
  for _, h in ipairs(Bd.pieces) do
    if h.arc >= RD.rocks.short_px then
      local reach = S .. " * " .. num(h.reach) .. " + " .. num(HG.rock_tiles) .. " / " .. S
      local wq = h.q == "bu" and "wu" or "wv"
      terms[#terms + 1] = "min(" .. reach .. " - abs(" .. wq .. " - " .. h.f .. "), " .. reach .. " + " .. S .. " * " ..
        num(h.span) .. " - abs(" .. h.p .. " - " .. S .. " * " .. num(h.mid) .. "))"
    end
  end
  def(N.high_map[key], joined("max", terms, "-inf"), L)
  -- The tiles pay for their own crest functions, so they read them at the wandering point itself, their reach
  -- follows the vertex heights, one local per piece, and a piece ends round: its box's corners drew flat-topped
  -- tabs of grey ground.
  local T2 = {}
  terms = {}
  for k, v in pairs(Bd.L) do
    T2[k] = v
  end
  T2.bu, T2.bv = L.wu, L.wv
  for k, h in ipairs(Bd.pieces) do
    local s = tostring(k)
    T2["a" .. s] = num(h.cos) .. " * abs(" .. h.q .. " - " .. h.f .. ")"
    T2["e" .. s] = "max(0, abs(" .. h.p .. " - " .. S .. " * " .. num(h.mid) .. ") - " .. S .. " * " .. num(h.span) ..
      ")"
    terms[k] = h.reach_text .. " - sqrt(a" .. s .. " * a" .. s .. " + e" .. s .. " * e" .. s .. ")"
  end
  def(N.high_tile_map[key], joined("max", terms, "-inf"), T2)
  local P, ds = {}, {}
  for i, c in ipairs(O.named) do
    local s = tostring(i)
    P["pu" .. s] = minus(O.u, c[1])
    P["pv" .. s] = minus(O.v, c[2])
    ds[i] = "pu" .. s .. " * pu" .. s .. " + pv" .. s .. " * pv" .. s
  end
  local R = RD.rocks
  local inner, outer = R.clear_tiles ^ 2, (R.clear_tiles + R.fade_tiles) ^ 2
  if #ds == 0 then
    def(N.passes[key], "1")
  else
    def(N.passes[key], "clamp((" .. joined("min", ds, "inf") .. ") * " .. scale2 .. " / " .. num(outer - inner) ..
      " - " .. num(inner / (outer - inner)) .. ", 0, 1)", P)
  end
end

-- A map's ridge bodies: the wandering axis, the run, the depth, the distance to the axis, the keep, the
-- height (the crest key) and the openings (Cliff), and the crest band (Entity).
local function map_bodies(key)
  -- the chain every map-wide layer reads (config.lua layer_chain_geo): a later geography version keeps
  -- its frame, so these registered bodies never move with one
  local g
  for _, v in ipairs((cfg.geography[key] or {}).versions or {}) do
    if v.geo_id == cfg.layer_chain_geo[key] then
      g = v
    end
  end
  if not g then
    error("config.lua layer_chain_geo names no geography version of " .. key .. " for the ridges")
  end
  local m = cfg.maps[key]
  -- every noise of the map's ridge reads the frame's geo tiles, so a seed's ridge is one shape whatever
  -- the spawn city
  local function wave(seed1, wavelength, per_scale)
    local input = num(1 / wavelength)
    if per_scale then
      input = input .. " / " .. S
    end
    return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = " .. input ..
      ", output_scale = 1, offset_x = " .. g.cx .. ", offset_y = " .. g.cy .. "}"
  end
  local function waves(rows, per_scale)
    local parts = {}
    for _, row in ipairs(rows) do
      parts[#parts + 1] = num(row.amplitude) .. " * " .. wave(row.seed1, row.wavelength, per_scale)
    end
    return table.concat(parts, " + ")
  end
  -- the wandering axis: the chain coordinates pushed about by slow noise, all in reference pixels, so
  -- the wander is one shape on the map at every scale
  def(N.wander_u[key], g.u .. " + " .. waves(RD.wander.u, true))
  def(N.wander_v[key], g.v .. " + " .. waves(RD.wander.v, true))
  -- the width's multiplier: at 0 the ridge has thinned to nothing and only the fray is left
  def(N.run[key], "max(0, (" .. num(RD.run_base) .. " + " .. waves(RD.run) .. ") * (1 - " .. N.keep[key] .. ") + " ..
    N.keep[key] .. ")")
  local C = {u = N.wander_u[key], v = N.wander_v[key], run = N.run[key], L = {}, terms = {}, near = {}}
  local O = {u = N.wander_u[key], v = N.wander_v[key], fixed_u = g.u, fixed_v = g.v, L = {}, terms = {}, keeps = {},
             named = {}}
  local centre = " + " .. num(RD.centre_tiles)
  local Bd = {L = {bu = g.u .. " * " .. S .. centre, bv = g.v .. " * " .. S .. centre}, terms = {}, pieces = {}}
  for _, r in ipairs(T.ranges) do
    local segs = r.segments[key]
    if segs then
      local pts, wide = {}, {}
      for i, ll in ipairs(r.crest) do
        local pu, pv = to_px(m, ll[1], ll[2])
        pts[i] = {pu, pv}
        wide[i] = half_width(r.heights[i], i == 1 or i == #r.crest)
      end
      add_segments(C, pts, segs, wide)
      local banded = {}
      for _, i in ipairs(segs) do
        if in_band(m, pts[i], pts[i + 1]) then
          banded[#banded + 1] = i
        end
      end
      add_band(Bd, pts, banded, r.heights)
      for _, o in ipairs(r.openings) do
        if on_map(o.maps, key) then
          add_opening(O, m, pts, o, wide)
        end
      end
    end
  end
  def(N.depth[key], joined("max", C.terms, "-inf"), C.L)
  def(N.near[key], joined("min", C.near, "inf"), C.L)
  def(N.crest[key], "(" .. minus(N.depth[key], RD.bias_tiles) .. ") / " .. num(RD.ramp_tiles) .. " + " .. waves(RD.fray))
  O.terms[#O.terms + 1] = "(" .. waves(RD.gaps.noise) .. " < " .. num(RD.gaps.threshold) .. " + " ..
    num(RD.gaps.thin_gain) .. " * clamp(1 - (" .. N.depth[key] .. " + " .. N.near[key] .. ") / " ..
    num(RD.gaps.thin_tiles) .. ", 0, 1) - " .. num(RD.gaps.collar_gain) .. " * " .. N.keep[key] .. ")"
  def(N.keep[key], joined("max", O.keeps, "0"), O.L)
  def(N.openings[key], joined("max", O.terms, "0"), O.L)
  if #Bd.terms == 0 then
    def(N.band[key], "0")
  else
    def(N.band[key], joined("max", Bd.terms, "0"), Bd.L)
  end
  highland(key, Bd, O)
end

for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] and N.crest[key] and N.openings[key] and N.band[key] then
    map_bodies(key)
  end
end

-- The effective height: the map's crest with ridges on, -inf with ridges off.
local on = K.ridges .. " > " .. num(RD.switch_threshold)
def(N.height, "if(" .. on .. ", " .. K.crest .. ", -inf)")
-- The ridge-free start disc (D25 wins there), 1 inside.
def(N.free, "distance < max(" .. num(RD.start.radius_tiles) .. ", starting_area_radius) + " ..
  num(RD.start.margin_tiles))
-- The two cliff properties (S5): the contours of the height, and the cliffiness gaps.
def(N.cliff_elevation, "cliff_elevation_0 + cliff_elevation_interval * clamp(1 + " .. N.height .. ", " ..
  num(RD.contour.low) .. ", " .. num(RD.contour.high) .. ")")
def(N.cliffiness, "if(" .. on .. ", " .. num(RD.cliffiness) .. " * (1 - " .. K.openings .. ") * (1 - " .. N.free ..
  "), 0)")
-- The ore clearance: 0 in the map's crest band (every tile within ore_clear_tiles of a crest, and a
-- little more where the crest bends or climbs) outside the start disc, else 1.
def(N.clear, "if(" .. on .. ", max(1 - " .. K.band .. ", " .. N.free .. "), 1)")

-- The highland: the map's reach frayed by noise the region layer already computes, the warp for rocks and the
-- warp, roughness and marsh outline for tiles, over the falloff, faded in outside the ridge-free start disc; 0
-- with ridges off.
local HG = RD.high
local FRAY, FRAY_TILE = cfg.regions.names.highland_fray, cfg.regions.names.highland_fray_tile
local MASSIF = cfg.regions.names.highland_massif
def(N.rise, "max(0, " .. K.high .. " + " .. S .. " * " .. FRAY .. ")")
def(N.rise_tile, "max(0, " .. K.high_tile .. " + " .. S .. " * " .. FRAY_TILE .. ")")
def(N.gate, "clamp((distance - max(" .. num(RD.start.radius_tiles) .. ", starting_area_radius) - " ..
  num(RD.start.margin_tiles) .. ") / " .. num(HG.start.ramp_tiles) .. ", 0, 1)")
local function high(r, fall)
  return "if(" .. on .. ", min(1, " .. r .. " / (" .. S .. " * " .. num(HG.fall_px) .. " + " .. fall .. ")) * " ..
    N.gate .. ", 0)"
end
def(N.high, high(N.rise, num(HG.rock_fall) .. " / " .. S))
def(N.high_tile, high(N.rise_tile, num(HG.fall_tiles)))
-- The tile temperature's fall, with ridges off 0, and the stony tiles' lean without Alien Biomes.
local GD = RD.ground
def(N.lapse, "if(" .. on .. ", " .. num(GD.lapse_per_px2) .. " * over * over * " .. N.gate .. " * clamp(" ..
  cfg.climate.names.core .. " / " .. num(GD.cold_t) .. ", " .. num(GD.cold_min) .. ", 1), 0)",
  {over = "max(0, " .. N.rise_tile .. " / " .. S .. " - " .. num(GD.lapse_from_px) .. ") * " .. MASSIF})
def(N.ground, num(RD.ground.lean) .. " * " .. N.high_tile)
def(K.ground, num(0))
-- The grain's bodies read the tile reach, and a save from before the highlands names those bodies but not this
-- key: its prototype leaves such a save no rise, so its ground stays.
def(K.high_tile, "-inf")
-- The rock lift: the highland outside the openings. The three big vanilla rocks read rock_density with it added
-- (trees.lua, their high bodies); Alien Biomes' big rocks read their own noise, so data-final-fixes.lua hooks the
-- key on them.
local RK = RD.rocks
def(N.rock_lift, N.high .. " * " .. K.passes)
def(N.rock_density, "rock_density + " .. num(RK.gain) .. " * " .. N.rock_lift)
def(N.rock_lift_ab, num(RK.gain_ab) .. " * " .. N.rock_lift)
def(K.rock_lift, num(0))

-- The toggle's neutral bodies, shared with waterways' canals switch: defined here unless an earlier
-- module did (one definition per name).
local NE = data.raw["noise-expression"] or {}
if not NE[SW.on] then
  def(SW.on, num(1))
end
if not NE[SW.off] then
  def(SW.off, num(0))
end

data:extend(E)

-- The cliff's art beside Alien Biomes (config.lua ridges.cliff_art): the sheets swap one for one, the
-- shadows stay vanilla's (Alien Biomes' shadow sheets have another frame width).
if mods[RD.cliff_art.mod] then
  for _, o in pairs(data.raw.cliff[RD.cliff_art.cliff].orientations) do
    o.pictures_lower = nil
    for _, picture in ipairs(o.pictures) do
      for _, layer in ipairs(picture.layers) do
        if not layer.draw_as_shadow then
          layer.filename = RD.cliff_art.to .. layer.filename:sub(#RD.cliff_art.from + 1)
        end
      end
    end
  end
end
