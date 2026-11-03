-- Vanilla's regular-patch curves as noise text, for the solid hotspots' third version (config.lua hotspots_v2.v3):
-- the large patch L(d) a row's total is a multiple of, and the mean ore per tile P(d) its richness is a multiple of.
-- The terms are vanilla's own (core/prototypes/noise-functions.lua resource_autoplace_all_patches and
-- core/lualib/resource-autoplace.lua); hotspots_v2.lua reads them for a row's bodies and data-final-fixes.lua for its
-- richness. Pure text, no prototypes.
local cfg = require("prototypes.config")

local V3 = cfg.hotspots_v2.v3
local TG = cfg.hotspots.target
local Q = V3.quantity

local M = {}

local function num(v)
  return string.format(cfg.number_format, v)
end

-- vanilla's regular_spot_quantity_base_at(d) with the size slider (frequency cancels in it)
local function quantity(h, d)
  local size = "var('control:" .. h.resource .. ":size')"
  return "(" .. num(Q.per_km2 / h.spots_per_km2 * h.base_density) .. " * " .. size .. " * clamp((" .. d .. " - " ..
    num(Q.fade_from) .. ") / " .. num(Q.fade_span) .. ", 0, 1) * (1 + clamp((" .. d .. " - " .. num(Q.double_from) ..
    ") / " .. num(Q.double_span) .. ", 0, 1)))"
end

-- vanilla's richness distance factor
local function factor(d)
  return "max((" .. num(TG.rich_offset) .. " + " .. d .. ") / " .. num(TG.rich_span) .. ", 1)"
end

-- L(d): a large (p90) regular patch's total, its distance held at cap_distance
function M.large(h)
  local dc = "min(distance, " .. num(V3.cap_distance) .. ")"
  return num(V3.p90[h.resource] * V3.size_max[h.resource]) .. " * " .. quantity(h, dc) .. " * " .. factor(dc)
end

-- P(d): the mean regular ore per tile, q / (pi r^2) of the typical spot, r = min(radius_cap, rq q^(1/3)); written
-- as the larger of its two branches, so it reads 0, not 0 / 0, where the fade leaves no quantity
function M.per_tile(h)
  local q = "(" .. num(h.mean_size) .. " * " .. quantity(h, "distance") .. ")"
  return num(V3.per_tile_fit) .. " * max(" .. q .. " ^ " .. num(V3.cube_root) .. " / " ..
    num(math.pi * h.rq * h.rq) .. ", " .. q .. " / " .. num(math.pi * V3.radius_cap * V3.radius_cap) .. ") * " ..
    factor("distance")
end

-- the quantity of a body_tiles cone, and that cone's mean height
function M.body_quantity(h)
  return (V3.body_tiles / (math.pi * h.rq * h.rq)) ^ V3.body_power
end
function M.body_height(h)
  return M.body_quantity(h) ^ V3.cube_root / (math.pi * h.rq * h.rq)
end

return M
