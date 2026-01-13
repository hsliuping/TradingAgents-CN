# -*- coding: utf-8 -*-
"""
分析研究经理 v2 的提示词模板，找出格式冲突问题
"""

import os
import sys
from pathlib import Path
from pprint import pprint

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

from pymongo import MongoClient

# 数据库连接
host = os.getenv('MONGODB_HOST', 'localhost') if 'MONGODB_HOST' in os.environ else 'localhost'
port = os.getenv('MONGODB_PORT', '27017') if 'MONGODB_PORT' in os.environ else '27017'
username = os.getenv('MONGODB_USERNAME', '') if 'MONGODB_USERNAME' in os.environ else ''
password = os.getenv('MONGODB_PASSWORD', '') if 'MONGODB_PASSWORD' in os.environ else ''
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents') if 'MONGODB_DATABASE' in os.environ else 'tradingagents'
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin') if 'MONGODB_AUTH_SOURCE' in os.environ else 'admin'

if username and password:
    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
else:
    mongo_uri = f"mongodb://{host}:{port}/{db_name}"

print(f"📊 连接数据库: {host}:{port}/{db_name}\n")
client = MongoClient(mongo_uri)
db = client[db_name]


def analyze_template(template):
    """分析单个模板，找出格式冲突"""
    content = template.get('content', {})
    preference = template.get('preference_type', 'N/A')
    
    print(f"\n{'=' * 80}")
    print(f"📋 分析模板: {preference} 偏好")
    print(f"{'=' * 80}")
    
    # 1. 检查各个字段
    fields = {
        'system_prompt': content.get('system_prompt', ''),
        'tool_guidance': content.get('tool_guidance', ''),
        'analysis_requirements': content.get('analysis_requirements', ''),
        'output_format': content.get('output_format', ''),
        'user_prompt': content.get('user_prompt', ''),
        'constraints': content.get('constraints', ''),
    }
    
    # 2. 查找格式相关的关键词
    format_keywords = [
        'JSON', 'json', '格式', '输出格式', '格式要求', '必须', '字段', 'action', 
        'confidence', 'target_price', 'reasoning', '买入', '持有', '卖出'
    ]
    
    conflicts = []
    
    # 3. 检查每个字段中的格式要求
    for field_name, field_content in fields.items():
        if not field_content:
            continue
            
        # 查找格式关键词
        found_keywords = []
        for keyword in format_keywords:
            if keyword in field_content:
                found_keywords.append(keyword)
        
        if found_keywords:
            conflicts.append({
                'field': field_name,
                'keywords': found_keywords,
                'content_preview': field_content[:300] + '...' if len(field_content) > 300 else field_content
            })
    
    # 4. 打印分析结果
    print(f"\n📊 字段内容概览:")
    for field_name, field_content in fields.items():
        if field_content:
            print(f"  ✅ {field_name}: {len(field_content)} 字符")
        else:
            print(f"  ⚠️  {field_name}: 空")
    
    print(f"\n🔍 格式要求冲突分析:")
    if conflicts:
        for conflict in conflicts:
            print(f"\n  ⚠️  {conflict['field']} 包含格式要求:")
            print(f"     关键词: {', '.join(conflict['keywords'])}")
            print(f"     内容预览: {conflict['content_preview']}")
    else:
        print("  ✅ 未发现明显的格式冲突")
    
    # 5. 详细打印各个字段
    print(f"\n{'─' * 80}")
    print(f"📝 详细内容:")
    print(f"{'─' * 80}")
    
    for field_name, field_content in fields.items():
        if field_content:
            print(f"\n【{field_name.upper()}】")
            print(f"{'─' * 80}")
            print(field_content)
            print()
    
    return conflicts


def main():
    """主函数"""
    import sys
    
    # 支持命令行参数指定要检查的agent
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "research_manager_v2"
    
    print(f"🔍 分析 {agent_name} 提示词模板\n")
    
    collection = db['prompt_templates']
    
    templates = list(collection.find({
        "agent_type": "managers_v2",
        "agent_name": agent_name
    }))
    
    if not templates:
        print(f"❌ 未找到 {agent_name} 模板")
        return
    
    print(f"找到 {len(templates)} 个模板\n")
    
    all_conflicts = []
    
    for template in templates:
        conflicts = analyze_template(template)
        all_conflicts.extend(conflicts)
    
    # 总结
    print(f"\n{'=' * 80}")
    print(f"📊 总结分析")
    print(f"{'=' * 80}")
    
    if all_conflicts:
        print(f"\n⚠️  发现 {len(all_conflicts)} 个潜在的格式冲突:")
        conflict_fields = {}
        for conflict in all_conflicts:
            field = conflict['field']
            if field not in conflict_fields:
                conflict_fields[field] = []
            conflict_fields[field].extend(conflict['keywords'])
        
        for field, keywords in conflict_fields.items():
            print(f"\n  📌 {field}:")
            print(f"     包含格式关键词: {', '.join(set(keywords))}")
        
        print(f"\n💡 建议:")
        print(f"  1. system_prompt: 只包含角色定义和核心职责，不包含格式要求")
        print(f"  2. output_format: 统一在这里定义所有格式要求（JSON结构、字段说明等）")
        print(f"  3. user_prompt: 只包含任务描述和数据，不包含格式要求")
        print(f"  4. constraints: 只包含约束条件，不包含格式要求")
    else:
        print("\n✅ 未发现明显的格式冲突")
    
    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
    client.close()

