"""
更新提示词模板，添加权重功能说明

更新以下Agent的user_prompt模板：
1. bull_researcher_v2 (researchers_v2/bull_researcher_v2)
2. bear_researcher_v2 (researchers_v2/bear_researcher_v2)
3. research_manager_v2 (managers_v2/research_manager_v2)
4. pa_advisor_v2 (position_analysis_v2/pa_advisor_v2)

权重功能说明：
- 在user_prompt中明确说明各报告的权重
- 提示LLM根据权重重点关注高权重报告
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from bson import ObjectId

# 数据库连接
MONGO_URI = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
DB_NAME = 'tradingagents'

# 需要更新的Agent配置
AGENTS_TO_UPDATE = [
    {
        "agent_type": "researchers_v2",
        "agent_name": "bull_researcher_v2",
        "display_name": "看涨研究员 v2.0",
        "update_user_prompt": True,  # 需要更新user_prompt
    },
    {
        "agent_type": "researchers_v2",
        "agent_name": "bear_researcher_v2",
        "display_name": "看跌研究员 v2.0",
        "update_user_prompt": True,
    },
    {
        "agent_type": "managers_v2",
        "agent_name": "research_manager_v2",
        "display_name": "研究经理 v2.0",
        "update_user_prompt": True,
    },
    {
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_advisor_v2",
        "display_name": "操作建议师 v2.0",
        "update_user_prompt": True,
    },
]


def get_weight_instruction_for_researchers() -> str:
    """
    获取研究员（看涨/看跌）的权重说明
    
    注意：权重信息会在代码中动态添加到user_prompt中，
    这里只是说明权重功能的存在，不需要在模板中硬编码权重值。
    """
    return """
**权重说明**：
- 系统会根据您选择的分析师自动计算各报告的权重
- 短线交易：技术分析权重40%，新闻分析权重30%，社媒分析权重30%，其他报告权重较低
- 中长线投资：基本面分析权重50%，板块分析权重30%，其他报告权重较低
- 请重点关注高权重报告，这些报告对投资决策更重要
- 低权重报告仅作为补充参考，不应过度依赖
- 在综合判断时，请根据权重给予相应的关注度
"""


def get_weight_instruction_for_research_manager() -> str:
    """
    获取研究经理的权重说明
    """
    return """
**权重说明**：
- 看涨观点和看跌观点权重相等（各50%），请同等重视
- 请客观权衡双方观点，基于证据做出理性决策
- 系统会在提示词中明确标注各观点的权重，请根据权重给予相应的关注度
"""


def get_weight_instruction_for_action_advisor() -> str:
    """
    获取操作建议师的权重说明
    """
    return """
**权重说明**：
- 技术面分析权重40%，基本面分析权重30%，风险评估权重30%
- 请重点关注高权重分析，这些分析对操作决策更重要
- 在综合判断时，请根据权重给予相应的关注度
"""


def update_template_user_prompt(
    collection,
    agent_type: str,
    agent_name: str,
    weight_instruction: str,
    preference_type: str = None
):
    """
    更新模板的user_prompt字段，添加权重说明
    
    Args:
        collection: MongoDB集合
        agent_type: Agent类型
        agent_name: Agent名称
        weight_instruction: 权重说明文本
        preference_type: 偏好类型（可选）
    """
    query = {
        "agent_type": agent_type,
        "agent_name": agent_name,
        "is_system": True,
        "status": "active"
    }
    
    if preference_type:
        query["preference_type"] = preference_type
    
    templates = collection.find(query)
    updated_count = 0
    
    for template in templates:
        template_id = template.get("_id")
        pref_type = template.get("preference_type", "N/A")
        
        print(f"  更新模板: {template_id} (偏好: {pref_type})")
        
        # 获取现有的content
        content = template.get("content", {})
        current_user_prompt = content.get("user_prompt", "")
        
        # 检查是否已经包含权重说明（避免重复更新）
        if "权重说明" in current_user_prompt or "权重" in current_user_prompt:
            print(f"    [SKIP] 模板已包含权重说明，跳过")
            continue
        
        # 在user_prompt末尾添加权重说明
        # 注意：权重说明应该添加到模板的末尾，因为实际的权重信息会在代码中动态插入
        # 这里只是添加一个通用的权重说明
        updated_user_prompt = current_user_prompt.rstrip() + "\n\n" + weight_instruction.strip()
        
        # 更新模板
        result = collection.update_one(
            {"_id": template_id},
            {
                "$set": {
                    "content.user_prompt": updated_user_prompt,
                    "updated_at": datetime.now(),
                    "version": template.get("version", 1) + 1
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"    [OK] 已更新 user_prompt (版本: {template.get('version', 1) + 1})")
            updated_count += 1
        else:
            print(f"    [WARN] 更新失败")
    
    return updated_count


def main():
    """主函数"""
    print("=" * 80)
    print("更新提示词模板，添加权重功能说明")
    print("=" * 80)
    
    # 连接数据库
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db.prompt_templates
    
    total_updated = 0
    
    # 更新每个Agent的模板
    for agent_config in AGENTS_TO_UPDATE:
        agent_type = agent_config["agent_type"]
        agent_name = agent_config["agent_name"]
        display_name = agent_config["display_name"]
        
        print(f"\n{'=' * 80}")
        print(f"更新 {display_name} ({agent_type}/{agent_name})")
        print(f"{'=' * 80}")
        
        # 根据Agent类型选择权重说明
        if "researcher" in agent_name:
            weight_instruction = get_weight_instruction_for_researchers()
        elif "research_manager" in agent_name:
            weight_instruction = get_weight_instruction_for_research_manager()
        elif "advisor" in agent_name or "pa_advisor" in agent_name:
            weight_instruction = get_weight_instruction_for_action_advisor()
        else:
            print(f"  [WARN] 未知的Agent类型，跳过")
            continue
        
        # 更新所有偏好类型的模板
        preference_types = [None, "aggressive", "neutral", "conservative"]
        
        for pref_type in preference_types:
            updated = update_template_user_prompt(
                collection,
                agent_type,
                agent_name,
                weight_instruction,
                pref_type
            )
            total_updated += updated
        
        print(f"\n[OK] {display_name} 更新完成")
    
    print(f"\n{'=' * 80}")
    print(f"更新完成！共更新 {total_updated} 个模板")
    print(f"{'=' * 80}")
    print("\n说明：")
    print("- 权重信息会在代码中动态添加到user_prompt中")
    print("- 模板中的权重说明只是通用说明，实际的权重值由代码计算")
    print("- 如果模板已包含权重说明，将跳过更新（避免重复）")
    print("\n下一步：")
    print("1. 重启后端服务")
    print("2. 测试权重功能是否正常工作")
    print("3. 检查生成的提示词是否包含权重信息")
    
    client.close()


if __name__ == "__main__":
    main()

