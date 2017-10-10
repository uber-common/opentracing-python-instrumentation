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

_interceptors = []


@six.add_metaclass(abc.ABCMeta)
class OpentracingInterceptor(object):

    @abc.abstractmethod
    def process(self, request, span):
        pass


class Interceptors(object):

    _interceptors = []

    @classmethod
    def append(cls, interceptor):
        cls._check(interceptor)
        cls._interceptors.append(interceptor)

    @classmethod
    def insert(cls, index, interceptor):
        cls._check(interceptor)
        cls._interceptors.insert(index, interceptor)

    @classmethod
    def _check(cls, interceptor):
        if not isinstance(interceptor, OpentracingInterceptor):
            raise ValueError('Interceptors only accepts instances '
                             'of OpentracingInterceptor')

    @classmethod
    def get_interceptors(cls):
        return cls._interceptors

    @classmethod
    def clear(cls):
        del cls._interceptors[:]
