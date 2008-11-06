#!/usr/bin/python

from ninep import proto

class ninepclient(object) :
    """
    A client interface to the protocol.
    Subclass this to provide service
    """
    verbose = 0
    def __init__(self, fd) :
        self.msg = Marshal9P(fd)

    def _rpc(self, type, *args) :
        tag = 1
        if type == Tversion :
            tag = notag
        if self.verbose :
            print cmdName[type], repr(args)
        self.msg.send(type, tag, *args)
        rtype,rtag,vals = self.msg.recv()
        if self.verbose :
            print cmdName[rtype], repr(vals)
        if rtag != tag :
            raise Error("invalid tag received")
        if rtype == Rerror :
            raise RpcError(vals)
        if rtype != type + 1 :
            raise Error("incorrect reply from server: %r" % [rtype,rtag,vals])
        return vals

    def version(self, msize, version) :
        return self._rpc(Tversion, msize, version)
    def auth(self, fid, uname, aname) :
        return self._rpc(Tauth, fid, uname, aname)
    def attach(self, fid, afid, uname, aname) :
        return self._rpc(Tattach, fid, afid, uname, aname)
    def walk(self, fid, newfid, wnames) :
        return self._rpc(Twalk, (fid, newfid, wnames))
    def open(self, fid, mode) :
        return self._rpc(Topen, fid, mode)
    def create(self, fid, name, perm, mode) :
        return self._rpc(Tcreate, fid, name, perm, mode)
    def read(self, fid, off, count) :
        return self._rpc(Tread, fid, off, count)
    def write(self, fid, off, data) :
        return self._rpc(Twrite, fid, off, data)
    def clunk(self, fid) :
        return self._rpc(Tclunk, fid)
    def remove(self, fid) :
        return self._rpc(Tremove, fid)
    def stat(self, fid) :
        return self._rpc(Tstat, fid)
    def wstat(self, fid, stats) :
        return self._rpc(Twstat, fid, stats)

class NinepClient(object) :
    """
    A tiny 9p client.
    """
    AFID = 10
    ROOT = 11
    CWD = 12
    F = 13

    def __init__(self, fd, user, passwd, authsrv) :
        self.rpc = ninep.RpcClient(fd)
        self.login(user, passwd, authsrv)

    def login(self, user, passwd, authsrv) :
        maxbuf,vers = self.rpc.version(16 * 1024, ninep.version)
        if vers != ninep.version :
            raise Error("version mismatch: %r" % vers)

        afid = self.AFID
        try :
            self.rpc.auth(afid, user, '')
            needauth = 1
        except ninep.RpcError,e :
            afid = ninep.nofid

        if afid != ninep.nofid :
            if passwd is None :
                raise Error("Password required")

            from ninep import sk1
            try :
                sk1.clientAuth(self.rpc, afid, user, ninep.sk1.makeKey(passwd), authsrv, ninepsk1.AUTHPORT)
            except socket.error,e :
                raise Error("%s: %s" % (authsrv, e.args[1]))
        self.rpc.attach(self.ROOT, afid, user, "")
        if afid != ninep.nofid :
            self.rpc.clunk(afid)
        self.rpc.walk(self.ROOT, self.CWD, [])

    def close(self) :
        self.rpc.clunk(self.ROOT)
        self.rpc.clunk(self.CWD)
        self.sock.close()

    def _walk(self, pstr='') :
        root = self.CWD
        if pstr == '' :
            path = []
        else :
            path = pstr.split("/")
            if path[0] == '' :
                root = self.ROOT
                path = path[1:]
            path = filter(None, path)
        try : 
            w = self.rpc.walk(root, self.F, path)
        except ninep.RpcError,e :
            print "%s: %s" % (pstr, e.args[0])
            return
        if len(w) < len(path) :
            print "%s: not found" % pstr
            return
        return w
    def _open(self, pstr='', mode=0) :
        if self._walk(pstr) is None :
            return
        self.pos = 0L
        return self.rpc.open(self.F, mode)
    def _create(self, pstr, perm=0644, mode=1) :
        p = pstr.split("/")
        pstr2,name = "/".join(p[:-1]),p[-1]
        if self._walk(pstr2) is None :
            return
        self.pos = 0L
        try :
            return self.rpc.create(self.F, name, perm, mode)
        except ninep.RpcError,e :
            self._close()
            raise ninep.RpcError(e.args[0])
    def _read(self, l) :
        buf = self.rpc.read(self.F, self.pos, l)
        self.pos += len(buf)
        return buf
    def _write(self, buf) :
        l = self.rpc.write(self.F, self.pos, buf)
        self.pos += l
        return l
    def _close(self) :
        self.rpc.clunk(self.F)

    def stat(self, pstr) :
        if self._walk(pstr) is None :
            print "%s: not found" % pstr
        else :
            for sz,t,d,q,m,at,mt,l,name,u,g,mod in self.rpc.stat(self.F) :
                print "%s %s %s %-8d\t\t%s" % (modeStr(m), u, g, l, name)
            self._close()
        
    def ls(self, long=0) :
        if self._open() is None :
            return
        while 1 :
            buf = self._read(4096)
            if len(buf) == 0 :
                break
            p9 = self.rpc.msg
            p9.setBuf(buf)
            for sz,t,d,q,m,at,mt,l,name,u,g,mod in p9._decStat(0) :
                if long :
                    print "%s %s %s %-8d\t\t%s" % (modeStr(m), u, g, l, name)
                else :
                    print name,
        if not long :
            print
        self._close()
    def cd(self, pstr) :
        q = self._walk(pstr)
        if q is None :
            return
        if q and not (q[-1][0] & ninep.QDIR) :
            print "%s: not a directory" % pstr
            self._close()
            return
        self.F,self.CWD = self.CWD,self.F
        self._close()

    def mkdir(self, pstr, perm=0644) :
        self._create(pstr, perm | ninep.DIR)
        self._close()

    def cat(self, name, out=None) :
        if out is None :
            out = sys.stdout
        if self._open(name) is None :
            return
        while 1 :
            buf = self._read(4096)
            if len(buf) == 0 :
                break
            out.write(buf)
        self._close()
    def put(self, name, inf=None) :
        if inf is None :
            inf = sys.stdin
        x = self._create(name)
        if x is None :
            x = self._open(name, ninep.OWRITE|ninep.OTRUNC)
            if x is None :
                return
        sz = 1024
        while 1 :
            buf = inf.read(sz)
            self._write(buf)
            if len(buf) < sz :
                break
        self._close()
    def rm(self, pstr) :
        self._open(pstr)
        self.rpc.remove(self.F)

