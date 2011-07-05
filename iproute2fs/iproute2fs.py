#!/usr/bin/env python

import py9p
import sys
import getopt
import os

from vfs import Inode, Storage, v9fs
from cStringIO import StringIO

from cxnet.netlink.iproute2 import iproute2

class RootDir(Inode):
    def __init__(self,storage):
        Inode.__init__(self,"/",self,qtype=py9p.DMDIR,storage=storage)
        self.storage = storage
        self.child_map = {
            "README":       ReadmeInode,
            "ifmap":        MapInode,
            "interfaces":   IfacesDir,
            "log":          LogInode,
        }

class IfacesDir(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.child_map = {
            "*":        InterfaceDir,
        }

    def sync_children(self):
        return [ x['dev'] for x in iproute2.get_all_links() ]

class MapInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        [ self.data.write("%-16s\t%-17s\n" % (x,y)) for x,y in [ (z["dev"],z["hwaddr"]) for z in iproute2.get_all_links() ] ]

class InterfaceDir(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.child_map = {
            "addresses":    AdressesInode,
            "flags":        FlagsInode,
            "mtu":          MtuInode,
            "hwaddr":       HwAddressInode,
        }

class LogInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_END)
        while iproute2.status()[0] > 0:
            for item in iproute2.get():
                t = item["timestamp"]
                del item["timestamp"]
                print "add %s" % (item)
                self.data.write("%s %s\n" % (t,str(item)))

class ReadmeInode(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent)
        self.data = StringIO("""
        This filesystem is exported from a python script with 9P protocol.
        Interface data is obtained realtime via rtnetlink protocol.

        9P protocol: http://9p.cat-v.org/documentation/rfc/
        Source code: http://projects.radlinux.org/cx/browser/cx/storage/iproute2fs.py

        You can get all source tree with git clone git://projects.radlinux.org/cx
        Please note, that the project is in early alpha.

        ...

        Almost all data is yet read-only, but one can change interface addresses
        just by editing interfaces/.../addresses file. Something like that:

        Set an address:
        echo 192.168.0.1/24 >interfaces/eth0/addresses

        Add one more address:
        echo -e '192.168.0.2/24\\n192.168.0.3/24' >>interfaces/eth0/addresses

        Remove an address:
        sed -i '/192.168.0.3/d' interfaces/eth0/addresses

        Flush all addresses:
        cat /dev/null >interfaces/eth0/addresses
""")

class InterfaceInode(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent)
        self.iface = self.parent.name
        self.addresses = []

class MtuInode(InterfaceInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(str(iproute2.get_link(self.iface)['mtu']))

class FlagsInode(InterfaceInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(",".join(iproute2.get_link(self.iface)['flags']))

class HwAddressInode(InterfaceInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(iproute2.get_link(self.iface)['hwaddr'])

class AdressesInode(InterfaceInode):

    def sync(self):
        s = ""
        self.addresses = [ "%s/%s" % (x['local'],x['mask']) for x in iproute2.get_addr(self.iface) if x.has_key('local') ]
        for x in self.addresses:
            s += "%s\n" % (x)
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(s)

    def commit(self):
        # get addr. list
        self.data.seek(0,os.SEEK_SET)
        chs = set(self.addresses)
        prs = set([ x.strip() for x in self.data.readlines() ])
        to_delete = chs - prs
        to_create = prs - chs
        [ iproute2.del_addr(self.iface,x) for x in to_delete ]
        [ iproute2.add_addr(self.iface,x) for x in to_create ]



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
    srv.serve()
