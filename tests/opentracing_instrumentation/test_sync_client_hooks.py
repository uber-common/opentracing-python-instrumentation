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

from future import standard_library
standard_library.install_aliases()

import mock
import pytest
from tornado.httputil import HTTPHeaders
import opentracing
from basictracer import BasicTracer
from basictracer.recorder import InMemoryRecorder
from opentracing_instrumentation.client_hooks import urllib2 as urllib2_hooks
from opentracing_instrumentation.config import CONFIG
from opentracing_instrumentation.request_context import span_in_context

import urllib.request
import six
if six.PY2:
    import urllib2


@pytest.yield_fixture
def install_hooks(request):
    urllibver = request.getfixturevalue('urllibver')

    if urllibver == 'urllib2':
        if six.PY3:
            try:
                yield None
            except:
                return
        module = urllib2
    else:
        module = urllib.request

    old_opener = module._opener
    old_callee_headers = CONFIG.callee_name_headers
    old_endpoint_headers = CONFIG.callee_endpoint_headers

    urllib2_hooks.install_patches.__original_func()
    CONFIG.callee_name_headers = ['Remote-Loc']
    CONFIG.callee_endpoint_headers = ['Remote-Op']

    try:
        yield module
    except:
        module.install_opener(old_opener)
        CONFIG.callee_name_headers = old_callee_headers
        CONFIG.callee_endpoint_headers = old_endpoint_headers


@pytest.yield_fixture
def tracer():
    t = BasicTracer(recorder=InMemoryRecorder())
    t.register_required_propagators()
    old_tracer = opentracing.tracer
    opentracing.tracer = t

    try:
        yield t
    except:
        opentracing.tracer = old_tracer


@pytest.mark.parametrize('urllibver,scheme,root_span', [
    ('urllib2', 'http', True),
    ('urllib2', 'http', False),
    ('urllib2', 'https', True),
    ('urllib2', 'https', False),
    ('urllib.request', 'http', True),
    ('urllib.request', 'http', False),
    ('urllib.request', 'https', True),
    ('urllib.request', 'https', False),
])
def test_urllib2(urllibver, scheme, root_span, install_hooks, tracer):

    module = install_hooks

    if module is None:
        pytest.skip('Skipping %s on Py3' % urllibver)

    class Response(object):
        def __init__(self):
            self.code = 200
            self.msg = ''

        def info(self):
            return None

    if root_span:
        root_span = tracer.start_span('root-span')
    else:
        root_span = None

    # ideally we should have started a test server and tested with real HTTP
    # request, but doing that for https is more difficult, so we mock the
    # request sending part.
    if urllibver == 'urllib2':
        p_do_open = mock.patch(
            'urllib2.AbstractHTTPHandler.do_open', return_value=Response()
        )
    else:
        cls = module.AbstractHTTPHandler
        p_do_open = mock._patch_object(
            cls, 'do_open', return_value=Response()
        )

    with p_do_open, span_in_context(span=root_span):
        request = module.Request(
            '%s://localhost:9777/proxy' % scheme,
            headers={
                'Remote-LOC': 'New New York',
                'Remote-Op': 'antiquing'
            })
        resp = module.urlopen(request)

    assert resp.code == 200
    assert len(tracer.recorder.get_spans()) == 1

    span = tracer.recorder.get_spans()[0]
    assert span.tags.get('span.kind') == 'client'

    # verify trace-id was correctly injected into headers
    # we wrap the headers to avoid having to deal with upper/lower case
    norm_headers = HTTPHeaders(request.headers)
    trace_id_header = norm_headers.get('ot-tracer-traceid')
    assert trace_id_header == '%x' % span.context.trace_id
