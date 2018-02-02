#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# measuring.py is part of mwetoolkit
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
This module provides measuring/evaluation classes.
These classes allow for easy data collection and calculation of
standard statistical measures, such as Precision and Recall.
"""








############################################################


class OneSidedComparison(object):
    r"""The result of a one-sided reference-vs-prediction MWE comparison.
    This is essentially a pair (NumberOfMatches, NumberOfAttempts), with
    an `add` operation that can be called on each match attempt.

    Example:
    >>> ose = OneSidedComparison(); ose
    OneSidedComparison((0, 0))
    >>> ose.add(1, 3); ose
    OneSidedComparison((1, 3))
    >>> ose.add(1, 2); ose
    OneSidedComparison((2, 5))
    >>> ose.evaluate_float()  # 2/5
    0.4
    """
    def __init__(self, _value=None):
        self.matches, self.attempts = _value or (0, 0)

    def add(self, num_matches, num_attempts):
        r"""Add (+num_matches / +num_attempts) to fraction."""
        self.matches += num_matches
        self.attempts += num_attempts

    def evaluate_float(self):
        r"""Evaluate fraction as a `float` instance."""
        if self.attempts == 0:
            return float('nan')
        return self.matches / self.attempts

    def __iter__(self):
        return iter((self.matches, self.attempts))

    def __repr__(self):
        return "OneSidedComparison({})".format(tuple(self))

    def __mul__(self, mul):
        return OneSidedComparison((mul * x for x in self))
    __rmul__ = __mul__

    def __add__(self, other):
        return OneSidedComparison((x + y for (x, y) in zip(self, other)))



class EvaluationResult(object):
    r"""The result of reference-vs-prediction corpus evaluation.
    
    Example:
    >>> er = EvaluationResult(); er
    EvaluationResult(((0, 0), (0, 0)))
    >>> er.prediction_comparison.add(1, 3); er
    EvaluationResult(((1, 3), (0, 0)))
    >>> er.prediction_comparison.add(1, 2); er
    EvaluationResult(((2, 5), (0, 0)))
    >>> er.precision()  # 2/5
    0.4
    >>> er.reference_comparison.add(4, 8); er
    EvaluationResult(((2, 5), (4, 8)))
    >>> er.recall()  # 4/8
    0.5
    >>> er = 2 * er; er
    EvaluationResult(((4, 10), (8, 16)))
    >>> er = er + EvaluationResult(((0, 0), (1, 1))); er
    EvaluationResult(((4, 10), (9, 17)))
    """
    def __init__(self, _values=None):
        p, r = _values or ((0, 0), (0, 0))
        self.prediction_comparison = OneSidedComparison(p)
        self.reference_comparison = OneSidedComparison(r)

    def get_one_sided_comparison(self, comp_type):
        r"""Return a OneSidedComparison for comp_type 'P' or 'R'."""
        if comp_type == "P": return self.prediction_comparison
        if comp_type == "R": return self.reference_comparison
        assert False, "comp_type must be one of {P, R}"

    def precision(self):
        r"""Return the precision (aka Positive Predictive Value)."""
        return self.prediction_comparison.evaluate_float()

    def recall(self):
        r"""Return the recall (aka True Positive Rate)."""
        return self.reference_comparison.evaluate_float()

    def f_measure(self):
        r"""Return the harmonic mean of [precision, recall]."""
        p, r = self.precision(), self.recall()
        return 2*p*r / (p+r)

    def __repr__(self):
        return "EvaluationResult({})".format(
                tuple(tuple(x) for x in self))

    def __iter__(self):
        return iter((self.prediction_comparison, self.reference_comparison))

    def __mul__(self, mul):
        return EvaluationResult((mul * x for x in self))
    __rmul__ = __mul__

    def __add__(self, other):
        return EvaluationResult((x + y for (x, y) in zip(self, other)))
