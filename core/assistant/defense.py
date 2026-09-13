"""智能助手回复质量防线（A11 收编自 app/services/intelligent_assistant_service.py）。

本模块是四道防线及数字溯源辅助的**唯一事实源**（物理搬家，逻辑不改）：
1. _has_fabricated_tool_json   编造工具 JSON 结果硬拦截
2. _has_fabricated_tool_refs   伪造工具调用痕迹
3. _has_unsourced_numbers      未调工具却含大量具体数字
4. _has_untraced_risky_numbers 调过工具但混入无法溯源的高风险数字

service 层通过 `from core.assistant.defense import ...` 复用这些名字，
ReplyGate 也统一调用本模块——任何路径的回复都过同一套防线。

设计文档：docs/05-design/v3.0/assistant-quality-architecture-refactor.md §3.3
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ── 编造/未溯源检测的正则与重试指令 ───────────────────────────────────────────
# 匹配回复中伪造的工具调用痕迹（如"数据来源：get_xxx_tool"或"📌 数据来源：XXX工具"）
_FABRICATED_TOOL_REF_RE = re.compile(
    r"(数据来源[:：]\s*(get_|fetch_)[a-z_]+|📌\s*数据来源[:：].*工具)",
    re.IGNORECASE,
)
# 匹配回复中出现的具体数字（亿元/万元/元/公斤等），用于检测未调工具却给数据的情况
_SPECIFIC_NUMBER_RE = re.compile(
    r"[\d,]+\.?\d*\s*(亿元|万元|元|公斤|辆|头|%|pct|分位|x|倍)"
)
# 匹配"工具名(参数) → { JSON结果 }"模式：所有真实工具的返回都是 Markdown 文本，
# 回复中把工具结果包装成 JSON 对象必然是 LLM 编造的结构化字段（如 post_count: 127）
_FABRICATED_TOOL_JSON_RE = re.compile(
    r"(get_|fetch_|trigger_|set_)[a-z0-9_]+\s*\([^)\n]{0,80}\)[^{\n]{0,60}\{[^{}\n]{5,500}\}",
    re.IGNORECASE,
)
# "未调工具但回复含大量数字"拦截后的自动纠错重试指令（最多重试1次）
_UNSOURCED_RETRY_PROMPT = (
    "【系统校验反馈】你刚才的回复包含了大量具体数字，但本轮对话你没有调用任何工具，"
    "这些数字无法溯源，属于训练记忆填充，已被系统拦截。\n"
    "请重新回答用户的问题，要求：\n"
    "1. 必须先调用相关工具获取真实数据（行业/板块问题用 get_sector_daily 或 search_sector，"
    "个股问题用 get_stock_market_data_unified / get_technical_indicators，"
    "最新行业动态用 get_web_search）；\n"
    "2. 只基于工具返回的真实数据作答，引用数字时标注来源和日期；\n"
    "3. 若工具确实未返回相关数据，请明确说明数据缺失，禁止使用任何具体数字。"
)

# "调过工具但高风险数字无法溯源"拦截后的自动纠错重试指令（最多重试1次）
_UNTRACED_RETRY_PROMPT_TEMPLATE = (
    "【系统校验反馈】你刚才的回复中引用了以下具体数字：{numbers}，"
    "但这些数字既不在本轮工具返回结果中，也不在历史工具结果或事实记忆中，无法溯源，"
    "疑似来自训练记忆，已被系统拦截。\n"
    "请重新回答用户的问题，要求：\n"
    "1. 只引用工具返回中出现过的数字；若是基于工具数字的计算结果（如区间涨跌幅、"
    "同比变化），必须在回复中列出算式与依据数字（例如：从X涨到Y，涨幅=(Y-X)/X），"
    "且计算必须正确；\n"
    "2. 需要新数据时先调用工具（行业/板块问题用 get_sector_daily 或 "
    "analyze_sector_by_name，个股问题用 get_stock_market_data_unified，"
    "最新行业动态用 get_web_search）；\n"
    "3. 工具未覆盖的数据一律改为定性描述或明确说明数据缺失，禁止编造具体数字。"
)


def _build_untraced_interception(untraced_detail: str) -> str:
    """构造"高风险数字无法溯源"的拦截文案（重试失败后兜底）。"""
    return (
        "抱歉，我在刚才的回复中引用了一些工具和搜索结果里都没有的具体数字"
        f"（如 {untraced_detail}），这类数字可能来自过时的记忆而非实时数据，"
        "继续呈现会误导您的判断，因此已整段拦截。\n\n"
        "常见原因：搜索结果只有标题/链接/摘要，未包含具体数值"
        "（如行业成本数据多在付费研报正文中，搜索引擎摘要抓不到）。\n"
        "您可以：\n"
        "• 换更具体的关键词让我再搜索（如\"牧原股份 7月成本 公告\"）\n"
        "• 让我引用搜索到的来源链接，由您人工查看原文\n"
        "• 只让我分析工具已返回的真实数据\n"
    )


# ── 第4道防线：高风险数字溯源校验 ─────────────────────────────────────────────
# 提取回复中带金融单位的高风险数字（长单位优先，避免"元/公斤"被"元"截断；
# 同时覆盖中英文单位写法：元/kg 与 元/公斤 是同一单位）
_RISKY_NUMBER_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(元/[kK][gG]|元/公斤|元/吨|元/斤|亿元|万元|万手|分位|pct|%|倍|元|手)"
)
# 提取工具返回文本中的所有数字（带金融单位或裸数字，如 JSON 字段值 0.37 / 15764.6）
_TOOL_NUMBER_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(元/[kK][gG]|元/公斤|元/吨|元/斤|亿元|万元|万手|分位|pct|%|倍|元|手)?"
)
# 金额类单位 → 归一化到"亿元"的换算因子
_AMOUNT_UNIT_FACTOR = {"亿元": 1.0, "万元": 1e-4}
# 工具侧裸数字的金额反推：当工具返回的是无单位裸数字（如成交额、规模），
# 而 LLM 回复时带上了「亿元/万元」等金额单位时，按以下常见单位反推
# （归一化到亿元），能匹配上就算溯源成功。
# 顺序优先用大单位（亿元、万元），避免小单位下大数误撞上价格类裸数字。
_BARE_AMOUNT_GUESS_FACTORS = [
    ("亿元", 1.0),
    ("万元", 1e-4),
    ("元", 1e-8),
]
# 成交量类裸数字反推（手 ↔ 万手）
_BARE_VOLUME_GUESS_FACTORS = [
    ("万手", 1e-4),  # 1手 = 0.0001万手
    ("手", 1.0),
]
# 重量价格单位 → 归一化到"元/公斤"的换算因子（乘以该因子=换算成元/公斤价格）。
# 每公斤价 = 每斤价 × 2（1公斤=2斤）；每公斤价 = 每吨价 ÷ 1000（1吨=1000公斤）。
# LLM 常将工具返回的 元/kg 换算为 元/斤 表述（如 10.87元/kg → 5.44元/斤），
# 属合法换算，不算编造
_WEIGHT_UNIT_FACTOR = {"元/公斤": 1.0, "元/斤": 2.0, "元/吨": 0.001}
# 匹配容差（工具值与回复值的相对误差上限；1% 覆盖常规四舍五入，
# 同时避免跨语义误匹配——如编造"15.8元/公斤"撞上质押 holding_ratio 15.54）
_TRACE_TOLERANCE = 0.01
# 百分比类数字的专项容差（涨跌幅、费率等容易因四舍五入或累计计算产生误差）
# 例如工具返回 0.17%，LLM 说"约0.2%"是合理的，不算编造
_TRACE_PCT_TOLERANCE = 0.05
# 百分比单位列表
_PCT_UNITS = {"%", "pct", "分位"}
# 不可溯源高风险数字达到该数量 → 触发拦截（不再调LLM重试，改为本地模糊化处理）
# 阈值不宜过低：LLM 对工具返回做简单加法/平均/四舍五入是合理的，
# 如"管理费0.15%+托管费0.05%=0.20%"、"近5日累计涨跌1.93%"等
_UNTRACED_NUMBER_LIMIT = 6


def _normalize_unit(unit: str) -> str:
    """单位别名归一：元/kg 与 元/公斤 视为同一单位。"""
    u = (unit or "").lower()
    return u.replace("/kg", "/公斤").replace("kg", "公斤")


def _parse_number(text: str) -> Optional[float]:
    """'1,771.97' → 1771.97；失败返回 None。"""
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _extract_risky_numbers(text: str, pattern: "re.Pattern") -> list:
    """从文本中提取 (数值, 单位) 列表，单位统一小写。"""
    out = []
    for m in pattern.finditer(text or ""):
        val = _parse_number(m.group(1))
        if val is None:
            continue
        unit = (m.group(2) or "").lower() if pattern.groups >= 2 else ""
        out.append((val, unit))
    return out


def _number_matches(value: float, unit: str, candidates: list) -> bool:
    """判断 (数值, 单位) 是否能在候选集（工具返回数字）中溯源。

    匹配规则：
    - 金额类（亿元/万元）：必须同属金额类，按归一化到亿元后匹配
      （如 15764.6万 ↔ 1.58亿；15764.6万 ≠ 157.6亿，防100倍换算错误）
    - 重量价格类（元/公斤、元/斤、元/吨）：归一化到元/公斤后匹配
      （如 5.44元/斤 ↔ 10.87元/kg，合法单位换算不算编造）
    - 非金额类（%/元/公斤/kg/倍/分位/裸数字）：单位写法差异按数值直接匹配（1%容差）
    - 不做 ×100 的百分比换算：工具返回 0.37 就是 0.37%，回复写 37% 视为不可溯源
    - 兜底：工具侧裸数字（无单位）但回复带金额/成交量单位时，按常见单位反推匹配
      （如工具返回 543533 万元 → LLM 说 54.35 亿元，属合理换算）
    """
    tol = _TRACE_TOLERANCE
    unit = _normalize_unit(unit)
    value_is_amount = unit in _AMOUNT_UNIT_FACTOR
    value_is_volume = unit in ("万手", "手")
    value_is_pct = unit in _PCT_UNITS
    for cand_val, cand_unit_raw in candidates:
        cand_unit = _normalize_unit(cand_unit_raw)
        cand_is_amount = cand_unit in _AMOUNT_UNIT_FACTOR
        cand_is_bare = cand_unit == ""
        cand_is_pct = cand_unit in _PCT_UNITS
        # 百分比类：用专项容差（四舍五入/累计计算误差较大属合理）
        if value_is_pct and cand_is_pct:
            if cand_val == 0 and value == 0:
                return True
            ref = max(abs(cand_val), abs(value), 1e-9)
            if abs(value - cand_val) <= _TRACE_PCT_TOLERANCE * ref:
                return True
            continue
        # 一边百分比一边裸数字 → 也用百分比容差（工具裸数字常就是百分比值）
        if value_is_pct and cand_is_bare:
            ref = max(abs(cand_val), abs(value), 1e-9)
            if abs(value - cand_val) <= _TRACE_PCT_TOLERANCE * ref:
                return True
        # 1) 两边都是金额单位 → 归一化到亿元后直接比较
        if value_is_amount and cand_is_amount:
            v1 = value * _AMOUNT_UNIT_FACTOR[unit]
            v2 = cand_val * _AMOUNT_UNIT_FACTOR[cand_unit]
            if abs(v1 - v2) <= tol * max(abs(v2), 1e-9):
                return True
            continue
        # 候选是金额但回复不是 → 跳过，避免把价格/百分比等误匹配成金额
        if cand_is_amount and not value_is_amount:
            continue
        # 2) 重量价格单位：归一化到元/公斤后比较（斤↔公斤 ×2、吨↔公斤 ×1000）
        if unit in _WEIGHT_UNIT_FACTOR and cand_unit in _WEIGHT_UNIT_FACTOR:
            v1 = value * _WEIGHT_UNIT_FACTOR[unit]
            v2 = cand_val * _WEIGHT_UNIT_FACTOR[cand_unit]
            if abs(v1 - v2) <= tol * max(abs(v2), 1e-9):
                return True
        # 3) 非金额类：数值相等即匹配（容忍单位写法差异）
        if abs(value - cand_val) <= tol * max(abs(cand_val), 1e-9):
            return True
        # 4) 兜底：工具侧是裸数字，回复带金额/成交量单位 → 按常见单位反推
        if cand_is_bare and cand_val > 0:
            if value_is_amount:
                v1 = value * _AMOUNT_UNIT_FACTOR[unit]
                for _, factor in _BARE_AMOUNT_GUESS_FACTORS:
                    v2 = cand_val * factor
                    if v2 <= 0:
                        continue
                    if abs(v1 - v2) <= tol * max(abs(v2), 1e-9):
                        return True
            elif value_is_volume:
                # 归一化到"手"再比较
                v1 = value * (10000 if unit == "万手" else 1)
                for _, factor in _BARE_VOLUME_GUESS_FACTORS:
                    # factor 是 候选值(以factor_unit计) → 手 的换算因子
                    # 归一化到手：cand_val * factor
                    v2 = cand_val * factor
                    if v2 <= 0:
                        continue
                    if abs(v1 - v2) <= tol * max(abs(v2), 1e-9):
                        return True
    return False


def _find_closest_candidate(value: float, unit: str, candidates: list) -> Optional[tuple]:
    """为一个不可溯源数字找到工具候选集中最接近的值（及推导关系说明）。

    返回 (cand_val, cand_unit, relation_desc) 或 None。
    relation_desc 描述推导关系，如"四舍五入"、"累计/差值估算"、"单位换算"等。
    """
    unit = _normalize_unit(unit)
    tol = _TRACE_TOLERANCE
    pct_tol = _TRACE_PCT_TOLERANCE
    value_is_amount = unit in _AMOUNT_UNIT_FACTOR
    value_is_volume = unit in ("万手", "手")
    value_is_pct = unit in _PCT_UNITS

    best = None  # (relative_diff, cand_val, cand_unit, relation)

    for cand_val, cand_unit_raw in candidates:
        cand_unit = _normalize_unit(cand_unit_raw)
        cand_is_amount = cand_unit in _AMOUNT_UNIT_FACTOR
        cand_is_bare = cand_unit == ""
        cand_is_pct = cand_unit in _PCT_UNITS

        v1 = value
        v2 = cand_val
        relation = None

        # 金额类（两边都是金额单位）
        if value_is_amount and cand_is_amount:
            v1 = value * _AMOUNT_UNIT_FACTOR[unit]
            v2 = cand_val * _AMOUNT_UNIT_FACTOR[cand_unit]
            relation = f"{cand_val}{cand_unit}（单位换算）"
        # 百分比类
        elif value_is_pct and cand_is_pct:
            relation = f"{cand_val}{cand_unit}（四舍五入/近似）"
        elif value_is_pct and cand_is_bare:
            relation = f"{cand_val}（四舍五入/近似）"
        # 金额 + 裸数字（反推）
        elif value_is_amount and cand_is_bare:
            best_guess = None
            for guess_unit, factor in _BARE_AMOUNT_GUESS_FACTORS:
                v2_guess = cand_val * factor
                if v2_guess <= 0:
                    continue
                rel_diff = abs(value * _AMOUNT_UNIT_FACTOR[unit] - v2_guess) \
                    / max(abs(v2_guess), 1e-9)
                if rel_diff < 0.5:  # 放宽到50%内都算有参考关系
                    if best_guess is None or rel_diff < best_guess[0]:
                        best_guess = (rel_diff, cand_val, guess_unit,
                                      f"{cand_val}元 ≈ {cand_val * factor:.2f}亿元（金额估算）")
            if best_guess:
                rel_diff, cv, cu, desc = best_guess
                if best is None or rel_diff < best[0]:
                    best = (rel_diff, cv, cu, desc)
            continue
        # 成交量 + 裸数字
        elif value_is_volume and cand_is_bare:
            best_guess = None
            for guess_unit, factor in _BARE_VOLUME_GUESS_FACTORS:
                v1_hand = value * (10000 if unit == "万手" else 1)
                v2_hand = cand_val * factor
                if v2_hand <= 0:
                    continue
                rel_diff = abs(v1_hand - v2_hand) / max(abs(v2_hand), 1e-9)
                if rel_diff < 0.5:
                    desc = f"{cand_val}手 ≈ {cand_val * factor / 10000:.2f}万手（成交量估算）" \
                        if guess_unit == "万手" \
                        else f"{cand_val}手（原始数据）"
                    if best_guess is None or rel_diff < best_guess[0]:
                        best_guess = (rel_diff, cand_val, guess_unit, desc)
            if best_guess:
                rel_diff, cv, cu, desc = best_guess
                if best is None or rel_diff < best[0]:
                    best = (rel_diff, cv, cu, desc)
            continue
        # 同单位（价格/倍数等）
        elif unit == cand_unit or (cand_is_bare and not value_is_amount):
            relation = f"{cand_val}{cand_unit}（近似）"
        else:
            continue

        if v2 == 0 and v1 == 0:
            rel_diff = 0.0
        else:
            ref = max(abs(v2), abs(v1), 1e-9)
            rel_diff = abs(v1 - v2) / ref

        # 跳过差异太大的（>100% 基本没关系）
        if rel_diff > 1.0:
            continue
        if rel_diff < (pct_tol if value_is_pct else tol):
            relation = relation or f"{cand_val}{cand_unit}"
        if best is None or rel_diff < best[0]:
            best = (rel_diff, cand_val, cand_unit, relation or f"{cand_val}{cand_unit}")

    if best is None:
        return None
    return (best[1], best[2], best[3])


def _get_untraced_risky_numbers(
    reply: str,
    tool_results: Optional[list],
    user_message: str = "",
    history_tool_contents: Optional[list] = None,
    return_candidates: bool = False,
):
    """提取回复中无法在工具返回原文（或用户消息）中溯源的高风险数字。

    Args:
        tool_results: 本轮工具返回（collector 收集）
        user_message: 用户消息（引用用户给的数字不算编造）
        history_tool_contents: 会话历史中 role=tool 的消息内容（多轮对话时，
            引用上一轮工具的真实数据同样可溯源，不应误判）
        return_candidates: True 时返回 (untraced, candidates) 供日志排查

    Returns:
        不可溯源的 "数值+单位" 字符串列表（用于日志与阈值判断）。
    """
    if not reply:
        return ([], []) if return_candidates else []
    # 工具返回原文中的所有数字（含裸数字）作为可信候选集
    candidates: list = []
    for item in (tool_results or []):
        content = item.get("content") or ""
        if not content or item.get("is_error"):
            continue
        candidates.extend(_extract_risky_numbers(content, _TOOL_NUMBER_RE))
    # 会话历史中工具返回过的数字同样可信（多轮引用）
    for content in (history_tool_contents or []):
        if content:
            candidates.extend(_extract_risky_numbers(content, _TOOL_NUMBER_RE))
    # 用户消息中出现的数字也视为可信（助手引用用户给的数字不算编造）
    user_numbers = _extract_risky_numbers(user_message or "", _TOOL_NUMBER_RE)
    candidates.extend(user_numbers)

    untraced = []
    for m in _RISKY_NUMBER_RE.finditer(reply):
        val = _parse_number(m.group(1))
        unit = (m.group(2) or "").lower()
        if val is None:
            continue
        # 排除：年份（1900-2099）、百分比里的小整数序号等噪音由阈值兜底
        if 1900 <= val <= 2099 and val == int(val):
            continue
        if _number_matches(val, unit, candidates):
            continue
        untraced.append(f"{m.group(1)}{m.group(2)}")
    if return_candidates:
        return untraced, candidates
    return untraced


def _build_data_transparency_note(
    reply: str,
    tool_results: list,
    user_message: str,
    history_tool_contents: list,
) -> Optional[str]:
    """生成「数据说明」附言：把推导/估算的数字透明标注出来，供用户自行判断。

    不再硬拦截，而是把 LLM 表述值、工具原始值、可能的推导关系都列出来。
    """
    untraced, candidates = _get_untraced_risky_numbers(
        reply, tool_results, user_message, history_tool_contents, return_candidates=True)
    if not untraced:
        return None

    lines = []
    for num_str in untraced[:8]:
        # 解析数值和单位
        m = _RISKY_NUMBER_RE.match(num_str)
        if not m:
            continue
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2) or ""
        closest = _find_closest_candidate(val, unit, candidates)
        if closest:
            _, _, relation = closest
            lines.append(f"- **{num_str}**：工具参考数据 {relation}，以上为估算/推导值，请谨慎参考")
        else:
            lines.append(f"- **{num_str}**：未在工具返回中找到对应数据，请注意核实")

    if not lines:
        return None

    return (
        "\n\n---\n"
        "📌 **数据说明**\n"
        "下面这些数值是基于工具原始数据推导或估算的（可能经过四舍五入、累计计算、单位换算等），"
        "原始工具数据也一并列出，请您自行判断：\n"
        + "\n".join(lines)
    )


# ── 四道主防线 ────────────────────────────────────────────────────────────────

def _has_fabricated_tool_json(reply: str) -> bool:
    """检测回复中是否把工具结果编造为 JSON 对象。

    系统所有工具的真实返回均为 Markdown 文本（output_shape=markdown），
    绝不会返回 {"sentiment_score": 0.32, "post_count": 127} 这类 JSON。
    若回复中出现"工具名(参数) ... { json }"模式，说明 LLM 自行构造了
    工具返回的结构化假数据 —— 硬拦截。
    """
    if not reply:
        return False
    m = _FABRICATED_TOOL_JSON_RE.search(reply)
    if m:
        logger.warning("[智能助手] 检测到编造的工具JSON结果: %.120s", m.group(0))
        return True
    return False


def _has_fabricated_tool_refs(reply: str, tools_used: list) -> bool:
    """检测回复中是否伪造了工具调用痕迹。

    判定标准：回复中出现了"数据来源：get_xxx_tool"等字样，
    但 tools_used 为空或不包含对应工具名。
    """
    if not reply:
        return False
    matches = _FABRICATED_TOOL_REF_RE.findall(reply)
    if not matches:
        return False
    # 有工具引用痕迹但没有实际调用任何工具 → 伪造
    if not tools_used:
        return True
    # 有工具引用痕迹，检查引用的工具名是否在 tools_used 中
    # 从回复中提取工具名
    tool_names_in_reply = set()
    for m in re.finditer(r"(get_|fetch_)[a-z_]+", reply, re.IGNORECASE):
        tool_names_in_reply.add(m.group(0).lower())
    tools_used_lower = {t.lower() for t in tools_used}
    # 如果引用的工具名都不在实际调用列表中 → 伪造
    if tool_names_in_reply and not tool_names_in_reply.intersection(tools_used_lower):
        return True
    return False


def _has_unsourced_numbers(reply: str, tools_used: list) -> bool:
    """检测回复中是否包含大量具体数字但未调用任何数据工具。

    用于拦截 LLM 未调工具却在回复中编造精确财务/销量数据的情况。
    """
    if not reply or tools_used:
        return False
    # 统计回复中的具体数字数量
    numbers = _SPECIFIC_NUMBER_RE.findall(reply)
    # 超过 5 个具体数字且未调任何工具 → 大概率编造
    return len(numbers) > 5


def _has_untraced_risky_numbers(
    reply: str,
    tool_results: Optional[list],
    tools_used: list,
    user_message: str = "",
    history_tool_contents: Optional[list] = None,
) -> bool:
    """第4道防线：调用了工具，但回复中混入大量无法溯源的高风险数字。

    场景：LLM 确实调用了工具（前三道防线通过），却用训练记忆补齐
    工具未返回的数字（如"行业成本线15.8元/公斤""PE近5年75%分位"），
    或对工具数字做错误换算（0.37 说成 37%、15764.6万 说成 157.6亿）。
    """
    if not reply or not tools_used:
        return False
    untraced, candidates = _get_untraced_risky_numbers(
        reply, tool_results, user_message, history_tool_contents, return_candidates=True
    )
    if len(untraced) >= _UNTRACED_NUMBER_LIMIT:
        # 附带候选集摘要，便于排查"数字在工具返回里但没匹配上"的误判（如单位别名差异）
        cand_preview = [f"{v}{u}" for v, u in candidates[:30]]
        logger.warning(
            "[智能助手] 检测到 %d 个无法溯源的高风险数字: %s | 工具候选集(%d个, 前30): %s",
            len(untraced), untraced[:10], len(candidates), cand_preview,
        )
        return True
    return False
