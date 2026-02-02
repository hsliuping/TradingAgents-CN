"""
修复持仓分析提示词模板结构

问题：
1. 旧版模板（aggressive/neutral/conservative）缺少 user_prompt
2. 新版模板（with_cache/without_cache）只有 2 个字段，缺少 system_prompt、user_prompt、tool_guidance、output_format

解决方案：
1. 先为旧版模板补充 user_prompt（基于代码中的降级提示词）
2. 然后为新版模板从旧版模板中提取所有字段，并根据缓存场景调整 user_prompt
3. 更新数据库中的模板结构
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.database import get_mongo_db_sync
from app.utils.timezone import now_tz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_user_prompt_template(agent_name: str, cache_scenario: str) -> str:
    """生成 user_prompt 模板内容
    
    Args:
        agent_name: Agent 名称（pa_technical_v2 或 pa_fundamental_v2）
        cache_scenario: 缓存场景（with_cache 或 without_cache）
    
    Returns:
        user_prompt 模板字符串
    """
    
    if agent_name == "pa_technical_v2":
        if cache_scenario == "with_cache":
            # 有缓存：引用缓存报告进行分析
            return """请基于以下单股技术面分析报告和持仓信息，进行持仓技术面分析：

=== 单股技术面分析报告（参考）===
{market_report}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}
- 持仓天数: {holding_days} 天

请结合持仓情况（成本价、盈亏等），对技术面进行持仓视角的分析：
1. 当前技术面状态与持仓成本的关系
2. 基于持仓的技术面操作建议
3. 支撑阻力位与持仓成本的关系
4. 短期走势预判（考虑持仓盈亏）
5. 技术面评分（1-10分）"""
        else:  # without_cache
            # 无缓存：需要调用工具获取数据，然后结合持仓信息分析
            return """⚠️ **重要提示**：当前没有单股技术面分析报告缓存，需要先调用工具获取市场数据。

## 📊 第一步：调用工具获取市场数据

请调用 **get_stock_market_data_unified** 工具获取以下数据：
- **股票代码**: {code}
- **开始日期**: {analysis_date}（系统会自动扩展到365天历史数据）
- **结束日期**: {analysis_date}

工具将返回：
- K线数据（价格走势、成交量）
- 技术指标（MA、MACD、RSI、KDJ等）
- 支撑阻力位分析

## 📈 第二步：结合持仓信息进行技术面分析

获取工具数据后，请结合以下持仓信息进行分析：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}
- 持仓天数: {holding_days} 天

=== 市场数据（工具返回）===
{market_data_summary}

=== 技术指标（工具返回）===
{technical_indicators}

## 🎯 分析要求

请基于工具获取的市场数据和技术指标，结合持仓情况（成本价、盈亏等），进行持仓视角的技术面分析：

1. **趋势判断**：当前趋势与持仓成本的关系
2. **支撑阻力**：关键价位与成本价的距离
3. **技术指标**：MACD/KDJ/RSI状态（持仓视角）
4. **走势预判**：未来3-5天走势（考虑持仓盈亏）
5. **技术评分**：1-10分的技术面评分（持仓视角）

**注意**：如果工具返回的数据为空或不完整，请重新调用工具获取数据。"""
    
    elif agent_name == "pa_fundamental_v2":
        if cache_scenario == "with_cache":
            # 有缓存：引用缓存报告进行分析
            return """请基于以下单股基本面分析报告和持仓信息，进行持仓基本面分析：

=== 单股基本面分析报告（参考）===
{fundamentals_report}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {industry}
- 成本价: {cost_price}
- 现价: {current_price}
- 持仓天数: {holding_days} 天

请结合持仓情况（成本价、持仓天数等），对基本面进行持仓视角的分析：
1. 当前基本面状态与持仓成本的关系
2. 基于持仓的基本面操作建议
3. 估值水平与持仓成本的关系
4. 成长性判断（考虑持仓周期）
5. 基本面评分（1-10分）"""
        else:  # without_cache
            # 无缓存：需要调用工具获取数据，然后结合持仓信息分析
            return """⚠️ **重要提示**：当前没有单股基本面分析报告缓存，需要先调用工具获取基本面数据。

## 📊 第一步：调用工具获取基本面数据

请调用 **get_stock_fundamentals_unified** 工具获取以下数据：
- **股票代码**: {code}
- **开始日期**: {analysis_date}（可选，工具会自动获取最近数据）
- **结束日期**: {analysis_date}（可选）
- **当前日期**: {analysis_date}（可选）

工具将返回：
- 财务数据（营收、利润、现金流等）
- 估值指标（PE、PB、PEG等）
- 行业对比数据
- 成长性指标

## 📈 第二步：结合持仓信息进行基本面分析

获取工具数据后，请结合以下持仓信息进行分析：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {industry}
- 成本价: {cost_price}
- 现价: {current_price}
- 持仓天数: {holding_days} 天

## 🎯 分析要求

请基于工具获取的基本面数据，结合持仓情况（成本价、持仓天数等），进行持仓视角的基本面分析：

1. **财务状况分析**：营收、利润、现金流与持仓成本的关系
2. **估值水平评估**：当前估值与持仓成本的关系
3. **行业地位分析**：行业地位对持仓价值的影响
4. **成长性判断**：未来增长潜力（考虑持仓周期）
5. **基本面评分**：1-10分的基本面评分（持仓视角）

**注意**：如果工具返回的数据为空或不完整，请重新调用工具获取数据。"""
    
    return ""


def fix_template_structure():
    """修复模板结构"""
    db = get_mongo_db_sync()
    templates_collection = db.prompt_templates
    
    # 需要修复的 Agent
    agents_to_fix = [
        {"agent_type": "position_analysis_v2", "agent_name": "pa_technical_v2"},
        {"agent_type": "position_analysis_v2", "agent_name": "pa_fundamental_v2"},
    ]
    
    # 偏好类型
    preference_types = ["aggressive", "neutral", "conservative"]
    
    for agent_info in agents_to_fix:
        agent_type = agent_info["agent_type"]
        agent_name = agent_info["agent_name"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"处理 Agent: {agent_type}/{agent_name}")
        logger.info(f"{'='*60}")
        
        # 第一步：先修复旧版模板（补充 user_prompt）
        logger.info(f"\n📝 第一步：修复旧版模板（补充 user_prompt）")
        for pref_type in preference_types:
            old_template = templates_collection.find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": pref_type,
                "is_system": True,
                "status": "active"
            })
            
            if old_template:
                fix_old_template(templates_collection, old_template, agent_name)
        
        # 第二步：修复新版模板（从旧版模板提取字段）
        logger.info(f"\n📝 第二步：修复新版模板（从旧版模板提取字段）")
        for pref_type in preference_types:
            # 查找旧版模板（作为源模板）
            old_template = templates_collection.find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": pref_type,
                "is_system": True,
                "status": "active"
            })
            
            if not old_template:
                logger.warning(f"⚠️ 未找到旧版模板: {agent_type}/{agent_name} (preference_type={pref_type})")
                continue
            
            old_content = old_template.get("content", {})
            if not old_content:
                logger.warning(f"⚠️ 旧版模板内容为空: {agent_type}/{agent_name} (preference_type={pref_type})")
                continue
            
            logger.info(f"\n📋 找到旧版模板: {pref_type}")
            logger.info(f"   模板ID: {old_template.get('_id')}")
            logger.info(f"   内容字段: {list(old_content.keys())}")
            
            # 修复 with_cache 模板
            with_cache_pref = f"with_cache_{pref_type}"
            with_cache_template = templates_collection.find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": with_cache_pref,
                "is_system": True,
                "status": "active"
            })
            
            if with_cache_template:
                logger.info(f"\n🔧 修复 with_cache 模板: {with_cache_pref}")
                fix_single_template(
                    templates_collection,
                    with_cache_template,
                    old_content,
                    "with_cache",
                    agent_type,
                    agent_name
                )
            else:
                logger.warning(f"⚠️ 未找到 with_cache 模板: {with_cache_pref}")
            
            # 修复 without_cache 模板
            without_cache_pref = f"without_cache_{pref_type}"
            without_cache_template = templates_collection.find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": without_cache_pref,
                "is_system": True,
                "status": "active"
            })
            
            if without_cache_template:
                logger.info(f"\n🔧 修复 without_cache 模板: {without_cache_pref}")
                fix_single_template(
                    templates_collection,
                    without_cache_template,
                    old_content,
                    "without_cache",
                    agent_type,
                    agent_name
                )
            else:
                logger.warning(f"⚠️ 未找到 without_cache 模板: {without_cache_pref}")


def fix_old_template(collection, template: Dict[str, Any], agent_name: str):
    """修复旧版模板（补充 user_prompt）"""
    template_id = template.get("_id")
    current_content = template.get("content", {})
    
    # 检查是否已有 user_prompt
    if "user_prompt" in current_content and current_content.get("user_prompt"):
        logger.info(f"   ✅ 旧版模板已有 user_prompt，跳过: {template.get('preference_type')}")
        return
    
    logger.info(f"\n🔧 修复旧版模板: {template.get('preference_type')}")
    logger.info(f"   模板ID: {template_id}")
    
    # 生成 user_prompt（使用 without_cache 场景，因为旧版模板不区分缓存）
    user_prompt = get_user_prompt_template(agent_name, "without_cache")
    
    # 更新模板
    new_content = {
        **current_content,
        "user_prompt": user_prompt
    }
    
    update_result = collection.update_one(
        {"_id": template_id},
        {
            "$set": {
                "content": new_content,
                "updated_at": now_tz()
            }
        }
    )
    
    if update_result.modified_count > 0:
        logger.info(f"   ✅ 旧版模板已补充 user_prompt")
        logger.info(f"   user_prompt 长度: {len(user_prompt)}")
    else:
        logger.warning(f"   ⚠️ 旧版模板更新失败")


def get_tool_guidance_template(agent_name: str, cache_scenario: str) -> str:
    """生成 tool_guidance 模板内容
    
    Args:
        agent_name: Agent 名称（pa_technical_v2 或 pa_fundamental_v2）
        cache_scenario: 缓存场景（with_cache 或 without_cache）
    
    Returns:
        tool_guidance 模板字符串
    """
    
    if cache_scenario == "with_cache":
        # 有缓存：基于缓存报告进行分析，不需要工具调用
        return """**工具使用指导**:

当前有单股分析报告缓存，可以直接使用缓存报告进行分析。
无需调用工具，直接基于缓存报告和持仓信息进行持仓视角的分析。"""
    
    else:  # without_cache
        # 无缓存：必须调用工具获取数据
        if agent_name == "pa_technical_v2":
            return """**工具使用指导**:

⚠️ **重要**：当前没有单股技术面分析报告缓存，必须调用工具获取市场数据。

**必须调用的工具**：
- **get_stock_market_data_unified**：获取K线数据和技术指标

**工具调用参数**：
- ticker: {code}（股票代码）
- start_date: {analysis_date}（系统会自动扩展到365天历史数据）
- end_date: {analysis_date}（分析日期）

**工具返回内容**：
- K线数据（价格走势、成交量）
- 技术指标（MA、MACD、RSI、KDJ等）
- 支撑阻力位分析

**调用时机**：
在分析开始前，必须先调用工具获取数据，然后结合持仓信息进行分析。"""
        
        elif agent_name == "pa_fundamental_v2":
            return """**工具使用指导**:

⚠️ **重要**：当前没有单股基本面分析报告缓存，必须调用工具获取基本面数据。

**必须调用的工具**：
- **get_stock_fundamentals_unified**：获取财务数据和估值指标

**工具调用参数**：
- ticker: {code}（股票代码）
- start_date: {analysis_date}（可选，工具会自动获取最近数据）
- end_date: {analysis_date}（可选）
- curr_date: {analysis_date}（可选）

**工具返回内容**：
- 财务数据（营收、利润、现金流等）
- 估值指标（PE、PB、PEG等）
- 行业对比数据
- 成长性指标

**调用时机**：
在分析开始前，必须先调用工具获取数据，然后结合持仓信息进行分析。"""
    
    return ""


def fix_single_template(
    collection,
    template: Dict[str, Any],
    source_content: Dict[str, Any],
    cache_scenario: str,
    agent_type: str,
    agent_name: str
):
    """修复单个模板的结构"""
    template_id = template.get("_id")
    current_content = template.get("content", {})
    
    logger.info(f"   当前模板ID: {template_id}")
    logger.info(f"   当前内容字段数: {len(current_content)}")
    logger.info(f"   当前字段: {list(current_content.keys())}")
    
    # 检查是否已经有完整的结构
    required_fields = ["system_prompt", "user_prompt", "tool_guidance", "analysis_requirements", "output_format"]
    has_all_fields = all(field in current_content for field in required_fields)
    
    if has_all_fields:
        # 即使有所有字段，也要检查是否需要根据缓存场景更新 tool_guidance 和 user_prompt
        logger.info(f"   ⚠️ 模板结构已完整，但需要检查是否需要根据缓存场景更新内容")
    
    # 从源模板中提取内容
    new_content = {
        "system_prompt": current_content.get("system_prompt") or source_content.get("system_prompt", ""),
        "user_prompt": "",  # 将根据缓存场景生成
        "tool_guidance": "",  # 将根据缓存场景生成
        "analysis_requirements": current_content.get("analysis_requirements") or source_content.get("analysis_requirements", ""),
        "output_format": current_content.get("output_format") or source_content.get("output_format", ""),
        "constraints": current_content.get("constraints") or source_content.get("constraints", ""),
    }
    
    # 根据缓存场景生成 user_prompt 和 tool_guidance
    new_content["user_prompt"] = get_user_prompt_template(agent_name, cache_scenario)
    new_content["tool_guidance"] = get_tool_guidance_template(agent_name, cache_scenario)
    
    # 更新模板
    update_result = collection.update_one(
        {"_id": template_id},
        {
            "$set": {
                "content": new_content,
                "updated_at": now_tz()
            }
        }
    )
    
    if update_result.modified_count > 0:
        logger.info(f"   ✅ 模板结构已修复")
        logger.info(f"   新内容字段数: {len(new_content)}")
        logger.info(f"   新字段: {list(new_content.keys())}")
        logger.info(f"   system_prompt 长度: {len(new_content['system_prompt'])}")
        logger.info(f"   user_prompt 长度: {len(new_content['user_prompt'])}")
    else:
        logger.warning(f"   ⚠️ 模板更新失败")


if __name__ == "__main__":
    logger.info("开始修复持仓分析提示词模板结构...")
    try:
        fix_template_structure()
        logger.info("\n✅ 修复完成！")
    except Exception as e:
        logger.error(f"\n❌ 修复失败: {e}", exc_info=True)
