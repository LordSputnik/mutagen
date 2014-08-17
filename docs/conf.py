# -*- coding: utf-8 -*-

import os
import sys

dir_ = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_)
sys.path.insert(0, os.path.abspath(os.path.join(dir_, "..")))
import mutagenx


extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'ext']
intersphinx_mapping = {'python': ('http://docs.python.org/2.7', None)}
source_suffix = '.rst'
master_doc = 'index'
project = 'mutagenx'
copyright = u'2013, Joe Wreschnig, Michael Urman, Lukáš Lalinský, ' \
            u'Christoph Reiter & others'
version = mutagenx.version_string
release = mutagenx.version_string
exclude_patterns = ['_build']
bug_url_template = "http://bitbucket.org/lazka/mutagen/issue/%s"
