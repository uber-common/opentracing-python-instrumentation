[![PyPI version][pypi-img]][pypi] [![Build Status][ci-img]][ci]

# opentracing-python-instrumentation

A collection of instrumentation tools to enable tracing with 
[OpenTracing API](http://opentracing.github.io).

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

Here's an example of a middleware for 
[Clay framework](https://github.com/uber/clay):

```python

from opentracing_instrumentation.request_context import RequestContextManager
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
                span.add_tag('error', str(exc_info))
            span.finish()

            return start_response(status, response_headers)

        with RequestContextManager(span=span):
            return other_wsgi(environ, start_response_wrapper)

    return wsgi_tracing_middleware
```

And here's an example for middleware in Tornado-based app:

```python
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
    def mgr():
        return RequestContextManager(span)

    with tornado.stack_context.StackContext(mgr):
        return func(*args, **kwargs)
```

## Development

```
virtualenv env
source env/bin/activate
make bootstrap
make test
```

## Releases

Before new release, add a summary of changes since last version to CHANGELOG.rst

```
pip install zest.releaser[recommended]
prerelease
release
git push origin master --follow-tags
python setup.py sdist upload -r pypi
postrelease
git push
```

[ci-img]: https://travis-ci.org/uber-common/opentracing-python-instrumentation.svg?branch=master
[ci]: https://travis-ci.org/uber-common/opentracing-python-instrumentation
[pypi-img]: https://img.shields.io/pypi/v/opentracing_instrumentation.svg
[pypi]: https://pypi.python.org/pypi/opentracing_instrumentation
