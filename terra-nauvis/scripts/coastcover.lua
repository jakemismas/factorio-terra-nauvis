-- Cover for the land Exact coastlines writes (scripts/bandfix.lua step 7; config.lua coastcover; the maintainer,
-- 2026-10-30 16:20). The game generates trees, rocks and decoratives before the handler runs, so land the
-- handler writes over generated water stays bare. This module gives it the cover of the land beside it:
--   read, before the tiles are written: inside the chunk, the box around the written land holds the generated
--     land the cover is copied from. Its land tiles, its trees and rocks and its decoratives give a rate per
--     tile and a sample to draw from. A read stops at a limit, so a dense forest costs what a sparse one does;
--     a chunk with no land of its own has nothing to copy and keeps its bare ground.
--   place, after they are written: a generator seeded from the map seed and the chunk draws per written land
--     tile whether it takes an entity and how many decoratives, each from the sample, kept only when the
--     prototype's tile_restriction allows the ground the tile took.
-- Everything read lies in the chunk, and an entity keeps coastcover.edge_gap clear of the chunk's edge, so
-- the cover is a pure function of the chunk's own generated state: neighbours and their generation state are
-- never read. No storage write: the generator is re-seeded per chunk and the prototype facts are a cache.
-- regenerate_entity and regenerate_decorative are not an option: on Old World they cost 7 to 90 ms a chunk and
-- place over the whole chunk.
local cfg = require("prototypes.config")

local M = {}
local CV = cfg.coastcover
local CT = cfg.bandfix.chunk_tiles
local H = CV.hash
local floor, max, min = math.floor, math.max, math.min

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
local INSET = {{0, 0}, {0, 0}}
local F_ENTS = {area = INSET, type = CV.types, limit = CV.entity_limit}
local F_ENT_COUNT = {area = INSET, type = CV.types}
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
  local R = CV.reach_tiles
  bx0, bx1 = max(bx0 - R, x0), min(bx1 + R, x0 + CT - 1)
  by0, by1 = max(by0 - R, y0), min(by1 + R, y0 + CT - 1)
  F_COUNT.name = nonland
  set_box(BOX, bx0, by0, bx1 + 1, by1 + 1)
  local land = surface.count_tiles_filtered(F_COUNT)
  if land < CV.min_land_tiles then
    bx0, by0, bx1, by1 = x0, y0, x0 + CT - 1, y0 + CT - 1
    set_box(BOX, x0, y0, x0 + CT, y0 + CT)
    land = surface.count_tiles_filtered(F_COUNT)
  end
  NE, ND = 0, 0
  if land == 0 then
    return false
  end
  set_box(INSET, max(bx0, x0 + CV.inset), max(by0, y0 + CV.inset), min(bx1 + 1, x0 + CT - CV.inset),
          min(by1 + 1, y0 + CT - CV.inset))
  local ents = surface.find_entities_filtered(F_ENTS)
  NE = #ents
  for k = 1, NE do
    NAMES[k] = ents[k].name
  end
  RATE_E = (NE < CV.entity_limit and NE or surface.count_entities_filtered(F_ENT_COUNT)) / land
  DECOS = surface.find_decoratives_filtered(F_DECOS)
  ND = #DECOS
  if ND == CV.decorative_limit then
    -- Cut off by the limit: results come row by row, so the rate is the sample's over the rows it covers.
    BOX[2][2] = DECOS[ND].position.y + 1
    land = max(surface.count_tiles_filtered(F_COUNT), 1)
  end
  RATE_D = ND / land
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
  RNG = RNG or game.create_random_generator()
  RNG.re_seed(chunk_seed(cx, cy))
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
