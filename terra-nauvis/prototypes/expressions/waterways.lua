-- Waterway expressions (ARCHITECTURE.md, "Expression inventory" and "Stable hooks"; contract 4).
--
-- Per map and scale, four named sets from the generated files (tools/build_waterways.py): the rivers,
-- straits and turning basins (ww), the canals, the dams and the fords. Each reads only its map's geo
-- tiles in the chain of the geography version that composes them (its `waterways` record), warped and
-- bound here to the locals X, Y, XP, YP, W, B and J, so they live in the Tile program alone (firewall rule);
-- that version's
-- elevation entry (coast.lua) picks the save's scale's ww, canal and dam sets by name through the
-- folded scale, and its preset points the ford key at the map's ford set for its scale, which the
-- water-shallow hook in data-final-fixes.lua reads behind the gate.
--
-- Also the shared bodies: the gate's and the ford key's prototypes, which hold their off values, and
-- the canals switch's two neutral bodies. Every name and number comes from config.lua (S-5).
local cfg = require("prototypes.config")

-- One require per generated file (the registration scan reads literal module names), by map, version of the
-- map's waterway files and scale. A geography version binds the files its waterway_files names, 1 when it names
-- none, so a river release moves one map's new worlds and no released body (ARCHITECTURE.md, "Release versioning
-- policy", rule 11). Each list runs in the order of the scale list of the record that names it.
local WV = cfg.waterways.versions
local FILES = {
  europe = {
    -- version 7 serves every offered scale from the first files (0.3.0 dropped version 6 and its scale extension)
    {
      require("prototypes.generated.waterways_europe_s1_v1"),
      require("prototypes.generated.waterways_europe_s2_v1"),
      require("prototypes.generated.waterways_europe_s3_v1"),
      require("prototypes.generated.waterways_europe_s4_v1"),
      require("prototypes.generated.waterways_europe_s5_v1"),
      require("prototypes.generated.waterways_europe_s6_v1"),
      require("prototypes.generated.waterways_europe_s12_v1"),
      require("prototypes.generated.waterways_europe_s24_v1"),
    },
  },
  atlantic = {
    [WV.atlantic] = {
      require("prototypes.generated.waterways_atlantic_s1_v2"),
      require("prototypes.generated.waterways_atlantic_s2_v2"),
      require("prototypes.generated.waterways_atlantic_s3_v2"),
      require("prototypes.generated.waterways_atlantic_s4_v2"),
      require("prototypes.generated.waterways_atlantic_s5_v2"),
      require("prototypes.generated.waterways_atlantic_s6_v2"),
      require("prototypes.generated.waterways_atlantic_s12_v2"),
      require("prototypes.generated.waterways_atlantic_s24_v2"),
    },
  },
  olde_world = {
    [WV.olde_world] = {
      require("prototypes.generated.waterways_olde_world_s1_v2"),
      require("prototypes.generated.waterways_olde_world_s2_v2"),
      require("prototypes.generated.waterways_olde_world_s3_v2"),
      require("prototypes.generated.waterways_olde_world_s4_v2"),
      require("prototypes.generated.waterways_olde_world_s5_v2"),
      require("prototypes.generated.waterways_olde_world_s6_v2"),
      require("prototypes.generated.waterways_olde_world_s12_v2"),
      require("prototypes.generated.waterways_olde_world_s24_v2"),
    },
  },
}

local H = cfg.hooks

local function files_of(key, g)
  return FILES[key][g.waterway_files or 1]
end

-- The scales a record serves: its own list, or the released list a landed version was built on.
local function scales_of(rec)
  return rec.scales or cfg.scales.released
end

local function num(v)
  return string.format(cfg.number_format, v)
end

-- A copy of a generated local function, so no two prototypes share one Lua table.
local function fn(f)
  local locals = {}
  for k, v in pairs(f.local_expressions or {}) do
    locals[k] = v
  end
  local params = {}
  for i, p in ipairs(f.parameters) do
    params[i] = p
  end
  return {parameters = params, expression = f.expression, local_expressions = locals}
end

-- The natural course (config.lua natural; design notes 2026-10-30): one warp of the geo tiles every set
-- of a version reads, so the fords stay on their rivers and the cost is a few noise evaluations per tile,
-- not per segment. Each octave is one basis noise per axis in geo tiles, anchored like the coast's detail,
-- so the same ground wanders the same way from every spawn. Rivers read X and Y, the whole warp; straits,
-- canals and dams read XP and YP, each octave at its passage share, so a passage keeps the places the
-- oracle tests. The warp fades out around the spawn, so a river stays where the river-safe starts measured
-- it. W is the rivers' low-frequency width modulation, B the fine bank noise of rivers and passages, which
-- only ever widens, so no floor moves (the river set of a geography low_bank lists takes low_bank's rows up to
-- its max_scale), J the rough edge of a ford, which would read as a bar across its river without it. T, the
-- rivers' source taper (a generated set of the sources), reads X and Y. Every local reads constants and x, y alone.
-- Whether geography version g is in a fine row's list, at a scale the row serves (min_scale, max_scale, above).
local function fine_row(row, g, scale, above)
  if not row then
    return false
  end
  local listed = false
  for _, id in ipairs(row.geographies) do
    listed = listed or id == g.geo_id
  end
  return listed and scale >= (row.min_scale or scale) and scale > (above or 0) and scale <= (row.max_scale or scale)
end

-- The fine meander (config.lua natural.warp_fine): rivers only, octaves fixed in tiles, so a bank bends between the
-- coarse octaves' bends. Named on as the warp rows' locals, so the warp bodies carry them.
local function fine_warp(N, g, scale, noise, locals, rx, ry)
  local WF = N.warp_fine
  if not fine_row(WF, g, scale) then
    return
  end
  for i, o in ipairs(WF.octaves) do
    local k = #N.warp + i
    local nx, ny = "wx" .. k, "wy" .. k
    locals[nx] = noise(o.seed1x, {o.wavelength_tiles, 0})
    locals[ny] = noise(o.seed1y, {o.wavelength_tiles, 0})
    rx[#rx + 1] = num(o.amplitude_tiles) .. " * " .. nx
    ry[#ry + 1] = num(o.amplitude_tiles) .. " * " .. ny
  end
end

-- The fine bank (config.lua natural.bank_fine): octaves fixed in tiles that only widen B. A scale the row does not
-- serve, and a version not listed, keep the bank as it was.
local function fine_bank(N, g, scale, noise, half)
  local BF = N.bank_fine
  if not fine_row(BF, g, scale) then
    return ""
  end
  local out = ""
  for _, o in ipairs(BF.octaves) do
    out = out .. " + " .. num(o.amplitude_tiles) .. " * (" .. half .. " + " .. half .. " * clamp(" ..
      noise(o.seed1, {o.wavelength_tiles, 0}) .. ", -1, 1))"
  end
  return out
end

-- The rough ford end past ford_edge.hold_above (config.lua natural.ford_fine): a ford's ends cross rivers 24 to 48
-- tiles wide there, and J alone left them near-straight lines across the water.
local function fine_ford(N, g, scale, noise)
  local FF = N.ford_fine
  if not fine_row(FF, g, scale, N.ford_edge.hold_above) then
    return ""
  end
  local out = ""
  for _, o in ipairs(FF.octaves) do
    out = out .. " + " .. num(o.amplitude_tiles) .. " * " .. noise(o.seed1, {o.wavelength_tiles, 0})
  end
  return out
end

local function natural_locals(g, mouth, scale, kind)
  local N = cfg.waterways.natural
  local s = cfg.keys.scale
  local function noise(seed1, wavelength)
    return "basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(seed1) .. ", input_scale = 1 / (" ..
      num(wavelength[1]) .. " + " .. num(wavelength[2]) .. " * " .. s .. "), offset_x = " .. g.cx ..
      ", offset_y = " .. g.cy .. "}"
  end
  local locals = {}
  local rx, ry, px, py = {}, {}, {}, {}
  for i, o in ipairs(N.warp) do
    local nx, ny = "wx" .. i, "wy" .. i
    local amp = "(" .. num(o.amplitude[1]) .. " + " .. num(o.amplitude[2]) .. " * " .. s .. ")"
    locals[nx] = noise(o.seed1x, o.wavelength)
    locals[ny] = noise(o.seed1y, o.wavelength)
    rx[i], ry[i] = amp .. " * " .. nx, amp .. " * " .. ny
    px[i] = num(o.passage) .. " * " .. rx[i]
    py[i] = num(o.passage) .. " * " .. ry[i]
  end
  fine_warp(N, g, scale, noise, locals, rx, ry)
  local F = N.spawn_fade
  local outer = math.max(F.outer_tiles, F.outer_per_scale * scale)
  locals.fade = "clamp((sqrt(x * x + y * y) - " .. num(F.inner_tiles) .. ") / " .. num(outer - F.inner_tiles) ..
    ", 0, 1)"
  local function warped(tile, parts, share)
    return tile .. " + fade * " .. (share or "") .. "(" .. table.concat(parts, " + ") .. ")"
  end
  -- A river keeps its polyline at the sea (generated mouth, natural.mouth), so Exact coastlines can shape a delta
  -- right up to it instead of leaving the coast fit there.
  locals.X, locals.Y = warped(g.gx, rx, mouth and "M * "), warped(g.gy, ry, mouth and "M * ")
  if mouth then
    locals.M = mouth
  end
  locals.XP, locals.YP = warped(g.gx, px), warped(g.gy, py)
  locals.W = "1 + " .. num(N.width.amplitude) .. " * clamp(" .. noise(N.width.seed1, N.width.wavelength) .. ", -1, 1)"
  local bank = N.bank
  local LB = N.low_bank
  if LB and kind == "ww" and scale <= LB.max_scale then
    for _, id in ipairs(LB.geographies) do
      if id == g.geo_id then
        bank = LB
      end
    end
  end
  local half = num(bank.half)
  local bn = noise(bank.seed1, bank.wavelength)
  if bank.gain then
    bn = num(bank.gain) .. " * " .. bn
  end
  locals.B = "(" .. num(bank.amplitude[1]) .. " + " .. num(bank.amplitude[2]) .. " * " .. s .. ") * (" .. half ..
    " + " .. half .. " * clamp(" .. bn .. ", -1, 1))"
  locals.B = locals.B .. fine_bank(N, g, scale, noise, half)
  local FE = N.ford_edge
  if scale > FE.hold_above then
    local h = FE.hold_above
    locals.J = num(FE.amplitude[1] + FE.amplitude[2] * h) .. " * " ..
      noise(FE.seed1, {FE.wavelength[1] + FE.wavelength[2] * h, 0})
  else
    locals.J = "(" .. num(FE.amplitude[1]) .. " + " .. num(FE.amplitude[2]) .. " * " .. s .. ") * " ..
      noise(FE.seed1, FE.wavelength)
  end
  locals.J = locals.J .. fine_ford(N, g, scale, noise)
  return locals
end

-- The warp a set reads through X, Y, XP and YP, as bodies of their own on a version that lists them (`warp`, four
-- names per scale in this order): a river's segment reads its point several times and a set holds near a thousand
-- segments, so the warp as locals was copied tens of thousands of times, at every start, for no change in the value.
local WARP_PARTS = {"X", "Y", "XP", "YP"}

local E = {}
-- The sets of one record, bound to the chain of geography version g, for every scale of the record's own list. A
-- record is the version, or its `extension`; a name list runs in the order of that list, so a scale reads its names
-- through its position there and is never a position itself.
local function emit_sets(key, g, rec)
    local sets = rec.waterways
    local files = files_of(key, rec)
    for pos, s in ipairs(scales_of(rec)) do
      local gen = files[pos]
      if not gen then
        error("waterways.lua has no generated file for " .. key .. " at scale " .. s)
      end
      -- The mouth share is a body of its own, not a local: the game copies a local into every seg() and box() call
      -- that reads it through X or Y, near a thousand a set, which cost 6.8 seconds at every start.
      local mouth = rec.mouths and rec.mouths[pos]
      if mouth then
        E[#E + 1] = {type = "noise-expression", name = mouth, expression = gen.mouth,
                     local_expressions = {X0 = g.gx, Y0 = g.gy}}
      end
      local warp
      if rec.warp then
        warp = {}
        local full = natural_locals(g, mouth, s)
        local inner = {M = full.M, fade = full.fade}
        for k, v in pairs(full) do
          if k:match("^w[xy]%d") then
            inner[k] = v
          end
        end
        for k, part in ipairs(WARP_PARTS) do
          warp[part] = rec.warp[(pos - 1) * #WARP_PARTS + k]
          E[#E + 1] = {type = "noise-expression", name = warp[part], expression = full[part], local_expressions = inner}
        end
      end
      local function set(kind, expression, functions)
        local name = sets[kind][pos]
        local locals = natural_locals(g, (kind == "ww" or kind == "fords") and mouth, s, kind)
        if warp then
          local kept = {W = locals.W, B = locals.B, J = locals.J}
          for part, body in pairs(warp) do
            kept[part] = body
          end
          locals = kept
        end
        if kind == "ww" then
          locals.T = gen.taper
        end
        local lf = {}
        for _, f in ipairs(functions) do
          lf[f] = fn(gen.functions[f])
        end
        E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals,
                     local_functions = lf}
      end
      set("ww", gen.ww, {"seg"})
      set("canals", gen.canals, {"seg"})
      set("dams", gen.dams, {"seg"})
      set("fords", gen.fords, {"box"})
    end
end

for _, key in ipairs(cfg.map_order) do
  local versions = (cfg.geography[key] or {}).versions or {}
  for _, g in ipairs(versions) do
    -- a thin version reads the older version's sets by name
    if g.waterways and not g.over then
      emit_sets(key, g, g)
      local X = cfg.scale_extensions[key]
      if X and X.geo_id == g.geo_id then
        emit_sets(key, g, X)
      end
    end
  end
end

-- The hook gate and the ford key hold their off values; Earth presets set the gate and point the key at
-- the map's ford set (ARCHITECTURE.md, "Stable hooks"). The canals switch's neutral bodies.
E[#E + 1] = {type = "noise-expression", name = cfg.keys.on, expression = num(H.gate_off)}
E[#E + 1] = {type = "noise-expression", name = H.fords.key, expression = H.fords.off}
E[#E + 1] = {type = "noise-expression", name = cfg.neutral.one, expression = num(H.gate_on)}
E[#E + 1] = {type = "noise-expression", name = cfg.neutral.zero, expression = num(H.gate_off)}

data:extend(E)

-- coast.lua's entry of a version with waterways: the waterway composition wrapped around the rest of
-- the version's composition (ARCHITECTURE.md, "Elevation composition", steps 5 and 6). Dams come
-- first, so a dam never closes a named waterway; both come after the rest of the version's
-- composition, so no lake of an earlier step reopens a dammed isthmus, and min() makes the carves
-- and lakes order-free. Each set is picked by name through the folded scale, so only the save's
-- scale's sets compile, and the canals switch compiles only its selected branch (S4: Tile 19,620 off
-- and 20,161 on at scale 1). Beside the dams, the map's ponds (tools/build_waterways.py river_ponds): land
-- over the fit's own discs on a river's course, inline text per scale, so a carve still cuts them.
local M = {}

-- A released version's list is frozen, so this text is too: the last value takes the else branch, which is why a
-- scale past a released version's list reads that version's scale 6 sets.
local function by_scale(names, values)
  local text = names[#values]
  for i = #values - 1, 1, -1 do
    text = "if(" .. cfg.keys.scale .. " == " .. num(values[i]) .. ", " .. names[i] .. ", " .. text .. ")"
  end
  return text
end

-- rec: the version, or its extension, which supplies the sets and the scale list; g the version whose chain they read.
function M.composition(rec, previous, key, g)
  local sets = rec.waterways
  if not sets then
    error("a waterways composition needs the version's waterway sets")
  end
  local on = cfg.keys.canals .. " > " .. num(H.threshold)
  local values = scales_of(rec)
  local ponds = {}
  for pos in ipairs(values) do
    ponds[pos] = files_of(key, rec)[pos].ponds
  end
  return "min(max(" .. previous .. ", dam, ponds), carve, canal)", {
    dam = "if(" .. on .. ", -inf, " .. by_scale(sets.dams, values) .. ")",
    ponds = by_scale(ponds, values),
    carve = by_scale(sets.ww, values),
    canal = "if(" .. on .. ", " .. by_scale(sets.canals, values) .. ", inf)",
    X = g.gx,
    Y = g.gy,
  }
end

return M
