from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='opentracing_instrumentation',
    version='3.0.0',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    description='Tracing Instrumentation using OpenTracing API '
                '(http://opentracing.io)',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    url='https://github.com/uber-common/opentracing-python-instrumentation',
    keywords=['opentracing'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
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
        'opentracing>=2.0,<2.1',
        'six',
    ],
    extras_require={
        'tests': [
            'coveralls',
            'doubles',
            'flake8',
            'flake8-quotes',
            'mock',
            'psycopg2-binary',
            'sqlalchemy>=1.2.0',

            # pytest-tornado isn't compatible with pytest>=4.0.0,
            # see https://github.com/eugeniy/pytest-tornado/pull/38
            'pytest>=3.0.0,<4.0.0',

            'pytest-cov',
            'pytest-localserver',
            'pytest-mock',
            'pytest-tornado',
            'basictracer>=3,<4',
            'redis',
            'Sphinx',
            'sphinx_rtd_theme',
        ]
    },
)
