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
import tornado.stack_context


class RequestContext(object):
    """
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
    """A context manager that saves RequestContext in thread-local state.

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


class ThreadSafeStackContext(tornado.stack_context.StackContext):
    """
    Thread safe version of Tornado's StackContext (up to 4.3)

    Copy of implementation by caspersj@, until tornado-extras is open-sourced.

    Tornado's StackContext works as follows:
    - When entering a context, create an instance of StackContext and
      add add this instance to the current "context stack"
    - If execution transfers to another thread (using the wraps helper
      method),  copy the current "context stack" and apply that in the new
      thread when execution starts
    - A context stack can be entered/exited by traversing the stack and
      calling enter/exit on all elements. This is how the `wraps` helper
      method enters/exits in new threads.

    - StackContext has an internal pointer to a context factory (i.e.
      RequestContext), and an internal stack of applied contexts (instances
      of RequestContext) for each instance of StackContext. RequestContext
      instances are entered/exited from the stack as the StackContext
      is entered/exited
    - However, the enter/exit logic and maintenance of this stack of
      RequestContext instances is not thread safe.

    ```
    def __init__(self, context_factory):
        self.context_factory = context_factory
        self.contexts = []
        self.active = True

    def enter(self):
        context = self.context_factory()
        self.contexts.append(context)
        context.__enter__()

    def exit(self, type, value, traceback):
        context = self.contexts.pop()
        context.__exit__(type, value, traceback)
    ```

    Unexpected semantics of Tornado's default StackContext implementation:

    - There exist a race on `self.contexts`, where thread A enters a
      context, thread B enters a context, and thread A exits its context.
      In this case, the exit by thread A pops the instance created by
      thread B and calls exit on this instance.
    - There exists a race between `enter` and `exit` where thread A
      executes the two first statements of enter (create instance and
      add to contexts) and thread B executes exit, calling exit on an
      instance that has been initialized but not yet exited (and
      subsequently this instance will then be entered).

    The ThreadSafeStackContext changes the internal contexts stack to be
    thread local, fixing both of the above issues.
    """

    def __init__(self, *args, **kwargs):
        class LocalContexts(threading.local):
            def __init__(self):
                super(LocalContexts, self).__init__()
                self._contexts = []

            def append(self, item):
                self._contexts.append(item)

            def pop(self):
                return self._contexts.pop()

        super(ThreadSafeStackContext, self).__init__(*args, **kwargs)

        if hasattr(self, 'contexts'):
            # only patch if context exists
            self.contexts = LocalContexts()


def get_current_span():
    """
    Access current request context and extract current Span from it.
    :return:
        Return current span associated with the current request context.
        If no request context is present in thread local, or the context
        has no span, return None.
    """
    context = RequestContextManager.current_context()
    return context.span if context else None


def span_in_context(span):
    """
    Create a context manager that stores the given span in the thread-local
    request context. This function should only be used in single-threaded
    applications like Flask / uWSGI.

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
    context = RequestContext(span)
    return RequestContextManager(context)


def span_in_stack_context(span):
    """
    Create Tornado's StackContext that stores the given span in the
    thread-local request context. This function is intended for use
    in Tornado applications based on IOLoop, although will work fine
    in single-threaded apps like Flask, albeit with more overhead.

    ## Usage example in Tornado application

    Suppose you have a method `handle_request(request)` in the http server.
    Instead of calling it directly, use a wrapper:

    .. code-block:: python

        from opentracing_instrumentation import request_context

        @tornado.gen.coroutine
        def handle_request_wrapper(request, actual_handler, *args, **kwargs)

            request_wrapper = TornadoRequestWrapper(request=request)
            span = http_server.before_request(request=request_wrapper)

            with request_context.span_in_stack_context(span):
                return actual_handler(*args, **kwargs)

    :param span:
    :return:
        Return StackContext that wraps the request context.
    """
    context = RequestContext(span)
    return ThreadSafeStackContext(lambda: RequestContextManager(context))
