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
from builtins import object
import mock
import unittest
import opentracing
from opentracing.mocktracer import MockTracer
from opentracing.scope_managers.tornado import TornadoScopeManager
from opentracing.scope_managers import ThreadLocalScopeManager

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


class PrepareMixin(object):

    scope_manager = None

    def setUp(self):
        super(PrepareMixin, self).setUp()
        self.patcher = mock.patch(
            'opentracing.tracer', MockTracer(self.scope_manager()))
        self.patcher.start()
        self.client = Client()

    def tearDown(self):
        super(PrepareMixin, self).tearDown()
        self.patcher.stop()


class TracedRegularFunctionDecoratorTest(PrepareMixin, unittest.TestCase):

    scope_manager = ThreadLocalScopeManager

    def test_no_arg_decorator(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            child = mock.MagicMock()
            # verify start_child is called with actual function name
            with patch_object(opentracing.tracer, 'start_span',
                              return_value=child) as start_child:
                child.set_tag = mock.MagicMock()
                child.error = mock.MagicMock()
                child.finish = mock.MagicMock()
                r = self.client.regular(123)
                start_child.assert_called_once_with(
                    operation_name='regular',
                    child_of=parent.context,
                    tags=None)
                assert child.set_tag.call_count == 0
                assert child.error.call_count == 0
                assert child.finish.call_count == 1
                assert r == 'oh yeah'

            # verify span.error() is called on exception
            child = mock.MagicMock()
            with patch_object(opentracing.tracer, 'start_span') as start_child:
                start_child.return_value = child
                child.error = mock.MagicMock()
                child.finish = mock.MagicMock()
                with self.assertRaises(AssertionError):
                    self.client.regular(999)
                assert child.log.call_count == 1
                assert child.finish.call_count == 1
        scope.close()

    def test_decorator_with_name(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            child = mock.MagicMock()
            with patch_object(opentracing.tracer, 'start_span',
                              return_value=child) as start_child:
                child.set_tag = mock.MagicMock()
                r = self.client.regular_with_name(123)
                assert r == 'oh yeah'
                start_child.assert_called_once_with(
                    operation_name='some_name',  # overridden name
                    child_of=parent.context,
                    tags=None)
                assert child.set_tag.call_count == 0
            parent.finish()
        scope.close()

    def test_decorator_with_start_hook(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            # verify call_size_tag argument is extracted and added as tag
            child = mock.MagicMock()
            with patch_object(opentracing.tracer, 'start_span') \
                    as start_child:
                start_child.return_value = child
                child.set_tag = mock.MagicMock()
                r = self.client.regular_with_hook(
                    'somewhere', call_site_tag='somewhere')
                assert r == 'oh yeah'
                start_child.assert_called_once_with(
                    operation_name='regular_with_hook',
                    child_of=parent.context,
                    tags=None)
                child.set_tag.assert_called_once_with(
                    'call_site_tag', 'somewhere')
        scope.close()

    def test_no_parent_span(self):

        with patch_object(opentracing.tracer, 'start_span') as start:
            r = self.client.regular(123)
            assert r == 'oh yeah'
            start.assert_called_once_with(
                operation_name='regular', child_of=None, tags=None)

        # verify no new trace or child span is started
        with patch_object(opentracing.tracer, 'start_span') as start:
            r = self.client.regular_require_active_trace(123)
            assert r == 'oh yeah'
            assert start.call_count == 0

    def test_nested_functions(self):
        tracer = opentracing.tracer

        parent = opentracing.tracer.start_span('hello')
        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            self.client.regular_with_nested(123)
            spans = tracer.finished_spans()
            self.assertEqual(len(spans), 3)
            root = spans[2]
            self.assertEqual(root.operation_name, 'regular_with_nested')

            self.assertEqual(spans[0].operation_name, 'regular')
            self.assertEqual(spans[0].parent_id, root.context.span_id)
            self.assertEqual(spans[1].operation_name, 'some_name')
            self.assertEqual(spans[1].parent_id, root.context.span_id)

            # Check parent context has been restored.
            self.assertEqual(tracer.scope_manager.active, scope)

    def test_nested_functions_with_exception(self):
        tracer = opentracing.tracer

        parent = opentracing.tracer.start_span('hello')
        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            # First nested function (`regular`) raises Exception.
            with self.assertRaises(AssertionError):
                self.client.regular_with_nested(999)
            spans = tracer.finished_spans()
            # Second nested function has not been invoked.
            self.assertEqual(len(spans), 2)
            root = spans[1]
            self.assertEqual(root.operation_name, 'regular_with_nested')

            self.assertEqual(spans[0].operation_name, 'regular')
            self.assertEqual(spans[0].parent_id, root.context.span_id)
            self.assertEqual(len(spans[0].tags), 1)
            self.assertEqual(spans[0].tags['error'], 'true')
            self.assertEqual(spans[0].logs[0].key_values['event'], 'exception')

            # Check parent context has been restored.
            self.assertEqual(tracer.scope_manager.active, scope)


class TracedCoroFunctionDecoratorTest(PrepareMixin, AsyncTestCase):

    scope_manager = TornadoScopeManager

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
                child = mock.MagicMock()
                # verify start_child is called with actual function name
                with patch_object(opentracing.tracer, 'start_span',
                                  return_value=child) as start_child:
                    child.set_tag = mock.MagicMock()
                    child.error = mock.MagicMock()
                    child.finish = mock.MagicMock()
                    r = yield self.call(func, 123)
                    start_child.assert_called_once_with(
                        operation_name=func,
                        child_of=parent.context,
                        tags=None)
                    assert child.set_tag.call_count == 0
                    assert child.error.call_count == 0
                    assert child.finish.call_count == 1
                    assert r == 'oh yeah'

                # verify span.error() is called on exception
                child = mock.MagicMock()
                with patch_object(opentracing.tracer, 'start_span') \
                        as start_child:
                    start_child.return_value = child
                    child.error = mock.MagicMock()
                    child.finish = mock.MagicMock()
                    with self.assertRaises(AssertionError):
                        yield self.call(func, 999)
                    assert child.log.call_count == 1
                    assert child.finish.call_count == 1

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_name(self):

        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify start_span is called with overridden function name
            for func in ('regular_with_name', 'coro_with_name', ):
                child = mock.MagicMock()
                with patch_object(opentracing.tracer, 'start_span',
                                  return_value=child) as start_child:
                    child.set_tag = mock.MagicMock()
                    r = yield self.call(func, 123)
                    assert r == 'oh yeah'
                    start_child.assert_called_once_with(
                        operation_name='some_name',  # overridden name
                        child_of=parent.context,
                        tags=None)
                    assert child.set_tag.call_count == 0

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_start_hook(self):

        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify call_size_tag argument is extracted and added as tag
            for func in ('regular_with_hook', 'coro_with_hook', ):
                child = mock.MagicMock()
                with patch_object(opentracing.tracer, 'start_span') \
                        as start_child:
                    start_child.return_value = child
                    child.set_tag = mock.MagicMock()
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
                    assert start.call_count == 0

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
