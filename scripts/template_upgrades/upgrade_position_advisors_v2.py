#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级持仓顾问 v2.0 模板

包括：
- pa_technical_v2 (技术面分析师)
- pa_fundamental_v2 (基本面分析师)
- pa_risk_v2 (风险评估师)
- pa_advisor_v2 (持仓研究整合师)
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
# 持仓顾问模板定义
# ============================================================

POSITION_ADVISOR_REQUIREMENTS = {
    "technical": """**技术面分析要求**:

📈 **趋势分析**:
- **当前趋势**:
  - 短期趋势（5日、10日）
  - 中期趋势（20日、60日）
  - 长期趋势（120日、250日）
  - 趋势强度和可持续性

📊 **技术指标**:
- **均线系统**:
  - MA5、MA10、MA20、MA60排列
  - 均线支撑/压制情况
  - 均线多头/空头排列

- **动量指标**:
  - MACD（金叉/死叉、背离）
  - RSI（超买/超卖、背离）
  - KDJ（金叉/死叉、超买超卖）

- **成交量**:
  - 量价配合情况
  - 放量/缩量分析
  - 异常成交量识别

🎯 **技术评分**:
- 趋势评分：X/10
- 指标评分：X/10
- 量价评分：X/10
- 综合技术评分：X/10

💡 **研究输出重点**:
- 技术结构是否改善或走弱
- 多空证据是否一致
- 后续需要继续跟踪的技术验证信号

🚫 **禁止输出**:
- 买入、卖出、持有、加仓、减仓、清仓等执行性建议
- 支撑阻力具体价位、目标价、止损止盈、仓位比例

🌍 **语言要求**: 所有内容使用中文""",
    
    "fundamental": """**基本面分析要求**:

📊 **财务分析**:
- **盈利能力**:
  - 营收增长率
  - 净利润增长率
  - ROE、ROA水平
  - 毛利率、净利率趋势

- **财务健康**:
  - 资产负债率
  - 流动比率、速动比率
  - 现金流状况
  - 偿债能力

📈 **成长性分析**:
- 业绩增长趋势
- 行业地位和竞争力
- 未来成长空间
- 业绩确定性

💰 **估值分析**:
- PE、PB、PS水平
- 与历史估值对比
- 与行业估值对比
- 估值合理性评估

🎯 **基本面评分**:
- 盈利能力评分：X/10
- 成长性评分：X/10
- 估值评分：X/10
- 综合基本面评分：X/10

💡 **研究输出重点**:
- 当前经营质量与估值是否匹配
- 成长逻辑是否在强化或减弱
- 后续需要继续跟踪的公开验证信号

🚫 **禁止输出**:
- 买入、卖出、持有、加仓、减仓、清仓等执行性建议
- 目标价、价格区间、仓位比例

🌍 **语言要求**: 所有内容使用中文""",
    
    "risk": """**风险评估要求**:

⚠️ **风险识别**:
- **技术风险**:
  - 破位风险（支撑位、趋势线）
  - 技术指标恶化风险
  - 下跌空间评估

- **基本面风险**:
  - 业绩下滑风险
  - 财务恶化风险
  - 行业风险、政策风险

- **市场风险**:
  - 大盘系统性风险
  - 板块轮动风险
  - 流动性风险

📉 **风险情景评估**:
- 哪些经营、行业或市场变化会削弱当前判断
- 当前持仓对账户整体波动的影响
- 哪些公开信号出现后需要重新评估

📊 **风险等级**:
- 技术风险：高/中/低
- 基本面风险：高/中/低
- 市场风险：高/中/低
- 综合风险等级：高/中/低

🎯 **风险评分**:
- 风险控制评分：X/10（分数越高风险越低）
- 安全边际评分：X/10
- 综合风险评分：X/10

💡 **研究输出重点**:
- 主要风险因素
- 风险影响路径
- 后续观察事项

🚫 **禁止输出**:
- 止损止盈、参考价位、目标价、仓位调整建议

🌍 **语言要求**: 所有内容使用中文""",
    
    "advisor": """**持仓研究整合要求**:

🎯 **综合评估**:
- **技术面评估**: [技术面分析师的核心结论]
- **基本面评估**: [基本面分析师的核心结论]
- **风险评估**: [风险评估师的核心结论]

  📋 **研究判断**:
  - **综合判断**: 偏强 / 中性 / 偏弱 / 待验证
  - **判断理由**: [基于三个维度的综合判断]
  - **当前阶段**: [处于验证、改善、承压或等待信号的哪一阶段]

  🧭 **后续观察事项**:
  - **优先关注事实**: [下一步优先核对的公告、财报或市场信号]
  - **关键验证指标**: [后续要跟踪的经营、行业或市场变量]
  - **判断调整条件**: [什么变化出现后需要重新审视判断]

  🛡️ **风险与催化**:
  - **主要风险**: [主要风险]
  - **潜在催化**: [可能改善判断的因素]
  - **风险提醒**: [当前最需要警惕的问题]

  🚫 **禁止输出**:
  - 加仓、减仓、持有、清仓、买卖等执行性建议
  - 目标价、价格区间、止损止盈、仓位比例、数量金额
  - 不得把收益预期、风险承受度翻译成买卖动作

  🌍 **语言要求**: 所有内容使用中文，保持研究判断口径"""
}


def update_position_advisors():
    """更新持仓顾问模板"""
    collection = db['prompt_templates']
    updated_count = 0

    print("=" * 80)
    print("更新持仓顾问模板")
    print("=" * 80)

    agents = {
        "pa_technical_v2": "technical",
        "pa_fundamental_v2": "fundamental",
        "pa_risk_v2": "risk",
        "pa_advisor_v2": "advisor"
    }

    for agent_name, req_type in agents.items():
        # 更新所有三种偏好类型（aggressive, neutral, conservative）
        for preference in ["aggressive", "neutral", "conservative"]:
            result = collection.update_one(
                {
                    "agent_type": "position_analysis_v2",
                    "agent_name": agent_name,
                    "preference_type": preference,
                    "is_system": True
                },
                {
                    "$set": {
                        "content.analysis_requirements": POSITION_ADVISOR_REQUIREMENTS[req_type],
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
    print("🔧 升级持仓顾问 v2.0 模板\n")

    # 更新模板（只更新 aggressive, neutral, conservative）
    updated = update_position_advisors()

    print(f"\n✅ 完成！共更新 {updated} 个模板")
    print("\n💡 注意:")
    print("  - 本脚本只更新 aggressive/neutral/conservative 三种偏好类型")
    print("  - with_cache/without_cache 模板由单独的脚本管理")
    print("  - 如需恢复 with_cache/without_cache 模板，请运行:")
    print("    python scripts/template_upgrades/restore_cache_templates.py")


if __name__ == "__main__":
    main()

