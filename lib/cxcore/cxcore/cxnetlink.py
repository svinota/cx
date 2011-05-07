"""
Connexion network infrastructure

It consists of three major parts:
	* UDP client/server socket for inter-cx communications
	* ZeroConf mDNS engine
	* OS network control subsystem: for Linux, it is [rt]netlink

"""

# 	Copyright (c) 2008 Peter V. Saveliev
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

from ctypes import *
from socket import AF_INET, SOL_SOCKET, SO_REUSEADDR, SOCK_DGRAM, socket, inet_ntoa, inet_aton
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.PublicKey import ElGamal
from Crypto.Util.number import getPrime
from pickle import dumps, loads
from cxcore.thread import Timer
from cxutil.utils import RandomPool
from threading import Event
from sys import version_info
from copy import copy

import traceback
import time
import random

from cxnet.common import hline
from cxnet.utils import *
from cxutil.utils import opts
from cxutil.UID import UID
from cxnet import zeroconf

from manager import CoreThread, public, tail, CoreService, ACoreService
from logger import log

CL_PORT = 40323
CL_DOMAIN = "_cx._udp.local"

class mDNSlistener(object,log):
	'''
	mDNS cache updater
	'''

	def __init__(self,server,bus):
		self.bus = bus
		self.server = server

	def removeService(self, zeroconf, type, name):
		self.log("info","unregistered service `%s'" % (name))

	def addService(self, zeroconf, type, name):
		info = self.server.getServiceInfo(type, name)
		self.log("info","registered service `%s'" % (name))


class mDNSannouncer(zeroconf.Announcer,log):
	'''
	mDNS cache announcer
	'''
	def __init__(self,bus):
		self.bus = bus

	def signal(self,sig,action,record):
		try:

			data = opts({
				"action": action,
				"host": record.name,
			})


			if (record.clazz == zeroconf._CLASS_IN) and (record.type == zeroconf._TYPE_A):
				data["address"] = inet_ntoa(record.address)
			elif (record.clazz == zeroconf._CLASS_IN) and (record.type == zeroconf._TYPE_SRV):
				data["port"] = record.port

			elif (record.clazz == zeroconf._CLASS_IN) and (record.type == zeroconf._TYPE_TXT):
				svc = zeroconf.ServiceInfo(record.name, record.name)
				svc.setText(record.text)
				data["properties"] = opts(svc.getProperties())

				# FIXME:
				# it's a dirty hack, please isolate this code
				try:
					x = ACoreService(self.bus, "lockd")
					x.call("signal_%s" % (data["properties"]["role"]), action,
						domain = record.name[record.name.index(".") + 1:],
						alias = data["properties"]["alias"])

				except Exception,e:
					# self.log("error",traceback.format_exc())
					pass

			#self.bus.put(
			#	"state",
			#	{
			#		"map": "signal",
			#		"signal": sig,
			#		"data": data,
			#	}
			#)
		except:
			self.log("error","signal exception: %s" % (str(traceback.format_exc())))

	def add(self,record):
		self.signal(("mdns.cache",),"add",record)
		# self.log("info","cache add: %s" % (repr(record)))

	def remove(self,record):
		self.signal(("mdns.cache",),"remove",record)
		# self.log("info","cache remove: %s" % (repr(record)))

	def expire(self,record):
		self.signal(("mdns.cache",),"expire",record)
		# self.log("info","cache expire: %s" % (repr(record)))


## Common exceptions
class mDNS_AlreadyRegistered(Exception):
	def __str__(self):
		return "Domain browser for `%s` already registered" % (self.message)


## Lookup exceptions
class mDNS_ServiceNotFound(Exception):
	def __str__(self):
		return "Service not found"

class mDNS_HostNotFound(Exception):
	def __str__(self):
		return "Host not found"

class mDNS_PortNotFound(Exception):
	def __str__(self):
		return "Port not found"

class mDNS_TextNotFound(Exception):
	def __str__(self):
		return "Text not found"



class mDNSengine(CoreThread):
	'''
	ZeroConf mDNS object with browsing support
	'''

	def __init__(self, address, bus, psk, pks_private, pks_public, adaptive=True, heartbeat=False):
		# set up ZeroConf mDNS
		CoreThread.__init__(self,bus,"mDNS resolver interface")
		self.server = zeroconf.Zeroconf(address, psk, pks_private, pks_public, adaptive, heartbeat)
		self.announcer = mDNSannouncer(bus)
		self.server.addCacheHook(self.announcer)
		self.listener = mDNSlistener(self.server, self.bus)
		self.browsers = {}

	@public
	def printCache(self):
		text = "\n"
		name = ""
		for i in self.server.cache.entries():
			try:
				if name != i.name:
					text += "\n%s\n" % (i.name)
					name = i.name
				text += "\t%s\t%s\t%s\n" % (zeroconf._CLASSES[i.clazz], zeroconf._TYPES[i.type], i)
			except:
				pass
		return text

	@public
	def registerService(self,name,address=[],port=CL_PORT,type=CL_DOMAIN,properties={},records=[zeroconf._TYPE_A, zeroconf._TYPE_SRV, zeroconf._TYPE_TXT],ttl=zeroconf._DNS_TTL,signer=None):
		# register the service and return a reference
		assert isinstance(address,list) or isinstance(address,tuple)

		svc = zeroconf.ServiceInfo(
			type='%s' % (type),
			name='%s.%s' % (name, type),
			address=map(lambda x: inet_aton(x), address),
			port=port,
			weight=0,
			priority=0,
			properties=properties,
			records=records,
			ttl=ttl,
			signer=signer
		)
		self.server.registerService( svc )
		# FIXME: return weak reference
		return svc

	@public
	def registerDomain(self,domain):
		# set up mDNS browser
		if domain in self.browsers.keys():
			raise mDNS_AlreadyRegistered(domain)
		else:
			self.browsers[domain] = zeroconf.ServiceBrowser(self.server, "%s" % (domain), self.listener)
			self.server.registerZone(self.browsers[domain])
			return self.browsers[domain]

	@public
	def lookupPTR(self,domain):
		"""
		Lookup a mDNS PTR record for a domain
		"""
		result = {}
		hosts = []
		for i in self.server.cache.entriesWithName(domain):
			if (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_PTR):
				hosts.append(i.alias)

		for i in hosts:
			if i not in result.keys():
				result[i] = "reachable"

			states = []

			for k in self.server.cache.entriesWithName(i):
				if (k.clazz == zeroconf._CLASS_IN) and (k.type == zeroconf._TYPE_A):
					states.append(k.state == "reachable")


			try:
				s = any(states)
			except:
				if version_info[:2] < (2,5):
					def _any(iterable):
						for element in iterable:
							if element:
								return True
						return False
					s = _any(states)
				else:
					raise

			if s:
				result[i] = "reachable"
			else:
				result[i] = "stale"

		return result.items()

	@public
	def getAllCache(self):
		return self.server.cache.entries()

	@public
	def getCacheAggregated(self):
		return copy(self.server.cache.cache)

	@public
	def getCache(self,host,types=[zeroconf._TYPE_A, zeroconf._TYPE_SRV, zeroconf._TYPE_TXT]):
		return filter(
			lambda x: x.type in types,
			self.server.cache.entriesWithName(host)
		)

	@public
	def lookupByIPPort(self,address,port):
		hosts = map(
			lambda x: x.name,
			self.lookupByIP(address)
		)
		return filter(
			lambda x: (x.name in hosts) and (x.port == port),
			filter(
				lambda x: (x.clazz == zeroconf._CLASS_IN) and (x.type == zeroconf._TYPE_SRV),
				self.server.cache.entries()
			)
		)[0].name

	@public
	def lookupByIP(self,address):
		return filter(
			lambda x: inet_ntoa(x.address) == address,
			filter(
				lambda x: (x.clazz == zeroconf._CLASS_IN) and (x.type == zeroconf._TYPE_A),
				self.server.cache.entries()
			)
		)

	@public
	def lookupAll(self,host,domain=None,nowait = False):

		types = [zeroconf._TYPE_A, zeroconf._TYPE_SRV, zeroconf._TYPE_TXT]

		if not domain:
			domain = host[host.index(".") + 1:]

		if not self.server.cache.entriesWithName(host):
			if nowait:
				raise mDNS_ServiceNotFound()
			else:
				self.server.getServiceInfo(domain, host)

		pool = []
		port = None
		properties = None

		for i in self.server.cache.entriesWithName(host):
			if (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_A):
				pool.append(i)
			elif (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_SRV):
				port = i.port
			elif (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_TXT):
				properties = i.properties

		return map(
			lambda x: ((inet_ntoa(x.address), port), properties, x),
			pool
		)


	@public
	def lookup(self,host,domain=None,types=[zeroconf._TYPE_A, zeroconf._TYPE_SRV],nowait=False):
		"""
		Lookup a mDNS entry for address, port or text
		"""

		if not domain:
			domain = host[host.index(".") + 1:]

		if not self.server.cache.entriesWithName(host):
			if nowait:
				raise mDNS_ServiceNotFound()
			else:
				self.server.getServiceInfo(domain, host)

		svc = zeroconf.ServiceInfo(domain, host)

		pool = {
			"reachable": [],
			"stale": [],
		}

		for i in self.server.cache.entriesWithName(host):
			if (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_A):
				if i.state in pool.keys():
					pool[i.state].append(i)
			elif (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_SRV):
				svc.port = i.port
			elif (i.clazz == zeroconf._CLASS_IN) and (i.type == zeroconf._TYPE_TXT):
				svc.setText(i.text)

		if len(pool["reachable"]) > 0:
			rec = random.choice(pool["reachable"])
		elif len(pool["stale"]) > 0:
			rec = random.choice(pool["stale"])
		else:
			rec = None

		if rec:
			address = inet_ntoa(rec.address)
		else:
			address = None

		if (not rec) and (zeroconf._TYPE_A in types):
			raise mDNS_HostNotFound()

		if (not svc.port) and (zeroconf._TYPE_SRV in types):
			raise mDNS_PortNotFound()

		if (not svc.text) and (zeroconf._TYPE_TXT in types):
			raise mDNS_TextNotFound()

		return ((address,svc.getPort()),svc.getProperties(),rec)


###
#
# Connexion protocol definition (FIXME: one should extract
# this out to cxnet lib)
#
# 8<---------------------------------------------------------------------
#
# Temporary protocol structure
#
# +--------+--------+--------+--------+
# |              msg_len              |
# +--------+--------+--------+--------+
# |               nonce               |
# +--------+--------+--------+--------+
# |     version     |      flags      |
# +--------+--------+--------+--------+
# |              fragment             |
# +--------+--------+--------+--------+
# | alg_len|  ...   |  ...   |  ...   |
# +--------+--------+--------+--------+
# |           ... data ...            |
# +-----------------------------------+
#
class cxhdr(BigEndianStructure):
	'''
	'''
	# BE == network byte order, so, we do not need
	# hton[sl]() and ntoh[sl]()
	_fields_ = [
		("msg_len",	c_uint32),
		("nonce",       c_uint32),
		("version",	c_uint16),
		("flags",	c_uint16),
		("fragment",	c_uint32), # so, max message size == CX_MAX_MSG * 2 ^ 32 (CX_MAX_FRAGMENT)
		("alg_len",	c_uint8),
		("pad",		c_byte * 3),
	]


CX_PROTO_VERSION = 2

CX_MAX_LENGTH = 256
CX_MAX_FRAGMENT = pow(2,32)
CX_MAX_MSG = CX_MAX_LENGTH - sizeof(cxhdr)


# flag				value		bit No
CX_FLAGS_FIRST_FRAGMENT		= 0x001		# 1	create storage structure
CX_FLAGS_FINAL_FRAGMENT		= 0x002		# 2	start reassembling
CX_FLAGS_MORE_FRAGMENTS		= 0x004		# 3	just store fragment
CX_FLAGS_RESET_NONCE		= 0x008		# 4	reset nonce and send AES key
CX_FLAGS_KX_REQ			= 0x010		# 5	key exchange request
CX_FLAGS_KX_RESP		= 0x020		# 6	key exchange response

CX_MSG_TRACK			= 0x100		# 9
CX_MSG_ECHO			= 0x200		# 10
CX_MSG_DROP			= 0x400		# 11

class cxmsg(Structure):
	'''
	'''
	_fields_ = [
		("header",	cxhdr),
		("data",	c_byte * CX_MAX_MSG),
	]
# 8<---------------------------------------------------------------------
#
###

###
#
# packet debug hooks
def skip(*argv):
	pass

def dump(bus,packet,size,line="packet"):
	bus.put("logger",("debug", "%s:\n%s" % (line,hline(packet,size))))

class cl_socket(object, log):
	'''
	UDP client/server socket for inter-cx communications

	Provides [un]reliable encrypted transport for inter-cx communications
	'''

	sock = None
	fd = None

	key = None
	cipher = None
	block = None
	rand = None

	recv_buffer = None
	send_buffer = None

	bus = None

	def __init__(self,address,port,bus,mdns,psk,pks_private,pks_public,debug=False):
		'''
		address		- IP address to bind to
		port		- UDP port to use
		bus 		- internal bus to send debug to

		key	or
		keyfile		- initialize cipher key from string or file
		block		- cipher block size

		debug		- turn packet logging on/off
		'''

		log.__init__(self,bus)

		self.block = 16
		self._nonce = 0

		# encryption
		self.rand = RandomPool(CX_MAX_LENGTH)
		self.psk = psk
		self.pks_private = pks_private					# key, suitable to sign messages
		self.pks_public = pks_public					# map for public sign keys
		self.enc_private = ElGamal.generate(1024,self.rand.get_bytes)	# key, suitable to encrypt messages
		self.enc_public = {}						# map for public encryption keys

		# host-specific maps
		self.emap = {}		# event map
		self.nmap = {}		# nonce map
		self.nkeys = {}		# key map

		# socket operations
		self.sock = socket(AF_INET,SOCK_DGRAM)
		self.sock.setsockopt(SOL_SOCKET,SO_REUSEADDR,1)
		self.sock.bind((address,port))
		self.fd = self.sock.fileno()

		# buffers & headers
		self.recv_buffer = create_string_buffer(CX_MAX_LENGTH)
		self.send_buffer = create_string_buffer(CX_MAX_LENGTH)
		self.reasm_buffer = {}
		self.finish_buffer = {}
		self.watch = {}

		# services
		self.mdns = mdns
		# debug hook
		if debug:
			self.hook = dump
		else:
			self.hook = skip

	def nonce(self):
		self._nonce += 1
		return self._nonce


	def prime(self,size=140):
		return getPrime(size,self.rand.get_bytes)

	def recv(self):
		'''
		Receive a packet and put it into the buffer for reassembling
		'''
		try:
			(bytes,(address,port)) = self.sock.recvfrom_into(self.recv_buffer)

		# python < 2.5
		except:
			if version_info[:2] < (2,5):
				(s,(address,port)) = self.sock.recvfrom(CX_MAX_LENGTH)
				x = create_string_buffer(s)
				memmove(self.recv_buffer,x,sizeof(x))
			else:
				raise

		# parse header
		header = cxhdr.from_address(addressof(self.recv_buffer))
		if header.version < CX_PROTO_VERSION:
			return

		try:
			origin = self.mdns.lookupByIPPort(address,port)
		except:
			return

		if (header.flags & CX_FLAGS_RESET_NONCE) and (header.flags & CX_FLAGS_FIRST_FRAGMENT):
			self.nmap[origin] = 0

		#for i in map(lambda x: x.name, self.mdns.lookupByIP(address)):
		if (address,origin) in self.watch.keys():
				self.watch[(address,origin)].state = "reachable"
				del self.watch[(address,origin)]

		## watch flags
		if (header.flags & CX_MSG_ECHO) and (header.flags & CX_FLAGS_FIRST_FRAGMENT):
			for i in map(lambda x: x.name, self.mdns.lookupByIP(address)):
				(host,prop,record) = self.mdns.lookup(i)
				self._send(origin,host,None,record,0,CX_MSG_DROP)

		if header.flags & CX_MSG_DROP:
			return

		# drop duplicates
		if origin not in self.nmap.keys():
			self.nmap[origin] = 0

		self.log("debug","Nonce: %s" % (header.nonce))
		self.log("debug","Map: %s" % (self.nmap[origin]))
		self.log("debug","Flags: %s" % (header.flags))

		if header.nonce <= self.nmap[origin]:
			if (origin,header.nonce) not in self.reasm_buffer.keys():
				self.log("debug","dropped old nonce not in self.reasm_buffer")
				return
			elif header.flags & CX_FLAGS_FIRST_FRAGMENT:
				self.log("debug","dropped old nonce with CX_FLAGS_FIRST_FRAGMENT flag")
				return
			self.log("debug","accepted old nonce in self.reasm_buffer")
		else:
			self.nmap[origin] = header.nonce
			self.log("debug","nonce for an origin incremented")

		# get plaintext message and load it
		self.hook(self.bus, self.recv_buffer, header.msg_len + sizeof(header), "cl_socket.recv()")
		n = string_at( addressof(self.recv_buffer) + sizeof(header), header.msg_len )
		self.store(origin,header,n)

	def store(self,origin,header,message):
		'''
		Store fragments
		'''
		key = (origin,header.nonce)
		if key not in self.reasm_buffer.keys():
			self.reasm_buffer[key] = {}
			self.finish_buffer[key] = 0

		if header.fragment in self.reasm_buffer[key].keys():
			# possible duplicate
			return

		try:

			# shortcut
			buf = self.reasm_buffer[key]

			# store fragment
			buf[header.fragment] = (header,message)

			#
			if header.flags & CX_FLAGS_FINAL_FRAGMENT:
				# store max fragment number
				self.finish_buffer[key] = header.fragment
				# drop all invalid fragments?
				while max(buf.keys()) > self.finish_buffer[key]:
					del buf[max(buf.keys())]

			#
			if self.finish_buffer[key] > 0:
				# if FIN packet already received, try to reassemble
				if len(buf.keys()) == self.finish_buffer[key]:
					self.reassemble(origin, header, key, buf)
		except:
			traceback.print_exc()
			self.log("debug","corrupted buffer `%s`: fragment dropped" % (header.nonce))
			return

	def reassemble(self,origin,header, key, buf):
		'''
		Reassemble fragments
		'''
		items = buf.items()
		items.sort(lambda x,y: cmp(x[0],y[0]))
		data = ""

		for (i,k) in items:
			data += k[1]

		# delete reassemble buffer
		del self.reasm_buffer[key]
		del self.finish_buffer[key]

		self.log("debug","Start reassembling for %s with flags %s" % (origin,header.flags))

		if header.flags & CX_FLAGS_KX_REQ:
			# subprotocol
			p = loads(data)
			self.log("debug","<< %s << %s" % (origin,p))
			hsh = MD5.new(p[0]).digest()
			if self.psk:
				if not self.pks_private.verify(hsh,p[1]):
					self.log("debug","Drop wrong key for %s" % (origin))
					return
			else:
				if not self.pks_public[origin].verify(hsh,p[1]):
					self.log("debug","Drop wrong key for %s" % (origin))
					return

			key = loads(p[0])

			if origin in self.enc_public.keys():
				if key == self.enc_public[origin]:
					self.log("debug","drop same public key for origin %s" % (origin))
					return

			self.log("debug","changing public key for origin %s" % (origin))
			self.enc_public[origin] = key
			akey = self.rand.get_bytes(16)
			self.nkeys[origin] = AES.new(akey,AES.MODE_CBC)
			self.send(origin,dumps(key.encrypt(akey,self.prime())),CX_FLAGS_KX_RESP)

		elif header.flags & CX_FLAGS_KX_RESP:
			# subprotocol
			p = loads(data)
			self.log("debug","<< %s << %s" % (origin,p))
			akey = self.enc_private.decrypt(loads(data))
			self.nkeys[origin] = AES.new(akey,AES.MODE_CBC)
			self.emap[origin].set()

		else:
			if origin not in self.nkeys.keys():
				return
			data = self.decrypt(origin, data,k[0].alg_len)
			msg = loads(data)
			# localize recipient (FIXME: no forwarding yet)
			msg["to"] = msg["to"].split("@")[0]
			self.log("debug","<< %s << %s" % (origin,msg))

			self.bus.tx.put(msg)


	def watchdog(self,host):
		if host in self.watch.keys():
			self.watch[host].state = "stale"
			del self.watch[host]

	def send(self,h,packet,flags=0):
		if (h not in self.pks_public.keys()) and not self.psk:
			self.log("error","has no public key for host %s, abort send operation" % (h))
			return
		if h not in self.nkeys.keys():
			pool = self.mdns.lookupAll(h)
			if not any (
					map (
						lambda x: x[2].state == "reachable", pool
					)
				):
				return

			key = dumps(self.enc_private.publickey())
			hsh = MD5.new(key).digest()
			p = dumps((key,self.pks_private.sign(hsh,self.prime())))
			nonce = self.nonce()
			self.emap[h] = Event()

			for (host,prop,record) in pool:
				self._send(h,host,p,record,nonce,CX_FLAGS_KX_REQ | CX_FLAGS_RESET_NONCE)
			self.emap[h].wait(5)
			if self.emap[h].isSet():
				del self.emap[h]
				self.log("debug","emap[%s] is set" % (h))
			else:
				for (host,prop,record) in pool:
					record.state = "stale"
					self.watch[(host[0],h)] = record
				return

		nonce = self.nonce()
		pool = self.mdns.lookupAll(h)
		for (host,prop,record) in pool:
			self._send(h,host,packet,record,nonce,flags)

	def _send(self,h,host,packet,record,nonce,flags=0):
		'''
		Encrypt and send a packet
		'''
		self.log("debug", ">> %s (%s) >> %s" % (h,record,packet))
		try:
			# create a message
			msg = cxmsg()
			msg.header.nonce = nonce

			# encrypt payload
			if \
				not (flags & CX_FLAGS_KX_REQ) and \
				not (flags & CX_FLAGS_KX_RESP):
				c = dumps(packet)
				(c,a) = self.encrypt(h,c)
				msg.header.alg_len = a
			else:
				c = packet

			if flags & CX_MSG_TRACK:
				self.watch[(host[0],h)] = record
				Timer(2,self.watchdog,((host[0],h),)).start()

			offset = 0
			fragment = 1
			while (offset < len(c)) and (fragment < CX_MAX_FRAGMENT):
				msg.header.flags = flags

				if offset == 0:
					msg.header.flags |= CX_FLAGS_FIRST_FRAGMENT

				cf = c[offset:offset + CX_MAX_MSG]
				offset += CX_MAX_MSG

				# create ctypes string buffer from this string
				x = create_string_buffer(cf,len(cf))
				# copy the buffer to the packet
				memmove(addressof(msg) + sizeof(msg.header),addressof(x),len(cf))
				# NOTE: I don't know, why c_char * CX_MAX_MSG does not work.
				# FIXME: fix it later...

				# construct header
				msg.header.msg_len = len(cf)
				msg.header.version = CX_PROTO_VERSION
				msg.header.fragment = fragment
				fragment += 1

				if offset >= len(c):
					msg.header.flags |= CX_FLAGS_FINAL_FRAGMENT
				else:
					msg.header.flags |= CX_FLAGS_MORE_FRAGMENTS


				self.hook(self.bus, msg, msg.header.msg_len + sizeof(msg.header), "cl_socket.send()")

				# send a packet
				self.sock.sendto(string_at(addressof(msg),msg.header.msg_len + sizeof(msg.header)),host)

		except Exception,e:
			self.log("error","cl_socket.send(): %s" % (e))
			self.log("debug","%s" % (traceback.format_exc()))
			return

	def decrypt(self,h,data,a):
		'''
		Decrypt data
		'''
		# strip IV and alignment data
		if a:
			return self.nkeys[h].decrypt(data)[self.block:-a]
		else:
			return self.nkeys[h].decrypt(data)[self.block:]

	def encrypt(self,h,data):
		'''
		Encrypt data with block cipher
		'''
		# create IV
		data = self.rand.get_bytes(self.block) + data

		# calculate alignment
		a = ((len(data) + self.block - 1) & ~ (self.block - 1)) - len(data)

		# justify data with random string
		data += self.rand.get_bytes(a)

		# encrypt it
		# return:
		#	* ciphertext
		#	* alignment length
		return (self.nkeys[h].encrypt(data),a)


class CXmutexCreateException(Exception):
	def __str__(self):
		return "cannot create distributed mutex: %s" % (self.message)

class CX_NoLeader(Exception):
	def __str__(self):
		return "no leader for domain %s" % (self.message)

class CX_MultipleLeaders(Exception):
	def __str__(self):
		return "multiple leaders for domain %s" % (self.message)


HEARTBEAT_TTL = 2
class cl_lockd(CoreThread):
	'''
	Connexion locking daemon

	'''

	def __init__(self,bus,mdns,alias):

		CoreThread.__init__(self,bus,"lockd")

		self.mdns = mdns
		self.alias = alias
		self.ds = {}
		self.wd = {}

	@public
	def init(self,mutex,addr=None):

		domain = mutex.domain
		mutex.uid = UID()

		###
		#
		# Register mutex domain, if not exists
		#
		###
		if domain not in self.ds.keys():
			# for each mutex domain there is a structure that holds info about:
			self.ds[domain] = opts({
				"uid": mutex.uid,	# uuid of the service
				"svc": None,		# ServiceInfo reference
				"queue": [],		# queue of uninitialized mutexes, without leader
				"counter": 0,		# election counter
				"queues": {},		# mutex queues, each queue is a list of tuples (node address, service ID)
				"watchdog": None	# election watchdog
			})

			try:
				# register service
				self.ds[domain]["svc"] = self.mdns.registerService(
					name = mutex.uid,
					type = domain,
					records = [zeroconf._TYPE_TXT],
					properties = {
						"role": "candidate",
						"alias": self.alias,
					},
					ttl = HEARTBEAT_TTL,
					signer = self.alias
				)
			except Exception,e:
				self.log("error","domain registration error: `%s`" % (e))
				return e

	def getRing(self,domain):
		'''
		Get all host names for a zone (domain)
		'''
		ring = self.mdns.lookupPTR(domain)
		ring.sort()
		return map(lambda x: x[0], ring)

	def getLeader(self,domain):
		'''
		Get a leader for a zone (domain), or raise an exception:

		* CX_MultipleLeaders
		* CX_NoLeader
		'''

		ring = self.getRing(domain)

		# lookup a leader
		leader = None
		for i in ring:
			try:
				((address,port),properties,record) = self.mdns.lookup(i,domain=domain,types=[zeroconf._TYPE_TXT],nowait=True)

				if (properties["role"] == "leader"):
					if leader:
						# FIXME: log possible attack
						self.log("warning","multiple leaders: possible attack")
						raise CX_MultipleLeaders(domain)
					else:
						leader = properties["alias"]
			except CX_MultipleLeaders:
				raise
			except:
				pass

		if not leader:
			raise CX_NoLeader(domain)

		return leader

	def assertMutex(self,domain,name,sid):
		while True:
			try:
				if self.ds[domain].queues[name][0][1] == sid:
					yield self.ds[domain].queues[name]
					return
			except:
				pass

			yield None

	def assertLeader(self,domain):
		while True:
			try:
				yield self.getLeader(domain)
				return
			except CX_NoLeader:
				self.runElection(domain)
			except:
				pass
			yield None

	@public
	@tail
	def acquire(self, mutex, watchdog=True, addr=None):


		domain = mutex.domain
		name = mutex.name
		sid = "%s.%s" % (self.ds[domain]["uid"], domain)
		uid = "%s.%s" % (name, domain)

		for leader in self.assertLeader(domain):
			if not leader: yield None
		self.log("debug","leader asserted: %s" % (leader))

		if not self._t_acquire(mutex, uid, 20):
			self.wd[uid] = False

		for mutex in self.assertMutex(domain,name,sid):
			if not mutex: yield None

		if self.wd[uid]:
			try:
				self.wd[uid].cancel()
			except:
				pass

			self.log("debug","mutex asserted: %s" % (mutex))
			del self.wd[uid]

		else:
			# we can reach this code only after mutex acquisition timeout
			# so, return False
			self.log("error","cannot acquire mutex `%s`" % (mutex))
			del self.wd[uid]
			yield False
			return

		yield True

	def _t_acquire(self, mutex, uid, countdown = 0):

		domain = mutex.domain
		name = mutex.name
		sid = "%s.%s" % (self.ds[domain]["uid"], domain)

		# try to find mutex in the list
		try:
			if sid in map(lambda x: x[1], self.ds[domain].queues[name]):
				self.log("debug","mutex already queued, request/watchdog aborted")
				self.wd[uid] = True
				return False
		except:
			pass

		if countdown > 0:
			if uid in self.wd.keys():
				try:
					self.wd[uid].cancel()
				except:
					pass
			self.wd[uid] = Timer(5,self._t_acquire,[mutex,uid,countdown - 1])
			self.wd[uid].start()
			self.log("debug","mutex acquire watchdog started")
		else:
			self.log("critical","timed out, watchdog aborted")
			self.wd[uid] = False
			return False

		try:
			x = ACoreService(self.bus,"lockd@%s" % (self.getLeader(domain)),flags=CX_MSG_TRACK)
			x.cl_acquire(domain,name,sid)

		except CX_NoLeader:
			self.runElection(domain)
		except:
			pass

		return True

	@public
	@tail
	def release(self,mutex,addr=None):

		leader = None
		domain = mutex.domain
		name = mutex.name

		uid = "%s.%s" % (name, domain)

		for leader in self.assertLeader(domain):
			if not leader: yield None

		self.log("debug","leader asserted: %s" % (leader))

		self._t_release(mutex,uid,20)

	def _t_release(self,mutex,uid,countdown = 0):

		domain = mutex.domain
		name = mutex.name
		sid = "%s.%s" % (self.ds[domain]["uid"], domain)

		# try to find mutex in the list
		try:
			if sid not in map(lambda x: x[1], self.ds[domain].queues[name]):
				self.log("debug","mutex dequeued, request/watchdog aborted")
				return
		except:
			pass

		if countdown > 0:
			if uid in self.wd.keys():
				try:
					self.wd[uid].cancel()
				except:
					pass
			self.wd[uid] = Timer(5,self._t_release,[mutex,countdown - 1])
			self.wd[uid].start()
			self.log("debug","mutex release watchdog started")
		else:
			self.log("critical","timed out, watchdog aborted")
			return False

		try:
			x = ACoreService(self.bus,"lockd@%s" % (self.getLeader(domain)))
			x.cl_release(domain,name,sid)
		except CX_NoLeader:
			self.runElection(domain)
		except:
			pass

		return True


	@public
	def cl_update(self,domain,name,queue,addr=None):
		self.ds[domain]["queues"][name] = queue
		self.cl_check_dead(domain,name,queue)

	def cl_announce(self,domain,name,q):
		for i in self.getRing(domain):
			try:
				((address,port),properties,record) = self.mdns.lookup(i,domain=domain,types=[zeroconf._TYPE_TXT],nowait=True)

				x = ACoreService(self.bus,"lockd@%s" % (properties["alias"]))
				x.cl_update(domain,name,q)

			except:
				pass

	def cl_check_dead(self,domain,name,q):
		# validate address
		while q:
			_sid = q[0][1]
			try:
				# get service record from DNS for this alias
				for i in self.getRing(domain):
					if i == _sid:
						self.log("debug","sid %s validated: found a live mutex lock" % (_sid))
						break
				else:
					raise Exception("sid %s seems to be dead" % (_sid))

				# so far we have a correct lock in the queue, abort
				break
			except:
				# dead mutex, clean up

				# silently drop what release returns, because
				# mutex owner is dead and there is no need to
				# alert him
				self.log("info","drop dead mutex lock for %s / %s" % q[0])
				self.cl_release(domain, name, _sid, addr = q[0][0])

		if q:
			return q[0]

	@public
	def cl_acquire(self,domain,name,sid,addr):
		self.log("debug","acquire request for `%s` from `%s`" % (name, addr))
		qs = self.ds[domain]["queues"]
		rq = None

		try:
			q = qs[name]
		except:
			q = qs[name] = []

		if q:
			rq = self.cl_check_dead(domain, name, q)

		# one should queue mutex only if there is no such sid in the queue:
		# we can receive duplicates
		if sid not in map(lambda x: x[1], q):
			q.append((addr,sid))
		else:
			self.log("warning","double lock attempt for `%s:%s:%s`" % (domain, name, addr))

		self.cl_announce(domain, name, q)

	@public
	def getQueue(self):
		return self.ds

	@public
	def cl_release(self,domain,name,sid,addr=None):
		qs = self.ds[domain]["queues"]
		try:
			q = qs[name]
		except:
			self.log("warning","release request for non-existent mutex `%s` from node `%s`" % (name, addr))
			return

		i = q[0][1]
		if sid != i:
			self.log("warning","release for mutex `%s` from non-owner `%s`" % (name, addr))
			return

		q.pop(0)
		self.cl_announce(domain, name, q)

		self.log("debug","release request for `%s` from `%s`" % (name, addr))

	def watchElection(self,domain):
		self.ds[domain].watchdog = None
		try:
			self.getLeader(domain)
		except CX_NoLeader:
			self.forceElection(domain)

	def forceElection(self,domain):

		# start election algorithm
		self.log("debug","election started for `%s`" % (domain))

		self.ds[domain]["svc"].setProperty("role","candidate")
		self.ds[domain]["counter"] += 1
		if not self.ds[domain]["watchdog"]:
			self.ds[domain]["watchdog"] = Timer(5,self.watchElection,[domain])
			self.ds[domain]["watchdog"].start()
			self.log("debug","election watchdog started for `%s`" % (domain))

		a = self.getNext(domain)
		if a:
			x = ACoreService(self.bus,"lockd@%s" % (a))
			x.relayElection(domain,self.ds[domain]["uid"],self.ds[domain]["counter"])

	def runElection(self,domain):

		if self.ds[domain]["counter"]:
			self.log("debug","election already rinning")
			return

		self.forceElection(domain)

	@public
	def relayElection(self,domain,uid,counter,addr=None):
		live = False
		node = ""

		# got to relay election
		euid = self.ds[domain]["uid"]
		self.log("debug","got relayElection() with euid=%s, uid=%s and counter=%s" % (euid,uid,counter))

		# 1. check for dead mutexes:
		for (i,k) in self.ds[domain].queues.items():
			# i -- mutex name
			# k -- mutex queue
			self.cl_check_dead(domain,i,k)

		# 2. send our token (if we are not in the process)
		if self.ds[domain]["counter"] < counter:
			self.log("debug","send our token")
			self.ds[domain]["counter"] = counter
			a = self.getNext(domain)
			if a:
				x = ACoreService(self.bus,"lockd@%s" % (a))
				x.relayElection(domain,euid,self.ds[domain]["counter"])

		# 3. analyze received token
		if uid == euid:
			self.log("debug","became a leader")
			# our token or it's our mutex in the head: we're leader
			self.ds[domain]["svc"].setProperty("role","leader")
			self.ds[domain]["svc"].ttl = HEARTBEAT_TTL

		elif uid < euid:
			self.log("debug","respect priority")
			# respect priority
			a = self.getNext(domain)
			if a:
				self.log("debug","forward a token to %s" % (a))
				x = ACoreService(self.bus,"lockd@%s" % (a))
				x.relayElection(domain,uid,counter)

			self.ds[domain]["svc"].setProperty("role","candidate")

			# The scheme with only one beacon in the network
			# requires leadership migration with mutex acquisition.
			#
			# While we're not ready to make this great step for
			# mankind, use _all_ nodes for beacons
			self.ds[domain]["svc"].ttl = HEARTBEAT_TTL

		else:
			self.log("debug","drop a token")
			# just drop the token
			pass

	def getNext(self,domain):
		while True:
			ring = self.getRing(domain)
			ring.sort()
			print "DEBUG",ring
			try:
				idx = ring.index("%s.%s" % (self.ds[domain]["uid"], domain))
			except:
				self.log("critical", traceback.format_exc())
				return

			if idx > 0:
				idx -= 1
			else:
				idx = len(ring) - 1

			next = ring[idx]
			try:
				((address,port),properties,record) = self.mdns.lookup(next,domain=domain,types=[zeroconf._TYPE_TXT],nowait=True)
				return properties["alias"]
			except Exception,e:
				self.log("debug","lookup error %s for host `%s` domain `%s`" % (e,next,domain))

	@public
	def signal_candidate(self,action,domain,alias,addr=None):

		# check for dead mutexes:
		for (i,k) in self.ds[domain].queues.items():
			# i -- mutex name
			# k -- mutex queue
			self.cl_check_dead(domain,i,k)

		try:
			if (action == "add") and (alias != self.alias):
				# replicate mutex table for the domain
				for (i,k) in self.ds[domain].queues.items():
					# i -- mutex name
					# k -- mutex queue
					x = ACoreService(self.bus,"lockd@%s" % (alias))
					x.cl_update(domain,i,k)

		except Exception,e:
			self.log("error","candidates update error: %s" % (e))

	@public
	def signal_leader(self,action,domain,alias,addr=None):

		# FIXME: get this out to a separate method

		# check for dead mutexes:
		for (i,k) in self.ds[domain].queues.items():
			# i -- mutex name
			# k -- mutex queue
			self.cl_check_dead(domain,i,k)

		if action == "add":
			self.ds[domain].counter = 0
			try:
				self.ds[domain].watchdog.cancel()
				self.ds[domain].watchdog = None
				self.log("debug","election watchdog for `%s` aborted" % (domain))
			except:
				pass
		else:
			self.runElection(domain)



class cl_mutex(object):

	def __init__(self,bus,name,domain):

		self.lockd = "lockd"
		self.name = name
		self.domain = domain
		self.bus = bus.put2("dispatcher2","connect")
		self.x = ACoreService(self.bus,self.lockd)
		self.y = CoreService(self.bus,self.lockd)
		self.x.init(self)

	def acquire(self):
		return self.y.acquire(self)

	def release(self):
		self.x.release(self)


class net_setup(object):
	'''
	Abstracts network control procedures like 'get interface', 'set route'
	and so on, and so forth.
	'''
	pass
