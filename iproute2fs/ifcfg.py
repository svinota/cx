#!/usr/bin/env python

from __future__ import print_function
from cxnet.netlink.iproute2 import iproute2

links = iproute2.get_all_links()

print("%-16s%-16s%-16s%-16s\n" % ("name","type","state","wireless"))
[ print("%-16s%-16s%-16s%-16s" % (x["dev"],x["link_type"][7:],x["state"],x["wireless"])) for x in links ]
