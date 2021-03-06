#!/usr/bin/env python
#
#     Copyright (c) 2011 Red Hat, Inc; ALT Linux Team; Peter V. Saveliev
#
#     This file was written for VDSM project and uses code from Connexion
#     library.
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
#
"""
Extra light, simple and fast library to acquire interfaces and addresses
via RT Netlink protocol. It is simplified up to the edge to fit partial
requirements. Also, it has all the limitations that ifconfig does --
due to output data format restrictions.

To get full version of the library, use master branch of the main git
repository at git://projects.radlinux.org/cx/ (cxnet.netlink.iproute2)

This module exports only one routine, nlconfig(), which takes no
parameters. The routine opens a Netlink socket for NETLINK_ROUTE family,
dumps links and interfaces data and builds a dictionary in the format:

{
    "<iface[:alias]>": {
        "hwaddr": "xx:xx:xx:xx:xx:xx",
        "addr": "xxx.xxx.xxx.xxx",
        "netmask": "xxx.xxx.xxx.xxx"
    },
    ...
}

Please note that there can be only one Netlink socket opened for each
Netlink family by a process at one time. So, in multithreading
environment nlconfig() calls must be protected by mutexes or any
other synchronization primitives.

Limitations:

 * IPv4 only (for this version)
 * returns only one address for an interface - format restriction
 * returns netmask in dotted quad notation - format restriction

"""


from ctypes import CDLL, Structure, Union
from ctypes import string_at, sizeof, addressof, byref
from ctypes import c_byte, c_ubyte, c_ushort, c_int, c_uint8, c_uint16, c_uint32
from socket import AF_NETLINK, SOCK_RAW
from copy import copy

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
    return "%02x:%02x:%02x:%02x:%02x:%02x" % (r[0], r[1], r[2], r[3], r[4], r[5])
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

    ## message type
    if \
        t <= RTM_DELLINK:
        r["type"] = "link"
        r["hwaddr"] = ""
        bias = ifinfmsg
        at = t_ifla_attr
    elif \
        t <= RTM_DELADDR:
        r["type"] = "address"
        if msg.data.address.prefixlen > 32:
            # only IPv4 addresses! (by the matter of fact, IPv6 are also returned
            # despite of IPv4 only group subscription)
            return None
        m = ( 0xffffffff << ( 32 - msg.data.address.prefixlen ) ) & 0xffffffff
        r["mask"] = "%i.%i.%i.%i" % tuple(reversed([ (m >> (8*x)) & 0xff for x in range(4) ]))
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

    links and interfaces data

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
    [ (
        # remove internal info
        ret[x].__delitem__('dev'),
        ret[x].__delitem__('type'),
        # add empty netmask and addr, as it does ifconfig routine
        ret[x].__setitem__('netmask',''),
        ret[x].__setitem__('addr','')
      ) for x in ret.keys() ]
    # fix hwaddr for loopback: the original ifconfig returns an empty string
    if ret.has_key("lo"):
        ret["lo"]["hwaddr"] = ""

    # ask for all addrs
    msg.hdr.type = RTM_GETADDR
    nl_send(s,msg)

    # get addrs
    result = nl_get(s)
    # emulate "alias interfaces" *)
    [ ret.__setitem__(x,copy(ret[x[:x.find(":")]])) for x in
        [ y["dev"] for y in result if y.has_key("dev")] if x.find(":") > -1 ]
    # put addresses by interfaces (and aliases)
    [ (
        # use a label to identify an interface
        #
        # strictly speaking, it is not correct, we should use interface
        # indexes, but here we emulate ifconfig...
        ret[x['dev']].__setitem__("addr",x['local']),
        ret[x['dev']].__setitem__("netmask",x['mask'])
      ) for x in
        # fetch only the first address for an interface (or alias), just as
        # ifconfig does. All secondary addresses in this case are ignored.
        result if x['type'] == 'address' and ret[x['dev']]['addr'] == ""
        ]

    #
    # *) actually, "alias interfaces" model is deprecated
    # in the Linux kernel together with ifconfig and ioctl()
    # usage for network configuration
    #

    libc.close(s)
    return ret

if __name__ == "__main__":
    print nlconfig()
