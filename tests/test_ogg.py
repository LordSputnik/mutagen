import os
import random
import shutil

from io import BytesIO
from tests import TestCase, add
from mutagenx.ogg import OggPage, OggFileType, error as OggError
from mutagenx._util import cdata
from tempfile import mkstemp
from os import devnull

class TOggPage(TestCase):

    def setUp(self):
        self.fileobj = open(os.path.join("tests", "data", "empty.ogg"), "rb")
        self.page = OggPage(self.fileobj)

        pages = [OggPage(), OggPage(), OggPage()]
        pages[0].packets = [b"foo"]
        pages[1].packets = [b"bar"]
        pages[2].packets = [b"baz"]
        for i in range(len(pages)):
            pages[i].sequence = i
        for page in pages:
            page.serial = 1
        self.pages = pages

    def test_flags(self):
        self.failUnless(self.page.first)
        self.failIf(self.page.continued)
        self.failIf(self.page.last)
        self.failUnless(self.page.complete)

        for first in [True, False]:
            self.page.first = first
            for last in [True, False]:
                self.page.last = last
                for continued in [True, False]:
                    self.page.continued = continued
                    self.failUnlessEqual(self.page.first, first)
                    self.failUnlessEqual(self.page.last, last)
                    self.failUnlessEqual(self.page.continued, continued)

    def test_flags_next_page(self):
        page = OggPage(self.fileobj)
        self.failIf(page.first)
        self.failIf(page.continued)
        self.failIf(page.last)

    def test_length(self):
        # Always true for Ogg Vorbis files
        self.failUnlessEqual(self.page.size, 58)
        self.failUnlessEqual(len(self.page.write()), 58)

    def test_first_metadata_page_is_separate(self):
        self.failIf(OggPage(self.fileobj).continued)

    def test_single_page_roundtrip(self):
        self.failUnlessEqual(
            self.page, OggPage(BytesIO(self.page.write())))

    def test_at_least_one_audio_page(self):
        page = OggPage(self.fileobj)
        while not page.last:
            page = OggPage(self.fileobj)
        self.failUnless(page.last)

    def test_crappy_fragmentation(self):
        packets = [b"1" * 511, b"2" * 511, b"3" * 511]
        pages = OggPage.from_packets(packets, default_size=510, wiggle_room=0)
        self.failUnless(len(pages) > 3)
        self.failUnlessEqual(OggPage.to_packets(pages), packets)

    def test_wiggle_room(self):
        packets = [b"1" * 511, b"2" * 511, b"3" * 511]
        pages = OggPage.from_packets(packets, default_size=510, wiggle_room=100)
        self.failUnlessEqual(len(pages), 3)
        self.failUnlessEqual(OggPage.to_packets(pages), packets)

    def test_one_packet_per_wiggle(self):
        packets = [b"1" * 511, b"2" * 511, b"3" * 511]
        pages = OggPage.from_packets(
            packets, default_size=1000, wiggle_room=1000000)
        self.failUnlessEqual(len(pages), 2)
        self.failUnlessEqual(OggPage.to_packets(pages), packets)

    def test_renumber(self):
        self.failUnlessEqual(
            [page.sequence for page in self.pages], [0, 1, 2])
        fileobj = BytesIO()
        for page in self.pages:
            fileobj.write(page.write())
        fileobj.seek(0)
        OggPage.renumber(fileobj, 1, 10)
        fileobj.seek(0)
        pages = [OggPage(fileobj) for i in range(3)]
        self.failUnlessEqual([page.sequence for page in pages], [10, 11, 12])

        fileobj.seek(0)
        OggPage.renumber(fileobj, 1, 20)
        fileobj.seek(0)
        pages = [OggPage(fileobj) for i in range(3)]
        self.failUnlessEqual([page.sequence for page in pages], [20, 21, 22])

    def test_renumber_extradata(self):
        fileobj = BytesIO()
        for page in self.pages:
            fileobj.write(page.write())
        fileobj.write(b"left over data")
        fileobj.seek(0)
        orig_data = fileobj.read()
        fileobj.seek(0)
        # Trying to rewrite should raise an error...
        self.failUnlessRaises(Exception, OggPage.renumber, fileobj, 1, 10)
        fileobj.seek(0)
        # But the already written data should remain valid,
        pages = [OggPage(fileobj) for i in range(3)]
        self.failUnlessEqual([page.sequence for page in pages], [10, 11, 12])
        # And the garbage that caused the error should be okay too.
        self.failUnlessEqual(fileobj.read(), b"left over data")

    def test_renumber_reread(self):
        try:
            fd, filename = mkstemp(suffix=".ogg")
            os.close(fd)
            shutil.copy(os.path.join("tests", "data", "multipagecomment.ogg"),
                        filename)
            fileobj = open(filename, "rb+")
            OggPage.renumber(fileobj, 1002429366, 20)
            fileobj.close()
            fileobj = open(filename, "rb+")
            OggPage.renumber(fileobj, 1002429366, 0)
            fileobj.close()
        finally:
            try: os.unlink(filename)
            except OSError: pass

    def test_renumber_muxed(self):
        pages = [OggPage() for i in range(10)]
        for seq, page in enumerate(pages[0:1] + pages[2:]):
            page.serial = 0
            page.sequence = seq
        pages[1].serial = 2
        pages[1].sequence = 100
        data = BytesIO(b"".join([page.write() for page in pages]))
        OggPage.renumber(data, 0, 20)
        data.seek(0)
        pages = [OggPage(data) for i in range(10)]
        self.failUnlessEqual(pages[1].serial, 2)
        self.failUnlessEqual(pages[1].sequence, 100)
        pages.pop(1)
        self.failUnlessEqual([page.sequence for page in pages], list(range(20, 29)))

    def test_to_packets(self):
        self.failUnlessEqual(
            [b"foo", b"bar", b"baz"], OggPage.to_packets(self.pages))
        self.pages[0].complete = False
        self.pages[1].continued = True
        self.failUnlessEqual(
            [b"foobar", b"baz"], OggPage.to_packets(self.pages))

    def test_to_packets_mixed_stream(self):
        self.pages[0].serial = 3
        self.failUnlessRaises(ValueError, OggPage.to_packets, self.pages)

    def test_to_packets_missing_sequence(self):
        self.pages[0].sequence = 3
        self.failUnlessRaises(ValueError, OggPage.to_packets, self.pages)

    def test_to_packets_continued(self):
        self.pages[0].continued = True
        self.failUnlessEqual(
            OggPage.to_packets(self.pages), [b"foo", b"bar", b"baz"])

    def test_to_packets_continued_strict(self):
        self.pages[0].continued = True
        self.failUnlessRaises(
            ValueError, OggPage.to_packets, self.pages, strict=True)

    def test_to_packets_strict(self):
        for page in self.pages:
            page.complete = False
        self.failUnlessRaises(
            ValueError, OggPage.to_packets, self.pages, strict=True)

    def test_from_packets_short_enough(self):
        packets = [b"1" * 200, b"2" * 200, b"3" * 200]
        pages = OggPage.from_packets(packets)
        self.failUnlessEqual(OggPage.to_packets(pages), packets)

    def test_from_packets_position(self):
        packets = [b"1" * 100000]
        pages = OggPage.from_packets(packets)
        self.failUnless(len(pages) > 1)
        for page in pages[:-1]:
            self.failUnlessEqual(-1, page.position)
        self.failUnlessEqual(0, pages[-1].position)

    def test_from_packets_long(self):
        packets = [b"1" * 100000, b"2" * 100000, b"3" * 100000]
        pages = OggPage.from_packets(packets)
        self.failIf(pages[0].complete)
        self.failUnless(pages[1].continued)
        self.failUnlessEqual(OggPage.to_packets(pages), packets)

    def test_random_data_roundtrip(self):
        try: random_file = open("/dev/urandom", "rb")
        except (IOError, OSError):
            print("WARNING: Random data round trip test disabled.")
            return
        for i in range(10):
            num_packets = random.randrange(2, 100)
            lengths = [random.randrange(10, 10000)
                       for i in range(num_packets)]
            packets = [random_file.read(l) for l in lengths]
            self.failUnlessEqual(
                packets, OggPage.to_packets(OggPage.from_packets(packets)))

    def test_packet_exactly_255(self):
        page = OggPage()
        page.packets = [b"1" * 255]
        page.complete = False
        page2 = OggPage()
        page2.packets = [b""]
        page2.sequence = 1
        page2.continued = True
        self.failUnlessEqual(
            [b"1" * 255], OggPage.to_packets([page, page2]))

    def test_page_max_size_alone_too_big(self):
        page = OggPage()
        page.packets = [b"1" * 255 * 255]
        page.complete = True
        self.failUnlessRaises(ValueError, page.write)

    def test_page_max_size(self):
        page = OggPage()
        page.packets = [b"1" * 255 * 255]
        page.complete = False
        page2 = OggPage()
        page2.packets = [b""]
        page2.sequence = 1
        page2.continued = True
        self.failUnlessEqual(
            [b"1" * 255 * 255], OggPage.to_packets([page, page2]))

    def test_complete_zero_length(self):
        packets = [b""] * 20
        page = OggPage.from_packets(packets)[0]
        new_page = OggPage(BytesIO(page.write()))
        self.failUnlessEqual(new_page, page)
        self.failUnlessEqual(OggPage.to_packets([new_page]), packets)

    def test_too_many_packets(self):
        packets = [b"1"] * 3000
        pages = OggPage.from_packets(packets)

        for p in pages:
            OggPage.write(p)

        self.failUnless(len(pages) > 3000//255)

    def test_read_max_size(self):
        page = OggPage()
        page.packets = [b"1" * 255 * 255]
        page.complete = False
        page2 = OggPage()
        page2.packets = [b"", b"foo"]
        page2.sequence = 1
        page2.continued = True
        data = page.write() + page2.write()
        fileobj = BytesIO(data)
        self.failUnlessEqual(OggPage(fileobj), page)
        self.failUnlessEqual(OggPage(fileobj), page2)
        self.failUnlessRaises(EOFError, OggPage, fileobj)

    def test_invalid_version(self):
        page = OggPage()
        OggPage(BytesIO(page.write()))
        page.version = 1
        self.failUnlessRaises(OggError, OggPage, BytesIO(page.write()))

    def test_not_enough_lacing(self):
        data = OggPage().write()[:-1] + b"\x10"
        self.failUnlessRaises(OggError, OggPage, BytesIO(data))

    def test_not_enough_data(self):
        data = OggPage().write()[:-1] + b"\x01\x10"
        self.failUnlessRaises(OggError, OggPage, BytesIO(data))

    def test_not_equal(self):
        self.failIfEqual(OggPage(), 12)

    def test_find_last(self):
        pages = [OggPage() for i in range(10)]
        for i, page in enumerate(pages): page.sequence = i
        data = BytesIO(b"".join([page.write() for page in pages]))
        self.failUnlessEqual(
            OggPage.find_last(data, pages[0].serial), pages[-1])

    def test_find_last_really_last(self):
        pages = [OggPage() for i in range(10)]
        pages[-1].last = True
        for i, page in enumerate(pages): page.sequence = i
        data = BytesIO(b"".join([page.write() for page in pages]))
        self.failUnlessEqual(
            OggPage.find_last(data, pages[0].serial), pages[-1])

    def test_find_last_muxed(self):
        pages = [OggPage() for i in range(10)]
        for i, page in enumerate(pages): page.sequence = i
        pages[-2].last = True
        pages[-1].serial = pages[0].serial + 1
        data = BytesIO(b"".join([page.write() for page in pages]))
        self.failUnlessEqual(
            OggPage.find_last(data, pages[0].serial), pages[-2])

    def test_find_last_no_serial(self):
        pages = [OggPage() for i in range(10)]
        for i, page in enumerate(pages): page.sequence = i
        data = BytesIO(b"".join([page.write() for page in pages]))
        self.failUnless(OggPage.find_last(data, pages[0].serial + 1) is None)

    def test_find_last_invalid(self):
        data = BytesIO(b"if you think this is an Ogg, you're crazy")
        self.failUnlessRaises(OggError, OggPage.find_last, data, 0)

    # Disabled because GStreamer will write Oggs with bad data,
    # which we need to make a best guess for.
    #
    #def test_find_last_invalid_sync(self):
    #    data = StringIO("if you think this is an OggS, you're crazy")
    #    self.failUnlessRaises(OggError, OggPage.find_last, data, 0)

    def test_find_last_invalid_sync(self):
        data = BytesIO(b"if you think this is an OggS, you're crazy")
        page = OggPage.find_last(data, 0)
        self.failIf(page)

    def test_crc_py25(self):
        # Make sure page.write can handle both signed/unsigned int
        # return values of crc32.
        # http://code.google.com/p/mutagen/issues/detail?id=63
        # http://docs.python.org/library/zlib.html#zlib.crc32

        import zlib
        old_crc = zlib.crc32
        def zlib_uint(*args):
            return (old_crc(*args) & 0xffffffff)
        def zlib_int(*args):
            return cdata.int_be(cdata.to_uint_be(old_crc(*args) & 0xffffffff))

        try:
            page = OggPage()
            page.packets = [b"abc"]
            zlib.crc32 = zlib_uint
            uint_data = page.write()
            zlib.crc32 = zlib_int
            int_data  = page.write()
        finally:
            zlib.crc32 = old_crc

        self.failUnlessEqual(uint_data, int_data)

    def tearDown(self):
        self.fileobj.close()
add(TOggPage)

# An abstract test class used to derive tests for OggSpeex, OggTheora, etc.
class TOggFileType(TestCase):
    def scan_file(self):
        fileobj = open(self.filename, "rb")
        try:
            try:
                while True:
                    OggPage(fileobj)
            except EOFError:
                pass
        finally:
            fileobj.close()

    def test_pprint_empty(self):
        self.audio.pprint()

    def test_pprint_stuff(self):
        self.test_set_two_tags()
        self.audio.pprint()

    def test_length(self):
        self.failUnlessAlmostEqual(3.7, self.audio.info.length, 1)

    def test_no_tags(self):
        self.failIf(self.audio.tags)
        self.failIf(self.audio.tags is None)

    def test_vendor_safe(self):
        self.audio["vendor"] = "a vendor"
        self.audio.save()
        audio = self.Kind(self.filename)
        self.failUnlessEqual(audio["vendor"], ["a vendor"])

    def test_set_two_tags(self):
        self.audio["foo"] = ["a"]
        self.audio["bar"] = ["b"]
        self.audio.save()
        audio = self.Kind(self.filename)
        self.failUnlessEqual(len(audio.tags.keys()), 2)
        self.failUnlessEqual(audio["foo"], ["a"])
        self.failUnlessEqual(audio["bar"], ["b"])
        self.scan_file()

    def test_save_twice(self):
        self.audio.save()
        self.audio.save()
        self.failUnlessEqual(self.Kind(self.filename).tags, self.audio.tags)
        self.scan_file()

    def test_set_delete(self):
        self.test_set_two_tags()
        self.audio.tags.clear()
        self.audio.save()
        audio = self.Kind(self.filename)
        self.failIf(audio.tags)
        self.scan_file()

    def test_delete(self):
        self.test_set_two_tags()
        self.audio.delete()
        self.failIf(self.audio.tags)
        audio = self.Kind(self.filename)
        self.failIf(audio.tags)

        self.audio["foobar"] = "foobar" * 1000
        self.audio.save()
        audio = self.Kind(self.filename)
        self.failUnlessEqual(self.audio["foobar"], audio["foobar"])

        self.scan_file()

    def test_really_big(self):
        self.audio["foo"] = "foo" * (2**16)
        self.audio["bar"] = "bar" * (2**16)
        self.audio["baz"] = "quux" * (2**16)
        self.audio.save()
        audio = self.Kind(self.filename)
        self.failUnlessEqual(audio["foo"], ["foo" * 2**16])
        self.failUnlessEqual(audio["bar"], ["bar" * 2**16])
        self.failUnlessEqual(audio["baz"], ["quux" * 2**16])
        self.scan_file()

    def test_delete_really_big(self):
        self.audio["foo"] = "foo" * (2**16)
        self.audio["bar"] = "bar" * (2**16)
        self.audio["baz"] = "quux" * (2**16)
        self.audio.save()

        self.audio.delete()
        audio = self.Kind(self.filename)
        self.failIf(audio.tags)
        self.scan_file()

    def test_invalid_open(self):
        self.failUnlessRaises(IOError, self.Kind,
                              os.path.join('tests', 'data', 'xing.mp3'))

    def test_invalid_delete(self):
        self.failUnlessRaises(IOError, self.audio.delete,
                              os.path.join('tests', 'data', 'xing.mp3'))

    def test_invalid_save(self):
        self.failUnlessRaises(IOError, self.audio.save,
                              os.path.join('tests', 'data', 'xing.mp3'))

    def ogg_reference(self, filename):
        self.scan_file()
        if have_ogginfo:
            value = os.system("ogginfo %s > %s 2> %s" % (filename, devnull,
                              devnull))
            self.failIf(value and value != NOTFOUND,
                        "ogginfo failed on %s" % filename)
        if have_oggz_validate:
            if filename.endswith(".opus") and not have_oggz_validate_opus:
                return
            value = os.system(
                "oggz-validate %s > %s" % (filename, devnull))
            self.failIf(value and value != NOTFOUND,
                        "oggz-validate failed on %s" % filename)

    def test_ogg_reference_simple_save(self):
        self.audio.save()
        self.ogg_reference(self.filename)

    def test_ogg_reference_really_big(self):
        self.test_really_big()
        self.audio.save()
        self.ogg_reference(self.filename)

    def test_ogg_reference_delete(self):
        self.audio.delete()
        self.ogg_reference(self.filename)

    def test_ogg_reference_medium_sized(self):
        self.audio["foobar"] = "foobar" * 1000
        self.audio.save()
        self.ogg_reference(self.filename)

    def test_ogg_reference_delete_readd(self):
        self.audio.delete()
        self.audio.tags.clear()
        self.audio["foobar"] = "foobar" * 1000
        self.audio.save()
        self.ogg_reference(self.filename)

    def test_mime_secondary(self):
        self.failUnless('application/ogg' in self.audio.mime)

    def tearDown(self):
        os.unlink(self.filename)

NOTFOUND = os.system("tools/notarealprogram 2> %s" % devnull)

have_ogginfo = True
if os.system("ogginfo 2> %s > %s" % (devnull, devnull)) == NOTFOUND:
    have_ogginfo = False
    print("WARNING: Skipping ogginfo reference tests.")

have_oggz_validate = True
have_oggz_validate_opus = True
if os.system("oggz-validate 2> %s > %s" % (devnull, devnull)) == NOTFOUND:
    have_oggz_validate = False
    print("WARNING: Skipping oggz-validate reference tests.")

else:
    f = os.popen("oggz-validate --version")
    try:
        version_string = f.read()
        version_part = version_string.split()[-1]
        version = tuple(map(int, version_part.split(".")))
        if version <= (0, 9, 9):
            have_oggz_validate_opus = False
            print("WARNING: Skipping oggz-validate reference tests for opus")
    finally:
        f.close()
