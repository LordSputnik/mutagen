import os
import glob

from tests import add
from tests.test_tools import _TTools


class TMutagenInspect(_TTools):

    TOOL_NAME = 'mutagen-inspect'

    def test_basic(self):
        base = os.path.join('tests', 'data')
        self.paths = glob.glob(os.path.join(base, 'empty*'))
        self.paths += glob.glob(os.path.join(base, 'silence-*'))

        for path in self.paths:
            res, out = self.call(path)
            self.failIf(res)
            self.failUnless(out.strip())
            self.failIf("Unknown file type" in out)
            self.failIf("Errno" in out)

add(TMutagenInspect)
