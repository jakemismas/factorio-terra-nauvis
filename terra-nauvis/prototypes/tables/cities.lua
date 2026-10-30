-- Spawn city tables (ARCHITECTURE.md, "Module map": prototypes/tables/; slice spawn-cities).
--
-- Pure data, like config.lua: no function call and no global, so the data and control stages read
-- it through require and the Python tools through tools/tnconfig.py's loader. Each map's table is
-- keyed by the spawn-city setting value (config.lua's settings, whose allowed_values give the order
-- and therefore each city's index), and each row holds EarthMaps' own in-map position as the
-- reference JSON records it: lon and lat of the pixel centre the spawn lands on, in degrees. The
-- data stage converts them to reference pixels with the pixel-centre formula (ARCHITECTURE.md,
-- "Build-time data flow", step 4). A released table version is never edited: a changed row ships
-- as the next version with the fold bodies built from it (versioning rule 5).
--
-- Europe, version 1: EarthMaps' 41 Europe cities (data-src/earthmaps/europe.json, cities.list)
-- minus Luxembourg, which APPROVALS 12 removes for iron-lorraine-minette; the 40 kept cities are
-- data-src/approvals/approvals-data.json cities.europe.kept, in that order. The gate's FG row
-- sc_dump_facts binds every row to both files.
return {
  europe = {
    version = 1,
    cities = {
      tirana = {name = "Tirana", country = "Albania", lon = 20.233, lat = 41.167},
      ["andorra-la-vella"] = {name = "Andorra la Vella", country = "Andorra", lon = 2.056, lat = 42.367},
      vienna = {name = "Vienna", country = "Austria", lon = 17.3, lat = 47.122},
      minsk = {name = "Minsk", country = "Belarus", lon = 26.544, lat = 52.233},
      brussels = {name = "Brussels", country = "Belgium", lon = 4.678, lat = 50.367},
      sarajevo = {name = "Sarajevo", country = "Bosnia and Herzegovina", lon = 18.189, lat = 43.433},
      sofia = {name = "Sofia", country = "Bulgaria", lon = 23.567, lat = 41.967},
      zagreb = {name = "Zagreb", country = "Croatia", lon = 16.411, lat = 45.567},
      prague = {name = "Prague", country = "Czechia", lon = 14.989, lat = 50.367},
      tallinn = {name = "Tallinn", country = "Estonia", lon = 25.078, lat = 59.211},
      helsinki = {name = "Helsinki", country = "Finland", lon = 25.033, lat = 60.367},
      paris = {name = "Paris", country = "France", lon = 2.411, lat = 49.389},
      berlin = {name = "Berlin", country = "Germany", lon = 13.256, lat = 52.189},
      athens = {name = "Athens", country = "Greece", lon = 22.856, lat = 38.456},
      budapest = {name = "Budapest", country = "Hungary", lon = 20.011, lat = 46.722},
      rome = {name = "Rome", country = "Italy", lon = 11.967, lat = 42.144},
      pristina = {name = "Pristina", country = "Kosovo", lon = 21.522, lat = 42.056},
      riga = {name = "Riga", country = "Latvia", lon = 23.656, lat = 56.678},
      vaduz = {name = "Vaduz", country = "Liechtenstein", lon = 9.567, lat = 46.544},
      vilnius = {name = "Vilnius", country = "Lithuania", lon = 21.433, lat = 54.056},
      chisinau = {name = "Chisinau", country = "Moldova", lon = 29.478, lat = 46.456},
      monaco = {name = "Monaco", country = "Monaco", lon = 7.744, lat = 44.1},
      podgorica = {name = "Podgorica", country = "Montenegro", lon = 19.433, lat = 42.544},
      amsterdam = {name = "Amsterdam", country = "Netherlands", lon = 4.9, lat = 52.322},
      skopje = {name = "Skopje", country = "North Macedonia", lon = 22.056, lat = 41.344},
      oslo = {name = "Oslo", country = "Norway", lon = 10.856, lat = 59.922},
      warsaw = {name = "Warsaw", country = "Poland", lon = 21.256, lat = 51.211},
      lisbon = {name = "Lisbon", country = "Portugal", lon = -9.011, lat = 38.633},
      bucharest = {name = "Bucharest", country = "Romania", lon = 26.144, lat = 44.322},
      moscow = {name = "Moscow", country = "Russia", lon = 37.522, lat = 55.033},
      ["san-marino"] = {name = "San Marino", country = "San Marino", lon = 11.922, lat = 44.278},
      belgrade = {name = "Belgrade", country = "Serbia", lon = 20.811, lat = 45.033},
      bratislava = {name = "Bratislava", country = "Slovakia", lon = 19.211, lat = 48.278},
      ljubljana = {name = "Ljubljana", country = "Slovenia", lon = 14.456, lat = 46.144},
      madrid = {name = "Madrid", country = "Spain", lon = -3.367, lat = 40.678},
      stockholm = {name = "Stockholm", country = "Sweden", lon = 18.411, lat = 59.656},
      bern = {name = "Bern", country = "Switzerland", lon = 7.744, lat = 46.011},
      ankara = {name = "Ankara", country = "Turkey", lon = 32.456, lat = 39.656},
      kyiv = {name = "Kyiv", country = "Ukraine", lon = 30.811, lat = 49.789},
      london = {name = "London", country = "United Kingdom", lon = 0.322, lat = 51.656},
    },
  },
}
