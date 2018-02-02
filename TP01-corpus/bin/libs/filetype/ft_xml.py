#!/usr/bin/env python3
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_xml.py is part of mwetoolkit
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
This module provides classes to manipulate files that are
encoded in mwetoolkit's "XML" filetype.

You should use the methods in package `filetype` instead.
"""


import collections
import itertools
from xml.etree import ElementTree
import pyexpat as expat

from . import _common as common
from ..base.word import Word
from ..base.sentence import SentenceFactory
from ..base.candidate import Candidate, CandidateFactory
from ..base.entry import Entry
from ..base.mweoccur import MWEOccurrence
from ..base.ngram import Ngram
from ..base.frequency import Frequency
from ..base.feature import Feature
from ..base.tpclass import TPClass
from ..base.meta import Meta
from ..base.corpus_size import CorpusSize
from ..base.meta_feat import MetaFeat
from ..base.meta_tpclass import MetaTPClass
from ..base import patternlib
from .. import util



################################################################################


class XMLInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for mwetoolkit's XML."""
    description = "An XML in mwetoolkit format (dtd/mwetoolkit-*.dtd)"
    filetype_ext = "XML"

    # Used to escape (but not to unescape!) XML files
    escaper = common.Escaper("&", ";", [
        # We don't escape "&apos;", as it's useless and e.g. "walk&apos;s" is ugly :p
        ("&", "&amp;"), ("\"", "&quot;"), ("<", "&lt;"), (">", "&gt;"),
        ("\n", "&#10;"), ("\t", "&#9;")
    ])

    def operations(self):
        return common.FiletypeOperations(XMLChecker, XMLParser, XMLPrinter)


INFO = XMLInfo()

################################################################################

class XMLChecker(common.AbstractChecker):
    r"""Checks whether input is in XML format."""
    def matches_header(self, strict):
        header = self.fileobj.peek(300)
        if header.startswith(b"\xef\xbb\xbf"):
            header = header[3:]  # remove utf8's BOM
        return (header.startswith(b"<?xml")
                or header.startswith(b"<pattern")
                or header.startswith(b"<!--")) and not b'<root>' in header



################################################################################

XML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE {category} SYSTEM "dtd/mwetoolkit-{category}.dtd">
<!-- MWETOOLKIT: filetype="XML" -->
<{category} {ns}>"""

XML_FOOTER = """</{category}>"""


class XMLPrinter(common.AbstractPrinter):
    """Instances can be used to print XML objects."""
    valid_categories = ["dict", "corpus", "candidates", "patterns"]

    def __init__(self, ctxinfo, *args, **kwargs):
        super(XMLPrinter, self).__init__(ctxinfo, *args, **kwargs)
        self.serializer = XMLSerializer(
                self.add_string, self.filetype_info.escaper)
        self.add_string(ctxinfo, XML_HEADER.format(
                category=self._category, ns=""), "\n")
        self._printed_filetype_directive = True

    def finish(self, ctxinfo):
        self.add_string(ctxinfo, XML_FOOTER.format(
                category=self._category), "\n")
        super(XMLPrinter, self).finish(ctxinfo)

    def handle_comment(self, comment, ctxinfo):
        self.serializer.serialize(ctxinfo, comment)

    def handle_pattern(self, pattern, ctxinfo):
        self.serializer.serialize(ctxinfo, pattern)

    def _fallback(self, obj, ctxinfo):
        self.serializer.serialize(ctxinfo, obj)



XML_INDENT_LEVEL = 4

class XMLSerializer(common.ObjSerializer):
    r"""Instances can serialize objects into XML."""

    def serialize_Comment(self, ctxinfo, comment, indent=0):
        # XML does not demand escaping inside comments
        # (instead, they forbid the substring "--"... Pfff)
        comment_s = str(comment).replace("--", "–")
        self.add_string(ctxinfo, " "*indent,
                "<!-- ", comment_s, " -->\n")


    def serialize_Word(self, ctxinfo, word, indent=0):
        self.add_string(ctxinfo, "<w")
        props = word.get_props()

        for key in ("surface", "lemma", "pos", "syn"):
            try:
                value = props.pop(key)
            except KeyError:
                pass  # Just don't print it
            else:
                self.add_string(ctxinfo, " ", key, "=\"",
                        self.escape(value), "\"")

        if not word.freqs:
            self.add_string(ctxinfo, " />")
        else:
            self.add_string(ctxinfo, " >")
            self.serialize(ctxinfo, word.freqs, indent=0)
            self.add_string(ctxinfo, "</w>")
        ctxinfo.check_all_popped(props)


    def serialize_Candidate(self, ctxinfo, candidate, indent=0):
        subindent = indent + XML_INDENT_LEVEL
        subsubindent = indent + 2*XML_INDENT_LEVEL

        self.add_string(ctxinfo, "<cand candid=\"",
                str(candidate.id_number), "\">\n")
        self.serialize_Ngram(ctxinfo, candidate, indent=subindent)

        if candidate.bigrams:
            self.add_string(ctxinfo, " "*subindent, "<bigram>\n")
            for bigram in self.bigrams :
                self.serialize(ctxinfo, bigram, indent=subsubindent)
                self.add_string(ctxinfo, "\n")
            self.add_string(ctxinfo, " "*subindent, "</bigram>\n")

        if candidate.occurs:
            self.add_string(ctxinfo, " "*subindent, "<occurs>\n")
            for mweoccur in candidate.occurs:
                # TODO adapt to use subsubindent (need to fix tests)
                self.serialize(ctxinfo, mweoccur, indent=subindent)
            self.add_string(ctxinfo, " "*subindent, "</occurs>\n")

        if candidate.vars:
            self.add_string(ctxinfo, " "*subindent, "<vars>\n")
            for var in self.vars:
                self.serialize(ctxinfo, var, indent=subsubindent)
            self.add_string(ctxinfo, " "*subindent, "</vars>\n")

        if candidate.features:
            self.add_string(ctxinfo, " "*subindent, "<features>\n")
            self.serialize(ctxinfo, candidate.features,
                    indent=subsubindent, after_each="\n")
            self.add_string(ctxinfo, " "*subindent, "</features>\n")

        if candidate.tpclasses:
            self.serialize(ctxinfo, candidate.tpclasses,
                    indent=subindent, after_each="\n")

        self.add_string(ctxinfo, "</cand>\n")


    def serialize_Sentence(self, ctxinfo, sentence, indent=0):
        subindent = indent + XML_INDENT_LEVEL
        self.add_string(ctxinfo, "<s")
        if sentence.id_number is not None:
            self.add_string(ctxinfo, " s_id=\"",
                    str(sentence.id_number), "\"")
        self.add_string(ctxinfo, ">")

        for word in sentence.word_list:
            self.serialize(ctxinfo, word)
            self.add_string(ctxinfo, " ")

        if sentence.mweoccurs:
            self.add_string(ctxinfo, "\n<mweoccurs>\n")
            for mweoccur in sentence.mweoccurs:
                self.add_string(ctxinfo, "  ")  # TODO replace by subindent
                self.serialize(ctxinfo, mweoccur)
                self.add_string(ctxinfo, "\n")
            self.add_string(ctxinfo, "</mweoccurs>\n")
        self.add_string(ctxinfo, "</s>\n")


    def serialize_Entry(self, ctxinfo, entry, indent=0):
        subindent = indent + XML_INDENT_LEVEL
        subsubindent = indent + XML_INDENT_LEVEL
        self.add_string(ctxinfo, " "*indent, "<entry")
        if entry.id_number is not None:
            self.add_string(ctxinfo, " entryid=\"",
                    str(entry.id_number), "\"")
        self.add_string(ctxinfo, ">")
        self.helper_serialize_Ngram(ctxinfo, ngram, indent=indent)

        if entry.features:
            self.add_string(ctxinfo, " "*subindent, "<features>\n")
            self.serialize(ctxinfo, entry.features, indent=subsubindent)
            self.add_string(ctxinfo, " "*subindent, "</features>\n")
        self.add_string(ctxinfo, "</entry>\n")


    def serialize_Ngram(self, ctxinfo, ngram, indent=0):
        self.add_string(ctxinfo, " "*indent, "<ngram>")
        self.helper_serialize_Ngram(ctxinfo, ngram, indent=indent)
        self.add_string(ctxinfo, "</ngram>\n")


    def helper_serialize_Ngram(self, ctxinfo, ngram, indent=0):
        subindent = indent + XML_INDENT_LEVEL
        for word in ngram:
            self.serialize(ctxinfo, word, indent=subindent)
            self.add_string(ctxinfo, " ")

        self.serialize(ctxinfo, ngram.freqs, indent=0)

        if len(ngram.sources) > 0:
            sources_string = ';'.join(str(s) for s in ngram.sources)
            self.add_string(ctxinfo, '<sources ids="%s"/>' % sources_string)


    def serialize_Meta(self, ctxinfo, meta, indent=0):
        subindent = indent + XML_INDENT_LEVEL
        self.add_string(ctxinfo, "<meta>\n")
        self.serialize(ctxinfo, meta.corpus_sizes,
                indent=subindent, after_each="\n")
        for meta_feat in meta.meta_feats:
            self.serialize(ctxinfo, meta_feat, indent=subindent)
        for meta_tpclass in meta.meta_tpclasses:
            self.serialize(ctxinfo, meta_tpclass, indent=subindent)
        self.add_string(ctxinfo, "</meta>\n")


    def serialize_MetaFeat(self, ctxinfo, metafeat, indent=0):
        self.add_string(ctxinfo, " "*indent,
                "<", metafeat.xml_class, " name=\"",
                self.escape(metafeat.name), "\" type=\"",
                self.escape(metafeat.feat_type), "\" />\n")

    # XXX remove MetaTPClass? It's a glorified subclass of MetaFeat...
    serialize_MetaTPClass = serialize_MetaFeat


    def serialize_FeatureSet(self, ctxinfo, featset,
            indent=0, after_each=""):
        # Handle <feat>, <freq>, <tpclass>, <corpussize>
        for featname, value in sorted(featset._dict.items()):
            value = util.portable_float2str(value)
            self.add_string(ctxinfo, " "*indent, "<", featset._xml_class,
                    " name=\"", self.escape(featname), "\" value=\"",
                    self.escape(str(value)), "\" />", after_each)


    def serialize_MWEOccurrence(self, ctxinfo, mweoccur, indent=0):
        self.add_string(ctxinfo, "<mweoccur candid=\"",
                str(mweoccur.candidate.id_number), "\">")

        # For each (candidate index, sentence index)...
        for c_i, s_i in enumerate(mweoccur.indexes):
            self.add_string(ctxinfo, "<mwepart index=\"",
                    # use s_i+1 due to 1-based indexing
                    str(s_i + 1), "\"/>")
        self.add_string(ctxinfo, "</mweoccur>")


    def serialize_EitherPattern(self, ctxinfo, pattern, indent=0):
        """Format the either pattern into XML."""
        self.add_string(ctxinfo, " "*indent, '<either>\n')
        for subpattern in pattern.subpatterns:
            self.serialize(ctxinfo, subpattern,
                    indent=indent+XML_INDENT_LEVEL)
        self.add_string(ctxinfo, " "*indent, '</either>\n')


    def serialize_SequencePattern(self, ctxinfo, pattern, indent=0):
        """Format the sequence pattern into XML."""
        self.add_string(ctxinfo, " "*indent, "<pat")
        if pattern.seq_strid:
            self.add_string(ctxinfo, " id=\"",
                    self.escape(pattern.seq_strid), "\"")
        if pattern.ignore:
            self.add_string(ctxinfo, " ignore=\"true\"")
        if pattern.repeat:
            self.add_string(ctxinfo, " repeat=\"",
                    self.escape(pattern.repeat), "\"")
        self.add_string(ctxinfo, ">\n")
        for subpattern in pattern.subpatterns:
            self.serialize(ctxinfo, subpattern,
                    indent=indent+XML_INDENT_LEVEL)
        self.add_string(ctxinfo, " "*indent, '</pat>\n')


    def serialize_WordPattern(self, ctxinfo, pattern, indent=0):
        """Format the word pattern into XML."""
        self.add_string(ctxinfo, " "*indent, "<w")
        for k, values in sorted(pattern.positive_props.items()):
            if self.check_xml_pat_prop(ctxinfo, k):
                for v in values:
                    self.add_string(ctxinfo, " ", k, "=")
                    self.serialize(ctxinfo, v)
        self.add_string(ctxinfo, ">")

        for k, values in sorted(pattern.negative_props.items()):
            if self.check_xml_pat_prop(ctxinfo, k):
                for v in values:
                    self.add_string(ctxinfo, "<neg ", k, "=")
                    self.serialize(ctxinfo, v)
                    self.add_string(ctxinfo, "/>")
        self.add_string(ctxinfo, "</w>\n")


    def check_xml_pat_prop(self, ctxinfo, propname):
        if propname.startswith("["):  # Behave nicely with for view.py
            propname = propname.split("m", 1)[1]
        if propname.endswith("m"):  # Behave nicely with for view.py
            propname = propname.rsplit("", 1)[0]

        if propname in patternlib.CLASSICAL_PAT_PROPS:
            return True
        ctxinfo.warn("Skipping unsupported propname " \
                "`{propname}`", propname=propname)


    def serialize_RegexProp(self, ctxinfo, wordprop, indent=0):
        self.add_string(ctxinfo, "\"", self.escape(wordprop.value),
                "\" style=\"regex\"")
        if wordprop.flags:
            self.add_string(ctxinfo, " flags=\"{}\"".format(wordprop.flags))

    def serialize_StarredWildcardProp(self, ctxinfo, wordprop, indent=0):
        self.add_string(ctxinfo, "\"", self.escape(wordprop.value), "\"")
        if "*" in wordprop.value:
            self.add_string(ctxinfo, " style=\"starred-wildcard\"")

    def serialize_LiteralProp(self, ctxinfo, wordprop, indent=0):
        self.add_string(ctxinfo, "\"", self.escape(wordprop.value), "\"")
        if "*" in wordprop.value:
            self.add_string(ctxinfo, " style=\"literal\"")

    def serialize_BackrefProp(self, ctxinfo, wordprop, indent=0):
        self.add_string(ctxinfo, "\"back:", self.escape(wordprop.w_strid),
                ".", self.escape(wordprop.prop), "\"")





################################################################################

class XMLParser(common.AbstractParser):
    r"""Instances of this class parse the mwetoolkit XML format,
    calling the `handler` for each object that is parsed.
    """
    valid_categories = ["dict", "corpus", "candidates", "patterns"]


    def _parse_file(self):
        xmlparser = iter(IterativeXMLParser(self.inputobj, self))
        if not self.inputobj.peek_bytes(10).startswith(b"<?xml"):
            if b"\n<?xml" in self.inputobj.peek_bytes():
                # Python's XMLParser is unable to handle this, so we just give up
                self.latest_ctxinfo.error("XML tag <?xml> cannot appear after first line!")
            self.latest_ctxinfo.warn("XML file should start with <?xml> tag!")

        already_seen = []

        for xmlevent in xmlparser:
            if xmlevent.event_str == "start":
                already_seen.append(xmlevent)  # XXX MOVE ABOVE TEST FOR "start"
                if xmlevent.elem.tag != ElementTree.Comment:
                    if xmlevent.elem.tag == "dict":
                        delegate = self.parse_dict
                    elif xmlevent.elem.tag == "corpus":
                        delegate = self.parse_corpus
                    elif xmlevent.elem.tag == "candidates":
                        delegate = self.parse_candidates
                    elif xmlevent.elem.tag == "patterns":
                        delegate = self.parse_patterns
                    else:
                        self.ctxinfo.error("Bad top-level XML elem: {tag!r}" \
                                .format(tag=xmlevent.elem.tag))

                    self.inputobj.category = xmlevent.elem.tag
                    with common.ParsingContext(self):
                        it = itertools.chain(already_seen, xmlparser)
                        delegate(it)



    def unknown_end_elem(self, xmlevent):
        r"""Complain about unknown XML element."""
        if xmlevent.elem.tag == ElementTree.Comment:
            comment = common.Comment(xmlevent.elem.text.strip())
            self.handler.handle_comment(comment, xmlevent.ctxinfo)
        else:
            xmlevent.ctxinfo.warn("Ignoring unexpected XML elem: <{tag}>",
                    tag=xmlevent.elem.tag)


    #######################################################
    def _parse_wordelem2props(self, ctxinfo, elem):
        props = {}
        for key in ("surface", "lemma", "pos", "syn"):
            try:
                value = elem.attrib.pop(key)
            except KeyError:
                pass  # Input does not assign to this key
            else:
                if not value:
                    ctxinfo.warn('Ignoring empty attribute: {attr}=""', attr=key)
                else:
                    props[key] = value

        for key in elem.attrib:
            ctxinfo.warn("Invalid word attribute: {attr!r}", attr=key)
        return props



    #######################################################
    def parse_corpus(self, inner_iterator):
        sentence_factory = SentenceFactory()
        sentence = None

        for xmlevent in inner_iterator:
            if xmlevent.event_str == "start":
                if xmlevent.elem.tag == "s" :
                    s_id = None
                    if "s_id" in xmlevent.elem.attrib:
                        s_id = int(xmlevent.elem.get("s_id"))
                    sentence = sentence_factory.make(id_number=s_id)

                elif xmlevent.elem.tag == "mweoccur":
                    occur_cand = Candidate(int(xmlevent.elem.get("candid")))
                    new_occur = MWEOccurrence(sentence, occur_cand, [])
                    sentence.mweoccurs.append(new_occur)

            elif xmlevent.event_str == "end":
                if xmlevent.elem.tag == "s":
                    # A complete sentence was read, call the callback function
                    self.handler.handle_sentence(sentence, xmlevent.ctxinfo)

                elif xmlevent.elem.tag == "w":
                    props = self._parse_wordelem2props(xmlevent.ctxinfo, xmlevent.elem)
                    # Add word to the sentence that is currently being read
                    sentence.append(Word(xmlevent.ctxinfo, props))

                elif xmlevent.elem.tag == "mweoccurs":
                    pass  # This tag is just a wrapper around `mweoccur` tags
                elif xmlevent.elem.tag == "mweoccur":
                    pass  # Already created MWEOccurrence on `start` event

                elif xmlevent.elem.tag == "mwepart":
                    sentence.mweoccurs[-1].indexes.append(int(xmlevent.elem.get("index"))-1)

                elif xmlevent.elem.tag == "corpus":
                    return  # Finished processing
                else:
                    self.unknown_end_elem(xmlevent)
                xmlevent.elem.clear()



    #######################################################

    def parse_patterns(self, inner_iterator):
        for top_xmlevent in inner_iterator:
            assert top_xmlevent.event_str == "start"
            if top_xmlevent.elem.tag == "patterns":
                self.parse_until_closed(top_xmlevent, inner_iterator)
            else:
                self.unknown_end_elem(top_xmlevent)


    def parse_until_closed(self, outer_xmlevent, inner_iterator):
        def iter_until_closed(closing_tag):
            for sub_xmlevent in inner_iterator:
                if sub_xmlevent.event_str == "end":
                    if closing_tag == sub_xmlevent.elem.tag:
                        return  # Finished processing
                    else:
                        self.unknown_end_elem(sub_xmlevent)
                else:
                    assert sub_xmlevent.event_str == "start"
                    yield sub_xmlevent


        outer_elem = outer_xmlevent.elem
        if outer_elem.tag == "patterns":
            for sub_xmlevent in iter_until_closed(outer_elem.tag):
                if sub_xmlevent.elem.tag == "pat":
                    if self.check_subelem(inner_iterator,
                            sub_xmlevent, "patterns", ("pat",)):
                        p = self.parse_until_closed(sub_xmlevent, inner_iterator)
                        self.handler.handle_pattern(p, sub_xmlevent.ctxinfo)
            return


        elif outer_elem.tag == "pat":  # XXX Future `seq`?
            seq_strid = outer_elem.attrib.pop("id", None)
            seq_repeat = outer_elem.attrib.pop("repeat", None)
            seq_ignore = bool(outer_elem.attrib.pop("ignore", False))
            outer_xmlevent.check_empty()
            ret = patternlib.SequencePattern(outer_xmlevent.ctxinfo, seq_strid, seq_repeat, seq_ignore)
            for sub_xmlevent in iter_until_closed(outer_elem.tag):
                if self.check_subelem(inner_iterator, sub_xmlevent, "pat", ("pat", "either", "w")):
                    p = self.parse_until_closed(sub_xmlevent, inner_iterator)
                    ret.append_pattern(sub_xmlevent.ctxinfo, p)
            return ret.freeze()


        elif outer_elem.tag == "either":
            outer_xmlevent.check_empty()
            ret = patternlib.EitherPattern(outer_xmlevent.ctxinfo)
            for sub_xmlevent in iter_until_closed(outer_elem.tag):
                p = self.parse_until_closed(sub_xmlevent, inner_iterator)
                ret.append_pattern(sub_xmlevent.ctxinfo, p)
            return ret.freeze()


        elif outer_elem.tag == "w":
            w_strid = outer_elem.attrib.pop("id", None)
            ret = patternlib.WordPattern(outer_xmlevent.ctxinfo, w_strid)

            match_style = outer_elem.attrib.pop("style", "")
            match_flags = outer_elem.attrib.pop("flags", "")
            for propname in patternlib.CLASSICAL_PAT_PROPS:
                if propname in outer_elem.attrib:
                    propval = outer_elem.attrib.pop(propname)
                    propval = self.propval2propobj(outer_xmlevent.ctxinfo,
                            propval, match_style, match_flags)
                    ret.add_prop(propname, propval, negated=False)
            outer_xmlevent.check_empty()

            for sub_xmlevent in iter_until_closed(outer_elem.tag):
                if self.check_subelem(inner_iterator, sub_xmlevent, "w", ("neg",)):
                    if sub_xmlevent.elem.tag == "neg":
                        match_style = outer_elem.attrib.pop("style", "")
                        match_flags = outer_elem.attrib.pop("flags", "")
                        for propname in patternlib.CLASSICAL_PAT_PROPS:
                            if propname in sub_xmlevent.elem.attrib:
                                propval = sub_xmlevent.elem.attrib.pop(propname)
                                propval = self.propval2propobj(sub_xmlevent.ctxinfo,
                                        propval, match_style, match_flags)
                                ret.add_prop(propname, propval, negated=True)
                        sub_xmlevent.check_empty()
                    self.parse_until_closed(sub_xmlevent, inner_iterator)
            return ret.freeze()


        else:
            for sub_xmlevent in inner_iterator:
                if (sub_xmlevent.event_str, sub_xmlevent.elem) == ("end", outer_elem):
                    break  # Finished skipping this elem



    def check_subelem(self, inner_iterator, sub_xmlevent, outer_elem_tag, valid_subelem_tags):
        r"""Check whether `sub_xmlevent.elem.tag` is a valid child under `elem_tag`."""
        if sub_xmlevent.elem.tag == ElementTree.Comment:
            self.parse_until_closed(sub_xmlevent, inner_iterator)
            self.unknown_end_elem(sub_xmlevent)
            return False

        if sub_xmlevent.elem.tag not in valid_subelem_tags:
            sub_xmlevent.ctxinfo.warn("Element <{tag}> does not allow sub-element " \
                    "<{subtag}>", tag=outer_elem_tag, subtag=sub_xmlevent.elem.tag)
            self.parse_until_closed(sub_xmlevent, inner_iterator)
            return False
        return True


    def propval2propobj(self, ctxinfo, propval, match_style, match_flags):
        r"""Return a regex version of `propval`."""
        if match_style not in ("regex", "literal", "", "starred-wildcard"):
            ctxinfo.warn("Unknown match-style `{style}`", style=match_style)

        if match_style == "regex":
            return patternlib.RegexProp(ctxinfo, propval, match_flags)
        if match_flags:
            ctxinfo.warn("Flags being ignored for match-style " \
                    "`{style}`", style=match_style or "starred-wildcard")
        if match_style == "literal":
            return patternlib.LiteralProp(ctxinfo, propval)

        if match_style == "":
            if propval.startswith("back:"):
                w_strid, prop = propval.split(":", 1)[1].split(".", 1)
                return patternlib.BackrefProp(ctxinfo, w_strid, prop)

            if not "*" in propval:
                return patternlib.LiteralProp(ctxinfo, propval)
        return patternlib.StarredWildcardProp(ctxinfo, propval)



    #######################################################
    def parse_candidates(self, inner_iterator):
        candidate_factory = CandidateFactory()
        candidate = None
        ngram = None
        in_bigram = False
        in_occurs = False
        in_vars = False
        word = None
        meta = None

        for xmlevent in inner_iterator:
            event_str, elem, ctxinfo = xmlevent

            if event_str == "start":
                if elem.tag == "cand":
                    # Get the candidate ID or else create a new ID for it          
                    id_number = None
                    if "candid" in elem.attrib:
                        id_number = elem.get("candid")
                    candidate = candidate_factory.make([], id_number=id_number)

                elif elem.tag == "ngram":
                    ngram = Ngram()

                elif elem.tag == "bigrams":
                    in_bigram = True
                elif elem.tag == "occurs" :
                    in_occurs = True
                elif elem.tag == "vars" :
                    in_vars = True

                elif elem.tag == "w":
                    props = self._parse_wordelem2props(ctxinfo, elem)
                    word = Word(ctxinfo, props)
                    # Add the word to the ngram that is on the stack
                    ngram.append(word)

                # Meta section and elements, correspond to meta-info about the
                # candidates lists. Meta-info are important for generating
                # features and converting to arff files, and must correspond
                # to the info in the candidates (e.g. meta-feature has the 
                # same elem.tag as actual feature)      
                elif elem.tag == "meta":
                    meta = Meta(None, None, None)


            elif event_str == "end":

                if elem.tag == "cand" :
                    # Finished reading the candidate, call callback
                    self.handler.handle_candidate(candidate, ctxinfo) 

                elif elem.tag == "ngram":
                    if in_occurs:
                        candidate.add_occur(ngram)
                    elif in_bigram:
                        candidate.add_bigram(ngram)
                    elif in_vars:
                        candidate.add_var(ngram)
                    else:
                        candidate.word_list = ngram.word_list
                        candidate.freqs = ngram.freqs

                elif elem.tag == "w":
                    # Set word to none, otherwise I cannot make the difference between
                    # the frequency of a word and the frequency of a whole ngram
                    word = None        

                elif elem.tag == "meta":
                    # Finished reading the meta header, call callback        
                    self.handler.handle_meta(meta, ctxinfo)

                elif elem.tag == "bigrams":
                    in_bigram = False
                elif elem.tag == "occurs":
                    in_occurs = False
                elif elem.tag == "vars":
                    in_vars = False


                elif elem.tag == "freq":
                    freq = Frequency(elem.get("name"),
                            int(elem.get("value")))
                    # If <freq> is inside a word element, then it's the word's
                    # frequency, otherwise it corresponds to the frequency of
                    # the ngram that is being read
                    if word is not None:
                        word.add_frequency(freq)            
                    else:
                        ngram.add_frequency(freq)

                elif elem.tag == "sources":
                    ngram.add_sources(elem.get("ids").split(';'))

                elif elem.tag == "feat":
                    feat_name = elem.get("name")
                    feat_value = elem.get("value")
                    feat_type = meta.get_feat_type(feat_name)
                    if feat_type == "integer":
                        feat_value = int(feat_value)
                    elif feat_type == "real":
                        feat_value = float(feat_value)                
                    f = Feature(feat_name, feat_value)
                    candidate.add_feat(f) 

                elif elem.tag == "tpclass" :
                    tp = TPClass(elem.get("name"), 
                                  elem.get("value"))
                    candidate.add_tpclass(tp)
                    
                elif elem.tag == "corpussize":
                    cs = CorpusSize(elem.get("name"), elem.get("value"))
                    meta.add_corpus_size(cs)
                elif elem.tag == "metafeat" :      
                    mf = MetaFeat(elem.get("name"), elem.get("type"))
                    meta.add_meta_feat(mf)  
                elif elem.tag == "metatpclass" :    
                    mtp = MetaTPClass(elem.get("name"), elem.get("type"))
                    meta.add_meta_tpclass(mtp)
                elif elem.tag == "features":
                    pass # nothing to do, but don't WARNING user
                elif elem.tag == "candidates":
                    return  # Finished processing
                else:
                    self.unknown_end_elem(xmlevent)
                elem.clear()


    #######################################################
    def parse_dict(self, inner_iterator):
        id_number_counter = 1
        entry = None
        word = None
        meta = None

        for event_str, elem, ctxinfo in inner_iterator:
            if event_str == "start":

                if elem.tag == "entry":
                    # Get the candidate ID or else create a new ID for it
                    if "entryid" in elem.attrib:
                        id_number_counter = elem.get("entryid")
                    # Instantiates an empty dict entry that will be treated
                    # when the <entry> tag is closed
                    entry = Entry(id_number_counter)
                    id_number_counter += 1

                elif elem.tag == "w":
                    props = self._parse_wordelem2props(ctxinfo, elem)
                    word = Word(ctxinfo, props)
                    entry.append(word)

                # Meta section and elements, correspond to meta-info about the
                # reference lists. Meta-info are important for generating
                # features and converting to arff files, and must correspond
                # to the info in the dictionary (e.g. meta-feature has the
                # same name as actual feature)
                elif elem.tag == "meta":
                    meta = Meta(None,None,None)

            if event_str == "end":

                if elem.tag == "entry":
                    self.handler.handle_candidate(entry, ctxinfo)
                    entry = None
                elif elem.tag == "w":
                    word = None
                elif elem.tag == "meta":
                    # Finished reading the meta header, call callback 
                    self.handler.handle_meta(meta, ctxinfo)

                elif elem.tag == "freq":
                    freq = Frequency(elem.get("name"),
                            int(elem.get("value")))
                    # If <freq> is inside a word element, then it's the word's
                    # frequency, otherwise it corresponds to the frequency of
                    # the ngram that is being read
                    if word is not None:
                        word.add_frequency(freq)
                    else:
                        entry.add_frequency(freq)

                elif elem.tag == "feat":
                    feat_name = elem.get("name")
                    feat_value = elem.get("value")
                    feat_type = meta.get_feat_type(feat_name)
                    if feat_type == "integer":
                        feat_value = int(feat_value)
                    elif feat_type == "real":
                        feat_value = float(feat_value)
                    f = Feature(feat_name, feat_value)
                    entry.add_feat(f)

                elif elem.tag == "corpussize":
                    cs = CorpusSize(elem.get("name"), elem.get("value"))
                    meta.add_corpus_size(cs)
                elif elem.tag == "metafeat" :      
                    mf = MetaFeat(elem.get("name"), elem.get("type"))
                    meta.add_meta_feat(mf)  

                elif elem.tag == "dict":
                    return  # Finished processing
                else:
                    self.unknown_end_elem(elem, ctxinfo)






######################################################################

class XMLEvent(collections.namedtuple('XMLEvent', 'event_str elem ctxinfo')):
    def check_empty(self):
        r"""Check whether `xmlevent.elem.attrib` values have been popped."""
        for k in self.elem.attrib:
            self.ctxinfo.warn("Ignoring unexpected XML attribute `{attr}` " \
                    "for elem `{elem}`", attr=k, elem=self.elem.tag)



class IterativeXMLParser:
    r"""This class allows us to iterate through the XML.
    Normally, `XMLPullParser` or `iterparse` would do the job,
    but we actually want to iterate through *everything*, including
    comments, and the devs decided that comments are not worthy
    of being iterated over... So we implement our own.

    We also generate source_{line,col}.
    """
    def __init__(self, inputobj, mwetkparser):
        self._subparser = expat.ParserCreate()
        self._subparser.CommentHandler = self.CommentHandler
        self._subparser.StartElementHandler = self.StartElementHandler
        self._subparser.EndElementHandler = self.EndElementHandler
        self._inputobj = inputobj
        self._mwetkparser = mwetkparser
        self._queue = collections.deque()  # deque[XMLEvent]
        self._elemstack = []  # list[XMLEvent]  (event_str=="start")

    def __iter__(self):
        r"""This object is an iterator."""
        return self

    def __next__(self):
        r"""Return next pair in buffer (parse more if needed)"""
        while True:
            if self._queue:
                return self._queue.popleft()

            data = self._inputobj.read_str(16*1024)
            if not data:
                # XXX check if self._subparser is in the
                # middle of processing something (HOW?), and
                # if so, raise an EOF error
                raise StopIteration
            self._subparser.Parse(data)


    def CommentHandler(self, text):
        elem = ElementTree.Element(ElementTree.Comment, {})
        elem.text = text
        ctxinfo = self._ctxinfo()
        self._queue.append(XMLEvent("start", elem, ctxinfo))
        self._queue.append(XMLEvent("end", elem, ctxinfo))

    def StartElementHandler(self, tag, attrs):
        elem = ElementTree.Element(tag, attrs)
        xmlevent = XMLEvent("start", elem, self._ctxinfo())
        self._elemstack.append(xmlevent)
        self._queue.append(xmlevent)

    def EndElementHandler(self, tag):
        xmlevent_start = self._elemstack.pop()
        xmlevent_end = XMLEvent("end", xmlevent_start.elem,
                self._ctxinfo(start_ctxinfo=xmlevent_start.ctxinfo))
        assert xmlevent_start.elem.tag == xmlevent_end.elem.tag
        self._queue.append(xmlevent_end)

    def _ctxinfo(self, start_ctxinfo=None):
        x_line = self._subparser.CurrentLineNumber-1
        x_col = self._subparser.CurrentColumnNumber
        if start_ctxinfo is not None:
            return start_ctxinfo.with_endpoint(x_line, x_col)

        return util.InputObjContextInfo(self._inputobj,
                mwetkparser=self._mwetkparser,
                linenum=util.NumberRange(x_line, None),
                colnum=util.NumberRange(x_col, None))
