# Copyright (c) 2015 Uber Technologies, Inc.
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
import contextlib2
import wrapt
import opentracing
from opentracing.ext import tags as ext_tags
from .. import get_current_span
from ..local_span import func_span

# Utils for instrumenting DB API v2 compatible drivers.
# PEP-249 - https://www.python.org/dev/peps/pep-0249/

_BEGIN = 'begin-trans'
_COMMIT = 'commit'
_ROLLBACK = 'rollback'
_TRANS_TAGS = [_BEGIN, _COMMIT, _ROLLBACK]

NO_ARG = object()


def db_span(sql_statement,
            module_name,
            sql_parameters=None,
            connect_params=None,
            cursor_params=None):
    span = get_current_span()

    @contextlib2.contextmanager
    def empty_ctx_mgr():
        yield None

    if span is None:
        return empty_ctx_mgr()

    statement = sql_statement.strip()
    add_sql_tag = True
    if sql_statement in _TRANS_TAGS:
        operation = sql_statement
        add_sql_tag = False
    else:
        space_idx = statement.find(' ')
        if space_idx == -1:
            operation = ''  # unrecognized format of the query
        else:
            operation = statement[0:space_idx]

    tags = {ext_tags.SPAN_KIND: ext_tags.SPAN_KIND_RPC_CLIENT}
    if add_sql_tag:
        tags['sql'] = statement
    if sql_parameters:
        tags['sql.params'] = sql_parameters
    if connect_params:
        tags['sql.conn'] = connect_params
    if cursor_params:
        tags['sql.cursor'] = cursor_params

    return opentracing.tracer.start_span(
        operation_name='%s:%s' % (module_name, operation),
        parent=span, tags=tags
    )


class ConnectionFactory(object):
    """
    Wraps connect_func of the DB API v2 module by creating a wrapper object
    for the actual connection.
    """

    def __init__(self, connect_func, module_name, conn_wrapper_ctor=None):
        self._connect_func = connect_func
        self._module_name = module_name
        if hasattr(connect_func, '__name__'):
            self._connect_func_name = '%s:%s' % (module_name,
                                                 connect_func.__name__)
        else:
            self._connect_func_name = '%s:%s' % (module_name, connect_func)
        self._wrapper_ctor = conn_wrapper_ctor \
            if conn_wrapper_ctor is not None else ConnectionWrapper

    def __call__(self, *args, **kwargs):
        safe_kwargs = kwargs
        if 'passwd' in kwargs or 'password' in kwargs or 'conv' in kwargs:
            safe_kwargs = dict(kwargs)
            if 'passwd' in safe_kwargs:
                del safe_kwargs['passwd']
            if 'password' in safe_kwargs:
                del safe_kwargs['password']
            if 'conv' in safe_kwargs:  # don't log conversion functions
                del safe_kwargs['conv']
        connect_params = (args, safe_kwargs) if args or safe_kwargs else None
        with func_span(self._connect_func_name):
            return self._wrapper_ctor(
                connection=self._connect_func(*args, **kwargs),
                module_name=self._module_name,
                connect_params=connect_params)


class ConnectionWrapper(wrapt.ObjectProxy):
    def __init__(self, connection, module_name, connect_params):
        super(ConnectionWrapper, self).__init__(wrapped=connection)
        self._module_name = module_name
        self._connect_params = connect_params

    def cursor(self, *args, **kwargs):
        return CursorWrapper(
            cursor=self.__wrapped__.cursor(*args, **kwargs),
            module_name=self._module_name,
            connect_params=self._connect_params,
            cursor_params=(args, kwargs) if args or kwargs else None)

    def begin(self):
        with db_span(sql_statement=_BEGIN, module_name=self._module_name):
            return self.__wrapped__.begin()

    def commit(self):
        with db_span(sql_statement=_COMMIT, module_name=self._module_name):
            return self.__wrapped__.commit()

    def rollback(self):
        with db_span(sql_statement=_ROLLBACK, module_name=self._module_name):
            return self.__wrapped__.rollback()


class ContextManagerConnectionWrapper(ConnectionWrapper):
    """
    Extends ConnectionWrapper by implementing `__enter__` and `__exit__`
    methods of the context manager API, for connections that can be used
    in as context managers to control the transactions, e.g.

    .. code-block:: python

        with MySQLdb.connect(...) as cursor:
            cursor.execute(...)
    """

    def __init__(self, connection, module_name, connect_params):
        super(ContextManagerConnectionWrapper, self).__init__(
            connection=connection,
            module_name=module_name,
            connect_params=connect_params
        )

    def __enter__(self):
        with func_span('%s:begin_transaction' % self._module_name):
            cursor = self.__wrapped__.__enter__()

        return CursorWrapper(cursor=cursor,
                             module_name=self._module_name,
                             connect_params=self._connect_params)

    def __exit__(self, exc, value, tb):
        outcome = _COMMIT if exc is None else _ROLLBACK
        with db_span(sql_statement=outcome, module_name=self._module_name):
            return self.__wrapped__.__exit__(exc, value, tb)


class CursorWrapper(wrapt.ObjectProxy):
    def __init__(self, cursor, module_name,
                 connect_params=None, cursor_params=None):
        super(CursorWrapper, self).__init__(wrapped=cursor)
        self._module_name = module_name
        self._connect_params = connect_params
        self._cursor_params = cursor_params
        # We could also start a span now and then override close() to capture
        # the life time of the cursor

    def execute(self, sql, params=NO_ARG):
        with db_span(sql_statement=sql,
                     sql_parameters=params if params is not NO_ARG else None,
                     module_name=self._module_name,
                     connect_params=self._connect_params,
                     cursor_params=self._cursor_params):
            if params is NO_ARG:
                return self.__wrapped__.execute(sql)
            else:
                return self.__wrapped__.execute(sql, params)

    def executemany(self, sql, seq_of_parameters):
        with db_span(sql_statement=sql, sql_parameters=seq_of_parameters,
                     module_name=self._module_name,
                     connect_params=self._connect_params,
                     cursor_params=self._cursor_params):
            return self.__wrapped__.executemany(sql, seq_of_parameters)

    def callproc(self, proc_name, params=NO_ARG):
        with db_span(sql_statement='sproc:%s' % proc_name,
                     sql_parameters=params if params is not NO_ARG else None,
                     module_name=self._module_name,
                     connect_params=self._connect_params,
                     cursor_params=self._cursor_params):
            if params is NO_ARG:
                return self.__wrapped__.callproc(proc_name)
            else:
                return self.__wrapped__.callproc(proc_name, params)
