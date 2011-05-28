# 	Copyright (c) 2011 Peter V. Saveliev
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

ifdef python
	override python := "python=${python}"
endif
ifdef root
	override root := "root=${root}"
endif
ifdef lib
	override lib := "lib=${lib}"
endif

build:
	@for i in `find .  -maxdepth 1 -mindepth 1 -type d ! -name '.*'`; do [ ! -e $$i/build-disabled ] && make -C $$i build ${root} ${lib} ${python} || echo "$$i disabled"; done
install:
	@for i in `find .  -maxdepth 1 -mindepth 1 -type d ! -name '.*'`; do [ ! -e $$i/build-disabled ] && make -C $$i install ${root} ${lib} ${python} || echo "$$i disabled"; done
clean:
	@for i in `find .  -maxdepth 1 -mindepth 1 -type d ! -name '.*'`; do [ ! -e $$i/build-disabled ] && make -C $$i clean ${root} ${lib} ${python} || echo "$$i disabled"; done
