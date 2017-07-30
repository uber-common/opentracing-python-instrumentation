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

import logging

from tornado.httputil import HTTPHeaders
from opentracing_instrumentation.request_context import get_current_span
from opentracing_instrumentation.http_client import AbstractRequestWrapper
from opentracing_instrumentation.http_client import before_http_request
from opentracing_instrumentation.http_client import split_host_and_port
from ._singleton import singleton

log = logging.getLogger(__name__)


@singleton
def install_patches():
    import httplib
    import urllib2

    log.info('Instrumenting urllib2 methods for tracing')

    def build_handler(base_type):
        """Build a urrllib2 handler from a base_type."""

        class DerivedHandler(base_type):
            """The class derived from base_type."""

            def do_open(self, req, conn):
                request_wrapper = Urllib2RequestWrapper(request=req)
                span = before_http_request(
                    request=request_wrapper,
                    current_span_extractor=get_current_span)
                with span:
                    resp = urllib2.AbstractHTTPHandler.do_open(self, conn, req)
                    if resp.code is not None:
                        span.set_tag('http.status_code', resp.code)
                return resp

        return DerivedHandler

    class Urllib2RequestWrapper(AbstractRequestWrapper):
        def __init__(self, request):
            self.request = request
            self._norm_headers = None

        def add_header(self, key, value):
            self.request.add_header(key, value)

        @property
        def method(self):
            return self.request.get_method()

        @property
        def full_url(self):
            return self.request.get_full_url()

        @property
        def _headers(self):
            if self._norm_headers is None:
                self._norm_headers = HTTPHeaders(self.request.headers)
            return self._norm_headers

        @property
        def host_port(self):
            host_string = self.request.get_host()
            return split_host_and_port(host_string=host_string,
                                       scheme=self.request.get_type())

    class TracedHTTPHandler(build_handler(urllib2.HTTPHandler)):

        def http_open(self, req):
            return self.do_open(req, httplib.HTTPConnection)

    class TracedHTTPSHandler(build_handler(urllib2.HTTPSHandler)):

        def https_open(self, req):
            return self.do_open(req, httplib.HTTPSConnection)

    opener = urllib2.build_opener(TracedHTTPHandler, TracedHTTPSHandler)
    urllib2.install_opener(opener)
