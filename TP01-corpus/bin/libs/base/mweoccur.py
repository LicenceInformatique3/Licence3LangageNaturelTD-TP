#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# mweoccur.py is part of mwetoolkit
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
This module provides the `MWEOccurrence` class. This class represents an
occurrence of an MWE `Candidate` inside a `Sentence`.
"""

################################################################################








class MWEOccurrence(object):
    r"""Represents the occurrence of an MWE candidate in a sentence.

    Constructor Arguments:
    @param sentence The sentence in this occurrence.
    @param candidate The MWE candidate in this occurrence.
    @param indexes A tuple of indexes that represent the position of
    each word from `self.candidate` in `self.sentence`.
    This list will be `list(xrange(i, i + len(self.candidate)))` when
    referring to the simplest kinds of MWEs.  If the MWE in-sentence has
    different word order (e.g. passive voice in English), a permutation of
    those indexes will be used.  If there are gaps inside the MWE (e.g.
    verb-particle compounds in English), other sentence indexes may be used.

    IMPORTANT: This list is 0-based in python but 1-based in XML.

    Examples:
        Today ,  a  demo was given  Sentence
                 ~  ~~~~     ~~~~~  Candidate = "give a demo"
        _     _  2  3    _   5      indexes = [5, 2, 3]

        The old man kicked the proverbial bucket  Sentence
                    ~~~~~~ ~~~            ~~~~~~  Candidate = "kick the bucket"
        _   _   _   3      4   _          6       indexes = [3, 4, 6]
    """
    def __init__(self, sentence, candidate, sentence_indexes):
        for s_i in sentence_indexes:
            if not (0 <= s_i < len(sentence)):
                raise Exception("Candidate %r references bad word " \
                        "index: Sentence %r (len %r), index %r."  % (
                        candidate.id_number, sentence.id_number,
                        len(sentence), s_i+1))
        self.candidate = candidate
        self.sentence = sentence
        self.indexes = sentence_indexes

    def is_contiguous(self):
        r"""True if indexes are not sequential (if gappy or in non-increasing order)."""
        return all(a+1==b for (a,b) in zip(self.indexes, self.indexes[1:]))

    def is_gappy(self):
        r"""True if indexes have gaps in between (but False if in non-increasing order)."""
        return not self.is_contiguous() \
                and all(a<b for (a,b) in zip(self.indexes, self.indexes[1:]))

        
################################################################################
        
if __name__ == "__main__" :
    import doctest
    doctest.testmod()  
