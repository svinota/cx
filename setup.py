#!/usr/bin/env python

from distutils.core import setup

setup(name='9P',
    version='0.0.1',
    description='9P Protocol Implementation',
    author='Andrey Mirtchovski',
    author_email='aamirtch@ucalgary.ca',
    url='http://grid.ucalgary.ca',
    packages=['P9'],
    scripts=[
        'P9/srv.py',
        'P9/cl.py',
        ]
      
    )
