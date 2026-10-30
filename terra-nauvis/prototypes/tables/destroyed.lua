-- Destroyed Europe's spawn cities (ARCHITECTURE.md, "Module map": prototypes/tables/; slice
-- destroyed-europe).
--
-- Pure data, like config.lua: no function call and no global, so the data stage reads it through require
-- and the Python tools through tools/tnconfig.py's loader. The zone's shape is not here: its outline and
-- keep rows are rows of prototypes/tables/regions.lua, which tools/build_regions.py writes from
-- data-src/approvals/destroyed-zone.json.
--
-- Version 1 (never released, so edited in place on Jake's ruling of 2026-10-30 10:05): every spawn city the
-- zone can hold at any seed, by each map's in-map positions (prototypes/city_tables.lua) and the outline in
-- data-src/approvals/destroyed-zone.json, keyed by each map's spawn-city setting values in the setting's
-- order. The outline moves with the seed by at most 107.5 px (266 km: the warp clamp 60 px at share 2.5, the
-- largest vertex jitter 44.5 px, the roughness clamp 3 px; tools/build_regions.py max_drift_px), so a city
-- within that of the nominal outline is listed even where most seeds leave it outside, and a random pick
-- never lands in the zone at any seed. London lies within that reach but keep_britain holds it outside.
-- Spawn cities inside the zone stay selectable (APPROVALS 10); only a random pick on a world with the zone
-- on skips them.
return {
  version = 1,
  zone_cities = {
    europe = {
      "andorra-la-vella", "vienna", "brussels", "zagreb", "prague", "paris", "berlin", "rome", "riga", "vaduz",
      "vilnius", "monaco", "amsterdam", "warsaw", "san-marino", "bratislava", "ljubljana", "bern",
    },
    atlantic = {"prague"},
    olde_world = {"prague", "frankfurt", "aachen"},
  },
}
