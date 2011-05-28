Name: connexion
Version: 0.7.1
Release: alt1
Summary: Python framework to build network-centric systems
License: GPLv3
Group: Development/Python
URL: http://projects.radlinux.org/cx/
BuildArch: noarch

Source: %name-%version.tar

%description
As for version 0.7.0, Connexion project is a set of libraries
intended to build network-centric systems. It includes implementations
of several transport and application layer protocols.

%package network
Summary: Network protocol implementations for Connexion project
Group: Development/Python
BuildArch: noarch

%description network
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

%prep
%setup

%build
%make_build python=%{__python}

%install
rm -rf $RPM_BUILD_ROOT
%make_install python=%{__python}

%files

%files network
%{python_sitelibdir}/cxnet*

%changelog
* Sun May 29 2011 Peter V. Saveliev <peet@altlinux.org> 0.7.1-alt1
- RPM prepared.
