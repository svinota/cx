
from threading import Thread as _Thread
from threading import _Timer
from ctypes import CDLL,sizeof,c_ulong
from os import uname

libc = CDLL("libc.so.6")

###
#
# It is a real pain in the ass, to get real thread ID in Python
# So, we have only one choice: to use gettid(2) via ctypes
#
# But, another pain is that there is no glibc wrapper for gettid(2)!
# Damn it. Ok, using syscall(2).
#
# But not so fast. We're to know SYS_gettid (__NR_gettid). But it
# have different values on different systems.
#
# Be happy, if we'd make right choice. Or say your system bye-bye.
#

system = uname()[0]

if sizeof(c_ulong) == 4:
	SYS_gettid = 224
elif sizeof(c_ulong) == 8:
	SYS_gettid = 186


class Thread (_Thread):

	def getPid(self):
		return self.pid

	def __bootstrap(self):
		# patch for threading.Thread bootstrap
		# save thread ID
		#
		# this code is for Linux only and is not portable
		#
		try:
			self.pid = libc.syscall(SYS_gettid)
		except:
			pass

		# Wrapper around the real bootstrap code that ignores
		# exceptions during interpreter cleanup.  Those typically
		# happen when a daemon thread wakes up at an unfortunate
		# moment, finds the world around it destroyed, and raises some
		# random exception *** while trying to report the exception in
		# __bootstrap_inner() below ***.  Those random exceptions
		# don't help anybody, and they confuse users, so we suppress
		# them.  We suppress them only when it appears that the world
		# indeed has already been destroyed, so that exceptions in
		# __bootstrap_inner() during normal business hours are properly
		# reported.  Also, we only suppress them for daemonic threads;
		# if a non-daemonic encounters this, something else is wrong.
		try:
			self.__bootstrap_inner()
		except:
			if self.__daemonic and _sys is None:
				return
			raise

def Timer(*args, **kwargs):
    return X_Timer(*args, **kwargs)

class X_Timer (_Timer, Thread):
	pass
