"""估值测算规格生成层（A10-D1 件①）

三层架构中的规格生成层：LLM（Seed-Evolving）从研究报告包提取判断，
输出模型规格 JSON；历史数据、现价、总股本由管道注入（真实数据锚点，
模型只生成判断类字段——预测假设与估值情景），压缩幻觉面。

校验失败自动反馈重试（对齐 Skill 生成管线的迭代修复叙事）。
确定性层见 valuation_excel.py。
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from core.llm.models import Message

from .valuation_excel import (
    ValuationSpecError,
    render_valuation_excel,
    validate_spec,
    validate_valuation_excel,
)

logger = logging.getLogger(__name__)

# ==================== 提示词 ====================

SPEC_SYSTEM_PROMPT = """你是一位严谨的估值建模分析师。你的任务：基于研究报告结论与结构化财务数据，产出估值测算表的模型规格（JSON）。

分工边界（最高优先级）：
- 历史财务数据、现价、总股本由系统注入，你不得编造、改动或输出这些字段
- 你只输出判断类字段：未来 2 年预测假设、估值情景与风险提示

输出要求：
- 只输出一个 JSON 对象，无 markdown 围栏、无解释文字
- JSON 只含两个字段：earnings_forecast、valuation

字段规范：
1. earnings_forecast.assumptions：未来 2 年预测数组，每项：
   - period：年份+E，如 "2026E"、"2027E"（与预测起点衔接）
   - revenue_growth：营收同比增速，小数（0.25 表示 25%）；必须 > -1 且不为 0
   - net_margin：净利率，小数；必须在 (0, 1] 区间且不为 0
   - rationale：50 字内依据，必须引用研究材料中的具体论据，不得编造材料外数据
2. valuation.scenarios：至少 3 个情景（悲观/中性/乐观），每项：
   - name：情景名
   - method：固定为 "PE"
   - multiple：PE 倍数，必须为正
   - eps_period：EPS 基准期间，必须是给定历史期间或你的预测期间之一
   - benchmark_basis：比较基准（同业区间、历史分位等，须可说明来源）
   - applicability_check：{"passed": true, "notes": ["归母净利润为正"]}（PE 要求基准期净利润为正）
3. valuation.risk_notes：3-5 条风险提示

方法适用性（必须自查）：
- 预测期净利润 = 上一期营收 × (1 + 增速) × 净利率（营收逐期滚动）
- PE 的 eps_period 若落在亏损期，必须换用盈利期

数值纪律：
- 假设方向须与研究结论一致（中性结论不应给极端假设）
- 倍数须有基准可依，不得凭空给数"""

# 材料 truncation 上限（字符）
_MAX_PLAN = 2500
_MAX_FUNDAMENTALS = 2500
_MAX_RESEARCHER = 1500


def _truncate(text: Any, limit: int) -> str:
    s = str(text or "").strip()
    return s if len(s) <= limit else s[:limit] + "…（后文截断）"


def build_spec_user_prompt(bundle: Dict[str, Any]) -> str:
    """组装规格生成用户提示词（结构化数据 + 研究材料）"""
    hist_rows = "\n".join(
        f"  | {h['period']} | {h['revenue']:.1f} | {h['net_profit']:.2f} |"
        for h in bundle["financial_history"]
    )
    last_period = bundle["financial_history"][-1]["period"]

    return f"""【股票】{bundle['stock_name']}（{bundle['ticker']}）　分析日期：{bundle.get('analysis_date', '')}

【结构化数据（系统注入，真实值，禁止改动）】
- 现价：{bundle['current_price']} 元
- 总股本：{bundle['share_count']} 亿股
- 财务历史（单位：亿元）：
  | 期间 | 营收 | 归母净利润 |
{hist_rows}
- 预测期净利润计算链：{last_period}营收 × (1+增速) × 净利率，逐期滚动

【综合研究结论】
{_truncate(bundle.get('investment_plan'), _MAX_PLAN)}

【基本面分析要点】
{_truncate(bundle.get('fundamentals_report'), _MAX_FUNDAMENTALS)}

【乐观研究员要点】
{_truncate(bundle.get('bull_report'), _MAX_RESEARCHER)}

【审慎研究员要点】
{_truncate(bundle.get('bear_report'), _MAX_RESEARCHER)}

请输出模型规格 JSON（只含 earnings_forecast 与 valuation 两个字段，无围栏无解释）。"""


# ==================== 解析与合并 ====================

def extract_json_block(text: str) -> Optional[dict]:
    """从模型输出提取 JSON（兼容围栏、前后杂文本）"""
    if not text or not text.strip():
        return None
    candidates: List[str] = []
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        candidates.append(text[s:e + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def merge_spec(model_output: Dict[str, Any], bundle: Dict[str, Any]) -> Dict[str, Any]:
    """合并模型输出与注入数据：真实数据字段一律以 bundle 为准"""
    ef = model_output.get("earnings_forecast") or {}
    val = model_output.get("valuation") or {}
    return {
        "ticker": bundle["ticker"],
        "stock_name": bundle["stock_name"],
        "analysis_date": bundle.get("analysis_date", ""),
        "share_count": bundle["share_count"],
        "current_price": bundle["current_price"],
        "earnings_forecast": {
            "history": bundle["financial_history"],
            "assumptions": ef.get("assumptions") or [],
        },
        "valuation": val,
    }


# ==================== 生成（含反馈重试） ====================

def generate_valuation_spec(
    bundle: Dict[str, Any],
    llm: Any,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """调用 LLM 生成模型规格，校验失败自动反馈重试

    Args:
        bundle: 报告包（financial_history/current_price/share_count 为注入的真实数据；
                investment_plan/fundamentals_report/bull_report/bear_report 为研究材料）
        llm: 具有 .chat(messages) -> response(.content) 的客户端（UnifiedLLMClient）
        max_attempts: 最大尝试次数

    Returns:
        {passed, spec, attempts, errors, elapsed}
    """
    t0 = time.time()
    messages: List[Message] = [
        Message(role="system", content=SPEC_SYSTEM_PROMPT),
        Message(role="user", content=build_spec_user_prompt(bundle)),
    ]
    last_errors = ["未调用 LLM"]

    for attempt in range(1, max_attempts + 1):
        resp = llm.chat(messages)
        text = getattr(resp, "content", None)
        if text is None:
            text = resp if isinstance(resp, str) else ""
        parsed = extract_json_block(text)
        if parsed is None:
            last_errors = ["输出无法解析为 JSON（可能含围栏外文本或格式错误）"]
        else:
            spec = merge_spec(parsed, bundle)
            last_errors = validate_spec(spec)
            if not last_errors:
                logger.info(f"[ValuationSpec] 规格生成成功（第 {attempt} 次尝试）")
                return {"passed": True, "spec": spec, "attempts": attempt,
                        "errors": [], "elapsed": time.time() - t0}
        logger.warning(f"[ValuationSpec] 第 {attempt} 次尝试失败: {last_errors}")

        # 反馈重试：把错误回传给模型修正
        messages.append(Message(role="assistant", content=str(text)[:4000]))
        messages.append(Message(
            role="user",
            content="上次输出存在以下问题：\n- " + "\n- ".join(last_errors)
                    + "\n请修正后重新输出完整 JSON（只含 earnings_forecast 与 valuation，无围栏无解释）。",
        ))

    return {"passed": False, "spec": None, "attempts": max_attempts,
            "errors": last_errors, "elapsed": time.time() - t0}


# ==================== 端到端入口 ====================

def generate_valuation_deliverable(
    bundle: Dict[str, Any],
    llm: Any,
    output_path: str = "",
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """端到端：报告包 → LLM 规格生成 → 渲染 xlsx → 文件校验

    供智能助手层按声明式交付物调度（demo 环节 5 链路）。
    """
    spec_result = generate_valuation_spec(bundle, llm, max_attempts=max_attempts)
    if not spec_result["passed"]:
        return {"success": False, "stage": "spec_generation",
                "attempts": spec_result["attempts"], "errors": spec_result["errors"]}

    spec = spec_result["spec"]
    if not output_path:
        from datetime import datetime
        from pathlib import Path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(Path("data") / "deliverables"
                          / f"valuation_{spec['ticker']}_{ts}.xlsx")

    try:
        path = render_valuation_excel(spec, output_path)
    except ValuationSpecError as e:  # 已过 validate_spec，理论不可达，防御性兜底
        return {"success": False, "stage": "render", "error": str(e)}

    report = validate_valuation_excel(spec, path)
    return {
        "success": report["passed"],
        "stage": "file_validation",
        "attempts": spec_result["attempts"],
        "spec": spec,
        "validation": report,
        "path": path,
    }
