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


class TraceContextManager(object):
    """A context manager that saves tracing span in per-thread state globally.

    Intended for use with Tornado's StackContext, or can be used directly
    as a context manager inside uWSGI middleware in clay.
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
    return TraceContextManager.current_span()
