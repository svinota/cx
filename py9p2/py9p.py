#!/usr/bin/python
"""
9P protocol implementation as documented in plan9 intro(5) and <fcall.h>.
"""

import os.path 
import sys
import socket
import select
import copy
import traceback

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

version = '9P2000'
versionu = '9P2000.u'

Ebadoffset = "bad offset"
Ebotch = "9P protocol botch"
Ecreatenondir = "create in non-directory"
Edupfid = "duplicate fid"
Eduptag = "duplicate tag"
Eisdir = "is a directory"
Enocreate = "create prohibited"
Enoremove = "remove prohibited"
Enostat = "stat prohibited"
Enotfound = "file not found"
Enowstat = "wstat prohibited"
Eperm = "permission denied"
Eunknownfid = "unknown fid"
Ebaddir = "bad directory in wstat"
Ewalknotdir = "walk in non-directory"

NOTAG = 0xffff
NOFID = 0xffffffffL

# Qid.type
QTDIR       =0x80        # type bit for directories 
QTAPPEND    =0x40        # type bit for append only files 
QTEXCL      =0x20        # type bit for exclusive use files 
QTMOUNT     =0x10        # type bit for mounted channel 
QTAUTH      =0x08        # type bit for authentication file 
QTTMP       =0x04        # type bit for non-backed-up file 
QTSYMLINK   =0x02        # type bit for symbolic link 
QTFILE      =0x00        # type bits for plain file 

# Dir.mode
DMDIR       =0x80000000  # mode bit for directories 
DMAPPEND    =0x40000000  # mode bit for append only files 
DMEXCL      =0x20000000  # mode bit for exclusive use files 
DMMOUNT     =0x10000000  # mode bit for mounted channel 
DMAUTH      =0x08000000  # mode bit for authentication file 
DMTMP       =0x04000000  # mode bit for non-backed-up file 
DMSYMLINK   =0x02000000  # mode bit for symbolic link (Unix, 9P2000.u) 
DMDEVICE    =0x00800000  # mode bit for device file (Unix, 9P2000.u) 
DMNAMEDPIPE =0x00200000  # mode bit for named pipe (Unix, 9P2000.u) 
DMSOCKET    =0x00100000  # mode bit for socket (Unix, 9P2000.u) 
DMSETUID    =0x00080000  # mode bit for setuid (Unix, 9P2000.u) 
DMSETGID    =0x00040000  # mode bit for setgid (Unix, 9P2000.u) 

DMREAD      =0x4     # mode bit for read permission 
DMWRITE     =0x2     # mode bit for write permission 
DMEXEC      =0x1     # mode bit for execute permission 

OREAD,OWRITE,ORDWR,OEXEC = range(4)
AEXIST,AEXEC,AWRITE,AREAD = range(4)
OTRUNC,ORCLOSE = 0x10,0x40

IOHDRSZ = 24
PORT = 564

class Error(Exception): pass
class RpcError(Error): pass
class ServerError(Error): pass
class ClientError(Error): pass

def modetostr(mode):
    bits = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
    def b(s):
        return bits[(mode>>s) & 7]
    d = "-"
    if mode & DMDIR:
        d = "d"
    return "%s%s%s%s" % (d, b(6), b(3), b(0))

def hash8(obj):
    return int(abs(hash(obj)))

def hasperm(f, uid, p):
    m = f.dir.mode & 7  # other
    if (p & m) == p:
        return 1

    if f.dir.uid == uid:
        m |= (f.dir.mode>>6) & 7
        if (p & m) == p:
            return 1
    if f.dir.gid == uid:
        m |= (f.dir.mode>>3) & 7
        if (p & m) == p:
            return 1
    return 0

class Sock:
    """Provide appropriate read and write methods for the Marshaller"""
    def __init__(self, sock):
        self.sock = sock
        self.fids = {}  # fids are per client
        self.reqs = {}  # reqs are per client
        self.uname = None
    def read(self, l):
        x = self.sock.recv(l)
        while len(x) < l:
            b = self.sock.recv(l - len(x))
            if not b:
                raise Error("client eof")
            x += b
        return x
    def write(self, buf):
        if self.sock.send(buf) != len(buf):
            raise Error("short write")
    def fileno(self):
        return self.sock.fileno()
    def delfid(self, fid):
        if fid in self.fids:
            self.fids[fid].ref = self.fids[fid].ref - 1
            if self.fids[fid].ref == 0:
                del self.fids[fid]
    def getfid(self, fid):
        if fid in self.fids:
            return self.fids[fid]
        return None

class Fcall:
    '''# possible values, from p9p's fcall.h
    msize       # Tversion, Rversion
    version     # Tversion, Rversion
    oldtag      # Tflush
    ename       # Rerror
    qid         # Rattach, Ropen, Rcreate
    iounit      # Ropen, Rcreate
    aqid        # Rauth
    afid        # Tauth, Tattach
    uname       # Tauth, Tattach
    aname       # Tauth, Tattach
    perm        # Tcreate
    name        # Tcreate
    mode        # Tcreate, Topen
    newfid      # Twalk
    nwname      # Twalk
    wname       # Twalk, array
    nwqid       # Rwalk
    wqid        # Rwalk, array
    offset      # Tread, Twrite
    count       # Tread, Twrite, Rread
    data        # Twrite, Rread
    nstat       # Twstat, Rstat
    stat        # Twstat, Rstat

    # dotu extensions:
    errornum    # Rerror
    extension   # Tcreate
    '''    
    def __init__(self, type, tag=1, fid=None):
        self.type = type
        self.fid = fid
        self.tag = tag
    def tostr(self):
        attr = filter(lambda x: not x.startswith('_') and not x.startswith('tostr'), dir(self))

        ret = ' '.join(map(lambda x: "%s=%s" % (x, getattr(self, x)), attr))
        ret = cmdName[self.type] + " " + ret
        return repr(ret)


class Qid:
    def __init__(self, type=None, vers=None, path=None):
        self.type = type
        self.vers = vers
        self.path = path

class Fid:
    def __init__(self, pool, fid, path='', auth=0):
        if pool.has_key(fid):
            return None
        self.fid = fid
        self.ref = 1
        self.omode=-1
        self.auth = auth
        self.uid = None
        self.qid = None
        self.path = path

        pool[fid] = self

class Dir:
    # type:         server type
    # dev           server subtype
    #
    # file data:
    # qid           unique id from server 
    # mode          permissions 
    # atime         last read time 
    # mtime         last write time 
    # length        file length 
    # name          last element of path 
    # uid           owner name 
    # gid           group name 
    # muid          last modifier name 
    #
    # 9P2000.u extensions:
    # uidnum        numeric uid
    # gidnum        numeric gid
    # muidnum       numeric muid
    # *ext          extended info

    def __init__(self, dotu=0, *args):
        self.dotu = dotu
        self.children = {}
        self.parent = {}
        # the dotu arguments will be added separately. this is not
        # straightforward but is cleaner.
        if len(args):
            (self.type,
                self.dev,
                self.qid,
                self.mode,
                self.atime,
                self.mtime,
                self.length,
                self.name,
                self.uid,
                self.gid,
                self.muid) = args
                
            if dotu:
                (self.uidnum,
                    self.gidnum,
                    self.muidnum,
                    self.extension) = args[-4:]

    def tolstr(self):
        if self.dotu:
            return "%s %d %d %-8d\t\t%s" % (modetostr(self.mode), self.uidnum, self.gidnum, self.length, self.name)
        else:
            return "%s %s %s %-8d\t\t%s" % (modetostr(self.mode), self.uid, self.gid, self.length, self.name)

    def todata(self):
        '''This circumvents a leftower from the original 9P python implementation.
        Why do enc functions have to hide data in "bytes"? I don't know'''

        n = Marshal9P()
        n.setBuf()
        if self.dotu:
            size = 2+4+13+4+4+4+8+len(self.name)+len(self.uid)+len(self.gid)+len(self.muid)+2+2+2+2+4+4+4
        else:
            size = 2+4+13+4+4+4+8+len(self.name)+len(self.uid)+len(self.gid)+len(self.muid)+2+2+2+2
        n.enc2(size)
        n.enc2(self.type)
        n.enc4(self.dev)
        n.encQ(self.qid)
        n.enc4(self.mode)
        n.enc4(self.atime)
        n.enc4(self.mtime)
        n.enc8(self.length)
        n.encS(self.name)
        n.encS(self.uid)
        n.encS(self.gid)
        n.encS(self.muid)
        if self.dotu:
            n.encS(self.uidnum)
            n.encS(self.gidnum)
            n.encS(self.muidnum)
        return n.bytes

class Req:
    def __init__(self, tag, fd = None, ifcall=None, ofcall=None, dir=None, oldreq=None,
    fid=None, afid=None, newfid=None):
        self.tag = tag
        self.fd = fd
        self.ifcall = ifcall
        self.ofcall = ofcall
        self.dir = dir
        self.oldreq = oldreq
        self.fid = fid
        self.afid = afid
        self.newfid = newfid

class Marshal(object):
    chatty = 0

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
            if n[:4] == "enc":
                encFunc[n[4:]] = self.__getattribute__(n)
            if n[:4] == "dec":
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

    def encX(self, x):
        "Encode opaque data"
        self.bytes += list(x)
    def decX(self, l):
        x = "".join(self.bytes[:l])
        #del self.bytes[:l]
        self.bytes[:l] = [] # significant speedup
        return x

    def encC(self, x):
        "Encode a 1-byte character"
        return self.encX(x)
    def decC(self):
        return self.decX(1)

    def enc1(self, x):
        "Encode a 1-byte integer"
        self._checkSize(x, 0xff)
        self.encC(chr(x))
    def dec1(self):
        return long(ord(self.decC()))

    def enc2(self, x):
        "Encode a 2-byte integer"
        self._checkSize(x, 0xffff)
        self.enc1(x & 0xff)
        self.enc1(x >> 8)
    def dec2(self):
        return self.dec1() | (self.dec1() << 8)

    def enc4(self, x):
        "Encode a 4-byte integer"
        self._checkSize(x, 0xffffffffL)
        self.enc2(x & 0xffff)
        self.enc2(x >> 16)
    def dec4(self):
        return self.dec2() | (self.dec2() << 16) 

    def enc8(self, x):
        "Encode a 4-byte integer"
        self._checkSize(x, 0xffffffffffffffffL)
        self.enc4(x & 0xffffffffL)
        self.enc4(x >> 32)
    def dec8(self):
        return self.dec4() | (self.dec4() << 32)

    def encS(self, x):
        "Encode length/data strings with 2-byte length"
        self.enc2(len(x))
        self.encX(x)
    def decS(self):
        return self.decX(self.dec2())

    def encD(self, d):
        "Encode length/data arrays with 4-byte length"
        self.enc4(len(d))
        self.encX(d)
    def decD(self):
        return self.decX(self.dec4())


class Marshal9P(Marshal):
    MAXSIZE = 1024 * 1024            # XXX
    chatty = False

    def __init__(self, dotu=0, chatty=False):
        self.chatty = chatty
        self.dotu = dotu

    def encQ(self, q):
        self.enc1(q.type)
        self.enc4(q.vers)
        self.enc8(q.path)
    def decQ(self):
        return Qid(self.dec1(), self.dec4(), self.dec8())

    def _checkType(self, t):
        if not cmdName.has_key(t):
            raise Error("Invalid message type %d" % t)
    def _checkResid(self):
        if len(self.bytes):
            raise Error("Extra information in message: %r" % self.bytes)

    def send(self, fd, fcall):
        "Format and send a message"
        self.setBuf()
        self._checkType(fcall.type)
        if self.chatty:
            print "-%d->" % fd.fileno(), cmdName[fcall.type], fcall.tag, fcall.tostr()
        self.enc1(fcall.type)
        self.enc2(fcall.tag)
        self.enc(fcall)
        self.enc4(len(self.bytes) + 4)
        self.bytes = self.bytes[-4:] + self.bytes[:-4]
        fd.write(self.getBuf())

    def recv(self, fd):
        "Read and decode a message"
        self.setBuf(fd.read(4))
        size = self.dec4()
        if size > self.MAXSIZE or size < 4:
            raise Error("Bad message size: %d" % size)
        self.setBuf(fd.read(size - 4))
        type,tag = self.dec1(),self.dec2()
        self._checkType(type)
        fcall = Fcall(type, tag)
        self.dec(fcall)
        self._checkResid()
        if self.chatty:
            print "<-%d-" % fd.fileno(), cmdName[type], tag, fcall.tostr()
        return fcall

    def encstat(self, fcall):
        totsz = 0
        for x in fcall.stat:
            if self.dotu:
                totsz = 2+4+13+4+4+4+8+len(x.name)+len(x.uid)+len(x.gid)+len(x.muid)+2+2+2+2+4+4+4
            else:
                totsz = 2+4+13+4+4+4+8+len(x.name)+len(x.uid)+len(x.gid)+len(x.muid)+2+2+2+2
        self.enc2(totsz+2)

        for x in fcall.stat:
            if self.dotu:
                size = 2+4+13+4+4+4+8+len(x.name)+len(x.uid)+len(x.gid)+len(x.muid)+2+2+2+2+4+4+4
            else:
                size = 2+4+13+4+4+4+8+len(x.name)+len(x.uid)+len(x.gid)+len(x.muid)+2+2+2+2
            self.enc2(size)
            self.enc2(x.type)
            self.enc4(x.dev)
            self.encQ(x.qid)
            self.enc4(x.mode)
            self.enc4(x.atime)
            self.enc4(x.mtime)
            self.enc8(x.length)
            self.encS(x.name)
            self.encS(x.uid)
            self.encS(x.gid)
            self.encS(x.muid)
            if self.dotu:
                self.encS(x.uidnum)
                self.encS(x.gidnum)
                self.encS(x.muidnum)

    def enc(self, fcall):
        if fcall.type in (Tversion, Rversion):
            self.enc4(fcall.msize)
            self.encS(fcall.version)
        elif fcall.type == Tauth:
            self.enc4(fcall.afid)
            self.encS(fcall.uname)
            self.encS(fcall.aname)
        elif fcall.type == Rauth:
            self.encQ(fcall.aqid)
        elif fcall.type == Rerror:
            self.encS(fcall.ename)
        elif fcall.type == Tflush:
            self.enc2(fcall.oldtag)
        elif fcall.type == Tattach:
            self.enc4(fcall.fid)
            self.enc4(fcall.afid)
            self.encS(fcall.uname)
            self.encS(fcall.aname)
        elif fcall.type == Rattach:
            self.encQ(fcall.afid)
        elif fcall.type == Twalk:
            self.enc4(fcall.fid)
            self.enc4(fcall.newfid)
            self.enc2(len(fcall.wname))
            for x in fcall.wname:
                self.encS(x)
        elif fcall.type == Rwalk:
            self.enc2(len(fcall.wqid))
            for x in fcall.wqid:
                self.encQ(x)
        elif fcall.type == Topen:
            self.enc4(fcall.fid)
            self.enc1(fcall.mode)
        elif fcall.type in (Ropen, Rcreate):
            self.encQ(fcall.qid)
            self.enc4(fcall.iounit)
        elif fcall.type == Tcreate:
            self.enc4(fcall.fid)
            self.encS(fcall.name)
            self.enc4(fcall.perm)
            self.enc1(fcall.mode)
            if self.dotu:
                self.encS(fcall.extension)
        elif fcall.type == Tread:
            self.enc4(fcall.fid)
            self.enc8(fcall.offset)
            self.enc4(fcall.count)
        elif fcall.type == Rread:
            self.encD(fcall.data)
        elif fcall.type == Twrite:
            self.enc4(fcall.fid)
            self.enc8(fcall.offset)
            self.enc4(len(fcall.data))
            self.encX(fcall.data)
        elif fcall.type == Rwrite:
            self.enc4(fcall.count)
        elif fcall.type in (Tclunk,  Tremove, Tstat):
            self.enc4(fcall.fid)
        elif fcall.type in (Rstat, Twstat):
            if fcall.type == Twstat:
                self.dec4(fcall.fid)
            self.encstat(fcall)


    def decstat(self, fcall, enclen=1):
        fcall.stat = []
        if enclen:
            totsz = self.dec2()
        while len(self.bytes):
            size = self.dec2()
            b = self.bytes
            self.bytes = b[0:size]

            stat = Dir(self.dotu)
            stat.type = self.dec2()     # type
            stat.dev = self.dec4()      # dev
            stat.qid = self.decQ()      # qid
            stat.mode = self.dec4()     # mode
            stat.atime = self.dec4()    # atime
            stat.mtime = self.dec4()    # mtime
            stat.length = self.dec8()   # length
            stat.name = self.decS()     # name  
            stat.uid = self.decS()      # uid
            stat.gid = self.decS()      # gid
            stat.muid = self.decS()     # muid
            if self.dotu:
                stat.uidnum = self.dec4()
                stat.gidnum = self.dec4()
                stat.muidnum = self.dec4()
            fcall.stat.append(stat)
            self.bytes = b
            self.bytes[0:size] = []


    def dec(self, fcall):
        if fcall.type in (Tversion, Rversion):
            fcall.msize = self.dec4()
            fcall.version = self.decS()
        elif fcall.type == Tauth:
            fcall.afid = self.dec4()
            fcall.uname = self.decS()
            fcall.aname = self.decS()
        elif fcall.type == Rauth:
            fcall.aqid = self.decQ()
        elif fcall.type == Rerror:
            fcall.ename = self.decS()
        elif fcall.type == Tflush:
            fcall.oldtag = self.dec2()
        elif fcall.type == Tattach:
            fcall.fid = self.dec4()
            fcall.afid = self.dec4()
            fcall.uname = self.decS()
            fcall.aname = self.decS()
        elif fcall.type == Rattach:
            fcall.afid = self.decQ()
        elif fcall.type == Twalk:
            fcall.fid = self.dec4()
            fcall.newfid = self.dec4()
            l = self.dec2()
            fcall.wname = [self.decS() for n in xrange(l)]
        elif fcall.type == Rwalk:
            l = self.dec2()
            fcall.wqid = [self.decQ() for n in xrange(l)]
        elif fcall.type == Topen:
            fcall.fid = self.dec4()
            fcall.mode = self.dec1()
        elif fcall.type in (Ropen, Rcreate):
            fcall.qid = self.decQ()
            fcall.iounit = self.dec4()
        elif fcall.type == Tcreate:
            fcall.fid = self.dec4()
            fcall.name = self.decS()
            fcall.perm = self.dec4()
            fcall.mode = self.dec1()
            if self.dotu:
                fcall.extension = self.decS()
        elif fcall.type == Tread:
            fcall.fid = self.dec4()
            fcall.offset = self.dec8()
            fcall.count = self.dec4()
        elif fcall.type == Rread:
            fcall.data = self.decD()
        elif fcall.type == Twrite:
            fcall.fid = self.dec4()
            fcall.offset = self.dec8()
            fcall.count = self.dec4()
            fcall.data = self.decX(fcall.count)
        elif fcall.type == Rwrite:
            fcall.count = self.dec4()
        elif fcall.type in (Tclunk, Tremove, Tstat):
            fcall.fid = self.dec4()
        elif fcall.type in (Rstat, Twstat):
            if fcall.type == Twstat:
                fcall.fid = self.dec4()
            self.decstat(fcall)

        return fcall
    
class Server(object):
    """
    A server interface to the protocol.
    Subclass this to provide service
    """
    msize = 8192 + IOHDRSZ
    chatty = False
    readpool = []
    writepool = []
    activesocks = {}

    def __init__(self, listen, fs=None, user=None, dom=None, key=None, chatty=False, dotu=False):
        if user == None:
            self.authfs = None
        else:
            import py9psk1
            self.authfs = py9psk1.AuthFs(user, dom, key)

        self.fs = fs
        self.dotu = dotu

        self.readpool = []
        self.writepool = []
        self.marshal = Marshal9P(dotu=self.dotu, chatty=chatty)
        self.user = user
        self.dom = dom
        self.host = listen[0]
        self.port = listen[1]
        self.chatty = chatty

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port),)
        self.sock.listen(5)
        self.readpool.append(self.sock)
        if self.chatty:
            print >>sys.stderr, "listening to %s:%d"%(self.host, self.port)
    def mount(self, fs):
        # XXX: for now only allow one mount
        # in the future accept fs/root and
        # handle different filesystems at walk time
        self.fs = fs

    def serve(self):
        while len(self.readpool) > 0 or len(self.writepool) > 0:
            inr, outr, excr = select.select(self.readpool, self.writepool, [])
            for s in inr:
                if s == self.sock:
                    cl, addr = s.accept()
                    self.readpool.append(cl)
                    self.activesocks[cl] = Sock(cl)
                    if self.chatty:
                        print >>sys.stderr, "accepted connection from: %s" % str(addr)
                else:
                    if hasattr(s, 'req'):
                        # this is a fs-delayed req that's just become ready, 
                        # assume client has a corresponding function call
                        # since that's the only way they can call
                        # regreadfd() to register here
                        name = cmdName[s.req.ifcall.type][1:]
                        try:
                            func = getattr(self.fs, name)
                            s.req.fromselect = 1
                            func(srv, req)
                        except:
                            print >>sys.stderr, "error in delayed respond: ", traceback.print_exc()
                            self.respond(req, "error in delayed response")
                            # what a mess! should we be doing this at all?
                            # how do we tell the fileserver that one of its
                            # fds has disappeared?
                            self.readpool.remove(s)
                            del s
                        continue
                    try:
                        self.fromnet(self.activesocks[s])
                    except socket.error, e:
                        if self.chatty:
                            print >>sys.stderr, "socket error: " + e.args[1]
                        self.readpool.remove(s)
                        del self.activesocks[s]
                    except Exception, e:
                        if e.args[0] == 'client eof':
                            if self.chatty:
                                print >>sys.stderr, "socket closed: " + e.args[0]
                            self.readpool.remove(s)
                            s.close()
                            del self.activesocks[s]
                            del s
                        else:
                            raise
        if self.chatty:
            print >>sys.stderr, "main socket closed"

        return

    def respond(self, req, error=None):
        name = 'r' + cmdName[req.ifcall.type][1:]
        if hasattr(self, name):
            func = getattr(self, name)
            try:
                func(req, error)
            except Exception, e:
                print >>sys.stderr, "error in respond: ", traceback.print_exc()
                return -1
        else:
            raise ServerError("can not handle message type " + cmdName[req.ifcall.type])

        req.ofcall.tag = req.ifcall.tag
        if error:
            req.ofcall.type = Rerror
            req.ofcall.ename = error
        try:
            self.marshal.send(req.sock, req.ofcall)
        except socket.error, e:
            if self.chatty:
                print >>sys.stderr, "socket error: " + e.args[1]
            self.readpool.remove(s)
        except Exception, e:
            if e.args[0] == 'client eof':
                if self.chatty:
                    print >>sys.stderr, "socket closed: " + e.args[0]
                self.readpool.remove(s)
            else:
                raise

        # XXX: unsure whether we need proper flushing semantics from rsc's p9p
        # thing is, we're not threaded.
        


    def fromnet(self, fd):
        fcall = self.marshal.recv(fd)
        req = Req(fcall.tag)
        req.ifcall = fcall
        req.ofcall = Fcall(fcall.type+1, fcall.tag)
        req.fd = fd.fileno()
        req.sock = fd

        if req.ifcall.type not in cmdName:
            self.respond(req, "invalid message")

        name = "t" + cmdName[req.ifcall.type][1:]
        if hasattr(self, name):
            func = getattr(self, name)
            try:
                func(req)
            except (ServerError, Error) ,e:
                print >>sys.stderr, "error processing request: ", traceback.print_exc()
                self.respond(req, str(e.args[0]))
                return -1
            except Exception, e:
                print >>sys.stderr, "unhandled exception: ", traceback.print_exc()
                self.respond(req, 'unhandled internal exception: ' + e.args[0])
                return -1
        else:
            self.respond(req, "unhandled message: %s" % (cmdName[req.ifcall.type]))
            return -1
        return 0

    def regreadfd(self, fd, req):
        '''Register a file descriptor in the read pool. When a fileserver
        wants to delay responding to a message they can register an fd and
        have it polled for reading. When it's ready, the corresponding 'req'
        will be called'''
        fd.req = req
        self.readpool.append(fd)

    def delreadfd(self, fd):
        '''Delete a fd registered with regreadfd() from the read pool'''
        self.readpool.remove(fd)

    def tversion(self, req):
        if req.ifcall.version[0:2] != '9P': 
            req.ofcall.version = "unknown";
            self.respond(r, None);
            return

        if req.ifcall.version == '9P2000.u':
            req.ofcall.version = '9P2000.u'
            self.dotu = True

        if req.ifcall.version == '9P2000':
            req.ofcall.version = '9P2000'
            self.dotu = False
        req.ofcall.msize = req.ifcall.msize
        self.respond(req, None)

    def rversion(self, req, error):
        self.msize = req.ofcall.msize

    def tauth(self, req):
        if self.authfs == None:
            self.respond(req, "%s: authentication not required"%(sys.argv[0]))
            return

        req.afid = Fid(req.sock.fids, req.ifcall.afid, auth=1)
        if not req.afid:
            self.respond(req, Edupfid)
        self.authfs.estab(req.afid)
        req.afid.qid = Qid(QTAUTH, 0, hash8('#a'))
        req.ofcall.aqid = req.afid.qid
        self.respond(req, None)

    def rauth(self, req, error):
        if error and req.afid:
            req.sock.delfid(req.afid.fid)

    def tattach(self, req):
        req.fid = Fid(req.sock.fids, req.ifcall.fid)
        if not req.fid:
            self.respond(req, Edupfid)
            return

        req.afid = None
        if req.ifcall.afid != NOFID:
            req.afid = req.sock.fids[req.ifcall.afid]
            if not req.afid:
                self.respond(req, Eunknownfid)
                return
            if req.afid.suid != req.ifcall.uname:
                self.respond(req, "not authenticated as %r"%req.ifcall.uname)
                return
            elif self.chatty:
                print >>sys.stderr, "authenticated as %r"%req.ifcall.uname

        req.fid.uid = req.ifcall.uname
        req.sock.uname = req.ifcall.uname # now we know who we are
        if hasattr(self.fs, 'attach'):
            self.fs.attach()
        else:
            req.ofcall.afid = self.fs.root.qid
            req.fid.qid = self.fs.root.qid
            self.respond(req, None)
        return

    def rattach(self, req, error):
        if error and req.fid:
            req.sock.delfid(req.fid.fid)

    def tflush(self, req):
        if hasattr(self.fs, 'flush'):
            self.fs.flush(srv, req)
        else:
            req.sock.reqs = []
            self.respond(req, None)
        

    def rflush(self, req, error):
        if req.oldreq:
            if req.oldreq.responded == 0:
                req.oldreq.nflush = req.oldreq.nflush+1
                if not hasattr(req.oldreq, 'flush'):
                    req.oldreq.nflush = 0
                    req.oldreq.flush = []
                req.oldreq.nflush = req.oldreq.nflush+1
                req.oldreq.flush.append(req)
        req.oldreq = None
        return 0

    def twalk(self, req):
        req.ofcall.wqid = []

        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if req.fid.omode != -1:
            self.respond(req, "cannot clone open fid")
            return
        if len(req.ifcall.wname) and not (req.fid.qid.type & QTDIR):
            self.respond(req, Ewalknotdir)
            return
        if req.ifcall.fid != req.ifcall.newfid:
            req.newfid = Fid(req.sock.fids, req.ifcall.newfid)
            if not req.newfid:
                self.respond(req, Edupfid)
                return
            req.newfid.uid = req.fid.uid
        else:
            req.fid.ref = req.fid.ref+1
            req.newfid = req.fid

#        if len(req.ifcall.wname) == 0 and self.fs.root:
#            req.ofcall.wqid.append(self.fs.root.qid)
#            req.newfid.qid = self.fs.root.qid
#            self.respond(req, None)
        if len(req.ifcall.wname) == 0:
            req.ofcall.wqid.append(req.fid.qid)
            self.respond(req, None)
        elif hasattr(self.fs, 'walk'):
            self.fs.walk(self, req)
        else:
            self.respond(req, "no walk function")

    def rwalk(self, req, error):
        if error or (len(req.ofcall.wqid) < len(req.ifcall.wname) and len(req.ifcall.wname) > 0):
            if req.ifcall.fid != req.ifcall.newfid and req.newfid:
                req.sock.delfid(req.ifcall.newfid)
            if len(req.ofcall.wqid) == 0:
                if not error and len(req.ifcall.wname) != 0:
                    req.error = Enotfound
            else:
                req.error = None
        else:
            if len(req.ofcall.wqid) == 0:
                req.newfid.qid = req.fid.qid
            else:
                req.newfid.qid = req.ofcall.wqid[-1]
                
    def topen(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if req.fid.omode != -1:
            self.respond(req, Ebotch)
            return
        if (req.fid.qid.type & QTDIR) and ((req.ifcall.mode & (~ORCLOSE)) != OREAD):
            self.respond(req, Eisdir)
            return
        req.ofcall.qid = req.fid.qid
        req.ofcall.iounit = self.msize - IOHDRSZ
        mode = req.ifcall.mode&3
        if mode == OREAD:
            p = AREAD
        elif mode == OWRITE:
            p = AWRITE
        elif mode == ORDWR:
            p = AREAD|AWRITE
        elif mode == OEXEC:
            p = AEXEC
        else:
            self.respond(req, "unknown open mode: %d" % mode)
            return

        if req.ifcall.mode & OTRUNC:
            p = p | AWRITE

        if (req.fid.qid.type & QTDIR) and (p != AREAD):
            self.respond(req, Eperm)
        if hasattr(self.fs, 'open'):
            self.fs.open(self, req)
        else:
            self.respond(req, None)

    def ropen(self, req, error):
        if error:
            return
        req.fid.omode = req.ifcall.mode
        req.fid.qid = req.ofcall.qid
        if req.ofcall.qid.type & QTDIR:
            req.fid.diroffset = 0

    def tcreate(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
        elif req.fid.omode != -1:
            self.respond(req, Ebotch)
        elif not (req.fid.qid.type & QTDIR):
            self.respond(req, Ecreatenondir)
        elif hasattr(self.fs, 'create'):
            self.fs.create(self, req)
        else:
            respond(req, Enocreate)

    def rcreate(self, req, error):
        if error:
            return
        req.fid.omode = req.ifcall.mode
        req.fid.qid = req.ofcall.qid
        req.ofcall.iounit = self.msize - IOHDRSZ

    def tread(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if req.ifcall.count < 0:
            self.respond(req, Ebotch)
            return
        if req.ifcall.offset < 0 or ((req.fid.qid.type & QTDIR) and (req.ifcall.offset != 0) and (req.ifcall.offset != req.fid.diroffset)):
            self.respond(req, Ebadoffset)
            return

        if req.fid.qid.type & QTAUTH and self.authfs:
            self.authfs.read(self, req)
            return

        if req.ifcall.count > self.msize - IOHDRSZ:
            req.ifcall.count = self.msize - IOHDRSZ
        o = req.fid.omode & 3
        if o != OREAD and o != ORDWR and o != OEXEC:
            self.respond(req, Ebotch)
            return
        if hasattr(self.fs, 'read'):
            self.fs.read(self, req)
        else:
            self.respond(req, 'no server read function')

    def rread(self, req, error):
        if error:
            return

        if req.fid.qid.type & QTDIR:
            data = []
            for x in req.ofcall.stat:
                data = data + x.todata()
            if req.ifcall.offset > len(data):
                data = []
            else:
                req.ofcall.data = data[req.ifcall.offset:req.ifcall.offset + req.ifcall.count]
            req.fid.diroffset = req.ifcall.offset + len(req.ofcall.data)

    def twrite(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if req.ifcall.count < 0:
            self.respond(req, Ebotch)
            return
        if req.ifcall.offset < 0:
            self.respond(req, Ebotch)
            return

        if req.fid.qid.type & QTAUTH and self.authfs:
            self.authfs.write(self, req)
            return

        if req.ifcall.count > self.msize - IOHDRSZ:
            req.ifcall.count = self.msize - IOHDRSZ
        o = req.fid.omode & 3
        if o != OWRITE and o != ORDWR:
            self.respond(req, "write on fid with open mode 0x%ux" % req.fid.omode)
            return
        if hasattr(self.fs, 'write'):
            self.fs.write(self, req)
        else:
            self.respond(req, 'no server write function')

    def rwrite(self, req, error):
        return

    def tclunk(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
        else:
            req.sock.delfid(req.ifcall.fid)
            self.respond(req, None)

    def rclunk(self, req, error):
        return

    def tremove(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if hasattr(self.fs, 'remove'):
            self.fs.remove(self, req)
        else:
            self.respond(req, Enoremove)

    def rremove(self, req, error):
        return

    def tstat(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if hasattr(self.fs, 'stat'):
            self.fs.stat(req)
        else:
            self.respond(req, Enostat)

    def rstat(self, req, error):
        if error:
            return
        # XXX

    def twstat(self, req):
        req.fid = req.sock.getfid(req.ifcall.fid)
        if not req.fid:
            self.respond(req, Eunknownfid)
            return
        if not hasattr(self.fs, 'wstat'):
            self.respond(req, Enowstat)
            return
        # XXX
    def rwstat(self, req, error):
        return

class Client(object):
    """
    A client interface to the protocol.
    """
    AFID = 10
    ROOT = 11
    CWD = 12
    F = 13

    path = '' # for 'getwd' equivalent
    chatty = 0
    msg = None
    msize = 8192 + IOHDRSZ

    def __init__(self, fd, user, passwd, authsrv, chatty=0):
        self.msg = Marshal9P(dotu=0, chatty=chatty)
        self.fd = fd
        self.chatty = chatty
        self.login(user, passwd, authsrv)

    def _rpc(self, fcall):
        if fcall.type == Tversion:
            fcall.tag = NOTAG
        self.msg.send(self.fd, fcall)
        ifcall = self.msg.recv(self.fd)
        if ifcall.tag != fcall.tag:
            raise RpcError("invalid tag received")
        if ifcall.type == Rerror:
            raise RpcError(ifcall.ename)
        if ifcall.type != fcall.type + 1:
            raise ClientError("incorrect reply from server: %r" % [fcall.type,fcall.tag])
        return ifcall

    # protocol calls; part of 9p
    # should be private functions, really
    def _version(self, msize, version):
        fcall = Fcall(Tversion)
        self.msize = msize
        fcall.msize = msize
        fcall.version = version
        return self._rpc(fcall)
    def _auth(self, afid, uname, aname):
        fcall = Fcall(Tauth)
        fcall.afid = afid
        fcall.uname = uname
        fcall.aname = aname
        return self._rpc(fcall)
    def _attach(self, fid, afid, uname, aname):
        fcall = Fcall(Tattach)
        fcall.fid = fid
        fcall.afid = afid
        fcall.uname = uname
        fcall.aname = aname
        return self._rpc(fcall)
    def _walk(self, fid, newfid, wnames):
        fcall = Fcall(Twalk)
        fcall.fid = fid
        fcall.newfid = newfid
        fcall.wname = wnames
        return self._rpc(fcall)
    def _open(self, fid, mode):
        fcall = Fcall(Topen)
        fcall.fid = fid
        fcall.mode = mode
        return self._rpc(fcall)
    def _create(self, fid, name, perm, mode):
        fcall = Fcall(Tcreate)
        fcall.fid = fid
        fcall.name = name
        fcall.perm = perm
        fcall.mode = mode
        return self._rpc(fcall)
    def _read(self, fid, off, count):
        fcall = Fcall(Tread)
        fcall.fid = fid
        fcall.offset = off
        fcall.count = count
        return self._rpc(fcall)
    def _write(self, fid, off, data):
        fcall = Fcall(Twrite)
        fcall.fid = fid
        fcall.offset = off
        fcall.data = data
        return self._rpc(fcall)
    def _clunk(self, fid):
        fcall = Fcall(Tclunk)
        fcall.fid = fid
        return self._rpc(fcall)
    def _remove(self, fid):
        fcall = Fcall(Tremove)
        fcall.fid = fid
        return self._rpc(fcall)
    def _stat(self, fid):
        fcall = Fcall(Tstat)
        fcall.fid = fid
        return self._rpc(fcall)
    def _wstat(self, fid, stats):
        fcall = Fcall(Wstat)
        fcall.fid = fid
        fcall.stats = stats
        return self._rpc(fcall)

    def _fullclose(self):
        self._clunk(self.ROOT)
        self._clunk(self.CWD)
        self.fd.close()

    def login(self, user, passwd, authsrv):
        fcall = self._version(8 * 1024, version)
        if fcall.version != version:
            raise ClientError("version mismatch: %r" % req.version)

        fcall.afid = self.AFID
        try:
            rfcall = self._auth(fcall.afid, user, '')
        except RpcError,e:
            fcall.afid = NOFID

        if fcall.afid != NOFID:
            fcall.aqid = rfcall.aqid
            if passwd is None:
                raise ClientError("Password required")

            import py9psk1, socket
            try:
                py9psk1.clientAuth(self, fcall, user, py9psk1.makeKey(passwd), authsrv, py9psk1.AUTHPORT)
            except socket.error,e:
                raise ClientError("%s: %s" % (authsrv, e.args[1]))
        self._attach(self.ROOT, fcall.afid, user, "")
        if fcall.afid != NOFID:
            self._clunk(fcall.afid)
        self._walk(self.ROOT, self.CWD, [])
        self.path = '/'


    # user accessible calls, the actual implementation of a client
    def close(self):
        self._clunk(self.F)

    def walk(self, pstr=''):
        root = self.CWD
        if pstr == '':
            path = []
        else:
            path = pstr.split("/")
            if path[0] == '':
                root = self.ROOT
                path = path[1:]
            path = filter(None, path)
        try: 
            fcall = self._walk(root, self.F, path)
        except RpcError,e:
            print "%s: %s" % (pstr, e.args[0])
            return

        if len(fcall.wqid) < len(path):
            print "%s: not found" % pstr
            return
        return fcall.wqid

    def open(self, pstr='', mode=0):
        if self.walk(pstr) is None:
            return
        self.pos = 0L
        try:
            fcall = self._open(self.F, mode)
        except RpcError, e:
            self.close()
            raise
        return fcall

    def create(self, pstr, perm=0644, mode=1):
        p = pstr.split("/")
        pstr2,name = "/".join(p[:-1]),p[-1]
        if self.walk(pstr2) is None:
            return
        self.pos = 0L
        try:
            return self._create(self.F, name, perm, mode)
        except RpcError,e:
            self.close()
            raise

    def rm(self, pstr):
        self.open(pstr)
        self._remove(self.F)
        self.close()

    def read(self, l):
        try:
            fcall = self._read(self.F, self.pos, l)
            buf = fcall.data
        except RpcError, e:
            self.close()
            raise

        self.pos += len(buf)
        return buf

    def write(self, buf):
        try:
            l = self._write(self.F, self.pos, buf).count
            self.pos += l
            return l
        except RpcError, e:
            self.close()
            raise

    def stat(self, pstr):
        ret = []
        if self.walk(pstr) is None:
            print "%s: not found" % pstr
        else:
            stats = self._stat(self.F).stat
            for stat in stats:
                ret.append(stat.tolstr())
            self.close()
        
    def ls(self, long=0):
        ret = []
        if self.open() is None:
            return
        try:
            while 1:
                buf = self.read(8192)
                if len(buf) == 0:
                    break

                p9 = Marshal9P()
                p9.setBuf(buf)
                fcall = Fcall(Rstat)
                p9.decstat(fcall, 0)
                for stat in fcall.stat:
                    if long:
                        ret.append(stat.tolstr())
                    else:
                        ret.append(stat.name)
        finally:
            self.close()
        return ret

    def cd(self, pstr):
        q = self.walk(pstr)
        if q is None:
            return 0
        if q and not (q[-1].type & QTDIR):
            print "%s: not a directory" % pstr
            self.close()
            return 0
        self.F, self.CWD = self.CWD, self.F
        self.close()
        return 1


