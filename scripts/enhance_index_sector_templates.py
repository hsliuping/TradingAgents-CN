#!/usr/bin/env python
"""
增强大盘分析师和行业分析师的提示词模板

为 index_analyst_v2 和 sector_analyst_v2 添加详细的 analysis_requirements 和 output_format
"""

import os
import sys
from datetime import datetime
from pathlib import Path

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

print(f"📊 连接数据库: {host}:{port}/{db_name}")
client = MongoClient(mongo_uri)
db = client[db_name]


# ============================================================
# 大盘分析师增强模板
# ============================================================

INDEX_ANALYST_ENHANCEMENTS = {
    "aggressive": {
        "analysis_requirements": """**激进型大盘分析要求**:

📊 **趋势分析**（重点关注上涨信号）:
- 主要指数走势（上证指数、深证成指、创业板指）
- 趋势突破信号（突破关键阻力位、均线多头排列）
- 成交量放大（资金流入信号）
- 技术指标（MACD金叉、RSI超卖反弹）

💰 **资金面分析**:
- 北向资金流入情况
- 两融余额变化
- 新增开户数
- 热点板块资金流向

📰 **政策面分析**:
- 货币政策（降准降息预期）
- 财政政策（减税降费、基建投资）
- 产业政策（新兴产业支持）
- 监管政策（利好政策）

🎯 **投资建议**（激进风格）:
- 仓位建议（建议加仓比例）
- 配置方向（推荐板块和主题）
- 操作策略（积极做多）
- 风险提示（但不过度强调）

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：加仓、满仓、重仓（不使用英文）""",
        "output_format": """## 📊 大盘分析报告（激进视角）

### 一、指数走势分析
[主要指数表现、涨跌幅、成交量]

### 二、趋势判断
✅ **上涨信号**:
1. [信号1及其意义]
2. [信号2及其意义]
3. [信号3及其意义]

### 三、资金面分析
| 指标 | 数值 | 变化 | 解读 |
|------|------|------|------|
| 北向资金 | XX亿 | +XX% | 持续流入 |
| 两融余额 | XX亿 | +XX% | 杠杆提升 |

### 四、热点板块
[资金流入的热点板块和主题]

### 五、投资建议
- **仓位建议**: 建议加仓至XX%
- **配置方向**: [推荐板块1]、[推荐板块2]
- **操作策略**: 积极做多，把握上涨机会
- **风险提示**: [主要风险]"""
    },
    "neutral": {
        "analysis_requirements": """**中性型大盘分析要求**:

📊 **趋势分析**（客观评估）:
- 主要指数走势和技术形态
- 支撑位和阻力位
- 均线系统（MA5, MA10, MA20, MA60）
- 技术指标（MACD, RSI, KDJ）

💰 **资金面分析**:
- 北向资金流向
- 两融余额变化
- 成交量和换手率
- 行业资金分布

📰 **政策面分析**:
- 货币政策影响
- 财政政策影响
- 产业政策影响
- 监管政策影响

😊 **情绪面分析**:
- 市场情绪指标
- 涨跌家数比
- 新高新低数量
- 恐慌贪婪指数

🎯 **投资建议**（中性风格）:
- 仓位建议（给出合理区间）
- 配置方向（平衡配置）
- 操作策略（灵活应对）
- 风险与机会并重

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：加仓、持仓、减仓（不使用英文）""",
        "output_format": """## 📊 大盘分析报告（中性视角）

### 一、指数走势分析
[主要指数表现、技术形态]

### 二、技术分析
| 指标 | 数值 | 信号 |
|------|------|------|
| MA5 | XXXX | 多头/空头 |
| MA20 | XXXX | 多头/空头 |
| MACD | XX | 金叉/死叉 |
| RSI | XX | 超买/超卖/中性 |

### 三、资金面分析
[北向资金、两融、成交量分析]

### 四、政策面分析
[货币、财政、产业政策影响]

### 五、机会与风险
| 机会因素 | 风险因素 |
|---------|---------|
| [机会1] | [风险1] |
| [机会2] | [风险2] |

### 六、投资建议
- **仓位建议**: XX%-XX%
- **配置方向**: [平衡配置建议]
- **操作策略**: [灵活应对策略]
- **核心逻辑**: [主要判断依据]"""
    },
    "conservative": {
        "analysis_requirements": """**保守型大盘分析要求**:

📊 **风险信号识别**:
- 下跌趋势确认（跌破关键支撑位）
- 均线空头排列
- 成交量萎缩（资金观望）
- 技术指标恶化（MACD死叉、RSI超买）

💰 **资金面风险**:
- 北向资金流出
- 两融余额下降
- 成交量萎缩
- 资金撤离迹象

📰 **政策面风险**:
- 货币政策收紧
- 监管政策趋严
- 外部环境恶化
- 系统性风险

📉 **下行风险评估**:
- 支撑位有效性
- 最坏情景分析
- 潜在下跌空间
- 止损位设置

🎯 **投资建议**（保守风格）:
- 仓位建议（建议减仓或空仓）
- 防御配置（低风险资产）
- 操作策略（保守防御）
- 风险警示（重点强调）

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：减仓、空仓、观望（不使用英文）""",
        "output_format": """## 📊 大盘分析报告（保守视角）

### 一、指数走势分析
[主要指数表现、下跌幅度]

### 二、风险信号
⚠️ **主要风险信号**:
1. [风险信号1及其影响]
2. [风险信号2及其影响]
3. [风险信号3及其影响]

### 三、资金面分析
[北向资金流出、两融下降、成交萎缩]

### 四、支撑位分析
- **关键支撑**: XXXX点
- **有效性评估**: [支撑强度分析]
- **跌破后果**: [下行空间预测]

### 五、下行风险评估
- **短期下跌目标**: XXXX点（-XX%）
- **中期下跌目标**: XXXX点（-XX%）
- **极端情况**: XXXX点（-XX%）

### 六、投资建议
- **仓位建议**: 建议减仓至XX%或空仓
- **防御配置**: [低风险资产配置]
- **操作策略**: 保守防御，控制风险
- **风险警示**: [核心风险提示]"""
    }
}


# ============================================================
# 行业分析师增强模板
# ============================================================

SECTOR_ANALYST_ENHANCEMENTS = {
    "aggressive": {
        "analysis_requirements": """**激进型行业分析要求**:

📊 **行业成长性分析**:
- 行业增长率（营收、利润增速）
- 市场规模和渗透率
- 行业生命周期阶段
- 未来成长空间

💰 **政策支持分析**:
- 产业政策利好
- 财政补贴和税收优惠
- 监管环境改善
- 国家战略定位

🏆 **龙头公司分析**:
- 行业龙头竞争优势
- 市场份额和集中度
- 技术壁垒和护城河
- 盈利能力对比

📈 **投资机会识别**:
- 行业拐点和催化剂
- 估值洼地
- 资金流入迹象
- 主题投资机会

🎯 **投资建议**（激进风格）:
- 行业配置比例（建议超配）
- 推荐标的（龙头公司）
- 买入时机
- 上涨空间预测

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：超配、重点配置（不使用英文）""",
        "output_format": """## 📊 行业分析报告（激进视角）

### 一、行业概况
[行业基本信息、市场规模]

### 二、成长性分析
| 指标 | 数值 | 增速 | 评价 |
|------|------|------|------|
| 行业营收 | XX亿 | +XX% | 高增长 |
| 行业利润 | XX亿 | +XX% | 高增长 |
| 市场规模 | XX亿 | +XX% | 扩张中 |

### 三、政策支持
✅ **利好政策**:
1. [政策1及其影响]
2. [政策2及其影响]
3. [政策3及其影响]

### 四、龙头公司分析
[行业龙头、市场份额、竞争优势]

### 五、投资机会
- **催化剂**: [行业拐点、利好事件]
- **估值机会**: [当前估值vs成长潜力]
- **资金流向**: [资金流入情况]

### 六、投资建议
- **配置建议**: 建议超配至XX%
- **推荐标的**: [龙头公司1]、[龙头公司2]
- **目标涨幅**: XX%
- **风险提示**: [主要风险]"""
    },
    "neutral": {
        "analysis_requirements": """**中性型行业分析要求**:

📊 **行业发展阶段**:
- 行业生命周期（导入/成长/成熟/衰退）
- 行业增长率和波动性
- 市场规模和增长潜力
- 行业集中度

🏆 **竞争格局分析**:
- 主要竞争者和市场份额
- 行业进入壁垒
- 替代品威胁
- 议价能力

📰 **政策影响分析**:
- 产业政策（支持/中性/限制）
- 监管环境
- 税收政策
- 环保要求

💰 **盈利能力分析**:
- 行业平均毛利率
- 行业平均净利率
- ROE水平
- 现金流状况

🎯 **投资建议**（中性风格）:
- 行业配置比例（标配/超配/低配）
- 推荐标的（综合评估）
- 机会与风险平衡
- 配置时机

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：标配、超配、低配（不使用英文）""",
        "output_format": """## 📊 行业分析报告（中性视角）

### 一、行业概况
[行业基本信息、发展阶段]

### 二、行业数据分析
| 指标 | 数值 | 同比 | 行业平均 |
|------|------|------|---------|
| 营收增速 | +XX% | - | +XX% |
| 利润增速 | +XX% | - | +XX% |
| 毛利率 | XX% | - | XX% |
| ROE | XX% | - | XX% |

### 三、竞争格局
[主要竞争者、市场份额、集中度]

### 四、政策影响
[产业政策、监管环境、税收政策]

### 五、机会与风险
| 机会因素 | 风险因素 |
|---------|---------|
| [机会1] | [风险1] |
| [机会2] | [风险2] |

### 六、投资建议
- **配置建议**: 标配/超配/低配
- **推荐标的**: [综合评估后的标的]
- **配置比例**: XX%
- **核心逻辑**: [主要投资逻辑]"""
    },
    "conservative": {
        "analysis_requirements": """**保守型行业分析要求**:

📊 **行业风险识别**:
- 行业下行周期
- 需求萎缩风险
- 产能过剩
- 技术替代风险

🏆 **竞争加剧风险**:
- 新进入者威胁
- 价格战风险
- 市场份额流失
- 利润率下滑

📰 **政策监管风险**:
- 监管政策收紧
- 环保要求提高
- 税收优惠取消
- 行业整顿

💰 **盈利能力恶化**:
- 毛利率下降
- 净利率压缩
- ROE下滑
- 现金流恶化

🎯 **投资建议**（保守风格）:
- 行业配置比例（建议低配或回避）
- 风险标的（需要规避的公司）
- 防御策略
- 风险警示

🌍 **语言要求**:
- 所有内容使用中文
- 投资建议使用：低配、回避、观望（不使用英文）""",
        "output_format": """## 📊 行业分析报告（保守视角）

### 一、行业概况
[行业基本信息、当前困境]

### 二、风险因素分析
⚠️ **主要风险**:
1. [风险1及其影响]
2. [风险2及其影响]
3. [风险3及其影响]

### 三、竞争格局恶化
[竞争加剧、价格战、利润率下滑]

### 四、政策监管风险
[监管收紧、环保压力、税收变化]

### 五、盈利能力分析
| 指标 | 当前 | 变化 | 趋势 |
|------|------|------|------|
| 毛利率 | XX% | -XX% | 下降 |
| 净利率 | XX% | -XX% | 下降 |
| ROE | XX% | -XX% | 下降 |

### 六、投资建议
- **配置建议**: 建议低配或回避
- **风险标的**: [需要规避的公司]
- **防御策略**: [风险控制措施]
- **风险警示**: [核心风险提示]"""
    }
}


def update_templates():
    """更新模板"""
    collection = db['prompt_templates']
    updated_count = 0

    print("=" * 80)
    print("更新大盘分析师模板")
    print("=" * 80)

    for preference, enhancements in INDEX_ANALYST_ENHANCEMENTS.items():
        result = collection.update_one(
            {
                "agent_type": "analysts_v2",
                "agent_name": "index_analyst_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": enhancements["analysis_requirements"],
                    "content.output_format": enhancements["output_format"],
                    "updated_at": datetime.now()
                }
            }
        )

        if result.modified_count > 0:
            print(f"✅ 更新: index_analyst_v2 / {preference}")
            updated_count += 1
        else:
            print(f"⏭️ 无变化: index_analyst_v2 / {preference}")

    print("\n" + "=" * 80)
    print("更新行业分析师模板")
    print("=" * 80)

    for preference, enhancements in SECTOR_ANALYST_ENHANCEMENTS.items():
        result = collection.update_one(
            {
                "agent_type": "analysts_v2",
                "agent_name": "sector_analyst_v2",
                "preference_type": preference,
                "is_system": True
            },
            {
                "$set": {
                    "content.analysis_requirements": enhancements["analysis_requirements"],
                    "content.output_format": enhancements["output_format"],
                    "updated_at": datetime.now()
                }
            }
        )

        if result.modified_count > 0:
            print(f"✅ 更新: sector_analyst_v2 / {preference}")
            updated_count += 1
        else:
            print(f"⏭️ 无变化: sector_analyst_v2 / {preference}")

    return updated_count


def main():
    """主函数"""
    print("🔧 增强大盘分析师和行业分析师模板\n")

    updated = update_templates()

    print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()


