"""
报告访问工具模块 - 供看涨/看跌研究员动态获取一阶段分析报告。

这些工具让 AI 智能体能够：
1. 发现当前可用的所有分析报告
2. 按需获取指定报告的内容
3. 批量获取多个报告

使用场景：
- 看涨/看跌研究员在辩论阶段需要引用分析数据
- 风险管理智能体需要查阅历史分析
- 交易员需要综合多份报告做决策
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 模块级状态存储（由调用方设置）
_current_state: Dict[str, Any] = {}

# 字段名到显示名映射（动态从配置文件加载）
def _get_report_display_names() -> Dict[str, str]:
    """从配置文件动态获取报告显示名称映射"""
    display_names = {}
    try:
        from tradingagents.agents.analysts.dynamic_analyst import DynamicAnalystFactory
        for agent in DynamicAnalystFactory.get_all_agents():
            slug = agent.get('slug', '')
            name = agent.get('name', '')
            if slug and name:
                internal_key = slug.replace("-analyst", "").replace("-", "_")
                report_key = f"{internal_key}_report"
                display_names[report_key] = f"{name}报告"
    except Exception as e:
        logger.warning(f"⚠️ 无法从配置文件加载报告显示名称: {e}")
    return display_names

# 延迟初始化，避免循环导入
REPORT_DISPLAY_NAMES: Dict[str, str] = {}


def set_state(state: Dict[str, Any]) -> None:
    """
    设置当前 State，供工具函数访问。
    
    Args:
        state: LangGraph 图执行过程中的状态字典
    """
    global _current_state
    _current_state = state if state is not None else {}


def get_state() -> Dict[str, Any]:
    """
    获取当前 State。
    
    Returns:
        当前状态字典
    """
    return _current_state


def _discover_reports(state: Dict[str, Any]) -> List[str]:
    """
    动态发现 State 中所有以 `_report` 结尾的字段。
    
    Args:
        state: 状态字典
        
    Returns:
        报告字段名列表
    """
    if not state:
        return []
    
    report_fields = []
    for key in state.keys():
        if isinstance(key, str) and key.endswith("_report"):
            report_fields.append(key)
    
    return sorted(report_fields)


def _get_display_name(field_name: str) -> str:
    """
    获取字段的显示名称。
    
    Args:
        field_name: 字段名
        
    Returns:
        显示名称
    """
    # 动态获取显示名称映射
    display_names = _get_report_display_names()
    if field_name in display_names:
        return display_names[field_name]
    
    # 自动生成显示名：将下划线替换为空格，移除 _report 后缀
    name = field_name.replace("_report", "").replace("_", " ")
    return f"{name.title()} 报告"


def _truncate_content(content: str, max_chars: int) -> str:
    """
    截断内容到指定长度。
    
    Args:
        content: 原始内容
        max_chars: 最大字符数
        
    Returns:
        截断后的内容（如果截断则添加标记）
    """
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[已截断，原文共 {} 字符]".format(len(content))


def _generate_summary(content: str, max_length: int = 500) -> str:
    """
    生成报告内容的摘要。
    
    简单实现：提取前 N 个字符作为摘要。
    未来可以接入 LLM 生成更智能的摘要。
    
    Args:
        content: 原始内容
        max_length: 摘要最大长度
        
    Returns:
        摘要内容
    """
    if not content:
        return "（无内容）"
    
    # 简单摘要：取前 max_length 字符
    if len(content) <= max_length:
        return content
    
    # 尝试在句子边界截断
    truncated = content[:max_length]
    
    # 查找最后一个句号、问号或感叹号
    for sep in ["。", "！", "？", ".", "!", "?"]:
        last_sep = truncated.rfind(sep)
        if last_sep > max_length // 2:
            return truncated[:last_sep + 1] + "..."
    
    return truncated + "..."


def list_reports() -> str:
    """
    列出当前可用的所有分析报告目录。
    
    此工具帮助你了解有哪些分析报告可供参考。返回每个报告的：
    - 字段名（用于 get_report_content 调用）
    - 显示名称
    - 内容长度
    - 内容摘要（前200字符）
    
    Returns:
        格式化的报告目录字符串
    """
    state = get_state()
    
    if not state:
        return "⚠️ 当前没有可用的状态数据。请确保一阶段分析已完成。"
    
    report_fields = _discover_reports(state)
    
    if not report_fields:
        return "⚠️ 当前状态中没有找到任何分析报告（以 _report 结尾的字段）。"
    
    # 统计信息
    total_count = len(report_fields)
    non_empty_count = 0
    
    # 构建报告列表
    lines = ["# 📊 可用分析报告目录\n"]
    lines.append(f"共发现 {total_count} 个报告字段\n")
    lines.append("-" * 50 + "\n")
    
    for i, field_name in enumerate(report_fields, 1):
        content = state.get(field_name, "")
        display_name = _get_display_name(field_name)
        
        # 处理内容
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        
        length = len(content)
        is_empty = length == 0 or content.strip() == ""
        
        if not is_empty:
            non_empty_count += 1
            summary = content[:200].replace("\n", " ").strip()
            if len(content) > 200:
                summary += "..."
            status = "✅"
        else:
            summary = "（未生成或为空）"
            status = "⚪"
        
        lines.append(f"\n## {i}. {status} {display_name}")
        lines.append(f"   - 字段名: `{field_name}`")
        lines.append(f"   - 长度: {length} 字符")
        lines.append(f"   - 摘要: {summary}")
    
    lines.append("\n" + "-" * 50)
    lines.append(f"\n📈 统计: {non_empty_count}/{total_count} 个报告已生成")
    lines.append("\n💡 提示: 使用 get_report_content(field_name) 获取完整报告内容")
    
    return "\n".join(lines)


def get_report_content(
    field_name: str,
    max_chars: Optional[int] = None,
    summary: bool = False
) -> str:
    """
    获取指定分析报告的内容。
    
    此工具让你获取特定报告的详细内容，用于在辩论中引用具体数据。
    
    Args:
        field_name: 报告字段名，如 "market_report"、"fundamentals_report"。
                   可通过 list_reports 工具获取可用字段名列表。
        max_chars: 最大返回字符数（可选）。如果报告很长，可以设置此参数
                  只获取前 N 个字符，避免信息过载。
        summary: 是否返回摘要而非原文（可选，默认 False）。
                设为 True 时返回报告的关键要点摘要。
    
    Returns:
        报告内容字符串，或错误信息
    
    Example:
        # 获取完整市场报告
        get_report_content("market_report")
        
        # 获取基本面报告的前2000字符
        get_report_content("fundamentals_report", max_chars=2000)
        
        # 获取新闻报告的摘要
        get_report_content("news_report", summary=True)
    """
    state = get_state()
    
    if not state:
        return "❌ 错误: 当前没有可用的状态数据。请确保一阶段分析已完成。"
    
    if not field_name:
        return "❌ 错误: 未指定报告字段名。请提供 field_name 参数。"
    
    # 检查字段是否存在
    available_reports = _discover_reports(state)
    
    if field_name not in state:
        # 提供友好的错误信息
        if available_reports:
            available_list = ", ".join([f"`{r}`" for r in available_reports[:5]])
            if len(available_reports) > 5:
                available_list += f" 等共 {len(available_reports)} 个"
            return f"❌ 错误: 报告 `{field_name}` 不存在。\n\n可用的报告字段: {available_list}\n\n💡 提示: 使用 list_reports() 查看所有可用报告。"
        else:
            return f"❌ 错误: 报告 `{field_name}` 不存在，且当前状态中没有任何报告。"
    
    # 获取内容
    content = state.get(field_name, "")
    
    if content is None:
        content = ""
    elif not isinstance(content, str):
        content = str(content)
    
    display_name = _get_display_name(field_name)
    
    # 检查是否为空
    if not content or content.strip() == "":
        return f"⚠️ 报告 `{field_name}` ({display_name}) 内容为空或未生成。"
    
    # 处理摘要请求
    if summary:
        summary_content = _generate_summary(content)
        return f"# 📋 {display_name} - 摘要\n\n字段名: `{field_name}`\n原文长度: {len(content)} 字符\n\n---\n\n{summary_content}"
    
    # 处理截断请求
    if max_chars is not None and max_chars > 0:
        content = _truncate_content(content, max_chars)
    
    return f"# 📋 {display_name}\n\n字段名: `{field_name}`\n内容长度: {len(state.get(field_name, ''))} 字符\n\n---\n\n{content}"


def get_reports_batch(
    field_names: List[str],
    max_chars_each: Optional[int] = None
) -> str:
    """
    批量获取多个分析报告的内容。
    
    此工具让你一次性获取多个报告，提高效率。
    
    Args:
        field_names: 报告字段名列表，如 ["market_report", "news_report"]
        max_chars_each: 每个报告的最大字符数（可选）
    
    Returns:
        所有请求报告的内容，按字段名分隔
    
    Example:
        # 获取市场和基本面两份报告
        get_reports_batch(["market_report", "fundamentals_report"])
        
        # 获取所有核心报告，每个限制1000字符
        get_reports_batch(
            ["market_report", "sentiment_report", "news_report", "fundamentals_report"],
            max_chars_each=1000
        )
    """
    if not field_names:
        return "❌ 错误: 未指定任何报告字段名。请提供 field_names 列表。"
    
    state = get_state()
    
    if not state:
        return "❌ 错误: 当前没有可用的状态数据。请确保一阶段分析已完成。"
    
    results = []
    found_count = 0
    missing_fields = []
    
    results.append(f"# 📊 批量报告获取结果\n")
    results.append(f"请求报告数: {len(field_names)}\n")
    results.append("=" * 60 + "\n")
    
    for field_name in field_names:
        if field_name not in state:
            missing_fields.append(field_name)
            continue
        
        content = state.get(field_name, "")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        
        display_name = _get_display_name(field_name)
        found_count += 1
        
        # 应用截断
        if max_chars_each is not None and max_chars_each > 0:
            content = _truncate_content(content, max_chars_each)
        
        results.append(f"\n## 📋 {display_name}")
        results.append(f"字段名: `{field_name}`")
        
        if content and content.strip():
            results.append(f"内容长度: {len(state.get(field_name, ''))} 字符\n")
            results.append(content)
        else:
            results.append("⚠️ 内容为空或未生成\n")
        
        results.append("\n" + "-" * 60)
    
    # 添加统计信息
    results.append(f"\n\n📈 统计: 成功获取 {found_count}/{len(field_names)} 个报告")
    
    if missing_fields:
        missing_list = ", ".join([f"`{f}`" for f in missing_fields])
        results.append(f"\n⚠️ 未找到的字段: {missing_list}")
    
    return "\n".join(results)
