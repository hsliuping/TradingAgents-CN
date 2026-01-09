#!/usr/bin/env python
"""
验证 v2.0 分析师模板配置

检查：
1. 数据库中是否存在所有 v2.0 分析师模板
2. 模板内容是否包含详细的 analysis_requirements
3. Agent 适配器是否正确调用 get_agent_prompt
"""

import os
import sys
from pathlib import Path

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

client = MongoClient(mongo_uri)
db = client[db_name]

# v2.0 分析师列表
V2_ANALYSTS = [
    "fundamentals_analyst_v2",
    "market_analyst_v2",
    "news_analyst_v2",
    "social_media_analyst_v2",
    "social_analyst_v2",
    "index_analyst_v2",
    "sector_analyst_v2",
]

PREFERENCES = ["aggressive", "neutral", "conservative"]


def check_database_templates():
    """检查数据库中的模板"""
    print("=" * 80)
    print("📊 检查数据库模板")
    print("=" * 80)
    
    collection = db['prompt_templates']
    total_found = 0
    total_missing = 0
    issues = []
    
    for agent_name in V2_ANALYSTS:
        for preference in PREFERENCES:
            template = collection.find_one({
                "agent_type": "analysts_v2",
                "agent_name": agent_name,
                "preference_type": preference,
                "is_system": True
            })
            
            if template:
                total_found += 1
                # 检查 analysis_requirements 是否存在且不为空
                content = template.get("content", {})
                analysis_req = content.get("analysis_requirements", "")
                
                if not analysis_req or len(analysis_req) < 50:
                    issues.append(f"⚠️ {agent_name}/{preference}: analysis_requirements 太短或为空")
                else:
                    print(f"✅ {agent_name}/{preference}: OK (analysis_requirements: {len(analysis_req)} 字符)")
            else:
                total_missing += 1
                issues.append(f"❌ {agent_name}/{preference}: 模板不存在")
    
    print(f"\n📊 统计:")
    print(f"  - 找到: {total_found} 个模板")
    print(f"  - 缺失: {total_missing} 个模板")
    
    if issues:
        print(f"\n⚠️ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"\n✅ 所有模板配置正确！")
    
    return total_missing == 0 and len(issues) == 0


def check_agent_adapters():
    """检查 Agent 适配器代码"""
    print("\n" + "=" * 80)
    print("🔍 检查 Agent 适配器代码")
    print("=" * 80)
    
    adapters_dir = project_root / "core" / "agents" / "adapters"
    issues = []
    
    for agent_name in V2_ANALYSTS:
        adapter_file = adapters_dir / f"{agent_name}.py"
        
        if not adapter_file.exists():
            issues.append(f"❌ {agent_name}: 适配器文件不存在")
            continue
        
        content = adapter_file.read_text(encoding='utf-8')
        
        # 检查是否导入了 get_agent_prompt
        if 'get_agent_prompt' not in content:
            issues.append(f"⚠️ {agent_name}: 未导入 get_agent_prompt")
        
        # 检查是否使用了正确的 agent_type
        if 'agent_type="analysts_v2"' in content or "agent_type='analysts_v2'" in content:
            print(f"✅ {agent_name}: 使用正确的 agent_type (analysts_v2)")
        elif 'agent_type="analysts"' in content or "agent_type='analysts'" in content:
            issues.append(f"❌ {agent_name}: 使用了错误的 agent_type (analysts)")
        else:
            issues.append(f"⚠️ {agent_name}: 未找到 agent_type 调用")
        
        # 检查是否使用了正确的 agent_name
        if f'agent_name="{agent_name}"' in content or f"agent_name='{agent_name}'" in content:
            print(f"✅ {agent_name}: 使用正确的 agent_name ({agent_name})")
        else:
            issues.append(f"⚠️ {agent_name}: 未找到正确的 agent_name")
    
    if issues:
        print(f"\n⚠️ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"\n✅ 所有适配器配置正确！")
    
    return len(issues) == 0


def main():
    """主函数"""
    print("🔍 v2.0 分析师模板验证工具\n")
    
    db_ok = check_database_templates()
    adapter_ok = check_agent_adapters()
    
    print("\n" + "=" * 80)
    print("📊 验证结果")
    print("=" * 80)
    
    if db_ok and adapter_ok:
        print("✅ 所有检查通过！v2.0 分析师配置正确。")
        return 0
    else:
        print("❌ 发现配置问题，请检查上述输出。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

