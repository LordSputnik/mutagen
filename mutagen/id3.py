# Written for Python 3

import os.path
import struct
import sys

import mutagen

class error(Exception): pass
class ID3NoHeaderError(error, ValueError): pass
class ID3BadUnsynchData(error, ValueError): pass
class ID3BadCompressedData(error, ValueError): pass
class ID3TagError(error, ValueError): pass
class ID3UnsupportedVersionError(error, NotImplementedError): pass
class ID3EncryptionUnsupportedError(error, NotImplementedError): pass
class ID3JunkFrameError(error, ValueError): pass
class ID3Warning(error, UserWarning): pass

class ID3(mutagen.Metadata):

    def __init__(self, *args, **kwargs):
        # Initialize the metadata base class with any input arguments.
        super(ID3, self).__init__(*args, **kwargs)

        self.unknown_frames = list()

        self.PEDANTIC = True
        self.version = (2,4,0)

    # Read size bytes of the file. Returns raw bytes.
    def __fullread(self, size):
        """ Read a certain number of bytes from the source file. """
        try:
            if size < 0:
                raise ValueError("Requested bytes ({}) less than zero".format(size))
            if size > self.__filesize:
                raise EOFError("Requested {:#x} of {:#x} {}".format(
                        long(size), long(self.__filesize), self.filename))
        except AttributeError:
            pass

        #Read binary data (bytes)
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
                raise ID3NoHeaderError("{}: too small ({} bytes)".format(
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

    def __load_header(self):
        fn = self.filename
        data = self.__fullread(10)
        id3, vmaj, vrev, flags, size = struct.unpack('>3sBBB4s', data)
        self.__flags = flags
        self.size = BitPaddedInt(size) + 10
        self.version = (2, vmaj, vrev)

        if id3 != b'ID3':
            raise ID3NoHeaderError("'{}' doesn't start with an ID3 tag".format(fn))
        if vmaj not in {2, 3, 4}:
            raise ID3UnsupportedVersionError("'{}' ID3v2.{} not supported".format(fn, vmaj))

        if self.PEDANTIC:
            if ((2, 4, 0) <= self.version) and (flags & 0x0f):
                raise ValueError("'{}' has invalid flags {#02x}".format(fn,flags))
            elif ((2, 3, 0) <= self.version < (2, 4, 0)) and (flags & 0x1f):
                raise ValueError("'{}' has invalid flags {#02x}".format(fn, flags))

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
                self.__extdata = b''

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
            key = key + ':'
            return [v for s, v in self.iteritems() if s.startswith(key)]

    def delall(self, key):
        """Delete all tags of a given kind; see getall."""
        if key in self:
            del(self[key])
        else:
            key = key + ":"
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
        return '\n'.join(frames)

    def add(self, frame):
        # turn 2.2 into 2.3/2.4 tags
        type_of_frame = type(frame)
        if len(type_of_frame.__name__) == 3:
            tag = type_of_frame.__base__(frame)

        self[tag.HashKey] = tag

class BitPaddedInt(int):
    def __new__(cls, value, bits = 7, bigendian = True):
        "Strips 8-bits bits out of every byte"
        mask = (1 << (bits)) - 1
        if isinstance(value, int):
            reformed_bytes = []
            while value:
                reformed_bytes.append(value & ((1 << bits) - 1))
                value = value >> 8
        if isinstance(value, bytes):
            reformed_bytes = [b & mask for b in value]
            if bigendian:
                reformed_bytes.reverse()
        numeric_value = 0
        for shift, byte in zip(range(0, len(reformed_bytes) * bits, bits), reformed_bytes):
            numeric_value += byte << shift

        self = int.__new__(BitPaddedInt, numeric_value)
        self.bits = bits
        self.bigendian = bigendian
        return self

    @staticmethod
    def to_bytes(value, bits = 7, bigendian = True, width = 4):
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

        return b''.join(reformed_bytes)

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
                    raise ValueError("invalid sync-safe string")
                elif val != b'\x00':
                    append(val)
                safe = True
        if not safe:
            raise ValueError("string ended unsafe")

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
        raise TypeError("Spec objects are unhashable")

class ByteSpec(Spec):
    def read(self, frame, data):
        return data[0], data[1:]

    def write(self, frame, value):
        return value

class IntegerSpec(Spec):
    def read(self, frame, data):
        return int(BitPaddedInt(data, bits = 8)), b''

    def write(self, frame, value):
        return BitPaddedInt.to_bytes(value, bits = 8, width = -1)

    def validate(self, frame, value):
        return value

class SizedIntegerSpec(Spec):
    def __init__(self, name, size):
        self.name, self.__sz = name, size

    def read(self, frame, data):
        return int(BitPaddedInt(data[:self.__sz], bits = 8)), data[self.__sz:]

    def write(self, frame, value):
        return BitPaddedInt.to_bytes(value, bits = 8, width = self.__sz)

    def validate(self, frame, value):
        return value

class EncodingSpec(ByteSpec):
    def read(self, frame, data):
        enc, data = super(EncodingSpec, self).read(frame, data)
        if enc < 16:
            return enc, data
        else:
            return 0, bytes(bytes([enc]) + data)

    def validate(self, frame, value):
        if value is None:
            return None

        if 0 <= value <= 3:
            return value

        raise ValueError("Invalid Encoding: {}".format(repr(value)))

class BinaryDataSpec(Spec):
    def read(self, frame, data):
        return data, ''

    def write(self, frame, value):
        return bytes(value)

    def validate(self, frame, value):
        return bytes(value)

class ASCIIStringSpec(Spec):
    def __init__(self, name, length):
        super(NamedStringSpec, self).__init__(name)
        self.length = length

    def read(self, frame, data):
        return data[:self.length], data[self.length:]

    def write(self, frame, value):
        if value is None:
            return b'\x00' * self.length
        else:
            return (bytes(value) + b'\x00' * self.length)[:self.length]

    def validate(self, frame, value):
        if value is None:
            return None

        if isinstance(value, bytes) and len(value) == self.length:
            return value

        raise ValueError("Invalid StringSpec[{}] data: {}".format(
                         self.length, repr(value)))

class EncodedTextSpec(Spec):
    # Okay, seriously. This is private and defined explicitly and
    # completely by the ID3 specification. You can't just add
    # encodings here however you want.
    _encodings = ( ('latin1', '\x00'), ('utf16', '\x00\x00'),
                   ('utf_16_be', '\x00\x00'), ('utf8', '\x00') )

    def read(self, frame, data):
        enc, term = self._encodings[frame.encoding]
        ret = b""
        if len(term) == 1:
            if term in data:
                data, ret = data.split(term, 1)
        else:
            offset = -1
            try:
                while True:
                    offset = data.index(term, offset+1)
                    if offset & 1:
                        continue
                    data, ret = data[0:offset], data[offset+2:]
                    break

            except ValueError:
                pass

        if len(data) < len(term):
            return "", ret

        return data.decode(enc), ret

    def write(self, frame, value):
        enc, term = self._encodings[frame.encoding]

        return value.encode(enc) + term

    def validate(self, frame, value):
        return str(value)