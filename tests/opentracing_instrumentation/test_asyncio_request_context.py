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
import pytest
import asyncio
import opentracing
from opentracing.scope_managers.asyncio import AsyncioScopeManager
from opentracing_instrumentation.request_context import (
    get_current_span,
    span_in_context,
)
from opentracing.mocktracer.tracer import MockTracer


pytestmark = pytest.mark.asyncio


@pytest.fixture
def tracer(asyncio_scope_manager):
    new_tracer = MockTracer(scope_manager=asyncio_scope_manager)
    tracer = opentracing.global_tracer()
    opentracing.set_global_tracer(new_tracer)
    yield new_tracer
    opentracing.set_global_tracer(tracer)


async def test_basic(tracer):

    assert opentracing.global_tracer() == tracer

    async def coro():
        span = tracer.start_span(operation_name='foobar')
        with span_in_context(span):
            span.finish()
        return span

    assert get_current_span() is None

    span = await coro()

    assert get_current_span() is None

    assert tracer.finished_spans() == [span]


async def test_nested(tracer):

    assert opentracing.global_tracer() == tracer

    async def coro(name, finish):
        span = tracer.start_span(operation_name=name)
        with span_in_context(span):
            if finish:
                span.finish()
        return span

    assert get_current_span() == None

    with tracer.start_active_span(operation_name='foo') as scope:
        outer_span = scope.span

        # Nested span in first coroutine has been finished.
        span_bar = await coro('bar', finish=True)
        # In second coroutine nested span still alive.
        span_baz = await coro('baz', finish=False)
        # Nevertheless we returning to outer scope and must get outer span as
        # current span.
        assert get_current_span() == outer_span

    # 2 of 3 span are finished.
    assert tracer.finished_spans() == [span_bar, outer_span]

    assert span_bar.parent_id == outer_span.context.span_id

    # baz is not finished but got outer_span as parent.
    assert not span_baz.finished
    assert span_baz.parent_id == outer_span.context.span_id


async def test_nested_tasks(tracer, asyncio_scope_manager):

    assert opentracing.global_tracer() == tracer

    async def coro(name, finish):
        span = tracer.start_span(operation_name=name)
        with span_in_context(span):
            if finish:
                span.finish()
        return span

    assert get_current_span() == None

    with tracer.start_active_span(operation_name='foo') as scope:
        outer_span = scope.span

        # Nested span in first task will finished.
        span_bar = asyncio.ensure_future(coro('bar', finish=True))
        # In second coroutine task span still alive.
        span_baz = asyncio.ensure_future(coro('baz', finish=False))
        # Nevertheless we returning to outer scope and must get outer span as
        # current span.
        assert get_current_span() == outer_span

    span_bar = await span_bar
    span_baz = await span_baz

    # 2 of 3 span are finished.
    # Note that outer span will be finished first ("bar" goes into event loop).
    assert tracer.finished_spans() == [outer_span, span_bar]

    # baz is not finished
    assert not span_baz.finished

    if isinstance(asyncio_scope_manager, AsyncioScopeManager):
        # AsyncioScopeManager doesn't support context propagation into
        # tasks. See https://github.com/opentracing/opentracing-python/blob/master/opentracing/scope_managers/asyncio.py#L37
        assert span_bar.parent_id is None
        assert span_baz.parent_id is None
    else:
        assert span_bar.parent_id == outer_span.context.span_id
        assert span_baz.parent_id == outer_span.context.span_id
