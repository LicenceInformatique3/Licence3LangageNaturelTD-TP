#!/usr/bin/python3
# -*- coding:UTF-8 -*-

# ###############################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# util.py is part of mwetoolkit
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
    Set of utility functions that are common to several scripts.
"""


import codecs
import collections
import copy
import getopt
import os
import sys
import traceback


################################################################################

verbose_on = False
debug_mode = False

common_options_usage_string = """\
-v OR --verbose
    Print messages that explain what is happening.

-D OR --debug
    Print debug information when an error occurs.
    
-h OR --help
    Print usage information about parameters and options"""


################################################################################

# Boolean flag indicating if the output should be completely deterministic.
# This should be used when running tests that will be `diff`ed against other
# files, to avoid e.g. outputting timestamps (which would generate different
# `diff` outputs each time).
deterministic_mode = ("MWETOOLKIT_DETERMINISTIC_MODE" in os.environ)


_SYS_STDERR_UTF8 = (sys.stderr)
_SYS_STDOUT_UTF8 = (sys.stdout)

# True iff last line was a `progress`-printing line
just_printed_progress_line = False


################################################################################

def set_verbose(value):
    """
        Sets whether to show verbose messages.
    """
    global verbose_on
    verbose_on = value


################################################################################

def verbose(message, end=None, printing_progress_now=False):
    """
        Prints a message if in verbose mode.
    """
    global just_printed_progress_line
    global verbose_on
    if verbose_on:
        if just_printed_progress_line and not printing_progress_now:
            print("", file=_SYS_STDERR_UTF8)
        print(message, end=end, file=_SYS_STDERR_UTF8)
        just_printed_progress_line = printing_progress_now


################################################################################

def set_debug_mode(value):
    """
        Sets whether to dump a stack trace when an unhandled exception occurs.
    """
    global debug_mode
    debug_mode = value
    if debug_mode:
        print("INFO: Debug mode on", file=_SYS_STDERR_UTF8)


################################################################################

def usage(usage_string):
    """
        Print detailed instructions about the use of this program. Each script
        that uses this function should provide a variable containing the
        usage string.
    """
    import os
    usage_string = usage_string.format(program=sys.argv[0],
            progname=os.path.basename(sys.argv[0]),
            tagsets=TagsetDescriptions(),
            common_options=common_options_usage_string,
            descriptions=FiletypeDescriptions())
    print(usage_string, end='', file=_SYS_STDOUT_UTF8)


class FiletypeDescriptions(object):
    @property
    def input(self):
        from . import filetype
        return self._descriptions(filetype.autoload().input_categ2infos)

    @property
    def output(self):
        from . import filetype
        return self._descriptions(filetype.autoload().output_categ2infos)

    def _descriptions(self, category2ftis):
        return {category: self._category_description(ftis) \
                for (category, ftis) in category2ftis.items()}

    def _category_description(self, ftis):
        return "\n    ".join("* \"{}\": {}".format(
                fti.filetype_ext, fti.description) for fti in
                sorted(ftis, key=lambda fti: fti.filetype_ext.upper())
                if fti.explicitly_visible)



class TagsetDescriptions(object):
    @property
    def all(self):
        import libs.tagset
        return "\n    ".join("* \"{}\": {}".format(
                ts.tset_name, ts.tset_description) for ts in
                sorted(libs.tagset.TAGSETS, key=lambda ts: ts.tset_name.upper()))


################################################################################

def treat_options_simplest(opts, arg, n_arg, usage_string):
    """
        Verifies that the number of arguments given to the script is correct.
        
        @param opts The options parsed by getopts. Ignored.
        
        @param arg The argument list parsed by getopts.
        
        @param n_arg The number of arguments expected for this script.
    """
    if n_arg >= 0 and len(arg) != n_arg:
        print("You must provide {n} arguments to this script" \
              .format(n=n_arg), file=_SYS_STDERR_UTF8)
        usage(usage_string)
        sys.exit(2)

    new_opts = []
    for (o, a) in opts:
        if o in ("-v", "--verbose"):
            set_verbose(True)
            verbose("INFO: Verbose mode on")
        elif o in ("-D", "--debug"):
            set_debug_mode(True)
        elif o in ("-h", "--help"):
            usage(usage_string)
            sys.exit(0)
        else:
            new_opts.append((o, a))
    opts[:] = new_opts


################################################################################

def read_options(shortopts, longopts, treat_options, n_args, usage_string):
    """
        Generic function that parses the input options using the getopt module.
        The options are then treated through the `treat_options` callback.
        
        @param shortopts Short options as defined by getopts, i.e. a sequence of
        letters (each letter followed by a colon to indicate argument).
        
        @param longopts Long options as defined by getopts, i.e. a list of 
        strings (each one ending with "=" to indicate argument).
        
        @param treat_options Callback function, receives a list of strings to
        indicate parsed options, a list of strings to indicate the parsed 
        arguments and an integer that expresses the expected number of arguments
        of this script.
    """

    for opt in ['v', 'D', 'h']:
        if opt not in shortopts:
            shortopts += opt

    for opt in ['verbose', 'debug', 'help']:
        if opt not in longopts:
            longopts += [opt]

    try:
        opts, arg = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError as err:
        # will print something like "option -a not recognized"
        ctxinfo = CmdlineContextInfo(sys.argv[1:])
        ctxinfo.error(err.msg, bad_option=err.opt or None)

    treat_options(opts, arg, n_args, usage_string)
    return arg

################################################################################

def interpret_ngram(argument):
    """
        Parses the argument of the "-n" option. This option is of the form
        "<min>:<max>" and defines the length of n-grams to extract. For 
        instance, "3:5" extracts ngrams that have at least 3 words and at most 5
        words. If you define only <min> or only <max>, the default is to 
        consider that both have the same value. The value of <min> must be at
        least 1. Generates an exception if the syntax is 
        incorrect, generates a None value if the arguments are incoherent 
        (e.g. <max> < <min>)
        
        @param argument String argument of the -n option, has the form 
        "<min>:<max>"
        
        @return A tuple (<min>,<max>) with the two integer limits, or None if
        the argument is incoherent.
    """
    try:
        if ":" in argument:
            [n_min, n_max] = argument.split(":")
            n_min = int(n_min)
            n_max = int(n_max)
        else:
            n_min = int(argument)
            n_max = int(argument)

        if n_min <= n_max:
            if n_min >= 1:
                return ( n_min, n_max )
            else:
                print("Error parsing argument for -n: <min> "
                      "must be at least 1", file=_SYS_STDERR_UTF8)
                return None
        else:
            print("Error parsing argument for -n: <min> is greater than <max>",
                  file=_SYS_STDERR_UTF8)
            return None

    except IndexError:
        return None
    except TypeError:
        return None
    except ValueError:
        return None


################################################################################

class MWEToolkitInputError(Exception):
    r"""Raised when the MWE Toolkit detects a bad user input.

    Full stack traces will not be usually provided for these errors,
    as they are NOT supposed to be internal errors in the toolkit.
    For internal errors, use any other exception class.
    """
    def __init__(self, message_template, ctxinfo, depth=0, **extra_info):
        self.message_template = message_template
        self.message = message_template.format(**extra_info)
        super(MWEToolkitInputError, self).__init__(self.message)
        self.ctxinfo = ctxinfo
        self.depth = depth
        self.extra_info = extra_info

    def warn(self):
        r"""Output "ERROR" message."""
        self.ctxinfo.raw_warn("ERROR: ", self.message)


def _error(message, depth=0, **extra_info):
    """(DEPRECATED. Use ctxinfo.error instead)"""
    SimpleContextInfo("<unknown error context>") \
            .error(message, depth=depth+1, **extra_info)

def _warn(message, **kwargs):
    """(DEPRECATED. Use ctxinfo.warn instead)"""
    SimpleContextInfo("<unknown context>").warn(message, **kwargs)

def _warn_once(message, **extra_info):
    """(DEPRECATED. Use ctxinfo.warn_once instead)"""
    _warn(message, only_once=True, **extra_info)


################################################################################

# {Warning message -> how many warnings already issued}
_WARNCOUNT = collections.Counter()

def _max_warnings():
    """(Upper bound on number of warnings that will be issued per message type)"""
    try:
        return int(os.environ["MWETOOLKIT_MAX_WARNINGS"])
    except (KeyError, TypeError, ValueError):
        if debug_mode or verbose_on:
            return float('inf')
        return 20  # Magical number: max 20 warnings


class ContextInfo(object):
    r"""Instances of this class represent a state in the execution
    (for example "parsing line 3, column 8 of file <foo>").
    ContextInfo instances are IMMUTABLE.
    """
    def info(self, message, **extra_info):
        r"""Utility method to output info message (not as bad as a warning)."""
        formatted_message = self._do_format(message, extra_info)
        self.raw_warn("INFO: ", formatted_message)

    def verbose(self, message, **extra_info):
        r"""Same as `self.info`, but silent if not `verbose_on`"""
        if verbose_on:
            return self.info(message, **extra_info)

    def warn(self, message, max_warnings=float('inf'), **extra_info):
        r"""Utility method to output warning message. Execution continues afterwards."""
        max_warnings = min(max_warnings, _max_warnings())
        _WARNCOUNT[message] += 1
        if _WARNCOUNT[message] > max_warnings:
            return  # Skip warning
        elif _WARNCOUNT[message] == max_warnings:
            message += "\n(Suppressing further warnings of this type)"

        formatted_message = self._do_format(message, extra_info)

        if debug_mode:
            print("-" * 40)
            traceback.print_stack()
        warn_type = "WARNING: "
        self.raw_warn(warn_type, formatted_message)

    def warn_once(self, message, **extra_info):
        r"""Same as `self.warn(message, max_warnings=1)`."""
        self.warn(message, max_warnings=1, **extra_info)

    def error(self, message, depth=0, **extra_info):
        """Utility method to quit with a nice error message."""
        raise MWEToolkitInputError(message, ctxinfo=self,
                depth=depth+1, **extra_info)

    def raw_warn(self, warn_type, message):
        r"""(Output specific warn-type message)"""
        global just_printed_progress_line
        if just_printed_progress_line:
            print("", file=_SYS_STDERR_UTF8)
            just_printed_progress_line = False

        submessages = message.split("\n")
        print(self.prefix(), warn_type, submessages[0],
                self.suffix(), sep="", file=_SYS_STDERR_UTF8)

        if len(warn_type) > 2:
            warn_type = "." * (len(warn_type)-2) + ": "
        for submessage in submessages[1:]:
            print(self.prefix(), warn_type, submessage,
                    sep="", file=_SYS_STDERR_UTF8)

    def prefix(self):
        r"""Return a string for the warning prefix."""
        raise NotImplementedError

    def suffix(self):
        r"""Return a string for the warning suffix."""
        return ""

    def check_all_popped(self, dict_or_properties, only_extras=False):
        r"""Check if all property keys have been popped from `dict_or_properties`."""
        for prop_name in dict_or_properties:
            if prop_name.startswith("@") or not only_extras:
                self.warn_once("Unable to handle property `{prop_name}`",
                        prop_name=prop_name)


    def _shortened(self, string, max_len=40):
        r"""Return a shortened version of given string.
        Use this when outputting user input, to avoid huge error messages.
        """
        if len(string) > max_len:
            dotdotdot = "[...]"
            return string[:max_len-len(dotdotdot)] + dotdotdot
        return string

    def _do_format(self, message, extra_info):
        r"""Essentially call `message.format(**extra_info)`."""
        extra_info = {k: self._shortened(str(v)) \
                for (k, v) in extra_info.items()}
        return message.format(**extra_info)


class SimpleContextInfo(ContextInfo):
    r"""ContextInfo object created with a given `prefix` string."""
    def __init__(self, prefix_str):
        self._prefix_str = prefix_str

    def prefix(self):
        return "{}: ".format(self._prefix_str) if self._prefix_str else ""


CONTEXTLESS_CTXINFO = SimpleContextInfo("")


class InputObjContextInfo(ContextInfo):
    r"""ContextInfo object created when reading an inputobj.

    Attributes:
    * @param parent_ctxinfo: Optional[ContextInfo]
    * @param inputobj: InputObj
    * @param mwetkparser: Optional[AbstractParser]
    """
    def __init__(self, inputobj, *, mwetkparser=None,
            linenum=None, colnum=None):
        super().__init__()
        assert inputobj is not None
        self.mwetkparser = mwetkparser
        self.inputobj = inputobj
        self._linenum = linenum or NumberRange(None, None)
        self._colnum = colnum or NumberRange(None, None)

    def with_column_range(self, colnum_beg, colnum_end):
        return InputObjContextInfo(self.inputobj,
                mwetkparser=self.mwetkparser, linenum=self.linenum,
                colnum=NumberRange(colnum_beg, colnum_end))

    def with_begpoint(self, linenum_beg, colnum_beg=None):
        return InputObjContextInfo(self.inputobj,
                mwetkparser=self.mwetkparser,
                linenum=NumberRange(linenum_beg, None),
                colnum=NumberRange(colnum_beg, None))

    def with_endpoint(self, linenum_end, colnum_end):
        return InputObjContextInfo(self.inputobj,
                mwetkparser=self.mwetkparser,
                linenum=self.linenum.with_end(linenum_end),
                colnum=self.colnum.with_end(colnum_end))

    @property
    def linenum(self):
        r"""A NumberRange for the line number."""
        return self._linenum

    @property
    def colnum(self):
        r"""A NumberRange for the column number."""
        return self._colnum

    def _ranges(self):
        if self.linenum.beg is None: return ""
        return self.linenum._make_range() + self.colnum._make_range()

    def prefix(self):
        return "{}:{} ".format(self.inputobj.filename, self._ranges())


class NumberRange(collections.namedtuple('NumberRange', 'beg end')):
    r"""A [beg, end) range. Starts at 0. Endpoints can be None."""
    def _make_range(self):
        r"""Return a human-readable string range (starts at 1)."""
        if self.beg is None: return ""
        if self.end is None: return "{}:".format(self.beg+1)
        return "{}-{}:".format(self.beg+1, self.end+1)

    def with_beg(self, new_beg):
        r"""Return NumberRange(new_beg, self.end)"""
        return NumberRange(new_beg, self.end)

    def with_end(self, new_end):
        r"""Return NumberRange(self.beg, new_end)"""
        return NumberRange(self.beg, new_end)


# XXX remove _update and make immutable
class CmdlineContextInfo(ContextInfo):
    r"""ContextInfo object created when parsing the command-line."""
    def __init__(self, opts):
        self.opts = opts
        self.cur_opt = None
        self.cur_arg = None

    def _update(self, opt, arg):
        r"""Update e.g. (opt="--from", arg="XML") for --from="XML"."""
        self.cur_opt, self.cur_arg = opt, arg

    def iter(self, opts_list):
        r"""Yield items from opts_list updating `self' accordingly."""
        for o, a in opts_list:
            self._update(o, a)
            yield o, a
        self._update(None, None)

    def prefix(self):
        return "<cmdline>: "

    def suffix(self):
        if self.cur_opt is None: return ""
        return " (in option `{}`)".format(self.cur_opt)


    def parse_signed_int(self, value):
        r"""Useful method for parsing command-line unsigned integers.
        Handles the suffixes k, M, G, T (powers of 1000: kilo, mega...)
        and Ki, Mi, Gi, Ti (powers of 1024: kibi, mebi...)

        @return: int(value)
        """
        NUM_SUFFIX = { "k":1, "K":1, "M":2, "G":3, "T":4 }
        base, exp = 1000, 0
        try:
            if value[-1] == "i":
                value, base = value[:-1], 1024
            if value[-1] in NUM_SUFFIX:
                value, exp = value[:-1], NUM_SUFFIX[value[-1]]
            return int(value) * base**int(exp)
        except (IndexError, ValueError):
            self.error("Expected an integer; " \
                    "got `{value}`", value=value)

    def parse_uint(self, value):
        r"""Useful method for parsing command-line unsigned integers.
        @return: self.parse_signed_int(value) iff value is an int >= 0.
        """
        try:
            limit = self.parse_signed_int(value)
            if limit < 0:
                raise ValueError
        except (ValueError, MWEToolkitInputError):
            self.error("Expected a positive integer; " \
                    "got `{value}`", value=value)
        return limit


    def parse_list(self, input_list, separator, valid_values):
        r"""Useful method for parsing command-line lists of values.
        @return: input_list.split(separator).
        """
        result = []
        for value in input_list.split(separator):
            if value not in valid_values:
                self.error("Unknown list element `{value}`\n" \
                        "List must be separated by `{sep}` and " \
                        "contain values from `{valid_values}`",
                        value=value, sep=separator,
                        valid_values=" ".join(valid_values))
            result.append(value)
        return result


################################################################################

def default_exception_handler(type, value, trace):
    """The default exception handler. This replaces Python's standard behavior
    of printing a stack trace and exiting. We don't print a stack trace on some
    user input errors, unless 'debug_mode' is on.
    """
    global debug_mode
    # Restore original excepthook, to avoid loops
    sys.excepthook = sys.__excepthook__

    if isinstance(value, MWEToolkitInputError) and not debug_mode:
        here = os.path.dirname(__file__)
        tb = traceback.extract_tb(trace)[-1-value.depth]
        fname, lineno, func, text = tb
        fname = os.path.relpath(fname, '.')
        print("-" * 40, file=_SYS_STDERR_UTF8)
        value.warn()
        print("Error detected in: \"{}\" (line {})"
              .format(fname, lineno), file=_SYS_STDERR_UTF8)
        print("For a full traceback, run with --debug.", file=_SYS_STDERR_UTF8)

    else:
        # This should only happen if there is a glaring top-level bug.
        # Any exception thrown inside the mwetoolkit library will be caught
        # early and an "UNEXPECTED ERROR" message will be shown instead.
        traceback.print_exception(type, value, trace)

    if "MWETOOLKIT_DEBUG_PDB" in os.environ:
        print(("-"*60 + "\n===> Found MWETOOLKIT_DEBUG_PDB in env. "
              "Running PDB <==="), file=sys.stderr)
        import pdb
        sys.stdout = open("/dev/tty", "w")
        sys.stdin = open("/dev/tty", "r")
        pdb.post_mortem(sys.last_traceback)
    else:
        print(("Moreover, environment variable MWETOOLKIT_DEBUG_PDB "
               "not found. Quitting."), file=sys.stderr)

    if isinstance(value, KeyboardInterrupt):
        sys.exit(130)  # 128 + SIGINT; Unix standard


if not hasattr(sys, "ps1"):
    # If not running in interpreter (interactive),
    # set up pretty exception handler
    sys.excepthook = default_exception_handler


################################################################################

def dynload_modules(in_path, module_prefix, pkgname):
    r"""Load all files `in_path` that start with `module_prefix`,
    assuming package name `pkgname`.
    """
    import pkgutil
    import importlib
    for loader, name, is_pkg in pkgutil.walk_packages(in_path, prefix="."):
        if name.startswith("." + module_prefix):
            yield importlib.import_module(name, package=pkgname)


################################################################################

def pagerify():
    r"""Pipes the current script into a pager."""
    # Here we do some black magic:
    # We fork the current process, the child keeps executing in python
    # and the parent exec's a pager on top of the current tty.
    # (Note that we need the tty, so we cannot do the other way round,
    # and that is why we cannot just use `subprocess.Popen`).
    pr, pw = os.pipe()
    pid = os.fork()
    if pid != 0:
        os.close(pw)
        sys.stdin.close()  # close stdin
        os.dup2(pr, 0)  # reopen stdin=pr
        os.execlp("less", "less", "-R")
        assert False, "UNREACHABLE"

    # Else, we are in child and we write into parent `less -R`
    os.close(pr)
    sys.stdout = os.fdopen(pw, "w")


################################################################################

def redirect(from_stream, to_stream, block_size=1024, blocking=False, autoclose=True):
    r"""Redirect data from one file stream to another.
    @param block_size: The size of each `read`.
    @param blocking: If True, blocks the current thread until finished.
    @param autoclose: If True, closes `to_stream` after sending all data.
    (If the stream is not closed, some process may hang, waiting for more data).
    """
    import threading
    class RedirectingThread(threading.Thread):
        def run(self):
            while True:
                content = from_stream.read1(block_size)
                if not content:
                    # Reached EOF
                    to_stream.close()
                    return
                try:
                    to_stream.write(content)
                except IOError:
                    return  # If closed pipe, just stop
    rt = RedirectingThread()
    rt.daemon = True  # if main thread wants to die, we comply
    rt.run() if blocking else rt.start()


################################################################################

def decent_str_split(string, separator=None):
    r"""Python is absurdly inconsistent:
    >>> ("".split(), "".splitlines(), "".split("separator"))
    ([], [], [u''])

    This function does the right thing.
    >>> decent_str_split("", "separator")
    []
    """
    if not string:
        return []
    return string.split(separator)


################################################################################

def floatable(string):
    r"""Returns True if `string` can be converted to float, False otherwise"""
    try:
        float(string)
        return True
    except ValueError:
        return False
        

################################################################################

def portable_float2str(value):
    r"""Return a reasonable string representation of the float `value`.
    This string must be identical on every machine (even Macs! ...)
    """
    if isinstance(value, float):
        return "{0:.5g}".format(value)
    return str(value)


################################################################################

def to_xml(ctxinfo, obj):
    r"""Utility method to convert a single object to XML

    (This is usually used for debugging, as ft_xml should
    use a single explicit instance of XMLSerializer for all printing).
    """
    from .filetype import ft_xml
    escaper = ft_xml.INFO.escaper
    return ft_xml.XMLSerializer.to_string(obj, escaper, ctxinfo)


################################################################################

_UTF8_ENCODER = codecs.getencoder('utf-8')
_UTF8_DECODER = codecs.getdecoder('utf-8')

def utf8_unicode2bytes(uni_str):
    r"""Convert from python string to the One True Encoding (utf8 bytes)."""
    return _UTF8_ENCODER(uni_str)[0]

def utf8_bytes2unicode(byte_str):
    r"""Convert from the One True Encoding (utf8 bytes) to python string."""
    return _UTF8_DECODER(byte_str)[0]
