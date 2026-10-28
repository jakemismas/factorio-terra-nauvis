-- PERF-15 (test notes 5.6, 7.3 item 15): vanilla elevation plus sixteen 8-octave multioctave
-- noise layers that cancel to a tiny term, so the map stays nearly vanilla while the Tile program
-- costs several times more. The benchmark-mode walker then shows which mapGenerator column carries
-- the extra cost. Wired through the planet, so a plain new map uses it (test-only).
local terms = {}
for i = 1, 16 do
  terms[#terms + 1] = "multioctave_noise{x = x, y = y, seed0 = map_seed, seed1 = " .. (9100 + i) ..
    ", octaves = 8, persistence = 0.5, input_scale = 1 / 64, output_scale = 1}"
end
data:extend{{
  type = "noise-expression",
  name = "ea_heavy_elevation",
  expression = "elevation_nauvis + 0.000001 * (" .. table.concat(terms, " + ") .. ")",
}}
data.raw.planet.nauvis.map_gen_settings.property_expression_names.elevation = "ea_heavy_elevation"
