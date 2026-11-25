"""合规输出工具。

统一收口分析结果中的交易建议型字段，保留研究辅助所需的摘要、风险因素和公开信息观察。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


SAFE_REPORT_KEYS = (
    "index_report",
    "sector_report",
    "market_report",
    "fundamentals_report",
    "sentiment_report",
    "news_report",
)

GENERIC_RESEARCH_RECOMMENDATION = "请参考详细研究报告，重点关注基本面变化、市场环境与风险因素。"
GENERIC_POSITION_RECOMMENDATION = "该持仓研究仅提供研究观察与风险提示，请结合自身策略独立判断。"
GENERIC_REVIEW_SUMMARY = "本次复盘仅保留复盘结论、纪律问题与研究改进方向，不提供未来交易动作建议。"
GENERIC_REVIEW_IMPROVEMENTS = (
    "完善交易前证据核验与记录，避免临盘依据不足。",
    "将交易计划触发条件整理为可验证清单，提升执行一致性。",
    "复盘时重点检查纪律执行、风险暴露与研究盲区。",
)

_ACTIONABLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"买入|卖出|持有|加仓|减仓|清仓|建仓|平仓|调仓",
        r"止损|止盈|仓位|目标价|目标价格|目标区间|价格分析区间|参考价格",
        r"目标位|目标点位|支撑位|阻力位|压力位|配置建议|防御性配置|进攻性配置|安全边际|板块机会",
        r"投资建议|交易建议|操作建议|一键模拟下单|下单|模拟交易",
        r"BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL",
        r"target_price|stop_loss|take_profit|position_ratio|suggested_quantity|suggested_amount",
    )
]
_REVIEW_EXECUTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(建议|可以|可考虑|应当|应该|需要|宜|不宜).{0,12}(买入|卖出|继续持有|持有|加仓|减仓|补仓|清仓|建仓|平仓|调仓)",
        r"(下次|后续|未来).{0,16}(买入|卖出|继续持有|持有|加仓|减仓|补仓|清仓|建仓|平仓|调仓|止损|止盈)",
        r"继续持有|逢低买入|逢高卖出|分批买入|分批卖出",
        r"止损价|止盈价|目标价|目标价格|目标区间|参考价|参考价格",
        r"(跌破|突破|回调到|反弹到|跌到|涨到|回到).{0,12}(买入|卖出|加仓|减仓|止损|止盈)",
        r"仓位.{0,8}(\d+%|百分之|\d+成|控制在|提升到|降到|上调到|下调到)",
        r"\b(BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL)\b",
        r"一键模拟下单|下单|模拟交易",
    )
]
_POSITION_TRIGGER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:技术面|基本面|风险|综合)?评分\s*[:：]?\s*\d+(?:\.\d+)?\s*分",
        r"连续.{0,8}(?:日|天|周).{0,10}(站稳|收盘站稳|放量|缩量|突破|跌破)",
        r"右侧介入|左侧介入|介入依据|入场依据|退出依据|交易触发|反弹动能",
        r"\bMA\d+\b|\bRSI\d*\b|\bMACD\b|\bKDJ\b|布林(?:中轨|上轨|下轨)?",
        r"支撑带|支撑位|阻力位|压力位|放量|缩量|站稳|突破|跌破",
    )
]
_POSITION_LABEL_ONLY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^(研究结论|核心依据|研究判断|风险提示|观察重点|补充视角|研究观察|风险评估|催化与改善条件)$",
    )
]
_POSITION_PLAIN_LANGUAGE_REPLACEMENTS = (
    ("技术面高度安全", "短期走势没有明显转弱"),
    ("中性偏强状态", "当前状态偏稳，但还需要继续验证"),
    ("技术结构临界守稳", "短期没有继续恶化"),
    ("基本面坚实但估值结构分化", "公司经营基础尚可，但市场对估值修复仍有分歧"),
    ("中性观察阶段", "暂时只能继续观察"),
    ("价格紧贴中期支撑", "股价目前仍在阶段性低位附近"),
    ("尚未出现趋势反转信号", "还没有看到明确修复信号"),
    ("亦未触发系统性恶化条件", "也没有出现明确恶化证据"),
    ("成本价显著高于现价", "当前价格仍明显低于持仓成本"),
    ("成本价深埋于所有关键均线之下", "当前价格明显高于持仓成本"),
    ("财务指标稳健，盈利质量优异", "经营和财务表现整体稳定"),
    ("经营现金流持续高倍覆盖净利润", "现金流表现较稳"),
    ("财务安全边际坚实", "财务缓冲仍然较稳"),
    ("成长逻辑待验证", "后续增长是否延续仍待验证"),
    ("ROE阶段性回落", "盈利效率阶段性回落"),
    ("毛利率数据缺失", "利润率数据还不完整"),
    ("高PB估值", "当前估值水平"),
    ("壁垒溢价", "竞争优势溢价"),
    ("增长溢价", "增长预期溢价"),
    ("估值中枢抬升", "市场愿意给出更高估值"),
    ("第二曲线", "新业务增长"),
    ("客户定点公告", "新增客户和项目进展公告"),
    ("议价能力", "定价能力"),
    ("修复需时间与多重条件配合", "后续修复通常需要时间，也需要多方面条件一起改善"),
)
_POSITION_GENERIC_ITEM_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"当前判断主要基于已披露经营信息与风险信号整理",
        r"当前结论主要基于已披露信息",
        r"请重点关注",
        r"请持续跟踪",
        r"后续重点观察",
    )
]
_POSITION_APPENDIX_SECTION_ORDER = (
    ("technical_analysis", "技术面分析"),
    ("fundamental_analysis", "基本面分析"),
    ("risk_analysis", "风险评估"),
)
_POSITION_APPENDIX_TITLE_TO_KEY = {
    title: key for key, title in _POSITION_APPENDIX_SECTION_ORDER
}
_POSITION_APPENDIX_HEADING_PATTERN = re.compile(r"^【(技术面分析|基本面分析|风险评估)】$")
_JSON_FIELD_PATTERN = re.compile(r'^[\[\]{}":,0-9._%\-\s]+$')
_SENTENCE_SPLIT_PATTERN = re.compile(r"[\n。！？；]+")
_LOW_SIGNAL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^股票基本信息$",
        r"^公司名称[:：]",
        r"^股票代码[:：]",
        r"^所属市场[:：]",
        r"^当前价格[:：]",
        r"^涨跌幅[:：]",
        r"^分析日期[:：]",
        r"^数据来源[:：]",
        r"^基本信息[:：]",
        r"^财务数据[:：]$",
        r"^一、公司概况$",
        r"^二、财务数据分析$",
        r"^三、",
        r"^四、",
        r"分析报告",
    )
]
_DISPLAY_REPORT_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"目标价|目标价格|价格区间|关键价位|关键价格|关键验证位|观察区间|参考价|参考价格|风险控制参考",
        r"支撑位|阻力位|突破|跌破|站稳|失守|止损|止盈|仓位|风险敞口|持仓周期",
        r"上涨空间|下跌空间|上行空间|下行空间|收益空间|收益预期|最大收益|潜在收益|回撤|最大可能损失",
        r"风险收益比|期望收益|安全边际|配置价值|逆向投资机会|买入信号|卖出信号|入场|退出条件|操作策略",
        r"增持观点|减持观点|建仓|平仓|调仓|重仓|轻仓|分批买入|分批卖出|看涨价位|看跌价位",
        r"(?:¥|￥|\$)\s*\d|\d+(?:\.\d+)?\s*(?:元|美元|港元)",
    )
]
_INFERENTIAL_EVIDENCE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"推断|推测|推定|估算|测算|估计|假设|假定|猜测|臆测|疑似",
        r"可能|或将|有望|预计|倾向于|大概率|或许|或可",
        r"待验证|需验证|尚待验证|仍待验证|不可验证|难以验证",
    )
]

_DISPLAY_TITLE_REPLACEMENTS = [
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?新闻分析师研究报告$', re.IGNORECASE), '新闻研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?新闻研究报告$', re.IGNORECASE), '新闻研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?社交媒体分析师研究报告$', re.IGNORECASE), '情绪研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?社交分析师研究报告$', re.IGNORECASE), '情绪研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?情绪分析师研究报告$', re.IGNORECASE), '情绪研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?板块分析师研究观察报告$', re.IGNORECASE), '行业板块研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?行业分析师研究观察报告$', re.IGNORECASE), '行业板块研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?行业板块研究观察报告$', re.IGNORECASE), '行业板块研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?大盘分析师研究观察报告$', re.IGNORECASE), '大盘环境研究'),
    (re.compile(r'^(?P<prefix>#{1,6}\s*)?大盘环境研究观察报告$', re.IGNORECASE), '大盘环境研究'),
]

_DISPLAY_PHRASE_REPLACEMENTS = (
    ('买入逻辑', '研究逻辑'),
    ('投资机会', '研究线索'),
    ('配置型投资者', '研究型用户'),
    ('配置价值', '研究跟踪价值'),
    ('安全边际', '风险缓冲'),
    ('具备一定吸引力', '值得继续跟踪'),
    ('价值修复的起点', '估值与预期修复的早期信号'),
)

RESEARCH_ONLY_DISCLAIMER = "本报告仅供研究参考，不构成个股推荐、投资建议或操作依据。请结合公开信息披露与自身研究独立判断。"
_LEGACY_DISCLAIMER_BLOCK_PATTERN = re.compile(
    r"(?is)(?:\*\*)?免责声明(?:\*\*)?[：:]\s*"
    r"(?:本(?:分析)?报告仅供参考，不构成投资建议。.*?独立做出投资决策。"
    r"|请结合自身情况独立判断。投资有风险，决策需谨慎。必要时请咨询专业顾问。)"
)
_LEGACY_DISCLAIMER_LINE_PATTERN = re.compile(
    r"(?is)请结合自身情况独立判断。投资有风险，决策需谨慎。必要时请咨询专业顾问。"
)
_TOOL_CALL_ARTIFACT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^</?tool_call>$",
        r'^\{"name"\s*:\s*"get_[^\"]+".*"arguments"\s*:\s*\{.*\}\s*\}$',
        r'^"name"\s*:\s*"get_[^\"]+"',
        r'^"arguments"\s*:\s*\{',
    )
]
_STABLE_DATA_REQUEST_DATE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"当前尚无分析日[（(](\d{4}-\d{2}-\d{2})[）)]对应的稳定收盘后日频数据",
        r"当前尚无\s*(\d{4}-\d{2}-\d{2})\s*对应的稳定收盘后日频数据",
        r"当前尚无\s*(\d{4}-\d{2}-\d{2})\s*的[^。\n]*稳定收盘后日频数据",
    )
]
_STABLE_DATA_SNAPSHOT_LINE_PATTERN = re.compile(
    r"所有估值指标快照日期统一为\s*(?:\*\*)?(\d{4}-\d{2}-\d{2})(?:\*\*)?[。.]?"
)


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "markdown", "text", "message", "report"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item
        return ""
    return "" if value is None else str(value)


def contains_actionable_content(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _ACTIONABLE_PATTERNS)


def contains_review_execution_guidance(text: str) -> bool:
    if not text:
        return False
    normalized = _plain_text(text)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _REVIEW_EXECUTION_PATTERNS)


def _plain_text(text: Any) -> str:
    if text is None:
        return ""

    if isinstance(text, (list, tuple, set)):
        joined = " ".join(
            fragment
            for item in text
            for fragment in [_plain_text(item)]
            if fragment
        )
        if not joined:
            return ""
        text = joined
    elif isinstance(text, dict):
        text = _as_text(text)
    elif not isinstance(text, str):
        text = str(text)

    normalized = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    normalized = re.sub(r"`+", "", normalized)
    normalized = normalized.replace("#", " ").replace("*", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_display_line(line: str) -> str:
    normalized_line = line

    for pattern, replacement in _DISPLAY_TITLE_REPLACEMENTS:
        match = pattern.match(normalized_line.strip())
        if match:
            prefix = match.groupdict().get('prefix') or ''
            return f"{prefix}{replacement}".rstrip()

    for old_text, new_text in _DISPLAY_PHRASE_REPLACEMENTS:
        normalized_line = normalized_line.replace(old_text, new_text)

    return normalized_line


def _normalize_research_disclaimer(text: str) -> str:
    normalized = _LEGACY_DISCLAIMER_BLOCK_PATTERN.sub(
        f"**免责声明**：{RESEARCH_ONLY_DISCLAIMER}",
        text,
    )
    normalized = _LEGACY_DISCLAIMER_LINE_PATTERN.sub(RESEARCH_ONLY_DISCLAIMER, normalized)
    return normalized


def _strip_tool_call_artifacts(text: str) -> Tuple[str, bool]:
    cleaned_lines: List[str] = []
    removed_any = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        normalized = _plain_text(raw_line)

        if any(pattern.search(stripped) or pattern.search(normalized) for pattern in _TOOL_CALL_ARTIFACT_PATTERNS):
            removed_any = True
            continue

        if stripped.startswith("{") and '"name"' in stripped and '"arguments"' in stripped and '"get_' in stripped:
            removed_any = True
            continue

        cleaned_lines.append(raw_line)

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"```(?:json)?\s*```", "", cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
    return cleaned_text, removed_any


def _normalize_stable_data_snapshot_conflicts(text: str) -> str:
    requested_date = ""
    for pattern in _STABLE_DATA_REQUEST_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            requested_date = match.group(1)
            break

    if not requested_date:
        return text

    def _replace_snapshot_line(match: re.Match[str]) -> str:
        snapshot_date = match.group(1)
        if snapshot_date == requested_date:
            return "所有估值指标快照日期应以工具返回的最近可用交易日为准，当前正文日期口径仍待验证。"
        return match.group(0)

    return _STABLE_DATA_SNAPSHOT_LINE_PATTERN.sub(_replace_snapshot_line, text)


def sanitize_report_artifacts(text: Any) -> str:
    raw_text = _as_text(text)
    if not raw_text:
        return ""

    normalized = _normalize_research_disclaimer(raw_text)
    normalized, _ = _strip_tool_call_artifacts(normalized)
    normalized = _normalize_stable_data_snapshot_conflicts(normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized


def is_low_signal_text(text: str) -> bool:
    normalized = _plain_text(text)
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in _LOW_SIGNAL_PATTERNS):
        return True
    if normalized.startswith("-") and len(normalized) <= 14:
        return True
    return False


def _fragment_score(text: str) -> int:
    normalized = _plain_text(text)
    if not normalized:
        return -1

    score = min(len(normalized), 160)
    if is_low_signal_text(normalized):
        score -= 120
    if any(keyword in normalized for keyword in ("风险", "盈利", "增长", "压力", "竞争", "估值", "资产", "负债", "催化", "行业", "宏观", "需求", "收入", "利润")):
        score += 60
    if normalized.startswith("-"):
        score -= 10
    return score


def sanitize_text_block(text: Any, fallback: str = "") -> str:
    raw_text = sanitize_report_artifacts(text)
    if not raw_text:
        return fallback

    lines: List[str] = []
    for chunk in re.split(r"\r?\n", raw_text):
        line = _plain_text(chunk)
        if not line or len(line) < 6:
            continue
        if _JSON_FIELD_PATTERN.match(line):
            continue
        if contains_actionable_content(line):
            continue
        if is_low_signal_text(line):
            continue
        lines.append(line)

    deduped: List[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)

    if not deduped:
        return fallback
    return "\n".join(deduped[:12])[:2500]


def contains_position_trigger_language(text: str) -> bool:
    if not text:
        return False
    normalized = _plain_text(text)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _POSITION_TRIGGER_PATTERNS)


def _iter_position_review_fragments(text: Any) -> Iterable[str]:
    for fragment in _iter_review_fragments(text):
        yield fragment

    raw_text = _as_text(text)
    if not raw_text:
        return

    for chunk in re.split(r"\r?\n", raw_text):
        normalized = _plain_text(chunk)
        if not normalized:
            continue

        fragments = [
            fragment.strip()
            for fragment in _SENTENCE_SPLIT_PATTERN.split(normalized)
            if fragment.strip()
        ]
        if not fragments:
            fragments = [normalized]

        for fragment in fragments:
            if len(fragment) < 4:
                continue
            if _JSON_FIELD_PATTERN.match(fragment):
                continue
            if is_low_signal_text(fragment):
                continue
            if not contains_review_execution_guidance(fragment):
                continue

            simplified = _simplify_position_user_language(fragment)
            if not simplified or contains_review_execution_guidance(simplified):
                continue
            yield simplified


def sanitize_position_text_block(text: Any, fallback: str = "") -> str:
    deduped: List[str] = []
    for fragment in _iter_position_review_fragments(text):
        if contains_position_trigger_language(fragment):
            continue
        if any(pattern.match(fragment) for pattern in _POSITION_LABEL_ONLY_PATTERNS):
            continue
        if fragment not in deduped:
            deduped.append(fragment)

    if not deduped:
        return fallback
    return "；".join(deduped[:5])[:600]


def _normalize_position_list_items(value: Any, fallback: List[str], limit: int = 3) -> List[str]:
    raw_items: List[str] = []
    if isinstance(value, list):
        for item in value:
            text = _plain_text(item)
            if text:
                raw_items.append(text)
    elif value:
        raw_items.extend(_iter_position_review_fragments(value))

    cleaned_items: List[str] = []
    for item in raw_items:
        for fragment in _iter_position_clauses(item):
            cleaned = _clip_position_user_text(_simplify_position_user_language(fragment), 56)
            if not cleaned or contains_position_trigger_language(cleaned):
                continue
            if _is_low_signal_position_item(cleaned) or _looks_truncated_position_text(cleaned):
                continue
            if cleaned not in cleaned_items:
                cleaned_items.append(cleaned)
            if len(cleaned_items) >= limit:
                break
        if len(cleaned_items) >= limit:
            break

    if cleaned_items:
        return cleaned_items
    return fallback[:limit]


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(number)


def _extract_position_snapshot(result_data: Dict[str, Any], position_snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if isinstance(position_snapshot, dict) and position_snapshot:
        return position_snapshot
    summary = result_data.get("summary")
    if isinstance(summary, dict):
        return summary
    return {}


def _simplify_position_user_language(text: str) -> str:
    normalized = _plain_text(text)
    if not normalized:
        return ""

    for old, new in _POSITION_PLAIN_LANGUAGE_REPLACEMENTS:
        normalized = normalized.replace(old, new)

    normalized = re.sub(
        r"短期未达目标(?:也)?未触(?:及)?止损",
        "短期表现未达到预期，但当前还没出现进一步恶化信号",
        normalized,
    )
    normalized = re.sub(r"未达目标", "表现未达到预期", normalized)
    normalized = re.sub(r"未触(?:及)?止损", "还没出现进一步恶化信号", normalized)

    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("现阶段短期没有继续恶化、", "现阶段更合适的结论是继续观察：短期没有继续恶化，")
    normalized = normalized.replace("仍有分歧的暂时只能继续观察", "仍有分歧，目前暂时只能继续观察")
    normalized = normalized.replace("；价格", "；股价")
    normalized = normalized.replace("当前持仓处于", "现阶段")
    normalized = normalized.replace("；-", "；")
    normalized = normalized.replace("- ", "")
    return normalized.strip(" ；，。")


def _iter_position_clauses(text: Any) -> Iterable[str]:
    normalized = _plain_text(text)
    if not normalized:
        return

    for sentence in re.split(r"[。！？；]+", normalized):
        sentence = sentence.strip(" ；，。")
        if not sentence:
            continue

        comma_fragments = [
            fragment.strip(" ；，。")
            for fragment in re.split(r"[，、]+", sentence)
            if fragment.strip(" ；，。")
        ]
        if len(comma_fragments) >= 2:
            for fragment in comma_fragments:
                if len(fragment) >= 6:
                    yield fragment
            continue

        yield sentence


def _clip_position_user_text(text: str, max_len: int) -> str:
    normalized = _plain_text(text).strip(" ；，。:-")
    if not normalized:
        return ""
    if len(normalized) <= max_len:
        return normalized

    window = normalized[: max_len + 1]
    cut_at = max(window.rfind(marker) for marker in ("；", "。", "，", "、", "：", " "))
    if cut_at >= max(10, max_len // 2):
        clipped = window[:cut_at]
    else:
        clipped = window[:max_len]

    clipped = re.sub(r"(?:将|让|获|并|但|且|及|与|或|则|需|待|可)+$", "", clipped)
    return clipped.strip(" ；，。:-")


def _looks_truncated_position_text(text: str) -> bool:
    normalized = _plain_text(text).strip()
    if len(normalized) < 12:
        return False
    if re.search(r"[；，,:：\-/]$", normalized):
        return True
    return bool(re.search(r"(?:将|让|获|并|但|且|及|与|或|则|需|待|可)$", normalized))


def _is_low_signal_position_item(text: str) -> bool:
    normalized = _plain_text(text)
    return any(pattern.search(normalized) for pattern in _POSITION_GENERIC_ITEM_PATTERNS)


def _build_position_candidate_items(*sources: Any, limit: int = 3, max_len: int = 40) -> List[str]:
    items: List[str] = []
    for source in sources:
        for fragment in _iter_position_clauses(source):
            cleaned = _clip_position_user_text(_simplify_position_user_language(fragment), max_len)
            if len(cleaned) < 6:
                continue
            if contains_position_trigger_language(cleaned):
                continue
            if _is_low_signal_position_item(cleaned) or _looks_truncated_position_text(cleaned):
                continue
            if cleaned not in items:
                items.append(cleaned)
            if len(items) >= limit:
                return items
    return items


def _build_position_conclusion(*sources: Any) -> str:
    for source in sources:
        normalized = _clip_position_user_text(_simplify_position_user_language(source), 72)
        if normalized and not _looks_truncated_position_text(normalized) and (
            "继续观察" in normalized
            or "表现未达到预期" in normalized
            or "进一步恶化信号" in normalized
        ):
            return normalized

    clauses = _build_position_candidate_items(*sources, limit=2, max_len=32)
    if clauses:
        return _clip_position_user_text("；".join(clauses), 72)
    return "现阶段更适合继续观察，重点确认原始研究逻辑是否仍然成立"


def _build_position_user_action_reason(
    result_data: Dict[str, Any],
    position_snapshot: Dict[str, Any] | None = None,
) -> tuple[str, str, Dict[str, Any]]:
    snapshot = _extract_position_snapshot(result_data, position_snapshot)
    raw_user_view = result_data.get("user_view") if isinstance(result_data.get("user_view"), dict) else {}
    analysis_summary = result_data.get("analysis_summary") if isinstance(result_data.get("analysis_summary"), dict) else {}
    neutral_advice = result_data.get("neutral_operation_advice") if isinstance(result_data.get("neutral_operation_advice"), dict) else {}
    if not neutral_advice and isinstance(result_data.get("neutral_operation_suggestion"), dict):
        neutral_advice = result_data.get("neutral_operation_suggestion")
    specific_plan = result_data.get("specific_plan") if isinstance(result_data.get("specific_plan"), dict) else {}
    cleaned_observation = _simplify_position_user_language(
        sanitize_position_text_block(
            raw_user_view.get("conclusion") or result_data.get("action_reason"),
            fallback="",
        )
    )
    cleaned_risk = sanitize_text_block(result_data.get("risk_assessment"), fallback="")
    cleaned_opportunity = sanitize_text_block(result_data.get("opportunity_assessment"), fallback="")

    current_price = _coerce_float(snapshot.get("current_price"))
    cost_price = _coerce_float(snapshot.get("cost_price"))
    unrealized_pnl_pct = _coerce_float(snapshot.get("unrealized_pnl_pct"))
    holding_days = _coerce_int(snapshot.get("holding_days"))

    snapshot_context_parts: List[str] = []
    if unrealized_pnl_pct is not None:
        abs_loss = abs(unrealized_pnl_pct)
        if unrealized_pnl_pct <= -30:
            snapshot_context_parts.append(f"当前这笔持仓浮亏约{abs_loss:.2f}%，已经处于较深浮亏区间。")
        elif unrealized_pnl_pct <= -15:
            snapshot_context_parts.append(f"当前这笔持仓浮亏约{abs_loss:.2f}%，已经明显偏离原始成本区间。")
        elif unrealized_pnl_pct < 0:
            snapshot_context_parts.append(f"当前这笔持仓浮亏约{abs_loss:.2f}%，仍处于成本下方运行。")
        elif unrealized_pnl_pct > 0:
            snapshot_context_parts.append(f"当前这笔持仓浮盈约{unrealized_pnl_pct:.2f}%，但后续判断仍需关注证据是否延续。")

    if cost_price is not None and current_price is not None:
        snapshot_context_parts.append(f"成本价约¥{cost_price:.2f}，当前价约¥{current_price:.2f}。")

    if holding_days is not None and holding_days >= 60:
        snapshot_context_parts.append(f"持有时间约{holding_days}天，后续更应优先确认经营与风险是否改善，而不是依赖短线技术信号。")

    opening_parts = list(snapshot_context_parts)

    if cleaned_observation:
        opening_parts.append(cleaned_observation)
    else:
        opening_parts.append("现阶段更适合把重点放在确认研究逻辑是否仍然成立，而不是把短期价格波动直接理解为修复开始。")

    raw_position_context = _clip_position_user_text(
        _simplify_position_user_language(raw_user_view.get("position_context", "")),
        88,
    )
    if raw_position_context and not _looks_truncated_position_text(raw_position_context):
        position_context = raw_position_context
    else:
        position_context = _clip_position_user_text(" ".join(snapshot_context_parts[:3]).strip(), 96)

    conclusion = _build_position_conclusion(
        raw_user_view.get("conclusion"),
        cleaned_observation,
        analysis_summary.get("overall_view"),
        neutral_advice.get("core_judgment"),
    )

    key_points_fallback = _build_position_candidate_items(
        raw_user_view.get("conclusion"),
        cleaned_observation,
        analysis_summary.get("overall_view"),
        neutral_advice.get("core_judgment"),
        limit=3,
        max_len=38,
    ) or ["当前判断仍要继续核对经营表现、风险变化和后续披露。"]
    key_points = _normalize_position_list_items(
        raw_user_view.get("key_points") or analysis_summary.get("key_points") or neutral_advice.get("reasoning"),
        fallback=key_points_fallback,
    )
    risk_focus_fallback = _build_position_candidate_items(
        raw_user_view.get("risk_focus"),
        cleaned_risk,
        limit=3,
        max_len=42,
    ) or ["请优先关注行业变化、公司公告和持仓波动是否继续恶化。"]
    risk_focus = _normalize_position_list_items(
        raw_user_view.get("risk_focus") or cleaned_risk,
        fallback=risk_focus_fallback,
    )
    watch_items_fallback = _build_position_candidate_items(
        raw_user_view.get("watch_items"),
        specific_plan.get("observation_factors"),
        neutral_advice.get("analysis_points"),
        cleaned_opportunity,
        limit=3,
        max_len=42,
    ) or ["后续重点观察经营质量、估值变化和能够改变当前判断的公开催化。"]
    watch_items = _normalize_position_list_items(
        raw_user_view.get("watch_items") or specific_plan.get("observation_factors") or neutral_advice.get("analysis_points") or cleaned_opportunity,
        fallback=watch_items_fallback,
    )
    uncertainty_note = _clip_position_user_text(
        _simplify_position_user_language(raw_user_view.get("uncertainty_note", ""))
        or "当前结论主要基于已披露信息，后续仍需结合财报、公告和行业变化继续验证。",
        72,
    )

    detailed_sections = [
        "### 当前状态",
        f"- {position_context}",
        f"- {conclusion}",
        "",
        "### 核心依据",
        *[f"- {item}" for item in key_points],
        "",
        "### 风险提示",
        *[f"- {item}" for item in risk_focus],
        "",
        "### 后续观察点",
        *[f"- {item}" for item in watch_items],
        "",
        "### 不确定性说明",
        f"- {uncertainty_note[:180]}",
    ]
    user_view = {
        "conclusion": conclusion[:80],
        "position_context": position_context[:96],
        "key_points": key_points,
        "risk_focus": risk_focus,
        "watch_items": watch_items,
        "uncertainty_note": uncertainty_note[:72],
    }
    compatibility_reason = _clip_position_user_text(f"{position_context} {conclusion}".strip(), 220)
    return compatibility_reason, "\n".join(detailed_sections).strip(), user_view


def _iter_review_fragments(text: Any) -> Iterable[str]:
    raw_text = _as_text(text)
    if not raw_text:
        return

    for chunk in re.split(r"\r?\n", raw_text):
        normalized = _plain_text(chunk)
        if not normalized:
            continue

        fragments = [
            fragment.strip()
            for fragment in _SENTENCE_SPLIT_PATTERN.split(normalized)
            if fragment.strip()
        ]
        if not fragments:
            fragments = [normalized]

        for fragment in fragments:
            if len(fragment) < 4:
                continue
            if _JSON_FIELD_PATTERN.match(fragment):
                continue
            if contains_review_execution_guidance(fragment):
                continue
            if is_low_signal_text(fragment):
                continue
            yield fragment


def sanitize_review_text_block(text: Any, fallback: str = "") -> str:
    deduped: List[str] = []
    for fragment in _iter_review_fragments(text):
        if fragment not in deduped:
            deduped.append(fragment)

    if not deduped:
        return fallback
    return "；".join(deduped[:6])[:1200]


def sanitize_review_detail_block(text: Any, fallback: str = "") -> str:
    raw_text = _as_text(text)
    if not raw_text:
        return fallback

    normalized = sanitize_report_artifacts(raw_text)
    if not normalized:
        return fallback

    cleaned_lines: List[str] = []

    for raw_line in normalized.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        plain = _plain_text(raw_line)
        if not plain:
            continue
        if _JSON_FIELD_PATTERN.match(plain):
            continue
        if contains_review_execution_guidance(plain):
            continue
        if is_low_signal_text(plain) and not stripped.startswith(("#", "-", "*")):
            continue

        cleaned_lines.append(raw_line.rstrip())

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    if cleaned_text:
        return cleaned_text[:4000]

    return fallback


def sanitize_review_points(points: Any, fallback: Iterable[str] = ()) -> List[str]:
    cleaned_points: List[str] = []

    if isinstance(points, list):
        source_items = points
    elif points in (None, ""):
        source_items = []
    else:
        source_items = [points]

    for item in source_items:
        for fragment in _iter_review_fragments(item):
            if fragment not in cleaned_points:
                cleaned_points.append(fragment)
            if len(cleaned_points) >= 5:
                return cleaned_points

    for item in fallback:
        normalized = _plain_text(item)
        if normalized and normalized not in cleaned_points:
            cleaned_points.append(normalized)
        if len(cleaned_points) >= 5:
            break

    return cleaned_points[:5]


def sanitize_brief_points(points: Any) -> List[str]:
    cleaned_points: List[str] = []

    if not isinstance(points, list):
        return cleaned_points

    for item in points:
        normalized = _plain_text(_as_text(item))
        if len(normalized) < 2:
            continue
        if _JSON_FIELD_PATTERN.match(normalized):
            continue
        if contains_actionable_content(normalized):
            continue
        if is_low_signal_text(normalized):
            continue
        if normalized not in cleaned_points:
            cleaned_points.append(normalized[:120])
        if len(cleaned_points) >= 5:
            break

    return cleaned_points


def contains_inferential_evidence(text: str) -> bool:
    normalized = _plain_text(_as_text(text))
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _INFERENTIAL_EVIDENCE_PATTERNS)


def normalize_research_brief_lists(
    core_evidence: Any,
    uncertainties: Any,
    invalidation_conditions: Any,
    watch_items: Any,
) -> Dict[str, List[str]]:
    cleaned_core_evidence = sanitize_brief_points(core_evidence)
    cleaned_uncertainties = sanitize_brief_points(uncertainties)
    cleaned_invalidation_conditions = sanitize_brief_points(invalidation_conditions)
    cleaned_watch_items = sanitize_brief_points(watch_items)

    normalized_core_evidence: List[str] = []
    demoted_inferential_items: List[str] = []

    for item in cleaned_core_evidence:
        if contains_inferential_evidence(item):
            demoted_inferential_items.append(item)
            continue
        normalized_core_evidence.append(item)

    for item in demoted_inferential_items:
        if item not in cleaned_uncertainties and len(cleaned_uncertainties) < 5:
            cleaned_uncertainties.append(item)
            continue
        if item not in cleaned_watch_items and len(cleaned_watch_items) < 5:
            cleaned_watch_items.append(item)

    return {
        "core_evidence": normalized_core_evidence[:5],
        "uncertainties": cleaned_uncertainties[:5],
        "invalidation_conditions": cleaned_invalidation_conditions[:5],
        "watch_items": cleaned_watch_items[:5],
    }


def sanitize_display_report_text(text: Any, fallback: str = "") -> str:
    raw_text = sanitize_report_artifacts(text)
    if not raw_text:
        return fallback

    cleaned_lines: List[str] = []
    in_disclaimer_block = False

    for raw_line in raw_text.splitlines():
        line = _normalize_display_line(raw_line.rstrip())
        normalized = _plain_text(line)

        if not normalized:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if "免责声明" in normalized or normalized == RESEARCH_ONLY_DISCLAIMER:
            cleaned_lines.append(line)
            # 免责声明正文整块保留：跳过可操作内容过滤，直到下一个 markdown 标题
            in_disclaimer_block = True
            continue

        if in_disclaimer_block:
            if line.strip().startswith("#"):
                in_disclaimer_block = False
            else:
                cleaned_lines.append(line)
                continue

        if contains_actionable_content(normalized):
            continue
        if any(pattern.search(normalized) for pattern in _DISPLAY_REPORT_RISK_PATTERNS):
            continue

        cleaned_lines.append(line)

    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
    cleaned_text = _normalize_research_disclaimer(cleaned_text)

    if cleaned_text:
        return cleaned_text[:4000]

    return sanitize_text_block(raw_text, fallback=fallback)


def _build_position_appendix_sections(result_data: Dict[str, Any]) -> List[Dict[str, str]]:
    normalized_sections: List[Dict[str, str]] = []
    seen_keys: set[str] = set()

    raw_sections = result_data.get("appendix_sections")
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if not isinstance(item, dict):
                continue
            raw_title = str(item.get("title") or "").strip()
            key = str(item.get("key") or _POSITION_APPENDIX_TITLE_TO_KEY.get(raw_title) or "").strip()
            title = raw_title or dict(_POSITION_APPENDIX_SECTION_ORDER).get(key, "")
            content = sanitize_display_report_text(item.get("content"))
            if key and title and content and key not in seen_keys:
                normalized_sections.append({"key": key, "title": title, "content": content[:4000]})
                seen_keys.add(key)

    if normalized_sections:
        return normalized_sections

    section_content_by_key: Dict[str, str] = {}
    for key, _title in _POSITION_APPENDIX_SECTION_ORDER:
        cleaned_direct = sanitize_display_report_text(result_data.get(key))
        if cleaned_direct:
            section_content_by_key[key] = cleaned_direct

    raw_detailed_analysis = sanitize_report_artifacts(result_data.get("detailed_analysis"))
    if raw_detailed_analysis:
        current_key: str | None = None
        current_lines: List[str] = []

        def flush_current_section() -> None:
            nonlocal current_key, current_lines
            if not current_key:
                current_lines = []
                return
            cleaned = sanitize_display_report_text("\n".join(current_lines).strip())
            if cleaned and current_key not in section_content_by_key:
                section_content_by_key[current_key] = cleaned
            current_key = None
            current_lines = []

        for raw_line in raw_detailed_analysis.splitlines():
            stripped = raw_line.strip()
            heading_match = _POSITION_APPENDIX_HEADING_PATTERN.match(stripped)
            if heading_match:
                flush_current_section()
                current_key = _POSITION_APPENDIX_TITLE_TO_KEY.get(heading_match.group(1))
                continue
            if current_key:
                current_lines.append(raw_line)

        flush_current_section()

    for key, title in _POSITION_APPENDIX_SECTION_ORDER:
        content = section_content_by_key.get(key)
        if content:
            normalized_sections.append({"key": key, "title": title, "content": content[:4000]})

    return normalized_sections


def filter_analysis_reports(reports: Any) -> Dict[str, str]:
    if not isinstance(reports, dict):
        return {}

    filtered: Dict[str, str] = {}
    for key in SAFE_REPORT_KEYS:
        cleaned = sanitize_text_block(reports.get(key))
        if cleaned:
            filtered[key] = cleaned
    return filtered


def _iter_safe_fragments(reports: Dict[str, str], fallback_summary: str = "") -> Iterable[str]:
    if fallback_summary:
        cleaned_summary = sanitize_text_block(fallback_summary)
        if cleaned_summary:
            for fragment in _SENTENCE_SPLIT_PATTERN.split(cleaned_summary):
                sentence = fragment.strip()
                if sentence and not contains_actionable_content(sentence) and not is_low_signal_text(sentence):
                    yield sentence

    summary_priority = (
        "fundamentals_report",
        "market_report",
        "sector_report",
        "news_report",
        "sentiment_report",
        "index_report",
    )

    for key in summary_priority:
        content = sanitize_text_block(reports.get(key, ""))
        if not content:
            continue
        for fragment in _SENTENCE_SPLIT_PATTERN.split(content):
            sentence = fragment.strip()
            if sentence and not contains_actionable_content(sentence) and not is_low_signal_text(sentence):
                yield sentence


def build_research_summary(reports: Dict[str, str], fallback_summary: str = "") -> str:
    candidate_fragments: List[str] = []
    for fragment in _iter_safe_fragments(reports, fallback_summary):
        normalized = _plain_text(fragment)
        if normalized and normalized not in candidate_fragments:
            candidate_fragments.append(normalized)

    summary_parts = sorted(candidate_fragments, key=_fragment_score, reverse=True)[:3]

    if summary_parts:
        return "；".join(summary_parts)[:800]

    return "本次结果已按研究辅助模式输出，请重点关注基础数据、风险因素与后续披露信息。"


def build_key_points(reports: Dict[str, str], key_points: Any, summary: str) -> List[str]:
    cleaned_points: List[str] = []
    if isinstance(key_points, list):
        for item in key_points:
            point = sanitize_text_block(item)
            if point and point not in cleaned_points and not is_low_signal_text(point):
                cleaned_points.append(point)

    if len(cleaned_points) >= 3:
        return cleaned_points[:5]

    for fragment in _iter_safe_fragments(reports, summary):
        if fragment not in cleaned_points and not is_low_signal_text(fragment):
            cleaned_points.append(fragment)
        if len(cleaned_points) >= 5:
            break

    return cleaned_points[:5]


def sanitize_analysis_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    reports = filter_analysis_reports(sanitized.get("reports") or {})
    summary = build_research_summary(reports, sanitized.get("summary", ""))

    sanitized["reports"] = reports
    sanitized["summary"] = summary
    sanitized["key_points"] = build_key_points(reports, sanitized.get("key_points"), summary)

    decision = sanitized.get("decision")
    normalized_action = ""
    if isinstance(decision, dict):
        sanitized_decision: Dict[str, Any] = {}
        action = decision.get("analysis_view") or decision.get("action")
        if isinstance(action, str) and action.strip():
            action_mapping = {
                "BUY": "乐观",
                "SELL": "审慎",
                "HOLD": "中性",
                "buy": "乐观",
                "sell": "审慎",
                "hold": "中性",
                "买入": "乐观",
                "卖出": "审慎",
                "持有": "中性",
                "看涨": "乐观",
                "看跌": "审慎",
                "乐观": "乐观",
                "审慎": "审慎",
                "中性": "中性",
            }
            normalized_action = action_mapping.get(action.strip(), action.strip())
            sanitized_decision["action"] = normalized_action
            sanitized_decision["analysis_view"] = normalized_action
        confidence = decision.get("confidence")
        if isinstance(confidence, (int, float)):
            sanitized_decision["confidence"] = confidence / 100 if confidence > 1 else confidence
        risk_score = decision.get("risk_score")
        if isinstance(risk_score, (int, float)):
            sanitized_decision["risk_score"] = risk_score / 100 if risk_score > 1 else risk_score
        reasoning = sanitize_text_block(decision.get("reasoning"), fallback=summary)
        if reasoning:
            sanitized_decision["reasoning"] = reasoning[:400]
        decision_summary = sanitize_text_block(decision.get("summary"))
        if decision_summary:
            sanitized_decision["summary"] = decision_summary[:240]
        risk_warning = sanitize_text_block(decision.get("risk_warning"))
        if risk_warning:
            sanitized_decision["risk_warning"] = risk_warning[:200]
        normalized_lists = normalize_research_brief_lists(
            decision.get("core_evidence"),
            decision.get("uncertainties"),
            decision.get("invalidation_conditions"),
            decision.get("watch_items"),
        )
        for field_name in ("core_evidence", "uncertainties", "invalidation_conditions", "watch_items"):
            cleaned_items = normalized_lists.get(field_name, [])
            if cleaned_items:
                sanitized_decision[field_name] = cleaned_items
        sanitized["decision"] = sanitized_decision

    recommendation_parts: List[str] = []
    if normalized_action:
        recommendation_parts.append(f"研究判断：{normalized_action}")
    if summary:
        recommendation_parts.append(summary[:120])
    recommendation_parts.append("请结合详细报告继续关注证据变化、风险因素与后续披露。")
    sanitized["recommendation"] = "；".join(part for part in recommendation_parts if part)[:240] or GENERIC_RESEARCH_RECOMMENDATION

    return sanitized


def sanitize_position_analysis_payload(
    result_data: Dict[str, Any],
    position_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    appendix_sections = _build_position_appendix_sections(sanitized)
    action_reason, user_detailed_analysis, user_view = _build_position_user_action_reason(sanitized, position_snapshot)
    summary = action_reason or sanitize_position_text_block(
        sanitized.get("summary") or sanitized.get("action_reason") or sanitized.get("detailed_analysis"),
        fallback="该持仓研究已转换为研究观察，请结合自身策略独立判断。",
    )

    sanitized["action"] = "hold"
    sanitized["action_reason"] = action_reason or "当前仅保留研究结论、风险提示与观察重点，不提供执行性交易建议。"
    sanitized["price_targets"] = {}
    sanitized["suggested_quantity"] = None
    sanitized["suggested_amount"] = None
    sanitized["risk_assessment"] = sanitize_text_block(
        sanitized.get("risk_assessment"),
        fallback="请重点关注持仓波动、行业变化和公告风险。",
    )
    sanitized["opportunity_assessment"] = sanitize_text_block(
        sanitized.get("opportunity_assessment"),
        fallback="请持续跟踪经营质量、估值变化和潜在催化事件。",
    )
    sanitized["detailed_analysis"] = user_detailed_analysis
    sanitized["user_view"] = user_view
    sanitized["appendix_sections"] = appendix_sections
    sanitized["summary"] = summary
    sanitized["recommendation"] = GENERIC_POSITION_RECOMMENDATION

    confidence = sanitized.get("confidence")
    if isinstance(confidence, (int, float)):
        sanitized["confidence"] = max(0.0, min(100.0, float(confidence)))

    return sanitized


def sanitize_trade_review_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    sanitized["summary"] = sanitize_review_text_block(
        sanitized.get("summary"),
        fallback=GENERIC_REVIEW_SUMMARY,
    )
    sanitized["strengths"] = sanitize_review_points(sanitized.get("strengths"))
    sanitized["weaknesses"] = sanitize_review_points(sanitized.get("weaknesses"))
    sanitized["suggestions"] = sanitize_review_points(
        sanitized.get("suggestions"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["timing_analysis"] = sanitize_review_detail_block(
        sanitized.get("timing_analysis"),
        fallback="请重点复盘入场与退出依据是否充分，而非给出新的买卖指令。",
    )
    sanitized["position_analysis"] = sanitize_review_detail_block(
        sanitized.get("position_analysis"),
        fallback="请重点复盘仓位管理依据与风险暴露，不提供具体仓位调整方案。",
    )
    sanitized["emotion_analysis"] = sanitize_review_detail_block(
        sanitized.get("emotion_analysis"),
        fallback="请重点复盘情绪控制与纪律执行问题。",
    )
    sanitized["attribution_analysis"] = sanitize_review_detail_block(
        sanitized.get("attribution_analysis"),
        fallback="请重点复盘收益与亏损来源的证据归因。",
    )
    sanitized["plan_adherence"] = sanitize_review_text_block(sanitized.get("plan_adherence"))
    sanitized["plan_deviation"] = sanitize_review_text_block(sanitized.get("plan_deviation"))
    sanitized.pop("optimal_pnl", None)
    sanitized.pop("missed_profit", None)
    sanitized.pop("avoided_loss", None)

    return sanitized


def sanitize_periodic_review_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    sanitized["summary"] = sanitize_review_text_block(
        sanitized.get("summary"),
        fallback=GENERIC_REVIEW_SUMMARY,
    )
    sanitized["trading_style"] = sanitize_review_text_block(
        sanitized.get("trading_style"),
        fallback="请从风格稳定性、纪律执行与研究准备充分性角度进行阶段性复盘。",
    )
    sanitized["common_mistakes"] = sanitize_review_points(sanitized.get("common_mistakes"))
    sanitized["improvement_areas"] = sanitize_review_points(
        sanitized.get("improvement_areas"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["action_plan"] = sanitize_review_points(
        sanitized.get("action_plan"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["best_trade"] = sanitize_review_text_block(sanitized.get("best_trade"))
    sanitized["worst_trade"] = sanitize_review_text_block(sanitized.get("worst_trade"))

    return sanitized