-- The outline of a Destroyed Europe made on 0.3.0 and after (config.lua destroyed.outline.next): zone_outline.lua's
-- outline, which worlds made before keep, with four changes. All of northern
-- Germany and Jutland come in, and the Danish islands stay out: the Denmark keep row is no longer a land keep, the
-- North Sea edge runs on past Norway and Sweden (norway, sweden), and the sea cut nordic takes Funen, Zealand, the
-- smaller Danish islands, Bornholm and Scania out of the presence. The south of France runs to the Pyrenees and not
-- into them: biscay and lion move out to sea, a land vertex iberia stands in Spain, and the land cut iberia keeps
-- Spain and the massif out, its north edge 6 reference pixels short of the snow on each map (the maps draw the massif
-- differently: Europe's snow stands up to 15 pixels farther north than Old World's). A bit more land round Venice:
-- istria moves south-east, so Veneto, Friuli and western Istria come in (Slovenia stays out).
--
-- Pure data, like config.lua; prototypes/expressions/regions.lua builds the outline's next bodies from it. Every
-- field is zone_outline.lua's. cuts are fixed polygons, unwarped: a sea cut (land = false) stops the zone's presence
-- alone and runs through water on every map, so it reads its crossing count and takes no roughness; a land cut is a
-- keep the barrier measures from as well, and takes the shared roughness as a keep row does. A cut holds one latlon
-- list for every map, or maps, one list per map key, folded on the map. Fitted from previews at seed 1000
-- (<work folder>/f-chaos/cuts.py, nordic2.py): nordic, one list, is the mid-line of the straits between the zone's
-- land (Jutland north and south of the Limfjord with Als and the islets within 3 pixels of its coast, the Wadden
-- islands, the German and Polish coast with Fehmarn and all of Rugen) and the rest (the Danish islands, Samsoe, Laesoe,
-- Anholt, Bornholm, Scandinavia), on the three maps at scales 1, 6 and 12 at once, so it keeps at least a quarter
-- pixel of water to either side on each, simplified to 0.75 reference pixels; iberia's edge, per map, follows the
-- snow's north edge at scale 1 less 6 pixels, smoothed, simplified to 1. A land cut's depth_px starts its depth that
-- far in, so the zone's fray and feather (destroyed.barrier: 0 to 48 and about 20 pixels) run out at the cut's edge in
-- places and the zone meets the foothills, more or less, instead of stopping a fray and a feather short of them.
-- Degrees, in the raster frame.
return {
  version = 2,
  warp = 2.5,
  vertices = {
    {id = "biscay", lat = 44.0, lon = -6.0, jitter_km = 0, phase = 0},
    {id = "bay", lat = 45.6, lon = -6.6, jitter_km = 0, phase = 0},
    {id = "ushant", lat = 48.9, lon = -8.6, jitter_km = 0, phase = 0},
    {id = "celtic", lat = 52.5, lon = -4, jitter_km = 0, phase = 0},
    {id = "dogger", lat = 55.2, lon = 3, jitter_km = 0, phase = 0},
    {id = "norway", lat = 59, lon = 6.5, jitter_km = 0, phase = 0},
    {id = "sweden", lat = 59, lon = 13.5, jitter_km = 0, phase = 0},
    {id = "baltic", lat = 56, lon = 17, jitter_km = 0, phase = 0},
    {id = "sambia", lat = 55.25, lon = 19.7, jitter_km = 30, phase = 0.481420007, land = true},
    {id = "suwalki", lat = 54.36, lon = 23.1, jitter_km = 110, phase = 0.746452696, land = true},
    {id = "bug", lat = 52.0766, lon = 23.6161, jitter_km = 110, phase = 0.796097949, land = true},
    {id = "galicia", lat = 49.7833, lon = 22.7667, jitter_km = 70, phase = 0.320134982, land = true},
    {id = "moravia", lat = 49.5, lon = 18.7, jitter_km = 50, phase = 0.808700745, land = true},
    {id = "pannonia", lat = 47.6, lon = 18.1, jitter_km = 40, phase = 0.5722, land = true},
    {id = "slovenia", lat = 45.6, lon = 15.6, jitter_km = 50, phase = 0.284323369, land = true},
    {id = "istria", lat = 44.3, lon = 14.4, jitter_km = 30, phase = 0.456894025},
    {id = "dalmatia", lat = 43.6, lon = 15, jitter_km = 0, phase = 0},
    {id = "adriatic", lat = 42, lon = 15.3, jitter_km = 60, phase = 0.408658231, land = true},
    {id = "rome", lat = 40.55, lon = 13, jitter_km = 60, phase = 0.33418846},
    {id = "corsica", lat = 41.25, lon = 9.6, jitter_km = 80, phase = 0.534147954},
    {id = "ligure", lat = 41.4, lon = 6.2, jitter_km = 0, phase = 0},
    {id = "lion", lat = 40.6, lon = 4.5, jitter_km = 0, phase = 0, land = true},
    {id = "iberia", lat = 40.5, lon = -2, jitter_km = 0, phase = 0, land = true},
  },
  -- zone_outline.lua's isles line, the same body
  isles = "v1",
  -- the released keep rows that stand on land: the barrier measures from these as well
  land_keeps = {"keep_carpathians"},
  cuts = {
    {id = "nordic", land = false, latlon = {
      {60.297, 2.8}, {60.3, 18.297}, {55.858, 18.3}, {55.867, 17.936}, {55.939, 17.653}, {55.456, 16.819},
      {55.422, 16.358}, {55.267, 15.931}, {54.842, 15.722}, {54.783, 15.658}, {54.589, 15.325}, {54.489, 14.931},
      {54.494, 14.686}, {54.589, 14.286}, {54.767, 14.192}, {54.933, 13.903}, {55.017, 13.369}, {55.006, 13.181},
      {54.928, 12.975}, {54.797, 12.928}, {54.761, 12.875}, {54.683, 12.703}, {54.661, 12.353}, {54.517, 12.192},
      {54.617, 11.992}, {54.617, 11.925}, {54.569, 11.867}, {54.383, 11.803}, {54.378, 11.603}, {54.339, 11.514},
      {54.572, 11.236}, {54.611, 11.108}, {54.622, 10.908}, {54.522, 10.714}, {54.622, 10.458}, {54.633, 10.281},
      {54.736, 10.189}, {54.914, 10.183}, {55.061, 10.031}, {55.164, 9.794}, {55.325, 9.728}, {55.519, 9.717},
      {55.589, 9.914}, {55.511, 9.969}, {55.536, 9.983}, {55.608, 9.95}, {55.65, 10.069}, {55.706, 10.131},
      {55.744, 10.386}, {55.622, 10.547}, {55.706, 10.847}, {55.936, 10.933}, {56.044, 11.142}, {56.286, 11.361},
      {56.778, 11.147}, {56.897, 10.728}, {57.114, 10.706}, {57.347, 10.733}, {57.553, 10.817}, {57.808, 11.044},
      {57.936, 10.983}, {58.319, 10.65}, {58.417, 10.531}, {58.372, 10.325}, {58.283, 10.119}, {58.2, 9.747},
      {58.056, 9.469}, {57.828, 9.181}, {57.761, 8.869}, {57.583, 8.303}, {57.317, 7.736}, {57.111, 7.442},
      {56.933, 7.092}, {56.644, 6.697}, {56.15, 6.169}, {55.761, 5.669}, {55.044, 4.519}, {54.239, 2.803},
    }},
    {id = "iberia", land = true, depth_px = 50, maps = {
      olde_world = {
        {44.5, -10}, {43.75, -3.6}, {43.631, -1.389}, {43.603, -1.278}, {43.471, -1.078}, {43.443, -0.789},
        {43.268, -0.433}, {43.246, -0.078}, {43.106, 0.5}, {43.129, 0.611}, {43.338, 0.922}, {43.344, 1.056},
        {43.278, 1.389}, {43.351, 1.722}, {43.713, 2.456}, {43.744, 2.589}, {43.738, 2.722}, {43.573, 3.322},
        {43.567, 3.744}, {43.25, 4.4}, {39, 4.4}, {39, -10},
      },
      europe = {
        {44.5, -10}, {43.75, -3.6}, {44.025, -1.344}, {44.056, -1.122}, {44.027, -0.9}, {43.725, -0.567},
        {43.636, -0.278}, {43.478, -0.1}, {43.402, 0.1}, {43.449, 0.256}, {43.433, 0.367}, {43.465, 0.5},
        {43.741, 0.811}, {43.767, 1.256}, {43.811, 1.322}, {43.827, 1.456}, {43.748, 1.833}, {43.529, 2.233},
        {43.5, 2.856}, {43.522, 3.256}, {43.469, 3.478}, {43.25, 4.4}, {39, 4.4}, {39, -10},
      },
      atlantic = {
        {44.5, -10}, {43.75, -3.6}, {44.083, -1.256}, {44.037, -1.167}, {43.852, -1.011}, {43.56, -0.567},
        {43.5, -0.322}, {43.5, -0.056}, {43.325, 0.1}, {43.243, 0.456}, {43.24, 0.7}, {43.383, 1.056},
        {43.411, 1.278}, {43.348, 1.5}, {43.125, 1.722}, {43.078, 1.833}, {43.1, 1.944}, {43.249, 2.189},
        {43.389, 2.567}, {43.284, 2.856}, {43.247, 3.1}, {43.25, 4.4}, {39, 4.4}, {39, -10},
      },
    }},
  },
}
