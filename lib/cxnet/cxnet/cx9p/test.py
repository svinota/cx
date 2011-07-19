#!/usr/bin/env python

from cxnet.cx9p.core import p9socket
from time import sleep

s = p9socket('127.0.0.1',10002)
s.serve()
sleep(600)
s.close()
