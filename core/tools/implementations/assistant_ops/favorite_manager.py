"""
股票关注列表列表管理工具

提供批量添加股票到股票关注列表列表的能力，适合与智能选股结果联动。
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


def _parse_tags(tags: str) -> list[str]:
    raw = (tags or "").replace("，", ",").replace("、", ",")
    parsed = []
    seen = set()
    for item in raw.split(","):
        tag = item.strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        parsed.append(tag)
    return parsed


@tool
@register_tool(
    tool_id="list_favorite_stocks",
    name="查看股票关注列表",
    description="查看用户的股票关注列表（即股票关注列表列表），可选按标签筛选。会返回股票代码、名称、市场和已有标签。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["favorite_management", "watchlist", "query", "list", "assistant_ops", "stock_favorites", "stock_watchlist", "tag_filter", "favorites_view", "self_selected_stocks"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看股票关注列表列表", "浏览关注的股票", "按标签筛选股票关注列表", "确认已关注的股票"],
    when_to_use="当用户想查看自己的股票关注列表、股票关注列表，或按标签筛选已关注的股票时使用。",
    returns="返回文本格式的股票关注列表列表，包含股票名称、代码、市场和已有标签。",
)
async def list_favorite_stocks(
    tag: Annotated[str, "可选，按标签筛选，例如 巴菲特；留空表示查看全部关注股票"] = "",
) -> str:
    """查看当前用户的股票关注列表（即股票关注列表），支持按标签筛选。"""
    from app.services.favorites_service import favorites_service

    user_id = require_current_user_id()
    favorites = await favorites_service.get_user_favorites(user_id)

    normalized_tag = str(tag or "").strip()
    if normalized_tag:
        favorites = [
            item for item in favorites
            if normalized_tag in list(item.get("tags") or [])
        ]

    if not favorites:
        if normalized_tag:
            return f"📂 你的股票关注列表中没有标签为「{normalized_tag}」的股票。"
        return "📂 你的股票关注列表目前为空，还没有添加任何股票关注列表。"

    lines = []
    for item in favorites:
        code = item.get("stock_code") or "-"
        name = item.get("stock_name") or code
        market = item.get("market") or "A股"
        tags = list(item.get("tags") or [])
        tag_text = f" | 标签: {', '.join(tags)}" if tags else ""
        lines.append(f"- {name} ({code}) | {market}{tag_text}")

    header = (
        f"📂 你的股票关注列表（标签：{normalized_tag}，共 {len(favorites)} 只）"
        if normalized_tag else
        f"📂 你的股票关注列表（共 {len(favorites)} 只）"
    )
    return header + "\n" + "\n".join(lines)


@tool
@register_tool(
    tool_id="add_stocks_to_favorites",
    name="批量添加股票到股票关注列表",
    description="将一只或多只股票批量添加到用户股票关注列表列表，适合在智能选股完成后一次保存推荐结果；支持通过 tags 参数同时给这些股票打标签，并为已在股票关注列表中的股票补充标签。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["favorite_management", "watchlist", "add", "batch_add", "assistant_ops", "stock_favorites", "tag_assignment", "bulk_add", "favorites_update", "self_selected_stocks"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["批量添加股票关注列表", "保存智能选股结果", "给关注股票打标签", "补充已有股票关注列表标签"],
    when_to_use="当用户想把一只或多只股票加入股票关注列表列表，或在智能选股完成后批量保存推荐结果时使用。",
    returns="返回文本消息，包含新增、跳过、补充标签和失败的股票代码统计。",
)
async def add_stocks_to_favorites(
    stocks_json: Annotated[
        str,
        "股票 JSON 数组，例如 [{\"code\":\"600519\",\"name\":\"贵州茅台\",\"market\":\"A股\"}]",
    ],
    tags: Annotated[
        str,
        "可选，给这些股票同时打上的标签，逗号分隔，例如 巴菲特,高分红",
    ] = "",
) -> str:
    """批量添加股票到当前用户的股票关注列表列表，并可同时补充标签。"""
    from app.services.favorites_service import favorites_service
    from app.services.tags_service import tags_service

    user_id = require_current_user_id()
    parsed_tags = _parse_tags(tags)

    try:
        items = json.loads(stocks_json)
    except json.JSONDecodeError:
        return "❌ 参数格式错误，请传入股票 JSON 数组。"

    if not isinstance(items, list) or not items:
        return "❌ 请至少提供一只待加入股票关注列表的股票。"

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

    existing_favorites = await favorites_service.get_user_favorites(user_id)
    existing_map = {
        str(item.get("stock_code") or item.get("symbol") or "").strip(): item
        for item in existing_favorites
        if str(item.get("stock_code") or item.get("symbol") or "").strip()
    }

    if parsed_tags:
        try:
            existing_tags = {
                tag.get("name")
                for tag in await tags_service.list_tags(user_id)
                if tag.get("name")
            }
            for tag_name in parsed_tags:
                if tag_name in existing_tags:
                    continue
                try:
                    await tags_service.create_tag(user_id=user_id, name=tag_name)
                    existing_tags.add(tag_name)
                except Exception:
                    logger.debug("[add_stocks_to_favorites] 创建标签失败，继续使用收藏标签聚合: %s", tag_name, exc_info=True)
        except Exception:
            logger.debug("[add_stocks_to_favorites] 读取/创建标签失败，继续执行收藏更新", exc_info=True)

    added_codes = []
    skipped_codes = []
    tagged_codes = []
    failed_codes = []

    for item in normalized_items:
        code = item["code"]
        try:
            existing = existing_map.get(code)
            if existing:
                current_tags = list(existing.get("tags") or [])
                merged_tags = current_tags
                if parsed_tags:
                    merged_tags = list(dict.fromkeys([*current_tags, *parsed_tags]))

                if merged_tags != current_tags:
                    await favorites_service.update_favorite(
                        user_id=user_id,
                        stock_code=code,
                        tags=merged_tags,
                    )
                    tagged_codes.append(code)
                else:
                    skipped_codes.append(code)
                continue

            await favorites_service.add_favorite(
                user_id=user_id,
                stock_code=code,
                stock_name=item["name"],
                market=item["market"],
                tags=parsed_tags,
            )
            added_codes.append(code)
        except Exception as e:
            logger.warning("[add_stocks_to_favorites] 添加股票关注列表失败: %s %s", code, e)
            failed_codes.append(code)

    lines = [
        f"✅ 已添加 {len(added_codes)} 只股票到股票关注列表" if added_codes else "✅ 本次没有新增股票关注列表",
    ]
    if added_codes:
        lines.append(f"- 新增: {', '.join(added_codes)}")
    if parsed_tags:
        lines.append(f"- 标签: {', '.join(parsed_tags)}")
    if tagged_codes:
        lines.append(f"- 已补充标签 {len(tagged_codes)} 只: {', '.join(tagged_codes)}")
    if skipped_codes:
        lines.append(f"- 已存在 {len(skipped_codes)} 只: {', '.join(skipped_codes)}")
    if failed_codes:
        lines.append(f"- 失败 {len(failed_codes)} 只: {', '.join(failed_codes)}")

    return "\n".join(lines)