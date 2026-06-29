"""标准化技术因子包工具。"""

import json
import logging
from typing import Annotated, Any, Dict

from langchain_core.tools import tool

from app.core.database import get_mongo_db_sync
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

TECHNICAL_FIELDS = [
    "ma20",
    "rsi14",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "dif",
    "dea",
    "macd_hist",
]


def _normalize_symbol(symbol: str) -> str:
    digits = "".join(ch for ch in str(symbol or "") if ch.isdigit())
    return digits.zfill(6)


def _pick_numeric(doc: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = doc.get(key)
        if value is not None:
            return value
    return None


@tool
@register_tool(
    tool_id="get_technical_factor_bundle_tool",
    name="技术因子包",
    description=(
        "返回股票的 technical_core 标准化技术因子包。"
        "适合一次性获取 MA20、RSI14、KDJ(K/D/J)、MACD(DIF/DEA/HIST) 这批当前仓库已物化并稳定支持的技术指标。"
        "输出是结构化 JSON，适合 Agent 直接绑定后做择时、趋势判断和技术面筛选。"
    ),
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_indicators", "factor_bundle", "structured_data", "ma", "rsi", "kdj", "macd"],
    tool_role_hint="supporting",
    preferred_for=["技术指标批量获取", "结构化技术因子", "Agent 技术面输入"],
    data_source="stock_technical_indicators/market_quotes",
    when_to_use=(
        "当 Agent 需要趋势、动量、超买超卖、MACD/KDJ 信号这类技术面指标时使用。"
        "如果你需要的是技术指标字段集合而不是长篇技术分析报告，优先绑定这个工具。"
    ),
    when_not_to_use=(
        "不适合获取 PE/PB/ROE/现金流等基本面指标；"
        "也不适合需要完整历史序列回测的场景。若只需可读性较强的文本技术分析，可考虑 get_technical_indicators。"
    ),
    returns=(
        "返回 JSON 字符串，结构包含 symbol、name、current_price、trade_date、data_source、bundle=technical_core、"
        "factors、missing_factors、calculation_notes。"
        "factors 中固定包含 ma20、rsi14、kdj_k、kdj_d、kdj_j、dif、dea、macd_hist。"
    ),
    example="get_technical_factor_bundle_tool(symbol='600519')",
    related_tools=[
        "get_technical_indicators",
        "get_stock_market_data_unified",
        "get_fundamental_factor_snapshot_tool",
    ],
)
def get_technical_factor_bundle_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"]
) -> str:
    """获取标准化技术因子包。"""
    normalized_symbol = _normalize_symbol(symbol)

    try:
        db = get_mongo_db_sync()
        technical_doc = db["stock_technical_indicators"].find_one(
            {"code": normalized_symbol},
            sort=[("trade_date", -1), ("updated_at", -1)],
        ) or {}
        quote_doc = db["market_quotes"].find_one(
            {"code": normalized_symbol},
            sort=[("trade_date", -1), ("updated_at", -1)],
        ) or {}
        basic_doc = db["stock_basic_info"].find_one({"code": normalized_symbol}) or {}

        factors = {field: technical_doc.get(field) for field in TECHNICAL_FIELDS}
        missing_factors = [field for field, value in factors.items() if value is None]

        payload = {
            "symbol": normalized_symbol,
            "name": basic_doc.get("name") or quote_doc.get("name"),
            "current_price": _pick_numeric(quote_doc, "close", "price", "last_price"),
            "trade_date": technical_doc.get("trade_date") or quote_doc.get("trade_date"),
            "data_source": technical_doc.get("source") or quote_doc.get("source"),
            "bundle": "technical_core",
            "factors": factors,
            "missing_factors": missing_factors,
            "calculation_notes": [
                "技术指标优先读取 stock_technical_indicators 中最新物化快照。",
                "当前标准技术因子包固定包含 MA20、RSI14、KDJ(K/D/J)、MACD(DIF/DEA/HIST)。",
                "如果 missing_factors 非空，表示对应指标在最新技术快照中暂不可用。",
            ],
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("技术因子包获取失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": f"获取技术因子包失败: {exc}", "symbol": normalized_symbol},
            ensure_ascii=False,
            indent=2,
            default=str,
        )


__all__ = ["get_technical_factor_bundle_tool"]