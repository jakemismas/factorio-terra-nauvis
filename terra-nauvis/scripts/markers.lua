-- City markers (ARCHITECTURE.md, "Control stage"; milestone extras; D28; APPROVALS 1a). With the runtime-global
-- setting City markers on, the map view of an Earth world (one made from a Terra Nauvis preset, which
-- guards.on_init records in storage.earth) shows the name of every city of the save's map where the city
-- lies; off removes them. Each marker is a rendering object in chart mode (config.lua markers): it draws on
-- the map view only, for every force, needs no charted chunk and no per-chunk event, and the headless T18
-- check reads it with rendering.get_all_objects.
--
-- A city's marker stands in the tile holding its reference pixel centre: world = geo - the city offset, where
-- the geo tile is the middle tile of the city's pixel at the save's scale (the conversion of spawn-cities'
-- force-spawn probe, T18 (c)) and the city offset is read back from the save with calculate_tile_properties
-- at (0, 0) through the save's own geography version, as scripts/bandfix.lua reads it (random folds in
-- float32, so Lua never recomputes it). The city rows are the save's map's table
-- (prototypes/tables/cities.lua; a released table is never edited, so the save's rows stay its own).
-- on_init draws them when the setting is on as the world is created; on_runtime_mod_setting_changed draws
-- or removes them. Every change destroys the markers it recorded in
-- storage.earth.markers before drawing again, so a repeated switch never doubles them.
--
-- A Map-type-only world gets none: it holds no storage.earth, and its scale and spawn follow the startup
-- settings at every load, so a marker drawn once could later stand away from its city.
local cfg = require("prototypes.config")
local cities = require("prototypes.tables.cities")
local guards = require("scripts.guards")

local M = {}
local MK = cfg.markers
local floor = math.floor

local function setting_name()
  return cfg.settings[MK.setting].name
end

local function map_key_of(id)
  for _, key in ipairs(cfg.map_order) do
    if cfg.maps[key].id == id then
      return key
    end
  end
  return nil
end

-- The world tile of a city row: its reference pixel by the pixel-centre formula (config.lua coordinates), the
-- middle tile of that pixel at the save's scale in geo tiles, less the city offset.
local function world_tile(m, c, scale, cx, cy)
  local C = cfg.coordinates
  local col = floor((c.lon - m.lon_left_edge) * C.px_per_degree)
  local row = floor((m.lat_top_edge - c.lat) * C.px_per_degree)
  local corner = floor(scale / C.corner_offset_divisor)
  return scale * (col - m.wr) + corner - cx, scale * (row - m.hr) + corner - cy
end

-- Destroys the markers the save recorded; returns how many were still there.
local function clear(earth)
  local n = 0
  for _, id in ipairs(earth.markers or {}) do
    local obj = rendering.get_object_by_id(id)
    if obj and obj.valid then
      obj.destroy()
      n = n + 1
    end
  end
  earth.markers = nil
  return n
end

-- Draws one marker per city of the save's map and records them; returns how many it drew.
local function draw(surface, earth)
  local key = map_key_of(earth.map)
  local m = key and cfg.maps[key]
  -- the city offset names of the save's own geography version (its tn_geo), never the newest
  local geo = guards.geography_of(earth.geo)
  local g = key and geo and geo.map == key and geo.version
  local tbl = key and cities[key]
  if not (m and g and tbl and earth.scale) then
    log({"", cfg.identity.title, ": no city table serves this save's map, so it gets no city markers"})
    return 0
  end
  local p = surface.calculate_tile_properties({g.cx, g.cy}, {{0, 0}})
  local cx, cy = p[g.cx] and p[g.cx][1], p[g.cy] and p[g.cy][1]
  if not (cx and cy) then
    log({"", cfg.identity.title, ": the city offset could not be read, so this save gets no city markers"})
    return 0
  end
  cx, cy = floor(cx + 1 / 2), floor(cy + 1 / 2)
  local keys = {}
  for k in pairs(tbl.cities) do
    keys[#keys + 1] = k
  end
  table.sort(keys)
  local ids = {}
  for _, k in ipairs(keys) do
    local c = tbl.cities[k]
    local x, y = world_tile(m, c, earth.scale, cx, cy)
    local obj = rendering.draw_text({
      text = c.name, surface = surface, target = {x + MK.centre, y + MK.centre}, color = MK.color,
      scale = MK.text_scale, scale_with_zoom = true, render_mode = MK.render_mode,
      alignment = MK.alignment, vertical_alignment = MK.vertical_alignment,
    })
    ids[#ids + 1] = obj.id
  end
  earth.markers = ids
  return #ids
end

-- Brings the save's markers in line with the setting: removes the recorded ones, then draws every city
-- again when the setting is on.
function M.sync()
  local earth = storage.earth
  local surface = game.surfaces["nauvis"]
  if not (earth and surface) then
    return
  end
  local removed = clear(earth)
  local drawn = 0
  if settings.global[setting_name()].value then
    drawn = draw(surface, earth)
  end
  log({"", cfg.identity.title, ": city markers removed ", removed, ", drawn ", drawn})
end

-- on_init, after guards.on_init has detected an Earth world and filled storage.earth.
function M.on_init()
  if storage.earth and settings.global[setting_name()].value then
    M.sync()
  end
end

function M.on_setting_changed(event)
  if event.setting == setting_name() then
    M.sync()
  end
end

return M
