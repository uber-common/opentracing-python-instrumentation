from __future__ import absolute_import
import logging

from opentracing.ext import tags
from tornado.stack_context import wrap as keep_stack_context

from opentracing_instrumentation import utils
from ..request_context import get_current_span, span_in_stack_context
from ._patcher import Patcher


try:
    from boto3.resources.action import ServiceAction
    from boto3.s3 import inject as s3_functions
    from botocore import xform_name
    from botocore.client import BaseClient
    from botocore.exceptions import ClientError
    from s3transfer.futures import BoundedExecutor
except ImportError:
    pass
else:
    _service_action_call = ServiceAction.__call__
    _client_make_api_call = BaseClient._make_api_call
    _Executor = BoundedExecutor.EXECUTOR_CLS

logger = logging.getLogger(__name__)


class Boto3Patcher(Patcher):
    applicable = '_service_action_call' in globals()

    S3_FUNCTIONS_TO_INSTRUMENT = (
        'copy',
        'download_file',
        'download_fileobj',
        'upload_file',
        'upload_fileobj',
    )

    def __init__(self):
        super(Boto3Patcher, self).__init__()
        self.s3_original_funcs = {}

    def _install_patches(self):
        ServiceAction.__call__ = self._get_service_action_call_wrapper()
        BaseClient._make_api_call = self._get_client_make_api_call_wrapper()
        BoundedExecutor.EXECUTOR_CLS = self._get_instrumented_executor_cls()
        for func_name in self.S3_FUNCTIONS_TO_INSTRUMENT:
            func = getattr(s3_functions, func_name, None)
            if func:
                self.s3_original_funcs[func_name] = func
                func_wrapper = self._get_s3_call_wrapper(func)
                setattr(s3_functions, func_name, func_wrapper)
            else:
                logging.warning('S3 function %s not found', func_name)

    def _reset_patches(self):
        ServiceAction.__call__ = _service_action_call
        BaseClient._make_api_call = _client_make_api_call
        BoundedExecutor.EXECUTOR_CLS = _Executor
        for func_name, original_func in self.s3_original_funcs.items():
            setattr(s3_functions, func_name, original_func)

    @staticmethod
    def set_request_id_tag(span, response):
        metadata = response.get('ResponseMetadata')

        # there is no ResponseMetadata for
        # boto3:dynamodb:describe_table
        if metadata:
            request_id = metadata.get('RequestId')

            # when using boto3.client('s3')
            # instead of boto3.resource('s3'),
            # there is no RequestId for
            # boto3:s3:CreateBucket
            if request_id:
                span.set_tag('aws.request_id', request_id)

    def _get_service_action_call_wrapper(self):
        def service_action_call_wrapper(service, parent, *args, **kwargs):
            """Wraps ServiceAction.__call__"""

            service_name = parent.meta.service_name
            operation_name = xform_name(
                service._action_model.request.operation
            )

            return self.perform_call(
                _service_action_call, 'resource',
                service_name, operation_name,
                service, parent, *args, **kwargs
            )

        return service_action_call_wrapper

    def _get_client_make_api_call_wrapper(self):
        def make_api_call_wrapper(client, operation_name, api_params):
            """Wraps BaseClient._make_api_call"""

            service_name = client._service_model.service_name
            formatted_operation_name = xform_name(operation_name)

            return self.perform_call(
                _client_make_api_call, 'client',
                service_name, formatted_operation_name,
                client, operation_name, api_params
            )

        return make_api_call_wrapper

    def _get_s3_call_wrapper(self, original_func):
        operation_name = original_func.__name__

        def s3_call_wrapper(*args, **kwargs):
            """Wraps __call__ of S3 client methods"""

            return self.perform_call(
                original_func, 'client', 's3', operation_name, *args, **kwargs
            )

        return s3_call_wrapper

    def perform_call(self, original_func, kind, service_name, operation_name,
                     *args, **kwargs):
        span = utils.start_child_span(
            operation_name='boto3:{}:{}:{}'.format(
                kind, service_name, operation_name
            ),
            parent=get_current_span()
        )

        span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
        span.set_tag(tags.COMPONENT, 'boto3')
        span.set_tag('boto3.service_name', service_name)

        with span, span_in_stack_context(span):
            try:
                response = original_func(*args, **kwargs)
            except ClientError as error:
                self.set_request_id_tag(span, error.response)
                raise
            else:
                if isinstance(response, dict):
                    self.set_request_id_tag(span, response)

        return response

    def _get_instrumented_executor_cls(self):
        class InstrumentedExecutor(_Executor):
            def submit(self, task, *args, **kwargs):
                return super(InstrumentedExecutor, self).submit(
                    keep_stack_context(task), *args, **kwargs
                )

        return InstrumentedExecutor


Boto3Patcher.configure_hook_module(globals())
