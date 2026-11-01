-- The rows of the second hotspot table: the first table's rows that it keeps, then its own (ARCHITECTURE.md,
-- release versioning rule 14; config.lua hotspots_v2). A pure read of the two tables, so that the bodies built
-- from it agree on one order.
local T1 = require("prototypes.tables.hotspots")
local T2 = require("prototypes.tables.hotspots_v2")

local retired = {}
for _, id in ipairs(T2.retired) do
  retired[id] = true
end

local rows = {}
for _, r in ipairs(T1.rows) do
  if not retired[r.id] then
    local s = T2.strength[r.id]
    if s then
      local copy = {}
      for k, v in pairs(r) do
        copy[k] = v
      end
      copy.strength = s
      r = copy
    end
    rows[#rows + 1] = r
  end
end
for _, r in ipairs(T2.rows) do
  rows[#rows + 1] = r
end

return {rows = rows, rivals = T2.rivals, frame_offset = T1.frame_offset}
