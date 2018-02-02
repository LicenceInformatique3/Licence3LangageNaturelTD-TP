#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_dimsum.py is part of mwetoolkit
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
"DiMSUM" filetype, which is an input/output corpus textual format.

You should use the methods in package `filetype` instead.
"""






from . import _common as common
from ..base.candidate import Candidate, CandidateFactory
from ..base.sentence import Sentence, SentenceFactory
from ..base.mweoccur import MWEOccurrence
from ..base.word import Word
from .. import util


class DimsumInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for Dimsum format."""
    description = "DiMSUM CONLL-like format (with supersenses)"
    filetype_ext = "DiMSUM"

    entries = ["*W_ID", "surface", "lemma", "pos", "@dimsum:bio",
            "*MWEPREV", "@dimsum:mwestrength", "@dimsum:senseclass",
            "@dimsum:__sentid"]

    comment_prefix = "#"
    escaper = None

    def operations(self):
        return common.FiletypeOperations(DimsumChecker,
                DimsumParser, DimsumPrinter)


INFO = DimsumInfo()

class DimsumChecker(common.AbstractChecker):
    r"""Checks whether input is in Dimsum format."""
    def matches_header(self, strict):
        if not strict: return True
        header = self.fileobj.peek(1024)
        first_line = header.split(b"\n")[0].split(b"\t")
        # First line must have the form 1\tXX\tXX\tNONNUMBER\tXX\t0\tXX\tXX\tXX
        return len(first_line) == 9 \
                and first_line[0] == b"1" \
                and first_line[5] == b"0" \
                and not first_line[3][:1].isdigit()


class DimsumParser(common.AbstractTxtParser):
    r"""Instances of this class parse the Dimsum format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["corpus"]

    def __init__(self, encoding='utf-8'):
        super(DimsumParser, self).__init__(encoding, autostrip=False)
        self.sentence_factory = SentenceFactory()
        self.candidate_factory = CandidateFactory()
        self.name2index = {name:i for (i, name) in
                enumerate(self.filetype_info.entries)}
        self.category = "corpus"

    def _parse_line(self, line, ctxinfo):
        if not line:
            self.flush_partial_callback()
            return  # empty line

        if self.partial_fun is None:
            self.new_partial(self.handler.handle_sentence,
                    self.sentence_factory.make(), ctxinfo=ctxinfo)
            self.id2mwe = {}

        data = line.split("\t")
        if len(data) <= 1: return

        if len(data) != len(self.filetype_info.entries):
            ctxinfo.warn("Expected {n_expected} entries, got {n_gotten}",
                    n_expected=len(self.filetype_info.entries),
                    n_gotten=len(data))
            return

        propsdict = dict((k, v) for (k, v)
                in zip(self.filetype_info.entries, data)  if v)
        wid = int(propsdict.pop("*W_ID"))-1
        self.partial_args[0].append(Word(ctxinfo, propsdict))

        mweprev = int(propsdict.pop("*MWEPREV", 0))-1
        if mweprev != -1:
            try:
                mweo = self.id2mwe[mweprev]
            except KeyError:
                mweo = MWEOccurrence(self.partial_args[0],
                        self.candidate_factory.make(), [mweprev])
                self.partial_args[0].mweoccurs.append(mweo)
                self.id2mwe[mweprev] = mweo

            mweo.indexes.append(wid)
            self.id2mwe[wid] = mweo



class DimsumPrinter(common.AbstractPrinter):
    valid_categories = ["corpus"]

    def handle_sentence(self, sentence, ctxinfo):
        bio = sentence.bio_list(update_mweoccurs=True)

        mweprev = [-1] * len(sentence)
        for indexes in sentence.xwe_indexes():
            for i in range(len(indexes)-1):
                mweprev[indexes[i+1]] = indexes[i]

        for wid, word in enumerate(sentence):
            self.add_string(ctxinfo, str(wid+1), "\t")
            self.add_string(ctxinfo, word.surface, "\t",
                    word.lemma, "\t", word.pos, "\t")

            self.add_string(ctxinfo, bio[wid], "\t")

            self.add_string(ctxinfo, str(mweprev[wid]+1))
            self.add_string(ctxinfo, "\t")
            self.add_string(ctxinfo, "", "\t")  # mwestrength field always empty
            self.add_string(ctxinfo, word.get_prop("@dimsum:senseclass", ""), "\t")
            self.add_string(ctxinfo, word.get_prop("@dimsum:__sentid", ""), "\n")
        self.add_string(ctxinfo, "\n")
