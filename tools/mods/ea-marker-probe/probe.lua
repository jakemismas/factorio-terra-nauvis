-- ea-marker-probe (test-only, never shipped): the probe of T18 (b), the D28 city markers (milestone extras).
-- tools/earth_test.py appends this file to control.lua in a staged copy of the mod under test and writes
-- marker-spec.lua beside it, so the probe runs in the mod's own Lua state: a mod may change only its own
-- runtime settings (runtime-api, LuaSettings.global), and the off and on steps change the markers setting.
--   switch   at each tick of spec.switch the setting takes the listed value through settings.global, which
--            raises on_runtime_mod_setting_changed for the mod's own handler
--   report   at each tick of spec.report: the setting's value, the save's map, scale, city number, resolved
--            city index and recorded marker count from storage.earth, the city offset read as
--            scripts/markers.lua reads it, and every rendering object of the mod (id, type, render mode,
--            surface, target position, text)
-- Output at spec.last: script-output/ea-marker-probe/<label>-report.json. Every Earth name comes from the mod's
-- own config.lua; the runner writes only ticks, values and the label into marker-spec.lua.
do
  local spec = require("marker-spec")
  local probe_cfg = require("prototypes.config")
  local setting = probe_cfg.settings[probe_cfg.markers.setting].name
  local report = {label = spec.label, mod = script.mod_name, steps = {}}

  local function offset(surface, earth)
    for _, key in ipairs(probe_cfg.map_order) do
      local versions = (probe_cfg.geography[key] or {}).versions or {}
      for _, g in ipairs(versions) do
        if g.geo_id == earth.geo and probe_cfg.maps[key].id == earth.map then
          local p = surface.calculate_tile_properties({g.cx, g.cy}, {{0, 0}})
          return {key = key, cx = p[g.cx] and p[g.cx][1], cy = p[g.cy] and p[g.cy][1]}
        end
      end
    end
    return {}
  end

  local function snapshot(tick)
    local surface = game.surfaces["nauvis"]
    local earth = storage.earth or {}
    local objects = {}
    for _, o in pairs(rendering.get_all_objects(script.mod_name)) do
      local t = o.target
      local pos = t and t.position
      objects[#objects + 1] = {id = o.id, type = o.type, render_mode = o.render_mode, surface = o.surface.name,
                               x = pos and pos.x, y = pos and pos.y, text = o.type == "text" and o.text or nil}
    end
    report.steps[#report.steps + 1] = {
      tick = tick, value = settings.global[setting].value, map = earth.map, scale = earth.scale,
      city = earth.city, city_index = earth.city_index,
      recorded = earth.markers and #earth.markers or 0, earth = storage.earth ~= nil,
      offset = earth.map and offset(surface, earth) or {}, objects = objects,
    }
  end

  script.on_event(defines.events.on_tick, function(event)
    for _, sw in ipairs(spec.switch) do
      if sw.tick == event.tick then
        settings.global[setting] = {value = sw.value}
      end
    end
    for _, t in ipairs(spec.report) do
      if t == event.tick then
        snapshot(event.tick)
      end
    end
    if event.tick == spec.last then
      helpers.write_file("ea-marker-probe/" .. spec.label .. "-report.json", helpers.table_to_json(report), false)
      log("ea-marker-probe: wrote " .. #report.steps .. " steps")
    end
  end)
end
