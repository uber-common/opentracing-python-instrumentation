# Copyright (c) 2015 Uber Technologies, Inc.
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

from __future__ import absolute_import
import mock
from opentracing_instrumentation.http_server import WSGIRequestWrapper


def test_creates_instance():
    wsgi_environ = {
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '8888',
        'REQUEST_METHOD': 'GET',
        'PATH_INFO': '/Farnsworth',
        'HTTP_X_FOO': 'bar',
        'REMOTE_ADDR': 'localhost',
        'REMOTE_PORT': '80',
        'wsgi.url_scheme': 'http'
    }
    request = WSGIRequestWrapper.from_wsgi_environ(wsgi_environ)

    assert request.server_port == '8888'
    assert request.method == 'GET'
    assert request.headers.get('x-foo') == 'bar'
    assert request.remote_ip == 'localhost'
    assert request.remote_port == '80'
    assert request.full_url == 'http://localhost:8888/Farnsworth'
    assert request.caller_name is None

    wsgi_environ['SERVER_PORT'] = 8888  # int is also acceptable
    request = WSGIRequestWrapper.from_wsgi_environ(wsgi_environ)
    assert request.server_port == 8888


def test_url():
    environ = {
        'wsgi.url_scheme': 'http',
        'HTTP_HOST': 'bender.com'
    }
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'http://bender.com'

    environ = {
        'wsgi.url_scheme': 'http',
        'SERVER_NAME': 'bender.com',
        'SERVER_PORT': '80'
    }
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'http://bender.com'

    environ['SERVER_PORT'] = '8888'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'http://bender.com:8888'

    environ['wsgi.url_scheme'] = 'https'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'https://bender.com:8888'

    environ['SERVER_PORT'] = '443'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'https://bender.com'

    environ['SCRIPT_NAME'] = '/Farnsworth'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'https://bender.com/Farnsworth'

    environ['PATH_INFO'] = '/PlanetExpress'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == 'https://bender.com/Farnsworth/PlanetExpress'

    environ['QUERY_STRING'] = 'Bender=antiquing'
    request = WSGIRequestWrapper.from_wsgi_environ(environ)
    assert request.full_url == \
        'https://bender.com/Farnsworth/PlanetExpress?Bender=antiquing'


def test_caller():
    environ = {
        'HTTP_Custom-Caller-Header': 'Zapp',
    }
    from opentracing_instrumentation import config

    with mock.patch.object(config.CONFIG, 'caller_name_headers',
                           ['XXX', 'Custom-Caller-Header']):
        request = WSGIRequestWrapper.from_wsgi_environ(environ)
        assert request.caller_name == 'Zapp'

    environ['HTTP_XXX'] = 'DOOP'
    with mock.patch.object(config.CONFIG, 'caller_name_headers',
                           ['XXX', 'Custom-Caller-Header']):
        request = WSGIRequestWrapper.from_wsgi_environ(environ)
        # header XXX is earlier in the list ==> higher priority
        assert request.caller_name == 'DOOP'
