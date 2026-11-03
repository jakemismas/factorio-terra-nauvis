-- The spawn-city tables of every map (ARCHITECTURE.md, "Module map": prototypes/tables/), merged into
-- one table keyed by map key, as spawn.lua and scripts/start.lua read them.
--
-- Each table file under prototypes/tables/ is pure data returning {<map key> = {version, cities}}.
-- cities.lua holds Europe's (spawn-cities); each map added later has a file of its own, so a landed
-- table file, and the spawn bearings generated from it (whose header records its sha256), never
-- change when a map is added. A map's next table version is a file of its own (0.3.1: cities_atlantic_v2.lua),
-- which keeps every earlier row and appends; the merge takes each map's newest version, and two files holding one
-- map at the same version fail at load.
local FILES = {
  require("prototypes.tables.cities"),
  require("prototypes.tables.cities_atlantic"),
  require("prototypes.tables.cities_olde_world"),
  require("prototypes.tables.cities_atlantic_v2"),
}

local out = {}
for _, tables in ipairs(FILES) do
  for key, tbl in pairs(tables) do
    local have = out[key]
    if have ~= nil and have.version == tbl.version then
      error("two spawn-city table files hold the map " .. tostring(key) .. " at version " .. tostring(tbl.version))
    end
    if have == nil or tbl.version > have.version then
      out[key] = tbl
    end
  end
end
return out
