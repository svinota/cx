#!/usr/bin/python

import socket
import sys

import ninep
import ninep/client

class Error(P9.Error) : pass

def modeStr(mode) :
	bits = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
	def b(s) :
		return bits[(mode>>s) & 7]
	d = "-"
	if mode & P9.DIR :
		d = "d"
	return "%s%s%s%s" % (d, b(6), b(3), b(0))

def _os(func, *args) :
	try :
		return func(*args)
	except OSError,e :
		raise Error(e.args[1])
	except IOError,e :
		raise Error(e.args[1])
	
class CmdClient(P9Client.Client) :
	"""command line driven access to the client"""
	def _cmdstat(self, args) :
		for a in args :
			self.stat(a)
	def _cmdls(self, args) :
		long = 0
		while len(args) > 0 :
			if args[0] == "-l" :
				long = 1
			else :
				print "usage: ls [-l]"
				return
			args[0:1] = []
		self.ls(long)
	def _cmdcd(self, args) :
		if len(args) != 1 :
			print "usage: cd path"
			return
		self.cd(args[0])
	def _cmdcat(self, args) :
		if len(args) != 1 :
			print "usage: cat path"
			return
		self.cat(args[0])
	def _cmdmkdir(self, args) :
		if len(args) != 1 :
			print "usage: mkdir path"
			return
		self.mkdir(args[0])
	def _cmdget(self, args) :
		if len(args) == 1 :
			f, = args
			f2 = f.split("/")[-1]
		elif len(args) == 2 :
			f,f2 = args
		else :
			print "usage: get path [localname]"
			return
		out = _os(file, f2, "wb")
		self.cat(f, out)
		out.close()
	def _cmdput(self, args) :
		if len(args) == 1 :
			f, = args
			f2 = f.split("/")[-1]
		elif len(args) == 2 :
			f,f2 = args
		else :
			print "usage: put path [remotename]"
			return
		if f == '-' :
			inf = sys.stdin
		else :
			inf = _os(file, f, "rb")
		self.put(f2, inf)
		if f != '-' :
			inf.close()
	def _cmdrm(self, args) :
		if len(args) == 1 :
			self.rm(args[0])
		else :
			print "usage: rm path"
	def _cmdhelp(self, args) :
		cmds = [x[4:] for x in dir(self) if x[:4] == "_cmd"]
		cmds.sort()
		print "Commands: ", " ".join(cmds)
	def _cmdquit(self, args) :
		self.done = 1
	_cmdexit = _cmdquit

	def _nextline(self) :		# generator is cleaner but not supported in 2.2
		if self.cmds is None :
			sys.stdout.write("9p> ")
			sys.stdout.flush()
			line = sys.stdin.readline()
			if line != "" :
				return line[:-1]
		else :
			if self.cmds :
				x,self.cmds = self.cmds[0],self.cmds[1:]
				return x
	def cmdLoop(self, cmds) :
		cmdf = {}
		for n in dir(self) :
			if n[:4] == "_cmd" :
				cmdf[n[4:]] = getattr(self, n)

		if not cmds :
			cmds = None
		self.cmds = cmds
		self.done = 0
		while 1 :
			line = self._nextline()
			if line is None :
				break
			args = filter(None, line.split(" "))
			if not args :
				continue
			cmd,args = args[0],args[1:]
			if cmd in cmdf :
				try :
					cmdf[cmd](args)
				except P9.Error,e :
					print "%s: %s" % (cmd, e.args[0])
			else :
				sys.stdout.write("%s ?\n" % cmd)
			if self.done :
				break

def usage(prog) :
	print "usage: %s [-d] [-a authsrv] [-n] [-p srvport] user srv [cmd ...]" % prog
	sys.exit(1)
	
def main(prog, *args) :
	import getopt
	import getpass

	authsrv = None
	port = P9.PORT
	try :
		opt,args = getopt.getopt(args, "a:dnp:")
	except :
		usage(prog)
	passwd = ""
	for opt,optarg in opt :
		if opt == '-a' :
			authsrv = optarg
		if opt == "-d" :
			import debug
		if opt == '-n' :
			passwd = None
		if opt == "-p" :
			port = int(optarg)		# XXX catch
	
	if len(args) < 2 :
		usage(prog)
	user = args[0]
	srv = args[1]
	if authsrv is None :
		authsrv = srv
	cmd = args[2:]

	sock = socket.socket(socket.AF_INET)
	try :
		sock.connect((srv, port),)
	except socket.error,e :
		print "%s: %s" % (srv, e.args[1])
		return

	if passwd is not None :
		passwd = getpass.getpass()
	try :
		cl = CmdClient(P9.Sock(sock), user, passwd, authsrv)
		cl.cmdLoop(cmd)
	except P9.Error,e :
		print e

if __name__ == "__main__" :
	try :
		main(*sys.argv)
	except KeyboardInterrupt :
		print "interrupted."

