API Notes
=========

This file documents deprecated parts of the Mutagen API. New code
should not use these parts, and several months after being added here,
they may be removed. Note that we do not intend to ever deprecate or
remove large portions of the API. All of these are corner cases that
arose from when Mutagen was still part of Quod Libet, and should never
be encountered in normal use.

General
-------

FileType constructors require a filename. However, the 'delete' and
'save' methods should not be called with one.

No modules, types, functions, or attributes beginning with '_' are
considered public API. These can and do change drastically between
Mutagen versions. This is the standard Python way of marking a
function protected or private.

Mutagen's goal is to adhere as closely as possible to published
specifications. If you try to abuse Mutagen to make it write things in
a non-standard fashion, Joe will update Mutagen to break your
program. If you want to do nonstandard things, write your own broken
library.

FLAC
----

The 'vc' attribute predates the FileType API and has been deprecated
since Mutagen 0.9; this also applies to the 'add_vc' method. The
standard 'tags' attribute and 'add_tags' method should be used
instead.

ID3
---

None of the Spec objects are considered part of the public API.

APEv2
-----

Python 2.5 forced an API change in the APEv2 reading code. Some things
which were case-insensitive are now case-sensitive. For example,
given::

    tag = APEv2()
    tag["Foo"] = "Bar"
    print "foo" in tag.keys()

Mutagen 1.7.1 and earlier would print "True", as the keys were a str
subclass that compared case-insensitively. However, Mutagen 1.8 and
above print "False", as the keys are normal strings.

::

    print "foo" in tag

Still prints "True", however, as __getitem__, __delitem__, and
__setitem__ (and so any operations on the dict itself) remain
case-insensitive.

As of 1.10.1, Mutagen no longer allows non-ASCII keys in APEv2
tags. This is in accordance with the APEv2 standard. A KeyError is
raised if you try.

M4A
---

mutagen.m4a is deprecated. You should use mutagen.mp4 instead.

MP4
---

There is no MPEG-4 iTunes metadata standard. Mutagen's features are
known to lead to problems in other implementations. For example, FAAD
will crash when reading a file with multiple "tmpo" atoms. iTunes
itself is our main compatibility target.

Python 2.6 forced an API change in the MP4 (and M4A) code, by
introducing the str.format instance method. Previously the cover image
format was available via the .format attribute; it is now available
via the .imageformat attribute. On versions of Python prior to 2.6, it
is also still available as .format.
