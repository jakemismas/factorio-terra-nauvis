-- The block the timer forces, "bx:by:wx:wy" in chunks (block corner, warm-up chunk). Runtime-global,
-- so a save keeps the value it was created with and a run never raises on_configuration_changed.
data:extend{
  {type = "string-setting", name = "tq1-gen-block", setting_type = "runtime-global", default_value = "64:32:-64:-48",
   allow_blank = false},
}
