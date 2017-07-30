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
import logging
import urllib.parse

from ..request_context import get_current_span
from ..http_client import AbstractRequestWrapper
from ..http_client import before_http_request
from ..http_client import split_host_and_port
from ._singleton import singleton

log = logging.getLogger(__name__)

# Try to save the original entry points
try:
    import requests.sessions
    import requests.adapters
except ImportError:  # pragma: no cover
    pass
else:
    _HTTPAdapter_send = requests.adapters.HTTPAdapter.send


@singleton
def install_patches():
    try:
        import requests.sessions
        import requests.adapters
    except ImportError:  # pragma: no cover
        return

    def send_wrapper(self, request, **kwargs):
        """Wraps HTTPAdapter.send"""

        request_wrapper = RequestWrapper(request=request)
        span = before_http_request(
            request=request_wrapper,
            current_span_extractor=get_current_span)
        with span:
            resp = _HTTPAdapter_send(self, request, **kwargs)
            if hasattr(resp, 'status_code') and resp.status_code is not None:
                span.set_tag('http.status_code', resp.status_code)
        return resp

    class RequestWrapper(AbstractRequestWrapper):
        def __init__(self, request):
            self.request = request
            self.scheme, rest = urllib.parse.splittype(request.url)
            if self.scheme and rest:
                self.host_str, _ = urllib.parse.splithost(rest)
            else:
                self.host_str = ''

        def add_header(self, key, value):
            self.request.headers[key] = value

        @property
        def method(self):
            return self.request.method

        @property
        def full_url(self):
            return self.request.url

        @property
        def _headers(self):
            return self.request.headers

        @property
        def host_port(self):
            return split_host_and_port(host_string=self.host_str,
                                       scheme=self.scheme)

    requests.adapters.HTTPAdapter.send = send_wrapper
