
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
from ctypes import c_ubyte, c_char, c_uint16, c_uint32, c_uint64

# 9P uses little-endian meta data
from ctypes import LittleEndianStructure as Structure

# The maximum message size is 8192 bytes
MAX_MSG_SIZE = 8192
__all__ = ["MAX_MSG_SIZE"]

# Normal (default) message size: 4096 bytes -- one memory page.
NORM_MSG_SIZE = 4096
__all__ += ["NORM_MSG_SIZE"]

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

__all__ += ["p9msg"]

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

__all__ += ["p9msgstring"]

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
    
__all__ += ["p9msgarray"]

class p9qid (Structure):
    """
    The 9P qid type.

    The qid represents the server's unique identification for the file
    being accessed: two files on the same server hierarchy are the same
    if and only if their qids are the same.
    """
    _pack_ = 1
    _fields_ = [
        ("type", c_ubyte),
        ("version", c_uint32),
        ("path", c_uint64),
    ]

__all__ += ["p9qid"]


# Do not edit the following.
# The following code is generated automatically from the
# 9P manual pages and C header files.
# See the `templates' branch for details.

# The 9P version implemented
VERSION9P = "9P2000"


class Tcreate (Structure):
    """
    9P type 114 'create' request (transmit) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
    ]

    class tail (Structure):
        """
        The static tail of the outer message class.
        """
        _pack_ = 1
        _fields_ = [
            ("perm", c_uint32),
            ("mode", c_ubyte),
        ]

    def cdarclass (self, index = 0):
        """
        Returns the type of the message tail number ``index``:
          * name ```p9msgstring```;
          * ```self.tail```.
        """
        if index < 1:
            return p9msgstring
        if (index - 1) < 1:
            return self.tail
        raise IndexError("Array index out of bounds")

class Rcreate (Structure):
    """
    9P type 115 'create' reply (return) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _pack_ = 1
    _fields_ = [
        ("qid", p9qid),
        ("iounit", c_uint32),
    ]


class Tremove (Structure):
    """
    9P type 122 'remove' request (transmit) message class
    Remove - remove a file from a server
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
    ]

class Rremove (Structure):
    """
    9P type 123 'remove' reply (return) message class
    Remove - remove a file from a server
    """


class Tversion (Structure):
    """
    9P type 100 'version' request (transmit) message class
    Version - negotiate protocol version
    """
    _pack_ = 1
    _fields_ = [
        ("msize", c_uint32),
    ]

    def cdarclass (self):
        """
        Returns the type of the message tail ``version``
        """
        return p9msgstring

class Rversion (Structure):
    """
    9P type 101 'version' reply (return) message class
    Version - negotiate protocol version
    """
    _pack_ = 1
    _fields_ = [
        ("msize", c_uint32),
    ]

    def cdarclass (self):
        """
        Returns the type of the message tail ``version``
        """
        return p9msgstring


class Tstat (Structure):
    """
    9P type 124 'stat' request (transmit) message class
    Stat, wstat - inquire or change file attributes
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
    ]

class Rstat (Structure):
    """
    9P type 125 'stat' reply (return) message class
    Stat, wstat - inquire or change file attributes
    """
    _pack_ = 1
    _fields_ = [
        ("stat", p9msgarray),
    ]


class Tclunk (Structure):
    """
    9P type 120 'clunk' request (transmit) message class
    Clunk - forget about a fid
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
    ]

class Rclunk (Structure):
    """
    9P type 121 'clunk' reply (return) message class
    Clunk - forget about a fid
    """


class Tauth (Structure):
    """
    9P type 102 'auth' request (transmit) message class
    Attach, auth - messages to establish a connection
    """
    _pack_ = 1
    _fields_ = [
        ("afid", c_uint32),
    ]

    def cdarclass (self, index = 0):
        """
        Returns the type of the message tail number ``index``:
          * uname ```p9msgstring```;
          * aname ```p9msgstring```.
        """
        if index < 1:
            return p9msgstring
        if (index - 1) < 1:
            return p9msgstring
        raise IndexError("Array index out of bounds")

class Rauth (Structure):
    """
    9P type 103 'auth' reply (return) message class
    Attach, auth - messages to establish a connection
    """
    _pack_ = 1
    _fields_ = [
        ("aqid", p9qid),
    ]


class Topen (Structure):
    """
    9P type 112 'open' request (transmit) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
        ("mode", c_ubyte),
    ]

class Ropen (Structure):
    """
    9P type 113 'open' reply (return) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _pack_ = 1
    _fields_ = [
        ("qid", p9qid),
        ("iounit", c_uint32),
    ]


class Tflush (Structure):
    """
    9P type 108 'flush' request (transmit) message class
    Flush - abort a message
    """
    _pack_ = 1
    _fields_ = [
        ("oldtag", c_uint16),
    ]

class Rflush (Structure):
    """
    9P type 109 'flush' reply (return) message class
    Flush - abort a message
    """


class Tread (Structure):
    """
    9P type 116 'read' request (transmit) message class
    Read, write - transfer data from and to a file
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
        ("offset", c_uint64),
        ("count", c_uint32),
    ]

class Rread (Structure):
    """
    9P type 117 'read' reply (return) message class
    Read, write - transfer data from and to a file
    """
    _pack_ = 1
    _fields_ = [
        ("count", c_uint32),
    ]

    def cdarclass (self):
        """
        Returns the type of the message tail ``data``
        """
        return (c_ubyte * count)


class Terror (Structure):
    """
    9P type 106 'error' request (transmit) message class
    Error - return an error
    Comment: illegal 
    """

class Rerror (Structure):
    """
    9P type 107 'error' reply (return) message class
    Error - return an error
    """
    _pack_ = 1
    _fields_ = [
        ("ename", p9msgstring),
    ]


class Twalk (Structure):
    """
    9P type 110 'walk' request (transmit) message class
    Walk - descend a directory hierarchy
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
        ("newfid", c_uint32),
        ("nwname", c_uint16),
    ]

    def cdarclass (self, index = 0):
        """
        Returns the type of the message tail number ``index``:
          * wname ```p9msgstring``` * nwname.
        """
        if index < nwname:
            return p9msgstring
        raise IndexError("Array index out of bounds")

class Rwalk (Structure):
    """
    9P type 111 'walk' reply (return) message class
    Walk - descend a directory hierarchy
    """
    _pack_ = 1
    _fields_ = [
        ("nwqid", c_uint16),
    ]

    def cdarclass (self, index = 0):
        """
        Returns the type of the message tail number ``index``:
          * qid ```p9qid``` * nwqid.
        """
        if index < nwqid:
            return p9qid
        raise IndexError("Array index out of bounds")


class Tattach (Structure):
    """
    9P type 104 'attach' request (transmit) message class
    Attach, auth - messages to establish a connection
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
        ("afid", c_uint32),
    ]

    def cdarclass (self, index = 0):
        """
        Returns the type of the message tail number ``index``:
          * uname ```p9msgstring```;
          * aname ```p9msgstring```.
        """
        if index < 1:
            return p9msgstring
        if (index - 1) < 1:
            return p9msgstring
        raise IndexError("Array index out of bounds")

class Rattach (Structure):
    """
    9P type 105 'attach' reply (return) message class
    Attach, auth - messages to establish a connection
    """
    _pack_ = 1
    _fields_ = [
        ("qid", p9qid),
    ]


class Twstat (Structure):
    """
    9P type 126 'wstat' request (transmit) message class
    Stat, wstat - inquire or change file attributes
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
    ]

    def cdarclass (self):
        """
        Returns the type of the message tail ``stat``
        """
        return p9msgarray

class Rwstat (Structure):
    """
    9P type 127 'wstat' reply (return) message class
    Stat, wstat - inquire or change file attributes
    """


class Twrite (Structure):
    """
    9P type 118 'write' request (transmit) message class
    Read, write - transfer data from and to a file
    """
    _pack_ = 1
    _fields_ = [
        ("fid", c_uint32),
        ("offset", c_uint64),
        ("count", c_uint32),
    ]

    def cdarclass (self):
        """
        Returns the type of the message tail ``data``
        """
        return (c_ubyte * count)

class Rwrite (Structure):
    """
    9P type 119 'write' reply (return) message class
    Read, write - transfer data from and to a file
    """
    _pack_ = 1
    _fields_ = [
        ("count", c_uint32),
    ]

# The tuple of all defined message classes
p9msgclasses = tuple()
p9msgclasses += tuple([None]*100) # Types for 0..99 are not defined
p9msgclasses += tuple([Tversion, Rversion]) # 100, 101
p9msgclasses += tuple([Tauth, Rauth]) # 102, 103
p9msgclasses += tuple([Tattach, Rattach]) # 104, 105
p9msgclasses += tuple([Terror, Rerror]) # 106, 107
p9msgclasses += tuple([Tflush, Rflush]) # 108, 109
p9msgclasses += tuple([Twalk, Rwalk]) # 110, 111
p9msgclasses += tuple([Topen, Ropen]) # 112, 113
p9msgclasses += tuple([Tcreate, Rcreate]) # 114, 115
p9msgclasses += tuple([Tread, Rread]) # 116, 117
p9msgclasses += tuple([Twrite, Rwrite]) # 118, 119
p9msgclasses += tuple([Tclunk, Rclunk]) # 120, 121
p9msgclasses += tuple([Tremove, Rremove]) # 122, 123
p9msgclasses += tuple([Tstat, Rstat]) # 124, 125
p9msgclasses += tuple([Twstat, Rwstat]) # 126, 127
p9msgclasses += tuple([None]*128) # Types for 128..255 are not defined

# Export some constants
__all__ += ["VERSION9P"]
# Export all defined message types
__all__ += export_by_prefix("T",globals()) + export_by_prefix("R",globals())
