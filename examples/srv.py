#!/usr/bin/python 

import sys
import socket
import os.path
import copy

from ninep import proto, authfs

class Server(proto.server) :
    """
    A tiny 9p server.
    """
    def __init__(self, fd, user=None, dom=None, key=None) :
        proto.server.__init__(self, fd)

        self.authfs = AuthFs(user, dom, key)
        self.root = proto.File('/')
        self.fid = {}

def sockserver(user, dom, key, port=ninep.PORT) :
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', port),)
    sock.listen(1)
    while 1 :
        sock2,addr = sock.accept()
        # XXX fork is breaking in cygwin, looks like a bug, possibly
        # due to importing the crypto dll?
        if dbg or not hasattr(os, 'fork') or sys.platform == 'cygwin' or os.fork() == 0 :
            sock.close()
            break
        sock2.close()

    try :
        print "serving: %r,%r" % addr
        s = Server(ninep.Sock(sock2), user, dom, key) 
        s.serve()
        print "done serving %r,%r" % addr
    except ninep.Error,e :
        print e.args[0]

def usage(prog) :
    print "usage:  %s [-d] [-m module] [-p port] [-r root] srvuser domain" % prog
    sys.exit(1)

def main(prog, *args) :
    import getopt
    import getpass

    port = ninep.PORT
    root = '/'
    mods = []
    try :
        opt,args = getopt.getopt(args, "dm:p:r:")
    except :
        usage(prog)
    for opt,optarg in opt :
        if opt == "-d" :
            global dbg
            import debug
            dbg = 1
        if opt == '-m' :
            mods.append(optarg)
        if opt == '-r' :
            root = optarg
        if opt == "-p" :
            port = int(optarg)

    if len(args) < 2 :
        usage(prog)
    user = args[0]
    dom = args[1]
    passwd = getpass.getpass()
    key = sk1.makeKey(passwd)

    for m in mods :
        x = __import__(m)
        mount(x.mountpoint, x.root)
        print '%s loaded.' % m
    sockserver(user, dom, key, port)

if __name__ == "__main__" :
    try :
        main(*sys.argv)
    except KeyboardInterrupt :
        print "interrupted."

