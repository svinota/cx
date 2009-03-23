#!/usr/bin/python
import time
import sys
import getopt
import os
import copy
import py9p

class SampleFs(py9p.Server):
    """
    A sample plugin filesystem.
    """
    mountpoint = '/'
    root = None
    files = {}
    def __init__(self):
        self.start = int(time.time())
        rootdir = py9p.Dir(0)    # not dotu
        rootdir.type = 0
        rootdir.dev = 0
        rootdir.mode = 0755
        rootdir.atime = rootdir.mtime = int(time.time())
        rootdir.length = 0
        rootdir.name = '/'
        rootdir.uid = rootdir.gid = rootdir.muid = os.environ['USER']
        rootdir.qid = py9p.Qid(py9p.QTDIR, 0, py9p.hash8(rootdir.name))
        self.root = py9p.File(rootdir, rootdir)    # / is its own parent, just so we don't fall off the edge of the earth

        # two files in '/'
        f = copy.copy(rootdir)
        f.name = 'sample1'
        f.qid = py9p.Qid(0, 0, py9p.hash8(f.name))
        f.length = 1024
        self.root.children.append(py9p.File(f, rootdir))
        f = copy.copy(f)
        f.name = 'sample2'
        f.length = 8192
        f.qid = py9p.Qid(0, 0, py9p.hash8(f.name))
        self.root.children.append(py9p.File(f, rootdir))

        # an empty dir in '/'
        dir = copy.copy(rootdir)
        dir.name = 'dir'
        dir.qid = py9p.Qid(0, 0, py9p.hash8(f.name))

        # add everybody to the easy lookup table for Files
        self.files[self.root.dir.qid.path] = self.root
        for x in self.root.children:
            self.files[x.dir.qid.path] = x

    def open(self, srv, req):
        '''If we have a file tree then simply check whether the Qid matches
        anything inside. respond qid and iounit are set by protocol'''
        if not self.files.has_key(req.fid.qid.path):
            srv.respond(req, "unknown file")
        f = self.files[req.fid.qid.path]
        if (req.ifcall.mode & f.dir.mode) != py9p.OREAD :
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
            req.ofcall.wqid.append(f.parent.dir.qid)
            srv.respond(req, None)
            return

        newd = f.findchild(req.ifcall.wname[0])
        if newd:
            req.ofcall.wqid.append(newd.dir.qid)
            srv.respond(req, None)
            return

        srv.respond(req, "can't find %s"%req.ifcall.wname[0])
        return

    def read(self, srv, req):
        if not self.files.has_key(req.fid.qid.path):
            raise py9p.ServError("unknown file")

        f = self.files[req.fid.qid.path]
        if f.dir.qid.type & py9p.QTDIR:
            req.ofcall.stat = []
            for x in f.children:
                req.ofcall.stat.append(x.dir)
        elif f.dir.name == 'sample1':
            buf = '%d\n' % time.time()
            req.ofcall.data = buf[:req.ifcall.count]
        elif f.dir.name == 'sample2' :
            buf = 'The time is now %s. thank you for asking.\n' % time.asctime(time.localtime(time.time()))
            if req.ifcall.offset > len(buf):
                req.ofcall.data = ''
            else:
                req.ofcall.data = buf[req.ifcall.offset : req.ifcall.offset + req.ifcall.count]

        srv.respond(req, None)

def usage(argv0):
    print "usage:  %s [-D] [-p port] [-u user] [-d domain] [-a authmode] [srvuser domain]" % argv0
    sys.exit(1)

def main(prog, *args):
    listen = 'localhost'
    port = py9p.PORT
    mods = []
    noauth = 0
    dbg = False
    user = None
    dom = None
    authmode = None

    try:
        opt,args = getopt.getopt(args, "Dnp:l:u:d:a:")
    except Exception, msg:
        usage(prog)
    for opt,optarg in opt:
        if opt == "-D":
            dbg = True
        if opt == "-p":
            port = int(optarg)
        if opt == '-l':
            listen = optarg
        if opt == '-n':
            noauth = 1
        if opt == '-u':
            user = optarg
        if opt == '-d':
            dom = optarg
        if opt == '-a':
            authmode = optarg

    if(authmode == None or authmode == 'none'):
        authmode == None
        user = None
        dom = None
        passwd = None
        key = None
    elif authmode == 'sk1':
        if len(args) != 2:
            usage(prog)
        else:
            user = args[0]
            dom = args[1]
            passwd = getpass.getpass()
            key = py9p.sk1.makeKey(passwd)
    elif authmode == 'pki':
        user = 'admin'
    else:
        print >>sys.stderr, "unknown auth type: %s; accepted: pki or sk1"%authmode
        sys.exit(1)

    srv = py9p.Server(listen=(listen, port), user=user, dom=dom, key=key, chatty=dbg)
    srv.mount(SampleFs())

    for m in mods:
        if os.path.dirname(m) != '':
            sys.path.append(os.path.dirname(m))
            m = os.path.basename(m)
        m = m.rstrip('.py')
        x = __import__(m)
        srv.mount(x)
        print '%s loaded.' % m

    print 'listening on %s:%d...' % (listen, port)
    srv.serve()


if __name__ == "__main__" :
    try :
        main(*sys.argv)
    except KeyboardInterrupt :
        print "interrupted."
