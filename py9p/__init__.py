# coding=utf-8
# Copyright © 2008 Andrey Mirtchovski

__author__ = """Andrey Mirtchovski"""
__docformat__ = 'plaintext'

__all__ = []
for subpackage in [
    'proto',
    'server',
    'client',
    'authfs',
    ]:
    try:
        exec 'import ' + subpackage
        __all__.append( subpackage )
    except ImportError:
        pass

