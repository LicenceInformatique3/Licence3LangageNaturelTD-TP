#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_glove.py is part of mwetoolkit
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
"GloVe" filetype, which is a useful input/output word-embedding format.

You should use the methods in package `filetype` instead.
"""






import collections

from . import _common as common
from ..base.embedding import Embedding, EmbeddingVector
from ..base.word import Word
from .. import util


class GloveInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for GloVe format."""
    description = "GloVe format (headerless word2vec)"
    filetype_ext = "GloVe"
 
    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), (" ", "${space}"), ("\t", "${tab}"),
            ("_", "${underscore}"), ("+", "${plus}"), ("#", "${hash}"),
            ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(GloveChecker,
                GloveParser, GlovePrinter)

INFO = GloveInfo()

class GloveChecker(common.AbstractChecker):
    r"""Checks whether input is in GloVe format."""
    def matches_header(self, strict):
        if not strict: return True
        header = self.fileobj.peek(2048)
        first_lines = header.rstrip(b"\n").split(b"\n")
        try:
            first_line = next(line for line in first_lines
                    if not line.startswith(util.utf8_unicode2bytes(
                        self.filetype_info.comment_prefix)))
        except StopIteration:
            return False

        try:
            word, vector = first_line.split(b" ", 1)
            if len(vector) <= 1: return False  # Avoid conflict with word2vec
            for value in vector.rstrip().split(b" "):
                float(value)  # Check if value is a float
        except (ValueError, TypeError):
            return False
        return True


class GloveParser(common.AbstractTxtParser):
    r"""Instances of this class parse the GloVe format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["embeddings"]

    def __init__(self, encoding='utf-8'):
        super(GloveParser, self).__init__(encoding)
        self.category = "embeddings"
        self.names = []

    def _parse_line(self, line, ctxinfo):
        pieces = line.split(" ")
        target_mwe = tuple(self.unescape(x) for x in pieces[0].split("_"))
        float_values = [float(v) for v in pieces[1:]]
        while len(float_values) > len(self.names):
            self.names.append(("c{}".format(len(self.names)),))
        value_vec = EmbeddingVector(list(zip(self.names, float_values)))
        mapping = collections.OrderedDict([("GloVe-value", value_vec)])
        emb = Embedding(target_mwe, mapping)
        self.handler.handle_embedding(emb, ctxinfo)



class GlovePrinter(common.AbstractPrinter):
    """Instances can be used to print GloVe format."""
    valid_categories = ["embeddings"]
    
    def __init__(self, *args, **kwargs):
        super(GlovePrinter, self).__init__(*args, **kwargs)
        self.context2id = {}
        self.ordered_contexts = []


    def handle_embedding(self, embedding, ctxinfo):
        for context in embedding.all_contexts():
            if context not in self.context2id:
                id = len(self.context2id)
                self.context2id[context] = id
                self.ordered_contexts.append(context)

        target = "_".join(self.escape(t) for t in embedding.target_mwe)
        self.add_string(ctxinfo, target)

        embvector = embedding.getany("GloVe-value")
        for id, context in enumerate(self.ordered_contexts):
            value = embvector.get(context)
            self.add_string(ctxinfo, " {0:.5f}".format(value))
        self.add_string(ctxinfo, "\n")
