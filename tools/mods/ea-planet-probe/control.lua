-- T14's runtime part (S11's method): what a planet surface inherits from the save's default map gen
-- settings, with and without the mod under test's surface guard. The "init" surface is made in this
-- probe's on_init, after the mod under test's on_init (this probe loads after it), and surfaces made
-- inside an on_init raise no on_surface_created (S11), so no guard sees it: the positive control.
-- The "tick" surface is made at tick 1 through LuaPlanet.create_surface, which raises
-- on_surface_created. The probe names no key of the mod under test: it lists every key whose value
-- equals the save's default, the keys a new surface inherits.
local OUT = "ea-planet-probe/planets.json"

local function inherited(surface)
  local default = game.default_map_gen_settings.property_expression_names or {}
  local pen = surface.map_gen_settings.property_expression_names or {}
  local same, keys = {}, {}
  for k, v in pairs(pen) do
    keys[#keys + 1] = k
    if default[k] ~= nil and tostring(default[k]) == tostring(v) then
      same[#same + 1] = k
    end
  end
  table.sort(same)
  table.sort(keys)
  local props = surface.calculate_tile_properties({"elevation"}, {{x = 0, y = 0}})
  return {name = surface.name, planet = surface.planet and surface.planet.name, keys = keys, inherited = same,
          elevation_key = pen.elevation, elevation_at_origin = props.elevation and props.elevation[1]}
end

local function report()
  local out = {default_keys = {}, surfaces = {}}
  for k in pairs(game.default_map_gen_settings.property_expression_names or {}) do
    out.default_keys[#out.default_keys + 1] = k
  end
  table.sort(out.default_keys)
  for _, name in ipairs({"ea-planet-probe-init", "ea-planet-probe-tick"}) do
    local s = game.surfaces[name]
    if s then
      out.surfaces[name] = inherited(s)
    end
  end
  helpers.write_file(OUT, helpers.table_to_json(out), false)
  log("ea-planet-probe: wrote " .. OUT)
end

script.on_init(function()
  game.planets["ea-planet-probe-init"].create_surface()
end)

script.on_event(defines.events.on_tick, function(event)
  if event.tick == 1 then
    game.planets["ea-planet-probe-tick"].create_surface()
  elseif event.tick == 2 then
    report()
  end
end)
