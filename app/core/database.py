"""
数据库连接管理模块
增强版本，支持连接池、健康检查和错误恢复
"""

import logging
import asyncio
from typing import Dict, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database
from redis.asyncio import Redis, ConnectionPool
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from redis.exceptions import ConnectionError as RedisConnectionError
from .config import settings

# 同步Redis客户端类型（延迟导入避免循环依赖）
try:
    import redis as redis_sync
except ImportError:
    redis_sync = None

logger = logging.getLogger(__name__)

# 全局连接实例
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db: Optional[AsyncIOMotorDatabase] = None
redis_client: Optional[Redis] = None
redis_pool: Optional[ConnectionPool] = None

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
        self._mongo_clients_by_loop: Dict[int, AsyncIOMotorClient] = {}
        self._mongo_dbs_by_loop: Dict[int, AsyncIOMotorDatabase] = {}
        self._redis_clients_by_loop: Dict[int, Redis] = {}
        self._redis_pools_by_loop: Dict[int, ConnectionPool] = {}
        self._mongo_healthy = False
        self._redis_healthy = False

    def _get_running_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """获取当前事件循环；在非异步上下文中返回 None。"""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def ensure_mongodb_for_current_loop(self) -> Tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
        """为当前事件循环获取独立的 MongoDB 客户端。"""
        current_loop = self._get_running_loop()
        loop_id = id(current_loop) if current_loop is not None else 0

        client = self._mongo_clients_by_loop.get(loop_id)
        database = self._mongo_dbs_by_loop.get(loop_id)
        if client is not None and database is not None:
            self.mongo_client = client
            self.mongo_db = database
            return client, database

        client_kwargs = {
            "maxPoolSize": settings.MONGO_MAX_CONNECTIONS,
            "minPoolSize": settings.MONGO_MIN_CONNECTIONS,
            "maxIdleTimeMS": 30000,
            "serverSelectionTimeoutMS": settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
            "connectTimeoutMS": settings.MONGO_CONNECT_TIMEOUT_MS,
            "socketTimeoutMS": settings.MONGO_SOCKET_TIMEOUT_MS,
        }
        if current_loop is not None:
            client_kwargs["io_loop"] = current_loop

        client = AsyncIOMotorClient(settings.MONGO_URI, **client_kwargs)
        database = client[settings.MONGO_DB]
        self._mongo_clients_by_loop[loop_id] = client
        self._mongo_dbs_by_loop[loop_id] = database
        self.mongo_client = client
        self.mongo_db = database

        if current_loop is not None and len(self._mongo_clients_by_loop) > 1:
            logger.warning("⚠️ 检测到多个事件循环正在使用 MongoDB 连接，已为当前 loop 创建独立客户端")

        return client, database

    def ensure_redis_for_current_loop(self) -> Tuple[Redis, ConnectionPool]:
        """为当前事件循环获取独立的 Redis 客户端。"""
        current_loop = self._get_running_loop()
        loop_id = id(current_loop) if current_loop is not None else 0

        client = self._redis_clients_by_loop.get(loop_id)
        pool = self._redis_pools_by_loop.get(loop_id)
        if client is not None and pool is not None:
            self.redis_client = client
            self.redis_pool = pool
            return client, pool

        pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        client = Redis(connection_pool=pool)
        self._redis_clients_by_loop[loop_id] = client
        self._redis_pools_by_loop[loop_id] = pool
        self.redis_client = client
        self.redis_pool = pool

        if current_loop is not None and len(self._redis_clients_by_loop) > 1:
            logger.warning("⚠️ 检测到多个事件循环正在使用 Redis 连接，已为当前 loop 创建独立客户端")

        return client, pool

    async def init_mongodb(self):
        """初始化MongoDB连接"""
        try:
            logger.info("🔄 正在初始化MongoDB连接...")

            # 为当前事件循环创建专属客户端，避免跨 loop 复用
            self.mongo_client, self.mongo_db = self.ensure_mongodb_for_current_loop()

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

            # 为当前事件循环创建专属客户端，避免跨 loop 复用
            self.redis_client, self.redis_pool = self.ensure_redis_for_current_loop()

            # 测试连接
            await self.redis_client.ping()
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
        closed_mongo_clients = set()
        for client in list(self._mongo_clients_by_loop.values()):
            if client is None or id(client) in closed_mongo_clients:
                continue
            try:
                client.close()
                closed_mongo_clients.add(id(client))
            except Exception as e:
                logger.error(f"❌ 关闭MongoDB连接时出错: {e}")
        if closed_mongo_clients:
            self._mongo_healthy = False
            logger.info("✅ MongoDB连接已关闭")

        # 关闭Redis连接
        closed_redis_clients = set()
        for client in list(self._redis_clients_by_loop.values()):
            if client is None or id(client) in closed_redis_clients:
                continue
            try:
                await client.close()
                closed_redis_clients.add(id(client))
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接时出错: {e}")
        if closed_redis_clients:
            self._redis_healthy = False
            logger.info("✅ Redis连接已关闭")

        # 关闭Redis连接池
        closed_redis_pools = set()
        for pool in list(self._redis_pools_by_loop.values()):
            if pool is None or id(pool) in closed_redis_pools:
                continue
            try:
                await pool.disconnect()
                closed_redis_pools.add(id(pool))
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接池时出错: {e}")
        if closed_redis_pools:
            logger.info("✅ Redis连接池已关闭")

        self._mongo_clients_by_loop.clear()
        self._mongo_dbs_by_loop.clear()
        self._redis_clients_by_loop.clear()
        self._redis_pools_by_loop.clear()
        self.mongo_client = None
        self.mongo_db = None
        self.redis_client = None
        self.redis_pool = None

    async def health_check(self) -> dict:
        """数据库健康检查"""
        health_status = {
            "mongodb": {"status": "unknown", "details": None},
            "redis": {"status": "unknown", "details": None}
        }

        # 检查MongoDB
        try:
            if self.mongo_client:
                result = await self.mongo_client.admin.command('ping')
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


async def init_database():
    """初始化数据库连接"""
    global mongo_client, mongo_db, redis_client, redis_pool

    try:
        # 初始化MongoDB
        await db_manager.init_mongodb()
        mongo_client = db_manager.mongo_client
        mongo_db = db_manager.mongo_db

        # 初始化Redis
        await db_manager.init_redis()
        redis_client = db_manager.redis_client
        redis_pool = db_manager.redis_pool

        logger.info("🎉 所有数据库连接初始化完成")

        # 🔥 初始化数据库视图和索引
        await init_database_views_and_indexes()

    except Exception as e:
        logger.error(f"💥 数据库初始化失败: {e}")
        raise


async def init_database_views_and_indexes():
    """初始化数据库视图和索引"""
    try:
        db = get_mongo_db()

        # 1. 创建股票筛选视图
        await create_stock_screening_view(db)

        # 2. 创建必要的索引
        await create_database_indexes(db)

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
            logger.info("📋 视图 stock_screening_view 已存在，先删除后重建以同步最新字段")
            await db["stock_screening_view"].drop()

        # 创建视图：将 stock_basic_info、market_quotes、stock_financial_periods
        # 和技术指标快照统一关联
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
            # 第三步：关联财务数据 (stock_financial_periods)
            {
                "$lookup": {
                    "from": "stock_financial_periods",
                    "let": {"stock_code": "$code", "stock_source": "$source"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$code", "$$stock_code"]},
                                        {"$eq": ["$source", "$$stock_source"]}
                                    ]
                                }
                            }
                        },
                        {"$sort": {"report_period": -1, "ann_date": -1, "updated_at": -1}},
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
            # 第五步：关联技术指标快照 (stock_technical_indicators)
            {
                "$lookup": {
                    "from": "stock_technical_indicators",
                    "let": {"stock_code": "$code", "stock_source": "$source"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$code", "$$stock_code"]},
                                        {"$eq": ["$source", "$$stock_source"]}
                                    ]
                                }
                            }
                        },
                        {"$sort": {"trade_date": -1, "updated_at": -1}},
                        {"$limit": 1}
                    ],
                    "as": "technical_data"
                }
            },
            # 第六步：展开 technical_data 数组
            {
                "$unwind": {
                    "path": "$technical_data",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 第七步：重新组织字段结构
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
                    "pb_mrq": {
                        "$ifNull": [
                            "$pb_mrq",
                            {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$ne": ["$total_mv", None]},
                                            {"$gt": ["$total_mv", 0]},
                                            {"$ne": [
                                                {
                                                    "$ifNull": [
                                                        "$financial_data.total_equity",
                                                        "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                                                    ]
                                                },
                                                None
                                            ]},
                                            {"$gt": [
                                                {
                                                    "$ifNull": [
                                                        "$financial_data.total_equity",
                                                        "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                                                    ]
                                                },
                                                0
                                            ]}
                                        ]
                                    },
                                    {
                                        "$divide": [
                                            {"$multiply": ["$total_mv", 100000000]},
                                            {
                                                "$ifNull": [
                                                    "$financial_data.total_equity",
                                                    "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                                                ]
                                            }
                                        ]
                                    },
                                    None
                                ]
                            }
                        ]
                    },
                    # 财务指标
                    "roe": "$financial_data.roe",
                    "roa": "$financial_data.roa",
                    "netprofit_margin": {
                        "$ifNull": [
                            "$financial_data.netprofit_margin",
                            "$financial_data.financial_indicators.netprofit_margin"
                        ]
                    },
                    "gross_margin": {
                        "$ifNull": [
                            "$financial_data.gross_margin",
                            "$financial_data.financial_indicators.gross_margin"
                        ]
                    },
                    "debt_to_assets": {
                        "$ifNull": [
                            "$financial_data.debt_to_assets",
                            "$financial_data.financial_indicators.debt_to_assets"
                        ]
                    },
                    "assets_to_eqt": {
                        "$ifNull": [
                            "$financial_data.assets_to_eqt",
                            "$financial_data.financial_indicators.assets_to_eqt"
                        ]
                    },
                    "current_ratio": {
                        "$ifNull": [
                            "$financial_data.current_ratio",
                            "$financial_data.financial_indicators.current_ratio"
                        ]
                    },
                    "quick_ratio": {
                        "$ifNull": [
                            "$financial_data.quick_ratio",
                            "$financial_data.financial_indicators.quick_ratio"
                        ]
                    },
                    "cash_ratio": {
                        "$ifNull": [
                            "$financial_data.cash_ratio",
                            "$financial_data.financial_indicators.cash_ratio"
                        ]
                    },
                    "dividend_yield": {
                        "$ifNull": [
                            "$dividend_yield",
                            {
                                "$ifNull": [
                                    "$financial_data.financial_indicators.dividend_yield",
                                    "$financial_data.dividend_yield"
                                ]
                            }
                        ]
                    },
                    "dividend_yield_ttm": "$dividend_yield_ttm",
                    "oper_profit": "$financial_data.oper_profit",
                    "total_equity": {
                        "$ifNull": [
                            "$financial_data.total_equity",
                            "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                        ]
                    },
                    "total_liab": {
                        "$ifNull": [
                            "$financial_data.total_liab",
                            "$financial_data.raw_data.balance_sheet.total_liab"
                        ]
                    },
                    "money_cap": {
                        "$ifNull": [
                            "$financial_data.money_cap",
                            "$financial_data.raw_data.balance_sheet.money_cap"
                        ]
                    },
                    "total_ncl": {
                        "$ifNull": [
                            "$financial_data.total_ncl",
                            "$financial_data.raw_data.balance_sheet.total_ncl"
                        ]
                    },
                    "accounts_receiv": {
                        "$ifNull": [
                            "$financial_data.accounts_receiv",
                            "$financial_data.raw_data.balance_sheet.accounts_receiv"
                        ]
                    },
                    "inventories": {
                        "$ifNull": [
                            "$financial_data.inventories",
                            "$financial_data.raw_data.balance_sheet.inventories"
                        ]
                    },
                    "oper_cost": {
                        "$ifNull": [
                            "$financial_data.oper_cost",
                            "$financial_data.raw_data.income_statement.oper_cost"
                        ]
                    },
                    "fin_exp": {
                        "$ifNull": [
                            "$financial_data.fin_exp",
                            "$financial_data.raw_data.income_statement.fin_exp"
                        ]
                    },
                    "revenue_ttm": "$financial_data.revenue_ttm",
                    "net_profit_ttm": "$financial_data.net_profit_ttm",
                    "n_cashflow_act": "$financial_data.n_cashflow_act",
                    "n_cashflow_inv_act": "$financial_data.n_cashflow_inv_act",
                    "revenue_yoy": {
                        "$ifNull": [
                            "$financial_data.revenue_yoy",
                            "$financial_data.financial_indicators.revenue_yoy"
                        ]
                    },
                    "net_profit_yoy": {
                        "$ifNull": [
                            "$financial_data.net_profit_yoy",
                            "$financial_data.financial_indicators.net_profit_yoy"
                        ]
                    },
                    "oper_profit_yoy": {
                        "$ifNull": [
                            "$financial_data.oper_profit_yoy",
                            "$financial_data.financial_indicators.oper_profit_yoy"
                        ]
                    },
                    "peg": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$pe_ttm", None]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.net_profit_yoy",
                                                "$financial_data.financial_indicators.net_profit_yoy"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$gt": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.net_profit_yoy",
                                                "$financial_data.financial_indicators.net_profit_yoy"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$divide": [
                                    "$pe_ttm",
                                    {
                                        "$ifNull": [
                                            "$financial_data.net_profit_yoy",
                                            "$financial_data.financial_indicators.net_profit_yoy"
                                        ]
                                    }
                                ]
                            },
                            None
                        ]
                    },
                    "roic": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.oper_profit", None]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_equity",
                                                "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_liab",
                                                "$financial_data.raw_data.balance_sheet.total_liab"
                                            ]
                                        },
                                        None
                                    ]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$multiply": [
                                                    "$financial_data.oper_profit",
                                                    {
                                                        "$subtract": [
                                                            1,
                                                            {
                                                                "$min": [
                                                                    0.35,
                                                                    {
                                                                        "$max": [
                                                                            0,
                                                                            {
                                                                                "$cond": [
                                                                                    {
                                                                                        "$and": [
                                                                                            {"$ne": ["$financial_data.total_profit", None]},
                                                                                            {"$gt": ["$financial_data.total_profit", 0]},
                                                                                            {"$ne": ["$financial_data.net_profit", None]}
                                                                                        ]
                                                                                    },
                                                                                    {
                                                                                        "$subtract": [
                                                                                            1,
                                                                                            {
                                                                                                "$divide": [
                                                                                                    "$financial_data.net_profit",
                                                                                                    "$financial_data.total_profit"
                                                                                                ]
                                                                                            }
                                                                                        ]
                                                                                    },
                                                                                    0.25
                                                                                ]
                                                                            }
                                                                        ]
                                                                    }
                                                                ]
                                                            }
                                                        ]
                                                    }
                                                ]
                                            },
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.total_equity",
                                                                    "$financial_data.raw_data.balance_sheet.total_hldr_eqy_exc_min_int"
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.total_liab",
                                                                    "$financial_data.raw_data.balance_sheet.total_liab"
                                                                ]
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        "$ifNull": [
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.money_cap",
                                                                    "$financial_data.raw_data.balance_sheet.money_cap"
                                                                ]
                                                            },
                                                            0
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "asset_turnover": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.revenue_ttm",
                                                "$financial_data.revenue"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$divide": [
                                    {
                                        "$ifNull": [
                                            "$financial_data.revenue_ttm",
                                            "$financial_data.revenue"
                                        ]
                                    },
                                    {
                                        "$ifNull": [
                                            "$financial_data.total_assets",
                                            "$financial_data.raw_data.balance_sheet.total_assets"
                                        ]
                                    }
                                ]
                            },
                            None
                        ]
                    },
                    "gross_profit_to_assets": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.revenue_ttm",
                                                "$financial_data.revenue"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.gross_margin",
                                                "$financial_data.financial_indicators.gross_margin"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$multiply": [
                                                    {
                                                        "$ifNull": [
                                                            "$financial_data.revenue_ttm",
                                                            "$financial_data.revenue"
                                                        ]
                                                    },
                                                    {
                                                        "$divide": [
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.gross_margin",
                                                                    "$financial_data.financial_indicators.gross_margin"
                                                                ]
                                                            },
                                                            100
                                                        ]
                                                    }
                                                ]
                                            },
                                            {
                                                "$ifNull": [
                                                    "$financial_data.total_assets",
                                                    "$financial_data.raw_data.balance_sheet.total_assets"
                                                ]
                                            }
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "interest_coverage": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.oper_profit", None]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.fin_exp",
                                                "$financial_data.raw_data.income_statement.fin_exp"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$gt": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.fin_exp",
                                                "$financial_data.raw_data.income_statement.fin_exp"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$divide": [
                                    "$financial_data.oper_profit",
                                    {
                                        "$ifNull": [
                                            "$financial_data.fin_exp",
                                            "$financial_data.raw_data.income_statement.fin_exp"
                                        ]
                                    }
                                ]
                            },
                            None
                        ]
                    },
                    "inventory_turnover": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.inventories",
                                                "$financial_data.raw_data.balance_sheet.inventories"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$gt": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.inventories",
                                                "$financial_data.raw_data.balance_sheet.inventories"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$divide": [
                                    {
                                        "$ifNull": [
                                            "$financial_data.oper_cost",
                                            {
                                                "$cond": [
                                                    {
                                                        "$and": [
                                                            {"$ne": [
                                                                {
                                                                    "$ifNull": [
                                                                        "$financial_data.revenue_ttm",
                                                                        "$financial_data.revenue"
                                                                    ]
                                                                },
                                                                None
                                                            ]},
                                                            {"$ne": [
                                                                {
                                                                    "$ifNull": [
                                                                        "$financial_data.gross_margin",
                                                                        "$financial_data.financial_indicators.gross_margin"
                                                                    ]
                                                                },
                                                                None
                                                            ]}
                                                        ]
                                                    },
                                                    {
                                                        "$multiply": [
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.revenue_ttm",
                                                                    "$financial_data.revenue"
                                                                ]
                                                            },
                                                            {
                                                                "$subtract": [
                                                                    1,
                                                                    {
                                                                        "$divide": [
                                                                            {
                                                                                "$ifNull": [
                                                                                    "$financial_data.gross_margin",
                                                                                    "$financial_data.financial_indicators.gross_margin"
                                                                                ]
                                                                            },
                                                                            100
                                                                        ]
                                                                    }
                                                                ]
                                                            }
                                                        ]
                                                    },
                                                    None
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "$ifNull": [
                                            "$financial_data.inventories",
                                            "$financial_data.raw_data.balance_sheet.inventories"
                                        ]
                                    }
                                ]
                            },
                            None
                        ]
                    },
                    "receivable_turnover": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.revenue_ttm",
                                                "$financial_data.revenue"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.accounts_receiv",
                                                "$financial_data.raw_data.balance_sheet.accounts_receiv"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$gt": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.accounts_receiv",
                                                "$financial_data.raw_data.balance_sheet.accounts_receiv"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$divide": [
                                    {
                                        "$ifNull": [
                                            "$financial_data.revenue_ttm",
                                            "$financial_data.revenue"
                                        ]
                                    },
                                    {
                                        "$ifNull": [
                                            "$financial_data.accounts_receiv",
                                            "$financial_data.raw_data.balance_sheet.accounts_receiv"
                                        ]
                                    }
                                ]
                            },
                            None
                        ]
                    },
                    "net_cash_position": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.money_cap",
                                                "$financial_data.raw_data.balance_sheet.money_cap"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$gt": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        0
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_ncl",
                                                "$financial_data.raw_data.balance_sheet.total_ncl"
                                            ]
                                        },
                                        None
                                    ]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$ifNull": [
                                                            "$financial_data.money_cap",
                                                            "$financial_data.raw_data.balance_sheet.money_cap"
                                                        ]
                                                    },
                                                    {
                                                        "$max": [
                                                            0,
                                                            {
                                                                "$ifNull": [
                                                                    "$financial_data.total_ncl",
                                                                    "$financial_data.raw_data.balance_sheet.total_ncl"
                                                                ]
                                                            }
                                                        ]
                                                    }
                                                ]
                                            },
                                            {
                                                "$ifNull": [
                                                    "$financial_data.total_assets",
                                                    "$financial_data.raw_data.balance_sheet.total_assets"
                                                ]
                                            }
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "fcf": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.n_cashflow_act", None]},
                                    {"$ne": ["$financial_data.n_cashflow_inv_act", None]}
                                ]
                            },
                            {
                                "$add": [
                                    "$financial_data.n_cashflow_act",
                                    "$financial_data.n_cashflow_inv_act"
                                ]
                            },
                            None
                        ]
                    },
                    "fcf_yield": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$total_mv", None]},
                                    {"$gt": ["$total_mv", 0]},
                                    {"$ne": ["$financial_data.n_cashflow_act", None]},
                                    {"$ne": ["$financial_data.n_cashflow_inv_act", None]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$add": [
                                                    "$financial_data.n_cashflow_act",
                                                    "$financial_data.n_cashflow_inv_act"
                                                ]
                                            },
                                            {"$multiply": ["$total_mv", 100000000]}
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "cash_conversion": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.n_cashflow_act", None]},
                                    {"$ne": ["$financial_data.net_profit", None]},
                                    {"$ne": ["$financial_data.net_profit", 0]}
                                ]
                            },
                            {
                                "$divide": [
                                    "$financial_data.n_cashflow_act",
                                    "$financial_data.net_profit"
                                ]
                            },
                            None
                        ]
                    },
                    "accrual_ratio": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.net_profit", None]},
                                    {"$ne": ["$financial_data.n_cashflow_act", None]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.total_assets",
                                                "$financial_data.raw_data.balance_sheet.total_assets"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$subtract": [
                                                    "$financial_data.net_profit",
                                                    "$financial_data.n_cashflow_act"
                                                ]
                                            },
                                            {
                                                "$ifNull": [
                                                    "$financial_data.total_assets",
                                                    "$financial_data.raw_data.balance_sheet.total_assets"
                                                ]
                                            }
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "ocf_yield": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$total_mv", None]},
                                    {"$gt": ["$total_mv", 0]},
                                    {"$ne": ["$financial_data.n_cashflow_act", None]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            "$financial_data.n_cashflow_act",
                                            {"$multiply": ["$total_mv", 100000000]}
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "fcf_margin": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$financial_data.n_cashflow_act", None]},
                                    {"$ne": ["$financial_data.n_cashflow_inv_act", None]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.revenue_ttm",
                                                "$financial_data.revenue"
                                            ]
                                        },
                                        None
                                    ]},
                                    {"$ne": [
                                        {
                                            "$ifNull": [
                                                "$financial_data.revenue_ttm",
                                                "$financial_data.revenue"
                                            ]
                                        },
                                        0
                                    ]}
                                ]
                            },
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            {
                                                "$add": [
                                                    "$financial_data.n_cashflow_act",
                                                    "$financial_data.n_cashflow_inv_act"
                                                ]
                                            },
                                            {
                                                "$ifNull": [
                                                    "$financial_data.revenue_ttm",
                                                    "$financial_data.revenue"
                                                ]
                                            }
                                        ]
                                    },
                                    100
                                ]
                            },
                            None
                        ]
                    },
                    "working_capital_change": "$financial_data.working_capital_change",
                    "revenue_cagr_3y": "$financial_data.revenue_cagr_3y",
                    "profit_cagr_3y": "$financial_data.profit_cagr_3y",
                    "net_working_capital": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": [{"$ifNull": ["$financial_data.total_cur_assets", "$financial_data.raw_data.balance_sheet.total_cur_assets"]}, None]},
                                    {"$ne": [{"$ifNull": ["$financial_data.total_cur_liab", "$financial_data.raw_data.balance_sheet.total_cur_liab"]}, None]}
                                ]
                            },
                            {
                                "$divide": [
                                    {
                                        "$subtract": [
                                            {"$ifNull": ["$financial_data.total_cur_assets", "$financial_data.raw_data.balance_sheet.total_cur_assets"]},
                                            {"$ifNull": ["$financial_data.total_cur_liab", "$financial_data.raw_data.balance_sheet.total_cur_liab"]}
                                        ]
                                    },
                                    100000000
                                ]
                            },
                            None
                        ]
                    },
                    "report_period": "$financial_data.report_period",
                    "is_st": {
                        "$regexMatch": {
                            "input": {"$ifNull": ["$name", ""]},
                            "regex": "(^|\\s)\\*?ST",
                            "options": "i"
                        }
                    },
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
                    # 技术指标快照
                    "ma20": "$technical_data.ma20",
                    "rsi14": "$technical_data.rsi14",
                    "kdj_k": "$technical_data.kdj_k",
                    "kdj_d": "$technical_data.kdj_d",
                    "kdj_j": "$technical_data.kdj_j",
                    "dif": "$technical_data.dif",
                    "dea": "$technical_data.dea",
                    "macd_hist": "$technical_data.macd_hist",
                    "technical_trade_date": "$technical_data.trade_date",
                    # 时间戳
                    "updated_at": 1,
                    "quote_updated_at": "$quote_data.updated_at",
                    "financial_updated_at": "$financial_data.updated_at",
                    "technical_updated_at": "$technical_data.updated_at"
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

        # stock_financial_periods 的索引
        financial_periods = db["stock_financial_periods"]
        await financial_periods.create_index([
            ("symbol", 1),
            ("source", 1),
            ("report_period", -1),
            ("ann_date", -1),
        ], unique=True)
        await financial_periods.create_index([("code", 1), ("source", 1), ("report_period", -1)])
        await financial_periods.create_index([("symbol", 1), ("report_period", -1)])
        await financial_periods.create_index([("symbol", 1), ("source", 1), ("updated_at", -1)])

        # stock_technical_indicators 的索引
        technical_indicators = db["stock_technical_indicators"]
        await technical_indicators.create_index([
            ("code", 1),
            ("source", 1),
            ("trade_date", -1),
        ], unique=True)
        await technical_indicators.create_index([("symbol", 1), ("source", 1), ("trade_date", -1)])
        await technical_indicators.create_index([("source", 1), ("updated_at", -1)])

        # screening_presets 用户筛选方案
        screening_presets = db["screening_presets"]
        await screening_presets.create_index([("user_id", 1), ("name", 1)], unique=True)
        await screening_presets.create_index([("user_id", 1), ("updated_at", -1)])

        # assistant_conversations 智能助手旧会话（兼容）
        assistant_conv = db["assistant_conversations"]
        await assistant_conv.create_index([("user_id", 1)], unique=True)

        # assistant_threads 智能助手主题会话
        assistant_threads = db["assistant_threads"]
        await assistant_threads.create_index([("user_id", 1), ("thread_id", 1)], unique=True)
        await assistant_threads.create_index([("user_id", 1), ("updated_at", -1)])
        await assistant_threads.create_index([("user_id", 1), ("parent_thread_id", 1), ("updated_at", -1)])

        # assistant_thread_messages 智能助手主题消息
        assistant_thread_messages = db["assistant_thread_messages"]
        await assistant_thread_messages.create_index([("thread_id", 1), ("created_at", 1)])
        await assistant_thread_messages.create_index([("user_id", 1), ("thread_id", 1), ("created_at", -1)])

        # assistant_thread_checkpoints 智能助手主题摘要快照
        assistant_thread_checkpoints = db["assistant_thread_checkpoints"]
        await assistant_thread_checkpoints.create_index([("thread_id", 1), ("created_at", -1)])
        await assistant_thread_checkpoints.create_index([("user_id", 1), ("thread_id", 1), ("created_at", -1)])

        # embedded_nanobot_threads 内嵌 Nanobot 会话
        embedded_nanobot_threads = db["embedded_nanobot_threads"]
        await embedded_nanobot_threads.create_index([("user_id", 1), ("thread_id", 1)], unique=True)
        await embedded_nanobot_threads.create_index([("user_id", 1), ("updated_at", -1)])
        await embedded_nanobot_threads.create_index([("session_key", 1), ("updated_at", -1)])

        # embedded_nanobot_thread_messages 内嵌 Nanobot 会话消息
        embedded_nanobot_thread_messages = db["embedded_nanobot_thread_messages"]
        await embedded_nanobot_thread_messages.create_index([("thread_id", 1), ("created_at", 1)])
        await embedded_nanobot_thread_messages.create_index([("user_id", 1), ("thread_id", 1), ("created_at", -1)])
        await embedded_nanobot_thread_messages.create_index([("session_key", 1), ("created_at", -1)])

        # ETF 集合索引
        etf_basic = db["etf_basic_info"]
        await etf_basic.create_index([("code", 1), ("source", 1)], unique=True)
        await etf_basic.create_index([("code", 1)])
        etf_daily = db["etf_daily_quotes"]
        await etf_daily.create_index([("code", 1), ("trade_date", -1)])
        await etf_daily.create_index([("symbol", 1), ("trade_date", -1)])

        # 工作流成长集合索引
        growth_memories = db["agent_memory_items"]
        await growth_memories.create_index([("memory_id", 1)], unique=True)
        await growth_memories.create_index([("user_id", 1), ("status", 1), ("updated_at", -1)])
        await growth_memories.create_index([("user_id", 1), ("source_id", 1), ("created_at", -1)])
        await growth_memories.create_index([("user_id", 1), ("object_type", 1), ("object_key", 1), ("status", 1)])

        growth_suggestions = db["agent_growth_suggestions"]
        await growth_suggestions.create_index([("suggestion_id", 1)], unique=True)
        await growth_suggestions.create_index([("user_id", 1), ("status", 1), ("updated_at", -1)])
        await growth_suggestions.create_index([("user_id", 1), ("source_id", 1), ("created_at", -1)])

        # Agent 工坊集合索引
        agent_specs = db["agent_specs"]
        await agent_specs.create_index([("spec_id", 1)], unique=True)
        await agent_specs.create_index([("owner_user_id", 1), ("status", 1), ("updated_at", -1)])
        await agent_specs.create_index([("latest_session_id", 1)])

        agent_workshop_sessions = db["agent_workshop_sessions"]
        await agent_workshop_sessions.create_index([("session_id", 1)], unique=True)
        await agent_workshop_sessions.create_index([("user_id", 1), ("stage", 1), ("updated_at", -1)])
        await agent_workshop_sessions.create_index([("spec_id", 1), ("updated_at", -1)])

        agent_versions = db["agent_versions"]
        await agent_versions.create_index([("version_id", 1)], unique=True)
        await agent_versions.create_index([("spec_id", 1), ("version", -1)], unique=True)
        await agent_versions.create_index([("spec_id", 1), ("status", 1), ("updated_at", -1)])

        agent_evaluations = db["agent_evaluations"]
        await agent_evaluations.create_index([("evaluation_id", 1)], unique=True)
        await agent_evaluations.create_index([("version_id", 1), ("created_at", -1)])

        # scheduler_executions（高频查询，此前无索引）
        sched_exec = db["scheduler_executions"]
        await sched_exec.create_index([("job_id", 1), ("status", 1), ("timestamp", -1)])
        await sched_exec.create_index([("status", 1), ("timestamp", -1)])
        await sched_exec.create_index([("updated_at", -1)])

        sched_hist = db["scheduler_history"]
        await sched_hist.create_index([("job_id", 1), ("timestamp", -1)])

        # 持仓 & 交易相关
        real_pos = db["real_positions"]
        await real_pos.create_index([("user_id", 1), ("code", 1), ("market", 1)])

        pos_changes = db["position_changes"]
        await pos_changes.create_index([("user_id", 1), ("created_at", -1)])
        await pos_changes.create_index([("user_id", 1), ("code", 1), ("market", 1), ("created_at", -1)])

        real_accts = db["real_accounts"]
        await real_accts.create_index([("user_id", 1)])

        # 分析报告
        reports = db["analysis_reports"]
        await reports.create_index([("user_id", 1), ("created_at", -1)])
        await reports.create_index([("user_id", 1), ("task_id", 1)])

        pos_reports = db["position_analysis_reports"]
        await pos_reports.create_index([("user_id", 1), ("created_at", -1)])

        # 统一任务中心
        unified_tasks = db["unified_analysis_tasks"]
        await unified_tasks.create_index([("user_id", 1), ("created_at", -1)])
        await unified_tasks.create_index([("task_id", 1)], unique=True)

        # 系统配置（对齐实际查询字段 config_key）
        sys_cfg = db["system_configs"]
        await sys_cfg.create_index([("config_key", 1)], unique=True, sparse=True)

        logger.info("✅ 数据库索引创建完成")

    except Exception as e:
        logger.warning(f"⚠️ 创建索引失败: {e}")


async def close_database():
    """关闭数据库连接"""
    global mongo_client, mongo_db, redis_client, redis_pool

    await db_manager.close_connections()

    # 清空全局变量
    mongo_client = None
    mongo_db = None
    redis_client = None
    redis_pool = None


def get_mongo_client() -> AsyncIOMotorClient:
    """获取MongoDB客户端"""
    global mongo_client, mongo_db

    mongo_client, mongo_db = db_manager.ensure_mongodb_for_current_loop()
    return mongo_client


def get_mongo_db() -> AsyncIOMotorDatabase:
    """获取MongoDB数据库实例"""
    global mongo_client, mongo_db

    mongo_client, mongo_db = db_manager.ensure_mongodb_for_current_loop()
    return mongo_db


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
    global redis_client, redis_pool

    redis_client, redis_pool = db_manager.ensure_redis_for_current_loop()
    return redis_client


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
    if db_manager.mongo_client is None:
        raise RuntimeError("MongoDB客户端未初始化")
    return db_manager.mongo_client.tradingagents