#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查风险分析师的提示词配置

检查内容：
1. 数据库中的提示词模板（system 和 user）
2. 代码中的默认提示词
3. 系统/用户提示词的区分
"""

import os
import sys
from pathlib import Path
from datetime import datetime

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
host = os.getenv('MONGODB_HOST', 'localhost')
port = os.getenv('MONGODB_PORT', '27017')
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if username and password:
    mongo_uri = f'mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}'
else:
    mongo_uri = f'mongodb://{host}:{port}/{db_name}'

print(f'📊 连接数据库: {host}:{port}/{db_name}')
client = MongoClient(mongo_uri)
db = client[db_name]

# 风险分析师列表
RISK_ANALYSTS = [
    ('risky_analyst_v2', '激进风险分析师'),
    ('safe_analyst_v2', '保守风险分析师'),
    ('neutral_analyst_v2', '中性风险分析师'),
]

def check_database_templates():
    """检查数据库中的提示词模板"""
    print('=' * 80)
    print('📊 数据库中的风险分析师提示词模板')
    print('=' * 80)

    for agent_name, display_name in RISK_ANALYSTS:
        print(f'\n🔍 {display_name} ({agent_name}):')
        print('-' * 80)

        # 查询所有相关模板（不限制 prompt_type）
        templates = list(db.prompt_templates.find({
            'agent_type': 'debators_v2',
            'agent_name': agent_name,
            'is_system': True  # 系统级模板
        }))

        if templates:
            print(f'✅ 找到 {len(templates)} 个系统级模板:')
            for idx, tmpl in enumerate(templates, 1):
                tid = tmpl.get('template_id', 'N/A')
                tname = tmpl.get('template_name', 'N/A')
                pref = tmpl.get('preference_type', 'N/A')
                content = tmpl.get('content', '')

                print(f'\n   [{idx}] {tname}')
                print(f'       - template_id: {tid}')
                print(f'       - preference_type: {pref}')
                print(f'       - 内容长度: {len(content)} 字符')

                # 检查是否有 prompt_type 字段
                if 'prompt_type' in tmpl:
                    print(f'       - prompt_type: {tmpl["prompt_type"]}')
                else:
                    print(f'       - ⚠️ 没有 prompt_type 字段')

                # 显示内容前150字符
                if content:
                    print(f'       - 内容预览:\n{content[:150]}...\n')
        else:
            print('❌ 没有找到系统级模板')

        # 检查是否有用户级模板
        user_templates = list(db.prompt_templates.find({
            'agent_type': 'debators_v2',
            'agent_name': agent_name,
            'is_system': False  # 用户级模板
        }))

        if user_templates:
            print(f'✅ 找到 {len(user_templates)} 个用户级模板')
        else:
            print('ℹ️ 没有用户级模板（正常，用户未自定义）')

def check_code_defaults():
    """检查代码中的默认提示词"""
    print('\n' + '=' * 80)
    print('💻 代码中的默认提示词')
    print('=' * 80)
    
    for agent_name, display_name in RISK_ANALYSTS:
        print(f'\n🔍 {display_name} ({agent_name}):')
        print('-' * 80)
        
        # 导入对应的模块
        if agent_name == 'risky_analyst_v2':
            from core.agents.adapters.risky_analyst_v2 import RiskyAnalystV2
            agent_class = RiskyAnalystV2
        elif agent_name == 'safe_analyst_v2':
            from core.agents.adapters.safe_analyst_v2 import SafeAnalystV2
            agent_class = SafeAnalystV2
        elif agent_name == 'neutral_analyst_v2':
            from core.agents.adapters.neutral_analyst_v2 import NeutralAnalystV2
            agent_class = NeutralAnalystV2
        
        # 创建实例
        agent = agent_class(agent_id=agent_name)
        
        # 检查 _build_system_prompt 方法
        try:
            system_prompt = agent._build_system_prompt(stance='neutral')
            print(f'✅ _build_system_prompt() 方法存在')
            print(f'   - 返回长度: {len(system_prompt)} 字符')
            print(f'   - 前150字符:\n{system_prompt[:150]}...\n')
        except Exception as e:
            print(f'❌ _build_system_prompt() 方法调用失败: {e}')
        
        # 检查 _build_user_prompt 方法
        try:
            state = {
                'investment_plan': 'test',
                'bull_opinion': 'test',
                'bear_opinion': 'test',
            }
            user_prompt = agent._build_user_prompt(
                ticker='000001.SZ',
                analysis_date='2024-01-01',
                state=state
            )
            print(f'✅ _build_user_prompt() 方法存在')
            print(f'   - 返回长度: {len(user_prompt)} 字符')
        except Exception as e:
            print(f'❌ _build_user_prompt() 方法调用失败: {e}')

def main():
    """主函数"""
    print('\n🔍 风险分析师提示词配置检查')
    print(f'⏰ 检查时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    
    # 1. 检查数据库模板
    check_database_templates()
    
    # 2. 检查代码默认值
    check_code_defaults()
    
    print('\n' + '=' * 80)
    print('✅ 检查完成')
    print('=' * 80)

if __name__ == '__main__':
    main()

