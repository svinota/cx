#!/usr/bin/python 

import sys
import socket
import os.path
import copy
import getopt
import getpass

import py9p, py9psrv, authfs, py9psk1

def usage(prog):
    print "usage:  %s [-a][-d][-m module][-p port][-r root][srvuser][domain]" % prog
    sys.exit(1)

class Server(py9psrv.netsrv):
    """
    A tiny 9p server.
    """
    def __init__(self):
        self.authfs = none
        self.root = py9p.File('/')
        self.fid = {}

def main(prog, *args):
    port = py9p.PORT
    root = '/'
    mods = []
    anon = 0
    user = None
    dom = None
    try :
        opt,args = getopt.getopt(args, "dam:p:r:")
    except :
        usage(prog)
    for opt,optarg in opt:
        if opt == "-d":
            global dbg
            import debug
            dbg = 1
        if opt == '-m':
            mods.append(optarg)
        if opt == '-r':
            root = optarg
        if opt == "-p":
            port = int(optarg)
        if opt == '-a':
            anon = 1

    if not anon:
        if len(args) < 2 :
            usage(prog)
        user = args[0]
        dom = args[1]
        passwd = getpass.getpass()
        key = py9psk1.makeKey(passwd)

    srv = py9psrv.netsrv(port=port, user=user, dom=dom)

    #srv.mount('/', py9p.File('/'))

    for m in mods:
        if os.path.dirname(m) != '':
            sys.path.append(os.path.dirname(m))
            m = os.path.basename(m)
        m = m.rstrip('.py')
        x = __import__(m)
        srv.mount(x.mountpoint, x.root)
        print '%s loaded.' % m

    srv.serve()

if __name__ == "__main__" :
    try :
        main(*sys.argv)
    except KeyboardInterrupt :
        print "interrupted."

