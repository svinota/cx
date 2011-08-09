
"""
9P protocol messages

http://man.cat-v.org/plan_9/5/intro
http://swtch.com/plan9port/man/man3/fcall.html
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


# ctypes types and functions
from ctypes import c_short, c_ushort, c_byte, c_ulong, c_uint32, c_uint16, c_ubyte, c_uint64, c_uint8
from ctypes import POINTER, sizeof, byref, cast
# 9P uses little-endian meta data
from ctypes import LittleEndianStructure as Structure, Union

from cxnet.utils import hprint, hline

"""
The maximum message size is 8192 bytes
"""
MAX_MSG_SIZE = 8192

class p9msgheaderobj (object):
    """
    Base class for the 9P message header
    """
    def __str__(self):
        "size: %s, type: %s, tag: %s\n" % (self.header.size, self.header.type, self.header.tag)

class p9msgheader (Structure, p9msgheaderobj):
    """
    Header of a 9P message
    """
    _fields_ = [
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]


class p9msgobj (p9msgheaderobj):
    """
    Base class for the 9P message
    """
    def __str__(self):
        ret = super(p9msgheaderobj, self).__str__()
        ret += hline(self, self.header.size)
        return ret

class p9msg (Structure, p9msgobj):
    """
    Raw 9P message
    """
    _fields_ = [
        ("header", p9msgheader),
        ("data", (c_ubyte * (MAX_MSG_SIZE - sizeof(p9msgheader)))),
    ]

    def msgclass (self):
        """
        Returns a class of the typed message object
        """
        return p9msgclasses[self.header.type]

    def narrow (self):
        """
        Returns a typed (narrowed) message object
        """
        return cast(byref(self), POINTER(self.msgclass())).contents
