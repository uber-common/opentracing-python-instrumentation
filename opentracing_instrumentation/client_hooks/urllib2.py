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
import six

from future import standard_library
standard_library.install_aliases()

from tornado.httputil import HTTPHeaders
from opentracing_instrumentation.request_context import get_current_span
from opentracing_instrumentation.http_client import AbstractRequestWrapper
from opentracing_instrumentation.http_client import before_http_request
from opentracing_instrumentation.http_client import split_host_and_port
from ._singleton import singleton

log = logging.getLogger(__name__)


@singleton
def install_patches():
    import http.client
    import urllib.request

    def build_handler(base_type, base_cls=None):
        """Build a urrllib2 handler from a base_type."""

        class DerivedHandler(base_type):
            """The class derived from base_type."""

            def do_open(self, req, conn):
                request_wrapper = Urllib2RequestWrapper(request=req)
                span = before_http_request(
                    request=request_wrapper,
                    current_span_extractor=get_current_span)
                with span:
                    if base_cls:
                        # urllib2.AbstractHTTPHandler doesn't support super()
                        resp = base_cls.do_open(self, conn, req)
                    else:
                        resp = super(DerivedHandler, self).do_open(conn, req)
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
            host_string = self.request.host
            return split_host_and_port(host_string=host_string,
                                       scheme=self.request.type)

    def install_for_module(module, do_open_base=None):
        httpBase = build_handler(module.HTTPHandler, do_open_base)
        httpsBase = build_handler(module.HTTPSHandler, do_open_base)

        class TracedHTTPHandler(httpBase):
            def http_open(self, req):
                return self.do_open(req, http.client.HTTPConnection)

        class TracedHTTPSHandler(httpsBase):
            def https_open(self, req):
                return self.do_open(req, http.client.HTTPSConnection)

        log.info('Instrumenting %s for tracing' % module.__name__)
        opener = module.build_opener(TracedHTTPHandler, TracedHTTPSHandler)
        module.install_opener(opener)

    if six.PY2:
        import urllib2
        base = urllib2.AbstractHTTPHandler
        install_for_module(urllib2, base)

    install_for_module(urllib.request)
