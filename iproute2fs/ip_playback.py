#!/usr/bin/env python

from __future__ import print_function
from cxnet.netlink.iproute2 import iproute2
from ip_interface import interface

@vars
class sync_map:

    @vars
    class link:
        def add(event,ifaces):
            print("add interface %s" % (event['dev']))
            if not ifaces.has_key(event['index']):
                ifaces[event['index']] = interface(event)
            else:
                print("already exists, skippin'")
        def remove(event,ifaces):
            print("remove interface %s" % (event['dev']))
            del ifaces[event['index']]

    @vars
    class address:
        def add(event,ifaces):
            print("add address %s" % (event['local']))
            ifaces[event['index']]['addresses'].append(event)
        def remove(event,ifaces):
            print("remove address %s" % (event['local']))
            [ ifaces[event['index']]['addresses'].remove(x) for x in ifaces[event['index']]['addresses']
                if
                    dict([ (y,z) for (y,z) in x.items() if y not in ('timestamp','action') ]) ==
                    dict([ (y,z) for (y,z) in event.items() if y not in ('timestamp','action') ])
            ]

    @vars
    class neigh:
        def add(*argv):
            pass
        def remove(*argv):
            pass

    @vars
    class route:
        def add(*argv):
            pass
        def remove(*argv):
            pass

def sync(ifaces):
    while True:
        events = iproute2.get(blocking=False)
        if len(events) == 0:
            break
        for event in events:
            sync_map[event['type']][event['action']](event,ifaces)
