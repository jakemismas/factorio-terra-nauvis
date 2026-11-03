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

-- vanilla's mean regular ore per tile at distance d, q / (pi r^2) of the typical spot, r = min(radius_cap,
-- rq q^(1/3)); written as the larger of its two branches, so it reads 0, not 0 / 0, where the fade leaves no quantity
local function mean_per_tile(h, d)
  local q = "(" .. num(h.mean_size) .. " * " .. quantity(h, d) .. ")"
  return num(V3.per_tile_fit) .. " * max(" .. q .. " ^ " .. num(V3.cube_root) .. " / " ..
    num(math.pi * h.rq * h.rq) .. ", " .. q .. " / " .. num(math.pi * V3.radius_cap * V3.radius_cap) .. ") * " ..
    factor(d)
end

-- P(d): what a hotspot's per tile is per_tile times: vanilla's mean regular ore per tile at the real distance, held
-- to flat_ratio / per_tile times the regular ore's own (the flattened distance, flat_distance below), so a far field
-- stays flat_ratio times as rich per tile as the regular ore round it and its total spreads over more tiles (Jake
-- 15:50: hotspots always take up a decent area); near fields, where the first is the lower, are unchanged
function M.per_tile(h)
  return "min(" .. mean_per_tile(h, "distance") .. ", " .. num(V3.flat_ratio / V3.per_tile) .. " * " ..
    mean_per_tile(h, M.flat_distance()) .. ")"
end

-- the P(d) a field's area (its bodies' worth) is read from: per_tile's, with the held branch over flat_fit, so a far
-- field of full-size bodies, which loses less to the blob and the trim than near fields, keeps the cap tip's total
function M.area_per_tile(h)
  return "min(" .. mean_per_tile(h, "distance") .. ", " .. num(V3.flat_ratio / V3.per_tile / V3.flat_fit) .. " * " ..
    mean_per_tile(h, M.flat_distance()) .. ")"
end

-- W1(d): the body_tiles cones one unit of k asks for at the amount setting, L(d) over the area per_tile * P(d) asks
-- of each (area_fit takes back what the outline and the room trim)
function M.unit_bodies(h)
  return num(V3.area_fit / (V3.per_tile * V3.body_tiles)) .. " * " .. cfg.keys.hotspot_amount .. " * " ..
    M.large(h) .. " / max(1, " .. M.per_tile(h) .. ")"
end

-- f(d): the share of a body_tiles cone's tiles a far field's bodies hold (config.lua hotspots_v2.v3.far)
function M.body_scale(h)
  local F = V3.far
  return "clamp(" .. num(F.k_ref / F.bodies) .. " * " .. M.unit_bodies(h) .. ", " .. num(F.least) .. ", 1)"
end

-- f ^ (body_power - 1): a far body's height and width against a body_tiles cone's
function M.height_scale(h)
  return "(" .. M.body_scale(h) .. ") ^ " .. num(V3.body_power - 1)
end

-- The distance regular ore grows by (config.lua resources.natural.flat): the real distance to the knee, then rate tiles
-- per tile to stop, then held. The curves above read the real distance, so a hotspot keeps today's numbers.
function M.flat_distance()
  local FL = cfg.resources.natural.flat
  return "(min(distance, " .. num(FL.knee) .. ") + " .. num(FL.rate) .. " * clamp(distance - " .. num(FL.knee) ..
    ", 0, " .. num(FL.stop - FL.knee) .. "))"
end

-- the quantity of a body_tiles cone, and that cone's mean height
function M.body_quantity(h)
  return (V3.body_tiles / (math.pi * h.rq * h.rq)) ^ V3.body_power
end
function M.body_height(h)
  return M.body_quantity(h) ^ V3.cube_root / (math.pi * h.rq * h.rq)
end

return M
