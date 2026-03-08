"""
持仓分析服务
提供持仓管理和AI分析功能
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.core.database import get_mongo_db

# ==================== 特性开关 ====================
# 是否使用模板系统生成提示词（默认关闭，保持向后兼容）
# 注意：使用函数动态读取，确保 .env 文件已加载
def _use_template_prompts() -> bool:
    """动态读取 USE_TEMPLATE_PROMPTS 环境变量"""
    return os.getenv("USE_TEMPLATE_PROMPTS", "false").lower() == "true"

# 是否使用新版股票分析引擎（默认关闭，保持向后兼容）
def _use_stock_engine() -> bool:
    """动态读取 USE_STOCK_ENGINE 环境变量"""
    return os.getenv("USE_STOCK_ENGINE", "false").lower() == "true"

# 是否使用新版分析引擎（包括工作流引擎）
def _use_stock_engine() -> bool:
    """动态读取 USE_STOCK_ENGINE 环境变量"""
    return os.getenv("USE_STOCK_ENGINE", "false").lower() == "true"

from app.models.portfolio import (
    RealPosition, PositionSource, PortfolioAnalysisStatus, PositionAction,
    PositionSnapshot, PortfolioSnapshot, IndustryDistribution, AccountSnapshot,
    ConcentrationAnalysis, AIAnalysisResult, PortfolioAnalysisReport,
    PositionCreate, PositionUpdate, PositionResponse, PortfolioStatsResponse,
    PositionAnalysisRequest, PositionAnalysisReport, PositionAnalysisResult,
    PriceTarget, PositionAnalysisResponse, PositionRiskMetrics,
    RealAccount, CapitalTransaction, CapitalTransactionType,
    AccountInitRequest, AccountTransactionRequest, AccountSettingsRequest, AccountSummary,
    PositionChangeType, PositionChange, PositionChangeResponse,
    PositionOperationType, PositionOperationRequest
)
from app.utils.timezone import now_tz

logger = logging.getLogger("app.services.portfolio_service")

# 市场代码映射：前端/数据库使用的代码 -> 单股分析服务使用的中文名称
MARKET_CODE_TO_NAME = {
    "CN": "A股",
    "HK": "港股",
    "US": "美股"
}

# 市场名称映射：中文名称 -> 代码
MARKET_NAME_TO_CODE = {
    "A股": "CN",
    "港股": "HK",
    "美股": "US"
}


def convert_market_code_to_name(market_code: str) -> str:
    """将市场代码转换为中文名称（用于单股分析服务）"""
    return MARKET_CODE_TO_NAME.get(market_code, market_code)


def convert_market_name_to_code(market_name: str) -> str:
    """将市场中文名称转换为代码（用于数据库存储）"""
    return MARKET_NAME_TO_CODE.get(market_name, market_name)


class PortfolioService:
    """持仓分析服务"""

    def __init__(self):
        self.db = get_mongo_db()
        self.positions_collection = "real_positions"
        self.analysis_collection = "portfolio_analysis_reports"
        self.position_analysis_collection = "position_analysis_reports"
        self.paper_positions_collection = "paper_positions"
        self.accounts_collection = "real_accounts"
        self.transactions_collection = "capital_transactions"
        self.position_changes_collection = "position_changes"

    # ==================== 资金账户管理 ====================

    async def get_or_create_account(self, user_id: str) -> Dict[str, Any]:
        """获取或创建资金账户"""
        acc = await self.db[self.accounts_collection].find_one({"user_id": user_id})
        if not acc:
            now = now_tz()
            acc = {
                "user_id": user_id,
                "cash": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "initial_capital": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "total_deposit": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "total_withdraw": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "settings": {
                    "default_market": "CN",
                    "max_position_pct": 30.0,
                    "max_loss_pct": 10.0
                },
                "created_at": now,
                "updated_at": now
            }
            await self.db[self.accounts_collection].insert_one(acc)
        return acc

    async def initialize_account(
        self, user_id: str, initial_capital: float, currency: str = "CNY"
    ) -> Dict[str, Any]:
        """初始化资金账户（设置初始资金）"""
        acc = await self.get_or_create_account(user_id)
        now = now_tz()

        # 获取当前余额
        current_cash = acc.get("cash", {}).get(currency, 0.0)
        new_cash = current_cash + initial_capital

        # 更新账户
        update_data = {
            f"cash.{currency}": new_cash,
            f"initial_capital.{currency}": acc.get("initial_capital", {}).get(currency, 0.0) + initial_capital,
            "updated_at": now
        }
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

        # 记录交易
        transaction = {
            "user_id": user_id,
            "transaction_type": CapitalTransactionType.INITIAL.value,
            "amount": initial_capital,
            "currency": currency,
            "balance_before": current_cash,
            "balance_after": new_cash,
            "description": f"初始资金 {initial_capital:,.2f} {currency}",
            "created_at": now
        }
        await self.db[self.transactions_collection].insert_one(transaction)

        return await self.get_or_create_account(user_id)

    async def deposit(
        self, user_id: str, amount: float, currency: str = "CNY", description: str = None
    ) -> Dict[str, Any]:
        """入金"""
        acc = await self.get_or_create_account(user_id)
        now = now_tz()

        current_cash = acc.get("cash", {}).get(currency, 0.0)
        new_cash = current_cash + amount
        current_deposit = acc.get("total_deposit", {}).get(currency, 0.0)

        update_data = {
            f"cash.{currency}": new_cash,
            f"total_deposit.{currency}": current_deposit + amount,
            "updated_at": now
        }
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

        transaction = {
            "user_id": user_id,
            "transaction_type": CapitalTransactionType.DEPOSIT.value,
            "amount": amount,
            "currency": currency,
            "balance_before": current_cash,
            "balance_after": new_cash,
            "description": description or f"入金 {amount:,.2f} {currency}",
            "created_at": now
        }
        await self.db[self.transactions_collection].insert_one(transaction)

        return await self.get_or_create_account(user_id)

    async def withdraw(
        self, user_id: str, amount: float, currency: str = "CNY", description: str = None
    ) -> Dict[str, Any]:
        """出金"""
        acc = await self.get_or_create_account(user_id)
        now = now_tz()

        current_cash = acc.get("cash", {}).get(currency, 0.0)
        if current_cash < amount:
            raise ValueError(f"可用{currency}不足：需要 {amount:.2f}，可用 {current_cash:.2f}")

        new_cash = current_cash - amount
        current_withdraw = acc.get("total_withdraw", {}).get(currency, 0.0)

        update_data = {
            f"cash.{currency}": new_cash,
            f"total_withdraw.{currency}": current_withdraw + amount,
            "updated_at": now
        }
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

        transaction = {
            "user_id": user_id,
            "transaction_type": CapitalTransactionType.WITHDRAW.value,
            "amount": -amount,  # 出金为负数
            "currency": currency,
            "balance_before": current_cash,
            "balance_after": new_cash,
            "description": description or f"出金 {amount:,.2f} {currency}",
            "created_at": now
        }
        await self.db[self.transactions_collection].insert_one(transaction)

        return await self.get_or_create_account(user_id)

    async def update_account_settings(
        self, user_id: str, settings: AccountSettingsRequest
    ) -> Dict[str, Any]:
        """更新账户设置"""
        acc = await self.get_or_create_account(user_id)
        now = now_tz()

        update_data = {"updated_at": now}
        if settings.max_position_pct is not None:
            update_data["settings.max_position_pct"] = settings.max_position_pct
        if settings.max_loss_pct is not None:
            update_data["settings.max_loss_pct"] = settings.max_loss_pct
        if settings.default_market is not None:
            update_data["settings.default_market"] = settings.default_market

        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

        return await self.get_or_create_account(user_id)

    async def get_account_summary(self, user_id: str) -> AccountSummary:
        """获取账户摘要（含持仓市值计算）"""
        acc = await self.get_or_create_account(user_id)

        # 获取持仓市值（只计算用户持仓，排除模拟盘）
        positions = await self.get_positions(user_id, include_market_data=True)
        positions_value = {"CNY": 0.0, "HKD": 0.0, "USD": 0.0}
        for pos in positions:
            # 只计算非模拟盘的持仓
            if pos.source == "paper":
                continue
            currency = pos.currency or "CNY"
            positions_value[currency] = positions_value.get(currency, 0.0) + (pos.market_value or 0.0)

        # 计算各项指标
        cash = acc.get("cash", {"CNY": 0.0, "HKD": 0.0, "USD": 0.0})
        initial_capital = acc.get("initial_capital", {"CNY": 0.0, "HKD": 0.0, "USD": 0.0})
        total_deposit = acc.get("total_deposit", {"CNY": 0.0, "HKD": 0.0, "USD": 0.0})
        total_withdraw = acc.get("total_withdraw", {"CNY": 0.0, "HKD": 0.0, "USD": 0.0})

        net_capital = {}
        total_assets = {}
        profit = {}
        profit_pct = {}

        for currency in ["CNY", "HKD", "USD"]:
            # 净入金 = 初始 + 入金 - 出金
            net = (initial_capital.get(currency, 0.0) +
                   total_deposit.get(currency, 0.0) -
                   total_withdraw.get(currency, 0.0))
            net_capital[currency] = round(net, 2)

            # 总资产 = 现金 + 持仓市值
            assets = cash.get(currency, 0.0) + positions_value.get(currency, 0.0)
            total_assets[currency] = round(assets, 2)

            # 收益 = 总资产 - 净入金
            pnl = assets - net
            profit[currency] = round(pnl, 2)

            # 收益率
            if net > 0:
                profit_pct[currency] = round((pnl / net) * 100, 2)
            else:
                profit_pct[currency] = 0.0

        return AccountSummary(
            cash=cash,
            initial_capital=initial_capital,
            total_deposit=total_deposit,
            total_withdraw=total_withdraw,
            net_capital=net_capital,
            positions_value=positions_value,
            total_assets=total_assets,
            profit=profit,
            profit_pct=profit_pct,
            settings=acc.get("settings", {})
        )

    async def get_transactions(
        self, user_id: str, currency: str = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取资金交易记录"""
        query = {"user_id": user_id}
        if currency:
            query["currency"] = currency

        cursor = self.db[self.transactions_collection].find(query).sort("created_at", -1).limit(limit)
        transactions = await cursor.to_list(None)

        # 转换 ObjectId
        for t in transactions:
            t["id"] = str(t.pop("_id"))

        return transactions

    async def get_total_capital(self, user_id: str, currency: str = "CNY") -> float:
        """获取用户的总资金（现金 + 持仓市值），用于持仓分析"""
        summary = await self.get_account_summary(user_id)
        return summary.total_assets.get(currency, 0.0)

    # ==================== 持仓变动记录 ====================

    async def record_position_change(
        self,
        user_id: str,
        change_type: PositionChangeType,
        code: str,
        name: str,
        market: str,
        currency: str,
        position_id: str = None,
        quantity_before: int = 0,
        cost_price_before: float = 0.0,
        quantity_after: int = 0,
        cost_price_after: float = 0.0,
        trade_price: float = None,
        realized_profit: float = None,
        description: str = None,
        trade_time: datetime = None
    ) -> Dict[str, Any]:
        """记录持仓变动

        Args:
            trade_time: 交易时间（实际交易发生的时间，由用户手工录入）
                       如果不提供，则使用当前时间
        """
        cost_value_before = quantity_before * cost_price_before
        cost_value_after = quantity_after * cost_price_after
        quantity_change = quantity_after - quantity_before
        cash_change = cost_value_before - cost_value_after  # 正数表示释放资金

        change_doc = {
            "user_id": user_id,
            "position_id": position_id,
            "code": code,
            "name": name,
            "market": market,
            "currency": currency,
            "change_type": change_type.value,
            "quantity_before": quantity_before,
            "cost_price_before": cost_price_before,
            "cost_value_before": round(cost_value_before, 2),
            "quantity_after": quantity_after,
            "cost_price_after": cost_price_after,
            "cost_value_after": round(cost_value_after, 2),
            "quantity_change": quantity_change,
            "cash_change": round(cash_change, 2),
            "trade_price": trade_price,
            "realized_profit": round(realized_profit, 2) if realized_profit else None,
            "description": description,
            "trade_time": trade_time or now_tz(),  # 交易时间，如果不提供则使用当前时间
            "created_at": now_tz()  # 记录创建时间
        }

        result = await self.db[self.position_changes_collection].insert_one(change_doc)
        change_doc["_id"] = result.inserted_id

        logger.info(f"📝 记录持仓变动: {user_id} - {code} - {change_type.value}")
        return change_doc

    async def get_position_changes(
        self,
        user_id: str,
        code: str = None,
        market: str = None,
        change_type: str = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[PositionChangeResponse]:
        """获取持仓变动记录"""
        query = {"user_id": user_id}
        if code:
            query["code"] = code
        if market:
            query["market"] = market
        if change_type:
            query["change_type"] = change_type

        cursor = self.db[self.position_changes_collection].find(query).sort("created_at", -1).skip(skip).limit(limit)
        changes = await cursor.to_list(None)

        result = []
        for c in changes:
            result.append(PositionChangeResponse(
                id=str(c["_id"]),
                position_id=c.get("position_id"),
                code=c["code"],
                name=c["name"],
                market=c["market"],
                currency=c.get("currency", "CNY"),
                change_type=c["change_type"],
                quantity_before=c.get("quantity_before", 0),
                cost_price_before=c.get("cost_price_before", 0.0),
                cost_value_before=c.get("cost_value_before", 0.0),
                quantity_after=c.get("quantity_after", 0),
                cost_price_after=c.get("cost_price_after", 0.0),
                cost_value_after=c.get("cost_value_after", 0.0),
                quantity_change=c.get("quantity_change", 0),
                cash_change=c.get("cash_change", 0.0),
                trade_price=c.get("trade_price"),
                realized_profit=c.get("realized_profit"),
                description=c.get("description"),
                trade_time=c.get("trade_time"),  # 交易时间
                created_at=c["created_at"]
            ))

        return result

    async def get_position_changes_count(
        self,
        user_id: str,
        code: str = None,
        market: str = None,
        change_type: str = None
    ) -> int:
        """获取持仓变动记录总数"""
        query = {"user_id": user_id}
        if code:
            query["code"] = code
        if market:
            query["market"] = market
        if change_type:
            query["change_type"] = change_type

        return await self.db[self.position_changes_collection].count_documents(query)

    async def update_position_change(
        self,
        user_id: str,
        change_id: str,
        quantity: int,
        price: float,
        trade_time: datetime = None
    ) -> Dict[str, Any]:
        """
        修改单笔交易记录（用于修正录入错误：数量、单价）
        支持 buy/add/reduce/sell 类型，修改后会级联重算后续记录并更新持仓
        """
        from bson import ObjectId
        try:
            obj_id = ObjectId(change_id)
        except Exception:
            raise ValueError("无效的变动记录ID")

        change = await self.db[self.position_changes_collection].find_one(
            {"_id": obj_id, "user_id": user_id}
        )
        if not change:
            raise ValueError("变动记录不存在或无权修改")

        ct = change.get("change_type")
        if ct not in ("buy", "add", "reduce", "sell"):
            raise ValueError("仅支持修改买入、加仓、减仓、卖出记录")

        code = change["code"]
        name = change.get("name", code)
        market = change.get("market", "CN")
        currency = change.get("currency", "CNY")

        # 获取该股票所有变动记录，按时间排序
        cursor = self.db[self.position_changes_collection].find(
            {"user_id": user_id, "code": code, "market": market}
        ).sort("created_at", 1)
        all_changes = await cursor.to_list(None)

        edit_idx = None
        for i, c in enumerate(all_changes):
            if c["_id"] == obj_id:
                edit_idx = i
                break
        if edit_idx is None:
            raise ValueError("变动记录不存在")

        # 计算编辑前的状态（前一笔的 quantity_after, cost_value_after）
        prev_qty = 0
        prev_cost_val = 0.0
        if edit_idx > 0:
            prev = all_changes[edit_idx - 1]
            prev_qty = prev.get("quantity_after", 0)
            prev_cost_val = prev.get("cost_value_after", 0.0)

        # 根据类型计算编辑后的记录
        def compute_updated_change(c, qty_before, cost_val_before, new_qty, new_price):
            ct = c.get("change_type")
            cost_val_before = round(cost_val_before, 2)
            cost_price_before = round(cost_val_before / qty_before, 4) if qty_before > 0 else 0.0

            if ct in ("buy", "add"):
                qty_after = qty_before + new_qty
                cost_val_after = round(qty_before * cost_price_before + new_qty * new_price, 2)
                cost_price_after = round(cost_val_after / qty_after, 4) if qty_after > 0 else 0.0
                cost_val_after = round(qty_after * cost_price_after, 2)
                cash_change = round(cost_val_before - cost_val_after, 2)
                return {
                    "quantity_before": qty_before,
                    "cost_price_before": cost_price_before,
                    "cost_value_before": cost_val_before,
                    "quantity_after": qty_after,
                    "cost_price_after": cost_price_after,
                    "cost_value_after": cost_val_after,
                    "quantity_change": new_qty,
                    "cash_change": cash_change,
                    "trade_price": None,
                    "realized_profit": None,
                }
            else:  # reduce, sell
                qty_after = qty_before - new_qty
                cost_per_share = cost_val_before / qty_before if qty_before > 0 else 0.0
                cost_val_after = round(qty_after * cost_per_share, 2) if qty_after > 0 else 0.0
                cost_price_after = round(cost_val_after / qty_after, 4) if qty_after > 0 else 0.0
                realized = round(new_qty * (new_price - cost_per_share), 2)
                cash_change = round(cost_val_before - cost_val_after + new_qty * new_price, 2)
                return {
                    "quantity_before": qty_before,
                    "cost_price_before": cost_price_before,
                    "cost_value_before": cost_val_before,
                    "quantity_after": qty_after,
                    "cost_price_after": cost_price_after,
                    "cost_value_after": cost_val_after,
                    "quantity_change": -new_qty,
                    "cash_change": cash_change,
                    "trade_price": new_price,
                    "realized_profit": realized,
                }

        # 更新编辑的记录
        updated = compute_updated_change(change, prev_qty, prev_cost_val, quantity, price)
        update_doc = {**updated}
        if trade_time:
            update_doc["trade_time"] = trade_time
        await self.db[self.position_changes_collection].update_one(
            {"_id": obj_id, "user_id": user_id},
            {"$set": update_doc}
        )

        # 级联更新后续记录（用新的 curr 状态重算每笔的派生字段）
        curr_qty = updated["quantity_after"]
        curr_cost_val = updated["cost_value_after"]
        for i in range(edit_idx + 1, len(all_changes)):
            c = all_changes[i]
            cid = c["_id"]
            ct = c.get("change_type")
            if ct in ("buy", "add"):
                qty_change = c.get("quantity_change", 0)
                orig_qty_after = c.get("quantity_after", 0)
                orig_cost_after = c.get("cost_price_after", 0)
                unit_price = (orig_cost_after * orig_qty_after - curr_cost_val) / qty_change if qty_change > 0 else 0
                cascade_updated = compute_updated_change(c, curr_qty, curr_cost_val, qty_change, unit_price)
            else:  # reduce, sell
                qty_sold = abs(c.get("quantity_change", 0))
                trade_p = c.get("trade_price", 0)
                cascade_updated = compute_updated_change(c, curr_qty, curr_cost_val, qty_sold, trade_p)
            await self.db[self.position_changes_collection].update_one(
                {"_id": cid, "user_id": user_id},
                {"$set": cascade_updated}
            )
            curr_qty = cascade_updated["quantity_after"]
            curr_cost_val = cascade_updated["cost_value_after"]

        cost_price = round(curr_cost_val / curr_qty, 4) if curr_qty > 0 else 0.0

        # 更新 positions 表
        position = await self.db[self.positions_collection].find_one(
            {"user_id": user_id, "code": code, "market": market}
        )
        if position:
            await self.db[self.positions_collection].update_one(
                {"_id": position["_id"]},
                {"$set": {
                    "quantity": curr_qty,
                    "cost_price": cost_price,
                    "original_avg_cost": cost_price,
                    "updated_at": now_tz()
                }}
            )

        logger.info(f"单笔记录修正: {code} 变动记录 {change_id}, 数量 {quantity}, 单价 {price}")
        return {"message": "记录修正成功", "quantity": curr_qty, "cost_price": cost_price}

    async def delete_position_change(
        self,
        user_id: str,
        change_id: str
    ) -> Dict[str, Any]:
        """
        删除单笔变动记录，级联重算后续记录并更新持仓
        """
        from bson import ObjectId
        try:
            obj_id = ObjectId(change_id)
        except Exception:
            raise ValueError("无效的变动记录ID")

        change = await self.db[self.position_changes_collection].find_one(
            {"_id": obj_id, "user_id": user_id}
        )
        if not change:
            raise ValueError("变动记录不存在或无权删除")

        code = change["code"]
        market = change.get("market", "CN")

        # 获取该股票所有变动记录，按时间排序，排除要删除的
        cursor = self.db[self.position_changes_collection].find(
            {"user_id": user_id, "code": code, "market": market}
        ).sort("created_at", 1)
        all_changes = await cursor.to_list(None)
        remaining = [c for c in all_changes if c["_id"] != obj_id]

        # 删除该记录
        await self.db[self.position_changes_collection].delete_one(
            {"_id": obj_id, "user_id": user_id}
        )

        # 重放剩余记录，级联更新每条
        def compute_updated_change(c, qty_before, cost_val_before, new_qty, new_price):
            ct = c.get("change_type")
            cost_val_before = round(cost_val_before, 2)
            cost_price_before = round(cost_val_before / qty_before, 4) if qty_before > 0 else 0.0
            if ct in ("buy", "add"):
                qty_after = qty_before + new_qty
                cost_val_after = round(qty_before * cost_price_before + new_qty * new_price, 2)
                cost_price_after = round(cost_val_after / qty_after, 4) if qty_after > 0 else 0.0
                cost_val_after = round(qty_after * cost_price_after, 2)
                cash_change = round(cost_val_before - cost_val_after, 2)
                return {
                    "quantity_before": qty_before, "cost_price_before": cost_price_before,
                    "cost_value_before": cost_val_before, "quantity_after": qty_after,
                    "cost_price_after": cost_price_after, "cost_value_after": cost_val_after,
                    "quantity_change": new_qty, "cash_change": cash_change,
                    "trade_price": None, "realized_profit": None,
                }
            else:
                qty_after = qty_before - new_qty
                cost_per_share = cost_val_before / qty_before if qty_before > 0 else 0.0
                cost_val_after = round(qty_after * cost_per_share, 2) if qty_after > 0 else 0.0
                cost_price_after = round(cost_val_after / qty_after, 4) if qty_after > 0 else 0.0
                realized = round(new_qty * (new_price - cost_per_share), 2)
                cash_change = round(cost_val_before - cost_val_after + new_qty * new_price, 2)
                return {
                    "quantity_before": qty_before, "cost_price_before": cost_price_before,
                    "cost_value_before": cost_val_before, "quantity_after": qty_after,
                    "cost_price_after": cost_price_after, "cost_value_after": cost_val_after,
                    "quantity_change": -new_qty, "cash_change": cash_change,
                    "trade_price": new_price, "realized_profit": realized,
                }

        curr_qty = 0
        curr_cost_val = 0.0
        for c in remaining:
            cid = c["_id"]
            ct = c.get("change_type")
            if ct in ("buy", "add"):
                qty_change = c.get("quantity_change", 0)
                orig_qty_after = c.get("quantity_after", 0)
                orig_cost_after = c.get("cost_price_after", 0)
                unit_price = (orig_cost_after * orig_qty_after - curr_cost_val) / qty_change if qty_change > 0 else 0
                updated = compute_updated_change(c, curr_qty, curr_cost_val, qty_change, unit_price)
            else:
                qty_sold = abs(c.get("quantity_change", 0))
                trade_p = c.get("trade_price", 0)
                updated = compute_updated_change(c, curr_qty, curr_cost_val, qty_sold, trade_p)
            await self.db[self.position_changes_collection].update_one(
                {"_id": cid, "user_id": user_id},
                {"$set": updated}
            )
            curr_qty = updated["quantity_after"]
            curr_cost_val = updated["cost_value_after"]

        cost_price = round(curr_cost_val / curr_qty, 4) if curr_qty > 0 else 0.0

        position = await self.db[self.positions_collection].find_one(
            {"user_id": user_id, "code": code, "market": market}
        )
        if position:
            await self.db[self.positions_collection].update_one(
                {"_id": position["_id"]},
                {"$set": {
                    "quantity": curr_qty,
                    "cost_price": cost_price,
                    "original_avg_cost": cost_price,
                    "updated_at": now_tz()
                }}
            )
        elif curr_qty > 0:
            # 有变动记录但无持仓，需新建
            name = change.get("name", code)
            currency = change.get("currency", "CNY")
            now = now_tz()
            await self.db[self.positions_collection].insert_one({
                "user_id": user_id, "code": code, "name": name, "market": market,
                "currency": currency, "quantity": curr_qty, "cost_price": cost_price,
                "original_avg_cost": cost_price, "source": PositionSource.MANUAL.value,
                "created_at": now, "updated_at": now
            })

        logger.info(f"删除变动记录: {code} {change_id}")
        return {"message": "删除成功", "quantity": curr_qty, "cost_price": cost_price}

    async def reset_position(self, user_id: str, code: str, market: str = "CN") -> Dict[str, Any]:
        """
        重置整个持仓：删除该股票的所有变动记录和持仓，资金不返还（用户重新录入）
        """
        position = await self.db[self.positions_collection].find_one(
            {"user_id": user_id, "code": code, "market": market}
        )
        deleted_changes = await self.db[self.position_changes_collection].delete_many(
            {"user_id": user_id, "code": code, "market": market}
        )
        result = await self.db[self.positions_collection].delete_one(
            {"user_id": user_id, "code": code, "market": market}
        )
        logger.info(f"重置持仓: {code} {market}, 删除 {deleted_changes.deleted_count} 条变动, 持仓 {'已删' if result.deleted_count else '不存在'}")
        return {
            "message": "重置成功",
            "deleted_changes": deleted_changes.deleted_count,
            "position_deleted": result.deleted_count > 0
        }

    async def reset_all_positions(self, user_id: str) -> Dict[str, Any]:
        """
        清零全部持仓：删除该用户所有持仓和变动记录，并重置资金账户
        资金账户重置为：现金=初始资金，累计入金/出金清零，累计收益归零
        """
        deleted_changes = await self.db[self.position_changes_collection].delete_many(
            {"user_id": user_id}
        )
        deleted_positions = await self.db[self.positions_collection].delete_many(
            {"user_id": user_id}
        )

        # 重置资金账户：现金恢复为初始资金，入金/出金清零
        acc = await self.get_or_create_account(user_id)
        initial_capital = acc.get("initial_capital", {"CNY": 0.0, "HKD": 0.0, "USD": 0.0})
        now = now_tz()
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {
                "cash": dict(initial_capital),
                "total_deposit": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "total_withdraw": {"CNY": 0.0, "HKD": 0.0, "USD": 0.0},
                "updated_at": now
            }}
        )

        logger.info(f"清零全部持仓: user={user_id}, 删除 {deleted_changes.deleted_count} 条变动, {deleted_positions.deleted_count} 个持仓, 资金账户已重置")
        return {
            "message": "清零成功",
            "deleted_changes": deleted_changes.deleted_count,
            "deleted_positions": deleted_positions.deleted_count
        }

    # ==================== 持仓管理 ====================

    async def get_positions(
        self, 
        user_id: str, 
        source: str = "all",
        include_market_data: bool = True
    ) -> List[PositionResponse]:
        """
        获取用户持仓列表
        
        Args:
            user_id: 用户ID
            source: 数据来源 (all/real/paper)
            include_market_data: 是否包含实时行情
        """
        positions = []

        # 获取用户持仓（只获取 quantity > 0 的持仓）
        if source in ["all", "real"]:
            real_positions = await self.db[self.positions_collection].find(
                {"user_id": user_id, "quantity": {"$gt": 0}}
            ).to_list(None)

            for p in real_positions:
                pos = await self._enrich_position(p, "real", include_market_data)
                positions.append(pos)

        # 获取模拟交易持仓（只获取 quantity > 0 的持仓）
        if source in ["all", "paper"]:
            paper_positions = await self.db[self.paper_positions_collection].find(
                {"user_id": user_id, "quantity": {"$gt": 0}}
            ).to_list(None)
            
            for p in paper_positions:
                pos = await self._enrich_position(p, "paper", include_market_data)
                positions.append(pos)

        return positions

    async def get_history_positions(
        self,
        user_id: str,
        source: str = "real",
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """
        获取历史持仓（已清仓的记录）
        按股票代码聚合，显示每只股票的交易汇总
        只显示已完全清仓的持仓（买入数量 = 卖出数量）
        """
        # 从变动记录中聚合历史持仓数据
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": {"code": "$code", "market": "$market"},
                "name": {"$last": "$name"},
                "currency": {"$last": "$currency"},
                "first_buy_date": {"$min": {"$cond": [
                    {"$in": ["$change_type", ["buy", "add"]]},
                    "$trade_time", None
                ]}},
                "last_sell_date": {"$max": {"$cond": [
                    {"$in": ["$change_type", ["sell", "reduce"]]},
                    "$trade_time", None
                ]}},
                "total_buy_qty": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["buy", "add"]]},
                    {"$abs": "$quantity_change"}, 0
                ]}},
                "total_sell_qty": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["sell", "reduce"]]},
                    {"$abs": "$quantity_change"}, 0
                ]}},
                "total_buy_amount": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["buy", "add"]]},
                    {"$abs": "$cash_change"}, 0
                ]}},
                "total_sell_amount": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["sell", "reduce"]]},
                    {"$abs": "$cash_change"}, 0
                ]}},
                "total_realized_pnl": {"$sum": {"$ifNull": ["$realized_profit", 0]}},
                "avg_buy_price": {"$avg": {"$cond": [
                    {"$in": ["$change_type", ["buy", "add"]]},
                    "$cost_price_after", None
                ]}},
                "avg_sell_price": {"$avg": {"$cond": [
                    {"$in": ["$change_type", ["sell", "reduce"]]},
                    "$trade_price", None
                ]}}
            }},
            # 只显示已完全清仓的（买入数量 = 卖出数量）
            {"$match": {
                "$expr": {
                    "$and": [
                        {"$gt": ["$total_sell_qty", 0]},
                        {"$eq": ["$total_buy_qty", "$total_sell_qty"]}
                    ]
                }
            }},
            {"$sort": {"last_sell_date": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]

        results = await self.db[self.position_changes_collection].aggregate(pipeline).to_list(None)

        # 计算总数
        count_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": {"code": "$code", "market": "$market"},
                "total_buy_qty": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["buy", "add"]]},
                    {"$abs": "$quantity_change"}, 0
                ]}},
                "total_sell_qty": {"$sum": {"$cond": [
                    {"$in": ["$change_type", ["sell", "reduce"]]},
                    {"$abs": "$quantity_change"}, 0
                ]}}
            }},
            {"$match": {
                "$expr": {
                    "$and": [
                        {"$gt": ["$total_sell_qty", 0]},
                        {"$eq": ["$total_buy_qty", "$total_sell_qty"]}
                    ]
                }
            }},
            {"$count": "total"}
        ]
        count_result = await self.db[self.position_changes_collection].aggregate(count_pipeline).to_list(None)
        total = count_result[0]["total"] if count_result else 0

        items = []
        for r in results:
            # 计算持有天数
            first_buy = r.get("first_buy_date")
            last_sell = r.get("last_sell_date")
            hold_days = 0
            if first_buy and last_sell:
                # 🔥 处理字符串类型的日期（MongoDB可能返回字符串）
                if isinstance(first_buy, str):
                    first_buy = datetime.fromisoformat(first_buy.replace('Z', '+00:00'))
                if isinstance(last_sell, str):
                    last_sell = datetime.fromisoformat(last_sell.replace('Z', '+00:00'))
                delta = last_sell - first_buy
                hold_days = delta.days

            # 计算盈亏百分比
            total_buy_amount = r.get("total_buy_amount", 0)
            total_realized_pnl = r.get("total_realized_pnl", 0)
            realized_pnl_pct = 0
            if total_buy_amount > 0:
                realized_pnl_pct = (total_realized_pnl / total_buy_amount) * 100

            items.append({
                "id": f"{r['_id']['code']}_{r['_id']['market']}",
                "code": r["_id"]["code"],
                "name": r.get("name"),
                "market": r["_id"]["market"],
                "currency": r.get("currency", "CNY"),
                "total_buy_qty": r.get("total_buy_qty", 0),
                "total_sell_qty": r.get("total_sell_qty", 0),
                "avg_buy_price": round(r.get("avg_buy_price") or 0, 2),
                "avg_sell_price": round(r.get("avg_sell_price") or 0, 2),
                "first_buy_date": first_buy.isoformat() if first_buy else None,
                "last_trade_date": last_sell.isoformat() if last_sell else None,
                "realized_pnl": round(total_realized_pnl, 2),
                "realized_pnl_pct": round(realized_pnl_pct, 2),
                "hold_days": hold_days,
                "cleared_at": last_sell.isoformat() if last_sell else None
            })

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "skip": skip
        }

    async def _enrich_position(
        self, 
        position: Dict, 
        source: str,
        include_market_data: bool = True
    ) -> PositionResponse:
        """丰富持仓数据（添加实时行情）"""
        code = position.get("code", "")
        market = position.get("market", "CN")
        quantity = int(position.get("quantity", 0))
        
        # 获取成本价
        if source == "paper":
            cost_price = float(position.get("avg_cost", 0.0))
            original_avg_cost = cost_price  # 模拟盘无原始成本区分
        else:
            cost_price = float(position.get("cost_price", 0.0))
            # 向后兼容：无 original_avg_cost 时使用 cost_price
            original_avg_cost = position.get("original_avg_cost")
            if original_avg_cost is None:
                original_avg_cost = cost_price
            else:
                original_avg_cost = float(original_avg_cost)

        # 获取实时价格
        current_price = None
        market_value = None
        unrealized_pnl = None
        unrealized_pnl_pct = None

        if include_market_data:
            current_price = await self._get_stock_price(code, market)
            if current_price and current_price > 0:
                market_value = round(current_price * quantity, 2)
                cost_value = cost_price * quantity
                if cost_value > 0:
                    unrealized_pnl = round(market_value - cost_value, 2)
                    unrealized_pnl_pct = round((unrealized_pnl / cost_value) * 100, 2)

        # 获取股票名称
        name = position.get("name")
        if not name:
            name = await self._get_stock_name(code, market)

        # 🔥 获取行业信息：如果为空，尝试从数据库获取并更新
        industry = position.get("industry")
        if not industry or industry == "未知":
            logger.info(f"🔄 [丰富持仓] 持仓 {code} ({source}) 行业为空或'未知'，尝试获取...")
            industry = await self._get_stock_industry(code, market)
            logger.info(f"📊 [丰富持仓] 持仓 {code} 获取到的行业: {industry}")
            
            # 如果获取到了行业信息，更新到数据库
            if industry:
                try:
                    position_id = position.get("_id")
                    if position_id:
                        # 根据数据源选择对应的集合
                        collection_name = self.paper_positions_collection if source == "paper" else self.positions_collection
                        
                        update_result = await self.db[collection_name].update_one(
                            {"_id": position_id},
                            {"$set": {"industry": industry, "updated_at": now_tz()}}
                        )
                        if update_result.modified_count > 0:
                            logger.info(f"✅ [丰富持仓] 已更新持仓 {code} ({source}) 的行业信息: {industry}")
                        else:
                            logger.debug(f"ℹ️ [丰富持仓] 持仓 {code} 行业信息未修改（可能已存在）")
                except Exception as e:
                    logger.warning(f"⚠️ [丰富持仓] 更新持仓 {code} 行业信息失败: {e}")
            else:
                # 如果无法获取，使用"未知"
                logger.warning(f"⚠️ [丰富持仓] 持仓 {code} 无法获取行业信息，使用'未知'")
                industry = "未知"

        return PositionResponse(
            id=str(position.get("_id", "")),
            code=code,
            name=name,
            market=market,
            currency=position.get("currency", "CNY"),
            quantity=quantity,
            cost_price=cost_price,
            original_avg_cost=round(original_avg_cost, 4) if original_avg_cost is not None else None,
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            buy_date=position.get("buy_date"),
            industry=industry,
            notes=position.get("notes"),
            source=source,
            created_at=position.get("created_at", now_tz()),
            updated_at=position.get("updated_at", now_tz())
        )

    async def add_position(self, user_id: str, data: PositionCreate) -> PositionResponse:
        """添加用户持仓（如果已有持仓则自动加仓）"""
        # 获取股票名称和行业
        name = data.name
        logger.debug(f"📝 [添加持仓] 股票代码: {data.code}, 市场: {data.market}, 已有名称: {name}")
        
        # 🔥 修复：无论名称是否为空，都尝试获取行业信息
        # 如果名称为空，先获取名称；如果名称不为空，也要获取行业信息
        if not name:
            name = await self._get_stock_name(data.code, data.market)
            logger.debug(f"📝 [添加持仓] 获取到的名称: {name}")
        
        # 始终尝试获取行业信息（即使名称已存在）
        industry = await self._get_stock_industry(data.code, data.market)
        logger.info(f"📝 [添加持仓] 股票 {data.code} 行业信息: {industry}")

        # 计算持仓成本
        currency = self._get_currency_by_market(data.market)
        position_cost = data.quantity * data.cost_price

        # 从资金账户中扣除成本
        account = await self.get_or_create_account(user_id)
        current_cash = account.get("cash", {}).get(currency, 0.0)

        if current_cash < position_cost:
            raise ValueError(f"可用资金不足。当前可用: {current_cash:.2f} {currency}，需要: {position_cost:.2f} {currency}")

        # 检查是否已有该股票的持仓（同一用户、同一股票代码、同一市场）
        existing_position = await self.db[self.positions_collection].find_one({
            "user_id": user_id,
            "code": data.code,
            "market": data.market,
            "quantity": {"$gt": 0}  # 只查找数量大于0的持仓（未清仓的）
        })

        if existing_position:
            # 已有持仓，执行加仓操作
            old_quantity = existing_position.get("quantity", 0)
            old_cost_price = existing_position.get("cost_price", 0.0)
            old_total_cost = old_quantity * old_cost_price

            # 计算新的持仓数量和平均成本价
            new_quantity = old_quantity + data.quantity
            new_total_cost = old_total_cost + position_cost
            new_cost_price = new_total_cost / new_quantity if new_quantity > 0 else 0.0

            # 扣除资金
            new_cash = current_cash - position_cost
            await self.db[self.accounts_collection].update_one(
                {"user_id": user_id},
                {"$set": {f"cash.{currency}": new_cash, "updated_at": now_tz()}}
            )

            # 更新持仓记录（加仓时 cost_price 与 original_avg_cost 均为加权均价）
            now = now_tz()
            await self.db[self.positions_collection].update_one(
                {"_id": existing_position["_id"]},
                {"$set": {
                    "quantity": new_quantity,
                    "cost_price": round(new_cost_price, 4),
                    "original_avg_cost": round(new_cost_price, 4),
                    "updated_at": now,
                    "notes": data.notes if data.notes else existing_position.get("notes")
                }}
            )

            # 记录持仓变动（加仓）
            await self.record_position_change(
                user_id=user_id,
                change_type=PositionChangeType.BUY,
                code=data.code,
                name=name or existing_position.get("name") or data.code,
                market=data.market,
                currency=currency,
                position_id=str(existing_position["_id"]),
                quantity_before=old_quantity,
                cost_price_before=old_cost_price,
                quantity_after=new_quantity,
                cost_price_after=new_cost_price,
                description=f"加仓: +{data.quantity}股 @ {data.cost_price:.2f}"
            )

            logger.info(f"✅ 加仓成功: {user_id} - {data.code}，{old_quantity} → {new_quantity}股，成本价: {old_cost_price:.2f} → {new_cost_price:.2f}，扣除资金: {position_cost:.2f} {currency}")

            # 返回更新后的持仓
            updated_position = await self.db[self.positions_collection].find_one({"_id": existing_position["_id"]})
            return await self._enrich_position(updated_position, "real")

        # 没有已有持仓，新建持仓记录
        # 扣除资金
        new_cash = current_cash - position_cost
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {f"cash.{currency}": new_cash, "updated_at": now_tz()}}
        )

        now = now_tz()
        position_doc = {
            "user_id": user_id,
            "code": data.code,
            "name": name,
            "market": data.market,
            "currency": currency,
            "quantity": data.quantity,
            "cost_price": data.cost_price,
            "original_avg_cost": data.cost_price,
            "buy_date": data.buy_date,
            "industry": industry,
            "notes": data.notes,
            "source": PositionSource.MANUAL.value,
            "created_at": now,
            "updated_at": now
        }

        result = await self.db[self.positions_collection].insert_one(position_doc)
        position_doc["_id"] = result.inserted_id

        # 记录持仓变动
        await self.record_position_change(
            user_id=user_id,
            change_type=PositionChangeType.BUY,
            code=data.code,
            name=name or data.code,
            market=data.market,
            currency=currency,
            position_id=str(result.inserted_id),
            quantity_before=0,
            cost_price_before=0.0,
            quantity_after=data.quantity,
            cost_price_after=data.cost_price,
            description=f"新建持仓: {data.notes}" if data.notes else "新建持仓",
            trade_time=data.buy_date  # 使用买入日期作为交易时间
        )

        logger.info(f"✅ 新建持仓成功: {user_id} - {data.code}，扣除资金: {position_cost:.2f} {currency}")
        return await self._enrich_position(position_doc, "real")

    async def operate_position(
        self,
        user_id: str,
        data: PositionOperationRequest
    ) -> Dict[str, Any]:
        """
        执行持仓操作（加仓、减仓、分红、拆股、合股、调整成本）
        """
        # 查找该股票的现有持仓
        existing_position = await self.db[self.positions_collection].find_one({
            "user_id": user_id,
            "code": data.code,
            "market": data.market,
            "quantity": {"$gt": 0}
        })

        if not existing_position and data.operation_type != PositionOperationType.ADD:
            raise ValueError(f"未找到 {data.code} 的持仓记录")

        currency = self._get_currency_by_market(data.market)
        now = now_tz()

        if data.operation_type == PositionOperationType.ADD:
            # 加仓：复用 add_position 逻辑
            return await self._handle_add_operation(user_id, data, existing_position, currency, now)

        elif data.operation_type == PositionOperationType.REDUCE:
            # 减仓
            return await self._handle_reduce_operation(user_id, data, existing_position, currency, now)

        elif data.operation_type == PositionOperationType.DIVIDEND:
            # 分红
            return await self._handle_dividend_operation(user_id, data, existing_position, currency, now)

        elif data.operation_type == PositionOperationType.SPLIT:
            # 拆股
            return await self._handle_split_operation(user_id, data, existing_position, currency, now)

        elif data.operation_type == PositionOperationType.MERGE:
            # 合股
            return await self._handle_merge_operation(user_id, data, existing_position, currency, now)

        elif data.operation_type == PositionOperationType.ADJUST:
            # 调整成本价
            return await self._handle_adjust_operation(user_id, data, existing_position, currency, now)

        else:
            raise ValueError(f"不支持的操作类型: {data.operation_type}")

    async def _handle_add_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Optional[Dict], currency: str, now
    ) -> Dict[str, Any]:
        """处理加仓操作"""
        if not data.quantity or not data.price:
            raise ValueError("加仓需要指定数量和价格")

        position_cost = data.quantity * data.price

        # 检查资金
        account = await self.get_or_create_account(user_id)
        current_cash = account.get("cash", {}).get(currency, 0.0)
        if current_cash < position_cost:
            raise ValueError(f"可用资金不足。当前: {current_cash:.2f}，需要: {position_cost:.2f}")

        # 扣除资金
        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {f"cash.{currency}": current_cash - position_cost, "updated_at": now}}
        )

        if existing_position:
            # 已有持仓，合并（加仓时 cost_price 与 original_avg_cost 均为加权均价）
            old_qty = existing_position["quantity"]
            old_cost = existing_position["cost_price"]
            new_qty = old_qty + data.quantity
            new_cost = (old_qty * old_cost + position_cost) / new_qty

            await self.db[self.positions_collection].update_one(
                {"_id": existing_position["_id"]},
                {"$set": {
                    "quantity": new_qty,
                    "cost_price": round(new_cost, 4),
                    "original_avg_cost": round(new_cost, 4),
                    "updated_at": now
                }}
            )

            await self.record_position_change(
                user_id=user_id, change_type=PositionChangeType.BUY,
                code=data.code, name=existing_position.get("name", data.code),
                market=data.market, currency=currency,
                position_id=str(existing_position["_id"]),
                quantity_before=old_qty, cost_price_before=old_cost,
                quantity_after=new_qty, cost_price_after=new_cost,
                description=f"加仓: +{data.quantity}股 @ {data.price:.2f}",
                trade_time=data.operation_date  # 使用操作日期作为交易时间
            )

            logger.info(f"✅ 加仓成功: {data.code}, {old_qty} → {new_qty}股")
            return {"message": "加仓成功", "new_quantity": new_qty, "new_cost_price": round(new_cost, 4)}
        else:
            # 新建持仓
            name = await self._get_stock_name(data.code, data.market)
            position_doc = {
                "user_id": user_id, "code": data.code, "name": name,
                "market": data.market, "currency": currency,
                "quantity": data.quantity, "cost_price": data.price,
                "original_avg_cost": data.price,
                "buy_date": data.operation_date or now,
                "source": PositionSource.MANUAL.value,
                "created_at": now, "updated_at": now
            }
            result = await self.db[self.positions_collection].insert_one(position_doc)

            await self.record_position_change(
                user_id=user_id, change_type=PositionChangeType.BUY,
                code=data.code, name=name or data.code,
                market=data.market, currency=currency,
                position_id=str(result.inserted_id),
                quantity_before=0, cost_price_before=0.0,
                quantity_after=data.quantity, cost_price_after=data.price,
                description="新建持仓",
                trade_time=data.operation_date  # 使用操作日期作为交易时间
            )

            logger.info(f"✅ 新建持仓: {data.code}, {data.quantity}股 @ {data.price:.2f}")
            return {"message": "新建持仓成功", "new_quantity": data.quantity, "new_cost_price": data.price}

    async def _handle_reduce_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Dict, currency: str, now
    ) -> Dict[str, Any]:
        """处理减仓操作"""
        if not data.quantity or not data.price:
            raise ValueError("减仓需要指定数量和价格")

        old_qty = existing_position["quantity"]
        old_cost = existing_position["cost_price"]

        if data.quantity > old_qty:
            raise ValueError(f"减仓数量({data.quantity})超过持仓数量({old_qty})")

        # 计算卖出金额，增加到现金
        sell_amount = data.quantity * data.price
        account = await self.get_or_create_account(user_id)
        current_cash = account.get("cash", {}).get(currency, 0.0)

        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {f"cash.{currency}": current_cash + sell_amount, "updated_at": now}}
        )

        new_qty = old_qty - data.quantity
        old_total_cost = old_qty * old_cost

        if new_qty == 0:
            # 清仓
            await self.db[self.positions_collection].update_one(
                {"_id": existing_position["_id"]},
                {"$set": {"quantity": 0, "updated_at": now}}
            )
            change_type = PositionChangeType.SELL
            description = f"清仓: -{data.quantity}股 @ {data.price:.2f}"
            new_cost = 0.0
        else:
            # 部分减仓：使用摊薄成本逻辑（与主流交易软件一致）
            # 剩余成本 = (原持仓总成本 - 本次卖出金额) / 剩余数量
            # 盈利减仓时成本降低，亏损减仓时成本升高
            remaining_cost = old_total_cost - sell_amount
            new_cost = remaining_cost / new_qty if new_qty > 0 else 0.0
            # 避免负成本（极端盈利时），保底为 0.01
            new_cost = max(0.01, round(new_cost, 4))

            await self.db[self.positions_collection].update_one(
                {"_id": existing_position["_id"]},
                {"$set": {"quantity": new_qty, "cost_price": new_cost, "updated_at": now}}
            )
            change_type = PositionChangeType.REDUCE
            description = f"减仓: -{data.quantity}股 @ {data.price:.2f}，成本 {old_cost:.2f} → {new_cost:.2f}"

        # 计算盈亏
        profit = (data.price - old_cost) * data.quantity
        profit_pct = (data.price - old_cost) / old_cost * 100 if old_cost > 0 else 0

        await self.record_position_change(
            user_id=user_id, change_type=change_type,
            code=data.code, name=existing_position.get("name", data.code),
            market=data.market, currency=currency,
            position_id=str(existing_position["_id"]),
            quantity_before=old_qty, cost_price_before=old_cost,
            quantity_after=new_qty, cost_price_after=new_cost,
            trade_price=data.price,
            realized_profit=profit,
            description=description,
            trade_time=data.operation_date  # 使用操作日期作为交易时间
        )

        logger.info(
            f"✅ 减仓成功: {data.code}, {old_qty} → {new_qty}股, "
            f"成本 {old_cost:.2f} → {new_cost:.2f}, 盈亏: {profit:.2f}"
        )
        result = {
            "message": "清仓成功" if new_qty == 0 else "减仓成功",
            "new_quantity": new_qty,
            "sell_amount": round(sell_amount, 2),
            "profit": round(profit, 2),
            "profit_pct": round(profit_pct, 2),
        }
        if new_qty > 0:
            result["new_cost_price"] = round(new_cost, 4)
        return result

    async def _handle_dividend_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Dict, currency: str, now
    ) -> Dict[str, Any]:
        """处理分红操作"""
        if not data.dividend_amount or data.dividend_amount <= 0:
            raise ValueError("分红需要指定分红金额")

        # 分红金额加入现金
        account = await self.get_or_create_account(user_id)
        current_cash = account.get("cash", {}).get(currency, 0.0)

        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {f"cash.{currency}": current_cash + data.dividend_amount, "updated_at": now}}
        )

        # 记录变动
        await self.record_position_change(
            user_id=user_id, change_type=PositionChangeType.ADJUST,
            code=data.code, name=existing_position.get("name", data.code),
            market=data.market, currency=currency,
            position_id=str(existing_position["_id"]),
            quantity_before=existing_position["quantity"],
            cost_price_before=existing_position["cost_price"],
            quantity_after=existing_position["quantity"],
            cost_price_after=existing_position["cost_price"],
            description=f"现金分红: +{data.dividend_amount:.2f} {currency}",
            trade_time=data.operation_date  # 使用操作日期作为交易时间
        )

        logger.info(f"✅ 分红成功: {data.code}, +{data.dividend_amount:.2f} {currency}")
        return {"message": "分红记录成功", "dividend_amount": data.dividend_amount}

    async def _handle_split_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Dict, currency: str, now
    ) -> Dict[str, Any]:
        """处理拆股操作（如 10送10，比例为 2:1）"""
        if not data.ratio:
            raise ValueError("拆股需要指定比例，如 2:1")

        try:
            parts = data.ratio.split(":")
            new_ratio = float(parts[0])
            old_ratio = float(parts[1])
            multiplier = new_ratio / old_ratio
        except Exception:
            raise ValueError("比例格式错误，应为 x:y 格式，如 2:1")

        old_qty = existing_position["quantity"]
        old_cost = existing_position["cost_price"]

        new_qty = int(old_qty * multiplier)
        new_cost = old_cost / multiplier

        await self.db[self.positions_collection].update_one(
            {"_id": existing_position["_id"]},
            {"$set": {"quantity": new_qty, "cost_price": round(new_cost, 4), "updated_at": now}}
        )

        await self.record_position_change(
            user_id=user_id, change_type=PositionChangeType.ADJUST,
            code=data.code, name=existing_position.get("name", data.code),
            market=data.market, currency=currency,
            position_id=str(existing_position["_id"]),
            quantity_before=old_qty, cost_price_before=old_cost,
            quantity_after=new_qty, cost_price_after=new_cost,
            description=f"拆股: {data.ratio}，数量 {old_qty} → {new_qty}",
            trade_time=data.operation_date  # 使用操作日期作为交易时间
        )

        logger.info(f"✅ 拆股成功: {data.code}, {old_qty} → {new_qty}股")
        return {"message": "拆股成功", "new_quantity": new_qty, "new_cost_price": round(new_cost, 4)}

    async def _handle_merge_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Dict, currency: str, now
    ) -> Dict[str, Any]:
        """处理合股操作（如 10合1，比例为 1:10）"""
        if not data.ratio:
            raise ValueError("合股需要指定比例，如 1:10")

        try:
            parts = data.ratio.split(":")
            new_ratio = float(parts[0])
            old_ratio = float(parts[1])
            multiplier = new_ratio / old_ratio
        except Exception:
            raise ValueError("比例格式错误，应为 x:y 格式，如 1:10")

        old_qty = existing_position["quantity"]
        old_cost = existing_position["cost_price"]

        new_qty = int(old_qty * multiplier)
        new_cost = old_cost / multiplier

        if new_qty < 1:
            raise ValueError(f"合股后数量({new_qty})不能小于1")

        await self.db[self.positions_collection].update_one(
            {"_id": existing_position["_id"]},
            {"$set": {"quantity": new_qty, "cost_price": round(new_cost, 4), "updated_at": now}}
        )

        await self.record_position_change(
            user_id=user_id, change_type=PositionChangeType.ADJUST,
            code=data.code, name=existing_position.get("name", data.code),
            market=data.market, currency=currency,
            position_id=str(existing_position["_id"]),
            quantity_before=old_qty, cost_price_before=old_cost,
            quantity_after=new_qty, cost_price_after=new_cost,
            description=f"合股: {data.ratio}，数量 {old_qty} → {new_qty}",
            trade_time=data.operation_date  # 使用操作日期作为交易时间
        )

        logger.info(f"✅ 合股成功: {data.code}, {old_qty} → {new_qty}股")
        return {"message": "合股成功", "new_quantity": new_qty, "new_cost_price": round(new_cost, 4)}

    async def _handle_adjust_operation(
        self, user_id: str, data: PositionOperationRequest,
        existing_position: Dict, currency: str, now
    ) -> Dict[str, Any]:
        """处理调整成本价操作"""
        if not data.new_cost_price or data.new_cost_price <= 0:
            raise ValueError("调整成本价需要指定新成本价")

        old_cost = existing_position["cost_price"]

        await self.db[self.positions_collection].update_one(
            {"_id": existing_position["_id"]},
            {"$set": {"cost_price": data.new_cost_price, "updated_at": now}}
        )

        await self.record_position_change(
            user_id=user_id, change_type=PositionChangeType.ADJUST,
            code=data.code, name=existing_position.get("name", data.code),
            market=data.market, currency=currency,
            position_id=str(existing_position["_id"]),
            quantity_before=existing_position["quantity"],
            cost_price_before=old_cost,
            quantity_after=existing_position["quantity"],
            cost_price_after=data.new_cost_price,
            description=f"调整成本价: {old_cost:.2f} → {data.new_cost_price:.2f}",
            trade_time=data.operation_date  # 使用操作日期作为交易时间
        )

        logger.info(f"✅ 调整成本价成功: {data.code}, {old_cost:.2f} → {data.new_cost_price:.2f}")
        return {"message": "调整成本价成功", "new_cost_price": data.new_cost_price}

    async def update_position(
        self,
        user_id: str,
        position_id: str,
        data: PositionUpdate
    ) -> Optional[PositionResponse]:
        """更新持仓"""
        try:
            obj_id = ObjectId(position_id)
        except Exception:
            logger.error(f"无效的持仓ID: {position_id}")
            return None

        # 获取原持仓信息
        old_position = await self.db[self.positions_collection].find_one(
            {"_id": obj_id, "user_id": user_id}
        )
        if not old_position:
            return None

        # 计算资金变化
        old_cost = old_position["quantity"] * old_position["cost_price"]
        new_quantity = data.quantity if data.quantity is not None else old_position["quantity"]
        new_cost_price = data.cost_price if data.cost_price is not None else old_position["cost_price"]
        new_cost = new_quantity * new_cost_price
        cost_diff = new_cost - old_cost  # 正数表示需要追加资金，负数表示释放资金

        # 更新资金账户
        if cost_diff != 0:
            currency = old_position["currency"]
            account = await self.get_or_create_account(user_id)
            current_cash = account.get("cash", {}).get(currency, 0.0)

            if cost_diff > 0 and current_cash < cost_diff:
                raise ValueError(f"可用资金不足。当前可用: {current_cash:.2f} {currency}，需要追加: {cost_diff:.2f} {currency}")

            new_cash = current_cash - cost_diff
            await self.db[self.accounts_collection].update_one(
                {"user_id": user_id},
                {"$set": {f"cash.{currency}": new_cash, "updated_at": now_tz()}}
            )

        # 构建更新数据
        update_data = {"updated_at": now_tz()}
        if data.name is not None:
            update_data["name"] = data.name
        if data.quantity is not None:
            update_data["quantity"] = data.quantity
        if data.cost_price is not None:
            update_data["cost_price"] = data.cost_price
        if data.buy_date is not None:
            update_data["buy_date"] = data.buy_date
        if data.notes is not None:
            update_data["notes"] = data.notes

        result = await self.db[self.positions_collection].find_one_and_update(
            {"_id": obj_id, "user_id": user_id},
            {"$set": update_data},
            return_document=True
        )

        if result:
            # 记录持仓变动
            currency = old_position["currency"]
            old_qty = old_position["quantity"]
            old_price = old_position["cost_price"]

            # 判断变动类型
            if new_quantity > old_qty:
                change_type = PositionChangeType.ADD
                desc = f"加仓 {new_quantity - old_qty} 股"
            elif new_quantity < old_qty:
                change_type = PositionChangeType.REDUCE
                desc = f"减仓 {old_qty - new_quantity} 股"
            else:
                change_type = PositionChangeType.ADJUST
                desc = "调整持仓信息"

            await self.record_position_change(
                user_id=user_id,
                change_type=change_type,
                code=old_position["code"],
                name=result.get("name", old_position["code"]),
                market=old_position["market"],
                currency=currency,
                position_id=position_id,
                quantity_before=old_qty,
                cost_price_before=old_price,
                quantity_after=new_quantity,
                cost_price_after=new_cost_price,
                description=desc
            )

            logger.info(f"✅ 更新持仓成功: {position_id}，资金变化: {-cost_diff:.2f} {currency}")
            return await self._enrich_position(result, "real")
        return None

    async def delete_position(self, user_id: str, position_id: str) -> bool:
        """删除持仓"""
        try:
            obj_id = ObjectId(position_id)
        except Exception:
            logger.error(f"无效的持仓ID: {position_id}")
            return False

        # 获取持仓信息以释放资金
        position = await self.db[self.positions_collection].find_one(
            {"_id": obj_id, "user_id": user_id}
        )
        if not position:
            return False

        # 释放资金（将持仓成本返还到可用资金）
        position_cost = position["quantity"] * position["cost_price"]
        currency = position["currency"]

        account = await self.get_or_create_account(user_id)
        current_cash = account.get("cash", {}).get(currency, 0.0)
        new_cash = current_cash + position_cost

        await self.db[self.accounts_collection].update_one(
            {"user_id": user_id},
            {"$set": {f"cash.{currency}": new_cash, "updated_at": now_tz()}}
        )

        # 记录持仓变动（在删除前记录）
        await self.record_position_change(
            user_id=user_id,
            change_type=PositionChangeType.SELL,
            code=position["code"],
            name=position.get("name", position["code"]),
            market=position["market"],
            currency=currency,
            position_id=position_id,
            quantity_before=position["quantity"],
            cost_price_before=position["cost_price"],
            quantity_after=0,
            cost_price_after=0.0,
            description="清仓卖出"
        )

        # 删除持仓
        result = await self.db[self.positions_collection].delete_one(
            {"_id": obj_id, "user_id": user_id}
        )

        if result.deleted_count > 0:
            logger.info(f"✅ 删除持仓成功: {position_id}，释放资金: {position_cost:.2f} {currency}")
            return True
        return False

    async def import_positions(
        self,
        user_id: str,
        positions: List[PositionCreate]
    ) -> Dict[str, Any]:
        """批量导入持仓"""
        success_count = 0
        failed_count = 0
        errors = []

        for pos in positions:
            try:
                await self.add_position(user_id, pos)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({"code": pos.code, "error": str(e)})

        logger.info(f"✅ 批量导入完成: 成功 {success_count}, 失败 {failed_count}")
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }

    # ==================== 持仓统计 ====================

    async def get_portfolio_statistics(self, user_id: str) -> PortfolioStatsResponse:
        """获取持仓统计"""
        positions = await self.get_positions(user_id, source="all", include_market_data=True)

        total_value = 0.0
        total_cost = 0.0
        industry_map: Dict[str, Dict] = {}
        market_map: Dict[str, float] = {}

        for pos in positions:
            cost = pos.cost_price * pos.quantity
            total_cost += cost

            if pos.market_value:
                total_value += pos.market_value
            else:
                total_value += cost  # 无法获取市值时使用成本

            # 🔥 修复：如果行业为空，尝试实时获取并更新到数据库
            industry = pos.industry
            logger.info(f"📊 [统计] 持仓 {pos.code} ({pos.name}) 当前行业: {industry}")
            
            if not industry or industry == "未知":
                logger.info(f"🔄 [统计] 持仓 {pos.code} 行业为空或'未知'，尝试实时获取...")
                # 尝试从数据库获取行业信息
                industry = await self._get_stock_industry(pos.code, pos.market)
                logger.info(f"📊 [统计] 持仓 {pos.code} 获取到的行业: {industry}")
                
                # 如果获取到了行业信息，更新到数据库
                if industry:
                    try:
                        update_result = await self.db[self.positions_collection].update_one(
                            {"_id": ObjectId(pos.id)},
                            {"$set": {"industry": industry, "updated_at": now_tz()}}
                        )
                        if update_result.modified_count > 0:
                            logger.info(f"✅ [统计] 已更新持仓 {pos.code} 的行业信息: {industry}")
                        else:
                            logger.warning(f"⚠️ [统计] 更新持仓 {pos.code} 行业信息失败: 未找到记录或未修改")
                    except Exception as e:
                        logger.error(f"❌ [统计] 更新持仓 {pos.code} 行业信息失败: {e}", exc_info=True)
                else:
                    # 如果无法获取，使用"未知"
                    logger.warning(f"⚠️ [统计] 持仓 {pos.code} 无法获取行业信息，使用'未知'")
                    industry = "未知"
            
            # 行业统计
            if industry not in industry_map:
                industry_map[industry] = {"value": 0.0, "count": 0}
            industry_map[industry]["value"] += pos.market_value or cost
            industry_map[industry]["count"] += 1

            # 市场统计
            market = pos.market
            if market not in market_map:
                market_map[market] = 0.0
            market_map[market] += pos.market_value or cost

        # 计算盈亏
        unrealized_pnl = total_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # 转换行业分布
        industry_dist = []
        for industry, data in industry_map.items():
            pct = (data["value"] / total_value * 100) if total_value > 0 else 0.0
            industry_dist.append(IndustryDistribution(
                industry=industry,
                value=round(data["value"], 2),
                percentage=round(pct, 2),
                count=data["count"]
            ))
        industry_dist.sort(key=lambda x: x.value, reverse=True)

        return PortfolioStatsResponse(
            total_positions=len(positions),
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            industry_distribution=industry_dist,
            market_distribution={k: round(v, 2) for k, v in market_map.items()}
        )

    # ==================== 持仓分析 ====================

    async def analyze_portfolio(
        self,
        user_id: str,
        include_paper: bool = True,
        research_depth: str = "标准"
    ) -> PortfolioAnalysisReport:
        """
        执行持仓分析

        Args:
            user_id: 用户ID
            include_paper: 是否包含模拟交易持仓
            research_depth: 分析深度
        """
        analysis_id = str(uuid.uuid4())
        analysis_date = datetime.now().strftime("%Y-%m-%d")

        # 创建分析报告
        report = PortfolioAnalysisReport(
            analysis_id=analysis_id,
            user_id=user_id,
            analysis_date=analysis_date,
            status=PortfolioAnalysisStatus.PROCESSING
        )

        try:
            # 1. 获取持仓数据
            source = "all" if include_paper else "real"
            positions = await self.get_positions(user_id, source=source)

            if not positions:
                report.status = PortfolioAnalysisStatus.FAILED
                report.error_message = "没有持仓数据"
                await self._save_analysis_report(report)
                return report

            # 2. 获取资金账户信息
            account_summary = await self.get_account_summary(user_id)

            # 3. 构建持仓快照（包含资金账户信息）
            portfolio_snapshot = await self._build_portfolio_snapshot(positions, account_summary)
            report.portfolio_snapshot = portfolio_snapshot

            # 4. 计算行业分布
            report.industry_distribution = await self._calculate_industry_distribution(positions)

            # 5. 计算集中度
            report.concentration_analysis = self._calculate_concentration(positions)

            # 6. 调用AI分析（传入资金账户信息）
            start_time = datetime.now()
            ai_result = await self._call_ai_analysis(portfolio_snapshot, report.industry_distribution)
            execution_time = (datetime.now() - start_time).total_seconds()

            report.ai_analysis = ai_result
            report.health_score = self._calculate_health_score(report)
            report.risk_level = self._calculate_risk_level(report)
            report.execution_time = execution_time
            report.status = PortfolioAnalysisStatus.COMPLETED

            logger.info(f"✅ 持仓分析完成: {analysis_id}, 健康度: {report.health_score}")

        except Exception as e:
            logger.error(f"❌ 持仓分析失败: {e}")
            report.status = PortfolioAnalysisStatus.FAILED
            report.error_message = str(e)

        # 保存报告
        await self._save_analysis_report(report)
        return report

    async def get_analysis_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取分析历史"""
        skip = (page - 1) * page_size

        cursor = self.db[self.analysis_collection].find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.analysis_collection].count_documents({"user_id": user_id})

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_analysis_detail(self, analysis_id: str) -> Optional[Dict]:
        """获取分析报告详情"""
        return await self.db[self.analysis_collection].find_one({"analysis_id": analysis_id})

    # ==================== 辅助方法 ====================

    async def _build_portfolio_snapshot(
        self,
        positions: List[PositionResponse],
        account_summary: AccountSummary = None
    ) -> PortfolioSnapshot:
        """构建持仓快照（包含资金账户信息）"""
        total_value = 0.0
        total_cost = 0.0
        snapshots = []

        # 获取总资产用于计算占比（默认使用CNY）
        total_assets = 0.0
        if account_summary:
            total_assets = account_summary.total_assets.get("CNY", 0.0)

        for pos in positions:
            cost = pos.cost_price * pos.quantity
            value = pos.market_value or cost
            total_cost += cost
            total_value += value

            # 计算持仓天数
            holding_days = None
            if pos.buy_date:
                holding_days = (datetime.now() - pos.buy_date).days

            # 计算资金占用比例（相对于总资产）
            cost_pct = None
            position_pct = None
            if total_assets > 0:
                cost_pct = round((cost / total_assets) * 100, 2)
                position_pct = round((value / total_assets) * 100, 2)

            snapshots.append(PositionSnapshot(
                code=pos.code,
                name=pos.name,
                market=pos.market,
                quantity=pos.quantity,
                cost_price=pos.cost_price,
                current_price=pos.current_price,
                market_value=pos.market_value,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_pct=pos.unrealized_pnl_pct,
                industry=pos.industry,
                holding_days=holding_days,
                cost_value=round(cost, 2),
                cost_pct=cost_pct,
                position_pct=position_pct
            ))

        unrealized_pnl = total_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # 构建资金账户快照
        account_snapshot = None
        if account_summary:
            cash_cny = account_summary.cash.get("CNY", 0.0)
            positions_value_cny = account_summary.positions_value.get("CNY", 0.0)
            total_assets_cny = account_summary.total_assets.get("CNY", 0.0)
            initial_capital_cny = account_summary.initial_capital.get("CNY", 0.0)
            net_capital_cny = account_summary.net_capital.get("CNY", 0.0)
            profit_cny = account_summary.profit.get("CNY", 0.0)
            profit_pct_cny = account_summary.profit_pct.get("CNY", 0.0)

            position_ratio = (positions_value_cny / total_assets_cny * 100) if total_assets_cny > 0 else 0.0
            cash_ratio = (cash_cny / total_assets_cny * 100) if total_assets_cny > 0 else 0.0

            account_snapshot = AccountSnapshot(
                total_assets=round(total_assets_cny, 2),
                cash=round(cash_cny, 2),
                positions_value=round(positions_value_cny, 2),
                position_ratio=round(position_ratio, 2),
                cash_ratio=round(cash_ratio, 2),
                initial_capital=round(initial_capital_cny, 2),
                net_capital=round(net_capital_cny, 2),
                total_profit=round(profit_cny, 2),
                total_profit_pct=round(profit_pct_cny, 2),
                currency="CNY"
            )

        return PortfolioSnapshot(
            total_positions=len(positions),
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            positions=snapshots,
            account=account_snapshot
        )

    async def _calculate_industry_distribution(
        self,
        positions: List[PositionResponse]
    ) -> List[IndustryDistribution]:
        """计算行业分布"""
        industry_map: Dict[str, Dict] = {}
        total_value = 0.0

        for pos in positions:
            value = pos.market_value or (pos.cost_price * pos.quantity)
            total_value += value

            industry = pos.industry or "未知"
            if industry not in industry_map:
                industry_map[industry] = {"value": 0.0, "count": 0}
            industry_map[industry]["value"] += value
            industry_map[industry]["count"] += 1

        result = []
        for industry, data in industry_map.items():
            pct = (data["value"] / total_value * 100) if total_value > 0 else 0.0
            result.append(IndustryDistribution(
                industry=industry,
                value=round(data["value"], 2),
                percentage=round(pct, 2),
                count=data["count"]
            ))

        result.sort(key=lambda x: x.value, reverse=True)
        return result

    def _calculate_concentration(self, positions: List[PositionResponse]) -> ConcentrationAnalysis:
        """计算集中度分析"""
        if not positions:
            return ConcentrationAnalysis()

        # 计算每只股票的市值
        values = []
        industries = set()
        total_value = 0.0

        for pos in positions:
            value = pos.market_value or (pos.cost_price * pos.quantity)
            values.append(value)
            total_value += value
            if pos.industry:
                industries.add(pos.industry)

        if total_value == 0:
            return ConcentrationAnalysis(stock_count=len(positions))

        # 排序获取Top N
        values.sort(reverse=True)

        top1_pct = (values[0] / total_value * 100) if len(values) >= 1 else 0
        top3_pct = (sum(values[:3]) / total_value * 100) if len(values) >= 3 else (sum(values) / total_value * 100)
        top5_pct = (sum(values[:5]) / total_value * 100) if len(values) >= 5 else (sum(values) / total_value * 100)

        # 计算HHI指数
        hhi = sum((v / total_value * 100) ** 2 for v in values)

        return ConcentrationAnalysis(
            stock_count=len(positions),
            top1_pct=round(top1_pct, 2),
            top3_pct=round(top3_pct, 2),
            top5_pct=round(top5_pct, 2),
            hhi_index=round(hhi, 2),
            industry_count=len(industries)
        )

    async def _call_ai_analysis(
        self,
        snapshot: PortfolioSnapshot,
        industry_dist: List[IndustryDistribution]
    ) -> AIAnalysisResult:
        """调用AI进行持仓分析"""
        try:
            # 构建分析提示词
            prompt = self._build_analysis_prompt(snapshot, industry_dist)

            # 从系统配置获取深度分析模型（与个股分析保持一致）
            from app.services.model_capability_service import get_model_capability_service
            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from tradingagents.graph.trading_graph import create_llm_by_provider

            capability_service = get_model_capability_service()
            _, deep_model = capability_service._get_default_models()
            model_name = deep_model

            logger.info(f"🤖 [整体持仓AI分析] 从系统配置获取深度分析模型: {model_name}")

            provider_info = get_provider_and_url_by_model_sync(model_name)
            backend_url = provider_info.get("backend_url")
            api_key = provider_info.get("api_key")

            logger.info(f"🏭 [整体持仓AI分析] 模型供应商: {provider_info.get('provider', '未知')}")
            logger.info(f"🔗 [整体持仓AI分析] API地址: {backend_url or '未配置'}")
            logger.info(f"🔑 [整体持仓AI分析] API Key: {'已配置' if api_key else '未配置'}")

            if not backend_url:
                raise ValueError(f"模型 {model_name} 的API地址未配置，请在设置页面配置")

            # 使用统一的 LLM 适配器
            provider_name = provider_info.get("provider", "dashscope")
            logger.info(f"🔧 [持仓AI分析] 准备创建 LLM: provider={provider_name}, model={model_name}, temperature=0.3")
            if api_key:
                logger.info(f"🔑 [持仓AI分析] API Key 前3位: {api_key[:3] if len(api_key) >= 3 else 'N/A'}")
            llm = create_llm_by_provider(
                provider=provider_name,
                model=model_name,
                backend_url=backend_url,
                temperature=0.3,
                max_tokens=4000,
                timeout=120,
                api_key=api_key
            )

            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # 解析响应
            return self._parse_ai_response(content)

        except Exception as e:
            logger.error(f"AI分析失败: {e}", exc_info=True)
            return AIAnalysisResult(
                summary=f"AI分析暂时不可用: {str(e)}",
                suggestions=["请稍后重试分析"]
            )

    def _build_analysis_prompt(
        self,
        snapshot: PortfolioSnapshot,
        industry_dist: List[IndustryDistribution]
    ) -> str:
        """构建分析提示词（包含资金账户和个股收益信息）"""

        # 资金账户信息
        account_section = ""
        if snapshot.account:
            acc = snapshot.account
            account_section = f"""## 💰 资金账户概况
| 项目 | 金额 | 说明 |
|------|------|------|
| 总资产 | ¥{acc.total_assets:,.2f} | 现金+持仓市值 |
| 可用现金 | ¥{acc.cash:,.2f} | 占比 {acc.cash_ratio:.1f}% |
| 持仓市值 | ¥{acc.positions_value:,.2f} | 占比 {acc.position_ratio:.1f}% |
| 净投入资金 | ¥{acc.net_capital:,.2f} | 初始资金+入金-出金 |
| 总盈亏 | ¥{acc.total_profit:,.2f} | 收益率 {acc.total_profit_pct:.2f}% |

### 仓位水平评估
- 当前仓位: **{acc.position_ratio:.1f}%**
- {"⚠️ 重仓状态（>80%），风险敞口较大" if acc.position_ratio > 80 else "⚠️ 偏重仓位（60-80%），建议保留部分现金" if acc.position_ratio > 60 else "✅ 仓位适中（40-60%），攻守兼备" if acc.position_ratio > 40 else "💡 轻仓状态（<40%），可择机加仓"}

"""

        # 持仓明细表（增强版：包含资金占用和收益详情）
        position_table = "| 股票代码 | 股票名称 | 行业 | 持仓天数 | 成本金额 | 市值 | 盈亏金额 | 盈亏% | 资金占比 |\n"
        position_table += "|---------|---------|-----|--------|---------|-----|---------|------|--------|\n"

        # 按盈亏金额排序，便于分析
        sorted_positions = sorted(
            snapshot.positions,
            key=lambda x: x.unrealized_pnl or 0,
            reverse=True
        )

        for pos in sorted_positions:
            pnl_emoji = "🟢" if (pos.unrealized_pnl or 0) >= 0 else "🔴"
            holding_days_str = f"{pos.holding_days}天" if pos.holding_days else "-"
            cost_value = pos.cost_value or (pos.cost_price * pos.quantity)
            position_table += f"| {pos.code} | {pos.name or '-'} | {pos.industry or '-'} | "
            position_table += f"{holding_days_str} | ¥{cost_value:,.0f} | ¥{pos.market_value or cost_value:,.0f} | "
            position_table += f"{pnl_emoji} ¥{pos.unrealized_pnl or 0:,.0f} | {pos.unrealized_pnl_pct or 0:.2f}% | "
            position_table += f"{pos.position_pct or '-'}% |\n"

        # 个股收益分析
        profitable_positions = [p for p in snapshot.positions if (p.unrealized_pnl or 0) > 0]
        losing_positions = [p for p in snapshot.positions if (p.unrealized_pnl or 0) < 0]
        total_profit = sum(p.unrealized_pnl or 0 for p in profitable_positions)
        total_loss = sum(p.unrealized_pnl or 0 for p in losing_positions)

        performance_section = f"""## 📊 个股收益分析
- 盈利股票: {len(profitable_positions)}只，合计盈利 ¥{total_profit:,.2f}
- 亏损股票: {len(losing_positions)}只，合计亏损 ¥{total_loss:,.2f}
- 盈亏比: {abs(total_profit/total_loss) if total_loss != 0 else '∞'}:1

### 盈利最多的股票
"""
        for pos in sorted_positions[:3]:
            if (pos.unrealized_pnl or 0) > 0:
                performance_section += f"- {pos.name}({pos.code}): +¥{pos.unrealized_pnl:,.0f} (+{pos.unrealized_pnl_pct:.2f}%)\n"

        performance_section += "\n### 亏损最多的股票\n"
        for pos in reversed(sorted_positions[-3:]):
            if (pos.unrealized_pnl or 0) < 0:
                performance_section += f"- {pos.name}({pos.code}): ¥{pos.unrealized_pnl:,.0f} ({pos.unrealized_pnl_pct:.2f}%)\n"

        # 资金占用分析
        capital_section = ""
        if snapshot.account and snapshot.account.total_assets > 0:
            high_concentration = [p for p in snapshot.positions if (p.position_pct or 0) > 20]
            if high_concentration:
                capital_section = "\n### ⚠️ 高集中度持仓（单只>20%）\n"
                for pos in high_concentration:
                    capital_section += f"- {pos.name}({pos.code}): 占比 {pos.position_pct:.1f}%，资金占用 ¥{pos.cost_value:,.0f}\n"

        # 行业分布
        industry_text = "\n".join([
            f"- {d.industry}: {d.percentage:.1f}% ({d.count}只)"
            for d in industry_dist[:5]
        ])

        prompt = f"""# 持仓组合分析任务

{account_section}## 📈 持仓概况
- 持仓总市值: ¥{snapshot.total_value:,.2f}
- 持仓成本: ¥{snapshot.total_cost:,.2f}
- 浮动盈亏: ¥{snapshot.unrealized_pnl:,.2f} ({snapshot.unrealized_pnl_pct:.2f}%)
- 持仓股票数: {snapshot.total_positions} 只

## 📋 持仓明细
{position_table}

{performance_section}
{capital_section}

## 🏭 行业分布
{industry_text}

## 分析要求
请基于以上数据，从以下维度进行专业分析（用中文回答）：

1. **持仓健康度评估** (给出0-100分，并说明主要扣分项)
2. **风险评估** (低/中/高，结合仓位水平和集中度分析)
3. **资金配置评估** (评估现金/持仓比例是否合理，资金利用效率)
4. **个股表现分析** (哪些股票表现好/差，是否需要止盈/止损)
5. **组合优势** (列出2-3点)
6. **组合劣势** (列出2-3点)
7. **调仓建议** (列出2-3条具体建议，包括：
   - 是否需要调整仓位水平
   - 是否需要止盈/止损某些股票
   - 是否需要调整行业配置)
8. **综合评价** (150字以内的总结)

请直接给出分析结果，不需要JSON格式。"""

        return prompt

    def _parse_ai_response(self, content: str) -> AIAnalysisResult:
        """解析AI响应"""
        # 简单解析，提取关键信息
        lines = content.split('\n')

        summary = ""
        strengths = []
        weaknesses = []
        suggestions = []

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if "综合评价" in line or "总结" in line:
                current_section = "summary"
            elif "优势" in line:
                current_section = "strengths"
            elif "劣势" in line or "不足" in line:
                current_section = "weaknesses"
            elif "建议" in line:
                current_section = "suggestions"
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                item = line.lstrip("-•* ").strip()
                if current_section == "strengths" and item:
                    strengths.append(item)
                elif current_section == "weaknesses" and item:
                    weaknesses.append(item)
                elif current_section == "suggestions" and item:
                    suggestions.append(item)
            elif current_section == "summary":
                summary += line + " "

        return AIAnalysisResult(
            summary=summary.strip() or content[:200],
            strengths=strengths[:3],
            weaknesses=weaknesses[:3],
            suggestions=suggestions[:5],
            detailed_report=content
        )

    def _calculate_health_score(self, report: PortfolioAnalysisReport) -> float:
        """计算健康度评分

        改进逻辑：
        1. 单股持仓时不因集中度扣分（单股起步是正常的）
        2. 主要根据盈亏情况评分
        3. 多股时才考虑集中度和行业分散度
        """
        score = 70.0  # 基础分提高到70

        concentration = report.concentration_analysis
        stock_count = concentration.stock_count or 1
        pnl_pct = report.portfolio_snapshot.total_unrealized_pnl_pct or 0

        # === 单股持仓的评分逻辑 ===
        if stock_count == 1:
            # 单股时不扣集中度分，主要看盈亏
            if pnl_pct > 20:
                score += 20
            elif pnl_pct > 10:
                score += 15
            elif pnl_pct > 5:
                score += 10
            elif pnl_pct > 0:
                score += 5
            elif pnl_pct > -5:
                score += 0  # 小幅亏损，不扣分
            elif pnl_pct > -10:
                score -= 5
            elif pnl_pct > -20:
                score -= 10
            else:
                score -= 20  # 亏损超20%

            return max(0, min(100, score))

        # === 多股持仓的评分逻辑 ===
        # 集中度评分 (最多扣15分)
        if concentration.top1_pct > 60:
            score -= 12
        elif concentration.top1_pct > 40:
            score -= 6

        if concentration.hhi_index > 4000:
            score -= 8
        elif concentration.hhi_index > 2500:
            score -= 4

        # 行业分散度加分 (最多加15分)
        if concentration.industry_count >= 5:
            score += 12
        elif concentration.industry_count >= 3:
            score += 8
        elif concentration.industry_count >= 2:
            score += 4

        # 盈利情况加分 (最多加/扣15分)
        if pnl_pct > 20:
            score += 12
        elif pnl_pct > 10:
            score += 8
        elif pnl_pct > 0:
            score += 4
        elif pnl_pct < -20:
            score -= 12
        elif pnl_pct < -10:
            score -= 6

        return max(0, min(100, score))

    def _calculate_risk_level(self, report: PortfolioAnalysisReport) -> str:
        """计算风险等级

        改进逻辑：
        1. 单股持仓时，不单纯按集中度判高风险
        2. 结合持仓市值、亏损比例等绝对风险指标
        3. 小资金轻仓位应判为低风险
        """
        concentration = report.concentration_analysis
        snapshot = report.portfolio_snapshot

        # 获取基本指标
        stock_count = concentration.stock_count or 1
        total_value = snapshot.total_market_value or 0
        total_pnl_pct = snapshot.total_unrealized_pnl_pct or 0

        # === 单股持仓的特殊处理 ===
        if stock_count == 1:
            # 单股持仓时，主要看亏损幅度和绝对金额
            # 小资金单股起步是正常的投资行为，不应判高风险

            # 亏损超过20%为高风险
            if total_pnl_pct < -20:
                return "高"
            # 亏损超过10%为中风险
            elif total_pnl_pct < -10:
                return "中"
            # 盈利或小幅亏损为低风险
            else:
                return "低"

        # === 多股持仓的集中度风险评估 ===
        # 高风险条件：集中度过高且有较大亏损
        if concentration.top1_pct > 50 and total_pnl_pct < -10:
            return "高"

        if concentration.hhi_index > 3000 and total_pnl_pct < -5:
            return "高"

        # 低风险条件：分散度好
        if concentration.top1_pct < 30 and concentration.industry_count >= 3:
            return "低"

        if concentration.top1_pct < 20 and concentration.industry_count >= 5:
            return "低"

        return "中"

    async def _save_analysis_report(self, report: PortfolioAnalysisReport):
        """保存分析报告"""
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.analysis_collection].insert_one(report_dict)
        logger.info(f"✅ 保存分析报告: {report.analysis_id}")

    # ==================== 数据获取工具 ====================

    async def _get_stock_price(self, code: str, market: str) -> Optional[float]:
        """获取股票最新价格"""
        if market == "CN":
            # A股从数据库获取
            q = await self.db["market_quotes"].find_one(
                {"$or": [{"code": code}, {"symbol": code}]},
                {"_id": 0, "close": 1}
            )
            if q and q.get("close"):
                try:
                    return float(q["close"])
                except (ValueError, TypeError):
                    pass

            # 回退到basic_info
            basic = await self.db["stock_basic_info"].find_one(
                {"$or": [{"code": code}, {"symbol": code}]},
                {"_id": 0, "current_price": 1}
            )
            if basic and basic.get("current_price"):
                try:
                    return float(basic["current_price"])
                except (ValueError, TypeError):
                    pass
        else:
            # 港股/美股
            try:
                from app.services.foreign_stock_service import ForeignStockService
                service = ForeignStockService(db=self.db)
                quote = await service.get_quote(market, code)
                if quote:
                    for field in ['regularMarketPrice', 'price', 'last']:
                        if quote.get(field):
                            return float(quote[field])
            except Exception as e:
                logger.warning(f"获取{market}股票价格失败: {code}, {e}")

        return None

    async def _get_stock_name(self, code: str, market: str) -> Optional[str]:
        """获取股票名称"""
        if market == "CN":
            basic = await self.db["stock_basic_info"].find_one(
                {"$or": [{"code": code}, {"symbol": code}]},
                {"_id": 0, "name": 1}
            )
            if basic:
                return basic.get("name")
        return None

    async def _get_stock_industry(self, code: str, market: str) -> Optional[str]:
        """获取股票所属行业
        
        按照数据库配置的数据源优先级顺序查询
        """
        try:
            if market == "CN":
                logger.info(f"🔍 [获取行业] 查询股票代码: {code}, 市场: {market}")
                
                # 🔥 获取启用的数据源列表（按优先级从高到低排序）
                from app.core.data_source_priority import get_enabled_data_sources_async
                enabled_sources = await get_enabled_data_sources_async(market_category="a_shares")
                logger.info(f"📊 [获取行业] 数据源优先级: {enabled_sources}")
                
                # 尝试多种查询方式
                query_conditions = [
                    {"code": code},
                    {"symbol": code},
                    {"code": code.strip().zfill(6)},  # 补齐前导零
                    {"symbol": code.strip().zfill(6)}
                ]
                
                # 🔥 按数据源优先级顺序查询
                for source in enabled_sources:
                    logger.info(f"🔍 [获取行业] 尝试数据源: {source}")
                    
                    for condition in query_conditions:
                        # 🔥 添加数据源筛选条件
                        condition_with_source = {**condition, "source": source}
                        basic = await self.db["stock_basic_info"].find_one(
                            condition_with_source,
                            {"_id": 0, "industry": 1, "code": 1, "symbol": 1, "name": 1, "source": 1}
                        )
                        
                        if basic:
                            industry = basic.get("industry")
                            code_found = basic.get("code") or basic.get("symbol")
                            name_found = basic.get("name")
                            source_found = basic.get("source")
                            logger.info(f"✅ [获取行业] 使用数据源 {source_found} 和查询条件 {condition} 找到记录")
                            logger.info(f"✅ [获取行业] 股票 {code} 查询结果 - 代码: {code_found}, 名称: {name_found}, 行业: {industry}, 数据源: {source_found}")
                            
                            if industry:
                                logger.info(f"✅ [获取行业] 成功获取行业信息: {industry} (数据源: {source_found})")
                                return industry
                            else:
                                logger.warning(f"⚠️ [获取行业] 股票 {code} 在数据源 {source_found} 中找到记录，但 industry 字段为空，继续尝试下一个数据源")
                                break  # 跳出查询条件循环，尝试下一个数据源
                
                # 🔥 如果所有数据源都没有找到行业信息，记录警告
                logger.warning(f"⚠️ [获取行业] 股票 {code} 在所有数据源中均未找到行业信息")
                # 打印一些调试信息
                count = await self.db["stock_basic_info"].count_documents({})
                logger.info(f"📊 [获取行业] stock_basic_info 集合总记录数: {count}")
                # 查找类似的代码（不限制数据源）
                similar = await self.db["stock_basic_info"].find_one(
                    {"code": {"$regex": code[-4:]}},  # 查找后4位相同的
                    {"_id": 0, "code": 1, "symbol": 1, "name": 1, "source": 1}
                )
                if similar:
                    logger.info(f"🔍 [获取行业] 找到类似的代码: {similar}")
            else:
                logger.info(f"🔍 [获取行业] 市场 {market} 暂不支持行业查询")
        except Exception as e:
            logger.error(f"❌ [获取行业] 获取股票 {code} 行业信息失败: {e}", exc_info=True)
        return None

    def _get_currency_by_market(self, market: str) -> str:
        """根据市场获取货币"""
        currency_map = {
            "CN": "CNY",
            "HK": "HKD",
            "US": "USD"
        }
        return currency_map.get(market, "CNY")

    # ==================== 单股持仓分析 ====================

    async def get_position_by_id(self, user_id: str, position_id: str) -> Optional[PositionResponse]:
        """根据ID获取持仓"""
        try:
            obj_id = ObjectId(position_id)
        except Exception:
            return None

        position = await self.db[self.positions_collection].find_one(
            {"_id": obj_id, "user_id": user_id}
        )
        if position:
            return await self._enrich_position(position, "real")
        return None

    async def analyze_position(
        self,
        user_id: str,
        position_id: str,
        params: PositionAnalysisRequest
    ) -> PositionAnalysisReport:
        """单股持仓分析

        流程：
        1. 检查是否有缓存的单股分析报告（只读取缓存，不创建新任务）
        2. 如果有缓存，使用缓存的报告；如果没有缓存，使用空报告
        3. 将分析报告（或空报告）+ 持仓信息发给持仓分析专用LLM
        4. 生成个性化的持仓操作建议
        """
        analysis_id = str(uuid.uuid4())

        # 获取持仓数据
        position = await self.get_position_by_id(user_id, position_id)
        if not position:
            report = PositionAnalysisReport(
                analysis_id=analysis_id,
                user_id=user_id,
                position_id=position_id,
                status=PortfolioAnalysisStatus.FAILED,
                error_message="持仓不存在"
            )
            return report

        # 构建持仓快照
        holding_days = None
        if position.buy_date:
            holding_days = (datetime.now() - datetime.fromisoformat(position.buy_date.replace('Z', '+00:00').split('+')[0])).days

        # 计算仓位占比（如果提供了资金总量）
        position_pct = None
        if params.total_capital and params.total_capital > 0 and position.market_value:
            position_pct = round((position.market_value / params.total_capital) * 100, 2)

        snapshot = PositionSnapshot(
            code=position.code,
            name=position.name,
            market=position.market,
            quantity=position.quantity,
            cost_price=position.cost_price,
            current_price=position.current_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            industry=position.industry,
            holding_days=holding_days,
            total_capital=params.total_capital,
            position_pct=position_pct
        )

        report = PositionAnalysisReport(
            analysis_id=analysis_id,
            user_id=user_id,
            position_id=position_id,
            position_snapshot=snapshot,
            status=PortfolioAnalysisStatus.PROCESSING
        )

        try:
            start_time = datetime.now()

            # 将市场代码转换为中文名称（用于缓存查询）
            market_name = convert_market_code_to_name(position.market)

            # 检查是否有缓存的单股分析报告（只读取缓存，不创建新任务）
            logger.info(f"📊 [持仓分析] 检查单股分析报告缓存 - {position.code} (市场: {position.market} -> {market_name})")
            stock_analysis_report = await self._get_cached_stock_analysis_report(
                stock_code=position.code,
                market=market_name,
                cache_hours=24  # 使用24小时内的缓存
            )

            # 如果没有缓存报告，创建空结构，直接进行持仓分析
            if not stock_analysis_report:
                logger.info(f"ℹ️ [持仓分析] 未找到缓存报告，直接进行持仓分析 - {position.code}")
                stock_analysis_report = {
                    "task_id": None,
                    "reports": {},
                    "decision": {},
                    "summary": "",
                    "recommendation": "",
                    "source": "none"
                }
            else:
                logger.info(f"✅ [持仓分析] 找到缓存报告，将作为参考 - {position.code}, 来源: {stock_analysis_report.get('source', 'unknown')}")

            # 结合持仓信息进行持仓分析
            logger.info(f"📊 [持仓分析] 开始持仓专用分析 - {position.code}")

            # 根据配置选择分析引擎（USE_STOCK_ENGINE=true 时使用工作流引擎v2.0）
            if _use_stock_engine():
                logger.info(f"🚀 [持仓分析] 使用工作流引擎v2.0进行分析")
                ai_result = await self._call_position_ai_analysis_workflow(
                    snapshot=snapshot,
                    params=params,
                    stock_analysis_report=stock_analysis_report,
                    user_id=user_id
                )
            else:
                logger.info(f"🤖 [持仓分析] 使用传统LLM分析")
                ai_result = await self._call_position_ai_analysis_v2(
                    snapshot=snapshot,
                    params=params,
                    stock_analysis_report=stock_analysis_report,
                    user_id=user_id
                )

            execution_time = (datetime.now() - start_time).total_seconds()

            report.ai_analysis = ai_result
            report.execution_time = execution_time
            report.status = PortfolioAnalysisStatus.COMPLETED
            # 保存单股分析报告的引用
            report.stock_analysis_task_id = stock_analysis_report.get("task_id")
            logger.info(f"✅ 单股持仓分析完成: {position.code}, 建议: {ai_result.action}")

        except Exception as e:
            logger.error(f"❌ 单股持仓分析失败: {e}", exc_info=True)
            report.status = PortfolioAnalysisStatus.FAILED
            report.error_message = str(e)

        # 保存报告
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.position_analysis_collection].insert_one(report_dict)
        return report

    async def create_position_analysis_task(
        self,
        user_id: str,
        code: str,
        market: str,
        params: "PositionAnalysisByCodeRequest"
    ) -> Dict[str, Any]:
        """创建持仓分析任务（异步模式）

        立即返回任务信息，后台执行分析
        """
        import asyncio
        from app.models.portfolio import PositionAnalysisByCodeRequest

        analysis_id = str(uuid.uuid4())

        # 检查是否已有正在进行的分析
        existing = await self.db[self.position_analysis_collection].find_one({
            "user_id": user_id,
            "position_id": f"{code}_{market}",
            "status": {"$in": ["pending", "processing"]}
        })

        if existing:
            return {
                "analysis_id": existing.get("analysis_id"),
                "code": code,
                "market": market,
                "status": existing.get("status"),
                "message": "已有分析任务正在进行中",
                "created_at": existing.get("created_at").isoformat() if existing.get("created_at") else None
            }

        # 检查是否有最近完成的分析（30分钟内）
        # 🔥 使用 now_tz() 确保时区一致
        recent_cutoff = now_tz() - timedelta(minutes=30)
        recent_completed = await self.db[self.position_analysis_collection].find_one({
            "user_id": user_id,
            "position_id": f"{code}_{market}",
            "status": "completed",
            "created_at": {"$gte": recent_cutoff}
        }, sort=[("created_at", -1)])

        if recent_completed:
            return {
                "analysis_id": recent_completed.get("analysis_id"),
                "code": code,
                "market": market,
                "status": "completed",
                "message": "已有最近的分析报告，可直接查看",
                "created_at": recent_completed.get("created_at").isoformat() if recent_completed.get("created_at") else None
            }

        # 创建新的分析任务记录
        report = PositionAnalysisReport(
            analysis_id=analysis_id,
            user_id=user_id,
            position_id=f"{code}_{market}",
            status=PortfolioAnalysisStatus.PENDING
        )

        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.position_analysis_collection].insert_one(report_dict)

        # 在后台启动分析任务
        asyncio.create_task(self._execute_position_analysis_background(
            user_id=user_id,
            analysis_id=analysis_id,
            code=code,
            market=market,
            params=params
        ))

        return {
            "analysis_id": analysis_id,
            "code": code,
            "market": market,
            "status": "pending",
            "message": "分析任务已创建，预计需要2-5分钟",
            "created_at": report.created_at.isoformat()
        }

    async def _execute_position_analysis_background(
        self,
        user_id: str,
        analysis_id: str,
        code: str,
        market: str,
        params: "PositionAnalysisByCodeRequest"
    ):
        """后台执行持仓分析"""
        try:
            # 更新状态为处理中
            await self.db[self.position_analysis_collection].update_one(
                {"analysis_id": analysis_id},
                {"$set": {"status": "processing"}}
            )

            # 执行实际分析
            report = await self.analyze_position_by_code(user_id, code, market, params)

            # 更新分析结果
            update_data = {
                "status": report.status.value,
                "position_snapshot": report.position_snapshot.model_dump() if report.position_snapshot else None,
                "ai_analysis": report.ai_analysis.model_dump() if report.ai_analysis else None,
                "execution_time": report.execution_time,
                "error_message": report.error_message,
                "stock_analysis_task_id": report.stock_analysis_task_id
            }

            await self.db[self.position_analysis_collection].update_one(
                {"analysis_id": analysis_id},
                {"$set": update_data}
            )

            logger.info(f"✅ 后台持仓分析完成: {code}, analysis_id={analysis_id}")

        except Exception as e:
            logger.error(f"❌ 后台持仓分析失败: {code}, error={e}", exc_info=True)
            await self.db[self.position_analysis_collection].update_one(
                {"analysis_id": analysis_id},
                {"$set": {"status": "failed", "error_message": str(e)}}
            )

    async def get_position_analysis_by_id(
        self,
        user_id: str,
        analysis_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据分析ID获取分析报告"""
        report = await self.db[self.position_analysis_collection].find_one({
            "user_id": user_id,
            "analysis_id": analysis_id
        })

        if not report:
            return None

        return self._format_position_analysis_report(report)

    async def get_latest_position_analysis(
        self,
        user_id: str,
        code: str,
        market: str,
        position_type: str = "real"
    ) -> Optional[Dict[str, Any]]:
        """获取某只股票的最新分析报告
        
        Args:
            user_id: 用户ID
            code: 股票代码
            market: 市场类型
            position_type: 持仓类型 (real/simulated)
        """
        # 🔥 根据 position_type 查询对应的分析报告
        query = {
            "user_id": user_id,
            "position_id": f"{code}_{market}",
            "position_type": position_type  # 添加 position_type 筛选条件
        }
        
        report = await self.db[self.position_analysis_collection].find_one(
            query,
            sort=[("created_at", -1)]
        )

        if not report:
            return None

        return self._format_position_analysis_report(report)

    def _format_position_analysis_report(self, report: Dict) -> Dict[str, Any]:
        """格式化分析报告为响应格式"""
        snapshot = report.get("position_snapshot") or {}
        ai_analysis = report.get("ai_analysis") or {}
        price_targets = ai_analysis.get("price_targets") or {}
        
        # 处理action_reason：如果是JSON格式，转换为Markdown
        action_reason_raw = ai_analysis.get("action_reason")
        action_reason_formatted = action_reason_raw
        
        if action_reason_raw:
            logger.info(f"📊 [格式化报告] 原始action_reason类型: {type(action_reason_raw)}, 长度: {len(str(action_reason_raw)) if action_reason_raw else 0}")
            
            import json
            advice_json = None
            
            # 如果是字符串，尝试解析JSON
            if isinstance(action_reason_raw, str):
                action_reason_str = action_reason_raw.strip()
                logger.info(f"📊 [格式化报告] action_reason前100字符: {action_reason_str[:100]}")
                
                # 检查是否包含JSON代码块或JSON格式
                if "```json" in action_reason_str or (action_reason_str.startswith("{") and ("analysis_summary" in action_reason_str or "neutral_operation" in action_reason_str)):
                    try:
                        # 提取JSON
                        if "```json" in action_reason_str:
                            json_start = action_reason_str.find("```json") + 7
                            json_end = action_reason_str.find("```", json_start)
                            if json_end > json_start:
                                json_str = action_reason_str[json_start:json_end].strip()
                                logger.info(f"📊 [格式化报告] 从代码块提取JSON，长度: {len(json_str)}")
                                advice_json = json.loads(json_str)
                        elif action_reason_str.strip().startswith("{"):
                            logger.info(f"📊 [格式化报告] 直接解析JSON格式")
                            advice_json = json.loads(action_reason_str)
                        
                        if advice_json:
                            logger.info(f"📊 [格式化报告] JSON解析成功，字段: {list(advice_json.keys())}")
                            action_reason_formatted = self._convert_action_advice_json_to_markdown(advice_json)
                            logger.info(f"📊 [格式化报告] JSON转换为Markdown成功，长度: {len(action_reason_formatted)}")
                        else:
                            logger.warning(f"⚠️ [格式化报告] JSON解析后为空，使用原始值")
                    except Exception as e:
                        logger.warning(f"⚠️ [格式化报告] JSON解析失败，使用原始值: {e}", exc_info=True)
            elif isinstance(action_reason_raw, dict):
                # 如果已经是字典格式，直接转换
                logger.info(f"📊 [格式化报告] action_reason是字典格式，字段: {list(action_reason_raw.keys())}")
                action_reason_formatted = self._convert_action_advice_json_to_markdown(action_reason_raw)
                logger.info(f"📊 [格式化报告] 字典转换为Markdown成功，长度: {len(action_reason_formatted)}")
        
        return {
            "analysis_id": report.get("analysis_id"),
            "position_id": report.get("position_id"),
            "code": snapshot.get("code") or report.get("position_id", "").split("_")[0],
            "name": snapshot.get("name"),
            "market": snapshot.get("market") or report.get("position_id", "").split("_")[-1],
            "status": report.get("status"),
            "action": ai_analysis.get("action"),
            "action_reason": action_reason_formatted,
            "confidence": ai_analysis.get("confidence"),
            "price_targets": price_targets,
            "risk_assessment": ai_analysis.get("risk_assessment"),
            "opportunity_assessment": ai_analysis.get("opportunity_assessment"),
            "detailed_analysis": ai_analysis.get("detailed_analysis"),
            "execution_time": report.get("execution_time"),
            "error_message": report.get("error_message"),
            "created_at": report.get("created_at").isoformat() if report.get("created_at") else None,
            "summary": {
                "quantity": snapshot.get("quantity"),
                "cost_price": snapshot.get("cost_price"),
                "current_price": snapshot.get("current_price"),
                "market_value": snapshot.get("market_value"),
                "unrealized_pnl": snapshot.get("unrealized_pnl"),
                "unrealized_pnl_pct": snapshot.get("unrealized_pnl_pct"),
                "holding_days": snapshot.get("holding_days"),
                "position_pct": snapshot.get("position_pct"),
            }
        }

    async def analyze_position_by_code(
        self,
        user_id: str,
        code: str,
        market: str,
        params: "PositionAnalysisByCodeRequest"
    ) -> PositionAnalysisReport:
        """按股票代码分析持仓 - 汇总同一股票的所有建仓记录

        这个方法会：
        1. 查询该股票的所有持仓记录
        2. 汇总计算总数量、平均成本价、总市值等
        3. 作为一个整体进行分析
        """
        from app.models.portfolio import PositionAnalysisByCodeRequest

        analysis_id = str(uuid.uuid4())

        # 🔥 根据 position_type 选择查询用户持仓还是模拟持仓
        position_type = params.position_type if hasattr(params, 'position_type') else "real"
        if position_type == "simulated":
            # 查询模拟持仓
            collection = self.paper_positions_collection
            logger.info(f"📊 [持仓分析] 查询模拟持仓: {code} ({market})")
        else:
            # 查询用户持仓
            collection = self.positions_collection
            logger.info(f"📊 [持仓分析] 查询用户持仓: {code} ({market})")

        # 查询该股票的所有持仓记录
        positions = await self.db[collection].find({
            "user_id": user_id,
            "code": code,
            "market": market
        }).to_list(None)

        if not positions:
            report = PositionAnalysisReport(
                analysis_id=analysis_id,
                user_id=user_id,
                position_id=f"{code}_{market}",  # 使用股票代码作为标识
                status=PortfolioAnalysisStatus.FAILED,
                error_message=f"未找到 {code} 的持仓记录"
            )
            return report

        # 汇总计算
        total_quantity = sum(p.get("quantity", 0) for p in positions)
        # 🔥 根据持仓类型选择成本价字段：模拟持仓使用 avg_cost，用户持仓使用 cost_price
        if position_type == "simulated":
            total_cost = sum(p.get("quantity", 0) * p.get("avg_cost", 0) for p in positions)
        else:
            total_cost = sum(p.get("quantity", 0) * p.get("cost_price", 0) for p in positions)
        avg_cost_price = total_cost / total_quantity if total_quantity > 0 else 0

        # 获取当前价格
        current_price = await self._get_stock_price(code, market)
        # 🔥 修复：确保 market_value、unrealized_pnl 和 unrealized_pnl_pct 不为 None（模拟持仓分析时可能为 None）
        if current_price and current_price > 0:
            market_value = current_price * total_quantity
            unrealized_pnl = market_value - total_cost
            unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0
        else:
            market_value = 0.0
            unrealized_pnl = 0.0
            unrealized_pnl_pct = 0.0

        # 获取股票名称和行业
        name = positions[0].get("name") or await self._get_stock_name(code, market)
        industry = positions[0].get("industry") or await self._get_stock_industry(code, market)

        # 计算持仓天数（使用最早的建仓日期）
        holding_days = None
        earliest_date = None
        for p in positions:
            buy_date = p.get("buy_date")
            if buy_date:
                if isinstance(buy_date, str):
                    buy_date = datetime.fromisoformat(buy_date.replace('Z', '+00:00').split('+')[0])
                if earliest_date is None or buy_date < earliest_date:
                    earliest_date = buy_date
        if earliest_date:
            holding_days = (datetime.now() - earliest_date).days

        # 计算仓位占比
        position_pct = None
        if params.total_capital and params.total_capital > 0 and market_value:
            position_pct = round((market_value / params.total_capital) * 100, 2)

        # 构建持仓快照（汇总后的）
        snapshot = PositionSnapshot(
            code=code,
            name=name,
            market=market,
            quantity=total_quantity,
            cost_price=round(avg_cost_price, 4),
            current_price=current_price if current_price else 0.0,
            market_value=round(market_value, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            industry=industry,
            holding_days=holding_days,
            total_capital=params.total_capital,
            position_pct=position_pct
        )

        # 创建分析参数（转换为 PositionAnalysisRequest）
        analysis_params = PositionAnalysisRequest(
            research_depth=params.research_depth,
            include_add_position=params.include_add_position,
            target_profit_pct=params.target_profit_pct,
            total_capital=params.total_capital,
            max_position_pct=params.max_position_pct,
            max_loss_pct=params.max_loss_pct
        )

        report = PositionAnalysisReport(
            analysis_id=analysis_id,
            user_id=user_id,
            position_id=f"{code}_{market}",  # 使用股票代码作为标识
            position_snapshot=snapshot,
            status=PortfolioAnalysisStatus.PROCESSING
        )

        try:
            start_time = datetime.now()

            # 将市场代码转换为中文名称（单股分析服务需要）
            market_name = convert_market_code_to_name(market)

            # 检查是否有缓存的单股分析报告（只读取缓存，不创建新任务）
            stock_analysis_report = None
            if params.use_stock_analysis:
                logger.info(f"📊 [汇总持仓分析] 检查单股分析报告缓存 - {code} (市场: {market} -> {market_name}, 共{len(positions)}条记录)")
                stock_analysis_report = await self._get_cached_stock_analysis_report(
                    stock_code=code,
                    market=market_name,
                    cache_hours=24  # 使用24小时内的缓存
                )

                # 如果没有缓存报告，记录日志
                if not stock_analysis_report:
                    logger.info(f"ℹ️ [汇总持仓分析] 未找到缓存报告，将直接进行持仓分析 - {code}")
                else:
                    logger.info(f"✅ [汇总持仓分析] 找到缓存报告，将作为参考 - {code}, 来源: {stock_analysis_report.get('source', 'unknown')}")
            else:
                logger.info(f"⏭️ [汇总持仓分析] 用户选择不使用单股分析报告 - {code}")

            # 如果没有单股分析报告，创建一个空的报告结构，避免后续代码报错
            if not stock_analysis_report:
                stock_analysis_report = {
                    "task_id": None,
                    "reports": {},
                    "decision": {},
                    "summary": "",
                    "recommendation": "",
                    "source": "none"
                }

            # 第二阶段：结合持仓信息进行持仓分析
            logger.info(f"📊 [汇总持仓分析] 第二阶段：持仓专用分析 - {code}")

            # 根据配置选择分析引擎（USE_STOCK_ENGINE=true 时使用工作流引擎v2.0）
            if _use_stock_engine():
                logger.info(f"🚀 [汇总持仓分析] 使用工作流引擎v2.0进行分析")
                ai_result = await self._call_position_ai_analysis_workflow(
                    snapshot=snapshot,
                    params=analysis_params,
                    stock_analysis_report=stock_analysis_report,
                    user_id=user_id
                )
            else:
                logger.info(f"🤖 [汇总持仓分析] 使用传统LLM分析")
                ai_result = await self._call_position_ai_analysis_v2(
                    snapshot=snapshot,
                    params=analysis_params,
                    stock_analysis_report=stock_analysis_report,
                    user_id=user_id
                )

            execution_time = (datetime.now() - start_time).total_seconds()

            report.ai_analysis = ai_result
            report.execution_time = execution_time
            report.status = PortfolioAnalysisStatus.COMPLETED
            report.stock_analysis_task_id = stock_analysis_report.get("task_id")
            logger.info(f"✅ 汇总持仓分析完成: {code}, 建议: {ai_result.action}, 共{len(positions)}条记录")

        except Exception as e:
            logger.error(f"❌ 汇总持仓分析失败: {e}", exc_info=True)
            report.status = PortfolioAnalysisStatus.FAILED
            report.error_message = str(e)

        # 保存报告
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        # 🔥 添加 position_type 字段到报告记录中，用于后续查询时区分模拟持仓和用户持仓
        report_dict["position_type"] = position_type
        await self.db[self.position_analysis_collection].insert_one(report_dict)
        return report

    async def analyze_position_by_code_v2(
        self,
        user_id: str,
        code: str,
        market: str,
        params: "PositionAnalysisByCodeRequest"
    ) -> PositionAnalysisReport:
        """按股票代码分析持仓 v2.0 - 使用统一任务引擎

        优势:
        - 支持多引擎切换（workflow/legacy/llm）
        - 统一的任务管理和进度跟踪
        - 自动选择最佳引擎
        - 任务可查询、可取消

        Args:
            user_id: 用户ID
            code: 股票代码
            market: 市场类型（CN/HK/US）
            params: 分析参数

        Returns:
            持仓分析报告
        """
        from app.services.task_analysis_service import get_task_analysis_service
        from app.models.analysis import AnalysisTaskType
        from app.models.portfolio import PositionAnalysisByCodeRequest
        from app.models.user import PyObjectId

        logger.info(f"🚀 [持仓分析v2.0] 使用统一任务引擎分析: {code} (市场: {market})")

        # 查询该股票的所有持仓记录（用于构建快照）
        positions = await self.db[self.positions_collection].find({
            "user_id": user_id,
            "code": code,
            "market": market
        }).to_list(None)

        if not positions:
            # 如果没有持仓记录，返回失败报告
            analysis_id = str(uuid.uuid4())
            report = PositionAnalysisReport(
                analysis_id=analysis_id,
                user_id=user_id,
                position_id=f"{code}_{market}",
                status=PortfolioAnalysisStatus.FAILED,
                error_message=f"未找到 {code} 的持仓记录"
            )
            return report

        # 汇总计算持仓数据
        total_quantity = sum(p.get("quantity", 0) for p in positions)
        total_cost = sum(p.get("quantity", 0) * p.get("cost_price", 0) for p in positions)
        avg_cost_price = total_cost / total_quantity if total_quantity > 0 else 0

        # 获取当前价格
        current_price = await self._get_stock_price(code, market)
        market_value = current_price * total_quantity if current_price else None
        unrealized_pnl = (market_value - total_cost) if market_value else None
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if unrealized_pnl and total_cost > 0 else None

        # 获取股票名称和行业
        name = positions[0].get("name") or await self._get_stock_name(code, market)
        industry = positions[0].get("industry") or await self._get_stock_industry(code, market)

        # 计算持仓天数
        holding_days = None
        earliest_date = None
        for p in positions:
            buy_date = p.get("buy_date")
            if buy_date:
                if isinstance(buy_date, str):
                    buy_date = datetime.fromisoformat(buy_date.replace('Z', '+00:00').split('+')[0])
                if earliest_date is None or buy_date < earliest_date:
                    earliest_date = buy_date
        if earliest_date:
            holding_days = (datetime.now() - earliest_date).days

        # 计算仓位占比
        position_pct = None
        if params.total_capital and params.total_capital > 0 and market_value:
            position_pct = round((market_value / params.total_capital) * 100, 2)

        # 构建持仓快照
        snapshot = PositionSnapshot(
            code=code,
            name=name,
            market=market,
            quantity=total_quantity,
            cost_price=round(avg_cost_price, 4),
            current_price=current_price,
            market_value=round(market_value, 2) if market_value else None,
            unrealized_pnl=round(unrealized_pnl, 2) if unrealized_pnl else None,
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2) if unrealized_pnl_pct else None,
            industry=industry,
            holding_days=holding_days,
            total_capital=params.total_capital,
            position_pct=position_pct
        )

        # 准备任务参数
        task_params = {
            "code": code,
            "market": market,
            "snapshot": snapshot.model_dump(),
            "research_depth": params.research_depth,
            "include_add_position": params.include_add_position,
            "target_profit_pct": params.target_profit_pct,
            "total_capital": params.total_capital,
            "max_position_pct": params.max_position_pct,
            "max_loss_pct": params.max_loss_pct,
            "use_stock_analysis": params.use_stock_analysis
        }

        # 使用统一任务引擎
        task_service = get_task_analysis_service()

        try:
            # 创建并执行任务
            task = await task_service.create_and_execute_task(
                user_id=PyObjectId(user_id),
                task_type=AnalysisTaskType.POSITION_ANALYSIS,
                task_params=task_params,
                engine_type=getattr(params, "engine_type", "auto"),  # 支持引擎选择
                preference_type=getattr(params, "preference_type", "neutral")
            )

            # 将任务结果转换为 PositionAnalysisReport
            report = PositionAnalysisReport(
                analysis_id=task.task_id,
                user_id=user_id,
                position_id=f"{code}_{market}",
                position_snapshot=snapshot,
                status=PortfolioAnalysisStatus.COMPLETED if task.status == "completed" else PortfolioAnalysisStatus.FAILED,
                execution_time=task.execution_time,
                error_message=task.error_message
            )

            # 从任务结果中提取 AI 分析
            if task.result and "ai_analysis" in task.result:
                report.ai_analysis = AIAnalysisResult(**task.result["ai_analysis"])

            logger.info(f"✅ [持仓分析v2.0] 分析完成: {code}, 任务ID: {task.task_id}")

            # 保存报告
            report_dict = report.model_dump(by_alias=True, exclude={"id"})
            await self.db[self.position_analysis_collection].insert_one(report_dict)

            return report

        except Exception as e:
            logger.error(f"❌ [持仓分析v2.0] 分析失败: {code} - {e}", exc_info=True)

            # 返回失败报告
            report = PositionAnalysisReport(
                analysis_id=str(uuid.uuid4()),
                user_id=user_id,
                position_id=f"{code}_{market}",
                position_snapshot=snapshot,
                status=PortfolioAnalysisStatus.FAILED,
                error_message=str(e)
            )

            # 保存报告
            report_dict = report.model_dump(by_alias=True, exclude={"id"})
            await self.db[self.position_analysis_collection].insert_one(report_dict)

            return report

    async def check_stock_analysis_cache(
        self,
        stock_code: str,
        market: str = "A股"
    ) -> Dict[str, Any]:
        """检查单股分析报告缓存状态
        
        Args:
            stock_code: 股票代码
            market: 市场类型（A股/港股/美股）
            
        Returns:
            包含缓存状态的字典：
            {
                "has_cache": bool,  # 是否有缓存
                "cache_age_minutes": int,  # 缓存年龄（分钟）
                "cache_age_hours": float,  # 缓存年龄（小时）
                "source": str  # 缓存来源（"engine" 或 "legacy"）
            }
        """
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        
        # 检查24小时内的报告（前端提示用户的标准）
        cache_hours = 24
        # 🔥 使用 now_tz() 确保时区一致
        recent_cutoff = now_tz() - timedelta(hours=cache_hours)
        
        # 检查旧版引擎的缓存（analysis_reports 集合）
        # 这是最常用的缓存位置，无论是否启用新引擎都会使用
        existing_report = await db.analysis_reports.find_one({
            "stock_symbol": stock_code,
            "created_at": {"$gte": recent_cutoff},
            "status": "completed"
        }, sort=[("created_at", -1)])
        
        if existing_report:
            created_at = existing_report.get("created_at", datetime.now())
            if isinstance(created_at, str):
                from dateutil.parser import parse
                created_at = parse(created_at)
            elif created_at is None:
                created_at = now_tz()
            
            # 🔥 确保时区一致：MongoDB 存储的是 UTC 时间
            # 如果从 MongoDB 读取的是 naive datetime，应该假定为 UTC
            # 注意：tz 和 now_tz 已在文件顶部导入
            current_time = now_tz()
            
            if created_at:
                # 如果 created_at 是 naive datetime，假定为 UTC（因为 MongoDB 存储的是 UTC）
                if isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=tz.utc)
                # 转换为配置时区以便计算时间差
                if created_at.tzinfo:
                    created_at = created_at.astimezone(current_time.tzinfo)
            else:
                created_at = current_time
            
            report_age = current_time - created_at
            age_minutes = int(report_age.total_seconds() / 60)
            age_hours = report_age.total_seconds() / 3600
            
            logger.info(f"✅ [检查缓存] 找到旧版引擎缓存: {stock_code}, 年龄: {age_minutes}分钟 (created_at: {created_at}, current_time: {current_time})")
            return {
                "has_cache": True,
                "cache_age_minutes": age_minutes,
                "cache_age_hours": round(age_hours, 2),
                "source": "legacy"
            }
        
        # 没有找到缓存
        logger.info(f"❌ [检查缓存] 未找到缓存: {stock_code}")
        return {
            "has_cache": False,
            "cache_age_minutes": None,
            "cache_age_hours": None,
            "source": None
        }

    async def _get_cached_stock_analysis_report(
        self,
        stock_code: str,
        market: str = "A股",
        cache_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """只从缓存中获取股票分析报告（不创建新任务）
        
        仅用于持仓分析场景，只读取已有缓存，不会创建新的单股分析任务
        
        Args:
            stock_code: 股票代码
            market: 市场类型（A股/港股/美股）
            cache_hours: 缓存有效期（小时）
            
        Returns:
            分析报告字典，如果没有缓存则返回 None
        """
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        # 🔥 使用 now_tz() 确保时区一致
        recent_cutoff = now_tz() - timedelta(hours=cache_hours)
        
        # 检查是否有已完成的分析报告（任意用户）
        existing_report = await db.analysis_reports.find_one({
            "stock_symbol": stock_code,
            "created_at": {"$gte": recent_cutoff},
            "status": "completed"
        }, sort=[("created_at", -1)])
        
        if existing_report:
            created_at = existing_report.get("created_at", datetime.now())
            if isinstance(created_at, str):
                from dateutil.parser import parse
                created_at = parse(created_at)
            
            # 🔥 确保时区一致：MongoDB 存储的是 UTC 时间
            # 如果从 MongoDB 读取的是 naive datetime，应该假定为 UTC
            # 注意：tz 和 now_tz 已在文件顶部导入
            current_time = now_tz()
            
            if created_at:
                # 如果 created_at 是 naive datetime，假定为 UTC（因为 MongoDB 存储的是 UTC）
                if isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=tz.utc)
                # 转换为配置时区以便计算时间差
                if created_at.tzinfo:
                    created_at = created_at.astimezone(current_time.tzinfo)
            else:
                created_at = current_time
            
            report_age = current_time - created_at
            age_minutes = int(report_age.total_seconds() / 60)
            age_hours = report_age.total_seconds() / 3600
            
            logger.info(f"📚 [持仓分析] 从缓存读取单股分析报告: {stock_code}, "
                       f"task_id={existing_report.get('task_id')}, "
                       f"报告时间: {age_minutes}分钟前 (created_at: {created_at}, current_time: {current_time})")
            return {
                "task_id": existing_report.get("task_id"),
                "reports": existing_report.get("reports", {}),
                "decision": existing_report.get("decision", {}),
                "summary": existing_report.get("summary", ""),
                "recommendation": existing_report.get("recommendation", ""),
                "source": "cached",
                "cache_age_minutes": age_minutes,
                "cache_age_hours": round(age_hours, 2)
            }
        
        logger.info(f"❌ [持仓分析] 未找到缓存的单股分析报告: {stock_code}")
        return None

    async def _get_stock_analysis_via_engine(
        self,
        stock_code: str,
        market: str = "A股"
    ) -> Optional[Dict[str, Any]]:
        """使用新版 StockAnalysisEngine 获取分析报告

        Returns:
            分析报告字典，失败返回 None
        """
        try:
            from tradingagents.core.engine.stock_analysis_engine import StockAnalysisEngine
            from core.workflow.builder import LegacyDependencyProvider

            # 转换市场类型
            market_type_map = {
                "A股": "cn",
                "港股": "hk",
                "美股": "us"
            }
            market_type = market_type_map.get(market, "cn")

            logger.info(f"🚀 [持仓分析] 使用 StockAnalysisEngine 分析: {stock_code} (市场: {market_type})")

            # 创建 LLM 依赖提供者（从数据库配置获取 LLM）
            dependency_provider = LegacyDependencyProvider.get_instance()
            llm = dependency_provider.get_llm("quick")

            engine = StockAnalysisEngine(
                llm=llm,
                use_stub=False
            )
            result = engine.analyze(
                ticker=stock_code,
                trade_date=datetime.now().strftime("%Y-%m-%d"),
                market_type=market_type
            )

            if result and result.success:
                logger.info(f"✅ [持仓分析] StockAnalysisEngine 分析完成: {stock_code}")

                # 转换为统一的返回格式
                context = result.context
                reports = {}

                # 从 context 提取各分析师报告
                if hasattr(context, 'reports') and context.reports:
                    reports = context.reports
                elif hasattr(context, 'get'):
                    reports = {
                        "market_report": context.get("market_report", ""),
                        "fundamentals_report": context.get("fundamentals_report", ""),
                        "news_report": context.get("news_report", ""),
                        "sentiment_report": context.get("sentiment_report", ""),
                        "sector_report": context.get("sector_report", "")
                    }

                return {
                    "task_id": "engine",
                    "source": "stock_analysis_engine",
                    "reports": reports,
                    "decision": result.final_decision if hasattr(result, 'final_decision') else {},
                    "summary": result.summary if hasattr(result, 'summary') else "",
                    "recommendation": result.recommendation if hasattr(result, 'recommendation') else ""
                }
            else:
                logger.warning(f"⚠️ [持仓分析] StockAnalysisEngine 返回失败结果: {stock_code}")
                return None

        except ImportError as e:
            logger.warning(f"⚠️ [持仓分析] StockAnalysisEngine 模块不可用: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ [持仓分析] StockAnalysisEngine 调用异常: {e}", exc_info=True)
            return None

    async def _get_stock_analysis_via_legacy(
        self,
        user_id: str,
        stock_code: str,
        market: str = "A股",
        skip_if_not_exists: bool = False
    ) -> Optional[Dict[str, Any]]:
        """使用旧版 simple_analysis_service 获取分析报告（降级方案）

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            market: 市场类型
            skip_if_not_exists: 如果没有缓存报告，是否跳过（不创建新任务）

        Returns:
            分析报告字典，如果 skip_if_not_exists=True 且没有缓存则返回 None
        """
        from app.services.simple_analysis_service import get_simple_analysis_service
        from app.models.analysis import SingleAnalysisRequest, AnalysisParameters
        from app.core.database import get_mongo_db
        import asyncio

        analysis_service = get_simple_analysis_service()

        db = get_mongo_db()

        # 3小时内的报告可以复用（股票基本面、技术面数据变化不大）
        cache_hours = 3
        # 🔥 使用 now_tz() 确保时区一致
        recent_cutoff = now_tz() - timedelta(hours=cache_hours)

        # 1. 首先检查是否有已完成的分析报告（3小时内，不限用户）
        # 单股分析的结果对所有用户都是一样的，可以共享
        # 注意：analysis_reports 集合中使用的是 stock_symbol 字段（不是 stock_code）
        existing_report = await db.analysis_reports.find_one({
            "stock_symbol": stock_code,  # 使用 stock_symbol 字段匹配
            "created_at": {"$gte": recent_cutoff},
            "status": "completed"
        }, sort=[("created_at", -1)])

        if existing_report:
            created_at = existing_report.get("created_at", datetime.now())
            if isinstance(created_at, str):
                from dateutil.parser import parse
                created_at = parse(created_at)
            
            # 🔥 确保时区一致：MongoDB 存储的是 UTC 时间
            # 如果从 MongoDB 读取的是 naive datetime，应该假定为 UTC
            # 注意：tz 和 now_tz 已在文件顶部导入
            current_time = now_tz()
            
            if created_at:
                # 如果 created_at 是 naive datetime，假定为 UTC（因为 MongoDB 存储的是 UTC）
                if isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=tz.utc)
                # 转换为配置时区以便计算时间差
                if created_at.tzinfo:
                    created_at = created_at.astimezone(current_time.tzinfo)
            else:
                created_at = current_time
            
            report_age = current_time - created_at
            age_minutes = int(report_age.total_seconds() / 60)
            logger.info(f"📚 [持仓分析] 复用已完成的分析报告: {stock_code}, "
                       f"task_id={existing_report.get('task_id')}, "
                       f"报告时间: {age_minutes}分钟前 (created_at: {created_at}, current_time: {current_time})")
            return {
                "task_id": existing_report.get("task_id"),
                "reports": existing_report.get("reports", {}),
                "decision": existing_report.get("decision", {}),
                "summary": existing_report.get("summary", ""),
                "recommendation": existing_report.get("recommendation", ""),
                "source": "cached",
                "cache_age_minutes": age_minutes
            }

        # 如果设置了 skip_if_not_exists，且没有缓存报告，直接返回 None
        if skip_if_not_exists:
            logger.info(f"⏭️ [持仓分析] 没有缓存的单股分析报告，跳过单股分析: {stock_code}")
            return None

        # 2. 检查是否有正在运行的分析任务（避免重复创建，不限用户）
        # 注意：analysis_reports 集合中使用的是 stock_symbol 字段
        running_report = await db.analysis_reports.find_one({
            "stock_symbol": stock_code,  # 使用 stock_symbol 字段匹配
            "created_at": {"$gte": recent_cutoff},
            "status": {"$in": ["pending", "running"]}
        }, sort=[("created_at", -1)])

        if running_report:
            task_id = running_report.get("task_id")
            logger.info(f"⏳ [持仓分析] 发现正在运行的任务，等待完成: {stock_code}, task_id={task_id}")
            # 等待这个正在运行的任务完成
            return await self._wait_for_analysis_task(analysis_service, task_id, stock_code)

        # 3. 没有缓存也没有正在运行的任务，创建新的分析
        logger.info(f"🔄 [持仓分析] 3小时内无可用报告，执行新的单股分析: {stock_code}, market={market}")

        # 创建分析请求（使用快速分析模式）
        analysis_request = SingleAnalysisRequest(
            symbol=stock_code,
            stock_code=stock_code,
            parameters=AnalysisParameters(
                research_depth="快速",  # 使用快速模式，减少等待时间
                selected_analysts=["market", "fundamentals", "news"],
                market_type=market
            )
        )

        # 创建任务
        task_result = await analysis_service.create_analysis_task(user_id, analysis_request)
        task_id = task_result.get("task_id")

        # 同步执行分析（等待完成）
        await analysis_service.execute_analysis_background(task_id, user_id, analysis_request)

        # 等待任务完成
        return await self._wait_for_analysis_task(analysis_service, task_id, stock_code)

    async def _wait_for_analysis_task(
        self,
        analysis_service,
        task_id: str,
        stock_code: str,
        max_wait: int = 300
    ) -> Dict[str, Any]:
        """等待分析任务完成并返回结果"""
        import asyncio

        waited = 0
        while waited < max_wait:
            task_status = await analysis_service.get_task_status(task_id)
            if task_status and task_status.get("status") == "completed":
                result_data = task_status.get("result_data", {})
                logger.info(f"✅ [持仓分析] 单股分析完成: {stock_code}")
                return {
                    "task_id": task_id,
                    "reports": result_data.get("reports", {}),
                    "decision": result_data.get("decision", {}),
                    "summary": result_data.get("summary", ""),
                    "recommendation": result_data.get("recommendation", ""),
                    "source": "fresh"
                }
            elif task_status and task_status.get("status") == "failed":
                error_msg = task_status.get("error_message", "未知错误")
                logger.warning(f"⚠️ [持仓分析] 单股分析失败: {stock_code}, 错误: {error_msg}")
                # 返回空报告，持仓分析仍可基于持仓信息给出建议
                return {
                    "task_id": task_id,
                    "reports": {},
                    "decision": {},
                    "summary": f"单股分析未能完成: {error_msg}",
                    "recommendation": "",
                    "source": "failed"
                }

            await asyncio.sleep(2)
            waited += 2

        # 超时
        logger.warning(f"⚠️ [持仓分析] 单股分析超时: {stock_code}")
        return {
            "task_id": task_id,
            "reports": {},
            "decision": {},
            "summary": "单股分析超时",
            "recommendation": "",
            "source": "timeout"
        }

    async def _call_position_ai_analysis_v2(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest,
        stock_analysis_report: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> PositionAnalysisResult:
        """调用AI进行单股持仓分析 - 方案2

        基于完整的单股分析报告 + 持仓信息，生成个性化操作建议
        使用系统配置的深度分析模型
        """
        import httpx

        try:
            # 构建持仓分析专用提示词
            prompt = self._build_position_analysis_prompt_v2(
                snapshot=snapshot,
                params=params,
                stock_analysis_report=stock_analysis_report,
                user_id=user_id
            )

            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from app.services.model_capability_service import get_model_capability_service
            from tradingagents.graph.trading_graph import create_llm_by_provider

            # 使用系统配置的深度分析模型
            capability_service = get_model_capability_service()
            _, deep_model = capability_service._get_default_models()
            model_name = deep_model

            logger.info(f"🤖 [持仓AI分析] 从系统配置获取深度分析模型: {model_name}")

            # 从数据库获取模型的完整配置（包括 API URL 和 API Key）
            provider_info = get_provider_and_url_by_model_sync(model_name)

            base_url = provider_info.get("backend_url")
            api_key = provider_info.get("api_key")
            provider = provider_info.get("provider")

            logger.info(f"🤖 [持仓AI分析] 使用模型: {model_name}")
            logger.info(f"🏭 [持仓AI分析] 模型供应商: {provider}")
            logger.info(f"🔗 [持仓AI分析] API地址: {base_url}")
            logger.info(f"🔑 [持仓AI分析] API Key: {'已配置' if api_key else '未配置'}")

            if not api_key:
                logger.warning("⚠️ [持仓AI分析] API Key 未配置，将尝试从环境变量获取")

            if not base_url:
                logger.error("❌ [持仓AI分析] API地址未配置")
                return PositionAnalysisResult(
                    action=PositionAction.HOLD,
                    action_reason="AI模型未正确配置，请在设置中配置深度分析模型的API地址"
                )

            # 使用统一的 LLM 适配器
            logger.info(f"🔧 [持仓AI分析v2] 准备创建 LLM: provider={provider}, model={model_name}, temperature=0.3")
            if api_key:
                logger.info(f"🔑 [持仓AI分析v2] API Key 前3位: {api_key[:3] if len(api_key) >= 3 else 'N/A'}")
            llm = create_llm_by_provider(
                provider=provider,
                model=model_name,
                backend_url=base_url,
                temperature=0.3,
                max_tokens=4000,
                timeout=120,
                api_key=api_key
            )

            logger.info(f"📤 [持仓AI分析] 开始调用 LLM...")
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"📥 [持仓AI分析] LLM 响应成功，内容长度: {len(content)}")

            return self._parse_position_ai_response_v2(content, snapshot)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [持仓AI分析] 分析失败: {error_msg}", exc_info=True)

            # 提供更友好的错误信息
            if "Connection error" in error_msg or "connect" in error_msg.lower():
                action_reason = "AI服务连接失败，请检查网络连接或API配置"
            elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                action_reason = "API Key 无效或未配置，请在设置中配置正确的API Key"
            elif "rate limit" in error_msg.lower():
                action_reason = "API 调用频率超限，请稍后重试"
            else:
                action_reason = f"AI分析暂时不可用: {error_msg}"

            return PositionAnalysisResult(
                action=PositionAction.HOLD,
                action_reason=action_reason
            )

    async def _call_position_ai_analysis(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest
    ) -> PositionAnalysisResult:
        """调用AI进行单股持仓分析 (旧版本，保留兼容)"""
        try:
            prompt = self._build_position_analysis_prompt(snapshot, params)

            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from tradingagents.graph.trading_graph import create_llm_by_provider

            model_name = "qwen-turbo"
            provider_info = get_provider_and_url_by_model_sync(model_name)

            # 使用统一的 LLM 适配器
            llm = create_llm_by_provider(
                provider=provider_info.get("provider", "dashscope"),
                model=model_name,
                backend_url=provider_info.get("backend_url"),
                temperature=0.3,
                max_tokens=4000,
                timeout=120,
                api_key=provider_info.get("api_key")
            )

            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_position_ai_response(content, snapshot)

        except Exception as e:
            logger.error(f"单股AI分析失败: {e}", exc_info=True)
            return PositionAnalysisResult(
                action=PositionAction.HOLD,
                action_reason=f"AI分析暂时不可用: {str(e)}"
            )

    def _build_position_analysis_prompt(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest
    ) -> str:
        """构建单股持仓分析提示词"""
        pnl_status = "盈利" if (snapshot.unrealized_pnl or 0) >= 0 else "亏损"

        prompt = f"""# 单股持仓分析任务

## 持仓信息
- 股票代码: {snapshot.code}
- 股票名称: {snapshot.name or '未知'}
- 持仓数量: {snapshot.quantity} 股
- 成本价: {snapshot.cost_price:.2f} 元
- 当前价: {snapshot.current_price or '未知'} 元
- 持仓市值: {snapshot.market_value or '未知'} 元
- 浮动盈亏: {snapshot.unrealized_pnl or 0:.2f} 元 ({snapshot.unrealized_pnl_pct or 0:.2f}%)
- 持仓天数: {snapshot.holding_days or '未知'} 天
- 当前状态: {pnl_status}

## 用户设置
- 目标收益率: {params.target_profit_pct}%
- 是否考虑加仓: {'是' if params.include_add_position else '否'}

## 分析要求
请从以下维度分析该持仓，用中文回答：

1. **操作建议** (必须是以下之一: 加仓/减仓/持有/清仓)
2. **建议理由** (100字以内)
3. **置信度** (0-100分)
4. **止损价建议** (具体价格)
5. **止盈价建议** (具体价格)
6. **风险评估** (300-500字，需详细说明主要风险点、风险等级、风险影响等)
7. **机会评估** (300-500字，需详细说明潜在机会、催化剂、收益空间等)
8. **详细分析** (200字以内的完整分析)

请直接给出分析结果。"""

        return prompt

    def _build_position_analysis_prompt_v2(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest,
        stock_analysis_report: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> str:
        """构建持仓分析专用提示词 - 方案2

        基于完整的单股分析报告 + 持仓信息，生成个性化操作建议
        支持模板系统（通过 USE_TEMPLATE_PROMPTS 特性开关控制）
        """
        # 先构建硬编码版本作为降级兜底
        legacy_prompt = self._build_legacy_position_prompt(snapshot, params, stock_analysis_report)

        # 如果启用模板系统，尝试使用模板生成提示词
        if _use_template_prompts():
            try:
                from tradingagents.utils.template_client import get_agent_prompt

                variables = self._build_position_vars(snapshot, params, stock_analysis_report)

                prompt = get_agent_prompt(
                    agent_type="trader",
                    agent_name="position_advisor",
                    variables=variables,
                    user_id=user_id,
                    preference_id=params.invest_style or "neutral",
                    fallback_prompt=legacy_prompt
                )

                if prompt and prompt != legacy_prompt:
                    logger.info(f"✅ [持仓分析] 使用模板系统生成提示词 (长度: {len(prompt)})")
                    return prompt

            except Exception as e:
                logger.warning(f"⚠️ [持仓分析] 模板系统调用失败，使用硬编码提示词: {e}")

        return legacy_prompt

    def _build_legacy_position_prompt(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest,
        stock_analysis_report: Dict[str, Any]
    ) -> str:
        """构建硬编码持仓分析提示词（旧版，作为降级兜底）"""
        pnl_status = "盈利" if (snapshot.unrealized_pnl or 0) >= 0 else "亏损"
        pnl_pct = snapshot.unrealized_pnl_pct or 0

        # 提取各分析师报告
        reports = stock_analysis_report.get("reports", {})
        decision = stock_analysis_report.get("decision", {})
        summary = stock_analysis_report.get("summary", "")
        recommendation = stock_analysis_report.get("recommendation", "")

        # 构建分析报告摘要
        market_report = reports.get("market_report", "")[:1500] if reports.get("market_report") else "暂无"
        fundamentals_report = reports.get("fundamentals_report", "")[:1500] if reports.get("fundamentals_report") else "暂无"
        news_report = reports.get("news_report", "")[:1000] if reports.get("news_report") else "暂无"

        # 提取交易建议
        trade_action = decision.get("action", "未知") if decision else "未知"
        target_price = decision.get("target_price") if decision else None

        prompt = f"""# 持仓分析专家任务

你是一位专业的持仓分析师，需要基于完整的股票分析报告和用户的持仓情况，给出个性化的操作建议。

## 📊 股票分析报告摘要

### 技术面分析
{market_report}

### 基本面分析
{fundamentals_report}

### 新闻面分析
{news_report}

### 综合建议
- 摘要: {summary or '暂无'}
- 交易建议: {trade_action}
- 目标价: {target_price or '未知'}
- 详细建议: {recommendation or '暂无'}

---

## 💼 用户持仓信息

| 项目 | 数值 |
|------|------|
| 股票代码 | {snapshot.code} |
| 股票名称 | {snapshot.name or '未知'} |
| 持仓数量 | {snapshot.quantity} 股 |
| 成本价 | {snapshot.cost_price:.2f} 元 |
| 当前价 | {snapshot.current_price or '未知'} 元 |
| 持仓市值 | {snapshot.market_value or '未知':.2f} 元 |
| 浮动盈亏 | {snapshot.unrealized_pnl or 0:.2f} 元 ({pnl_pct:.2f}%) |
| 持仓天数 | {snapshot.holding_days or '未知'} 天 |
| 当前状态 | {pnl_status} |
| 行业 | {snapshot.industry or '未知'} |

## 🎯 用户投资目标
- 目标收益率: {params.target_profit_pct}%
- 是否考虑加仓: {'是' if params.include_add_position else '否'}
{self._build_capital_info_section(snapshot, params)}

---

## 📝 分析要求

请综合以上股票分析报告和持仓信息，给出个性化的持仓操作建议。

**重要考量因素**：
1. 当前盈亏状态：{pnl_status} {pnl_pct:.2f}%
2. 与目标收益率的差距：目标 {params.target_profit_pct}%，当前 {pnl_pct:.2f}%
3. 股票分析报告中的交易建议：{trade_action}
4. 技术面、基本面、新闻面的综合判断

**请以JSON格式输出**：
```json
{{
    "action": "加仓|减仓|持有|清仓",
    "action_reason": "操作建议的核心理由，需要结合分析报告和持仓情况说明（100字以内）",
    "confidence": 0-100的整数,
    "stop_loss_price": 止损价（数字，保留2位小数）,
    "take_profit_price": 止盈价（数字，保留2位小数）,
    "risk_assessment": "基于分析报告的详细风险评估（300-500字，需包含主要风险点、风险等级、风险影响等）",
    "opportunity_assessment": "基于分析报告的详细机会评估（300-500字，需包含潜在机会、催化剂、收益空间等）",
    "detailed_analysis": "结合分析报告和持仓情况的详细分析（200字以内）",
    "suggested_quantity": 建议操作数量（整数，加仓/减仓时填写，可选）,
    "suggested_amount": 建议操作金额（数字，加仓/减仓时填写，可选）,
    "position_risk_analysis": "仓位风险分析（如提供了资金总量，分析仓位占比是否合理，50字以内，可选）"
}}
```

**注意事项**：
- 止损价应低于当前价
- 止盈价应高于当前价
- 所有价格保留2位小数
- 必须基于提供的分析报告进行判断，不要凭空编造信息
- 如果用户提供了资金总量，务必在分析中考虑仓位占比和风险敞口
"""

        return prompt

    def _build_capital_info_section(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest
    ) -> str:
        """构建资金信息部分的提示词"""
        if not params.total_capital or params.total_capital <= 0:
            return ""

        # 计算各项风险指标
        market_value = snapshot.market_value or (snapshot.quantity * (snapshot.current_price or snapshot.cost_price))
        position_pct = (market_value / params.total_capital) * 100 if params.total_capital > 0 else 0

        # 计算最大可能亏损（假设跌到止损线）
        stop_loss_pct = params.max_loss_pct  # 默认10%
        max_loss_amount = market_value * (stop_loss_pct / 100)
        max_loss_impact_pct = (max_loss_amount / params.total_capital) * 100

        # 计算可加仓金额（基于最大仓位限制）
        max_position_value = params.total_capital * (params.max_position_pct / 100)
        available_add_amount = max(0, max_position_value - market_value)

        # 判断风险等级
        risk_level = "low"
        if position_pct > params.max_position_pct:
            risk_level = "critical"
        elif position_pct > params.max_position_pct * 0.8:
            risk_level = "high"
        elif position_pct > params.max_position_pct * 0.5:
            risk_level = "medium"

        section = f"""
## 💰 资金与仓位分析

| 项目 | 数值 | 说明 |
|------|------|------|
| 投资资金总量 | {params.total_capital:,.0f} 元 | 用户设置的总投资资金 |
| 当前持仓市值 | {market_value:,.2f} 元 | 该股票的持仓市值 |
| 当前仓位占比 | {position_pct:.2f}% | 占总资金比例 |
| 最大仓位限制 | {params.max_position_pct:.0f}% | 单只股票最大仓位 |
| 仓位风险等级 | {risk_level} | low/medium/high/critical |

### 风险敞口分析
- 如果该股票下跌 {stop_loss_pct:.0f}%（止损线），最大亏损金额: {max_loss_amount:,.2f} 元
- 最大亏损对总资金影响: {max_loss_impact_pct:.2f}%
- 用户可接受最大亏损比例: {params.max_loss_pct:.0f}%

### 加仓空间分析
- 最大允许持仓市值: {max_position_value:,.0f} 元
- 当前已占用: {market_value:,.2f} 元
- 剩余可加仓金额: {available_add_amount:,.0f} 元
- 剩余可加仓数量（按当前价）: {int(available_add_amount / (snapshot.current_price or snapshot.cost_price))} 股

**⚠️ 重要提醒**：
- 仓位风险等级为 **{risk_level}**
- {'仓位已超限！建议减仓' if risk_level == 'critical' else '仓位接近上限，谨慎加仓' if risk_level == 'high' else '仓位合理' if risk_level == 'medium' else '仓位较轻，有加仓空间'}
"""
        return section

    def _build_position_vars(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest,
        stock_analysis_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建模板变量（用于模板系统）

        根据设计文档 portfolio-trade-review-engine-integration.md 中定义的变量规范
        """
        pnl_pct = snapshot.unrealized_pnl_pct or 0

        # 提取分析报告
        reports = stock_analysis_report.get("reports", {})
        decision = stock_analysis_report.get("decision", {})

        # 计算仓位信息
        market_value = snapshot.market_value or (snapshot.quantity * (snapshot.current_price or snapshot.cost_price))
        position_pct = 0.0
        position_risk_level = "unknown"

        if params.total_capital and params.total_capital > 0:
            position_pct = (market_value / params.total_capital) * 100
            if position_pct > params.max_position_pct:
                position_risk_level = "critical"
            elif position_pct > params.max_position_pct * 0.8:
                position_risk_level = "high"
            elif position_pct > params.max_position_pct * 0.5:
                position_risk_level = "medium"
            else:
                position_risk_level = "low"

        return {
            # 持仓信息
            "position": {
                "code": snapshot.code,
                "name": snapshot.name or "未知",
                "quantity": snapshot.quantity,
                "cost_price": f"{snapshot.cost_price:.2f}",
                "current_price": f"{snapshot.current_price:.2f}" if snapshot.current_price else "未知",
                "market_value": f"{market_value:.2f}",
                "holding_days": snapshot.holding_days or "未知",
                "unrealized_pnl": f"{snapshot.unrealized_pnl or 0:.2f}",
                "unrealized_pnl_pct": f"{pnl_pct:.2f}",
                "industry": snapshot.industry or "未知"
            },

            # 账户与仓位
            "capital": {
                "total_assets": f"{params.total_capital:,.0f}" if params.total_capital else "未提供",
                "position_pct": f"{position_pct:.2f}",
                "position_risk_level": position_risk_level,
                "max_position_pct": f"{params.max_position_pct:.0f}"
            },

            # 用户设置
            "goal": {
                "target_profit_pct": f"{params.target_profit_pct}",
                "max_loss_pct": f"{params.max_loss_pct}",
                "include_add_position": "是" if params.include_add_position else "否"
            },

            # 单股分析报告
            "engine": {
                "market_report": (reports.get("market_report", "") or "暂无")[:1500],
                "fundamentals_report": (reports.get("fundamentals_report", "") or "暂无")[:1500],
                "news_report": (reports.get("news_report", "") or "暂无")[:1000],
                "sentiment_report": (reports.get("sentiment_report", "") or "暂无")[:500],
                "sector_report": (reports.get("sector_report", "") or "暂无")[:500],
                "final_decision": {
                    "action": decision.get("action", "未知") if decision else "未知",
                    "target_price": str(decision.get("target_price", "未知")) if decision else "未知",
                    "reason": decision.get("reason", stock_analysis_report.get("recommendation", "暂无"))[:500]
                }
            },

            # 上下文
            "context": {
                "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                "user_style": params.invest_style or "neutral"
            }
        }

    def _parse_position_ai_response_v2(
        self,
        content: str,
        snapshot: PositionSnapshot
    ) -> PositionAnalysisResult:
        """解析持仓AI响应 - 方案2 (增强JSON解析)"""
        import re
        import json

        # 尝试提取JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))

                # 解析操作建议
                action_str = data.get("action", "持有")
                action = PositionAction.HOLD
                if "加仓" in action_str:
                    action = PositionAction.ADD
                elif "减仓" in action_str:
                    action = PositionAction.REDUCE
                elif "清仓" in action_str:
                    action = PositionAction.CLEAR

                # 构建价格目标
                price_targets = PriceTarget(
                    stop_loss_price=float(data.get("stop_loss_price", 0)) if data.get("stop_loss_price") else None,
                    take_profit_price=float(data.get("take_profit_price", 0)) if data.get("take_profit_price") else None,
                    breakeven_price=snapshot.cost_price
                )

                # 计算百分比
                if price_targets.stop_loss_price and snapshot.cost_price > 0:
                    price_targets.stop_loss_pct = round((price_targets.stop_loss_price - snapshot.cost_price) / snapshot.cost_price * 100, 2)
                if price_targets.take_profit_price and snapshot.cost_price > 0:
                    price_targets.take_profit_pct = round((price_targets.take_profit_price - snapshot.cost_price) / snapshot.cost_price * 100, 2)

                # 解析建议数量和金额
                suggested_quantity = None
                suggested_amount = None
                if data.get("suggested_quantity"):
                    try:
                        suggested_quantity = int(data["suggested_quantity"])
                    except (ValueError, TypeError):
                        pass
                if data.get("suggested_amount"):
                    try:
                        suggested_amount = float(data["suggested_amount"])
                    except (ValueError, TypeError):
                        pass

                # 构建风险指标（如果提供了资金总量）
                risk_metrics = None
                if snapshot.total_capital and snapshot.total_capital > 0:
                    risk_metrics = self._calculate_risk_metrics(snapshot, price_targets)

                return PositionAnalysisResult(
                    action=action,
                    action_reason=data.get("action_reason", "基于综合分析给出建议"),
                    confidence=float(data.get("confidence", 50)),
                    price_targets=price_targets,
                    risk_assessment=data.get("risk_assessment", "请关注市场风险"),
                    opportunity_assessment=data.get("opportunity_assessment", "请关注市场机会"),
                    detailed_analysis=data.get("detailed_analysis", content[:500]),
                    suggested_quantity=suggested_quantity,
                    suggested_amount=suggested_amount,
                    risk_metrics=risk_metrics
                )
            except json.JSONDecodeError:
                logger.warning("JSON解析失败，使用备用解析方法")

        # 备用解析方法（与原有方法类似）
        return self._parse_position_ai_response(content, snapshot)

    def _parse_position_ai_response(
        self,
        content: str,
        snapshot: PositionSnapshot
    ) -> PositionAnalysisResult:
        """解析单股持仓AI响应"""
        # 确定操作建议
        action = PositionAction.HOLD
        if "加仓" in content:
            action = PositionAction.ADD
        elif "减仓" in content:
            action = PositionAction.REDUCE
        elif "清仓" in content:
            action = PositionAction.CLEAR

        # 提取置信度
        confidence = 50.0
        import re
        conf_match = re.search(r'置信度[：:]\s*(\d+)', content)
        if conf_match:
            confidence = float(conf_match.group(1))

        # 提取止损止盈价
        price_targets = PriceTarget()
        stop_loss_match = re.search(r'止损价[：:]\s*(\d+\.?\d*)', content)
        if stop_loss_match:
            price_targets.stop_loss_price = float(stop_loss_match.group(1))
            if snapshot.cost_price > 0:
                price_targets.stop_loss_pct = round((price_targets.stop_loss_price - snapshot.cost_price) / snapshot.cost_price * 100, 2)

        take_profit_match = re.search(r'止盈价[：:]\s*(\d+\.?\d*)', content)
        if take_profit_match:
            price_targets.take_profit_price = float(take_profit_match.group(1))
            if snapshot.cost_price > 0:
                price_targets.take_profit_pct = round((price_targets.take_profit_price - snapshot.cost_price) / snapshot.cost_price * 100, 2)

        price_targets.breakeven_price = snapshot.cost_price

        # 提取各部分内容
        reason = ""
        risk = ""
        opportunity = ""

        lines = content.split('\n')
        current_section = None
        for line in lines:
            line = line.strip()
            if "建议理由" in line or "理由" in line:
                current_section = "reason"
            elif "风险评估" in line:
                current_section = "risk"
            elif "机会评估" in line:
                current_section = "opportunity"
            elif line and current_section:
                if current_section == "reason" and len(reason) < 100:
                    reason += line + " "
                elif current_section == "risk" and len(risk) < 100:
                    risk += line + " "
                elif current_section == "opportunity" and len(opportunity) < 100:
                    opportunity += line + " "

        return PositionAnalysisResult(
            action=action,
            action_reason=reason.strip() or "基于综合分析给出建议",
            confidence=confidence,
            price_targets=price_targets,
            risk_assessment=risk.strip() or "请关注市场风险",
            opportunity_assessment=opportunity.strip() or "请关注市场机会",
            detailed_analysis=content[:500]
        )

    def _calculate_risk_metrics(
        self,
        snapshot: PositionSnapshot,
        price_targets: PriceTarget
    ) -> PositionRiskMetrics:
        """计算持仓风险指标"""
        if not snapshot.total_capital or snapshot.total_capital <= 0:
            return PositionRiskMetrics()

        total_capital = snapshot.total_capital
        market_value = snapshot.market_value or (snapshot.quantity * (snapshot.current_price or snapshot.cost_price))
        position_pct = (market_value / total_capital) * 100 if total_capital > 0 else 0

        # 计算最大可能亏损（使用止损价或默认10%）
        stop_loss_pct = 10.0  # 默认10%
        if price_targets.stop_loss_pct:
            stop_loss_pct = abs(price_targets.stop_loss_pct)
        max_loss_amount = market_value * (stop_loss_pct / 100)
        max_loss_impact_pct = (max_loss_amount / total_capital) * 100

        # 计算可加仓金额（假设最大仓位30%）
        max_position_pct = 30.0
        max_position_value = total_capital * (max_position_pct / 100)
        available_add_amount = max(0, max_position_value - market_value)

        # 判断风险等级
        if position_pct > max_position_pct:
            risk_level = "critical"
            risk_summary = f"仓位{position_pct:.1f}%已超出上限{max_position_pct:.0f}%，建议减仓"
        elif position_pct > max_position_pct * 0.8:
            risk_level = "high"
            risk_summary = f"仓位{position_pct:.1f}%接近上限，谨慎加仓"
        elif position_pct > max_position_pct * 0.5:
            risk_level = "medium"
            risk_summary = f"仓位{position_pct:.1f}%适中，可适度加仓"
        else:
            risk_level = "low"
            risk_summary = f"仓位{position_pct:.1f}%较轻，有较大加仓空间"

        return PositionRiskMetrics(
            position_pct=round(position_pct, 2),
            position_value=round(market_value, 2),
            max_loss_amount=round(max_loss_amount, 2),
            max_loss_impact_pct=round(max_loss_impact_pct, 2),
            available_add_amount=round(available_add_amount, 2),
            risk_level=risk_level,
            risk_summary=risk_summary
        )

    async def get_position_analysis_history(
        self,
        user_id: str,
        position_id: str,
        page: int = 1,
        page_size: int = 10,
        position_type: str = "real"
    ) -> Dict[str, Any]:
        """获取单股分析历史
        
        Args:
            user_id: 用户ID
            position_id: 持仓ID（格式：code_market）
            page: 页码
            page_size: 每页大小
            position_type: 持仓类型 (real/simulated)
        """
        skip = (page - 1) * page_size

        # 🔥 根据 position_type 添加筛选条件
        query = {
            "user_id": user_id,
            "position_id": position_id,
            "position_type": position_type  # 添加 position_type 筛选条件
        }

        cursor = self.db[self.position_analysis_collection].find(query).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.position_analysis_collection].count_documents(query)

        # 格式化数据：将 ai_analysis 中的所有字段提取到顶层，方便前端使用
        formatted_items = []
        for item in items:
            formatted_item = dict(item)
            
            # 🔥 提取 position_type 字段（用于区分模拟持仓和用户持仓）
            formatted_item["position_type"] = item.get("position_type", "real")
            
            # 提取 ai_analysis 中的所有字段到顶层
            ai_analysis = item.get("ai_analysis", {})
            if ai_analysis:
                # 提取 action（可能是枚举类型，需要转换为字符串）
                action_value = ai_analysis.get("action")
                if action_value:
                    # 如果是枚举类型，获取其值
                    if hasattr(action_value, "value"):
                        formatted_item["action"] = action_value.value
                    elif isinstance(action_value, str):
                        formatted_item["action"] = action_value
                    else:
                        formatted_item["action"] = str(action_value)
                else:
                    formatted_item["action"] = None
                
                # 提取其他字段
                formatted_item["confidence"] = ai_analysis.get("confidence")
                formatted_item["action_reason"] = ai_analysis.get("action_reason", "")
                formatted_item["risk_assessment"] = ai_analysis.get("risk_assessment", "")
                formatted_item["opportunity_assessment"] = ai_analysis.get("opportunity_assessment", "")
                formatted_item["detailed_analysis"] = ai_analysis.get("detailed_analysis", "")
                
                # 提取 price_targets（如果存在）
                price_targets = ai_analysis.get("price_targets")
                if price_targets:
                    # 如果是字典，直接使用；如果是对象，转换为字典
                    if isinstance(price_targets, dict):
                        formatted_item["price_targets"] = price_targets
                    elif hasattr(price_targets, "model_dump"):
                        formatted_item["price_targets"] = price_targets.model_dump()
                    elif hasattr(price_targets, "dict"):
                        formatted_item["price_targets"] = price_targets.dict()
                    else:
                        formatted_item["price_targets"] = None
                else:
                    formatted_item["price_targets"] = None
                
                # 提取其他可选字段
                formatted_item["suggested_quantity"] = ai_analysis.get("suggested_quantity")
                formatted_item["suggested_amount"] = ai_analysis.get("suggested_amount")
                formatted_item["risk_metrics"] = ai_analysis.get("risk_metrics")
                formatted_item["summary"] = ai_analysis.get("summary", "")
                formatted_item["recommendation"] = ai_analysis.get("recommendation", "")
            else:
                # 如果没有 ai_analysis，设置默认值
                formatted_item["action"] = None
                formatted_item["confidence"] = None
                formatted_item["action_reason"] = ""
                formatted_item["risk_assessment"] = ""
                formatted_item["opportunity_assessment"] = ""
                formatted_item["detailed_analysis"] = ""
                formatted_item["price_targets"] = None
            
            # 保留 position_snapshot 中的持仓信息，方便前端显示
            position_snapshot = item.get("position_snapshot")
            if position_snapshot:
                # 直接保留完整的 position_snapshot 对象
                formatted_item["position_snapshot"] = position_snapshot
                
                # 同时提取常用字段到顶层（用于列表显示）
                formatted_item["quantity"] = position_snapshot.get("quantity", 0)
                formatted_item["cost_price"] = position_snapshot.get("cost_price", 0.0)
                formatted_item["current_price"] = position_snapshot.get("current_price", 0.0)
                
                # 计算浮动盈亏（如果 position_snapshot 中没有）
                if "unrealized_pnl" not in position_snapshot:
                    if formatted_item.get("quantity") and formatted_item.get("cost_price") and formatted_item.get("current_price"):
                        quantity = formatted_item["quantity"]
                        cost_price = formatted_item["cost_price"]
                        current_price = formatted_item["current_price"]
                        floating_pnl = (current_price - cost_price) * quantity
                        floating_pnl_pct = ((current_price - cost_price) / cost_price * 100) if cost_price > 0 else 0.0
                        formatted_item["floating_pnl"] = floating_pnl
                        formatted_item["floating_pnl_pct"] = floating_pnl_pct
                else:
                    formatted_item["floating_pnl"] = position_snapshot.get("unrealized_pnl", 0.0)
                    formatted_item["floating_pnl_pct"] = position_snapshot.get("unrealized_pnl_pct", 0.0)
            
            formatted_items.append(formatted_item)

        return {
            "items": formatted_items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    # ==================== 工作流引擎集成 ====================

    async def _call_position_ai_analysis_workflow(
        self,
        snapshot: PositionSnapshot,
        params: PositionAnalysisRequest,
        stock_analysis_report: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> PositionAnalysisResult:
        """使用工作流引擎进行持仓分析

        使用持仓分析工作流，包含：
        1. 持仓技术面分析师 - 分析技术指标和走势
        2. 持仓基本面分析师 - 分析财务数据和估值
        3. 持仓风险评估师 - 评估风险和止损建议
        4. 持仓操作建议师 - 综合分析给出操作建议
        """
        try:
            from core.api.workflow_api import WorkflowAPI

            # 准备单股分析报告数据（agents中使用的字段名是 stock_analysis_report）
            # 如果有缓存，需要设置 has_cache 标志，并提取 reports 子报告
            stock_analysis_report_for_workflow = {}
            if stock_analysis_report and stock_analysis_report.get("reports"):
                # 有缓存：设置标志并提取报告
                stock_analysis_report_for_workflow = {
                    "has_cache": True,
                    "reports": stock_analysis_report.get("reports", {}),
                    "task_id": stock_analysis_report.get("task_id"),
                    "source": stock_analysis_report.get("source", "cached")
                }
                logger.info(f"📊 [工作流持仓分析] 传递缓存报告到工作流: {snapshot.code}, reports字段: {list(stock_analysis_report_for_workflow.get('reports', {}).keys())}")
            else:
                # 无缓存：设置标志为空
                stock_analysis_report_for_workflow = {
                    "has_cache": False,
                    "reports": {},
                    "task_id": None,
                    "source": "none"
                }
                logger.info(f"📊 [工作流持仓分析] 无缓存报告，传递空结构到工作流: {snapshot.code}")
            
            # 准备工作流输入数据
            workflow_inputs = {
                # 持仓基础信息
                "position_info": {
                    "code": snapshot.code,
                    "name": snapshot.name,
                    "market": snapshot.market,
                    "industry": snapshot.industry,
                    "quantity": snapshot.quantity,
                    "cost_price": snapshot.cost_price,
                    "current_price": snapshot.current_price,
                    "market_value": snapshot.market_value,
                    "unrealized_pnl": snapshot.unrealized_pnl,
                    "unrealized_pnl_pct": snapshot.unrealized_pnl_pct,
                    "holding_days": snapshot.holding_days,
                    "position_pct": snapshot.position_pct,
                    "total_capital": snapshot.total_capital
                },

                # 分析参数
                "analysis_params": {
                    "research_depth": params.research_depth,
                    "include_add_position": params.include_add_position,
                    "target_profit_pct": params.target_profit_pct,
                    "total_capital": params.total_capital,
                    "max_position_pct": params.max_position_pct,
                    "max_loss_pct": params.max_loss_pct,
                    "risk_tolerance": params.risk_tolerance,
                    "investment_horizon": params.investment_horizon,
                    "analysis_focus": params.analysis_focus,
                    "position_type": params.position_type
                },

                # 单股分析报告（agents中使用的字段名是 stock_analysis_report）
                "stock_analysis_report": stock_analysis_report_for_workflow,

                # 用户偏好（用于选择提示词模板风格）
                "user_preference": self._get_user_analysis_preference(user_id, params.risk_tolerance),

                # 持仓类型标识
                "position_type": params.position_type
            }

            logger.info(f"🚀 [工作流持仓分析] 开始执行持仓分析工作流 - {snapshot.code}")

            # 🔥 从数据库获取模型配置并构建 legacy_config（与单股分析流程保持一致）
            legacy_config = {}
            try:
                from app.services.config_provider import provider as config_provider
                from app.services.unified_analysis_engine import UnifiedAnalysisEngine
                
                # 使用 config_provider 获取系统设置（包含 quick_analysis_model 和 deep_analysis_model）
                effective_settings = await config_provider.get_effective_system_settings()
                
                # 从 system_settings 中读取 quick_analysis_model 和 deep_analysis_model
                quick_analysis_model = effective_settings.get("quick_analysis_model")
                deep_analysis_model = effective_settings.get("deep_analysis_model")
                
                if quick_analysis_model and deep_analysis_model:
                    # 🔥 使用 UnifiedAnalysisEngine 的 _build_llm_config 方法获取完整的LLM配置
                    # 这样可以获取 temperature, timeout, max_tokens 等参数
                    engine = UnifiedAnalysisEngine()
                    full_config = await engine._build_llm_config(quick_analysis_model, deep_analysis_model)
                    
                    if full_config:
                        legacy_config.update(full_config)
                        logger.info(f"📊 [工作流持仓分析] 从数据库获取完整模型配置: quick={quick_analysis_model}, deep={deep_analysis_model}")
                        logger.info(f"  quick: temperature={legacy_config.get('quick_temperature')}, max_tokens={legacy_config.get('quick_max_tokens')}, timeout={legacy_config.get('quick_timeout')}")
                        logger.info(f"  deep: temperature={legacy_config.get('deep_temperature')}, max_tokens={legacy_config.get('deep_max_tokens')}, timeout={legacy_config.get('deep_timeout')}")
                    else:
                        # 如果获取失败，至少设置模型名称
                        legacy_config["quick_think_llm"] = quick_analysis_model
                        legacy_config["deep_think_llm"] = deep_analysis_model
                        legacy_config["llm_provider"] = "dashscope"
                        logger.warning(f"⚠️ [工作流持仓分析] 无法获取完整模型配置，仅设置模型名称")
                else:
                    logger.warning(f"⚠️ [工作流持仓分析] system_settings中未找到quick_analysis_model或deep_analysis_model，使用默认配置")
                    # 如果没有配置，使用默认值
                    legacy_config["quick_think_llm"] = quick_analysis_model or "qwen-turbo"
                    legacy_config["deep_think_llm"] = deep_analysis_model or "qwen-plus"
                    legacy_config["llm_provider"] = "dashscope"
            except Exception as e:
                logger.error(f"❌ [工作流持仓分析] 从数据库获取模型配置失败: {e}", exc_info=True)
                # 失败时使用默认配置
                legacy_config["quick_think_llm"] = "qwen-turbo"
                legacy_config["deep_think_llm"] = "qwen-plus"
                legacy_config["llm_provider"] = "dashscope"

            # 执行工作流（注意：WorkflowAPI.execute() 是同步方法，不需要 await）
            workflow_api = WorkflowAPI()
            result = workflow_api.execute(
                workflow_id="position_analysis_v2",
                inputs=workflow_inputs,
                legacy_config=legacy_config if legacy_config else None  # 🔥 传递模型配置
            )

            if not result.get("success"):
                error_msg = result.get("error", "工作流执行失败")
                logger.error(f"❌ [工作流持仓分析] 执行失败: {error_msg}")
                return PositionAnalysisResult(
                    action=PositionAction.HOLD,
                    action_reason=f"分析失败: {error_msg}"
                )

            # 解析工作流结果
            workflow_result = result.get("result", {})

            # 提取各个分析师的结果（处理可能是字典的情况）
            def extract_content(value):
                """安全提取内容，处理可能是字典的情况"""
                if isinstance(value, dict):
                    return value.get("content", value.get("error", str(value)))
                elif isinstance(value, str):
                    return value
                else:
                    return str(value) if value else ""

            technical_analysis = extract_content(workflow_result.get("technical_analysis", ""))
            fundamental_analysis = extract_content(workflow_result.get("fundamental_analysis", ""))
            risk_analysis = extract_content(workflow_result.get("risk_analysis", ""))
            
            # action_advice可能是字符串（JSON）或字典（包含content字段）
            action_advice_raw = workflow_result.get("action_advice", "")
            logger.info(f"📊 [工作流持仓分析] action_advice_raw类型: {type(action_advice_raw)}")
            
            # 使用extract_content提取content字段（无论原始格式是什么）
            action_advice = extract_content(action_advice_raw)
            logger.info(f"📊 [工作流持仓分析] action_advice提取后类型: {type(action_advice)}, 长度: {len(str(action_advice))}")

            logger.info(f"✅ [工作流持仓分析] 分析完成 - {snapshot.code}")

            # 初始化默认值
            from app.models.portfolio import PriceTarget
            action = PositionAction.HOLD
            action_reason = ""
            confidence = 0.0
            price_targets = PriceTarget()
            risk_assessment_text = risk_analysis  # 默认使用工作流的风险评估
            opportunity_assessment_text = ""
            
            # 从操作建议中提取具体的操作和理由
            # 如果action_advice是JSON格式，先转换为Markdown
            import json
            advice_json = None
            logger.info(f"📊 [工作流持仓分析] 开始解析action_advice，类型: {type(action_advice)}, 长度: {len(action_advice) if action_advice else 0}")
            
            # 尝试解析JSON（action_advice应该是字符串）
            if action_advice and isinstance(action_advice, str) and ("```json" in action_advice or action_advice.strip().startswith("{")):
                try:
                    # 提取JSON
                    if "```json" in action_advice:
                        json_start = action_advice.find("```json") + 7
                        json_end = action_advice.find("```", json_start)
                        if json_end > json_start:
                            json_str = action_advice[json_start:json_end].strip()
                            logger.info(f"📊 [工作流持仓分析] 从代码块中提取JSON，长度: {len(json_str)}")
                            advice_json = json.loads(json_str)
                    elif action_advice.strip().startswith("{"):
                        logger.info(f"📊 [工作流持仓分析] 直接解析JSON格式")
                        advice_json = json.loads(action_advice)
                except Exception as e:
                    logger.warning(f"⚠️ [工作流持仓分析] JSON解析失败: {e}")
                    advice_json = None
            
            # 转换为Markdown格式并提取其他字段（无论action_advice是字典还是解析后的JSON字符串）
            if advice_json:
                logger.info(f"📊 [工作流持仓分析] JSON解析成功，字段: {list(advice_json.keys())}")
                action_reason = self._convert_action_advice_json_to_markdown(advice_json)
                logger.info(f"📊 [工作流持仓分析] JSON转换为Markdown成功，长度: {len(action_reason)}")
                # 从JSON中提取action
                action = self._extract_action_from_json(advice_json)
                logger.info(f"📊 [工作流持仓分析] 提取的action: {action}")
                # 提取其他字段
                # 置信度可能在多个位置
                confidence = None
                if "confidence" in advice_json:
                    confidence = advice_json.get("confidence")
                elif "neutral_operation_advice" in advice_json:
                    neutral = advice_json["neutral_operation_advice"]
                    if isinstance(neutral, dict):
                        confidence = neutral.get("confidence")
                elif "neutral_operation_suggestion" in advice_json:
                    neutral = advice_json["neutral_operation_suggestion"]
                    if isinstance(neutral, dict):
                        confidence = neutral.get("confidence")
                
                if confidence is not None:
                    try:
                        confidence = float(confidence)
                        # 确保置信度在0-100范围内
                        confidence = max(0.0, min(100.0, confidence))
                    except (ValueError, TypeError):
                        confidence = 50.0  # 默认值
                        logger.warning(f"⚠️ [工作流持仓分析] confidence转换失败，使用默认值50")
                else:
                    # 如果AI没有生成置信度，根据分析质量设置一个合理的默认值
                    confidence = 50.0  # 默认中等置信度
                    logger.info(f"📊 [工作流持仓分析] JSON中没有confidence字段，使用默认值50")
                
                logger.info(f"📊 [工作流持仓分析] 提取的confidence: {confidence}")
                price_targets = self._extract_price_targets_from_json(advice_json, snapshot, params)
                logger.info(f"📊 [工作流持仓分析] 提取的price_targets: stop_loss={price_targets.stop_loss_price}, take_profit={price_targets.take_profit_price}, breakeven={price_targets.breakeven_price}")
                risk_assessment_text = advice_json.get("risk_assessment", "") or risk_analysis
                logger.info(f"📊 [工作流持仓分析] 提取的risk_assessment长度: {len(risk_assessment_text)}")
                opportunity_assessment_text = advice_json.get("opportunity_assessment", "")
                logger.info(f"📊 [工作流持仓分析] 提取的opportunity_assessment长度: {len(opportunity_assessment_text)}")
            else:
                logger.warning(f"⚠️ [工作流持仓分析] advice_json为空，使用文本解析")
                action, action_reason = self._parse_workflow_action_advice(action_advice if isinstance(action_advice, str) else str(action_advice))

            # 构建完整的分析结果
            # 注意：使用转换后的 action_reason（Markdown格式）而不是原始的 action_advice（可能是JSON）
            action_advice_for_summary = action_reason if action_reason else action_advice
            logger.info(f"📊 [工作流持仓分析] 构建analysis_summary: 使用转换后的action_reason（长度: {len(action_advice_for_summary)}）")
            
            # analysis_summary 包含所有内容（用于summary字段）
            analysis_summary = f"""
【技术面分析】
{technical_analysis}

【基本面分析】
{fundamental_analysis}

【风险评估】
{risk_analysis}

【操作建议】
{action_advice_for_summary}
            """.strip()
            
            # detailed_analysis 只包含技术面、基本面和风险评估，不包含操作建议（避免与action_reason重复）
            detailed_analysis = f"""
【技术面分析】
{technical_analysis}

【基本面分析】
{fundamental_analysis}

【风险评估】
{risk_analysis}
            """.strip()
            
            logger.info(f"📊 [工作流持仓分析] analysis_summary长度: {len(analysis_summary)}, detailed_analysis长度: {len(detailed_analysis)}")
            
            # 确保 detailed_analysis 不为空
            if not detailed_analysis:
                logger.warning(f"⚠️ [工作流持仓分析] detailed_analysis为空，使用默认内容")
                detailed_analysis = f"【技术面分析】\n{technical_analysis}\n\n【基本面分析】\n{fundamental_analysis}\n\n【风险评估】\n{risk_analysis}".strip()

            logger.info(f"📊 [工作流持仓分析] 构建分析结果: action={action}, risk_assessment长度={len(risk_assessment_text)}, detailed_analysis长度={len(detailed_analysis)}")
            
            # recommendation 字段也应该使用转换后的 Markdown 格式（与 action_reason 保持一致）
            # 如果 action_reason 已经转换过，直接使用它；否则使用原始的 action_advice（但必须是字符串）
            if action_reason and isinstance(action_reason, str) and action_reason:
                recommendation_markdown = action_reason
            elif isinstance(action_advice, str):
                recommendation_markdown = action_advice
            else:
                # 如果 action_advice 是字典，使用转换后的 action_reason，或者空字符串
                recommendation_markdown = action_reason if isinstance(action_reason, str) else ""
            
            # 确保 recommendation_markdown 是字符串
            if not isinstance(recommendation_markdown, str):
                logger.warning(f"⚠️ [工作流持仓分析] recommendation不是字符串，类型: {type(recommendation_markdown)}，转换为字符串")
                recommendation_markdown = str(recommendation_markdown) if recommendation_markdown else ""
            
            logger.info(f"📊 [工作流持仓分析] recommendation字段: 使用转换后的Markdown，长度: {len(recommendation_markdown)}")

            return PositionAnalysisResult(
                action=action,
                action_reason=action_reason,
                confidence=confidence,
                price_targets=price_targets,
                risk_assessment=risk_assessment_text,
                opportunity_assessment=opportunity_assessment_text,
                detailed_analysis=detailed_analysis,
                summary=analysis_summary,
                recommendation=recommendation_markdown,
                source="workflow_engine_v2"
            )

        except Exception as e:
            logger.error(f"❌ [工作流持仓分析] 执行异常: {e}", exc_info=True)
            return PositionAnalysisResult(
                action=PositionAction.HOLD,
                action_reason=f"工作流分析异常: {str(e)}"
            )

    def _get_user_analysis_preference(self, user_id: Optional[str], risk_tolerance: str) -> str:
        """根据用户ID和风险偏好确定分析风格

        Returns:
            str: 'aggressive', 'neutral', 'conservative'
        """
        # 根据风险偏好映射到分析风格
        risk_to_preference = {
            "low": "conservative",      # 低风险 -> 保守型
            "medium": "neutral",        # 中等风险 -> 中性型
            "high": "aggressive"        # 高风险 -> 激进型
        }

        return risk_to_preference.get(risk_tolerance, "neutral")

    def _convert_action_advice_json_to_markdown(self, advice_json: Dict[str, Any]) -> str:
        """将JSON格式的操作建议转换为Markdown格式的文本
        
        Args:
            advice_json: 操作建议的JSON对象
            
        Returns:
            Markdown格式的操作建议文本
        """
        lines = []
        
        # 1. 分析摘要（如果有）
        if "analysis_summary" in advice_json:
            summary = advice_json["analysis_summary"]
            if isinstance(summary, str) and summary:
                lines.append(f"## 📊 分析摘要\n\n{summary}\n")
            elif isinstance(summary, dict):
                overall_view = summary.get("overall_view", summary.get("overall_assessment", ""))
                if overall_view:
                    lines.append(f"## 📊 分析摘要\n\n{overall_view}\n")
                key_points = summary.get("key_points", [])
                if isinstance(key_points, list) and key_points:
                    lines.append("\n**关键点**：\n\n")
                    for point in key_points:
                        if point:
                            lines.append(f"- {point}\n")
        
        # 2. 综合评估（如果有）
        if "comprehensive_assessment" in advice_json:
            assessment = advice_json["comprehensive_assessment"]
            if isinstance(assessment, dict):
                lines.append("\n## 🔍 综合评估\n\n")
                
                # 持仓状态
                if "position_status" in assessment:
                    pos_status = assessment["position_status"]
                    if isinstance(pos_status, dict):
                        lines.append("### 📈 持仓状态\n\n")
                        current_price = pos_status.get("current_price", "")
                        cost_price = pos_status.get("cost_price", "")
                        floating_loss_ratio = pos_status.get("floating_loss_ratio", "")
                        assessment_text = pos_status.get("assessment", "")
                        if current_price or cost_price or floating_loss_ratio:
                            lines.append(f"- **当前价格**: ¥{current_price}\n")
                            lines.append(f"- **成本价格**: ¥{cost_price}\n")
                            lines.append(f"- **浮动盈亏**: {floating_loss_ratio}\n")
                        if assessment_text:
                            lines.append(f"\n{assessment_text}\n")
                
                # 技术面视角
                if "technical_perspective" in assessment:
                    tech = assessment["technical_perspective"]
                    if isinstance(tech, dict):
                        lines.append("\n### 📊 技术面视角\n\n")
                        trend = tech.get("trend", "")
                        momentum = tech.get("momentum", "")
                        neutral_view = tech.get("neutral_view", "")
                        if trend:
                            lines.append(f"**趋势判断**: {trend}\n\n")
                        if momentum:
                            lines.append(f"**动能分析**: {momentum}\n\n")
                        if neutral_view:
                            lines.append(f"**中性观点**: {neutral_view}\n\n")
                
                # 基本面视角
                if "fundamental_perspective" in assessment:
                    fund = assessment["fundamental_perspective"]
                    if isinstance(fund, dict):
                        lines.append("\n### 💼 基本面视角\n\n")
                        strengths = fund.get("strengths", "")
                        challenges = fund.get("challenges", "")
                        neutral_view = fund.get("neutral_view", "")
                        if strengths:
                            lines.append(f"**优势**: {strengths}\n\n")
                        if challenges:
                            lines.append(f"**挑战**: {challenges}\n\n")
                        if neutral_view:
                            lines.append(f"**中性观点**: {neutral_view}\n\n")
                
                # 风险视角
                if "risk_perspective" in assessment:
                    risk = assessment["risk_perspective"]
                    if isinstance(risk, dict):
                        lines.append("\n### ⚠️ 风险视角\n\n")
                        volatility = risk.get("volatility", "")
                        key_risk_factors = risk.get("key_risk_factors", "")
                        neutral_view = risk.get("neutral_view", "")
                        if volatility:
                            lines.append(f"**波动性**: {volatility}\n\n")
                        if key_risk_factors:
                            lines.append(f"**关键风险因素**: {key_risk_factors}\n\n")
                        if neutral_view:
                            lines.append(f"**中性观点**: {neutral_view}\n\n")
        
        # 3. 中性操作建议（最核心的内容）
        # 支持两种格式：neutral_operation_advice 和 neutral_operation_suggestion
        neutral_advice = None
        if "neutral_operation_advice" in advice_json:
            neutral_advice = advice_json["neutral_operation_advice"]
        elif "neutral_operation_suggestion" in advice_json:
            neutral_advice = advice_json["neutral_operation_suggestion"]
        
        if neutral_advice and isinstance(neutral_advice, dict):
            lines.append("\n## 💡 操作建议\n\n")
            
            # 核心判断
            core_judgment = neutral_advice.get("core_judgment", "")
            if core_judgment:
                lines.append(f"### 核心判断\n\n{core_judgment}\n\n")
            
            # 推荐操作/建议操作（兼容不同字段名）
            recommended_action = neutral_advice.get("recommended_action", neutral_advice.get("suggested_action", ""))
            if recommended_action:
                lines.append(f"**推荐操作**: {recommended_action}\n\n")
            
            # 理由说明（reasoning字段，可能是列表或字符串）
            reasoning = neutral_advice.get("reasoning", [])
            if isinstance(reasoning, list) and reasoning:
                lines.append("### 理由说明\n\n")
                for idx, reason_item in enumerate(reasoning, 1):
                    if isinstance(reason_item, str) and reason_item:
                        lines.append(f"{idx}. {reason_item}\n\n")
                    elif isinstance(reason_item, dict):
                        # 如果是字典，提取所有键值对
                        for key, value in reason_item.items():
                            if value:
                                lines.append(f"**{key}**: {value}\n\n")
            elif isinstance(reasoning, str) and reasoning:
                lines.append(f"### 理由说明\n\n{reasoning}\n\n")
            
            # 具体建议（新格式）
            specific_suggestions = neutral_advice.get("specific_suggestions", [])
            if isinstance(specific_suggestions, list) and specific_suggestions:
                lines.append("### 具体建议\n\n")
                for idx, suggestion in enumerate(specific_suggestions, 1):
                    if isinstance(suggestion, dict):
                        action = suggestion.get("action", "")
                        reason = suggestion.get("reason", "")
                        if action or reason:
                            lines.append(f"#### {idx}. {action}\n\n")
                            if reason:
                                # 处理reason中的Markdown格式（如**加粗**）
                                lines.append(f"{reason}\n\n")
            
            # 详细建议步骤（兼容旧格式）
            detailed_suggestions = neutral_advice.get("detailed_suggestions", [])
            if isinstance(detailed_suggestions, list) and detailed_suggestions:
                for suggestion in detailed_suggestions:
                    if isinstance(suggestion, dict):
                        step = suggestion.get("step", "")
                        content = suggestion.get("content", "")
                        if step or content:
                            if step:
                                lines.append(f"**{step}**\n\n")
                            if content:
                                lines.append(f"{content}\n\n")
            
            # 理由说明（兼容旧格式）
            action_reasoning = neutral_advice.get("action_reasoning", "")
            if action_reasoning:
                lines.append(f"{action_reasoning}\n\n")
            
            # 风险提醒
            risk_reminder = neutral_advice.get("risk_reminder", "")
            if risk_reminder:
                lines.append(f"\n---\n\n> ⚠️ **风险提醒**: {risk_reminder}\n")
        
        # 处理 specific_plan 字段（新格式）
        if "specific_plan" in advice_json:
            specific_plan = advice_json["specific_plan"]
            if isinstance(specific_plan, dict):
                lines.append("\n## 📋 具体计划\n\n")
                
                # 立即步骤
                immediate_step = specific_plan.get("immediate_step", "")
                if immediate_step:
                    lines.append(f"### 立即行动\n\n{immediate_step}\n\n")
                
                # 价格监控
                price_monitoring = specific_plan.get("price_monitoring", {})
                if isinstance(price_monitoring, dict) and price_monitoring:
                    lines.append("### 价格监控\n\n")
                    stop_loss_ref = price_monitoring.get("止损参考价", "")
                    if stop_loss_ref:
                        lines.append(f"**止损参考价**: {stop_loss_ref}\n\n")
                    first_target = price_monitoring.get("第一目标价（减亏/解套）", "")
                    if first_target:
                        lines.append(f"**第一目标价（减亏/解套）**: {first_target}\n\n")
                    second_target = price_monitoring.get("第二目标价（达成收益）", "")
                    if second_target:
                        lines.append(f"**第二目标价（达成收益）**: {second_target}\n\n")
                
                # 观察因素
                observation_factors = specific_plan.get("observation_factors", [])
                if isinstance(observation_factors, list) and observation_factors:
                    lines.append("### 观察要点\n\n")
                    for factor in observation_factors:
                        if factor:
                            lines.append(f"- {factor}\n")
                    lines.append("\n")
        
        # 4. 基于目标的具体建议（兼容旧格式）
        if "specific_suggestions_based_on_your_goals" in advice_json:
            suggestions = advice_json["specific_suggestions_based_on_your_goals"]
            if isinstance(suggestions, dict):
                lines.append("\n## 🎯 基于您的目标的具体建议\n\n")
                
                if_price_rises = suggestions.get("if_price_rises", {})
                if isinstance(if_price_rises, dict):
                    scenario = if_price_rises.get("scenario", "")
                    suggestion = if_price_rises.get("suggestion", "")
                    if scenario or suggestion:
                        lines.append(f"### 📈 如果股价上涨\n\n")
                        if scenario:
                            lines.append(f"**情景**: {scenario}\n\n")
                        if suggestion:
                            lines.append(f"{suggestion}\n\n")
                
                if_price_falls = suggestions.get("if_price_falls", {})
                if isinstance(if_price_falls, dict):
                    scenario = if_price_falls.get("scenario", "")
                    suggestion = if_price_falls.get("suggestion", "")
                    if scenario or suggestion:
                        lines.append(f"### 📉 如果股价下跌\n\n")
                        if scenario:
                            lines.append(f"**情景**: {scenario}\n\n")
                        if suggestion:
                            lines.append(f"{suggestion}\n\n")
                
                if_price_consolidates = suggestions.get("if_price_consolidates", {})
                if isinstance(if_price_consolidates, dict):
                    scenario = if_price_consolidates.get("scenario", "")
                    suggestion = if_price_consolidates.get("suggestion", "")
                    if scenario or suggestion:
                        lines.append(f"### ➡️ 如果股价盘整\n\n")
                        if scenario:
                            lines.append(f"**情景**: {scenario}\n\n")
                        if suggestion:
                            lines.append(f"{suggestion}\n\n")
        
        # 5. 风险提醒（顶层，兼容旧格式）
        if "risk_reminder" in advice_json and "neutral_operation_advice" not in advice_json:
            risk_reminder = advice_json["risk_reminder"]
            if risk_reminder:
                lines.append(f"\n---\n\n> ⚠️ **风险提醒**: {risk_reminder}\n")
        
        # 6. 数据差异说明（兼容旧格式）
        if "data_discrepancy_note" in advice_json:
            note = advice_json["data_discrepancy_note"]
            if isinstance(note, dict):
                important_note = note.get("**重要提示**", note.get("important_note", ""))
                if important_note:
                    lines.append(f"\n> 📌 **重要提示**: {important_note}\n")
            elif isinstance(note, str) and note:
                lines.append(f"\n> 📌 **数据差异说明**: {note}\n")
        
        # 如果没有提取到任何内容，尝试其他字段
        if len(lines) == 0:
            if "conclusion" in advice_json:
                lines.append(advice_json["conclusion"])
            elif "operation_suggestion" in advice_json:
                lines.append(advice_json["operation_suggestion"])
        
        return "\n".join(lines).strip() if lines else "基于综合分析给出建议"
    
    def _extract_price_targets_from_json(self, advice_json: Dict[str, Any], snapshot: PositionSnapshot, params: Optional[PositionAnalysisRequest] = None) -> PriceTarget:
        """从JSON中提取价格目标
        
        Args:
            advice_json: 操作建议的JSON对象
            snapshot: 持仓快照
            
        Returns:
            PriceTarget对象
        """
        from app.models.portfolio import PriceTarget
        import re
        price_targets = PriceTarget()
        
        logger.info(f"📊 [提取价格目标] JSON字段: {list(advice_json.keys())}")
        
        # 提取止损价（可能在多个位置）
        stop_loss_price = None
        
        # 1. 从顶层提取
        stop_loss_price = advice_json.get("stop_loss_price")
        
        # 2. 从specific_plan.price_monitoring中提取
        if not stop_loss_price and "specific_plan" in advice_json:
            specific_plan = advice_json["specific_plan"]
            if isinstance(specific_plan, dict):
                price_monitoring = specific_plan.get("price_monitoring", {})
                if isinstance(price_monitoring, dict):
                    # 提取"止损参考价"字段（可能是字符串，包含价格）
                    stop_loss_ref = price_monitoring.get("止损参考价", "")
                    if stop_loss_ref:
                        # 尝试从字符串中提取价格数字（如"¥4.73"或"4.73"）
                        price_match = re.search(r'[\d.]+', str(stop_loss_ref))
                        if price_match:
                            try:
                                stop_loss_price = float(price_match.group())
                                logger.info(f"📊 [提取价格目标] 从specific_plan.price_monitoring提取止损价: {stop_loss_price}")
                            except (ValueError, TypeError):
                                pass
        
        # 3. 从neutral_operation_advice中提取（如果有）
        if not stop_loss_price and "neutral_operation_advice" in advice_json:
            neutral = advice_json["neutral_operation_advice"]
            if isinstance(neutral, dict):
                stop_loss_price = neutral.get("stop_loss_price")
        
        # 处理止损价
        if stop_loss_price:
            try:
                price_targets.stop_loss_price = float(stop_loss_price)
                if snapshot.cost_price and snapshot.cost_price > 0:
                    price_targets.stop_loss_pct = round(
                        (price_targets.stop_loss_price - snapshot.cost_price) / snapshot.cost_price * 100, 2
                    )
                logger.info(f"📊 [提取价格目标] 止损价: {price_targets.stop_loss_price}, 百分比: {price_targets.stop_loss_pct}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ [提取价格目标] 止损价转换失败: {e}")
        else:
            logger.info(f"📊 [提取价格目标] JSON中没有找到stop_loss_price字段")
        
        # 提取止盈价（可能在多个位置）
        take_profit_price = None
        
        # 1. 从顶层提取
        take_profit_price = advice_json.get("take_profit_price")
        
        # 2. 从specific_plan.price_monitoring中提取（第二目标价通常是止盈价）
        if not take_profit_price and "specific_plan" in advice_json:
            specific_plan = advice_json["specific_plan"]
            if isinstance(specific_plan, dict):
                price_monitoring = specific_plan.get("price_monitoring", {})
                if isinstance(price_monitoring, dict):
                    # 优先使用"第二目标价（达成收益）"
                    second_target = price_monitoring.get("第二目标价（达成收益）", "")
                    if second_target:
                        price_match = re.search(r'[\d.]+', str(second_target))
                        if price_match:
                            try:
                                take_profit_price = float(price_match.group())
                                logger.info(f"📊 [提取价格目标] 从specific_plan.price_monitoring提取止盈价: {take_profit_price}")
                            except (ValueError, TypeError):
                                pass
                    # 如果没有第二目标价，尝试使用第一目标价
                    if not take_profit_price:
                        first_target = price_monitoring.get("第一目标价（减亏/解套）", "")
                        if first_target:
                            price_match = re.search(r'[\d.]+', str(first_target))
                            if price_match:
                                try:
                                    take_profit_price = float(price_match.group())
                                    logger.info(f"📊 [提取价格目标] 从specific_plan.price_monitoring提取止盈价（使用第一目标价）: {take_profit_price}")
                                except (ValueError, TypeError):
                                    pass
        
        # 3. 从neutral_operation_advice中提取（如果有）
        if not take_profit_price and "neutral_operation_advice" in advice_json:
            neutral = advice_json["neutral_operation_advice"]
            if isinstance(neutral, dict):
                take_profit_price = neutral.get("take_profit_price")
        
        # 处理止盈价
        if take_profit_price:
            try:
                price_targets.take_profit_price = float(take_profit_price)
                if snapshot.cost_price and snapshot.cost_price > 0:
                    price_targets.take_profit_pct = round(
                        (price_targets.take_profit_price - snapshot.cost_price) / snapshot.cost_price * 100, 2
                    )
                logger.info(f"📊 [提取价格目标] 止盈价: {price_targets.take_profit_price}, 百分比: {price_targets.take_profit_pct}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ [提取价格目标] 止盈价转换失败: {e}")
        else:
            logger.info(f"📊 [提取价格目标] JSON中没有找到take_profit_price字段")
        
        # 回本价就是成本价
        if snapshot.cost_price and snapshot.cost_price > 0:
            price_targets.breakeven_price = snapshot.cost_price
            logger.info(f"📊 [提取价格目标] 回本价: {price_targets.breakeven_price}")
        
        # 如果AI没有生成价格目标，根据用户设定的百分比计算（fallback逻辑）
        if not price_targets.stop_loss_price and params and snapshot.cost_price and snapshot.cost_price > 0:
            # 使用用户设定的最大亏损百分比计算止损价
            max_loss_pct = params.max_loss_pct if params.max_loss_pct else 10.0  # 默认10%
            price_targets.stop_loss_price = round(snapshot.cost_price * (1 - max_loss_pct / 100), 2)
            price_targets.stop_loss_pct = round(-max_loss_pct, 2)
            logger.info(f"📊 [提取价格目标] AI未生成止损价，根据用户设定计算: stop_loss={price_targets.stop_loss_price} (基于{max_loss_pct}%亏损)")
        
        if not price_targets.take_profit_price and params and snapshot.cost_price and snapshot.cost_price > 0:
            # 使用用户设定的目标收益百分比计算止盈价
            target_profit_pct = params.target_profit_pct if params.target_profit_pct else 10.0  # 默认10%
            price_targets.take_profit_price = round(snapshot.cost_price * (1 + target_profit_pct / 100), 2)
            price_targets.take_profit_pct = round(target_profit_pct, 2)
            logger.info(f"📊 [提取价格目标] AI未生成止盈价，根据用户设定计算: take_profit={price_targets.take_profit_price} (基于{target_profit_pct}%收益)")
        
        return price_targets
    
    def _extract_action_from_json(self, advice_json: Dict[str, Any]) -> PositionAction:
        """从JSON中提取action
        
        Args:
            advice_json: 操作建议的JSON对象
            
        Returns:
            PositionAction枚举值
        """
        # 优先从neutral_operation_advice.specific_suggestions中提取（新格式）
        if "neutral_operation_advice" in advice_json:
            neutral = advice_json["neutral_operation_advice"]
            if isinstance(neutral, dict):
                # 新格式：从specific_suggestions数组中提取第一个action
                specific_suggestions = neutral.get("specific_suggestions", [])
                if isinstance(specific_suggestions, list) and specific_suggestions:
                    first_suggestion = specific_suggestions[0]
                    if isinstance(first_suggestion, dict):
                        action_text = first_suggestion.get("action", "")
                        if action_text:
                            action_lower = action_text.lower()
                            if "加仓" in action_lower or "买入" in action_lower or "补仓" in action_lower:
                                return PositionAction.ADD
                            elif "减仓" in action_lower or "减持" in action_lower:
                                return PositionAction.REDUCE
                            elif "清仓" in action_lower or "卖出" in action_lower or "全部卖出" in action_lower:
                                return PositionAction.CLEAR
                            elif "持有" in action_lower or "继续持有" in action_lower or "观察" in action_lower:
                                return PositionAction.HOLD
                
                # 兼容旧格式：从recommended_action中提取
                recommended = neutral.get("recommended_action", "")
                if recommended:
                    recommended_lower = recommended.lower()
                    if "加仓" in recommended_lower or "买入" in recommended_lower:
                        return PositionAction.ADD
                    elif "减仓" in recommended_lower:
                        return PositionAction.REDUCE
                    elif "清仓" in recommended_lower or "卖出" in recommended_lower:
                        return PositionAction.CLEAR
        
        # 默认持有
        return PositionAction.HOLD
    
    def _parse_workflow_action_advice(self, action_advice: str) -> tuple[PositionAction, str]:
        """从工作流的操作建议中解析出具体的操作和理由

        Args:
            action_advice: 操作建议师的输出文本

        Returns:
            tuple: (操作类型, 操作理由)
        """
        if not action_advice:
            return PositionAction.HOLD, "未获取到操作建议"

        # 转换为小写便于匹配
        advice_lower = action_advice.lower()

        # 根据关键词判断操作类型（使用正确的枚举值）
        if any(keyword in advice_lower for keyword in ["买入", "加仓", "增持", "建议买", "推荐买", "add"]):
            action = PositionAction.ADD
        elif any(keyword in advice_lower for keyword in ["清仓", "建议卖", "推荐卖", "clear"]):
            action = PositionAction.CLEAR
        elif any(keyword in advice_lower for keyword in ["减仓", "卖出", "reduce"]):
            action = PositionAction.REDUCE
        else:
            action = PositionAction.HOLD

        # 提取操作理由（取前200个字符作为简要理由）
        action_reason = action_advice[:200] + "..." if len(action_advice) > 200 else action_advice

        return action, action_reason


# 服务实例
_portfolio_service: Optional[PortfolioService] = None


def get_portfolio_service() -> PortfolioService:
    """获取持仓分析服务实例"""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service

