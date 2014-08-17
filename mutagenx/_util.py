# -*- coding: utf-8 -*-

# Copyright 2006 Joe Wreschnig
#           2014 Ben Ockmore
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Utility classes for MutagenX.

You should not rely on the interfaces here being stable. They are
intended for internal use in MutagenX only.
"""

import struct
import codecs

from fnmatch import fnmatchcase

from ._compat import chr_, text_type, PY2, iteritems, iterbytes

from collections import OrderedDict, MutableMapping


def total_ordering(cls):
    assert hasattr(cls, "__eq__")
    assert hasattr(cls, "__lt__")

    cls.__le__ = lambda self, other: self == other or self < other
    cls.__gt__ = lambda self, other: not (self == other or self < other)
    cls.__ge__ = lambda self, other: not self < other
    cls.__ne__ = lambda self, other: not self.__eq__(other)

    return cls

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

    short_le = staticmethod(lambda data: struct.unpack('<h', data)[0])
    ushort_le = staticmethod(lambda data: struct.unpack('<H', data)[0])

    short_be = staticmethod(lambda data: struct.unpack('>h', data)[0])
    ushort_be = staticmethod(lambda data: struct.unpack('>H', data)[0])

    int_le = staticmethod(lambda data: struct.unpack('<i', data)[0])
    uint_le = staticmethod(lambda data: struct.unpack('<I', data)[0])

    int_be = staticmethod(lambda data: struct.unpack('>i', data)[0])
    uint_be = staticmethod(lambda data: struct.unpack('>I', data)[0])

    longlong_le = staticmethod(lambda data: struct.unpack('<q', data)[0])
    ulonglong_le = staticmethod(lambda data: struct.unpack('<Q', data)[0])

    longlong_be = staticmethod(lambda data: struct.unpack('>q', data)[0])
    ulonglong_be = staticmethod(lambda data: struct.unpack('>Q', data)[0])

    to_short_le = staticmethod(lambda data: struct.pack('<h', data))
    to_ushort_le = staticmethod(lambda data: struct.pack('<H', data))

    to_short_be = staticmethod(lambda data: struct.pack('>h', data))
    to_ushort_be = staticmethod(lambda data: struct.pack('>H', data))

    to_int_le = staticmethod(lambda data: struct.pack('<i', data))
    to_uint_le = staticmethod(lambda data: struct.pack('<I', data))

    to_int_be = staticmethod(lambda data: struct.pack('>i', data))
    to_uint_be = staticmethod(lambda data: struct.pack('>I', data))

    to_longlong_le = staticmethod(lambda data: struct.pack('<q', data))
    to_ulonglong_le = staticmethod(lambda data: struct.pack('<Q', data))

    to_longlong_be = staticmethod(lambda data: struct.pack('>q', data))
    to_ulonglong_be = staticmethod(lambda data: struct.pack('>Q', data))

    bitswap = b''.join(chr_(sum(((val >> i) & 1) << (7-i) for i in range(8)))
                       for val in range(256))

    test_bit = staticmethod(lambda value, n: bool((value >> n) & 1))


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
    equivalent. MutagenX tries to use mmap to resize the file, but
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
    equivalent. MutagenX tries to use mmap to resize the file, but
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
    """Convert a basestring to a valid UTF-8 str."""

    if isinstance(data, bytes):
        return data.decode("utf-8", "replace").encode("utf-8")
    elif isinstance(data, text_type):
        return data.encode("utf-8")
    else:
        raise TypeError("only unicode/bytes types can be converted to UTF-8")


def dict_match(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        for pattern, value in iteritems(d):
            if fnmatchcase(key, pattern):
                return value
    return default


def decode_terminated(data, encoding, strict=True):
    """Returns the decoded data until the first NULL terminator
    and all data after it.

    In case the data can't be decoded raises UnicodeError.
    In case the encoding is not found raises LookupError.
    In case the data isn't null terminated (even if it is encoded correctly)
    raises ValueError except if strict is False, then the decoded string
    will be returned anyway.
    """

    codec_info = codecs.lookup(encoding)

    # normalize encoding name so we can compare by name
    encoding = codec_info.name

    # fast path
    if encoding in ("utf-8", "iso8859-1"):
        index = data.find(b"\x00")
        if index == -1:
            # make sure we raise UnicodeError first, like in the slow path
            res = data.decode(encoding), b""
            if strict:
                raise ValueError("not null terminated")
            else:
                return res
        return data[:index].decode(encoding), data[index + 1:]

    # slow path
    decoder = codec_info.incrementaldecoder()
    r = []
    for i, b in enumerate(iterbytes(data)):
        c = decoder.decode(b)
        if c == u"\x00":
            return u"".join(r), data[i + 1:]
        r.append(c)
    else:
        # make sure the decoder is finished
        r.append(decoder.decode(b"", True))
        if strict:
            raise ValueError("not null terminated")
        return u"".join(r), b""
