import celery as celery_module
import mock
import pytest

from celery import Celery
from celery.signals import (
    before_task_publish, after_task_publish, task_postrun
)
from celery.states import SUCCESS, FAILURE
from celery.worker import state as celery_worker_state
from kombu import Connection
from opentracing.ext import tags

from opentracing_instrumentation.client_hooks import celery as celery_hooks


CELERY_3 = celery_module.__version__.split('.', 1)[0] == '3'


@pytest.fixture(autouse=True, scope='module')
def patch_celery():
    celery_hooks.install_patches()
    try:
        yield
    finally:
        celery_hooks.reset_patches()


def assert_span(span, result, operation, span_kind):
    assert span.operation_name == 'Celery:{}:foo'.format(operation)
    assert span.tags.get(tags.SPAN_KIND) == span_kind
    assert span.tags.get(tags.COMPONENT) == 'Celery'
    assert span.tags.get('celery.task_name') == 'foo'
    assert span.tags.get('celery.task_id') == result.task_id


@mock.patch(
    'celery.worker.job.logger' if CELERY_3 else 'celery.app.trace.logger'
)
def _test_foo_task(celery, task_error, celery_logger):

    @celery.task(name='foo')
    def foo():
        foo.called = True
        if task_error:
            raise ValueError('Task error')
    foo.called = False

    result = foo.delay()
    assert foo.called
    if task_error:
        assert result.status == FAILURE
        if not (
            CELERY_3 and celery.conf.defaults[0].get('CELERY_ALWAYS_EAGER')
        ):
            celery_logger.log.assert_called_once()
    else:
        assert result.status == SUCCESS
        celery_logger.log.assert_not_called()

    return result


def _test_with_instrumented_client(celery, tracer, task_error):
    result = _test_foo_task(celery, task_error)

    span_server, span_client = tracer.recorder.get_spans()
    assert span_client.parent_id is None
    assert span_client.context.trace_id == span_server.context.trace_id
    assert span_client.context.span_id == span_server.parent_id

    assert_span(span_client, result, 'apply_async', tags.SPAN_KIND_RPC_CLIENT)
    assert_span(span_server, result, 'run', tags.SPAN_KIND_RPC_SERVER)


@mock.patch(
    'celery.app.task.Task.apply_async', new=celery_hooks._task_apply_async
)
def _test_with_regular_client(celery, tracer, task_error):
    before_task_publish.disconnect(celery_hooks.before_task_publish_handler)
    try:
        result = _test_foo_task(celery, task_error)

        spans = tracer.recorder.get_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.parent_id is None
        assert_span(span, result, 'run', tags.SPAN_KIND_RPC_SERVER)
    finally:
        before_task_publish.connect(celery_hooks.before_task_publish_handler)


TEST_METHODS = _test_with_instrumented_client, _test_with_regular_client


def is_rabbitmq_running():
    try:
        Connection('amqp://guest:guest@127.0.0.1:5672//').connect()
        return True
    except:
        return False


@pytest.mark.skipif(not is_rabbitmq_running(),
                    reason='RabbitMQ is not running or cannot connect')
@pytest.mark.parametrize('task_error', (False, True))
@pytest.mark.parametrize('test_method', TEST_METHODS)
def test_celery_with_rabbitmq(test_method, tracer, task_error):
    celery = Celery(
        'test',

        # For Celery 3.x we have to use rpc:// to get the results
        # because with Redis we can get only PENDING for the status.
        # For Celery 4.x we need redis:// since with RPC we can
        # correctly assert status only for the first one task.
        # Feel free to suggest a better solution here.
        backend='rpc://' if CELERY_3 else 'redis://',

        # avoiding CDeprecationWarning
        changes={
            'CELERY_ACCEPT_CONTENT': ['pickle', 'json'],
        }
    )

    @after_task_publish.connect
    def run_worker(**kwargs):
        celery_worker_state.should_stop = False
        after_task_publish.disconnect(run_worker)
        worker = celery.Worker(concurrency=1,
                               pool_cls='solo',
                               use_eventloop=False,
                               prefetch_multiplier=1,
                               quiet=True,
                               without_heartbeat=True)

        @task_postrun.connect
        def stop_worker_soon(**kwargs):
            celery_worker_state.should_stop = True
            task_postrun.disconnect(stop_worker_soon)
            if hasattr(worker.consumer, '_pending_operations'):
                # Celery 4.x

                def stop_worker():
                    # avoiding AttributeError that makes tests noisy
                    worker.consumer.connection.drain_events = mock.Mock()

                    worker.stop()

                # worker must be stopped not earlier than
                # data exchange with RabbitMQ is completed
                worker.consumer._pending_operations.insert(0, stop_worker)
            else:
                # Celery 3.x
                worker.stop()

        worker.start()

    test_method(celery, tracer, task_error)


@pytest.fixture
def celery_eager():
    celery = Celery('test')
    celery.config_from_object({
        'task_always_eager': True,  # Celery 4.x
        'CELERY_ALWAYS_EAGER': True,  # Celery 3.x
    })
    return celery


@pytest.mark.parametrize('task_error', (False, True))
@pytest.mark.parametrize('test_method', TEST_METHODS)
def test_celery_eager(test_method, celery_eager, tracer, task_error):
    test_method(celery_eager, tracer, task_error)


@mock.patch.object(celery_hooks, 'patcher')
def test_set_custom_patcher(default_patcher):
    patcher = mock.Mock()
    celery_hooks.set_patcher(patcher)

    assert celery_hooks.patcher is not default_patcher
    assert celery_hooks.patcher is patcher

    celery_hooks.install_patches()
    celery_hooks.reset_patches()

    patcher.install_patches.assert_called_once()
    patcher.reset_patches.assert_called_once()
