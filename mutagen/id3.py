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
            except (ID3NoHeaderError, ID3UnsupportedVersionError) as err:
                self.size = 0
                stack = sys.exc_info()[2]
                try:
                    self.__fileobj.seek(-128, 2)
                except EnvironmentError:
                    raise err, None, stack
                else:
                    frames = ParseID3v1(self.__fileobj.read(128))
                    if frames is not None:
                        self.version = (1, 1)
                        for f in frames.values():
                            self.add(f)
                    else:
                        raise err, None, stack
            else:
                frames = self.__known_frames
                if frames is None:
                    if (2, 3, 0) <= self.version:
                        frames = Frames
                    elif (2, 2, 0) <= self.version:
                        frames = Frames_2_2
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

    def getall(self, key):
        """Return all frames with a given name (the list may be empty).

        This is best explained by examples:
            id3.getall('TIT2') == [id3['TIT2']]
            id3.getall('TTTT') == []
            id3.getall('TXXX') == [TXXX(desc='woo', text='bar'),
                                   TXXX(desc='baz', text='quuuux'), ...]

        Since this is based on the frame's HashKey, which is
        colon-separated, you can use it to do things like
        getall('COMM:MusicMatch') or getall('TXXX:QuodLibet:').
        """
        if key in self:
            return [self[key]]
        else:
            key = key + u':'
            return [v for s, v in self.iteritems() if s.startswith(key)]

    def delall(self, key):
        """Delete all tags of a given kind; see getall."""
        if key in self:
            del(self[key])
        else:
            key = key + u":"
            for k in [s for s in self.iterkeys() if s.startswith(key)]:
                del(self[k])

    def setall(self, key, values):
        """Delete frames of the given type and add frames in 'values'."""
        self.delall(key)
        for tag in values:
            self[tag.HashKey] = tag

    def pprint(self):
        """Return tags in a human-readable format.

        "Human-readable" is used loosely here. The format is intended
        to mirror that used for Vorbis or APEv2 output, e.g.
            TIT2=My Title
        However, ID3 frames can have multiple keys:
            POPM=user@example.org=3 128/255
        """
        frames = sorted(Frame.pprint(s) for s in self.itervalues())
        return u'\n'.join(frames)

    def add(self, frame):
        # turn 2.2 into 2.3/2.4 tags
        type_of_frame = type(frame)
        if len(type_of_frame.__name__) == 3:
            tag = type_of_frame.__base__(frame)

        self[tag.HashKey] = tag

    def __determine_bpi(self, data, frames, EMPTY = "\x00" * 10):
        if self.version < (2, 4, 0):
            return int
        # have to special case whether to use bitpaddedints here
        # spec says to use them, but iTunes has it wrong

        # count number of tags found as BitPaddedInt and how far past
        o = 0
        asbpi = 0
        while o < (len(data) - 10):
            part = data[o:o + 10]
            if part == EMPTY:
                bpioff = -((len(data) - o) % 10)
                break
            name, size, flags = struct.unpack('>4sLH', part)
            size = BitPaddedInt(size)
            o += 10 + size
            if name in frames:
                asbpi += 1
        else:
            bpioff = o - len(data)

        # count number of tags found as int and how far past
        o = 0
        asint = 0
        while o < (len(data) - 10):
            part = data[o:o + 10]
            if part == EMPTY:
                intoff = -((len(data) - o) % 10)
                break
            name, size, flags = struct.unpack('>4sLH', part)
            o += 10 + size
            if name in frames:
                asint += 1
        else:
            intoff = o - len(data)

        # if more tags as int, or equal and bpi is past and int is not
        if asint > asbpi or (asint == asbpi and (bpioff >= 1 and intoff <= 1)):
            return int
        return BitPaddedInt

    def __read_frames(self, data, frames):
        if self.version < (2, 4, 0) and self.f_unsynch:
            try:
                data = unsynch.decode(data)
            except ValueError:
                pass

        if (2, 3, 0) <= self.version:
            bpi = self.__determine_bpi(data, frames)
            while data:
                header = data[:10]
                try:
                    name, size, flags = struct.unpack('>4sLH', header)
                except struct.error:
                    return  # not enough header

            if name.strip(b'\x00') == b'':
                return

            size = bpi(size)

            framedata = data[10:10 + size]
            data = data[10 + size:]

            if size == 0:
                continue  # drop empty frames

            try:
                tag = frames[name]
            except KeyError:
                if is_valid_frame_id(name):
                    yield header + framedata
            else:
                try:
                    yield self.__load_framedata(tag, flags, framedata)
                except NotImplementedError:
                    yield header + framedata
                except ID3JunkFrameError:
                    pass

        elif (2, 2, 0) <= self.version:
            while data:
                header = data[0:6]
                try:
                    name, size = unpack('>3s3s', header)
                except struct.error:
                    return  # not enough header

                size = struct.unpack('>L', b'\x00' + size)[0]

                if name.strip(b'\x00') == b'':
                    return

                framedata = data[6:6 + size]
                data = data[6 + size:]

                if size == 0:
                    continue  # drop empty frames

                try:
                    tag = frames[name]
                except KeyError:
                    if is_valid_frame_id(name):
                        yield header + framedata
                else:
                    try:
                        yield self.__load_framedata(tag, 0, framedata)
                    except NotImplementedError:
                        yield header + framedata
                    except ID3JunkFrameError:
                        pass

    def __load_framedata(self, tag, flags, framedata):
        return tag.fromData(self, flags, framedata)

    def delete(self, filename = None, delete_v1 = True, delete_v2 = True):
        """Remove tags from a file.

        If no filename is given, the one most recently loaded is used.

        Keyword arguments:
        delete_v1 -- delete any ID3v1 tag
        delete_v2 -- delete any ID3v2 tag
        """
        if filename is None:
            filename = self.filename
        delete(filename, delete_v1, delete_v2)
        self.clear()

def delete(filename, delete_v1 = True, delete_v2 = True):
    """Remove tags from a file.

    Keyword arguments:
    delete_v1 -- delete any ID3v1 tag
    delete_v2 -- delete any ID3v2 tag
    """

    f = open(filename, 'rb+')

    if delete_v1:
        try:
            f.seek(-128, 2)
        except IOError:
            pass
        else:
            if f.read(3) == "TAG":
                f.seek(-128, 2)
                f.truncate()

    # technically an insize=0 tag is invalid, but we delete it anyway
    # (primarily because we used to write it)
    if delete_v2:
        f.seek(0, 0)
        idata = f.read(10)
        try:
            id3, vmaj, vrev, flags, insize = unpack('>3sBBB4s', idata)
        except struct.error:
            id3, insize = b'', -1

        insize = BitPaddedInt(insize)
        if (id3 == b'ID3') and (insize >= 0):
            delete_bytes(f, insize + 10, 0)

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

# TODO Must be a better way to do this with bytearray?
class unsynch(object):
    @staticmethod
    def decode(value):
        output = []
        safe = True
        append = output.append
        for val in value:
            if safe:
                append(val)
                safe = (val != b'\xFF')
            else:
                if val >= b'\xE0':
                    raise ValueError(u'invalid sync-safe string')
                elif val != b'\x00':
                    append(val)
                safe = True
        if not safe:
            raise ValueError(u'string ended unsafe')

        return b''.join(output)

    @staticmethod
    def encode(value):
        output = []
        safe = True
        append = output.append
        for val in value:
            if safe:
                append(val)
                if val == b'\xFF':
                    safe = False
            elif (val == b'\x00') or (val >= b'\xE0'):
                append(b'\x00')
                append(val)
                safe = (val != b'\xFF')
            else:
                append(val)
                safe = True
        if not safe:
            append(b'\x00')

        return b''.join(output)

class Spec(object):
    def __init__(self, name):
        self.name = name

    def __hash__(self):
        raise TypeError(u"Spec objects are unhashable")

# PYTHON3 This could be problematic - chr and ord don't work with bytes.
class ByteSpec(Spec):
    def read(self, frame, data):
        return ord(data[0]), data[1:]

    def write(self, frame, value):
        return chr(value)

class IntegerSpec(Spec):
    def read(self, frame, data):
        return int(BitPaddedInt(data, bits = 8)), b''

    def write(self, frame, value):
        return BitPaddedInt.to_str(value, bits = 8, width = -1)

    def validate(self, frame, value):
        return value

class SizedIntegerSpec(Spec):
    def __init__(self, name, size):
        self.name, self.__sz = name, size

    def read(self, frame, data):
        return int(BitPaddedInt(data[:self.__sz], bits = 8)), data[self.__sz:]

    def write(self, frame, value):
        return BitPaddedInt.to_str(value, bits = 8, width = self.__sz)

    def validate(self, frame, value):
        return value

class EncodingSpec(ByteSpec):
    def read(self, frame, data):
        enc, data = super(EncodingSpec, self).read(frame, data)
        if enc < 16:
            return enc, data
        else:
            return 0, chr(enc) + data

    def validate(self, frame, value):
        if value is None:
            return None

        if 0 <= value <= 3:
            return value

        raise ValueError(u"Invalid Encoding: {}".format(repr(value)))

# PYTHON3 str() could be problematic
class StringSpec(Spec):
    def __init__(self, name, length):
        super(StringSpec, self).__init__(name)
        self.length = length

    def read(self, frame, data):
        return data[:self.length], data[self.length:]

    def write(self, frame, value):
        if value is None:
            return b'\x00' * self.length
        else:
            return (str(value) + b'\x00' * self.length)[:self.length]

    def validate(self, frame, value):
        if value is None:
            return None

        if isinstance(value, str) and len(value) == self.length:
            return value

        raise ValueError(
              u"Invalid StringSpec[{}] data: {}".format(self.length,
                                                        repr(value)))

