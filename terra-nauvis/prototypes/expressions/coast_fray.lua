-- The coast fray and the Map type versions (config.lua coast_fray; geography versions with map_type_of).
--
-- A Map type version re-reads an older version's composition by name: its chain, box, spawn bodies and waterway sets
-- stay that version's, and its entry, shore, inland lakes and coast fit are its own. Its coast fit is the generated
-- fit its fits.geo names, bound to the older version's warped chain plus the fray octaves (coast.lua), and its bodies
-- read that fit past map_type_of.above_scale and the older version's geo up to it. The scale is a folded constant, so
-- each world compiles one branch.
local cfg = require("prototypes.config")

local M = {}
local K = cfg.keys
local F = cfg.coast_fray

local function num(v)
  return string.format(cfg.number_format, v)
end

-- The version of a map a Map type version re-reads, by geo_id.
function M.base(key, v)
  for _, o in ipairs(cfg.geography[key].versions) do
    if o.geo_id == v.map_type_of.geo_id and not o.map_type_of then
      return o
    end
  end
  error("config.lua geography." .. key .. ": map_type_of of " .. v.entry .. " names no older version")
end

-- The text a Map type version's bodies read in place of a name: `past` past above_scale, `upto` up to it.
function M.pick(v, past, upto)
  return "if(" .. K.scale .. " > " .. num(v.map_type_of.above_scale) .. ", " .. past .. ", " .. upto .. ")"
end

-- The fray's terms on one warped axis ("u" or "v") of version g's chain, in reference pixels: each octave
-- amplitude_tiles / scale * basis_noise at wavelength_tiles, anchored through the city offset.
function M.terms(g, axis)
  local out = {}
  for _, o in ipairs(F.octaves) do
    out[#out + 1] = num(o.amplitude_tiles) .. " / " .. K.scale .. " * basis_noise{x = x, y = y, seed0 = map_seed, " ..
      "seed1 = " .. num(o.seed1[axis]) .. ", input_scale = " .. num(1 / o.wavelength_tiles) .. ", offset_x = " ..
      g.cx .. ", offset_y = " .. g.cy .. "}"
  end
  return table.concat(out, " + ")
end

-- The base version's record with the Map type version's own entry, shore and spawn record, and its geo read through
-- pick(): what coast.lua and spawn.lua compose for it. geo_id stays the base's, so every list a version is looked up
-- in (the coast warp, the shore fray, the spawn folds) answers as for the base.
function M.record(key, v)
  local base = M.base(key, v)
  local r = {}
  for k, value in pairs(base) do
    r[k] = value
  end
  r.entry, r.shore, r.spawn = v.entry, v.shore, v.spawn
  r.geo = M.pick(v, v.geo, base.geo)
  return r, base
end

return M
