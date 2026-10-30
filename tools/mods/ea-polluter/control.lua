-- ea-polluter: pollution at a site, so the nests round it attack, timed by the runner with
-- --benchmark-verbose all (pathFinder per tick). The chunks within `radius` of the site are generated
-- on gen-tick; on start-tick fuelled stone furnaces go down at the site (the targets attack groups
-- seek) and pollution is added there every `period` ticks; on end-tick the record is written: the
-- spawners, worms and units within `radius`, the units within a chunk of the site and the furnaces
-- still standing.
local P = "ea-polluter-"
local function S(n) return settings.startup[P .. n].value end

local function split(text, sep)
  local out = {}
  for part in string.gmatch(text or "", "[^" .. sep .. "]+") do out[#out + 1] = part end
  return out
end

local function site()
  local v = split(S("site"), ",")
  return {x = tonumber(v[1]) or 0, y = tonumber(v[2]) or 0}
end

local function count(surface, centre, radius, kind)
  return surface.count_entities_filtered{position = centre, radius = radius, type = kind}
end

local function census(surface, centre, radius)
  return {spawners = count(surface, centre, radius, "unit-spawner"), worms = count(surface, centre, radius, "turret"),
          units = count(surface, centre, radius, "unit"), units_at_site = count(surface, centre, 32, "unit")}
end

script.on_event(defines.events.on_tick, function(ev)
  local surface = game.surfaces[S("surface")]
  if not surface then return end
  local c = site()
  local r = S("radius")
  if ev.tick == S("gen-tick") then
    for cy = math.floor((c.y - r) / 32), math.floor((c.y + r) / 32) do
      for cx = math.floor((c.x - r) / 32), math.floor((c.x + r) / 32) do
        surface.request_to_generate_chunks({x = cx * 32 + 16, y = cy * 32 + 16}, 0)
      end
    end
    surface.force_generate_chunk_requests()
  elseif ev.tick == S("start-tick") then
    storage.ea_polluter = {before = census(surface, c, r), furnaces = {}, placed = 0, pulses = 0}
    local st = storage.ea_polluter
    local n = S("furnaces")
    for k = 0, n * 4 do
      if st.placed >= n then break end
      local pos = {x = c.x + (k % 8) * 3 - 12, y = c.y + math.floor(k / 8) * 3 - 6}
      if surface.can_place_entity{name = "stone-furnace", position = pos, force = "player"} then
        local e = surface.create_entity{name = "stone-furnace", position = pos, force = "player"}
        if e then
          e.insert{name = "coal", count = 50}
          e.insert{name = "iron-ore", count = 50}
          st.furnaces[#st.furnaces + 1] = e
          st.placed = st.placed + 1
        end
      end
    end
  elseif ev.tick > S("start-tick") and ev.tick < S("end-tick") then
    if (ev.tick - S("start-tick")) % S("period") == 0 then
      surface.pollute(c, S("amount"))
      storage.ea_polluter.pulses = storage.ea_polluter.pulses + 1
    end
  elseif ev.tick == S("end-tick") then
    local st = storage.ea_polluter or {}
    local standing = 0
    for _, e in ipairs(st.furnaces or {}) do
      if e.valid then standing = standing + 1 end
    end
    local rec = {label = S("label"), site = c, radius = r, before = st.before, after = census(surface, c, r),
                 furnaces_placed = st.placed, furnaces_standing = standing, pulses = st.pulses,
                 pollution_at_site = surface.get_pollution(c), tick = ev.tick}
    helpers.write_file("ea-polluter/" .. S("label") .. ".json", helpers.table_to_json(rec), false)
    log("ea-polluter: wrote " .. S("label") .. ".json")
  end
end)
