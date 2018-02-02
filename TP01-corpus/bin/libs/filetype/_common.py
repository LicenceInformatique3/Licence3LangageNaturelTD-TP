#!/usr/bin/python3
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# filetypes/_common.py is part of mwetoolkit
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
This module provides common classes and abstract base classes
that can be used when implementing a new filetype parser/printer.
"""


import io
import codecs
import collections
import itertools
import os
import re
import sys

from ..base.candidate import Candidate
from ..base.sentence import Sentence
from ..base.word import Word
from ..base.meta import Meta
from .. import util



################################################################################
####################   Filetype Info   #########################################
################################################################################


class FiletypeInfo(object):
    r"""Instances of this class represent a filetype.

    Subclasses must define the attributes:
    -- `description`
    -- `filetype_ext`
    -- `comment_prefix`  (unless `handle_comment` is overridden).
    Subclasses must also override the method `operations`.

    The attribute `escaper` must also be defined, with an instance of
    `common.Escaper`.  If the associated Parser/Printer will never call
    its method `escape`/`unescape`, the value of `escaper` may be None.
    """
    @property
    def explicitly_visible(self):
        """Whether this file type should be explicit in e.g. `-h` flags."""
        return True

    @property
    def description(self):
        """A small string describing this filetype."""
        raise NotImplementedError

    def operations(self):
        r"""Return an instance of FiletypeOperations."""
        raise NotImplementedError

    @property
    def filetype_ext(self):
        """A string with the extension for this filetype.
        Also used as a filetype hint."""
        raise NotImplementedError

    @property
    def comment_prefix(self):
        """String that precedes a commentary for this filetype."""
        raise NotImplementedError

    @property
    def escaper(self):
        """An instance of Escaper."""
        raise NotImplementedError

    def matches_filetype(self, filetype_hint):
        r"""Return whether the binary contents
        of `header` matches this filetype."""
        return self.filetype_ext == filetype_hint

    def get_checker_class(self, ctxinfo):
        """Return a subclass of AbstractChecker for this filetype."""
        return self.operations().checker_class

    def get_parser_class(self, ctxinfo):
        """Return a subclass of AbstractParser for this filetype.
        Calls ctxinfo.error if no subclass is available.
        """
        ret = self.operations().parser_class
        if ret is not None: return ret
        ctxinfo.error("Parser not implemented for {ext}; " \
                "please specify another filetype", ext=self.filetype_ext)

    def get_printer_class(self, ctxinfo):
        """Return a subclass of AbstractPrinter for this filetype.
        Calls ctxinfo.error if no subclass is available.
        """
        ret = self.operations().printer_class
        if ret is not None: return ret
        ctxinfo.error("Printer not implemented for {ext}; " \
                "please specify another filetype", ext=self.filetype_ext)



class Escaper(object):
    r"""An object that has the methods `escape` and `unescape`
    which are used to (un)escape unicode strings.

    The first pair in `escape_pairs` must be a substring of the prefix,
    otherwise we would have ambiguity problems when replacing substrings.

    Example:
    >>> Escaper("${", "}",  [("$", "${dollar}"), ("#", "${hash}")])
    """
    def __init__(self, prefix, suffix, escape_pairs):
        assert escape_pairs[0][0] in prefix, \
                "First escape pair must have " + prefix
        self._prefix, self._suffix = prefix, suffix
        self._escape_pairs = escape_pairs

    def escape(self, string):
        r"""Convert e.g. "foo#bar" => "foo${hash}bar"."""
        for unescaped, escaped in self._escape_pairs:
            if unescaped in string:
                string = string.replace(unescaped, escaped)
        return string

    def unescape(self, string):
        r"""Convert e.g. "foo${hash}bar" => "foo#bar"."""
        if self._prefix in string:
            # We reverse the order in order to unescape the first pair last
            for unescaped, escaped in reversed(self._escape_pairs):
                string = string.replace(escaped, unescaped)
        return string



class FiletypeOperations(collections.namedtuple("FiletypeOperations",
        "checker_class parser_class printer_class")):
    r"""A named triple (checker_class, parser_class, printer_class):
    -- checker_class: A subclass of AbstractChecker.
    -- parser_class: Either None or a subclass of AbstractParser.
    -- printer_class: Either None or a subclass of AbstractPrinter.
    """
    def __new__(cls, checker_class, parser_class, printer_class):
        assert issubclass(checker_class, AbstractChecker), checker_class
        return super(FiletypeOperations, cls).__new__(cls,
                checker_class, parser_class, printer_class)


############################################################

def autoload():
    r"""Get the singleton object of type _AutoloadedInfo."""
    global __autoloaded_info
    try:
        return __autoloaded_info
    except NameError:
        __autoloaded_info = _AutoloadedInfo()
        return __autoloaded_info

class _AutoloadedInfo:
    def __init__(self):
        # List of FiletypeInfo singletons
        here = os.path.dirname(__file__)
        self.infos = []
        for ft_module in util.dynload_modules([here], "ft_", "libs.filetype"):
            try:
                info = ft_module.INFO
            except AttributeError:
                raise AttributeError("Module at `{}` has no attribute `INFO`" \
                        .format(ft_module.__file__))
            else:
                self.infos.append(info)

        self.hint2info = {}  # Map filetype_hint -> filetype_info
        self.input_categ2infos = {}   # Map input_category -> list of filetype_infos
        self.output_categ2infos = {}  # Map output_category -> list of filetype_infos

        for fti in self.infos:
            checker, parser, printer = fti.operations()
            self.hint2info[fti.filetype_ext] = fti
            if checker is not None:
                checker.filetype_info = fti
            if parser is not None:
                parser.filetype_info = fti
                self.input_categ2infos.setdefault("ALL", []).append(fti)
                for category in parser.valid_categories:
                    self.input_categ2infos.setdefault(category, []).append(fti)
            if printer is not None:
                printer.filetype_info = fti
                self.output_categ2infos.setdefault("ALL", []).append(fti)
                for category in printer.valid_categories:
                    self.output_categ2infos.setdefault(category, []).append(fti)



################################################################################
####################   Filetype Checking   #####################################
################################################################################


class AbstractChecker(object):
    r"""Instances of this class can be used to peek at a file object
    and test whether its header matches a given filetype.
    
    Constructor Arguments:
    @param inputobj: The file object to be peeked.

    Attributes:
    @param filetype_info: Instance of FiletypeInfo
    that corresponds to the underlying filetype.
    """
    filetype_info = None

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def matches_header(self, strict):
        r"""Return whether the header of `self.fileobj`
        could be interpreted as an instance of this filetype.

        If `strict` is True, perform stricter checks and
        only return True if the header is *known* to be in
        the format of this filetype (usually, one should use
        strict=True when detecting filetypes and strict=False
        when checking for bad matches."""
        raise NotImplementedError

    def check(self, ctxinfo):
        r"""Check if `self.fileobj` belongs to this filetype
        and raise an exception if it does not."""
        if not self.matches_header(strict=False):
            ctxinfo.warn("Bad \"{filetype}\" file header",
                filetype=self.filetype_info.filetype_ext)



################################################################################
####################   File parsing   ##########################################
################################################################################


class StopParsing(Exception):
    """Raised to warn the parser that it should stop parsing the current file.
    Conceptually similar to StopIteration.
    """
    pass


# XXX not yet implemented (necessary for e.g. detecting glove format)
# ALTHOUGH: We should have a class InputObjHeader representing
# the file header, and it's this class that is passed in to
# FileFormatCheckers, and if: (a) no checker has managed to
# detect the file format and (b) at least one checker raised
# NeedMoreHeaderError; then we (1) re-assign for InputObj `iobj`
# iobj.fileobj_bytes_ok = io.BufferedReader(iobj.fileobj_bytes_ok.buffer, bigBufferSize); and (2) retry
IO_BUFFER_SIZE = 32*1024


class InputObj(object):
    r"""Object that wraps `fileobj` instances.
    Using this, we can work with input files at a higher level.

    Attributes: XXX UPDATEME
    @param fileobj: the underlying file object
    @param size: the size of this file (0 if unknown)
    @param ctxinfo: the underlying ContextInfo
    @param filepath: the full path to the underlying file
    @param filename: a pretty filename (usually, just the basename)
    """
    def __init__(self, file_descr):
        self.__open_file(file_descr)
        #XXX direct access to `fileobj` should be deprecated,
        #XXX as we always want to update `self.ctxinfo` when reading data.
        #XXX We should rename this to `self.fileobj_3_buffered`
        #XXX (But then, how do we handle e.g. the XML parser?)
        (self.is_uncompressing, self._fileobj_bytes_ok,
                self._fileobj_unicode_ok) = self.__uncompressed()
        if self.is_uncompressing:
            self._fileobj_unicode_maybecompressed = None  # avoid bugs
        self.fileobj = self._fileobj_bytes_ok  # XXX remove this and fix code that uses this
        self.size = self.__sizeof()  # XXX rename to byte_size
        self.beg, self.total = None, None
        self._lineno = 0
        self._progress_lower_bound = 0
        self._progress_upper_bound = 0

    @property
    def filepath(self):
        r"""The full path to this file."""
        return self._filepath

    @property
    def filename(self):
        r"""The full path to this file."""
        return self._filename

    @property
    def lineno(self):
        r"""A positive integer with the current line number.
        0 if at the beginning of file.
        """
        return self._filename

    def peek_bytes(self, n=64*1024):
        r"""Peek next `n` bytes."""
        return self._fileobj_bytes_ok.peek(n)

    def read_str(self, n):
        r"""Read up to `n` bytes and return it as string."""
        ret = self._fileobj_unicode_ok.read(n)
        self._lineno += ret.count("\n")
        return ret

    def tell(self):
        r"""Return position inside current file.
        Returns 0 on failure. See also `self.size`.
        """
        try:
            return self._fileobj_bytes_maybecompressed.tell()
        except (IOError, ValueError):
            return 0

    def lines(self, *, autostrip=True):
        r"""Yield all lines in this file.
        Lines do NOT contain the final "\n".
        If autostrip==True, strips all spaces around each line.
        """
        for line in self._fileobj_unicode_ok:
            self._lineno += 1
            yield line.strip() if autostrip else line.rstrip("\n")

    def lines_with_ctxinfo(self, *, autostrip=True):
        r"""Yield (line, ctxinfo) for all lines in this file.
        Lines do NOT contain the final "\n".
        If autostrip==True, strips all spaces around each line.
        """
        for i, line in enumerate(self.lines(autostrip=autostrip)):
            yield line, util.InputObjContextInfo(self,
                    linenum=util.NumberRange(i, None))

    def generic_ctxinfo(self, mwetkparser=None):
        r"""Return a generic `ctxinfo` for this InputObj."""
        return util.InputObjContextInfo(self, mwetkparser=mwetkparser)

    def current_progress(self):
        r"""Return progress for this file."""
        new_progress = self.tell()
        if new_progress > self._progress_upper_bound:
            self._progress_lower_bound = self._progress_upper_bound
            self._progress_upper_bound = new_progress

        if self.is_uncompressing:
            # XXX UPDATE THIS FOR MWETK WITH PYTHON3 (we changed things)
            # If uncompressing, we look at the compressed position anyway,
            # as we don't know the total uncompressed size.  Since `gunzip`
            # output will be buffered and we look at the progress BEFORE
            # piping into `gunzip`, we have to wait for fileobj_2_raw
            # to request for more data in order to update... Which means
            # our progress estimates have super-coarse granularity.
            #
            # In the future, we could try to look at the internals of
            # fileobj_3_buffered (is it possible?) and slowly increment
            # progress estimates based on the buffer contents.
            return (self.beg + self._progress_lower_bound, self.total)
        return (self.beg + self._progress_lower_bound, self.total)

    def close(self):
        r"""Close underlying fileobj."""
        if hasattr(self._fileobj_bytes_maybecompressed, "close"):
            self._fileobj_bytes_maybecompressed.close()
        self._fileobj_bytes_maybecompressed = self._fileobj_unicode_maybecompressed = None
        self._fileobj_bytes_ok = self._fileobj_unicode_ok = None


    def __sizeof(self):
        r"""(Quick'n'dirty way of measuring file size; 0 if unknown)."""
        try:
            return os.fstat(self._fileobj_bytes_maybecompressed.fileno()).st_size
        except (AttributeError, ValueError, io.UnsupportedOperation):
            try:
                cur = self._fileobj_bytes_maybecompressed.tell()
                self._fileobj_bytes_maybecompressed.seek(0, os.SEEK_END)
                size = self._fileobj_bytes_maybecompressed.tell()
                self._fileobj_bytes_maybecompressed.seek(cur, os.SEEK_SET)
                return size
            except (ValueError, io.UnsupportedOperation):
                util.CONTEXTLESS_CTXINFO.warn(
                        "Input file size unknown for {filename!r}",
                        filename=self.filename)
                return 0

    def __open_file(self, descr):
        r"""(Set up self.fileobj* and friends)"""
        self._fileobj_unicode_maybecompressed = _open_utf8(descr)
        self._fileobj_bytes_maybecompressed = self._fileobj_unicode_maybecompressed.buffer
        self._filepath = self._fileobj_bytes_maybecompressed.name

        self._filename = os.path.basename(self._filepath)
        if self._filename.isdigit():
            self._filename = os.path.join(".", self._filepath)

    def ensure_encoding(self, encoding, encoding_errors):
        r"""Ensure that given encoding and encoding error-handler are being used."""
        cur_enc = self._fileobj_unicode_ok.encoding.lower().replace("-", "")
        if (encoding.lower().replace("-", "") != cur_enc
                or encoding_errors != self._fileobj_unicode_ok.errors):
            self.generic_ctxinfo().warn("Re-opening as {encoding} ({errors})",
                    encoding=encoding, errors=encoding_errors)
            self._fileobj_unicode_ok = io.TextIOWrapper(self._fileobj_bytes_ok,
                    encoding=encoding, errors=encoding_errors)


    def __uncompressed(self):
        header = self._fileobj_bytes_maybecompressed.peek(20)
        if header.startswith(b"\x50\x4b\x03\x04"):  # is ZIP?
            fileobj_unicode_ok = self.__pipe("funzip", self._fileobj_bytes_maybecompressed)
        elif header.startswith(b"\x42\x5a\x68"):  # is BZ2?
            fileobj_unicode_ok = self.__pipe("bunzip2", self._fileobj_bytes_maybecompressed)
        elif header.startswith(b"\x1f\x8b\x08"):  # is GZIP?
            fileobj_unicode_ok = self.__pipe("gunzip", self._fileobj_bytes_maybecompressed)
        else:
            return False, self._fileobj_bytes_maybecompressed, self._fileobj_unicode_maybecompressed
        return True, fileobj_unicode_ok.buffer, fileobj_unicode_ok


    def __pipe(self, command, fileobj_bytes):
        r"""Pipe `fileobj` through `command`."""
        self.generic_ctxinfo().verbose("Running file through `{cmd}`", cmd=command)
        import subprocess, threading, shlex
        command = shlex.split(command)
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        util.redirect(from_stream=fileobj_bytes, to_stream=proc.stdin, blocking=False)
        return _open_utf8(proc.stdout)


    def detect_filetype(self, filetype_hint=None):
        r"""Return a FiletypeInfo instance for given fileobj."""
        generic_ctxinfo = self.generic_ctxinfo()
        if filetype_hint in autoload().hint2info:
            return autoload().hint2info[filetype_hint]
        if filetype_hint is not None:
            generic_ctxinfo.error("Invalid filetype: {hint}", hint=filetype_hint)
        header_bytes = self.peek_bytes()
        for m in Directive.RE_BYTE_FILETYPE.finditer(header_bytes):
            ftype = m.group(1).decode("utf-8")
            headerfiletype = Directive("filetype", ftype).value
            generic_ctxinfo.verbose("Found directive for filetype `{ft_ext}`",
                    ft_ext=headerfiletype)
            return autoload().hint2info[headerfiletype]

        matched_infos = []
        for fti in autoload().infos:
            checker_class = fti.get_checker_class(generic_ctxinfo)
            if checker_class(self.fileobj).matches_header(strict=True):
                matched_infos.append(fti)
        if len(matched_infos) == 1:
            fti = matched_infos[0]
            generic_ctxinfo.verbose("Detected filetype `{ft_ext}`",
                    ft_ext=fti.filetype_ext)
            return fti
        elif len(matched_infos) > 1:
            names = "\n* ".join(x.filetype_ext for x in matched_infos)
            generic_ctxinfo.error("Cannot guess file format for: {}\nHeaders "
                   "match all these formats: \n* {}\nUse --from to specify format "
                   "manually".format(self.filename, names))
        else:
            # len(matched_infos)==0, unable to guess
            generic_ctxinfo.error("Unknown file format for: " + self.filename)


    def _parser_class(self, filetype_hint=None):
        r"""Return the Parser class (not an instance!) that can handle this file."""
        generic_ctxinfo = self.generic_ctxinfo()
        fti = self.detect_filetype(filetype_hint)
        checker_class = fti.get_checker_class(generic_ctxinfo)
        checker_class(self.fileobj).check(generic_ctxinfo)
        return fti.get_parser_class(generic_ctxinfo)


def _open_utf8(descr):
    r"""(Return utf8 file object for given argument)"""
    if descr == "-" or descr == sys.stdin:  # for stdin
        ret, sys.stdin = sys.stdin, None
        return ret
    if hasattr(descr, "buffer"):  # for TextIOBase
        return descr
    if hasattr(descr, "peek"):  # for BufferedReader
        return io.TextIOWrapper(descr, encoding="utf8")
    if isinstance(descr, io.BytesIO):
        return io.TextIOWrapper(io.BufferedReader(descr), encoding="utf8")
    if isinstance(descr, io.StringIO):
        raise ValueError("Must use BytesIO instead")

    if isinstance(descr, str):  # for file paths
        try:
            return open(descr, "r", encoding="utf8")
        except IOError:
            util.CONTEXTLESS_CTXINFO.error(
                    "Input file not found: `{filename}`",
                    filename=os.path.basename(descr))
    assert False, descr


def make_inputobjs(list_of_files):
    r"""Return a list of InputObj's to be parsed."""
    assert isinstance(list_of_files, list), list_of_files
    list_of_files = list_of_files or ["-"]
    L = [InputObj(f) if not isinstance(f, InputObj)
            else f for f in list_of_files]
    current, total = 0, sum(f.size for f in L)

    for f in L:
        f.beg, f.total = current, total
        current += f.size
    return L



class AbstractParser(object):
    r"""Base class for file parsing objects.

    Subclasses should override `_parse_file`,
    calling the appropriate `handler` methods.

    Constructor Arguments:
    @param input_files: A list of target file paths,
    or an instance of FileList.
    """
    filetype_info = None
    valid_categories = []

    def __init__(self):
        self.partial_fun = None
        self.partial_args = None
        self.partial_kwargs = None
        self._meta_handled = False

    def flush_partial_callback(self):
        r"""Finally perform the callback `self.partial_fun(...args...)`."""
        if self.partial_fun is not None:
            self.partial_fun(*self.partial_args, **self.partial_kwargs)
        self.discard_partial_callback()

    def discard_partial_callback(self):
        r"""Discard partial callback."""
        self.partial_fun = self.partial_args = self.partial_kwargs = None


    def new_partial(self, new_partial_fun, *args, **kwargs):
        r"""Add future callback `partial_fun(...args...)`."""
        self.flush_partial_callback()
        self.partial_fun = new_partial_fun
        self.partial_args = args
        self.partial_kwargs = kwargs


    def parse(self, inputobj, handler):
        r"""Parse all files with this parser.
        (Sets `self.inputobj` and `self.handler`).

        WARNING: Don't EVER call this function directly unless you
        know what you're doing. Call `filetype.parse` instead.

        @param inputobj: An instance of InputObj.
        @param handler: An instance of InputHandler.
        Callback methods will be called on `handler`.
        """
        self.inputobj = inputobj
        self.handler = handler
        self.latest_ctxinfo = self.inputobj.generic_ctxinfo(mwetkparser=self)
        self._parse_file()


    def _parse_comment(self, comment_str, ctxinfo):
        r"""Parse contents of single-line comment string and chain to 
        `handler.handle_{directive,comment}` accordingly.
        """
        comment_str = comment_str.strip()
        directive = Directive.from_string(comment_str)
        if directive:
            self.handler.handle_directive(directive, ctxinfo)
        else:
            comment_obj = Comment(comment_str)
            self.handler.handle_comment(comment_obj, ctxinfo)


    def unescape(self, string):
        r"""Return an unescaped version of `string`, using
        `self.filetype_info.escaper`."""
        return self.filetype_info.escaper.unescape(string)


    def _parse_file(self):
        r"""(Called to parse `self.inputobj`)"""
        raise NotImplementedError


################################################################################

class AbstractTxtParser(AbstractParser):
    r"""Base class for plaintext-file parsing objects.
    (For example, CONLL parsers, Moses parsers...)

    Subclasses should override `_parse_line`,
    calling the appropriate `handler` methods.

    Constructor Arguments:
    @param encoding: The encoding to use when reading files.
    """
    def __init__(self, encoding="utf-8", autostrip=False):
        super().__init__()
        self.autostrip = autostrip
        self.encoding = encoding
        self.encoding_errors = "strict"
        self.category = "<unknown-category>"

    def _parse_file(self):
        assert self.category != "<unknown-category>", \
                "Subclass should have set `self.category`"
        self.inputobj.ensure_encoding(self.encoding, self.encoding_errors)
        self.inputobj.category = self.category

        with ParsingContext(self):
            just_saw_a_comment = False

            for line, ctxinfo in self.inputobj.lines_with_ctxinfo(autostrip=self.autostrip):
                cp = self.filetype_info.comment_prefix

                if line.startswith(cp):
                    comment = line[len(cp):]
                    self._parse_comment(comment, ctxinfo)
                    just_saw_a_comment = True

                elif line == "" and just_saw_a_comment:
                    self._parse_comment("", ctxinfo)
                    just_saw_a_comment = False

                else:
                    self._parse_line(line, ctxinfo)
                    just_saw_a_comment = False

    def _parse_line(self, line, ctxinfo):
        r"""Called to parse a line of the TXT file.
        Not called for comments and SOMETIMES not called
        for empty lines.

        Subclasses may override."""
        raise NotImplementedError


class ParsingContext(object):
    r"""(Call `handler.{before,after}_file`.)"""
    EXPECTED_ERRORS = (StopParsing, IOError, util.MWEToolkitInputError)

    def __init__(self, mwetkparser):
        self.mwetkparser = mwetkparser

    def __enter__(self):
        ctxinfo = self.mwetkparser.latest_ctxinfo
        self.mwetkparser.handler.before_file(self.mwetkparser.inputobj.fileobj, ctxinfo)

    def __exit__(self, t, v, tb):
        ctxinfo = self.mwetkparser.latest_ctxinfo
        if not (v is None or isinstance(v, self.EXPECTED_ERRORS)):
            ctxinfo.raw_warn("UNEXPECTED ERROR: ", "when parsing input")

        if v is None:
            # If e.g. StopParsing was raised, we don't want
            # to append even more stuff in the output
            # (Especially since that would re-raise StopParsing
            # from inside __exit__, which will make a mess)
            self.mwetkparser.flush_partial_callback()

        if v is None or isinstance(v, StopParsing):
            self.mwetkparser.handler.after_file(self.mwetkparser.inputobj.fileobj, ctxinfo)



################################################################################
####################   Input Handlers   ########################################
################################################################################


class InputHandler(object):
    r"""Handler interface with callback methods that
    are called by the parser during its execution."""

    def before_file(self, fileobj, ctxinfo):
        r"""Called before parsing file contents."""
        pass  # By default, do nothing

    def after_file(self, fileobj, ctxinfo):
        r"""Called after parsing file contents."""
        pass  # By default, do nothing

    def finish(self, ctxinfo):
        r"""Called after parsing all files."""
        pass  # By default, do nothing

    def handle_sentence(self, sentence, ctxinfo):
        r"""Called to treat a Sentence object."""
        return self._fallback_entity(sentence, ctxinfo)

    def handle_candidate(self, candidate, ctxinfo):
        r"""Called to treat a Candidate object."""
        return self._fallback_entity(candidate, ctxinfo)

    def handle_pattern(self, pattern, ctxinfo):
        r"""Called to treat a ParsedPattern object."""
        return self._fallback_entity(pattern, ctxinfo)

    def handle_meta(self, meta_obj, ctxinfo):
        r"""Called to treat a Meta object."""
        return self._fallback(meta_obj, ctxinfo)

    def handle_embedding(self, embedding, ctxinfo):
        r"""Called to treat an Embedding object."""
        return self._fallback(embedding, ctxinfo)

    def handle_comment(self, comment, ctxinfo):
        r"""Called when parsing a comment."""
        return self._fallback(comment, ctxinfo)

    def handle_directive(self, directive, ctxinfo):
        r"""Default implementation when seeing a directive."""
        if directive.key == "filetype":
            # We don't care about the input filetype directive,
            # as we will generate an output filetype directive regardless.
            #self.handle_comment(Comment("[Converted from "
            #       + directive.value + "]"), ctxinfo)
            pass
        else:
            ctxinfo.warn_once("Unknown directive: {directive}",
                    directive=directive.key)


    def handle(self, obj, ctxinfo):
        r"""Alternative to calling `self.handle_{SOMETHING}` methods.
        Useful as a catch-all when delegating from another InputHandler.

        This method should NEVER be overridden, because is not
        even guaranteed to ever be called. Override `_fallback` instead.
        """
        return getattr(self, obj.DISPATCH)(obj, ctxinfo=ctxinfo)

    def _fallback_entity(self, entity, ctxinfo):
        r"""Called to treat a generic entity (sentence/candidate/pattern)."""
        self._fallback(entity, ctxinfo)

    def _fallback(self, obj, ctxinfo):
        r"""Called to handle anything that hasn't been handled explicitly."""
        if obj.DISPATCH == "handle_meta" and obj.is_dummy():
            return  # We don't want to complain about dummy metas
        ctxinfo.warn("Method `{dispatch}` has not been implemented",
                dispatch=obj.DISPATCH)


    def make_printer(self, ctxinfo, forced_filetype_ext,
            category=None, output=None):
        r"""Create and return a printer.
        In the case of ChainedInputHandler's, the returned printer
        should be assigned to `self.chain`.

        The printer is created based on either
        the value of `forced_filetype_ext` or ctxinfo.mwetkparser,
        and uses the category from either `category` or
        `ctxinfo.inputobj.category`.
        """
        from .. import filetype
        ext = forced_filetype_ext \
                or ctxinfo.mwetkparser.filetype_info.filetype_ext
        return filetype.printer_class(ctxinfo, ext)(ctxinfo,
                category=category or ctxinfo.inputobj.category,
                output=output)

################################################################################

class ChainedInputHandler(InputHandler):
    r"""InputHandler that delegates all methods to `self.chain`.
    """
    chain = None

    def before_file(self, fileobj, ctxinfo):
        self.chain.before_file(fileobj, ctxinfo)

    def after_file(self, fileobj, ctxinfo):
        self.chain.after_file(fileobj, ctxinfo)

    def finish(self, ctxinfo):
        self.chain.finish(ctxinfo)

    def _fallback(self, entity, ctxinfo):
        self.chain.handle(entity, ctxinfo)




################################################################################
####################   File Printers ###########################################
################################################################################


class AbstractPrinter(InputHandler):
    r"""Base implementation of a printer-style class.

    Required Constructor Arguments:
    @param ctxinfo An instance of `util.ContextInfo`.
    @param category The category of the output file. This value
    must be in the subclass's `valid_categories` list.

    Optional Constructor Arguments:
    @param output An IO-like object, such as sys.stdout
    or an instance of StringIO.
    """
    valid_categories = []

    @property
    def filetype_info(self):
        r"""The singleton instance of FiletypeInfo
        for this printer's file type. Must be overridden."""
        raise NotImplementedError
    
    def __init__(self, ctxinfo, category, output=None):
        if category not in self.valid_categories:
            raise Exception("Bad printer: {}(category=\"{}\")"
                    .format(type(self).__name__, category))
        self._category = category
        self._output = output or sys.stdout
        self._printed_filetype_directive = False
        self._scope = 0

    def before_file(self, fileobj, ctxinfo):
        r"""Begin processing by printing filetype."""
        if not self._printed_filetype_directive:
            directive = Directive("filetype",
                    self.filetype_info.filetype_ext)
            self.write_directive(directive, ctxinfo)


    def escape(self, string):
        r"""Return an escaped version of `string`, using
        `self.filetype_info.escaper`."""
        return self.filetype_info.escaper.escape(string)


    def add_string(self, ctxinfo, *strings):
        r"""Queue strings to be printed."""
        assert strings, "Must pass at least 2 args: ctxinfo, str0"
        for string in strings:
            self._output.write(string)
        return self  # enable call chaining

    def flush(self, ctxinfo):
        r"""Flush the underlying output file."""
        self._output.flush()

    def finish(self, ctxinfo):
        r"""Output any required footer and flush."""
        self.flush(ctxinfo)

    def write_directive(self, directive, ctxinfo, to_string_args={}):
        r"""Output directive. This is different from `handle_directive`
        because Printers will actually interpret those directives instead
        of just passing them along.
        """
        comment = Comment(directive.to_string(**to_string_args))
        self.handle_comment(comment, ctxinfo)
        if directive.key == "filetype":
            self._printed_filetype_directive = True

    def handle_comment(self, comment, ctxinfo):
        r"""Default implementation to output comment."""
        for c in str(comment).split("\n"):
            if c == "":
                self.add_string(ctxinfo, "\n")
            else:
                self.add_string(ctxinfo, self.filetype_info.comment_prefix + " " + c + "\n")



class ObjSerializer(object):
    r"""Printer helper for `libs/base/*.py`.
    
    @param add_string: the callback for serializing substrings
    @param escaper: an instance of `Escaper`
    """
    def __init__(self, add_string, escaper):
        self.add_string, self.escaper = add_string, escaper
        self.escape = self.escaper.escape if self.escaper else lambda x: x


    def serialize(self, ctxinfo, obj, **kwargs):
        r"""This method should call `self.add_string` to add
        string pieces which, when joined, serialize `obj`.

        By default, it delegates e.g. to `serialize_Word`
        for an instance of `Word`, and so on.
        """
        deleg = "serialize_" + type(obj).__name__
        return getattr(self, deleg)(ctxinfo, obj, **kwargs)


    @classmethod
    def to_string(cls, obj, escaper, ctxinfo):
        r"""Serialize `obj` into a string and return it."""
        ret = []
        def add_string_to_array(ctxinfo, *strings):
            ret.extend(strings)
        cls(add_string_to_array, escaper).serialize(ctxinfo, obj)
        return "".join(ret)



################################################################################
####################   Other classes   #########################################
################################################################################

class Directive(object):
    r"""Instances are objects that are passed to `handle_directive`."""
    DISPATCH = "handle_directive"

    RE_PATTERN = re.compile(
            r' *MWETOOLKIT: *(\w+)="(.*?)" *$', re.MULTILINE)
    RE_BYTE_FILETYPE = re.compile(
            br' *MWETOOLKIT: *filetype="(.*?)" *$', re.MULTILINE)

    def __init__(self, key, value):
        self.key, self.value = key, value
        assert "\"" not in value

    def __str__(self):
        return self.to_string()

    def to_string(self, around_mwetoolkit=("", "")):
        r"""Return a string such as '# MWETOOLKIT: filetype="XML"'."""
        return "{}MWETOOLKIT:{} {}=\"{}\"".format(around_mwetoolkit[0],
                around_mwetoolkit[1], self.key, self.value)

    @staticmethod
    def from_string(string):
        r"""Return an instance of Directive or None."""
        m = Directive.RE_PATTERN.match(string)
        if m is None: return None
        return Directive(*m.groups())


class Comment(object):
    r"""Instances are objects that are passed to `handle_comment`."""
    DISPATCH = "handle_comment"

    def __init__(self, contents):
        self._contents = contents

    def __str__(self):
        return self._contents


def directive_or_comment_from_string(string):
    r"""Return an instance of Directive or Comment for `string`."""
    return Directive.from_string(string) or Comment(string)
