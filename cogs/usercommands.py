from datetime import timedelta
from typing import Union

import discord
from discord.ext import commands

from nanosserver import NanosError

def formatTimedelta(delta: timedelta) -> str:
	'''Utility to convert timedelta to formatted string'''
	days, seconds = delta.days, delta.seconds
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	seconds = seconds % 60

	datetimeStr = []
	if days != 0: datetimeStr.append(f"{days} day{'s' if days != 1 else ''}")
	if hours != 0: datetimeStr.append(f"{hours} hour{'s' if hours != 1 else ''}")
	if minutes != 0: datetimeStr.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
	if seconds != 0: datetimeStr.append(f"{seconds} second{'s' if seconds != 1 else ''}")
	return " ".join(datetimeStr)

class UserCommands(commands.Cog):
	'''Commands to be run by any user in a channel with a connection'''

	def __init__(self, bot: commands.Bot, json: dict, embedColour: int):
		self.bot = bot
		self.json = json
		self.embedColour = embedColour

	@commands.command()
	async def status(self, ctx):
		'''Tells you whether the connection to the server is closed, invalid, or open'''
		ping = None
		try: ping = self.json[str(ctx.channel.id)]["server"].ping()
		except NanosError as e:
			await ctx.message.reply("Connection to server isn't closed internally, however failed to ping the server with exception `" + e.message + "`")
			return
		
		await ctx.message.reply("Server online, ping %d. (Note that the ping is from the location of the bot)" % ping)

	@commands.command()
	async def info(self, ctx: commands.Context, infoName: str = None):
		'''Gets server info, all if no name specified'''
		await ctx.message.reply("Not implemented yet")

	@commands.command()
	async def players(self, ctx):
		'''Gets all players on the server'''
		await ctx.message.reply("Not implemented yet")

	@commands.command()
	async def rules(self, ctx, ruleName: str = None):
		'''
		Gets a rule's value from the server or all if none specified (Discord embed char limit permitting)\n
		Note, only people with manage server perms can get all rules to reduce spam
		'''
		await ctx.message.reply("Not implemented yet")

	@commands.command()
	async def notify(self, ctx, target: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to notify you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''
		affectingSelf = target is None
		if target is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != target.id:
				await ctx.message.reply(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: target = ctx.message.author

		if target.bot: await ctx.message.reply("Bots cannot be notified regarding server outage"); return

		if target.id in self.json[str(ctx.channel.id)]["toNotify"]: await ctx.message.reply("Already configured to notify " + ("you" if affectingSelf else f"<@{target.id}>"))
		else:
			self.json[str(ctx.channel.id)]["toNotify"].append(target.id)
			await ctx.message.reply(("You" if affectingSelf else f"<@{target.id}>") + " will now be notified regarding server outage")

	@commands.command()
	async def dontNotify(self, ctx, target: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to stop notifying you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''
		affectingSelf = target is None
		if target is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != target.id:
				await ctx.message.reply(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: target = ctx.message.author

		if target.id not in self.json[str(ctx.channel.id)]["toNotify"]: await ctx.message.reply("Already configured to not notify " + ("you" if affectingSelf else f"<@{target.id}>"))
		else:
			self.json[str(ctx.channel.id)]["toNotify"].remove(target.id)
			await ctx.message.reply(("You" if affectingSelf else f"<@{target.id}>") + " will no longer be notified regarding server outage")

	@commands.command()
	async def peopleToNotify(self, ctx):
		'''
		Lists all people set to be notified
		'''

		if len(self.json[str(ctx.channel.id)]["toNotify"]) == 0: # If no one is set to be notified don't bother building a message
			await ctx.message.reply(f"No one is set to be notified regarding server outage\n*use `{self.bot.command_prefix}notify` to mark yourself to be notified, and `{self.bot.command_prefix}dontNotify` to disable notifications*")
			return

		# As with the actual ping task, we save a list of valid IDs and replace the existing list with this one after the loop
		validIDs = []

		# Message to be sent
		msg = "*The following people are set to be notified regarding outage from the server linked to this channel:*\n"

		for userID in self.json[str(ctx.channel.id)]["toNotify"]:
			member = await ctx.guild.fetch_member(userID)
			if member is None: continue

			validIDs.append(userID)
			msg += (f"<@{ctx.message.author.id}>" if ctx.message.author.id == userID else "`" + member.display_name + "`") + ", "

		self.json[str(ctx.channel.id)]["toNotify"] = validIDs
		await ctx.message.reply(msg[:-2])

	# Command validity checks
	async def cog_check(self, ctx):
		if str(ctx.channel.id) not in self.json: return False

		# Handle autogenerated help command
		prefixLen = len(self.bot.command_prefix)
		if ctx.message.content[prefixLen:(prefixLen + 4)] == "help": return True

		if self.json[str(ctx.channel.id)]["server"].isClosed:
			await ctx.message.reply("Server is closed, please try again later")
			return False

		return True

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, NanosError):
			await ctx.message.reply(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, commands.errors.CheckFailure): pass
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.message.reply(f"Command missing required argument, see `{self.bot.command_prefix}help`")
		else: raise error
