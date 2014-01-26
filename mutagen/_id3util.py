# -*- coding: utf-8 -*-

# Copyright (C) 2005  Michael Urman
#               2013  Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.


class error(Exception):
    pass


class ID3NoHeaderError(error, ValueError):
    pass


class ID3BadUnsynchData(error, ValueError):
    pass


class ID3BadCompressedData(error, ValueError):
    pass


class ID3TagError(error, ValueError):
    pass


class ID3UnsupportedVersionError(error, NotImplementedError):
    pass


class ID3EncryptionUnsupportedError(error, NotImplementedError):
    pass


class ID3JunkFrameError(error, ValueError):
    pass


class ID3Warning(error, UserWarning):
    pass


# TODO Must be a better way to do this with bytearray?
class unsynch(object):
    @staticmethod
    def decode(value):
        fragments = [bytearray(x) for x in value.split(b'\xff')]
        if not fragments[-1]:
            raise ValueError('string ended unsafe')
                
        for f in (fragments[1:] if not fragments[0] else fragments):
            if (not f) or (f[0] >= b'\xE0'[0]):
                raise ValueError('invalid sync-safe string')
            
            if f[0] == b'\x00'[0]:
                del f[0]
        
        return b'\xff'.join(fragments)

    @staticmethod
    def encode(value):
        fragments = [bytearray(x) for x in value.split(b'\xff')]
                
        for f in (fragments[1:] if not fragments[0] else fragments):
            if (not f) or (f[0] >= b'\xE0'[0]) or (f[0] == b'\x00'[0]):
                f[0:0] = b'\x00'
            
        return b'\xff'.join(map(bytes, fragments))

class BitPaddedInt(int):
    def __new__(cls, value, bits=7, bigendian=True):
        "Strips 8-bits bits out of every byte"
        mask = (1 << (bits)) - 1
        if isinstance(value, int):
            reformed_bytes = []
            while value:
                reformed_bytes.append(value & ((1 << bits) - 1))
                value = value >> 8
        elif isinstance(value, bytes):
            reformed_bytes = [b & mask for b in value]
            if bigendian:
                reformed_bytes.reverse()
        else:
            raise TypeError

        numeric_value = 0
        for shift, byte in zip(range(0, len(reformed_bytes) * bits, bits),
                               reformed_bytes):
            numeric_value += byte << shift

        self = int.__new__(BitPaddedInt, numeric_value)
        self.bits = bits
        self.bigendian = bigendian
        return self

    @staticmethod
    def to_bytes(value, bits=7, bigendian=True, width=4, minwidth=4):
        bits = getattr(value, 'bits', bits)
        bigendian = getattr(value, 'bigendian', bigendian)
        value = int(value)
        mask = (1 << bits) - 1

        if width != -1:
            index = 0
            bytes_ = bytearray(width)
            try:
                while value:
                    bytes_[index] = value & mask
                    value >>= bits
                    index += 1
            except IndexError:
                raise ValueError('Value too wide (>%d bytes)' % width)
        else:
            # PCNT and POPM use growing integers
            # of at least 4 bytes (=minwidth) as counters.
            bytes_ = bytearray()
            append = bytes_.append
            while value:
                append(value & mask)
                value >>= bits
            bytes_ = bytes_.ljust(minwidth, b"\x00")

        if bigendian:
            bytes_.reverse()
        return bytes(bytes_)

    def as_bytes(self, bits=7, bigendian=True, width=4):
        return BitPaddedInt.to_bytes(self,bits,bigendian,width)

    @staticmethod
    def has_valid_padding(value, bits=7):
        """Whether the padding bits are all zero"""

        assert bits <= 8

        mask = (((1 << (8 - bits)) - 1) << bits)

        if isinstance(value, int):
            while value:
                if value & mask:
                    return False
                value >>= 8
        elif isinstance(value, bytes):
            for byte in value:
                if byte & mask:
                    return False
        else:
            raise TypeError

        return True
