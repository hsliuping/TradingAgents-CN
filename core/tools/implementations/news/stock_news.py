"""
统一股票新闻工具

自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

数据源优先级：
1. MongoDB 数据库（包括 local、akshare、tushare 等数据源）
2. 外部 API（AKShare、Google News、Finnhub）
"""

import concurrent.futures
import hashlib
import logging
import unicodedata
from datetime import datetime, time, timedelta
from typing import Annotated, Any, Callable, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


A_SHARE_NEWS_LOOKBACK_DAYS = 7
TUSHARE_LIVE_SOURCES = [
    "sina",
    "eastmoney",
    "10jqka",
    "cls",
    "wallstreetcn",
]

SOURCE_DISPLAY_NAMES = {
    "local": "本地数据",
    "tushare": "Tushare",
    "akshare": "AKShare",
    "baostock": "Baostock",
    "google": "Google新闻",
    "finnhub": "Finnhub",
}

LIVE_SOURCE_DISPLAY_NAMES = {
    "tushare": "Tushare多源新闻（付费增强）",
    "akshare": "AKShare东方财富（免费回退）",
}

CATEGORY_DISPLAY_NAMES = {
    "company_announcement": "公司公告",
    "policy_news": "政策监管",
    "industry_news": "行业新闻",
    "market_news": "市场动态",
    "other": "其他",
}

SENTIMENT_DISPLAY_NAMES = {
    "positive": "偏积极",
    "negative": "偏审慎",
    "neutral": "中性",
}

IMPORTANCE_DISPLAY_NAMES = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

A_SHARE_DIRECT_EVENT_KEYWORDS = [
    "业绩",
    "财报",
    "公告",
    "年报",
    "季报",
    "半年报",
    "业绩预告",
    "业绩快报",
    "回购",
    "分红",
    "派息",
    "增持",
    "减持",
    "合作",
    "协议",
    "中标",
    "签约",
    "发布",
    "发货",
    "落地",
    "停牌",
    "复牌",
    "重组",
    "并购",
    "回应",
    "传闻",
    "辟谣",
    "澄清",
]

A_SHARE_BROAD_CONTEXT_KEYWORDS = [
    "资本市场",
    "市场大事提醒",
    "大事提醒",
    "国家统计局",
    "重磅数据",
    "板块",
    "指数",
    "etf",
    "基金",
    "资金流入",
    "资金流出",
    "市场",
    "a股",
    "沪深",
    "早报",
    "午报",
    "晚报",
    "策略",
    "一周",
    "下周",
]

A_SHARE_ENUMERATION_MARKERS = [
    "等",
    "多家",
    "多只",
    "多股",
    "名单",
    "提醒",
]

A_SHARE_GENERIC_ALIAS_TERMS = {
    "银行",
    "证券",
    "保险",
    "科技",
    "医药",
    "药业",
    "电子",
    "集团",
    "股份",
    "控股",
    "发展",
    "实业",
    "能源",
    "电力",
    "信息",
    "投资",
    "材料",
    "航空",
    "汽车",
    "家居",
    "制造",
    "通信",
    "地产",
}

HIGH_CONFIDENCE_A_SHARE_RELEVANCE_SCORE = 85

HIGH_SIGNAL_NEWS_SOURCE_KEYWORDS = [
    "公告",
    "交易所",
    "证监会",
    "财联社",
    "证券时报",
    "新浪财经",
    "华尔街见闻",
    "同花顺",
    "东方财富",
    "红星资本局",
    "路透",
    "彭博",
]

LOW_SIGNAL_NEWS_SOURCE_KEYWORDS = [
    "股吧",
    "论坛",
    "微博",
    "自媒体",
    "社区",
]


def _normalize_analysis_date(curr_date: str) -> str:
    """标准化分析日期字符串。"""
    return curr_date.split()[0] if " " in curr_date else curr_date


def _build_a_share_news_window(curr_date: str) -> Tuple[datetime, datetime, str, str]:
    """构建 A 股新闻查询时间窗口，默认覆盖分析日往前 7 个自然日。"""
    analysis_date_str = _normalize_analysis_date(curr_date)
    analysis_date = datetime.strptime(analysis_date_str, "%Y-%m-%d")
    start_date = datetime.combine(
        (analysis_date - timedelta(days=A_SHARE_NEWS_LOOKBACK_DAYS - 1)).date(),
        time.min,
    )
    end_date = datetime.combine(analysis_date.date(), time.max)
    return start_date, end_date, start_date.strftime("%Y-%m-%d"), analysis_date_str


def _normalize_a_share_symbol(ticker: str) -> str:
    """标准化 A 股股票代码。"""
    return (
        ticker.upper()
        .replace(".SH", "")
        .replace(".SZ", "")
        .replace(".SS", "")
        .replace(".XSHE", "")
        .replace(".XSHG", "")
    )


def _collapse_whitespace(value: Any) -> str:
    """折叠多余空白，便于 Markdown 输出。"""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _parse_publish_time(value: Any) -> Optional[datetime]:
    """解析新闻发布时间。"""
    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        return None

    text = _collapse_whitespace(value)
    if not text:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%m-%d %H:%M",
        "%m/%d %H:%M",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt in {"%m-%d %H:%M", "%m/%d %H:%M"}:
                parsed = parsed.replace(year=datetime.now().year)
            return parsed
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        logger.debug(f"⚠️ [统一新闻工具] 无法解析新闻时间: {text}")
        return None


def _format_publish_time(value: Any) -> str:
    """格式化新闻发布时间。"""
    parsed = _parse_publish_time(value)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d %H:%M")
    return _collapse_whitespace(value) or "未知时间"


def _coerce_keywords(value: Any) -> List[str]:
    """统一关键词为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in (_collapse_whitespace(keyword) for keyword in value) if item]
    if isinstance(value, str):
        text = _collapse_whitespace(value)
        if not text:
            return []
        separators = [",", "，", ";", "；", "|"]
        tokens = [text]
        for separator in separators:
            if separator in text:
                tokens = text.split(separator)
                break
        return [item for item in (_collapse_whitespace(token) for token in tokens) if item]
    return []


def _get_source_display_name(source: str) -> str:
    """获取数据源显示名称。"""
    return SOURCE_DISPLAY_NAMES.get(source, source or "未知来源")


def _get_live_source_display_name(source: str) -> str:
    """获取 A 股实时数据源显示名称。"""
    return LIVE_SOURCE_DISPLAY_NAMES.get(source, _get_source_display_name(source))


def _get_a_share_enabled_sources() -> List[str]:
    """获取 A 股启用的数据源优先级。"""
    try:
        from app.core.data_source_priority import get_enabled_data_sources_sync

        return get_enabled_data_sources_sync(market_category="a_shares")
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] 获取 A 股数据源优先级失败，使用默认顺序: {exc}")
        return ["local", "tushare", "akshare", "baostock"]


def _build_a_share_live_source_plan(enabled_sources: List[str]) -> List[str]:
    """生成 A 股实时新闻分析链路，仅使用 AKShare。"""
    return ["akshare"] if "akshare" in enabled_sources else ["akshare"]


def _build_a_share_analysis_priority(enabled_sources: List[str]) -> List[str]:
    """生成 A 股新闻分析链路优先级说明。"""
    priority = ["local"] if "local" in enabled_sources else []
    for source in _build_a_share_live_source_plan(enabled_sources):
        if source not in priority:
            priority.append(source)

    return priority or ["local", "akshare"]


def _is_placeholder_company_name(company_name: str, symbol: str) -> bool:
    """判断公司名是否只是占位符。"""
    cleaned_name = _collapse_whitespace(company_name)
    return not cleaned_name or cleaned_name in {symbol, f"股票{symbol}"}


def _get_company_name(symbol: str) -> Optional[str]:
    """获取股票代码对应的公司名称。"""
    try:
        from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified

        stock_info = get_china_stock_info_unified(symbol)
        company_name = _collapse_whitespace(stock_info.get("name")) if isinstance(stock_info, dict) else ""
        if company_name and not _is_placeholder_company_name(company_name, symbol):
            return company_name
    except Exception as exc:
        logger.debug(f"⚠️ [统一新闻工具] 通过 data_source_manager 获取公司名失败: {exc}")

    try:
        from tradingagents.utils.news_filter import get_company_name

        company_name = _collapse_whitespace(get_company_name(symbol))
        if company_name and not _is_placeholder_company_name(company_name, symbol):
            return company_name
    except Exception as exc:
        logger.debug(f"⚠️ [统一新闻工具] 通过新闻过滤器获取公司名失败: {exc}")

    return None


def _get_company_aliases(company_name: Optional[str]) -> List[str]:
    """生成公司名称别名，用于 Tushare 新闻相关性过滤。"""
    if not company_name:
        return []

    normalized_name = _collapse_whitespace(company_name)
    aliases = set()
    suffixes = [
        "股份有限公司",
        "集团股份有限公司",
        "集团有限公司",
        "有限公司",
        "股份",
        "集团",
    ]

    def _add_alias(alias_value: Optional[str]) -> None:
        alias_text = _collapse_whitespace(alias_value)
        if not alias_text or len(alias_text) < 2:
            return

        aliases.add(alias_text)

        alias_nfkc = _normalize_nfkc_text(alias_text)
        if alias_nfkc and alias_nfkc != alias_text and len(alias_nfkc) >= 2:
            aliases.add(alias_nfkc)

    _add_alias(normalized_name)

    for suffix in suffixes:
        if normalized_name.endswith(suffix):
            alias = normalized_name[: -len(suffix)]
            _add_alias(alias)

    if len(normalized_name) >= 4:
        shortened_alias = normalized_name[2:]
        if shortened_alias and shortened_alias not in A_SHARE_GENERIC_ALIAS_TERMS:
            _add_alias(shortened_alias)

    for alias in list(aliases):
        alias_nfkc = _normalize_nfkc_text(alias)
        if len(alias_nfkc) >= 3 and alias_nfkc[-1].upper() in {"A", "B", "H"}:
            stripped_alias = alias_nfkc[:-1].strip()
            if stripped_alias and stripped_alias not in A_SHARE_GENERIC_ALIAS_TERMS:
                _add_alias(stripped_alias)

    return [alias for alias in sorted(aliases, key=len, reverse=True) if len(alias) >= 2]


def _normalize_nfkc_text(value: Any) -> str:
    """对文本做空白折叠与 NFKC 归一化，兼容全角/半角股票简称。"""
    text = _collapse_whitespace(value)
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


def _text_contains_company_name(text: Optional[str], company_name: Optional[str]) -> bool:
    """判断文本是否包含公司名，兼容全角/半角差异。"""
    normalized_text = _collapse_whitespace(text)
    normalized_company_name = _collapse_whitespace(company_name)
    if not normalized_text or not normalized_company_name:
        return False

    if normalized_company_name in normalized_text:
        return True

    text_nfkc = _normalize_nfkc_text(normalized_text)
    company_name_nfkc = _normalize_nfkc_text(normalized_company_name)
    return bool(company_name_nfkc and company_name_nfkc in text_nfkc)


def _find_matching_aliases(text: Optional[str], aliases: List[str]) -> List[str]:
    """返回文本中命中的公司别名，兼容全角/半角差异。"""
    normalized_text = _collapse_whitespace(text)
    if not normalized_text or not aliases:
        return []

    text_nfkc = _normalize_nfkc_text(normalized_text)
    matches = []
    for alias in aliases:
        normalized_alias = _collapse_whitespace(alias)
        if not normalized_alias:
            continue

        alias_nfkc = _normalize_nfkc_text(normalized_alias)
        if normalized_alias in normalized_text or (alias_nfkc and alias_nfkc in text_nfkc):
            matches.append(normalized_alias)

    return matches


def _text_starts_with_any_alias(text: Optional[str], aliases: List[str]) -> bool:
    """判断标题是否以任一公司别名起始，兼容全角/半角差异。"""
    normalized_text = _collapse_whitespace(text)
    if not normalized_text or not aliases:
        return False

    text_nfkc = _normalize_nfkc_text(normalized_text)
    for alias in aliases:
        normalized_alias = _collapse_whitespace(alias)
        if not normalized_alias:
            continue

        alias_nfkc = _normalize_nfkc_text(normalized_alias)
        if normalized_text.startswith(normalized_alias) or (
            alias_nfkc and text_nfkc.startswith(alias_nfkc)
        ):
            return True

    return False


def _is_relevant_a_share_news(news_item: Dict[str, Any], symbol: str, company_name: Optional[str]) -> bool:
    """判断新闻是否与目标 A 股公司相关。"""
    symbol_clean = symbol.zfill(6)
    text_parts = [
        _collapse_whitespace(news_item.get("title")),
        _collapse_whitespace(news_item.get("content")),
        _collapse_whitespace(news_item.get("summary")),
        " ".join(_coerce_keywords(news_item.get("keywords"))),
    ]
    text_blob = " ".join(part for part in text_parts if part)

    if not text_blob:
        return False

    if symbol_clean in text_blob or symbol in text_blob:
        return True

    return bool(_find_matching_aliases(text_blob, _get_company_aliases(company_name)))


def _filter_news_by_date_range(
    news_list: List[Dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """严格按分析日期窗口过滤新闻。"""
    filtered_news = []

    for news in news_list:
        publish_time = _parse_publish_time(news.get("publish_time"))
        if publish_time is None:
            continue
        if start_date <= publish_time <= end_date:
            filtered_news.append(news)

    return filtered_news


def _contains_any_keyword(text: str, keywords: List[str]) -> bool:
    """判断文本是否包含任一关键词。"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


def _strip_redundant_title_from_body_text(title: str, body_text: str) -> str:
    """去除摘要/正文中重复拼接的标题，避免重复计分。"""
    normalized_title = _collapse_whitespace(title)
    normalized_body = _collapse_whitespace(body_text)
    if not normalized_title or not normalized_body:
        return normalized_body

    body_without_title = normalized_body.replace(normalized_title, "", 1)
    return body_without_title.strip("【】[]():：- \n\t")


def _calculate_a_share_news_relevance(
    news_item: Dict[str, Any],
    symbol: str,
    company_name: Optional[str],
) -> int:
    """计算 A 股新闻的公司直指度与事件相关性评分。"""
    title = _collapse_whitespace(news_item.get("title"))
    summary = _collapse_whitespace(news_item.get("summary"))
    content = _collapse_whitespace(news_item.get("content"))
    body_text = " ".join(part for part in [summary, content] if part)
    body_text_for_scoring = _strip_redundant_title_from_body_text(title, body_text)
    aliases = _get_company_aliases(company_name)
    symbol_clean = symbol.zfill(6)

    title_alias_matches = _find_matching_aliases(title, aliases)
    body_alias_matches = _find_matching_aliases(body_text_for_scoring, aliases)
    title_has_symbol = symbol_clean in title or symbol in title
    body_has_symbol = symbol_clean in body_text_for_scoring or symbol in body_text_for_scoring
    title_has_company_name = _text_contains_company_name(title, company_name)
    body_has_company_name = _text_contains_company_name(body_text_for_scoring, company_name)

    score = 0

    if title_has_symbol:
        score += 90
    elif body_has_symbol:
        score += 35

    if title_has_company_name:
        score += 70
    elif title_alias_matches:
        score += 55

    if title_alias_matches and _text_starts_with_any_alias(title, title_alias_matches):
        score += 15

    if body_has_company_name:
        score += 30
    elif body_alias_matches:
        score += 20

    if _contains_any_keyword(title, A_SHARE_DIRECT_EVENT_KEYWORDS):
        score += 18
    elif _contains_any_keyword(body_text_for_scoring, A_SHARE_DIRECT_EVENT_KEYWORDS):
        score += 8

    category = _collapse_whitespace(news_item.get("category"))
    importance = _collapse_whitespace(news_item.get("importance"))
    if category == "company_announcement":
        score += 15
    if importance == "high":
        score += 12
    elif importance == "medium":
        score += 6

    if _contains_any_keyword(title, A_SHARE_BROAD_CONTEXT_KEYWORDS):
        score -= 35

    if title_alias_matches and _contains_any_keyword(title, A_SHARE_ENUMERATION_MARKERS):
        score -= 20

    if (
        not title_alias_matches
        and not title_has_symbol
        and not title_has_company_name
        and (body_alias_matches or body_has_symbol or body_has_company_name)
    ):
        score -= 25

    if not title_alias_matches and not body_alias_matches and not title_has_symbol and not body_has_symbol:
        score -= 25

    return max(0, min(100, score))


def _is_high_confidence_a_share_news_item(
    news_item: Dict[str, Any],
    symbol: str,
    company_name: Optional[str],
) -> bool:
    """判断是否属于可提前停止回退的高置信度公司直指新闻。"""
    relevance_score = int(
        news_item.get("relevance_score", 0)
        or _calculate_a_share_news_relevance(news_item, symbol, company_name)
    )
    if relevance_score < HIGH_CONFIDENCE_A_SHARE_RELEVANCE_SCORE:
        return False

    title = _collapse_whitespace(news_item.get("title"))
    if not title:
        return False

    aliases = _get_company_aliases(company_name)
    symbol_clean = symbol.zfill(6)
    title_alias_matches = _find_matching_aliases(title, aliases)
    title_has_company_name = _text_contains_company_name(title, company_name)
    title_has_symbol = symbol_clean in title or symbol in title
    title_starts_with_alias = bool(title_alias_matches and _text_starts_with_any_alias(title, title_alias_matches))
    title_has_direct_event = _contains_any_keyword(title, A_SHARE_DIRECT_EVENT_KEYWORDS)
    title_has_broad_context = _contains_any_keyword(title, A_SHARE_BROAD_CONTEXT_KEYWORDS)
    title_has_enumeration = _contains_any_keyword(title, A_SHARE_ENUMERATION_MARKERS)
    category = _collapse_whitespace(news_item.get("category"))

    if title_has_broad_context or title_has_enumeration:
        return False

    if not (title_has_symbol or title_has_company_name or title_starts_with_alias):
        return False

    return title_has_direct_event or category == "company_announcement"


def _rank_a_share_news_items(
    news_list: List[Dict[str, Any]],
    symbol: str,
    company_name: Optional[str],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """按公司直指度与事件相关性对 A 股新闻排序。"""
    ranked_news = []

    for news in news_list:
        relevance_score = _calculate_a_share_news_relevance(news, symbol, company_name)
        if relevance_score <= 0:
            continue

        ranked_item = dict(news)
        ranked_item["relevance_score"] = relevance_score
        ranked_news.append(ranked_item)

    ranked_news.sort(
        key=lambda item: (
            item.get("relevance_score", 0),
            _parse_publish_time(item.get("publish_time")) or datetime(1970, 1, 1),
        ),
        reverse=True,
    )
    return ranked_news[:limit]


def _get_top_relevance_score(news_list: List[Dict[str, Any]]) -> int:
    """获取新闻列表的最高相关性评分。"""
    if not news_list:
        return 0
    return int(news_list[0].get("relevance_score", 0) or 0)


def _select_best_live_news_source(
    source_news_map: Dict[str, List[Dict[str, Any]]],
    live_source_plan: List[str],
) -> Optional[str]:
    """在实时新闻候选源之间选择最佳结果。"""
    best_source = None
    best_key = None

    for source in live_source_plan:
        ranked_news = source_news_map.get(source) or []
        if not ranked_news:
            continue

        source_key = (
            _get_top_relevance_score(ranked_news),
            len(ranked_news),
            -live_source_plan.index(source),
        )

        if best_key is None or source_key > best_key:
            best_source = source
            best_key = source_key

    return best_source


def _deduplicate_news_items(news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按标题去重新闻列表。"""
    seen_titles = set()
    deduplicated_news = []

    for news in news_list:
        title = _collapse_whitespace(news.get("title"))
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        deduplicated_news.append(news)

    return deduplicated_news


def _sort_news_by_time(news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按发布时间倒序排序新闻。"""
    return sorted(
        news_list,
        key=lambda item: _parse_publish_time(item.get("publish_time")) or datetime.min,
        reverse=True,
    )


def _summarize_news_item(news_item: Dict[str, Any]) -> str:
    """获取新闻摘要，优先使用结构化摘要，其次回退到正文截断。"""
    summary = _collapse_whitespace(news_item.get("summary"))
    if summary:
        return summary

    content = _collapse_whitespace(news_item.get("content"))
    if not content:
        return ""

    if len(content) <= 160:
        return content
    return content[:160] + "..."


def _format_news_item(news_item: Dict[str, Any]) -> str:
    """格式化单条新闻为结构化 Markdown。"""
    title = _collapse_whitespace(news_item.get("title")) or "无标题"
    url = _collapse_whitespace(news_item.get("url"))
    source = _collapse_whitespace(news_item.get("source")) or _get_source_display_name(
        _collapse_whitespace(news_item.get("data_source"))
    )
    summary = _summarize_news_item(news_item)
    category = CATEGORY_DISPLAY_NAMES.get(_collapse_whitespace(news_item.get("category")), "其他")
    sentiment = SENTIMENT_DISPLAY_NAMES.get(_collapse_whitespace(news_item.get("sentiment")), "中性")
    importance = IMPORTANCE_DISPLAY_NAMES.get(_collapse_whitespace(news_item.get("importance")), "中")
    keywords = _coerce_keywords(news_item.get("keywords"))

    if url:
        lines = [f"- [**{title}**]({url})"]
    else:
        lines = [f"- **{title}**"]

    lines.append(f"  - 时间: {_format_publish_time(news_item.get('publish_time'))} | 来源: {source}")

    if summary:
        lines.append(f"  - 摘要: {summary}")

    lines.append(f"  - 类别: {category} | 情绪: {sentiment} | 重要性: {importance}")

    if keywords:
        lines.append(f"  - 关键词: {', '.join(keywords[:8])}")

    return "\n".join(lines)


def _format_news_section(news_list: List[Dict[str, Any]], section_title: str, source_note: str = "") -> str:
    """将新闻列表格式化为 Markdown 章节。"""
    if not news_list:
        return ""

    header = f"## {section_title}"
    if source_note:
        header += f"\n**说明**: {source_note}"

    news_items = "\n".join(_format_news_item(news) for news in news_list)
    return f"{header}\n{news_items}"


def _query_news_from_database(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    从 MongoDB 数据库查询新闻，并按启用的数据源聚合结果。

    Args:
        symbol: 股票代码（6位代码，如 000001）
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回数量限制

    Returns:
        包含新闻列表、启用数据源和命中数据源的字典
    """
    enabled_sources = _get_a_share_enabled_sources()

    try:
        from app.core.database import get_mongo_db_sync

        db = get_mongo_db_sync()
        collection = db.stock_news

        logger.info(f"📊 [新闻数据库查询] 数据源优先级: {enabled_sources}")

        query = {
            "symbol": symbol,
            "data_source": {"$in": enabled_sources},
            "publish_time": {
                "$gte": start_date,
                "$lte": end_date,
            },
        }

        raw_news = list(
            collection.find(query).sort("publish_time", -1).limit(max(limit * max(len(enabled_sources), 1), limit))
        )

        if not raw_news:
            logger.info(f"⚠️ [新闻数据库查询] 所有数据源都没有 {symbol} 的新闻数据")
            return {
                "news": [],
                "enabled_sources": enabled_sources,
                "used_sources": [],
            }

        priority_map = {source: index for index, source in enumerate(enabled_sources)}
        raw_news.sort(
            key=lambda item: (
                _parse_publish_time(item.get("publish_time")) or datetime(1970, 1, 1),
                -priority_map.get(item.get("data_source"), 999),
            ),
            reverse=True,
        )

        unique_news = _deduplicate_news_items(raw_news)[:limit]
        used_sources = []
        for news in unique_news:
            data_source = _collapse_whitespace(news.get("data_source"))
            if data_source and data_source not in used_sources:
                used_sources.append(data_source)

        logger.info(
            f"✅ [新闻数据库查询] 聚合到 {len(unique_news)} 条新闻，命中数据源: {used_sources or '无'}"
        )
        return {
            "news": unique_news,
            "enabled_sources": enabled_sources,
            "used_sources": used_sources,
        }

    except Exception as exc:
        logger.error(f"❌ [新闻数据库查询] 查询失败: {exc}")
        return {
            "news": [],
            "enabled_sources": enabled_sources,
            "used_sources": [],
        }


def _run_async_in_thread(coroutine_factory: Callable[[], Any], timeout: float = 30.0) -> Any:
    """在独立线程中执行异步协程，避免事件循环冲突。"""

    def _runner() -> Any:
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coroutine_factory())
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_runner)
        return future.result(timeout=timeout)


def _fetch_tushare_news_live(
    symbol: str,
    company_name: Optional[str],
    start_date: datetime,
    end_date: datetime,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """从 Tushare 直接拉取指定时间窗口的多源实时新闻。"""
    logger.info(
        f"📰 [统一新闻工具] 尝试 Tushare 实时新闻: symbol={symbol}, "
        f"company_name={company_name or '-'}, window={start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}"
    )

    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] 初始化 Tushare provider 失败: {exc}")
        return []

    if not provider or not provider.is_available() or provider.api is None:
        logger.info("⚠️ [统一新闻工具] Tushare provider 不可用，跳过付费增强链路")
        return []

    start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    fetch_limit = max(limit * 4, 40)
    collected_news: List[Dict[str, Any]] = []

    for source_code in TUSHARE_LIVE_SOURCES:
        try:
            logger.debug(f"📰 [统一新闻工具] Tushare 尝试新闻源: {source_code}")
            news_df = provider.api.news(
                src=source_code,
                start_date=start_date_str,
                end_date=end_date_str,
            )
        except Exception as exc:
            error_text = str(exc).lower()
            if any(keyword in error_text for keyword in ["权限", "permission", "unauthorized", "access denied", "积分", "point"]):
                logger.warning(f"⚠️ [统一新闻工具] Tushare 新闻权限不可用，跳过付费增强链路: {exc}")
                return []
            logger.debug(f"⚠️ [统一新闻工具] Tushare 新闻源 {source_code} 拉取失败: {exc}")
            continue

        if news_df is None or news_df.empty:
            logger.info(f"📰 [统一新闻工具] Tushare 新闻源 {source_code} 未返回数据")
            continue

        raw_row_count = 0
        try:
            raw_row_count = int(len(news_df))
        except Exception:
            raw_row_count = 0

        process_limit = max(fetch_limit, raw_row_count) if raw_row_count else fetch_limit
        if raw_row_count > fetch_limit * 2:
            logger.info(
                f"📰 [统一新闻工具] Tushare 新闻源 {source_code} 原始返回 {raw_row_count} 条，"
                f"按全量扫描避免公司相关新闻落在截断范围之外"
            )

        processed_news = provider._process_tushare_news(  # type: ignore[attr-defined]
            news_df,
            source_code,
            symbol=None,
            limit=process_limit,
        )
        relevant_news = [
            news
            for news in processed_news
            if _is_relevant_a_share_news(news, symbol, company_name)
        ]

        if relevant_news:
            collected_news.extend(relevant_news)
            logger.info(
                f"📰 [统一新闻工具] Tushare 新闻源 {source_code} 命中 {len(relevant_news)} 条相关候选"
            )
        else:
            logger.info(
                f"📰 [统一新闻工具] Tushare 新闻源 {source_code} 有原始数据，但未命中目标公司相关候选"
            )

        if len(_deduplicate_news_items(collected_news)) >= limit * 2:
            break

    if not collected_news:
        logger.info("📰 [统一新闻工具] Tushare 实时链路未获取到可用候选")
        return []

    filtered_news = _filter_news_by_date_range(_deduplicate_news_items(collected_news), start_date, end_date)
    final_news = _sort_news_by_time(filtered_news)[:limit]
    logger.info(f"📰 [统一新闻工具] Tushare 实时链路最终返回 {len(final_news)} 条新闻")
    return final_news


def _fetch_akshare_news_live(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """从 AKShare 拉取结构化新闻，并严格按分析日期窗口过滤。"""
    logger.info(
        f"📰 [统一新闻工具] 尝试 AKShare 实时新闻: symbol={symbol}, "
        f"window={start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}"
    )

    try:
        from tradingagents.dataflows.providers.china.akshare import AKShareProvider

        provider = AKShareProvider()
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] 初始化 AKShare provider 失败: {exc}")
        return []

    if not provider.is_available():
        logger.info("⚠️ [统一新闻工具] AKShare provider 不可用，跳过免费回退链路")
        return []

    fetch_limit = max(limit * 5, 50)

    async def _get_news() -> Any:
        return await provider.get_stock_news(symbol=symbol, limit=fetch_limit)

    try:
        news_list = _run_async_in_thread(_get_news, timeout=30.0) or []
    except concurrent.futures.TimeoutError:
        logger.warning("⚠️ [统一新闻工具] AKShare 新闻获取超时，跳过免费回退链路")
        return []
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] AKShare 新闻获取失败: {exc}")
        return []

    if not isinstance(news_list, list):
        logger.info("📰 [统一新闻工具] AKShare 实时链路返回了非列表结果，视为无效")
        return []

    filtered_news = _filter_news_by_date_range(news_list, start_date, end_date)
    final_news = _sort_news_by_time(_deduplicate_news_items(filtered_news))[:limit]
    logger.info(f"📰 [统一新闻工具] AKShare 实时链路最终返回 {len(final_news)} 条新闻")
    return final_news


def _fetch_google_news_candidates(
    query: str,
    start_date_str: str,
    end_date_str: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """从 Google News 抓取结构化候选新闻。"""
    try:
        from tradingagents.dataflows.news.google_news import getNewsData
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] 初始化 Google 新闻抓取失败: {exc}")
        return []

    try:
        raw_results = getNewsData(query.replace(" ", "+"), start_date_str, end_date_str)
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] Google 新闻抓取失败: {exc}")
        return []

    news_items = []
    for index, news in enumerate(raw_results[:limit]):
        news_items.append(
            {
                "title": _collapse_whitespace(news.get("title")),
                "summary": _collapse_whitespace(news.get("snippet")),
                "content": _collapse_whitespace(news.get("snippet")),
                "publish_time": _collapse_whitespace(news.get("date")),
                "source": _collapse_whitespace(news.get("source")) or "Google新闻",
                "url": _collapse_whitespace(news.get("link")),
                "category": "other",
                "sentiment": "neutral",
                "importance": "medium",
                "data_source": "google",
                "relevance_score": max(35, 95 - index),
            }
        )

    return _deduplicate_news_items(news_items)


def _fetch_finnhub_news_candidates(
    ticker: str,
    start_date_str: str,
    end_date_str: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """从 Finnhub 本地缓存中构建结构化新闻候选。"""
    try:
        from tradingagents.config.config_manager import config_manager
        from tradingagents.dataflows.providers.us import get_data_in_range
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] 初始化 Finnhub 新闻读取失败: {exc}")
        return []

    try:
        raw_results = get_data_in_range(
            ticker,
            start_date_str,
            end_date_str,
            "news_data",
            config_manager.get_data_dir(),
        )
    except Exception as exc:
        logger.warning(f"⚠️ [统一新闻工具] Finnhub 新闻读取失败: {exc}")
        return []

    if not raw_results:
        return []

    news_items: List[Dict[str, Any]] = []
    for day in sorted(raw_results.keys(), reverse=True):
        day_entries = raw_results.get(day) or []
        for entry in day_entries:
            news_items.append(
                {
                    "title": _collapse_whitespace(entry.get("headline")),
                    "summary": _collapse_whitespace(entry.get("summary")),
                    "content": _collapse_whitespace(entry.get("summary")),
                    "publish_time": day,
                    "source": _collapse_whitespace(entry.get("source")) or "Finnhub",
                    "url": _collapse_whitespace(entry.get("url")),
                    "category": "other",
                    "sentiment": "neutral",
                    "importance": "medium",
                    "data_source": "finnhub",
                }
            )
            if len(news_items) >= limit:
                return _deduplicate_news_items(news_items)

    return _deduplicate_news_items(news_items)


def _normalize_news_title_key(title: Any) -> str:
    """标准化新闻标题键，用于标题级去重。"""
    return _collapse_whitespace(title).lower()


def _collect_unique_text_values(*values: Any) -> List[str]:
    """合并多个文本或文本列表，保持去重后的原始顺序。"""
    collected: List[str] = []
    seen = set()

    for value in values:
        if value is None:
            continue

        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            text = _collapse_whitespace(candidate)
            if not text or text in seen:
                continue
            seen.add(text)
            collected.append(text)

    return collected


def _build_news_id(news_item: Dict[str, Any]) -> str:
    """为标题聚合后的新闻生成稳定的 news_id。"""
    title_key = _normalize_news_title_key(news_item.get("title"))
    if not title_key:
        title_key = _collapse_whitespace(news_item.get("url")) or "untitled-news"
    digest = hashlib.md5(title_key.encode("utf-8")).hexdigest()[:10]
    return f"news_{digest}"


def _get_news_priority_key(news_item: Dict[str, Any]) -> Tuple[int, int, int, datetime]:
    """获取新闻聚合时的优先级键。"""
    return (
        int(news_item.get("relevance_score", 0) or 0),
        1 if _collapse_whitespace(news_item.get("content")) else 0,
        1 if _collapse_whitespace(news_item.get("summary")) else 0,
        _parse_publish_time(news_item.get("publish_time")) or datetime.min,
    )


def _normalize_news_cluster_item(news_item: Dict[str, Any]) -> Dict[str, Any]:
    """标准化聚合候选新闻项。"""
    normalized_item = dict(news_item)
    normalized_item["title"] = _collapse_whitespace(normalized_item.get("title"))
    normalized_item["summary"] = _collapse_whitespace(normalized_item.get("summary"))
    normalized_item["content"] = _collapse_whitespace(normalized_item.get("content"))
    normalized_item["source"] = _collapse_whitespace(normalized_item.get("source"))
    normalized_item["data_source"] = _collapse_whitespace(normalized_item.get("data_source"))
    normalized_item["url"] = _collapse_whitespace(normalized_item.get("url"))
    normalized_item["source_variants"] = _collect_unique_text_values(
        normalized_item.get("source_variants"),
        normalized_item.get("source"),
    )
    normalized_item["data_source_variants"] = _collect_unique_text_values(
        normalized_item.get("data_source_variants"),
        normalized_item.get("data_source"),
    )
    normalized_item["origin_paths"] = _collect_unique_text_values(
        normalized_item.get("origin_paths"),
        normalized_item.get("origin_path"),
    )
    normalized_item["url_variants"] = _collect_unique_text_values(
        normalized_item.get("url_variants"),
        normalized_item.get("url"),
    )
    normalized_item["duplicate_count"] = int(normalized_item.get("duplicate_count", 1) or 1)
    normalized_item["news_id"] = _build_news_id(normalized_item)
    return normalized_item


def _merge_news_cluster_items(
    existing_item: Dict[str, Any],
    incoming_item: Dict[str, Any],
) -> Dict[str, Any]:
    """合并同标题新闻，保留更优主记录并聚合来源信息。"""
    normalized_existing = _normalize_news_cluster_item(existing_item)
    normalized_incoming = _normalize_news_cluster_item(incoming_item)

    preferred_item = normalized_incoming
    fallback_item = normalized_existing
    if _get_news_priority_key(normalized_existing) >= _get_news_priority_key(normalized_incoming):
        preferred_item = normalized_existing
        fallback_item = normalized_incoming

    merged_item = dict(preferred_item)
    merged_item["source_variants"] = _collect_unique_text_values(
        preferred_item.get("source_variants"),
        fallback_item.get("source_variants"),
    )
    merged_item["data_source_variants"] = _collect_unique_text_values(
        preferred_item.get("data_source_variants"),
        fallback_item.get("data_source_variants"),
    )
    merged_item["origin_paths"] = _collect_unique_text_values(
        preferred_item.get("origin_paths"),
        fallback_item.get("origin_paths"),
    )
    merged_item["url_variants"] = _collect_unique_text_values(
        preferred_item.get("url_variants"),
        fallback_item.get("url_variants"),
    )
    merged_item["duplicate_count"] = int(preferred_item.get("duplicate_count", 1) or 1) + int(
        fallback_item.get("duplicate_count", 1) or 1
    )

    if not merged_item.get("summary") and fallback_item.get("summary"):
        merged_item["summary"] = fallback_item["summary"]
    if len(_collapse_whitespace(fallback_item.get("content"))) > len(_collapse_whitespace(merged_item.get("content"))):
        merged_item["content"] = fallback_item.get("content")
    if not merged_item.get("url") and fallback_item.get("url"):
        merged_item["url"] = fallback_item.get("url")

    merged_item["news_id"] = _build_news_id(merged_item)
    return merged_item


def _merge_news_items_by_title(
    news_list: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """按标题聚合新闻并保留来源聚合信息。"""
    clusters: Dict[str, Dict[str, Any]] = {}

    for news_item in news_list:
        title_key = _normalize_news_title_key(news_item.get("title"))
        if not title_key:
            continue

        normalized_item = _normalize_news_cluster_item(news_item)
        existing_item = clusters.get(title_key)
        if existing_item is None:
            clusters[title_key] = normalized_item
        else:
            clusters[title_key] = _merge_news_cluster_items(existing_item, normalized_item)

    merged_items = list(clusters.values())
    merged_items.sort(key=_get_news_priority_key, reverse=True)
    return merged_items[:limit]


def _get_news_source_signal(news_item: Dict[str, Any]) -> Tuple[str, str]:
    """根据来源判断新闻信号强度。"""
    source_text = " ".join(
        _collect_unique_text_values(news_item.get("source_variants"), news_item.get("source"))
    )

    if any(keyword in source_text for keyword in HIGH_SIGNAL_NEWS_SOURCE_KEYWORDS):
        return "高", "来源包含公告或主流财经媒体"

    if any(keyword in source_text for keyword in LOW_SIGNAL_NEWS_SOURCE_KEYWORDS):
        return "低", "来源偏社区或弱信号渠道"

    return "中", "来源可作为线索，但仍需结合标题与细节判断"


def _get_detail_recommendation(news_item: Dict[str, Any]) -> Tuple[str, str]:
    """给出是否建议继续查看新闻明细的判断。"""
    title = _collapse_whitespace(news_item.get("title"))
    category = _collapse_whitespace(news_item.get("category"))
    relevance_score = int(news_item.get("relevance_score", 0) or 0)
    source_signal, source_reason = _get_news_source_signal(news_item)

    if _contains_any_keyword(title, A_SHARE_BROAD_CONTEXT_KEYWORDS):
        if _contains_any_keyword(title, A_SHARE_ENUMERATION_MARKERS):
            return "可暂不展开", "更像宏观提醒或多公司枚举新闻"
        return "按需查看", "更像宏观背景或日历提醒"

    if category == "company_announcement" or _contains_any_keyword(title, A_SHARE_DIRECT_EVENT_KEYWORDS):
        return "建议查看", "涉及公告或直接公司事件"

    if relevance_score >= HIGH_CONFIDENCE_A_SHARE_RELEVANCE_SCORE:
        return "建议查看", "标题与目标公司高度相关"

    if source_signal == "高" and relevance_score >= 55:
        return "建议查看", source_reason

    if relevance_score >= 45:
        return "按需查看", "标题具备一定研究相关性，可在需要时展开细节"

    return "可暂不展开", "更像背景提及或弱相关线索"


def _annotate_headline_items(news_list: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    """为标题候选补充 news_id、来源信号和明细建议。"""
    annotated_items = []
    for news_item in news_list[:limit]:
        annotated_item = _normalize_news_cluster_item(news_item)
        source_signal, source_signal_reason = _get_news_source_signal(annotated_item)
        detail_action, detail_reason = _get_detail_recommendation(annotated_item)
        annotated_item["source_signal"] = source_signal
        annotated_item["source_signal_reason"] = source_signal_reason
        annotated_item["detail_action"] = detail_action
        annotated_item["detail_reason"] = detail_reason
        annotated_items.append(annotated_item)

    return annotated_items


def _format_variant_values(values: List[str], fallback: str) -> str:
    """格式化候选聚合值。"""
    cleaned_values = _collect_unique_text_values(values)
    return " / ".join(cleaned_values[:4]) if cleaned_values else fallback


def _format_headline_item(news_item: Dict[str, Any]) -> str:
    """格式化新闻标题候选。"""
    title = _collapse_whitespace(news_item.get("title")) or "无标题"
    source_text = _format_variant_values(
        news_item.get("source_variants") or [],
        _collapse_whitespace(news_item.get("source")) or "未知来源",
    )
    data_source_text = _format_variant_values(
        [_get_source_display_name(source) for source in news_item.get("data_source_variants") or []],
        _get_source_display_name(_collapse_whitespace(news_item.get("data_source"))),
    )

    lines = [f"- [news_id: {news_item.get('news_id')}] **{title}**"]
    lines.append(
        f"  - 时间: {_format_publish_time(news_item.get('publish_time'))} | 来源: {source_text} | 数据源: {data_source_text}"
    )
    lines.append(
        f"  - 相关性: {int(news_item.get('relevance_score', 0) or 0)} | 来源信号: {news_item.get('source_signal')} | 明细建议: {news_item.get('detail_action')}（{news_item.get('detail_reason')}）"
    )

    if int(news_item.get("duplicate_count", 1) or 1) > 1:
        lines.append(f"  - 去重合并: 已合并 {int(news_item.get('duplicate_count', 1) or 1)} 条同标题新闻")

    return "\n".join(lines)


def _format_headline_section(news_list: List[Dict[str, Any]], section_title: str, source_note: str = "") -> str:
    """将标题候选格式化为 Markdown 章节。"""
    if not news_list:
        return ""

    header = f"## {section_title}"
    if source_note:
        header += f"\n**说明**: {source_note}"

    headline_items = "\n".join(_format_headline_item(news) for news in news_list)
    return f"{header}\n{headline_items}"


def _format_news_detail_item(news_item: Dict[str, Any]) -> str:
    """格式化单条新闻明细。"""
    source_text = _format_variant_values(
        news_item.get("source_variants") or [],
        _collapse_whitespace(news_item.get("source")) or "未知来源",
    )
    data_source_text = _format_variant_values(
        [_get_source_display_name(source) for source in news_item.get("data_source_variants") or []],
        _get_source_display_name(_collapse_whitespace(news_item.get("data_source"))),
    )
    summary = _summarize_news_item(news_item)
    content = _collapse_whitespace(news_item.get("content"))
    keywords = _coerce_keywords(news_item.get("keywords"))
    url = _collapse_whitespace(news_item.get("url"))

    lines = [f"## [news_id: {news_item.get('news_id')}] {_collapse_whitespace(news_item.get('title')) or '无标题'}"]
    lines.append(
        f"- 时间: {_format_publish_time(news_item.get('publish_time'))} | 来源: {source_text} | 数据源: {data_source_text}"
    )
    lines.append(
        f"- 相关性: {int(news_item.get('relevance_score', 0) or 0)} | 来源信号: {news_item.get('source_signal')} | 明细建议: {news_item.get('detail_action')}"
    )

    if summary:
        lines.append(f"- 摘要: {summary}")

    if content and content != summary:
        lines.append(f"- 正文要点: {content}")
    else:
        lines.append("- 正文要点: 工具结果未提供更长正文，当前只能基于标题与摘要展开分析。")

    if keywords:
        lines.append(f"- 关键词: {', '.join(keywords[:8])}")

    if int(news_item.get("duplicate_count", 1) or 1) > 1:
        lines.append(
            f"- 去重来源: 已合并 {int(news_item.get('duplicate_count', 1) or 1)} 条同标题新闻，来源包括 {source_text}"
        )

    if url:
        lines.append(f"- 链接: {url}")

    return "\n".join(lines)


def _parse_requested_news_ids(news_ids: str) -> List[str]:
    """解析 detail 工具传入的 news_id 列表。"""
    normalized_ids = news_ids or ""
    for separator in ["，", "；", ";", "|", "\n", "\t"]:
        normalized_ids = normalized_ids.replace(separator, ",")

    requested_ids = []
    for raw_news_id in normalized_ids.split(","):
        news_id = _collapse_whitespace(raw_news_id)
        if news_id and news_id not in requested_ids:
            requested_ids.append(news_id)

    return requested_ids


def _build_a_share_news_bundle(ticker: str, curr_date: str, limit: int = 20) -> Dict[str, Any]:
    """构建 A 股新闻标题/明细候选集。"""
    start_date, end_date, start_date_str, end_date_str = _build_a_share_news_window(curr_date)
    clean_ticker = _normalize_a_share_symbol(ticker)
    company_name = _get_company_name(clean_ticker)
    candidate_limit = max(limit * 4, 40)

    db_result = _query_news_from_database(
        symbol=clean_ticker,
        start_date=start_date,
        end_date=end_date,
        limit=candidate_limit,
    )
    enabled_sources = db_result.get("enabled_sources") or _get_a_share_enabled_sources()

    combined_candidates: List[Dict[str, Any]] = []
    db_news = _rank_a_share_news_items(
        db_result.get("news") or [],
        clean_ticker,
        company_name,
        limit=candidate_limit,
    )
    for news_item in db_news:
        candidate = dict(news_item)
        candidate["origin_path"] = "database"
        combined_candidates.append(candidate)

    live_source_plan = _build_a_share_live_source_plan(enabled_sources)
    logger.info(f"📰 [统一新闻工具] A股新闻候选构建实时回退链: {live_source_plan}")
    for live_source in live_source_plan:
        if live_source != "akshare":
            logger.info(f"📰 [统一新闻工具] 跳过非实时分析源: {live_source}")
            continue

        live_news = _fetch_akshare_news_live(
            symbol=clean_ticker,
            start_date=start_date,
            end_date=end_date,
            limit=candidate_limit,
        )

        ranked_live_news = _rank_a_share_news_items(
            live_news,
            clean_ticker,
            company_name,
            limit=candidate_limit,
        )
        logger.info(
            f"📰 [统一新闻工具] A股新闻候选源 {live_source} 排序后保留 {len(ranked_live_news)} 条新闻"
        )
        for news_item in ranked_live_news:
            candidate = dict(news_item)
            candidate["origin_path"] = f"{live_source}_live"
            combined_candidates.append(candidate)

    merged_candidates = _merge_news_items_by_title(combined_candidates, limit=candidate_limit)
    annotated_items = _annotate_headline_items(merged_candidates, limit=limit)

    return {
        "ticker": clean_ticker,
        "market_name": "中国A股",
        "analysis_date": curr_date,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "company_name": company_name,
        "items": annotated_items,
        "footer_note": _build_a_share_footer(enabled_sources),
    }


def _build_hk_news_bundle(ticker: str, curr_date: str, limit: int = 20) -> Dict[str, Any]:
    """构建港股新闻标题/明细候选集。"""
    _, _, start_date_str, end_date_str = _build_a_share_news_window(curr_date)
    google_candidates = _fetch_google_news_candidates(
        query=f"{ticker} 港股",
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        limit=max(limit * 3, 30),
    )
    merged_candidates = _merge_news_items_by_title(google_candidates, limit=max(limit * 3, 30))
    annotated_items = _annotate_headline_items(merged_candidates, limit=limit)

    return {
        "ticker": ticker,
        "market_name": "港股",
        "analysis_date": curr_date,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "company_name": ticker,
        "items": annotated_items,
        "footer_note": "---\n*港股标题候选当前来自 Google News 检索；若工具未提供更长正文，明细仅包含摘要与链接。*",
    }


def _build_us_news_bundle(ticker: str, curr_date: str, limit: int = 20) -> Dict[str, Any]:
    """构建美股新闻标题/明细候选集。"""
    _, _, start_date_str, end_date_str = _build_a_share_news_window(curr_date)
    finnhub_candidates = _fetch_finnhub_news_candidates(
        ticker=ticker,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        limit=max(limit * 2, 20),
    )
    for index, news_item in enumerate(finnhub_candidates):
        news_item.setdefault("relevance_score", max(40, 100 - index))

    google_candidates = _fetch_google_news_candidates(
        query=f"{ticker} stock news",
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        limit=max(limit * 2, 20),
    )
    for index, news_item in enumerate(google_candidates):
        news_item.setdefault("relevance_score", max(35, 90 - index))

    merged_candidates = _merge_news_items_by_title(
        finnhub_candidates + google_candidates,
        limit=max(limit * 3, 30),
    )
    annotated_items = _annotate_headline_items(merged_candidates, limit=limit)

    return {
        "ticker": ticker,
        "market_name": "美股",
        "analysis_date": curr_date,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "company_name": ticker,
        "items": annotated_items,
        "footer_note": "---\n*美股标题候选优先使用 Finnhub 缓存和 Google News 检索；若工具未提供更长正文，明细仅包含摘要与链接。*",
    }


def _build_stock_news_bundle(ticker: str, curr_date: str, limit: int = 20) -> Dict[str, Any]:
    """按市场构建统一新闻候选集。"""
    from tradingagents.utils.stock_utils import StockUtils

    market_info = StockUtils.get_market_info(ticker)
    curr_date_clean = _normalize_analysis_date(curr_date)

    if market_info["is_china"]:
        return _build_a_share_news_bundle(ticker, curr_date_clean, limit=limit)
    if market_info["is_hk"]:
        return _build_hk_news_bundle(ticker, curr_date_clean, limit=limit)
    if market_info["is_us"]:
        return _build_us_news_bundle(ticker, curr_date_clean, limit=limit)

    _, _, start_date_str, end_date_str = _build_a_share_news_window(curr_date_clean)
    return {
        "ticker": ticker,
        "market_name": market_info.get("market_name", "未知市场"),
        "analysis_date": curr_date_clean,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "company_name": ticker,
        "items": [],
        "footer_note": "",
    }


def _build_a_share_footer(enabled_sources: List[str]) -> str:
    """生成 A 股新闻工具的尾部说明。"""
    live_path = _build_a_share_live_source_plan(enabled_sources)
    live_path_text = " → ".join(_get_live_source_display_name(source) for source in live_path)
    priority_text = " > ".join(_build_a_share_analysis_priority(enabled_sources))

    footer_lines = [
        "---",
        f"*A股优先路径: 数据库缓存{' → ' + live_path_text if live_path_text else ''}*",
        f"*当前分析优先级: {priority_text}*",
        "*Tushare 新闻源当前仅用于同步入库，不参与实时新闻分析调用。*",
    ]
    return "\n".join(footer_lines)


@tool
@register_tool(
    tool_id="get_stock_news_headlines_unified",
    name="统一股票新闻标题",
    description="获取股票新闻标题候选、来源判断和去重结果，供后续按需拉取明细",
    category="news",
    is_online=True,
    auto_register=True,
    capability_tags=["stock_news", "news_headlines", "news_articles", "company_news", "market_news", "news", "event_driven"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["news_headline_screening", "news_deduplication", "company_event_discovery"],
)
def get_stock_news_headlines_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"],
    limit: Annotated[int, "返回的标题候选数量，默认12"] = 12,
) -> str:
    """获取去重后的股票新闻标题候选，支持 A 股、港股、美股，返回标题、来源判断和去重结果。

    Args:
        ticker: 股票代码（支持 A 股、港股、美股）
        curr_date: 当前日期，格式 YYYY-MM-DD
        limit: 返回的标题候选数量，默认 12（实际限制在 1-30 之间）

    Returns:
        str: Markdown 格式的新闻标题候选报告，内容包括 —
            # {ticker} 新闻标题候选：报告主标题
            **股票类型**: 市场类型名称
            **分析日期**: 实际使用的分析日期
            **新闻时间范围**: 起始日期 至 结束日期
            ## 去重后的新闻标题：标题候选列表（每条含 news_id、标题、来源、时间、摘要等）
            底部说明：来源路径与下一步操作提示
        无新闻时返回包含 "当前未获取到可用新闻标题" 的 Markdown 字符串
        异常时返回以 "统一新闻标题工具执行失败" 开头的错误说明字符串
    """
    try:
        bundle = _build_stock_news_bundle(ticker, curr_date, limit=max(1, min(limit, 30)))
        news_items = bundle.get("items") or []

        if not news_items:
            return (
                f"# {ticker} 新闻标题候选\n\n"
                f"**股票类型**: {bundle.get('market_name')}\n"
                f"**分析日期**: {bundle.get('analysis_date')}\n"
                f"**新闻时间范围**: {bundle.get('start_date')} 至 {bundle.get('end_date')}\n\n"
                "## 新闻标题候选\n当前未获取到可用新闻标题。"
            )

        result_parts = [
            f"# {ticker} 新闻标题候选",
            "",
            f"**股票类型**: {bundle.get('market_name')}",
            f"**分析日期**: {bundle.get('analysis_date')}",
            f"**新闻时间范围**: {bundle.get('start_date')} 至 {bundle.get('end_date')}",
            "",
            _format_headline_section(
                news_items,
                "去重后的新闻标题",
                "先根据 news_id、来源、相关性和明细建议筛选事件，再调用 get_stock_news_details_unified 拉取需要深挖的新闻明细。",
            ),
            "",
            "*下一步：将选中的 news_id（可逗号分隔多个）传给 get_stock_news_details_unified，获取摘要与正文要点。*",
        ]

        footer_note = _collapse_whitespace(bundle.get("footer_note"))
        if footer_note:
            result_parts.extend(["", bundle.get("footer_note")])

        return "\n".join(part for part in result_parts if part is not None)

    except Exception as exc:
        error_msg = f"统一新闻标题工具执行失败: {exc}"
        logger.error(f"❌ [统一新闻标题工具] {error_msg}")
        return error_msg


@tool
@register_tool(
    tool_id="get_stock_news_details_unified",
    name="统一股票新闻明细",
    description="根据标题工具返回的 news_id 获取股票新闻摘要、正文要点和来源明细",
    category="news",
    is_online=True,
    auto_register=True,
    capability_tags=["stock_news", "news_details", "news_articles", "company_news", "news_summary", "news", "event_driven"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["news_detail_review", "news_content_analysis", "event_investigation"],
)
def get_stock_news_details_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"],
    news_ids: Annotated[str, "要查看明细的 news_id，可使用逗号分隔多个 ID"],
) -> str:
    """根据 news_id 获取股票新闻明细，返回新闻摘要、正文要点和来源明细。

    Args:
        ticker: 股票代码（支持 A 股、港股、美股）
        curr_date: 当前日期，格式 YYYY-MM-DD
        news_ids: 要查看明细的 news_id，可使用逗号分隔多个 ID

    Returns:
        str: Markdown 格式的新闻明细报告，内容包括 —
            # {ticker} 新闻明细：报告主标题
            **股票类型**: 市场类型名称
            **分析日期**: 实际使用的分析日期
            **新闻时间范围**: 起始日期 至 结束日期
            新闻明细正文：每条新闻的摘要、正文要点、来源链接等（按传入 news_ids 顺序）
            底部说明：可选，未找到的 news_id 提示与来源说明
        未提供有效 news_id 时返回以 "统一新闻明细工具执行失败" 开头的错误说明字符串
        未找到请求的 news_id 时返回包含未找到 ID 列表的 Markdown 字符串
        异常时返回以 "统一新闻明细工具执行失败" 开头的错误说明字符串
    """
    requested_ids = _parse_requested_news_ids(news_ids)
    if not requested_ids:
        return "统一新闻明细工具执行失败: 未提供有效的 news_id。"

    try:
        bundle = _build_stock_news_bundle(
            ticker,
            curr_date,
            limit=max(len(requested_ids) * 12, 60),
        )
        item_map = {item.get("news_id"): item for item in bundle.get("items") or []}
        selected_items = [item_map[news_id] for news_id in requested_ids if news_id in item_map]
        missing_ids = [news_id for news_id in requested_ids if news_id not in item_map]

        if not selected_items:
            return (
                f"# {ticker} 新闻明细\n\n"
                f"**股票类型**: {bundle.get('market_name')}\n"
                f"**分析日期**: {bundle.get('analysis_date')}\n\n"
                f"未找到请求的 news_id: {', '.join(missing_ids)}。可能原因是实时新闻已刷新，请先重新调用 get_stock_news_headlines_unified。"
            )

        result_parts = [
            f"# {ticker} 新闻明细",
            "",
            f"**股票类型**: {bundle.get('market_name')}",
            f"**分析日期**: {bundle.get('analysis_date')}",
            f"**新闻时间范围**: {bundle.get('start_date')} 至 {bundle.get('end_date')}",
            "",
            "\n\n".join(_format_news_detail_item(item) for item in selected_items),
        ]

        if missing_ids:
            result_parts.extend(
                [
                    "",
                    f"*未找到以下 news_id：{', '.join(missing_ids)}。实时新闻可能已刷新，请先重新调用 get_stock_news_headlines_unified。*",
                ]
            )

        footer_note = bundle.get("footer_note")
        if footer_note:
            result_parts.extend(["", footer_note])

        return "\n".join(part for part in result_parts if part is not None)

    except Exception as exc:
        error_msg = f"统一新闻明细工具执行失败: {exc}"
        logger.error(f"❌ [统一新闻明细工具] {error_msg}")
        return error_msg


@tool
@register_tool(
    tool_id="get_stock_news_unified",
    name="统一股票新闻",
    description="获取股票相关新闻（支持A股、港股、美股），结构化返回新闻标题、摘要、来源链接、情感倾向、重要性等字段",
    category="news",
    is_online=True,
    auto_register=True,
    capability_tags=["stock_news", "news", "news_articles", "company_news", "market_news", "event_driven", "market_sentiment"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["news_analysis", "company_event_review", "market_sentiment_collection"],
)
def get_stock_news_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的股票新闻工具
    自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        curr_date: 当前日期（格式：YYYY-MM-DD）

    Returns:
        str: 新闻分析报告
    """
    logger.info(f"📰 [统一新闻工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info["is_china"]
        is_hk = market_info["is_hk"]
        is_us = market_info["is_us"]

        logger.info(f"📰 [统一新闻工具] 股票类型: {market_info['market_name']}")

        curr_date_clean = _normalize_analysis_date(curr_date)
        start_date, end_date, start_date_str, end_date_str = _build_a_share_news_window(curr_date_clean)

        result_data = []
        footer_note = ""

        if is_china:
            logger.info(f"🇨🇳 [统一新闻工具] 处理A股新闻...")

            clean_ticker = _normalize_a_share_symbol(ticker)
            company_name = _get_company_name(clean_ticker)
            db_result = _query_news_from_database(
                symbol=clean_ticker,
                start_date=start_date,
                end_date=end_date,
                limit=20,
            )
            enabled_sources = db_result.get("enabled_sources") or _get_a_share_enabled_sources()
            footer_note = _build_a_share_footer(enabled_sources)

            db_news = _rank_a_share_news_items(
                db_result.get("news") or [],
                clean_ticker,
                company_name,
                limit=20,
            )
            if db_news:
                used_sources = db_result.get("used_sources") or []
                source_note = "命中来源: " + " / ".join(
                    f"{_get_source_display_name(source)}（数据库缓存）" for source in used_sources
                ) if used_sources else "命中来源: 数据库缓存"
                result_data.append(_format_news_section(db_news, "数据库缓存", source_note))
                logger.info(f"✅ [统一新闻工具] 从数据库缓存获取到 {len(db_news)} 条结构化新闻")
            else:
                live_source_plan = _build_a_share_live_source_plan(enabled_sources)
                logger.info(f"📰 [统一新闻工具] A股实时新闻回退链: {live_source_plan}")
                live_source_candidates: Dict[str, List[Dict[str, Any]]] = {}
                selected_live_source = None

                for live_source in live_source_plan:
                    logger.info(f"📰 [统一新闻工具] 开始尝试实时新闻源: {live_source}")
                    if live_source != "akshare":
                        logger.info(f"📰 [统一新闻工具] 跳过非实时分析源: {live_source}")
                        continue

                    live_news = _fetch_akshare_news_live(
                        symbol=clean_ticker,
                        start_date=start_date,
                        end_date=end_date,
                        limit=20,
                    )

                    ranked_live_news = _rank_a_share_news_items(
                        live_news,
                        clean_ticker,
                        company_name,
                        limit=20,
                    )
                    if not ranked_live_news:
                        logger.info(
                            f"📰 [统一新闻工具] {live_source} 实时链路无可用候选，继续回退"
                        )
                        continue

                    live_source_candidates[live_source] = ranked_live_news
                    logger.info(
                        f"✅ [统一新闻工具] {live_source} 实时链路命中 {len(ranked_live_news)} 条新闻，"
                        f"最高相关性评分: {_get_top_relevance_score(ranked_live_news)}"
                    )

                    if _is_high_confidence_a_share_news_item(
                        ranked_live_news[0],
                        clean_ticker,
                        company_name,
                    ):
                        selected_live_source = live_source
                        logger.info(
                            f"✅ [统一新闻工具] {live_source} 命中高置信度公司直指新闻，停止继续回退"
                        )
                        break

                if selected_live_source is None:
                    selected_live_source = _select_best_live_news_source(live_source_candidates, live_source_plan)
                    logger.info(
                        f"📰 [统一新闻工具] A股实时新闻最佳候选源: {selected_live_source or '无'}"
                    )

                if selected_live_source:
                    live_news = live_source_candidates[selected_live_source]
                    live_section_title = "AKShare东方财富新闻（实时）"
                    live_note = "已按分析日期窗口严格过滤，并按公司直指度与事件相关性择优排序展示"

                    result_data.append(_format_news_section(live_news, live_section_title, live_note))
                else:
                    result_data.append("## A股新闻\n未获取到符合分析日期窗口的新闻数据。")

        elif is_hk:
            # 港股：使用Google新闻
            logger.info(f"🇭🇰 [统一新闻工具] 处理港股新闻...")

            try:
                search_query = f"{ticker} 港股"

                from tradingagents.dataflows.interface import get_google_news
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(get_google_news, search_query, curr_date_clean)
                    try:
                        news_data = future.result(timeout=30.0)  # 最多等待30秒
                        if news_data:
                            result_data.append(f"## Google新闻\n{news_data}")
                            logger.info(f"✅ 成功获取Google新闻")
                        else:
                            logger.warning(f"⚠️ Google新闻返回空结果")
                    except FutureTimeoutError:
                        logger.warning(f"⚠️ Google新闻获取超时（30秒），跳过Google新闻以避免阻塞流程")
                    except Exception as e:
                        logger.error(f"❌ Google新闻获取失败: {e}")
            except Exception as google_e:
                logger.error(f"❌ Google新闻获取异常: {google_e}")

        elif is_us:
            # 美股：使用Finnhub新闻和Google新闻
            logger.info(f"🇺🇸 [统一新闻工具] 处理美股新闻...")

            # 1. 获取Finnhub新闻
            try:
                from tradingagents.dataflows.interface import get_finnhub_news
                news_data = get_finnhub_news(ticker, start_date_str, end_date_str)
                if news_data:
                    result_data.append(f"## 美股新闻\n{news_data}")
            except Exception as e:
                logger.error(f"❌ Finnhub新闻获取失败: {e}")
                result_data.append(f"## 美股新闻\n获取失败: {e}")

            # 2. 获取Google新闻作为补充（带超时保护，避免阻塞整个流程）
            try:
                search_query = f"{ticker} stock news"

                from tradingagents.dataflows.interface import get_google_news
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(get_google_news, search_query, curr_date_clean)
                    try:
                        news_data = future.result(timeout=30.0)  # 最多等待30秒
                        if news_data:
                            result_data.append(f"## Google新闻\n{news_data}")
                            logger.info(f"✅ 成功获取Google新闻")
                        else:
                            logger.warning(f"⚠️ Google新闻返回空结果")
                    except FutureTimeoutError:
                        logger.warning(f"⚠️ Google新闻获取超时（30秒），跳过Google新闻以避免阻塞流程")
                    except Exception as e:
                        logger.error(f"❌ Google新闻获取失败: {e}")
            except Exception as google_e:
                logger.error(f"❌ Google新闻获取异常: {google_e}")

        if not result_data:
            result_data.append("## 新闻结果\n当前未获取到可用新闻数据。")

        # 组合所有数据
        combined_result = f"""# {ticker} 新闻分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date_clean}
**新闻时间范围**: {start_date_str} 至 {end_date_str}

{chr(10).join(result_data)}

{footer_note}
"""

        logger.info(f"📰 [统一新闻工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一新闻工具执行失败: {str(e)}"
        logger.error(f"❌ [统一新闻工具] {error_msg}")
        return error_msg

