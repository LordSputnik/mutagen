#!/usr/bin/env python
# Copyright 2005-2009,2011 Joe Wreschnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

import glob
import os
import shutil
import sys
import subprocess
import tarfile

from imp import reload
from distutils.core import setup, Command
from distutils import dir_util

from distutils.command.clean import clean as distutils_clean
from distutils.command.sdist import sdist


class clean(distutils_clean):
    def run(self):
        # In addition to what the normal clean run does, remove pyc
        # and pyo and backup files from the source tree.
        distutils_clean.run(self)

        def should_remove(filename):
            if (filename.lower()[-4:] in [".pyc", ".pyo"] or
                    filename.endswith("~") or
                    (filename.startswith("#") and filename.endswith("#"))):
                return True
            else:
                return False
        for pathname, dirs, files in os.walk(os.path.dirname(__file__)):
            for filename in files:
                if should_remove(filename):
                    try:
                        os.unlink(os.path.join(pathname, filename))
                    except EnvironmentError as err:
                        print(str(err))

        try:
            os.unlink("MANIFEST")
        except OSError:
            pass

        for base in ["coverage", "build", "dist"]:
            path = os.path.join(os.path.dirname(__file__), base)
            if os.path.isdir(path):
                shutil.rmtree(path)


class distcheck(sdist):

    def _check_manifest(self):
        assert self.get_archive_files()

        # make sure MANIFEST.in includes all tracked files
        if subprocess.call(["hg", "status"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE) == 0:
            # contains the packaged files after run() is finished
            included_files = self.filelist.files
            assert included_files

            process = subprocess.Popen(["hg", "locate"],
                                       stdout=subprocess.PIPE)
            out, err = process.communicate()
            assert process.returncode == 0

            tracked_files = out.splitlines()
            for ignore in [".hgignore", ".hgtags"]:
                tracked_files.remove(ignore)

            assert not set(tracked_files) - set(included_files), \
                "Not all tracked files included in tarball, update MANIFEST.in"

    def _check_dist(self):
        assert self.get_archive_files()

        distcheck_dir = os.path.join(self.dist_dir, "distcheck")
        if os.path.exists(distcheck_dir):
            dir_util.remove_tree(distcheck_dir)
        self.mkpath(distcheck_dir)

        archive = self.get_archive_files()[0]
        tfile = tarfile.open(archive, "r:gz")
        tfile.extractall(distcheck_dir)
        tfile.close()

        name = self.distribution.get_fullname()
        extract_dir =  os.path.join(distcheck_dir, name)

        old_pwd = os.getcwd()
        os.chdir(extract_dir)
        self.spawn([sys.executable, "setup.py", "test"])
        self.spawn([sys.executable, "setup.py", "build"])
        self.spawn([sys.executable, "setup.py", "build_sphinx"])
        self.spawn([sys.executable, "setup.py", "install",
                    "--prefix", "../prefix", "--record", "../log.txt"])
        os.environ["LC_ALL"] = "C"
        self.spawn([sys.executable, "setup.py", "test", "--quick"])
        os.chdir(old_pwd)

    def run(self):
        sdist.run(self)
        self._check_manifest()
        self._check_dist()


class build_sphinx(Command):
    description = "build sphinx documentation"
    user_options = [
        ("build-dir=", "d", "build directory"),
    ]

    def initialize_options(self):
        self.build_dir = None

    def finalize_options(self):
        self.build_dir = self.build_dir or "build"

    def run(self):
        docs = "docs"
        target = os.path.join(self.build_dir, "sphinx")
        self.spawn(["sphinx-build", "-b", "html", "-n", docs, target])


class test_cmd(Command):
    description = "run automated tests"
    user_options = [
        ("to-run=", None, "list of tests to run (default all)"),
        ("quick", None, "don't run slow mmap-failing tests"),
    ]

    def initialize_options(self):
        self.to_run = []
        self.quick = False

    def finalize_options(self):
        if self.to_run:
            self.to_run = self.to_run.split(",")

    def run(self):
        import tests

        count, failures = tests.unit(self.to_run, self.quick)
        if failures:
            print("%d out of %d failed" % (failures, count))
            raise SystemExit("Test failures are listed above.")
        else:
            print("All tests passed")


class coverage_cmd(Command):
    description = "generate test coverage data"
    user_options = [
        ("quick", None, "don't run slow mmap-failing tests"),
    ]

    def initialize_options(self):
        self.quick = None

    def finalize_options(self):
        self.quick = bool(self.quick)

    def run(self):
        import trace
        tracer = trace.Trace(
            count=True, trace=False,
            ignoredirs=[sys.prefix, sys.exec_prefix])

        def run_tests():
            import mutagenx
            import mutagenx._util
            reload(mutagenx._util)
            reload(mutagenx)
            cmd = self.reinitialize_command("test")
            cmd.quick = self.quick
            cmd.ensure_finalized()
            cmd.run()

        tracer.runfunc(run_tests)
        results = tracer.results()
        coverage = os.path.join(os.path.dirname(__file__), "coverage")
        results.write_results(show_missing=True, coverdir=coverage)

        for match in glob.glob(os.path.join(coverage, "[!m]*.cover")):
            os.unlink(match)

        try:
            os.unlink(os.path.join(coverage, "..setup.cover"))
        except OSError:
            pass

        total_lines = 0
        bad_lines = 0
        for filename in glob.glob(os.path.join(coverage, "*.cover")):
            lines = open(filename, "rU").readlines()
            total_lines += len(lines)
            bad_lines += len(
                [line for line in lines if
                 (line.startswith(">>>>>>") and
                  "finally:" not in line and '"""' not in line)])
        pct = 100.0 * (total_lines - bad_lines) / float(total_lines)
        print("Coverage data written to %s (%d/%d, %0.2f%%)" % (
              coverage, total_lines - bad_lines, total_lines, pct))

        if pct < 98.66:
            raise SystemExit(
                "Coverage percentage went down; write more tests.")
        if pct > 98.7:
            raise SystemExit("Coverage percentage went up; change setup.py.")

if os.name == "posix":
    data_files = [('share/man/man1', glob.glob("man/*.1"))]
else:
    data_files = []

if __name__ == "__main__":
    from mutagenx import version_string

    cmd_classes = {
        "clean": clean,
        "test": test_cmd,
        "coverage": coverage_cmd,
        "distcheck": distcheck,
        "build_sphinx": build_sphinx,
    }

    setup(cmdclass=cmd_classes,
          name="mutagenx", version=version_string,
          url="https://github.com/LordSputnik/mutagen",
          description="read and write audio tags for many formats in Python 3",
          author="Ben Ockmore",
          author_email="ben.sput@gmail.com",
          license="GNU GPL v2",
          classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Topic :: Multimedia :: Sound/Audio'
          ],
          packages=["mutagenx"],
          data_files=data_files,
          scripts=[os.path.join("tools", name) for name in [
            "mid3iconv",
            "mid3v2",
            "moggsplit",
            "mutagen-inspect",
            "mutagen-pony",
          ]],
          long_description="""\
A fork of the mutagen package, modified to support Python 3.3+. I
take no credit for the original mutagen - the copyright for that is
owned by the original developers. This package isn't currently
compatible with Python 2.x, but I am working with the mutagen
developers to make these two projects converge. Once this happens, I'll
close this project and start working on improving mutagen itself.

From the original package description:

\"Mutagen is a Python module to handle audio metadata. It supports ASF,
FLAC, M4A, Monkey's Audio, MP3, Musepack, Ogg FLAC, Ogg Speex, Ogg
Theora, Ogg Vorbis, True Audio, WavPack and OptimFROG audio files. All
versions of ID3v2 are supported, and all standard ID3v2.4 frames are
parsed. It can read Xing headers to accurately calculate the bitrate
and length of MP3s. ID3 and APEv2 tags can be edited regardless of
audio format. It can also manipulate Ogg streams on an individual
packet/page level.\"
"""
    )
