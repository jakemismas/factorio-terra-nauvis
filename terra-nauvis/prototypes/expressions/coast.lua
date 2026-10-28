-- Coast and elevation expressions (ARCHITECTURE.md, "Expression graph").
--
-- Milestone toolchain ships only the placeholder shape: the placeholder map's world extent at the
-- placeholder scale is land with vanilla terrain inside, and everything beyond it is an endless
-- ocean. The world origin sits at the corner of the placeholder's spawn pixel, near the extent's
-- west edge, so a preview at the spawn shows the coast and differs from vanilla. europe-coast
-- replaces all of it with the coordinate chain, the coast fit and tn_land_coarse, and retires these
-- names. Every coordinate and constant comes from config.lua (S-5).
local cfg = require("prototypes.config")

local P = cfg.placeholder
local map = cfg.maps[P.map]

local function num(v)
  return string.format(cfg.number_format, v)
end

-- Tile x = (u - col) s and y = (v - row) s for continuous pixel coordinates (u, v) at scale s,
-- with (col, row) the spawn pixel, so the extent spans x from -col s to (W - col) s and y from
-- -row s to (H - row) s.
local s = P.scale
local col, row = P.spawn_px[1], P.spawn_px[2]
local x_lo, x_hi = -col * s, (map.width_px - col) * s
local y_lo, y_hi = -row * s, (map.height_px - row) * s

-- Signed distance to the nearest edge of the extent in tiles, positive inside.
local edge = "min(x - (" .. num(x_lo) .. "), (" .. num(x_hi) .. ") - x, y - (" .. num(y_lo) .. "), (" ..
  num(y_hi) .. ") - y)"

-- Vanilla terrain inside, a coast along the edge and deep water offshore. The redirect reads
-- elevation_nauvis, never elevation, which it replaces.
--
-- The start mask: vanilla's starting_resources_lake_mask reads elevation per starting-ore
-- candidate, which on this preset would carry the placeholder shape into the Entity program
-- (design constraint 3). The preset points that key at this copy of vanilla 2.1.23's body, which
-- reads elevation_nauvis instead, so the Entity program keeps vanilla's land field.
data:extend({
  {
    type = "noise-expression",
    name = P.names.elevation,
    expression = "max(" .. num(P.sea_floor) .. ", min(elevation_nauvis, " .. edge .. " / " ..
      num(P.shore_tiles) .. "))",
  },
  {
    type = "noise-expression",
    name = P.names.starting_resources_lake_mask,
    expression = "clamp((elevation_nauvis - " .. num(P.start_mask_floor) .. ") / " .. num(P.start_mask_span) ..
      ", 0, 1)",
  },
})
