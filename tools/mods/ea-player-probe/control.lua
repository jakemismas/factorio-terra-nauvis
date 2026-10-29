-- T18's player path: can a headless run create a player, so that on_player_created fires?
-- 2.1.23's runtime-api.json lists create_test_player only on LuaSimulation (UNVERIFIED in a game until
-- this probe). The probe looks the method up on the game object of a normal map and records the
-- answer, the player count and the connected player count.
script.on_init(function()
  local ok, err = pcall(function()
    return game.create_test_player
  end)
  local out = {create_test_player_available = ok and err ~= nil, error = (not ok) and tostring(err) or nil,
               players = #game.players, connected = #game.connected_players, is_multiplayer = game.is_multiplayer()}
  helpers.write_file("ea-player-probe/player.json", helpers.table_to_json(out), false)
  log("ea-player-probe: create_test_player available: " .. tostring(out.create_test_player_available))
end)
