-- The rows of the third hotspot table: the second table's rows (hotspot_rows_v2.lua) less the ones the third retires,
-- then its own (config.lua hotspots_v3; ARCHITECTURE.md, release versioning rule 14). A pure read of the tables, so
-- that the bodies built from it agree on one order. rich is the third table's per-row factor on ore per tile.
local V2 = require("prototypes.hotspot_rows_v2")
local T3 = require("prototypes.tables.hotspots_v3")

local retired = {}
for _, id in ipairs(T3.retired) do
  retired[id] = true
end

local rows = {}
for _, r in ipairs(V2.rows) do
  if not retired[r.id] then
    rows[#rows + 1] = r
  end
end
for _, r in ipairs(T3.rows) do
  rows[#rows + 1] = r
end

return {rows = rows, rivals = T3.rivals, rich = T3.rich, frame_offset = V2.frame_offset}
