#!/usr/bin/env python
import time
import sys
import getopt
import os
import copy
import py9p
import pwd
import grp
from cStringIO import StringIO

import getopt
import getpass

from cxnet.netlink.iproute2 import iproute2

DEFAULT_DIR_MODE = 0755
DEFAULT_FILE_MODE = 0644

class Inode(py9p.Dir):
    """
    VFS inode, based on py9p.Dir
    """
    def __init__(self,name,parent,qtype=0,storage=None):
        py9p.Dir.__init__(self,True)

        self.parent = parent
        self.storage = storage or parent.storage
        self.name = name
        #
        # DMDIR = 0x80000000
        # QTDIR = 0x80
        #
        self.qid = py9p.Qid((qtype >> 24) & py9p.QTDIR, 0, py9p.hash8(self.absolute_name()))
        self.type = 0
        self.dev = 0
        self.atime = self.mtime = int(time.time())
        self.uidnum = self.muidnum = os.getuid()
        self.gidnum = os.getgid()
        self.uid = self.muid = pwd.getpwuid(self.uidnum).pw_name
        self.gid = grp.getgrgid(self.gidnum).gr_name
        self.children = {}
        self.static_children = []
        self.writelock = False
        if self.qid.type & py9p.QTDIR:
            self.mode = py9p.DMDIR | DEFAULT_DIR_MODE
            self.children["."] = self
            self.children[".."] = self.parent
            self.special_names = [".",".."]
        else:
            self.mode = DEFAULT_FILE_MODE
            self.data = StringIO()
            self.special_names = []

        self.storage.register(self)
        self.child_map = {}
        self.subst_map = {}

    def absolute_name(self):
        if (self.parent is not None) and (self.parent != self):
            return "%s/%s" % (self.parent.absolute_name(),self.name)
        else:
            return self.name

    def commit(self):
        pass

    def sync_children(self):
        return [ x for x in self.child_map.keys() if x != "*" ]

    def remove(self,child):
        if child.name in self.static_children:
            self.static_children.remove(child.name)
            del self.children[child.name]

    def create(self,name,qtype=0):
        # get additional parameters by name, if there is what to get
        if self.subst_map.has_key(name):
            name = self.subst_map[name]
        # return a specific class
        if self.child_map.has_key(name):
            return self.child_map[name](name,self)
        # return non-specific "wildcard" class, if exists
        if self.child_map.has_key("*"):
            return self.child_map["*"](name,self)
        # return default Inode class otherwise
        self.children[name] = Inode(name,self,qtype=qtype,storage=self.storage)
        self.static_children.append(name)
        return self.children[name]

    def rename(self,old_name,new_name):

        self.sync()

        if new_name in self.child_map.keys():
            # the target is special and exists already
            self.children[new_name].data = self.children[old_name].data
            self.children[new_name].commit()
        else:
            self.children[new_name] = self.children[old_name]
            if new_name not in self.static_children:
                self.static_children.append(new_name)

        del self.children[old_name]
        self.static_children.remove(old_name)

    def wstat(self,stat):
        # change uid?
        if stat.uidnum != 0xFFFFFFFF:
            self.uid = getpwuid(stat.uidnum).pw_name
        else:
            if stat.uid:
                self.uid = stat.uid
        # change gid?
        if stat.gidnum != 0xFFFFFFFF:
            self.gid = getgrgid(stat.gidnum).gr_name
        else:
            if stat.gid:
                self.gid = stat.gid
        # change mode?
        if stat.mode != 0xFFFFFFFF:
            self.mode = ((self.mode & 07777) ^ self.mode) | (stat.mode & 07777)
        # change name?
        if stat.name:
            # update parent
            self.parent.rename(self.name,stat.name)
            self.name = stat.name

    def sync(self):
        # create set of children names
        chs = set(self.children.keys())
        # create set of actual items
        prs = set(self.sync_children() + self.static_children)

        # inodes to delete
        to_delete = chs - prs
        # preserve special names
        [ to_delete.remove(x) for x in self.special_names ]
        # remove from storage
        [ self.storage.unregister(x) for x in [ self.children[y].qid.path for y in to_delete ] ]
        # remove from children
        [ self.children.__delitem__(x) for x in to_delete ]
        # inodes to create
        to_create = prs - chs
        # add to children
        [ self.children.__setitem__(x.name,x) for x in [ self.create(y) for y in to_create ] ]
        # add to storage
        [ self.storage.register(x) for x in [ self.children[y] for y in to_create ] ]

        [ self.children[y].sync() for x in to_create ]

    @property
    def length(self):
        if self.qid.type & py9p.QTDIR:
            return len(self.children.keys()) + len(self.static_children)
        else:
            self.data.seek(0,os.SEEK_END)
            return self.data.tell()


class Storage(object):
    """
    Low-level storage interface
    """
    def __init__(self,root):
        self.files = {}
        self.root = root(storage=self)
        self.cwd = self.root
        self.files[self.root.qid.path] = self.root

    def register(self,inode):
        self.files[inode.qid.path] = inode

    def unregister(self,inode):
        del self.files[inode.qid.path]

    def create(self,name,mode=0,parent=None):
        if parent:
            self.cwd = parent
        new = self.cwd.create(name,mode)
        self.files[new.qid.path] = new
        return new.qid

    def chdir(self,target):
        if isinstance(target,py9p.Qid):
            self.cwd = self.files[target]

    def checkout(self,target):
        if not self.files.has_key(target):
            raise py9p.ServerError("file not found")
        return self.files[target]

    def commit(self,target):
        f = self.checkout(target)
        if f.writelock:
            f.writelock = False
            f.commit()

    def write(self,target,data,offset=0):
        f = self.checkout(target)

        f.writelock = True

        if f.qid.type & py9p.QTDIR:
            raise py9p.ServerError("Is a directory")

        f.data.seek(offset,os.SEEK_SET)
        f.data.write(data)
        return len(data)

    def read(self,target,size,offset=0):
        f = self.checkout(target)
        if offset == 0:
            f.sync()
        f.data.seek(offset,os.SEEK_SET)
        return f.data.read(size)

    def remove(self,target):
        f = self.checkout(target)
        f.remove(f)
        del self.files[target]

    def wstat(self,target,stat):

        f = self.checkout(target)
        f.wstat(stat)


class v9fs(py9p.Server):
    """
    VFS 9p abstraction layer
    """

    def __init__(self, storage):
        self.mountpoint = '/'
        self.storage = storage
        self.root = self.storage.root

    def create(self, srv, req):
        # get parent
        f = self.storage.checkout(req.fid.qid.path)
        req.ofcall.qid = self.storage.create(req.ifcall.name, req.ifcall.perm,f)
        srv.respond(req, None)

    def open(self, srv, req):
        '''If we have a file tree then simply check whether the Qid matches
        anything inside. respond qid and iounit are set by protocol'''
        f = self.storage.checkout(req.fid.qid.path)
        f.sync()

        if (req.ifcall.mode & f.mode) != py9p.OREAD :
            raise py9p.ServerError("permission denied")

        srv.respond(req, None)

    def walk(self, srv, req, fid = None):

        fd = fid or req.fid
        f = self.storage.checkout(fd.qid.path)
        f.sync()

        for (i,k) in f.children.items():
            if req.ifcall.wname[0] == i:
                req.ofcall.wqid.append(k.qid)
                if k.qid.type & py9p.QTDIR:
                    self.storage.chdir(k.qid.path)
                if len(req.ifcall.wname) > 1:
                    req.ifcall.wname.pop(0)
                    self.walk(srv,req,k)
                else:
                    srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    def wstat(self, srv, req):

        f = self.storage.checkout(req.fid.qid.path)
        s = req.ifcall.stat[0]
        self.storage.wstat(req.fid.qid.path,s)
        srv.respond(req,None)

    def stat(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        f.sync()
        req.ofcall.stat.append(f)
        srv.respond(req, None)

    def write(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        req.ofcall.count = self.storage.write(req.fid.qid.path,req.ifcall.data,req.ifcall.offset)
        srv.respond(req, None)

    def clunk(self, srv, req):
        self.storage.commit(req.fid.qid.path)
        srv.respond(req, None)

    def read(self, srv, req):

        f = self.storage.checkout(req.fid.qid.path)

        if f.qid.type & py9p.QTDIR:
            f.sync()
            req.ofcall.stat = []
            for (i,k) in f.children.items():
                if i not in (".",".."):
                    req.ofcall.stat.append(k)
        else:
            if req.ifcall.offset == 0:
                f.sync()
            req.ofcall.data = self.storage.read(f.qid.path,req.ifcall.count,req.ifcall.offset)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)


