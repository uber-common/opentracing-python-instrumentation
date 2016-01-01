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
import functools

import tornado.stack_context
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test
from opentracing_instrumentation.trace_context import get_current_span
from opentracing_instrumentation.trace_context import TraceContextManager


class TornadoTraceContextTest(AsyncTestCase):

    @gen_test
    def test_http_fetch(self):
        span1 = 'Bender is great!'
        span2 = 'Fry is dumb!'

        @gen.coroutine
        def check(span_to_check):
            assert get_current_span() == span_to_check

        with self.assertRaises(Exception):  # passing mismatching spans
            yield run_coroutine_with_span(span1, check, span2)

        @gen.coroutine
        def nested(nested_span_to_check, span_to_check):
            yield run_coroutine_with_span(span1, check, nested_span_to_check)
            assert get_current_span() == span_to_check

        with self.assertRaises(Exception):  # passing mismatching spans
            yield run_coroutine_with_span(span2, nested, span1, span1)
        with self.assertRaises(Exception):  # passing mismatching spans
            yield run_coroutine_with_span(span2, nested, span2, span2)

        # successful case
        yield run_coroutine_with_span(span2, nested, span1, span2)

    def test_no_span(self):
        ctx = TraceContextManager(span='x')
        assert ctx._span == 'x'
        assert TraceContextManager.current_span() is None


def run_coroutine_with_span(span, func, *args, **kwargs):
    """Wrap the execution of a Tornado coroutine func in a tracing span.

    This makes the span available through the get_current_span() function.

    :param span: The tracing span to expose.
    :param func: Co-routine to execute in the scope of tracing span.
    :param args: Positional args to func, if any.
    :param kwargs: Keyword args to func, if any.
    """
    mgr = functools.partial(TraceContextManager, span)
    with tornado.stack_context.StackContext(mgr):
        return func(*args, **kwargs)
