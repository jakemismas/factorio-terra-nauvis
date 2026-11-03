-- Tree expressions (ARCHITECTURE.md, "Expression inventory" and "Stable hooks"). Climate tiles
-- ships the palm switch; trees-forests adds the forest boost, the restored vanilla trees, rocks and
-- decals beside Alien Biomes, and the palms' second versions.
--
-- The palm switch (DECISIONS 08:00; council graft 10; plan reconciliation 9): Alien Biomes' palms read
-- elevation in the Entity program (R3 4.1), which on an Earth preset is the fine coast field (constraint
-- S-3). Earth presets point each palm's entity:<tree>:probability and :richness keys at
-- Earth copies of its autoplace (presets.lua) that read this constant where AB reads elevation. The
-- constant is the palm band's middle (AB's palms grow from elevation 0 to 2), so on Earth presets palms
-- follow climate and sand alone (plan Contradictions item 6); every other world keeps AB's own palms,
-- untouched. A Map type pick sets no key, so its palms read the fine field (Contradictions item 15).
-- Every Earth preset bakes the keys with or without Alien Biomes, so a world that gains AB later
-- meets the switch too; a save made before the switch names no key and keeps AB's own palms on its
-- fine field for life (DECISIONS 2026-10-29 18:40).
--
-- The copies are built at data-final-fixes from the installed palms (M.palm_bodies), since Alien Biomes' own
-- data-final-fixes is the last to touch a tree, and hold no Alien Biomes text in this mod. Each carries the noise
-- functions it calls as local functions under local_prefix. The names are registered, so
-- data-final-fixes.lua holds the installed palms to config.lua's digest (tools/build_palms.py): on a missing or
-- unexpected palm, and with no Alien Biomes, every copy is the neutral body, so a save always finds its names.
--
-- The great forests (trees-forests; S10 section 4; ARCHITECTURE.md, "Stable hooks"): every living tree's
-- probability becomes boost(own) below, if(tn_forests_on > threshold, min(cap, ((own) + tn_tree_lift) *
-- tn_tree_mult), own) on the base game's living trees (own alone on every other tree); the lift key's
-- prototype holds 0 and Earth presets name the boreal lift (config.lua trees.boost), so only the boreal
-- great forests fill in beyond the multiplier. The gate's prototype holds 0 and the key's 1, so on every
-- world without an Earth preset the hook folds to the tree's own autoplace; Earth presets bake the gate
-- from the great-forests setting and name the region layer's multiplier in the key (1 + forest boost 2
-- times the forest sum; the region formula lives in regions.lua alone, D13). A multiplier keeps the
-- climate in charge: where a tree's own probability is 0 or below, the boost adds nothing (S10). Alien
-- Biomes' palm prototypes carry no
-- hook (they stay AB's, so the palm copies and their digest read them raw): on Earth presets the
-- palms read their copies, so each palm's probability key names a second version that is the same
-- formula around the registered first (design rule 21); the richness keys keep the first versions.
--
-- The restored base game beside Alien Biomes (trees-forests; S3 section 5; R3 3.4 items 3 to 6): AB nils
-- the autoplace of the 15 living vanilla trees and of the vanilla rocks and decals. data-final-fixes.lua
-- rebuilds each behind the gate tn_on with one key, whose prototype here holds the off value and which
-- Earth presets with AB point at the Earth body defined here from prototypes/tables/vanilla.lua: the
-- base game's own text, with the Earth temperature on the vanilla scale where a tree reads temperature
-- (the fallback climate's scale and clamp, which the vanilla trees read without AB). These bodies read
-- the base game's shared tree and rock helpers by name, as the base game's own entities do (DECISIONS,
-- trees-forests). The re-listed decoratives' keys hold -inf and Earth presets name one shared body, 0.
local cfg = require("prototypes.config")
local V = require("prototypes.tables.vanilla")

local P = cfg.tiles.palm
local TR = cfg.trees
local B = TR.boost
local R = TR.restore
local FB = cfg.climate.temperature.fallback

local function num(v)
  return string.format(cfg.number_format, v)
end

local M = {}

-- The great-forests hook around a tree's own probability (also each palm copy's second version, without
-- the lift). `lift` adds the boreal lift key, for the base game's living trees only: Alien Biomes' trees
-- already fill its taiga, and lifted they covered over half the land (draft run q-ab-after, 558 trees per
-- chunk in the preview against 129 without). `band` scales the lift beside Alien Biomes, where these trees
-- stand on adopted tiles that reach past the band: unscaled, it set a forest on every such tile of the taiga.
function M.boost(own, lift, band)
  local inner = "(" .. own .. ")"
  if lift then
    inner = "((" .. own .. ") + " .. B.lift .. (band and (" * " .. band) or "") .. ")"
  end
  return "if(" .. B.gate .. " > " .. num(cfg.hooks.threshold) .. ", min(" .. num(B.cap) .. ", " .. inner .. " * " ..
    B.key .. "), " .. own .. ")"
end

local function ident(name)
  return "%f[%w_]" .. (string.gsub(name, "%p", "%%%0")) .. "%f[^%w_]"
end

-- The palm copies' prototypes from Alien Biomes' live autoplace (`source`, data-final-fixes.lua palm_source): each text
-- with every called function renamed to its local name and elevation replaced by the palm constant, the functions
-- carried as local functions; numbers pass through. With no source, the neutral body under every name, so a saved
-- world's names stay defined.
function M.palm_bodies(source)
  local out = {}
  if not source then
    for i, c in ipairs(P.copies) do
      out[i] = {type = "noise-expression", name = c.body, expression = P.neutral}
    end
    return out
  end
  local fnames = {}
  for name in pairs(source.functions) do
    fnames[#fnames + 1] = name
  end
  table.sort(fnames)
  local function rewrite(v)
    if type(v) ~= "string" then
      return v
    end
    local s = v
    for _, name in ipairs(fnames) do
      s = string.gsub(s, ident(name), P.local_prefix .. name)
    end
    return (string.gsub(s, ident(P.reads), P.body))
  end
  local function rewrite_all(t)
    local copy = {}
    for k, v in pairs(t or {}) do
      copy[k] = rewrite(v)
    end
    return copy
  end
  local function local_functions()
    local copy = {}
    for _, name in ipairs(fnames) do
      local f = source.functions[name]
      local params = {}
      for i, p in ipairs(f.parameters) do
        params[i] = p
      end
      copy[P.local_prefix .. name] = {parameters = params, expression = rewrite(f.expression),
                                      local_expressions = f.local_expressions and rewrite_all(f.local_expressions) or
                                        nil}
    end
    return copy
  end
  for i, c in ipairs(P.copies) do
    local t = source.trees[c.tree]
    out[i] = {type = "noise-expression", name = c.body, expression = rewrite(t[c.field .. "_expression"]),
              local_expressions = rewrite_all(t.local_expressions), local_functions = local_functions()}
  end
  return out
end

local E = {{type = "noise-expression", name = P.body, expression = string.format(cfg.number_format, P.value)}}

local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The boost's gate and multiplier key, at their off values.
def(B.gate, B.gate_off)
def(B.key, B.key_off)
def(B.lift, B.lift_off)
def(B.lift_body, num(B.lift_per_sum) .. " * " .. cfg.regions.names.forest_sum .. " * clamp((" ..
  num(B.boreal_from_t) .. " - " .. cfg.climate.names.core .. ") / " .. num(B.boreal_from_t - B.boreal_full_t) ..
  ", 0, 1)")

-- The Earth temperature on the vanilla scale, as the fallback climate hands it to vanilla trees.
def(TR.temperature, "clamp(" .. num(FB.scale) .. " * temperature, " .. num(FB.min) .. ", " .. num(FB.max) .. ")")

-- The restored trees: each tree's text with the vanilla-scale temperature; one shared richness body.
local TEMP = "%f[%w_]temperature%f[^%w_]"
for _, row in ipairs(V.trees) do
  local n = R.trees[row.tree]
  if not n then
    error("config.lua trees.restore.trees has no names for " .. row.tree)
  end
  def(n.p, R.tree_off)
  def(n.r, R.tree_off)
  def(n.body, (string.gsub(row.text, TEMP, TR.temperature)))
end
def(R.richness, V.tree_richness)

-- The rebuilt rocks and decals: each one's own autoplace text and local expressions.
for _, row in ipairs(V.rocks) do
  local n = R.rocks[row.name]
  if not n then
    error("config.lua trees.restore.rocks has no names for " .. row.name)
  end
  local locals = nil
  if row.local_expressions then
    locals = {}
    for k, v in pairs(row.local_expressions) do
      locals[k] = v
    end
  end
  def(n.key, R.rock_off)
  def(n.body, row.probability_expression, locals)
  -- A big rock's highland body (ridges.lua): the same text on rock_density with the lift. Rock decoratives keep
  -- vanilla's, so ground cover stays what it was.
  if n.high then
    def(n.high, (string.gsub(row.probability_expression, "%f[%w_]rock_density%f[^%w_]", cfg.ridges.names.rock_density)),
      locals)
  end
  -- The cold versions (config.lua trees.restore.cold): no tan rock or sand decal on cold ground.
  local RC = R.cold
  local fade = " * clamp((temperature - " .. num(RC.lo) .. ") / " .. num(RC.span) .. ", 0, 1)"
  if n.cold then
    def(n.cold, n.body .. fade)
  end
  if n.cold_high then
    def(n.cold_high, n.high .. fade)
  end
end

-- The re-listed decoratives: one key each at -inf, all naming one body.
for _, name in ipairs(V.relist) do
  local key = R.decoratives[name]
  if not key then
    error("config.lua trees.restore.decoratives has no key for " .. name)
  end
  def(key, R.deco_off)
end
def(R.deco_body, R.deco_on)

-- The palms' second probability versions: the boost around climate-tiles' copies, defined on every
-- load as the copies are (design rule 21: the copies stay registered and unchanged).
for _, p in ipairs(TR.palm) do
  def(p.body, M.boost(p.base))
  def(p.next, p.body .. " * " .. cfg.tiles.palm_allow.body)
  def(p.next2, "max(" .. p.body .. " * " .. cfg.tiles.palm_allow2.body .. ", " .. cfg.tiles.palm_allow2.shore.body ..
    ")")
  -- The violet palm keeps to the blue zone (config.lua blue.no_blue), whose open exists with Alien Biomes alone.
  if p.next3 and mods["alien-biomes"] then
    def(p.next3, p.next2 .. " * " .. cfg.blue.no_blue.open)
  end
end

-- The palm mask (config.lua tiles.palm_allow): a product of tests on fields the Entity program holds already.
local PA = cfg.tiles.palm_allow
def(PA.body, "(temperature + " .. cfg.climate.names.belts.t .. " > " .. num(PA.warm_t) .. ") * (" .. cfg.keys.high ..
  " + " .. cfg.keys.scale .. " * (" .. cfg.regions.names.highland_fray .. " + " .. num(PA.margin_px) .. ") <= 0) * (" ..
  cfg.climate.names.lat .. " < " .. num(PA.lat) .. ")")

-- The mask of 0.3.0 (config.lua tiles.palm_allow2): the shore field is the squared distance in degrees to the nearest
-- warm Mediterranean shore segment, on the unmeandered latitude, so it follows the coast and not the climate's wander.
local PA2 = cfg.tiles.palm_allow2
local SHORE = require("prototypes.tables.palm_coast").shores
local CK = PA2.lon_scale
local shore_locals = {plon = cfg.climate.names.lon .. " * " .. num(CK),
                      plat = cfg.climate.names.lat .. " - " .. num(cfg.climate.meander.degrees) .. " * " ..
                        cfg.climate.meander.name}
local terms = {}
for _, line in ipairs(SHORE) do
  for i = 2, #line do
    local ax, ay = line[i - 1][1] * CK, line[i - 1][2]
    local bx, by = line[i][1] * CK - ax, line[i][2] - ay
    local len2 = bx * bx + by * by
    if len2 > 0 then
      local k = #terms + 1
      shore_locals["t" .. k] = "clamp((plon - " .. num(ax) .. ") * " .. num(bx / len2) .. " + (plat - " .. num(ay) ..
        ") * " .. num(by / len2) .. ", 0, 1)"
      shore_locals["x" .. k] = "plon - " .. num(ax) .. " - t" .. k .. " * " .. num(bx)
      shore_locals["y" .. k] = "plat - " .. num(ay) .. " - t" .. k .. " * " .. num(by)
      terms[k] = "x" .. k .. " * x" .. k .. " + y" .. k .. " * y" .. k
    end
  end
end
def(PA2.med, "min(" .. table.concat(terms, ", ") .. ")", shore_locals)
local BAND = PA2.band_px / cfg.coordinates.px_per_degree
local WARM_LOW = "(temperature + " .. cfg.climate.names.belts.t .. " > " .. num(PA.warm_t) .. ") * (" ..
  cfg.keys.high .. " + " .. cfg.keys.scale .. " * (" .. cfg.regions.names.highland_fray .. " + " .. num(PA.margin_px) ..
  ") <= 0)"
def(PA2.body, WARM_LOW .. " * max(" .. cfg.climate.names.lat .. " < " .. num(PA.lat) .. ", " .. PA2.med .. " < " ..
  num(BAND * BAND) .. ")")
local SH = PA2.shore
local K = cfg.keys
def(SH.body, "(temperature + " .. cfg.climate.names.belts.t .. " > " .. num(PA.warm_t) .. ") * ((" .. K.high ..
  " - " .. num(cfg.ridges.high.rock_tiles) .. " / " .. K.scale .. ") / " .. K.scale .. " + " ..
  cfg.regions.names.highland_fray .. " <= " .. num(SH.reach_px) .. ") * (" .. cfg.climate.names.lat .. " >= " ..
  num(PA.lat) .. ") * " .. num(SH.p) ..
  " * clamp(1 - " .. PA2.med .. " / " .. num(BAND * BAND) .. ", 0, 1) * clamp(" .. num(SH.grove_mid) .. " + " ..
  num(SH.grove) ..
  " * basis_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(SH.seed1) .. ", input_scale = 1 / " ..
  num(SH.wave_tiles) .. ", output_scale = 1}, 0, 1)")

data:extend(E)

return M
