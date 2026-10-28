-- The job for saves created while this value is set (read once, in on_init). Runtime-global, not
-- startup: a startup value that differs between a save and the run that loads it would raise
-- on_configuration_changed in every mod (EarthMaps re-runs its setup there).
data:extend{
  {type = "string-setting", name = "tq2-mode", setting_type = "runtime-global", default_value = "none",
   allow_blank = false},
}
