#!/usr/bin/python
"""
9P protocol implementation as documented in plan9 intro(5) and <fcall.h>.
"""

import os.path # normpath for servers
import sys
import socket
import select
import copy

cmdName = {}
def _enumCmd(*args):
    num = 100
    ns = globals()
    for name in args:
        cmdName[num] = "T%s" % name
        cmdName[num+1] = "R%s" % name
        ns["T%s" % name] = num
        ns["R%s" % name] = num+1
        num += 2
    ns["Tmax"] = num

_enumCmd("version", "auth", "attach", "error", "flush", "walk", "open",
        "create", "read", "write", "clunk", "remove", "stat", "wstat")

version = "9P2000"
notag = 0xffff
nofid = 0xffffffffL

DIR = 020000000000L
QDIR = 0x80
OREAD,OWRITE,ORDWR,OEXEC = range(4)
OTRUNC,ORCLOSE = 0x10,0x40

PORT = 564

# maps path names to filesystem objects
mountTable = {}
klasses = {}

def pad(str, l, padch='\0'):
    str += padch * (l - len(str))
    return str[:l]

def _applyFuncs(funcs, vals=None):
    """Return the results from each function using vals as an argument."""
    if vals is not None:
        x = [f(v) for f,v in zip(funcs, vals)]
    else:
        x = [f() for f in funcs]
    if len(x) == 1:
        x = x[0]
    return x

def normpath(p):
    return os.path.normpath(os.path.abspath(p))

def hash8(obj):
    return abs(hash(obj))

def XXXdump(buf):
    print " ".join(["%02x" % ord(ch) for ch in buf])

class Error(Exception): pass
class RpcError(Error): pass
class ServerError(Error): pass
class ClientError(Error): pass


class Sock:
    """Provide appropriate read and write methods for the Marshaller"""
    def __init__(self, sock):
        self.sock = sock
        self.fid = {}   # fids are per client
    def read(self, l):
        x = self.sock.recv(l)
        while len(x) < l:
            b = self.sock.recv(l - len(x))
            if not b:
                raise Error("Client EOF")
            x += b
        return x
    def write(self, buf):
        if self.sock.send(buf) != len(buf):
            raise Error("short write")
    def fileno(self):
        return self.sock.fileno()

class Marshal(object):
    """
    Class for marshalling data.

    This class provies helpers for marshalling data.  Integers are encoded
    as little endian.  All encoders and decoders rely on _encX and _decX.
    These methods append bytes to self.bytes for output and remove bytes
    from the beginning of self.bytes for input.  To use another scheme
    only these two methods need be overriden.
    """
    verbose = 0

    def _splitFmt(self, fmt):
        "Split up a format string."
        idx = 0
        r = []
        while idx < len(fmt):
            if fmt[idx] == '[':
                idx2 = fmt.find("]", idx)
                name = fmt[idx+1:idx2]
                idx = idx2
            else:
                name = fmt[idx]
            r.append(name)
            idx += 1
        return r

    def _prep(self, fmttab):
        "Precompute encode and decode function tables."
        encFunc,decFunc = {},{}
        for n in dir(self):
            if n[:4] == "_enc":
                encFunc[n[4:]] = self.__getattribute__(n)
            if n[:4] == "_dec":
                decFunc[n[4:]] = self.__getattribute__(n)

        self.msgEncodes,self.msgDecodes = {}, {}
        for k,v in fmttab.items():
            fmts = self._splitFmt(v)
            self.msgEncodes[k] = [encFunc[fmt] for fmt in fmts]
            self.msgDecodes[k] = [decFunc[fmt] for fmt in fmts]

    def setBuf(self, str=""):
        self.bytes = list(str)
    def getBuf(self):
        return "".join(self.bytes)

    def _checkSize(self, v, mask):
        if v != v & mask:
            raise Error("Invalid value %d" % v)
    def _checkLen(self, x, l):
        if len(x) != l:
            raise Error("Wrong length %d, expected %d: %r" % (len(x), l, x))

    def _encX(self, x):
        "Encode opaque data"
        self.bytes += list(x)
    def _decX(self, l):
        x = "".join(self.bytes[:l])
        #del self.bytes[:l]
        self.bytes[:l] = []
        return x

    def _encC(self, x):
        "Encode a 1-byte character"
        return self._encX(x)
    def _decC(self):
        return self._decX(1)

    def _enc1(self, x):
        "Encode a 1-byte integer"
        self._checkSize(x, 0xff)
        self._encC(chr(x))
    def _dec1(self):
        return long(ord(self._decC()))

    def _enc2(self, x):
        "Encode a 2-byte integer"
        self._checkSize(x, 0xffff)
        self._enc1(x & 0xff)
        self._enc1(x >> 8)
    def _dec2(self):
        return self._dec1() | (self._dec1() << 8)

    def _enc4(self, x):
        "Encode a 4-byte integer"
        self._checkSize(x, 0xffffffffL)
        self._enc2(x & 0xffff)
        self._enc2(x >> 16)
    def _dec4(self):
        return self._dec2() | (self._dec2() << 16) 

    def _enc8(self, x):
        "Encode a 4-byte integer"
        self._checkSize(x, 0xffffffffffffffffL)
        self._enc4(x & 0xffffffffL)
        self._enc4(x >> 32)
    def _dec8(self):
        return self._dec4() | (self._dec4() << 32)

    def _encS(self, x):
        "Encode length/data strings with 2-byte length"
        self._enc2(len(x))
        self._encX(x)
    def _decS(self):
        return self._decX(self._dec2())

    def _encD(self, d):
        "Encode length/data arrays with 4-byte length"
        self._enc4(len(d))
        self._encX(d)
    def _decD(self):
        return self._decX(self._dec4())


class Marshal9P(Marshal):
    MAXSIZE = 1024 * 1024            # XXX
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

    verbose = 0

    def __init__(self, chatty=0):
        self._prep(self.msgFmt)
        self.verbose=chatty

    def _checkType(self, t):
        if t not in self.msgFmt:
            raise Error("Invalid message type %d" % t)
    def _checkResid(self):
        if len(self.bytes):
            raise Error("Extra information in message: %r" % self.bytes)

    def send(self, fd, type, tag, *args):
        "Format and send a message"
        self.setBuf()
        self._checkType(type)
        self._enc1(type)
        self._enc2(tag)
        _applyFuncs(self.msgEncodes[type], args)
        self._enc4(len(self.bytes) + 4)
        self.bytes = self.bytes[-4:] + self.bytes[:-4]
        if self.verbose:
            print "-%d->" % fd.fileno(), cmdName[type], tag, repr(args)
        fd.write(self.getBuf())

    def recv(self, fd):
        "Read and decode a message"
        self.setBuf(fd.read(4))
        size = self._dec4()
        if size > self.MAXSIZE or size < 4:
            raise Error("Bad message size: %d" % size)
        self.setBuf(fd.read(size - 4))
        type,tag = self._dec1(),self._dec2()
        self._checkType(type)
        rest = _applyFuncs(self.msgDecodes[type])
        self._checkResid()
        if self.verbose:
            print "<-%d-" % fd.fileno(), cmdName[type], tag, repr(rest)
        return type,tag,rest

    def _encQ(self, q):
        type,vers,path = q
        self._enc1(type)
        self._enc4(vers)
        self._enc8(path)
    def _decQ(self):
        return self._dec1(), self._dec4(), self._dec8()
    def _encR(self, r):
        self._encX(r)
    def _decR(self):
        return self._decX(len(self.bytes))

    def _encTwalk(self, x):
        fid,newfid,names = x
        self._enc4(fid)
        self._enc4(newfid)
        self._enc2(len(names))
        for n in names:
            self._encS(n)
    def _decTwalk(self):
        fid = self._dec4()
        newfid = self._dec4()
        l = self._dec2()
        names = [self._decS() for n in xrange(l)]
        return fid,newfid,names
    def _encRwalk(self, qids):
        self._enc2(len(qids))
        for q in qids:
            self._encQ(q)
    def _decRwalk(self):
        l = self._dec2()
        return [self._decQ() for n in xrange(l)]

    def _encStat(self, l, enclen=1):
        if enclen:
            totsz = 0
            for x in l:
                size,type,dev,qid,mode,atime,mtime,ln,name,uid,gid,muid = x
                totsz = 2+4+13+4+4+4+8+len(name)+len(uid)+len(gid)+len(muid)+2+2+2+2
            self._enc2(totsz+2)

        for x in l:
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

    def _decStat(self, enclen=1):
        if enclen:
            totsz = self._dec2()
        r = []
        while len(self.bytes):
            size = self._dec2()
            b = self.bytes
            self.bytes = b[0:size]
            r.append((size,
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
            self.bytes = b
            self.bytes[0:size] = []
        return r


class File(object):
    """
    A File object represents an instance of a file, directory or path.
    It contains all the per-instance state for the file/dir/path.
    It is associated with a filesystem object (or occasionally with
    multiple filesystem objects at union mount points).  All file instances
    implemented by a filesystem share a single file system object.
    """
    def __init__(self, path, dev=None, parent=None, type=None):
        """If dev is specified this must not be the root of the dev."""
        self.path = normpath(path)
        self.owner = None
        self.groups = []
        self.basename = os.path.basename(self.path)
        self.parent = parent
        self.isdir = 0
        self.dirlist = []
        self.odev = None
        self.type = type

        self.devs = []
        if dev:
            self.devs.append(dev)
            dev.estab(self, 0)
        if self.path in mountTable:
            for d in mountTable[self.path]:
                self.devs.append(d)
                d.estab(self, 1)
        if not self.devs:
            raise ServerError("no implementation for %s" % self.path)
        self.dev = self.devs[0]

    def _checkOpen(self, want):
        if (self.odev is not None) != want:
            err = ("already open", "not open")[want]
            raise ServerError(err)

    def dup(self):
        """
        Dup a non-open object.  
        N.B. No fields referenced prior to opening the file can be altered!
        """
        self._checkOpen(0)
        return copy.copy(self)

    def getQid(self):
        type = self.dev.type
        if self.isdir:
            type |= QDIR
        return type,0,hash8(self.path)

    def walk(self, n):
        self._checkOpen(0)
        path = os.path.join(self.path, n)
        for d in self.devs:
            fn = File(path, d, self)
            if d.walk(self, fn, n):
                return fn

    def _statd(self, d):
        s = list(d.stat(self))
        q = self.getQid()
        s[1] = q[0]
        s[3] = q
        s[8] = self.basename
        return s

    def stat(self):
        # XXX return all stats or just the first one?
        return self._statd(self.dev)

    def wstat(self, stbuf):
        self._checkOpen(0)
        self.dev.wstat(self, stbuf)
        l,t,d,q,mode,at,mt,sz,name,uid,gid,muid = st
        if name is not nochgS:
            new = normpath(os.path.join(os.path.basedir(self.path), name))
            self.path = new

    def remove(self):
        # XXX checkOpen?
        if self.path in mountTable:
            raise ServerError("mountpoint busy")
        if not self.dev.cancreate:
            raise ServerError("remove not allowed")
        if hasattr(self.dev, 'remove'):
            self.dev.remove(self)
        else:
            raise ServerError("dev can not remove")

    def open(self, mode):
        self._checkOpen(0)
        for d in self.devs:
            d.open(self, mode)
            self.odev = d

    def create(self, n, perm, mode):
        self._checkOpen(0)
        path = os.path.join(self.path, n)
        for d in self.devs:
            fn = File(path, d, self)
            if d.exists(fn):
                raise ServerError("already exists")
        for d in self.devs:
            fn = File(path, d, self)
            if d.cancreate:
                d.create(fn, perm, mode)
                fn.odev = d
                return fn
        raise ServerError("creation not allowed")

    def clunk(self):
        if self.odev:
            self.odev.clunk(self)
            self.odev = None

    def _readDir(self, off, l):
        if off == 0:
            self.dirlist = []
            for d in self.devs:
                for n in d.list(self):
                    # XXX ignore exceptions in stat?
                    path = os.path.join(self.path, n)
                    fn = File(path, d, self)
                    s = fn._statd(d)
                    self.dirlist.append(s)

        # otherwise assume we continue where we left off
        p9 = Marshal9P()
        p9.setBuf()
        while self.dirlist:
            # Peeking into our abstractions here.  Proceed cautiously.
            xl = len(p9.bytes)
            #print "dirlist: ", self.dirlist[0:1]
            p9._encStat(self.dirlist[0:1], enclen=0)
            if len(p9.bytes) > l:            # backup if necessary
                p9.bytes = p9.bytes[:xl]
                break
            self.dirlist[0:1] = []
        return p9.getBuf()

    def read(self, off, l):
        self._checkOpen(1)
        if self.isdir:
            return self._readDir(off, l)
        else:
            return self.odev.read(self, off, l)

    def write(self, off, buf):
        self._checkOpen(1)
        if self.isdir:
            raise ServerError("can't write to directories")
        return self.odev.write(self, off, buf)


class Server(object):
    """
    A server interface to the protocol.
    Subclass this to provide service
    """
    BUFSZ = 8320
    verbose = 0
    selectpool = []

    def __init__(self, listen, user=None, dom=None, key=None, chatty=0):
        if user == None:
            self.authfs = None
        else:
            self.authfs = AuthFs(user, dom, key)

        self.root = None
        self.sockpool = {}
        self.msg = Marshal9P(chatty)
        self.user = user
        self.dom = dom
        self.host = listen[0]
        self.port = listen[1]
        self.authfs = None
        self.chatty = chatty

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port),)
        self.sock.listen(5)
        self.selectpool.append(self.sock)

    def mount(self, obj):
        """
        Mount obj at path in the tree.  Path should exist and be a directory.
        Only one instance of obj of a given type is allowed since otherwise
        they would compete for the same storage in the File object.
        """
        path = obj.mountpoint
        k = obj.__class__
        if k in klasses:
            raise Error("only one %s allowed" % k)

        path = normpath(path)
        if path not in mountTable:
            mountTable[path] = []

        mountTable[path].append(obj)
        klasses[k] = 1

        if self.root == None:
            self.root = File('/')

    def _err(self, fd, tag, msg):
        print 'Error', msg        # XXX
        if self.verbose:
            print cmdName[Rerror], repr(msg)
        self.msg.send(fd, Rerror, tag, msg)

    def rpc(self, fd):
        """
        Process a single RPC message.
        Return -1 on error.
        """
        type,tag,vals = self.msg.recv(fd)
        if type not in cmdName:
            return self._err(fd, tag, "Invalid message")
        name = "_srv" + cmdName[type]
        if hasattr(self, name):
            func = getattr(self, name)
            try:
                rvals = func(type, tag, vals)
            except ServerError,e:
                self._err(fd, tag, e.args[0])
                return 1                    # nonfatal
            self.msg.send(fd, type + 1, tag, *rvals)
        else:
            return self._err(fd, tag, "Unhandled message: %s" % cmdName[type])
        return 1


    def _getFid(self, fid):
        if fid not in self.activesock.fid:
            raise ServerError("fid %d not in use" % fid)
        obj = self.activesock.fid[fid]
        return obj

    def _setFid(self, fid, obj):
        if fid in self.activesock.fid:
            raise ServerError("fid %d in use" % fid)
        self.activesock.fid[fid] = obj
        return obj

    def _walk(self, obj, path):
        qs = []
        for p in path:
            if p == '/':
                obj = self.root
            elif p == '..':
                obj = obj.parent
            else:
                if p.find('/') >= 0:
                    raise ServerError("illegal character in file")
                obj = obj.walk(p)
            if obj is None:
                break
            qs.append(obj.getQid())
        return qs,obj

    def _srvTversion(self, type, tag, vals):
        bufsz,vers = vals
        if vers != version:
            raise ServerError("unknown version %r" % vers)
        if bufsz > self.BUFSZ:
            bufsz = self.BUFSZ
        return bufsz,vers

    def _srvTauth(self, type, tag, vals):
        fid,uname,aname = vals
        if self.authfs == None:
            if uname == 'none':
                raise ServerError("user 'none' requires no authentication")
            else:
                raise ServerError("no auth info: access allowed to user 'none' only")

        obj = File('#a', self.authfs)
        self._setFid(fid, obj)
        return (obj.getQid(),)

    def _srvTattach(self, type, tag, vals):
        fid,afid,uname,aname = vals

        # permit none to login for anonymous servers
        if uname == 'none':
            if self.authfs != None:
                raise ServerError("user 'none' not permitted to attach")
        else: 
            if self.authfs == None:
                raise ServerError("only user 'none' allowed on non-auth servers")
            try:
                a = self._getFid(afid)
            except ServerError, e:
                raise ServerError("auth fid missing: authentication not complete")
            if a.suid != uname:
                raise ServerError("not authenticated as %r" % uname)
        r = self._setFid(fid, self.root.dup())
        return (r.getQid(),)

    def _srvTflush(self, type, tag, vals):
        return ()

    def _srvTwalk(self, type, tag, vals):
        fid,nfid,names = vals
        obj = self._getFid(fid)
        qs,obj = self._walk(obj, names)
        if len(qs) == len(names):
            self._setFid(nfid, obj)
        return qs,

    def _srvTopen(self, type, tag, vals):
        fid,mode = vals
        obj = self._getFid(fid).dup()
        obj.open(mode)
        self.activesock.fid[fid] = obj
        return obj.getQid(),8192        # XXX

    def _srvTcreate(self, type, tag, vals):
        fid,name,perm,mode = vals
        obj = self._getFid(fid)
        obj = obj.create(name, perm, mode)
        self.activesock.fid[fid] = obj
        return obj.getQid(),8192        # XXX

    def _srvTread(self, type, tag, vals):
        fid,off,count = vals
        return self._getFid(fid).read(off, count),

    def _srvTwrite(self, type, tag, vals):
        fid,off,data = vals
        return self._getFid(fid).write(off, data),

    def _srvTclunk(self, type, tag, vals):
        fid = vals
        self._getFid(fid).clunk()
        del self.activesock.fid[fid]
        return None,

    def _srvTremove(self, type, tag, vals):
        fid = vals
        obj = self._getFid(fid)
        # clunk even if remove fails
        r = self._srvTclunk(type, tag, vals)
        obj.remove()
        return r

    def _srvTstat(self, type, tag, vals):
        # XXX to return multiple stat entries or not?!
        fid = vals
        obj = self._getFid(fid)
        return [obj.stat()],

    def _srvTwstat(self, type, tag, vals):
        fid,stats = vals
        if len(stats) != 1:
            raise ServerError("multiple stats")
        obj = self._getFid(fid)
        obj.wstat(stats[0])
        return None,

    def serve(self):
        while len(self.selectpool) > 0:
            inr, outr, excr = select.select(self.selectpool, [], [])
            for s in inr:
                if s == self.sock:
                    cl, addr = s.accept()
                    self.selectpool.append(cl)
                    self.sockpool[cl] = Sock(cl)
                    if self.chatty:
                        print >>sys.stderr, "accepted connection from: %s" % str(addr)
                else:
                    try:
                        self.activesock = self.sockpool[s]
                        self.rpc(self.sockpool[s])
                    except:
                        if self.chatty:
                            print >>sys.stderr, "socket closed..."
                        self.selectpool.remove(s)
                        del self.sockpool[s]

        if self.chatty:
            print >>sys.stderr, "no more clients left; main socket closed"
        return


class Client(object):
    """
    A client interface to the protocol.
    """
    AFID = 10
    ROOT = 11
    CWD = 12
    F = 13

    verbose = 0
    msg = None

    def __init__(self, fd, user, passwd, authsrv, chatty=0):
        self.msg = Marshal9P(chatty)
        self.fd = fd
        self.verbose = chatty
        self.login(user, passwd, authsrv)

    def _rpc(self, type, *args):
        tag = 1
        if type == Tversion:
            tag = notag
        self.msg.send(self.fd, type, tag, *args)
        rtype,rtag,vals = self.msg.recv(self.fd)
        if rtag != tag:
            raise RpcError("invalid tag received")
        if rtype == Rerror:
            raise RpcError(vals)
        if rtype != type + 1:
            raise ClientError("incorrect reply from server: %r" % [rtype,rtag,vals])
        return vals

    def version(self, msize, version):
        return self._rpc(Tversion, msize, version)
    def auth(self, fid, uname, aname):
        return self._rpc(Tauth, fid, uname, aname)
    def attach(self, fid, afid, uname, aname):
        return self._rpc(Tattach, fid, afid, uname, aname)
    def walk(self, fid, newfid, wnames):
        return self._rpc(Twalk, (fid, newfid, wnames))
    def open(self, fid, mode):
        return self._rpc(Topen, fid, mode)
    def create(self, fid, name, perm, mode):
        return self._rpc(Tcreate, fid, name, perm, mode)
    def read(self, fid, off, count):
        return self._rpc(Tread, fid, off, count)
    def write(self, fid, off, data):
        return self._rpc(Twrite, fid, off, data)
    def clunk(self, fid):
        return self._rpc(Tclunk, fid)
    def remove(self, fid):
        return self._rpc(Tremove, fid)
    def stat(self, fid):
        return self._rpc(Tstat, fid)
    def wstat(self, fid, stats):
        return self._rpc(Twstat, fid, stats)

    def close(self):
        self.clunk(self.ROOT)
        self.clunk(self.CWD)
        self.fd.close()


    def login(self, user, passwd, authsrv):
        maxbuf,vers = self.version(16 * 1024, version)
        if vers != version:
            raise ClientError("version mismatch: %r" % vers)

        afid = self.AFID
        try:
            self.auth(afid, user, '')
            needauth = 1
        except RpcError,e:
            afid = nofid

        if afid != nofid:
            if passwd is None:
                raise ClientError("Password required")

            import py9psk1, socket
            try:
                py9psk1.clientAuth(self, afid, user, py9psk1.makeKey(passwd), authsrv, py9psk1.AUTHPORT)
            except socket.error,e:
                raise ClientError("%s: %s" % (authsrv, e.args[1]))
        self.attach(self.ROOT, afid, user, "")
        if afid != nofid:
            self.clunk(afid)
        self.walk(self.ROOT, self.CWD, [])


