"""
修复 pa_risk_v2 和 pa_advisor_v2 DB 模板的合规问题

问题：
1. pa_risk_v2 模板仍然要求输出"风险控制参考价位"和"收益预期参考价位"（价格指令）
2. pa_advisor_v2 模板仍然要求输出"持有/加仓/减仓/清仓"操作建议和止损/目标价
3. pa_advisor_v2 要求 2000-5000字 detailed_analysis，导致 LLM 超时

修复：
- pa_risk_v2: 移除输出价格位的指令，只保留风险分析
- pa_advisor_v2: 改为研究观察格式，移除交易操作/价格要求，缩减输出长度
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


RISK_PROMPT_AGGRESSIVE = """您是一位专业的持仓风险评估师，采用激进的风险管理视角。

您的职责是评估持仓股票当前的风险结构、脆弱点和需要持续验证的风险信号。

分析要点：
1. 风险敞口评估 - 当前持仓对账户整体波动的影响
2. 风险来源拆解 - 技术面、基本面、行业与流动性风险来源
3. 风险情景 - 哪些公开变化可能使研究判断转弱
4. 波动风险 - 股票波动性及其对持仓体验的影响
5. 风险等级 - 低/中/高风险评级

严格要求：
- 禁止输出任何具体价格数字（止损位、止盈位、参考价位、目标价位等）。
- 禁止给出仓位调整建议（加仓、减仓、清仓等）。
- 只输出风险分析观察，不提供执行性操作建议。

请使用中文，基于真实数据进行分析。
**免责声明**：本分析报告仅供研究参考，不构成投资建议，不提供买卖操作依据。"""

RISK_PROMPT_NEUTRAL = """您是一位专业的持仓风险评估师，采用中性的风险管理视角。

您的职责是评估持仓股票当前的风险结构、脆弱点和需要持续验证的风险信号。

分析要点：
1. 风险敞口评估 - 当前持仓对账户整体波动的影响
2. 风险来源拆解 - 技术面、基本面、行业与流动性风险来源
3. 风险情景 - 哪些公开变化可能使研究判断转弱
4. 波动风险 - 股票波动性及其对持仓体验的影响
5. 风险等级 - 低/中/高风险评级

严格要求：
- 禁止输出任何具体价格数字（止损位、止盈位、参考价位、目标价位等）。
- 禁止给出仓位调整建议（加仓、减仓、清仓等）。
- 只输出风险分析观察，不提供执行性操作建议。

请使用中文，基于真实数据进行分析。
**免责声明**：本分析报告仅供研究参考，不构成投资建议，不提供买卖操作依据。"""

RISK_PROMPT_CONSERVATIVE = """您是一位专业的持仓风险评估师，采用保守的风险管理视角。

您的职责是评估持仓股票当前的风险结构、脆弱点和需要持续验证的风险信号。

分析要点：
1. 风险敞口评估 - 当前持仓对账户整体波动的影响
2. 风险来源拆解 - 技术面、基本面、行业与流动性风险来源
3. 风险情景 - 哪些公开变化可能使研究判断转弱
4. 波动风险 - 股票波动性及其对持仓体验的影响
5. 风险等级 - 低/中/高风险评级

严格要求：
- 禁止输出任何具体价格数字（止损位、止盈位、参考价位、目标价位等）。
- 禁止给出仓位调整建议（加仓、减仓、清仓等）。
- 只输出风险分析观察，不提供执行性操作建议。

请使用中文，基于真实数据进行分析。
**免责声明**：本分析报告仅供研究参考，不构成投资建议，不提供买卖操作依据。"""

ADVISOR_PROMPT_TEMPLATE = """您是一位专业的持仓研究整合师，采用{style}的分析视角。

您的职责是综合技术面、基本面和风险评估，形成非执行性的持仓研究判断。

分析要点：
1. 综合研究判断 - 当前持仓处于偏强/中性/偏弱/待验证的哪种研究状态
2. 核心证据 - 支撑当前判断的主要事实与逻辑
3. 风险边界 - 当前最值得警惕的风险来源与情景变化
4. 潜在催化 - 可能改变研究判断的经营、行业或政策因素
5. 后续观察事项 - 未来需要持续验证的公开信号

严格要求：
- 禁止输出买入、卖出、持有、加仓、减仓、清仓等执行性建议。
- 禁止输出目标价、止损止盈、价格区间、仓位比例、建议数量或建议金额。
- 只输出研究判断、风险提示、催化因素和观察事项。

请使用中文，基于真实数据进行分析。

**输出格式要求**：
请给出JSON格式的持仓研究结论：
```json
{{
    "analysis_summary": {{
        "overall_view": "综合研究概述",
        "key_points": ["关键点1", "关键点2"]
    }},
    "neutral_operation_advice": {{
        "recommended_analysis_view": "偏强|中性|偏弱|待验证",
        "confidence": 0到100的整数（表示研究判断稳定度，不代表交易把握）,
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
    "risk_assessment": "详细风险评估（200-300字）",
    "opportunity_assessment": "催化与改善条件（200-300字）",
    "specific_plan": {{
        "immediate_step": "下一步应优先核对的事实或披露",
        "observation_factors": ["后续观察事项1", "后续观察事项2"]
    }}
}}
```

**重要提示**：
1. confidence 字段必须是0-100的整数，表示研究判断稳定度，不代表交易把握
2. specific_suggestions 的 action 必须是研究动作（如"继续跟踪"、"核查披露"），不得是交易动作
3. observation_factors 必须是可验证的公开信号，不得写成交易动作

**免责声明**：本分析仅用于研究辅助与风险提示，不构成任何交易建议或执行指令。"""


RISK_PROMPTS = {
    "aggressive": RISK_PROMPT_AGGRESSIVE,
    "neutral": RISK_PROMPT_NEUTRAL,
    "conservative": RISK_PROMPT_CONSERVATIVE,
}

# 用于检测哪些模板需要更新（包含价格指令的关键词）
RISK_PRICE_KEYWORDS = [
    "风险控制参考价位",
    "收益预期参考价位",
    "止损参考价",
    "第一目标价",
    "第二目标价",
    "止盈",
    "参考价",
]

# pa_advisor_v2 需要更新的关键词（包含操作建议指令）
ADVISOR_ACTION_KEYWORDS = [
    "持有|加仓|减仓|清仓",
    "止损止盈价位",
    "止损参考价",
    "第一目标价",
    "2000-5000字",
    "detailed_analysis",
]


def detect_risk_style(system_prompt: str) -> str:
    if "激进" in system_prompt:
        return "aggressive"
    elif "保守" in system_prompt:
        return "conservative"
    else:
        return "neutral"


def detect_advisor_style(system_prompt: str) -> str:
    if "激进" in system_prompt:
        return "激进"
    elif "保守" in system_prompt:
        return "保守"
    else:
        return "中性"


async def fix_templates():
    from app.core.database import init_database, get_mongo_db, close_database
    await init_database()
    db = get_mongo_db()
    col = db.prompt_templates

    # ── 1. 更新 pa_risk_v2 ──────────────────────────────────
    print("\n🔍 查找 pa_risk_v2 模板 (position_analysis_v2)...")
    risk_docs = await col.find(
        {"agent_name": "pa_risk_v2", "agent_type": "position_analysis_v2"}
    ).to_list(length=None)
    print(f"   找到 {len(risk_docs)} 个模板")

    risk_updated = 0
    for doc in risk_docs:
        sp = doc.get("content", {}).get("system_prompt", "")
        style = detect_risk_style(sp)
        needs_update = any(kw in sp for kw in RISK_PRICE_KEYWORDS)

        if needs_update:
            new_prompt = RISK_PROMPTS[style]
            result = await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"content.system_prompt": new_prompt}},
            )
            print(f"   ✅ 更新 {str(doc['_id'])} (风格: {style}), modified={result.modified_count}")
            risk_updated += 1
        else:
            print(f"   ⏭️  无需更新 {str(doc['_id'])} (风格: {style})")

    print(f"   → 共更新 {risk_updated} 个 pa_risk_v2 模板")

    # ── 2. 更新 pa_advisor_v2 ────────────────────────────────
    print("\n🔍 查找 pa_advisor_v2 模板 (position_analysis_v2)...")
    advisor_docs = await col.find(
        {"agent_name": "pa_advisor_v2", "agent_type": "position_analysis_v2"}
    ).to_list(length=None)
    print(f"   找到 {len(advisor_docs)} 个模板")

    advisor_updated = 0
    for doc in advisor_docs:
        sp = doc.get("content", {}).get("system_prompt", "")
        style = detect_advisor_style(sp)
        needs_update = any(kw in sp for kw in ADVISOR_ACTION_KEYWORDS)

        if needs_update:
            new_prompt = ADVISOR_PROMPT_TEMPLATE.format(style=style)
            result = await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"content.system_prompt": new_prompt}},
            )
            print(f"   ✅ 更新 {str(doc['_id'])} (风格: {style}), modified={result.modified_count}")
            advisor_updated += 1
        else:
            print(f"   ⏭️  无需更新 {str(doc['_id'])} (风格: {style})")

    print(f"   → 共更新 {advisor_updated} 个 pa_advisor_v2 模板")
    print("\n✅ 修复完成")
    await close_database()


if __name__ == "__main__":
    asyncio.run(fix_templates())
