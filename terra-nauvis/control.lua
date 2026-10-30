-- Control stage: event wiring only (ARCHITECTURE.md, "Control stage"). In every milestone the T16
-- registration scan allows only the events of ARCHITECTURE.md's event table: never on_tick or
-- on_nth_tick, and no per-chunk event outside scripts/bandfix.lua. Milestone europe-coast wires the
-- guards: world detection and the Map type notice in on_init, the missing-name guard and the drift
-- line in on_configuration_changed, the withheld-preset warning in both, and the notice and the
-- stored warnings to each created player. Milestone spawn-cities adds the start (the resolved city, the
-- start message and the RSO warning; from ridges also the cliff "none" reset) after world detection,
-- and the D33 surface guard on every new surface and as a sweep in on_init and on_configuration_changed
-- (surfaces made inside an on_init raise no event, S11). Nothing is registered conditionally, so
-- on_load has nothing to restore.
local guards = require("scripts.guards")
local start = require("scripts.start")

script.on_init(function()
  guards.on_init()
  start.on_init()
  guards.sweep_surfaces()
end)

script.on_configuration_changed(function(data)
  guards.on_configuration_changed(data)
  guards.sweep_surfaces()
end)

script.on_event(defines.events.on_surface_created, guards.on_surface_created)
script.on_event(defines.events.on_player_created, guards.on_player_created)
