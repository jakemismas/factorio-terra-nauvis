-- Startup settings the runner writes into the modset's mod-settings.dat (tools/earth_test.py).
local P = "ea-path-probe-"
data:extend{
  {type = "string-setting", name = P .. "label", setting_type = "startup", default_value = "paths", allow_blank = false},
  {type = "string-setting", name = P .. "surface", setting_type = "startup", default_value = "nauvis",
   allow_blank = false},
  -- start and goal pairs in world tiles, "ax,ay,bx,by;ax,ay,bx,by"
  {type = "string-setting", name = P .. "pairs", setting_type = "startup", default_value = "", allow_blank = true},
  -- requests per pair, the tick that generates the chunks, the tick that sends the requests and the tick
  -- that writes the record
  {type = "int-setting", name = P .. "repeats", setting_type = "startup", default_value = 10, minimum_value = 1,
   maximum_value = 1000},
  {type = "int-setting", name = P .. "gen-tick", setting_type = "startup", default_value = 1, minimum_value = 1,
   maximum_value = 100000},
  {type = "int-setting", name = P .. "send-tick", setting_type = "startup", default_value = 2, minimum_value = 1,
   maximum_value = 100000},
  {type = "int-setting", name = P .. "end-tick", setting_type = "startup", default_value = 600, minimum_value = 2,
   maximum_value = 1000000},
  -- the margin in tiles round each pair's box whose chunks are generated before the requests
  {type = "int-setting", name = P .. "margin", setting_type = "startup", default_value = 256, minimum_value = 0,
   maximum_value = 4096},
  -- how far in tiles an end may move to a spot that can hold the unit
  {type = "int-setting", name = P .. "snap", setting_type = "startup", default_value = 16, minimum_value = 0,
   maximum_value = 256},
  -- the biter whose box and collision mask the requests use
  {type = "string-setting", name = P .. "unit", setting_type = "startup", default_value = "small-biter",
   allow_blank = false},
}
