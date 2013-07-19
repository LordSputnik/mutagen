# Written for Python 3

import os.path
import struct
import sys
import re

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

def is_valid_frame_id(frame_id):
    return frame_id.isalnum() and frame_id.isupper()

class ID3(mutagen.Metadata):

    def __init__(self, *args, **kwargs):
        self.unknown_frames = list()

        self.PEDANTIC = True
        self.version = (2,4,0)
        self.__readbytes = 0
        self.__flags = 0

        # Initialize the metadata base class with any input arguments.
        super(ID3, self).__init__(*args, **kwargs)

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
                    raise err.with_traceback(stack)
                else:
                    frames = ParseID3v1(self.__fileobj.read(128))
                    if frames is not None:
                        self.version = (1, 1)
                        for f in frames.values():
                            self.add(f)
                    else:
                        raise err.with_traceback(stack)
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

    def __determine_bpi(self, data, frames, EMPTY="\x00" * 10):
        if self.version < (2, 4, 0):
            return int
        # have to special case whether to use bitpaddedints here
        # spec says to use them, but iTunes has it wrong

        # count number of tags found as BitPaddedInt and how far past
        o = 0
        asbpi = 0
        while o < len(data) - 10:
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
        while o < len(data) - 10:
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
        if self.version < (2,4,0) and self.f_unsynch:
            try:
                data = unsynch.decode(data)
            except ValueError:
                pass

        if (2,3,0) <= self.version:
            bpi = self.__determine_bpi(data, frames)
            while data:
                header = data[:10]
                try:
                    name, size, flags = struct.unpack('>4sLH', header)
                except struct.error:
                    return # not enough header
                if name.strip(b'\x00') == b'':
                    return

                name = name.decode('ascii')

                size = bpi(size)
                framedata = data[10:10+size]
                data = data[10+size:]
                if size == 0:
                    continue # drop empty frames
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

        elif (2,2,0) <= self.version:
            while data:
                header = data[0:6]
                try:
                    name, size = struct.unpack('>3s3s', header)
                except struct.error:
                    return # not enough header

                size = struct.unpack('>L', '\x00'+size)[0]

                if name.strip(b'\x00') == b'':
                    return

                framedata = data[6:6+size]
                data = data[6+size:]

                if size == 0:
                    continue # drop empty frames

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

    f_unsynch = property(lambda s: bool(s.__flags & 0x80))
    f_extended = property(lambda s: bool(s.__flags & 0x40))
    f_experimental = property(lambda s: bool(s.__flags & 0x20))
    f_footer = property(lambda s: bool(s.__flags & 0x10))

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
        frames = sorted(Frame.pprint(s) for s in self.values())
        return '\n'.join(frames)

    def add(self, frame):
        # turn 2.2 into 2.3/2.4 tags
        type_of_frame = type(frame)
        if len(type_of_frame.__name__) == 3:
            frame = type_of_frame.__base__(frame)

        self[frame.HashKey] = frame

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


# As far as I can tell, the purpose of validate is to return valid data for
# write, and if it can't do that, raise an exception. I've rewritten a few
# with this in mind.

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

    def validate(self, frame, value):
        if value is None:
            return None

        return bytes([value])[0]

class IntegerSpec(Spec):
    def read(self, frame, data):
        return int(BitPaddedInt(data, bits = 8)), b''

    def write(self, frame, value):
        return BitPaddedInt.to_bytes(value, bits = 8, width = -1)

    def validate(self, frame, value):
        return int(value)

class SizedIntegerSpec(Spec):
    def __init__(self, name, size):
        self.name, self.__sz = name, size

    def read(self, frame, data):
        return int(BitPaddedInt(data[:self.__sz], bits = 8)), data[self.__sz:]

    def write(self, frame, value):
        return BitPaddedInt.to_bytes(value, bits = 8, width = self.__sz)

    def validate(self, frame, value):
        return int(value)

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
        return data, b''

    def write(self, frame, value):
        return value

    def validate(self, frame, value):
        if value is None:
            return None

        return bytes(value)

class ASCIIStringSpec(Spec):
    def __init__(self, name, length):
        super(ASCIIStringSpec, self).__init__(name)
        self.length = length

    def read(self, frame, data):
        return data[:self.length].decode('ascii'), data[self.length:]

    def write(self, frame, value):
        if value is None:
            return b'\x00' * self.length
        else:
            return (value.encode('ascii') + b'\x00' * self.length)[:self.length]

    def validate(self, frame, value):
        if value is None:
            return None

        encoded = value.encode('ascii')

        if len(encoded) == self.length:
            return value

        raise ValueError("Invalid StringSpec[{}] data: {}".format(
                         self.length, repr(value)))

class Latin1TextSpec(Spec):
    def read(self, frame, data):
        if b"\x00" in data:
            data, ret = data.split(b'\x00',1)
        else:
            ret = b""
        return data.decode('latin1'), ret

    def write(self, data, value):
        return value.encode('latin1') + '\x00'

    def validate(self, frame, value):
        if value is None:
            return None

        return value.encode('latin').decode('latin1')

class EncodedTextSpec(Spec):
    # Okay, seriously. This is private and defined explicitly and
    # completely by the ID3 specification. You can't just add
    # encodings here however you want.
    _encodings = ( ('latin1', b'\x00'), ('utf16', b'\x00\x00'),
                   ('utf_16_be', b'\x00\x00'), ('utf8', b'\x00') )

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
        if value is None:
            return None

        enc = self._encodings[frame.encoding][0]

        return value.encode(enc).decode(enc)

class EncodedNumericTextSpec(EncodedTextSpec): pass
class EncodedNumericPartTextSpec(EncodedTextSpec): pass

class MultiSpec(Spec):
    def __init__(self, name, *specs, **kw):
        super(MultiSpec, self).__init__(name)
        self.specs = specs
        self.sep = kw.get('sep')

    def read(self, frame, data):
        values = []
        while data:
            record = []
            for spec in self.specs:
                value, data = spec.read(frame, data)
                record.append(value)
            if len(self.specs) != 1:
                values.append(record)
            else:
                values.append(record[0])

        return values, data

    def write(self, frame, values):
        data = []

        if len(self.specs) == 1:
            for v in values:
                data.append(self.specs[0].write(frame, v))
        else:
            for record in values:
                for v, s in zip(record, self.specs):
                    data.append(s.write(frame, v))
        return b''.join(data)

    def validate(self, frame, value):
        if value is None:
            return []

        if self.sep and isinstance(value, bytes):
            value = value.split(self.sep)

        if isinstance(value, list):
            if len(self.specs) == 1:
                return [self.specs[0].validate(frame, v) for v in value]
            else:
                return [
                    [s.validate(frame, v) for (v,s) in zip(val, self.specs)]
                    for val in value ]

        raise ValueError("Invalid MultiSpec data: {}".format(repr(value)))

class ID3TimeStamp(object):
    """A time stamp in ID3v2 format.

    This is a restricted form of the ISO 8601 standard; time stamps
    take the form of:
        YYYY-MM-DD HH:MM:SS
    Or some partial form (YYYY-MM-DD HH, YYYY, etc.).

    The 'text' attribute contains the raw text data of the time stamp.
    """

    def __init__(self, text):
        if isinstance(text, ID3TimeStamp):
            text = text.text

        if not isinstance(text, str):
            raise TypeError(
            "ID3TimeStamp input type must be string or ID3TimeStamp")

        self.year = self.month = self.day = None
        self.hour = self.minute = self.second = None

        self.text = text

    def get_text(self):
        data = [(self.year, '{:04d}-'), (self.month, '{:02d}-'),
                (self.day, '{:02d} '), (self.hour, '{:02d}:'),
                (self.minute, '{:02d}:'), (self.second, '{:02d}x')]

        return ''.join(p[1].format(p[0]) for p in data if p[0] is not None)[:-1]

    def set_text(self, text, splitre=re.compile('[-T:/.]|\s+')):
        data = splitre.split(text + ':::::')[:6]

        for i, a in enumerate('year month day hour minute second'.split()):
            try:
                setattr(self, a, int(data[i]))
            except ValueError:
                break

    text = property(get_text, set_text, doc="ID3v2.4 date and time.")

    def __str__(self):
        return self.text

    def __repr__(self):
        return repr(self.text)

    def __cmp__(self, other):
        return cmp(self.text, other.text)

    __hash__ = object.__hash__
    def encode(self, *args, **kwargs):
        return self.text.encode(*args, **kwargs)

class TimeStampSpec(EncodedTextSpec):
    def read(self, frame, data):
        value, data = super(TimeStampSpec, self).read(frame, data)
        return self.validate(frame, value), data

    def write(self, frame, data):
        return super(TimeStampSpec, self).write(frame,
                data.text.replace(' ', 'T'))

    def validate(self, frame, value):
        try:
            return ID3TimeStamp(value)
        except TypeError:
            raise ValueError("Invalid ID3TimeStamp: {}".format(repr(value)))

class ChannelSpec(ByteSpec):
    (OTHER, MASTER, FRONTRIGHT, FRONTLEFT, BACKRIGHT, BACKLEFT, FRONTCENTRE,
     BACKCENTRE, SUBWOOFER) = range(9)

class VolumeAdjustmentSpec(Spec):
    def read(self, frame, data):
        value = unpack('>h', data[0:2])[0]
        return value/512, data[2:]

    def write(self, frame, value):
        return pack('>h', int(round(value * 512)))

    def validate(self, frame, value):
        return value

class VolumePeakSpec(Spec):
    def read(self, frame, data):
        # http://bugs.xmms.org/attachment.cgi?id=113&action=view
        peak = 0
        bits = data[0]
        vol_bytes = min(4, (bits + 7) >> 3)

        # not enough frame data
        if vol_bytes + 1 > len(data):
            raise ID3JunkFrameError

        shift = ((8 - (bits & 7)) & 7) + (4 - vol_bytes) * 8

        for i in range(1, vol_bytes+1):
            peak *= 256
            peak += data[i]

        peak *= 2**shift
        return (float(peak) / (2**31-1)), data[1+vol_bytes:]

    def write(self, frame, value):
        # always write as 16 bits for sanity.
        return b"\x10" + pack('>H', int(round(value * 32768)))

    def validate(self, frame, value):
        return value

class SynchronizedTextSpec(EncodedTextSpec):
    def read(self, frame, data):
        texts = []
        encoding, term = self._encodings[frame.encoding]
        while data:
            l = len(term)
            try:
                value_idx = data.index(term)
            except ValueError:
                raise ID3JunkFrameError

            value = data[:value_idx].decode(encoding)

            if len(data) < value_idx + l + 4:
                raise ID3JunkFrameError

            time = struct.unpack(">I", data[value_idx+l:value_idx+l+4])[0]
            texts.append((value, time))
            data = data[value_idx+l+4:]
        return texts, b""

    def write(self, frame, value):
        data = []
        encoding, term = self._encodings[frame.encoding]
        for text, time in frame.text:
            text = text.encode(encoding) + term
            data.append(text + struct.pack(">I", time))
        return b"".join(data)

    def validate(self, frame, value):
        return value

class KeyEventSpec(Spec):
    def read(self, frame, data):
        events = []
        while len(data) >= 5:
            events.append(struct.unpack(">bI", data[:5]))
            data = data[5:]
        return events, data

    def write(self, frame, value):
        return b"".join(struct.pack(">bI", *event) for event in value)

    def validate(self, frame, value):
        return value

class VolumeAdjustmentsSpec(Spec):
    # Not to be confused with VolumeAdjustmentSpec.
    def read(self, frame, data):
        adjustments = {}
        while len(data) >= 4:
            freq, adj = struct.unpack(">Hh", data[:4])
            data = data[4:]
            freq /= 2
            adj /= 512
            adjustments[freq] = adj
        adjustments = sorted(adjustments.items())
        return adjustments, data

    def write(self, frame, value):
        return b"".join(struct.pack(">Hh", int(freq * 2), int(adj * 512))
                        for (freq, adj) in sorted(value))

    def validate(self, frame, value):
        return value

class ASPIIndexSpec(Spec):
    def read(self, frame, data):
        if frame.b == 16:
            data_format = "H"
            size = 2
        elif frame.b == 8:
            data_format = "B"
            size = 1
        else:
            warn("invalid bit count in ASPI (%d)" % frame.b, ID3Warning)
            return [], data

        indexes = data[:frame.N * size]
        data = data[frame.N * size:]
        return list(struct.unpack(">" + data_format * frame.N, indexes)), data

    def write(self, frame, values):
        if frame.b == 16:
            data_format = "H"
        elif frame.b == 8:
            data_format = "B"
        else:
            raise ValueError("frame.b must be 8 or 16")

        return struct.pack(">" + data_format * frame.N, *values)

    def validate(self, frame, values):
        return values

class Frame(object):
    """Fundamental unit of ID3 data.

    ID3 tags are split into frames. Each frame has a potentially
    different structure, and so this base class is not very featureful.
    """

    FLAG23_ALTERTAG     = 0x8000
    FLAG23_ALTERFILE    = 0x4000
    FLAG23_READONLY     = 0x2000
    FLAG23_COMPRESS     = 0x0080
    FLAG23_ENCRYPT      = 0x0040
    FLAG23_GROUP        = 0x0020

    FLAG24_ALTERTAG     = 0x4000
    FLAG24_ALTERFILE    = 0x2000
    FLAG24_READONLY     = 0x1000
    FLAG24_GROUPID      = 0x0040
    FLAG24_COMPRESS     = 0x0008
    FLAG24_ENCRYPT      = 0x0004
    FLAG24_UNSYNCH      = 0x0002
    FLAG24_DATALEN      = 0x0001

    _framespec = []
    def __init__(self, *args, **kwargs):
        if len(args)==1 and len(kwargs)==0 and isinstance(args[0], type(self)):
            other = args[0]
            for checker in self._framespec:
                val = checker.validate(self, getattr(other, checker.name))
                setattr(self, checker.name, val)
        else:
            for checker, val in zip(self._framespec, args):
                setattr(self, checker.name, checker.validate(self, val))
            for checker in self._framespec[len(args):]:
                validated = checker.validate(
                    self, kwargs.get(checker.name, None))
                setattr(self, checker.name, validated)

    HashKey = property(
        lambda s: s.FrameID,
        doc="an internal key used to ensure frame uniqueness in a tag")
    FrameID = property(
        lambda s: type(s).__name__,
        doc="ID3v2 three or four character frame ID")

    def __repr__(self):
        """Python representation of a frame.

        The string returned is a valid Python expression to construct
        a copy of this frame.
        """
        kw = ["{}={}".format(a.name, repr(getattr(self, a.name)))
              for a in self._framespec]

        return "{}({})".format(type(self).__name__, ', '.join(kw))

    def _readData(self, data):
        odata = data
        for reader in self._framespec:
            if len(data):
                try:
                    value, data = reader.read(self, data)
                except UnicodeDecodeError:
                    raise ID3JunkFrameError
            else:
                raise ID3JunkFrameError
            setattr(self, reader.name, value)
        if data.strip(b'\x00'):
            warn("Leftover data: {}: {} (from {})".format(type(self).__name__,
                 repr(data), repr(odata)), ID3Warning)

    def _writeData(self):
        data = [w.write(self, getattr(self, w.name)) for w in self._framespec]

        return b''.join(data)

    def pprint(self):
        """Return a human-readable representation of the frame."""
        return "{}={}".format(type(self).__name__, self._pprint())

    def _pprint(self):
        return "[unrepresentable data]"

    @classmethod
    def fromData(cls, id3, tflags, data):
        """Construct this ID3 frame from raw string data."""

        if (2,4,0) <= id3.version:
            if tflags & (Frame.FLAG24_COMPRESS | Frame.FLAG24_DATALEN):
                # The data length int is syncsafe in 2.4 (but not 2.3).
                # However, we don't actually need the data length int,
                # except to work around a QL 0.12 bug, and in that case
                # all we need are the raw bytes.
                datalen_bytes = data[:4]
                data = data[4:]
            if tflags & Frame.FLAG24_UNSYNCH or id3.f_unsynch:
                try:
                    data = unsynch.decode(data)
                except ValueError as err:
                    if id3.PEDANTIC:
                        raise ID3BadUnsynchData('{}: {}'.format(err,
                                                repr(data)))
            if tflags & Frame.FLAG24_ENCRYPT:
                raise ID3EncryptionUnsupportedError
            if tflags & Frame.FLAG24_COMPRESS:
                try:
                    data = data.decode('zlib')
                except zlibError as err:
                    # the initial mutagen that went out with QL 0.12 did not
                    # write the 4 bytes of uncompressed size. Compensate.
                    data = datalen_bytes + data
                    try:
                        data = data.decode('zlib')
                    except zlibError as err:
                        if id3.PEDANTIC:
                            raise ID3BadCompressedData('{}: {}'.format(err,
                                                       repr(data)))

        elif (2,3,0) <= id3.version:
            if tflags & Frame.FLAG23_COMPRESS:
                usize = unpack('>L', data[:4])[0]
                data = data[4:]
            if tflags & Frame.FLAG23_ENCRYPT:
                raise ID3EncryptionUnsupportedError
            if tflags & Frame.FLAG23_COMPRESS:
                try:
                    data = data.decode('zlib')
                except zlibError as err:
                    if id3.PEDANTIC:
                        raise ID3BadCompressedData('{}: {}'.format(err,
                                                   repr(data)))

        frame = cls()
        frame._rawdata = data
        frame._flags = tflags
        frame._readData(data)
        return frame

    def __hash__(self):
        raise TypeError("Frame objects are unhashable")

class FrameOpt(Frame):
    """A frame with optional parts.

    Some ID3 frames have optional data; this class extends Frame to
    provide support for those parts.
    """
    _optionalspec = []

    def __init__(self, *args, **kwargs):
        super(FrameOpt, self).__init__(*args, **kwargs)
        for spec in self._optionalspec:
            if spec.name in kwargs:
                validated = spec.validate(self, kwargs[spec.name])
                setattr(self, spec.name, validated)
            else:
                break

    def _readData(self, data):
        odata = data
        for r in self._framespec:
            if len(data):
                value, data = r.read(self, data)
            else:
                raise ID3JunkFrameError
            setattr(self, r.name, value)
        if data:
            for r in self._optionalspec:
                if len(data):
                    value, data = r.read(self, data)
                else:
                    break
                setattr(self, r.name, value)
        if data.strip('\x00'):
            warn("Leftover data: {}: {} (from {})".format(type(self).__name__,
                 repr(data), repr(odata)), ID3Warning)

    def _writeData(self):
        data = [w.write(self, getattr(self, w.name)) for w in self._framespec]

        for w in self._optionalspec:
            try:
                data.append(w.write(self, getattr(self, w.name)))
            except AttributeError:
                break

        return b''.join(data)

    def __repr__(self):

        kw = ["{}={}".format(a.name, repr(getattr(self, a.name)))
              for a in self._framespec]

        for attr in self._optionalspec:
            if hasattr(self, attr.name):
                kw.append('{}={}'.format(attr.name,
                                         repr(getattr(self, attr.name))))

        return '{}({})'.format(type(self).__name__, ', '.join(kw))

class TextFrame(Frame):
    """Text strings.

    Text frames support casts to unicode or str objects, as well as
    list-like indexing, extend, and append.

    Iterating over a TextFrame iterates over its strings, not its
    characters.

    Text frames have a 'text' attribute which is the list of strings,
    and an 'encoding' attribute; 0 for ISO-8859 1, 1 UTF-16, 2 for
    UTF-16BE, and 3 for UTF-8. If you don't want to worry about
    encodings, just set it to 3.
    """

    _framespec = [ EncodingSpec('encoding'),
        MultiSpec('text', EncodedTextSpec('text'), sep=u'\u0000') ]

    def __str__(self):
        return '\u0000'.join(self.text)

    def __eq__(self, other):
        if isinstance(other, str):
            return str(self) == other

        return self.text == other

    __hash__ = Frame.__hash__

    def __getitem__(self, item):
        return self.text[item]

    def __iter__(self):
        return iter(self.text)

    def append(self, value):
        return self.text.append(value)

    def extend(self, value):
        return self.text.extend(value)

    def _pprint(self):
        return " / ".join(self.text)

class NumericTextFrame(TextFrame):
    """Numerical text strings.

    The numeric value of these frames can be gotten with unary plus, e.g.
        frame = TLEN('12345')
        length = +frame
    """

    _framespec = [ EncodingSpec('encoding'),
        MultiSpec('text', EncodedNumericTextSpec('text'), sep=u'\u0000') ]

    def __pos__(self):
        """Return the numerical value of the string."""
        return int(self.text[0])

class NumericPartTextFrame(TextFrame):
    """Multivalue numerical text strings.

    These strings indicate 'part (e.g. track) X of Y', and unary plus
    returns the first value:
        frame = TRCK('4/15')
        track = +frame # track == 4
    """

    _framespec = [ EncodingSpec('encoding'),
        MultiSpec('text', EncodedNumericPartTextSpec('text'), sep=u'\u0000') ]

    def __pos__(self):
        return int(self.text[0].split("/")[0])

class TimeStampTextFrame(TextFrame):
    """A list of time stamps.

    The 'text' attribute in this frame is a list of ID3TimeStamp
    objects, not a list of strings.
    """

    _framespec = [ EncodingSpec('encoding'),
        MultiSpec('text', TimeStampSpec('stamp'), sep=u',') ]

    def __str__(self):
        return ','.join(stamp.text for stamp in self.text)

    def _pprint(self):
        return " / ".join(stamp.text for stamp in self.text)

class UrlFrame(Frame):
    """A frame containing a URL string.

    The ID3 specification is silent about IRIs and normalized URL
    forms. Mutagen assumes all URLs in files are encoded as Latin 1,
    but string conversion of this frame returns a UTF-8 representation
    for compatibility with other string conversions.

    The only sane way to handle URLs in MP3s is to restrict them to
    ASCII.
    """

    _framespec = [ Latin1TextSpec('url') ]

    def __str__(self):
        return self.url

    def __eq__(self, other):
        return self.url == other

    __hash__ = Frame.__hash__

    _pprint = __str__

class UrlFrameU(UrlFrame):
    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.url))

class TALB(TextFrame): "Album"
class TBPM(NumericTextFrame): "Beats per minute"
class TCOM(TextFrame): "Composer"



class TCOP(TextFrame): "Copyright (c)"
class TCMP(NumericTextFrame): "iTunes Compilation Flag"
class TDAT(TextFrame): "Date of recording (DDMM)"
class TDEN(TimeStampTextFrame): "Encoding Time"
class TDOR(TimeStampTextFrame): "Original Release Time"
class TDLY(NumericTextFrame): "Audio Delay (ms)"
class TDRC(TimeStampTextFrame): "Recording Time"
class TDRL(TimeStampTextFrame): "Release Time"
class TDTG(TimeStampTextFrame): "Tagging Time"
class TENC(TextFrame): "Encoder"
class TEXT(TextFrame): "Lyricist"
class TFLT(TextFrame): "File type"
class TIME(TextFrame): "Time of recording (HHMM)"
class TIT1(TextFrame): "Content group description"
class TIT2(TextFrame): "Title"
class TIT3(TextFrame): "Subtitle/Description refinement"
class TKEY(TextFrame): "Starting Key"
class TLAN(TextFrame): "Audio Languages"
class TLEN(NumericTextFrame): "Audio Length (ms)"
class TMED(TextFrame): "Source Media Type"
class TMOO(TextFrame): "Mood"
class TOAL(TextFrame): "Original Album"
class TOFN(TextFrame): "Original Filename"
class TOLY(TextFrame): "Original Lyricist"
class TOPE(TextFrame): "Original Artist/Performer"
class TORY(NumericTextFrame): "Original Release Year"
class TOWN(TextFrame): "Owner/Licensee"
class TPE1(TextFrame): "Lead Artist/Performer/Soloist/Group"
class TPE2(TextFrame): "Band/Orchestra/Accompaniment"
class TPE3(TextFrame): "Conductor"
class TPE4(TextFrame): "Interpreter/Remixer/Modifier"
class TPOS(NumericPartTextFrame): "Part of set"
class TPRO(TextFrame): "Produced (P)"
class TPUB(TextFrame): "Publisher"
class TRCK(NumericPartTextFrame): "Track Number"
class TRDA(TextFrame): "Recording Dates"
class TRSN(TextFrame): "Internet Radio Station Name"
class TRSO(TextFrame): "Internet Radio Station Owner"
class TSIZ(NumericTextFrame): "Size of audio data (bytes)"
class TSO2(TextFrame): "iTunes Album Artist Sort"
class TSOA(TextFrame): "Album Sort Order key"
class TSOC(TextFrame): "iTunes Composer Sort"
class TSOP(TextFrame): "Perfomer Sort Order key"
class TSOT(TextFrame): "Title Sort Order key"
class TSRC(TextFrame): "International Standard Recording Code (ISRC)"
class TSSE(TextFrame): "Encoder settings"
class TSST(TextFrame): "Set Subtitle"
class TYER(NumericTextFrame): "Year of recording"

class TXXX(TextFrame):
    """User-defined text data.

    TXXX frames have a 'desc' attribute which is set to any Unicode
    value (though the encoding of the text and the description must be
    the same). Many taggers use this frame to store freeform keys.
    """
    _framespec = [ EncodingSpec('encoding'), EncodedTextSpec('desc'),
        MultiSpec('text', EncodedTextSpec('text'), sep=u'\u0000') ]
    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

    def _pprint(self):
        return "{}={}".format(self.desc, " / ".join(self.text))

class WCOM(UrlFrameU): "Commercial Information"
class WCOP(UrlFrame): "Copyright Information"
class WOAF(UrlFrame): "Official File Information"
class WOAR(UrlFrameU): "Official Artist/Performer Information"
class WOAS(UrlFrame): "Official Source Information"
class WORS(UrlFrame): "Official Internet Radio Information"
class WPAY(UrlFrame): "Payment Information"
class WPUB(UrlFrame): "Official Publisher Information"

class WXXX(UrlFrame):
    """User-defined URL data.

    Like TXXX, this has a freeform description associated with it.
    """
    _framespec = [ EncodingSpec('encoding'), EncodedTextSpec('desc'),
        Latin1TextSpec('url') ]
    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

class PairedTextFrame(Frame):
    """Paired text strings.

    Some ID3 frames pair text strings, to associate names with a more
    specific involvement in the song. The 'people' attribute of these
    frames contains a list of pairs:
        [['trumpet', 'Miles Davis'], ['bass', 'Paul Chambers']]

    Like text frames, these frames also have an encoding attribute.
    """

    _framespec = [ EncodingSpec('encoding'), MultiSpec('people',
        EncodedTextSpec('involvement'), EncodedTextSpec('person')) ]

    def __eq__(self, other):
        return self.people == other

    __hash__ = Frame.__hash__

class TIPL(PairedTextFrame): "Involved People List"
class TMCL(PairedTextFrame): "Musicians Credits List"
class IPLS(TIPL): "Involved People List"

class BinaryFrame(Frame):
    """Binary data

    The 'data' attribute contains the raw byte string.
    """
    _framespec = [ BinaryDataSpec('data') ]

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

class MCDI(BinaryFrame): "Binary dump of CD's TOC"

class ETCO(Frame):
    """Event timing codes."""
    _framespec = [ ByteSpec("format"), KeyEventSpec("events") ]

    def __eq__(self, other):
        return self.events == other

    __hash__ = Frame.__hash__

class MLLT(Frame):
    """MPEG location lookup table.

    This frame's attributes may be changed in the future based on
    feedback from real-world use.
    """
    _framespec = [ SizedIntegerSpec('frames', 2),
                   SizedIntegerSpec('bytes', 3),
                   SizedIntegerSpec('milliseconds', 3),
                   ByteSpec('bits_for_bytes'),
                   ByteSpec('bits_for_milliseconds'),
                   BinaryDataSpec('data') ]

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

class SYTC(Frame):
    """Synchronised tempo codes.

    This frame's attributes may be changed in the future based on
    feedback from real-world use.
    """
    _framespec = [ ByteSpec("format"), BinaryDataSpec("data") ]

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

class USLT(Frame):
    """Unsynchronised lyrics/text transcription.

    Lyrics have a three letter ISO language code ('lang'), a
    description ('desc'), and a block of plain text ('text').
    """

    _framespec = [ EncodingSpec('encoding'), ASCIIStringSpec('lang', 3),
        EncodedTextSpec('desc'), EncodedTextSpec('text') ]

    HashKey = property(lambda s: '{}:{}:{}'.format(s.FrameID, s.desc,
                       repr(s.lang)))

    def __str__(self):
        return self.text

    def __eq__(self, other):
        return self.text == other

    __hash__ = Frame.__hash__

class SYLT(Frame):
    """Synchronised lyrics/text."""

    _framespec = [ EncodingSpec('encoding'), ASCIIStringSpec('lang', 3),
        ByteSpec('format'), ByteSpec('type'), EncodedTextSpec('desc'),
        SynchronizedTextSpec('text') ]

    HashKey = property(lambda s: '{}:{}:{}'.format(s.FrameID, s.desc,
                       repr(s.lang)))

    def __eq__(self, other):
        return str(self) == other

    __hash__ = Frame.__hash__

    def __str__(self):
        return "".join(text for (text, time) in self.text)

class COMM(TextFrame):
    """User comment.

    User comment frames have a descrption, like TXXX, and also a three
    letter ISO language code in the 'lang' attribute.
    """
    _framespec = [ EncodingSpec('encoding'), ASCIIStringSpec('lang', 3),
        EncodedTextSpec('desc'),
        MultiSpec('text', EncodedTextSpec('text'), sep=u'\u0000') ]

    HashKey = property(lambda s: '{}:{}:{}'.format(s.FrameID, s.desc,
                       repr(s.lang)))

    def _pprint(self):
        return "{}={}={}".format(self.desc, repr(self.lang),
                                 " / ".join(self.text))

class RVA2(Frame):
    """Relative volume adjustment (2).

    This frame is used to implemented volume scaling, and in
    particular, normalization using ReplayGain.

    Attributes:
    desc -- description or context of this adjustment
    channel -- audio channel to adjust (master is 1)
    gain -- a + or - dB gain relative to some reference level
    peak -- peak of the audio as a floating point number, [0, 1]

    When storing ReplayGain tags, use descriptions of 'album' and
    'track' on channel 1.
    """

    _framespec = [ Latin1TextSpec('desc'), ChannelSpec('channel'),
        VolumeAdjustmentSpec('gain'), VolumePeakSpec('peak') ]
    _channels = ["Other", "Master volume", "Front right", "Front left",
                 "Back right", "Back left", "Front centre", "Back centre",
                 "Subwoofer"]
    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

    def __eq__(self, other):
        return ((str(self) == other) or
                (self.desc == other.desc and
                 self.channel == other.channel and
                 self.gain == other.gain and
                 self.peak == other.peak))

    __hash__ = Frame.__hash__

    def __str__(self):
        return "{}: {:+0.4f} dB/{:0.4f}".format(self._channels[self.channel],
                                                self.gain, self.peak)

class EQU2(Frame):
    """Equalisation (2).

    Attributes:
    method -- interpolation method (0 = band, 1 = linear)
    desc -- identifying description
    adjustments -- list of (frequency, vol_adjustment) pairs
    """
    _framespec = [ ByteSpec("method"), Latin1TextSpec("desc"),
                   VolumeAdjustmentsSpec("adjustments") ]

    def __eq__(self, other):
        return self.adjustments == other

    __hash__ = Frame.__hash__

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

# class RVAD: unsupported
# class EQUA: unsupported

class RVRB(Frame):
    """Reverb."""
    _framespec = [ SizedIntegerSpec('left', 2), SizedIntegerSpec('right', 2),
                   ByteSpec('bounce_left'), ByteSpec('bounce_right'),
                   ByteSpec('feedback_ltl'), ByteSpec('feedback_ltr'),
                   ByteSpec('feedback_rtr'), ByteSpec('feedback_rtl'),
                   ByteSpec('premix_ltr'), ByteSpec('premix_rtl') ]

    def __eq__(self, other):
        return (self.left, self.right) == other

    __hash__ = Frame.__hash__

class APIC(Frame):
    """Attached (or linked) Picture.

    Attributes:
    encoding -- text encoding for the description
    mime -- a MIME type (e.g. image/jpeg) or '-->' if the data is a URI
    type -- the source of the image (3 is the album front cover)
    desc -- a text description of the image
    data -- raw image data, as a byte string

    Mutagen will automatically compress large images when saving tags.
    """
    _framespec = [ EncodingSpec('encoding'), Latin1TextSpec('mime'),
        ByteSpec('type'), EncodedTextSpec('desc'), BinaryDataSpec('data') ]

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

    def _pprint(self):
        return "{} ({}, {} bytes)".format(self.desc, self.mime, len(self.data))


class PCNT(Frame):
    """Play counter.

    The 'count' attribute contains the (recorded) number of times this
    file has been played.

    This frame is basically obsoleted by POPM.
    """
    _framespec = [ IntegerSpec('count') ]

    def __eq__(self, other):
        return self.count == other

    __hash__ = Frame.__hash__

    def __pos__(self):
        return self.count

    def _pprint(self):
        return str(self.count)

class POPM(FrameOpt):
    """Popularimeter.

    This frame keys a rating (out of 255) and a play count to an email
    address.

    Attributes:
    email -- email this POPM frame is for
    rating -- rating from 0 to 255
    count -- number of times the files has been played (optional)
    """
    _framespec = [ Latin1TextSpec('email'), ByteSpec('rating') ]
    _optionalspec = [ IntegerSpec('count') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.email))

    def __eq__(self, other):
        return self.rating == other

    __hash__ = FrameOpt.__hash__

    def __pos__(self):
        return self.rating

    def _pprint(self):
        return "{}={} {}/255".format(self.email,
               repr(getattr(self, 'count', None)), repr(self.rating))

class GEOB(Frame):
    """General Encapsulated Object.

    A blob of binary data, that is not a picture (those go in APIC).

    Attributes:
    encoding -- encoding of the description
    mime -- MIME type of the data or '-->' if the data is a URI
    filename -- suggested filename if extracted
    desc -- text description of the data
    data -- raw data, as a byte string
    """
    _framespec = [ EncodingSpec('encoding'), Latin1TextSpec('mime'),
        EncodedTextSpec('filename'), EncodedTextSpec('desc'),
        BinaryDataSpec('data') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.desc))

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

class RBUF(FrameOpt):
    """Recommended buffer size.

    Attributes:
    size -- recommended buffer size in bytes
    info -- if ID3 tags may be elsewhere in the file (optional)
    offset -- the location of the next ID3 tag, if any

    Mutagen will not find the next tag itself.
    """
    _framespec = [ SizedIntegerSpec('size', 3) ]
    _optionalspec = [ ByteSpec('info'), SizedIntegerSpec('offset', 4) ]

    def __eq__(self, other):
        return self.size == other

    __hash__ = FrameOpt.__hash__

    def __pos__(self):
        return self.size

class AENC(FrameOpt):
    """Audio encryption.

    Attributes:
    owner -- key identifying this encryption type
    preview_start -- unencrypted data block offset
    preview_length -- number of unencrypted blocks
    data -- data required for decryption (optional)

    Mutagen cannot decrypt files.
    """
    _framespec = [ Latin1TextSpec('owner'),
                   SizedIntegerSpec('preview_start', 2),
                   SizedIntegerSpec('preview_length', 2) ]
    _optionalspec = [ BinaryDataSpec('data') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.owner))

    def __str__(self):
        return self.owner

    def __eq__(self, other):
        return self.owner == other
    __hash__ = FrameOpt.__hash__

class LINK(FrameOpt):
    """Linked information.

    Attributes:
    frameid -- the ID of the linked frame
    url -- the location of the linked frame
    data -- further ID information for the frame
    """

    _framespec = [ ASCIIStringSpec('frameid', 4), Latin1TextSpec('url') ]
    _optionalspec = [ BinaryDataSpec('data') ]

    def __HashKey(self):
        try:
            return "{}:{}:{}:{}".format(
                self.FrameID, self.frameid, self.url, repr(self.data))
        except AttributeError:
            return "{}:{}:{}".format(self.FrameID, self.frameid, self.url)

    HashKey = property(__HashKey)

    def __eq__(self, other):
        try:
            return (self.frameid, self.url, self.data) == other
        except AttributeError:
            return (self.frameid, self.url) == other

    __hash__ = FrameOpt.__hash__

class POSS(Frame):
    """Position synchronisation frame

    Attribute:
    format -- format of the position attribute (frames or milliseconds)
    position -- current position of the file
    """
    _framespec = [ ByteSpec('format'), IntegerSpec('position') ]

    def __pos__(self):
        return self.position

    def __eq__(self, other):
        return self.position == other

    __hash__ = Frame.__hash__

class UFID(Frame):
    """Unique file identifier.

    Attributes:
    owner -- format/type of identifier
    data -- identifier
    """

    _framespec = [ Latin1TextSpec('owner'), BinaryDataSpec('data') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.owner))

    def __eq__(s, o):
        if isinstance(o, UFI):
            return s.owner == o.owner and s.data == o.data
        else:
            return s.data == o

    __hash__ = Frame.__hash__

    def _pprint(self):
        isascii = max(self.data) < 128
        if isascii:
            return "{}={}".format(self.owner, self.data)
        else:
            return "{} ({} bytes)".format(self.owner, len(self.data))

class USER(Frame):
    """Terms of use.

    Attributes:
    encoding -- text encoding
    lang -- ISO three letter language code
    text -- licensing terms for the audio
    """
    _framespec = [ EncodingSpec('encoding'), ASCIIStringSpec('lang', 3),
        EncodedTextSpec('text') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, repr(s.lang)))

    def __str__(self):
        return self.text

    def __eq__(self, other):
        return self.text == other

    __hash__ = Frame.__hash__

    def _pprint(self):
        return "{}={}".format(repr(self.lang), self.text)

class OWNE(Frame):
    """Ownership frame."""
    _framespec = [ EncodingSpec('encoding'), Latin1TextSpec('price'),
                   ASCIIStringSpec('date', 8), EncodedTextSpec('seller') ]

    def __str__(self):
        return self.seller

    def __eq__(self, other):
        return self.seller == other

    __hash__ = Frame.__hash__

class COMR(FrameOpt):
    """Commercial frame."""
    _framespec = [ EncodingSpec('encoding'), Latin1TextSpec('price'),
                   ASCIIStringSpec('valid_until', 8), Latin1TextSpec('contact'),
                   ByteSpec('format'), EncodedTextSpec('seller'),
                   EncodedTextSpec('desc')]

    _optionalspec = [ Latin1TextSpec('mime'), BinaryDataSpec('logo') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s._writeData()))

    def __eq__(self, other):
        return self._writeData() == other._writeData()

    __hash__ = FrameOpt.__hash__

class ENCR(Frame):
    """Encryption method registration.

    The standard does not allow multiple ENCR frames with the same owner
    or the same method. Mutagen only verifies that the owner is unique.
    """
    _framespec = [ Latin1TextSpec('owner'), ByteSpec('method'),
                   BinaryDataSpec('data') ]

    HashKey = property(lambda s: "{}:{}".format(s.FrameID, s.owner))

    def __str__(self):
        return self.data

    def __eq__(self, other):
        return self.data == other

    __hash__ = Frame.__hash__

class GRID(FrameOpt):
    """Group identification registration."""
    _framespec = [ Latin1TextSpec('owner'), ByteSpec('group') ]

    _optionalspec = [ BinaryDataSpec('data') ]

    HashKey = property(lambda s: '{}:{}'.format(s.FrameID, s.group))

    def __pos__(self):
        return self.group

    def __str__(self):
        return self.owner

    def __eq__(self, other):
        return self.owner == other or self.group == other

    __hash__ = FrameOpt.__hash__


class PRIV(Frame):
    """Private frame."""
    _framespec = [ Latin1TextSpec('owner'), BinaryDataSpec('data') ]
    HashKey = property(lambda s: '{}:{}:{}'.format(
        s.FrameID, s.owner, s.data.decode('latin1')))

    def __str__(self):
        return self.data

    def __eq__(self, other):
        return self.data == other

    def _pprint(self):
        isascii = max(self.data) < 128
        if isascii:
            return "{}={}".format(self.owner, self.data)
        else:
            return "{} ({} bytes)".format(self.owner, len(self.data))

    __hash__ = Frame.__hash__

class SIGN(Frame):
    """Signature frame."""
    _framespec = [ ByteSpec('group'), BinaryDataSpec('sig') ]
    HashKey = property(lambda s: '{}:{:c}:{}'.format(s.FrameID, s.group, s.sig))

    def __str__(self):
        return self.sig

    def __eq__(self, other):
        return self.sig == other
    __hash__ = Frame.__hash__

class SEEK(Frame):
    """Seek frame.

    Mutagen does not find tags at seek offsets.
    """
    _framespec = [ IntegerSpec('offset') ]

    def __pos__(self):
        return self.offset

    def __eq__(self, other):
        return self.offset == other

    __hash__ = Frame.__hash__

class ASPI(Frame):
    """Audio seek point index.

    Attributes: S, L, N, b, and Fi. For the meaning of these, see
    the ID3v2.4 specification. Fi is a list of integers.
    """
    _framespec = [ SizedIntegerSpec("S", 4), SizedIntegerSpec("L", 4),
                   SizedIntegerSpec("N", 2), ByteSpec("b"),
                   ASPIIndexSpec("Fi") ]

    def __eq__(self, other):
        return self.Fi == other

    __hash__ = Frame.__hash__

Frames = dict([(k,v) for (k,v) in globals().items()
        if len(k)==4 and isinstance(v, type) and issubclass(v, Frame)])