[![PyPI version][pypi-img]][pypi] [![Build Status][ci-img]][ci] [![Coverage Status][cov-img]][cov]

# opentracing-python-instrumentation

A collection of instrumentation tools to enable tracing with 
[OpenTracing API](http://opentracing.io).

## Module

Make sure you are running recent enough versions of `pip` and `setuptools`, e.g. before installing your project requirements execute this:

```
pip install --upgrade "setuptools>=29" "pip>=9"
```

The module name is `opentracing_instrumentation`.

## What's inside

### Supported client frameworks

The following libraries are instrumented for tracing in this module:
 * [boto3](https://github.com/boto/boto3) — AWS SDK for Python
 * [Celery](https://github.com/celery/celery) — Distributed Task Queue
 * `urllib2`
 * `requests`
 * `SQLAlchemy`
 * `MySQLdb`
 * `psycopg2`
 * Tornado HTTP client
 *  `redis`

### Server instrumentation

For inbound requests a helper function `before_request` is provided for creating middleware for frameworks like Flask and uWSGI.

### Manual instrumentation

Finally, a `@traced_function` decorator is provided for manual instrumentation.

### In-process Context Propagation

As part of the OpenTracing 2.0 API, in-process `Span` propagation happens through the newly defined
[ScopeManager](https://opentracing-python.readthedocs.io/en/latest/api.html#scope-managers)
interface. However, the existing functionality has been kept to provide backwards compatibility and
ease code migration:

`span_in_context()` implements context propagation using the current `opentracing.tracer.scope_manager`,
expected to be a thread-local based `ScopeManager`, such as `opentracing.scope_managers.ThreadLocalScopeManager`.

`span_in_stack_context()` implements context propagation for Tornado applications
using the current `opentracing.tracer.scope_manager` too, expected to be an instance of
 `opentracing.scope_managers.tornado.TornadoScopeManager`.

`get_current_span()` returns the currently active `Span`, if any.

Direct access to the `request_context` module as well as usage of `RequestContext` and `RequestContextManager`
have been **fully** deprecated, as they do not integrate with the new OpenTracing 2.0 API.
Using them along `get_current_span()` is guaranteed to work, but it is **highly** recommended
to switch to the previously mentioned functions.

## Usage

This library provides two types of instrumentation, explicit instrumentation
for server endpoints, and implicit instrumentation for client call sites.

Server endpoints are instrumented by creating a middleware class that:

 1. initializes the specific tracer implementation
 2. wraps incoming request handlers into a method that reads the incoming
    tracing info from the request and creates a new tracing Span

Client call sites are instrumented implicitly by executing a set of 
available `client_hooks` that monkey-patch some API points in several 
common libraries like `SQLAlchemy`, `urllib2`, Tornado Async HTTP Client.
The initialization of those hooks is usually also done from the middleware
class's `__init__` method.

There is a client-server example using this library with Flask instrumentation
from opentracing-contrib: https://github.com/opentracing-contrib/python-flask/tree/master/example.

Here's an example of a middleware for [Clay framework](https://github.com/uber/clay):

```python

from opentracing_instrumentation import span_in_context
from opentracing_instrumentation.http_server import before_request
from opentracing_instrumentation.http_server import WSGIRequestWrapper
from opentracing_instrumentation.client_hooks import install_all_patches


class TracerMiddleware(object):

    def __init__(self, app, wsgi_app):
        self.wsgi_app = wsgi_app
        self.service_name = app.name

        CONFIG.app_name = self.service_name
        CONFIG.caller_name_headers.append('X-Uber-Source')
        CONFIG.callee_endpoint_headers.append('X-Uber-Endpoint')

        install_all_patches()
        self.wsgi_app = create_wsgi_middleware(wsgi_app)
        self.init_tracer()

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def init_tracer(self):
        # code specific to your tracer implementation
        pass


def create_wsgi_middleware(other_wsgi, tracer=None):
    """
    Create a wrapper middleware for another WSGI response handler.
    If tracer is not passed in, 'opentracing.tracer' is used.
    """

    def wsgi_tracing_middleware(environ, start_response):
        # TODO find out if the route can be retrieved from somewhere

        request = WSGIRequestWrapper.from_wsgi_environ(environ)
        span = before_request(request=request, tracer=tracer)

        # Wrapper around the real start_response object to log
        # additional information to opentracing Span
        def start_response_wrapper(status, response_headers, exc_info=None):
            if exc_info is not None:
                span.set_tag('error', str(exc_info))
            span.finish()

            return start_response(status, response_headers)

        with span_in_context(span):
            return other_wsgi(environ, start_response_wrapper)

    return wsgi_tracing_middleware
```

And here's an example for middleware in Tornado-based app:

```python

import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager
from opentracing_instrumentation import span_in_stack_context


opentracing.tracer = MyOpenTracingTracer(scope_manager=TornadoScopeManager())


class TracerMiddleware(object):

    def __init__(self):
        # perform initialization similar to above, including installing
        # the client_hooks
        
    @gen.coroutine
    def __call__(self, request, handler, next_mw):
        request_wrapper = http_server.TornadoRequestWrapper(request=request)
        span = http_server.before_request(request=request_wrapper)

        @gen.coroutine
        def next_middleware_with_span():
            yield next_mw()

        yield run_coroutine_with_span(span=span,
                                      func=next_middleware_with_span)

        span.finish()


def run_coroutine_with_span(span, func, *args, **kwargs):
    """Wrap the execution of a Tornado coroutine func in a tracing span.

    This makes the span available through the get_current_span() function.

    :param span: The tracing span to expose.
    :param func: Co-routine to execute in the scope of tracing span.
    :param args: Positional args to func, if any.
    :param kwargs: Keyword args to func, if any.
    """
    with span_in_stack_context(span):
        return func(*args, **kwargs)
```

### Customization

For the `requests` library, in case you want to set custom tags
to spans depending on content or some metadata of responses,
you can set `response_handler_hook`.
The hook must be a method with a signature `(response, span)`,
where `response` and `span` are positional arguments,
so you can use different names for them if needed.

```python
from opentracing_instrumentation.client_hooks.requests import patcher


def hook(response, span):
    if not response.ok:
        span.set_tag('error', 'true')


patcher.set_response_handler_hook(hook)
```

If you have issues with getting the parent span, it is possible to override
default function that retrieves parent span. 

```python 
from opentracing_instrumentation.client_hooks import install_all_patches,
     set_current_span_func

set_current_span_func(my_custom_extractor_func)
install_all_patches()

``` 

## Development

`PostgreSQL`, `RabbitMQ`, `Redis`, and `DynamoDB` are required for certain tests.

```bash
docker-compose up -d
```

To prepare a development environment please execute the following commands.
```bash
virtualenv env
source env/bin/activate
make bootstrap
make test
```

You can use [tox](https://tox.readthedocs.io) to run tests as well.
```bash
tox
```

[ci-img]: https://travis-ci.org/uber-common/opentracing-python-instrumentation.svg?branch=master
[ci]: https://travis-ci.org/uber-common/opentracing-python-instrumentation
[pypi-img]: https://img.shields.io/pypi/v/opentracing_instrumentation.svg
[pypi]: https://pypi.python.org/pypi/opentracing_instrumentation
[cov-img]: https://coveralls.io/repos/github/uber-common/opentracing-python-instrumentation/badge.svg
[cov]: https://coveralls.io/github/uber-common/opentracing-python-instrumentation
