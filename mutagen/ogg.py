# -*- coding: utf-8 -*-

# Copyright 2006 Joe Wreschnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# $Id: ogg.py 3975 2007-01-13 21:51:17Z piman $
#
# Modified for Python 3 by Ben Ockmore <ben.sput@gmail.com>

"""Read and write Ogg bitstreams and pages.

This module reads and writes a subset of the Ogg bitstream format
version 0. It does *not* read or write Ogg Vorbis files! For that,
you should use mutagen.oggvorbis.

This implementation is based on the RFC 3533 standard found at
http://www.xiph.org/ogg/doc/rfc3533.txt.
"""

import struct
import sys
import zlib
import io

class error(IOError):
    """Ogg stream parsing errors."""
    pass

class OggPage(object):
    """A single Ogg page (not necessarily a single encoded packet).

    A page is a header of 26 bytes, followed by the length of the
    data, followed by the data.

    The constructor is givin a file-like object pointing to the start
    of an Ogg page. After the constructor is finished it is pointing
    to the start of the next page.

    Attributes:
    version -- stream structure version (currently always 0)
    position -- absolute stream position (default -1)
    serial -- logical stream serial number (default 0)
    sequence -- page sequence number within logical stream (default 0)
    offset -- offset this page was read from (default None)
    complete -- if the last packet on this page is complete (default True)
    packets -- list of raw packet data (default [])

    Note that if 'complete' is false, the next page's 'continued'
    property must be true (so set both when constructing pages).

    If a file-like object is supplied to the constructor, the above
    attributes will be filled in based on it.
    """

    def __init__(self, fileobj=None):
        self.__type_flags = 0
        self.version = 0
        self.position = 0L
        self.serial = 0
        self.sequence = 0
        self.offset = None
        self.complete = True
        self.packets = []

        if fileobj is None:
            return

        self.offset = fileobj.tell()

        header = fileobj.read(27)
        if len(header) == 0:
            raise EOFError

        try:
            (oggs, self.version, self.__type_flags, self.position, self.serial,
             self.sequence, crc, segments) = \
                struct.unpack("<4sBBqIIiB", header)
        except struct.error:
            raise error("unable to read full header; got {}".format(header))

        if oggs != b"OggS":
            raise error("read {}, expected {}, at {#x}".format(
                repr(oggs), repr(b"OggS"), fileobj.tell() - 27))

        if self.version != 0:
            raise error("version {} unsupported".format(self.version)

        total = 0
        lacings = []
        lacing_bytes = fileobj.read(segments)

        if len(lacing_bytes) != segments:
            raise error("unable to read {} lacing bytes".format(segments))

        for c in lacing_bytes:
            total += c
            if c < 255:
                lacings.append(total)
                total = 0
        if total:
            lacings.append(total)
            self.complete = False

        self.packets = [fileobj.read(l) for l in lacings]
        if [len(p) for p in self.packets] != lacings:
            raise error("unable to read full data")

    def __eq__(self, other):
        """Two Ogg pages are the same if they write the same data."""
        try:
            return (self.write() == other.write())
        except AttributeError:
            return False

    __hash__ = object.__hash__

    def __repr__(self):
        attrs = ['version', 'position', 'serial', 'sequence', 'offset',
                 'complete', 'continued', 'first', 'last']
        values = ["{}={}".format(attr, repr(getattr(self, attr)))
                  for attr in attrs]
        return "<{} {}, {} bytes in {} packets>".format(
            type(self).__name__, " ".join(values),
            sum(len(p) for p in self.packets), len(self.packets))

    def write(self):
        """Return a string encoding of the page header and data.

        A ValueError is raised if the data is too big to fit in a
        single page.
        """

        data = [
            struct.pack("<4sBBqIIi", b"OggS", self.version, self.__type_flags,
                        self.position, self.serial, self.sequence, 0)
            ]

        lacing_data = []
        for datum in self.packets:
            quot, rem = divmod(len(datum), 255)
            lacing_data.append(b"\xff" * quot + bytes([rem]))
        lacing_data = b"".join(lacing_data)
        if not self.complete and lacing_data.endswith("\x00"):
            lacing_data = lacing_data[:-1]
        data.append(bytes([len(lacing_data)]))
        data.append(lacing_data)
        data.extend(self.packets)
        data = b"".join(data)

        # Python's CRC is swapped relative to Ogg's needs.
        # crc32 returns uint prior to py2.6 on some platforms, so force uint
        crc = (~zlib.crc32(data.translate(cdata.bitswap), -1)) & 0xffffffff
        # Although we're using to_uint_be, this actually makes the CRC
        # a proper le integer, since Python's CRC is byteswapped.
        crc = cdata.to_uint_be(crc).translate(cdata.bitswap)
        data = data[:22] + crc + data[26:]
        return data

    def __size(self):
        size = 27 # Initial header size
        for datum in self.packets:
            quot, rem = divmod(len(datum), 255)
            size += quot + 1
        if not self.complete and rem == 0:
            # Packet contains a multiple of 255 bytes and is not
            # terminated, so we don't have a \x00 at the end.
            size -= 1
        size += sum(len(p) for p in self.packets)
        return size

    size = property(__size, doc="Total frame size.")

    def __set_flag(self, bit, val):
        mask = 1 << bit
        if val:
            self.__type_flags |= mask
        else:
            self.__type_flags &= ~mask

    continued = property(
        lambda self:
            cdata.test_bit(self.__type_flags, 0),
        lambda self, v:
            self.__set_flag(0, v),
        doc="The first packet is continued from the previous page.")

    first = property(
        lambda self:
            cdata.test_bit(self.__type_flags, 1),
        lambda self, v:
            self.__set_flag(1, v),
        doc="This is the first page of a logical bitstream.")

    last = property(
        lambda self:
            cdata.test_bit(self.__type_flags, 2),
        lambda self, v:
            self.__set_flag(2, v),
        doc="This is the last page of a logical bitstream.")

    @staticmethod
    def renumber(fileobj, serial, start):
        """Renumber pages belonging to a specified logical stream.

        fileobj must be opened with mode r+b or w+b.

        Starting at page number 'start', renumber all pages belonging
        to logical stream 'serial'. Other pages will be ignored.

        fileobj must point to the start of a valid Ogg page; any
        occuring after it and part of the specified logical stream
        will be numbered. No adjustment will be made to the data in
        the pages nor the granule position; only the page number, and
        so also the CRC.

        If an error occurs (e.g. non-Ogg data is found), fileobj will
        be left pointing to the place in the stream the error occured,
        but the invalid data will be left intact (since this function
        does not change the total file size).
        """

        number = start
        while True:
            try:
                page = OggPage(fileobj)
            except EOFError:
                break
            else:
                if page.serial != serial:
                    # Wrong stream, skip this page.
                    continue
                # Changing the number can't change the page size,
                # so seeking back based on the current size is safe.
                fileobj.seek(-page.size, 1)
            page.sequence = number
            fileobj.write(page.write())
            fileobj.seek(page.offset + page.size, 0)
            number += 1

    @staticmethod
    def to_packets(pages, strict=False):
        """Construct a list of packet data from a list of Ogg pages.

        If strict is true, the first page must start a new packet,
        and the last page must end the last packet.
        """

        serial = pages[0].serial
        sequence = pages[0].sequence
        packets = []

        if strict:
            if pages[0].continued:
                raise ValueError("first packet is continued")
            if not pages[-1].complete:
                raise ValueError("last packet does not complete")
        elif pages and pages[0].continued:
            packets.append(b"")

        for page in pages:
            if serial != page.serial:
                raise ValueError("invalid serial "
                                 "number in {}".format(repr(page)))
            elif sequence != page.sequence:
                raise ValueError("bad sequence "
                                 "number in {}".format(repr(page)))
            else:
                sequence += 1

            if page.continued:
                packets[-1] += page.packets[0]
            else:
                packets.append(page.packets[0])
            packets.extend(page.packets[1:])

        return packets

        @staticmethod
        def from_packets(packets, sequence=0, default_size=4096,
                         wiggle_room=2048):
        """Construct a list of Ogg pages from a list of packet data.

        The algorithm will generate pages of approximately
        default_size in size (rounded down to the nearest multiple of
        255). However, it will also allow pages to increase to
        approximately default_size + wiggle_room if allowing the
        wiggle room would finish a packet (only one packet will be
        finished in this way per page; if the next packet would fit
        into the wiggle room, it still starts on a new page).

        This method reduces packet fragmentation when packet sizes are
        slightly larger than the default page size, while still
        ensuring most pages are of the average size.

        Pages are numbered started at 'sequence'; other information is
        uninitialized.
        """

        chunk_size = (default_size // 255) * 255

        pages = []

        page = OggPage()
        page.sequence = sequence

        for packet in packets:
            page.packets.append(b"")
            while packet:
                data, packet = packet[:chunk_size], packet[chunk_size:]
                if page.size < default_size and len(page.packets) < 255:
                    page.packets[-1] += data
                else:
                    # If we've put any packet data into this page yet,
                    # we need to mark it incomplete. However, we can
                    # also have just started this packet on an already
                    # full page, in which case, just start the new
                    # page with this packet.
                    if page.packets[-1]:
                        page.complete = False
                        if len(page.packets) == 1:
                            page.position = -1L
                    else:
                        page.packets.pop(-1)
                    pages.append(page)
                    page = OggPage()
                    page.continued = not pages[-1].complete
                    page.sequence = pages[-1].sequence + 1
                    page.packets.append(data)

                if len(packet) < wiggle_room:
                    page.packets[-1] += packet
                    packet = b""

        if page.packets:
            pages.append(page)

        return pages

    @classmethod
    def replace(cls, fileobj, old_pages, new_pages):
        """Replace old_pages with new_pages within fileobj.

        old_pages must have come from reading fileobj originally.
        new_pages are assumed to have the 'same' data as old_pages,
        and so the serial and sequence numbers will be copied, as will
        the flags for the first and last pages.

        fileobj will be resized and pages renumbered as necessary. As
        such, it must be opened r+b or w+b.
        """

        # Number the new pages starting from the first old page.
        first = old_pages[0].sequence
        for page, seq in zip(new_pages, range(first, first + len(new_pages))):
            page.sequence = seq
            page.serial = old_pages[0].serial

        new_pages[0].first = old_pages[0].first
        new_pages[0].last = old_pages[0].last
        new_pages[0].continued = old_pages[0].continued

        new_pages[-1].first = old_pages[-1].first
        new_pages[-1].last = old_pages[-1].last
        new_pages[-1].complete = old_pages[-1].complete
        if not new_pages[-1].complete and len(new_pages[-1].packets) == 1:
            new_pages[-1].position = -1L

        new_data = b"".join(cls.write(p) for p in new_pages)

        # Make room in the file for the new data.
        delta = len(new_data)
        fileobj.seek(old_pages[0].offset, 0)
        insert_bytes(fileobj, delta, old_pages[0].offset)
        fileobj.seek(old_pages[0].offset, 0)
        fileobj.write(new_data)
        new_data_end = old_pages[0].offset + delta

        # Go through the old pages and delete them. Since we shifted
        # the data down the file, we need to adjust their offsets. We
        # also need to go backwards, so we don't adjust the deltas of
        # the other pages.
        old_pages.reverse()
        for old_page in old_pages:
            adj_offset = old_page.offset + delta
            delete_bytes(fileobj, old_page.size, adj_offset)

        # Finally, if there's any discrepency in length, we need to
        # renumber the pages for the logical stream.
        if len(old_pages) != len(new_pages):
            fileobj.seek(new_data_end, 0)
            serial = new_pages[-1].serial
            sequence = new_pages[-1].sequence + 1
            cls.renumber(fileobj, serial, sequence)

    @staticmethod
    def find_last(fileobj, serial):
        """Find the last page of the stream 'serial'.

        If the file is not multiplexed this function is fast. If it is,
        it must read the whole the stream.

        This finds the last page in the actual file object, or the last
        page in the stream (with eos set), whichever comes first.
        """

        # For non-muxed streams, look at the last page.
        try:
            fileobj.seek(-256*256, 2)
        except IOError:
            # The file is less than 64k in length.
            fileobj.seek(0)
        data = fileobj.read()
        try:
            index = data.rindex(b"OggS")
        except ValueError:
            raise error("unable to find final Ogg header")
        bytesobj = io.BytesIO(data[index:])
        best_page = None
        try:
            page = OggPage(bytesobj)
        except error:
            pass
        else:
            if page.serial == serial:
                if page.last:
                    return page
                else:
                    best_page = page
            else:
                best_page = None

        # The stream is muxed, so use the slow way.
        fileobj.seek(0)
        try:
            page = OggPage(fileobj)
            while not page.last:
                page = OggPage(fileobj)
                while page.serial != serial:
                    page = OggPage(fileobj)
                best_page = page
            return page
        except error:
            return best_page
        except EOFError:
            return best_page

class OggFileType(FileType):
    """An generic Ogg file."""

    _Info = None
    _Tags = None
    _Error = None
    _mimes = ["application/ogg", "application/x-ogg"]

    def load(self, filename):
        """Load file information from a filename."""

        self.filename = filename
        fileobj = open(filename, "rb")
        try:
            try:
                self.info = self._Info(fileobj)
                self.tags = self._Tags(fileobj, self.info)
                self.info._post_tags(fileobj)
            except error as e:
                raise self._Error(e).with_traceback(sys.exc_info()[2])
            except EOFError:
                raise self._Error("no appropriate stream found")
        finally:
            fileobj.close()

    def delete(self, filename=None):
        """Remove tags from a file.

        If no filename is given, the one most recently loaded is used.
        """
        if filename is None:
            filename = self.filename

        self.tags.clear()
        fileobj = open(filename, "rb+")
        try:
            try:
                self.tags._inject(fileobj)
            except error as e:
                raise self._Error(e).with_traceback(sys.exc_info()[2])
            except EOFError:
                raise self._Error("no appropriate stream found")
        finally:
            fileobj.close()

    def save(self, filename=None):
        """Save a tag to a file.

        If no filename is given, the one most recently loaded is used.
        """
        if filename is None:
            filename = self.filename

        fileobj = open(filename, "rb+")
        try:
            try:
                self.tags._inject(fileobj)
            except error as e:
                raise self._Error(e).with_traceback(sys.exc_info()[2])
            except EOFError:
                raise self._Error("no appropriate stream found")
        finally:
            fileobj.close()
