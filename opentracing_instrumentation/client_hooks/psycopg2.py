# Copyright (c) 2017 Uber Technologies, Inc.
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
from ._singleton import singleton

# Try to save the original entry points
try:
    import psycopg2
except ImportError:  # pragma: no cover
    pass
else:
    _psycopg2_connect = psycopg2.connect


@singleton
def install_patches():
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        return

    factory = ConnectionFactory(connect_func=psycopg2.connect,
                                module_name='psycopg2',
                                conn_wrapper_ctor=ConnectionWrapper)
    setattr(psycopg2, 'connect', factory)
    if hasattr(psycopg2, 'Connect'):
        setattr(psycopg2, 'Connect', factory)
