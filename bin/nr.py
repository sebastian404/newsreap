#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# NewsReap Command Line Interface (CLI)
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE

# This is the easiest way to interact with NewsReap from the command line
# It handles most basic functionality and offers users the ability to
# create their own plugins to enhance it's functionality further.
#
# Type nr.py --help for command help.
#
# Successfully executed commands always return a zero (0) to the command
# line, otherwise a non-zero value is returned which may or may not
# identify details on the problem that occurred.
#
# Drop a configuration file in your home directory:
#    mkdir -p ~/.config/newsreap
#    cp config.yaml ~/.config/newsreap
#
# Now update the configuration to reflect your NNTP Setup
#

# To initialize your workable database safely you might do the following:
#
#   # Initialize our database (only needs to be ran the first time)
#   nr.py db init
#
#   # Poll the configured NNTP Servers in your config.yaml file for
#   # all of the usenet groups supported.
#   nr.py update groups
#
#   # You can list them all now by typing:
#   nr.py group list --all
#
#   # Aliases allow you to simplify group reference so you don't have to type
#   # the whole name out each time. The below creates an alias called
#   # 'a.b.test' and assciates it with the group alt.binaries.test.
#   nr.py alias add test alt.binaries.test
#
#   # You can list the aliases and what they're associated with by typing
#   nr.py alias list
#
#   # You can also associate more then one group with the same alias
#   nr.py alias add test alt.binaries.testing alt.binaries.test.files
#
#   # Index all the groups defined by our alias.
#   # the below only looks back untl Jan 1st, 2014
#   # Depending on how many articles are in the group, this can take a very
#   # long time. The -vv at least lets you know something is going on.
#
#   # consider setting a database like PostgreSQL or MySQL for speed
#   # alternatively, if you insist on using the default SQLite database, then
#   # consider setting up a RAM drive for faster processing of the table
#   # writes.
#   nr.py -vvv update search --date-from=2014 test
#
#   # Index a from/to range if you want.
#   nr.py -vvv update search --date-from=2013 --date-to=2014.02 test
#
#   # Newsreap also maintains a watch list which is groups you just always
#   # intend to index. It can be a conbination of aliases you set up, or
#   # just a few individual groups. The below adds our 'test' group to
#   # a watch list.
#   nr.py group watch test
#
#   # We can now update our search by typing this following:
#   nr.py -vvv update search --watched

#   # Index the entire group (the whole retention period you have to work with)
#   nr.py group index test
#
#   # Now that you've got content indexed, you can browse for things
#   # You must specify an alias/group as your first argument
#   # From there, you can specify your search arguments
#   nr.py search test "keyword or string 1" "keyword or string 2" "etc..."
#
#   # Getting to many hits?  Filter them; the below only shows entries
#   # that scored higher then 30
#   nr.py search test --score=30 "keyword or string 1" \
#                                   "keyword or string 2" "etc..."
#
#   # You can do ranges too
#   # The below only shows entries that have scored between -90 and 30
#   nr.py search test --score=-90-30 "keyword or string 1" \
#                                       "keyword or string 2" "etc..."
#
#   # Want to elminate crap from your database that you know is just
#   # taking up useless junk (and space, and thus speed because it's indexed):
#   # use the delete option; it takes all the same parameters and options the
#   # search function does (--score, etc).
#   nr.py delete "keyword or string 1" "etc"
#
#  If you setup you filters right, you can download content by group or
#  single files.  Just pay attention to the id on the left (in your search)

# This monkey patching must be done before anything else to prevent
# Warnings like this on exit:
# Exception KeyError: KeyError(139667991911952,) in \
#       <module 'threading' from '/usr/lib64/python2.6/threading.pyc'> ignored
import gevent.monkey
gevent.monkey.patch_all()

import click
import sys
from os.path import abspath
from os.path import dirname
from os.path import basename
from os.path import isdir
from os.path import isfile

# Path
try:
    from newsreap.NNTPSettings import CLI_PLUGINS_MAPPING

except ImportError:
    sys.path.insert(0, dirname(dirname(abspath(__file__))))
    from newsreap.NNTPSettings import CLI_PLUGINS_MAPPING

# Import our file based paths
from newsreap.NNTPSettings import DEFAULT_CLI_PLUGIN_DIRECTORIES
from newsreap.NNTPSettings import NNTPSettings
from newsreap.NNTPManager import NNTPManager
from newsreap.Utils import scan_pylib
from newsreap.Utils import load_pylib

# Logging
from newsreap.Logger import *
import logging
logger = logging.getLogger(NEWSREAP_CLI)


# General Options
@click.group()
@click.option('--config', '-c',
              help='Specify configuration file.')
@click.option('--verbose', '-v', count=True,
              help='Verbose mode.')
@click.option('--noprompt', '-y', is_flag=True,
              help='Assume `yes` to all prompts.')
@click.pass_context
def cli(ctx, config, verbose, noprompt):
    ctx.obj['verbose'] = verbose

    # Add our handlers at the parent level
    add_handler(logging.getLogger(SQLALCHEMY_LOGGER))
    add_handler(logging.getLogger(NEWSREAP_LOGGER))

    # Handle Verbosity
    set_verbosity(verbose)

    ctx.obj['noprompt'] = noprompt

    if config is not None and not isfile(config):
        logger.error(
            "The YAML config file '%s' was not found." % config,
        )
        exit(1)

    # NNTPSettings() for storing and retrieving settings
    ctx.obj['NNTPSettings'] = NNTPSettings(cfg_file=config)

    if not ctx.obj['NNTPSettings'].is_valid():
        # our configuration was invalid
        logger.error("No valid config.yaml file was found.")
        exit(1)

    # NNTPManager() for interacting with all configured NNTP Servers
    ctx.obj['NNTPManager'] = NNTPManager(
        settings=ctx.obj['NNTPSettings'],
    )

# Dynamically Build CLI List; This is done by iterating through
# plugin directories and looking for CLI_PLUGINS_MAPPING
# which is expected to be a dictionary containing the mapping of
# the cli group (the key) to the function prefixes defined.
#
# If we can load it we'll save it here
plugins = scan_pylib(paths=[d for d in DEFAULT_CLI_PLUGIN_DIRECTORIES \
                    if isdir(d) is True])

# Now we iterate over the keys
for k, v in plugins.iteritems():
    for _pyfile in v:
        # Apply entry
        obj = load_pylib('_nrcli_%s' % k, _pyfile)
        if not hasattr(obj, CLI_PLUGINS_MAPPING):
            continue

        if isinstance(obj.NEWSREAP_CLI_PLUGINS, basestring):
            # 1-1 mapping of a function
            _click_func = getattr(obj, obj.NEWSREAP_CLI_PLUGINS, None)
            if callable(_click_func):
                cli.add_command(_click_func)
                break

        elif isinstance(obj.NEWSREAP_CLI_PLUGINS, dict):
            # parse format:
            # shorthand:function
            for sf, _meta in obj.NEWSREAP_CLI_PLUGINS.iteritems():
                # A flag used to track whether at least one command was added
                # otherwise why bother store the entry.
                store = False

                # Default Action Description
                group_desc = None

                if isinstance(_meta, basestring):
                    fn_prefix = _meta

                elif isinstance(_meta, dict):
                    # Support Dictionaries; but a prefix 'MUST'
                    # be specified or we move on
                    # {
                    #    'prefix': 'function_prefix',
                    #    'desc': 'action description',
                    # }
                    fn_prefix = _meta.get('prefix', None)

                    # Get Description (if present)
                    group_desc = _meta.get('desc', None)

                if not fn_prefix:
                    # Ignore entry
                    logger.warning('Ignoring bad plugin %s' % (
                        basename(_pyfile),
                    ))
                    continue

                # If we find a function identical to the module
                # we are accessing; then we are no longer dealing with
                # a group; instead we're dealing with a command
                command = None
                for fn in dir(obj):
                    if command is None and fn == fn_prefix:
                        # No group; this is a command; save it in our
                        # group_func arg so it gets added using the logic
                        # below
                        _click_group_func = getattr(obj, fn)
                        # Toggle flag allowing it to be added
                        store = True
                        break

                    elif not fn.startswith('%s_' % fn_prefix):
                        continue

                    # Anything below here and we're dealing with a fn_prefix
                    # entry
                    elif command is None:
                        # we're dealing with a group
                        def _click_group_func(ctx):
                            pass

                        if group_desc is None:
                            # Save our group description to this group
                            group_desc = ""

                        # Store our doc string
                        _click_group_func.__doc__ = group_desc

                        # Apply our Decorators; the below is equivalent to
                        #       @cli.group(name=sf)
                        #       @click.pass_context
                        #       def _click_group_func(ctx):
                        #           pass
                        #
                        # We intententionally use the decorators this way so
                        # that we an apply our group_desc (if specified) from
                        # the plugin modules we detect and load.
                        _click_group_func = \
                                click.pass_context(_click_group_func)
                        _click_group_func = \
                                cli.group(name=sf)(_click_group_func)

                        # Set the flag and fall through
                        command = False

                    if fn_prefix:
                        # Get our fn_suffix
                        fn_suffix = fn[len(fn_prefix)+1:]

                    # Store our function
                    _click_func = getattr(obj, fn)
                    _click_group_func.add_command(_click_func)

                    # Flip the store flag
                    store = True

            if store:
                cli.add_command(_click_group_func)


if __name__ == '__main__':

    cli(obj={})
