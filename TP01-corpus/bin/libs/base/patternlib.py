#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# patternlib.py is part of mwetoolkit
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







import bisect
import collections
import itertools

from ..base.word import ATTRIBUTE_SEPARATOR, WORD_SEPARATOR


##################################################

class AbstractPattern(object):
    """An in-memory representation of a pattern fragment."""
    def __init__(self, ctxinfo):
        self.ctxinfo = ctxinfo
        self._frozen = False
        self._matcher = None

    def matches(self, *args, **kwargs):
        r"""Create internal PatternMatcher and run its method `matches`.
        (Note: This method forces this object to be frozen beforehand!)
        """
        self.freeze()
        if not self._matcher:
            self._matcher = PatternMatcher(self)
        return self._matcher.matches(*args, **kwargs)

    def freeze(self):
        r"""Make this object unmodifiable."""
        if not self._frozen:
            self._frozen = True
            for subpattern in self.subpatterns:
                subpattern.freeze()
        return self

    def sub_strid(self, cur_id):
        r"""Return this object's ID, or `cur_id` if unavailable."""
        return cur_id

    @property
    def ignore(self):
        r"""Whether matches with this object should be ignored."""
        return False



class ContainerPattern(AbstractPattern):
    """ContainerPattern is an abstract class."""
    def __init__(self, ctxinfo, subpatterns=None):
        super(ContainerPattern, self).__init__(ctxinfo)
        self.subpatterns = subpatterns or []

    def sub_elems(self):
        r"""Iterate through all sub-elements."""
        return iter(self.subpatterns)

    def append_pattern(self, ctxinfo, subpattern):
        """Append subpattern to the list of subpatterns.

        Parameters:
        @subpattern: The AbstractPattern instance to append
        """
        # Just delegate to `add_pattern`
        return self.add_pattern(ctxinfo, subpattern, len(self.subpatterns))

    def add_pattern(self, ctxinfo, subpattern, index):
        """Add a subpattern to the list of subpatterns.

        Parameters:
        @subpattern: The AbstractPattern instance to add
        """
        assert not self._frozen
        assert isinstance(subpattern, AbstractPattern), subpattern
        self.subpatterns.insert(index, subpattern)

    def remove_pattern(self, ctxinfo, subpattern):
        """Remove an AbstractPattern from the list of subpatterns.

        Parameters:
        @subpattern: The AbstractPattern instance to remove
        """
        assert not self._frozen
        self.subpatterns.remove(subpattern)



##################################################

class EitherPattern(ContainerPattern):
    """Represents an OR operation among AbstractPatterns."""
    def add_pattern(self, ctxinfo, subpattern, index):
        if not isinstance(subpattern, SequencePattern):
            ctxinfo.error("Bad subpattern inside `either` block")
        super(EitherPattern, self).add_pattern(ctxinfo, subpattern, index)



##################################################

class SequencePattern(ContainerPattern):
    """Represents a sequence of AbstractPatterns.

    Attributes:
    @seq_strid: the ID for this SequencePattern, or None
    @repeat: a repeat command (e.g. "*" or "+"), or None
    @ignore: whether to ignore matches inside this SequencePattern
    """
    DISPATCH = "handle_pattern"

    def __init__(self, ctxinfo, seq_strid=None, repeat=None, ignore=False, subpatterns=None):
        # XXX we don't yet support anchor_start and anchor_end
        super(SequencePattern, self).__init__(ctxinfo, subpatterns)
        self.seq_strid = seq_strid
        self.repeat = repeat
        self._ignore = ignore

    def sub_strid(self, cur_strid):
        return self.seq_strid if self.seq_strid is not None else cur_strid

    @property
    def ignore(self):
        return self._ignore

    @ignore.setter
    def ignore(self, new_ignore):
        self._ignore = bool(new_ignore)



##################################################

"""The only props actually guaranteed to be supported by the toolkit for now."""
CLASSICAL_PAT_PROPS = frozenset(("surface", "lemma", "pos", "syn", "syndep"))


class WordPattern(AbstractPattern):
    """Represents a pattern that corresponds to a `Word`.

    Attributes:
    @w_strid: the ID for this word
    @positive_props: Dict[name, value] where name=~/value/
    @negative_props: Dict[name, value] where name!~/value/
    """

    def __init__(self, ctxinfo, w_strid=None):
        super(WordPattern, self).__init__(ctxinfo)
        self.ctxinfo = ctxinfo
        self.w_strid = w_strid
        self.positive_props = {}
        self.negative_props = {}

    def sub_strid(self, cur_strid):
        return self.w_strid if self.w_strid is not None else cur_strid


    def add_prop(self, name, value, negated):
        """Add an attribute name=value or name!=value to a word pattern.

        Parameters:
        @name: The name of the attribute
        @value: An instance of WordProp
        @negated: Whether the match should be negated (name !~ value)
        """
        assert not self._frozen
        assert isinstance(value, WordProp), value
        d = self.negative_props if negated else self.positive_props
        try:
            proplist = d[name]
        except KeyError:
            proplist = d[name] = []
        proplist.append(value)


    @property
    def subpatterns(self):
        r"""All sub-elements."""
        return ()



##################################################

import re

class WordProp(object):
    r"""Represents a key=value or some similar property
    that can be added to a WordPattern.
    """
    def to_base_regex(self):
        r"""Return the regex that matches this property."""
        raise NotImplementedError

    def to_positive_lookahead_regex(self):
        r"""Return the positive lookahead that matches this property."""
        # TODO CHECKME we should forbid e.g. "la" matching "cela" or "lave"
        return "(?={})".format(self.to_base_regex())

    def to_negative_lookahead_regex(self):
        r"""Return the negative lookahead that matches this property."""
        # TODO CHECKME we should allow e.g. "?!la" to match "cela" or "lave"
        return "(?!{})".format(self.to_base_regex())


class RegexProp(WordProp):
    r"""Represents the value of a field. E.g. "walk(s|ing|ed)?"."""
    RE_REGEX_SPECIAL = re.compile(r"(\\[sdwSDW\W]|\[\^|[?*+.(){|}\[\]])")

    RE_VALUE_NONSEPARATOR = "[^" + ATTRIBUTE_SEPARATOR + WORD_SEPARATOR + "]"
    RE_VALUE_ADD_NONSEP = "[^\\1" + ATTRIBUTE_SEPARATOR + WORD_SEPARATOR + "]"

    RE_NEGBLOCK = re.compile(r"(?!\\)\[\^(.*?)\]")  # matches "[^charseq]"
    RE_BACKSLASHES = re.compile(r"(\\[WDS])")  # matches "\W", "\D", "\S"
    RE_DOT = re.compile(r"(?!\\)\.")  # matches "."
    RE_BAD = re.compile(r"(?!\\)(\$|\(\?|\^)|\\[^sdwSDW\W]")  # bad stuff: ^, $, (?

    def __init__(self, ctxinfo, value, flags=""):
        for bad in self.RE_BAD.finditer(value):
            # "^" and "$" are already implicit; "(?" breaks things
            ctxinfo.warn("Bad regex element `{re}`", re=bad.group(0))

        for flag in flags:
            if flag not in ["i"]:
                ctxinfo.warn("Bad regex flag `{flag}`", flag=flag)

        # Meta: we use regexes to fix regexes... Why not...
        re_value = value
        re_value = self.RE_DOT.sub(self.RE_VALUE_NONSEPARATOR, re_value)
        re_value = self.RE_NEGBLOCK.sub(self.RE_VALUE_ADD_NONSEP, re_value)
        re_value = self.RE_BACKSLASHES.sub(self.RE_VALUE_ADD_NONSEP, re_value)

        # TODO check if the regex is re.compile`able
        self.re_value = re_value
        self.value = value
        self.flags = flags

    def to_base_regex(self):
        if self.flags:
            return "(?" + self.flags + ")" + self.re_value
        return self.re_value


class StarredWildcardProp(WordProp):
    r"""Represents the value of a field. E.g. "walk*"."""
    def __init__(self, ctxinfo, value):
        self.value = value

    def to_base_regex(self):
        return re.escape(self.value).replace("\\*",
                PatternMatcher.ATTRIBUTE_WILDCARD)


class LiteralProp(WordProp):
    r"""Represents the value of a literal field. E.g. "walk"."""
    def __init__(self, ctxinfo, value):
        self.value = value

    def to_base_regex(self):
        return re.escape(self.value)


class BackrefProp(WordProp):
    r"""Represents a field back-reference. E.g. (w_strid="n1", prop="lemma")."""
    def __init__(self, ctxinfo, w_strid, prop):
        self.w_strid, self.prop = w_strid, prop

    def to_base_regex(self):
        return "(?P=wid_{}_{})".format(self.w_strid, self.prop)



##################################################

from ..base.word import Word, WORD_ATTRIBUTES
from ..base.ngram import Ngram


class PatternMatcher(object):
    r"""Instances of this class can match against a pattern."""
    # ATTRIBUTE_WILDCARD: Match .* inside an attribute.
    ATTRIBUTE_WILDCARD = "[^" + ATTRIBUTE_SEPARATOR + WORD_SEPARATOR + "]*"
    # WORD_FORMAT: Internal Regex format to match a word with its attributes.
    WORD_FORMAT = ATTRIBUTE_SEPARATOR.join("{"+s+"}" for s in (["wordnum"] + WORD_ATTRIBUTES))

    def __init__(self, patternobj):
        assert isinstance(patternobj, AbstractPattern), patternobj
        self.patternobj = patternobj
        self.ctxinfo = patternobj.ctxinfo

        self.temp_id = 0
        self.defined_w_ids = []
        self.forepattern_ids = {}
        self.WORD_SEPARATOR = WORD_SEPARATOR
        self.pat_pieces = [self.WORD_SEPARATOR]
        self.strid2parent = {}
        self.ignored2strid = {}

        self._do_parse(patternobj, "id_*", None)
        self._post_parsing()


    def _post_parsing(self):
        self.compiled_pattern = re.compile("".join(self.pat_pieces))
        if self.compiled_pattern.match(self.WORD_SEPARATOR):
            self.ctxinfo.warn("Pattern matches empty string")
        self._strid2numid = {"id_*": 0}
        self._strid2numid.update(self.compiled_pattern.groupindex)
        self.numid2parent = {self._strid2numid[sid]: self._strid2numid[par]
                for (sid, par) in self.strid2parent.items()}
        self.ignored_numids = set(numid for (strid, numid) in
                list(self.compiled_pattern.groupindex.items()) if
                strid.startswith("ignore_"))
        self.ignored_sub_numids = collections.defaultdict(list)
        self._fill_ignored_sub_numids()


    def _fill_ignored_sub_numids(self):
        r"""Update self.ignored_sub_numids to be a {ID: set([ch1,ch2,..])} dict."""
        for patobj, strid in self.ignored2strid.items():
            numid = self._strid2numid[strid]
            ancestor = numid
            while True:
                self.ignored_sub_numids[ancestor].append(numid)
                if ancestor == 0: break
                ancestor = self.numid2parent[ancestor]


    def _do_parse(self, pat_obj, parent_strid, scope_repeat):
        if isinstance(pat_obj, SequencePattern):
            self._parse_seq(pat_obj, parent_strid, scope_repeat)
        elif isinstance(pat_obj, EitherPattern):
            self._parse_either(pat_obj, parent_strid, scope_repeat)
        elif isinstance(pat_obj, WordPattern):
            self._parse_w(pat_obj, parent_strid, scope_repeat)
        else:
            assert False, pat_obj


    def _check_scope_repeat(self, scope_repeat, pat_obj):
        if scope_repeat is not None:
            self.ctxinfo.warn(
                    "Elem cannot have `id` or `ignore` under a `repeat`" \
                    " scope (`repeat` in line {line_super}," \
                    " col {col_super})",
                    line_super=scope_repeat.ctxinfo.linenum.beg,
                    col_super=scope_repeat.ctxinfo.colnum.beg)


    def _parse_seq(self, seq_patobj, parent_strid, scope_repeat):
        seq_strid = seq_patobj.seq_strid
        repeat = seq_patobj.repeat
        ignore = seq_patobj.ignore

        if ignore:
            self._check_scope_repeat(scope_repeat, seq_patobj)
            strid = "ignore_%d" % len(self.ignored2strid)
            self.pat_pieces.extend(("(?P<", strid, ">"))
            self.ignored2strid[seq_patobj] = strid
            self.strid2parent[strid] = parent_strid
            parent_strid = strid

        if seq_strid:
            self._check_scope_repeat(scope_repeat, seq_patobj)
            assert "_" not in seq_strid, seq_strid
            strid = "id_%s" % seq_strid
            self.pat_pieces.extend(("(?P<", strid, ">"))
            self.strid2parent[strid] = parent_strid
            parent_strid = strid

        if repeat:
            self.pat_pieces.append("(?:")

        if scope_repeat is not None and repeat != "":
            scope_repeat = seq_patobj
        for subpat in seq_patobj.subpatterns:
            self._do_parse(subpat, parent_strid, scope_repeat)

        if repeat:
            self.pat_pieces.append(")")
            self.pat_pieces.append(repeat)
            if repeat != "*" and repeat != "?" and repeat != "+" and \
                not re.match(r"^\{[0-9]*,[0-9]*\}|\{[0-9]+\}$",repeat ) :
                self.ctxinfo.warn("Invalid repeat pattern: {repeat}",
                        repeat=repeat)

        if seq_strid:
            self.pat_pieces.append(")")

        if ignore:
            self.pat_pieces.append(")")


    def _parse_either(self, either_patobj, parent_strid, scope_repeat):
        self.pat_pieces.append("(?:")

        first_pattern = True
        for subpat in either_patobj.subpatterns:
            if not first_pattern:
                self.pat_pieces.append("|")
            first_pattern = False
            self._do_parse(subpat, parent_strid, scope_repeat)

        self.pat_pieces.append(")")


    def _parse_w(self, w_patobj, parent_strid, scope_repeat):
        attrs = { "wordnum": self.ATTRIBUTE_WILDCARD }
        w_strid = w_patobj.w_strid

        for attr in WORD_ATTRIBUTES:
            try:
                positive_props = w_patobj.positive_props[attr]
            except KeyError:
                val = self.ATTRIBUTE_WILDCARD
            else:
                propval = positive_props[0]
                val = propval.to_base_regex()
                val = "".join(propval.to_positive_lookahead_regex()
                        for propval in positive_props[1:]) + val

            val = "".join(propval.to_negative_lookahead_regex()
                    for propval in w_patobj.negative_props.get(attr, ())) + val
            attrs[attr] = val

        
        if w_patobj.w_strid:
            self._check_scope_repeat(scope_repeat, w_patobj)
            if w_patobj.w_strid in self.forepattern_ids:
                attrs["wordnum"] = "(?P=foreid_%s)" % self.forepattern_ids[w_patobj.w_strid]
            for attr in attrs:
                attrs[attr] = "(?P<wid_%s_%s>%s)" % (w_patobj.w_strid, attr, attrs[attr])
            if w_patobj.w_strid in self.defined_w_ids:
                raise Exception("Id '%s' defined twice" % w_patobj.w_strid)
            self.defined_w_ids.append(w_patobj.w_strid)


        if "syndep" in w_patobj.positive_props:
            propval = w_patobj.positive_props["syndep"][0]  # XXX support negation and multiple syndeps
            # XXX what is this ";" being added?!?!

            (deptype, depref) = propval.value.split(":")
            if depref in self.defined_w_ids:
                # Backreference.
                attrs["syn"] = (self.ATTRIBUTE_WILDCARD +
                               ";%s:(?P=wid_%s_wordnum);" % (deptype, depref) +
                               self.ATTRIBUTE_WILDCARD)
            else:
                # Fore-reference.
                foredep = "foredep_%d" % self.temp_id
                self.temp_id += 1
                self.forepattern_ids[depref] = foredep

                attrs["syn"] = (self.ATTRIBUTE_WILDCARD +
                                ";%s:(?P<foreid_%s>[0-9]*);" % (deptype, foredep) +
                                self.ATTRIBUTE_WILDCARD)

        w_pat = self.WORD_FORMAT.format(**attrs) + self.WORD_SEPARATOR
        if w_patobj.w_strid:
            w_pat = "(?P<id_{}>{})".format(w_patobj.w_strid, w_pat)
        self.pat_pieces.append(w_pat)



    def matches(self, words, match_distance="All", overlapping=True,
                id_order=("*",), anchor_begin=False, anchor_end=False):
        """Returns an iterator over all matches of this pattern in the word list.
        Each iteration yields a pair `(ngram, match_indexes)`.
        """
        numid_order = list(self.strids2numids(id_order))
        wordstringlist = []
        seplen = len(self.WORD_SEPARATOR)        
        wordstringlen = seplen
        positions = []
        wordnum = 1
        for word in words:
            positions.append(wordstringlen)
            attrs = { "wordnum": wordnum }
            for attr in WORD_ATTRIBUTES:
                attrs[attr] = getattr(word, attr)
            attrs["syn"] = ";{};".format(attrs["syn"])
            wordstringelem = self.WORD_FORMAT.format(**attrs)
            wordstringlist.append(wordstringelem)
            wordstringlen += len(wordstringelem) + seplen
            wordnum += 1
        wordstring = self.WORD_SEPARATOR + self.WORD_SEPARATOR.join(wordstringlist) + self.WORD_SEPARATOR

        i = 0
        while i < len(positions):
            matches_here = list(self._matches_at(words, wordstring,
                    positions[i], len(wordstring), positions, numid_order,
                    anchor_end))

            increment = 1
            if match_distance == "All":
                if not overlapping:
                    raise Exception("All requires Overlapping")
                for m in matches_here:
                    yield m
            elif match_distance == "Longest":
                if matches_here:
                    yield matches_here[0]
                    if not overlapping:
                        increment = len(matches_here[0][0])
            elif match_distance == "Shortest":
                if matches_here:
                    yield matches_here[-1]
                    if not overlapping:
                        increment = len(matches_here[-1][0])
            else:
                raise Exception("Bad match_distance: " + match_distance)

            i += increment
            if anchor_begin: return


    def _matches_at(self, words, wordstring, current_start,
            limit, positions, numid_order, anchor_end):
        # Example:
        # -- words: foo (barr{id=R}){ignore} baz{id=Z} qux
        # -- wordstring: @foo@barr@baz@qux@
        # -- numid_order: 3(=Z) 0(=*) 1(=R)   # 2=ignore
        # -- positions: p1 p5 p10 p14 p18
        # -- match_result.span (numid2posrange): 0(=*)=>p1-p18 1(=R)=>p5-p10
        #                                   2(=ignore)=>p5-p10 3(=Z)=>p10-p14
        # -- wordnums (returned):  2  0 2 3  1
        # -- ngram (returned):  baz  foo abz qux  barr
        current_end = limit
        matches_here = []
        while True:
            match_result = self.compiled_pattern.match(
                    wordstring, current_start-1, current_end)
            if not match_result: return

            start = match_result.start()
            end = match_result.end()
            current_end = end - 1
            ngram = []
            wordnums = []

            pos2wordnum = {p:i for (i,p) in enumerate(positions)}

            for numid in numid_order:
                ignored_ranges = list(match_result.span(numid) \
                        for numid in self.ignored_sub_numids[numid])
                p_beg, p_end = match_result.span(numid)
                i = bisect.bisect_left(positions, p_beg)
                # Look at each pos in wordstring in range p_beg..p_end
                for pos in itertools.islice(positions, i, None):
                    if pos >= p_end: break  # Outside slice for `numid`
                    if not any(p_ignored_beg <= pos < p_ignored_end \
                            for (p_ignored_beg, p_ignored_end) in ignored_ranges):
                        wordnums.append(pos2wordnum[pos])

            yield (Ngram([words[i].copy() for i in wordnums]), wordnums)
            if anchor_end: return


    def strids2numids(self, strid_order):
        for strid in strid_order:
            try:
                yield self._strid2numid["id_" + strid]
            except KeyError:
                self.ctxinfo.warn_once("Pattern does not define id " \
                        "`{strid}`", strid=strid)


    def printable_pattern(self):
        r"""Return a printable version of `self.pattern`.
        The pattern follows the syntax `@attr1,attr2,...,attrN@` where
           * @ = word separator (words are surrounded by these)
           * attrK = attribute K ("_" for undefined)
        """
        return printable(self.compiled_pattern.pattern) \
                .replace("[^,@]*", "_")


def printable(string):
    r"""Return a printable version of `string`.
    The pattern follows the syntax `@attr1,attr2,...,attrN@` where
       * @ = word separator (words are surrounded by these)
       * attrK = attribute K ("_" for undefined)
    """
    return string \
            .replace(WORD_SEPARATOR, "@") \
            .replace(ATTRIBUTE_SEPARATOR, ",")


def build_generic_pattern(ctxinfo, min, max):
    """Returns a pattern matching any ngram of size min~max."""
    repeat = "{{{min},{max}}}".format(min=min, max=max)
    sp = SequencePattern(ctxinfo, None, repeat, False)
    sp.append_pattern(ctxinfo, WordPattern(ctxinfo, None))
    return sp.freeze()
