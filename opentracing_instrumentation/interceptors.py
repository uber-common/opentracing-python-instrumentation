# Copyright (c) 2017 Uber Technologies, Inc.
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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class OpenTracingInterceptor(object):
    """
    Abstract OpenTracing Interceptor class.

    Subclasses are expected to provide a full implementation of
    the ``process(..)`` method which is passed the request object,
    and the current span.

    A code sample of expected usage:

    .. code-block:: python

        from opentracing_instrumentation.interceptors \
            import OpenTracingInterceptor

        class CustomOpenTracingInterceptor(OpenTracingInterceptor):

            def process(self, request, span):
                span.set_baggage_item(..)

    """

    @abc.abstractmethod
    def process(self, request, span):
        """Fire the interceptor."""
        pass


class ClientInterceptors(object):
    """
    Client interceptors executed between span creation and injection.

    Subclassed implementations of ``OpenTracingInterceptor`` can be added
    and are executed in order in which they are added, after child
    span for current request is created, but before the span baggage
    contents are injected into the outbound request.

    A code sample of expected usage:

    from opentracing_instrumentation.interceptors import ClientInterceptors

    from my_project.interceptors import CustomOpenTracingInterceptor

    my_interceptor = CustomOpenTracingInterceptor()
    ClientInterceptors.append(my_interceptor)

    """

    _interceptors = []

    @classmethod
    def append(cls, interceptor):
        """
        Add interceptor to the end of the internal list.

        Note: Raises ``ValueError`` if interceptor
              does not extend ``OpenTracingInterceptor``
        """
        cls._check(interceptor)
        cls._interceptors.append(interceptor)

    @classmethod
    def insert(cls, index, interceptor):
        """
        Add interceptor to the given index in the internal list.

        Note: Raises ``ValueError`` if interceptor
              does not extend ``OpenTracingInterceptor``
        """
        cls._check(interceptor)
        cls._interceptors.insert(index, interceptor)

    @classmethod
    def _check(cls, interceptor):
        if not isinstance(interceptor, OpenTracingInterceptor):
            raise ValueError('ClientInterceptors only accepts instances '
                             'of OpenTracingInterceptor')

    @classmethod
    def get_interceptors(cls):
        """Return a list of interceptors."""
        return cls._interceptors

    @classmethod
    def clear(cls):
        """Clear the internal list of interceptors."""
        del cls._interceptors[:]
