-- The outline of the Moscow zone (0.3.1; config.lua moscow): the Baltic states, southern Finland, Belarus, most of
-- Ukraine, Moldova, Crimea, eastern Poland to about 21 E and western Russia from the Gulf of Finland and Lake Onega to
-- about 47 E. The vertices follow a hand-drawn outline over an Old World map view, read off the image by a plate carree
-- fit on its water against a render of the same view (within about a tenth of a degree).
--
-- Pure data, like config.lua; prototypes/expressions/regions.lua builds the outline's bodies from it with the same
-- formulas as the Destroyed Europe outline (zone_outline.lua), so every field means what it means there: land marks an
-- edge that crosses land, from its vertex to the next, and the zone's gradient is measured from those edges alone; the
-- others lie in the Baltic and the Black Sea, so the zone runs to the shore there. Only land vertices jitter. No isles
-- line, no keep rows and no cuts. Degrees and km throughout.
return {
  version = 1,
  warp = 1,
  vertices = {
    {id = "gotland", lat = 55.5, lon = 20.0, jitter_km = 0, phase = 0},
    {id = "courland", lat = 57.8, lon = 20.3, jitter_km = 0, phase = 0},
    {id = "hanko", lat = 59.8, lon = 21.8, jitter_km = 0, phase = 0, land = true},
    {id = "forssa", lat = 60.9, lon = 23.9, jitter_km = 12, phase = 0.613, land = true},
    {id = "jyvaskyla", lat = 61.9, lon = 25.9, jitter_km = 12, phase = 0.287, land = true},
    {id = "savo", lat = 62.2, lon = 27.9, jitter_km = 12, phase = 0.842, land = true},
    {id = "karelia", lat = 62.1, lon = 29.8, jitter_km = 12, phase = 0.159, land = true},
    {id = "sortavala", lat = 61.8, lon = 31.4, jitter_km = 15, phase = 0.476, land = true},
    {id = "ladoga", lat = 61.4, lon = 32.8, jitter_km = 15, phase = 0.731, land = true},
    {id = "svir", lat = 61.4, lon = 34.1, jitter_km = 15, phase = 0.394, land = true},
    {id = "onega", lat = 62.0, lon = 35.6, jitter_km = 15, phase = 0.918, land = true},
    {id = "kargopol", lat = 63.1, lon = 37.6, jitter_km = 15, phase = 0.205, land = true},
    {id = "dvina", lat = 63.8, lon = 40.1, jitter_km = 15, phase = 0.567, land = true},
    {id = "pinega", lat = 63.2, lon = 42.3, jitter_km = 15, phase = 0.083, land = true},
    {id = "kotlas", lat = 61.7, lon = 44.0, jitter_km = 15, phase = 0.659, land = true},
    {id = "vetluga", lat = 59.9, lon = 45.4, jitter_km = 15, phase = 0.352, land = true},
    {id = "kirov", lat = 57.8, lon = 46.6, jitter_km = 15, phase = 0.771, land = true},
    {id = "volga", lat = 55.4, lon = 45.7, jitter_km = 15, phase = 0.128, land = true},
    {id = "mordovia", lat = 53.6, lon = 43.3, jitter_km = 15, phase = 0.534, land = true},
    {id = "tambov", lat = 52.2, lon = 41.6, jitter_km = 15, phase = 0.897, land = true},
    {id = "voronezh", lat = 50.5, lon = 41.4, jitter_km = 15, phase = 0.241, land = true},
    {id = "don", lat = 48.6, lon = 41.7, jitter_km = 15, phase = 0.685, land = true},
    {id = "manych", lat = 46.6, lon = 41.1, jitter_km = 12, phase = 0.419, land = true},
    {id = "kuban", lat = 45.1, lon = 39.9, jitter_km = 15, phase = 0.806, land = true},
    {id = "anapa", lat = 44.2, lon = 38.2, jitter_km = 0, phase = 0},
    {id = "kerch", lat = 43.9, lon = 36.2, jitter_km = 0, phase = 0},
    {id = "crimea", lat = 43.8, lon = 34.4, jitter_km = 0, phase = 0},
    {id = "euxine", lat = 43.7, lon = 32.5, jitter_km = 0, phase = 0},
    {id = "varna", lat = 43.5, lon = 30.5, jitter_km = 0, phase = 0},
    {id = "constanta", lat = 44.3, lon = 28.8, jitter_km = 0, phase = 0, land = true},
    {id = "galati", lat = 45.4, lon = 27.2, jitter_km = 15, phase = 0.312, land = true},
    {id = "prut", lat = 47.2, lon = 26.3, jitter_km = 12, phase = 0.748, land = true},
    {id = "podolia", lat = 49.0, lon = 25.9, jitter_km = 12, phase = 0.176, land = true},
    {id = "lviv", lat = 49.9, lon = 24.0, jitter_km = 12, phase = 0.593, land = true},
    {id = "lublin", lat = 51.2, lon = 21.8, jitter_km = 12, phase = 0.937, land = true},
    {id = "masuria", lat = 53.2, lon = 20.6, jitter_km = 12, phase = 0.461, land = true},
  },
}
