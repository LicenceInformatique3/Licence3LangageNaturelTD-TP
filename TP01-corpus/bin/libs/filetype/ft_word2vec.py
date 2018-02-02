#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_word2vec.py is part of mwetoolkit
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
"word2vec" filetype, which is a useful input/output word-embedding format.

You should use the methods in package `filetype` instead.
"""






import collections

from . import _common as common
from ..base.embedding import Embedding, EmbeddingVector
from ..base.word import Word
from .. import util


class Word2vecInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for word2vec format."""
    description = "word2vec textual format"
    filetype_ext = "word2vec"
 
    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), (" ", "${space}"), ("\t", "${tab}"),
            ("_", "${underscore}"), ("+", "${plus}"), ("#", "${hash}"),
            ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(Word2vecChecker,
                Word2vecParser, Word2vecPrinter)

INFO = Word2vecInfo()

class Word2vecChecker(common.AbstractChecker):
    r"""Checks whether input is in word2vec format."""
    def matches_header(self, strict):
        if not strict: return True
        header = self.fileobj.peek(2048)
        first_lines = header.rstrip(b"\n").split(b"\n")
        first_lines = [line for line in first_lines
                if not line.startswith(util.utf8_unicode2bytes(
                    self.filetype_info.comment_prefix))]
        if len(first_lines) == 0:
            return False
        if len(first_lines) == 1:
            return header.startswith(b"0 ")

        try:
            n_lines, dim = first_lines[0].split(b" ")
            return len(first_lines[1].split(b" ")) == int(dim)+1
        except (ValueError, TypeError):
            return False


class Word2vecParser(common.AbstractTxtParser):
    r"""Instances of this class parse the word2vec format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["embeddings"]

    def __init__(self, encoding='utf-8'):
        super(Word2vecParser, self).__init__(encoding)
        self.category = "embeddings"
        self.first_line = True

    def _parse_line(self, line, ctxinfo):
        if self.first_line:
            self.first_line = False
            n_lines, dim = line.split(" ")
            self.n = int(dim)
            self.names = [("c{}".format(i),) for i in range(self.n)]
        else:
            pieces = line.split(" ")
            target_mwe = tuple(self.unescape(x) for x in pieces[0].split("_"))
            float_values = [float(v) for v in pieces[1:]]
            value_vec = EmbeddingVector(list(zip(self.names, float_values)))
            mapping = collections.OrderedDict([("w2v-value", value_vec)])
            emb = Embedding(target_mwe, mapping)
            self.handler.handle_embedding(emb, ctxinfo)



class Word2vecPrinter(common.AbstractPrinter):
    """Instances can be used to print word2vec format."""
    valid_categories = ["embeddings"]
    
    def __init__(self, *args, **kwargs):
        super(Word2vecPrinter, self).__init__(*args, **kwargs)
        self.embeddings = []
        self.context2id = {}
        self.ordered_contexts = []


    def handle_embedding(self, embedding, ctxinfo):
        """Since the word2vec header must contain the number of lines and
        global number of contexts, we need to store everything in memory
        and then print it all at `finish`.
        """
        for context in embedding.all_contexts():
            if context not in self.context2id:
                id = len(self.context2id)
                self.context2id[context] = id
                self.ordered_contexts.append(context)
        self.embeddings.append((embedding, ctxinfo))


    def finish(self, finish_ctxinfo):
        r"""Actually print the embeddings, preceded by the header."""
        self.add_string(finish_ctxinfo,
                str(len(self.embeddings)), " ",
                str(len(self.context2id)), "\n")

        for embedding, emb_ctxinfo in self.embeddings:
            target = "_".join(self.escape(t) for t in embedding.target_mwe)
            self.add_string(emb_ctxinfo, target)

            embvector = embedding.getany("w2v-value")
            for id, context in enumerate(self.ordered_contexts):
                value = embvector.get(context)
                self.add_string(emb_ctxinfo, " {0:.5f}".format(value))
            self.add_string(emb_ctxinfo, "\n")
