#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# fmtutil.py is part of mwetoolkit
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
This module provides utility functions to parse/print data more easily.
These functions should only be used by `ft_*.py` files.
"""






import itertools

from . import _common as common
from . import util


################################################################################


class _Joiner(object):
    def __init__(self, j_string):
        self.j_string = j_string
        self.join = j_string.join

    def split(self, string):
        return util.decent_str_split(string, self.j_string)


class XWEFormatter(object):
    """Instances of this class can convert SingleWE/MWE
    into a `mwe_joined_format|N_A_N|...` and help when converting
    back to internal representation.

    @param attr_joiner: string that joins word attributes (e.g: `"|"` in Moses).
    @param word_joiner: string that joins words in a MWE (e.g: `"="` in Moses).
    @param xwe_joiner: string that joins S/MWEs (e.g: `" "` in Moses).
    @param attr_getter: string that returns a fixed-length tuple of strings
    for a given Word (e.g: `lambda w: (w.surface, w.pos)`).
    @param xwe_inside_out: if True, join attributes after joining words.
    By default True, as it is trivial to join into a non-inside-out
    string using Python generators.
    """
    def __init__(self, attr_joiner, word_joiner,
            xwe_joiner, attr_getter, xwe_inside_out=True):
        self.attr_joiner = _Joiner(attr_joiner)  # e.g. "|" in Moses
        self.word_joiner = _Joiner(word_joiner)  # e.g. "_" in Moses
        self.xwe_joiner = _Joiner(xwe_joiner)    # e.g. " " in Moses
        self.attr_getter = attr_getter
        self.xwe_inside_out = xwe_inside_out


    def fmt_xwes(self, ctxinfo, printer, sentence):
        r"""Join the return of `self.fmt_xwe` for SWE/MWEs in `sentence`."""
        for i, xwe in enumerate(sentence.xwes()):
            if i != 0:
                printer.add_string(ctxinfo, self.xwe_joiner.j_string)
            self.fmt_xwe(ctxinfo, printer, xwe)


    def fmt_xwe(self, ctxinfo, printer, xwe):
        """Converts SingleWE/MWE into a `mwe_joined_format|N_A_N|...`

        @param printer: an object with `escape` and `add_string` methods.
        @param xwe: iterator that yields Word objects.
        @return A string representation of a SingleWE/MultiWE.
        """
        attrmtx = tuple(
                    tuple(printer.escape(a) for a in self.attr_getter(word))
                    for word in xwe)  # NxM matrix

        if not self.xwe_inside_out:
            for w in _joining(ctxinfo, printer, self.word_joiner.j_string, attrmtx):
                for a in _joining(ctxinfo, printer, self.attr_joiner.j_string, w):
                    printer.add_string(ctxinfo, a)
        else:
            # We use izip_longest just to catch programming errors
            attrmtx = itertools.zip_longest(*attrmtx, fillvalue="")
            for a in _joining(ctxinfo, printer, self.attr_joiner.j_string, attrmtx):
                for w in _joining(ctxinfo, printer, self.word_joiner.j_string, a):
                    printer.add_string(ctxinfo, w)


    def parse_xwes(self, ctxinfo, line):
        r"""Yield calls to `parse_xwe` for SWE/MWEs in `line`."""
        for xwe in self.xwe_joiner.split(line):
            yield tuple(self.parse_xwe(ctxinfo, xwe))


    def parse_xwe(self, ctxinfo, xwe_str):
        """Read a string such as "the_house|D_N" and yield things
        such as ("the", "D") and ("house", "N").
        """
        if not self.xwe_inside_out:
            words = self.word_joiner.split(xwe_str)
            return tuple(self.attr_joiner.split(w) for w in words)
        else:
            attrs = self.attr_joiner.split(xwe_str)
            words = (self.word_joiner.split(a) for a in attrs)
            # We use izip_longest just to catch programming errors
            return tuple(itertools.zip_longest(*words, fillvalue=""))


def _joining(ctxinfo, printer, joiner, iterable):
    r"""Iterate through iterable, outputting `joiner` between arguments."""
    first = True
    for elem in iterable:
        if not first:
            printer.add_string(ctxinfo, joiner)
        yield elem
        first = False


def make_props(entry_names, data_tuple, unescaper):
    # XXX We use this helper function in order to generate `props`
    # dictionaries from split data (see xwe_parse). In the future, this
    # should be integrated into xwe_parse, which should return two dictionaries
    # (one with e.g. {"lemma":"foo", "pos":"VBR"} and the other
    # {"*ID":"7", "@conll:postag":"V"})
    return {name:unescaper(value) for (name, value) in
            zip(entry_names, data_tuple) if value}
