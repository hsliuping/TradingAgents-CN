"""
数据库连接管理模块
增强版本，支持连接池、健康检查和错误恢复
"""

import logging
import asyncio
from typing import Callable, Optional, Tuple, Dict
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database
from redis.asyncio import Redis, ConnectionPool
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import AuthenticationError as RedisAuthenticationError
from .config import settings

# 同步Redis客户端类型（延迟导入避免循环依赖）
try:
    import redis as redis_sync
except ImportError:
    redis_sync = None

logger = logging.getLogger(__name__)


def _should_retry_redis_without_password(error: Exception) -> bool:
    """判断是否应在本地无密码 Redis 场景下回退重试。"""
    if not isinstance(error, RedisAuthenticationError):
        return False

    error_text = str(error).lower()
    return "without any password configured" in error_text


def _build_redis_url_without_password() -> str:
    """构建不带密码的 Redis URL，用于本地无密码实例回退。"""
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

# 全局连接实例
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db: Optional[AsyncIOMotorDatabase] = None
redis_client: Optional[Redis] = None
redis_pool: Optional[ConnectionPool] = None
_mongo_runtime_loop: Optional[asyncio.AbstractEventLoop] = None
_redis_runtime_loop: Optional[asyncio.AbstractEventLoop] = None
_mongo_db_proxy = None
_mongo_client_proxy = None
_redis_client_proxy = None
_mongo_loop_bindings: Dict[int, Tuple[asyncio.AbstractEventLoop, AsyncIOMotorClient, AsyncIOMotorDatabase]] = {}

# 同步 MongoDB 连接（用于非异步上下文）
_sync_mongo_client: Optional[MongoClient] = None
_sync_mongo_db: Optional[Database] = None


class DatabaseManager:
    """数据库连接管理器"""

    def __init__(self):
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.mongo_db: Optional[AsyncIOMotorDatabase] = None
        self.redis_client: Optional[Redis] = None
        self.redis_pool: Optional[ConnectionPool] = None
        self.redis_url_in_use: Optional[str] = None
        self._mongo_healthy = False
        self._redis_healthy = False

    async def init_mongodb(self):
        """初始化MongoDB连接"""
        try:
            logger.info("🔄 正在初始化MongoDB连接...")

            # 创建MongoDB客户端，配置连接池
            self.mongo_client = _create_async_mongo_client()

            # 获取数据库实例
            self.mongo_db = self.mongo_client[settings.MONGO_DB]

            # 测试连接
            await self.mongo_client.admin.command('ping')
            self._mongo_healthy = True

            logger.info("✅ MongoDB连接成功建立")
            logger.info(f"📊 数据库: {settings.MONGO_DB}")
            logger.info(f"🔗 连接池: {settings.MONGO_MIN_CONNECTIONS}-{settings.MONGO_MAX_CONNECTIONS}")
            logger.info(f"⏱️  超时配置: connectTimeout={settings.MONGO_CONNECT_TIMEOUT_MS}ms, socketTimeout={settings.MONGO_SOCKET_TIMEOUT_MS}ms")

        except Exception as e:
            logger.error(f"❌ MongoDB连接失败: {e}")
            self._mongo_healthy = False
            raise

    async def init_redis(self):
        """初始化Redis连接"""
        try:
            logger.info("🔄 正在初始化Redis连接...")

            async def _connect(redis_url: str) -> tuple[ConnectionPool, Redis]:
                pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=settings.REDIS_MAX_CONNECTIONS,
                    retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
                    decode_responses=True,
                    socket_connect_timeout=5,  # 5秒连接超时
                    socket_timeout=10,  # 10秒套接字超时
                )
                client = Redis(connection_pool=pool)
                try:
                    await client.ping()
                    return pool, client
                except Exception:
                    await client.close()
                    await pool.disconnect()
                    raise

            try:
                self.redis_pool, self.redis_client = await _connect(settings.REDIS_URL)
                self.redis_url_in_use = settings.REDIS_URL
            except Exception as e:
                if not (settings.REDIS_PASSWORD and _should_retry_redis_without_password(e)):
                    raise

                logger.warning(
                    "⚠️ 当前 Redis 实例未配置密码，但环境变量提供了 REDIS_PASSWORD；"
                    "将自动回退为无密码连接。"
                )
                fallback_url = _build_redis_url_without_password()
                self.redis_pool, self.redis_client = await _connect(fallback_url)
                self.redis_url_in_use = fallback_url

            self._redis_healthy = True

            logger.info("✅ Redis连接成功建立")
            logger.info(f"🔗 连接池大小: {settings.REDIS_MAX_CONNECTIONS}")

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            self._redis_healthy = False
            raise

    async def close_connections(self):
        """关闭所有数据库连接"""
        logger.info("🔄 正在关闭数据库连接...")

        # 关闭MongoDB连接
        try:
            await _close_all_async_mongo_bindings(log_message=False)
            self._mongo_healthy = False
            logger.info("✅ MongoDB连接已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭MongoDB连接时出错: {e}")

        # 关闭Redis连接
        if self.redis_client:
            try:
                await self.redis_client.close()
                self._redis_healthy = False
                logger.info("✅ Redis连接已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接时出错: {e}")

        # 关闭Redis连接池
        if self.redis_pool:
            try:
                await self.redis_pool.disconnect()
                logger.info("✅ Redis连接池已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接池时出错: {e}")

    async def health_check(self) -> dict:
        """数据库健康检查"""
        health_status = {
            "mongodb": {"status": "unknown", "details": None},
            "redis": {"status": "unknown", "details": None}
        }

        # 检查MongoDB
        try:
            try:
                mongo = _get_bound_mongo_client()
            except RuntimeError:
                mongo = None

            if mongo:
                result = await mongo.admin.command('ping')
                health_status["mongodb"] = {
                    "status": "healthy",
                    "details": {"ping": result, "database": settings.MONGO_DB}
                }
                self._mongo_healthy = True
            else:
                health_status["mongodb"]["status"] = "disconnected"
        except Exception as e:
            health_status["mongodb"] = {
                "status": "unhealthy",
                "details": {"error": str(e)}
            }
            self._mongo_healthy = False

        # 检查Redis
        try:
            if self.redis_client:
                result = await self.redis_client.ping()
                health_status["redis"] = {
                    "status": "healthy",
                    "details": {"ping": result}
                }
                self._redis_healthy = True
            else:
                health_status["redis"]["status"] = "disconnected"
        except Exception as e:
            health_status["redis"] = {
                "status": "unhealthy",
                "details": {"error": str(e)}
            }
            self._redis_healthy = False

        return health_status

    @property
    def is_healthy(self) -> bool:
        """检查所有数据库连接是否健康"""
        return self._mongo_healthy and self._redis_healthy


# 全局数据库管理器实例
db_manager = DatabaseManager()


def _create_async_mongo_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(
        settings.MONGO_URI,
        maxPoolSize=settings.MONGO_MAX_CONNECTIONS,
        minPoolSize=settings.MONGO_MIN_CONNECTIONS,
        maxIdleTimeMS=30000,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
    )


def _is_pymongo_client_closed(client: Optional[MongoClient]) -> bool:
    if client is None:
        return True

    topology = getattr(client, "_topology", None)
    if topology is None:
        return False

    return bool(getattr(topology, "_closed", False))


def _is_async_mongo_client_closed(client: Optional[AsyncIOMotorClient]) -> bool:
    if client is None:
        return True

    delegate = getattr(client, "delegate", None)
    return _is_pymongo_client_closed(delegate)


def _set_active_mongo_binding(
    loop: Optional[asyncio.AbstractEventLoop],
    client: AsyncIOMotorClient,
    db: AsyncIOMotorDatabase,
) -> None:
    global mongo_client, mongo_db, _mongo_runtime_loop

    mongo_client = client
    mongo_db = db
    _mongo_runtime_loop = loop
    db_manager.mongo_client = client
    db_manager.mongo_db = db


def _store_mongo_loop_binding(
    loop: asyncio.AbstractEventLoop,
    client: AsyncIOMotorClient,
    db: AsyncIOMotorDatabase,
) -> None:
    _mongo_loop_bindings[id(loop)] = (loop, client, db)
    _set_active_mongo_binding(loop, client, db)


def _prune_closed_mongo_loop_bindings() -> None:
    stale_loop_ids = []

    for loop_id, (loop, client, _) in list(_mongo_loop_bindings.items()):
        if loop.is_closed() or _is_async_mongo_client_closed(client):
            stale_loop_ids.append(loop_id)

    for loop_id in stale_loop_ids:
        _, client, _ = _mongo_loop_bindings.pop(loop_id)
        if client is not None and not _is_async_mongo_client_closed(client):
            try:
                client.close()
            except Exception as exc:
                logger.warning(f"⚠️ 关闭失效 MongoDB 客户端失败（忽略）: {exc}")


class _LoopSafeMongoCollectionProxy:
    """集合代理：即使对象被缓存，也总是转发到当前 loop 绑定的 collection。"""

    def __init__(self, resolver: Callable[[], AsyncIOMotorCollection]):
        self._resolver = resolver

    def _target(self) -> AsyncIOMotorCollection:
        return self._resolver()

    def __getattr__(self, name: str):
        return getattr(self._target(), name)


class _LoopSafeMongoDatabaseProxy:
    """数据库代理：避免调用方缓存旧 loop 绑定的 AsyncIOMotorDatabase。"""

    def __init__(self, resolver: Optional[Callable[[], AsyncIOMotorDatabase]] = None):
        self._resolver = resolver or _get_bound_mongo_db

    def _target(self) -> AsyncIOMotorDatabase:
        return self._resolver()

    def __getitem__(self, name: str):
        return _LoopSafeMongoCollectionProxy(lambda: _get_bound_mongo_db()[name])

    def __getattr__(self, name: str):
        target = getattr(self._target(), name)
        if isinstance(target, AsyncIOMotorCollection):
            return _LoopSafeMongoCollectionProxy(lambda: getattr(_get_bound_mongo_db(), name))
        return target


class _LoopSafeMongoClientProxy:
    """客户端代理：避免缓存旧 loop 绑定的 AsyncIOMotorClient。"""

    def _target(self) -> AsyncIOMotorClient:
        return _get_bound_mongo_client()

    def __getattr__(self, name: str):
        return getattr(self._target(), name)

    def __getitem__(self, name: str):
        return _LoopSafeMongoDatabaseProxy(lambda name=name: _get_bound_mongo_client()[name])


class _LoopSafeRedisClientProxy:
    """Redis 代理：即使对象被缓存，也总是转发到当前 loop 绑定的 Redis 客户端。"""

    def _target(self) -> Redis:
        return _get_bound_redis_client()

    def __getattr__(self, name: str):
        return getattr(self._target(), name)


async def init_database():
    """初始化数据库连接"""
    global mongo_client, mongo_db, redis_client, redis_pool, _mongo_runtime_loop, _redis_runtime_loop

    current_loop: Optional[asyncio.AbstractEventLoop]
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    mongo_binding = _get_current_mongo_loop_binding() if current_loop is not None else None

    mongo_ready = mongo_binding is not None and db_manager._mongo_healthy
    redis_ready = redis_client is not None and redis_pool is not None and db_manager._redis_healthy

    if mongo_ready and redis_ready:
        logger.debug("数据库连接已初始化且健康，跳过重复初始化")
        return

    try:
        if not mongo_ready:
            # 初始化MongoDB
            await db_manager.init_mongodb()
            if current_loop is not None and db_manager.mongo_client is not None and db_manager.mongo_db is not None:
                _store_mongo_loop_binding(current_loop, db_manager.mongo_client, db_manager.mongo_db)
            else:
                mongo_client = db_manager.mongo_client
                mongo_db = db_manager.mongo_db
                _mongo_runtime_loop = current_loop

        if not redis_ready:
            # 初始化Redis
            await db_manager.init_redis()
            redis_client = db_manager.redis_client
            redis_pool = db_manager.redis_pool
            _redis_runtime_loop = asyncio.get_running_loop()

        logger.info("🎉 所有数据库连接初始化完成")

        # 🔥 初始化数据库视图和索引
        await init_database_views_and_indexes()

    except Exception as e:
        logger.error(f"💥 数据库初始化失败: {e}")
        raise


async def init_redis_binding() -> None:
    """仅初始化 Redis 绑定，供兼容层和独立组件复用。"""
    global redis_client, redis_pool, _redis_runtime_loop

    if redis_client is not None and redis_pool is not None:
        try:
            _ensure_async_redis_binding()
        except RuntimeError:
            pass
        return

    await db_manager.init_redis()
    redis_client = db_manager.redis_client
    redis_pool = db_manager.redis_pool

    try:
        _redis_runtime_loop = asyncio.get_running_loop()
    except RuntimeError:
        _redis_runtime_loop = None


async def init_database_views_and_indexes():
    """初始化数据库视图和索引"""
    try:
        db = get_mongo_db()

        # 1. 创建股票筛选视图
        await create_stock_screening_view(db)

        # 2. 创建必要的索引
        await create_database_indexes(db)

        # 3. 创建 agent 执行轨迹集合索引（P1 机器可读执行轨迹）
        # 局部导入避免循环依赖；服务初始化失败不影响应用启动
        try:
            from app.pro.services.execution_trace_service import execution_trace_service
            await execution_trace_service.create_indexes()
        except Exception as trace_exc:
            logger.warning(f"⚠️ 执行轨迹索引初始化失败（不影响应用启动）: {trace_exc}")

        # 4. 创建 agent 断言集合索引（P2 可执行断言）
        try:
            from app.pro.services.agent_assertion_service import agent_assertion_service
            await agent_assertion_service.create_indexes()
        except Exception as assertion_exc:
            logger.warning(f"⚠️ 断言索引初始化失败（不影响应用启动）: {assertion_exc}")

        # 5. 创建助手质量埋点集合索引（A11 阶段4 S9）
        try:
            from core.assistant import quality_metrics
            await quality_metrics.create_indexes(db)
        except Exception as metrics_exc:
            logger.warning(f"⚠️ 质量埋点索引初始化失败（不影响应用启动）: {metrics_exc}")

        logger.info("✅ 数据库视图和索引初始化完成")

    except Exception as e:
        logger.warning(f"⚠️ 数据库视图和索引初始化失败: {e}")
        # 不抛出异常，允许应用继续启动


async def create_stock_screening_view(db):
    """创建股票筛选视图"""
    try:
        # 检查视图是否已存在
        collections = await db.list_collection_names()
        if "stock_screening_view" in collections:
            logger.info("📋 视图 stock_screening_view 已存在，跳过创建")
            return

        # 创建视图：将 stock_basic_info、market_quotes 和 stock_financial_data 关联
        pipeline = [
            # 第一步：关联实时行情数据 (market_quotes)
            {
                "$lookup": {
                    "from": "market_quotes",
                    "localField": "code",
                    "foreignField": "code",
                    "as": "quote_data"
                }
            },
            # 第二步：展开 quote_data 数组
            {
                "$unwind": {
                    "path": "$quote_data",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 第三步：关联财务数据 (stock_financial_data)
            {
                "$lookup": {
                    "from": "stock_financial_data",
                    "let": {"stock_code": "$code", "stock_source": "$source"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$code", "$$stock_code"]},
                                        {"$eq": ["$data_source", "$$stock_source"]}
                                    ]
                                }
                            }
                        },
                        {"$sort": {"report_period": -1}},
                        {"$limit": 1}
                    ],
                    "as": "financial_data"
                }
            },
            # 第四步：展开 financial_data 数组
            {
                "$unwind": {
                    "path": "$financial_data",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 第五步：重新组织字段结构
            {
                "$project": {
                    # 基础信息字段
                    "code": 1,
                    "name": 1,
                    "industry": 1,
                    "area": 1,
                    "market": 1,
                    "list_date": 1,
                    "source": 1,
                    # 市值信息
                    "total_mv": 1,
                    "circ_mv": 1,
                    # 估值指标
                    "pe": 1,
                    "pb": 1,
                    "pe_ttm": 1,
                    "pb_mrq": 1,
                    # 财务指标
                    "roe": "$financial_data.roe",
                    "roa": "$financial_data.roa",
                    "netprofit_margin": "$financial_data.netprofit_margin",
                    "gross_margin": "$financial_data.gross_margin",
                    "report_period": "$financial_data.report_period",
                    # 交易指标
                    "turnover_rate": 1,
                    "volume_ratio": 1,
                    # 实时行情数据
                    "close": "$quote_data.close",
                    "open": "$quote_data.open",
                    "high": "$quote_data.high",
                    "low": "$quote_data.low",
                    "pre_close": "$quote_data.pre_close",
                    "pct_chg": "$quote_data.pct_chg",
                    "amount": "$quote_data.amount",
                    "volume": "$quote_data.volume",
                    "trade_date": "$quote_data.trade_date",
                    # 时间戳
                    "updated_at": 1,
                    "quote_updated_at": "$quote_data.updated_at",
                    "financial_updated_at": "$financial_data.updated_at"
                }
            }
        ]

        # 创建视图
        await db.command({
            "create": "stock_screening_view",
            "viewOn": "stock_basic_info",
            "pipeline": pipeline
        })

        logger.info("✅ 视图 stock_screening_view 创建成功")

    except Exception as e:
        logger.warning(f"⚠️ 创建视图失败: {e}")


async def create_database_indexes(db):
    """创建数据库索引"""
    try:
        # stock_basic_info 的索引
        basic_info = db["stock_basic_info"]
        await basic_info.create_index([("code", 1), ("source", 1)], unique=True)
        await basic_info.create_index([("source", 1)])  # 🔥 单独的 source 索引，优化按数据源筛选的查询
        await basic_info.create_index([("source", 1), ("total_mv", -1)])  # 🔥 复合索引：优化按数据源筛选+市值排序的查询（视图查询常用场景）
        await basic_info.create_index([("industry", 1)])
        await basic_info.create_index([("total_mv", -1)])
        await basic_info.create_index([("pe", 1)])
        await basic_info.create_index([("pb", 1)])

        # market_quotes 的索引
        market_quotes = db["market_quotes"]
        await market_quotes.create_index([("code", 1)], unique=True)
        await market_quotes.create_index([("pct_chg", -1)])
        await market_quotes.create_index([("amount", -1)])
        await market_quotes.create_index([("updated_at", -1)])

        industry_mapping = db["stock_industry_mappings"]
        await industry_mapping.create_index([("code", 1)], unique=True)
        await industry_mapping.create_index([("provider", 1), ("updated_at", -1)])

        logger.info("✅ 数据库索引创建完成")

    except Exception as e:
        logger.warning(f"⚠️ 创建索引失败: {e}")


async def close_database():
    """关闭数据库连接"""
    global mongo_client, mongo_db, redis_client, redis_pool, _mongo_runtime_loop, _redis_runtime_loop

    await db_manager.close_connections()

    # 清空全局变量
    mongo_client = None
    mongo_db = None
    redis_client = None
    redis_pool = None
    _mongo_runtime_loop = None
    _redis_runtime_loop = None


async def close_redis_binding() -> None:
    """仅关闭 Redis 绑定，供兼容层和独立组件复用。"""
    global redis_client, redis_pool, _redis_runtime_loop

    if db_manager.redis_client:
        try:
            await db_manager.redis_client.close()
        except Exception as exc:
            logger.error(f"❌ 关闭Redis连接时出错: {exc}")

    if db_manager.redis_pool:
        try:
            await db_manager.redis_pool.disconnect()
        except Exception as exc:
            logger.error(f"❌ 关闭Redis连接池时出错: {exc}")

    db_manager.redis_client = None
    db_manager.redis_pool = None
    db_manager.redis_url_in_use = None
    db_manager._redis_healthy = False
    redis_client = None
    redis_pool = None
    _redis_runtime_loop = None


def _recreate_async_mongo_binding() -> None:
    """按当前事件循环重建异步 MongoDB 绑定，避免跨 loop 复用旧 Motor 客户端。"""
    current_loop = asyncio.get_running_loop()
    existing = _get_current_mongo_loop_binding()
    if existing is not None:
        return

    client = _create_async_mongo_client()
    db = client[settings.MONGO_DB]
    _store_mongo_loop_binding(current_loop, client, db)
    db_manager._mongo_healthy = True


def _recreate_async_redis_binding() -> None:
    """按当前事件循环重建异步 Redis 绑定，避免跨 loop 复用旧客户端。"""
    global redis_client, redis_pool, _redis_runtime_loop

    current_loop = asyncio.get_running_loop()
    redis_url = db_manager.redis_url_in_use or settings.REDIS_URL

    redis_pool = ConnectionPool.from_url(
        redis_url,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
    )
    redis_client = Redis(connection_pool=redis_pool)
    _redis_runtime_loop = current_loop
    db_manager.redis_pool = redis_pool
    db_manager.redis_client = redis_client


def _ensure_async_redis_binding() -> None:
    """确保返回的异步 Redis 连接绑定到当前运行中的事件循环。"""
    global _redis_runtime_loop

    if redis_client is None or redis_pool is None:
        raise RuntimeError("Redis客户端未初始化")

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _redis_runtime_loop is None:
        _redis_runtime_loop = current_loop
        return

    if _redis_runtime_loop.is_closed() or _redis_runtime_loop is not current_loop:
        logger.warning("⚠️ 检测到异步 Redis 客户端绑定的事件循环已变化，正在重建连接")
        _recreate_async_redis_binding()


def _ensure_async_mongo_binding() -> None:
    """确保返回的异步 MongoDB 连接绑定到当前运行中的事件循环。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return

    binding = _get_current_mongo_loop_binding()
    if binding is not None:
        return

    if mongo_client is None or mongo_db is None:
        raise RuntimeError("MongoDB客户端未初始化")

    if _is_async_mongo_client_closed(mongo_client):
        logger.warning("⚠️ 检测到异步 MongoDB 客户端已关闭，正在为当前事件循环重建连接")
    else:
        logger.warning("⚠️ 检测到异步 MongoDB 客户端绑定的事件循环已变化，正在为当前事件循环创建独立连接")

    _recreate_async_mongo_binding()


def _get_bound_mongo_client() -> AsyncIOMotorClient:
    _ensure_async_mongo_binding()
    assert mongo_client is not None
    return mongo_client


def _get_bound_mongo_db() -> AsyncIOMotorDatabase:
    _ensure_async_mongo_binding()
    assert mongo_db is not None
    return mongo_db


def _get_bound_redis_client() -> Redis:
    _ensure_async_redis_binding()
    assert redis_client is not None
    return redis_client


def get_mongo_client() -> AsyncIOMotorClient:
    """获取MongoDB客户端"""
    global _mongo_client_proxy
    if _mongo_client_proxy is None:
        _mongo_client_proxy = _LoopSafeMongoClientProxy()
    return _mongo_client_proxy


def get_mongo_db() -> AsyncIOMotorDatabase:
    """获取MongoDB数据库实例"""
    global _mongo_db_proxy
    if _mongo_db_proxy is None:
        _mongo_db_proxy = _LoopSafeMongoDatabaseProxy()
    return _mongo_db_proxy


def bind_loop_safe_mongo_db(target: object, attr_name: str = "db") -> AsyncIOMotorDatabase:
    """将 loop-safe MongoDB 代理绑定到对象属性，替代手动重建 AsyncIOMotorClient。"""
    db = get_mongo_db()
    setattr(target, attr_name, db)
    return db


def create_isolated_async_mongo_binding() -> Tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    """创建与当前调用方独立的异步 MongoDB 连接，适用于线程池或临时隔离任务。"""
    client = _create_async_mongo_client()
    return client, client[settings.MONGO_DB]


def _get_current_mongo_loop_binding() -> Optional[Tuple[asyncio.AbstractEventLoop, AsyncIOMotorClient, AsyncIOMotorDatabase]]:
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    _prune_closed_mongo_loop_bindings()

    binding = _mongo_loop_bindings.get(id(current_loop))
    if binding is not None:
        _, client, db = binding
        _set_active_mongo_binding(current_loop, client, db)
        return binding

    if (
        mongo_client is not None
        and mongo_db is not None
        and not _is_async_mongo_client_closed(mongo_client)
        and (_mongo_runtime_loop is None or _mongo_runtime_loop is current_loop)
    ):
        _store_mongo_loop_binding(current_loop, mongo_client, mongo_db)
        return _mongo_loop_bindings.get(id(current_loop))

    return None


async def _close_all_async_mongo_bindings(log_message: bool = True) -> None:
    global mongo_client, mongo_db, _mongo_runtime_loop

    if log_message:
        logger.info("🔄 正在关闭全部 MongoDB 事件循环绑定...")

    _prune_closed_mongo_loop_bindings()
    closed_client_ids = set()

    for _, client, _ in list(_mongo_loop_bindings.values()):
        if client is None:
            continue

        client_id = id(client)
        if client_id in closed_client_ids or _is_async_mongo_client_closed(client):
            closed_client_ids.add(client_id)
            continue

        try:
            client.close()
        except Exception as exc:
            logger.warning(f"⚠️ 关闭 MongoDB 客户端失败（忽略）: {exc}")

        closed_client_ids.add(client_id)

    _mongo_loop_bindings.clear()
    mongo_client = None
    mongo_db = None
    _mongo_runtime_loop = None
    db_manager.mongo_client = None
    db_manager.mongo_db = None
    db_manager._mongo_healthy = False


def get_mongo_db_sync() -> Database:
    """
    获取同步版本的MongoDB数据库实例
    用于非异步上下文（如普通函数调用）
    """
    global _sync_mongo_client, _sync_mongo_db

    if _sync_mongo_db is not None:
        return _sync_mongo_db

    # 创建同步 MongoDB 客户端
    if _sync_mongo_client is None:
        _sync_mongo_client = MongoClient(
            settings.MONGO_URI,
            maxPoolSize=settings.MONGO_MAX_CONNECTIONS,
            minPoolSize=settings.MONGO_MIN_CONNECTIONS,
            maxIdleTimeMS=30000,
            serverSelectionTimeoutMS=5000
        )

    _sync_mongo_db = _sync_mongo_client[settings.MONGO_DB]
    return _sync_mongo_db


def get_redis_client() -> Redis:
    """获取Redis客户端（异步）"""
    global _redis_client_proxy
    if _redis_client_proxy is None:
        _redis_client_proxy = _LoopSafeRedisClientProxy()
    return _redis_client_proxy


# 同步Redis客户端（用于同步上下文）
_redis_sync_client: Optional[redis_sync.Redis] = None


def get_redis_sync_client() -> redis_sync.Redis:
    """
    获取同步Redis客户端（用于同步上下文）
    
    使用系统的Redis配置，但创建同步连接以避免事件循环问题
    统一使用系统的REDIS_URL配置
    """
    global _redis_sync_client
    
    if _redis_sync_client is None:
        if redis_sync is None:
            raise RuntimeError("redis模块未安装，无法创建同步Redis客户端")
        
        redis_url = settings.REDIS_URL
        
        try:
            # 使用redis.from_url自动解析URL，使用系统配置
            _redis_sync_client = redis_sync.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10
            )
            # 测试连接
            _redis_sync_client.ping()
            logger.debug("✅ 同步Redis客户端连接成功（使用系统配置）")
        except Exception as e:
            if settings.REDIS_PASSWORD and _should_retry_redis_without_password(e):
                try:
                    fallback_url = _build_redis_url_without_password()
                    logger.warning(
                        "⚠️ 同步 Redis 客户端检测到本地实例未配置密码，"
                        "将自动回退为无密码连接。"
                    )
                    _redis_sync_client = redis_sync.from_url(
                        fallback_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=10
                    )
                    _redis_sync_client.ping()
                    logger.debug("✅ 同步Redis客户端连接成功（无密码回退）")
                except Exception as fallback_error:
                    logger.warning(f"⚠️ 同步Redis客户端初始化失败: {fallback_error}", exc_info=True)
                    raise RuntimeError(f"同步Redis客户端初始化失败: {fallback_error}")
            else:
                logger.warning(f"⚠️ 同步Redis客户端初始化失败: {e}", exc_info=True)
                raise RuntimeError(f"同步Redis客户端初始化失败: {e}")
    
    return _redis_sync_client


async def get_database_health() -> dict:
    """获取数据库健康状态"""
    return await db_manager.health_check()


# 兼容性别名
init_db = init_database
close_db = close_database


def get_database():
    """获取数据库实例"""
    return get_mongo_db()