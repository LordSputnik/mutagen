import os
import shutil
from tempfile import mkstemp

from mutagenx.id3 import ID3, TIT2
from mutagenx.musepack import Musepack, MusepackInfo, MusepackHeaderError
from io import BytesIO
from tests import TestCase, add

class TMusepack(TestCase):

    def setUp(self):
        self.sv8 = Musepack(os.path.join("tests", "data", "sv8_header.mpc"))
        self.sv7 = Musepack(os.path.join("tests", "data", "click.mpc"))
        self.sv5 = Musepack(os.path.join("tests", "data", "sv5_header.mpc"))
        self.sv4 = Musepack(os.path.join("tests", "data", "sv4_header.mpc"))

    def test_bad_header(self):
        self.failUnlessRaises(
            MusepackHeaderError,
            Musepack, os.path.join("tests", "data", "almostempty.mpc"))

    def test_channels(self):
        self.failUnlessEqual(self.sv8.info.channels, 2)
        self.failUnlessEqual(self.sv7.info.channels, 2)
        self.failUnlessEqual(self.sv5.info.channels, 2)
        self.failUnlessEqual(self.sv4.info.channels, 2)

    def test_sample_rate(self):
        self.failUnlessEqual(self.sv8.info.sample_rate, 44100)
        self.failUnlessEqual(self.sv7.info.sample_rate, 44100)
        self.failUnlessEqual(self.sv5.info.sample_rate, 44100)
        self.failUnlessEqual(self.sv4.info.sample_rate, 44100)

    def test_bitrate(self):
        self.failUnlessEqual(self.sv8.info.bitrate, 609)
        self.failUnlessEqual(self.sv7.info.bitrate, 194530)
        self.failUnlessEqual(self.sv5.info.bitrate, 39)
        self.failUnlessEqual(self.sv4.info.bitrate, 39)

    def test_length(self):
        self.failUnlessAlmostEqual(self.sv8.info.length, 1.49, 1)
        self.failUnlessAlmostEqual(self.sv7.info.length, 0.07, 2)
        self.failUnlessAlmostEqual(self.sv5.info.length, 26.3, 1)
        self.failUnlessAlmostEqual(self.sv4.info.length, 26.3, 1)

    def test_gain(self):
        self.failUnlessAlmostEqual(self.sv8.info.title_gain, -4.668, 3)
        self.failUnlessAlmostEqual(self.sv8.info.title_peak, 0.5288, 3)
        self.failUnlessEqual(self.sv8.info.title_gain, self.sv8.info.album_gain)
        self.failUnlessEqual(self.sv8.info.title_peak, self.sv8.info.album_peak)
        self.failUnlessAlmostEqual(self.sv7.info.title_gain, 9.27, 6)
        self.failUnlessAlmostEqual(self.sv7.info.title_peak, 0.1149, 4)
        self.failUnlessEqual(self.sv7.info.title_gain, self.sv7.info.album_gain)
        self.failUnlessEqual(self.sv7.info.title_peak, self.sv7.info.album_peak)
        self.failUnlessRaises(AttributeError, getattr, self.sv5, 'title_gain')

    def test_not_my_file(self):
        self.failUnlessRaises(
            MusepackHeaderError, Musepack,
            os.path.join("tests", "data", "empty.ogg"))
        self.failUnlessRaises(
            MusepackHeaderError, Musepack,
            os.path.join("tests", "data", "emptyfile.mp3"))

    def test_almost_my_file(self):
        self.failUnlessRaises(
            MusepackHeaderError, MusepackInfo, BytesIO(b"MP+" + b"\x00" * 32))
        self.failUnlessRaises(
            MusepackHeaderError, MusepackInfo, BytesIO(b"MP+" + b"\x00" * 100))
        self.failUnlessRaises(
            MusepackHeaderError, MusepackInfo, BytesIO(b"MPCK" + b"\x00" * 100))

    def test_pprint(self):
        self.sv8.pprint()
        self.sv7.pprint()
        self.sv5.pprint()
        self.sv4.pprint()

    def test_mime(self):
        self.failUnless("audio/x-musepack" in self.sv7.mime)

add(TMusepack)


class TMusepackWithID3(TestCase):
    SAMPLE = os.path.join("tests", "data", "click.mpc")

    def setUp(self):
        fd, self.NEW = mkstemp(suffix='mpc')
        os.close(fd)
        shutil.copy(self.SAMPLE, self.NEW)
        self.failUnlessEqual(open(self.SAMPLE,"rb").read(), open(self.NEW,"rb").read())

    def tearDown(self):
        os.unlink(self.NEW)

    def test_ignore_id3(self):
        id3 = ID3()
        id3.add(TIT2(encoding=0, text='id3 title'))
        id3.save(self.NEW)
        f = Musepack(self.NEW)
        f['title'] = 'apev2 title'
        f.save()
        id3 = ID3(self.NEW)
        self.failUnlessEqual(id3['TIT2'], 'id3 title')
        f = Musepack(self.NEW)
        self.failUnlessEqual(f['title'], 'apev2 title')

add(TMusepackWithID3)
