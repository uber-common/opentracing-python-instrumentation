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

import logging

from opentracing import tags


from .. import utils
from ._current_span import current_span_func
from ._patcher import Patcher

log = logging.getLogger(__name__)

try:
    from sqlalchemy.engine import Engine
    from sqlalchemy import event
except ImportError:
    pass


class SQLAlchemyPatcher(Patcher):
    applicable = 'event' in globals()

    def _install_patches(self):
        log.info('Instrumenting SQLAlchemy for tracing')
        event.listen(Engine, 'before_cursor_execute',
                     self.before_cursor_execute)
        event.listen(Engine, 'after_cursor_execute',
                     self.after_cursor_execute)

    def _reset_patches(self):
        event.remove(Engine, 'before_cursor_execute',
                     self.before_cursor_execute)
        event.remove(Engine, 'after_cursor_execute',
                     self.after_cursor_execute)

    @staticmethod
    def before_cursor_execute(conn, cursor, statement, parameters, context,
                              executemany):
        operation = 'SQL'
        statement = statement.strip()
        if statement:
            operation = '%s %s' % (operation,
                                   statement.split(' ', 1)[0].upper())
        span = utils.start_child_span(
            operation_name=operation, parent=current_span_func())
        span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
        span.set_tag(tags.COMPONENT, 'sqlalchemy')
        if conn.engine:
            span.set_tag(tags.DATABASE_TYPE, conn.engine.name)
            span.set_tag(tags.DATABASE_INSTANCE, repr(conn.engine.url))
        if statement:
            span.set_tag(tags.DATABASE_STATEMENT, statement)
        context.opentracing_span = span

    @staticmethod
    def after_cursor_execute(conn, cursor, statement, parameters, context,
                             executemany):
        if hasattr(context, 'opentracing_span') and context.opentracing_span:
            context.opentracing_span.finish()
            context.opentracing_span = None


SQLAlchemyPatcher.configure_hook_module(globals())
