-- ea-region-probe: named noise expressions read with calculate_tile_properties, no chunk generated.
-- Points and grids are given in geo tiles; the probe reads the spawn offset in the game and reads
-- each position at world = geo - offset, so a check never needs the offset beforehand.
local P = "ea-region-probe-"
local function S(n) return settings.startup[P .. n].value end
local BATCH = 64

local function split(text, sep)
  local out = {}
  for part in string.gmatch(text or "", "[^" .. sep .. "]+") do out[#out + 1] = part end
  return out
end

local function names_of(text)
  local out = {}
  for _, n in ipairs(split(text, ",")) do
    local t = n:gsub("^%s+", ""):gsub("%s+$", "")
    if t ~= "" then out[#out + 1] = t end
  end
  return out
end

-- {name = {values...}} over positions, in groups of names; an unknown name comes back absent.
local function read(surface, names, positions)
  local out = {}
  for i = 1, #names, BATCH do
    local part = {}
    for j = i, math.min(#names, i + BATCH - 1) do part[#part + 1] = names[j] end
    local got = surface.calculate_tile_properties(part, positions)
    for _, n in ipairs(part) do out[n] = got[n] end
  end
  return out
end

local function at_origin(surface, names)
  local out = {}
  if #names == 0 then return out end
  local got = read(surface, names, {{x = 0, y = 0}})
  for _, n in ipairs(names) do out[n] = got[n] and got[n][1] or "unrecognized" end
  return out
end

local function finite(v)
  return v == v and v ~= math.huge and v ~= -math.huge
end

local function grid(surface, spec, ox, oy)
  local parts = split(spec, "|")
  local g = split(parts[2] or "", ",")
  local x0, y0, step, nx, ny = tonumber(g[1]), tonumber(g[2]), tonumber(g[3]), tonumber(g[4]), tonumber(g[5])
  local mode, names = parts[3] or "raw", names_of(parts[4] or "")
  local out = {label = parts[1], x0 = x0, y0 = y0, step = step, nx = nx, ny = ny, mode = mode, names = names,
               values = {}, ones = {}, nonfinite = {}, recognised = {}}
  for _, n in ipairs(names) do
    out.values[n], out.ones[n], out.nonfinite[n], out.recognised[n] = {}, 0, 0, true
  end
  for j = 0, ny - 1 do
    local positions = {}
    for i = 0, nx - 1 do positions[i + 1] = {x = x0 + i * step - ox, y = y0 + j * step - oy} end
    local got = read(surface, names, positions)
    for _, n in ipairs(names) do
      local vals = got[n]
      if not vals then
        out.recognised[n] = false
      elseif mode == "sign" then
        local runs, cur, cnt = {}, nil, 0
        for i = 1, nx do
          local v, b = vals[i], 2
          if finite(v) then
            b = v > 0 and 1 or 0
          end
          if b == 1 then out.ones[n] = out.ones[n] + 1 elseif b == 2 then out.nonfinite[n] = out.nonfinite[n] + 1 end
          if b == cur then
            cnt = cnt + 1
          else
            if cur then runs[#runs + 1] = cur .. "*" .. cnt end
            cur, cnt = b, 1
          end
        end
        runs[#runs + 1] = cur .. "*" .. cnt
        out.values[n][j + 1] = table.concat(runs, " ")
      else
        out.values[n][j + 1] = vals
      end
    end
  end
  return out
end

script.on_event(defines.events.on_tick, function(ev)
  if ev.tick ~= S("tick") then return end
  local surface = game.surfaces[S("surface")]
  if not surface then
    log("ea-region-probe: no surface " .. S("surface"))
    return
  end
  local offset = names_of(S("offset"))
  local ox, oy = 0, 0
  local off = at_origin(surface, offset)
  if #offset == 2 then
    ox, oy = off[offset[1]], off[offset[2]]
    if type(ox) ~= "number" or type(oy) ~= "number" then
      log("ea-region-probe: the offset names did not resolve")
      return
    end
  end
  local out = {format = "ea-region-probe/1", label = S("label"), tick = ev.tick, surface = surface.name,
               seed = surface.map_gen_settings.seed, active_mods = script.active_mods,
               offset = {names = offset, x = ox, y = oy}, constants = at_origin(surface, names_of(S("constants"))),
               names = names_of(S("names")), points = {}, grids = {}}
  local pts = {}
  for _, a in ipairs(split(S("points"), ";")) do
    local v = split(a, ",")
    if #v >= 2 then pts[#pts + 1] = {x = tonumber(v[1]), y = tonumber(v[2])} end
  end
  if #pts > 0 and #out.names > 0 then
    local positions = {}
    for i, p in ipairs(pts) do positions[i] = {x = p.x - ox, y = p.y - oy} end
    local got = read(surface, out.names, positions)
    for i, p in ipairs(pts) do
      local vals = {}
      for j, n in ipairs(out.names) do vals[j] = got[n] and got[n][i] or "unrecognized" end
      out.points[i] = {x = p.x, y = p.y, values = vals}
    end
  end
  for _, spec in ipairs(split(S("grids"), ";")) do
    out.grids[#out.grids + 1] = grid(surface, spec, ox, oy)
  end
  helpers.write_file("ea-region-probe/" .. S("label") .. ".json", helpers.table_to_json(out), false)
  log("ea-region-probe: wrote ea-region-probe/" .. S("label") .. ".json, points " .. #out.points .. ", grids " ..
      #out.grids)
end)
