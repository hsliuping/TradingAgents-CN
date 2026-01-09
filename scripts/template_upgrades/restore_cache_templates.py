#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
恢复 with_cache 和 without_cache 模板

这些模板用于区分是否有缓存的单股分析报告：
- with_cache: 有缓存报告，提示词会引导 Agent 结合缓存报告进行分析
- without_cache: 无缓存报告，提示词会引导 Agent 直接基于持仓信息分析
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
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


# ============================================================
# 缓存场景模板定义
# ============================================================

CACHE_TEMPLATES = {
    "pa_technical_v2": {
        "with_cache": """## 分析要求（有缓存报告）

📊 **结合单股分析报告**:
- 参考单股技术面分析报告中的趋势判断
- 结合持仓成本价，评估当前技术位置
- 分析持仓盈亏与技术面的关系

📈 **持仓视角的技术分析**:
1. **趋势判断**: 当前趋势与持仓成本的关系
2. **支撑阻力**: 关键价位与成本价的距离
3. **技术指标**: MACD/KDJ/RSI状态（持仓视角）
4. **走势预判**: 未来3-5天走势（考虑持仓盈亏）
5. **技术评分**: 1-10分（持仓视角）

🎯 **操作建议**: 基于技术面，是否适合继续持有/加仓/减仓

🌍 **语言要求**: 所有内容使用中文""",
        
        "without_cache": """## 分析要求（无缓存报告）

📈 **直接技术面分析**:
1. **趋势判断**: 当前处于上升/下降/震荡趋势
2. **支撑阻力**: 关键支撑位和阻力位
3. **技术指标**: MACD/KDJ/RSI等指标状态
4. **走势预判**: 未来可能走势
5. **技术评分**: 1-10分的技术面评分

📊 **持仓关联**:
- 当前价格与成本价的关系
- 技术面是否支持继续持有
- 关键技术位的操作建议

🌍 **语言要求**: 所有内容使用中文"""
    },
    
    "pa_fundamental_v2": {
        "with_cache": """## 分析要求（有缓存报告）

📊 **结合单股分析报告**:
- 参考单股基本面分析报告中的财务分析
- 结合持仓成本价，评估当前估值水平
- 分析持仓周期与基本面变化的关系

💰 **持仓视角的基本面分析**:
1. **财务状况**: 营收、利润、现金流（结合报告）
2. **估值水平**: PE/PB/PEG与持仓成本的关系
3. **行业地位**: 竞争优势（考虑持仓周期）
4. **成长性**: 未来增长潜力（持仓视角）
5. **基本面评分**: 1-10分（持仓视角）

🎯 **操作建议**: 基于基本面，是否适合继续持有/加仓/减仓

🌍 **语言要求**: 所有内容使用中文""",
        
        "without_cache": """## 分析要求（无缓存报告）

💰 **直接基本面分析**:
1. **财务状况**: 营收、利润、现金流分析
2. **估值水平**: PE/PB/PEG等估值指标
3. **行业地位**: 竞争优势和市场份额
4. **成长性**: 未来增长潜力
5. **基本面评分**: 1-10分的基本面评分

📊 **持仓关联**:
- 当前估值与成本价的关系
- 基本面是否支持继续持有
- 估值水平的操作建议

🌍 **语言要求**: 所有内容使用中文"""
    }
}


def restore_cache_templates():
    """恢复 with_cache 和 without_cache 模板"""
    collection = db['prompt_templates']
    created_count = 0
    
    print("=" * 80)
    print("恢复缓存场景模板")
    print("=" * 80)
    
    agents = ["pa_technical_v2", "pa_fundamental_v2"]
    cache_scenarios = ["with_cache", "without_cache"]
    styles = ["aggressive", "neutral", "conservative"]
    
    for agent_name in agents:
        for cache_scenario in cache_scenarios:
            for style in styles:
                preference_type = f"{cache_scenario}_{style}"
                
                # 检查是否已存在
                existing = collection.find_one({
                    "agent_type": "position_analysis_v2",
                    "agent_name": agent_name,
                    "preference_type": preference_type,
                    "is_system": True
                })
                
                if existing:
                    print(f"⏭️ 已存在: {agent_name} / {preference_type}")
                    continue
                
                # 创建新模板
                template = {
                    "agent_type": "position_analysis_v2",
                    "agent_name": agent_name,
                    "preference_type": preference_type,
                    "template_name": f"{agent_name} - {preference_type}",
                    "version": 2,
                    "source": "system",
                    "is_system": True,
                    "status": "active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "content": {
                        "analysis_requirements": CACHE_TEMPLATES[agent_name][cache_scenario]
                    }
                }
                
                collection.insert_one(template)
                print(f"✅ 创建: {agent_name} / {preference_type}")
                created_count += 1
    
    return created_count


def main():
    """主函数"""
    print("🔧 恢复 with_cache 和 without_cache 模板\n")
    
    created = restore_cache_templates()
    
    print(f"\n✅ 完成！共创建 {created} 个模板")
    print("\n💡 说明:")
    print("  - with_cache: 有缓存报告时使用，引导 Agent 结合缓存报告分析")
    print("  - without_cache: 无缓存报告时使用，引导 Agent 直接分析")


if __name__ == "__main__":
    main()

