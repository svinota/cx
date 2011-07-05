"""
Logging subsystem
"""

# 	Copyright (c) 2005-2008 Peter V. Saveliev
#
# 	This file is part of Connexion project.
#
# 	Connexion is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 3 of the License, or
# 	(at your option) any later version.
#
# 	Connexion is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with Connexion; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from cxcore.thread import Thread
import logging
import types

class log:

	def __init__(self,bus,disconnect=False):
		self.bus = bus
		self.__disconnect = disconnect

	def __del__(self):
		try:
			if self.__disconnect:
				self.bus.put("dispatcher2",{"disconnect": self.bus.address})
		except:
			pass

	def log(self,level,message):
		'''
		A function to ease logging via dispatcher2
		'''
		self.bus.put("logger",(level,message))

class logger(Thread):
	'''
	Logger thread

	Do not use remote logging, implemented by Python `logging` module.
	Use internal messaging to a remote connexion instance, it will go
	through secure channel.
	'''
	level = {
		"critical":	(logging.CRITICAL,	logging.critical),
		"error":	(logging.ERROR,		logging.error),
		"warning":	(logging.WARNING,	logging.warning),
		"info":		(logging.INFO,		logging.info),
		"debug":	(logging.DEBUG,		logging.debug),
	}

	def __init__(self,name="logger",file=None,level="warning"):
		Thread.__init__(self)
		self.setName(name)
		logging.basicConfig(filename=file, level=self.level[level][0], format='%(asctime)s: (%(levelname)s) %(message)s')
		self.level["info"][1]("logger thread %s startup" % (self.getName()))

	def run(self):
		while True:
			addr = {}
			message = self.bus.get(addr)

			# print message

			if type(message) == types.DictType:
				if "map" in message.keys():
					if message["map"] == "rpdb":
						try:
							import rpdb2
							self.level["debug"][1]("%s: starting rpdb2" % (self.getName()))
							rpdb2.start_embedded_debugger(message["argv"][0])
						except:
							self.level["debug"][1]("%s: no rpdb2 found, continuing w/o debugging" % (self.getName()))


			elif type(message) == types.StringType:
				if self.magic(message):
					return

			elif type(message) == types.TupleType:
				s = addr["from"].split("@")
				if len(s) > 1:
					system = s[1]
				else:
					system = "local"
				self.level[message[0]][1]("[%s] %s" % (system, message[1]))

	def magic(self,text):
		if text == "shutdown":
			self.level["info"][1]("logger thread %s shutdown" % (self.getName()))
			return True

		elif text in self.level.keys():
			logging.getLogger().setLevel(self.level[text][0])

		return False
