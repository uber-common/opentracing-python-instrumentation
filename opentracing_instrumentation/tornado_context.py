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

_tornado_supported = False
_stack_context_supported = False

import opentracing
try:
    import tornado  # noqa
    _tornado_supported = True
    from opentracing.scope_managers.tornado import TornadoScopeManager
    from opentracing.scope_managers.tornado import tracer_stack_context
    _stack_context_supported = True
except ImportError:
    pass


def is_tornado_supported():
    return _tornado_supported


def is_stack_context_supported():
    return _stack_context_supported


class _TracerEnteredStackContext(object):
    """
    An entered tracer_stack_context() object.

    Intended to have a ready-to-use context where
    Span objects can be activated before the context
    itself is returned to the user.
    """

    def __init__(self, context):
        self._context = context
        self._deactivation_cb = context.__enter__()

    def __enter__(self):
        return self._deactivation_cb

    def __exit__(self, type, value, traceback):
        return self._context.__exit__(type, value, traceback)


def span_in_stack_context(span):
    """
    Create Tornado's (4.x, 5.x) StackContext that stores the given span in the
    thread-local request context. This function is intended for use
    in Tornado applications based on IOLoop, although will work fine
    in single-threaded apps like Flask, albeit with more overhead.

    StackContext has been deprecated in Tornado 6 and higher.
    Because of asyncio nature of Tornado 6.x, consider using
    `span_in_context` with opentracing scope manager `ContextVarScopeManager`

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
    if not _tornado_supported:
        raise RuntimeError('span_in_stack_context requires Tornado')

    if not is_stack_context_supported():
        raise RuntimeError('tornado.stack_context is not supported in '
                           'Tornado >= 6.x')
    if not isinstance(
            opentracing.tracer.scope_manager, TornadoScopeManager
    ):
        raise RuntimeError('scope_manager is not TornadoScopeManager')

    # Enter the newly created stack context so we have
    # storage available for Span activation.
    context = tracer_stack_context()
    entered_context = _TracerEnteredStackContext(context)

    if span is None:
        return entered_context

    opentracing.tracer.scope_manager.activate(span, False)
    assert opentracing.tracer.active_span is not None
    assert opentracing.tracer.active_span is span

    return entered_context
