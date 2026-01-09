#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级持仓顾问 v2.0 模板

包括：
- pa_technical_v2 (技术面分析师)
- pa_fundamental_v2 (基本面分析师)
- pa_risk_v2 (风险评估师)
- pa_advisor_v2 (操作建议师)
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

- **关键价位**:
  - 支撑位（强支撑、弱支撑）
  - 阻力位（强阻力、弱阻力）
  - 当前价格所处位置

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

💡 **技术建议**:
- 技术面是否支持继续持有
- 关键技术位和操作建议
- 技术风险提示

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

💡 **基本面建议**:
- 基本面是否支持继续持有
- 基本面变化趋势
- 基本面风险提示

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

📉 **下行风险评估**:
- 最大可能损失：-XX%
- 下一个支撑位：¥XX.XX
- 破位后的下跌空间
- 止损位建议：¥XX.XX

📊 **风险等级**:
- 技术风险：高/中/低
- 基本面风险：高/中/低
- 市场风险：高/中/低
- 综合风险等级：高/中/低

🎯 **风险评分**:
- 风险控制评分：X/10（分数越高风险越低）
- 安全边际评分：X/10
- 综合风险评分：X/10

💡 **风险建议**:
- 主要风险因素
- 风险应对措施
- 止损位设置建议

🌍 **语言要求**: 所有内容使用中文""",
    
    "advisor": """**操作建议要求**:

🎯 **综合评估**:
- **技术面评估**: [技术面分析师的核心结论]
- **基本面评估**: [基本面分析师的核心结论]
- **风险评估**: [风险评估师的核心结论]

📋 **操作建议**:
- **主要建议**: 继续持有 / 加仓 / 减仓 / 清仓
- **建议理由**: [基于三个维度的综合判断]
- **操作时机**: 立即执行 / 等待信号 / 分批操作

💰 **仓位建议**:
- **当前仓位**: XX%
- **建议仓位**: XX%
- **调整方向**: 加仓XX% / 减仓XX% / 维持不变
- **调整理由**: [具体原因]

📊 **具体操作方案**:

**如果加仓**:
- 加仓价位：≤¥XX.XX
- 加仓幅度：XX%
- 加仓条件：[具体条件]
- 最大仓位：XX%

**如果减仓**:
- 减仓价位：≥¥XX.XX
- 减仓幅度：XX%
- 减仓条件：[具体条件]
- 最小仓位：XX%

**如果持有**:
- 持有理由：[具体原因]
- 加仓条件：[具体条件]
- 减仓条件：[具体条件]

🛡️ **风险控制**:
- **止损位**: ¥XX.XX（-XX%）
- **止盈位**: ¥XX.XX（+XX%）
- **风险提示**: [主要风险]

📅 **复盘建议**:
- 下次复盘时间：XX天后
- 关注指标：[关键指标]
- 触发条件：[需要立即复盘的条件]

🌍 **语言要求**: 所有内容使用中文，使用：加仓、减仓、持有、清仓"""
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

