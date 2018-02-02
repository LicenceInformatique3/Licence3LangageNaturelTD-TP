#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_pwac.py is part of mwetoolkit
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
This module provides classes to manipulate files that are encoded in the
"pWaC" filetype, which is a useful input/output corpus textual format.

You should use the methods in package `filetype` instead.
"""






from . import _common as common
from ..base.candidate import Candidate
from ..base.sentence import Sentence
from ..base.word import Word
from .. import util

# XXX REMOVE THIS... IMPORTING ft_* is WRONG!
# (We probably have bugs where `libs.filetype` is not loaded
# when importing directly the children...
from .ft_conll import ConllParser, ConllPrinter

class PWaCInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for pWaC format."""
    description = "WaC parsed format"
    filetype_ext = "pWaC"

    entries = ["surface", "lemma", "pos", "*ID", "*HEAD", "*DEPREL"]

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("_", "${underscore}"),
            ("<", "${lt}"), (">", "${gt}"), (" ", "${space}"),
            ("#", "${hash}"), ("\t", "${tab}"), ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(PWaCChecker, PWaCParser, PWaCPrinter)


INFO = PWaCInfo()

class PWaCChecker(common.AbstractChecker):
    r"""Checks whether input is in pWaC format."""
    def matches_header(self, strict):
        # Check is always strict because tag <text id is mandatory
        return b"<text id" in self.fileobj.peek(1024)


class PWaCParser(ConllParser):
    r"""Instances of this class parse the pWaC format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["corpus"]

    def __init__(self, encoding='utf-8'):
        super(PWaCParser, self).__init__(encoding)

    def _parse_line(self, line, ctxinfo):
        if line == "":
            pass  # Ignore empty lines
        elif line[0] == "<" and line[-1] == ">":
            # We just ignore <text id>, <s> and </s>
            # `new_partial` will be called when seeing ID "1"
            pass
        else:
            super(PWaCParser, self)._parse_line(line, ctxinfo)


class PWaCPrinter(ConllPrinter):
    BETWEEN_SENTENCES = ""
    def before_file(self, fileobj, ctxinfo):
        self.add_string(ctxinfo, '<text id="mwetoolkit">\n')

    def after_file(self, fileobj, ctxinfo):
        self.add_string(ctxinfo, '</text>\n')

    def handle_sentence(self, sentence, ctxinfo):
        self.add_string(ctxinfo, '<s>\n')
        super(PWaCPrinter, self).handle_sentence(sentence, ctxinfo)
        self.add_string(ctxinfo, '</s>\n')

