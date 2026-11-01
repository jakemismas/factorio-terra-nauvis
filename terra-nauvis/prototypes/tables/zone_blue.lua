-- The shapes of Blue corrupted UK and Australia (config.lua blue).
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through tools/tnconfig.py's
-- loader. prototypes/expressions/regions.lua turns it into bodies in the region frame. Degrees throughout.
--
-- britain and australia lie out at sea on every side, so the coast is their edge: they take no warp, no jitter and no
-- distance, only a crossing count, and a seed never moves them. britain follows the line that keeps Destroyed Europe
-- off the British Isles (tables/zone_outline.lua, isles) from the Channel to Shetland, then passes down the Irish Sea
-- and west of Scilly, short of the Republic. australia runs through the Torres Strait, about 100 km off Cape York and
-- 75 km off Papua, and takes in Tasmania. maps lists the maps that hold the shape.
--
-- ulster is Northern Ireland. Its border is the one edge that crosses land, marked land from a vertex to the next: the
-- barrier measures from those edges, and warp moves them by a share of the region layer's warp. They stand about 10 km
-- outside the real border, which is what the feather takes back. The rest of it lies at sea in Lough Foyle, the North
-- Channel and the Irish Sea.
return {
  version = 1,
  britain = {
    maps = {"europe", "atlantic", "olde_world"},
    {49.6, -7}, {49.35, -6}, {49.72, -3.7}, {50.12, -2}, {50.22, -0.4}, {50.45, 0.85}, {51.0072, 1.4786}, {51.33, 2},
    {52.4, 2.85}, {54.4, 1.2}, {58, -0.6}, {61.2, -0.3}, {61.2, -3}, {58.9, -9.4}, {56.3, -8.9}, {55.75, -7.25},
    {55.38, -6.35}, {54.95, -5.6}, {54.2, -5.2}, {53.4, -5.4}, {52.3, -5.85}, {51.4, -5.95}, {50.3, -7},
  },
  australia = {
    maps = {"atlantic", "olde_world"},
    {-13, 121}, {-11.8, 126.5}, {-10.6, 130}, {-10.2, 136.8}, {-9.95, 141.5}, {-9.75, 143}, {-9.9, 145}, {-15, 150},
    {-24, 155.3}, {-29, 155}, {-38, 151.5}, {-40, 149.5}, {-43.5, 149}, {-44.6, 146.5}, {-42, 143.7}, {-39.5, 142.8},
    {-37, 137}, {-36.5, 118}, {-35.2, 113.8}, {-26, 112}, {-21, 113.2},
  },
  ulster = {
    maps = {"europe", "atlantic", "olde_world"},
    warp = 0.25,
    vertices = {
      {lat = 55.2, lon = -6.95, land = true},
      {lat = 55.05, lon = -7.2, land = true},
      {lat = 55, lon = -7.5, land = true},
      {lat = 54.75, lon = -7.65, land = true},
      {lat = 54.5, lon = -8, land = true},
      {lat = 54.42, lon = -8.3, land = true},
      {lat = 54.2, lon = -8.05, land = true},
      {lat = 54.05, lon = -7.25, land = true},
      {lat = 54.25, lon = -6.95, land = true},
      {lat = 54, lon = -6.6, land = true},
      {lat = 53.9, lon = -6.45, land = true},
      {lat = 53.85, lon = -6.1},
      {lat = 53.9, lon = -5.85},
      {lat = 54.35, lon = -5.25},
      {lat = 54.9, lon = -5.55},
      {lat = 55.38, lon = -6.3},
      {lat = 55.5, lon = -6.9},
    },
  },
}
