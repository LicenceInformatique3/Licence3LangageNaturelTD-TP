#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_minimanticsprofile.py is part of mwetoolkit
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
"MinimanticsProfile" filetype, which is a useful input/output word-embedding format.

You should use the methods in package `filetype` instead.
"""






import collections

from . import _common as common
from ..base.embedding import Embedding, EmbeddingVector
from ..base.word import Word
from .. import util


class MinimanticsProfileInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for MinimanticsProfile format."""
    description = "Minimantics profile format"
    filetype_ext = "MinimanticsProfile"
 
    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), (" ", "${space}"), ("\t", "${tab}"),
            ("_", "${underscore}"), ("+", "${plus}"), ("#", "${hash}"),
            ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(MinimanticsProfileChecker,
                MinimanticsProfileParser, MinimanticsProfilePrinter)

INFO = MinimanticsProfileInfo()


class MinimanticsProfileChecker(common.AbstractChecker):
    r"""Checks whether input is in MinimanticsProfile format."""
    def matches_header(self, strict):
        if not strict: return True
        header = self.fileobj.peek(2048)
        return header.startswith(b"target\tid_target\tcontext") \
                or header.startswith(b"target\tcontext")


class MinimanticsProfileParser(common.AbstractTxtParser):
    r"""Instances of this class parse the MinimanticsProfile format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["embeddings"]

    def __init__(self, encoding='utf-8'):
        super(MinimanticsProfileParser, self).__init__(encoding)
        self.category = "embeddings"
        self.cur_target = None
        self.header = None

    def _parse_line(self, line, ctxinfo):
        if self.header is None:
            self.header = line.split("\t")
            if "target" not in self.header:
                ctxinfo.error("File header must have `target`")
            if "context" not in self.header:
                ctxinfo.error("File header must have `context`")
        else:
            data = line.split("\t")
            if len(data) != len(self.header):
                return ctxinfo.warn("Line has `{n}` entries; expected `{expected}`",
                        n=len(data), expected=len(self.header))

            datadict = collections.OrderedDict(list(zip(self.header, data)))
            target = tuple(self.unescape(t) for t in datadict.pop("target").split("_"))
            context = tuple(self.unescape(c) for c in datadict.pop("context").split("_"))

            for vecname in list(datadict.keys()):
                if vecname.startswith("id_"):
                    datadict.pop(vecname)

            if target != self.cur_target:
                self.new_partial(self.handler.handle_sentence,
                        Embedding.zero(target), ctxinfo=ctxinfo)
                self.cur_target = target

            for vecname, value in datadict.items():
                self.partial_args[0].get(vecname).increment(context, float(value))



class MinimanticsProfilePrinter(common.AbstractPrinter):
    """Instances can be used to print MinimanticsProfile format."""
    valid_categories = ["embeddings"]
    
    def __init__(self, *args, **kwargs):
        super(MinimanticsProfilePrinter, self).__init__(*args, **kwargs)
        self.all_contexts = None


    def handle_embedding(self, embedding, ctxinfo):
        if self.all_contexts is None:
            self.all_contexts = embedding.all_contexts()
            self.add_string(ctxinfo, "target\tcontext")
            for vecname in embedding.iter_vecnames():
                self.add_string(ctxinfo, "\t", vecname)
            self.add_string(ctxinfo, "\n")

        for context in self.all_contexts:
            self.add_string(ctxinfo, self.join(embedding.target_mwe))
            self.add_string(ctxinfo, "\t", self.join(context))
            for embvector in embedding.iter_vectors():
                self.add_string(ctxinfo, "\t{:.5f}".format(embvector.get(context)))
            self.add_string(ctxinfo, "\n")

    def join(self, strings):
        return "_".join(self.escape(s) for s in strings)
