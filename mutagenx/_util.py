# -*- coding: utf-8 -*-

# Copyright 2006 Joe Wreschnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

"""Utility classes for Mutagen.

You should not rely on the interfaces here being stable. They are
intended for internal use in Mutagen only.
"""

import struct

from fnmatch import fnmatchcase

from collections import OrderedDict
from collections.abc import MutableMapping



class DictProxy(MutableMapping):
    def __init__(self, *args, **kwargs):
        #Needs to be an ordered dict to get around a testing issue in EasyID3
        self.__dict = OrderedDict()
        super(DictProxy, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        return self.__dict[key]

    def __setitem__(self, key, value):
        self.__dict[key] = value

    def __delitem__(self, key):
        del(self.__dict[key])

    def __iter__(self):
        return iter(self.__dict)

    def __len__(self):
        return len(self.__dict)


class cdata(object):
    """C character buffer to Python numeric type conversions."""

    from struct import error
    error = error

    @staticmethod
    def short_le(data): return struct.unpack('<h', data)[0]
    @staticmethod
    def ushort_le(data): return struct.unpack('<H', data)[0]

    @staticmethod
    def short_be(data): return struct.unpack('>h', data)[0]
    @staticmethod
    def ushort_be(data): return struct.unpack('>H', data)[0]

    @staticmethod
    def int_le(data): return struct.unpack('<i', data)[0]
    @staticmethod
    def uint_le(data): return struct.unpack('<I', data)[0]

    @staticmethod
    def int_be(data): return struct.unpack('>i', data)[0]
    @staticmethod
    def uint_be(data): return struct.unpack('>I', data)[0]

    @staticmethod
    def longlong_le(data): return struct.unpack('<q', data)[0]
    @staticmethod
    def ulonglong_le(data): return struct.unpack('<Q', data)[0]

    @staticmethod
    def longlong_be(data): return struct.unpack('>q', data)[0]
    @staticmethod
    def ulonglong_be(data): return struct.unpack('>Q', data)[0]

    @staticmethod
    def to_short_le(data): return struct.pack('<h', data)
    @staticmethod
    def to_ushort_le(data): return struct.pack('<H', data)

    @staticmethod
    def to_short_be(data): return struct.pack('>h', data)
    @staticmethod
    def to_ushort_be(data): return struct.pack('>H', data)

    @staticmethod
    def to_int_le(data): return struct.pack('<i', data)
    @staticmethod
    def to_uint_le(data): return struct.pack('<I', data)

    @staticmethod
    def to_int_be(data): return struct.pack('>i', data)
    @staticmethod
    def to_uint_be(data): return struct.pack('>I', data)

    @staticmethod
    def to_longlong_le(data): return struct.pack('<q', data)
    @staticmethod
    def to_ulonglong_le(data): return struct.pack('<Q', data)

    @staticmethod
    def to_longlong_be(data): return struct.pack('>q', data)
    @staticmethod
    def to_ulonglong_be(data): return struct.pack('>Q', data)

    bitswap = bytes(sum(((val >> i) & 1) << (7-i) for i in range(8))
                       for val in range(256))

    @staticmethod
    def test_bit(value, n): return bool((value >> n) & 1)


def lock(fileobj):
    """Lock a file object 'safely'.

    That means a failure to lock because the platform doesn't
    support fcntl or filesystem locks is not considered a
    failure. This call does block.

    Returns whether or not the lock was successful, or
    raises an exception in more extreme circumstances (full
    lock table, invalid file).
    """

    try:
        import fcntl
    except ImportError:
        return False
    else:
        try:
            fcntl.lockf(fileobj, fcntl.LOCK_EX)
        except IOError:
            # FIXME: There's possibly a lot of complicated
            # logic that needs to go here in case the IOError
            # is EACCES or EAGAIN.
            return False
        else:
            return True


def unlock(fileobj):
    """Unlock a file object.

    Don't call this on a file object unless a call to lock()
    returned true.
    """

    # If this fails there's a mismatched lock/unlock pair,
    # so we definitely don't want to ignore errors.
    import fcntl
    fcntl.lockf(fileobj, fcntl.LOCK_UN)


def insert_bytes(fobj, size, offset, BUFFER_SIZE=2**16):
    """Insert size bytes of empty space starting at offset.

    fobj must be an open file object, open rb+ or
    equivalent. Mutagen tries to use mmap to resize the file, but
    falls back to a significantly slower method if mmap fails.
    """

    assert 0 < size
    assert 0 <= offset
    locked = False
    fobj.seek(0, 2)
    filesize = fobj.tell()
    movesize = filesize - offset
    fobj.write(b'\x00' * size)
    fobj.flush()
    try:
        try:
            import mmap
            file_map = mmap.mmap(fobj.fileno(), filesize + size)
            try:
                file_map.move(offset + size, offset, movesize)
            finally:
                file_map.close()
        except (ValueError, EnvironmentError, ImportError):
            # handle broken mmap scenarios
            locked = lock(fobj)
            fobj.truncate(filesize)

            fobj.seek(0, 2)
            padsize = size
            # Don't generate an enormous string if we need to pad
            # the file out several megs.
            while padsize:
                addsize = min(BUFFER_SIZE, padsize)
                fobj.write(b"\x00" * addsize)
                padsize -= addsize

            fobj.seek(filesize, 0)
            while movesize:
                # At the start of this loop, fobj is pointing at the end
                # of the data we need to move, which is of movesize length.
                thismove = min(BUFFER_SIZE, movesize)
                # Seek back however much we're going to read this frame.
                fobj.seek(-thismove, 1)
                nextpos = fobj.tell()
                # Read it, so we're back at the end.
                data = fobj.read(thismove)
                # Seek back to where we need to write it.
                fobj.seek(-thismove + size, 1)
                # Write it.
                fobj.write(data)
                # And seek back to the end of the unmoved data.
                fobj.seek(nextpos)
                movesize -= thismove

            fobj.flush()
    finally:
        if locked:
            unlock(fobj)


def delete_bytes(fobj, size, offset, BUFFER_SIZE=2**16):
    """Delete size bytes of empty space starting at offset.

    fobj must be an open file object, open rb+ or
    equivalent. Mutagen tries to use mmap to resize the file, but
    falls back to a significantly slower method if mmap fails.
    """

    locked = False
    assert 0 < size
    assert 0 <= offset
    fobj.seek(0, 2)
    filesize = fobj.tell()
    movesize = filesize - offset - size
    assert 0 <= movesize
    try:
        if movesize > 0:
            fobj.flush()
            try:
                import mmap
                file_map = mmap.mmap(fobj.fileno(), filesize)
                try:
                    file_map.move(offset, offset + size, movesize)
                finally:
                    file_map.close()
            except (ValueError, EnvironmentError, ImportError):
                # handle broken mmap scenarios
                locked = lock(fobj)
                fobj.seek(offset + size)
                buf = fobj.read(BUFFER_SIZE)
                while buf:
                    fobj.seek(offset)
                    fobj.write(buf)
                    offset += len(buf)
                    fobj.seek(offset + size)
                    buf = fobj.read(BUFFER_SIZE)
        fobj.truncate(filesize - size)
        fobj.flush()
    finally:
        if locked:
            unlock(fobj)


def utf8(data):
    """Converts anything resembling a string to UTF8-encoded bytes."""

    if isinstance(data, bytes):
        return data.decode("utf-8", "replace").encode("utf-8")
    elif isinstance(data, str):
        return data.encode("utf-8")
    else:
        raise TypeError("only str/bytes types can be converted to UTF-8")

def dict_match(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        for pattern, value in d.items():
            if fnmatchcase(key, pattern):
                return value
    return default
