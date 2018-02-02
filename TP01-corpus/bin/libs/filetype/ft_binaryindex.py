#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_binaryindex.py is part of mwetoolkit
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
This module provides classes to manipulate binary index files. It is actually
a wrapper that uses indexlib.

You should use the methods in package `filetype` instead.
"""








from . import _common as common
from . import util
import sys

class BinaryIndexInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for BinaryIndex files."""
    description = "The `.info` file for binary index created by index.py"
    filetype_ext = "BinaryIndex"

    def operations(self):
        # TODO import indexlib...  BinaryIndexPrinter
        return common.FiletypeOperations(BinaryIndexChecker, BinaryIndexParser, None)

INFO = BinaryIndexInfo()

class BinaryIndexChecker(common.AbstractChecker):
    r"""Checks whether input is in BinaryIndex format."""
    def check(self, ctxinfo):
        if self.fileobj.name == "<stdin>":
            ctxinfo.error("Cannot read BinaryIndex file from stdin")
        if not self.fileobj.name.endswith(".info"):
            ctxinfo.error("BinaryIndex file should have extension .info")
        super(BinaryIndexChecker, self).check(ctxinfo)

    def matches_header(self, strict):
        # Check is always strict because the absence of header means file is wrong
        return self.fileobj.peek(20).startswith(b"corpus_size int")


class BinaryIndexParser(common.AbstractParser):
    valid_categories = ["corpus"]

    def _parse_file(self):
        self.inputobj.category = "corpus"
        with common.ParsingContext(self):
            from .indexlib import Index
            assert self.inputobj.filepath.endswith(".info")
            index = Index(self.inputobj.filepath[:-len(".info")],
                    ctxinfo=self.latest_ctxinfo)
            index.load_main(self.latest_ctxinfo)
            for sentence in index.iterate_sentences(self.latest_ctxinfo):
                self.latest_ctxinfo = sentence.ctxinfo
                self.handler.handle_sentence(sentence, sentence.ctxinfo)
