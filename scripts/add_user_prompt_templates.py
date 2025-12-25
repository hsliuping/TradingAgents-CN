"""
添加用户提示词模板到 reviewers_v2

本脚本的目的：
1. 为所有5个 reviewers_v2 分析师添加 user_prompt 字段
2. user_prompt 包含变量占位符，支持动态数据替换
3. 确保所有提示词都在数据库中管理，而不是硬编码在代码中

包含的分析师：
- emotion_analyst_v2 (情绪分析师)
- position_analyst_v2 (仓位分析师)
- timing_analyst_v2 (时机分析师)
- attribution_analyst_v2 (归因分析师)
- review_manager_v2 (复盘管理器)
"""

from pymongo import MongoClient

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

print("=" * 80)
print("添加用户提示词模板到所有 reviewers_v2 分析师")
print("=" * 80)

# 情绪分析师的用户提示词模板
EMOTION_USER_PROMPT = """请分析以下交易的情绪控制：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 交易次数: {{trade_count}} 次（{{buy_count}} 次买入，{{sell_count}} 次卖出）
- 最终收益: {{pnl_sign}}{{realized_pnl}}元（{{pnl_sign}}{{realized_pnl_pct}}%）
- 持仓周期: {{first_buy_date}} 至 {{last_sell_date}}（共约 {{holding_days}} 天）

=== 交易行为模式 ===
{{trade_patterns}}

=== 市场环境 ===
{{market_summary}}

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据（收益金额、收益率、持仓周期等）必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的情绪分析报告，包括：
1. 追涨杀跌行为识别
2. 恐慌抛售分析
3. 贪婪持有分析
4. 交易纪律评估
5. 情绪控制评分（1-10分）"""

# 仓位分析师的用户提示词模板
POSITION_USER_PROMPT = """请分析以下交易的仓位管理：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 交易次数: {{trade_count}}
- 盈亏金额: {{pnl_sign}}{{realized_pnl}}元
- 收益率: {{pnl_sign}}{{realized_pnl_pct}}%

=== 仓位变化 ===
{{position_changes}}

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据（收益金额、收益率等）必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的仓位分析报告，包括：
1. 初始仓位评估
2. 加减仓策略分析
3. 仓位与风险匹配度
4. 资金利用效率
5. 仓位管理评分（1-10分）"""

# 时机分析师的用户提示词模板
TIMING_USER_PROMPT = """请分析以下交易的时机选择：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 持仓周期: {{holding_days}}天
- 盈亏金额: {{pnl_sign}}{{realized_pnl}}元
- 收益率: {{pnl_sign}}{{realized_pnl_pct}}%

=== 交易记录 ===
{{trade_list}}

=== 市场数据 ===
{{market_summary}}

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的时机分析报告，包括：
1. 买入时机评估
2. 卖出时机评估
3. 与最优点的差距
4. 持仓周期合理性
5. 时机选择评分（1-10分）"""

# 归因分析师的用户提示词模板
ATTRIBUTION_USER_PROMPT = """请分析以下交易的收益归因：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 股票收益率: {{stock_return}}%
- 持仓周期: {{holding_days}}天

=== 基准数据 ===
- 大盘收益率: {{market_return}}%
- 行业: {{industry_name}}
- 行业收益率: {{industry_return}}%

=== 超额收益分解 ===
- 相对大盘超额: {{market_excess}}%
- 行业超额收益: {{industry_excess}}%
- 个股Alpha: {{stock_alpha}}%

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的归因分析报告，包括：
1. Beta收益分析（大盘贡献）
2. 行业超额收益分析
3. 个股Alpha分析（选股能力）
4. 择时贡献分析
5. 收益质量评分（1-10分）"""

# 复盘管理器的用户提示词模板
REVIEW_MANAGER_USER_PROMPT = """请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 盈亏金额: {{pnl_sign}}{{realized_pnl}}元
- 收益率: {{pnl_sign}}{{realized_pnl_pct}}%
- 持仓周期: {{holding_days}}天

=== 时机分析 ===
{{timing_analysis}}

=== 仓位分析 ===
{{position_analysis}}

=== 情绪分析 ===
{{emotion_analysis}}

=== 归因分析 ===
{{attribution_analysis}}

**重要提示**：
- 报告中的所有数据必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请给出JSON格式的复盘报告。"""

# 更新情绪分析师 v2.0
print("\n" + "=" * 80)
print("更新情绪分析师 v2.0")
print("=" * 80)

emotion_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'emotion_analyst_v2'
})

for template in emotion_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')
    
    print(f"\n更新模板: {template_id} (偏好: {preference})")
    
    # 添加 user_prompt 字段
    db.prompt_templates.update_one(
        {'_id': template_id},
        {'$set': {'content.user_prompt': EMOTION_USER_PROMPT}}
    )
    print(f"  ✅ 已添加 user_prompt 字段")

# 更新仓位分析师 v2.0
print("\n" + "=" * 80)
print("更新仓位分析师 v2.0")
print("=" * 80)

position_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'position_analyst_v2'
})

for template in position_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')
    
    print(f"\n更新模板: {template_id} (偏好: {preference})")
    
    # 添加 user_prompt 字段
    db.prompt_templates.update_one(
        {'_id': template_id},
        {'$set': {'content.user_prompt': POSITION_USER_PROMPT}}
    )
    print(f"  ✅ 已添加 user_prompt 字段")

# 更新时机分析师 v2.0
print("\n" + "=" * 80)
print("更新时机分析师 v2.0")
print("=" * 80)

timing_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'timing_analyst_v2'
})

for template in timing_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')

    print(f"\n更新模板: {template_id} (偏好: {preference})")

    # 添加 user_prompt 字段
    db.prompt_templates.update_one(
        {'_id': template_id},
        {'$set': {'content.user_prompt': TIMING_USER_PROMPT}}
    )
    print(f"  ✅ 已添加 user_prompt 字段")

# 更新归因分析师 v2.0
print("\n" + "=" * 80)
print("更新归因分析师 v2.0")
print("=" * 80)

attribution_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'attribution_analyst_v2'
})

for template in attribution_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')

    print(f"\n更新模板: {template_id} (偏好: {preference})")

    # 添加 user_prompt 字段
    db.prompt_templates.update_one(
        {'_id': template_id},
        {'$set': {'content.user_prompt': ATTRIBUTION_USER_PROMPT}}
    )
    print(f"  ✅ 已添加 user_prompt 字段")

# 更新复盘管理器 v2.0
print("\n" + "=" * 80)
print("更新复盘管理器 v2.0")
print("=" * 80)

manager_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'review_manager_v2'
})

for template in manager_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')

    print(f"\n更新模板: {template_id} (偏好: {preference})")

    # 添加 user_prompt 字段
    db.prompt_templates.update_one(
        {'_id': template_id},
        {'$set': {'content.user_prompt': REVIEW_MANAGER_USER_PROMPT}}
    )
    print(f"  ✅ 已添加 user_prompt 字段")

print("\n" + "=" * 80)
print("更新完成！")
print("=" * 80)
print("\n说明：")
print("- 已为所有5个 reviewers_v2 分析师添加 user_prompt 字段：")
print("  1. emotion_analyst_v2 (情绪分析师)")
print("  2. position_analyst_v2 (仓位分析师)")
print("  3. timing_analyst_v2 (时机分析师)")
print("  4. attribution_analyst_v2 (归因分析师)")
print("  5. review_manager_v2 (复盘管理器)")
print("- user_prompt 包含变量占位符（如 {{code}}, {{name}}, {{realized_pnl}} 等）")
print("\n下一步：")
print("1. 修改 timing_analyst_v2.py, attribution_analyst_v2.py, review_manager_v2.py 的代码")
print("2. 让它们的 _build_user_prompt 方法使用模板系统")
print("3. 重启后端服务")
print("4. 测试复盘分析功能")

