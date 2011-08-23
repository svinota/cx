#!/usr/bin/env python

import py9p
import sys
import getopt
import os

from threading import Thread

from vfs import Inode, Storage, v9fs
from ip_interface import interface, InterfaceInode
from ip_playback import sync

from cStringIO import StringIO

from cxnet.netlink.iproute2 import iproute2

class RootDir(Inode):
    def __init__(self,storage):
        Inode.__init__(self,"/",self,qtype=py9p.DMDIR,storage=storage)
        self.storage = storage
        self.child_map = {
            "interfaces":   InterfacesDir,
        }


class InterfacesDir(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.ifaces = {}
        self.child_map = {
            "*":   InterfaceInode,
        }


    def sync_children(self):
        return [ x['dev'] for x in self.ifaces.values() if x.has_key('dev') ]

if __name__ == "__main__" :

    try:
        opt,args = getopt.getopt(sys.argv[1:], "Dp:l:")
    except Exception,e:
        print(e)
        print("usage: [-D] [-p port] [-l address]")
        sys.exit(0)

    port = py9p.PORT
    address = 'localhost'
    dbg = False

    for i,k in opt:
        if i == "-D":
            dbg = True
        if i == "-p":
            port = int(k)
        if i == "-l":
            address = k

    print("%s:%s, debug=%s" % (address,port,dbg))
    storage = Storage(RootDir)
    srv = py9p.Server(listen=(address, port), chatty=dbg, dotu=True)
    srv.mount(v9fs(storage))

    ifaces = {}
    ifaces['by-name'] = dict([ (x['dev'],x) for x in ifaces.values() ])
    iproute2.get_all_links()
    iproute2.get_all_addrs()
    storage.root.sync()
    storage.root.children["interfaces"].ifaces = ifaces
    storage.root.children["interfaces"].subst_map = ifaces['by-name']

    s = Thread(target=sync,name="sync thread",args=(ifaces,True))
    s.daemon = True
    s.start()

    srv.serve()
