"""
自选股服务
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from app.core.database import get_mongo_db
from app.models.user import FavoriteStock
# 已移除在线行情补齐功能，只从数据库读取数据
# 用户可以通过"同步实时行情"按钮来更新数据
# from app.services.quotes_service import get_quotes_service

logger = logging.getLogger("webapi")


class FavoritesService:
    """自选股服务类"""
    
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            self.db = get_mongo_db()
        return self.db

    def _is_valid_object_id(self, user_id: str) -> bool:
        """
        检查是否是有效的ObjectId格式
        注意：这里只检查格式，不代表数据库中实际存储的是ObjectId类型
        为了兼容性，我们统一使用 user_favorites 集合存储自选股
        """
        # 强制返回 False，统一使用 user_favorites 集合
        return False

    def _format_favorite(self, favorite: Dict[str, Any]) -> Dict[str, Any]:
        """格式化收藏条目（仅基础信息，不包含实时行情）。
        行情将在 get_user_favorites 中批量富集。
        """
        added_at = favorite.get("added_at")
        if isinstance(added_at, datetime):
            added_at = added_at.isoformat()
        return {
            "stock_code": favorite.get("stock_code"),
            "stock_name": favorite.get("stock_name"),
            "market": favorite.get("market", "A股"),
            "added_at": added_at,
            "tags": favorite.get("tags", []),
            "notes": favorite.get("notes", ""),
            "alert_price_high": favorite.get("alert_price_high"),
            "alert_price_low": favorite.get("alert_price_low"),
            # 行情占位，稍后填充
            "current_price": None,
            "change_percent": None,
            "volume": None,
        }

    async def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户自选股列表，并从数据库读取实时行情进行富集（兼容字符串ID与ObjectId）。
        
        注意：
        - 只从数据库（market_quotes、market_quotes_hk、market_quotes_us）读取数据
        - 不会调用在线 API 拉取最新价格，避免接口超时
        - 用户可以通过"同步实时行情"按钮来更新数据
        - 后台定时任务会定期更新数据库中的实时行情数据
        """
        import time
        start_time = time.time()
        db = await self._get_db()

        logger.info(f"🔍 [get_user_favorites] 开始查询用户自选股: user_id={user_id}")

        favorites: List[Dict[str, Any]] = []
        if self._is_valid_object_id(user_id):
            # 先尝试使用 ObjectId 查询
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            # 如果 ObjectId 查询失败，尝试使用字符串查询
            if user is None:
                user = await db.users.find_one({"_id": user_id})
            favorites = (user or {}).get("favorite_stocks", [])
            logger.info(f"✅ [get_user_favorites] 从 users 集合获取到 {len(favorites)} 只自选股")
        else:
            # 🔥 严格过滤：只查询当前用户的自选股
            # 使用精确匹配，确保只获取当前用户的数据
            doc = await db.user_favorites.find_one({"user_id": {"$eq": user_id}})
            if doc:
                # 🔥 双重验证：确保文档的 user_id 确实匹配
                doc_user_id = doc.get("user_id")
                if doc_user_id != user_id:
                    logger.error(f"❌ [get_user_favorites] 用户ID不匹配！查询: {user_id}, 文档: {doc_user_id}")
                    favorites = []
                else:
                    favorites = doc.get("favorites", [])
                    logger.info(f"✅ [get_user_favorites] 从 user_favorites 集合获取到 {len(favorites)} 只自选股 (user_id={doc_user_id})")
            else:
                logger.warning(f"⚠️ [get_user_favorites] 未找到用户自选股数据: user_id={user_id}")
                # 🔥 调试：检查是否有其他用户的文档（仅用于调试）
                all_docs_count = await db.user_favorites.count_documents({})
                logger.info(f"🔍 [get_user_favorites] 数据库中共有 {all_docs_count} 个文档")
                if all_docs_count > 0:
                    # 只查询前5个文档用于调试
                    all_docs = await db.user_favorites.find({}, {"user_id": 1, "favorites": 1}).limit(5).to_list(length=5)
                    for idx, d in enumerate(all_docs):
                        logger.info(f"  文档 {idx+1}: user_id={d.get('user_id')}, favorites数量={len(d.get('favorites', []))}")
                favorites = []

        # 先格式化基础字段
        items = [self._format_favorite(fav) for fav in favorites]

        # 批量获取股票基础信息（板块等）
        codes = [it.get("stock_code") for it in items if it.get("stock_code")]
        if codes:
            try:
                # 🔥 获取数据源优先级配置
                from app.core.unified_config import UnifiedConfigManager
                config = UnifiedConfigManager()
                data_source_configs = await config.get_data_source_configs_async()

                # 提取启用的数据源，按优先级排序
                enabled_sources = [
                    ds.type.lower() for ds in data_source_configs
                    if ds.enabled and ds.type.lower() in ['tushare', 'akshare', 'baostock']
                ]

                if not enabled_sources:
                    enabled_sources = ['tushare', 'akshare', 'baostock']

                preferred_source = enabled_sources[0] if enabled_sources else 'tushare'

                # 从 stock_basic_info 获取板块信息（只查询优先级最高的数据源）
                basic_info_coll = db["stock_basic_info"]
                cursor = basic_info_coll.find(
                    {"code": {"$in": codes}, "source": preferred_source},  # 🔥 添加数据源筛选
                    {"code": 1, "sse": 1, "market": 1, "_id": 0}
                )
                basic_docs = await cursor.to_list(length=None)
                basic_map = {str(d.get("code")).zfill(6): d for d in (basic_docs or [])}

                for it in items:
                    code = it.get("stock_code")
                    basic = basic_map.get(code)
                    if basic:
                        # market 字段表示板块（主板、创业板、科创板等）
                        it["board"] = basic.get("market", "-")
                        # sse 字段表示交易所（上海证券交易所、深圳证券交易所等）
                        it["exchange"] = basic.get("sse", "-")
                    else:
                        it["board"] = "-"
                        it["exchange"] = "-"
            except Exception as e:
                # 查询失败时设置默认值
                for it in items:
                    it["board"] = "-"
                    it["exchange"] = "-"

        # 批量获取行情（按市场类型分别处理，避免不必要的接口调用）
        if codes:
            try:
                # 🔥 按市场类型分组
                a_share_items = []  # A股
                hk_items = []       # 港股
                us_items = []       # 美股
                
                for it in items:
                    market = it.get("market", "A股")
                    if market == "港股":
                        hk_items.append(it)
                    elif market == "美股":
                        us_items.append(it)
                    else:
                        a_share_items.append(it)
                
                # 1. 处理A股：优先使用入库的 market_quotes，30秒更新
                if a_share_items:
                    a_share_codes = [it.get("stock_code") for it in a_share_items if it.get("stock_code")]
                    if a_share_codes:
                        try:
                            coll = db["market_quotes"]
                            cursor = coll.find({"code": {"$in": a_share_codes}}, {"code": 1, "close": 1, "pct_chg": 1, "amount": 1})
                            docs = await cursor.to_list(length=None)
                            quotes_map = {str(d.get("code")).zfill(6): d for d in (docs or [])}
                            for it in a_share_items:
                                code = it.get("stock_code")
                                q = quotes_map.get(code)
                                if q:
                                    it["current_price"] = q.get("close")
                                    it["change_percent"] = q.get("pct_chg")
                                # 如果数据库中没有数据，保持 None（不调用在线 API）
                                # 用户可以通过点击"同步实时行情"按钮来更新数据
                        except Exception as e:
                            logger.warning(f"⚠️ 查询A股行情失败: {e}")
                
                # 2. 处理港股：从 market_quotes_hk 查询
                if hk_items:
                    hk_codes = [it.get("stock_code") for it in hk_items if it.get("stock_code")]
                    if hk_codes:
                        try:
                            coll = db["market_quotes_hk"]
                            cursor = coll.find({"code": {"$in": hk_codes}}, {"code": 1, "close": 1, "pct_chg": 1, "amount": 1})
                            docs = await cursor.to_list(length=None)
                            quotes_map = {str(d.get("code")): d for d in (docs or [])}
                            for it in hk_items:
                                code = it.get("stock_code")
                                q = quotes_map.get(code)
                                if q:
                                    it["current_price"] = q.get("close")
                                    it["change_percent"] = q.get("pct_chg")
                        except Exception as e:
                            logger.warning(f"⚠️ 查询港股行情失败: {e}")
                
                # 3. 处理美股：从 market_quotes_us 查询
                if us_items:
                    us_codes = [it.get("stock_code") for it in us_items if it.get("stock_code")]
                    if us_codes:
                        try:
                            coll = db["market_quotes_us"]
                            cursor = coll.find({"code": {"$in": us_codes}}, {"code": 1, "close": 1, "pct_chg": 1, "amount": 1})
                            docs = await cursor.to_list(length=None)
                            quotes_map = {str(d.get("code")): d for d in (docs or [])}
                            for it in us_items:
                                code = it.get("stock_code")
                                q = quotes_map.get(code)
                                if q:
                                    it["current_price"] = q.get("close")
                                    it["change_percent"] = q.get("pct_chg")
                        except Exception as e:
                            logger.warning(f"⚠️ 查询美股行情失败: {e}")
                            
            except Exception as e:
                logger.warning(f"⚠️ 批量获取行情失败: {e}")
                # 查询失败时保持占位 None，避免影响基础功能
                pass

        # 记录性能日志
        elapsed_time = time.time() - start_time
        logger.info(f"✅ [get_user_favorites] 查询完成: user_id={user_id}, 返回 {len(items)} 只自选股, 耗时 {elapsed_time:.2f}秒")
        if elapsed_time > 5:
            logger.warning(f"⚠️ [get_user_favorites] 接口耗时较长: {elapsed_time:.2f}秒，可能存在性能问题")

        return items

    async def add_favorite(
        self,
        user_id: str,
        stock_code: str,
        stock_name: str,
        market: str = "A股",
        tags: List[str] = None,
        notes: str = "",
        alert_price_high: Optional[float] = None,
        alert_price_low: Optional[float] = None
    ) -> bool:
        """添加股票到自选股（兼容字符串ID与ObjectId）"""
        import logging
        logger = logging.getLogger("webapi")

        try:
            logger.info(f"🔧 [add_favorite] 开始添加到研究列表: user_id={user_id}, stock_code={stock_code}")

            db = await self._get_db()
            logger.info(f"🔧 [add_favorite] 数据库连接获取成功")

            favorite_stock = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market": market,
                "added_at": datetime.utcnow(),
                "tags": tags or [],
                "notes": notes,
                "alert_price_high": alert_price_high,
                "alert_price_low": alert_price_low
            }

            logger.info(f"🔧 [add_favorite] 自选股数据构建完成: {favorite_stock}")

            is_oid = self._is_valid_object_id(user_id)
            logger.info(f"🔧 [add_favorite] 用户ID类型检查: is_valid_object_id={is_oid}")

            if is_oid:
                logger.info(f"🔧 [add_favorite] 使用 ObjectId 方式添加到 users 集合")

                # 先尝试使用 ObjectId 查询
                result = await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$push": {"favorite_stocks": favorite_stock},
                        "$setOnInsert": {"favorite_stocks": []}
                    }
                )
                logger.info(f"🔧 [add_favorite] ObjectId查询结果: matched_count={result.matched_count}, modified_count={result.modified_count}")

                # 如果 ObjectId 查询失败，尝试使用字符串查询
                if result.matched_count == 0:
                    logger.info(f"🔧 [add_favorite] ObjectId查询失败，尝试使用字符串ID查询")
                    result = await db.users.update_one(
                        {"_id": user_id},
                        {
                            "$push": {"favorite_stocks": favorite_stock}
                        }
                    )
                    logger.info(f"🔧 [add_favorite] 字符串ID查询结果: matched_count={result.matched_count}, modified_count={result.modified_count}")

                success = result.matched_count > 0
                logger.info(f"🔧 [add_favorite] 返回结果: {success}")
                return success
            else:
                logger.info(f"🔧 [add_favorite] 使用字符串ID方式添加到 user_favorites 集合")
                result = await db.user_favorites.update_one(
                    {"user_id": user_id},
                    {
                        "$setOnInsert": {"user_id": user_id, "created_at": datetime.utcnow()},
                        "$push": {"favorites": favorite_stock},
                        "$set": {"updated_at": datetime.utcnow()}
                    },
                    upsert=True
                )
                logger.info(f"🔧 [add_favorite] 更新结果: matched_count={result.matched_count}, modified_count={result.modified_count}, upserted_id={result.upserted_id}")
                logger.info(f"🔧 [add_favorite] 返回结果: True")
                return True
        except Exception as e:
            logger.error(f"❌ [add_favorite] 添加到研究列表异常: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

    async def remove_favorite(self, user_id: str, stock_code: str) -> bool:
        """从自选股中移除股票（兼容字符串ID与ObjectId）"""
        db = await self._get_db()

        if self._is_valid_object_id(user_id):
            # 先尝试使用 ObjectId 查询
            result = await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$pull": {"favorite_stocks": {"stock_code": stock_code}}}
            )
            # 如果 ObjectId 查询失败，尝试使用字符串查询
            if result.matched_count == 0:
                result = await db.users.update_one(
                    {"_id": user_id},
                    {"$pull": {"favorite_stocks": {"stock_code": stock_code}}}
                )
            return result.modified_count > 0
        else:
            result = await db.user_favorites.update_one(
                {"user_id": user_id},
                {
                    "$pull": {"favorites": {"stock_code": stock_code}},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            return result.modified_count > 0

    async def update_favorite(
        self,
        user_id: str,
        stock_code: str,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        alert_price_high: Optional[float] = None,
        alert_price_low: Optional[float] = None
    ) -> bool:
        """更新自选股信息（兼容字符串ID与ObjectId）"""
        db = await self._get_db()

        # 统一构建更新字段（根据不同集合的字段路径设置前缀）
        is_oid = self._is_valid_object_id(user_id)
        prefix = "favorite_stocks.$." if is_oid else "favorites.$."
        update_fields: Dict[str, Any] = {}
        if tags is not None:
            update_fields[prefix + "tags"] = tags
        if notes is not None:
            update_fields[prefix + "notes"] = notes
        if alert_price_high is not None:
            update_fields[prefix + "alert_price_high"] = alert_price_high
        if alert_price_low is not None:
            update_fields[prefix + "alert_price_low"] = alert_price_low

        if not update_fields:
            return True

        if is_oid:
            result = await db.users.update_one(
                {
                    "_id": ObjectId(user_id),
                    "favorite_stocks.stock_code": stock_code
                },
                {"$set": update_fields}
            )
            return result.modified_count > 0
        else:
            result = await db.user_favorites.update_one(
                {
                    "user_id": user_id,
                    "favorites.stock_code": stock_code
                },
                {
                    "$set": {
                        **update_fields,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0

    async def is_favorite(self, user_id: str, stock_code: str) -> bool:
        """检查股票是否在自选股中（兼容字符串ID与ObjectId）"""
        import logging
        logger = logging.getLogger("webapi")

        try:
            logger.info(f"🔧 [is_favorite] 检查自选股: user_id={user_id}, stock_code={stock_code}")

            db = await self._get_db()

            is_oid = self._is_valid_object_id(user_id)
            logger.info(f"🔧 [is_favorite] 用户ID类型: is_valid_object_id={is_oid}")

            if is_oid:
                # 先尝试使用 ObjectId 查询
                user = await db.users.find_one(
                    {
                        "_id": ObjectId(user_id),
                        "favorite_stocks.stock_code": stock_code
                    }
                )

                # 如果 ObjectId 查询失败，尝试使用字符串查询
                if user is None:
                    logger.info(f"🔧 [is_favorite] ObjectId查询未找到，尝试使用字符串ID查询")
                    user = await db.users.find_one(
                        {
                            "_id": user_id,
                            "favorite_stocks.stock_code": stock_code
                        }
                    )

                result = user is not None
                logger.info(f"🔧 [is_favorite] 查询结果: {result}")
                return result
            else:
                doc = await db.user_favorites.find_one(
                    {
                        "user_id": user_id,
                        "favorites.stock_code": stock_code
                    }
                )
                result = doc is not None
                logger.info(f"🔧 [is_favorite] 字符串ID查询结果: {result}")
                return result
        except Exception as e:
            logger.error(f"❌ [is_favorite] 检查自选股异常: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

    async def get_user_tags(self, user_id: str) -> List[str]:
        """获取用户使用的所有标签（兼容字符串ID与ObjectId）"""
        db = await self._get_db()

        if self._is_valid_object_id(user_id):
            pipeline = [
                {"$match": {"_id": ObjectId(user_id)}},
                {"$unwind": "$favorite_stocks"},
                {"$unwind": "$favorite_stocks.tags"},
                {"$group": {"_id": "$favorite_stocks.tags"}},
                {"$sort": {"_id": 1}}
            ]
            result = await db.users.aggregate(pipeline).to_list(None)
        else:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$unwind": "$favorites"},
                {"$unwind": "$favorites.tags"},
                {"$group": {"_id": "$favorites.tags"}},
                {"$sort": {"_id": 1}}
            ]
            result = await db.user_favorites.aggregate(pipeline).to_list(None)

        return [item["_id"] for item in result if item.get("_id")]

    def _get_mock_price(self, stock_code: str) -> float:
        """获取模拟股价"""
        # 基于股票代码生成模拟价格
        base_price = hash(stock_code) % 100 + 10
        return round(base_price + (hash(stock_code) % 1000) / 100, 2)
    
    def _get_mock_change(self, stock_code: str) -> float:
        """获取模拟涨跌幅"""
        # 基于股票代码生成模拟涨跌幅
        change = (hash(stock_code) % 2000 - 1000) / 100
        return round(change, 2)
    
    def _get_mock_volume(self, stock_code: str) -> int:
        """获取模拟成交量"""
        # 基于股票代码生成模拟成交量
        return (hash(stock_code) % 10000 + 1000) * 100


# 创建全局实例
favorites_service = FavoritesService()
