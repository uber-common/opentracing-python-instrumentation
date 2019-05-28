# Copyright (c) 2017,2019 Uber Technologies, Inc.
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
from psycopg2.sql import Composable
from ._dbapi2 import ContextManagerConnectionWrapper as ConnectionWrapper
from ._dbapi2 import ConnectionFactory, CursorWrapper, NO_ARG
from ._singleton import singleton

# Try to save the original entry points
try:
    import psycopg2.extensions
except ImportError:  # pragma: no cover
    pass
else:
    _psycopg2_connect = psycopg2.connect
    _psycopg2_extensions_register_type = psycopg2.extensions.register_type
    _psycopg2_extensions_quote_ident = psycopg2.extensions.quote_ident


class Psycopg2CursorWrapper(CursorWrapper):
    """
    Psycopg2 accept not only string as sql statement, but instances of
    ``psycopg2.sql.Composable`` that should be represented as string before the
    executing.
    """
    def execute(self, sql, params=NO_ARG):
        if isinstance(sql, Composable):
            sql = sql.as_string(self)
        return super(Psycopg2CursorWrapper, self).execute(sql, params)

    def executemany(self, sql, seq_of_parameters):
        if isinstance(sql, Composable):
            sql = sql.as_string(self)
        return super(Psycopg2CursorWrapper, self).executemany(
            sql, seq_of_parameters
        )


@singleton
def install_patches():
    if 'psycopg2' not in globals():
        return

    # the following original methods checks a type of the conn_or_curs
    # and it doesn't accept wrappers
    def register_type(obj, conn_or_curs=None):
        if isinstance(conn_or_curs, (ConnectionWrapper, CursorWrapper)):
            conn_or_curs = conn_or_curs.__wrapped__
        _psycopg2_extensions_register_type(obj, conn_or_curs)

    def quote_ident(string, scope):
        if isinstance(scope, (ConnectionWrapper, CursorWrapper)):
            scope = scope.__wrapped__
        return _psycopg2_extensions_quote_ident(string, scope)

    psycopg2.extensions.register_type = register_type
    psycopg2.extensions.quote_ident = quote_ident

    factory = ConnectionFactory(connect_func=psycopg2.connect,
                                module_name='psycopg2',
                                conn_wrapper_ctor=ConnectionWrapper,
                                cursor_wrapper=Psycopg2CursorWrapper)
    setattr(psycopg2, 'connect', factory)
    if hasattr(psycopg2, 'Connect'):
        setattr(psycopg2, 'Connect', factory)
