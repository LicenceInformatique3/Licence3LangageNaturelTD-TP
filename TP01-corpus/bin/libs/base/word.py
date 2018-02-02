#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# word.py is part of mwetoolkit
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
    This module provides the `Word` class. This class represents an orthographic
    word (as in mwetoolkit-corpus.dtd, mwetoolkit-patterns.dtd and 
    mwetoolkit-candidates.dtd) defined by a surface form, a lemma and a POS tag.
"""






from .feature import FeatureSet

# List of valid word attributes. Must appear in the same order as the
# arguments for the Word class constructor.
WORD_ATTRIBUTES = ["surface", "lemma", "pos", "syn"]
# Characters internally used as attribute and word separators.
# Must not appear in the corpus, neither as a word, nor as POS tag etc!
# The probability is minimal but it is nevertheless important to warn you
# about it! Each separator must be a single character.
ATTRIBUTE_SEPARATOR = "\35"  # ASCII level 2 separator
WORD_SEPARATOR = "\34"       # ASCII level 1 separator
SEPARATOR = ATTRIBUTE_SEPARATOR

def _traditional_prop(propname):
    def fget(word):
        return word.get_prop(propname, "")
    def fset(word, value):
        return word.set_prop(propname, value)
    def fdel(word):
        return word.del_prop(propname)
    return property(fget, fset, fdel)


_raise_if_missing=object()


################################################################################

class Word(object):
    """
        An orthographic word (in languages for which words are separated from 
        each other by a space) is the simplest lexical unit recognisable by a
        native speaker, and it is characterized by its surface form, its lemma 
        and its Part Of Speech tag.
    """
    __slots__ = ("ctxinfo", "_props", "_freqs")


    def __init__(self, ctxinfo, props):
        """
            Instantiates a new `Word`. A Word might be one of: a token in a 
            corpus, in which case it will probably have at least a defined 
            surface form (mwetoolkit-corpus.dtd); a part of a reference or
            gold standard entry, in which case it will have at least a defined
            lemma (mwetoolkit-patterns.dtd); a part of an n-gram
            in a candidates list, in which case most of the parts should be
            defined (mwetoolkit-candidates.dtd). Besides the surface form, the
            lemma and the Part Of Speech tag, a word also contains a list of
            `Frequency`ies, each one corresponding to its number of occurrences 
            in a given corpus.
            
            @param surface: A string corresponding to the surface form of the
            word, i.e. the form in which it occurs in the corpus. A surface form
            might include morphological inflection such as plural and gender
            marks, conjugation for verbs, etc. For example, "went", "going", 
            "go", "gone", are all different surface forms for a same lemma, the
            verb "(to) go".
            
            @param lemma: A string corresponding to the lemma of the word, i.e.
            the normalized non-inflected form of the word. A lemma is generally
            the preferred simplest form of a word as it appears in a dictionary,
            like infinitive for verbs or singular for nouns. Notice that a lemma
            is a well formed linguistic word, and thus differs from a root or
            a stem. For example, the lemma of the noun "preprocessing" is
            "preprocessing" while the root (without prefixes and suffixes) is
            "process". Analagously, the lemma of the verb "studied" is "(to) 
            study" whereas a stem would be "stud-", which is not an English
            word.
            
            @param pos: A string corresponding to a Part Of Speech tag of the 
            word. A POS tag is a morphosyntactic class like "Noun", "Adjective"
            or "Verb". You should use a POS tagger system to tag your corpus
            before you use mwetoolkit. The tag set, i.e. the set of valid POS
            tags, is your choice. You can use a very simple set that 
            distinguishes only top-level classes ("N", "A", "V") or a fine-
            grained classification, e.g. "NN" is a proper noun, "NNS" a proper
            noun in plural form, etc.

            @param syn: A string corresponding to a syntax information of the
            word. AS the jungle of syntactic formalisms is wild, we assume that
            each word has a string that encodes the syntactic information. If
            you use a dependency parser, for instance, you might encode the
            syntax information as "rel:>index" where "rel" is the type of
            syntactic relation (object, subject, det, etc.) and the "index" is
            the index of the word on which this word depends. An example can be
            found in the corpus DTD file.
            
            @param freqs: A dict of `corpus_name`->`Frequency` corresponding to counts of 
            occurrences of this word in a certain corpus. Please notice that
            the frequencies correspond to occurrences of a SINGLE word in a 
            corpus. Joint `Ngram` frequencies are attached to the corresponding 
            `Ngram` object that contains this `Word`, if any.

            @param props: A dict of `@key -> value` pairs.
            Example pairs:
            -- ("lemma", "walk")
            -- ("@connl:coarse_postag", "V")
        """
        # Callers must get rid of empty entries beforehand:
        assert (propval for propval in props.values()), props

        self.ctxinfo = ctxinfo
        self._props = props


################################################################################

    def get_props(self):
        r"""Get a dict of all properties."""
        return self._props.copy()

    def get_prop(self, prop_name, default=_raise_if_missing):
        r"""Retrieve a word prop (such as "lemma" or "@coarse_pos")."""
        try:
            return self._props[prop_name]
        except KeyError:
            global _raise_if_missing
            if default is _raise_if_missing: raise
            return default

    def set_prop(self, prop_name, value):
        r"""Assign a word prop (such as "lemma" or "@coarse_pos")."""
        if not value:
            self.del_prop(prop_name)
        else:
            self._props[prop_name] = value

    def del_prop(self, prop_name):
        r"""Delete a word prop (such as "lemma" or "@coarse_pos")."""
        try:
            del self._props[prop_name]
        except KeyError:
            pass  # Missing key; we don't care

    def has_prop(self, prop_name):
        r"""Return True iff word has prop (such as "lemma" or "@coarse_pos")."""
        try:
            self.get_prop(prop_name)
        except KeyError:
            return False
        return True


################################################################################

    lemma = _traditional_prop("lemma")
    surface = _traditional_prop("surface")
    pos = _traditional_prop("pos")
    syn = _traditional_prop("syn")

    @property
    def freqs(self):
        try:
            return self._freqs
        except AttributeError:
            self._freqs = FeatureSet("freq", lambda x,y: x+y)
            return self._freqs


################################################################################

    def keep_only_props(self, prop_set):
        r"""Delete all properties that are not in `prop_set`."""
        for propname in tuple(self._props):
            if propname not in prop_set:
                del self._props[propname]


################################################################################

    def copy(self):
        r"""Return a copy of this Word."""
        word = Word(self.ctxinfo, self._props.copy())
        try:
            word._freqs = self._freqs.copy()
        except AttributeError:
            pass  # Just don't assign a _freqs
        return word


################################################################################

    def lemma_or_surface(self):
        r"""Return lemma if it is defined; otherwise, return surface."""
        return self.lemma or self.surface

################################################################################

    def add_frequency( self, freq ) :
        """
            Add a `Frequency` to the list of frequencies of the word.
            
            @param freq `Frequency` that corresponds to a count of this word in 
            a corpus. No test is performed in order to verify whether this is a 
            repeated frequency in the list.
        """
        self.freqs.add(freq.name, freq.value)

################################################################################
            
    def to_string( self ) :
        """
            Converts this word to an internal string representation where each           
            part of the word is separated with a special `SEPARATOR`. This is 
            only used internally by the scripts and is of little use to the
            user because of reduced legibility. Deconversion is made by the 
            function `from_string`.
            
            @return A string with a special internal representation of the 
            word.
        """
        return SEPARATOR.join((self.surface, self.lemma, self.pos))
                
################################################################################
            
    def from_string( self, s ) :
        """ 
            Instanciates the current word by converting to an object 
            an internal string representation where each part of the word is 
            separated with a special `SEPARATOR`. This is only used internally 
            by the scripts and is of little use to the user because of reduced 
            legibility. Deconversion is made by the function `to_string`.
            
            @param s A string with a special internal representation of
            the word, as generated by the function `to_string`
        """
        [ self.surface, self.lemma, self.pos ] = s.split( SEPARATOR )
        
################################################################################

    def to_html( self, wid ) :
        """
            TODO
            @return TODO
        """
        # TODO: properly escape this stuff
        wtempl = "<a href=\"#\" class=\"word\">%(surface)s" \
                 "<span class=\"wid\">%(wid)d</span>" \
                 "<span class=\"lps\">%(lemma)s%(pos)s%(syn)s</span></a>"
        attr_map = [(x, self.__html_templ(x)) for x in WORD_ATTRIBUTES] + [("wid", wid)]
        return wtempl % dict(attr_map)

    def __html_templ(self, attrname):
        try:
            value = self.get_prop(attrname)
        except KeyError:
            return ""
        else:
            return "<span class=\"%s\">%s</span>" % (attrname, value)


################################################################################

    def to_corenlp(self, fallback_ctxinfo):
        from xml.etree import ElementTree
        ctxinfo = self.ctxinfo or fallback_ctxinfo
        props = self.get_props()
        token = ElementTree.Element('token', {'id': props['id']})
        token.tail = '\n\t'
        token.text = '\n\t\t'

        # create subelements containing word info
        for attribute, value in list(props.items()):
            if value and attribute != 'xml' and attribute != 'id':
                el = ElementTree.Element(attribute)
                el.text = value
                el.tail = '\n\t\t'
                token.append(el)
        ctxinfo.check_all_popped(props)
        return ElementTree.tostring(token)

################################################################################


################################################################################

    def __hash__(self):
        return hash(frozenset(self.get_props()))

    def __eq__(self, other) :
        return self.get_props() == other.get_props()

    def cmpkey_heavy(self, other) :
        r"""Key that can be used to compare two words when surface/lemma/pos is not enough."""
        return list(sorted(self._props.items()))

    @staticmethod
    def wordlist_lt(wordlist_a, wordlist_b):
        r"""Useful method for sorting two word lists.

        Prioritizes:
        1) Surface forms
        2) Word-list length
        3) Lemma
        4) POS
        5) Other word properties, in sorted order
        """
        for key in ["surface", "lemma", "pos"]:
            for w_a, w_b in zip(wordlist_a, wordlist_b):
                v_a, v_b = w_a.get_prop(key), w_b.get_prop(key)
                if v_a != v_b:
                    return v_a < v_b
            # If all surfaces are equal and one list is longer, sort by length:
            if len(wordlist_a) != len(wordlist_b):
                return len(wordlist_a) < len(wordlist_b)
            # Shortcut, as identical ngrams should be more
            # common than differences in lemma & friends:
            if key == "surface" and wordlist_a == wordlist_b:
                return False

        cmpkeys_a = [w.cmpkey_heavy() for w in wordlist_a]
        cmpkeys_b = [w.cmpkey_heavy() for w in wordlist_b]
        return cmpkeys_a < cmpkeys_b


################################################################################

    def wc_length( self ) :
        """
            Returns the number of characters in a word. Chooses upon available
            information, in priority order surface > lemma > pos.

            @return The number of characters in this word. Zero if this is an
            empty word (or all fields are wildcards)
        """
        return len(self.get_prop("surface", None)
                or self.get_prop("lemma", None)
                or self.get_prop("pos", ""))

################################################################################

    # XXX DECPRECATED, do we need this method? Also: `self` is not used
    def compare( self, s1, s2, ignore_case ) :
        """
            Compares two strings for equality conditioning the type of
            comparison (case sensitive/insensitive) to boolean argument
            `ignore_case`.

            @param s1 A string to compare.

            @param s2 Another string to compare.

            @param ignore_case True if comparison should be case insensitive,
            False if comparision should be case sensitive.

            @return True if the strings are identical, False if they are
            different.
        """
        if ignore_case :
            return s1.lower() == s2.lower()
        else :
            return s1 == s2

################################################################################

    # XXX DEPRECATED
    # XXX (Will be removed soon)
    def match( self, w, ignore_case=False, lemma_or_surface=False ) :
        """
            A simple matching algorithm that returns true if the parts of the
            current word match the parts of the given word. The matching at the 
            word level considers only the parts that are defined, for example, 
            POS tags for candidate extraction or lemmas for automatic gold 
            standard evaluation. A match on a part of the current word is True 
            when this part equals to the corresponding part of `w` or when the 
            part of the current word is not defined.
            All the three parts (surface, lemma and pos) need to match so that
            the match of the word is true. If ANY of these three word parts does
            not match the correspondent part of the given word `w`, this 
            function returns False.
            
            @param w A `Word` against which we would like to compare the current 
            word. In general, the current word contains the `WILDCARD`s while 
            `w` has all the parts (surface, lemma, pos) with a defined value.
            
            @return Will return True if ALL the word parts of `w` match ALL
            the word parts of the current pattern (i.e. they have the same 
            values for all the defined parts). Will return False if
            ANY of the three word parts does not match the correspondent part of 
            the given word `w`.
        """

        if self.pos and not self.compare(self.pos, w.pos, ignore_case):
            return False

        if lemma_or_surface:
            return ((self.compare(self.lemma, w.lemma, ignore_case)
                 or (self.compare(self.lemma, w.surface, ignore_case))
                 or (self.compare(self.surface, w.lemma, ignore_case))
                 or (self.compare(self.surface, w.surface, ignore_case))))
                  
        else:
            return ((not self.surface or self.compare(self.surface, w.surface, ignore_case))
                  and (not self.lemma or self.compare(self.lemma, w.lemma, ignore_case)))


        #return ((self.surface != WILDCARD and self.compare( self.surface,w.surface,ignore_case)) or \
        #     self.surface == WILDCARD) and \
        #     ((self.lemma != WILDCARD and self.compare( self.lemma, w.lemma, ignore_case ) ) or \
        #     self.lemma == WILDCARD) and \
        #     ((self.pos != WILDCARD and self.compare( self.pos, w.pos, ignore_case ) ) or \
        #     self.pos == WILDCARD)

            
################################################################################

    def get_case_class( self, s_or_l="surface" ) :
        """
            For a given word (surface form), assigns a class that can be:        
            * lowercase - All characters are lowercase
            * UPPERCASE - All characters are uppercase
            * Firstupper - All characters are lowercase except for the first
            * MiXeD - This token contains mixed lowercase and uppercase characters
            * ? - This token contains non-alphabetic characters
            
            @param s_or_l Surface or lemma? Default value is "surface" but set it
            to "lemma" if you want to know the class based on the lemma.

            @return A string that describes the case class according to the list 
            above.
        """
        try:
            form = self.get_prop(s_or_l)
        except KeyError:
            token_list = []
        else:
            token_list = list(form)
        case_class = "?"
        for letter_i in range( len( token_list ) ) :
            letter = token_list[ letter_i ]
            if letter.isupper() :
                if letter_i > 0 :
                    if case_class == "lowercase" or case_class == "Firstupper" :
                        case_class = "MiXeD"
                    elif case_class == "?" :
                        case_class = "UPPERCASE"    
                else :
                    case_class = "UPPERCASE"                
            elif letter.islower() :
                if letter_i > 0 :                
                    if case_class == "UPPERCASE" :
                        if letter_i == 1 :
                            case_class = "Firstupper"
                        else :
                            case_class = "MiXeD"
                    elif case_class == "?" :
                        case_class = "lowercase"
                else :
                    case_class = "lowercase"
        return case_class    
    
################################################################################      

    def get_freq_value( self, freq_name ) :
        """
            Returns the value of a `Frequency` in the frequencies list. The 
            frequency is identified by the frequency name provided as input to 
            this function. If two frequencies have the same name, only the first 
            value found will be returned.
            
            @param freq_name A string that identifies the `Frequency` of the 
            candidate for which you would like to know the value.
            
            @return Value of the searched frequency. If there is no frequency 
            with this name, then it will return 0.
        """
        for freq in self.freqs :
            if freq.name == freq_name :
                return freq.value
        return 0     

################################################################################      

    def syn_iter(self, fallback_ctxinfo):
        r"""Yield pairs (synrel, index) based on `self.syn`."""
        ctxinfo = self.ctxinfo or fallback_ctxinfo
        if self.syn:
            for syn_pair in self.syn.split(";"):
                try:
                    a, b = syn_pair.split(":")
                except ValueError:
                    ctxinfo.warn("Bad colon-separated syn pair: {pair!r}", pair=syn_pair)
                else:
                    try:
                        b = int(b) - 1
                    except ValueError:
                        ctxinfo.warn("Bad syn index reference: {index!r}", index=b)
                    else:
                        yield (a, b)

################################################################################      

    @staticmethod
    def syn_encode(syn_pairs):
        r"""Return a representation of the
        list of (synrel, index) pairs `syn_pairs`.
        The result can be assigned to a Word's `syn` attribute.
        """
        return ";".join("{}:{}".format(rel, index+1)
                for (rel, index) in syn_pairs)
