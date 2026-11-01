-- A zone's exclusion (config.lua destroyed.exclusion): the trees and plants a zone keeps out, beside Alien Biomes.
--
-- Alien Biomes picks its plants by climate, not by tile, so a blue flower or a palm stands on any tile its list holds,
-- and the zone's tiles are on those lists. Taking a tile off a list would change saves that hold the tile already, so
-- the hook works on probability instead: if(key > threshold, own * open, own). The key's prototype holds 0, so every
-- world without the key, a save made before included, folds to its own text and its own program. A spec is data, so a
-- second zone states its own tiles, key and mask and calls apply again; hooks nest.
--
-- Only what can stand on a zone tile takes a hook: most of Alien Biomes' plants never can, and each hook costs load
-- time and a term in the Entity program.
local cfg = require("prototypes.config")

local M = {}

local function num(v)
  return string.format(cfg.number_format, v)
end

local function can_stand_on(autoplace, tiles)
  local list = autoplace.tile_restriction
  if not list then
    return true
  end
  for _, t in ipairs(list) do
    if tiles[t] then
      return true
    end
  end
  return false
end

local function has_word(name, words)
  for _, w in ipairs(words) do
    if string.find(name, w, 1, true) then
      return true
    end
  end
  return false
end

local function plant_stays(name, plants)
  return has_word(name, plants.keep) and not has_word(name, plants.drop)
end

local function sorted_names(group)
  local names = {}
  for name in pairs(group or {}) do
    names[#names + 1] = name
  end
  table.sort(names)
  return names
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

-- Every copy reads the zone's one density. It has no tile list: the body says where, and collision keeps it off water.
-- On any world but a zone's the probability folds to 0. The game places the likeliest entity on a tile, so an equal
-- share gives one kind only: a random penalty of its own per copy lets each kind win its share of the tiles. Copies
-- sort after every other tree: among them, a copy moves its neighbours' placements on worlds with the zone off.
local function dead_copies(Z, gate)
  for i, row in ipairs(Z.dead_trees or {}) do
    local copy = deep(data.raw.tree[row.tree])
    copy.name = row.copy
    copy.localised_name = {"entity-name." .. row.tree}
    copy.factoriopedia_alternative = row.tree
    copy.order = Z.dead_order .. row.tree
    copy.autoplace = {control = copy.autoplace.control, order = Z.dead_order .. row.tree,
                      probability_expression = "if(" .. gate .. ", random_penalty{x = x, y = y, seed = " .. num(i) ..
                        ", source = " .. num(row.share) .. " * " .. Z.dead .. ", amplitude = " ..
                        num(row.share * Z.dead_peak) .. "}, 0)"}
    data:extend({copy})
  end
end

-- Every prototype of a group Nauvis places, with a probability, that can stand on a zone tile.
local function each_standing(group, kind, tiles, on_nauvis, fn)
  local n = 0
  for _, name in ipairs(sorted_names(group)) do
    local autoplace = group[name].autoplace
    if autoplace and autoplace.probability_expression ~= nil and on_nauvis(kind, name, autoplace) and
        can_stand_on(autoplace, tiles) and fn(name, autoplace) then
      n = n + 1
    end
  end
  return n
end

local function times(autoplace, gate, term)
  local own = "(" .. tostring(autoplace.probability_expression) .. ")"
  autoplace.probability_expression = "if(" .. gate .. ", " .. own .. " * " .. term .. ", " .. own .. ")"
end

local function boost(Z, gate)
  for _, row in ipairs(Z.boost or {}) do
    local proto = data.raw[row.type] and data.raw[row.type][row.name]
    local autoplace = proto and proto.autoplace
    if autoplace and autoplace.probability_expression ~= nil then
      local own = "(" .. tostring(autoplace.probability_expression) .. ")"
      autoplace.probability_expression = "if(" .. gate .. ", min(1, " .. own .. " * (" .. num(row.gain) .. " - " ..
        num(row.gain - 1) .. " * " .. Z.open .. ")), " .. own .. ")"
    end
  end
end

function M.apply(Z, on_nauvis)
  local tiles = {}
  for _, t in ipairs(Z.tiles) do
    tiles[t] = true
  end
  local palm = {}
  for _, c in ipairs(cfg.tiles.palm.copies) do
    palm[c.tree] = true
  end
  local gate = Z.key .. " > " .. num(cfg.hooks.threshold)
  local trees = each_standing(data.raw.tree, "entity", tiles, on_nauvis, function(name, autoplace)
    if not palm[name] and not (Z.keep_trees and Z.keep_trees[name]) then
      times(autoplace, gate, Z.open)
      return true
    end
  end)
  local plants = each_standing(data.raw["optimized-decorative"], "decorative", tiles, on_nauvis,
    function(name, autoplace)
      if not plant_stays(name, Z.plants) then
        times(autoplace, gate, Z.open)
        return true
      end
    end)
  -- Rocks stay, thinned round the spawn.
  if Z.thin then
    each_standing(data.raw["simple-entity"], "entity", tiles, on_nauvis, function(_, autoplace)
      times(autoplace, gate, Z.thin)
      return true
    end)
  end
  boost(Z, gate)
  dead_copies(Z, gate)
  log(cfg.identity.title .. ": zone exclusion on " .. trees .. " trees and " .. plants .. " plants")
end

return M
