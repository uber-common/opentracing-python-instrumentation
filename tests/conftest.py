# Copyright (c) 2018 Uber Technologies, Inc.
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

import opentracing
import pytest
from basictracer import BasicTracer
from basictracer.recorder import InMemoryRecorder
from opentracing.scope_managers.tornado import TornadoScopeManager


def _get_tracers(scope_manager=None):
    dummy_tracer = BasicTracer(recorder=InMemoryRecorder(),
                               scope_manager=scope_manager)
    dummy_tracer.register_required_propagators()
    old_tracer = opentracing.tracer
    opentracing.tracer = dummy_tracer

    return old_tracer, dummy_tracer


@pytest.fixture
def tracer():
    old_tracer, dummy_tracer = _get_tracers()
    try:
        yield dummy_tracer
    finally:
        opentracing.tracer = old_tracer


@pytest.fixture
def thread_safe_tracer():
    old_tracer, dummy_tracer = _get_tracers(TornadoScopeManager())
    try:
        yield dummy_tracer
    finally:
        opentracing.tracer = old_tracer
