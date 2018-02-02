#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# embedding.py is part of mwetoolkit
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
    This module provides the `Embedding` class, which is essentially
    a sparse vector with a `target` single-word or MWE.
"""





import collections
import math

from .word import Word


################################################################################

class EmbeddingFactory(object):
    r"""Instances of EmbeddingFactory can be used
    to create instances of Embedding while keeping
    a ctx2value of (`context` -> `integer_id`).

    Call `self.make(target, ctx2value)` to create an Embedding.
    """
    def __init__(self):
        self.context2id = {}

    def make(self, target, ctx2value):
        r"""Calls `Embedding(...)` to create a word embedding."""
        for context in ctx2value:
            self.context2id[context] = len(self.context2id)
        return Embedding(target, ctx2value)


################################################################################

class Embedding(object):
    """An Embedding object is a group of `EmbeddingVector`s,
    one for each `vecname` (e.g. vecname=PMI, vecname=cosine...)

    @param target_mwe: a list of strings indicating the target name
    (list length > 1 if the target is an MWE)
    @param vecname2vec: an OrderedDict with {vecname: EmbeddingVector}
    """
    DISPATCH = "handle_embedding"

    def __init__(self, target_mwe, vecname2vec):
        assert isinstance(target_mwe, (tuple, list)), target_mwe
        assert isinstance(vecname2vec, collections.OrderedDict), vecname2vec
        self.target_mwe = tuple(target_mwe)
        self._vecname2vec = vecname2vec

    def copy(self):
        r"""Return a new Embedding that is a copy of `self`."""
        return Embedding(tuple(self.target_mwe), collection.OrderedDict(
                (k, v.copy()) for (k, v) in self._vecname2vec.items()))

    def iter_vec_items(self):
        r"""Yield (vecname, vec) pairs."""
        return iter(self._vecname2vec.items())

    def iter_vecnames(self):
        r"""Yield the name of all vectors."""
        return iter(self._vecname2vec.keys())

    def iter_vectors(self):
        r"""Yield all `EmbeddingVector`s."""
        return iter(self._vecname2vec.values())

    def all_contexts(self):
        r"""Return the name of all contexts inside any of the vectors."""
        seen, ret = set(), []
        for embvec in self.iter_vectors():
            for context in embvec.iter_contexts():
                if context not in seen:
                    seen.add(context)
                    ret.append(context)
        return ret

    def n_vectors(self):
        r"""Return number of `EmbeddingVector`s in this `Embedding`."""
        return len(self._vecname2vec)


    @staticmethod
    def zero(target_mwe=()):
        r"""Instantiate an empty embedding."""
        return Embedding(target_mwe, collections.OrderedDict())


    def get(self, vecname):
        r"""Return the EmbeddingVector for `vecname` (create it if needed)."""
        try:
            return self._vecname2vec[vecname]
        except KeyError:
            return self._vecname2vec.setdefault(vecname, EmbeddingVector())


    def getany(self, pref_vecname, on_missing=None):
        r"""Return any EmbeddingVector, preferably `pref_vecname`.

        If `pref_vecname` is not found, calls `on_missing(vecname, vec)`
        with the (vecname, vec) that will be used.  `on_missing` is expected
        to return the actual (vecname, vec) pair that will be used.
        """
        try:
            # Try `pref_vecname`
            return self._vecname2vec[pref_vecname]
        except KeyError:
            try:
                # Try any other vecname
                vecname, vec = next(iter(self._vecname2vec.items()))
                if on_missing is not None:
                    vecname, vec = on_missing(vecname, vec)
                return vec
            except StopIteration:
                # If nothing exists, create `pref_vecname`
                return self.get(pref_vecname)


    def update_add(self, other):
        r"""Call `self.increment` for each (key, val) pair in `other`."""
        assert isinstance(other, Embedding), other
        for vecname, vec in other.iter_vec_items():
            self.get(vecname).update_add(vec)

    @staticmethod
    def sum(embeddings):
        r"""Return the sum of all elements."""
        ret = Embedding.zero()
        for emb in embeddings:
            assert isinstance(emb, Embedding), emb
            ret.update_add(emb)
        return ret


################################################################################

class EmbeddingVector(object):
    """An EmbeddingVector is a sparse vector, represented
    as an OrderedDict {context_mwe: real_number}.
    """
    def __init__(self, init=None):
        self._ctx2value = collections.OrderedDict(init or ())

    def __repr__(self):
        return "EmbeddingVector({})".format(" ".join(
                "{}={}".format("_".join(k), v) \
                for (k, v) in self._ctx2value.items()))

    def copy(self):
        r"""Return a new Embedding that is a copy of `self`."""
        return EmbeddingVector(self._ctx2value)

    def is_zero(self):
        r"""Return whether this is EmbeddingVector only has zero values."""
        return all(v==0 for v in self._ctx2value.values())


    def iter_contexts(self):
        r"""Yield the names of all contexts."""
        return iter(self._ctx2value.keys())


    def has_context(self, context):
        r"""Yield the names of all contexts."""
        assert isinstance(context, tuple)
        return context in self._ctx2value


    def get(self, context):
        r"""Return a real number for given context.
        Returns 0 if context is not known.
        """
        assert isinstance(context, tuple)
        return self._ctx2value.get(context, 0)


    def increment(self, context, added_value):
        r"""Set self[context] = old_value + added_value"""
        assert isinstance(context, tuple)
        try:
            self._ctx2value[context] += added_value
        except KeyError:
            self._ctx2value[context] = added_value


    def update_add(self, other):
        r"""Call `self.increment` for each (key, val) pair in `other`."""
        for k, v in other._ctx2value.items():
            self.increment(k, v)


    def __add__(self, other):
        ret = self.copy()
        ret.update(other)
        ret.target_mwe = self.target_mwe + other.target_mwe
        return ret


    @staticmethod
    def sum(embvectors):
        r"""Return the sum of all elements."""
        ret = EmbeddingVector()
        for vec in embvectors:
            assert isinstance(vec, EmbeddingVector), vec
            ret.update_add(vec)
        return ret


    def dotprod(self, other):
        r"""Return the dot product between embeddings."""
        assert isinstance(other, EmbeddingVector), other
        ret = 0.0
        for ctx in self.iter_contexts():
            if other.has_context(ctx):
                ret += self.get(ctx) * other.get(ctx)
        return ret


    def abs(self):
        r"""Return the hypothenuse of `self`."""
        return math.sqrt(sum(x*x for x in self._ctx2value.values()))


    def normalized(self):
        r"""Return a normalized version of `self`.
        If `self.is_zero()`, returns another zero vector.
        """
        if self.is_zero(): return self
        return self.scaled_by(1 / self.abs())


    def scaled_by(self, scaling_value):
        r"""Return a version of `self` where every value
        is scaled by `scaling_value`.
        """
        new_ctx2value = collections.OrderedDict((k, x * scaling_value)
                for (k, x) in self._ctx2value.items())
        return EmbeddingVector(new_ctx2value)
