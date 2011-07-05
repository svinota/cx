#!/usr/bin/env python

from cxnet.netlink.iproute2 import iproute2
from sys import argv
import timeit


if len(argv) < 2:
    tc = 100
else:
    tc = int(argv[1])

links = timeit.Timer("a = iproute2.get_all_links()","from __main__ import iproute2")
addrs = timeit.Timer("a = iproute2.get_all_addrs()","from __main__ import iproute2")

print "links timeit per %s cycles: %s" % (tc,links.timeit(tc))
print "addrs timeit per %s cycles: %s" % (tc,addrs.timeit(tc))
