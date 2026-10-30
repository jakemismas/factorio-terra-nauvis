-- ea-cc-probe/t12.lua (test-only, never shipped): T12's walker, saves and storage probe. tools/earth_test.py
-- (compat-completeness) appends this file to control.lua in a staged copy of the mod under test and writes
-- cc-spec.lua beside it, so the probe runs in the mod's own Lua state and can write that mod's storage:
--   walkers  every period ticks from start, each walker requests the chunks within radius of its next point
--            (never forced); a census of the walked chunks goes into the report
--   saves    game.server_save at the listed ticks, on a server only
--   storage  the mod's whole storage at storage_ticks, to <label>-storage-<tick>.json (TST-28: the
--            benchmark checksum ignores storage)
--   report   at report_tick: the walked chunks requested and generated, whether the save is multiplayer
--   bad      the recipe's positive control only: on every chunk event one extra tile write whose position
--            comes from a file-level counter, which a save and load cannot reproduce
--   planets  with Space Age, at planets_tick every other planet's surface is created and its chunks near the
--            origin requested, so the multiplayer recipe covers planet generation
-- Outputs: script-output/ea-cc-probe/<label>-report.json and <label>-storage-<tick>.json. The runner writes
-- only positions, ticks and flags into cc-spec.lua; the mod under test registers no on_tick handler and, with
-- its band-fix key absent, no on_chunk_generated handler, so the probe's registrations replace nothing.
do
  local spec = require("cc-spec")
  local base = "ea-cc-probe/" .. spec.label
  local bad_counter = 0

  if spec.bad then
    script.on_event(defines.events.on_chunk_generated, function(e)
      bad_counter = bad_counter + 1
      local x, y = e.position.x * 32 + bad_counter % 32, e.position.y * 32
      e.surface.set_tiles({{name = "water", position = {x, y}}}, false, true, true, false)
    end)
  end

  local function nauvis()
    return game.surfaces["nauvis"]
  end

  local function walk(tick)
    local rel = tick - spec.start
    if not spec.walkers or rel < 0 or rel % spec.period ~= 0 then
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

  local saves, storage_ticks = {}, {}
  for _, sv in ipairs(spec.saves or {}) do
    saves[sv.tick] = sv.name
  end
  for _, t in ipairs(spec.storage_ticks or {}) do
    storage_ticks[t] = true
  end

  -- planets (Space Age, multiplayer): at planets_tick every other planet's surface is created and its chunks within
  -- radius 2 of the origin are requested (never forced), so the recipe covers planet generation too
  local function planets(tick)
    if tick ~= spec.planets_tick or not game.planets then
      return
    end
    local made = {}
    for name, planet in pairs(game.planets) do
      if name ~= "nauvis" then
        local s = planet.surface or planet.create_surface()
        s.request_to_generate_chunks({0, 0}, 2)
        made[#made + 1] = name
      end
    end
    table.sort(made)
    helpers.write_file(base .. "-planets.json", helpers.table_to_json{tick = tick, planets = made}, false)
  end

  script.on_event(defines.events.on_tick, function(e)
    walk(e.tick)
    planets(e.tick)
    if storage_ticks[e.tick] then
      local copy = {}
      for k, v in pairs(storage) do
        copy[k] = v
      end
      helpers.write_file(base .. "-storage-" .. e.tick .. ".json", helpers.table_to_json(copy), false)
    end
    if e.tick == spec.report_tick then
      local want, have = walked()
      helpers.write_file(base .. "-report.json", helpers.table_to_json{
        tick = e.tick, walk_chunks = want, walk_generated = have, multiplayer = game.is_multiplayer()}, false)
    end
    local name = saves[e.tick]
    if name and game.is_multiplayer() then
      game.server_save(name)
    end
  end)
end
