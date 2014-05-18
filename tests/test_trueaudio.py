import os
import shutil
from mutagenx.trueaudio import TrueAudio, delete
from mutagenx.id3 import TIT1
from tests import TestCase, add
from tempfile import mkstemp

class TTrueAudio(TestCase):

    def setUp(self):
        self.audio = TrueAudio(os.path.join("tests", "data", "empty.tta"))

    def test_tags(self):
        self.failUnless(self.audio.tags is None)

    def test_length(self):
        self.failUnlessAlmostEqual(self.audio.info.length, 3.7, 1)

    def test_sample_rate(self):
        self.failUnlessEqual(44100, self.audio.info.sample_rate)

    def test_not_my_file(self):
        filename = os.path.join("tests", "data", "empty.ogg")
        self.failUnlessRaises(IOError, TrueAudio, filename)

    def test_module_delete(self):
        delete(os.path.join("tests", "data", "empty.tta"))

    def test_delete(self):
        self.audio.delete()
        self.failIf(self.audio.tags)

    def test_pprint(self):
        self.failUnless(self.audio.pprint())

    def test_save_reload(self):
        try:
            fd, filename = mkstemp(suffix='.tta')
            os.close(fd)
            shutil.copy(self.audio.filename, filename)
            audio = TrueAudio(filename)
            audio.add_tags()
            audio.tags.add(TIT1(encoding=0, text="A Title"))
            audio.save()
            audio = TrueAudio(filename)
            self.failUnlessEqual(audio["TIT1"], "A Title")
        finally:
            os.unlink(filename)

    def test_mime(self):
        self.failUnless("audio/x-tta" in self.audio.mime)

add(TTrueAudio)
