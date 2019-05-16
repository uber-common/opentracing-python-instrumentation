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
from opentracing_instrumentation import http_server
from opentracing_instrumentation import config

import pytest


@pytest.mark.parametrize('with_peer_tags,with_context', [
    (True, True),
    (False, True),
    (True, False),
    (False, False),
])
def test_middleware(with_peer_tags, with_context):
    """
    Tests http_server.before_request call

    :param with_peer_tags: whether Request object exposes peer properties
    :param with_context: whether the inbound request contains tracing context
    :return:
    """
    request = mock.MagicMock()
    request.method = 'GET'
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
    if with_context:
        span_ctx = mock.MagicMock()
    else:
        span_ctx = None
    p_extract = mock.patch.object(tracer, 'extract', return_value=span_ctx)
    span = mock.MagicMock()
    p_start_span = mock.patch.object(tracer, 'start_span', return_value=span)
    with p_extract as extract_call, p_start_span as start_span_call:
        span2 = http_server.before_request(request=request, tracer=tracer)
        assert span == span2
        extract_call.assert_called_with(
            format=Format.HTTP_HEADERS, carrier={})
        expected_tags = {
            'http.method': 'GET',
            'http.url': 'http://localhost:12345/test',
            'span.kind': 'server',
        }
        if with_peer_tags:
            expected_tags.update({
                'peer.service': 'test_middleware',
                'span.kind': 'server',
                'peer.ipv4': 'localhost',
                'peer.port': 12345,
            })
        start_span_call.assert_called_with(
            operation_name='my-test',
            tags=expected_tags,
            child_of=span_ctx
        )


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
