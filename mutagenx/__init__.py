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

import warnings
import collections.abc

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

class FileType(collections.abc.MutableMapping):
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

    def __iter__(self):
        if self.tags is None:
            return iter([])
        else:
            return iter(list(self.tags.keys()))

    def __len__(self):
        if self.tags is None:
            return 0
        else:
            return len(list(self.tags.keys()))

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

def File(filename, options=None, easy=False):
    """Guess the type of the file and try to open it.

    The file type is decided by several things, such as the first 128
    bytes (which usually contains a file type identifier), the
    filename extension, and the presence of existing tags.

    If no appropriate type could be found, None is returned.
    """

    if options is None:
        from mutagenx.asf import ASF
        from mutagenx.apev2 import APEv2File
        from mutagenx.flac import FLAC

        if easy:
            from mutagenx.easyid3 import EasyID3FileType as ID3FileType
        else:
            from mutagenx.id3 import ID3FileType

        if easy:
            from mutagenx.mp3 import EasyMP3 as MP3
        else:
            from mutagenx.mp3 import MP3

        from mutagenx.oggflac import OggFLAC
        from mutagenx.oggspeex import OggSpeex
        from mutagenx.oggtheora import OggTheora
        from mutagenx.oggvorbis import OggVorbis
        from mutagenx.oggopus import OggOpus

        if easy:
            from mutagenx.trueaudio import EasyTrueAudio as TrueAudio
        else:
            from mutagenx.trueaudio import TrueAudio

        from mutagenx.wavpack import WavPack
        if easy:
            from mutagenx.easymp4 import EasyMP4 as MP4
        else:
            from mutagenx.mp4 import MP4

        from mutagenx.musepack import Musepack
        from mutagenx.monkeysaudio import MonkeysAudio
        from mutagenx.optimfrog import OptimFROG

        options = [MP3, TrueAudio, OggTheora, OggSpeex, OggVorbis, OggFLAC,
                   FLAC, APEv2File, MP4, ID3FileType, WavPack, Musepack,
                   MonkeysAudio, OptimFROG, ASF, OggOpus]

    if not options:
        return None

    fileobj = open(filename, "rb")
    try:
        header = fileobj.read(128)
        # Sort by name after score. Otherwise import order affects
        # Kind sort order, which affects treatment of things with
        # equals scores.
        results = [(Kind.score(filename, fileobj, header), Kind.__name__)
                   for Kind in options]
    finally:
        fileobj.close()
    results = sorted(zip(results, options))
    (score, name), Kind = results[-1]
    if score > 0:
        return Kind(filename)
    else:
        return None
