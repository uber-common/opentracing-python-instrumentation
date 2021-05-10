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

import mock
import pytest

import opentracing
from opentracing.mocktracer import MockTracer
from opentracing.scope_managers.tornado import TornadoScopeManager

import tornado.stack_context
from tornado.concurrent import is_future
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test
from opentracing_instrumentation import traced_function
from opentracing_instrumentation import span_in_stack_context

patch_object = mock.patch.object


def extract_call_site_tag(span, *_, **kwargs):
    if 'call_site_tag' in kwargs:
        span.set_tag('call_site_tag', kwargs['call_site_tag'])


class Client(object):

    def _func(self, param):
        assert param == 123
        return 'oh yeah'

    @traced_function
    def regular(self, param):
        return self._func(param)

    @traced_function(name='some_name')
    def regular_with_name(self, param):
        return self._func(param)

    @traced_function(on_start=extract_call_site_tag)
    def regular_with_hook(self, param1, param2=None, call_site_tag=None):
        assert param1 == call_site_tag
        assert param2 is None
        return 'oh yeah'

    @traced_function(require_active_trace=True)
    def regular_require_active_trace(self, param):
        return self._func(param)

    @traced_function()
    def regular_with_nested(self, param):
        self.regular(param)
        self.regular_with_name(param)

    def _coro(self, param):
        return tornado.gen.Return(self._func(param))

    @traced_function
    @gen.coroutine
    def coro(self, param):
        raise self._coro(param)

    @traced_function(name='some_name')
    @gen.coroutine
    def coro_with_name(self, param):
        raise self._coro(param)

    @traced_function(on_start=extract_call_site_tag)
    @gen.coroutine
    def coro_with_hook(self, param1, param2=None, call_site_tag=None):
        assert param1 == call_site_tag
        assert param2 is None
        raise tornado.gen.Return('oh yeah')

    @traced_function(require_active_trace=True)
    def coro_require_active_trace(self, param):
        raise self._coro(param)


class TracedCoroFunctionDecoratorTest(AsyncTestCase):

    scope_manager = TornadoScopeManager

    def setUp(self):
        super(TracedCoroFunctionDecoratorTest, self).setUp()
        self.patcher = mock.patch(
            'opentracing.tracer', MockTracer(self.scope_manager()))
        self.patcher.start()
        self.client = Client()

    def tearDown(self):
        super(TracedCoroFunctionDecoratorTest, self).tearDown()
        self.patcher.stop()

    @gen.coroutine
    def call(self, method, *args, **kwargs):
        """
        Execute synchronous or asynchronous method of client and return the
        result.
        """
        result = getattr(self.client, method)(*args, **kwargs)
        if is_future(result):
            result = yield result
        raise tornado.gen.Return(result)

    @gen_test
    def test_no_arg_decorator(self):

        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # test both co-routine and regular function
            for func in ('regular', 'coro', ):
                child = mock.Mock()
                # verify start_child is called with actual function name
                with patch_object(opentracing.tracer, 'start_span',
                                  return_value=child) as start_child:
                    r = yield self.call(func, 123)
                    start_child.assert_called_once_with(
                        operation_name=func,
                        child_of=parent.context,
                        tags=None)
                    child.set_tag.assert_not_called()
                    child.error.assert_not_called()
                    child.finish.assert_called_once()
                    assert r == 'oh yeah'

                # verify span.error() is called on exception
                child = mock.Mock()
                with patch_object(opentracing.tracer, 'start_span') \
                        as start_child:
                    start_child.return_value = child
                    with pytest.raises(AssertionError):
                        yield self.call(func, 999)
                    child.log.assert_called_once()
                    child.finish.assert_called_once()

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_name(self):

        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify start_span is called with overridden function name
            for func in ('regular_with_name', 'coro_with_name', ):
                child = mock.Mock()
                with patch_object(opentracing.tracer, 'start_span',
                                  return_value=child) as start_child:
                    r = yield self.call(func, 123)
                    assert r == 'oh yeah'
                    start_child.assert_called_once_with(
                        operation_name='some_name',  # overridden name
                        child_of=parent.context,
                        tags=None)
                    child.set_tag.assert_not_called()

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_start_hook(self):

        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify call_size_tag argument is extracted and added as tag
            for func in ('regular_with_hook', 'coro_with_hook', ):
                child = mock.Mock()
                with patch_object(opentracing.tracer, 'start_span') \
                        as start_child:
                    start_child.return_value = child
                    r = yield self.call(
                        func, 'somewhere', call_site_tag='somewhere')
                    assert r == 'oh yeah'
                    start_child.assert_called_once_with(
                        operation_name=func,
                        child_of=parent.context,
                        tags=None)
                    child.set_tag.assert_called_once_with(
                        'call_site_tag', 'somewhere')

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_no_parent_span(self):

        @gen.coroutine
        def run():
            # verify a new trace is started
            for func1, func2 in (('regular', 'regular_require_active_trace'),
                                 ('coro', 'coro_require_active_trace')):
                with patch_object(opentracing.tracer, 'start_span') as start:
                    r = yield self.call(func1, 123)
                    assert r == 'oh yeah'
                    start.assert_called_once_with(
                        operation_name=func1, child_of=None, tags=None)

                # verify no new trace or child span is started
                with patch_object(opentracing.tracer, 'start_span') as start:
                    r = yield self.call(func2, 123)
                    assert r == 'oh yeah'
                    start.assert_not_called()

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=None, coro=run)


def run_coroutine_with_span(span, coro, *args, **kwargs):
    """Wrap the execution of a Tornado coroutine func in a tracing span.

    This makes the span available through the get_current_span() function.

    :param span: The tracing span to expose.
    :param coro: Co-routine to execute in the scope of tracing span.
    :param args: Positional args to func, if any.
    :param kwargs: Keyword args to func, if any.
    """
    with span_in_stack_context(span=span):
        return coro(*args, **kwargs)
