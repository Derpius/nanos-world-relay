local string_find, string_lower = string.find, string.lower
local _ipairs, _pairs = ipairs, pairs

local table_insert, table_sort = table.insert, table.sort

local function sortedFind(tbl, match)
	-- Get matches
	local matches = {}
	for _, v in _pairs(tbl) do
		local weight = match(v)
		if weight then table_insert(matches, {weight, v}) end
	end

	-- Sort
	table_sort(matches, function(a, b) return a[1] < b[1] end)

	-- Clean table
	for i, v in _ipairs(matches) do matches[i] = matches[i][2] end

	return matches
end

-- Members
-- Get the entire member table
function GetMembers()
	return Members
end

-- Get a member by id
function GetMember(id)
	return Members[id]
end

-- Get a list of members who match the given name (sorted by importance descending)
function FindMembersByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(Members, function(member)
		local matchIdx = string_find(
			caseSensitive and member:GetDisplayName() or string_lower(member:GetDisplayName()),
			name, 1, noPatterns
		)

		if not matchIdx then
			matchIdx = string_find(
				caseSensitive and member:GetUsername() or string_lower(member:GetUsername()),
				name, 1, noPatterns
			)

			if matchIdx then
				return matchIdx * 10 -- Heavily weight only username matches to the end
			end
		end

		return matchIdx
	end)
end

-- Roles
-- Get the entire roles table
function GetRoles()
	return Roles
end

-- Get a role by id
function GetRole(id)
	return Roles[id]
end

-- Get a list of roles that match the given name (sorted by importance descending)
function FindRolesByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(Roles, function(role)
		return string_find(
			caseSensitive and role:GetName() or string_lower(role:GetName()),
			name, 1, noPatterns
		)
	end)
end

-- Emotes
-- Get the entire emote table
function GetEmotes()
	return Emotes
end

-- Get an emote by id
function GetEmote(id)
	return Emotes[id]
end

-- Get a list of emotes that match the given name (sorted by importance descending)
function FindEmotesByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(Emotes, function(emote)
		return string_find(
			caseSensitive and emote:GetName() or string_lower(emote:GetName()),
			name, 1, noPatterns
		)
	end)
end

-- Exports
Package.Export("GetMembers", GetMembers)
Package.Export("GetMember", GetMember)
Package.Export("FindMembersByName", FindMembersByName)
Package.Export("GetRoles", GetRoles)
Package.Export("GetRole", GetRole)
Package.Export("FindRolesByName", FindRolesByName)
Package.Export("GetEmotes", GetEmotes)
Package.Export("GetEmote", GetEmote)
Package.Export("FindEmotesByName", FindEmotesByName)
