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


class Span(object):

    def __init__(self):
        self.tags = {}

    def set_tag(self, key, val):
        self.tags[key] = val

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass


class StartSpan(object):

    def __init__(self, span):
        self.kwargs = None
        self.args = None
        self.span = span

    def __call__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.args = args
        return self.span


def spans(monkeypatch):
    span = Span()
    start_span = StartSpan(span)
    monkeypatch.setattr(opentracing.tracer, 'start_span', start_span)
    return span, start_span


def check_span(span, key):
    assert span.tags['redis.key'] == key.encode('string_escape')
    assert span.tags[tags.SPAN_KIND] == tags.SPAN_KIND_RPC_CLIENT
    assert span.tags[tags.PEER_SERVICE] == 'redis'


def test_get(monkeypatch, client, key):
    span, start_span = spans(monkeypatch)
    client.get(key)
    assert start_span.kwargs['operation_name'] == 'redis:GET'
    check_span(span, key)


def test_set(monkeypatch, client, key):
    span, start_span = spans(monkeypatch)
    client.set(key, VAL)
    assert start_span.kwargs['operation_name'] == 'redis:SET'
    check_span(span, key)
    assert client.get(key) == VAL


def test_setex(monkeypatch, client, key):
    span, start_span = spans(monkeypatch)
    client.setex(key, 60, VAL)
    assert start_span.kwargs['operation_name'] == 'redis:SETEX'
    check_span(span, key)
    assert client.get(key) == VAL


def test_setnx(monkeypatch, client, key):
    span, start_span = spans(monkeypatch)
    client.setnx(key, VAL)
    assert start_span.kwargs['operation_name'] == 'redis:SETNX'
    check_span(span, key)
    assert client.get(key) == VAL


def test_key_is_cleared(monkeypatch, client, key):
    # first do a GET that sets the key
    span, start_span = spans(monkeypatch)
    client.get(key)
    assert span.tags['redis.key'] == key

    # now do an ECHO, and make sure redis.key is not used
    span, start_span = spans(monkeypatch)
    client.echo('hello world')
    assert 'redis.key' not in span.tags
