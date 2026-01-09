#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级风险分析师 v2.0 模板

包括：
- risky_analyst_v2 (激进风险分析师)
- safe_analyst_v2 (保守风险分析师)
- neutral_analyst_v2 (中性风险分析师)
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
# 风险分析师模板定义
# ============================================================

RISK_ANALYST_REQUIREMENTS = {
    "risky": """**激进风险分析要求**:

📈 **收益潜力评估**（重点关注）:
- 最大收益预期和上涨空间分析
- 收益实现路径和催化剂识别
- 最佳收益情景模拟
- 超额收益来源分析

⚖️ **风险收益比分析**:
- 预期收益 vs 潜在风险对比
- 风险可控性评估（技术止损、仓位控制）
- 是否值得承担风险的判断
- 风险补偿是否充分

💰 **仓位建议**（激进风格）:
- 建议仓位：60%-80%（激进配置）
- 加仓时机和条件（突破、放量、利好）
- 止盈策略（分批止盈、移动止盈）
- 仓位动态调整规则

⚠️ **风险提示**:
- 主要风险因素（技术、基本面、市场）
- 风险应对措施（止损、对冲）
- 风险监控指标

🎯 **交易建议**:
- 买入价位（最佳价位、可接受区间）
- 目标价位（短期、中期目标）
- 止损位（相对宽松，-10%至-15%）
- 操作策略和时机选择

🌍 **语言要求**: 
- 所有内容使用中文
- 建议使用：重仓、加仓、激进买入（不使用英文）""",
    
    "safe": """**保守风险分析要求**:

🛡️ **风险识别**（重点关注）:
- 财务风险（负债率、现金流、偿债能力）
- 经营风险（竞争、市场份额、管理层）
- 市场风险（估值、流动性、系统性风险）
- 潜在损失评估（最大回撤、破位风险）

📉 **下行风险评估**:
- 最大可能损失（最坏情景分析）
- 支撑位有效性评估
- 破位后的下跌空间
- 止损失效风险

💰 **仓位建议**（保守风格）:
- 建议仓位：20%-40%（保守配置）
- 分批建仓策略（3-5批次）
- 严格止损设置（-5%至-8%）
- 仓位上限控制

✅ **安全边际要求**:
- 要求的安全边际（至少30%-50%）
- 保守买入价位（远低于合理估值）
- 风险控制措施（止损、对冲、分散）
- 本金保护优先原则

🎯 **交易建议**:
- 保守买入价位（要求足够安全边际）
- 严格止损位（-5%至-8%）
- 风险控制策略（分批、止损、对冲）
- 退出条件（时间、价格、事件）

🌍 **语言要求**: 
- 所有内容使用中文
- 建议使用：谨慎买入、小仓位、严格止损（不使用英文）""",
    
    "neutral": """**中性风险分析要求**:

⚖️ **风险收益平衡**:
- 客观评估收益潜力（基于数据和逻辑）
- 全面识别风险因素（技术、基本面、市场）
- 风险收益比计算（量化评估）
- 期望收益评估（概率加权）

📊 **综合评估**:
- 技术面分析（趋势、支撑阻力、指标）
- 基本面分析（估值、成长性、财务健康）
- 情绪面分析（市场情绪、资金流向）
- 多维度综合判断

💰 **仓位建议**（中性风格）:
- 建议仓位：40%-60%（适中配置）
- 分批建仓策略（2-3批次）
- 合理止盈止损（止损-8%至-10%，止盈+15%至+20%）
- 动态仓位调整

🎯 **交易建议**:
- 合理买入价位区间（基于估值和技术）
- 目标价位和止损位（风险收益比至少1:2）
- 操作策略（分批建仓、动态调整）
- 持仓周期建议

🌍 **语言要求**: 
- 所有内容使用中文
- 建议使用：买入、持有、适度配置（不使用英文）"""
}

RISK_ANALYST_OUTPUT_FORMAT = {
    "risky": """## 🔥 激进风险评估报告

### 一、收益潜力分析
- **最大收益预期**: +XX%
- **目标价位**: ¥XX.XX（短期）/ ¥XX.XX（中期）
- **收益路径**: [实现路径和催化剂]
- **超额收益来源**: [Alpha来源分析]

### 二、风险收益比
- **预期收益**: +XX%
- **潜在风险**: -XX%
- **风险收益比**: X:X
- **评估结论**: 值得承担 / 风险过高

### 三、交易建议
- **操作建议**: 激进买入 / 重仓
- **建议仓位**: 60%-80%
- **买入价位**: ¥XX.XX - ¥XX.XX
- **目标价位**: ¥XX.XX（+XX%）
- **止损位**: ¥XX.XX（-XX%）
- **加仓条件**: [具体条件]

### 四、风险提示
⚠️ **主要风险**:
1. [风险1及应对措施]
2. [风险2及应对措施]""",
    
    "safe": """## 🛡️ 保守风险评估报告

### 一、风险识别
⚠️ **风险清单**:
1. **财务风险**: [具体风险及严重性]
2. **经营风险**: [具体风险及严重性]
3. **市场风险**: [具体风险及严重性]

### 二、下行风险评估
- **最大可能损失**: -XX%
- **支撑位**: ¥XX.XX
- **破位风险**: [评估]
- **最坏情景**: [分析]

### 三、安全边际
- **内在价值**: ¥XX.XX
- **当前价格**: ¥XX.XX
- **安全边际**: XX%（要求≥30%）
- **评估**: 安全边际充足 / 不足

### 四、交易建议
- **操作建议**: 谨慎买入 / 观望
- **建议仓位**: 20%-40%
- **买入价位**: ≤ ¥XX.XX（要求30%+安全边际）
- **止损位**: ¥XX.XX（-5%至-8%）
- **建仓策略**: 分3-5批建仓""",
    
    "neutral": """## ⚖️ 中性风险评估报告

### 一、风险收益平衡
- **预期收益**: +XX%
- **潜在风险**: -XX%
- **风险收益比**: X:X
- **期望收益**: +XX%（概率加权）

### 二、综合评估
| 维度 | 评分 | 说明 |
|------|------|------|
| 技术面 | X/10 | [趋势、指标] |
| 基本面 | X/10 | [估值、成长] |
| 情绪面 | X/10 | [资金、情绪] |
| **综合** | **X/10** | **[总体评价]** |

### 三、交易建议
- **操作建议**: 买入 / 持有
- **建议仓位**: 40%-60%
- **买入价位**: ¥XX.XX - ¥XX.XX
- **目标价位**: ¥XX.XX（+XX%）
- **止损位**: ¥XX.XX（-XX%）
- **风险收益比**: X:X"""
}


def update_risk_analysts():
    """更新风险分析师模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("=" * 80)
    print("更新风险分析师模板")
    print("=" * 80)
    
    agents = {
        "risky_analyst_v2": "risky",
        "safe_analyst_v2": "safe",
        "neutral_analyst_v2": "neutral"
    }
    
    for agent_name, risk_type in agents.items():
        for preference in ["aggressive", "neutral", "conservative"]:
            result = collection.update_one(
                {
                    "agent_type": "debators_v2",
                    "agent_name": agent_name,
                    "preference_type": preference,
                    "is_system": True
                },
                {
                    "$set": {
                        "content.analysis_requirements": RISK_ANALYST_REQUIREMENTS[risk_type],
                        "content.output_format": RISK_ANALYST_OUTPUT_FORMAT[risk_type],
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
    print("🔧 升级风险分析师 v2.0 模板\n")
    
    updated = update_risk_analysts()
    
    print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()

