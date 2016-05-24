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
import re
import opentracing
from opentracing import Format
from opentracing.ext import tags
from opentracing_instrumentation.config import CONFIG


def before_http_request(request, current_span_extractor):
    """
    A hook to be executed before HTTP request is executed.
    It returns a Span object that can be used as a context manager around
    the actual HTTP call implementation, or in case of async callback,
    it needs its `finish()` method to be called explicitly.

    :param request: request must match API defined by AbstractRequestWrapper
    :param current_span_extractor: function that extracts current span
        from some context
    :return: returns child tracing span encapsulating this request
    """

    span = opentracing.tracer.start_span(
        operation_name=request.operation,
        parent=current_span_extractor()
    )

    span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
    span.set_tag(tags.HTTP_URL, request.full_url)

    service_name = request.service_name
    host, port = request.host_port
    if service_name:
        span.set_tag(tags.PEER_SERVICE, service_name)
    if host:
        span.set_tag(tags.PEER_HOST_IPV4, host)
    if port:
        span.set_tag(tags.PEER_PORT, port)

    try:
        carrier = {}
        opentracing.tracer.inject(span=span, format=Format.TEXT_MAP,
                                  carrier=carrier)
        for key, value in carrier.iteritems():
            request.add_header(key, value)
    except opentracing.UnsupportedFormatException:
        pass

    return span


class AbstractRequestWrapper(object):
    def add_header(self, key, value):
        pass

    @property
    def _headers(self):
        return {}

    @property
    def host_port(self):
        return None, None

    @property
    def service_name(self):
        for header in CONFIG.callee_name_headers:
            value = self._headers.get(header, None)
            if value is not None:
                return value
        return None

    @property
    def operation(self):
        for header in CONFIG.callee_endpoint_headers:
            value = self._headers.get(header, None)
            if value is not None:
                return '%s:%s' % (self.method, value)
        return self.method

    @property
    def method(self):
        raise NotImplementedError

    @property
    def full_url(self):
        raise NotImplementedError


HOST_PORT_RE = re.compile(r'^(.*):(\d+)$')


def split_host_and_port(host_string, scheme='http'):
    is_secure = True if scheme == 'https' else False
    m = HOST_PORT_RE.match(host_string)
    if m:
        host, port = m.groups()
        return host, int(port)
    elif is_secure is None:
        return host_string, None
    elif is_secure:
        return host_string, 443
    else:
        return host_string, 80
