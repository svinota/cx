#!/usr/bin/env python

import pickle
import timeit

f = open("events","r")
events = pickle.load(f)

[ x.__setitem__("action","remove") for x in events if x["action"] == "del" ]

f.close()

#8<-----------------------------------
# hash-based parser, two levels

def link_up(event):
    pass

def link_down(event):
    pass

def addr_add(event):
    pass

def addr_remove(event):
    pass

def default(event):
    pass

parser = {
    "link": {
        "add": link_up,
        "remove": link_down,
        },
    "address": {
        "add": addr_add,
        "remove": addr_remove,
        },
    "neigh": {
        "add": default,
        "remove": default,
        },
    "route": {
        "add": default,
        "remove": default,
        },
    }

t = timeit.Timer('[ parser[x["type"]][x["action"]](x) for x in events ]','from __main__ import events,parser')
print "hash-based parser, two levels", t.timeit(100)

#8<-----------------------------------
# hash-based parser, one level

def link_up(event):
    pass

def link_down(event):
    pass

def addr_add(event):
    pass

def addr_remove(event):
    pass

def default(event):
    pass

parser = {
    "link_add": link_up,
    "link_remove": link_down,
    "address_add": addr_add,
    "address_remove": addr_remove,
    "neigh_add": default,
    "neigh_remove": default,
    "route_add": default,
    "route_remove": default,
    }

t = timeit.Timer('[ parser["%s_%s" % (x["type"],x["action"])](x) for x in events ]','from __main__ import events,parser')
print "hash-based parser, one level", t.timeit(100)

#8<-----------------------------------
# @vars-based parser, two levels

@vars
class parser:
    @vars
    class link:
        def add(event):
            pass
        def remove(event):
            pass
    @vars
    class address:
        def add(event):
            pass
        def remove(event):
            pass
    @vars
    class neigh:
        def add(event):
            pass
        def remove(event):
            pass
    @vars
    class route:
        def add(event):
            pass
        def remove(event):
            pass

t = timeit.Timer('[ parser[x["type"]][x["action"]](x) for x in events ]','from __main__ import events,parser')
print "@vars-based parser, two levels",t.timeit(100)

#8<-----------------------------------
# @vars-based parser

@vars
class parser:
    def link_add(event):
        pass
    def link_remove(event):
        pass
    def address_add(event):
        pass
    def address_remove(event):
        pass
    def neigh_add(event):
        pass
    def neigh_remove(event):
        pass
    def route_add(event):
        pass
    def route_remove(event):
        pass

t = timeit.Timer('[ parser["%s_%s" % (x["type"],x["action"])](x) for x in events ]','from __main__ import events,parser')
print "@vars-based parser",t.timeit(100)

#8<-----------------------------------
# if-based parser

def parser(events):
    for event in events:
        if event['type'] == 'link':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'remove':
                pass
        elif event['type'] == 'address':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'remove':
                pass
        elif event['type'] == 'neigh':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'remove':
                pass
        elif event['type'] == 'route':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'remove':
                pass

t = timeit.Timer('parser(events)','from __main__ import events,parser')
print "if-based parser",t.timeit(100)
