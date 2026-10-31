-- The start ore guarantee (config.lua start_ore; design notes 2026-10-30): once, from start.on_init on an
-- Earth or Map-type-only world, every starting ore gets a patch on the land the spawn reaches on foot
-- when that land holds too little of it. The starting area is generated before on_init
-- (worldgen-runtime rule 2) and bandfix.on_init has settled its coast, so the tiles and ore read here are
-- final. Beside RSO they are final too:
-- the `? rso-mod` dependency runs RSO's on_init, which places its starting ore, before this one, so a
-- start RSO served well gets nothing. RSO's own "Ore in starting area" off stands the pass down. Runs
-- once per world, so its cost (one tile query and one flood over the start square) never recurs.
local cfg = require("prototypes.config")

local M = {}
local C = cfg.start_ore
local MSG = cfg.messages
local floor, sqrt, sin, cos, pi, max = math.floor, math.sqrt, math.sin, math.cos, math.pi, math.max

local G = C.grid
local HALF = 1 / 2
local STEPS = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}
local W = 2 * G + 1

local function idx(x, y)
  if x < -G or x > G or y < -G or y > G then
    return nil
  end
  return (y + G) * W + (x + G) + 1
end

-- The tiles reached on foot from the spawn: a set of grid indices.
local function reached_land(surface)
  local water = {}
  for _, t in pairs(surface.find_tiles_filtered{area = {{-G, -G}, {G + 1, G + 1}}, collision_mask = C.water_layer}) do
    local p = t.position
    local i = idx(p.x, p.y)
    if i then
      water[i] = true
    end
  end
  local reach = {}
  local i0 = idx(0, 0)
  if water[i0] then
    return reach
  end
  reach[i0] = true
  local qx, qy, head, tail = {0}, {0}, 1, 1
  while head <= tail do
    local x, y = qx[head], qy[head]
    head = head + 1
    for _, st in ipairs(STEPS) do
      local nx, ny = x + st[1], y + st[2]
      local j = idx(nx, ny)
      if j and not reach[j] and not water[j] then
        reach[j] = true
        tail = tail + 1
        qx[tail], qy[tail] = nx, ny
      end
    end
  end
  return reach
end

local function reached_amount(surface, reach, name)
  local sum = 0
  for _, e in pairs(surface.find_entities_filtered{position = {0, 0}, radius = C.radius, name = name}) do
    local p = e.position
    local i = idx(floor(p.x), floor(p.y))
    if i and reach[i] then
      sum = sum + e.amount
    end
  end
  return sum
end

-- Whether every tile within `rr` of (cx, cy) is reached land.
local function disc_on_land(reach, cx, cy, rr)
  local r2 = rr * rr
  for dy = -rr, rr do
    for dx = -rr, rr do
      if dx * dx + dy * dy <= r2 then
        local i = idx(cx + dx, cy + dy)
        if not (i and reach[i]) then
          return false
        end
      end
    end
  end
  return true
end

-- The nearest centre for a disc of radius r, searched ring by ring from `turn` (a fraction of a turn).
local function find_spot(surface, reach, r, turn)
  local d = C.min_distance
  local d_max = C.radius - r - 1
  while d <= d_max do
    local n = max(C.min_ring_points, floor(2 * pi * d / C.arc_step))
    for k = 0, n - 1 do
      local a = 2 * pi * (turn + k / n)
      local cx, cy = floor(d * cos(a) + HALF), floor(d * sin(a) + HALF)
      local i = idx(cx, cy)
      if i and reach[i] and disc_on_land(reach, cx, cy, r + C.land_margin)
        and surface.count_entities_filtered{position = {cx + HALF, cy + HALF}, radius = r + C.ore_margin,
                                            type = C.resource_type, limit = 1} == 0 then
        return cx, cy
      end
    end
    d = d + C.ring_step
  end
  return nil
end

-- The patch: the disc find_spot proved, eaten back by the hotspot blob so its outline is as uneven as a
-- hotspot's bodies (config.lua start_ore.outline), with the amount spread over the tiles it keeps. The blob
-- counts from its own mean over the disc, so a patch keeps its size wherever it lands; a world that cannot
-- read the blob keeps the plain disc.
local function place(surface, name, cx, cy, r, amount)
  local O = C.outline
  local cells, n = {}, 0
  local r2 = r * r
  for dy = -r, r do
    for dx = -r, r do
      if dx * dx + dy * dy <= r2 then
        n = n + 1
        cells[n] = {x = cx + dx + HALF, y = cy + dy + HALF, q = (dx * dx + dy * dy) / r2}
      end
    end
  end
  local blob = surface.calculate_tile_properties({O.blob}, cells)[O.blob]
  local mean = 0
  for i = 1, blob and n or 0 do
    mean = mean + blob[i] / n
  end
  local kept, wsum = {}, 0
  for i, t in ipairs(cells) do
    if not blob or sqrt(t.q) < O.inner + O.gain * (blob[i] - mean) then
      t.w = 1 - t.q / 2
      wsum = wsum + t.w
      kept[#kept + 1] = t
    end
  end
  for _, t in ipairs(kept) do
    surface.create_entity{name = name, position = {t.x, t.y}, amount = max(1, floor(amount * t.w / wsum + HALF))}
  end
end

function M.ensure(surface)
  local rso_start = settings.global[C.rso_start]
  if rso_start and not rso_start.value then
    return
  end
  local controls = surface.map_gen_settings.autoplace_controls or {}
  local reach = reached_land(surface)
  for n, ore in ipairs(C.ores) do
    local c = controls[ore.resource] or {}
    if prototypes.entity[ore.resource] and (c.size or 1) > 0 then
      local target = ore.reference * (c.richness or 1)
      local have = reached_amount(surface, reach, ore.resource)
      if have < C.trigger * target then
        local amount = floor(C.fill * target)
        local r = max(C.min_radius, floor(C.outline.grow * sqrt(amount / ore.density / pi) + HALF))
        local cx, cy
        while true do
          cx, cy = find_spot(surface, reach, r, (n - 1) / #C.ores)
          if cx or r <= C.min_radius then
            break
          end
          r = max(C.min_radius, floor(r * C.shrink))
        end
        if cx then
          place(surface, ore.resource, cx, cy, r, amount)
          log({MSG.section .. "." .. MSG.keys.start_ore, ore.resource, have, amount, cx, cy})
        else
          log({MSG.section .. "." .. MSG.keys.start_ore_none, ore.resource, have})
        end
      end
    end
  end
end

return M
