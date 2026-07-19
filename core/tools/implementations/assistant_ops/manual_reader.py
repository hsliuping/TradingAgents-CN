"""使用问答机器人工具：按章节名读取用户手册。

让使用问答助手能"查"用户手册的具体章节内容，避免把 139KB 全部塞入系统提示词。
按二级标题切片，按章节名模糊匹配返回。
"""

import logging
import os
import re
from typing import Annotated, List, Tuple

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _resolve_manual_path() -> str:
    """定位用户手册文件路径"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # core/tools/implementations/assistant_ops/manual_reader.py -> 项目根目录
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    candidates = [
        os.path.join(project_root, "docs", "02-user-guide", "user-manual-v3.0.md"),
        os.path.join(project_root, "docs", "02-user-guide", "user-manual.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _split_sections(content: str) -> List[Tuple[str, str, int]]:
    """按 markdown 标题切片。

    返回 [(title, body, level), ...]
    level 是 # 的数量（1-4）
    """
    sections: List[Tuple[str, str, int]] = []
    # 匹配行首的 1-4 个 # 后跟空格和标题
    parts = re.split(r'\n(?=#{1,4}\s+[^\n]+)', content)
    for part in parts:
        match = re.match(r'^(#{1,4})\s+([^\n]+)\n(.*)', part, re.DOTALL)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            body = match.group(3).strip()
            sections.append((title, body, level))
    return sections


def _truncate_to_next_level(body: str, current_level: int) -> str:
    """截取到下一个同级或更高级标题"""
    pattern = re.compile(rf'\n#{{1,{current_level}}}\s+')
    match = pattern.search(body)
    if match:
        return body[:match.start()].strip()
    return body.strip()


@tool
@register_tool(
    tool_id="read_user_manual_section",
    name="读取用户手册章节",
    description="按章节名读取用户手册内容。支持模糊匹配，如输入'安装'可匹配'安装部署'章节。当用户问'怎么配置 Token''模拟交易怎么开通''怎么加入关注列表'等操作流程问题时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "manual", "documentation", "user_guide", "operation_flow"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["怎么配置 Token", "模拟交易怎么开通", "怎么加入关注列表", "License 怎么激活", "操作流程"],
    when_to_use="当用户问到具体操作流程、功能配置步骤或系统使用方法时使用，应优先调用本工具查文档而非凭记忆回答。",
    returns="返回文本格式的用户手册章节内容。如未匹配，返回可选章节列表。",
)
async def read_user_manual_section(
    section_name: Annotated[str, "章节名或关键字，如'安装部署'、'数据源配置'、'模拟交易'、'License'、'定时分析'、'股票关注列表'"],
) -> str:
    """按章节名读取用户手册内容。"""
    manual_path = _resolve_manual_path()
    if not manual_path:
        return "❌ 用户手册文件不存在。请检查 docs/02-user-guide/ 目录下是否有 user-manual-v3.0.md 文件。"

    try:
        with open(manual_path, encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        logger.error("[read_user_manual_section] 读取手册失败: %s", exc)
        return f"❌ 读取用户手册失败: {exc}"

    sections = _split_sections(content)
    if not sections:
        return "❌ 用户手册内容为空或格式异常。"

    keyword = (section_name or "").strip().lower()
    if not keyword:
        # 列出所有章节
        titles = [s[0] for s in sections if s[2] <= 3]  # 只列到 3 级标题
        return f"📖 用户手册共 {len(sections)} 个章节。请提供具体章节名，可选章节:\n" + "\n".join(f"  - {t}" for t in titles[:50])

    # 模糊匹配
    matched = []
    for title, body, level in sections:
        if keyword in title.lower():
            truncated = _truncate_to_next_level(body, level)
            matched.append((title, truncated, level))

    if not matched:
        # 二次匹配：标题中任意单词
        keywords = [k for k in keyword.split() if len(k) >= 2]
        for title, body, level in sections:
            if any(k in title.lower() for k in keywords):
                truncated = _truncate_to_next_level(body, level)
                matched.append((title, truncated, level))

    if not matched:
        titles = [s[0] for s in sections if s[2] <= 2]
        return f"❌ 未找到章节 '{section_name}'。\n\n📖 可选章节（一级和二级标题）:\n" + "\n".join(f"  - {t}" for t in titles[:30])

    # 拼接匹配结果，控制总长度
    parts = []
    total_len = 0
    max_len = 6000  # 截断防止超长
    for title, body, level in matched[:3]:  # 最多返回 3 个匹配章节
        prefix = "#" * level
        section_text = f"{prefix} {title}\n\n{body}"
        if total_len + len(section_text) > max_len:
            remaining = max_len - total_len
            if remaining > 200:
                section_text = section_text[:remaining] + "\n\n...(内容已截断，如需完整内容请提供更精确的章节名)"
                parts.append(section_text)
                total_len = max_len
            break
        parts.append(section_text)
        total_len += len(section_text)

    header = f"📖 用户手册 - 匹配到 {len(matched)} 个章节（keyword='{section_name}'）:\n\n"
    return header + "\n\n---\n\n".join(parts)
