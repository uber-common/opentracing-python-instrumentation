# Copyright (c) 2017 Uber Technologies, Inc.
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

from mock import patch
import pytest

from opentracing_instrumentation.client_hooks import install_client_interceptors
from opentracing_instrumentation.interceptors import OpenTracingInterceptor


class TestClientInterceptor(OpenTracingInterceptor):

    def process(self, request, span):
        pass


def Any(cls):

    class Any(cls):

        def __eq__(self, other):
            return isinstance(other, cls)

    return Any()


def test_install_client_interceptors_non_list_arg():
    with pytest.raises(ValueError):
        install_client_interceptors('abc')


def test_install_client_interceptors():
    # TODO: can this path be obtained programmatically?
    path_to_interceptor = ('tests.opentracing_instrumentation.'
                           'test_install_client_hooks.TestClientInterceptor')
    with patch('opentracing_instrumentation.http_client.ClientInterceptors') as MockClientInterceptors:
        install_client_interceptors([path_to_interceptor])

    MockClientInterceptors.append.assert_called_once_with(Any(TestClientInterceptor))
