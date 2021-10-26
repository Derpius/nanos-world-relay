RELAY_CONNECTION = "127.0.0.1:8080"
RELAY_INTERVAL = 16

Package.Require("Relay.lua")

local commands = {
	relay_connection = function(constr)
		RELAY_CONNECTION = constr
	end,
	relay_interval = function(interval)
		interval = tonumber(interval)
		if not interval then interval = 16 end
		RELAY_INTERVAL = interval
	end,
	relay_start = StartRelay,
	relay_stop = StopRelay,
	dsay = DSay
}
setmetatable(commands, {
	__index = function(self, k)
		Package.Log("Unknown command '" .. tostring(k) .. "'")
	end
})

Server.Subscribe("Console", function(argstr)
	local args = string.Split(argstr)
	local command = table.remove(args, 1)
	
	if commands[command] then commands[command](table.unpack(args)) end
end)
