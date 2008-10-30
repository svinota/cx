import sys
import socket
import os.path
import copy
import stat

import P9
import srv

ServError = srv.ServError

def uidname(u) :            # XXX
    return "%d" % u
gidname = uidname            # XXX


def normpath(p) :
    return os.path.normpath(os.path.abspath(p))

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


class LocalFs(object) :
    """
    A local filesystem device.
    """
    type = ord('f')
    def __init__(self, root, cancreate=1) :
        self.root = normpath(root) 
        self.cancreate = cancreate 

    def estab(self, f, isroot) :
        if isroot :
            f.localpath = self.root
        else :
            f.localpath = normpath(os.path.join(f.parent.localpath, f.basename))
        f.isdir = os.path.isdir(f.localpath)
        f.fd = None

    def walk(self, f, fn, n) :
        if os.path.exists(fn.localpath) :
            return fn

    def remove(self, f) :
        if f.isdir :
            _os(os.rmdir, f.localpath)
        else :
            _os(os.remove, f.localpath)

    def stat(self, f) :
        s = _os(os.stat, f.localpath)
        u = uidname(s.st_uid)
        res = s.st_mode & 0777
        if stat.S_ISDIR(s.st_mode):
            res = res | P9.DIR
            
        return (0, 0, s.st_dev, None, res, 
                int(s.st_atime), int(s.st_mtime),
                s.st_size, None, u, gidname(s.st_gid), u)

    def wstat(self, f, st) :
        # nowhere near atomic
        l,t,d,q,mode,at,mt,sz,name,uid,gid,muid = st
        s = _os(os.stat, f.localpath)
        if sz != nochg8 :
            raise ServError("size changes unsupported")        # XXX
        if (uid,gid,muid) != (nochgS,nochgS,nochgS) :
            raise ServError("user change unsupported")        # XXX
        if name != nochgS :
            new = os.path.join(os.path.basedir(f.localpath), name)
            _os(os.rename, f.localpath, new)
            f.localpath = new
        if mode != nochg4 :
            _os(os.chmod, f.localpath, mode & 0777)

    def create(self, f, perm, mode) :
        # nowhere close to atomic. *sigh*
        if perm & P9.DIR :
            _os(os.mkdir, f.localpath, perm & ~P9.DIR)
            f.isdir = 1
        else :
            _os(file, f.localpath, "w+").close()
            _os(os.chmod, f.localpath, perm & 0777)
            f.isdir = 0
        return self.open(f, mode)
        
    def exists(self, f) :
        return os.path.exists(f.localpath)

    def open(self, f, mode) :
        if not f.isdir :
            if (mode & 3) == P9.OWRITE :
                if mode & P9.OTRUNC :
                    m = "wb"
                else :
                    m = "r+b"        # almost
            elif (mode & 3) == P9.ORDWR :
                if m & OTRUNC :
                    m = "w+b"
                else :
                    m = "r+b"
            else :                # P9.OREAD and otherwise
                m = "rb"
            f.fd = _os(file, f.localpath, m)

    def clunk(self, f) :
        if f.fd is not None :
            f.fd.close()
            f.fd = None

    def list(self, f) :
        l = os.listdir(f.localpath)
        return filter(lambda x : x not in ('.','..'), l)

    def read(self, f, pos, l) :
        f.fd.seek(pos)
        return f.fd.read(l)

    def write(self, f, pos, buf) :
        f.fd.seek(pos)
        f.fd.write(buf)
        return len(buf)

root = LocalFs('/tmp')
mountpoint = '/'

