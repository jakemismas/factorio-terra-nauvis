-- Guards (ARCHITECTURE.md, "Guards"; milestones europe-coast and spawn-cities): world detection, the
-- missing-name guard, the drift line, the Map type notice, the withheld-preset warning and the D33
-- Nauvis-only surface guard. Control code reads save state only: the Nauvis surface's
-- property_expression_names (U6), storage, script.active_mods and prototypes.named_noise_expression;
-- the drift line also reads the startup settings it compares the save with, and never changes the
-- world. The surface guard is the one writer of another surface's map_gen_settings: it removes the
-- Earth keys a planet surface inherited from the save's defaults (D33, S11).
--
-- An Earth world's Nauvis surface holds tn_geo (it was made from an Earth preset). A Map-type-only
-- world names a version of one of the maps' elevation entries for elevation and holds no tn_geo; its
-- other values come from the prototype fallbacks. Any version counts (config.lua's geography
-- versions): only the newest carries the Map type fields, and a world made from an older one keeps
-- naming it.
-- on_init records such a world in storage, which identifies it from then on. It gets the one-time
-- notice, never the missing-name error, and its drift line says it follows changed settings. Every
-- message names the world's map by its preset's name, which no version changes, never through an
-- entry's [noise-expression] name, which only the newest version keeps. The game raises
-- on_configuration_changed whenever the mod's content changed, the same version included (its
-- checksum differs), so the drift line reports each move once.
--
-- Stored records (ARCHITECTURE.md, "Guards", binding on every milestone): storage.earth.warnings is a
-- list of {key = <a key of config.lua messages.keys>, args = {<LocalisedString>, ...}}, sent to a
-- player as {section .. "." .. messages.keys[key], table.unpack(args)}, and
-- storage.earth.sent[player_index] is the number of those records that player has received.
-- M.record_warning is their only writer (the T16 storage scan keeps every other file off both
-- fields and from replacing storage.earth or storage.map_type, which on_init here builds), and the
-- readers here check every stored record's shape, so a record of another shape, or one whose key a
-- later version lacks, is skipped with a log line and never stops a load or a player's creation. A
-- stored key is never removed from messages.keys (T16 append-only row).
local cfg = require("prototypes.config")

local M = {}
local K = cfg.keys
local MSG = cfg.messages
local RED = {r = 1, g = 0, b = 0}

local function message(key, ...)
  return {MSG.section .. "." .. MSG.keys[key], ...}
end

-- The map key and the geography version of every version of each map's elevation entry, the map
-- key of each map id (the number tn_map), and the preset of each map.
local ENTRY_MAP, ENTRY_VERSION, MAP_OF_ID, PRESET_OF = {}, {}, {}, {}
for _, key in ipairs(cfg.map_order) do
  MAP_OF_ID[cfg.maps[key].id] = key
  local g = cfg.geography[key]
  for _, v in ipairs(g and g.versions or {}) do
    ENTRY_MAP[v.entry] = key
    ENTRY_VERSION[v.entry] = v
  end
end
for _, key in ipairs(cfg.preset_order) do
  local p = cfg.presets[key]
  PRESET_OF[p.map] = p
end

-- A save's geography release (its tn_geo) resolved through the release registry, which names each
-- id's map, to that map's version of that id (ARCHITECTURE.md, "Release versioning policy", rule 4):
-- {map = <map key>, version = <geography version>}. Release-coupled data (the city table) is keyed
-- by tn_geo alone, never by the newest version.
local GEO = {}
for _, r in ipairs(cfg.release_registry) do
  local g = r.geography and cfg.geography[r.map]
  for _, v in ipairs(g and g.versions or {}) do
    if v.geo_id == r.geography then
      GEO[r.geography] = {map = r.map, version = v}
    end
  end
end

function M.geography_of(geo)
  return GEO[tonumber(geo)]
end

-- The spawn record whose per-save city number is `name`, by name (every version that reads it).
local CITY_SPAWN = {}
for _, key in ipairs(cfg.map_order) do
  local g = cfg.geography[key]
  for _, v in ipairs(g and g.versions or {}) do
    if v.spawn then
      CITY_SPAWN[v.spawn.city] = v.spawn
    end
  end
end

-- The toggle a per-save key belongs to (waterways: the canals switch), by its preset key.
local TOGGLE_OF = {}
for _, key in ipairs(cfg.toggle_order) do
  local tg = cfg.toggles[key]
  TOGGLE_OF[tg.preset_key] = tg
end

-- A version's offshore stamp key (resources-enemies), a Map type fallback that follows the hotspots
-- toggle under a name of its own: the map's stamp body when on, the neutral zero when off
-- (presets.lua stamp_values), so its drift line names the hotspots setting.
local function stamp_keys()
  local out = {}
  local hotspots = cfg.toggles.hotspots
  for _, key in ipairs(cfg.map_order) do
    local g = cfg.geography[key]
    for _, v in ipairs(g and g.versions or {}) do
      if v.fields and hotspots and cfg.fields and cfg.fields.names[key] then
        out[v.fields] = {setting = hotspots.setting, on = cfg.fields.names[key], off = cfg.neutral.zero}
      end
    end
  end
  return out
end
local STAMP_OF = stamp_keys()

-- A map's name in every message: its preset's name (presets are named by map, so no version changes
-- it), or the map's display name for a map without a preset.
local function map_label(map_key)
  local p = PRESET_OF[map_key]
  if p then
    return {"map-gen-preset-name." .. p.name}
  end
  local m = cfg.maps[map_key]
  return m and m.display or tostring(map_key)
end

-- The active mods that withhold a map's preset (presets.lua defines no such preset), in config order.
local function withheld_by(map_key)
  local out = {}
  local p = PRESET_OF[map_key]
  for _, m in ipairs(p and p.withheld_with or {}) do
    if script.active_mods[m] then
      out[#out + 1] = m
    end
  end
  return out
end

local function pen_of(surface)
  return surface.map_gen_settings.property_expression_names or {}
end

local function nauvis()
  return game.surfaces["nauvis"]
end

-- "earth", "map_type" (with its map key) or nil. Once on_init has recorded a Map-type-only world,
-- storage identifies it; before that, a defined version of a map's elevation entry does.
function M.kind(surface)
  local pen = pen_of(surface)
  if pen[K.geo] ~= nil then
    return "earth"
  end
  local state = storage.map_type
  if type(state) == "table" and state.map then
    return "map_type", state.map
  end
  local entry = pen[K.elevation]
  local key = entry and ENTRY_MAP[entry]
  if key and prototypes.named_noise_expression[entry] then
    return "map_type", key
  end
  return nil
end

-- The geography of a Map-type-only world: {map = <map key>, version = <the geography version whose
-- entry the world names for elevation>}, or nil for any other world (scripts/start.lua's start
-- messages read it).
function M.map_type_geography(surface)
  local kind, key = M.kind(surface)
  local v = kind == "map_type" and ENTRY_VERSION[pen_of(surface)[K.elevation]]
  if not v then
    return nil
  end
  return {map = key, version = v}
end

-- A noise name's prototype body as text, "" when this version defines none.
local function body_of(name)
  local proto = prototypes.named_noise_expression[name]
  return proto and tostring(proto.expression) or ""
end

-- The fallback values a Map-type-only world reads, from the prototypes (never settings.startup), in
-- config order: {{name = <noise name>, value = <body>}, ...}, for the geography version whose
-- entry the world names. The record keeps the names the world was made with, so a later version's
-- own fallbacks never enter it.
local function fallback_record(entry)
  local out = {}
  local v = ENTRY_VERSION[entry]
  for _, f in ipairs(v and v.fallbacks or {}) do
    out[#out + 1] = {name = f.name, value = body_of(f.name)}
  end
  return out
end

-- A saved city number as a number: a map's random pool, which a preset with the Destroyed Europe zone on
-- bakes for a random spawn city (destroyed-europe), counts as random, 0. The pools are looked up here, not
-- in a main-chunk table, which keeps this file's main chunk inside the linter's complexity limit.
local function city_number(value)
  local n = tonumber(value)
  if n == nil then
    for _, name in pairs((cfg.destroyed or {}).pools or {}) do
      if value == name then
        return 0
      end
    end
  end
  return n
end

local function setting_label(name)
  if name == K.scale then
    return {"mod-setting-name." .. cfg.settings.scale.name}
  end
  local sp = CITY_SPAWN[name]
  if sp then
    return {"mod-setting-name." .. cfg.settings[sp.city_setting].name}
  end
  local tg = TOGGLE_OF[name] or STAMP_OF[name]
  if tg then
    return {"mod-setting-name." .. cfg.settings[tg.setting].name}
  end
  return name
end

-- The dropdown label of a per-save city number (0 random, k the k-th city of the setting).
local function city_label(sp, number)
  local s = cfg.settings[sp.city_setting]
  local value = number and s.allowed_values[number + 1]
  if not value then
    return tostring(number)
  end
  return {"string-mod-setting." .. s.name .. "-" .. value}
end

-- A per-save value as a drift line shows it: a city number as its dropdown label, a toggle's on or
-- off body (a stamp key's stamp or zero body) as on or off.
local function fallback_label(name, value)
  local sp = CITY_SPAWN[name]
  if sp then
    return city_label(sp, city_number(value))
  end
  local tg = TOGGLE_OF[name] or STAMP_OF[name]
  if tg and value == tg.on then
    return message("toggle_on")
  elseif tg and value == tg.off then
    return message("toggle_off")
  end
  return value
end

-- The per-save city number the current spawn-city setting stands for (presets.lua bakes the same).
local function setting_city(sp)
  local s = cfg.settings[sp.city_setting]
  local value = settings.startup[s.name].value
  for i, v in ipairs(s.allowed_values) do
    if v == value then
      return i - 1
    end
  end
  return nil
end

local function say(msg, color)
  log(msg)
  if color then
    game.print(msg, {color = color})
  else
    game.print(msg)
  end
end

-- The Map type notice, built when it is used from this version's text and the mods active then:
-- where the map's preset is withheld it says so instead of pointing to a preset the new-game screen
-- does not list.
local function notice(map_key)
  return message(#withheld_by(map_key) > 0 and "notice_withheld" or "notice", map_label(map_key))
end

-- A stored warning's text, or nil when the record is not {key = <a messages key of this version>,
-- args = <table>}.
local function stored_message(w)
  if type(w) == "table" and type(w.key) == "string" and MSG.keys[w.key] ~= nil and type(w.args) == "table" then
    return message(w.key, table.unpack(w.args))
  end
  return nil
end

-- The one writer of storage.earth.warnings: stores {key, args} for the players created later and
-- says it now (log and a red print). key must be a key of config.lua messages.keys and args a list
-- of LocalisedString parameters (the T16 storage scan checks every call's key statically); a call
-- that breaks that is logged and stores nothing. Returns true when the warning was stored.
function M.record_warning(key, args)
  args = args or {}
  if type(key) ~= "string" or MSG.keys[key] == nil or type(args) ~= "table" then
    log("record_warning refused a warning of key " .. tostring(key) .. ": not a messages key with a list of arguments")
    return false
  end
  if type(storage.earth) ~= "table" then
    storage.earth = {schema = 1}
  end
  local earth = storage.earth
  if type(earth.warnings) ~= "table" then
    earth.warnings = {}
  end
  local w = {key = key, args = args}
  earth.warnings[#earth.warnings + 1] = w
  say(stored_message(w), RED)
  return true
end

-- An Earth world whose map's preset this version withholds beside an active mod (withheld_with):
-- the save keeps naming the map's fine field for elevation and that mod reads elevation in the
-- Entity program (Alien Biomes' palms), so every chunk generated from now on carries the fine field
-- there. Withholding the preset reaches new worlds only and no load can change a save's names, so:
-- one loud warning per withholding mod, once per save, recorded in storage for the players created
-- later and for the palm switch (climate-tiles).
local function warn_withheld(surface, earth)
  local key = MAP_OF_ID[tonumber(pen_of(surface)[K.map])]
  if not key then
    return
  end
  local seen = type(earth.withheld_beside) == "table" and earth.withheld_beside or {}
  earth.withheld_beside = seen
  local fresh = {}
  for _, m in ipairs(withheld_by(key)) do
    if not seen[m] then
      seen[m] = game.tick
      fresh[#fresh + 1] = m
    end
  end
  if #fresh > 0 then
    M.record_warning("withheld_beside", {map_label(key), table.concat(fresh, ", ")})
  end
end

function M.on_init()
  local surface = nauvis()
  if not surface then
    return
  end
  local kind, map_key = M.kind(surface)
  local pen = pen_of(surface)
  if kind == "earth" then
    storage.earth = {schema = 1, map = tonumber(pen[K.map]), scale = tonumber(pen[K.scale]),
                     geo = tonumber(pen[K.geo]), warnings = {}, sent = {}}
    -- a world made beside a withholding mod from a full map-gen-settings file (the server route)
    warn_withheld(surface, storage.earth)
  elseif kind == "map_type" then
    -- game.print in on_init reaches no player (S11): log the notice once here and send it to each
    -- player as that player is created. The record holds the fallback values the world was made with.
    storage.map_type = {schema = 1, map = map_key, fallbacks = fallback_record(pen[K.elevation]), sent = {}}
    log(notice(map_key))
  end
end

-- Every Earth key whose value is a name must name a defined noise expression: a dropped name
-- silently gives new chunks vanilla terrain (COUNCIL graft). Returns the number of misses.
function M.missing_names(surface)
  local pen = pen_of(surface)
  local found = 0
  for _, key in ipairs(cfg.preset_keys) do
    local value = pen[key]
    if type(value) == "string" and value ~= "" and not tonumber(value)
        and not prototypes.named_noise_expression[value] then
      say(message("missing_name", key, value), RED)
      found = found + 1
    end
  end
  return found
end

-- An Earth world keeps its scale, spawn city and toggles: one info line per value the startup
-- settings now set differently. The city is the one of the world's own geography release (its
-- tn_geo); a toggle is checked only where the world's preset baked it.
local function drift_earth(surface)
  local pen = pen_of(surface)
  local saved = tonumber(pen[K.scale])
  local now = tonumber(settings.startup[cfg.settings.scale.name].value)
  if saved and now and saved ~= now then
    say(message("drift_scale", saved, now))
  end
  local geo = M.geography_of(pen[K.geo])
  local sp = geo and geo.version.spawn
  if sp then
    local saved_city = city_number(pen[sp.city])
    local now_city = setting_city(sp)
    if saved_city and now_city and saved_city ~= now_city then
      say(message("drift_city", city_label(sp, saved_city), city_label(sp, now_city)))
    end
  end
  for _, key in ipairs(cfg.toggle_order) do
    local tg = cfg.toggles[key]
    local was = pen[tg.preset_key]
    local on = settings.startup[cfg.settings[tg.setting].name].value
    -- a toggle that requires a mod is off without it, as the preset baked it (destroyed-europe)
    if tg.requires and not script.active_mods[tg.requires] then
      on = false
    end
    local want = on and tg.on or tg.off
    if was ~= nil and was ~= want then
      say(message(tg.map_type_follows and "drift_toggle" or "drift_toggle_new", setting_label(tg.preset_key),
        fallback_label(tg.preset_key, was), fallback_label(tg.preset_key, want)))
    end
  end
end

-- A Map-type-only world follows the startup settings through its fallbacks: one line per recorded
-- fallback whose prototype body moved since the world last recorded it, on every configuration
-- change (a mod update as well as a startup-setting change); then the record follows too, so each
-- change is reported once. A setting's fallback after a setting change names the setting; any
-- other move came with the mod itself, which the frozen fallbacks forbid a real build (the line is a
-- tripwire, ARCHITECTURE.md "Map type entries").
local function drift_map_type(state, settings_changed)
  local recorded = type(state.fallbacks) == "table" and state.fallbacks or {}
  for i, f in ipairs(recorded) do
    if type(f) ~= "table" or type(f.name) ~= "string" or type(f.value) ~= "string" then
      log("skipped recorded fallback " .. i .. ": not a {name, value} record")
    else
      local now = body_of(f.name)
      if now ~= f.value then
        local label = setting_label(f.name)
        local key = (settings_changed and label ~= f.name) and "drift_follows" or "drift_update"
        say(message(key, map_label(state.map), label, fallback_label(f.name, now), fallback_label(f.name, f.value)))
        f.value = now
      end
    end
  end
end

-- D33's strip rule (ARCHITECTURE.md, "D33 surface guard"): a surface other than Nauvis drops a listed
-- key only when the save's default value names an Earth body or the key is an Earth per-save key. From
-- ridges the listed keys include vanilla properties (cliff_elevation, cliffiness, the ore
-- probabilities, beside group 0's water slider readers), and vanilla's Lakes and Island presets set
-- cliffiness and cliff_elevation to the very values Space Age's planets set themselves, so comparing
-- the value alone would blank those planets' own keys on a world that is no Earth map. The guard's
-- comparison with the default value stays; this predicate gates it (the static d33_guard row requires
-- the call).
function M.earth_valued(key, value)
  local prefix = cfg.identity.noise_prefix
  local function earth(s)
    return type(s) == "string" and s:sub(1, #prefix) == prefix
  end
  return earth(key) or earth(value)
end

-- D33 (ARCHITECTURE.md, "D33 surface guard"; S11): a surface other than Nauvis inherits the save's
-- default property_expression_names unless its planet sets a key itself, so it drops (writes "") each
-- Earth preset key whose value equals the save's own default, with a whole-table assignment. A planet
-- that sets a key keeps it, because its value differs. Only an Earth or Map-type-only world is
-- touched, and only a default that is Terra Nauvis's: every preset key of an Earth world's defaults
-- (they hold tn_geo, so an Earth preset or file wrote them), else a key of this mod's own or a
-- default naming one of its noise expressions. Several preset keys are vanilla's (elevation,
-- distance, the lake mask, the water slider), and a vanilla preset sets some of them (Island and
-- Lakes set elevation), so a non-Earth save is never touched and a Map-type-only world keeps every
-- vanilla value. Under Space Age this keeps every other planet as it generates without Terra
-- Nauvis. Returns the number of keys removed.
function M.surface_guard(surface)
  if not (surface and surface.valid) or surface.name == "nauvis" then
    return 0
  end
  local home = nauvis()
  if not (home and M.kind(home)) then
    return 0
  end
  local default = game.default_map_gen_settings.property_expression_names or {}
  local earth_defaults = default[K.geo] ~= nil
  local mgs = surface.map_gen_settings
  local pen = mgs.property_expression_names or {}
  local removed = 0
  for _, key in ipairs(cfg.preset_keys) do
    local v, d = pen[key], default[key]
    if v ~= nil and v ~= "" and d ~= nil and tostring(v) == tostring(d)
        and (earth_defaults or M.earth_valued(key, d)) then
      pen[key] = ""
      removed = removed + 1
    end
  end
  if removed > 0 then
    mgs.property_expression_names = pen
    surface.map_gen_settings = mgs
    log({"", cfg.identity.title, ": the Nauvis-only guard removed ", removed, " keys from surface ", surface.name})
  end
  return removed
end

-- The guard over every surface: surfaces created inside an on_init never raise on_surface_created
-- (S11), so on_init and on_configuration_changed sweep them all.
function M.sweep_surfaces()
  for _, surface in pairs(game.surfaces) do
    M.surface_guard(surface)
  end
end

function M.on_surface_created(event)
  M.surface_guard(game.get_surface(event.surface_index))
end

function M.on_configuration_changed(data)
  local surface = nauvis()
  if not surface then
    return
  end
  local kind = M.kind(surface)
  if kind == "earth" then
    M.missing_names(surface)
    if data.mod_startup_settings_changed then
      drift_earth(surface)
    end
    if type(storage.earth) ~= "table" then
      storage.earth = {schema = 1}
    end
    warn_withheld(surface, storage.earth)
  elseif kind == "map_type" and type(storage.map_type) == "table" then
    drift_map_type(storage.map_type, data.mod_startup_settings_changed)
  end
end

-- Each created player gets the Map type notice once on a Map-type-only world, and on an Earth world
-- every stored warning it has not had yet (S11: game.print in on_init reaches no player). Every
-- stored field is checked before use (the stored-records contract above): a record of another
-- shape is skipped with a log line, and a count that is not a number reads as none sent.
function M.on_player_created(event)
  local player = game.get_player(event.player_index)
  if not player then
    return
  end
  local state = storage.map_type
  if type(state) == "table" and state.map then
    if type(state.sent) ~= "table" then
      state.sent = {}
    end
    if not state.sent[event.player_index] then
      player.print(notice(state.map))
      state.sent[event.player_index] = true
    end
  end
  local earth = storage.earth
  if type(earth) == "table" and type(earth.warnings) == "table" then
    if type(earth.sent) ~= "table" then
      earth.sent = {}
    end
    local had = earth.sent[event.player_index]
    if type(had) ~= "number" then
      had = 0
    end
    for i = had + 1, #earth.warnings do
      local msg = stored_message(earth.warnings[i])
      if msg then
        player.print(msg, {color = RED})
      else
        log("skipped stored warning " .. i .. ": not a {key, args} record with a messages key of this version")
      end
    end
    earth.sent[event.player_index] = #earth.warnings
  end
end

return M
