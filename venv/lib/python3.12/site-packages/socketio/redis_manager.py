import logging
import pickle
import time
from urllib.parse import urlparse

try:
    import redis
except ImportError:
    redis = None

from .pubsub_manager import PubSubManager

logger = logging.getLogger('socketio')


def parse_redis_sentinel_url(url):
    """Parse a Redis Sentinel URL with the format:
    redis+sentinel://[:password]@host1:port1,host2:port2,.../db/service_name
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme != 'redis+sentinel':
        raise ValueError('Invalid Redis Sentinel URL')
    sentinels = []
    for host_port in parsed_url.netloc.split('@')[-1].split(','):
        host, port = host_port.rsplit(':', 1)
        sentinels.append((host, int(port)))
    kwargs = {}
    if parsed_url.username:
        kwargs['username'] = parsed_url.username
    if parsed_url.password:
        kwargs['password'] = parsed_url.password
    service_name = None
    if parsed_url.path:
        parts = parsed_url.path.split('/')
        if len(parts) >= 2 and parts[1] != '':
            kwargs['db'] = int(parts[1])
        if len(parts) >= 3 and parts[2] != '':
            service_name = parts[2]
    return sentinels, service_name, kwargs


class RedisManager(PubSubManager):  # pragma: no cover
    """Redis based client manager.

    This class implements a Redis backend for event sharing across multiple
    processes. Only kept here as one more example of how to build a custom
    backend, since the kombu backend is perfectly adequate to support a Redis
    message queue.

    To use a Redis backend, initialize the :class:`Server` instance as
    follows::

        url = 'redis://hostname:port/0'
        server = socketio.Server(client_manager=socketio.RedisManager(url))

    :param url: The connection URL for the Redis server. For a default Redis
                store running on the same host, use ``redis://``.  To use a
                TLS connection, use ``rediss://``. To use Redis Sentinel, use
                ``redis+sentinel://`` with a comma-separated list of hosts
                and the service name after the db in the URL path. Example:
                ``redis+sentinel://user:pw@host1:1234,host2:2345/0/myredis``.
    :param channel: The channel name on which the server sends and receives
                    notifications. Must be the same in all the servers.
    :param write_only: If set to ``True``, only initialize to emit events. The
                       default of ``False`` initializes the class for emitting
                       and receiving.
    :param redis_options: additional keyword arguments to be passed to
                          ``Redis.from_url()`` or ``Sentinel()``.
    """
    name = 'redis'

    def __init__(self, url='redis://localhost:6379/0', channel='socketio',
                 write_only=False, logger=None, redis_options=None):
        if redis is None:
            raise RuntimeError('Redis package is not installed '
                               '(Run "pip install redis" in your '
                               'virtualenv).')
        self.redis_url = url
        self.redis_options = redis_options or {}
        self._redis_connect()
        super().__init__(channel=channel, write_only=write_only, logger=logger)

    def initialize(self):
        super().initialize()

        monkey_patched = True
        if self.server.async_mode == 'eventlet':
            from eventlet.patcher import is_monkey_patched
            monkey_patched = is_monkey_patched('socket')
        elif 'gevent' in self.server.async_mode:
            from gevent.monkey import is_module_patched
            monkey_patched = is_module_patched('socket')
        if not monkey_patched:
            raise RuntimeError(
                'Redis requires a monkey patched socket library to work '
                'with ' + self.server.async_mode)

    def _redis_connect(self):
        if not self.redis_url.startswith('redis+sentinel://'):
            self.redis = redis.Redis.from_url(self.redis_url,
                                              **self.redis_options)
        else:
            sentinels, service_name, connection_kwargs = \
                parse_redis_sentinel_url(self.redis_url)
            kwargs = self.redis_options
            kwargs.update(connection_kwargs)
            sentinel = redis.sentinel.Sentinel(sentinels, **kwargs)
            self.redis = sentinel.master_for(service_name or self.channel)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)

    def _publish(self, data):
        retry = True
        while True:
            try:
                if not retry:
                    self._redis_connect()
                return self.redis.publish(self.channel, pickle.dumps(data))
            except redis.exceptions.RedisError:
                if retry:
                    logger.error('Cannot publish to redis... retrying')
                    retry = False
                else:
                    logger.error('Cannot publish to redis... giving up')
                    break

    def _redis_listen_with_retries(self):
        retry_sleep = 1
        connect = False
        while True:
            try:
                if connect:
                    self._redis_connect()
                    self.pubsub.subscribe(self.channel)
                    retry_sleep = 1
                yield from self.pubsub.listen()
            except redis.exceptions.RedisError:
                logger.error('Cannot receive from redis... '
                             'retrying in {} secs'.format(retry_sleep))
                connect = True
                time.sleep(retry_sleep)
                retry_sleep *= 2
                if retry_sleep > 60:
                    retry_sleep = 60

    def _listen(self):
        channel = self.channel.encode('utf-8')
        self.pubsub.subscribe(self.channel)
        for message in self._redis_listen_with_retries():
            if message['channel'] == channel and \
                    message['type'] == 'message' and 'data' in message:
                yield message['data']
        self.pubsub.unsubscribe(self.channel)
