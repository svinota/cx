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
            "interfaces":   IfacesDir,
            "by-type":      TypeDir,
            "log":          LogInode,
        }


class MappingDir(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.child_map = {
            "*":        self.fmap,
        }

class FilterDir(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.child_map = {
            "*":        InterfaceDir,
        }

###
#
# Filters for interfaces
#
class IfacesTypeDir(FilterDir):
    """
    Filter interfaces by types
    """
    def sync_children(self):
        if self.name == 'wifi':
            return [ x['dev'] for x in iproute2.get_all_links() if x['wireless'] is not None ]
        else:
            return [ x['dev'] for x in iproute2.get_all_links() if x['link_type'] == self.name.upper() ]


class IfacesDir(FilterDir):
    """
    Just all interfaces, not filtered
    """
    def sync_children(self):
        return [ x['dev'] for x in iproute2.get_all_links() ]


###
#
# Mapping containers
#
class TypeDir(MappingDir):
    """
    Create map of current interface types from 'link_type' and 'wireless' fields
    """
    fmap = IfacesTypeDir
    def sync_children(self):
        l = list(set([ x['link_type'].lower() for x in iproute2.get_all_links() ]))
        if len(set([ x['wireless'] for x in iproute2.get_all_links() ])) > 1:
            l.append("wifi")
        return l


###
#
#
#

class LogInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_END)
        while iproute2.status()[0] > 0:
            for item in iproute2.get():
                t = item["timestamp"]
                del item["timestamp"]
                print "add %s" % (item)
                self.data.write("%s %s\n" % (t,str(item)))

###
#
#
#
class InterfaceDir(Inode):
    """
    Minimal interface representation. This directory contains
    some basic properties, as IP addresses and so on. The
    directory is named after interface label.
    """
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent,qtype=py9p.DMDIR)
        self.ifname = name
        self.child_map = {
            "addresses":    AdressesInode,
            "flags":        FlagsInode,
            "mtu":          MtuInode,
            "hwaddr":       HwAddressInode,
        }

class PropertyInode(Inode):
    def __init__(self,name,parent):
        Inode.__init__(self,name,parent)
        self.ifname = self.parent.ifname
        self.addresses = []

class MtuInode(PropertyInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(str(iproute2.get_link(self.ifname)['mtu']))

class FlagsInode(PropertyInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(",".join(iproute2.get_link(self.ifname)['flags']))

class HwAddressInode(PropertyInode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(iproute2.get_link(self.ifname)['hwaddr'])

class AdressesInode(PropertyInode):

    def sync(self):
        s = ""
        self.addresses = [ "%s/%s" % (x['local'],x['mask']) for x in iproute2.get_addr(self.ifname) if x.has_key('local') ]
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
