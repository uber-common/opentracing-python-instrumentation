from __future__ import absolute_import

import opentracing
from opentracing.ext import tags

from ..request_context import get_current_span, span_in_context
from ._patcher import Patcher


try:
    from celery.app.task import Task
    from celery.signals import (
        before_task_publish, task_prerun, task_success, task_failure
    )
except ImportError:  # pragma: no cover
    pass
else:
    _task_apply_async = Task.apply_async


def task_apply_async_wrapper(task, args=None, kwargs=None, **other_kwargs):
    operation_name = 'Celery:apply_async:{}'.format(task.name)
    span = opentracing.tracer.start_span(operation_name=operation_name,
                                         child_of=get_current_span())
    set_common_tags(span, task, tags.SPAN_KIND_RPC_CLIENT)

    with span_in_context(span), span:
        result = _task_apply_async(task, args, kwargs, **other_kwargs)
        span.set_tag('celery.task_id', result.task_id)
        return result


def set_common_tags(span, task, span_kind):
    span.set_tag(tags.SPAN_KIND, span_kind)
    span.set_tag(tags.COMPONENT, 'Celery')
    span.set_tag('celery.task_name', task.name)


def before_task_publish_handler(headers, **kwargs):
    headers['parent_span_context'] = span_context = {}
    opentracing.tracer.inject(span_context=get_current_span().context,
                              format=opentracing.Format.TEXT_MAP,
                              carrier=span_context)


def task_prerun_handler(task, task_id, **kwargs):
    request = task.request

    operation_name = 'Celery:run:{}'.format(task.name)
    child_of = None
    if request.delivery_info.get('is_eager'):
        child_of = get_current_span()
    else:
        if hasattr(request, 'headers'):
            # Celery 3.x
            parent_span_context = (
                request.headers and request.headers.get('parent_span_context')
            )
        else:
            # Celery 4.x
            parent_span_context = getattr(request, 'parent_span_context', None)

        if parent_span_context:
            child_of = opentracing.tracer.extract(
                opentracing.Format.TEXT_MAP, parent_span_context
            )

    task.request.span = span = opentracing.tracer.start_span(
        operation_name=operation_name,
        child_of=child_of,
    )
    set_common_tags(span, task, tags.SPAN_KIND_RPC_SERVER)
    span.set_tag('celery.task_id', task_id)

    request.tracing_context = span_in_context(span)
    request.tracing_context.__enter__()


def finish_current_span(task, exc_type=None, exc_val=None, exc_tb=None):
    task.request.span.finish()
    task.request.tracing_context.__exit__(exc_type, exc_val, exc_tb)


def task_success_handler(sender, **kwargs):
    finish_current_span(task=sender)


def task_failure_handler(sender, exception, traceback, **kwargs):
    finish_current_span(
        task=sender,
        exc_type=type(exception),
        exc_val=exception,
        exc_tb=traceback,
    )


class CeleryPatcher(Patcher):
    applicable = '_task_apply_async' in globals()

    def _install_patches(self):
        Task.apply_async = task_apply_async_wrapper
        before_task_publish.connect(before_task_publish_handler)
        task_prerun.connect(task_prerun_handler)
        task_success.connect(task_success_handler)
        task_failure.connect(task_failure_handler)

    def _reset_patches(self):
        Task.apply_async = _task_apply_async
        before_task_publish.disconnect(before_task_publish_handler)
        task_prerun.disconnect(task_prerun_handler)
        task_success.disconnect(task_success_handler)
        task_failure.disconnect(task_failure_handler)


patcher = CeleryPatcher()


def set_patcher(custom_patcher):
    global patcher
    patcher = custom_patcher


def install_patches():
    patcher.install_patches()


def reset_patches():
    patcher.reset_patches()
