#!/usr/bin/env python
import time
import sys
import getopt
import os
import copy
import py9p
from cStringIO import StringIO

import getopt
import getpass


DEFAULT_DIR_MODE = 0750
DEFAULT_FILE_MODE = 0640

class Inode(py9p.Dir):
    """
    VFS inode, based on py9p.Dir
    """
    def __init__(self,name,qtype=0,parent=None):
        py9p.Dir.__init__(self,True)
        self.parent = parent
        self.name = name
        #
        # DMDIR = 0x80000000
        # QTDIR = 0x80
        #
        self.qid = py9p.Qid((qtype >> 24) & py9p.QTDIR, 0, py9p.hash8(name))
        self.type = 0
        self.dev = 0
        self.atime = self.mtime = int(time.time())
        self.uid = self.gid = self.muid = os.environ['USER']
        if self.qid.type & py9p.DMDIR:
            self.mode = py9p.DMDIR | DEFAULT_DIR_MODE
            self.children = []
        else:
            self.mode = DEFAULT_FILE_MODE
            self.data = StringIO()

    @property
    def length(self):
        if self.qid.type & py9p.QTDIR:
            return len(self.children)
        else:
            return self.data.len

class VFS(py9p.Server):
    """
    VFS 
    """
    mountpoint = '/'
    root = None
    files = {}

    def __init__(self):
        self.start = int(time.time())
        rootdir = Inode('/', py9p.DMDIR)
        rootdir.parent = rootdir
        self.root = rootdir    # / is its own parent, just so we don't fall off the edge of the earth
        self.files[self.root.qid.path] = self.root

    def create(self, srv, req):
        # get parent
        f = self.files[req.fid.qid.path]
        new = Inode(req.ifcall.name, req.ifcall.perm,f)
        self.files[new.qid.path] = new
        f.children.append(new)
        req.ofcall.qid = new.qid
        srv.respond(req, None)

    def open(self, srv, req):
        '''If we have a file tree then simply check whether the Qid matches
        anything inside. respond qid and iounit are set by protocol'''
        if not self.files.has_key(req.fid.qid.path):
            srv.respond(req, "unknown file")
        f = self.files[req.fid.qid.path]
        if (req.ifcall.mode & f.mode) != py9p.OREAD :
            raise py9p.ServerError("permission denied")
        srv.respond(req, None)

    def walk(self, srv, req):
        # root walks are handled inside the protocol if we have self.root
        # set, so don't do them here. '..' however is handled by us,
        # trivially

        f = self.files[req.fid.qid.path]
        if len(req.ifcall.wname) > 1:
            srv.respond(req, "don't know how to handle multiple walks yet")
            return

        if req.ifcall.wname[0] == '..':
            req.ofcall.wqid.append(f.parent.qid)
            srv.respond(req, None)
            return

        for x in f.children:
            if req.ifcall.wname[0] == x.name:
                req.ofcall.wqid.append(x.qid)
                srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    def wstat(self, srv, req):
        if not self.files.has_key(req.fid.qid.path):
            raise py9p.ServerError("file not found")

        f = self.files[req.fid.qid.path]
        s = req.ifcall.stat[0]

        # change uid?
        if s.uidnum != 0xFFFFFFFF:
            f.uid = getpwuid(s.uidnum).pw_name
        else:
            if s.uid:
                f.uid = s.uid
        # change gid?
        if s.gidnum != 0xFFFFFFFF:
            f.gid = getgrgid(s.gidnum).gr_name
        else:
            if s.gid:
                f.gid = s.gid
        # change mode?
        if s.mode != 0xFFFFFFFF:
            f.mode = ((f.mode & 07777) ^ f.mode) | (s.mode & 07777)
        # change name?
        if s.name:
            f.name = s.name

        srv.respond(req,None)

    def stat(self, srv, req):
        if not self.files.has_key(req.fid.qid.path):
            raise py9p.ServerError("file not found")
        req.ofcall.stat.append(self.files[req.fid.qid.path])
        srv.respond(req, None)

    def write(self, srv, req):
        if not self.files.has_key(req.fid.qid.path):
            raise py9p.ServerError("file not found")
        f = self.files[req.fid.qid.path]
        if f.qid.type & py9p.QTDIR:
            raise py9p.ServerError("Is a directory")
        f.data.seek(req.ifcall.offset)
        f.data.write(req.ifcall.data)
        f.length = f.data.len
        req.ofcall.count = len(req.ifcall.data)
        srv.respond(req, None)

    def read(self, srv, req):
        if not self.files.has_key(req.fid.qid.path):
            raise py9p.ServerError("file not found")

        f = self.files[req.fid.qid.path]
        if f.qid.type & py9p.QTDIR:
            req.ofcall.stat = []
            for x in f.children:
                req.ofcall.stat.append(x)
        else:
            f.data.seek(req.ifcall.offset)
            req.ofcall.data = f.data.read(req.ifcall.count)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)

def usage(argv0):
    print "usage:  %s [-dD] [-p port] [-l listen] [-a authmode] [srvuser domain]" % argv0
    sys.exit(1)

def main(prog, *args):

    # import rpdb2
    # rpdb2.start_embedded_debugger("bala")
    listen = 'localhost'
    port = py9p.PORT
    mods = []
    noauth = 0
    dbg = False
    user = None
    dom = None
    passwd = None
    authmode = None
    key = None
    dotu = 0

    try:
        opt,args = getopt.getopt(args, "dDp:l:a:")
    except Exception, msg:
        usage(prog)
    for opt,optarg in opt:
        if opt == '-d':
            dotu = optarg
        if opt == "-D":
            dbg = True
        if opt == "-p":
            port = int(optarg)
        if opt == '-l':
            listen = optarg
        if opt == '-a':
            authmode = optarg

    if authmode == 'sk1':
        if len(args) != 2:
            print >>sys.stderr, 'missing user and authsrv'
            usage(prog)
        else:
            py9p.sk1 = __import__("py9p.sk1").sk1
            user = args[0]
            dom = args[1]
            passwd = getpass.getpass()
            key = py9p.sk1.makeKey(passwd)
    elif authmode == 'pki':
        py9p.pki = __import__("py9p.pki").pki
        user = 'admin'
    elif authmode != None and authmode != 'none':
        print >>sys.stderr, "unknown auth type: %s; accepted: pki or sk1"%authmode
        sys.exit(1)

    srv = py9p.Server(listen=(listen, port), authmode=authmode, user=user, dom=dom, key=key, chatty=dbg)
    srv.mount(VFS())
    srv.serve()


if __name__ == "__main__" :
    try :
        main(*sys.argv)
    except KeyboardInterrupt :
        print "interrupted."
