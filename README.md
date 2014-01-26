mutagenx
--------
mutagenx was originally a project to create a Python 3 library which
implemented all the features of the Python 2 library mutagen. After the
developer of mutagen made some visible progress in making the mutagen
code Python 3 compatible, I decided to do the same, in the other
direction. So, we now have two projects, moving together from opposite
sides of the problem, aiming to achieve a unified codebase.

Once mutagen supports Python 3, I intend to continue with the mutagenx
project, adding various features I think should be in mutagen. I hope it
will act as a testing ground for things that end up going into mutagen.
The first of these improvements will be a common interface for accessing
metadata, to replace the EasyMP3 and EasyMP4 classes with a system which
works for all formats.

This should greatly simplify the majority of metadata editing tasks, and
make it unnecessary to use the format-specific metadata classes. It will
also enable projects such as MusicBrainz Picard to scrap a ton of
metadata specific code.

The rest of this README features text from the original mutagen 1.22 README
file.

What is Mutagen?
----------------
Mutagen is a Python module to handle audio metadata. It supports ASF, FLAC, 
M4A, Monkey's Audio, MP3, Musepack, Ogg Opus, Ogg FLAC, Ogg Speex, Ogg 
Theora, Ogg Vorbis, True Audio, WavPack and OptimFROG audio files. All 
versions of ID3v2 are supported, and all standard ID3v2.4 frames are 
parsed. It can read Xing headers to accurately calculate the bitrate and 
length of MP3s. ID3 and APEv2 tags can be edited regardless of audio 
format. It can also manipulate Ogg streams on an individual packet/page 
level.

Mutagen works on Python 2.6+ / PyPy and has no dependencies outside the 
CPython standard library.


Installing
----------

 $ ./setup.py build
 $ su -c "./setup.py install"


Documentation
-------------

The primary documentation for Mutagen is the doc strings found in
the source code and the sphinx documentation in the docs/ directory.

To build the docs (needs sphinx):

 $ ./setup.py build_sphinx

The tools/ directory contains several useful examples.

The docs are also hosted on readthedocs.org:

 http://mutagen.readthedocs.org


Testing the Module
------------------

To test Mutagen's MP3 reading support, run
 $ tools/mutagen-pony <your top-level MP3 directory here>
Mutagen will try to load all of them, and report any errors.

To look at the tags in files, run
 $ tools/mutagen-inspect filename ...

To run our test suite,
 $ ./setup.py test


Compatibility/Bugs
------------------

See docs/bugs.rst
