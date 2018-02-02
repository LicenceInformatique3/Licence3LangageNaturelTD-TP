#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# tset_frTreeTagger.py is part of mwetoolkit
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
the "frTreeTagger" (French TreeTagger) tagset.
"""


from . import _common as common


TAGSET = common.Tagset(
    tset_name="frTreeTagger",
    tset_description="French TreeTagger POS tags",

    content_tags=[
        "NOM",
        "ADJ",
        "VER:pres", "VER:pper", "VER:infi", "VER:subp", "VER:ppre",
                "VER:futu", "VER:impf", "VER:cond", "VER:subi",
                "VER:impe", "VER:simp",
        "ADV",
    ],

    sparse_content_tags=[
        "NUM", "NAM"
    ],
)


_EXAMPLE_TABLE = """
    NOM         noun                       table, tables
    ADJ         adjective                  majeur, pire
    VER:pres    verb, present tense        atteste
    VER:pper    verb, participle           perdu
    VER:infi    verb, infinitive           faire
    VER:subp    verb, subj present         fasse
    VER:ppre    verb, present participle   disant
    VER:futu    verb, future               seront
    VER:impf    verb, imparfait            venaient
    VER:cond    verb, conditionnel         semblerait
    VER:subi    verb, subj imparfait       agisse
    VER:impe    verb, imperative           gagnez
    VER:simp    verb, passé simple         chanta
    ADV         adverb                     très, pas

    NUM         number                     42
    NAM         proper noun                John, Vikings
"""
