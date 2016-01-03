from setuptools import setup


setup(
    name='opentracing_instrumentation',
    version='0.1.1.dev0',
    author='Yuri Shkuro',
    author_email='ys@uber.com',
    description='Tracing Instrumentation using OpenTracing API',
    license='MIT',
    #url='https://github.com/uber-common/opentracing-python-instrumentation',
    keywords=['opentracing'],
    classifiers=[
        'Development Status :: Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=['opentracing_instrumentation'],
    include_package_data=True,
    platforms='any',
    install_requires=[
        'futures',
        'tornado>=4.1',
        'opentracing>=0.3.1,<1.0.0',
    ],
    extras_require={
        'tests': [
            'doubles',
            'flake8',
            'flake8-quotes',
            'mock<1.1.0',
            'pytest',
            'pytest-cov',
            'pytest-mock',
            'Sphinx',
            'sphinx_rtd_theme',
        ]
    },
)
