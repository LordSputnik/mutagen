from __future__ import print_function, absolute_import, division

import os
from tempfile import mkstemp
import shutil

from mutagenx.id3 import ID3

from tests import add
from tests.test_tools import _TTools


AMBIGUOUS = b"\xc3\xae\xc3\xa5\xc3\xb4\xc3\xb2 \xc3\xa0\xc3\xa9\xc3\xa7\xc3" \
            b"\xa5\xc3\xa3 \xc3\xb9\xc3\xac \xc3\xab\xc3\xa5\xc3\xa5\xc3\xb8" \
            b"\xc3\xba"
CODECS = ["utf8", "latin-1", "Windows-1255", "gbk"]


class TMid3Iconv(_TTools):

    TOOL_NAME = "mid3iconv"

    def setUp(self):
        super(TMid3Iconv, self).setUp()
        original = os.path.join('tests', 'data', 'silence-44-s.mp3')
        fd, self.filename = mkstemp(suffix='.mp3')
        os.close(fd)
        shutil.copy(original, self.filename)

    def tearDown(self):
        super(TMid3Iconv, self).tearDown()
        os.unlink(self.filename)

    def test_noop(self):
        res, out = self.call()
        self.failIf(res)
        self.failUnless("Usage:" in out)

    def test_debug(self):
        res, out = self.call("-d", "-p", self.filename)
        self.failIf(res)
        self.failUnless("TCON=Silence" in out)

    def test_quiet(self):
        res, out = self.call("-q", self.filename)
        self.failIf(res)
        self.failIf(out)

    def test_test_data(self):
        results = set()
        for codec in CODECS:
            results.add(AMBIGUOUS.decode(codec))
        self.failUnlessEqual(len(results), len(CODECS))

    def test_conv_basic(self):
        from mutagen.id3 import TALB

        for codec in CODECS:
            f = ID3(self.filename)
            f.add(TALB(text=[AMBIGUOUS.decode("latin-1")], encoding=0))
            f.save()
            res, out = self.call("-d", "-e", codec, self.filename)
            f = ID3(self.filename)
            self.failUnlessEqual(f["TALB"].encoding, 1)
            self.failUnlessEqual(f["TALB"].text[0] , AMBIGUOUS.decode(codec))

    def test_comm(self):
        from mutagen.id3 import COMM

        for codec in CODECS:
            f = ID3(self.filename)
            frame = COMM(desc="", lang="eng",  encoding=0,
                         text=[AMBIGUOUS.decode("latin-1")])
            f.add(frame)
            f.save()
            res, out = self.call("-d", "-e", codec, self.filename)
            f = ID3(self.filename)
            new_frame = f[frame.HashKey]
            self.failUnlessEqual(new_frame.encoding, 1)
            self.failUnlessEqual(new_frame.text[0] , AMBIGUOUS.decode(codec))

    def test_remove_v1(self):
        from mutagen.id3 import ParseID3v1
        res, out = self.call("--remove-v1", self.filename)

        with open(self.filename, "rb") as h:
            h.seek(-128, 2)
            data = h.read()
            self.failUnlessEqual(len(data), 128)
            self.failIf(ParseID3v1(data))

add(TMid3Iconv)
