-- The outline of a Destroyed Europe made after the first release (config.lua destroyed.outline): the zone runs to the
-- shore on its sea sides, Brittany and the Channel coast included, and the barrier stands on land edges only.
--
-- Pure data, like config.lua: the data stage reads it through require, the Python tools through
-- tools/tnconfig.py's loader. prototypes/expressions/regions.lua turns it into the outline's bodies, in the region
-- frame. Worlds made before keep prototypes/tables/regions.lua's destroyed rows.
--
-- land marks an edge that crosses land, from its vertex to the next: the barrier is measured from those edges alone.
-- The others lie out at sea, past what the warp and a vertex's jitter can reach, so a seed never moves a coast: only
-- land vertices jitter. phase is each vertex's fold phase, the released outline's where the vertex is the same. The
-- land edges stand a barrier's width past the released ones, so the wasteland itself reaches Vienna and Rome.
-- isles is the fixed line down the Channel and the North Sea that keeps Britain and Ireland out at every seed. It
-- takes no warp: at Dover it has 16 km of water on either side. Degrees and km throughout.
return {
  version = 1,
  warp = 2.5,
  vertices = {
    {id = "biscay", lat = 43.45, lon = -2.1, jitter_km = 80, phase = 0.437112688},
    {id = "bay", lat = 45.6, lon = -6.6, jitter_km = 0, phase = 0},
    {id = "ushant", lat = 48.9, lon = -8.6, jitter_km = 0, phase = 0},
    {id = "celtic", lat = 52.5, lon = -4, jitter_km = 0, phase = 0},
    {id = "dogger", lat = 55.2, lon = 3, jitter_km = 0, phase = 0},
    {id = "baltic", lat = 56, lon = 17, jitter_km = 0, phase = 0},
    {id = "sambia", lat = 55.25, lon = 19.7, jitter_km = 30, phase = 0.481420007, land = true},
    {id = "suwalki", lat = 54.36, lon = 23.1, jitter_km = 110, phase = 0.746452696, land = true},
    {id = "bug", lat = 52.0766, lon = 23.6161, jitter_km = 110, phase = 0.796097949, land = true},
    {id = "galicia", lat = 49.7833, lon = 22.7667, jitter_km = 70, phase = 0.320134982, land = true},
    {id = "moravia", lat = 49.5, lon = 18.7, jitter_km = 50, phase = 0.808700745, land = true},
    {id = "pannonia", lat = 47.6, lon = 18.1, jitter_km = 40, phase = 0.5722, land = true},
    {id = "slovenia", lat = 45.6, lon = 15.6, jitter_km = 50, phase = 0.284323369, land = true},
    {id = "istria", lat = 45.3, lon = 13.4, jitter_km = 40, phase = 0.456894025},
    {id = "dalmatia", lat = 43.6, lon = 15, jitter_km = 0, phase = 0},
    {id = "adriatic", lat = 42, lon = 15.3, jitter_km = 60, phase = 0.408658231, land = true},
    {id = "rome", lat = 40.55, lon = 13, jitter_km = 60, phase = 0.33418846},
    {id = "corsica", lat = 41.25, lon = 9.6, jitter_km = 80, phase = 0.534147954},
    {id = "ligure", lat = 41.4, lon = 6.2, jitter_km = 0, phase = 0},
    {id = "lion", lat = 42.35, lon = 3.3, jitter_km = 70, phase = 0.26615482, land = true},
  },
  isles = {
    {48.7, -12}, {49.35, -6}, {49.72, -3.7}, {50.12, -2}, {50.22, -0.4}, {50.45, 0.85}, {51.0072, 1.4786}, {51.33, 2},
    {52.4, 2.85}, {54.4, 1.2}, {58, -0.6}, {61.2, -0.3}, {61.2, -13},
  },
  -- the released keep rows that stand on land: the barrier measures from these as well
  land_keeps = {"keep_denmark", "keep_carpathians"},
}
