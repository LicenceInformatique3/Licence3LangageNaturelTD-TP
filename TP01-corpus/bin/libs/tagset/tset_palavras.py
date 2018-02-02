#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# tset_palavras.py is part of mwetoolkit
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
This module provides an internal representation for
the "PALAVRAS" (PALAVRAS parser) tagset.
"""


from . import _common as common


class PalavrasTagset(common.Tagset):
    def reduced(self, pos_tag):
        return pos_tag.split(".")[0]


TAGSET = PalavrasTagset(
    tset_name="PALAVRAS",
    tset_description="PALAVRAS parser POS-tags",

    content_tags=[
        "N",
        "ADJ",
        "V",
        "ADV"
    ],

    sparse_content_tags=[
        "NUM", "PROP"
    ],
)


_EXAMPLE_TABLE = """
    N       noun              mesa
    ADJ     adjective         verde
    V       verb              andaremos
    ADV     adverb            rapidamente

    NUM     number            42
    PROP    proper noun       João, Estados Unidos
"""
