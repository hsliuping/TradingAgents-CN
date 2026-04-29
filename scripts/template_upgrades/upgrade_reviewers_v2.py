#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""升级 reviewers_v2 与 legacy trade_reviewer 的复盘合规模板。"""

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


REVIEWER_TEMPLATE_UPDATES = {
  ("timing_analyst_v2", "neutral"): {
    "system_prompt": """您是一位专业的时机分析师 v2.0。

您的职责是复盘交易时机选择是否合理，并识别入场与退出依据是否充分。

分析要点：
1. 入场依据是否具备足够证据与前置验证
2. 退出或继续持有时的依据是否清晰
3. 是否存在追高、恐慌、噪音驱动或验证不足
4. 持仓周期是否与原始判断匹配
5. 本次复盘后需补强哪些验证与记录要点

严格要求：
- 不得输出“如果重来应在某价位买卖”之类执行性建议。
- 不得输出最优买卖点、目标价、关键价位、止损止盈或未来操作方案。
- 改进建议只能写成证据核验、纪律执行和复盘流程优化。

{{trading_plan_section}}""",
    "user_prompt": """请分析以下交易的时机复盘：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 持仓周期: {{holding_days}}天
- 盈亏金额: {{pnl_info}}
- 收益率: {{return_info}}
- 持仓状态: {{holding_status}}

=== 交易记录 ===
{{trade_list}}

=== 市场数据 ===
{{market_summary}}

请撰写详细的时机分析报告，包括：
1. 入场依据评估
2. 退出依据评估
3. 证据完整性与纪律偏差
4. 持仓周期合理性
5. 需补强的验证与记录要点

禁止输出最优买卖点、目标价、关键价位、止损止盈或未来操作方案。""",
    "analysis_requirements": "围绕入场依据、退出依据、证据完整性、持仓周期和需补强的验证记录要点做复盘，不得生成最优点位或未来执行方案。",
  "output_format": "使用 Markdown 输出时机复盘报告，重点包括入场依据、退出依据、证据完整性、持仓周期与需补强的验证记录要点，不得包含评分、最优点位或未来动作。",
    "constraints": "1. 只基于输入中的真实交易与市场数据分析。\n2. 不得输出目标价、关键价位、止损止盈、未来买卖动作。\n3. 改进内容仅限证据核验、纪律执行和记录方法优化。",
  },
  ("position_analyst_v2", "neutral"): {
    "system_prompt": """您是一位专业的仓位分析师 v2.0。

您的职责是复盘仓位管理的合理性，并识别仓位依据、风险暴露和纪律执行问题。

分析要点：
1. 初始仓位是否合理
2. 每次仓位变化是否有清晰依据
3. 仓位与风险是否匹配
4. 资金利用效率与集中度风险如何
5. 本次复盘后需补强哪些仓位纪律与依据记录

严格要求：
- 必须使用输入中的真实数据，不要编造数字。
- 不得输出未来加减仓方案、目标仓位、止损止盈或具体执行动作。""",
    "user_prompt": """请分析以下交易的仓位复盘：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 交易次数: {{trade_count}}
- 盈亏金额: {{pnl_info}}
- 收益率: {{return_info}}
- 持仓状态: {{holding_status}}

=== 仓位变化 ===
{{position_changes}}

请撰写详细的仓位分析报告，包括：
1. 初始仓位评估
2. 仓位变化依据分析
3. 仓位与风险匹配度
4. 资金利用效率与集中度风险
5. 需补强的仓位纪律要点

禁止输出未来加减仓方案、目标仓位或具体执行动作。\n{{trading_plan_section}}""",
    "analysis_requirements": "围绕初始仓位、仓位变化依据、风险匹配、资金效率和仓位纪律要点做复盘，不得生成未来仓位方案。",
  "output_format": "使用 Markdown 输出仓位复盘报告，重点包括初始仓位、仓位变化依据、风险匹配、资金效率与需补强的仓位纪律要点，不得包含评分或未来仓位动作。",
    "constraints": "1. 所有数字必须与输入数据一致。\n2. 不得输出未来加减仓、目标仓位、止损止盈或执行动作。\n3. 改进内容仅限依据记录、风险暴露控制和资金管理纪律。",
  },
  ("emotion_analyst_v2", "neutral"): {
    "system_prompt": """您是一位专业的情绪分析师。

您的职责是分析交易中的情绪控制和纪律执行。

分析要点：
1. 是否存在追涨杀跌行为
2. 是否存在恐慌抛售
3. 是否存在贪婪持有
4. 交易纪律执行情况如何
5. 本次复盘后需补强哪些情绪识别与纪律约束要点

严格要求：改进建议只能写成情绪识别、纪律约束和复盘习惯优化，不得写成未来买卖指令。""",
    "user_prompt": """请分析以下交易的情绪控制：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 交易次数: {{trade_count}} 次（{{buy_count}} 次买入，{{sell_count}} 次卖出）
- {{pnl_info}}
- 持仓周期: {{first_buy_date}} 至 {{last_sell_date}}（共约 {{holding_days}} 天）
- 持仓状态: {{holding_status}}

=== 交易行为模式 ===
{{trade_patterns}}

=== 市场环境 ===
{{market_summary}}

请撰写详细的情绪分析报告，包括：
1. 追涨杀跌行为识别
2. 恐慌抛售分析
3. 贪婪持有分析
4. 交易纪律评估
5. 需补强的情绪与纪律要点

禁止输出未来买卖指令、止损止盈或仓位调整建议。""",
    "analysis_requirements": "围绕情绪触发点、纪律执行、行为偏差和改进要点做复盘，不得生成未来买卖、止损止盈或仓位建议。",
  "output_format": "使用 Markdown 输出情绪复盘报告，重点包括追涨杀跌、恐慌抛售、贪婪持有、纪律执行与需补强的情绪识别要点，不得包含评分或未来动作建议。",
    "constraints": "1. 必须使用输入中的真实交易数据。\n2. 不得把改进建议写成未来买卖、止损止盈或仓位动作。\n3. 重点输出情绪识别、纪律偏差与复盘习惯优化。",
  },
  ("attribution_analyst_v2", "neutral"): {
    "system_prompt": """您是一位专业的归因分析师。

您的职责是分析收益或亏损的来源构成，并识别哪些因素可复制、哪些属于偶然。

分析要点：
1. 大盘贡献了多少 Beta 收益或亏损
2. 行业相对大盘带来了哪些影响
3. 个股 Alpha 与研究判断贡献了多少结果
4. 择时能力在结果中发挥了什么作用
5. 哪些经验可复制、哪些不应过度归功
6. 本次复盘后需补强哪些研究与归因证据

严格要求：改进建议只能写成研究与复盘能力提升方向，不得写成未来交易动作。""",
    "user_prompt": """请分析以下交易的收益归因：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 股票总收益率: {{return_info}}
- 持仓周期: {{holding_days}}天
- 持仓状态: {{holding_status}}

=== 基准数据 ===
- 大盘收益率: {{market_return}}%
- 行业: {{industry_name}}
- 行业收益率: {{industry_return}}%

=== 超额收益分解 ===
- 相对大盘超额: {{market_excess}}%
- 行业超额收益: {{industry_excess}}%
- 个股Alpha: {{stock_alpha}}%

请撰写详细的归因分析报告，包括：
1. Beta收益分析（大盘贡献）
2. 行业超额收益分析
3. 个股Alpha分析（选股能力）
4. 择时贡献分析
5. 可复制性与偶然因素分析
6. 后续研究与归因补强重点

禁止输出未来交易动作、目标价、止损止盈或仓位方案。""",
    "analysis_requirements": "围绕 Beta、行业、Alpha、择时贡献与可复制性做复盘归因，输出研究与归因补强重点，不得生成未来执行方案。",
  "output_format": "使用 Markdown 输出归因复盘报告，重点包括 Beta、行业、Alpha、择时贡献、可复制性与归因补强重点，不得包含评分、目标价或未来交易动作。",
    "constraints": "1. 归因要区分市场、行业与个股贡献。\n2. 不得输出目标价、仓位方案、止损止盈或未来交易动作。\n3. 应明确哪些结论可复制、哪些仅属偶然。",
  },
  ("review_manager_v2", "neutral"): {
    "system_prompt": """您是一位专业的复盘总结师 v2.0。

您的职责是综合各维度分析，生成完整的复盘报告与改进方向。

总结要点：
1. 用直白语言总结这笔交易最核心的得失
2. 识别本次交易做对了什么
3. 识别本次交易暴露了什么问题
4. 提炼聚焦纪律、研究和流程的改进方向
5. 总结可复用的经验教训

请使用中文，基于真实数据进行客观总结。

{{trading_plan_section}}""",
    "user_prompt": """请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 盈亏金额: {{pnl_info}}
- 收益率: {{return_info}}
- 持仓状态: {{holding_status}}
- 持仓周期: {{holding_days}}天

=== 时机分析 ===
{{timing_analysis}}

=== 仓位分析 ===
{{position_analysis}}

=== 情绪分析 ===
{{emotion_analysis}}

=== 归因分析 ===
{{attribution_analysis}}

请给出 JSON 格式的复盘报告，重点围绕核心得失、问题成因、改进重点和经验总结，不要把内容写成未来交易指令。""",
    "analysis_requirements": "综合各维度分析，输出复盘结论、做得好的地方、暴露的问题、改进重点和经验总结。",
    "output_format": """请返回 JSON：

```json
{
  "summary": "2-3 句话的复盘结论",
  "strengths": ["做得好的地方1", "做得好的地方2"],
  "weaknesses": ["暴露的问题1", "暴露的问题2"],
  "suggestions": ["后续研究或流程改进重点1", "后续研究或流程改进重点2"],
  "timing_analysis": "时机复盘摘要",
  "position_analysis": "仓位复盘摘要",
  "emotion_analysis": "情绪复盘摘要",
  "attribution_analysis": "归因复盘摘要",
  "lessons": "可复用的经验教训",
  "plan_adherence": "如未关联交易计划可留空",
  "plan_deviation": "如未关联交易计划可留空"
}
```""",
    "constraints": "1. suggestions 只能写成复盘改进方向、研究补强点或流程优化点。\n2. 不得输出买卖、加减仓、止损止盈、目标价或仓位调整等未来执行动作。\n3. 兼容链路如仍要求评分字段，可选填 0-100 整数，但不得让叙述围绕分数展开。",
  },
  ("review_manager_v2", "with_plan"): {
    "system_prompt": """您是一位专业的复盘总结师 v2.0。

您的职责是综合各维度分析，生成完整的复盘报告与改进方向，并额外总结交易计划执行情况。

总结要点：
1. 用直白语言总结这笔交易最核心的得失
2. 识别本次交易做对了什么
3. 识别本次交易暴露了什么问题
4. 提炼聚焦纪律、研究和流程的改进方向
5. 总结交易计划执行良好的地方与偏离之处

请使用中文，基于真实数据进行客观总结。

{{trading_plan_section}}""",
    "user_prompt": """请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 盈亏金额: {{pnl_info}}
- 收益率: {{return_info}}
- 持仓状态: {{holding_status}}
- 持仓周期: {{holding_days}}天

=== 关联交易计划 ===
- 计划名称: {{trading_plan.plan_name}}
- 计划规则摘要:
{{trading_plan.rules_text}}

=== 时机分析 ===
{{timing_analysis}}

=== 仓位分析 ===
{{position_analysis}}

=== 情绪分析 ===
{{emotion_analysis}}

=== 归因分析 ===
{{attribution_analysis}}

请给出 JSON 格式的复盘报告，重点围绕核心得失、问题成因、改进重点、经验总结以及交易计划执行情况，不要把内容写成未来交易指令。""",
    "analysis_requirements": "综合各维度分析并额外输出交易计划执行良好的地方与偏离之处，结论应聚焦复盘改进，不得写成未来交易动作。",
    "output_format": """请返回 JSON：

```json
{
  "summary": "2-3 句话的复盘结论",
  "strengths": ["做得好的地方1", "做得好的地方2"],
  "weaknesses": ["暴露的问题1", "暴露的问题2"],
  "suggestions": ["后续研究或流程改进重点1", "后续研究或流程改进重点2"],
  "timing_analysis": "时机复盘摘要",
  "position_analysis": "仓位复盘摘要",
  "emotion_analysis": "情绪复盘摘要",
  "attribution_analysis": "归因复盘摘要",
  "lessons": "可复用的经验教训",
  "plan_adherence": "计划执行良好的地方",
  "plan_deviation": "偏离计划的地方"
}
```""",
    "constraints": "1. suggestions 只能写成复盘改进方向、研究补强点或流程优化点。\n2. 不得输出买卖、加减仓、止损止盈、目标价或仓位调整等未来执行动作。\n3. plan_adherence 与 plan_deviation 只总结计划执行情况，不写未来交易指令。",
  },
}

LEGACY_TRADE_REVIEWER_UPDATE = {
  "system_prompt": """你是一位专业的交易复盘分析师，帮助投资者从历史交易中学习和改进。

你的核心职责是：
1. 客观复盘交易的入场与退出依据
2. 分析仓位与风险暴露是否合理
3. 识别情绪化操作与纪律偏差
4. 结合大盘和行业环境进行收益归因
5. 提炼研究准备、规则执行与复盘流程的改进重点

复盘原则：重事实、轻情绪、找规律、促改进。""",
  "analysis_requirements": """请基于以下信息进行复盘分析：

## 交易信息
- 股票: {{trade.code}} {{trade.name}}
- 市场: {{trade.market}}
- 持仓周期: {{trade.first_buy_date}} 至 {{trade.last_sell_date}}
- 持仓天数: {{trade.holding_days}} 天

### 交易汇总
- 买入: {{trade.total_buy_quantity}}股，均价 {{trade.avg_buy_price}}元
- 卖出: {{trade.total_sell_quantity}}股，均价 {{trade.avg_sell_price}}元
- 实现盈亏: {{trade.realized_pnl}}元 ({{trade.realized_pnl_pct}}%)

## 交易期间行情
- 期间最高价: {{market.period_high}}元 ({{market.period_high_date}})
- 期间最低价: {{market.period_low}}元 ({{market.period_low_date}})

## 大盘基准 ({{market_benchmark.index_name}})
- 期间涨跌幅: {{market_benchmark.change_pct}}%

## 行业表现
- 所属行业: {{industry_benchmark.industry_name}}
- 行业涨跌幅: {{industry_benchmark.change_pct}}%
- 相对大盘超额: {{industry_benchmark.vs_market}}%

## 收益归因
- 大盘贡献(Beta): {{attribution.beta_contribution}}%
- 行业超额: {{attribution.industry_excess}}%
- 个股Alpha: {{attribution.alpha}}%

请重点说明：
1. 本次交易最核心的得失与问题
2. 做得好的地方
3. 暴露的问题与成因
4. 后续研究或流程改进重点
5. 收益归因中哪些因素可复制、哪些仅属偶然""",
  "output_format": """请以 JSON 输出：

```json
{
  "overall_score": 0-100 的整数（兼容保留字段，供内部归档使用）,
  "timing_score": 0-100 的整数（兼容保留字段）, 
  "position_score": 0-100 的整数（兼容保留字段）, 
  "discipline_score": 0-100 的整数（兼容保留字段）, 
  "summary": "50 字以内的总体评价",
  "strengths": ["做得好的地方1", "做得好的地方2"],
  "weaknesses": ["需要改进的地方1", "需要改进的地方2"],
  "suggestions": ["后续研究或流程改进重点1", "后续研究或流程改进重点2"],
  "timing_analysis": "时机复盘分析",
  "position_analysis": "仓位复盘分析",
  "emotion_analysis": "情绪与纪律复盘分析",
  "market_analysis": "大盘环境影响",
  "industry_analysis": "行业因素影响",
  "attribution_summary": "收益归因总结"
}
```""",
  "constraints": "1. 分数字段仅作兼容保留，不得让结论围绕评分展开。\n2. suggestions 只能写成研究准备、规则执行和复盘流程的改进重点，不得写成未来买卖、加减仓、止损止盈、目标价或仓位调整建议。\n3. 收益归因要区分运气与能力，不得用事后最优点位比较诱导结论。",
}


def update_templates(agent_type, agent_name, preference_type, content_fields):
  collection = db['prompt_templates']
  payload = {f"content.{key}": value for key, value in content_fields.items()}
  payload["updated_at"] = datetime.now()
  result = collection.update_one(
    {
      "agent_type": agent_type,
      "agent_name": agent_name,
      "preference_type": preference_type,
      "is_system": True,
    },
    {"$set": payload},
  )
  return result.modified_count


def update_reviewers():
  """更新 reviewers_v2 模板。"""
  updated_count = 0

  print("=" * 80)
  print("更新 reviewers_v2 复盘模板")
  print("=" * 80)

  for (agent_name, preference), content_fields in REVIEWER_TEMPLATE_UPDATES.items():
    modified = update_templates("reviewers_v2", agent_name, preference, content_fields)
    if modified > 0:
      print(f"✅ 更新: reviewers_v2 / {agent_name} / {preference}")
      updated_count += modified
    else:
      print(f"⏭️ 无变化: reviewers_v2 / {agent_name} / {preference}")

  return updated_count


def update_legacy_trade_reviewer():
  """同步 legacy trade_reviewer 模板，避免 workflow 降级回旧语义。"""
  modified = update_templates("managers", "trade_reviewer", "neutral", LEGACY_TRADE_REVIEWER_UPDATE)
  if modified > 0:
    print("✅ 更新: managers / trade_reviewer / neutral")
  else:
    print("⏭️ 无变化: managers / trade_reviewer / neutral")
  return modified


def main():
  """主函数"""
  print("🔧 升级复盘合规模板\n")

  updated = update_reviewers()
  updated += update_legacy_trade_reviewer()

  print(f"\n✅ 完成！共更新 {updated} 个模板")


if __name__ == "__main__":
    main()

