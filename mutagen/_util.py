# -*- coding: utf-8 -*-

# Copyright 2006 Joe Wreschnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# $Id: _util.py 4218 2007-12-02 06:11:20Z piman $
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

"""Utility classes for Mutagen.

You should not rely on the interfaces here being stable. They are
intended for internal use in Mutagen only.
"""

from fnmatch import fnmatchcase

def dict_match(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        for pattern, value in d.iteritems():
            if fnmatchcase(key, pattern):
                return value
    return default
