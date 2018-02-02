#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_csv.py is part of mwetoolkit
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
"CSV" filetype, which is useful when exporting data to Office spreadsheet and
related formats

You should use the methods in package `filetype` instead.
"""






from . import _common as common

################################################################################


class CSVInfo(common.FiletypeInfo):
    description = "Tab-separated CSV filetype format, one field per column"
    filetype_ext = "CSV"
    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), ("/", "${slash}"),
            (" ", "${space}"), (";", "${semicolon}"),
            # TODO: fix problems when coloring at view.py;
            # this won't be easy, as ";" can appear repeatedly
            ("\t", "${tab}"), ("\n", "${newline}"),
            ("#", "${hash}")
    ])

    def operations(self):
        return common.FiletypeOperations(CSVChecker, None, CSVPrinter)

INFO = CSVInfo()

################################################################################

class CSVChecker(common.AbstractChecker):
    r"""Checks whether input is in CSV format."""
    def matches_header(self, strict):
        return not strict

################################################################################

class CSVPrinter(common.AbstractPrinter):
    valid_categories = ["candidates"]

    def __init__(self, ctxinfo, category, sep="\t",
            surfaces=False, lemmapos=False, **kwargs):
        super(CSVPrinter, self).__init__(ctxinfo, category, **kwargs)
        self.sep = sep
        self.surfaces = surfaces
        self.lemmapos = lemmapos

    def handle_meta(self, meta, ctxinfo):
        """When the `Meta` header is read, this function generates a
        corresponding header for the CSV file. The header includes name of the
        fields, including fixed elements like the candidate n-gram and POS
        sequence, as well as variable elements like TPClasses and feature names

        @param meta: The `Meta` header that is being read from the file.
        @param ctxinfo: Any extra information as a dictionary
        """
        # ORDER OF ELEMENTS IN META DETERMINES ORDER OF EACH CANDIDATES' COLUMNS
        # RELATED TO MWE BOOK BUG - TABLE WITH ASSOCIATION MEASURES
        # CHECK YVES BESTGEN's EMAIL
        headers = ["id", "ngram", "pos"]
        self.corpus_sizes_order = [x.name for x in meta.corpus_sizes]
        headers.extend(self.escape(cs.name) for cs in meta.corpus_sizes)
        headers.extend(["occurs", "sources"])
        self.tpclasses_order = [x.name for x in meta.meta_tpclasses]
        headers.extend(self.escape(cs.name) for cs in meta.meta_tpclasses)
        self.feats_order = [x.name for x in meta.meta_feats]
        headers.extend(self.escape(cs.name) for cs in meta.meta_feats)
        self.add_string(ctxinfo, self.sep.join(headers), "\n")

    def handle_candidate(self, candidate, ctxinfo):
        """
            For each `Candidate`,

            @param entity: `Candidate` being read from the file
        """
        values = [str(candidate.id_number)]
        ngram_list = [self._ngram_list(x) for x in candidate]
        
        values.append(" ".join(ngram_list))
        values.append("" if self.lemmapos else " ".join([x.pos for x in candidate]))
        ordered_freqs = [candidate.get_freq_value(fname) for fname in self.corpus_sizes_order]
        values.extend(str(freq) for freq in ordered_freqs)
        sorted_tpclasses = [candidate.get_tpclass_value(fname) for fname in self.tpclasses_order]
        values.extend(str(tpclass) for tpclass in sorted_tpclasses)
        values.append(";".join([" ".join([y.surface for y in x]) for x in candidate.occurs]))
        values.append(";".join([";".join(map(str,o.sources)) for o in candidate.occurs]))
        ordered_feats = [candidate.get_feat_value(fname) for fname in self.feats_order]
        values.extend(str(feat) for feat in ordered_feats)
        self.add_string(ctxinfo, self.sep.join(values), "\n")


    def _ngram_list(self, x):
        if self.lemmapos:
            return "{}/{}".format(self.escape(x.lemma), self.escape(x.pos))
        elif self.surfaces or (not x.has_prop("lemma")):
            return self.escape(x.surface)
        return self.escape(x.lemma)
