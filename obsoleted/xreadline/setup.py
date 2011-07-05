#!/usr/bin/env python

from distutils.core import setup
from distutils.extension import Extension

include_dirs = []
library_dirs = ['/usr/lib/termcap']
runtime_library_dirs = []
libraries = ['readline','ncursesw']
extra_objects = []

setup(
	name="xreadline",
	version="0.1",
	url="http://www.radlinux.org/connexion/",
	author="Peter V. Saveliev",
	author_email="peet@altlinux.org",
	license="GPL",

	ext_modules = [
	Extension(
		name='xreadline',
		sources=['readline.c'],
		include_dirs=include_dirs,
		library_dirs=library_dirs,
		runtime_library_dirs=runtime_library_dirs,
		libraries=libraries,
		extra_objects=extra_objects,
	)],
)
