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

import urllib2
import contextlib

import mock
import pytest
from tornado.httputil import HTTPHeaders
import opentracing
from opentracing_instrumentation.client_hooks import urllib2 as urllib2_hooks
from opentracing_instrumentation.config import CONFIG
from opentracing_instrumentation.request_context import span_in_context


@pytest.yield_fixture
def install_hooks():
    old_opener = urllib2._opener
    old_callee_headers = CONFIG.callee_name_headers
    old_endpoint_headers = CONFIG.callee_endpoint_headers

    urllib2_hooks.install_patches.__original_func()
    CONFIG.callee_name_headers = ['Remote-Loc']
    CONFIG.callee_endpoint_headers = ['Remote-Op']

    try:
        yield
    except:
        urllib2.install_opener(old_opener)
        CONFIG.callee_name_headers = old_callee_headers
        CONFIG.callee_endpoint_headers = old_endpoint_headers


@pytest.mark.parametrize('scheme,root_span', [
    ('http', True),
    ('http', False),
    ('https', True),
    ('https', False),
])
def test_urllib2(scheme, root_span, install_hooks):
    request = urllib2.Request('%s://localhost:9777/proxy' % scheme,
                              headers={'Remote-LOC': 'New New York',
                                       'Remote-Op': 'antiquing'})

    class Response(object):
        def __init__(self):
            self.code = 200
            self.msg = ''

        def info(self):
            return None

    if root_span:
        root_span = mock.MagicMock()
        root_span.context = mock.MagicMock()
        root_span.finish = mock.MagicMock()
        root_span.__exit__ = mock.MagicMock()
    else:
        root_span = None

    span = mock.MagicMock()
    span.set_tag = mock.MagicMock()
    span.finish = mock.MagicMock()

    def inject(span_context, format, carrier):
        carrier['TRACE-ID'] = '123'

    p_do_open = mock.patch('urllib2.AbstractHTTPHandler.do_open',
                           return_value=Response())
    p_start_span = mock.patch.object(opentracing.tracer, 'start_span',
                                     return_value=span)
    p_inject = mock.patch.object(opentracing.tracer, 'inject',
                                 side_effect=inject)
    p_current_span = span_in_context(span=root_span)

    with p_do_open, p_start_span as start_call, p_inject, p_current_span:
        resp = urllib2.urlopen(request)
        expected_references = None
        if root_span:
            expected_references = opentracing.child_of(root_span.context)
        start_call.assert_called_once_with(
            operation_name='GET:antiquing',
            references=expected_references,
            tags=None,
        )
    assert resp is not None
    span.set_tag.assert_any_call('span.kind', 'client')
    assert span.__enter__.call_count == 1
    assert span.__exit__.call_count == 1, 'ensure finish() was called'
    if root_span:
        assert root_span.__exit__.call_count == 0, 'do not finish root span'

    # verify trace-id was correctly injected into headers
    norm_headers = HTTPHeaders(request.headers)
    assert norm_headers.get('trace-id') == '123'
