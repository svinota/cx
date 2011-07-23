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
from ctypes import byref, sizeof, create_string_buffer
# ctypes simple types
from ctypes import c_short, c_ushort, c_byte, c_ulong, c_uint32, c_uint16, c_ubyte, c_uint64, c_uint8

from cxnet.utils import dqn_to_int, hprint, hline
from cxnet.common import libc
from socket import htons, htonl, ntohs, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

MAX_MSG_SIZE = 8192

__all__ = [ "p9socket" ]

class sockaddr_in (Structure):
    _pack_ = 2
    _fields_ = [
        ("sin_family", c_uint16),        # AF_INET etc...
        ("sin_port", c_uint16),          # port number
        ("sin_addr", c_uint32),          # ip address
        ("sin_zero", (c_uint8 * 8)),
    ]

class p9msg (Structure):
    """
    http://man.cat-v.org/plan_9/5/intro
    http://swtch.com/plan9port/man/man3/fcall.html
    """
    _fields_ = [
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("data", (c_ubyte * MAX_MSG_SIZE)),
    ]

    def __str__(self):
        ret = hline(self,self.size)
        ret += "size: %s, type: %s, tag: %s\n" % (self.size, self.type, self.tag)
        return ret

class p9socket (object):
    """
    9P core
    """
    fd = None    # socket file descriptor

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

    def close(self):
        """
        Close the socket
        """
        libc.close(self.fd)

    def dial(self,target):
        """
        Client connection
        """
        pass

    def serve(self):
        """
        9p server
        """
        libc.listen(self.fd,10)
        while True:
            sa = sockaddr_in()
            s = libc.accept(self.fd, byref(sa), byref(c_uint32(sizeof(sa))))
            (l,msg) = self.recv(s)
            print("got message of",l,"bytes")
            print(msg)
            libc.close(s)


    def recv(self,socket):
        """
        """
        msg = p9msg()
        l = libc.recv(socket, byref(msg), sizeof(msg), 0)

        return (l,msg)

    def send(self, msg, size=0):
        """
        """
        l = libc.send(self.fd, byref(msg), size, 0)
        return l

