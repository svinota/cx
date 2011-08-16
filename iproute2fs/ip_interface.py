#!/usr/bin/env python

class interface(dict):
    def __init__(self,*argv,**kwargs):
        dict.__init__(self,*argv,**kwargs)
        self['addresses'] = []

    def create(self):
        pass

    def destroy(self):
        pass

    def up(self):
        pass

    def down(self):
        pass

