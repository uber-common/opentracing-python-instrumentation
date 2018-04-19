from setuptools import setup, find_packages


setup(
    name='opentracing_instrumentation',
    version='2.4.1',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    description='Tracing Instrumentation using OpenTracing API (http://opentracing.io)',
    license='MIT',
    url='https://github.com/uber-common/opentracing-python-instrumentation',
    keywords=['opentracing'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'future',
        'wrapt',
        'tornado>=4.1,<5',
        'contextlib2',
        'opentracing>=1.1,<2',
        'six',
    ],
    extras_require={
        'tests': [
            'coveralls',
            'doubles',
            'flake8<3',  # see https://github.com/zheller/flake8-quotes/issues/29
            'flake8-quotes',
            'mock<1.1.0',
            'pytest>=3.0.0',
            'pytest-cov',
            'pytest-localserver',
            'pytest-mock',
            'pytest-tornado',
            'basictracer>=2.1,<2.2',
            'redis',
            'Sphinx',
            'sphinx_rtd_theme',
        ]
    },
)
