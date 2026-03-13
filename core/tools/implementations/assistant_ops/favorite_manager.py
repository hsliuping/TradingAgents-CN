"""
自选股列表管理工具

提供批量添加股票到自选股列表的能力，适合与智能选股结果联动。
"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _normalize_market(market: str) -> str:
    value = (market or "A股").strip().upper()
    if value in ("A股", "CN", "SH", "SZ", "SSE", "SZSE", "BJ", "BSE"):
        return "A股"
    if value in ("港股", "HK", "HKEX"):
        return "港股"
    if value in ("美股", "US", "NASDAQ", "NYSE", "AMEX"):
        return "美股"
    return "A股"


@tool
@register_tool(
    tool_id="add_stocks_to_favorites",
    name="批量添加股票到自选股",
    description="将一只或多只股票批量添加到用户自选股列表，适合在智能选股完成后一次保存推荐结果。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def add_stocks_to_favorites(
    stocks_json: Annotated[
        str,
        "股票 JSON 数组，例如 [{\"code\":\"600519\",\"name\":\"贵州茅台\",\"market\":\"A股\"}]",
    ],
) -> str:
    """批量添加股票到当前用户的自选股列表。"""
    from app.services.favorites_service import favorites_service

    user_id = require_current_user_id()

    try:
        items = json.loads(stocks_json)
    except json.JSONDecodeError:
        return "❌ 参数格式错误，请传入股票 JSON 数组。"

    if not isinstance(items, list) or not items:
        return "❌ 请至少提供一只待加入自选股的股票。"

    normalized_items = []
    seen_codes = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or item.get("symbol") or item.get("stock_code") or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        normalized_items.append({
            "code": code,
            "name": str(item.get("name") or item.get("stock_name") or code).strip() or code,
            "market": _normalize_market(str(item.get("market") or "A股")),
        })

    if not normalized_items:
        return "❌ 未解析出有效的股票代码。"

    added_codes = []
    skipped_codes = []
    failed_codes = []

    for item in normalized_items:
        code = item["code"]
        try:
            if await favorites_service.is_favorite(user_id, code):
                skipped_codes.append(code)
                continue

            await favorites_service.add_favorite(
                user_id=user_id,
                stock_code=code,
                stock_name=item["name"],
                market=item["market"],
            )
            added_codes.append(code)
        except Exception as e:
            logger.warning("[add_stocks_to_favorites] 添加自选股失败: %s %s", code, e)
            failed_codes.append(code)

    lines = [
        f"✅ 已添加 {len(added_codes)} 只股票到自选股" if added_codes else "✅ 本次没有新增自选股",
    ]
    if added_codes:
        lines.append(f"- 新增: {', '.join(added_codes)}")
    if skipped_codes:
        lines.append(f"- 已存在 {len(skipped_codes)} 只: {', '.join(skipped_codes)}")
    if failed_codes:
        lines.append(f"- 失败 {len(failed_codes)} 只: {', '.join(failed_codes)}")

    return "\n".join(lines)