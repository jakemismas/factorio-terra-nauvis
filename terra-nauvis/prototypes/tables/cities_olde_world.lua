-- Spawn city table of the Old World map (ARCHITECTURE.md, "Module map": prototypes/tables/; slice
-- olde-world-atlantic).
--
-- Pure data in cities.lua's shape (no function call and no global), one file per map from this slice
-- on, so a landed map's table file and the spawn bearings generated from it never change when a map
-- is added (prototypes/city_tables.lua merges the files). Old World, version 1 (never released, so
-- edited in place on Jake's start-city ruling of 2026-10-30 07:35): EarthMaps' 30 Olde World cities
-- (data-src/earthmaps/olde_world.json, cities.list), none removed by APPROVALS 12, in the order of
-- data-src/approvals/approvals-data.json cities.olde_world.kept, each at EarthMaps' own in-map
-- position, except Prague, moved from EarthMaps' grid point (13.7E, 52.1N) to the real city
-- (50.08N 14.44E); then Frankfurt (50.11N 8.68E), Aachen (50.78N 6.08E) and Moscow (55.76N 37.62E),
-- appended so the other rows keep their indices. Every moved or added row is the centre of the
-- reference pixel holding the real coordinate in the map's plate carree georeference
-- (data-src/earthmaps/olde_world.json georeference: lon = -19.1778 + (col + 0.5) / 45, lat = 82.0889
-- - (row + 0.5) / 45), rounded to 3 decimals as the EarthMaps rows are. A released table version is
-- never edited: a changed row ships as the next version with the fold bodies built from it
-- (versioning rule 5).
return {
  olde_world = {
    version = 1,
    cities = {
      prague = {name = "Prague", country = "Czech Republic", lon = 14.433, lat = 50.078},
      madrid = {name = "Madrid", country = "Spain", lon = -4.078, lat = 40.989},
      london = {name = "London", country = "United Kingdom", lon = 0.367, lat = 52.1},
      kovdor = {name = "Kovdor", country = "Russia", lon = 29.256, lat = 65.433},
      munguy = {name = "Munguy", country = "Russia", lon = 80.367, lat = 65.433},
      xeta = {name = "Xeta", country = "Russia", lon = 102.589, lat = 74.322},
      yakutia = {name = "Yakutia", country = "Russia", lon = 124.811, lat = 65.433},
      zyryanka = {name = "Zyryanka", country = "Russia", lon = 147.033, lat = 65.433},
      kharkiv = {name = "Kharkiv", country = "Ukraine", lon = 35.922, lat = 52.1},
      huambo = {name = "Huambo", country = "Angola", lon = 16.367, lat = -5.678},
      mongo = {name = "Mongo", country = "Chad", lon = 13.7, lat = 13.211},
      dangila = {name = "Dangila", country = "Ethiopia", lon = 35.922, lat = 13.211},
      bamako = {name = "Bamako", country = "Mali", lon = -8.522, lat = 13.211},
      akka = {name = "Akka", country = "Morocco", lon = -8.522, lat = 29.878},
      waddan = {name = "Waddan", country = "North Africa", lon = 13.7, lat = 29.878},
      johannesburg = {name = "Johannesburg", country = "South Africa", lon = 27.033, lat = -23.456},
      songea = {name = "Songea", country = "Tanzania", lon = 35.922, lat = -5.678},
      tabuk = {name = "Tabuk", country = "Saudi Arabia", lon = 35.922, lat = 29.878},
      chengdu = {name = "Chengdu", country = "China", lon = 102.589, lat = 29.878},
      nanchang = {name = "Nanchang", country = "China", lon = 115.922, lat = 29.878},
      songling = {name = "Songling", country = "China", lon = 124.811, lat = 52.1},
      delhi = {name = "Delhi", country = "India", lon = 80.367, lat = 29.878},
      hampi = {name = "Hampi", country = "India", lon = 75.922, lat = 16.544},
      bam = {name = "Bam", country = "Iran", lon = 58.144, lat = 29.878},
      aktobe = {name = "Aktobe", country = "Kazakhstan", lon = 58.144, lat = 52.1},
      semey = {name = "Semey", country = "Kazakhstan", lon = 80.367, lat = 52.1},
      moron = {name = "Moron", country = "Mongolia", lon = 102.589, lat = 52.1},
      bangkok = {name = "Bangkok", country = "Thailand", lon = 100.367, lat = 16.544},
      griffith = {name = "Griffith", country = "Australia", lon = 147.033, lat = -27.9},
      newman = {name = "Newman", country = "Australia", lon = 118.144, lat = -23.456},
      frankfurt = {name = "Frankfurt", country = "Germany", lon = 8.678, lat = 50.1},
      aachen = {name = "Aachen", country = "Germany", lon = 6.078, lat = 50.789},
      moscow = {name = "Moscow", country = "Russia", lon = 37.611, lat = 55.767},
    },
  },
}
