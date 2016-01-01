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

import opentracing
from opentracing_instrumentation import config
from opentracing.ext import tags


def before_request(request, tracer=None):
    if tracer is None:  # pragma: no cover
        tracer = opentracing.tracer

    operation = request.operation
    context = tracer.unmarshal_trace_context_str_dict(
        trace_context_id=request.headers,
        trace_attributes=request.headers
    )
    if context is None:
        span = tracer.start_trace(operation_name=operation)
    else:
        span = tracer.join_trace(operation_name=operation,
                                 parent_trace_context=context)

    span.add_tag('client.http.url', request.full_url)

    remote_ip = request.remote_ip
    if remote_ip:
        span.add_tag(tags.PEER_HOST_IPV4, remote_ip)

    caller_name = request.caller_name
    if caller_name:
        span.add_tag(tags.PEER_SERVICE, caller_name)

    remote_port = request.remote_port
    if remote_port:
        span.add_tag(tags.PEER_PORT, remote_port)

    return span


class AbstractRequestWrapper(object):
    """
    Exposes several properties used by the tracing methods.
    """

    @property
    def caller_name(self):
        for header in config.CONFIG.caller_name_headers:
            caller = self.headers.get(header, None)
            if caller is not None:
                return caller
        return None

    @property
    def full_url(self):
        raise NotImplementedError('full_url')

    @property
    def headers(self):
        raise NotImplementedError('headers')

    @property
    def method(self):
        raise NotImplementedError('method')

    @property
    def remote_ip(self):
        raise NotImplementedError('remote_ip')

    @property
    def remote_port(self):
        return None

    @property
    def server_port(self):
        return None

    @property
    def operation(self):
        return self.method
