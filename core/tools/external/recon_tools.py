"""侦察层可调用工具集。

将 skill_runtime 中的只读探测函数包装为 LLM function-calling 可用的独立工具。
每个函数都有详细的 docstring 和类型注解，供 ToolCallNormalizer.normalize_tool_definition 自动转换。
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

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
    返回 JSON 对象，包含 sample_count、top_level_fields 等。"""
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
    """查看指定股票在某个集合中的样本文档。
    参数 collection: 集合名称。
    参数 symbol: 6 位股票代码，例如 '600519'。
    参数 limit: 返回文档数（默认 2，最大 5）。
    返回 JSON 数组，每项为一条文档。"""
    from core.skill_runtime.project_access import inspect_symbol_documents
    limit = int(limit) if not isinstance(limit, int) else limit
    docs = inspect_symbol_documents(collection, symbol, limit=min(limit, 5))
    return json.dumps(docs, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# 工具 5: 描述 runtime helper 函数签名和文档
# ---------------------------------------------------------------------------

def describe_runtime_helper(module: str, function_name: str) -> str:
    """查看 skill_runtime 公开模块中某个函数的签名和文档字符串。
    参数 module: 模块短名，支持 'data_access'、'project_access'、'external_sources'。
    参数 function_name: 函数名，例如 'get_stock_valuation_context'。
    返回 JSON 对象，包含 signature(函数签名)和 docstring(文档)。"""
    MODULE_MAP = {
        "data_access": "core.skill_runtime.data_access",
        "project_access": "core.skill_runtime.project_access",
        "external_sources": "core.skill_runtime.external_sources",
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
    参数 module: 模块短名，支持 'data_access'、'project_access'、'external_sources'。
    返回 JSON 数组，每项包含 name(函数名)和 signature(签名)。"""
    MODULE_MAP = {
        "data_access": "core.skill_runtime.data_access",
        "project_access": "core.skill_runtime.project_access",
        "external_sources": "core.skill_runtime.external_sources",
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
            doc_first_line = (inspect.getdoc(obj) or "").split("\n")[0]
            funcs.append({"name": name, "signature": f"{name}{sig}", "summary": doc_first_line})
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
# 工具注册表（供 ReconnaissanceController 使用）
# ---------------------------------------------------------------------------

RECON_TOOLS: List[callable] = [
    list_available_collections,
    inspect_collection_schema,
    check_field_coverage,
    inspect_symbol_sample,
    describe_runtime_helper,
    list_runtime_functions,
    list_external_data_sources,
    list_mcp_tools,
]
"""侦察阶段可用的全部工具函数列表。"""

