-- The zones' ground and look beside Alien Biomes, each with its zone's startup setting on (config.lua zone_look; Jake
-- 2026-11-01: the 10-hour list's item 5, and the recolour of every light brown or dirt-coloured decal and plant in the
-- zones, nest and worm creep included). Prototype edits only. A tile the zone shares with the rest of the map
-- (zone_look.shared) keeps its own values and takes no zone creep.
--   ground    zone ground absorbs pollution like grass, walks at full speed and caps vehicle friction; the zone's
--             dead tree copies absorb like a living tree. A save made before takes it too.
--   plant     with Space Age, the tree farm plant's plot list gains the zones' ground (Alien Biomes' list holds none),
--             and beside Alien Biomes with or without a zone the vanilla land tiles Earth presets restore.
--   recolour  each decorative of a zone's list gets a copy in the zone's tint. The copy takes the original's
--             probability inside the zone (1 - open) and the original keeps it outside (open), behind the zone's key,
--             so a world without the key, a save made before included, compiles the original alone.
--   creep     the spawners' and worms' decals: a copy per zone joins each spawn list beside its original. A spawn list
--             has no noise and no tile condition, so collision layers keep each on its own ground: the original
--             collides with every zone's ground, each copy with every tile but its zone's (the engine checks tile
--             collision when it spawns them, measured with create_entity and the map generator). This follows the
--             tiles, so new nests on a save made before take it too. Where the original is autoplaced too, its copy
--             also takes the recolour's autoplace. Mods that clear creep by name (Biter Cleanup) do not know the
--             copies.
local cfg = require("prototypes.config")

local M = {}
local ZL = cfg.zone_look

local function num(v)
  return string.format(cfg.number_format, v)
end

local function deep(t)
  if type(t) ~= "table" then
    return t
  end
  local out = {}
  for k, v in pairs(t) do
    out[k] = deep(v)
  end
  return out
end

local function set_of(list)
  local s = {}
  for _, v in ipairs(list or {}) do
    s[v] = true
  end
  return s
end

-- The tiles a zone owns: its exclusion tiles less the shared ones, present in this game.
local function owned_tiles(Z)
  local shared, out = set_of(ZL.shared), {}
  for _, t in ipairs(Z.tiles) do
    if not shared[t] and data.raw.tile[t] then
      out[#out + 1] = t
    end
  end
  return out
end

-- Pollution, walking speed and vehicle friction on the zone's own ground, and the dead tree copies' absorption.
local function ground(Z)
  local G = ZL.ground
  for _, name in ipairs(Z.ground_tiles) do
    local t = data.raw.tile[name]
    local a = t.absorptions_per_second or {}
    a.pollution = math.max(a.pollution or 0, G.absorption)
    t.absorptions_per_second = a
    t.walking_speed_modifier = math.max(t.walking_speed_modifier or 1, G.walking_speed)
    if (t.vehicle_friction_modifier or 1) > G.friction_cap then
      t.vehicle_friction_modifier = G.friction_cap
    end
  end
  for _, row in ipairs(Z.dead_trees or {}) do
    local tree = data.raw.tree[row.copy]
    if tree then
      local e = tree.emissions_per_second or {}
      e.pollution = math.min(e.pollution or 0, -G.tree_absorption)
      tree.emissions_per_second = e
    end
  end
end

-- Space Age's tree farm plots: the plant's tile list gains these tiles.
local function plant_tiles(tiles)
  local plant = data.raw.plant and data.raw.plant[ZL.plant.name]
  local autoplace = plant and plant.autoplace
  if not (mods["space-age"] and autoplace and autoplace.tile_restriction) then
    return 0
  end
  local have, n = set_of(autoplace.tile_restriction), 0
  for _, t in ipairs(tiles) do
    if not have[t] and data.raw.tile[t] then
      autoplace.tile_restriction[#autoplace.tile_restriction + 1] = t
      have[t] = true
      n = n + 1
    end
  end
  return n
end

-- A tint on every sprite of a picture tree, times any tint it had.
local function tint(p, c)
  if type(p) ~= "table" then
    return
  end
  if p.layers then
    for _, l in ipairs(p.layers) do
      tint(l, c)
    end
  elseif p.sheet then
    tint(p.sheet, c)
  elseif p.filename or p.filenames then
    -- a Color may be named or positional, and in 0 to 255 when any channel is over 1
    local o, old, big = p.tint or {}, {}, false
    for i, k in ipairs(ZL.color.channels) do
      old[k] = o[k] or o[i] or 1
      big = big or old[k] > 1
    end
    local scale = big and ZL.color.max or 1
    p.tint = {}
    for _, k in ipairs(ZL.color.channels) do
      p.tint[k] = old[k] / scale * (c[k] or 1)
    end
  else
    for _, v in ipairs(p) do
      tint(v, c)
    end
  end
end

local function nauvis_decoratives()
  local n = data.raw.planet and data.raw.planet.nauvis
  local s = n and n.map_gen_settings and n.map_gen_settings.autoplace_settings
  return s and s.decorative and s.decorative.settings
end

-- Whether Nauvis places this decorative through its autoplace.
local function placed(src)
  local listed = nauvis_decoratives()
  return src.autoplace ~= nil and src.autoplace.probability_expression ~= nil and listed ~= nil and
    listed[src.name] ~= nil
end

-- The zone's copy of one decorative: tinted, and, where Nauvis places the original, an autoplace with the original's
-- probability inside the zone only. Called before the original's own autoplace takes the zone's hook. The copy keeps
-- the original's order: among decoratives of one order the engine places only the likeliest, and the two never both
-- score, so the copy takes the original's turn and its neighbours place as before (sorted last, it let lava decals
-- and sand decals into tiles the mud decals had held).
local function copy_of(Z, src, mask)
  local copy = deep(src)
  copy.name = cfg.identity.id .. "-" .. Z.id .. "-" .. src.name
  copy.localised_name = src.localised_name or {"decorative-name." .. src.name}
  copy.factoriopedia_alternative = src.name
  tint(copy.pictures, Z.tint)
  if mask then
    copy.collision_mask = mask
  end
  copy.autoplace = nil
  if placed(src) then
    local own = "(" .. tostring(src.autoplace.probability_expression) .. ")"
    copy.autoplace = deep(src.autoplace)
    copy.autoplace.probability_expression = "if(" .. Z.gate .. ", " .. own .. " * (1 - " .. Z.open .. "), 0)"
    local listed = nauvis_decoratives()
    listed[copy.name] = deep(listed[src.name])
  end
  data:extend({copy})
  return copy.name
end

-- The original's side of the recolour: its probability outside the zone only.
local function outside(Z, src)
  if placed(src) then
    local own = "(" .. tostring(src.autoplace.probability_expression) .. ")"
    src.autoplace.probability_expression = "if(" .. Z.gate .. ", " .. own .. " * " .. Z.open .. ", " .. own .. ")"
  end
end

-- An autoplaced decorative of the zone's list: the copy inside, the original outside.
local function recolour(Z, name)
  local src = data.raw["optimized-decorative"][name]
  if not (src and placed(src)) then
    return false
  end
  copy_of(Z, src, nil)
  outside(Z, src)
  return true
end

-- The collision layers: zone on every zone's own ground, off .. id on every tile but that zone's.
local function mark_tiles(zones)
  local L = ZL.layers
  local defs = {{type = "collision-layer", name = L.zone}}
  local any = {}
  for _, Z in ipairs(zones) do
    defs[#defs + 1] = {type = "collision-layer", name = L.off .. Z.id}
    Z.owned = set_of(Z.ground_tiles)
    for t in pairs(Z.owned) do
      any[t] = true
    end
  end
  data:extend(defs)
  for name, t in pairs(data.raw.tile) do
    t.collision_mask = t.collision_mask or {layers = {ground_tile = true}}
    t.collision_mask.layers = t.collision_mask.layers or {}
    if any[name] then
      t.collision_mask.layers[L.zone] = true
    end
    for _, Z in ipairs(zones) do
      if not Z.owned[name] then
        t.collision_mask.layers[L.off .. Z.id] = true
      end
    end
  end
end

-- Each creep decal's copies, one per zone, and the original kept off every zone's ground. A decal collides with
-- tiles only, and water stays off, as the base game's creep decals do.
local function creep_copies(zones)
  local L, copies = ZL.layers, {}
  for _, name in ipairs(ZL.creep) do
    local src = data.raw["optimized-decorative"][name]
    if src then
      local base = deep(src.collision_mask or {layers = {doodad = true}})
      base.layers = base.layers or {}
      base.layers.water_tile = true
      base.colliding_with_tiles_only = true
      base.not_colliding_with_itself = nil
      copies[name] = {}
      for _, Z in ipairs(zones) do
        local mask = deep(base)
        mask.layers[L.off .. Z.id] = true
        copies[name][#copies[name] + 1] = copy_of(Z, src, mask)
      end
      for _, Z in ipairs(zones) do
        outside(Z, src)
      end
      local own = deep(base)
      own.layers[L.zone] = true
      src.collision_mask = own
    end
  end
  return copies
end

-- One spawn list with every copy beside its original, and how many entries it gained.
local function with_copies(list, copies)
  local out, n = {}, 0
  for _, item in ipairs(list) do
    out[#out + 1] = item
    for _, c in ipairs(copies[item.decorative] or {}) do
      local z = deep(item)
      z.decorative = c
      out[#out + 1] = z
      n = n + 1
    end
  end
  return out, n
end

-- The creep: tile layers, the copies, and each spawn list gains every zone's copy beside the original.
local function creep(zones)
  mark_tiles(zones)
  local copies, n = creep_copies(zones), 0
  for _, kind in ipairs(ZL.spawn_types) do
    for _, e in pairs(data.raw[kind] or {}) do
      if e.spawn_decoration then
        local added
        e.spawn_decoration, added = with_copies(e.spawn_decoration, copies)
        n = n + added
      end
    end
  end
  return n
end

function M.apply()
  if not mods["alien-biomes"] then
    return
  end
  -- Alien Biomes rewrites the tree farm plant's list to its own tiles, and Earth presets put the vanilla land back.
  local vanilla = plant_tiles(cfg.tiles.vanilla.tiles)
  if vanilla > 0 then
    log(cfg.identity.title .. ": tree farm plots on " .. vanilla .. " vanilla land tiles")
  end
  local zones = {}
  for _, Z in ipairs(ZL.zones) do
    if settings.startup[cfg.settings[Z.setting].name].value then
      local X = cfg[Z.section].exclusion
      local z = {id = Z.id, tint = Z.tint, decoratives = Z.decoratives, tiles = X.tiles, dead_trees = X.dead_trees,
                 gate = X.key .. " > " .. num(cfg.hooks.threshold), open = X.open}
      z.ground_tiles = owned_tiles(z)
      zones[#zones + 1] = z
    end
  end
  if #zones == 0 then
    return
  end
  local tinted, creep_set, planted = 0, set_of(ZL.creep), 0
  for _, Z in ipairs(zones) do
    ground(Z)
    planted = planted + plant_tiles(Z.ground_tiles)
    for _, name in ipairs(Z.decoratives) do
      if not creep_set[name] and recolour(Z, name) then
        tinted = tinted + 1
      end
    end
  end
  local spawned = creep(zones)
  log(cfg.identity.title .. ": zone look on " .. #zones .. " zones: " .. tinted .. " decoratives recoloured, " ..
    spawned .. " creep entries, " .. planted .. " tree farm tiles")
end

return M
