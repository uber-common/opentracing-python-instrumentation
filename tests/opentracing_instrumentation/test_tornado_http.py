
import pytest
import tornado.gen
import tornado.web
import tornado.httpserver
import tornado.netutil
import tornado.httpclient
from mock import patch
from opentracing_instrumentation import span_in_stack_context
from opentracing_instrumentation.client_hooks.tornado_http import (
    install_patches,
    reset_patchers
)
from opentracing_instrumentation.http_server import (
    before_request,
    TornadoRequestWrapper
)
from basictracer import BasicTracer
from basictracer.recorder import InMemoryRecorder
import opentracing


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
    t = BasicTracer(recorder=InMemoryRecorder())
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
