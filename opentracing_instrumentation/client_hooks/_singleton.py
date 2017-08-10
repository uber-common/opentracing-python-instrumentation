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

from builtins import range
import functools


def singleton(func):
    """
    This decorator allows you to make sure that a function is called once and
    only once. Note that recursive functions will still work.

    Not thread-safe.
    """
    NOT_CALLED, IN_CALL, CALLED = list(range(3))

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if wrapper.__call_state__ == CALLED:
            return
        old_state, wrapper.__call_state__ = wrapper.__call_state__, IN_CALL
        ret = func(*args, **kwargs)
        if old_state == NOT_CALLED:
            wrapper.__call_state__ = CALLED
        return ret

    wrapper.__call_state__ = NOT_CALLED
    # save original func to be able to patch and restore multiple times from
    # unit tests
    wrapper.__original_func = func
    return wrapper
