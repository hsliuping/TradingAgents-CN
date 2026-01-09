#!/usr/bin/env python
"""
导出 v1.x 模板内容用于参考
"""

import os
import sys
from pathlib import Path
import json

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


def export_v1_templates():
    """导出 v1.x 模板"""
    collection = db['prompt_templates']
    
    # 需要导出的 v1.x Agent
    agents_to_export = [
        'bull_researcher',
        'bear_researcher',
        'trader',
        'position_advisor',
        'aggressive_debator',
        'conservative_debator',
        'neutral_debator',
    ]
    
    print("=" * 100)
    print("导出 v1.x 模板内容")
    print("=" * 100)
    
    for agent_name in agents_to_export:
        template = collection.find_one({
            'agent_name': agent_name,
            'is_system': True
        })
        
        if template:
            print(f"\n{'=' * 100}")
            print(f"Agent: {agent_name}")
            print(f"Template: {template.get('template_name', 'N/A')}")
            print(f"Agent Type: {template.get('agent_type', 'N/A')}")
            print(f"{'=' * 100}")
            
            content = template.get('content', {})
            
            # System Prompt
            system_prompt = content.get('system_prompt', '')
            print(f"\n📋 System Prompt ({len(system_prompt)} 字符):")
            print("-" * 100)
            print(system_prompt)
            
            # User Prompt
            user_prompt = content.get('user_prompt', '')
            if user_prompt:
                print(f"\n📝 User Prompt ({len(user_prompt)} 字符):")
                print("-" * 100)
                print(user_prompt)
            
            # Analysis Requirements
            analysis_req = content.get('analysis_requirements', '')
            if analysis_req:
                print(f"\n📊 Analysis Requirements ({len(analysis_req)} 字符):")
                print("-" * 100)
                print(analysis_req)
            
            # Output Format
            output_format = content.get('output_format', '')
            if output_format:
                print(f"\n📄 Output Format ({len(output_format)} 字符):")
                print("-" * 100)
                print(output_format)
            
            # Tool Guidance
            tool_guidance = content.get('tool_guidance', '')
            if tool_guidance:
                print(f"\n🔧 Tool Guidance ({len(tool_guidance)} 字符):")
                print("-" * 100)
                print(tool_guidance)
        else:
            print(f"\n⚠️ 未找到: {agent_name}")


def main():
    """主函数"""
    print("🔍 导出 v1.x 模板内容\n")
    export_v1_templates()


if __name__ == "__main__":
    main()

