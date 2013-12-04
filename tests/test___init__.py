import os
from io import BytesIO
from tempfile import mkstemp
import shutil

from tests import TestCase, add
from mutagenx import File, Metadata, FileType
from mutagenx.oggvorbis import OggVorbis
from mutagenx.oggflac import OggFLAC
from mutagenx.oggspeex import OggSpeex
from mutagenx.oggtheora import OggTheora
from mutagenx.oggopus import OggOpus
from mutagenx.mp3 import MP3, EasyMP3
from mutagenx.apev2 import APEv2File
from mutagenx.flac import FLAC
from mutagenx.wavpack import WavPack
from mutagenx.trueaudio import TrueAudio, EasyTrueAudio
from mutagenx.mp4 import MP4
from mutagenx.musepack import Musepack
from mutagenx.monkeysaudio import MonkeysAudio
from mutagenx.optimfrog import OptimFROG
from mutagenx.asf import ASF

from os import devnull

class TMetadata(TestCase):

    class FakeMeta(Metadata):
        def __init__(self): pass

    def test_virtual_constructor(self):
        self.failUnlessRaises(NotImplementedError, Metadata, "filename")

    def test_load(self):
        m = Metadata()
        self.failUnlessRaises(NotImplementedError, m.load, "filename")

    def test_virtual_save(self):
        self.failUnlessRaises(NotImplementedError, self.FakeMeta().save)
        self.failUnlessRaises(
            NotImplementedError, self.FakeMeta().save, "filename")

    def test_virtual_delete(self):
        self.failUnlessRaises(NotImplementedError, self.FakeMeta().delete)
        self.failUnlessRaises(
            NotImplementedError, self.FakeMeta().delete, "filename")
add(TMetadata)

class TFileType(TestCase):

    def setUp(self):
        self.vorbis = File(os.path.join("tests", "data", "empty.ogg"))

    def test_delitem_not_there(self):
        self.failUnlessRaises(KeyError, self.vorbis.__delitem__, "foobar")

    def test_add_tags(self):
        self.failUnlessRaises(NotImplementedError, FileType().add_tags)

    def test_delitem(self):
        self.vorbis["foobar"] = "quux"
        del(self.vorbis["foobar"])
        self.failIf("quux" in self.vorbis)
add(TFileType)

class TFile(TestCase):

    def test_bad(self):
        try: self.failUnless(File(devnull) is None)
        except (OSError, IOError):
            print("WARNING: Unable to open %s." % devnull)
        self.failUnless(File(__file__) is None)

    def test_empty(self):
        filename = os.path.join("tests", "data", "empty")
        open(filename, "wb").close()
        try: self.failUnless(File(filename) is None)
        finally: os.unlink(filename)

    def test_not_file(self):
        self.failUnlessRaises(EnvironmentError, File, "/dev/doesnotexist")

    def test_no_options(self):
        for filename in ["empty.ogg", "empty.oggflac", "silence-44-s.mp3"]:
            filename = os.path.join("tests", "data", "empty.ogg")
            self.failIf(File(filename, options=[]))

    def test_oggvorbis(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.ogg")), OggVorbis))

    def test_oggflac(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.oggflac")), OggFLAC))

    def test_oggspeex(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.spx")), OggSpeex))

    def test_oggtheora(self):
        self.failUnless(isinstance(File(
            os.path.join("tests", "data", "sample.oggtheora")), OggTheora))

    def test_oggopus(self):
        self.failUnless(isinstance(File(
            os.path.join("tests", "data", "example.opus")), OggOpus))

    def test_mp3(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "bad-xing.mp3")), MP3))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "xing.mp3")), MP3))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-44-s.mp3")), MP3))

    def test_easy_mp3(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-44-s.mp3"), easy=True),
            EasyMP3))

    def test_flac(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-44-s.flac")), FLAC))

    def test_musepack(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "click.mpc")), Musepack))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "sv4_header.mpc")), Musepack))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "sv5_header.mpc")), Musepack))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "sv8_header.mpc")), Musepack))

    def test_monkeysaudio(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "mac-399.ape")), MonkeysAudio))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "mac-396.ape")), MonkeysAudio))

    def test_apev2(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "oldtag.apev2")), APEv2File))

    def test_tta(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.tta")), TrueAudio))

    def test_easy_tta(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.tta"), easy=True),
            EasyTrueAudio))

    def test_wavpack(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-44-s.wv")), WavPack))

    def test_mp4(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "has-tags.m4a")), MP4))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "no-tags.m4a")), MP4))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "no-tags.3g2")), MP4))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "truncated-64bit.mp4")), MP4))

    def test_optimfrog(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.ofr")), OptimFROG))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "empty.ofs")), OptimFROG))

    def test_asf(self):
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-1.wma")), ASF))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-2.wma")), ASF))
        self.failUnless(isinstance(
            File(os.path.join("tests", "data", "silence-3.wma")), ASF))

    def test_id3_indicates_mp3_not_tta(self):
        header = b"ID3 the rest of this is garbage"
        fileobj = BytesIO(header)
        filename = "not-identifiable.ext"
        self.failUnless(TrueAudio.score(filename, fileobj, header) <
                        MP3.score(filename, fileobj, header))

add(TFile)

class TFileUpperExt(TestCase):
    FILES = [(os.path.join("tests", "data", "empty.ofr"), OptimFROG),
             (os.path.join("tests", "data", "sv5_header.mpc"), Musepack),
             (os.path.join("tests", "data", "silence-3.wma"), ASF),
             (os.path.join("tests", "data", "truncated-64bit.mp4"), MP4),
             (os.path.join("tests", "data", "silence-44-s.flac"), FLAC),
             ]

    def setUp(self):
        checks = []
        for (original, instance) in self.FILES:
            ext = os.path.splitext(original)[1]
            fd, filename = mkstemp(suffix='.'+ext.upper())
            os.close(fd)
            shutil.copy(original, filename)
            checks.append((filename, instance))
        self.checks = checks

    def test_case_insensitive_ext(self):
        for (path, instance) in self.checks:
            self.failUnless(isinstance(File(path, options=[instance]), instance))

    def tearDown(self):
        for (path, instance) in self.checks:
            os.unlink(path)

add(TFileUpperExt)


class TModuleImportAll(TestCase):

    def test_all(self):
        import mutagenx
        files = os.listdir(mutagenx.__path__[0])
        modules = [os.path.splitext(f)[0] for f in files]
        modules = [f for f in modules if not f.startswith("_")]

        for module in modules:
            mod = getattr(__import__("mutagenx." + module), module)
            for attr in getattr(mod, "__all__", []):
                getattr(mod, attr)

add(TModuleImportAll)
