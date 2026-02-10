"""验证研究员提示词更新结果"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv('MONGODB_HOST', 'localhost')
port = int(os.getenv('MONGODB_PORT', '27017'))
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if username and password:
    uri = f'mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}'
else:
    uri = f'mongodb://{host}:{port}/{db_name}'

client = MongoClient(uri)
db = client[db_name]

# 查询所有更新的模板
templates = list(db.prompt_templates.find({
    'agent_type': 'researchers_v2',
    'agent_name': {'$in': ['bull_researcher_v2', 'bear_researcher_v2']},
    'is_system': True
}).sort([('agent_name', 1), ('preference_type', 1)]))

print('=' * 80)
print('📋 研究员提示词更新验证')
print('=' * 80)
print()

for tmpl in templates:
    agent_name = tmpl.get('agent_name')
    preference = tmpl.get('preference_type')
    version = tmpl.get('version')
    updated_at = tmpl.get('updated_at')
    
    display_name = '看多研究员' if 'bull' in agent_name else '看空研究员'
    
    print(f'📝 {display_name} - {preference}')
    print(f'   版本: {version}')
    print(f'   更新时间: {updated_at}')
    
    # 检查约束条件
    constraints = tmpl.get('content', {}).get('constraints', '')
    
    # 检查关键词
    has_source_tag = '【】' in constraints
    has_time_constraint = '2023年' in constraints or '2024年' in constraints
    has_example = '示例对比' in constraints
    has_strict_warning = '严格约束' in constraints
    
    print(f'   ✅ 包含来源标注要求: {has_source_tag}')
    print(f'   ✅ 包含时间约束: {has_time_constraint}')
    print(f'   ✅ 包含示例对比: {has_example}')
    print(f'   ✅ 包含严格警告: {has_strict_warning}')
    print()

print('=' * 80)
print(f'✅ 验证完成！共检查 {len(templates)} 个模板')
print('=' * 80)

# 显示一个完整的约束条件示例
print()
print('=' * 80)
print('📄 约束条件示例（看多研究员 - aggressive）')
print('=' * 80)
sample = db.prompt_templates.find_one({
    'agent_type': 'researchers_v2',
    'agent_name': 'bull_researcher_v2',
    'preference_type': 'aggressive'
})

if sample:
    constraints = sample.get('content', {}).get('constraints', '')
    print(constraints)

client.close()

