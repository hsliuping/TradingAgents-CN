#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析数据库中的风险分析师提示词

步骤：
1. 从数据库获取所有风险分析师的提示词模板
2. 分析每个模板的内容和结构
3. 识别需要优化的地方
4. 输出详细的分析报告
"""

import os
import sys
from pathlib import Path
from datetime import datetime
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

print(f'📊 连接数据库: {host}:{port}/{db_name}\n')
client = MongoClient(mongo_uri)
db = client[db_name]

# 风险分析师列表
RISK_ANALYSTS = [
    ('risky_analyst_v2', '激进风险分析师'),
    ('safe_analyst_v2', '保守风险分析师'),
    ('neutral_analyst_v2', '中性风险分析师'),
]

def fetch_templates():
    """从数据库获取所有风险分析师的提示词模板"""
    print('=' * 100)
    print('📥 从数据库获取风险分析师提示词模板')
    print('=' * 100)
    
    all_templates = {}
    
    for agent_name, display_name in RISK_ANALYSTS:
        print(f'\n🔍 {display_name} ({agent_name}):')
        print('-' * 100)
        
        # 查询所有相关模板
        templates = list(db.prompt_templates.find({
            'agent_type': 'debators_v2',
            'agent_name': agent_name,
        }).sort('preference_type', 1))
        
        if templates:
            print(f'✅ 找到 {len(templates)} 个模板')
            all_templates[agent_name] = templates
            
            for idx, tmpl in enumerate(templates, 1):
                tid = tmpl.get('template_id', 'N/A')
                tname = tmpl.get('template_name', 'N/A')
                pref = tmpl.get('preference_type', 'N/A')
                is_sys = tmpl.get('is_system', False)
                content = tmpl.get('content', '')
                
                print(f'\n   [{idx}] {tname}')
                print(f'       - template_id: {tid}')
                print(f'       - preference_type: {pref}')
                print(f'       - is_system: {is_sys}')

                # 检查 content 的类型
                if isinstance(content, dict):
                    print(f'       - 内容类型: dict (包含 {len(content)} 个字段)')
                    print(f'       - 内容:\n')
                    print('       ' + '-' * 90)
                    print(f'       {json.dumps(content, ensure_ascii=False, indent=8)}')
                    print('       ' + '-' * 90)
                elif isinstance(content, str):
                    print(f'       - 内容类型: str')
                    print(f'       - 内容长度: {len(content)} 字符')
                    print(f'       - 内容:\n')
                    print('       ' + '-' * 90)
                    # 打印完整内容，每行缩进
                    for line in content.split('\n'):
                        print(f'       {line}')
                    print('       ' + '-' * 90)
                else:
                    print(f'       - 内容类型: {type(content).__name__}')
                    print(f'       - 内容: {content}')
        else:
            print('❌ 没有找到模板')
            all_templates[agent_name] = []
    
    return all_templates

def analyze_templates(all_templates):
    """分析提示词模板，识别需要优化的地方"""
    print('\n' + '=' * 100)
    print('🔍 分析提示词模板')
    print('=' * 100)
    
    issues = []
    
    for agent_name, display_name in RISK_ANALYSTS:
        templates = all_templates.get(agent_name, [])
        
        print(f'\n📋 {display_name} ({agent_name}):')
        print('-' * 100)
        
        if not templates:
            issues.append(f'❌ {agent_name}: 没有任何模板')
            print('❌ 没有任何模板')
            continue
        
        # 检查是否有 neutral 版本（默认版本）
        neutral_template = None
        for tmpl in templates:
            if tmpl.get('preference_type') == 'neutral':
                neutral_template = tmpl
                break
        
        if neutral_template:
            content = neutral_template.get('content', {})
            print(f'✅ 找到 neutral 版本（默认版本）')

            if isinstance(content, dict):
                # 检查各个字段
                system_prompt = content.get('system_prompt', '')
                tool_guidance = content.get('tool_guidance', '')
                constraints = content.get('constraints', '')
                version = neutral_template.get('version', 'N/A')

                print(f'   - 版本: {version}')
                print(f'   - system_prompt 长度: {len(system_prompt)} 字符')
                print(f'   - tool_guidance 长度: {len(tool_guidance)} 字符')

                # 检查 tool_guidance 是否包含具体报告列表
                if '【投资计划】' in tool_guidance or '【大盘环境分析】' in tool_guidance:
                    print(f'   ✅ tool_guidance 包含具体分析报告列表')
                else:
                    print(f'   ❌ tool_guidance 缺少具体分析报告列表')
                    issues.append(f'{agent_name} (neutral): tool_guidance 缺少具体分析报告列表')

                # 检查 constraints 是否正确
                if agent_name == 'risky_analyst_v2' and '激进' in constraints:
                    print(f'   ✅ constraints 正确（激进）')
                elif agent_name == 'safe_analyst_v2' and '保守' in constraints:
                    print(f'   ✅ constraints 正确（保守）')
                elif agent_name == 'neutral_analyst_v2' and '中性' in constraints:
                    print(f'   ✅ constraints 正确（中性）')
                else:
                    print(f'   ❌ constraints 错误: {constraints}')
                    issues.append(f'{agent_name} (neutral): constraints 错误')
            else:
                print(f'   ⚠️ content 不是字典类型')
        else:
            issues.append(f'❌ {agent_name}: 没有 neutral 版本（默认版本）')
            print('❌ 没有 neutral 版本（默认版本）')

    # 输出问题汇总
    print('\n' + '=' * 100)
    print('📝 问题汇总')
    print('=' * 100)

    if issues:
        for issue in issues:
            print(f'  - {issue}')
    else:
        print('✅ 没有发现问题')

    return issues

def save_templates_to_file(all_templates):
    """保存模板到文件，方便查看和对比"""
    output_dir = project_root / 'scripts' / 'template_analysis'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for agent_name, templates in all_templates.items():
        if not templates:
            continue

        output_file = output_dir / f'{agent_name}_templates_{timestamp}.txt'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f'# {agent_name} 提示词模板\n')
            f.write(f'# 导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')

            for idx, tmpl in enumerate(templates, 1):
                tname = tmpl.get('template_name', 'N/A')
                pref = tmpl.get('preference_type', 'N/A')
                version = tmpl.get('version', 'N/A')
                content = tmpl.get('content', {})

                f.write(f'## [{idx}] {tname}\n')
                f.write(f'- preference_type: {pref}\n')
                f.write(f'- version: {version}\n\n')

                if isinstance(content, dict):
                    for key, value in content.items():
                        f.write(f'### {key}\n')
                        f.write(f'{value}\n\n')
                else:
                    f.write(f'### content\n')
                    f.write(f'{content}\n\n')

                f.write('-' * 100 + '\n\n')

        print(f'💾 保存 {agent_name} 的模板到: {output_file}')

def main():
    """主函数"""
    print('\n🔍 风险分析师提示词分析')
    print(f'⏰ 分析时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    # 1. 获取模板
    all_templates = fetch_templates()

    # 2. 分析模板
    issues = analyze_templates(all_templates)

    # 3. 保存到文件
    print('\n' + '=' * 100)
    print('💾 保存模板到文件')
    print('=' * 100)
    save_templates_to_file(all_templates)

    print('\n' + '=' * 100)
    print('✅ 分析完成')
    print('=' * 100)

    if issues:
        print(f'\n⚠️ 发现 {len(issues)} 个问题，需要优化')
    else:
        print('\n✅ 所有模板都符合要求')

if __name__ == '__main__':
    main()


