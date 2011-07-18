#!/usr/bin/env python
"""
An isolated code from http://git.fedorahosted.org/git/?p=vdsm.git;a=blob;f=vdsm/netinfo.py

For speed testing
"""

# Copyright 2009-2010 Red Hat, Inc. and/or its affiliates.
#
# Licensed to you under the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  See the files README and
# LICENSE_GPL_v2 which accompany this distribution.
#

import subprocess

def ifconfig():
     """ Partial parser to ifconfig output """

     p = subprocess.Popen(["/sbin/ifconfig", '-a'],
             close_fds=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
             stderr=subprocess.PIPE)
     out, err = p.communicate()
     ifaces = {}
     for ifaceblock in out.split('\n\n'):
         if not ifaceblock: continue
         addr = netmask = hwaddr = ''
         for line in ifaceblock.splitlines():
             if line[0] != ' ':
                 ls = line.split()
                 name = ls[0]
                 if ls[2] == 'encap:Ethernet' and ls[3] == 'HWaddr':
                     hwaddr = ls[4]
             if line.startswith('          inet addr:'):
                 sp = line.split()
                 for col in sp:
                     if ':' not in col: continue
                     k, v = col.split(':')
                     if k == 'addr':
                         addr = v
                     if k == 'Mask':
                         netmask = v
         ifaces[name] = {'addr': addr, 'netmask': netmask, 'hwaddr': hwaddr}
     return ifaces


from nlconfig import nlconfig

import timeit

i = timeit.Timer("ifconfig()","from __main__ import ifconfig")
n = timeit.Timer("nlconfig()","from __main__ import nlconfig")
print i.timeit(100)
print n.timeit(100)
print ifconfig()
print nlconfig()