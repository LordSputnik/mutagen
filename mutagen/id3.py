import os.path
import struct
import sys


class error(Exception): pass
class ID3NoHeaderError(error, ValueError): pass
class ID3BadUnsynchData(error, ValueError): pass
class ID3BadCompressedData(error, ValueError): pass
class ID3TagError(error, ValueError): pass
class ID3UnsupportedVersionError(error, NotImplementedError): pass
class ID3EncryptionUnsupportedError(error, NotImplementedError): pass
class ID3JunkFrameError(error, ValueError): pass

class ID3Warning(error, UserWarning): pass

import mutagen
from mutagen._util import DictProxy

class ID3(DictProxy, mutagen.Metadata):
    """A file with an ID3v2 tag.

    Attributes:
    version -- ID3 tag version as a tuple
    unknown_frames -- raw frame data of any unknown frames found
    size -- the total size of the ID3 tag, including the header
    """

    PEDANTIC = True
    version = (2, 4, 0)

    filename = None
    size = 0
    __flags = 0
    __readbytes = 0
    __crc = None
    __unknown_updated = False

    def __init__(self, *args, **kwargs):
        self.unknown_frames = list()
        super(ID3, self).__init__(*args, **kwargs)

    def __fullread(self, size):
        try:
            if size < 0:
                raise ValueError(u'Requested bytes ({}) less than zero'.format(size))
            if size > self.__filesize:
                raise EOFError(u'Requested {:#x} of {:#x} {}'.format(
                        long(size), long(self.__filesize), self.filename))
        except AttributeError:
            pass

        data = self.__fileobj.read(size)
        if len(data) != size:
            raise EOFError

        self.__readbytes += size
        return data

    def load(self, filename, known_frames = None, translate = True):
        self.filename = filename
        self.__known_frames = known_frames
        self.__fileobj = open(filename, 'rb')
        self.__filesize = os.path.getsize(filename)

        try:
            try:
                self.__load_header()
            except EOFError:
                self.size = 0
                raise ID3NoHeaderError(u"{}: too small ({} bytes)".format(
                    filename, self.__filesize))
            except ID3NoHeaderError, ID3UnsupportedVersionError as err:
                self.size = 0
                stack = sys.exc_info()[2]
                try:
                    self.__fileobj.seek(-128,2)
                except EnvironmentError:
                    raise err, None, stack
                else:
                    frames = ParseID3v1(self.__fileobj.read(128))
                    if frames is not None:
                        self.version = (1,1)
                        for f in frames.values():
                            self.add(f)
                    else:
                        raise err, None, stack
                else:
                    frames = self.__known_frames
                    if frames is None:
                        if (2,3,0) <= self.version: frames = Frames
                        elif (2,2,0) <= self.version: frames = Frames_2_2
                    data = self.__fullread(self.size - 10)
                    for frame in self.__read_frames(data, frames = frames):
                        if isinstance(frame, Frame):
                            self.add(frame)
                        else:
                            self.unknown_frames.append(frame)
        finally:
            self.__fileobj.close()
            del self.__fileobj
            del self.__filesize
            if translate:
                self.update_to_v24()

    f_unsynch = property(lambda s: bool(s.__flags & 0x80))
    f_extended = property(lambda s: bool(s.__flags & 0x40))
    f_experimental = property(lambda s: bool(s.__flags & 0x20))
    f_footer = property(lambda s: bool(s.__flags & 0x10))

    def __load_header(self):
        fn = self.filename
        data = self.__fullread(10)
        id3, vmaj, vrev, flags, size = struct.unpack('>3sBBB4s', data)
        self.__flags = flags
        self.size = BitPaddedInt(size) + 10
        self.version = (2, vmaj, vrev)

        if id3 != b'ID3':
            raise ID3NoHeaderError(u"'{}' doesn't start with an ID3 tag".format(fn))
        if vmaj not in [2, 3, 4]:
            raise ID3UnsupportedVersionError(u"'{}' ID3v2.{} not supported".format(fn, vmaj))

        if self.PEDANTIC:
            if (2, 4, 0) <= self.version and (flags & 0x0f):
                raise ValueError(u"'{}' has invalid flags {#02x}".format(fn, flags))
            elif (2, 3, 0) <= self.version < (2, 4, 0) and (flags & 0x1f):
                raise ValueError(u"'{}' has invalid flags {#02x}".format(fn, flags))

        if self.f_extended:
            extsize = self.__fullread(4)
            if extsize in Frames:
                # Some tagger sets the extended header flag but
                # doesn't write an extended header; in this case, the
                # ID3 data follows immediately. Since no extended
                # header is going to be long enough to actually match
                # a frame, and if it's *not* a frame we're going to be
                # completely lost anyway, this seems to be the most
                # correct check.
                # http://code.google.com/p/quodlibet/issues/detail?id=126
                self.__flags ^= 0x40
                self.__extsize = 0
                self.__fileobj.seek(-4, 1)
                self.__readbytes -= 4
            elif self.version >= (2, 4, 0):
                # "Where the 'Extended header size' is the size of the whole
                # extended header, stored as a 32 bit synchsafe integer."
                self.__extsize = BitPaddedInt(extsize) - 4
            else:
                # "Where the 'Extended header size', currently 6 or 10 bytes,
                # excludes itself."
                self.__extsize = struct.unpack('>L', extsize)[0]

            if self.__extsize:
                self.__extdata = self.__fullread(self.__extsize)
            else:
                self.__extdata = b""

class BitPaddedInt(int):
    def __new__(cls, value, bits = 7, bigendian = True):
        "Strips 8-bits bits out of every byte"
        mask = (1 << (bits)) - 1
        if isinstance(value, (int, long)):
            reformed_bytes = []
            while value:
                reformed_bytes.append(value & ((1 << bits) - 1))
                value = value >> 8
        if isinstance(value, str):
            reformed_bytes = [ord(byte) & mask for byte in value]
            if bigendian:
                reformed_bytes.reverse()
        numeric_value = 0
        for shift, byte in zip(range(0, len(reformed_bytes) * bits, bits), reformed_bytes):
            numeric_value += byte << shift

        if isinstance(numeric_value, long):
            self = long.__new__(BitPaddedLong, numeric_value)
        else:
            self = int.__new__(BitPaddedInt, numeric_value)
        self.bits = bits
        self.bigendian = bigendian
        return self

    @staticmethod
    def to_str(value, bits = 7, bigendian = True, width = 4):
        bits = getattr(value, 'bits', bits)
        bigendian = getattr(value, 'bigendian', bigendian)
        value = int(value)
        mask = (1 << bits) - 1
        reformed_bytes = []
        while value:
            reformed_bytes.append(value & mask)
            value = value >> bits
        if width == -1:
            width = max(4, len(bytes))

        if len(bytes) > width:
            raise ValueError(u'Value too wide ({} bytes)'.format(len(reformed_bytes)))
        else:
            reformed_bytes.extend([0] * (width - len(reformed_bytes)))

        if bigendian:
            reformed_bytes.reverse()

        return ''.join(chr(b) for b in reformed_bytes)

class BitPaddedLong(long):
    @staticmethod
    def to_str(value, bits = 7, bigendian = True, width = 4):
        return BitPaddedInt.to_str(value, bits, bigendian, width)

