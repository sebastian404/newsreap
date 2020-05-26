# -*- coding: utf-8 -*-
#
# Hook is an object to simplify the handling of hook calls
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

from blist import sortedset

# Logging
import logging
from newsreap.Logger import NEWSREAP_HOOKS
logger = logging.getLogger(NEWSREAP_HOOKS)


class Hook(object):
    """
    Hooks allow us to define external functions and execute them at key times.

    Hooks allow external users to define their own logic that they'd like to
    occur at certain times events occur.  It allows you to effectivly define
    a callback.

    """

    # The default priority
    priority = 1000

    # The hook_id must be marked against all functions that are desired to
    # act as a hook.  Use the newsreap.decorator.hook decorator to acomplish
    # this task
    hook_id = 'newsreap_hook'
    module_id = 'newsreap_hook_module_name'

    def __init__(self, name, module=None, priority=1000):
        """
        Initialize our object which has a global priority defined

        """
        # The name of the module
        self.name = name

        # The pointer to actual dynamic module loaded
        self.module = module

        # Defines the defined functions that can be found inside this hook
        self.functions = {}

        # Defines our priory; the lower, the more likely it will be called
        try:
            self.priority = int(priority)

        except (TypeError, ValueError):
            self.priority = Hook.priority

        if self.module is not None:
            # Build our function map
            for element in dir(self.module):
                func = getattr(self.module, element, None)
                if callable(func) and hasattr(func, self.hook_id):
                    # Acquire all of our entries associated with our hook
                    entries = getattr(func, self.hook_id, element)

                    if isinstance(entries, dict):
                        # we're dealing with a function generated by our
                        # @hook decorator. So we store all instances of our
                        # name
                        for hookname, meta in entries.items():
                            self.add(
                                func,
                                name=hookname,
                                priority=meta['priority'],
                            )

                    elif isinstance(entries, basestring):
                        # Save our element
                        self[entries] = func
                        self.add(func, name=entries, priority=priority)

    def call(self, function_name, **kwargs):
        """
        Executes the specified function while passing in the same parameters
        you feed it here.

        This function returns the called functions respose as it's own return.

        """

        # Our response
        # We sort on index zero (0) which will be our priority
        responses = sortedset(key=lambda x: x['key'])

        # Acquire our object
        funcs = self.functions.get(function_name)

        if funcs is not None:
            for _func in funcs:
                # Acquire our information from our dictionary set
                func = _func['function']
                priority = _func['priority']

                # Acquire our entries
                module = getattr(
                    func,
                    self.module_id,
                    '{module}.{function}'.format(
                        module=self.name,
                        function=func.__name__,
                    ),
                )

                try:
                    # Execute our function and return it into our
                    # tuple which provides us the priority (used to sort
                    # our response), our function name (which may or may
                    # not be the same as the function call type) and
                    # our result
                    responses.add({
                        # Store our priority and module path for unambiguity
                        # This becomes our key
                        'key': '%.6d/%s' % (priority, module),

                        # Store our priority
                        'priority': priority,

                        # Store our module path:
                        'module': module,

                        # Store our result
                        'result': func(**kwargs),
                    })

                except Exception as e:
                    logger.warning(
                        "Hook Exception {0} calling {1}."
                        .format(str(e), module))

        return responses

    def add(self, function, name=None, priority=None):
        """
        Add's as a function to the specified hook

        """
        if not callable(function):
            return False

        if not name:
            # Default our group name to be the same name as the function
            name = function.__name__

        # Acquire our entries (if any)
        entries = getattr(function, Hook.hook_id, dict())

        # Determine our priority
        if not isinstance(priority, int):
            priority = self.priority

        if name not in entries:
            # @hook was never applied

            # Store our new entry contents using what we do know
            entries[name] = {
                'priority': priority,
            }

            try:
                # Save our entries back to the function
                setattr(function, Hook.hook_id, entries)

                # Storing meta information into our object allows us to reference
                # it later on by external wrappers such as the HookManager
                setattr(function, self.module_id, '%s.%s' % (
                    self.name, function.__name__))

            except AttributeError:
                # You can't assign entries to instancemethod objects (which
                # are functions embedded in classes.  In these cases this
                # exception is thrown, but it's no big deal since our primary
                # goal is to add this function to our function list which
                # occurs below
                pass

        added_count = 0
        # Now iterate over our entries and set them up
        for hookname, meta in entries.iteritems():
            # Now set our entries
            if hookname not in self.functions:
                self.functions[hookname] = sortedset(key=lambda x: x['key'])

            try:
                _priority = int(meta.get('priority', priority))

            except (TypeError, ValueError):
                # Default
                _priority = priority

            # store our function:
            bcnt = len(self.functions[hookname])
            self.functions[hookname].add({
                'key': '%.6d/%s' % (priority, function.__name__),
                'priority': _priority,
                'function': function,
            })

            if len(self.functions[hookname]) > bcnt:
                added_count += 1

        # Return if we were successful or not
        return added_count > 0

    def key(self):
        """
        Returns a key that can be used for sorting with:
            lambda x : x.key()

        """
        return '%.6d%s' % (self.priority, self.name)

    def __iter__(self):
        """
        Grants usage of the next()
        """
        for fset in self.functions.iterkeys():
            for func in self.functions[fset]:
                yield func['function']

    def __len__(self):
        """
        Returns the number of functions defined in the current module
        """
        return sum([len(x) for _, x in self.functions.iteritems()])

    def __lt__(self, other):
        """
        Handles less than for storing in btrees

        """
        return self.key() < other.key()

    def __eq__(self, other):
        """
        Handles equality

        """
        if isinstance(other, basestring):
            return self.name == other

        # otherwise assume we're dealing with another hook object
        return self.key() == other.key()

    def __getitem__(self, name):
        """
        Support accessing the functions if they exist

        """
        if name in self.functions:
            return self.functions[name]

        return None

    def __setitem__(self, name, func):
        """
        Sets an item through it's indexed value

        """
        if not callable(func):
            raise ValueError('Value must be callable!')

        if name in self.functions:
            # Reset our object
            self.functions[name].clear()

        # Add our function
        self.add(func, name=name, priority=self.priority)

    def __delitem__(self, name):
        """
        Allows the removal of an item

        """
        # removes the element from our list
        del self.functions[name]

    def __contains__(self, function_name):
        """
        Support 'in' keyword

        """
        return function_name in self.functions

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

    def __hash__(self):
        """
        Returns our hash
        """
        return hash(self.name)

    def __repr__(self):
        """
        Return an unambigious version of the object
        """

        return '<Hook name="%s" priority="%d" />' % (
            self.name,
            self.priority,
        )
