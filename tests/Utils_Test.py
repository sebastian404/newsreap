# -*- coding: utf-8 -*-
#
# A base testing class/library to test the Utils functions
#
# Copyright (C) 2015-2017 Chris Caron <lead2gold@gmail.com>
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

from blist import sortedset
from os.path import abspath
from os.path import dirname
from os.path import basename
from os.path import isdir
from os.path import isfile
from os.path import join
from os import chmod
from os import getcwd
import errno

import re
from itertools import chain

try:
    from tests.TestBase import TestBase

except ImportError:
    sys.path.insert(0, dirname(dirname(abspath(__file__))))
    from tests.TestBase import TestBase

from newsreap.Utils import strsize_to_bytes
from newsreap.Utils import bytes_to_strsize
from newsreap.Utils import stat
from newsreap.Utils import mkdir
from newsreap.Utils import pushd
from newsreap.Utils import find
from newsreap.Utils import rm
from newsreap.Utils import parse_list
from newsreap.Utils import parse_bool
from newsreap.Utils import parse_paths
from newsreap.Utils import scan_pylib
from newsreap.Utils import load_pylib
from newsreap.Utils import hexdump
from newsreap.Utils import dirsize

import logging
from newsreap.Logger import NEWSREAP_ENGINE
logging.getLogger(NEWSREAP_ENGINE).setLevel(logging.DEBUG)


class Utils_Test(TestBase):
    """
    Testing the Utils class
    """

    def test_strsize_n_bytes(self):
        """
        A formatting tool to make bytes more readable for an end user
        """
        # Garbage Entry
        assert strsize_to_bytes(None) is None
        assert strsize_to_bytes("0J") is None
        assert strsize_to_bytes("") is None
        assert strsize_to_bytes("totalgarbage") is None

        # Allow integers
        assert strsize_to_bytes(0) == 0
        assert strsize_to_bytes(1024) == 1024

        # Good Entries
        assert strsize_to_bytes("0B") == 0
        assert strsize_to_bytes("0") == 0
        assert strsize_to_bytes("10") == 10
        assert strsize_to_bytes("1K") == 1024
        assert strsize_to_bytes("1M") == 1024*1024
        assert strsize_to_bytes("1G") == 1024*1024*1024
        assert strsize_to_bytes("1T") == 1024*1024*1024*1024

        # Spaces between units and value are fine too
        assert strsize_to_bytes(" 0         B ") == 0
        assert strsize_to_bytes("  1       K  ") == 1024
        assert strsize_to_bytes("   1     M   ") == 1024*1024
        assert strsize_to_bytes("    1   G    ") == 1024*1024*1024
        assert strsize_to_bytes("     1 T     ") == 1024*1024*1024*1024

        # Support Byte character
        assert strsize_to_bytes("1KB") == 1024
        assert strsize_to_bytes("1MB") == 1024*1024
        assert strsize_to_bytes("1GB") == 1024*1024*1024
        assert strsize_to_bytes("1TB") == 1024*1024*1024*1024

        # Support bit character
        assert strsize_to_bytes("1Kb") == 1000
        assert strsize_to_bytes("1Mb") == 1000*1000
        assert strsize_to_bytes("1Gb") == 1000*1000*1000
        assert strsize_to_bytes("1Tb") == 1000*1000*1000*1000

        # Garbage Entry
        assert bytes_to_strsize(None) is None
        assert bytes_to_strsize('') is None
        assert bytes_to_strsize('GARBAGE') is None

        # Good Entries
        assert bytes_to_strsize(0) == "0.00B"
        assert bytes_to_strsize(1) == "1.00B"
        assert bytes_to_strsize(1024) == "1.00KB"
        assert bytes_to_strsize(1024*1024) == "1.00MB"
        assert bytes_to_strsize(1024*1024*1024) == "1.00GB"
        assert bytes_to_strsize(1024*1024*1024*1024) == "1.00TB"

        # Support strings too
        assert bytes_to_strsize("0") == "0.00B"
        assert bytes_to_strsize("1024") == "1.00KB"

    def test_stat(self):
        """
        Stat makes it easier to disect the file extension, filesystem info
        and mime information.
        """

        general_keys = ('extension', 'basename', 'filename', 'dirname')
        filesys_keys = ('created', 'modified', 'accessed', 'size')
        mime_keys = ('mime',)

        # Test a file that doesn't exist
        tmp_file = join(self.tmp_dir, 'Utils_Test.stat', 'missing_file')
        stats = stat(tmp_file)
        assert stats is None
        stats = stat(tmp_file, fsinfo=False)
        assert stats is None
        stats = stat(tmp_file, fsinfo=False, mime=False)
        assert stats is None

        # Create Temporary file 1MB in size
        tmp_file = join(self.tmp_dir, 'Utils_Test.stat', '1MB.rar')
        assert self.touch(tmp_file, size='1MB')

        stats = stat(tmp_file)

        # This check basically makes sure all of the expected keys
        # are in place and that there aren't more or less
        k_iter = chain(mime_keys, filesys_keys, general_keys)
        k_len = len(mime_keys) + len(filesys_keys) + len(general_keys)
        assert isinstance(stats, dict) is True
        assert len([k for k in k_iter if k not in stats.keys()]) == 0
        assert k_len == len(stats)

        # Filesize should actually match what we set it as
        assert bytes_to_strsize(stats['size']) == "1.00MB"

        # different OS's and variations of python can yield different
        # results.  We're trying to just make sure that we find the
        # rar keyword in the mime type
        assert(stats['mime'] == 'application/x-rar-compressed')

        # Create Temporary file 1MB in size
        tmp_file = join(self.tmp_dir, 'Utils_Test.stat', '2MB.zip')
        assert self.touch(tmp_file, size='2MB')

        stats = stat(tmp_file)

        # This check basically makes sure all of the expected keys
        # are in place and that there aren't more or less
        k_iter = chain(mime_keys, filesys_keys, general_keys)
        k_len = len(mime_keys) + len(filesys_keys) + len(general_keys)
        assert isinstance(stats, dict) is True
        assert len([k for k in k_iter if k not in stats.keys()]) == 0
        assert k_len == len(stats)

        # Filesize should actually match what we set it as
        assert bytes_to_strsize(stats['size']) == "2.00MB"

        assert re.search(
            'application/.*zip.*',
            stats['mime'],
            re.IGNORECASE,
        ) is not None

        # Test different variations
        stats = stat(tmp_file, mime=False)

        # This check basically makes sure all of the expected keys
        # are in place and that there aren't more or less
        k_iter = chain(filesys_keys, general_keys)
        k_len = len(filesys_keys) + len(general_keys)
        assert isinstance(stats, dict) is True
        assert len([k for k in k_iter if k not in stats.keys()]) == 0
        assert k_len == len(stats)

        # Test different variations
        stats = stat(tmp_file, fsinfo=False, mime=True)

        # This check basically makes sure all of the expected keys
        # are in place and that there aren't more or less
        k_iter = chain(mime_keys, general_keys)
        k_len = len(mime_keys) + len(general_keys)
        assert isinstance(stats, dict) is True
        assert len([k for k in k_iter if k not in stats.keys()]) == 0
        assert k_len == len(stats)

        # Test different variations
        stats = stat(tmp_file, fsinfo=False, mime=False)

        # This check basically makes sure all of the expected keys
        # are in place and that there aren't more or less
        k_iter = chain(general_keys)
        k_len = len(general_keys)
        assert isinstance(stats, dict) is True
        assert len([k for k in k_iter if k not in stats.keys()]) == 0
        assert k_len == len(stats)

    def test_mkdir(self):
        """
        Just a simple wrapper to makedirs, but tries a few times before
        completely aborting.

        """

        work_dir = join(self.tmp_dir, 'Utils_Test.mkdir', 'dirA')
        # The directory should not exist
        assert isdir(work_dir) is False

        # mkdir() should be successful
        assert mkdir(work_dir) is True

        # The directory should exist now
        assert isdir(work_dir) is True

        # mkdir() gracefully handles 2 calls to the same location
        assert mkdir(work_dir) is True

        # Create Temporary file 1KB in size
        tmp_file = join(self.tmp_dir, 'Utils_Test.mkdir', '2KB')
        assert self.touch(tmp_file, size='2KB')

        # Now the isdir() will still return False because there is a file
        # there now, not a directory
        assert isdir(tmp_file) is False
        # mkdir() will fail to create a directory in place of file
        assert mkdir(tmp_file) is False

        # And reference a new directory (not created yet) within
        new_work_dir = join(work_dir, 'subdir')

        # Confirm our directory doesn't exist
        assert isdir(new_work_dir) is False

        # Now we'll protect our original directory
        chmod(work_dir, 0000)

        # mkdir() will fail because of permissions, but incase it doesn't work
        # as planned, just store the result in a variable.  We'll flip our
        # permission back first
        result = mkdir(new_work_dir)

        # reset the permission
        chmod(work_dir, 0700)

        # Our result should yield a failed result
        assert result is False

        # Confirm that the directory was never created:
        assert isdir(new_work_dir) is False

    def test_pushd_popd(self):
        """
        Just a simple wrapper to makedirs, but tries a few times before
        completely aborting.

        """

        # Temporary directory to work with
        work_dir = join(self.tmp_dir, 'Utils_Test.pushd', 'newdir')

        # Ensure it doesn't already exist
        assert isdir(work_dir) is False

        # Store our current directory
        cur_dir = getcwd()

        try:
            with pushd(work_dir):
                # We should throw an exeption here and never make it to the
                # assert call below; but just incase ...
                assert False

        except OSError, e:
            # Directory doesn't exist
            assert e[0] is errno.ENOENT
            assert getcwd() == cur_dir

        # Now we'll make the directory
        with pushd(work_dir, create_if_missing=True):
            # We're in a new directory
            assert getcwd() == work_dir

        # We're back to where we were
        assert getcwd() == cur_dir

        try:
            with pushd(work_dir, create_if_missing=True):
                # We're in a new directory
                assert getcwd() == work_dir
                # Throw an exception
                raise Exception

        except Exception:
            # We're back to where we were
            assert getcwd() == cur_dir

    def test_parse_list(self):
        """
        Test parse_list function
        """
        # A simple single array entry (As str)
        results = parse_list(
            '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg,.mpeg,.vob,.iso')

        assert results == [
            '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
            '.xvid', '.wmv', '.mp4',
        ]

        # Now 2 lists with lots of duplicates and other delimiters
        results = parse_list(
            '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg .mpeg,.vob,,; ;',
            '.mkv,.avi,.divx,.xvid,.mov        .wmv,.mp4;.mpg,.mpeg,.vob,.iso')

        assert results == [
            '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
            '.xvid', '.wmv', '.mp4',
        ]

        # Now a list with extras we want to add as strings
        # empty entries are removed
        results = parse_list([
            '.divx', '.iso', '.mkv', '.mov', '', '  ', '.avi', '.mpeg',
            '.vob', '.xvid', '.mp4'], '.mov,.wmv,.mp4,.mpg')

        assert results == [
            '.divx', '.wmv', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.vob',
            '.xvid', '.mpeg', '.mp4',
        ]

        # Support Sets and Sorted Sets
        results = parse_list(
            set(['.divx', '.iso', '.mkv', '.mov', '', '  ', '.avi', '.mpeg',
                 '.vob', '.xvid', '.mp4']),
            '.mov,.wmv,.mp4,.mpg',
            sortedset(['.vob', '.xvid']),
        )
        assert results == [
            '.divx', '.wmv', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.vob',
            '.xvid', '.mpeg', '.mp4',
        ]

    def test_find_prefix(self):
        """
        Test the prefix part of the find function
        """

        # Temporary directory to work with
        work_dir = join(self.tmp_dir, 'Utils_Test.find', 'prefix')

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(join(work_dir, 'file%.3d.mkv' % idx)) is True

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(
                join(work_dir, 'file%.3d-extra.mkv' % idx),
            ) is True

        # Create some other random entries of close names (+4 files)
        assert self.touch(join(work_dir, 'File000.mkv')) is True
        assert self.touch(join(work_dir, 'File000-EXTRA.nfo')) is True
        assert self.touch(join(work_dir, 'unknown.avi')) is True
        assert self.touch(join(work_dir, 'README')) is True

        # At this point we have our temporary directory filled with 24 files.

        # Case insensitive results
        results = find(work_dir, prefix_filter='file', case_sensitive=False)
        assert isinstance(results, dict)
        assert len(results) == 22

        # Case sensitive results won't pick up on File000.mkv and
        # File000-EXTRA.nfo
        results = find(work_dir, prefix_filter='file', case_sensitive=True)
        assert isinstance(results, dict)
        assert len(results) == 20

        # We can also pass in a tuple of prefixes which will cause us to hit
        # more matches
        results = find(
            work_dir,
            prefix_filter=('file', 'File'),
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 22

        # support list of prefixes
        results = find(
            work_dir,
            prefix_filter=['file', 'File', 'unknown'],
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 23

        # support set of prefixes
        results = find(
            work_dir,
            prefix_filter=set(['file', 'File', 'unknown', 'README']),
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 24

    def test_find_suffix(self):
        """
        Test the suffix part of the find function
        """

        # Temporary directory to work with
        work_dir = join(self.tmp_dir, 'Utils_Test.find', 'suffix')

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(join(work_dir, 'file%.3d.mkv' % idx)) is True

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(
                join(work_dir, 'file%.3d-extra.mkv' % idx),
            ) is True

        # Create some other random entries of close names (+4 files)
        assert self.touch(join(work_dir, 'File000.mkv')) is True
        assert self.touch(join(work_dir, 'File000-EXTRA.nfo')) is True
        assert self.touch(join(work_dir, 'unknown.MKV')) is True
        assert self.touch(join(work_dir, 'README')) is True

        # At this point we have our temporary directory filled with 24 files.

        # Case insensitive results
        results = find(work_dir, suffix_filter='mkv', case_sensitive=False)
        assert isinstance(results, dict)
        assert len(results) == 22

        # Case sensitive results won't pick up on unknown.MKV
        results = find(work_dir, suffix_filter='mkv', case_sensitive=True)
        assert isinstance(results, dict)
        assert len(results) == 21

        # We can also pass in a tuple of suffixes which will cause us to hit
        # more matches
        results = find(
            work_dir,
            suffix_filter=('MKV', 'ME'),
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 2

        # support list of suffixes
        results = find(
            work_dir,
            suffix_filter=['nfo', 'mkv', 'README'],
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 23

        # support set of suffixes
        results = find(
            work_dir,
            suffix_filter=['nfo', 'mkv', 'MKV', 'README'],
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 24

    def test_find_regex(self):
        """
        Test the regex part of the find function
        """

        # Temporary directory to work with
        work_dir = join(self.tmp_dir, 'Utils_Test.find', 'regex')

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(join(work_dir, 'file%.3d.mpg' % idx)) is True

        # Create 10 temporary files
        for idx in range(1, 11):
            assert self.touch(
                join(work_dir, 'file%.3d-extra.mpeg' % idx),
            ) is True

        # Create some other random entries of close names (+4 files)
        assert self.touch(join(work_dir, 'File000.mpg')) is True
        assert self.touch(join(work_dir, 'File000-EXTRA.nfo')) is True
        assert self.touch(join(work_dir, 'unknown.MPEG')) is True
        assert self.touch(join(work_dir, 'README.txt')) is True

        # At this point we have our temporary directory filled with 24 files.

        # Case insensitive results
        results = find(
            work_dir,
            regex_filter='.*\.mpe?g$',
            case_sensitive=False,
        )
        assert isinstance(results, dict)
        assert len(results) == 22

        # Case sensitive results won't pick up on unknown.MPEG
        results = find(
            work_dir,
            regex_filter='.*\.mpe?g$',
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 21

        # You can also just compile the regular expression yourself and pass
        # that in if you'd rather
        _regex = re.compile('.*\.TXT', re.I)
        results = find(work_dir, regex_filter=_regex)
        assert isinstance(results, dict)
        # Case insensitive re.I was passed in, so we will match on README.txt
        assert len(results) == 1

        # Invalid regular expressions will always yield a None return value
        # and not a dictionary.
        assert find(work_dir, regex_filter='((((()') is None

        # You can chain multiple regular expressions together using
        # sets, lists and tuples; here is a list example
        results = find(
            work_dir,
            regex_filter=[
                '.*\.mpe?g$',
                '.*\.txt$',
            ],
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 22

        # tuple example
        results = find(
            work_dir,
            regex_filter=(
                '.*\.mpe?g$',
                '.*\.txt$',
                '^unknown.*',
            ),
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 23

        # Finally, here is a set() example
        results = find(
            work_dir,
            regex_filter=(
                '.*\.mpe?g$',
                '.*\.nfo$',
                '.*\.txt$',
                '^unknown.*',
            ),
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 24

    def test_find_depth(self):
        """
        Test the regex part of the find function
        """

        # Temporary directory to work with
        work_dir = join(self.tmp_dir, 'Utils_Test.find', 'depth')

        # Create some depth to test within:
        #   /depth01.jpeg
        #   /level02/depth02.jpeg
        #   /level02/level03/depth03.jpeg
        #   /level02/level03/level04/depth04.jpeg
        #   ...
        work_dir_depth = work_dir
        assert self.touch(join(work_dir, 'depth01.jpeg')) is True
        for idx in range(2, 11):
            work_dir_depth = join(work_dir_depth, 'level%.2d' % idx)
            assert self.touch(
                join(work_dir_depth, 'depth%.2d.jpeg' % idx),
            ) is True

        # Just to give us a ballpark of the total files (and depth) we're
        # looking at here:
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 10

        # Search only the first level
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            max_depth=1,
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert 'depth01.jpeg' == basename(results.keys()[0])

        # Search from the fifth level on
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            min_depth=5,
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        # Why 6? Because we're starting at (and including) the 5th level
        # level 5  = +1
        # level 6  = +1 (2)
        # level 7  = +1 (3)
        # level 8  = +1 (4)
        # level 9  = +1 (5)
        # level 10 = +1 (6)
        assert len(results) == 6
        # Double check that our files are infact in relation to the depth
        # we expect them to be at:
        for idx in range(5, 11):
            assert 'depth%.2d.jpeg' % idx \
                    in [basename(x) for x in results.keys()]

        # Search only the second level
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            min_depth=2,
            max_depth=2,
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert 'depth02.jpeg' == basename(results.keys()[0])

        # Search the 3rd and 4th levels only
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            min_depth=3,
            max_depth=4,
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        assert len(results) == 2
        assert 'depth03.jpeg' in [basename(x) for x in results.keys()]
        assert 'depth04.jpeg' in [basename(x) for x in results.keys()]

        # if min_depth > max_depth you'll get a None type
        assert find(
            work_dir,
            suffix_filter='.jpeg',
            min_depth=5,
            max_depth=4,
            case_sensitive=True,
        ) is None

        # Create some more depth levels to test that we scan all directories of
        # all levels when requested.
        #   /level02b/depth02b.jpeg
        #   /level02b/level03b/depth03.jpeg
        #   /level02b/level03b/level04b/depth04.jpeg
        #   ...

        # This runs in parallel with the directories already created above
        work_dir_depth = work_dir
        for idx in range(2, 11):
            work_dir_depth = join(work_dir_depth, 'level%.2db' % idx)
            assert self.touch(
                join(work_dir_depth, 'depth%.2d.jpeg' % idx),
            ) is True

        # Just to give us a ballpark of the total files (and depth) we're
        # looking at here:
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        # Not 20 (because no extra file was created on depth level 1)
        assert len(results) == 19

        # Search only the second level
        results = find(
            work_dir,
            suffix_filter='.jpeg',
            min_depth=2,
            max_depth=2,
            case_sensitive=True,
        )
        assert isinstance(results, dict)
        # there should be 2 now
        assert len(results) == 2

        for k in results.keys():
            # 2 directories now each with the same filename
            assert 'depth02.jpeg' == basename(k)

        # Create a 12th and 13th level; but store nothing in the 12th
        work_dir_12 = join(work_dir_depth, 'level%.2d' % 12)

        assert mkdir(work_dir_12) is True
        work_dir_13 = join(work_dir_12, 'level%.2d' % 13)
        assert self.touch(
            join(work_dir_13, 'depth%.2d.jpeg' % 13),
        ) is True

        # Search the 12th level which contains no files
        # (the 13th does but we're explicity not looking there)
        results = find(
            work_dir_12,
            min_depth=1,
            max_depth=1,
        )
        # even with no results we should get a dictionary response
        assert isinstance(results, dict)
        # there should be 0 now
        assert len(results) == 0

    def test_rm(self):
        """
        rm is just a simple wrapper for unlink and rmtree.
        it returns True if it was successful and false if it failed.

        it's equivalent to rm -rf <path>

        """

        work_dir = join(self.tmp_dir, 'Utils_Test.rm')
        # The directory should not exist
        assert isdir(work_dir) is False

        # mkdir() should be successful
        assert mkdir(work_dir) is True

        # Remove the directory
        assert rm(work_dir) is True

        # The directory should not exist
        assert isdir(work_dir) is False

        # Temporary directory
        tmp_dir = join(work_dir, 'testdir', 'test01')
        tmp_file = join(tmp_dir, 'test.file.ogg')

        # create a file in it
        assert self.touch(tmp_file, perm=0000) is True

        # The directory should exist
        assert isdir(tmp_dir) is True
        assert isfile(tmp_file) is True

        # Remove the directory
        assert rm(tmp_dir) is True

        # The directory nor the file should no longer exist
        assert isdir(tmp_dir) is False
        assert isfile(tmp_file) is False

        # Create the file again
        assert self.touch(tmp_file, perm=0000) is True
        assert isfile(tmp_file) is True
        # Set the directory it resides in with bad permissions
        chmod(tmp_dir, 0000)

        # The directory should exist
        assert isdir(tmp_dir) is True

        # Remove the directory; just using rmtree() in this circumstance would
        # cause an exception to be thrown, however rm() should handle this
        # gracefully
        assert rm(tmp_dir) is True

        # The directory nor the file should no longer exist
        assert isdir(tmp_dir) is False
        assert isfile(tmp_file) is False

        # Now just to repeat this step with a directory without permissions
        # within a directory without permissions

        tmp_dir_level2 = join(tmp_dir, 'level02')
        tmp_file = join(tmp_dir_level2, 'test.file.ogg')
        # create a file in it
        assert self.touch(tmp_file, perm=0000) is True

        # The directories and file should exist now
        assert isdir(tmp_dir) is True
        assert isdir(tmp_dir_level2) is True
        assert isfile(tmp_file) is True

        # Set the directory it resides in with bad permissions
        chmod(tmp_dir_level2, 0000)
        chmod(tmp_dir, 0000)

        # Remove the directory; just using rmtree() in this circumstance would
        # cause an exception to be thrown, however rm() should handle this
        # gracefully
        assert rm(tmp_dir) is True

        # The directory nor the file should no longer exist
        assert isdir(tmp_dir) is False
        assert isdir(tmp_dir_level2) is False
        assert isfile(tmp_file) is False

        # Support just the removal of files too (not just directories)
        assert self.touch(tmp_file, perm=0000) is True
        assert isfile(tmp_file) is True
        assert rm(tmp_file) is True
        assert isfile(tmp_file) is False

    def test_parse_bool(self):
        """
        tests the parse_bool function which allows string interpretations
        of what could be a Python True/False value.
        """
        assert parse_bool('Enabled', None) is True
        assert parse_bool('Disabled', None) is False
        assert parse_bool('Allow', None) is True
        assert parse_bool('Deny', None) is False
        assert parse_bool('Yes', None) is True
        assert parse_bool('YES', None) is True
        assert parse_bool('Always', None) is True
        assert parse_bool('No', None) is False
        assert parse_bool('NO', None) is False
        assert parse_bool('NEVER', None) is False
        assert parse_bool('TrUE', None) is True
        assert parse_bool('tRUe', None) is True
        assert parse_bool('FAlse', None) is False
        assert parse_bool('F', None) is False
        assert parse_bool('T', None) is True
        assert parse_bool('0', None) is False
        assert parse_bool('1', None) is True
        assert parse_bool('True', None) is True
        assert parse_bool('Yes', None) is True
        assert parse_bool(1, None) is True
        assert parse_bool(0, None) is False
        assert parse_bool(True, None) is True
        assert parse_bool(False, None) is False

        # only the int of 0 will return False since the function
        # casts this to a boolean
        assert parse_bool(2, None) is True
        # An empty list is still false
        assert parse_bool([], None) is False
        # But a list that contains something is True
        assert parse_bool(['value', ], None) is True

        # Use Default (which is False)
        assert parse_bool('OhYeah') is False
        # Adjust Default and get a different result
        assert parse_bool('OhYeah', True) is True

    def test_hexdump(self):
        """converts binary content to hexidecimal in a standard
        easy to read format
        """
        # Compare File
        hexdump_file = join(self.var_dir, 'hexdump.txt')
        assert isfile(hexdump_file)

        all_characters = ''.join(map(chr, range(0, 256)))
        with open(hexdump_file, 'r') as fd_in:
            ref_data = fd_in.read()

        # when reading in content, there is a new line appeneded
        # after the last line (even if one isn't otherwise present)
        # rstrip() to just simplify the test by stripping off
        # all trailing whitespace
        assert hexdump(all_characters) == ref_data.rstrip()

    def test_dirsize(self):
        """
        tests dirsize()

        """

        # No problem if the directory doesn't exist; it's sizeless
        assert(dirsize('non/existant/directory') == 0)

        work_dir = join(self.tmp_dir, 'Utils_Test.dirsize', 'dirA')
        # The directory should not exist
        assert isdir(work_dir) is False

        # mkdir() should be successful
        assert mkdir(work_dir) is True

        # The directory should exist now
        assert isdir(work_dir) is True

        # Directory should be zero-bytes
        assert(dirsize(work_dir) == 0)

        tmp_file01 = join(work_dir, 'test01_1MB')
        assert self.touch(tmp_file01, size='1MB')

        # Directory should be 1MB in size
        assert(dirsize(work_dir) == strsize_to_bytes('1MB'))

        tmp_file02 = join(work_dir, 'test02_1MB')
        assert self.touch(tmp_file02, size='1MB')

        # Now we should have double the storage
        assert(dirsize(work_dir) == strsize_to_bytes('2MB'))

        # Lets make the directory inaccessible
        chmod(work_dir, 0000)

        # Since we can't officially calculate the total size we abort
        # internally, but instead of returning zero, we return None
        # to signify our failure
        assert(dirsize(work_dir) is None)

        # restore our accessibility
        chmod(work_dir, 0755)

        # Back to normal
        assert(dirsize(work_dir) == strsize_to_bytes('2MB'))

    def test_parse_paths(self):
        """
        tests parse_paths()
        """

        # A simple single array entry (As str)
        results = parse_paths(
            'C:\\test path with space\\and more spaces\\',
            'D:\\weird path\\more spaces\\ ',
            'D:\\weird path\\more spaces\\ G:\\save E:\\\\save_dir',
            'D:\\weird path\\more spaces\\ ',  # Duplicate is removed
            '  D:\\\\weird path\\more spaces\\\\ ',  # Duplicate is removed
            'relative path\\\\\\with\\crap\\\\ second_path\\more spaces\\ ',
            # Windows Network Paths
            '\\\\a\\network\\path\\\\ \\\\\\another\\nw\\\\path\\\\         ',
            # lists supported too
            ['relative path\\in\\list', 'second_path\\more spaces\\\\'],
            # Unsupported and ignored types
            None, 1, 4.3, True, False, -4000,
        )

        assert(len(results) == 9)
        assert('D:\\weird path\\more spaces' in results)
        assert('E:\\save_dir' in results)
        assert('G:\\save' in results)
        assert('second_path\\more spaces' in results)
        assert('\\\\a\\network\\path' in results)
        assert('\\\\another\\nw\\path' in results)
        assert('relative path\\with\\crap' in results)
        assert('relative path\\in\\list' in results)
        assert('C:\\test path with space\\and more spaces' in results)

        # A simple single array entry (As str)
        results = parse_paths(
            # 3 paths identified below
            '//absolute/path /another///absolute//path/// /',
            # A whole slew of duplicates and list inside list
            '/', ['/', '/', '//', '//////', ['/', ''], ],
            'relative/path/here',
            'relative/path/here/',
            'another/relative////path///',
        )
        assert(len(results) == 5)
        assert('/absolute/path' in results)
        assert('/another/absolute/path' in results)
        assert('another/relative/path' in results)
        assert('/' in results)
        assert('relative/path/here' in results)

        results = parse_paths(
            '/home/username/News/TVShows, /home/username/News/Movies',
        )
        assert(len(results) == 2)
        assert('/home/username/News/TVShows' in results)
        assert('/home/username/News/Movies' in results)

        # A simple single array entry (As str)
        results = parse_paths(
            '\\\\ht-pc\\htpc_5tb\\Media\\TV, '
            '\\\\ht-pc\\htpc_5tb\\Media\\Movies, '
            '\\\\ht-pc\\htpc_2tb\\Media\\TV, '
            '\\\\ht-pc\\htpc_2tb\\Media\\Movies',
        )
        assert(len(results) == 4)
        assert('\\\\ht-pc\\htpc_5tb\\Media\\TV' in results)
        assert('\\\\ht-pc\\htpc_5tb\\Media\\Movies' in results)
        assert('\\\\ht-pc\\htpc_2tb\\Media\\TV' in results)
        assert('\\\\ht-pc\\htpc_2tb\\Media\\Movies' in results)

        # comma is a delimiter
        results = parse_paths('path1, path2 ,path3,path4')
        assert(len(results) == 4)
        assert('path1' in results)
        assert('path2' in results)
        assert('path3' in results)
        assert('path4' in results)

    def test_scan_pylib(self):
        """
        tests scanning for python packages

        """
        # A working dir
        work_dir = join(self.tmp_dir, 'Utils_Test.scan_pylib')

        # The directory should not exist
        assert(isdir(work_dir) is False)

        # mkdir() should be successful
        assert(mkdir(work_dir) is True)

        # The directory should now exist
        assert(isdir(work_dir) is True)

        # Nothing in directory so we return nothing
        assert(scan_pylib(work_dir) == {})

        # We will ignore these types of files
        assert(self.touch(join(work_dir, '__init__.py')))
        assert(scan_pylib(work_dir) == {})

        # If our directory is not accessible, we will return False signifying
        # that we couldn't process the request at all.
        chmod(work_dir, 0000)
        assert(scan_pylib(work_dir) is None)

        # Restore our permissions
        chmod(work_dir, 0700)

        # Create a proper module name that is loadable
        assert(self.touch(join(work_dir, 'test01.py')))
        results = scan_pylib(work_dir)
        assert(len(results) == 1)
        assert('test01' in results)
        # Results are always a set (of directorys)
        assert(isinstance(results['test01'], set))
        # One entry
        assert(len(results['test01']) == 1)
        assert(next(iter(results['test01'])) == join(work_dir, 'test01.py'))

        # We can load content directly by file as well
        results = scan_pylib(join(work_dir, 'test01.py'))
        assert(len(results) == 1)
        assert('test01' in results)
        # Results are always a set (of directorys)
        assert(isinstance(results['test01'], set))
        # One entry
        assert(len(results['test01']) == 1)
        assert(next(iter(results['test01'])) == join(work_dir, 'test01.py'))

        # Multiple entries are handled (no duplicates are added)
        results = scan_pylib([
            work_dir,
            work_dir,
            join(work_dir, 'test01.py'),
        ])
        assert(len(results) == 1)
        assert('test01' in results)
        # Results are always a set (of directorys)
        assert(isinstance(results['test01'], set))
        # One entry (no duplicates)
        assert(len(results['test01']) == 1)
        assert(next(iter(results['test01'])) == join(work_dir, 'test01.py'))

        # We add a new file type to our mix
        assert(self.touch(join(work_dir, 'test02.py')))
        results = scan_pylib(work_dir)
        assert(len(results) == 2)
        assert('test01' in results)
        assert('test02' in results)
        # Results are always a set (of directorys)
        assert(isinstance(results['test01'], set))
        assert(isinstance(results['test02'], set))
        # One entry
        assert(len(results['test01']) == 1)
        assert(len(results['test02']) == 1)
        assert(next(iter(results['test01'])) == join(work_dir, 'test01.py'))
        assert(next(iter(results['test02'])) == join(work_dir, 'test02.py'))

    def test_load_pylib(self):
        """
        tests the dynamic loading of a python package

        """

        # A working dir
        work_dir = join(self.tmp_dir, 'Utils_Test.load_pylib')

        # Add a few modules
        assert(self.touch(join(work_dir, 'test01.py')))

        # A module we can attempt to load
        work_module = load_pylib('test01', join(work_dir, 'test01.py'))
        assert(work_module is not None)
        assert(work_module.__class__.__name__ == 'module')

        work_module = load_pylib(join(work_dir, 'test01.py'))
        assert(work_module is not None)
        assert(work_module.__class__.__name__ == 'module')

        # Now we'll protect our original directory
        chmod(work_dir, 0000)

        # We should fail to load our module
        work_module = load_pylib('test01', join(work_dir, 'test01.py'))
        assert(work_module is None)

        # Restore our permissions
        chmod(work_dir, 0700)

        # Protect our module
        chmod(join(work_dir, 'test01.py'), 0000)
        work_module = load_pylib('test01', join(work_dir, 'test01.py'))
        assert(work_module is None)

        # Restore our permissions
        chmod(join(work_dir, 'test01.py'), 0600)
