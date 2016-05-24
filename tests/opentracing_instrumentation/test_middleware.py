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
import unittest
import mock
from opentracing_instrumentation.http_server import TornadoRequestWrapper
import tornado.httputil
import opentracing
from opentracing import Format
from opentracing.ext import tags
from opentracing_instrumentation import http_server
from opentracing_instrumentation import config

import pytest


@pytest.mark.parametrize('with_peer_tags', [True, False])
def test_middleware(with_peer_tags):
    request = mock.MagicMock()
    request.full_url = 'http://localhost:12345/test'
    request.operation = 'my-test'
    if with_peer_tags:
        request.remote_ip = 'localhost'
        request.remote_port = 12345
        request.caller_name = 'test_middleware'
    else:
        request.remote_ip = None
        request.remote_port = None
        request.caller_name = None

    tracer = opentracing.tracer
    span = mock.MagicMock()
    with mock.patch.object(tracer, 'start_span',
                           return_value=span) as start_trace, \
            mock.patch.object(tracer, 'join',
                              return_value=None):
        span2 = http_server.before_request(request=request, tracer=tracer)
        assert span == span2
        start_trace.assert_called_with(operation_name='my-test')
        span.set_tag.assert_any_call('http.url', request.full_url)
        if with_peer_tags:
            span.set_tag.assert_any_call(tags.PEER_HOST_IPV4, 'localhost')
            span.set_tag.assert_any_call(tags.PEER_PORT, 12345)
            span.set_tag.assert_any_call(tags.PEER_SERVICE, 'test_middleware')

    # now test server when it looks like there is a trace in the headers
    span = mock.MagicMock()
    with mock.patch.object(tracer, 'join',
                           return_value=span) as join_trace:
        span2 = http_server.before_request(request=request, tracer=tracer)
        assert span == span2
        join_trace.assert_called_with(operation_name='my-test',
                                      format=Format.TEXT_MAP,
                                      carrier=request.headers)
        span.set_tag.assert_any_call('http.url', request.full_url)
        if with_peer_tags:
            span.set_tag.assert_any_call(tags.PEER_HOST_IPV4, 'localhost')
            span.set_tag.assert_any_call(tags.PEER_PORT, 12345)
            span.set_tag.assert_any_call(tags.PEER_SERVICE, 'test_middleware')


class AbstractRequestWrapperTest(unittest.TestCase):
    def test_not_implemented(self):
        request = http_server.AbstractRequestWrapper()
        self.assertRaises(NotImplementedError, lambda: request.full_url)
        self.assertRaises(NotImplementedError, lambda: request.headers)
        self.assertRaises(NotImplementedError, lambda: request.method)
        self.assertRaises(NotImplementedError, lambda: request.remote_ip)
        assert request.remote_port is None
        assert request.server_port is None

    def test_operation(self):
        request = http_server.AbstractRequestWrapper()
        with mock.patch('opentracing_instrumentation.http_server'
                        '.AbstractRequestWrapper.method',
                        new_callable=mock.PropertyMock) as method:
            method.return_value = 'my-test-method'
            assert request.operation == 'my-test-method'

    def test_caller_name(self):
        request = http_server.AbstractRequestWrapper()
        assert request.caller_name is None
        with mock.patch.object(config.CONFIG, 'caller_name_headers',
                               ['caller']):
            headers = tornado.httputil.HTTPHeaders({'caller': 'test-caller'})
            with mock.patch('opentracing_instrumentation.http_server'
                            '.AbstractRequestWrapper.headers',
                            new_callable=mock.PropertyMock) as headers_prop:
                headers_prop.return_value = headers
                assert request.caller_name == 'test-caller'
                headers_prop.return_value = {}
                assert request.caller_name is None


class TornadoRequestWrapperTest(unittest.TestCase):
    def test_all(self):
        request = mock.MagicMock()
        request.full_url = mock.MagicMock(return_value='sample full url')
        request.headers = {'a': 'b'}
        request.method = 'sample method'
        request.remote_ip = 'sample remote ip'
        wrapper = TornadoRequestWrapper(request)
        assert 'sample full url' == wrapper.full_url
        assert {'a': 'b'} == wrapper.headers
        assert 'sample method' == wrapper.method
        assert 'sample remote ip' == wrapper.remote_ip


def find_tag(span, key):
    for tag in span.tags:
        if key == tag.key:
            return tag.value
    return None
