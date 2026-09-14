"""
外部接口与数据源目录

为 Skill 生成器提供一份可维护的外部数据源能力目录，
用于按需求筛选 AKShare、Tushare、Google News、Finnhub 等来源，
避免把所有外部接口说明一次性注入提示词。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


ExternalSourceCatalog = Dict[str, Any]


EXTERNAL_DATA_SOURCE_CATALOG: List[ExternalSourceCatalog] = [
    {
        "source_id": "akshare",
        "display_name": "AKShare",
        "source_type": "python_library",
        "markets": ["CN", "HK", "US", "ETF", "macro"],
        "categories": ["market", "technical", "fundamentals", "news", "etf"],
        "preferred_for": [
            "A 股免费实时/历史行情补数",
            "东方财富新闻、盘口、板块、ETF 等公开数据",
            "没有稳定本地缓存时的在线降级",
        ],
        "interfaces": [
            "tradingagents.dataflows.providers.china.akshare.AKShareProvider",
            "provider.get_stock_news_sync(symbol)",
            "provider.get_historical_data(symbol, start_date, end_date)",
            "直接 import akshare as ak 调公开接口",
        ],
        "usage_examples": [
            "from tradingagents.dataflows.providers.china.akshare import get_akshare_provider",
            "provider = get_akshare_provider()",
            "news_df = provider.get_stock_news_sync(symbol, limit=10)",
            "# 或者直接 import akshare as ak 调公开免费接口",
        ],
        "constraints": [
            "字段名经常带中文列名，返回后要立刻标准化。",
            "不同接口返回结构不完全一致，不能假设所有字段长期稳定。",
            "适合做免费补数，但不适合把每个接口都当成严格契约。",
        ],
        "notes": [
            "A 股在线降级首选。",
            "若已有本地库缓存，优先读本地再补 AKShare。",
        ],
    },
    {
        "source_id": "tushare",
        "display_name": "Tushare Pro",
        "source_type": "provider_api",
        "markets": ["CN", "fundamentals", "index", "ETF"],
        "categories": ["market", "fundamentals", "valuation", "dividend", "chip"],
        "preferred_for": [
            "A 股财务报表、分红、主营构成等结构化基本面数据",
            "需要较稳定字段口径的官方风格数据",
            "需要 ts_code / report_period / ann_date 一类标准字段时",
        ],
        "interfaces": [
            "tradingagents.dataflows.providers.china.tushare.TushareProvider",
            "provider.get_financial_data(symbol, limit)",
            "provider.get_historical_data(symbol, start_date, end_date)",
            "get_tushare_provider()",
        ],
        "usage_examples": [
            "from tradingagents.dataflows.providers.china.tushare import get_tushare_provider",
            "provider = get_tushare_provider()",
            "# 优先先读本地缓存；确需在线补数时再调用 provider 的标准方法",
            "# 生成同步 Skill 时，不要发明未文档化的 tushare 调用路径",
        ],
        "constraints": [
            "部分接口需要 token、积分或更高权限。",
            "若需求能由本地缓存满足，不要直接把 Skill 设计成每次都在线打 Tushare。",
            "要注意 ts_code 与 6 位 symbol 的格式转换。",
        ],
        "notes": [
            "A 股基本面和财务深度数据优先来源。",
            "若涉及分红、主营业务、筹码等，先评估权限门槛。",
        ],
    },
    {
        "source_id": "eastmoney_via_akshare",
        "display_name": "东方财富（经 AKShare）",
        "source_type": "public_web_api",
        "markets": ["CN"],
        "categories": ["news", "market", "fund_flow", "sector"],
        "preferred_for": [
            "A 股新闻、盘口、板块、资金流等公开网页数据",
            "需要免费公开数据而不想直接解析网页时",
        ],
        "interfaces": [
            "AKShareProvider.get_stock_news_sync(symbol)",
            "akshare 东方财富相关接口",
        ],
        "usage_examples": [
            "import akshare as ak",
            "# 直接调用 AKShare 的东财公开接口后，立刻把中文列名标准化",
        ],
        "constraints": [
            "本质上依赖公开网页接口，稳定性弱于数据库和正式 API。",
            "适合做新闻/行情补充，不适合作为唯一高可靠源。",
        ],
        "notes": [
            "新闻类 Skill 常见降级来源。",
        ],
    },
    {
        "source_id": "google_news",
        "display_name": "Google News",
        "source_type": "search_interface",
        "markets": ["HK", "US", "global"],
        "categories": ["news", "event"],
        "preferred_for": [
            "港股、美股、海外公司新闻补充",
            "需要跨站点聚合新闻标题与摘要时",
        ],
        "interfaces": [
            "tradingagents.dataflows.interface.get_google_news(query, date)",
        ],
        "usage_examples": [
            "from tradingagents.dataflows.interface import get_google_news",
            "news = get_google_news(query, curr_date)",
        ],
        "constraints": [
            "返回质量依赖搜索结果，必须设置超时保护。",
            "结果更适合作为新闻补充，不适合做严格结构化财务数据来源。",
        ],
        "notes": [
            "港股/美股新闻常用补充源。",
            "建议和 Finnhub 或本地新闻缓存组合使用。",
        ],
    },
    {
        "source_id": "finnhub",
        "display_name": "Finnhub",
        "source_type": "api",
        "markets": ["US"],
        "categories": ["news", "market", "company"],
        "preferred_for": [
            "美股公司新闻、事件驱动信息",
            "需要美股相关新闻时间范围查询时",
        ],
        "interfaces": [
            "tradingagents.dataflows.interface.get_finnhub_news(symbol, start_date, end_date)",
        ],
        "usage_examples": [
            "from tradingagents.dataflows.interface import get_finnhub_news",
            "news = get_finnhub_news(symbol, curr_date, look_back_days)",
        ],
        "constraints": [
            "通常依赖外部配置或配额，生成 Skill 时应保留失败降级路径。",
            "更适合新闻/事件流，不适合替代财务和日线主数据。",
        ],
        "notes": [
            "美股新闻优先源之一。",
        ],
    },
]


SOURCE_CATEGORY_HINTS: Dict[str, Sequence[str]] = {
    "akshare": ("market", "technical", "news", "etf", "utility"),
    "tushare": ("fundamentals", "valuation", "market", "utility"),
    "eastmoney_via_akshare": ("news", "market"),
    "google_news": ("news", "event"),
    "finnhub": ("news", "market"),
}


def is_known_external_source(name: str) -> bool:
    """判断给定来源名是否属于已知外部数据源目录（source_id / display_name / 关键词别名）。

    用于需求分流：用户指定的来源（如 "dongchedi"）若不在目录中，
    调用方应显式标注"目录外数据源"而不是 fallback 凑推荐。
    """
    text = (name or "").strip().lower()
    if not text:
        return False
    if text in {item["source_id"] for item in EXTERNAL_DATA_SOURCE_CATALOG}:
        return True
    for item in EXTERNAL_DATA_SOURCE_CATALOG:
        display = (item.get("display_name") or "").lower()
        if display and (display in text or text in display):
            return True
    for keywords in SOURCE_KEYWORDS.values():
        for keyword in keywords:
            if keyword.lower() in text:
                return True
    return False

SOURCE_KEYWORDS: Dict[str, Sequence[str]] = {
    "akshare": (
        "akshare", "东方财富", "eastmoney", "免费", "盘口", "实时", "历史行情", "etf", "板块",
        "资金流", "quote", "snapshot", "technical", "k线",
    ),
    "tushare": (
        "tushare", "财务", "报表", "利润", "分红", "主营", "筹码", "估值", "基本面", "公告日期",
        "report_period", "ann_date", "financial", "dividend",
    ),
    "eastmoney_via_akshare": (
        "东方财富新闻", "东财", "快讯", "公开网页", "新闻", "资金流", "板块",
    ),
    "google_news": (
        "google", "google news", "港股", "美股", "海外", "global", "headline", "新闻聚合",
    ),
    "finnhub": (
        "finnhub", "美股", "us stock", "company news", "事件", "overseas",
    ),
}

PARAMETER_SOURCE_HINTS: Dict[str, Sequence[str]] = {
    "start_date": ("akshare", "tushare", "google_news", "finnhub"),
    "end_date": ("akshare", "tushare", "google_news", "finnhub"),
    "report_period": ("tushare",),
    "report_type": ("tushare",),
    "curr_date": ("google_news", "finnhub"),
    "limit": ("akshare", "google_news", "finnhub"),
}


def _normalize_text_parts(values: Iterable[Any]) -> List[str]:
    parts: List[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text.lower())
            continue
        if isinstance(value, dict):
            parts.extend(_normalize_text_parts(value.values()))
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(_normalize_text_parts(value))
            continue
        text = str(value).strip()
        if text:
            parts.append(text.lower())
    return parts


def _build_skill_context_text(
    *,
    category: str = "",
    description: str = "",
    data_source: str = "",
    constraints: Sequence[str] | None = None,
    expected_fields: Sequence[str] | None = None,
    parameter_names: Sequence[str] | None = None,
) -> str:
    return "\n".join(
        _normalize_text_parts(
            [
                category,
                description,
                data_source,
                constraints or [],
                expected_fields or [],
                parameter_names or [],
            ]
        )
    )


def select_relevant_external_data_sources(
    *,
    category: str = "",
    description: str = "",
    data_source: str = "",
    constraints: Sequence[str] | None = None,
    expected_fields: Sequence[str] | None = None,
    parameter_names: Sequence[str] | None = None,
    max_items: int = 3,
) -> List[ExternalSourceCatalog]:
    context_text = _build_skill_context_text(
        category=category,
        description=description,
        data_source=data_source,
        constraints=constraints,
        expected_fields=expected_fields,
        parameter_names=parameter_names,
    )
    category_lower = (category or "").strip().lower()
    data_source_lower = (data_source or "").strip().lower()
    param_names = {(name or "").strip().lower() for name in (parameter_names or []) if name}

    ranked: List[tuple[int, ExternalSourceCatalog]] = []
    for item in EXTERNAL_DATA_SOURCE_CATALOG:
        source_id = item["source_id"]
        score = 0

        if category_lower in SOURCE_CATEGORY_HINTS.get(source_id, ()):
            score += 5
        if data_source_lower and source_id in data_source_lower:
            score += 8

        for keyword in SOURCE_KEYWORDS.get(source_id, ()):
            if keyword.lower() in context_text:
                score += 2

        for param_name, related_sources in PARAMETER_SOURCE_HINTS.items():
            if param_name in param_names and source_id in related_sources:
                score += 1

        ranked.append((score, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    selected = [item for score, item in ranked if score >= 3][:max_items]

    if not selected:
        fallback_map = {
            "news": ["akshare", "google_news", "finnhub"],
            "market": ["akshare", "tushare"],
            "technical": ["akshare", "tushare"],
            "fundamentals": ["tushare", "akshare"],
            "utility": ["akshare", "tushare"],
        }
        fallback_ids = fallback_map.get(category_lower, ["akshare", "tushare"])
        selected = [item for item in EXTERNAL_DATA_SOURCE_CATALOG if item["source_id"] in fallback_ids][:max_items]

    return selected[:max_items]


def _render_source_block(item: ExternalSourceCatalog) -> str:
    lines = [
        f"- 数据源: {item['display_name']} ({item['source_id']})",
        f"  类型: {item['source_type']}",
        f"  覆盖市场: {', '.join(item.get('markets', [])) or '无'}",
        f"  适用分类: {', '.join(item.get('categories', [])) or '无'}",
        f"  推荐场景: {', '.join(item.get('preferred_for', [])) or '无'}",
        "  推荐接口:",
    ]
    for entry in item.get("interfaces", []):
        lines.append(f"    - {entry}")
    if item.get("usage_examples"):
        lines.append("  调用示例:")
        for entry in item["usage_examples"]:
            lines.append(f"    - {entry}")
    if item.get("constraints"):
        lines.append("  约束:")
        for entry in item["constraints"]:
            lines.append(f"    - {entry}")
    if item.get("notes"):
        lines.append("  维护说明:")
        for entry in item["notes"]:
            lines.append(f"    - {entry}")
    return "\n".join(lines)


def render_external_data_source_doc(
    sources: Sequence[ExternalSourceCatalog] | None = None,
    focus_summary: str = "",
) -> str:
    source_items = list(sources or EXTERNAL_DATA_SOURCE_CATALOG)
    header = [
        "【外部接口与数据源目录】",
        "以下目录仅描述当前系统中优先支持、且适合 Skill 自动生成时复用的外部数据源。",
        "优先顺序始终是：先本地库，再选择最匹配的外部来源，不要同时臆造多个不确定接口。",
        "如果需求已经能被本地缓存满足，就不要把 Skill 设计成必须实时依赖外部 API。",
        "外部数据源必须调用项目中已文档化的入口，不要发明未声明的 provider 方法或第三方返回字段。",
        "",
    ]
    if focus_summary:
        header.insert(1, f"本次按当前需求仅加载相关外部来源: {focus_summary}")
    body = ["\n\n".join(_render_source_block(item) for item in source_items)]
    footer = [
        "",
        "【使用原则】",
        "1. A 股免费在线补数优先考虑 AKShare；A 股结构化财务优先考虑 Tushare 或其本地缓存。",
        "2. 港股/美股新闻优先考虑 Google News 或 Finnhub，并保留超时与失败降级。",
        "3. 需要精确字段契约时，优先使用 Provider 封装或已有接口函数，不要直接猜测原始网页字段。",
        "4. 如果某来源有权限/积分门槛，Skill 中必须提供本地缓存或免费来源的备选路径。",
        "5. 生成代码时优先照着上述 import 和调用示例写，不要自己杜撰 get_mongo_connection、provider.fetch_xxx 之类项目中不存在的方法。",
    ]
    return "\n".join(header + body + footer)


def build_external_data_source_doc_for_skill(skill_spec: Any, max_items: int = 3) -> str:
    category = getattr(skill_spec, "category", "")
    description = getattr(skill_spec, "description", "")
    data_source = getattr(skill_spec, "data_source", "")
    constraints = getattr(skill_spec, "constraints", []) or []
    expected_output = getattr(skill_spec, "expected_output", None)
    expected_fields = getattr(expected_output, "fields", []) if expected_output else []
    parameter_names = [getattr(param, "name", "") for param in getattr(skill_spec, "parameters", []) or []]

    selected = select_relevant_external_data_sources(
        category=category,
        description=description,
        data_source=data_source,
        constraints=constraints,
        expected_fields=expected_fields,
        parameter_names=parameter_names,
        max_items=max_items,
    )
    focus_summary = "、".join(item["display_name"] for item in selected)
    return render_external_data_source_doc(selected, focus_summary=focus_summary)


EXTERNAL_DATA_SOURCE_DOC = render_external_data_source_doc()