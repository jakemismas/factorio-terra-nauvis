-- Control stage: event wiring only (ARCHITECTURE.md, "Control stage"). Throughout, the T16
-- registration scan allows only the events of ARCHITECTURE.md's event table: never on_tick or
-- on_nth_tick, and no per-chunk event outside scripts/bandfix.lua. It wires the
-- guards: world detection and the Map type notice in on_init, the missing-name guard and the drift
-- line in on_configuration_changed, the withheld-preset warning in both, and the notice and the
-- stored warnings to each created player. It also wires the start (the resolved city, the
-- start message and the RSO warning; from ridges also the cliff "none" reset) after world detection,
-- and the D33 surface guard on every new surface and as a sweep in on_init and on_configuration_changed
-- (surfaces made inside an on_init raise no event, S11). Destroyed Europe adds to the start the
-- D12 warning (Destroyed Europe on without Alien Biomes), stored like the RSO warning for every created
-- player (design rule 25). For Exact coastlines, after world detection on_init records
-- the save's band-fix key, and on_init and on_load register scripts/bandfix.lua's on_chunk_generated
-- handler from that record only (a save without the key registers nothing, the one conditional
-- registration); its drift line joins on_configuration_changed. Then come the D28 city
-- markers: drawn in on_init when their runtime-global setting is on, and drawn or removed when it
-- changes. bandfix.on_init runs before start.on_init because the start ore guarantee reads the tiles the
-- band fix writes.
local guards = require("scripts.guards")
local start = require("scripts.start")
local bandfix = require("scripts.bandfix")
local markers = require("scripts.markers")

script.on_init(function()
  guards.on_init()
  bandfix.on_init()
  start.on_init()
  markers.on_init()
  guards.sweep_surfaces()
end)

script.on_load(bandfix.on_load)

script.on_configuration_changed(function(data)
  guards.on_configuration_changed(data)
  bandfix.on_configuration_changed(data)
  guards.sweep_surfaces()
end)

script.on_event(defines.events.on_surface_created, guards.on_surface_created)
script.on_event(defines.events.on_player_created, guards.on_player_created)
script.on_event(defines.events.on_runtime_mod_setting_changed, markers.on_setting_changed)
