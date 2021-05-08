# Copyright (c) 2018 Uber Technologies, Inc.
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
import six
import sys
import opentracing
import pytest
try:
    import tornado
except ImportError:
    stack_context_support = False
else:
    stack_context_support = tornado.version_info < (6, 0, 0, 0)

collect_ignore = []


if not stack_context_support:
    collect_ignore.extend([
        'opentracing_instrumentation/test_tornado_http.py',
        # XXX: boto3 instrumentation relies on stack_context now
        'opentracing_instrumentation/test_boto3.py',
        'opentracing_instrumentation/test_thread_safe_request_context.py',
        'opentracing_instrumentation/test_tornado_request_context.py',
        'opentracing_instrumentation/test_traced_function_decorator_tornado_coroutines.py',
    ])

if six.PY2:
    collect_ignore.extend([
        'opentracing_instrumentation/test_asyncio_request_context.py',
        'opentracing_instrumentation/test_tornado_asyncio_http.py',
    ])


def _get_tracers(scope_manager=None):
    from basictracer.recorder import InMemoryRecorder
    from basictracer.tracer import BasicTracer

    dummy_tracer = BasicTracer(recorder=InMemoryRecorder(),
                               scope_manager=scope_manager)
    dummy_tracer.register_required_propagators()
    old_tracer = opentracing.tracer
    opentracing.tracer = dummy_tracer

    return old_tracer, dummy_tracer


@pytest.fixture
def tracer():
    old_tracer, dummy_tracer = _get_tracers()
    try:
        yield dummy_tracer
    finally:
        opentracing.tracer = old_tracer


if six.PY3:
    from opentracing.scope_managers.asyncio import AsyncioScopeManager
    asyncio_scope_managers = [AsyncioScopeManager]

    if sys.version_info[:2] >= (3, 7):
        from opentracing.scope_managers.contextvars import \
            ContextVarsScopeManager
        # ContextVarsScopeManager is recommended scope manager for
        # asyncio applications, but it works with python 3.7.x and higher.
        asyncio_scope_managers.append(
            ContextVarsScopeManager
        )

    @pytest.fixture(params=asyncio_scope_managers)
    def asyncio_scope_manager(request):
        return request.param()

if stack_context_support:
    from opentracing.scope_managers.tornado import TornadoScopeManager

    @pytest.fixture
    def thread_safe_tracer():
        old_tracer, dummy_tracer = _get_tracers(TornadoScopeManager())
        try:
            yield dummy_tracer
        finally:
            opentracing.tracer = old_tracer
