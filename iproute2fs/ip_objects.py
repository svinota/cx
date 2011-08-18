#!/usr/bin/env python

from __future__ import print_function
from cxnet.netlink.iproute2 import iproute2
from ip_playback import sync
from ip_interface import interface
from time import sleep
from pprint import pprint

#
# startup: init objects
#

print("8<-------------------- init")
ifaces = dict([ (x['index'],interface(x)) for x in iproute2.get_all_links() ])
[ ifaces[x['index']]['addresses'].append(x) for x in iproute2.get_all_addrs() ]
print("8<-------------------- init results")
[ print(x) for x in ifaces.items() ]
#
# playback log records
#
print("8<-------------------- sleep")
sleep(20)
print("8<-------------------- log playback")
sync(ifaces)
print("8<-------------------- playback results")
pprint(ifaces)

#
# results
#
