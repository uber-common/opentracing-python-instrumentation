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
from tornado.httputil import HTTPHeaders
import opentracing
from opentracing_instrumentation.client_hooks import urllib2 as urllib2_hooks
from opentracing_instrumentation.config import CONFIG
from opentracing_instrumentation.request_context import RequestContextManager


@contextlib.contextmanager
def install_hooks():
    old_opener = urllib2._opener
    old_callee_headers = CONFIG.callee_name_headers
    old_endpoint_headers = CONFIG.callee_endpoint_headers

    urllib2_hooks.install_patches.__original_func()
    CONFIG.callee_name_headers = ['Remote-Loc']
    CONFIG.callee_endpoint_headers = ['Remote-Op']

    yield

    urllib2.install_opener(old_opener)
    CONFIG.callee_name_headers = old_callee_headers
    CONFIG.callee_endpoint_headers = old_endpoint_headers


def test_http_root():
    do_test(scheme='http', root_span=True)


def test_https_root():
    do_test(scheme='https', root_span=True)


def test_http_child():
    do_test(scheme='http', root_span=False)


def test_https_child():
    do_test(scheme='https', root_span=False)


def do_test(scheme='http', root_span=True):
    with install_hooks():
        _do_test(scheme=scheme, root_span=root_span)


def _do_test(scheme='http', root_span=True):
    request = urllib2.Request('%s://localhost:9777/proxy' % scheme,
                              headers={'Remote-LOC': 'New New York',
                                       'Remote-Op': 'antiquing'})

    class Response(object):
        def __init__(self):
            self.code = 200
            self.msg = ''

        def info(self):
            return None

    span = mock.MagicMock()
    span.set_tag = mock.MagicMock()
    span.finish = mock.MagicMock()

    headers = {'TRACE-ID': '123'}

    def inject(span, format, carrier):
        carrier['TRACE-ID'] = '123'

    with mock.patch('urllib2.AbstractHTTPHandler.do_open',
                    return_value=Response()), \
            mock.patch.object(opentracing.tracer, 'inject',
                              side_effect=inject):

        if root_span:
            with mock.patch.object(opentracing.tracer,
                                   'start_span',
                                   return_value=span) as ctx:
                resp = urllib2.urlopen(request)
                ctx.assert_called_once_with(
                    operation_name='GET:antiquing', parent=None)
                # TODO check client=True
        else:
            current_span = mock.MagicMock()
            with mock.patch.object(opentracing.tracer,
                                   'start_span',
                                   return_value=span) as start_child:
                with RequestContextManager(current_span):
                    resp = urllib2.urlopen(request)
                    start_child.assert_called_once_with(
                        operation_name='GET:antiquing',
                        parent=current_span)

    assert resp is not None
    assert span.set_tag.call_count >= 2
    assert span.__enter__.call_count == 1
    assert span.__exit__.call_count == 1, 'ensure finish() was called'

    # verify trace-id was correctly injected into headers
    norm_headers = HTTPHeaders(request.headers)
    assert norm_headers.get('trace-id') == '123'
