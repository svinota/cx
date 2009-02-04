#!/usr/bin/python
import socket
import sys
import os
import getopt
import getpass

import py9p

class Error(py9p.Error): pass

def modeStr(mode):
    bits = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
    def b(s):
        return bits[(mode>>s) & 7]
    d = "-"
    if mode & py9p.DIR:
        d = "d"
    return "%s%s%s%s" % (d, b(6), b(3), b(0))

def _os(func, *args):
    try:
        return func(*args)
    except OSError,e:
        raise Error(e.args[1])
    except IOError,e:
        raise Error(e.args[1])
    
class CmdClient(py9p.Client):
    def mkdir(self, pstr, perm=0644):
        self.create(pstr, perm | py9p.DIR)
        self.close()

    def cat(self, name, out=None):
        if out is None:
            out = sys.stdout
        if self.open(name) is None:
            return
        while 1:
            buf = self.read(8192*2)
            if len(buf) == 0:
                break
            out.write(buf)
        self.close()

    def put(self, name, inf=None):
        if inf is None:
            inf = sys.stdin
        x = self.create(name)
        if x is None:
            x = self.open(name, py9p.OWRITE|py9p.OTRUNC)
            if x is None:
                return
        sz = 1024
        while 1:
            buf = inf.read(sz)
            self.write(buf)
            if len(buf) < sz:
                break
        self.close()

    def _cmdwrite(self, args):
        if len(args) < 1:
            print "write: no file name"
        elif len(args) == 1:
            buf = ''
        else:
            buf = ' '.join(args[1:])

        name = args[0]
        x = self.open(name, py9p.OWRITE|py9p.OTRUNC)
        if x is None:
            return
        if buf != None:
            self.write(buf)
        self.close()

    def _cmdstat(self, args):
        for a in args:
            self.stat(a)
    def _cmdls(self, args):
        long = 0
        while len(args) > 0:
            if args[0] == "-l":
                long = 1
            else:
                print "usage: ls [-l]"
                return
            args[0:1] = []
        self.ls(long)
    def _cmdcd(self, args):
        if len(args) != 1:
            print "usage: cd path"
            return
        self.cd(args[0])
    def _cmdcat(self, args):
        if len(args) != 1:
            print "usage: cat path"
            return
        self.cat(args[0])

    def _cmdmkdir(self, args):
        if len(args) != 1:
            print "usage: mkdir path"
            return
        self.mkdir(args[0])
    def _cmdget(self, args):
        if len(args) == 1:
            f, = args
            f2 = f.split("/")[-1]
        elif len(args) == 2:
            f,f2 = args
        else:
            print "usage: get path [localname]"
            return
        out = _os(file, f2, "wb")
        self.cat(f, out)
        out.close()
    def _cmdput(self, args):
        if len(args) == 1:
            f, = args
            f2 = f.split("/")[-1]
        elif len(args) == 2:
            f,f2 = args
        else:
            print "usage: put path [remotename]"
            return
        if f == '-':
            inf = sys.stdin
        else:
            inf = _os(file, f, "rb")
        self.put(f2, inf)
        if f != '-':
            inf.close()
    def _cmdrm(self, args):
        if len(args) == 1:
            self.rm(args[0])
        else:
            print "usage: rm path"
    def _cmdhelp(self, args):
        cmds = [x[4:] for x in dir(self) if x[:4] == "_cmd"]
        cmds.sort()
        print "Commands: ", " ".join(cmds)
    def _cmdquit(self, args):
        self.done = 1
    _cmdexit = _cmdquit

    def _nextline(self):        # generator is cleaner but not supported in 2.2
        if self.cmds is None:
            sys.stdout.write("9p> ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if line != "":
                return line[:-1]
        else:
            if self.cmds:
                x,self.cmds = self.cmds[0],self.cmds[1:]
                return x
    def cmdLoop(self, cmds):
        cmdf = {}
        for n in dir(self):
            if n[:4] == "_cmd":
                cmdf[n[4:]] = getattr(self, n)

        if not cmds:
            cmds = None
        self.cmds = cmds
        self.done = 0
        while 1:
            line = self._nextline()
            if line is None:
                break
            args = filter(None, line.split(" "))
            if not args:
                continue
            cmd,args = args[0],args[1:]
            if cmd in cmdf:
                try:
                    cmdf[cmd](args)
                except py9p.Error,e:
                    print "%s: %s" % (cmd, e.args[0])
                    if e.args[0] == 'Client EOF':
                        break
            else:
                sys.stdout.write("%s ?\n" % cmd)
            if self.done:
                break

def usage(prog):
    print "usage: %s [-dn] [-a authsrv] [user@]srv[:port] [cmd ...]" % prog
    sys.exit(1)
    
def main(prog, *args):
    port = py9p.PORT
    authsrv = None
    chatty = 0
    try:
        opt,args = getopt.getopt(args, "nda:u:p:")
    except:
        usage(prog)
    passwd = ""

    if os.environ.has_key('USER'):
        user = os.environ['USER']

    for opt,optarg in opt:
        if opt == '-a':
            authsrv = optarg
#        if opt == "-d":
#            import py9p.debug
        if opt == '-d':
            chatty = 1
        if opt == '-n':
            passwd = None
        if opt == "-p":
            port = int(optarg)        # XXX catch
        if opt == '-u':
            user = optarg
    
    if len(args) < 1:
        print >>sys.stderr, "error: no server to connect to..."
        usage(prog)

    srvkey = args[0].split('@', 2)
    if len(srvkey) == 2:
        user = srvkey[0]
        srvkey = srvkey[1]

    srvkey = srvkey.split(':', 2)
    if len(srvkey) == 2:
        port = int(srvkey[1])
        srvkey = srvkey[0]

    srv = srvkey
    if chatty:
        print "connecting as %s to %s, port %d" % (user, srv, port)

    # 
    if passwd != None and authsrv is None:
        print >>sys.stderr, "assuming %s is also auth server" % srv
        authsrv = srv

    cmd = args[2:]

    sock = socket.socket(socket.AF_INET)
    try:
        sock.connect((srv, port),)
    except socket.error,e:
        print "%s: %s" % (srv, e.args[1])
        return

    if passwd is not None:
        passwd = getpass.getpass()
    try:
        cl = CmdClient(py9p.Sock(sock), user, passwd, authsrv, chatty)
        cl.cmdLoop(cmd)
    except py9p.Error,e:
        print e

if __name__ == "__main__":
    try:
        main(*sys.argv)
    except KeyboardInterrupt:
        print "interrupted."

