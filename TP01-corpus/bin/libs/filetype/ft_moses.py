#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_moses.py is part of mwetoolkit
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
"Moses" filetype, which is a useful input/output corpus textual format.

You should use the methods in package `filetype` instead.
"""






import itertools

from . import fmtutil
from . import _common as common
from ..base.sentence import SentenceFactory
from ..base.candidate import CandidateFactory
from ..base.word import Word
from .. import util


################################################################################

FMT = fmtutil.XWEFormatter("|", "_", " ",
        lambda w: (w.surface, w.lemma, w.pos, w.syn),
        xwe_inside_out=True)


class MosesInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for Moses."""
    description = "Moses factored format (word=f1|f2|f3|f4)"
    filetype_ext = "Moses"

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("|", "${pipe}"),
            ("#", "${hash}"), ("_", "${underscore}"), ("=", "${eq}"),
            (" ", "${space}"), ("\t", "${tab}"),
            ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(MosesChecker,
                MosesParser, MosesPrinter)

INFO = MosesInfo()

class MosesChecker(common.AbstractChecker):
    r"""Checks whether input is in Moses format."""
    def matches_header(self, strict):
        header = self.fileobj.peek(512)
        for line in header.split(b"\n"):
            if not line.startswith(util.utf8_unicode2bytes(
                    self.filetype_info.comment_prefix)):
                return all(w.count(b"|") == 3 for w in line.split(b" ") if w)
        return not strict


class MosesParser(common.AbstractTxtParser):
    r"""Instances of this class parse the Moses format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["corpus"]

    def __init__(self, encoding='utf-8'):
        super(MosesParser,self).__init__(encoding)
        self.sentence_factory = SentenceFactory()
        self.candidate_factory = CandidateFactory()
        self.category = "corpus"

    def _parse_line(self, line, ctxinfo):
        ENTRY_NAMES = ("surface", "lemma", "pos", "syn")
        s = self.sentence_factory.make()
        for i, words in enumerate(FMT.parse_xwes(ctxinfo, line)):
            for token in words:
                if len(token) == 4:
                    props = fmtutil.make_props(ENTRY_NAMES, token, self.unescape)
                    s.append(Word(ctxinfo, props))
                else:
                    ctxinfo.warn("Ignoring bad word token #{tokennum}", tokennum=i+1)

            if len(words) != 1:
                from ..base.mweoccur import MWEOccurrence
                c = self.candidate_factory.make_uniq(s[-len(words):])
                indexes = list(range(len(s)-len(words), len(s)))
                mweo = MWEOccurrence(s, c, indexes)
                s.mweoccurs.append(mweo)

        self.handler.handle_sentence(s, ctxinfo)


class MosesPrinter(common.AbstractPrinter):
    """Instances can be used to print Moses format."""
    valid_categories = ["corpus"]

    def handle_sentence(self, sentence, ctxinfo):
        """Prints a simple Moses string where words are separated by 
        a single space and each word part (surface, lemma, POS, syntax) is 
        separated from the next using a vertical bar "|".
        
        @return A string with the Moses form of the sentence
        """
        FMT.fmt_xwes(ctxinfo, self, sentence)
        self.add_string(ctxinfo, "\n")
