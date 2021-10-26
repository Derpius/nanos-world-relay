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

Events.Subscribe("DiscordRelay.InfoPayload", function(rawPayload)
	decodePayload(JSON.parse(rawPayload))
end)
