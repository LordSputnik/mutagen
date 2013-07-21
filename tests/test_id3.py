import os.path
from unittest import TestCase
from tests import add
from mutagen.id3 import ID3, BitPaddedInt, COMR, Frames, Frames_2_2, ID3Warning, ID3JunkFrameError
import shutil
import io
import warnings
warnings.simplefilter('error', ID3Warning)

_22 = ID3(); _22.version = (2,2,0)
_23 = ID3(); _23.version = (2,3,0)
_24 = ID3(); _24.version = (2,4,0)

class ID3GetSetDel(TestCase):
    uses_mmap = False

    def setUp(self):
        self.i = ID3()
        self.i["BLAH"] = 1
        self.i["QUUX"] = 2
        self.i["FOOB:ar"] = 3
        self.i["FOOB:az"] = 4

    def test_getnormal(self):
        self.assertEquals(self.i.getall("BLAH"), [1])
        self.assertEquals(self.i.getall("QUUX"), [2])
        self.assertEquals(self.i.getall("FOOB:ar"), [3])
        self.assertEquals(self.i.getall("FOOB:az"), [4])

    def test_getlist(self):
        self.assertEquals(self.i.getall("FOOB") , [3, 4])

    def test_delnormal(self):
        self.assert_("BLAH" in self.i)
        self.i.delall("BLAH")
        self.assert_("BLAH" not in self.i)

    def test_delone(self):
        self.i.delall("FOOB:ar")
        self.assertEquals(self.i.getall("FOOB"), [4])

    def test_delall(self):
        self.assert_("FOOB:ar" in self.i)
        self.assert_("FOOB:az" in self.i)
        self.i.delall("FOOB")
        self.assert_("FOOB:ar" not in self.i)
        self.assert_("FOOB:az" not in self.i)

    def test_setone(self):
        class TEST(object): HashKey = "FOOB:ar"
        t = TEST()
        self.i.setall("FOOB", [t])
        self.assertEquals(self.i["FOOB:ar"], t)
        self.assertEquals(self.i.getall("FOOB"), [t])

    def test_settwo(self):
        class TEST(object): HashKey = "FOOB:ar"
        t = TEST()
        t2 = TEST(); t2.HashKey = "FOOB:az"
        self.i.setall("FOOB", [t, t2])
        self.assertEquals(self.i["FOOB:ar"], t)
        self.assertEquals(self.i["FOOB:az"], t2)
        self.assertEquals(self.i.getall("FOOB"), [t, t2])

class ID3Loading(TestCase):
    uses_mmap = False


    empty = os.path.join('tests', 'data', 'emptyfile.mp3')
    silence = os.path.join('tests', 'data', 'silence-44-s.mp3')

    def test_empty_file(self):
        name = self.empty
        self.assertRaises(ValueError, ID3, filename=name)
        #from_name = ID3(name)
        #obj = open(name, 'rb')
        #from_obj = ID3(fileobj=obj)
        #self.assertEquals(from_name, from_explicit_name)
        #self.assertEquals(from_name, from_obj)

    def test_nonexistent_file(self):
        name = os.path.join('tests', 'data', 'does', 'not', 'exist')
        self.assertRaises(EnvironmentError, ID3, name)

    def test_header_empty(self):
        id3 = ID3()
        id3._ID3__fileobj = open(self.empty, 'rb')
        self.assertRaises(EOFError, id3._ID3__load_header)

    def test_header_silence(self):
        id3 = ID3()
        id3._ID3__fileobj = open(self.silence, 'rb')
        id3._ID3__load_header()
        self.assertEquals(id3.version, (2,3,0))
        self.assertEquals(id3.size, 1314)

    def test_header_2_4_invalid_flags(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x04\x00\x1f\x00\x00\x00\x00')
        self.assertRaises(ValueError, id3._ID3__load_header)

    def test_header_2_4_allow_footer(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x04\x00\x10\x00\x00\x00\x00')
        id3._ID3__load_header()

    def test_header_2_3_invalid_flags(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x03\x00\x1f\x00\x00\x00\x00')
        self.assertRaises(ValueError, id3._ID3__load_header)
        id3._ID3__fileobj = io.BytesIO(b'ID3\x03\x00\x0f\x00\x00\x00\x00')
        self.assertRaises(ValueError, id3._ID3__load_header)

    def test_header_2_2(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x02\x00\x00\x00\x00\x00\x00')
        id3._ID3__load_header()
        self.assertEquals(id3.version, (2,2,0))

    def test_header_2_1(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x01\x00\x00\x00\x00\x00\x00')
        self.assertRaises(NotImplementedError, id3._ID3__load_header)

    def test_header_too_small(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(b'ID3\x01\x00\x00\x00\x00\x00')
        self.assertRaises(EOFError, id3._ID3__load_header)

    def test_header_2_4_extended(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(
            b'ID3\x04\x00\x40\x00\x00\x00\x00\x00\x00\x00\x05\x5a')
        id3._ID3__load_header()
        self.assertEquals(id3._ID3__extsize, 1)
        self.assertEquals(id3._ID3__extdata, b'\x5a')

    def test_header_2_4_extended_but_not(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(
            b'ID3\x04\x00\x40\x00\x00\x00\x00TIT1\x00\x00\x00\x01a')
        id3._ID3__load_header()
        self.assertEquals(id3._ID3__extsize, 0)
        self.assertEquals(id3._ID3__extdata, b'')

    def test_header_2_4_extended_but_not_but_not_tag(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(
            b'ID3\x04\x00\x40\x00\x00\x00\x00TIT9')
        self.failUnlessRaises(EOFError, id3._ID3__load_header)

    def test_header_2_3_extended(self):
        id3 = ID3()
        id3._ID3__fileobj = io.BytesIO(
            b'ID3\x03\x00\x40\x00\x00\x00\x00\x00\x00\x00\x06'
            b'\x00\x00\x56\x78\x9a\xbc')
        id3._ID3__load_header()
        self.assertEquals(id3._ID3__extsize, 6)
        self.assertEquals(id3._ID3__extdata, b'\x00\x00\x56\x78\x9a\xbc')

    def test_unsynch(self):
        id3 = ID3()
        id3.version = (2,4,0)
        id3._ID3__flags = 0x80
        badsync = b'\x00\xff\x00ab\x00'
        self.assertEquals(id3._ID3__load_framedata(Frames["TPE2"], 0, badsync),
                          ["\xffab"])
        id3._ID3__flags = 0x00
        self.assertEquals(id3._ID3__load_framedata(Frames["TPE2"], 0x02, badsync),
                          ["\xffab"])
        tag = id3._ID3__load_framedata(Frames["TPE2"], 0, badsync)
        self.assertEquals(tag, ["\xff", "ab"])

    def test_insane__ID3__fullread(self):
        id3 = ID3()
        id3._ID3__filesize = 0
        self.assertRaises(ValueError, id3._ID3__fullread, -3)
        self.assertRaises(EOFError, id3._ID3__fullread, 3)

class Issue21(TestCase):
    uses_mmap = False

    # Files with bad extended header flags failed to read tags.
    # Ensure the extended header is turned off, and the frames are
    # read.
    def setUp(self):
        self.id3 = ID3(os.path.join('tests', 'data', 'issue_21.id3'))

    def test_no_ext(self):
        self.failIf(self.id3.f_extended)

    def test_has_tags(self):
        self.failUnless("TIT2" in self.id3)
        self.failUnless("TALB" in self.id3)

    def test_tit2_value(self):
        self.failUnlessEqual(self.id3["TIT2"].text, ["Punk To Funk"])

add(Issue21)

class ID3Tags(TestCase):
    uses_mmap = False

    def setUp(self):
        self.silence = os.path.join('tests', 'data', 'silence-44-s.mp3')

    def test_None(self):
        id3 = ID3(self.silence, known_frames={})
        self.assertEquals(0, len(id3.keys()))
        self.assertEquals(9, len(id3.unknown_frames))

    def test_has_docs(self):
        for Kind in (list(Frames.values()) + list(Frames_2_2.values())):
            self.failUnless(Kind.__doc__, "{} has no docstring".format(Kind))

    def test_23(self):
        id3 = ID3(self.silence)
        self.assertEquals(8, len(id3.keys()))
        self.assertEquals(0, len(id3.unknown_frames))
        self.assertEquals('Quod Libet Test Data', id3['TALB'])
        self.assertEquals('Silence', str(id3['TCON']))
        self.assertEquals('Silence', str(id3['TIT1']))
        self.assertEquals('Silence', str(id3['TIT2']))
        self.assertEquals(3000, +id3['TLEN'])
        self.assertNotEquals(['piman','jzig'], id3['TPE1'])
        self.assertEquals('02/10', id3['TRCK'])
        self.assertEquals(2, +id3['TRCK'])
        self.assertEquals('2004', id3['TDRC'])

    def test_23_multiframe_hack(self):
        class ID3hack(ID3):
            "Override 'correct' behavior with desired behavior"
            def add(self, frame):
                if frame.HashKey in self:
                    self[frame.HashKey].extend(frame[:])
                else:
                    self[frame.HashKey] = frame

        id3 = ID3hack(self.silence)
        self.assertEquals(8, len(id3.keys()))
        self.assertEquals(0, len(id3.unknown_frames))
        self.assertEquals('Quod Libet Test Data', id3['TALB'])
        self.assertEquals('Silence', str(id3['TCON']))
        self.assertEquals('Silence', str(id3['TIT1']))
        self.assertEquals('Silence', str(id3['TIT2']))
        self.assertEquals(3000, +id3['TLEN'])
        self.assertEquals(['piman','jzig'], id3['TPE1'])
        self.assertEquals('02/10', id3['TRCK'])
        self.assertEquals(2, +id3['TRCK'])
        self.assertEquals('2004', id3['TDRC'])

    def test_badencoding(self):
        self.assertRaises(IndexError, Frames["TPE1"].fromData, _24, 0, b"\x09ab")
        self.assertRaises(ValueError, Frames["TPE1"], encoding=9, text="ab")

    def test_badsync(self):
        self.assertRaises(
            ValueError, Frames["TPE1"].fromData, _24, 0x02, b"\x00\xff\xfe")

    def test_noencrypt(self):
        self.assertRaises(
            NotImplementedError, Frames["TPE1"].fromData, _24, 0x04, b"\x00")
        self.assertRaises(
            NotImplementedError, Frames["TPE1"].fromData, _23, 0x40, b"\x00")

    def test_badcompress(self):
        self.assertRaises(
            ValueError, Frames["TPE1"].fromData, _24, 0x08, b"\x00\x00\x00\x00#")
        self.assertRaises(
            ValueError, Frames["TPE1"].fromData, _23, 0x80, b"\x00\x00\x00\x00#")

    def test_junkframe(self):
        self.assertRaises(ValueError, Frames["TPE1"].fromData, _24, 0, b"")

    def test_bad_sylt(self):
        self.assertRaises(
            ID3JunkFrameError, Frames["SYLT"].fromData, _24, 0x0,
            b"\x00eng\x01description\x00foobar")
        self.assertRaises(
            ID3JunkFrameError, Frames["SYLT"].fromData, _24, 0x0,
            b"\x00eng\x01description\x00foobar\x00\xFF\xFF\xFF")

    def test_extradata(self):
        from mutagen.id3 import RVRB, RBUF
        self.assertRaises(ID3Warning, RVRB()._readData, b'L1R1BBFFFFPP#xyz')
        self.assertRaises(ID3Warning, RBUF()._readData,
                          b'\x00\x01\x00\x01\x00\x00\x00\x00#xyz')


class ID3v1Tags(TestCase):
    uses_mmap = False

    def setUp(self):
        self.silence = os.path.join('tests', 'data', 'silence-44-s-v1.mp3')
        self.id3 = ID3(self.silence)

    def test_album(self):
        self.assertEquals('Quod Libet Test Data', self.id3['TALB'])
    def test_genre(self):
        self.assertEquals('Darkwave', self.id3['TCON'].genres[0])
    def test_title(self):
        self.assertEquals('Silence', str(self.id3['TIT2']))
    def test_artist(self):
        self.assertEquals(['piman'], self.id3['TPE1'])
    def test_track(self):
        self.assertEquals('2', self.id3['TRCK'])
        self.assertEquals(2, +self.id3['TRCK'])
    def test_year(self):
        self.assertEquals('2004', self.id3['TDRC'])

    def test_v1_not_v11(self):
        from mutagen.id3 import MakeID3v1, ParseID3v1, TRCK
        self.id3["TRCK"] = TRCK(encoding=0, text="32")
        tag = MakeID3v1(self.id3)
        self.failUnless(32, ParseID3v1(tag)["TRCK"])
        del(self.id3["TRCK"])
        tag = MakeID3v1(self.id3)
        tag = tag[:125] + b'  ' + bytes([tag[-1]])
        self.failIf("TRCK" in ParseID3v1(tag))

    def test_nulls(self):
        from mutagen.id3 import ParseID3v1
        artist = (b'abcd\00fg' + b'\x00' * 30)[:30]
        title = (b'hijklmn\x00p' + b'\x00' * 30)[:30]
        album = (b'qrst\x00v' + b'\x00' * 30)[:30]
        cmt = (b'wxyz' + b'\x00' * 29)[:29]
        year = (b'1224' + b'\x00' * 4)[:4]
        s = b'TAG' + title + artist + album + year + cmt + b'\x03\x01'
        tags = ParseID3v1(s)
        self.assertEquals(b'abcd'.decode('latin1'), tags['TPE1'])
        self.assertEquals(b'hijklmn'.decode('latin1'), tags['TIT2'])
        self.assertEquals(b'qrst'.decode('latin1'), tags['TALB'])

    def test_nonascii(self):
        from mutagen.id3 import ParseID3v1
        artist = (b'abcd\xe9fg' + b'\x00' * 30)[:30]
        title = (b'hijklmn\xf3p' + b'\x00' * 30)[:30]
        album = (b'qrst\xfcv' + b'\x00' * 30)[:30]
        cmt = (b'wxyz' + b'\x00' * 29)[:29]
        year = (b'1234' + b'\x00' * 4)[:4]
        s = b'TAG' + title + artist + album + year + cmt + b'\x03\x01'
        tags = ParseID3v1(s)
        self.assertEquals(b'abcd\xe9fg'.decode('latin1'), tags['TPE1'])
        self.assertEquals(b'hijklmn\xf3p'.decode('latin1'), tags['TIT2'])
        self.assertEquals(b'qrst\xfcv'.decode('latin1'), tags['TALB'])
        self.assertEquals("wxyz", tags['COMM'])
        self.assertEquals("3", tags['TRCK'])
        self.assertEquals("1234", str(tags['TDRC']))

    def test_roundtrip(self):
        from mutagen.id3 import ParseID3v1, MakeID3v1
        frames = {}
        for key in ["TIT2", "TALB", "TPE1", "TDRC"]:
            frames[key] = self.id3[key]

        self.assertEquals(ParseID3v1(MakeID3v1(frames)), frames)

    def test_make_from_empty(self):
        from mutagen.id3 import MakeID3v1, TCON, COMM
        empty = b'TAG' + b'\x00' * 124 + b'\xff'
        self.assertEquals(MakeID3v1({}), empty)
        self.assertEquals(MakeID3v1({'TCON': TCON()}), empty)
        self.assertEquals(
            MakeID3v1({'COMM': COMM(encoding=0, text="")}), empty)

    def test_make_v1_from_tyer(self):
        from mutagen.id3 import ParseID3v1, MakeID3v1, TYER, TDRC
        self.assertEquals(
            MakeID3v1({"TDRC": TDRC(encoding=0, text="2010-10-10")}),
            MakeID3v1({"TYER": TYER(encoding=0, text="2010")}))
        self.assertEquals(
            ParseID3v1(MakeID3v1({"TDRC": TDRC(encoding=0, text="2010-10-10")})),
            ParseID3v1(MakeID3v1({"TYER": TYER(encoding=0, text="2010")})))

    def test_invalid(self):
        from mutagen.id3 import ParseID3v1
        self.failUnless(ParseID3v1(b"") is None)

    def test_invalid_track(self):
        from mutagen.id3 import ParseID3v1, MakeID3v1, TRCK
        tag = {}
        tag["TRCK"] = TRCK(encoding=0, text="not a number")
        v1tag = MakeID3v1(tag)
        self.failIf("TRCK" in ParseID3v1(v1tag))

    def test_v1_genre(self):
        from mutagen.id3 import ParseID3v1, MakeID3v1, TCON
        tag = {}
        tag["TCON"] = TCON(encoding=0, text="Pop")
        v1tag = MakeID3v1(tag)
        self.failUnlessEqual(ParseID3v1(v1tag)["TCON"].genres, ["Pop"])

class TestWriteID3v1(TestCase):
    SILENCE = os.path.join("tests", "data", "silence-44-s.mp3")
    def setUp(self):
        from tempfile import mkstemp
        fd, self.filename = mkstemp(suffix='.mp3')
        os.close(fd)
        shutil.copy(self.SILENCE, self.filename)
        self.audio = ID3(self.filename)

    def failIfV1(self):
        fileobj = open(self.filename, "rb")
        fileobj.seek(-128, 2)
        self.failIf(fileobj.read(3) == b"TAG")

    def failUnlessV1(self):
        fileobj = open(self.filename, "rb")
        fileobj.seek(-128, 2)
        self.failUnless(fileobj.read(3) == b"TAG")

    def test_save_delete(self):
        self.audio.save(v1=0)
        self.failIfV1()

    def test_save_add(self):
        self.audio.save(v1=2)
        self.failUnlessV1()

    def test_save_defaults(self):
        self.audio.save(v1=0)
        self.failIfV1()
        self.audio.save(v1=1)
        self.failIfV1()
        self.audio.save(v1=2)
        self.failUnlessV1()
        self.audio.save(v1=1)
        self.failUnlessV1()

    def tearDown(self):
        os.unlink(self.filename)

add(TestWriteID3v1)

add(ID3Loading)
add(ID3GetSetDel)
add(ID3Tags)
add(ID3v1Tags)
