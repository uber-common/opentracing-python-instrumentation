.. :changelog:

History
-------

0.3.6 (unreleased)
------------------

- Nothing changed yet.


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
