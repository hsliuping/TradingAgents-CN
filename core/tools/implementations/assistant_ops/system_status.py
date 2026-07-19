"""使用问答机器人工具：查询系统状态。

提供查询系统模式（标准/京东云）、当前默认模型、数据源启用状态、版本号等能力，
让使用问答助手能"看到"系统当前真实状态。
"""

import logging
import os
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _resolve_version() -> str:
    """读取 VERSION 文件"""
    try:
        # 工具文件路径: core/tools/implementations/assistant_ops/system_status.py
        # 项目根目录: 上四级
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        version_path = os.path.join(project_root, "VERSION")
        if os.path.exists(version_path):
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
    except Exception as exc:
        logger.warning("[get_system_status] 读取 VERSION 文件失败: %s", exc)
    return "未知"


def _is_jdyun_mode() -> bool:
    """判断是否为京东云模式"""
    return os.environ.get("JDYUN_MODE", "false").lower() == "true"


@tool
@register_tool(
    tool_id="get_system_status",
    name="获取系统状态",
    description="查询系统当前的运行模式（标准版/京东云版）、默认大模型、数据源启用状态和版本号。当用户问'这是什么版本''当前用什么模型''数据源有哪些'等问题时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "system_status", "jdyun_mode", "default_model", "data_sources", "version"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["当前是什么版本", "京东云版还是标准版", "当前用什么大模型", "数据源有哪些"],
    when_to_use="当用户问到系统配置、模式、版本、当前模型或数据源状态时使用。",
    returns="返回文本格式的系统状态摘要，包含运行模式、默认模型、数据源列表和版本号。",
)
async def get_system_status() -> str:
    """获取系统当前运行状态。"""
    from app.core.database import get_mongo_db

    db = get_mongo_db()
    jdyun = _is_jdyun_mode()
    version = _resolve_version()

    # 当前默认模型
    default_model = "未配置"
    default_provider = "未配置"
    try:
        # 从 llm_configs 集合读取启用的模型
        cursor = db.llm_configs.find({"enabled": True}, {"model_name": 1, "provider": 1, "is_default": 1}).limit(10)
        docs = await cursor.to_list(length=10)
        if docs:
            # 优先取 is_default
            default_doc = next((d for d in docs if d.get("is_default")), docs[0])
            default_model = default_doc.get("model_name", "未知")
            default_provider = default_doc.get("provider", "未知")
    except Exception as exc:
        logger.warning("[get_system_status] 查询默认模型失败: %s", exc)

    # 数据源启用状态
    data_sources_lines = []
    try:
        cursor = db.data_sources.find({}, {"name": 1, "type": 1, "enabled": 1}).limit(20)
        docs = await cursor.to_list(length=20)
        if docs:
            for ds in docs:
                name = ds.get("name") or ds.get("type") or "?"
                ds_type = ds.get("type") or "?"
                enabled = "启用" if ds.get("enabled") else "禁用"
                # 京东云版隐藏非支持的数据源
                if jdyun and ds_type.lower() not in {"tushare", "akshare"}:
                    continue
                data_sources_lines.append(f"  - {name}({ds_type}): {enabled}")
        else:
            data_sources_lines.append("  - (数据库中未配置数据源)")
    except Exception as exc:
        logger.warning("[get_system_status] 查询数据源失败: %s", exc)
        data_sources_lines.append(f"  - 查询失败: {exc}")

    lines = [
        "🖥️ 系统状态",
        f"- 运行模式: {'京东云版' if jdyun else '标准版'}",
        f"- 版本号: v{version}",
        f"- 默认大模型: {default_model} (厂家: {default_provider})",
        "- 数据源:",
    ]
    lines.extend(data_sources_lines or ["  - 无"])

    if jdyun:
        lines.append("- 京东云版说明: 全功能开放，无需激活 License；大模型和数据源由平台统一配置")

    return "\n".join(lines)
