#!/usr/bin/python

from py9p import py9p

errors = {
    Ebadoffset: "bad offset",
    Ebotch: "9P protocol botch",
    Ecreatenondir: "create in non-directory",
    Edupfid: "duplicate fid",
    Eduptag: "duplicate tag",
    Eisdir: "is a directory",
    Enocreate: "create prohibited",
    Enoremove: "remove prohibited",
    Enostat: "stat prohibited",
    Enotfound: "file not found",
    Enowstat: "wstat prohibited",
    Eperm: "permission denied",
    Eunknownfid: "unknown fid",
    Ebaddir: "bad directory in wstat",
    Ewalknodir: "walk in non-directory",
}

nochg2 = 0xffff
nochg4 = 0xffffffffL
nochg8 = 0xffffffffffffffffL
nochgS = ''

ServError = py9p.ServError
class Error(py9p.Error) : pass

def _os(func, *args) :
    try :
        return func(*args)
    except OSError,e :
        raise ServError(e.args[1])
    except IOError,e :
        raise ServError(e.args[1])

def _nf(func, *args) :
    try :
        return func(*args)
    except ServError,e :
        return


class py9pserver(object) :
    """
    A server interface to the protocol.
    Subclass this to provide service
    """

    verbose = 1 # server level verbosity

    BUFSZ = 8320

    # maps path names to filesystem objects
    mountTable = {}
    klasses = {}

    def __init__(self, fd) :
        self.msg = Marshal9P(fd)

    def _err(self, tag, msg) :
        print 'Error', msg        # XXX
        if self.verbose :
            print cmdName[Rerror], repr(msg)
        self.msg.send(Rerror, tag, msg)

    def normpath(p) :
        return os.path.normpath(os.path.abspath(p))

    def hash8(obj) :
        return abs(hash(obj))

    def uidname(u) :            # XXX
        return "%d" % u
    gidname = uidname           # XXX

    def mount(path, obj) :
        """
        Mount obj at path in the tree.  Path should exist and be a directory.
        Only one instance of obj of a given type is allowed since otherwise
        they would compete for the same storage in the File object.
        """
        k = obj.__class__
        if k in klasses :
            raise Error("only one server for %s allowed" % k)

        # XXX walk tree to ensure that mountpoint exists and is
        # a directory!
        path = normpath(path)
        if path not in mountTable :
            mountTable[path] = []
        mountTable[path].append(obj)
        klasses[k] = 1



    def rpc(self) :
        """
        Process a single RPC message.
        Return -1 on error.
        """
        type,tag,vals = self.msg.recv()
        if type not in cmdName :
            return self._err(tag, "Invalid message")
        name = "_srv" + cmdName[type]
        if self.verbose :
            print cmdName[type], repr(vals)
        if hasattr(self, name) :
            func = getattr(self, name)
            try :
                rvals = func(type, tag, vals)
            except ServError,e :
                self._err(tag, e.args[0])
                return 1                    # nonfatal
            if self.verbose :
                print cmdName[type+1], repr(rvals)
            self.msg.send(type + 1, tag, *rvals)
        else :
            return self._err(tag, "Unhandled message: %s" % cmdName[type])
        return 1

    def _walk(self, obj, path) :
        qs = []
        for p in path :
            if p == '/' :
                obj = self.root
            elif p == '..' :
                obj = obj.parent
            else :
                if p.find('/') >= 0 :
                    raise ServError("illegal character in file")
                obj = obj.walk(p)
            if obj is None :
                break
            qs.append(obj.getQid())
        return qs,obj

    def _srvTversion(self, type, tag, vals) :
        bufsz,vers = vals
        if vers[0:2] != '9P':
            vers = 'unknown' 
            return bufsz, vers

        if vers[0:8] == '9P2000.u':
            self.dotu = 1
        elif vers != '9P2000':
            raise ServError("unknown version %r" % vers)

        if bufsz > self.BUFSZ:
            bufsz = self.BUFSZ
        elif bufsz < self.BUFSZ:
            self.BUFSZ = bufsz
        return bufsz,vers

    def _srvTauth(self, type, tag, vals) :
        
        fid,uname,aname = vals
        obj = File('#a', self.authfs)
        self._setFid(fid, obj)
        return (obj.getQid(),)

    def _srvTattach(self, type, tag, vals) :
        fid,afid,uname,aname = vals
        a = self._getFid(afid)
        if a.suid != uname :
            raise ServError("not authenticated as %r" % uname)
        r = self._setFid(fid, self.root.dup())
        return (r.getQid(),)

    def _srvTflush(self, type, tag, vals) :
        return ()

    def _srvTwalk(self, type, tag, vals) :
        fid,nfid,names = vals
        obj = self._getFid(fid)
        qs,obj = self._walk(obj, names)
        if len(qs) == len(names) :
            self._setFid(nfid, obj)
        return qs,

    def _srvTopen(self, type, tag, vals) :
        fid,mode = vals
        obj = self._getFid(fid).dup()
        obj.open(mode)
        self.fid[fid] = obj
        return obj.getQid(),4096        # XXX

    def _srvTcreate(self, type, tag, vals) :
        fid,name,perm,mode = vals
        obj = self._getFid(fid)
        obj = obj.create(name, perm, mode)
        self.fid[fid] = obj
        return obj.getQid(),4096        # XXX

    def _srvTread(self, type, tag, vals) :
        fid,off,count = vals
        return self._getFid(fid).read(off, count),

    def _srvTwrite(self, type, tag, vals) :
        fid,off,data = vals
        return self._getFid(fid).write(off, data),

    def _srvTclunk(self, type, tag, vals) :
        fid = vals
        self._getFid(fid).clunk()
        del self.fid[fid]
        return None,

    def _srvTremove(self, type, tag, vals) :
        fid = vals
        obj = self._getFid(fid)
        # clunk even if remove fails
        r = self._srvTclunk(type, tag, vals)
        obj.remove()
        return r

    def _srvTstat(self, type, tag, vals) :
        fid = vals
        obj = self._getFid(fid)
        return [obj.stat()],

    def _srvTwstat(self, type, tag, vals) :
        fid,stats = vals
        if len(stats) != 1 :
            raise ServError("multiple stats")
        obj = self._getFid(fid)
        obj.wstat(stats[0])
        return None,

    def serve(self) :
        while self.rpc() :
            pass



