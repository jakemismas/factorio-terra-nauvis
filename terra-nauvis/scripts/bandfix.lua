-- Exact coastlines (ARCHITECTURE.md, "Control stage"; milestone coast-band-fix; S12, S13-bandfix; design notes
-- 07:05, 12:35 and 13:45). The mod's only per-chunk handler. on_chunk_generated is registered only on a
-- save whose Nauvis surface carries the band-fix key (config.lua bandfix.key set to bandfix.on; absent
-- means off): on_init records the save's state once (storage.earth.bandfix) and both on_init and on_load
-- register from it, so a save made without the key never registers it, whatever the setting says later.
--
-- Per new chunk of the Nauvis surface, a pure function of the chunk's position, its generated tiles and
-- the shipped K+ data of the save's map and scale (scripts/generated/, tools/build_geo.py --bandfix): the
-- map's K+ table (its K pixels at every offered scale with the reference classes of their neighbours)
-- and the scale's mask table (the K+ pixels inside a waterway, canal, dam or basin footprint there):
--   1. the chunk's reference pixels: geo tile = world tile + the city offset read once in on_init, pixel
--      floor(geo / scale) + the map's radius, tile offset geo mod scale (the coordinate chain's frame);
--   2. a chunk with no K pixel returns before reading a tile;
--   3. per run of K pixels of one class on a pixel row, one tile query finds the tiles of the wrong class:
--      player-blocking water on land pixels, land on water pixels; kept tiles, the water a player walks, fords
--      and marsh water, are neither, so the right tiles of a coast cost nothing;
--   4. such a tile takes its pixel's class when it lies outside the spawn keep disc and the reference, blurred
--      by a quadratic B-spline over the pixel's 3 x 3, reads its pixel's class at it by more than
--      a threshold (bandfix.smooth): half a pixel from a straight coast, so the rule is S12's there, and the
--      line where a write stops is a rounded, wobbling curve instead of the raster's stairs. A pixel whose band
--      region holds no 2 x 2 block of tiles (an islet or a channel narrower than a pixel) is drawn as a blob
--      around its centre, whatever the blur reads there; below smooth.min_scale the rule is
--      S12's closed rule. Land of an open-sea pixel (no land around it) becomes deep water, and where the chunk
--      writes anything, so do those pixels' shallow tiles; in a chunk left with no land, all shallow tiles reading
--      open sea do; so a false island sinks without a pale patch or a ghost of its shallows;
--   5. the classes of the written tiles' bounding box are read once: a written tile that would stand as a
--      strip one tile wide takes its neighbour in the box along, when that neighbour belongs to the same
--      reference class;
--   6. one set_tiles call inside the chunk, without tile correction.
-- It writes only tiles the rule changes, so a repeated delivery writes nothing, and what it reads outside its
-- own chunk can only pick the name of a land tile, never land or water. No RNG, no player state, no storage
-- write. Decoded table rows are a cache of shipped data, so a joining peer that starts with an empty cache
-- computes the same tiles.
local cfg = require("prototypes.config")
local guards = require("scripts.guards")
local coastcover = require("scripts.coastcover")

-- One require per generated table (the registration scan reads literal module names): per map its K+
-- table and its mask table for every offered scale.
local TABLES = {
  europe = {
    shared = require("scripts.generated.bandfix_europe_v1"),
    scales = {
      require("scripts.generated.bandfix_europe_s1_v1"),
      require("scripts.generated.bandfix_europe_s2_v1"),
      require("scripts.generated.bandfix_europe_s3_v1"),
      require("scripts.generated.bandfix_europe_s4_v1"),
      require("scripts.generated.bandfix_europe_s5_v1"),
      require("scripts.generated.bandfix_europe_s6_v1"),
    },
  },
  atlantic = {
    shared = require("scripts.generated.bandfix_atlantic_v1"),
    scales = {
      require("scripts.generated.bandfix_atlantic_s1_v1"),
      require("scripts.generated.bandfix_atlantic_s2_v1"),
      require("scripts.generated.bandfix_atlantic_s3_v1"),
      require("scripts.generated.bandfix_atlantic_s4_v1"),
      require("scripts.generated.bandfix_atlantic_s5_v1"),
      require("scripts.generated.bandfix_atlantic_s6_v1"),
    },
  },
  olde_world = {
    shared = require("scripts.generated.bandfix_olde_world_v1"),
    scales = {
      require("scripts.generated.bandfix_olde_world_s1_v1"),
      require("scripts.generated.bandfix_olde_world_s2_v1"),
      require("scripts.generated.bandfix_olde_world_s3_v1"),
      require("scripts.generated.bandfix_olde_world_s4_v1"),
      require("scripts.generated.bandfix_olde_world_s5_v1"),
      require("scripts.generated.bandfix_olde_world_s6_v1"),
    },
  },
}

local M = {}
local B = cfg.bandfix
local MSG = cfg.messages
local floor, max, min = math.floor, math.max, math.min
local byte, rep, find, sub, gsub, concat = string.byte, string.rep, string.find, string.sub, string.gsub, table.concat
local band = bit32.band

local CT = B.chunk_tiles
local KEEP_R2 = B.spawn_keep_tiles * B.spawn_keep_tiles

-- The table encoding (config.lua bandfix): digits, the symbol of each role, what a symbol means, and the K
-- symbols as one pattern. A masked pixel keeps its class for the band but is never written.
local DIGIT, BASE = {}, B.varint_base
for k = 1, #B.alphabet do
  DIGIT[byte(B.alphabet, k)] = k - 1
end
local ORDER, NSYM = B.symbol_order, #B.symbol_order
local CHAR, BY = {}, {}
for k, role in ipairs(ORDER) do
  CHAR[k - 1] = B.symbols[role]
  BY[role] = byte(B.symbols[role])
end
local S = B.symbols
local NONE = BY.none
local LANDISH = {[BY.land] = true, [BY.land_k] = true, [BY.land_masked] = true}
local IS_K = {[BY.water_k] = true, [BY.land_k] = true}
local OPEN = {[BY.water] = true, [BY.land] = true, [BY.water_k] = true, [BY.land_k] = true}
local KPAT = "[" .. S.water_k .. S.land_k .. "]"
local MASKED = {[S.water] = S.water_masked, [S.water_k] = S.water_masked, [S.land] = S.land_masked,
                [S.land_k] = S.land_masked, [S.thin] = S.thin, [S.none] = S.none,
                [S.water_masked] = S.water_masked, [S.land_masked] = S.land_masked}

-- The save's state and what register() prepares from it: its tables, map, band and fill tables, tile lists,
-- the blurred reference's values per mask and tile offset, filled as tiles ask, and the wobble.
local STATE, SHARED, MASKS, MAP, LUT, THIN
local SMOOTH, THIN_CENTRE, WOBBLE = {}, {}, {}
local SM = B.smooth
local WP = SM.period_tiles
local WP_X, WP_Y = SM.shift_tiles[1], SM.shift_tiles[2]
-- A geography version with the soft map edge (edge = true) sinks land into deep water within
-- coast.edge_band.mask_px reference px of the box plus the side's margin table there, where the K+ table's
-- classes no longer hold: the handler writes nothing there (EDGE is mask_px, or 0 for a version without
-- the edge; EDGE_SIDE holds each side with a table as its reach per reference px along it).
local EDGE = 0
local EDGE_SIDE = {}
local WATER, KEEP, NONLAND, NONLAND_SET, FALLBACK = {}, {}, {}, {}, nil
local GROUND, GROUND_STAMP = nil, nil
-- The corner ground (config.lua bandfix.smooth.corners), on the maps it lists: CORNERS is that table.
local CORNERS, CORNER, CORNER_READ = nil, {}, {}

------------------------------------------------------------------------------------------------ the tables

-- One payload: its first column, then one varint per run, (length - 1) * n + value.
local function varints(payload)
  local vals, v, mul = {}, 0, 1
  for k = 1, #payload do
    local d = DIGIT[byte(payload, k)]
    if d >= BASE then
      v = v + (d - BASE) * mul
      mul = mul * BASE
    else
      vals[#vals + 1] = v + d * mul
      v, mul = 0, 1
    end
  end
  return vals
end

-- A shared row's symbols over its span, with the scale's masked runs applied.
local function decode(payload, masks)
  local vals = varints(payload)
  local parts = {}
  for k = 2, #vals do
    local x = vals[k]
    parts[#parts + 1] = rep(CHAR[x % NSYM], floor(x / NSYM) + 1)
  end
  local first, text = vals[1], concat(parts)
  if masks then
    local mv = varints(masks)
    local c = mv[1]
    for k = 2, #mv do
      local x = mv[k]
      local len = floor(x / 2) + 1
      if x % 2 == 1 then
        local a = c - first + 1
        text = sub(text, 1, a - 1) .. gsub(sub(text, a, a + len - 1), ".", MASKED) .. sub(text, a + len)
      end
      c = c + len
    end
  end
  return {first = first, text = text}
end

-- Decoded rows, at most B.row_cache of them: a ring of row indices evicts the oldest one at a time, so a
-- walk over more rows than that re-decodes only what it leaves behind.
local CACHE, RING, RING_AT, CACHE_FOR = {}, {}, 0, nil

-- The decoded row r of the save's tables, or false where the K+ table holds no pixel on that row.
local function row_at(r)
  if CACHE_FOR ~= MASKS then
    CACHE, RING, RING_AT, CACHE_FOR = {}, {}, 0, MASKS
  end
  local hit = CACHE[r]
  if hit then
    return hit
  end
  local payload = SHARED.rows[r]
  if not payload then
    return false
  end
  local row = decode(payload, MASKS.rows[r])
  RING_AT = RING_AT % B.row_cache + 1
  local old = RING[RING_AT]
  if old then
    CACHE[old] = nil
  end
  RING[RING_AT] = r
  CACHE[r] = row
  return row
end

local function sym_in(row, c)
  if not row then
    return NONE
  end
  local k = c - row.first + 1
  if k < 1 or k > #row.text then
    return NONE
  end
  return byte(row.text, k)
end

-- Whether a pixel's reference class is land; thin water and the area outside the raster count as water.
local function landish(c, r)
  if c < 0 or r < 0 or c >= MAP.width_px or r >= MAP.height_px then
    return false
  end
  return LANDISH[sym_in(row_at(r), c)] or false
end

-- The other-class mask of a pixel: one bit per neighbour (config.lua's order) of the other class.
local function other_mask(c, r, me)
  local m, bit = 0, 1
  for _, nb in ipairs(B.neighbours) do
    if landish(c + nb[1], r + nb[2]) ~= me then
      m = m + bit
    end
    bit = bit * 2
  end
  return m
end

-- Per tile offset (i, j) of a pixel at scale s, the neighbours whose squares lie closer than half a pixel
-- to its sample point, exact in units of 1 / (2 s) px (S12's band table; tools/build_geo.py builds it).
local function reach_lut(s)
  local half = floor(s / 2)
  local function g(d, k)
    local d2 = 2 * (k - half)
    if d == 0 then
      return 0
    elseif d == 1 then
      return s - d2
    end
    return d2 + s
  end
  local lut = {}
  for j = 0, s - 1 do
    for i = 0, s - 1 do
      local m, bit = 0, 1
      for _, nb in ipairs(B.neighbours) do
        local gx, gy = g(nb[1], i), g(nb[2], j)
        if gx * gx + gy * gy < s * s then
          m = m + bit
        end
        bit = bit * 2
      end
      lut[j * s + i] = m
    end
  end
  return lut
end

-- The reference at tile offset (i, j) of a pixel with other-class mask m, blurred by a quadratic B-spline over
-- the pixel's 3 x 3: 1 where all of it is the pixel's class, 0 on a straight coast, 3/4 half a pixel in.
local function smooth_at(m, j, i)
  local s = STATE.scale
  local half = floor(s / 2)
  local function weight(d, k)
    local u = (k - half) / s
    if d == 0 then
      return SM.spline_centre - u * u
    end
    local v = 1 / 2 + d * u
    return v * v / 2
  end
  local other, bit = 0, 1
  for _, nb in ipairs(B.neighbours) do
    if band(m, bit) ~= 0 then
      other = other + weight(nb[1], i) * weight(nb[2], j)
    end
    bit = bit * 2
  end
  return 1 - 2 * other
end

-- A smooth tile noise in -1 .. 1, periodic over WP tiles: value noise of SM.octaves, a pure function of its
-- lattice indices.
local function wobble_table()
  local out, H = {}, SM.hash
  local function lattice(n, i, j, seed)
    local h = ((i % n) * H.x + (j % n) * H.y + seed * H.seed) % H.modulus
    return (h * h * H.mix % H.modulus) / H.half - 1
  end
  local function ease(t)
    return t * t * (SM.ease - 2 * t)
  end
  for y = 0, WP - 1 do
    for x = 0, WP - 1 do
      local sum, norm = 0, 0
      for k, o in ipairs(SM.octaves) do
        local n = o.cells
        local cell = WP / n
        local fx, fy = x / cell, y / cell
        local ix, iy = floor(fx), floor(fy)
        local tx, ty = ease(fx - ix), ease(fy - iy)
        local a = lattice(n, ix, iy, k) * (1 - tx) + lattice(n, ix + 1, iy, k) * tx
        local b2 = lattice(n, ix, iy + 1, k) * (1 - tx) + lattice(n, ix + 1, iy + 1, k) * tx
        sum = sum + o.weight * (a * (1 - ty) + b2 * ty)
        norm = norm + o.weight
      end
      out[y * WP + x] = sum / norm
    end
  end
  return out
end

-- Per other-class mask (0 to 255), whether the band region holds no 2 x 2 block of tiles at scale s: such a
-- pixel is a fill pixel, written whole (tools/build_geo.py's thin_lut).
local function thin_lut(s, lut)
  local out = {}
  local masks = 2 ^ #B.neighbours
  for m = 0, masks - 1 do
    local open = {}
    for k = 0, s * s - 1 do
      open[k] = band(m, lut[k]) == 0
    end
    local block = false
    for j = 0, s - 2 do
      for i = 0, s - 2 do
        local k = j * s + i
        if open[k] and open[k + 1] and open[k + s] and open[k + s + 1] then
          block = true
        end
      end
    end
    out[m] = not block
  end
  return out
end

------------------------------------------------------------------------------------------------ one chunk

-- Per-chunk scratch, reused: marks stamped with the current chunk, so a new stamp clears them.
local stamp = 0
local WET, KEPT, WROTE, WLAND, WDEEP, PM_STAMP, PM_MASK = {}, {}, {}, {}, {}, {}, {}
local SEA = {}
local QX, QY = {}, {}
local NWET, MARKS_WET, NW = 0, true, 0
local GX0, GY0, X0, Y0, C0, R0, WW, NEAR = 0, 0, 0, 0, 0, 0, 0, false
-- The window's runs of K pixels of one class: pixel row RR[q], columns RA[q]..RB[q], class RL[q], NRUN of them.
-- BX0..BX1, BY0..BY1 are the chunk tiles step 5 reads, NB of them.
local RR, RA, RB, RL = {}, {}, {}, {}
local NRUN = 0
local BX0, BX1, BY0, BY1, NB = 0, 0, 0, 0, 0
local AREA = {{0, 0}, {0, 0}}
local F_WET, F_LAND, F_SHALLOW = {area = AREA}, {area = AREA, invert = true}, {area = AREA}

-- The box's generated classes: its player-blocking water tiles (or, where water is the majority, the
-- others) and its kept tiles are marked once.
local function read_tiles(surface, area)
  NWET = surface.count_tiles_filtered{area = area, name = WATER}
  MARKS_WET = true
  if NWET > 0 and NWET < NB then
    local list
    if NWET * 2 > NB then
      list = surface.find_tiles_filtered{area = area, name = WATER, invert = true}
      MARKS_WET = false
    else
      list = surface.find_tiles_filtered{area = area, name = WATER}
    end
    for k = 1, #list do
      local p = list[k].position
      WET[(p.y - Y0) * CT + p.x - X0] = stamp
    end
  end
  if #KEEP > 0 and surface.count_tiles_filtered{area = area, name = KEEP} > 0 then
    for _, t in ipairs(surface.find_tiles_filtered{area = area, name = KEEP}) do
      local p = t.position
      KEPT[(p.y - Y0) * CT + p.x - X0] = stamp
    end
  end
end

local function generated_wet(idx)
  if NWET == 0 then
    return false
  elseif NWET == NB then
    return true
  end
  return (WET[idx] == stamp) == MARKS_WET
end

local function post_wet(idx)
  if WROTE[idx] == stamp then
    return not WLAND[idx]
  end
  return generated_wet(idx)
end

-- The chunk's window: the geo tile of its corner and pixel columns c0..c1, rows r0..r1.
local function window(chx, chy)
  local s = STATE.scale
  local gx0, gy0 = chx * CT + STATE.cx, chy * CT + STATE.cy
  local c0, c1 = floor(gx0 / s) + MAP.wr, floor((gx0 + CT - 1) / s) + MAP.wr
  local r0, r1 = floor(gy0 / s) + MAP.hr, floor((gy0 + CT - 1) / s) + MAP.hr
  return gx0, gy0, c0, c1, r0, r1
end

-- Whether world tile (x, y) of the chunk lies inside the spawn keep disc.
local function kept_by_spawn(lx, ly)
  if not NEAR then
    return false
  end
  local x, y = X0 + lx, Y0 + ly
  return x * x + y * y < KEEP_R2
end

local function mark_write(idx, lx, ly, land, open_sea)
  WROTE[idx], WLAND[idx], WDEEP[idx] = stamp, land, open_sea
  NW = NW + 1
  QX[NW], QY[NW] = lx, ly
end

-- The other-class mask of pixel (c, r) of the window, computed once per chunk.
local function pixel_mask(c, r, land)
  local k = (r - R0) * WW + (c - C0)
  if PM_STAMP[k] ~= stamp then
    PM_STAMP[k], PM_MASK[k] = stamp, other_mask(c, r, land)
  end
  return PM_MASK[k]
end

-- Each px along a side, its reach: mask_px plus the table's knots read piecewise linearly, rounded up, as
-- earth_test.py's edge_band_reach. Module state rebuilt from config.lua on every load, so no save holds it.
local function side_reach(knots, n)
  local out, k = {}, 2
  for a = 0, n - 1 do
    while k < #knots and a >= knots[k][1] do
      k = k + 1
    end
    local a0, v0, a1, v1 = knots[k - 1][1], knots[k - 1][2], knots[k][1], knots[k][2]
    local t = (a - a0) / (a1 - a0)
    t = t < 0 and 0 or t > 1 and 1 or t
    out[a] = EDGE + math.ceil(v0 + t * (v1 - v0))
  end
  return out
end

-- Whether reference pixel (c, r) lies in the soft edge band of the save's geography version.
local function in_edge(c, r)
  if EDGE == 0 then
    return false
  end
  local L, T, R, B_ = EDGE_SIDE.left, EDGE_SIDE.top, EDGE_SIDE.right, EDGE_SIDE.bottom
  return c < (L and L[r] or EDGE) or r < (T and T[c] or EDGE)
    or c >= MAP.width_px - (R and R[r] or EDGE) or r >= MAP.height_px - (B_ and B_[c] or EDGE)
end

-- Whether pixel (c, r) is open sea: water with no land among its 8 neighbours. A pixel outside the K+ table reads
-- as water, so deep water can come one pixel nearer such land, never onto it. Computed once per chunk.
local function open_sea(c, r)
  local k = r * MAP.width_px + c
  local sea = SEA[k]
  if sea == nil then
    sea = not landish(c, r) and other_mask(c, r, false) == 0
    SEA[k] = sea
  end
  return sea
end

-- Whether geo tile (gx, gy) reads open sea, its pixel looked up through the wobble (half a pixel, typically), so
-- the line between shallow and deep water does not draw the raster's squares.
local function sea_at(gx, gy)
  local s = STATE.scale
  local dx, dy = WOBBLE[gy % WP * WP + gx % WP], WOBBLE[(gy + WP_Y) % WP * WP + (gx + WP_X) % WP]
  return open_sea(floor(gx / s + dx) + MAP.wr, floor(gy / s + dy) + MAP.hr)
end

-- Step 2: the runs of K pixels of the window's columns C0..c1 and rows R0..r1 outside the edge band; returns
-- false when there are none.
local function collect_k(c1, r1)
  NRUN = 0
  for r = R0, r1 do
    local row = row_at(r)
    if row then
      local a, b = C0 - row.first + 1, c1 - row.first + 1
      if a < 1 then
        a = 1
      end
      local seg = b >= a and sub(row.text, a, b) or ""
      if find(seg, KPAT) then
        local base = row.first + a - 2
        local open = false
        for k = 1, #seg do
          local code = byte(seg, k)
          local c = base + k
          if IS_K[code] and not in_edge(c, r) then
            local land = LANDISH[code] or false
            if open and RL[NRUN] == land then
              RB[NRUN] = c
            else
              NRUN = NRUN + 1
              RR[NRUN], RA[NRUN], RB[NRUN], RL[NRUN] = r, c, c, land
              open = true
            end
          else
            open = false
          end
        end
      end
    end
  end
  return NRUN > 0
end

-- Whether geo tile (gx, gy), jrow = its row inside its pixel times the scale, lies outside the band of a pixel
-- with other-class mask m (step 4).
local function outside(m, jrow, gx, gy)
  local s = STATE.scale
  if s < SM.min_scale then
    return THIN[m] or band(m, LUT[jrow + gx % s]) == 0
  end
  local key = m * s * s + jrow + gx % s
  local v = SMOOTH[key]
  if not v then
    v = smooth_at(m, jrow / s, gx % s)
    SMOOTH[key] = v
  end
  if THIN[m] then
    local c = THIN_CENTRE[m]
    if not c then
      c = smooth_at(m, floor(s / 2), floor(s / 2)) - SM.thin
      THIN_CENTRE[m] = c
    end
    return v >= c
  end
  return v >= SM.threshold + SM.wobble * WOBBLE[gy % WP * WP + gx % WP]
end

-- The world area of run q's tiles inside the chunk, into AREA.
local function run_area(q)
  local s = STATE.scale
  local gy0 = (RR[q] - MAP.hr) * s
  local lx0, lx1 = max((RA[q] - MAP.wr) * s - GX0, 0), min((RB[q] - MAP.wr + 1) * s - 1 - GX0, CT - 1)
  local ly0, ly1 = max(gy0 - GY0, 0), min(gy0 + s - 1 - GY0, CT - 1)
  AREA[1][1], AREA[1][2], AREA[2][1], AREA[2][2] = X0 + lx0, Y0 + ly0, X0 + lx1 + 1, Y0 + ly1 + 1
end

-- Steps 3 and 4 on run q.
local function scan_run(surface, q)
  local s = STATE.scale
  local r, land = RR[q], RL[q]
  local gy0 = (r - MAP.hr) * s
  run_area(q)
  local list = surface.find_tiles_filtered(land and F_WET or F_LAND)
  for k = 1, #list do
    local p = list[k].position
    local lx, ly = p.x - X0, p.y - Y0
    if not kept_by_spawn(lx, ly) then
      local gx = GX0 + lx
      local c = floor(gx / s) + MAP.wr
      if not land and sea_at(gx, GY0 + ly) then
        mark_write(ly * CT + lx, lx, ly, false, true)
      elseif outside(pixel_mask(c, r, land), (ly + GY0 - gy0) * s, gx, GY0 + ly) then
        mark_write(ly * CT + lx, lx, ly, land, false)
      end
    end
  end
end

-- The shallow tiles in AREA that read open sea go deep.
local function sink_area(surface)
  local list = surface.find_tiles_filtered(F_SHALLOW)
  for k = 1, #list do
    local p = list[k].position
    local lx, ly = p.x - X0, p.y - Y0
    local idx = ly * CT + lx
    if WROTE[idx] ~= stamp and sea_at(GX0 + lx, GY0 + ly) and not kept_by_spawn(lx, ly) then
      mark_write(idx, lx, ly, false, true)
    end
  end
end

-- Where the chunk writes, the shallow tiles of its open-sea pixels go deep too. In a chunk left with no land, every
-- shallow tile that reads open sea does, written or not: the rim of a false spit outlives the spit.
local function sink_shallows(surface)
  local sunk, wrote_land = 0, false
  for q = 1, NW do
    if WLAND[QY[q] * CT + QX[q]] then
      wrote_land = true
    else
      sunk = sunk + 1
    end
  end
  if NW > 0 then
    for q = 1, NRUN do
      if not RL[q] then
        run_area(q)
        sink_area(surface)
      end
    end
  end
  AREA[1][1], AREA[1][2], AREA[2][1], AREA[2][2] = X0, Y0, X0 + CT, Y0 + CT
  if not wrote_land and surface.count_tiles_filtered(F_LAND) <= sunk then
    sink_area(surface)
  end
end

-- The reference class of the pixel holding chunk tile (lx, ly), for a written tile's neighbour: true for
-- land, false for water, nil where the pixel may not be written (outside K+, thin water, masked).
local function open_class(lx, ly)
  local s = STATE.scale
  local gx, gy = GX0 + lx, GY0 + ly
  local c, r = floor(gx / s) + MAP.wr, floor(gy / s) + MAP.hr
  local code = sym_in(row_at(r), c)
  if not OPEN[code] or in_edge(c, r) then
    return nil
  end
  return LANDISH[code] or false
end

local function writable(n, nx, ny, land)
  return WROTE[n] ~= stamp and KEPT[n] ~= stamp and not kept_by_spawn(nx, ny) and open_class(nx, ny) == land
end

-- Step 5: a written tile whose neighbours along one axis inside the box all hold the other class takes one
-- of them along (the + side first), when that neighbour may be written to the same class.
local function extend_axis(q, dx, dy)
  local lx, ly = QX[q], QY[q]
  local wet = post_wet(ly * CT + lx)
  local ax, ay, bx, by = lx + dx, ly + dy, lx - dx, ly - dy
  local a_in = ax >= BX0 and ax <= BX1 and ay >= BY0 and ay <= BY1
  local b_in = bx >= BX0 and bx <= BX1 and by >= BY0 and by <= BY1
  local a, b = ay * CT + ax, by * CT + bx
  if (a_in and post_wet(a) == wet) or (b_in and post_wet(b) == wet) then
    return
  end
  if a_in and writable(a, ax, ay, not wet) then
    mark_write(a, ax, ay, not wet, false)
  elseif b_in and writable(b, bx, by, not wet) then
    mark_write(b, bx, by, not wet, false)
  end
end

-- The land near written land on a world lattice reaching past the chunk (config.lua bandfix.smooth.corners), each
-- node grown over reach steps: a node's value depends only on nodes within reach of it, all of them read by every
-- chunk that holds the node, so chunks agree along their borders. Only every other node is read, by world parity,
-- so every chunk reads the same nodes for half the calls; the first step fills the rest.
local function shared_lattice(surface)
  local step, reach = CORNERS.step, CORNERS.reach
  local margin = reach + 1
  local n = floor(CT / step) + 1 + 2 * margin
  local x0, y0 = X0 - margin * step, Y0 - margin * step
  local odd = floor(x0 / step) + floor(y0 / step)
  local cells = {}
  for j = 0, n - 1 do
    for i = (odd + j) % 2, n - 1, 2 do
      local t = surface.get_tile(x0 + i * step, y0 + j * step)
      local name = t.valid and t.name
      if name and not NONLAND_SET[name] and name ~= "out-of-map" then
        cells[j * n + i] = name
      end
    end
  end
  for _ = 1, reach do
    local grown = {}
    for j = 0, n - 1 do
      for i = 0, n - 1 do
        local k = j * n + i
        grown[k] = cells[k] or (i > 0 and cells[k - 1]) or (i < n - 1 and cells[k + 1]) or
          (j > 0 and cells[k - n]) or (j < n - 1 and cells[k + n]) or nil
      end
    end
    cells = grown
  end
  return cells, n, step, margin
end

-- The land tile for written land: the nearest land on a lattice of the chunk's generated tiles, so a written
-- strip carries on the ground beside it; FALLBACK in a chunk whose lattice holds no land.
local function land_lattice(surface)
  if CORNERS then
    return shared_lattice(surface)
  end
  local step, n = SM.lattice_tiles, floor(CT / SM.lattice_tiles) + 1
  local cells, found = {}, 0
  for j = 0, n - 1 do
    for i = 0, n - 1 do
      local name = surface.get_tile(X0 + min(i * step, CT - 1), Y0 + min(j * step, CT - 1)).name
      if not NONLAND_SET[name] then
        cells[j * n + i] = name
        found = found + 1
      end
    end
  end
  local total = n * n
  while found > 0 and found < total do
    local grown = {}
    for j = 0, n - 1 do
      for i = 0, n - 1 do
        local k = j * n + i
        local name = cells[k] or (i > 0 and cells[k - 1]) or (i < n - 1 and cells[k + 1]) or
          (j > 0 and cells[k - n]) or (j < n - 1 and cells[k + n])
        grown[k] = name or nil
      end
    end
    cells, found = grown, 0
    for _ in pairs(cells) do
      found = found + 1
    end
  end
  return cells, n, step, 0
end

-- The land tile for a chunk whose lattice holds no land: the first land on rings of samples around it, inside the
-- 7 x 7 chunks the game has given tiles (worldgen-runtime), or FALLBACK, once per chunk. A sample can read land this
-- handler wrote there, so the ground of such a chunk can follow generation order; its land and water cannot.
local function chunk_ground(surface)
  if GROUND_STAMP == stamp then
    return GROUND
  end
  GROUND_STAMP, GROUND = stamp, FALLBACK
  for ring = 1, B.ground_rings do
    for dy = -1, 1 do
      for dx = -1, 1 do
        local t = surface.get_tile(X0 + CT / 2 + dx * ring * CT, Y0 + CT / 2 + dy * ring * CT)
        if t.valid and not NONLAND_SET[t.name] then
          GROUND = t.name
          return GROUND
        end
      end
    end
  end
  return GROUND
end

-- The first land on rings of samples around one chunk corner. Every chunk that meets at the corner reads the same
-- samples, so what they write there meets without a seam.
local function corner_sample(surface, cx, cy)
  for _, r in ipairs(CORNERS.rings) do
    for dy = -1, 1 do
      for dx = -1, 1 do
        local t = surface.get_tile(cx + dx * r, cy + dy * r)
        local name = t.valid and t.name
        if name and not NONLAND_SET[name] and name ~= "out-of-map" then
          return name
        end
      end
    end
  end
  return nil
end

-- The ground of written land out of reach of the chunk's own lattice: the nearest of the chunk's four corners, the
-- borders between them wandering with the wobble, so a chunk's edge always takes its own corners and no chunk
-- is a rectangle of one tile (config.lua bandfix.smooth.corners).
local function corner_at(surface, i, j)
  local k = j * 2 + i
  if CORNER_READ[k] ~= stamp then
    CORNER_READ[k] = stamp
    CORNER[k] = corner_sample(surface, X0 + i * CT, Y0 + j * CT)
  end
  return CORNER[k]
end

local function corner_ground(surface, lx, ly)
  local x, y = X0 + lx, Y0 + ly
  local half = 1 / 2
  local i = (lx + half) / CT + CORNERS.wander * WOBBLE[y % WP * WP + x % WP] >= half and 1 or 0
  local j = (ly + half) / CT + CORNERS.wander * WOBBLE[(y + WP_Y) % WP * WP + (x + WP_X) % WP] >= half and 1 or 0
  return corner_at(surface, i, j) or corner_at(surface, 1 - i, j) or corner_at(surface, i, 1 - j) or
    corner_at(surface, 1 - i, 1 - j)
end

local RECS = {}

-- Step 6: one set_tiles call; written land takes the ground around it, and written water is deep in an open-sea
-- pixel, so a false island sinks into the open sea without a pale patch.
local function write(surface)
  local cells, n, step, margin
  for q = 1, NW do
    local lx, ly = QX[q], QY[q]
    local idx = ly * CT + lx
    local name = WDEEP[idx] and B.new_deep or B.new_water
    if WLAND[idx] then
      if not cells then
        cells, n, step, margin = land_lattice(surface)
      end
      local rx, ry = lx, ly
      if CORNERS then
        -- read the lattice a little off the tile, so no 4 x 4 block of a node shows
        local x, y = X0 + lx, Y0 + ly
        rx = lx + step * WOBBLE[y % WP * WP + x % WP]
        ry = ly + step * WOBBLE[(y + WP_Y) % WP * WP + (x + WP_X) % WP]
      end
      name = cells[(floor((ry + step / 2) / step) + margin) * n + floor((rx + step / 2) / step) + margin] or
        (CORNERS and corner_ground(surface, lx, ly)) or chunk_ground(surface)
    end
    local rec = RECS[q]
    if rec then
      rec.name = name
      rec.position[1], rec.position[2] = X0 + lx, Y0 + ly
    else
      RECS[q] = {name = name, position = {X0 + lx, Y0 + ly}}
    end
  end
  for q = #RECS, NW + 1, -1 do
    RECS[q] = nil
  end
  local cover = coastcover.read(surface, X0, Y0, RECS, NW, NONLAND_SET, NONLAND)
  surface.set_tiles(RECS, false, true, true, false)
  if cover then
    coastcover.place(surface, X0 / CT, Y0 / CT)
  end
end

-- Plans the tiles one chunk needs written (steps 1 to 5) into QX, QY and WLAND, NW of them.
local function plan_chunk(surface, chx, chy)
  local c1, r1
  GX0, GY0, C0, c1, R0, r1 = window(chx, chy)
  NW = 0
  stamp = stamp + 1
  WW = c1 - C0 + 1
  if not collect_k(c1, r1) then
    return
  end
  SEA = {}
  X0, Y0 = chx * CT, chy * CT
  local dx = X0 > 0 and X0 or (X0 + CT - 1 < 0 and -(X0 + CT - 1) or 0)
  local dy = Y0 > 0 and Y0 or (Y0 + CT - 1 < 0 and -(Y0 + CT - 1) or 0)
  NEAR = dx * dx + dy * dy < KEEP_R2
  for q = 1, NRUN do
    scan_run(surface, q)
  end
  sink_shallows(surface)
  if NW == 0 then
    return
  end
  local x0, x1, y0, y1 = CT, -1, CT, -1
  for q = 1, NW do
    local lx, ly = QX[q], QY[q]
    x0, x1, y0, y1 = min(x0, lx), max(x1, lx), min(y0, ly), max(y1, ly)
  end
  BX0, BX1, BY0, BY1 = max(x0 - 2, 0), min(x1 + 2, CT - 1), max(y0 - 2, 0), min(y1 + 2, CT - 1)
  NB = (BX1 - BX0 + 1) * (BY1 - BY0 + 1)
  read_tiles(surface, {{X0 + BX0, Y0 + BY0}, {X0 + BX1 + 1, Y0 + BY1 + 1}})
  local q = 1
  while q <= NW do
    extend_axis(q, 1, 0)
    extend_axis(q, 0, 1)
    q = q + 1
  end
end

local function fix_chunk(surface, chx, chy)
  plan_chunk(surface, chx, chy)
  if NW > 0 then
    write(surface)
  end
  return NW
end

------------------------------------------------------------------------------------------------ lifecycle

local function map_of(id)
  for _, key in ipairs(cfg.map_order) do
    if cfg.maps[key].id == id then
      return key
    end
  end
  return nil
end

local function listed(list, v)
  for _, x in ipairs(list or {}) do
    if x == v then
      return true
    end
  end
  return false
end

-- The tile lists, from the prototypes: player-blocking water (water_tile and player layers, placed by an
-- autoplace, as T1 counts water) and kept water (water_tile without the player layer: fords, marsh water).
local function tile_lists()
  WATER, KEEP, NONLAND = {}, {}, {}
  for name, t in pairs(prototypes.tile) do
    local layers = t.collision_mask.layers
    if layers.water_tile then
      if not layers.player then
        KEEP[#KEEP + 1] = name
        NONLAND[#NONLAND + 1] = name
      elseif t.autoplace_specification then
        WATER[#WATER + 1] = name
        NONLAND[#NONLAND + 1] = name
      end
    end
  end
  table.sort(WATER)
  table.sort(KEEP)
  table.sort(NONLAND)
  F_WET.name, F_LAND.name, F_SHALLOW.name = WATER, NONLAND, B.new_water
  NONLAND_SET = {}
  for _, name in ipairs(NONLAND) do
    NONLAND_SET[name] = true
  end
  FALLBACK = B.land_fallback
  if not prototypes.tile[FALLBACK] then
    local names = {}
    for name, t in pairs(prototypes.tile) do
      if t.autoplace_specification and not t.collision_mask.layers.water_tile then
        names[#names + 1] = name
      end
    end
    table.sort(names)
    FALLBACK = names[1]
  end
end

-- What the handler reads from the save's state; false when the shipped data does not serve it.
local function prepare(st)
  local tabs = TABLES[st.map]
  local m = cfg.maps[st.map]
  local masks = tabs and tabs.scales[st.scale]
  if not (masks and m and tabs.shared.width == m.width_px and tabs.shared.height == m.height_px
          and masks.scale == st.scale) then
    log("Terra Nauvis: Exact coastlines has no table for this save's map and scale; the handler stays off")
    return false
  end
  STATE, SHARED, MASKS, MAP = st, tabs.shared, masks, m
  local gv = guards.geography_of(st.geo)
  EDGE = (gv and gv.version and gv.version.edge) and cfg.coast.edge_band.mask_px or 0
  CORNERS = SM.corners.maps[st.map] and SM.corners or nil
  LUT = reach_lut(st.scale)
  THIN = thin_lut(st.scale, LUT)
  SMOOTH, THIN_CENTRE, WOBBLE = {}, {}, wobble_table()
  tile_lists()
  coastcover.prepare()
  return true
end

local function register()
  local earth = storage.earth
  local st = earth and earth.bandfix
  if st and prepare(st) then
    script.on_event(defines.events.on_chunk_generated, M.on_chunk_generated)
  end
end

-- The save's band-fix state from its own Nauvis surface: nil unless the key is on and the shipped tables
-- serve its map, scale and geography (config.lua bandfix.tables). The city offset names are those of the
-- save's own geography version (its tn_geo, guards.geography_of), never the newest.
function M.state(surface, earth)
  local pen = surface.map_gen_settings.property_expression_names or {}
  if pen[B.key] ~= B.on then
    return nil
  end
  local key = map_of(earth.map)
  local geo = guards.geography_of(earth.geo)
  local g = key and geo and geo.map == key and geo.version
  local spec = key and (B.tables or {})[key]
  local tabs = key and TABLES[key]
  if not (g and spec and tabs and earth.scale and tabs.scales[earth.scale] and listed(spec.geographies, earth.geo)) then
    log("Terra Nauvis: the save carries the Exact coastlines key, but no shipped table serves its map, scale and "
        .. "geography; the handler stays off")
    return nil
  end
  local p = surface.calculate_tile_properties({g.cx, g.cy}, {{0, 0}})
  local cx, cy = p[g.cx] and p[g.cx][1], p[g.cy] and p[g.cy][1]
  if not (cx and cy) then
    log("Terra Nauvis: Exact coastlines could not read the city offset; the handler stays off")
    return nil
  end
  return {surface = surface.index, map = key, scale = earth.scale, geo = earth.geo,
          cx = floor(cx + 1 / 2), cy = floor(cy + 1 / 2)}
end

-- on_init, after guards.on_init has detected an Earth world and filled storage.earth.
function M.on_init()
  local earth = storage.earth
  local surface = game.surfaces["nauvis"]
  if not (earth and surface) then
    return
  end
  earth.bandfix = M.state(surface, earth) or false
  if earth.bandfix then
    log("Terra Nauvis: Exact coastlines on for this save (" .. earth.bandfix.map .. ", scale " ..
        earth.bandfix.scale .. ")")
  end
  register()
end

-- on_load: register again from the saved state; storage is read, never written (mod-dev rule 9).
function M.on_load()
  register()
end

-- Returns the tiles written (the event system ignores it; the checks' probe counts it).
function M.on_chunk_generated(e)
  if STATE and e.surface.index == STATE.surface then
    return fix_chunk(e.surface, e.position.x, e.position.y)
  end
  return 0
end

-- The tiles one chunk would have written now, without writing them (the checks' recheck: 0 once the
-- handler has run on it). tools/earth_test.py reads it from a staged test copy of the mod.
function M.pending(surface, chx, chy)
  if not STATE then
    return 0
  end
  plan_chunk(surface, chx, chy)
  return NW
end

-- The drift line (on_configuration_changed with changed startup settings): an Earth world keeps its key,
-- so where the setting now bakes something else for this world's map, one info line says so. The setting
-- acts only on the maps bandfix.maps lists; on any other map it changes nothing to report.
function M.on_configuration_changed(data)
  local earth, surface = storage.earth, game.surfaces["nauvis"]
  if not (data.mod_startup_settings_changed and earth and surface) then
    return
  end
  local key = map_of(earth.map)
  if not (key and listed(B.maps, key)) then
    return
  end
  local pen = surface.map_gen_settings.property_expression_names or {}
  local setting = cfg.settings[B.setting].name
  local was = pen[B.key] == B.on
  local now = settings.startup[setting].value == true
  if was ~= now then
    local function state(on)
      return {MSG.section .. "." .. MSG.keys[on and "toggle_on" or "toggle_off"]}
    end
    local msg = {MSG.section .. "." .. MSG.keys.drift_toggle, {"mod-setting-name." .. setting}, state(was), state(now)}
    log(msg)
    game.print(msg)
  end
end

return M
