#!/usr/bin/env python3

import glob
import os
import shutil
import sys

from imp import reload
from distutils.core import setup, Command

from distutils.command.clean import clean as distutils_clean
from distutils.command.sdist import sdist as distutils_sdist


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
            for filename in (f for f in files if should_remove(f)):
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


class sdist(distutils_sdist):
    def run(self):
        self.run_command("test")

        distutils_sdist.run(self)

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

        if tests.unit(self.to_run, self.quick):
            raise SystemExit("Test failures are listed above.")


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
        "sdist": sdist,
        "build_sphinx": build_sphinx,
    }

    setup(cmdclass=cmd_classes,
          name="mutagenx", version=version_string,
          url="https://github.com/LordSputnik/mutagen",
          description="read and write audio tags for many formats in Python 3",
          author="Ben Ockmore",
          author_email="ben.sput@gmail.com",
          license="GNU GPL v2",
          packages=["mutagenx"],
          data_files=data_files,
          scripts=glob.glob("tools/m*[!~]"),
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
