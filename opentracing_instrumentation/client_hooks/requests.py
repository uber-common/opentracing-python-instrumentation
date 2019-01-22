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

from opentracing.ext import tags
from ..http_client import AbstractRequestWrapper
from ..http_client import before_http_request
from ..http_client import split_host_and_port
from ._patcher import Patcher
from ._current_span import current_span_func

log = logging.getLogger(__name__)

# Try to save the original entry points
try:
    import requests.adapters
except ImportError:  # pragma: no cover
    pass
else:
    _HTTPAdapter_send = requests.adapters.HTTPAdapter.send


class RequestsPatcher(Patcher):
    applicable = '_HTTPAdapter_send' in globals()
    response_handler_hook = None

    def set_response_handler_hook(self, response_handler_hook):
        """
        Set a hook that will be called when a response is received.

        The hook can be set in purpose to set custom tags to spans
        depending on content or some metadata of responses.

        :param response_handler_hook: hook method
            It must have a signature `(response, span)`,
            where `response` and `span` are positional arguments,
            so you can use different names for them if needed.
        """

        self.response_handler_hook = response_handler_hook

    def _install_patches(self):
        requests.adapters.HTTPAdapter.send = self._get_send_wrapper()

    def _reset_patches(self):
        requests.adapters.HTTPAdapter.send = _HTTPAdapter_send

    def _get_send_wrapper(self):
        def send_wrapper(http_adapter, request, **kwargs):
            """Wraps HTTPAdapter.send"""
            request_wrapper = self.RequestWrapper(request=request)
            span = before_http_request(request=request_wrapper,
                                       current_span_extractor=current_span_func
                                       )
            with span:
                response = _HTTPAdapter_send(http_adapter, request, **kwargs)
                if getattr(response, 'status_code', None) is not None:
                    span.set_tag(tags.HTTP_STATUS_CODE, response.status_code)
                if self.response_handler_hook is not None:
                    self.response_handler_hook(response, span)
            return response

        return send_wrapper

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


patcher = RequestsPatcher()


def set_patcher(custom_patcher):
    global patcher
    patcher = custom_patcher


def install_patches():
    patcher.install_patches()
