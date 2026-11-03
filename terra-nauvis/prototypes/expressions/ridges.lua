-- Ridges (ARCHITECTURE.md, contract 8; S5; APPROVALS 5 and 11; design notes 2026-10-30,
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
--   h        (depth - bias) / ramp + fray: the fray moves the edge along the strike, so a line does not
--            hold to one lattice row
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
-- an exact distance there measured Entity +3,028 on Europe against the ridges' +2,000 allocation; the
-- ridges' design notes). Ore clears the axis only: where a ridge wanders off it an ore patch can take a
-- cliff out, which reads as one more gap. All read the map's own coordinate chain, so they are
-- firewall-clean. Shared bodies: the effective height, which the ridges toggle (a name switch to tn_one
-- or tn_zero) turns into -inf when off, so nothing of a ridge compiles and no cliff is placed (S5: a
-- constant field places none); the ridge-free start disc (D25 wins inside it, design rule 12); the two cliff
-- properties; and the ore clearance that data-final-fixes.lua multiplies into every Earth ore
-- probability, without a global cliff_removal_probability edit. Every noise reads the
-- frame's geo tiles, so a seed's ridges are one shape for every spawn city; only the Cliff program pays
-- for the noise, on the 4-tile lattice (S5). Every name and number comes from config.lua (S-5); the
-- toggle never multiplies (U5).
--
-- The highlands (2026-10-30: a cliff squiggle on plain grass does not read as a mountain range; design notes
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
-- the second table (0.3.0): ranges the released table lacks, read only by the next bodies (the union below)
local T2R = require("prototypes.tables.ranges_v2")

local RD = cfg.ridges
-- both tables' ranges, the first table's first: the union bodies read them in this order
local function union_ranges()
  local all, second = {}, {}
  for _, tab in ipairs({T.ranges, T2R.ranges}) do
    for _, r in ipairs(tab) do
      all[#all + 1] = r
      second[r] = tab == T2R.ranges or nil
    end
  end
  return all, second
end
local UR, second = union_ranges()
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
local function band_term(pts, run, piece, k, B, H, heights, opts)
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
  local rows, cols = 0, 0
  for _, v in ipairs(list) do
    rows = rows + (piece.axis == "x" and v[2] or v[1])
    cols = cols + (piece.axis == "x" and v[1] or v[2])
  end
  H[#H + 1] = {p = p, q = q, f = f, mid = mid, span = span, cos = 2 * span / arc, arc = arc, top = top,
               row = rows / #list, col = cols / #list,
               reach = reach_px((sum / #list + top) / 2), opts = opts,
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
      (O.pass_half or num(RD.pass_tiles / 2))
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
local function add_band(Bd, pts, segs, heights, opts)
  local run = {}
  local function flush()
    if #run > 0 then
      for _, piece in ipairs(band_pieces(pts, run)) do
        Bd.terms[#Bd.terms + 1] = band_term(pts, run, piece, #Bd.terms + 1, Bd.L, Bd.pieces, heights, opts)
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
local function highland(key, Bd, O, NM)
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
  def(NM.high, joined("max", terms, "-inf"), L)
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
  def(NM.high_tile, joined("max", terms, "-inf"), T2)
  -- The cold field (config.lua ridges.cold): one field per piece, on the pieces the rocks read, so the rocks' reach
  -- covers every cold tile and the palm mask can stand on it.
  local CO, m = RD.cold, cfg.maps[key]
  -- The second version (0.3.0) raises a piece's snow line by dry_rise_m times the largest dry belt weight at its mean
  -- vertex, as climate.lua's dry weight reads the belts.
  -- The union's second-table pieces (ridges.union.cold): only a piece whose top clears its snow line counts (a grey
  -- verdict is a flat plateau that slow noise lifts into snow, with straight edges and wide grey), and outside the
  -- snow edge its field falls k = reach / ref_px times faster, so its rim is as narrow as a ref_px piece's; past its
  -- ends the distance is the distance across plus taper times the distance past the end, so the snow ends in a V;
  -- the edge rows (tiles) and fray times
  -- the ragged factor (12 to 384 tiles) frays the snow edge, which a long straight crest and the slow region noise
  -- left smooth for hundreds of tiles. Their terms go in C2 as locals. A row with cold = false (the Ethiopian
  -- Highlands: no snow in Africa) adds none.
  local UC = cfg.ridges.union.cold
  local FS2 = CO.snow_at * CO.top_t / (CO.top_t - CO.snow_t)
  local C2 = {}
  local function cold_terms(rise)
    local out = {}
    for k, h in ipairs(Bd.pieces) do
      local o = h.opts or {}
      if h.arc >= RD.rocks.short_px and not o.nocold then
        local plat = m.lat_top_edge - (h.row + 1 / 2) / PPD
        local lat = math.abs(plat)
        local line = math.max(CO.snow_min_m, CO.snow_m - CO.snow_per_degree * math.max(0, lat - CO.snow_lat))
        if rise then
          local plon = m.lon_left_edge + (h.col + 1 / 2) / PPD
          local dry = 0
          for _, b in ipairs(cfg.climate.dry_belts) do
            local wl = math.max(0, math.min(1, math.min(plat - b.lat[1], b.lat[2] - plat) / b.ramp[1]))
            local wo = math.max(0, math.min(1, math.min(plon - b.lon[1], b.lon[2] - plon) / b.ramp[2]))
            dry = math.max(dry, wl * wo)
          end
          line = line + CO.dry_rise_m * dry
        end
        if h.top >= line - CO.grey_m then
          local s = tostring(k)
          local snowy = h.top >= line
          local dist = "sqrt(a" .. s .. " * a" .. s .. " + e" .. s .. " * e" .. s .. ")"
          if o.second then
            -- a second-table piece ends in a V past its ends: a round or pointed cap of a reach several hundred tiles
            -- across meets the view at right angles to the crest, a straight edge at player zoom; a V's sides are
            -- diagonals
            dist = "(a" .. s .. " + " .. num(UC.taper) .. " * e" .. s .. ")"
          end
          local term = "1 - " .. dist .. " / (" .. num(h.reach * (snowy and 1 or CO.grey_reach)) .. " * " ..
            N.cold.reach .. ")"
          if not o.second then
            out[#out + 1] = snowy and term or ("min(" .. num(CO.grey_top) .. ", " .. term .. ")")
          elseif snowy then
            C2["c" .. s] = term .. " + fr"
            out[#out + 1] = "min(c" .. s .. ", " .. num(FS2) .. " + " .. num(math.max(1, h.reach / UC.ref_px)) ..
              " * (c" .. s .. " - " .. num(FS2) .. "))"
          end
        end
      end
    end
    return out
  end
  if NM.cold then
    def(NM.cold, joined("max", cold_terms(false), "-inf"), T2)
  end
  if NM.cold2 then
    local cterms = cold_terms(true)
    local L2 = T2
    if next(C2) then
      L2 = {}
      for k, v in pairs(T2) do
        L2[k] = v
      end
      for k, v in pairs(C2) do
        L2[k] = v
      end
      -- the second table's snow edge noise, once for every term: the ragged factor and two rows in tiles
      local fr = num(UC.fray) .. " * (" .. cfg.climate.ragged.name .. " - 1)"
      for _, w in ipairs(UC.edge) do
        fr = fr .. " + " .. num(w.amplitude) .. " * basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " ..
          num(w.seed1) .. ", input_scale = " .. num(1 / w.tiles) .. ", output_scale = 1}"
      end
      L2.fr = fr
    end
    def(NM.cold2, joined("max", cterms, "-inf"), L2)
  end
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
    def(NM.passes, "1")
  else
    def(NM.passes, "clamp((" .. joined("min", ds, "inf") .. ") * " .. scale2 .. " / " .. num(outer - inner) ..
      " - " .. num(inner / (outer - inner)) .. ", 0, 1)", P)
  end
end

-- The union (0.3.0, Earth mods recommendation 4): both tables' ranges in the next highland reach, tile reach and
-- passes, and in the cold field's second version, which only 0.3.0 reads. The second table's ranges draw no cliffs:
-- the line field's contours hold one row of the cliffs' 4-tile lattice for 20 to 80 tiles and step at right angles,
-- and neither a wiggle along the crest nor short gaps cured it (reports/f-ranges.md), so they stay out of the crest,
-- openings and crest band, which a preset still names from the first table. map_bodies' bodies read the first table
-- alone, so a world made before keeps every ridge it had. g is the map's frame.
local function union_bodies(key, m, g)
  local centre = " + " .. num(RD.centre_tiles)
  local O2 = {u = N.wander_u[key], v = N.wander_v[key], fixed_u = g.u, fixed_v = g.v, L = {}, terms = {}, keeps = {},
              named = {}}
  local Bd2 = {L = {bu = g.u .. " * " .. S .. centre, bv = g.v .. " * " .. S .. centre}, terms = {}, pieces = {}}
  for _, r in ipairs(UR) do
    local segs = r.segments[key]
    if segs then
      local pts, wide = {}, {}
      for i, ll in ipairs(r.crest) do
        local pu, pv = to_px(m, ll[1], ll[2])
        pts[i] = {pu, pv}
        wide[i] = half_width(r.heights[i], i == 1 or i == #r.crest)
      end
      local banded = {}
      for _, i in ipairs(segs) do
        if in_band(m, pts[i], pts[i + 1]) then
          banded[#banded + 1] = i
        end
      end
      add_band(Bd2, pts, banded, r.heights, second[r] and {second = true, nocold = r.cold == false} or nil)
      for _, o in ipairs(r.openings) do
        if on_map(o.maps, key) then
          add_opening(O2, m, pts, o, wide)
        end
      end
    end
  end
  local UN = cfg.ridges.union.names
  highland(key, Bd2, O2, {high = UN.high_map[key], high_tile = UN.high_tile_map[key], cold2 = N.cold2.map[key],
                          passes = UN.passes[key]})
end

-- A map's ridge bodies: the wandering axis, the run, the depth, the distance to the axis, the keep, the
-- height (the crest key) and the openings (Cliff), and the crest band (Entity).
local function map_bodies(key)
  -- the chain every map-wide layer reads (config.lua layer_chain_geo): a later geography version keeps
  -- its frame, so these registered bodies never move with one
  local g
  for _, v in ipairs({cfg.frames[key]}) do
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
  def(N.crest[key], "(" .. minus(N.depth[key], RD.bias_tiles) .. ") / " .. num(RD.ramp_tiles) .. " + " ..
    waves(RD.fray))
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
  highland(key, Bd, O, {high = N.high_map[key], high_tile = N.high_tile_map[key], cold = N.cold.map[key],
                        passes = N.passes[key]})
  union_bodies(key, m, g)
end

for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] and N.crest[key] and N.openings[key] and N.band[key] then
    map_bodies(key)
  end
end

-- The line field (config.lua ridges.line and ridges.preset; design notes 2026-10-31, ridges as lines). The bodies above
-- draw a ridge as the outline of a band, so it has two flanks that run side by side and close round its ends: at
-- scale 1, where a range is about as long as its band is wide, that outline is a box. Here the field is a signed
-- distance across the crest with its high side on one hand, so its contours follow the crest and stand open at both
-- ends. On each map:
--   side    the signed distance to the nearest crest piece at the wandering point, positive on the high side. A
--           piece is band_pieces', monotone along one axis, so its distance is that axis's piecewise-linear crest
--           function (3 operations per segment against the 14 of the exact distance above) times the piece's mean
--           cosine, plus the distance past its ends. The sign is the piece's own hand and the magnitude the distance
--           every piece compares, so the field does not step where one piece hands over to the next. The crest is
--           the table's with its corners cut, or a line takes a polyline's right angle (the Western Alps turn 87
--           degrees at Monte Rosa)
--   width   a piece's half-width along its crest, the same clamps at the width's own slopes, times the run: a line
--           thins out where the width falls to nothing, because a thin stretch takes the gaps below
--   reach   base_tiles + gain * fit * width, the width capped: how far one contour stands from the next and how far
--           the noise pushes a line, so a taller range spreads wider. It reads the width alone, not the distance:
--           with the distance the slope steepened off the crest and noise could not bend a side line. fit is (scale
--           / 6) ^ power: a range is shorter at a low scale, so its lines stand closer and fewer of them
--   along   the distance along the crest in tiles, at the same piece. The line's bends are waves of this, not noise
--           over the plane: noise with slope enough to bend a line off the lattice folds a contour back on itself
--           into rings, and noise gentle enough not to leaves decided flats, while a wave along the crest moves a
--           contour only along the crest, so any bend is free
--   h       (side * stretch + fine) / reach + bends, three contours through config.lua's contour clamp: the line at
--           h = 0 and a side line each way. bends are the waves of along, their lengths in no simple ratio and each
--           phase pushed about by slow noise, so they never fall into step and a seed has its own; along leans a
--           little with side (shear), so a side line does not copy the line's bends. stretch moves only the side
--           lines. fine is in tiles, so a low range breaks off the lattice as well as a tall one
-- A contour's high side decides how it draws: an east-west face that looks south is the heaviest cliff there is
-- (11,108 opaque px against 1,778 for the same line facing north). So a piece along the east-west axis lifts its
-- north side, and a north-south piece keeps the hand round it. Where a range doubles back the hand reverses and
-- every contour would fold along the piece boundary: that reversal is a gap, as wide as the lines reach.
local LN = RD.line

-- One run of consecutive kept segments with its corners cut: each inner vertex becomes two, a share of the way along
-- its two segments and at most cut_px from it, so a line takes no kink from the polyline. A vertex's width carries
-- over along the segment. Returns the run's new points and widths.
local function cut_corners(pts, wide, run)
  local out, ws = {pts[run[1]]}, {wide[run[1]]}
  for n = 2, #run do
    local i = run[n]
    local p, v, q = pts[i - 1], pts[i], pts[i + 1]
    local function toward(o, w)
      local dx, dy = o[1] - v[1], o[2] - v[2]
      local t = math.min(LN.cut_share, LN.cut_px / math.sqrt(dx * dx + dy * dy))
      out[#out + 1] = {v[1] + t * dx, v[2] + t * dy}
      ws[#ws + 1] = wide[i] + t * (w - wide[i])
    end
    toward(p, wide[i - 1])
    toward(q, wide[i + 1])
  end
  local e = run[#run] + 1
  out[#out + 1], ws[#ws + 1] = pts[e], wide[e]
  return out, ws
end

-- Every piece of a range's kept segments in order, on the crest with its corners cut, knowing which way it runs
-- and, when it is an east-west piece long enough to pick, the hand that lifts its north side.
local function line_pieces(pts, wide, segs)
  local pcs, run = {}, {}
  local function flush()
    if #run == 0 then
      return
    end
    local cp, cw = cut_corners(pts, wide, run)
    local cr = {}
    for n = 1, #cp - 1 do
      cr[n] = n
    end
    for _, pc in ipairs(band_pieces(cp, cr)) do
      local a, b = cp[cr[pc.first]], cp[cr[pc.last] + 1]
      local i = pc.axis == "x" and 1 or 2
      pc.ascending = b[i] > a[i]
      pc.run, pc.pts, pc.wide = cr, cp, cw
      if pc.axis == "x" and math.abs(b[1] - a[1]) >= LN.turn_px then
        pc.want = pc.ascending and 1 or -1
      end
      pcs[#pcs + 1] = pc
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
  return pcs
end

-- Calls use(piece, hand) along a range: the hand stays until an east-west piece wants the other, and that reversal
-- joins flips. A range with no east-west piece long enough lifts its west side.
local function walk_hands(pcs, use, flips)
  local hand
  for _, pc in ipairs(pcs) do
    hand = hand or pc.want
  end
  if not hand and pcs[1] then
    local south = pcs[1].axis == "y" and pcs[1].ascending
    hand = south and -1 or 1
  end
  for _, pc in ipairs(pcs) do
    if pc.want and pc.want ~= hand then
      hand = pc.want
      flips[#flips + 1] = pc.pts[pc.run[pc.first]]
    end
    use(pc, hand)
  end
end

local function line_bodies(key)
  local g
  for _, v in ipairs({cfg.frames[key]}) do
    if v.geo_id == cfg.layer_chain_geo[key] then
      g = v
    end
  end
  local m = cfg.maps[key]
  local function wave(row)
    return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(row.seed1) .. ", input_scale = " ..
      num(1 / row.wavelength) .. ", output_scale = 1, offset_x = " .. g.cx .. ", offset_y = " .. g.cy .. "}"
  end
  local function waves(rows)
    local parts = {}
    for _, row in ipairs(rows) do
      parts[#parts + 1] = num(row.amplitude) .. " * " .. wave(row)
    end
    return table.concat(parts, " + ")
  end
  local LNN = LN.names
  local L = {wu = N.wander_u[key] .. " * " .. S .. " + " .. num(RD.centre_tiles),
             wv = N.wander_v[key] .. " * " .. S .. " + " .. num(RD.centre_tiles)}
  local fit = "(" .. S .. " / " .. num(LN.fit_scale) .. ") ^ " .. num(LN.fit_power)
  -- a low scale packs the same passes into a shorter crest: the Alps at scale 1 are a slot every 40 tiles
  local O = {u = N.wander_u[key], v = N.wander_v[key], fixed_u = g.u, fixed_v = g.v, L = {}, terms = {}, keeps = {},
             named = {},
             pass_half = "max(" .. num(LN.pass_min_tiles / 2) .. ", " .. num(LN.pass_tiles / 2) .. " * " .. fit .. ")"}
  local k = 0
  local deps, flips = {}, {}
  local walked = 0
  local function piece(pts, wide, run, pc, hand)
    local up = {}
    for j = pc.first, pc.last do
      if j == pc.first then
        up[#up + 1] = run[j]
      end
      up[#up + 1] = run[j] + 1
    end
    local list = {}
    for n, i in ipairs(up) do
      local v = pts[i]
      list[n] = pc.axis == "x" and {v[1], v[2], w = wide[i]} or {v[2], v[1], w = wide[i]}
    end
    if not pc.ascending then
      local rev = {}
      for n = #list, 1, -1 do
        rev[#rev + 1] = list[n]
      end
      list = rev
    end
    k = k + 1
    local id = tostring(k)
    local P, Q = "wu", "wv"
    -- the sign that makes side positive on the left of travel
    local left = pc.ascending and -1 or 1
    if pc.axis == "y" then
      P, Q, left = "wv", "wu", -left
    end
    local f, r, c, c2, arc = {}, {}, list[1][2], list[1].w, 0
    for n = 2, #list do
      local a, b = list[n - 1], list[n]
      local slope = (b[2] - a[2]) / (b[1] - a[1])
      local rise = (b.w - a.w) / (b[1] - a[1])
      c, c2 = c - slope * a[1], c2 - rise * a[1]
      local cl = "clamp(" .. P .. ", " .. S .. " * " .. num(a[1]) .. ", " .. S .. " * " .. num(b[1]) .. ")"
      L["c" .. id .. "_" .. n] = cl
      f[#f + 1] = num(slope) .. " * c" .. id .. "_" .. n
      r[#r + 1] = num(rise) .. " * c" .. id .. "_" .. n .. " / " .. S
      arc = arc + (b[1] - a[1]) * math.sqrt(1 + slope * slope)
    end
    local mid, span = (list[1][1] + list[#list][1]) / 2, (list[#list][1] - list[1][1]) / 2
    L["a" .. id] = num(hand * left * 2 * span / arc) .. " * (" .. Q .. " - " .. S .. " * " .. num(c) .. " - (" ..
      table.concat(f, " + ") .. "))"
    L["e" .. id] = "max(0, abs(" .. P .. " - " .. S .. " * " .. num(mid) .. ") - " .. S .. " * " .. num(span) .. ")"
    L["d" .. id] = "abs(a" .. id .. ") + e" .. id
    -- the distance along the crest in tiles, running on from the piece before and holding past the piece's ends, so
    -- two pieces agree where one hands over to the other
    local per = (pc.ascending and 1 or -1) * arc / (2 * span)
    L["w" .. id] = S .. " * " .. num(walked - per * (pc.ascending and list[1][1] or list[#list][1])) .. " + " ..
      num(per) .. " * clamp(" .. P .. ", " .. S .. " * " .. num(list[1][1]) .. ", " .. S .. " * " ..
      num(list[#list][1]) .. ")"
    walked = walked + arc
    deps[#deps + 1] = "(" .. num(c2) .. " + " .. table.concat(r, " + ") .. ") * " .. N.run[key] .. " - d" .. id
    if k == 1 then
      L.m1 = "d1"
      L.s1 = "if(a1 > 0, d1, -d1)"
      L.t1 = "w1"
    else
      local q = tostring(k - 1)
      L["m" .. id] = "min(d" .. id .. ", m" .. q .. ")"
      L["s" .. id] = "if(d" .. id .. " < m" .. q .. ", if(a" .. id .. " > 0, d" .. id .. ", -d" .. id .. "), s" .. q ..
        ")"
      L["t" .. id] = "if(d" .. id .. " < m" .. q .. ", w" .. id .. ", t" .. q .. ")"
    end
  end
  for _, r in ipairs(T.ranges) do
    local segs = r.segments[key]
    if segs then
      local pts, wide = {}, {}
      for i, ll in ipairs(r.crest) do
        local pu, pv = to_px(m, ll[1], ll[2])
        pts[i] = {pu, pv}
        wide[i] = half_width(r.heights[i], i == 1 or i == #r.crest)
      end
      walk_hands(line_pieces(pts, wide, segs), function(pc, hand)
        piece(pc.pts, pc.wide, pc.run, pc, hand)
      end, flips)
      for _, o in ipairs(r.openings) do
        if on_map(o.maps, key) then
          add_opening(O, m, pts, o, wide)
        end
      end
    end
  end
  local id = tostring(k)
  def(LNN.depth[key], joined("max", deps, "-inf"), L)
  def(LNN.side[key], "s" .. id, L)
  def(LNN.near[key], "m" .. id, L)
  def(LNN.along[key], "t" .. id, L)
  local width = "(" .. LNN.depth[key] .. " + " .. LNN.near[key] .. ")"
  local reach = "(" .. num(LN.base_tiles) .. " + " .. num(LN.gain) .. " * " .. fit .. " * clamp(" .. width .. ", 0, " ..
    num(LN.width_max_tiles) .. "))"
  def(LNN.reach[key], reach)
  local R, KP = LNN.reach[key], N.keep[key]
  local bends = {}
  for _, w in ipairs(LN.waves) do
    bends[#bends + 1] = num(w.amplitude) .. " * sin(" .. num(2 * math.pi / w.tiles) .. " * walk + " .. num(LN.phase) ..
      " * " .. wave(RD.run[w.phase]) .. ")"
  end
  def(LNN.crest[key], "(" .. LNN.side[key] .. " * max(" .. num(LN.stretch.floor) .. ", 1 + " .. num(LN.stretch.gain) ..
    " * " .. wave(LN.stretch) .. ") + " .. waves(LN.fine) .. ") / " .. R .. " + " .. table.concat(bends, " + "),
    {walk = LNN.along[key] .. " + " .. num(LN.shear) .. " * " .. LNN.side[key]})
  local H = LNN.crest[key]
  for i, c in ipairs(flips) do
    local s = "f" .. i
    O.L["pu" .. s] = minus(O.u, c[1])
    O.L["pv" .. s] = minus(O.v, c[2])
    O.terms[#O.terms + 1] = "((pu" .. s .. " * pu" .. s .. " + pv" .. s .. " * pv" .. s .. ") * " .. scale2 .. " < " ..
      num(LN.mask ^ 2) .. " * " .. R .. " * " .. R .. ")"
  end
  -- the noise gaps, as the bodies above draw them, and short snips off the fine row, so gaps come in two sizes
  O.terms[#O.terms + 1] = "(" .. waves(RD.gaps.noise) .. " < " .. num(LN.gaps.threshold) .. " + " ..
    num(LN.gaps.thin_gain) .. " * clamp(1 - " .. width .. " / " .. num(LN.gaps.thin_tiles) .. ", 0, 1) - " ..
    num(RD.gaps.collar_gain) .. " * " .. KP .. ")"
  O.terms[#O.terms + 1] = "(abs(" .. wave(LN.fine[1]) .. ") > " .. num(LN.snip) .. " + " .. num(RD.gaps.collar_gain) ..
    " * " .. KP .. ")"
  -- past the lines' reach every hand change draws a contour: nothing stands there
  O.terms[#O.terms + 1] = "(" .. LNN.near[key] .. " > " .. num(LN.mask) .. " * " .. R .. ")"
  -- a side line stands on one hand at a time, on a wide stretch, and never round a slot
  O.terms[#O.terms + 1] = "(abs(" .. H .. ") > " .. num(LN.side_level) .. ") * max(" .. width .. " * " .. fit ..
    " < " .. num(LN.side_min_tiles) .. ", " .. H .. " * " .. wave(RD.run[1]) .. " < 0, " .. KP .. " > " ..
    num(LN.side_keep) .. ")"
  def(LNN.openings[key], joined("max", O.terms, "0"), O.L)
end

for _, key in ipairs(cfg.map_order) do
  if cfg.geography[key] and N.crest[key] and N.openings[key] and N.band[key] then
    line_bodies(key)
  end
end

-- The effective height: the map's crest with ridges on, -inf with ridges off.
local on = K.ridges .. " > " .. num(RD.switch_threshold)
def(N.height, "if(" .. on .. ", " .. K.crest .. ", -inf)")
-- The ridge-free start disc (D25 wins there, design rule 12), 1 inside.
def(N.free, "distance < max(" .. num(RD.start.radius_tiles) .. ", starting_area_radius) + " ..
  num(RD.start.margin_tiles))
-- The two cliff properties (S5): the contours of the height, and the cliffiness gaps.
def(N.cliff_elevation, "cliff_elevation_0 + cliff_elevation_interval * clamp(1 + " .. N.height .. ", " ..
  num(RD.contour.low) .. ", " .. num(RD.contour.high) .. ")")
def(N.cliffiness, "if(" .. on .. ", " .. num(RD.cliffiness) .. " * (1 - " .. K.openings .. ") * (1 - " .. N.free ..
  "), 0)")
def(LN.names.cliff_elevation, "cliff_elevation_0 + cliff_elevation_interval * clamp(1 + " .. N.height .. ", " ..
  num(LN.contour.low) .. ", " .. num(LN.contour.high) .. ")")
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
-- The cold field and its temperature cap (config.lua ridges.cold): the map's field folded on the per-save map number,
-- with the region layer's outline.
local CO = RD.cold
local function cold_fold(NC)
  local text
  for _, key in ipairs(cfg.map_order) do
    local body = NC.map[key]
    if body then
      text = text and ("if(" .. K.map .. " == " .. num(cfg.maps[key].id) .. ", " .. body .. ", " .. text .. ")") or body
    end
  end
  return text
end
def(N.cold.reach, S .. " * max(1, (" .. num(CO.fit_scale) .. " / " .. S .. ") ^ " .. num(CO.fit_power) .. ")")
for _, NC in ipairs({N.cold, N.cold2}) do
  def(NC.field, cold_fold(NC) .. " + " .. cfg.regions.names.highland_cold)
  def(NC.high, "if(" .. on .. ", clamp(" .. NC.field .. " / " .. num(CO.high_at) .. ", 0, 1) * " .. N.gate .. ", 0)")
  -- The start disc takes the field down from inside, so the outline's noise acts on its edge: an offset on the cap drew
  -- a razor arc round the spawn, which at scale 1 cuts through a range.
  def(NC.gated, NC.field .. " - " .. num(CO.start_fall) .. " * (1 - " .. N.gate .. ")")
end
def(N.cold.cap, "if(" .. on .. ", max(" .. num(CO.floor_t) .. ", " .. num(CO.top_t) .. " - " ..
  num((CO.top_t - CO.snow_t) / CO.snow_at) .. " * " .. N.cold.gated .. "), " .. num(CO.off) .. ")")
-- The second cap (0.3.0): inside the snow edge (field fs) it falls as the first, up to steep times faster where the
-- ragged factor is under grey_w, so the snow's frayed edge thins where the rim breaks; outside, it rises to top_t
-- across the grey rim, band times the factor in field units, and on past it, where it no longer binds (ridges.cold).
local FS = CO.snow_at * CO.top_t / (CO.top_t - CO.snow_t)
local RAG = cfg.climate.ragged.name
def(N.cold2.cap, "if(" .. on .. ", max(" .. num(CO.floor_t) .. ", (" .. num(FS) .. " - g) * if(g > " .. num(FS) ..
  ", " .. num((CO.top_t - CO.snow_t) / CO.snow_at) .. " * (1 + " .. num(CO.steep) .. " * (1 - min(1, " .. RAG ..
  " / " .. num(CO.grey_w) .. "))), " .. num(CO.top_t) .. " / max(" .. num(CO.band_min) .. ", " .. num(CO.band) ..
  " * " .. RAG .. "))), " .. num(CO.off) .. ")", {g = N.cold2.gated})
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
