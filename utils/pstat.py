#!/usr/bin/env python

from pstats import Stats
from sys import argv

s = Stats(argv[1])
s.sort_stats("time")
s.reverse_order()
s.print_stats()
