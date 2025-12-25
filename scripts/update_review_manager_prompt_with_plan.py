"""
创建 review_manager_v2_with_plan 提示词模板（带交易计划对比分析）
"""
import asyncio
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime

# MongoDB 连接配置
username = quote_plus("admin")
password = quote_plus("tradingagents123")
MONGO_URI = f"mongodb://{username}:{password}@localhost:27017/"

async def create_review_manager_with_plan_template():
    """创建 review_manager_v2_with_plan 提示词模板"""
    client = MongoClient(MONGO_URI)
    db = client["tradingagents"]
    collection = db["prompt_templates"]

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
   例如：timing_score=7, position_score=7, discipline_score=6，则 overall_score = round((7+7+6)/3) = 7
3. summary 和 lessons 必须是字符串，不能是对象或数组
4. strengths、weaknesses、suggestions 必须是字符串数组
5. 请根据实际分析给出真实的评分，不要使用示例中的默认值
6. **禁止在输出中包含任何日期信息**（如"2025年4月5日"、"分析时间"等），日期由系统自动生成
7. summary、lessons、strengths、weaknesses、suggestions 中都不要包含日期
8. plan_adherence 和 plan_deviation 必须是字符串，简明扼要地说明计划执行情况"""

    # 检查是否已存在（使用 preference_id="with_plan" 来区分）
    existing = collection.find_one({
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2",
        "preference_id": "with_plan",
        "is_system": True,
        "status": "active"
    })

    if existing:
        print("⚠️ review_manager_v2 (with_plan) 模板已存在，将更新...")
        result = collection.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "template_name": "复盘总结师 v2.0 - 含交易计划",  # 🔑 更新模板名称
                    "version": 2,  # 🔑 更新版本号
                    "source": "system",  # 🔑 更新来源
                    "content.system_prompt": system_prompt,
                    "content.user_prompt": user_prompt,
                    "content.output_format": output_format,
                    "updated_at": datetime.now()
                }
            }
        )
        print(f"✅ 成功更新 review_manager_v2 (with_plan) 模板")
    else:
        print("📝 创建新的 review_manager_v2 (with_plan) 模板...")
        template_doc = {
            "agent_type": "reviewers_v2",
            "agent_name": "review_manager_v2",
            "template_name": "复盘总结师 v2.0 - 含交易计划",  # 🔑 添加模板名称
            "preference_id": "with_plan",  # 🔑 使用 preference_id 区分
            "version": 2,  # 🔑 添加版本号
            "source": "system",  # 🔑 添加来源
            "is_system": True,
            "status": "active",
            "content": {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "output_format": output_format,
                "tool_guidance": "",
                "analysis_requirements": "",
                "constraints": ""
            },
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        collection.insert_one(template_doc)
        print(f"✅ 成功创建 review_manager_v2 (with_plan) 模板")

    print(f"   - Agent名称: review_manager_v2")
    print(f"   - Preference ID: with_plan")
    print(f"   - 添加了交易计划规则展示")
    print(f"   - 添加了 plan_adherence 和 plan_deviation 字段")
    print(f"\n💡 使用方式：")
    print(f"   - 无交易计划: get_user_prompt(agent_name='review_manager_v2', preference_id='neutral')")
    print(f"   - 有交易计划: get_user_prompt(agent_name='review_manager_v2', preference_id='with_plan')")

    client.close()

if __name__ == "__main__":
    asyncio.run(create_review_manager_with_plan_template())

