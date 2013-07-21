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

class TestV22Tags(TestCase):
    uses_mmap = False

    def setUp(self):
        filename = os.path.join("tests", "data", "id3v22-test.mp3")
        self.tags = ID3(filename)

    def test_tags(self):
        self.failUnless(self.tags["TRCK"].text == ["3/11"])
        self.failUnless(self.tags["TPE1"].text == ["Anais Mitchell"])
add(TestV22Tags)

def TestReadTags():
    #tag, data, value, intval, info
    tests = [
    ['TALB', b'\x00a/b', 'a/b', '', dict(encoding=0)],
    ['TBPM', b'\x00120', '120', 120, dict(encoding=0)],
    ['TCMP', b'\x001', '1', 1, dict(encoding=0)],
    ['TCMP', b'\x000', '0', 0, dict(encoding=0)],
    ['TCOM', b'\x00a/b', 'a/b', '', dict(encoding=0)],
    ['TCON', b'\x00(21)Disco', '(21)Disco', '', dict(encoding=0)],
    ['TCOP', b'\x001900 c', '1900 c', '', dict(encoding=0)],
    ['TDAT', b'\x00a/b', 'a/b', '', dict(encoding=0)],
    ['TDEN', b'\x001987', '1987', '', dict(encoding=0, year=[1987])],
    ['TDOR', b'\x001987-12', '1987-12', '',
     dict(encoding=0, year=[1987], month=[12])],
    ['TDRC', b'\x001987\x00', '1987', '', dict(encoding=0, year=[1987])],
    ['TDRL', b'\x001987\x001988', '1987,1988', '',
     dict(encoding=0, year=[1987,1988])],
    ['TDTG', b'\x001987', '1987', '', dict(encoding=0, year=[1987])],
    ['TDLY', b'\x001205', '1205', 1205, dict(encoding=0)],
    ['TENC', b'\x00a b/c d', 'a b/c d', '', dict(encoding=0)],
    ['TEXT', b'\x00a b\x00c d', ['a b', 'c d'], '', dict(encoding=0)],
    ['TFLT', b'\x00MPG/3', 'MPG/3', '', dict(encoding=0)],
    ['TIME', b'\x001205', '1205', '', dict(encoding=0)],
    ['TIPL', b'\x02\x00a\x00\x00\x00b', [["a", "b"]], '', dict(encoding=2)],
    ['TIT1', b'\x00a/b', 'a/b', '', dict(encoding=0)],
    # TIT2 checks misaligned terminator '\x00\x00' across crosses utf16 chars
    ['TIT2', b'\x01\xff\xfe\x38\x00\x00\x38', u'8\u3800', '', dict(encoding=1)],
    ['TIT3', b'\x00a/b', 'a/b', '', dict(encoding=0)],
    ['TKEY', b'\x00A#m', 'A#m', '', dict(encoding=0)],
    ['TLAN', b'\x006241', '6241', '', dict(encoding=0)],
    ['TLEN', b'\x006241', '6241', 6241, dict(encoding=0)],
    ['TMCL', b'\x02\x00a\x00\x00\x00b', [["a", "b"]], '', dict(encoding=2)],
    ['TMED', b'\x00med', 'med', '', dict(encoding=0)],
    ['TMOO', b'\x00moo', 'moo', '', dict(encoding=0)],
    ['TOAL', b'\x00alb', 'alb', '', dict(encoding=0)],
    ['TOFN', b'\x0012 : bar', '12 : bar', '', dict(encoding=0)],
    ['TOLY', b'\x00lyr', 'lyr', '', dict(encoding=0)],
    ['TOPE', b'\x00own/lic', 'own/lic', '', dict(encoding=0)],
    ['TORY', b'\x001923', '1923', 1923, dict(encoding=0)],
    ['TOWN', b'\x00own/lic', 'own/lic', '', dict(encoding=0)],
    ['TPE1', b'\x00ab', ['ab'], '', dict(encoding=0)],
    ['TPE2', b'\x00ab\x00cd\x00ef', ['ab','cd','ef'], '', dict(encoding=0)],
    ['TPE3', b'\x00ab\x00cd', ['ab','cd'], '', dict(encoding=0)],
    ['TPE4', b'\x00ab\x00', ['ab'], '', dict(encoding=0)],
    ['TPOS', b'\x0008/32', '08/32', 8, dict(encoding=0)],
    ['TPRO', b'\x00pro', 'pro', '', dict(encoding=0)],
    ['TPUB', b'\x00pub', 'pub', '', dict(encoding=0)],
    ['TRCK', b'\x004/9', '4/9', 4, dict(encoding=0)],
    ['TRDA', b'\x00Sun Jun 12', 'Sun Jun 12', '', dict(encoding=0)],
    ['TRSN', b'\x00ab/cd', 'ab/cd', '', dict(encoding=0)],
    ['TRSO', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSIZ', b'\x0012345', '12345', 12345, dict(encoding=0)],
    ['TSOA', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSOP', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSOT', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSO2', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSOC', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TSRC', b'\x0012345', '12345', '', dict(encoding=0)],
    ['TSSE', b'\x0012345', '12345', '', dict(encoding=0)],
    ['TSST', b'\x0012345', '12345', '', dict(encoding=0)],
    ['TYER', b'\x002004', '2004', 2004, dict(encoding=0)],

    ['TXXX', b'\x00usr\x00a/b\x00c', ['a/b','c'], '',
     dict(encoding=0, desc='usr')],

    ['WCOM', b'http://foo', 'http://foo', '', {}],
    ['WCOP', b'http://bar', 'http://bar', '', {}],
    ['WOAF', b'http://baz', 'http://baz', '', {}],
    ['WOAR', b'http://bar', 'http://bar', '', {}],
    ['WOAS', b'http://bar', 'http://bar', '', {}],
    ['WORS', b'http://bar', 'http://bar', '', {}],
    ['WPAY', b'http://bar', 'http://bar', '', {}],
    ['WPUB', b'http://bar', 'http://bar', '', {}],

    ['WXXX', b'\x00usr\x00http', 'http', '', dict(encoding=0, desc='usr')],

    ['IPLS', b'\x00a\x00A\x00b\x00B\x00', [['a','A'],['b','B']], '',
        dict(encoding=0)],

    ['MCDI', b'\x01\x02\x03\x04', b'\x01\x02\x03\x04', '', {}],

    ['ETCO', b'\x01\x12\x00\x00\x7f\xff', [(18, 32767)], '', dict(format=1)],

    ['COMM', b'\x00ENUT\x00Com', 'Com', '',
        dict(desc='T', lang=b'ENU', encoding=0)],
    # found in a real MP3
    ['COMM', b'\x00\x00\xcc\x01\x00     ', '     ', '',
        dict(desc='', lang=b'\x00\xcc\x01', encoding=0)],

    ['APIC', b'\x00-->\x00\x03cover\x00cover.jpg', b'cover.jpg', '',
        dict(mime='-->', type=3, desc='cover', encoding=0)],
    ['USER', b'\x00ENUCom', 'Com', '', dict(lang=b'ENU', encoding=0)],

    ['RVA2', b'testdata\x00\x01\xfb\x8c\x10\x12\x23',
        'Master volume: -2.2266 dB/0.1417', '',
        dict(desc='testdata', channel=1, gain=-2.22656, peak=0.14169)],

    ['RVA2', b'testdata\x00\x01\xfb\x8c\x24\x01\x22\x30\x00\x00',
        'Master volume: -2.2266 dB/0.1417', '',
        dict(desc='testdata', channel=1, gain=-2.22656, peak=0.14169)],

    ['RVA2', b'testdata2\x00\x01\x04\x01\x00',
        'Master volume: +2.0020 dB/0.0000', '',
        dict(desc='testdata2', channel=1, gain=2.001953125, peak=0)],

    ['PCNT', b'\x00\x00\x00\x11', 17, 17, dict(count=17)],
    ['POPM', b'foo@bar.org\x00\xde\x00\x00\x00\x11', 222, 222,
        dict(email="foo@bar.org", rating=222, count=17)],
    ['POPM', b'foo@bar.org\x00\xde\x00', 222, 222,
        dict(email="foo@bar.org", rating=222, count=0)],
    # Issue #33 - POPM may have no playcount at all.
    ['POPM', b'foo@bar.org\x00\xde', 222, 222,
        dict(email="foo@bar.org", rating=222)],

    ['UFID', b'own\x00data', b'data', '', dict(data=b'data', owner='own')],
    ['UFID', b'own\x00\xdd', b'\xdd', '', dict(data=b'\xdd', owner='own')],

    ['GEOB', b'\x00mime\x00name\x00desc\x00data', b'data', '',
        dict(encoding=0, mime='mime', filename='name', desc='desc')],

    ['USLT', b'\x00engsome lyrics\x00woo\nfun', 'woo\nfun', '',
     dict(encoding=0, lang=b'eng', desc='some lyrics', text='woo\nfun')],

    ['SYLT', (b'\x00eng\x02\x01some lyrics\x00foo\x00\x00\x00\x00\x01bar'
              b'\x00\x00\x00\x00\x10'), "foobar", '',
     dict(encoding=0, lang=b'eng', type=1, format=2, desc='some lyrics')],

    ['POSS', b'\x01\x0f', 15, 15, dict(format=1, position=15)],
    ['OWNE', b'\x00USD10.01\x0020041010CDBaby', 'CDBaby', 'CDBaby',
     dict(encoding=0, price="USD10.01", date=b'20041010', seller='CDBaby')],

    ['PRIV', b'a@b.org\x00random data', b'random data', 'random data',
     dict(owner='a@b.org', data=b'random data')],
    ['PRIV', b'a@b.org\x00\xdd', b'\xdd', '\xdd',
     dict(owner='a@b.org', data=b'\xdd')],

    ['SIGN', b'\x92huh?', b'huh?', 'huh?', dict(group=0x92, sig=b'huh?')],
    ['ENCR', b'a@b.org\x00\x92Data!', b'Data!', 'Data!',
     dict(owner='a@b.org', method=0x92, data=b'Data!')],
    ['SEEK', b'\x00\x12\x00\x56', 0x12*256*256+0x56, 0x12*256*256+0x56,
     dict(offset=0x12*256*256+0x56)],

    ['SYTC', b"\x01\x10obar", b'\x10obar', '', dict(format=1, data=b'\x10obar')],

    ['RBUF', b'\x00\x12\x00', 0x12*256, 0x12*256, dict(size=0x12*256)],
    ['RBUF', b'\x00\x12\x00\x01', 0x12*256, 0x12*256,
     dict(size=0x12*256, info=1)],
    ['RBUF', b'\x00\x12\x00\x01\x00\x00\x00\x23', 0x12*256, 0x12*256,
     dict(size=0x12*256, info=1, offset=0x23)],

    ['RVRB', b'\x12\x12\x23\x23\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11',
     (0x12*256+0x12, 0x23*256+0x23), '',
     dict(left=0x12*256+0x12, right=0x23*256+0x23) ],

    ['AENC', b'a@b.org\x00\x00\x12\x00\x23', 'a@b.org', 'a@b.org',
     dict(owner='a@b.org', preview_start=0x12, preview_length=0x23)],
    ['AENC', b'a@b.org\x00\x00\x12\x00\x23!', 'a@b.org', 'a@b.org',
     dict(owner='a@b.org', preview_start=0x12, preview_length=0x23, data=b'!')],

    ['GRID', b'a@b.org\x00\x99', 'a@b.org', 0x99,
     dict(owner='a@b.org', group=0x99)],
    ['GRID', b'a@b.org\x00\x99data', 'a@b.org', 0x99,
     dict(owner='a@b.org', group=0x99, data=b'data')],

    ['COMR', b'\x00USD10.00\x0020051010ql@sc.net\x00\x09Joe\x00A song\x00'
     b'x-image/fake\x00some data',
     COMR(encoding=0, price="USD10.00", valid_until=b"20051010",
          contact="ql@sc.net", format=9, seller="Joe", desc="A song",
          mime='x-image/fake', logo=b'some data'), '',
     dict(
        encoding=0, price="USD10.00", valid_until=b"20051010",
        contact="ql@sc.net", format=9, seller="Joe", desc="A song",
        mime='x-image/fake', logo=b'some data')],

    ['COMR', b'\x00USD10.00\x0020051010ql@sc.net\x00\x09Joe\x00A song\x00',
     COMR(encoding=0, price="USD10.00", valid_until=b"20051010",
          contact="ql@sc.net", format=9, seller="Joe", desc="A song"), '',
     dict(
        encoding=0, price="USD10.00", valid_until=b"20051010",
        contact="ql@sc.net", format=9, seller="Joe", desc="A song")],

    ['MLLT', b'\x00\x01\x00\x00\x02\x00\x00\x03\x04\x08foobar', b'foobar', '',
     dict(frames=1, bytes=2, milliseconds=3, bits_for_bytes=4,
          bits_for_milliseconds=8, data=b'foobar')],

    ['EQU2', b'\x00Foobar\x00\x01\x01\x04\x00', [(128.5, 2.0)], '',
     dict(method=0, desc="Foobar")],

    ['ASPI', b'\x00\x00\x00\x00\x00\x00\x00\x10\x00\x03\x08\x01\x02\x03',
     [1, 2, 3], '', dict(S=0, L=16, N=3, b=8)],

    ['ASPI', b'\x00\x00\x00\x00\x00\x00\x00\x10\x00\x03\x10'
     b'\x00\x01\x00\x02\x00\x03', [1, 2, 3], '', dict(S=0, L=16, N=3, b=16)],

    ['LINK', b'TIT1http://www.example.org/TIT1.txt\x00',
     (b"TIT1", 'http://www.example.org/TIT1.txt'), '',
     dict(frameid=b'TIT1', url='http://www.example.org/TIT1.txt')],
    ['LINK', b'COMMhttp://www.example.org/COMM.txt\x00engfoo',
     (b"COMM", 'http://www.example.org/COMM.txt', b'engfoo'), '',
     dict(frameid=b'COMM', url='http://www.example.org/COMM.txt',
          data=b'engfoo')],

    # 2.2 tags
    ['UFI', b'own\x00data', b'data', '', dict(data=b'data', owner='own')],
    ['SLT', (b'\x00eng\x02\x01some lyrics\x00foo\x00\x00\x00\x00\x01bar'
             b'\x00\x00\x00\x00\x10'), "foobar", '',
     dict(encoding=0, lang=b'eng', type=1, format=2, desc='some lyrics')],
    ['TT1', b'\x00ab\x00', 'ab', '', dict(encoding=0)],
    ['TT2', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TT3', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TP1', b'\x00ab\x00', 'ab', '', dict(encoding=0)],
    ['TP2', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TP3', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TP4', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TCM', b'\x00ab/cd', 'ab/cd', '', dict(encoding=0)],
    ['TXT', b'\x00lyr', 'lyr', '', dict(encoding=0)],
    ['TLA', b'\x00ENU', 'ENU', '', dict(encoding=0)],
    ['TCO', b'\x00gen', 'gen', '', dict(encoding=0)],
    ['TAL', b'\x00alb', 'alb', '', dict(encoding=0)],
    ['TPA', b'\x001/9', '1/9', 1, dict(encoding=0)],
    ['TRK', b'\x002/8', '2/8', 2, dict(encoding=0)],
    ['TRC', b'\x00isrc', 'isrc', '', dict(encoding=0)],
    ['TYE', b'\x001900', '1900', 1900, dict(encoding=0)],
    ['TDA', b'\x002512', '2512', '', dict(encoding=0)],
    ['TIM', b'\x001225', '1225', '', dict(encoding=0)],
    ['TRD', b'\x00Jul 17', 'Jul 17', '', dict(encoding=0)],
    ['TMT', b'\x00DIG/A', 'DIG/A', '', dict(encoding=0)],
    ['TFT', b'\x00MPG/3', 'MPG/3', '', dict(encoding=0)],
    ['TBP', b'\x00133', '133', 133, dict(encoding=0)],
    ['TCP', b'\x001', '1', 1, dict(encoding=0)],
    ['TCP', b'\x000', '0', 0, dict(encoding=0)],
    ['TCR', b'\x00Me', 'Me', '', dict(encoding=0)],
    ['TPB', b'\x00Him', 'Him', '', dict(encoding=0)],
    ['TEN', b'\x00Lamer', 'Lamer', '', dict(encoding=0)],
    ['TSS', b'\x00ab', 'ab', '', dict(encoding=0)],
    ['TOF', b'\x00ab:cd', 'ab:cd', '', dict(encoding=0)],
    ['TLE', b'\x0012', '12', 12, dict(encoding=0)],
    ['TSI', b'\x0012', '12', 12, dict(encoding=0)],
    ['TDY', b'\x0012', '12', 12, dict(encoding=0)],
    ['TKE', b'\x00A#m', 'A#m', '', dict(encoding=0)],
    ['TOT', b'\x00org', 'org', '', dict(encoding=0)],
    ['TOA', b'\x00org', 'org', '', dict(encoding=0)],
    ['TOL', b'\x00org', 'org', '', dict(encoding=0)],
    ['TOR', b'\x001877', '1877', 1877, dict(encoding=0)],
    ['TXX', b'\x00desc\x00val', 'val', '', dict(encoding=0, desc='desc')],

    ['WAF', b'http://zzz', 'http://zzz', '', {}],
    ['WAR', b'http://zzz', 'http://zzz', '', {}],
    ['WAS', b'http://zzz', 'http://zzz', '', {}],
    ['WCM', b'http://zzz', 'http://zzz', '', {}],
    ['WCP', b'http://zzz', 'http://zzz', '', {}],
    ['WPB', b'http://zzz', 'http://zzz', '', {}],
    ['WXX', b'\x00desc\x00http', 'http', '', dict(encoding=0, desc='desc')],

    ['IPL', b'\x00a\x00A\x00b\x00B\x00', [['a','A'],['b','B']], '',
        dict(encoding=0)],
    ['MCI', b'\x01\x02\x03\x04', b'\x01\x02\x03\x04', '', {}],

    ['ETC', b'\x01\x12\x00\x00\x7f\xff', [(18, 32767)], '', dict(format=1)],

    ['COM', b'\x00ENUT\x00Com', 'Com', '',
        dict(desc='T', lang=b'ENU', encoding=0)],
    ['PIC', b'\x00-->\x03cover\x00cover.jpg', b'cover.jpg', '',
        dict(mime=b'-->', type=3, desc='cover', encoding=0)],

    ['POP', b'foo@bar.org\x00\xde\x00\x00\x00\x11', 222, 222,
        dict(email="foo@bar.org", rating=222, count=17)],
    ['CNT', b'\x00\x00\x00\x11', 17, 17, dict(count=17)],
    ['GEO', b'\x00mime\x00name\x00desc\x00data', b'data', '',
        dict(encoding=0, mime='mime', filename='name', desc='desc')],
    ['ULT', b'\x00engsome lyrics\x00woo\nfun', 'woo\nfun', '',
     dict(encoding=0, lang=b'eng', desc='some lyrics', text='woo\nfun')],

    ['BUF', b'\x00\x12\x00', 0x12*256, 0x12*256, dict(size=0x12*256)],

    ['CRA', b'a@b.org\x00\x00\x12\x00\x23', 'a@b.org', 'a@b.org',
     dict(owner='a@b.org', preview_start=0x12, preview_length=0x23)],
    ['CRA', b'a@b.org\x00\x00\x12\x00\x23!', 'a@b.org', 'a@b.org',
     dict(owner='a@b.org', preview_start=0x12, preview_length=0x23, data=b'!')],

    ['REV', b'\x12\x12\x23\x23\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11',
     (0x12*256+0x12, 0x23*256+0x23), '',
     dict(left=0x12*256+0x12, right=0x23*256+0x23) ],

    ['STC', b"\x01\x10obar", b'\x10obar', '', dict(format=1, data=b'\x10obar')],

    ['MLL', b'\x00\x01\x00\x00\x02\x00\x00\x03\x04\x08foobar', b'foobar', '',
     dict(frames=1, bytes=2, milliseconds=3, bits_for_bytes=4,
          bits_for_milliseconds=8, data=b'foobar')],
    ['LNK', b'TT1http://www.example.org/TIT1.txt\x00',
     (b"TT1", 'http://www.example.org/TIT1.txt'), '',
     dict(frameid=b'TT1', url='http://www.example.org/TIT1.txt')],
    ['CRM', b'foo@example.org\x00test\x00woo',
     b'woo', '', dict(owner='foo@example.org', desc='test', data=b'woo')],

    ]

    load_tests = {}
    repr_tests = {}
    write_tests = {}
    for i, (tag, data, value, intval, info) in enumerate(tests):
        info = info.copy()

        def test_tag(self, tag=tag, data=data, value=value, intval=intval,
                     info=info):
            from operator import pos
            id3 = __import__('mutagen.id3', globals(), locals(), [tag])
            TAG = getattr(id3, tag)
            tag = TAG.fromData(_23, 0, data)
            self.failUnless(tag.HashKey)
            self.failUnless(tag.pprint())
            self.assertEquals(value, tag)
            if 'encoding' not in info:
                self.assertRaises(AttributeError, getattr, tag, 'encoding')
            for attr, value in info.items():
                t = tag
                if not isinstance(value, list):
                    value = [value]
                    t = [t]
                for value, t in zip(value, iter(t)):
                    if isinstance(value, float):
                        self.failUnlessAlmostEqual(value, getattr(t, attr), 5)
                    else:
                        self.assertEquals(value, getattr(t, attr))

                    if isinstance(intval, int):
                        self.assertEquals(intval, pos(t))
                    else:
                        self.assertRaises(TypeError, pos, t)

        load_tests['test_{}_{}'.format(tag, i)] = test_tag

        def test_tag_repr(self, tag=tag, data=data):
            from mutagen.id3 import ID3TimeStamp
            id3 = __import__('mutagen.id3', globals(), locals(), [tag])
            TAG = getattr(id3, tag)
            tag = TAG.fromData(_23, 0, data)
            tag2 = eval(repr(tag), {TAG.__name__:TAG,
                    'ID3TimeStamp':ID3TimeStamp})
            self.assertEquals(type(tag), type(tag2))
            for spec in TAG._framespec:
                attr = spec.name
                self.assertEquals(getattr(tag, attr), getattr(tag2, attr))
        repr_tests['test_repr_{}_{}'.format(tag, i)] = test_tag_repr

        def test_tag_write(self, tag=tag, data=data):
            id3 = __import__('mutagen.id3', globals(), locals(), [tag])
            TAG = getattr(id3, tag)
            tag = TAG.fromData(_24, 0, data)
            towrite = tag._writeData()
            tag2 = TAG.fromData(_24, 0, towrite)
            for spec in TAG._framespec:
                attr = spec.name
                self.assertEquals(getattr(tag, attr), getattr(tag2, attr))
        write_tests['test_write_{}_{}'.format(tag, i)] = test_tag_write

    testcase = type('TestReadTags', (TestCase,), load_tests)
    testcase.uses_mmap = False
    add(testcase)
    testcase = type('TestReadReprTags', (TestCase,), repr_tests)
    testcase.uses_mmap = False
    #add(testcase)
    testcase = type('TestReadWriteTags', (TestCase,), write_tests)
    testcase.uses_mmap = False
    #add(testcase)

    test_tests = {}
    from mutagen.id3 import Frames, Frames_2_2
    check = dict.fromkeys(list(Frames.keys()) + list(Frames_2_2.keys()))
    tested_tags = dict.fromkeys([row[0] for row in tests])
    for tag in check:
        def check(self, tag=tag): self.assert_(tag in tested_tags)
        tested_tags['test_' + tag + '_tested'] = check
    testcase = type('TestTestedTags', (TestCase,), tested_tags)
    testcase.uses_mmap = False
    #add(testcase)

TestReadTags()
del TestReadTags

add(TestWriteID3v1)

add(ID3Loading)
add(ID3GetSetDel)
add(ID3Tags)
add(ID3v1Tags)
