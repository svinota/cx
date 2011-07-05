"""
Commit call mask (see state/core.py)
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

# ... empty mask
Empty = 0x0
# ... force execution
Force = 0x1
# ... pass execution
Bypass = 0x2
# ... `in-call` commit
Call = 0x4
# ... immediate call from state2.parse()
Immediate = 0x8
# ... script up
ScriptUp = 0x10
# ... script down
ScriptDown = 0x20
# ... signal
Signal = 0x40
# DB resync
Resync = 0x80
