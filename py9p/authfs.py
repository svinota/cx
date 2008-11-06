import py9p
import py9psrv
import py9psk1

class AuthFs(object) :
    """
    A special file for performing p9sk1 authentication.  On completion
    of the protocol, suid is set to the authenticated username.
    """
    type = ord('a')
    HaveProtos,HaveSinfo,HaveSauth,NeedProto,NeedCchal,NeedTicket,Success = range(7)
    cancreate = 0

    def __init__(self, user, dom, key) :
        self.sk1 = sk1.Marshal()
        self.user = user
        self.dom = dom
        self.ks = key

    def estab(self, f, isroot) :
        f.isdir = 0
        f.odev = self
        f.CHs = sk1.randChars(8)
        f.CHc = None
        f.suid = None
        f.treq = [sk1.AuthTreq, self.user, self.dom, f.CHs, '', '']
        f.phase = self.HaveProtos

    def _invalid(self, *args) :
        raise ServError("bad operation")

    walk = _invalid
    remove = _invalid
    create = _invalid
    open = _invalid

    def exists(self, f) :
        return 1
    def clunk(self, f) :
        pass

    def read(self, f, pos, len) :
        self.sk1.setBuf()
        if f.phase == self.HaveProtos :
            f.phase = self.NeedProto
            return "p9sk1@%s\0" % self.dom
        elif f.phase == self.HaveSinfo :
            f.phase = self.NeedTicket
            self.sk1._encTicketReq(f.treq)
            return self.sk1.getBuf()
        elif f.phase == self.HaveSauth :
            f.phase = self.Success
            self.sk1._encAuth([sk1.AuthAs, f.CHc, 0])
            return self.sk1.getBuf()
        raise ServError("unexpected phase")

    def write(self, f, pos, buf) :
        self.sk1.setBuf(buf)
        if f.phase == self.NeedProto :
            l = buf.index("\0")
            if l < 0 :
                raise ServError("missing terminator")
            s = buf.split(" ")
            if len(s) != 2 or s[0] != "p9sk1" or s[1] != self.dom + '\0' :
                raise ServError("bad protocol %r" % buf)
            f.phase = self.NeedCchal
            return l + 1
        elif f.phase == self.NeedCchal :
            f.CHc = self.sk1._decChal()
            f.phase = self.HaveSinfo
            return 8
        elif f.phase == self.NeedTicket :
            self.sk1.setKs(self.ks)
            num,chal,cuid,suid,key = self.sk1._decTicket()
            if num != sk1.AuthTs or chal != f.CHs :
                raise ServError("bad ticket")
            self.sk1.setKn(key)
            num,chal,id = self.sk1._decAuth()
            if num != sk1.AuthAc or chal != f.CHs or id != 0 :
                raise ServError("bad authentication for %s" % suid)
            f.suid = suid
            f.phase = self.HaveSauth
            return 72 + 13
        raise ServError("unexpected phase")


