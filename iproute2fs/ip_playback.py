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
                ifaces['by-name'][event['dev']] = ifaces[event['index']] = interface(event)
            else:
                print("already exists, skippin'")
        def remove(event,ifaces):
            print("remove interface %s" % (event['dev']))
            del ifaces[event['index']]
            del ifaces['by-name'][event['dev']]

    @vars
    class address:
        def add(event,ifaces):
            if event.has_key('local'):
                key = '%s/%s' % (event['local'],event['mask'])
            else:
                key = '%s/%s' % (event['address'],event['mask'])
            print("add address %s" % (key))
            ifaces[event['index']]['addresses'][key] = event
        def remove(event,ifaces):
            if event.has_key('local'):
                key = '%s/%s' % (event['local'],event['mask'])
            else:
                key = '%s/%s' % (event['address'],event['mask'])
            print("remove address %s" % (key))
            del ifaces[event['index']]['addresses'][key]

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

def sync(ifaces,blocking=False):
    while True:
        events = iproute2.get(0,blocking)
        if len(events) == 0:
            break
        for event in events:
            sync_map[event['type']][event['action']](event,ifaces)
