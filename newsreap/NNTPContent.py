# -*- coding: utf-8 -*-
#
# A container for controlling content found within an article
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

import errno
import hashlib
import weakref

from os import unlink
from os import fdopen
from os.path import join
from os.path import getsize
from os.path import basename
from os.path import dirname
from os.path import abspath
from os.path import expanduser
from os.path import isdir
from os.path import isfile
from io import BytesIO
from tempfile import mkstemp
from shutil import move as _move
from shutil import copy as _copy
from shutil import Error as ShutilError
from zlib import crc32
from blist import sortedset
from types import MethodType

from .codecs.CodecBase import DEFAULT_TMP_DIR

from .Utils import mkdir
from .Utils import pushd
from .Utils import rm
from .Utils import bytes_to_strsize
from .Utils import strsize_to_bytes
from .Utils import hexdump
from .Utils import SEEK_SET
from .Utils import SEEK_END

from .Mime import Mime
from .Mime import DEFAULT_MIME_TYPE
from .NNTPSettings import DEFAULT_BLOCK_SIZE as BLOCK_SIZE

# Logging
import logging
from .Logger import NEWSREAP_ENGINE
logger = logging.getLogger(NEWSREAP_ENGINE)


class NNTPFileMode(object):
    """
    This class makes the detction of file modes easier since
    we can compare what is set to a variable/object name
    """
    BINARY_RO = 'rb'
    BINARY_WO = 'rb+'
    BINARY_WO_TRUNCATE = 'wb'
    BINARY_RW = 'r+b'
    BINARY_RW_TRUNCATE = 'w+b'
    ASCII_R = 'r'
    ASCII_RW = 'w+'


class NNTPContent(object):
    """
    An object for maintaining retrieved article content. There can only
    be 1 article, however that 1 article can have a lot of content
    found within it.

    This identifies the content found internally within an article.

    This function does it's best to behave like a stream. But provides
    some functions to make manipulating and merging with other articles
    easier to do.

    Articles by default assume a roll of 'attached'.  This means that
    the files written to disk are removed the second the object is
    destroyed.  This is intentional!  You can call detach() at any
    time you want but now you are responsible for cleaning up the
    filename.

    """

    def __init__(self, filepath=None, part=None, total_parts=None,
                 begin=None, end=None, total_size=None, work_dir=None,
                 sort_no=10000, unique=False, *args, **kwargs):
        """
        Initialize NNTP Content

        If a filepath is specified, it can be either a stream (already opened
        file or ByteIO or StringIO class is fine too), or it can be a path to
        a filename which will be open in 'wb' mode.

        if unique is set to True, then if the file passed in already exists,
        a temporary file is used instead. But the filename info isn't lost.

        Set the unique to True when you don't want to accidently over-write
        or alter a file you may already be working with.
        """

        # The sort is used with sorting; different filetypes/content types
        # should be processed before otheres.

        # For example, the NNTPHeader() and NNTPMetaContent() area always kept
        # at the head where as NNTPAsciiContent() and NNTPBinaryContent() are
        # kept at the back.

        # The lower sort no is always processe first; but default we choose
        # a rather large sort value. Grouped content should share the same sort
        # value so that they sort their content together.
        self.sort_no = sort_no

        # A _unique string is used to ensure our file is always different
        # from another
        self._unique = False
        if unique:
            # Convert to string for indexing speed in key() calls since
            # the index is already in string format
            self._unique = str(id(self))

        # Default filename
        self.filename = ''

        # The filepath is automatically set up when the temporary file is
        # created
        self.filepath = None

        # used to track the filemode (saves on time from opening and closing
        # un-nessisarily).  These flags are set during an open and a close
        self.filemode = None

        # Prepare temporary folder we intend to use by default
        if work_dir:
            self.work_dir = abspath(expanduser(work_dir))
        else:
            self.work_dir = DEFAULT_TMP_DIR

        # A Stream object
        self.stream = None

        # Detached prevents the article from cleaning up all of
        # the data it otherwise tracks (such as the article stored
        # on disk)
        #
        # If set to None, then it hasn't been initalized yet
        self._detached = None

        # Dirty flag is set to true if a write is made; all data
        # is considered dirty until flush() is called (forcing
        # contents out of cache and onto disk)
        self._dirty = False

        # A flag that can be toggled if the data stored is
        # corrupted in some way. Such as through CRC Failing
        # or part construction (a part missing perhaps, etc)
        # if all is good, then we just leave the flag as is
        self._is_valid = False

        # Store part
        self.part = 1
        if part is not None:
            try:
                self.part = int(part)

            except (ValueError, TypeError):
                raise AttributeError(
                    "Invalid part specified (%s)." %
                    str(part),
                )

        # Tracks parts (most used for posting/encoding)
        self.total_parts = 1
        if total_parts is not None:
            try:
                self.total_parts = int(total_parts)

            except (ValueError, TypeError):
                raise AttributeError(
                    "Invalid total_parts specified (%s)." %
                    str(total_parts),
                )

            if self.total_parts < self.part:
                raise AttributeError(
                    "Invalid parts/total_parts specified (%s/%s)." % (
                        str(part), str(total_parts),
                    )
                )
        else:
            self.total_parts = self.part

        # Used for tracking the indexes (head/tail) that make
        # up the block of data this NNTPContent object represents.
        # this is only used if split() is called
        self._begin = 0
        if begin is not None:
            try:
                self._begin = int(begin)

            except (ValueError, TypeError):
                raise AttributeError(
                    "Invalid begin specified (%s)." % str(begin),
                )

        self._end = None
        if end is not None:
            try:
                self._end = int(end)

            except (ValueError, TypeError):
                self._end = None

        # Tracks total_size (used for posting when we have parts of files
        self._total_size = None
        if total_size is not None:
            try:
                self._total_size = int(total_size)

            except (ValueError, TypeError):
                raise AttributeError(
                    "Invalid total_size specified (%s)." %
                    str(total_size),
                )

        # Set blocksize as a variable for those who want to tweak it
        # later on.  This controls the maximum amount of content read
        # from a file in one chunk (thus how much memory will be occupied
        # when called).  Setting this too high will utilize a lot of
        # memory if concurrent calls are made but will be faster if your
        # system can handle it.
        self._block_size = BLOCK_SIZE

        # Reserved for split() function which populates any children
        # spawned from this object with a pointer back to this as
        # object as a reference.
        self._parent = None

        # TODO: all md5, crc32, len() calls etc should all cache their results
        # here and retrieve from here if present. If a write() or load() is
        # made, the cache should be destroyed. The cache is only populated on
        # demand.
        self._lazy_cache = {}

        # NNTPContent supports directory storing too. This is toggle in the
        # event we're dealing with a directory
        self._isdir = False

        if not filepath:
            # Will use load() or open() which causes temp file
            # to be created
            return

        elif isinstance(filepath, file):

            # store stream
            self.stream = filepath

            # Always detach streams
            self._detached = True

            if hasattr('name', self.stream):
                self.filepath = abspath(self.stream.name)
                self.filename = basename(filepath)

            if hasattr('mode', self.stream):
                # Store our mode
                self.filemode = self.stream.mode
        else:
            if self._unique is False and isfile(filepath):
                self.load(filepath, sort_no=sort_no)

            elif isdir(filepath):
                # Toggle Flag
                self._isdir = True
                # Directories are always detached
                self._detached = True
                # Store our dirname
                self.filename = basename(filepath)
                # Store our path
                self.filepath = abspath(expanduser(filepath))

            else:
                # Store our filename
                self.filename = basename(filepath)

    def getvalue(self):
        """
        This is mostly just used for unit testing, but it
        greatly makes life easier anyway.

        Effectively we put the pointer at the head of our
        file and read back the entire chunk into memory
        and return it.
        """

        if not self.open(mode=NNTPFileMode.BINARY_RO, eof=False):
            # Error
            return None

        # Head of data
        self.stream.seek(0L, SEEK_SET)

        return self.read()

    def can_post(self):
        """
        Similar to is_valid() except only returns true if the item is
        postable. The big difference is is_valid() is toggle after something
        has been downloaded, where as can_post() is a field checked prior
        to posting to an NNTP Server.

        Content is only postable in ascii form, so binaries and directories
        will always return a False here.
        """
        return False

    def is_valid(self):
        """
        A simple function that returns whether the article is valid or not

        The function returns True if it is valid, and False if it isn't
        and None if there isn't enough information to make a valid guess.

        The basic version (no overloading) just returns what the flag
        was set to.

        A directory can never be valid because it isn't content per say
        but a container to content.
        """
        return self._is_valid and not self._isdir

    def open(self, filepath=None, mode=None, eof=False):
        """
        Opens a filepath specified and re-attaches to it.
        You can also pass in an already open stream which
        causes it to operate in a detached state

        default open mode is BINARY_RW

        if eof is set to True, then after the file is opened, the
        pointer is placed at the end of the file (oppose to
        the head)
        """

        if not mode:
            # Read and write
            mode = NNTPFileMode.BINARY_RW

        if self.stream is not None:
            if self.filemode is not None and self.filemode == mode:
                # ensure we're at the head of the file
                if not eof:
                    self.stream.seek(0L, SEEK_SET)
                else:
                    self.stream.seek(0L, SEEK_END)

                return weakref.ref(self.stream)

        if not filepath and self.filepath:
            # Update filepath
            filepath = self.filepath

        elif not filepath:
            if not isdir(self.work_dir):
                # create directory
                mkdir(self.work_dir)

            # Create a Temporary File
            fileno, self.filepath = mkstemp(dir=self.work_dir)
            try:
                self.stream = fdopen(fileno, mode)
                if self._detached is None:
                    self._detached = False

                # save the last mode the file was opened as
                self.filemode = mode

                logger.debug(
                    'Opened %s (mode=%s)' %
                    (self.filepath, mode),
                )

            except (IOError, OSError) as e:
                logger.error(
                    'Could not open %s (mode=%s)' %
                    (self.filepath, mode),
                )
                logger.debug(
                    'fdopen({0}, {1}, wd={2}) exception ({3})'.format(
                        fileno, mode, self.work_dir, str(e)))
                return False

            return weakref.ref(self.stream)

        if isinstance(filepath, basestring):

            # expand our path to be absolute
            filepath = abspath(expanduser(filepath))

            # Create our stream
            try:
                self.stream = open(filepath, mode)

                self.filepath = filepath
                if self._detached is None:
                    self._detached = True

                # save the last mode the file was opened as
                self.filemode = mode

                logger.debug(
                    # D flag for Detached
                    'Opened %s (mode=%s) (flag=D)' %
                    (self.filepath, mode),
                )

            except (IOError, OSError) as e:
                logger.error(
                    'Could not open %s (mode=%s) (flag=D)' %
                    (self.filepath, mode),
                )
                logger.debug(
                    'open({0}, {1}, wd={2}) exception ({3})'.format(
                        filepath, mode, self.work_dir, str(e)))
                return False

        elif hasattr(filepath, 'seek'):
            # assume we're dealing with an already open stream and therefore
            # we work in a detached state
            self.stream = filepath
            self.filepath = filepath.get('name')
            self.filemode = filepath.get('mode')

            if self.filepath:
                self.filename = basename(self.filepath)
            else:
                self.filename = ''

            # You can never have an attached file without a filepath
            self._detached = False

            # Reset dirty flag
            self._dirty = False

        else:
            logger.error(
                'Could not open object %s' % (type(self.filepath))
            )
            return False

        if not eof:
            # Ensure we're at the head of the file
            self.stream.seek(0L, SEEK_SET)

        else:
            # Ensure we're at the end of the file
            self.stream.seek(0L, SEEK_END)

        return weakref.ref(self.stream)

    def encode(self, encoder):
        """
        A wrapper to the encoding of content. The function returns None if
        a problem occurs, otherwise the function returns an NNTPContent()
        object.

        The power of this function comes from the fact you can pass in
        multiple encoders to have them all fire after one another.
        """
        # Python does not allow recursive inclusion; since NNTPContent is
        # included via the codec paths we test if it's an encoder by just
        # looking for the encode() function
        if not isinstance(encoder, object):
            return None

        if not isinstance(encoder, (list, tuple, sortedset, list)):
            # work with a tuple for now
            encoder = (encoder, )

        # Content object we chain to
        content = self

        for _enc in encoder:
            # Support Type initializations
            if isinstance(_enc, type):
                enc = _enc()
            else:
                enc = _enc

            if hasattr(enc, 'encode') and \
               isinstance(enc.encode, MethodType):
                # We're dealing with a stream based encoder
                content = enc.encode(self)
                if content is None:
                    return None

            else:
                # We don't support this
                return None

        return content

    def load(self, filepath, sort_no=10000):
        """
        This causes the function to point to the file specified and acts in a
        detached manner to it.

        Loaded files are 'always' detached; if the file already existed in the
        filesystem it would be silly to tie it to the scope of this object.

        If the filepath identifie is an NNTPContent() object, then it is copied
        into an 'attached' NNTPContent() object.

        If the filepath identified is a set, sortedset or list of
        NNTPContent() objects, a new single 'attached' file will be generated
        based on the contains passed in.  NNTPContent() objects are
        automatically combined/merged based on their ordering by automating
        the use of the .append() function of this class for the caller.

        """

        if self.stream is not None:
            if self.filemode == NNTPFileMode.BINARY_WO_TRUNCATE:
                # Truncate remaining portions of the file
                self.truncate()

            # Close any existing open file
            self.close()

        if self._detached is False and self.filepath:
            # We're changing so it's better we unlink this (but only if we're
            # attached to it)
            rm(self.filepath)

        # Support directories but initialize field to false
        self._isdir = False

        # Set Detached since we don't want to obstruct our newly loaded
        # file in any way
        self._detached = True

        # Reset Valid Flag
        self._is_valid = False

        # Reset Unique Flag
        self._unique = False

        if isinstance(filepath, NNTPContent):
            # Support NNTPContent object copying; by simply storing
            # the object in a list, we are able to catch it in the
            # next check
            self.part = filepath.part
            filepath = [filepath]

        if isinstance(filepath, (tuple, set, sortedset, list)):
            # Perform merge if we detected a set of NNTPContent objects
            count = 0
            for content in filepath:
                if isinstance(content, NNTPContent):
                    self.append(content)
                    count += 1

            if count == 0 or len(filepath) != count:
                # Return True if we iterated over everything
                return False

            # update our filepath to be that of the file that was actually
            # created
            filepath = self.filepath

            # Our file is not detached in this state
            self._detached = False

        elif isdir(filepath):
            # Toggle our flag and fall through as we support directories
            self._isdir = True

        elif not isfile(filepath):
            # we can't load the file so reset some common variables
            self.filepath = None
            self.filename = ''

            return False

        # Assign new file
        self.filepath = filepath

        # Set Flag
        self._is_valid = True

        # Store our filename
        self.filename = basename(filepath)

        return True

    def copy(self):
        """
        copy is very close to save(); this is especially the case since
        the save() function has a copy parameter.

        the difference is copy actually duplicates/clones the content
        object as a completely new file that is not detached and therefore
        this copy (by default) is destroyed when the object goes out
        of scope.

        This is useful for handling downloads; one might want to create
        a copy of the original object and build onto it or alter it. With
        a copy to work with, you don't have to worry about obstructing the
        original file.

        copy() is just a clean way to simplify your code by wrapping
        the save() function with error handling.  Unlike save()
        which returns True if it was successful and False if it failed),
        copy() returns a new NNTPContent object.

        The function returns None if there was a failure

        """

        with pushd(self.work_dir, create_if_missing=True):
            # mkstemp used to genrate an unused temporary file
            _, filepath = mkstemp(dir=self.work_dir)
            try:
                # Remove the created file to silence any warnings
                # from the save() call coming next
                unlink(filepath)
            except:
                pass

        if not self.save(filepath, copy=True):
            return None

        # Initialize a new object
        obj = NNTPContent(
            filepath, part=self.part, total_parts=self.total_parts,
            begin=self._begin, end=self._end, total_size=self._total_size,
            work_dir=self.work_dir, sort_no=self.sort_no, unique=False,
        )

        # Save our official filename
        obj.filename = self.filename

        # Ensure our copy is attached
        obj.attach()

        return obj

    def save(self, filepath=None, copy=False):
        """
        This function writes the content to disk using the filename
        specified.

        If copy is False, then the content detaches itself from internal
        management and is moved to the new path specified by filepath.
        If copy is True, then content is written to the new location
        and remains in it's current detached state (whatever it was).

        If no filepath is specified, then the detected filename and
        work_dir specified during the objects initialization is used instead.

        The function returns True if it successfully saved the file and
        False otherwise. If you never passed in a filepath, then the path
        that was last loaded is saved to instead and the file is automatically
        detached from the Object.
        """
        if filepath:
            if not isfile(filepath):
                # If the file wasn't found relative to where we are, we'll try
                # again but relative to the work dir
                with pushd(self.work_dir, create_if_missing=True):
                    if isfile(filepath):
                        # Ensure we've expanded the file path
                        filepath = abspath(filepath)
                    else:
                        # Attempt to expand path
                        filepath = abspath(expanduser(filepath))
            else:
                # Ensure we've expanded the file path
                filepath = abspath(filepath)

        if filepath is None:
            if self.filename:
                filepath = join(self.work_dir, self.filename)
            else:
                filepath = join(self.work_dir, basename(self.filepath))

        elif isdir(filepath):
            if self.filename:
                filepath = join(filepath, basename(self.filename))
            else:
                filepath = join(self.work_dir, basename(self.filepath))

        if isfile(filepath):
            if self.path() != filepath:
                try:
                    unlink(filepath)
                    logger.warning('%s already existed (removed).' % (
                            filepath,
                        )
                    )
                except:
                    logger.error(
                        '%s already existed (and could not be removed).' % (
                            filepath,
                        )
                    )
                    return False

        # else: treat it as full path and filename included
        if not isdir(dirname(filepath)):
            # Attempt to pre-create save path
            if not mkdir(dirname(filepath)):
                return False

        if self.stream:
            # close the file if it's open
            self.close()

        # Function Wrapping
        if copy:
            action = _copy
            action_str = "copy"

        else:
            action = _move
            action_str = "move"

        if self.path() != filepath:
            try:
                action(self.filepath, filepath)

                logger.debug('%s(%s, %s)' % (
                    action_str, self.filepath, filepath,
                ))

            except ShutilError, e:
                logger.debug('%s(%s, %s) exception %s' % (
                    action_str, self.filepath, filepath, str(e),
                ))
                return False

        if not copy:
            # If we reach here, we want to treat moves() as an official
            # way of saving/writing the file to it's final destination
            # and therefore we can update our object

            # Detach File
            self._detached = True
            # Update filepath
            self.filepath = filepath
            # Update filename
            self.filename = basename(filepath)

        return True

    def path(self):
        """
        Always returns a filepath of the file, if one hasn't been created yet
        then one is automatically generated and returned.
        """
        if not self.filepath:
            # Create a Temporary File
            _, self.filepath = mkstemp(dir=self.work_dir)

        return self.filepath

    def split(self, size=81920, mem_buf=1048576):
        """Returns a set of NNTPContent() objects containing the split version
        of this object based on the criteria specified.

        Even if the object can't be split any further given the parameters, a
        set of at least 1 entry will always be returned.  None is returned if
        an error occurs.

        """
        # File Length
        file_size = len(self)
        if file_size == 0:
            # Object can not be split
            return None

        if not isinstance(size, int):
            # try to support other types
            size = strsize_to_bytes(size)

        if not size or size < 0:
            return None

        if not isinstance(mem_buf, int):
            # try to support other types
            mem_buf = strsize_to_bytes(mem_buf)

        if not mem_buf or mem_buf < 0:
            return None

        # Initialize Part #
        part = 0

        # Initialize Total Part #
        total_parts, partial = divmod(len(self), size)
        if partial:
            total_parts += 1

        # A lists of NNTPContent() objects to return
        objs = sortedset(key=lambda x: x.key())

        if not self.open(mode=NNTPFileMode.BINARY_RO):
            return None

        # Calculate the total length of our data
        total_size = len(self)

        # File length of our first object
        f_length = 0

        # Total Bytes Read
        total_bytes = 0

        # Initialize dummy value
        obj = None

        # Now read our chunks as per our memory restrictions
        while True:

            if total_bytes == 0:
                # Read memory chunk
                data = BytesIO(self.stream.read(mem_buf-total_bytes))

                # Retrieve length of our buffer
                total_bytes = data.seek(0L, SEEK_END)

                # Reset our pointer to the head of our data stream
                data.seek(0L, SEEK_SET)

                if total_bytes == 0:
                    if f_length > 0:
                        # Store our last object before we wrap up
                        obj.close()
                        objs.add(obj)
                    # Return our list of NNTPContent() objects
                    return objs

            while total_bytes > 0 and size-f_length > 0:
                # Store content up to our alotted amount
                block_size = size-f_length
                if total_bytes < block_size:
                    block_size = total_bytes

                if f_length == 0:

                    # Create a new object
                    obj = NNTPContent(
                        filepath=self.filename,
                        part=part+1,
                        total_parts=total_parts,
                        begin=(part*size),
                        end=((part*size)+size),
                        total_size=total_size,
                        work_dir=self.work_dir,
                        sort_no=self.sort_no,
                    )

                    # Increment our part
                    part += 1

                    # Create a pointer to the parent
                    obj._parent = weakref.proxy(self)

                    # Open the new file
                    obj.open(mode=NNTPFileMode.BINARY_WO_TRUNCATE)

                try:
                    obj.write(data.read(block_size))

                except IOError, e:
                    if e[0] is errno.ENOSPC:
                        # most probably a disk space issue
                        logger.error(
                            'Ran out of disk space while writing %s.' %
                            (obj.filepath),
                        )
                    else:
                        # most probably a disk space issue
                        logger.error(
                            'An I/O error '
                            '(%d) occured while writing %s to disk.' %
                            (e[0], obj.filepath),
                        )

                    # Tidy
                    self.close()

                    # Return None
                    return None

                f_length += block_size
                total_bytes -= block_size

            if f_length == size:
                # We're done
                obj.close()
                objs.add(obj)

                # File length reset
                f_length = 0

        # code will never reach here
        return None

    def write(self, data, eof=True):
        """
        Writes data to stream

        eof is only considered if the file wasn't open prior to the write()
        call. Otherwise the pointer remains where it last was. If set to True
        and the file wasn't previously open, the pointer is automatically
        placed at the end of the stream.

        """
        if self.stream is None:
            # open the file if it's not already open
            self.open(mode=NNTPFileMode.BINARY_RW, eof=eof)

        response = self.stream.write(data)

        if not self._dirty:
            # Set dirty flag
            self._dirty = True

            # We can't trust self._end anymore now because content was
            # written to the file.
            self._end = None

        return response

    def read(self, n=-1):
        """
        read up to n bytes from the stream
        """
        if self.stream is None:
            # open the file if it's not already open
            self.open(mode=NNTPFileMode.BINARY_RO, eof=False)

        return self.stream.read(n)

    def close(self):
        """
        Closes the file but retains any attachment to it.
        """
        if self.stream is not None:
            try:
                self.stream.close()
                if self.filepath:
                    logger.debug('Closed %s' % (self.filepath))
                else:
                    logger.debug('Closed stream.')
            except:
                pass

            self.stream = None
            self.filemode = None

            # A closed file can't be dirty as content is
            # flushed to disk at this point; therefore reset the flag
            # back to False
            self._dirty = False

        return

    def append(self, content):
        """
        This function takes a content object (or list of content objects) and
        appends them to `this` object.

        """
        if isinstance(content, NNTPContent):
            content = [content]

        if not self.open(mode=NNTPFileMode.BINARY_WO, eof=True):
            return False

        for entry in content:
            if isinstance(entry, NNTPContent):
                # Just append the current content
                if not entry.open(mode=NNTPFileMode.BINARY_RO, eof=False):
                    logger.debug('Error handling content: %s' % entry)
                    continue

                logger.debug('Appending content %s' % entry)

                while True:
                    buf = entry.stream.read(self._block_size)
                    if not buf:
                        # Set dirty flag
                        self._dirty = True
                        break
                    self.stream.write(buf)

                entry.close()

        return True

    def begin(self):
        """
        Returns the beginning ptr; this is nessisary when building encoded
        parts to be posted on an NNTPServer
        """
        if self._begin:
            return self._begin
        return 0

    def end(self):
        """
        Returns the end ptr; this is nessisary when building encoded
        parts to be posted on an NNTPServer
        """
        if self._end is None:
            self._end = self._begin + len(self)
        return self._end

    def total_size(self):
        """
        Returns the total size of the entire object (all parts included).
        This result is the same as len() if there is only 1 part to
        the entire object
        """
        if self.total_parts <= 1:
            return len(self)

        return self.end() - self.begin()

    def is_attached(self):
        """
        Simply returns whether or not the file is attached to the object or
        not.  Files that are attached are destroyed when the object goes
        out of scope.

        """
        return not self._detached

    def detach(self):
        """
        Detach the article stored on disk from being further managed by this
        class
        """
        self._detached = True
        return

    def attach(self):
        """
        Attach the file and it's data directly to this objects life expectancy
        """
        self._detached = False
        return

    def remove(self):
        """
        Gracefully remove the file (attached or not)
        """
        if self.stream is not None:
            self.close()

        if self.filepath:
            return rm(self.filepath)

        return False

    def key(self):
        """
        Returns a key that can be used for sorting with:
            lambda x : x.key()
        """
        if self.part is not None:
            result = '%.5d/%s/%.5d' % (self.sort_no, self.filename, self.part)
        else:
            result = '%.5d/%s//' % (self.sort_no, self.filename)

        if self._unique is not False:
            return result + self._unique

        return result

    def post_iter(self, block_size=BLOCK_SIZE):
        """
        Returns NNTP string as it would be required for posting to an
        NNTP Server
        """
        if not block_size:
            block_size = self._block_size

        if self.open(mode=NNTPFileMode.BINARY_RO):
            while 1:
                data = self.stream.read(block_size)
                if not data:
                    break
                yield data
            self.close()

    def crc32(self):
        """
        A little bit old-fashioned, but some encodings like yEnc require that
        a crc32 value be used.  This calculates it based on the file
        """
        # block size defined as 2**16
        block_size = 65536

        # The mask to apply to all CRC checking
        BIN_MASK = 0xffffffffL

        # Initialize
        _crc = 0

        if self.open(mode=NNTPFileMode.BINARY_RO):
            for chunk in iter(lambda: self.stream.read(block_size), b''):
                _crc = crc32(chunk, _crc)

            return format(_crc & BIN_MASK, '08x')

        return None

    def mime(self):
        """
        Returns the mime of the object
            Source: https://github.com/ahupp/python-magic
        """

        # Initialize our Mime object
        m = Mime()

        if self.open(mode=NNTPFileMode.BINARY_RO):
            mr = m.from_content(self.stream.read(128))
        else:
            mr = None

        if mr is None or mr.type() == DEFAULT_MIME_TYPE:
            # Try one more time by the filename
            mr = m.from_filename(
                self.filename if self.filename else self.filepath)

        # Return our type
        return mr

    def md5(self):
        """
        Simply return the md5 hash value associated with the content file.

        If the file can't be accessed, then None is returned.
        """
        md5 = hashlib.md5()
        if self.open(mode=NNTPFileMode.BINARY_RO):
            for chunk in \
                    iter(lambda: self.stream.read(128*md5.block_size), b''):
                md5.update(chunk)
            return md5.hexdigest()
        return None

    def sha1(self):
        """
        Simply return the sha1 hash value associated with the content file.

        If the file can't be accessed, then None is returned.
        """
        sha1 = hashlib.sha1()
        if self.open(mode=NNTPFileMode.BINARY_RO):
            for chunk in \
                    iter(lambda: self.stream.read(128*sha1.block_size), b''):
                sha1.update(chunk)
            return sha1.hexdigest()
        return None

    def sha256(self):
        """
        Simply return the sha256 hash value associated with the content file.

        If the file can't be accessed, then None is returned.
        """
        sha256 = hashlib.sha256()
        if self.open(mode=NNTPFileMode.BINARY_RO):
            for chunk in \
                    iter(lambda: self.stream.read(128*sha256.block_size), b''):
                sha256.update(chunk)
            return sha256.hexdigest()
        return None

    def tell(self):
        """
        Allows reference to our object from within a Codec()

        """
        if not self.filepath:
            # If there is no filepath, then we're probably dealing with a
            # stream in memory like a StringIO or BytesIO stream.
            if self.stream:
                # Advance to the end of the file
                return self.stream.tell()

        else:
            if self.stream and self._dirty is True:
                self.stream.flush()
                self._dirty = False

        if not self.stream:
            if not self.open(mode=NNTPFileMode.BINARY_RO):
                return None

        return self.stream.tell()

    def readline(self, *args, **kwargs):
        """
        Returns a single line from the stream
        """
        if not self.stream:
            return ''
        return self.stream.readline(*args, **kwargs)

    def next(self):
        """
        Python 2 support
        Support stream type functions and iterations
        """
        data = self.stream.read(self._block_size)
        if not data:
            self.close()
            raise StopIteration()

        return data

    def __next__(self):
        """
        Python 3 support
        Support stream type functions and iterations
        """
        data = self.stream.read(self._block_size)
        if not data:
            self.close()
            raise StopIteration()

        return data

    def __iter__(self):
        """
        Grants usage of the next()
        """

        # Ensure our stream is open with read
        self.open(mode=NNTPFileMode.BINARY_RO)
        return self

    def __len__(self):
        """
        Returns the length of the content
        """
        if not self.filepath:
            # If there is no filepath, then we're probably dealing with a
            # stream in memory like a StringIO or BytesIO stream.
            if self.stream:
                # Advance to the end of the file
                ptr = self.stream.tell()
                # Advance to the end of the file and get our length
                length = self.stream.seek(0L, SEEK_END)
                if length != ptr:
                    # Return our pointer
                    self.stream.seek(ptr, SEEK_SET)
            else:
                # No Stream or Filepath; nothing has been initialized
                # yet at all so just return 0
                length = 0
        else:
            if self.stream and self._dirty is True:
                self.stream.flush()
                self._dirty = False

            # Get the size
            length = getsize(self.filepath)

        return length

    def hexdump(self, max_bytes=128):
        """
        Returns a hex dump of characters up to the defined max_bytes
        If max_bytes is 0 then all content is dumped

        """

        if not self.open(mode=NNTPFileMode.BINARY_RO, eof=False):
            # Error
            return None

        # Head of data
        self.stream.seek(0L, SEEK_SET)

        if not max_bytes:
            return hexdump(self.read())
        return hexdump(self.read(max_bytes))

    def __del__(self):
        """
        Gracefully remove the file retrieved as it was removed
        from scope for a good reason. We can easily avoid
        having this step called by calling the detach() function
        """
        if self.stream is not None:
            self.close()

        if not self._detached and self.filepath:
            # We need to do some cleanup
            rm(self.filepath)

    def __lt__(self, other):
        """
        Support Less Than (<) operator for sorting
        """
        return self.key() < self.key()

    def __cmp__(self, content):
        """
        Support comparative checks
        """
        return cmp(self.key(), content.key())

    def __str__(self):
        """
        Return a printable version of the file being read
        """
        if self.part is not None:
            return '%s.%.5d' % (self.filename, self.part)

        return self.filename

    def __enter__(self):
        """
        supports use of the 'with' clause.  You can use the expression:

        with myobj as fp:
            # write and/or read content here

        """
        # Open our file and return a pointer to it
        if self.open():
            return self

        # Throw an exception
        raise IOError(errno.EIO, 'Could not open NNTPContent', self.path())

    def __exit__(self, type, value, traceback):
        """
        our exit function executed from the 'with' clause
        """
        # Close our file (if open)
        self.close()

    def __repr__(self):
        """
        Return a printable version of the file being read
        """
        if self.part is not None:
            return \
                '<NNTPContent sort=%d filename="%s" part=%d/%d len=%s />' % (
                    self.sort_no,
                    self.filename,
                    self.part,
                    self.total_parts,
                    bytes_to_strsize(len(self))
                )
        else:
            return '<NNTPContent sort=%d filename="%s" len=%s />' % (
                self.sort_no,
                self.filename,
                bytes_to_strsize(len(self)),
            )
