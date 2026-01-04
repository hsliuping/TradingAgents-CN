"""
权重计算工具

根据用户选择的分析师，自动计算各报告的权重
"""

from typing import Dict, List, Optional, Tuple


def calculate_report_weights(
    reports: Dict[str, str],
    trading_style: Optional[str] = None
) -> Dict[str, float]:
    """
    根据用户选择的分析师报告，计算各报告的权重
    
    Args:
        reports: 报告字典，key为报告字段名，value为报告内容（如果为空字符串或None，表示未选择）
        trading_style: 交易风格，"short"（短线）或"long"（中长线），如果为None则自动判断
    
    Returns:
        权重字典，key为报告字段名，value为权重（0-1之间的浮点数）
    """
    # 报告字段名到分析师类型的映射
    REPORT_TO_ANALYST_TYPE = {
        "market_report": "technical",      # 市场分析师（技术分析）
        "news_report": "news",             # 新闻分析师
        "sentiment_report": "social",       # 社媒分析师（情绪分析）
        "fundamentals_report": "fundamental",  # 基本面分析师
        "sector_report": "sector",         # 板块分析师（行业分析）
        "index_report": "index",           # 大盘分析师
    }
    
    # 筛选出非空报告（表示用户选择了这些分析师）
    selected_reports = {
        report_key: report_content
        for report_key, report_content in reports.items()
        if report_content and isinstance(report_content, str) and len(report_content.strip()) > 0
    }
    
    if not selected_reports:
        # 如果没有选择任何报告，返回空权重字典
        return {}
    
    # 如果没有指定交易风格，自动判断
    if trading_style is None:
        trading_style = _infer_trading_style(selected_reports)
    
    # 根据交易风格设置权重
    if trading_style == "short":
        # 短线权重配置
        weights = _calculate_short_term_weights(selected_reports)
    elif trading_style == "long":
        # 中长线权重配置
        weights = _calculate_long_term_weights(selected_reports)
    else:
        # 默认：平均权重
        weights = _calculate_equal_weights(selected_reports)
    
    return weights


def _infer_trading_style(reports: Dict[str, str]) -> str:
    """
    根据选择的报告推断交易风格
    
    Args:
        reports: 选择的报告字典
    
    Returns:
        "short" 或 "long"
    """
    # 如果选择了基本面分析师，更可能是中长线
    if "fundamentals_report" in reports:
        return "long"
    
    # 如果选择了技术、新闻、社媒分析师，更可能是短线
    if "market_report" in reports and "news_report" in reports and "sentiment_report" in reports:
        return "short"
    
    # 如果选择了板块分析师，更可能是中长线
    if "sector_report" in reports:
        return "long"
    
    # 默认返回短线
    return "short"


def _calculate_short_term_weights(reports: Dict[str, str]) -> Dict[str, float]:
    """
    计算短线交易的权重
    
    短线权重配置：
    - 技术分析（market_report）：40%
    - 新闻分析（news_report）：30%
    - 社媒分析（sentiment_report）：30%
    - 其他报告：10%或更低
    """
    weights = {}
    total_weight = 0.0
    
    # 核心报告权重
    core_reports = {
        "market_report": 0.40,      # 技术分析 40%
        "news_report": 0.30,        # 新闻分析 30%
        "sentiment_report": 0.30,   # 社媒分析 30%
    }
    
    # 检查核心报告是否存在
    selected_core_reports = {
        k: v for k, v in core_reports.items() if k in reports
    }
    
    if selected_core_reports:
        # 如果核心报告都存在，使用预设权重
        for report_key, weight in selected_core_reports.items():
            weights[report_key] = weight
            total_weight += weight
        
        # 其他报告（基本面、板块、大盘）权重较低
        other_reports = {
            "fundamentals_report": 0.05,  # 基本面 5%
            "sector_report": 0.05,        # 板块 5%
            "index_report": 0.10,         # 大盘 10%
        }
        
        for report_key, weight in other_reports.items():
            if report_key in reports:
                weights[report_key] = weight
                total_weight += weight
        
        # 归一化权重（确保总和为1.0）
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
    else:
        # 如果核心报告不全，使用平均权重
        weights = _calculate_equal_weights(reports)
    
    return weights


def _calculate_long_term_weights(reports: Dict[str, str]) -> Dict[str, float]:
    """
    计算中长线投资的权重
    
    中长线权重配置：
    - 基本面分析（fundamentals_report）：50%
    - 板块分析（sector_report）：30%
    - 风险分析（通过风险辩论体现）：20%
    - 其他报告：10%或更低
    """
    weights = {}
    total_weight = 0.0
    
    # 核心报告权重
    core_reports = {
        "fundamentals_report": 0.50,  # 基本面分析 50%
        "sector_report": 0.30,        # 板块分析 30%
    }
    
    # 检查核心报告是否存在
    selected_core_reports = {
        k: v for k, v in core_reports.items() if k in reports
    }
    
    if selected_core_reports:
        # 如果核心报告都存在，使用预设权重
        for report_key, weight in selected_core_reports.items():
            weights[report_key] = weight
            total_weight += weight
        
        # 其他报告权重较低
        other_reports = {
            "market_report": 0.10,        # 技术分析 10%（仅用于判断技术面是否在下跌趋势中）
            "news_report": 0.05,          # 新闻分析 5%
            "sentiment_report": 0.05,     # 社媒分析 5%
            "index_report": 0.00,         # 大盘分析 0%（中长线不太关注大盘）
        }
        
        for report_key, weight in other_reports.items():
            if report_key in reports:
                weights[report_key] = weight
                total_weight += weight
        
        # 归一化权重（确保总和为1.0）
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
    else:
        # 如果核心报告不全，使用平均权重
        weights = _calculate_equal_weights(reports)
    
    return weights


def _calculate_equal_weights(reports: Dict[str, str]) -> Dict[str, float]:
    """
    计算平均权重（当无法确定交易风格时使用）
    
    Args:
        reports: 选择的报告字典
    
    Returns:
        权重字典，所有报告的权重相等
    """
    if not reports:
        return {}
    
    weight = 1.0 / len(reports)
    return {report_key: weight for report_key in reports.keys()}


def format_weighted_reports_prompt(
    reports: Dict[str, str],
    weights: Dict[str, float],
    report_labels: Optional[Dict[str, str]] = None
) -> str:
    """
    格式化带权重的报告提示词
    
    Args:
        reports: 报告字典
        weights: 权重字典
        report_labels: 报告标签字典（可选），用于显示中文名称
    
    Returns:
        格式化后的提示词文本
    """
    if not report_labels:
        report_labels = {
            "market_report": "市场分析（技术分析）",
            "news_report": "新闻分析",
            "sentiment_report": "社媒分析（市场情绪）",
            "fundamentals_report": "基本面分析",
            "sector_report": "板块分析（行业分析）",
            "index_report": "大盘分析",
        }
    
    # 按权重排序（从高到低）
    sorted_reports = sorted(
        weights.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    prompt_parts = []
    
    # 高权重报告（权重 >= 20%）
    high_weight_reports = [
        (report_key, weight) for report_key, weight in sorted_reports
        if weight >= 0.20 and report_key in reports
    ]
    
    if high_weight_reports:
        prompt_parts.append("【重要报告】（权重高，请重点关注）")
        for report_key, weight in high_weight_reports:
            label = report_labels.get(report_key, report_key)
            weight_pct = int(weight * 100)
            prompt_parts.append(f"- {label}（权重{weight_pct}%）：\n{reports[report_key]}\n")
    
    # 低权重报告（权重 < 20%）
    low_weight_reports = [
        (report_key, weight) for report_key, weight in sorted_reports
        if weight < 0.20 and report_key in reports
    ]
    
    if low_weight_reports:
        prompt_parts.append("\n【次要报告】（权重低，仅供参考）")
        for report_key, weight in low_weight_reports:
            label = report_labels.get(report_key, report_key)
            weight_pct = int(weight * 100)
            prompt_parts.append(f"- {label}（权重{weight_pct}%，仅供参考）：\n{reports[report_key]}\n")
    
    # 添加权重说明
    if prompt_parts:
        prompt_parts.append(
            "\n**权重说明**："
            "\n- 请重点关注高权重报告，这些报告对投资决策更重要"
            "\n- 低权重报告仅作为补充参考，不应过度依赖"
            "\n- 在综合判断时，请根据权重给予相应的关注度"
        )
    
    return "\n".join(prompt_parts)


