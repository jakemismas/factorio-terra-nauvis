-- The probe's options (control.lua), runtime-global so a save keeps what it was created with: the block set every
-- surface digests (standard: 90 chunks per planet; wide: 491, for compat-completeness), and in travel mode whether a
-- cargo pod is sent down to every planet the platform reaches.
data:extend{
  {type = "string-setting", name = "ea-sa-probe-blocks", setting_type = "runtime-global", default_value = "standard",
   allowed_values = {"standard", "wide"}},
  {type = "bool-setting", name = "ea-sa-probe-landing", setting_type = "runtime-global", default_value = false},
}
