#! /usr/bin/env python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2015 Carlos Ramisch, Vitor De Araujo
#
# tagset/_common.py is part of mwetoolkit
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
that can be used when implementing a new tagset module.
"""






from .. import util



class Tagset(object):
    r"""Instances of this class represent a tagger/parser tagset.

    @param tset_name: name of this tagset
    @param content_tags: set of tags that represent content words
    @param sparse_content_tags: subset of `content_tags` for tags
    that represent sparse values (e.g. proper names, numbers)

    Other attributes:
    @param upper2canonical: mapping uppercase-name => canonical-name
    (e.g. mapping `VER:PPER` => `VER:pper` in frTreeTagger).
    """
    def __init__(self, tset_name, tset_description,
            content_tags, sparse_content_tags):
        self.tset_name = tset_name
        self.tset_description = tset_description
        sparse_content_tags = frozenset(sparse_content_tags)
        self.content_tags = frozenset(content_tags) | sparse_content_tags
        self.sparse_content_tags = sparse_content_tags
        self._setup_upper2canonical([self.content_tags])

    def _setup_upper2canonical(self, tag_collections):
        self.upper2canonical = {tag.upper(): tag \
                for tag_collection in tag_collections \
                for tag in tag_collection}


    def canonicalized(self, pos_tag):
        r"""Return canonical version of POS-tag,
        or the POS-tag itself if unknown.
        """
        return self.upper2canonical.get(pos_tag.upper(), pos_tag)


    def reduced(self, pos_tag):
        r"""Return a reduced form of `pos_tag`.
        (Note: input `pos_tag` might not be canonicalized).
        """
        return pos_tag


    def is_content(self, pos_tag):
        r"""Return True iff `pos_tag` represents a content word."""
        return self.canonicalized(self.reduced(pos_tag)) \
                in self.content_tags

    def is_sparse(self, pos_tag):
        r"""Return True iff `pos_tag` represents a sparse word
        (which should probably be normalized as some placeholder).
        """
        return self.canonicalized(self.reduced(pos_tag)) \
                in self.sparse_content_tags
