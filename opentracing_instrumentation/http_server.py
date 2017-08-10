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
import logging
import urllib.parse
import opentracing
import six
from opentracing import Format
from opentracing.ext import tags
from opentracing_instrumentation import config


def before_request(request, tracer=None):
    """
    Attempts to extract a tracing span from incoming request.
    If no tracing context is passed in the headers, or the data
    cannot be parsed, a new root span is started.

    :param request: HTTP request with `.headers` property exposed
        that satisfies a regular dictionary interface
    :param tracer: optional tracer instance to use. If not specified
        the global opentracing.tracer will be used.
    :return: returns a new, already started span.
    """
    if tracer is None:  # pragma: no cover
        tracer = opentracing.tracer

    # we need to prepare tags upfront, mainly because RPC_SERVER tag must be
    # set when starting the span, to support Zipkin's one-span-per-RPC model
    tags_dict = {
        tags.SPAN_KIND: tags.SPAN_KIND_RPC_SERVER,
        tags.HTTP_URL: request.full_url,
    }

    remote_ip = request.remote_ip
    if remote_ip:
        tags_dict[tags.PEER_HOST_IPV4] = remote_ip

    caller_name = request.caller_name
    if caller_name:
        tags_dict[tags.PEER_SERVICE] = caller_name

    remote_port = request.remote_port
    if remote_port:
        tags_dict[tags.PEER_PORT] = remote_port

    operation = request.operation
    try:
        carrier = {}
        for key, value in six.iteritems(request.headers):
            carrier[key] = value
        parent_ctx = tracer.extract(
            format=Format.HTTP_HEADERS, carrier=carrier
        )
    except Exception as e:
        logging.exception('trace extract failed: %s' % e)
        parent_ctx = None

    span = tracer.start_span(
        operation_name=operation,
        child_of=parent_ctx,
        tags=tags_dict)

    return span


class AbstractRequestWrapper(object):
    """
    Exposes several properties used by the tracing methods.
    """

    @property
    def caller_name(self):
        for header in config.CONFIG.caller_name_headers:
            caller = self.headers.get(header.lower(), None)
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


class TornadoRequestWrapper(AbstractRequestWrapper):
    """
    Wraps tornado.httputils.HTTPServerRequest and exposes several properties
    used by the tracing methods.
    """

    def __init__(self, request):
        self.request = request

    @property
    def full_url(self):
        return self.request.full_url()

    @property
    def headers(self):
        return self.request.headers

    @property
    def method(self):
        return self.request.method

    @property
    def remote_ip(self):
        return self.request.remote_ip


class WSGIRequestWrapper(AbstractRequestWrapper):
    """
    Wraps WSGI environment and exposes several properties
    used by the tracing methods.
    """

    def __init__(self, wsgi_environ, headers):
        self.wsgi_environ = wsgi_environ
        self._headers = headers

    @classmethod
    def from_wsgi_environ(cls, wsgi_environ):
        instance = cls(wsgi_environ=wsgi_environ,
                       headers=cls._parse_wsgi_headers(wsgi_environ))
        return instance

    @staticmethod
    def _parse_wsgi_headers(wsgi_environ):
        """
        HTTP headers are presented in WSGI environment with 'HTTP_' prefix.
        This method finds those headers, removes the prefix, converts
        underscores to dashes, and converts to lower case.

        :param wsgi_environ:
        :return: returns a dictionary of headers
        """
        prefix = 'HTTP_'
        p_len = len(prefix)
        # use .items() despite suspected memory pressure bc GC occasionally
        # collects wsgi_environ.iteritems() during iteration.
        headers = {
            key[p_len:].replace('_', '-').lower():
                val for (key, val) in wsgi_environ.items()
            if key.startswith(prefix)}
        return headers

    @property
    def full_url(self):
        """
        Taken from
        http://legacy.python.org/dev/peps/pep-3333/#url-reconstruction

        :return: Reconstructed URL from WSGI environment.
        """
        environ = self.wsgi_environ
        url = environ['wsgi.url_scheme'] + '://'

        if environ.get('HTTP_HOST'):
            url += environ['HTTP_HOST']
        else:
            url += environ['SERVER_NAME']

            if environ['wsgi.url_scheme'] == 'https':
                if environ['SERVER_PORT'] != '443':
                    url += ':' + environ['SERVER_PORT']
            else:
                if environ['SERVER_PORT'] != '80':
                    url += ':' + environ['SERVER_PORT']

        url += urllib.parse.quote(environ.get('SCRIPT_NAME', ''))
        url += urllib.parse.quote(environ.get('PATH_INFO', ''))
        if environ.get('QUERY_STRING'):
            url += '?' + environ['QUERY_STRING']
        return url

    @property
    def headers(self):
        return self._headers

    @property
    def method(self):
        return self.wsgi_environ.get('REQUEST_METHOD')

    @property
    def remote_ip(self):
        return self.wsgi_environ.get('REMOTE_ADDR', None)

    @property
    def remote_port(self):
        return self.wsgi_environ.get('REMOTE_PORT', None)

    @property
    def server_port(self):
        return self.wsgi_environ.get('SERVER_PORT', None)
