"""
Threading prototypes
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

import types
from cxcore.thread import Thread
from Queue import Queue
from cxutil.utils import opts
from cxutil.UID import UID
from logger import log
import traceback
import gc

def public(func):
	func.rpc_public = True
	return func

def tail(func):
	func.rpc_tail = True
	return func

def rpc_alias(alias):
	def f(func):
		func.rpc_alias = alias
		return func
	return f

def passive(glist):
	'''
	Deprecated
	'''
	def f(func):
		glist.append(func.func_name)
		return func
	return f

def push(glist):
	'''
	Deprecated
	'''
	def f(func):
		glist[func.func_name] = None
		return func
	return f

CP_VERSION = (0,2)

class BaseCoreService(log):
	'''
	Function-fabrique
	'''
	def __init__(self,bus,addr,flags=0,disconnect=False):
		log.__init__(self,bus,disconnect)
		self.addr = addr
		self.flags = flags


class CoreService (BaseCoreService):
	'''
	Synchronous calls

	sample:
		x = CoreService(bus,addr)
		result = x.func(param,pam,pam)
	'''
	def __getattr__(self,key):
		if key == "addr":
			return self.addr
		elif key[:2] == "__":
			return BaseCoreService.__getattr__(self,key)
		elif key == "call":
			def f(*argv,**kwarg):
				key = argv[0]
				argv = list(argv)
				argv.pop(0)
				self.bus.put2(
					self.addr,
					{
						"map": key,
						"version": CP_VERSION,
						"argv": argv,
						"sync": False,
						"kwarg": kwarg,
					},
					flags=self.flags
				)
			return f
		else:
			def f(*argv,**kwarg):
				ret = self.bus.put2(
					self.addr,
					{
						"map": key,
						"version": CP_VERSION,
						"argv": argv,
						"sync": True,
						"kwarg": kwarg,
					},
					flags=self.flags
				)
				if ret["error"]:
					self.log("debug","raising exception: %s" % (ret["data"]))
					raise Exception(ret["error"])
				return ret["data"]
			return f

class ACoreService (BaseCoreService):
	'''
	Asynchronous calls

	sample:
		x = ACoreService(bus,addr)
		x.func(param,pam,pam)
	'''

	def __getattr__(self,key):
		if key == "addr":
			return self.addr
		elif key[:2] == "__":
			return BaseCoreService.__getattr__(self,key)
		elif key == "call":
			def f(*argv,**kwarg):
				key = argv[0]
				argv = list(argv)
				argv.pop(0)
				self.bus.put(
					self.addr,
					{
						"map": key,
						"version": CP_VERSION,
						"argv": argv,
						"sync": False,
						"kwarg": kwarg,
					},
					flags=self.flags
				)
			return f
		else:
			def f(*argv,**kwarg):
				self.bus.put(
					self.addr,
					{
						"map": key,
						"version": CP_VERSION,
						"argv": argv,
						"sync": False,
						"kwarg": kwarg,
					},
					flags=self.flags
				)
			return f

class CoreThread (opts,log,Thread):
	'''
	A manager object, an event handler for dispatcher2
	'''

	def __init__(self,bus,name, _dct=None):
		if _dct is None:
			dct = {}
		else:
			dct = _dct
		opts.__init__(self,dct)
		log.__init__(self,bus,True)
		Thread.__init__(self)

		self.setName(name)

		self.__generator_queue = []
		self.__delay_queue = Queue()
		self.__func_acl = []
		self.__shutdown = False

		self.public = {}
		self.generators = []

		for i in dir(self):
			x = getattr(self,i)
			try:
				if x.rpc_public:
					if hasattr(x,"rpc_alias"):
						self.public[x.rpc_alias] = x
					else:
						self.public[i] = x
			except:
				pass
			try:
				if x.rpc_tail:
					self.generators.append(i)
			except:
				pass

	@public
	def rpdb(self, *argv, **kwarg):
		try:
			import rpdb2
			self.log("debug","%s: starting rpdb2" % (self.getName()))
			rpdb2.start_embedded_debugger(argv[0])
		except:
			self.log("debug","%s: no rpdb2 found, continuing w/o debugging" % (self.getName()))


	@public
	def shutdown(self,*argv,**kwarg):
		self.log("debug","%s: got to shut down" % (self.getName()))
		self.__shutdown = True

	def allow(self,*argv):
		if not argv:
			self.__func_acl = []
		else:
			# new function acl
			self.__func_acl = argv
		# invalidate delay queue
		while True:
			try:
				(addr,message) = self.__delay_queue.get_nowait()
				self.bus.loopback(addr,message)
			except:
				self.log("debug","queue invalidation: %s" % (traceback.format_exc()))
				break

	def run(self):
		while not self.__shutdown:
			addr = {}
			message = self.bus.get(addr)

			try:
				if message["version"] != CP_VERSION:
					self.log("warning","incompatible protocol version %s from address %s" % (message["version"],addr["from"]))
					continue
			except:
				if message == "shutdown":
					return
				self.log("warning","unsupported protocol from %s" % (addr["from"]))
				continue


			result = {
				"version": CP_VERSION,
				"data": None,
				"error": None,
			}
			target = message["map"]
			sync = message["sync"]
			func = None

			if target in self.public.keys():
				func = self.public[target]
				import inspect
				spec = inspect.getargspec(func)
				if spec[1] or spec[2] or ('addr' in spec[0]):
					message['kwarg']['addr'] = addr
				if  \
					(self.__func_acl and (target in self.__func_acl)) or \
					(not self.__func_acl):

					if target in self.generators:
						###
						#
						# Create and enqueue tail generator
						#
						###
						self.__generator_queue.append([addr["from"],func(*message["argv"],**message["kwarg"]),sync,True])
						sync = False

					else:
						###
						#
						# Run ordinary function and return a message
						#
						###
						try:
							result["data"] = func(*message["argv"],**message["kwarg"])
						except Exception,e:
							result["error"] = str(e)
							result["data"] = traceback.format_exc()
							self.log("critical",traceback.format_exc())

					self.send(addr["from"],result,sync)
				else:
					self.log("debug","method `%s` not allowed right now, put the call in the delay queue" % (target))
					self.__delay_queue.put((addr["from"],message))
					self.log("debug","delay queue size: %s" % (self.__delay_queue.qsize()))

			else:
				self.log("error","unknown symbol %s" % (target))

			###
			#
			# Iterate passive generators
			#
			###
			i = 0
			while True:
				try:
					(addr,generator,sync,valid) = self.__generator_queue[i]
					# run iterator
					m = generator.next()
					if (m is not None) and valid:
						result["data"] = m
						self.send(addr,result,sync)
						if sync:
							# valid
							self.__generator_queue[i][3] = False
					i += 1
				except StopIteration:
					# if empty, pop it from the list
					if valid and sync:
						self.send(addr,result,sync)
					self.__generator_queue.pop(i)
				except IndexError:
					# end of queue, break the cycle
					break
				except Exception,e:
					result["data"] = traceback.format_exc()
					result["error"] = str(e)
					self.send(addr,result,sync)
					self.log("error","error while running iterator: %s" % (traceback.format_exc()))

	def send(self,addr,message,sync=False):
		try:
			if "to" in message["data"].keys():
				addr = message["data"]["to"]
		except:
			pass

		if not sync:
			message = message["data"]

		if ((message is not None) and not sync) or sync:
			self.bus.put(addr,message)
