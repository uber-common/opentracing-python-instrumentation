from functools import partial

import time

import pytest

from threading import Thread
from tornado import gen
from tornado.locks import Condition
from tornado.stack_context import wrap

from opentracing_instrumentation.request_context import (
    get_current_span, span_in_stack_context,
)


def test__request_context_is_thread_safe():
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
                for _ in xrange(0, num_iterations):
                    self.fn()
            except Exception as e:
                exception[0] = e
                raise

    with span_in_stack_context(span='span'):
        workers = []
        for i in xrange(0, num_workers):
            worker = Worker(wrap(async_task))
            workers.append(worker)

        for worker in workers:
            worker.start()

        for worker in workers:
            worker.join()

    if exception[0]:
        raise exception[0]
