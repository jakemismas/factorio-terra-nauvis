-- ea-cc-probe (test-only, never shipped): the compat-completeness checks' probe (tools/earth_test.py, section
-- compat-completeness). Its jobs are read once, in on_init, from the runtime-global setting ea-cc-probe-job
-- ("|" between jobs) and kept in storage, so a save keeps them:
--   none
--   census:<label>:<tick>:<digest 0|1>:<areas>
--       at <tick> request every chunk of the areas ("x0,y0,w,h;..." in tiles) on Nauvis, force their
--       generation, and write per area the tile, entity and decorative name counts, the resource amounts by
--       name, the resources standing on a water tile by name and, with digest 1, one digest per chunk of its
--       tiles, entities and decoratives, to
--       script-output/ea-cc-probe/<label>-census.json (T17, T12, the T13 interaction rows)
--   surfaces:<tick>:<keys>[:<control>]
--       at <tick>, every surface's name, planet and property_expression_names, and each key of <keys>
--       ("a,b") read at (0, 0) through calculate_tile_properties, which ignores unrecognized names, to
--       script-output/ea-cc-probe/surfaces.json (T14 at runtime: minime's hidden surfaces); with <control>,
--       first a surface of that name made with no map gen settings of its own (it inherits the save's
--       defaults: the positive control a surface guard must strip)
-- The on_tick handler is registered only while a job is pending, so a finished save carries none.
local DIR = "ea-cc-probe/"
local TYPES = {"resource", "tree", "simple-entity", "fish", "cliff", "unit-spawner", "turret", "unit"}
local M32 = 4294967296

local function split(text, sep)
  local out = {}
  for part in string.gmatch(text or "", "[^" .. sep .. "]+") do
    out[#out + 1] = part
  end
  return out
end

local function parse(spec)
  local jobs = {}
  for _, j in ipairs(split(spec, "|")) do
    local p = split(j, ":")
    if p[1] == "census" then
      local areas = {}
      for _, a in ipairs(split(p[5], ";")) do
        local v = split(a, ",")
        if #v == 4 then
          areas[#areas + 1] = {x0 = tonumber(v[1]), y0 = tonumber(v[2]), w = tonumber(v[3]), h = tonumber(v[4])}
        end
      end
      jobs[#jobs + 1] = {kind = "census", label = p[2], tick = tonumber(p[3]), digest = p[4] == "1", areas = areas}
    elseif p[1] == "surfaces" then
      jobs[#jobs + 1] = {kind = "surfaces", tick = tonumber(p[2]), keys = split(p[3] or "", ","), control = p[4]}
    end
  end
  return jobs
end

-- Every intermediate stays below 2^53, so the double arithmetic is exact and a digest is stable.
local function mix(h, v)
  return (h * 65599 + v) % M32
end

local ids = {}
local function sid(s)
  local id = ids[s]
  if not id then
    id = 5381
    for i = 1, #s do
      id = (id * 33 + string.byte(s, i)) % M32
    end
    ids[s] = id
  end
  return id
end

-- A map coordinate in 1/256 tile as a non-negative 32-bit number.
local function q(v)
  return math.floor(v * 256 + 0.5) % M32
end

local function area_chunks(a)
  local out = {}
  for cy = math.floor(a.y0 / 32), math.floor((a.y0 + a.h - 1) / 32) do
    for cx = math.floor(a.x0 / 32), math.floor((a.x0 + a.w - 1) / 32) do
      out[#out + 1] = {cx, cy}
    end
  end
  return out
end

-- One chunk's digests: its tiles in row order, and order-free sums over its entities and decoratives.
local function chunk_digest(s, cx, cy)
  local t = 0
  for y = cy * 32, cy * 32 + 31 do
    for x = cx * 32, cx * 32 + 31 do
      t = mix(t, sid(s.get_tile(x, y).name))
    end
  end
  local box = {{cx * 32, cy * 32}, {cx * 32 + 32, cy * 32 + 32}}
  local e, en = 0, 0
  for _, ent in pairs(s.find_entities_filtered{area = box}) do
    local p = ent.position
    if p.x >= cx * 32 and p.x < cx * 32 + 32 and p.y >= cy * 32 and p.y < cy * 32 + 32 then
      local h = mix(mix(mix(sid(ent.name), q(p.x)), q(p.y)), ent.type == "resource" and ent.amount or 0)
      e = (e + h) % M32
      en = en + 1
    end
  end
  local d, dn = 0, 0
  for _, dec in pairs(s.find_decoratives_filtered{area = box}) do
    local h = mix(mix(mix(sid(dec.decorative.name), q(dec.position.x)), q(dec.position.y)), dec.amount)
    d = (d + h) % M32
    dn = dn + 1
  end
  return {t = t, e = e, en = en, d = d, dn = dn}
end

local function census(job)
  local s = game.surfaces["nauvis"]
  for _, a in ipairs(job.areas) do
    for _, c in ipairs(area_chunks(a)) do
      s.request_to_generate_chunks({c[1] * 32 + 16, c[2] * 32 + 16}, 0)
    end
  end
  s.force_generate_chunk_requests()
  local tiles = {}
  for name, _ in pairs(prototypes.tile) do
    tiles[#tiles + 1] = name
  end
  table.sort(tiles)
  local out = {label = job.label, tick = game.tick, areas = {}}
  for i, a in ipairs(job.areas) do
    local box = {{a.x0, a.y0}, {a.x0 + a.w, a.y0 + a.h}}
    local rec = {x0 = a.x0, y0 = a.y0, w = a.w, h = a.h, tiles = {}, entities = {}, types = {}, amounts = {},
                 on_water = {}, decoratives = {}, chunks = {}, generated = 0}
    for _, name in ipairs(tiles) do
      local n = s.count_tiles_filtered{area = box, name = name}
      if n > 0 then
        rec.tiles[name] = n
      end
    end
    for _, ent in pairs(s.find_entities_filtered{area = box, type = TYPES}) do
      rec.entities[ent.name] = (rec.entities[ent.name] or 0) + 1
      rec.types[ent.name] = ent.type
      if ent.type == "resource" then
        rec.amounts[ent.name] = (rec.amounts[ent.name] or 0) + ent.amount
        if s.get_tile(ent.position.x, ent.position.y).collides_with("water_tile") then
          rec.on_water[ent.name] = (rec.on_water[ent.name] or 0) + 1
        end
      end
    end
    for _, c in ipairs(area_chunks(a)) do
      if s.is_chunk_generated(c) then
        rec.generated = rec.generated + 1
      end
      local cbox = {{c[1] * 32, c[2] * 32}, {c[1] * 32 + 32, c[2] * 32 + 32}}
      for _, dec in pairs(s.find_decoratives_filtered{area = cbox}) do
        local n = dec.decorative.name
        rec.decoratives[n] = (rec.decoratives[n] or 0) + 1
      end
      if job.digest then
        rec.chunks[c[1] .. "," .. c[2]] = chunk_digest(s, c[1], c[2])
      end
    end
    out.areas[i] = rec
  end
  helpers.write_file(DIR .. job.label .. "-census.json", helpers.table_to_json(out), false)
end

local function surfaces(job)
  local out = {tick = game.tick, surfaces = {}, control = job.control, control_tick = job.control_tick}
  for _, s in pairs(game.surfaces) do
    local pen = {}
    local ok, err = pcall(function()
      for k, v in pairs(s.map_gen_settings.property_expression_names or {}) do
        pen[k] = tostring(v)
      end
    end)
    local rec = {name = s.name, index = s.index, planet = s.planet and s.planet.name or nil, pen = pen,
                 pen_error = (not ok) and tostring(err) or nil, values = {}, unrecognized = {}}
    for _, k in ipairs(job.keys) do
      local ok2, res = pcall(function()
        return s.calculate_tile_properties({k}, {{0, 0}})
      end)
      if ok2 and res and res[k] then
        rec.values[k] = res[k][1]
      elseif ok2 then
        rec.unrecognized[#rec.unrecognized + 1] = k
      else
        rec.values[k] = "error: " .. tostring(res)
      end
    end
    out.surfaces[#out.surfaces + 1] = rec
  end
  helpers.write_file(DIR .. "surfaces.json", helpers.table_to_json(out), false)
end

local function pending()
  for _, j in ipairs(storage.jobs or {}) do
    if not j.done then
      return true
    end
  end
  return false
end

local on_tick
on_tick = function(e)
  for _, j in ipairs(storage.jobs) do
    -- the positive control, one tick before the read: a surface made with no map gen settings of its own
    -- inherits the save's defaults, an Earth preset's keys included, unless the mod under test's surface
    -- guard strips them
    if j.kind == "surfaces" and j.control and not j.control_tick and e.tick >= j.tick - 1 then
      if not game.surfaces[j.control] then
        game.create_surface(j.control)
      end
      j.control_tick = e.tick
    end
    if not j.done and e.tick >= j.tick and (j.kind ~= "surfaces" or not j.control or j.control_tick ~= e.tick) then
      if j.kind == "census" then
        census(j)
      else
        surfaces(j)
      end
      j.done = true
    end
  end
  if not pending() then
    script.on_event(defines.events.on_tick, nil)
  end
end

script.on_init(function()
  local spec = settings.global["ea-cc-probe-job"].value
  storage.jobs = parse(spec)
  helpers.write_file(DIR .. "init.json", helpers.table_to_json{spec = spec, jobs = #storage.jobs, tick = game.tick},
                     false)
  if pending() then
    script.on_event(defines.events.on_tick, on_tick)
  end
end)

script.on_load(function()
  if pending() then
    script.on_event(defines.events.on_tick, on_tick)
  end
end)
