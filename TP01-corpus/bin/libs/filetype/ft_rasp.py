#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_rasp.py is part of mwetoolkit
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
"RASP" filetype, which is generated by the RASP parser.

You should use the methods in package `filetype` instead.
"""






import os
from subprocess import Popen, PIPE

from . import _common as common
from ..base.sentence import SentenceFactory
from ..base.word import Word
from .. import util


################################################################################

class RaspInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for RASP."""
    description = "RASP parser format with grammatical relations"
    filetype_ext = "RASP"

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"), (":", "${colon}"), ("|", "${pipe}"),
            ("#", "${hash}"), ("_", "${underscore}"), (" ", "${space}"), 
            ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(RaspChecker,
                RaspParser, RaspPrinter)

INFO = RaspInfo()
                
################################################################################

class RaspChecker(common.AbstractChecker):
    r"""Checks whether input is in RASP format."""
    def matches_header(self, strict):
        header = self.fileobj.peek(512)
        for line in header.split(b"\n"):
            if not line.startswith(util.utf8_unicode2bytes(
                    self.filetype_info.comment_prefix)):
                return (line.startswith(b"(") and line.endswith(b")")) or \
                       line == b"gr-list: 1"
        return not strict

################################################################################

class RaspParser(common.AbstractTxtParser):
    r"""Instances of this class parse the RASP format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["corpus"]

    def __init__(self, morphg_file=None, morphg_folder=None, rasp_version=2, 
                       encoding='utf-8'):
        super(RaspParser,self).__init__(encoding)
        self.sentence_factory = SentenceFactory()
        self.category = "corpus"
        self.in_gr = False
        self.in_ignored = False
        self.morphg_file = morphg_file
        self.morphg_folder = morphg_folder
        self.indices = {}
        self.rasp_version = rasp_version


    def _parse_line(self, line, ctxinfo):
        if line == "gr-list: 1" :
            self.in_gr = True  
            self.rasp_version = 3
        elif len(line.strip()) == 0 :
            self.in_ignored = False 
            if self.rasp_version == 3 : # version 3, can have several blank lines
                self.in_gr = False
            else : # version 2, blank line can be init of gr-list
                self.in_gr = not self.in_gr
        elif line.startswith("(X") :
            ctxinfo.warn("Long sentence not previously parsed by RASP (-w limit was specified)")
            self.in_ignored = True                                    
        elif self.in_gr and not self.in_ignored :
            self._parse_gr( line, ctxinfo )
        elif not self.in_ignored : # not in_gr, main sentence word list                
            self.indices = {}            
            self.new_partial(self.handler.handle_sentence,
                             self.sentence_factory.make(), ctxinfo=ctxinfo)
            self._parse_sent( line, ctxinfo )
        # Else, ignore until blank line        
        
        
    def _parse_gr(self, line, ctxinfo) :
        parts = line.replace(" _", "").replace("(", "").replace(")", "").split(" ")
        rel = ""
        members = []
        for part in parts :
            if ":" not in part :
                if rel == "" : 
                    rel = part.replace("|","")
                else :
                    rel = rel + "_" + part.replace("|","")
            else:
                members.append(part)
        if len(members) >= 1 : # simple property: passive, have_to, etc.   
            syn = rel
            if len(members) >= 2:    # binary (typical) dependency relation                 
                # This line below converts RASP's token IDs into token positions in
                # moses format. This is required because sometimes RASP skips words
                # and assigns e.g. 1 2 4 5, so dependency 2->4 should be converted
                # into 2->3 in new sentence 1 2 3 4.        
                syn = rel + ":" + self._get_shifted_index(members[0], ctxinfo)
                if len(members) == 3 :
                    syn += ";" + rel + ":" + self._get_shifted_index(members[1], ctxinfo)
            son_index = self._get_shifted_index(members[-1], ctxinfo)                     
            try :
                entry = self.partial_args[0][int(son_index)-1]
            except IndexError:
                entry = None  
            if syn and entry :

                if entry.syn == "" :
                    entry.syn = syn
                else :
                    entry.syn += ";" + syn
        else :        
            ctxinfo.warn("Unrecognized grammatical relation `{relation}`", relation=line)


    def _get_shifted_index(self, token, ctxinfo) :
        return self.indices[int(self._parse_word(token, ctxinfo)[1])]
        

    def _parse_sent(self, line, ctxinfo) :
        wordtokens = line.split(" ")[:-3]                       #remove last 3 elements
        wordtokens = " ".join(wordtokens)[1:-1].split(" ")      # remove parentheses
        for (iwordtoken, wordtoken) in enumerate(wordtokens) :  #e.g.: resume+ed:7_VVN
            try :
                (prelemma, index, pos) = self._parse_word(wordtoken, ctxinfo)
                (surface, lemma, affix) = self._get_surface(prelemma, pos, ctxinfo)
                props = {"surface":surface, "lemma":lemma, "pos":pos, "@rasp:affix":affix}
                w = Word(ctxinfo, props)
                self.partial_args[0].append(w)
                self.indices[int(index)] = str(iwordtoken+1)
            except IndexError:
                ctxinfo.warn("Ignored word `{wordtoken}`", wordtoken=wordtoken)


    def _get_surface( self, lemma_morph, pos, ctxinfo ) :
        """
            Given a lemma+affix in RASP format, returns a tuple containing 
            (surface, lemma, affix). Uses morphg to generate the surface, or returns 2 
            copies of the input if morphg was not provided.
        """        
        affix = ""
        parts = lemma_morph.rsplit("+",1)
        if len(parts) == 1 or lemma_morph == "+": # No inflection, e.g. lemma_morph="+"
            lemma = surface = lemma_morph
        elif len(parts) == 2 and "+" not in parts[0]: # Standard inflected unit, e.g. lemma_morph="be+s"
            lemma, affix = parts
            if self.morphg_file is not None : 
                lemma_morph = lemma_morph.replace("\"","\\\"")                
                cmd = "echo \"%s_%s\" | ${morphg_res:-./%s -t}" % \
                      ( lemma_morph, pos, self.morphg_file )
                p = Popen(cmd, shell=True, stdout=PIPE).stdout
                #generates the surface form using morphg
                surface = str(p.readline(), self.encoding).split("_")[0]
                p.close()
            else:
                ctxinfo.warn_once("Not using morphg, using lemma+affix instead of surface")
                surface = lemma_morph
        else: # the token contains one or several '+', e.g. lemma_morph="C+++"
            lemma = surface = parts[0]
            affix = parts[1]
        return ( surface, lemma, affix )
        

    def _parse_word(self, token, ctxinfo) :
        """
            Given a string in RASP format representing a token like 
            "|resume+ed:7_VVN|" or "resume+ed\:7_VVN" (RASP 3), returns a tuple
            containing (lemma,index,pos). Lemma includes the +... morphological
            suffix.
        """
        ignore = False
        if token.startswith("|") and token.endswith("|") : # regular token
            token = token[1:-1]
        token_parts = token.rsplit( "_", 1 )
        if len(token_parts) == 2 :
            lemma_and_index, pos = token_parts
            lemma_parts =  lemma_and_index.rsplit( ":", 1 )
            if len(lemma_parts) == 2 :        
                lemma, index = lemma_parts
                if lemma.endswith("\\") :
                    lemma = lemma[:-1]                     # separator was \:            
            else :
                ignore = True
        else :
            ignore = True
        if ignore :
            ctxinfo.warn("Ignoring bad token `{token}`", token=token)
            return None
        else :        
            return (lemma, index, pos)


############################################################

class RaspPrinter(common.AbstractPrinter):
    valid_categories = ["corpus"]

    def handle_sentence(self, sentence, ctxinfo):
        if sentence.mweoccurs:
            ctxinfo.warn_once("Unable to represent MWEs in RASP format")

        self.add_string(ctxinfo, "(")
        for i, w in enumerate(sentence):
            if i != 0:
                self.add_string(ctxinfo, " ")
            self._print_word(ctxinfo, sentence, i)

        # XXX change these LOST_INFOs into actual numbers
        self.add_string(ctxinfo, ") LOST_INFO ; (LOST_INFO) \n\n")

        gr_printed = False
        for i, j, deprel in self._ordered_deprels(ctxinfo, sentence):
            self.add_string(ctxinfo, "(|", deprel, "| ")
            self._print_word(ctxinfo, sentence, j)
            self.add_string(ctxinfo, " ")
            self._print_word(ctxinfo, sentence, i)
            self.add_string(ctxinfo, ")\n")
            gr_printed = True

        # print the (X |w1| |w2| ...)
        if not gr_printed:
            self.add_string(ctxinfo, "(X")
            for i, w in enumerate(sentence):
                self.add_string(ctxinfo, " ")
                self._print_word(ctxinfo, sentence, i)
            self.add_string(ctxinfo, ")\n")

        self.add_string(ctxinfo, "\n\n")


    def _print_word(self, ctxinfo, sentence, i):
        r"""Print something like this string: "|lemma+s:42_NN|"."""
        w = sentence[i]
        try:
            lemma = w.get_prop("lemma")
            try:
                lemma_morph = lemma + "+" + w.get_prop("@rasp:affix")
            except KeyError:
                lemma_morph = lemma
        except KeyError:
            lemma_morph = w.get_prop("surface", "<?>")
        self.add_string(ctxinfo, "|", lemma_morph, ":", str(i+1),
                "_", w.get_prop("pos", ""), "|")


    def _ordered_deprels(self, ctxinfo, sentence):
        for i, wi in enumerate(sentence):
            for deprel, j in wi.syn_iter(ctxinfo):
                yield i, j, deprel
