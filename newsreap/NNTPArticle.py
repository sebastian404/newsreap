# -*- coding: utf-8 -*-
#
# A representation of an actual NNTPArticle() which can contain 1 or more
# NNTPContent() objects in addition to header information.
#
# Copyright (C) 2015-2016 Chris Caron <lead2gold@gmail.com>
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

from blist import sortedset
from newsreap.NNTPContent import NNTPContent
from newsreap.NNTPBinaryContent import NNTPBinaryContent
from newsreap.NNTPAsciiContent import NNTPAsciiContent
from newsreap.NNTPHeader import NNTPHeader

# Logging
import logging
from newsreap.Logging import NEWSREAP_ENGINE
logger = logging.getLogger(NEWSREAP_ENGINE)

DEFAULT_NNTP_SUBJECT = 'unknown.file'
DEFAULT_NNTP_POSTER = 'newsreaper <news@reap.er>'


class NNTPArticle(object):
    """
    An object for maintaining retrieved article content. The primary
    reason for this object is it makes it easier to sort the results
    in memory tracking both the content downloaded (using the
    NNTPConnection.get() call along with the file stored locally on disk
    that it's responsible for.

    This function does it's best to behave like a stream. But provides
    some functions to make manipulating and merging with other articles
    easier to do.

    Articles by default assume a roll of 'attached'.  This means that
    the files written to disk are removed the second the object is
    destroyed.  This is intentional!  You can call detach() at any
    time you want but now you are responsible for cleaning up the
    filename.

    """

    def __init__(self, subject=DEFAULT_NNTP_SUBJECT,
                 poster=DEFAULT_NNTP_POSTER, groups=None, *args, **kwargs):
        """
        Initialize NNTP Article

        """
        # The Subject
        self.subject = subject

        # The Poster
        self.poster = poster

        # TODO: Rename id to article_id (readability and id is a
        # reserved keyword)
        # The Article Message-ID
        self.id = kwargs.get(u'id', '')

        # TODO: Rename no to index_no (readability)
        # The NNTP Group Index #
        try:
            self.no = int(kwargs.get(u'no', 1000))
        except:
            self.no = int(kwargs.get(u'no', 1000))

        ## The size (used with segments)
        #self._size = kwargs.get(u'size', 0)
        #if not isinstance(self._size, int):
        #    try:
        #        self._size = int(self._size)

        #    except (TypeError, ValueError):
        #        self._size = 0

        #if self._size < 0:
        #    # Since we do calculations based on this size
        #    # there is no reason we should set this value to
        #    # anything less then zero.
        #    self._size = 0

        # Track the groups this article resides in
        # This is populated for meta information when an article is
        # retrieved; but its contents are used when posting an article
        self.groups = groups
        if not self.groups:
            self.groups = set()

        elif isinstance(self.groups, basestring):
            self.groups = set((self.groups, ))

        elif isinstance(self.groups, (list, tuple)):
            self.groups = set([ x.lower() for x in self.groups])

        elif not isinstance(self.groups, set):
            raise AttributeError("Invalid group set specified.")

            # else: we simpy don't support it

        # A hash of header entries
        self.header = NNTPHeader()

        # Our body contains non-decoded content
        self.body = NNTPAsciiContent()

        # TODO: rename decoded to content because decoded implies this object
        # is only used when retrieving articles when in fact it's used for
        # posting them too.
        # Contains a list of decoded content
        self.decoded = sortedset(key=lambda x: x.key())

    def load_response(self, response):
        """
        Loads an article by it's NNTPResponse
        """
        # Our body contains non-decoded content
        self.body = response.body

        # Store decoded content
        self.decoded = response.decoded

        # Store Header
        self.header = next((d for d in self.decoded \
                    if isinstance(d, NNTPHeader)), None)

        if self.header is not None:
            # Remove Header from decoded list
            self.decoded.remove(self.header)

            # TODO: Parse header information (if present) and populate
            # some obvious fields (such as subject, groups, etc)

        return True

    def files(self):
        """
        Returns a list of the files within article
        """
        return [x.path() for x in self.decoded]

    def key(self):
        """
        Returns a key that can be used for sorting with:
            lambda x : x.key()
        """
        return '%.5d%s' % (self.no, self.id)

    def detach(self):
        """
        Detach the article stored on disk from being further managed by this
        class
        """
        for a in self.decoded:
            if isinstance(a, NNTPBinaryContent):
                a.detach()
        return

    def add(self, content):
        """
        Used for adding content to the self.decoded class
        """
        if not isinstance(content, NNTPContent):
            return False

        # duplicates are ignored in a blist and therefore
        # we just capture the length of our list before
        # and after so that we can properly return a True/False
        # value
        _bcnt = len(self.decoded)
        self.decoded.add(content)

        return len(self.decoded) > _bcnt

    def size(self):
        """
        return the total size of our decoded content
        """
        return sum(len(d) for d in self.decoded)

    def __iter__(self):
        """
        Grants usage of the next()
        """

        # Ensure our stream is open with read
        return iter(self.decoded)

    def __len__(self):
        """
        Returns the number of decoded content entries found
        """
        return len(self.decoded)

    def __lt__(self, other):
        """
        Handles less than for storing in btrees
        """
        return self.key() < other.key()

    def __str__(self):
        """
        Return a printable version of the article
        """
        return '%s' % self.id

    def __unicode__(self):
        """
        Return a printable version of the article
        """
        return u'%s' % self.id

    def __repr__(self):
        """
        Return an unambigious version of the object
        """

        return '<NNTPArticle Message-ID="%s" attachments="%d" />' % (
            self.id,
            len(self.decoded),
        )