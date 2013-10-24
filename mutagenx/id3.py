# -*- coding: utf-8 -*-

# Copyright (C) 2005  Michael Urman
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# $Id: id3.py 4285 2008-09-06 08:01:31Z piman $
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

import os.path
import struct
import sys
import re
import zlib
import functools

import mutagenx
from mutagenx._util import insert_bytes, delete_bytes, DictProxy
from warnings import warn

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

class ID3(DictProxy, mutagenx.Metadata):

    filename = None
    PEDANTIC = True

    def __init__(self, *args, **kwargs):
        self.unknown_frames = list()

        self.version = (2, 4, 0)
        self.__readbytes = 0
        self.__flags = 0
        self.__unknown_updated = False

        # Initialize the metadata base class with any input arguments.
        super(ID3, self).__init__(*args, **kwargs)

    # Read size bytes of the file. Returns raw bytes.
    def __fullread(self, size):
        """ Read a certain number of bytes from the source file. """
        try:
            if size < 0:
                raise ValueError("Requested bytes ({}) less than "
                                 "zero".format(size))
            if size > self.__filesize:
                raise EOFError("Requested {:#x} of {:#x} {}".format(int(size),
                               int(self.__filesize), self.filename))
        except AttributeError:
            pass

        #Read binary data (bytes)
        data = self.__fileobj.read(size)
        if len(data) != size:
            raise EOFError("Read: {:d} Requested: {:d}".format(len(data),size))

        self.__readbytes += size
        return data

    def load(self, filename, known_frames=None, translate=True):
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
                for frame in self.__read_frames(data, frames=frames):
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
            raise ID3NoHeaderError("'{}' doesn't start with an "
                                   "ID3 tag".format(fn))
        if vmaj not in {2, 3, 4}:
            raise ID3UnsupportedVersionError("'{}' ID3v2.{} "
                                             "not supported".format(fn, vmaj))

        if self.PEDANTIC:
            if ((2, 4, 0) <= self.version) and (flags & 0x0f):
                raise ValueError("'{}' has invalid "
                                 "flags {:#02x}".format(fn, flags))
            elif ((2, 3, 0) <= self.version < (2, 4, 0)) and (flags & 0x1f):
                raise ValueError("'{}' has invalid "
                                 "flags {:#02x}".format(fn, flags))

        if self.f_extended:
            extsize = self.__fullread(4)

            if extsize.decode('ascii') in Frames:
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

                name = name.decode('latin1')

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
                    name, size = struct.unpack('>3s3s', header)
                except struct.error:
                    return  # not enough header

                size = struct.unpack('>L', b'\x00' + size)[0]

                if name.strip(b'\x00') == b'':
                    return

                name = name.decode('latin1')

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
            return [v for s, v in self.items() if s.startswith(key)]

    def delall(self, key):
        """Delete all tags of a given kind; see getall."""
        if key in self:
            del(self[key])
        else:
            key = key + ":"
            for k in [s for s in self.keys() if s.startswith(key)]:
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

    def save(self, filename=None, v1=1):
        """Save changes to a file.

        If no filename is given, the one most recently loaded is used.

        Keyword arguments:
        v1 -- if 0, ID3v1 tags will be removed
              if 1, ID3v1 tags will be updated but not added
              if 2, ID3v1 tags will be created and/or updated

        The lack of a way to update only an ID3v1 tag is intentional.
        """

        # Sort frames by 'importance'
        order = ["TIT2", "TPE1", "TRCK", "TALB", "TPOS", "TDRC", "TCON"]

        order = {b: a for a, b in enumerate(order)}
        last = len(order)
        frames = sorted(self.items(), key=lambda a: order.get(a[0][:4], last))

        f_data = [self.__save_frame(frame) for (key, frame) in frames]
        f_data.extend(data for data in self.unknown_frames if len(data) > 10)
        if not f_data:
            try:
                self.delete(filename)
            except EnvironmentError as err:
                from errno import ENOENT
                if err.errno != ENOENT:
                    raise
            return

        f_data = b''.join(f_data)
        framesize = len(f_data)

        if filename is None:
            filename = self.filename
        try:
            f = open(filename, 'rb+')
        except IOError as err:
            from errno import ENOENT
            if err.errno != ENOENT:
                raise
            f = open(filename, 'ab')  # create, then reopen
            f = open(filename, 'rb+')
        try:
            idata = f.read(10)
            try:
                id3, vmaj, vrev, flags, insize = struct.unpack('>3sBBB4s',
                                                               idata)
            except struct.error:
                id3, insize = b'', 0

            insize = BitPaddedInt(insize)
            if id3 != b'ID3':
                insize = -10

            if insize >= framesize:
                outsize = insize
            else:
                outsize = (framesize + 1023) & ~0x3FF
            f_data += b'\x00' * (outsize - framesize)

            framesize = BitPaddedInt.to_bytes(outsize, width=4)
            flags = 0
            header = struct.pack('>3sBBB4s', b'ID3', 4, 0, flags, framesize)
            data = header + f_data

            if (insize < outsize):
                insert_bytes(f, outsize - insize, insize + 10)

            f.seek(0)
            f.write(data)

            try:
                f.seek(-128, 2)
            except IOError as err:
                # If the file is too small, that's OK - it just means
                # we're certain it doesn't have a v1 tag.
                from errno import EINVAL
                if err.errno != EINVAL:
                    # If we failed to see for some other reason, bail out.
                    raise
                # Since we're sure this isn't a v1 tag, don't read it.
                f.seek(0, 2)

            data = f.read(128)
            try:
                idx = data.index(b"TAG")
            except ValueError:
                offset = 0
                has_v1 = False
            else:
                offset = idx - len(data)
                has_v1 = True

            f.seek(offset, 2)
            if v1 == 1 and has_v1 or v1 == 2:
                f.write(MakeID3v1(self))
            else:
                f.truncate()

        finally:
            f.close()

    def delete(self, filename=None, delete_v1=True, delete_v2=True):
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

    def __save_frame(self, frame, name=None):
        flags = 0
        if self.PEDANTIC and isinstance(frame, TextFrame):
            if len(str(frame)) == 0:
                return b''

        framedata = frame._writeData()
        usize = len(framedata)

        if usize > 2048:
            # Disabled as this causes iTunes and other programs
            # to fail to find these frames, which usually includes
            # e.g. APIC.
            #framedata = BitPaddedInt.to_str(usize) + framedata.encode('zlib')
            #flags |= Frame.FLAG24_COMPRESS | Frame.FLAG24_DATALEN
            pass

        datasize = BitPaddedInt.to_bytes(len(framedata), width=4)
        header = struct.pack('>4s4sH',
                             (name or type(frame).__name__).encode('ascii'),
                             datasize, flags)
        return header + framedata

    def normalize_for_v24(self):
        """Convert older tags into an ID3v2.4 tag.

        This updates old ID3v2 frames to ID3v2.4 ones (e.g. TYER to
        TDRC). If you intend to save tags, you must call this function
        at some point; it is called by default when loading the tag.
        """

        if self.version < (2, 3, 0):
            # unsafe to write
            del self.unknown_frames[:]
        elif self.version == (2, 3, 0) and not self.__unknown_updated:
            # convert unknown 2.3 frames (flags/size) to 2.4
            converted = []
            for frame in self.unknown_frames:
                try:
                    name, size, flags = struct.unpack('>4sLH', frame[:10])
                    frame = BinaryFrame.fromData(self, flags, frame[10:])
                except (struct.error, error):
                    continue
                name = name.decode('ascii')
                converted.append(self.__save_frame(frame, name=name))
            self.unknown_frames[:] = converted
            self.__unknown_updated = True

        # TDAT, TYER, and TIME have been turned into TDRC.
        try:
            if str(self.get("TYER", "")):
                date = str(self.pop("TYER"))
                if str(self.get("TDAT", "")):
                    dat = str(self.pop("TDAT"))
                    date = "{}-{}-{}".format(date, dat[2:], dat[:2])
                    if str(self.get("TIME", "")):
                        time = str(self.pop("TIME"))
                        date += "T{}:{}:00".format(time[:2], time[2:])
                if "TDRC" not in self:
                    self.add(TDRC(encoding=0, text=date))
        except UnicodeDecodeError:
            # Old ID3 tags have *lots* of Unicode problems, so if TYER
            # is bad, just chuck the frames.
            pass

        # TORY can be the first part of a TDOR.
        if "TORY" in self:
            f = self.pop("TORY")
            if "TDOR" not in self:
                try:
                    self.add(TDOR(encoding=0, text=str(f)))
                except UnicodeDecodeError:
                    pass

        # IPLS is now TIPL.
        if "IPLS" in self:
            f = self.pop("IPLS")
            if "TIPL" not in self:
                self.add(TIPL(encoding=f.encoding, people=f.people))

        if "TCON" in self:
            # Get rid of "(xx)Foobr" format.
            self["TCON"].genres = self["TCON"].genres

        if self.version < (2, 3):
            # ID3v2.2 PIC frames are slightly different.
            pics = self.getall("APIC")
            mimes = {"PNG": "image/png", "JPG": "image/jpeg"}
            self.delall("APIC")
            for pic in pics:
                newpic = APIC(encoding=pic.encoding,
                              mime=mimes.get(pic.mime, pic.mime),
                              type=pic.type, desc=pic.desc, data=pic.data)
                self.add(newpic)

            # ID3v2.2 LNK frames are just way too different to upgrade.
            self.delall("LINK")

        # These can't be trivially translated to any ID3v2.4 tags, or
        # should have been removed already.
        for key in ["RVAD", "EQUA", "TRDA", "TSIZ", "TDAT", "TIME", "CRM"]:
            if key in self:
                del(self[key])

    update_to_v24 = normalize_for_v24

def delete(filename, delete_v1=True, delete_v2=True):
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
            if f.read(3) == b'TAG':
                f.seek(-128, 2)
                f.truncate()

    # technically an insize=0 tag is invalid, but we delete it anyway
    # (primarily because we used to write it)
    if delete_v2:
        f.seek(0, 0)
        idata = f.read(10)
        try:
            id3, vmaj, vrev, flags, insize = struct.unpack('>3sBBB4s', idata)
        except struct.error:
            id3, insize = b'', -1
        insize = BitPaddedInt(insize)

        if id3 == b'ID3' and insize >= 0:
            delete_bytes(f, insize + 10, 0)


# support open(filename) as interface
Open = ID3


# ID3v1.1 support.
def ParseID3v1(data):
    """Parse an ID3v1 tag, returning a list of ID3v2.4 frames."""

    try:
        data = data[data.index(b'TAG'):]
    except ValueError:
        return None
    if 128 < len(data) or len(data) < 124:
        return None

    # Issue #69 - Previous versions of Mutagen, when encountering
    # out-of-spec TDRC and TYER frames of less than four characters,
    # wrote only the characters available - e.g. "1" or "" - into the
    # year field. To parse those, reduce the size of the year field.
    # Amazingly, "0s" works as a struct format string.
    unpack_fmt = "3s30s30s30s{}s29sBB".format(len(data) - 124)

    try:
        tag, title, artist, album, year, comment, track, genre = \
            struct.unpack(unpack_fmt, data)
    except StructError:
        return None

    if tag != b"TAG":
        return None

    def fix(data):
        return data.split(b'\x00')[0].strip().decode('latin1')

    title, artist, album, year, comment = map(
        fix, [title, artist, album, year, comment])

    frames = {}
    if title:
        frames['TIT2'] = TIT2(encoding=0, text=title)
    if artist:
        frames['TPE1'] = TPE1(encoding=0, text=[artist])
    if album:
        frames['TALB'] = TALB(encoding=0, text=album)
    if year:
        frames['TDRC'] = TDRC(encoding=0, text=year)
    if comment:
        frames['COMM'] = COMM(encoding=0, lang='eng', desc="ID3v1 Comment",
                              text=comment)

    # Don't read a track number if it looks like the comment was
    # padded with spaces instead of nulls (thanks, WinAmp).
    if track and (track != 32 or data[-3] == 0):
        frames['TRCK'] = TRCK(encoding=0, text=str(track))

    if genre != 255:
        frames['TCON'] = TCON(encoding=0, text=str(genre))

    return frames

def MakeID3v1(id3):
    """Return an ID3v1.1 tag string from a dict of ID3v2.4 frames."""

    v1 = {}

    for v2id, name in {"TIT2": "title", "TPE1": "artist",
                       "TALB": "album"}.items():
        if v2id in id3:
            text = id3[v2id].text[0].encode('latin1', 'replace')[:30]
        else:
            text = b""

        v1[name] = text + (b'\x00' * (30 - len(text)))

    if "COMM" in id3:
        cmnt = id3["COMM"].text[0].encode('latin1', 'replace')[:28]
    else:
        cmnt = b""

    v1['comment'] = cmnt + (b'\x00' * (29 - len(cmnt)))

    if "TRCK" in id3:
        try:
            v1['track'] = bytes((+id3["TRCK"],))
        except ValueError:
            v1['track'] = b'\x00'
    else:
        v1['track'] = b'\x00'

    if 'TCON' in id3:
        try:
            genre = id3['TCON'].genres[0]
        except IndexError:
            pass
        else:
            if genre in TCON.GENRES:
                v1['genre'] = bytes((TCON.GENRES.index(genre),))

    if 'genre' not in v1:
        v1['genre'] = b"\xff"

    if 'TDRC' in id3:
        year = str(id3['TDRC']).encode('latin1', 'replace')
    elif "TYER" in id3:
        year = str(id3['TYER']).encode('latin1', 'replace')
    else:
        year = b""

    v1['year'] = (year + b'\x00\x00\x00\x00')[:4]

    return (b'TAG' + v1['title'] + v1['artist'] + v1['album'] + v1['year'] +
            v1['comment'] + v1['track'] + v1['genre'])


class ID3FileType(mutagenx.FileType):
    """An unknown type of file with ID3 tags."""

    ID3 = ID3

    class _Info(object):
        length = 0

        def __init__(self, fileobj, offset):
            pass

        pprint = staticmethod(lambda: "Unknown format with ID3 tag")

    @staticmethod
    def score(filename, fileobj, header_data):
        return header_data.startswith(b"ID3")

    def add_tags(self, ID3=None):
        """Add an empty ID3 tag to the file.

        A custom tag reader may be used in instead of the default
        mutagenx.id3.ID3 object, e.g. an EasyID3 reader.
        """
        if ID3 is None:
            ID3 = self.ID3
        if self.tags is None:
            self.ID3 = ID3
            self.tags = ID3()
        else:
            raise error("an ID3 tag already exists")

    def load(self, filename, ID3=None, **kwargs):
        """Load stream and tag information from a file.

        A custom tag reader may be used in instead of the default
        mutagenx.id3.ID3 object, e.g. an EasyID3 reader.
        """
        if ID3 is None:
            ID3 = self.ID3
        else:
            # If this was initialized with EasyID3, remember that for
            # when tags are auto-instantiated in add_tags.
            self.ID3 = ID3
        self.filename = filename
        try:
            self.tags = ID3(filename, **kwargs)
        except error:
            self.tags = None

        if self.tags is not None:
            try:
                offset = self.tags.size
            except AttributeError:
                offset = None
        else:
            offset = None

        try:
            fileobj = open(filename, "rb")
            self.info = self._Info(fileobj, offset)
        finally:
            fileobj.close()
