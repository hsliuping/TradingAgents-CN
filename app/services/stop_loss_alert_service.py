"""
止损提醒服务

周期扫描用户设置的止损提醒（alert_price_low），
当价格接近或跌破阈值时创建通知。
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from app.core.database import get_mongo_db
from app.models.notification import NotificationCreate
from app.services.notifications_service import get_notifications_service
from app.utils.timezone import now_tz

logger = logging.getLogger("app.services.stop_loss_alert_service")


class StopLossAlertService:
    def __init__(self):
        self.db = get_mongo_db()
        self.state_collection = "stop_loss_alert_states"

    async def ensure_indexes(self) -> None:
        try:
            await self.db[self.state_collection].create_index([("key", 1)], unique=True)
            await self.db[self.state_collection].create_index([("updated_at", -1)])
        except Exception as e:
            logger.warning("创建止损提醒索引失败(忽略): %s", e)

    async def run_once(self, near_pct: float = 0.02, cooldown_minutes: int = 180) -> None:
        """执行一次止损提醒扫描。"""
        await self.ensure_indexes()

        watch_items = await self._load_watch_items()
        if not watch_items:
            logger.info("[止损提醒] 无已配置止损提醒")
            return

        quotes = await self._load_quotes(watch_items)
        now = now_tz()
        notified = 0

        for item in watch_items:
            user_id = item["user_id"]
            code = item["code"]
            market = item["market"]
            stock_name = item.get("stock_name") or code
            threshold = item["alert_price_low"]

            current_price = self._get_price(quotes, market, code)
            if current_price is None:
                continue

            state = "safe"
            if current_price <= threshold:
                state = "below"
            elif current_price <= threshold * (1 + near_pct):
                state = "near"

            key = f"{user_id}:{market}:{code}"
            prev = await self.db[self.state_collection].find_one({"key": key})
            prev_state = prev.get("state") if prev else "safe"
            last_alert_at = prev.get("last_alert_at") if prev else None

            should_notify = False
            if state in ("near", "below"):
                if prev_state != state:
                    should_notify = True
                elif last_alert_at and now - last_alert_at >= timedelta(minutes=cooldown_minutes):
                    should_notify = True

            if should_notify:
                title = f"止损提醒：{stock_name}({code})"
                if state == "below":
                    content = (
                        f"当前价 {current_price:.2f} 已跌破止损线 {threshold:.2f}，"
                        "建议立即检查仓位与风险控制。"
                    )
                    severity = "error"
                else:
                    content = (
                        f"当前价 {current_price:.2f} 接近止损线 {threshold:.2f}，"
                        "请关注价格波动。"
                    )
                    severity = "warning"

                await get_notifications_service().create_and_publish(
                    NotificationCreate(
                        user_id=user_id,
                        type="alert",
                        title=title,
                        content=content,
                        source="stop_loss_alert",
                        severity=severity,
                        metadata={
                            "stock_code": code,
                            "market": market,
                            "current_price": current_price,
                            "stop_loss_price": threshold,
                            "state": state,
                        },
                    )
                )
                notified += 1

            set_fields = {
                "key": key,
                "user_id": user_id,
                "code": code,
                "market": market,
                "stock_name": stock_name,
                "threshold": threshold,
                "state": state,
                "current_price": current_price,
                "updated_at": now,
            }
            if should_notify:
                set_fields["last_alert_at"] = now

            await self.db[self.state_collection].update_one(
                {"key": key},
                {
                    "$set": set_fields,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

        if notified:
            logger.info("[价格下限提醒] 本轮发送 %s 条提醒", notified)
        else:
            logger.info("[价格下限提醒] 本轮无触发提醒")

    async def _load_watch_items(self) -> List[Dict[str, Any]]:
        """加载提醒监控项。

        优先级：
        1) 用户手动设置的 alert_price_low（favorites）
        2) 持仓分析最新报告里的风险关注价格（position_analysis_reports）
        """
        items: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        # 新结构：users.favorite_stocks
        cursor_users = self.db.users.find(
            {"favorite_stocks.alert_price_low": {"$ne": None}},
            {"_id": 1, "favorite_stocks": 1},
        )
        async for u in cursor_users:
            user_id = str(u.get("_id"))
            for fav in u.get("favorite_stocks", []) or []:
                low = fav.get("alert_price_low")
                code = str(fav.get("stock_code") or "").strip()
                if low is None or not code:
                    continue
                market = self._normalize_market(fav.get("market"))
                key = (user_id, market, code)
                items[key] = {
                    "user_id": user_id,
                    "code": code,
                    "market": market,
                    "stock_name": fav.get("stock_name") or code,
                    "alert_price_low": float(low),
                }

        # 旧结构：user_favorites.favorites
        cursor_old = self.db.user_favorites.find(
            {"favorites.alert_price_low": {"$ne": None}},
            {"user_id": 1, "favorites": 1},
        )
        async for d in cursor_old:
            user_id = str(d.get("user_id") or "").strip()
            if not user_id:
                continue
            for fav in d.get("favorites", []) or []:
                low = fav.get("alert_price_low")
                code = str(fav.get("stock_code") or "").strip()
                if low is None or not code:
                    continue
                market = self._normalize_market(fav.get("market"))
                key = (user_id, market, code)
                if key not in items:
                    items[key] = {
                        "user_id": user_id,
                        "code": code,
                        "market": market,
                        "stock_name": fav.get("stock_name") or code,
                        "alert_price_low": float(low),
                    }

        # 对未手动设置提醒的持仓股票：使用最新持仓分析报告里的风险关注价格
        manual_keys = set(items.keys())
        pipeline = [
            {
                "$match": {
                    "position_type": "real",
                    "status": "completed",
                    "ai_analysis.price_targets": {"$exists": True},
                }
            },
            {"$sort": {"created_at": -1}},
            {
                "$group": {
                    "_id": {"user_id": "$user_id", "position_id": "$position_id"},
                    "doc": {"$first": "$$ROOT"},
                }
            },
        ]

        latest_reports = await self.db.position_analysis_reports.aggregate(pipeline).to_list(length=None)
        for row in latest_reports:
            doc = row.get("doc") or {}
            user_id = str((doc.get("user_id") or "")).strip()
            position_id = str((doc.get("position_id") or "")).strip()  # e.g. 300033_CN
            if not user_id or "_" not in position_id:
                continue

            code, market = position_id.rsplit("_", 1)
            market = self._normalize_market(market)
            key = (user_id, market, code)
            if key in manual_keys:
                continue

            price_targets = (doc.get("ai_analysis") or {}).get("price_targets") or {}
            stop_loss = self._extract_stop_loss(price_targets)
            if stop_loss is None:
                continue

            snapshot = doc.get("position_snapshot") or {}
            items[key] = {
                "user_id": user_id,
                "code": code,
                "market": market,
                "stock_name": snapshot.get("name") or code,
                "alert_price_low": float(stop_loss),
            }

        return list(items.values())

    @staticmethod
    def _extract_stop_loss(price_targets: Dict[str, Any]) -> float | None:
        """兼容多种字段名提取风险关注价格。"""
        candidates = [
            price_targets.get("stop_loss"),
            price_targets.get("stop_loss_price"),
            price_targets.get("stopLoss"),
        ]
        for v in candidates:
            try:
                if v is not None:
                    return float(v)
            except Exception:
                continue
        return None

    async def _load_quotes(self, watch_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        market_codes: Dict[str, List[str]] = {"CN": [], "HK": [], "US": []}
        for item in watch_items:
            market_codes.setdefault(item["market"], []).append(item["code"])

        quotes: Dict[str, Dict[str, float]] = {"CN": {}, "HK": {}, "US": {}}

        if market_codes.get("CN"):
            docs = await self.db.market_quotes.find(
                {"code": {"$in": list(set(market_codes["CN"]))}},
                {"code": 1, "close": 1},
            ).to_list(length=None)
            quotes["CN"] = {str(d.get("code")).zfill(6): float(d.get("close")) for d in docs if d.get("close") is not None}

        if market_codes.get("HK"):
            docs = await self.db.market_quotes_hk.find(
                {"code": {"$in": list(set(market_codes["HK"]))}},
                {"code": 1, "close": 1},
            ).to_list(length=None)
            quotes["HK"] = {str(d.get("code")): float(d.get("close")) for d in docs if d.get("close") is not None}

        if market_codes.get("US"):
            docs = await self.db.market_quotes_us.find(
                {"code": {"$in": list(set(market_codes["US"]))}},
                {"code": 1, "close": 1},
            ).to_list(length=None)
            quotes["US"] = {str(d.get("code")): float(d.get("close")) for d in docs if d.get("close") is not None}

        return quotes

    @staticmethod
    def _normalize_market(market: Any) -> str:
        m = str(market or "CN").upper()
        if m in ("A股", "CN", "SH", "SZ"):
            return "CN"
        if m in ("港股", "HK"):
            return "HK"
        if m in ("美股", "US"):
            return "US"
        return "CN"

    @staticmethod
    def _get_price(quotes: Dict[str, Dict[str, float]], market: str, code: str):
        if market == "CN":
            return quotes.get("CN", {}).get(str(code).zfill(6))
        if market == "HK":
            return quotes.get("HK", {}).get(str(code))
        if market == "US":
            return quotes.get("US", {}).get(str(code))
        return None


_stop_loss_alert_service: StopLossAlertService | None = None


def get_stop_loss_alert_service() -> StopLossAlertService:
    global _stop_loss_alert_service
    if _stop_loss_alert_service is None:
        _stop_loss_alert_service = StopLossAlertService()
    return _stop_loss_alert_service
