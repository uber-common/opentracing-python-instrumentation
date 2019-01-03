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

import pytest

from basictracer import BasicTracer
from basictracer.recorder import InMemoryRecorder
from mock import Mock, patch
import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager
import tornado.gen
import tornado.web
import tornado.httpserver
import tornado.netutil
import tornado.httpclient

from opentracing_instrumentation import span_in_stack_context
from opentracing_instrumentation.client_hooks.tornado_http import (
    install_patches,
    reset_patchers
)
from opentracing_instrumentation.http_server import (
    TornadoRequestWrapper,
    before_request
)
from opentracing_instrumentation.interceptors import OpenTracingInterceptor


class Handler(tornado.web.RequestHandler):

    def get(self):
        request = TornadoRequestWrapper(self.request)
        with before_request(request, tracer=opentracing.tracer) as span:
            self.write('{:x}'.format(span.context.trace_id))
            self.set_status(200)


@pytest.fixture
def app():
    return tornado.web.Application([
        (r"/", Handler)
    ])


@pytest.yield_fixture
def tornado_http_patch():
    install_patches.__original_func()
    try:
        yield None
    finally:
        reset_patchers()


@pytest.fixture
def tracer():
    t = BasicTracer(
        recorder=InMemoryRecorder(),
        scope_manager=TornadoScopeManager(),
    )
    t.register_required_propagators()
    return t


@pytest.mark.gen_test(run_sync=False)
def test_http_fetch(base_url, http_client, tornado_http_patch, tracer):

    @tornado.gen.coroutine
    def make_downstream_call():
        resp = yield http_client.fetch(base_url)
        raise tornado.gen.Return(resp)

    with patch('opentracing.tracer', tracer):
        assert opentracing.tracer == tracer  # sanity check that patch worked

        span = tracer.start_span('test')
        trace_id = '{:x}'.format(span.context.trace_id)

        with span_in_stack_context(span):
            response = make_downstream_call()
        response = yield response  # cannot yield when in StackContext context

        span.finish()
    assert response.code == 200
    assert response.body.decode('utf-8') == trace_id


@pytest.mark.gen_test(run_sync=False)
def test_http_fetch_with_interceptor(base_url, http_client, tornado_http_patch, tracer):

    @tornado.gen.coroutine
    def make_downstream_call():
        resp = yield http_client.fetch(base_url)
        raise tornado.gen.Return(resp)

    with patch('opentracing.tracer', tracer):
        assert opentracing.tracer == tracer  # sanity check that patch worked

        span = tracer.start_span('test')
        trace_id = '{:x}'.format(span.context.trace_id)

        with patch('opentracing_instrumentation.http_client.ClientInterceptors') as MockClientInterceptors:
            mock_interceptor = Mock(spec=OpenTracingInterceptor)
            MockClientInterceptors.get_interceptors.return_value = [mock_interceptor]

            with span_in_stack_context(span):
                response = make_downstream_call()
            response = yield response  # cannot yield when in StackContext context

            mock_interceptor.process.assert_called_once()
            assert mock_interceptor.process.call_args_list[0][1]['span'].tracer == tracer

            span.finish()

    assert response.code == 200
    assert response.body.decode('utf-8') == trace_id
