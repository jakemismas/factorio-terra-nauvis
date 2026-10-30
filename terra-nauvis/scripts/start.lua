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
--
-- A Map-type-only world is not an Earth world here (it holds no tn_geo): it gets the Map type notice
-- from guards.lua and no start message. Control code reads save state only (U6).
local cfg = require("prototypes.config")
local cities = require("prototypes.tables.cities")
local guards = require("scripts.guards")

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

function M.on_init()
  local earth = storage.earth
  local surface = game.surfaces["nauvis"]
  if type(earth) ~= "table" or not surface then
    return
  end
  reset_cliffs(earth, surface)
  local geo = guards.geography_of(earth.geo)
  local sp = geo and geo.version.spawn
  if sp then
    local pen = surface.map_gen_settings.property_expression_names or {}
    earth.city = tonumber(pen[sp.city])
    local got = surface.calculate_tile_properties({sp.city_index}, {{x = 0, y = 0}})[sp.city_index]
    local index = got and got[1] and math.floor(got[1] + 1 / 2)
    earth.city_index = index
    local row = index and city_row(geo.map, sp, index)
    if row then
      local m = cfg.maps[geo.map]
      local scale = earth.scale or 0
      local text = message("start", row.name, m.width_px * scale, m.height_px * scale)
      log(text)
      earth.intro = intro(text)
    end
  end
  local rso = script.active_mods["rso-mod"]
  if rso then
    guards.record_warning("rso", {rso})
  end
end

return M
