#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# tset_ptb.py is part of mwetoolkit
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
the "ptb" (Penn Treebank) tagset.
"""


from . import _common as common


TAGSET = common.Tagset(
    tset_name="ptb",
    tset_description="Penn Treebank POS tags",

    content_tags=[
        "NN", "NNS",
        "JJ", "JJR", "JJS",
        "VV", "VVD", "VVG", "VVN", "VVP", "VVZ",
        "RB", "RBR", "RBS", "RP"
    ],

    sparse_content_tags=[
        "CD", "NP", "NPS"
    ],
)


_EXAMPLE_TABLE = """
    NN      noun, singular or mass           table
    NNS     noun plural                      tables
    JJ      adjective                        green
    JJR     adjective, comparative           greener
    JJS     adjective, superlative           greenest
    VV      verb, base form                  take
    VVD     verb, past tense                 took
    VVG     verb, gerund/present participle  taking
    VVN     verb, past participle            taken
    VVP     verb, sing. present, non-3d      take
    VVZ     verb, 3rd person sing. present   takes
    RB      adverb                           however, usually, naturally, here, good
    RBR     adverb, comparative              better
    RBS     adverb, superlative              best
    RP      particle                         give up

    CD      number                           42
    NP      proper noun, singular            John
    NPS     proper noun, plural              Vikings
"""
