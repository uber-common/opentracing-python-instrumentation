from setuptools import setup, find_packages


setup(
    name='opentracing_instrumentation',
    version='2.2.0',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    description='Tracing Instrumentation using OpenTracing API (http://opentracing.io)',
    license='MIT',
    url='https://github.com/uber-common/opentracing-python-instrumentation',
    keywords=['opentracing'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'futures',
        'wrapt',
        'tornado>=4.1',
        'contextlib2',
        'opentracing>=1.1,<1.3',
    ],
    extras_require={
        'tests': [
            'doubles',
            'flake8<3',  # see https://github.com/zheller/flake8-quotes/issues/29
            'flake8-quotes',
            'mock<1.1.0',
            'pytest>=2.7',
            'pytest-cov',
            'pytest-mock',
            'pytest-tornado',
            'basictracer>=2.1,<2.2',
            'redis',
            'Sphinx',
            'sphinx_rtd_theme',
        ]
    },
)
