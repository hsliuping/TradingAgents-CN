"""
为持仓分析Agent v2.0添加风险分析和操作建议的完整模板（2种缓存场景 × 3种风格 = 6个模板/Agent）

为 pa_risk_v2 和 pa_advisor_v2 创建：
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


# ==================== 风险评估师 v2.0 模板 ====================

def get_risk_template(cache_scenario: str, style: str) -> dict:
    """获取风险评估师模板（根据缓存场景和风格）"""
    
    # 风格描述
    style_descriptions = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    
    style_desc = style_descriptions.get(style, style)
    
    # 基础系统提示词
    if cache_scenario == "with_cache":
        system_prompt = f"""您是一位专业的风险评估师，采用{style_desc}的风险管理风格。

您的职责是结合单股分析报告中的风险分析、技术面分析、基本面分析和持仓信息，进行持仓风险评估。

分析要点：
1. 风险敞口评估 - 结合单股分析报告中的风险分析、技术面和基本面分析，评估当前持仓的风险敞口
2. 风险控制参考 - 参考单股分析报告中的风险分析，结合技术面支撑位和基本面估值，设置风险控制参考价位（仅供参考）
3. 收益预期参考 - 基于技术面阻力位和基本面估值，设置收益预期参考价位（仅供参考）
4. 波动风险 - 参考单股分析报告中的风险分析，结合市场数据和技术面分析，评估股票波动性
5. 风险等级 - 综合单股分析报告中的风险分析、技术面、基本面和市场风险，给出风险等级评定（低/中/高）

请使用中文，基于单股分析报告中的风险分析、技术面分析、基本面分析和持仓信息进行风险评估。"""
        
        user_prompt = """请基于以下单股分析报告中的风险分析、技术面分析、基本面分析和持仓信息，进行持仓风险评估：

=== 单股分析报告中的风险分析（参考）===
{risk_report}

=== 技术面分析结果 ===
{technical_analysis}

=== 基本面分析结果 ===
{fundamental_analysis}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {quantity} 股
- 成本价: {cost_price}
- 现价: {current_price}
- 持仓市值: {market_value}
- 浮动盈亏: {unrealized_pnl} ({unrealized_pnl_pct})

=== 资金信息 ===
- 总资产: {total_assets}
- 风险敞口占比: {risk_exposure_ratio}%

请结合单股分析报告中的风险分析、技术面和基本面分析结果，撰写详细的风险评估报告，包括：
1. 风险敞口评估（参考单股分析报告中的风险分析，结合持仓情况）
2. 风险控制参考价位（参考单股分析报告中的风险分析，结合技术面支撑位和持仓成本，仅供参考）
3. 收益预期参考价位（基于技术面阻力位和基本面估值，仅供参考）
4. 波动风险分析（参考单股分析报告中的风险分析，结合持仓周期）
5. 风险等级评定（综合单股分析报告中的风险分析、技术面、基本面和持仓风险，低/中/高）"""
    else:  # without_cache
        system_prompt = f"""您是一位专业的风险评估师，采用{style_desc}的风险管理风格。

您的职责是基于持仓信息、技术面分析和基本面分析，进行持仓风险评估。

分析要点：
1. 风险敞口评估 - 评估当前持仓的风险敞口
2. 风险控制参考 - 设置风险控制参考价位（仅供参考）
3. 收益预期参考 - 设置收益预期参考价位（仅供参考）
4. 波动风险 - 评估股票波动性
5. 风险等级 - 给出风险等级评定（低/中/高）

请使用中文，基于真实数据进行分析。"""
        
        user_prompt = """请基于以下技术面分析、基本面分析和持仓信息，进行持仓风险评估：

=== 技术面分析结果 ===
{technical_analysis}

=== 基本面分析结果 ===
{fundamental_analysis}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {quantity} 股
- 成本价: {cost_price}
- 现价: {current_price}
- 持仓市值: {market_value}
- 浮动盈亏: {unrealized_pnl} ({unrealized_pnl_pct})

=== 资金信息 ===
- 总资产: {total_assets}
- 风险敞口占比: {risk_exposure_ratio}%

=== 市场数据 ===
- 波动性: {volatility}

请撰写详细的风险评估报告，包括：
1. 风险敞口评估
2. 风险控制参考价位（仅供参考）
3. 收益预期参考价位（仅供参考）
4. 波动风险分析
5. 风险等级评定（低/中/高）"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "风险评估重点：在控制风险的前提下追求更高收益，重点关注上行空间，设置相对宽松的风险控制参考"
        constraints = "重点关注收益机会，风险控制相对宽松，评估标准偏向积极"
    elif style == "conservative":
        tool_guidance = "风险评估重点：严格评估风险，以保护本金为首要目标，重点关注下行风险，设置严格的风险控制参考"
        constraints = "重点关注风险控制，强调本金保护，评估标准偏向保守"
    else:  # neutral
        tool_guidance = "风险评估重点：平衡风险与收益，客观评估风险敞口，综合考虑技术面和基本面风险"
        constraints = "保持客观中性，平衡风险与收益，不偏向任何一方"
    
    return {
        "template_name": f"风险评估师 v2.0 - {style_desc}风格 ({'有缓存' if cache_scenario == 'with_cache' else '无缓存'})",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 风险评估要求\n1. **风险敞口评估**: 评估当前持仓的风险敞口\n2. **风险控制参考**: 设置风险控制参考价位（仅供参考）\n3. **收益预期参考**: 设置收益预期参考价位（仅供参考）\n4. **波动风险**: 评估股票波动性\n5. **风险等级**: 给出风险等级评定（低/中/高）",
            output_format="请用简洁专业的语言客观评估风险。",
            constraints=constraints
        )
    }


# ==================== 操作建议师 v2.0 模板 ====================

def get_advisor_template(style: str) -> dict:
    """获取操作建议师模板（只需要风格，不需要缓存场景）
    
    操作建议师是根据技术面、基本面、风险分析的结果做综合判断，
    和缓存没有关系，所以只需要风格偏好（neutral/aggressive/conservative）
    """
    
    # 风格描述
    style_descriptions = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    
    style_desc = style_descriptions.get(style, style)
    
    # 基础系统提示词（操作建议师不需要区分缓存场景）
    system_prompt = f"""您是一位专业的投资顾问，采用{style_desc}的持仓分析观点风格。

您的职责是综合技术面分析、基本面分析和风险评估，给出持仓分析观点和操作建议。

分析要点：
1. 市场观点 - 基于技术面、基本面和风险评估，给出看涨/看跌/中性观点
2. 持仓建议 - 基于综合分析，给出继续持有/增持/减持/清仓建议
3. 价格分析区间 - 基于技术面支撑阻力位和基本面估值，给出价格分析区间
4. 风险控制参考 - 基于风险评估，设置风险控制参考价位（仅供参考）
5. 收益预期参考 - 基于技术面阻力位和基本面估值，设置收益预期参考价位（仅供参考）
6. 信心度 - 基于分析质量，给出信心度评分（1-10分）

请使用中文，基于技术面分析、基本面分析和风险评估进行综合分析。"""
    
    user_prompt = """请基于以下技术面分析、基本面分析、风险评估和持仓信息，给出持仓分析观点和操作建议：

=== 技术面分析结果 ===
{technical_analysis}

=== 基本面分析结果 ===
{fundamental_analysis}

=== 风险评估结果 ===
{risk_analysis}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}

=== 用户目标 ===
- 目标收益: {target_return}%
- 风险控制线: {stop_loss}%

请综合各维度分析，给出持仓分析观点和操作建议，包括：
1. 市场观点（看涨/看跌/中性）
2. 持仓建议（继续持有/增持/减持/清仓）
3. 价格分析区间
4. 风险控制参考价位（仅供参考）
5. 收益预期参考价位（仅供参考）
6. 信心度评分（1-10分）"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "操作建议重点：积极寻找增持机会，重点关注上行空间，设置相对宽松的风险控制参考，强调收益预期"
        constraints = "重点关注收益机会，建议偏向积极，评估标准偏向成长"
    elif style == "conservative":
        tool_guidance = "操作建议重点：严格评估风险，以保护本金为首要目标，设置严格的风险控制参考，强调风险控制"
        constraints = "重点关注风险控制，建议偏向保守，评估标准偏向价值"
    else:  # neutral
        tool_guidance = "操作建议重点：平衡风险与收益，客观评估各维度分析，综合考虑技术面、基本面和风险因素"
        constraints = "保持客观中性，平衡风险与收益，不偏向任何风格"
    
    return {
        "template_name": f"操作建议师 v2.0 - {style_desc}风格",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 分析要求\n1. **市场观点**: 看涨/看跌/中性\n2. **持仓建议**: 继续持有/增持/减持/清仓\n3. **价格分析区间**: 基于技术面和基本面\n4. **风险控制参考**: 风险控制参考价位（仅供参考）\n5. **收益预期参考**: 收益预期参考价位（仅供参考）\n6. **信心度**: 1-10分",
            output_format="请用简洁专业的语言给出持仓分析观点和操作建议。",
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
    """初始化风险分析和操作建议的完整模板"""
    print("🚀 开始为持仓分析Agent v2.0添加风险分析和操作建议的完整模板...")
    print("🔄 正在初始化数据库连接...")

    await init_database()
    print("✅ 数据库连接初始化完成\n")

    service = PromptTemplateService()

    created_count = 0
    skipped_count = 0

    # 缓存场景和风格组合（仅用于风险分析师）
    cache_scenarios = ["with_cache", "without_cache"]
    styles = ["aggressive", "neutral", "conservative"]
    
    # 风险分析师：需要缓存场景和风格组合（2种缓存场景 × 3种风格 = 6个模板）
    print(f"\n📌 初始化风险评估师 v2.0 (pa_risk_v2) 模板...")
    for cache_scenario in cache_scenarios:
        for style in styles:
            # 组合preference_id：缓存场景_风格偏好
            preference_id = f"{cache_scenario}_{style}"
            
            # 获取模板数据
            template_data = get_risk_template(cache_scenario, style)
            
            if await create_template(service, "pa_risk_v2", preference_id, template_data):
                created_count += 1
            else:
                skipped_count += 1
    
    # 操作建议师：只需要风格偏好（3种风格 = 3个模板）
    print(f"\n📌 初始化操作建议师 v2.0 (pa_advisor_v2) 模板...")
    for style in styles:
        # preference_id 就是风格偏好（不需要缓存场景）
        preference_id = style
        
        # 获取模板数据
        template_data = get_advisor_template(style)
        
        if await create_template(service, "pa_advisor_v2", preference_id, template_data):
            created_count += 1
        else:
            skipped_count += 1

    print(f"\n🎉 初始化完成！")
    print(f"✅ 创建: {created_count} 个模板")
    print(f"⏭️  跳过: {skipped_count} 个模板")

    print(f"\n📋 已创建的模板:")
    print(f"   ⚠️  pa_risk_v2 (风险评估师 v2.0) - 2种缓存场景 × 3种风格 = 6个模板")
    print(f"   💡 pa_advisor_v2 (操作建议师 v2.0) - 3种风格 = 3个模板")
    print(f"   总计: 9个模板")


if __name__ == "__main__":
    asyncio.run(main())
