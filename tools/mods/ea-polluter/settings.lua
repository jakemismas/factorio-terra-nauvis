-- Startup settings the runner writes into the modset's mod-settings.dat (tools/earth_test.py).
local P = "ea-polluter-"
data:extend{
  {type = "string-setting", name = P .. "label", setting_type = "startup", default_value = "polluter", allow_blank = false},
  {type = "string-setting", name = P .. "surface", setting_type = "startup", default_value = "nauvis",
   allow_blank = false},
  -- the site in world tiles, "x,y"
  {type = "string-setting", name = P .. "site", setting_type = "startup", default_value = "0,0", allow_blank = false},
  -- the tick that generates the chunks, the tick the furnaces and pollution start, the tick the record is
  -- written
  {type = "int-setting", name = P .. "gen-tick", setting_type = "startup", default_value = 1, minimum_value = 1,
   maximum_value = 100000},
  {type = "int-setting", name = P .. "start-tick", setting_type = "startup", default_value = 2, minimum_value = 1,
   maximum_value = 100000},
  {type = "int-setting", name = P .. "end-tick", setting_type = "startup", default_value = 18000, minimum_value = 3,
   maximum_value = 1000000},
  -- the radius in tiles round the site whose chunks are generated and whose enemies are counted
  {type = "int-setting", name = P .. "radius", setting_type = "startup", default_value = 384, minimum_value = 32,
   maximum_value = 4096},
  -- pollution added at the site every `period` ticks, and the furnaces placed there
  {type = "int-setting", name = P .. "amount", setting_type = "startup", default_value = 2000, minimum_value = 0,
   maximum_value = 1000000},
  {type = "int-setting", name = P .. "period", setting_type = "startup", default_value = 60, minimum_value = 1,
   maximum_value = 100000},
  {type = "int-setting", name = P .. "furnaces", setting_type = "startup", default_value = 4, minimum_value = 1,
   maximum_value = 64},
}
