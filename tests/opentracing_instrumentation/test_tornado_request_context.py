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

import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager
from opentracing_instrumentation.request_context import (
    get_current_span,
    span_in_stack_context,
    RequestContext,
    RequestContextManager,
)
from mock import patch
from tornado import gen
from tornado import stack_context
from tornado.testing import AsyncTestCase, gen_test


@patch('opentracing.tracer', new=opentracing.Tracer(TornadoScopeManager()))
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
        ctx = RequestContextManager(context=RequestContext(span='x'))
        assert ctx._context.span == 'x'
        assert RequestContextManager.current_context() is None

    def test_backwards_compatible(self):
        span = opentracing.tracer.start_span(operation_name='test')
        mgr = RequestContextManager(span)  # span as positional arg
        assert mgr._context.span == span
        mgr = RequestContextManager(context=span)  # span context arg
        assert mgr._context.span == span
        mgr = RequestContextManager(span=span)  # span as span arg
        assert mgr._context.span == span

    @gen_test
    def test_request_context_manager_backwards_compatible(self):
        span = opentracing.tracer.start_span(operation_name='test')

        @gen.coroutine
        def check():
            assert get_current_span() == span

        # Bypass ScopeManager/span_in_stack_context() and use
        # RequestContextManager directly.
        def run_coroutine(span, coro):
            def mgr():
                return RequestContextManager(span)

            with stack_context.StackContext(mgr):
                return coro()

        yield run_coroutine(span, check)


def run_coroutine_with_span(span, coro, *args, **kwargs):
    """Wrap the execution of a Tornado coroutine func in a tracing span.

    This makes the span available through the get_current_span() function.

    :param span: The tracing span to expose.
    :param coro: Co-routine to execute in the scope of tracing span.
    :param args: Positional args to func, if any.
    :param kwargs: Keyword args to func, if any.
    """
    with span_in_stack_context(span):
        return coro(*args, **kwargs)
