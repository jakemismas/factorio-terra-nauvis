-- The spawn-city tables of every map (ARCHITECTURE.md, "Module map": prototypes/tables/), merged into
-- one table keyed by map key, as spawn.lua and scripts/start.lua read them.
--
-- Each table file under prototypes/tables/ is pure data returning {<map key> = {version, cities}}.
-- cities.lua holds Europe's (spawn-cities); each map added later has a file of its own, so a landed
-- table file, and the spawn bearings generated from it (whose header records its sha256), never
-- change when a map is added. A map held by two files fails at load.
local FILES = {
  require("prototypes.tables.cities"),
  require("prototypes.tables.cities_atlantic"),
  require("prototypes.tables.cities_olde_world"),
}

local out = {}
for _, tables in ipairs(FILES) do
  for key, tbl in pairs(tables) do
    if out[key] ~= nil then
      error("two spawn-city table files hold the map " .. tostring(key))
    end
    out[key] = tbl
  end
end
return out
