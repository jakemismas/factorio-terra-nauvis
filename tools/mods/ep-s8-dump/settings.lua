-- All startup settings: dump_render.py run writes them into the modset's mod-settings.dat.
data:extend{
  {type = "string-setting", name = "ep-s8-dump-label", setting_type = "startup", default_value = "dump", allow_blank = false},
  {type = "string-setting", name = "ep-s8-dump-surface", setting_type = "startup", default_value = "nauvis", allow_blank = false},
  -- Areas: "x0,y0,w,h;x0,y0,w,h" in tiles, top-left inclusive.
  {type = "string-setting", name = "ep-s8-dump-areas", setting_type = "startup", default_value = "-128,-128,256,256", allow_blank = true},
  {type = "string-setting", name = "ep-s8-dump-types", setting_type = "startup",
   default_value = "tree,simple-entity,resource,cliff,unit-spawner,turret,unit,fish", allow_blank = true},
  {type = "bool-setting", name = "ep-s8-dump-decoratives", setting_type = "startup", default_value = true},
  -- Points: "x,y;x,y" in tiles; names: comma list of noise expressions or properties to evaluate there.
  {type = "string-setting", name = "ep-s8-dump-points", setting_type = "startup", default_value = "", allow_blank = true},
  {type = "string-setting", name = "ep-s8-dump-names", setting_type = "startup", default_value = "", allow_blank = true},
  -- Scene: comma list of "cliffs" (one cliff of every orientation on cleared landfill, with the game's
  -- collision rasters) and "wall" (a cliff wall across x -40..40 near y 1026 with one 8-tile gap).
  {type = "string-setting", name = "ep-s8-dump-scene", setting_type = "startup", default_value = "", allow_blank = true},
  {type = "int-setting", name = "ep-s8-dump-scene-lattice", setting_type = "startup", default_value = 4, minimum_value = 1, maximum_value = 16},
  -- Grid: "x0,y0,step,nx,ny" (first point and spacing in tiles); grid-name is evaluated there with
  -- calculate_tile_properties and written as run-length rows of 1 (value op threshold), 0 or 2 (not finite).
  {type = "string-setting", name = "ep-s8-dump-grid", setting_type = "startup", default_value = "", allow_blank = true},
  {type = "string-setting", name = "ep-s8-dump-grid-name", setting_type = "startup", default_value = "elevation", allow_blank = true},
  {type = "string-setting", name = "ep-s8-dump-grid-threshold", setting_type = "startup", default_value = "0", allow_blank = false},
  {type = "string-setting", name = "ep-s8-dump-grid-op", setting_type = "startup", default_value = "ge", allowed_values = {"ge", "gt", "le", "lt"}},
  {type = "int-setting", name = "ep-s8-dump-gen-tick", setting_type = "startup", default_value = 1, minimum_value = 1, maximum_value = 100000},
  {type = "int-setting", name = "ep-s8-dump-tick", setting_type = "startup", default_value = 2, minimum_value = 1, maximum_value = 100000},
}
