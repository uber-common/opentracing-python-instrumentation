# Copyright (c) 2016 Uber Technologies, Inc.
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

from opentracing.ext import tags as ext_tags
import re

from ._current_span import current_span_func
from ._singleton import singleton
from .. import utils

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


# regex to match an ipv4 address
IPV4_RE = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

METHOD_NAMES = ['execute_command', 'get', 'set', 'setex', 'setnx']
ORIG_METHODS = {}


@singleton
def install_patches():
    if redis is None:
        return

    def peer_tags(self):
        """Fetch the peer host/port tags for opentracing.

        We do this lazily and cache the result since the host/port won't
        change.
        """
        if not hasattr(self, '_peer_tags'):
            self._peer_tags = []
            conn_info = self.connection_pool.connection_kwargs
            host = conn_info.get('host')
            if host:
                if IPV4_RE.match(host):
                    self._peer_tags.append((ext_tags.PEER_HOST_IPV4, host))
                else:
                    self._peer_tags.append((ext_tags.PEER_HOSTNAME, host))
            port = conn_info.get('port')
            if port:
                self._peer_tags.append((ext_tags.PEER_PORT, port))
        return self._peer_tags

    redis.StrictRedis.peer_tags = peer_tags

    for name in METHOD_NAMES:
        ORIG_METHODS[name] = getattr(redis.StrictRedis, name)

    def get(self, name, **kwargs):
        self._extra_tags = [('redis.key', name)]
        return ORIG_METHODS['get'](self, name, **kwargs)

    def set(self, name, value, ex=None, px=None, nx=False, xx=False, **kwargs):
        self._extra_tags = [('redis.key', name)]
        return ORIG_METHODS['set'](self, name, value,
                                   ex=ex, px=px, nx=nx, xx=xx,
                                   **kwargs)

    def setex(self, name, time, value, **kwargs):
        self._extra_tags = [('redis.key', name),
                            ('redis.ttl', time)]
        return ORIG_METHODS['setex'](self, name, time, value, **kwargs)

    def setnx(self, name, value, **kwargs):
        self._extra_tags = [('redis.key', name)]
        return ORIG_METHODS['setnx'](self, name, value, **kwargs)

    def execute_command(self, cmd, *args, **kwargs):
        operation_name = 'redis:%s' % (cmd,)
        span = utils.start_child_span(
            operation_name=operation_name, parent=current_span_func())
        span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
        span.set_tag(ext_tags.PEER_SERVICE, 'redis')

        # set the peer information (remote host/port)
        for tag_key, tag_val in self.peer_tags():
            span.set_tag(tag_key, tag_val)

        # for certain commands we'll add extra attributes such as the redis key
        for tag_key, tag_val in getattr(self, '_extra_tags', []):
            span.set_tag(tag_key, tag_val)
        self._extra_tags = []

        with span:
            return ORIG_METHODS['execute_command'](self, cmd, *args, **kwargs)

    for name in METHOD_NAMES:
        setattr(redis.StrictRedis, name, locals()[name])


def reset_patches():
    for name in METHOD_NAMES:
        setattr(redis.StrictRedis, name, ORIG_METHODS[name])
    ORIG_METHODS.clear()
    install_patches.reset()
