# -*- coding: utf-8 -*-

'''
Code disassemble functions
'''

# 	Copyright (c) 2008 Peter V. Saveliev
#
# 	This file is part of Connexion project.
#
# 	Connexion is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 3 of the License, or
# 	(at your option) any later version.
#
# 	Connexion is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with Connexion; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


from dis import opname, hasconst, HAVE_ARGUMENT, EXTENDED_ARG


def is2way(f):
	'''
	This function determines, whether a function «f» may
	return something other than None.
	'''
	name = f.func_name
	co = f.func_code
	code = co.co_code
	
	n = len(code)
	i = 0
	extended_arg = 0

	cc = False
	ret = False

	while i < n:
		c = code[i]
		op = ord(c)

		if opname[op] in ('RETURN_VALUE','YIELD_VALUE'):
			if cc is not None:
				ret = True

		i = i+1

		if op >= HAVE_ARGUMENT:
			oparg = ord(code[i]) + ord(code[i+1])*256 + extended_arg
			extended_arg = 0
			i = i+2
			if op == EXTENDED_ARG:
				extended_arg = oparg*65536L

			if op in hasconst:
				if co.co_consts[oparg] is None:
					cc = None


	return ret
