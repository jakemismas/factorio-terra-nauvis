-- Isolation check (a), S9's method: the twin keeps every prototype of the mod under test and turns
-- its fine coast field (the firewall bodies) into one constant, so a program that reads the coast
-- per tile changes and one that does not stays identical. tools/earth_test.py writes
-- twin-names.lua into a staged copy of this mod at run time; this committed copy names nothing.
local spec = require("twin-names")
for _, name in ipairs(spec.names) do
  local e = data.raw["noise-expression"][name]
  if not e then
    error("ea-coast-twin: no noise expression " .. name)
  end
  e.expression = spec.value
  e.local_expressions = nil
end
log("ea-coast-twin: " .. #spec.names .. " bodies set to " .. spec.value)
