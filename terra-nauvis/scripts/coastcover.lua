-- Cover for the land Exact coastlines writes (scripts/bandfix.lua step 7; config.lua coastcover;
-- 2026-10-30 16:20). The game generates trees, rocks and decoratives before the handler runs, so land the
-- handler writes over generated water stays bare. This module gives it the cover of the land beside it:
--   read, before the tiles are written: the box around the written land, inside the chunk and clear of its edge
--     band, holds the generated land the cover is copied from. Its land tiles, its trees and rocks and its
--     decoratives give a rate per tile and a sample to draw from. A read stops at a limit, so a dense forest costs
--     what a sparse one does. A chunk with no land of its own reads a generated neighbour instead.
--   place, after they are written: a generator seeded from the map seed and the chunk draws per written land
--     tile whether it takes an entity and how many decoratives, each from the sample, kept only when the
--     prototype's tile_restriction allows the ground the tile took.
-- In a chunk with land of its own everything read lies in the chunk, and an entity keeps coastcover.edge_gap clear
-- of the chunk's edge, so the cover is a pure function of the chunk's own generated state. That state can follow
-- generation order, as the game's own trees and decoratives do (DECISIONS 2026-10-30 coastcover). No storage
-- write: each chunk makes its own generator, and the prototype facts are a cache.
-- regenerate_entity and regenerate_decorative are not an option: on Old World they cost 7 to 90 ms a chunk and
-- place over the whole chunk (DECISIONS 2026-10-30 coastcover).
local cfg = require("prototypes.config")

local M = {}
local CV = cfg.coastcover
local CT = cfg.bandfix.chunk_tiles
local H = CV.hash
local ceil, floor, max, min = math.ceil, math.floor, math.max, math.min

local RNG, SEED = nil, nil
-- Prototype facts by name: the grounds an autoplace allows (true: any, false: no autoplace), an entity's margin.
local GROUNDS_E, GROUNDS_D, MARGIN = {}, {}, {}

-- The scratch of one chunk, filled by read and used by place.
local LAND, NLAND = {}, 0
local NAMES, NE, RATE_E = {}, 0, 0
local DECOS, ND, RATE_D = {}, 0, 0
local OUT = {}
local BOX = {{0, 0}, {0, 0}}
local F_COUNT = {area = BOX, invert = true}
local F_ENTS = {area = BOX, type = CV.types, limit = CV.entity_limit}
local F_ENTS_ALL = {area = BOX, type = CV.types}
local F_DECOS = {area = BOX, limit = CV.decorative_limit}

-- The grounds an autoplace allows: a set of tile names, true for any ground, false without an autoplace.
local function grounds(spec)
  if not spec then
    return false
  end
  local list = spec.tile_restriction
  if not list then
    return true
  end
  local set = {}
  for _, r in ipairs(list) do
    if r.first then
      set[r.first] = true
    end
    if r.second then
      set[r.second] = true
    end
  end
  return set
end

-- Fills the prototype facts once, at load: reading an autoplace is slow, and a chunk must never pay for it.
function M.prepare()
  for name, p in pairs(prototypes.get_entity_filtered{{filter = "type", type = CV.types}}) do
    GROUNDS_E[name] = grounds(p.autoplace_specification)
    local b = p.collision_box
    MARGIN[name] = max(-b.left_top.x, -b.left_top.y, b.right_bottom.x, b.right_bottom.y) + CV.edge_gap
  end
  for name, p in pairs(prototypes.decorative) do
    GROUNDS_D[name] = grounds(p.autoplace_specification)
  end
end

local function set_box(a, x0, y0, x1, y1)
  a[1][1], a[1][2], a[2][1], a[2][2] = x0, y0, x1, y1
end

-- The per-chunk seed, hashed first: seeds close together roll alike (factorio-worldgen-runtime rule 7).
local function chunk_seed(cx, cy)
  local h = SEED % H.modulus
  h = (h * H.mul + H.add + (cx % H.coord) * H.x) % H.modulus
  h = (h * H.mul + H.add + (cy % H.coord) * H.y) % H.modulus
  h = (h * H.mul + H.add) % H.modulus
  return H.floor + h % (H.modulus - H.floor)
end

-- The land tiles of a box of tiles, which the box and every read after it then use.
local function land_in(surface, bx0, by0, bx1, by1)
  set_box(BOX, bx0, by0, bx1 + 1, by1 + 1)
  return surface.count_tiles_filtered(F_COUNT)
end

-- Decoratives come dear, so they are read from the middle rows of the box, about decorative_land tiles of land,
-- unless that holds too little land. The game also returns decoratives whose collision box reaches the area, so
-- those outside it, perhaps a neighbour's, are dropped; the rate is theirs over the land counted for the same box.
local function read_decoratives(surface, bx0, by0, bx1, by1, land)
  local rows = by1 - by0 + 1
  local keep = max(ceil(rows * min(CV.decorative_land / land, 1)), 1)
  local top = by0 + floor((rows - keep) / 2)
  if keep < rows then
    local part = land_in(surface, bx0, top, bx1, top + keep - 1)
    if part < CV.min_land_tiles then
      land_in(surface, bx0, by0, bx1, by1)
    else
      land, by0, by1 = part, top, top + keep - 1
    end
  end
  local found = surface.find_decoratives_filtered(F_DECOS)
  for k = 1, #found do
    local d = found[k]
    local p = d.position
    if p.x >= bx0 and p.x <= bx1 and p.y >= by0 and p.y <= by1 then
      ND = ND + 1
      DECOS[ND] = d
    end
  end
  RATE_D = ND / land
end

-- A chunk with no land of its own reads the generated neighbour with the most land, the same way the band fix
-- takes such a chunk's ground from around it. Its cover can follow generation order; its land and water cannot.
local function neighbour_box(surface, x0, y0)
  local best, bx, by, g = 0, nil, nil, CV.inset_tiles
  for _, nb in ipairs(cfg.bandfix.neighbours) do
    local nx, ny = x0 + nb[1] * CT, y0 + nb[2] * CT
    if surface.is_chunk_generated({nx / CT, ny / CT}) then
      local n = land_in(surface, nx + g, ny + g, nx + CT - 1 - g, ny + CT - 1 - g)
      if n > best then
        best, bx, by = n, nx, ny
      end
    end
  end
  if best == 0 then
    return 0
  end
  local x1, y1 = bx + CT - 1 - g, by + CT - 1 - g
  land_in(surface, bx + g, by + g, x1, y1)
  return best, bx + g, by + g, x1, y1
end

-- Before set_tiles: the generated cover around the written land of the chunk at world tile (x0, y0). recs are
-- the records set_tiles will take, n of them; nonland_set and nonland the tiles that are not land. Returns
-- whether place has anything to do.
function M.read(surface, x0, y0, recs, n, nonland_set, nonland)
  local bx0, bx1, by0, by1 = x0 + CT, x0 - 1, y0 + CT, y0 - 1
  NLAND = 0
  for q = 1, n do
    local r = recs[q]
    if not nonland_set[r.name] then
      NLAND = NLAND + 1
      LAND[NLAND] = r
      local x, y = r.position[1], r.position[2]
      bx0, bx1, by0, by1 = min(bx0, x), max(bx1, x), min(by0, y), max(by1, y)
    end
  end
  if NLAND == 0 then
    return false
  end
  local R, g = CV.reach_tiles, CV.inset_tiles
  local lo_x, hi_x, lo_y, hi_y = x0 + g, x0 + CT - 1 - g, y0 + g, y0 + CT - 1 - g
  bx0, bx1 = max(bx0 - R, lo_x), min(bx1 + R, hi_x)
  by0, by1 = max(by0 - R, lo_y), min(by1 + R, hi_y)
  F_COUNT.name = nonland
  local land = land_in(surface, bx0, by0, bx1, by1)
  if land < CV.min_land_tiles then
    bx0, by0, bx1, by1 = lo_x, lo_y, hi_x, hi_y
    land = land_in(surface, bx0, by0, bx1, by1)
  end
  NE, ND = 0, 0
  if land == 0 then
    land, bx0, by0, bx1, by1 = neighbour_box(surface, x0, y0)
    if land == 0 then
      return false
    end
  end
  local ents = surface.find_entities_filtered(F_ENTS)
  NE = #ents
  for k = 1, NE do
    NAMES[k] = ents[k].name
  end
  RATE_E = (NE < CV.entity_limit and NE or surface.count_entities_filtered(F_ENTS_ALL)) / land
  read_decoratives(surface, bx0, by0, bx1, by1, land)
  return NE > 0 or ND > 0
end

local function draw_entity(ground)
  for _ = 1, CV.tries do
    local name = NAMES[RNG(1, NE)]
    local g = GROUNDS_E[name]
    if g == true or (g and g[ground]) then
      return name
    end
  end
  return nil
end

local function draw_decorative(ground)
  for _ = 1, CV.tries do
    local d = DECOS[RNG(1, ND)]
    local name = d.decorative.name
    local g = GROUNDS_D[name]
    if g == true or (g and g[ground]) then
      return name, d.amount
    end
  end
  return nil
end

local function place_entity(surface, name, x0, y0, tx, ty)
  local m = MARGIN[name]
  local lo, hi = CV.offset, 1 - CV.offset
  local x = min(max(tx + lo + (hi - lo) * RNG(), x0 + m), x0 + CT - m)
  local y = min(max(ty + lo + (hi - lo) * RNG(), y0 + m), y0 + CT - m)
  local pos = {x, y}
  if not surface.can_place_entity{name = name, position = pos} then
    -- A tile beside water takes its tree on the middle of the tile, or not at all.
    pos[1], pos[2] = min(max(tx + 1 / 2, x0 + m), x0 + CT - m), min(max(ty + 1 / 2, y0 + m), y0 + CT - m)
    if not surface.can_place_entity{name = name, position = pos} then
      return
    end
  end
  surface.create_entity{name = name, position = pos, create_build_effect_smoke = false}
end

-- After set_tiles: the cover read before it, on the written land of chunk (cx, cy).
function M.place(surface, cx, cy)
  SEED = SEED or surface.map_gen_settings.seed
  RNG = game.create_random_generator(chunk_seed(cx, cy))
  local x0, y0, m = cx * CT, cy * CT, 0
  for q = 1, NLAND do
    local r = LAND[q]
    local tx, ty, ground = r.position[1], r.position[2], r.name
    if NE > 0 and RNG() < RATE_E then
      local name = draw_entity(ground)
      if name then
        place_entity(surface, name, x0, y0, tx, ty)
      end
    end
    if ND > 0 then
      for _ = 1, floor(RATE_D + RNG()) do
        local name, amount = draw_decorative(ground)
        if name then
          m = m + 1
          local o = OUT[m]
          if o then
            o.name, o.amount = name, amount
            o.position[1], o.position[2] = tx, ty
          else
            OUT[m] = {name = name, amount = amount, position = {tx, ty}}
          end
        end
      end
    end
  end
  for k = #OUT, m + 1, -1 do
    OUT[k] = nil
  end
  if m > 0 then
    surface.create_decoratives{decoratives = OUT, check_collision = CV.check_collision}
  end
end

return M
