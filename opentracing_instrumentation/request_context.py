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
import threading


class RequestContextManager(object):
    """A context manager that saves tracing span in per-thread state globally.

    Intended for use with Tornado's StackContext or as context manager
    in a WSGI middleware.

    ## Usage with Tornado StackContext

    Suppose you have a method `handle_request(request)` in the http server.
    Instead of calling it directly, use a wrapper:

    .. code-block:: python

        @tornado.gen.coroutine
        def handle_request_wrapper(request, actual_handler, *args, **kwargs)

            request_wrapper = TornadoRequestWrapper(request=request)
            span = http_server.before_request(request=request_wrapper)

            mgr = lambda: RequestContextManager(span)
            with tornado.stack_context.StackContext(mgr):
                return actual_handler(*args, **kwargs)

    ## Usage with WSGI middleware:

    .. code-block:: python

        def create_wsgi_tracing_middleware(other_wsgi):

            def wsgi_tracing_middleware(environ, start_response):
                request = WSGIRequestWrapper.from_wsgi_environ(environ)
                span = before_request(request=request, tracer=tracer)

                # Wrapper around the real start_response object to log
                # additional information to opentracing Span
                def start_response_wrapper(status, response_headers,
                                           exc_info=None):
                    if exc_info is not None:
                        span.error('exception', exc_info)
                    span.finish()

                    return start_response(status, response_headers)

                with RequestContextManager(span=span):
                    return other_wsgi(environ, start_response_wrapper)

            return wsgi_tracing_middleware

    """

    _state = threading.local()
    _state.span = None

    @classmethod
    def current_span(cls):
        """Get the current tracing span.

        :rtype: opentracing.Span
        :returns: The current tracing span, or None if no span was started.
        """

        return getattr(cls._state, 'span', None)

    def __init__(self, span):
        self._span = span

    def __enter__(self):
        self._prev_span = self.__class__.current_span()
        self.__class__._state.span = self._span

    def __exit__(self, *_):
        self.__class__._state.span = self._prev_span
        self._prev_span = None
        return False


def get_current_span():
    """
    :return: Current span associated with the current stack context, or None.
    """
    return RequestContextManager.current_span()
