"""
股票基础信息（stock_basic_info）统一 Schema —— 兼容壳

实现本体已下沉到共享层 ``tradingagents/dataflows/stock_basic_schema.py``
（分层约定：app -> tradingagents，tradingagents/core 域读侧合并也复用本 Schema）。

本模块保留既有 import 路径：
``from app.services.stock_basic_schema import normalize_stock_basic_doc, ...``
新代码建议直接从共享层 import。
"""
from tradingagents.dataflows.stock_basic_schema import (  # noqa: F401
    ALIAS_FIELDS,
    ALLOWED_EMPTY_FIELDS,
    DERIVED_FIELDS,
    FIELD_SOURCE_KEY,
    FINANCIAL_FIELDS,
    META_FIELDS,
    NUMERIC_FIELDS,
    PROFILE_FIELDS,
    REQUIRED_FIELDS,
    SOURCE_PRIORITY,
    STANDARD_FIELDS,
    get_source_rank,
    merge_stock_basic_records,
    normalize_stock_basic_doc,
    validate_stock_basic_doc,
)
