-- The shapes of Blue corrupted UK on worlds made on 0.3.1 and after (config.lua blue.outline.next): zone_blue.lua's
-- britain and ulster rows unchanged, without australia, so the zone holds the United Kingdom alone on every map.
-- Worlds made before keep zone_blue.lua's shapes.
--
-- Pure data, like config.lua; prototypes/expressions/regions.lua builds the next outline's bodies from it. Every field
-- is zone_blue.lua's. Degrees throughout.
return {
  version = 2,
  britain = {
    maps = {"europe", "atlantic", "olde_world"},
    {49.6, -7}, {49.35, -6}, {49.72, -3.7}, {50.12, -2}, {50.22, -0.4}, {50.45, 0.85}, {51.0072, 1.4786}, {51.33, 2},
    {52.4, 2.85}, {54.4, 1.2}, {58, -0.6}, {61.2, -0.3}, {61.2, -3}, {58.9, -9.4}, {56.3, -8.9}, {55.75, -7.25},
    {55.38, -6.35}, {54.95, -5.6}, {54.2, -5.2}, {53.4, -5.4}, {52.3, -5.85}, {51.4, -5.95}, {50.3, -7},
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
