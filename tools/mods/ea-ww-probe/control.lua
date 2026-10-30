-- ea-ww-probe: T5, T7 and T15e evidence for the waterways milestone, from a spec the runner stages
-- (ww-spec.lua). Generation is forced in on_tick at tick 1 (every mod's chunk handler then runs inside
-- the force call), and each job writes one JSON file to script-output/ea-ww-probe/<label>-<job>.json:
--   tiles:      the tiles of every listed chunk as run-length rows over a palette with each tile's
--               collision layers, so the checker rebuilds the corridor raster (S4's method)
--   placements: surface.can_place_entity for each listed entity, position and direction (M3: Cargo
--               Ships' waterway pieces need water_tile under every tile they cover)
--   paths:      surface.request_path from each start to the target with a biter's collision box,
--               answered by on_script_path_request_finished; written when all have answered or at
--               the job's deadline tick
local spec = require("ww-spec")
local OUT = "ea-ww-probe/"

local function tile_rows(surface, cx, cy, index, palette)
  local rows = {}
  for y = cy * 32, cy * 32 + 31 do
    local parts, run_i, run_n = {}, nil, 0
    for x = cx * 32, cx * 32 + 31 do
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
  return rows
end

local function layers_of(name)
  local tp = prototypes.tile[name]
  local out = {}
  if tp then
    for k in pairs(tp.collision_mask.layers) do out[#out + 1] = k end
    table.sort(out)
  end
  return out
end

local function run_tiles(surface, job)
  for _, c in ipairs(job.chunks) do
    surface.request_to_generate_chunks({x = c[1] * 32 + 16, y = c[2] * 32 + 16}, 0)
  end
  surface.force_generate_chunk_requests()
  local palette, index, chunks = {}, {}, {}
  for _, c in ipairs(job.chunks) do
    chunks[#chunks + 1] = {c[1], c[2], tile_rows(surface, c[1], c[2], index, palette),
                           surface.is_chunk_generated({c[1], c[2]})}
  end
  local info = {}
  for _, name in ipairs(palette) do info[#info + 1] = {name = name, layers = layers_of(name)} end
  return {palette = info, chunks = chunks,
          format = "chunks: [cx, cy, rows, generated]; rows are index*count runs, 32 rows of 32 tiles from the chunk's corner"}
end

local function run_placements(surface, job)
  local area_chunks = {}
  for _, p in ipairs(job.placements) do
    local cx, cy = math.floor(p.x / 32), math.floor(p.y / 32)
    for dx = -1, 1 do
      for dy = -1, 1 do
        area_chunks[(cx + dx) .. "," .. (cy + dy)] = {cx + dx, cy + dy}
      end
    end
  end
  for _, c in pairs(area_chunks) do
    surface.request_to_generate_chunks({x = c[1] * 32 + 16, y = c[2] * 32 + 16}, 0)
  end
  surface.force_generate_chunk_requests()
  local out = {}
  for i, p in ipairs(job.placements) do
    local proto = prototypes.entity[p.name]
    local ok = false
    if proto then
      ok = surface.can_place_entity{name = p.name, position = {p.x, p.y}, direction = p.direction,
                                    build_check_type = defines.build_check_type.manual}
    end
    out[i] = {p.name, p.x, p.y, p.direction, proto ~= nil, ok}
  end
  return {placements = out, format = "[name, x, y, direction, prototype exists, can_place_entity]"}
end

local pending = {}

local function start_paths(surface, job)
  for _, c in ipairs(job.chunks or {}) do
    surface.request_to_generate_chunks({x = c[1] * 32 + 16, y = c[2] * 32 + 16}, 0)
  end
  surface.force_generate_chunk_requests()
  local rec = {job = job, results = {}, ids = {}, started = game.tick, answered = 0}
  local box = {{-0.4, -0.4}, {0.4, 0.4}}
  for i, s in ipairs(job.starts) do
    local id = surface.request_path{bounding_box = box, collision_mask = {layers = {player = true, object = true}},
                                    start = {s[1], s[2]}, goal = {job.target[1], job.target[2]},
                                    force = "enemy", radius = 2, pathfind_flags = {cache = false},
                                    path_resolution_modifier = 0}
    rec.ids[id] = i
    rec.results[i] = {s[1], s[2], "pending", 0}
  end
  pending[#pending + 1] = rec
end

local function finish(label, job, data)
  data.job = job.name
  data.tick = game.tick
  helpers.write_file(OUT .. label .. "-" .. job.name .. ".json", helpers.table_to_json(data), false)
end

script.on_event(defines.events.on_script_path_request_finished, function(e)
  for _, rec in ipairs(pending) do
    local i = rec.ids[e.id]
    if i then
      local r = rec.results[i]
      r[3] = e.path and "ok" or (e.try_again_later and "busy" or "failed")
      r[4] = e.path and #e.path or 0
      r[5] = game.tick - rec.started
      rec.answered = rec.answered + 1
    end
  end
end)

script.on_event(defines.events.on_tick, function(e)
  local surface = game.surfaces["nauvis"]
  if e.tick == 1 then
    for _, job in ipairs(spec.jobs) do
      if job.kind == "tiles" then
        finish(spec.label, job, run_tiles(surface, job))
      elseif job.kind == "placements" then
        finish(spec.label, job, run_placements(surface, job))
      elseif job.kind == "paths" then
        start_paths(surface, job)
      end
    end
  end
  for k = #pending, 1, -1 do
    local rec = pending[k]
    if rec.answered >= #rec.job.starts or e.tick >= rec.started + (rec.job.deadline_ticks or 600) then
      finish(spec.label, rec.job, {paths = rec.results, answered = rec.answered,
                                   format = "[start x, start y, ok | failed | busy | pending, path nodes, ticks]"})
      table.remove(pending, k)
    end
  end
end)
