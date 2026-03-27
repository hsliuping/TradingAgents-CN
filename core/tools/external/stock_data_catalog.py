"""
股票数据集合目录

这份目录专门给 Skill 生成器和维护者使用，统一描述当前系统里
可直接复用的股票 MongoDB 集合、关键字段、推荐访问方式和注意事项。

维护原则：
1. 优先记录“稳定且常用”的字段，不追求把所有历史遗留字段一次性写尽。
2. 如果某集合允许 source-specific 扩展字段，需在 notes 中写清楚。
3. 当 local_data.py 新增访问函数或集合字段发生变化时，优先同步此文件。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


StockField = Dict[str, Any]
CollectionCatalog = Dict[str, Any]


COLLECTION_CATEGORY_HINTS: Dict[str, Sequence[str]] = {
    "stock_basic_info": ("fundamentals", "utility", "profile", "company"),
    "market_quotes": ("market", "technical", "realtime", "quote"),
    "stock_daily_quotes": ("market", "technical", "trend", "history"),
    "stock_financial_data": ("fundamentals", "valuation", "finance"),
    "stock_news": ("news", "event", "sentiment"),
}

COLLECTION_KEYWORDS: Dict[str, Sequence[str]] = {
    "stock_basic_info": (
        "基础信息", "公司信息", "行业", "板块", "静态估值", "市值", "股息率", "roe",
        "profile", "company", "industry", "sector", "valuation", "market cap", "dividend",
    ),
    "market_quotes": (
        "实时", "最新价", "盘口", "分时", "quote", "snapshot", "tick", "现价", "涨跌幅",
        "成交额", "成交量", "买一", "卖一",
    ),
    "stock_daily_quotes": (
        "日线", "k线", "历史行情", "区间走势", "技术指标", "均线", "波动率", "回测",
        "daily", "history", "ohlc", "candlestick", "trend", "technical", "moving average",
    ),
    "stock_financial_data": (
        "财务", "报表", "利润", "营收", "现金流", "资产负债", "估值", "基本面", "业绩",
        "financial", "revenue", "net income", "balance sheet", "cash flow", "earnings",
    ),
    "stock_news": (
        "新闻", "公告", "事件", "舆情", "情绪", "研报", "快讯", "headline", "news",
        "sentiment", "research report", "event",
    ),
}

PARAMETER_COLLECTION_HINTS: Dict[str, Sequence[str]] = {
    "start_date": ("stock_daily_quotes",),
    "end_date": ("stock_daily_quotes",),
    "trade_date": ("stock_daily_quotes", "market_quotes"),
    "report_period": ("stock_financial_data",),
    "report_type": ("stock_financial_data",),
    "limit": ("stock_news",),
    "sentiment": ("stock_news",),
    "publish_time": ("stock_news",),
}


STOCK_DATA_COLLECTION_CATALOG: List[CollectionCatalog] = [
    {
        "collection": "stock_basic_info",
        "purpose": "股票基础信息、行业归属、静态估值和部分交易指标。",
        "preferred_access": ["get_stock_basic_info", "get_industry_peer_basic_info", "summarize_industry_valuation"],
        "query_keys": ["symbol", "code", "source"],
        "notes": [
            "A 股核心基础表，优先用 get_stock_basic_info 访问。",
            "若需求是同行筛选、行业样本或 PB/PE/PS 相对估值，优先用 get_industry_peer_basic_info / summarize_industry_valuation。",
            "同一股票可能按 source 保留多份记录，查询时通常需要结合 source 或优先级策略。",
            "除标准字段外，允许保留数据源扩展字段。",
        ],
        "fields": [
            {"name": "symbol", "type": "str", "description": "6 位股票代码，主查询键。"},
            {"name": "code", "type": "str", "description": "兼容旧逻辑的 6 位股票代码。"},
            {"name": "full_symbol", "type": "str", "description": "标准化完整代码，如 600519.SH / 000001.SZ。"},
            {"name": "name", "type": "str", "description": "股票名称。"},
            {"name": "area", "type": "str", "description": "地区。"},
            {"name": "industry", "type": "str", "description": "行业。"},
            {"name": "market", "type": "str", "description": "交易市场名称。"},
            {"name": "list_date", "type": "str", "description": "上市日期。"},
            {"name": "sse", "type": "str", "description": "板块信息。"},
            {"name": "sec", "type": "str", "description": "所属板块/分类。"},
            {"name": "source", "type": "str", "description": "基础信息数据源，如 tushare / akshare / baostock / multi_source。"},
            {"name": "updated_at", "type": "datetime|str", "description": "最近更新时间。"},
            {"name": "total_mv", "type": "float", "description": "总市值，常见口径为亿元。"},
            {"name": "circ_mv", "type": "float", "description": "流通市值，常见口径为亿元。"},
            {"name": "pe", "type": "float", "description": "市盈率。"},
            {"name": "pb", "type": "float", "description": "市净率。"},
            {"name": "ps", "type": "float", "description": "市销率。"},
            {"name": "pe_ttm", "type": "float", "description": "滚动市盈率。"},
            {"name": "pb_mrq", "type": "float", "description": "最新市净率。"},
            {"name": "ps_ttm", "type": "float", "description": "滚动市销率。"},
            {"name": "roe", "type": "float", "description": "净资产收益率。"},
            {"name": "turnover_rate", "type": "float", "description": "换手率。"},
            {"name": "volume_ratio", "type": "float", "description": "量比。"},
            {"name": "dividend_yield", "type": "float", "description": "股息率。"},
            {"name": "dividend_yield_ttm", "type": "float", "description": "TTM 股息率。"},
            {"name": "total_share", "type": "float", "description": "总股本，部分同步链路使用此字段名。"},
            {"name": "float_share", "type": "float", "description": "流通股本，部分同步链路使用此字段名。"},
            {"name": "total_shares", "type": "float", "description": "总股本，标准化扩展字段。"},
            {"name": "float_shares", "type": "float", "description": "流通股本，标准化扩展字段。"},
            {"name": "board", "type": "str", "description": "板块标准化字段。"},
            {"name": "sector", "type": "str", "description": "行业/赛道标准化字段。"},
            {"name": "industry_code", "type": "str", "description": "行业代码。"},
            {"name": "status", "type": "str", "description": "上市状态，如 L / D / P。"},
            {"name": "is_hs", "type": "bool", "description": "是否沪深港通标的。"},
            {"name": "currency", "type": "str", "description": "交易货币。"},
            {"name": "market_info", "type": "dict", "description": "市场信息扩展结构，含 exchange / currency / timezone 等。"},
            {"name": "data_version", "type": "int", "description": "数据版本。"},
        ],
    },
    {
        "collection": "market_quotes",
        "purpose": "近实时行情、涨跌、成交额和盘口相关字段。",
        "preferred_access": ["get_market_quotes"],
        "query_keys": ["symbol", "code"],
        "notes": [
            "实时行情主表，通常只保留每只股票一条最新记录。",
            "优先用 get_market_quotes 访问，避免直接依赖字段兼容差异。",
        ],
        "fields": [
            {"name": "symbol", "type": "str", "description": "6 位股票代码，主查询键。"},
            {"name": "code", "type": "str", "description": "兼容旧逻辑的 6 位股票代码。"},
            {"name": "full_symbol", "type": "str", "description": "标准化完整代码。"},
            {"name": "market", "type": "str", "description": "市场标识，如 CN / HK / US。"},
            {"name": "close", "type": "float", "description": "最新价/收盘价。"},
            {"name": "current_price", "type": "float", "description": "当前价格，通常与 close 对齐。"},
            {"name": "pre_close", "type": "float", "description": "前收盘价。"},
            {"name": "change", "type": "float", "description": "涨跌额。"},
            {"name": "pct_chg", "type": "float", "description": "涨跌幅。"},
            {"name": "open", "type": "float", "description": "开盘价。"},
            {"name": "high", "type": "float", "description": "最高价。"},
            {"name": "low", "type": "float", "description": "最低价。"},
            {"name": "volume", "type": "float", "description": "成交量。"},
            {"name": "amount", "type": "float", "description": "成交额。"},
            {"name": "turnover_rate", "type": "float", "description": "换手率。"},
            {"name": "volume_ratio", "type": "float", "description": "量比。"},
            {"name": "trade_date", "type": "str", "description": "交易日期。"},
            {"name": "timestamp", "type": "datetime", "description": "行情时间戳。"},
            {"name": "updated_at", "type": "datetime", "description": "更新时间。"},
            {"name": "bid_prices", "type": "list[float]", "description": "买 1-5 档价格。"},
            {"name": "bid_volumes", "type": "list[float]", "description": "买 1-5 档数量。"},
            {"name": "ask_prices", "type": "list[float]", "description": "卖 1-5 档价格。"},
            {"name": "ask_volumes", "type": "list[float]", "description": "卖 1-5 档数量。"},
            {"name": "data_source", "type": "str", "description": "行情来源字段。"},
            {"name": "data_version", "type": "int", "description": "数据版本。"},
        ],
    },
    {
        "collection": "stock_daily_quotes",
        "purpose": "历史日线/K 线，供价格趋势、区间统计、技术指标计算使用。",
        "preferred_access": ["get_stock_daily_quotes"],
        "query_keys": ["symbol", "trade_date", "period", "data_source"],
        "notes": [
            "历史行情主表，常用于按 symbol + 日期区间查询。",
            "优先使用 get_stock_daily_quotes，不建议生成的 Skill 自己拼低层 Mongo 查询。",
        ],
        "fields": [
            {"name": "symbol", "type": "str", "description": "6 位股票代码。"},
            {"name": "code", "type": "str", "description": "兼容旧逻辑的股票代码。"},
            {"name": "full_symbol", "type": "str", "description": "标准化完整代码。"},
            {"name": "market", "type": "str", "description": "市场标识。"},
            {"name": "trade_date", "type": "str", "description": "交易日期，常见格式 YYYY-MM-DD。"},
            {"name": "period", "type": "str", "description": "周期，如 daily / weekly / monthly。"},
            {"name": "open", "type": "float", "description": "开盘价。"},
            {"name": "high", "type": "float", "description": "最高价。"},
            {"name": "low", "type": "float", "description": "最低价。"},
            {"name": "close", "type": "float", "description": "收盘价。"},
            {"name": "pre_close", "type": "float", "description": "前收盘价。"},
            {"name": "change", "type": "float", "description": "涨跌额。"},
            {"name": "pct_chg", "type": "float", "description": "涨跌幅。"},
            {"name": "volume", "type": "float", "description": "成交量。"},
            {"name": "amount", "type": "float", "description": "成交额。"},
            {"name": "turnover_rate", "type": "float", "description": "换手率。"},
            {"name": "volume_ratio", "type": "float", "description": "量比。"},
            {"name": "pe", "type": "float", "description": "当日或快照估值指标中的市盈率。"},
            {"name": "pb", "type": "float", "description": "市净率。"},
            {"name": "ps", "type": "float", "description": "市销率。"},
            {"name": "adjustflag", "type": "float|str", "description": "复权标记或复权因子。"},
            {"name": "tradestatus", "type": "float|str", "description": "交易状态。"},
            {"name": "isST", "type": "float|str", "description": "是否 ST。"},
            {"name": "data_source", "type": "str", "description": "历史数据来源。"},
            {"name": "created_at", "type": "datetime", "description": "创建时间。"},
            {"name": "updated_at", "type": "datetime", "description": "更新时间。"},
            {"name": "version", "type": "int", "description": "数据版本。"},
        ],
    },
    {
        "collection": "stock_financial_data",
        "purpose": "财务报表与关键财务指标，供基本面分析和估值计算使用。",
        "preferred_access": ["get_stock_financial_data"],
        "query_keys": ["symbol", "report_period", "data_source", "report_type"],
        "notes": [
            "这是统一财务主表，基础元数据字段比较稳定，明细指标允许因 source 不同而扩展。",
            "生成 Skill 时应优先依赖 report_period / report_type / data_source 做过滤。",
            "历史数据中也可能出现 report_date 字段，生成 Skill 时要兼容 report_period / report_date 两种口径。",
            "如果只需要最近几期财务数据，优先用 get_stock_financial_data，而不是自己做复杂聚合。",
        ],
        "fields": [
            {"name": "symbol", "type": "str", "description": "6 位股票代码。"},
            {"name": "code", "type": "str", "description": "兼容旧逻辑的股票代码。"},
            {"name": "full_symbol", "type": "str", "description": "标准化完整代码。"},
            {"name": "market", "type": "str", "description": "市场标识。"},
            {"name": "report_period", "type": "str", "description": "报告期，如 20241231。"},
            {"name": "report_type", "type": "str", "description": "报告类型，如 quarterly / annual。"},
            {"name": "data_source", "type": "str", "description": "财务数据来源，如 tushare / akshare / baostock。"},
            {"name": "ann_date", "type": "str", "description": "公告日期，部分来源存在。"},
            {"name": "revenue", "type": "float", "description": "营业收入。"},
            {"name": "net_income", "type": "float", "description": "净利润。"},
            {"name": "total_assets", "type": "float", "description": "总资产。"},
            {"name": "total_equity", "type": "float", "description": "股东权益合计。"},
            {"name": "total_liab", "type": "float", "description": "负债合计。"},
            {"name": "cash_and_equivalents", "type": "float", "description": "货币资金/现金及等价物。"},
            {"name": "roe", "type": "float", "description": "净资产收益率。"},
            {"name": "debt_to_assets", "type": "float", "description": "资产负债率。"},
            {"name": "created_at", "type": "datetime", "description": "创建时间。"},
            {"name": "updated_at", "type": "datetime", "description": "更新时间。"},
            {"name": "version", "type": "int", "description": "数据版本。"},
        ],
    },
    {
        "collection": "stock_news",
        "purpose": "个股新闻、事件、情绪与标签。",
        "preferred_access": ["get_stock_news", "get_stock_news_by_date_range"],
        "query_keys": ["symbol", "symbols", "publish_time", "data_source"],
        "notes": [
            "新闻主表适合按 symbol + 时间区间查询。",
            "唯一性通常由 url + title + publish_time 组合保证。",
            "生成 Skill 时应尽量复用 get_stock_news / get_stock_news_by_date_range。",
        ],
        "fields": [
            {"name": "symbol", "type": "str", "description": "主要关联股票代码。"},
            {"name": "full_symbol", "type": "str", "description": "标准化完整代码。"},
            {"name": "market", "type": "str", "description": "市场标识。"},
            {"name": "symbols", "type": "list[str]", "description": "该新闻关联的多只股票代码。"},
            {"name": "title", "type": "str", "description": "新闻标题。"},
            {"name": "content", "type": "str", "description": "新闻正文或摘要正文。"},
            {"name": "summary", "type": "str", "description": "摘要。"},
            {"name": "url", "type": "str", "description": "原始链接。"},
            {"name": "source", "type": "str", "description": "原始媒体来源。"},
            {"name": "author", "type": "str", "description": "作者。"},
            {"name": "publish_time", "type": "datetime", "description": "发布时间。"},
            {"name": "category", "type": "str", "description": "新闻类别。"},
            {"name": "sentiment", "type": "str", "description": "情感标签，如 positive / neutral / negative。"},
            {"name": "sentiment_score", "type": "float", "description": "情感分数。"},
            {"name": "keywords", "type": "list[str]", "description": "关键词列表。"},
            {"name": "importance", "type": "str", "description": "重要性等级。"},
            {"name": "data_source", "type": "str", "description": "新闻聚合来源。"},
            {"name": "created_at", "type": "datetime", "description": "创建时间。"},
            {"name": "updated_at", "type": "datetime", "description": "更新时间。"},
            {"name": "version", "type": "int", "description": "数据版本。"},
        ],
    },
]


def _render_collection_block(item: CollectionCatalog) -> str:
    lines = [
        f"- 集合: {item['collection']}",
        f"  用途: {item['purpose']}",
        f"  推荐访问函数: {', '.join(item.get('preferred_access', [])) or '无'}",
        f"  常用查询键: {', '.join(item.get('query_keys', [])) or '无'}",
        "  关键字段:",
    ]
    for field in item.get("fields", []):
        lines.append(
            f"    - {field['name']} ({field['type']}): {field['description']}"
        )
    if item.get("notes"):
        lines.append("  维护说明:")
        for note in item["notes"]:
            lines.append(f"    - {note}")
    return "\n".join(lines)


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


def select_relevant_stock_collections(
    *,
    category: str = "",
    description: str = "",
    data_source: str = "",
    constraints: Sequence[str] | None = None,
    expected_fields: Sequence[str] | None = None,
    parameter_names: Sequence[str] | None = None,
    max_items: int = 3,
) -> List[CollectionCatalog]:
    context_text = _build_skill_context_text(
        category=category,
        description=description,
        data_source=data_source,
        constraints=constraints,
        expected_fields=expected_fields,
        parameter_names=parameter_names,
    )
    category_lower = (category or "").strip().lower()
    param_names = {(name or "").strip().lower() for name in (parameter_names or []) if name}

    ranked: List[tuple[int, CollectionCatalog]] = []
    for item in STOCK_DATA_COLLECTION_CATALOG:
        collection = item["collection"]
        score = 0

        if category_lower in COLLECTION_CATEGORY_HINTS.get(collection, ()):
            score += 6

        for keyword in COLLECTION_KEYWORDS.get(collection, ()):
            if keyword.lower() in context_text:
                score += 2

        for param_name, related_collections in PARAMETER_COLLECTION_HINTS.items():
            if param_name in param_names and collection in related_collections:
                score += 2

        field_names = {field.get("name", "").lower() for field in item.get("fields", [])}
        for expected_field in (expected_fields or []):
            normalized_field = (expected_field or "").strip().lower()
            if normalized_field and normalized_field in field_names:
                score += 1

        if any(
            query_key.lower() in param_names and query_key.lower() not in {"symbol", "code"}
            for query_key in item.get("query_keys", [])
        ):
            score += 1

        ranked.append((score, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    selected = [item for score, item in ranked if score > 0][:max_items]

    if not selected:
        fallback_map = {
            "news": ["stock_news", "stock_basic_info"],
            "market": ["market_quotes", "stock_daily_quotes"],
            "technical": ["stock_daily_quotes", "market_quotes"],
            "fundamentals": ["stock_financial_data", "stock_basic_info"],
            "utility": ["stock_basic_info"],
        }
        fallback_collections = fallback_map.get(category_lower, ["stock_basic_info"])
        selected = [
            item for item in STOCK_DATA_COLLECTION_CATALOG
            if item["collection"] in fallback_collections
        ]

    selected_names = {item["collection"] for item in selected}
    if "stock_basic_info" not in selected_names and category_lower in {"fundamentals", "market", "news", "technical"}:
        basic_info = next(
            (item for item in STOCK_DATA_COLLECTION_CATALOG if item["collection"] == "stock_basic_info"),
            None,
        )
        if basic_info is not None and len(selected) < max_items:
            selected.append(basic_info)

    return selected[:max_items]


def build_stock_data_collection_doc_for_skill(skill_spec: Any, max_items: int = 3) -> str:
    category = getattr(skill_spec, "category", "")
    description = getattr(skill_spec, "description", "")
    data_source = getattr(skill_spec, "data_source", "")
    constraints = getattr(skill_spec, "constraints", []) or []
    expected_output = getattr(skill_spec, "expected_output", None)
    expected_fields = getattr(expected_output, "fields", []) if expected_output else []
    parameter_names = [getattr(param, "name", "") for param in getattr(skill_spec, "parameters", []) or []]

    selected = select_relevant_stock_collections(
        category=category,
        description=description,
        data_source=data_source,
        constraints=constraints,
        expected_fields=expected_fields,
        parameter_names=parameter_names,
        max_items=max_items,
    )
    focus_summary = "、".join(item["collection"] for item in selected)
    return render_stock_data_collection_doc(
        collections=selected,
        focus_summary=focus_summary,
    )


def render_stock_data_collection_doc(
    collections: Sequence[CollectionCatalog] | None = None,
    focus_summary: str = "",
) -> str:
    collection_items = list(collections or STOCK_DATA_COLLECTION_CATALOG)
    header = [
        "【股票本地数据集合目录】",
        "以下目录是当前系统中最重要的股票数据 MongoDB 集合说明，供生成 Skill 时参考。",
        "生成 Skill 时，优先调用 local_data.py 中的封装函数；只有封装函数无法满足时，才考虑直接查询集合。",
        "如果直接查 MongoDB，必须严格使用以下字段名，不要臆造不存在的列。",
        "严禁在生成代码中自行创建 MongoClient、硬编码数据库名或发明项目中不存在的数据库 helper。",
        "",
    ]
    if focus_summary:
        header.insert(1, f"本次按当前需求仅加载相关集合: {focus_summary}")
    body = ["\n\n".join(_render_collection_block(item) for item in collection_items)]
    footer = [
        "",
        "【使用原则】",
        "1. 优先本地数据，后补外部 API。",
        "2. 需要基础信息时优先 stock_basic_info；需要最新价格时优先 market_quotes；需要区间行情时优先 stock_daily_quotes。",
        "3. 需要行业同行样本、集合字段复用或 PB/PE/PS 行业统计时，优先使用 get_industry_peer_basic_info / summarize_industry_valuation。",
        "3. 财务数据按 report_period 倒序取最近几期；若历史记录使用 report_date，也要兼容该字段。",
        "4. 新闻数据按 symbol + publish_time 过滤，并控制 limit，避免一次返回过多正文。",
        "5. 若集合字段与当前 Skill 需求不完全匹配，优先在返回结果中做二次整理，不要猜测数据库里还有未声明字段。",
    ]
    return "\n".join(header + body + footer)


STOCK_DATA_COLLECTION_DOC = render_stock_data_collection_doc()
