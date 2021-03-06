from infopayload import InfoPayload
import random
import time

import discord
from discord.ext import commands, tasks

from relay import Relay

from nanosserver import NanosError, NanosServer

import re

from typing import Dict, Sequence

urlPattern = re.compile(
	r'^(?:http|ftp)s?://' # http:// or https://
	r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
	r'localhost|' #localhost...
	r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
	r'(?::\d+)?' # optional port
	r'(?:/?|[/?]\S+)$', re.IGNORECASE
)

# Server admin commands (Note, these commands can be run in any channel by people who have manage server perms, even when told not to run)
class ServerCommands(commands.Cog):
	'''Server commands to be used by anyone with manager server permissions'''

	def __init__(self, bot: commands.Bot, json: dict, relay: Relay, timeBeforeNotify: int, messageFormats: dict):
		self.bot = bot
		self.json = json
		self.relay = relay
		
		# List for logging if a server was closed automatically or not
		self.autoclosed = set()

		self.timeBeforeNotify = timeBeforeNotify
		self.messageFormats = messageFormats

		self.infoPayloads: Dict[int, InfoPayload] = {}

		self.lastAuthor = ["", 0]

		self.pingServer.start()
		self.getFromRelay.start()
	
	def getGuildInfo(self, guild: discord.Guild) -> InfoPayload:
		'''Get the appropriate InfoPayload for this context, or create one if none exists'''
		if guild.id not in self.infoPayloads:
			# Create an info payload for this guild if none exists
			payload = InfoPayload()
			
			payload.setRoles(guild.roles)
			payload.setEmotes(guild.emojis)
			payload.setMembers(guild.members)

			self.infoPayloads[guild.id] = payload
		return self.infoPayloads[guild.id]
	
	def setupConStr(self, guild: discord.Guild, constr: str):
		'''Perform initialisation for a new relaying constring'''
		self.relay.addConStr(constr)
		payload = self.getGuildInfo(guild)
		payload.addConStr(constr)
		self.relay.setInitPayload(constr, payload.encode())
	
	def removeConStr(self, guild: discord.Guild, constr: str):
		'''Perform deinitialisation of a relaying constring'''
		self.relay.removeConStr(constr)
		if guild.id in self.infoPayloads:
			self.infoPayloads[guild.id].removeConStr(constr)
	
	@commands.Cog.listener()
	async def on_ready(self):
		await self.bot.wait_until_ready()

		for channelId, serverObj in self.json.items():
			if serverObj["relay"] == 0: continue

			channel = self.bot.get_channel(int(channelId))
			if channel is None: continue
			if isinstance(channel, discord.abc.PrivateChannel): raise TypeError("This bot does not support private channels (DMs and group chats)")

			self.setupConStr(channel.guild, serverObj["server"].getConstring())

	async def cog_check(self, ctx: commands.Context):
		'''Make sure the person using these commands has manage guild permissions'''
		if not ctx.author.guild_permissions.manage_guild:
			await ctx.message.reply(f"You don't have permission to run that command <@{ctx.message.author.id}>")
			return False
		return True

	@commands.command()
	async def connect(self, ctx: commands.Context, connectionString: str):
		'''Adds a connection to a source server to this channel'''
		channelID = str(ctx.channel.id)

		# Validate the request
		if channelID in self.json:
			existingConnection = self.json[channelID]['server'].getConstring()
			if connectionString == existingConnection:
				await ctx.message.reply("This channel is already connected to that server")
				return
			await ctx.message.reply(f"This channel is already connected to `{existingConnection}`, use `{self.bot.command_prefix}disconnect` to connect to a different server")
			return

		# Attempt to connect to the server provided
		server = None
		try: server = NanosServer(connectionString)
		except NanosError as e: await ctx.message.reply("Error, " + e.rawMessage)
		except ValueError: await ctx.message.reply("Connection string invalid")
		else:
			if server.isClosed: await ctx.message.reply("Failed to connect to server")
			else:
				self.json.update({channelID: {"server": server, "toNotify": [], "time_since_down": -1, "relay": 0}})
				await ctx.message.reply("Successfully connected to server!")

	@commands.command()
	async def disconnect(self, ctx: commands.Context):
		'''Removes this channel's connection to a source server'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: await ctx.message.reply("This channel isn't connected to a server"); return

		if self.json[channelID]["relay"] == 1:
			self.removeConStr(ctx.guild, self.json[channelID]['server'].getConstring())

		del self.json[channelID]
		await ctx.message.reply("Connection removed successfully!")

	@commands.command()
	async def close(self, ctx: commands.Context):
		'''Closes the connection to the server'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: return
		if self.json[channelID]["server"].isClosed: await ctx.message.reply("Server is already closed"); return

		if self.json[channelID]["relay"] == 1:
			self.removeConStr(ctx.guild, self.json[channelID]['server'].getConstring())

		self.json[channelID]["server"].close()
		await ctx.message.reply(f"Server closed successfully!\nReconnect with `{self.bot.command_prefix}retry`")

	@commands.command()
	async def retry(self, ctx: commands.Context):
		'''Attempts to reconnect to the server'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: return
		if not self.json[channelID]["server"].isClosed: await ctx.message.reply("Server is already connected"); return
		serverCon = self.json[channelID]

		serverCon["server"].retry()
		if serverCon["server"].isClosed: await ctx.message.reply("Failed to reconnect to server")
		else:
			if serverCon["relay"] == 1:
				self.setupConStr(ctx.guild, self.json[channelID]["server"].getConstring())
			
			self.json[channelID]["time_since_down"] = -1
			await ctx.message.reply("Successfully reconnected to server!")

			if channelID in self.autoclosed:
				# Create a list of all valid user IDs
				# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
				validIDs = []

				info = serverCon["server"].getInfo()

				# For every person set to be notified, send them a DM to say the server is back online
				for personToNotify in serverCon["toNotify"]:
					member = await ctx.guild.fetch_member(personToNotify)
					if member is None: continue

					validIDs.append(personToNotify)

					await member.send(f'''
					The Source Dedicated Server `{info.name}` @ `{serverCon["server"].getConstring()}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{ctx.guild.name}`*
					''')

				self.json[channelID]["toNotify"] = validIDs
				self.autoclosed.remove(channelID)

	@commands.command()
	async def enableRelay(self, ctx: commands.Context):
		'''Enables the relay in this channel'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: await ctx.message.reply("This channel is not connected to a server"); return

		serverCon = self.json[channelID]
		if serverCon["server"].isClosed: await ctx.message.reply("Server connection is closed"); return

		if serverCon["relay"] == 1: await ctx.message.reply("The relay is already enabled"); return

		if self.relay.isConStrAdded(serverCon["server"].getConstring()):
			await ctx.message.reply("The relay is already handling this server in another channel, please disable it there first")
			return

		serverCon["relay"] = 1

		# Init on relay server
		self.setupConStr(ctx.guild, serverCon["server"].getConstring())
		
		await ctx.message.reply("Relay set successfully!")

	@commands.command()
	async def disableRelay(self, ctx: commands.Context):
		'''Disables the relay in this channel'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: await ctx.message.reply("This channel is not connected to a server"); return

		serverCon = self.json[channelID]
		if serverCon["relay"] == 0: await ctx.message.reply("The relay is already disabled"); return

		serverCon["relay"] = 0

		if not serverCon["server"].isClosed: self.removeConStr(ctx.guild, serverCon["server"].getConstring())

		await ctx.message.reply(f"Relay disabled, use `{self.bot.command_prefix}enableRelay` to re-enable")
	
	@commands.command()
	async def rcon(self, ctx: commands.Context):
		'''
		Runs a string in the relay client's console  
		(may not be supported by all clients)
		'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: await ctx.message.reply("This channel is not connected to a server"); return

		serverCon = self.json[channelID]
		if serverCon["server"].isClosed: await ctx.message.reply("The server is closed"); return
		if serverCon["relay"] == 0: await ctx.message.reply("The relay isn't enabled for this server"); return
		
		sanetised = ctx.message.content[len(self.bot.command_prefix + "rcon "):].replace("\n", ";")
		if len(sanetised) == 0:
			await ctx.message.reply("No command string specified")
			return

		self.relay.addRCON(sanetised, serverCon["server"].getConstring())
		await ctx.message.reply(f"Command `{sanetised if len(sanetised) < 256 else sanetised[:256] + '...'}` queued")
	
	@commands.command()
	async def constring(self, ctx: commands.Context):
		'''Prints the current constring of the connected server'''
		channelID = str(ctx.channel.id)
		if channelID not in self.json: await ctx.message.reply("This channel is not connected to a server"); return
		await ctx.message.reply(f"`{self.json[channelID]['server'].getConstring()}`")

	# Cog error handler
	async def cog_command_error(self, ctx: commands.Context, error):
		if isinstance(error, NanosError):
			await ctx.message.reply(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.message.reply(f"Command missing required argument, see `{self.bot.command_prefix}help`")
		elif isinstance(error, commands.errors.CheckFailure): pass
		else: raise error

	# Tasks
	def cog_unload(self):
		self.pingServer.cancel()
		self.getFromRelay.cancel()

	@tasks.loop(minutes=1)
	async def pingServer(self):
		await self.bot.wait_until_ready()

		for channelID, serverCon in self.json.items():
			if serverCon["server"].isClosed:
				if not channelID in self.autoclosed: continue # If the server was closed manually just continue
				
				# Attempt to retry the connection to the server
				serverCon["server"].retry()
				if not serverCon["server"].isClosed:
					guild = self.bot.get_channel(int(channelID)).guild

					if serverCon["relay"] == 1:
						self.setupConStr(guild, serverCon["server"].getConstring())

					self.json[channelID]["time_since_down"] = -1

					# Create a list of all valid user IDs
					# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
					validIDs = []

					# For every person set to be notified, send them a DM to say the server is back online
					for personToNotify in serverCon["toNotify"]:
						member = await guild.fetch_member(personToNotify)
						if member is None: continue

						validIDs.append(personToNotify)

						guildName = guild.name
						await member.send(f'''
						The Source Dedicated Server `{serverCon["server"].getInfo().name}` @ `{serverCon["server"].getConstring()}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
						''')

					self.json[channelID]["toNotify"] = validIDs
					self.autoclosed.remove(channelID)
				continue
			try: serverCon["server"].ping()
			except NanosError:
				self.json[channelID]["time_since_down"] += 1
				if serverCon["time_since_down"] < self.timeBeforeNotify: continue

				guild = self.bot.get_channel(int(channelID)).guild

				# Create a list of all valid user IDs
				# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
				validIDs = []

				for personToNotify in serverCon["toNotify"]:
					member = await guild.fetch_member(personToNotify)
					if member is None: continue

					validIDs.append(personToNotify)

					guildName = guild.name
					await member.send(f'''
					**WARNING:** The Source Dedicated Server `{serverCon["server"].getInfo().name}` @ `{serverCon["server"].getConstring()}` assigned to this bot is down!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
					''')

				self.json[channelID]["toNotify"] = validIDs

				serverCon["server"].close()
				if serverCon["relay"] == 1:
					self.removeConStr(guild, serverCon["server"].getConstring())

				self.autoclosed.add(channelID)
			else:
				if self.json[channelID]["time_since_down"] != -1: self.json[channelID]["time_since_down"] = -1

	@tasks.loop(seconds=0.1)
	async def getFromRelay(self):
		await self.bot.wait_until_ready()

		for channelID in self.json.keys():
			channelIDInt = int(channelID)
			serverCon = self.json[channelID]
			if serverCon["server"].isClosed or serverCon["relay"] == 0: continue

			constring = serverCon["server"].getConstring()
			msgs = self.relay.getMessages(constring)
			for msg in msgs:
				author = [msg["steamID"], time.time(), f"[{msg['teamName']}] {msg['name']}"]
				lastMsg = (await self.bot.get_channel(channelIDInt).history(limit=1).flatten())[0]

				if (
					author[0] != self.lastAuthor[0] or
					lastMsg.author.id != self.bot.user.id or
					len(lastMsg.embeds) == 0 or
					lastMsg.embeds[0].author.name != author[2] or
					author[1] - self.lastAuthor[1] > 420 or
					lastMsg.embeds[0].description == discord.Embed.Empty or
					len(lastMsg.embeds[0].description) + len(msg["message"]) > 4096
				):
					embed = discord.Embed(description=msg["message"], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"].split(",")]))
					embed.set_author(name=author[2], icon_url=msg["icon"])
					lastMsg = await self.bot.get_channel(channelIDInt).send(embed=embed)
					self.lastAuthor = author
				else:
					embed = discord.Embed(description=lastMsg.embeds[0].description + "\n" + msg["message"], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"].split(",")]))
					embed.set_author(name=author[2], icon_url=msg["icon"])
					await lastMsg.edit(embed=embed)
				
				if urlPattern.match(msg["message"]) is not None: # Message is a URL by itself, post separately for the embed
					await lastMsg.reply(msg['message'])

			# Handle custom events
			custom = self.relay.getCustom(constring)
			for body in custom:
				if len(body) == 0 or body.isspace(): continue
				await self.bot.get_channel(channelIDInt).send(body)

			# Handle death events
			deaths = self.relay.getDeaths(constring)
			for death in deaths:
				if death[3] and not death[4]: # suicide with a weapon
					await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["suicide"]).replace("{victim}", death[0]).replace("{inflictor}", death[1]))
				elif death[3]: # suicide without a weapon
					await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["suicideNoWeapon"]).replace("{victim}", death[0]))
				elif not death[4]: # kill with a weapon
					await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["kill"]).replace("{victim}", death[0]).replace("{inflictor}", death[1]).replace("{attacker}", death[2]))
				else: # kill without a weapon
					await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["killNoWeapon"]).replace("{victim}", death[0]).replace("{attacker}", death[2]))

			# Handle join and leave events
			# (joins first incase someone joins then leaves in the same tenth of a second, so the leave message always comes after the join)
			joinsAndLeaves = self.relay.getJoinsAndLeaves(constring)

			for name in joinsAndLeaves[0]:
				await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["joinMsgs"]).replace("{player}", name))
			for name in joinsAndLeaves[1]:
				await self.bot.get_channel(channelIDInt).send(random.choice(self.messageFormats["leaveMsgs"]).replace("{player}", name))

	@commands.Cog.listener()
	async def on_message(self, msg: discord.Message):
		channelID = str(msg.channel.id)
		if msg.author.bot or channelID not in self.json or self.json[channelID]["relay"] == 0 or self.json[channelID]["server"].isClosed: return

		if ( # If the message is using the command prefix, check if it's a valid command
			len(msg.content) > len(self.bot.command_prefix) and
			msg.content[:len(self.bot.command_prefix)] == self.bot.command_prefix
		):
			cmdText = msg.content[len(self.bot.command_prefix):].split()[0]
			for cmd in self.bot.commands:
				if cmd.name == cmdText: return # Don't relay the message if it's a valid bot command

		constring = self.json[channelID]["server"].getConstring()
		if msg.author.colour.value == 0: colour = (255, 255, 255)
		else: colour = msg.author.colour.to_rgb()
		if len(msg.content) != 0: self.relay.addMessage((msg.author.display_name, msg.content, "%02x%02x%02x" % colour, msg.author.top_role.name, msg.clean_content), constring)

		for attachment in msg.attachments:
			self.relay.addMessage((msg.author.display_name, attachment.url, "%02x%02x%02x" % colour, msg.author.top_role.name, attachment.url), constring)
	
	# InfoPayload Updaters
	def updatePayloadConStrs(self, payload: InfoPayload):
		'''Goes through every constring using this payload and sends them the new data'''
		for constr in payload.constrs:
			self.relay.setInitPayload(constr, payload.encode())

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		self.getGuildInfo(member.guild).updateMember(member)
		self.updatePayloadConStrs(self.infoPayloads[member.guild.id])

	@commands.Cog.listener()
	async def on_member_remove(self, member: discord.Member):
		self.getGuildInfo(member.guild).removeMember(member)
		self.updatePayloadConStrs(self.infoPayloads[member.guild.id])

	@commands.Cog.listener()
	async def on_member_update(self, _: discord.Member, after: discord.Member):
		self.getGuildInfo(after.guild).updateMember(after)
		self.updatePayloadConStrs(self.infoPayloads[after.guild.id])

	@commands.Cog.listener()
	async def on_guild_role_create(self, role: discord.Role):
		self.getGuildInfo(role.guild).updateRole(role)
		self.updatePayloadConStrs(self.infoPayloads[role.guild.id])

	@commands.Cog.listener()
	async def on_guild_role_delete(self, role: discord.Role):
		self.getGuildInfo(role.guild).removeRole(role)
		self.updatePayloadConStrs(self.infoPayloads[role.guild.id])

	@commands.Cog.listener()
	async def on_guild_role_update(self, _: discord.Role, after: discord.Role):
		self.getGuildInfo(after.guild).updateRole(after)
		self.updatePayloadConStrs(self.infoPayloads[after.guild.id])
	
	@commands.Cog.listener()
	async def on_guild_emojis_update(self, guild: discord.Guild, _: Sequence[discord.Emoji], after: Sequence[discord.Emoji]):
		self.getGuildInfo(guild).setEmotes(after)
		self.updatePayloadConStrs(self.infoPayloads[guild.id])
