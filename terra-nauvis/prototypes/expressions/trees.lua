-- Tree expressions (ARCHITECTURE.md, "Expression inventory" and "Stable hooks"). Milestone climate-tiles
-- ships the palm switch; trees-forests adds the forest boost, the restored vanilla trees, rocks and
-- decals beside Alien Biomes, and the palms' second versions.
--
-- The palm switch: Alien Biomes' palms read
-- elevation in the Entity program (R3 4.1), which on an Earth preset is the fine coast field (design
-- constraint S-3). Earth presets point each palm's entity:<tree>:probability and :richness keys at
-- Earth copies of its autoplace (presets.lua) that read this constant where AB reads elevation. The
-- constant is the palm band's middle (AB's palms grow from elevation 0 to 2), so on Earth presets palms
-- follow climate and sand alone (design note 6); every other world keeps AB's own palms,
-- untouched. A Map type pick sets no key, so its palms read the fine field (Contradictions item 15).
-- Every Earth preset bakes the keys with or without Alien Biomes, so a world that gains AB later
-- meets the switch too; a save made before the switch names no key and keeps AB's own palms on its
-- fine field for life.
--
-- The copies are registered bodies, so they are built from Earth's own data, never from the installed
-- Alien Biomes: the generated table (config.lua tiles.palm.table, tools/build_palms.py) freezes Alien
-- Biomes 0.8.0's palm autoplace and the noise functions it calls, which each copy carries as local
-- functions under local_prefix. They are defined on every load, with or without Alien Biomes, so a
-- save that names them always finds the same bodies; data-final-fixes.lua points the keys at the
-- neutral body instead when the installed palms differ from the table.
--
-- The great forests (trees-forests; S10 section 4; ARCHITECTURE.md, "Stable hooks"): every living tree's
-- probability becomes boost(own) below, if(tn_forests_on > threshold, min(cap, (own) * tn_tree_mult),
-- own). The gate's prototype holds 0 and the key's 1, so on every world without an Earth preset the
-- hook folds to the tree's own autoplace; Earth presets bake the gate from the great-forests setting and
-- name the region layer's multiplier in the key (1 + forest boost 2 times the forest sum; the region
-- formula lives in regions.lua alone, D13). A multiplier keeps the climate in charge: where a tree's
-- own probability is 0 or below, the boost adds nothing (S10). On Earth presets the palms read their
-- copies, so each palm's probability key names a second version that is the same formula around the
-- registered first; the richness keys keep the first versions.
--
-- The restored base game beside Alien Biomes (trees-forests; S3 section 5; R3 3.4 items 3 to 6): AB nils
-- the autoplace of the 15 living vanilla trees and of the vanilla rocks and decals. data-final-fixes.lua
-- rebuilds each behind the gate tn_on with one key, whose prototype here holds the off value and which
-- Earth presets with AB point at the Earth body defined here from prototypes/tables/vanilla.lua: the
-- base game's own text, with the Earth temperature on the vanilla scale where a tree reads temperature
-- (the fallback climate's scale and clamp, which the vanilla trees read without AB). These bodies read
-- the base game's shared tree and rock helpers by name, as the base game's own entities do (design notes,
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

-- The great-forests hook around a tree's own probability (also each palm copy's second version).
function M.boost(own)
  return "if(" .. B.gate .. " > " .. num(cfg.hooks.threshold) .. ", min(" .. num(B.cap) .. ", (" .. own .. ") * " ..
    B.key .. "), " .. own .. ")"
end
-- config.lua tiles.palm.table names this file for tools/build_palms.py; the registration scan reads
-- literal module names only.
local T = require("prototypes.generated.palms_ab_v1")

local function ident(name)
  return "%f[%w_]" .. (string.gsub(name, "%p", "%%%0")) .. "%f[^%w_]"
end

local fnames = {}
for name in pairs(T.functions) do
  fnames[#fnames + 1] = name
end
table.sort(fnames)

-- A recorded text with each carried function renamed to its local name and elevation replaced by the
-- palm constant; numbers pass through.
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
  local out = {}
  for k, v in pairs(t or {}) do
    out[k] = rewrite(v)
  end
  return out
end

local function local_functions()
  local out = {}
  for _, name in ipairs(fnames) do
    local f = T.functions[name]
    local params = {}
    for i, p in ipairs(f.parameters) do
      params[i] = p
    end
    out[P.local_prefix .. name] = {parameters = params, expression = rewrite(f.expression),
                                   local_expressions = f.local_expressions and rewrite_all(f.local_expressions) or nil}
  end
  return out
end

local E = {{type = "noise-expression", name = P.body, expression = string.format(cfg.number_format, P.value)}}
for _, c in ipairs(P.copies) do
  local t = T.trees[c.tree]
  E[#E + 1] = {type = "noise-expression", name = c.body, expression = rewrite(t[c.field .. "_expression"]),
               local_expressions = rewrite_all(t.local_expressions), local_functions = local_functions()}
end

local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

-- The boost's gate and multiplier key, at their off values.
def(B.gate, B.gate_off)
def(B.key, B.key_off)

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
-- load as the copies are (decision 21: the copies stay registered and unchanged).
for _, p in ipairs(TR.palm) do
  def(p.body, M.boost(p.base))
end

data:extend(E)

return M
