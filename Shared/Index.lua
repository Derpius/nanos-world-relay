string.Split = function(self, sep)
	if not sep then
		sep = "%s"
	end

	local t = {}
	local count = 0

	for str in string.gmatch(self, "([^"..sep.."]+)") do
		count = count + 1
		t[count] = str
	end

	return t
end

function string.SetChar(str, pos, char)
	return str:sub(1, pos - 1) .. char .. str:sub(pos + 1)
end

-- Manual CurTime
local startTime = os.clock()
function CurTime()
	return os.clock() - startTime
end

Members, Roles, Emotes = {}, {}, {}

Package.Require("API.lua")
Package.Require("Types.lua")
Package.Require("InfoPayload.lua")
