#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_conll.py is part of mwetoolkit
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
"CONLL" filetype, which is a useful input/output corpus textual format.

You should use the methods in package `filetype` instead.
"""







from . import _common as common
from ..base.candidate import CandidateFactory
from ..base.sentence import SentenceFactory
from ..base.word import Word
from .. import util



class ConllInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for CONLL."""
    description = "CONLL tab-separated 10-entries-per-word"
    filetype_ext = "CONLL"

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("_", "${underscore}"),
            (" ", "${space}"), ("#", "${hash}"),
            ("\t", "${tab}"), ("\n", "${newline}")
    ])

    entries = ["*ID", "surface", "lemma", "@coarse_pos", "pos",
            "@conll:feats", "*HEAD", "*DEPREL",
            "@conll-x:phead", "@connl-x:pdeprel"]

    def operations(self):
        return common.FiletypeOperations(ConllChecker, ConllParser,
                ConllPrinter)
                
INFO = ConllInfo()

class ConllChecker(common.AbstractChecker):
    r"""Checks whether input is in CONLL format."""
    def matches_header(self, strict):
        header = self.fileobj.peek(1024)
        for line in header.split(b"\n"):
            if line and not line.startswith(
                    util.utf8_unicode2bytes(self.filetype_info.comment_prefix)):
                return len(line.split(b"\t")) == len(self.filetype_info.entries)
        return not strict


def getitem(a_list, index, default=None):
    r"""Obvious implementation for a function
    that should already exist."""
    try:
        return a_list[index]
    except IndexError:
        return default



# XXX in the future, we should use fmtutil to generate a dict
# (instead of a tuple) and this should disappear (key=EMPTYATTR
# will just be a missing key in the dict)
EMPTYATTR = ""


class ConllParser(common.AbstractTxtParser):
    r"""Instances of this class parse the CONLL-X format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["corpus"]

    def __init__(self, encoding='utf-8'):
        super(ConllParser,self).__init__(encoding)
        self.sentence_factory = SentenceFactory()
        self.candidate_factory = CandidateFactory()
        self.ignoring_cur_sent = False
        self.name2index = {name:i for (i, name) in
                enumerate(self.filetype_info.entries)}
        self.index_id = self.name2index["*ID"]
        self.index_syn0 = self.filetype_info.entries.index("*DEPREL")
        self.index_syn1 = self.filetype_info.entries.index("*HEAD")
        self.category = "corpus"

    def _parse_line(self, line, ctxinfo):
        data = line.split("\t")
        if len(data) <= 1: return
        data = [d.split(" ") for d in data]  # split MWEs

        if len(data) != len(self.filetype_info.entries):
            ctxinfo.warn("Expected {n_expected} entries, got {n_gotten}",
                    n_expected=len(self.filetype_info.entries),
                    n_gotten=len(data))
            self.ignoring_cur_sent = True
            return

        indexes = []
        for mwe_i, wid_s in enumerate(data[self.index_id]):
            word_data = [getitem(d, mwe_i, "_") for d in data]
            word_data = [(EMPTYATTR if d == "_" else d) for d in word_data]
            try:
                wid = int(wid_s)-1
            except ValueError:
                ctxinfo.warn("Bad word ID at field {field_idx}: {wid_s!r} ",
                        field_idx=self.index_id, wid_s=wid_s)
                self.ignoring_cur_sent = True
            else:
                if wid == 0:
                    self.new_partial(self.handler.handle_sentence,
                            self.sentence_factory.make(), ctxinfo=ctxinfo)
                    self.ignoring_cur_sent = False

                if not self.ignoring_cur_sent:
                    indexes.append(wid)
                    word = self._parse_word(self.handler, word_data, ctxinfo)
                    self.partial_args[0].append(word)

        if len(data[self.index_id]) != 1:
            from ..base.mweoccur import MWEOccurrence
            mwe_words = []  # XXX do we use surface or lemma?
            c = self.candidate_factory.make_uniq(mwe_words)
            mweo = MWEOccurrence(self.partial_args[0], c, indexes)
            self.partial_args[0].mweoccurs.append(mweo)

    def _parse_word(self, handler, word_data, ctxinfo):
        w = Word(ctxinfo, {})
        for prop_name, value in zip(self.filetype_info.entries, word_data):
            if not prop_name.startswith("*"):
                w.set_prop(prop_name, self.unescape(value))

        syn = self.unescape(word_data[self.index_syn0])
        syn1 = self.unescape(word_data[self.index_syn1])
        if syn != EMPTYATTR and syn1 != EMPTYATTR:
            syn += ":" + str(syn1)
        w.syn = syn
        return w


class ConllPrinter(common.AbstractPrinter):
    BETWEEN_SENTENCES = "\n"
    valid_categories = ["corpus"]

    def __init__(self, ctxinfo, category, **kwargs):
        super(ConllPrinter, self).__init__(ctxinfo, category, **kwargs)
        self.count_sentences = 0
        self.index_syn0 = self.filetype_info.entries.index("*DEPREL")
        self.index_syn1 = self.filetype_info.entries.index("*HEAD")
        self.index_id = self.filetype_info.entries.index("*ID")


    def handle_sentence(self, sentence, ctxinfo):
        if self.count_sentences != 0:
            self.add_string(ctxinfo, self.BETWEEN_SENTENCES)
        self.count_sentences += 1

        for indexes in sentence.xwe_indexes():
            entries = []  # [[entries for word 1], [entries for 2], ...]
            for i in indexes:
                entry = []
                word = sentence[i]
                props = word.get_props()
                for prop_name in self.filetype_info.entries:
                    try:
                        entry.append(self.escape(props.pop(prop_name)))
                    except KeyError:
                        entry.append("_")

                props.pop("syn", None)  # Handling `syn` here
                syn_list = list(word.syn_iter(ctxinfo))
                if len(syn_list) != 0:
                    if len(syn_list) > 1:
                        ctxinfo.warn("Ignoring multiple syn values")
                    entry[self.index_syn0] = self.escape(syn_list[0][0])
                    entry[self.index_syn1] = self.escape(str(syn_list[0][1]+1))

                entry[self.index_id] = str(i + 1)
                word.ctxinfo.check_all_popped(props)
                entries.append(entry)

            line = list(zip(*entries))  # [[entries A for all], [entries B], ...]
            line = "\t".join(" ".join(entries_n) for entries_n in line)
            self.add_string(ctxinfo, line, "\n")
