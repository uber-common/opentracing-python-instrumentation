# Copyright (c) 2016 Uber Technologies, Inc.
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

from mock import patch

import opentracing
from opentracing.scope_managers import ThreadLocalScopeManager
from opentracing_instrumentation.local_span import func_span
from opentracing_instrumentation.client_hooks._dbapi2 import db_span, _COMMIT
from opentracing_instrumentation.client_hooks._singleton import singleton
from opentracing_instrumentation import span_in_context


@patch('opentracing.tracer', new=opentracing.Tracer(ThreadLocalScopeManager()))
def test_func_span_without_parent():
    with func_span('test', require_active_trace=False) as span:
        assert span is not None
    with func_span('test', require_active_trace=True) as span:
        assert span is None


def test_func_span():
    tracer = opentracing.tracer
    span = tracer.start_span(operation_name='parent')
    with span_in_context(span=span):
        with func_span('test') as child_span:
            assert span is child_span
        with func_span('test', tags={'x': 'y'}) as child_span:
            assert span is child_span


@patch('opentracing.tracer', new=opentracing.Tracer(ThreadLocalScopeManager()))
def test_db_span_without_parent():
    with db_span('test', 'MySQLdb') as span:
        assert span is None


def test_db_span():
    tracer = opentracing.tracer
    span = tracer.start_span(operation_name='parent')
    with span_in_context(span=span):
        with db_span(_COMMIT, 'MySQLdb') as child_span:
            assert span is child_span
        with db_span('select * from X', 'MySQLdb') as child_span:
            assert span is child_span


def test_singleton():
    data = [1]

    @singleton
    def increment():
        data[0] += 1

    @singleton
    def increment2(func=None):
        data[0] += 1
        if func:
            func()

    increment()
    assert data[0] == 2
    increment()
    assert data[0] == 2
    increment.__original_func()
    assert data[0] == 3

    # recursive call does increment twice
    increment2(func=lambda: increment2())
    assert data[0] == 5
    # but not on the second round
    increment2(func=lambda: increment2())
    assert data[0] == 5
