-- Map-gen presets and the Map type fallbacks (ARCHITECTURE.md, "Preset redirects" and "Map type
-- entries"), built from config.lua.
--
-- Each Earth preset bakes every map-shaping value into basic_settings.property_expression_names, so
-- a save keeps its map for life whatever the startup settings say later (S2): its map's elevation
-- entry, the start mask on the coarse land field, the coarse field itself, the numbers tn_map,
-- tn_scale, tn_geo and the map's city offset, and vanilla's three readers of the water slider at
-- their default-slider values, so the slider moves nothing on the preset (D15; config.lua's
-- water_slider). From spawn-cities a version with a spawn record also bakes the distance redirect,
-- the map's city number and the spawn lake and bias keys, and its city offset names name the city
-- fold. From waterways a version that composes the waterways also sets the hook gate on and points
-- the ford key at its map's ford set for the save's scale, and every version of a map a toggle lists
-- bakes the toggle from its setting (the canals switch names a neutral body). A Map-type-only world
-- keeps the gate's prototype (off), so it has no fords (ARCHITECTURE.md, "Map type entries"). A
-- preset's geography version (its elevation entry, start mask, coarse field, city offset and tn_geo)
-- is chosen in one place, geography() below, so climate-tiles can give Alien Biomes worlds a cheaper
-- geography without touching base worlds.
--
-- A Map type pick sets only elevation, so every other per-save name a geography version's entry
-- reads gets a prototype-level fallback valued as that version's preset bakes it under the current
-- startup settings: every version's, the older ones included, since their entries stay defined for
-- the worlds that name them. Surface values beat prototype names (S2): preset worlds and saves keep
-- their own values, and only a Map-type-only world follows the startup settings at every load
-- (Contradictions item 15). A frozen fallback (config.lua) mirrors no setting: its constant body is
-- registered, so no later version moves the worlds that read it.
--
-- A preset is not defined while a mod of its withheld_with list is loaded: from europe-coast to
-- region-layer Alien Biomes' palms read elevation in the Entity program, so beside them a preset
-- would have carried its fine field there (design constraint 3). climate-tiles ships the palm switch
-- (design note 9) and empties the lists. Its fallbacks stay defined, so the map's Map type
-- entry still works there. Withholding reached new worlds only: scripts/guards.lua warned a preset
-- world that later loaded beside such a mod, and a save made before the switch keeps its palms on
-- its fine field for life (ARCHITECTURE.md, "Alien Biomes"; design notes 2026-10-29 18:40).
--
-- From climate-tiles each preset also redirects temperature, moisture and aux to the Earth climate,
-- the Alien Biomes variant when alien-biomes is loaded and the fallback otherwise (climate.lua), and
-- points the marsh keys at their bodies and each palm's probability and richness keys at its Earth
-- copy (trees.lua, built from the frozen Alien Biomes table on every load, so the name is never
-- dangling), which reads the palm constant where AB reads elevation and closes the palm leak
-- (ARCHITECTURE.md, design constraint S-3; design note 9), with or without Alien Biomes, so a
-- world that gains it later meets the switch too; with Alien Biomes it also points the 19 vanilla
-- tile keys at the shared bonus body and the exclusion key at its body, and data-final-fixes.lua
-- points a palm's keys at the neutral body when the installed palm differs from the table. Every
-- other AB key exists only with AB loaded (ARCHITECTURE.md, "Module map"); without AB the marsh grass
-- key gives grass-1 between the marsh pools instead (APPROVALS 8).
--
-- From trees-forests each preset also bakes the great-forests gate from its setting (a toggle) and
-- points the multiplier key at the region layer's multiplier; with Alien Biomes it points the restored
-- vanilla trees', rocks', decals' and decoratives' keys at their bodies and each palm's probability key at
-- its second version (trees.lua).
--
-- From ridges each preset also bakes the ridges toggle from its setting and points the cliff properties
-- at the ridge bodies with the map's crest and openings keys; data-final-fixes.lua adds the ore keys,
-- whose wrappers read other mods' final ore autoplace. The water frequency slider's two vanilla readers
-- are group 0's water_slider constants (D15). A Map-type-only world sets none of them, so it keeps
-- vanilla cliffs and ore (ARCHITECTURE.md, "Map type entries").
--
-- From resources-enemies each preset also bakes the hotspots toggle and, for a version with an
-- offshore stamp, its map's stamp key (the stamp body with hotspots on, the neutral zero body off;
-- also a Map type fallback, since the version's entry reads it), and sets frequency 0.75 for the six
-- base resources (D20); data-final-fixes.lua points the ore, richness, enemy and offshore-oil keys at
-- its wrappers.
--
-- From edge-and-lakes each preset also bakes the inland lakes toggle (default off; toggle_values), which
-- a version with a lakes field reads its inland lakes through, and the toggle's key is that version's
-- Map type fallback, so a Map-type-only world follows the setting.
--
-- From destroyed-europe each preset also bakes the zone toggle, on only when its setting is on and
-- Alien Biomes is loaded (the toggle's `requires`; FEAS-17); with Alien Biomes it points temperature at
-- the Alien Biomes temperature's next version, whose switch folds it to climate-tiles' first when the
-- toggle is off; and with the toggle on and the spawn city at random a version with a spawn record
-- bakes the map's random pool as the city number, so random never lands on a city the zone covers
-- (APPROVALS 10).
--
-- From coast-band-fix a preset also bakes the band-fix key, a name switch to tn_one, when the startup
-- setting Exact coastlines is on and its map passed all four flip checks (config.lua bandfix.maps,
-- decision 9); otherwise the key is absent, which means off. No expression reads it: scripts/bandfix.lua
-- reads it from the save's own surface, so a world keeps it for life.
local cfg = require("prototypes.config")

local K = cfg.keys
local AB = mods["alien-biomes"] ~= nil

local function num(v)
  return string.format(cfg.number_format, v)
end

-- The geography version a map's preset names: its newest.
local function geography(map_key)
  local g = cfg.geography[map_key]
  if not g or not g.versions or #g.versions == 0 then
    error("config.lua has no geography version for the preset map " .. map_key)
  end
  return g.versions[#g.versions]
end

local scale = tonumber(settings.startup[cfg.settings.scale.name].value)

-- The per-save city number a spawn-city setting stands for: its value's position in the setting's
-- allowed values, less one, so random (the first) is 0 and the first city 1.
local function city_number(setting_key)
  local s = cfg.settings[setting_key]
  local value = settings.startup[s.name].value
  for i, v in ipairs(s.allowed_values) do
    if v == value then
      return i - 1
    end
  end
  error("the setting " .. s.name .. " holds " .. tostring(value) .. ", which config.lua does not list")
end

-- The climate and tile keys every Earth preset sets (climate-tiles), the same on every map and version.
local function climate_names()
  local TL = cfg.tiles
  local variant = AB and cfg.climate.names.ab or cfg.climate.names.fallback
  local out = {
    temperature = variant.temperature,
    moisture = variant.moisture,
    aux = variant.aux,
    [TL.marsh.water_mud.key] = TL.marsh.water_mud.body,
    [TL.marsh.water_shallow.key] = TL.marsh.water_shallow.body,
  }
  -- The palm keys with Alien Biomes loaded or not: a world made without it that gains it later
  -- places its palms from the copies too, never from the fine field.
  for _, c in ipairs(TL.palm.copies) do
    out[c.key] = c.body
  end
  if AB then
    for _, t in ipairs(TL.vanilla.tiles) do
      out[TL.vanilla.keys[t]] = TL.vanilla.body
    end
    out[TL.exclude.key] = TL.exclude.body
  else
    out[TL.marsh.grass.key] = TL.marsh.grass.body
  end
  return out
end

-- The tree keys every Earth preset sets (trees-forests), the same on every map: the great-forests
-- multiplier key names the region layer's multiplier (the gate is a toggle); with Alien Biomes each
-- restored vanilla tree's, rock's, decal's and decorative's key names its Earth body, and each palm's
-- probability key its second version, the boost around climate-tiles' copy.
local function tree_names()
  local TR = cfg.trees
  local R = TR.restore
  local out = {[TR.boost.key] = cfg.regions.names.tree_mult, [TR.boost.lift] = TR.boost.lift_body}
  if AB then
    for _, n in pairs(R.trees) do
      out[n.p] = n.body
      out[n.r] = R.richness
    end
    for _, n in pairs(R.rocks) do
      out[n.key] = n.body
    end
    for _, key in pairs(R.decoratives) do
      out[key] = R.deco_body
    end
    for _, p in ipairs(TR.palm) do
      out[p.key] = p.body
    end
  end
  return out
end

-- The ridges (milestone ridges; S5): the two cliff properties point at the shared ridge bodies, which read
-- the map's crest distance and openings through the keys tn_crest and tn_openings (and the ore
-- clearance its crest band through tn_band), so ridges are the only cliffs on every Terra Nauvis
-- preset, ridges on or off (off: 0 cliffs).
local function ridge_values(map_key)
  local RN = cfg.ridges.names
  local crest, openings, band = RN.crest[map_key], RN.openings[map_key], RN.band[map_key]
  if not (crest and openings and band) then
    return {}
  end
  return {[K.cliff_elevation] = RN.cliff_elevation, [K.cliffiness] = RN.cliffiness, [K.crest] = crest,
          [K.openings] = openings, [K.band] = band}
end

-- The offshore field stamp (milestone resources-enemies; APPROVALS 3): a version's map-qualified stamp key
-- names the map's stamp body when the hotspots setting is on and the neutral zero body when it is off
-- (min(e, 0) leaves water unchanged), so the stamp follows the hotspots toggle.
local function stamp_values(map_key, v)
  local key, body = v.fields, cfg.fields.names[map_key]
  if not (key and body) then
    return {}
  end
  local on = settings.startup[cfg.settings[cfg.toggles.hotspots.setting].name].value
  return {[key] = on and body or cfg.neutral.zero}
end

-- Destroyed Europe (milestone destroyed-europe): with Alien Biomes, temperature names the zone's lift (its
-- switch, the toggle baked above, folds it to climate-tiles' first temperature when off); with the toggle
-- on and the map's spawn city at random, a version's city number (its spawn record's) names the map's random
-- pool, which skips the cities the zone covers. `names` is the version's table so far.
local function destroyed_values(map_key, v, names)
  local D, sw = cfg.destroyed, cfg.toggles.destroyed_europe
  local out = {}
  if AB then
    out.temperature = D.names.temperature
  end
  local pool, sp = D.pools[map_key], v.spawn
  if sp and pool and names[sw.preset_key] == sw.on and names[sp.city] == 0 then
    out[sp.city] = pool
  end
  return out
end

-- The six base resources a little sparser (D20): frequency 0.75 in the preset, planet entries left
-- neutral (planet values multiply preset values; known noise gotcha). A control another mod removed
-- is left out.
local function controls()
  local out = {}
  for _, name in ipairs(cfg.resources.controls) do
    if data.raw["autoplace-control"] and data.raw["autoplace-control"][name] then
      out[name] = {frequency = cfg.resources.frequency, size = 1, richness = 1}
    end
  end
  return out
end

-- Each toggle's per-save value on a map: its on or off body by the toggle's startup setting, for the
-- maps the toggle lists.
local function toggle_values(map_key)
  local out = {}
  for _, key in ipairs(cfg.toggle_order) do
    local t = cfg.toggles[key]
    for _, m in ipairs(t.maps) do
      if m == map_key then
        local value = settings.startup[cfg.settings[t.setting].name].value
        -- a toggle that requires a mod bakes off without it, whatever the setting says (destroyed-europe)
        if t.requires and not mods[t.requires] then
          value = false
        end
        out[t.preset_key] = value and t.on or t.off
      end
    end
  end
  return out
end

-- The band-fix key on a map's preset (coast-band-fix): set only when the setting is on and the map is
-- one the setting acts on.
local function bandfix_names(map_key)
  local BF = cfg.bandfix
  local out = {}
  if BF and settings.startup[cfg.settings[BF.setting].name].value then
    for _, m in ipairs(BF.maps) do
      if m == map_key then
        out[BF.key] = BF.on
      end
    end
  end
  return out
end

-- A spawn version's layer chain offset names: where the map's layer chain version (config.lua
-- layer_chain_geo, the frame the region layer, the climate and the layers after them read) holds
-- another city offset (Atlantic's and Old World's, registered at 0 before their spawn versions), its
-- offset names point at this version's city fold, so those layers read the spawn's ground. Europe's
-- layer chain version already reads the fold, so it bakes nothing here.
local function layer_chain_names(map_key, v)
  local out = {}
  local id = (cfg.layer_chain_geo or {})[map_key]
  if not (v.spawn and id) then
    return out
  end
  for _, lv in ipairs(cfg.geography[map_key].versions) do
    if lv.geo_id == id and lv.cx ~= v.cx and
        (lv.city_offset[1] ~= v.city_offset[1] or lv.city_offset[2] ~= v.city_offset[2]) then
      out[lv.cx] = v.city_offset[1]
      out[lv.cy] = v.city_offset[2]
    end
  end
  return out
end

-- The property_expression_names one geography version's preset bakes under the current startup
-- settings (tools/tnconfig.py baked_names mirrors it). A version with a spawn record also bakes the
-- distance redirect (vanilla's starting ore and enemy-free start follow the spawn through it, S7),
-- the map's city number and the spawn lake and bias the start mask reads. From climate-tiles every
-- version also bakes the climate and tile keys (climate_names), from trees-forests the tree keys
-- after them (tree_names: a palm's probability key names its second version), and from ridges the
-- cliff properties and the map's ridge keys (ridge_values), from resources-enemies a version with
-- an offshore stamp its stamp key (stamp_values), from destroyed-europe the Alien Biomes temperature's
-- next version and, with the zone on and the city at random, the map's random pool (destroyed_values),
-- and from coast-band-fix the band-fix key where the setting acts on the map (bandfix_names).
local function baked(map_key, v)
  local names = {
    [K.elevation] = v.entry,
    [K.start_mask] = v.start_mask,
    [K.land_coarse] = v.land_coarse,
    [K.map] = cfg.maps[map_key].id,
    [K.scale] = scale,
    [K.geo] = v.geo_id,
    [v.cx] = v.city_offset[1],
    [v.cy] = v.city_offset[2],
  }
  for _, w in ipairs(cfg.water_slider) do
    names[w.key] = w.value
  end
  local sp = v.spawn
  if sp then
    names[K.distance] = sp.distance
    names[sp.city] = city_number(sp.city_setting)
    names[K.spawn_lake] = sp.spawn_lake
    names[K.spawn_bias] = sp.spawn_bias
    for k, value in pairs(layer_chain_names(map_key, v)) do
      names[k] = value
    end
  end
  local ww = v.waterways
  if ww then
    names[K.on] = cfg.hooks.gate_on
    names[K.fords] = ww.fords[scale]
  end
  for k, value in pairs(toggle_values(map_key)) do
    names[k] = value
  end
  for k, value in pairs(climate_names()) do
    names[k] = value
  end
  for k, value in pairs(tree_names()) do
    names[k] = value
  end
  for k, value in pairs(ridge_values(map_key)) do
    names[k] = value
  end
  for k, value in pairs(stamp_values(map_key, v)) do
    names[k] = value
  end
  for k, value in pairs(destroyed_values(map_key, v, names)) do
    names[k] = value
  end
  for k, value in pairs(bandfix_names(map_key)) do
    names[k] = value
  end
  return names
end

local function withheld(p)
  for _, m in ipairs(p.withheld_with or {}) do
    if mods[m] then
      return true
    end
  end
  return false
end

local presets = data.raw["map-gen-presets"]["default"]

for _, key in ipairs(cfg.preset_order) do
  local p = cfg.presets[key]
  if not withheld(p) then
    presets[p.name] = {
      order = p.order,
      basic_settings = {property_expression_names = baked(p.map, geography(p.map)), autoplace_controls = controls()},
    }
  end
end

-- The fallbacks of every geography version: one prototype per name, valued as every version that
-- reads it bakes it (a number, or the name of the expression that folds it).
local fallbacks, seen = {}, {}
for _, key in ipairs(cfg.map_order) do
  local g = cfg.geography[key]
  for _, v in ipairs(g and g.versions or {}) do
    local names = baked(key, v)
    for _, f in ipairs(v.fallbacks) do
      local value = names[f.name]
      if value == nil then
        error("the Map type fallback " .. f.name .. " of " .. v.entry .. " has no value in its version's preset")
      end
      if seen[f.name] == nil then
        seen[f.name] = value
        local body = type(value) == "number" and num(value) or value
        fallbacks[#fallbacks + 1] = {type = "noise-expression", name = f.name, expression = body}
      elseif seen[f.name] ~= value then
        error("the Map type fallback " .. f.name .. " differs between versions or maps: one fallback holds one value")
      end
    end
  end
end
data:extend(fallbacks)
