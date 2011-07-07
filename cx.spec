%define pprefix python-module

Name: connexion
Version: 0.7.1
Release: alt4
Summary: Python framework to build network-centric systems
License: GPLv3
Group: Development/Python
URL: http://projects.radlinux.org/cx/

BuildArch: noarch
BuildPreReq: python-devel rpm-build-python

Requires: %{pprefix}-cxnet = %version-%release
Requires: %{pprefix}-py9p  = %version-%release

Source: %name-%version.tar

%description
As for version 0.7.0, Connexion project is a set of libraries
intended to build network-centric systems. It includes implementations
of several transport and application layer protocols.

This is a meta-package, that install all related packages.

%package -n %{pprefix}-cxnet
Summary: Network protocol implementations for Connexion project
Group: Development/Python
License: GPLv3
BuildArch: noarch

%description -n %{pprefix}-cxnet
Network protocol implementations for Connexion project can be used
by any Python program. This package includes:

* mDNS client/server with DNSSEC extensions

Netlink family protocol implementations:

* Generic netlink
* RT netlink (limited)
* IPQ netlink
* Taskstats

Common definitions of packet structures (in ctypes):

* ARP
* Ethernet
* IPv4
* TCP

%package -n %{pprefix}-py9p
Summary: Pure Python implementation of 9P protocol (Plan9)
Group: Development/Python
License: MIT
BuildArch: noarch
URL: http://mirtchovski.com/p9/py9p

%description -n %{pprefix}-py9p
Protocol 9P is developed for Plan9 operating system from Bell Labs.
It is used for remote file access, and since files are key objects
in Plan9, 9P can be used also for composite file access, RPC etc.

%prep
%setup

%install
%makeinstall python=%{__python} root=%buildroot lib=%{python_sitelibdir}

%files

%files -n %{pprefix}-cxnet
%_bindir/cxkey
%{python_sitelibdir}/cxnet*

%files -n %{pprefix}-py9p
%{python_sitelibdir}/py9p*

%changelog
* Thu Jul  7 2011 Peter V. Saveliev <peet@altlinux.org> 0.7.1-alt4
- iproute2 can add and delete addresses on interfaces
- more attributes parsed by rtnl
- wireless interfaces detection (ioctl) in rtnl
- get/set attributes in attr_msg class
- new utility function (make_map) that creates two-way mappings of set of attributes

* Wed Jun 17 2011 Peter V. Saveliev <peet@altlinux.org> 0.7.1-alt3
- cxkey utility added
- named parameters for py9p.Dir
- zeroconf.py fixed and tested

* Sun May 29 2011 Peter V. Saveliev <peet@altlinux.org> 0.7.1-alt2
- Sisyphus build fixed.

* Sun May 29 2011 Peter V. Saveliev <peet@altlinux.org> 0.7.1-alt1
- RPM prepared.

* Wed Nov 25 2009 Eugeny A. Rostovtsev (REAL) <real at altlinux.org> 0.4.6-alt7.svn1392.1
- Rebuilt with python 2.6
