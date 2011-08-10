#!/usr/bin/env python

import pickle
import timeit

f = open("events","r")
events = pickle.load(f)
f.close()

#8<-----------------------------------
# hash-based parser

def link_up(event):
    pass

def link_down(event):
    pass

def addr_add(event):
    pass

def addr_del(event):
    pass

def default(event):
    pass

parser = {
    "link": {
        "add": link_up,
        "del": link_down,
        },
    "address": {
        "add": addr_add,
        "del": addr_del,
        },
    "neigh": {
        "add": default,
        "del": default,
        },
    "route": {
        "add": default,
        "del": default,
        },
    }

t = timeit.Timer('[ parser[x["type"]][x["action"]](x) for x in events ]','from __main__ import events,parser')
print t.timeit(100)

#8<-----------------------------------
# if-based parser

def parser(events):
    for event in events:
        if event['type'] == 'link':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'del':
                pass
        elif event['type'] == 'address':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'del':
                pass
        elif event['type'] == 'neigh':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'del':
                pass
        elif event['type'] == 'route':
            if event['action'] == 'add':
                pass
            elif event['action'] == 'del':
                pass

t = timeit.Timer('parser(events)','from __main__ import events,parser')
print t.timeit(100)
