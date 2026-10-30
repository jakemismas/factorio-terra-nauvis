-- Ridges (ARCHITECTURE.md, milestone contract 8; S5; APPROVALS 5 and 11; milestone ridges).
--
-- Every range of prototypes/tables/ranges.lua (tools/build_ranges.py writes it from the approval data
-- and R7b) becomes cliffs along its crest polyline, written in contour units so the cliffs slider is
-- inert (S5): with d the distance to the nearest crest in tiles,
--   cliff_elevation = cliff_elevation_0 + cliff_elevation_interval * clamp(1 + (flank - d) / ramp, low, high)
-- crosses one contour only, f = 1, flank tiles out on each side with its high side toward the crest,
-- whatever the frequency slider makes the interval, and
--   cliffiness = cliffiness_on * (1 - opening) outside the ridge-free start disc, 0 inside it
-- never reads cliff_richness, so continuity and richness have nothing to act on. An opening is a slot
-- across the crest at a pass or an unnamed gap (pass_tiles along the crest, reach_tiles to each side),
-- or, where a range cut by the map's edge has no pass on that map, a band along the edge near the
-- crossing, so the ridge stops short of the edge (APPROVALS 5).
--
-- Per map (each a body the preset names through a key, as tn_land_coarse is): the squared crest
-- distance in tiles (tn_crest) and the openings (tn_openings), which only the Cliff program reads, and
-- the crest band (tn_band) the ore clearance reads in the Entity program, a cheap superset of the tiles
-- whose centre lies within ore_clear_tiles of a crest (read at the centre, where an ore entity stands,
-- not at the integer corner the program samples; an exact distance there measured Entity +3,028 on
-- Europe against the milestone's +2,000 allocation; this milestone's design notes). All read the map's own
-- coordinate chain, so they are firewall-clean. Shared bodies: the effective crest
-- distance, which the ridges toggle (a name switch to tn_one or tn_zero) turns into +inf when off, so
-- nothing of a ridge compiles and no cliff is placed (S5: a constant crest distance places none); the
-- ridge-free start disc (D25 wins inside it); the two cliff properties; and the ore
-- clearance that data-final-fixes.lua multiplies into every Earth ore probability, so ore never
-- stands on a ridge cell without a global cliff_removal_probability edit.
-- Every name and number comes from config.lua (S-5); the toggle never multiplies (U5).
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

-- One band term (and its locals) for a piece; P and Q name the scaled axis and cross coordinates.
local function band_term(pts, run, piece, k, B)
  local vs = {}
  for j = piece.first, piece.last do
    if j == piece.first then
      vs[#vs + 1] = pts[run[j]]
    end
    vs[#vs + 1] = pts[run[j] + 1]
  end
  local p, q = "bu", "bv"
  local list = {}
  for n, v in ipairs(vs) do
    list[n] = piece.axis == "x" and {v[1], v[2]} or {v[2], v[1]}
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
  for n = 2, #list do
    local a, b = list[n - 1], list[n]
    local slope = (b[2] - a[2]) / (b[1] - a[1])
    steep = math.max(steep, math.abs(slope))
    c = c - slope * a[1]
    terms[#terms + 1] = num(slope) .. " * clamp(" .. p .. ", " .. S .. " * " .. num(a[1]) .. ", " .. S .. " * " ..
      num(b[1]) .. ")"
  end
  local half = RD.ore_clear_tiles * math.sqrt(1 + steep * steep)
  local mid, span = (list[1][1] + list[#list][1]) / 2, (list[#list][1] - list[1][1]) / 2
  local f = "f" .. k
  B[f] = S .. " * " .. num(c) .. " + " .. table.concat(terms, " + ")
  return "(abs(" .. q .. " - " .. f .. ") < " .. num(half) .. ") * (abs(" .. p .. " - " .. S .. " * " .. num(mid) ..
    ") < " .. S .. " * " .. num(span) .. " + " .. num(RD.ore_clear_tiles) .. ")"
end

-- The crest segments of one range on a map, added to the crest body's locals and terms.
local function add_segments(C, pts, segs)
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
      C.terms[#C.terms + 1] = "qx" .. s .. " * qx" .. s .. " + qy" .. s .. " * qy" .. s
    end
  end
end

-- One opening on a map: a slot across the crest at a pass or a gap; at an edge crossing, the tiles
-- within edge_tiles of the map's extent (its edges at -1/2 and W - 1/2 in this frame) and within
-- edge_reach_tiles of the crossing.
local function add_opening(O, m, pts, o)
  local cu, cv = to_px(m, o.lat, o.lon)
  local a, b = pts[o.seg], pts[o.seg + 1]
  local dx, dy = b[1] - a[1], b[2] - a[2]
  local len = math.sqrt(dx * dx + dy * dy)
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
  O.L["pu" .. s] = minus(O.u, cu)
  O.L["pv" .. s] = minus(O.v, cv)
  local pu, pv = "pu" .. s, "pv" .. s
  if o.kind == "edge" then
    O.L["ed" .. s] = "min(" .. O.u .. " + 1 / 2, " .. num(m.width_px) .. " - 1 / 2 - " .. O.u .. ", " .. O.v ..
      " + 1 / 2, " .. num(m.height_px) .. " - 1 / 2 - " .. O.v .. ")"
    O.terms[#O.terms + 1] = "(ed" .. s .. " * " .. S .. " < " .. num(RD.edge_tiles) .. ") * ((" .. pu .. " * " ..
      pu .. " + " .. pv .. " * " .. pv .. ") * " .. scale2 .. " < " .. num(RD.edge_reach_tiles ^ 2) .. ")"
  elseif len > 0 then
    -- along the crest, outward at a tip (the crest's end vertex): from pass_tiles / 2 inside it to
    -- tip_tiles past it, so the end cap goes too; elsewhere pass_tiles / 2 either side
    local tx, ty = dx / len, dy / len
    local along = "abs(" .. pu .. " * " .. num(tx) .. " + " .. pv .. " * " .. num(ty) .. ") * " .. S .. " < " ..
      num(RD.pass_tiles / 2)
    if o.tip then
      tx, ty = tx * o.tip, ty * o.tip
      local lo, hi = -RD.pass_tiles / 2, RD.tip_tiles
      along = "abs((" .. pu .. " * " .. num(tx) .. " + " .. pv .. " * " .. num(ty) .. ") * " .. S .. " - " ..
        num((lo + hi) / 2) .. ") < " .. num((hi - lo) / 2)
    end
    O.terms[#O.terms + 1] = "(" .. along .. ") * (abs(" .. pv .. " * " .. num(tx) .. " - " .. pu .. " * " .. num(ty) ..
      ") * " .. S .. " < " .. num(RD.reach_tiles) .. ")"
  end
end

-- The crest band of one range on a map: its kept segments in runs of consecutive ones, each cut
-- into monotone pieces.
local function add_band(Bd, pts, segs)
  local run = {}
  local function flush()
    if #run > 0 then
      for _, piece in ipairs(band_pieces(pts, run)) do
        Bd.terms[#Bd.terms + 1] = band_term(pts, run, piece, #Bd.terms + 1, Bd.L)
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

-- A map's three ridge bodies: the squared crest distance in tiles squared (Cliff), the openings
-- (Cliff) and the crest band (Entity).
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
  local C = {u = g.u, v = g.v, L = {}, terms = {}}
  local O = {u = g.u, v = g.v, L = {}, terms = {}}
  local centre = " + " .. num(RD.centre_tiles)
  local Bd = {L = {bu = g.u .. " * " .. S .. centre, bv = g.v .. " * " .. S .. centre}, terms = {}}
  for _, r in ipairs(T.ranges) do
    local segs = r.segments[key]
    if segs then
      local pts = {}
      for i, ll in ipairs(r.crest) do
        local pu, pv = to_px(m, ll[1], ll[2])
        pts[i] = {pu, pv}
      end
      add_segments(C, pts, segs)
      add_band(Bd, pts, segs)
      for _, o in ipairs(r.openings) do
        if on_map(o.maps, key) then
          add_opening(O, m, pts, o)
        end
      end
    end
  end
  if #C.terms == 0 then
    def(N.crest[key], "inf")
  else
    def(N.crest[key], joined("min", C.terms, "inf") .. " * " .. scale2, C.L)
  end
  def(N.openings[key], joined("max", O.terms, "0"), O.L)
  if #Bd.terms == 0 then
    def(N.band[key], "0")
  else
    def(N.band[key], joined("max", Bd.terms, "0"), Bd.L)
  end
end

for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] and N.crest[key] and N.openings[key] and N.band[key] then
    map_bodies(key)
  end
end

-- The effective squared crest distance: the map's crest with ridges on, +inf with ridges off.
local on = K.ridges .. " > " .. num(RD.switch_threshold)
def(N.d2, "if(" .. on .. ", " .. K.crest .. ", inf)")
-- The ridge-free start disc (D25 wins there), 1 inside.
def(N.free, "distance < max(" .. num(RD.start.radius_tiles) .. ", starting_area_radius) + " ..
  num(RD.start.margin_tiles))
-- The two cliff properties (S5): one contour, flank tiles out, and the cliffiness gaps.
def(N.cliff_elevation, "cliff_elevation_0 + cliff_elevation_interval * clamp(1 + (" .. num(RD.flank_tiles) ..
  " - sqrt(" .. N.d2 .. ")) / " .. num(RD.ramp_tiles) .. ", " .. num(RD.contour.low) .. ", " .. num(RD.contour.high) ..
  ")")
def(N.cliffiness, "if(" .. on .. ", " .. num(RD.cliffiness) .. " * (1 - " .. K.openings .. ") * (1 - " .. N.free ..
  "), 0)")
-- The ore clearance: 0 in the map's crest band (every tile within ore_clear_tiles of a crest, and a
-- little more where the crest bends or climbs) outside the start disc, else 1.
def(N.clear, "if(" .. on .. ", max(1 - " .. K.band .. ", " .. N.free .. "), 1)")

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
