#!/usr/bin/python3
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# __init__.py is part of mwetoolkit
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


import sys as _sys

# We check if the user is running python2.
# If so, we quit with a pretty error message
# (instead of failing with a SyntaxError later).
#
# Note: this only works if the importer of this
# module does not use python3-specific syntax...
if _sys.version_info.major == 2:
    try:
        import textwrap, os
        interpreter = os.path.basename(_sys.executable)
        command = _sys.argv[0]
    except Exception:
        pass  # Some corner case, just let it fail with a SyntaxError
    else:
        exit(textwrap.dedent("""\
            ################################################
            ERROR: You are using python2 instead of python3.
            ------------------------------------------------
            Instead of this command:
                {interpreter} {cmd}
            You should use this:
                {cmd}
            ################################################\
        """.format(interpreter=interpreter, cmd=command)))
