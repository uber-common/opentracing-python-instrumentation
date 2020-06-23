## Release process

Before new release, add a summary of changes since last version to CHANGELOG.rst

```shell
pip install 'zest.releaser[recommended]'
prerelease
release
git push origin master --follow-tags
```

At this point Travis should start a [build][] for the version tag and the last step
`Python: 3.7 CELERY=4 COVER=1` should upload the release to [pypi][].

Once that's done, switch back to development:

```shell
postrelease
git push
```

[build]: https://travis-ci.org/uber-common/opentracing-python-instrumentation
[pypi]: https://pypi.org/project/opentracing-instrumentation/

