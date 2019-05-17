# Copyright (c) 2018,2019 Uber Technologies, Inc.
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

import mock
import psycopg2 as psycopg2_client
import pytest
from psycopg2 import extensions as pg_extensions, sql
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.orm import mapper, sessionmaker

from opentracing_instrumentation.client_hooks import psycopg2


SKIP_REASON = 'Postgres is not running or cannot connect'
POSTGRES_CONNECTION_STRING = 'postgresql://localhost/travis_ci_test'


@pytest.fixture
def engine():
    try:
        yield create_engine(POSTGRES_CONNECTION_STRING)
    except:
        pass


@pytest.fixture
def session():
    Session = sessionmaker()
    Session.configure(bind=engine)
    try:
        yield Session()
    except:
        pass


@pytest.fixture(autouse=True)
def patch_postgres():
    psycopg2.install_patches()


metadata = MetaData()
user = Table('user', metadata,
             Column('id', Integer, primary_key=True),
             Column('name', String(50)),
             Column('fullname', String(50)),
             Column('password', String(12)))


class User(object):

    def __init__(self, name, fullname, password):
        self.name = name
        self.fullname = fullname
        self.password = password


mapper(User, user)


@pytest.fixture()
def connection():
    return psycopg2_client.connect(POSTGRES_CONNECTION_STRING)


def is_postgres_running():
    try:
        with psycopg2_client.connect(POSTGRES_CONNECTION_STRING):
            pass
        return True
    except:
        return False


@pytest.mark.skipif(not is_postgres_running(), reason=SKIP_REASON)
def test_db(tracer, engine, session):
    metadata.create_all(engine)
    user1 = User(name='user1', fullname='User 1', password='password')
    user2 = User(name='user2', fullname='User 2', password='password')
    session.add(user1)
    session.add(user2)
    # If the test does not raised an error, it is passing


@pytest.mark.skipif(not is_postgres_running(), reason=SKIP_REASON)
def test_connection_proxy(connection):
    assert isinstance(connection, psycopg2.ConnectionWrapper)

    # Test that connection properties are proxied by
    # ContextManagerConnectionWrapper
    assert connection.closed == 0


def _test_register_type(connection):
    assert not connection.string_types

    test_type = pg_extensions.UNICODE
    pg_extensions.register_type(test_type, connection)

    assert connection.string_types
    for string_type in connection.string_types.values():
        assert string_type is test_type


@pytest.mark.skipif(not is_postgres_running(), reason=SKIP_REASON)
def test_register_type_for_wrapped_connection(connection):
    _test_register_type(connection)


@pytest.mark.skipif(not is_postgres_running(), reason=SKIP_REASON)
def test_register_type_for_raw_connection(connection):
    _test_register_type(connection.__wrapped__)


@mock.patch.object(psycopg2, 'psycopg2')
@mock.patch.object(psycopg2, 'ConnectionFactory')
def test_install_patches_skip(factory_mock, *mocks):
    del psycopg2.psycopg2
    psycopg2.install_patches.reset()
    psycopg2.install_patches()
    factory_mock.assert_not_called()


@pytest.mark.skipif(not is_postgres_running(), reason=SKIP_REASON)
@pytest.mark.parametrize('sql_object', (str, sql.SQL, sql.Composed))
def test_execute_sql(tracer, engine, session, connection, sql_object):
    metadata.create_all(engine)
    user1 = User(name='user1', fullname='User 1', password='password')
    session.add(user1)
    with tracer.start_active_span('test') as scope:
        trace_id = str(scope.span.context.trace_id)
        cur = connection.cursor()
        query = '''SELECT %s;'''
        if sql_object is sql.SQL:
            query = sql_object(query)
        if sql_object is sql.Composed:
            query = sql_object([sql.SQL(query)])
        cur.execute(query, (trace_id, ))
        assert cur.fetchall() == [(trace_id, )]
