# -*- coding: utf-8 -*-

# Copyright 2005 Joe Wreschnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

__all__ = ["FLAC", "Open", "delete"]

from mutagen import FileType
from functools import reduce
import io

class error(IOError): pass
class FLACNoHeaderError(error): pass
class FLACVorbisError(ValueError, error): pass

def to_int_be(data):
    """Convert an arbitrarily-long string to a long using big-endian
    byte order."""
    return reduce(lambda a, b: (a << 8) + ord(b), data, 0)

class StrictFileObject(object):
    """Wraps a file-like object and raises an exception if the requested
    amount of data to read isn't returned."""

    def __init__(self, fileobj):
        self._fileobj = fileobj
        for m in ["close", "tell", "seek", "write", "name"]:
            if hasattr(fileobj, m):
                setattr(self, m, getattr(fileobj, m))

    def read(self, size=-1):
        data = self._fileobj.read(size)
        if size >= 0 and len(data) != size:
            raise error("file said {} bytes, read {} bytes".format(size, len(data)))
        return data

    def tryread(self, *args):
        return self._fileobj.read(*args)

class MetadataBlock(object):
    """A generic block of FLAC metadata.

    This class is extended by specific used as an ancestor for more specific
    blocks, and also as a container for data blobs of unknown blocks.

    Attributes:
    data -- raw binary data for this block
    """

    _distrust_size = False

    def __init__(self, data):
        """Parse the given data string or file-like as a metadata block.
        The metadata header should not be included."""
        if data is not None:
            if not isinstance(data, StrictFileObject):
                if isinstance(data, bytes):
                    data = io.BytesIO(data)
                elif not hasattr(data, 'read'):
                    raise TypeError(
                        "StreamInfo requires string data or a file-like")
                data = StrictFileObject(data)
            self.load(data)

    def load(self, data):
        self.data = data.read()

    def write(self):
        return self.data

    @staticmethod
    def writeblocks(blocks):
        """Render metadata block as a byte string."""
        data = []
        codes = [[block.code, block.write()] for block in blocks]
        codes[-1][0] |= 128
        for byte, datum in codes:
            if len(datum) > 2 ** 24:
                raise error("block is too long to write")
            length = struct.pack(">I", len(datum))[-3:]
            data.append(byte + length + datum)
        return bytes(data)

    @staticmethod
    def group_padding(blocks):
        """Consolidate FLAC padding metadata blocks.

        The overall size of the rendered blocks does not change, so
        this adds several bytes of padding for each merged block."""
        paddings = [b for b in block if isinstance(b, Padding)]

        for padding in paddings:
            blocks.remove(padding)

        padding = Padding()
        # total padding size is the sum of padding sizes plus 4 bytes
        # per removed header.
        size = sum(padding.length for padding in paddings)
        padding.length = size + 4 * (len(paddings) - 1)
        blocks.append(padding)


class StreamInfo(MetadataBlock):
    """FLAC stream information.

    This contains information about the audio data in the FLAC file.
    Unlike most stream information objects in Mutagen, changes to this
    one will rewritten to the file when it is saved. Unless you are
    actually changing the audio stream itself, don't change any
    attributes of this block.

    Attributes:
    min_blocksize -- minimum audio block size
    max_blocksize -- maximum audio block size
    sample_rate -- audio sample rate in Hz
    channels -- audio channels (1 for mono, 2 for stereo)
    bits_per_sample -- bits per sample
    total_samples -- total samples in file
    length -- audio length in seconds
    """

    code = 0

    def __eq__(self, other):
        try:
            return (self.min_blocksize == other.min_blocksize and
                    self.max_blocksize == other.max_blocksize and
                    self.sample_rate == other.sample_rate and
                    self.channels == other.channels and
                    self.bits_per_sample == other.bits_per_sample and
                    self.total_samples == other.total_samples)
        except:
            return False
    __hash__ = MetadataBlock.__hash__

    def load(self, data):
        self.min_blocksize = to_int_be(data.read(2))
        self.max_blocksize = to_int_be(data.read(2))
        self.min_framesize = to_int_be(data.read(3))
        self.max_framesize = to_int_be(data.read(3))
        # first 16 bits of sample rate
        sample_first = to_int_be(data.read(2))
        # last 4 bits of sample rate, 3 of channels, first 1 of bits/sample
        sample_channels_bps = to_int_be(data.read(1))
        # last 4 of bits/sample, 36 of total samples
        bps_total = to_int_be(data.read(5))

        sample_tail = sample_channels_bps >> 4
        self.sample_rate = (sample_first << 4) + sample_tail
        if not self.sample_rate:
            raise error("A sample rate value of 0 is invalid")
        self.channels = ((sample_channels_bps >> 1) & 7) + 1
        bps_tail = bps_total >> 36
        bps_head = (sample_channels_bps & 1) << 4
        self.bits_per_sample = bps_head + bps_tail + 1
        self.total_samples = bps_total & 0xFFFFFFFFF
        self.length = self.total_samples / self.sample_rate

        self.md5_signature = to_int_be(data.read(16))

    def write(self):
        f = StringIO()
        f.write(struct.pack(">I", self.min_blocksize)[-2:])
        f.write(struct.pack(">I", self.max_blocksize)[-2:])
        f.write(struct.pack(">I", self.min_framesize)[-3:])
        f.write(struct.pack(">I", self.max_framesize)[-3:])

        # first 16 bits of sample rate
        f.write(struct.pack(">I", self.sample_rate >> 4)[-2:])
        # 4 bits sample, 3 channel, 1 bps
        byte = (self.sample_rate & 0xF) << 4
        byte += ((self.channels - 1) & 7) << 1
        byte += ((self.bits_per_sample - 1) >> 4) & 1
        f.write(bytes([byte]))
        # 4 bits of bps, 4 of sample count
        byte = ((self.bits_per_sample - 1) & 0xF)  << 4
        byte += (self.total_samples >> 32) & 0xF
        f.write(bytes(byte))
        # last 32 of sample count
        f.write(struct.pack(">I", self.total_samples & 0xFFFFFFFF))
        # MD5 signature
        sig = self.md5_signature
        f.write(struct.pack(
            ">4I", (sig >> 96) & 0xFFFFFFFF, (sig >> 64) & 0xFFFFFFFF,
            (sig >> 32) & 0xFFFFFFFF, sig & 0xFFFFFFFF))
        return f.getvalue()

    def pprint(self):
        return "FLAC, {:.2f} seconds, {} Hz".format(self.length, self.sample_rate)

class SeekPoint(tuple):
    """A single seek point in a FLAC file.

    Placeholder seek points have first_sample of 0xFFFFFFFFFFFFFFFFL,
    and byte_offset and num_samples undefined. Seek points must be
    sorted in ascending order by first_sample number. Seek points must
    be unique by first_sample number, except for placeholder
    points. Placeholder points must occur last in the table and there
    may be any number of them.

    Attributes:
    first_sample -- sample number of first sample in the target frame
    byte_offset -- offset from first frame to target frame
    num_samples -- number of samples in target frame
    """

    def __new__(cls, first_sample, byte_offset, num_samples):
        return super(cls, SeekPoint).__new__(cls, (first_sample,
            byte_offset, num_samples))

    first_sample = property(lambda self: self[0])
    byte_offset = property(lambda self: self[1])
    num_samples = property(lambda self: self[2])

class SeekTable(MetadataBlock):
    """Read and write FLAC seek tables.

    Attributes:
    seekpoints -- list of SeekPoint objects
    """

    __SEEKPOINT_FORMAT = '>QQH'
    __SEEKPOINT_SIZE = struct.calcsize(__SEEKPOINT_FORMAT)

    code = 3

    def __init__(self, data):
        self.seekpoints = []
        super(SeekTable, self).__init__(data)

    def __eq__(self, other):
        try:
            return (self.seekpoints == other.seekpoints)
        except (AttributeError, TypeError):
            return False
    __hash__ = MetadataBlock.__hash__

    def load(self, data):
        self.seekpoints = []
        sp = data.tryread(self.__SEEKPOINT_SIZE)
        while len(sp) == self.__SEEKPOINT_SIZE:
            self.seekpoints.append(SeekPoint(
                *struct.unpack(self.__SEEKPOINT_FORMAT, sp)))
            sp = data.tryread(self.__SEEKPOINT_SIZE)

    def write(self):
        f = StringIO()
        for seekpoint in self.seekpoints:
            packed = struct.pack(self.__SEEKPOINT_FORMAT,
                seekpoint.first_sample, seekpoint.byte_offset,
                seekpoint.num_samples)
            f.write(packed)
        return f.getvalue()

    def __repr__(self):
        return "<{} seekpoints={}>".format(type(self).__name__, repr(self.seekpoints))

class VCFLACDict(VCommentDict):
    """Read and write FLAC Vorbis comments.

    FLACs don't use the framing bit at the end of the comment block.
    So this extends VCommentDict to not use the framing bit.
    """

    code = 4
    _distrust_size = True

    def load(self, data, errors='replace', framing=False):
        super(VCFLACDict, self).load(data, errors=errors, framing=framing)

    def write(self, framing=False):
        return super(VCFLACDict, self).write(framing=framing)

class CueSheetTrackIndex(tuple):
    """Index for a track in a cuesheet.

    For CD-DA, an index_number of 0 corresponds to the track
    pre-gap. The first index in a track must have a number of 0 or 1,
    and subsequently, index_numbers must increase by 1. Index_numbers
    must be unique within a track. And index_offset must be evenly
    divisible by 588 samples.

    Attributes:
    index_number -- index point number
    index_offset -- offset in samples from track start
    """

    def __new__(cls, index_number, index_offset):
        return super(cls, CueSheetTrackIndex).__new__(cls,
            (index_number, index_offset))

    index_number = property(lambda self: self[0])
    index_offset = property(lambda self: self[1])

class CueSheetTrack(object):
    """A track in a cuesheet.

    For CD-DA, track_numbers must be 1-99, or 170 for the
    lead-out. Track_numbers must be unique within a cue sheet. There
    must be atleast one index in every track except the lead-out track
    which must have none.

    Attributes:
    track_number -- track number
    start_offset -- track offset in samples from start of FLAC stream
    isrc -- ISRC code
    type -- 0 for audio, 1 for digital data
    pre_emphasis -- true if the track is recorded with pre-emphasis
    indexes -- list of CueSheetTrackIndex objects
    """

    def __init__(self, track_number, start_offset, isrc='', type_=0,
                 pre_emphasis=False):
        self.track_number = track_number
        self.start_offset = start_offset
        self.isrc = isrc
        self.type = type_
        self.pre_emphasis = pre_emphasis
        self.indexes = []

    def __eq__(self, other):
        try:
            return (self.track_number == other.track_number and
                    self.start_offset == other.start_offset and
                    self.isrc == other.isrc and
                    self.type == other.type and
                    self.pre_emphasis == other.pre_emphasis and
                    self.indexes == other.indexes)
        except (AttributeError, TypeError):
            return False
    __hash__ = object.__hash__

    def __repr__(self):
        return ("<{} number={}, offset={}, isrc={}, type={}, "
                "pre_emphasis={}, indexes={})>") % (
            type(self).__name__, repr(self.track_number), self.start_offset,
            repr(self.isrc), repr(self.type), repr(self.pre_emphasis), repr(self.indexes))

class CueSheet(MetadataBlock):
    """Read and write FLAC embedded cue sheets.

    Number of tracks should be from 1 to 100. There should always be
    exactly one lead-out track and that track must be the last track
    in the cue sheet.

    Attributes:
    media_catalog_number -- media catalog number in ASCII
    lead_in_samples -- number of lead-in samples
    compact_disc -- true if the cuesheet corresponds to a compact disc
    tracks -- list of CueSheetTrack objects
    lead_out -- lead-out as CueSheetTrack or None if lead-out was not found
    """

    __CUESHEET_FORMAT = '>128sQB258xB'
    __CUESHEET_SIZE = struct.calcsize(__CUESHEET_FORMAT)
    __CUESHEET_TRACK_FORMAT = '>QB12sB13xB'
    __CUESHEET_TRACK_SIZE = struct.calcsize(__CUESHEET_TRACK_FORMAT)
    __CUESHEET_TRACKINDEX_FORMAT = '>QB3x'
    __CUESHEET_TRACKINDEX_SIZE = struct.calcsize(__CUESHEET_TRACKINDEX_FORMAT)

    code = 5

    media_catalog_number = ''
    lead_in_samples = 88200
    compact_disc = True

    def __init__(self, data):
        self.tracks = []
        super(CueSheet, self).__init__(data)

    def __eq__(self, other):
        try:
            return (self.media_catalog_number == other.media_catalog_number and
                    self.lead_in_samples == other.lead_in_samples and
                    self.compact_disc == other.compact_disc and
                    self.tracks == other.tracks)
        except (AttributeError, TypeError):
            return False
    __hash__ = MetadataBlock.__hash__

    def load(self, data):
        header = data.read(self.__CUESHEET_SIZE)
        media_catalog_number, lead_in_samples, flags, num_tracks = \
            struct.unpack(self.__CUESHEET_FORMAT, header)
        self.media_catalog_number = media_catalog_number.rstrip(b'\0')
        self.lead_in_samples = lead_in_samples
        self.compact_disc = bool(flags & 0x80)
        self.tracks = []
        for i in range(num_tracks):
            track = data.read(self.__CUESHEET_TRACK_SIZE)
            start_offset, track_number, isrc_padded, flags, num_indexes = \
                struct.unpack(self.__CUESHEET_TRACK_FORMAT, track)
            isrc = isrc_padded.rstrip(b'\0')
            type_ = (flags & 0x80) >> 7
            pre_emphasis = bool(flags & 0x40)
            val = CueSheetTrack(
                track_number, start_offset, isrc, type_, pre_emphasis)
            for j in range(num_indexes):
                index = data.read(self.__CUESHEET_TRACKINDEX_SIZE)
                index_offset, index_number = struct.unpack(
                    self.__CUESHEET_TRACKINDEX_FORMAT, index)
                val.indexes.append(
                    CueSheetTrackIndex(index_number, index_offset))
            self.tracks.append(val)

    def write(self):
        f = BytesIO()
        flags = 0
        if self.compact_disc:
            flags |= 0x80

        packed = struct.pack(self.__CUESHEET_FORMAT, self.media_catalog_number,
                             self.lead_in_samples, flags, len(self.tracks))
        f.write(packed)
        for track in self.tracks:
            track_flags = 0
            track_flags |= (track.type & 1) << 7
            if track.pre_emphasis:
                track_flags |= 0x40
            track_packed = struct.pack(
                self.__CUESHEET_TRACK_FORMAT, track.start_offset,
                track.track_number, track.isrc, track_flags,
                len(track.indexes))
            f.write(track_packed)
            for index in track.indexes:
                index_packed = struct.pack(
                    self.__CUESHEET_TRACKINDEX_FORMAT,
                    index.index_offset, index.index_number)
                f.write(index_packed)
        return f.getvalue()

    def __repr__(self):
        return ("<{} media_catalog_number={}, lead_in={}, compact_disc={}, "
                "tracks={}>").format(
            type(self).__name__, repr(self.media_catalog_number),
            repr(self.lead_in_samples), repr(self.compact_disc), repr(self.tracks))
