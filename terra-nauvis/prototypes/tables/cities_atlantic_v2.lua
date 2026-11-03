-- Spawn city table of the Atlantic map, version 2 (ARCHITECTURE.md, "Module map": prototypes/tables/; 0.3.1).
--
-- Version 1's 50 rows, unchanged and in its order (prototypes/tables/cities_atlantic.lua, released in 0.3.0 and never
-- edited), then Frankfurt (50.11N 8.68E) and Moscow (55.76N 37.62E), appended so every earlier row keeps its index.
-- Each added row is the centre of the reference pixel holding the real coordinate in the map's plate carree
-- georeference (data-src/earthmaps/atlantic.json georeference: lon = -168.6444 + (col + 0.5) / 45, lat = 87.1778 -
-- (row + 0.5) / 45), rounded to 3 decimals as the EarthMaps rows are. prototypes/city_tables.lua merges the newest
-- version of each map; the released spawn record reads the rows its own bearings file holds (spawn.lua), so the
-- version 1 folds keep their text. A released table version is never edited: a changed row ships as the next
-- version with the fold bodies built from it (versioning rule 5).
return {
  atlantic = {
    version = 2,
    cities = {
      prague = {name = "Prague", country = "Czech Republic", lon = 13.589, lat = 51.611},
      madrid = {name = "Madrid", country = "Spain", lon = -4.189, lat = 40.5},
      london = {name = "London", country = "United Kingdom", lon = 0.256, lat = 51.611},
      kovdor = {name = "Kovdor", country = "Russia", lon = 29.144, lat = 64.944},
      munguy = {name = "Munguy", country = "Russia", lon = 80.256, lat = 64.944},
      xeta = {name = "Xeta", country = "Russia", lon = 102.478, lat = 73.833},
      yakutia = {name = "Yakutia", country = "Russia", lon = 124.7, lat = 64.944},
      zyryanka = {name = "Zyryanka", country = "Russia", lon = 146.922, lat = 64.944},
      kharkiv = {name = "Kharkiv", country = "Ukraine", lon = 35.811, lat = 51.611},
      huambo = {name = "Huambo", country = "Angola", lon = 16.922, lat = -6.167},
      mongo = {name = "Mongo", country = "Chad", lon = 13.589, lat = 12.722},
      dangila = {name = "Dangila", country = "Ethiopia", lon = 35.811, lat = 12.722},
      bamako = {name = "Bamako", country = "Mali", lon = -8.633, lat = 12.722},
      akka = {name = "Akka", country = "Morocco", lon = -8.633, lat = 29.389},
      waddan = {name = "Waddan", country = "North Africa", lon = 13.589, lat = 29.389},
      johannesburg = {name = "Johannesburg", country = "South Africa", lon = 26.922, lat = -23.944},
      songea = {name = "Songea", country = "Tanzania", lon = 35.811, lat = -6.167},
      tabuk = {name = "Tabuk", country = "Saudi Arabia", lon = 35.811, lat = 29.389},
      chengdu = {name = "Chengdu", country = "China", lon = 102.478, lat = 29.389},
      nanchang = {name = "Nanchang", country = "China", lon = 115.811, lat = 29.389},
      songling = {name = "Songling", country = "China", lon = 124.7, lat = 51.611},
      delhi = {name = "Delhi", country = "India", lon = 80.256, lat = 29.389},
      hampi = {name = "Hampi", country = "India", lon = 75.811, lat = 16.056},
      bam = {name = "Bam", country = "Iran", lon = 58.033, lat = 29.389},
      aktobe = {name = "Aktobe", country = "Kazakhstan", lon = 58.033, lat = 51.611},
      semey = {name = "Semey", country = "Kazakhstan", lon = 80.256, lat = 51.611},
      moron = {name = "Moron", country = "Mongolia", lon = 102.478, lat = 51.611},
      bangkok = {name = "Bangkok", country = "Thailand", lon = 100.256, lat = 16.056},
      ["mexico-city"] = {name = "Mexico City", country = "Mexico", lon = -99.744, lat = 20.5},
      ["ellesmere-island"] = {name = "Ellesmere Island", country = "Canada", lon = -81.967, lat = 78.278},
      ["fort-liard"] = {name = "Fort Liard", country = "Canada", lon = -128.633, lat = 64.944},
      hearst = {name = "Hearst", country = "Canada", lon = -81.967, lat = 51.611},
      ["mid-baffin"] = {name = "Mid Baffin", country = "Canada", lon = -73.078, lat = 69.389},
      okak = {name = "Okak", country = "Canada", lon = -64.189, lat = 57.167},
      saskatoon = {name = "Saskatoon", country = "Canada", lon = -106.411, lat = 52.722},
      yellowknife = {name = "Yellowknife", country = "Canada", lon = -104.189, lat = 66.056},
      qaanaaq = {name = "Qaanaaq", country = "Greenland", lon = -55.3, lat = 78.278},
      ["summit-camp"] = {name = "Summit Camp", country = "Greenland", lon = -44.189, lat = 67.167},
      uranienborg = {name = "Uranienborg", country = "Greenland", lon = -28.633, lat = 78.278},
      albany = {name = "Albany", country = "United States", lon = -74.189, lat = 42.722},
      boise = {name = "Boise", country = "United States", lon = -115.3, lat = 42.722},
      minneapolis = {name = "Minneapolis", country = "United States", lon = -94.189, lat = 42.722},
      ["el-paso"] = {name = "El Paso", country = "United States", lon = -108.633, lat = 33.833},
      hughes = {name = "Hughes", country = "United States", lon = -155.3, lat = 64.944},
      montgomery = {name = "Montgomery", country = "United States", lon = -84.189, lat = 33.833},
      cordoba = {name = "Cordoba", country = "Argentina", lon = -64.189, lat = -28.389},
      palmas = {name = "Palmas", country = "Brazil", lon = -46.411, lat = -8.389},
      iquitos = {name = "Iquitos", country = "Peru", lon = -70.856, lat = -1.722},
      griffith = {name = "Griffith", country = "Australia", lon = 146.922, lat = -28.389},
      newman = {name = "Newman", country = "Australia", lon = 118.033, lat = -23.944},
      frankfurt = {name = "Frankfurt", country = "Germany", lon = 8.678, lat = 50.1},
      moscow = {name = "Moscow", country = "Russia", lon = 37.611, lat = 55.767},
    },
  },
}
