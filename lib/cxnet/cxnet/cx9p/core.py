"""
9P protocol implementation
"""

#     Copyright (c) 2011 Peter V. Saveliev
#     Copyright (c) 2011 Paul Wolneykien
#
#     This file is part of Connexion project.
#
#     Connexion is free software; you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation; either version 3 of the License, or
#     (at your option) any later version.
#
#     Connexion is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with Connexion; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from __future__ import print_function

# ctypes structures
from ctypes import Structure, Union
# ctypes functions
from ctypes import byref, sizeof, create_string_buffer, resize
# ctypes simple types
from ctypes import c_short, c_ushort, c_byte, c_ulong, c_uint32, c_uint16, c_ubyte, c_uint64, c_uint8

from cxnet.utils import dqn_to_int, hprint, hline
from cxnet.common import libc
from socket import htons, htonl, ntohs, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

from messages import *
from mempair import *

# Modules for asynchronous queue processing
import threading
import Queue

# Limit the size of the message queue
MAXWAITING = 1024

# The number of threads per queue
QTHREADS = 2

def basereply (tmsg, rtype = -1):
    """
    Returns the base mempair structure of the reply message for
    a given T-message mempair object
    """
    if rtype < 0:
        rtype = tmsg.car().type + 1
    msgdata = (c_ubyte * NORM_MSG_SIZE)()
    replymsg = mempair(p9msg, msgdata)
    replymsg.car().type = rtype
    replymsg.car().tag = tmsg.car().tag
    (baddr, bsize) = replymsg.carbuf()
    replymsg.car().size = bsize
    
    return replymsg

def errorreply (tmsg, emsg):
    """
    Returns the Rerror message mempair object with a given
    error message for a given T-message
    """
    replymsg = basereply(tmsg, 107)
    replymsg.car().size += sizeof(p9msgstring) + len(emsg)
    replymsg.cdr().car().len = len(emsg)
    replymsg.cdr().cdr().cdr().raw = emsg
    return replymsg


class p9socketworker(threading.Thread):
    """
    Processes the T-message queue running a thread
    """
    def __init__ (self, sock):
        self.__sock = sock
        threading.Thread.__init__(self)

    def getversion (self, verstr, msize):
        """
        Returns a tuple (sverstr, smsize), where ``sverstr`` is the
        9P version that is supported by this server equal or less than
        the version given in ``verstr`` parameter and ``smsize`` is the
        maximum message length that this server is ready to receive or
        send equal or less than the size given in ``msize``
        """

        if msize <= MAX_MSG_SIZE:
            rmsize = msize
        else:
            rmsize = MAX_MSG_SIZE
        return (VERSION9P, rmsize)

    def run (self):
        while True:
            (session, msg) = self.__sock.nextmsg()
            if msg is None:
                self.__sock.debug ("Worker finished")
                break # reached the end of the queue

            if self.__sock.closed:
                self.__sock.reply (errorreply (msg, "The server is closed"))
            
            if isinstance(msg.cdr().car(), Tversion):
                session.debug ("Requested 9P version: %s, maximum size: %i bytes" % (msg.cdr().cdr().cdr().car().raw, msg.cdr().car().msize))
                (rver, rmsize) = self.getversion(msg.cdr().cdr().cdr().car().raw,
                                                 msg.cdr().car().msize)
                session.msize = rmsize
                rmsg = basereply(msg)
                rmsg.cdr().car().msize = rmsize;
                rmsg.cdr().cdr().car().len = len(rver)
                rmsg.cdr().cdr().cdr().car().raw = rver
                session.debug ("Supported 9P version: %s, maximum size: %i bytes" % (rmsg.cdr().cdr().cdr().car().raw, rmsg.cdr().car().msize))
            else:
                session.debug ("An unknown case! Message type: %i" % msg.car().type)
                emsg = "Currently the message %s is not supported. Sorry!" % msg.cdr().car().__class__.__name__
                rmsg = errorreply(msg, emsg)
                session.debug (emsg)

            session.reply(rmsg)


__all__ = [ "p9socket" ]

class sockaddr_in (Structure):
    _pack_ = 2
    _fields_ = [
        ("sin_family", c_uint16),        # AF_INET etc...
        ("sin_port", c_uint16),          # port number
        ("sin_addr", c_uint32),          # ip address
        ("sin_zero", (c_uint8 * 8)),
    ]

class p9socket (object):
    """
    9P core
    """
    fd = None    # socket file descriptor

    # The message queue
    __msgq = Queue.Queue(MAXWAITING)

    __debug = True

    closed = True

    def __init__(self, address='0.0.0.0',port=10001):
        """
        Create and bind socket structure
        """
        self.fd = libc.socket(AF_INET,SOCK_STREAM,0)
        libc.setsockopt(self.fd, SOL_SOCKET, SO_REUSEADDR, byref(c_uint32(1)), sizeof(c_uint32))

        sa = sockaddr_in()
        sa.sin_family = AF_INET
        sa.sin_port = htons(port)
        sa.sin_addr = htonl(dqn_to_int(address))

        self.sa = sa

        l = libc.bind(self.fd, byref(sa), sizeof(sa))
        if l != 0:
            self.close()
            raise Exception("libc.bind(): errcode %i" % (l))

        for i in range(QTHREADS):
            p9socketworker(self).start()

    def close(self):
        """
        Close the socket
        """
        for i in range(QTHREADS):
            self.enqueue (None, None)
        self.debug ("Waiting for queue workers to finish...")
        self.__msgq.join()
        libc.close(self.fd)
        self.closed = True

    def dial(self,target):
        """
        Client connection
        """
        pass

    def enqueue (self, session, msg):
        """
        Enqueue the given reply message for later processing
        """
        self.__msgq.put((session, msg))

    def serve(self):
        """
        9p server
        """
        libc.listen(self.fd,10)
        self.closed = False
        while True:
            sa = sockaddr_in()
            try:
                s = libc.accept(self.fd, byref(sa), byref(c_uint32(sizeof(sa))))
                p9session(self, s).start()
            except:
                self.close()
                raise

    def recv(self,socket):
        """
        """
        msgdata = (c_ubyte * NORM_MSG_SIZE)()
        msg = mempair(p9msg, msgdata)
        (baddr, blen) = msg.buf()
        l = libc.recv(socket, baddr, blen, 0)
        hdr = msg.car()
        if l > sizeof(hdr):
            if hdr.size > l:
                if hdr.size > MAX_MSG_SIZE:
                    raise IOError ("The message is too large: %d bytes" % hdr.size)
                resize(msgdata, hdr.size)
                (baddr, blen) = msg.buf()
                l2 = libc.recv(socket, baddr + hdr.size - l, blen - l, 0)
                if l2 > 0:
                    l += l2
                else:
                    raise IOError ("Unable to read the %d remaining bytes" % blen - l)
        else:
            raise IOError ("Unable to read the message")

        return msg

    def send(self, msg):
        """
        """
        (baddr, blen) = msg.buf()
        l = libc.send(self.fd, baddr, blen, 0)
        return l

    def debug (self, dmsg):
        """
        Outputs the given debug message if in debug mode
        """
        if self.__debug:
            print (dmsg)

    def nextmsg (self):
        """
        Returns the next message from the queue
        """
        msg = None
        next = True
        while next:
            next = False
            (session, msg) = self.__msgq.get()
            if msg is None:
                self.__msgq.task_done()
            else:
                next = (session.closed or session.clearflushed(msg))
        return (session, msg)

    def reply (self, rmsg, task_done = True):
        """
        Send the given reply message and call task_done on the
        message queue
        """
        self.send(rmsg)
        if task_done:
            self.__msgq.task_done()


class p9session (threading.Thread):
    """
    Client-server connection via 9P
    """
    def __init__(self, p9sock, clsock, p9msize = MAX_MSG_SIZE):
        """
        Initializes the session object bound to the specified
        9P socket instance
        """
        self.__sock = p9sock
        self.__clsock = clsock
        self.msize = p9msize
        self.__lock = threading.Lock()
        self.__flushed = {}
        self.closed = False
        threading.Thread.__init__(self)

    def markflushed (self, oldtag):
        """
        Mark the given tag as flushed (aborted)
        """
        self.__lock.acquire()
        self.__flushed[oldtag] = True
        self.__lock.release()

    def isflushed (self, msg):
        """
        Indicates if the given message is flushed (aborted)
        """        
        return msg.car().tag in self.__flushed

    def clearflushed (self, arg):
        """
        Unmark the given message or tag from the set of
        flushed (aborted) messages/tags
        """
        if isinstance (arg, mempair):
            tag = arg.car().tag
        else:
            tag = arg
        self.__lock.acquire()
        if tag in self.__flushed:
            del self.__flushed[tag]
            ret = True
        else:
            ret = False
        self.__lock.release()
        return ret

    def run (self):
        """
        Receive and transmit messages
        """
        self.debug ("Start a new session")
        try:
            while not self.__sock.closed:
                try:
                    msg = self.__sock.recv(self.__clsock)
                except IOError:
                    break
                if isinstance(msg.cdr().car(), Tflush):
                    self.markflushed (msg.cdr().car().oldtag)
                    self.reply (basereply(msg), False)
                else:
                    self.__sock.enqueue (self, msg)
            libc.close(self.__clsock)
            self.closed = True
            self.debug ("The session is closed")
        except:
            libc.close(self.__clsock)
            self.closed = True
            self.debug ("The session is closed on an error")
            raise

    def nextmsg (self):
        """
        A proxy method to the parent socket ``nextmsg`` proc
        """
        return self.__sock.nextmsg()

    def debug (self, dmsg):
        """
        A proxy method to the parent socket ``debug`` proc
        """
        self.__sock.debug("[session] " + dmsg)

    def reply (self, rmsg, task_done = True):
        """
        A proxy method to the parent socket ``reply`` proc.
        The size of the given message is checked not to exceed
        the maximum message size, configured for this instance.
        According to the 9P spec, the maximum message size is
        specified by the client with the T-version request.
        If the message is longer than the client is ready to
        handle, then the Rerror message is sent and a
        ValueError is raised
        """
        if rmsg.car().size <= self.msize:
            self.__sock.reply (rmsg, task_done)
        else:
            emsg = errorreply (rmsg, "The reply message is too long")
            extra = emsg.car().size - self.msize
            if extra > emsg.cdr().car().len:
                extra = emsg.cdr().car().len
            if extra > 0:
                emsg.cdr().car().len -= extra
                emsg.car().size -= extra
            self.__sock.reply (emsg, task_done)
            raise ValueError ("The message is too long")
