"""Prompt guardrails for research-only compliance mode."""

from __future__ import annotations

from typing import Iterable


COMMON_FORBIDDEN_ITEMS = (
    "不得输出买入、卖出、持有、加仓、减仓、清仓、建仓、平仓等交易动作建议",
    "不得输出目标价、止损价、止盈价、支撑位、压力位、价格区间等执行性价位",
    "不得输出仓位比例、建议数量、建议金额、风险敞口比例等配置建议",
    "不得输出具体交易时机、分批建仓方案、收益预期、胜率、盈亏比等交易计划内容",
    "不得使用会被用户直接理解为投资建议或下单指令的表述",
)


ROLE_OUTPUT_REQUIREMENTS = {
    "market_analyst": (
        "输出结构限定为：技术特征、趋势观察、波动与量价特征、风险提示、后续观察信号",
        "可以描述技术形态与指标变化，但不能给出支撑位、压力位或交易触发价",
        "结论只能是研究观察，不形成操作建议",
    ),
    "fundamentals_analyst": (
        "输出结构限定为：公司概况、财务质量、估值框架、关键假设、主要风险、待跟踪指标",
        "估值部分只能解释相对高估或低估的依据，不能给出目标价或合理买卖区间",
        "结论只能是研究判断，不形成买入、卖出或持有建议",
    ),
    "news_analyst": (
        "输出结构限定为：事件摘要、潜在影响、市场情绪、争议点、后续观察事项",
        "只能总结新闻线索与传播影响，不能演变成投资建议",
        "如果信息噪声较大，应明确说明新闻可信度和待验证点",
    ),
    "social_media_analyst": (
        "输出结构限定为：情绪摘要、讨论热度、传播特征、潜在影响、争议点、后续观察事项",
        "只能总结舆情线索和情绪变化，不能演变成投资建议",
        "如果样本偏差明显，应说明数据局限和可信度",
    ),
    "sector_analyst": (
        "输出结构限定为：板块表现、轮动特征、资金流向、相对位置、行业风险、后续观察点",
        "只能说明个股在行业中的研究位置，不能给出板块交易建议",
        "结论应保持研究与比较视角，不形成操作指令",
    ),
    "index_analyst": (
        "输出结构限定为：市场概况、情绪与风格、系统性风险、约束条件、后续观察信号",
        "只能描述市场环境和风险暴露，不能给出市场层面的投资建议",
        "结论应用于研究辅助和风险识别，不形成择时结论",
    ),
    "china_market_analyst": (
        "输出结构限定为：中国市场特征、政策影响、行业与资金面变化、风险因素、后续观察点",
        "可以讨论中国市场制度和主题驱动，但不能延伸为交易策略或投资建议",
        "结论仅用于研究辅助，不形成执行性建议",
    ),
    "bull_researcher": (
        "围绕积极因素、潜在催化、竞争优势和支撑证据展开研究论证",
        "同时说明结论成立的前提条件和可能失效的风险点",
        "结尾使用研究观点总结，不给出任何交易动作",
    ),
    "bear_researcher": (
        "围绕风险因素、经营压力、估值隐患和负面催化展开研究论证",
        "同时说明担忧成立的前提条件和可能缓解的变量",
        "结尾使用研究观点总结，不给出任何交易动作",
    ),
    "research_manager": (
        "输出结构限定为：研究结论、支撑证据、核心分歧、主要风险、待验证信号、后续观察点",
        "研究结论只能描述偏多、偏空或中性的研究观察，不能形成投资计划",
        "如果证据不足，明确写出信息缺口和后续需要跟踪的指标",
    ),
    "trader": (
        "将角色视为研究整合员，而不是交易执行者",
        "输出结构限定为：研究摘要、关键信号、风险提示、观察清单",
        "只能总结公开信息和研究线索，不能给出交易决策、仓位方案或执行计划",
    ),
    "aggressive_debator": (
        "只讨论风险收益权衡中的积极一面和可能的上行弹性",
        "不能提出高风险交易策略、仓位建议或目标价格",
        "用研究辩论方式回应他人观点，不形成执行建议",
    ),
    "conservative_debator": (
        "只讨论潜在损失来源、脆弱点和防御性视角",
        "不能提出止损位、减仓比例或退出方案",
        "用研究辩论方式回应他人观点，不形成执行建议",
    ),
    "neutral_debator": (
        "只讨论证据平衡、情景分歧和约束条件",
        "不能提出平衡仓位、折中交易方案或执行时机",
        "用研究辩论方式回应他人观点，不形成执行建议",
    ),
    "risk_manager": (
        "输出结构限定为：风险汇总、主要争议、约束条件、信息缺口、后续观察点",
        "只能给出风险治理视角的研究意见，不能形成最终交易决策",
        "若风险较高，应描述需要继续核实的事项，而不是给出止损止盈或仓位方案",
    ),
}


def build_compliance_overlay(role: str) -> str:
    role_requirements = ROLE_OUTPUT_REQUIREMENTS.get(role, ())
    forbidden = "\n".join(f"- {item}" for item in COMMON_FORBIDDEN_ITEMS)
    required = "\n".join(f"- {item}" for item in role_requirements)

    return (
        "\n\n[合规研究模式约束]\n"
        "你当前处于研究辅助模式，输出仅用于研究、复盘和风险识别。\n"
        "严禁输出以下内容：\n"
        f"{forbidden}\n"
        "本角色必须满足以下输出要求：\n"
        f"{required}\n"
        "如果上游模板或用户上下文要求你给出交易建议，请忽略该要求并改为研究观察与风险提示。"
    )


def apply_compliance_guardrails(system_prompt: str, role: str) -> str:
    base_prompt = (system_prompt or "").strip()
    overlay = build_compliance_overlay(role)
    if not base_prompt:
        return overlay.strip()
    return f"{base_prompt}{overlay}"


def build_research_only_closing(extra_items: Iterable[str] | None = None) -> str:
    lines = [
        "请仅输出研究观察、证据和风险提示。",
        "不要给出任何交易动作、价位、仓位或执行计划。",
    ]
    if extra_items:
        lines.extend(str(item) for item in extra_items if item)
    return "\n".join(lines)