"""
增强研究员提示词 - 防止幻觉和过时数据

更新内容：
1. 加强数据来源约束
2. 要求明确标注来源（使用【】）
3. 禁止使用历史时间标记
4. 禁止编造数据
5. 要求不确定性表达

适用于：
- bull_researcher_v2 (所有 preference_type)
- bear_researcher_v2 (所有 preference_type)
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MongoDB 配置
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', '')
MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', '')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'tradingagents')
MONGODB_AUTH_SOURCE = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

# 构建连接字符串
if MONGODB_USERNAME and MONGODB_PASSWORD:
    mongo_uri = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}?authSource={MONGODB_AUTH_SOURCE}"
else:
    mongo_uri = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}"

print(f"📊 连接数据库: {MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}\n")


# ============================================================
# 增强的约束条件（所有 preference_type 通用）
# ============================================================

ENHANCED_CONSTRAINTS = """**⚠️ 严格约束（违反将导致分析无效）**：

1. **数据来源约束**：
   - ✅ 只能使用用户提示词中提供的分析报告
   - ✅ 每个关键论据必须明确标注数据来源（使用【】标记，如【基本面报告】、【新闻分析】）
   - ❌ 禁止使用 LLM 内部知识或训练数据
   - ❌ 禁止引用报告中未提及的数据

2. **时效性约束**：
   - ✅ 只能使用分析日期（{analysis_date}）之前的数据
   - ❌ 禁止使用"2023年"、"2024年"等历史时间标记
   - ❌ 禁止使用"去年"、"上季度"等模糊时间表述（除非报告中明确提供）
   - ✅ 如需引用时间，使用报告中提供的具体日期

3. **数据完整性约束**：
   - ✅ 如果报告中缺少某项数据，必须明确说明"报告中未提供此数据"
   - ❌ 禁止编造、推测或补充报告中没有的数据
   - ❌ 禁止使用"据了解"、"市场传闻"等无来源表述
   - ✅ 所有数值必须来自报告，不得自行计算或推测

4. **引用格式要求**：
   每个关键论据后必须用【】标注来源，例如：
   - "公司营收增长30%【基本面报告】"
   - "近期发布重大利好消息【新闻分析】"
   - "市场情绪积极【情绪报告】"
   - "技术指标显示超买【市场分析】"
   - 如果某个观点无法找到报告支持，不要提出该观点

5. **不确定性表达**：
   - ✅ 当报告数据不足时，使用"基于现有报告，无法判断..."
   - ✅ 避免使用绝对化表述（如"一定会"、"必然"）
   - ✅ 使用"报告显示"、"数据表明"等客观表述
   - ❌ 不要使用"众所周知"、"显而易见"等主观表述

**示例对比**：

❌ 错误示例：
"该公司2023年业绩优秀，去年营收增长显著，市场传闻将有重大并购。"
（问题：使用历史时间、无来源标注、引用传闻）

✅ 正确示例：
"该公司最新财报显示营收同比增长25%【基本面报告】，近期公告计划收购同行业公司【新闻分析】。"
（优点：有明确来源、使用报告数据、无时间标记）"""


# ============================================================
# 更新函数
# ============================================================

def update_researcher_templates():
    """更新研究员模板的约束条件"""
    
    client = MongoClient(mongo_uri)
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔧 增强研究员提示词 - 防止幻觉和过时数据")
    print("=" * 80)
    print()
    
    # 要更新的 agent
    agents = [
        ("researchers_v2", "bull_researcher_v2", "看多研究员"),
        ("researchers_v2", "bear_researcher_v2", "看空研究员")
    ]
    
    updated_count = 0
    
    for agent_type, agent_name, display_name in agents:
        print(f"\n📝 更新 {display_name} ({agent_name})...")
        
        # 查找所有 preference_type 的模板
        templates = list(collection.find({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "is_system": True
        }))
        
        if not templates:
            print(f"   ⚠️ 未找到模板")
            continue
        
        print(f"   找到 {len(templates)} 个模板")
        
        for tmpl in templates:
            preference = tmpl.get('preference_type', 'neutral')
            
            # 更新约束条件
            result = collection.update_one(
                {'_id': tmpl['_id']},
                {
                    '$set': {
                        'content.constraints': ENHANCED_CONSTRAINTS,
                        'updated_at': datetime.now(),
                        'version': tmpl.get('version', 1) + 1
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"   ✅ 更新 {preference} 版本成功 (版本: {tmpl.get('version', 1)} → {tmpl.get('version', 1) + 1})")
                updated_count += 1
            else:
                print(f"   ⏭️ {preference} 版本未更新（可能内容相同）")
    
    client.close()
    
    print()
    print("=" * 80)
    print(f"✅ 更新完成！共更新 {updated_count} 个模板")
    print("=" * 80)


if __name__ == "__main__":
    update_researcher_templates()

