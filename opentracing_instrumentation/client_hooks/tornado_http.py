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
from builtins import object
import functools
import logging
import urllib.parse

from tornado.httputil import HTTPHeaders

from opentracing.ext import tags
from opentracing_instrumentation.http_client import AbstractRequestWrapper
from opentracing_instrumentation.http_client import before_http_request
from opentracing_instrumentation.http_client import split_host_and_port
from opentracing_instrumentation import get_current_span
from ._singleton import singleton

logger = logging.getLogger(__name__)


# Try to save the original types for Tornado
try:
    import tornado.simple_httpclient
except ImportError:  # pragma: no cover
    pass
else:
    _SimpleAsyncHTTPClient_fetch_impl = \
        tornado.simple_httpclient.SimpleAsyncHTTPClient.fetch_impl


try:
    import tornado.curl_httpclient
except ImportError:  # pragma: no cover
    pass
else:
    _CurlAsyncHTTPClient_fetch_impl = \
        tornado.curl_httpclient.CurlAsyncHTTPClient.fetch_impl


class TracedPatcherBuilder(object):

    def patch(self):
        for obj, attr, repl in self._tornado():
            self._build_patcher(obj, attr, repl)

    @staticmethod
    def _build_patcher(obj, patched_attribute, replacement):
        if not hasattr(obj, patched_attribute):
            return
        return setattr(obj, patched_attribute, replacement)

    @staticmethod
    def _tornado():
        try:
            import tornado.simple_httpclient as simple
        except ImportError:  # pragma: no cover
            pass
        else:
            new_fetch_impl = traced_fetch_impl(
                _SimpleAsyncHTTPClient_fetch_impl
            )
            yield simple.SimpleAsyncHTTPClient, 'fetch_impl', new_fetch_impl

        try:
            import tornado.curl_httpclient as curl
        except ImportError:  # pragma: no cover
            pass
        else:
            new_fetch_impl = traced_fetch_impl(
                _CurlAsyncHTTPClient_fetch_impl
            )
            yield curl.CurlAsyncHTTPClient, 'fetch_impl', new_fetch_impl


@singleton
def install_patches():
    builder = TracedPatcherBuilder()
    builder.patch()


def reset_patchers():
    try:
        import tornado.simple_httpclient as simple
    except ImportError:  # pragma: no cover
        pass
    else:
        setattr(
            simple.SimpleAsyncHTTPClient,
            'fetch_impl',
            _SimpleAsyncHTTPClient_fetch_impl,
        )
    try:
        import tornado.curl_httpclient as curl
    except ImportError:  # pragma: no cover
        pass
    else:
        setattr(
            curl.CurlAsyncHTTPClient,
            'fetch_impl',
            _CurlAsyncHTTPClient_fetch_impl,
        )


def traced_fetch_impl(real_fetch_impl):

    @functools.wraps(real_fetch_impl)
    def new_fetch_impl(self, request, callback):
        request_wrapper = TornadoRequestWrapper(request=request)
        span = before_http_request(request=request_wrapper,
                                   current_span_extractor=get_current_span)

        def new_callback(response):
            if hasattr(response, 'code') and response.code:
                span.set_tag(tags.HTTP_STATUS_CODE, '%s' % response.code)
            if hasattr(response, 'error') and response.error:
                span.set_tag(tags.ERROR, True)
                span.log(event=tags.ERROR, payload='%s' % response.error)
            span.finish()
            return callback(response)

        real_fetch_impl(self, request, new_callback)

    return new_fetch_impl


class TornadoRequestWrapper(AbstractRequestWrapper):

    def __init__(self, request):
        self.request = request
        self._norm_headers = None

    def add_header(self, key, value):
        self.request.headers[key] = value

    @property
    def _headers(self):
        if self._norm_headers is None:
            if type(self.request.headers) is HTTPHeaders:
                self._norm_headers = self.request.headers
            else:
                self._norm_headers = HTTPHeaders(self.request.headers)
        return self._norm_headers

    @property
    def host_port(self):
        res = urllib.parse.urlparse(self.full_url)
        if res:
            return split_host_and_port(host_string=res.netloc,
                                       scheme=res.scheme)
        return None, None

    @property
    def method(self):
        return self.request.method

    @property
    def full_url(self):
        return self.request.url
