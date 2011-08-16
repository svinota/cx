#!/usr/bin/env python

from __future__ import print_function
from cxnet.netlink.iproute2 import iproute2
from ip_interface import interface

def playback(ifaces):
    while True:
        events = iproute2.get(blocking=False)
        if len(events) == 0:
            break
        for event in events:
            if event['type'] == 'link':
                if event['action'] == 'del':
                    print("remove interface %s" % (event['dev']))
                    del ifaces[event['index']]
                elif event['action'] == 'add':
                    print("add interface %s" % (event['dev']))
                    if not ifaces.has_key(event['index']):
                        ifaces[event['index']] = interface(event)
                    else:
                        print("already exists, skippin'")
            elif event['type'] == 'address':
                if event['action'] == 'del':
                    print("remove address %s" % (event['local']))
                    [ ifaces[event['index']]['addresses'].remove(x) for x in ifaces[event['index']]['addresses']
                        if
                            dict([ (y,z) for (y,z) in x.items() if y != 'timestamp' ]) ==
                            dict([ (y,z) for (y,z) in event.items() if y != 'timestamp' ])
                    ]
                elif event['action'] == 'add':
                    print("add address %s" % (event['local']))
                    ifaces[event['index']]['addresses'].append(event)

