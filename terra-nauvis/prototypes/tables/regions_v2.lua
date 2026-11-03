-- The second region table (config.lua regions_v2; 0.3.0, Jake 2026-11-02, Earth mods recommendation 3).
-- Hand-kept pure data, like config.lua: the great forests and marshes outside Europe that the first table
-- (prototypes/tables/regions.lua, a released table) lacks. prototypes/expressions/regions.lua gives each row the
-- first table's three bodies (signed distance, weight, depth) and sums every row of both tables into the second
-- versions of the forest and marsh aggregates (config.lua regions_v2.names), which a new world's preset names in the
-- first versions' place (regions_v2.points). Fields as in the first table; a disc of each place's equivalent radius,
-- held inside its land where the place is long and narrow, and the first table's warp shares (forest 0.25, marsh 0).
return {
  rows = {
    {
      id = "borneo", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = 0.8, lon = 114, radius_km = 430,
      maps = {"atlantic", "olde_world"},
      source = "Borneo lowland and montane rain forests (RESOLVE 2017 ecoregions), Earth mods recommendation 3",
    },
    {
      id = "sumatra", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = -0.6, lon = 101.8,
      radius_km = 260,
      maps = {"atlantic", "olde_world"},
      source = "Sumatran lowland and montane rain forests (RESOLVE 2017 ecoregions), Earth mods recommendation 3",
    },
    {
      id = "new_guinea", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = -5.2, lon = 141.5,
      radius_km = 400,
      maps = {"atlantic", "olde_world"},
      source = "New Guinea lowland and montane rain forests (RESOLVE 2017 ecoregions), Earth mods recommendation 3",
    },
    {
      id = "pacific_northwest", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = 46.5, lon = -122.3,
      radius_km = 260,
      maps = {"atlantic"},
      source = "Cascades and Pacific coastal temperate rain forests (RESOLVE 2017), Earth mods recommendation 3",
    },
    {
      id = "appalachian", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = 37.8, lon = -80.8,
      radius_km = 360,
      maps = {"atlantic"},
      source = "Appalachian mixed mesophytic and Blue Ridge forests (RESOLVE 2017), Earth mods recommendation 3",
    },
    {
      id = "valdivian", layer = "forest", shape = "disc", warp = 0.25, boost = 1, lat = -41, lon = -72.8,
      radius_km = 210,
      maps = {"atlantic"},
      source = "Valdivian temperate rain forests (RESOLVE 2017 ecoregions), Earth mods recommendation 3",
    },
    {
      id = "sundarbans", layer = "marsh", shape = "disc", warp = 0, lat = 21.9, lon = 89.2, radius_km = 55,
      maps = {"atlantic", "olde_world"},
      source = "Sundarbans mangroves, about 10000 km2, a disc of its equivalent radius",
    },
    {
      id = "inner_niger_delta", layer = "marsh", shape = "disc", warp = 0, lat = 14.8, lon = -4.3, radius_km = 95,
      maps = {"atlantic", "olde_world"},
      source = "Inner Niger Delta floodplain, about 30000 km2 at high water, a disc of its equivalent radius",
    },
    {
      id = "mekong_delta", layer = "marsh", shape = "disc", warp = 0, lat = 9.9, lon = 105.9, radius_km = 85,
      maps = {"atlantic", "olde_world"},
      source = "Mekong delta wetlands, held to the delta's seaward half",
    },
  },
}
