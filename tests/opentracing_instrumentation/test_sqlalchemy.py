import pytest

from opentracing.ext import tags
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from opentracing_instrumentation.client_hooks import (
    sqlalchemy as sqlalchemy_hooks
)
from .sql_common import metadata, User


@pytest.fixture
def session():
    Session = sessionmaker()
    engine = create_engine("sqlite://")
    Session.configure(bind=engine)
    metadata.create_all(engine)
    try:
        yield Session()
    except:
        pass


@pytest.fixture(autouse=True, scope='module')
def patch_sqlalchemy():
    sqlalchemy_hooks.install_patches()
    try:
        yield
    finally:
        sqlalchemy_hooks.reset_patches()


def assert_span(span, operation):
    assert span.operation_name == 'SQL ' + operation
    assert span.tags.get(tags.SPAN_KIND) == tags.SPAN_KIND_RPC_CLIENT


def test_db(tracer, session):
    user = User(name='user', fullname='User', password='password')
    session.add(user)
    session.commit()

    spans = tracer.recorder.get_spans()
    assert len(spans) == 4

    pragma_span_1, pragma_span_2, create_span, insert_span = spans
    assert_span(pragma_span_1, 'PRAGMA')
    assert_span(pragma_span_2, 'PRAGMA')
    assert_span(create_span, 'CREATE')
    assert_span(insert_span, 'INSERT')
