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

from ctypes import CDLL, Structure
from ctypes import byref, sizeof
from ctypes import c_short, c_ushort, c_byte, c_ulong
from cxnet.utils import dqn_to_int
from cxnet.common import hprint
from socket import htons, htonl, AF_INET, SOCK_STREAM

__all__ = [ "p9socket" ]

libc = CDLL("libc.so.6")

class sockaddr_in (Structure):
    _pack_ = 2
    _fields_ = [
        ("sin_family", c_short),        # AF_INET etc...
        ("sin_port", c_ushort),         # port number
        ("sin_addr", c_ulong),          # ip address
        ("sin_zero", (c_byte * 8)),
    ]

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

        sa = sockaddr_in()
        sa.sin_family = AF_INET
        sa.sin_port = htons(port)
        sa.sin_addr = htonl(dqn_to_int(address))

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
            s = libc.accept(self.fd, byref(sa), sizeof(sa))
            print sa.sin_port
            print sa.sin_addr
            libc.close(s)


    def recv(self):
        """
        Receive a packet from Netlink socket (using recvfrom(2))
        """
        msg = self.msg()
        l = libc.recvfrom(self.fd, byref(msg), sizeof(msg), 0, 0, 0)

        if l == -1:
            msg = None
        else:
            if (msg.hdr.type == NLMSG_NOOP):
                msg = None
            elif (msg.hdr.type == NLMSG_ERROR):
                error = nlmsgerr.from_address(addressof(msg.data))
                raise Exception("Netlink error %i" % (error.code))

        return (l,msg)

    def send(self, msg, size=0):
        """
        Send a packet through Netlink socket
        """

        if not size:
            size = sizeof(msg)

        sa = sockaddr()
        sa.family = AF_NETLINK
        sa.pid = 0

        self.prepare(msg, size)

        l = libc.sendto(self.fd, byref(msg), size, 0, byref(sa), sizeof(sa))
        return l

    def prepare(self, msg, size=0):
        """
        Adjust message header fields before sending
        """

        if not size:
            size = sizeof(msg)

        msg.hdr.length = size
        msg.hdr.pid = getpid()
