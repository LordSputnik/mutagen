Compatibility / Bugs
====================

Mutagen writes ID3v2.4 tags which id3lib cannot read. If you enable
ID3v1 tag saving (pass v1=2 to ID3.save), id3lib will read those.

iTunes has a bug in its handling of very large ID3 tags (such as tags
that contain an attached picture). Mutagen can read tags from iTunes,
but iTunes may not be able to read tags written by Quod Libet.

Mutagen has had several bugs in correct sync-safe parsing and writing
of data length flags in ID3 tags. This will only affect files with
very large or compressed ID3 frames (e.g. APIC). As of 1.10 we believe
them all to be fixed.

Prior to 1.10.1, Mutagen wrote an incorrect flag for APEv2 tags that
claimed they did not have footers. This has been fixed, however it
means that all APEv2 tags written before 1.10.1 are corrupt.

Prior to 1.16, the MP4 cover atom used a .format attribute to indicate
the image format (JPEG/PNG). Python 2.6 added a str.format method
which conflicts with this. 1.17 provides .imageformat when running on
any version, and still provides .format when running on a version
before 2.6.

Mutagen 1.18 moved EasyID3FileType to mutagen.easyid3, rather than
mutagen.id3, which was used in 1.17. Keeping in mutagen.id3 caused
circular import problems. To import EasyID3FileType correctly in 1.17
and 1.18 or later::

    import mutagen.id3
    try:
        from mutagen.easyid3 import EasyID3FileType
    except ImportError:
        # Mutagen 1.17.
        from mutagen.id3 import EasyID3FileType

Mutagen 1.19 made it possible for POPM to have no 'count'
attribute. Previously, files that generated POPM frames of this type
would fail to load at all.

When given date frames less than four characters long (which are
already outside the ID3v2 specification), Mutagen 1.20 and earlier
would write invalid ID3v1 tags that were too short. Mutagen 1.21 will
parse these and fix them if it finds them while saving.
