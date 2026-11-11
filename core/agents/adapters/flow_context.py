"""流程上下文注入助手（v4.0 第二波：流程五段闭环）

流程改造（用户拍板「五段全做」）：
    辩论 → ①风险约束卡(机械) → ②计划(注入约束) → ③情景试算(机械)
         → ④风险审查(注入试算) → 用户版计划(注入约束+试算)

两个确定性节点把结果写入 state：
    risk_profile_card  —— 事前风险约束卡（risk_profile_v2 节点产出）
    scenario_simulation —— 情景效果试算（scenario_simulator_v2 节点产出）

下游 agent 在 _build_user_prompt 的最终返回值上追加本模块产出的文本块，
对「模板系统提示词」和「降级提示词」两条路径一视同仁（后置追加，
不依赖模板里预埋变量）。
"""

from typing import Any, Dict

from core.agents.base import GENERIC_REPORT_FALLBACK


def is_degraded_placeholder(value: Any) -> bool:
    """判断值是否为降级占位文本或 error dict。

    降级形态统一为 GENERIC_REPORT_FALLBACK 文本；历史遗留的 error dict
    （{'error': '...'}）也视为降级。用于下游跳过 + 前端降级识别。
    """
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        if text == GENERIC_REPORT_FALLBACK:
            return True
        # 兼容历史降级文案：仅对占位长度的短文本做关键词匹配，
        # 避免长报告正文含「待验证/未完成」等词被误判为降级（误杀真实内容）
        if len(text) <= 50:
            lowered = text.lower()
            if any(k in lowered for k in ("待验证", "未完成", "执行失败", "降级占位")):
                return True
        return False
    if isinstance(value, dict):
        # error dict 形态：{'error': '...'} / {'content': '...', 'error': '...'}
        if "error" in value:
            return True
        # content 字段是占位文本也算降级
        content = value.get("content") or value.get("markdown") or value.get("text")
        if isinstance(content, str) and content.strip():
            return is_degraded_placeholder(content)
        return False
    return False


def safe_extract(value: Any, default: str = "") -> str:
    """安全提取报告文本，降级占位返回空串（不混入下游推理）。

    替代各 adapter 里的 `str(report)` / `report.get('content', str(report))`，
    确保降级占位文本不被当作真实论据喂给 LLM。
    """
    if is_degraded_placeholder(value):
        return default
    if isinstance(value, dict):
        content = value.get("content") or value.get("markdown") or value.get("text")
        if isinstance(content, str) and content.strip():
            return content
        return default
    if isinstance(value, str):
        return value
    return default


def all_degraded(state: Any, fields: list) -> bool:
    """检查 state 中指定字段是否全部为降级占位（用于下游跳过判定）。

    任一字段有有效内容 → 返回 False（不跳过）。
    所有字段都降级/缺失 → 返回 True（跳过，不调 LLM）。
    """
    if not isinstance(state, dict):
        return True
    for field in fields:
        if not is_degraded_placeholder(state.get(field)):
            return False
    return True


def _card_text(state: Any, field: str) -> str:
    """从 state 中安全取出 dict 字段的 text 摘要"""
    if not isinstance(state, dict):
        return ""
    value = state.get(field)
    if isinstance(value, dict):
        text = value.get("text")
        return str(text) if text else ""
    return ""


def risk_profile_block(state: Any) -> str:
    """事前风险约束卡文本块（计划生成/审查必须遵守的硬约束）"""
    text = _card_text(state, "risk_profile_card")
    if not text:
        return ""
    return (
        "\n\n【事前风险约束卡（程序化生成，生成与评估计划时必须遵守）】\n"
        f"{text}"
    )


def simulation_block(state: Any) -> str:
    """情景效果试算文本块（机械计算结果，供风险评估参考）"""
    text = _card_text(state, "scenario_simulation")
    if not text:
        return ""
    return (
        "\n\n【情景效果试算（机械计算，非 LLM 观点；缺失项如实标注，"
        "评估时不得臆造补充）】\n"
        f"{text}"
    )


def append_flow_context(
    prompt: str,
    state: Any,
    include_profile: bool = True,
    include_simulation: bool = False,
) -> str:
    """在最终用户提示词后追加流程上下文块。

    Args:
        prompt: 已构建完成的用户提示词（模板路径或降级路径均可）
        state: 工作流 state（可能为 dict）
        include_profile: 是否追加事前风险约束卡
        include_simulation: 是否追加情景效果试算
    """
    if not prompt:
        return prompt
    blocks = []
    if include_profile:
        block = risk_profile_block(state)
        if block:
            blocks.append(block)
    if include_simulation:
        block = simulation_block(state)
        if block:
            blocks.append(block)
    if not blocks:
        return prompt
    return prompt + "\n".join(blocks)


def _report_text(value: Any) -> str:
    """提取报告纯文本（降级占位返回空串，供确定性节点安全消费）"""
    return safe_extract(value)


# ==================== 情景区间/基准价解析（risk_profile_v2 与 scenario_simulator_v2 共用） ====================

import re  # noqa: E402

# 情景价格区间：约1520—1660元 / 1380-1520元 / 3.5~3.8元 / 40.5—45.0 元 等变体
# 币种符号可前置（¥40.5—¥45.0），单位后缀必填，避免把日期/编号误配成区间
_RANGE_RE = re.compile(
    r"[¥￥]?(\d{1,6}(?:\.\d{1,3})?)\s*[—–\-~至]\s*[¥￥]?(\d{1,6}(?:\.\d{1,3})?)\s*"
    r"(?:元|港元|美元)"
)

# 基准价：收于 1523 元 / 现价1523元 / 收盘价 1523.50 元 /
# 市场报告表格形态「| 最新价格 | ¥40.40 |」/ 「**最新价**：40.40 元」
# 关键词与数字之间允许空白、Markdown 表格竖线、冒号、粗体符号与币种符号；
# 单位后缀可省（表格里价格常在独立单元格）
_PRICE_RE = re.compile(
    r"(?:最新价格|最新价|现价|收盘价|收于|报收|股价)"
    r"[\s|:：为是*]*[¥￥]?\s*"
    r"(\d{1,6}(?:\.\d{1,3})?)"
    r"\s*(?:元|港元|美元)?"
)


def _valid_price(value: float) -> bool:
    return 0.01 <= value <= 1_000_000


def parse_price_range(text: str):
    """从报告中解析首个有效价格区间，返回 (low, high) 或 None。

    合理性约束：low < high，且 high/low < 3（排除把两个无关数字误配成区间）。
    """
    for m in _RANGE_RE.finditer(text or ""):
        try:
            low, high = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if _valid_price(low) and _valid_price(high) and low < high and high / low < 3:
            return low, high
    return None


def parse_reference_price(text: str):
    """从市场报告中解析基准价（现价/收盘价），返回 float 或 None。"""
    for m in _PRICE_RE.finditer(text or ""):
        try:
            price = float(m.group(1))
        except ValueError:
            continue
        if _valid_price(price):
            return price
    return None

