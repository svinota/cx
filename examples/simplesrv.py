#!/usr/bin/python
import time
import sys
import getopt
import py9p
import py9p.py9psk1 as py9psk1

class SampleFs(py9p.Server):
    """
    A sample plugin filesystem.
    """
    dirs = {
        '/' : ['sample1', 'sample2'],
    }
    type = ord('S')
    cancreate = 0
    mountpoint = '/'
    def __init__(self):
        self.start = int(time.time())

    def estab(self, f, isroot):
        f.samptype = None
        if isroot :
            f.isdir = 1
            f.samptype = '/'
        else :
            pt = f.parent.samptype
            if (pt in self.dirs) and (f.basename in self.dirs[pt]):
                f.samptype = f.basename

    def walk(self, f, fn, n):
        if f.samptype in self.dirs and n in self.dirs[f.samptype] :
            return fn

    def remove(self, f):
        raise py9p.ServError("bad remove")
    def stat(self, f):
        return (0, 0, 0, None, 0644, self.start, int(time.time()),
                1024, None, 'uid', 'gid', 'muid')
    def wstat(self, f, st):
        raise py9p.ServError("bad wstat")
    def create(self, f, perm, mode):
        raise py9p.ServError("bad create")
    def exists(self, f):
        return (f.samptype is not None)
    def open(self, f, mode):
        if (mode & 0777) != py9p.OREAD :
            raise py9p.ServError("permission denied")
    def clunk(self, f):
        pass
    def list(self, f):
        if f.samptype in self.dirs :
            return self.dirs[f.samptype]

    def read(self, f, pos, l):
        if f.samptype == 'sample1' :
            buf = '%d\n' % time.time()
            return buf[:l]
        elif f.samptype == 'sample2' :
            buf = 'The time is now %s. thank you for asking.\n' % time.asctime(time.localtime(time.time()))
            return buf[pos : pos + l]
        return ''
        
    def write(self, f, pos, buf):
        raise py9p.ServError('not opened for writing')
        

def usage(argv0):
    print "usage:  %s [-nD] [-p port] [-u user] [-d domain]" % argv0
    sys.exit(1)

def main(prog, *args):
    port = py9p.PORT
    listen = 'localhost'
    mods = []
    noauth = 0
    dbg = False
    user = None
    dom = None

    try:
        opt,args = getopt.getopt(args, "Dnp:l:u:d:")
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
            

    if(noauth):
        user = None
        dom = None
        passwd = None
        key = None
    else:
        if user == None or dom == None:
            print >>sys.stderr, "authentication requires user (-u) and domain (-d)"
            usage(prog)
        passwd = getpass.getpass()
        key = p9sk1.makeKey(passwd)

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

