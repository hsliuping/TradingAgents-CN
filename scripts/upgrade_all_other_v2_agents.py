#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级所有其他 v2.0 Agent 模板

包括：
1. 风险分析师 (risky_analyst_v2, safe_analyst_v2, neutral_analyst_v2)
2. 交易员 (trader_v2)
3. 管理员 (research_manager_v2, risk_manager_v2)

注意：由于模板内容较多，这里使用简化版本，重点是增加 analysis_requirements 的详细程度
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


# 通用的详细 analysis_requirements 模板
RISK_ANALYST_REQUIREMENTS = {
    "risky": """**激进风险分析要求**:

📈 **收益潜力评估**:
- 最大收益预期和上涨空间
- 收益实现路径和催化剂
- 最佳收益情景分析

⚖️ **风险收益比**:
- 预期收益 vs 潜在风险
- 风险可控性评估
- 是否值得承担风险

💰 **仓位建议**（激进风格）:
- 建议仓位：60%-80%
- 加仓时机和策略
- 止盈止损设置

⚠️ **风险提示**:
- 主要风险因素
- 风险应对措施

🎯 **交易建议**:
- 买入价位、目标价位、止损位
- 操作策略和时机

🌍 **语言要求**: 所有内容使用中文，建议使用：重仓、加仓、激进买入""",
    
    "safe": """**保守风险分析要求**:

🛡️ **风险识别**（重点关注）:
- 财务风险、经营风险、市场风险
- 潜在损失评估
- 最坏情景分析

📉 **下行风险评估**:
- 最大可能损失
- 支撑位有效性
- 破位后果

💰 **仓位建议**（保守风格）:
- 建议仓位：20%-40%
- 分批建仓策略
- 严格止损设置

✅ **安全边际**:
- 要求的安全边际（至少30%）
- 保守买入价位
- 风险控制措施

🎯 **交易建议**:
- 保守买入价位、止损位
- 风险控制策略

🌍 **语言要求**: 所有内容使用中文，建议使用：谨慎买入、小仓位、严格止损""",
    
    "neutral": """**中性风险分析要求**:

⚖️ **风险收益平衡**:
- 客观评估收益潜力
- 全面识别风险因素
- 风险收益比计算

📊 **综合评估**:
- 技术面、基本面、情绪面
- 支撑位和阻力位
- 趋势和动能

💰 **仓位建议**（中性风格）:
- 建议仓位：40%-60%
- 分批建仓策略
- 合理止盈止损

🎯 **交易建议**:
- 合理买入价位区间
- 目标价位和止损位
- 操作策略

🌍 **语言要求**: 所有内容使用中文，建议使用：买入、持有、适度配置"""
}

TRADER_REQUIREMENTS = """**交易计划制定要求**:

📋 **交易计划要素**:
1. **买入策略**:
   - 买入价位（最佳价位、可接受价位区间）
   - 买入时机（技术信号、催化剂）
   - 分批建仓计划（首次仓位、加仓条件）

2. **仓位管理**:
   - 初始仓位比例
   - 加仓/减仓条件
   - 最大仓位限制

3. **风险控制**:
   - 止损位设置（价格止损、时间止损）
   - 止损幅度（建议5%-15%）
   - 风险敞口控制

4. **止盈策略**:
   - 目标价位（短期、中期、长期）
   - 分批止盈计划
   - 止盈条件（价格、时间、事件）

5. **持仓周期**:
   - 预期持仓时间
   - 定期复盘频率
   - 退出条件

📊 **交易计划格式**:
- 使用表格清晰展示
- 包含具体数字和百分比
- 明确操作条件和触发点

🌍 **语言要求**: 所有内容使用中文，使用：买入、卖出、止损、止盈"""

MANAGER_REQUIREMENTS = {
    "research": """**研究总结要求**:

📊 **多空观点汇总**:
- 看多核心观点和支撑数据
- 看空核心观点和风险因素
- 观点分歧点和共识点

⚖️ **综合判断**:
- 多空力量对比
- 市场共识 vs 分歧
- 投资价值评估

🎯 **投资建议**:
- 综合投资建议（买入/持有/卖出）
- 建议理由和逻辑
- 关键风险提示

🌍 **语言要求**: 所有内容使用中文""",
    
    "risk": """**风险评估总结要求**:

⚖️ **风险观点汇总**:
- 激进观点（收益潜力）
- 保守观点（风险因素）
- 中性观点（平衡评估）

📊 **综合风险评估**:
- 整体风险等级（高/中/低）
- 主要风险因素
- 风险可控性

🎯 **最终建议**:
- 综合仓位建议
- 风险控制措施
- 操作策略

🌍 **语言要求**: 所有内容使用中文"""
}


def update_risk_analysts():
    """更新风险分析师模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("=" * 80)
    print("更新风险分析师模板")
    print("=" * 80)
    
    # 激进风险分析师
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "debators_v2",
                "agent_name": "risky_analyst_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": RISK_ANALYST_REQUIREMENTS["risky"],
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: risky_analyst_v2 / {preference}")
            updated_count += 1
    
    # 保守风险分析师
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "debators_v2",
                "agent_name": "safe_analyst_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": RISK_ANALYST_REQUIREMENTS["safe"],
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: safe_analyst_v2 / {preference}")
            updated_count += 1
    
    # 中性风险分析师
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "debators_v2",
                "agent_name": "neutral_analyst_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": RISK_ANALYST_REQUIREMENTS["neutral"],
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: neutral_analyst_v2 / {preference}")
            updated_count += 1
    
    return updated_count


def update_trader():
    """更新交易员模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("\n" + "=" * 80)
    print("更新交易员模板 (trader_v2)")
    print("=" * 80)
    
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "trader_v2",
                "agent_name": "trader_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": TRADER_REQUIREMENTS,
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: trader_v2 / {preference}")
            updated_count += 1
    
    return updated_count


def update_managers():
    """更新管理员模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("\n" + "=" * 80)
    print("更新管理员模板")
    print("=" * 80)
    
    # 研究管理员
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "managers_v2",
                "agent_name": "research_manager_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": MANAGER_REQUIREMENTS["research"],
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: research_manager_v2 / {preference}")
            updated_count += 1
    
    # 风险管理员
    for preference in ["aggressive", "neutral", "conservative"]:
        result = collection.update_one(
            {
                "agent_type": "managers_v2",
                "agent_name": "risk_manager_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": MANAGER_REQUIREMENTS["risk"],
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: risk_manager_v2 / {preference}")
            updated_count += 1
    
    return updated_count


def main():
    """主函数"""
    print("🔧 升级其他 v2.0 Agent 模板\n")
    
    total_updated = 0
    
    # 1. 更新风险分析师
    total_updated += update_risk_analysts()
    
    # 2. 更新交易员
    total_updated += update_trader()
    
    # 3. 更新管理员
    total_updated += update_managers()
    
    print(f"\n✅ 完成！共更新 {total_updated} 个模板")


if __name__ == "__main__":
    main()

