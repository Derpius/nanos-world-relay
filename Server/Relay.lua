local toggle = false

local toPost = {}
local tickTimer = 0

function CachePost(body)
	local nonce = 1
	local key = tostring(math.floor(CurTime())) .. string.char(nonce)

	while toPost[key] do
		key = string.SetChar(key, #key, string.char(nonce))
		nonce = nonce + 1
		if nonce > 255 or (nonce > 5 and body.type ~= "message" and body.type ~= "custom") then
			Package.Log("Preventing caching messages to avoid Discord rate limiting due to spam")
			return
		end
	end

	toPost[key] = body
end

local function onChat(msg, plr)
	local teamColour = Color(1, 1, 1)
	CachePost({
		type="message",
		name=plr:GetName(), message=msg,
		teamName="Player", teamColour=("%s,%s,%s"):format(
			math.floor(teamColour.R * 255),
			math.floor(teamColour.G * 255),
			math.floor(teamColour.B * 255)
		),
		steamID = plr:GetSteamID()
	})
end

local function onJoin(plr)
	CachePost({type="join", name=plr:GetName()})
end

local function onLeave(plr)
	CachePost({type="leave", name=plr:GetName()})
end

local function onDeath(vic, _, _, damageType, _, atk)
	local vicPlr = vic:GetPlayer()
	if not vicPlr or not vicPlr:IsValid() then return end

	CachePost({
		type="death",
		victim=vicPlr:GetName(), inflictor="Not implemented yet", attacker=atk:GetName(),
		suicide=vicPlr == atk and "1" or "0", noweapon="1"
	})
end

local function onTick()
	tickTimer = (tickTimer + 1) % RELAY_INTERVAL

	local notEmpty = false
	for _, _ in pairs(toPost) do
		notEmpty = true
		break
	end

	if tickTimer == 0 and notEmpty then
		-- POST cached messages to relay server
		Server.HTTPRequest(
			"http://" .. RELAY_CONNECTION, "/", "POST",
			JSON.stringify(toPost),
			"application/json", false,
			{["Source-Port"] = tostring(Server.GetPort())},
			function() end
		)
		toPost = {}
	elseif tickTimer == math.floor(RELAY_INTERVAL / 2) then
		-- GET any available messages from relay server
		Server.HTTPRequest(
			"http://" .. RELAY_CONNECTION, "/", "GET", "", "", false,
			{["Source-Port"] = tostring(Server.GetPort())},
			function(statusCode, content)
				if statusCode ~= 200 then return end

				local json = JSON.parse(content)

				if json["init-info-dirty"] then UpdateInfo() end

				for _, msg in pairs(json.messages.chat) do
					Package.Log("[Discord | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
					local colourHex = tonumber(msg[3], 16)

					Server.BroadcastChatMessage(("<marengo>[Discord | %s]</> %s: %s"):format(msg[4], msg[1], msg[5]))
				end

				for _, command in ipairs(json.messages.rcon) do
					Package.Log("Tried to execute command from Discord, but Nanos doesn't support it yet")
				end
			end
		)
	end
end

function StartRelay()
	if toggle then return end
	toggle = true

	Server.Subscribe("Chat", onChat)
	Player.Subscribe("Ready", onJoin)
	Player.Subscribe("Destroy", onLeave)
	Character.Subscribe("Death", onDeath)
	Server.Subscribe("Tick", onTick)

	Package.Log("Relay started")
	Server.HTTPRequest(
		"http://" .. RELAY_CONNECTION, "/", "POST",
		'{"0":{"type":"custom","body":"Relay client connected!"}}',
		"application/json", false,
		{["Source-Port"] = tostring(Server.GetPort())},
		function(status) Package.Log(status) end
	)
	UpdateInfo()
end

function StopRelay()
	if not toggle then return end
	toggle = false

	Server.Unsubscribe("Chat", onChat)
	Player.Unsubscribe("Ready", onJoin)
	Player.Unsubscribe("Destroy", onLeave)
	Character.Unsubscribe("Death", onDeath)
	Server.Unsubscribe("Tick", onTick)

	Package.Log("Relay stopped")
	CachePost({type="custom", body="Relay client disconnected"})

	-- POST any remaining messages including the disconnect one
	Server.HTTPRequest(
		"http://" .. RELAY_CONNECTION, "/", "POST",
		JSON.stringify(toPost),
		"application/json", false,
		{["Source-Port"] = tostring(Server.GetPort())},
		function() end
	)
	toPost = {}
end

function DSay(...)
	if not toggle then Package.Log("Please start the relay with relay_start first") return end
	local argStr = table.concat({...}, " ")
	CachePost({type="custom", body="[CONSOLE]: " .. argStr})

	Server.BroadcastChatMessage("<marengo>Console</>: " .. argStr)
	Package.Log("Console: " .. argStr)
end
