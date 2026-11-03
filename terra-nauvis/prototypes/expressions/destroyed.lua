-- Destroyed Europe (ARCHITECTURE.md, "Region layer" and contract 10;
-- APPROVALS 10; D12; S3 section 6; R3 7.1).
--
-- The zone reads one region-layer interface name, tn_destroyed_depth: the outline of
-- data-src/approvals/destroyed-zone.json less its keep rows (Britain, Denmark and the Carpathians), in tiles.
-- Each seed moves the outline's vertices and warps its edges harder than the shared warp, the same way on
-- every map. No region formula lives here (the static
-- regions row fails one outside regions.lua). The zone is cut by the start disc around the spawn, which the
-- spawn shift keeps at the origin on every map, so every spawn city, the zone's included, starts on normal
-- ground with normal trees (T7). Its heat climbs from a heat-1 rim to a core that mixes Alien Biomes' four
-- heat bands (R3 7.1), and the Alien Biomes temperature's next version lifts the zone to it, so AB's
-- volcanic tiles, its lava decals, volcanic rocks and the volcanic tree follow. Past the rim, which keeps
-- the climate's temperature and trees, a class per tile mixes those with black ash, red rock and red
-- grass (2026-10-30 16:35; config.lua destroyed.chaos); nothing else changes (APPROVALS 10).
-- The lift sits behind the toggle tn_destroyed, a name switch whose folded if()
-- compiles climate-tiles' first temperature alone when off (U5). Without Alien Biomes nothing here is
-- named by any preset: the toggle bakes off at the data stage and the presets keep the fallback climate
-- (FEAS-17), so the world equals the zone off. Every body is analytic in x, y, map_seed and per-save
-- numbers: firewall-clean, as the region layer is, so the Entity program, where Alien Biomes' trees read
-- temperature, may read it. Every number comes from config.lua's destroyed group (S-5).
--
-- All of the above is what a world made on 0.1.0 and 0.1.1 keeps. A new world with the zone on names the barrier's heat
-- and class in place of those names (bottom of this file). Those read a second outline with no start cut, whose depth
-- counts land edges alone (config.lua destroyed.outline): a barrier of wasteland where the zone meets land, a heart of
-- heat ground past it, and the zone runs to the shore on every sea side.
local cfg = require("prototypes.config")

local AB = mods["alien-biomes"] ~= nil

local D = cfg.destroyed
local N = D.names
local DEPTH = cfg.regions.names.destroyed_depth
local K = cfg.keys

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The zone in tiles: positive inside, never inside the start disc (the zone's own start mask), whose edge
-- the fine noise moves outward only, so the start stays safe and its edge is no circle. The sign is the one
-- that adds to the heat lift's fray: the other cancels it, and the lift's edge round the start comes out round.
def(N.zone, "min(" .. DEPTH .. ", " .. D.start.distance .. " - max(" .. num(D.start.radius_tiles) ..
  ", starting_area_radius) - " .. num(D.start.warp_tiles) .. " * (1 - clamp(" .. N.fine .. ", -1, 1)))")

-- The fine noise, one named field: the heat mixes the core's bands with it, and the palette reads it too.
local H = D.heat
local NZ = H.noise
def(N.fine, "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(NZ.seed1) .. ", octaves = " ..
  num(NZ.octaves) .. ", persistence = " .. num(NZ.persistence) .. ", input_scale = 1 / " ..
  num(NZ.wavelength_tiles) .. ", output_scale = 1}")

-- The heat inside the zone, from lift_px in, frayed by the fine noise, so the rim keeps the climate's
-- temperature and its trees and plants: it climbs to rim + ramp, and the noise mixes the core's bands.
local function heat_over(zone)
  return "if(" .. zone .. " + " .. K.scale .. " * (" .. num(H.lift_fray_px) .. " * " .. N.fine .. " - " ..
    num(H.lift_px) .. ") > 0, clamp(" .. num(H.rim) .. " + min(" .. num(H.per_tile) .. " * " .. zone .. ", " ..
    num(H.ramp) .. ") + " .. num(NZ.amplitude) .. " * " .. N.fine .. ", " .. num(H.rim) .. ", " .. num(H.cap) ..
    "), -inf)"
end
def(N.heat, heat_over(N.zone))

-- 0.3.1: the Moscow zone's level and the Europe key (config.lua moscow), at a world's off values on every load: a
-- world made before never names the bodies that read them.
local MZ = cfg.moscow
def(MZ.key, "0")
def(MZ.europe.key, num(MZ.europe.on))

-- The Alien Biomes temperature's next version (design rule 21: climate-tiles' first stays defined, unchanged):
-- the zone's heat where it is hotter, with the toggle on. It reads AB's controls through the first
-- version, so it exists only with Alien Biomes, as that one does.
if AB then
  local T1 = cfg.climate.names.ab.temperature
  def(N.temperature, "if(" .. K.destroyed .. " > " .. num(D.switch_threshold) .. ", max(" .. T1 .. ", " .. N.heat ..
    "), " .. T1 .. ")")

  -- The red palette (config.lua destroyed.chaos): one class per tile, and a score per palette tile that
  -- data-final-fixes.lua takes the max with. Tile scores alone read these, and with the toggle off the
  -- score folds to -inf, which max() leaves the tile's own score.
  local C = D.chaos
  local function noise(P)
    return "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(P.seed1) .. ", octaves = " ..
      num(P.octaves) .. ", persistence = " .. num(P.persistence) .. ", input_scale = 1 / (" ..
      num(P.wavelength_px) .. " * " .. K.scale .. "), output_scale = 1}"
  end
  def(C.names.macro, noise(C.macro))
  def(C.names.kind, noise(C.kind))
  local G = C.grass
  local L = {}
  for _, t in ipairs(C.tiles) do
    L[t.tile] = num(t.class)
  end
  local T = C.tile
  local rock = "if(" .. C.names.kind .. " < " .. num(C.black_below) .. ", if(" .. N.fine .. " > 0, " ..
    L[T.black_sand] .. ", " .. L[T.black_dirt] .. "), if(" .. N.fine .. " > 0, " .. L[T.red_sand] .. ", " ..
    L[T.red_dirt] .. "))"
  def(C.names.class, "if(depth <= 0, 0, if(reach < " .. num(C.rim_px) .. ", if(depth * " .. num(G.per_px) .. " + " ..
    num(G.fine) .. " * " .. N.fine .. " > " .. num(G.cut) .. ", " .. L[T.grass] .. ", 0), if(reach < " ..
    num(C.mid_px) .. ", " .. rock .. ", 0)))", {
      depth = N.zone .. " / " .. K.scale,
      reach = "min(depth, " .. num(C.sat_px) .. ") + " .. num(C.mac_px) .. " * " .. C.names.macro,
    })
  for _, t in ipairs(C.tiles) do
    def(t.body, "if(" .. K.destroyed .. " > " .. num(D.switch_threshold) .. ", if(elevation > 0, if(" ..
      C.names.class .. " == " .. num(t.class) .. ", " .. num(C.score) .. ", -inf), -inf), -inf)")
  end

  -- The barrier (config.lua destroyed.barrier). A preset with the zone on names the next heat and class in place of
  -- the released ones, so the tile scores and the temperature keep their text and a save keeps its zone. The class
  -- reads lava in the Tile program, and the heat in both, so the Entity program pays for the edge, blob and flow
  -- noises, and the open mask adds the kind noise.
  local B = D.barrier
  local BN = B.names
  local O = D.outline.names

  -- A noise in reference pixels that stops shrinking at its floor (config.lua destroyed.barrier: scale 1's specks).
  local function floored(P)
    return "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(P.seed1) .. ", octaves = " ..
      num(P.octaves) .. ", persistence = " .. num(P.persistence) .. ", input_scale = 1 / max(" ..
      num(P.wavelength_px) .. " * " .. K.scale .. ", " .. num(P.floor_tiles) .. "), output_scale = 1}"
  end
  def(BN.edge, noise(B.edge))
  def(BN.blob, floored(B.blob))
  def(BN.flow, floored(B.flow))
  def(BN.kind, floored(B.kind))
  def(BN.macro, floored(B.macro))
  def(BN.zone, K.scale .. " * (" .. O.depth .. " - " .. num(B.fray_px) .. " * (1 + clamp(" .. BN.edge .. ", -1, 1)))")
  -- The next zone (destroyed.barrier.next): the next outline's depth, cut as above and frayed. A preset with the zone
  -- on names it over the released zone, which reach reads by name, so the wasteland's edge frays as before. The next
  -- heat and class read it shifted by the gap instead: the barrier between that edge and the heat ground narrows to
  -- nothing in places and runs wider in others.
  local GP = B.next.gap
  def(BN.gap, "clamp(" .. num(GP.mid) .. " + " .. num(GP.amp) .. " * " .. noise(GP) .. ", " .. num(GP.low) .. ", " ..
    num(GP.top) .. ")")
  local function fray(FR, per_tile)
    -- in tiles: size tiles, but never more than cap reference pixels (at scale 1 a tile is a reference pixel)
    return (per_tile and ("min(" .. num(FR.cap) .. ", " .. num(FR.size) .. " / " .. K.scale .. ")") or num(FR.size)) ..
      " * multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(FR.seed1) .. ", octaves = " ..
      num(FR.octaves) .. ", persistence = " .. num(FR.persistence) .. ", input_scale = 1 / " ..
      (per_tile and num(FR.wavelength) or ("(" .. num(FR.wavelength) .. " * " .. K.scale .. ")")) ..
      ", output_scale = 1}"
  end
  def(BN.zone3, K.scale .. " * (" .. D.outline.next.depth .. " - " .. num(B.fray_px) .. " * (1 + clamp(" .. BN.edge ..
    ", -1, 1)) + " .. fray(B.next.fray.px) .. " + " .. fray(B.next.fray.tiles, true) .. ")")
  local shifted = BN.zone3 .. " / " .. K.scale .. " + " .. BN.gap
  def(BN.lava, BN.blob .. " + " .. num(B.flow_lift) .. " * clamp((" .. BN.blob .. " - " .. num(B.flow_from) .. ") / " ..
    num(B.flow_span) .. ", 0, 1) * clamp(1 - abs(" .. BN.flow .. ") / " .. num(B.flow_width) .. ", 0, 1)")
  local grain = "noise_layer_noise(" .. num(cfg.climate.grain.layer) .. ")"
  -- An amplitude in reference pixels on a noise measured in tiles (config.lua destroyed.barrier.swing_tiles).
  local function swing(px)
    return "min(" .. num(px) .. ", " .. num(px * B.swing_tiles) .. " / " .. K.scale .. ")"
  end
  local lifted = "depth + " .. swing(H.lift_fray_px) .. " * " .. N.fine .. " - " .. num(B.lift_px)
  -- The spawn stands in the zone (destroyed.barrier.start): the hottest bands wait a little way out.
  local top = "min(" .. num(H.cap) .. ", " .. num(B.start.cap) .. " + " .. num(B.start.per_tile) .. " * max(0, " ..
    D.start.distance .. " - " .. num(B.start.cool_tiles) .. "))"
  local hot = "clamp(" .. num(B.t_at) .. " + " .. num(B.gain) ..
    " * (" .. BN.lava .. " - " .. num(B.lava_at) .. ") + " .. num(B.gain_hot) .. " * max(0, " .. BN.lava .. " - " ..
    num(B.lava_at) .. ") + " .. num(B.fine) .. " * " .. N.fine .. " + " ..
    num(B.t_grain) .. " * grain, " ..
    num(H.rim) .. ", " .. top .. ")"
  def(BN.heat, "if(min(" .. O.present .. ", " .. lifted .. ") > 0, " .. hot .. ", -inf)",
    {depth = BN.zone .. " / " .. K.scale, grain = grain})

  -- Where the wasteland is: every tile the class or the lift takes. The class reads it, and the Entity program, so
  -- what a zone excludes stops on the tile the wasteland starts on.
  def(BN.reach, "min(" .. O.present .. ", max(" .. lifted .. ", depth - " .. num(B.feather_in) .. " + " ..
    swing(B.feather_px) .. " * " .. N.fine .. " + " .. num(B.feather_kind) .. " * " .. BN.kind .. " + " ..
    swing(B.feather_grain) .. " * grain))", {depth = BN.zone .. " / " .. K.scale, grain = grain})
  def(BN.open, "if(" .. BN.reach .. " + " .. swing(B.open_px) .. " > 0, 0, 1)")
  -- The next heat: the lift on the shifted depth, and never past the wasteland's edge, which the plain depth draws
  -- (the reach, read by name).
  def(BN.heat3, "if(min(" .. O.present .. ", " .. lifted .. ", " .. BN.reach .. ") > 0, " .. hot .. ", -inf)",
    {depth = shifted, grain = grain})

  -- Room to build round the spawn (destroyed.barrier.start): 1 outside the zone and past the clearing.
  def(BN.thin, "max(" .. BN.open .. ", clamp((" .. D.start.distance .. " - " .. num(B.start.rock_tiles) .. ") / " ..
    num(B.start.rock_span) .. ", " .. num(B.start.rock_floor) .. ", 1))")

  local blackish = BN.kind .. " + " .. num(B.black_fine) .. " * " .. N.fine .. " + " ..
    num(B.black_grain) ..
    " * grain < " .. num(B.black_below) .. " + " .. num(B.black_in) .. " * core + " .. num(B.heart_black) ..
    " * heart + " .. num(B.black_mac) .. " * (1 - heart) * " .. BN.macro
  local black = "if(" .. blackish .. ", if(sandy > 0, " .. L[T.black_sand] .. ", " .. L[T.black_dirt] .. "), "
  local rock2 = "if(" .. BN.macro .. " * " .. num(B.grey_mac) .. " + " .. num(B.grey_kind) .. " * " .. BN.kind ..
    " + " .. num(B.grey_grain) .. " * grain > " .. num(B.grey_at) .. " + " .. num(B.grey_out) .. " * (1 - core), " ..
    L[T.grey_dirt] .. ", " .. black .. "if(sandy > 0, " .. L[T.red_sand] .. ", " .. L[T.red_dirt] .. ")))"
  -- The next class's rock (destroyed.barrier.rock3): black ash, and where black sand or red dirt stood, heat ground or
  -- black ash by depth and noise. No grey dirt, red sand, black sand or red dirt.
  local R3 = B.rock3
  local heated = "if(min(" .. lifted .. ", core + " .. num(R3.mac) .. " * " .. BN.macro .. " + " .. num(R3.fine) ..
    " * " .. N.fine .. " + " .. num(R3.grain) .. " * grain - " .. num(R3.heat_at) .. ") > 0, 0, " .. L[T.black_dirt] ..
    ")"
  local rock3 = "if(" .. blackish .. ", if(sandy > 0, " .. heated .. ", " .. L[T.black_dirt] .. "), " .. heated .. ")"
  -- Heat ground needs the lift: without it class 0 is ordinary ground, in specks inside the wasteland.
  local function class_body(name, depth, ground_at, palette, ground)
    ground = ground or {fine = B.ground_fine, grain = B.ground_grain}
    def(name, "if(" .. BN.reach .. " <= 0, 0, if(min(" .. lifted .. ", " .. BN.lava .. " + " .. num(ground.fine) ..
    " * " .. N.fine .. " + " .. num(ground.grain) .. " * grain - " .. num(B.penalty) .. " * (1 - core) + " ..
    num(B.heart_gain) .. " * heart - " .. num(ground_at) .. ") > 0, 0, if(grassy < " .. num(B.grass_cut) .. ", " ..
    L[T.grass] .. ", " ..
    palette .. ")))", {
      depth = depth,
      grain = grain,
      sandy = num(B.sand_mac) .. " * " .. BN.macro .. " + " .. N.fine .. " + " .. num(B.sand_grain) .. " * grain - " ..
        num(B.sand_cut),
      core = "clamp((depth - " .. num(B.barrier_px) .. " - " .. num(B.barrier_mac) .. " * " .. BN.macro ..
        ") / " .. num(B.ramp_px) .. ", 0, 1)",
      heart = "clamp((depth - " .. num(B.heart_px) .. " - " .. num(B.heart_mac) .. " * " .. BN.macro ..
        ") / " .. num(B.heart_ramp) .. ", 0, 1)",
      grassy = "depth / " .. num(B.grass_px) .. " + " .. num(B.grass_mac) .. " * " .. BN.macro .. " + " ..
        num(B.grass_fine) .. " * " .. N.fine .. " + " .. num(B.grass_heart) .. " * heart",
    })
  end
  class_body(BN.class, BN.zone .. " / " .. K.scale, B.ground_at, rock2)
  class_body(BN.class3, shifted, B.next.ground_at, rock3, B.next.ground)

  -- The devastation field (0.3.1; config.lua destroyed.dev). A preset with the zone on names its heat, class, reach and
  -- open mask over the barrier's. One position in tiles, and every class a cut on it, so the classes follow each other
  -- from the edge in and none stands outside its band: dry dirt, scorched red grass, black ash, then heat ground.
  local DV = D.dev
  local DN = DV.names
  local PY = DV.pyrenees
  def(DN.ragged, num(DV.ragged.px) .. " * " .. noise(DV.ragged))
  def(DN.width, num(DV.width_px) .. " * " .. K.scale .. " * clamp(1 + " .. num(DV.width.amp) .. " * " ..
    noise(DV.width) .. ", " .. num(DV.width.low) .. ", " .. num(DV.width.high) .. ")")
  def(DN.wobble_a, noise(DV.wobble.a))
  def(DN.wobble_b, noise(DV.wobble.b))
  local tf = {}
  for _, o in ipairs(DV.tile_fray) do
    tf[#tf + 1] = num(o.amp) .. " * basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(o.seed1) ..
      ", input_scale = 1 / " .. num(o.tiles) .. ", output_scale = 1}"
  end
  def(DN.fray, table.concat(tf, " + "))
  -- Near the Iberia cut the position yields to the massif's snow, so the snow's own frayed edge is the zone's there;
  -- the cut's depth into Spain (south pixels a pixel) keeps the yield from rising again past the snow, and the gate
  -- takes the yield off from gate_px north of the cut, so no other range in the zone takes snow back.
  local cut = D.outline.next.cuts.iberia
  local cold = cfg.ridges.names.cold2.gated
  -- The Moscow zone's position (config.lua moscow.dev), the same formula on its own outline. The field is the larger
  -- of Europe's, with the Europe key on, and Moscow's, with the level at chaos.
  local MO = MZ.outline.names
  def(MZ.dev, "if(" .. MO.present .. " > 0, " .. K.scale .. " * (" .. MO.depth .. " - " .. num(MZ.start_px) .. " + " ..
    num(MZ.ragged_share) .. " * " .. DN.ragged .. "), " .. num(DV.outside_tiles) .. ")")
  def(DN.dev, "max(if(" .. MZ.europe.key .. " > " .. num(MZ.match) .. ", if(" .. DN.present .. " > 0, min(" ..
    K.scale .. " * (" .. DN.depth .. " - " .. num(DV.start_px) .. " + " .. DN.ragged .. "), " .. K.scale ..
    " * snow), " .. num(DV.outside_tiles) .. "), " .. num(DV.outside_tiles) .. "), if(abs(" .. MZ.key .. " - " ..
    num(MZ.chaos) .. ") < " .. num(MZ.match) .. ", " .. MZ.dev .. ", " .. num(DV.outside_tiles) .. "))", {
      snow = num(PY.snow_px) .. " * (" .. num(PY.snow_at) .. " - " .. cold .. ") - " .. num(PY.south) .. " * " .. cut ..
        " + " .. num(PY.gate_per_px) .. " * max(0, -" .. cut .. " - " .. num(PY.gate_px) .. ")",
    })
  -- A cut, positive inside it: the position, the cut's own fray in tiles (macro and kind in reference pixels, fine and
  -- grain in tiles), less the cut's place in widths, which the wobble noises move.
  local function cut_at(F)
    local t = {DN.dev, DN.fray}
    local function add(c, what)
      if c ~= 0 then
        t[#t + 1] = num(c) .. " * " .. what
      end
    end
    add(F.macro, K.scale .. " * " .. BN.macro)
    add(F.kind, K.scale .. " * " .. BN.kind)
    add(F.fine, N.fine)
    add(F.grain, "grain")
    local at = {num(F.at)}
    if F.a ~= 0 then
      at[#at + 1] = num(F.a) .. " * " .. DN.wobble_a
    end
    if F.b ~= 0 then
      at[#at + 1] = num(F.b) .. " * " .. DN.wobble_b
    end
    return "(" .. table.concat(t, " + ") .. " - (" .. table.concat(at, " + ") .. ") * " .. DN.width .. ")"
  end
  local CU = DV.cuts
  local at = {grain = grain}
  def(DN.reach, cut_at(CU.dry), at)
  def(DN.open, "if(" .. DN.reach .. " + " .. num(DV.open_tiles) .. " > 0, 0, 1)")
  def(DN.class, "if(" .. DN.reach .. " <= 0, 0, if(" .. cut_at(CU.heat) .. " > 0, 0, if(" .. cut_at(CU.ash) ..
    " > 0, " .. L[T.black_dirt] .. ", if(" .. cut_at(CU.scorched) .. " > 0, " .. L[T.grass] .. ", " ..
    num(DV.tiles[1].class) .. "))))", at)
  -- The heat ground: heat 1 at the cut, rising by ramp degrees a width, and never hotter than the lava blob's
  -- temperature or the spawn's cooler cap.
  def(DN.heat, "if(h > 0, clamp(min(" .. hot .. ", " .. num(H.rim) .. " + " .. num(DV.ramp) .. " * h / " .. DN.width ..
    "), " .. num(H.rim) .. ", " .. top .. "), -inf)", {h = cut_at(CU.heat), grain = grain})
  for _, t in ipairs(DV.tiles) do
    def(t.body, "if(" .. K.destroyed .. " > " .. num(D.switch_threshold) .. ", if(elevation > 0, if(" ..
      C.names.class .. " == " .. num(t.class) .. ", " .. num(C.score) .. ", -inf), -inf), -inf)")
  end

  -- The exclusion (config.lua destroyed.exclusion): the key's prototype holds 0, so a world made before keeps every
  -- hook's off branch and the dead trees' copies place nothing.
  local X = D.exclusion
  def(X.key, "0")
  for _, p in ipairs(X.palms) do
    def(p.body, p.inner .. " * " .. BN.open)
    def(p.next.body, p.next.inner .. " * " .. BN.open)
  end
  local G2 = B.dead
  def(BN.dead_noise, "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(G2.seed1) .. ", octaves = " ..
    num(G2.octaves) .. ", persistence = " .. num(G2.persistence) .. ", input_scale = 1 / " ..
    num(G2.wavelength_tiles) .. ", output_scale = 1}")
  def(BN.dead, "if(" .. BN.reach .. " > 0, if(" .. BN.lava .. " < " .. num(B.lava_at) .. ", " .. num(G2.peak) ..
    " * " .. BN.thin .. " * clamp((" .. BN.dead_noise .. " - " .. num(G2.cut) .. ") / " .. num(G2.span) ..
    ", 0, 1), 0), 0)")
  -- The dead Great forests (config.lua destroyed.barrier.dead.forest), behind the great-forests gate.
  local GF, TB = G2.forest, cfg.trees.boost
  def(BN.dead2, "if(" .. BN.reach .. " > 0, if(" .. BN.lava .. " < " .. num(B.lava_at) .. ", max(" .. num(G2.peak) ..
    " * " .. BN.thin .. " * clamp((" .. BN.dead_noise .. " - " .. num(G2.cut) .. ") / " .. num(G2.span) ..
    ", 0, 1), if(" .. TB.gate .. " > " .. num(cfg.hooks.threshold) .. ", " .. num(GF.peak) .. " * " .. BN.thin ..
    " * clamp(" .. num(GF.gain) .. " * " .. cfg.regions.names.forest_w .. ", 0, 1) * clamp(" .. num(GF.floor) ..
    " + " .. BN.dead_noise .. ", 0, 1), 0)), 0), 0)")
end

data:extend(E)
