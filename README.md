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

Please see the README.rst file for the current README included in mutagen.