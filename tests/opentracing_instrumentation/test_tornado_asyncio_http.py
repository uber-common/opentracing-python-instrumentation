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
import tornado.web
import tornado.httpserver
import tornado.netutil
import tornado.httpclient

from opentracing_instrumentation.client_hooks.tornado_http import (
    install_patches,
    reset_patchers
)
from opentracing_instrumentation.http_server import (
    TornadoRequestWrapper,
    before_request
)
from opentracing_instrumentation.interceptors import OpenTracingInterceptor


pytestmark = pytest.mark.gen_test


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


@pytest.fixture
def tornado_http_patch():
    install_patches.__original_func()
    try:
        yield None
    finally:
        reset_patchers()


@pytest.fixture
def tracer(asyncio_scope_manager):
    t = BasicTracer(
        recorder=InMemoryRecorder(),
        scope_manager=asyncio_scope_manager,
    )
    t.register_required_propagators()
    return t


async def test_http_fetch(base_url, http_client, tornado_http_patch, tracer):

    with patch('opentracing.tracer', tracer):
        assert opentracing.tracer == tracer

        with tracer.start_active_span('test') as scope:
            span = scope.span
            trace_id = '{:x}'.format(span.context.trace_id)

            response = await http_client.fetch(base_url)

    assert response.code == 200
    assert response.body.decode('utf-8') == trace_id


async def test_http_fetch_with_interceptor(base_url, http_client, tornado_http_patch, tracer):

    with patch('opentracing.tracer', tracer):
        assert opentracing.tracer == tracer  # sanity check that patch worked

        with tracer.start_active_span('test') as scope:
            span = scope.span
            trace_id = '{:x}'.format(span.context.trace_id)

            with patch('opentracing_instrumentation.http_client.ClientInterceptors') as MockClientInterceptors:
                mock_interceptor = Mock(spec=OpenTracingInterceptor)
                MockClientInterceptors.get_interceptors.return_value = [mock_interceptor]

                response = await http_client.fetch(base_url)

                mock_interceptor.process.assert_called_once()
                assert mock_interceptor.process.call_args_list[0][1]['span'].tracer == tracer

    assert response.code == 200
    assert response.body.decode('utf-8') == trace_id
