-- ep-s8-dump: tiles, selected entities, point probes and a cliff scene, written to script-output.
-- Generation is forced on gen-tick (in on_tick at tick 1 or later, on_chunk_generated is raised
-- inside the force call, so every mod's chunk handler has run), and the dump is written on dump-tick.
local P = "ep-s8-dump-"
local function S(n) return settings.startup[P .. n].value end

local function split(text, sep)
  local out = {}
  for part in string.gmatch(text or "", "[^" .. sep .. "]+") do out[#out + 1] = part end
  return out
end

local function parse_areas()
  local out = {}
  for _, a in ipairs(split(S("areas"), ";")) do
    local v = split(a, ",")
    if #v == 4 then
      out[#out + 1] = {x0 = tonumber(v[1]), y0 = tonumber(v[2]), w = tonumber(v[3]), h = tonumber(v[4])}
    end
  end
  return out
end

local function parse_points()
  local out = {}
  for _, a in ipairs(split(S("points"), ";")) do
    local v = split(a, ",")
    if #v >= 2 then out[#out + 1] = {x = tonumber(v[1]), y = tonumber(v[2])} end
  end
  return out
end

local SCENE_ORIENTATIONS = {
  "west-to-east", "north-to-south", "east-to-west", "south-to-north", "west-to-north", "north-to-east",
  "east-to-south", "south-to-west", "west-to-south", "north-to-west", "east-to-north", "south-to-east",
  "west-to-none", "none-to-east", "east-to-none", "none-to-west", "north-to-none", "none-to-south",
  "south-to-none", "none-to-north",
}
local SCENE = {x0 = 0, y0 = -1024, spacing = 16}   -- one row of cliffs far from the start area

local function request_area(surface, x0, y0, w, h)
  for cy = math.floor(y0 / 32), math.floor((y0 + h - 1) / 32) do
    for cx = math.floor(x0 / 32), math.floor((x0 + w - 1) / 32) do
      surface.request_to_generate_chunks({x = cx * 32 + 16, y = cy * 32 + 16}, 0)
    end
  end
end

local function color_list(c)
  if not c then return nil end
  return {c.r or 0, c.g or 0, c.b or 0, c.a or 1}
end

local function dump_area(surface, ar, types, want_decoratives)
  local x0, y0, w, h = ar.x0, ar.y0, ar.w, ar.h
  local palette, index, rows = {}, {}, {}
  for y = y0, y0 + h - 1 do
    local parts, run_i, run_n = {}, nil, 0
    for x = x0, x0 + w - 1 do
      local t = surface.get_tile(x, y)
      local name = t.valid and t.name or "<none>"
      local i = index[name]
      if not i then
        palette[#palette + 1] = name
        i = #palette - 1
        index[name] = i
      end
      if i == run_i then
        run_n = run_n + 1
      else
        if run_i then parts[#parts + 1] = run_i .. "*" .. run_n end
        run_i, run_n = i, 1
      end
    end
    parts[#parts + 1] = run_i .. "*" .. run_n
    rows[#rows + 1] = table.concat(parts, " ")
  end
  local tile_info = {}
  for _, name in ipairs(palette) do
    local tp = prototypes.tile[name]
    local layers = {}
    if tp then
      for k in pairs(tp.collision_mask.layers) do layers[#layers + 1] = k end
      table.sort(layers)
    end
    tile_info[#tile_info + 1] = {name = name, map_color = tp and color_list(tp.map_color) or nil, layers = layers}
  end
  local ents, cliffs, eindex, einfo = {}, {}, {}, {}
  local area = {{x0, y0}, {x0 + w, y0 + h}}
  if #types > 0 then
    for _, e in ipairs(surface.find_entities_filtered{area = area, type = types}) do
      local ni = eindex[e.name]
      if not ni then
        local ep = e.prototype
        einfo[#einfo + 1] = {name = e.name, type = e.type, map_color = color_list(ep.map_color),
                             enemy_map_color = color_list(ep.enemy_map_color)}
        ni = #einfo - 1
        eindex[e.name] = ni
      end
      local p = e.position
      if e.type == "cliff" then
        local bb = e.bounding_box
        cliffs[#cliffs + 1] = {ni, p.x, p.y, e.cliff_orientation, bb.left_top.x, bb.left_top.y,
                               bb.right_bottom.x, bb.right_bottom.y, bb.orientation or 0}
      elseif e.type == "resource" then
        ents[#ents + 1] = {ni, p.x, p.y, e.amount}
      else
        ents[#ents + 1] = {ni, p.x, p.y}
      end
    end
  end
  local decoratives = nil
  if want_decoratives then
    decoratives = {}
    for _, d in ipairs(surface.find_decoratives_filtered{area = area}) do
      local n = d.decorative.name
      decoratives[n] = (decoratives[n] or 0) + d.amount
    end
  end
  local chunks_missing = 0
  for cy = math.floor(y0 / 32), math.floor((y0 + h - 1) / 32) do
    for cx = math.floor(x0 / 32), math.floor((x0 + w - 1) / 32) do
      if not surface.is_chunk_generated({cx, cy}) then chunks_missing = chunks_missing + 1 end
    end
  end
  return {
    area = {x0 = x0, y0 = y0, w = w, h = h}, chunks_not_generated = chunks_missing,
    tiles = {palette = palette, info = tile_info, rows = rows,
             encoding = "row-major from y0; each row is index*count pairs left to right from x0"},
    entity_names = einfo,
    entities = ents, entities_format = "[name_index, x, y] plus amount for resources",
    cliffs = cliffs,
    cliffs_format = "[name_index, x, y, cliff_orientation, left_top.x, left_top.y, right_bottom.x, right_bottom.y, bounding_box orientation]",
    decoratives = decoratives,
  }
end

local function dump_points(surface, pts, names)
  local out = {}
  if #pts == 0 then return out end
  local positions = {}
  for i, p in ipairs(pts) do positions[i] = {x = p.x, y = p.y} end
  local props = {}
  if #names > 0 then props = surface.calculate_tile_properties(names, positions) end
  for i, p in ipairs(pts) do
    local t = surface.get_tile(p.x, p.y)
    local vals = {}
    for j, n in ipairs(names) do
      local list = props[n]
      vals[j] = list and list[i] or "unrecognized"
    end
    out[i] = {x = p.x, y = p.y, tile = t.valid and t.name or "<none>", values = vals}
  end
  return out
end

-- Thresholded expression on a regular grid, one calculate_tile_properties call per row (no size cap).
local function dump_grid(surface)
  local v = split(S("grid"), ",")
  if #v ~= 5 then return nil end
  local x0, y0, step, nx, ny = tonumber(v[1]), tonumber(v[2]), tonumber(v[3]), tonumber(v[4]), tonumber(v[5])
  local name, thr, op = S("grid-name"), tonumber(S("grid-threshold")), S("grid-op")
  local rows, nonfinite, ones = {}, 0, 0
  local recognised = true
  for j = 0, ny - 1 do
    local y = y0 + j * step
    local positions = {}
    for i = 0, nx - 1 do positions[i + 1] = {x = x0 + i * step, y = y} end
    local vals = surface.calculate_tile_properties({name}, positions)[name]
    if not vals then
      recognised = false
      break
    end
    local parts, cur, cnt = {}, nil, 0
    for i = 1, nx do
      local val, b = vals[i], 2
      if val == val and val ~= math.huge and val ~= -math.huge then
        local hit
        if op == "ge" then hit = val >= thr elseif op == "gt" then hit = val > thr
        elseif op == "le" then hit = val <= thr else hit = val < thr end
        b = hit and 1 or 0
      end
      if b == 2 then nonfinite = nonfinite + 1 elseif b == 1 then ones = ones + 1 end
      if b == cur then
        cnt = cnt + 1
      else
        if cur then parts[#parts + 1] = cur .. "*" .. cnt end
        cur, cnt = b, 1
      end
    end
    parts[#parts + 1] = cur .. "*" .. cnt
    rows[#rows + 1] = table.concat(parts, " ")
  end
  return {x0 = x0, y0 = y0, step = step, nx = nx, ny = ny, name = name, threshold = thr, op = op,
          recognised = recognised, ones = ones, nonfinite = nonfinite, rows = rows,
          encoding = "row j is y0 + j * step; each row is value*count pairs from x0 by step; 1 = value op threshold, 0 = not, 2 = not finite"}
end

local function scene_setup(surface)
  local n = #SCENE_ORIENTATIONS
  local x0, y0, w, h = SCENE.x0 - 8, SCENE.y0 - 8, n * SCENE.spacing + 16, 32
  local area = {{x0, y0}, {x0 + w, y0 + h}}
  for _, e in ipairs(surface.find_entities_filtered{area = area}) do
    if e.valid and e.type ~= "character" then e.destroy() end
  end
  local tiles = {}
  for y = y0, y0 + h - 1 do
    for x = x0, x0 + w - 1 do tiles[#tiles + 1] = {name = "landfill", position = {x, y}} end
  end
  surface.set_tiles(tiles, true, true, true, false)
  surface.destroy_decoratives{area = area}
  local made = {}
  for i, o in ipairs(SCENE_ORIENTATIONS) do
    made[#made + 1] = surface.create_entity{name = "cliff", position = {SCENE.x0 + (i - 1) * SCENE.spacing, SCENE.y0},
                                            cliff_orientation = o}
  end
  return made
end

-- Known-answer ridge for T6: a straight wall of west-to-east cliffs across x -40..40 at y about 1026,
-- with the two middle cliffs left out, so the only way across inside x -40..40 is an 8-tile gap.
local WALL = {x0 = -48, y0 = 1000, w = 96, h = 48, y = 1024}

local function wall_setup(surface)
  local area = {{WALL.x0, WALL.y0}, {WALL.x0 + WALL.w, WALL.y0 + WALL.h}}
  for _, e in ipairs(surface.find_entities_filtered{area = area}) do
    if e.valid and e.type ~= "character" then e.destroy() end
  end
  local tiles = {}
  for y = WALL.y0, WALL.y0 + WALL.h - 1 do
    for x = WALL.x0, WALL.x0 + WALL.w - 1 do tiles[#tiles + 1] = {name = "landfill", position = {x, y}} end
  end
  surface.set_tiles(tiles, true, true, true, false)
  surface.destroy_decoratives{area = area}
  for x = -40, 36, 4 do
    if x ~= -4 and x ~= 0 then
      surface.create_entity{name = "cliff", position = {x, WALL.y}, cliff_orientation = "west-to-east"}
    end
  end
end

local function scene_probe(surface, made)
  local L = S("scene-lattice")
  local out = {}
  for _, e in ipairs(made) do
    if e and e.valid then
      local p, bb = e.position, e.bounding_box
      local lx0, ly0 = math.floor(p.x) - 6, math.floor(p.y) - 6
      local nx, ny = 12 * L, 12 * L
      local occ, chr = {}, {}
      for j = 0, ny - 1 do
        local ro, rc = {}, {}
        for k = 0, nx - 1 do
          local q = {x = lx0 + (k + 0.5) / L, y = ly0 + (j + 0.5) / L}
          ro[#ro + 1] = (#surface.find_entities_filtered{position = q, type = "cliff"} > 0) and "1" or "0"
          rc[#rc + 1] = surface.can_place_entity{name = "character", position = q} and "0" or "1"
        end
        occ[#occ + 1] = table.concat(ro)
        chr[#chr + 1] = table.concat(rc)
      end
      out[#out + 1] = {orientation = e.cliff_orientation, x = p.x, y = p.y,
                       bounding_box = {bb.left_top.x, bb.left_top.y, bb.right_bottom.x, bb.right_bottom.y, bb.orientation or 0},
                       lattice = {x0 = lx0, y0 = ly0, n = L, nx = nx, ny = ny},
                       cliff_at_point = occ, character_blocked = chr}
    end
  end
  return out
end

local made_scene = nil

script.on_event(defines.events.on_tick, function(ev)
  local gen_tick, dump_tick = S("gen-tick"), S("tick")
  if ev.tick ~= gen_tick and ev.tick ~= dump_tick then return end
  local surface = game.surfaces[S("surface")]
  if not surface then
    log("ep-s8-dump: no surface " .. S("surface"))
    return
  end
  if ev.tick == gen_tick then
    for _, ar in ipairs(parse_areas()) do request_area(surface, ar.x0, ar.y0, ar.w, ar.h) end
    for _, p in ipairs(parse_points()) do request_area(surface, math.floor(p.x), math.floor(p.y), 1, 1) end
    local scene = {}
    for _, s in ipairs(split(S("scene"), ",")) do scene[s] = true end
    if scene.cliffs then
      request_area(surface, SCENE.x0 - 8, SCENE.y0 - 8, #SCENE_ORIENTATIONS * SCENE.spacing + 16, 32)
    end
    if scene.wall then request_area(surface, WALL.x0, WALL.y0, WALL.w, WALL.h) end
    surface.force_generate_chunk_requests()
    if scene.cliffs then made_scene = scene_setup(surface) end
    if scene.wall then wall_setup(surface) end
  end
  if ev.tick == dump_tick then
    local types = split(S("types"), ",")
    local out = {
      format = "ep-s8-dump/1", label = S("label"), tick = ev.tick, surface = surface.name,
      seed = surface.map_gen_settings.seed, active_mods = script.active_mods,
      areas = {}, names = split(S("names"), ","), types = types,
    }
    for _, ar in ipairs(parse_areas()) do out.areas[#out.areas + 1] = dump_area(surface, ar, types, S("decoratives")) end
    out.points = dump_points(surface, parse_points(), out.names)
    if S("grid") ~= "" then out.grid = dump_grid(surface) end
    if made_scene then out.scene = scene_probe(surface, made_scene) end
    helpers.write_file("ep-s8-dump/" .. S("label") .. ".json", helpers.table_to_json(out), false)
    log("ep-s8-dump: wrote ep-s8-dump/" .. S("label") .. ".json, areas " .. #out.areas .. ", points " .. #out.points)
  end
end)
