
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

# The maximum message size is 8192 bytes
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


# The 9P version implemented
VERSION9P = "9P2000"

class p9createmsgobj (p9msgobj):
    """
    9P 'create' message base class
    Open, create - prepare a fid for I/O on an existing or new file
    """

    def __init__ (self):
        pass

class Tcreate (Structure, p9createmsgobj):
    """
    9P type 114 'create' request (transmit) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("name", p9msgstr),
        ("perm", c_uint32),
        ("mode", c_ubyte),
    ]

    def __init__ (self):
        super(p9createmsgobj, self).__init__()

class Rcreate (Structure, p9createmsgobj):
    """
    9P type 115 'create' reply (return) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("qid", p9qid),
        ("iounit", c_uint32),
    ]

    def __init__ (self):
        super(p9createmsgobj, self).__init__()

class p9removemsgobj (p9msgobj):
    """
    9P 'remove' message base class
    Remove - remove a file from a server
    """

    def __init__ (self):
        pass

class Tremove (Structure, p9removemsgobj):
    """
    9P type 122 'remove' request (transmit) message class
    Remove - remove a file from a server
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
    ]

    def __init__ (self):
        super(p9removemsgobj, self).__init__()

class Rremove (Structure, p9removemsgobj):
    """
    9P type 123 'remove' reply (return) message class
    Remove - remove a file from a server
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]

    def __init__ (self):
        super(p9removemsgobj, self).__init__()

class p9versionmsgobj (p9msgobj):
    """
    9P 'version' message base class
    Version - negotiate protocol version
    """

    def __init__ (self):
        pass

class Tversion (Structure, p9versionmsgobj):
    """
    9P type 100 'version' request (transmit) message class
    Version - negotiate protocol version
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("msize", c_uint32),
        ("version", p9msgstr),
    ]

    def __init__ (self):
        super(p9versionmsgobj, self).__init__()

class Rversion (Structure, p9versionmsgobj):
    """
    9P type 101 'version' reply (return) message class
    Version - negotiate protocol version
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("msize", c_uint32),
        ("version", p9msgstr),
    ]

    def __init__ (self):
        super(p9versionmsgobj, self).__init__()

class p9statmsgobj (p9msgobj):
    """
    9P 'stat' message base class
    Stat, wstat - inquire or change file attributes
    """

    def __init__ (self):
        pass

class Tstat (Structure, p9statmsgobj):
    """
    9P type 124 'stat' request (transmit) message class
    Stat, wstat - inquire or change file attributes
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
    ]

    def __init__ (self):
        super(p9statmsgobj, self).__init__()

class Rstat (Structure, p9statmsgobj):
    """
    9P type 125 'stat' reply (return) message class
    Stat, wstat - inquire or change file attributes
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("stat", p9msgarray16),
    ]

    def __init__ (self):
        super(p9statmsgobj, self).__init__()
        stat = p9msgarray16(c_ubyte)

class p9clunkmsgobj (p9msgobj):
    """
    9P 'clunk' message base class
    Clunk - forget about a fid
    """

    def __init__ (self):
        pass

class Tclunk (Structure, p9clunkmsgobj):
    """
    9P type 120 'clunk' request (transmit) message class
    Clunk - forget about a fid
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
    ]

    def __init__ (self):
        super(p9clunkmsgobj, self).__init__()

class Rclunk (Structure, p9clunkmsgobj):
    """
    9P type 121 'clunk' reply (return) message class
    Clunk - forget about a fid
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]

    def __init__ (self):
        super(p9clunkmsgobj, self).__init__()

class p9authmsgobj (p9msgobj):
    """
    9P 'auth' message base class
    Attach, auth - messages to establish a connection
    """

    def __init__ (self):
        pass

class Tauth (Structure, p9authmsgobj):
    """
    9P type 102 'auth' request (transmit) message class
    Attach, auth - messages to establish a connection
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("afid", c_uint32),
        ("uname", p9msgstr),
        ("aname", p9msgstr),
    ]

    def __init__ (self):
        super(p9authmsgobj, self).__init__()

class Rauth (Structure, p9authmsgobj):
    """
    9P type 103 'auth' reply (return) message class
    Attach, auth - messages to establish a connection
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("aqid", p9qid),
    ]

    def __init__ (self):
        super(p9authmsgobj, self).__init__()

class p9openmsgobj (p9msgobj):
    """
    9P 'open' message base class
    Open, create - prepare a fid for I/O on an existing or new file
    """

    def __init__ (self):
        pass

class Topen (Structure, p9openmsgobj):
    """
    9P type 112 'open' request (transmit) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("mode", c_ubyte),
    ]

    def __init__ (self):
        super(p9openmsgobj, self).__init__()

class Ropen (Structure, p9openmsgobj):
    """
    9P type 113 'open' reply (return) message class
    Open, create - prepare a fid for I/O on an existing or new file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("qid", p9qid),
        ("iounit", c_uint32),
    ]

    def __init__ (self):
        super(p9openmsgobj, self).__init__()

class p9flushmsgobj (p9msgobj):
    """
    9P 'flush' message base class
    Flush - abort a message
    """

    def __init__ (self):
        pass

class Tflush (Structure, p9flushmsgobj):
    """
    9P type 108 'flush' request (transmit) message class
    Flush - abort a message
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("oldtag", c_uint16),
    ]

    def __init__ (self):
        super(p9flushmsgobj, self).__init__()

class Rflush (Structure, p9flushmsgobj):
    """
    9P type 109 'flush' reply (return) message class
    Flush - abort a message
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]

    def __init__ (self):
        super(p9flushmsgobj, self).__init__()

class p9readmsgobj (p9msgobj):
    """
    9P 'read' message base class
    Read, write - transfer data from and to a file
    """

    def __init__ (self):
        pass

class Tread (Structure, p9readmsgobj):
    """
    9P type 116 'read' request (transmit) message class
    Read, write - transfer data from and to a file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("offset", c_uint64),
        ("count", c_uint32),
    ]

    def __init__ (self):
        super(p9readmsgobj, self).__init__()

class Rread (Structure, p9readmsgobj):
    """
    9P type 117 'read' reply (return) message class
    Read, write - transfer data from and to a file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("data", p9msgarray32),
    ]

    def __init__ (self):
        super(p9readmsgobj, self).__init__()
        data = p9msgarray32(c_ubyte)

class p9errormsgobj (p9msgobj):
    """
    9P 'error' message base class
    Error - return an error
    """

    def __init__ (self):
        pass

class Terror (Structure, p9errormsgobj):
    """
    9P type 106 'error' request (transmit) message class
    Error - return an error
    Comment: illegal 
    """
    _fields_ = [
        ("header", p9msgheader),
    ]

    def __init__ (self):
        super(p9errormsgobj, self).__init__()

class Rerror (Structure, p9errormsgobj):
    """
    9P type 107 'error' reply (return) message class
    Error - return an error
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("ename", p9msgstr),
    ]

    def __init__ (self):
        super(p9errormsgobj, self).__init__()

class p9walkmsgobj (p9msgobj):
    """
    9P 'walk' message base class
    Walk - descend a directory hierarchy
    """

    def __init__ (self):
        pass

class Twalk (Structure, p9walkmsgobj):
    """
    9P type 110 'walk' request (transmit) message class
    Walk - descend a directory hierarchy
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("newfid", c_uint32),
        ("wname", p9msgarray16),
    ]

    def __init__ (self):
        super(p9walkmsgobj, self).__init__()
        wname = p9msgarray16(p9msgstr)

class Rwalk (Structure, p9walkmsgobj):
    """
    9P type 111 'walk' reply (return) message class
    Walk - descend a directory hierarchy
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("qid", p9msgarray16),
    ]

    def __init__ (self):
        super(p9walkmsgobj, self).__init__()
        qid = p9msgarray16(p9qid)

class p9attachmsgobj (p9msgobj):
    """
    9P 'attach' message base class
    Attach, auth - messages to establish a connection
    """

    def __init__ (self):
        pass

class Tattach (Structure, p9attachmsgobj):
    """
    9P type 104 'attach' request (transmit) message class
    Attach, auth - messages to establish a connection
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("afid", c_uint32),
        ("uname", p9msgstr),
        ("aname", p9msgstr),
    ]

    def __init__ (self):
        super(p9attachmsgobj, self).__init__()

class Rattach (Structure, p9attachmsgobj):
    """
    9P type 105 'attach' reply (return) message class
    Attach, auth - messages to establish a connection
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("qid", p9qid),
    ]

    def __init__ (self):
        super(p9attachmsgobj, self).__init__()

class p9wstatmsgobj (p9msgobj):
    """
    9P 'wstat' message base class
    Stat, wstat - inquire or change file attributes
    """

    def __init__ (self):
        pass

class Twstat (Structure, p9wstatmsgobj):
    """
    9P type 126 'wstat' request (transmit) message class
    Stat, wstat - inquire or change file attributes
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("stat", p9msgarray16),
    ]

    def __init__ (self):
        super(p9wstatmsgobj, self).__init__()
        stat = p9msgarray16(c_ubyte)

class Rwstat (Structure, p9wstatmsgobj):
    """
    9P type 127 'wstat' reply (return) message class
    Stat, wstat - inquire or change file attributes
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
    ]

    def __init__ (self):
        super(p9wstatmsgobj, self).__init__()

class p9writemsgobj (p9msgobj):
    """
    9P 'write' message base class
    Read, write - transfer data from and to a file
    """

    def __init__ (self):
        pass

class Twrite (Structure, p9writemsgobj):
    """
    9P type 118 'write' request (transmit) message class
    Read, write - transfer data from and to a file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("fid", c_uint32),
        ("offset", c_uint64),
        ("data", p9msgarray32),
    ]

    def __init__ (self):
        super(p9writemsgobj, self).__init__()
        data = p9msgarray32(c_ubyte)

class Rwrite (Structure, p9writemsgobj):
    """
    9P type 119 'write' reply (return) message class
    Read, write - transfer data from and to a file
    """
    _fields_ = [
        ("header", p9msgheader),
        ("size", c_uint32),
        ("type", c_ubyte),
        ("tag", c_uint16),
        ("count", c_uint32),
    ]

    def __init__ (self):
        super(p9writemsgobj, self).__init__()

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
# Export the generic message class
__all__ += ["p9msg"]
# Export all defined message types
__all__ += export_by_prefix("T",globals()) + export_by_prefix("R",globals())
