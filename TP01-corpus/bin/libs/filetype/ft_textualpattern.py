#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# ft_bracketpattern.py is part of mwetoolkit
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
"TextualPattern" filetype, which is an input/output pattern format.

You should use the methods in package `filetype` instead.
"""






import re

from . import _common as common
from ..base import patternlib
from .. import util


################################################################################

class TextualPatternInfo(common.FiletypeInfo):
    r"""FiletypeInfo subclass for TextualPattern."""
    description = "Human-readable MWE-pattern format"
    filetype_ext = "TextualPattern"

    comment_prefix = "#"
    escaper = common.Escaper("${", "}", [
            ("$", "${dollar}"),
            ("{", "${openbrace}"),
            ("$${openbrace}dollar}", "${"),  # fix bug (escaping both $ and { above)
            ("[", "${openbracket}"), ("]", "${closebracket}"),
            ("\x1b${openbracket}", "\x1b["),  # fix problems when coloring at view.py
            ("}", "${closebrace}"),
            ("#", "${hash}"), ("_", "${underscore}"), ("\"", "${quot}"),
            ("|", "${pipe}"), ("=", "${eq}"), ("~", "${tilde}"),
            (":", "colon"), ("!", "${bang}"), ("/", "${slash}"),
            ("&", "${amp}"), ("(", "${openparen}"), (")", "${closeparen}"),
            (" ", "${space}"), ("\t", "${tab}"), ("\n", "${newline}")
    ])

    def operations(self):
        return common.FiletypeOperations(TextualPatternChecker,
                TextualPatternParser, TextualPatternPrinter)

INFO = TextualPatternInfo()



class TextualPatternChecker(common.AbstractChecker):
    r"""Checks whether input is in TextualPattern format."""
    def matches_header(self, strict):
        # TODO add detection code
        return not strict



class TextualPatternParser(common.AbstractTxtParser):
    r"""Instances of this class parse the TextualPattern format,
    calling the `handler` for each pattern that is parsed.
    """
    valid_categories = ["patterns"]

    RE_OPENER = re.compile(r"(?P<paren>\w*\()|(?P<bracket>\[)|(?P<pipe>\|)| |(?P<literal>\w+)")
    RE_BRACKET_ELEM = re.compile(r" *(?P<prop>\S+?)(?P<neg>!)?(?P<eq>=|~|≈≈)(?P<val>\S+) *")
    RE_BRACE_ELEM = re.compile(r" *(?P<key>\w+)=(?P<val>\S+) *")
    REVERSE = {"[":"]", "(":")", "{":"}"}


    def __init__(self, encoding='utf-8'):
        super(TextualPatternParser,self).__init__(encoding)
        self.category = "patterns"

    def _parse_line(self, line, ctxinfo):
        r"""Parse a single line (one pattern per line)."""
        self.line = line
        self.ctxinfo = self.ctxinfo.with_column_range(0, len(self.line))
        try:
            self.ctxinfo, p = self.parse_globbed_in_paren(self.ctxinfo, "seq(", None, {})
        except MwetoolkitInternalSkipSyntax:
            pass  # Skip this bad line and try the next one
        else:
            self.handler.handle_pattern(p, p.ctxinfo)


    def glob_first_child(self, cur_ctxinfo, opener_stack):
        r"""Return a more specific ctxinfo that globs the first
        child inside `cur_ctxinfo`, assuming the given opener stacks.
        Updates `cur_ctxinfo` to point to the char after this child.
        """
        i = cur_ctxinfo.colnum.beg
        while i < cur_ctxinfo.colnum.end:
            c = self.line[i]
            if c == "\\":
                i += 2; continue

            elif c in "({[":
                opener_stack.append(c)
            elif opener_stack[-1] == c:  # Allow other elems in stack
                opener_stack.pop()
            elif c in ")}]":
                if self.REVERSE[opener_stack[-1]] == c:
                    opener_stack.pop()
                else:
                    err_ctxinfo = cur_ctxinfo.with_column_range(cur_ctxinfo.colnum.beg, i+1)
                    err_ctxinfo.warn("Unmatched char `{char}`", char=c)

            if not opener_stack:
                child_ctxinfo = cur_ctxinfo.with_column_range(cur_ctxinfo.colnum.beg, i)
                cur_ctxinfo = cur_ctxinfo.with_column_range(i+1, cur_ctxinfo.colnum.end)
                return cur_ctxinfo, child_ctxinfo  # Found the end of the globbed piece

            i += 1

        self.warn_syntax(cur_ctxinfo, "Line ended before `{reversed}`",
                reversed=self.REVERSE[opener_stack[-1]])


    def match_and_advance(self, cur_ctxinfo, regex):
        r"""Match against compiled regex and return (new_ctxinfo, Match) for token.
        Returns (cur_ctxinfo, None) on error.
        """
        ret = regex.match(self.line, cur_ctxinfo.colnum.beg,
                cur_ctxinfo.colnum.end)
        if ret:
            cur_ctxinfo = cur_ctxinfo.with_column_range(ret.end(), cur_ctxinfo.colnum.end)
        return cur_ctxinfo, ret


    def parse_globbed_in_paren(self, cur_ctxinfo,
            paren_prefix, cur_attrib_ctxinfo, cur_attribs):
        r"""Parse the contents inside a `seq(blablala...)` or
        `either(blablabla...)`, possibly followed by {key=value} pairs.
        Return (new_ctxinfo, pattern).

        Arguments:
        @param cur_ctxinfo: the ctxinfo for the contents *inside parens*.
        @param paren_prefix: one of "seq(" or "either(" or "(".
        @param cur_attrib_ctxinfo: the ctxinfo for the contents inside the {k=v}
        pairs that come right after closing the parens around `cur_ctxinfo`.
        @param cur_attribs: the contents inside {k=v} pairs.
        """
        initial_cur_ctxinfo = cur_ctxinfo
        children = []
        while cur_ctxinfo.colnum.beg < cur_ctxinfo.colnum.end:
            cur_ctxinfo, opener = self.match_and_advance(cur_ctxinfo, self.RE_OPENER)
            if not opener:
                cur_ctxinfo.update_colnum(cur_ctxinfo.colnum.beg, None)
                self.warn_syntax(cur_ctxinfo, "Unexpected character `{char}`",
                        char=self.line[cur_ctxinfo.colnum.beg])

            # Handle: [surface=foo pos=V]
            if opener.group("bracket"):
                cur_ctxinfo, child_ctxinfo = self.glob_first_child(cur_ctxinfo, ["["])
                w_attrib_ctxinfo, w_attribs = self.read_attribs(cur_ctxinfo)
                w = self.parse_in_word(child_ctxinfo)
                w = self.added_attribs(w, w_attrib_ctxinfo, w_attribs)
                children.append(w)

            # Handle: (blablaba...)
            elif opener.group("paren"):
                cur_ctxinfo, child_ctxinfo = self.glob_first_child(cur_ctxinfo, ["("])
                p_attrib_ctxinfo, p_attribs = self.read_attribs(cur_ctxinfo)
                child_ctxinfo, p = self.parse_globbed_in_paren(child_ctxinfo,
                        opener.group("paren"), p_attrib_ctxinfo, p_attribs)
                children.append(p)

            # Handle `|` inside a (blablaba...)
            elif opener.group("pipe"):
                if paren_prefix not in ("(", "either("):
                    cur_ctxinfo.warn("Alternative list inside non-`either` block")
                paren_prefix = "either("

            # Handle a literal, such as `walk` or `NPP`
            elif opener.group("literal"):
                child_ctxinfo = cur_ctxinfo.with_column_range(opener.start(), opener.end())
                cur_ctxinfo = cur_ctxinfo.with_column_range(child_ctxinfo.colnum.end, cur_ctxinfo.colnum.end)
                lit_attrib_ctxinfo, lit_attribs = self.read_attribs(cur_ctxinfo)
                xval = re.escape(opener.group("literal"))
                w = patternlib.WordPattern(child_ctxinfo, None)
                # TODO when we have a to_bracketpattern properly implemented,
                # use that here, to avoid problems if we ever fail to actually
                # build what we say we are building...
                if xval.isupper():
                    child_ctxinfo.info("Interpreting `{input}` as [pos~/{value}.*/i]",
                            input=opener.group("literal"), value=xval)
                    value = patternlib.RegexProp(child_ctxinfo, xval+".*", "i")
                    w.add_prop("pos", value, False)
                else:
                    child_ctxinfo.info("Interpreting `{input}` as [lemma=\"{value}\"]",
                            input=opener.group("literal"), value=xval)
                    value = patternlib.LiteralProp(child_ctxinfo, xval)
                    w.add_prop("lemma", value, False)
                w = self.added_attribs(w, lit_attrib_ctxinfo, lit_attribs)
                children.append(w)

        if paren_prefix == "either(":
            children = [(c if isinstance(c, patternlib.SequencePattern)
                else patternlib.SequencePattern(c.ctxinfo, None, None, False, [c]))
                for c in children]
            p = patternlib.EitherPattern(cur_ctxinfo, children)
            return self.added_attribs(p, cur_attrib_ctxinfo, cur_attribs)
        else:
            p = patternlib.SequencePattern(initial_cur_ctxinfo, subpatterns=children)
            return self.added_attribs(p, cur_attrib_ctxinfo, cur_attribs)



    def read_attribs(self, cur_ctxinfo):
        r"""Read a list of {key=value} pairs in braces.
        Update cur_ctxinfo to point to the char after the braces.
        """
        if not self.line.startswith("{", cur_ctxinfo.colnum.beg):
            return None, {}  # No list of attributes

        cur_ctxinfo = cur_ctxinfo.with_column_range(
                cur_ctxinfo.colnum.beg+1, cur_ctxinfo.colnum.end)
        cur_ctxinfo, attrib_ctxinfo = self.glob_first_child(cur_ctxinfo, ["{"])
        attribs = {}

        while attrib_ctxinfo.colnum.beg < attrib_ctxinfo.colnum.end:
            attrib_ctxinfo, pair = self.match_and_advance(attrib_ctxinfo, self.RE_BRACE_ELEM)
            if not pair: self.warn_syntax(cur_ctxinfo, "Bad key=value pair")
            attribs[pair.group("key")] = pair.group("val")
        return attrib_ctxinfo, attribs


    def parse_in_word(self, cur_ctxinfo):
        r"""Parse the content [inside=brackets].
        @param cur_ctxinfo: a ctxinfo for the contents inside=brackets.
        """
        ret = patternlib.WordPattern(cur_ctxinfo, None)
        while cur_ctxinfo.colnum.beg < cur_ctxinfo.colnum.end:
            attrib_ctxinfo, pair = self.match_and_advance(cur_ctxinfo, self.RE_BRACKET_ELEM)
            if not pair: self.warn_syntax(cur_ctxinfo, "Bad prop=value pair")
            delimited, flags = False, ""

            xval = pair.group("val")
            xval_ctxinfo = cur_ctxinfo.copy()
            xval_ctxinfo = xval_ctxinfo.with_column_range(
                    xval_ctxinfo.colnum.beg - len(xval), xval_ctxinfo.colnum.end)

            if len(xval) >= 2 and not xval[0].isalnum():
                try:
                    xval, flags = xval[1:].rsplit(xval[0], 1)
                    delimited = True  # e.g. prop="foo" instead of prop=foo
                except ValueError:
                    self.warn_syntax(xval_ctxinfo,
                            "Missing regex end-delimiter `{delim}`", delim=xval[0])

            if pair.group("eq") == "=":
                if flags:
                    child_ctxinfo = cur_ctxinfo.with_column_range(
                            cur_ctxinfo.colnum.beg + len(xval) + 1, cur_ctxinfo.colnum.end)
                    child_ctxinfo.warn("Trailing characters after non-regex string")

                if xval.startswith("back:") and not delimited:
                    # Create BackrefProp for key=back:wid.prop
                    wid, prop = xval[5:].split(".", 1)
                    value = patternlib.BackrefProp(xval_ctxinfo,
                            self.unescape(wid), self.unescape(prop))
                else:
                    # Create LiteralProp for prop="value"
                    value = patternlib.LiteralProp(xval_ctxinfo, xval)

            elif pair.group("eq") == "≈≈":
                # Create StarredWildcardProp for prop:value
                value = patternlib.StarredWildcardProp(xval_ctxinfo, xval)

            elif pair.group("eq") == "~":
                # Create RegexProp for prop=/value/flags
                value = patternlib.RegexProp(xval_ctxinfo, xval, flags)
            ret.add_prop(self.unescape(pair.group("prop")), value, bool(pair.group("neg")))
        return ret


    def added_attribs(self, pattern, attrib_ctxinfo, attribs):
        r"""Set attributes to pattern and return it.
        If pattern does not accept an attribute, try to wrap it
        in a SequencePattern and return that instead.
        """
        if isinstance(pattern, patternlib.WordPattern):
            if not all((a in ["id"]) for a in attribs.keys()):
                p = patternlib.SequencePattern(attrib_ctxinfo, subpatterns=[pattern])
                return self.added_attribs(p, attrib_ctxinfo, attribs)
            pattern.w_strid = attribs.pop("id", None)
            return pattern

        elif isinstance(pattern, patternlib.EitherPattern):
            if attribs:
                p = patternlib.SequencePattern(attrib_ctxinfo, subpatterns=[pattern])
                return self.added_attribs(p, attrib_ctxinfo, attribs)
            return pattern

        elif isinstance(pattern, patternlib.SequencePattern):
            pattern.seq_strid = attribs.pop("id", None)
            pattern.repeat = attribs.pop("repeat", None)
            pattern.ignore = bool(attribs.pop("ignore", False))
            self.check_empty(attrib_ctxinfo, attribs)
            return pattern
        else:
            assert False


    def check_empty(self, cur_ctxinfo, attribs):
        r"""Check whether all `attribs` values have been popped."""
        for k in attribs:
            cur_ctxinfo.warn("Ignoring unknown attribute `{attr}`", attr=k)


    def warn_syntax(self, cur_ctxinfo, msg, **kwargs):
        r"""Call cur_ctxinfo.warn and then raise MwetoolkitInternalSkipSyntax."""
        cur_ctxinfo.warn(msg, **kwargs)
        raise MwetoolkitInternalSkipSyntax


class MwetoolkitInternalSkipSyntax(Exception):
    r"""Raised to skip until next pattern."""
    pass


############################################################

class TextualPatternPrinter(common.AbstractPrinter):
    """Instances can be used to print TextualPattern format."""
    valid_categories = ["patterns"]


    def handle_pattern(self, pattern, ctxinfo):
        assert isinstance(pattern, patternlib.SequencePattern), pattern
        self.handle_subpattern(pattern, ctxinfo, level0=True)
        self.add_string(ctxinfo, "\n")


    def handle_subpattern(self, pattern, ctxinfo, level0=False):
        if isinstance(pattern, patternlib.SequencePattern):
            if not level0:
                self.add_string(ctxinfo, "seq(")

            first = True
            for subp in pattern.subpatterns:
                if not first:
                    self.add_string(ctxinfo, " ")
                self.handle_subpattern(subp, ctxinfo)
                first = False

            if not level0:
                self.add_string(ctxinfo, ")")

            braces = Surrounder(self, "{", " ", "}", "")
            if pattern.seq_strid:
                braces.new_entry(ctxinfo)
                self.add_string(ctxinfo, "id=", self.escape(pattern.seq_strid))
            if pattern.ignore:
                braces.new_entry(ctxinfo)
                self.add_string(ctxinfo, "ignore=true")
            if pattern.repeat:
                braces.new_entry(ctxinfo)
                # We don't escape e.g. "{2,5}", as it would look ugly
                self.add_string(ctxinfo, "repeat=", pattern.repeat)
            braces.close(ctxinfo)

        elif isinstance(pattern, patternlib.EitherPattern):
            either = Surrounder(self, "either(", " | ", ")", "either()")
            for subp in pattern.subpatterns:
                either.new_entry(ctxinfo)
                assert isinstance(subp, patternlib.SequencePattern), subp
                if len(subp.subpatterns) == 1:
                    subp = subp.subpatterns[0]
                self.handle_subpattern(subp, ctxinfo)
            either.close(ctxinfo)

        elif isinstance(pattern, patternlib.WordPattern):
            wordprops = Surrounder(self, "[", " ", "]", "[]")
            for propsymbol, propdict in [("", pattern.positive_props), \
                    ("!", pattern.negative_props)]:
                for propname in sorted(propdict):
                    for propval in propdict[propname]:
                        wordprops.new_entry(ctxinfo)
                        self.add_string(ctxinfo, self.escape(propname), propsymbol)
                        self.print_value(ctxinfo, propval)
            wordprops.close(ctxinfo)

            braces = Surrounder(self, "{", " ", "}", "")
            if pattern.w_strid:
                braces.new_entry(ctxinfo)
                self.add_string(ctxinfo, "id=", self.escape(pattern.w_strid))
            braces.close(ctxinfo)

        else:
            pattern.ctxinfo.warn("Unable to handle `{patterntype}`",
                    patterntype=type(pattern).__name__)


    RE_SLASH = re.compile(r"(?<!\\)/")  # replace "/" => "\/"
    RE_QUOTE = re.compile(r"(?<!\\)\"")  # replace '"' => '\"'

    def print_value(self, ctxinfo, propval):
        if isinstance(propval, patternlib.RegexProp):
            value = self.RE_SLASH.sub(r"\/", propval.value)
            self.add_string(ctxinfo, "~/", value, "/", propval.flags)
        elif isinstance(propval, patternlib.LiteralProp):
            value = self.RE_QUOTE.sub(r"\"", propval.value)
            self.add_string(ctxinfo, "=\"", value, "\"")
        elif isinstance(propval, patternlib.StarredWildcardProp):
            self.add_string(ctxinfo, "≈≈", propval.value)
        elif isinstance(propval, patternlib.BackrefProp):
            self.add_string(ctxinfo, "=back:", self.escape(propval.w_strid),
                    ".", self.escape(propval.prop))
        else:
            ctxinfo.warn("Unknown prop type `{proptype}`",
                    proptype=type(propval).__name__)


class Surrounder(object):
    def __init__(self, printer, opener, separator, closer, empty):
        self.printer = printer
        self.opener = opener
        self.separator = separator
        self.closer = closer
        self.empty = empty
        self._opened = False

    def new_entry(self, ctxinfo):
        if not self._opened:
            self.printer.add_string(ctxinfo, self.opener)
            self._opened = True
        else:
            self.printer.add_string(ctxinfo, self.separator)

    def close(self, ctxinfo):
        if self._opened:
            self.printer.add_string(ctxinfo, self.closer)
        else:
            self.printer.add_string(ctxinfo, self.empty)
