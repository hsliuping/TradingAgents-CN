"""
结论快照（M5.1）：按股票沉淀结构化结论，供下期分析作对比基线

记忆是研究资产不是 agent 私产——分析完成后从 trader/整合层输出提取
「判断/依据/假设/失效条件」四层快照（与研究日志四态、决策闭环备忘录同构），
按 user_id + ticker 多条存档（取最新一期），替代 per-agent 向量记忆的读注入。

- 快速档（memory_mode=off）不写；缓存命中路径不调用 report_saver，天然不写快照
- 提取规则：优先解析「结论快照」章节（core/workflow/depth_profiles.py
  build_snapshot_requirements 指令文案与本模块解析严格对应）；无章节时启发式
  兜底（judgment 取推荐结论、evidence 取关键要点，缺的层如实留空，不编造）

设计文档：docs/05-design/v4.0/analysis-depth-profiles-refactor.md §3.3
实施文档：docs/05-design/v4.0/analysis-depth-profiles-implementation.md M5
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# 主库集合（业务数据入主库 settings.MONGO_DB，与 analysis_reports 同库）
CONCLUSION_SNAPSHOT_COLLECTION = "analysis_conclusion_snapshots"

# 报告文本中「结论快照」章节的字段行（与 core/workflow/depth_profiles.py 指令文案一致）
_FIELD_KEYS = ("判断", "依据", "假设", "失效条件")
_FIELD_LINE_RE = re.compile(r"^\s*[-*•]?\s*(判断|依据|假设|失效条件)\s*[:：]\s*(.*)$")
# 章节标题行（# 标题 / 【标题】），解析到快照字段后遇到新标题即结束
_HEADING_RE = re.compile(r"^\s*(#{1,6}\s|【)")
_JUDGMENT_SEP_RE = re.compile(r"[｜|]")
_CONFIDENCE_RE = re.compile(r"置信\s*[:：]?\s*([0-9.]+\s*%?|高|中|低)")

# 快照来源报告字段优先级（trader/整合层输出为准）
_SNAPSHOT_SOURCE_PRIORITY = (
    "final_trade_decision",
    "trader_investment_plan",
    "research_team_decision",
    "investment_plan",
)


def _split_items(text: str) -> List[str]:
    """「；」/「;」分隔的条目文本 → 列表（去空，不编造）。"""
    return [item.strip() for item in re.split(r"[；;]", text or "") if item.strip()]


def _parse_judgment(text: str, confidence: Any = None) -> Dict[str, Any]:
    """判断行解析：<方向>｜<评级>｜置信 <值>；格式不符时只留原文（不编造）。"""
    judgment: Dict[str, Any] = {"text": text.strip(), "direction": "", "rating": "", "confidence": confidence}
    parts = [p.strip() for p in _JUDGMENT_SEP_RE.split(text) if p.strip()]
    if parts:
        judgment["direction"] = parts[0]
    if len(parts) >= 2:
        judgment["rating"] = parts[1]
    conf_match = _CONFIDENCE_RE.search(text)
    if conf_match:
        judgment["confidence"] = conf_match.group(1).replace(" ", "")
    return judgment


def _extract_section_fields(text: str) -> Optional[Dict[str, Any]]:
    """从报告文本中解析「结论快照」章节四层结构；无章节返回 None。"""
    lines = str(text or "").splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if "结论快照" in line and _HEADING_RE.match(line):
            header_idx = idx
            break
    if header_idx is None:
        return None

    fields: Dict[str, List[str]] = {"判断": [], "依据": [], "假设": [], "失效条件": []}
    current_field: Optional[str] = None
    found_any = False
    for line in lines[header_idx + 1:]:
        if _HEADING_RE.match(line) and current_field is not None:
            break  # 进入下一章节
        match = _FIELD_LINE_RE.match(line)
        if match:
            current_field = match.group(1)
            value = match.group(2).strip()
            if value:
                fields[current_field].append(value)
                found_any = True
            continue
        if current_field and line.strip():
            fields[current_field].append(line.strip())
            found_any = True
    if not found_any:
        return None

    judgment_text = "；".join(fields["判断"]) or ""
    return {
        "judgment": _parse_judgment(judgment_text) if judgment_text else {"text": "", "direction": "", "rating": "", "confidence": None},
        "evidence": _split_items("；".join(fields["依据"])),
        "assumptions": _split_items("；".join(fields["假设"])),
        "invalidations": _split_items("；".join(fields["失效条件"])),
        "extract_source": "section",
    }


def extract_conclusion_snapshot(
    reports: Dict[str, Any],
    decision: Dict[str, Any] = None,
    recommendation: str = "",
    confidence_score: Any = None,
    key_points: list = None,
) -> Dict[str, Any]:
    """从分析输出提取结论快照（判断/依据/假设/失效条件）。

    优先解析「结论快照」章节；无章节时启发式兜底，缺失的层如实留空（宁缺勿造）。
    """
    # 1. 章节解析（trader/整合层输出优先）
    ordered_texts: List[str] = []
    for key in _SNAPSHOT_SOURCE_PRIORITY:
        value = (reports or {}).get(key)
        if isinstance(value, str) and value.strip():
            ordered_texts.append(value)
    for key, value in (reports or {}).items():
        if key not in _SNAPSHOT_SOURCE_PRIORITY and isinstance(value, str) and value.strip():
            ordered_texts.append(value)

    for text in ordered_texts:
        snapshot = _extract_section_fields(text)
        if snapshot:
            return snapshot

    # 2. 启发式兜底：判断取推荐结论/决策观点，依据取关键要点，假设/失效条件留空
    decision = decision or {}
    judgment_text = str(recommendation or "").strip()
    if not judgment_text:
        judgment_text = str(
            decision.get("analysis_view") or decision.get("action") or decision.get("reasoning") or ""
        ).strip()
    if not judgment_text:
        judgment_text = "暂无读数：输出未含结论快照章节"
    return {
        "judgment": _parse_judgment(judgment_text, confidence_score),
        "evidence": [str(p).strip() for p in (key_points or []) if str(p).strip()],
        "assumptions": [],
        "invalidations": [],
        "extract_source": "heuristic",
    }


async def save_conclusion_snapshot(
    db,
    user_id: Optional[str],
    ticker: str,
    stock_name: str,
    snapshot: Dict[str, Any],
    data_as_of: str,
    depth: str,
    run_id: str,
    analysis_date: Optional[str] = None,
) -> None:
    """落一条结论快照（同集合多条存档，取最新一期；不覆盖历史）。"""
    judgment = snapshot.get("judgment") or {}
    if not isinstance(judgment, dict):
        judgment = {"text": str(judgment), "direction": "", "rating": "", "confidence": None}
    document = {
        "user_id": str(user_id) if user_id else "",
        "ticker": ticker,
        "stock_name": stock_name,
        "snapshot_date": analysis_date or data_as_of,
        "run_id": run_id,
        "depth": depth,
        "data_as_of": data_as_of,
        "judgment": judgment,
        "evidence": list(snapshot.get("evidence") or []),
        "assumptions": list(snapshot.get("assumptions") or []),
        "invalidations": list(snapshot.get("invalidations") or []),
        "extract_source": snapshot.get("extract_source", ""),
        "created_at": now_tz(),
    }
    await db[CONCLUSION_SNAPSHOT_COLLECTION].insert_one(document)
    logger.info(
        f"🕰️ 结论快照已保存: ticker={ticker} depth={depth} run_id={run_id} "
        f"source={document['extract_source']}"
    )


async def load_latest_conclusion_snapshot(
    db, user_id: Optional[str], ticker: str
) -> Optional[Dict[str, Any]]:
    """取该 user_id + ticker 的最新一期结论快照（无则返回 None，首期分析）。"""
    return await db[CONCLUSION_SNAPSHOT_COLLECTION].find_one(
        {"user_id": str(user_id) if user_id else "", "ticker": ticker},
        sort=[("created_at", -1)],
    )
