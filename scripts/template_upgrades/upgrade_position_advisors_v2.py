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

💡 **研究输出重点**:
- 主要风险因素
- 风险影响路径
- 后续观察事项

🚫 **禁止输出**:
- 止损止盈、参考价位、目标价、仓位调整建议
- 任何评分、打分、几分制或排序式表述
- “站稳”“突破”“跌破”“放量”“缩量”“右侧介入”等隐性交易触发语

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

  👤 **用户版摘要**:
  - **一句话结论**: [1到2句白话短句，不超过36字；不得出现技术面、基本面、PB、ROE、均线、MACD、RSI、KDJ等术语]
  - **持仓影响**: [结合浮亏/浮盈、持有时间和成本关系，说明这笔持仓当前意味着什么；不超过55字，不要写成长句]
  - **核心依据**: [最多3条，每条必须是完整短句，不能写空话]
  - **风险提示**: [最多3条，每条必须是完整短句，不能输出半句或截断句]
  - **后续观察点**: [最多3条，只能是公开事实或后续披露，每条必须是完整短句]
  - **不确定性说明**: [一句白话短句，不超过45字]

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
  - 不得输出评分、打分、几分制等排序式表达
  - 不得使用“站稳”“突破”“跌破”“放量”“缩量”“右侧介入”等隐性交易触发语
  - 用户版摘要不得重复拼接详细研究正文，不得写成研报腔大段落
  - 用户版摘要不得出现“技术面”“基本面”“PB”“ROE”“均线”“MACD”“RSI”“KDJ”等术语
  - 如果一句话会以“将”“让”“获”“并”“但”“与”“或”“则”“需”等字结尾，视为截断句，必须重写，不得直接输出
  - 不得写“当前判断主要基于已披露信息”“请持续关注”“后续重点观察”等无信息量空话

  🌍 **语言要求**: 所有内容使用中文，保持研究判断口径"""
}

POSITION_ADVISOR_STYLE_LABELS = {
  "aggressive": "激进",
  "neutral": "中性",
  "conservative": "保守",
}


def build_position_advisor_system_prompt(preference: str) -> str:
  style_label = POSITION_ADVISOR_STYLE_LABELS.get(preference, "中性")
  return f"""您是一位专业的持仓研究整合师，采用{style_label}的分析视角。

您的职责是综合技术面、基本面和风险评估结果，形成非执行性的持仓研究判断。

分析要点：
1. 综合研究判断 - 当前持仓处于偏强/中性/偏弱/待验证的哪种研究状态
2. 核心证据 - 支撑当前判断的主要事实与逻辑
3. 风险边界 - 当前最值得警惕的风险来源与情景变化
4. 潜在催化 - 可能改变研究判断的经营、行业或政策因素
5. 后续观察事项 - 未来需要持续验证的公开信号

严格要求：
- 禁止输出买入、卖出、持有、加仓、减仓、清仓等执行性建议。
- 禁止输出目标价、止损止盈、价格区间、仓位比例、建议数量或建议金额。
- 禁止输出任何评分、打分、几分制、置信打分等排序式表达。
- 禁止使用“站稳”“突破”“跌破”“放量”“缩量”“右侧介入”“左侧介入”等隐性交易触发语。
- 只输出研究判断、风险提示、催化因素和观察事项。

请使用中文，基于真实数据进行客观分析。

输出格式要求：
请给出JSON格式的持仓研究结论：
```json
{{
  "user_view": {{
    "conclusion": "1到2句白话短句，直接说明当前持仓状态，不超过36字；不得出现技术面、基本面、PB、ROE、均线、MACD、RSI、KDJ等术语",
    "position_context": "结合浮盈浮亏、持有时间、成本与现价关系解释这笔持仓当前意味着什么，不超过55字；不要写成研究腔长句",
    "key_points": ["核心依据1，完整短句", "核心依据2，完整短句", "核心依据3，完整短句"],
    "risk_focus": ["风险提示1，完整短句", "风险提示2，完整短句", "风险提示3，完整短句"],
    "watch_items": ["后续观察点1，完整短句", "后续观察点2，完整短句", "后续观察点3，完整短句"],
    "uncertainty_note": "一句话说明还缺哪些公开信息验证，不超过45字"
  }},
  "analysis_summary": {{
    "overall_view": "综合研究概述",
    "key_points": ["关键点1", "关键点2"]
  }},
  "neutral_operation_advice": {{
    "recommended_analysis_view": "偏强|中性|偏弱|待验证",
    "confidence": 0-100的整数（表示研究判断稳定度，不代表交易把握）, 
    "core_judgment": "当前持仓所处研究阶段与核心判断",
    "reasoning": ["依据1", "依据2"],
    "analysis_points": ["观察要点1", "观察要点2"],
    "specific_suggestions": [
      {{
        "action": "继续跟踪",
        "reason": "说明当前最应优先跟踪的公开信号"
      }}
    ],
    "risk_reminder": "主要风险提示"
  }},
  "risk_assessment": "详细风险评估（300-500字）",
  "opportunity_assessment": "详细催化与改善条件（300-500字）",
  "specific_plan": {{
    "immediate_step": "下一步应优先核对的事实或披露",
    "observation_factors": ["后续观察事项1", "后续观察事项2"]
  }}
}}
```

**免责声明**：
本分析仅用于研究辅助与风险提示，不构成任何交易建议或执行指令。"""


def build_position_advisor_user_prompt() -> str:
  return """请综合以下分析，形成持仓研究判断：

=== 持仓信息 ===
- 股票: {{code}} {{name}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 浮动盈亏: {{unrealized_pnl_pct}}

=== 技术面分析 ===
{{technical_analysis}}

=== 基本面分析 ===
{{fundamental_analysis}}

=== 风险评估 ===
{{risk_analysis}}

=== 用户目标 ===
- 目标收益: {{target_return}}%
- 止损线: {{stop_loss}}%

请给出JSON格式的持仓研究结论：
```json
{
  "user_view": {
    "conclusion": "一句话结论，白话短句",
    "position_context": "持仓影响说明，白话短句",
    "key_points": ["核心依据1，完整短句", "核心依据2，完整短句", "核心依据3，完整短句"],
    "risk_focus": ["风险提示1，完整短句", "风险提示2，完整短句", "风险提示3，完整短句"],
    "watch_items": ["后续观察点1，完整短句", "后续观察点2，完整短句", "后续观察点3，完整短句"],
    "uncertainty_note": "不确定性说明，白话短句"
  },
  "analysis_summary": {
    "overall_view": "综合研究概述",
    "key_points": ["关键点1", "关键点2"]
  },
  "neutral_operation_advice": {
    "recommended_analysis_view": "偏强|中性|偏弱|待验证",
    "confidence": 0-100的整数（研究判断稳定度，不代表交易把握）, 
    "core_judgment": "当前持仓所处研究阶段与核心判断",
    "reasoning": ["理由1", "理由2"],
    "analysis_points": ["分析要点1", "分析要点2"],
    "specific_suggestions": [
      {
        "action": "继续跟踪",
        "reason": "说明当前最应优先跟踪的公开信号"
      }
    ],
    "risk_reminder": "主要风险提示"
  },
  "risk_assessment": "详细风险评估",
  "opportunity_assessment": "详细催化与改善条件",
  "specific_plan": {
    "immediate_step": "下一步应优先核对的事实或披露",
    "observation_factors": ["后续观察事项1", "后续观察事项2"]
  }
}
```

**重要提示**：
1. user_view 是给前端主界面直接展示的用户版内容，必须优先生成，且不得与后面的详细研究字段重复堆砌
2. user_view.conclusion 和 user_view.position_context 必须使用白话中文，不得出现“技术面”“基本面”“PB”“ROE”“均线”“MACD”“RSI”“KDJ”“站稳”“突破”“支撑位”“阻力位”“右侧介入”“放量”等术语或触发语
3. user_view.key_points、risk_focus、watch_items 每组最多3条，每条必须是完整短句；宁可少写也不要输出半句、截断句或长段落
4. 如果某条内容会以“将”“让”“获”“并”“但”“与”“或”“则”“需”等字结尾，说明句子不完整，必须重写，不得直接输出
5. key_points 不得写“当前判断主要基于已披露信息”“请持续关注”“后续重点观察”等空话，必须写具体依据
6. confidence 字段是必需的，必须是0-100的整数，表示研究判断稳定度，不代表交易把握
7. 严禁输出加仓、减仓、清仓、买卖、目标价、价格区间、止损止盈、仓位比例等执行性内容
8. 请根据综合分析给出真实的 confidence 值，不要使用默认值
9. specific_suggestions 和 observation_factors 必须是可继续验证的公开信号、研究动作或信息核查事项，不得写成交易动作
10. 严禁输出“评分”“站稳”“突破”“放量”“右侧介入”等会被用户理解为交易触发条件的表达"""


def build_position_advisor_output_format() -> str:
  return """**输出格式要求**：
必须使用JSON格式输出，包含以下核心字段：
- user_view（用户主界面展示内容，必需字段）
- analysis_summary（分析摘要）
- neutral_operation_advice（持仓分析观点，必须包含 recommended_analysis_view 和 confidence 字段）
- specific_plan（具体计划，必须包含 immediate_step 和 observation_factors）
- risk_assessment（风险评估，300-500字，必需字段）
- opportunity_assessment（催化与改善条件，300-500字，必需字段）

**user_view字段说明**：
- conclusion：1到2句白话短句，不超过36字
- position_context：说明这笔持仓当前意味着什么，不超过55字
- key_points / risk_focus / watch_items：每组最多3条，每条必须是完整短句
- uncertainty_note：一句白话短句，不超过45字

**confidence字段说明**：
- 类型：整数（0-100）
- 含义：研究判断稳定度，不代表交易把握
- 必需性：必需字段，必须提供

**观察事项说明**：
- observation_factors 只能写公开事实、后续披露、研究核查事项
- 不得写成价格触发条件、交易动作或仓位动作"""


def build_position_advisor_constraints(preference: str) -> str:
  style_label = POSITION_ADVISOR_STYLE_LABELS.get(preference, "中性")
  return f"""必须从{style_label}角度进行分析，保持一致的分析立场。必须严格按照JSON格式输出，确保所有必需字段都存在。

**user_view特别要求**：
- conclusion 和 position_context 必须使用白话中文，不得出现“技术面”“基本面”“PB”“ROE”“均线”“MACD”“RSI”“KDJ”等术语
- key_points、risk_focus、watch_items 每组最多3条，每条必须是完整短句，宁可少写也不要输出半句
- 若一句话以“将”“让”“获”“并”“但”“与”“或”“则”“需”等字结尾，视为截断句，必须重写
- 不得写“当前判断主要基于已披露信息”“请持续关注”“后续重点观察”等空话

**合规要求**：
- 严禁输出加仓、减仓、持有、清仓、买卖、目标价、价格区间、止损止盈、仓位比例、数量金额等执行性内容
- 严禁输出“评分”“站稳”“突破”“跌破”“放量”“缩量”“右侧介入”等会被理解为交易触发条件的表达
- 报告内容应直接开始，无需添加任何署名、日期或声明信息。"""


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
            update_fields = {
                "content.analysis_requirements": POSITION_ADVISOR_REQUIREMENTS[req_type],
                "updated_at": datetime.now(),
            }

            if agent_name == "pa_advisor_v2":
                update_fields.update({
                    "content.system_prompt": build_position_advisor_system_prompt(preference),
                    "content.user_prompt": build_position_advisor_user_prompt(),
                    "content.tool_guidance": f"**工具使用指导**:\n\n基于提供的分析报告进行{POSITION_ADVISOR_STYLE_LABELS.get(preference, '中性')}的综合分析。\n从{POSITION_ADVISOR_STYLE_LABELS.get(preference, '中性')}角度评估所有信息。",
                    "content.output_format": build_position_advisor_output_format(),
                    "content.constraints": build_position_advisor_constraints(preference),
                })

            result = collection.update_one(
                {
                    "agent_type": "position_analysis_v2",
                    "agent_name": agent_name,
                    "preference_type": preference,
                    "is_system": True
                },
                {
                    "$set": {
                    **update_fields
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

