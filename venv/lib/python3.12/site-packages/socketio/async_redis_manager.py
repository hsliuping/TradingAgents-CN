import asyncio
import pickle

try:  # pragma: no cover
    from redis import asyncio as aioredis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover
    try:
        import aioredis
        from aioredis.exceptions import RedisError
    except ImportError:
        aioredis = None
        RedisError = None

from .async_pubsub_manager import AsyncPubSubManager
from .redis_manager import parse_redis_sentinel_url


class AsyncRedisManager(AsyncPubSubManager):  # pragma: no cover
    """Redis based client manager for asyncio servers.

    This class implements a Redis backend for event sharing across multiple
    processes.

    To use a Redis backend, initialize the :class:`AsyncServer` instance as
    follows::

        url = 'redis://hostname:port/0'
        server = socketio.AsyncServer(
            client_manager=socketio.AsyncRedisManager(url))

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
    name = 'aioredis'

    def __init__(self, url='redis://localhost:6379/0', channel='socketio',
                 write_only=False, logger=None, redis_options=None):
        if aioredis is None:
            raise RuntimeError('Redis package is not installed '
                               '(Run "pip install redis" in your virtualenv).')
        if not hasattr(aioredis.Redis, 'from_url'):
            raise RuntimeError('Version 2 of aioredis package is required.')
        self.redis_url = url
        self.redis_options = redis_options or {}
        self._redis_connect()
        super().__init__(channel=channel, write_only=write_only, logger=logger)

    def _redis_connect(self):
        if not self.redis_url.startswith('redis+sentinel://'):
            self.redis = aioredis.Redis.from_url(self.redis_url,
                                                 **self.redis_options)
        else:
            sentinels, service_name, connection_kwargs = \
                parse_redis_sentinel_url(self.redis_url)
            kwargs = self.redis_options
            kwargs.update(connection_kwargs)
            sentinel = aioredis.sentinel.Sentinel(sentinels, **kwargs)
            self.redis = sentinel.master_for(service_name or self.channel)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)

    async def _publish(self, data):
        retry = True
        while True:
            try:
                if not retry:
                    self._redis_connect()
                return await self.redis.publish(
                    self.channel, pickle.dumps(data))
            except RedisError:
                if retry:
                    self._get_logger().error('Cannot publish to redis... '
                                             'retrying')
                    retry = False
                else:
                    self._get_logger().error('Cannot publish to redis... '
                                             'giving up')
                    break

    async def _redis_listen_with_retries(self):
        retry_sleep = 1
        connect = False
        while True:
            try:
                if connect:
                    self._redis_connect()
                    await self.pubsub.subscribe(self.channel)
                    retry_sleep = 1
                async for message in self.pubsub.listen():
                    yield message
            except RedisError:
                self._get_logger().error('Cannot receive from redis... '
                                         'retrying in '
                                         '{} secs'.format(retry_sleep))
                connect = True
                await asyncio.sleep(retry_sleep)
                retry_sleep *= 2
                if retry_sleep > 60:
                    retry_sleep = 60

    async def _listen(self):
        channel = self.channel.encode('utf-8')
        await self.pubsub.subscribe(self.channel)
        async for message in self._redis_listen_with_retries():
            if message['channel'] == channel and \
                    message['type'] == 'message' and 'data' in message:
                yield message['data']
        await self.pubsub.unsubscribe(self.channel)
