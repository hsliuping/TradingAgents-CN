"""侦察层可调用工具集。

将 skill_runtime 中的只读探测函数包装为 LLM function-calling 可用的独立工具。
每个函数都有详细的 docstring 和类型注解，供 ToolCallNormalizer.normalize_tool_definition 自动转换。
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_READONLY_QUERY_CALL_COUNT = 0
_PROBE_INTERFACE_CALL_COUNT = 0
_PROBE_INTERFACE_LAST_CALLED_AT: Dict[str, float] = {}
_PROBE_INTERFACE_MIN_INTERVAL_SECONDS = 0.1

# ---------------------------------------------------------------------------
# 工具 1: 列出可用集合
# ---------------------------------------------------------------------------

def list_available_collections() -> str:
    """列出 Skill 运行时允许访问的所有本地 MongoDB 集合及其用途。
    返回 JSON 数组，每项包含 collection(集合名)、purpose(用途说明)、preferred_access(推荐访问函数)、query_keys(常用查询键)。"""
    from core.skill_runtime.catalog import list_supported_stock_collections
    items = list_supported_stock_collections()
    return json.dumps(items, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 2: 查看集合 schema
# ---------------------------------------------------------------------------

def inspect_collection_schema(collection: str, sample_size: int = 20) -> str:
    """查看指定集合的顶层字段和覆盖率摘要。
    参数 collection: 集合名称（如 stock_basic_info, market_quotes, stock_financial_data 等）。
    参数 sample_size: 采样文档数（默认 20，最大 100）。
    返回 JSON 对象，包含 matching_document_count、sample_count、top_level_fields、field_coverage、sample_document_summaries 等。
    只返回结构摘要，不返回完整样本文档。"""
    from core.skill_runtime.project_access import inspect_stock_collection_schema
    sample_size = int(sample_size) if not isinstance(sample_size, int) else sample_size
    result = inspect_stock_collection_schema(collection, sample_size=sample_size)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# 工具 3: 查看字段覆盖率
# ---------------------------------------------------------------------------

def check_field_coverage(collection: str, fields: str, sample_size: int = 50) -> str:
    """检查指定集合中若干字段的非空覆盖率。
    参数 collection: 集合名称。
    参数 fields: 逗号分隔的字段列表，例如 'pe,pb,total_mv,roe'。
    参数 sample_size: 采样文档数（默认 50）。
    返回 JSON 对象，包含每个字段的 non_null_coverage 比率。"""
    from core.skill_runtime.project_access import inspect_field_coverage as _inspect
    sample_size = int(sample_size) if not isinstance(sample_size, int) else sample_size
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    if not field_list:
        return json.dumps({"error": "fields 参数不能为空"}, ensure_ascii=False)
    result = _inspect(collection, field_list, sample_size=sample_size)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# 工具 4: 查看指定股票的样本文档
# ---------------------------------------------------------------------------

def inspect_symbol_sample(collection: str, symbol: str, limit: int = 2) -> str:
    """查看指定股票在某个集合中的样本文档摘要。
    参数 collection: 集合名称。
    参数 symbol: 6 位股票代码，例如 '600519'。
    参数 limit: 返回文档数（默认 2，最大 5）。
    返回 JSON 对象，包含 matching_document_count、returned_summary_count、documents。
    documents 仅包含字段概览、非空字段数、标识字段预览和嵌套结构摘要，不返回完整原文。"""
    from core.skill_runtime.project_access import inspect_symbol_documents
    limit = int(limit) if not isinstance(limit, int) else limit
    docs = inspect_symbol_documents(collection, symbol, limit=min(limit, 5))
    return json.dumps(docs, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# 工具 5: 描述 runtime helper 函数签名和文档
# ---------------------------------------------------------------------------

def describe_runtime_helper(module: str, function_name: str) -> str:
    """查看 skill_runtime 公开模块中某个函数的签名和文档字符串。
    参数 module: 模块短名，支持 'data_access'、'project_access'、'external_sources'、'standard_financial_apis'。
    参数 function_name: 函数名，例如 'get_stock_valuation_context'。
    返回 JSON 对象，包含 signature(函数签名)和 docstring(文档)。"""
    MODULE_MAP = {
        "data_access": "core.skill_runtime.data_access",
        "project_access": "core.skill_runtime.project_access",
        "external_sources": "core.skill_runtime.external_sources",
        "standard_financial_apis": "core.skill_runtime.standard_financial_apis",
    }
    full_module = MODULE_MAP.get(module)
    if not full_module:
        return json.dumps({"error": f"不支持的模块: {module}，可选: {list(MODULE_MAP.keys())}"}, ensure_ascii=False)
    try:
        import importlib
        mod = importlib.import_module(full_module)
        func = getattr(mod, function_name, None)
        if func is None or not callable(func):
            # 列出可用函数
            available = [name for name, obj in inspect.getmembers(mod, inspect.isfunction) if not name.startswith("_")]
            return json.dumps({"error": f"函数 {function_name} 不存在", "available_functions": available}, ensure_ascii=False)
        sig = str(inspect.signature(func))
        doc = inspect.getdoc(func) or "(无文档)"
        return json.dumps({"module": full_module, "function": function_name, "signature": f"{function_name}{sig}", "docstring": doc}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 6: 列出模块中所有公开函数
# ---------------------------------------------------------------------------

def list_runtime_functions(module: str) -> str:
    """列出 skill_runtime 某个模块中所有公开函数的名称和签名。
    参数 module: 模块短名，支持 'data_access'、'project_access'、'external_sources'、'standard_financial_apis'。
    返回 JSON 数组，每项包含 name(函数名)和 signature(签名)。"""
    MODULE_MAP = {
        "data_access": "core.skill_runtime.data_access",
        "project_access": "core.skill_runtime.project_access",
        "external_sources": "core.skill_runtime.external_sources",
        "standard_financial_apis": "core.skill_runtime.standard_financial_apis",
    }
    full_module = MODULE_MAP.get(module)
    if not full_module:
        return json.dumps({"error": f"不支持的模块: {module}，可选: {list(MODULE_MAP.keys())}"}, ensure_ascii=False)
    try:
        import importlib
        mod = importlib.import_module(full_module)
        funcs = []
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"):
                continue
            sig = str(inspect.signature(obj))
            full_doc = inspect.getdoc(obj) or ""
            funcs.append({"name": name, "signature": f"{name}{sig}", "summary": full_doc})
        return json.dumps(funcs, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 7: 列出已配置的外部数据源
# ---------------------------------------------------------------------------

def list_external_data_sources(market_category: str = "a_shares") -> str:
    """列出当前系统已配置并启用的外部数据源（如 akshare、tushare、baostock）。
    参数 market_category: 市场类别，默认 'a_shares'，可选 'hk_stocks'、'us_stocks'。
    返回 JSON 对象，包含 supported(该市场支持的全部数据源)和 configured(当前已启用的数据源)。
    外部数据源的函数可通过 list_runtime_functions('external_sources') 查看。"""
    from core.skill_runtime.catalog import (
        list_supported_external_sources,
        list_configured_external_sources,
    )
    supported = list_supported_external_sources(market_category)
    configured = list_configured_external_sources(market_category)
    return json.dumps({
        "market_category": market_category,
        "supported_sources": supported,
        "configured_sources": configured,
        "hint": "使用 list_runtime_functions('external_sources') 查看可调用的外部数据获取函数",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 7b: 列出所有可复用的分析类工具（core.tools.implementations）
# ---------------------------------------------------------------------------

# 分析类子目录白名单（与 static_validator.ALLOWED_CORE_PREFIXES 保持一致）
_ANALYSIS_SUBDIRS = [
    "fundamentals", "market", "technical", "portfolio",
    "risk", "news", "social", "trade_review", "legacy_bridge",
]

def list_analysis_tools(category: str = "") -> str:
    """列出所有可复用的分析类工具及其完整导入路径。
    参数 category: 可选分类过滤，支持 'fundamentals'、'market'、'technical'、'portfolio'、'risk'、'news'、'social'、'trade_review'、'legacy_bridge'。留空返回全部。
    返回 JSON 数组，每项包含 tool_id、name、category、module_path（完整导入路径）、function_name（函数名）、summary（一句话说明）。
    生成的 Skill 代码可通过 from <module_path> import <function_name> 调用这些工具。
    注意：此工具返回全量列表，适合分类浏览。若需按需求语义匹配最相关的工具，侦察阶段会通过 CapabilityIndexService 向量搜索自动推荐。"""
    import inspect as _inspect

    target_cats = {category} if category else set(_ANALYSIS_SUBDIRS)
    if category and category not in _ANALYSIS_SUBDIRS:
        return json.dumps({"error": f"不支持的分类: {category}", "allowed": _ANALYSIS_SUBDIRS}, ensure_ascii=False)

    try:
        from core.tools.registry import get_tool_registry
        registry = get_tool_registry()
        all_tools = registry.list_all()
    except Exception as exc:
        return json.dumps({"error": f"ToolRegistry 加载失败: {exc}"}, ensure_ascii=False)

    results = []
    for t in all_tools:
        if t.category not in target_cats:
            continue
        # 获取工具的可调用函数，以确定模块路径
        func = None
        try:
            func = registry.get_function(t.id)
        except Exception:
            pass
        module_path = ""
        function_name = t.id  # 默认用 tool_id 作为函数名
        summary = ""
        if func is not None:
            module_path = getattr(func, "__module__", "") or ""
            function_name = getattr(func, "__name__", t.id)
            doc_first = (_inspect.getdoc(func) or "").split("\n")[0]
            summary = doc_first[:100]
        results.append({
            "tool_id": t.id,
            "name": t.name,
            "category": t.category,
            "module_path": module_path,
            "function_name": function_name,
            "summary": summary,
        })

    return json.dumps(results, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 8: 列出已注册的 MCP 工具
# ---------------------------------------------------------------------------

def list_mcp_tools() -> str:
    """列出当前通过 MCP (Model Context Protocol) 服务器注册到系统的所有工具。
    MCP 工具是外部服务动态注册的能力，可能提供额外的数据获取或计算功能。
    返回 JSON 数组，每项包含 tool_id、name、description。
    若无 MCP 工具则返回空数组。"""
    try:
        from core.tools.registry import get_tool_registry
        registry = get_tool_registry()
        mcp_tools = [t for t in registry.list_all() if t.category == "mcp"]
        items = []
        for t in mcp_tools:
            item: Dict[str, Any] = {
                "tool_id": t.id,
                "name": t.name,
                "description": t.description or "",
            }
            # 如果有参数定义，也附带
            if t.parameters:
                item["parameters"] = [
                    {"name": p.name, "type": p.type, "description": getattr(p, "description", "")}
                    for p in t.parameters
                    if hasattr(p, "name")
                ]
            items.append(item)
        return json.dumps(items, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning(f"[recon] 列出 MCP 工具失败: {exc}")
        return json.dumps([], ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 9: 读取真实样本文档
# ---------------------------------------------------------------------------

def _contains_mongo_operator(value: Any) -> bool:
    """保守拒绝 MongoDB 操作符，确保只读查询工具只支持简单等值过滤。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).startswith("$"):
                return True
            if _contains_mongo_operator(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_mongo_operator(item) for item in value)
    return False


def _json_safe_preview(value: Any, max_chars: int = 6000) -> Any:
    """转换为 JSON 安全对象，并限制返回体积。"""
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return json.loads(text)
    return {
        "truncated": True,
        "original_chars": len(text),
        "preview": text[:max_chars],
    }


def run_readonly_query(
    collection: str,
    filter: dict = None,
    projection: dict = None,
    limit: int = 20,
) -> str:
    """在白名单 MongoDB 集合上执行只读查询，返回真实样本文档。
    参数 collection: 集合名，仅允许 skill_runtime.catalog.SUPPORTED_COLLECTIONS 中登记的集合。
    参数 filter: 简单等值过滤条件，不允许 $where/$regex/$expr 等 Mongo 操作符。
    参数 projection: 字段投影，默认排除 _id。
    参数 limit: 返回条数，最大 20。
    返回 JSON 对象，包含 collection、filter、returned_count、documents、metrics。"""
    global _READONLY_QUERY_CALL_COUNT
    _READONLY_QUERY_CALL_COUNT += 1
    started = time.perf_counter()
    from core.skill_runtime.catalog import SUPPORTED_COLLECTIONS
    from core.skill_runtime.project_access import query_stock_collection

    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        return json.dumps({
            "success": False,
            "error": f"unsupported collection: {collection_name}",
            "allowed_collections": sorted(SUPPORTED_COLLECTIONS),
            "metrics": {"call_count": _READONLY_QUERY_CALL_COUNT},
        }, ensure_ascii=False)

    filters = filter or {}
    projections = projection or {"_id": 0}
    if not isinstance(filters, dict):
        return json.dumps({"success": False, "error": "filter must be an object", "metrics": {"call_count": _READONLY_QUERY_CALL_COUNT}}, ensure_ascii=False)
    if not isinstance(projections, dict):
        return json.dumps({"success": False, "error": "projection must be an object", "metrics": {"call_count": _READONLY_QUERY_CALL_COUNT}}, ensure_ascii=False)
    if _contains_mongo_operator(filters) or _contains_mongo_operator(projections):
        return json.dumps({
            "success": False,
            "error": "Mongo operators are not allowed in run_readonly_query; use simple equality filters only",
            "metrics": {"call_count": _READONLY_QUERY_CALL_COUNT},
        }, ensure_ascii=False)

    capped_limit = max(1, min(int(limit or 20), 20))
    try:
        docs = query_stock_collection(
            collection=collection_name,
            filters=filters,
            projection=projections,
            limit=capped_limit,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        payload = {
            "success": True,
            "collection": collection_name,
            "filter": filters,
            "projection": projections,
            "limit": capped_limit,
            "returned_count": len(docs),
            "documents": docs,
            "metrics": {
                "call_count": _READONLY_QUERY_CALL_COUNT,
                "elapsed_ms": elapsed_ms,
                "limit_capped": int(limit or 20) != capped_limit,
            },
        }
        return json.dumps(_json_safe_preview(payload), ensure_ascii=False, default=str)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("[recon] run_readonly_query failed: %s", exc)
        return json.dumps({
            "success": False,
            "error": str(exc),
            "metrics": {"call_count": _READONLY_QUERY_CALL_COUNT, "elapsed_ms": elapsed_ms},
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具 10: 真实调用运行时 helper / 外部接口探针
# ---------------------------------------------------------------------------

def _summarize_probe_shape(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        keys = list(value.keys())
        summary: Dict[str, Any] = {
            "type": "dict",
            "keys": keys[:30],
            "key_count": len(keys),
        }
        for key in ("data", "items", "result", "records"):
            nested = value.get(key)
            if isinstance(nested, list):
                summary[f"{key}_length"] = len(nested)
                if nested:
                    summary[f"{key}_first_item_type"] = type(nested[0]).__name__
                    if isinstance(nested[0], dict):
                        summary[f"{key}_first_item_keys"] = list(nested[0].keys())[:30]
            elif isinstance(nested, dict):
                summary[f"{key}_keys"] = list(nested.keys())[:30]
        return summary
    if isinstance(value, list):
        summary = {"type": "list", "length": len(value)}
        if value:
            summary["first_item_type"] = type(value[0]).__name__
            if isinstance(value[0], dict):
                summary["first_item_keys"] = list(value[0].keys())[:30]
        return summary
    return {"type": type(value).__name__}


def _resolve_runtime_helper(source_or_helper: str):
    import importlib

    raw = str(source_or_helper or "").strip()
    if not raw:
        raise ValueError("source_or_helper is required")

    module_map = {
        "data_access": "core.skill_runtime.data_access",
        "project_access": "core.skill_runtime.project_access",
        "external_sources": "core.skill_runtime.external_sources",
        "standard_financial_apis": "core.skill_runtime.standard_financial_apis",
    }
    allowed_modules = set(module_map.values())

    if raw.count(".") >= 1:
        module_part, func_name = raw.rsplit(".", 1)
        module_name = module_map.get(module_part, module_part)
        if module_name not in allowed_modules:
            raise ValueError(f"unsupported helper module: {module_name}")
        module = importlib.import_module(module_name)
        func = getattr(module, func_name, None)
        if callable(func) and not func_name.startswith("_"):
            return module_name, func_name, func
        raise ValueError(f"helper not found: {raw}")

    for module_name in allowed_modules:
        module = importlib.import_module(module_name)
        func = getattr(module, raw, None)
        if callable(func) and not raw.startswith("_"):
            return module_name, raw, func
    raise ValueError(f"helper not found: {raw}")


def probe_interface(source_or_helper: str, sample_args: dict = None) -> str:
    """真实调用一次已登记的 skill_runtime helper，返回可用性、返回形状和预览。
    参数 source_or_helper: helper 名称，支持 get_external_valuation_data、external_sources.get_external_valuation_data、core.skill_runtime.external_sources.get_external_valuation_data 等。
    参数 sample_args: 样例参数对象，例如 {"symbol":"600519", "start_date":"2024-01-01", "end_date":"2024-12-31"}。
    返回 JSON 对象，包含 success、module、function、elapsed_ms、shape、preview、metrics 或 error。"""
    global _PROBE_INTERFACE_CALL_COUNT
    _PROBE_INTERFACE_CALL_COUNT += 1

    # 处理 LLM 可能传入 JSON 字符串的情况
    args = sample_args
    if args is None:
        args = {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
            logger.debug(f"[probe_interface] sample_args 已从 JSON 字符串解析: {type(args)}")
        except Exception:
            pass
    if not isinstance(args, dict):
        logger.warning(f"[probe_interface] sample_args 类型错误: {type(args)}，值: {args}")
        return json.dumps({"success": False, "error": f"sample_args must be an object（当前类型: {type(args).__name__}）", "metrics": {"call_count": _PROBE_INTERFACE_CALL_COUNT}}, ensure_ascii=False)
    if _contains_mongo_operator(args):
        return json.dumps({"success": False, "error": "Mongo-style operators are not allowed in sample_args", "metrics": {"call_count": _PROBE_INTERFACE_CALL_COUNT}}, ensure_ascii=False)

    started = time.perf_counter()
    try:
        module_name, func_name, func = _resolve_runtime_helper(source_or_helper)
        rate_key = f"{module_name}.{func_name}"
        now = time.perf_counter()
        last_called = _PROBE_INTERFACE_LAST_CALLED_AT.get(rate_key, 0.0)
        min_interval = _PROBE_INTERFACE_MIN_INTERVAL_SECONDS
        waited_ms = 0.0
        if min_interval > 0 and now - last_called < min_interval:
            wait_seconds = min_interval - (now - last_called)
            time.sleep(wait_seconds)
            waited_ms = round(wait_seconds * 1000, 2)
        _PROBE_INTERFACE_LAST_CALLED_AT[rate_key] = time.perf_counter()

        result = func(**args)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        payload = {
            "success": True,
            "module": module_name,
            "function": func_name,
            "elapsed_ms": elapsed_ms,
            "shape": _summarize_probe_shape(result),
            "preview": _json_safe_preview(result, max_chars=4000),
            "metrics": {
                "call_count": _PROBE_INTERFACE_CALL_COUNT,
                "rate_limit_wait_ms": waited_ms,
                "min_interval_ms": round(min_interval * 1000, 2),
            },
        }
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("[recon] probe_interface failed: %s", exc)
        return json.dumps({
            "success": False,
            "source_or_helper": source_or_helper,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
            "metrics": {"call_count": _PROBE_INTERFACE_CALL_COUNT},
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具注册表（供 ReconnaissanceController / Agentic Loop 使用）
# ---------------------------------------------------------------------------

RECON_TOOLS: List[callable] = [
    list_available_collections,
    inspect_collection_schema,
    check_field_coverage,
    inspect_symbol_sample,
    describe_runtime_helper,
    list_runtime_functions,
    list_analysis_tools,
    list_external_data_sources,
    list_mcp_tools,
    run_readonly_query,
    probe_interface,
]
"""侦察阶段与 Agentic Skill 生成循环可用的全部工具函数列表。"""


