import os
import shutil
import struct
import io
import tempfile

from tests import TestCase, add

from mutagen.mp4 import MP4, Atom, Atoms, MP4Tags, MP4Info, \
     delete, MP4Cover, MP4MetadataError, MP4FreeForm
from mutagen._util import cdata

class TAtom(TestCase):
    uses_mmap = False

    def test_no_children(self):
        fileobj = io.BytesIO(b"\x00\x00\x00\x08atom")
        atom = Atom(fileobj)
        self.failUnlessRaises(KeyError, atom.__getitem__, "test")

    def test_length_1(self):
        fileobj = io.BytesIO(b"\x00\x00\x00\x01atom"
                           b"\x00\x00\x00\x00\x00\x00\x00\x08" + b"\x00" * 8)
        self.failUnlessEqual(Atom(fileobj).length, 8)

    def test_length_less_than_8(self):
        fileobj = io.BytesIO(b"\x00\x00\x00\x02atom")
        self.assertRaises(MP4MetadataError, Atom, fileobj)

    def test_render_too_big(self):
        class TooBig(bytes):
            def __len__(self):
                return 1 << 32
            
        data = TooBig(b"test")
        try:
            len(data)
        except OverflowError:
            # Py_ssize_t is still only 32 bits on this system.
            self.failUnlessRaises(OverflowError, Atom.render, b"data", data)
        else:
            data = Atom.render(b"data", data)
            self.failUnlessEqual(len(data), 4 + 4 + 8 + 4)

    def test_non_top_level_length_0_is_invalid(self):
        data = io.BytesIO(struct.pack(">I4s", 0, b"whee"))
        self.assertRaises(MP4MetadataError, Atom, data, level=1)

    def test_length_0(self):
        fileobj = io.BytesIO(b"\x00\x00\x00\x00atom" + 40 * b"\x00")
        atom = Atom(fileobj)
        self.failUnlessEqual(fileobj.tell(), 48)
        self.failUnlessEqual(atom.length, 48)

    def test_length_0_container(self):
        data = io.BytesIO(struct.pack(">I4s", 0, b"moov") +
                        Atom.render(b"data", b"whee"))
        atom = Atom(data)
        self.failUnlessEqual(len(atom.children), 1)
        self.failUnlessEqual(atom.length, 20)
        self.failUnlessEqual(atom.children[-1].length, 12)

add(TAtom)
