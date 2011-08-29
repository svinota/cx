
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
from ctypes import c_ubyte, c_char, c_uint16, c_uint32

# 9P uses little-endian meta data
from ctypes import LittleEndianStructure as Structure

# The maximum message size is 8192 bytes
MAX_MSG_SIZE = 8192
__all__ += ["MAX_MSG_SIZE"]

class p9msg (Structure):
    """
    A 9P message head.
    """
    _pack_ = 1
    _fields_ = [
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]
    
    def cdarclass (self):
        """
        Determines the message body class using the ``p9msgclasses``
        tuple.
        """
        if self.type > 0 and self.type < len(p9msgclasses):
            return p9msgclasses[self.type]
        else:
            raise ValueError("Unknown message type: %d" % (self.type))

class p9msgstring (Structure):
    """
    A 9P message string.
    """
    _pack_ = 1
    _fields_ = [
        ("len", c_uint16),
    ]
    
    def cdarclass (self):
        """
        Returns a character array type of the corresponding length.
        """
        return c_char * self.len

class p9msgarray (Structure):
    """
    A 9P message array.
    """
    _pack_ = 1
    _fields_ = [
        ("len", c_uint16),
    ]
    
    def cdarclass (self):
        """
        Returns a byte array type of the corresponding length.
        """
        return c_ubyte * self.len
