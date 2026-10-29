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
-- fold. A preset's geography version (its elevation entry, start mask, coarse field, city offset
-- and tn_geo) is chosen in one place, geography() below, so climate-tiles can give Alien Biomes
-- worlds a cheaper geography without touching base worlds.
--
-- A Map type pick sets only elevation, so every other per-save name a geography version's entry
-- reads gets a prototype-level fallback valued as that version's preset bakes it under the current
-- startup settings: every version's, the older ones included, since their entries stay defined for
-- the worlds that name them. Surface values beat prototype names (S2): preset worlds and saves keep
-- their own values, and only a Map-type-only world follows the startup settings at every load
-- (Contradictions item 15). A frozen fallback (config.lua) mirrors no setting: its constant body is
-- registered, so no later version moves the worlds that read it.
--
-- A preset is not defined while a mod of its withheld_with list is loaded: Alien Biomes' palms read
-- elevation in the Entity program, so beside them a preset would carry its fine field there (design
-- constraint 3) until climate-tiles ships the palm switch (design note 9). Its fallbacks
-- stay defined, so the map's Map type entry still works there. Withholding reaches new worlds only:
-- scripts/guards.lua warns a preset world that later loads beside such a mod.
local cfg = require("prototypes.config")

local K = cfg.keys

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

-- The property_expression_names one geography version's preset bakes under the current startup
-- settings (tools/tnconfig.py baked_names mirrors it). A version with a spawn record also bakes the
-- distance redirect (vanilla's starting ore and enemy-free start follow the spawn through it, S7),
-- the map's city number and the spawn lake and bias the start mask reads.
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
      basic_settings = {property_expression_names = baked(p.map, geography(p.map))},
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
