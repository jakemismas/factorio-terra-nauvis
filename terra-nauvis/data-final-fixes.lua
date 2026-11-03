-- Everything that reads other mods' final state: entity wrappers and gated hooks on shared
-- prototypes (ARCHITECTURE.md, "Module map" and "Stable hooks"). Waterways: the ford hook.
-- Climate tiles: the marsh keys, and beside Alien Biomes the vanilla land tiles, the exclusion
-- of non-adopted AB tiles from temperate bands and the palm copies, built from the installed palms. Trees
-- and forests: beside Alien Biomes the base game's trees, rocks, decals and plants, and on every world
-- the great-forests hook. Ridges: the Earth-gated ridge exclusion on ore probability. Resources
-- and enemies: the ore, richness, enemy and offshore-oil wrappers around the pack's live autoplace.
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

-- A tile's own six-octave noise as two of the shared fields (config.lua tiles.noise_share).
local function mixed_noise(seed1)
  local NS = TL.noise_share
  local n, steps = #NS.fields, #NS.steps
  local seed = tonumber(seed1)
  local j = math.floor(seed / n)
  local a = seed % n
  local b = (a + NS.steps[j % steps + 1]) % n
  local signs = math.floor(j / steps) % NS.sign_patterns
  local w = num(NS.weight)
  return "(" .. (signs >= 2 and "-" or "") .. w .. " * " .. NS.fields[a + 1] .. (signs % 2 == 1 and " - " or " + ") ..
    w .. " * " .. NS.fields[b + 1] .. ")"
end

-- The vanilla land tiles beside Alien Biomes (S3 section 2): AB keeps their autoplace on the
-- prototypes and takes them off Nauvis (R3 3.2); re-listed here behind the gate, each adds its key.
local function vanilla_hooks()
  local V = TL.vanilla
  for i, name in ipairs(V.tiles) do
    local tile = data.raw.tile[name]
    if tile and tile.autoplace and tile.autoplace.probability_expression then
      tile.autoplace.probability_expression = hook("(" .. tostring(tile.autoplace.probability_expression) .. ") + " ..
        V.keys[name] .. " + " .. V.mix.key .. " * " .. mixed_noise(V.mix.first_seed1 + i - 1) ..
        " * (" .. V.keys[name] .. " > " .. num(V.bonus / 2) .. ")", V.off)
      register(name)
    else
      log(cfg.identity.title .. ": vanilla tile " .. name .. " is missing or has no autoplace")
    end
  end
end

-- A tile's own noise is found by its arguments, not by another mod's text: a multioctave_noise call that holds the
-- shared fields' own parameters (config.lua tiles.noise_share) and a whole-number seed1. A call with any other
-- argument, or with a call nested in it, keeps the tile's own noise.
local SHARED_CALL = "multioctave_noise{"
local SHARED_NAMES = {x = "x", y = "y", seed0 = "map_seed"}
local shared_calls = 0

local function trim(s)
  return string.match(s, "^%s*(.-)%s*$")
end

-- A number, or numbers divided in turn (1/6/4), as the noise language reads them; nil for anything else.
local function quotient(v)
  local q
  for part in string.gmatch(v, "[^/]+") do
    local n = tonumber(trim(part))
    if n == nil then
      return nil
    end
    q = q and q / n or n
  end
  return q
end

local function call_args(body)
  local args = {}
  for part in string.gmatch(body .. ",", "([^,]*),") do
    local k, v = string.match(part, "^%s*([%a_][%w_]*)%s*=%s*(.-)%s*$")
    if k == nil or args[k] ~= nil then
      return nil
    end
    args[k] = v
  end
  return args
end

local function shared_seed(body)
  local NS = TL.noise_share
  local numbers = {offset_x = NS.offset_x, persistence = NS.persistence, octaves = NS.octaves,
                   input_scale = 1 / NS.wavelength_tiles, output_scale = NS.output_scale}
  local args = not string.find(body, "{", 1, true) and call_args(body)
  if not args then
    return nil
  end
  for k in pairs(args) do
    if SHARED_NAMES[k] == nil and numbers[k] == nil and k ~= "seed1" then
      return nil
    end
  end
  for k, v in pairs(SHARED_NAMES) do
    if args[k] ~= v then
      return nil
    end
  end
  for k, v in pairs(numbers) do
    if args[k] == nil or quotient(args[k]) ~= v then
      return nil
    end
  end
  return args.seed1 and string.match(args.seed1, "^%d+$")
end

local function shared_noise(text)
  local out, pos = {}, 1
  while true do
    local s, e = string.find(text, SHARED_CALL, pos, true)
    local close = s and string.find(text, "}", e + 1, true)
    if not close then
      break
    end
    local seed = not (s > 1 and string.find(string.sub(text, s - 1, s - 1), "[%w_]")) and
      shared_seed(string.sub(text, e + 1, close - 1))
    if seed then
      out[#out + 1] = string.sub(text, pos, s - 1) .. mixed_noise(seed)
      shared_calls = shared_calls + 1
      pos = close + 1
    else
      out[#out + 1] = string.sub(text, pos, e)
      pos = e + 1
    end
  end
  out[#out + 1] = string.sub(text, pos)
  return table.concat(out)
end

-- A tile score with the three climate fields read through the grain's copies (config.lua climate.grain)
-- and its own noise through the shared fields.
local function grain_scores(text)
  for field, key in pairs(cfg.climate.grain.keys) do
    text = string.gsub(text, "%f[%w_:]" .. field .. "%f[^%w_:]", key)
  end
  return shared_noise(text)
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
  log(cfg.identity.title .. ": shared noise in " .. shared_calls .. " tile scores")
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
  -- 0.3.1: the devastation field's dry dirt (destroyed.dev.tiles), whose score folds to -inf on every world made before
  for _, t in ipairs(cfg.destroyed.dev.tiles) do
    if t.tile == name then
      return "max(" .. text .. ", " .. t.body .. ")"
    end
  end
  return text
end

-- Blue corrupted UK and Australia's palette takes its max the same way (config.lua blue).
local function with_blue(name, text)
  for _, t in ipairs(cfg.blue.tiles) do
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
    autoplace.probability_expression = hook(with_blue(name, with_chaos(name, grain_scores(original) .. " + " .. X.key)),
      original)
  end
  log(cfg.identity.title .. ": temperate exclusion on " .. #names .. " Alien Biomes tiles")
  grain_hooks(excluded, #names)
  vegetation_hooks()
end

-- The palm switch: Earth presets name the Earth copies of the palms, built here because
-- Alien Biomes' data-final-fixes, which runs first, is the last to touch a tree. The installed palms are held to
-- config.lua's digest (tools/build_palms.py writes the same text): a palm that differs or lost its autoplace
-- (Alien Biomes' disable-vegetation setting, a newer release) makes every copy the neutral body and points both keys at
-- it on every Earth preset, so it grows nowhere on new Earth worlds instead of reading a dangling name, and the log
-- says why; the gate's dump facts fail on it too. AB's prototypes stay untouched, so every other world compiles exactly
-- AB's program. Any other tree that reads elevation is logged loudly: the M2 isolation walk (T15 (b)) then fails on it.
local PALM = TL.palm

local function sorted_keys(t)
  local keys = {}
  for k in pairs(t or {}) do
    keys[#keys + 1] = k
  end
  table.sort(keys)
  return keys
end

local function palm_value(v)
  return type(v) == "number" and string.format(PALM.digest.number, v) or tostring(v)
end

-- The digest's canonical text: tools/build_palms.py canonical writes the same lines.
local function palm_text(src)
  local lines = {}
  local function locals(t)
    for _, k in ipairs(sorted_keys(t)) do
      lines[#lines + 1] = "l " .. k .. " " .. palm_value(t[k])
    end
  end
  for _, tree in ipairs(sorted_keys(src.trees)) do
    local rec = src.trees[tree]
    lines[#lines + 1] = "tree " .. tree
    lines[#lines + 1] = "p " .. palm_value(rec.probability_expression)
    lines[#lines + 1] = "r " .. palm_value(rec.richness_expression)
    locals(rec.local_expressions)
  end
  for _, name in ipairs(sorted_keys(src.functions)) do
    local f = src.functions[name]
    lines[#lines + 1] = "f " .. name .. " " .. table.concat(f.parameters, ",")
    lines[#lines + 1] = "e " .. palm_value(f.expression)
    locals(f.local_expressions)
  end
  return table.concat(lines, "\n")
end

local function fnv(text, base)
  local h = base
  for i = 1, #text do
    h = bit32.bxor(h, string.byte(text, i))
    h = (h * PALM.digest.prime_low + bit32.lshift(h, PALM.digest.prime_shift)) % PALM.digest.word
  end
  return h
end

local function palm_digest(src)
  local text = palm_text(src)
  local out = {}
  for i, base in ipairs(PALM.digest.bases) do
    out[i] = string.format(PALM.digest.hex, fnv(text, base))
  end
  return table.concat(out)
end

-- A text's names, quoted strings left out, as tools/build_palms.py idents reads them.
local function idents(text)
  local out = {}
  if type(text) == "string" then
    local bare = string.gsub(string.gsub(text, "'[^']*'", " "), '"[^"]*"', " ")
    for name in string.gmatch(bare, "[%a_][%w_:]*") do
      out[name] = true
    end
  end
  return out
end

-- The installed palms into src, with one walk per palm for the functions its texts call; or nil and why not.
local function palm_trees(src)
  local jobs = {}
  for _, c in ipairs(PALM.copies) do
    local proto = (data.raw.tree or {})[c.tree]
    local ap = proto and proto.autoplace
    if not (ap and ap.probability_expression ~= nil and ap.richness_expression ~= nil) then
      return nil, c.tree .. " has no whole autoplace"
    end
    if not src.trees[c.tree] then
      local locals = ap.local_expressions or {}
      src.trees[c.tree] = {probability_expression = ap.probability_expression,
                           richness_expression = ap.richness_expression, local_expressions = locals}
      local texts = {ap.probability_expression, ap.richness_expression}
      for _, v in pairs(locals) do
        texts[#texts + 1] = v
      end
      jobs[#jobs + 1] = {where = c.tree, known = locals, texts = texts}
    end
  end
  return jobs
end

-- A called function into src, with a walk of its own texts; or why it cannot be carried.
local function palm_function(src, jobs, name, f)
  if f.local_functions then
    return "the noise function " .. name .. " has local functions"
  end
  src.functions[name] = {parameters = f.parameters or {}, expression = f.expression,
                         local_expressions = f.local_expressions}
  local known, texts = {}, {f.expression}
  for _, p in ipairs(f.parameters or {}) do
    known[p] = true
  end
  for k, v in pairs(f.local_expressions or {}) do
    known[k] = true
    texts[#texts + 1] = v
  end
  jobs[#jobs + 1] = {where = name, known = known, texts = texts}
  return nil
end

-- One text's names: a function goes into src, a named expression cannot be carried.
local function palm_names(src, jobs, job, text, reads)
  for name in pairs(idents(text)) do
    if not job.known[name] and not reads[name] then
      local f = (data.raw["noise-function"] or {})[name]
      local why = nil
      if f and not src.functions[name] then
        why = palm_function(src, jobs, name, f)
      elseif not f and (data.raw["noise-expression"] or {})[name] then
        why = job.where .. " reads the named expression " .. name
      end
      if why then
        return why
      end
    end
  end
  return nil
end

-- The installed palms and every noise function their texts call, or nil and why not.
local function palm_source()
  local src = {trees = {}, functions = {}}
  local jobs, why = palm_trees(src)
  if not jobs then
    return nil, why
  end
  local reads = {}
  for _, name in ipairs(PALM.digest.reads) do
    reads[name] = true
  end
  while #jobs > 0 do
    local job = table.remove(jobs)
    for _, text in ipairs(job.texts) do
      why = palm_names(src, jobs, job, text, reads)
      if why then
        return nil, why
      end
    end
  end
  return src
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
  local TREES = require("prototypes.expressions.trees")
  local src, why
  if AB then
    src, why = palm_source()
    if src and palm_digest(src) ~= PALM.digest.value then
      src, why = nil, "they differ from Alien Biomes " .. PALM.digest.version .. " by digest"
    end
    if not src then
      local presets = data.raw["map-gen-presets"] and data.raw["map-gen-presets"]["default"] or {}
      for _, c in ipairs(PALM.copies) do
        for _, key in ipairs(cfg.preset_order) do
          local p = presets[cfg.presets[key].name]
          local names = p and p.basic_settings and p.basic_settings.property_expression_names
          if names then
            names[c.key] = PALM.neutral
          end
        end
      end
      log(cfg.identity.title .. ": ERROR the palms cannot be copied (" .. why .. "); Earth presets name the neutral " ..
        "body")
    end
  end
  data:extend(TREES.palm_bodies(src))
  if not AB then
    return
  end
  local copied = {}
  for _, c in ipairs(PALM.copies) do
    copied[c.tree] = true
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

-- Destroyed Europe: with the zone on, the volcanic heat bands take the ramp of cfg.destroyed.map_colors,
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

-- Blue corrupted UK and Australia: Alien Biomes' colours are near black on the map view (config.lua blue). Map colours
-- only; no world changes.
local function blue_map_colors()
  for _, t in ipairs(cfg.blue.tiles) do
    local tile = data.raw.tile[t.tile]
    if tile then
      tile.map_color = t.map
    end
  end
end

palm_check()
if AB then
  vanilla_hooks()
  exclusion_hooks()
  if settings.startup[cfg.settings.destroyed_europe.name].value then
    heat_map_colors()
  end
  if settings.startup[cfg.settings.blue_corrupted.name].value then
    blue_map_colors()
  end
else
  marsh_grass_hook()
  ground_hooks()
  local F = TL.frozen
  data.raw.tile[F.tile].autoplace = {probability_expression = hook(F.key, F.off)}
  register(F.tile)
end

-- Trees and forests. Beside Alien Biomes, the base game's living trees, rocks, decals and plants come
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
  -- Alien Biomes' include settings can drop an adopted tile, and a tile_restriction naming a missing tile stops the
  -- game loading on every world.
  for _, t in ipairs(TL.ab_adopted) do
    if t ~= TL.marsh.water_mud.tile and data.raw.tile[t] then
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

-- The tiles of every other planet that places this decorative (its settings list it, or its property names give
-- it a probability), sorted: Space Age's Gleba lists light-mud-decal and several of the green plants.
local function planet_tiles_for(name)
  local found = {}
  for pname, planet in pairs(data.raw.planet or {}) do
    local mgs = pname ~= "nauvis" and planet.map_gen_settings
    local aps = mgs and mgs.autoplace_settings or {}
    local listed = aps.decorative and aps.decorative.settings and aps.decorative.settings[name] ~= nil
    local pen = mgs and mgs.property_expression_names or {}
    if listed or pen["decorative:" .. name .. ":probability"] ~= nil then
      for t in pairs(aps.tile and aps.tile.settings or {}) do
        found[#found + 1] = t
      end
    end
  end
  table.sort(found)
  return found
end

-- A re-listed decorative's tiles: the vanilla land tiles, then the tiles of every other planet that places it
-- which its old restriction allowed (all of them where it had none), less any Nauvis places. The land list
-- alone took light-mud-decal off Gleba beside Alien Biomes and Space Age (69 in the probe's near block without
-- Terra Nauvis, 0 with it). Nauvis never holds an added tile, so no Nauvis chunk changes, and without another
-- planet the list stays the land list.
local function relist_restriction(name, old)
  local list, seen = land_tiles(), {}
  for _, t in ipairs(list) do
    seen[t] = true
  end
  local allowed
  if old then
    allowed = {}
    for _, t in ipairs(old) do
      allowed[t] = true
    end
  end
  for _, t in ipairs(planet_tiles_for(name)) do
    if (allowed == nil or allowed[t]) and not seen[t] and data.raw.tile[t] and
        not (tile_settings and tile_settings[t] ~= nil) then
      seen[t] = true
      list[#list + 1] = t
    end
  end
  return list
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
      autoplace.tile_restriction = relist_restriction(name, autoplace.tile_restriction)
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
-- untouched, so no other planet compiles a hook (2026-10-28: never touch other planets; compat-completeness
-- found the hook moving their programs and placements).
local function on_nauvis(kind, name, autoplace)
  local mgs = ((data.raw.planet or {}).nauvis or {}).map_gen_settings or {}
  local controls = mgs.autoplace_controls or {}
  local listed = ((mgs.autoplace_settings or {})[kind] or {}).settings or {}
  return (autoplace.control ~= nil and controls[autoplace.control] ~= nil) or listed[name] ~= nil
end

-- The great-forests hook on every living tree Nauvis places (the base game's dead and dry trees excepted,
-- S10). Alien Biomes' palms are left out too: their prototypes stay AB's (ARCHITECTURE.md, "Stable hooks"),
-- since the palm copies and their digest read them raw, and on Earth presets their probability
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

-- Destroyed Europe, the exclusion (prototypes/zone_exclusion.lua): last, so each hook wraps a tree's and a
-- plant's final text, and the dead trees' copies take no hook of their own.
if AB then
  require("prototypes.zone_exclusion").apply(cfg.destroyed.exclusion, on_nauvis)
  require("prototypes.zone_exclusion").apply(cfg.blue.exclusion, on_nauvis)
end
-- Trees and plants off a hotspot's solid ore (config.lua resources.ore_trees), with and without Alien Biomes, over
-- every tile: every tree Nauvis places takes the hook with the trees' share, then every plant but the kept kinds with
-- the plants'.
do
  local OT = cfg.resources.ore_trees
  local tiles = {}
  for name in pairs(data.raw.tile) do
    tiles[#tiles + 1] = name
  end
  table.sort(tiles)
  local apply = require("prototypes.zone_exclusion").apply
  apply({key = OT.key, open = OT.open, tiles = tiles, plants = {keep = {""}, drop = {}}}, on_nauvis)
  local every_tree = {}
  for name in pairs(data.raw.tree or {}) do
    every_tree[name] = true
  end
  apply({key = OT.key, open = OT.plants.open, tiles = tiles, plants = OT.plants, keep_trees = every_tree}, on_nauvis)
end

-- Blue only in the zone (config.lua blue.no_blue): around every other hook, so inside the zone each prototype keeps its
-- whole text, and a world without the key folds to it everywhere.
local function no_blue_hooks()
  local NB = cfg.blue.no_blue
  local gate = NB.key .. " > " .. num(H.threshold)
  local function has(name, words)
    for _, w in ipairs(words) do
      if string.find(name, w, 1, true) then
        return true
      end
    end
    return false
  end
  local function each(group, kind, pick, wrap)
    local names, n = {}, 0
    for name in pairs(group or {}) do
      names[#names + 1] = name
    end
    table.sort(names)
    for _, name in ipairs(names) do
      local autoplace = group[name].autoplace
      if autoplace and autoplace.probability_expression ~= nil and pick(name) and on_nauvis(kind, name, autoplace) then
        local own = "(" .. tostring(autoplace.probability_expression) .. ")"
        autoplace.probability_expression = "if(" .. gate .. ", " .. wrap(own, name) .. ", " .. own .. ")"
        n = n + 1
      end
    end
    return n
  end
  local tree_set = {}
  for _, name in ipairs(NB.trees) do
    tree_set[name] = true
  end
  -- Each blue tile's text as it stands, for its counterpart (NB.swap), which takes the tile's place outside the zone:
  -- -inf on a tile alone let grey dirt and water-mud take Moscow's teal grass.
  local swapped = {}
  local function counterpart(name)
    for _, p in ipairs(NB.tile_prefixes) do
      if string.sub(name, 1, #p) == p then
        for _, w in ipairs(NB.words) do
          local i = string.find(name, w, 1, true)
          if i then
            return string.sub(name, 1, i - 1) .. NB.swap[p] .. string.sub(name, i + #w)
          end
        end
      end
    end
  end
  local tiles = each(data.raw.tile, "tile", function(name)
    for _, p in ipairs(NB.tile_prefixes) do
      if string.sub(name, 1, #p) == p then
        return has(name, NB.words)
      end
    end
    return false
  end, function(own, name)
    local c = counterpart(name)
    if c and data.raw.tile[c] and data.raw.tile[c].autoplace then
      swapped[c] = swapped[c] or {}
      table.insert(swapped[c], own .. " + " .. NB.out)
    end
    return own .. " + " .. NB.tile
  end)
  local counterparts = 0
  for _, c in ipairs(sorted_keys(swapped)) do
    local autoplace = data.raw.tile[c].autoplace
    local own = "(" .. tostring(autoplace.probability_expression) .. ")"
    autoplace.probability_expression = "if(" .. gate .. ", max(" .. own .. ", " .. table.concat(swapped[c], ", ") ..
      "), " .. own .. ")"
    counterparts = counterparts + 1
  end
  local plants = each(data.raw["optimized-decorative"], "decorative", function(name)
    return has(name, NB.words)
  end, function(own)
    return own .. " * " .. NB.open
  end)
  local trees = each(data.raw.tree, "entity", function(name)
    return tree_set[name] == true
  end, function(own)
    return own .. " * " .. NB.open
  end)
  log(cfg.identity.title .. ": blue only in the zone on " .. tiles .. " tiles (" .. counterparts ..
    " counterparts), " .. plants .. " plants and " .. trees .. " trees")
end
if AB then
  no_blue_hooks()
end

-- No normal plant in the Blue zone (config.lua blue.plants2): green and olive plants that can stand on its tiles take
-- its open, behind the zone's own gate and a key only new worlds hold.
local function zone_plant_hooks()
  local B, P2 = cfg.blue, cfg.blue.plants2
  local zone_tiles = {}
  for _, t in ipairs(B.exclusion.tiles) do
    zone_tiles[t] = true
  end
  local n = 0
  for _, name in ipairs(sorted_keys(data.raw["optimized-decorative"])) do
    local autoplace = data.raw["optimized-decorative"][name].autoplace
    local green = false
    for _, w in ipairs(P2.words) do
      green = green or string.find(name, w, 1, true) ~= nil
    end
    local stands = autoplace and autoplace.tile_restriction == nil
    for _, t in ipairs((autoplace or {}).tile_restriction or {}) do
      stands = stands or zone_tiles[t] == true
    end
    if green and stands and autoplace.probability_expression ~= nil and on_nauvis("decorative", name, autoplace) then
      local own = "(" .. tostring(autoplace.probability_expression) .. ")"
      autoplace.probability_expression = "if(" .. P2.key .. " > " .. num(H.threshold) .. ", if(" .. B.exclusion.key ..
        " > " .. num(H.threshold) .. ", " .. own .. " * " .. B.exclusion.open .. ", " .. own .. "), " .. own .. ")"
      n = n + 1
    end
  end
  log(cfg.identity.title .. ": no normal plant in the blue zone on " .. n .. " plants")
end
if AB then
  zone_plant_hooks()
end

-- Ridges: the Earth-gated ridge exclusion on ore probability. For each Earth
-- ore of config.lua's ridges group whose resource has an autoplace, a wrapper body holds the live
-- probability expression (as the pack leaves it: base, Alien Biomes, the Oil Rig and the rest load
-- before this) times the ore clearance of prototypes/expressions/ridges.lua, and every Terra Nauvis
-- preset points the ore's probability key at it. Only those presets read the wrappers, so a default
-- world compiles none of them, and no resource prototype changes: no cliff_removal_probability edit,
-- which would change default worlds (A-1). resources-enemies moves the keys to its own wrappers under
-- the next version, leaving these defined (design rule 21).
--
-- Resources and enemies: hotspots, the richness ramp, the enemy layer and offshore oil around the
-- pack's live autoplace (ARCHITECTURE.md contract 9; versioning rule 3: these wrap the live
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

-- Ridges: the probability wrappers with the ridge clearance.
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
local HS, FLUID, HROW = {}, {}, {}
for _, h in ipairs(cfg.hotspots.resources) do
  HS[h.resource] = h.names
  FLUID[h.resource] = h.fluid ~= nil
  HROW[h.resource] = h
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

-- 0.3.0's richness wrapper of one ore (config.lua resources.richness_v2): the same choice as the first, with the
-- distance read as the reference map has it past ref_scale, and a solid hotspot ore lifted to the regular ore's
-- richness round it. Up to ref_scale the regular branch folds to the first wrapper's text.
local RV = RS.richness_v2
local ORE_CURVES = require("prototypes.ore_curves")
local function richness_v2(W, keys, o, ap, rich, hs, gen)
  gen = gen or {name = o.r2, bodies = cfg.hotspots_v2.v3.bodies}
  local S = cfg.keys.scale
  local function f(d)
    return "max((" .. num(RV.rich_offset) .. " + " .. d .. ") / " .. num(RV.rich_span) .. ", 1)"
  end
  local function ramp(d)
    local RP = RS.ramp
    return "(1 + " .. num(RP.gain) .. " * clamp((" .. d .. " - " .. num(RP.from) .. ") / " .. num(RP.span) .. ", 0, 1))"
  end
  local ramped = RAMPED[o.resource]
  local function F(d)
    return ramped and (f(d) .. " * " .. ramp(d)) or f(d)
  end
  local far = S .. " > " .. num(RV.ref_scale)
  local own = ramped and ("live_value * " .. RS.ramp.name) or "live_value"
  local base = "if(" .. far .. ", live_value * " .. f("rv_d") .. " / " .. f("distance") ..
    (ramped and (" * " .. ramp("rv_d")) or "") .. ", " .. own .. ")"
  local flat
  if RV.vanilla then
    -- regular ore's richness factor at the flattened distance (resources.natural.flat): 1 out to the knee
    base = "live_value * rv_flat"
    flat = f(ORE_CURVES.flat_distance()) .. " / " .. f("distance")
  end
  local hot = hs.r
  local fh
  local V3 = cfg.hotspots_v2.v3
  if not FLUID[o.resource] and gen.bodies[o.resource] then
    -- the third table (hotspots_v2.v3): per_tile times vanilla's mean regular ore per tile here, times the body's
    -- height (held to peak_cap of a body_tiles cone's mean, where bodies crowd) over that mean, times the richness
    -- slider
    local h = HROW[o.resource]
    -- a far field's smaller bodies (ore_curves.lua body_scale) stand f ^ 0.5 as high: the mean height reads that
    hot = num(V3.rich_fit * V3.per_tile / ORE_CURVES.body_height(h)) .. " / rv_fh * " .. ORE_CURVES.per_tile(h) ..
      " * var('control:" .. o.resource .. ":richness') * min(" .. gen.bodies[o.resource] .. ", " ..
      num(V3.peak_cap * ORE_CURVES.body_height(h)) .. " * rv_fh)"
    -- the third table's factor on a small row's ore per tile (hotspots_v3 rich), 1 off its footprint
    if gen.rich_body and gen.rich_body[o.resource] then
      hot = hot .. " * " .. gen.rich_body[o.resource]
    end
    fh = ORE_CURVES.height_scale(h)
  elseif not FLUID[o.resource] then
    hot = hs.r .. " * max(1, " .. num(RV.lift) .. " * " .. F("rv_d") .. " / (" .. F("distance") .. ") ^ " ..
      num(RV.cube_root) .. ")"
  end
  local w = wrapper(gen.name, rich, ap, "if(" .. on .. ", max(rv_base, " .. hot .. "), rv_base)")
  if string.find(base .. " " .. hot, "rv_d", 1, true) then
    w.local_expressions.rv_d = "if(" .. far .. ", distance * " .. num(RV.ref_scale) .. " / " .. S .. ", distance)"
  end
  w.local_expressions.rv_base = base
  if flat then
    w.local_expressions.rv_flat = flat
  end
  if fh then
    w.local_expressions.rv_fh = fh
  end
  W[#W + 1] = w
  keys[o.richness] = gen.name
end

-- 0.3.0's probability wrapper of a solid ore: the hotspot term's value lowered by the wobble (config.lua
-- resources.richness_v2.edge), and Batu Hijau's copper kept off Lombok (richness_v2.lombok). The value is the second
-- table's body: new worlds read that table through the first one's names.
local function probability_v3(W, keys, o, gen)
  gen = gen or {name = o.p3, bodies = cfg.hotspots_v2.v3.bodies, lombok_row = RV.lombok.row}
  local keep = "1"
  local LB = RV.lombok
  if o.resource == LB.resource then
    -- west of the strait on each map's own chain (the region layer's chain, whose frame later versions keep), near the
    -- row: the map's u against the strait's column, folded on the per-save map number
    local west, ids = {}, {}
    for _, key in ipairs(cfg.map_order) do
      for _, v in ipairs({cfg.frames[key]}) do
        if v.geo_id == cfg.layer_chain_geo[key] then
          local cut = (LB.cut_lon - cfg.maps[key].lon_left_edge) * cfg.coordinates.px_per_degree - 1 / 2
          west[#west + 1] = "(" .. v.u .. " < " .. num(cut) .. ")"
          ids[#ids + 1] = cfg.maps[key].id
        end
      end
    end
    local fold = west[#west]
    for i = #west - 1, 1, -1 do
      fold = "if(" .. cfg.keys.map .. " == " .. num(ids[i]) .. ", " .. west[i] .. ", " .. fold .. ")"
    end
    local pd = cfg.regions.names.row.pd .. gen.lombok_row .. cfg.regions.names.suffix
    keep = "(1 - " .. fold .. " * (" .. pd .. " < " .. num(LB.reach_px) .. "))"
  end
  -- the cone's least slope, the first table's bound (config.lua hotspots.size note)
  local rq = HROW[o.resource].rq
  local slope = cfg.hotspots.spot.cone_factor / (math.pi * rq * rq * rq)
  local v3 = cfg.hotspots_v2.v3
  local body = gen.bodies[o.resource] or cfg.hotspots_v2.bodies[o.resource]
  local edge_trim = gen.bodies[o.resource] and v3.trim or RV.edge.trim
  -- a far field's bodies (ore_curves.lua body_scale) are f ^ 0.5 as wide: the wobble's trim follows them
  local fscale = gen.bodies[o.resource] and (" * " .. ORE_CURVES.height_scale(HROW[o.resource])) or ""
  local value = "clamp(" .. body .. " - " .. num(edge_trim * slope) .. " * " ..
    RV.edge.wobble .. fscale .. ", 0, 1)"
  W[#W + 1] = {type = "noise-expression", name = gen.name, expression = "if(" .. on .. ", max(" .. o.p_v1 .. ", " ..
               value .. " * " .. clear .. " * " .. keep .. "), " .. o.p_v1 .. ")"}
  keys[o.probability] = gen.name
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
      if o.r2 then
        richness_v2(W, keys, o, ap, rich, hs)
      end
      if o.p3 then
        probability_v3(W, keys, o)
      end
      -- 0.3.1: the same two wrappers over the third table's bodies (config.lua hotspots_v3)
      if o.r3 and o.p4 then
        local H3 = cfg.hotspots_v3
        richness_v2(W, keys, o, ap, rich, hs, {name = o.r3, bodies = H3.bodies, rich_body = H3.rich_body})
        probability_v3(W, keys, o, {name = o.p4, bodies = H3.bodies, lombok_row = RV.lombok.row3})
      end
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
    -- New worlds: inside the second table's layer the layer stands alone (expressions/enemies.lua).
    local H2 = cfg.hotspots_v2
    W[#W + 1] = wrapper(H2.nests.wrapper, live, ebp, "if(" .. on .. ", if(" .. H2.enemy_layer ..
      " > " .. num(H2.nests.outside) .. ", " .. H2.enemy_layer .. ", live_value), live_value)")
    -- 0.3.0: the bases scattered (config.lua enemies.scatter), off a hotspot's ore while hotspots are on.
    local SC = cfg.enemies.scatter
    local solid = {}
    for _, resource in ipairs(RS.ramped) do
      solid[#solid + 1] = H2.v3.bodies[resource]
    end
    solid[#solid + 1] = H2.v3.bodies["uranium-ore"]
    local function draw(x, y, seed)
      return "random_penalty{x = " .. x .. ", y = " .. y .. ", source = 1, amplitude = 1, seed = " .. num(seed) .. "}"
    end
    local L = num(SC.run)
    -- a run is kept when its draw is under the share and under the two runs' on each side along the row, so kept runs
    -- stand at least two runs apart and neither spawners nor worms line up along a row
    W[#W + 1] = {type = "noise-expression", name = SC.wrapper,
                 expression = "if((base > 0) * (1 - ore) * (run < " .. num(SC.run_share) ..
                   " * fit) * (run < min(before, after, before2, after2)) > 0, base, min(base, -1))",
                 local_expressions = {
                   base = H2.nests.wrapper,
                   phase = draw("0", "y", SC.seed + 1),
                   index = "floor((x + " .. L .. " * phase) / " .. L .. ")",
                   run = draw("index", "y", SC.seed),
                   before = draw("index - 1", "y", SC.seed),
                   after = draw("index + 1", "y", SC.seed),
                   before2 = draw("index - 2", "y", SC.seed),
                   after2 = draw("index + 2", "y", SC.seed),
                   fit = "if(" .. on .. ", if(" .. H2.enemy_layer .. " > " .. num(H2.nests.outside) .. ", " ..
                     num(SC.footprint_share) .. ", 1), 1)",
                   ore = "if(" .. on .. ", max(" .. table.concat(solid, ", ") .. ") > " .. num(-SC.ore_margin) ..
                     ", 0)",
                 }}
    keys[cfg.keys.enemy] = SC.wrapper
    -- 0.3.1: the nests over the third table's layer, and the scatter off its solid bodies (config.lua hotspots_v3)
    local H3 = cfg.hotspots_v3
    W[#W + 1] = wrapper(H3.nests, live, ebp, "if(" .. on .. ", if(" .. H3.enemy_layer ..
      " > " .. num(H2.nests.outside) .. ", " .. H3.enemy_layer .. ", live_value), live_value)")
    local solid3 = {}
    for _, resource in ipairs(RS.ramped) do
      solid3[#solid3 + 1] = H3.bodies[resource]
    end
    solid3[#solid3 + 1] = H3.bodies["uranium-ore"]
    local L3 = {}
    for k, v in pairs(W[#W - 1].local_expressions) do
      L3[k] = v
    end
    L3.base = H3.nests
    L3.fit = "if(" .. on .. ", if(" .. H3.enemy_layer .. " > " .. num(H2.nests.outside) .. ", " ..
      num(SC.footprint_share) .. ", 1), 1)"
    L3.ore = "if(" .. on .. ", max(" .. table.concat(solid3, ", ") .. ") > " .. num(-SC.ore_margin) .. ", 0)"
    W[#W + 1] = {type = "noise-expression", name = H3.scatter, expression = W[#W - 1].expression,
                 local_expressions = L3}
    keys[cfg.keys.enemy] = H3.scatter
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
      -- 0.3.0: vanilla's function with the footprint gap (resources.natural.fn2); a world made earlier keeps b.name
      if b.name2 then
        -- and the keep of regional scarcity (resources.scarcity); offshore oil keeps every patch
        local keep = b.scarcity and RS.scarcity.names[b.scarcity].keep or cfg.neutral.one
        local scarcity_on = b.scarcity and ("(" .. cfg.keys.scarcity .. " > " .. RS.scarcity.levels.off .. ")") or
          cfg.neutral.zero
        W[#W + 1] = {type = "noise-expression", name = b.name2,
                     expression = (string.gsub(text, NP.vanilla_fn .. "{", NP.fn2 .. "{" .. NP.keep_param .. " = " ..
                       keep .. ", " .. NP.on_param .. " = " .. scarcity_on .. ", "))}
        keys[b.live] = b.name2
      end
    end
  end
end

ridge_wrappers()
local W, keys = {}, {}
natural_patches(W, keys)
ore_wrappers(W, keys)
enemy_wrapper(W, keys)
offshore_wrappers(W, keys)
-- the trees' hook gate (resources.ore_trees): new presets alone switch it on
keys[RS.ore_trees.key] = cfg.neutral.one
keys[RS.ore_trees.open] = RS.ore_trees.open_v2
keys[RS.ore_trees.plants.open] = RS.ore_trees.plants.open_v2
-- 0.3.1: the shares follow the third table's bodies
keys[RS.ore_trees.open] = RS.ore_trees.open_v3
keys[RS.ore_trees.plants.open] = RS.ore_trees.plants.open_v3
if #W > 0 then
  data:extend(W)
end
point_presets(keys)

-- The zones' ground and look (prototypes/zone_look.lua): last, so its copies take every hook's final text.
require("prototypes.zone_look").apply()
