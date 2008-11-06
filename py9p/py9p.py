#!/usr/bin/python
"""
9P protocol implementation as documented in plan9 intro(5) and <fcall.h>.
"""

cmdName = {}
def _enumCmd(*args) :
	num = 100
	ns = globals()
	for name in args :
		cmdName[num] = "T%s" % name
		cmdName[num+1] = "R%s" % name
		ns["T%s" % name] = num
		ns["R%s" % name] = num+1
		num += 2
	ns["Tmax"] = num

_enumCmd("version", "auth", "attach", "error", "flush", "walk", "open",
		"create", "read", "write", "clunk", "remove", "stat", "wstat")

VERSION = "9P2000"
NOTAG = 0xffff
NOFID = 0xffffffffL

DIR = 020000000000L
QDIR = 0x80
OREAD,OWRITE,ORDWR,OEXEC = range(4)
OTRUNC,ORCLOSE = 0x10,0x40

PORT = 564


def pad(str, l, padch='\0') :
	str += padch * (l - len(str))
	return str[:l]

def _applyFuncs(funcs, vals=None) :
	"""Return the results from each function using vals as an argument."""
	if vals is not None :
		x = [f(v) for f,v in zip(funcs, vals)]
	else :
		x = [f() for f in funcs]
	if len(x) == 1 :
		x = x[0]
	return x

def XXXdump(buf) :
	print " ".join(["%02x" % ord(ch) for ch in buf])

class Error(Exception) : pass
class RpcError(Error) : pass
class ServError(Error) : pass

class Sock :
	"""Provide appropriate read and write methods for the Marshaller"""
	def __init__(self, sock) :
		self.sock = sock
	def read(self, l) :
		x = self.sock.recv(l)
		while len(x) < l :
			b = self.sock.recv(l - len(x))
			if not b :
				raise Error("Client EOF")
			x += b
		return x
	def write(self, buf) :
		if self.sock.send(buf) != len(buf) :
			raise Error("short write")

class Marshal(object) :
	"""
	Class for marshalling data.

	This class provies helpers for marshalling data.  Integers are encoded
	as little endian.  All encoders and decoders rely on _encX and _decX.
	These methods append bytes to self.bytes for output and remove bytes
	from the beginning of self.bytes for input.  To use another scheme
	only these two methods need be overriden.
	"""
	verbose = 1

	def _splitFmt(self, fmt) :
		"Split up a format string."
		idx = 0
		r = []
		while idx < len(fmt) :
			if fmt[idx] == '[' :
				idx2 = fmt.find("]", idx)
				name = fmt[idx+1:idx2]
				idx = idx2
			else :
				name = fmt[idx]
			r.append(name)
			idx += 1
		return r

	def _prep(self, fmttab) :
		"Precompute encode and decode function tables."
		encFunc,decFunc = {},{}
		for n in dir(self) :
			if n[:4] == "_enc" :
				encFunc[n[4:]] = self.__getattribute__(n)
			if n[:4] == "_dec" :
				decFunc[n[4:]] = self.__getattribute__(n)

		self.msgEncodes,self.msgDecodes = {}, {}
		for k,v in fmttab.items() :
			fmts = self._splitFmt(v)
			self.msgEncodes[k] = [encFunc[fmt] for fmt in fmts]
			self.msgDecodes[k] = [decFunc[fmt] for fmt in fmts]

	def setBuf(self, str="") :
		self.bytes = list(str)
	def getBuf(self) :
		return "".join(self.bytes)

	def _checkSize(self, v, mask) :
		if v != v & mask :
			raise Error("Invalid value %d" % v)
	def _checkLen(self, x, l) :
		if len(x) != l :
			raise Error("Wrong length %d, expected %d: %r" % (len(x), l, x))

	def _encX(self, x) :
		"Encode opaque data"
		self.bytes += list(x)
	def _decX(self, l) :
		x = "".join(self.bytes[:l])
		self.bytes[:l] = []
		return x

	def _encC(self, x) :
		"Encode a 1-byte character"
		return self._encX(x)
	def _decC(self) :
		return self._decX(1)

	def _enc1(self, x) :
		"Encode a 1-byte integer"
		self._checkSize(x, 0xff)
		self._encC(chr(x))
	def _dec1(self) :
		return long(ord(self._decC()))

	def _enc2(self, x) :
		"Encode a 2-byte integer"
		self._checkSize(x, 0xffff)
		self._enc1(x & 0xff)
		self._enc1(x >> 8)
	def _dec2(self) :
		return self._dec1() | (self._dec1() << 8)

	def _enc4(self, x) :
		"Encode a 4-byte integer"
		self._checkSize(x, 0xffffffffL)
		self._enc2(x & 0xffff)
		self._enc2(x >> 16)
	def _dec4(self) :
		return self._dec2() | (self._dec2() << 16) 

	def _enc8(self, x) :
		"Encode a 4-byte integer"
		self._checkSize(x, 0xffffffffffffffffL)
		self._enc4(x & 0xffffffffL)
		self._enc4(x >> 32)
	def _dec8(self) :
		return self._dec4() | (self._dec4() << 32)

	def _encS(self, x) :
		"Encode length/data strings with 2-byte length"
		self._enc2(len(x))
		self._encX(x)
	def _decS(self) :
		return self._decX(self._dec2())

	def _encD(self, d) :
		"Encode length/data arrays with 4-byte length"
		self._enc4(len(d))
		self._encX(d)
	def _decD(self) :
		return self._decX(self._dec4())


class Marshal9P(Marshal) :
	MAXSIZE = 1024 * 1024
	msgFmt = {
		Tversion: "4S",
		Rversion: "4S",
		Tauth: "4SS",
		Rauth: "Q",
		Terror: "",
		Rerror: "S",
		Tflush: "2",
		Rflush: "",
		Tattach: "44SS",
		Rattach: "Q",
		Twalk: "[Twalk]",
		Rwalk: "[Rwalk]",
		Topen: "41",
		Ropen: "Q4",
		Tcreate: "4S41",
		Rcreate: "Q4",
		Tread: "484",
		Rread: "D",
		Twrite: "48D",
		Rwrite: "4",
		Tclunk: "4",
		Rclunk: "",
		Tremove: "4",
		Rremove: "",
		Tstat: "4",
		Rstat: "[Stat]",
		Twstat: "4[Stat]",
		Rwstat: "",
	}
	verbose = 1 # protocol level verbosity

	def __init__(self, fd) :
		self.fd = fd
		self._prep(self.msgFmt)

	def _checkType(self, t) :
		if t not in self.msgFmt :
			raise Error("Invalid message type %d" % t)
	def _checkResid(self) :
		if len(self.bytes) :
			raise Error("Extra information in message: %r" % self.bytes)

	def send(self, type, tag, *args) :
		"Format and send a message"
		self.setBuf()
		self._checkType(type)
		self._enc1(type)
		self._enc2(tag)
		_applyFuncs(self.msgEncodes[type], args)
		self._enc4(len(self.bytes) + 4)
		self.bytes = self.bytes[-4:] + self.bytes[:-4]
		if self.verbose :
			print "-->", type, tag, repr(args)
		self.fd.write(self.getBuf())

	def recv(self) :
		"Read and decode a message"
		self.setBuf(self.fd.read(4))
		size = self._dec4()
		if size > self.MAXSIZE or size < 4 :
			raise Error("Bad message size: %d" % size)
		self.setBuf(self.fd.read(size - 4))
		type,tag = self._dec1(),self._dec2()
		self._checkType(type)
		rest = _applyFuncs(self.msgDecodes[type])
		self._checkResid()
		if self.verbose :
			print "<--", type, tag, repr(rest)
		return type,tag,rest

	def _encQ(self, q) :
		type,vers,path = q
		self._enc1(type)
		self._enc4(vers)
		self._enc8(path)
	def _decQ(self) :
		return self._dec1(), self._dec4(), self._dec8()
	def _encR(self, r) :
		self._encX(r)
	def _decR(self) :
		return self._decX(len(self.bytes))

	def _encTwalk(self, x) :
		fid,newfid,names = x
		self._enc4(fid)
		self._enc4(newfid)
		self._enc2(len(names))
		for n in names :
			self._encS(n)
	def _decTwalk(self) :
		fid = self._dec4()
		newfid = self._dec4()
		l = self._dec2()
		names = [self._decS() for n in xrange(l)]
		return fid,newfid,names
	def _encRwalk(self, qids) :
		self._enc2(len(qids))
		for q in qids :
			self._encQ(q)
	def _decRwalk(self) :
		l = self._dec2()
		return [self._decQ() for n in xrange(l)]

	def _encStat(self, l, enclen=1) :
		if enclen :
			totsz = 0
			for x in l :
				size,type,dev,qid,mode,atime,mtime,ln,name,uid,gid,muid = x
				totsz = 2+4+13+4+4+4+8+len(name)+len(uid)+len(gid)+len(muid)+2+2+2+2
			self._enc2(totsz+2)

		for x in l :
			size,type,dev,qid,mode,atime,mtime,ln,name,uid,gid,muid = x
			size = 2+4+13+4+4+4+8+len(name)+len(uid)+len(gid)+len(muid)+2+2+2+2
			self._enc2(size)
			self._enc2(type)
			self._enc4(dev)
			self._encQ(qid)
			self._enc4(mode)
			self._enc4(atime)
			self._enc4(mtime)
			self._enc8(ln)
			self._encS(name)
			self._encS(uid)
			self._encS(gid)
			self._encS(muid)
	def _decStat(self, enclen=1) :
		if enclen :
			totsz = self._dec2()
		r = []
		while len(self.bytes) :
			r.append((self._dec2(),
				self._dec2(),
				self._dec4(),
				self._decQ(),
				self._dec4(),
				self._dec4(),
				self._dec4(),
				self._dec8(),
				self._decS(),
				self._decS(),
				self._decS(),
				self._decS()),)
		return r

class File(object) :
    """
    A File object represents an instance of a file, directory or path.
    It contains all the per-instance state for the file/dir/path.
    It is associated with a filesystem object (or occasionally with
    multiple filesystem objects at union mount points).  All file instances
    implemented by a filesystem share a single file system object.
    """

    def __init__(self, path, dev=None, parent=None) :
        """If dev is specified this must not be the root of the dev."""
        self.path = normpath(path)
        self.basename = os.path.basename(self.path)
        self.parent = parent
        self.isdir = 0
        self.dirlist = []
        self.odev = None

        self.devs = []
        if dev :
            self.devs.append(dev)
            dev.estab(self, 0)
        if self.path in mountTable :
            for d in mountTable[self.path] :
                self.devs.append(d)
                d.estab(self, 1)
        if not self.devs :
            raise ServError("no implementation for %s" % self.path)
        self.dev = self.devs[0]

    def _checkOpen(self, want) :
        if (self.odev is not None) != want :
            err = ("already open", "not open")[want]
            raise ServError(err)

    def dup(self) :
        """
        Dup a non-open object.  
        N.B. No fields referenced prior to opening the file can be altered!
        """
        self._checkOpen(0)
        return copy.copy(self)

    def getQid(self) :
        type = self.dev.type
        if self.isdir :
            type |= QDIR
        return type,0,hash8(self.path)

    def walk(self, n) :
        self._checkOpen(0)
        path = os.path.join(self.path, n)
        for d in self.devs :
            fn = File(path, d, self)
            if d.walk(self, fn, n) :
                return fn

    def _statd(self, d) :
        s = list(d.stat(self))
        q = self.getQid()
        s[1] = q[0]
        s[3] = q
        s[8] = self.basename
        return s

    def stat(self) :
        # XXX return all stats or just the first one?
        return self._statd(self.dev)

    def wstat(self, stbuf) :
        self._checkOpen(0)
        self.dev.wstat(self, stbuf)
        l,t,d,q,mode,at,mt,sz,name,uid,gid,muid = st
        if name is not nochgS :
            new = normpath(os.path.join(os.path.basedir(self.path), name))
            self.path = new

    def remove(self) :
        # XXX checkOpen?
        if self.path in mountTable :
            raise ServError("mountpoint busy")
        self.dev.remove(self)

    def open(self, mode) :
        self._checkOpen(0)
        for d in self.devs :
            d.open(self, mode)
            self.odev = d

    def create(self, n, perm, mode) :
        self._checkOpen(0)
        path = os.path.join(self.path, n)
        for d in self.devs :
            fn = File(path, d, self)
            if d.exists(fn) :
                raise ServError("already exists")
        for d in self.devs :
            fn = File(path, d, self)
            if d.cancreate :
                d.create(fn, perm, mode)
                fn.odev = d
                return fn
        raise ServError("creation not allowed")

    def clunk(self) :
        if self.odev :
            self.odev.clunk(self)
            self.odev = None

    def _readDir(self, off, l) :
        if off == 0 :
            self.dirlist = []
            for d in self.devs :
                for n in d.list(self) :
                    # XXX ignore exceptions in stat?
                    path = os.path.join(self.path, n)
                    fn = File(path, d, self)
                    s = fn._statd(d)
                    self.dirlist.append(s)
        # otherwise assume we continue where we left off
        p9 = Marshal9P(None)
        p9.setBuf()
        while self.dirlist :
            # Peeking into our abstractions here.  Proceed cautiously.
            xl = len(p9.bytes)
            p9._encStat(self.dirlist[0:1], enclen=0)
            if len(p9.bytes) > l :            # backup if necessary
                p9.bytes = p9.bytes[:xl]
                break
            self.dirlist[0:1] = []
        return p9.getBuf()

    def read(self, off, l) :
        self._checkOpen(1)
        if self.isdir :
            return self._readDir(off, l)
        else :
            return self.odev.read(self, off, l)

    def write(self, off, buf) :
        self._checkOpen(1)
        if self.isdir :
            raise ServError("can't write directories")
        return self.odev.write(self, off, buf)


