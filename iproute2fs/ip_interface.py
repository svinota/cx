#!/usr/bin/env python

from vfs import Inode
from cxnet.netlink.iproute2 import iproute2
import py9p
import os

###
#
#
#
class interface(dict):
    """
    Minimal interface representation. This directory contains
    some basic properties, as IP addresses and so on. The
    directory is named after interface label.
    """
    def __init__(self,rt_dict):
        dict.__init__(self,rt_dict)
        self['addresses'] = {}

    def __hash__(self):
        return hash(self.__getitem__("dev"))

class InterfaceInode(Inode):
    def __init__(self,rt_dict,parent):
        Inode.__init__(self,rt_dict["dev"],parent,qtype=py9p.DMDIR)
        self.interface = rt_dict
        self.child_map = {
            "addresses":    AdressesInode,
            "flags":        FlagsInode,
            "mtu":          MtuInode,
            "hwaddr":       HwAddressInode,
        }

class MtuInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(str(self.parent.interface['mtu']))

class FlagsInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(",".join(self.parent.interface['flags']))

class HwAddressInode(Inode):
    def sync(self):
        self.data.seek(0,os.SEEK_SET)
        self.data.truncate()
        self.data.write(self.parent.interface['hwaddr'])

class AdressesInode(Inode):

    def sync(self):
        s = ""
        self.addresses = [ "%s/%s" % (x['address'],x['mask']) for x in self.parent.interface['addresses'].values() ]
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
        try:
            [ iproute2.del_addr(self.parent.interface['dev'],x) for x in to_delete ]
            [ iproute2.add_addr(self.parent.interface['dev'],x) for x in to_create ]
        except Exception,e:
            print e

