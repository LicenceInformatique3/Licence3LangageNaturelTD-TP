#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# filetype.py is part of mwetoolkit
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
This module provides classes and methods for filetype detection,
parsing and printing.
"""

from ..base.candidate import Candidate
from ..base.sentence import Sentence
from ..base.word import Word
from .. import util

from . import _common as common


################################################################################

# Leak very common stuff into this namespace
from ._common import autoload, StopParsing, InputHandler, \
        ChainedInputHandler, Directive, InputObj


################################################################################

def parse(input_fileobjs, handler, filetype_hint=None, parser=None):
    r"""For each input fileobj, detect its file format,
    parse it and call the appropriate handler methods.

    You MUST call this function when parsing a file.
    Don't EVER call `parser.parse` directly, or you will
    suffer HARSH CONSEQUENCES. You have been warned.

    @param input_fileobjs: a list of file objects to be parsed.
    @param handler: an instance of InputHandler.
    @param filetype_hint: either None or a valid filetype_ext string.
    @param parser: either None or an instance of AbstractParser.
    """
    assert not (parser and filetype_hint), \
            "Pass filetype_hint to the ctor of the parser instead"
    assert filetype_hint is None or isinstance(filetype_hint, str)
    assert parser is None or isinstance(parser, common.AbstractParser)
    assert isinstance(handler, InputHandler), handler
    parser = parser or SmartParser(filetype_hint)

    with HandlerWrapper(handler) as hw:
        for input_file in common.make_inputobjs(input_fileobjs):
            parser.parse(input_file, hw.handler)
            input_file.close()


class HandlerWrapper(object):
    r"""Context manager that should be used at top-level
    if ever calling a method on an InputHandler.

    Don't EVER call e.g. `parser.parse` directly without having
    a HandleWrapper somewhere along the way, or you will suffer
    HARSH CONSEQUENCES.  You have been warned.
    """
    def __init__(self, handler):
        self.inner_handler = handler

    def __enter__(self):
        self.handler = FirstInputHandler(self.inner_handler)
        return self

    def __exit__(self, _t, value, tb):
        self.handler.exiting()
        suppress_exception = True
        if value is None:
            pass  # No exception; just continue
        elif isinstance(value, StopParsing):
            pass  # Exception was raised just to stop parsing, so we stop
        elif isinstance(value, IOError):
            suppress_exception = self.check_errno(value)
        else:
            return False  # re-raise exception

        try:
            ctxinfo = util.SimpleContextInfo("<parsing input files>")
            self.handler.finish(ctxinfo)
        except IOError as e:
            suppress_exception = self.check_errno(e)
        return suppress_exception

    def check_errno(self, exception):
        r"""Suppress errno=EPIPE, because it just means a closed stdout."""
        import errno
        return exception.errno == errno.EPIPE


###########################################################

class DelegatorHandler(InputHandler):
    r"""InputHandler that can delegate every call
    to another InputHandler at a later time.
    """
    def __init__(self):
        self.handlables = []

    def _fallback(self, entity, ctxinfo):
        entity.ctxinfo = ctxinfo
        self.handlables.append(entity)

    def delegate_to(self, another_handler):
        r"""Delegate every `handle` call to `another_handler`."""
        with HandlerWrapper(another_handler):
            cur_ctxinfo = None
            for handlable in self.handlables:
                if cur_ctxinfo and cur_ctxinfo.inputobj is not handlable.ctxinfo.inputobj:
                    another_handler.after_file(cur_ctxinfo.inputobj.fileobj, cur_ctxinfo)
                    cur_ctxinfo = None
                if not cur_ctxinfo:
                    cur_ctxinfo = handlable.ctxinfo
                    another_handler.before_file(cur_ctxinfo.inputobj.fileobj, cur_ctxinfo)
                another_handler.handle(handlable, handlable.ctxinfo)
            if cur_ctxinfo:
                another_handler.after_file(cur_ctxinfo.inputobj.fileobj, cur_ctxinfo)


###########################################################


def parse_entities(input_files, filetype_hint=None):
    r"""For each input file, detect its file format and parse it,
    returning a list of all parsed entities.
    
    @param input_files: a list of file objects
    whose contents should be parsed.
    @param filetype_hint: either None or a valid
    filetype_ext string.
    """
    handler = EntityCollectorHandler()
    parse(input_files, handler, filetype_hint)
    return handler.entities


class EntityCollectorHandler(InputHandler):
    r"""InputHandler that collects ALL entities together
    in `self.entities`. Will fail with an out-of-memory
    error if used on huge inputs."""
    def __init__(self):
        self.entities = []

    def _fallback_entity(self, entity, ctxinfo):
        entity.ctxinfo = ctxinfo
        self.entities.append(entity)

    def handle_comment(self, comment, ctxinfo):
        pass  # Just ignore them


################################################################################


def printer_class(ctxinfo, filetype_ext):
    r"""Return a subclass of AbstractPrinter for given filetype extension.
    If you want a printer class that automatically handles all categories,
    create an instance of AutomaticPrinterHandler instead.
    """
    try:
        return common.autoload().hint2info[filetype_ext].get_printer_class(ctxinfo)
    except KeyError:
        ctxinfo.error("Unknown file extension {ext}", ext=filetype_ext)


################################################################################


class FirstInputHandler(ChainedInputHandler):
    r"""First instance of InputHandler in a chain.
    This InputHandler does some general processing before
    passing the arguments over to the actual handlers.
    
    Tasks that are performed here:
    -- print_progress: warning the user about what
    has already been processed.
    -- handle_meta_if_absent: guarantee that `handle_meta`
    has been called when handling entities.
    """
    PROGRESS_EVERY = 100

    def __init__(self, chain):
        self.chain = chain
        self.count = 0
        self._meta_handled = False

    def _fallback_entity(self, entity, ctxinfo):
        self.count += 1
        self.print_progress(ctxinfo)
        self.chain.handle(entity, ctxinfo)
        
    def handle_candidate(self, candidate, ctxinfo):
        self.handle_meta_if_absent(ctxinfo)
        self._fallback_entity(candidate, ctxinfo)
    
    def handle_meta(self, meta, ctxinfo):
        self._meta_handled = True
        self.chain.handle_meta(meta, ctxinfo)

    def handle_meta_if_absent(self, ctxinfo):
        if not self._meta_handled:
            from ..base.meta import Meta
            self.handle_meta(Meta(None,None,None), ctxinfo)

    def print_progress(self, ctxinfo):
        if self.count % self.PROGRESS_EVERY == 0:
            a, b = ctxinfo.inputobj.current_progress()
            if b == 0:
                percent = ""
            else:
                p = round(100 * (a/b), 0)
                if p == 100.0:
                    p = 99.0  # "100%" looks fake...
                percent = " ({:2.0f}%)".format(p)

            if util.verbose_on:
                util.verbose("\r~~> Processing entity number {n}{percent}\x1b[0K"
                        .format(n=self.count, percent=percent), end="",
                        printing_progress_now=True)
                util.just_printed_progress_line = True

    def exiting(self):
        r"""(Finish the job of print_progress)."""
        if util.just_printed_progress_line:
            util.verbose("", end="")

################################################################################


class AutomaticPrinterHandler(ChainedInputHandler):
    r"""Utility subclass of ChainedInputHandler that automatically
    creates an appropriate printer by calling `make_printer` with
    information from the first input file.
    """
    def __init__(self, forced_filetype_ext):
        self.forced_filetype_ext = forced_filetype_ext

    def before_file(self, fileobj, ctxinfo):
        if not self.chain:
            self.chain = self.make_printer(ctxinfo, self.forced_filetype_ext)
        self.chain.before_file(fileobj, ctxinfo)


################################################################################


# XXX This class should just disappear, right?
class SmartParser(common.AbstractParser):
    r"""Class that detects input file formats
    and chains the work to the correct parser.
    """
    def __init__(self, filetype_hint=None):
        super(SmartParser, self).__init__()
        self.filetype_hint = filetype_hint

    def _parse_file(self):
        p_cls = self.inputobj._parser_class(self.filetype_hint)
        # Delegate the whole work to parser `p`.
        p_cls().parse(self.inputobj, self.handler)


################################################################################

if __name__ == "__main__" :
    import doctest
    doctest.testmod()  
