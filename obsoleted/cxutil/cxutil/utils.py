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

import types
from os import WIFEXITED, WEXITSTATUS, fstat
from popen2 import Popen3
import re

urandom = None

def fetch(opts,key,default):
	'''
	'''
	if key in opts.keys():
		return opts[key]
	else:
		return default


def intersection(a, b):
	'''
	Fast intersection of two lists
	'''
	it = {}
	ad = {}
	for i in a:
		ad[i] = 1
	for i in b:
		if i in ad.keys():
			it[i] = 1
        return it.keys()

def exclusion(a, b):
	'''
	Fast list exclusion
	'''
	bd = {}
	it = {}
	for i in b:
		bd[i] = 1
	for i in a:
		if i not in bd.keys():
			it[i] = 1
	return it.keys()

def subtract(d1,d2):
	'''
	Subtract d1 from d2
	'''
	for i in d1.keys():
		if i in d2.keys():
			if (type(d1[i]) == types.ListType) and (type(d2[i]) == types.ListType):
				for k in d1[i]:
					try:
						d2[i].remove(k)
					except:
						pass
			elif \
				((type(d1[i]) == types.DictType) or (type(d1[i]) == type(opts()))) and\
				((type(d2[i]) == types.DictType) or (type(d2[i]) == type(opts()))):
				subtract(d1[i],d2[i])
			else:
				del d2[i]

def merge(d1,d2):
	'''
	Merge d1 into d2
	'''
	for i in d1.keys():
		if i not in d2.keys():
			d2[i] = d1[i]
		else:
			if (type(d1[i]) == types.ListType) and (type(d2[i]) == types.ListType):
				for k in d1[i]:
					if not k in d2[i]:
						d2[i].append(k)
			elif \
				((type(d1[i]) == types.DictType) or (type(d1[i]) == type(opts()))) and\
				((type(d2[i]) == types.DictType) or (type(d2[i]) == type(opts()))):
				merge(d1[i],d2[i])


def nsort(xI,yI):
	'''
	Compare two string word by word, taking numbers in account
	'''
	x = xI.split()
	y = yI.split()
	r = re.compile("^[0-9]+$")

	lx = len(x)
	ly = len(y)

	for i in xrange(lx):

		# type mask
		mask = 0

		# check, if ly <= i
		if ly <= i:
			# yI > xI
			return 1

		# check word types
		if r.match(x[i]):
			kx = int(x[i])
			mask |= 2
		else:
			kx = x[i]

		if r.match(y[i]):
			ky = int(y[i])
			mask |= 1
		else:
			ky = y[i]

		# string > int
		if mask == 1:
			# kx -- string
			# ky -- int
			# kx > ky
			return 1
		if mask == 2:
			# kx -- int
			# ky -- string
			# kx < ky
			return -1

		# both strings or ints
		if kx != ky:
			if kx > ky:
				return 1
			if kx < ky:
				return -1

	# ly > lx
	return -1

class opts(object):
	'''
	Pseudo-dict object
	'''
	__dct__ = None
	__hidden__ = [
		"__init__",
		"__getitem__",
		"__setitem__",
		"__setattr__",
		"keys",
		"items",
		"dump_recursive",
		"__str__",
		"__hidden__",
		"__dct__",
	]

	def __init__(self, _dct = None):
		object.__setattr__(self,"__dct__",{})
		if _dct is None:
			dct = {}
		else:
			dct = _dct
		merge(dct,self)

	def __getitem__(self,key):
		return self.__dct__[key]

	def __delitem__(self,key):
		if not key in self.__hidden__:
			del self.__dct__[key]
			try:
				object.__delattr__(self,key)
			except:
				pass

	def __delattr__(self,key):
		self.__delitem__(key)

	def __setitem__(self,key,value):
		self.__setattr__(key,value)

	def __setattr__(self,key,value):
		if type(value) == types.DictType:
			value = opts(value)
		if type(key) == types.StringType:
			if \
				(not key in self.__hidden__) and \
				(re.match("^[a-zA-Z_]+$",key)):
				object.__setattr__(self,key,value)
		self.__dct__[key] = value

	def keys(self):
		return self.__dct__.keys()

	def items(self):
		return self.__dct__.items()

	def dump_recursive(self,prefix = ""):
		t = ""
		for (i,k) in self.items():
			t += "%s%s: " % (prefix,i)
			if type(k) == type(self):
				t += "\n"
				t += k.dump_recursive(prefix + "\t")
			else:
				t += str(k)
				t += ";\n"
		return t

	def __str__(self):
		return "%s" % (self.__dct__)

class Executor(object):
	'''
	Shell/exec launcher

	Runs a command in the subshell or via fork'n'exec (see the class constructor).
	'''

	data = None
	lines = None

	edata = None
	elines = None

	pid = None
	ret = None

	def __init__(self,command,fc=True):
		'''
		Creates object _and_ runs a command

		command	- a command to run
		fc	- `fast call` - whether to run via fork'n'exec (True)
			  or in the subshell (False)
		'''
		if fc:
			command = command.split()

		inst = Popen3(command,True,-1)
		(o,i,e) = (inst.fromchild, inst.tochild, inst.childerr)

		self.pid = inst.pid

		self.elines = e.readlines()
		self.lines = o.readlines()

		ret = inst.wait()
		if WIFEXITED(ret):
			self.ret = WEXITSTATUS(ret)
		else:
			self.ret = 255

		i.close()
		o.close()
		e.close()

		self.edata = ""
		self.data = ""

		for i in self.lines:
			self.data += i

		for i in self.elines:
			self.edata += i

	def __str__(self):
		return self.data.strip()

class RandomPool (object):

	size = None

	def __init__ (self,size):
		self.size = None

	def get_bytes(self,_size = None):
		global urandom
		try:
			fstat(urandom.fileno())
		except:
			urandom = open("/dev/urandom","r")

		if _size is None:
			size = self.size
		else:
			size = _size
		return urandom.read(size)

class PSK (object):
	def __init__(self,t,bits):
		rp = RandomPool(bits//8)
		self.type = t
		self.bits = bits
		self.psk = rp.get_bytes(self.bits//8)
		if t == "AES":
			self.block = 16
		else:
			self.block = 8

	def __getstate__(self):
		o = self.__dict__.copy()
		if "key" in o.keys():
			del o["key"]
		return o

	def __setstate__(self,d):
		self.__dict__.update(d)
		exec("from Crypto.Cipher import %s as module" % (self.type))
		self.key = module.new(self.psk,module.MODE_CBC)
		self.rp = RandomPool(self.bits//8)

	def randomize(self):
		while self.rp.entropy < self.bits:
			self.rp.add_event()

	def __repr__(self):
		return "<PSK instance for %s type key (%s bits)>" % (self.type,self.bits)

	def encrypt(self,s):
		return self.key.encrypt(self.rp.get_bytes(self.block) + s)

	def decrypt(self,s):
		return self.key.decrypt(s)[self.block:]

	def sign(self,h,p):
		return self.encrypt(h)

	def verify(self,h,s):
		return self.decrypt(s) == h

	def can_encrypt(self):
		return 1

	def can_sign(self):
		return 1

	def has_private(self):
		return True
