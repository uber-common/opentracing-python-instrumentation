import os
from importlib import import_module

import pytest

from opentracing_instrumentation.client_hooks import install_all_patches


HOOKS_WITH_PATCHERS = ('boto3', 'celery', 'mysqldb', 'sqlalchemy', 'requests')


@pytest.mark.skipif(os.environ.get('TEST_MISSING_MODULES_HANDLING') != '1',
                    reason='Not this time')
def test_missing_modules_handling():
    install_all_patches()
    for name in HOOKS_WITH_PATCHERS:
        hook_module = import_module(
            'opentracing_instrumentation.client_hooks.' + name
        )
        assert not hook_module.patcher.applicable
