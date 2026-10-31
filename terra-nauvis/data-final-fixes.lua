-- Everything that reads other mods' final state: entity wrappers and gated hooks on shared
-- prototypes (ARCHITECTURE.md, "Module map" and "Stable hooks"). Milestone waterways: the ford hook.
-- Milestone climate-tiles: the marsh keys, and beside Alien Biomes the vanilla land tiles, the exclusion
-- of non-adopted AB tiles from temperate bands and the palm check against the frozen palm table. Milestone
-- trees-forests: beside Alien Biomes the base game's trees, rocks, decals and plants, and on every world
-- the great-forests hook. Milestone ridges: the Earth-gated ridge exclusion on ore probability. Milestone
-- resources-enemies: the ore, richness, enemy and offshore-oil wrappers around the pack's live autoplace.
--
-- Every gated hook is
--   if(tn_on > threshold, <on branch>, <off value>)
-- with the gate tn_on (prototype off, Earth presets on) outermost, so on every other world the hook
-- folds to the off value and the world stays hash- and complexity-identical (T13; S3: a gate inside the
-- score cost default worlds Tile +7,489). Hooks run here, after every mod's data stage, so each wraps a
-- tile's final autoplace; a tile placed nowhere before is registered on Nauvis (noise rule 2).
--
-- water-shallow: the on branch is max() of the ford key tn_fords, which an Earth
-- preset points at its map's ford set for the save's scale, and the marsh key (climate-tiles). Where
-- another mod gives the tile an autoplace (Alien Biomes' coastal shallows), that expression is the off
-- value and joins the max(), so its shallows are unchanged on every world; without one the off value is
-- -inf. water-mud (climate-tiles): the same shape around the marsh key; Alien Biomes' inland shallows
-- are its off value with AB, and without AB the tile is registered on Nauvis for Earth presets only.
local cfg = require("prototypes.config")

local H = cfg.hooks
local TL = cfg.tiles
local AB = mods["alien-biomes"] ~= nil

local function num(v)
  return string.format(cfg.number_format, v)
end

local GATE = cfg.keys.on .. " > " .. num(H.threshold)

local function hook(on_branch, off_value)
  return "if(" .. GATE .. ", " .. on_branch .. ", " .. off_value .. ")"
end

local nauvis = data.raw.planet and data.raw.planet.nauvis
local tile_settings = nauvis and nauvis.map_gen_settings and nauvis.map_gen_settings.autoplace_settings and
  nauvis.map_gen_settings.autoplace_settings.tile and nauvis.map_gen_settings.autoplace_settings.tile.settings

local function register(name)
  if tile_settings and tile_settings[name] == nil then
    tile_settings[name] = {}
  end
end

-- A max() hook on a water tile: the keys joined with the tile's own autoplace where it has one.
local function water_hook(name, keys, off, why)
  local tile = data.raw.tile[name]
  if not tile then
    log(cfg.identity.title .. ": no tile " .. name .. " for the " .. why)
    return
  end
  local autoplace = tile.autoplace or {}
  local original = autoplace.probability_expression
  local parts, off_value = {}, nil
  for _, k in ipairs(keys) do
    parts[#parts + 1] = k
  end
  if original ~= nil and original ~= "" then
    off_value = "(" .. tostring(original) .. ")"
    parts[#parts + 1] = off_value
  end
  local on_branch = #parts == 1 and parts[1] or ("max(" .. table.concat(parts, ", ") .. ")")
  autoplace.probability_expression = hook(on_branch, off_value or off)
  tile.autoplace = autoplace
  register(name)
  log(cfg.identity.title .. ": " .. why .. " on " .. name .. (original and " around its own autoplace" or "") ..
    (tile_settings and ", registered on Nauvis" or ", Nauvis has no tile settings"))
end

water_hook(H.fords.tile, {H.fords.key, TL.marsh.water_shallow.key}, H.fords.off, "ford and marsh hook")
water_hook(TL.marsh.water_mud.tile, {TL.marsh.water_mud.key}, TL.marsh.water_mud.off, "marsh hook")

-- The vanilla land tiles beside Alien Biomes (S3 section 2): AB keeps their autoplace on the
-- prototypes and takes them off Nauvis (R3 3.2); re-listed here behind the gate, each adds its key.
local function vanilla_hooks()
  local V = TL.vanilla
  for i, name in ipairs(V.tiles) do
    local tile = data.raw.tile[name]
    if tile and tile.autoplace and tile.autoplace.probability_expression then
      tile.autoplace.probability_expression = hook("(" .. tostring(tile.autoplace.probability_expression) .. ") + " ..
        V.keys[name] .. " + " .. V.mix.key .. " * " .. string.format(V.mix.noise, V.mix.first_seed1 + i - 1) ..
        " * (" .. V.keys[name] .. " > " .. num(V.bonus / 2) .. ")", V.off)
      register(name)
    else
      log(cfg.identity.title .. ": vanilla tile " .. name .. " is missing or has no autoplace")
    end
  end
end

-- A tile's own six-octave noise as two of the shared fields (config.lua tiles.noise_share).
local function mixed_noise(seed1)
  local NS = TL.noise_share
  local n, steps = #NS.fields, #NS.steps
  local seed = tonumber(seed1)
  local j = math.floor(seed / n)
  local a = seed % n
  local b = (a + NS.steps[j % steps + 1]) % n
  local signs = math.floor(j / steps) % 4
  local w = num(NS.weight)
  return "(" .. (signs >= 2 and "-" or "") .. w .. " * " .. NS.fields[a + 1] .. (signs % 2 == 1 and " - " or " + ") ..
    w .. " * " .. NS.fields[b + 1] .. ")"
end

-- A tile score with the three climate fields read through the grain's copies (config.lua climate.grain)
-- and its own noise through the shared fields.
local function grain_scores(text)
  for field, key in pairs(cfg.climate.grain.keys) do
    text = string.gsub(text, "%f[%w_:]" .. field .. "%f[^%w_:]", key)
  end
  return (string.gsub(text, TL.noise_share.pattern, mixed_noise))
end

-- The grain's copies reach every Alien Biomes land tile: snow, volcanic and the adopted tiles too, and ice
-- gives up score on its on branch (config.lua climate.grain.ice).
local function grain_hooks(excluded, n)
  local G = cfg.climate.grain
  local others = {}
  for name in pairs(tile_settings or {}) do
    local t = data.raw.tile[name]
    if not excluded[name] and t and t.autoplace and t.autoplace.probability_expression then
      for _, p in ipairs(G.prefixes) do
        if string.sub(name, 1, #p) == p then
          others[#others + 1] = name
          break
        end
      end
    end
  end
  table.sort(others)
  for _, name in ipairs(others) do
    local autoplace = data.raw.tile[name].autoplace
    local original = "(" .. tostring(autoplace.probability_expression) .. ")"
    local on = grain_scores(original)
    if G.ice[name] then
      on = on .. " - " .. num(G.ice[name])
    end
    autoplace.probability_expression = hook(on, original)
  end
  log(cfg.identity.title .. ": climate grain copies on " .. (n + #others) .. " Alien Biomes tiles")
end

-- Vegetation tiles read a temperature of their own, excluded or adopted alike (config.lua climate.grain),
-- and the brown green grasses give up score on their on branch, which alone holds the exclusion key.
local function vegetation_hooks()
  local G, key = cfg.climate.grain, TL.exclude.key
  for name in pairs(tile_settings or {}) do
    local autoplace = data.raw.tile[name] and data.raw.tile[name].autoplace
    local text = autoplace and autoplace.probability_expression
    if text and string.sub(name, 1, #G.veg_prefix) == G.veg_prefix then
      text = string.gsub(text, "%f[%w_:]" .. G.keys.temperature .. "%f[^%w_:]", G.veg_key)
      if G.brown[name] then
        text = string.gsub(text, "%f[%w_]" .. key .. "%f[^%w_]", key .. " - " .. num(G.brown[name]))
      end
      autoplace.probability_expression = text
    end
  end
end

-- Only the adopted Alien Biomes tiles mix into temperate bands (D11; APPROVALS 9): every other AB land
-- tile on Nauvis adds the exclusion key, and its own score stays the off value.
-- The red palette's tiles take the max with their score (config.lua destroyed.chaos): the exclusion is
-- -inf in the temperate band, and these tiles must win there inside the zone.
local function with_chaos(name, text)
  for _, t in ipairs(cfg.destroyed.chaos.tiles) do
    if t.tile == name then
      return "max(" .. text .. ", " .. t.body .. ")"
    end
  end
  return text
end

local function exclusion_hooks()
  local X = TL.exclude
  local adopted = {}
  for _, name in ipairs(TL.ab_adopted) do
    adopted[name] = true
  end
  local names = {}
  for name in pairs(tile_settings or {}) do
    local t = data.raw.tile[name]
    if not adopted[name] and t and t.autoplace and t.autoplace.probability_expression then
      for _, p in ipairs(X.prefixes) do
        if string.sub(name, 1, #p) == p then
          names[#names + 1] = name
          break
        end
      end
    end
  end
  table.sort(names)
  local excluded = {}
  for _, name in ipairs(names) do
    excluded[name] = true
    local autoplace = data.raw.tile[name].autoplace
    local original = "(" .. tostring(autoplace.probability_expression) .. ")"
    autoplace.probability_expression = hook(with_chaos(name, grain_scores(original) .. " + " .. X.key), original)
  end
  log(cfg.identity.title .. ": temperate exclusion on " .. #names .. " Alien Biomes tiles")
  grain_hooks(excluded, #names)
  vegetation_hooks()
end

-- The palm switch: Earth presets name the Earth copies of the palms,
-- which trees.lua builds from the frozen Alien Biomes 0.8.0 table. Here the installed palms are
-- compared with that table, every text, local and called function (numbers within tolerance): a palm
-- that differs or lost its autoplace (Alien Biomes' disable-vegetation setting, a newer release) gets
-- both keys pointed at the neutral body on every Earth preset, so it grows nowhere on new Earth worlds
-- instead of reading a dangling name, and the log says why; the gate's dump facts fail on it too.
-- AB's prototypes stay untouched, so every other world compiles exactly AB's program. Any other tree
-- that reads elevation is logged loudly: the M2 isolation walk (T15 (b)) then fails on it.
local PALM = TL.palm

-- Equal, numbers within the palm tolerance (a dump's numbers round-trip through text).
local function same(a, b)
  if type(a) == "number" and type(b) == "number" then
    return math.abs(a - b) <= PALM.tolerance * math.max(1, math.abs(a))
  end
  if type(a) ~= type(b) then
    return false
  end
  if type(a) ~= "table" then
    return a == b
  end
  for k, v in pairs(a) do
    if not same(v, b[k]) then
      return false
    end
  end
  for k in pairs(b) do
    if a[k] == nil then
      return false
    end
  end
  return true
end

-- Why the installed palm differs from the frozen table, or nil.
local function palm_differs(T, tree)
  local ap = data.raw.tree[tree] and data.raw.tree[tree].autoplace
  local rec = T.trees[tree]
  if not ap then
    return "it has no autoplace"
  end
  for _, field in ipairs({"probability_expression", "richness_expression"}) do
    if not same(rec[field], ap[field]) then
      return "its " .. field .. " differs"
    end
  end
  if not same(rec.local_expressions or {}, ap.local_expressions or {}) then
    return "its local expressions differ"
  end
  for name, f in pairs(T.functions) do
    local live = data.raw["noise-function"] and data.raw["noise-function"][name]
    if not live or not same({f.parameters, f.expression, f.local_expressions or {}},
        {live.parameters, live.expression, live.local_expressions or {}}) then
      return "the noise function " .. name .. " it calls differs"
    end
  end
  return nil
end

local function reads_elevation(autoplace)
  local pattern = "%f[%w_]" .. PALM.reads .. "%f[^%w_]"
  local texts = {}
  for _, field in ipairs({"probability_expression", "richness_expression"}) do
    texts[#texts + 1] = autoplace[field]
  end
  for _, lv in pairs(autoplace.local_expressions or {}) do
    texts[#texts + 1] = lv
  end
  for _, text in pairs(texts) do
    if type(text) == "string" and string.find(text, pattern) then
      return true
    end
  end
  return false
end

local function palm_check()
  local T = require("prototypes.generated.palms_ab_v1")
  local presets = data.raw["map-gen-presets"] and data.raw["map-gen-presets"]["default"] or {}
  local copied = {}
  for _, c in ipairs(PALM.copies) do
    copied[c.tree] = true
    local why = palm_differs(T, c.tree)
    if why then
      for _, key in ipairs(cfg.preset_order) do
        local p = presets[cfg.presets[key].name]
        local names = p and p.basic_settings and p.basic_settings.property_expression_names
        if names then
          names[c.key] = PALM.neutral
        end
      end
      log(cfg.identity.title .. ": ERROR palm " .. c.tree .. " differs from the frozen " .. T.source.mod .. " " ..
        T.source.version .. " table (" .. why .. "); Earth presets point " .. c.key .. " at the neutral body")
    end
  end
  local trees = {}
  for name in pairs(data.raw.tree or {}) do
    trees[#trees + 1] = name
  end
  table.sort(trees)
  for _, name in ipairs(trees) do
    local autoplace = data.raw.tree[name].autoplace
    if autoplace and not copied[name] and reads_elevation(autoplace) then
      log(cfg.identity.title .. ": ERROR tree " .. name .. " reads " .. PALM.reads .. " and has no Earth copy")
    end
  end
end

-- Without Alien Biomes: grass-1 between the marsh pools (APPROVALS 8's without-AB column), (score) +
-- the grass key behind the gate, its own score off, so every other world keeps vanilla's grass-1.
local function marsh_grass_hook()
  local G = TL.marsh.grass
  local tile = data.raw.tile[G.tile]
  local original = tile and tile.autoplace and tile.autoplace.probability_expression
  if original == nil then
    log(cfg.identity.title .. ": no autoplace on " .. G.tile .. " for the marsh grass hook")
    return
  end
  local o = "(" .. tostring(original) .. ")"
  tile.autoplace.probability_expression = hook(o .. " + " .. G.key, o)
end

-- Without Alien Biomes: the highland's lean on the stony vanilla tiles, (score) + the ground key behind the gate
-- (ridges.lua); beside it their tile keys name the lean with the bonus (presets.lua).
local function ground_hooks()
  for _, name in ipairs(TL.vanilla.stony) do
    local tile = data.raw.tile[name]
    local original = tile and tile.autoplace and tile.autoplace.probability_expression
    if original ~= nil then
      local o = "(" .. tostring(original) .. ")"
      tile.autoplace.probability_expression = hook(o .. " + " .. cfg.keys.ground, o)
    end
  end
end

-- Milestone destroyed-europe: with the zone on, the volcanic heat bands take the ramp of cfg.destroyed.map_colors,
-- so the map view and the new-game preview tell them apart. Map colours only; no world changes.
local function heat_map_colors()
  local C = cfg.destroyed.map_colors
  for _, family in ipairs(C.families) do
    for band, color in ipairs(C.bands) do
      local tile = data.raw.tile["volcanic-" .. family .. "-heat-" .. band]
      if tile then
        tile.map_color = color
      end
    end
  end
end

if AB then
  vanilla_hooks()
  exclusion_hooks()
  palm_check()
  if settings.startup[cfg.settings.destroyed_europe.name].value then
    heat_map_colors()
  end
else
  marsh_grass_hook()
  ground_hooks()
end

-- Milestone trees-forests. Beside Alien Biomes, the base game's living trees, rocks, decals and plants come
-- back on Earth presets (S3 section 5; R3 3.4 items 3 to 6; design note 10): AB nils their
-- autoplace or takes them off Nauvis, so each is rebuilt from prototypes/tables/vanilla.lua behind the gate
-- tn_on with its key (trees.lua), restricted to the vanilla land tiles so AB's land keeps AB's own, and
-- listed on Nauvis where the base game lists it (trees ride the trees control). Then the great-forests
-- hook on every living tree but AB's palms, every world (ARCHITECTURE.md, "Stable hooks"): its outermost
-- if() is the forests gate, so on every world without an Earth preset each tree compiles its own autoplace.
local TR = cfg.trees
local VAN = require("prototypes.tables.vanilla")
local TREES = require("prototypes.expressions.trees")

local function nauvis_settings(kind)
  local s = nauvis and nauvis.map_gen_settings and nauvis.map_gen_settings.autoplace_settings and
    nauvis.map_gen_settings.autoplace_settings[kind]
  return s and s.settings
end

local function list_on_nauvis(kind, name)
  local s = nauvis_settings(kind)
  if s and s[name] == nil then
    s[name] = {}
  end
end

local function land_tiles()
  local out = {}
  for i, t in ipairs(TL.vanilla.tiles) do
    out[i] = t
  end
  return out
end

-- Puts the vanilla land tiles at the front of an AB tile restriction (never nils it: the plant would
-- spread onto AB's frozen and volcanic tiles, R3 3.4 item 6). The front, because the game walks a list
-- entry by entry for every tile and vanilla land is most of an Earth map (the list hook below).
local function extend_restriction(autoplace)
  local list, seen = land_tiles(), {}
  for _, t in ipairs(list) do
    seen[t] = true
  end
  for _, t in ipairs(autoplace.tile_restriction) do
    if not seen[t] then
      list[#list + 1] = t
    end
  end
  autoplace.tile_restriction = list
end

-- The living trees: each rebuilt behind the gate with its probability and richness keys.
-- 1 where AB's trees are off (config.lua tiles.scan), 0 where they grow.
local function tree_band()
  return "(1 - " .. TL.scan.body .. ")"
end

-- The restored trees stand on the adopted tiles too and stop where tiles.scan.body opens to AB's trees, so a
-- forest crosses APPROVALS 9's tiles inside the band: AB's trees are off there and vanilla's were not listed.
local function restore_trees(R)
  local n = 0
  local band = tree_band()
  local tiles = land_tiles()
  for _, t in ipairs(TL.ab_adopted) do
    if t ~= TL.marsh.water_mud.tile then
      tiles[#tiles + 1] = t
    end
  end
  for _, row in ipairs(VAN.trees) do
    local tree, names = data.raw.tree[row.tree], R.trees[row.tree]
    if tree and names then
      tree.autoplace = {control = row.control, order = row.order,
                        probability_expression = hook(names.p .. " * " .. band, R.tree_off),
                        richness_expression = hook(names.r, R.tree_off), tile_restriction = tiles}
      n = n + 1
    else
      log(cfg.identity.title .. ": vanilla tree " .. row.tree .. " is missing; not restored")
    end
  end
  return n
end

-- The rocks and decals: each rebuilt behind the gate with its key and listed on Nauvis.
local function restore_rocks(R)
  local n = 0
  for _, row in ipairs(VAN.rocks) do
    local proto, names = data.raw[row.type] and data.raw[row.type][row.name], R.rocks[row.name]
    if proto and names then
      proto.autoplace = {control = row.control, order = row.order, placement_density = row.placement_density,
                         probability_expression = hook(names.key, R.rock_off), tile_restriction = land_tiles()}
      list_on_nauvis(row.type == "simple-entity" and "entity" or "decorative", row.name)
      n = n + 1
    else
      log(cfg.identity.title .. ": vanilla " .. row.type .. " " .. row.name .. " is missing; not restored")
    end
  end
  return n
end

-- A base game text on the vanilla-scale temperature, which is what its boxes mean.
local function vanilla_scale(text)
  return (string.gsub(text, "%f[%w_]temperature%f[^%w_]", TR.temperature))
end

-- The decoratives AB keeps but takes off Nauvis: (own score) + key behind the gate, re-listed. The off value
-- reads none of these locals, so the vanilla-scale text changes no other world.
local function relist_decoratives(R)
  local n = 0
  for _, name in ipairs(VAN.relist) do
    local proto, key = data.raw["optimized-decorative"][name], R.decoratives[name]
    local autoplace = proto and proto.autoplace
    if autoplace and autoplace.probability_expression ~= nil and key then
      autoplace.probability_expression = hook("(" .. vanilla_scale(tostring(autoplace.probability_expression)) ..
        ") + " .. key, R.deco_off)
      for k, v in pairs(autoplace.local_expressions or {}) do
        if type(v) == "string" then
          autoplace.local_expressions[k] = vanilla_scale(v)
        end
      end
      autoplace.tile_restriction = land_tiles()
      list_on_nauvis("decorative", name)
      n = n + 1
    else
      log(cfg.identity.title .. ": vanilla decorative " .. name .. " is missing or has no autoplace; not re-listed")
    end
  end
  return n
end

-- The vanilla decoratives and dead trees AB restricts to its own tiles: the vanilla land tiles appended.
local function extend_restrictions()
  local n = 0
  for _, group in ipairs({{data.raw["optimized-decorative"], VAN.extend}, {data.raw.tree, VAN.dead_trees}}) do
    for _, name in ipairs(group[2]) do
      local autoplace = group[1] and group[1][name] and group[1][name].autoplace
      if autoplace and autoplace.tile_restriction then
        extend_restriction(autoplace)
        n = n + 1
      end
    end
  end
  return n
end

-- The base game's score where vanilla land lies, AB's elsewhere (config.lua trees.decor). A row's own text
-- reads its box under the local D.box, since six of these still hold vanilla's region_box on the other branch.
local function decor_hooks()
  local D = TR.decor
  local n = 0
  for _, row in ipairs(VAN.decor) do
    local proto = data.raw["optimized-decorative"][row.name]
    local autoplace = proto and proto.autoplace
    if autoplace and autoplace.probability_expression ~= nil then
      local own = "(" .. tostring(autoplace.probability_expression) .. ")"
      local text = string.gsub(row.text, "%f[%w_]region_box%f[^%w_]", D.box)
      if row.box then
        autoplace.local_expressions = autoplace.local_expressions or {}
        autoplace.local_expressions[D.box] = vanilla_scale(row.box)
      end
      local thin = D.thin[row.name]
      local on = vanilla_scale(text)
      -- `if` evaluates both branches, and a text AB left alone places nothing on its land at this temperature.
      if tostring(autoplace.probability_expression) ~= row.text then
        on = "if(" .. TL.scan.body .. " > " .. num(H.threshold) .. ", " ..
          (thin and (num(thin) .. " * " .. own) or own) .. ", " .. on .. ")"
      end
      autoplace.probability_expression = hook(on, own)
      n = n + 1
    else
      log(cfg.identity.title .. ": vanilla decorative " .. row.name .. " is missing or has no autoplace; no band score")
    end
  end
  return n
end

-- The same for the dead trees: AB's score elsewhere, and where vanilla land lies the base game's, off the
-- restored trees' keys, which read the vanilla-scale temperature.
local function dead_hooks(R)
  for _, name in ipairs(VAN.dead_trees) do
    local autoplace = data.raw.tree[name] and data.raw.tree[name].autoplace
    if autoplace and autoplace.probability_expression ~= nil then
      local keys = {}
      for i, t in ipairs(VAN.dead_scores[name]) do
        keys[i] = R.trees[t].p
      end
      local own = "(" .. tostring(autoplace.probability_expression) .. ")"
      autoplace.probability_expression = hook("if(" .. TL.scan.body .. " > " .. num(H.threshold) .. ", " .. own ..
        ", " .. string.format(VAN.dead_score, table.concat(keys, ", ")) .. ")", own)
    end
  end
end

local function restore_vanilla()
  local R = TR.restore
  local trees, rocks, relisted, extended = restore_trees(R), restore_rocks(R), relist_decoratives(R),
    extend_restrictions()
  decor_hooks()
  dead_hooks(R)
  log(cfg.identity.title .. ": restored " .. trees .. " vanilla trees and " .. rocks .. " rocks and decals, " ..
    "re-listed " .. relisted .. " decoratives, extended " .. extended .. " restrictions beside Alien Biomes")
end

-- Whether Nauvis places a prototype: its autoplace names a control Nauvis lists, or Nauvis's autoplace settings
-- list it. Another planet's trees (Space Age's Vulcanus lichen trees and Gleba plants) keep their prototypes
-- untouched, so no other planet compiles a hook (never touch other planets; compat-completeness
-- found the hook moving their programs and placements).
local function on_nauvis(kind, name, autoplace)
  local mgs = ((data.raw.planet or {}).nauvis or {}).map_gen_settings or {}
  local controls = mgs.autoplace_controls or {}
  local listed = ((mgs.autoplace_settings or {})[kind] or {}).settings or {}
  return (autoplace.control ~= nil and controls[autoplace.control] ~= nil) or listed[name] ~= nil
end

-- The great-forests hook on every living tree Nauvis places (the base game's dead and dry trees excepted,
-- S10). Alien Biomes' palms are left out too: their prototypes stay AB's (ARCHITECTURE.md, "Stable hooks"),
-- since the frozen palm table and its dump checks read them raw, and on Earth presets their probability
-- keys name the copies' second versions, which carry the boost.
local function boost_hooks()
  local skip = {}
  for _, name in ipairs(VAN.dead_trees) do
    skip[name] = true
  end
  for _, c in ipairs(PALM.copies) do
    skip[c.tree] = true
  end
  local names = {}
  for name, tree in pairs(data.raw.tree or {}) do
    if not skip[name] and tree.autoplace and tree.autoplace.probability_expression ~= nil and
        on_nauvis("entity", name, tree.autoplace) then
      names[#names + 1] = name
    end
  end
  table.sort(names)
  local base_tree = {}
  for _, row in ipairs(VAN.trees) do
    base_tree[row.tree] = true
  end
  for _, name in ipairs(names) do
    local autoplace = data.raw.tree[name].autoplace
    autoplace.probability_expression = TREES.boost(tostring(autoplace.probability_expression), base_tree[name],
      AB and tree_band())
  end
  log(cfg.identity.title .. ": the great-forests hook on " .. #names .. " living trees")
end

-- The list hook beside Alien Biomes (config.lua tiles.scan; design notes 2026-10-30 12:55): every AB-only
-- decorative and tree Nauvis places, with a list longer than the vanilla land tiles and none of them on
-- it, gets them at its front and, behind the gate, its probability times the keep body. On every world
-- without an Earth preset the hook folds and no vanilla land tile is placed beside Alien Biomes, so the
-- longer list changes nothing there. The keep body is 0 wherever those tiles may lie, so they add no
-- placement: what they end is the walk. An AB-only prototype loses its placements on the adopted tiles
-- and water-mud where vanilla may also lie (0.3 percent of the decoratives around Frankfurt).
local function list_hooks()
  local S = TL.scan
  local land = land_tiles()
  local on_land, skip, n = {}, {}, 0
  for _, t in ipairs(land) do
    on_land[t] = true
  end
  for _, c in ipairs(PALM.copies) do
    skip[c.tree] = true
  end
  for _, g in ipairs(S.types) do
    local names = {}
    for name, proto in pairs(data.raw[g.type] or {}) do
      local autoplace = proto.autoplace
      if not skip[name] and autoplace and autoplace.tile_restriction and autoplace.probability_expression ~= nil and
          #autoplace.tile_restriction > #land and on_nauvis(g.group, name, autoplace) then
        local vanilla = false
        for _, t in ipairs(autoplace.tile_restriction) do
          vanilla = vanilla or on_land[t] == true
        end
        if not vanilla then
          names[#names + 1] = name
        end
      end
    end
    table.sort(names)
    for _, name in ipairs(names) do
      local autoplace = data.raw[g.type][name].autoplace
      local original = "(" .. tostring(autoplace.probability_expression) .. ")"
      autoplace.probability_expression = hook(original .. " * " .. S.body, original)
      extend_restriction(autoplace)
      n = n + 1
    end
  end
  log(cfg.identity.title .. ": the list hook on " .. n .. " Alien Biomes autoplaces")
end

-- The highland lift on Alien Biomes' big rocks (ridges.lua): they read a noise of their own, not rock_density,
-- and stand on Alien Biomes' tiles, which is most of a range outside the temperate band. Each adds the key to
-- its peak, behind the gate, so on every world without an Earth preset the hook folds to Alien Biomes' text.
local function rock_lift_hooks()
  local RK = cfg.ridges.rocks
  local names = {}
  for name, proto in pairs(data.raw["simple-entity"] or {}) do
    local locals = proto.autoplace and proto.autoplace.local_expressions
    local skip = not (locals and locals.peaks_expr)
    for _, s in ipairs(RK.ab_skip) do
      skip = skip or string.find(name, s, 1, true) ~= nil
    end
    for _, p in ipairs(RK.ab_prefixes) do
      if not skip and string.sub(name, 1, #p) == p then
        names[#names + 1] = name
        break
      end
    end
  end
  table.sort(names)
  for _, name in ipairs(names) do
    local locals = data.raw["simple-entity"][name].autoplace.local_expressions
    locals.peaks_expr = hook(locals.peaks_expr .. " + " .. cfg.keys.rock_lift, locals.peaks_expr)
  end
  log(cfg.identity.title .. ": the highland rock hook on " .. #names .. " Alien Biomes rocks")
end

if AB then
  restore_vanilla()
  list_hooks()
  rock_lift_hooks()
end
boost_hooks()

-- Milestone ridges: the Earth-gated ridge exclusion on ore probability. For each Earth
-- ore of config.lua's ridges group whose resource has an autoplace, a wrapper body holds the live
-- probability expression (as the pack leaves it: base, Alien Biomes, the Oil Rig and the rest load
-- before this) times the ore clearance of prototypes/expressions/ridges.lua, and every Terra Nauvis
-- preset points the ore's probability key at it. Only those presets read the wrappers, so a default
-- world compiles none of them, and no resource prototype changes: no cliff_removal_probability edit,
-- which would change default worlds (A-1). resources-enemies moves the keys to its own wrappers under
-- the next version, leaving these defined.
--
-- Milestone resources-enemies: hotspots, the richness ramp, the enemy layer and offshore oil around the
-- pack's live autoplace (ARCHITECTURE.md milestone contract 9; versioning rule 3: these wrap the live
-- expressions on purpose, so bobenemies' cap and the Oil Rig's patch set keep acting, and Earth
-- freezes its own terms). Each wrapper is a folded if() on the hotspots toggle, so hotspots off
-- compiles the live expression alone (U5):
--   probability  the ore's ridges wrapper (live times the ridge clearance) or the hotspot term times
--                the same clearance, whichever is larger (S6: max(live, hotspot)); the presets' ore
--                probability keys move to this next version and ridges' bodies stay defined
--   richness     the live richness, times the ramp on the four solid ores, or the hotspot richness
--   enemies      max(live enemy_base_probability, the enemy layer of prototypes/expressions/enemies.lua)
--   offshore     with the Oil Rig loaded: its live probability times the sea mask (random wells on
--                open sea only, FEAS-07), or the field wells, which the stamp keeps on deepwater
local presets = data.raw["map-gen-presets"]["default"]
local clear = cfg.ridges.names.clear
local NE = data.raw["noise-expression"]

local function copy(t)
  local out = {}
  for k, v in pairs(t or {}) do
    out[k] = v
  end
  return out
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

local function text_of(v)
  if type(v) == "number" then
    return string.format(cfg.number_format, v)
  end
  return v
end

-- Every Terra Nauvis preset points these keys at these bodies.
local function point_presets(keys)
  for _, key in ipairs(cfg.preset_order) do
    local p = presets[cfg.presets[key].name]
    local names = p and p.basic_settings and p.basic_settings.property_expression_names
    if names then
      for k, v in pairs(keys) do
        names[k] = v
      end
    end
  end
end

-- Milestone ridges: the probability wrappers with the ridge clearance.
local function ridge_wrappers()
  local E, keys = {}, {}
  for _, o in ipairs(cfg.ridges.ores) do
    local r = data.raw.resource[o.resource]
    local ap = r and r.autoplace
    local live = ap and text_of(ap.probability_expression)
    if type(live) == "string" then
      E[#E + 1] = {type = "noise-expression", name = o.name, expression = "(" .. live .. ") * " .. clear,
                   local_expressions = copy(ap.local_expressions)}
      keys[o.key] = o.name
    elseif ap then
      log(cfg.identity.title .. ": the autoplace of " .. o.resource .. " holds no probability expression this " ..
          "version wraps; its ore keeps no ridge clearance")
    end
  end
  -- data:extend refuses an empty list, and a mod that replaces the base ores leaves this one empty
  if #E > 0 then
    data:extend(E)
  end
  point_presets(keys)
end

local RS = cfg.resources
local on = cfg.keys.hotspots .. " > " .. string.format(cfg.number_format, cfg.ridges.switch_threshold)
local HS = {}
for _, h in ipairs(cfg.hotspots.resources) do
  HS[h.resource] = h.names
end
local RAMPED = {}
for _, name in ipairs(RS.ramped) do
  RAMPED[name] = true
end

-- A wrapper body around a live expression: the live text becomes the local live_value beside the
-- autoplace's own locals, so each branch of the folded if() reads one copy.
local function wrapper(name, live, owner, expression)
  local locals = deep(owner and owner.local_expressions) or {}
  locals.live_value = live
  return {type = "noise-expression", name = name, expression = expression, local_expressions = locals,
          local_functions = deep(owner and owner.local_functions)}
end

-- Each Earth ore: the probability wrapper's next version and the richness wrapper.
local function ore_wrappers(W, keys)
  for _, o in ipairs(RS.ores) do
    local r = data.raw.resource[o.resource]
    local ap = r and r.autoplace
    local hs = HS[o.resource]
    local rich = ap and text_of(ap.richness_expression)
    -- only around ridges' probability wrapper: an ore that one does not wrap keeps the live autoplace
    if NE[o.p_v1] and hs and type(rich) == "string" then
      W[#W + 1] = {type = "noise-expression", name = o.p, expression = "if(" .. on .. ", max(" .. o.p_v1 .. ", " ..
                   hs.p .. " * " .. clear .. "), " .. o.p_v1 .. ")"}
      local base = RAMPED[o.resource] and ("live_value * " .. RS.ramp.name) or "live_value"
      W[#W + 1] = wrapper(o.r, rich, ap, "if(" .. on .. ", max(" .. base .. ", " .. hs.r .. "), " .. base .. ")")
      keys[o.probability] = o.p
      keys[o.richness] = o.r
    elseif ap then
      log(cfg.identity.title .. ": " .. o.resource .. " has no wrapper this version builds; its ore keeps no " ..
          "hotspots")
    end
  end
end

-- The enemy wrapper around the live enemy_base_probability (bobenemies' or vanilla's).
local function enemy_wrapper(W, keys)
  local ebp = NE[cfg.keys.enemy]
  local layer = cfg.enemies.layer
  local live = ebp and text_of(ebp.expression)
  if NE[layer] and type(live) == "string" then
    W[#W + 1] = wrapper(cfg.enemies.wrapper, live, ebp, "if(" .. on .. ", max(live_value, " .. layer ..
      "), live_value)")
    keys[cfg.keys.enemy] = cfg.enemies.wrapper
  end
end

-- The Oil Rig's offshore oil, when it is loaded.
local function offshore_wrappers(W, keys)
  local OF = RS.offshore
  local res = data.raw.resource[OF.resource]
  local ap = res and res.autoplace
  local p, r = ap and text_of(ap.probability_expression), ap and text_of(ap.richness_expression)
  local hs = HS[OF.resource]
  if type(p) == "string" and type(r) == "string" and hs then
    local random = "live_value * " .. RS.sea.name
    W[#W + 1] = wrapper(OF.p, p, ap, "if(" .. on .. ", max(" .. random .. ", " .. hs.p .. "), " .. random .. ")")
    W[#W + 1] = wrapper(OF.r, r, ap, "if(" .. on .. ", max(live_value, " .. hs.r .. "), live_value)")
    keys[OF.probability] = OF.p
    keys[OF.richness] = OF.r
  end
end

-- Natural regular patches (config.lua resources.natural): each live patch expression's own text, its call
-- moved to the Earth copy of vanilla's function, with the preset's redirect of the live name. The wrappers
-- above keep reading the live autoplace, whose text names the live patch expression, so they stay as they
-- are, and a mod that replaced a patch expression keeps its own.
local function natural_patches(W, keys)
  local NP = RS.natural
  for _, b in ipairs(NP.bodies) do
    local live = NE[b.live]
    local text = live and text_of(live.expression)
    if type(text) == "string" and string.find(text, NP.vanilla_fn, 1, true) then
      W[#W + 1] = {type = "noise-expression", name = b.name, expression = (string.gsub(text, NP.vanilla_fn, NP.fn))}
      keys[b.live] = b.name
    end
  end
end

ridge_wrappers()
local W, keys = {}, {}
natural_patches(W, keys)
ore_wrappers(W, keys)
enemy_wrapper(W, keys)
offshore_wrappers(W, keys)
if #W > 0 then
  data:extend(W)
end
point_presets(keys)
