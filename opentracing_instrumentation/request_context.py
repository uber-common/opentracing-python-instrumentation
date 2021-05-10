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
from builtins import object
import threading

import opentracing
from .tornado_context import span_in_stack_context  # noqa


class RequestContext(object):
    """
    DEPRECATED, use either span_in_context() or span_in_stack_context()
    instead.

    RequestContext represents the context of a request being executed.

    Useful when a service needs to make downstream calls to other services
    and requires access to some aspects of the original request, such as
    tracing information.

    It is designed to hold a reference to the current OpenTracing Span,
    but the class can be extended to store more information.
    """

    __slots__ = ('span', )

    def __init__(self, span):
        self.span = span


class RequestContextManager(object):
    """
    DEPRECATED, use either span_in_context() or span_in_stack_context()
    instead.

    A context manager that saves RequestContext in thread-local state.

    Intended for use with ThreadSafeStackContext (a thread-safe
    replacement for Tornado's StackContext) or as context manager
    in a WSGI middleware.
    """

    _state = threading.local()
    _state.context = None

    @classmethod
    def current_context(cls):
        """Get the current request context.

        :rtype: opentracing_instrumentation.RequestContext
        :returns: The current request context, or None.
        """
        return getattr(cls._state, 'context', None)

    def __init__(self, context=None, span=None):
        # normally we want the context parameter, but for backwards
        # compatibility we make it optional and allow span as well
        if span:
            self._context = RequestContext(span=span)
        elif isinstance(context, opentracing.Span):
            self._context = RequestContext(span=context)
        else:
            self._context = context

    def __enter__(self):
        self._prev_context = self.__class__.current_context()
        self.__class__._state.context = self._context
        return self._context

    def __exit__(self, *_):
        self.__class__._state.context = self._prev_context
        self._prev_context = None
        return False


def get_current_span():
    """
    Access current request context and extract current Span from it.
    :return:
        Return current span associated with the current request context.
        If no request context is present in thread local, or the context
        has no span, return None.
    """
    # Check against the old, ScopeManager-less implementation,
    # for backwards compatibility.
    context = RequestContextManager.current_context()
    if context is not None:
        return context.span

    active = opentracing.tracer.scope_manager.active
    return active.span if active else None


def span_in_context(span):
    """
    Create a context manager that stores the given span in the thread-local
    request context. This function should only be used in single-threaded
    applications like Flask / uWSGI.

    This function also compatible with asyncio.

    ## Usage example in WSGI middleware:

    .. code-block:: python
        from opentracing_instrumentation.http_server import WSGIRequestWrapper
        from opentracing_instrumentation.http_server import before_request
        from opentracing_instrumentation import request_context

        def create_wsgi_tracing_middleware(other_wsgi):

            def wsgi_tracing_middleware(environ, start_response):
                request = WSGIRequestWrapper.from_wsgi_environ(environ)
                span = before_request(request=request, tracer=tracer)

                # Wrapper around the real start_response object to log
                # additional information to opentracing Span
                def start_response_wrapper(status, response_headers,
                                           exc_info=None):
                    if exc_info is not None:
                        span.log(event='exception', payload=exc_info)
                    span.finish()

                    return start_response(status, response_headers)

                with request_context.span_in_context(span):
                    return other_wsgi(environ, start_response_wrapper)

            return wsgi_tracing_middleware

    :param span: OpenTracing Span
    :return:
        Return context manager that wraps the request context.
    """

    # Return a no-op Scope if None was specified.
    if span is None:
        return opentracing.Scope(None, None)

    return opentracing.tracer.scope_manager.activate(span, False)
