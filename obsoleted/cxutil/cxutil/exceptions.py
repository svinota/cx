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

class Dump(Exception):
	'''
	Emit a signal to dump environment
	'''
	module = None

	def __init__(self,module=None):
		self.module = module

	def __str__(self):
		if self.module:
			return "debug dump for `%s`" % (self.module.fn)
		else:
			return "debug dump"

class CommitRaise(Exception):
	pass

class CallPass(CommitRaise):
	'''
	Emit a signal to pass this commit call
	'''
	pass

class CallQueue(CommitRaise):
	'''
	Emit a signal to queue this commit call
	'''
	pass

class BranchPass(CommitRaise):
	'''
	Emit a signal to mark this branch as executed and pass commit
	'''
	pass