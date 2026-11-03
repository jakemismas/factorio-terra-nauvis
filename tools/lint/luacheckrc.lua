-- luacheck 1.2.0 configuration for the Lua files of the Terra Nauvis zip (T16). tools/earth_test.py
-- passes it with --config and lists the files explicitly; paths below are relative to the repo root.
--
-- Globals per stage follow factorio-mod-dev's stage table: the settings stage has data, mods,
-- feature_flags and helpers; the data stage adds settings and util; the control stage has script,
-- game, settings, prototypes, helpers, storage, rendering, remote, commands, rcon and defines.
-- config.lua is pure data and may read no global at all.

std = "lua52"
max_line_length = 120
max_cyclomatic_complexity = 20

local common = {"log", "serpent", "table_size", "localised_print"}

local function with(list)
  local out = {}
  for _, v in ipairs(common) do out[#out + 1] = v end
  for _, v in ipairs(list) do out[#out + 1] = v end
  return out
end

local settings_stage = {globals = {"data"}, read_globals = with({"mods", "feature_flags", "helpers"})}
local data_stage = {globals = {"data"}, read_globals = with({"mods", "feature_flags", "helpers", "settings", "util",
  "defines"})}
local control_stage = {globals = {"storage"}, read_globals = with({"script", "game", "settings", "prototypes",
  "helpers", "rendering", "remote", "commands", "rcon", "defines"})}

files["terra-nauvis/settings.lua"] = settings_stage
files["terra-nauvis/settings-updates.lua"] = settings_stage
files["terra-nauvis/settings-final-fixes.lua"] = settings_stage
files["terra-nauvis/data.lua"] = data_stage
files["terra-nauvis/data-updates.lua"] = data_stage
files["terra-nauvis/data-final-fixes.lua"] = data_stage
files["terra-nauvis/prototypes/presets.lua"] = data_stage
files["terra-nauvis/prototypes/zone_exclusion.lua"] = data_stage
files["terra-nauvis/prototypes/zone_look.lua"] = data_stage
files["terra-nauvis/prototypes/expressions/**/*.lua"] = data_stage
files["terra-nauvis/prototypes/generated/**/*.lua"] = data_stage
-- Pure data: no global at all, not even Lua's standard library.
files["terra-nauvis/prototypes/config.lua"] = {std = "none"}
files["terra-nauvis/prototypes/tables/**/*.lua"] = {std = "none"}
files["terra-nauvis/control.lua"] = control_stage
files["terra-nauvis/scripts/**/*.lua"] = control_stage
files["terra-nauvis/migrations/**/*.lua"] = control_stage
