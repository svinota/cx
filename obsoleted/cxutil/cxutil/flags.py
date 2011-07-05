"""
Module flags (see command.py)
"""

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

### DDB general
Empty = 0x0
					# bit No
# ... local node (do not distribute execution)
Local = 0x1				# 1
# ... weak node
Weak = 0x2				# 2
# ... parent node
Begin = 0x4				# 3
# ... node removal
Down = 0x8				# 4
# ... marked for update
Mark = 0x10				# 5
# ... marked as committed
Committed = 0x20			# 6

### CX specific
					# bit No
# ... takes addition system info
Esoteric = 0x8000			# 16
# ... runs immediately anyway
Immediate = 0x10000			# 17
# ... pass command execution
Bypass = 0x20000			# 18
# ... unique node
Unique = 0x40000			# 19
# ... hidden node
Hidden = 0x80000			# 20
# ... force subtree to be restarted
Force = 0x100000			# 21
# ... transparent node
Transparent = 0x200000			# 22
# ... internal node
Internal = 0x400000			# 23
# ... newborn flag
Newborn = 0x800000			# 24
# ... once ?
Once = 0x1000000			# 25
# ... transparent node for locals upload
LocalsTransparent = 0x2000000		# 26
# ... upoad variables
Upload = 0x4000000			# 27
# ... stop locals
StopLocals = 0x8000000			# 28
# ... satellite class, not for direct commands
Satellite = 0x10000000			# 29
# ... remote execution
Rexec = 0x20000000			# 30
# ... local execution
Lexec = 0x40000000			# 31