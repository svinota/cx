#!/usr/bin/env python
"""
Extra light, simple and fast library to acquire interfaces and addresses
via RT Netlink protocol. It is simplified up to the edge to fit partial
requirements.

To get full version of the library, use master branch of the main git
repository at git://projects.radlinux.org/cx/
"""

from ctypes import CDLL, Structure, Union
from ctypes import string_at, create_string_buffer, sizeof, addressof, byref
from ctypes import c_byte, c_ubyte, c_ushort, c_int, c_uint8, c_uint16, c_uint32, c_uint64
from socket import AF_NETLINK, SOCK_RAW
from sys import maxint

__all__ = [ "nlconfig" ]

###
#
# There are two ways to work with a binary protocol. One is
# to use Python's socket objects and read/write strings, formatted
# in either way. This way is portable.
#
# The second is to use raw libc calls. This way isn't portable
# at all, but it is faster. Anyway, we're to get Linux' ip
# configuration data, so, there are no portability issues.
#
libc = CDLL("libc.so.6")

# The only netlink protocol we're to use
NETLINK_ROUTE = 0

##  RT Netlink multicast groups
RTNLGRP_NONE = 0x0
RTNLGRP_LINK = 0x1
RTNLGRP_IPV4_IFADDR = 0x10

## Types of RT Netlink messages
RTM_NEWLINK = 16
RTM_DELLINK = 17
RTM_GETLINK = 18
RTM_NEWADDR = 20
RTM_DELADDR = 21
RTM_GETADDR = 22

## Netlink message flags values
NLM_F_REQUEST            = 1    # It is request message.
NLM_F_MULTI              = 2    # Multipart message, terminated by NLMSG_DONE
NLM_F_ACK                = 4    # Reply with ack, with zero or error code
NLM_F_ECHO               = 8    # Echo this request
# Modifiers of GET request
NLM_F_ROOT               = 0x100    # specify tree    root
NLM_F_MATCH              = 0x200    # return all matching
NLM_F_ATOMIC             = 0x400    # atomic GET
NLM_F_DUMP               = (NLM_F_ROOT|NLM_F_MATCH)

## NL messages
NLMSG_NOOP               = 0x1    # Nothing
NLMSG_ERROR              = 0x2    # Error
NLMSG_DONE               = 0x3    # End of a dump
NLMSG_OVERRUN            = 0x4    # Data lost
NLMSG_MIN_TYPE           = 0x10    # < 0x10: reserved control messages
NLMSG_MAX_LEN = 0xffff

# Standard alignment function
NLMSG_ALIGNTO = 4
def NLMSG_ALIGN(l):
    return ( l + NLMSG_ALIGNTO - 1) & ~ (NLMSG_ALIGNTO - 1)


class sockaddr (Structure):
    """
    Sockaddr structure, see bind(2)
    """
    _fields_ = [
        ("family", c_ushort),
        ("pad",    c_ushort),
        ("pid",    c_uint32),
        ("groups", c_uint32),
    ]

class nlattr(Structure):
    """
    Netlink attribute header
    """
    _fields_ = [
        ("nla_len",     c_uint16),
        ("nla_type",    c_uint16),
    ]

class ifaddrmsg (Structure):
    """
    RT Netlink address message
    """
    _fields_ = [
        ("family",    c_ubyte),    # Address family
        ("prefixlen", c_ubyte),    # Address' prefix length
        ("flags",     c_ubyte),    # Address flags
        ("scope",     c_ubyte),    # Adress scope
        ("index",     c_int),      # Interface index
    ]

class ifinfmsg (Structure):
    """
    RT Netlink link message
    """
    _fields_ = [
        ("family",   c_ubyte),      # AF_UNSPEC (?)
        ("type",     c_uint16),     # Interface type
        ("index",    c_int),        # Interface index
        ("flags",    c_int),        # Interface flags (netdevice(7))
        ("change",   c_int),        # Change mask (reserved, always 0xFFFFFFFF)
    ]

class nlmsghdr (Structure):
    """
    Generic Netlink header
    """
    _fields_ = [
        ("length",             c_uint32),
        ("type",               c_uint16),
        ("flags",              c_uint16),
        ("sequence_number",    c_uint32),
        ("pid",                c_uint32),
    ]

class rtnl_payload (Union):
    """
    Unified RT Netlink payload
    """
    _fields_ = [
        ("link",     ifinfmsg),
        ("address",  ifaddrmsg),
        ("raw",      (c_byte * NLMSG_MAX_LEN)),
    ]

class rtnl_msg (Structure):
    """
    RT Netlink message
    """
    _fields_ = [
        ("hdr",      nlmsghdr),
        ("data",     rtnl_payload),
    ]

    offset = None

    def size(self):
        """
        Get size of the message
        """
        return self.offset - addressof(self)

    def setup(self,offset,direct={}):
        """
        Prepare self.offset. The method should be called
        before any attribute processing.
        """
        self.offset = offset

    def get_attr(self,type_map):

        assert self.offset < addressof(self) + self.hdr.length

        hdr = nlattr.from_address(self.offset)
        ptr = self.offset
        self.offset += NLMSG_ALIGN(hdr.nla_len)

        if type_map.has_key(hdr.nla_type):
            return (type_map[hdr.nla_type][1],type_map[hdr.nla_type][0](ptr))
        else:
            return None

def t_ip4ad(address):
    """
    Parse IPv4 address attribute
    """
    r = (c_uint8 * 4).from_address(address + sizeof(nlattr))
    return "%u.%u.%u.%u" % (r[0], r[1], r[2], r[3])
def t_l2ad(address):
    """
    Parse MAC address attribute
    """
    r = (c_uint8 * 6).from_address(address + sizeof(nlattr))
    return "%x:%x:%x:%x:%x:%x" % (r[0], r[1], r[2], r[3], r[4], r[5])
def t_asciiz(address):
    """
    Parse a zero-terminated string
    """
    return string_at(address + sizeof(nlattr))


## address attributes
IFA_LOCAL     = 2
IFA_LABEL     = 3

t_ifa_attr = {
            IFA_LOCAL:      (t_ip4ad,   "local"),
            IFA_LABEL:      (t_asciiz,  "dev"),
        }

## link attributes
IFLA_ADDRESS    = 1
IFLA_IFNAME     = 3

t_ifla_attr = {
            IFLA_ADDRESS:   (t_l2ad,        "hwaddr"),
            IFLA_IFNAME:    (t_asciiz,      "dev"),
        }


def nl_parse(msg):
    """
    Parse a RT Netlink message
    """
    r = {}
    t = msg.hdr.type

    direct = {}

    ## message type
    if \
        t <= RTM_DELLINK:
        r["type"] = "link"
        bias = ifinfmsg
        at = t_ifla_attr
    elif \
        t <= RTM_DELADDR:
        r["type"] = "address"
        r["mask"] = msg.data.address.prefixlen
        bias = ifaddrmsg
        at = t_ifa_attr
    else:
        r["type"] = "n/a"
        return r

    msg.setup(addressof(msg) + sizeof(nlmsghdr) + sizeof(bias))

    try:
        while True:
            ret = msg.get_attr(at)
            if ret is not None:
                r[ret[0]] = ret[1]
    except:
        pass

    return r


def nl_send(fd,msg,size=0):
    """
    Send a Netlink message
    """
    if not size:
        size = sizeof(msg)

    sa = sockaddr()
    sa.family = AF_NETLINK
    sa.pid = 0

    msg.hdr.length = size
    msg.hdr.pid = 0

    return libc.sendto(fd, byref(msg), size, 0, byref(sa), sizeof(sa))

def nl_recv(fd):
    """
    Receive a Netlink message
    """
    msg = rtnl_msg()
    l = libc.recvfrom(fd, byref(msg), sizeof(msg), 0, 0, 0)
    if l == -1:
        msg = None
    else:
        if (msg.hdr.type == NLMSG_NOOP):
            msg = None
    return (l,msg)

def nl_get(fd):
    """
    Get parsed message
    """
    result = []
    end = False
    while not end:
        bias = 0
        (l,msg) = nl_recv(fd)
        while bias < l:
            x = rtnl_msg.from_address(addressof(msg) + bias)
            bias += x.hdr.length
            parsed = nl_parse(x)
            if isinstance(parsed,dict):
                result.append(parsed)
            if not ((x.hdr.type > NLMSG_DONE) and (x.hdr.flags & NLM_F_MULTI)):
                end = True
                break
    return result

def nlconfig():
    """
    Extra light RT netlink client.
    For speed, it uses ctypes data representation instead of pack/unpack
    """

    ret = {}

    # create netlink socket, suitable to work with ctypes structures
    s = libc.socket(AF_NETLINK,SOCK_RAW,NETLINK_ROUTE)
    sa = sockaddr()
    sa.family = AF_NETLINK
    sa.pid = 0
    sa.groups = RTNLGRP_IPV4_IFADDR | RTNLGRP_LINK

    # subscribe only for addr and link events
    l = libc.bind(s, byref(sa), sizeof(sa))
    if l != 0:
        libc.close(s)
        raise Exception("libc.bind(): errcode %i" % (l))

    # prepare a request
    msg = rtnl_msg()
    msg.hdr.flags = NLM_F_DUMP | NLM_F_REQUEST


    # ask for all links
    msg.hdr.type = RTM_GETLINK
    nl_send(s,msg)

    # get only devices list, map them to a dictionary
    [ ret.__setitem__(x['dev'],x) for x in nl_get(s) if x.has_key('dev') ]
    # clean up
    [ (ret[x].__delitem__('dev'),ret[x].__delitem__('type')) for x in ret.keys() ]

    # ask for all addrs
    msg.hdr.type = RTM_GETADDR
    nl_send(s,msg)

    # map addrs to devices
    [ (ret[x['dev']].__setitem__("addr",x['local']),ret[x['dev']].__setitem__("netmask",x['mask'])) for x in nl_get(s) if x['type'] == 'address' ]
    return ret

if __name__ == "__main__":
    print nlconfig()
