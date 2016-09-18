# -*- encoding: utf-8 -*-
#
# Test the NNTPnzb Object
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

import sys
if 'threading' in sys.modules:
    #  gevent patching since pytests import
    #  the sys library before we do.
    del sys.modules['threading']

import gevent.monkey
gevent.monkey.patch_all()

from os.path import join
from os.path import dirname
from os.path import basename
from os.path import isfile
from os.path import abspath

try:
    from tests.TestBase import TestBase

except ImportError:
    sys.path.insert(0, dirname(dirname(abspath(__file__))))
    from tests.TestBase import TestBase

from newsreap.NNTPnzb import NNTPnzb

from newsreap.NNTPBinaryContent import NNTPBinaryContent
from newsreap.NNTPArticle import NNTPArticle
from newsreap.NNTPSegmentedPost import NNTPSegmentedPost


class NNTPnzb_Test(TestBase):
    """
    A Class for testing NNTPnzb which handles all the XML
    parsing and simple iterations over our XML files.

    """

    def test_file_parsing(self):
        """
        Test the filename parsing
        """
        # Prepare an NZB Object
        nzbobj = NNTPnzb()

        parse_str = 'Just awesome! [1/3] - "the.awesome.file.ogg" yEnc (1/1)'
        result = nzbobj.parse_subject(parse_str)
        assert result is not None
        assert isinstance(result, dict)
        assert result['desc'] == 'Just awesome!'
        assert result['index'] == 1
        assert result['count'] == 3
        assert 'size' not in result
        assert result['fname'] == 'the.awesome.file.ogg'
        assert result['yindex'] == 1
        assert result['ycount'] == 1

        parse_str = '"Quotes on Desc" - the.awesome.file.ogg yEnc (1/2)'
        result = nzbobj.parse_subject(parse_str)
        assert result is not None
        assert isinstance(result, dict)
        assert result['desc'] == 'Quotes on Desc'
        assert 'index' not in result
        assert 'count' not in result
        assert 'size' not in result
        assert result['fname'] == 'the.awesome.file.ogg'
        assert result['yindex'] == 1
        assert result['ycount'] == 2

        parse_str = 'A great description - the.awesome.file.ogg yEnc (/1)'
        result = nzbobj.parse_subject(parse_str)
        assert result is not None
        assert isinstance(result, dict)
        assert result['desc'] == 'A great description'
        assert 'index' not in result
        assert 'count' not in result
        assert 'size' not in result
        assert result['fname'] == 'the.awesome.file.ogg'
        assert 'yindex' not in result
        assert result['ycount'] == 1

        parse_str = 'Another [1/1] - "the.awesome.file.ogg" yEnc (1/1) 343575'
        result = nzbobj.parse_subject(parse_str)
        assert result is not None
        assert isinstance(result, dict)
        assert result['desc'] == 'Another'
        assert result['index'] == 1
        assert result['count'] == 1
        assert result['size'] == 343575
        assert result['fname'] == 'the.awesome.file.ogg'
        assert result['yindex'] == 1
        assert result['ycount'] == 1

        # Test escaping
        parse_str = 'Another (4/5) - &quot;the.awesome.file.ogg&quot; yEnc (3/9) 123456'
        result = nzbobj.parse_subject(parse_str, unescape=True)
        assert result is not None
        assert isinstance(result, dict)
        assert result['desc'] == 'Another'
        assert result['index'] == 4
        assert result['count'] == 5
        assert result['size'] == 123456
        assert result['fname'] == 'the.awesome.file.ogg'
        assert result['yindex'] == 3
        assert result['ycount'] == 9

    def test_general_features(self):
        """
        Open a valid nzb file and make sure we can parse it
        """
        # No parameters should create a file
        nzbfile = join(self.var_dir, 'Ubuntu-16.04.1-Server-i386.nzb')
        assert isfile(nzbfile)
        # create an object containing our nzbfile
        nzbobj = NNTPnzb(nzbfile=nzbfile)

        # Test iterations
        for article in nzbobj:
            assert isinstance(article, NNTPSegmentedPost)

        # Test iterations (with enumeration)
        for _, article in enumerate(nzbobj):
            assert isinstance(article, NNTPSegmentedPost)

            for seg in article:
                # Iterate over objects
                assert isinstance(seg, NNTPArticle)

        # However until content is loaded into memory we can't use the indexes
        try:
            _ = nzbobj[0]
            assert False
        except IndexError:
            assert True

        # Test Length (this particular file we know has 55 entries
        # If we don't hardcode this check, we could get it wrong below
        assert len(nzbobj) == 55

        # We should be able to iterate over each entry and get
        # the same count
        assert len(nzbobj) == sum(1 for c in nzbobj)

        assert nzbobj.is_valid() is True

        assert nzbobj.gid() == '8c6b3a3bc8d925cd63125f7bea31a5c9'

        # use load() to load all of the NZB entries into memory
        # This is never nessisary to do unless you plan on modifying the NZB
        # file. Those reading the tests to learn how the code works, if you're
        # only going to parse the nzbfile for it's entries, just run a
        # for loop over the object (without ever calling load() to use the
        # least amount of memory and only parse line by line on demand
        nzbobj.load()

        # Count should still 55
        assert len(nzbobj) == 55

        # Test enumeration works too
        for no, article in enumerate(nzbobj):
            assert isinstance(article, NNTPSegmentedPost)
            assert str(nzbobj[no]) == str(article)

        for no, segment in enumerate(nzbobj.segments):
            # Test equality
            assert nzbobj[no] == segment

    def test_gid_retrievals(self):
        """
        Test different variations of gid retrievals based on what
        defines a valid GID entry in an NZB File.
        """
        # No parameters should create a file
        nzbfile = join(
            self.var_dir,
            'Ubuntu-16.04.1-Server-i386-nofirstsegment.nzb',
        )
        assert isfile(nzbfile)

        nzbobj = NNTPnzb(nzbfile=nzbfile)
        assert nzbobj.is_valid() is True

        # GID Is not retrievable
        assert nzbobj.gid() is None

        # No parameters should create a file
        nzbfile = join(
            self.var_dir,
            'Ubuntu-16.04.1-Server-i386-nofile.nzb',
        )
        assert isfile(nzbfile)

        nzbobj = NNTPnzb(nzbfile=nzbfile)
        assert nzbobj.is_valid() is True

        # GID Is not retrievable
        assert nzbobj.gid() is None

        # No parameters should create a file
        nzbfile = join(
            self.var_dir,
            'Ubuntu-16.04.1-Server-i386-noindex.nzb',
        )
        assert isfile(nzbfile)

        nzbobj = NNTPnzb(nzbfile=nzbfile)
        assert nzbobj.is_valid() is True

        # GID should still be the correct first entry
        assert nzbobj.gid() == '8c6b3a3bc8d925cd63125f7bea31a5c9'

        # No parameters should create a file
        nzbfile = join(
            self.var_dir,
            'Ubuntu-16.04.1-Server-i386-badsize.nzb',
        )
        assert isfile(nzbfile)

        nzbobj = NNTPnzb(nzbfile=nzbfile)
        assert nzbobj.is_valid() is True

        # Test that we correctly store all Size 0
        # Test iterations
        for article in nzbobj:
            assert isinstance(article, NNTPSegmentedPost) is True
            assert article.size() == 0

        # Test Length (this particular file we know has 55 entries
        # If we don't hardcode this check, we could get it wrong below
        assert len(nzbobj) == 55

        # GID should still be the correct first entry
        assert nzbobj.gid() == '8c6b3a3bc8d925cd63125f7bea31a5c9'

    def test_nzbfile_generation(self):
        """
        Tests the creation of NZB Files
        """
        nzbfile = join(self.tmp_dir, 'test.nzbfile.nzb')
        payload = join(self.var_dir, 'uudecoded.tax.jpg')
        assert isfile(nzbfile) is False
        # Create our NZB Object
        nzbobj = NNTPnzb()

        # create a fake article
        segpost = NNTPSegmentedPost(basename(payload))
        content = NNTPBinaryContent(payload)

        article = NNTPArticle('testfile', groups='newsreap.is.awesome')
        # Add our Content to the article
        article.add(content)
        # now add our article to the NZBFile
        segpost.add(article)
        # now add our Segmented Post to the NZBFile
        nzbobj.add(segpost)

        # Store our file
        assert nzbobj.save(nzbfile) is True
        assert isfile(nzbfile) is True

    def test_bad_files(self):
        """
        Test different variations of bad file inputs
        """
        # No parameters should create a file
        nzbfile = join(self.var_dir, 'missing.file.nzb')
        assert not isfile(nzbfile)

        nzbobj = NNTPnzb(nzbfile=nzbfile)
        assert nzbobj.is_valid() is False
        assert nzbobj.gid() is None

        # Test Length
        assert len(nzbobj) == 0
