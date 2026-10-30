-- ea-path-probe: surface.request_path from given starts to given goals, timed by the runner with
-- --benchmark-verbose all (pathFinder per tick). Chunks round every pair are generated on gen-tick, so
-- the pathfinder meets real terrain; the requests go out on send-tick; the record is written on
-- end-tick with the count of finished, failed and retried requests and the ticks each took.
local P = "ea-path-probe-"
local function S(n) return settings.startup[P .. n].value end

local function split(text, sep)
  local out = {}
  for part in string.gmatch(text or "", "[^" .. sep .. "]+") do out[#out + 1] = part end
  return out
end

local function pairs_list()
  local out = {}
  for _, a in ipairs(split(S("pairs"), ";")) do
    local v = split(a, ",")
    if #v == 4 then
      out[#out + 1] = {ax = tonumber(v[1]), ay = tonumber(v[2]), bx = tonumber(v[3]), by = tonumber(v[4])}
    end
  end
  return out
end

local function generate(surface, p, margin)
  local x0, x1 = math.min(p.ax, p.bx) - margin, math.max(p.ax, p.bx) + margin
  local y0, y1 = math.min(p.ay, p.by) - margin, math.max(p.ay, p.by) + margin
  for cy = math.floor(y0 / 32), math.floor(y1 / 32) do
    for cx = math.floor(x0 / 32), math.floor(x1 / 32) do
      surface.request_to_generate_chunks({x = cx * 32 + 16, y = cy * 32 + 16}, 0)
    end
  end
end

script.on_event(defines.events.on_script_path_request_finished, function(ev)
  local rec = storage.ea_path and storage.ea_path.ids[ev.id]
  if not rec then return end
  local st = storage.ea_path
  local pp = st.per_pair[rec.pair]
  if ev.try_again_later then
    st.retried = st.retried + 1
    pp.retried = pp.retried + 1
    st.ids[ev.id] = nil
    return
  end
  if ev.path then
    st.found = st.found + 1
    pp.found = pp.found + 1
    st.waypoints = st.waypoints + #ev.path
  else
    st.failed = st.failed + 1
    pp.failed = pp.failed + 1
  end
  st.ticks[#st.ticks + 1] = ev.tick - rec.sent
  st.ids[ev.id] = nil
end)

script.on_event(defines.events.on_tick, function(ev)
  local surface = game.surfaces[S("surface")]
  if not surface then return end
  if ev.tick == S("gen-tick") then
    for _, p in ipairs(pairs_list()) do generate(surface, p, S("margin")) end
    surface.force_generate_chunk_requests()
  end
  if ev.tick == S("send-tick") then
    local unit = prototypes.entity[S("unit")]
    storage.ea_path = {ids = {}, sent = 0, found = 0, failed = 0, retried = 0, waypoints = 0, ticks = {},
                       send_tick = ev.tick, per_pair = {}}
    local st = storage.ea_path
    for k, p in ipairs(pairs_list()) do
      -- each end moves to the nearest spot that can hold the unit (a tree or rock on the given tile would
      -- fail the request at once, which reads as a blocked end rather than a detour)
      local function at(x, y)
        local q = surface.find_non_colliding_position(unit.name, {x, y}, S("snap"), 0.25) or {x = x, y = y}
        return {x = q.x, y = q.y, moved = math.sqrt((q.x - x) ^ 2 + (q.y - y) ^ 2),
                placeable = surface.can_place_entity{name = unit.name, position = q, force = "enemy"},
                tile = surface.get_tile(q.x, q.y).name}
      end
      local a, b = at(p.ax, p.ay), at(p.bx, p.by)
      st.per_pair[k] = {found = 0, failed = 0, retried = 0, start = a, goal = b}
      for _ = 1, S("repeats") do
        local id = surface.request_path{bounding_box = unit.collision_box, collision_mask = unit.collision_mask,
                                        start = {x = a.x, y = a.y}, goal = {x = b.x, y = b.y}, force = "enemy",
                                        radius = 2, pathfind_flags = {cache = false}}
        st.ids[id] = {sent = ev.tick, pair = k}
        st.sent = st.sent + 1
      end
    end
  end
  if ev.tick == S("end-tick") and storage.ea_path then
    local st = storage.ea_path
    local pending = 0
    for _, rec in pairs(st.ids) do
      pending = pending + 1
      local pp = st.per_pair[rec.pair]
      pp.pending = (pp.pending or 0) + 1
    end
    local out = {format = "ea-path-probe/1", label = S("label"), sent = st.sent, found = st.found, failed = st.failed,
                 retried = st.retried, pending = pending, waypoints = st.waypoints, ticks = st.ticks,
                 send_tick = st.send_tick, end_tick = ev.tick, pairs = #pairs_list(), repeats = S("repeats"),
                 per_pair = st.per_pair}
    helpers.write_file("ea-path-probe/" .. S("label") .. ".json", helpers.table_to_json(out), false)
    log("ea-path-probe: wrote ea-path-probe/" .. S("label") .. ".json, sent " .. st.sent)
  end
end)
