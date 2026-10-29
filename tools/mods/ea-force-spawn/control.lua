-- T18 (c), D31: a later per-player spawn needs no new generation data. At tick 1 the probe reads the
-- world's folded city offset (cx, cy) and scale with calculate_tile_properties at (0, 0), converts
-- each picked city of the shipped city table to its world tile (world = geo - offset, the tile holding
-- the city's pixel centre: scale (col - wr) + floor(scale / divisor) - offset), sets a second force's
-- spawn there, generates that chunk and records the tile and elevation found. spec.cities holds the
-- shipped table rows (degrees), spec.map the shipped map constants and coordinate rules.
local spec = require("force-spawn-spec")

local function world_tile(c, cx, cy, scale)
  local m = spec.map
  local col = math.floor((c.lon - m.lon_left_edge) * spec.px_per_degree)
  local row = math.floor((m.lat_top_edge - c.lat) * spec.px_per_degree)
  local corner = math.floor(scale / spec.corner_divisor)
  return {x = scale * (col - m.wr) + corner - cx, y = scale * (row - m.hr) + corner - cy, col = col, row = row}
end

script.on_event(defines.events.on_tick, function(event)
  if event.tick ~= 1 or not spec.scale_name then
    return
  end
  local surface = game.surfaces["nauvis"]
  local names = {spec.offset_names[1], spec.offset_names[2], spec.scale_name}
  local p = surface.calculate_tile_properties(names, {{x = 0, y = 0}})
  local cx, cy, scale = p[names[1]][1], p[names[2]][1], p[names[3]][1]
  local force = game.forces["ea-force-spawn"] or game.create_force("ea-force-spawn")
  local out = {offset = {cx, cy}, scale = scale, spawns = {}}
  for _, key in ipairs(spec.picks) do
    local c = spec.cities[key]
    local w = world_tile(c, cx, cy, scale)
    force.set_spawn_position({w.x + 0.5, w.y + 0.5}, surface)
    surface.request_to_generate_chunks({w.x, w.y}, 0)
    surface.force_generate_chunk_requests()
    local sp = force.get_spawn_position(surface)
    local t = surface.get_tile(math.floor(sp.x), math.floor(sp.y))
    local e = surface.calculate_tile_properties({"elevation"}, {{x = w.x, y = w.y}}).elevation[1]
    out.spawns[#out.spawns + 1] = {city = key, name = c.name, tile = t.valid and t.name or "<none>",
                                   world = {w.x, w.y}, pixel = {w.col, w.row}, spawn = {sp.x, sp.y},
                                   elevation = e}
  end
  helpers.write_file("ea-force-spawn/spawns.json", helpers.table_to_json(out), false)
  log("ea-force-spawn: wrote " .. #out.spawns .. " spawns")
end)
