#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级复盘分析师 v2.0 模板

包括：
- timing_analyst_v2 (时机分析师)
- position_analyst_v2 (仓位分析师)
- emotion_analyst_v2 (情绪分析师)
- attribution_analyst_v2 (归因分析师)
- review_manager_v2 (复盘总结师)
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
# 复盘分析师模板定义
# ============================================================

REVIEWER_REQUIREMENTS = {
    "timing": """**时机分析要求**:

📊 **买卖时机评估**:
- **买入时机分析**:
  - 买入时的技术位置（支撑位、阻力位、趋势）
  - 买入时的市场环境（大盘、板块、情绪）
  - 买入时机是否合理（是否追高、是否抄底）
  - 更好的买入时机建议

- **卖出时机分析**:
  - 卖出时的技术位置
  - 卖出时的市场环境
  - 卖出时机是否合理（是否恐慌、是否贪婪）
  - 更好的卖出时机建议

📈 **技术指标分析**:
- 买卖时的关键技术指标（MA、MACD、RSI、KDJ等）
- 技术信号是否支持操作
- 技术指标的有效性评估

🎯 **时机评分**:
- 买入时机评分：X/10
- 卖出时机评分：X/10
- 综合时机评分：X/10

💡 **改进建议**:
- 如何选择更好的买入时机
- 如何选择更好的卖出时机
- 时机把握的技巧和方法

🌍 **语言要求**: 所有内容使用中文""",
    
    "position": """**仓位分析要求**:

💰 **仓位管理评估**:
- **仓位配置**:
  - 初始仓位比例是否合理
  - 最大仓位是否超标
  - 仓位与风险承受能力是否匹配

- **加减仓操作**:
  - 加仓时机和幅度是否合理
  - 减仓时机和幅度是否合理
  - 加减仓是否有明确的依据

📊 **资金管理**:
- 单只股票仓位占比
- 资金使用效率
- 是否存在过度集中风险

🎯 **仓位评分**:
- 仓位配置评分：X/10
- 加减仓操作评分：X/10
- 综合仓位评分：X/10

💡 **改进建议**:
- 更合理的仓位配置方案
- 加减仓的优化建议
- 资金管理的改进方向

🌍 **语言要求**: 所有内容使用中文""",
    
    "emotion": """**情绪分析要求**:

😊 **情绪识别**:
- **交易情绪类型**:
  - 是否存在追涨杀跌（FOMO、恐慌）
  - 是否存在贪婪持有（不愿止盈）
  - 是否存在恐慌抛售（不愿止损）
  - 是否存在报复性交易

- **情绪影响**:
  - 情绪对决策的影响程度
  - 情绪导致的损失或错失机会
  - 情绪控制的有效性

📋 **纪律执行**:
- 是否严格执行交易计划
- 是否遵守止损止盈规则
- 是否存在随意改变计划的情况

🎯 **情绪评分**:
- 情绪控制评分：X/10
- 纪律执行评分：X/10
- 综合情绪评分：X/10

💡 **改进建议**:
- 如何控制交易情绪
- 如何提高纪律执行
- 情绪管理的方法和技巧

🌍 **语言要求**: 所有内容使用中文""",
    
    "attribution": """**归因分析要求**:

📊 **收益归因**:
- **Alpha来源**（超额收益）:
  - 选股能力（基本面、技术面）
  - 择时能力（买卖时机）
  - 运气成分（市场环境、突发事件）

- **Beta来源**（市场收益）:
  - 大盘贡献
  - 板块贡献
  - 系统性收益

📉 **亏损归因**:
- 判断失误（基本面、技术面）
- 时机失误（买卖时机）
- 情绪失误（追涨杀跌、恐慌）
- 运气因素（黑天鹅事件）

🎯 **能力评估**:
- 选股能力评分：X/10
- 择时能力评分：X/10
- 风险控制能力评分：X/10
- 综合能力评分：X/10

💡 **改进建议**:
- 如何提升选股能力
- 如何提升择时能力
- 如何提升风险控制能力

🌍 **语言要求**: 所有内容使用中文""",
    
    "review_manager": """**复盘总结要求**:

📊 **综合评估**:
- **各维度评分汇总**:
  - 时机评分：X/10
  - 仓位评分：X/10
  - 情绪评分：X/10
  - 归因评分：X/10
  - 综合评分：X/10

- **主要问题识别**:
  - 最严重的问题（优先级排序）
  - 问题的根本原因
  - 问题的影响程度

🎯 **核心建议**:
- **短期改进**（立即执行）:
  1. [具体建议1]
  2. [具体建议2]
  3. [具体建议3]

- **长期提升**（持续优化）:
  1. [具体建议1]
  2. [具体建议2]
  3. [具体建议3]

💡 **行动计划**:
- 下一步操作建议
- 需要学习的知识
- 需要改进的习惯

🌍 **语言要求**: 所有内容使用中文"""
}


def update_reviewers():
    """更新复盘分析师模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("=" * 80)
    print("更新复盘分析师模板")
    print("=" * 80)
    
    agents = {
        "timing_analyst_v2": "timing",
        "position_analyst_v2": "position",
        "emotion_analyst_v2": "emotion",
        "attribution_analyst_v2": "attribution",
        "review_manager_v2": "review_manager"
    }
    
    for agent_name, req_type in agents.items():
        # 复盘分析师通常只有 neutral 偏好
        for preference in ["neutral"]:
            result = collection.update_one(
                {
                    "agent_type": "reviewers_v2",
                    "agent_name": agent_name,
                    "preference_type": preference,
                    "is_system": True
                },
                {
                    "$set": {
                        "content.analysis_requirements": REVIEWER_REQUIREMENTS[req_type],
                        "updated_at": datetime.now()
                    }
                }
            )
            if result.modified_count > 0:
                print(f"✅ 更新: {agent_name} / {preference}")
                updated_count += 1
            else:
                print(f"⏭️ 无变化: {agent_name} / {preference}")
    
    return updated_count


def main():
    """主函数"""
    print("🔧 升级复盘分析师 v2.0 模板\n")
    
    updated = update_reviewers()
    
    print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()

