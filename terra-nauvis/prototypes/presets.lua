-- Map-gen presets (ARCHITECTURE.md, "Preset redirects"), built from config.lua.
--
-- Milestone toolchain ships the placeholder preset only. It names the placeholder elevation and the
-- placeholder's copy of vanilla's start mask, which reads elevation_nauvis, so vanilla starting
-- ore never reads the placeholder shape and the Entity program keeps vanilla's land field
-- (design constraint 3). The isolation checks' positive controls run on a test-only preset
-- (tools/mods/ea-leak-fixture) that redirects elevation alone.
--
-- With a mod of placeholder.withheld_with loaded (Alien Biomes), a preset marked placeholder is
-- not defined at all: Alien Biomes' palms read elevation in the Entity program, so on this preset
-- they would read the placeholder shape and break design constraint 3. Only presets marked
-- placeholder are withheld; the real presets are meant to exist beside Alien Biomes. The gate's
-- ab_placeholder row checks this and retires with the placeholder in europe-coast. From then until
-- climate-tiles ships the switch for every Alien Biomes autoplace that reads elevation (plan
-- reconciliation 9), AB's palms read the real presets' elevation entry, and that leak is outside
-- the gate (ARCHITECTURE.md, design constraint S-3).
local cfg = require("prototypes.config")

local presets = data.raw["map-gen-presets"]["default"]

local function withheld(p)
  if not p.placeholder then
    return false
  end
  for _, m in ipairs(cfg.placeholder.withheld_with) do
    if mods[m] then
      return true
    end
  end
  return false
end

for _, key in ipairs(cfg.preset_order) do
  local p = cfg.presets[key]
  if not withheld(p) then
    local names = {}
    if p.placeholder then
      for _, k in ipairs(cfg.placeholder.keys) do
        names[k] = cfg.placeholder.names[k]
      end
    end
    presets[p.name] = {
      order = p.order,
      basic_settings = {property_expression_names = names},
    }
  end
end
