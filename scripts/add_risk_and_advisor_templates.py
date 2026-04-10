"""
为持仓分析Agent v2.0添加风险分析和研究整合的完整模板（2种缓存场景 × 3种风格 = 6个模板/Agent）

为 pa_risk_v2 和 pa_advisor_v2 创建研究判断模式模板：
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
2. 主要风险来源 - 识别当前最重要的技术、基本面和市场风险
3. 风险情景 - 哪些公开变化会使研究判断转弱或需要重评
4. 波动风险 - 参考单股分析报告中的风险分析，结合市场数据和技术面分析，评估股票波动性
5. 风险等级 - 综合单股分析报告中的风险分析、技术面、基本面和市场风险，给出风险等级评定（低/中/高）

严格要求：禁止输出止损止盈、参考价位、目标价、仓位调整建议。

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
2. 主要风险来源与触发情景（说明哪些公开变化需要警惕）
3. 波动风险分析（参考单股分析报告中的风险分析，结合持仓周期）
4. 风险等级评定（综合单股分析报告中的风险分析、技术面、基本面和持仓风险，低/中/高）
5. 后续观察事项（列出需要继续跟踪的公开信号）

禁止输出风险控制参考价位、收益预期参考价位、止损止盈或具体仓位建议。"""
    else:  # without_cache
        system_prompt = f"""您是一位专业的风险评估师，采用{style_desc}的风险管理风格。

您的职责是基于持仓信息、技术面分析和基本面分析，进行持仓风险评估。

分析要点：
1. 风险敞口评估 - 评估当前持仓的风险敞口
2. 主要风险来源 - 识别当前最重要的风险项
3. 风险情景 - 哪些公开变化会使研究判断转弱或需要重评
4. 波动风险 - 评估股票波动性
5. 风险等级 - 给出风险等级评定（低/中/高）

严格要求：禁止输出止损止盈、参考价位、目标价、仓位调整建议。

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
2. 主要风险来源与触发情景
3. 波动风险分析
4. 风险等级评定（低/中/高）
5. 后续观察事项

禁止输出风险控制参考价位、收益预期参考价位、止损止盈或具体仓位建议。"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "风险评估重点：在较积极的假设下评估主要脆弱点与改善条件，但不输出执行性价格或动作建议"
        constraints = "重点关注收益机会，但禁止输出参考价位、仓位和交易动作"
    elif style == "conservative":
        tool_guidance = "风险评估重点：严格评估风险，以保护本金为首要目标，强调风险来源与重评条件"
        constraints = "重点关注风险控制，禁止输出参考价位、仓位和交易动作"
    else:  # neutral
        tool_guidance = "风险评估重点：平衡风险与收益，客观评估风险敞口、波动来源与后续验证重点"
        constraints = "保持客观中性，平衡风险与收益，不输出执行动作或价格位"
    
    return {
        "template_name": f"风险评估师 v2.0 - {style_desc}风格 ({'有缓存' if cache_scenario == 'with_cache' else '无缓存'})",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 风险评估要求\n1. **风险敞口评估**: 评估当前持仓的风险敞口\n2. **主要风险来源**: 识别当前最重要的风险项\n3. **风险情景**: 哪些公开变化会使研究判断转弱或需要重评\n4. **波动风险**: 评估股票波动性\n5. **风险等级**: 给出风险等级评定（低/中/高）\n6. **后续观察事项**: 列出需要继续跟踪的公开信号",
            output_format="请用简洁专业的语言客观评估风险。",
            constraints=constraints
        )
    }


# ==================== 持仓研究整合师 v2.0 模板 ====================

def get_advisor_template(style: str) -> dict:
    """获取持仓研究整合师模板（只需要风格，不需要缓存场景）
    
    持仓研究整合师是根据技术面、基本面、风险分析的结果做综合判断，
    和缓存没有关系，所以只需要风格偏好（neutral/aggressive/conservative）
    """
    
    # 风格描述
    style_descriptions = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    
    style_desc = style_descriptions.get(style, style)
    
    # 基础系统提示词（整合师不需要区分缓存场景）
    system_prompt = f"""您是一位专业的持仓研究整合师，采用{style_desc}的研究风格。

您的职责是综合技术面分析、基本面分析和风险评估，形成持仓研究判断与后续观察事项。

分析要点：
1. 综合研究判断 - 基于技术面、基本面和风险评估，给出偏强/中性/偏弱/待验证观点
2. 核心证据 - 说明当前判断最重要的事实依据
3. 风险边界 - 说明最需要警惕的风险来源与情景变化
4. 潜在催化 - 说明哪些因素可能改善或恶化研究判断
5. 后续观察事项 - 给出需要继续跟踪的公开验证信号
6. 信心度 - 基于分析质量，给出信心度评分（0-100分）

严格要求：禁止输出买卖建议、加减仓、目标价、价格区间、止损止盈、仓位比例。

请使用中文，基于技术面分析、基本面分析和风险评估进行综合分析。"""
    
    user_prompt = """请基于以下技术面分析、基本面分析、风险评估和持仓信息，给出持仓研究判断：

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
- 可承受波动参考: {stop_loss}%

请综合各维度分析，给出持仓研究判断，包括：
1. 综合研究判断（偏强/中性/偏弱/待验证）
2. 核心证据与判断理由
3. 主要风险来源与风险提醒
4. 潜在催化与改善条件
5. 后续观察事项（公开验证信号）
6. 信心度评分（0-100分）

禁止输出买卖建议、加减仓、目标价、价格区间、止损止盈、仓位比例。"""
    
    # 风格相关的指导
    if style == "aggressive":
        tool_guidance = "研究整合重点：在较积极的假设下识别核心证据与催化因素，但不输出执行性价格或动作建议"
        constraints = "重点关注收益机会，但禁止输出交易动作、价格位和仓位建议"
    elif style == "conservative":
        tool_guidance = "研究整合重点：严格评估风险，以保护本金为首要目标，强调风险边界与重评条件"
        constraints = "重点关注风险控制，禁止输出交易动作、价格位和仓位建议"
    else:  # neutral
        tool_guidance = "研究整合重点：平衡风险与收益，客观评估各维度分析，综合考虑技术面、基本面和风险因素"
        constraints = "保持客观中性，平衡风险与收益，不输出执行动作或价格位"
    
    return {
        "template_name": f"持仓研究整合师 v2.0 - {style_desc}风格",
        "content": TemplateContent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements="## 分析要求\n1. **综合研究判断**: 偏强/中性/偏弱/待验证\n2. **核心证据**: 当前判断的关键事实依据\n3. **风险边界**: 当前最重要的风险来源与情景变化\n4. **潜在催化**: 可能改善或恶化判断的因素\n5. **后续观察事项**: 需要继续跟踪的公开验证信号\n6. **信心度**: 0-100分",
            output_format="请用简洁专业的语言给出持仓研究判断与观察事项。",
            constraints=constraints
        )
    }


# ==================== 模板创建函数 ====================

async def create_template(service: PromptTemplateService, agent_name: str, preference_id: str, template_data: dict) -> bool:
    """同步模板"""
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

        result, operation = await service.upsert_system_template(
            template_create,
            remark_suffix="[2026-04-11] 幂等同步持仓风险与整合模板",
        )
        if not result:
            print(f"❌ 同步失败: {agent_name}/{preference_id} - {operation}")
            return False

        action_text = {"created": "创建", "updated": "更新", "unchanged": "保持"}.get(operation, operation)
        print(f"✅ {action_text}: {agent_name}/{preference_id} - {template_data['template_name']}")
        return True

    except Exception as e:
        print(f"❌ 创建失败: {agent_name}/{preference_id} - {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """初始化风险分析和研究整合的完整模板"""
    print("🚀 开始为持仓分析Agent v2.0添加风险分析和研究整合的完整模板...")
    print("🔄 正在初始化数据库连接...")

    await init_database()
    print("✅ 数据库连接初始化完成\n")

    service = PromptTemplateService()

    synced_count = 0
    failed_count = 0

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
                synced_count += 1
            else:
                failed_count += 1
    
    # 持仓研究整合师：只需要风格偏好（3种风格 = 3个模板）
    print(f"\n📌 初始化持仓研究整合师 v2.0 (pa_advisor_v2) 模板...")
    for style in styles:
        # preference_id 就是风格偏好（不需要缓存场景）
        preference_id = style
        
        # 获取模板数据
        template_data = get_advisor_template(style)
        
        if await create_template(service, "pa_advisor_v2", preference_id, template_data):
            synced_count += 1
        else:
            failed_count += 1

    print(f"\n🎉 初始化完成！")
    print(f"✅ 已同步: {synced_count} 个模板")
    print(f"❌ 失败: {failed_count} 个模板")

    print(f"\n📋 已创建的模板:")
    print(f"   ⚠️  pa_risk_v2 (风险评估师 v2.0) - 2种缓存场景 × 3种风格 = 6个模板")
    print(f"   💡 pa_advisor_v2 (持仓研究整合师 v2.0) - 3种风格 = 3个模板")
    print(f"   总计: 9个模板")


if __name__ == "__main__":
    asyncio.run(main())
