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
from builtins import str
import functools
import contextlib2
import tornado.concurrent
import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager
from . import get_current_span, span_in_stack_context, span_in_context, utils

try:
    import asyncio
    _ASYNCIO = True
except ImportError:
    _ASYNCIO = False


def is_asyncio_coroutine(func):
    return _ASYNCIO and asyncio.iscoroutine(func)


def func_span(func, tags=None, require_active_trace=False):
    """
    Creates a new local span for execution of the given `func`.
    The returned span is best used as a context manager, e.g.

    .. code-block:: python

        with func_span('my_function'):
            return my_function(...)

    At this time the func should be a string name. In the future this code
    can be enhanced to accept a real function and derive its qualified name.

    :param func: name of the function or method
    :param tags: optional tags to add to the child span
    :param require_active_trace: controls what to do when there is no active
        trace. If require_active_trace=True, then no span is created.
        If require_active_trace=False, a new trace is started.
    :return: new child span, or a dummy context manager if there is no
        active/current parent span
    """
    current_span = get_current_span()

    if current_span is None and require_active_trace:
        @contextlib2.contextmanager
        def empty_ctx_mgr():
            yield None

        return empty_ctx_mgr()

    # TODO convert func to a proper name: module:class.func
    operation_name = str(func)
    return utils.start_child_span(
        operation_name=operation_name, parent=current_span, tags=tags)


class _DummyStackContext(object):
    """
    Stack context that restores previous scope after exit.
    Will be returned by helper `_span_in_stack_context` when tracer scope
    manager is not `TornadoScopeManager`.
    """
    def __init__(self, context):
        self._context = context

    def __enter__(self):
        # Need for compatibility with `span_in_stack_context`.
        return lambda: None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._context:
            self._context.close()


def _span_in_stack_context(span):
    if isinstance(opentracing.tracer.scope_manager, TornadoScopeManager):
        return span_in_stack_context(span)
    else:
        return _DummyStackContext(span_in_context(span))


def traced_function(func=None, name=None, on_start=None,
                    require_active_trace=False):
    """
    A decorator that enables tracing of the wrapped function or
    Tornado co-routine provided there is a parent span already established.

    .. code-block:: python

        @traced_function
        def my_function1(arg1, arg2=None)
            ...

    :param func: decorated function or Tornado co-routine
    :param name: optional name to use as the Span.operation_name.
        If not provided, func.__name__ will be used.
    :param on_start: an optional callback to be executed once the child span
        is started, but before the decorated function is called. It can be
        used to set any additional tags on the span, perhaps by inspecting
        the decorated function arguments. The callback must have a signature
        `(span, *args, *kwargs)`, where the last two collections are the
        arguments passed to the actual decorated function.

        .. code-block:: python

            def extract_call_site_tag(span, *args, *kwargs)
                if 'call_site_tag' in kwargs:
                    span.set_tag('call_site_tag', kwargs['call_site_tag'])

            @traced_function(on_start=extract_call_site_tag)
            @tornado.get.coroutine
            def my_function(arg1, arg2=None, call_site_tag=None)
                ...

    :param require_active_trace: controls what to do when there is no active
        trace. If require_active_trace=True, then no span is created.
        If require_active_trace=False, a new trace is started.
    :return: returns a tracing decorator
    """

    if func is None:
        return functools.partial(traced_function, name=name,
                                 on_start=on_start,
                                 require_active_trace=require_active_trace)

    if name:
        operation_name = name
    else:
        operation_name = func.__name__

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        parent_span = get_current_span()
        if parent_span is None and require_active_trace:
            return func(*args, **kwargs)

        span = utils.start_child_span(
            operation_name=operation_name, parent=parent_span)
        if callable(on_start):
            on_start(span, *args, **kwargs)

        # We explicitly invoke deactivation callback for the StackContext,
        # because there are scenarios when it gets retained forever, for
        # example when a Periodic Callback is scheduled lazily while in the
        # scope of a tracing StackContext.
        with _span_in_stack_context(span) as deactivate_cb:
            try:
                res = func(*args, **kwargs)
                is_tornado = tornado.concurrent.is_future(res)
                is_asyncio = is_asyncio_coroutine(res)
                if is_asyncio:
                    task = asyncio.create_task(res)
                else:
                    task = res
                # Tornado co-routines usually return futures, so we must wait
                # until the future is completed, in order to accurately
                # capture the function's execution time.
                if is_tornado or is_asyncio:
                    def done_callback(future):
                        deactivate_cb()
                        exception = future.exception()
                        if exception is not None:
                            span.log(event='exception', payload=exception)
                            span.set_tag('error', 'true')
                        span.finish()
                    if task.done():
                        done_callback(res)
                    else:
                        task.add_done_callback(done_callback)
                else:
                    deactivate_cb()
                    span.finish()
                return task
            except Exception as e:
                deactivate_cb()
                span.log(event='exception', payload=e)
                span.set_tag('error', 'true')
                span.finish()
                raise
    return decorator
