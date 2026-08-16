"""使用问答机器人工具：按章节名读取用户手册。

让使用问答助手能"查"用户手册的具体章节内容，避免把 139KB 全部塞入系统提示词。
按二级标题切片，按章节名模糊匹配返回。

京东云版（JDYUN_MODE=true）会自动切换到 jdyun-user-manual-v3.0.md，
内容专门面向京东云版用户（部署、限速、卷名问题等）。
"""

import logging
import os
import re
from typing import Annotated, List, Tuple

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _is_jdyun_mode() -> bool:
    """判断是否为京东云模式"""
    return os.environ.get("JDYUN_MODE", "false").lower() == "true"


def _resolve_manual_path() -> str:
    """定位当前应该使用的用户手册。

    京东云版（JDYUN_MODE=true）→ 优先使用 jdyun-user-manual-v3.0.md
    标准版 → 优先使用 user-manual-v3.0.md
    找不到对应版本时回退到标准版，避免手册完全不可用。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # core/tools/implementations/assistant_ops/manual_reader.py -> 项目根目录
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    user_guide_dir = os.path.join(project_root, "docs", "02-user-guide")

    if _is_jdyun_mode():
        # 京东云版优先查找 jdyun-user-manual-v3.0.md，回退到主手册
        candidates = [
            os.path.join(user_guide_dir, "jdyun-user-manual-v3.0.md"),
            os.path.join(user_guide_dir, "user-manual-v3.0.md"),
            os.path.join(user_guide_dir, "user-manual.md"),
        ]
    else:
        candidates = [
            os.path.join(user_guide_dir, "user-manual-v3.0.md"),
            os.path.join(user_guide_dir, "user-manual.md"),
            os.path.join(user_guide_dir, "jdyun-user-manual-v3.0.md"),
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _resolve_all_manual_paths() -> List[Tuple[str, str]]:
    """列出所有可用的用户手册（按优先级顺序），用于多手册搜索。

    返回 [(手册路径, 手册类型), ...]
    手册类型: "jdyun" | "standard"
    京东云版时把京东云手册放前面，标准版时把主手册放前面。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    user_guide_dir = os.path.join(project_root, "docs", "02-user-guide")

    standard_path = os.path.join(user_guide_dir, "user-manual-v3.0.md")
    jdyun_path = os.path.join(user_guide_dir, "jdyun-user-manual-v3.0.md")

    manuals = []
    if _is_jdyun_mode():
        if os.path.exists(jdyun_path):
            manuals.append((jdyun_path, "jdyun"))
        if os.path.exists(standard_path):
            manuals.append((standard_path, "standard"))
    else:
        if os.path.exists(standard_path):
            manuals.append((standard_path, "standard"))
        if os.path.exists(jdyun_path):
            manuals.append((jdyun_path, "jdyun"))
    return manuals


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


def _extract_keyword_fragments(keyword: str, min_len: int = 2) -> List[str]:
    """从关键词中提取可用于模糊匹配的所有连续子片段。

    解决"单容器数据丢失"无法匹配"Q5：单容器重启后数据丢失"的问题。
    提取所有长度 >= min_len 的连续子串，按长度倒序排列（优先匹配长片段）。

    示例:
        "单容器数据丢失" → ["单容器", "数据", "丢失", "容器数据", "据丢失", ...]
        "数据丢失" → ["数据", "丢失", "据丢失"]
    """
    if not keyword or len(keyword) < min_len:
        return []
    fragments = set()
    n = len(keyword)
    for length in range(min_len, n + 1):
        for i in range(n - length + 1):
            frag = keyword[i:i + length]
            if len(frag) >= min_len:
                fragments.add(frag)
    # 按长度倒序（优先用更长的片段，更精确）
    return sorted(fragments, key=len, reverse=True)


def _extract_two_char_fragments(keyword: str) -> List[str]:
    """提取关键词中所有 2 字连续片段（去重，按出现顺序）。

    用于"多数命中"模糊匹配：只要标题中包含其中 60% 的片段，就算匹配。
    解决"单容器数据丢失" vs "Q5：单容器重启后数据丢失" 这类长句重组问题。

    示例:
        "单容器数据丢失" → ["单容器", "容器数", "据丢", "丢失"]  (实际是"单容器","容器","据","丢失"等)
        实际上取固定 2 字窗口："单容","容器","数据","丢失"
    """
    if not keyword or len(keyword) < 2:
        return []
    frags = []
    seen = set()
    for i in range(len(keyword) - 1):
        frag = keyword[i:i + 2]
        if frag not in seen:
            seen.add(frag)
            frags.append(frag)
    return frags


@tool
@register_tool(
    tool_id="read_user_manual_section",
    name="读取用户手册章节",
    description="按章节名读取用户手册内容。支持模糊匹配，如输入'安装'可匹配'安装部署'章节。当用户问'怎么配置 Token''模拟交易怎么开通''怎么加自选股''429 限速怎么办''单容器数据丢失'等操作流程问题时使用。京东云版用户会自动读取京东云版专用手册（包含部署、限速、数据卷等京东云特有问题的解答）。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "manual", "documentation", "user_guide", "operation_flow", "jdyun_manual"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["怎么配置 Token", "模拟交易怎么开通", "怎么加自选股", "License 怎么激活", "429 限速", "单容器数据丢失", "操作流程", "京东云部署"],
    when_to_use="当用户问到具体操作流程、功能配置步骤或系统使用方法时使用，应优先调用本工具查文档而非凭记忆回答。",
    returns="返回文本格式的用户手册章节内容。如未匹配，返回可选章节列表。",
)
async def read_user_manual_section(
    section_name: Annotated[str, "章节名或关键字，如'安装部署'、'数据源配置'、'模拟交易'、'License'、'定时分析'、'股票关注列表'、'429 限速'、'单容器数据丢失'"],
) -> str:
    """按章节名读取用户手册内容。"""
    manual_paths = _resolve_all_manual_paths()
    if not manual_paths:
        return "❌ 用户手册文件不存在。请检查 docs/02-user-guide/ 目录下是否有 user-manual-v3.0.md 文件。"

    keyword = (section_name or "").strip().lower()
    is_jdyun = _is_jdyun_mode()
    current_manual_label = "京东云版专用手册" if is_jdyun else "标准版主手册"

    # 1) 列出所有手册的章节概览
    if not keyword:
        # 收集所有手册的章节
        overview_lines = [f"📖 当前模式: {current_manual_label}", ""]
        for path, manual_type in manual_paths:
            label = "京东云版专用手册" if manual_type == "jdyun" else "标准版主手册"
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                sections = _split_sections(content)
                if not sections:
                    continue
                overview_lines.append(f"━━━ {label} ({os.path.basename(path)}) ━━━")
                for title, body, level in sections:
                    if level <= 2:  # 只列出一级和二级标题
                        prefix = "  " * (level - 1) + "-"
                        overview_lines.append(f"{prefix} {title}")
                overview_lines.append("")
            except Exception as exc:
                logger.warning("[read_user_manual_section] 概览读取失败 %s: %s", path, exc)
        overview_lines.append("💡 请提供具体章节名或关键字（如 '安装部署'、'429 限速'、'单容器数据丢失'）")
        return "\n".join(overview_lines)

    # 2) 关键字搜索：先搜京东云版(若存在)，再搜标准版，合并去重
    all_matches = []  # [(手册类型, 手册名, title, body, level)]
    primary_label = manual_paths[0][1] if manual_paths else "standard"
    seen_titles = set()  # 用于去重

    for path, manual_type in manual_paths:
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            sections = _split_sections(content)
        except Exception as exc:
            logger.warning("[read_user_manual_section] 读取手册失败 %s: %s", path, exc)
            continue

        # 主匹配：标题完全包含关键字
        primary_hits = 0
        for title, body, level in sections:
            if keyword in title.lower():
                dedup_key = f"{manual_type}:{title}"
                if dedup_key not in seen_titles:
                    seen_titles.add(dedup_key)
                    all_matches.append((manual_type, path, title, body, level))
                    primary_hits += 1

        # 模糊匹配：仅在当前手册没有主匹配结果时尝试（避免污染主匹配）
        if primary_hits == 0:
            # 方案 1：用关键字的最长 2 字片段(取前 2-3 个)做"多数命中"判断
            # 解决"单容器数据丢失"匹配不到"Q5：单容器重启后数据丢失"的问题
            # 两者共有片段: "单容器" / "数据" / "丢失" - 3 个 2 字片段
            two_char_frags = _extract_two_char_fragments(keyword)
            if two_char_frags:
                # 至少命中 60% 的 2 字片段才算匹配
                threshold = max(1, int(len(two_char_frags) * 0.6))
                for title, body, level in sections:
                    title_lower = title.lower()
                    hit_count = sum(1 for f in two_char_frags if f in title_lower)
                    if hit_count >= threshold:
                        dedup_key = f"{manual_type}:{title}"
                        if dedup_key not in seen_titles:
                            seen_titles.add(dedup_key)
                            all_matches.append((manual_type, path, title, body, level))

    # 如果主匹配没结果，尝试按单词拆分匹配
    if not all_matches:
        keywords = [k for k in keyword.split() if len(k) >= 2]
        if keywords:
            for path, manual_type in manual_paths:
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    sections = _split_sections(content)
                except Exception:
                    continue
                for title, body, level in sections:
                    if any(k in title.lower() for k in keywords):
                        dedup_key = f"{manual_type}:{title}"
                        if dedup_key not in seen_titles:
                            seen_titles.add(dedup_key)
                            all_matches.append((manual_type, path, title, body, level))

    if not all_matches:
        # 收集所有手册的一级和二级标题作为可选列表
        all_titles = []
        for path, manual_type in manual_paths:
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                sections = _split_sections(content)
                label = "京东云版" if manual_type == "jdyun" else "标准版"
                for title, _, level in sections:
                    if level <= 2 and (label, title) not in all_titles:
                        all_titles.append((label, title))
            except Exception:
                continue
        titles_text = "\n".join(f"  - [{label}] {t}" for label, t in all_titles[:40])
        return f"❌ 未找到章节 '{section_name}'。\n\n📖 可选章节:\n{titles_text}"

    # 3) 拼接匹配结果，控制总长度
    parts = []
    total_len = 0
    max_len = 6000  # 截断防止超长
    matches_to_show = all_matches[:3]  # 最多返回 3 个匹配章节

    for manual_type, path, title, body, level in matches_to_show:
        truncated = _truncate_to_next_level(body, level)
        prefix = "#" * level
        manual_label = "📕 京东云版" if manual_type == "jdyun" else "📘 标准版"
        section_text = f"{manual_label} | {prefix} {title}\n\n{truncated}"
        if total_len + len(section_text) > max_len:
            remaining = max_len - total_len
            if remaining > 200:
                section_text = section_text[:remaining] + "\n\n...(内容已截断，如需完整内容请提供更精确的章节名)"
                parts.append(section_text)
                total_len = max_len
            break
        parts.append(section_text)
        total_len += len(section_text)

    header = f"📖 用户手册搜索结果（keyword='{section_name}', 当前模式: {current_manual_label}）:\n\n"
    return header + "\n\n---\n\n".join(parts)


# ============================================================
# 向量检索工具：基于语义匹配，解决自然语言问题匹配不到章节的问题
# ============================================================


@tool
@register_tool(
    tool_id="search_user_manual",
    name="语义搜索用户手册",
    description=(
        "基于向量语义检索用户手册，用自然语言查找相关章节。"
        "当用户用自然语言提问（如'怎么做分析''怎么研究一只股票''持仓分析怎么用''如何配置 Token'）时使用本工具，"
        "它会返回语义最相关的 Top-5 章节。"
        "本工具比 read_user_manual_section 更适合处理用户的自然语言提问，"
        "建议优先使用本工具检索，再用 read_user_manual_section 按精确章节名读取完整内容。"
    ),
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "manual", "vector_search", "semantic_search", "user_guide"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=[
        "怎么做分析", "怎么研究股票", "如何分析一只股票", "单股分析怎么用",
        "分析在哪", "怎么发起分析", "研究流程", "怎么用平台做分析",
        "持仓分析", "选股助手怎么用", "怎么配置 Token", "怎么加自选",
    ],
    when_to_use=(
        "当用户用自然语言询问系统使用方法、功能流程、操作步骤时优先使用本工具。"
        "本工具基于向量语义匹配，能理解'怎么做分析'等自然语言提问并召回相关章节。"
    ),
    returns="返回 Top-5 相关章节的标题和内容片段，按相似度降序排列。",
)
async def search_user_manual(
    query: Annotated[
        str,
        "用户的自然语言问题，如'怎么做分析''怎么研究一只股票''持仓分析怎么用''如何配置 Token''429 限速怎么办'",
    ],
) -> str:
    """基于向量语义检索用户手册，用自然语言查找相关章节。"""
    try:
        from core.knowledge.user_manual_manager import UserManualManager

        manager = UserManualManager()

        # 检查向量库是否可用；不可用时尝试重新初始化
        # （用户可能已配置好 Embedding Key，reinit 会重新读取配置，无需重启后端）
        if not manager.available:
            try:
                if manager.reinit() and manager.available:
                    logger.info("[search_user_manual] 向量检索重新初始化成功，继续语义检索")
                else:
                    raise RuntimeError("reinit 失败")
            except Exception as e:
                # 优雅降级：回退到 read_user_manual_section 的关键字匹配
                logger.warning(
                    "[search_user_manual] 向量检索不可用（%s），回退到关键字匹配。"
                    "建议检查 Embedding 配置（系统设置 -> LLM/Embedding）或重启后端。",
                    e,
                )
                return (
                    "⚠️ 向量检索当前不可用（Embedding 或向量数据库未就绪），已回退到关键字匹配模式。\n\n"
                    "请尝试用更精确的章节名调用 read_user_manual_section 工具，"
                    "如 '单股研究'、'数据源配置'、'模拟交易' 等。"
                )

        # 检查索引是否已构建
        count = manager.get_count()
        if count == 0:
            logger.warning("[search_user_manual] 手册索引为空，尝试触发重建")
            # 同步触发一次重建（不阻塞太久，失败就降级）
            try:
                manager.ensure_indexed(force=False)
            except Exception as e:
                logger.error(f"[search_user_manual] 触发重建失败: {e}")

            count = manager.get_count()
            if count == 0:
                return (
                    "⚠️ 用户手册索引尚未构建完成，向量检索暂不可用。\n"
                    "可改用 read_user_manual_section 工具按章节名精确读取。"
                )

        # 执行语义检索
        results = manager.search(query, top_k=5)

        if not results:
            return (
                f"❌ 未找到与 '{query}' 语义相关的手册章节。\n"
                "可尝试用更具体的关键字调用 read_user_manual_section 工具。"
            )

        # 格式化输出
        import os
        is_jdyun = _is_jdyun_mode()
        current_label = "京东云版专用手册" if is_jdyun else "标准版主手册"

        lines = [
            f"📖 用户手册语义检索结果（query='{query}', 当前模式: {current_label}）",
            f"找到 {len(results)} 个相关章节（按相似度降序）：",
            "",
        ]

        for i, r in enumerate(results, 1):
            manual_label = "📕 京东云版" if r.manual_type == "jdyun" else "📘 标准版"
            sim_pct = f"{r.similarity * 100:.0f}%"
            parent_hint = f"（所属：{r.parent_title}）" if r.parent_title else ""

            # 控制单个结果长度，避免总输出过长
            content_display = r.content
            if len(content_display) > 800:
                content_display = content_display[:800] + "\n...(内容已截断，如需完整内容请用 read_user_manual_section 按标题读取)"

            lines.append(f"━━━ #{i} {manual_label} | 相似度 {sim_pct} ━━━")
            lines.append(f"📌 标题: {r.title}{parent_hint}")
            lines.append(f"📄 内容:")
            lines.append(content_display)
            lines.append("")

        lines.append(
            "💡 如需查看某个章节的完整内容，可用 read_user_manual_section 工具按上述标题精确读取。"
        )

        return "\n".join(lines)

    except ImportError:
        logger.error("[search_user_manual] UserManualManager 模块未找到")
        return "❌ 向量检索模块未安装。请改用 read_user_manual_section 工具。"
    except Exception as e:
        logger.error(f"[search_user_manual] 检索异常: {e}", exc_info=True)
        return f"❌ 检索失败: {e}\n请改用 read_user_manual_section 工具按章节名精确读取。"

