"""更新复盘分析师的提示词模板，添加交易计划规则支持"""
from pymongo import MongoClient
from bson import ObjectId

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

print("=" * 80)
print("更新 reviewers_v2 类型的提示词模板 - 添加交易计划规则支持")
print("=" * 80)

# 定义要添加的交易计划规则部分（可选，只在有交易计划时显示）
TRADING_PLAN_SECTION_TIMING = """
{trading_plan_section}"""

TRADING_PLAN_SECTION_POSITION = """
{trading_plan_section}"""

TRADING_PLAN_SECTION_MANAGER = """
{trading_plan_section}"""

# 更新时机分析师 v2.0
print("\n" + "=" * 80)
print("更新时机分析师 v2.0")
print("=" * 80)

timing_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'timing_analyst_v2'
})

for template in timing_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')
    
    print(f"\n更新模板: {template_id} (偏好: {preference})")
    
    content = template.get('content', {})
    
    # 在 analysis_requirements 末尾添加交易计划规则检查
    if 'analysis_requirements' in content:
        original = content['analysis_requirements']
        
        # 检查是否已经包含交易计划相关内容
        if '{trading_plan_section}' not in original:
            updated = original + TRADING_PLAN_SECTION_TIMING
            
            db.prompt_templates.update_one(
                {'_id': template_id},
                {'$set': {'content.analysis_requirements': updated}}
            )
            print(f"  ✅ 已添加交易计划规则占位符")
        else:
            print(f"  ⏭️  已包含交易计划规则占位符，跳过")

# 更新仓位分析师 v2.0
print("\n" + "=" * 80)
print("更新仓位分析师 v2.0")
print("=" * 80)

position_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'position_analyst_v2'
})

for template in position_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')
    
    print(f"\n更新模板: {template_id} (偏好: {preference})")
    
    content = template.get('content', {})
    
    # 在 analysis_requirements 末尾添加交易计划规则检查
    if 'analysis_requirements' in content:
        original = content['analysis_requirements']
        
        # 检查是否已经包含交易计划相关内容
        if '{trading_plan_section}' not in original:
            updated = original + TRADING_PLAN_SECTION_POSITION
            
            db.prompt_templates.update_one(
                {'_id': template_id},
                {'$set': {'content.analysis_requirements': updated}}
            )
            print(f"  ✅ 已添加交易计划规则占位符")
        else:
            print(f"  ⏭️  已包含交易计划规则占位符，跳过")

# 更新复盘总结师 v2.0
print("\n" + "=" * 80)
print("更新复盘总结师 v2.0")
print("=" * 80)

manager_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'review_manager_v2'
})

for template in manager_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')
    
    print(f"\n更新模板: {template_id} (偏好: {preference})")
    
    content = template.get('content', {})
    
    # 在 analysis_requirements 末尾添加交易计划规则检查
    if 'analysis_requirements' in content:
        original = content['analysis_requirements']
        
        # 检查是否已经包含交易计划相关内容
        if '{trading_plan_section}' not in original:
            updated = original + TRADING_PLAN_SECTION_MANAGER
            
            db.prompt_templates.update_one(
                {'_id': template_id},
                {'$set': {'content.analysis_requirements': updated}}
            )
            print(f"  ✅ 已添加交易计划规则占位符")
        else:
            print(f"  ⏭️  已包含交易计划规则占位符，跳过")

print("\n" + "=" * 80)
print("更新完成！")
print("=" * 80)
print("\n说明：")
print("- 已在所有 reviewers_v2 模板的 analysis_requirements 字段中添加 {trading_plan_section} 占位符")
print("- 当有交易计划时，Agent 会传递具体的规则文本")
print("- 当没有交易计划时，Agent 会传递空字符串，占位符不显示任何内容")

