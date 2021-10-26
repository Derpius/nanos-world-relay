local function decodePayload(payload)
	Members, Roles, Emotes = {}, {}, {}
	for id, member in pairs(payload.members) do
		Members[id] = Member(id, member.username, member["display-name"], member.avatar, member.discriminator, member.roles)
	end

	for id, role in pairs(payload.roles) do
		Roles[id] = Role(id, role.name, Color(role.colour[1], role.colour[2], role.colour[3]))
	end

	for id, emote in pairs(payload.emotes) do
		Emotes[id] = Emote(id, emote.name, emote.url)
	end
end

local rawPayload = ""
function UpdateInfo()
	Server.HTTPRequest(
		"http://" .. RELAY_CONNECTION, "/", "PATCH", "", "", false,
		{["Source-Port"] = tostring(Server.GetPort())},
		function(statusCode, content)
			if statusCode ~= 200 then return end
			rawPayload = content

			Events.BroadcastRemote("DiscordRelay.InfoPayload", content)
			decodePayload(JSON.parse(content))
		end
	)
end

-- Clients will send this whenever they init to request the server's data
Player.Subscribe("Ready", function(player)
	Events.CallRemote("DiscordRelay.InfoPayload", player, rawPayload)
end)
