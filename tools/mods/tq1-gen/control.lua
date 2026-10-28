-- TQ1's generation timer, ported from the planning spike TQ1 (spikes/TQ1-timing at planning commit
-- 45c86d706c21) for tools/perf.py (T15b, test notes 5.4). Test-only, never shipped.
-- Force-generate one 16 x 16 chunk block and time the blocking call with a LuaProfiler (main-thread
-- wall time; the map generator's worker threads do the work). The timed path is the spike's; the
-- one change is that the block and the warm-up chunk come from the runtime-global setting
-- tq1-gen-block ("bx:by:wx:wy", read once in on_init into storage), so perf.py can place a map's
-- block in geo coordinates through the spawn offset. The default is TQ1b's block 64..79 x 32..47.
local SIDE = 16
local WARM_TICK, GEN_TICK = 3, 5

local function parse(spec)
  local p = {}
  for part in string.gmatch(spec, "[^:]+") do p[#p + 1] = tonumber(part) end
  return {bx = p[1], by = p[2], wx = p[3], wy = p[4], spec = spec}
end

local function counts(s)
  local listed, generated = 0, 0
  for c in s.get_chunks() do
    listed = listed + 1
    if s.is_chunk_generated(c) then generated = generated + 1 end
  end
  return listed, generated
end

local function block_generated(s, b)
  local n = 0
  for cy = b.by, b.by + SIDE - 1 do
    for cx = b.bx, b.bx + SIDE - 1 do
      if s.is_chunk_generated({cx, cy}) then n = n + 1 end
    end
  end
  return n
end

script.on_init(function()
  storage.block = parse(settings.global["tq1-gen-block"].value)
  helpers.write_file("tq1/init.json", helpers.table_to_json{spec = storage.block.spec, tick = game.tick}, false)
end)

script.on_event(defines.events.on_tick, function(e)
  local b = storage.block
  if not b or e.tick > GEN_TICK then return end
  local s = game.surfaces.nauvis
  if e.tick == WARM_TICK then
    local listed, generated = counts(s)
    local p = helpers.create_profiler()
    s.request_to_generate_chunks({b.wx * 32 + 16, b.wy * 32 + 16}, 0)
    s.force_generate_chunk_requests()
    p.stop()
    helpers.write_file("tq1/warm.txt", {"", "warm ", p, "\n"}, false)
    helpers.write_file("tq1/warm.json", helpers.table_to_json{tick = e.tick, listed_before = listed,
      generated_before = generated}, false)
  elseif e.tick == GEN_TICK then
    local before = block_generated(s, b)
    local listed0, generated0 = counts(s)
    local pr = helpers.create_profiler()
    for cy = b.by, b.by + SIDE - 1 do
      for cx = b.bx, b.bx + SIDE - 1 do
        s.request_to_generate_chunks({cx * 32 + 16, cy * 32 + 16}, 0)
      end
    end
    pr.stop()
    local pg = helpers.create_profiler()
    s.force_generate_chunk_requests()
    pg.stop()
    helpers.write_file("tq1/gen.txt", {"", "request ", pr, "\nforce ", pg, "\n"}, false)
    local after = block_generated(s, b)
    local listed1, generated1 = counts(s)
    local area = {{b.bx * 32, b.by * 32}, {(b.bx + SIDE) * 32, (b.by + SIDE) * 32}}
    helpers.write_file("tq1/gen.json", helpers.table_to_json{
      tick = e.tick, block = b.spec, block_generated_before = before, block_generated_after = after,
      listed_before = listed0, generated_before = generated0,
      listed_after = listed1, generated_after = generated1,
      water_tiles = s.count_tiles_filtered{area = area, collision_mask = "water_tile"},
      resources = s.count_entities_filtered{area = area, type = "resource"},
      trees = s.count_entities_filtered{area = area, type = "tree"},
      rocks = s.count_entities_filtered{area = area, type = "simple-entity"},
      cliffs = s.count_entities_filtered{area = area, type = "cliff"},
      enemies = s.count_entities_filtered{area = area, force = "enemy"},
    }, false)
  end
end)
