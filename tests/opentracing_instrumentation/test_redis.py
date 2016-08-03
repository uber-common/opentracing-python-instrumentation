# Copyright (c) 2016 Uber Technologies, Inc.
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

import contextlib
import mock
import redis
import os

import opentracing
from opentracing.ext import tags

from opentracing_instrumentation.client_hooks import strict_redis

import pytest


VAL = 'opentracing is fun and easy!'


@pytest.yield_fixture(autouse=True, scope='module')
def patch_redis():
    strict_redis.install_patches()
    try:
        yield
    finally:
        strict_redis.reset_patches()


@pytest.fixture()
def client():
    return redis.StrictRedis()


@pytest.fixture()
def key():
    return os.urandom(8).encode('hex')


@contextlib.contextmanager
def mock_span():
    tracer = opentracing.tracer
    span = mock.MagicMock()

    with mock.patch.object(tracer, 'start_span', return_value=span) as new_span,\
         mock.patch.object(tracer, 'join', return_value=None):
        yield new_span, span


def check_span(span, key):
    span.set_tag.assert_any_call('redis.key', key)
    span.set_tag.assert_any_call(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
    span.set_tag.assert_any_call(tags.PEER_SERVICE, 'redis')


def test_get(client, key):
    with mock_span() as (new_span, span):
        client.get(key)
    new_span.assert_called_with(operation_name='redis:GET', parent=None)
    check_span(span, key)


def test_set(client, key):
    with mock_span() as (new_span, span):
        client.set(key, VAL)
    assert client.get(key) == VAL
    new_span.assert_called_with(operation_name='redis:SET', parent=None)
    check_span(span, key)


def test_setex(client, key):
    with mock_span() as (new_span, span):
        client.setex(key, 60, VAL)
    assert client.get(key) == VAL
    new_span.assert_called_with(operation_name='redis:SETEX', parent=None)
    check_span(span, key)


def test_setnx(client, key):
    with mock_span() as (new_span, span):
        client.setnx(key, VAL)
    assert client.get(key) == VAL
    new_span.assert_called_with(operation_name='redis:SETNX', parent=None)
    check_span(span, key)
