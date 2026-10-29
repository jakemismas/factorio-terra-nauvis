-- Two stand-ins for a planet without its own elevation (S11: eapp-open), copied from Nauvis's
-- prototype with an empty property_expression_names, so a surface of either inherits every key of
-- the save's default map gen settings that it does not set itself.
local function probe_planet(name, orientation)
  local mgs = table.deepcopy(data.raw.planet.nauvis.map_gen_settings)
  mgs.property_expression_names = {}
  return {
    type = "planet",
    name = name,
    icon = "__base__/graphics/icons/nauvis.png",
    distance = 20,
    orientation = orientation,
    map_gen_settings = mgs,
  }
end

data:extend({
  probe_planet("ea-planet-probe-init", 0.5),
  probe_planet("ea-planet-probe-tick", 0.55),
})
