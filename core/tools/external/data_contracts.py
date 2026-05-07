"""数据契约加载与任务级文档生成。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from .stock_data_catalog import select_relevant_stock_collections


DataContract = Dict[str, Any]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACT_DIR = _REPO_ROOT / "config" / "data_contracts"


@lru_cache(maxsize=1)
def list_data_contracts() -> Dict[str, DataContract]:
    contracts: Dict[str, DataContract] = {}
    if not _CONTRACT_DIR.exists():
        return contracts

    for path in sorted(_CONTRACT_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        collection = str(payload.get("collection") or path.stem).strip()
        if collection:
            contracts[collection] = payload
    return contracts


def get_data_contract(collection: str) -> DataContract | None:
    return list_data_contracts().get(str(collection or "").strip())


def _render_contract(contract: DataContract) -> str:
    structure = contract.get("structure") or {}
    lines: List[str] = [
        f"- 集合契约: {contract.get('collection', 'unknown')}",
        f"  摘要: {contract.get('summary', '')}",
    ]

    top_level_shape = structure.get("top_level_shape")
    if top_level_shape:
        lines.append(f"  顶层结构: {top_level_shape}")

    query_keys = structure.get("query_keys") or []
    if query_keys:
        lines.append(f"  查询键: {', '.join(str(item) for item in query_keys)}")

    stable_fields = structure.get("stable_top_level_fields") or []
    if stable_fields:
        lines.append(f"  稳定顶层字段: {', '.join(str(item) for item in stable_fields[:16])}")

    nested_paths = structure.get("nested_paths") or []
    if nested_paths:
        lines.append("  嵌套路径:")
        for item in nested_paths[:6]:
            lines.append(
                f"    - {item.get('path')} [{item.get('type')}]: {item.get('description', '')}"
            )

    task_mappings = contract.get("task_mappings") or []
    if task_mappings:
        lines.append("  任务映射:")
        for item in task_mappings[:4]:
            task = item.get("task", "unknown")
            primary = item.get("primary_paths") or []
            fallback = item.get("fallback_paths") or []
            lines.append(f"    - {task}: 主路径={'; '.join(str(v) for v in primary[:4])}")
            if fallback:
                lines.append(f"      回退={'; '.join(str(v) for v in fallback[:3])}")
            for note in (item.get("notes") or [])[:3]:
                lines.append(f"      说明={note}")

    pitfalls = contract.get("pitfalls") or []
    if pitfalls:
        lines.append("  易错点:")
        for item in pitfalls[:5]:
            lines.append(f"    - {item}")

    return "\n".join(lines)


def build_data_contract_doc_for_skill(skill_spec: Any, max_items: int = 3) -> str:
    expected_output = getattr(skill_spec, "expected_output", None)
    expected_fields = getattr(expected_output, "fields", []) if expected_output else []
    parameter_names = [getattr(param, "name", "") for param in getattr(skill_spec, "parameters", []) or []]

    selected = select_relevant_stock_collections(
        category=getattr(skill_spec, "category", ""),
        description=getattr(skill_spec, "description", ""),
        data_source=getattr(skill_spec, "data_source", ""),
        constraints=getattr(skill_spec, "constraints", []) or [],
        expected_fields=expected_fields,
        parameter_names=parameter_names,
        max_items=max_items,
    )
    contracts = [
        get_data_contract(item.get("collection", ""))
        for item in selected
    ]
    contracts = [item for item in contracts if item]
    if not contracts:
        return ""

    header = [
        "【任务相关数据契约】",
        "以下内容来自仓库内可维护的数据契约配置，是比自由推断更高优先级的结构事实。",
        "如契约说明与样本数据冲突，先记录冲突并以样本验证结果为准，不要臆造中间结构。",
        "",
    ]
    body = ["\n\n".join(_render_contract(contract) for contract in contracts)]
    footer = [
        "",
        "【使用要求】",
        "1. 先按契约理解字段层级，再决定是否需要样本探测。",
        "2. 对 array 路径必须按数组元素遍历，不要把 array 当 dict。",
        "3. 若任务依赖主路径失败，再按契约中的回退路径实现。",
    ]
    return "\n".join(header + body + footer)