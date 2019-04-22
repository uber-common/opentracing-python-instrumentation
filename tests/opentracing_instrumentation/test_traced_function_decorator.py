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
import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager

import tornado.stack_context
import tornado.concurrent
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test
from opentracing_instrumentation import traced_function
from opentracing_instrumentation import span_in_stack_context

patch_object = mock.patch.object


def extract_call_site_tag(span, *_, **kwargs):
    if 'call_site_tag' in kwargs:
        span.set_tag('call_site_tag', kwargs['call_site_tag'])


@mock.patch('opentracing.tracer', opentracing.Tracer(TornadoScopeManager()))
class TracedFuctionDecoratorTest(AsyncTestCase):

    @gen_test
    def test_no_arg_decorator(self):
        class SomeClient(object):
            @traced_function
            @gen.coroutine
            def func1(self, param1):
                assert param1 == 123
                raise tornado.gen.Return('oh yeah')

            @traced_function
            def func1_1(self, param1):
                assert param1 == 123
                return 'oh yeah'  # not a co-routine

        s = SomeClient()
        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # test both co-routine and regular function
            for func in ['func1', 'func1_1']:
                child = mock.MagicMock()
                # verify start_child is called with actual function name
                with patch_object(opentracing.tracer, 'start_span',
                                  return_value=child) as start_child:
                    child.set_tag = mock.MagicMock()
                    child.error = mock.MagicMock()
                    child.finish = mock.MagicMock()
                    if func == 'func1':
                        r = yield s.func1(123)
                    else:
                        r = s.func1_1(123)
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
                        if func == 'func1':
                            yield s.func1(999)
                        else:
                            s.func1_1(999)
                    assert child.log.call_count == 1
                    assert child.finish.call_count == 1

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_name(self):
        class SomeClient(object):
            @traced_function(name='func2_modified')
            @gen.coroutine
            def func2(self, param1):
                assert param1 == 123
                raise tornado.gen.Return('oh yeah')

        s = SomeClient()
        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify start_span is called with overridden function name
            child = mock.MagicMock()
            with patch_object(opentracing.tracer, 'start_span',
                              return_value=child) as start_child:
                child.set_tag = mock.MagicMock()
                r = yield s.func2(123)
                assert r == 'oh yeah'
                start_child.assert_called_once_with(
                    operation_name='func2_modified',  # overridden name
                    child_of=parent.context,
                    tags=None)
                assert child.set_tag.call_count == 0

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_decorator_with_start_hook(self):
        class SomeClient(object):
            @traced_function(on_start=extract_call_site_tag)
            def func3(self, param1, param2=None, call_site_tag=None):
                assert param1 == call_site_tag
                assert param2 is None
                return 'oh yeah'  # not a co-routine

        s = SomeClient()
        parent = opentracing.tracer.start_span('hello')

        @gen.coroutine
        def run():
            # verify call_size_tag argument is extracted and added as tag
            child = mock.MagicMock()
            with patch_object(opentracing.tracer, 'start_span') \
                    as start_child:
                start_child.return_value = child
                child.set_tag = mock.MagicMock()
                r = s.func3('somewhere', call_site_tag='somewhere')
                assert r == 'oh yeah'
                start_child.assert_called_once_with(
                    operation_name='func3',
                    child_of=parent.context,
                    tags=None)
                child.set_tag.assert_called_once_with(
                    'call_site_tag', 'somewhere')

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=parent, coro=run)

    @gen_test
    def test_no_parent_span(self):
        class SomeClient(object):
            @traced_function
            def func4(self, param1):
                assert param1 == 123
                return 'oh yeah'  # not a co-routine

        class SomeClient2(object):
            @traced_function(require_active_trace=True)
            def func5(self, param1):
                assert param1 == 123
                return 'oh yeah'  # not a co-routine

        s = SomeClient()
        s2 = SomeClient2()

        @gen.coroutine
        def run():
            # verify a new trace is started
            with patch_object(opentracing.tracer, 'start_span') as start:
                r = s.func4(123)
                assert r == 'oh yeah'
                start.assert_called_once_with(
                    operation_name='func4', child_of=None, tags=None)

            # verify no new trace or child span is started
            with patch_object(opentracing.tracer, 'start_span') as start:
                r = s2.func5(123)
                assert r == 'oh yeah'
                assert start.call_count == 0

            raise tornado.gen.Return(1)

        yield run_coroutine_with_span(span=None, coro=run)


def run_coroutine_with_span(span, coro, *args, **kwargs):
    """Wrap the execution of a Tornado coroutine func in a tracing span.

    This makes the span available through the get_current_span() function.

    :param span: The tracing span to expose.
    :param func: Co-routine to execute in the scope of tracing span.
    :param args: Positional args to func, if any.
    :param kwargs: Keyword args to func, if any.
    """
    with span_in_stack_context(span=span):
        return coro(*args, **kwargs)
