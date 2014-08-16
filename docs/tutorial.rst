Mutagen Tutorial
----------------

There are two different ways to load files in Mutagen, but both provide 
similar interfaces. The first is the :class:`Metadata <mutagen.Metadata>` 
API, which deals only in metadata tags. The second is the :class:`FileType 
<mutagen.FileType>` API, which is a superset of the :class:`mutagen 
<mutagen.Metadata>` API, and contains information about the audio data 
itself.

Both Metadata and FileType objects present a dict-like interface to
edit tags. FileType objects also have an 'info' attribute that gives
information about the song length, as well as per-format
information. In addition, both support the load(filename),
save(filename), and delete(filename) instance methods; if no filename
is given to save or delete, the last loaded filename is used.

This tutorial is only an outline of Mutagen's API. For the full
details, you should read the docstrings (pydoc mutagen) or source
code.

Easy Examples
^^^^^^^^^^^^^

The following code loads a file, sets its title, prints all tag data,
then saves the file, first on a FLAC file, then on a Musepack
file. The code is almost identical.

::

      from mutagen.flac import FLAC
      audio = FLAC("example.flac")
      audio["title"] = "An example"
      audio.pprint()
      audio.save()

::

      from mutagen.apev2 import APEv2
      audio = APEv2("example.mpc")
      audio["title"] = "An example"
      audio.pprint()
      audio.save()

The following example gets the length and bitrate of an MP3 file::

    from mutagen.mp3 import MP3
    audio = MP3("example.mp3")
    print audio.info.length, audio.info.bitrate

The following deletes an ID3 tag from an MP3 file::

    from mutagen.id3 import ID3
    audio = ID3("example.mp3")
    audio.delete()

Hard Examples: ID3
^^^^^^^^^^^^^^^^^^

Unlike Vorbis, FLAC, and APEv2 comments, ID3 data is highly
structured. Because of this, the interface for ID3 tags is very
different from the APEv2 or Vorbis/FLAC interface. For example, to set
the title of an ID3 tag, you need to do the following::

    from mutagen.id3 import ID3, TIT2
    audio = ID3("example.mp3")
    audio.add(TIT2(encoding=3, text=u"An example"))
    audio.save()

If you use the ID3 module, you should familiarize yourself with how
ID3v2 tags are stored, by reading the the details of the ID3v2
standard at http://www.id3.org/develop.html.


Easy ID3
^^^^^^^^

Since reading standards is hard, Mutagen also provides a simpler ID3
interface.

::

    from mutagen.easyid3 import EasyID3
    audio = EasyID3("example.mp3")
    audio["title"] = u"An example"
    audio.save()

Because of the simpler interface, only a few keys can be edited by
EasyID3; to see them, use::

    from mutagen.easyid3 import EasyID3
    print EasyID3.valid_keys.keys()

By default, mutagen.mp3.MP3 uses the real ID3 class. You can make it
use EasyID3 as follows::

    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
    audio = MP3("example.mp3", ID3=EasyID3)
    audio.pprint()

Unicode
^^^^^^^

Mutagen has full Unicode support for all formats. When you assign text
strings, we strongly recommend using Python unicode objects rather
than str objects. If you use str objects, Mutagen will assume they are
in UTF-8.

(This does not apply to strings that must be interpreted as bytes, for
example filenames. Those should be passed as str objectss, and will
remain str objects within Mutagen.)

Multiple Values
^^^^^^^^^^^^^^^

Most tag formats support multiple values for each key, so when you
access then (e.g. ``audio["title"]``) you will get a list of strings
rather than a single one (``[u"An example"]`` rather than ``u"An example"``).
Similarly, you can assign a list of strings rather than a single one.
