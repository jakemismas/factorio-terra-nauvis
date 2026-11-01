-- Blue corrupted UK and Australia (config.lua blue).
--
-- The tiles follow Destroyed Europe's pattern: a class per tile, a score per palette tile that data-final-fixes.lua
-- takes the max with, and an elevation gate that keeps water water. Trees and plants follow Alien Biomes' own boxes:
-- a preset with the zone on names the three climate bodies below in place of temperature, moisture and aux, and the
-- keep body in place of tiles.scan's, so inside the zone Alien Biomes grows what its boxes hold at this climate, and
-- past the coast or the Ulster border every reader meets the name it read before. Each climate body reads the old value
-- through an under name, which the preset points at it, so the zone wraps Destroyed Europe's temperature rather than
-- replacing it. What the boxes let through and should not is config.lua blue.exclusion's job.
--
-- Tile scores read their own copies of the climate, so a tile takes no score from these bodies. The Entity program does
-- read them, so nothing here reads elevation (the firewall). Every world without the toggle compiles none of this: the
-- key's prototype holds 0, and each score folds to -inf behind it.
local cfg = require("prototypes.config")

local AB = mods["alien-biomes"] ~= nil

local B = cfg.blue
local N = B.names
local O = B.outline.names
local K = cfg.keys
local T = B.tile

local function num(v)
  return string.format(cfg.number_format, v)
end

local E = {}
local function def(name, expression, locals)
  E[#E + 1] = {type = "noise-expression", name = name, expression = expression, local_expressions = locals}
end

def(K.blue, "0")

if AB then
  local FINE = cfg.destroyed.names.fine
  local GRAIN = "noise_layer_noise(" .. num(cfg.climate.grain.layer) .. ")"

  -- A noise in reference pixels that stops shrinking at its floor, so scale 1 keeps a patch a player can read.
  local function floored(P)
    return "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. num(P.seed1) .. ", octaves = " ..
      num(P.octaves) .. ", persistence = " .. num(P.persistence) .. ", input_scale = 1 / max(" ..
      num(P.wavelength_px) .. " * " .. K.scale .. ", " .. num(P.floor_tiles) .. "), output_scale = 1}"
  end

  -- An amplitude in reference pixels on a noise measured in tiles, which would turn to dither on a large map.
  local function swing(px)
    return "min(" .. num(px) .. ", " .. num(px * B.swing_tiles) .. " / " .. K.scale .. ")"
  end

  def(N.macro, floored(B.macro))
  def(N.kind, floored(B.kind))
  def(N.dry, floored(B.dry))
  def(N.field, N.macro .. " + " .. num(B.kind_share) .. " * " .. N.kind)
  def(N.reach, O.depth .. " - " .. num(B.feather_in) .. " + " .. swing(B.feather_px) .. " * " .. FINE .. " + " ..
    num(B.feather_kind) .. " * " .. N.kind .. " + " .. swing(B.feather_grain) .. " * " .. GRAIN)
  def(N.open, "if(" .. N.reach .. " + " .. swing(B.open_px) .. " > 0, 0, 1)")

  local L = {}
  for _, t in ipairs(B.tiles) do
    L[t.tile] = num(t.class)
  end

  local function pair(first, second)
    return "if(side > " .. num(B.side_at) .. ", " .. L[first] .. ", " .. L[second] .. ")"
  end
  def(N.class, "if(" .. N.reach .. " <= 0, 0, if(" .. O.depth .. " - " .. num(B.rim_px) .. " - " .. num(B.rim_mac) ..
    " * " .. N.kind .. " + " .. swing(B.rim_grain) .. " * " .. GRAIN .. " < 0, " .. L[T.aubergine_rim] .. ", if(" ..
    N.dry .. " + edge < " .. num(B.dirt_at) .. ", " .. pair(T.purple_dirt, T.aubergine_dirt) ..
    ", if(z < " .. num(B.lo) .. ", " .. pair(T.blue_1, T.blue_2) .. ", if(z > " .. num(B.hi) .. ", " ..
    pair(T.purple_1, T.purple_2) .. ", " .. pair(T.mauve_1, T.mauve_2) .. ")))))", {
      edge = num(B.edge_fine) .. " * " .. FINE .. " + " .. num(B.edge_grain) .. " * " .. GRAIN,
      z = N.field .. " + edge",
      side = FINE .. " + " .. num(B.side_grain) .. " * " .. GRAIN,
    })
  for _, t in ipairs(B.tiles) do
    def(t.body, "if(" .. K.blue .. " > " .. num(cfg.destroyed.switch_threshold) .. ", if(elevation > 0, if(" ..
      N.class .. " == " .. num(t.class) .. ", " .. num(B.score) .. ", -inf), -inf), -inf)")
  end

  -- The climate inside the zone. Past the reach each body is the value it wraps. lo and hi on the field stand at the
  -- box's 20 and 40, so purple ground grows purple's trees and plants.
  local C = B.climate
  local function inside(value, under)
    return "if(" .. N.reach .. " > 0, " .. value .. ", " .. under .. ")"
  end
  def(C.temperature.body, inside(num(B.t_at) .. " + " .. num(B.t_per_field) .. " * " .. N.field, C.temperature.under))
  local wet = N.dry .. " + " .. num(B.edge_fine) .. " * " .. FINE .. " + " .. num(B.edge_grain) .. " * " .. GRAIN
  def(C.moisture.body, inside("if(wet > " .. num(B.wood_at) .. ", " .. num(B.m_wood) .. ", if(wet < " ..
    num(B.dry_at) .. ", " .. num(B.m_dry) .. ", " .. num(B.m_open) .. "))", C.moisture.under), {wet = wet})
  def(C.aux.body, inside("clamp(" .. num(B.aux_at) .. " + " .. num(B.aux_span) .. " * " .. N.kind .. ", " ..
    num(B.aux_low) .. ", " .. num(B.aux_high) .. ")", C.aux.under))
  -- Each under name is what a world reads if no preset points it, which never happens on a world that compiles these.
  for _, c in pairs(C) do
    def(c.under, "0")
  end

  -- The list hook's keep body with the zone open: the same text under a second name, since a preset points the first at
  -- this one and a body cannot read itself by name.
  local scan = data.raw["noise-expression"][cfg.tiles.scan.body]
  def(N.keep_under, scan.expression, scan.local_expressions)
  def(N.keep, inside("1", N.keep_under))

  -- No palm stands in the zone. Alien Biomes' violet palm would fit the box, and it stays out with the green one.
  for _, p in ipairs(B.palms) do
    def(p.under, "0")
    def(p.body, p.under .. " * " .. N.open)
  end
end

data:extend(E)
