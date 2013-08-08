import os
import shutil
import tempfile

from unittest import TestCase

from tests import add

from mutagen.apev2 import APEv2File, APEv2, is_valid_apev2_key

DIR = os.path.dirname(__file__)
SAMPLE = os.path.join(DIR, "data", "click.mpc")
OLD = os.path.join(DIR, "data", "oldtag.apev2")
BROKEN = os.path.join(DIR, "data", "brokentag.apev2")
LYRICS2 = os.path.join(DIR, "data", "apev2-lyricsv2.mp3")

class Tis_valid_apev2_key(TestCase):
    uses_mmap = False
    def test_yes(self):
        for key in ["foo", "Foo", "   f ~~~"]:
            self.failUnless(is_valid_apev2_key(key))

    def test_no(self):
        for key in ["\x11hi", "ffoo\xFF", "\u1234", "a", "", "foo" * 100]:
            self.failIf(is_valid_apev2_key(key))
add(Tis_valid_apev2_key)


class TAPEWriter(TestCase):
    offset = 0

    def setUp(self):
        shutil.copy(SAMPLE, SAMPLE + ".new")
        shutil.copy(BROKEN, BROKEN + ".new")
        tag = APEv2()
        self.values = {"artist": "Joe Wreschnig\0unittest",
                       "album": "Mutagen tests",
                       "title": "Not really a song"}
        for k, v in self.values.items():
            tag[k] = v
        tag.save(SAMPLE + ".new")
        tag.save(SAMPLE + ".justtag")
        tag.save(SAMPLE + ".tag_at_start")
        fileobj = open(SAMPLE + ".tag_at_start", "ab")
        fileobj.write(b"tag garbage" * 1000)
        fileobj.close()
        self.tag = APEv2(SAMPLE + ".new")

    def test_changed(self):
        size = os.path.getsize(SAMPLE + ".new")
        self.tag.save()
        self.failUnlessEqual(
            os.path.getsize(SAMPLE + ".new"), size - self.offset)

    def test_fix_broken(self):
        # Clean up garbage from a bug in pre-Mutagen APEv2.
        # This also tests removing ID3v1 tags on writes.
        self.failIfEqual(os.path.getsize(OLD), os.path.getsize(BROKEN))
        tag = APEv2(BROKEN)
        tag.save(BROKEN + ".new")
        self.failUnlessEqual(
            os.path.getsize(OLD), os.path.getsize(BROKEN+".new"))

    def test_readback(self):
        for k, v in self.tag.items():
            self.failUnlessEqual(str(v), self.values[k])

    def test_size(self):
        self.failUnlessEqual(
            os.path.getsize(SAMPLE + ".new"),
            os.path.getsize(SAMPLE) + os.path.getsize(SAMPLE + ".justtag"))

    def test_delete(self):
        mutagen.apev2.delete(SAMPLE + ".justtag")
        tag = APEv2(SAMPLE + ".new")
        tag.delete()
        self.failUnlessEqual(os.path.getsize(SAMPLE + ".justtag"), self.offset)
        self.failUnlessEqual(os.path.getsize(SAMPLE) + self.offset,
                             os.path.getsize(SAMPLE + ".new"))
        self.failIf(tag)

    def test_empty(self):
        self.failUnlessRaises(
            IOError, APEv2,
            os.path.join("tests", "data", "emptyfile.mp3"))

    def test_tag_at_start(self):
        filename = SAMPLE + ".tag_at_start"
        tag = APEv2(filename)
        self.failUnlessEqual(tag["album"], "Mutagen tests")

    def test_tag_at_start_write(self):
        filename = SAMPLE + ".tag_at_start"
        tag = APEv2(filename)
        tag.save()
        tag = APEv2(filename)
        self.failUnlessEqual(tag["album"], "Mutagen tests")
        self.failUnlessEqual(
            os.path.getsize(SAMPLE + ".justtag"),
            os.path.getsize(filename) - (len("tag garbage") * 1000))

    def test_tag_at_start_delete(self):
        filename = SAMPLE + ".tag_at_start"
        tag = APEv2(filename)
        tag.delete()
        self.failUnlessRaises(IOError, APEv2, filename)
        self.failUnlessEqual(
            os.path.getsize(filename), len("tag garbage") * 1000)

    def test_case_preservation(self):
        mutagen.apev2.delete(SAMPLE + ".justtag")
        tag = APEv2(SAMPLE + ".new")
        tag["FoObaR"] = "Quux"
        tag.save()
        tag = APEv2(SAMPLE + ".new")
        self.failUnless("FoObaR" in tag.keys())
        self.failIf("foobar" in tag.keys())

    def test_unicode_key(self):
        # http://code.google.com/p/mutagen/issues/detail?id=123
        tag = APEv2(SAMPLE + ".new")
        tag["abc"] = '\xf6\xe4\xfc'
        tag["cba"] = "abc"
        tag.save()

    def tearDown(self):
        os.unlink(SAMPLE + ".new")
        os.unlink(BROKEN + ".new")
        os.unlink(SAMPLE + ".justtag")
        os.unlink(SAMPLE + ".tag_at_start")

add(TAPEWriter)
