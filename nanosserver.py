import re
from typing import List

class Info:
	'''Server info struct'''
	def __init__(self, name: str):
		self.name = name

class Player:
	'''Player info struct'''
	def __init__(self, id: str, name: str):
		self.id = id
		self.name = name

class NanosServer: pass # Forward declare for typehint
class NanosError(Exception):
	def __init__(self, server: NanosServer, message: str):
		self.message = "Source Server Error @ " + server._ip + ":" + str(server._port) + " | " + message
		self.rawMessage = message
		super().__init__(self.message)

# Super long regex that validates a string is a valid ip, then :, then a valid port number
CONSTR_REGEX = re.compile(r"^(?:(?:[0-9]|[0-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[0-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]):(?:[1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]|[0-5][0-9][0-9][0-9][0-9]|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$")
class NanosServer:
	'''Abstraction of a Nanos World server connection'''
	def __init__(self, constring: str):
		if not re.match(CONSTR_REGEX, constring): raise ValueError("Invalid connection string")

		self._constring = constring
		self._ip, self._port = constring.split(":")
		self._port = int(self._port)

		self.isClosed = False

	def retry(self):
		self.isClosed = False

	def close(self):
		self.isClosed = True

	def getConstring(self) -> str:
		'''Get server connection string'''
		return self._constring
	
	def ping(self, places: int = 0) -> float:
		'''Gets server ping from the bot'''
		#sendTime = time.time()
		#_ = self.info
		#return round((time.time() - sendTime) * 1000, places)
		return -1

	def getInfo(self) -> Info:
		'''Get server info'''
		return Info("Nanos World Server")

	def getPlayers(self) -> List[Player]:
		'''Get players on server'''
		return []
