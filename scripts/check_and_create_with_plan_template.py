#!/usr/bin/env python3
"""检查并创建 with_plan 模板"""

import asyncio
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime

# MongoDB 连接配置
username = quote_plus("admin")
password = quote_plus("tradingagents123")
MONGO_URI = f"mongodb://{username}:{password}@localhost:27017/"

def check_and_create_template():
    """检查并创建 with_plan 模板"""
    client = MongoClient(MONGO_URI)
    db = client["tradingagents"]
    collection = db["prompt_templates"]

    # 检查是否已存在
    existing = collection.find_one({
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2",
        "preference_id": "with_plan"
    })

    if existing:
        print("✅ with_plan 模板已存在")
        print(f"   - template_name: {existing.get('template_name')}")
        print(f"   - version: {existing.get('version')}")
        print(f"   - created_at: {existing.get('created_at')}")
        return

    print("❌ with_plan 模板不存在，开始创建...")

    # system_prompt（与原版相同）
    system_prompt = """你是一位资深的交易复盘分析师，负责综合多维度分析结果，生成完整的复盘报告。

你的职责：
1. 综合时机、仓位、情绪、归因等维度的分析
2. 给出客观、准确的评分
3. 总结优点、不足和改进建议
4. 提供可操作的经验教训

请使用中文，基于真实数据进行客观总结。"""

    # user_prompt（带交易计划）
    user_prompt = """请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 盈亏金额: {{pnl_sign}}{{realized_pnl}}元
- 收益率: {{pnl_sign}}{{realized_pnl_pct}}%
- 持仓周期: {{holding_days}}天

=== 关联交易计划 ===
**计划名称**: {{trading_plan.plan_name}}
**计划风格**: {{trading_plan.style}}

**交易计划规则**:
{{trading_plan.rules_text}}

**重要**: 请在分析中重点对比本次交易与交易计划规则的符合程度，指出执行良好和违反规则的地方。

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
- 必须在 plan_adherence 和 plan_deviation 字段中提供交易计划执行情况分析

请给出JSON格式的复盘报告。"""

    # output_format（带交易计划字段）
    output_format = """请以JSON格式输出复盘报告，必须严格按照以下结构：

```json
{
    "overall_score": 7,
    "timing_score": 7,
    "position_score": 7,
    "discipline_score": 6,
    "summary": "2-3句话的综合评价（必须是字符串，不能是对象）",
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "suggestions": ["建议1", "建议2", "建议3"],
    "lessons": "经验教训总结（必须是字符串）",
    "plan_adherence": "交易计划执行情况总结（1-2句话，说明哪些规则执行良好）",
    "plan_deviation": "与计划的主要偏离点（1-2句话，说明违反了哪些规则，如无偏离则说明'完全符合计划'）"
}
```

**重要提示**：
1. overall_score、timing_score、position_score、discipline_score 必须是 1-10 的整数
2. overall_score 应该是 timing_score、position_score、discipline_score 的平均值（四舍五入）
3. summary 和 lessons 必须是字符串，不能是对象或数组
4. strengths、weaknesses、suggestions 必须是字符串数组
5. 请根据实际分析给出真实的评分，不要使用示例中的默认值
6. **禁止在输出中包含任何日期信息**
7. plan_adherence 和 plan_deviation 必须是字符串，简明扼要地说明计划执行情况"""

    # 创建模板文档
    template_doc = {
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2",
        "preference_id": "with_plan",
        "template_name": "复盘总结师（含交易计划对比）",
        "version": "2.0.1",
        "content": {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_format": output_format,
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # 插入数据库
    result = collection.insert_one(template_doc)
    print(f"✅ 成功创建 with_plan 模板")
    print(f"   - _id: {result.inserted_id}")
    print(f"   - template_name: {template_doc['template_name']}")
    print(f"   - version: {template_doc['version']}")

if __name__ == "__main__":
    check_and_create_template()

