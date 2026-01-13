#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级管理员 v2.0 模板

包括：
- research_manager_v2 (研究管理员)
- risk_manager_v2 (风险管理员)
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
# 管理员模板定义
# ============================================================

RESEARCH_MANAGER_REQUIREMENTS = """**研究总结要求**:

📊 **多空观点汇总**:
- **看多核心观点**:
  - 主要投资亮点（成长性、估值、催化剂）
  - 支撑数据和逻辑
  - 上涨空间预测
  
- **看空核心观点**:
  - 主要风险因素（财务、经营、市场）
  - 支撑数据和逻辑
  - 下跌风险评估

- **观点分歧点**:
  - 多空双方的主要分歧
  - 分歧的根源（数据解读、假设、预期）
  - 哪方观点更有说服力

- **观点共识点**:
  - 多空双方的共识
  - 确定性较高的判断
  - 可以依赖的基础

⚖️ **综合判断**:
- **多空力量对比**:
  - 看多力量强度（1-10分）
  - 看空力量强度（1-10分）
  - 力量对比分析
  
- **市场共识 vs 分歧**:
  - 市场主流观点
  - 分歧观点的价值
  - 潜在的预期差

- **投资价值评估**:
  - 当前价格是否合理
  - 风险收益比评估
  - 投资吸引力（高/中/低）

🎯 **投资建议**:
- **综合投资建议**: 买入 / 持有 / 卖出
- **建议理由**: [基于多空辩论的核心逻辑]
- **关键风险提示**: [必须关注的风险]
- **操作策略**: [具体操作建议]

📋 **投资计划要点**:
- 建议买入价位区间
- 建议仓位比例
- 止损止盈设置
- 持仓周期建议

💰 **目标价格设定**（重要）:
- **必须先提取当前股价**：从看涨/看跌报告中提取当前股价
- **必须参考价格区间**：
  - 看涨报告的合理价位区间（上限）
  - 看跌报告的风险价位区间（下限）
- **目标价格原则**：
  - 如果建议买入：目标价格应在看涨报告的合理价位区间内
  - 如果建议持有：目标价格应在当前价格的±20%范围内
  - 如果建议卖出：可以不设定目标价格
  - **严禁随意编造目标价格**，必须基于报告中的真实数据
  - 目标价格必须在合理范围内（通常是当前价格的±50%以内）
- **如果无法确定合理的目标价格**：请不要填写 target_price 字段

🌍 **语言要求**: 
- 所有内容使用中文
- 投资建议使用：买入、持有、卖出（不使用英文）"""

RESEARCH_MANAGER_OUTPUT_FORMAT = """## 📊 研究总结报告

### 一、多空观点对比

| 维度 | 看多观点 | 看空观点 |
|------|---------|---------|
| 核心逻辑 | [看多核心逻辑] | [看空核心逻辑] |
| 支撑数据 | [关键数据] | [关键数据] |
| 预期收益/风险 | +XX% | -XX% |

### 二、观点分歧与共识

**分歧点**:
1. [分歧1及分析]
2. [分歧2及分析]

**共识点**:
1. [共识1]
2. [共识2]

### 三、综合判断

- **多空力量对比**: 看多 X/10 vs 看空 X/10
- **投资价值**: 高 / 中 / 低
- **风险收益比**: X:X

### 四、投资建议

- **综合建议**: 买入 / 持有 / 卖出
- **核心逻辑**: [主要理由]
- **关键风险**: [必须关注的风险]
- **操作策略**: [具体建议]"""

RISK_MANAGER_REQUIREMENTS = """**风险评估总结要求**:

⚖️ **风险观点汇总**:
- **激进观点**（收益导向）:
  - 收益潜力评估
  - 建议仓位和策略
  - 风险可控性判断
  
- **保守观点**（风险导向）:
  - 风险因素识别
  - 下行风险评估
  - 安全边际要求

- **中性观点**（平衡导向）:
  - 风险收益平衡
  - 综合评估结论
  - 理性操作建议

📊 **综合风险评估**:
- **整体风险等级**: 高 / 中 / 低
  - 评级依据（技术、基本面、市场）
  - 风险量化评估
  - 风险趋势（上升/稳定/下降）

- **主要风险因素**:
  - 财务风险（负债、现金流）
  - 经营风险（竞争、市场）
  - 市场风险（估值、流动性）
  - 系统性风险（政策、宏观）

- **风险可控性**:
  - 可控风险 vs 不可控风险
  - 风险应对措施
  - 风险监控指标

🎯 **最终建议**:
- **综合仓位建议**: XX%-XX%
  - 激进建议：XX%
  - 保守建议：XX%
  - 中性建议：XX%
  - 综合权衡：XX%

- **风险控制措施**:
  - 止损位设置
  - 仓位控制规则
  - 风险对冲策略

- **操作策略**:
  - 建仓策略（一次性/分批）
  - 加减仓条件
  - 退出条件

🌍 **语言要求**: 
- 所有内容使用中文
- 建议使用：买入、持有、减仓（不使用英文）"""

RISK_MANAGER_OUTPUT_FORMAT = """## ⚖️ 风险评估总结报告

### 一、风险观点汇总

| 角色 | 仓位建议 | 核心观点 |
|------|---------|---------|
| 激进分析师 | XX% | [收益导向观点] |
| 保守分析师 | XX% | [风险导向观点] |
| 中性分析师 | XX% | [平衡导向观点] |

### 二、综合风险评估

- **整体风险等级**: 高 / 中 / 低
- **风险评分**: X/10
- **风险趋势**: 上升 / 稳定 / 下降

**主要风险因素**:
1. [风险1及严重性]
2. [风险2及严重性]
3. [风险3及严重性]

### 三、最终建议

- **综合仓位**: XX%（激进XX% + 保守XX% + 中性XX%）
- **风险控制**:
  - 止损位：¥XX.XX（-XX%）
  - 止盈位：¥XX.XX（+XX%）
  - 仓位上限：XX%
  
- **操作策略**: [具体建议]"""


# 研究管理员用户提示词模板
RESEARCH_MANAGER_USER_PROMPT = """请综合分析 {{company_name}}（{{ticker}}）的投资机会：

📊 **基本信息**：
- 股票代码：{{ticker}}
- 公司名称：{{company_name}}
- 分析日期：{{analysis_date}}
- 当前价格：¥{{current_price}}

【看涨观点】
{{bull_report}}

【看跌观点】
{{bear_report}}

【辩论总结】
{{debate_summary}}

请给出最终的投资计划（买入/持有/卖出）和详细理由。

**输出要求**：
必须以JSON格式输出，示例：
```json
{
    "action": "持有",
    "confidence": 65,
    "target_price": 16.50,
    "reasoning": "综合看涨与看跌观点..."
}
```

**字段说明**：
1. **action** (必需): 只能是"买入"、"持有"或"卖出"
2. **confidence** (必需): 信心度，**必须是0-100的整数**（如：62、75、80），**不是小数**！
3. **target_price** (可选): 目标价格，基于当前价格 ¥{{current_price}} 和报告中的价格区间
4. **reasoning** (必需): 决策理由，200-500字，说明为什么做出这个建议

**重要**：confidence 必须是整数，如 65，不要写成 0.65！

**权重说明**：
- 看涨观点和看跌观点权重相等（各50%），请同等重视
- 请客观权衡双方观点，基于证据做出理性决策

**⏰ 时间上下文说明**：
- 当前分析日期：{{analysis_date}}
- 如果建议"等待财报"或"等待年报"，请注意：
  * 不要指定具体年份（如"等待2024年年报"）
  * 直接说"等待年报发布"或"等待下一期财报"
  * 或根据当前月份智能判断（1-4月等待上一年度年报，5-12月等待本年度年报）"""


def update_managers():
    """更新管理员模板"""
    collection = db['prompt_templates']
    updated_count = 0

    print("=" * 80)
    print("更新管理员模板")
    print("=" * 80)

    # 研究管理员 - 更新用户提示词
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
                    "content.analysis_requirements": RESEARCH_MANAGER_REQUIREMENTS,
                    "content.output_format": RESEARCH_MANAGER_OUTPUT_FORMAT,
                    "content.user_prompt": RESEARCH_MANAGER_USER_PROMPT,  # ✅ 添加用户提示词
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: research_manager_v2 / {preference} (包含用户提示词)")
            updated_count += 1
        else:
            print(f"⏭️ 无变化: research_manager_v2 / {preference}")
    
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
                    "content.analysis_requirements": RISK_MANAGER_REQUIREMENTS,
                    "content.output_format": RISK_MANAGER_OUTPUT_FORMAT,
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: risk_manager_v2 / {preference}")
            updated_count += 1
        else:
            print(f"⏭️ 无变化: risk_manager_v2 / {preference}")
    
    return updated_count


def main():
    """主函数"""
    print("🔧 升级管理员 v2.0 模板\n")
    
    updated = update_managers()
    
    print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()

