#!/usr/bin/python 

import sys
import socket
import stat
import os.path
import copy
import time

import py9p
import py9p.py9psk1 as py9psk1

def _os(func, *args):
    try:
        return func(*args)
    except OSError,e:
        raise py9p.ServerError(e.args[1])
    except IOError,e:
        raise py9p.ServerError(e.args[1])

def _nf(func, *args):
    try:
        return func(*args)
    except py9p.ServerError,e:
        return

def uidname(u) :            # XXX
    return "%d" % u
gidname = uidname            # XXX

class LocalFs(object) :
    """
    A local filesystem device.
    """
    type = ord('f')
    mountpoint = py9p.normpath('/tmp')

    def __init__(self, root=None, cancreate=1) :
        if root:
            self.root = py9p.normpath(root) 
        self.cancreate = cancreate 

    def estab(self, f, isroot) :
        if isroot :
            f.localpath = self.root
        else :
            f.localpath = py9p.normpath(os.path.join(f.parent.localpath, f.basename))
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
            res = res | py9p.DIR
            
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
        if perm & py9p.DIR :
            _os(os.mkdir, f.localpath, perm & ~py9p.DIR)
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
            if (mode & 3) == py9p.OWRITE :
                if mode & py9p.OTRUNC :
                    m = "wb"
                else :
                    m = "r+b"        # almost
            elif (mode & 3) == py9p.ORDWR :
                if m & OTRUNC :
                    m = "w+b"
                else :
                    m = "r+b"
            else :                # py9p.OREAD and otherwise
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

def usage(prog):
    print "usage:  %s [-d] [-n] [-m module] [-p port] [-r root] [-l listen] srvuser domain" % prog
    sys.exit(1)

def main():
    import getopt
    import getpass

    prog = sys.argv[0]
    args = sys.argv[1:]

    port = py9p.PORT
    listen = '0.0.0.0'
    root = None
    mods = []
    noauth = 0
    chatty = 0

    try:
        opt,args = getopt.getopt(args, "dncm:p:r:l:")
    except:
        usage(prog)
    for opt,optarg in opt:
        if opt == "-d":
            chatty = 1
        if opt == '-m':
            mods.append(optarg)
        if opt == '-c':
            chatty = chatty + 1
        if opt == '-r':
            root = optarg
        if opt == "-n":
            noauth = 1
        if opt == "-p":
            port = int(optarg)
        if opt == '-l':
            listen = optarg

    if(noauth):
        user = None
        dom = None
        passwd = None
        key = None
    elif len(args) != 2:
        usage(prog)
    else:
        user = args[0]
        dom = args[1]
        passwd = getpass.getpass()
        key = py9psk1.makeKey(passwd)

    srv = py9p.Server(listen=(listen, port), user=user, dom=dom, key=key, chatty=chatty)
    srv.mount(LocalFs(root))

    for m in mods:
        x = __import__(m)
        mount(x.mountpoint, x.root)
        print '%s loaded.' % m

    srv.serve()

#'''
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "interrupted."
'''
if __name__ == "__main__":
    import trace

    # create a Trace object, telling it what to ignore, and whether to
    # do tracing or line-counting or both.
    tracer = trace.Trace(
        ignoredirs=[sys.prefix, sys.exec_prefix],
        trace=1,
        count=1)

    # run the new command using the given tracer
    tracer.run('main()')
    # make a report, placing output in /tmp
    r = tracer.results()
    r.write_results(show_missing=True, coverdir="/tmp")
#'''
