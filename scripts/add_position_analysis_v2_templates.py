"""
为持仓分析Agent v2.0添加完整模板（2种缓存场景 × 3种风格 = 6个模板/Agent）

基于现有的模板结构，为 pa_technical_v2 和 pa_fundamental_v2 创建：
- with_cache_aggressive, with_cache_neutral, with_cache_conservative
- without_cache_aggressive, without_cache_neutral, without_cache_conservative
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.prompt_template_service import PromptTemplateService
from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.core.database import init_database


# ==================== 技术面分析师 v2.0 模板 ====================

def get_technical_template(cache_scenario: str, style: str) -> dict:
    """获取技术面分析师模板（根据缓存场景和风格）"""
    
    # 风格描述
    style_descriptions = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    
    style_desc = style_descriptions.get(style, style)
    
    # 基础系统提示词
    if cache_scenario == "with_cache":
        system_prompt = f"""您是一位专业的技术面分析师，采用{style_desc}的分析风格。

您的职责是结合单股分析报告和持仓信息，进行持仓视角的技术面分析。

分析要点：
1. 趋势判断 - 结合单股分析报告中的技术面判断，评估当前持仓的技术面状态
2. 支撑阻力 - 关键支撑位和阻力位，重点关注与持仓成本的关系
3. 技术指标 - MACD/KDJ/RSI等指标状态，结合持仓盈亏情况
4. 短期预判 - 未来3-5天可能走势，考虑持仓成本的影响
5. 技术评分 - 1-10分的技术面评分（持仓视角）

请使用中文，基于单股分析报告和持仓信息进行分析。"""
        
        user_prompt = """请基于以下单股技术面分析报告和持仓信息，进行持仓技术面分析：

=== 单股技术面分析报告（参考）===
{{market_report}}

=== 持仓信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 浮动盈亏: {{unrealized_pnl_pct}}

请结合持仓情况（成本价、盈亏等），对技术面进行持仓视角的分析：
1. 当前技术面状态与持仓成本的关系
2. 基于持仓的技术面操作建议
3. 支撑阻力位与持仓成本的关系
4. 短期走势预判（考虑持仓盈亏）
5. 技术面评分（1-10分）"""
    else:
        system_prompt = f"""您是一位专业的技术面分析师，采用{style_desc}的分析风格。

您的职责是基于持仓信息直接进行技术面分析。

分析要点：
1. 趋势判断 - 当前处于上升/下降/震荡趋势
2. 支撑阻力 - 关键支撑位和阻力位
3. 技术指标 - MACD/KDJ/RSI等指标状态
4. 短期预判 - 未来3-5天可能走势
5. 技术评分 - 1-10分的技术面评分

请使用中文，基于真实数据进行分析。"""
        
        user_prompt = """请分析以下持仓股票的技术面：

=== 持仓信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 浮动盈亏: {{unrealized_pnl_pct}}

=== 市场数据 ===
{{market_data_summary}}

=== 技术指标 ===
{{technical_indicators}}

请撰写详细的技术面分析报告，包括：
1. 趋势判断
2. 支撑阻力位
3. 技术指标分析
4. 短期走势预判
5. 技术面评分（1-10分）"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "技术分析重点：关注短线趋势和买卖信号，重点分析MACD金叉/死叉信号，KDJ超买超卖区域判断，突破关键阻力位的力度"
        constraints = "重点关注短期趋势变化，强调突破和反转信号，评估标准偏向短线交易"
    elif style == "conservative":
        tool_guidance = "技术分析重点：关注中长期趋势和形态，重点分析周线和月线走势，识别重要支撑位防守，关注风险信号和预警"
        constraints = "重点关注中长期趋势，强调风险和支撑位，评估标准偏向保守稳健"
    else:  # neutral
        tool_guidance = "技术分析重点：综合分析趋势和形态，客观评估技术指标状态，平衡考虑多空因素，识别关键价格区域"
        constraints = "保持客观中性，综合考虑多空因素，不偏向任何一方"
    
    return {
        "template_name": f"技术面分析师 v2.0 - {style_desc}风格 ({'有缓存' if cache_scenario == 'with_cache' else '无缓存'})",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 分析要求\n1. **趋势判断**: 当前处于上升/下降/震荡趋势\n2. **支撑阻力**: 关键支撑位和阻力位\n3. **技术指标**: MACD/KDJ/RSI等指标状态\n4. **走势预判**: 未来可能走势\n5. **技术评分**: 1-10分的技术面评分",
            output_format="请用简洁专业的语言客观分析。",
            constraints=constraints
        )
    }


# ==================== 基本面分析师 v2.0 模板 ====================

def get_fundamental_template(cache_scenario: str, style: str) -> dict:
    """获取基本面分析师模板（根据缓存场景和风格）"""
    
    # 风格描述
    style_descriptions = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    
    style_desc = style_descriptions.get(style, style)
    
    # 基础系统提示词
    if cache_scenario == "with_cache":
        system_prompt = f"""您是一位专业的基本面分析师，采用{style_desc}的分析风格。

您的职责是结合单股分析报告和持仓信息，进行持仓视角的基本面分析。

分析要点：
1. 财务状况 - 结合单股分析报告中的基本面分析，评估当前持仓的基本面状态
2. 估值水平 - PE/PB/PEG等估值指标，重点关注与持仓成本的关系
3. 行业地位 - 竞争优势和市场份额，结合持仓周期评估
4. 成长性 - 未来增长潜力，考虑持仓目标
5. 基本面评分 - 1-10分的基本面评分（持仓视角）

请使用中文，基于单股分析报告和持仓信息进行分析。"""
        
        user_prompt = """请基于以下单股基本面分析报告和持仓信息，进行持仓基本面分析：

=== 单股基本面分析报告（参考）===
{{fundamentals_report}}

=== 持仓信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 所属行业: {{industry}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 持仓天数: {{holding_days}} 天

请结合持仓情况（成本价、持仓天数等），对基本面进行持仓视角的分析：
1. 当前基本面状态与持仓成本的关系
2. 基于持仓的基本面操作建议
3. 估值水平与持仓成本的关系
4. 成长性判断（考虑持仓周期）
5. 基本面评分（1-10分）"""
    else:
        system_prompt = f"""您是一位专业的基本面分析师，采用{style_desc}的分析风格。

您的职责是基于持仓信息直接进行基本面分析。

分析要点：
1. 财务状况 - 营收、利润、现金流分析
2. 估值水平 - PE/PB/PEG等估值指标
3. 行业地位 - 竞争优势和市场份额
4. 成长性 - 未来增长潜力
5. 基本面评分 - 1-10分的基本面评分

请使用中文，基于真实数据进行分析。"""
        
        user_prompt = """请分析以下持仓股票的基本面：

=== 持仓信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 所属行业: {{industry}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 持仓天数: {{holding_days}} 天

请撰写详细的基本面分析报告，包括：
1. 财务状况分析
2. 估值水平评估
3. 行业地位分析
4. 成长性判断
5. 基本面评分（1-10分）"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "基本面分析重点：关注业绩增长速度，重点分析成长性指标，评估行业竞争地位，关注未来增长潜力"
        constraints = "重点关注成长性，接受较高估值，评估标准偏向成长股"
    elif style == "conservative":
        tool_guidance = "基本面分析重点：关注财务稳健性，重点分析估值安全边际，评估分红和现金流，关注资产负债表质量"
        constraints = "重点关注安全性，强调估值合理性，评估标准偏向价值投资"
    else:  # neutral
        tool_guidance = "基本面分析重点：综合分析财务数据，客观评估估值水平，平衡考虑风险收益，全面分析竞争格局"
        constraints = "保持客观中性，综合考虑各因素，不偏向任何风格"
    
    return {
        "template_name": f"基本面分析师 v2.0 - {style_desc}风格 ({'有缓存' if cache_scenario == 'with_cache' else '无缓存'})",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 分析要求\n1. **财务状况**: 营收、利润、现金流分析\n2. **估值水平**: PE/PB/PEG等估值指标\n3. **行业地位**: 竞争优势和市场份额\n4. **成长性**: 未来增长潜力\n5. **基本面评分**: 1-10分的基本面评分",
            output_format="请用简洁专业的语言客观分析。",
            constraints=constraints
        )
    }


# ==================== 模板创建函数 ====================

async def create_template(service: PromptTemplateService, agent_name: str, preference_id: str, template_data: dict) -> bool:
    """创建模板"""
    try:
        template_create = PromptTemplateCreate(
            agent_type="position_analysis_v2",  # 与工作流ID保持一致
            agent_name=agent_name,
            preference_type=preference_id,  # 例如：with_cache_aggressive
            template_name=template_data["template_name"],
            content=template_data["content"],
            remark=f"{template_data['template_name']} - v2.0系统模板",
            status="active",
        )

        # 检查是否已存在
        existing = await service.get_system_templates(
            agent_type="position_analysis_v2",  # 与工作流ID保持一致
            agent_name=agent_name,
            preference_type=preference_id
        )

        if existing:
            print(f"⏭️  跳过: {agent_name}/{preference_id} - 已存在")
            return False

        await service.create_template(template_create)
        print(f"✅ 创建: {agent_name}/{preference_id} - {template_data['template_name']}")
        return True

    except Exception as e:
        print(f"❌ 创建失败: {agent_name}/{preference_id} - {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """初始化v2.0 Agent的完整模板"""
    print("🚀 开始为持仓分析Agent v2.0添加完整模板...")
    print("🔄 正在初始化数据库连接...")

    await init_database()
    print("✅ 数据库连接初始化完成\n")

    service = PromptTemplateService()

    created_count = 0
    skipped_count = 0

    # 缓存场景和风格组合
    cache_scenarios = ["with_cache", "without_cache"]
    styles = ["aggressive", "neutral", "conservative"]
    
    # 定义所有Agent
    all_agents = [
        ("pa_technical_v2", get_technical_template, "技术面分析师 v2.0"),
        ("pa_fundamental_v2", get_fundamental_template, "基本面分析师 v2.0"),
    ]

    for agent_name, template_func, display_name in all_agents:
        print(f"\n📌 初始化{display_name}({agent_name})模板...")
        
        # 为每个缓存场景和风格组合创建模板
        for cache_scenario in cache_scenarios:
            for style in styles:
                # 组合preference_id：缓存场景_风格偏好
                preference_id = f"{cache_scenario}_{style}"
                
                # 获取模板数据
                template_data = template_func(cache_scenario, style)
                
                if await create_template(service, agent_name, preference_id, template_data):
                    created_count += 1
                else:
                    skipped_count += 1

    print(f"\n🎉 初始化完成！")
    print(f"✅ 创建: {created_count} 个模板")
    print(f"⏭️  跳过: {skipped_count} 个模板")

    print(f"\n📋 已创建的模板（2种缓存场景 × 3种风格 = 6个模板/Agent）:")
    print(f"   📈 pa_technical_v2 (技术面分析师 v2.0) - 6个模板")
    print(f"   📊 pa_fundamental_v2 (基本面分析师 v2.0) - 6个模板")
    print(f"   总计: 12个模板")


if __name__ == "__main__":
    asyncio.run(main())

