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
-- geography without touching base worlds (DECISIONS 10:20).
--
-- A Map type pick sets only elevation, so every other per-save name a geography version's entry
-- reads gets a prototype-level fallback valued as that version's preset bakes it under the current
-- startup settings. Surface values beat prototype names (S2): preset worlds and saves keep their own
-- values, and only a Map-type-only world follows the startup settings at every load (Contradictions
-- item 15). A frozen fallback (config.lua) mirrors no setting: its constant body is registered, so no
-- later version moves the worlds that read it.
--
-- A preset is not defined while a mod of its withheld_with list is loaded: from europe-coast to
-- region-layer Alien Biomes' palms read elevation in the Entity program, so beside them a preset
-- would have carried its fine field there (constraint S-3). climate-tiles ships the palm switch
-- (plan reconciliation 9) and empties the lists. Its fallbacks stay defined, so the map's Map type
-- entry still works there. Withholding reached new worlds only: scripts/guards.lua warned a preset
-- world that later loaded beside such a mod, and a save made before the switch keeps its palms on
-- its fine field for life (ARCHITECTURE.md, "Alien Biomes"; DECISIONS 2026-10-29 18:40).
--
-- From climate-tiles each preset also redirects temperature, moisture and aux to the Earth climate,
-- the Alien Biomes variant when alien-biomes is loaded and the fallback otherwise (climate.lua), and
-- points the marsh keys at their bodies and each palm's probability and richness keys at its Earth
-- copy (trees.lua, built from the frozen Alien Biomes table on every load, so the name is never
-- dangling), which reads the palm constant where AB reads elevation and closes the palm leak
-- (ARCHITECTURE.md, constraint S-3; plan reconciliation 9), with or without Alien Biomes, so a
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
-- are the first water_slider constants (D15). A Map-type-only world sets none of them, so it keeps
-- vanilla cliffs and ore (ARCHITECTURE.md, "Map type entries").
--
-- From resources-enemies each preset also bakes the hotspots toggle and, for a version with an
-- offshore stamp, its map's stamp key (the stamp body with hotspots on, the neutral zero body off;
-- also a Map type fallback, since the version's entry reads it), and sets the six base resources'
-- frequency (D20's 0.75; 1 from 0.3.0); data-final-fixes.lua points the ore, richness, enemy and offshore-oil keys at
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
-- design rule 9); otherwise the key is absent, which means off. No expression reads it: scripts/bandfix.lua
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
-- The hotspot amount is a percentage in the setting and a multiplier in the bodies.
local hotspot_amount = tonumber(settings.startup[cfg.settings.hotspot_amount.name].value) / cfg.hotspots.amount_percent
-- The regional scarcity level (resources.scarcity): the setting's value as a number.
local scarcity = cfg.resources.scarcity.levels[settings.startup[cfg.settings.regional_scarcity.name].value]
if not scarcity then
  error("config.lua resources.scarcity.levels has no level for the setting's value")
end

-- The Moscow zone's level (config.lua moscow): the setting's value as the level's index, normal without Alien Biomes
-- (it needs it, as Destroyed Europe does).
-- A picklist setting's level index (levels of {value, index}); `what` names the levels in the error.
local function level_index(levels, setting_key, what)
  local value = settings.startup[cfg.settings[setting_key].name].value
  for _, level in ipairs(levels) do
    if level.value == value then
      return level.index
    end
  end
  error("config.lua " .. what .. " has no level for the setting's value")
end

local moscow = level_index(cfg.moscow.levels, cfg.moscow.setting, "moscow.levels")
if not mods[cfg.moscow.requires] then
  moscow = cfg.moscow.levels[1].index
end

-- The North snow level (climate.north_snow): the setting's value as the level's index.
local north_snow = level_index(cfg.climate.north_snow.levels, cfg.climate.north_snow.setting,
  "climate.north_snow.levels")

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
  local variant = AB and cfg.climate.points.ab or cfg.climate.points.fallback
  local out = {
    temperature = variant.temperature,
    moisture = variant.moisture,
    aux = variant.aux,
    [TL.marsh.water_mud.key] = TL.marsh.water_mud.body2,
    [TL.marsh.water_shallow.key] = TL.marsh.water_shallow.body,
  }
  -- the biome size (config.lua climate.size): the spread's frequency sliders at 1 / factor
  for _, key in ipairs(cfg.climate.size.keys) do
    out[key] = 1 / cfg.climate.size.factor
  end
  -- The palm keys with Alien Biomes loaded or not: a world made without it that gains it later
  -- places its palms from the copies too, never from the fine field (DECISIONS 2026-10-29 18:40).
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
    out[TL.frozen.key] = TL.frozen.body3
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
      out[p.key] = p.next3 or p.next2
    end
    out[cfg.blue.no_blue.key] = cfg.neutral.one
    out[cfg.blue.plants2.key] = cfg.neutral.one
  end
  return out
end

-- The ridges (S5): the two cliff properties point at the shared ridge bodies, which read
-- the map's crest and openings through the keys tn_crest and tn_openings (and the ore
-- clearance its crest band through tn_band), so ridges are the only cliffs on every Terra Nauvis
-- preset, ridges on or off (off: 0 cliffs). config.lua's ridges.preset says which cliff, crest and openings
-- bodies a new world takes; a save keeps the names it was made with. The highland keys name the map's band for
-- rocks and for tile scores and its openings. The three big vanilla rocks name their high bodies, through their
-- restored keys beside Alien Biomes and their probability keys without it; the rock key reaches Alien Biomes'
-- rocks, and without Alien Biomes
-- the ground key the stony tiles' hook (with it their tile keys name the lean, grain_values below).
local function ridge_values(map_key)
  local RN, RP = cfg.ridges.names, cfg.ridges.preset
  local crest, openings, band = RP.crest[map_key], RP.openings[map_key], RN.band[map_key]
  if not (crest and openings and band) then
    return {}
  end
  -- 0.3.0: the band, highland, passes and tile reach a new world takes (ridges.preset, the union of both range
  -- tables)
  local out = {[K.cliff_elevation] = RP.cliff_elevation, [K.cliffiness] = RN.cliffiness, [K.crest] = crest,
               [K.openings] = openings, [K.band] = (RP.band or RN.band)[map_key],
               [K.high] = RP.high[map_key], [K.passes] = RP.passes[map_key],
               [K.high_tile] = RP.high_tile[map_key]}
  for name, n in pairs(cfg.trees.restore.rocks) do
    if n.high then
      out[AB and n.key or ("entity:" .. name .. ":probability")] = n.high
    end
  end
  if AB then
    out[K.rock_lift] = RN.rock_lift_ab
  else
    out[K.ground] = RN.ground
  end
  return out
end

-- The offshore field stamp (APPROVALS 3): a version's map-qualified stamp key
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

-- Destroyed Europe: with Alien Biomes, temperature names the zone's lift (its
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
  -- the random pool skips Destroyed Europe's cities: with the Moscow zone alone at chaos the Europe key is off
  local europe = names[cfg.moscow.europe.key] == nil or names[cfg.moscow.europe.key] == cfg.moscow.europe.on
  if sp and pool and names[sw.preset_key] == sw.on and europe and names[sp.city] == 0 then
    out[sp.city] = pool
  end
  -- The barrier (config.lua destroyed.barrier): a new world with the zone on names the next heat and class in place
  -- of the released ones, which every reader keeps reading by name. A world made before never holds these keys.
  if AB and names[sw.preset_key] == sw.on then
    -- 0.3.0: the next heat and class, and the next zone and outline over the released ones (destroyed.barrier.next,
    -- destroyed.outline.next), which reach and the rest read by name
    out[D.names.heat] = D.barrier.names.heat3
    out[D.chaos.names.class] = D.barrier.names.class3
    -- 0.3.1: the devastation field's heat, class, reach and open mask over the barrier's (destroyed.dev); the dead
    -- trees, the thinning and the exclusion read the reach and the mask by name
    out[D.names.heat] = D.dev.names.heat
    out[D.chaos.names.class] = D.dev.names.class
    out[D.barrier.names.reach] = D.dev.names.reach
    out[D.barrier.names.open] = D.dev.names.open
    out[D.barrier.names.zone] = D.barrier.names.zone3
    out[D.outline.names.present] = D.outline.next.present
    out[D.outline.names.depth] = D.outline.next.depth
    -- Great forests in the zone stand as dead forests: the dead trees' copies read the first body by name.
    out[D.barrier.names.dead] = D.barrier.names.dead2
    -- The exclusion (config.lua destroyed.exclusion): a palm's key names the masked body, the rest read the key.
    out[D.exclusion.key] = cfg.neutral.one
    for _, p in ipairs(D.exclusion.palms) do
      out[p.key] = p.next.body
    end
  end
  return out
end

-- The climate grain (config.lua climate.grain): with Alien Biomes, the listed maps' tile scores read the
-- grain's bodies through the keys, and the temperate bonus and exclusion their grain versions. A map not
-- listed keeps its keys as the plain fields, and its worlds keep their programs.
local function grain_values(map_key)
  local out = {}
  if AB and cfg.climate.grain.maps[map_key] then
    local C, TL = cfg.climate, cfg.tiles
    for field, key in pairs(C.grain.keys) do
      out[key] = C.points.grain[field]
    end
    out[C.grain.veg_key] = C.points.grain.veg
    -- The cold north's plain temperature, which reads the zone's by name, so destroyed_values' pick stands inside it.
    out.temperature = C.points.north
    out[TL.exclude.key] = TL.exclude.body_grain
    local fray = TL.vanilla.next.maps[map_key]
    for _, t in ipairs(TL.vanilla.tiles) do
      out[TL.vanilla.keys[t]] = fray and TL.vanilla.next.grain or TL.vanilla.body_grain
    end
    for _, t in ipairs(TL.vanilla.stony) do
      out[TL.vanilla.keys[t]] = fray and TL.vanilla.next.high or TL.vanilla.body_high
    end
    for i, name in ipairs(TL.noise_share.fields) do
      out[name] = TL.noise_share.fray2.fields[i]
    end
  end
  if AB and cfg.tiles.vanilla.mix.maps[map_key] then
    out[cfg.tiles.vanilla.mix.key] = cfg.tiles.vanilla.mix.amount
  end
  return out
end

-- The six base resources at preset_frequency in the preset (0.3.0: 1, vanilla's; D20 set 0.75), planet entries left
-- neutral (planet values multiply preset values; noise skill gotcha). A control another mod removed
-- is left out.
local function controls()
  local out = {}
  for _, name in ipairs(cfg.resources.controls) do
    if data.raw["autoplace-control"] and data.raw["autoplace-control"][name] then
      out[name] = {frequency = cfg.resources.preset_frequency, size = 1, richness = 1}
    end
  end
  -- the biome size: Alien Biomes' hot and cold frequency, which its temperature spread averages (climate.size)
  for _, name in ipairs(cfg.climate.size.ab_controls) do
    if AB and data.raw["autoplace-control"] and data.raw["autoplace-control"][name] then
      out[name] = {frequency = 1 / cfg.climate.size.factor, size = 1, richness = 1}
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

-- The band-fix key on a map's preset (coast-band-fix): set only when the setting is on, the map is
-- one the setting acts on and the scale is one it serves.
local function bandfix_names(map_key)
  local BF = cfg.bandfix
  local out = {}
  local served = false
  for _, s in ipairs(cfg.scales.exact_coast) do
    served = served or s == scale
  end
  if BF and served and settings.startup[cfg.settings[BF.setting].name].value then
    for _, m in ipairs(BF.maps) do
      if m == map_key then
        out[BF.key] = BF.on
      end
    end
  end
  return out
end

-- Blue corrupted UK (config.lua blue): with the toggle on, each climate field and palm key names its zone
-- body and its under name what it held, and the list hook's keep body names the zone's. It runs after every other
-- step, so it wraps Destroyed Europe's temperature and palms when both are on. A world made before holds none of these.
local function blue_values(names)
  local B, sw = cfg.blue, cfg.toggles.blue_corrupted
  local out = {}
  if AB and names[sw.preset_key] == sw.on then
    for field, c in pairs(B.climate) do
      out[c.under] = names[field]
      out[field] = c.body
    end
    for _, p in ipairs(B.palms) do
      out[p.under] = names[p.key]
      out[p.key] = p.body
    end
    out[cfg.tiles.scan.body] = B.names.keep
    -- 0.3.1: the next outline's depth (blue.outline.next), the United Kingdom alone, as the union with the Moscow zone
    -- (moscow.corrupt.union), each behind its key; the class with the snow join, and the north rim's keep
    out[B.outline.names.depth] = cfg.moscow.corrupt.union
    out[B.names.class] = cfg.moscow.snow.class
    out[cfg.moscow.snow.north_keep] = cfg.moscow.snow.rim_keep
  end
  return out
end

-- The second tables' re-points, which every new world bakes: the second hotspot table's bodies and the second region
-- table's forest and marsh aggregates, each under the first table's name.
local function second_tables()
  local out = {}
  for _, points in ipairs({cfg.hotspots_v2.points, cfg.regions_v2.points, cfg.hotspots_v3.points}) do
    for k, value in pairs(points) do
      out[k] = value
    end
  end
  return out
end

-- 0.3.1: the Moscow zone (config.lua moscow), after the toggles: its level, whether each zone's own outline is on, and
-- the zone's machinery switched on for it: chaos runs Destroyed Europe's, corrupted Blue corrupted's.
local function moscow_values(names)
  local MZ, TG = cfg.moscow, cfg.toggles
  local de, bl = TG.destroyed_europe, TG.blue_corrupted
  names[K.moscow] = moscow
  names[MZ.europe.key] = names[de.preset_key] == de.on and MZ.europe.on or MZ.europe.off
  names[MZ.uk.key] = names[bl.preset_key] == bl.on and MZ.uk.on or MZ.uk.off
  if moscow == MZ.chaos and names[de.preset_key] ~= nil then
    names[de.preset_key] = de.on
  end
  if moscow == MZ.corrupted and names[bl.preset_key] ~= nil then
    names[bl.preset_key] = bl.on
  end
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
  -- The record that serves the save's scale: the version, or its extension past a released version's list. A record's
  -- name lists run in the order of its own scales. An older version a new world never names still reads through here
  -- for the fallback check below: past its list it takes its last set, as its frozen entry does.
  local function position(rec)
    for pos, s in ipairs(rec.scales or cfg.scales.released) do
      if s == scale then
        return pos
      end
    end
  end
  local X = cfg.scale_extensions[map_key]
  local rec = (X and X.geo_id == v.geo_id and not position(v)) and X or v
  local names = {
    [K.elevation] = rec.entry,
    [K.start_mask] = v.start_mask,
    [K.land_coarse] = v.land_coarse,
    [K.map] = cfg.maps[map_key].id,
    [K.scale] = scale,
    [K.hotspot_amount] = hotspot_amount,
    [K.scarcity] = scarcity,
    [K.north_snow] = north_snow,
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
  local ww = rec.waterways
  if ww then
    names[K.on] = cfg.hooks.gate_on
    names[K.fords] = ww.fords[position(rec) or #(rec.scales or cfg.scales.released)]
  end
  for k, value in pairs(toggle_values(map_key)) do
    names[k] = value
  end
  moscow_values(names)
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
  for k, value in pairs(grain_values(map_key)) do
    names[k] = value
  end
  for k, value in pairs(bandfix_names(map_key)) do
    names[k] = value
  end
  for k, value in pairs(blue_values(names)) do
    names[k] = value
  end
  -- The second hotspot table and the second region table: every new world reads them through the first tables'
  -- names.
  for k, value in pairs(second_tables()) do
    names[k] = value
  end
  return names
end

-- The next spawn folds (config.lua spawn_next): a new world whose city number is past the cities the version's
-- released folds serve names the next folds over them, as the city offset under the version's own cx and cy and its
-- map's frame, the spawn lake under the key and the name the entry reads, and the starting-ore bias under its key. Any
-- other world, random included, bakes what 0.3.0 baked. Not part of baked(): a Map type fallback stays the released
-- fold.
local function spawn_next_values(map_key, v, names)
  local nx = cfg.spawn_next and cfg.spawn_next.versions[v.geo_id]
  local sp = v.spawn
  local out = {}
  if nx and sp and type(names[sp.city]) == "number" and names[sp.city] > nx.served then
    local fr = cfg.frames[map_key]
    out[v.cx], out[v.cy] = nx.city_offset[1], nx.city_offset[2]
    if fr then
      out[fr.cx], out[fr.cy] = nx.city_offset[1], nx.city_offset[2]
    end
    out[K.spawn_lake], out[sp.spawn_lake] = nx.spawn_lake, nx.spawn_lake
    out[K.spawn_bias] = nx.spawn_bias
  end
  return out
end

-- The next geo body (config.lua coast.next): past its above_scale a new world names it over the version's own. Not part
-- of baked(): no Map type fallback reads a geo body.
local function geo_next_values(v)
  local nx = cfg.coast.next and cfg.coast.next.versions[v.geo_id]
  if nx and scale > nx.above_scale then
    return {[v.geo] = nx.body}
  end
  return {}
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

-- Copies every pair of `extra` into `names`, extra's value winning.
local function merge_into(names, extra)
  for k, value in pairs(extra) do
    names[k] = value
  end
end

for _, key in ipairs(cfg.preset_order) do
  local p = cfg.presets[key]
  if not withheld(p) then
    local v = geography(p.map)
    local names = baked(p.map, v)
    merge_into(names, spawn_next_values(p.map, v, names))
    merge_into(names, geo_next_values(v))
    presets[p.name] = {
      order = p.order,
      basic_settings = {property_expression_names = names, autoplace_controls = controls()},
    }
  end
end

-- A fallback's body: a number's text, or the name of the expression that folds it.
local function fallback_body(value)
  return type(value) == "number" and num(value) or value
end

-- The map's frame (config.lua frames): its city offset names, which no preset bakes, hold the city fold, as the
-- frame's dropped version baked them.
local function frame_fallbacks(key, fallbacks, seen)
  local fr = cfg.frames[key]
  for i, f in ipairs(fr and fr.fallbacks or {}) do
    local value = fr.city_offset[i]
    if f.name ~= (i == 1 and fr.cx or fr.cy) or seen[f.name] ~= nil then
      error("the frame fallback " .. f.name .. " of " .. key .. " must be the frame's cx then cy, defined once")
    end
    seen[f.name] = value
    fallbacks[#fallbacks + 1] = {type = "noise-expression", name = f.name, expression = fallback_body(value)}
  end
end

-- The fallbacks of every geography version: one prototype per name, valued as every version that
-- reads it bakes it (a number, or the name of the expression that folds it).
local fallbacks, seen = {}, {}
for _, key in ipairs(cfg.map_order) do
  local g = cfg.geography[key]
  for _, v in ipairs(g and g.versions or {}) do
    local names = baked(key, v)
    -- A city past the released folds' cities (config.lua spawn_next) falls back to random on a Map-type-only world,
    -- which reads the released folds through its frozen fallbacks.
    local nx = cfg.spawn_next and cfg.spawn_next.versions[v.geo_id]
    if nx and v.spawn and type(names[v.spawn.city]) == "number" and names[v.spawn.city] > nx.served then
      names[v.spawn.city] = 0
    end
    for _, f in ipairs(v.fallbacks) do
      local value = names[f.name]
      if value == nil then
        error("the Map type fallback " .. f.name .. " of " .. v.entry .. " has no value in its version's preset")
      end
      if seen[f.name] == nil then
        seen[f.name] = value
        fallbacks[#fallbacks + 1] = {type = "noise-expression", name = f.name, expression = fallback_body(value)}
      elseif seen[f.name] ~= value then
        error("the Map type fallback " .. f.name .. " differs between versions or maps: one fallback holds one value")
      end
    end
  end
  frame_fallbacks(key, fallbacks, seen)
end
data:extend(fallbacks)
