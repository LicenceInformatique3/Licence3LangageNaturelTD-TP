#!/usr/bin/python
# -*- coding:UTF-8 -*-

# ###############################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# indexlib.py is part of mwetoolkit
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
    index.py - Routines for index manipulation.
"""

# In release 0.5, we add the ability to use either the C indexer or the
# original (more well tested) Python indexer. We face the doubt of how to
# implement that:
#
# 1. Subclassing: we implement a class for interfacing with the C indexer
# as as subclass of the current one (or make both the current one and the
#  C one subclasses of a new generic/abstract Index class).
#
#  2. Lots of if/elses. (Not so many of them, actually.)
#
# Approach 1 would work fine for normal index generation (as done by index.py):
# index.py instantiates the right class, then creates the indices. However, for
# dynamic index building (attribute fusion), we have already instantiated 
# mrkrrhgrghgrgrh, rethink all of this.






import sys
import os
import array
import subprocess
import struct
import functools

from ..base.sentence import SentenceFactory
from .. import util
from ..base.word import Word, WORD_ATTRIBUTES, ATTRIBUTE_SEPARATOR
from .. import filetype
from . import _common as common

# Path to the C indexer program. The default value should work.
END_OF_SENTENCE = ''
_escaper = common.Escaper("${", "}", [
    # (Note: remember that ${empty} is also used).
    ("$", "${dollar}"), ("\n", "${newline}"), ("#", "${hash}")
])

################################################################################

def index_escape(token) :
    token = _escaper.escape(token)
    if not token :
        token = "${empty}"
    return token

################################################################################

def index_unescape(token) :
    if token == "${empty}":
        token = ""
    token = _escaper.unescape(token)
    return token

################################################################################

# Taken from counter.py
def load_array_from_file(an_array, a_filename):
    """
        Fills an existing array with the contents of a file.
    """
    MAX_MEM = 10000
    fd = open(a_filename, "rb")
    isMore = True
    while isMore:
        try:
            an_array.fromfile(fd, MAX_MEM)
        except EOFError:
            isMore = False  # Did not read MAX_MEM_ITEMS items? Not a problem...
    fd.close()


################################################################################

def save_array_to_file(array, path):
    """
        Dumps an array to a file.
    """
    file = open(path, "wb")
    array.tofile(file)
    file.close()


################################################################################

def load_symbols_from_file(symbols, path):
    """
        Fills an existing symbol table with the contents of a file.
    """

    file = open(path, "rb")
    id = 0
    symbols.number_to_escaped_symbol = []
    symbols.escaped_symbol_to_number = {}
    for line in file:
        sym = line[:-1].decode("utf-8")
        symbols.escaped_symbol_to_number[sym] = id
        symbols.number_to_escaped_symbol.append(sym)
        id += 1

    file.close()


################################################################################

# Used by python indexer only
def save_symbols_to_file(symbols, path):
    """
        Dumps a symbol table to a file.
    """
    file = open(path, "wb")
    for sym in symbols.number_to_escaped_symbol:
        file.write(sym.encode("utf-8") + b'\n')
    file.close()


################################################################################

def read_attribute_from_index(attr, path):
    """
        Returns an iterator that yields the value of the attribute `attr`
        for every word in an index's corpus array. This allows one to recover
        the corpus from the index, and is used for attribute fusion.
    """

    with open(path + "." + attr + ".corpus", "rb") as corpus_file:
        symbols = SymbolTable()
        load_symbols_from_file(symbols, path + "." + attr + ".symbols")

        while True:
            # Assuming symbol table containing 32-bit ints (VOCABULARY size,
            # not CORPUS size)
            wordcode = corpus_file.read(4)
            if wordcode == b"":
                return
            wordnum = struct.unpack('I', wordcode)[0]
            yield symbols.number_to_escaped_symbol[wordnum]

################################################################################

def fuse_suffix_arrays(array1, array2, ctxinfo):
    """
        Returns a new `SuffixArray` fusing the `corpus` data of each input array
        This is used to generate indices for combined attributes (eg lemma+pos)
    """
    fused_array = SuffixArray()
    for i in range(len(array1.corpus)):
        sym1 = array1.symbols.number_to_escaped_symbol[array1.corpus[i]]
        sym2 = array2.symbols.number_to_escaped_symbol[array2.corpus[i]]
        if sym1 or sym2 : # None is a blank line
            assert(sym1 and sym2)
            fused_array.append_escaped_word(sym1 + ATTRIBUTE_SEPARATOR + sym2, ctxinfo)
        else : # Blank line, means end-of-sentence
            fused_array.append_escaped_word(END_OF_SENTENCE, ctxinfo)
    return fused_array


################################################################################
################################################################################

class SymbolTable(object):
    """
        Handles the conversion between word strings and numbers.
    """

    def __init__(self):
        self.escaped_symbol_to_number = {END_OF_SENTENCE: 0}
        self.number_to_escaped_symbol = [END_OF_SENTENCE]
        self.last_number = 0

    def intern(self, e_symbol):
        """
            Adds the string `e_symbol` to the symbol table.
        """
        if e_symbol not in self.escaped_symbol_to_number:
            self.last_number += 1
            self.escaped_symbol_to_number[e_symbol] = self.last_number
            #self.number_to_escaped_symbol[self.last_number] = symbol
            # Risky and not intention-expressing            
            self.number_to_escaped_symbol.append(e_symbol)

        return self.escaped_symbol_to_number[e_symbol]


################################################################################
################################################################################

class SuffixArray(object):
    """
        Class containing the corpus and suffix arrays and the symbol table
        for one attribute of a corpus.
    """

################################################################################

    def __init__(self, ctxinfo):
        self.corpus = array.array('I')  # List of word numbers
        self.suffix = array.array('L')  # List of word positions
        self.symbols = SymbolTable()  # word<->number conversion table

################################################################################

    def set_basepath(self, basepath, ctxinfo):
        """
            Sets the base path for the suffix array files.
        """
        self.basepath = basepath
        self.corpus_path = basepath + ".corpus"
        self.suffix_path = basepath + ".suffix"
        self.symbols_path = basepath + ".symbols"

################################################################################

    def load(self, ctxinfo):
        """
            Loads the suffix array from the files at `self.basepath`.
        """
        load_array_from_file(self.corpus, self.corpus_path)
        load_array_from_file(self.suffix, self.suffix_path)
        load_symbols_from_file(self.symbols, self.symbols_path)

################################################################################

    def save(self, ctxinfo):
        """
            Saves the suffix array to the files at `self.basepath`.
        """
        save_array_to_file(self.corpus, self.corpus_path)
        save_array_to_file(self.suffix, self.suffix_path)
        save_symbols_to_file(self.symbols, self.symbols_path)

################################################################################

    def append_escaped_word(self, word, ctxinfo):
        """
            Adds a new word to the end of the corpus array, putting it in the
            symbol table if necessary.
        """
        self.corpus.append(self.symbols.intern(word))

################################################################################

    def build_suffix_array(self, ctxinfo):
        """
            Builds the sorted suffix array from the corpus array.
        """
        tmpseq = list(range(0, len(self.corpus)))
        tmpseq.sort(key=functools.cmp_to_key(self.compare_ngrams))
        self.suffix = array.array('L', tmpseq)

################################################################################

    def compare_ngrams(self, pos1, pos2):
        """
            Compares the ngram at position `pos1` in the word list `corpus` with
            the ngram at position `pos2` in the word list `corpus`. Returns an
            integer less than, equal or greater than 0 if the first ngram is less
            than, equal or greater than the second, respectively. Comparison is
            truncated at END_OF_SENTENCE

            @param ngram1 A list or array of numbers, each representing a word.
            Likewise for `ngram2`.

            @param pos1 Position where the first ngram begins in `ngram1`.
            Likewise for `pos2`.
        """
        corpus = self.corpus
        max1 = len(corpus)
        while pos1 < max1 and pos2 < max1 :
            if corpus[pos1] != corpus[pos2] :
                return int(corpus[pos1] - corpus[pos2])
            if corpus[pos1]==0 and corpus[pos2]==0 :
                return 0  # Don't care about order after end-of-sentence.
            pos1+=1
            pos2+=1
        if pos1 >= max1:
            return -1
        elif pos2 >= max1:
            return 1
        else :
            return 0

################################################################################

    def find_ngram_range(self, ngram, min=0, max=None):
        """
            Returns a tuple `(first, last)` of matching ngram positions in
            the suffix array, or `None` if there is no match.
        """
        # TODO: We will need a more "incremental" approach for searching for
        # patterns that use multple word attributes. (Can't be done!)

        if max is None:
            max = len(self.suffix) - 1

        first = self.binary_search_ngram(ngram, min, max, array.array.__ge__)
        last = self.binary_search_ngram(ngram, min, max, array.array.__gt__)

        if first is None:
            return None
        if last is None:
            last = max
        else:
            last -= 1

        if first <= last:
            return (first, last)
        else:
            return None

################################################################################

    def binary_search_ngram(self, ngram, first, last, cmp):
        """
            Find the least suffix that satisfies `suffix <cmp> ngram`, or
            `None` if there is none.
        """

        # 'max' must be one more than 'last', for the case no suffix
        # satisfies the comparison.
        maxi = last + 1
        mini = first
        ngram_array = array.array('I', ngram)
        length = len(ngram)
        mid = -1
        while mini < maxi:
            mid = (mini + maxi) // 2
            midsuf = self.suffix[mid]
            #if cmp(compare_ngrams(self.corpus, self.suffix[mid], ngram, 0, \
            #                      ngram2_exhausted=0), 0):
            if cmp(self.corpus[midsuf: midsuf + length], ngram_array):
                # If 'mid' satisfies, then what we want *is* mid or *is before*
                # mid            
                maxi = mid
            else:
                # If 'mid' does not satisfy, what we want *must be after* mid.            
                mid += 1
                mini = mid
        if mid > last:
            return None
        else:
            return mid

################################################################################

    # For debugging.
    def dump_suffixes(self, limit=10, start=0, max=None):
        """
            Prints the suffix array to standard output (for debugging).
        """
        if max is None:
            max = len(self.suffix)

        #for pos in self.suffix:
        for suf in range(start, max):
            pos = self.suffix[suf]
            print("%4d:" % pos, end="")
            for i in range(pos, pos + limit):
                if i < len(self.corpus):
                    sym = self.symbols.number_to_escaped_symbol[self.corpus[i]]
                    if sym == "":
                        sym = "#"
                    print(sym, end="")
                else:
                    print("*", end="")

            print("")


################################################################################
################################################################################

C_INDEXER_PROGRAM = os.path.dirname(__file__) + "/../../c-indexer"

class CSuffixArray(SuffixArray):
    """
        This class implements an interface to the C indexer. Appended words
        go to a piped stream, and build_suffix_array invoked the C
        indexer upon that stream. After array construction, one must call
        array.load() to load the array into 'python-space'.
    """

################################################################################

    def __init__(self, ctxinfo):
        super(CSuffixArray, self).__init__(ctxinfo)
        self.basepath = None

################################################################################

    def set_basepath(self, basepath, ctxinfo):
        super(CSuffixArray, self).set_basepath(basepath,ctxinfo)
        self.indexer_process = subprocess.Popen([C_INDEXER_PROGRAM,
                                                 self.basepath],
                                                stdin=subprocess.PIPE,
                                                bufsize=4096)
        self.wordlist_file = self.indexer_process.stdin

################################################################################

    def append_escaped_word(self, word, ctxinfo):
        self.wordlist_file.write(word.encode('utf-8') + b'\n')

################################################################################

    def build_suffix_array(self, ctxinfo):
        if self.basepath is None:
            ctxinfo.error("Base path not specified for suffix array " \
                    "to be built with C indexer")
            sys.exit(2)

        util.verbose("Using C indexer to build suffix array %s" % self.basepath)
        self.indexer_process.communicate()

################################################################################

    def save(self, ctxinfo):
        self.wordlist_file.close()

################################################################################
################################################################################

class Index(object):
    """
        This class holds the `SuffixArray`s for all attributes of a corpus,
        plus metadata which is common for all attributes.
    """

    make_suffix_array = None
    c_indexer_program = None

################################################################################

    @staticmethod
    def use_c_indexer(wants_to_use, ctxinfo):
        """
            Class method that sets the appropriate indexer to use (C or Python).

            @param `wants_to_use` Whether we want to use the C indexer.
            Possible values are True, False and None (we don't care about it).
            If value is None, and use_c_indexer has never been called before,
            it defaults to True; otherwise it does not touch the current state.

        """

        if wants_to_use is None and Index.make_suffix_array is None:
            wants_to_use = True

        can_use = True
        # Find whether the C indexer exists.
        if wants_to_use:
            if os.path.isfile(C_INDEXER_PROGRAM):
                Index.c_indexer_program = C_INDEXER_PROGRAM
            elif os.path.isfile(C_INDEXER_PROGRAM + ".exe"):
                Index.c_indexer_program = C_INDEXER_PROGRAM + ".exe"
            else:
                can_use = False

        if can_use and wants_to_use:
            Index.make_suffix_array = CSuffixArray
        else:
            if wants_to_use:
                ctxinfo.warn("C indexer not found; "
                        "using (slower) Python indexer instead.")
            Index.make_suffix_array = SuffixArray


################################################################################

    def __init__(self, basepath=None, used_word_attributes=None,
                 use_c_indexer=None, ctxinfo=None):
        assert ctxinfo, "Argument ctxinfo is mandatory"
        self.arrays = {}
        self.metadata = {"corpus_size": 0}
        self.sentence_factory = SentenceFactory()

        Index.use_c_indexer(use_c_indexer, ctxinfo)

        if used_word_attributes is not None:
            self.used_word_attributes = used_word_attributes
        else:
            self.used_word_attributes = list(WORD_ATTRIBUTES)

        if basepath is not None:
            self.set_basepath(basepath, ctxinfo)

################################################################################

    def fresh_arrays(self, ctxinfo):
        """
            Creates empty suffix arrays for each used attribute in the index.
        """
        for attr in self.used_word_attributes:
            self.arrays[attr] = Index.make_suffix_array(ctxinfo)
            self.arrays[attr].set_basepath(self.basepath + "." + attr,
                                           ctxinfo)

################################################################################

    def set_basepath(self, path, ctxinfo):
        """
            Sets the base path for the index files.
        """
        self.basepath = path
        self.metadata_path = path + ".info"

################################################################################

    def array_file_exists(self, attr):
        return os.path.isfile(self.basepath + "." + attr + ".corpus")

################################################################################

    def load(self, attribute, ctxinfo):
        """
            Load an attribute from the corresponding index files.
            If the attribute is of the form `a1+a2` and the corresponding
            file does not exist, creates a new suffix array fusing the 
            arrays for attributes `a1` and `a2`.
        """
        #pdb.set_trace()
        if attribute in self.arrays:
            return self.arrays[attribute]

        if not self.array_file_exists(attribute):
            if '+' in attribute:
                self.make_fused_array(attribute.split('+'), ctxinfo)
            else:
                ctxinfo.warn("Cannot load attribute {attr}; " \
                        "index files not present.", attr=attribute)
                return None

        util.verbose("Loading corpus files for attribute \"%s\"." % attribute)
        array = SuffixArray(ctxinfo)
        path = self.basepath + "." + attribute
        array.set_basepath(path, ctxinfo)
        array.load(ctxinfo)

        self.arrays[attribute] = array
        return array

################################################################################

    def make_fused_array(self, attrs, ctxinfo):
        """
            Make an array combining the attributes `attrs`. This array must be
            loaded after creation.
        """

        util.verbose("Making fused array for " + '+'.join(attrs) + "...")
        generators = [read_attribute_from_index(attr, self.basepath) \
                      for attr in attrs]

        sufarray = Index.make_suffix_array(ctxinfo)
        sufarray.set_basepath(self.basepath + "." + '+'.join(attrs), ctxinfo)
        while True:
            try:                
                next_words = [next(g) for g in generators]
                # An empty line means End-Of-Sentence in input of C indexer
                if all(not n for n in next_words) :
                    sufarray.append_escaped_word(END_OF_SENTENCE, ctxinfo)
                else:
                    w = ATTRIBUTE_SEPARATOR.join(index_escape(w) for w in next_words)
                    sufarray.append_escaped_word(w, ctxinfo)

            except StopIteration:
                break

        sufarray.build_suffix_array(ctxinfo)
        sufarray.save(ctxinfo)

        # Is this any good? (May be with the old indexer; must test)
        sufarray = None
        #print("objects collected by gc.collect()", file=sys.stderr)

################################################################################

    def save(self, attribute, ctxinfo):
        """
            Saves the suffix array for `attribute` to the corresponding files.
        """
        array = self.arrays[attribute]
        #array.set_basepath(self.basepath + "." + attribute, ctxinfo)
        array.save(ctxinfo)

################################################################################

    def load_metadata(self, ctxinfo):
        """
            Loads the index metadata from the corresponding file.
        """
        try:
            metafile = open(self.metadata_path)
        except IOError:
            import os
            ctxinfo.error("Cannot access metadata file `{filename}`",
                    filename=os.path.basename(self.metadata_path))

        for line in metafile:
            key, type, value = line.rstrip('\n').split(" ", 2)
            if type == "int":
                value = int(value)
            self.metadata[key] = value

        metafile.close()

################################################################################

    def save_metadata(self, ctxinfo):
        """
            Saves the index metadata to the corresponding file.
        """
        metafile = open(self.metadata_path, "w")
        for key, value in list(self.metadata.items()):
            if isinstance(value, int):
                type = "int"
            else:
                type = "string"

            metafile.write("%s %s %s\n" % (key, type, value))

        metafile.close()

################################################################################

    # Load/save main (non-composite) attributes and metadata
    def load_main(self, ctxinfo):
        self.load_metadata(ctxinfo)
        present_attributes = []
        for attr in self.used_word_attributes:
            present = self.load(attr, ctxinfo)
            if present:
                present_attributes.append(attr)
        self.used_word_attributes = present_attributes

    ################################################################################

    def save_main(self, ctxinfo):
        self.save_metadata(ctxinfo)
        for attr in self.used_word_attributes:
            self.save(attr, ctxinfo)

################################################################################


    def append_end_sentence(self, nb_words, ctxinfo):
        for attr in self.used_word_attributes:
            # '' (symbol 0)  means end-of-sentence
            self.arrays[attr].append_escaped_word(END_OF_SENTENCE, ctxinfo)
        self.metadata["corpus_size"] += nb_words
    
################################################################################

    def append_sentence(self, sentence, ctxinfo):
        """
            Adds a `Sentence` (extracted from a corpus file) to the index.
        """
        for attr in self.used_word_attributes:
            for word in sentence:
                try :
                    value = word.get_prop(attr)
                except KeyError :
                    ctxinfo.warn_once("Empty/missing value for " \
                            "word attribute `{attr}`", attr=attr)
                    value = ""
                value = index_escape(value)
                self.arrays[attr].append_escaped_word(value, ctxinfo)
                # '' (symbol 0)  means end-of-sentence
        self.append_end_sentence(len(sentence), ctxinfo)

################################################################################

    def build_suffix_arrays(self, ctxinfo):
        """
            Build suffix arrays for all attributes in the index.
        """
        for attr in list(self.arrays.keys()):
            util.verbose("Building suffix array for %s..." % attr)
            ## REFACTOR FIXME
            #self.arrays[attr].set_basepath(self.basepath + "." + attr, ctxinfo)
            self.arrays[attr].build_suffix_array(ctxinfo)

################################################################################

    def iterate_sentences(self, ctxinfo):
        """Returns an iterator over all sentences in the corpus."""
        guide = self.used_word_attributes[0]  # guide?
        length = len(self.arrays[guide].corpus)
        words = []
        for i in range(0, length):
            if self.arrays[guide].corpus[i] == 0:
                # We have already a whole sentence.
                sentence = self.sentence_factory.make(words)
                sentence.ctxinfo = ctxinfo.with_begpoint(i)
                sentence.ctxinfo.current_progress = (i, length)
                yield sentence
                words = []

            else:
                props = {}
                for attr in self.used_word_attributes:
                    number = self.arrays[attr].corpus[i]
                    e_symbol = self.arrays[attr].symbols.number_to_escaped_symbol[number]
                    if e_symbol != "${empty}":
                        props[attr] = index_unescape(e_symbol)
                words.append(Word(ctxinfo, props))

################################################################################

    # For debugging.
    def print_sentences(self, ctxinfo):
        for sentence in self.iterate_sentences(ctxinfo):
            for word in sentence:
                print(word.surface, end="")
            print("")


################################################################################

    def populate_index(self, corpus_fileobjs, filetype_hint=None, ctxinfo=None):
        """Generates an `Index` from corpus files.
        CAREFUL: Creates fresh_arrays every time this is called.
        """
        handler = IndexPopulatorHandler(self, ctxinfo)
        filetype.parse(corpus_fileobjs, handler, filetype_hint)


################################################################################

class IndexPopulatorHandler(filetype.InputHandler):
    def __init__(self, index, ctxinfo):
        self.index = index
        self.index.fresh_arrays(ctxinfo)

    def handle_sentence(self, sentence, ctxinfo):
        self.index.append_sentence(sentence, ctxinfo)

    def finish(self, ctxinfo):
        self.index.build_suffix_arrays(ctxinfo)
        self.index.save_main(ctxinfo)


################################################################################
################################################################################
#t = fuse_suffix_arrays(h.arrays["surface"], h.arrays["pos"])

# For debugging.
def standalone_main(argv):
    if len(argv) != 3:
        print("Usage: python indexlib.py <basepath> <corpus>", file=sys.stderr)
        return 1

    basepath = argv[1]
    corpus = argv[2]

    ctxinfo = util.SimpleContextInfo("<debug run>")
    index = _index_from_corpus(ctxinfo, corpus, basepath)
    index.save_main(ctxinfo)
    print("Done.", file=sys.stderr)


def _index_from_corpus(ctxinfo, corpus, basepath=None, attrs=None):
    index = Index(basepath, attrs, ctxinfo=ctxinfo)
    index.populate_index([corpus], ctxinfo=ctxinfo)
    return index

################################################################################

if __name__ == "__main__":
    standalone_main(sys.argv)
