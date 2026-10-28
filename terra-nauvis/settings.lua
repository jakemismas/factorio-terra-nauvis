-- Mod settings (ARCHITECTURE.md, "Module map"). Names, types, values and defaults come from
-- config.lua; the defaults follow APPROVALS 1a, and tests/design-rules.json holds the row the T16
-- design-rules check compares them with.
local cfg = require("prototypes.config")

local defs = {}
for _, key in ipairs(cfg.setting_order) do
  local s = cfg.settings[key]
  defs[#defs + 1] = {
    type = s.type,
    name = s.name,
    setting_type = s.setting_type,
    default_value = s.default_value,
    allowed_values = s.allowed_values,
    order = s.order,
  }
end
data:extend(defs)
