"""
懂车帝汽车品牌月度销量查询工具

数据来源：懂车帝公开销量榜接口
    https://www.dongchedi.com/motor/pc/car/rank_data
    ?month=202608          # 指定月份；500=近半年、1000=近一年聚合
    &rank_data_type=11     # 全国月度销量榜
    &count=100             # 单次上限 100
    &offset=0              # 翻页有效

接口仅需 User-Agent + Referer，无需认证。
榜单为车系（车型）粒度，含 brand_name（如 "AITO问界"），
因此按品牌查询需要拉取全量榜单后再按品牌名匹配。
"""

import logging
import re
import time
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

import requests
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

_RANK_API = "https://www.dongchedi.com/motor/pc/car/rank_data"

# 懂车帝仅要求携带 UA + Referer，无需认证
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.dongchedi.com/auto/rank",
}

_RANK_TYPE_SALES = 11   # 11=全国月度销量榜（缺省为关注度榜）
_PAGE_SIZE = 100        # 接口单次返回上限
_MAX_PAGES = 12         # 翻页上限（1200 条），防御异常情况下的无限翻页
_REQUEST_TIMEOUT = 15
_REQUEST_RETRIES = 2
_RETRY_INTERVAL = 0.5

# 缓存键前缀（走项目统一缓存入口，避免同一月份榜单被反复拉取）
_CACHE_SYMBOL_PREFIX = "dongchedi_rank"
_CACHE_DATA_SOURCE = "dongchedi"


def _request_rank(params: Dict[str, Any]) -> Dict[str, Any]:
    """请求销量榜接口（带重试）"""
    last_error = ""
    for attempt in range(_REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                _RANK_API,
                params=params,
                headers=_HTTP_HEADERS,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("status") == 0:
                return payload
            last_error = f"接口返回异常状态: status={payload.get('status')}, message={payload.get('message')}"
        except Exception as e:
            last_error = str(e)
        if attempt < _REQUEST_RETRIES:
            time.sleep(_RETRY_INTERVAL * (attempt + 1))
    raise RuntimeError(last_error or "未知错误")


def _fetch_page(month: str, offset: int, count: int = _PAGE_SIZE) -> Dict[str, Any]:
    """拉取单页榜单数据"""
    payload = _request_rank({
        "month": month,
        "rank_data_type": _RANK_TYPE_SALES,
        "count": count,
        "offset": offset,
    })
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _fetch_rank_list(month: str) -> List[Dict[str, Any]]:
    """翻页拉取指定月份的全国销量榜全量数据"""
    items: List[Dict[str, Any]] = []
    offset = 0
    for page in range(_MAX_PAGES):
        data = _fetch_page(month, offset)
        page_items = data.get("list") or []
        if not page_items:
            break
        items.extend(page_items)
        has_more = (data.get("paging") or {}).get("has_more")
        logger.debug(f"懂车帝销量榜 {month} 第 {page + 1} 页: {len(page_items)} 条, has_more={has_more}")
        if not has_more:
            break
        offset += _PAGE_SIZE
    return items


def _probe_month(month: str) -> bool:
    """探测某月是否有销量数据（仅取 1 条，节省流量）"""
    try:
        data = _fetch_page(month, 0, count=1)
        return bool(data.get("list"))
    except Exception:
        return False


def _previous_month(year_month: int) -> int:
    """返回上一个自然月（YYYYMM 整数形式）"""
    year, month = divmod(year_month, 100)
    if month == 1:
        return (year - 1) * 100 + 12
    return year * 100 + (month - 1)


def _detect_latest_month() -> str:
    """
    返回最近一个有数据的完整月份

    起点取上一个自然月：当月榜单为滚动累计口径（月内尚未结束），
    作为「月度销量」不完整，故默认不采用。
    """
    today = datetime.now()
    cursor = _previous_month(today.year * 100 + today.month)
    for _ in range(4):
        candidate = f"{cursor:06d}"
        if _probe_month(candidate):
            return candidate
        cursor = _previous_month(cursor)
    return ""


def _normalize_month(month: str) -> Optional[str]:
    """
    归一化月份输入

    Returns:
        接口可用的 month 值；None 表示未提供（需自动探测）；空字符串表示格式非法
    """
    if month is None or str(month).strip() == "":
        return None
    text = str(month).strip()
    # 先处理带分隔符的写法（2026年8月 / 2026-8 / 2026/8 / 2026.8），
    # 否则“8”在去除非数字字符后会变成“20268”，月份前导 0 丢失
    separated = re.search(r"(\d{4})\s*[年\-/.]\s*(\d{1,2})", text)
    if separated:
        return f"{separated.group(1)}{int(separated.group(2)):02d}"
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if digits in ("500", "1000"):   # 近半年 / 近一年聚合口径
        return digits
    if len(digits) == 6:            # YYYYMM
        return digits
    return ""


def _format_month_label(month: str) -> str:
    """把 month 参数值转为可读的统计口径描述"""
    if month == "500":
        return "近半年（销量聚合）"
    if month == "1000":
        return "近一年（销量聚合）"
    if len(month) == 6:
        return f"{month[:4]}年{int(month[4:6])}月"
    return month


def _normalize_text(value: Any) -> str:
    """归一化品牌/车型名，便于大小写与空白无关的匹配"""
    return re.sub(r"\s+", "", str(value or "")).lower()


def _match_brand_items(items: List[Dict[str, Any]], brand: str) -> List[Dict[str, Any]]:
    """
    按品牌名匹配榜单条目

    匹配优先级：品牌名精确匹配 > 品牌名/子品牌名/车系名包含关键词
    （懂车帝品牌名常带前缀，如 "AITO问界"，故必须支持包含匹配）
    """
    key = _normalize_text(brand)
    if not key:
        return []

    exact: List[Dict[str, Any]] = []
    fuzzy: List[Dict[str, Any]] = []
    for item in items:
        brand_name = _normalize_text(item.get("brand_name"))
        sub_brand = _normalize_text(item.get("sub_brand_name"))
        series_name = _normalize_text(item.get("series_name"))
        if brand_name and brand_name == key:
            exact.append(item)
        elif key in brand_name or key in sub_brand or key in series_name or (brand_name and brand_name in key):
            fuzzy.append(item)

    return exact or fuzzy


def _format_rank_trend(rank: Any, last_rank: Any) -> str:
    """根据本期/上期排名计算名次变化"""
    if not rank:
        return "-"
    if not last_rank:
        return "新上榜"
    delta = int(last_rank) - int(rank)
    if delta > 0:
        return f"↑{delta}"
    if delta < 0:
        return f"↓{abs(delta)}"
    return "—"


def _render_brand_section(brand_name: str, sub_brand_name: str, rows: List[Dict[str, Any]]) -> str:
    """渲染单个品牌的车型销量表"""
    total = sum(int(item.get("count") or 0) for item in rows)
    header = f"### {brand_name}"
    if sub_brand_name and sub_brand_name != brand_name:
        header += f"（{sub_brand_name}）"
    header += f" — 合计 {total:,} 辆"

    lines = [
        header,
        "",
        "| 排名 | 车型 | 月销量(辆) | 售价区间 | 上期排名 | 名次变化 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in rows:
        rank = item.get("rank") or "-"
        last_rank = item.get("last_rank") or "-"
        lines.append(
            f"| {rank} | {item.get('series_name') or '-'} "
            f"| {int(item.get('count') or 0):,} "
            f"| {item.get('price') or '-'} "
            f"| {last_rank} "
            f"| {_format_rank_trend(item.get('rank'), item.get('last_rank'))} |"
        )
    return "\n".join(lines)


def _load_rank_list(month: str) -> List[Dict[str, Any]]:
    """获取指定月份榜单全量数据（优先命中项目统一缓存）"""
    symbol = f"{_CACHE_SYMBOL_PREFIX}_{month}_{_RANK_TYPE_SALES}"

    try:
        from tradingagents.dataflows.cache import get_cache

        cache = get_cache()
        cache_key = cache.find_cached_stock_data(
            symbol=symbol,
            start_date="",
            end_date="",
            data_source=_CACHE_DATA_SOURCE,
        )
        if cache_key:
            cached = cache.load_stock_data(cache_key)
            if isinstance(cached, list) and cached:
                logger.info(f"✅ 懂车帝销量榜命中缓存: {symbol}（{len(cached)} 条）")
                return cached
    except Exception as e:
        logger.warning(f"⚠️ 懂车帝销量榜缓存读取失败，改为实时拉取: {e}")

    items = _fetch_rank_list(month)

    try:
        from tradingagents.dataflows.cache import get_cache

        get_cache().save_stock_data(
            symbol=symbol,
            data=items,
            start_date="",
            end_date="",
            data_source=_CACHE_DATA_SOURCE,
        )
    except Exception as e:
        logger.warning(f"⚠️ 懂车帝销量榜缓存写入失败: {e}")

    return items


@tool
@register_tool(
    tool_id="get_auto_brand_monthly_sales",
    name="汽车品牌月度销量",
    description="查询指定汽车品牌在某个月份下的全部车型销量（懂车帝全国月度销量榜），返回车型排名、月销量、售价区间与名次变化",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["auto_sales", "brand_sales", "monthly_sales", "auto_industry", "dongchedi"],
    tool_role_hint="specialized",
    output_shape="report",
    preferred_for=["汽车品牌月度销量查询", "品牌旗下车型销量对比", "整车厂商销量跟踪"],
)
def get_auto_brand_monthly_sales(
    brand: Annotated[str, "汽车品牌名称，如“问界”“比亚迪”“理想汽车”。支持模糊匹配：输入“问界”可匹配懂车帝品牌名“AITO问界”"],
    month: Annotated[str, "统计月份，格式 YYYYMM（如 202608 表示 2026 年 8 月）；也可传 500（近半年聚合）或 1000（近一年聚合）；留空则自动使用最近一个有数据的完整月份"] = "",
) -> str:
    """
    查询汽车品牌月度销量。

    通过懂车帝全国月度销量榜获取指定品牌旗下所有车型的月销量，
    适用于汽车产业链/整车厂商的销量跟踪与横向对比。

    Args:
        brand: 汽车品牌名称（支持模糊匹配）
        month: 统计月份 YYYYMM，或 500/1000 聚合口径，留空自动取最近一个完整月份

    Returns:
        str: markdown 格式的品牌车型销量报告
    """
    if not brand or not str(brand).strip():
        return "❌ 请提供汽车品牌名称，例如：问界、比亚迪、理想汽车。"

    normalized_month = _normalize_month(month)
    if normalized_month == "":
        return f"❌ 月份格式无法识别：{month}。请使用 YYYYMM 格式（如 202608），或 500（近半年）/1000（近一年）。"

    try:
        if normalized_month is None:
            normalized_month = _detect_latest_month()
            if not normalized_month:
                return "❌ 未能获取到最近的销量榜数据，请稍后重试或显式指定月份（如 202608）。"
            logger.info(f"📅 懂车帝销量榜自动选用最新月份: {normalized_month}")

        month_label = _format_month_label(normalized_month)
        logger.info(f"🚗 [汽车品牌销量] 品牌={brand}, 月份={month_label}")

        items = _load_rank_list(normalized_month)
        if not items:
            return f"❌ 未获取到 {month_label} 的销量榜数据（数据可能尚未发布）。"

        matched = _match_brand_items(items, brand)
        if not matched:
            top_brands: List[str] = []
            for item in items[:80]:
                name = item.get("brand_name")
                if name and name not in top_brands:
                    top_brands.append(name)
                if len(top_brands) >= 15:
                    break
            return (
                f"❌ 未在 {month_label} 销量榜中找到品牌“{brand}”。\n\n"
                f"该月榜单共 {len(items)} 款车型、{len(set(i.get('brand_name') for i in items))} 个品牌。\n"
                f"可参考的品牌名示例：{'、'.join(top_brands)}。"
            )

        # 按品牌分组（模糊匹配可能命中同一车企的多个品牌，如“吉利银河”“吉利汽车”）
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in matched:
            grouped.setdefault(item.get("brand_name") or str(brand), []).append(item)

        sections = []
        for brand_name, rows in grouped.items():
            rows.sort(key=lambda x: (x.get("rank") or 9999))
            sub_brand = rows[0].get("sub_brand_name") or ""
            sections.append(_render_brand_section(brand_name, sub_brand, rows))

        total_count = sum(int(item.get("count") or 0) for item in matched)
        # 当月榜单为滚动累计口径，需向读者说明数据尚未完整
        current_month = f"{datetime.now():%Y%m}"
        month_note = "（该月尚未结束，为滚动累计数据）" if normalized_month == current_month else ""
        report = f"""# 汽车品牌月度销量：{brand}

- **统计口径**：懂车帝全国月度销量榜（{month_label}）{month_note}
- **匹配车型数**：{len(matched)} 款
- **合计销量**：{total_count:,} 辆

{chr(10).join(sections)}

---
数据来源：懂车帝公开销量榜。以上为车型零售销量统计，仅供研究参考，不构成投资建议。
"""
        logger.info(f"✅ [汽车品牌销量] 完成，匹配 {len(matched)} 款车型，合计 {total_count} 辆")
        return report

    except Exception as e:
        logger.error(f"❌ [汽车品牌销量] 查询失败: {e}", exc_info=True)
        return f"汽车品牌月度销量查询失败：{e}"