# Copyright (c) 2015-2017 Uber Technologies, Inc.
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

from collections import Sequence

import importlib
import logging

import six


def install_all_patches():
    """
    A convenience method that installs all available hooks.

    If a specific module is not available on the path, it is ignored.
    """
    from . import mysqldb
    from . import psycopg2
    from . import strict_redis
    from . import sqlalchemy
    from . import tornado_http
    from . import urllib
    from . import urllib2
    from . import requests

    mysqldb.install_patches()
    psycopg2.install_patches()
    strict_redis.install_patches()
    sqlalchemy.install_patches()
    tornado_http.install_patches()
    urllib.install_patches()
    urllib2.install_patches()
    requests.install_patches()


def install_patches(patchers='all'):
    """
    Usually called from middleware to install client hooks
    specified in the client_hooks section of the configuration.

    :param patchers: a list of patchers to run. Acceptable values include:
      * None - installs all client patches
      * 'all' - installs all client patches
      * empty list - does not install any patches
      * list of function names - executes the functions
    """
    if patchers is None or patchers == 'all':
        install_all_patches()
        return
    if not _valid_args(patchers):
        raise ValueError('patchers argument must be None, "all", or a list')

    for patch_func_name in patchers:
        logging.info('Loading client hook %s', patch_func_name)
        patch_func = _load_symbol(patch_func_name)
        logging.info('Applying client hook %s', patch_func_name)
        patch_func()


def install_client_interceptors(client_interceptors=()):
    """
    Install client interceptors for the patchers.

    :param client_interceptors: a list of client interceptors to install.
        Should be a list of classes
    """
    if not _valid_args(client_interceptors):
        raise ValueError('client_interceptors argument must be a list')

    from ..http_client import ClientInterceptors

    for client_interceptor in client_interceptors:
        logging.info('Loading client interceptor %s', client_interceptor)
        interceptor_class = _load_symbol(client_interceptor)
        logging.info('Adding client interceptor %s', client_interceptor)
        ClientInterceptors.append(interceptor_class())


def _valid_args(value):
    return isinstance(value, Sequence) and \
        not isinstance(value, six.string_types)


def _load_symbol(name):
    """Load a symbol by name.

    :param str name: The name to load, specified by `module.attr`.
    :returns: The attribute value. If the specified module does not contain
              the requested attribute then `None` is returned.
    """
    module_name, key = name.rsplit('.', 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as err:
        # it's possible the symbol is a class method
        module_name, class_name = module_name.rsplit('.', 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name, None)
        if cls:
            attr = getattr(cls, key, None)
        else:
            raise err
    else:
        attr = getattr(module, key, None)
    if not callable(attr):
        raise ValueError('%s is not callable (was %r)' % (name, attr))
    return attr
