-- The missing-name guard's test build (T16; review note 2 and 3): a later version of the mod
-- that no longer defines some Earth names. Every noise expression drop-names.lua lists is removed,
-- and every map-gen preset key that names it with it, so the build itself stays consistent while a
-- save made with the full build still names the dropped body. tools/earth_test.py writes
-- drop-names.lua into a staged copy at run time; this committed copy names nothing. An empty list
-- adds the mod alone, which still runs on_configuration_changed on every save it loads.
local spec = require("drop-names")
local presets = data.raw["map-gen-presets"]["default"]
for _, name in ipairs(spec.names) do
  if not data.raw["noise-expression"][name] then
    error("ea-drop-name: no noise expression " .. name)
  end
  data.raw["noise-expression"][name] = nil
  for _, p in pairs(presets) do
    local pen = type(p) == "table" and p.basic_settings and p.basic_settings.property_expression_names
    if pen then
      for k, v in pairs(pen) do
        if v == name then
          pen[k] = nil
        end
      end
    end
  end
end
log("ea-drop-name: dropped " .. #spec.names .. " names")
