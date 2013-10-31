import os
import sys
from io import BytesIO

from tests import TestCase


def get_var(tool_name, entry="main"):
    tool_path = os.path.join("tools", tool_name)
    env = {}
    execfile(tool_path, env)
    return env[entry]


class _TTools(TestCase):
    TOOL_NAME = None

    def setUp(self):
        self._main = get_var(self.TOOL_NAME)

    def get_var(self, name):
        return get_var(self.TOOL_NAME, name)

    def call(self, *args):
        for arg in args:
            assert isinstance(arg, str)
        old_stdout = sys.stdout
        try:
            out = BytesIO()
            sys.stdout = out
            try:
                ret = self._main([self.TOOL_NAME] + list(args))
            except SystemExit as e:
                ret = e.code
            ret = ret or 0
            return (ret,  out.getvalue())
        finally:
            sys.stdout = old_stdout

    def tearDown(self):
        del self._main
