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
        ("trader_v2", "交易员 v2.0", "交易执行"),
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
        "constraints": f"必须从{pref_label}角度进行分析，保持一致的分析立场。"
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

                    # 保存到数据库（user_id=None表示系统模板）
                    result = await service.create_template(template_data, user_id=None)

                    print(f"    ✅ {preference}: {result.id}")
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

