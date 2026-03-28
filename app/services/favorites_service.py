"""
自选股服务
"""

import logging

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from bson import ObjectId

from app.core.database import get_mongo_db
from app.models.user import FavoriteStock
from app.services.market_metadata_service import infer_market_metadata
from app.services.quotes_service import get_quotes_service


logger = logging.getLogger("webapi")


def _build_quote_lookup_keys(code: str, market: Optional[str] = None) -> List[str]:
    """为不同市场生成可兼容的行情代码匹配键。"""
    if not code:
        return []

    raw = str(code).strip().upper()
    keys: List[str] = []

    def _add(value: Optional[str]) -> None:
        if value and value not in keys:
            keys.append(value)

    _add(raw)

    if raw.endswith(".HK"):
        raw = raw[:-3]
        _add(raw)

    if raw.isdigit():
        stripped = raw.lstrip("0") or "0"
        _add(stripped)
        _add(stripped.zfill(5))
        _add(stripped.zfill(6))

    if market == "港股" and raw.isdigit():
        hk = (raw.lstrip("0") or "0").zfill(5)
        _add(hk)
    elif market == "A股" and raw.isdigit():
        _add(raw.zfill(6))

    return keys


def _build_batch_quote_lookup_keys(items: List[Dict[str, Any]]) -> List[str]:
    """为批量行情查询构造兼容 key，避免港股因前导零差异漏查。"""
    lookup_keys: List[str] = []

    for item in items or []:
        stock_code = item.get("stock_code")
        market = item.get("market")
        for key in _build_quote_lookup_keys(stock_code, market):
            if key not in lookup_keys:
                lookup_keys.append(key)

    return lookup_keys


def _extract_valid_price(doc: Optional[Dict[str, Any]]) -> Optional[float]:
    """从行情文档中提取有效价格。"""
    if not doc:
        return None

    for key in ("close", "current_price", "price"):
        value = doc.get(key)
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except Exception:
            continue
    return None


def _extract_change_percent(doc: Optional[Dict[str, Any]]) -> Optional[float]:
    """从行情文档中提取涨跌幅。"""
    if not doc:
        return None

    for key in ("pct_chg", "change_percent"):
        value = doc.get(key)
        try:
            if value is not None:
                return float(value)
        except Exception:
            continue
    return None


def _extract_timestamp(doc: Optional[Dict[str, Any]], *keys: str) -> Optional[str]:
    """从文档中提取时间字段，并统一转成字符串。"""
    if not doc:
        return None

    for key in keys:
        value = doc.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
    return None


def _extract_date_part(value: Optional[str]) -> Optional[str]:
    """提取 YYYY-MM-DD 日期部分。"""
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    if "/" in text:
        return text.replace("/", "-")
    return text


def _quote_rank(doc: Optional[Dict[str, Any]]) -> Tuple[int, int, int, str]:
    """为重复行情记录打分，优先选择信息更完整、时间更新的记录。"""
    if not doc:
        return (0, 0, 0, "")

    has_price = 1 if _extract_valid_price(doc) is not None else 0
    has_change = 1 if _extract_change_percent(doc) is not None else 0
    updated_at = doc.get("updated_at") or doc.get("trade_date") or ""
    data_source = str(doc.get("data_source") or doc.get("source") or "")
    return (has_price, has_change, 1 if updated_at else 0, f"{updated_at}|{data_source}")


def _pick_better_quote(current: Optional[Dict[str, Any]], candidate: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """在多条行情记录中挑出更适合展示的一条。"""
    if not current:
        return candidate
    if not candidate:
        return current
    return candidate if _quote_rank(candidate) >= _quote_rank(current) else current


def _infer_currency(market: Optional[str]) -> str:
    """根据市场推断价格货币。"""
    if market == "港股":
        return "HKD"
    if market == "美股":
        return "USD"
    return "CNY"


def infer_favorite_market_metadata(market: Optional[str], code: Optional[str]) -> Dict[str, Optional[str]]:
    """根据市场与股票代码推断交易所与板块。"""
    inferred = infer_market_metadata(market, code)
    return {
        "exchange": inferred.get("exchange"),
        "board": inferred.get("board"),
    }


def build_historical_quote_fallback(
    kline_data: Optional[List[Dict[str, Any]]],
    preferred_price: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """根据最近K线构造非实时展示兜底数据。"""
    normalized_items: List[Dict[str, Any]] = []

    for raw_item in kline_data or []:
        if not isinstance(raw_item, dict):
            continue
        close_value = raw_item.get("close")
        try:
            close_value = float(close_value) if close_value is not None else None
        except Exception:
            close_value = None
        if close_value is None or close_value <= 0:
            continue
        normalized_items.append(
            {
                "close": close_value,
                "trade_date": raw_item.get("trade_date") or raw_item.get("date"),
            }
        )

    if not normalized_items:
        return None

    latest = normalized_items[-1]
    previous = normalized_items[-2] if len(normalized_items) >= 2 else None

    try:
        base_price = float(preferred_price) if preferred_price is not None else latest["close"]
    except Exception:
        base_price = latest["close"]
    if base_price <= 0:
        base_price = latest["close"]

    change_percent = None
    if previous and previous.get("close") not in (None, 0, 0.0):
        try:
            change_percent = round((base_price / float(previous["close"]) - 1.0) * 100.0, 2)
        except Exception:
            change_percent = None

    return {
        "current_price": round(base_price, 4),
        "change_percent": change_percent,
        "trade_date": latest.get("trade_date"),
        "fallback_source": "recent_kline",
    }


def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
    """标签去空、去重并保留首次出现顺序。"""
    normalized: List[str] = []
    seen = set()

    for tag in tags or []:
        tag_name = str(tag or "").strip()
        if not tag_name or tag_name in seen:
            continue
        seen.add(tag_name)
        normalized.append(tag_name)

    return normalized


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
        return {
            "stock_code": favorite.get("stock_code"),
            "stock_name": favorite.get("stock_name"),
            "market": favorite.get("market", "A股"),
            "currency": _infer_currency(favorite.get("market", "A股")),
            "tags": _normalize_tags(favorite.get("tags", [])),
            "notes": favorite.get("notes", ""),
            "alert_price_high": favorite.get("alert_price_high"),
            "alert_price_low": favorite.get("alert_price_low"),
            # 行情占位，稍后填充
            "current_price": None,
            "change_percent": None,
            "volume": None,
            "quote_trade_date": None,
            "quote_updated_at": None,
            "price_display_mode": None,
            "price_display_hint": None,
            "change_display_mode": None,
            "change_display_hint": None,
        }

    async def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户自选股列表，并批量拉取实时行情进行富集（兼容字符串ID与ObjectId）。"""
        db = await self._get_db()

        favorites: List[Dict[str, Any]] = []
        if self._is_valid_object_id(user_id):
            # 先尝试使用 ObjectId 查询
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            # 如果 ObjectId 查询失败，尝试使用字符串查询
            if user is None:
                user = await db.users.find_one({"_id": user_id})
            favorites = (user or {}).get("favorite_stocks", [])
        else:
            doc = await db.user_favorites.find_one({"user_id": user_id})
            favorites = (doc or {}).get("favorites", [])

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
                    inferred_meta = infer_favorite_market_metadata(it.get("market"), code)
                    if basic:
                        # market 字段表示板块（主板、创业板、科创板等）
                        it["board"] = basic.get("market") or inferred_meta.get("board") or "-"
                        # sse 字段表示交易所（上海证券交易所、深圳证券交易所等）
                        it["exchange"] = basic.get("sse") or inferred_meta.get("exchange") or "-"
                    else:
                        it["board"] = inferred_meta.get("board") or "-"
                        it["exchange"] = inferred_meta.get("exchange") or "-"
            except Exception as e:
                # 查询失败时设置默认值
                for it in items:
                    inferred_meta = infer_favorite_market_metadata(it.get("market"), it.get("stock_code"))
                    it["board"] = inferred_meta.get("board") or "-"
                    it["exchange"] = inferred_meta.get("exchange") or "-"

        # 批量获取行情（优先使用入库的 market_quotes，30秒更新）
        if codes:
            try:
                coll = db["market_quotes"]
                quote_lookup_keys = _build_batch_quote_lookup_keys(items)
                cursor = coll.find(
                    {"code": {"$in": quote_lookup_keys}},
                    {
                        "code": 1,
                        "close": 1,
                        "current_price": 1,
                        "price": 1,
                        "pct_chg": 1,
                        "change_percent": 1,
                        "amount": 1,
                        "updated_at": 1,
                        "trade_date": 1,
                        "last_sync": 1,
                        "data_source": 1,
                    },
                )
                docs = await cursor.to_list(length=None)
                quotes_map: Dict[str, Dict[str, Any]] = {}
                for doc in docs or []:
                    code = str(doc.get("code") or "").strip().upper()
                    for key in _build_quote_lookup_keys(code):
                        quotes_map[key] = _pick_better_quote(quotes_map.get(key), doc)
                for it in items:
                    code = it.get("stock_code")
                    market = it.get("market")
                    q = None
                    for key in _build_quote_lookup_keys(code, market):
                        q = quotes_map.get(key)
                        if q:
                            break
                    valid_price = _extract_valid_price(q)
                    if q and valid_price is not None:
                        it["current_price"] = valid_price
                        it["change_percent"] = _extract_change_percent(q)
                        it["quote_trade_date"] = q.get("trade_date")
                        it["quote_updated_at"] = _extract_timestamp(q, "updated_at", "last_sync")
                # 兜底：对未命中的代码使用在线源补齐（可选）
                missing = []
                missing_hk = []
                for it in items:
                    code = it.get("stock_code")
                    market = it.get("market")
                    needs_quote_fill = (
                        it.get("current_price") is None
                        or it.get("change_percent") is None
                        or not it.get("quote_trade_date")
                        or not it.get("quote_updated_at")
                    )
                    if not needs_quote_fill:
                        continue
                    if market == "港股":
                        missing_hk.append(code)
                    else:
                        missing.append(code)

                if missing:
                    try:
                        quotes_online = await get_quotes_service().get_quotes(missing)
                        for it in items:
                            code = it.get("stock_code")
                            if it.get("market") == "港股":
                                continue
                            needs_online_fill = (
                                it.get("current_price") is None
                                or it.get("change_percent") is None
                                or not it.get("quote_trade_date")
                                or not it.get("quote_updated_at")
                            )
                            if not needs_online_fill:
                                continue

                            q2 = quotes_online.get(code, {}) if quotes_online else {}
                            price = _extract_valid_price(q2)
                            change = _extract_change_percent(q2)
                            if it.get("current_price") is None and price is not None:
                                it["current_price"] = price
                            if it.get("change_percent") is None and change is not None:
                                it["change_percent"] = change
                            if not it.get("quote_trade_date"):
                                it["quote_trade_date"] = q2.get("trade_date")
                            if not it.get("quote_updated_at"):
                                it["quote_updated_at"] = q2.get("updated_at")
                    except Exception:
                        pass
                if missing_hk:
                    try:
                        from app.services.foreign_stock_service import ForeignStockService

                        foreign_service = ForeignStockService(db)
                        for it in items:
                            code = it.get("stock_code")
                            market = it.get("market")
                            if market != "港股":
                                continue
                            if (
                                it.get("current_price") is not None
                                and it.get("change_percent") is not None
                                and it.get("quote_trade_date")
                                and it.get("quote_updated_at")
                            ):
                                continue

                            try:
                                quote = await foreign_service.get_quote("HK", code, force_refresh=False)
                                price = _extract_valid_price(quote)
                                change = _extract_change_percent(quote)
                                if it.get("current_price") is None and price is not None:
                                    it["current_price"] = price
                                if it.get("change_percent") is None and change is not None:
                                    it["change_percent"] = change
                                if not it.get("quote_trade_date"):
                                    it["quote_trade_date"] = quote.get("trade_date")
                                if not it.get("quote_updated_at"):
                                    it["quote_updated_at"] = quote.get("updated_at")
                            except Exception:
                                pass

                            needs_historical_fallback = (
                                it.get("current_price") is None
                                or it.get("change_percent") is None
                            )
                            if not needs_historical_fallback:
                                continue

                            try:
                                kline_data = await foreign_service.get_kline(
                                    "HK",
                                    code,
                                    period="day",
                                    limit=2,
                                    force_refresh=False,
                                )
                                fallback_quote = build_historical_quote_fallback(
                                    kline_data,
                                    preferred_price=it.get("current_price"),
                                )
                                if not fallback_quote:
                                    continue

                                fallback_trade_date = fallback_quote.get("trade_date") or "最近交易日"

                                if it.get("current_price") is None and fallback_quote.get("current_price") is not None:
                                    it["current_price"] = fallback_quote["current_price"]
                                    if not it.get("quote_trade_date"):
                                        it["quote_trade_date"] = fallback_quote.get("trade_date")
                                    it["price_display_mode"] = "historical_close_fallback"
                                    it["price_display_hint"] = (
                                        f"未获取到最新实时行情，当前展示为 {fallback_trade_date} 的最近收盘价"
                                    )

                                if it.get("change_percent") is None and fallback_quote.get("change_percent") is not None:
                                    it["change_percent"] = fallback_quote["change_percent"]
                                    if not it.get("quote_trade_date"):
                                        it["quote_trade_date"] = fallback_quote.get("trade_date")
                                    it["change_display_mode"] = "historical_close_fallback"
                                    it["change_display_hint"] = (
                                        f"当前涨跌幅按 {fallback_trade_date} 最近两根日K估算，可能与最新价格口径不同"
                                    )

                                if it.get("price_display_mode") or it.get("change_display_mode"):
                                    logger.info(
                                        "📉 自选股港股展示已回退最近K线: stock_code=%s, price_mode=%s, change_mode=%s",
                                        code,
                                        it.get("price_display_mode"),
                                        it.get("change_display_mode"),
                                    )
                            except Exception:
                                continue
                    except Exception:
                        pass

                for it in items:
                    quote_trade_date = _extract_date_part(it.get("quote_trade_date"))
                    quote_updated_at = _extract_timestamp(
                        {"value": it.get("quote_updated_at")},
                        "value",
                    )
                    updated_date = _extract_date_part(quote_updated_at)

                    if quote_trade_date:
                        it["quote_trade_date"] = quote_trade_date
                    if quote_updated_at:
                        it["quote_updated_at"] = quote_updated_at

                    if quote_trade_date and updated_date and quote_trade_date != updated_date:
                        base_hint = f"当前展示数据对应交易日 {quote_trade_date}"
                        if it.get("current_price") is not None and not it.get("price_display_hint"):
                            it["price_display_hint"] = base_hint
                        if (
                            it.get("change_percent") is not None
                            and not it.get("change_display_hint")
                            and not it.get("change_display_mode")
                        ):
                            it["change_display_hint"] = base_hint

                    if not quote_trade_date and quote_updated_at:
                        base_hint = "当前仅能确认最近一次抓取时间，暂无明确交易日信息"
                        if it.get("current_price") is not None and not it.get("price_display_hint"):
                            it["price_display_hint"] = base_hint
                        if it.get("change_percent") is not None and not it.get("change_display_hint"):
                            it["change_display_hint"] = base_hint
            except Exception:
                # 查询失败时保持占位 None，避免影响基础功能
                pass

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
            logger.info(f"🔧 [add_favorite] 开始添加自选股: user_id={user_id}, stock_code={stock_code}")

            db = await self._get_db()
            logger.info(f"🔧 [add_favorite] 数据库连接获取成功")

            favorite_stock = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market": market,
                "tags": _normalize_tags(tags),
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
            logger.error(f"❌ [add_favorite] 添加自选股异常: {type(e).__name__}: {str(e)}", exc_info=True)
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
            update_fields[prefix + "tags"] = _normalize_tags(tags)
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
