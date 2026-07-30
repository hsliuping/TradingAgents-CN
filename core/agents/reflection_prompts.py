"""
反射模式 prompt 模板集中管理。

基于旧 tradingagents/graph/reflection.py 的 4 维度框架（Reasoning/Improvement/Summary/Query）改造，
去掉"事后收益"依赖，改为"结论 vs 走势"维度。

三个场景：
- TRADE_REFLECTION：复盘完成后（项2）
- ANALYSIS_REFLECTION：研究员报告生成后（项3）
- DEBATE_REFLECTION：辩论结束后（项8）

所有 prompt 要求输出严格 JSON，便于程序解析和 mem0 结构化存储。
"""

from typing import Any, Dict, List, Optional


# ============================================================
# System Prompts
# ============================================================

TRADE_REFLECTION_SYSTEM_PROMPT = """你是交易反思专家。基于以下复盘结论，提炼可复用的结构化经验。

## 输出格式（严格 JSON）
{
  "reasoning": "本次交易的核心逻辑是什么？哪些判断被市场验证了？哪些被证伪了？（50-150字）",
  "improvement": "哪些判断错了？下次遇到类似情境应该怎么改进？（50-150字）",
  "summary": "一句话总结这次交易的核心教训（20-50字）",
  "query": "可用于向量检索的关键词，逗号分隔（10-20字）"
}

## 要求
1. 只输出 JSON，不要其他内容（不要 ```json 标记，不要解释）
2. 基于复盘结论提炼，不要编造未给出的信息
3. 教训应该可复用，不要只针对单次交易的细节
4. 如果复盘结论信息不足，reasoning/improvement 可填"信息不足，无法深度反思"
"""

ANALYSIS_REFLECTION_SYSTEM_PROMPT = """你是投研反思专家。基于以下分析报告，提炼可复用的结构化教训。

## 输出格式（严格 JSON）
{
  "reasoning": "本次分析的核心观点是什么？依据是什么？（50-150字）",
  "improvement": "分析中可能遗漏了哪些维度？下次应该补充什么？（50-150字）",
  "summary": "一句话总结本次分析的核心教训（20-50字）",
  "query": "可用于向量检索的关键词，逗号分隔（10-20字）"
}

## 要求
1. 只输出 JSON，不要其他内容（不要 ```json 标记，不要解释）
2. 基于报告内容提炼，不要编造未给出的信息
3. 教训应该面向"下次同股票或同行业分析"可复用
4. 如果报告信息不足，reasoning/improvement 可填"信息不足，无法深度反思"
"""

DEBATE_REFLECTION_SYSTEM_PROMPT = """你是辩论反思专家。基于以下辩论历史和最终裁决，提炼辩论中的新观点和教训。

## 输出格式（严格 JSON）
{
  "reasoning": "辩论中提出了哪些有价值的新观点？哪些观点被最终裁决采纳？（50-150字）",
  "improvement": "哪些观点被忽略了？辩论是否充分？下次类似辩论应该补充什么？（50-150字）",
  "summary": "一句话总结本次辩论的核心教训（20-50字）",
  "query": "可用于向量检索的关键词，逗号分隔（10-20字）"
}

## 要求
1. 只输出 JSON，不要其他内容（不要 ```json 标记，不要解释）
2. 基于辩论历史和裁决提炼，不要编造未给出的信息
3. 教训应该面向"下次同股票或同行业辩论"可复用
4. 如果辩论信息不足，reasoning/improvement 可填"信息不足，无法深度反思"
"""


# ============================================================
# User Prompt 构建器
# ============================================================

def build_trade_reflection_user_prompt(
    trade_info: Any,
    ai_review: Any,
) -> str:
    """构建复盘反思的 user prompt。

    Args:
        trade_info: 交易信息对象（有 code/name/first_buy_date 等属性）
        ai_review: AI 复盘结论（有 summary/strengths/weaknesses/suggestions/plan_deviation 属性）

    Returns:
        user prompt 文本
    """
    code = getattr(trade_info, "code", "") or ""
    name = getattr(trade_info, "name", "") or ""
    first_buy = getattr(trade_info, "first_buy_date", "") or ""

    summary = (getattr(ai_review, "summary", "") or "").strip()
    strengths = list(getattr(ai_review, "strengths", []) or [])
    weaknesses = list(getattr(ai_review, "weaknesses", []) or [])
    suggestions = list(getattr(ai_review, "suggestions", []) or [])
    plan_deviation = (getattr(ai_review, "plan_deviation", "") or "").strip()

    parts = [f"## 交易标的：{name}({code})，首次买入：{first_buy}"]
    if summary:
        parts.append(f"### 复盘总结\n{summary}")
    if strengths:
        parts.append("### 做得好的方面\n" + "\n".join(f"- {s}" for s in strengths[:5] if s))
    if weaknesses:
        parts.append("### 不足之处\n" + "\n".join(f"- {w}" for w in weaknesses[:5] if w))
    if plan_deviation:
        parts.append(f"### 计划偏差\n{plan_deviation[:500]}")
    if suggestions:
        parts.append("### 改进建议\n" + "\n".join(f"- {s}" for s in suggestions[:5] if s))

    return "\n\n".join(parts)


def build_analysis_reflection_user_prompt(
    ticker: str,
    report: Any,
    analysis_date: str = "",
) -> str:
    """构建研究员报告反思的 user prompt。

    Args:
        ticker: 股票代码
        report: 研究报告（字典或字符串）
        analysis_date: 分析日期

    Returns:
        user prompt 文本
    """
    # 提取报告内容
    if isinstance(report, dict):
        content = report.get("content", "") or report.get("report", "") or str(report)
        stance = report.get("stance", "")
    else:
        content = str(report)
        stance = ""

    # 截断过长内容（避免 token 浪费）
    max_chars = 2000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n...(内容已截断)"

    parts = [f"## 股票：{ticker}，分析日期：{analysis_date or '未知'}"]
    if stance:
        stance_label = {"bull": "乐观", "bear": "审慎", "risky": "高弹性", "safe": "防御", "neutral": "基准情景"}.get(stance, stance)
        parts.append(f"### 研究立场：{stance_label}")
    parts.append(f"### 分析报告\n{content}")

    return "\n\n".join(parts)


def build_debate_reflection_user_prompt(
    ticker: str,
    debate_history: str,
    conclusion: str,
    debate_type: str = "",
) -> str:
    """构建多情景研究反思的 user prompt。

    Args:
        ticker: 股票代码
        debate_history: 多情景研究历史文本
        conclusion: 最终裁决/结论
        debate_type: 多情景研究类型（investment_debate / risk_debate）

    Returns:
        user prompt 文本
    """
    # 截断过多情景研究历史
    max_chars = 3000
    if len(debate_history) > max_chars:
        debate_history = debate_history[:max_chars] + "\n...(多情景研究历史已截断)"

    if len(conclusion) > max_chars:
        conclusion = conclusion[:max_chars] + "\n...(结论已截断)"

    debate_label = {
        "investment_debate_state": "多情景研究",
        "risk_debate_state": "风险多情景研究",
    }.get(debate_type, debate_type or "多情景研究")

    parts = [
        f"## 股票：{ticker}",
        f"### 多情景研究类型：{debate_label}",
        f"### 多情景研究历史\n{debate_history}",
        f"### 最终裁决\n{conclusion}",
    ]

    return "\n\n".join(parts)
