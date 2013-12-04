mutagenx
--------
mutagenx is a Python 3 library that aims to reimplement all of the features of
the Python 2 library mutagen, plus a bit extra here and there. The port fixes
things like string/bytes differentiation, archaic Python 2.3 functions,
non-PEP8 styling and use of outdated (non-Python 3) libraries.

Currently in the very early stages of development, but please feel free to have
a look at the latest testing branch and submit any issues you find with it! The
library has been tested on Python 3.3.1, so that's currently the minimum
official version. Please let me know if it works on Python 3.2 and 3.1, but
don't bother with 3.0!

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