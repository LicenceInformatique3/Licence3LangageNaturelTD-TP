#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_ucs.py is part of mwetoolkit
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
"UCS" data set format. Since UCS works only with pairs (2-grams),
all ngrams with sizes other than 2 are discarded.

You should use the methods in package `filetype` instead.
"""






from . import _common as common
from .. import util

################################################################################


class UCSInfo(common.FiletypeInfo):
    description = "UCS 2-gram filetype format"
    filetype_ext = "UCS"

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("/", "${slash}"), (" ", "${space}"),
            ("\t", "${tab}"), ("\n", "${newline}"), ("#", "${hash}")
    ])

    def operations(self):
        return common.FiletypeOperations(UCSChecker, None, UCSPrinter)

INFO = UCSInfo()

################################################################################

class UCSChecker(common.AbstractChecker):
    r"""Checks whether input is in UCS format."""
    def matches_header(self, strict):
        return not strict

################################################################################

class UCSPrinter(common.AbstractPrinter):
    valid_categories = ["candidates"]

    def __init__(self, ctxinfo, category, freq_source=None,
            lemmapos=False, surface_instead_lemmas=False, **kwargs):
        super(UCSPrinter, self).__init__(ctxinfo, category)
        self.freq_source = freq_source
        self.lemmapos = lemmapos
        self.surface_instead_lemmas = surface_instead_lemmas


    def handle_meta(self, meta, ctxinfo):
        """Print the header for the UCS dataset file,
        and save the corpus size."""
        string_cand = "id\tl1\tl2\tf\tf1\tf2\tN"

        #for cs in meta.corpus_sizes :
        #    string_cand = string_cand + cs.name + "\t"
        #string_cand = string_cand + "occurs\tsources\t"

        #for cs in meta.meta_tpclasses :
        #    string_cand = string_cand + cs.name + "\t"
        #for cs in meta.meta_feats :
        #    string_cand = string_cand + cs.name + "\t"  
        xml_meta = meta
        self.corpus_size = self.freq_value(ctxinfo, xml_meta.corpus_sizes)
        self.add_string(ctxinfo, string_cand, "\n")
       

    def handle_candidate(self, entity, ctxinfo):
        """Print each `Candidate` as a UCS data set entry line.
        @param entity: The `Candidate` that is being read from the XML file.
        """
        string_cand = ""
        if entity.id_number >= 0 :
            string_cand += str( entity.id_number )
        string_cand = string_cand.strip() + "\t"    
        
        if len(entity) != 2:
            ctxinfo.warn("Ignoring entity %s, of length %d!=2" % (entity.id_number, len(entity)))
            return

        for w in entity :
            if self.lemmapos :
                string_cand += self.escape(w.lemma) + "/" + self.escape(w.pos) + "\t"
            elif w.has_prop("lemma") and not self.surface_instead_lemmas :
                string_cand += w.lemma + "\t"
            else :
                string_cand += w.surface + "\t"
        string_cand += "%f\t" % self.freq_value(ctxinfo, entity.freqs)

        for w in entity:
            try:
                string_cand += "%f\t" % self.freq_value(ctxinfo, w.freqs)
            except:
                string_cand += "0\t"
                ctxinfo.warn("Word frequency information missing for"\
                            " entity %d" % entity.id_number)
        string_cand += str(self.corpus_size)
        self.add_string(ctxinfo, string_cand, "\n")


    def freq_value(self, ctxinfo, items):
        """Given a list of items with a `name` and a `value` attribute, return
        the item whose name is the same as that of `freq_source`.
        """
        for item in items:
            if self.freq_source is None or item.name == self.freq_source:
                return item.value

        ctxinfo.warn("Frequency source '%s' not found!" % self.freq_source)
        return 0

