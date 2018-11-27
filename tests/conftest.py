import opentracing
import pytest
from basictracer import BasicTracer
from basictracer.recorder import InMemoryRecorder


@pytest.fixture
def tracer():
    dummy_tracer = BasicTracer(recorder=InMemoryRecorder())
    dummy_tracer.register_required_propagators()
    old_tracer = opentracing.tracer
    opentracing.tracer = dummy_tracer

    try:
        yield dummy_tracer
    finally:
        opentracing.tracer = old_tracer
