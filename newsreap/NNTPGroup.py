# -*- coding: utf-8 -*-
#
# NNTPGroup is an object to simplify group manipulation and shortform
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import re

# a regular expression used to break appart multiple groups
# identfied; we split on anything that isn't a valid group token
GROUP_INVALID_CHAR_RE = re.compile('[^A-Z0-9.-]+', re.I)


class NNTPGroup(object):
    """
    An object for manipulating and looking up group information.

    It handles short-form references such as a.b can be transformed
    to alt.binaries., etc.

    """
    def __init__(self, name, *args, **kwargs):
        """
        Initialize NNTP Group

        """
        # The Group Name
        self.name = NNTPGroup.normalize(name)

        if self.name is None:
            raise AttributeError(
                "Invalid group {} set specified.".format(name))

    @staticmethod
    def normalize(group):
        """
        takes a group identifier and normalizes it. For example:
        a.b.test           returns alt.binaries.test
        a.b.pictures.test  returns alt.binaries.pictures.test
        A.Binaries.test    returns alt.binaries.test

        items that can be normalized or are of an invalid group causes the
        function to return None.

        """
        # TODO

        if isinstance(group, NNTPGroup):
            # Support passing in ourselves
            return group.name

        try:
            group = GROUP_INVALID_CHAR_RE.sub('', group).lower()

        except (AttributeError, TypeError):
            # Invalid content passed in
            pass

        if not group:
            return None

        return group

    @staticmethod
    def split(groups):
        """
        Takes a string containing multiple groups and returns a normalized
        group set()
        """

        # Initialize our return result set
        result = set()

        if isinstance(groups, basestring):
            groups = GROUP_INVALID_CHAR_RE.split(groups)

        if isinstance(groups, (set, list, tuple)):
            for group in groups:
                if isinstance(group, NNTPGroup):
                    result.add(group)

                elif isinstance(group, basestring):
                    try:
                        result.add(NNTPGroup(group))

                    except AttributeError:
                        pass

                elif isinstance(group, (set, list, tuple)):
                    # a little bit of recursion
                    result |= NNTPGroup.split(group)

        return result

    def shorthand(self):
        """
        Returns the shorthand version of the group
        """

        # TODO
        return self.name

    def __str__(self):
        """
        Return a printable version of the article
        """
        return '%s' % self.name

    def __unicode__(self):
        """
        Return a printable version of the article
        """
        return u'%s' % self.name

    def __lt__(self, other):
        """
        Handles group sorting while sticking 'None' type records (if they
        exist at the end)
        """
        return self.name < other.name

    def __eq__(self, other):
        """
        Handles equality

        """
        if isinstance(other, NNTPGroup):
            return self.name == other.name

        elif isinstance(other, basestring):
            return self.name == NNTPGroup.normalize(other)

        return False

    def __hash__(self):
        """
        allows us to make use of the 'in' keyword. Hence this object can
        reside within a set, and you can still type:
        if 'alt.binaries.test' in set(NNTPGroup(), NNTPGroup())
        """
        return hash(self.name)

    def __len__(self):
        """
        Returns the length of our group
        """
        return len(self.name)

    def __repr__(self):
        """
        Return an unambigious version of the object
        """
        return '<NNTPGroup name="%s" />' % (
            self.name,
        )
