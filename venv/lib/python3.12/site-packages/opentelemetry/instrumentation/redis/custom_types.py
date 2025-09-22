from __future__ import annotations

from typing import Any, Callable, TypeVar

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.connection

from opentelemetry.trace import Span

RequestHook = Callable[
    [Span, redis.connection.Connection, list[Any], dict[str, Any]], None
]
ResponseHook = Callable[[Span, redis.connection.Connection, Any], None]

AsyncPipelineInstance = TypeVar(
    "AsyncPipelineInstance",
    redis.asyncio.client.Pipeline,
    redis.asyncio.cluster.ClusterPipeline,
)
AsyncRedisInstance = TypeVar(
    "AsyncRedisInstance", redis.asyncio.Redis, redis.asyncio.RedisCluster
)
PipelineInstance = TypeVar(
    "PipelineInstance",
    redis.client.Pipeline,
    redis.cluster.ClusterPipeline,
)
RedisInstance = TypeVar(
    "RedisInstance", redis.client.Redis, redis.cluster.RedisCluster
)
R = TypeVar("R")
