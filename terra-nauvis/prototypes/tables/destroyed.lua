-- Destroyed Europe's spawn cities (ARCHITECTURE.md, "Module map": prototypes/tables/; milestone
-- destroyed-europe).
--
-- Pure data, like config.lua: no function call and no global, so the data stage reads it through require
-- and the Python tools through tools/tnconfig.py's loader. The zone's shape is not here: R7b's 14-vertex
-- polygon and its six exclusion rows are rows of prototypes/tables/regions.lua, which
-- tools/build_regions.py writes from approvals-data.json (S10 design (d)).
--
-- Version 1: APPROVALS 10's spawn cities inside the polygon, by EarthMaps' in-map positions
-- (prototypes/tables/cities.lua) and the polygon's vertices (approvals-data.json
-- destroyed_europe_polygon), keyed by each map's spawn-city setting values in the setting's order. On
-- Europe APPROVALS 10 lists 8 of 41 cities; Luxembourg is not a setting value (APPROVALS 12 removes it
-- for iron-lorraine-minette), which leaves 7 of 40. Atlantic and Old World each hold Prague, at their
-- own in-map position. Vilnius lies 39 km inside the polygon's edge on Europe's map, and no other city of
-- any map lies within 70 km of the edge, so no warped edge (at most 66.7 km of movement, S10) brings
-- another city in. The gate's FG row de_dump_facts recomputes this list from the polygon and the city
-- tables. Spawn cities inside the zone stay selectable (APPROVALS 10); only a random pick on a world
-- with the zone on skips them. A changed list ships as the next version with the pool bodies built from
-- it.
return {
  version = 1,
  zone_cities = {
    europe = {"brussels", "prague", "paris", "berlin", "vilnius", "amsterdam", "warsaw"},
    atlantic = {"prague"},
    olde_world = {"prague"},
  },
}
