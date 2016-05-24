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

import logging

import opentracing
from opentracing.ext import tags as ext_tags
from ..request_context import get_current_span
from ._singleton import singleton

log = logging.getLogger(__name__)


@singleton
def install_patches():
    try:
        from sqlalchemy.engine import Engine
        from sqlalchemy import event
    except ImportError:
        # If SQLAlchemy cannot be imported, then the project we are
        # instrumenting does not depend on it and we do not need to install
        # the SQL hooks.
        return

    log.info('Instrumenting SQL methods for tracing')

    @event.listens_for(Engine, 'before_cursor_execute')
    def before_cursor_execute(conn, cursor, statement, parameters, context,
                              executemany):
        operation = 'SQL'
        statement = statement.strip()
        if statement:
            operation = '%s %s' % (operation,
                                   statement.split(' ', 1)[0].upper())
        span = opentracing.tracer.start_span(
            operation_name=operation, parent=get_current_span())
        span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
        if statement:
            span.set_tag('sql', statement)
        context.opentracing_span = span

    @event.listens_for(Engine, 'after_cursor_execute')
    def after_cursor_execute(conn, cursor, statement, parameters, context,
                             executemany):
        if hasattr(context, 'opentracing_span') and context.opentracing_span:
            context.opentracing_span.finish()
            context.opentracing_span = None
