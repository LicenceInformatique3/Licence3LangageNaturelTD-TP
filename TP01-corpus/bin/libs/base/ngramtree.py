#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ngramtree.py is part of mwetoolkit
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
    This module provides the `NgramTree` class, which is a prefix tree
    that represents a set of n-grams.
"""






import collections
from . import mweoccur


############################################################

class NgramTree(object):
    r"""A prefix tree where each edge transition is associated
    with a dict of `props` (e.g. {"lemma":"be", "surface":"are"}).
    """
    def __init__(self):
        # Dict[prop_keys, Dict[prop_set, NgramTree]]
        # where e.g. prop_keys = frozenset(["lemma", "surface"])
        # where e.g. prop_set = frozenset([("lemma","be"), ("surface","are")])
        self._keys2props2subtree = collections.defaultdict(dict)


    def add_subtree_for_ngram(self, ctxinfo, ngram):
        r"""Add subtree nodes for given `Ngram`.
        Calls `add_subtree_for_word`.
        """
        subtree = self
        for word in ngram:
            subtree = subtree.add_subtree_for_word_props(
                    ctxinfo, word.get_props())
        return subtree

    def add_subtree_for_word_props(self, ctxinfo, props):
        r"""Return child NgramTree linked by `props` edge.
        Example:
        >>> add_subtree_for_word({"lemma":"be", "pos":"V"})
        """
        prop_set = frozenset(iter(props.items()))
        prop_keys = frozenset(iter(props.keys()))
        props2subtree = self._keys2props2subtree[prop_keys]
        try:
            return props2subtree[prop_set]
        except KeyError:
            ret = props2subtree[prop_set] = type(self)()
            return ret


    def iter_subtrees_matching_word(self, word, match_superset=False):
        r"""Yield children NgramTree's that match `word`."""
        expected_props = word.get_props()
        expected_keys = expected_props.keys()
        for keys, props2subtree in self._keys2props2subtree.items():
            if self.matches(keys, expected_keys, match_superset=match_superset):
                prop_set = frozenset((k, expected_props[k]) for k in keys)
                try:
                    yield props2subtree[prop_set]
                except KeyError:
                    pass  # No MWE with these properties


    def iter_subtrees_matching_ngram(self, ngram, _i=0, match_superset=False):
        r"""Yield all descendant subtrees for given `ngram`."""
        if len(ngram) == _i:
            yield self; return
        for subtree in self.iter_subtrees_matching_word(ngram[_i], match_superset=match_superset):
            for ret in subtree.iter_subtrees_matching_ngram(ngram, _i+1, match_superset=match_superset):
                yield ret  # (In python 3.x, `yield from`)


    def matches(self, keys, expected_keys, match_superset):
        r"""Return whether keys is a subset of expected_keys.
        (Compares against superset if `match_superset=True` instead).
        """
        if match_superset:
            return keys.issuperset(expected_keys)
        return keys.issubset(expected_keys)


    def has_subtree_matching_ngram(self, ngram, _i=0):
        r"""Return True iff there is a descendant
        subtree for given `ngram`.
        """
        if len(ngram) == _i:
            return True  # Base case
        return any(ngt.matches_ngram(ngram, _i+1)
                for ngt in self.iter_subtrees_matching_word(ngram[_i]))



############################################################

class NgramPartialMatch(collections.namedtuple('NgramPartialMatch',
        'ngram_tree sentence n_available_gaps indexes')):
    r"""Instances of NgramPartialMatch represent a partial match
    of a sentence fragment as a path in an NgramTree.

    You need to use this class when:
    * You want to find matches with gaps; or
    * You want to have multiple matches with
    many different starting indexes in a sentence; or
    * You want a list of all matched indexes.

    Arguments:
    -- ngram_tree: the next node of the tree to match
    -- sentence: the sentence being matches
    -- n_available_gaps: number of gaps still allowed
    -- indexes: indexes in `self.sentence` that have already matched
    """

    def matching_at(self, i):
        r"""For a given sentence index `i`, walk the
        tree and yield new NgramPartialMatch instances.
        """
        word = self.sentence[i]
        new_indexes = self.indexes + (i,)
        for subtree in self.ngram_tree.iter_subtrees_matching_word(word):
            yield NgramPartialMatch(subtree, self.sentence,
                    self.n_available_gaps, new_indexes)

        if self.n_available_gaps > 0 and self.indexes:
            yield NgramPartialMatch(self.ngram_tree, self.sentence,
                    self.n_available_gaps-1, self.indexes)


    def mweoccurs_after_matching_at(self, i):
        r"""For a given sentence index `i`, check if
        the current tree position is associated with Ngram
        instances and yield MWEOccurrence's if so.
        """
        if self.indexes[-1] != i:
            return  # Do not allow gaps at the end of a MWEO
        for ngram in self.ngram_tree.ngrams_finishing_here:
            yield mweoccur.MWEOccurrence(self.sentence, ngram, self.indexes)
