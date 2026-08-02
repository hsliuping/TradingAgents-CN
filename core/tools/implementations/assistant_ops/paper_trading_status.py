"""使用问答机器人工具：查询模拟交易账户状态。

让使用问答助手能"看到"用户当前的模拟交易账户状态，包含：
- 总资产、可用资金、持仓市值
- 已实现盈亏、浮动盈亏
- 持仓股票数、盈利/亏损股票数
- 持仓明细（最多 10 只）

避免机器人凭 FAQ 猜答案，遇到模拟交易相关问题直接调工具看真实状态。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _format_money(value: Optional[float]) -> str:
    """格式化金额为中文可读字符串。"""
    if value is None:
        return "未知"
    try:
        v = float(value)
        if abs(v) >= 100_000_000:
            return f"{v / 100_000_000:.2f} 亿"
        if abs(v) >= 10_000:
            return f"{v / 10_000:.2f} 万"
        return f"{v:.2f} 元"
    except Exception:
        return str(value)


def _format_pnl(value: Optional[float]) -> str:
    """格式化盈亏金额（带正负号）。"""
    if value is None:
        return "未知"
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{_format_money(v)}"
    except Exception:
        return str(value)


async def _get_paper_account(db, user_id: str) -> Optional[Dict[str, Any]]:
    """获取或创建模拟交易账户。"""
    try:
        # 兼容 user_id 为 ObjectId 或字符串
        from bson import ObjectId
        uid = user_id
        try:
            uid = ObjectId(user_id)
        except Exception:
            pass

        acc = await db["paper_accounts"].find_one({"user_id": uid})
        if not acc:
            # 尝试字符串形式
            acc = await db["paper_accounts"].find_one({"user_id": user_id})
        if not acc:
            # 检查是否已有初始化的账户
            acc = await db["paper_accounts"].find_one({"user_id": uid, "status": "active"})
        return acc
    except Exception as exc:
        logger.warning("[get_paper_trading_status] 查询模拟账户失败: %s", exc)
        return None


async def _get_paper_positions(db, user_id: str) -> List[Dict[str, Any]]:
    """获取持仓列表。"""
    try:
        from bson import ObjectId
        uid = user_id
        try:
            uid = ObjectId(user_id)
        except Exception:
            pass

        cursor = db["paper_positions"].find({"user_id": uid})
        docs = await cursor.to_list(length=50)
        if not docs:
            docs = await db["paper_positions"].find({"user_id": user_id}).to_list(length=50)
        return docs or []
    except Exception as exc:
        logger.warning("[get_paper_trading_status] 查询持仓失败: %s", exc)
        return []


async def _get_latest_prices(db, codes: List[str]) -> Dict[str, Optional[float]]:
    """批量获取最新价（从 market_quotes 或 historical_data 集合）。"""
    prices: Dict[str, Optional[float]] = {}
    if not codes:
        return prices
    try:
        for code in codes:
            # 优先从 market_quotes 集合取
            quote = await db["market_quotes"].find_one({"code": code}, sort=[("updated_at", -1)])
            if quote and quote.get("last_price"):
                prices[code] = float(quote["last_price"])
                continue
            # 回退到 historical_data 取最新一条
            hist = await db["historical_data"].find_one({"symbol": code}, sort=[("date", -1)])
            if hist and hist.get("close"):
                prices[code] = float(hist["close"])
            else:
                prices[code] = None
    except Exception as exc:
        logger.warning("[get_paper_trading_status] 获取最新价失败: %s", exc)
    return prices


@tool
@register_tool(
    tool_id="get_paper_trading_status",
    name="查询模拟交易账户状态",
    description="查询当前用户的模拟交易账户状态：总资产、可用资金、持仓市值、已实现盈亏、浮动盈亏、持仓股票数、盈利亏损股票数。当用户问'模拟账户多少钱''今天盈亏多少''还剩多少资金''持仓几只股票''哪只亏得最多'时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "paper_trading", "portfolio", "account_balance", "pnl", "positions", "virtual_trading"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=[
        "模拟账户多少钱",
        "模拟交易总资产",
        "今天盈亏多少",
        "可用资金还有多少",
        "持仓几只股票",
        "哪只股票亏得最多",
        "持仓股票盈亏情况",
        "模拟交易账户状态",
    ],
    when_to_use="当用户问到模拟交易账户余额、可用资金、持仓数、盈亏情况时使用。",
    returns="返回文本格式的模拟交易账户摘要，包含总资产、可用资金、持仓市值、盈亏、持仓股票列表。",
)
async def get_paper_trading_status() -> str:
    """查询模拟交易账户状态。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    acc = await _get_paper_account(db, user_id)
    if not acc:
        return (
            "📊 模拟交易账户状态\n"
            "\n"
            "❌ 您还没有开通模拟交易账户\n"
            "\n"
            "💡 提示：可以到仪表板点击「模拟交易总资产」卡片，或在侧边栏选择「模拟交易」菜单，"
            "首次进入会自动为您开通虚拟账户（初始资金 100 万）。"
        )

    positions = await _get_paper_positions(db, user_id)

    # 解析资金信息（多货币格式）
    cash_dict = acc.get("cash", {})
    realized_pnl_dict = acc.get("realized_pnl", {})

    # 兼容旧格式（单一现金）
    if not isinstance(cash_dict, dict):
        cash_dict = {"CNY": float(cash_dict or 0)}
    if not isinstance(realized_pnl_dict, dict):
        realized_pnl_dict = {"CNY": float(realized_pnl_dict or 0)}

    # 获取持仓股票的最新价
    codes = [p.get("code") for p in positions if p.get("code")]
    prices = await _get_latest_prices(db, codes)

    # 计算持仓市值（按 CNY 简化）
    positions_value_cny = 0.0
    floating_pnl_cny = 0.0
    enriched_positions: List[Dict[str, Any]] = []

    for p in positions:
        code = p.get("code", "?")
        name = p.get("name", "") or code
        qty = int(p.get("quantity", 0) or 0)
        avg_cost = float(p.get("avg_cost", 0) or 0.0)
        last_price = prices.get(code)
        mkt_value = (last_price or 0.0) * qty
        floating = (last_price - avg_cost) * qty if last_price is not None else None

        positions_value_cny += mkt_value
        if floating is not None:
            floating_pnl_cny += floating

        enriched_positions.append({
            "code": code,
            "name": name,
            "quantity": qty,
            "avg_cost": avg_cost,
            "last_price": last_price,
            "market_value": round(mkt_value, 2),
            "floating_pnl": round(floating, 2) if floating is not None else None,
            "floating_pnl_pct": (
                round(((last_price - avg_cost) / avg_cost) * 100, 2)
                if last_price is not None and avg_cost > 0 else None
            ),
        })

    cash_cny = float(cash_dict.get("CNY", 0) or 0)
    realized_pnl_cny = float(realized_pnl_dict.get("CNY", 0) or 0)
    total_assets = cash_cny + positions_value_cny
    total_pnl = realized_pnl_cny + floating_pnl_cny

    # 持仓股票盈亏统计
    profit_count = sum(1 for p in enriched_positions if (p.get("floating_pnl") or 0) > 0)
    loss_count = sum(1 for p in enriched_positions if (p.get("floating_pnl") or 0) < 0)
    flat_count = sum(1 for p in enriched_positions if (p.get("floating_pnl") or 0) == 0)

    # 找出亏损最多和盈利最多的股票
    worst_position = None
    best_position = None
    if enriched_positions:
        with_pnl = [p for p in enriched_positions if p.get("floating_pnl") is not None]
        if with_pnl:
            worst_position = min(with_pnl, key=lambda x: x["floating_pnl"])
            best_position = max(with_pnl, key=lambda x: x["floating_pnl"])

    # 格式化输出
    lines = ["📊 模拟交易账户状态"]
    lines.append("")
    lines.append("【1】资产概览")
    lines.append(f"- 总资产: {_format_money(total_assets)}")
    lines.append(f"- 可用资金: {_format_money(cash_cny)}")
    lines.append(f"- 持仓市值: {_format_money(positions_value_cny)}")
    lines.append("")
    lines.append("【2】盈亏情况")
    lines.append(f"- 总盈亏(已实现+浮动): {_format_pnl(total_pnl)}")
    lines.append(f"- 已实现盈亏: {_format_pnl(realized_pnl_cny)}")
    lines.append(f"- 浮动盈亏: {_format_pnl(floating_pnl_cny)}")
    lines.append("")
    lines.append("【3】持仓统计")
    lines.append(f"- 持仓股票数: {len(enriched_positions)}")
    lines.append(f"- 盈利/亏损/持平: {profit_count}/{loss_count}/{flat_count}")

    if best_position and (best_position.get("floating_pnl") or 0) > 0:
        lines.append(
            f"- 盈利最多: {best_position['name']}({best_position['code']}) "
            f"{_format_pnl(best_position['floating_pnl'])} "
            f"({best_position.get('floating_pnl_pct', 0):+}%)"
        )
    if worst_position and (worst_position.get("floating_pnl") or 0) < 0:
        lines.append(
            f"- 亏损最多: {worst_position['name']}({worst_position['code']}) "
            f"{_format_pnl(worst_position['floating_pnl'])} "
            f"({worst_position.get('floating_pnl_pct', 0):+}%)"
        )

    # 持仓明细（最多 10 只）
    if enriched_positions:
        lines.append("")
        lines.append("【4】持仓明细（最多 10 只）")
        sorted_positions = sorted(
            enriched_positions,
            key=lambda x: abs(x.get("market_value") or 0),
            reverse=True,
        )
        for p in sorted_positions[:10]:
            pnl_str = (
                f"{_format_pnl(p['floating_pnl'])} ({p.get('floating_pnl_pct', 0):+}%)"
                if p.get("floating_pnl") is not None else "无最新价"
            )
            last_price_str = f"{p['last_price']:.2f}" if p.get("last_price") is not None else "无"
            lines.append(
                f"  • {p['name']}({p['code']}) 数量 {p['quantity']} | "
                f"成本 {p['avg_cost']:.2f} | 最新价 {last_price_str} | "
                f"市值 {_format_money(p['market_value'])} | 浮动 {pnl_str}"
            )

    # 账户更新时间
    updated_at = acc.get("updated_at") or acc.get("created_at")
    if updated_at:
        if isinstance(updated_at, datetime):
            updated_str = updated_at.strftime("%Y-%m-%d %H:%M")
        else:
            updated_str = str(updated_at)[:19]
        lines.append("")
        lines.append(f"📌 账户最近更新: {updated_str}")

    # 综合建议
    lines.append("")
    lines.append("💡 综合判断")
    if not enriched_positions:
        lines.append("- 当前空仓，可用资金充足。可以到「模拟交易」页面进行虚拟操作练习")
    else:
        if floating_pnl_cny > 0:
            lines.append(f"- 当前持仓整体浮盈 {_format_pnl(floating_pnl_cny)}，可关注收益关注价位")
        elif floating_pnl_cny < 0:
            lines.append(f"- 当前持仓整体浮亏 {_format_pnl(floating_pnl_cny)}，可关注风险关注价位")
        else:
            lines.append("- 当前持仓整体持平")

        if cash_cny / max(total_assets, 1) < 0.1:
            lines.append("- ⚠️ 可用资金占比 < 10%，资金利用率高，注意风险")
        elif cash_cny / max(total_assets, 1) > 0.9 and positions_value_cny > 0:
            lines.append("- 可用资金占比 > 90%，资金利用率低")

    return "\n".join(lines)
