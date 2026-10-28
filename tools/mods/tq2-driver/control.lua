-- TQ2 driver, ported from the planning spike TQ2 (spikes/TQ2-benchmark at planning commit
-- 45c86d706c21) for tools/perf.py. Control stage only; test-only, never shipped. Changes against
-- the spike: the walk job (the benchmark-mode walker, test notes 5.6) and a final server save
-- at the end of the rtexplore job, so every loopback server run leaves its expected save file
-- (project rule 1's server clause).
--
-- One driver serves every metric: its job is read once, in on_init, from the runtime-global
-- setting tq2-mode and kept in storage, and tq2.py creates one save per job with the value set.
-- Fields are separated by ':'.
--   none
--   forced:<surface>:<bx>:<by>:<wx>:<wy>:<hist>
--       TQ1's timer (mod/spikes/TQ1-timing, tq1-gen): force-generate the warm-up chunk wx,wy at
--       tick 3, then at tick 5 request chunks bx..bx+15 x by..by+15 and time
--       force_generate_chunk_requests() with a LuaProfiler; census after the timed call.
--   explore:<surface>:<cx0>:<cy>:<R>:<K>:<P>:<D>:<T0>
--       From tick T0, every P ticks request one new column of 2R+1 chunks (x = cx0 + k, rows
--       cy-R..cy+R), K columns in all, asynchronously (never forced): a frontier moving east at
--       32/P tiles per tick. The window is ticks T0 .. T0+K*P+D-1; the census runs one tick
--       after it, so its cost stays outside the measured ticks.
--   save:<surface>:<bx>:<by>:<hist>
--       Server only: game.server_save("tq2-pre") at tick 60, the forced block at tick 61 (same as
--       forced, untimed), game.server_save("tq2-post") at tick 120.
--   rtexplore:<surface>:<cx0>:<cy>:<R>:<K>:<P>:<D>:<T0>
--       The explore job for a real-time loopback server: the same frontier and census, plus the wall
--       time between consecutive on_tick calls (a LuaProfiler restarted every tick) for every window
--       tick, appended to tq2/rt.txt. Benchmark runs tick as fast as they can, so they cannot show
--       whether work the map generator does off the main thread is hidden by real-time pacing.
--   walk:<surface>:<x0>:<y0>:<dx>:<dy>:<R>:<P>:<N>:<D>:<T0>
--       The benchmark-mode walker: from tick T0, every P ticks request the chunks within radius R
--       (chunks) of the point (x0 + k dx, y0 + k dy) in tiles, k = 0 .. N - 1, never forced; then D
--       drain ticks. A census of the requested chunks runs one tick after the window.
--   st:<surface>:<x0>:<y0>:<x1>:<y1>:<T>
--       New-map startup runs: at tick T (through on_nth_tick, so no per-tick handler runs before
--       it) census chunks x0..x1 x y0..y1, the start area, to prove the script mods painted it.
-- hist = 1 adds a per-name tile and tree histogram to the census (slow; untimed jobs only).
-- The on_tick handler is registered only while a job is pending, so a finished save carries no
-- per-tick handler into the steady-UPS benchmark.

local WARM_TICK, GEN_TICK = 3, 5
local SIDE = 16
local LAB = {"lab-dark-1", "lab-dark-2", "lab-white"}
-- factorio-world 2.1.6 terrain_codes without Alien Biomes (control.lua:6-19).
local FW_PALETTE = {"out-of-map", "deepwater", "deepwater-green", "water", "water-green", "grass-1",
  "grass-2", "grass-3", "dirt-3", "dirt-6", "sand-1", "sand-3"}

local function parse(spec)
  local p = {}
  for part in string.gmatch(spec, "[^:]+") do p[#p + 1] = part end
  local function n(i) return tonumber(p[i]) end
  local m = {spec = spec, kind = p[1] or "none"}
  if m.kind == "forced" then
    m.surface, m.bx, m.by, m.wx, m.wy, m.hist = p[2], n(3), n(4), n(5), n(6), p[7] == "1"
  elseif m.kind == "explore" or m.kind == "rtexplore" then
    m.surface, m.cx0, m.cy, m.R, m.K, m.P, m.D, m.T0 = p[2], n(3), n(4), n(5), n(6), n(7), n(8), n(9)
  elseif m.kind == "save" then
    m.surface, m.bx, m.by, m.hist = p[2], n(3), n(4), p[5] == "1"
  elseif m.kind == "walk" then
    m.surface, m.x0, m.y0, m.dx, m.dy, m.R, m.P, m.N, m.D, m.T0 = p[2], n(3), n(4), n(5), n(6), n(7), n(8), n(9),
      n(10), n(11)
  elseif m.kind == "st" then
    m.surface, m.x0, m.y0, m.x1, m.y1, m.T = p[2], n(3), n(4), n(5), n(6), n(7)
  else
    m.kind = "none"
  end
  return m
end

local function chunk_counts(s)
  local listed, generated = 0, 0
  for c in s.get_chunks() do
    listed = listed + 1
    if s.is_chunk_generated(c) then generated = generated + 1 end
  end
  return listed, generated
end

local function census(s, area, chunks, hist)
  local r = {}
  r.water_tiles = s.count_tiles_filtered{area = area, collision_mask = "water_tile"}
  r.lab_tiles = s.count_tiles_filtered{area = area, name = LAB}
  r.non_fw_palette_tiles = s.count_tiles_filtered{area = area, name = FW_PALETTE, invert = true}
  r.trees = s.count_entities_filtered{area = area, type = "tree"}
  r.rocks = s.count_entities_filtered{area = area, type = "simple-entity"}
  r.cliffs = s.count_entities_filtered{area = area, type = "cliff"}
  r.fish = s.count_entities_filtered{area = area, type = "fish"}
  r.spawners = s.count_entities_filtered{area = area, type = "unit-spawner"}
  r.worms = s.count_entities_filtered{area = area, type = "turret", force = "enemy"}
  r.units = s.count_entities_filtered{area = area, type = "unit"}
  r.enemies = s.count_entities_filtered{area = area, force = "enemy"}
  r.entities = s.count_entities_filtered{area = area}
  local by, amt, n = {}, {}, 0
  for _, e in pairs(s.find_entities_filtered{area = area, type = "resource"}) do
    n = n + 1
    by[e.name] = (by[e.name] or 0) + 1
    amt[e.name] = (amt[e.name] or 0) + e.amount
  end
  r.resources, r.resources_by_name, r.resource_amount_by_name = n, by, amt
  if chunks then
    local dec, dec_amount = 0, 0
    for _, c in pairs(chunks) do
      local list = s.find_decoratives_filtered{area = {{c[1] * 32, c[2] * 32}, {c[1] * 32 + 32, c[2] * 32 + 32}}}
      dec = dec + #list
      for _, d in pairs(list) do dec_amount = dec_amount + d.amount end
    end
    r.decoratives, r.decorative_amount = dec, dec_amount
  end
  if hist then
    local h = {}
    for name, _ in pairs(prototypes.tile) do
      local k = s.count_tiles_filtered{area = area, name = name}
      if k > 0 then h[name] = k end
    end
    r.tile_histogram = h
    local th = {}
    for _, e in pairs(s.find_entities_filtered{area = area, type = "tree"}) do th[e.name] = (th[e.name] or 0) + 1 end
    r.tree_histogram = th
  end
  return r
end

local function block_chunks(bx, by)
  local t = {}
  for cy = by, by + SIDE - 1 do
    for cx = bx, bx + SIDE - 1 do t[#t + 1] = {cx, cy} end
  end
  return t
end

local function count_generated(s, chunks)
  local n = 0
  for _, c in pairs(chunks) do
    if s.is_chunk_generated(c) then n = n + 1 end
  end
  return n
end

-- TQ1's timed block: the request loop and the blocking call each timed, then the census.
local function run_block(m, s, tag)
  local chunks = block_chunks(m.bx, m.by)
  local before = count_generated(s, chunks)
  local listed0, generated0 = chunk_counts(s)
  local pr = helpers.create_profiler()
  for _, c in pairs(chunks) do
    s.request_to_generate_chunks({c[1] * 32 + 16, c[2] * 32 + 16}, 0)
  end
  pr.stop()
  local pg = helpers.create_profiler()
  s.force_generate_chunk_requests()
  pg.stop()
  helpers.write_file("tq2/" .. tag .. ".txt", {"", "request ", pr, "\nforce ", pg, "\n"}, false)
  local after = count_generated(s, chunks)
  local listed1, generated1 = chunk_counts(s)
  local area = {{m.bx * 32, m.by * 32}, {(m.bx + SIDE) * 32, (m.by + SIDE) * 32}}
  local rec = census(s, area, chunks, m.hist)
  rec.tick, rec.surface, rec.spec = game.tick, s.name, m.spec
  rec.block_generated_before, rec.block_generated_after = before, after
  rec.listed_before, rec.generated_before = listed0, generated0
  rec.listed_after, rec.generated_after = listed1, generated1
  helpers.write_file("tq2/" .. tag .. ".json", helpers.table_to_json(rec), false)
end

local on_tick

local function finish()
  storage.done = true
  script.on_event(defines.events.on_tick, nil)
  if storage.m and storage.m.kind == "st" then script.on_nth_tick(storage.m.T, nil) end
end

local function forced_tick(m, s, tick)
  if tick == WARM_TICK then
    local listed, generated = chunk_counts(s)
    local p = helpers.create_profiler()
    s.request_to_generate_chunks({m.wx * 32 + 16, m.wy * 32 + 16}, 0)
    s.force_generate_chunk_requests()
    p.stop()
    helpers.write_file("tq2/warm.txt", {"", "warm ", p, "\n"}, false)
    helpers.write_file("tq2/warm.json", helpers.table_to_json{tick = tick, listed_before = listed,
      generated_before = generated, surface = s.name}, false)
  elseif tick == GEN_TICK then
    run_block(m, s, "gen")
    finish()
  end
end

local function explore_tick(m, s, tick)
  local st = storage.ex
  local rel = tick - m.T0
  if rel >= 0 and rel < m.K * m.P and rel % m.P == 0 then
    local k = math.floor(rel / m.P)
    local col = {k = k, req = tick, left = 0, n = 0}
    local cx = m.cx0 + k
    for cy = m.cy - m.R, m.cy + m.R do
      col.n = col.n + 1
      if s.is_chunk_generated({cx, cy}) then
        st.pre_generated = st.pre_generated + 1
      else
        col.left = col.left + 1
        st.pending[#st.pending + 1] = {cx, cy, k}
        s.request_to_generate_chunks({cx * 32 + 16, cy * 32 + 16}, 0)
      end
    end
    if col.left == 0 then col.done = tick end
    st.cols[k + 1] = col
    if k == 0 then
      st.window_start_tick = tick
      st.listed_start, st.generated_start = chunk_counts(s)
    end
  end
  if #st.pending > 0 then
    local keep = {}
    for _, p in ipairs(st.pending) do
      if s.is_chunk_generated({p[1], p[2]}) then
        local col = st.cols[p[3] + 1]
        col.left = col.left - 1
        if col.left == 0 then col.done = tick end
        st.generated_in_window = st.generated_in_window + 1
      else
        keep[#keep + 1] = p
      end
    end
    st.pending = keep
  end
  local last = m.T0 + m.K * m.P + m.D - 1
  if tick == last then
    st.window_end_tick = tick
    st.pending_at_window_end = #st.pending
    st.listed_end, st.generated_end = chunk_counts(s)
  elseif tick == last + 1 then
    local area = {{m.cx0 * 32, (m.cy - m.R) * 32}, {(m.cx0 + m.K) * 32, (m.cy + m.R + 1) * 32}}
    local band = {}
    for k = 0, m.K - 1 do
      for cy = m.cy - m.R, m.cy + m.R do band[#band + 1] = {m.cx0 + k, cy} end
    end
    local rec = census(s, area, nil, false)
    rec.band_chunks = #band
    rec.band_generated = count_generated(s, band)
    rec.spec, rec.surface, rec.census_tick = m.spec, s.name, tick
    rec.window_start_tick, rec.window_end_tick = st.window_start_tick, st.window_end_tick
    rec.pending_at_window_end, rec.generated_in_window = st.pending_at_window_end, st.generated_in_window
    rec.pre_generated = st.pre_generated
    rec.listed_start, rec.generated_start = st.listed_start, st.generated_start
    rec.listed_end, rec.generated_end = st.listed_end, st.generated_end
    local lat = {}
    for i, col in ipairs(st.cols) do lat[i] = col.done and (col.done - col.req) or -1 end
    rec.column_latency_ticks = lat
    helpers.write_file("tq2/explore.json", helpers.table_to_json(rec), false)
    finish()
  end
end

local function save_tick(m, s, tick)
  if tick == 60 then
    game.server_save("tq2-pre")
  elseif tick == 61 then
    run_block(m, s, "save-block")
  elseif tick == 120 then
    -- done is set before the save so the saved world carries no pending job and no on_tick handler
    finish()
    game.server_save("tq2-post")
    helpers.write_file("tq2/save-done.json", helpers.table_to_json{tick = tick}, false)
  end
end

local function st_tick(e)
  local m = storage.m
  if e.tick ~= m.T then return end
  local s = game.surfaces[m.surface]
  if not s then error("tq2-driver: no surface " .. tostring(m.surface)) end
  local chunks = {}
  for cy = m.y0, m.y1 do
    for cx = m.x0, m.x1 do chunks[#chunks + 1] = {cx, cy} end
  end
  local rec = census(s, {{m.x0 * 32, m.y0 * 32}, {(m.x1 + 1) * 32, (m.y1 + 1) * 32}}, nil, false)
  rec.area_chunks, rec.area_generated = #chunks, count_generated(s, chunks)
  rec.listed, rec.generated = chunk_counts(s)
  rec.tick, rec.spec, rec.surface = e.tick, m.spec, s.name
  helpers.write_file("tq2/st.json", helpers.table_to_json(rec), false)
  finish()
end

-- Runtime only, never in storage: one LuaProfiler per tick interval (restart() would keep counting,
-- so a new one is created each tick), buffered and written once per column period at phase 16,
-- a quiet tick, so the file writes stay off the measured intervals and off the heavy ticks.
local rt_prof, rt_buf = nil, {}

local function rt_flush()
  if #rt_buf == 0 then return end
  local outer, g = {""}, {""}
  for _, e in ipairs(rt_buf) do
    g[#g + 1] = tostring(e[1])
    g[#g + 1] = " "
    g[#g + 1] = e[2]
    g[#g + 1] = "\n"
    if #g >= 17 then
      outer[#outer + 1] = g
      g = {""}
    end
  end
  if #g > 1 then outer[#outer + 1] = g end
  helpers.write_file("tq2/rt.txt", outer, true)
  rt_buf = {}
end

local function rt_tick(m, tick)
  local last = m.T0 + m.K * m.P + m.D - 1
  if tick == m.T0 - 1 then
    helpers.write_file("tq2/rt.txt", "", false)
    rt_prof = helpers.create_profiler()
  elseif rt_prof and tick >= m.T0 and tick <= last then
    rt_prof.stop()
    rt_buf[#rt_buf + 1] = {tick, rt_prof}
    if (tick - m.T0) % m.P == 16 or tick == last then rt_flush() end
    rt_prof = helpers.create_profiler()
  end
end

-- The benchmark-mode walker (test notes 5.6): a point moving dx, dy tiles per step requests
-- the chunks within radius R around it every P ticks, never forced.
local function walk_tick(m, s, tick)
  local w = storage.walk
  local rel = tick - m.T0
  if rel >= 0 and rel < m.N * m.P and rel % m.P == 0 then
    local k = math.floor(rel / m.P)
    local x, y = m.x0 + k * m.dx, m.y0 + k * m.dy
    local cx, cy = math.floor(x / 32), math.floor(y / 32)
    for j = cy - m.R, cy + m.R do
      for i = cx - m.R, cx + m.R do
        local key = i .. "," .. j
        if not w.seen[key] then
          w.seen[key] = true
          w.chunks[#w.chunks + 1] = {i, j}
          if s.is_chunk_generated({i, j}) then w.pre_generated = w.pre_generated + 1 end
        end
      end
    end
    s.request_to_generate_chunks({x, y}, m.R)
    if k == 0 then
      w.window_start_tick = tick
      w.listed_start, w.generated_start = chunk_counts(s)
    end
  end
  local last = m.T0 + m.N * m.P + m.D - 1
  if tick == last then
    w.window_end_tick = tick
    w.listed_end, w.generated_end = chunk_counts(s)
  elseif tick == last + 1 then
    local rec = {spec = m.spec, surface = s.name, census_tick = tick, requested = #w.chunks,
      generated = count_generated(s, w.chunks), pre_generated = w.pre_generated,
      window_start_tick = w.window_start_tick, window_end_tick = w.window_end_tick,
      listed_start = w.listed_start, generated_start = w.generated_start,
      listed_end = w.listed_end, generated_end = w.generated_end}
    helpers.write_file("tq2/walk.json", helpers.table_to_json(rec), false)
    finish()
  end
end

on_tick = function(e)
  local m = storage.m
  local s = game.surfaces[m.surface]
  if not s then error("tq2-driver: no surface " .. tostring(m.surface)) end
  if m.kind == "forced" then
    forced_tick(m, s, e.tick)
  elseif m.kind == "explore" then
    explore_tick(m, s, e.tick)
  elseif m.kind == "rtexplore" then
    rt_tick(m, e.tick)
    explore_tick(m, s, e.tick)
    if storage.done and not storage.rt_saved then
      -- after the census, outside the measured window: the server clause's expected save file
      storage.rt_saved = true
      game.server_save("tq2-rt")
    end
  elseif m.kind == "walk" then
    walk_tick(m, s, e.tick)
  elseif m.kind == "save" then
    save_tick(m, s, e.tick)
  end
end

local function register()
  if storage.m and storage.m.kind == "st" and not storage.done then
    script.on_nth_tick(storage.m.T, st_tick)
  elseif storage.m and storage.m.kind ~= "none" and not storage.done then
    script.on_event(defines.events.on_tick, on_tick)
  end
end

script.on_init(function()
  storage.m = parse(settings.global["tq2-mode"].value)
  storage.done = false
  if storage.m.kind == "explore" or storage.m.kind == "rtexplore" then
    storage.ex = {pending = {}, cols = {}, pre_generated = 0, generated_in_window = 0}
  elseif storage.m.kind == "walk" then
    storage.walk = {seen = {}, chunks = {}, pre_generated = 0}
  end
  helpers.write_file("tq2/init.json", helpers.table_to_json{spec = storage.m.spec, kind = storage.m.kind,
    tick = game.tick, surfaces = (function() local t = {} for _, x in pairs(game.surfaces) do t[#t + 1] = x.name end return t end)()}, false)
  register()
end)

script.on_load(register)
