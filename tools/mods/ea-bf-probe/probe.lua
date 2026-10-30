-- ea-bf-probe (test-only, never shipped): the coast-band-fix checks' probe. tools/earth_test.py appends
-- this file to control.lua in a staged copy of the mod under test and writes bf-spec.lua beside it, so the
-- probe runs in the mod's own Lua state, after control.lua's main chunk and before on_init or on_load:
--   timer    wraps the band-fix module's handler in a LuaProfiler (registration reads the module field
--            later, so the wrapper is what gets registered) and keeps, per tick that delivered chunk
--            events, the events, the chunks written, the tiles written and the summed handler time
--   walkers  every period ticks from start, each walker requests the chunks within radius of its next
--            point (never forced), then drain ticks
--   saves    game.server_save at the listed ticks, on a server only
--   report   at report_tick: whether on_chunk_generated has a handler, the save's band-fix state and key,
--            the tiles the listed chunks would still need (the recheck: 0 once the handler ran), and the
--            walk's chunk counts; storage.earth at storage_ticks
--   neutral  the base of bf_off: the band fix stubbed out (its on_init, on_load and drift line do nothing)
--   other    design constraint 4: at other.tick a second surface with Nauvis's own map gen settings (key
--            included) generates the recheck chunks; the report gives the chunk events the handler saw
--            there, the tiles it says it wrote there, and the tiles of those chunks where the two
--            surfaces differ (0 with the key absent; with it on, exactly the tiles written on Nauvis)
--   bad      T12's positive control only: one extra tile write per chunk event from a file-level counter,
--            which a save and load cannot reproduce
-- Outputs: script-output/ea-bf-probe/<label>-report.json, -timer.txt ("<tick> <events> <chunks written>
-- <tiles> Duration: <ms>ms" per line), -storage-<tick>.json. Every Earth name comes from the mod's own
-- config.lua; the runner writes only positions, ticks and flags into bf-spec.lua.
do
  local spec = require("bf-spec")
  local probe_cfg = require("prototypes.config")
  local bf = require("scripts.bandfix")
  local base = "ea-bf-probe/" .. spec.label
  local timer_lines, timer_out, truncated = {}, base .. "-timer.txt", false
  local acc, acc_tick, acc_events, acc_chunks, acc_tiles = nil, nil, 0, 0, 0
  local bad_counter = 0

  local function close_tick()
    if acc then
      timer_lines[#timer_lines + 1] = {"", acc_tick, " ", acc_events, " ", acc_chunks, " ", acc_tiles, " ", acc, "\n"}
    end
    acc = nil
  end

  local function flush_timer()
    close_tick()
    if #timer_lines == 0 then
      return
    end
    local outer, group = {""}, {""}
    for _, line in ipairs(timer_lines) do
      group[#group + 1] = line
      if #group >= 16 then
        outer[#outer + 1] = group
        group = {""}
        if #outer >= 16 then
          helpers.write_file(timer_out, outer, truncated)
          truncated = true
          outer = {""}
        end
      end
    end
    if #group > 1 then
      outer[#outer + 1] = group
    end
    if #outer > 1 then
      helpers.write_file(timer_out, outer, truncated)
      truncated = true
    end
    timer_lines = {}
  end

  if spec.timer then
    local inner = bf.on_chunk_generated
    bf.on_chunk_generated = function(e)
      local p = helpers.create_profiler()
      local n = inner(e) or 0
      p.stop()
      if e.tick ~= acc_tick then
        close_tick()
        acc, acc_tick, acc_events, acc_chunks, acc_tiles = helpers.create_profiler(true), e.tick, 0, 0, 0
      end
      acc.add(p)
      acc_events = acc_events + 1
      if n > 0 then
        acc_chunks = acc_chunks + 1
        acc_tiles = acc_tiles + n
      end
      return n
    end
  end

  local other_events, other_written = 0, 0
  if spec.other then
    local inner = bf.on_chunk_generated
    bf.on_chunk_generated = function(e)
      local n = inner(e) or 0
      if e.surface.name ~= "nauvis" then
        other_events = other_events + 1
        other_written = other_written + n
      end
      return n
    end
  end

  -- the base for T11's "byte-identical" row: the same build with the band fix stubbed out
  if spec.neutral then
    bf.on_init = function() end
    bf.on_configuration_changed = function() end
    script.on_load(function() end)
  end

  if spec.bad then
    local inner = bf.on_chunk_generated
    bf.on_chunk_generated = function(e)
      inner(e)
      bad_counter = bad_counter + 1
      local x, y = e.position.x * 32 + bad_counter % 32, e.position.y * 32
      e.surface.set_tiles({{name = "water", position = {x, y}}}, false, true, true, false)
    end
  end

  local function nauvis()
    return game.surfaces["nauvis"]
  end

  local function walk(tick)
    if not spec.walkers then
      return
    end
    local rel = tick - spec.start
    if rel < 0 or rel % spec.period ~= 0 then
      return
    end
    local k = rel / spec.period + 1
    local s = nauvis()
    for _, w in ipairs(spec.walkers) do
      local p = w.points[k]
      if p then
        s.request_to_generate_chunks({p[1], p[2]}, w.radius)
      end
    end
  end

  local function make_other(tick)
    if not (spec.other and tick == spec.other.tick) then
      return
    end
    local o = game.create_surface(spec.other.name, nauvis().map_gen_settings)
    for _, c in ipairs(spec.recheck or {}) do
      o.request_to_generate_chunks({c[1] * 32 + 16, c[2] * 32 + 16}, 0)
    end
    o.force_generate_chunk_requests()
  end

  -- tiles of the recheck chunks where the other surface differs from Nauvis; nil when it lacks one of them
  local function other_differs(s, o)
    local n = 0
    for _, c in ipairs(spec.recheck or {}) do
      if not (o.is_chunk_generated({c[1], c[2]}) and s.is_chunk_generated({c[1], c[2]})) then
        return nil
      end
      for y = c[2] * 32, c[2] * 32 + 31 do
        for x = c[1] * 32, c[1] * 32 + 31 do
          if s.get_tile(x, y).name ~= o.get_tile(x, y).name then
            n = n + 1
          end
        end
      end
    end
    return n
  end

  local function walked()
    local s = nauvis()
    local want, have = 0, 0
    for _, w in ipairs(spec.walkers or {}) do
      for _, p in ipairs(w.points) do
        local cx, cy = math.floor(p[1] / 32), math.floor(p[2] / 32)
        for j = cy - w.radius, cy + w.radius do
          for i = cx - w.radius, cx + w.radius do
            want = want + 1
            if s.is_chunk_generated({i, j}) then
              have = have + 1
            end
          end
        end
      end
    end
    return want, have
  end

  local function report(tick)
    local s = nauvis()
    local pen = s and s.map_gen_settings.property_expression_names or {}
    local pending, rechecked = 0, 0
    for _, c in ipairs(spec.recheck or {}) do
      if s.is_chunk_generated({c[1], c[2]}) then
        pending = pending + bf.pending(s, c[1], c[2])
        rechecked = rechecked + 1
      end
    end
    local want, have = walked()
    local earth = storage.earth
    local rec = {tick = tick, registered = script.get_event_handler(defines.events.on_chunk_generated) ~= nil,
                 key = pen[probe_cfg.bandfix.key], state = earth and earth.bandfix or "none",
                 pending = pending, rechecked = rechecked, walk_chunks = want, walk_generated = have,
                 multiplayer = game.is_multiplayer()}
    local o = spec.other and game.surfaces[spec.other.name]
    if o then
      local op = 0
      for _, c in ipairs(spec.recheck or {}) do
        if o.is_chunk_generated({c[1], c[2]}) then
          op = op + bf.pending(o, c[1], c[2])
        end
      end
      rec.other = {events = other_events, written = other_written, pending = op,
                   differs = other_differs(s, o) or "missing"}
    end
    helpers.write_file(base .. "-report.json", helpers.table_to_json(rec), false)
  end

  local saves, storage_ticks = {}, {}
  for _, sv in ipairs(spec.saves or {}) do
    saves[sv.tick] = sv.name
  end
  for _, t in ipairs(spec.storage_ticks or {}) do
    storage_ticks[t] = true
  end

  script.on_event(defines.events.on_tick, function(e)
    walk(e.tick)
    make_other(e.tick)
    if spec.timer and e.tick % 60 == 0 then
      flush_timer()
    end
    if storage_ticks[e.tick] then
      helpers.write_file(base .. "-storage-" .. e.tick .. ".json", helpers.table_to_json(storage.earth or {}), false)
    end
    if e.tick == spec.report_tick then
      flush_timer()
      report(e.tick)
    end
    local name = saves[e.tick]
    if name and game.is_multiplayer() then
      flush_timer()
      game.server_save(name)
    end
  end)
end
