-- Isolation checks' positive controls (design constraint 3), test-only presets the runner stages:
--   - the first redirects every key of the mod's first preset except its start mask, so vanilla's
--     starting_resources_lake_mask reads the fine field in the Entity program: isolation (a) must
--     see Entity differ between the real build and its constant-coast twin, and (b) must walk from
--     a starting ore to the fine field;
--   - the second redirects every key of that preset, start mask included, plus an entity and a
--     decorative autoplace key (entity:<name>:probability and the like) to fixture bodies that read
--     the fine field: (b) must follow both keys there.
-- tools/earth_test.py writes fixture-names.lua into a staged copy at run time: the presets, their
-- redirect tables and the fixture bodies. A redirect value is a noise expression name or a number
-- (a double, a boolean or a numeric string), as property_expression_names allows.
local spec = require("fixture-names")

for _, e in ipairs(spec.expressions or {}) do
  data:extend({{type = "noise-expression", name = e.name, expression = e.expression}})
end

for _, p in ipairs(spec.presets or {}) do
  local names = {}
  local n = 0
  for k, v in pairs(p.names) do
    local t = type(v)
    if t == "string" then
      if not tonumber(v) and not data.raw["noise-expression"][v] then
        error("ea-leak-fixture: no noise expression " .. v)
      end
    elseif t ~= "number" and t ~= "boolean" then
      error("ea-leak-fixture: the redirect " .. tostring(k) .. " holds a " .. t)
    end
    names[k] = v
    n = n + 1
  end
  data.raw["map-gen-presets"]["default"][p.name] = {
    order = p.order,
    basic_settings = {property_expression_names = names},
  }
  log("ea-leak-fixture: preset " .. p.name .. " redirects " .. n .. " keys")
end
