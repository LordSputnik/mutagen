# -*- coding: utf-8 -*-

# Copyright (C) 2005  Michael Urman
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# $Id: __init__.py 4348 2008-12-02 02:41:15Z piman $
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

version = (1, 21)
version_string = ".".join(str(v) for v in version)

class Metadata(object):
    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.load(*args, **kwargs)

    def load(self, *args, **kwargs):
        raise NotImplementedError

    def save(self, filename=None):
        raise NotImplementedError

    def delete(self, filename=None):
        raise NotImplementedError

class FileType(dict):
    """An abstract object wrapping tags and audio stream information.

    Attributes:
    info -- stream information (length, bitrate, sample rate)
    tags -- metadata tags, if any

    Each file format has different potential tags and stream
    information.

    FileTypes implement an interface very similar to Metadata; the
    dict interface, save, load, and delete calls on a FileType call
    the appropriate methods on its tag data.
    """

    info = None
    tags = None
    filename = None
    _mimes = ["application/octet-stream"]

    def __init__(self, filename=None, *args, **kwargs):
        if filename is None:
            warnings.warn("FileType constructor requires a filename",
                          DeprecationWarning)
        else:
            self.load(filename, *args, **kwargs)

    def load(self, filename, *args, **kwargs):
        raise NotImplementedError

    def __getitem__(self, key):
        """Look up a metadata tag key.

        If the file has no tags at all, a KeyError is raised.
        """
        if self.tags is None:
            raise KeyError(key)
        else:
            return self.tags[key]

    def __setitem__(self, key, value):
        """Set a metadata tag.

        If the file has no tags, an appropriate format is added (but
        not written until save is called).
        """
        if self.tags is None:
            self.add_tags()

        self.tags[key] = value

    def __delitem__(self, key):
        """Delete a metadata tag key.

        If the file has no tags at all, a KeyError is raised.
        """
        if self.tags is None:
            raise KeyError(key)
        else:
            del(self.tags[key])

    def keys(self):
        """Return a list of keys in the metadata tag.

        If the file has no tags at all, an empty list is returned.
        """
        if self.tags is None:
            return []
        else:
            return self.tags.keys()

    def values(self):
        """Return a list of keys in the metadata tag.

        If the file has no tags at all, an empty list is returned.
        """
        if self.tags is None:
            return []
        else:
            return self.tags.values()

    def items(self):
        """Return a list of keys in the metadata tag.

        If the file has no tags at all, an empty list is returned.
        """
        if self.tags is None:
            return []
        else:
            return self.tags.items()

    def delete(self, filename=None):
        """Remove tags from a file."""
        if self.tags is not None:
            if filename is None:
                filename = self.filename
            else:
                warnings.warn(
                    "delete(filename=...) is deprecated, reload the file",
                    DeprecationWarning)
            return self.tags.delete(filename)

    def save(self, filename=None, **kwargs):
        """Save metadata tags."""
        if filename is None:
            filename = self.filename
        else:
            warnings.warn(
                "save(filename=...) is deprecated, reload the file",
                DeprecationWarning)
        if self.tags is not None:
            return self.tags.save(filename, **kwargs)
        else: raise ValueError("no tags in file")

    def pprint(self):
        """Print stream information and comment key=value pairs."""
        stream = "{} ({})".format(self.info.pprint(), self.mime[0])
        try:
            tags = self.tags.pprint()
        except AttributeError:
            return stream
        else:
            return stream + ((tags and "\n" + tags) or "")

    def add_tags(self):
        raise NotImplementedError

    def __get_mime(self):
        mimes = []
        for Kind in type(self).__mro__:
            for mime in getattr(Kind, '_mimes', []):
                if mime not in mimes:
                    mimes.append(mime)
        return mimes

    mime = property(__get_mime)
