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

import time

from threading import Thread
from tornado.stack_context import wrap

from opentracing_instrumentation.request_context import (
    get_current_span, span_in_stack_context,
)


def test__request_context_is_thread_safe(thread_safe_tracer):
    """
    Port of Uber's internal tornado-extras (by @sema).

    This test illustrates that the default Tornado's StackContext
    is not thread-safe. The test can be made to fail by commenting
    out these lines in the ThreadSafeStackContext constructor:

        if hasattr(self, 'contexts'):
            # only patch if context exists
            self.contexts = LocalContexts()
    """

    num_iterations = 1000
    num_workers = 10
    exception = [0]

    def async_task():
        time.sleep(0.001)
        assert get_current_span() is not None

    class Worker(Thread):
        def __init__(self, fn):
            super(Worker, self).__init__()
            self.fn = fn

        def run(self):
            try:
                for _ in range(0, num_iterations):
                    self.fn()
            except Exception as e:
                exception[0] = e
                raise

    with span_in_stack_context(span='span'):
        workers = []
        for i in range(0, num_workers):
            worker = Worker(wrap(async_task))
            workers.append(worker)

        for worker in workers:
            worker.start()

        for worker in workers:
            worker.join()

    if exception[0]:
        raise exception[0]
