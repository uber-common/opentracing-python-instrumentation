import sys

import pytest

from opentracing.ext import tags
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from opentracing_instrumentation.client_hooks import mysqldb as mysqldb_hooks
from opentracing_instrumentation.request_context import span_in_context
from .sql_common import metadata, User


SKIP_REASON_PYTHON_3 = 'MySQLdb is not compatible with Python 3'
SKIP_REASON_CONNECTION = 'MySQL is not running or cannot connect'
MYSQL_CONNECTION_STRING = 'mysql://root@127.0.0.1/test'


@pytest.fixture
def session():
    Session = sessionmaker()
    engine = create_engine(MYSQL_CONNECTION_STRING)
    Session.configure(bind=engine)
    metadata.create_all(engine)
    try:
        yield Session()
    except:
        pass


@pytest.fixture(autouse=True, scope='module')
def patch_sqlalchemy():
    mysqldb_hooks.install_patches()
    try:
        yield
    finally:
        mysqldb_hooks.reset_patches()


def is_mysql_running():
    try:
        import MySQLdb
        with MySQLdb.connect(host='127.0.0.1', user='root'):
            pass
        return True
    except:
        return False


def assert_span(span, operation, parent=None):
    assert span.operation_name == 'MySQLdb:' + operation
    assert span.tags.get(tags.SPAN_KIND) == tags.SPAN_KIND_RPC_CLIENT
    if parent:
        assert span.parent_id == parent.context.span_id
        assert span.context.trace_id == parent.context.trace_id
    else:
        assert span.parent_id is None


@pytest.mark.skipif(not is_mysql_running(), reason=SKIP_REASON_CONNECTION)
@pytest.mark.skipif(sys.version_info.major == 3, reason=SKIP_REASON_PYTHON_3)
def test_db(tracer, session):
    root_span = tracer.start_span('root-span')

    # span recording works for regular operations within a context only
    with span_in_context(root_span):
        user = User(name='user', fullname='User', password='password')
        session.add(user)
        session.commit()

    spans = tracer.recorder.get_spans()
    assert len(spans) == 4

    connect_span, insert_span, commit_span, rollback_span = spans
    assert_span(connect_span, 'Connect')
    assert_span(insert_span, 'INSERT', root_span)
    assert_span(commit_span, 'commit', root_span)
    assert_span(rollback_span, 'rollback', root_span)
