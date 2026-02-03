"""
批量更新 prompt_templates 集合中的所有记录
将"最终交易决策"替换为"最终分析结果"

使用方法:
    python scripts/update_prompt_templates_final_decision.py
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def update_prompt_templates():
    """更新所有 prompt_templates 记录，将"最终交易决策"替换为"最终分析结果" """
    
    print("=" * 60)
    print("批量更新 prompt_templates 集合")
    print("将'最终交易决策'替换为'最终分析结果'")
    print("=" * 60)
    print()
    
    # 连接 MongoDB
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collection = db['prompt_templates']
    
    # 查询所有记录
    print("📊 查询所有 prompt_templates 记录...")
    all_templates = list(collection.find({}))
    total_count = len(all_templates)
    print(f"✅ 找到 {total_count} 条记录")
    print()
    
    if total_count == 0:
        print("⚠️ 没有找到任何记录，退出")
        client.close()
        return
    
    # 需要检查的字段列表
    content_fields = [
        'system_prompt',
        'user_prompt',
        'tool_guidance',
        'analysis_requirements',
        'output_format',
        'constraints'
    ]
    
    updated_count = 0
    modified_templates = []
    
    # 遍历所有记录
    for template in all_templates:
        template_id = template.get('_id')
        agent_type = template.get('agent_type', '')
        agent_name = template.get('agent_name', '')
        template_name = template.get('template_name', '')
        
        content = template.get('content', {})
        if not isinstance(content, dict):
            print(f"⚠️ 跳过记录 {template_id}: content 不是字典类型")
            continue
        
        # 检查每个字段并构建更新数据
        update_data = {}
        has_changes = False
        
        for field in content_fields:
            field_value = content.get(field)
            if field_value and isinstance(field_value, str):
                if '最终交易决策' in field_value:
                    new_value = field_value.replace('最终交易决策', '最终分析结果')
                    update_data[f'content.{field}'] = new_value
                    has_changes = True
                    print(f"  📝 {agent_type}/{agent_name}/{template_name}: {field} 字段需要更新")
        
        # 如果有更新，执行更新操作
        if has_changes:
            update_data['updated_at'] = datetime.utcnow()
            
            result = collection.update_one(
                {'_id': template_id},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                updated_count += 1
                modified_templates.append({
                    'id': str(template_id),
                    'agent_type': agent_type,
                    'agent_name': agent_name,
                    'template_name': template_name,
                    'updated_fields': list(update_data.keys())
                })
                print(f"  ✅ 已更新: {agent_type}/{agent_name}/{template_name}")
            else:
                print(f"  ⚠️ 更新失败: {agent_type}/{agent_name}/{template_name}")
        
        print()  # 空行分隔
    
    # 输出统计信息
    print("=" * 60)
    print("更新完成")
    print("=" * 60)
    print(f"总记录数: {total_count}")
    print(f"已更新记录数: {updated_count}")
    print(f"未更新记录数: {total_count - updated_count}")
    print()
    
    if modified_templates:
        print("已更新的模板列表:")
        for i, tmpl in enumerate(modified_templates, 1):
            print(f"  {i}. {tmpl['agent_type']}/{tmpl['agent_name']}/{tmpl['template_name']}")
            print(f"     更新字段: {', '.join(tmpl['updated_fields'])}")
        print()
    
    client.close()
    print("✅ 更新完成！")


if __name__ == '__main__':
    try:
        update_prompt_templates()
    except Exception as e:
        print(f"❌ 更新失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
