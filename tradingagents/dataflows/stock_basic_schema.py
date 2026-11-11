"""
股票基础信息（stock_basic_info）统一 Schema（共享层）

背景：多个同步服务（basics_sync_service / multi_source_basics_sync_service /
akshare_sync_service 等）写入同一集合 stock_basic_info，但字段构造不统一。
本模块定义标准字段集合与写入/读取入口，供 app / tradingagents / core 三域共用：

- 写入：``normalize_stock_basic_doc`` / ``validate_stock_basic_doc``
  所有同步服务写库前必须经由 normalize 对齐字段语义（尤其 source/data_source 一致）。
- 读取：``merge_stock_basic_records``
  同 code 的多 source 记录按 ``SOURCE_PRIORITY`` 优先级 + 非空字段互补合并，
  并在 ``_field_source`` 中保留字段级来源标注。

多源记录设计（(code, source) 联合 upsert，同一只股票保留多条来源记录）保持不变，
本模块只统一字段口径与读侧合并，不合并写入记录。

分层约定：实现本体在本模块（tradingagents 共享层，依赖方向 app -> tradingagents）；
``app/services/stock_basic_schema.py`` 仅是 re-export 兼容壳，既有 import 路径不受影响。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据源优先级（读侧合并顺序：越靠前优先级越高）
#
# 注意与 data_source_manager.DEFAULT_SOURCE_PRIORITY（数据源降级链顺序，含 local）
# 是两套语义、不可合并：本表只裁决「同 code 多 source 记录合并时同字段冲突谁赢」，
# 基础字段（name/industry/pe_ttm 等）以 tushare 为准；local 记录以行情快照字段为主，
# 不参与基础字段冲突裁决（未列出的 source 一律按最低优先级，仅参与非空互补）。
# ---------------------------------------------------------------------------
SOURCE_PRIORITY: Tuple[str, ...] = ("tushare", "multi_source", "akshare", "baostock")

_SOURCE_RANK = {src: idx for idx, src in enumerate(SOURCE_PRIORITY)}

# ---------------------------------------------------------------------------
# 标准字段集合
# ---------------------------------------------------------------------------
# 必填字段（写入身份键，(code, source) 联合 upsert 依赖）
REQUIRED_FIELDS: Tuple[str, ...] = ("code", "source")

# 必填但可推导：normalize 会用 code 补齐
DERIVED_FIELDS: Tuple[str, ...] = ("symbol",)

# 基础信息可选字段（允许为空 / 允许缺失）
PROFILE_FIELDS: Tuple[str, ...] = (
    "name",
    "area",
    "industry",
    "market",
    "list_date",
    "sse",
    "full_symbol",
    "category",
)

# 来源与维护元信息
META_FIELDS: Tuple[str, ...] = ("source", "data_source", "industry_source", "updated_at")

# 财务/交易指标（可选、允许为空，允许缺失）
FINANCIAL_FIELDS: Tuple[str, ...] = (
    "total_mv",
    "circ_mv",
    "pe",
    "pb",
    "ps",
    "pe_ttm",
    "pb_mrq",
    "ps_ttm",
    "turnover_rate",
    "volume_ratio",
    "total_share",
    "float_share",
    "dividend_yield",
    "dividend_yield_ttm",
    "roe",
)

# 数值型字段（validate 时检查可转 float）
NUMERIC_FIELDS: Tuple[str, ...] = FINANCIAL_FIELDS

# 允许为空的字段（"" / None 均合法；缺失也合法）
ALLOWED_EMPTY_FIELDS: Tuple[str, ...] = PROFILE_FIELDS + FINANCIAL_FIELDS + ("industry_source",)

# 全部标准字段
STANDARD_FIELDS: Tuple[str, ...] = tuple(
    dict.fromkeys(REQUIRED_FIELDS + DERIVED_FIELDS + PROFILE_FIELDS + META_FIELDS + FINANCIAL_FIELDS)
)

# 历史别名字段 -> 规范字段（老服务写 "sec"，规范名为 "category"；
# 读写两侧都保留两个名字以兼容存量读取方）
ALIAS_FIELDS: Dict[str, str] = {"sec": "category"}

# 合并结果中的字段级来源标注键
FIELD_SOURCE_KEY = "_field_source"


def _is_non_empty(value: Any) -> bool:
    """判断字段值是否为有效非空值（""/空白/None/NaN 视为空，0/False 视为有效）。"""
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def get_source_rank(source: Any) -> int:
    """数据源优先级排名（越小越优先；未知来源排在最后）。"""
    key = str(source or "").strip()
    return _SOURCE_RANK.get(key, len(SOURCE_PRIORITY))


def _canonical_key(key: str) -> str:
    return ALIAS_FIELDS.get(key, key)


# ---------------------------------------------------------------------------
# 写入入口
# ---------------------------------------------------------------------------
def validate_stock_basic_doc(doc: Mapping[str, Any]) -> List[str]:
    """
    校验一条 stock_basic_info 文档，返回错误信息列表（空列表 = 合法）。

    规则：
    - 必填：code（6 位数字字符串）、source（非空字符串）
    - symbol 若存在必须为 6 位数字字符串
    - 数值型字段若非空必须可转 float
    """
    errors: List[str] = []

    code = str(doc.get("code") or "").strip()
    if not code:
        errors.append("缺少必填字段: code")
    elif not (code.isdigit() and len(code) == 6):
        errors.append(f"code 必须为 6 位数字: {code!r}")

    source = str(doc.get("source") or "").strip()
    if not source:
        errors.append("缺少必填字段: source")

    symbol = doc.get("symbol")
    if _is_non_empty(symbol):
        symbol_str = str(symbol).strip()
        if not (symbol_str.isdigit() and len(symbol_str) == 6):
            errors.append(f"symbol 必须为 6 位数字: {symbol!r}")

    for field in NUMERIC_FIELDS:
        value = doc.get(field)
        if not _is_non_empty(value):
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            errors.append(f"{field} 必须为数值: {value!r}")

    return errors


def normalize_stock_basic_doc(doc: Mapping[str, Any], write_path: str = "sync") -> Dict[str, Any]:
    """
    对齐一条 stock_basic_info 文档到统一 Schema（写入入口）。

    - code：去空白，数字补零到 6 位
    - symbol：缺失/为空时用 code 补齐
    - source/data_source：统一语义，data_source 恒等于 source（以 source 为准）
    - category/sec：互为镜像，保证同一值（不凭空补值）
    - write_path：写入路径标记 'sync'（离线同步）| 'cache'（请求时缓存回写），
      默认 'sync'；文档已带标记时保留原值（§七：读侧与治理页可区分两条写入路径）
    - 标准字符串字段去首尾空白；未知字段原样保留（不做删除）
    - 校验失败抛 ValueError（错误信息来自 validate_stock_basic_doc）
    """
    if not isinstance(doc, Mapping):
        raise ValueError("stock basic doc 必须是映射类型")

    result: Dict[str, Any] = dict(doc)

    # 写入路径标记（§七）：默认离线同步，缓存回写路径传 write_path="cache"
    result["write_path"] = str(result.get("write_path") or write_path)

    # code 规范化
    code = str(result.get("code") or "").strip()
    if code.isdigit() and len(code) < 6:
        code = code.zfill(6)
    result["code"] = code

    # symbol 从 code 推导
    symbol = str(result.get("symbol") or "").strip()
    result["symbol"] = symbol if symbol else code

    # source / data_source 语义统一：同一条记录两处一致，以 source 为准
    source = str(result.get("source") or "").strip()
    result["source"] = source
    result["data_source"] = source

    # 标准字符串字段去空白
    for field in STANDARD_FIELDS:
        if field in ("code", "symbol", "source", "data_source"):
            continue
        value = result.get(field)
        if isinstance(value, str):
            result[field] = value.strip()

    # category / sec（历史别名）互为镜像
    category = result.get("category")
    sec = result.get("sec")
    if _is_non_empty(category):
        result["sec"] = category
    elif _is_non_empty(sec):
        result["category"] = sec

    errors = validate_stock_basic_doc(result)
    if errors:
        raise ValueError("; ".join(errors))

    return result


# ---------------------------------------------------------------------------
# 读取入口：多源记录合并
# ---------------------------------------------------------------------------
def merge_stock_basic_records(records: Optional[Iterable[Mapping[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    合并同一只股票（同 code）的多 source 记录。

    规则：
    - 按 ``SOURCE_PRIORITY``（tushare > multi_source > akshare > baostock）排序，
      未知来源排在最后；同一来源内部保持传入顺序
    - 非空字段互补：每个字段取"优先级最高且值非空"的记录值
     （""/空白/None/NaN 视为空，0/False 视为有效值）
    - ``_field_source``：字段级来源标注，形如 ``{"area": "akshare"}``
    - source/data_source 语义统一：合并结果的 data_source 恒等于主来源 source
    - category/sec 互为镜像（历史别名）

    Args:
        records: 同 code 的多条记录（可含无 source 的历史记录，排最后）

    Returns:
        合并后的文档；records 为空时返回 None
    """
    docs = [dict(r) for r in (records or []) if isinstance(r, Mapping) and r]
    if not docs:
        return None

    # 优先级排序（稳定排序：同 source 内保持原顺序）
    docs.sort(key=lambda d: get_source_rank(d.get("source") or d.get("data_source")))

    merged: Dict[str, Any] = {}
    field_source: Dict[str, str] = {}

    for doc in docs:
        src = str(doc.get("source") or doc.get("data_source") or "").strip() or "unknown"
        for key, value in doc.items():
            if key in ("_id", FIELD_SOURCE_KEY):
                continue
            canon = _canonical_key(key)
            if canon in merged and _is_non_empty(merged[canon]):
                continue
            if not _is_non_empty(value):
                continue
            merged[canon] = value
            field_source[canon] = src
            # 别名字段同步写回两个名字
            if canon != key:
                merged[key] = value
                field_source[key] = src

    if not merged:
        return None

    # category / sec 互为镜像
    if _is_non_empty(merged.get("category")):
        merged["sec"] = merged["category"]
        field_source.setdefault("sec", field_source.get("category", "unknown"))
    elif _is_non_empty(merged.get("sec")):
        merged["category"] = merged["sec"]
        field_source.setdefault("category", field_source.get("sec", "unknown"))

    # symbol 缺失时用 code 补齐（与写入 normalize 一致）
    if not _is_non_empty(merged.get("symbol")) and _is_non_empty(merged.get("code")):
        merged["symbol"] = merged["code"]
        field_source["symbol"] = field_source.get("code", "unknown")

    # source/data_source 语义统一：合并结果以主来源为准
    primary_source = str(merged.get("source") or merged.get("data_source") or "").strip() or "unknown"
    merged["source"] = primary_source
    merged["data_source"] = primary_source
    field_source.setdefault("source", primary_source)
    field_source["data_source"] = field_source.get("source", primary_source)

    merged[FIELD_SOURCE_KEY] = field_source
    return merged
