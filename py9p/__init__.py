# coding=utf-8
# Copyright © 2008 Andrey Mirtchovski

from py9p import *

__author__ = """Andrey Mirtchovski"""
__docformat__ = 'plaintext'

__all__ = []
for subpackage in [
    'py9p',
    'py9psk1',
    ]:
    try:
        exec 'import ' + subpackage
        __all__.append( subpackage )
    except ImportError:
        pass

