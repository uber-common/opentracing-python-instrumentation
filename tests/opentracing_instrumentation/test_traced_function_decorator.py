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
import unittest

import opentracing
from opentracing.mocktracer import MockTracer
from opentracing.scope_managers import ThreadLocalScopeManager

from opentracing_instrumentation import traced_function

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


class TracedRegularFunctionDecoratorTest(unittest.TestCase):

    scope_manager = ThreadLocalScopeManager

    def setUp(self):
        super(TracedRegularFunctionDecoratorTest, self).setUp()
        self.patcher = mock.patch(
            'opentracing.tracer', MockTracer(self.scope_manager()))
        self.patcher.start()
        self.client = Client()

    def tearDown(self):
        super(TracedRegularFunctionDecoratorTest, self).tearDown()
        self.patcher.stop()

    def test_no_arg_decorator(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            child = mock.Mock()
            # verify start_child is called with actual function name
            with patch_object(opentracing.tracer, 'start_span',
                              return_value=child) as start_child:
                r = self.client.regular(123)
                start_child.assert_called_once_with(
                    operation_name='regular',
                    child_of=parent.context,
                    tags=None)
                child.set_tag.assert_not_called()
                child.error.assert_not_called()
                child.finish.assert_called_once()
                assert r == 'oh yeah'

            # verify span.error() is called on exception
            child = mock.Mock()
            with patch_object(opentracing.tracer, 'start_span') as start_child:
                start_child.return_value = child
                with pytest.raises(AssertionError):
                    self.client.regular(999)
                child.log.assert_called_once()
                child.finish.assert_called_once()
        scope.close()

    def test_decorator_with_name(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            child = mock.Mock()
            with patch_object(opentracing.tracer, 'start_span',
                              return_value=child) as start_child:
                r = self.client.regular_with_name(123)
                assert r == 'oh yeah'
                start_child.assert_called_once_with(
                    operation_name='some_name',  # overridden name
                    child_of=parent.context,
                    tags=None)
                child.set_tag.assert_not_called()
            parent.finish()
        scope.close()

    def test_decorator_with_start_hook(self):

        parent = opentracing.tracer.start_span('hello')

        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            # verify call_size_tag argument is extracted and added as tag
            child = mock.Mock()
            with patch_object(opentracing.tracer, 'start_span') as start_child:
                start_child.return_value = child
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
            start.assert_not_called()

    def test_nested_functions(self):
        tracer = opentracing.tracer

        parent = opentracing.tracer.start_span('hello')
        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            self.client.regular_with_nested(123)
            spans = tracer.finished_spans()
            assert len(spans) == 3
            root = spans[2]
            assert root.operation_name == 'regular_with_nested'

            assert spans[0].operation_name == 'regular'
            assert spans[0].parent_id == root.context.span_id
            assert spans[1].operation_name == 'some_name'
            assert spans[1].parent_id == root.context.span_id

            # Check parent context has been restored.
            assert tracer.scope_manager.active is scope

    def test_nested_functions_with_exception(self):
        tracer = opentracing.tracer

        parent = opentracing.tracer.start_span('hello')
        with opentracing.tracer.scope_manager.activate(parent, True) as scope:
            # First nested function (`regular`) raises Exception.
            with pytest.raises(AssertionError):
                self.client.regular_with_nested(999)
            spans = tracer.finished_spans()
            # Second nested function has not been invoked.
            assert len(spans) == 2
            root = spans[1]
            assert root.operation_name == 'regular_with_nested'

            assert spans[0].operation_name == 'regular'
            assert spans[0].parent_id == root.context.span_id
            assert len(spans[0].tags) == 1
            assert spans[0].tags['error'] == 'true'
            assert spans[0].logs[0].key_values['event'] == 'exception'

            # Check parent context has been restored.
            assert tracer.scope_manager.active is scope
