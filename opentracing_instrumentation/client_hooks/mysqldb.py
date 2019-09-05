# Copyright (c) 2015,2019 Uber Technologies, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import
from ._dbapi2 import ContextManagerConnectionWrapper as ConnectionWrapper
from ._dbapi2 import ConnectionFactory
from ._patcher import Patcher

# Try to save the original entry points
try:
    import MySQLdb
except ImportError:
    pass
else:
    _MySQLdb_connect = MySQLdb.connect


class MySQLdbPatcher(Patcher):
    applicable = '_MySQLdb_connect' in globals()

    def _install_patches(self):
        factory = ConnectionFactory(connect_func=MySQLdb.connect,
                                    module_name='MySQLdb',
                                    conn_wrapper_ctor=ConnectionWrapper)
        MySQLdb.connect = factory
        if hasattr(MySQLdb, 'Connect'):
            MySQLdb.Connect = factory

    def _reset_patches(self):
        MySQLdb.connect = _MySQLdb_connect
        if hasattr(MySQLdb, 'Connect'):
            MySQLdb.Connect = _MySQLdb_connect


MySQLdbPatcher.configure_hook_module(globals())
