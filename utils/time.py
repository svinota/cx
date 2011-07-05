#!/usr/bin/env python

from cxnet.netlink.iproute2 import iproute2
from ifconfig import ifconfig
from sys import argv
import timeit


if len(argv) < 2:
    tc = 100
else:
    tc = int(argv[1])

links = timeit.Timer("iproute2.cache = {}; a = iproute2.get_all_links()","from __main__ import iproute2")
addrs = timeit.Timer("iproute2.cache = {}; a = iproute2.get_all_addrs()","from __main__ import iproute2")
ifcfg = timeit.Timer("a = ifconfig()","from __main__ import ifconfig")

print "links timeit per %s cycles: %s" % (tc,links.timeit(tc))
print "addrs timeit per %s cycles: %s" % (tc,addrs.timeit(tc))
print "ifcfg timeit per %s cycles: %s" % (tc,ifcfg.timeit(tc))
