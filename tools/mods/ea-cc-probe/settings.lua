-- The probe's jobs (control.lua): runtime-global, read once in on_init and kept in storage, so a save keeps
-- its jobs and a startup value never differs between a save and the run that loads it.
data:extend{
  {type = "string-setting", name = "ea-cc-probe-job", setting_type = "runtime-global", default_value = "none",
   allow_blank = false},
}
