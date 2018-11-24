.. :changelog:

History
-------

2.5.0 (unreleased)
------------------

- Add support for Python 3.7
- Drop support of Python 3.3
- Update the requirements
- Fix flake8 warnings


2.4.3 (2018-08-24)
------------------

- Fix Makefile to check Python version to determine setuptools version (#62)
- Fix gettattr for ContextManagerConnectionWrapper (#63)


2.4.2 (2018-08-03)
------------------

- Fix wrapper for psycopg2 connection so type check does not fail (#55)


2.4.1 (2018-04-19)
------------------

- Remove dependency on 'futures' (#47)


2.4.0 (2018-01-09)
------------------

- Add client hooks for psycopg2 (#39)


2.3.0 (2017-10-25)
------------------

- Futurize to support Python 3
- Add interceptor support to ``opentracing_instrumentation.http_client``
- Add function to install interceptors from list


2.2.0 (2016-10-04)
------------------

- Upgrade to opentracing 1.2 with KV logging


2.1.0 (2016-09-08)
------------------

- Remove url encoding/decoding when using HTTP_HEADERS codecs


2.0.3 (2016-08-11)
------------------

- Match redis.set() signature


2.0.2 (2016-08-10)
------------------

- Fix monkeypatched argument names in redis hooks


2.0.1 (2016-08-09)
------------------

- Correct API in strict_redis patcher.


2.0.0 (2016-08-07)
------------------

- Upgrade to OpenTracing API 1.1 with SpanContext


1.4.1 (2016-08-07)
------------------

- Fix relative import


1.4.1 (2016-08-07)
------------------

- Fix relative import


1.4.0 (2016-08-02)
------------------

- Add more information to Redis hooks


1.3.0 (2016-07-29)
------------------

- Add Redis hooks


1.2.0 (2016-07-19)
------------------

- Add config-based client_hooks patching


1.1.1 (2016-07-14)
------------------

- Support backwards compatible usage of RequestContextManager with span argument


1.1.0 (2016-06-09)
------------------

- Change request context from Span to a wrapper object RequestContext


1.0.1 (2016-06-06)
------------------

- Apply URL quote/unquote to values stored in the headers


1.0.0 (2016-05-24)
------------------

- Upgrade to OpenTracing API 1.0rc4


0.4.2 (2016-03-28)
------------------

- Work around uWSGI collecting wsgi_environ.iteritems() during iteration


0.4.1 (2016-03-03)
------------------

- Fix memory leak in SQL instrumentation


0.4.0 (2016-02-26)
------------------

- Replace Tornado's StackContext with ThreadSafeStackContext


0.3.11 (2016-02-06)
-------------------

- Add instrumentation for `requests` library


0.3.9 (2016-02-04)
------------------

- Set SPAN_KIND tag for all RPC spans.
- Allow traced_function to start a trace.


0.3.8 (2016-01-22)
------------------

- Check if MySQLdb can be imported before trying to instrument it.


0.3.7 (2016-01-22)
------------------

- Expose `client_hooks.install_all_patches` convenience method


0.3.6 (2016-01-20)
------------------

- Merge traced_function/traced_coroutine into a single decorator, with custom on-start hook


0.3.5 (2016-01-17)
------------------

- Upgrade to latest OpenTracing (change add_tag to set_tag)
- Add decorators for functions and Tornado coroutines
- Clean-up premature conversion to str and use span.error() for reporting errors


0.3.4 (2016-01-13)
------------------

- Bug fix for empty context manager when there is no parent span.


0.3.3 (2016-01-11)
------------------

- Set upper bound on opentracing version


0.3.2 (2016-01-11)
------------------

- Use wrapt.ObjectProxy to ensure all methods from wrapped connection/cursor are exposed


0.3.1 (2016-01-08)
------------------

- Add support for mysql-python, with a general framework for PEP-249 drivers


0.2.0 (2016-01-06)
------------------

- Upgrade to OpenTracing API 0.4.x


0.1.1 (2016-01-02)
------------------

- Use findpackages


0.1.0 (2016-01-02)
------------------

- Initial version
