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
import contextlib2
import wrapt
import tornado.stack_context
from . import get_current_span, RequestContextManager


def func_span(func, tags=None):
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
    :return: new child span, or a dummy context manager if there is no
        active/current parent span
    """
    span = get_current_span()

    @contextlib2.contextmanager
    def empty_ctx_mgr():
        yield None

    if span is None:
        return empty_ctx_mgr()

    # TODO convert func to a proper name: module:class.func
    return span.start_child(operation_name=str(func), tags=tags)


def traced_function(operation_name, **tags):
    """
    A decorator that enables tracing of the wrapped function provided there
    is a parent span already established. Should not be used with Tornado
    coroutines because the span is finished as soon as the wrapped function
    returns a result, which in case of a coroutine will be an incomplete
    future. For coroutine use `traced_coroutine` decorator instead.

    :param operation_name: used as the name of the child span
    :param tags: optional tags that can be passed to the new child span
    :return: returns a tracing decorator
    """

    @wrapt.decorator
    def wrapper(wrapped, _, args, kwargs):
        parent_span = get_current_span()
        if parent_span is None:
            return wrapped(*args, **kwargs)
        with parent_span.start_child(operation_name=operation_name,
                                     tags=tags) as span:
            mgr = lambda: RequestContextManager(span)
            with tornado.stack_context.StackContext(mgr):
                return wrapped(*args, **kwargs)
    return wrapper


def traced_coroutine(operation_name, **tags):
    """
    A decorator that enables tracing of the wrapped Tornado coroutine
    provided there is a parent span already established.

    :param operation_name: used as the name of the child span
    :param tags: optional tags that can be passed to the new child span
    :return: returns a tracing decorator
    """

    @wrapt.decorator
    def wrapper(wrapped, _, args, kwargs):
        parent_span = get_current_span()
        if parent_span is None:
            return wrapped(*args, **kwargs)

        span = parent_span.start_child(operation_name=operation_name,
                                       tags=tags)
        mgr = lambda: RequestContextManager(span)
        with tornado.stack_context.StackContext(mgr):
            try:
                # cannot use yield inside StackContext, so instead
                # use a hook on Future completion
                res = wrapped(*args, **kwargs)

                def done_callback(future):
                    if future.exception() is not None:
                        span.error('exception', future.exception())
                    span.finish()

                res.add_done_callback(done_callback)
                return res
            except Exception as e:
                span.error('exception', e)
                span.finish()
                raise
    return wrapper
