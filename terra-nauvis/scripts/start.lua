-- Start (ARCHITECTURE.md, "Control stage"; milestone spawn-cities): one-time work when an Earth world is
-- created, after guards.on_init has detected it and built storage.earth.
--
--   - The resolved spawn city, read back with calculate_tile_properties at (0, 0): random folds in
--     float32, so Lua never recomputes it (S7: seed 4294967295 gives a city the integer hash does
--     not). The city table is the one of the geography release the save names in tn_geo, resolved
--     through the release registry (guards.geography_of), never the newest.
--   - D29: the start message, "Spawn city: <name>. World size: <W> x <H> tiles.", logged once and
--     set as freeplay's custom intro (after the intro freeplay would show), when that interface
--     exists.
--   - D32: with RSO active, the RSO warning, stored through guards.record_warning, which logs it
--     once here and sends it to each created player (game.print in on_init reaches no player, S11;
--     decision 25).
--   - The cliff "none" reset (milestone ridges; S5): with the cliff control's size at 0 ("none") the
--     engine places no cliffs at all, whatever the cliff expressions say, and the starting area is
--     generated before on_init. So on an Earth world with ridges on, a size of 0 is written back as
--     reset_size (config.lua ridges) with a whole-table assignment, once, logged in one line: the
--     preview and the starting chunks keep none, and every chunk generated from then on gets its
--     ridges (S5: 330 of 330 cliffs restored; the starting area holds no ridge cell anyway).
--   - D12 (milestone destroyed-europe): with the Destroyed Europe setting on and Alien Biomes not
--     active, the warning that the world has no zone, stored through guards.record_warning like the RSO
--     warning. The preset baked the zone off for lack of Alien Biomes (FEAS-17), so the save
--     cannot tell an asked-for zone from none: this one check reads the startup setting, which on_init
--     reads as the world was created with. With the zone on and the spawn city at random, the save's city
--     number names the map's random pool, which counts as random (0) here.
--
-- A Map-type-only world (it holds no tn_geo) gets the same start: its spawn city, read back the same
-- way through the city fold its elevation entry reads (the per-save names fall back to the
-- prototypes, valued as the preset bakes them), the start message with the map type's world size
-- (its scale read back at (0, 0) too), and the RSO warning; guards.lua adds the Map type notice.
-- The cliff reset and D12 stay Earth-only. A world that is neither gets nothing. Control code reads
-- save state only (U6).
local cfg = require("prototypes.config")
local cities = require("prototypes.city_tables")
local guards = require("scripts.guards")
local start_ore = require("scripts.start_ore")

local M = {}
local MSG = cfg.messages

local function message(key, ...)
  return {MSG.section .. "." .. MSG.keys[key], ...}
end

-- The city row of a resolved index (1 to n) of a spawn record's city setting, or nil.
local function city_row(map_key, sp, index)
  local setting = cfg.settings[sp.city_setting]
  local value = setting and setting.allowed_values[index + 1]
  local tbl = cities[map_key]
  return value and tbl and tbl.cities[value]
end

-- Freeplay's intro with the start message under it, keeping the intro freeplay (or a mod before
-- us) would show. Returns whether the interface took it.
local function intro(text)
  local fp = remote.interfaces["freeplay"]
  if not (fp and fp["set_custom_intro_message"] and fp["get_custom_intro_message"]) then
    return false
  end
  local before = remote.call("freeplay", "get_custom_intro_message")
  if before == nil then
    if script.active_mods["space-age"] then
      before = {"msg-intro-space-age"}
    else
      before = {"msg-intro"}
    end
  end
  remote.call("freeplay", "set_custom_intro_message", {"", before, "\n\n", text})
  return true
end

-- The cliff "none" reset; returns true when it wrote the control back.
local function reset_cliffs(earth, surface)
  local mgs = surface.map_gen_settings
  local pen = mgs.property_expression_names or {}
  local sw = cfg.toggles.ridges
  if pen[sw.preset_key] ~= sw.on then
    return false
  end
  local control = mgs.cliff_settings and mgs.cliff_settings.control
  local controls = mgs.autoplace_controls or {}
  local c = control and controls[control]
  if not (c and c.size == 0) then
    return false
  end
  c.size = cfg.ridges.reset_size
  controls[control] = c
  mgs.autoplace_controls = controls
  surface.map_gen_settings = mgs
  earth.cliff_reset = true
  log(message("cliff_reset", control, cfg.ridges.reset_size))
  return true
end

-- The resolved spawn city of a world whose geography version has a spawn record, read back at
-- (0, 0), and the start message naming it with the world size at `scale` (D29), logged once and set
-- as freeplay's intro. Returns the index and whether the intro took the message.
local function announce(surface, map_key, sp, scale)
  local got = surface.calculate_tile_properties({sp.city_index}, {{x = 0, y = 0}})[sp.city_index]
  local index = got and got[1] and math.floor(got[1] + 1 / 2)
  local row = index and city_row(map_key, sp, index)
  if not row then
    return index, false
  end
  local m = cfg.maps[map_key]
  local text = message("start", row.name, m.width_px * scale, m.height_px * scale)
  log(text)
  return index, intro(text)
end

-- A noise value at (0, 0) of the surface (its own names, else the prototypes' fallbacks).
local function value_at_origin(surface, name)
  local got = surface.calculate_tile_properties({name}, {{x = 0, y = 0}})[name]
  return got and got[1]
end

function M.on_init()
  local surface = game.surfaces["nauvis"]
  if not surface then
    return
  end
  local earth = storage.earth
  if type(earth) == "table" then
    reset_cliffs(earth, surface)
    local geo = guards.geography_of(earth.geo)
    local sp = geo and geo.version.spawn
    if sp then
      local pen = surface.map_gen_settings.property_expression_names or {}
      earth.city = tonumber(pen[sp.city])
      if earth.city == nil and pen[sp.city] ~= nil and pen[sp.city] == (cfg.destroyed.pools or {})[geo.map] then
        earth.city = 0
      end
      earth.city_index, earth.intro = announce(surface, geo.map, sp, earth.scale or 0)
    end
    start_ore.ensure(surface)
  else
    local mt = guards.map_type_geography(surface)
    if not mt then
      return
    end
    local sp = mt.version.spawn
    local state = storage.map_type
    if sp and type(state) == "table" then
      local scale = math.floor((value_at_origin(surface, cfg.keys.scale) or 0) + 1 / 2)
      state.city_index, state.intro = announce(surface, mt.map, sp, scale)
    end
    start_ore.ensure(surface)
  end
  local rso = script.active_mods["rso-mod"]
  if rso then
    guards.record_warning("rso", {rso})
  end
  if type(earth) == "table" then
    local de = cfg.toggles.destroyed_europe
    if settings.startup[cfg.settings[de.setting].name].value and not script.active_mods[de.requires] then
      guards.record_warning("destroyed_no_ab", {})
    end
  end
end

return M
