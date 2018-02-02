#!/usr/bin/python
# -*- coding:UTF-8 -*-

# ###############################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_corenlp.py is part of mwetoolkit
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
# ###############################################################################
"""
This module provides classes to manipulate files that are
encoded in mwetoolkit's "XML" filetype.

You should use the methods in package `filetype` instead.
"""






import itertools
import collections
from xml.etree import ElementTree

from . import _common as common
from . import ft_xml

# from ..base.__common import WILDCARD
from ..base.word import Word
from ..base.sentence import Sentence, SentenceFactory
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
from .. import util

# todo preserve coreference info at the end of the corpus

# subclass Word to modify writing functionality (to_xml won't serve our purposes)
class WordCoreNLP(Word):  # todo remove
    def __init__(self, ctxinfo, surface=None, lemma=None,
                 pos=None, syn=None, freqs=None, extra=None):
        super(WordCoreNLP, self).__init__(ctxinfo, surface, lemma, pos, syn, freqs, extra)
        self._extra = collections.defaultdict(str)
        if extra is not None:
            self._extra.update(extra)

    def to_corenlp(self, fallback_ctxinfo):
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


class SentenceCoreNLP(Sentence):  # todo remove
    def __init__(self, word_list, id_number):
        super(SentenceCoreNLP, self).__init__(word_list, id_number)

    def to_corenlp(self, ctxinfo):
        """
            Provides an XML string representation of the current object,
            including internal variables, formatted as CoreNLP.

            @return A string containing the XML element <sentence> with
            its internal structure and attributes.
        """

        result = "<sentence"
        if self.id_number >= 0:
            result += " id=\"" + str(self.id_number) + "\">\n\t<tokens>\n"
        else:
            result += ">\n\t<tokens>\n\t"
        for word in self.word_list:
            result = result + word.to_corenlp(ctxinfo) + " "
        result += '</tokens>\n'

        result += self.word_list[-1]._extra['xml']  # append dependency information

        if self.mweoccurs:
            result += "\n<mweoccurs>\n"
            for mweoccur in self.mweoccurs:
                result += "  " + util.to_xml(mweoccur, ctxinfo) + "\n"
            result += "</mweoccurs>\n"
        result += "</sentence>"

        return result.strip()


# subclass SentenceFactory to use SentenceCoreNLP objects
class SentenceFactoryCoreNLP(SentenceFactory):
    def __init__(self):
        super(SentenceFactoryCoreNLP, self).__init__()

    def make(self, word_list=[], **kwargs):
        r"""Calls `Sentence(word_list, ...)` to create a Sentence."""
        self.prev_id = kwargs.pop("id_number", self.prev_id + 1)
        return SentenceCoreNLP(word_list, id_number=self.prev_id, **kwargs)


# ###############################################################################

class CoreNLPInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for mwetoolkit's XML."""
    description = "An XML in CoreNLP format"
    filetype_ext = "CoreNLP"

    # TODO use escape_pairs here... how?
    escape_pairs = []

    def operations(self):
        return common.FiletypeOperations(CoreNLPChecker, CoreNLPParser, CoreNLPPrinter)


INFO = CoreNLPInfo()

# ###############################################################################


class CoreNLPChecker(common.AbstractChecker):
    r"""Checks whether input is in CoreNLP format."""

    def matches_header(self, strict):
        header = self.fileobj.peek(300)
        if header.startswith(b"\xef\xbb\xbf"):
            header = header[3:]  # remove utf8's BOM
        return b'<root>' in header


# ###############################################################################

XML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
# <!DOCTYPE {category} SYSTEM "dtd/mwetoolkit-{category}.dtd">
<!-- MWETOOLKIT: filetype="CoreNLP" -->
<root {ns}>
<document>
<sentences>"""

XML_FOOTER = """</sentences>
{coreference}
</document>
</root>"""
# fixme when you decide to save coreference info, this should go in before document tag above

class CoreNLPPrinter(common.AbstractPrinter):
    """Instances can be used to print XML objects."""
    valid_categories = ["corpus"]

    # initialize the printer and write header
    def __init__(self, ctxinfo, *args, **kwargs):
        super(CoreNLPPrinter, self).__init__(ctxinfo, *args, **kwargs)
        self.add_string(ctxinfo, XML_HEADER.format(category=self._category, ns=""), "\n")
        self._printed_filetype_directive = True

    # write footer and finish printing
    def finish(self, ctxinfo):
        self.add_string(ctxinfo, XML_FOOTER.format(coreference=''), "\n")
        super(CoreNLPPrinter, self).finish(ctxinfo)

    def handle_comment(self, comment, ctxinfo):
        self.add_string(ctxinfo, "<!-- ", self.escape(str(comment)), " -->\n")

    def handle_pattern(self, pattern, ctxinfo):
        # TODO Currently copying node XML from input. This should change in the future...
        self.add_string(ctxinfo, ElementTree.tostring(pattern.node))

    def _fallback(self, entity, ctxinfo):

        # word and sentences get written into corenlp format
        # try:
            self.add_string(ctxinfo, entity.to_corenlp(ctxinfo), "\n")

        # other things like mwe occurrences get written as xml until we decide better
        # except AttributeError:
        #     self.add_string(ctxinfo, entity.to_xml(ctxinfo), "\n")


################################################################################
class CoreNLPParser(common.AbstractParser):
    r"""Instances of this class parse the mwetoolkit XML format,
    calling the `handler` for each object that is parsed.
    """

    def __init__(self):
        super(CoreNLPParser, self).__init__()
        self.dependencies = {}
        self.extra = {}
        self.extra_xml = ''

    valid_categories = ["corpus"]

    def _parse_file(self):
        # Here, fileobj is raw bytes, not unicode, because ElementTree
        # complains if we feed it a pre-decoded stream in python2k
        xmlparser = iter(ft_xml.IterativeXMLParser(self.inputobj, self))
        if not self.inputobj.peek_bytes(10).startswith(b"<?xml"):
            if b"\n<?xml" in self.inputobj.peek_bytes():
                # Python's XMLParser is unable to handle this, so we just give up
                self.latest_ctxinfo.error("XML tag <?xml> cannot appear after first line!")
            self.latest_ctxinfo.warn("XML file should start with <?xml> tag!")

        already_seen = []

        for event, elem, ctxinfo in xmlparser:
            already_seen.append((event, elem))
            if event == "start":
                if elem.tag != ElementTree.Comment:
                    if elem.tag != "root":
                        self.ctxinfo.error("Bad top-level XML elem: {tag!r}" \
                                           .format(tag=elem.tag))
                    delegate = self.parse_corpus
                    self.inputobj.category = 'corpus'

                    with common.ParsingContext(self):
                        it = itertools.chain(already_seen, xmlparser)
                        delegate(it, self.ctxinfo)


    def unknown_end_elem(self, elem, ctxinfo):
        r"""Complain about unknown XML element."""
        if elem.tag == ElementTree.Comment:
            comment = common.Comment(elem.text.strip())
            self.handler.handle_comment(comment, ctxinfo)
        else:
            ctxinfo.warn("Ignoring unknown XML elem: {tag!r}", tag=elem.tag)


    #######################################################
    def parse_corpus(self, inner_iterator, ctxinfo):
        # sentence_factory = SentenceFactoryCoreNLP()
        sentence_factory = SentenceFactory()
        sentence = None

        ignore_tags = [

            # structure-related, are easy to restore
            'document',
            'tokens',
            'sentences',

            # coreference info, should be preserved on corpus-level
            'coreference',
            'mention',
            'start',
            'end',
            'head',
            'text'
        ]
        extra_tags = [
            'CharacterOffsetBegin',
            'CharacterOffsetEnd',
            'NER',
            'Speaker',
            'Timex',
            'NormalizedNER'
        ]

        # this is a list of tags that should not be cleared after reading.
        # they will be retained until their parent element has finished processing, and then cleared with it
        no_clear = [
            'dep',
            'governor',
            'dependent'
        ]

        for event, elem in inner_iterator:

            update(ctxinfo, elem)

            if event == "start":

                # there are two kinds of sentence tags: the first kind contains words; make this into a Sentence
                # the second kind appears in coreference info and only carries its own id as value, pass
                if elem.tag == "sentence":
                    try:
                        s_id = int(elem.attrib['id'])
                        sentence = sentence_factory.make(id_number=s_id)

                    except KeyError:
                        sentence = None

                elif elem.tag == "mweoccur":
                    occur_cand = Candidate(int(elem.get("candid")))
                    new_occur = MWEOccurrence(sentence, occur_cand, [])
                    sentence.mweoccurs.append(new_occur)

            elif event == "end":
                if elem.tag == "sentence":

                    if sentence:  # otherwise, we're in a coreference sentence tag that doesn't need processing
                        # A complete sentence was read, call the callback function
                        self.update_dependencies(sentence)
                        self.attach_extra(sentence)
                        self.handler.handle_sentence(sentence, ctxinfo)

                elif elem.tag == "token":
                    # modified this, because in a corenlp corpus attrbutes are listed as child tag text
                    # Add word to the sentence that is currently being read
                    self.extra['id'] = elem.attrib['id']
                    props = {'surface': surface,
                             'lemma': lemma,
                             'pos': pos,
                             }
                    props.update(self.extra)
                    sentence.append(Word(ctxinfo, props))
                    self.extra.clear()

                elif elem.tag == "mweoccurs":
                    pass  # This tag is just a wrapper around `mweoccur` tags
                elif elem.tag == "mweoccur":
                    pass  # Already created MWEOccurrence on `start` event

                elif elem.tag == "mwepart":
                    sentence.mweoccurs[-1].indexes.append(int(elem.get("index")) - 1)

                elif elem.tag == "root":
                    return  # Finished processing

                # save current word attributes before they get cleared by iterparse
                elif elem.tag == 'lemma':
                    lemma = elem.text
                elif elem.tag == 'POS':
                    pos = elem.text
                elif elem.tag == 'word':
                    surface = elem.text

                # save all tags inside a token that are not used in mwetoolkit
                elif elem.tag in extra_tags:
                    self.extra[elem.tag] = elem.text

                # same story with these, otherwise they get cleared before we process <dep> tags
                elif elem.tag == 'governor':
                    governor_id = elem.get('idx')
                elif elem.tag == 'dependent':
                    dependent_id = elem.get('idx')

                # save all dependency info to reconstruct and attach to words later
                elif elem.tag == 'dep':

                    # CoreNLP files contain multiple dependency records, from basic to collapsed
                    # we cannot access the parent element from here to check directly where we are
                    # but the basic dependencies, which are the ones we need, occur first in the file
                    # so simply do not overwrite anything already written in place for a word
                    try:
                        self.dependencies[dependent_id]
                    except KeyError:
                        self.dependencies[dependent_id] = \
                            '{0:s}:{1:s}'.format(elem.get('type'), governor_id)

                # save chunks of xml related to each sentence. they will be carried through unaltered
                elif elem.tag == 'dependencies' or elem.tag == 'parse':
                    self.extra_xml += ElementTree.tostring(elem)

                elif elem.tag in ignore_tags:
                    pass
                else:
                    self.unknown_end_elem(elem, ctxinfo)

                if elem.tag not in no_clear:
                    elem.clear()

    def update_dependencies(self, sentence):
        # iterate over words in a sentence
        for i in range(len(sentence.word_list)):  # because no explicit indices are available
            word = sentence.word_list[i]

            try:
                # assign syntactic dependency info gathered from dep tags
                word.syn = self.dependencies[str(i + 1)]  # add one because CoreNLP enumerates from 1

            # not all words are dependent
            except KeyError:
                pass

    def attach_extra(self, sentence):
        if sentence.word_list:
            word = sentence.word_list[-1]  # really doesn't matter which one, the last for geographic proximity
            word._props['xml'] = self.extra_xml
        self.extra_xml = ''
