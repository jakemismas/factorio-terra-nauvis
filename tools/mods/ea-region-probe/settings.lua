-- Startup settings the runner writes into the modset's mod-settings.dat (tools/earth_test.py).
local P = "ea-region-probe-"
data:extend{
  {type = "string-setting", name = P .. "label", setting_type = "startup", default_value = "probe",
   allow_blank = false},
  {type = "string-setting", name = P .. "surface", setting_type = "startup", default_value = "nauvis",
   allow_blank = false},
  -- names evaluated at (0, 0) and recorded: the per-save numbers a check reads back
  {type = "string-setting", name = P .. "constants", setting_type = "startup", default_value = "", allow_blank = true},
  -- two names (x, y) whose values at (0, 0) are the spawn offset: world = geo - offset
  {type = "string-setting", name = P .. "offset", setting_type = "startup", default_value = "", allow_blank = true},
  -- points "x,y;x,y" in geo tiles and the comma list of names read at each
  {type = "string-setting", name = P .. "points", setting_type = "startup", default_value = "", allow_blank = true},
  {type = "string-setting", name = P .. "names", setting_type = "startup", default_value = "", allow_blank = true},
  -- grids "label|x0,y0,step,nx,ny|mode|name,name;..." in geo tiles; mode raw (values) or sign (1 above
  -- 0, 0 at or below, 2 not finite, run-length per row)
  {type = "string-setting", name = P .. "grids", setting_type = "startup", default_value = "", allow_blank = true},
  {type = "int-setting", name = P .. "tick", setting_type = "startup", default_value = 1, minimum_value = 1,
   maximum_value = 100000},
}
