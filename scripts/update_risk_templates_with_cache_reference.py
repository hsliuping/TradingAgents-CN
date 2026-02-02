"""
更新数据库中已有的风险分析师模板，添加对单股分析报告中风险分析部分的引用说明

更新 with_cache 场景的模板，明确说明如何使用缓存中的单股分析报告的风险分析部分
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_mongo_db_sync
from app.utils.timezone import now_tz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_updated_risk_template_content(cache_scenario: str, style: str) -> dict:
    """获取更新后的风险分析师模板内容（根据缓存场景和风格）"""
    
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

您的职责是结合单股分析报告中的风险经理决策报告、技术面分析、基本面分析和持仓信息，进行持仓风险评估。

**重要说明**：单股分析报告中的风险经理决策报告（risk_management_decision）是风险经理（投资组合经理）的综合决策报告，包含了激进、保守、中性风险分析师的多角度风险评估和最终风险决策。您需要参考这份报告中的风险分析观点，结合持仓情况进行持仓视角的风险评估。

分析要点：
1. 风险敞口评估 - 结合单股分析报告中的风险经理决策报告、技术面和基本面分析，评估当前持仓的风险敞口
2. 风险控制参考 - 参考单股分析报告中的风险经理决策报告，结合技术面支撑位和基本面估值，设置风险控制参考价位（仅供参考）
3. 收益预期参考 - 基于技术面阻力位和基本面估值，设置收益预期参考价位（仅供参考）
4. 波动风险 - 参考单股分析报告中的风险经理决策报告，结合市场数据和技术面分析，评估股票波动性
5. 风险等级 - 综合单股分析报告中的风险经理决策报告、技术面、基本面和市场风险，给出风险等级评定（低/中/高）

请使用中文，基于单股分析报告中的风险经理决策报告、技术面分析、基本面分析和持仓信息进行风险评估。"""
        
        user_prompt = """请基于以下单股分析报告中的风险经理决策报告、技术面分析、基本面分析和持仓信息，进行持仓风险评估：

=== 单股分析报告中的风险经理决策报告（参考）===
{risk_management_decision}

**说明**：以上是单股分析中风险经理（投资组合经理）的综合决策报告，包含了激进、保守、中性风险分析师的多角度风险评估和最终风险决策。请参考这份报告中的风险分析观点，结合持仓情况进行持仓视角的风险评估。

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

请结合单股分析报告中的风险经理决策报告、技术面和基本面分析结果，撰写详细的风险评估报告，包括：
1. 风险敞口评估（参考单股分析报告中的风险经理决策报告，结合持仓情况）
2. 风险控制参考价位（参考单股分析报告中的风险经理决策报告，结合技术面支撑位和持仓成本，仅供参考）
3. 收益预期参考价位（基于技术面阻力位和基本面估值，仅供参考）
4. 波动风险分析（参考单股分析报告中的风险经理决策报告，结合持仓周期）
5. 风险等级评定（综合单股分析报告中的风险经理决策报告、技术面、基本面和持仓风险，低/中/高）"""
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
    
    # 根据缓存场景设置不同的分析要求
    if cache_scenario == "with_cache":
        analysis_requirements = "## 风险评估要求\n1. **风险敞口评估**: 参考单股分析报告中的风险经理决策报告，结合持仓情况评估当前持仓的风险敞口\n2. **风险控制参考**: 参考单股分析报告中的风险经理决策报告，结合技术面支撑位和持仓成本，设置风险控制参考价位（仅供参考）\n3. **收益预期参考**: 基于技术面阻力位和基本面估值，设置收益预期参考价位（仅供参考）\n4. **波动风险**: 参考单股分析报告中的风险经理决策报告，结合持仓周期评估股票波动性\n5. **风险等级**: 综合单股分析报告中的风险经理决策报告、技术面、基本面和持仓风险，给出风险等级评定（低/中/高）"
    else:  # without_cache
        analysis_requirements = "## 风险评估要求\n1. **风险敞口评估**: 评估当前持仓的风险敞口\n2. **风险控制参考**: 设置风险控制参考价位（仅供参考）\n3. **收益预期参考**: 设置收益预期参考价位（仅供参考）\n4. **波动风险**: 评估股票波动性\n5. **风险等级**: 给出风险等级评定（低/中/高）"
    
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "tool_guidance": tool_guidance,
        "analysis_requirements": analysis_requirements,
        "output_format": "请用简洁专业的语言客观评估风险。",
        "constraints": constraints
    }


def update_risk_templates():
    """更新数据库中已有的风险分析师模板"""
    db = get_mongo_db_sync()
    templates_collection = db.prompt_templates
    
    # 需要更新的模板：with_cache 场景的所有风格
    cache_scenarios = ["with_cache"]
    styles = ["aggressive", "neutral", "conservative"]
    
    updated_count = 0
    not_found_count = 0
    
    for cache_scenario in cache_scenarios:
        for style in styles:
            preference_id = f"{cache_scenario}_{style}"
            
            # 查找现有模板
            template = templates_collection.find_one({
                "agent_type": "position_analysis_v2",
                "agent_name": "pa_risk_v2",
                "preference_type": preference_id,
                "is_system": True,
                "status": "active"
            })
            
            if template:
                # 获取更新后的模板内容
                updated_content = get_updated_risk_template_content(cache_scenario, style)
                
                # 更新模板的 content 字段
                update_result = templates_collection.update_one(
                    {"_id": template["_id"]},
                    {
                        "$set": {
                            "content": updated_content,
                            "updated_at": now_tz(),
                            "version": template.get("version", 1) + 1
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    logger.info(f"✅ 更新模板: pa_risk_v2/{preference_id}")
                    updated_count += 1
                else:
                    logger.warning(f"⚠️ 模板未修改: pa_risk_v2/{preference_id}")
            else:
                logger.warning(f"⚠️ 模板不存在: pa_risk_v2/{preference_id}")
                not_found_count += 1
    
    print(f"\n🎉 更新完成！")
    print(f"✅ 更新: {updated_count} 个模板")
    print(f"⚠️  未找到: {not_found_count} 个模板")
    
    if updated_count > 0:
        print(f"\n📋 已更新的模板:")
        print(f"   ⚠️  pa_risk_v2 (风险评估师 v2.0) - with_cache 场景的 3 个风格模板")
        print(f"   总计: {updated_count} 个模板")


if __name__ == "__main__":
    print("🚀 开始更新风险分析师模板...")
    print("🔄 正在连接数据库...")
    
    update_risk_templates()
    
    print("\n✅ 更新完成！")
