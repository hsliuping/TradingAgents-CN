# -*- coding: utf-8 -*-
"""
查看研究经理 v2 的提示词模板
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


def view_research_manager_templates():
    """查看研究经理的所有模板"""
    collection = db['prompt_templates']
    
    templates = collection.find({
        "agent_type": "managers_v2",
        "agent_name": "research_manager_v2"
    })
    
    print("=" * 80)
    print("📋 研究经理 v2 模板列表")
    print("=" * 80)
    
    for idx, template in enumerate(templates, 1):
        print(f"\n{'=' * 80}")
        print(f"模板 #{idx}")
        print(f"{'=' * 80}")
        print(f"ID: {template.get('_id')}")
        print(f"偏好类型: {template.get('preference_type')}")
        print(f"是否系统模板: {template.get('is_system')}")
        print(f"状态: {template.get('status')}")
        print(f"创建时间: {template.get('created_at')}")
        print(f"更新时间: {template.get('updated_at')}")
        
        content = template.get('content', {})
        print(f"\n📝 模板内容字段: {list(content.keys())}")
        
        # 打印每个字段的内容
        for key in ['system_prompt', 'tool_guidance', 'analysis_requirements', 'output_format', 'user_prompt', 'constraints']:
            if key in content:
                value = content[key]
                print(f"\n{'─' * 80}")
                print(f"🔹 {key.upper()}")
                print(f"{'─' * 80}")
                if isinstance(value, str):
                    print(value[:500] + "..." if len(value) > 500 else value)
                else:
                    pprint(value)


def main():
    """主函数"""
    print("🔍 查看研究经理 v2 提示词模板\n")
    view_research_manager_templates()
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()

