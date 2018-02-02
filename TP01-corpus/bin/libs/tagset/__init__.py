#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# tagset.py is part of mwetoolkit
#
# mwetoolkit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# mwetoolkit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mwetoolkit.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
"""
This module provides classes and methods for tagset manipulation.
"""






from .. import util
from . import _common as common



TAGSETS = []
NAME2TAGSET = {}

for tset_module in util.dynload_modules(__path__, "tset_", "libs.tagset"):
    try:
        tagset = tset_module.TAGSET
    except AttributeError:
        raise AttributeError("Module at `{}` has no attribute `TAGSET`" \
                .format(tset_module.__file__))
    else:
        TAGSETS.append(tagset)    
        NAME2TAGSET[tagset.tset_name] = tagset
