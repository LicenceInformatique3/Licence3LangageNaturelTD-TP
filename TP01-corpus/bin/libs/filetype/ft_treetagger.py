#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_treetagger.py is part of mwetoolkit
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
"TreeTagger" filetype, which is a useful input corpus textual format.

You should use the methods in package `filetype` instead.
"""






from . import _common as common
from ..base.candidate import Candidate
from ..base.sentence import SentenceFactory
from ..base.word import Word
from . import fmtutil
from .. import util


class TreeTaggerInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for TreeTagger format."""
    description = "3-field tab-separated format output by TreeTagger"
    filetype_ext = "TreeTagger"
  
    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("|", "${pipe}"), ("#", "${hash}"),
            ("<", "${lt}"), (">", "${gt}"), (" ", "${space}"),
            ("\t", "${tab}"), ("\n", "${newline}")
    ])
                    
    entries = ["surface", "pos", "lemma"]

    def operations(self):
        return common.FiletypeOperations(
                TreeTaggerChecker, TreeTaggerParser, TreeTaggerPrinter)


INFO = TreeTaggerInfo()

class TreeTaggerParser(common.AbstractTxtParser):
    r"""Parse file in TreeTagger TAB-separated format:
    One word per line, each word is in format "surface\tpos\tlemma".
    Optional sentence separators "</s>" may also constitute a word on a line.
    """
    valid_categories = ["corpus"]

    def __init__(self, encoding='utf-8', sent_split=None):
        super(TreeTaggerParser, self).__init__(encoding)
        self.sentence_factory = SentenceFactory()
        self.category = "corpus"
        self.words = []
        self.sent_split = sent_split

    def _parse_line(self, line, ctxinfo):
        self.current_ctxinfo = ctxinfo
        sentence = None

        if not self.words:
            self.new_partial(self.finish_sentence, ctxinfo)

        if line == "</s>":
            self.flush_partial_callback()

        else:
            fields = line.split("\t")
            if len(fields) != 3:
                ctxinfo.warn("Expected 3 entries, got {n_entries}", 
                        n_entries=len(fields))
                return

            fields = ("" if f=="<unknown>" \
                    else self.unescape(f) for f in fields)
            props = fmtutil.make_props(self.filetype_info.entries, fields, unescaper=lambda x: x)
            word = Word(ctxinfo, props)
            self.words.append(word)
            
            if self.words and len(self.words) > 500 :
                ctxinfo.warn_once("Very long sentence: {n} words. Did you "\
                           "specify a sentence delimiter?", n=len(self.words))

            if word.pos == self.sent_split:
                self.flush_partial_callback()


    def finish_sentence(self, ctxinfo):
        r"""Finish building sentence and call handler."""
        if len(self.words) > 500:
            ctxinfo.warn("Very long sentence: {n} words. Did you "\
                       "specify a sentence delimiter?", n=len(self.words))

        s = self.sentence_factory.make(self.words)
        self.handler.handle_sentence(s, self.current_ctxinfo)
        self.words = []


class TreeTaggerChecker(common.AbstractChecker):
    r"""Checks whether input is in TreeTagger format."""
    def matches_header(self, strict):
        header = self.fileobj.peek(1024)
        for line in header.split(b"\n"):
            if line and not line.startswith(
                    util.utf8_unicode2bytes(self.filetype_info.comment_prefix)):
                return len(line.split(b"\t")) == len(self.filetype_info.entries)
        return not strict


class TreeTaggerPrinter(common.AbstractPrinter):

    valid_categories = ["corpus"]
    BETWEEN_SENTENCES = "</s>\n"
    
    def __init__(self, ctxinfo, category, **kwargs):
        super(TreeTaggerPrinter, self).__init__(ctxinfo, category, **kwargs)
        self.count_sentences = 0


    def handle_sentence(self, sentence, ctxinfo):
        if self.count_sentences != 0:
            self.add_string(ctxinfo, self.BETWEEN_SENTENCES)
        self.count_sentences += 1

        for indexes in sentence.xwe_indexes():
            multi_entries = []  # [[entries for word 1], [entries for 2], ...]
            for i in indexes:
                word = sentence[i]
                entries = []
                for entry_name in self.filetype_info.entries:
                    try:
                        entries.append(self.escape(word.get_prop(entry_name)))
                    except KeyError:
                        entries.append("<unknown>")
                multi_entries.append(entries)

            line = list(zip(*multi_entries))  # [[entries A for all], [entries B], ...]
            line = "\t".join(" ".join(entries_n) for entries_n in line)
            self.add_string(ctxinfo, line, "\n")
