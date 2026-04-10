"""
初始化v2.0系统模板脚本
为23个v2.0 Agent创建系统模板（每个Agent × 3种偏好 = 69个模板）

使用模板生成函数批量创建，避免重复代码
"""

import asyncio
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

from app.services.prompt_template_service import PromptTemplateService
from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.core.database import init_database, close_database


# v2.0 Agent配置
# 使用独立的v2.0类型名称，与v1.0并行
V2_AGENTS = {
    "analysts_v2": [
        ("fundamentals_analyst_v2", "基本面分析师 v2.0", "get_stock_fundamentals_unified"),
        ("market_analyst_v2", "市场分析师 v2.0", "get_stock_market_data_unified"),
        ("news_analyst_v2", "新闻分析师 v2.0", "get_stock_news_unified"),
        ("social_analyst_v2", "社交媒体分析师 v2.0", "get_stock_sentiment_unified"),
        ("sector_analyst_v2", "板块分析师 v2.0", "get_sector_data"),
        ("index_analyst_v2", "大盘分析师 v2.0", "get_index_data"),
    ],
    "researchers_v2": [
        ("bull_researcher_v2", "看涨研究员 v2.0", "看涨"),
        ("bear_researcher_v2", "看跌研究员 v2.0", "看跌"),
    ],
    "managers_v2": [
        ("research_manager_v2", "研究经理 v2.0", "投资决策"),
        ("risk_manager_v2", "风险管理者 v2.0", "风险评估"),
    ],
    "trader_v2": [
        ("trader_v2", "研究整合员 v2.0", "研究整合"),
    ],
    "debators_v2": [
        ("risky_analyst_v2", "激进风险分析师 v2.0", "激进风险"),
        ("safe_analyst_v2", "保守风险分析师 v2.0", "保守风险"),
        ("neutral_analyst_v2", "中性风险分析师 v2.0", "中性风险"),
    ],
    "reviewers_v2": [
        ("timing_analyst_v2", "时机分析师 v2.0", "时机分析"),
        ("position_analyst_v2", "仓位分析师 v2.0", "仓位分析"),
        ("emotion_analyst_v2", "情绪分析师 v2.0", "情绪分析"),
        ("attribution_analyst_v2", "归因分析师 v2.0", "归因分析"),
        ("review_manager_v2", "复盘总结师 v2.0", "复盘总结"),
    ],
    "position_analysis_v2": [
        ("pa_technical_v2", "技术面分析师 v2.0", "技术面分析"),
        ("pa_fundamental_v2", "基本面分析师 v2.0", "基本面分析"),
        ("pa_risk_v2", "风险评估师 v2.0", "风险评估"),
        ("pa_advisor_v2", "操作建议师 v2.0", "操作建议"),
    ]
}


def generate_template_content(agent_type: str, agent_name: str, display_name: str, context: str, preference: str) -> dict:
    """
    生成模板内容
    
    Args:
        agent_type: Agent类型（analysts_v2, researchers_v2等）
        agent_name: Agent名称（fundamentals_analyst_v2等）
        display_name: 显示名称（基本面分析师等）
        context: 上下文信息（工具名称或分析重点）
        preference: 偏好类型（aggressive, neutral, conservative）
    
    Returns:
        包含system_prompt, tool_guidance, analysis_requirements的字典
    """

    if agent_name == "news_analyst_v2":
        focus_map = {
            "aggressive": ("高敏感度", "更快识别可能强化研究判断的事件催化", "说明催化成立前提、时效性与验证条件", "输出催化、风险与后续观察事项"),
            "neutral": ("中性", "平衡评估新闻、公告与监管事件", "区分短期噪音与中期变量", "输出事件影响路径、信息缺口与观察事项"),
            "conservative": ("保守", "优先识别可能削弱研究判断的风险事件", "关注争议、监管与负面舆情的影响路径", "输出脆弱点、风险与后续观察事项"),
        }
        pref_label, focus1, focus2, focus3 = focus_map[preference]
        return {
            "system_prompt": f"""你是一位{pref_label}的{display_name}。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. {focus1}
2. {focus2}
3. {focus3}
4. 仅输出研究观察、风险提示与验证事项

允许引用真实事件、时间与数字，但不得输出买卖建议、目标价、价格区间、止损止盈或仓位计划。""",
            "tool_guidance": """**工具使用指导**:

1. 必须调用 get_stock_news_unified 获取真实新闻数据
2. 调用参数使用 ticker 与 curr_date
3. 只分析真实返回的事件、公告和监管信息

⚠️ 严格禁止：假设或编造新闻、把事件解读改写成交易建议或价格触发条件。""",
            "analysis_requirements": """**分析要求**:

1. 梳理核心事件事实、时效性和可信度
2. 说明事件如何影响经营、估值预期、行业位置或风险暴露
3. 提炼主要催化、主要风险与后续观察事项

**输出重点**: 事件影响路径、信息缺口、观察信号""",
            "output_format": "使用Markdown格式输出研究报告，按核心事件、影响路径、催化与风险、后续观察事项展开。",
            "constraints": "必须基于真实数据进行分析，禁止输出任何交易建议、价位方案、止损止盈、仓位计划或执行指令。"
        }

    if agent_name == "social_analyst_v2":
        focus_map = {
            "aggressive": ("高敏感度", "更快识别可能强化研究判断的正向情绪变化", "分析热度扩散、观点分歧与情绪共振", "输出值得跟踪的情绪信号与观察事项"),
            "neutral": ("中性", "平衡评估情绪方向、热度与渠道差异", "识别情绪背离、噪音与待验证信号", "输出研究观察、风险提示与观察事项"),
            "conservative": ("保守", "优先识别负面情绪、恐慌扩散与脆弱点", "分析噪音放大与风险外溢可能", "输出风险提示与后续观察事项"),
        }
        pref_label, focus1, focus2, focus3 = focus_map[preference]
        return {
            "system_prompt": f"""你是一位{pref_label}的{display_name}。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. {focus1}
2. {focus2}
3. {focus3}
4. 仅输出研究观察、风险提示与验证事项

允许引用真实情绪指标、讨论热度与文本片段，但不得输出买卖建议、目标价、价格区间、止损止盈或仓位计划。""",
            "tool_guidance": """**工具使用指导**:

1. 必须调用 get_stock_sentiment_unified 获取真实情绪数据
2. 调用参数使用 ticker 与 curr_date
3. 只分析真实返回的情绪指标、讨论主题和观点分歧

⚠️ 严格禁止：假设或编造情绪数据、把情绪变化改写成交易建议或执行指令。""",
            "analysis_requirements": """**分析要求**:

1. 说明情绪方向、热度变化和主要讨论主题
2. 分析不同渠道观点差异、情绪背离与噪音来源
3. 提炼值得跟踪的情绪信号、主要风险与后续观察事项

**输出重点**: 情绪结构、噪音识别、观察信号""",
            "output_format": "使用Markdown格式输出研究报告，按情绪方向、热度变化、背离与噪音、后续观察事项展开。",
            "constraints": "必须基于真实数据进行分析，禁止输出任何交易建议、价位方案、止损止盈、仓位计划或执行指令。"
        }

    if agent_name == "index_analyst_v2":
        focus_map = {
            "aggressive": ("高敏感度", "更快识别可能强化研究判断的宏观催化", "分析流动性改善、风险偏好变化与周期切换信号", "输出关键宏观信号、风险与后续观察事项"),
            "neutral": ("中性", "平衡评估市场环境、流动性条件与系统性风险", "识别风险、催化与信息缺口", "输出研究观察、风险提示与后续观察事项"),
            "conservative": ("保守", "优先识别系统性风险、脆弱点和环境恶化信号", "分析流动性收紧与风险外溢路径", "输出风险提示与后续观察事项"),
        }
        pref_label, focus1, focus2, focus3 = focus_map[preference]
        return {
            "system_prompt": f"""你是一位{pref_label}的{display_name}。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. {focus1}
2. {focus2}
3. {focus3}
4. 仅输出研究观察、风险提示与验证事项

允许引用真实指数点位、资金和指标数据，但不得输出买卖建议、目标位、价格区间、支撑阻力位、止损止盈或仓位配置。""",
            "tool_guidance": """**工具使用指导**:

1. 必须调用指数与市场环境相关工具获取真实数据
2. 只分析真实返回的指数走势、流动性、资金流向和周期信息
3. 说明市场环境如何影响研究判断，而不是生成交易策略

⚠️ 严格禁止：假设或编造市场数据、把指数点位改写成执行性价位或交易建议。""",
            "analysis_requirements": """**分析要求**:

1. 说明市场环境、流动性条件和风险偏好变化
2. 分析系统性风险来源、宏观催化与信息缺口
3. 提炼关键观察信号与后续观察事项

**输出重点**: 市场环境、系统性风险、观察信号""",
            "output_format": "使用Markdown格式输出研究报告，按市场环境、关键信号、风险与后续观察事项展开。",
            "constraints": "必须基于真实数据进行分析，禁止输出任何交易建议、价位方案、止损止盈、仓位配置或执行指令。"
        }

    if agent_name == "sector_analyst_v2":
        focus_map = {
            "aggressive": ("高敏感度", "更快识别可能强化研究判断的行业催化", "分析景气度改善、供需变化与结构分化", "输出行业催化、风险与后续观察事项"),
            "neutral": ("中性", "平衡评估行业景气度、竞争格局与结构变化", "识别风险、催化与信息缺口", "输出研究观察、风险提示与后续观察事项"),
            "conservative": ("保守", "优先识别行业下行风险、结构脆弱点和监管冲击", "分析资金外流与风险外溢路径", "输出风险提示与后续观察事项"),
        }
        pref_label, focus1, focus2, focus3 = focus_map[preference]
        return {
            "system_prompt": f"""你是一位{pref_label}的{display_name}。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. {focus1}
2. {focus2}
3. {focus3}
4. 仅输出研究观察、风险提示与验证事项

允许引用真实行业数据、同比变化和同业对比，但不得输出板块机会、配置建议、防御性配置、安全边际、目标位、止损止盈或仓位计划。""",
            "tool_guidance": """**工具使用指导**:

1. 必须调用行业与板块相关工具获取真实数据
2. 只分析真实返回的行业趋势、同业对比、资金流向和事件影响
3. 说明行业结构变化如何影响研究判断，而不是生成配置方案

⚠️ 严格禁止：假设或编造行业数据、把行业结论改写成配置建议或执行指令。""",
            "analysis_requirements": """**分析要求**:

1. 说明行业景气度、竞争格局与结构变化
2. 分析主要风险来源、催化线索与信息缺口
3. 提炼关键观察信号与后续观察事项

**输出重点**: 行业结构、风险来源、观察信号""",
            "output_format": "使用Markdown格式输出研究报告，按行业景气度、结构变化、风险与后续观察事项展开。",
            "constraints": "必须基于真实数据进行分析，禁止输出任何交易建议、配置方案、止损止盈、仓位计划或执行指令。"
        }
    
    preference_map = {
        "aggressive": ("激进", "发现投资机会", "强调成长潜力", "积极寻找买入理由"),
        "neutral": ("中性", "客观评估", "平衡分析", "提供理性判断"),
        "conservative": ("保守", "评估风险", "强调安全边际", "识别潜在问题")
    }
    
    pref_label, focus1, focus2, focus3 = preference_map[preference]
    
    system_prompt = f"""你是一位{pref_label}的{display_name} v2.0。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. {focus1}
2. {focus2}
3. {focus3}
4. 提供{pref_label}的分析建议

请使用{{currency_name}}（{{currency_symbol}}）进行所有金额表述。"""

    if "analyst" in agent_type:
        tool_guidance = f"""**工具使用指导**:

1. **必须调用工具**: 使用 {{tool_names}} 获取真实数据
2. **数据分析**: 深度分析所有可用数据
3. **{pref_label}视角**: 从{pref_label}角度进行分析

⚠️ **严格要求**: 不允许假设或编造数据！"""
    else:
        tool_guidance = f"""**工具使用指导**:

基于提供的分析报告进行{pref_label}的综合分析。
从{pref_label}角度评估所有信息。"""

    analysis_requirements = f"""**分析要求**:

1. 提供{pref_label}的分析视角
2. {focus2}
3. 提供明确的{pref_label}建议

**输出重点**: {focus2}、{focus3}"""

    return {
        "system_prompt": system_prompt,
        "tool_guidance": tool_guidance,
        "analysis_requirements": analysis_requirements,
        "output_format": "使用Markdown格式输出分析报告",
        "constraints": f"""必须从{pref_label}角度进行分析，保持一致的分析立场。

⚠️ **重要约束**：
- 本报告由AI自动生成，禁止在报告中添加任何署名信息（如"撰写人"、"分析师"、"日期"、"声明"等）
- 禁止生成任何虚假的人名、作者信息或署名
- 报告内容应直接开始，无需添加任何署名、日期或声明信息"""
    }


async def create_v2_templates():
    """创建v2.0系统模板"""
    # 初始化MongoDB连接
    await init_database()

    service = PromptTemplateService()
    
    total = 0
    success = 0
    failed = 0
    
    preferences = ["aggressive", "neutral", "conservative"]
    
    print("=" * 80)
    print("开始创建v2.0系统模板")
    print("=" * 80)
    
    for agent_type, agents in V2_AGENTS.items():
        print(f"\n处理类别: {agent_type}")
        
        for agent_name, display_name, context in agents:
            print(f"\n  Agent: {agent_name} ({display_name})")
            
            for preference in preferences:
                total += 1
                
                try:
                    # 生成模板内容
                    content_dict = generate_template_content(
                        agent_type, agent_name, display_name, context, preference
                    )
                    
                    content = TemplateContent(**content_dict)
                    
                    # 创建模板
                    template_data = PromptTemplateCreate(
                        agent_type=agent_type,
                        agent_name=agent_name,
                        template_name=f"{display_name} - {preference.capitalize()} v2.0",
                        preference_type=preference,
                        content=content,
                        status="active"
                    )

                    result, operation = await service.upsert_system_template(
                        template_data,
                        remark_suffix="[2026-04-11] 幂等同步 v2.0 系统模板",
                    )

                    if not result:
                        raise RuntimeError(f"同步失败: {operation}")

                    action_text = {
                        "created": "创建",
                        "updated": "更新",
                        "unchanged": "保持",
                    }.get(operation, operation)
                    print(f"    ✅ {preference}: {action_text} -> {result.id}")
                    success += 1

                except Exception as e:
                    print(f"    ❌ {preference}: {e}")
                    failed += 1

    print("\n" + "=" * 80)
    print("创建完成")
    print("=" * 80)
    print(f"总数: {total}")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print("=" * 80)

    # 关闭MongoDB连接
    await close_database()


if __name__ == "__main__":
    asyncio.run(create_v2_templates())

