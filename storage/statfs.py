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

from cxnet.netlink.taskstats import *

DEFAULT_DIR_MODE = 0750
DEFAULT_FILE_MODE = 0640

class Taskstats(object):

    def __init__(self):
        self.s = genl_socket()
        self.prid = self.s.get_protocol_id("TASKSTATS")


    def get(self,pid):
        (l,msg) = self.s.send_cmd(self.prid,TASKSTATS_CMD_GET,TASKSTATS_TYPE_PID,c_uint32(pid))
        a = nlattr.from_address(addressof(msg.data))
        pid = nlattr.from_address(addressof(msg.data) + sizeof(a))
        stats = taskstatsmsg.from_address(addressof(msg.data) + sizeof(a) + NLMSG_ALIGN(pid.nla_len) + sizeof(nlattr))
        return stats

taskstats = Taskstats()


class Inode(py9p.Dir):
    """
    VFS inode, based on py9p.Dir
    """
    def __init__(self,name,qtype=0,parent=None):
        py9p.Dir.__init__(self,True)
        self.parent = parent
        self.name = name
        #
        # DMDIR = 0x80000000
        # QTDIR = 0x80
        #
        self.qid = py9p.Qid((qtype >> 24) & py9p.QTDIR, 0, py9p.hash8(name))
        self.type = 0
        self.dev = 0
        self.atime = self.mtime = int(time.time())
        self.uidnum = self.muidnum = os.getuid()
        self.gidnum = os.getgid()
        self.uid = self.muid = pwd.getpwuid(self.uidnum).pw_name
        self.gid = grp.getgrgid(self.gidnum).gr_name
        self.children = []
        self.writelock = False
        if self.qid.type & py9p.QTDIR:
            self.mode = py9p.DMDIR | DEFAULT_DIR_MODE
        else:
            self.mode = DEFAULT_FILE_MODE
            self.data = StringIO()

    def checkout(self):
        return self

    @property
    def length(self):
        if self.qid.type & py9p.QTDIR:
            return len(self.children)
        else:
            p = self.data.tell()
            self.data.seek(0,os.SEEK_END)
            l = self.data.tell()
            self.data.seek(p,os.SEEK_SET)
            return l

class RootDir(Inode):
    def __init__(self):
        Inode.__init__(self,"/",qtype=py9p.QTDIR)

    def checkout(self):
        # create dir list:
        self.children = [ ProcessDir(x,self) for x in os.listdir("/proc") if re.match(r'^[0-9]+$',x) ]
        return self

class ProcessDir(Inode):
    def __init__(self,name,parent=None):
        Inode.__init__(self,name,qtype=py9p.QTDIR,parent=parent)
        self.taskstats = TaskstatsInode(pid=name,parent=self)
        self.children.append(self.taskstats)

class TaskstatsInode(Inode):
    def __init__(self,pid,parent=None):
        Inode.__init__(self,"taskstats",parent=parent)
        self.pid = pid

    def checkout(self):
        self.data = StringIO(taskstats.get(self.pid).sprint())

class Storage(object):
    """
    Low-level storage interface
    """
    def __init__(self):
        self.files = {}
        self.root = Inode("/",py9p.DMDIR)
        self.root.parent = self.root
        self.cwd = self.root
        self.files[self.root.qid.path] = self.root

    def create(self,name,mode=0,parent=None):
        if parent:
            self.cwd = parent
        new = Inode(name,mode,self.cwd)
        self.files[new.qid.path] = new
        self.cwd.children.append(new)
        return new.qid

    def chdir(self,target):
        if isinstance(target,py9p.Qid):
            self.cwd = self.files[target].checkout()

    def checkout(self,target):
        if not self.files.has_key(target):
            raise py9p.ServerError("file not found")
        return self.files[target].checkout()

    def commit(self,target):
        f = self.checkout(target)
        if f.writelock:
            f.writelock = False
            print f.path()

    def write(self,target,data,offset=0):
        f = self.checkout(target)

        f.writelock = True

        if f.qid.type & py9p.QTDIR:
            raise py9p.ServerError("Is a directory")

        f.data.seek(offset)
        f.data.write(data)
        return len(data)

    def read(self,target,size,offset=0):
        f = self.checkout(target)
        f.data.seek(offset)
        return f.data.read(size)

    def remove(self,target):
        f = self.checkout(target)
        for i in f.children:
            self.remove(i.qid.path)
        f.parent.children.remove(f)
        del self.files[target]

    def wstat(self,target,stat):

        f = self.checkout(target)

        # change uid?
        if stat.uidnum != 0xFFFFFFFF:
            f.uid = getpwuid(stat.uidnum).pw_name
        else:
            if stat.uid:
                f.uid = stat.uid
        # change gid?
        if stat.gidnum != 0xFFFFFFFF:
            f.gid = getgrgid(stat.gidnum).gr_name
        else:
            if stat.gid:
                f.gid = stat.gid
        # change mode?
        if stat.mode != 0xFFFFFFFF:
            f.mode = ((f.mode & 07777) ^ f.mode) | (stat.mode & 07777)
        # change name?
        if stat.name:
            f.name = stat.name


class v9fs(py9p.Server):
    """
    VFS 9p abstraction layer
    """

    def __init__(self, storage):
        self.mountpoint = '/'
        self.storage = storage
        self.root = self.storage.root

    def open(self, srv, req):
        '''If we have a file tree then simply check whether the Qid matches
        anything inside. respond qid and iounit are set by protocol'''
        f = self.storage.checkout(req.fid.qid.path)

        f.checkout()

        if (req.ifcall.mode & f.mode) != py9p.OREAD :
            raise py9p.ServerError("permission denied")

        srv.respond(req, None)

    def walk(self, srv, req):
        # root walks are handled inside the protocol if we have self.root
        # set, so don't do them here. '..' however is handled by us,
        # trivially

        f = self.storage.checkout(req.fid.qid.path)

        if len(req.ifcall.wname) > 1:
            srv.respond(req, "don't know how to handle multiple walks yet")
            return

        if req.ifcall.wname[0] == '..':
            req.ofcall.wqid.append(f.parent.qid)
            self.storage.chdir(f.parent.qid.path)
            srv.respond(req, None)
            return

        for x in f.children:
            if req.ifcall.wname[0] == x.name:
                req.ofcall.wqid.append(x.qid)
                self.storage.chdir(x.qid.path)
                srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    def stat(self, srv, req):
        req.ofcall.stat.append(self.storage.checkout(req.fid.qid.path))
        srv.respond(req, None)

    def read(self, srv, req):

        f = self.storage.checkout(req.fid.qid.path)

        if f.qid.type & py9p.QTDIR:
            req.ofcall.stat = []
            for x in f.children:
                req.ofcall.stat.append(x)
        else:
            req.ofcall.data = self.storage.read(f.qid.path,req.ifcall.count,req.ifcall.offset)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)


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
    storage = Storage()
    srv = py9p.Server(listen=(address, port), chatty=dbg, dotu=True)
    srv.mount(v9fs(storage))
    srv.serve()
