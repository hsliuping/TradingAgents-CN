#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级交易员 v2.0 模板

包括：
- trader_v2 (交易员)
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
# 交易员模板定义
# ============================================================

TRADER_REQUIREMENTS = """**交易计划制定要求**:

📋 **交易计划核心要素**:

1. **买入策略**:
   - **买入价位**:
     - 最佳买入价：¥XX.XX（基于技术支撑和估值）
     - 可接受价位区间：¥XX.XX - ¥XX.XX
     - 价位选择依据（技术面、基本面、情绪面）
   
   - **买入时机**:
     - 技术信号（突破、回调、金叉等）
     - 基本面催化剂（业绩、政策、事件）
     - 市场环境（大盘、板块、情绪）
   
   - **分批建仓计划**:
     - 首次建仓：XX%仓位，价格≤¥XX.XX
     - 第二次加仓：XX%仓位，条件：[具体条件]
     - 第三次加仓：XX%仓位，条件：[具体条件]
     - 最大仓位：XX%

2. **仓位管理**:
   - **初始仓位比例**: XX%（基于风险评估）
   - **加仓条件**:
     - 价格回调至支撑位且企稳
     - 出现重大利好催化剂
     - 技术指标确认上涨趋势
   - **减仓条件**:
     - 达到目标价位
     - 技术指标转弱
     - 基本面恶化
   - **最大仓位限制**: XX%（风险控制）

3. **风险控制**:
   - **止损位设置**:
     - 价格止损：¥XX.XX（-XX%）
     - 技术止损：跌破关键支撑位
     - 时间止损：持仓XX天未盈利
   - **止损幅度**: 建议5%-15%（根据风险偏好）
   - **风险敞口控制**: 单只股票最大损失≤总资金的XX%

4. **止盈策略**:
   - **目标价位**:
     - 短期目标：¥XX.XX（+XX%）
     - 中期目标：¥XX.XX（+XX%）
     - 长期目标：¥XX.XX（+XX%）
   - **分批止盈计划**:
     - 第一次止盈：XX%仓位，价格≥¥XX.XX
     - 第二次止盈：XX%仓位，价格≥¥XX.XX
     - 剩余仓位：持有或移动止盈
   - **止盈条件**:
     - 价格达到目标价位
     - 技术指标超买
     - 基本面或市场环境恶化

5. **持仓周期**:
   - **预期持仓时间**: XX天 - XX天
   - **定期复盘频率**: 每周/每月
   - **退出条件**:
     - 达到目标价位
     - 触发止损
     - 投资逻辑改变
     - 出现更好的投资机会

📊 **交易计划格式要求**:
- 使用表格清晰展示关键信息
- 包含具体数字和百分比（不要使用XX占位符）
- 明确操作条件和触发点
- 提供清晰的决策树或流程图

🎯 **风险收益评估**:
- 预期收益：+XX%
- 最大风险：-XX%
- 风险收益比：X:X
- 胜率评估：XX%

🌍 **语言要求**: 
- 所有内容使用中文
- 使用：买入、卖出、止损、止盈（不使用英文）"""

TRADER_OUTPUT_FORMAT = """## 📋 交易计划

### 一、交易概要

| 项目 | 内容 |
|------|------|
| 股票代码 | {ticker} |
| 股票名称 | {company_name} |
| 当前价格 | ¥XX.XX |
| 交易方向 | 买入 / 持有 / 卖出 |
| 建议仓位 | XX% |
| 风险收益比 | X:X |

### 二、买入策略

**买入价位**:
- 最佳买入价：¥XX.XX
- 可接受区间：¥XX.XX - ¥XX.XX
- 价位依据：[技术支撑 + 估值分析]

**分批建仓计划**:
| 批次 | 仓位 | 价格条件 | 触发条件 |
|------|------|---------|---------|
| 首次 | XX% | ≤¥XX.XX | 立即执行 |
| 加仓1 | XX% | ≤¥XX.XX | [具体条件] |
| 加仓2 | XX% | ≤¥XX.XX | [具体条件] |

### 三、仓位管理

**仓位配置**:
- 初始仓位：XX%
- 最大仓位：XX%
- 加仓条件：[具体条件]
- 减仓条件：[具体条件]

### 四、风险控制

**止损设置**:
- 止损价位：¥XX.XX（-XX%）
- 止损条件：
  1. 价格跌破¥XX.XX
  2. 跌破关键支撑位
  3. 持仓XX天未盈利

**风险控制**:
- 最大损失：-XX%（总资金的XX%）
- 风险敞口：≤总资金的XX%

### 五、止盈策略

**目标价位**:
| 目标 | 价格 | 涨幅 | 止盈仓位 |
|------|------|------|---------|
| 短期 | ¥XX.XX | +XX% | XX% |
| 中期 | ¥XX.XX | +XX% | XX% |
| 长期 | ¥XX.XX | +XX% | 剩余 |

**止盈条件**:
1. 达到目标价位
2. 技术指标超买
3. 基本面恶化

### 六、持仓管理

- **预期持仓**: XX天 - XX天
- **复盘频率**: 每周/每月
- **退出条件**:
  1. 达到目标价位
  2. 触发止损
  3. 投资逻辑改变

### 七、风险收益评估

- **预期收益**: +XX%
- **最大风险**: -XX%
- **风险收益比**: X:X
- **胜率评估**: XX%
- **期望收益**: +XX%（概率加权）"""


def update_trader():
    """更新交易员模板"""
    collection = db['prompt_templates']
    updated_count = 0
    
    print("=" * 80)
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
                    "content.output_format": TRADER_OUTPUT_FORMAT,
                    "updated_at": datetime.now()
                }
            }
        )
        if result.modified_count > 0:
            print(f"✅ 更新: trader_v2 / {preference}")
            updated_count += 1
        else:
            print(f"⏭️ 无变化: trader_v2 / {preference}")
    
    return updated_count


def main():
    """主函数"""
    print("🔧 升级交易员 v2.0 模板\n")
    
    updated = update_trader()
    
    print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()

