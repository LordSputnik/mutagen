import os

from mutagenx.wavpack import WavPack
from tests import TestCase, add

class TWavPack(TestCase):

    def setUp(self):
        self.audio = WavPack(os.path.join("tests", "data", "silence-44-s.wv"))

    def test_channels(self):
        self.failUnlessEqual(self.audio.info.channels, 2)

    def test_sample_rate(self):
        self.failUnlessEqual(self.audio.info.sample_rate, 44100)

    def test_length(self):
        self.failUnlessAlmostEqual(self.audio.info.length, 3.68, 2)

    def test_not_my_file(self):
        self.failUnlessRaises(
            IOError, WavPack, os.path.join("tests", "data", "empty.ogg"))

    def test_pprint(self):
        self.audio.pprint()

    def test_mime(self):
        self.failUnless("audio/x-wavpack" in self.audio.mime)

add(TWavPack)
